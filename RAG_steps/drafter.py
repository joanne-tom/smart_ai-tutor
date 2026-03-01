import ollama

def run_phi3_draft(question, group_chunks):
    # group_chunks: list of dicts with keys content, topic, page_hint, id
    context_parts = []
    used_ids = []
    for i, ch in enumerate(group_chunks):
        used_ids.append(ch["id"])
        context_parts.append(
            f"Context {i+1} (id={ch['id']}, topic={ch['topic']}, page={ch.get('page_hint','')}):\n{ch['content']}\n"
        )
        k=ch.get('page_hint','')
    context_text = "\n\n".join(context_parts)

    prompt = f"""
You are an operating systems tutor for B.Tech students.

Use ONLY the context below to answer the question.

{context_text}

Question: {question}

Task:
1. Write a concise, exam-style answer (max 2 paragraphs).
2. Then write a short rationale explaining which context snippets (by id) you used and why.

Answer format:
[ANSWER]
...your answer...

[RATIONALE]
...your rationale, mentioning context ids...
""".strip()

    resp = ollama.chat(
        model="gemma3:27b-cloud",  
        messages=[{"role": "user", "content": prompt}],
    )
    full_text = resp["message"]["content"]

    # simple split; you can make this more robust later
    if "[RATIONALE]" in full_text:
        answer_text, rationale_text = full_text.split("[RATIONALE]", 1)
        answer_text = answer_text.replace("[ANSWER]", "").strip()
        rationale_text = rationale_text.strip()
    else:
        answer_text, rationale_text = full_text.strip(), ""

    return {
        "answer": answer_text,
        "rationale": rationale_text,
        "chunk_ids": used_ids,
    }    