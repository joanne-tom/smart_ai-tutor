# rag_pipeline.py
from embedding import debug_query
from chunk_subsets import round_robin_from_results
from drafter import run_phi3_draft
from verifier import verify_drafts


question='Explain page replacement algorithms.'
# module=1
results = debug_query(question, k=9)
print(f"\n=== Query: {question!r} ===")
for i, (doc, meta, dist) in enumerate(zip(
    results["documents"][0],
    results["metadatas"][0],
    results["distances"][0],
    )):
    print(f"\nResult {i+1} (distance {dist:.4f}):")
    print(f"  module={meta['module']}, topic={meta.get('topic')}, "
              f"page={meta.get('page_hint')}, src={meta.get('source_file')}")
    preview = doc[:400].replace("\n", " ")
    print(f"  {preview}{'...' if len(doc) > 400 else ''}")


groups = round_robin_from_results(results, num_groups=3)
chunk_lookup = {}
for group in groups:
    for ch in group:
        chunk_lookup[ch["chunk_id"]] = {
            "content": ch["content"],
            "topic": ch["metadata"].get("topic", ""),
            "page_hint": ch["metadata"].get("page_hint", "")
        }
for i, group in enumerate(groups, start=1):
    print(f"\nGroup {i} chunks:")
    for ch in group:
        print(
            f" - {ch['chunk_id']} | "
            f"{ch['metadata']['topic']} | "
            f"{ch['metadata']['page_hint']} | "
            f"{ch['distance']:.4f}"
        )


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
    draft = run_phi3_draft(question,context_chunks)
    drafts.append(draft)


for i, d in enumerate(drafts):
    print(f"\nDraft {i+1} Answer:\n{d['answer']}")

answer=verify_drafts(question, drafts,chunk_lookup)
print(f"\nFinal Verified Answer:\n{answer['final_answer']}\nRationale:\n{answer['verification_rationale']}\nUsed Drafts: {answer['used_draft_indices']}")