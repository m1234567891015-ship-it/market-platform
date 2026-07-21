# 前端互動路徑盤點 (工單00B 第一部分)

依 `docs/工單00B_前端行為護欄.md` 第一部分要求,逐頁掃描 21 個 HTML 頁面 + app.js,
盤點所有互動控制項(addEventListener 綁定的 click/change/input/submit、inline handler、
form/select/input[type=search]、可排序表頭、分頁控制項),並依「使用者實際會做」的
重要性分級為 P0(必測)/ P1(應測)/ P2(選測)。

**P0 定義(依裁決更新,見文末「裁決紀錄」)**:P0 = 該頁核心功能路徑,分兩型——
(a) **互動型**:點擊/輸入後 DOM 正確反應;(b) **渲染型**:頁面載入後關鍵容器有實質內容
(表格有列、卡片有數值、圖表有繪製)。純唯讀儀表板頁(無任何 addEventListener)改用渲染型
P0 佐證,而非強行指定不存在的互動控制項。

**方法**:由 3 組平行 Explore agent 分別對 7 頁進行程式碼實證盤點(讀取實際 HTML 與
app.js 綁定程式碼,確認元素真的被插入 DOM、確認 addEventListener 呼叫確實存在),
再由本文件彙整。每一列都可追溯到 app.js 的實際行號。

---

## 全頁 data-page 對應表

| HTML 檔案 | `data-page` | 其他判別屬性 | 進入點(app.js) |
|---|---|---|---|
| bonds.html | `asset-hub` | `data-asset-hub-mode="bonds"` | `initAssetHubPage()` (28886) |
| derivatives-ai.html | `derivatives-ai` | — | `initDerivativesAiPage()` (33518) + HTML meta-refresh,純轉址頁 |
| derivatives-analytics.html | `derivatives-analytics` | — | `initDerivativesAnalyticsPage()` (33377) |
| derivatives-assets.html | `asset-hub` | `data-asset-hub-mode="derivatives"` | `initAssetHubPage()` (28886) → 因非 finance/bonds/precious-metals 模式,提早 return 到 `renderDerivativesMarketOverview()` |
| derivatives-status.html | `derivatives-status` | — | **不經過 `renderCurrentPage()`**,由 `derivatives-ui.js` 自己的 `DOMContentLoaded` IIFE 渲染 |
| futures.html | `global-market` | `data-market-category="futures"` | `initGlobalMarketPage(false)` (20709) → 因 `isDerivativePage` 為 true,走 `renderDerivativesFuturesSinglePage` |
| index.html | `home` | — | `renderCurrentPage()` branch 34074 → `renderHome()` (4177) |
| international-finance.html | `asset-hub` | `data-asset-hub-mode="finance"` | `initAssetHubPage()` (28886),financeView="combined" |
| market-overview.html | `market` | — | `renderMarketPage()` (5081)。**與 news.html 共用同一 data-page** |
| news.html | `market` | — | 同上,`renderMarketPage()`。**與 market-overview.html 互動介面完全相同** |
| options.html | `global-market` | `data-market-category="options"` | `initGlobalMarketPage()` (20709) → `renderDerivativesSinglePageContent()` → `renderOptionsAiFunctionalPage()` |
| precious-metals.html | `asset-hub` | `data-asset-hub-mode="precious-metals"` | `initAssetHubPage()` (28886),financeView="metals"(是 international-finance.html 的子集) |
| tw-etf.html | `tw-etf` | — | `initTwEtfPage()` → `loadTwEtfPage()` (33981) |
| tw-Optional-stocks.html | `watchlist` | — | `initWatchlistPage()` (8843)。⚠ 檔名與 data-page 不一致 |
| tw-stock-search.html | `search` | — | `initSearchPage()` (33189),不經過 `renderCurrentPage()` 分派 |
| tw-stocks.html | `sectors` | — | `renderSectorPageV2()` (2530)。⚠ 檔名與 data-page 不一致 |
| us-etf.html | `us-etf` | — | `initUsEtfPage()` (12266) |
| us-market-overview.html | `global-market` | `data-market-category="us-stocks"` `data-market-view="overview"` | `initGlobalMarketPage(false)` → `renderUsMarketOverviewLikeTaiwan()`,因 `data-market-view` 提早 return |
| us-stock-search.html | `us-stock-search` | — | `initUsStockSearchPage()` (22271) |
| us-stocks.html | `global-market` | `data-market-category="us-stocks"`(無 `data-market-view`) | `initGlobalMarketPage(false)` → 走一般分支(`renderUsMajorIndexVixCard` 等)。**與 us-market-overview.html 共用 data-page + data-market-category,僅靠 data-market-view 有無區分** |
| us-watchlist.html | `us-watchlist` | — | `initUsWatchlistPage()` (22989) |

---

## bonds.html

`data-asset-hub-mode="bonds"` 使 `initAssetHubPage()` 抓 `GET /api/global-market/bonds?limit=all`,
再呼叫 `renderAssetHubPage()` → 因 `view==="bonds"`,只渲染 `renderAssetFinanceBondsResearchSection()`
(排除貴金屬/交叉參照區塊)。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `[data-bond-yield-focus]`(7 個殖利率按鈕) | click | `initAssetFinanceBondFocusControls` app.js:27881-27889 | 切換殖利率焦點,更新下方 AI 評論文字,按鈕 active 狀態切換 | 否(用已載入 payload 重渲染) | P1 |
| `[data-bond-etf-bucket]`(8 個 ETF 分類) | click | `initAssetFinanceBondFocusControls` app.js:27890-27898 | 重渲染債券 ETF 表格與訊號卡 | 否 | **P0** |
| `[data-asset-finance-volume-symbol]`(ETF 表格內「選取」按鈕) | click | `initAssetFinanceVolumeSelectors` app.js:26211-26213 | 切換 24 日趨勢圖 + 個股 AI 分析面板 | 否(用內嵌 JSON) | P1 |
| `.asset-finance-volume-hover-zone` | mouseenter/mousemove/mouseleave | `bindAssetFinanceVolumeCursor` 26218-26269 | 顯示/隱藏 SVG 十字準線與提示框 | 否 | P2 |
| `.asset-hub-nav-card`(純連結) | click | 無 handler,純 `<a>` | 導航到其他頁面 | n/a | P2 |

