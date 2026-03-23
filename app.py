# app.py — Smart AI Tutor — RAG Backend + Tutor Agent
# Port 5001

import sys
import os
import pathlib
import pdfplumber
import json
import io
import torch
import numpy as np

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS

from syllabus_parser import parse_syllabus
SYLLABUS_JSON = pathlib.Path("syllabus_structure.json")

# ── Point Python to RAG_steps folder ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "RAG_steps"))

# ── RAG imports ──
from embedding import debug_query, collection
from chunk_subsets import round_robin_from_results
from drafter import run_phi3_draft
from verifier import verify_drafts
from chunking import chunk_os_txt
from extract_images import extract_images_from_pdf

# ── Tutor Agent imports ──
from tutor_agent.adaptive_router import route_doubt
from tutor_agent.tool_selector import choose_tool
from tutor_agent.pedagogical_agent import teach_response
from tutor_agent.syllabus_guard import check_syllabus
from tutor_agent.misconception_detector import detect_misconception

# ── MCP Client — all tool calls go through the real MCP protocol ──
from tools.mcp_client import call_mcp_tool

# ── Memory import ──
from memory.context_memory import store_doubt, get_context

# ── Flask app ──
app = Flask(__name__, static_folder="static")
CORS(app,
     resources={r"/*": {"origins": "*"}},
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "Accept"])

# ── CORS preflight handler ──
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,Accept')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    return response

# ── Kokoro TTS init ──
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Kokoro TTS running on: {device.upper()}")

try:
    from kokoro import KPipeline
    import soundfile as sf
    tts_pipeline = KPipeline(lang_code='a')
    TTS_AVAILABLE = True
    print("✅ Kokoro TTS loaded")
except Exception as e:
    tts_pipeline = None
    TTS_AVAILABLE = False
    print(f"⚠️ Kokoro TTS not available: {e}")

# ── Folders ──
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
        # ✅ Fixed model name parsing
        models = [m.get("model", m.get("name", "")) for m in resp.get("models", [])]
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
        "tts_available": TTS_AVAILABLE,
    })


# ─────────────────────────────────────────
# ROUTE 3 — Upload single PDF
# ─────────────────────────────────────────
@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    subject = request.form.get("subject", "General").strip()

    if not file.filename.endswith(".pdf"):
        return jsonify({"error": "Only PDF files accepted"}), 400

    pdf_path = UPLOAD_FOLDER / file.filename
    file.save(pdf_path)

    # Extract images
    extract_images_from_pdf(str(pdf_path))

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

    chunk_os_txt(txt_path, module_id=1)

    chunks_path = txt_path.with_suffix(".chunks.json")
    if not chunks_path.exists():
        return jsonify({"error": "Chunking failed"}), 500

    with open(chunks_path, encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        return jsonify({"error": "No chunks produced"}), 400

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

    topics = list(set(c["topic"] for c in chunks if len(c.get("topic", "")) > 2))
    return jsonify({
        "success": True,
        "message": f"Indexed {len(chunks)} chunks from {file.filename}",
        "topics": topics[:25],
        "chunk_count": len(chunks),
    })


# ─────────────────────────────────────────
# ROUTE 3b — Upload multiple Notes PDFs
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
            pdf_path = UPLOAD_FOLDER / file.filename
            file.save(pdf_path)

            # Extract images
            extract_images_from_pdf(str(pdf_path))

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

            chunk_os_txt(txt_path, module_id=idx)

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
                ids=[f"{file.filename}__{c['id']}" for c in chunks],
            )

            results.append({"file": file.filename, "chunks": len(chunks), "success": True})

        except Exception as e:
            results.append({"file": file.filename, "error": str(e)})

    total_chunks = sum(r.get("chunks", 0) for r in results)
    return jsonify({"success": True, "total_chunks": total_chunks, "files": results})


