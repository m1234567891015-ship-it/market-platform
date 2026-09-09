"""工單 00-B 第二部分:互動測試路徑的宣告式定義。

純資料模組,無副作用、不 import Playwright。每個 PageSpec 對應
`interaction_inventory.md` 的一個頁面段落,Step 逐條轉錄該頁表格列
(selector / trigger_event / handler_summary / expected_dom_impact / tier)。

**範圍**:本檔只收錄 P0 + P1(依使用者裁決,P2 本輪不寫測試碼)。P2 條目清單見
`interaction_inventory.md` 各頁表格,標記 tier="P2" 的列;待後續工單以 `--interactions-full`
方式補上,新增時比照本檔案格式即可,不需改動 interaction_check.py 引擎。

render_only=True 的頁面(derivatives-status / derivatives-assets)
沒有真正的互動控制項,PageSpec 的每個 Step.action 為 None,只在頁面載入穩定後跑 asserts
(裁決紀錄第2點:渲染型 P0,斷言主要資料區塊載入後非空)。derivatives-analytics
另有策略選擇器,因此以 P0 select 路徑驗證明細切換與 fail-closed 狀態。
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


def wait_networkidle() -> WaitFor:
    """給「觸發一整串背景 fetch 佇列(如逐檔重新分析)」用:wait_stable 常在佇列
    處理到一半、畫面暫時沒變化時就誤判穩定提早返回,佇列剩下的請求若稍後被其他
    Step(尤其是整頁導航)中斷,會在 capture 錄成無效 HAR 項目。改等網路真正閒置。
    """
    return WaitFor(kind="networkidle")


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
    # 自選股一類頁面預設 localStorage 是空的,沒有既有項目就沒有卡片可互動。
    # {key: JSON 字串},在每次頁面導覽前用 context.add_init_script 寫入,
    # 讓 app.js 首次讀取 localStorage 時就看得到(比 goto 後才 evaluate 設定更早,
    # 避免頁面已經用空清單渲染完一次)。
    seed_local_storage: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Batch 0:框架驗證頁(tw-stock-search.html)
# ---------------------------------------------------------------------------

TW_STOCK_SEARCH = PageSpec(
    file="tw-stock-search.html",
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
            id="tw-stock-search__institution-history-background-load",
            tier="P0",
            selector=".chip-institution-daily-table",
            action=None,
            wait_for=wait_networkidle(),
            asserts=(a_min_count(".chip-institution-daily-table .chip-data-row", 1),),
            note=(
                "TD-16:個股詳情頁渲染完成後自動背景觸發的法人買賣超歷史載入"
                "(js/stock-detail.js:loadInstitutionalTradeHistoryIfNeeded)。"
                "非任何 P0/P1 控制項觸發,是 renderStockDetail 內部無條件呼叫"
                "的背景 fetch;渲染型 step(無 action)。wait_for 標記為"
                "networkidle,但實測頁面背景輪詢會讓 networkidle 永遠不觸發,"
                "interaction_check.py 對渲染型 step 改直接輪詢本 step 的"
                "min_count 斷言目標(逾時 90 秒,涵蓋法人籌碼這類多批次即時"
                "外部資料抓取實測會用到的時間),等目標選擇器數量真的達標才"
                "斷言。TD-16 修復前此路徑會在法人交易歷史"
                "筆數 < 5 時無限遞迴,列為 known-broken 排除於基準外;修復後"
                "正式納入。"
            ),
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


# ---------------------------------------------------------------------------
# Batch 3:自選股/組合模擬頁
# ---------------------------------------------------------------------------

TW_OPTIONAL_STOCKS = PageSpec(
    file="tw-Optional-stocks.html",
    # 自選股清單預設是空的(localStorage 沒資料就沒卡片可互動),播種2筆固定資料。
    seed_local_storage={
        "market-pulse-watchlist-v1": '[{"code":"2330","name":"台積電","market":"TWSE"},'
        '{"code":"0050","name":"元大台灣50","market":"TWSE"}]',
    },
    steps=(
        # analysis-refresh 刻意不排第一步:loadWatchlistAiAnalyses(true) 會啟動
        # 非同步佇列逐檔抓取(2檔),每抓完一檔就整個重渲染 #watchlist-grid
        # (連帶重渲染模擬器表格)一次;wait_stable 只盯 #watchlist-grid 穩定,
        # 抓不到「模擬器表格也還在被非同步重渲染」的尾巴。實測若接下來立刻操作
        # 模擬器輸入框,填入的值會被隨後才完成的背景重渲染用(尚未存檔的)舊值
        # 蓋掉。排在所有模擬器欄位測試「之後」,避開這個競態視窗。
        Step(
            id="tw-optional-stocks__portfolio-entry-price",
            tier="P0",
            selector='input[type=number][data-portfolio-field="entryPrice"]',
            action="fill",
            action_value="999",
            wait_for=wait_stable("#portfolio-simulator-table"),
            asserts=(a_value_changed(None),),
            note="修改進場價→重算並重渲染整個模擬器摘要與表格(app.js:5707-5718)",
        ),
        Step(
            id="tw-optional-stocks__portfolio-shares",
            tier="P0",
            selector='input[type=number][data-portfolio-field="shares"]',
            action="fill",
            action_value="500",
            wait_for=wait_stable("#portfolio-simulator-table"),
            asserts=(a_value_changed(None),),
            note="修改股數→重算並重渲染整個模擬器摘要與表格(app.js:5707-5718)",
        ),
        Step(
            id="tw-optional-stocks__portfolio-stop-loss",
            tier="P1",
            selector='input[type=number][data-portfolio-field="stopLossPct"]',
            action="fill",
            action_value="15",
            wait_for=wait_stable("#portfolio-simulator-table"),
            asserts=(a_value_changed(None),),
            note="修改停損%→重算停損風險金額/riskLabel(app.js:5707-5718)",
        ),
        Step(
            id="tw-optional-stocks__portfolio-take-profit",
            tier="P1",
            selector='input[type=number][data-portfolio-field="takeProfitPct"]',
            action="fill",
            action_value="25",
            wait_for=wait_stable("#portfolio-simulator-table"),
            asserts=(a_value_changed(None),),
            note="修改停利%→重算並重渲染(app.js:5707-5718)",
        ),
        Step(
            id="tw-optional-stocks__portfolio-reset",
            tier="P1",
            selector="#portfolio-simulator-reset",
            action="click",
            wait_for=wait_stable("#portfolio-simulator-table"),
            asserts=(a_content_changed("#portfolio-simulator-table"),),
            note="重設為預設值(進場價=現價、股數=0、停損8%/停利15%)(app.js:8848-8851)",
        ),
        Step(
            id="tw-optional-stocks__analysis-refresh",
            tier="P0",
            selector="#watchlist-analysis-refresh",
            action="click",
            # loadWatchlistAiAnalyses(true) 清快取後重新抓取,但 HAR 重播的資料是
            # 凍結的——同一支股票重新抓「同一筆」資料、重算出來的 AI 建議文字會
            # 逐位元組相同,content_changed 在這裡永遠會誤判失敗(不是等待時機
            # 的問題,是這個動作在凍結資料下本來就不會改變最終文字)。改斷言
            # 「這個動作確實觸發了重新抓取」這個不受資料是否變動影響的行為。
            # 佇列逐檔處理(2檔),wait_stable 常在兩檔之間畫面暫時沒變化時就
            # 誤判穩定提早返回,佇列還沒處理完的請求若被後面的整頁導航 Step
            # 中斷,capture 會錄成無效 HAR 項目;改等網路真正閒置。
            wait_for=wait_networkidle(),
            asserts=(a_request_fired("**/api/twse/stock/**"),),
            note="AI分析重新整理→清除快取,逐檔重新抓取即時資料(app.js:8726,8845-8847)",
        ),
        Step(
            id="tw-optional-stocks__watchlist-remove",
            tier="P1",
            selector="button.watchlist-remove[data-watchlist-remove]",
            action="click",
            # 保留 index=0(2330)給最後一步的導航測試用,先移除 index=1(0050)。
            action_index=1,
            wait_for=wait_stable("#watchlist-grid"),
            asserts=(a_content_changed("#watchlist-grid"),),
            note="移除自選→從 localStorage 移除,重渲染清單,更新統計/狀態文字(app.js:8715-8723)",
        ),
        Step(
            id="tw-optional-stocks__card-navigate",
            tier="P0",
            # 放最後一步:這是真正的整頁導航(window.location.href),導航後頁面已
            # 不是 tw-Optional-stocks.html,後面不能再接其他 Step。
            selector=".watchlist-card[data-watchlist-detail-url]",
            action="click",
            action_index=0,
            wait_for=wait_stable(None),
            asserts=(a_url_matches("**/tw-stock-search.html?q=2330*"),),
            note="點擊卡片→完整導航到 tw-stock-search.html?q=...(app.js:8699-8713)",
        ),
    ),
)


US_WATCHLIST = PageSpec(
    file="us-watchlist.html",
    seed_local_storage={
        "market-pulse-us-watchlist-v1": '[{"symbol":"AAPL","name":"Apple Inc."},'
        '{"symbol":"MSFT","name":"Microsoft"}]',
    },
    steps=(
        # analysis-refresh 排在模擬器欄位測試之後,理由同 tw-optional-stocks:
        # 非同步逐檔重渲染的尾巴會蓋掉緊接著填入模擬器輸入框的值。
        Step(
            id="us-watchlist__portfolio-entry-price",
            tier="P1",
            selector='#us-portfolio-simulator-table input[type=number][data-us-portfolio-field="entryPrice"]',
            action="fill",
            action_value="999",
            wait_for=wait_stable("#us-portfolio-simulator-table"),
            asserts=(a_value_changed(None),),
            note="修改進場價→寫入storage,重渲染模擬器(重算損益/風險指標)(app.js:22893-22902)",
        ),
        Step(
            id="us-watchlist__portfolio-reset",
            tier="P1",
            selector="#us-portfolio-simulator-reset",
            action="click",
            wait_for=wait_stable("#us-portfolio-simulator-table"),
            # 盯整個表格容器的 content_changed 在這裡不穩定(重設後的預設進場價
            # 剛好與前一步填入的測試值格式化後可能重疊或表格其餘部分掩蓋了差異),
            # 改直接盯進場價欄位本身的 value 是否確實變動,更精準也更可靠。
            asserts=(a_value_changed('#us-portfolio-simulator-table input[data-us-portfolio-field="entryPrice"]'),),
            note="清除模擬器 storage,重渲染為預設值(app.js:22994-22997)",
        ),
        Step(
            id="us-watchlist__analysis-refresh",
            tier="P0",
            selector="#us-watchlist-analysis-refresh",
            action="click",
            # 同 tw-optional-stocks 的教訓:HAR 重播下重新抓「同一筆」資料重算出
            # 的文字會逐位元組相同,content_changed 在這裡結構性地不適用,改斷言
            # 「確實觸發了重新抓取」;wait_stable 也常在佇列處理到一半時誤判
            # 穩定提早返回,改等網路真正閒置,避免尾巴請求被後面的導航中斷。
            wait_for=wait_networkidle(),
            asserts=(a_request_fired("**/api/us-market/symbol/**"),),
            note="AI分析重新整理→清除快取,逐檔重新抓取(app.js:22551,22991-22993)",
        ),
        Step(
            id="us-watchlist__watch-remove",
            tier="P0",
            selector="#us-watchlist-grid [data-us-watch-remove]",
            action="click",
            # 保留 index=0(AAPL)給最後一步的導航測試用,先移除 index=1(MSFT)。
            action_index=1,
            wait_for=wait_stable("#us-watchlist-grid"),
            asserts=(a_content_changed("#us-watchlist-grid"),),
            note="從localStorage移除,重渲染網格,更新狀態文字(app.js:22679-22688)",
        ),
        Step(
            id="us-watchlist__card-navigate",
            tier="P0",
            # 放最後一步:真正的整頁導航(window.location.href)。
            selector="#us-watchlist-grid [data-us-watchlist-detail-url]",
            action="click",
            action_index=0,
            wait_for=wait_stable(None),
            # 實測發現既有的競態小 bug(非本測試框架造成):導航到
            # us-stock-search.html 後,initUsStockSearchPage() 內
            # runUsStockSearch(initialSymbol,...) 的 replaceState(改用 ?q=)
            # 和其內部 autoSelect 觸發的 loadUsStockSymbol() 的 replaceState
            # (改用 ?symbol=)互相競爭,最終 URL 的參數名稱不確定是 q= 還是
            # symbol=(兩種都實測出現過),但兩者最終都正確顯示 AAPL,不影響
            # 使用者可見行為。斷言放寬為不依賴參數名稱,只認導航目的地與代號正確。
            asserts=(a_url_matches("**/us-stock-search.html?*AAPL*"),),
            note="點擊卡片→完整導航到 us-stock-search.html(app.js:22664-22678)",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Batch 4:Asset-hub 頁(bonds/international-finance/precious-metals 共用元件:
# initAssetFinanceTrendSwitchers/initAssetFinanceVolumeSelectors/
# initAssetFinanceBondFocusControls,皆為純前端用內嵌 JSON 重渲染,class_present
# 斷言 + wait_class 足夠,不需要 wait_stable/wait_response)
# ---------------------------------------------------------------------------

BONDS = PageSpec(
    file="bonds.html",
    steps=(
        Step(
            id="bonds__etf-bucket",
            tier="P0",
            selector="[data-bond-etf-bucket]",
            action="click",
            # index=0 是預設 bucket(有「已是目前bucket」早退判斷,app.js:27893)。
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換ETF分類→重渲染債券ETF表格與訊號卡(app.js:27890-27898)",
        ),
        Step(
            id="bonds__yield-focus",
            tier="P1",
            selector="[data-bond-yield-focus]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換殖利率焦點→更新AI評論文字,按鈕active狀態切換(app.js:27881-27889)",
        ),
        Step(
            id="bonds__volume-symbol",
            tier="P1",
            selector="[data-asset-finance-volume-symbol]",
            action="click",
            action_index=0,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="選取ETF→切換24日趨勢圖+個股AI分析面板(app.js:26211-26213)",
        ),
    ),
)


INTERNATIONAL_FINANCE = PageSpec(
    file="international-finance.html",
    steps=(
        Step(
            id="international-finance__trend-range",
            tier="P0",
            selector="[data-asset-finance-trend-range]",
            action="click",
            # index=0 是預設range(1m),無早退判斷但重複點選同一range會產生
            # 逐位元組相同的重渲染結果。
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換國際貴金屬走勢圖時間範圍→重繪趨勢圖、更新狀態文字與預測面板(app.js:24397,24447-24450)",
        ),
        Step(
            id="international-finance__trend-metal",
            tier="P1",
            selector="[data-asset-finance-trend-metal]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="篩選單一金屬序列(app.js:24452-24458)",
        ),
        Step(
            id="international-finance__volume-symbol",
            tier="P1",
            selector="button.asset-finance-etf-select[data-asset-finance-volume-symbol]",
            action="click",
            action_index=0,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換ETF圖表+個股分析文字(app.js:26179)",
        ),
    ),
)


PRECIOUS_METALS = PageSpec(
    file="precious-metals.html",
    steps=(
        Step(
            id="precious-metals__trend-range",
            tier="P0",
            selector="button[data-asset-finance-trend-range]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換貴金屬走勢圖時間範圍(app.js:24397,24447-24450,與international-finance.html同機制)",
        ),
        Step(
            id="precious-metals__trend-metal",
            tier="P1",
            selector="button[data-asset-finance-trend-metal]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="篩選單一金屬序列(app.js:24452-24458)",
        ),
        Step(
            id="precious-metals__volume-symbol",
            tier="P1",
            selector="button.asset-finance-etf-select[data-asset-finance-volume-symbol]",
            action="click",
            action_index=0,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換ETF圖表+個股分析文字(app.js:26179)",
        ),
    ),
)


DERIVATIVES_ASSETS = PageSpec(
    file="derivatives-assets.html",
    render_only=True,
    steps=(
        Step(
            id="derivatives-assets__render",
            tier="P0",
            selector="#asset-hub-root",
            action=None,
            # 裁決紀錄第2點:本頁因 renderAssetHubPage() 在 !isFinanceMode 時提早
            # return 到 renderDerivativesMarketOverview(),沒有真正的狀態變更
            # 控制項(其餘皆為純導航連結,P2),改用渲染型 P0:斷言主要內容區塊
            # (文字卡片與導航卡)載入後非空。
            asserts=(a_min_count("#asset-hub-root .asset-hub-nav-card", 1),),
            note="頁面載入→renderDerivativesMarketOverview() 渲染文字卡片與導航卡(app.js:28488-28726)",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Batch 5:儀表板/渲染型 + 剩餘互動頁
# ---------------------------------------------------------------------------

DERIVATIVES_ANALYTICS = PageSpec(
    file="derivatives-analytics.html",
    render_only=False,
    steps=(
        Step(
            id="derivatives-analytics__strategy-select",
            tier="P0",
            selector="[data-strategy-select]",
            action="select",
            action_value=None,
            wait_for=wait_stable("#derivatives-strategy-detail"),
            asserts=(
                a_min_count("#derivatives-analytics-root .panel-card", 1),
                a_min_count("#derivatives-analytics-market-state .derivatives-market-state-value", 1),
                a_content_changed("#derivatives-strategy-detail"),
                a_min_count("#derivatives-strategy-detail .derivatives-strategy-detail-title", 1),
            ),
            note="頁面載入完成後切換第2個策略→驗證13策略選擇器與實際腿／fail-closed明細渲染",
        ),
    ),
)


DERIVATIVES_STATUS = PageSpec(
    file="derivatives-status.html",
    render_only=True,
    steps=(
        Step(
            id="derivatives-status__render",
            tier="P0",
            selector="#derivatives-status-root",
            action=None,
            # 裁決紀錄第2點:本頁零互動控制項(derivatives-ui.js 純資料展示),
            # 改用渲染型P0:斷言hero/統計格/目錄表/AI分數卡載入後非空。
            asserts=(a_min_count("#derivatives-status-root .panel-card", 1),),
            note="頁面載入→derivatives-ui.js 抓 /api/derivatives/v1-status 渲染狀態頁(derivatives-ui.js:73)",
        ),
    ),
)


DERIVATIVES_AI = PageSpec(
    file="derivatives-ai.html",
    render_only=True,
    steps=(
        Step(
            id="derivatives-ai__redirect",
            tier="P0",
            selector="body",
            action=None,
            # 純轉址頁:initDerivativesAiPage() 執行 window.location.replace(...),
            # 頁面載入後應已完整導航到目的地(HTML <meta refresh> 亦同時存在,
            # 兩者競速執行同一目的地,見 TD-15 佐證清單#5)。
            asserts=(a_url_matches("**/derivatives-analytics.html#derivatives-analytics-market-state"),),
            note="頁面載入(load)→window.location.replace 導向衍生品市場狀態與策略分析區(app.js:33518-33520)",
        ),
    ),
)


INDEX = PageSpec(
    file="index.html",
    steps=(
        Step(
            id="index__selection-funnel-sector",
            tier="P0",
            selector="#selection-funnel-root [data-selection-sector]",
            action="click",
            action_index=1,
            wait_for=wait_stable("#selection-funnel-root"),
            asserts=(
                a_class_present("is-active"),
                a_content_changed("#selection-funnel-root"),
            ),
            note="Phase B: 選取既有淨流入排序的下一個類股→候選宇宙改為該類股既有 TOP10。",
        ),
        Step(
            id="index__penny-trend-market",
            tier="P0",
            selector="#penny-trend-controls [data-home-penny-market]",
            action="click",
            # index=0 是預設市場(上市),無早退判斷但重複點選同一市場會產生
            # 逐位元組相同的重渲染結果。
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="裁決升級為P0(互動型):切換銅板股市場分頁→重渲染卡片網格與摘要文字(app.js:4117-4122)",
        ),
    ),
)


MARKET_OVERVIEW = PageSpec(
    file="market-overview.html",
    steps=(
        Step(
            id="market-overview__sector-flow-mode",
            tier="P0",
            selector="#sector-fund-flow [data-sector-flow-mode]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="裁決升級為P0(互動型):切換類股資金流向模式(app.js:306,365-370)",
        ),
        Step(
            id="market-overview__sector-ranking-group",
            tier="P1",
            selector="#market-sector-ranking [data-market-sector-ranking-group]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="切換排行市場群組(app.js:2311)",
        ),
        Step(
            id="market-overview__sector-sort",
            tier="P1",
            # 注意:#sector-sort-slot 包裝是 renderSectorPageV2()(tw-stocks.html)
            # 專屬的,renderMarketPage() 這裡的 select 沒有外層 .sector-sort-slot
            # 容器(實測 closest('[id]') 回傳自己),直接用裸 id 選取。
            selector="#sector-sort-select",
            action="select",
            wait_for=wait_stable("#market-sector-ranking"),
            asserts=(a_value_changed(None),),
            note="依所選指標重新排序表格列(app.js:2603-2606)",
        ),
    ),
)


# news.html 與 market-overview.html 分派完全相同(同一 data-page="market" →
# renderMarketPage()),互動介面逐位元組相同(見 interaction_inventory.md
# TD-15 佐證清單#12),故沿用同一組 Step 定義,只換 file。
NEWS = PageSpec(
    file="news.html",
    steps=MARKET_OVERVIEW.steps,
)


US_MARKET_OVERVIEW = PageSpec(
    file="us-market-overview.html",
    steps=(
        Step(
            id="us-market-overview__global-refresh",
            tier="P0",
            # 注意:此頁走 renderUsMarketOverviewLikeTaiwan() 專屬渲染路徑(因
            # data-market-view="overview"),global-refresh 按鈕位在
            # .market-institution-card(#us-market-overview 的手足區塊,不在其
            # 內部),實測 `#us-market-overview [data-global-refresh]` 選不到。
            selector="[data-global-refresh]",
            action="click",
            wait_for=wait_response("**/api/global-market/us-stocks**"),
            asserts=(a_content_changed("#global-market-root"),),
            note="重新整理→全頁重新抓取+重渲染(app.js:34132-34137;本頁非衍生品分類,"
            "與futures.html不同,此控制項確實存在)",
        ),
        Step(
            id="us-market-overview__sector-ranking-group",
            tier="P1",
            selector="[data-us-market-sector-ranking-group]",
            action="click",
            action_index=1,
            wait_for=wait_class("is-active"),
            asserts=(a_class_present("is-active"),),
            note="重渲染排行子清單(S&P500 vs 產業群組)(app.js:19964-19969)",
        ),
        Step(
            id="us-market-overview__sector-sort",
            tier="P1",
            selector="[data-us-market-sector-sort]",
            action="select",
            wait_for=wait_stable("#us-market-overview"),
            asserts=(a_value_changed(None),),
            note="重新排序排行清單(app.js:19970-19973)",
        ),
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
    TW_OPTIONAL_STOCKS,
    US_WATCHLIST,
    BONDS,
    INTERNATIONAL_FINANCE,
    PRECIOUS_METALS,
    DERIVATIVES_ASSETS,
    DERIVATIVES_ANALYTICS,
    DERIVATIVES_STATUS,
    DERIVATIVES_AI,
    INDEX,
    MARKET_OVERVIEW,
    NEWS,
    US_MARKET_OVERVIEW,
)


def get_page_spec(file: str) -> PageSpec:
    for spec in PAGES:
        if spec.file == file:
            return spec
    raise KeyError(f"no PageSpec registered for {file}")