## derivatives-ai.html

**純轉址頁,無實際功能。**

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| 頁面本體(load) | load | HTML `<meta http-equiv="refresh">` **同時** `initDerivativesAiPage()` app.js:33518-33520 `window.location.replace(...)` | 完整導航至 derivatives-analytics.html#derivatives-ai-section | 否 | **P0**(這就是本頁唯一功能:轉址) |
| 備援 `<a>` 連結 | click | 無 | 導航 | 否 | P2 |

無任何表單/按鈕/select。

## derivatives-analytics.html

`initDerivativesAnalyticsPage()` 發出 8 個平行請求(TXO options chain、PCR、法人籌碼、
基差、AI 分析 ×2、新聞),組出一整串 `root.innerHTML`,**之後未呼叫任何 bind/init controls 函式**。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| — | — | 無(已逐一核對每個 addEventListener 呼叫點,均不落在本頁 13 個渲染函式內;app.js 全檔亦無 `onclick=`) | — | — | — |
| `#root` 主要資料區塊(load) | load | `initDerivativesAnalyticsPage()` 8個平行API請求後組出 `root.innerHTML` | TXO 選擇權鏈表格、PCR 卡片、法人籌碼卡片、基差卡片等關鍵容器載入後非空(有列/有數值) | 是(頁面載入時的8個平行請求) | **P0**(裁決新增,渲染型) |

**本頁零互動控制項**,純唯讀儀表板;依裁決紀錄第2點改用渲染型 P0 佐證。

## derivatives-assets.html

與 bonds.html 相同進入點,但 `data-asset-hub-mode="derivatives"` 使 `isFinanceMode` 為 false,
在 `renderAssetHubPage()` 提早 return 到 `renderDerivativesMarketOverview()`
——該函式全文只有純文字卡片與 2 個 `<a>` 導航卡,無任何 button/select/data-* 控制屬性。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `a.asset-hub-nav-card[href="futures.html"]` | click | 無(純連結) | 導航到 futures.html | 否 | P2 |
| `a.asset-hub-nav-card[href="options.html"]` | click | 無 | 導航到 options.html | 否 | P2 |
| `a.global-refresh`(「查看完整分析」×2) | click | 無 | 導航 | 否 | P2 |
| `#root` 主要內容區塊(load) | load | `renderDerivativesMarketOverview()` | 文字卡片與導航卡載入後非空(至少有標題+說明文字) | 否 | **P0**(裁決新增,渲染型) |

**本頁無真正的狀態變更控制項**——所有本應存在的 asset-hub 控制項(`[data-asset-load-more]`、
`[data-tw-option-expiry-select]`、`initAssetFinanceTrendSwitchers` 等)因提早 return 而成為死碼。

## derivatives-status.html

由獨立的 `derivatives-ui.js`(85 行 IIFE)渲染,**不經過 app.js 的 `renderCurrentPage()`**。
`init()` 抓 `GET /api/derivatives/v1-status`,注入 hero + 統計格 + 2 張目錄表 + AI 分數公式卡。
全檔無 button/select/input/addEventListener。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| — | — | 無 | — | — | — |
| 頁面主體(load) | load | `derivatives-ui.js` IIFE `init()` 抓 `/api/derivatives/v1-status` | hero 區塊、統計格、2張目錄表、AI 分數公式卡載入後非空 | 是 | **P0**(裁決新增,渲染型) |

**本頁零互動控制項**,純唯讀狀態頁;依裁決紀錄第2點改用渲染型 P0 佐證。

## futures.html

