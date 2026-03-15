# app.py — Thin Flask wrapper
# Only sets up routes and calls your existing RAG_steps files as-is

import sys
import os
import pathlib
import pdfplumber
import json

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from syllabus_parser import parse_syllabus
SYLLABUS_JSON = pathlib.Path("syllabus_structure.json")

# ── Point Python to your RAG_steps folder ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "RAG_steps"))

# ── Import YOUR existing functions unchanged ──
from embedding import debug_query, collection        # your embedding.py
from chunk_subsets import round_robin_from_results   # your chunk_subsets.py
from drafter import run_phi3_draft                   # your drafter.py
from verifier import verify_drafts                   # your verifier.py
from chunking import chunk_os_txt                    # your chunking.py

app = Flask(__name__, static_folder="static")
CORS(app)

# app.py — add this import at top
from kokoro import KPipeline
import soundfile as sf
import io
from flask import send_file
import torch

# ✅ Initialize Kokoro once globally (loads ~350MB model)
device = 'cuda' if torch.cuda.is_available() else 'cpu'
tts_pipeline = KPipeline(lang_code='a')  # 'a' = American English

# ─────────────────────────────────────────
# ROUTE 6 — Text to Speech
# ─────────────────────────────────────────
@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.json
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # ✅ af_sarah = natural female professor voice
        # Other good voices: af_nova, af_jessica, am_adam (male)
        generator = tts_pipeline(
            text,
            voice='af_sarah',
            speed=0.95   # slightly slower = clearer for students
        )

        # Collect all audio chunks
        import numpy as np
        audio_chunks = []
        for _, _, audio in generator:
            audio_chunks.append(audio)

        full_audio = np.concatenate(audio_chunks)

        # Write to buffer and send as WAV
        buffer = io.BytesIO()
        sf.write(buffer, full_audio, 24000, format='WAV')
        buffer.seek(0)

        return send_file(
            buffer,
            mimetype='audio/wav',
            as_attachment=False,
            download_name='lecture.wav'
        )

    except Exception as e:
        print(f"TTS error: {e}")
        return jsonify({"error": str(e)}), 500

UPLOAD_FOLDER = pathlib.Path("uploads")
UPLOAD_FOLDER.mkdir(exist_ok=True)
TEXT_FOLDER = pathlib.Path("output_text")
TEXT_FOLDER.mkdir(exist_ok=True)

# ─────────────────────────────────────────
# ROUTE 1 — Serve the UI
# ─────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ─────────────────────────────────────────
# ROUTE 2 — Check system status
# ─────────────────────────────────────────
@app.route("/api/status")
def status():
    import ollama as ol
    ollama_ok = False
    models = []
    try:
        resp = ol.list()
        models = [m["name"] for m in resp.get("models", [])]
        ollama_ok = True
    except:
        pass

    try:
        chunk_count = collection.count()
    except:
        chunk_count = 0

    return jsonify({
        "ollama": ollama_ok,
        "models": models,
        "indexed_chunks": chunk_count,
    })


