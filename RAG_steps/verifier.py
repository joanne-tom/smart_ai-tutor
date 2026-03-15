# verifier.py
import os
import requests
from dotenv import load_dotenv
load_dotenv()

PATRONUS_API_KEY = os.environ.get("PATRONUS_API_KEY")
PATRONUS_URL = "https://api.patronus.ai/v1/evaluate"

def verify_drafts(question: str, drafts: list[dict], chunk_lookup: dict):
    """
    Verifies multiple drafts using Patronus Lynx API.

    Args:
        question:     The lecture topic or student question
        drafts:       List of dicts, each with 'answer' and 'chunk_ids'
        chunk_lookup: dict mapping chunk_id -> {'content', 'topic', 'page_hint'}

    Returns:
        dict with 'final_answer', 'verification_rationale', 'used_draft_indices'
    """
    scored = []

    for idx, draft in enumerate(drafts, start=1):

        # ✅ FIX 1: task_context must be a LIST of strings, not one joined string
        context_list = []
        for cid in draft["chunk_ids"]:
            ch = chunk_lookup.get(cid, {})
            context_list.append(
                f"[{cid}] topic={ch.get('topic','')} page={ch.get('page_hint','')}:\n{ch.get('content','')}"
            )

        # ✅ FIX 2: Correct field names per Patronus API docs
        body = {
            "evaluators": [
                {
                    "evaluator": "lynx",
                    "criteria": "patronus:hallucination",
                    "explain_strategy": "always"   # ✅ get reasoning back
                }
            ],
            "task_input": question,                 # ✅ was evaluated_model_input
            "task_output": draft["answer"],         # ✅ was evaluated_model_output
            "task_context": context_list,           # ✅ was evaluated_model_retrieved_context (and was a string)
        }

        try:
            resp = requests.post(
                PATRONUS_URL,
                headers={
                    "X-API-KEY": PATRONUS_API_KEY,
                    "accept": "application/json",
                    "content-type": "application/json",
                },
                json=body,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

        except requests.exceptions.Timeout:
            print(f"Draft {idx}: Patronus API timed out, skipping")
            scored.append({"index": idx, "draft": draft, "score": 0, "reasoning": "timeout"})
            continue

        except requests.exceptions.HTTPError as e:
            print(f"Draft {idx}: HTTP error {e}")
            scored.append({"index": idx, "draft": draft, "score": 0, "reasoning": str(e)})
            continue

        # ✅ FIX 3: Correct response parsing
        results = data.get("results", [])
        if not results:
            score = 0
            reasoning = "No results returned"
        else:
            res = results[0]
            eval_result = res.get("evaluation_result", {})

            # Patronus returns pass/fail + a raw score (0.0 to 1.0)
            passed     = eval_result.get("pass", False)
            raw_score  = eval_result.get("score", 0.0) or 0.0
            reasoning  = eval_result.get("explanation", "")

            # Use raw score; if missing fall back to pass/fail
            score = raw_score if raw_score else (1.0 if passed else 0.0)

        print(f"Draft {idx} → score: {score:.2f} | reasoning: {reasoning[:80]}...")

        scored.append({
            "index": idx,
            "draft": draft,
            "score": score,
            "reasoning": reasoning,
        })

    if not scored:
        return {
            "final_answer": drafts[0]["answer"] if drafts else "",
            "verification_rationale": "All verifications failed",
            "used_draft_indices": [1],
        }

    # Pick the best draft (highest faithfulness score)
    best = max(scored, key=lambda x: x["score"])

    # ✅ Warn if even best draft is low quality
    if best["score"] < 0.5:
        print("⚠️ Warning: Best draft has low faithfulness score. Topic may not be in notes.")

    return {
        "final_answer": best["draft"]["answer"],
        "verification_rationale": best["reasoning"],
        "used_draft_indices": [best["index"]],
    }

# verifier.py — top section
# import hashlib
# import json
# import os
# import torch
# from minicheck.minicheck import MiniCheck

# # ✅ Detect GPU for info purposes
# device = 'cuda' if torch.cuda.is_available() else 'cpu'
# print(f"MiniCheck running on: {device.upper()}")

# # ✅ MiniCheck without device argument
# scorer = MiniCheck(
#     model_name='deberta-v3-large',
#     cache_dir='./ckpts'
# )

# # ✅ Move model to GPU manually after loading
# if device == 'cuda' and hasattr(scorer, 'model'):
#     try:
#         scorer.model.model = scorer.model.model.to('cuda')
#         print("✅ MiniCheck moved to GPU successfully")
#     except Exception as e:
#         print(f"⚠️ Could not move MiniCheck to GPU: {e}, staying on CPU")

# CACHE_FILE = "./verified_cache.json"

# def load_cache():
#     if os.path.exists(CACHE_FILE):
#         with open(CACHE_FILE, 'r') as f:
#             return json.load(f)
#     return {}

# def save_cache(cache):
#     with open(CACHE_FILE, 'w') as f:
#         json.dump(cache, f, indent=2)

# def make_cache_key(question: str, draft_answer: str) -> str:
#     raw = f"{question.strip().lower()}|{draft_answer.strip()}"
#     return hashlib.md5(raw.encode()).hexdigest()


# def verify_drafts(question: str, drafts: list[dict], chunk_lookup: dict):
#     cache = load_cache()
#     scored = []

#     for idx, draft in enumerate(drafts, start=1):

#         # ✅ Cache hit — skip verification entirely
#         cache_key = make_cache_key(question, draft["answer"])
#         if cache_key in cache:
#             print(f"Draft {idx} → ✅ cache hit | score: {cache[cache_key]['score']:.2f}")
#             scored.append({
#                 "index": idx,
#                 "draft": draft,
#                 "score": cache[cache_key]["score"],
#                 "reasoning": cache[cache_key]["reasoning"],
#             })
#             continue

#         # Build context from chunks
#         context_parts = []
#         for cid in draft["chunk_ids"]:
#             ch = chunk_lookup.get(cid, {})
#             context_parts.append(
#                 f"[{cid}] topic={ch.get('topic', '')} page={ch.get('page_hint', '')}:\n{ch.get('content', '')}"
#             )
#         context_text = "\n\n".join(context_parts)

#         # Split into sentences
#         sentences = [s.strip() for s in draft["answer"].split('.') if s.strip()]

#         if not sentences:
#             scored.append({"index": idx, "draft": draft, "score": 0.0, "reasoning": "Empty draft"})
#             continue

#         pred_labels, raw_probs, _, _ = scorer.score(
#             docs=[context_text] * len(sentences),
#             claims=sentences
#         )

#         reasoning_lines = []
#         for sentence, label, prob in zip(sentences, pred_labels, raw_probs):
#             status = "✅ supported" if label == 1 else "❌ hallucinated"
#             reasoning_lines.append(f"{status} ({prob:.2f}): {sentence[:80]}")

#         reasoning = "\n".join(reasoning_lines)
#         avg_score = sum(raw_probs) / len(raw_probs)

#         print(f"Draft {idx} → score: {avg_score:.2f} | device: {device.upper()}")

#         cache[cache_key] = {"score": avg_score, "reasoning": reasoning}
#         save_cache(cache)

#         scored.append({
#             "index": idx,
#             "draft": draft,
#             "score": avg_score,
#             "reasoning": reasoning,
#         })

#     if not scored:
#         return {
#             "final_answer": drafts[0]["answer"] if drafts else "",
#             "verification_rationale": "No drafts to verify",
#             "used_draft_indices": [1],
#         }

#     best = max(scored, key=lambda x: x["score"])

#     if best["score"] < 0.6:
#         print("⚠️ Warning: Best draft has low faithfulness. Topic may not be in notes.")

#     return {
#         "final_answer": best["draft"]["answer"],
#         "verification_rationale": best["reasoning"],
#         "used_draft_indices": [best["index"]],
#     }