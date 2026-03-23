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

from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

def now_ist():
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

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
    status TEXT DEFAULT 'scheduled',
    lecture_text TEXT,
    image_urls TEXT,
    start_time TEXT,
    end_time TEXT
);
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            session_id INTEGER,
            joined_at TIMESTAMP,
            left_at TIMESTAMP,
            is_late BOOLEAN DEFAULT 0
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
    
    # Try adding the columns if they don't exist
    columns_to_add = [
        ("sessions", "lecture_text TEXT"),
        ("sessions", "image_urls TEXT"),
        ("sessions", "start_time TEXT"),
        ("sessions", "end_time TEXT"),
        ("attendance", "is_late BOOLEAN DEFAULT 0")
    ]
    
    for table, column_def in columns_to_add:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
            conn.commit()
        except sqlite3.OperationalError:
            pass # Column already exists
    
    conn.close()

init_db()

def mcp_response(data=None, error=None):
    return jsonify({
        "success": error is None,
        "timestamp": now_ist(),
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
    
    session_dict = dict(session)
    is_late = False
    start_time_str = session_dict.get("start_time")
    date_str = session_dict.get("scheduled_date")
    if start_time_str and date_str:
        try:
            # Check if current time is > 5 minutes past start_time
            start_dt = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %H:%M")
            if (datetime.now() - start_dt).total_seconds() > 300:
                is_late = True
        except ValueError:
            pass

    existing = conn.execute("SELECT * FROM attendance WHERE student_id=? AND session_id=?", (student_id, session_id)).fetchone()
    if existing:
        att_id = existing["id"]
    else:
        cursor = conn.execute(
    "INSERT INTO attendance (student_id, session_id, joined_at, is_late) VALUES (?,?,?,?)",
    (student_id, session_id, now_ist(), is_late)
)
        conn.commit()
        att_id = cursor.lastrowid
    conn.close()
    return mcp_response(data={"attendance_id": att_id, "session": session_dict})

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
    lecture_text = session.get("lecture_text")
    image_urls_str = session.get("image_urls")
    
    import json
    images = []
    if image_urls_str:
        try:
            images = json.loads(image_urls_str)
        except Exception:
            images = []

    if not lecture_text:
        # Fallback if no lecture text was pre-generated
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
            print(f"RAG error in start_lecture fallback: {e}")
            lecture_text = (
                f"Welcome to today's session on {topic} in {subject}. "
                f"Let's begin with the fundamentals of {topic}."
            )

    return mcp_response(data={
        "lecture_text": lecture_text,
        "topic":        topic,
        "subject":      subject,
        "images":       images,
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

    # ✅ Build mode-aware question
    if mode == "simplified":
        rag_question = f"Explain in very simple basic terms for a beginner: {question}"
    elif mode == "example":
        rag_question = f"Explain with a clear real-world example: {question}"
    else:
        rag_question = question

    try:
        # ✅ Call /api/doubt with correct field names
        rag_resp = requests.post(
            f"{RAG_URL}/api/doubt",
            json={
                "student_id": str(student_id),
                "doubt":      rag_question,   # ✅ "doubt" not "topic"
                "topic":      topic,           # ✅ lecture topic for context
            },
            timeout=600,
        )
        rag_resp.raise_for_status()
        result = rag_resp.json()
        answer = result.get("response")       # ✅ "response" not "content"

        if not answer:
            raise Exception("Empty response from tutor agent")

    except Exception as e:
        print(f"Tutor agent error in ask_question: {e}")
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
                 (now_ist(), student_id, session_id))
    conn.commit()
    conn.close()
    return mcp_response(data={"left": True})

@app.route("/admin/seed_session", methods=["POST"])
def seed_session():
    data = request.json or {}
    subject = data.get("subject", "Operating Systems")
    topic = data.get("topic", "")
    faculty = data.get("faculty", "")
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    start_time = data.get("start_time", "09:00:00")
    end_time = data.get("end_time", "10:00:00")

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO sessions (subject, topic, scheduled_date, faculty_name, start_time, end_time) VALUES (?,?,?,?,?,?)",
        (subject, topic, date_str, faculty, start_time, end_time)
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()

    return jsonify({"session_id": session_id, "message": "Session seeded"})

@app.route("/admin/upload_and_generate_lecture", methods=["POST"])
def upload_and_generate_lecture():
    session_id = request.form.get("session_id")
    subject = request.form.get("subject", "Operating Systems")
    topic = request.form.get("topic", "")
    notes_file = request.files.get("notes") # PDF file

    import json
    lecture_content = ""
    images = []

    if notes_file:
        try:
            files = {'files': (notes_file.filename, notes_file.read(), notes_file.content_type)}
            upload_data = {'subject': subject}
            rag_upload_resp = requests.post(f"{RAG_URL}/api/upload_notes", files=files, data=upload_data, timeout=120)
            rag_upload_resp.raise_for_status()

            rag_gen_resp = requests.post(f"{RAG_URL}/api/generate", json={
                "module": "",
                "topic": subject + " — " + topic,
                "subtopic": "",
                "subject": subject
            }, timeout=300)
            
            if rag_gen_resp.status_code == 200:
                gen_data = rag_gen_resp.json()
                lecture_content = gen_data.get("content", "")
                images = gen_data.get("images", [])
        except Exception as e:
            print(f"Error communicating with RAG backend: {e}")
            return jsonify({"error": str(e)}), 500

    conn = get_db()
    conn.execute("UPDATE sessions SET lecture_text=?, image_urls=? WHERE id=?", (lecture_content, json.dumps(images), session_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Lecture generated successfully"})

@app.route("/admin/delete_session", methods=["POST"])
def delete_session():
    data = request.json or {}
    session_id = data.get("session_id")
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    conn.execute("DELETE FROM attendance WHERE session_id=?", (session_id,))
    conn.execute("DELETE FROM engagement_log WHERE session_id=?", (session_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Session deleted"})

@app.route("/admin/get_attendance_report", methods=["GET"])
def get_attendance_report():
    session_id = request.args.get("session_id")
    conn = get_db()
    query = """
    SELECT s.name, s.roll_number, a.joined_at, a.left_at, a.is_late
    FROM attendance a
    JOIN students s ON a.student_id = s.id
    WHERE a.session_id = ?
    ORDER BY a.joined_at ASC
    """
    records = conn.execute(query, (session_id,)).fetchall()
    conn.close()
    return jsonify({"attendance": [dict(r) for r in records]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)