# ─────────────────────────────────────────
# ROUTE 3 — Upload PDF
# Runs: pdfplumber extract → your chunking.py → your embedding.py
# ─────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    subject = request.form.get("subject", "General").strip()

    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files accepted"}), 400

    # Save PDF
    pdf_path = UPLOAD_FOLDER / file.filename
    file.save(pdf_path)

    # Extract text using pdfplumber (same as your extract_pdf.py)
    txt_path = TEXT_FOLDER / (pdf_path.stem + ".txt")
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(layout=True)
            if text:
                cleaned = "\n".join(
                    line.rstrip() for line in text.splitlines() if line.strip()
                )
                parts.append(f"\n\n--- Page {i+1} ---\n{cleaned}")
    txt_path.write_text("".join(parts), encoding="utf-8")

    # Chunk using YOUR chunking.py
    # module_id=1 for uploaded files (can extend later)
    chunk_os_txt(txt_path, module_id=1)

    # Now embed the chunks using YOUR embedding.py
    import json
    chunks_path = txt_path.with_suffix(".chunks.json")
    if not chunks_path.exists():
        return jsonify({"error": "Chunking failed"}), 500

    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        return jsonify({"error": "No chunks produced"}), 400

    # Add subject to metadata and add to your collection
    from chromadb.utils import embedding_functions
    collection.add(
        documents=[c["content"] for c in chunks],
        metadatas=[{
            "id":          str(c["id"]),
            "module":      int(c.get("module", 1)),
            "topic":       str(c.get("topic", "")),
            "page_hint":   str(c.get("page_hint", "")),
            "source_file": str(c.get("source_file", file.filename)),
            "subject":     subject,
        } for c in chunks],
        ids=[str(c["id"]) for c in chunks],
    )

    topics = list(set(c["topic"] for c in chunks if len(c.get("topic","")) > 2))

    return jsonify({
        "success": True,
        "message": f"Indexed {len(chunks)} chunks from {file.filename}",
        "topics": topics[:25],
        "chunk_count": len(chunks),
    })
