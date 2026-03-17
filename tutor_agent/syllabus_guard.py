# tutor_agent/syllabus_guard.py
import json
import pathlib

SYLLABUS_JSON = pathlib.Path(__file__).parent.parent / "syllabus_structure.json"

def load_topics():
    if not SYLLABUS_JSON.exists():
        return []

    data = json.loads(SYLLABUS_JSON.read_text(encoding="utf-8"))
    topics = []

    for mod in data.values():
        for topic, subtopics in mod.items():
            topics.append(topic.lower())
            # ✅ also add individual words from topics
            for word in topic.lower().split():
                if len(word) > 3:  # skip short words like "and", "the"
                    topics.append(word)
            # ✅ add subtopics too
            if isinstance(subtopics, list):
                for sub in subtopics:
                    topics.append(sub.lower())
                    for word in sub.lower().split():
                        if len(word) > 3:
                            topics.append(word)

    return list(set(topics))  # deduplicate


def check_syllabus(doubt: str) -> bool:
    topics = load_topics()

    # ✅ If no syllabus loaded yet, allow everything
    if not topics:
        return True

    doubt_lower = doubt.lower()
    doubt_words = set(w for w in doubt_lower.split() if len(w) > 3)

    # ✅ Check if any topic keyword appears in the doubt
    for t in topics:
        if t in doubt_lower:
            return True

    # ✅ Check word overlap (at least 1 matching word)
    for word in doubt_words:
        if any(word in t or t in word for t in topics):
            return True

    return False