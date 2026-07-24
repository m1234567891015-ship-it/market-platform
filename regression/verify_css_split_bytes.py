"""Byte-for-byte verify that CSS blocks moved out of styles.css landed unchanged.

Usage:
    python regression/verify_css_split_bytes.py <old_git_ref> <new_file> <startLine1> [startLine2 ...]

<startLine...> refers to line numbers in styles.css AS IT WAS at <old_git_ref>
(before the move). Extracts each block's exact bytes from the old ref's styles.css
and from the current target file, and diffs them.
"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from move_css_batch import parse_blocks  # noqa: E402


def git_show(ref, path):
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=BASE_DIR,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8")


def main():
    args = sys.argv[1:]
    if len(args) < 3:
        print("usage: verify_css_split_bytes.py <old_git_ref> <new_file> <startLine1> [startLine2 ...]")
        sys.exit(1)
    old_ref = args[0]
    new_file = args[1]
    start_lines = [int(x) for x in args[2:]]

    old_text = git_show(old_ref, "styles.css")
    old_blocks = parse_blocks(old_text)
    old_by_line = {b["startLine"]: b for b in old_blocks if b["kind"] in ("rule", "atrule")}

    new_text = (BASE_DIR / new_file).read_text(encoding="utf-8", newline="")

    ok = True
    for sl in start_lines:
        b = old_by_line.get(sl)
        if b is None:
            print(f"[FAIL] no block found at old styles.css line {sl}")
            ok = False
            continue
        expected = old_text[b["start"]:b["end"]]
        if expected not in new_text:
            print(f"[FAIL] block from old line {sl} ({len(expected)} bytes) not found byte-identical in {new_file}")
            print("  expected snippet:", repr(expected[:120]))
            ok = False
        else:
            print(f"[OK] line {sl}: {len(expected)} bytes identical")

    if ok:
        print(f"\nBYTE_COMPARISON_OK: {len(start_lines)} blocks verified identical")
    else:
        print("\nBYTE_COMPARISON_FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
