# def round_robin_from_results(results, num_groups=3):

#     documents = results["documents"][0]
#     metadatas = results["metadatas"][0]
#     distances = results["distances"][0]

#     chunks = []
#     for doc, meta, dist in zip(documents, metadatas, distances):
#         chunks.append({
#             "chunk_id": meta.get("id"),
#             "content": doc,
#             "metadata": meta,
#             "distance": dist,
#         })

#     # Round-robin grouping
#     groups = [[] for _ in range(num_groups)]
#     for idx, chunk in enumerate(chunks):
#         groups[idx % num_groups].append(chunk)

#     return groups

# chunk_subsets.py

def round_robin_from_results(results, num_groups=3, distance_threshold=0.7):
    """
    Groups retrieved chunks for speculative RAG drafting.
    
    - Filters out low-relevance chunks by distance threshold
    - Locks each group to the dominant topic
    - Ensures every group gets the top chunk (anchor)
    """

    documents  = results["documents"][0]
    metadatas  = results["metadatas"][0]
    distances  = results["distances"][0]

    # ✅ Step 1: Filter out low-relevance chunks
    chunks = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        if dist > distance_threshold:
            print(f"⚠️ Skipping low-relevance chunk (distance={dist:.2f}): {meta.get('topic','?')}")
            continue
        chunks.append({
            "chunk_id": meta.get("id"),
            "content":  doc,
            "metadata": meta,
            "distance": dist,
        })

    if not chunks:
        print("❌ No chunks passed the distance threshold!")
        return [[] for _ in range(num_groups)]

    # ✅ Step 2: Find dominant topic from top 3 chunks
    top_topics = [c["metadata"].get("topic", "") for c in chunks[:3]]
    dominant_topic = max(set(top_topics), key=top_topics.count)
    print(f"🎯 Dominant topic locked: {dominant_topic}")

    # ✅ Step 3: Separate on-topic vs off-topic chunks
    on_topic  = [c for c in chunks if c["metadata"].get("topic", "") == dominant_topic]
    off_topic = [c for c in chunks if c["metadata"].get("topic", "") != dominant_topic]

    if off_topic:
        print(f"🚫 Excluded {len(off_topic)} off-topic chunks: "
              f"{set(c['metadata'].get('topic','?') for c in off_topic)}")

    # ✅ Step 4: Use only on-topic chunks for grouping
    # Fallback: if filtering left too few, use all chunks
    pool = on_topic if len(on_topic) >= num_groups else chunks

    # ✅ Step 5: Round-robin distribute on-topic chunks
    groups = [[] for _ in range(num_groups)]
    for idx, chunk in enumerate(pool):
        groups[idx % num_groups].append(chunk)

    # ✅ Step 6: Ensure every group has the top (most relevant) chunk
    top_chunk = pool[0]
    for g in groups:
        if top_chunk not in g:
            g.insert(0, top_chunk)

    # ✅ Step 7: Remove empty groups
    groups = [g for g in groups if g]

    return groups

# chunk_subsets.py — add this helper
def prepare_for_drafter(group: list[dict]) -> list[dict]:
    """Flatten metadata for drafter consumption."""
    prepared = []
    for c in group:
        meta = c.get("metadata", {})
        prepared.append({
            "id":            c.get("chunk_id") or meta.get("id", ""),
            "content":       c.get("content", ""),
            "topic":         meta.get("topic", ""),
            "subtopic":      meta.get("subtopic", ""),
            "module":        meta.get("module", ""),
            "lecture_order": meta.get("lecture_order", ""),
            "page_hint":     meta.get("page_hint", ""),
        })
    return prepared