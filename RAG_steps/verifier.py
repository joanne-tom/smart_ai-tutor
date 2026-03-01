# verifier.py
import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()

PATRONUS_API_KEY = os.environ.get("PATRONUS_API_KEY")  # make sure this is set in your env
print("PATRONUS KEY:", PATRONUS_API_KEY)
PATRONUS_URL = "https://api.patronus.ai/v1/evaluate"  # confirm the latest from Patronus docs

def verify_drafts(question: str, drafts: list[dict], chunk_lookup: dict):
    """
    Verifies multiple drafts using Patronus API.

    Args:
        question: The question to answer.
        drafts: List of draft dicts, each containing:
            - 'answer': str
            - 'chunk_ids': list[str]
        chunk_lookup: dict mapping chunk_id -> {'content', 'topic', 'page_hint'}

    Returns:
        dict with:
            - 'final_answer': str, verified answer
            - 'verification_rationale': str
            - 'used_draft_indices': list[int], drafts selected by Patronus
    """
    scored = []

    for idx, draft in enumerate(drafts, start=1):
        # Build context from the chunks used in this draft
        context_parts = []
        for cid in draft["chunk_ids"]:
            ch = chunk_lookup.get(cid, {})
            context_parts.append(
                f"[{cid}] (topic={ch.get('topic','')}, page={ch.get('page_hint','')}):\n{ch.get('content','')}"
            )
        context_text = "\n\n".join(context_parts)

        # Patronus API request
        body = {
            "evaluators": [
                {"evaluator": "lynx", "criteria": "patronus:hallucination"}
            ],
            "evaluated_model_input": question,
            "evaluated_model_output": draft["answer"],
            "evaluated_model_retrieved_context": context_text,
        }

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

        # DEBUG: inspect response structure
        # print(json.dumps(data, indent=2))

        # Safely extract score / reasoning
        res = data.get("results", [{}])[0]
        # if Patronus uses pass/fail:
        if "pass_fail" in res:
            score = 1 if res.get("pass_fail") == "PASS" else 0
        else:
            score = res.get("score", 0)  # fallback to 0 if missing
        reasoning = res.get("reasoning", "")

        scored.append({
            "index": idx,
            "draft": draft,
            "score": score,
            "reasoning": reasoning,
        })

    # Pick the best draft (higher score = better)
    best = max(scored, key=lambda x: x["score"])

    return {
        "final_answer": best["draft"]["answer"],
        "verification_rationale": best["reasoning"],
        "used_draft_indices": [best["index"]],
    }
