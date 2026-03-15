from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import sqlite3
import os
import requests

app = Flask(__name__)
CORS(app, 
     resources={r"/*": {"origins": "*"}},
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "Accept"])

DB_PATH = "student_data.db"
RAG_URL = "http://localhost:5001"

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
    module TEXT,
    topic TEXT NOT NULL,
    subtopic TEXT,
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

    session = dict(session)
    topic    = session["topic"]
    subject  = session["subject"]

    try:
        rag_resp = requests.post(
            f"{RAG_URL}/api/generate",
            json={
                "module":   session.get("module", ""),
                "topic":    topic,
                "subtopic": session.get("subtopic", ""),
                "subject":  subject,
            },
            timeout=300,  # ✅ 5 mins — RAG pipeline needs time
        )
        rag_resp.raise_for_status()
        result = rag_resp.json()
        lecture_text = result.get("content")

        if not lecture_text:
            raise Exception("Empty response from RAG")

    except Exception as e:
        print(f"RAG error in start_lecture: {e}")
        lecture_text = (
            f"Welcome to today's session on {topic} in {subject}. "
            f"Let's begin with the fundamentals of {topic}."
        )

    return mcp_response(data={
        "lecture_text": lecture_text,
        "topic":        topic,
        "subject":      subject,
    })

@app.route("/mcp/ask_question", methods=["POST"])
def ask_question():
    data = request.json
    student_id = data.get("student_id")
    session_id = data.get("session_id")
    question   = data.get("question", "").strip()
    mode       = data.get("mode", "explanation")

    conn = get_db()
    session = conn.execute(
        "SELECT * FROM sessions WHERE id=?", (session_id,)
    ).fetchone()
    conn.close()

    session  = dict(session) if session else {}
    topic    = session.get("topic", "general")
    subject  = session.get("subject", "general")

    # ✅ Build mode-aware question to send to RAG
    if mode == "simplified":
        rag_question = f"Explain in very simple basic terms for a beginner: {question}"
    elif mode == "example":
        rag_question = f"Explain with a clear real-world example: {question}"
    else:
        rag_question = question

    try:
        rag_resp = requests.post(
            f"{RAG_URL}/api/generate",
            json={
                "module":   session.get("module", ""),
                "topic":    rag_question,   # ✅ send actual question as topic
                "subtopic": session.get("subtopic", ""),
                "subject":  subject,
            },
            timeout=300,  # ✅ increased timeout
        )
        rag_resp.raise_for_status()
        answer = rag_resp.json().get("content")

        if not answer:
            raise Exception("Empty response from RAG")

    except Exception as e:
        print(f"RAG error in ask_question: {e}")
        # ✅ Fallback is now question-aware
        if mode == "simplified":
            answer = f"Simply put: {question} — this relates to {topic} which is a core concept in {subject}."
        elif mode == "example":
            answer = f"For example, in {topic}: {question} can be understood by thinking about how the OS handles this in practice."
        else:
            answer = f"Regarding your question about {question} in {topic}: this is an important concept in {subject}."

    # Log engagement
    conn = get_db()
    conn.execute(
        "INSERT INTO engagement_log (student_id, session_id, event_type, score_delta) VALUES (?,?,?,?)",
        (student_id, session_id, "asked_question", -1),
    )
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
    "INSERT INTO sessions (subject, topic, scheduled_date) VALUES (?,?,?)",
    (
        data.get("subject", "Operating Systems"),
        data.get("topic", ""),
        data.get("date", datetime.now().strftime("%Y-%m-%d")),
    )
)
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()
    return jsonify({"session_id": session_id, "message": "Session seeded"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)