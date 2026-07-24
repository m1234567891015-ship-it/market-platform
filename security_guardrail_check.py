from __future__ import annotations

import ast
import importlib
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


class GuardrailFailure(AssertionError):
    pass


def read_text(path: str) -> str:
    return (BASE_DIR / path).read_text(encoding="utf-8-sig")


def frontend_combined_source() -> str:
    """TD-02 把 app.js 拆成 app.js + js/*.js,前端安全防護的具體位置隨批次
    搬移改變檔案,但檢查對象邏輯上一直是「整個前端」,合併讀取。"""
    parts = [read_text("app.js")]
    js_dir = BASE_DIR / "js"
    if js_dir.exists():
        parts.extend(p.read_text(encoding="utf-8-sig") for p in sorted(js_dir.glob("*.js")))
    return "\n".join(parts)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise GuardrailFailure(message)


def unsafe_dynamic_url_lines(script: str, attribute: str) -> list[str]:
    needle = f'{attribute}="${{'
    safe_prefix = f'{attribute}="${{safeUrl('
    ignored_fragments = ("querySelector",)
    return [
        line.strip()
        for line in script.splitlines()
        if needle in line and safe_prefix not in line and not any(fragment in line for fragment in ignored_fragments)
    ]


def check_frontend_xss_and_url_safety() -> None:
    script = frontend_combined_source()
    for required in (
        "function escapeHtml(",
        "function safeUrl(",
        "function sanitizeHtml(",
        "nativeInnerHtmlDescriptor.set.call(template, html)",
        'Object.defineProperty(Element.prototype, "innerHTML"',
        'compact.startsWith("javascript:")',
        'compact.startsWith("data:")',
        'compact.startsWith("vbscript:")',
    ):
        assert_true(required in script, f"Missing front-end safety guard: {required}")

    unsafe_href = unsafe_dynamic_url_lines(script, "href")
    unsafe_src = unsafe_dynamic_url_lines(script, "src")
    assert_true(not unsafe_href, "Dynamic href must use safeUrl(): " + "; ".join(unsafe_href[:5]))
    assert_true(not unsafe_src, "Dynamic src must use safeUrl(): " + "; ".join(unsafe_src[:5]))


def check_api_error_sanitization() -> None:
    source = read_text("app.py")
    cache_source = read_text("cache.py")
    forbidden = (
        "{exc}",
        "str(exc)",
        'cache_data["last_error"] = str(exc)',
    )
    for token in forbidden:
        assert_true(token not in source, f"Raw exception detail may leak through API payloads: {token}")
        assert_true(token not in cache_source, f"Raw exception detail may leak through API payloads: {token}")
    for required in (
        "PUBLIC_DATA_SOURCE_ERROR_MESSAGE",
        "def api_exception_response",
        "LOGGER.exception",
    ):
        assert_true(required in source, f"Missing API error guard: {required}")
    assert_true("PUBLIC_CACHE_ERROR_MESSAGE" in cache_source, "Missing API error guard: PUBLIC_CACHE_ERROR_MESSAGE")


def check_admin_token_guard() -> None:
    app_source = read_text("app.py")
    security_source = read_text("security.py")
    routes_derivatives_source = read_text("routes_derivatives.py")
    assert_true("DERIVATIVES_ADMIN_TOKEN" in security_source, "Admin token must come from environment")
    assert_true("hmac.compare_digest" in security_source, "Admin token comparison must use constant-time compare")
    for source in (app_source, security_source, routes_derivatives_source):
        assert_true('request.args.get("admin_token")' not in source, "Admin token must not be accepted in query string")
        assert_true('request.values.get("admin_token")' not in source, "Admin token must not be accepted from request values")


def check_security_headers_static() -> None:
    source = read_text("security.py")
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
        "Strict-Transport-Security",
    ):
        assert_true(header in source, f"Missing security header: {header}")
    for directive in ("default-src 'self'", "base-uri 'self'", "frame-ancestors 'none'", "connect-src 'self'"):
        assert_true(directive in source, f"Missing CSP directive: {directive}")


