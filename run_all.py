# run_all.py
import subprocess
import sys
import time
import signal
import os
import requests

# ✅ Always resolve paths relative to this script's location
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
    print(f"⏳ Waiting for {name}...")
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

# ── Step 1: RAG backend ───────────────────────────────────────
rag_script = os.path.join(BASE_DIR, "app.py")
print(f"▶ Starting RAG backend: {rag_script}")

rag = subprocess.Popen(
    [sys.executable, rag_script],
    cwd=BASE_DIR,              # ✅ run from project root
    stdout=sys.stdout,
    stderr=sys.stderr,
)
processes.append(("RAG Backend", rag))

time.sleep(5)  # ✅ let Flask fully boot before polling

if not wait_for_server("http://localhost:5001/api/status", "RAG Backend"):
    print("❌ RAG backend failed. Aborting.")
    cleanup()

# ── Step 2: MCP backend ───────────────────────────────────────
mcp_script = os.path.join(BASE_DIR, "student_backend", "app.py")
print(f"\n▶ Starting MCP backend: {mcp_script}")

# ✅ Verify file exists before trying to launch
if not os.path.exists(mcp_script):
    print(f"❌ Cannot find: {mcp_script}")
    print("   Check your folder structure!")
    cleanup()

mcp = subprocess.Popen(
    [sys.executable, mcp_script],
    cwd=os.path.join(BASE_DIR, "student_backend"),  # ✅ run from its own folder
    stdout=sys.stdout,
    stderr=sys.stderr,
)
processes.append(("MCP Backend", mcp))

if not wait_for_server("http://localhost:5000/mcp/get_sessions", "MCP Backend"):
    print("❌ MCP backend failed. Aborting.")
    cleanup()

print("\n" + "="*50)
print("✅ Both backends are running!")
print("="*50)
print("   📚 Faculty Portal  → http://localhost:5001")
print("   👨‍🎓 MCP API         → http://localhost:5000")
print("\n👉 Open a NEW terminal and run:")
print("   cd student_app")
print("   flutter run -d chrome")
print("\nPress Ctrl+C to stop both backends.")
print("="*50 + "\n")

while True:
    for name, p in processes:
        if p.poll() is not None:
            print(f"\n💥 {name} crashed! (exit code {p.returncode})")
            cleanup()
    time.sleep(3)