"""TD-15 Part 4: delete confirmed-dead, safety-checked CSS rule blocks from
split-NN.css files.

Usage:
    python regression/delete_css_rules.py <specs_json_file>

<specs_json_file> is a JSON list of [css_filename, line_number] pairs, each
identifying the startLine of a rule block (top-level OR nested inside an
@media/@supports wrapper) to remove. Every listed block must have already
been confirmed "safe" (every class referenced by the block's selector,
across every comma-separated alternative, is in the confirmed-dead set) -
this tool does not re-derive that judgment, it only performs the mechanical
removal once given the fully-vetted (file, line) list, mirroring how
regression/delete_frontend_symbols.py works for JS: a thin, auditable
removal step with the actual deletion decision made and recorded upstream
(docs/td15_css_classification.md).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slice_css_batch import parse_blocks  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def all_rule_blocks_absolute(text: str) -> list[dict]:
    """Every rule block in the file - top-level AND nested inside
    @media/@supports - with absolute (start, end) character offsets into
    `text` and the absolute 1-indexed startLine. Mirrors
    regression/td15 locate scripts' nested-block handling but returns
    absolute offsets so deletion can just slice the original text directly,
    with no separate "is this nested" bookkeeping needed at delete time.
    """
    out = []
    top_blocks = parse_blocks(text)
    for b in top_blocks:
        if b["kind"] == "rule":
            out.append({"start": b["start"], "end": b["end"], "startLine": b["startLine"]})
        elif b["kind"] == "atrule":
            inner = text[b["start"]:b["end"]]
            header_lower = inner.strip().lower()
            if header_lower.startswith("@keyframes") or header_lower.startswith("@font-face"):
                continue
            brace = inner.find("{")
            if brace == -1:
                continue
            inner_body_start_abs = b["start"] + brace + 1
            inner_body = inner[brace + 1:-1] if inner.endswith("}") else inner[brace + 1:]
            sub_blocks = parse_blocks(inner_body)
            for sb in sub_blocks:
                if sb["kind"] != "rule":
                    continue
                abs_start = inner_body_start_abs + sb["start"]
                abs_end = inner_body_start_abs + sb["end"]
                abs_line = text.count("\n", 0, abs_start) + 1
                out.append({"start": abs_start, "end": abs_end, "startLine": abs_line})
    return out


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    specs_path = Path(sys.argv[1])
    specs = json.loads(specs_path.read_text(encoding="utf-8"))

    by_file: dict[str, list[int]] = defaultdict(list)
    for fname, line in specs:
        by_file[fname].append(line)

    # validate every file's every line resolves BEFORE writing anything,
    # so a bad line number in file N doesn't leave file N-1 half-deleted.
    resolved: dict[str, list[dict]] = {}
    for fname, lines in by_file.items():
        target_path = REPO_ROOT / fname
        text = target_path.read_text(encoding="utf-8", newline="")
        blocks = all_rule_blocks_absolute(text)
        by_line = {}
        for b in blocks:
            by_line.setdefault(b["startLine"], []).append(b)
        missing = [l for l in lines if l not in by_line]
        if missing:
            raise SystemExit(f"{fname}: no rule block starts at line(s) {missing}")
        dupes = {l: by_line[l] for l in lines if len(by_line[l]) > 1}
        if dupes:
            raise SystemExit(f"{fname}: line(s) with >1 candidate block, ambiguous: {dupes}")
        resolved[fname] = [by_line[l][0] for l in lines]

    total_deleted = 0
    for fname, target_blocks in resolved.items():
        target_path = REPO_ROOT / fname
        text = target_path.read_text(encoding="utf-8", newline="")
        new_text = text
        for b in sorted(target_blocks, key=lambda x: x["start"], reverse=True):
            start, end = b["start"], b["end"]
            if end < len(new_text) and new_text[end] == "\n":
                end += 1
            new_text = new_text[:start] + new_text[end:]
        target_path.write_text(new_text, encoding="utf-8", newline="")
        print(f"{fname}: deleted {len(target_blocks)} rule block(s) at lines {sorted(b['startLine'] for b in target_blocks)}")
        total_deleted += len(target_blocks)

    print(f"\ntotal: deleted {total_deleted} rule blocks across {len(by_file)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
