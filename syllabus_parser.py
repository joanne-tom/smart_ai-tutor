# syllabus_parser.py — KTU Syllabus Parser
#
# This PDF has a tricky table layout where module number cells appear
# in the MIDDLE of content, not cleanly at boundaries.
# Verified raw line map of sylla.pdf:
#
#  Lines 3-10  → Module 1 content (before "1 11" cell)
#  Line  11    → "1 11"  ← module cell mid-module-1
#  Lines 12-25 → Module 1 remaining (Threads, Scheduling, MFQ, Concurrency&Sync)
#  Line  26    → "2"     ← start of Module 2 section in PDF
#  Lines 27-37 → Module 2 content (case study + Concurrency/Deadlock + Memory)
#  Line  38    → "3 11"  ← start of Module 3
#  Lines 39-47 → Module 3 (Virtual memory continuation + I/O + Hard disk)
#  Line  48    → "4 10"  ← start of Module 4
#  Lines 49-56 → Module 4 (Files, File Organization)
#
# BUT: Lines 20-25 (Concurrency & Synchronization topics) appear BEFORE the "2"
# cell but belong to Module 2 per the actual KTU spec.
# This is a PDF rendering artifact — the cell spans rows.
#
# SOLUTION: parse all topics purely based on TOPIC COLON headers, then
# reassign to modules using the CORRECT module cell positions as dividers,
# where "lines before first cell = Module 1" and we DON'T carry topics
# across boundaries — instead topics go to the module where their header line is.

import pdfplumber, re, json

MODULE_CELL = re.compile(r"^([1-9])(\s+\d{1,2})?$")
TOPIC_COLON = re.compile(r"^([A-Z][A-Za-z0-9 /\-]{2,40}):\s*(.*)$")
CASE_STUDY  = re.compile(r"^Case study[:\s]+(.+)", re.IGNORECASE)

STOP_RE = re.compile(
    r"^(Course Assessment|Continuous Internal|Text Books?|Reference Books?|"
    r"Video Links?|Course Outcomes?|CO.PO|Note:\s*1:|In Part A|End Semester)",
    re.IGNORECASE)

SKIP_RE = re.compile(
    r"(Downloaded from|ktunotes|^Course Code|^CIE|^ESE|Teaching Hours|"
    r"Prerequisites|^Course Objectives|^SYLLABUS$|^Syllabus Description|"
    r"^No\.\s+Hours|^Module\s+Contact|https?://|^CO[1-9]\b|^PO[1-9]\b|"
    r"^K[1-6][\s\-]|^SEMESTER|^\(Common|^\(L:|^Credits\s+\d|"
    r"^Course Type|^Exam Hours)", re.IGNORECASE)


