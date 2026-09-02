"""工單 TD-02 每批強制步驟:逐位元組比對每個被搬移符號在搬移前(app.js 的
Git 歷史版本)與搬移後(js/*.js 現版)的原始文字是否完全相同。

單靠語法檢查/符號集合比對(名稱有沒有出現)抓不到 regex 常值、樣板字面值、
跳脫序列邊界被寫壞的情況——這正是批次 2 實際踩到的問題(normalizeSafeUrl
的控制字元 regex 被悄悄改寫成實體位元組)。只有逐位元組比對原始文字才擋得住。

用法:
    python regression/verify_frontend_split_bytes.py <old_git_ref> <new_file> <symbol1> [symbol2 ...]

例如批次 3(js/api.js,4 個符號,搬移前是 HEAD~1 的 app.js):
    python regression/verify_frontend_split_bytes.py HEAD~1 js/api.js \\
        buildTwseInstitutionTradeUrl fetchClientInstitutionalTradeForDate \\
        fetchClientInstitutionalTradeHistory fetchWithTimeout
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from security_guardrail_check import TOP_LEVEL_FUNCTION_RE, TOP_LEVEL_VAR_RE, find_matching_close, strip_js_noise  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


def extract_symbol_span(source: str, name: str) -> str | None:
    """回傳原始(未處理)原始碼中,某個頂層符號的完整文字(含結尾分號/換行,
    不含前導空白),找不到或不唯一回傳 None。用 strip_js_noise 過的版本定位
    邊界,再切回原始文字(這樣切出來的文字就是逐位元組比對要用的「事實」)。
    """
    stripped = strip_js_noise(source)

    fn_pattern = re.compile(r"^(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", re.MULTILINE)
    fn_matches = list(fn_pattern.finditer(stripped))
    if len(fn_matches) == 1:
        m = fn_matches[0]
        paren_open = m.end() - 1
        paren_close = find_matching_close(stripped, paren_open)
        brace_open = stripped.find("{", paren_close)
        brace_close = find_matching_close(stripped, brace_open)
        return source[m.start() : brace_close + 1]
    if len(fn_matches) > 1:
        return None

    var_pattern = re.compile(r"^(?:let|const|var)\s+" + re.escape(name) + r"\b", re.MULTILINE)
    var_matches = list(var_pattern.finditer(stripped))
    if len(var_matches) != 1:
        return None
    m = var_matches[0]
    # 用挖空版找這個宣告陳述式的結尾分號(跳過字串/樣板字面值/括號內容)。
    i = m.start()
    depth = 0
    n = len(stripped)
    while i < n:
        ch = stripped[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ";" and depth == 0:
            return source[m.start() : i + 1]
        i += 1
    return None


def git_show(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return result.stdout


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    old_ref, new_file, *symbol_names = sys.argv[1:]

    old_app_js = git_show(old_ref, "app.js")
    new_source = (REPO_ROOT / new_file).read_text(encoding="utf-8")

    failures = []
    for name in symbol_names:
        old_span = extract_symbol_span(old_app_js, name)
        new_span = extract_symbol_span(new_source, name)
        if old_span is None:
            failures.append(f"{name}: 在 {old_ref}:app.js 找不到唯一符合的符號範圍")
            continue
        if new_span is None:
            failures.append(f"{name}: 在 {new_file} 找不到唯一符合的符號範圍")
            continue
        if old_span != new_span:
            # 找出第一個不同的位置,方便定位
            min_len = min(len(old_span), len(new_span))
            diff_at = next((i for i in range(min_len) if old_span[i] != new_span[i]), min_len)
            failures.append(
                f"{name}: 位元組不相同,第一個差異在偏移 {diff_at}\n"
                f"  舊: {old_span[max(0,diff_at-30):diff_at+30]!r}\n"
                f"  新: {new_span[max(0,diff_at-30):diff_at+30]!r}"
            )
        else:
            print(f"[OK] {name}: {len(old_span)} bytes identical")

    if failures:
        print("\n=== BYTE COMPARISON FAILURES ===")
        for f in failures:
            print(f"[FAIL] {f}")
        return 1
    print(f"\nBYTE_COMPARISON_OK: {len(symbol_names)} symbols verified identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
