"""工單 TD-02:批次搬移工具——把指定的頂層符號從 app.js 原封不動搬到
js/<target> 檔案。全程只用 Python 直接操作位元組,絕不讓符號內容經過人工
轉寫或工具呼叫參數重新輸入,徹底避開跳脫序列/控制字元被悄悄解碼成實體
位元組的風險(批次 2 曾實際踩到)。

用法:
    python regression/move_frontend_batch.py <target_js_file> <symbol1> [symbol2 ...]

例如批次 3(js/api.js):
    python regression/move_frontend_batch.py js/api.js buildTwseInstitutionTradeUrl \\
        fetchClientInstitutionalTradeForDate fetchClientInstitutionalTradeHistory \\
        fetchWithTimeout

執行後會:
1. 依 app.js 內原始出現順序排列符號、依序寫入目標檔案(若目標檔案已存在,
   直接失敗——每個批次應該是新檔案,若要接續舊檔案得自己手動處理)。
2. 從 app.js 移除這些符號的原始文字。
3. 立即用逐位元組比對確認目標檔案內容與 app.js 移除前的原始文字完全相同。
4. 印出 app.js 新的總行數,供後續驗證使用。

不做:不修改任何 HTML、不更新 JS_MODULE_STATIC_FILES、不執行測試——這些仍
需要各自手動確認與執行,本工具只負責「搬移」這一個純機械步驟本身。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from security_guardrail_check import find_matching_close, strip_js_noise  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_JS_PATH = REPO_ROOT / "app.js"


def find_symbol_span(stripped: str, source: str, name: str) -> tuple[int, int]:
    """回傳 (start, end) —— name 這個頂層符號在 source 裡的完整範圍(含結尾
    分號或右大括號,不含前後空白/換行)。找不到或不唯一就丟例外,不要用
    猜的。"""
    fn_pattern = re.compile(r"^(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", re.MULTILINE)
    fn_matches = list(fn_pattern.finditer(stripped))
    if len(fn_matches) == 1:
        m = fn_matches[0]
        paren_open = m.end() - 1
        paren_close = find_matching_close(stripped, paren_open)
        brace_open = stripped.find("{", paren_close)
        brace_close = find_matching_close(stripped, brace_open)
        return m.start(), brace_close + 1
    if len(fn_matches) > 1:
        raise SystemExit(f"{name}: 找到 {len(fn_matches)} 個符合的頂層函式宣告,不唯一")

    var_pattern = re.compile(r"^(?:let|const|var)\s+" + re.escape(name) + r"\b", re.MULTILINE)
    var_matches = list(var_pattern.finditer(stripped))
    if len(var_matches) != 1:
        raise SystemExit(f"{name}: 找到 {len(var_matches)} 個符合的頂層變數宣告(需要恰好 1 個)")
    m = var_matches[0]
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
            return m.start(), i + 1
        i += 1
    raise SystemExit(f"{name}: 找不到宣告陳述式的結尾分號")


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    target_rel, *names = sys.argv[1:]
    target_path = REPO_ROOT / target_rel
    if target_path.exists():
        raise SystemExit(f"{target_path} 已存在,本工具只處理新檔案")

    source = APP_JS_PATH.read_text(encoding="utf-8")
    stripped = strip_js_noise(source)

    spans = []
    for name in names:
        start, end = find_symbol_span(stripped, source, name)
        # 吃掉緊接著的一個換行,避免搬移後原地留下多餘空行
        text_end = end + 1 if end < len(source) and source[end] == "\n" else end
        spans.append((start, end, text_end, name))

    spans.sort()
    for i in range(1, len(spans)):
        if spans[i][0] < spans[i - 1][2]:
            raise SystemExit(f"範圍重疊:{spans[i-1][3]} 與 {spans[i][3]}")

    # 依原始順序組出目標檔案內容(用 end,不是 text_end,不吃掉搬移內容
    # 本身之後的換行,只在「從 app.js 刪除」時才用 text_end 一併吃掉多餘
    # 空行——這樣目標檔案彼此之間用單一換行銜接,不會累積額外空行)。
    target_parts = [source[start:end] for start, end, _, _ in spans]
    target_content = "\n".join(target_parts) + "\n"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(target_content, encoding="utf-8", newline="\n")

    new_source = source
    for start, end, text_end, name in sorted(spans, reverse=True):
        removed = new_source[start:end]
        assert removed == source[start:end], name
        new_source = new_source[:start] + new_source[text_end:]
    APP_JS_PATH.write_text(new_source, encoding="utf-8", newline="\n")

    # 立即逐位元組比對:重新從（已修改的）app.js 之前狀態驗證不可能了
    # （已覆寫),改成直接比對「剛剛切出來的 span」與「目標檔案裡實際寫入
    # 的內容」是否一致（這一步主要是防呆,防止拼接/寫檔過程本身出錯,
    # 不是防轉寫錯誤——轉寫錯誤已經因為全程不手動輸入內容而不存在)。
    written = target_path.read_text(encoding="utf-8")
    rebuilt = "\n".join(target_parts) + "\n"
    if written != rebuilt:
        raise SystemExit("寫入後重讀內容與預期不符,寫檔本身可能有問題")

    print(f"moved {len(names)} symbols to {target_rel}")
    print(f"app.js new length: {len(new_source)} chars, {new_source.count(chr(10))} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
