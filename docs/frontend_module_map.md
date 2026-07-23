# 前端模組地圖(工單 TD-02 第一部分:依賴盤點與切片計畫)

來源:對 `app.js`(34,149 行)做 AST 層級靜態分析(acorn,非正則猜測),
以實際 `data-page`/`data-market-category` 派發結構為準,反推每個頂層符號
真正被哪些頁面使用,而非照抄工單表格的假設。分析工具與中間產物存放於
本次對話的暫存目錄,不隨此文件提交進 repo。

**這是盤點文件,不是搬移紀錄。本文件完成後停下回報,搬移(第二部分起)
需使用者明確確認後才開始,依 `工單TD02_前端拆分.md` 的硬性規則第 1 點。**

---

## 0. 摘要:與工單表格假設不同的地方

依實際呼叫圖分析,有 4 項發現會影響原工單第 4 節的目標模組表,依重要性排序:

### 發現①:`app.js` 不是「單一 IIFE」

工單與 `docs/TD稽核清單.md`(TD-02 債項描述)都稱 app.js 為「單一 IIFE」,
但實測檔案開頭到結尾都是最外層(column 0)的 `let`/`const`/`function` 宣告,
**沒有** `(function(){ ... })()` 包裹。這是透過經典 `<script src="app.js">`
(非 `type="module"`,非 `defer` 包裝)以「classic script 全域作用域」共享
狀態,不是字面上的 IIFE。對本工單的實務影響很小(共享作用域的風險與因應
方式不變,見工單第 2 節),但文件用詞不精確,寫在這裡供未來稽核核對用。

### 發現②:`global-market` 是單一進入點,橫跨工單表格的 page-us.js 與 page-derivatives.js

`futures.html`、`options.html`、`us-market-overview.html`、`us-stocks.html`
四個頁面的 `data-page` 全部是 `"global-market"`,共用同一個
`initGlobalMarketPage()` → `renderGlobalMarketPage()` 進入點,內部依
`document.body.dataset.marketCategory`(`futures`/`options`/`us-stocks`)
分流。工單表格把「global-market(us)」歸進 `page-us.js`、「futures、options」
歸進 `page-derivatives.js`,但這兩組其實是**同一個函式的呼叫者**,在
「禁止拆分函式」的硬性規則下無法乾淨地分屬兩個檔案。

### 發現③:asset-hub 與 derivatives-analytics/-ai 跟 global-market 雙向互相呼叫

繼續往下追可達性,發現 `bonds.html`/`derivatives-assets.html`/
`international-finance.html`/`precious-metals.html`(`data-page="asset-hub"`)
以及 `derivatives-analytics.html`/`derivatives-ai.html` 跟 global-market
也不是單向依賴,而是雙向呼叫,例如:

- `renderFuturesCenterRegionalMarket`(global-market)呼叫
  `getAssetHubItems`/`renderAssetHubQuoteGrid`(asset-hub)
- `renderAssetHubFallbackPage`(asset-hub)呼叫
  `buildGlobalMarketInsight`/`renderGlobalMarketSections`(global-market)

這不是分類誤判——逐一核對原始碼確認兩個方向的呼叫都是真實存在的函式呼叫。
在不切割既有函式的前提下,這 7 個頁面(futures/options/us-market-overview/
us-stocks/asset-hub 四頁/derivatives-analytics/derivatives-ai)**必須合併
成同一個目標檔案**,本文件稱為 `js/page-global-market.js`,取代工單表格
原本 `page-us.js`/`page-derivatives.js` 對應的這一部分。`page-us.js` 縮小為
只剩 `us-stock-search`/`us-etf`/`us-watchlist`。styles.css 的類別前綴統計
(見第 6 節)也呈現同一群集(`asset-finance`/`options`/`futures`/
`derivatives`/`asset-hub` 合計超過 2,000 處),與 JS 側發現互相印證。

### 發現④:無法從任何已知進入點到達的頂層符號有 98 個,遠多於 TD-15 已知的 16-17 項

TD-15(前端死碼與失效控制項)是透過工單 00-B 的互動測試盤點手動發現
16 項死碼/失效控制項。本次用靜態呼叫圖分析(從 14 個頁面進入點 + `main`
bootstrap 尾端程式碼出發做可達性分析)發現 **98 個頂層符號**(91 個函式 +
7 個狀態變數)完全無法從任何已知進入點到達,且排除了 CSP 禁止 inline
onclick、無 `window[...]` 動態字串派發等常見的「隱藏呼叫點」可能性後,
仍然找不到呼叫者。例如 `renderVixSentimentRules`、`searchStocksLocally`、
`fetchClientInstitutionalTradeHistory`、`runWatchlistSearch` 等,函式本身
完整、命名正常,但全檔案搜尋不到任何呼叫點。

**這不是本工單要處理的問題**(硬性規則第 4 點:發現新問題只記錄不修)。
這些符號一樣會被搬移(不刪除),依命名啟發式給出「暫定」模組歸屬,但信心
標記為 low,遷移該批次前建議先用 grep 或執行期監控確認實際呼叫情形。
是否要擴大 TD-15 的範圍或另開工單追蹤,留待使用者裁決;本文件第 8 節
附上完整清單供後續參考。

### 附帶發現:`derivatives-status.html` 有獨立的第三支 script

21 個 HTML 頁面中,只有 `derivatives-status.html` 額外載入
`derivatives-ui.js`(85 行,獨立檔案,不在本工單範圍內)。它的
`data-page="derivatives-status"` 在 app.js 的 `renderCurrentPage()` 派發
邏輯中完全沒有對應分支,代表它的頁面邏輯主要活在 `derivatives-ui.js`,
不在 app.js 內。搬移 app.js 時不會影響這個頁面的獨立腳本,但提醒一併確認
`derivatives-ui.js` 是否也該在未來某個工單一併處理。

---

## 1. 方法論

1. 用 acorn 把 app.js 解析成 AST,擷取所有頂層(script 作用域)的
   `function` 宣告與 `let`/`const`/`var` 宣告,共 959 個符號
   (818 個函式 + 141 個狀態變數),另有 7 個頂層非宣告陳述式
   (bootstrap 尾端派發區塊 + 1 個 IIFE 安全防護)。
2. 對每個函式符號,走訪其函式本體 AST,找出所有參照到「其他頂層符號」的
   識別字,同時追蹤區域變數/參數遮蔽(避免把同名的區域變數誤判成依賴),
   建立完整呼叫圖(A 依賴 B = A 的函式體內用到 B)。
3. 從 21 個 HTML 頁面實際的 `data-page`/`data-market-category` 屬性
   反推出 14 組「頁面群組 → 進入點函式」對照(不是照抄工單表格,是重新
   驗證過的),對每組做 BFS 找出可達的全部頂層符號。
   - `renderCurrentPage()`(全站唯一派發器,呼叫全部 14 個頁面進入點)
     設為 BFS 邊界節點:算「被呼叫方可達」,但不繼續展開它自己的依賴,
     否則任何會呼叫 `loadLiveData()`(進而呼叫 `renderCurrentPage()`)的
     頁面都會「可達」全部 959 個符號,污染分類訊號。
   - `renderStockDetail`/`loadInstitutionalTradeHistoryIfNeeded` 另外
     單獨做一次 BFS(不算獨立頁面群組),用來判斷 stock-detail 的
     專屬子函式,跟工單第 5 節「renderStockDetail 獨立成一批次」的
     設計對齊。
4. 依可達性 + 命名啟發式(規則詳列於分析腳本,均以具體函式名或命名前綴
   為準,不是模糊比對)把 959 個符號分類到目標模組。信心分三級:
   - **high**:只被單一頁面群組可達,直接對應該頁的目標模組。
   - **medium**:被 2 個以上頁面群組共用,依命名/呼叫對象歸類到
     core/state/api/charts/render-shared/shared-calc 等共用層。
   - **low**:完全無法從任何已知進入點到達(發現④),用命名啟發式猜測,
     遷移前需人工核實。
5. 計算「目標模組」之間的有向邊,做循環依賴檢查,發現的循環全部逐一
   點名實際函式對、重新歸類到正確模組後消除(過程見第 0 節發現②③)。
   **最終模組依賴圖(下方第 2 節)不含任何循環**,只有一個已核實安全的
   例外(見第 2 節末段說明)。
6. 依循環依賴檢查得出的拓撲順序,在每個模組內部依「工單第 5 節」的
   單批上限(60 函式或 3,000 行)切批次,批次內依原始行號排序(相鄰程式
   碼盡量同批,降低單批次內部語意跳躍)。

---

## 2. 最終模組依賴圖(拓撲順序,無循環)

```
state → core → api → shared-calc → render-shared → charts → stock-detail
  → page-home ┐
  → page-us   ├→ page-tw → main
  → page-global-market ┘
```

模組間依賴邊(A → B 表示 A 用到 B 的符號,已消除所有循環):

```
api                 → core
charts              → core, render-shared, shared-calc, state
core                → state
page-global-market  → api, charts, core, render-shared, shared-calc, state
page-home           → api, charts, core, render-shared, state
page-tw             → api, charts, core, main, render-shared, shared-calc, state, stock-detail
page-us             → api, charts, core, render-shared, shared-calc, state, stock-detail
render-shared       → api, core, shared-calc, state
shared-calc         → core, state
stock-detail        → api, charts, core, render-shared, shared-calc, state
main                → api, core, page-global-market, page-home, page-tw, page-us, state
```

**一個已核實安全、刻意不消除的例外**:`page-tw` 的 `initWatchlistPage`
直接呼叫 `main` 模組的 `loadLiveData()`(不只是透過 bootstrap 尾端的
`setInterval` 間接觸發)。這在模組依賴圖上會畫出 `page-tw → main` 的邊,
跟 `main → page-tw`(`renderCurrentPage` 派發到 `initWatchlistPage`)
方向相反,形成表面上的循環。但這條邊**不影響實際載入順序**,因為:
`initWatchlistPage` 只是在函式「本體」裡引用 `loadLiveData`,不是在
`page-tw.js` 的頂層(立即執行)程式碼引用——只要 `js/main.js` 是最後一個
`<script>` 標籤(依上面拓撲順序,它本來就該最後載入),等使用者實際
觸發 watchlist 頁面互動、呼叫到 `initWatchlistPage` 的當下,全部
`<script>` 標籤早已載入完畢,`loadLiveData` 一定已存在。**這條邊符合
工單第 2 節第 4 點「載入順序即依賴順序」的精神(main.js 本來就該最後載入),
不需要任何額外處理**,寫在這裡是為了讓下一步做 HTML script 標籤排序時,
不會誤以為這是要修的問題。

---

## 3. 批次計畫(依上面拓撲順序切分,單批 ≤ 60 函式或 ≤ 3,000 行)

**實際需要 22 個批次,超出工單原本估計的 8-12 批。** 主因是發現②③
合併後的 `page-global-market` 模組單獨就有 370 個符號、14,141 行
(佔全檔 34,149 行的 41%),需要 7 個批次才能切完;工單原本的 8-12 批
估計是在不知道這個合併結果的情況下寫的。是否接受 22 批、或者要另外
討論縮小合併範圍(例如允許重複少量小函式以換取更小的批次數,但這會
違反硬性規則「禁止複製多份」,不建議),留待使用者裁決。

| 批次 | 目標模組 | 符號數 | 函式數 | 行數 | 範圍(依行號排序後首末) |
|---|---|---|---|---|---|
| 1 | js/state.js | 151 | 10 | 459 | `data` ~ `assetFinanceTrendChartCounter` |
| 2 | js/core.js | 26 | 26 | 167 | `toneClass` ~ `formatChartDate` |
| 3 | js/api.js | 4 | 4 | 80 | `buildTwseInstitutionTradeUrl` ~ `fetchWithTimeout` |
| 4 | js/shared-calc.js(新增) | 54 | 54 | 2921 | `normalizePortfolioHistory` ~ `calculateFuturesParabolicSar` |
| 5 | js/shared-calc.js(新增,續) | 18 | 18 | 427 | `buildFuturesTechnicalSnapshot` ~ `calculateIchimoku` |
| 6 | js/render-shared.js | 46 | 46 | 1257 | `renderSharedNavigation` ~ `twEtfWeightText` |
| 7 | js/charts.js | 10 | 10 | 909 | `renderSectorLineChart` ~ `bindChartHover` |
| 8 | js/stock-detail.js | 10 | 10 | 2859 | `buildFallbackStockDetail` ~ `getStockDetailCacheKey`(含 `renderStockDetail` 本體 2,512 行) |
| 9 | js/page-home.js | 33 | 33 | 1204 | `formatSectorFundFlowAmount` ~ `renderMarketPage` |
| 10 | js/page-us.js | 60 | 60 | 2624 | `getUsEtfCategoryLabel` ~ `runUsStockSearch` |
| 11 | js/page-us.js(續) | 6 | 6 | 334 | `initUsStockSearchPage` ~ `initUsVolumeMomentumCursor` |
| 12 | js/page-global-market.js(新增) | 60 | 60 | 2809 | `renderMiniLineChart` ~ `renderFuturesInvestmentLiveDataPanel` |
| 13 | js/page-global-market.js(續) | 60 | 60 | 1938 | `renderFuturesInvestmentFramework` ~ `getOptionsFocusItems` |
| 14 | js/page-global-market.js(續) | 60 | 60 | 1825 | `getOptionsActiveFocus` ~ `bindDerivativeAssetLoadMore` |
| 15 | js/page-global-market.js(續) | 60 | 60 | 2053 | `hydrateDerivativesFuturesCandles` ~ `renderAssetHubQuoteGrid` |
| 16 | js/page-global-market.js(續) | 60 | 60 | 2121 | `renderAssetHubSummary` ~ `renderAssetFinanceVolumeTrendChart` |
| 17 | js/page-global-market.js(續) | 57 | 57 | 2852 | `getAssetFinanceVolumePayloadItem` ~ `renderDerivativesMarketOverview` |
| 18 | js/page-global-market.js(續,末) | 13 | 13 | 543 | `renderAssetHubPage` ~ `initDerivativesAiPage` |
| 19 | js/page-tw.js | 60 | 60 | 2288 | `getWeightedIndexSector` ~ `renderWeightedSectorThemeContext` |
| 20 | js/page-tw.js(續) | 51 | 51 | 1885 | `renderWeightedSectorTrendRecommendationCard` ~ `initTwEtfPage` |
| 21 | (暫不歸類,見發現④) | 58 | 58 | 1614 | `normalizeStockSearchTerm` ~ `renderTwEtfSummary`,遷移前逐一核實 |
| 22 | js/main.js | 2 | 2 | 88 | `renderCurrentPage`、`loadLiveData`,另加 bootstrap 尾端 7 段非宣告陳述式(見第 5 節) |

