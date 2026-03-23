# run_all.py — Smart AI Tutor
# Starts both Python backends together.
# Run:  python run_all.py
# Then in a separate terminal: cd student_app && flutter run -d chrome

import subprocess
import sys
import time
import signal
import os
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

processes = []

def cleanup(sig=None, frame=None):
    print("\n🛑 Shutting down backends...")
    for name, p in processes:
        print(f"   Stopping {name}...")
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    print("✅ Backends stopped.")
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def wait_for_server(url, name, timeout=120):
    print(f"⏳ Waiting for {name} to be ready...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                print(f"✅ {name} is ready!")
                return True
        except Exception:
            pass
        time.sleep(2)
    print(f"❌ {name} failed to start within {timeout}s")
    return False

print("🚀 Starting Smart AI Tutor backends...\n")

# ── Backend 1: Tutor / RAG / MCP server (port 5001) ──────────────────────────
rag_script = os.path.join(BASE_DIR, "app.py")
print(f"▶ Starting Tutor + RAG Backend (port 5001): {rag_script}")

rag = subprocess.Popen(
    [sys.executable, rag_script],
    cwd=BASE_DIR,
    stdout=sys.stdout,
    stderr=sys.stderr,
)
processes.append(("Tutor + RAG Backend", rag))

time.sleep(5)

if not wait_for_server("http://localhost:5001/api/status", "Tutor + RAG Backend"):
    print("❌ Tutor + RAG backend failed to start. Aborting.")
    cleanup()

# ── Backend 2: Student REST API (port 5000) ───────────────────────────────────
student_script = os.path.join(BASE_DIR, "student_backend", "app.py")
print(f"\n▶ Starting Student REST API (port 5000): {student_script}")

if not os.path.exists(student_script):
    print(f"❌ Cannot find: {student_script}")
    cleanup()

student = subprocess.Popen(
    [sys.executable, student_script],
    cwd=os.path.join(BASE_DIR, "student_backend"),
    stdout=sys.stdout,
    stderr=sys.stderr,
)
processes.append(("Student REST API", student))

if not wait_for_server("http://localhost:5000/mcp/get_sessions", "Student REST API"):
    print("❌ Student REST API failed to start. Aborting.")
    cleanup()

print("\n" + "="*55)
print("✅ Both backends are running!")
print("="*55)
print("   📚 Tutor + RAG Backend  →  http://localhost:5001")
print("   👨‍🎓 Student REST API     →  http://localhost:5000")
print("   🔧 MCP Tool Server      →  auto-started inside port 5001")
print()
print("👉 In a NEW terminal, run Flutter:")
print("   cd student_app")
print("   flutter run -d chrome")
print()
print("Press Ctrl+C to stop both backends.")
print("="*55 + "\n")

while True:
    for name, p in processes:
        if p.poll() is not None:
            print(f"\n💥 {name} crashed! (exit code {p.returncode})")
            cleanup()
    time.sleep(3)