`data-market-category="futures"` → `initGlobalMarketPage(false)` 抓 `/api/futures`,因
`isDerivativePage` 為 true,走 `renderDerivativesFuturesSinglePage()` = `renderFuturesAnalysisCenter`
+ `renderDerivativesFuturesPanel`,渲染後呼叫 `bindDerivativesFuturesPanel` + `bindDerivativeWatchlistControls`。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `[data-global-refresh="futures"]`(委派於 document) | click | app.js:34132-34137 → `initGlobalMarketPage(true)` | 全頁重新抓取+重渲染 | 是 — `GET /api/futures?limit=all&refresh=1` | **P0** |
| `[data-futures-framework-scope]`(台灣/美國/國際) | click | `bindDerivativesFuturesPanel` 19013-19020 | 切換投資框架分頁 | 否 | P1 |
| `[data-futures-detail-scope]` | click | 19021-19036 | 切換詳細面板市場範圍與預設商品 | 否 | P1 |
| `[data-futures-detail-symbol]`(合約晶片,如 TX/MTX/ES=F) | click | 19037-19043 | 切換單一合約詳情/圖表面板 | 否 | **P0**(主要合約選擇器) |
| `[data-futures-region-toggle]` | click | 19044-19055 | 展開/收合區域群組 | 否 | P2 |
| `[data-asset-region-toggle="futures-regional-market"]` | click | 19056-19063 | 重渲染區域市場區塊 | 否 | P2 |
| `[data-futures-technical-contract-code]` | click | 19064-19072 | 切換 TAIFEX 合約月份 | 否(隨後由 hydrate 請求) | P1 |
| `[data-futures-technical-interval]`(日/週/月) | click | 19073-19081 | 切換 K 線週期 | 否 | P1 |
| `[data-futures-indicator-view]` | click | 19082-19090 | 切換 MA / 其他指標視圖 | 否 | P2 |
| `[data-futures-chart-ma]`(MA5/10/20/60/120/240) | click | 19091-19102 | 切換均線疊圖 | 否 | P1 |
| `[data-futures-chart-indicator]`(布林/斐波那契/支撐壓力/SMC) | click | 19103-19114 | 切換疊圖指標 | 否 | P1 |
| `[data-futures-panel-indicator]` | click | 19115-19126 | 切換下方面板指標(至少保留1個) | 否 | P2 |
| `[data-futures-chart-zoom]` | click | 19127-19161 `updateFuturesChartZoom` | 改變可視 K 棒範圍 | 否 | P1 |
| `[data-futures-chart-pan]` | click | 19143-19164 `updateFuturesChartPan` | 平移可視範圍 | 否 | P1 |
| `.sector-chart-frame` | wheel | 19170-19174 | 滾輪縮放 | 否 | P2 |
| chart frame | pointerdown/up/cancel | `bindHorizontalChartPan` 29006-29029 | 拖曳平移圖表 | 否 | P2 |
| `.sector-chart-frame` hover zones | pointerenter/move/leave, focus/blur | `bindChartHover`(19166 綁定) | 顯示十字準線+OHLC提示 | 否 | P2 |
| (非點擊,自動觸發) | — | `hydrateDerivativesFuturesCandles` 18962-19009,於 `bindDerivativesFuturesPanel` 結尾(19176)及合約/週期切換後的重渲染循環觸發 | 將 TAIFEX 官方 K 線資料填入圖表 | 是 — `GET /api/futures/{symbol}/technical-candles?code=...&interval=...` | **P0** |
| `[data-derivative-watch-symbol]`(加入/移除自選) | click | `bindDerivativeWatchlistControls` 13365-13387 | 切換 localStorage 自選,更新按鈕文字 | 否(僅 localStorage) | P1 |

## index.html

`data-page="home"` → `renderHome()`,注入靜態文字/卡片(資料來自 `loadLiveData()` 60 秒輪詢),
並呼叫 `renderHomePennyTrend()` + `loadHomePennySectorRecommendations()`。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `#penny-trend-controls [data-home-penny-market]`(上市/上櫃/興櫃) | click | app.js:4117-4122 | 切換「銅板股推薦」卡片網格與摘要文字 | 否(用已載入 payload 重渲染) | **P0**(裁決升級,互動型) |
| `a.penny-trend-top-row` | click | 無(純連結) | 導航到 tw-stock-search.html | 否 | P2 |
| `a.btn-primary` / `a.link-card`(5張) | click | 無 | 導航到其他頁面 | 否 | P2 |

**P0 裁決**:本頁原無控制項達到「壞了等於該頁廢掉」的嚴格標準,依裁決紀錄第2點,將現有最高階
控制項——銅板股市場分頁切換器——升級為 P0(互動型)。

## international-finance.html

`data-asset-hub-mode="finance"` → `financeView="combined"`,渲染 nav cards + 核心儀表板
(靜態)+ 貴金屬研究區 + 交叉參照區塊(靜態,無控制項)。債券相關控制項不屬本模式。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `a.asset-hub-nav-card`(貴金屬/債券導覽卡) | click | 無(純連結/錨點捲動) | 捲動至區塊或導航到 bonds.html | 否 | P2 |
| `[data-asset-finance-trend-range="1m"/"3m"/"6m"/"1y"]`(國際貴金屬走勢圖) | click | `initAssetFinanceTrendSwitchers` app.js:24397 | 重繪趨勢圖、更新狀態文字與預測面板 | 否(用內嵌 JSON) | **P0** |
| `[data-asset-finance-trend-metal="all"/"gold"/"silver"/"platinum"/"palladium"]` | click | 同上 handler | 篩選單一金屬序列(資料點<2時停用) | 否 | P1 |
| `button.asset-finance-etf-select[data-asset-finance-volume-symbol]` | click | `initAssetFinanceVolumeSelectors` app.js:26179 | 切換 ETF 圖表 + 個股分析文字 | 否 | P1 |

## market-overview.html

`data-page="market"` → `renderMarketPage()`(5081)。所有子面板皆以 id 選取,與 news.html 完全相同。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `button[data-sector-flow-mode="inflow"/"outflow"/"all"]`(`#sector-fund-flow`內) | click | `renderSectorFundFlow()` app.js:306 | 重渲染面板,僅顯示流入/流出/全部類股列 | 否 | **P0**(裁決升級,互動型) |
| `button[data-market-sector-ranking-group="listed"/"otc"/"emerging"]`(`#market-sector-ranking`內) | click | `renderMarketListedSectorRanking()` app.js:2310 | 重建對應市場群組的排行表 | 否 | P1 |
| `select#sector-sort-select[data-sector-sort]` | change | 同上函式 | 依所選指標重新排序表格列 | 否 | P1 |

**P0 裁決**:依裁決紀錄第2點,將現有最高階控制項——類股資金流向模式切換
(`data-sector-flow-mode`)——升級為 P0(互動型),因其為本頁主面板的主要篩選機制。
其餘可見內容多為 `<a>` 導航連結(股票/類股名稱連向 tw-stock-search.html / tw-stocks.html),
不計入控制項列表。

## news.html

與 market-overview.html 分派完全相同(同一 `data-page="market"` → `renderMarketPage()`),
兩頁的 id 完全一致,故互動介面**逐位元組相同**。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `button[data-sector-flow-mode="inflow"/"outflow"/"all"]` | click | `renderSectorFundFlow()` app.js:306 | 同 market-overview.html | 否 | **P0**(裁決升級,互動型) |
| `button[data-market-sector-ranking-group="listed"/"otc"/"emerging"]` | click | `renderMarketListedSectorRanking()` app.js:2310 | 同上 | 否 | P1 |
| `select#sector-sort-select[data-sector-sort]` | change | 同上 | 同上 | 否 | P1 |

