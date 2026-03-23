import wikipedia
import requests
import re


# ─────────────────────────────────────────
# Wikipedia search (real-world / application questions)
# ─────────────────────────────────────────
def wiki_search(query: str) -> str:
    try:
        summary = wikipedia.summary(query, sentences=3)
        return summary
    except Exception:
        return "No external information found."


# ─────────────────────────────────────────
# OS Documentation search
# Tries tldr-pages (concise Linux command docs), then
# falls back to man7.org HTML for system calls.
# ─────────────────────────────────────────
def os_docs_search(query: str) -> str:
    """
    Search Linux / OS documentation for the given query.
    Priority order:
      1. tldr-pages GitHub raw (clear, concise Linux command/syscall summaries)
      2. man7.org HTML (Linux man page for the term as a section-2 syscall)
      3. Wikipedia fallback with "linux operating system" context
    """
    slug = query.lower().strip().replace(" ", "-")
    word = query.lower().strip().split()[0]   # first keyword for man pages

    # ── 1. tldr-pages ──────────────────────────────────────────────────────
    for section in ("linux", "common"):
        try:
            url = (
                f"https://raw.githubusercontent.com/tldr-pages/tldr/main/"
                f"pages/{section}/{slug}.md"
            )
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200:
                lines = [
                    l.strip()
                    for l in resp.text.splitlines()
                    if l.strip() and not l.startswith("#")
                ]
                content = " ".join(lines[:6])
                return f"[tldr / Linux docs — {query}]: {content[:700]}"
        except Exception:
            pass

    # ── 2. man7.org system-call page ──────────────────────────────────────
    try:
        man_url = f"https://man7.org/linux/man-pages/man2/{word}.2.html"
        resp = requests.get(man_url, timeout=8)
        if resp.status_code == 200:
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s+", " ", text)
            # Extract the NAME section (sits between "NAME" and "SYNOPSIS")
            m = re.search(r"NAME\s+(.*?)SYNOPSIS", text, re.DOTALL)
            if m:
                snippet = m.group(1).strip()[:700]
                return f"[Linux man page — {word}(2)]: {snippet}"
    except Exception:
        pass

    # ── 3. Wikipedia fallback with OS context ─────────────────────────────
    try:
        result = wikipedia.summary(
            f"{query} linux operating system", sentences=3
        )
        return f"[OS reference — {query}]: {result}"
    except Exception:
        pass

    return f"No OS documentation found for '{query}'."