批次 21(unclassified)建議獨立處理,不硬塞進其他批次的順序中——每個
符號遷移前先個別確認實際呼叫情形(或確認是死碼,決定歸屬模組但不刪除),
不能像其他批次一樣整批直接搬。

---

## 4. `renderStockDetail` 拆解(工單第 5 節要求列出內部分段結構)

`renderStockDetail`(app.js:30029-32540,2,512 行)+
`loadInstitutionalTradeHistoryIfNeeded`(678-733,56 行)的完整依賴閉包
共 120 個符號,扣掉被其他頁面群組共用的技術指標計算(如 `calculateRsi`/
`calculateMacd`,這些正確留在 shared-calc,不隨 stock-detail 搬),
stock-detail 專屬的有 10 個(見第 8 節模組符號表 js/stock-detail.js)。
`renderStockDetail` 本體內部粗略分段(依函式體內部結構觀察,不是獨立
函式,只是同一個 2,512 行函式內的邏輯區塊,供未來若要進一步拆分時參考,
本工單不執行任何拆分):

- 資料整理/防呆(fallback 資料建構、快取鍵計算)
- 技術指標面板渲染(呼叫 shared-calc 一大批 `calculate*`/`technical*`)
- 法人籌碼/融資融券分頁渲染
- 事件綁定(watchlist 收藏切換、圖表游標互動)

---
## 5. `main` 模組:bootstrap 尾端(不是具名符號,單獨列出)

app.js 最後 21 行(34129-34149)是 7 段頂層非宣告陳述式,執行順序即定義
順序,不能重排:

```js
renderSharedNavigation();
if (document.body.dataset.page === "search") initSearchPage();
if (document.body.dataset.page === "watchlist") initWatchlistPage();
document.addEventListener("click", (event) => { /* 全域點擊委派:
  data-global-refresh → initGlobalMarketPage(true)
  data-yahoo-sector-group/-index → loadYahooSectorCategory(...) */ });
renderCurrentPage();
if (![...9 個排除頁面].includes(document.body.dataset.page)) {
  loadLiveData();
  setInterval(loadLiveData, ...);
}
```

另外開頭 208-224 行有一個獨立 IIFE `enforceSafeInnerHtml()`(安全防護,
鎖定 `innerHTML` 存取以強制走 `escapeHtml`),依內容屬性歸類到
`js/core.js`,不屬於 main 的 bootstrap 尾端,已計入第 8 節 core 符號表。

---

## 6. `styles.css`(21,972 行)簡化版盤點

依工單第 4 節說明「選用/簡化版」,不做逐 selector 的呼叫圖分析(CSS
沒有函式呼叫關係,只有類別字串比對,精確追蹤到頁面的成本效益比 JS 低
很多),改用類別前綴粗略統計,佐證第 0 節發現③的合併建議:

| 前綴 | 出現次數 | 對應目標 CSS 分層 |
|---|---|---|
| `asset-finance-` | 722 | css/page-global-market.css |
| `options-` | 518 | css/page-global-market.css |
| `futures-` | 431 | css/page-global-market.css |
| `derivatives-` | 300 | css/page-global-market.css |
| `sector-` | 230 | css/page-tw.css |
| `institution-` | 118 | 跨頁共用(stock-detail + page-global-market 都有),需個別核對 |
| `asset-hub-` | 104 | css/page-global-market.css |
| `backtest-` | 101 | 跨頁共用(shared-calc 對應的視覺呈現) |
| `vix-` | 73 | 跨頁共用(page-home + page-global-market) |
| `technical-` | 72 | css/stock-detail.css + css/page-global-market.css,需個別核對 |
| `watchlist-` | 60 | css/page-tw.css |
| `portfolio-` | 52 | 跨頁共用(watchlist + us-watchlist) |
| `tw-etf-` | 47 | css/page-tw.css |
| `chart-` | 38 | css/charts.css |
| `us-etf-` | 143 | css/page-us.css |
| `nav-` | 11 | css/components.css(共用導覽) |
| `us-watchlist-`/`us-stock-` | 11 | css/page-us.css |
| `stock-detail-` | 3 | css/stock-detail.css |
| `bond-`/`precious-metal-` | 0 | 未找到獨立前綴,實際併在 `asset-finance-` 命名下 |

`asset-finance-`/`options-`/`futures-`/`derivatives-`/`asset-hub-` 五者
合計 2,075 處,佔已辨識前綴總數的最大宗,與 JS 側「page-global-market
是最大合併模組」的結論互相印證。`bond-`/`precious-metal-` 沒有獨立
前綴,代表這兩個資產類別的樣式是併在通用的 `asset-finance-` 命名空間下,
不是獨立區塊,這點在切分 CSS 檔案時要注意——不能簡單依「頁面」切,
要跟著 JS 那邊「asset-hub 併入 page-global-market」的結論一起處理。

**建議**:CSS 的實際切分(建立 `docs/css_split_map.md` 或併入本文件)
留到 Part 2 實際搬移該批次時再做精確盤點(每次只搬一批,只需要那一批
涉及的 CSS 規則,不需要一次全部盤點完),原因跟 `bond-`/`precious-metal-`
沒有獨立前綴一樣——CSS 的規則邊界模糊,提前做整體精確盤點的性價比低,
遷移到 render-shared/page-* 批次的當下針對該批次涉及的 HTML class 現查
現核對更準確。

---

## 7. 依賴閉包驗證(交叉檢查)

- `renderStockDetail` 閉包:120 個符號(含技術指標計算共用層)。
- `initGlobalMarketPage`+`renderAssetHubPage` 等 page-global-market 進入點
  閉包:370 個符號,是全部 14 個頁面群組中最大的一組,佔全檔案函式總數
  約 45%。
- 全部 21 頁的 P0+P1 互動測試基準(工單 00-B,93 步驟)在本次分析
  期間沒有被觸碰,`regression/interaction_check.py --compare` 未執行
  於本次盤點(純靜態分析,無需啟動伺服器),Part 2 每批次搬移後仍依
  工單既有規範跑。

---

## 8. 完整符號分類表(依模組分組,模組內依行號排序)


### js/state.js

