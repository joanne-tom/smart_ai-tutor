# tools/rag_tool.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'RAG_steps'))

from embedding import debug_query
from chunk_subsets import round_robin_from_results, prepare_for_drafter
from drafter import run_phi3_draft
from verifier import verify_drafts


def rag_answer(question: str) -> str:

    results = debug_query(question, k=9)

    if not results["documents"][0]:
        return "No relevant content found in notes."

    groups = round_robin_from_results(results, num_groups=2)

    drafts = []
    chunk_lookup = {}

    for group in groups:
        context_chunks = []
        for ch in group:
            cid = ch["chunk_id"]   # ✅ use chunk_id not metadata id

            # ✅ chunk_lookup must store a DICT not a string
            chunk_lookup[cid] = {
                "content":   ch["content"],
                "topic":     ch["metadata"].get("topic", ""),
                "page_hint": ch["metadata"].get("page_hint", "")
            }

            context_chunks.append({
                "id":        cid,
                "content":   ch["content"],
                "topic":     ch["metadata"].get("topic", ""),
                "page_hint": ch["metadata"].get("page_hint", "")
            })

        draft = run_phi3_draft(question, context_chunks)
        drafts.append(draft)

    answer = verify_drafts(question, drafts, chunk_lookup)
    return answer["final_answer"]