# ─────────────────────────────────────────
# ROUTE 3b — Upload multiple Notes PDFs at once
# Each file: pdfplumber extract → chunk → embed into ChromaDB
# ─────────────────────────────────────────
@app.route("/api/upload_notes", methods=["POST"])
def upload_notes():
    if "files" not in request.files:
        return jsonify({"error": "No files provided"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files provided"}), 400

    subject = request.form.get("subject", "General").strip()
    results = []

    for idx, file in enumerate(files, start=1):
        if not file.filename.endswith(".pdf"):
            results.append({"file": file.filename, "error": "Skipped — not a PDF"})
            continue

        try:
            # Save PDF
            pdf_path = UPLOAD_FOLDER / file.filename
            file.save(pdf_path)

            # Extract text
            txt_path = TEXT_FOLDER / (pdf_path.stem + ".txt")
            parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text(layout=True)
                    if text:
                        cleaned = "\n".join(
                            line.rstrip() for line in text.splitlines() if line.strip()
                        )
                        parts.append(f"\n\n--- Page {i+1} ---\n{cleaned}")
            txt_path.write_text("".join(parts), encoding="utf-8")

            # Chunk
            chunk_os_txt(txt_path, module_id=idx)

            # Embed
            chunks_path = txt_path.with_suffix(".chunks.json")
            if not chunks_path.exists():
                results.append({"file": file.filename, "error": "Chunking failed"})
                continue

            with open(chunks_path, encoding="utf-8") as f:
                chunks = json.load(f)

            if not chunks:
                results.append({"file": file.filename, "error": "No chunks produced"})
                continue

            collection.add(
                documents=[c["content"] for c in chunks],
                metadatas=[{
                    "id":          str(c["id"]),
                    "module":      int(c.get("module", idx)),
                    "topic":       str(c.get("topic", "")),
                    "page_hint":   str(c.get("page_hint", "")),
                    "source_file": str(c.get("source_file", file.filename)),
                    "subject":     subject,
                } for c in chunks],
                # Prefix filename to avoid ID collisions across multiple uploads
                ids=[f"{file.filename}__{c['id']}" for c in chunks],
            )

            results.append({
                "file": file.filename,
                "chunks": len(chunks),
                "success": True,
            })

        except Exception as e:
            results.append({"file": file.filename, "error": str(e)})

    total_chunks = sum(r.get("chunks", 0) for r in results)
    return jsonify({
        "success": True,
        "total_chunks": total_chunks,
        "files": results,
    })


# ─────────────────────────────────────────
# ROUTE 3c — Upload & Parse Syllabus PDF
# Calls syllabus_parser.py → returns Module→Topic→Subtopic tree
# Saves result to syllabus_structure.json for persistence
# ─────────────────────────────────────────
@app.route("/api/upload_syllabus", methods=["POST"])
def upload_syllabus():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files accepted"}), 400

    pdf_path = UPLOAD_FOLDER / "syllabus.pdf"
    file.save(pdf_path)

    try:
        structure = parse_syllabus(str(pdf_path))
        # Persist so dropdowns survive page refresh / server restart
        SYLLABUS_JSON.write_text(
            json.dumps(structure, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return jsonify({
            "success": True,
            "data": structure,
            "module_count": len(structure),
        })
    except Exception as e:
        return jsonify({"error": f"Syllabus parsing failed: {str(e)}"}), 500


# ─────────────────────────────────────────
# ROUTE 3d — Get persisted syllabus structure
# Called on page load to restore dropdowns without re-uploading
# ─────────────────────────────────────────
@app.route("/api/syllabus")
def get_syllabus():
    if not SYLLABUS_JSON.exists():
        return jsonify({"data": {}}), 200
    try:
        structure = json.loads(SYLLABUS_JSON.read_text(encoding="utf-8"))
        return jsonify({"data": structure, "module_count": len(structure)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ─────────────────────────────────────────
# ROUTE 4 — Get all indexed topics
# ─────────────────────────────────────────
@app.route("/api/topics")
def get_topics():
    try:
        res = collection.get(include=["metadatas"])
        topics   = list(set(m["topic"]   for m in res["metadatas"] if m.get("topic")))
        subjects = list(set(m["subject"] for m in res["metadatas"] if m.get("subject")))
        return jsonify({"topics": topics, "subjects": subjects})
    except:
        return jsonify({"topics": [], "subjects": []})


# ─────────────────────────────────────────
# ROUTE 5 — Generate lecture (full RAG pipeline)
# Runs: debug_query → round_robin → run_qwen2.5_draft x3 → verify_drafts
# ─────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate():

    data = request.json

    module = str(data.get("module", "")).strip()
    topic = data.get("topic", "").strip()
    subtopic = data.get("subtopic", "").strip()
    subject = data.get("subject", "").strip()

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    if collection.count() == 0:
        return jsonify({"error": "No notes indexed yet. Please upload a PDF first."}), 400


    # Build syllabus-aware query
    query = f"""
Explain this Operating Systems topic clearly for students.

Module: {module}
Topic: {topic}
Subtopic: {subtopic}

Your explanation must cover:
• definitions
• working principle
• examples if applicable
• key concepts required for exams
"""


    # STEP 1 — Retrieve chunks
    results = debug_query(f"{topic} {subtopic}", k=15)

    if not results["documents"][0]:
        return jsonify({"error": "No relevant content found"}), 404


    # STEP 2 — Speculative grouping
    groups = round_robin_from_results(results, num_groups=2)


    chunk_lookup = {}

    for group in groups:
        for ch in group:
            chunk_lookup[ch["chunk_id"]] = {
                "content": ch["content"],
                "topic": ch["metadata"].get("topic", ""),
                "page_hint": ch["metadata"].get("page_hint", "")
            }


    # STEP 3 — Draft generation
    drafts = []

    for group in groups:

        context_chunks = [
            {
                "id": ch["metadata"]["id"],
                "content": ch["content"],
                "topic": ch["metadata"].get("topic", ""),
                "page_hint": ch["metadata"].get("page_hint", "")
            }
            for ch in group
        ]

        draft = run_phi3_draft(query, context_chunks)
        drafts.append(draft)


    # STEP 4 — Verification
    answer = verify_drafts(query, drafts, chunk_lookup)


    return jsonify({
        "module": module,
        "topic": topic,
        "subtopic": subtopic,
        "content": answer["final_answer"],
        "rationale": answer["verification_rationale"],
        "status": "success"
    })

    
    # ... (remaining code unchanged)
if __name__ == "__main__":
    print("\n🤖 Smart AI Tutor — starting...")
    print("📌 Open: http://localhost:5001\n")
    app.run(debug=False, port=5001)