151 個符號(函式 10、狀態 141),共 459 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `data` | state | 1-1 | 1 | high |  |
| `localAllStocks` | state | 2-2 | 1 | high |  |
| `activeStockCode` | state | 3-3 | 1 | high |  |
| `activeStockMarket` | state | 4-4 | 1 | high |  |
| `activeRenderedStockDetail` | state | 5-5 | 1 | high |  |
| `stockDetailRequestId` | state | 6-6 | 1 | high |  |
| `stockSearchRequestId` | state | 7-7 | 1 | high |  |
| `yahooSectorQuoteCache` | state | 8-8 | 1 | high |  |
| `yahooSectorChartLoading` | state | 9-9 | 1 | high |  |
| `yahooSectorChartErrors` | state | 10-10 | 1 | high |  |
| `activeYahooSectorCategories` | state | 11-11 | 1 | high |  |
| `activeYahooSectorStocks` | state | 12-12 | 1 | high |  |
| `activeYahooSectorModes` | state | 13-13 | 1 | low |  |
| `defaultYahooSectorCategoryAttempts` | state | 14-14 | 1 | high |  |
| `sectorComparisonZoomCounts` | state | 15-15 | 1 | high |  |
| `sectorComparisonPanOffsets` | state | 16-16 | 1 | high |  |
| `sectorSortState` | state | 17-17 | 1 | high |  |
| `marketSectorRankingState` | state | 18-18 | 1 | high |  |
| `sectorFundFlowState` | state | 19-19 | 1 | high |  |
| `usMarketSectorRankingState` | state | 20-20 | 1 | high |  |
| `assetFinanceBondFocusKey` | state | 21-21 | 1 | high |  |
| `assetFinanceBondEtfBucketKey` | state | 22-22 | 1 | high |  |
| `SECTOR_SYNC_PICKER_LIMIT` | state | 23-23 | 1 | high |  |
| `yahooSectorRequestId` | state | 24-24 | 1 | high |  |
| `WATCHLIST_STORAGE_KEY` | state | 25-25 | 1 | high |  |
| `US_WATCHLIST_STORAGE_KEY` | state | 26-26 | 1 | high |  |
| `PORTFOLIO_SIM_STORAGE_KEY` | state | 27-27 | 1 | high |  |
| `US_PORTFOLIO_SIM_STORAGE_KEY` | state | 28-28 | 1 | high |  |
| `MARKET_BREADTH_STORAGE_KEY` | state | 29-29 | 1 | high |  |
| `watchlistAnalysisCache` | state | 30-30 | 1 | high |  |
| `watchlistDetailCache` | state | 31-31 | 1 | high |  |
| `usWatchlistAnalysisCache` | state | 32-32 | 1 | high |  |
| `usWatchlistDetailCache` | state | 33-33 | 1 | high |  |
| `stockSearchCache` | state | 34-34 | 1 | low |  |
| `stockDetailCache` | state | 35-35 | 1 | low |  |
| `stockDetailPending` | state | 36-36 | 1 | low |  |
| `stockFullDetailCache` | state | 37-37 | 1 | high |  |
| `stockFullDetailPending` | state | 38-38 | 1 | high |  |
| `internationalIndexesPromise` | state | 39-39 | 1 | high |  |
| `homePennySectorPayload` | state | 40-40 | 1 | high |  |
| `homePennySectorPromise` | state | 41-41 | 1 | high |  |
| `homePennySectorMarket` | state | 42-42 | 1 | high |  |
| `stockInstitutionHistoryCache` | state | 43-43 | 1 | high |  |
| `stockInstitutionHistoryPending` | state | 44-44 | 1 | high |  |
| `stockInstitutionRangeHistoryCache` | state | 45-45 | 1 | high |  |
| `stockShareholderCache` | state | 46-46 | 1 | high |  |
| `stockShareholderPending` | state | 47-47 | 1 | high |  |
| `stockInstitutionPeriodState` | state | 48-48 | 1 | high |  |
| `stockInstitutionRangeState` | state | 49-49 | 1 | high |  |
| `stockInstitutionSeriesState` | state | 50-50 | 1 | high |  |
| `stockMarginRangeState` | state | 51-51 | 1 | high |  |
| `stockMarginSummaryModeState` | state | 52-52 | 1 | high |  |
| `stockMarginTableTypeState` | state | 53-53 | 1 | high |  |
| `stockMarginPeriodState` | state | 54-54 | 1 | high |  |
| `stockChipTabState` | state | 55-55 | 1 | high |  |
| `liveStockDirectoryPromise` | state | 56-56 | 1 | low |  |
| `liveStockDirectoryLoaded` | state | 57-57 | 1 | low |  |
| `watchlistAnalysisRequestId` | state | 58-58 | 1 | high |  |
| `usWatchlistAnalysisRequestId` | state | 59-59 | 1 | high |  |
| `twEtfPayload` | state | 60-60 | 1 | high |  |
| `twEtfSelectedCode` | state | 61-61 | 1 | high |  |
| `TW_ETF_DEFAULT_PAGE_SIZE` | state | 62-62 | 1 | high |  |
| `TW_ETF_PAGE_SIZE_OPTIONS` | state | 63-63 | 1 | high |  |
| `twEtfState` | state | 64-70 | 7 | high |  |
| `usMajorIndexChartSymbol` | state | 71-71 | 1 | high |  |
| `usMajorIndexChartSymbols` | state | 72-72 | 1 | high |  |
| `usMajorIndexShowVix` | state | 73-73 | 1 | high |  |
| `usMajorIndexZoomCounts` | state | 74-74 | 1 | high |  |
| `usMajorIndexPanOffsets` | state | 75-75 | 1 | high |  |
| `usSectorCompareSymbol` | state | 76-76 | 1 | high |  |
| `usSectorBenchmarkSymbol` | state | 77-77 | 1 | high |  |
| `usSectorStockBenchmarkSymbol` | state | 78-78 | 1 | high |  |
| `usSectorStockSymbol` | state | 79-79 | 1 | high |  |
| `usSectorNyseStockState` | state | 80-87 | 8 | high |  |
| `US_SECTOR_STOCK_SELECTION_KEY` | state | 88-88 | 1 | high |  |
| `US_MAJOR_INDEX_SYMBOLS` | state | 89-89 | 1 | high |  |
| `US_SP500_SECTOR_SYMBOLS` | state | 90-90 | 1 | high |  |
| `US_INDUSTRY_SECTOR_SYMBOLS` | state | 91-91 | 1 | high |  |
| `US_MAJOR_INDEX_SECTOR_SYMBOLS` | state | 92-97 | 6 | high |  |
| `nativeInnerHtmlDescriptor` | state | 179-179 | 1 | low |  |
| `EXCLUDED_SECTOR_SOURCE_NAMES` | state | 735-735 | 1 | high |  |
| `WEIGHTED_SECTOR_THEME_RULES` | state | 3209-3240 | 32 | high |  |
| `getWatchlist` | function | 5188-5195 | 8 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) |
| `saveWatchlist` | function | 5197-5199 | 3 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) |
| `watchlistKey` | function | 5201-5203 | 3 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) |
| `PORTFOLIO_FACTOR_SOURCE` | state | 5236-5239 | 4 | high |  |
| `PORTFOLIO_COST_MODEL` | state | 5241-5246 | 6 | high |  |
| `BACKTEST_BENCHMARK_SOURCE` | state | 5993-5996 | 4 | high |  |
| `BACKTEST_DRIFT_SOURCE` | state | 5998-6001 | 4 | high |  |
| `BACKTEST_FACTOR_BASELINE` | state | 6003-6013 | 11 | high |  |
| `US_NYSE_DIRECTORY_PAGE_SIZE` | state | 10831-10831 | 1 | high |  |
| `US_ETF_DEFAULT_PAGE_SIZE` | state | 10832-10832 | 1 | high |  |
| `US_ETF_PAGE_SIZE_OPTIONS` | state | 10833-10833 | 1 | high |  |
| `usNyseDirectoryState` | state | 10834-10845 | 12 | high |  |
| `usEtfSelectedSymbol` | state | 10846-10846 | 1 | high |  |
| `US_ETF_CATEGORY_DEFINITIONS` | state | 10847-10860 | 14 | high |  |
| `US_ETF_CATEGORY_LABELS` | state | 10861-10861 | 1 | high |  |
| `US_ETF_DIRECTORY_SORT_OPTIONS` | state | 10862-10868 | 7 | high |  |
| `derivativesFuturesDetailSymbol` | state | 13230-13230 | 1 | high |  |
| `derivativesFuturesMarketScope` | state | 13231-13231 | 1 | high |  |
| `derivativesFuturesFrameworkScope` | state | 13232-13232 | 1 | high |  |
| `derivativesFuturesRegionalExpandedKeys` | state | 13233-13233 | 1 | high |  |
| `derivativesFuturesTechnicalChartStates` | state | 13234-13234 | 1 | low |  |
| `derivativesFuturesTechnicalContractState` | state | 13235-13235 | 1 | high |  |
| `derivativesFuturesTechnicalIntervalState` | state | 13236-13236 | 1 | high |  |
| `derivativesFuturesTechnicalIndicatorState` | state | 13237-13237 | 1 | high |  |
| `derivativesFuturesStockStyleMaState` | state | 13238-13238 | 1 | high |  |
| `derivativesFuturesStockStyleOverlayState` | state | 13239-13239 | 1 | high |  |
| `derivativesFuturesStockStylePanelState` | state | 13240-13240 | 1 | high |  |
| `derivativesFuturesStockStyleVisibleState` | state | 13241-13241 | 1 | high |  |
| `derivativesFuturesStockStylePanState` | state | 13242-13242 | 1 | high |  |
| `derivativesFuturesTechnicalSeriesCache` | state | 13243-13243 | 1 | high |  |
| `derivativesFuturesTechnicalLoadingKeys` | state | 13244-13244 | 1 | high |  |
| `FUTURES_TECHNICAL_INTERVAL_OPTIONS` | state | 13245-13249 | 5 | high |  |
| `FUTURES_TECHNICAL_INDICATOR_OPTIONS` | state | 13250-13257 | 8 | high |  |
| `TECHNICAL_PANEL_INDICATOR_OPTIONS` | state | 13258-13273 | 16 | high |  |
| `TECHNICAL_PANEL_INDICATOR_KEYS` | state | 13274-13274 | 1 | high |  |
| `DERIVATIVES_WATCHLIST_STORAGE_KEY` | state | 13275-13275 | 1 | high |  |
| `DERIVATIVE_ASSET_NAME_MAP` | state | 13276-13317 | 42 | high |  |
| `getSelectedFuturesTechnicalContract` | function | 14136-14144 | 9 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getSelectedFuturesTechnicalInterval` | function | 14146-14150 | 5 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getFuturesTechnicalIntervalLabel` | function | 14152-14154 | 3 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getFuturesTechnicalIndicatorStateKey` | function | 14156-14161 | 6 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getSelectedFuturesTechnicalIndicatorView` | function | 14163-14167 | 5 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getFuturesTechnicalSeriesCacheKey` | function | 14201-14206 | 6 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getFuturesTechnicalCachedPayload` | function | 14222-14233 | 12 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `TAIWAN_OPTION_PRODUCT_FALLBACKS` | state | 16117-16126 | 10 | high |  |
| `TAIWAN_OPTION_CHAIN_UNDERLYINGS` | state | 16128-16128 | 1 | high |  |
| `OPTIONS_DOCUMENT_CATEGORY_ORDER` | state | 17567-17578 | 12 | high |  |
| `OPTIONS_MARKET_CHAIN_SYMBOL_ALIASES` | state | 18018-18036 | 19 | high |  |
| `OPTIONS_MARKET_CHAIN_FUTURES_SYMBOLS` | state | 18038-18043 | 6 | high |  |
| `derivativesOptionsSelectedStrategy` | state | 18622-18622 | 1 | high |  |
| `derivativesOptionsChainSource` | state | 18623-18623 | 1 | high |  |
| `derivativesOptionsSelectedUnderlying` | state | 18624-18624 | 1 | high |  |
| `derivativesOptionsSelectedFocus` | state | 18625-18625 | 1 | high |  |
| `derivativesOptionsSelectedStrike` | state | 18626-18626 | 1 | high |  |
| `derivativesOptionsRegionalExpandedKeys` | state | 18627-18627 | 1 | high |  |
| `DERIVATIVES_OPTIONS_AUTO_REFRESH_MS` | state | 18628-18628 | 1 | high |  |
| `derivativesOptionsAutoRefreshTimer` | state | 18629-18629 | 1 | high |  |
| `derivativesOptionsAutoRefreshPayload` | state | 18630-18630 | 1 | high |  |
| `derivativesOptionsAutoRefreshInFlight` | state | 18631-18631 | 1 | high |  |
| `derivativesOptionsMarketChainInFlightKey` | state | 19268-19268 | 1 | high |  |
| `optionsAiExtrasCache` | state | 19501-19501 | 1 | high |  |
| `optionsAiExtrasLoading` | state | 19502-19502 | 1 | high |  |
| `usStockSearchRequestId` | state | 22233-22233 | 1 | high |  |
| `ASSET_HUB_REGION_ORDER` | state | 23121-23121 | 1 | high |  |
| `ASSET_HUB_SCHEMA_FALLBACK` | state | 23122-23150 | 29 | high |  |
| `ASSET_HUB_OPTION_CHAIN_UNDERLYINGS` | state | 23474-23480 | 7 | high |  |
| `ASSET_FINANCE_TREND_RANGES` | state | 24187-24192 | 6 | high |  |
| `ASSET_FINANCE_TREND_FILTERS` | state | 24194-24200 | 7 | high |  |
| `assetFinanceTrendChartCounter` | state | 24202-24202 | 1 | high |  |

### js/core.js

