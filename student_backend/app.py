from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import sqlite3
import os
import requests

app = Flask(__name__)
CORS(app)

DB_PATH = "student_data.db"
RAG_URL = "http://localhost:5000"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            roll_number TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            faculty_name TEXT,
            status TEXT DEFAULT 'scheduled'
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            session_id INTEGER,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            left_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS engagement_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            session_id INTEGER,
            event_type TEXT,
            score_delta INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

init_db()

def mcp_response(data=None, error=None):
    return jsonify({
        "success": error is None,
        "timestamp": datetime.now().isoformat(),
        "data": data,
        "error": error
    })

@app.route("/mcp/student_login", methods=["POST"])
def student_login():
    data = request.json
    name = data.get("name", "").strip()
    roll_number = data.get("roll_number", "").strip()
    if not name or not roll_number:
        return mcp_response(error="name and roll_number required"), 400
    conn = get_db()
    existing = conn.execute("SELECT * FROM students WHERE roll_number=?", (roll_number,)).fetchone()
    if existing:
        student = dict(existing)
    else:
        cursor = conn.execute("INSERT INTO students (name, roll_number) VALUES (?,?)", (name, roll_number))
        conn.commit()
        student = {"id": cursor.lastrowid, "name": name, "roll_number": roll_number}
    conn.close()
    return mcp_response(data={"student_id": student["id"], "name": student["name"], "roll_number": student["roll_number"]})

@app.route("/mcp/get_sessions", methods=["GET"])
def get_sessions():
    conn = get_db()
    sessions = conn.execute("SELECT * FROM sessions ORDER BY scheduled_date DESC").fetchall()
    conn.close()
    return mcp_response(data={"sessions": [dict(s) for s in sessions]})

@app.route("/mcp/join_session", methods=["POST"])
def join_session():
    data = request.json
    student_id = data.get("student_id")
    session_id = data.get("session_id")
    conn = get_db()
    session = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    if not session:
        conn.close()
        return mcp_response(error="Session not found"), 404
    existing = conn.execute("SELECT * FROM attendance WHERE student_id=? AND session_id=?", (student_id, session_id)).fetchone()
    if existing:
        att_id = existing["id"]
    else:
        cursor = conn.execute("INSERT INTO attendance (student_id, session_id) VALUES (?,?)", (student_id, session_id))
        conn.commit()
        att_id = cursor.lastrowid
    conn.close()
    return mcp_response(data={"attendance_id": att_id, "session": dict(session)})

@app.route("/mcp/start_lecture", methods=["POST"])
def start_lecture():
    data = request.json
    session_id = data.get("session_id")
    conn = get_db()
    session = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    if not session:
        return mcp_response(error="Session not found"), 404
    topic = session["topic"]
    subject = session["subject"]

    try:
        rag_resp = requests.post(f"{RAG_URL}/api/generate", json={
            "topic": topic,
            "subject": subject
        }, timeout=60)
        lecture_text = rag_resp.json().get("content", None)
        if not lecture_text:
            raise Exception("Empty response")
    except:
        lecture_text = f"Welcome to today's session on {topic} in {subject}. Let's begin with the fundamentals. {topic} is a core concept in {subject}. We will explore the key principles, definitions, and practical applications step by step. Pay close attention and feel free to ask any doubts."

    return mcp_response(data={"lecture_text": lecture_text, "topic": topic, "subject": subject})

@app.route("/mcp/ask_question", methods=["POST"])
def ask_question():
    data = request.json
    student_id = data.get("student_id")
    session_id = data.get("session_id")
    question = data.get("question", "").strip()
    mode = data.get("mode", "explanation")
    conn = get_db()
    session = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    topic = session["topic"] if session else "general"
    subject = session["subject"] if session else "general"

    if mode == "simplified":
        prompt = f"Explain simply in very basic terms: {question}"
    elif mode == "example":
        prompt = f"Explain with a clear real-world example: {question}"
    else:
        prompt = question

    try:
        rag_resp = requests.post(f"{RAG_URL}/api/generate", json={
            "topic": prompt,
            "subject": subject,
            "mode": mode
        }, timeout=60)
        answer = rag_resp.json().get("content", None)
        if not answer:
            raise Exception("Empty response")
    except:
        if mode == "simplified":
            answer = f"Simply put: '{question}' in {topic} means understanding the core concept step by step."
        elif mode == "example":
            answer = f"Here's an example for '{question}' in {topic}: Think of it like a real-world scenario where this concept applies directly."
        else:
            answer = f"Regarding '{question}' in {topic}: this is an important concept in {subject}. Understanding the fundamentals helps in applying them practically."

    conn = get_db()
    conn.execute("INSERT INTO engagement_log (student_id, session_id, event_type, score_delta) VALUES (?,?,?,?)",
                 (student_id, session_id, "asked_question", -1))
    conn.commit()
    conn.close()
    return mcp_response(data={"question": question, "answer": answer})

@app.route("/mcp/log_engagement", methods=["POST"])
def log_engagement():
    data = request.json
    student_id = data.get("student_id")
    session_id = data.get("session_id")
    event_type = data.get("event_type", "unknown")
    score_map = {"app_exit": -3, "app_return": 1, "idle_start": -1, "correct_answer": 3, "wrong_answer": -1}
    delta = score_map.get(event_type, 0)
    conn = get_db()
    conn.execute("INSERT INTO engagement_log (student_id, session_id, event_type, score_delta) VALUES (?,?,?,?)",
                 (student_id, session_id, event_type, delta))
    conn.commit()
    conn.close()
    return mcp_response(data={"logged": True})

@app.route("/mcp/leave_session", methods=["POST"])
def leave_session():
    data = request.json
    student_id = data.get("student_id")
    session_id = data.get("session_id")
    conn = get_db()
    conn.execute("UPDATE attendance SET left_at=? WHERE student_id=? AND session_id=?",
                 (datetime.now().isoformat(), student_id, session_id))
    conn.commit()
    conn.close()
    return mcp_response(data={"left": True})

@app.route("/admin/seed_session", methods=["POST"])
def seed_session():
    data = request.json
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO sessions (subject, topic, scheduled_date, faculty_name, status) VALUES (?,?,?,?,?)",
        (data.get("subject", "Computer Networks"), data.get("topic", "OSI Model"),
         data.get("date", datetime.now().strftime("%Y-%m-%d")),
         data.get("faculty", "Dr. Smith"), "active")
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return jsonify({"session_id": session_id, "message": "Session seeded"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)