**P0 裁決**:與 market-overview.html 相同(兩頁互動介面逐位元組相同),類股資金流向模式切換
升級為 P0(互動型)。

## options.html

`data-market-category="options"` → `isDerivativePage=true`,實際 DOM 只來自
`renderOptionsAiFunctionalPage()`(`renderOptionsHeroDashboard` + `renderOptionsMarketWorkbench`)。
**`renderDerivativesOptionsPanel()` 被計算但從未插入 DOM**——多個 selector 因此死碼(見下方彙整)。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `tr[data-options-chain-strike]`(TAIFEX TXO 鏈表格 + 公開市場鏈表格,role=button) | click / keydown Enter/Space | `bindDerivativesOptionsPanel` selectStrike app.js:19347-19360 | 選取列加上 `.is-selected`,下方插入 OI/履約價 AI 摘要列 | 否 | **P0** |
| `button[data-options-focus-key]`(市場選擇權鏈 地區/分類 分頁) | click | `bindDerivativesOptionsPanel` 19464-19498 | 切換選擇的標的,重渲染商品清單+摘要+鏈表格 | 是 — `/api/options/chain?underlying=...&source=...` 或 `/api/us-market/options-chain/{symbol}` | **P0** |
| `select[data-options-market-expiration-select]` | change | 19416-19439 → `fetchOptionsMarketChainPayload()` | 重渲染鏈表格+OI摘要 | 是 — `/api/us-market/options-chain/{symbol}?expiration=...` | P1 |
| `button.options-strategy-button[data-options-strategy-key]` | click | 19456-19463 | 顯示對應策略的證據/風險文字 | 否 | P1 |
| `button[data-asset-load-more]`(「載入更多已驗證行情」) | click | `bindDerivativeAssetLoadMore` app.js:18937 | 按鈕文字變更後全頁重渲染,擴大項目上限 | 是 — `/api/options?limit={n}` | P2 |

**本頁死碼控制項(勿當作可運作路徑測試)**:`[data-options-chain-source]`(從未渲染出對應 UI)、
`[data-tw-option-product]`/`[data-derivative-watch-symbol]`(只存在於從未插入的 `renderDerivativesOptionsPanel`
輸出中)、`[data-asset-option-underlying]`(`renderOptionsUsChainCard()` 在到達自己模板前就 `return ""`,
100% 不可達)、`[data-asset-region-toggle="options-regional-market"]`(唯一實例被
`.options-hero-regional-market.is-hidden{display:none}` 硬編碼隱藏,無任何 JS 會清除)。

## precious-metals.html

與 international-finance.html 相同機制,但 `financeView="metals"`,只渲染 nav cards +
`renderAssetFinanceMetalsResearchSection()`(無核心儀表板、無交叉參照、無債券區塊)——
互動介面是 international-finance.html 的**子集**。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `a.asset-hub-nav-card` | click | 無(純連結) | 捲動或完整頁面導航 | 否 | P2 |
| `button[data-asset-finance-trend-range="1m"/"3m"/"6m"/"1y"]` | click | `initAssetFinanceTrendSwitchers` app.js:24397 | 同 international-finance.html | 否 | **P0** |
| `button[data-asset-finance-trend-metal=...]` | click | 同上 | 同上 | 否 | P1 |
| `button.asset-finance-etf-select[data-asset-finance-volume-symbol]` | click | `initAssetFinanceVolumeSelectors` app.js:26179 | 同上 | 否 | P1 |

## tw-etf.html

`initTwEtfPage()` → `loadTwEtfPage()` 抓 `/api/twse/etfs?...` → `renderTwEtfPage()` →
`bindTwEtfEvents()`。**注意**:`renderTwEtfPage()` 自建一份 filter form 後立即刪除,
真正生效的是 `.tw-etf-list-toolbar` 內由 `renderTwEtfFilterForm()` 產生的第二份同 id 副本
(見下方彙整,測試須指定該範圍)。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `input#tw-etf-query[type=search]`(`.tw-etf-list-toolbar` 內) | input(送出時讀值) | 由 `run()` 於表單送出時讀取 | 見下方 submit 列 | — | **P0** |
| `select#tw-etf-category` | change | `bindTwEtfEvents()` app.js:33893,立即呼叫 `run()` | 依分類重渲染清單+分頁 | 是 — `/api/twse/etfs?...&category=...` | **P0** |
| `select#tw-etf-sort` | change | 同上 33894 | 依指標重新排序清單 | 是 — `/api/twse/etfs?...&sort=...` | P1 |
| `form#tw-etf-filter-form`(「篩選」送出) | submit | 33889-33892,`preventDefault()` + `run()` | 依 query+category+sort 重建清單,保留捲動位置 | 是 — `/api/twse/etfs?q=...&category=...&sort=...` | **P0** |
| `select#tw-etf-page-size` | change | 33895-33899 | 依新頁面大小重切表格與分頁(純前端) | 否 | P2 |
| `button[data-tw-etf-page="first"/"prev"/"next"/"last"]` | click | `setTwEtfPage()` 33671 | 更新分頁標籤與表格列(對已載入資料切片) | 否 | P1 |
| `button.tw-etf-detail-button[data-tw-etf-detail]`(每列「查看」) | click | 33903-33915 → `loadTwEtfDetail()` 33965 | `#tw-etf-detail` 替換為 ETF 分析/持股/配息卡片 | 是 — `/api/twse/stock/{code}?market=...` | **P0** |

## tw-Optional-stocks.html

