# tutor_agent/adaptive_router.py
import ollama
import json
import re


def route_doubt(doubt: str, lecture_topic: str) -> dict:
    """
    Classifies a student doubt using LLM reasoning.

    Returns:
        dict with keys: type, reason, needs_external
        type is one of: concept, misconception, application, out_of_syllabus
    """

    prompt = f"""You are an AI tutor reasoning engine for Operating Systems.

Lecture topic: {lecture_topic}

Student doubt:
{doubt}

Classify the doubt into exactly ONE of these types:

- concept: student asking what something is or how it works
  Examples: "What is round robin?", "How does paging work?", "Explain semaphores"

- misconception: student stating something factually wrong or oversimplified
  Examples: "Round robin always gives best performance", "FIFO is always fair",
  "More RAM always makes a computer faster"

- application: real-world scenarios, design problems, complex multi-part questions,
  "which algorithm should be used for X", "how would the OS prevent X",
  "what is the real-world use case for this", "give me a system architecture example",
  "give me an out of bound analogy or real-world application."
  Examples: "Which scheduling prevents a process from monopolizing CPU?",
  "How does OS ensure fair CPU allocation?",
  "What's a real world example of a system call in Windows?"

- out_of_syllabus: completely unrelated to operating systems or computer science
  Examples: "How do I make pasta?", "What is photosynthesis?"

Rules:
- If the doubt describes a real-world problem and asks for a solution or recommendation → application
- If the doubt asks about OS behavior in a scenario, an analogy, or a real-world architecture → application  
- If the doubt is a simple definition or explanation question within the text → concept
- If the doubt states something factually wrong → misconception
- `needs_external` MUST be `true` for application type so external tools can retrieve real-world data.

Return ONLY valid JSON with no extra text, no markdown, no explanation:
{{
  "type": "application",
  "reason": "brief one-line reason",
  "needs_external": true
}}"""

    try:
        resp = ollama.chat(
            model="qwen2.5:7b",
            messages=[{"role": "user", "content": prompt}]
        )

        text = resp["message"]["content"].strip()

        # ── Try 1: Direct JSON parse ──
        try:
            result = json.loads(text)
            return _validate_route(result)
        except json.JSONDecodeError:
            pass

        # ── Try 2: Extract JSON block from response ──
        match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                return _validate_route(result)
            except json.JSONDecodeError:
                pass

        # ── Try 3: Look for type keyword in response ──
        text_lower = text.lower()
        if "misconception" in text_lower:
            return {"type": "misconception", "reason": "detected from response", "needs_external": False}
        if "application" in text_lower:
            return {"type": "application", "reason": "detected from response", "needs_external": True}
        if "out_of_syllabus" in text_lower or "outside" in text_lower:
            return {"type": "out_of_syllabus", "reason": "detected from response", "needs_external": False}

    except Exception as e:
        print(f"Adaptive router error: {e}")

    # ── Fallback ──
    return {
        "type": "concept",
        "reason": "fallback — could not parse router response",
        "needs_external": False
    }


def _validate_route(result: dict) -> dict:
    """Ensures the route dict has all required fields with valid values."""
    valid_types = {"concept", "misconception", "application", "out_of_syllabus"}

    if "type" not in result or result["type"] not in valid_types:
        result["type"] = "concept"

    if "reason" not in result:
        result["reason"] = ""

    if "needs_external" not in result:
        # Auto-set needs_external based on type
        result["needs_external"] = result["type"] == "application"

    return result