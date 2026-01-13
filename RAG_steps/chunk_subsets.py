def round_robin_from_results(results, num_groups=3):

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    chunks = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        chunks.append({
            "chunk_id": meta.get("id"),
            "content": doc,
            "metadata": meta,
            "distance": dist,
        })

    # Round-robin grouping
    groups = [[] for _ in range(num_groups)]
    for idx, chunk in enumerate(chunks):
        groups[idx % num_groups].append(chunk)

    return groups