`initWatchlistPage()` → `renderWatchlist()` + `renderPortfolioSimulator()`。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `#watchlist-analysis-refresh` | click | `loadWatchlistAiAnalyses(true)` app.js:8726 | 各卡片 AI 建議/理由隨串流更新 | 是 — per-stock detail fetch | **P0** |
| `.watchlist-card[data-watchlist-detail-url]`(role=link,tabindex=0) | click / keydown Enter/Space | app.js:8699-8713 `window.location.href` | 完整導航到 tw-stock-search.html?... | 否 | **P0** |
| `button.watchlist-remove[data-watchlist-remove]` | click | 8715-8723 | 從 localStorage 移除,重渲染清單,更新統計/狀態文字 | 否 | P1 |
| `a.watchlist-detail-link`(純連結) | click | 無 | 導航 | 否 | P2 |
| `input[type=number][data-portfolio-field="entryPrice"]` | change | 5707-5718 | 重算並重渲染整個模擬器摘要與表格 | 否 | **P0** |
| `input[type=number][data-portfolio-field="shares"]` | change | 同上 | 同上 | 否 | **P0** |
| `input[type=number][data-portfolio-field="stopLossPct"]` | change | 同上 | 同上(含停損風險金額/riskLabel) | 否 | P1 |
| `input[type=number][data-portfolio-field="takeProfitPct"]` | change | 同上 | 同上 | 否 | P1 |
| `#portfolio-simulator-reset` | click | 清除 storage 後重渲染 | 重設為預設值(進場價=現價、股數=0、停損8%/停利15%) | 否 | P1 |

## tw-stock-search.html

`initSearchPage()`。搜尋框/結果清單獨立於共用 `data`/`renderCurrentPage` 機制。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `#stock-search-form` | submit | app.js:33195 → `runStockSearch(query)` 33139 | `#search-results` 替換為結果按鈕,`#search-status` 更新 | 是 — `GET /api/twse/live-search?q=` | **P0** |
| `#stock-search-input` | input(去抖 600ms) | 33205 | 同上;query 為空時清空結果 | 是(非空時) | **P0** |
| `#search-results [data-code]`(每個結果按鈕) | click | 8880-8898 | 標記 `.is-active`,更新 URL,呼叫 `loadStockDetail()` 33047 | 是 — `GET /api/twse/stock/{code}?refresh=1&quick=1` | **P0** |
| `#stock-detail [data-stock-watchlist-toggle]` | click | 32188-32198 | 切換按鈕文字/`.is-added`,更新狀態文字 | 否(僅 localStorage) | P1 |
| `#stock-detail [data-interval]`(日/週/月線) | click | 32477-32487 | 切換 active 樣式,重渲染技術圖表 | 條件式 — 週/月資料不足時補抓 history | **P0** |
| `#stock-detail [data-ma-period]`(MA5/10/20/60/120/240) | click | 32497-32509 | 切換均線疊圖 | 條件式(同上) | P1 |
| `#stock-detail [data-chart-indicator]`(布林/斐波那契/支撐壓力/SMC) | click | 32511-32524 | 切換疊圖指標 | 條件式 | P1 |
| `#stock-detail [data-panel-indicator]` | click | 32526-32539 | 切換下方面板指標(至少保留1個) | 條件式 | P2 |
| `#stock-detail [data-stock-zoom]` | click | 32489-32491 → `updateStockZoom()` | 改變可視K棒數,更新縮放狀態文字 | 視情況 | P1 |
| `#stock-detail [data-stock-pan]` | click | 32493-32495 → `updateStockPan()` | 平移可視範圍 | 視情況 | P2 |
| `.sector-chart-frame` | wheel | 32395-32403 | 滾輪縮放+水平平移綁定 | 視情況 | P2 |
| `#stock-detail [data-institution-period]` | click | 32200-32207 | 重渲染新法人週期 | 否 | P2 |
| `#stock-detail [data-institution-range]`(6m/1y等) | click | 32209-32276 | 重渲染法人買賣超區塊,保留捲動位置 | 是,僅 range∈{6m,1y} | P1 |
| `#stock-detail [data-margin-range]`/`[data-margin-summary-mode]`/`[data-margin-table-type]`/`[data-margin-period]` | click | 32278-32328 | 設定 Map 狀態鍵,重渲染 | 否 | P2 |
| `#stock-detail [data-institution-series]` | click | 32330-32343 | 切換法人序列圖例顯示(至少保留1個) | 否 | P2 |
| `#stock-detail [data-chip-tab]` | click | 32345-32352 | 切換籌碼子分頁 | 否 | P2 |

## tw-stocks.html ⚠(data-page 實際為 "sectors",與檔名不符)

`renderSectorPageV2()` + `renderWeightedIndexPanel()`。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `.class-tabs [data-category]`(動態產生,取代 HTML 原生的6個靜態 span) | click | 2597-2602 | 設定 activeCategory,`renderSectorPageV2()` 全頁重渲染 | 視情況(Yahoo來源類別可能觸發載入) | **P0** |
| `#sector-sort-slot [data-sector-sort]`(select) | change | 2603-2606 | 重渲染排行表 | 否 | P1 |
| `#class-links [data-yahoo-sector-group][data-yahoo-sector-index]`(電子產業/概念股等子分類) | click | 委派於 document,34138-34143 → `loadYahooSectorCategory()` 1849 | 抓取/快取子分類報價,重渲染全頁 | 是 | P1 |
| `#class-links a.class-stock-link`(純連結) | click | 無 | 完整頁面導航 | 否 | P2 |
| `#sector-sync-view [data-sector-source-select]`(select) | change | `bindSectorSyncControls` 2448-2457 | 切換比較圖顯示的類股 | 視快取情況 | **P0** |
| `#sector-sync-view [data-retry-sector-chart]` | click | 2471-2477 | 重試 Yahoo 圖表抓取 | 是 | P2 |
| `#sector-sync-view [data-comparison-zoom]`/`[data-comparison-pan]` | click | 2500-2519 | 縮放/平移比較圖 | 否 | P2 |
| `.sector-chart-frame`(sync view) | wheel | 2523-2527 | 同上縮放 | 否 | P2 |
| `#weighted-index-panel [data-weighted-mode]`(日/週/月/指數比對) | click | 3976-3981 | 切換加權指數圖表模式,重渲染整個面板 | 否(資料已載入) | **P0** |
| `#weighted-index-panel [data-international-key]` | click | 3982-3991 | 切換比較圖顯示的指數線(多選) | 否 | P1 |
| `#weighted-index-panel [data-weighted-chart-zoom]`/`[data-weighted-chart-pan]` | click | 3992-4024 | 縮放/平移加權指數圖 | 否 | P2 |
| `.sector-chart-frame`(weighted panel) | wheel | 4024-4027 | 同上縮放 | 否 | P2 |