def check_static_whitelist_static() -> None:
    app_source = read_text("app.py")
    config_source = read_text("market_config.py")
    routes_system_source = read_text("routes_system.py")
    for required in ("ROOT_STATIC_FILES", "ASSET_STATIC_FILES", "send_from_directory"):
        assert_true(
            required in app_source or required in config_source or required in routes_system_source,
            f"Missing static whitelist control: {required}",
        )
    forbidden_entries = (".py", ".sqlite", ".sqlite3", ".db", ".env", ".docx")
    whitelist_section = "\n".join(
        line for line in config_source.splitlines()
        if "ROOT_STATIC_FILES" in line or "ASSET_STATIC_FILES" in line or line.strip().startswith('"')
    )
    for suffix in forbidden_entries:
        assert_true(suffix not in whitelist_section, f"Static whitelist must not include sensitive suffix: {suffix}")


def check_rate_limit_static() -> None:
    app_source = read_text("app.py")
    security_source = read_text("security.py")
    for required in (
        "API_RATE_LIMIT_PER_WINDOW",
        "API_RATE_LIMIT_WINDOW_SECONDS",
        "cleanup_api_rate_limit_state",
        "RATE_LIMITED",
        "Retry-After",
    ):
        assert_true(required in security_source, f"Missing rate-limit guard: {required}")
    assert_true("ProxyFix" in app_source, "Missing rate-limit guard: ProxyFix")
    assert_true('request.headers.get("X-Forwarded-For")' not in security_source, "Rate limit must not trust X-Forwarded-For directly")


def strip_js_noise(source: str) -> str:
    """把字串/樣板字面值/註解常值替換成等長空白,只保留程式碼結構(括號、
    分號、識別字),供括號深度追蹤與頂層陳述式切分使用。用堆疊追蹤樣板
    字面值的 `${...}` 插值區塊——插值內容可能包含巢狀物件字面值、巢狀
    字串、甚至巢狀樣板字面值,單純數 `${` 出現次數會在插值內有物件字面值
    時提早把深度算成 0(第一版有這個 bug,已用 app.js 實測抓到並修正)。
    正規表示式常值(如 `/[&<>"']/g`)的字元類別裡常含引號字元,若誤判成
    字串開頭會讓後續整段文字的字串配對全部錯位(第二版有這個 bug,已用
    app.js 的 escapeHtml() 實測抓到並修正)——用標準的「除法 vs 正規表示式」
    消歧法:`/` 前一個有意義字元若不是識別字/數字/`)`/`]`,視為正規表示式
    開頭。
    """
    out = list(source)
    n = len(source)
    i = 0
    stack: list[str | tuple[str, int]] = ["code"]
    last_significant = ""  # 上一個非空白、非註解的程式碼字元,用來判斷 / 的意義

    def blank_range(start: int, end: int) -> None:
        for k in range(start, end):
            if source[k] != "\n":
                out[k] = " "

    def looks_like_value_end(ch: str) -> bool:
        return ch.isalnum() or ch in "_$)]"

    while i < n:
        mode = stack[-1]
        in_code = mode == "code" or (isinstance(mode, tuple) and mode[0] == "interp")

        if in_code:
            ch = source[i]
            if ch == "/" and i + 1 < n and source[i + 1] == "/":
                j = source.find("\n", i)
                j = n if j == -1 else j
                blank_range(i, j)
                i = j
                continue
            if ch == "/" and i + 1 < n and source[i + 1] == "*":
                j = source.find("*/", i + 2)
                j = n if j == -1 else j + 2
                blank_range(i, j)
                i = j
                continue
            if ch == "/" and not looks_like_value_end(last_significant):
                j = i + 1
                in_class = False
                while j < n:
                    c = source[j]
                    if c == "\\":
                        j += 2
                        continue
                    if c == "\n":
                        break  # 正規表示式常值不能跨行,視為誤判,當作除法放行
                    if c == "[":
                        in_class = True
                    elif c == "]":
                        in_class = False
                    elif c == "/" and not in_class:
                        j += 1
                        break
                    j += 1
                if j <= n and (j == n or source[j - 1] == "/"):
                    while j < n and source[j].isalpha():
                        j += 1
                    blank_range(i, j)
                    last_significant = "/"
                    i = j
                    continue
            if ch not in " \t\r\n":
                last_significant = ch
            if ch in "\"'":
                quote = ch
                j = i + 1
                while j < n and source[j] != quote:
                    if source[j] == "\\":
                        j += 1
                    j += 1
                j = min(j + 1, n)
                blank_range(i, j)
                last_significant = ")"  # 字串是一個值,後面接 / 應視為除法
                i = j
                continue
            if ch == "`":
                out[i] = " "
                stack.append("template")
                last_significant = ")"  # 樣板字面值也是一個值
                i += 1
                continue
            if isinstance(mode, tuple):
                if ch == "{":
                    stack[-1] = ("interp", mode[1] + 1)
                elif ch == "}":
                    new_depth = mode[1] - 1
                    if new_depth == 0:
                        # 這個 } 是插值 ${...} 的收尾,跟被挖空的 ${ 是一對,
                        # 一併挖空,否則外層(如函式本體)的括號配對計數會
                        # 少算一個開括號、多出一個沒人要的收括號。
                        out[i] = " "
                        stack.pop()
                        last_significant = ")"  # 插值結果是一個值
                        i += 1
                        continue
                    stack[-1] = ("interp", new_depth)
            i += 1
            continue

        # mode == "template": 樣板字面值的原始文字區段
        ch = source[i]
        if ch == "\\":
            out[i] = " "
            if i + 1 < n and source[i + 1] != "\n":
                out[i + 1] = " "
            i += 2
            continue
        if ch == "`":
            out[i] = " "
            stack.pop()
            i += 1
            continue
        if source[i : i + 2] == "${":
            out[i] = " "
            out[i + 1] = " "
            stack.append(("interp", 1))
            i += 2
            continue
        if ch != "\n":
            out[i] = " "
        i += 1

    return "".join(out)


