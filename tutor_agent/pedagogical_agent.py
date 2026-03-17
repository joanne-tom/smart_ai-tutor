import ollama

def teach_response(doubt, raw_answer):

    prompt = f"""
You are a university tutor.

Student doubt:
{doubt}

Information to explain:
{raw_answer}

Explain clearly:

1. Acknowledge the doubt
2. Give explanation
3. Provide a simple example
4. Encourage further thinking
"""

    resp = ollama.chat(
        model="qwen2.5:7b",
        messages=[{"role":"user","content":prompt}]
    )

    return resp["message"]["content"]