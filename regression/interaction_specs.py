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


def a_class_toggled(class_name: str, target: str | None = None) -> Assert:
    """跟 a_class_present 不同:不假設 class 是「操作後才出現」,只要求操作前後
    的有無狀態確實不同(涵蓋預設就有、點擊後移除的情況,如 VIX 疊圖預設開啟)。"""
    return Assert(kind="class_toggled", target=target, class_name=class_name)


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


# ---------------------------------------------------------------------------
# Batch 1:搜尋/名錄頁
# ---------------------------------------------------------------------------

US_STOCK_SEARCH = PageSpec(
    file="us-stock-search.html",
    steps=(
        Step(
            id="us-stock-search__search-form-submit",
            tier="P0",
            selector="#us-stock-search-form button[type=submit]",
            action="click",
            pre_fill=("#us-stock-search-input", "AAPL"),
            # #us-stock-detail 內含技術走勢圖(SVG),outerHTML 可能因圖表持續重繪
            # 而永遠等不到 wait_stable 要求的連續兩輪不變;改成直接等待驅動這次
            # 更新的網路回應本身,更精準也更快。
            wait_for=wait_response("**/api/us-market/symbol/**"),
            asserts=(
                a_min_count("#us-search-results .us-result-main-button[data-us-symbol]", 1),
                a_content_changed("#us-stock-detail"),
            ),
            note="表單送出→搜尋 AAPL→自動選取第一筆→載入美股詳情(app.js:22277-22285,22235,autoSelect=true)",
        ),
        Step(
            id="us-stock-search__input-debounce",
            tier="P0",
            selector="#us-stock-search-input",
            action="fill",
            action_value="MSFT",
            wait_for=wait_response("**/api/us-market/search**"),
            asserts=(a_content_changed("#us-search-results"),),
            note="輸入去抖 300ms 觸發搜尋,不自動選取(app.js:22287-22297)",
        ),
        Step(
            id="us-stock-search__result-click",
            tier="P0",
            selector="#us-search-results .us-result-main-button[data-us-symbol]",
            action="click",
            action_index=0,
            # 同 search-form-submit:#us-stock-detail 含技術走勢圖(SVG),
            # wait_stable 在此容器上不可靠,改等驅動更新的網路回應本身。
            wait_for=wait_response("**/api/us-market/symbol/**"),
            asserts=(a_content_changed("#us-stock-detail"),),
            note="點擊搜尋結果→卡片標記 is-active→呼叫 loadUsStockSymbol()(app.js:22198-22204,22207)",
        ),
        Step(
            id="us-stock-search__watchlist-toggle",
            tier="P1",
            selector="#us-stock-detail [data-us-stock-watchlist-toggle]",
            action="click",
            wait_for=wait_class("is-added"),
            asserts=(a_class_present("is-added"),),
            note="加入自選→按鈕文字/樣式切換(app.js:22140-22145)",
        ),
        Step(
            id="us-stock-search__interval-week",
            tier="P0",
            selector='#us-stock-detail [data-us-interval="week"]',
            action="click",
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換週線,資料已內嵌不需重新請求(app.js:21983-21991)",
        ),
        Step(
            id="us-stock-search__ma-period-20",
            tier="P1",
            selector='#us-stock-detail [data-us-ma-period="20"]',
            action="click",
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換 MA20 疊圖(app.js:21992-21999)",
        ),
        Step(
            id="us-stock-search__chart-indicator-bollinger",
            tier="P1",
            selector='#us-stock-detail [data-us-chart-indicator="bollinger"]',
            action="click",
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換布林通道疊圖指標(app.js:22001-22009)",
        ),
        Step(
            id="us-stock-search__stock-zoom-in",
            tier="P1",
            selector='#us-stock-detail [data-us-stock-zoom="in"]',
            action="click",
            # 縮放按鈕的 disabled 狀態切換是同步的(updateZoom 沒有 await),等小範圍
            # 容器(.stock-chart-zoom)穩定就夠,不必等含 SVG 圖表、持續重繪的
            # #us-stock-detail 整塊(見 search-form-submit/result-click 的教訓)。
            wait_for=wait_stable("#us-stock-detail .stock-chart-zoom"),
            asserts=(a_not_disabled('#us-stock-detail [data-us-stock-zoom="out"]'),),
            note="縮放圖表可視範圍→縮小/重設按鈕從 disabled 變為可用(app.js:21942-21944,22021-22023)",
        ),
    ),
)


