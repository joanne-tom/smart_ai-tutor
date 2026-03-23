import json
import os

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "context_store.json")


def _load() -> dict:
    """Load the full memory store from disk."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(store: dict) -> None:
    """Persist the full memory store to disk."""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[ContextMemory] Failed to save: {e}")


def get_context(student_id: str) -> list:
    """Return the last (up to 5) doubts for this student."""
    store = _load()
    return store.get(str(student_id), [])


def store_doubt(student_id: str, doubt: str) -> None:
    """Append a doubt to the student's history and persist immediately."""
    store = _load()
    key = str(student_id)
    if key not in store:
        store[key] = []
    store[key].append(doubt)
    store[key] = store[key][-5:]   # keep only last 5
    _save(store)