"""工單 00-B 第二部分:互動測試路徑的宣告式定義。

純資料模組,無副作用、不 import Playwright。每個 PageSpec 對應
`interaction_inventory.md` 的一個頁面段落,Step 逐條轉錄該頁表格列
(selector / trigger_event / handler_summary / expected_dom_impact / tier)。

**範圍**:本檔只收錄 P0 + P1(依使用者裁決,P2 本輪不寫測試碼)。P2 條目清單見
`interaction_inventory.md` 各頁表格,標記 tier="P2" 的列;待後續工單以 `--interactions-full`
方式補上,新增時比照本檔案格式即可,不需改動 interaction_check.py 引擎。

render_only=True 的頁面(derivatives-analytics / derivatives-status / derivatives-assets)
沒有真正的互動控制項,PageSpec 的每個 Step.action 為 None,只在頁面載入穩定後跑 asserts
(裁決紀錄第2點:渲染型 P0,斷言主要資料區塊載入後非空)。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WaitFor:
    """互動後的等待策略(工單要求:明確條件,不得以固定 sleep 當主要同步手段)。

    kind="stable"        等待 target(或整個 body)在連續 2 輪輪詢間內容不再變化。
    kind="response"      等待符合 pattern 的一個網路回應(action 必須在此等待範圍內觸發)。
    kind="class_present" 等待 target 出現 class_name(用於單純的 class 切換型互動)。
    """

    kind: str
    target: str | None = None
    pattern: str | None = None
    class_name: str | None = None


@dataclass(frozen=True)
class Assert:
    """斷言必須是實質的(工單要求,禁止只斷言沒有 console error)。

    target=None 代表沿用該 Step 本身操作的元素(selector + action_index)。
    """

    kind: str
    target: str | None = None
    n: int | None = None
    class_name: str | None = None
    pattern: str | None = None


def wait_stable(target: str | None = None) -> WaitFor:
    return WaitFor(kind="stable", target=target)


def wait_response(pattern: str) -> WaitFor:
    return WaitFor(kind="response", pattern=pattern)


def wait_class(class_name: str, target: str | None = None) -> WaitFor:
    return WaitFor(kind="class_present", target=target, class_name=class_name)


def a_content_changed(target: str | None = None) -> Assert:
    return Assert(kind="content_changed", target=target)


def a_min_count(target: str, n: int) -> Assert:
    return Assert(kind="min_count", target=target, n=n)


def a_class_present(class_name: str, target: str | None = None) -> Assert:
    return Assert(kind="class_present", target=target, class_name=class_name)


def a_value_changed(target: str | None = None) -> Assert:
    return Assert(kind="value_changed", target=target)


def a_url_matches(pattern: str) -> Assert:
    return Assert(kind="url_matches", pattern=pattern)


def a_request_fired(pattern: str) -> Assert:
    return Assert(kind="request_fired", pattern=pattern)


def a_not_disabled(target: str | None = None) -> Assert:
    return Assert(kind="not_disabled", target=target)


def a_canvas_drawn(target: str) -> Assert:
    return Assert(kind="canvas_drawn", target=target)


@dataclass(frozen=True)
class Step:
    id: str
    tier: str  # "P0" | "P1"
    selector: str
    action: str | None  # "click" | "fill" | "select" | None(渲染型,無互動)
    action_value: str | None = None
    action_index: int = 0
    pre_fill: tuple[str, str] | None = None
    wait_for: WaitFor = field(default_factory=wait_stable)
    asserts: tuple[Assert, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class PageSpec:
    file: str
    steps: tuple[Step, ...]
    render_only: bool = False
    # capture 模式下,在打開瀏覽器前先用一般 HTTP 呼叫這些端點一次,把伺服器端的
    # TTL 快取(如法人籌碼)預熱。部分端點在冷快取時要打真正的外部即時資料源,
    # 耗時遠超過頁面互動測試合理的等待範圍;這類請求通常不是任何 Step 明確操作的
    # 對象,而是頁面渲染時自動背景觸發(如個股詳情頁的法人買賣超),預熱可避免
    # capture 當下 context 關閉時把仍在飛行中的請求錄成無效(status<=0)的 HAR 項目。
    warmup_urls: tuple[str, ...] = ()
    # 已知既有 bug、依使用者裁決排除於基準驗證範圍外的說明(不是「這條路徑通過測試」,
    # 而是「這條路徑被刻意短路,不代表已驗證正常」)。寫入 manifest.json 供人工稽核,
    # 對應的 TD 編號與細節見 docs/TD稽核清單.md 與 interaction_inventory.md。
    known_issues: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Batch 0:框架驗證頁(tw-stock-search.html)
# ---------------------------------------------------------------------------

TW_STOCK_SEARCH = PageSpec(
    file="tw-stock-search.html",
    known_issues=(
        "TD-16: 個股詳情頁自動觸發的 loadInstitutionalTradeHistoryIfNeeded()"
        "(app.js:678)在法人買賣超歷史筆數<5時無限遞迴,實測 stack overflow。"
        "interaction_check.py 用合成回應短路此背景請求,僅為避免連累其他 P0/P1"
        "路徑的基準穩定性,不代表此路徑本身已驗證正常;TD-16 修復前不納入基準。",
    ),
    steps=(
        Step(
            id="tw-stock-search__search-form-submit",
            tier="P0",
            selector="#stock-search-form button[type=submit]",
            action="click",
            pre_fill=("#stock-search-input", "2330"),
            wait_for=wait_stable(),
            asserts=(
                a_min_count("#search-results [data-code]", 1),
                a_content_changed("#stock-detail"),
            ),
            note="表單送出→live 搜尋 2330→自動選取第一筆→載入個股詳情(app.js:33195,33139)",
        ),
        Step(
            id="tw-stock-search__input-debounce",
            tier="P0",
            selector="#stock-search-input",
            action="fill",
            action_value="0050",
            wait_for=wait_response("**/api/twse/live-search**"),
            asserts=(a_content_changed("#search-results"),),
            note="輸入去抖 600ms 觸發 live 搜尋,不自動選取(app.js:33205-33214)",
        ),
        Step(
            id="tw-stock-search__result-click",
            tier="P0",
            selector="#search-results [data-code]",
            action="click",
            action_index=0,
            wait_for=wait_stable("#stock-detail"),
            asserts=(
                a_class_present("is-active"),
                a_content_changed("#stock-detail"),
            ),
            note="點擊搜尋結果→標記 is-active→更新 URL→載入個股詳情(app.js:8880-8898)",
        ),
        Step(
            id="tw-stock-search__watchlist-toggle",
            tier="P1",
            selector="#stock-detail [data-stock-watchlist-toggle]",
            action="click",
            wait_for=wait_class("is-added"),
            asserts=(a_class_present("is-added"),),
            note="加入自選→按鈕文字/樣式切換(app.js:32188-32198)",
        ),
        Step(
            id="tw-stock-search__interval-week",
            tier="P0",
            selector='#stock-detail [data-interval="week"]',
            action="click",
            wait_for=wait_stable("#stock-detail"),
            asserts=(a_class_present("is-active"),),
            note="切換週線→active 樣式切換,重繪技術圖表(app.js:32477-32487)",
        ),
        Step(
            id="tw-stock-search__ma-period-20",
            tier="P1",
            selector='#stock-detail [data-ma-period="20"]',
            action="click",
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換 MA20 疊圖(app.js:32497-32509)",
        ),
        Step(
            id="tw-stock-search__chart-indicator-bollinger",
            tier="P1",
            selector='#stock-detail [data-chart-indicator="bollinger"]',
            action="click",
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換布林通道疊圖指標(app.js:32511-32524)",
        ),
        Step(
            id="tw-stock-search__stock-zoom-in",
            tier="P1",
            selector='#stock-detail [data-stock-zoom="in"]',
            action="click",
            wait_for=wait_stable("#stock-detail"),
            asserts=(a_not_disabled('#stock-detail [data-stock-zoom="out"]'),),
            note="縮放圖表可視K棒數→縮小/重設按鈕從 disabled 變為可用(app.js:32452-32463)",
        ),
        Step(
            id="tw-stock-search__institution-range-3m",
            tier="P1",
            selector='#stock-detail [data-institution-range="3m"]',
            action="click",
            # 只有 range∈{6m,1y} 會另外打外部即時資料源(app.js:32233 shouldFetchRealRange);
            # 3m 是純前端用既有已載入資料重渲染,不依賴外部資料源可用性,避免把基準綁在
            # 即時資料源的成功率上(該外部呼叫在本機驗證時觀測到會回傳失敗/逾時,屬已知
            # 不穩定路徑,依裁決「寧可少測、不收 flaky 測試進基準」原則改測不依賴外部
            # 請求的 3m 分支,涵蓋的仍是同一組 click handler / 同一個 DOM 更新邏輯)。
            wait_for=wait_stable("#stock-detail"),
            asserts=(a_content_changed("#stock-detail"),),
            note="切換法人 3 個月區間(純前端重渲染,預設為 1m)→重建法人買賣超區塊(app.js:32209-32276)",
        ),
    ),
)


PAGES: tuple[PageSpec, ...] = (
    TW_STOCK_SEARCH,
)


def get_page_spec(file: str) -> PageSpec:
    for spec in PAGES:
        if spec.file == file:
            return spec
    raise KeyError(f"no PageSpec registered for {file}")
