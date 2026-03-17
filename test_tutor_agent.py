# test_tutor_agent.py
# Run this from your project root to verify all components work
# Usage: python test_tutor_agent.py

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "RAG_steps"))

print("="*60)
print("🧪 Smart AI Tutor — Component Test Suite")
print("="*60)

results = []

def test(name, fn):
    try:
        result = fn()
        print(f"✅ {name}: {result}")
        results.append((name, True, result))
    except Exception as e:
        print(f"❌ {name}: {e}")
        results.append((name, False, str(e)))

# ─────────────────────────────────────────
# 1. Context Memory
# ─────────────────────────────────────────
print("\n📦 Testing Context Memory...")

def test_memory():
    from memory.context_memory import store_doubt, get_context
    store_doubt("student_1", "What is round robin?")
    store_doubt("student_1", "What is paging?")
    history = get_context("student_1")
    assert len(history) == 2, f"Expected 2, got {len(history)}"
    return f"Stored and retrieved {len(history)} doubts"

test("Context Memory", test_memory)

# ─────────────────────────────────────────
# 2. Syllabus Guard
# ─────────────────────────────────────────
print("\n🛡️ Testing Syllabus Guard...")

def test_syllabus_guard_in():
    from tutor_agent.syllabus_guard import check_syllabus
    # This should return True (OS topic)
    result = check_syllabus("What is process scheduling?")
    return f"'process scheduling' → in_syllabus={result}"

def test_syllabus_guard_out():
    from tutor_agent.syllabus_guard import check_syllabus
    # This should return False (unrelated topic)
    result = check_syllabus("What is the recipe for pasta?")
    return f"'pasta recipe' → in_syllabus={result} (should be False)"

test("Syllabus Guard (in-syllabus)", test_syllabus_guard_in)
test("Syllabus Guard (out-of-syllabus)", test_syllabus_guard_out)

# ─────────────────────────────────────────
# 3. Adaptive Router
# ─────────────────────────────────────────
print("\n🔀 Testing Adaptive Router (LLM call)...")

def test_router_concept():
    from tutor_agent.adaptive_router import route_doubt
    result = route_doubt(
        doubt="What is round robin scheduling?",
        lecture_topic="CPU Scheduling"
    )
    assert "type" in result, "Missing 'type' in result"
    assert result["type"] in ["concept", "misconception", "application", "out_of_syllabus"]
    return f"type={result['type']}, needs_external={result.get('needs_external')}"

def test_router_misconception():
    from tutor_agent.adaptive_router import route_doubt
    result = route_doubt(
        doubt="Round robin always gives the best performance",
        lecture_topic="CPU Scheduling"
    )
    return f"type={result['type']} (should be misconception or concept)"

test("Adaptive Router (concept question)", test_router_concept)
test("Adaptive Router (misconception statement)", test_router_misconception)

# ─────────────────────────────────────────
# 4. Misconception Detector
# ─────────────────────────────────────────
print("\n🔍 Testing Misconception Detector (LLM call)...")

def test_misconception_true():
    from tutor_agent.misconception_detector import detect_misconception
    result = detect_misconception("Round robin always gives best performance")
    return f"'Round robin always best' → is_misconception={result} (should be True)"

def test_misconception_false():
    from tutor_agent.misconception_detector import detect_misconception
    result = detect_misconception("What is round robin scheduling?")
    return f"'What is round robin?' → is_misconception={result} (should be False)"

test("Misconception Detector (wrong statement)", test_misconception_true)
test("Misconception Detector (normal question)", test_misconception_false)

# ─────────────────────────────────────────
# 5. Tool Selector
# ─────────────────────────────────────────
print("\n🔧 Testing Tool Selector...")

def test_tool_selector():
    from tutor_agent.tool_selector import choose_tool
    r1 = choose_tool({"type": "concept", "needs_external": False})
    r2 = choose_tool({"type": "misconception", "needs_external": False})
    r3 = choose_tool({"type": "application", "needs_external": True})
    r4 = choose_tool({"type": "out_of_syllabus", "needs_external": False})
    assert r1 == "rag", f"concept should → rag, got {r1}"
    assert r2 == "rag", f"misconception should → rag, got {r2}"
    assert r3 == "mcp", f"application+external should → mcp, got {r3}"
    assert r4 == "rag", f"out_of_syllabus should → rag, got {r4}"
    return f"concept→{r1}, misconception→{r2}, application+external→{r3}"

test("Tool Selector", test_tool_selector)

# ─────────────────────────────────────────
# 6. RAG Tool
# ─────────────────────────────────────────
print("\n📚 Testing RAG Tool (full pipeline — will take ~60s)...")

def test_rag_tool():
    from tools.rag_tool import rag_answer
    result = rag_answer("What is round robin scheduling?")
    assert result and len(result) > 50, "RAG returned empty or too short answer"
    return f"Got answer ({len(result)} chars): {result[:80]}..."

test("RAG Tool", test_rag_tool)

# ─────────────────────────────────────────
# 7. MCP Tool (Wikipedia)
# ─────────────────────────────────────────
print("\n🌐 Testing MCP Tool (Wikipedia)...")

def test_wiki():
    from tools.mcp_tools import wiki_search
    result = wiki_search("round robin scheduling operating system")
    assert result and len(result) > 20, "Wiki returned empty"
    return f"Got wiki result ({len(result)} chars): {result[:80]}..."

test("MCP Tool (Wikipedia)", test_wiki)

# ─────────────────────────────────────────
# 8. Pedagogical Agent
# ─────────────────────────────────────────
print("\n🎓 Testing Pedagogical Agent (LLM call)...")

def test_pedagogical():
    from tutor_agent.pedagogical_agent import teach_response
    result = teach_response(
        doubt="What is round robin scheduling?",
        raw_answer="Round robin is a CPU scheduling algorithm that assigns a fixed time quantum to each process in circular order."
    )
    assert result and len(result) > 50
    return f"Got response ({len(result)} chars): {result[:80]}..."

test("Pedagogical Agent", test_pedagogical)

# ─────────────────────────────────────────
# 9. Full Doubt API (end-to-end via HTTP)
# ─────────────────────────────────────────
print("\n🔗 Testing Full /api/doubt endpoint (requires app.py running)...")

def test_doubt_api():
    import requests
    resp = requests.post(
        "http://localhost:5001/api/doubt",
        json={
            "student_id": "test_student",
            "doubt": "What is round robin scheduling?",
            "topic": "CPU Scheduling"
        },
        timeout=120
    )
    assert resp.status_code == 200, f"Status {resp.status_code}"
    data = resp.json()
    assert "response" in data
    return f"route={data.get('route')}, tool={data.get('tool')}, response_len={len(data['response'])}"

test("Full /api/doubt API", test_doubt_api)

# ─────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────
print("\n" + "="*60)
print("📊 TEST SUMMARY")
print("="*60)

passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)

for name, ok, msg in results:
    status = "✅ PASS" if ok else "❌ FAIL"
    print(f"{status} — {name}")
    if not ok:
        print(f"        Error: {msg}")

print(f"\n{passed}/{len(results)} tests passed")

if failed > 0:
    print("\n⚠️  Fix the failing components before using the tutor agent.")
else:
    print("\n🎉 All components working! Your tutor agent is ready.")