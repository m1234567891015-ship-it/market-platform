# TD-15 第二層觀察清單(標記日期:2026-07-25)

依工單 TD-15 第 3 部分,以下 6 個符號屬第二層(AST 不可達,但字串掃描在 repo
內找到其他活著檔案的引用,依「寧可漏刪」原則不滿足第一層三重證據全過的門檻,
本輪不刪除)。每個符號已在 `js/legacy-unclassified.js` 原始位置加註
`@TD-15-OBSERVE (2026-07-25)` 標記,含各自的呼叫者依據。本輪未加
`console.warn`(避免任何行為/副作用變更),僅加註解。

## 額外發現:疑似死鏈死碼群(裁決要求記錄)

逐一追查這 6 個符號的呼叫者後發現:**它們各自唯一的呼叫者,本身也都是零
呼叫者、不在任何 21 頁入口鏈上的孤兒函式**。也就是說,這不是「6 個獨立、
真的被使用的符號」,而更可能是「6 段死碼鏈,只是鏈的兩端剛好落在 TD-02
依原始檔案位置切分時被分到不同檔案」。TD-15 本輪的字面證據標準(字串形式
只要在 repo 任何地方出現就不算第一層全過)偵測不到「呼叫者本身也是死的」
這種情況,這正是本輪選擇保守標記、不深入判斷的原因。

**下一輪處理建議**:重新評估時應該把整條呼叫鏈(不只終端符號)一起納入
可達性分析,而不是只看 `js/legacy-unclassified.js` 內部這幾個符號本身。

## 完整呼叫鏈清單

### 1-2. `buildClientInstitutionalTradeRecord` / `buildClientInstitutionalTradeSummary`

- 位置:`js/legacy-unclassified.js`
- 直接呼叫者:`js/api.js` 的 `fetchClientInstitutionalTradeHistory`(第 21 行起)
- 呼叫鏈根節點狀態:`fetchClientInstitutionalTradeHistory` 在整個 repo
  搜尋不到任何呼叫者(只有自己的宣告),疑似整條鏈都是死碼

### 3. `buildWeightedVixComparisonModel`

- 位置:`js/legacy-unclassified.js`
- 直接呼叫者:`js/charts.js` 的 `renderWeightedVixComparisonChart`
- 呼叫鏈根節點狀態:`renderWeightedVixComparisonChart` 在整個 repo
  搜尋不到任何呼叫者,疑似整條鏈都是死碼

### 4. `getFuturesFiniteVisualSeries`

- 位置:`js/legacy-unclassified.js`
- 直接呼叫者:`js/page-global-market-futures.js` 的 `renderFuturesMiniSparkline`
- 呼叫鏈根節點狀態:`renderFuturesMiniSparkline` 只被
  `js/legacy-unclassified.js` 內部的 `renderFuturesAnalysisMetric` 系列
  呼叫者呼叫(這批呼叫者已在 TD-15 Layer 1 刪除),疑似整條鏈都是死碼

### 5. `renderFuturesIndicatorPlot`

- 位置:`js/legacy-unclassified.js`
- 直接呼叫者:`js/page-global-market-futures.js` 的
  `renderFuturesIndicatorSwitchChart`(3 處呼叫)
- 呼叫鏈根節點狀態:`renderFuturesIndicatorSwitchChart` 在整個 repo
  搜尋不到任何呼叫者,疑似整條鏈都是死碼

### 6. `loadUsWatchlistSymbol`

- 位置:`js/legacy-unclassified.js`
- 直接呼叫者:`js/page-us.js` 的 `renderUsWatchlistSearchResults`
  (透過 `addEventListener("click", ...)`)
- 呼叫鏈根節點狀態:`renderUsWatchlistSearchResults` 只被
  `runUsWatchlistSearch`(`js/legacy-unclassified.js`,已在 TD-15 Layer 1
  刪除,刪除前確認零呼叫者)呼叫,以及遞迴呼叫自己;真正的
  `us-watchlist.html` 入口點 `initUsWatchlistPage` 不呼叫這整條鏈中的
  任何函式,疑似整條鏈都是死碼

## 統計

- 標記符號數:6
- `console.warn` 執行期偵測:本輪未加(裁決:避免行為變更副作用)
- 下一輪待辦:重新以「整條呼叫鏈」為單位做可達性分析,若確認鏈根節點
  (`fetchClientInstitutionalTradeHistory`/`renderWeightedVixComparisonChart`/
  `renderFuturesIndicatorSwitchChart`/`runUsWatchlistSearch` 呼叫路徑相關函式)
  也符合三重證據,則整條鏈(含這 6 個 + 各自的呼叫者)一併降級為可刪除