26 個符號(函式 26、狀態 0),共 167 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `toneClass` | function | 144-148 | 5 | medium | groups=home (index.html) / market (market-overview.html, news.html) / sectors (tw-stocks.html) / watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / tw-etf (tw-etf.html) / us-watchlist (us-watchlist.html) |
| `escapeHtml` | function | 150-158 | 9 | medium | groups=home (index.html) / market (market-overview.html, news.html) / sectors (tw-stocks.html) / watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / tw-etf (tw-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) / derivatives-analytics (derivatives-analytics.html) |
| `normalizeSafeUrl` | function | 160-173 | 14 | medium | groups=home (index.html) / market (market-overview.html, news.html) / sectors (tw-stocks.html) / watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / tw-etf (tw-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) / derivatives-analytics (derivatives-analytics.html) |
| `safeUrl` | function | 175-177 | 3 | medium | groups=home (index.html) / market (market-overview.html, news.html) / sectors (tw-stocks.html) / watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / tw-etf (tw-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) / derivatives-analytics (derivatives-analytics.html) |
| `sanitizeHtml` | function | 181-206 | 26 | high | 只被 main bootstrap 尾端程式碼(或其內的 enforceSafeInnerHtml IIFE)參照,非死碼候選 |
| `formatRocDateFromDate` | function | 444-449 | 6 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `parseTwseNumber` | function | 512-515 | 4 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `formatYmdDate` | function | 517-522 | 6 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `parseYmdDate` | function | 524-529 | 6 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `clampScore` | function | 3255-3258 | 4 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `setText` | function | 4469-4472 | 4 | medium | groups=home (index.html) / market (market-overview.html, news.html) / watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `parseAnalysisNumber` | function | 5721-5725 | 5 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `parseMarketNumber` | function | 8901-8905 | 5 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) / watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / tw-etf (tw-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) / derivatives-analytics (derivatives-analytics.html) |
| `formatGlobalValue` | function | 8922-8929 | 8 | medium | groups=sectors (tw-stocks.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) / derivatives-analytics (derivatives-analytics.html) |
| `formatGlobalVolume` | function | 8931-8937 | 7 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) / derivatives-analytics (derivatives-analytics.html) |
| `formatSignedPercentValue` | function | 11811-11813 | 3 | medium | groups=sectors (tw-stocks.html) / us-etf (us-etf.html) |
| `formatUsDetailMetric` | function | 20766-20769 | 4 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `formatBacktestRatio` | function | 21561-21564 | 4 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `formatBacktestPercent` | function | 21566-21571 | 6 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `formatUsSimulationMoney` | function | 22388-22392 | 5 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `assetHubTone` | function | 23109-23112 | 4 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `formatAssetHubExpiration` | function | 23454-23460 | 7 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `formatAssetOptionNumber` | function | 23511-23515 | 5 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `formatAssetOptionWhole` | function | 23517-23521 | 5 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `formatAssetOptionIv` | function | 23523-23527 | 5 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `formatChartDate` | function | 29063-29069 | 7 | medium | groups=sectors (tw-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |

### js/api.js

4 個符號(函式 4、狀態 0),共 80 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `buildTwseInstitutionTradeUrl` | function | 531-538 | 8 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `fetchClientInstitutionalTradeForDate` | function | 560-571 | 12 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `fetchClientInstitutionalTradeHistory` | function | 610-660 | 51 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `fetchWithTimeout` | function | 4459-4467 | 9 | medium | groups=home (index.html) / sectors (tw-stocks.html) / watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / tw-etf (tw-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) / derivatives-analytics (derivatives-analytics.html) |

### js/shared-calc.js(新增,見發現①)

72 個符號(函式 72、狀態 0),共 3348 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `normalizePortfolioHistory` | function | 5248-5258 | 11 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculatePortfolioReturns` | function | 5260-5269 | 10 | medium | groups=watchlist (tw-Optional-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculatePortfolioStdDev` | function | 5271-5277 | 7 | medium | groups=watchlist (tw-Optional-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculatePortfolioCorrelation` | function | 5279-5298 | 20 | medium | groups=watchlist (tw-Optional-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculatePeriodReturn` | function | 5300-5306 | 7 | medium | groups=watchlist (tw-Optional-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildPortfolioTheoryAssessment` | function | 5308-5412 | 105 | medium | groups=watchlist (tw-Optional-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `getSimulationSignal` | function | 5542-5566 | 25 | medium | groups=watchlist (tw-Optional-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `technicalSma` | function | 5727-5735 | 9 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `technicalSlope` | function | 5737-5750 | 14 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `technicalPivots` | function | 5752-5762 | 11 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildMarketBreadthIndicators` | function | 5764-5806 | 43 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildFuturesBreadthProxyIndicators` | function | 5808-5907 | 100 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculatePsy` | function | 5909-5917 | 9 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `classifyVolumePriceNinePatterns` | function | 5919-5991 | 73 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateBacktestAtrPct` | function | 6015-6032 | 18 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateMaxDrawdownPct` | function | 6034-6047 | 14 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateSharpeLikeScore` | function | 6049-6055 | 7 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateBacktestWinRate` | function | 6057-6060 | 4 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateBacktestAverageReturn` | function | 6062-6065 | 4 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateBacktestProfitFactor` | function | 6067-6073 | 7 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateMaxLosingStreak` | function | 6075-6088 | 14 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `summarizeBacktestSegment` | function | 6090-6100 | 11 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildBacktestModelValidation` | function | 6102-6173 | 72 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildBacktestModelRebuildResult` | function | 6175-6230 | 56 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildBacktestTrendForecast` | function | 6232-6362 | 131 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildBacktestLearningModel` | function | 6364-6667 | 304 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildInstitutionalBacktestFramework` | function | 6669-6975 | 307 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildFuturesBacktestFramework` | function | 6977-7072 | 96 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `calculateBollingerBands` | function | 7074-7091 | 18 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateFibonacciRetracement` | function | 7093-7114 | 22 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateSupportResistance` | function | 7116-7153 | 38 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateSmartMoneyConcepts` | function | 7155-7206 | 52 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildChipIndicator` | function | 7208-7240 | 33 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `buildMovingAverageIndicator` | function | 7242-7422 | 181 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `analyzeTechnicalTheories` | function | 7424-8248 | 825 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `movingAverage` | function | 8907-8913 | 7 | medium | groups=sectors (tw-stocks.html) / watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildGlobalMarketDetail` | function | 10347-10392 | 46 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `averageFuturesValues` | function | 14131-14134 | 4 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `lastFiniteFuturesValue` | function | 14578-14584 | 7 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `calculateFuturesEmaSeries` | function | 14586-14602 | 17 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesRollingAverageSeries` | function | 14604-14611 | 8 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesRsiSeries` | function | 14613-14619 | 7 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesKdSeries` | function | 14621-14639 | 19 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesVwapSeries` | function | 14641-14648 | 8 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesObvSeries` | function | 14650-14658 | 9 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesMfi` | function | 14660-14673 | 14 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesRollingIndicatorSeries` | function | 14675-14677 | 3 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesRsi` | function | 14679-14690 | 12 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesKd` | function | 14692-14707 | 16 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `calculateFuturesAtr` | function | 14709-14717 | 9 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesCci` | function | 14719-14728 | 10 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesWilliamsR` | function | 14730-14737 | 8 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesDmiAdx` | function | 14739-14766 | 28 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `calculateFuturesParabolicSar` | function | 14768-14798 | 31 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `buildFuturesTechnicalSnapshot` | function | 14800-14934 | 135 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `parseRocDate` | function | 29029-29061 | 33 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `isValidTechnicalOhlc` | function | 29088-29092 | 5 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `normalizeHistory` | function | 29094-29114 | 21 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `exponentialMovingAverage` | function | 29173-29186 | 14 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateKd` | function | 29188-29200 | 13 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateMacd` | function | 29202-29215 | 14 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateRsi` | function | 29217-29234 | 18 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateBias` | function | 29236-29242 | 7 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateDmi` | function | 29244-29293 | 50 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateObv` | function | 29295-29304 | 10 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateAtr` | function | 29306-29319 | 14 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateCci` | function | 29321-29331 | 11 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateWilliamsR` | function | 29333-29341 | 9 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateMfi` | function | 29343-29363 | 21 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateMomentum` | function | 29365-29369 | 5 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateParabolicSarSeries` | function | 29371-29404 | 34 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `calculateIchimoku` | function | 29406-29418 | 13 | medium | groups=watchlist (tw-Optional-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |

### js/render-shared.js

46 個符號(函式 46、狀態 0),共 1257 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `renderSharedNavigation` | function | 105-142 | 38 | high | 只被 main bootstrap 尾端程式碼(或其內的 enforceSafeInnerHtml IIFE)參照,非死碼候選 |
| `isExcludedSector` | function | 737-740 | 4 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `sectorMatchesAnyLabel` | function | 742-746 | 5 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `normalizeSectorSummaryItem` | function | 1690-1716 | 27 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `renderSectorStockName` | function | 1788-1796 | 9 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `sectorSortValue` | function | 1998-2004 | 7 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `sortSectorItemsByActiveMode` | function | 2006-2021 | 16 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `renderSectorSortControl` | function | 2023-2040 | 18 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `renderScrollableClassTable` | function | 2042-2048 | 7 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `getSectorPageGroups` | function | 2050-2100 | 51 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `buildTechnicalTrendSummary` | function | 8250-8388 | 139 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `renderTechnicalTrendForecastSummary` | function | 8390-8462 | 73 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `buildPath` | function | 8915-8920 | 6 | medium | groups=sectors (tw-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `normalizeGlobalSeries` | function | 8975-8982 | 8 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-etf (us-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `normalizeGlobalOhlcvSeries` | function | 8984-9004 | 21 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `getVixSentimentBand` | function | 9028-9035 | 8 | medium | groups=sectors (tw-stocks.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `buildYahooFinanceUrl` | function | 10337-10340 | 4 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / us-watchlist (us-watchlist.html) |
| `buildUsStockSearchUrl` | function | 10342-10345 | 4 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) / us-watchlist (us-watchlist.html) |
| `normalizeFuturesTechnicalCandles` | function | 14208-14220 | 13 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `optionsNumber` | function | 16093-16097 | 5 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `optionsWhole` | function | 16099-16102 | 4 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `optionsDecimal` | function | 16104-16110 | 7 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `optionsPct` | function | 16112-16115 | 4 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `averageUsHistoryField` | function | 20771-20774 | 4 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildUsSearchDetail` | function | 20776-20859 | 84 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `renderUsBacktestLearningCard` | function | 21573-21735 | 163 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `normalizeUsWatchlistItem` | function | 22317-22329 | 13 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `usWatchlistKey` | function | 22331-22333 | 3 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `getUsWatchlist` | function | 22335-22344 | 10 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `saveUsWatchlist` | function | 22346-22348 | 3 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `upsertUsWatchlistSymbol` | function | 22350-22365 | 16 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `getUsPortfolioSimulation` | function | 22375-22382 | 8 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `saveUsPortfolioSimulation` | function | 22384-22386 | 3 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `classifyUsPortfolioAsset` | function | 22394-22397 | 4 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `estimateUsPortfolioTransactionCost` | function | 22399-22405 | 7 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `renderUsWatchlistAiSummary` | function | 22521-22549 | 29 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `renderUsWatchlist` | function | 22603-22689 | 87 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `buildUsPortfolioFactorAssessment` | function | 22691-22777 | 87 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `renderUsPortfolioSimulator` | function | 22779-22903 | 125 | medium | groups=us-stock-search (us-stock-search.html) / us-watchlist (us-watchlist.html) |
| `sliceVisibleWindow` | function | 28999-29004 | 6 | medium | groups=sectors (tw-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `getWeekKey` | function | 29071-29075 | 5 | medium | groups=sectors (tw-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `getPeriodKey` | function | 29077-29086 | 10 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `aggregateHistory` | function | 29116-29144 | 29 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `renderCombinedIndicatorPanel` | function | 29553-29618 | 66 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `fetchDerivativesApi` | function | 33226-33237 | 12 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / derivatives-analytics (derivatives-analytics.html) |
| `twEtfWeightText` | function | 33731-33735 | 5 | medium | groups=us-etf (us-etf.html) / tw-etf (tw-etf.html) |

### js/charts.js

10 個符號(函式 10、狀態 0),共 909 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `renderSectorLineChart` | function | 752-784 | 33 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `renderSectorSnapshotLineChart` | function | 786-836 | 51 | medium | groups=market (market-overview.html, news.html) / sectors (tw-stocks.html) |
| `renderWeightedVixComparisonChart` | function | 1604-1688 | 85 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderVixSparkline` | function | 4474-4518 | 45 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `bindHorizontalChartPan` | function | 29006-29027 | 22 | medium | groups=sectors (tw-stocks.html) / search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `getChartHistory` | function | 29146-29159 | 14 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `getChartIntervalLabel` | function | 29161-29171 | 11 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderIndicatorChart` | function | 29420-29551 | 132 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderTechnicalChart` | function | 29620-30027 | 408 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) |
| `bindChartHover` | function | 32542-32649 | 108 | medium | groups=search (tw-stock-search.html) / global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / us-stock-search (us-stock-search.html) / us-etf (us-etf.html) |

### js/stock-detail.js

10 個符號(函式 10、狀態 0),共 2859 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `buildFallbackStockDetail` | function | 451-510 | 60 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildLatestInstitutionalTradeFromHistory` | function | 589-608 | 20 | high |  |
| `loadInstitutionalTradeHistoryIfNeeded` | function | 678-733 | 56 | high |  |
| `isStockInWatchlist` | function | 5205-5207 | 3 | high |  |
| `toggleWatchlistStock` | function | 5209-5215 | 7 | high |  |
| `renderStockDetail` | function | 30029-32540 | 2512 | high |  |
| `initInstitutionChartCursor` | function | 32651-32720 | 70 | high |  |
| `initMajorHolderChartCursor` | function | 32722-32788 | 67 | high |  |
| `initMarginBalanceChartCursor` | function | 32790-32850 | 61 | high |  |
| `getStockDetailCacheKey` | function | 32923-32925 | 3 | medium | groups=search (tw-stock-search.html) / us-stock-search (us-stock-search.html) |

### js/page-home.js

33 個符號(函式 33、狀態 0),共 1204 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `formatSectorFundFlowAmount` | function | 226-235 | 10 | high |  |
| `formatSectorFundFlowPct` | function | 237-242 | 6 | high |  |
| `sectorFundFlowTone` | function | 244-248 | 5 | high |  |
| `getSectorFundFlowRows` | function | 250-261 | 12 | high |  |
| `renderSectorFundFlowMetric` | function | 263-270 | 8 | high |  |
| `renderSectorFundFlowRow` | function | 272-304 | 33 | high |  |
| `renderSectorFundFlow` | function | 306-371 | 66 | high |  |
| `buildInstitutionSummaryFromRows` | function | 373-399 | 27 | high |  |
| `buildSectorCategoryUrl` | function | 1814-1818 | 5 | high |  |
| `renderSectorCategoryLink` | function | 1820-1823 | 4 | high |  |
| `renderMarketSectorRankingName` | function | 2256-2260 | 5 | high |  |
| `renderMarketSectorRankingTable` | function | 2262-2291 | 30 | high |  |
| `renderMarketSectorRankingTabs` | function | 2293-2308 | 16 | high |  |
| `renderMarketListedSectorRanking` | function | 2310-2359 | 50 | high |  |
| `formatUpdateText` | function | 4091-4096 | 6 | high |  |
| `renderHomePennyTrend` | function | 4098-4152 | 55 | high |  |
| `loadHomePennySectorRecommendations` | function | 4154-4176 | 23 | high |  |
| `renderHome` | function | 4177-4231 | 55 | high |  |
| `buildMarketRiskAdvice` | function | 4233-4297 | 65 | high |  |
| `buildMarketThemeNewsCards` | function | 4299-4386 | 88 | high |  |
| `buildAfterMarketWatchCard` | function | 4388-4448 | 61 | high |  |
| `formatInstitutionAmount` | function | 4451-4457 | 7 | high |  |
| `getVixSentiment` | function | 4520-4567 | 48 | high |  |
| `buildInstitutionContinuityModel` | function | 4651-4698 | 48 | high |  |
| `buildMarketAiInsightModel` | function | 4700-4905 | 206 | high |  |
| `renderMarketInsightRankList` | function | 4907-4923 | 17 | high |  |
| `renderMarketInsightPanel` | function | 4925-4962 | 38 | high |  |
| `getMarketSortedSectors` | function | 4964-4970 | 7 | high |  |
| `getMarketLimitSamples` | function | 4972-4978 | 7 | high |  |
| `getMarketExtremeSummary` | function | 4980-4995 | 16 | high |  |
| `renderLimitMoveStockLink` | function | 4997-5008 | 12 | high |  |
| `renderMarketExtremeObservationCard` | function | 5010-5079 | 70 | high |  |
| `renderMarketPage` | function | 5081-5178 | 98 | high |  |

### js/page-us.js

66 個符號(函式 66、狀態 0),共 2958 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `getUsEtfCategoryLabel` | function | 10870-10872 | 3 | high |  |
| `getUsEtfCategoryKey` | function | 10874-10909 | 36 | high |  |
| `enrichUsEtfDirectoryItems` | function | 10911-10920 | 10 | high |  |
| `renderUsEtfCategoryFilters` | function | 10922-10934 | 13 | high |  |
| `renderUsEtfCategoryOptions` | function | 10936-10948 | 13 | high |  |
| `renderUsEtfSortOptions` | function | 10950-10954 | 5 | high |  |
| `normalizeUsEtfSymbolKey` | function | 10956-10958 | 3 | high |  |
| `getUsEtfQuoteMap` | function | 10960-10970 | 11 | high |  |
| `buildUsEtfDirectoryRows` | function | 10972-10992 | 21 | high |  |
| `getUsEtfDirectorySortValue` | function | 10994-10998 | 5 | high |  |
| `getUsEtfFilteredDirectoryRows` | function | 11000-11022 | 23 | high |  |
| `getUsEtfDirectoryPage` | function | 11024-11042 | 19 | high |  |
| `getUsNyseDirectoryConfig` | function | 11044-11084 | 41 | high |  |
| `renderUsNyseDirectorySection` | function | 11086-11128 | 43 | high |  |
| `renderUsNyseListedStocksSection` | function | 11130-11132 | 3 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderUsNyseListedEtfsSection` | function | 11134-11136 | 3 | high |  |
| `renderUsEtfDirectoryTable` | function | 11138-11223 | 86 | high |  |
| `findUsEtfDirectoryRow` | function | 11225-11228 | 4 | high |  |
| `getUsEtfDetailTone` | function | 11230-11236 | 7 | high |  |
| `getUsEtfDetailSignals` | function | 11238-11285 | 48 | high |  |
| `getUsEtfDetailPositionInsight` | function | 11307-11358 | 52 | high |  |
| `getUsEtfDetailRiskInsight` | function | 11360-11379 | 20 | high |  |
| `renderUsEtfSourceStep` | function | 11394-11406 | 13 | high |  |
| `renderUsEtfComponentsCard` | function | 11408-11438 | 31 | high |  |
| `renderUsEtfIncomeCard` | function | 11440-11489 | 50 | high |  |
| `renderUsEtfDetail` | function | 11491-11612 | 122 | high |  |
| `loadUsEtfDetail` | function | 11614-11664 | 51 | high |  |
| `renderUsNyseDirectoryTable` | function | 11666-11740 | 75 | high |  |
| `renderUsNyseListedStocksTable` | function | 11742-11744 | 3 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderUsNyseListedEtfsTable` | function | 11746-11748 | 3 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `loadUsNyseDirectory` | function | 11750-11793 | 44 | high |  |
| `loadUsNyseListedEtfs` | function | 11799-11801 | 3 | high |  |
| `getUsEtfMarketItems` | function | 11803-11805 | 3 | high |  |
| `getUsEtfDirectoryItems` | function | 11807-11809 | 3 | high |  |
| `getUsEtfReturnStats` | function | 11815-11857 | 43 | high |  |
| `getUsEtfRankedItems` | function | 11859-11874 | 16 | high |  |
| `getUsEtfComparisonItems` | function | 11876-11882 | 7 | high |  |
| `renderUsEtfRankRows` | function | 11884-11904 | 21 | high |  |
| `renderUsEtfPageHero` | function | 11906-11915 | 10 | high |  |
| `renderUsEtfOverview` | function | 11917-12039 | 123 | high |  |
| `renderUsEtfAiAllocation` | function | 12041-12131 | 91 | high |  |
| `renderUsEtfRanking` | function | 12133-12153 | 21 | high |  |
| `getUsEtfPopularThemeNote` | function | 12155-12172 | 18 | high |  |
| `getUsEtfPopularRiskText` | function | 12174-12183 | 10 | high |  |
| `renderUsEtfComparison` | function | 12185-12237 | 53 | high |  |
| `renderUsEtfPage` | function | 12239-12264 | 26 | high |  |
| `initUsEtfPage` | function | 12266-12293 | 28 | high |  |
| `bindUsNyseDirectoryControls` | function | 12786-12868 | 83 | high |  |
| `isUsStockInWatchlist` | function | 20861-20864 | 4 | high |  |
| `toggleUsDetailWatchlist` | function | 20866-20883 | 18 | high |  |
| `renderUsDetailAnalysisCards` | function | 20885-21369 | 485 | high |  |
| `renderUsDetailNewsCard` | function | 21371-21406 | 36 | high |  |
| `renderUsValuationCompanyCard` | function | 21408-21559 | 152 | high |  |
| `renderUsTechnicalTheorySection` | function | 21753-21921 | 169 | high |  |
| `bindUsDetailChartControls` | function | 21923-22037 | 115 | high |  |
| `renderUsMarketDetailTo` | function | 22039-22167 | 129 | high |  |
| `renderUsStockSearchDetail` | function | 22169-22171 | 3 | high |  |
| `renderUsStockSearchResults` | function | 22173-22205 | 33 | high |  |
| `loadUsStockSymbol` | function | 22207-22231 | 25 | high |  |
| `runUsStockSearch` | function | 22235-22269 | 35 | high |  |
| `initUsStockSearchPage` | function | 22271-22315 | 45 | high |  |
| `buildUsWatchlistAiAnalysis` | function | 22407-22519 | 113 | high |  |
| `loadUsWatchlistAiAnalyses` | function | 22551-22601 | 51 | high |  |
| `renderUsWatchlistSearchResults` | function | 22905-22948 | 44 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `initUsWatchlistPage` | function | 22989-22999 | 11 | high |  |
| `initUsVolumeMomentumCursor` | function | 32852-32921 | 70 | high |  |

### js/page-global-market.js(新增,取代原表格的 page-us.js「global-market(us)」+ page-derivatives.js,見發現②③)

370 個符號(函式 370、狀態 0),共 14141 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `renderMiniLineChart` | function | 8939-8973 | 35 | high |  |
| `buildUsMarketSentiment` | function | 9037-9068 | 32 | high |  |
| `renderUsMarketSentimentValueCard` | function | 9070-9163 | 94 | high |  |
| `renderUsVixSentimentSvg` | function | 9165-9231 | 67 | high |  |
| `renderUsIndexVixSvg` | function | 9233-9323 | 91 | high |  |
| `getUsIndexLineColor` | function | 9325-9327 | 3 | high |  |
| `getUsIndexLineColorBySymbol` | function | 9329-9332 | 4 | high |  |
| `getUsMajorIndexSelection` | function | 9334-9342 | 9 | high |  |
| `getUsMajorIndexCommonDateCount` | function | 9344-9351 | 8 | high |  |
| `getUsMajorIndexChartState` | function | 9353-9364 | 12 | high |  |
| `buildUsIndexVixAiAnalysis` | function | 9366-9522 | 157 | high |  |
| `renderUsMultiIndexVixSvg` | function | 9524-9623 | 100 | high |  |
| `renderUsMajorIndexVixCard` | function | 9625-9763 | 139 | high |  |
| `bindUsMajorIndexVixCard` | function | 9765-9851 | 87 | high |  |
| `bindUsIndexChartHover` | function | 9853-9937 | 85 | high |  |
| `buildUsSectorComparisonModel` | function | 9939-9972 | 34 | high |  |
| `buildUsSectorComparisonAnalysis` | function | 9974-10023 | 50 | high |  |
| `getUsBenchmarkDisplayName` | function | 10025-10033 | 9 | high |  |
| `getUsSectorDisplayName` | function | 10035-10058 | 24 | high |  |
| `getUsSectorOptionsForBenchmark` | function | 10060-10072 | 13 | high |  |
| `renderUsSectorComparisonSvg` | function | 10074-10163 | 90 | high |  |
| `renderUsSectorIndexComparisonCard` | function | 10165-10260 | 96 | high |  |
| `bindUsSectorIndexComparisonCard` | function | 10262-10335 | 74 | high |  |
| `buildGlobalMarketInsight` | function | 10463-10471 | 9 | high |  |
| `buildUsMarketPulseAnalysis` | function | 10473-10668 | 196 | high |  |
| `renderGlobalSummaryCard` | function | 10670-10794 | 125 | high |  |
| `renderGlobalMarketCards` | function | 10796-10829 | 34 | high |  |
| `getUsSectorStockSelectionStore` | function | 12295-12313 | 19 | high |  |
| `saveUsSectorStockSelection` | function | 12315-12320 | 6 | high |  |
| `getUsSectorStockLabel` | function | 12322-12325 | 4 | high |  |
| `renderUsSectorIndexSummaryContent` | function | 12327-12352 | 26 | high |  |
| `normalizeUsScopeSymbol` | function | 12354-12356 | 3 | high |  |
| `usSectorItemMatchesQuery` | function | 12358-12363 | 6 | high |  |
| `buildUsSectorScopeItems` | function | 12365-12396 | 32 | high |  |
| `mergeUsSectorDirectoryWithScope` | function | 12398-12454 | 57 | high |  |
| `renderUsSectorStocksBrowser` | function | 12456-12522 | 67 | high |  |
| `renderUsSectorStockItems` | function | 12524-12602 | 79 | high |  |
| `syncUsSectorStockSelectorState` | function | 12604-12616 | 13 | high |  |
| `fetchUsSectorDirectoryPayload` | function | 12618-12650 | 33 | high |  |
| `fetchUsSectorScopePayload` | function | 12652-12675 | 24 | high |  |
| `loadUsSectorStocks` | function | 12677-12704 | 28 | high |  |
| `bindUsSectorStocksBrowser` | function | 12706-12784 | 79 | high |  |
| `renderGlobalMarketSections` | function | 12870-12898 | 29 | high |  |
| `getUsMarketPayloadCounts` | function | 12900-12909 | 10 | high |  |
| `renderUsMarketScopeNote` | function | 12911-12919 | 9 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderUsPlatformDashboard` | function | 12921-13079 | 159 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderUsPlatformArchitecture` | function | 13081-13103 | 23 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `getAssetPlatformConfig` | function | 13105-13180 | 76 | high |  |
| `renderAssetPlatformDashboard` | function | 13182-13228 | 47 | high |  |
| `renderDerivativeNameMappingCard` | function | 13319-13344 | 26 | high |  |
| `readDerivativesWatchlist` | function | 13346-13353 | 8 | high |  |
| `hasDerivativeWatchSymbol` | function | 13355-13358 | 4 | high |  |
| `renderDerivativeWatchButton` | function | 13360-13363 | 4 | high |  |
| `bindDerivativeWatchlistControls` | function | 13365-13387 | 23 | high |  |
| `getFuturesMarketScope` | function | 13389-13396 | 8 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `buildFuturesCenterModel` | function | 13398-13447 | 50 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderFuturesCenterHero` | function | 13449-13509 | 61 | high |  |
| `getFuturesRegionToggleKey` | function | 13511-13519 | 9 | high |  |
| `renderFuturesCenterRegionalMarket` | function | 13521-13571 | 51 | high |  |
| `renderFuturesInvestmentLiveDataPanel` | function | 13573-13631 | 59 | high |  |
| `renderFuturesInvestmentFramework` | function | 13755-14024 | 270 | high |  |
| `renderFuturesAnalysisCenter` | function | 14026-14037 | 12 | high |  |
| `getFuturesScopeDetailConfig` | function | 14039-14061 | 23 | high |  |
| `buildFuturesScopeDetailStats` | function | 14063-14091 | 29 | high |  |
| `renderFuturesDetailScopeInsight` | function | 14093-14125 | 33 | high |  |
| `formatFuturesPctValue` | function | 14127-14129 | 3 | high |  |
| `getFuturesStockStyleChartKey` | function | 14169-14171 | 3 | high |  |
| `parseFuturesChartStateList` | function | 14173-14177 | 5 | high |  |
| `getFuturesStockStyleMaPeriods` | function | 14179-14184 | 6 | high |  |
| `getFuturesStockStyleOverlayIndicators` | function | 14186-14189 | 4 | high |  |
| `getFuturesStockStylePanelIndicators` | function | 14191-14195 | 5 | high |  |
| `setFuturesStockStyleStateList` | function | 14197-14199 | 3 | high |  |
| `buildFuturesTechnicalRenderItem` | function | 14235-14325 | 91 | high |  |
| `formatFuturesContractLabel` | function | 14327-14332 | 6 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `buildFuturesTechnicalOutlook` | function | 14334-14402 | 69 | high |  |
| `renderFuturesTechnicalContracts` | function | 14404-14433 | 30 | high |  |
| `renderFuturesTechnicalOutlookCard` | function | 14435-14464 | 30 | high |  |
| `renderFuturesKlineVolumeChart` | function | 14466-14576 | 111 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `formatFuturesIndicatorValue` | function | 14936-14940 | 5 | high |  |
| `renderFuturesMiniSparkline` | function | 14954-14976 | 23 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderFuturesTechnicalTimeframeControls` | function | 15096-15109 | 14 | high |  |
| `renderFuturesIndicatorSwitchChart` | function | 15111-15181 | 71 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `buildFuturesStockStyleChartDetail` | function | 15275-15312 | 38 | high |  |
| `getDefaultFuturesStockStyleVisibleCount` | function | 15314-15318 | 5 | high |  |
| `getFuturesStockStyleZoomState` | function | 15320-15328 | 9 | high |  |
| `renderFuturesTechnicalSummaryCard` | function | 15330-15421 | 92 | high |  |
| `renderFuturesStockStyleTechnicalChart` | function | 15423-15496 | 74 | high |  |
| `renderFuturesTechnicalTheorySection` | function | 15498-15673 | 176 | high |  |
| `renderFuturesQuoteOutlookCard` | function | 15675-15730 | 56 | high |  |
| `renderFuturesMarketDepthNotice` | function | 15732-15744 | 13 | high |  |
| `renderFuturesQuoteContextStack` | function | 15746-15755 | 10 | high |  |
| `renderFuturesQuoteTrendAnalysis` | function | 15757-15828 | 72 | high |  |
| `renderDerivativesFuturesPanel` | function | 15830-15924 | 95 | high |  |
| `renderDerivativesFuturesDataSections` | function | 15926-15939 | 14 | high |  |
| `renderDerivativesOptionsPanel` | function | 15941-15952 | 12 | high |  |
| `getTaiwanOptionProducts` | function | 16130-16139 | 10 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getActiveTaiwanOptionUnderlying` | function | 16141-16143 | 3 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getTaiwanOptionProductLabel` | function | 16145-16149 | 5 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderTaiwanOptionProductTabs` | function | 16151-16164 | 14 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getOptionsChainRows` | function | 16166-16168 | 3 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getOptionsDistributionRows` | function | 16170-16180 | 11 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getOptionsIvValues` | function | 16182-16187 | 6 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getOptionsDaysToExpiry` | function | 16189-16196 | 8 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getOptionsMaxOiWalls` | function | 16198-16209 | 12 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `normalizeOptionsOiRow` | function | 16211-16222 | 12 | high |  |
| `getOptionsLocalOiWalls` | function | 16224-16235 | 12 | high |  |
| `calculateOptionsLocalMaxPain` | function | 16237-16256 | 20 | high |  |
| `optionsOiWhole` | function | 16258-16261 | 4 | high |  |
| `sumOptionFinite` | function | 16263-16268 | 6 | high |  |
| `findOptionsExtraItem` | function | 16270-16277 | 8 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `buildOptionsHiddenDecisionFactors` | function | 16279-16371 | 93 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `buildOptionsAiFunctionalModel` | function | 16373-16503 | 131 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getOptionsUnderlyingPrice` | function | 16694-16696 | 3 | high |  |
| `getOptionsFocusMove` | function | 16698-16701 | 4 | high |  |
| `getOptionsRegionItemFocusKey` | function | 16703-16709 | 7 | high |  |
| `isOptionsRegionFocusActive` | function | 16711-16714 | 4 | high |  |
| `getOptionsFocusScopeLabel` | function | 16716-16720 | 5 | high |  |
| `getOptionsRegionalFocusItems` | function | 16722-16735 | 14 | high |  |
| `getOptionsRegionalItemFocusItems` | function | 16737-16749 | 13 | high |  |
| `getOptionsFocusItems` | function | 16751-16768 | 18 | high |  |
| `getOptionsActiveFocus` | function | 16770-16775 | 6 | high |  |
| `getOptionsRiskLightFromScore` | function | 16777-16785 | 9 | high |  |
| `buildOptionsFocusAnalysis` | function | 16787-16919 | 133 | high |  |
| `formatOptionsDistanceText` | function | 16921-16930 | 10 | high |  |
| `buildOptionsInvestorPlaybook` | function | 16932-16999 | 68 | high |  |
| `formatOptionsConeValue` | function | 17001-17010 | 10 | high |  |
| `buildOptionsRiskConeProjection` | function | 17012-17096 | 85 | high |  |
| `renderOptionsRiskConeContent` | function | 17098-17202 | 105 | high |  |
| `getOptionsStrikeKey` | function | 17215-17218 | 4 | high |  |
| `getSelectedOptionsStrike` | function | 17220-17230 | 11 | high |  |
| `optionsSignedWhole` | function | 17232-17237 | 6 | high |  |
| `renderOptionsChainStats` | function | 17239-17262 | 24 | high |  |
| `renderOptionsChainOiSummary` | function | 17264-17434 | 171 | high |  |
| `buildOptionsCrossValidationModules` | function | 17436-17448 | 13 | high |  |
| `renderOptionsCrossValidationInline` | function | 17450-17469 | 20 | high |  |
| `renderOptionsInsightFeedContent` | function | 17471-17531 | 61 | high |  |
| `getOptionsDocumentCategory` | function | 17580-17589 | 10 | high |  |
| `groupOptionsItemsByDocumentCategory` | function | 17591-17601 | 11 | high |  |
| `buildOptionsRegionalSummary` | function | 17603-17614 | 12 | high |  |
| `renderOptionsRegionAnalysisQuoteGrid` | function | 17616-17646 | 31 | high |  |
| `renderOptionsHeroMarketPanelV2` | function | 17692-17734 | 43 | high |  |
| `renderOptionsHeroMergedIntelligence` | function | 17736-17813 | 78 | high |  |
| `renderOptionsAiRiskModuleDeck` | function | 17815-17834 | 20 | high |  |
| `renderOptionsHeroDashboard` | function | 17836-17875 | 40 | high |  |
| `renderOptionsChainTableClean` | function | 17920-17986 | 67 | high |  |
| `renderOptionsChainSourceTabs` | function | 17995-18009 | 15 | high |  |
| `getTaiwanOptionUnderlyingFromMarketItem` | function | 18011-18016 | 6 | high |  |
| `isOptionsMarketChainCandidateSymbol` | function | 18045-18055 | 11 | high |  |
| `getOptionsMarketOptionChainSymbols` | function | 18057-18069 | 13 | high |  |
| `getOptionsMarketOptionChainSymbol` | function | 18071-18073 | 3 | high |  |
| `attachOptionsMarketChainMeta` | function | 18086-18093 | 8 | high |  |
| `getOptionsRegionalFocusKeyBySymbol` | function | 18095-18104 | 10 | high |  |
| `getOptionsMarketChainSelectorContext` | function | 18106-18115 | 10 | high |  |
| `getOptionsMarketChainItemForFocus` | function | 18117-18133 | 17 | high |  |
| `renderOptionsMarketChainSelector` | function | 18135-18194 | 60 | high |  |
| `renderOptionsOfficialTaiwanChainPanel` | function | 18196-18219 | 24 | high |  |
| `formatMarketOptionChainIv` | function | 18221-18226 | 6 | high |  |
| `formatMarketOptionContractPrice` | function | 18228-18232 | 5 | high |  |
| `pairMarketOptionContracts` | function | 18234-18251 | 18 | high |  |
| `normalizeMarketOptionContractForOi` | function | 18253-18267 | 15 | high |  |
| `buildOptionsModelFromPublicChain` | function | 18269-18345 | 77 | high |  |
| `pickMarketOptionChainRows` | function | 18347-18359 | 13 | high |  |
| `renderOptionsMarketOptionExpirationSelect` | function | 18361-18375 | 15 | high |  |
| `renderOptionsMarketOptionChainTable` | function | 18377-18447 | 71 | high |  |
| `renderOptionsMarketOptionChainPanel` | function | 18449-18513 | 65 | high |  |
| `renderOptionsMarketWorkbench` | function | 18515-18541 | 27 | high |  |
| `renderOptionsSpotBenchmarkStrip` | function | 18543-18565 | 23 | high |  |
| `renderOptionsVolatilityCenter` | function | 18567-18582 | 16 | high |  |
| `renderOptionsGreeksCenter` | function | 18584-18613 | 30 | high |  |
| `getOptionsStrategyGrade` | function | 18615-18620 | 6 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `buildOptionsStrategyRows` | function | 18633-18702 | 70 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getOptionsActiveStrategy` | function | 18704-18708 | 5 | high |  |
| `renderOptionsStrategyDetail` | function | 18710-18730 | 21 | high |  |
| `renderOptionsStrategyCenter` | function | 18732-18776 | 45 | high |  |
| `renderOptionsRiskDashboard` | function | 18849-18873 | 25 | high |  |
| `renderOptionsAiFunctionalPage` | function | 18902-18908 | 7 | high |  |
| `renderDerivativesFuturesSinglePage` | function | 18918-18923 | 6 | high |  |
| `renderDerivativesOptionsSinglePage` | function | 18925-18929 | 5 | high |  |
| `renderDerivativesSinglePageContent` | function | 18931-18935 | 5 | high |  |
| `bindDerivativeAssetLoadMore` | function | 18937-18960 | 24 | high |  |
| `hydrateDerivativesFuturesCandles` | function | 18962-19009 | 48 | high |  |
| `bindDerivativesFuturesPanel` | function | 19011-19177 | 167 | high |  |
| `bindOptionsRiskConeHover` | function | 19179-19240 | 62 | high |  |
| `refreshDerivativesOptionsCurrentExpiry` | function | 19242-19266 | 25 | high |  |
| `fetchOptionsMarketChainPayload` | function | 19270-19278 | 9 | high |  |
| `hydrateSelectedOptionsMarketChain` | function | 19280-19314 | 35 | high |  |
| `scheduleDerivativesOptionsAutoRefresh` | function | 19316-19321 | 6 | high |  |
| `bindDerivativesOptionsPanel` | function | 19323-19499 | 177 | high |  |
| `fetchOptionsAiExtraMarket` | function | 19504-19508 | 5 | high |  |
| `hydrateOptionsAiExtras` | function | 19510-19539 | 30 | high |  |
| `getUsMarketOverviewModel` | function | 19541-19595 | 55 | high |  |
| `getUsMarketTone` | function | 19597-19601 | 5 | high |  |
| `formatUsMarketPct` | function | 19603-19606 | 4 | high |  |
| `renderUsMarketOverviewCards` | function | 19608-19625 | 18 | high |  |
| `renderUsMarketInstitutionSummary` | function | 19627-19675 | 49 | high |  |
| `renderUsMarketInstitutionRows` | function | 19677-19695 | 19 | high |  |
| `buildUsMarketRankItems` | function | 19697-19704 | 8 | high |  |
| `renderUsMarketRankList` | function | 19706-19722 | 17 | high |  |
| `getUsMarketSectorRankingGroups` | function | 19724-19750 | 27 | high |  |
| `getUsMarketSectorRankingContext` | function | 19752-19760 | 9 | high |  |
| `getUsMarketSectorRankingName` | function | 19762-19766 | 5 | high |  |
| `getUsMarketRankingTurnover` | function | 19768-19777 | 10 | high |  |
| `formatUsMarketRankingAmount` | function | 19779-19786 | 8 | high |  |
| `getUsMarketSectorSortValue` | function | 19788-19794 | 7 | high |  |
| `sortUsMarketSectorRankingItems` | function | 19796-19819 | 24 | high |  |
| `formatUsMarketRankingChange` | function | 19821-19828 | 8 | high |  |
| `renderUsMarketSectorRankingTabs` | function | 19830-19840 | 11 | high |  |
| `renderUsMarketSectorSortControl` | function | 19842-19859 | 18 | high |  |
| `renderUsMarketSectorRankingName` | function | 19861-19870 | 10 | high |  |
| `renderUsMarketSectorLineChart` | function | 19872-19908 | 37 | high |  |
| `renderUsMarketSectorRankingTable` | function | 19910-19936 | 27 | high |  |
| `renderUsMarketSectorRanking` | function | 19938-19954 | 17 | high |  |
| `bindUsMarketOverviewControls` | function | 19956-19974 | 19 | high |  |
| `renderUsMarketInsightPanel` | function | 19976-20022 | 47 | high |  |
| `renderUsMarketRiskAdviceCard` | function | 20024-20188 | 165 | high |  |
| `renderUsMarketDecisionInsights` | function | 20190-20315 | 126 | high |  |
| `renderUsMarketExtremeObservation` | function | 20317-20381 | 65 | high |  |
| `normalizeUsNewsText` | function | 20383-20389 | 7 | high |  |
| `buildUsMarketNewsFallbackTitle` | function | 20391-20406 | 16 | high |  |
| `localizeUsMarketNewsTitle` | function | 20408-20474 | 67 | high |  |
| `localizeUsMarketNewsTag` | function | 20476-20486 | 11 | high |  |
| `renderUsMarketNewsGrid` | function | 20488-20528 | 41 | high |  |
| `renderUsMarketOverviewLikeTaiwan` | function | 20530-20591 | 62 | high |  |
| `renderGlobalMarketPage` | function | 20593-20707 | 115 | high |  |
| `initGlobalMarketPage` | function | 20709-20764 | 56 | high |  |
| `renderFuturesBacktestLearningCard` | function | 21737-21751 | 15 | high |  |
| `renderAssetHubFallbackPage` | function | 23001-23091 | 91 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `getAssetHubItems` | function | 23093-23095 | 3 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `getAssetHubUsableItems` | function | 23097-23099 | 3 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `findAssetHubItem` | function | 23101-23103 | 3 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `filterAssetHubItems` | function | 23105-23107 | 3 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `assetHubDirection` | function | 23114-23119 | 6 | high |  |
| `getAssetHubRegion` | function | 23152-23160 | 9 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `getAssetHubItemUrl` | function | 23162-23164 | 3 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `getAssetHubMetric` | function | 23166-23170 | 5 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `groupAssetHubItemsByRegion` | function | 23172-23182 | 11 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `renderAssetHubRegionChips` | function | 23184-23192 | 9 | medium | groups=asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `renderAssetHubSchemaPanel` | function | 23194-23256 | 63 | medium | groups=asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `renderAssetHubRegionalGroups` | function | 23258-23308 | 51 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `renderAssetHubQuoteGrid` | function | 23310-23333 | 24 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `renderAssetHubSummary` | function | 23335-23372 | 38 | high |  |
| `renderAssetHubOnlineRows` | function | 23374-23394 | 21 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `renderAssetHubOnlineTable` | function | 23396-23415 | 20 | medium | groups=global-market (futures.html, options.html, us-market-overview.html, us-stocks.html) / asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) |
| `renderAssetHubFutures` | function | 23417-23432 | 16 | high |  |
| `renderAssetHubTaiwanFuturesCard` | function | 23434-23452 | 19 | medium | groups=asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `renderAssetHubOptionContracts` | function | 23462-23472 | 11 | medium | groups=asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `renderAssetHubPublicOptionChainCard` | function | 23482-23509 | 28 | medium | groups=asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `pickTaiwanOptionRows` | function | 23529-23538 | 10 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `getTaiwanOptionExpiryPrefix` | function | 23540-23545 | 6 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `formatTaiwanOptionExpiryCode` | function | 23547-23553 | 7 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `formatTaiwanOptionExpiryLabel` | function | 23555-23557 | 3 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderTaiwanOptionExpiryTabs` | function | 23559-23575 | 17 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderTaiwanOptionChainTable` | function | 23577-23625 | 49 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderTaiwanOptionDistribution` | function | 23627-23647 | 21 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderTaiwanOptionAnalysis` | function | 23649-23691 | 43 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderTaiwanOptionChainCard` | function | 23693-23727 | 35 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `renderAssetHubOptionsLegacy` | function | 23729-23748 | 20 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetHubOptions` | function | 23750-23774 | 25 | high |  |
| `findAssetHubItemAny` | function | 23776-23782 | 7 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `findAssetHubUsableItemAny` | function | 23784-23790 | 7 | high |  |
| `getAssetHubItemsBySymbols` | function | 23792-23795 | 4 | high |  |
| `getAssetHubUsableBySymbols` | function | 23797-23800 | 4 | high |  |
| `uniqueAssetHubItemsBySymbol` | function | 23802-23810 | 9 | high |  |
| `normalizeTreasuryYieldValue` | function | 23812-23816 | 5 | high |  |
| `getAssetHubTreasuryYieldPoint` | function | 23818-23841 | 24 | high |  |
| `formatAssetHubYield` | function | 23843-23845 | 3 | high |  |
| `formatAssetHubRatio` | function | 23847-23849 | 3 | high |  |
| `clampAssetHubScore` | function | 23851-23855 | 5 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `buildAssetHubFinanceModel` | function | 23857-24012 | 156 | high |  |
| `buildAssetHubFinanceScenarios` | function | 24014-24056 | 43 | high |  |
| `buildAssetHubAllocationAdvice` | function | 24058-24081 | 24 | high |  |
| `renderAssetFinanceSignal` | function | 24083-24093 | 11 | high |  |
| `renderAssetFinanceSignalPanel` | function | 24095-24110 | 16 | high |  |
| `renderAssetFinanceCoreDashboard` | function | 24112-24143 | 32 | high |  |
| `renderAssetFinanceMetalsPanel` | function | 24145-24185 | 41 | high |  |
| `getAssetFinanceTrendRange` | function | 24204-24206 | 3 | high |  |
| `buildAssetFinanceTrendDataset` | function | 24208-24217 | 10 | high |  |
| `buildAssetFinanceTrendPoints` | function | 24219-24231 | 13 | high |  |
| `buildAssetFinanceTrendSeriesList` | function | 24233-24239 | 7 | high |  |
| `renderAssetFinanceTrendBody` | function | 24241-24338 | 98 | high |  |
| `getAssetFinanceTrendStatus` | function | 24340-24346 | 7 | high |  |
| `bindAssetFinanceTrendCursor` | function | 24348-24395 | 48 | high |  |
| `initAssetFinanceTrendSwitchers` | function | 24397-24461 | 65 | high |  |
| `renderAssetFinanceTrendPanelContent` | function | 24463-24521 | 59 | high |  |
| `renderAssetFinanceMetalProfilesPanel` | function | 24531-24606 | 76 | high |  |
| `buildAssetFinanceGlobalVenueInsight` | function | 24608-24669 | 62 | high |  |
| `renderAssetFinanceDriverFactorCard` | function | 24690-24705 | 16 | high |  |
| `formatAssetFinanceMetricPct` | function | 24707-24709 | 3 | high |  |
| `averageAssetFinanceValues` | function | 24711-24715 | 5 | high |  |
| `standardDeviationAssetFinanceValues` | function | 24717-24724 | 8 | high |  |
| `buildAssetFinanceForecastItem` | function | 24726-24804 | 79 | high |  |
| `buildAssetFinancePriceForecastItems` | function | 24806-24813 | 8 | high |  |
| `renderAssetFinancePriceForecastBody` | function | 24815-24881 | 67 | high |  |
| `renderAssetFinancePriceForecastContent` | function | 24883-24901 | 19 | high |  |
| `renderAssetFinanceMetalDriversPanel` | function | 24911-25124 | 214 | high |  |
| `renderAssetFinanceDecisionCenterPanel` | function | 25126-25422 | 297 | high |  |
| `renderAssetFinanceSelectableMetalOnlineRows` | function | 25460-25482 | 23 | high |  |
| `renderAssetFinanceSelectableBondOnlineRows` | function | 25484-25506 | 23 | high |  |
| `buildAssetFinanceMetalsEtfConclusion` | function | 25508-25555 | 48 | high |  |
| `renderAssetFinanceVolumeTrendChart` | function | 25595-25674 | 80 | high |  |
| `getAssetFinanceVolumePayloadItem` | function | 25676-25696 | 21 | high |  |
| `renderAssetFinanceSingleTrendRiskAnalysis` | function | 25698-25766 | 69 | high |  |
| `getAssetFinanceBondProfile` | function | 25768-25839 | 72 | high |  |
| `getAssetFinanceBondEtfLens` | function | 25841-25912 | 72 | high |  |
| `renderAssetFinanceBondSingleAnalysis` | function | 25914-26177 | 264 | high |  |
| `initAssetFinanceVolumeSelectors` | function | 26179-26216 | 38 | high |  |
| `bindAssetFinanceVolumeCursor` | function | 26218-26269 | 52 | high |  |
| `renderAssetFinanceMetalEtfSyncPanel` | function | 26271-26352 | 82 | high |  |
| `buildAssetFinanceBondResearchImport` | function | 26354-26516 | 163 | high |  |
| `renderAssetFinanceBondResearchHero` | function | 26518-26547 | 30 | high |  |
| `renderAssetFinanceBondResearchMarketAnalysis` | function | 26549-26581 | 33 | high |  |
| `renderAssetFinanceBondResearchPanel` | function | 26583-26637 | 55 | high |  |
| `renderAssetFinanceScenarioPanel` | function | 26639-26660 | 22 | high |  |
| `averageAssetFinancePct` | function | 26662-26666 | 5 | high |  |
| `strongestAssetFinanceItem` | function | 26668-26672 | 5 | high |  |
| `formatAssetFinancePct` | function | 26674-26677 | 4 | high |  |
| `assetFinancePctTone` | function | 26679-26682 | 4 | high |  |
| `renderAssetFinanceSyncStat` | function | 26684-26703 | 20 | high |  |
| `renderAssetFinanceMetalsResearchSection` | function | 26832-26851 | 20 | high |  |
| `getAssetFinanceBondRows` | function | 26853-26858 | 6 | high |  |
| `isAssetFinanceTaiwanBond` | function | 26860-26863 | 4 | high |  |
| `filterAssetFinanceBondRows` | function | 26865-26867 | 3 | high |  |
| `getAssetFinanceBondFocusKey` | function | 26869-26875 | 7 | high |  |
| `getAssetFinanceRateMoveTone` | function | 26877-26882 | 6 | high |  |
| `getAssetFinanceBondFocusKind` | function | 26884-26894 | 11 | high |  |
| `buildAssetFinanceBondFocusEtfPulse` | function | 26896-26926 | 31 | high |  |
| `buildAssetFinanceBondFocusMetricSet` | function | 26928-26990 | 63 | high |  |
| `buildAssetFinanceBondYieldFocusInsight` | function | 26992-27056 | 65 | high |  |
| `buildAssetFinanceBondDashboardCommentary` | function | 27058-27150 | 93 | high |  |
| `getAssetFinanceBondCommentaryPoints` | function | 27152-27165 | 14 | high |  |
| `renderAssetFinanceBondCommentarySection` | function | 27167-27178 | 12 | high |  |
| `renderAssetFinanceBondDashboardCommentary` | function | 27180-27206 | 27 | high |  |
| `buildAssetFinanceBondMacroContext` | function | 27208-27378 | 171 | high |  |
| `renderAssetFinanceBondDecisionOverview` | function | 27380-27438 | 59 | high |  |
| `renderAssetFinanceBondCenterDashboard` | function | 27440-27551 | 112 | high |  |
| `renderAssetFinanceBondRegionalMarketPanel` | function | 27553-27676 | 124 | high |  |
| `renderAssetFinanceBondEtfCenterPanel` | function | 27678-27821 | 144 | high |  |
| `renderAssetFinanceBondsResearchSection` | function | 27823-27841 | 19 | high |  |
| `renderAssetFinanceCrossReferenceSection` | function | 27843-27858 | 16 | high |  |
| `renderAssetHubFinanceDashboard` | function | 27860-27878 | 19 | high |  |
| `initAssetFinanceBondFocusControls` | function | 27880-27899 | 20 | high |  |
| `renderAssetHubCompactQuotePanel` | function | 27901-27914 | 14 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetHubMetals` | function | 27916-27918 | 3 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetHubBonds` | function | 27920-27951 | 32 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `createAssetHubPlaceholder` | function | 27953-27970 | 18 | medium | groups=asset-hub (bonds/derivatives-assets/international-finance/precious-metals.html) / derivatives-analytics (derivatives-analytics.html) |
| `getDerivativeOverviewItems` | function | 27972-27991 | 20 | high |  |
| `renderDerivativeOverviewQuote` | function | 27993-28008 | 16 | high |  |
| `renderDerivativeOverviewMetric` | function | 28010-28018 | 9 | high |  |
| `getDerivativeOverviewTechnicalModel` | function | 28034-28068 | 35 | high |  |
| `renderDerivativeOverviewInstitutionSummary` | function | 28070-28155 | 86 | high |  |
| `buildDerivativeFuturesPositionAnalysis` | function | 28157-28217 | 61 | high |  |
| `renderDerivativeFuturesPositionCard` | function | 28219-28244 | 26 | high |  |
| `renderDerivativeOverviewInstitution` | function | 28246-28283 | 38 | high |  |
| `getDerivativeOverviewNewsImpact` | function | 28285-28325 | 41 | high |  |
| `buildDerivativeOverviewImpactModel` | function | 28327-28425 | 99 | high |  |
| `renderDerivativeOverviewNews` | function | 28427-28486 | 60 | high |  |
| `renderDerivativesMarketOverview` | function | 28488-28724 | 237 | high |  |
| `renderAssetHubPage` | function | 28726-28884 | 159 | high |  |
| `initAssetHubPage` | function | 28886-28997 | 112 | high |  |
| `renderDerivativePcrHistory` | function | 33239-33267 | 29 | high |  |
| `renderDerivativeNewsItems` | function | 33269-33273 | 5 | high |  |
| `renderDerivativeBasisCard` | function | 33275-33291 | 17 | high |  |
| `renderInstitutionPositionCard` | function | 33293-33313 | 21 | high |  |
| `loadDerivativesAssetHubPayloads` | function | 33315-33340 | 26 | high |  |
| `renderDerivativePayloadSnapshot` | function | 33342-33364 | 23 | high |  |
| `renderDerivativesAssetSnapshotGrid` | function | 33366-33375 | 10 | high |  |
| `initDerivativesAnalyticsPage` | function | 33377-33454 | 78 | high |  |
| `renderDerivativeAiReport` | function | 33456-33473 | 18 | high |  |
| `renderDerivativeAiArchitectureCard` | function | 33475-33516 | 42 | high |  |
| `initDerivativesAiPage` | function | 33518-33520 | 3 | high |  |

### js/page-tw.js

111 個符號(函式 111、狀態 0),共 4173 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `getWeightedIndexSector` | function | 748-750 | 3 | high |  |
| `normalizeComparisonSeries` | function | 855-864 | 10 | high |  |
| `aggregateSectorSeriesByWeek` | function | 866-902 | 37 | high |  |
| `aggregateSectorSeriesByMonth` | function | 904-941 | 38 | high |  |
| `aggregateIntradaySectorSeries` | function | 943-971 | 29 | high |  |
| `getSectorSeriesForMode` | function | 973-1024 | 52 | high |  |
| `buildSectorComparisonModel` | function | 1026-1062 | 37 | high |  |
| `renderSectorComparisonChart` | function | 1064-1219 | 156 | high |  |
| `renderSectorSyncView` | function | 1221-1343 | 123 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildSectorTrendModel` | function | 1345-1392 | 48 | high |  |
| `renderSectorTrendChart` | function | 1394-1570 | 177 | high |  |
| `isLeveragedSectorDefault` | function | 1718-1721 | 4 | high |  |
| `hasUsableComparisonSeries` | function | 1723-1725 | 3 | high |  |
| `hasYahooChartSymbol` | function | 1727-1729 | 3 | high |  |
| `pickDefaultSectorSyncItem` | function | 1731-1748 | 18 | high |  |
| `getSectorSyncPickerItems` | function | 1750-1765 | 16 | high |  |
| `renderCompactSectorSyncPicker` | function | 1767-1786 | 20 | high |  |
| `normalizeSectorCategoryText` | function | 1798-1805 | 8 | high |  |
| `sectorCategoryTextMatches` | function | 1807-1812 | 6 | high |  |
| `buildSectorHeroInsight` | function | 1825-1835 | 11 | high |  |
| `renderYahooCategoryLinks` | function | 1837-1847 | 11 | high |  |
| `loadYahooSectorCategory` | function | 1849-1897 | 49 | high |  |
| `ensureDefaultYahooSectorCategory` | function | 1899-1921 | 23 | high |  |
| `mergeYahooSectorChartPayload` | function | 1923-1939 | 17 | high |  |
| `loadYahooSectorStockChart` | function | 1941-1977 | 37 | high |  |
| `renderSectorGroup` | function | 2102-2254 | 153 | high |  |
| `shouldRenderSectorPageRanking` | function | 2361-2364 | 4 | high |  |
| `getSectorPageRankingTitle` | function | 2366-2370 | 5 | high |  |
| `bindSectorComparisonTooltips` | function | 2372-2434 | 63 | high |  |
| `findYahooSectorSourceItem` | function | 2436-2445 | 10 | high |  |
| `bindSectorSyncControls` | function | 2447-2528 | 82 | high |  |
| `renderSectorPageV2` | function | 2530-2607 | 78 | high |  |
| `renderSectorSyncViewV2` | function | 2609-2727 | 119 | high |  |
| `getVolatilityBundle` | function | 2729-2731 | 3 | high |  |
| `normalizeInternationalIndexItem` | function | 2733-2751 | 19 | high |  |
| `getInternationalIndexItems` | function | 2753-2775 | 23 | high |  |
| `loadInternationalIndexesIfNeeded` | function | 2777-2801 | 25 | high |  |
| `startVixPolling` | function | 2803-2805 | 3 | high |  |
| `isVixComparisonItem` | function | 2807-2809 | 3 | high |  |
| `getComparisonItemLatestValue` | function | 2811-2815 | 5 | high |  |
| `getComparisonItemPreviousValue` | function | 2817-2821 | 5 | high |  |
| `buildVixSentimentMetrics` | function | 2823-2843 | 21 | high |  |
| `buildSingleIndexQuoteMetrics` | function | 2845-2859 | 15 | high |  |
| `buildInternationalSelectionMetrics` | function | 2861-2883 | 23 | high |  |
| `alignIndexSeries` | function | 2885-2908 | 24 | high |  |
| `renderFreeIndexComparisonChart` | function | 2910-3003 | 94 | high |  |
| `renderIndexComparisonInsight` | function | 3005-3053 | 49 | high |  |
| `renderSingleIndexComparisonInsight` | function | 3055-3098 | 44 | high |  |
| `renderWeightedTechnicalInsightCard` | function | 3100-3193 | 94 | high |  |
| `getWeightedComponentSectorCandidates` | function | 3195-3207 | 13 | high |  |
| `getWeightedSectorThemeMatches` | function | 3242-3245 | 4 | high |  |
| `calculateReturnPct` | function | 3247-3253 | 7 | high |  |
| `averageFinite` | function | 3260-3264 | 5 | high |  |
| `percentileScore` | function | 3266-3273 | 8 | high |  |
| `scoreRangePosition` | function | 3275-3283 | 9 | high |  |
| `buildWeightedSectorTrendModels` | function | 3285-3500 | 216 | high |  |
| `buildWeightedSectorThemeContext` | function | 3502-3543 | 42 | high |  |
| `buildWeightedSectorMarketContext` | function | 3545-3575 | 31 | high |  |
| `renderWeightedSectorTrendFocus` | function | 3577-3602 | 26 | high |  |
| `renderWeightedSectorThemeContext` | function | 3604-3630 | 27 | high |  |
| `renderWeightedSectorTrendRecommendationCard` | function | 3632-3693 | 62 | high |  |
| `getVixRiskTemperature` | function | 3695-3698 | 4 | high |  |
| `getVixRiskToneClass` | function | 3700-3703 | 4 | high |  |
| `renderVixTemperatureMeter` | function | 3705-3720 | 16 | high |  |
| `renderSectorVixSparkline` | function | 3722-3773 | 52 | high |  |
| `renderVixRuleList` | function | 3775-3799 | 25 | high |  |
| `renderVolatilitySwitchCard` | function | 3801-3850 | 50 | high |  |
| `renderWeightedChartZoomControls` | function | 3852-3863 | 12 | high |  |
| `renderWeightedIndexPanel` | function | 3865-4030 | 166 | high |  |
| `bindWeightedPanelHover` | function | 4032-4089 | 58 | high |  |
| `renderSectorsPage` | function | 5180-5182 | 3 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `getPortfolioSimulation` | function | 5217-5224 | 8 | high |  |
| `savePortfolioSimulation` | function | 5226-5228 | 3 | high |  |
| `formatSimulationMoney` | function | 5230-5234 | 5 | high |  |
| `classifyPortfolioAsset` | function | 5414-5419 | 6 | high |  |
| `estimatePortfolioTransactionCost` | function | 5421-5429 | 9 | high |  |
| `buildPortfolioFactorAssessment` | function | 5431-5540 | 110 | high |  |
| `renderPortfolioSimulator` | function | 5568-5719 | 152 | high |  |
| `buildWatchlistAiAnalysis` | function | 8464-8604 | 141 | high |  |
| `renderWatchlistAiSummary` | function | 8606-8638 | 33 | high |  |
| `renderWatchlist` | function | 8640-8724 | 85 | high |  |
| `loadWatchlistAiAnalyses` | function | 8726-8784 | 59 | high |  |
| `renderWatchlistSearchResults` | function | 8786-8824 | 39 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `initWatchlistPage` | function | 8843-8862 | 20 | high |  |
| `renderSearchResults` | function | 8864-8899 | 36 | high |  |
| `loadFullStockDetailFromLive` | function | 32927-32978 | 52 | high |  |
| `renderLiveSearchStockPreview` | function | 32980-33004 | 25 | high |  |
| `loadShareholderDistributionFromLive` | function | 33006-33045 | 40 | high |  |
| `loadStockDetail` | function | 33047-33094 | 48 | high |  |
| `pickPreferredStockResult` | function | 33096-33102 | 7 | high |  |
| `runStockSearch` | function | 33139-33187 | 49 | high |  |
| `initSearchPage` | function | 33189-33224 | 36 | high |  |
| `twEtfCompactNumber` | function | 33522-33528 | 7 | high |  |
| `twEtfItemLink` | function | 33536-33541 | 6 | high |  |
| `renderTwEtfRankingList` | function | 33559-33573 | 15 | high |  |
| `renderTwEtfCompareTable` | function | 33575-33604 | 30 | high |  |
| `renderTwEtfFilterForm` | function | 33606-33627 | 22 | high |  |
| `getTwEtfPage` | function | 33629-33643 | 15 | high |  |
| `renderTwEtfPager` | function | 33645-33669 | 25 | high |  |
| `setTwEtfPage` | function | 33671-33690 | 20 | high |  |
| `renderTwEtfTable` | function | 33692-33724 | 33 | high |  |
| `twEtfHasValue` | function | 33726-33729 | 4 | high |  |
| `renderTwEtfAnalysisBullets` | function | 33737-33758 | 22 | high |  |
| `renderTwEtfComponentsCard` | function | 33760-33790 | 31 | high |  |
| `renderTwEtfDividendCard` | function | 33792-33831 | 40 | high |  |
| `renderTwEtfDetail` | function | 33833-33871 | 39 | high |  |
| `bindTwEtfEvents` | function | 33873-33916 | 44 | high |  |
| `renderTwEtfPage` | function | 33918-33963 | 46 | high |  |
| `loadTwEtfDetail` | function | 33965-33979 | 15 | high |  |
| `loadTwEtfPage` | function | 33981-34033 | 53 | high |  |
| `initTwEtfPage` | function | 34035-34037 | 3 | high |  |

### js/main.js

2 個符號(函式 2、狀態 0),共 88 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `renderCurrentPage` | function | 34039-34078 | 40 | high | 手動指名覆蓋(與同族 state 存取器耦合) |
| `loadLiveData` | function | 34080-34127 | 48 | high | 手動指名覆蓋(與同族 state 存取器耦合) |

### (暫不歸類——見發現④,遷移前需逐一人工核實實際呼叫點)

58 個符號(函式 58、狀態 0),共 1614 行。

| 符號 | 種類 | 行號 | 行數 | 信心 | 備註 |
|---|---|---|---|---|---|
| `normalizeStockSearchTerm` | function | 401-403 | 3 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `searchStocksLocally` | function | 405-442 | 38 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildClientInstitutionalTradeRecord` | function | 540-558 | 19 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildClientInstitutionalTradeSummary` | function | 573-587 | 15 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildPendingInstitutionalTradeHistory` | function | 662-676 | 15 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `alignSectorSeries` | function | 838-853 | 16 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildWeightedVixComparisonModel` | function | 1572-1602 | 31 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `getSectorRankingChangeValue` | function | 1979-1986 | 8 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `sortSectorsByChange` | function | 1988-1996 | 9 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderVixSentimentRules` | function | 4569-4588 | 20 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildMarketInsightNotes` | function | 4590-4649 | 60 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `runWatchlistSearch` | function | 8826-8841 | 16 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `alignAndNormalizeSeries` | function | 9006-9026 | 21 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderGlobalTechnicalAnalysis` | function | 10394-10461 | 68 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderUsEtfDetailSignalCard` | function | 11287-11295 | 9 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderUsEtfDetailFact` | function | 11297-11305 | 9 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderUsEtfDetailBriefCard` | function | 11381-11392 | 12 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `loadUsNyseListedStocks` | function | 11795-11797 | 3 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderFuturesMarketFramework` | function | 13633-13678 | 46 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderFuturesAiModules` | function | 13680-13722 | 43 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderFuturesProductMatrix` | function | 13724-13753 | 30 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `clampFuturesVisualValue` | function | 14942-14946 | 5 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `getFuturesFiniteVisualSeries` | function | 14948-14952 | 5 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderFuturesMiniHistogram` | function | 14978-15001 | 24 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderFuturesIndicatorGauge` | function | 15003-15013 | 11 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderFuturesIndicatorPlot` | function | 15015-15084 | 70 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderFuturesAnalysisMetric` | function | 15086-15094 | 9 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderFuturesAdvancedTechnicalPanel` | function | 15183-15273 | 91 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildOptionsAnalysisCenterModelLegacy` | function | 15954-16022 | 69 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsAnalysisCenterLegacy` | function | 16024-16091 | 68 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `getOptionsPlatformReadiness` | function | 16505-16519 | 15 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsPlatformConsole` | function | 16521-16692 | 172 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsRiskCone` | function | 17204-17213 | 10 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsInsightFeed` | function | 17533-17548 | 16 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsFocusSelector` | function | 17550-17565 | 16 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsHeroMarketPanel` | function | 17648-17690 | 43 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsCoreModelGrid` | function | 17877-17918 | 42 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `getOptionsChainSourceKey` | function | 17988-17993 | 6 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `getOptionsMarketChainSymbolLabel` | function | 18075-18084 | 10 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsDecisionBrief` | function | 18778-18847 | 70 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderOptionsUsChainCard` | function | 18875-18900 | 26 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderDerivativeAssetSummarySection` | function | 18910-18916 | 7 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `removeUsWatchlistSymbol` | function | 22367-22373 | 7 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `loadUsWatchlistSymbol` | function | 22950-22966 | 17 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `runUsWatchlistSearch` | function | 22968-22987 | 20 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetFinanceInternationalTrendPanel` | function | 24523-24529 | 7 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetFinanceGlobalMarketPanel` | function | 24671-24688 | 18 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetFinancePriceForecastPanel` | function | 24903-24909 | 7 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetFinanceEtfRows` | function | 25424-25439 | 16 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetFinanceSelectableEtfRows` | function | 25441-25458 | 18 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetFinanceEtfPanel` | function | 25557-25593 | 37 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetFinanceCompareRow` | function | 26705-26721 | 17 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `describeAssetFinanceTaiwanSync` | function | 26723-26745 | 23 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderAssetFinanceTaiwanPanel` | function | 26747-26830 | 84 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `buildDerivativeOverviewConclusion` | function | 28020-28032 | 13 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `loadLiveStockDirectory` | function | 33104-33137 | 34 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `twEtfSignedPct` | function | 33530-33534 | 5 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |
| `renderTwEtfSummary` | function | 33543-33557 | 15 | low | 無法從任何已知入口到達,可能為死碼或動態引用,遷移前需人工確認實際呼叫點 |

---

## 9. 待使用者裁決的問題(Part 2 開始前需回答)

1. **接受發現②③的合併嗎?** 也就是把工單原表格的 `page-us.js`
   (只剩 `global-market(us)` 那部分)與 `page-derivatives.js` 整個合併成
   一個 `js/page-global-market.js`(370 符號、14,141 行、7 個批次),
   `page-us.js` 縮小為只有 `us-stock-search`/`us-etf`/`us-watchlist`
   (66 符號)?這是本文件的核心建議,理由見第 0 節發現②③,程式碼證據
   已列出實際函式對。若不接受合併,唯一的替代方案是複製部分函式到兩個
   檔案(違反工單「禁止複製多份」的硬性規則),不建議。
2. **接受批次數從 8-12 批增加到 22 批嗎?** 主因是 page-global-market
   單一模組就需要 7 批。若要縮減批次數,可考慮放寬單批上限(如
   80 函式/4,000 行),但這樣每批次的可審查性會下降,是否值得抓歷史
   工單(如 TD-05)的批次節奏抓一個折衷值,請裁決。
3. **批次 21(unclassified,58 個符號)的處理方式?** 目前建議是遷移前
   逐一核實呼叫情形,但不刪除任何一個(即使確認是死碼)。是否要在
   確認後,對其中真正確認是死碼的項目額外標記(不刪除,只是註記),
   併入或擴充 TD-15 的死碼清單(TD-15 目前只有 16-17 項,這次多出的
   91 個函式+7 個狀態變數是全新發現,遠超原本規模)?這部分不屬於
   TD-02 的行為範圍,只是提議是否要另開回報。
4. **`derivatives-ui.js`(85 行,derivatives-status.html 專屬)要不要
   一併處理?** 目前判定不在本工單範圍(範圍明文只有 app.js/styles.css),
   但既然它是唯一一個有獨立第三支腳本的頁面,是否要在 TD-02 之外另開
   一個小工單追蹤,或留給未來的 TD-18(建置工具)一併看,請裁決。
5. **CSS 精確切分要現在做還是留到各批次搬移當下再做?** 本文件第 6 節
   建議留到搬移當下(理由見該節),但如果你希望在 Part 2 開始前就有一份
   完整的 CSS selector → 目標檔案對照表,我可以另外花時間做,請告知。

---

## 10. 下一步

第一部分(依賴盤點與切片計畫)到此完成,依你的指示停下回報。等你確認
第 9 節的裁決後,再依批次計畫開始第二部分(實際搬移),每批次流程依
工單第 5 節「單批執行規範」與第 6 節「兩層驗證」執行,每批獨立 commit。