TW_ETF = PageSpec(
    file="tw-etf.html",
    # 初始載入用 limit=all 打一次全量即時 ETF 報價,冷快取時很慢;先在開瀏覽器前
    # 暖身一次,降低 capture 時初始等待逾時的機率。
    warmup_urls=("/api/twse/etfs?category=all&sort=return_desc&limit=all",),
    steps=(
        # 分頁測試放最前面,趁清單還是初始「全部分類、無查詢字串」的最大狀態,
        # 確保「下一頁」按鈕確實可點——後面幾步會依序疊加查詢字串/分類篩選,
        # 篩選越疊越窄,若分頁測試排在後面容易篩到只剩一頁而按鈕變 disabled。
        Step(
            id="tw-etf__page-next",
            tier="P1",
            selector='[data-tw-etf-page="next"]',
            action="click",
            wait_for=wait_stable("#tw-etf-table-section"),
            asserts=(a_content_changed("#tw-etf-table-section"),),
            note="下一頁→對已載入資料切片重繪表格與分頁(純前端,app.js:33671)",
        ),
        Step(
            id="tw-etf__filter-form-submit",
            tier="P0",
            selector=".tw-etf-list-toolbar #tw-etf-filter-form button[type=submit]",
            action="click",
            # 頁面自建一份 #tw-etf-filter-form 後立刻移除,真正生效的是
            # .tw-etf-list-toolbar 內的第二份同 id 副本(interaction_inventory.md
            # 已記錄的死碼陷阱),測試必須用範圍選擇器鎖定,不可假設裸 id 唯一。
            # 查詢字串刻意用寬鬆的 "00" 前綴(絕大多數台股 ETF 代號的共同前綴),
            # 避免篩到 0 筆,連累後面 category/sort/detail 幾步。
            pre_fill=(".tw-etf-list-toolbar #tw-etf-query", "00"),
            wait_for=wait_response("**/api/twse/etfs**"),
            asserts=(a_content_changed("#tw-etf-table-section"),),
            note="篩選送出→依 query+category+sort 重建清單(app.js:33889-33892,33873)",
        ),
        Step(
            id="tw-etf__category-select",
            tier="P0",
            selector=".tw-etf-list-toolbar #tw-etf-category",
            action="select",
            action_value="high-dividend",
            wait_for=wait_response("**/api/twse/etfs**"),
            asserts=(a_content_changed("#tw-etf-table-section"),),
            note="切換分類→重渲染清單+分頁(app.js:33893,routes_twse.py TW_ETF_CATEGORY_DEFINITIONS)",
        ),
        Step(
            id="tw-etf__sort-select",
            tier="P1",
            selector=".tw-etf-list-toolbar #tw-etf-sort",
            action="select",
            action_value="code",
            wait_for=wait_response("**/api/twse/etfs**"),
            asserts=(a_content_changed("#tw-etf-table-section"),),
            note="依代號排序→重新排序清單(app.js:33894)",
        ),
        Step(
            id="tw-etf__detail-button-click",
            tier="P0",
            selector="button.tw-etf-detail-button[data-tw-etf-detail]",
            action="click",
            action_index=0,
            wait_for=wait_response("**/api/twse/stock/**"),
            asserts=(a_content_changed("#tw-etf-detail"),),
            note="查看→#tw-etf-detail 替換為 ETF 分析/持股/配息卡片(app.js:33903-33915,33965)",
        ),
    ),
)


