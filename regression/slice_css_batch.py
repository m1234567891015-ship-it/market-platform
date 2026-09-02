"""Cut a contiguous, position-preserving slice of top-level blocks out of styles.css.

Unlike move_css_batch.py (selector-prefix based, can reorder rules relative to
their original position -> proven to break cascade ties in practice), this tool
NEVER reorders anything: it takes the first N not-yet-moved top-level blocks
(in original document order) and moves that exact contiguous run into a new
target file. Concatenating every css/*.css file in the same order they were
cut, followed by whatever remains in styles.css, reproduces the original
styles.css byte-for-byte. Cascade order is therefore unchanged by construction,
not by verification after the fact.

Usage:
    python regression/slice_css_batch.py <target_file> <block_count>

Always slices from the top (index 0) of the CURRENT styles.css, recomputed
fresh from disk each run.

IMPORTANT: <target_file> must be a root-level filename (e.g. "split-01.css"),
NOT a subdirectory path. CSS url() references are resolved relative to the
stylesheet's own URL, so a file served from a subdirectory (e.g. "css/foo.css")
would break any relative-path url() it contains (e.g. url("assets/x.jpg")
would then resolve to "css/assets/x.jpg" and 404). Keeping split files at
root, same level as styles.css, avoids this entirely without rewriting any
url() content (which would violate the byte-exact/no-editing requirement).
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
    if len(args) != 2:
        print("usage: slice_css_batch.py <target_file> <block_count>")
        sys.exit(1)
    target_file = args[0]
    block_count = int(args[1])
    if "/" in target_file or "\\" in target_file:
        print("ERROR: target_file must be a root-level filename, not a subdirectory path (see module docstring)")
        sys.exit(1)

    text = STYLES_PATH.read_text(encoding="utf-8", newline="")
    blocks = parse_blocks(text)
    if block_count > len(blocks):
        print(f"ERROR: requested {block_count} blocks but only {len(blocks)} remain")
        sys.exit(1)

    selected = blocks[:block_count]
    cut_end = selected[-1]["end"]
    moved_text = text[:cut_end]
    remaining_text = text[cut_end:]

    target_path = BASE_DIR / target_file
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(moved_text, encoding="utf-8", newline="")
    STYLES_PATH.write_text(remaining_text, encoding="utf-8", newline="")

    first_line = selected[0]["startLine"]
    last_line = selected[-1]["endLine"]
    print(f"moved blocks 0..{block_count - 1} (styles.css original lines {first_line}-{last_line}) to {target_file}")
    print(f"{target_file}: {len(moved_text)} chars")
    print(f"styles.css new length: {len(remaining_text)} chars, {remaining_text.count(chr(10)) + 1} lines")


if __name__ == "__main__":
    main()