# ─────────────────────────────────────────
# ROUTE 3c — Upload & Parse Syllabus PDF
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
        SYLLABUS_JSON.write_text(
            json.dumps(structure, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return jsonify({"success": True, "data": structure, "module_count": len(structure)})
    except Exception as e:
        return jsonify({"error": f"Syllabus parsing failed: {str(e)}"}), 500


# ─────────────────────────────────────────
# ROUTE 3d — Get persisted syllabus
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
# ─────────────────────────────────────────
@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.json

    module   = str(data.get("module", "")).strip()
    topic    = data.get("topic", "").strip()
    subtopic = data.get("subtopic", "").strip()
    subject  = data.get("subject", "").strip()

    if not topic:
        return jsonify({"error": "Topic is required"}), 400

    if collection.count() == 0:
        return jsonify({"error": "No notes indexed yet. Please upload a PDF first."}), 400

    query = f"""
Generate an incredibly comprehensive, in-depth lecture script on the Operating Systems topic: "{topic}".
This should simulate a full 1-hour university lecture. You must cover the topic very broadly and deeply, not just a small sub-section, using easy-to-understand language.

Context Constraints:
Module: {module}
Topic: {topic}
Subtopic: {subtopic}

Your comprehensive lecture MUST include:
• A detailed introduction and broad overview of {topic}
• In-depth definitions and core mechanisms based strictly on the text
• Step-by-step working principles
• Multiple real-world examples and analogies to explain complex parts broadly
• Key concepts and potential exam questions
• A thorough summary at the end

You are simulating a 1-hour university lecture, so be highly informative and engaging.
CRITICAL CONSTRAINT: Although you must be highly expansive and illustrative, DO NOT invent new major sub-topics or protocols that are not present anywhere in the provided context chunks. Anchor your lecture firmly in the facts provided.
"""

    # STEP 1 — Retrieve
    results = debug_query(f"{topic} {subtopic}", k=15)
    if not results["documents"][0]:
        return jsonify({"error": "No relevant content found"}), 404

    # STEP 2 — Group
    groups = round_robin_from_results(results, num_groups=2)

    chunk_lookup = {}
    for group in groups:
        for ch in group:
            chunk_lookup[ch["chunk_id"]] = {
                "content":   ch["content"],
                "topic":     ch["metadata"].get("topic", ""),
                "page_hint": ch["metadata"].get("page_hint", ""),
                "source_file": ch["metadata"].get("source_file", "")
            }

    # STEP 3 — Draft
    drafts = []
    for group in groups:
        context_chunks = [
            {
                "id":        ch["metadata"]["id"],
                "content":   ch["content"],
                "topic":     ch["metadata"].get("topic", ""),
                "page_hint": ch["metadata"].get("page_hint", ""),
                "source_file": ch["metadata"].get("source_file", "")
            }
            for ch in group
        ]
        draft = run_phi3_draft(query, context_chunks)
        drafts.append(draft)

    # STEP 4 — Verify
    answer = verify_drafts(query, drafts, chunk_lookup)

    # Collect relevant images based on chunk page_hints
    import re
    images = []
    
    # Use the server's base URL for static images. In production, this would be an env var.
    base_url = "http://localhost:5001/static/images"
    
    for ch_id, ch_info in chunk_lookup.items():
        page_hint = ch_info.get("page_hint", "")
        if not page_hint:
            continue
            
        # Example page_hint: "Page 4-5" or "Page 4"
        pages_found = re.findall(r'\d+', page_hint)
        if not pages_found:
            continue
            
        start_page = int(pages_found[0])
        end_page = int(pages_found[-1]) if len(pages_found) > 1 else start_page
        
        source_file = ch_info.get("source_file", "")
        if not source_file:
            continue
            
        source_stem = source_file.replace(".txt", "")
        for p in range(start_page, end_page + 1):
            image_dir = pathlib.Path("static/images") / source_stem
            if image_dir.exists():
                for img_path in image_dir.glob(f"page_{p}_*"):
                    url = f"{base_url}/{source_stem}/{img_path.name}"
                    if url not in images:
                        images.append(url)
                        
    cleaned_lecture = re.sub(r'[*#_~`]', '', answer["final_answer"])

    return jsonify({
        "module":   module,
        "topic":    topic,
        "subtopic": subtopic,
        "content":  cleaned_lecture,
        "rationale": answer["verification_rationale"],
        "status":   "success",
        "images":   images
    })


# ─────────────────────────────────────────
# ROUTE 6 — Text to Speech (Kokoro)
# ─────────────────────────────────────────
@app.route("/api/tts", methods=["POST"])
def tts():
    if not TTS_AVAILABLE:
        return jsonify({"error": "TTS not available — install kokoro"}), 503

    data = request.json
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        generator = tts_pipeline(text, voice='af_sarah', speed=0.95)

        audio_chunks = []
        for _, _, audio in generator:
            audio_chunks.append(audio)

        full_audio = np.concatenate(audio_chunks)

        buffer = io.BytesIO()
        import soundfile as sf
        sf.write(buffer, full_audio, 24000, format='WAV')
        buffer.seek(0)

        return send_file(buffer, mimetype='audio/wav', as_attachment=False, download_name='lecture.wav')

    except Exception as e:
        print(f"TTS error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────
# ROUTE 7 — Student Doubt (Tutor Agent)
# ─────────────────────────────────────────
@app.route("/api/doubt", methods=["POST"])
def doubt():
    data = request.json

    student_id    = str(data.get("student_id", "default"))
    doubt_text    = data.get("doubt", "").strip()
    lecture_topic = data.get("topic", "").strip()

    if not doubt_text:
        return jsonify({"error": "No doubt provided"}), 400

    # ── Step 1: Store in memory ──
    store_doubt(student_id, doubt_text)
    previous = get_context(student_id)

    # ── Step 2: Adaptive Router ──
    try:
        route = route_doubt(doubt_text, lecture_topic)
    except Exception as e:
        print(f"Router error: {e}")
        route = {"type": "concept", "reason": "fallback", "needs_external": False}

    # ── Step 3: Syllabus Guard ──
    # If the router explicitly says out_of_syllabus, or if the keyword check fails
    if route.get("type") == "out_of_syllabus" or not check_syllabus(doubt_text):
        return jsonify({
            "response": "This question appears to be outside the current syllabus. Please ask questions related to the topics covered in your notes.",
            "route":    "out_of_syllabus",
            "tool":     "none"
        })

    # ── Step 4: Misconception Detector ──
    try:
        is_misconception = detect_misconception(doubt_text)
        if is_misconception:
            route["type"] = "misconception"
    except Exception as e:
        print(f"Misconception detector error: {e}")

    # ── Step 5: Tool Selection ──
    # Pass the doubt text so the selector can apply OS-keyword heuristic
    route["doubt"] = doubt_text
    tool = choose_tool(route)

    # ── Step 6: Execute Tool via MCP Protocol ──
    # Map internal tool names → MCP tool names on the server
    _TOOL_MAP = {
        "rag":       "rag_answer",
        "os_docs":   "os_docs_search",
        "wikipedia": "wikipedia_search",
    }
    mcp_tool_name = _TOOL_MAP.get(tool, "rag_answer")
    try:
        print(f"[MCP] Calling tool '{mcp_tool_name}' for doubt: {doubt_text[:60]}...")
        raw_answer = call_mcp_tool(mcp_tool_name, {"query": doubt_text})
    except Exception as e:
        print(f"MCP tool error: {e}")
        raw_answer = f"I found some information about {doubt_text} but encountered an issue retrieving it. Please try again."

    # ── Step 7: Pedagogical Agent ──
    # Only run for RAG — wikipedia & os_docs already return clean readable text,
    # so we skip the extra LLM call for speed.
    if tool == "rag":
        try:
            final_response = teach_response(doubt_text, raw_answer)
        except Exception as e:
            print(f"Pedagogical agent error: {e}")
            final_response = raw_answer
    else:
        print(f"[Pedagogical Agent] Skipped for tool='{tool}' — returning raw MCP result.")
        final_response = raw_answer

    # ── Output Cleaning (Remove Markdown) ──
    import re
    final_response_clean = re.sub(r'[*#_~`]', '', final_response)

    return jsonify({
        "response":  final_response_clean,
        "route":     route.get("type", "concept"),
        "tool":      tool,
        "previous_doubts_count": len(previous)
    })


# ─────────────────────────────────────────
# ROUTE 8 — Get student doubt history
# ─────────────────────────────────────────
@app.route("/api/doubt_history", methods=["GET"])
def doubt_history():
    student_id = request.args.get("student_id", "default")
    history = get_context(student_id)
    return jsonify({"student_id": student_id, "history": history})


if __name__ == "__main__":
    print("\n🤖 Smart AI Tutor — starting...")
    print("📌 Faculty Portal: http://localhost:5001")
    print("📌 Tutor Agent:    http://localhost:5001/api/doubt\n")
    app.run(debug=False, port=5001)