## us-etf.html

`initUsEtfPage()` 抓 `/api/us-market/etf-center?directoryLimit=7000&quoteLimit=56` →
`renderUsEtfPage()`。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `form[data-us-nyse-search-form="etf"]`(搜尋input+分類select+排序select+「篩選」) | submit | `bindUsNyseDirectoryControls` 12787-12802 | 重設頁碼,呼叫 `loadUsNyseDirectory("etf")` | 是 — `GET /api/us-market/etf-center?...&q=` | **P0** |
| `[data-us-nyse-page-size="etf"]`(select) | change | 12818-12827 | 依新頁面大小重渲染表格(前端切片) | 否 | P1 |
| `[data-us-nyse-page="etf"][data-page=...]`(分頁first/prev/next/last) | click | 12850-12865 | 更新 `#us-nyse-etf-table` | 否 | **P0** |
| `[data-us-etf-detail]`(每列「查看」) | click | 12829-12839 | 捲動並填入 `#us-etf-detail` | 是 — `loadUsEtfDetail()` 11614 | **P0** |
| `.us-etf-hot-item`/比較表內連結(純連結) | click | 無 | 完整頁面導航 | 否 | P2 |
| 圖表 hover zones | mouseenter/mousemove/mouseleave | `bindChartHover`(12263 綁定) | 僅提示框/十字準線 | 否 | P2 |

## us-market-overview.html

`initGlobalMarketPage(false)` → `renderUsMarketOverviewLikeTaiwan()` + `bindUsMarketOverviewControls()`。
因 20601 提早 return,**不會**得到 `renderUsMajorIndexVixCard`/`renderUsSectorIndexComparisonCard`/
`renderUsSectorStocksBrowser`(那些屬於 us-stocks.html)。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `[data-global-refresh]`(「重新整理」) | click | 委派於 document,34132-34137 → `initGlobalMarketPage(true)` | 全頁重新抓取+重渲染 | 是 — `/api/global-market/us-stocks?refresh=1&limit=all` | **P0** |
| `[data-us-market-sector-ranking-group]` | click | `bindUsMarketOverviewControls` 19964-19969 | 重渲染排行子清單(S&P500 vs 產業群組) | 否 | P1 |
| `[data-us-market-sector-sort]`(select) | change | 19970-19973 | 重新排序排行清單 | 否 | P1 |
| 圖表 hover zones | mouseenter/mousemove/mouseleave | `bindChartHover`(20706) | 僅提示框 | 否 | P2 |

## us-stock-search.html

`initUsStockSearchPage()`。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `#us-stock-search-form` | submit | 22277-22285 → `runUsStockSearch(query, true)` 22235 | 填入 `#us-search-results`,更新狀態文字與 URL | 是 — `GET /api/us-market/search?q=` | **P0** |
| `#us-stock-search-input` | input(去抖 300ms) | 22287-22297 | 同上 | 是 | **P0** |
| `#us-search-results .us-result-main-button[data-us-symbol]` | click | 22198-22204 | 標記結果為 active,呼叫 `loadUsStockSymbol()` 22207 | 是 — `GET /api/us-market/symbol/{symbol}` | **P0** |
| `#us-stock-detail [data-us-stock-watchlist-toggle]` | click | 22140-22145 | 切換按鈕標籤/樣式,寫入 localStorage | 否 | P1 |
| `#us-stock-detail [data-us-interval]`(日/週/月線) | click | 21983-21991 | 切換週期,重渲染圖表(資料已內嵌) | 否 | **P0** |
| `#us-stock-detail [data-us-ma-period]` | click | 21992-21999 | 切換均線疊圖 | 否 | P1 |
| `#us-stock-detail [data-us-chart-indicator]` | click | 22001-22009 | 切換疊圖指標 | 否 | P1 |
| `#us-stock-detail [data-us-panel-indicator]` | click | 22010-22019 | 切換下方面板指標 | 否 | P2 |
| `#us-stock-detail [data-us-stock-zoom]` | click | 22021-22023 | 改變可視範圍 | 否 | P1 |
| `#us-stock-detail [data-us-stock-pan]` | click | 22024-22033 | 平移可視範圍 | 否 | P2 |
| `.sector-chart-frame` | wheel | 21965-21968 | 滾輪縮放 | 否 | P2 |
| `#us-stock-detail [data-us-chip-tab]` | click | 22146-22164 | 切換基本面/籌碼/新聞子面板 | 否 | P2 |
| 外部連結(Yahoo Finance) | click | 無 | 開新分頁 | 外部導航 | P2 |

## us-stocks.html(與 us-market-overview.html 共用 data-page,靠 `data-market-view` 有無區分)

