"""Move a set of top-level CSS rule blocks from styles.css into a target css/*.css file.

Blocks are identified by their 1-indexed starting line in the CURRENT styles.css
(recomputed fresh from disk on every run, never from a cached offset table, so this
is safe to run repeatedly across batches as the file shrinks).

Usage:
    python regression/move_css_batch.py <target_file> [--append] <startLine1> [startLine2 ...]

Mirrors regression/move_frontend_batch.py's safety properties for JS: extraction is
done via direct Python file I/O on exact byte ranges, never by retyping content, and
removal is applied in reverse (highest offset first) so earlier spans are unaffected.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STYLES_PATH = BASE_DIR / "styles.css"


def parse_blocks(text):
    n = len(text)
    i = 0
    blocks = []
    while i < n:
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            blocks.append({"kind": "comment", "start": i, "end": end})
            i = end
            continue
        if ch.isspace():
            i += 1
            continue
        header_start = i
        j = i
        brace_pos = -1
        while j < n:
            if text[j] == "{":
                brace_pos = j
                break
            if text[j] == "/" and j + 1 < n and text[j + 1] == "*":
                j = text.find("*/", j + 2)
                j = n if j == -1 else j + 2
                continue
            if text[j] == ";":
                brace_pos = None
                j += 1
                break
            j += 1
        if brace_pos is None:
            blocks.append({"kind": "atrule-simple", "start": header_start, "end": j})
            i = j
            continue
        if brace_pos == -1:
            blocks.append({"kind": "unknown-tail", "start": header_start, "end": n})
            i = n
            continue
        header = text[header_start:brace_pos]
        depth = 1
        k = brace_pos + 1
        while k < n and depth > 0:
            c = text[k]
            if c == "/" and k + 1 < n and text[k + 1] == "*":
                k = text.find("*/", k + 2)
                k = n if k == -1 else k + 2
                continue
            if c in ("'", '"'):
                quote = c
                k += 1
                while k < n and text[k] != quote:
                    if text[k] == "\\":
                        k += 1
                    k += 1
                k += 1
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            k += 1
        end = k
        kind = "atrule" if header.strip().startswith("@") else "rule"
        blocks.append({"kind": kind, "start": header_start, "end": end, "header": header.strip()})
        i = end
    for b in blocks:
        b["startLine"] = text.count("\n", 0, b["start"]) + 1
        b["endLine"] = text.count("\n", 0, b["end"] - 1) + 1
    return blocks


def main():
    args = sys.argv[1:]
    if not args:
        print("usage: move_css_batch.py <target_file> [--append] <startLine1> [startLine2 ...]")
        sys.exit(1)
    target_file = args[0]
    rest = args[1:]
    append = False
    if rest and rest[0] == "--append":
        append = True
        rest = rest[1:]
    start_lines = [int(x) for x in rest]
    if not start_lines:
        print("no startLine values given")
        sys.exit(1)

    text = STYLES_PATH.read_text(encoding="utf-8", newline="")
    blocks = parse_blocks(text)
    by_line = {b["startLine"]: b for b in blocks if b["kind"] in ("rule", "atrule")}

    selected = []
    missing = []
    for sl in start_lines:
        b = by_line.get(sl)
        if b is None:
            missing.append(sl)
        else:
            selected.append(b)
    if missing:
        print("ERROR: no rule/atrule block starts at line(s):", missing)
        sys.exit(1)

    # preserve original document order in the target file
    selected_sorted = sorted(selected, key=lambda b: b["start"])
    moved_text = "\n\n".join(text[b["start"]:b["end"]] for b in selected_sorted) + "\n"

    target_path = BASE_DIR / target_file
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if append and target_path.exists():
        existing = target_path.read_text(encoding="utf-8", newline="")
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + moved_text
    else:
        new_content = moved_text
    target_path.write_text(new_content, encoding="utf-8", newline="")

    # remove selected spans from styles.css, reverse order so earlier offsets stay valid
    remove_spans = sorted(((b["start"], b["end"]) for b in selected_sorted), reverse=True)
    new_styles = text
    for start, end in remove_spans:
        new_styles = new_styles[:start] + new_styles[end:]
    STYLES_PATH.write_text(new_styles, encoding="utf-8", newline="")

    print(f"moved {len(selected_sorted)} blocks to {target_file}")
    print(f"styles.css new length: {len(new_styles)} chars, {new_styles.count(chr(10)) + 1} lines")


if __name__ == "__main__":
    main()
