# embedding.py
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.utils import embedding_functions

BASE            = Path(__file__).parent.parent / "output_text"
COLLECTION_NAME = "cst206_all"
DB_PATH         = str(Path(__file__).parent.parent / "chroma_db")  # ✅ persistent folder

# ── Embedding model ──────────────────────────────────────────
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# ── Persistent ChromaDB client ────────────────────────────────
# ✅ Data survives server restarts — saved to ./chroma_db folder
client = chromadb.PersistentClient(path=DB_PATH)

# ✅ Get or create — never wipe on import
collection = client.get_or_create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_fn,
)

# ── Load any chunk files found on disk (startup only) ─────────
# This is a one-time seed for chunks already on disk
# New uploads go through app.py /api/upload route directly
CHUNK_FILES = sorted(BASE.glob("*.chunks.json"))

loaded_docs = 0
loaded_files = 0

for chunk_file in CHUNK_FILES:
    with chunk_file.open("r", encoding="utf-8") as f:
        chunks = json.load(f)

    # ✅ Only add chunks not already in collection (no duplicates)
    existing_ids = set(collection.get(ids=[str(c["id"]) for c in chunks])["ids"])

    new_docs, new_metas, new_ids = [], [], []
    for chunk in chunks:
        cid = str(chunk.get("id", ""))
        if cid in existing_ids:
            continue
        new_docs.append(chunk["content"])
        new_metas.append({
            "id":            cid,
            "module":        int(chunk.get("module", 0)),
            "topic":         str(chunk.get("topic", "")),
            "subtopic":      str(chunk.get("subtopic", "")),
            "lecture_order": int(chunk.get("lecture_order", 0)),
            "page_hint":     str(chunk.get("page_hint", "")),
            "source_file":   str(chunk.get("source_file", chunk_file.name)),
            "subject":       str(chunk.get("subject", "Operating Systems")),
        })
        new_ids.append(cid)

    if new_docs:
        collection.add(documents=new_docs, metadatas=new_metas, ids=new_ids)
        loaded_docs  += len(new_docs)
        loaded_files += 1

print(f"Loaded {loaded_docs} new chunks from {loaded_files} files.")
print(f"Total chunks in collection: {collection.count()}")


# ── Query function ────────────────────────────────────────────
def debug_query(question: str, k: int = 9, module: int | None = None):
    """
    Query the collection. Optionally filter by module.
    Automatically reduces k if collection is smaller.
    """
    total = collection.count()
    if total == 0:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    # ✅ Never request more results than chunks available
    safe_k = min(k, total)

    query_args = {
        "query_texts": [question],
        "n_results":   safe_k,
    }

    if module is not None:
        query_args["where"] = {"module": module}

    return collection.query(**query_args)