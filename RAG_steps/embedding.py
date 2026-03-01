import json
from pathlib import Path

from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.utils import embedding_functions


##CHUNK_FILES = [
   #$$$ BASE / "CST206 M5.chunks.json",
#]
BASE = Path(__file__).parent.parent / "output_text"

CHUNK_FILES = []

COLLECTION_NAME = "cst206_all"


all_documents = []
all_metadatas = []
all_ids = []

for chunk_file in CHUNK_FILES:
    if not chunk_file.exists():
        print(f"Skipping missing file: {chunk_file}")
        continue

    with chunk_file.open("r", encoding="utf-8") as f:
        chunks = json.load(f)

    for chunk in chunks:
        all_documents.append(chunk["content"])
        all_metadatas.append({
    "id": str(chunk.get("id", "")),  
    "module": int(chunk.get("module", 0)), 
    "topic": str(chunk.get("topic", "")),
    "page_hint": str(chunk.get("page_hint", "")),
    "source_file": str(chunk.get("source_file", chunk_file.name)),
})
        all_ids.append(chunk["id"])

print(f"Loaded {len(all_documents)} chunks from {len(CHUNK_FILES)} files.")



model = SentenceTransformer("all-MiniLM-L6-v2")
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)


client = chromadb.Client()


existing = {c.name for c in client.list_collections()}
if COLLECTION_NAME in existing:
    client.delete_collection(name=COLLECTION_NAME)

collection = client.create_collection(
    name=COLLECTION_NAME,
    embedding_function=embedding_fn,
)
if all_documents:
 collection.add(
    documents=all_documents,
    metadatas=all_metadatas,
    ids=all_ids,
)

print(f"Added {len(all_documents)} chunks to collection '{COLLECTION_NAME}'.")


def debug_query(question: str, k: int = 9, module: int | None = None):
    """
    Query all modules by default.
    Optionally filter by module if provided.
    """

    query_args = {
        "query_texts": [question],
        "n_results": k,
    }

    if module is not None:
        query_args["where"] = {"module": module}

    return collection.query(**query_args)