US_ETF = PageSpec(
    file="us-etf.html",
    # 初始載入打 directoryLimit=6000&quoteLimit=56 的全量美股 ETF 目錄+報價,
    # 前端自己給到 120 秒逾時,冷快取極慢;先暖身降低 capture 逾時機率。
    warmup_urls=("/api/us-market/etf-center?directoryLimit=6000&quoteLimit=56",),
    steps=(
        # 分頁測試放最前面,理由同 tw-etf.html:避免後面的篩選把清單縮到只剩一頁。
        Step(
            id="us-etf__page-next",
            tier="P0",
            selector='[data-us-nyse-page="etf"][data-page="next"]',
            action="click",
            wait_for=wait_stable("#us-nyse-etf-table"),
            asserts=(a_content_changed("#us-nyse-etf-table"),),
            note="下一頁→更新 #us-nyse-etf-table(前端切片,app.js:12850-12865)",
        ),
        Step(
            id="us-etf__page-size-select",
            tier="P1",
            selector='[data-us-nyse-page-size="etf"]',
            action="select",
            action_value="50",
            wait_for=wait_stable("#us-nyse-etf-table"),
            asserts=(a_content_changed("#us-nyse-etf-table"),),
            note="切換每頁筆數→重渲染表格(前端切片,app.js:12818-12827)",
        ),
        Step(
            id="us-etf__search-form-submit",
            tier="P0",
            selector='[data-us-nyse-search-form="etf"] button[type=submit]',
            action="click",
            pre_fill=("#us-nyse-etf-search", "SPY"),
            wait_for=wait_response("**/api/us-market/etf-center**"),
            asserts=(a_content_changed("#us-nyse-etf-table"),),
            note="篩選送出→重設頁碼並重新查詢(app.js:12787-12802,bindUsNyseDirectoryControls)",
        ),
        Step(
            id="us-etf__detail-button-click",
            tier="P0",
            selector="[data-us-etf-detail]",
            action="click",
            action_index=0,
            wait_for=wait_response("**/api/us-market/etf-center**"),
            asserts=(a_content_changed("#us-etf-detail"),),
            note="查看→#us-etf-detail 填入 ETF 行情與明細(app.js:12829-12839,11614)",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Batch 2:衍生品/圖表頁
# ---------------------------------------------------------------------------

FUTURES = PageSpec(
    file="futures.html",
    # 初始載入(limit=12)可能冷快取時很慢(前端自己給到 120 秒逾時),
    # 先暖身降低 capture 初始等待落空的機率。
    warmup_urls=("/api/futures?limit=12",),
    steps=(
        # 注意:interaction_inventory.md 原將 [data-global-refresh="futures"] 列為 P0,
        # 經本次建置測試框架時實際執行期檢查(document.querySelectorAll 確認 0 個
        # 匹配元素),證實該控制項在衍生品類頁面(isDerivativePage=true,futures/options)
        # 根本不會被渲染——app.js:20623 的 isDerivativePage 分支直接走
        # renderDerivativesSinglePageContent(),完全繞過唯一會渲染這顆按鈕的
        # renderGlobalSummaryCard()(app.js:20629,只在 else 分支呼叫)。已回頭修正
        # interaction_inventory.md,此處不再收錄這條路徑。
        # 以下圖表操作類 Step 刻意排在「切換合約/範圍」的 Step 之前,全部在頁面載入的
        # 預設商品(通常是台灣期貨 TX,TAIFEX 契約資料最完整)上操作;detail-symbol/
        # detail-scope/framework-scope 這些「換一個商品看」的 Step 排最後,避免換到
        # 契約資料較少的商品後,後面的圖表操作 Step 找不到對應元素。
        Step(
            id="futures__technical-contract-code",
            tier="P1",
            selector="[data-futures-technical-contract-code]",
            action="click",
            # index=0 常常就是目前已作用中的契約(標為 is-primary),點擊 handler
            # 無早退判斷仍會重渲染,但設回相同 code 產生的 HTML 可能逐位元組相同,
            # 導致 content_changed 誤判失敗;用 index=1 確保切到不同契約。
            action_index=1,
            # 只盯契約橫向捲動列(.futures-contract-scroll),不盯含 K 線圖的
            # #futures-detail 整塊(候選圖表持續重繪,教訓同 us-stock-search),
            # 斷言本身仍看 #futures-detail 內容是否變化。
            wait_for=wait_stable(".futures-contract-scroll"),
            asserts=(a_content_changed("#futures-detail"),),
            note="切換 TAIFEX 合約月份(app.js:19064-19072,無早退判斷,點擊必重渲染)",
        ),
        Step(
            id="futures__technical-interval-week",
            tier="P1",
            selector='[data-futures-technical-interval="week"]',
            action="click",
            action_index=0,
            wait_for=wait_stable(".futures-technical-intervals"),
            asserts=(a_class_present("is-active"),),
            note="切換週線(app.js:19073-19081)",
        ),
        Step(
            id="futures__chart-ma",
            tier="P1",
            selector="[data-futures-chart-ma]",
            action="click",
            action_index=0,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換均線疊圖(app.js:19091-19102)",
        ),
        Step(
            id="futures__chart-indicator",
            tier="P1",
            selector="[data-futures-chart-indicator]",
            action="click",
            action_index=0,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換疊圖指標(布林/斐波那契/支撐壓力/SMC)(app.js:19103-19114)",
        ),
        Step(
            id="futures__chart-zoom-in",
            tier="P1",
            selector='[data-futures-chart-zoom="in"]',
            action="click",
            action_index=0,
            # 縮放是同步重渲染,只盯縮放控制小容器(.stock-chart-zoom),避免圖表
            # 本身持續重繪讓 wait_stable 永遠等不到(教訓同 us-stock-search)。
            wait_for=wait_stable(".stock-chart-zoom"),
            asserts=(a_not_disabled('[data-futures-chart-zoom="out"]'),),
            note="縮放圖表可視K棒範圍→縮小/重設按鈕從 disabled 變為可用(app.js:19127-19161)",
        ),
        Step(
            id="futures__chart-pan",
            tier="P1",
            selector='[data-futures-chart-pan="older"]',
            action="click",
            action_index=0,
            wait_for=wait_stable(".stock-chart-zoom"),
            asserts=(a_not_disabled('[data-futures-chart-pan="newer"]'),),
            note="平移可視範圍→往前平移後「往後」按鈕從 disabled(panOffset<=0)變為可用(app.js:15487-15488,19143-19164)",
        ),
        Step(
            id="futures__watchlist-toggle",
            tier="P1",
            selector="[data-derivative-watch-symbol]",
            action="click",
            action_index=0,
            wait_for=wait_stable(".asset-hub-summary-actions"),
            asserts=(a_content_changed(None),),
            note="加入/移除自選→按鈕文字切換(app.js:13365-13387,僅 localStorage)",
        ),
        Step(
            id="futures__framework-scope",
            tier="P1",
            selector="[data-futures-framework-scope]",
            action="click",
            # 用第2個選項(index=1)而非第1個,避免點到預設已啟用的分頁(該
            # handler 有 `if (scope === current) return;` 提早結束,點目前已啟用
            # 的分頁不會有任何變化,斷言會誤判失敗)。
            action_index=1,
            wait_for=wait_stable(".futures-investment-market-grid"),
            asserts=(a_class_present("is-active"),),
            note="切換投資框架分頁(台灣/美國/國際)(app.js:19013-19020)",
        ),
        Step(
            id="futures__detail-scope",
            tier="P1",
            selector="[data-futures-detail-scope]",
            action="click",
            action_index=1,
            wait_for=wait_stable("#futures-detail .futures-detail-scope-switcher"),
            asserts=(a_class_present("is-active"),),
            note="切換詳細面板市場範圍(台灣/美國/國際期貨)(app.js:19021-19036)",
        ),
        Step(
            id="futures__detail-symbol",
            tier="P0",
            selector="[data-futures-detail-symbol]",
            action="click",
            # index=0 通常就是目前作用中的商品,candles 已經進了
            # derivativesFuturesTechnicalSeriesCache,再點一次不會發出新請求
            # (hydrateDerivativesFuturesCandles 18973 行有 cache-hit 就直接 return
            # 的守門判斷)。切到 index=1 才能確保這步真的切到不同商品。
            action_index=1,
            # 只盯合約晶片列(.us-index-switcher),不等 technical-candles 網路回應——
            # 實測這個組合(換商品後是否連帶觸發新的 TAIFEX K 線抓取)在本機驗證時
            # 多次不穩定(見 commit message),依裁決「寧可少測、不收 flaky 測試進
            # 基準」原則,只驗證「切換商品→詳情面板內容確實改變」這個穩定、確定性的
            # 核心行為,不強求同時斷言背景 hydrate 的網路時序。
            wait_for=wait_stable("#futures-detail .us-index-switcher"),
            asserts=(a_content_changed("#futures-detail"),),
            note="切換合約(TX/MTX/ES=F等)→重渲染詳情/圖表面板(app.js:19037-19043,主要合約選擇器)",
        ),
        Step(
            id="futures__technical-candles-hydrate",
            tier="P0",
            selector="[data-futures-detail-symbol]",
            action=None,
            asserts=(a_min_count("[data-futures-technical-chart-view]", 1),),
            note="非點擊,自動觸發:hydrateDerivativesFuturesCandles() 於頁面載入與合約/週期切換後"
            "把 TAIFEX 官方 K 線資料填入圖表(app.js:18962-19009,19176)。這裡只以圖表容器確實"
            "存在佐證渲染骨架就緒,不嚴格檢查資料是否已抓到(見上方 detail-symbol 說明,"
            "TAIFEX 官方資料源時序在本機驗證時不穩定)。",
        ),
    ),
)


OPTIONS = PageSpec(
    file="options.html",
    # 初始載入 limit=12,冷快取偶爾慢;先暖身。
    warmup_urls=("/api/options?limit=12",),
    steps=(
        # 注意(TD-15 已記錄的死碼,不測):[data-options-chain-source]、
        # [data-tw-option-product]、[data-derivative-watch-symbol](options 情境)、
        # [data-asset-option-underlying](100%不可達,TD-15最高優先)、
        # [data-asset-region-toggle="options-regional-market"](CSS 硬編碼隱藏)。
        Step(
            id="options__chain-strike-select",
            tier="P0",
            selector="[data-options-chain-strike]",
            action="click",
            # index=0 常是 ATM 履約價,可能已經是預設選取狀態(selectStrike 有
            # `strike === derivativesOptionsSelectedStrike` 早退判斷)。
            action_index=1,
            wait_for=wait_class("is-selected"),
            asserts=(a_class_present("is-selected"),),
            note="點選履約價列→標記 is-selected,下方插入 OI/履約價 AI 摘要列(app.js:19347-19360)",
        ),
        Step(
            id="options__focus-key-select-us-market",
            tier="P0",
            # [data-options-market-expiration-select] 只在「市場選擇權鏈」(Cboe
            # 公開市場,非 TAIFEX 官方 TAIWAN_OPTION_CHAIN_UNDERLYINGS)情境才會渲染
            # (app.js:19472-19491 判斷式)——初始狀態是台股官方標的,不會有這顆
            # select。先切到一個確定屬於美股指數的 focus-key(GSPC=S&P 500),
            # 才能穩定觸發市場選擇權鏈渲染路徑。此 Step 必須排在
            # focus-key-select(切換區域分頁)之前——GSPC 是 option-region-0
            # 底下的子項目,一旦切到別的區域分頁,GSPC 這個按鈕會從 DOM 消失。
            selector='[data-options-focus-key*="GSPC"]',
            action="click",
            wait_for=wait_response("**/options-chain/**"),
            asserts=(a_content_changed("#global-market-root"),),
            note="切換到美股指數選擇權(S&P 500)→改走市場選擇權鏈渲染路徑(app.js:19464-19498)",
        ),
        Step(
            id="options__market-expiration-select",
            tier="P1",
            selector="[data-options-market-expiration-select]",
            action="select",
            wait_for=wait_stable("[data-options-market-expiration-select]"),
            asserts=(a_value_changed(None),),
            note="切換到期日→重渲染鏈表格+OI摘要(app.js:19416-19439)",
        ),
        Step(
            id="options__focus-key-select",
            tier="P0",
            selector="[data-options-focus-key]",
            action="click",
            action_index=1,
            # 切換地區/分類分頁通常會重新抓該標的的選擇權鏈。Playwright 的 glob
            # 比對中 * 不跨越 "/",中間有路徑分隔符時必須用 **(先前 "options*chain"
            # 版本因此永遠比對不到 /api/options/chain 這種路徑)。
            wait_for=wait_response("**/options/chain**"),
            asserts=(a_class_present("is-active"),),
            note="切換市場選擇權鏈地區/分類分頁→重渲染商品清單+摘要+鏈表格(app.js:19464-19498)",
        ),
        Step(
            id="options__strategy-button",
            tier="P1",
            selector="button.options-strategy-button[data-options-strategy-key]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換策略卡→顯示對應策略的證據/風險文字(app.js:19456-19463)",
        ),
    ),
)


TW_STOCKS = PageSpec(
    file="tw-stocks.html",
    steps=(
        # 注意(TD-15 已記錄的死碼,不測):renderSectorSyncView()(舊版
        # [data-sector-source]/[data-sync-mode])從未被呼叫,實際生效的是
        # renderSectorSyncViewV2() 的 [data-sector-source-select]。
        Step(
            id="tw-stocks__class-tab-select",
            tier="P0",
            selector=".class-tabs [data-category]",
            action="click",
            # index=0 可能已是預設 activeCategory(handler 無早退判斷,但點擊
            # 目前已啟用的分頁會產生逐位元組相同的重渲染結果)。
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換產業分類分頁→設定 activeCategory,全頁重渲染(app.js:2597-2602)",
        ),
        Step(
            id="tw-stocks__sector-sort-select",
            tier="P1",
            selector="#sector-sort-slot [data-sector-sort]",
            action="select",
            wait_for=wait_stable("#sector-sort-slot"),
            asserts=(a_value_changed(None),),
            note="切換排行指標→重渲染排行表(app.js:2603-2606)",
        ),
        Step(
            id="tw-stocks__sector-source-select",
            tier="P0",
            selector="#sector-sync-view [data-sector-source-select]",
            action="select",
            # loadYahooSectorStockChart 在該來源已有 >=20 筆比較序列快取時直接
            # 跳過 fetch、同步重渲染(app.js:1942-1945),不強求一定要等到網路回應,
            # 只盯同步視圖容器本身的內容變化。
            wait_for=wait_stable("#sector-sync-view"),
            asserts=(a_content_changed("#sector-sync-view"),),
            note="切換比較圖來源→重渲染同步比較視圖(app.js:2447-2457,V2版,非TD-15死碼的V1版)",
        ),
        Step(
            id="tw-stocks__yahoo-sector-group",
            tier="P1",
            selector="#class-links [data-yahoo-sector-group][data-yahoo-sector-index]",
            action="click",
            action_index=1,
            # is-active 的比對基準(activeIndex)是「該按鈕所屬 group 內的相對索引」
            # (app.js:1840,1844),不是這個 Playwright locator 在全頁的第 N 個匹配
            # 順位——兩者對不上,用 content_changed 驗證「點擊後真的抓取/重渲染了」
            # 這個更穩定、語意也對得上的行為即可。
            wait_for=wait_stable("#class-links"),
            asserts=(a_content_changed("#class-links"),),
            note="切換 Yahoo 子分類(電子產業/概念股等)→抓取/快取子分類報價,重渲染全頁"
            "(委派於document,app.js:34138-34143,loadYahooSectorCategory 1849)",
        ),
        Step(
            id="tw-stocks__weighted-mode",
            tier="P0",
            # 指定切到「指數比對」模式(而非泛用 index=1):[data-international-key]
            # 只在 activeMode==="comparison" 時才會渲染(app.js:3966),下一步
            # international-key 需要這個前置狀態;同時仍然驗證了「切換圖表模式→
            # 重渲染整個面板」這個 P0 行為本身。
            selector='#weighted-index-panel [data-weighted-mode="comparison"]',
            action="click",
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換加權指數圖表模式(日/週/月/指數比對)→重渲染整個面板(app.js:3976-3981)",
        ),
        Step(
            id="tw-stocks__international-key",
            tier="P1",
            selector="#weighted-index-panel [data-international-key]",
            action="click",
            action_index=0,
            wait_for=wait_stable("#weighted-index-panel"),
            asserts=(a_content_changed("#weighted-index-panel"),),
            note="切換比較圖顯示的國際指數線(多選,app.js:3982-3991)",
        ),
    ),
)


US_STOCKS = PageSpec(
    file="us-stocks.html",
    steps=(
        Step(
            id="us-stocks__global-refresh",
            tier="P0",
            selector="#us-market-overview [data-global-refresh]",
            action="click",
            wait_for=wait_response("**/api/global-market/us-stocks**"),
            asserts=(a_content_changed("#us-market-overview"),),
            note="重新整理→全頁重新抓取+重渲染(app.js:34132-34137)",
        ),
        Step(
            id="us-stocks__major-index-select",
            tier="P0",
            selector="#us-major-index-vix [data-us-major-index]",
            action="click",
            # 非 ctrl/shift 點擊會直接把選取集合換成單一新指數(app.js:9788),
            # index=1 確保換到跟預設(index=0,^GSPC)不同的指數。
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換主要指數圖表線(S&P/Dow/Nasdaq/Russell)(app.js:9783-9801)",
        ),
        Step(
            id="us-stocks__major-index-all",
            tier="P1",
            selector="#us-major-index-vix [data-us-major-index-all]",
            action="click",
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="全選四大指數(app.js:9802-9808)",
        ),
        Step(
            id="us-stocks__vix-toggle",
            tier="P1",
            selector="#us-major-index-vix [data-us-vix-toggle]",
            action="click",
            # usMajorIndexShowVix 預設為 true,這顆按鈕預設就帶 is-active,點擊後是
            # 移除而非加上(跟大多數「預設沒有,點了才有」的 toggle 方向相反)。
            # wait_class 專為「等 class 出現」設計,用在這裡在點擊前就已符合條件、
            # 等於沒等到任何操作後的狀態;改用小範圍 wait_stable + class_toggled。
            wait_for=wait_stable("#us-major-index-vix .us-index-switcher"),
            asserts=(a_class_toggled("is-active"),),
            note="切換VIX疊圖(app.js:9809-9812)",
        ),
        Step(
            id="us-stocks__sector-benchmark",
            tier="P0",
            selector="#us-sector-index-comparison [data-us-sector-benchmark]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換比較基準指數,重渲染卡片(app.js:10272-10277)",
        ),
        Step(
            id="us-stocks__sector-index",
            tier="P0",
            selector="#us-sector-index-comparison [data-us-sector-index]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換比較的類股指數(app.js:10278-10283)",
        ),
        Step(
            id="us-stocks__sector-stock-select",
            tier="P0",
            selector='#us-sector-stock-browser [data-us-sector-stock][data-us-sector-stock-role="sector"]',
            action="click",
            # index=0 常是目前已選取的類股(usSectorStockSymbol 預設值),點擊
            # handler 無早退判斷仍會重渲染,但設回相同 symbol 產生的表格內容可能
            # 逐位元組相同,導致 content_changed 誤判失敗;用 index=1 確保換類股。
            action_index=1,
            # loadUsSectorStocks() 有 scopeCache 命中就跳過 fetch 的邏輯
            # (app.js:12656-12658),不強求一定要等到網路回應,只盯表格容器本身。
            wait_for=wait_stable("#us-sector-stock-table"),
            asserts=(a_content_changed("#us-sector-stock-table"),),
            note="切換類股(非benchmark角色)→重新載入成分股表格(app.js:12710-12758,loadUsSectorStocks)",
        ),
        Step(
            id="us-stocks__sector-nyse-search-form",
            tier="P0",
            selector="#us-sector-stock-browser form[data-us-sector-nyse-search-form] button[type=submit]",
            action="click",
            pre_fill=("#us-sector-nyse-search", "AAPL"),
            wait_for=wait_stable("#us-sector-stock-table"),
            asserts=(a_content_changed("#us-sector-stock-table"),),
            note="搜尋送出→設定查詢字串,重設頁碼,重新載入(app.js:12759-12765)",
        ),
        Step(
            id="us-stocks__sector-nyse-reset",
            tier="P1",
            selector="#us-sector-stock-browser [data-us-sector-nyse-reset]",
            action="click",
            wait_for=wait_stable("#us-sector-stock-table"),
            asserts=(a_value_changed("#us-sector-nyse-search"),),
            note="清除→清空輸入/查詢字串(app.js:12766-12772)",
        ),
        # 注意:interaction_inventory.md 原將 [data-us-sector-nyse-page="next"] 列為 P0,
        # 經本次建置測試框架時實際執行期檢查證實此控制項結構性不可達——
        # fetchUsSectorScopePayload() 固定 limit=30(app.js:12660),但分頁門檻
        # US_NYSE_DIRECTORY_PAGE_SIZE=50(app.js:10831),30<50 代表這個瀏覽器的
        # 項目數永遠不會超過一頁,「下一頁」按鈕在任何可達狀態下都是 disabled
        # (實測初始載入即 disabled,9 筆資料)。已登錄為 TD-15 新增項目並修正
        # interaction_inventory.md,此處不再收錄這條路徑。
    ),
)


PAGES: tuple[PageSpec, ...] = (
    TW_STOCK_SEARCH,
    US_STOCK_SEARCH,
    TW_ETF,
    US_ETF,
    FUTURES,
    OPTIONS,
    TW_STOCKS,
    US_STOCKS,
)


def get_page_spec(file: str) -> PageSpec:
    for spec in PAGES:
        if spec.file == file:
            return spec
    raise KeyError(f"no PageSpec registered for {file}")
