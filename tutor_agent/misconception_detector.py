# tutor_agent/misconception_detector.py
import ollama

def detect_misconception(doubt: str) -> bool:

    prompt = f"""You are an expert computer science professor.

A student made this statement:
"{doubt}"

Does this statement contain a factual error, oversimplification, or misconception about computer science or operating systems?

Examples of misconceptions:
- "Round robin always gives best performance" → YES (wrong, depends on quantum size)
- "FIFO is always fair" → YES (wrong, can cause convoy effect)
- "More RAM always makes a computer faster" → YES (oversimplification)

Examples of normal questions (not misconceptions):
- "What is round robin scheduling?" → NO
- "How does paging work?" → NO
- "Why do we need an OS?" → NO

Answer with only YES or NO."""

    resp = ollama.chat(
        model="qwen2.5:7b",
        messages=[{"role": "user", "content": prompt}]
    )

    text = resp["message"]["content"].strip().upper()
    return text.startswith("YES")