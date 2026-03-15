# rag_pipeline.py

from embedding import debug_query
from chunk_subsets import round_robin_from_results
from drafter import run_phi3_draft
from verifier import verify_drafts


def run_rag_pipeline(question):

    # Step 1: Retrieve relevant chunks
    results = debug_query(question, k=9)

    if not results["documents"][0]:
        return {
            "final_answer": "No relevant information found in the notes.",
            "verification_rationale": "No chunks retrieved.",
            "used_draft_indices": []
        }

    # Step 2: Create chunk groups
    groups = round_robin_from_results(results, num_groups=3)

    chunk_lookup = {}
    for group in groups:
        for ch in group:
            chunk_lookup[ch["chunk_id"]] = {
                "content": ch["content"],
                "topic": ch["metadata"].get("topic", ""),
                "page_hint": ch["metadata"].get("page_hint", "")
            }

    # Step 3: Generate drafts
    drafts = []

    for group in groups:

        context_chunks = [
            {
                "id": ch["metadata"]["id"],
                "content": ch["content"],
                "topic": ch["metadata"].get("topic", ""),
                "page_hint": ch["metadata"].get("page_hint", "")
            }
            for ch in group
        ]

        draft = run_phi3_draft(question, context_chunks)
        drafts.append(draft)

    # Step 4: Verify drafts
    answer = verify_drafts(question, drafts, chunk_lookup)

    return answer