`initGlobalMarketPage(false)` 走一般分支(20613-20707)。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `#us-market-overview [data-global-refresh]` | click | 委派於document,34132-34137 | 全頁重新抓取+重渲染 | 是 — `/api/global-market/us-stocks?refresh=1&limit=all` | **P0** |
| `#us-major-index-vix [data-us-major-index]`(S&P/Dow/Nasdaq/Russell) | click | `bindUsMajorIndexVixCard` 9783-9801 | 多選指數圖表線(ctrl/shift疊加) | 否 | **P0** |
| `#us-major-index-vix [data-us-major-index-all]`(全選) | click | 9802-9808 | 全選/取消四大指數 | 否 | P1 |
| `#us-major-index-vix [data-us-vix-toggle]` | click | 9809-9812 | 切換VIX疊圖 | 否 | P1 |
| `#us-major-index-vix [data-us-index-zoom]`/`[data-us-index-pan]` | click | 9838-9843 | 縮放/平移指數圖 | 否 | P2 |
| `.us-index-vix-chart-wrap` | wheel | 9844+ | 滾輪縮放 | 否 | P2 |
| `#us-sector-index-comparison [data-us-sector-benchmark]` | click | `bindUsSectorIndexComparisonCard` 10272-10277 | 切換比較基準,重渲染卡片 | 否 | **P0** |
| `#us-sector-index-comparison [data-us-sector-index]` | click | 10278-10283 | 切換比較的類股 | 否 | **P0** |
| `.us-sector-compare-chart-wrap` | wheel/mouseenter/mousemove | 10284+ | 提示框+縮放 | 否 | P2 |
| `#us-sector-stock-browser [data-us-sector-stock]` | click | `bindUsSectorStocksBrowser` 12710-12758 | 切換基準或類股;若role=benchmark則替換整個瀏覽器區塊並重新綁定 | 是 — `loadUsSectorStocks()` | **P0** |
| `#us-sector-stock-browser form[data-us-sector-nyse-search-form]` | submit | 12759-12765 | 設定查詢字串,重設頁碼 | 是 | **P0** |
| `#us-sector-stock-browser [data-us-sector-nyse-reset]` | click | 12766-12772 | 清空輸入/查詢 | 是 | P1 |
| `#us-sector-stock-browser [data-us-sector-nyse-page]`(first/prev/next/last) | click | 12773-12783 | 分頁(前端切片) | 否 | **P0** |
| 圖表 hover zones | mouseenter/mousemove/mouseleave | `bindChartHover`(20706) | 僅提示框 | 否 | P2 |

## us-watchlist.html

`initUsWatchlistPage()`。

| selector | trigger_event | handler_summary | expected_dom_impact | fires_api_request | tier |
|---|---|---|---|---|---|
| `#us-watchlist-analysis-refresh` | click | 22991-22993 → `loadUsWatchlistAiAnalyses(true)` 22551 | 清除AI快取,串流更新摘要與各卡片AI區塊 | 是 — 每檔 `GET /api/us-market/symbol/{symbol}` | **P0** |
| `#us-portfolio-simulator-reset` | click | 22994-22997 | 清除模擬器 storage,重渲染為預設值 | 否 | P1 |
| `#us-watchlist-grid [data-us-watchlist-detail-url]`(整張卡片,role=link) | click / keydown Enter/Space | 22664-22678 `window.location.href` | 完整導航到 us-stock-search.html?symbol=... | 否 | **P0** |
| `#us-watchlist-grid [data-us-watch-remove]` | click | 22679-22688 | 從localStorage移除,重渲染網格,更新狀態文字 | 否 | **P0** |
| `#us-portfolio-simulator-table [data-us-portfolio-field]`(entryPrice/shares/stopLossPct/takeProfitPct) | change | 22893-22902 | 寫入storage,重渲染模擬器(重算損益/風險指標) | 否 | P1 |

**本頁死碼(見彙整)**:`#us-watchlist-results`/`#us-watchlist-detail` 永遠不會被填入內容
——`renderUsWatchlistSearchResults()`/`runUsWatchlistSearch()` 從未被呼叫,頁面上也沒有對應的搜尋表單。

---

## 彙整:發現的異常/死碼(依硬性規則第1條,僅記錄不修復;已登錄為 TD-15,見 docs/TD稽核清單.md)

1. **market-overview.html 與 news.html 是功能上的重複頁面**:兩者 `data-page="market"` 完全相同,
   `renderMarketPage()` 只以 id 選取元素,而兩頁定義的 id 完全一致——互動介面(及所抓取的資料)
   逐位元組相同。針對一頁寫的測試等同涵蓋另一頁。
2. **tw-Optional-stocks.html 檔名與 `data-page`("watchlist")不符**,是本次盤點中唯一一個檔名
   完全對不上任何 data-page 或 data-*-mode 判別值的頁面。
3. **tw-stocks.html 的 `data-page` 實際是 `"sectors"`**,與檔名不符。
4. **derivatives-analytics.html 零互動控制項**:已逐一核對其呼叫的13個渲染函式,均不含
   addEventListener;純唯讀儀表板(8個平行API請求後即完成)。
5. **derivatives-assets.html 零真正狀態變更控制項**:`renderAssetHubPage()` 在
   `!isFinanceMode` 時提早 return 到 `renderDerivativesMarketOverview()`,導致本應存在的
   `initAssetFinanceTrendSwitchers`/`initAssetFinanceVolumeSelectors`/`initAssetFinanceBondFocusControls`
   及多個 click handler 全部綁定成功但目標元素從未出現在DOM——是死碼而非本頁功能。
6. **derivatives-status.html 零互動控制項**,且**每60秒無謂輪詢一次不相關端點**:
   `renderCurrentPage()` 的排除清單(app.js:34146)未包含 `"derivatives-status"`,
   導致本頁意外落入 TWSE dashboard 的 `loadLiveData()` 輪詢分支,抓到的資料無處使用即被丟棄。
   非明顯錯誤,但屬浪費流量的潛在風險。
