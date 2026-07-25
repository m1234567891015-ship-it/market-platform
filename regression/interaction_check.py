"""工單 00-B 第二部分:前端互動行為測試框架。

用法:
    python regression/interaction_check.py --capture   # 建立/更新互動基準(HAR + manifest/results)
    python regression/interaction_check.py --compare   # 與基準比對(重構期反覆執行)

    # 分批 capture(只處理指定頁面,不影響其他頁面已錄好的 HAR/基準):
    python regression/interaction_check.py --capture --pages tw-stock-search.html

範圍(依使用者裁決):只涵蓋 P0 + P1 tier(見 regression/interaction_specs.py)。
`--interactions-full` 旗標先接好,但 P2 尚未實作,目前行為等同預設。

設計要點(詳見 docs/工單00B_前端行為護欄.md 第二部分 + 對話中確認的架構計畫):
- 沿用 regression/frontend_check.py 的 HAR 錄製/重播寫法,但涵蓋範圍不同:
  frontend_check.py 只錄「頁面載入」;這裡的 --capture 會依序執行該頁全部步驟,
  讓互動觸發的請求(切換合約、切換期別等)也進入同一份 HAR,--compare 才能完整重播。
- 每個 Step 的斷言在 capture 當下就必須通過(通不過代表測試設計錯誤,直接中止,
  不能把「連原版都過不了」的東西寫進基準)。
- 等待策略一律用明確條件(stable / response / class_present),不用固定 sleep 主導同步。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from interaction_specs import PAGES, Assert, PageSpec, Step  # noqa: E402
from server_harness import start_server  # noqa: E402

REGRESSION_DIR = Path(__file__).resolve().parent
REPO_ROOT = REGRESSION_DIR.parent
BASELINE_DIR = REGRESSION_DIR / "baseline" / "interactions"
HAR_DIR = BASELINE_DIR / "har"
MANIFEST_PATH = BASELINE_DIR / "manifest.json"
RESULTS_PATH = BASELINE_DIR / "results.json"

# 互動測試的 HAR 錄製/重播需要固定 origin;跟 frontend_check.py(18765)分開,
# 避免兩支腳本萬一被同時執行時搶同一個埠。
FIXED_SERVER_PORT = 18766

_API_REQUEST_MARK = "/api/"

# 自動背景請求(非任何 Step 明確操作的對象,如個股詳情頁載入後自動補齊的法人
# 籌碼/股東分佈/完整基本面)在冷快取時可能打到真正的外部即時資料源,耗時超過
# 前端自身的逾時上限,見 _visit_page 與 _background_route_handler 的說明。
# 目前沒有任何 P0/P1 斷言依賴這些端點的實際內容。

# shareholders、完整基本面補齊(refresh=1,無 quick=1 也無 history=all)這兩類
# 背景請求,app.js 對應的 .catch 只會記一個 console.error 再更新狀態文字,不像
# institutional-history 有遞迴風險,所以直接快速失敗(503)即可,不必合成資料。
# 對應的 console.error 訊息前綴收錄在 _EXPECTED_BACKGROUND_ERROR_PREFIXES,
# 在 console 監聽時視為已知背景雜訊,不計入斷言用的 console_errors。
_EXPECTED_BACKGROUND_ERROR_PREFIXES = (
    "Failed to load full stock detail",
    "Failed to load shareholder distribution",
    # 訊息含動態的股票代號後綴(如 "...AAPL:"),用不含代號的穩定前綴比對。
    "Failed to analyze US watchlist",
    # Chromium 對任何非 2xx 的 fetch/XHR 都會自動印這則泛用訊息,不含 URL;
    # 系統內目前唯一的 503 來源就是上面 _background_route_handler 的刻意快速失敗。
    "Failed to load resource: the server responded with a status of 503",
)


def _is_expected_background_error(message: str) -> bool:
    return any(prefix in message for prefix in _EXPECTED_BACKGROUND_ERROR_PREFIXES)


def _background_route_handler(route, page_file: str) -> None:
    url = route.request.url
    if "/shareholders" in url:
        route.fulfill(status=503, content_type="application/json", body='{"error":"regression-fast-fail"}')
        return
    if "/api/twse/stock/" in url and "refresh=1" in url and "quick=1" not in url and "history=all" not in url:
        route.fulfill(status=503, content_type="application/json", body='{"error":"regression-fast-fail"}')
        return
    if page_file == "us-etf.html" and "/api/us-market/symbol/" in url:
        # loadUsEtfDetail() 的 Promise.all 第二個請求純屬錦上添花的個股補充資料,
        # 已用 .catch(() => null) 包住不影響渲染;client 自己的 fetchWithTimeout
        # 24 秒逾時常在慢請求上先於伺服器回應觸發,讓 HAR 錄成無效回應。同一個
        # URL pattern 在 us-stock-search.html 是核心受測路徑,不可全域短路,
        # 只在 us-etf.html 這裡快速失敗。
        route.fulfill(status=503, content_type="application/json", body='{"error":"regression-fast-fail"}')
        return
    if page_file == "us-watchlist.html" and "/api/us-market/symbol/" in url:
        # loadUsWatchlistAiAnalyses() 逐檔(AAPL/MSFT)依序抓取,無論等多久
        # (試過 networkidle 20s/60s 都一樣)都會在本頁最後一步(卡片點擊→整頁
        # 導航)時被瀏覽器原生行為中止尚在飛行中的請求,錄成無效 HAR 項目。
        # 本頁對這個端點的斷言只看「是否確實觸發請求」(a_request_fired),不看
        # 回應內容,短路成快速失敗一樣能滿足斷言,同時徹底避開這個跟頁面卸載
        # 時序有關、無法單靠拉長等待時間解決的問題。
        route.fulfill(status=503, content_type="application/json", body='{"error":"regression-fast-fail"}')
        return
    route.fallback()


# ---------------------------------------------------------------------------
# DOM 快照與等待策略
# ---------------------------------------------------------------------------

_SNAPSHOT_JS = """([selector, index]) => {
    const els = document.querySelectorAll(selector);
    const el = els[index];
    if (!el) return null;
    return {
        text: el.textContent || "",
        html: el.innerHTML || "",
        value: ("value" in el) ? String(el.value) : null,
        className: el.className || "",
        disabled: !!el.disabled,
        count: els.length,
    };
}"""


def _snapshot(page, selector: str, index: int):
    return page.evaluate(_SNAPSHOT_JS, [selector, index])


def _resolve_target(step: Step, a: Assert) -> tuple[str, int]:
    if a.target is not None:
        return a.target, 0
    return step.selector, step.action_index


def _measure_stability(page, target: str | None):
    if target:
        return page.evaluate(
            "(sel) => { const el = document.querySelector(sel); return el ? el.outerHTML.length : -1; }",
            target,
        )
    return page.evaluate("() => document.documentElement.scrollHeight")


def _wait_dom_stable(page, target: str | None, rounds_required: int = 2, poll_ms: int = 300, max_rounds: int = 60) -> None:
    previous = None
    stable_rounds = 0
    for _ in range(max_rounds):
        page.wait_for_timeout(poll_ms)
        current = _measure_stability(page, target)
        if current == previous:
            stable_rounds += 1
            if stable_rounds >= rounds_required:
                return
        else:
            stable_rounds = 0
        previous = current


def _wait_class_present(page, target: str, class_name: str, index: int = 0, timeout_ms: int = 8000, poll_ms: int = 100) -> None:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        classes = page.evaluate(
            "([sel, idx]) => { const el = document.querySelectorAll(sel)[idx]; return el ? el.className : null; }",
            [target, index],
        )
        if classes and class_name in classes.split():
            return
        page.wait_for_timeout(poll_ms)


# ---------------------------------------------------------------------------
# 斷言
# ---------------------------------------------------------------------------

def _check_assert(page, step: Step, a: Assert, before: dict, after: dict, fired_urls: list[str]) -> tuple[bool, str]:
    if a.kind == "content_changed":
        target, index = _resolve_target(step, a)
        af = after.get((target, index))
        if af is None:
            return False, f"content_changed: 找不到目標元素 {target}[{index}]"
        b = before.get((target, index))
        if b is not None and b["text"] == af["text"] and b["html"] == af["html"]:
            return False, f"content_changed: {target} 內容操作前後未變化"
        return True, ""

    if a.kind == "min_count":
        count = page.evaluate("(sel) => document.querySelectorAll(sel).length", a.target)
        if count < (a.n or 1):
            return False, f"min_count: {a.target} 數量 {count} < {a.n}"
        return True, ""

    if a.kind == "class_present":
        target, index = _resolve_target(step, a)
        af = after.get((target, index)) or _snapshot(page, target, index)
        classes = (af["className"] if af else "") or ""
        if a.class_name not in classes.split():
            return False, f"class_present: {target}[{index}] 缺少 class {a.class_name}(現況 class={classes!r})"
        return True, ""

    if a.kind == "class_toggled":
        # 有些切換是「預設就有這個 class,點擊後移除」(如 VIX 疊圖預設開啟),
        # 跟 class_present 假設的「預設沒有,點擊後加上」方向相反。這裡不管方向,
        # 只看 class 名稱的有無狀態操作前後是否真的不同。
        target, index = _resolve_target(step, a)
        af = after.get((target, index))
        if af is None:
            return False, f"class_toggled: 找不到目標元素 {target}[{index}]"
        b = before.get((target, index))
        after_has = a.class_name in (af["className"] or "").split()
        before_has = a.class_name in (b["className"] or "").split() if b else None
        if before_has is not None and before_has == after_has:
            return False, f"class_toggled: {target}[{index}] 的 class {a.class_name} 操作前後未變化(前後皆為 {after_has})"
        return True, ""

    if a.kind == "value_changed":
        target, index = _resolve_target(step, a)
        af = after.get((target, index))
        if af is None:
            return False, f"value_changed: 找不到目標元素 {target}[{index}]"
        b = before.get((target, index))
        if b is not None and b["value"] == af["value"]:
            return False, f"value_changed: {target} 的值操作前後未變化"
        return True, ""

    if a.kind == "url_matches":
        if not fnmatch.fnmatch(page.url, a.pattern):
            return False, f"url_matches: URL {page.url} 不符合 {a.pattern}"
        return True, ""

    if a.kind == "request_fired":
        if not any(fnmatch.fnmatch(u, a.pattern) for u in fired_urls):
            return False, f"request_fired: 操作期間({len(fired_urls)} 個 API 請求)未偵測到符合 {a.pattern} 的請求"
        return True, ""

    if a.kind == "not_disabled":
        target, index = _resolve_target(step, a)
        af = _snapshot(page, target, index)
        if af is None:
            return False, f"not_disabled: 找不到目標元素 {target}[{index}]"
        if af["disabled"]:
            return False, f"not_disabled: {target}[{index}] 仍為 disabled"
        return True, ""

    if a.kind == "canvas_drawn":
        ok = page.evaluate(
            """(sel) => Array.from(document.querySelectorAll(sel)).some(
                (el) => (el.tagName === "CANVAS" && el.width > 0 && el.height > 0)
                     || (el.tagName.toLowerCase() === "svg" && el.children.length > 0)
            )""",
            a.target,
        )
        if not ok:
            return False, f"canvas_drawn: {a.target} 沒有已繪製的 canvas/svg"
        return True, ""

    raise ValueError(f"unknown assert kind: {a.kind}")


# ---------------------------------------------------------------------------
# Step 執行
# ---------------------------------------------------------------------------

def _perform_action(page, step: Step) -> None:
    loc = page.locator(step.selector).nth(step.action_index)
    if step.action == "click":
        loc.click(timeout=10000)
    elif step.action == "fill":
        # 觀測到的 Playwright/Chromium 怪癖:若這個 Step 前面有任何
        # page.evaluate() 呼叫(例如上一個 Step 為了 assert 而讀 _snapshot),
        # 緊接著對「另一個」元素呼叫 .fill() 常會靜默失敗(不拋錯,但值沒真的
        # 寫入)。先明確 .click() 建立真實的使用者觸發焦點可穩定避開,不是
        # app.js 的問題(tw-optional-stocks__portfolio-shares 之類的欄位序列
        # 已實測重現、確認此修法有效)。
        loc.click(timeout=10000)
        loc.fill(step.action_value or "", timeout=10000)
    elif step.action == "select":
        if step.action_value is None:
            # 選項的實際 value(如到期日)是伺服器動態決定的,不方便在 spec 裡硬編碼;
            # 沒指定 action_value 時改選「第2個選項」(index=1),避開通常是預設值的
            # 第1個選項,確保 change 事件真的代表切換到不同值。
            loc.select_option(index=1, timeout=10000)
        else:
            loc.select_option(step.action_value, timeout=10000)
    else:
        raise ValueError(f"unknown action: {step.action}")


def run_step(page, step: Step, requests_seen: list[str]) -> dict:
    needed_targets: set[tuple[str, int]] = set()
    for a in step.asserts:
        if a.kind in ("content_changed", "value_changed", "class_present", "class_toggled"):
            needed_targets.add(_resolve_target(step, a))

    before = {t: _snapshot(page, t[0], t[1]) for t in needed_targets}

    if step.pre_fill:
        pf_sel, pf_val = step.pre_fill
        # 用 evaluate 直接寫入 value,不觸發 input 事件(避免同時喚醒該欄位自己的
        # debounce 監聽器,和本 Step 的操作互相干擾——debounce 行為由專屬 Step 測試)。
        page.locator(pf_sel).first.evaluate("(el, v) => { el.value = v; }", pf_val)

    start_idx = len(requests_seen)
    if step.wait_for.kind == "response":
        with page.expect_response(step.wait_for.pattern, timeout=30000):
            _perform_action(page, step)
    else:
        _perform_action(page, step)
        if step.wait_for.kind == "stable":
            _wait_dom_stable(page, step.wait_for.target)
        elif step.wait_for.kind == "class_present":
            # target 未指定時預設沿用「這次操作的元素」(selector+action_index),
            # 不能只看 step.selector 的第一個匹配——action_index != 0 時會盯錯元素
            # (實測 tw-stocks__class-tab-select 就是踩到這個坑,見對應 commit)。
            wait_target = step.wait_for.target or step.selector
            wait_index = 0 if step.wait_for.target else step.action_index
            _wait_class_present(page, wait_target, step.wait_for.class_name, index=wait_index)
        elif step.wait_for.kind == "networkidle":
            try:
                page.wait_for_load_state("networkidle", timeout=60000)
            except Exception:  # noqa: BLE001
                pass
    end_idx = len(requests_seen)
    fired_urls = requests_seen[start_idx:end_idx]

    if step.wait_for.kind == "response":
        # 回應到達網路層之後,JS 還要 parse JSON + 重渲染 DOM,兩者間有一段
        # 短暫落差;固定的小緩衝比再疊一個 DOM 穩定輪詢便宜,也足夠。
        page.wait_for_timeout(400)

    after = {t: _snapshot(page, t[0], t[1]) for t in needed_targets}

    failures = []
    for a in step.asserts:
        ok, msg = _check_assert(page, step, a, before, after, fired_urls)
        if not ok:
            failures.append(msg)

    return {
        "id": step.id,
        "tier": step.tier,
        "ok": not failures,
        "failures": failures,
        "after_snapshot": {f"{t}[{i}]": after.get((t, i)) for (t, i) in needed_targets},
    }


def run_render_only_step(page, step: Step) -> dict:
    # TD-16: 渲染型 step 過去完全不看 step.wait_for(沒有 action 可包
    # page.expect_response,所以 "response" 等待種類天生不適用)。"stable"
    # 不需要包 action,_wait_dom_stable 本來就是獨立輪詢函式。"networkidle"
    # 實測對這裡不可靠(這份檔案自己在別處就記錄過同樣的教訓:頁面若有任何
    # 輪詢式背景請求,networkidle 永遠不會觸發,60 秒等待整段浪費在等一個
    # 不會發生的狀態);改直接輪詢 min_count 斷言實際要看的目標選擇器,
    # 等到數量真的滿足或逾時(90 秒,涵蓋法人籌碼這類多批次即時外部資料
    # 抓取實測會用到的時間),比等待「網路閒置」這個間接、不可靠的代理
    # 訊號更直接可靠。
    if step.wait_for.kind == "stable":
        _wait_dom_stable(page, step.wait_for.target)
    elif step.wait_for.kind == "networkidle":
        min_count_asserts = [a for a in step.asserts if a.kind == "min_count"]
        if min_count_asserts:
            deadline = time.time() + 90
            while time.time() < deadline:
                if all(
                    page.evaluate("(sel) => document.querySelectorAll(sel).length", a.target) >= (a.n or 1)
                    for a in min_count_asserts
                ):
                    break
                page.wait_for_timeout(500)
    failures = []
    for a in step.asserts:
        ok, msg = _check_assert(page, step, a, {}, {}, [])
        if not ok:
            failures.append(msg)
    return {"id": step.id, "tier": step.tier, "ok": not failures, "failures": failures, "after_snapshot": {}}


# ---------------------------------------------------------------------------
# 頁面訪問(capture / compare 共用)
# ---------------------------------------------------------------------------

def _visit_page(browser, base_url: str, page_spec: PageSpec, mode: str) -> dict:
    console_errors: list[str] = []
    har_path = HAR_DIR / f"{page_spec.file}.har"
    context_kwargs: dict = {}
    if mode == "capture":
        HAR_DIR.mkdir(parents=True, exist_ok=True)
        context_kwargs["record_har_path"] = str(har_path)
        context_kwargs["record_har_mode"] = "full"
        context_kwargs["record_har_content"] = "embed"
        context_kwargs["record_har_url_filter"] = "**/api/**"

    context = browser.new_context(**context_kwargs)
    if mode == "compare":
        if not har_path.exists():
            raise SystemExit(f"找不到 {page_spec.file} 的互動基準 HAR {har_path},請先執行 --capture")
        context.route_from_har(str(har_path), url="**/api/**", not_found="abort")

    # 部分背景請求(非任何 Step 明確操作的對象,而是頁面渲染時自動觸發,如個股詳情頁
    # 載入後自動補齊的法人籌碼/股東分佈/完整基本面)在冷快取時會打真正的外部即時
    # 資料源,耗時可能逼近甚至超過前端自己 fetchWithTimeout 的逾時上限,導致 HAR
    # 錄到無效回應(compare 重播時會整個中斷,見 _har_broken_entries)或拖慢每次
    # capture。這些端點的內容不是任何 P0/P1 斷言的對象,用 _background_route_handler
    # 統一短路/快速失敗,讓測試穩定且快速,不依賴外部資料源在冷快取下的回應時間。
    context.route("**/api/**", lambda route: _background_route_handler(route, page_spec.file))

    if page_spec.seed_local_storage:
        # add_init_script 在每份新文件的任何頁面腳本執行前跑,確保 app.js 第一次
        # 讀 localStorage 時資料已經在——比 goto 後才 evaluate 設定更早,避免頁面
        # 已經用空清單渲染完一次(自選股類頁面預設 localStorage 是空的)。
        for key, value in page_spec.seed_local_storage.items():
            context.add_init_script(
                f"window.localStorage.setItem({json.dumps(key)}, {json.dumps(value)});"
            )

    page = context.new_page()
    page.on(
        "console",
        lambda msg: console_errors.append(msg.text) if msg.type == "error" and not _is_expected_background_error(msg.text) else None,
    )
    page.on("pageerror", lambda exc: console_errors.append(str(exc)))
    requests_seen: list[str] = []
    page.on("request", lambda req: requests_seen.append(req.url) if _API_REQUEST_MARK in req.url else None)

    page.goto(f"{base_url}/{page_spec.file}", wait_until="load", timeout=30000)
    # 有些頁面初始載入本身就要打較重的即時資料(如 tw-etf.html 的
    # limit=all),寬鬆的 networkidle 比固定輪詢上限更能等到它真的載完;
    # 逾時就退回原本的穩定輪詢當保底(frontend_check.py 已有的教訓:輪詢式
    # 背景請求會讓 networkidle 永遠不觸發,所以還是要有退路)。
    try:
        page.wait_for_load_state("networkidle", timeout=30000)
    except Exception:  # noqa: BLE001
        pass
    _wait_dom_stable(page, None)

    step_results = []
    for step in page_spec.steps:
        if page_spec.render_only or step.action is None:
            outcome = run_render_only_step(page, step)
        else:
            outcome = run_step(page, step, requests_seen)
        step_results.append(outcome)
        if mode == "capture" and not outcome["ok"]:
            context.close()
            raise CaptureAssertionError(
                f"{page_spec.file}::{outcome['id']} 基準抓取時斷言失敗: {outcome['failures']}"
            )

    if mode == "capture":
        # 部分背景請求(如個股詳情頁預設區間的法人籌碼)不在任何 Step 的等待範圍內,
        # 但仍會被錄進 HAR;若在它們完成前就關閉 context,對應請求會被中止,錄成
        # status<=0 的無效回應,compare 重播時會整個中斷(見 _har_broken_entries)。
        # 用 networkidle 讓這類背景請求有機會落地成真正的回應,逾時就放棄
        # (frontend_check.py 已踩過同樣的坑:輪詢式背景請求會讓 networkidle 永遠不觸發)。
        try:
            page.wait_for_load_state("networkidle", timeout=40000)
        except Exception:  # noqa: BLE001
            pass

    context.close()

    if mode == "capture":
        broken = _har_broken_entries(har_path)
        if broken:
            # 這類請求(如頁面自動觸發、非任何 Step 明確操作的背景 fetch)不會被
            # 上面的 Step 斷言擋到,但錄進 HAR 的無效回應(status<=0)會讓 compare
            # 階段的 route_from_har 在重播時整個中斷(Playwright 內部拋出
            # asyncio.CancelledError)。視為與 CaptureAssertionError 同類的外部
            # 資料源當下不穩定,交給呼叫端重試整頁。
            raise CaptureAssertionError(
                f"{page_spec.file} 錄到 {len(broken)} 個無效回應(status<=0)的 API 請求,"
                f"重播時會中斷:{broken[:3]}"
            )

    return {"file": page_spec.file, "console_errors": console_errors, "steps": step_results}


def _warmup(base_url: str, page_spec: PageSpec) -> None:
    import urllib.error
    import urllib.request

    for path in page_spec.warmup_urls:
        url = base_url + path
        try:
            urllib.request.urlopen(url, timeout=150)
            print(f"    [warmup] {path} 完成")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"    [warmup] {path} 失敗(忽略,繼續): {exc}")


def _har_broken_entries(har_path: Path) -> list[str]:
    if not har_path.exists():
        return []
    har = json.loads(har_path.read_text(encoding="utf-8"))
    broken = []
    for entry in har.get("log", {}).get("entries", []):
        status = entry.get("response", {}).get("status")
        if status is None or status <= 0:
            broken.append(entry.get("request", {}).get("url", "<unknown>"))
    return broken


class CaptureAssertionError(RuntimeError):
    """capture 模式下,某個 Step 的斷言沒通過。可能是測試設計錯誤,也可能是該步驟
    依賴的外部即時資料源當下不穩定(見 CAPTURE_RETRY_COUNT 的重試機制)。"""


# 部分互動步驟依賴外部即時資料源(如 TWSE live-search),capture 當下偶發逾時/失敗
# 不代表測試設計有誤(見 tw-stock-search__input-debounce 在本機驗證時的偶發重試紀錄)。
# 重試整頁(而非單一步驟)是因為步驟之間有累積狀態,無法從中間單獨重跑一步。
CAPTURE_RETRY_COUNT = 2


def run(mode: str, page_files: list[str] | None) -> dict:
    from playwright.sync_api import sync_playwright

    specs = [p for p in PAGES if page_files is None or p.file in page_files]
    if page_files is not None:
        missing = set(page_files) - {p.file for p in specs}
        if missing:
            raise SystemExit(f"--pages 指定了未登錄的頁面: {sorted(missing)}")

    results = []
    with start_server(port=FIXED_SERVER_PORT) as server, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for spec in specs:
                print(f"  [{mode}] {spec.file} ({len(spec.steps)} 步驟) ...", flush=True)
                if mode == "capture":
                    if spec.warmup_urls:
                        _warmup(server.base_url, spec)
                    last_error: Exception | None = None
                    for attempt in range(1, CAPTURE_RETRY_COUNT + 2):
                        try:
                            results.append(_visit_page(browser, server.base_url, spec, mode))
                            last_error = None
                            break
                        except CaptureAssertionError as exc:
                            last_error = exc
                            print(f"    [retry {attempt}/{CAPTURE_RETRY_COUNT + 1}] {exc}")
                    if last_error is not None:
                        raise SystemExit(f"[capture] {spec.file} 重試 {CAPTURE_RETRY_COUNT + 1} 次後仍失敗: {last_error}")
                else:
                    try:
                        results.append(_visit_page(browser, server.base_url, spec, mode))
                    except Exception as exc:  # noqa: BLE001
                        # 單一頁面的操作(如某個選擇器失效)可能讓 Playwright 拋出未預期
                        # 例外(逾時、strict mode violation 等),不該讓整個 --compare
                        # 執行中止、連帶跳過其餘頁面。記成一筆失敗結果,繼續跑下一頁。
                        results.append({
                            "file": spec.file,
                            "console_errors": [],
                            "steps": [{
                                "ok": False,
                                "id": "<page-crash>",
                                "tier": "P0",
                                "failures": [f"{type(exc).__name__}: {exc}"],
                            }],
                        })
        finally:
            browser.close()

    if mode == "capture":
        return _write_baseline(results)
    return _compare(results)


# ---------------------------------------------------------------------------
# capture 落盤 / compare 彙整
# ---------------------------------------------------------------------------

def _step_manifest_entry(step: Step) -> dict:
    return {
        "id": step.id,
        "tier": step.tier,
        "selector": step.selector,
        "action": step.action,
        "action_value": step.action_value,
        "action_index": step.action_index,
        "pre_fill": list(step.pre_fill) if step.pre_fill else None,
        "wait_for": {"kind": step.wait_for.kind, "target": step.wait_for.target, "pattern": step.wait_for.pattern, "class_name": step.wait_for.class_name},
        "asserts": [
            {"kind": a.kind, "target": a.target, "n": a.n, "class_name": a.class_name, "pattern": a.pattern}
            for a in step.asserts
        ],
        "note": step.note,
    }


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"pages": {}}


def _write_baseline(results: list[dict]) -> dict:
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_json(MANIFEST_PATH)
    results_doc = _load_json(RESULTS_PATH)
    manifest.setdefault("pages", {})
    results_doc.setdefault("pages", {})

    specs_by_file = {p.file: p for p in PAGES}
    for result in results:
        spec = specs_by_file[result["file"]]
        manifest["pages"][result["file"]] = {
            "render_only": spec.render_only,
            "step_count": len(spec.steps),
            "steps": [_step_manifest_entry(s) for s in spec.steps],
            "known_issues": list(spec.known_issues),
        }
        results_doc["pages"][result["file"]] = {
            "console_error_count": len(result["console_errors"]),
            "steps": result["steps"],
        }
        if result["console_errors"]:
            print(f"  [WARN] {result['file']}: 基準抓取時已出現 console error: {result['console_errors']}")

    manifest["page_count"] = len(manifest["pages"])
    manifest["step_count_total"] = sum(p["step_count"] for p in manifest["pages"].values())
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    RESULTS_PATH.write_text(json.dumps(results_doc, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[interaction_check] 已寫入 {MANIFEST_PATH} 與 {RESULTS_PATH}(累計 {manifest['page_count']} 頁、{manifest['step_count_total']} 步驟)")
    return manifest


def _compare(results: list[dict]) -> dict:
    failures: list[str] = []
    step_count = 0
    for result in results:
        if result["console_errors"]:
            failures.append(f"{result['file']}: 出現 {len(result['console_errors'])} 個 console error: {result['console_errors'][:3]}")
        for step in result["steps"]:
            step_count += 1
            if not step["ok"]:
                failures.append(f"{result['file']}::{step['id']}({step['tier']}): {'; '.join(step['failures'])}")

    ok = not failures
    print(f"[interaction_check] compare 結果: {'PASS' if ok else 'FAIL'} ({len(failures)} 項問題,共 {step_count} 個互動步驟)")
    for failure in failures:
        print(f"  [FAIL] {failure}")
    return {"ok": ok, "failures": failures, "step_count": step_count}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--capture", action="store_true", help="建立/更新互動基準(HAR + manifest/results)")
    group.add_argument("--compare", action="store_true", help="與既有互動基準比對")
    parser.add_argument("--pages", type=str, default=None, help="逗號分隔的頁面檔名清單,限定只處理這些頁面(供分批 capture)")
    parser.add_argument("--interactions-full", action="store_true", help="保留旗標:P2 尚未實作,目前行為等同預設(P0+P1)")
    args = parser.parse_args()

    page_files = [p.strip() for p in args.pages.split(",")] if args.pages else None
    outcome = run("capture" if args.capture else "compare", page_files)
    if args.compare and not outcome.get("ok", False):
        sys.exit(1)