def _clean(s):
    s = re.sub(r"\s*\(Book\s*\d+[^)]*\)", "", s)
    s = re.sub(r"\s*\(Book\s*\d.*", "", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;:–-–()")
    return s


def _subtopics(text):
    out = []
    for p in re.split(r"[,;]\s*", text):
        p = _clean(p)
        if p and len(p) > 4 and re.search(r"[A-Za-z]{3,}", p):
            out.append(p)
    return out


def _is_junk(line):
    if re.match(r"^\d+\)?\s*$", line.strip()):
        return True
    return False


def parse_syllabus(pdf_path: str) -> dict:
    # ── 1. Extract lines
    raw = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=False)
            if text:
                for line in text.splitlines():
                    s = line.strip()
                    if s: raw.append(s)

    # ── 2. Trim to SYLLABUS section
    start = next((i for i, l in enumerate(raw) if l.upper() == "SYLLABUS"), 0) + 1
    stop  = next((i for i, l in enumerate(raw) if STOP_RE.search(l)), len(raw))
    lines = raw[start:stop]

    # ── 3. Find all module cell positions
    mod_positions = []   # [(line_index, module_num)]
    for i, line in enumerate(lines):
        m = MODULE_CELL.match(line.strip())
        if m:
            mod_positions.append((i, int(m.group(1))))

    # ── 4. Build module index map: for each line index, what module is it in?
    # Rules:
    #   - Lines 0 to first_cell_idx (exclusive) = Module first_num (before mid-cell)
    #   - Lines first_cell_idx+1 to second_cell_idx (exclusive) = Module first_num
    #     (the first cell appears mid-module, NOT at a boundary)
    #   - Lines second_cell_idx+1 to third_cell_idx = Module second_num
    #   - etc.
    # In other words: the FIRST module cell is treated as mid-content (merge pre+post)
    # All subsequent cells ARE true boundaries.

    line_to_mod = {}

    if not mod_positions:
        for i in range(len(lines)):
            line_to_mod[i] = 1
    else:
        first_idx, first_num = mod_positions[0]

        # Everything up to (and including) the range of first cell = first module
        end_first = mod_positions[1][0] if len(mod_positions) > 1 else len(lines)
        for i in range(end_first):
            line_to_mod[i] = first_num

        # All subsequent module cells mark true boundaries
        for k in range(1, len(mod_positions)):
            idx, num = mod_positions[k]
            end = mod_positions[k+1][0] if k+1 < len(mod_positions) else len(lines)
            for i in range(idx, end):
                line_to_mod[i] = num

    # ── 5. Single-pass: collect topic events with their module assignment
    # A topic is assigned to the module of its HEADER LINE.
    # Continuations go to the current topic regardless of module boundary crossings.
    # (We just merge continuation lines into the topic—don't split topics across modules)

    result = {}         # mod_name -> {topic_name -> [subtopics]}
    mod_order = []
    topic_order = {}    # mod_name -> [topic_names in order]

    cur_mod   = None
    cur_mod_name = None
    cur_topic = None

    def get_mod(line_idx):
        return line_to_mod.get(line_idx, 1)

    def ensure_mod(mod_name):
        if mod_name not in result:
            result[mod_name] = {}
            topic_order[mod_name] = []
            mod_order.append(mod_name)

    def ensure_topic(mod_name, topic_name):
        ensure_mod(mod_name)
        if topic_name not in result[mod_name]:
            result[mod_name][topic_name] = []
            topic_order[mod_name].append(topic_name)

    def add_sub(sub):
        if cur_mod_name and cur_topic:
            cs = _clean(sub)
            if cs and len(cs) > 4 and cs not in result[cur_mod_name][cur_topic]:
                result[cur_mod_name][cur_topic].append(cs)

    for i, line in enumerate(lines):
        if not line or SKIP_RE.search(line) or _is_junk(line): continue
        if MODULE_CELL.match(line.strip()): continue

        mod_num  = get_mod(i)
        mod_name = f"Module {mod_num}"

        cs = CASE_STUDY.match(line)
        if cs:
            ensure_topic(cur_mod_name or mod_name, cur_topic or "Introduction")
            add_sub("Case Study: " + cs.group(1))
            continue

        tc = TOPIC_COLON.match(line)
        if tc:
            cur_mod_name = mod_name
            cur_topic    = _clean(tc.group(1))
            ensure_topic(cur_mod_name, cur_topic)
            rest = tc.group(2).strip()
            if rest:
                for s in _subtopics(rest): add_sub(s)
            continue

        cleaned = _clean(line)
        if cleaned and len(cleaned) > 5:
            if cur_topic:
                add_sub(cleaned)
            else:
                cur_mod_name = mod_name
                cur_topic    = "Introduction"
                ensure_topic(cur_mod_name, cur_topic)
                for s in _subtopics(cleaned): add_sub(s)

    # Build final ordered structure
    structure = {}
    for mod_name in mod_order:
        structure[mod_name] = {
            t: result[mod_name][t]
            for t in topic_order[mod_name]
            if result[mod_name][t] is not None
        }

    return structure or {"Module 1": {"General": []}}


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "sylla.pdf"
    r = parse_syllabus(path)
    print(json.dumps(r, indent=2))
    print("\n--- SUMMARY ---")
    for mod, topics in r.items():
        print(f"  {mod}: {list(topics.keys())}")
