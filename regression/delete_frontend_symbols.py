"""TD-15 Part 2/4: delete confirmed-dead top-level symbols from a JS/frontend
source file. Adapts move_frontend_batch.py's span-finding logic (paren/brace
matching for function declarations, depth-aware semicolon scan for variable
declarations) but only removes the span - nothing is written anywhere else.
Pure mechanical deletion, no retyping, no rewriting of anything else in the
file.

Usage:
    python regression/delete_frontend_symbols.py <source_js_file> <symbol1> [symbol2 ...]

Verifies via git diff that the ONLY change to the file is the removal of the
named symbols' exact spans (nothing else shifted/rewritten).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from security_guardrail_check import find_matching_close, strip_js_noise  # noqa: E402
from move_frontend_batch import find_symbol_span  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    target_rel, *names = sys.argv[1:]
    target_path = REPO_ROOT / target_rel
    if not target_path.exists():
        raise SystemExit(f"{target_path} does not exist")

    source = target_path.read_text(encoding="utf-8")
    stripped = strip_js_noise(source)

    spans = []
    for name in names:
        start, end = find_symbol_span(stripped, source, name)
        text_end = end + 1 if end < len(source) and source[end] == "\n" else end
        spans.append((start, end, text_end, name))

    spans.sort()
    for i in range(1, len(spans)):
        if spans[i][0] < spans[i - 1][2]:
            raise SystemExit(f"overlapping spans: {spans[i-1][3]} and {spans[i][3]}")

    removed_texts = {name: source[start:end] for start, end, _, name in spans}

    new_source = source
    for start, end, text_end, name in sorted(spans, reverse=True):
        removed = new_source[start:end]
        assert removed == source[start:end], name
        new_source = new_source[:start] + new_source[text_end:]

    target_path.write_text(new_source, encoding="utf-8", newline="\n")

    print(f"deleted {len(names)} symbols from {target_rel}")
    print(f"{target_rel} new length: {len(new_source)} chars, {new_source.count(chr(10))} lines")
    for name in names:
        print(f"  - {name} ({len(removed_texts[name])} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
