# drafter.py
import ollama

SYSTEM_PROMPT = """
You are a calm and experienced B.Tech Operating Systems professor.

Your job is to teach students exactly the way a real classroom teacher would — 
strictly based on the provided teaching material.

Teaching style:
- Speak naturally, like a human explaining concepts to students.
- Start with the core idea, then explain the details step-by-step.
- Use simple language suitable for engineering students.
- If the context contains diagrams or figures, clearly describe them in words.
- Use phrases like "let's understand this" or "now consider this" naturally.

STRICT RULES — you must follow these without exception:
1. Use ONLY information explicitly present in the provided context.
2. Do NOT add outside knowledge, facts, or figures not in the context.
3. Do NOT invent analogies, examples, or scenarios not mentioned in the context.
4. If the context does not contain enough information to answer, say:
   "This topic is not fully covered in the provided notes."
5. Stay strictly on the topic of the question — do not drift to related topics.
6. Make sure the lecture takes atleast 45 minutes-1 hour to deliver when spoken aloud.

Explanation structure:
1. Begin with a short intuitive explanation of the concept.
2. Expand using only the information in the context.
3. If examples or processes are in the context, explain them step-by-step.
4. End with a short direct answer to the student's question.

Tone:
- Friendly, patient, natural spoken explanation.
- Avoid robotic or overly formal language.
- The response will be converted to speech — write smoothly for audio.
""".strip()


def run_phi3_draft(question: str, group_chunks: list[dict]) -> dict:
    """
    Generate a single grounded draft answer from Qwen using the provided chunks.

    Args:
        question:     Student question or lecture topic
        group_chunks: List of chunk dicts with keys: content, topic, subtopic,
                      module, lecture_order, page_hint, id

    Returns:
        dict with 'answer' (str) and 'chunk_ids' (list[str])
    """

    context_parts = []
    used_ids = []

    for i, ch in enumerate(group_chunks):
        used_ids.append(ch["id"])
        context_parts.append(
            f"""Context {i+1}
Module: {ch.get('module', '')}
Topic: {ch.get('topic', '')}
Subtopic: {ch.get('subtopic', '')}
Lecture Order: {ch.get('lecture_order', '')}
Page: {ch.get('page_hint', '')}

{ch['content']}
"""
        )

    context_text = "\n\n".join(context_parts)

    # ✅ Extract topic from chunks to lock Qwen on-topic
    main_topic = group_chunks[0].get('topic', 'the topic') if group_chunks else 'the topic'

    prompt = f"""
The student has asked about: "{question}"
The topic is: {main_topic}

Use ONLY the context below to answer. Do not use any outside knowledge.
Do not invent examples or analogies that are not in the context.
If something is not in the context, do not include it.

{context_text}

Now explain "{main_topic}" to the student using this structure:
1. Briefly introduce the concept (1-2 sentences).
2. Explain clearly using only the teaching material above.
3. Describe any examples or processes mentioned in the material above.
4. End with a short direct answer to the question: "{question}"

Write in a natural spoken style suitable for an audio tutor.
Stay strictly on the topic of "{main_topic}". Do not drift to other topics.
""".strip()

    resp = ollama.chat(
        model="gemma3:4b",   # ✅ fixed casing
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
    )

    answer_text = resp["message"]["content"].strip()

    return {
        "answer": answer_text,
        "chunk_ids": used_ids,
    }