TOP_LEVEL_FUNCTION_RE = re.compile(r"^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.MULTILINE)
TOP_LEVEL_VAR_RE = re.compile(r"^(?:let|const|var)\s+([A-Za-z_$][\w$]*)\b", re.MULTILINE)
# 用 (?<!\.) 排除 obj.prop 形式的屬性存取(prop 不是自由變數引用),
# 用 (?!\s*:(?!:)) 排除 {key: value} 物件字面值的 key(避免跟三元運算子
# a ? b : c 的 c 混淆,c 後面通常不會立刻接另一個 :,足夠用於這裡的保守
# 啟發式)。都保留 obj/a/b 本身,是真正的識別字引用。
IDENTIFIER_RE = re.compile(r"(?<!\.)\b[A-Za-z_$][\w$]*\b(?!\s*:(?!:))")

JS_RESERVED_WORDS = {
    "let", "const", "var", "function", "async", "await", "return", "if", "else",
    "for", "while", "do", "switch", "case", "default", "break", "continue",
    "try", "catch", "finally", "throw", "new", "delete", "typeof", "instanceof",
    "in", "of", "this", "class", "extends", "super", "void", "yield", "null",
    "true", "false", "undefined", "static", "get", "set", "import", "export",
    "from", "as",
}

# JS/瀏覽器內建全域,不算「引用到晚載入檔案的符號」。故意保守(寧可放過,
# 不誤判),因為這層檢查的目的是抓「引用到本專案自己定義、但還沒載入的符號」,
# 不是要當一個完整的 lint。
KNOWN_GLOBALS = {
    "window", "document", "console", "localStorage", "sessionStorage", "navigator",
    "location", "history", "URLSearchParams", "URL", "Array", "Object", "Math",
    "JSON", "Map", "Set", "WeakMap", "WeakSet", "Number", "String", "Boolean",
    "Promise", "fetch", "setTimeout", "setInterval", "clearTimeout", "clearInterval",
    "RegExp", "Intl", "Event", "CustomEvent", "requestAnimationFrame", "Element",
    "Node", "NodeList", "HTMLElement", "Symbol", "Error", "TypeError", "RangeError",
    "Proxy", "Reflect", "Blob", "FormData", "AbortController", "structuredClone",
    "crypto", "performance", "matchMedia", "getComputedStyle", "alert", "confirm",
    "prompt", "File", "FileReader", "Image", "IntersectionObserver",
    "MutationObserver", "ResizeObserver", "TextEncoder", "TextDecoder",
    "Uint8Array", "Float32Array", "Function", "Infinity", "NaN", "undefined",
    "isNaN", "isFinite", "parseInt", "parseFloat", "encodeURIComponent",
    "decodeURIComponent", "queueMicrotask", "globalThis", "self", "top", "parent",
    "DOMParser", "XMLSerializer", "CSS", "getSelection", "print", "SVGElement",
    "PointerEvent", "MouseEvent", "KeyboardEvent", "TouchEvent", "WheelEvent",
    "AbortSignal", "ReadableStream", "WritableStream", "Worker", "requestIdleCallback",
    "cancelAnimationFrame", "customElements", "CanvasRenderingContext2D", "Path2D",
}


def js_top_level_declared_names(source: str) -> set[str]:
    stripped = strip_js_noise(source)
    names = {m.group(1) for m in TOP_LEVEL_FUNCTION_RE.finditer(stripped)}
    names |= {m.group(1) for m in TOP_LEVEL_VAR_RE.finditer(stripped)}
    return names


def find_matching_close(text: str, open_pos: int) -> int:
    """text[open_pos] 必須是 ( [ { 之一。回傳配對的收尾括號 index(找不到則
    回傳 len(text))。用整體括號深度(不分開/中/大括號種類)判斷配對,對
    「函式參數列後面接函式本體」這種同一個陳述式橫跨兩組括號的情況才不會
    在參數列结束時就誤判陳述式已經結束。"""
    depth = 0
    n = len(text)
    i = open_pos
    while i < n:
        if text[i] in "([{":
            depth += 1
        elif text[i] in ")]}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n


def js_declaration_skip_spans(stripped: str) -> list[tuple[int, int]]:
    """找出所有「頂層函式宣告」與「頂層變數宣告但值是函式/箭頭函式運算式」
    的完整範圍(從關鍵字開始,到函式本體收尾 `}` 為止)——這些範圍內部是
    函式本體,只在被呼叫時才執行,不算「立即執行程式碼」,整段跳過不分析。
    """
    spans = []
    for m in TOP_LEVEL_FUNCTION_RE.finditer(stripped):
        paren_open = m.end() - 1  # regex 以 \( 結尾,end()-1 正好是那個 ( 的位置
        paren_close = find_matching_close(stripped, paren_open)
        brace_open = stripped.find("{", paren_close)
        if brace_open == -1:
            spans.append((m.start(), paren_close + 1))
            continue
        brace_close = find_matching_close(stripped, brace_open)
        spans.append((m.start(), brace_close + 1))

    func_value_re = re.compile(
        r"^(?:let|const|var)\s+[A-Za-z_$][\w$]*\s*=\s*(async\s+)?(function\b[^{]*|\([^)]*\)\s*=>\s*)",
    )
    for m in TOP_LEVEL_VAR_RE.finditer(stripped):
        line_end = stripped.find("\n", m.start())
        line_end = len(stripped) if line_end == -1 else line_end
        # 抓宣告開頭一段(不含整個值,值可能有好幾千行)判斷是否為函式/箭頭
        # 函式賦值;真正要跳過的範圍還是要從完整字串重新找 { 才能正確配對。
        head_window = stripped[m.start() : m.start() + 400]
        vm = func_value_re.match(head_window)
        if not vm:
            continue
        brace_open = stripped.find("{", m.start() + vm.end())
        if brace_open == -1 or brace_open > m.start() + 2000:
            continue
        # 確認 { 之前只有空白(排除箭頭函式回傳物件字面值 () => ({...}) 這種
        # 「值本身就是物件」而非函式本體的情況——那種仍在函式本體被呼叫時
        # 才求值,一樣安全,一併跳過,不需要特別排除)。
        brace_close = find_matching_close(stripped, brace_open)
        spans.append((m.start(), brace_close + 1))
    spans.sort()
    return spans


def js_top_level_immediate_statement_identifiers(source: str) -> list[tuple[int, set[str]]]:
    """回傳 [(起始行號, 陳述式內引用到的識別字集合), ...]:先把所有函式宣告/
    函式值宣告的完整範圍(含本體)整段跳過,剩下的頂層內容才是會在
    <script> 執行當下就跑的程式碼(立即執行陳述式)。函式本體內部引用
    晚載入檔案的符號是安全的(工單第 2 節第 3 點),不受此規則限制。
    """
    stripped = strip_js_noise(source)
    skip_spans = js_declaration_skip_spans(stripped)

    # 把要跳過的範圍挖空(填成空白,保留換行以維持行號),剩下的就是立即
    # 執行陳述式的原始文字,可以直接用簡單的「頂層 ;」切分(不會再遇到
    # 函式宣告參數列/本體橫跨兩組括號的歧義,因為那些整段都已經被挖空)。
    chars = list(stripped)
    for start, end in skip_spans:
        for k in range(start, min(end, len(chars))):
            if chars[k] != "\n":
                chars[k] = " "
    remaining = "".join(chars)

    n = len(remaining)
    results: list[tuple[int, str]] = []
    i = 0
    line = 1
    depth = 0
    stmt_start_line = None
    stmt_chars: list[str] = []
    while i < n:
        ch = remaining[i]
        if ch == "\n":
            line += 1
        if depth == 0 and ch == ";":
            if stmt_chars:
                results.append((stmt_start_line, "".join(stmt_chars)))
            stmt_chars = []
            stmt_start_line = None
        elif ch in " \t\r\n":
            if stmt_chars:
                stmt_chars.append(" ")
        else:
            if stmt_start_line is None:
                stmt_start_line = line
            stmt_chars.append(ch)
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
        i += 1
    if stmt_chars:
        results.append((stmt_start_line, "".join(stmt_chars)))

    out = []
    for start_line, text in results:
        idents = {m.group(0) for m in IDENTIFIER_RE.finditer(text)} - JS_RESERVED_WORDS
        idents -= locally_bound_names(text)
        if idents:
            out.append((start_line or 0, idents))
    return out


ARROW_PARAM_LIST_RE = re.compile(r"\(([^()]*)\)\s*=>")
ARROW_SINGLE_PARAM_RE = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=>")
LOCAL_DECL_RE = re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)")
NAMED_FUNCTION_EXPR_RE = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")
METHOD_OR_FUNCTION_PARAMS_RE = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(([^()]*)\)\s*\{")


def locally_bound_names(text: str) -> set[str]:
    """找出這段文字內所有「區域繫結」名稱,不是自由變數引用,不該被當成
    「引用到還沒載入的符號」:箭頭函式參數、具名函式運算式自己的名字、
    function/method 簡寫的參數列、巢狀的 const/let/var 宣告(例如 IIFE 本體
    內部自己宣告的區域變數)。這一層是淺層文字啟發式,不是完整作用域分析
    (不分辨陰影範圍,寧可少報不誤報,適合「安全網」的定位)。"""
    bound: set[str] = set()
    for m in ARROW_PARAM_LIST_RE.finditer(text):
        bound |= {t.group(0) for t in IDENTIFIER_RE.finditer(m.group(1))} - JS_RESERVED_WORDS
    for m in ARROW_SINGLE_PARAM_RE.finditer(text):
        bound.add(m.group(1))
    for m in LOCAL_DECL_RE.finditer(text):
        bound.add(m.group(1))
    for m in NAMED_FUNCTION_EXPR_RE.finditer(text):
        bound.add(m.group(1))
    for m in METHOD_OR_FUNCTION_PARAMS_RE.finditer(text):
        # 不管前面的名字是不是保留字(get/set 這類 method 簡寫名稱本來就會撞到
        # 保留字清單),只要是「名字(參數列){」這個形狀,參數列一律視為區域
        # 繫結——就算誤判到 if(x){/while(x){ 的 x,也只是少檢查一個,方向
        # 上安全(這層檢查寧可少報不誤報)。
        bound |= {t.group(0) for t in IDENTIFIER_RE.finditer(m.group(2))} - JS_RESERVED_WORDS
    return bound


def check_frontend_global_symbol_stability() -> None:
    """新增檢查(TD-02):切分前後,app.js + js/*.js 的頂層符號集合必須跟
    凍結基準完全相同——不多也不少。取代原本工單「僅允許 window.MP」的規則
    (該命名空間方案已撤銷,見 docs/工單TD02_前端拆分.md 第 2 節)。"""
    baseline_path = BASE_DIR / "regression" / "baseline" / "frontend" / "global_symbols.json"
    assert_true(baseline_path.exists(), f"Missing frontend global-symbol baseline: {baseline_path}")
    import json

    baseline = set(json.loads(baseline_path.read_text(encoding="utf-8")))

    current: set[str] = set()
    js_dir = BASE_DIR / "js"
    if js_dir.exists():
        for js_file in sorted(js_dir.glob("*.js")):
            current |= js_top_level_declared_names(js_file.read_text(encoding="utf-8-sig"))
    current |= js_top_level_declared_names(read_text("app.js"))

    missing = baseline - current
    extra = current - baseline
    assert_true(not missing, f"Frontend split lost top-level symbols (should still exist somewhere): {sorted(missing)[:10]}")
    assert_true(not extra, f"Frontend split introduced new top-level symbols (unexpected global pollution): {sorted(extra)[:10]}")


def check_frontend_escapehtml_single_source() -> None:
    """escapeHtml 全站只能有一份定義,拆分後要跨 app.js + js/*.js 一起算,
    不能只看 app.js(否則搬到 js/core.js 之後這個檢查會誤判成 0 份)。"""
    count = len(re.findall(r"function escapeHtml\(", read_text("app.js")))
    js_dir = BASE_DIR / "js"
    if js_dir.exists():
        for js_file in sorted(js_dir.glob("*.js")):
            count += len(re.findall(r"function escapeHtml\(", js_file.read_text(encoding="utf-8-sig")))
    assert_true(count == 1, f"escapeHtml must be defined exactly once across app.js + js/*.js, found {count}")


def check_frontend_no_inline_script() -> None:
    """21 頁 HTML 的 <script> 標籤不得含有內容,只允許 src= 形式(工單第 6
    節追加檢查第 3 項)。"""
    script_tag_re = re.compile(r"<script\b[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
    for html_file in sorted(BASE_DIR.glob("*.html")):
        content = html_file.read_text(encoding="utf-8-sig")
        for match in script_tag_re.finditer(content):
            inner = match.group(1).strip()
            assert_true(not inner, f"{html_file.name} has an inline <script> body (only src= is allowed): {inner[:80]!r}")


def html_script_order(content: str) -> list[str]:
    """依 HTML 檔案中出現順序,取出屬於本工單拆分範圍的 <script src=...>
    (js/*.js 與 app.js),忽略 pwa.js、derivatives-ui.js 等範圍外的腳本。"""
    order = []
    for match in re.finditer(r'<script\s+src="([^"]+)"', content):
        src = match.group(1).split("?")[0]
        if src.startswith("js/") or src == "app.js":
            order.append(src)
    return order


def check_frontend_load_order_initialization() -> None:
    """新增檢查(TD-02 第 6 層):確認沒有任何檔案的頂層立即執行陳述式
    (不是函式定義本體)引用到「更晚載入」的檔案中宣告的符號。函式定義本體
    內部引用晚載入檔案的符號視為安全,不受此規則限制(理由見工單第 2 節
    第 3 點)。"""
    html_files = sorted(BASE_DIR.glob("*.html"))
    assert_true(bool(html_files), "No HTML files found to determine script load order")

    orders = {f.name: html_script_order(f.read_text(encoding="utf-8-sig")) for f in html_files}
    non_empty_orders = {name: order for name, order in orders.items() if order}
    assert_true(non_empty_orders, "No HTML file references app.js or js/*.js via <script src=...>")
    first_order = next(iter(non_empty_orders.values()))
    for name, order in non_empty_orders.items():
        assert_true(order == first_order, f"{name} 的 js/*.js + app.js 載入順序與其他頁面不一致: {order} vs {first_order}")

    file_sources: dict[str, str] = {}
    for rel_path in first_order:
        full_path = BASE_DIR / rel_path
        assert_true(full_path.exists(), f"Script referenced in HTML does not exist: {rel_path}")
        file_sources[rel_path] = full_path.read_text(encoding="utf-8-sig")

    declared_so_far: set[str] = set()
    for rel_path in first_order:
        source = file_sources[rel_path]
        own_declared = js_top_level_declared_names(source)
        for line_no, idents in js_top_level_immediate_statement_identifiers(source):
            unresolved = idents - declared_so_far - own_declared - KNOWN_GLOBALS
            unresolved = {name for name in unresolved if not name[:1].isdigit()}
            assert_true(
                not unresolved,
                f"{rel_path}:{line_no} 頂層立即執行程式碼引用到尚未載入的符號: {sorted(unresolved)[:10]}",
            )
        declared_so_far |= own_declared


def check_environment_and_persistence_static() -> None:
    app_source = read_text("app.py")
    security_source = read_text("security.py")
    store_source = read_text("derivatives_store.py")
    assert_true('os.environ.get("DERIVATIVES_DB_PATH"' in app_source, "Database path must be configurable by environment")
    assert_true('os.environ.get("DERIVATIVES_ADMIN_TOKEN")' in security_source, "Admin token must be configured by environment")
    assert_true("self.path.parent.mkdir(parents=True, exist_ok=True)" in store_source, "DB directory must be created for portable persistence")
    assert_true("PRAGMA journal_mode = WAL" in store_source, "SQLite WAL mode must be enabled")
    assert_true("_PRUNE_ALLOWLIST" in store_source, "Dynamic prune SQL must use an allowlist")


def call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = call_name(ast.Call(func=func.value, args=[], keywords=[])) if isinstance(func.value, ast.Call) else ""
        if isinstance(func.value, ast.Name):
            base = func.value.id
        return f"{base}.{func.attr}" if base else func.attr
    return ""


def function_name_stack(tree: ast.AST) -> dict[ast.AST, str]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    names: dict[ast.AST, str] = {}
    for node in ast.walk(tree):
        current = node
        function_name = ""
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_name = current.name
                break
        names[node] = function_name
    return names


def check_sql_parameterization() -> None:
    for filename in ("app.py", "derivatives_store.py"):
        source = read_text(filename)
        tree = ast.parse(source, filename=filename)
        function_names = function_name_stack(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = call_name(node)
            if not (name.endswith(".execute") or name.endswith(".executemany")):
                continue
            if not node.args:
                continue
            first_arg = node.args[0]
            if isinstance(first_arg, ast.JoinedStr):
                function_name = function_names.get(node, "")
                assert_true(
                    filename == "derivatives_store.py" and function_name == "_prune_to_limit",
                    f"{filename}:{node.lineno} SQL f-string is not allowed outside allowlisted pruning",
                )
            if isinstance(first_arg, ast.BinOp):
                raise GuardrailFailure(f"{filename}:{node.lineno} SQL string concatenation/interpolation is not allowed")
    store_source = read_text("derivatives_store.py")
    assert_true("if (table, where_field) not in DerivativesStore._PRUNE_ALLOWLIST" in store_source, "Dynamic prune SQL must validate table/field allowlist")


def check_dangerous_functions() -> None:
    python_forbidden = {"eval", "exec", "os.system", "os.popen", "pickle.loads", "pickle.load"}
    for filename in ("app.py", "security.py", "cache.py", "fetchers.py", "fetch_registry.py", "builders.py", "parsers.py", "routes_system.py", "routes_global_market.py", "routes_twse.py", "routes_derivatives.py", "derivatives_store.py", "market_config.py"):
        tree = ast.parse(read_text(filename), filename=filename)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = call_name(node)
                assert_true(name not in python_forbidden, f"{filename}:{node.lineno} dangerous function is forbidden: {name}")
                if name in {"subprocess.run", "subprocess.call", "subprocess.Popen"}:
                    for keyword in node.keywords:
                        if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                            raise GuardrailFailure(f"{filename}:{node.lineno} subprocess shell=True is forbidden")

    js_source = read_text("app.js")
    js_forbidden_patterns = {
        r"\beval\s*\(": "eval()",
        r"\bnew\s+Function\b": "new Function",
        r"\bdocument\.write\s*\(": "document.write()",
    }
    for pattern, label in js_forbidden_patterns.items():
        assert_true(not re.search(pattern, js_source), f"JavaScript dangerous function is forbidden: {label}")


def check_hardcoded_secrets() -> None:
    candidates = ["app.py", "security.py", "cache.py", "fetchers.py", "fetch_registry.py", "builders.py", "parsers.py", "routes_system.py", "routes_global_market.py", "routes_twse.py", "routes_derivatives.py", "market_config.py", "derivatives_store.py", "app.js", "derivatives-ui.js"]
    secret_assignment = re.compile(
        r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"]([^'\"]{8,})['\"]"
    )
    allowed_fragments = (
        "DERIVATIVES_ADMIN_TOKEN",
        "X-Admin-Token",
        "X-Derivatives-Admin-Token",
        "ADMIN_AUTH_REQUIRED",
        "test-admin-token",
    )
    for filename in candidates:
        source = read_text(filename)
        for match in secret_assignment.finditer(source):
            line = source[max(0, match.start() - 120):match.end() + 120]
            assert_true(
                any(fragment in line for fragment in allowed_fragments),
                f"{filename} appears to contain a hardcoded secret assignment near: {match.group(1)}",
            )


def load_app_with_temp_db() -> tuple[Any, tempfile.TemporaryDirectory[str]]:
    tempdir = tempfile.TemporaryDirectory(prefix="market-pulse-guardrail-")
    os.environ["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
    os.environ["MARKET_PULSE_LOG_LEVEL"] = "CRITICAL"
    os.environ["DERIVATIVES_ADMIN_TOKEN"] = "guardrail-admin-token"
    os.environ["DERIVATIVES_DB_PATH"] = str(Path(tempdir.name) / "guardrail.sqlite3")
    if "app" in sys.modules:
        del sys.modules["app"]
    app_module = importlib.import_module("app")
    return app_module, tempdir


def check_runtime_security_behaviour() -> None:
    app_module, tempdir = load_app_with_temp_db()
    security_module = importlib.import_module("security")
    try:
        client = app_module.app.test_client()

        for path, expected_status in (
            ("/app.js", 200),
            ("/assets/app-icon.svg", 200),
            ("/app.py", 404),
            ("/derivatives-platform.sqlite3", 404),
            ("/assets/app.py", 404),
            ("/V1.0_Security_Baseline_Guardrail_Specification.docx", 404),
        ):
            response = client.get(path)
            assert_true(response.status_code == expected_status, f"{path} expected {expected_status}, got {response.status_code}")

        health = client.get("/api/health")
        headers = health.headers
        assert_true(headers.get("X-Content-Type-Options") == "nosniff", "Missing nosniff header at runtime")
        assert_true(headers.get("X-Frame-Options") == "DENY", "Missing DENY frame header at runtime")
        assert_true("frame-ancestors 'none'" in headers.get("Content-Security-Policy", ""), "CSP frame-ancestors missing at runtime")

        payload = {"rows": [{"institution": "guardrail", "product_code": "TX_GUARD", "trade_date": "2026-06-23"}]}
        denied = client.post("/api/institution/import", json=payload)
        assert_true(denied.status_code == 403, "Admin import without header token must be denied")
        query_denied = client.post("/api/institution/import?admin_token=guardrail-admin-token", json=payload)
        assert_true(query_denied.status_code == 403, "Admin token in URL query must be denied")
        imported = client.post("/api/institution/import", json=payload, headers={"X-Admin-Token": "guardrail-admin-token"})
        assert_true(imported.status_code == 200, f"Admin header token should be accepted, got {imported.status_code}")

        original_limit = security_module.API_RATE_LIMIT_PER_WINDOW
        security_module.API_RATE_LIMIT_PER_WINDOW = 2
        try:
            with security_module.API_RATE_LIMIT_LOCK:
                security_module.API_RATE_LIMIT_STATE.clear()
            assert_true(client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 200, "Rate limit first request failed")
            assert_true(client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 200, "Rate limit second request failed")
            limited = client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.3"})
            assert_true(limited.status_code == 429, "Rate limit must ignore spoofed X-Forwarded-For and return 429")
            assert_true("Retry-After" in limited.headers, "Rate limit response must include Retry-After")
        finally:
            security_module.API_RATE_LIMIT_PER_WINDOW = original_limit
            with security_module.API_RATE_LIMIT_LOCK:
                security_module.API_RATE_LIMIT_STATE.clear()

        db_path = Path(os.environ["DERIVATIVES_DB_PATH"])
        assert_true(db_path.exists(), "Guardrail temp database was not created")
    finally:
        tempdir.cleanup()


CHECKS = (
    ("S-01 static whitelist", check_static_whitelist_static),
    ("S-02 admin header token", check_admin_token_guard),
    ("S-03 SQL parameterization", check_sql_parameterization),
    ("S-04/S-05 XSS and URL safety", check_frontend_xss_and_url_safety),
    ("S-06 API error sanitization", check_api_error_sanitization),
    ("S-07 rate limiting", check_rate_limit_static),
    ("S-08 security headers", check_security_headers_static),
    ("S-09/S-10 env and persistence", check_environment_and_persistence_static),
    ("Dangerous functions", check_dangerous_functions),
    ("Hardcoded secrets", check_hardcoded_secrets),
    ("Runtime security behaviour", check_runtime_security_behaviour),
    ("TD-02 frontend global symbol stability", check_frontend_global_symbol_stability),
    ("TD-02 escapeHtml single source", check_frontend_escapehtml_single_source),
    ("TD-02 no inline script", check_frontend_no_inline_script),
    ("TD-02 load-order initialization", check_frontend_load_order_initialization),
)


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    for name, check in CHECKS:
        try:
            check()
        except Exception as exc:  # noqa: BLE001
            results.append(CheckResult(name, False, str(exc)))
        else:
            results.append(CheckResult(name, True))
    return results


def main() -> int:
    results = run_checks()
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        detail = f" - {result.detail}" if result.detail else ""
        print(f"[{status}] {result.name}{detail}")
    failed = [result for result in results if not result.passed]
    if failed:
        print(f"SECURITY_GUARDRAIL_FAILED: {len(failed)} check(s) failed")
        return 1
    print("SECURITY_GUARDRAIL_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
