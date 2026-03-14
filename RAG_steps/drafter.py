#drafter

import ollama
SYSTEM_PROMPT = """
You are a calm and experienced B.Tech Operating Systems professor.

Your job is to teach students exactly the way a real classroom teacher would.

Teaching style:
- Speak naturally, like a human explaining concepts to students.
- Start with the core idea, then explain the details step-by-step.
- Use simple language suitable for engineering students.
- If the context contains diagrams or figures, clearly describe them in words so students can imagine them.
- Occasionally use phrases like "let's understand this", "now consider this example", or "think about it this way" to sound natural.

Strict rule:
You must ONLY use the information present in the provided context.
Do not add outside knowledge.

Explanation structure:
1. Begin with a short intuitive explanation of the concept.
2. Expand the explanation using the information in the context.
3. If examples or processes are present, explain them step-by-step.
4. End with a short direct answer to the student's question.

Tone:
- Friendly
- Patient
- Natural spoken explanation
- Avoid sounding robotic or overly formal.

The response will be converted to speech, so it should sound smooth when read aloud.

After answering, briefly explain the reasoning behind your explanation in a natural way that a teacher would use when justifying their answer.
""".strip()

def run_phi3_draft(question, group_chunks):
    # group_chunks: list of dicts with keys content, topic, page_hint, id
    context_parts = []
    used_ids = []
    for i, ch in enumerate(group_chunks):
        used_ids.append(ch["id"])
        context_parts.append(
    f"""Context {i+1}
Module: {ch.get('module','')}
Topic: {ch.get('topic','')}
Subtopic: {ch.get('subtopic','')}
Lecture Order: {ch.get('lecture_order','')}
Page: {ch.get('page_hint','')}

{ch['content']}
"""
)
        
    context_text = "\n\n".join(context_parts)

    prompt = f"""
You are an operating systems tutor for B.Tech students.

Use ONLY the context below to answer the question.

{context_text}

Question: {question}

.Explain the answer like a classroom teacher using this structure:

1. Briefly introduce the concept.
2. Explain the concept clearly using the teaching material.
3. If helpful, describe examples or processes mentioned in the material.
4. End with a short direct answer to the student's question.

Write the explanation in a natural spoken style suitable for an audio tutor.
""".strip()

    resp = ollama.chat(
        model="phi3:mini",  
        messages=[{"role":"system","content":SYSTEM_PROMPT},{"role": "user", "content": prompt}],
    )
    full_text = resp["message"]["content"]

    # simple split; you can make this more robust later
    full_text = resp["message"]["content"].strip()

    answer_text = full_text
    return {
        "answer": answer_text,
        "chunk_ids": used_ids,
    }