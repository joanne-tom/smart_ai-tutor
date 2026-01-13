from langchain_text_splitters import RecursiveCharacterTextSplitter
import pathlib
import json
import re


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_heading(line: str) -> bool:
    line = line.strip()

    if not line:
        return False
    if line.startswith(("•", "-", "–", "")):
        return False
    if line.startswith("--- Page"):
        return False
    if len(line) > 60:
        return False

    words = line.split()
    if len(words) > 6:
        return False

    # reject sentence-like fragments
    forbidden = {"is", "are", "was", "were", "be", "being", "been"}
    if any(w.lower() in forbidden for w in words):
        return False

    # reject punctuation-only / syllabus junk headings
    if re.fullmatch(r"[A-Z()–\-., ]+", line) and len(words) <= 2:
        return False

    # allow ALL CAPS headings
    if line.isupper():
        return True

    # require mostly Title Case
    title_case_ratio = sum(
        w[0].isupper() for w in words if w[0].isalpha()
    ) / len(words)

    return title_case_ratio >= 0.6



def split_by_detected_topics(text: str):
    sections = []
    current_topic = "General"
    buffer = []

    for line in text.split("\n"):
        if line.startswith("--- Page"):
            buffer.append(line)
            continue

        if is_heading(line):
            if buffer:
                section_text = "\n".join(buffer).strip()
                # FIX: skip ultra-short junk sections
                if len(section_text.split()) >= 30:
                    sections.append((current_topic, section_text))
                buffer = []
            current_topic = line.strip()
        else:
            buffer.append(line)

    if buffer:
        section_text = "\n".join(buffer).strip()
        if len(section_text.split()) >= 30:
            sections.append((current_topic, section_text))

    return sections


# -----------------------------------
# Page Hint Extraction
# -----------------------------------
def extract_page_hint(text: str):
    pages = re.findall(r"--- Page (\d+) ---", text)
    if not pages:
        return None
    if len(pages) == 1:
        return f"Page {pages[0]}"
    return f"Page {pages[0]}–{pages[-1]}"


# -----------------------------------
# Main Chunking Function
# -----------------------------------
def chunk_os_txt(txt_path: pathlib.Path, module_id: int):
    raw_text = txt_path.read_text(encoding="utf-8")
    text = clean_text(raw_text)

    topic_sections = split_by_detected_topics(text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
    )

    chunks = []
    chunk_index = 0

    for topic, section_text in topic_sections:
        docs = splitter.create_documents([section_text])

        for d in docs:
            content = d.page_content.strip()

            # skip tiny chunks
            if len(content) < 80:
                continue

            chunks.append({
                "id": f"{module_id}_{chunk_index}",
                "module": module_id,
                "topic": topic,
                "page_hint": extract_page_hint(content),
                "content": content,
                "source_file": txt_path.name,
            })
            chunk_index += 1

    out_path = txt_path.with_suffix(".chunks.json")
    out_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved {len(chunks)} clean topic-aware chunks to {out_path}")


# -----------------------------------
# Runner
# -----------------------------------
if __name__ == "__main__":
    base = pathlib.Path(
        r"C:\Users\Joanne\Documents\smart_ai_tutor\smartaivenv\output_folder\text"
    )

    module_files = [
        (1, base / "CST206 M1.txt"),
        (2, base / "CST206 M2.txt"),
        (3, base / "CST206 M3.txt"),
        (4, base / "CST206 M4.txt"),
        (5, base / "CST206 M5.txt"),
    ]

    for module_id, path in module_files:
        chunk_os_txt(path, module_id)