7. **derivatives-ai.html 重複轉址機制**:HTML `<meta refresh>` 與 JS 的
   `window.location.replace()` 同時存在,兩者競速執行同一目的地,非錯誤但寫測試時應斷言最終
   URL,而非本頁本身渲染任何內容。
8. **options.html 約5-6個死碼/不可達互動元素**,全因 `renderGlobalMarketPage()` 計算的
   `derivativesHtml`(來自 `renderDerivativesOptionsPanel`)在 `category==="options"` 分支下
   從未被插入DOM:`[data-options-chain-source]`(無對應UI)、`[data-tw-option-product]`、
   `[data-derivative-watch-symbol]`(僅存在於未插入的輸出中)、`[data-asset-option-underlying]`
   (`renderOptionsUsChainCard()` 提早 `return ""`,100%不可達)、地區市場切換
   (`.options-hero-regional-market.is-hidden` 被CSS硬編碼隱藏且無JS清除)。
9. **tw-etf.html 渲染出重複的篩選表單並丟棄其中一份**:`renderTwEtfPage()` 自行產生一份
   `#tw-etf-filter-form` 後立刻將其所在 `.section` 移除;真正生效的是巢狀在
   `.tw-etf-list-toolbar` 內、由 `renderTwEtfFilterForm()` 產生的第二份同id副本。功能正常,
   但測試須鎖定 `.tw-etf-list-toolbar #tw-etf-query` 等範圍選擇器,不可假設裸id唯一。
10. **us-stocks.html 與 us-market-overview.html 共用 `data-page="global-market"` +
    `data-market-category="us-stocks"`**,唯一區分靠 `data-market-view="overview"` 是否存在
    (app.js:20597 單一布林值分岔)。兩頁render tree完全不同(互不共用任何控制項),Playwright
    selector策略若僅以 `body[data-page="global-market"]` 選取需額外檢查 `data-market-view`。
11. **us-watchlist.html 的搜尋/詳情流程是死碼**:`renderUsWatchlistSearchResults()` /
    `runUsWatchlistSearch()` 定義但從未被呼叫,頁面也無對應搜尋表單。導致 `#us-watchlist-results`
    與 `#us-watchlist-detail` 永久留空,靜態文案「點選自選股卡片後,這裡會顯示個股詳情」與實際
    行為不符——實際行為是完整頁面導航到 us-stock-search.html。
12. **tw-stocks.html 有一段死碼舊版比較視圖**:`renderSectorSyncView()`(含其
    `[data-sector-source]`/`[data-sync-mode]` 按鈕)從未被 `renderSectorPageV2()`/
    `renderSectorGroup()` 呼叫,只被自己內部的handler互相引用,對本頁完全不可達
    (實際使用的是 `renderSectorSyncViewV2()`)。
13. **us-etf.html 的ETF分類快速篩選晶片是死碼**:`renderUsEtfCategoryFilters()` 只被
    `renderUsNyseDirectoryTable(kind, payload)` 在 `kind !== "etf"` 的分支引用,但ETF頁面
    `kind==="etf"` 會提早return到 `renderUsEtfDirectoryTable`,故容器id
    `us-nyse-etf-category-filters` 從未出現在實際DOM,對應的 `bindUsNyseDirectoryControls`
    click分支也隨之不可達。
14. **`renderDerivativeAssetSummarySection`(app.js:18910-18916)完全是死碼**——定義但全檔
    無任何呼叫處。
15. **兩個貴金屬/國際金融渲染路徑的次要死碼訊號**(優先度較低,非使用者可見):
    `renderAssetFinanceInternationalTrendPanel()` 定義但從未被呼叫;`renderAssetHubMetals()`
    是永遠回傳空字串的stub。
16. 全檔案(app.js)確認**零個 inline `onclick=` handler**——所有21頁的互動介面皆透過
    addEventListener綁定,驗證了「不得憑猜測設計測試」要求的必要性,也正是找出上述死碼的方法。

---

## 裁決紀錄:每頁至少1條P0 的下限與實際盤點結果的張力(已解決)

工單第51行要求「每頁至少1條P0路徑,21頁合計不少於25條」。原始盤點的6個零P0頁面缺口,
已依使用者裁決處理如下(對應本文件上方已套用的修訂):

1. **P0 定義修正**:P0 = 該頁核心功能路徑,分兩型——(a) 互動型:點擊/輸入後 DOM 正確反應;
   (b) 渲染型:頁面載入後關鍵容器有實質內容(表格有列、卡片有數值、圖表有繪製)。
2. **6個零P0頁面補上**:
   - index.html / market-overview.html / news.html:現有最高階控制項提升為 P0(互動型)——
     index.html 為銅板股市場分頁切換器,market-overview.html / news.html 為類股資金流向模式切換。
   - derivatives-analytics.html / derivatives-status.html / derivatives-assets.html:
     改用渲染型 P0,斷言主要資料區塊載入後非空。
   - derivatives-ai.html:P0 維持「導向 derivatives-analytics.html#derivatives-ai-section」不變。
3. **死碼與失效控制項**:全部登錄為 [TD-15](../docs/TD稽核清單.md)(前端死碼與失效控制項),
   本工單(00-B)不修復。其中 options.html 的 `[data-asset-option-underlying]`
   (`renderOptionsUsChainCard()` 提早 `return ""`,100%不可達,使用者看得到、點得到但無反應)
   在 TD-15 中標為最高優先。
4. **執行時間**:42+6=48 條 P0 若使全套超過 5 分鐘,將 P2 改為選用(`--interactions-full`
   才跑),P0+P1 為預設套件。

裁決來源:指令5.md(使用者確認紀錄)。derivatives-assets.html 的死碼(控制項因
`renderAssetHubPage()` 提早 return 而全數不可達)已併入 TD-15,不另立工單。

在您確認前,我不會建立 `regression/interaction_check.py` 或動到第二部分之後的任何工作。
