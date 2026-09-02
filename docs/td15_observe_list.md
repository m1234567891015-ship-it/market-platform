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

## H-04-11 重評結果(2026-08-30)

第一條 institutional trade 疑似死碼鏈已完成整鏈重評並移除:
`buildTwseInstitutionTradeUrl`、`fetchClientInstitutionalTradeForDate`、
`fetchClientInstitutionalTradeHistory`、`buildClientInstitutionalTradeRecord`、
`buildClientInstitutionalTradeSummary`。重評確認根入口無產品呼叫者、無頁面
入口或 interaction manifest 依賴,且鏈外無 runtime 呼叫；同步移除 frozen
global-symbol baseline 中的 5 個符號。`fetchWithTimeout` 為全站共用函式,保留。

其餘 4 條疑似死碼鏈仍維持觀察狀態,需各自完成同樣的整鏈三方證據後才可處理。

## H-04-12 重評結果(2026-08-30)

第二條 weighted VIX comparison 疑似死碼鏈已完成整鏈重評並移除:
`buildWeightedVixComparisonModel` 與 `renderWeightedVixComparisonChart`。重評確認
產品 runtime 僅存在前者被後者呼叫的鏈內關係,無頁面入口或 interaction manifest
依賴,且鏈外無 runtime 呼叫；同步移除 frozen global-symbol baseline 中的 2 個符號。

其餘 3 條疑似死碼鏈仍維持觀察狀態,需各自完成同樣的整鏈三方證據後才可處理。

## H-04-13 重評結果(2026-08-30)

第三條 futures mini sparkline 疑似死碼鏈已完成整鏈重評並移除:
`getFuturesFiniteVisualSeries` 與 `renderFuturesMiniSparkline`。重評確認
產品 runtime 僅存在前者被後者呼叫的鏈內關係,無頁面入口或 interaction manifest
依賴,且鏈外無 runtime 呼叫；同步移除 frozen global-symbol baseline 中的 2 個符號，
並將 `escapeHtml` 呼叫次數基準由 1905 同步調整為 1904。

其餘 2 條疑似死碼鏈仍維持觀察狀態,需各自完成同樣的整鏈三方證據後才可處理。

## H-04-14 重評結果(2026-08-30)

第四條 futures indicator switch 疑似死碼鏈已完成整鏈重評並移除:
`renderFuturesIndicatorPlot` 與 `renderFuturesIndicatorSwitchChart`。重評確認
產品 runtime 僅存在前者被後者呼叫的鏈內關係,無頁面入口或 interaction manifest
依賴,且鏈外無 runtime 呼叫；同步移除 frozen global-symbol baseline 中的 2 個符號，
並將 `escapeHtml` 呼叫次數基準由 1904 同步調整為 1895。

其餘 1 條疑似死碼鏈仍維持觀察狀態,需完成同樣的整鏈三方證據後才可處理。

## H-04-15 重評結果(2026-08-30)

第五條 US watchlist 疑似死碼鏈已完成整鏈重評並移除:
`loadUsWatchlistSymbol` 與 `renderUsWatchlistSearchResults`。重評確認
`renderUsWatchlistSearchResults` 僅被已刪除的 `runUsWatchlistSearch` 與自身遞迴呼叫,
`initUsWatchlistPage` 未建立此鏈的入口,且鏈外無 runtime 或 interaction manifest 依賴；
同步移除 frozen global-symbol baseline 中的 2 個符號，並將 `escapeHtml` 呼叫次數基準由
1895 同步調整為 1887。

TD-15 這 5 條額外疑似死鏈均已完成整鏈三方重評並處理完畢。

## 統計

- 標記符號數:6
- 已完成整鏈重評:5 條
- 尚待重評:0 條
- `console.warn` 執行期偵測:本輪未加(裁決:避免行為變更副作用)
- 下一輪待辦:本觀察清單 5 條疑似死鏈已完成處理；若新增 TD-15 候選，依同樣的
  「整條呼叫鏈」三方證據另立批次，不回溯已結案鏈

## 2026-09-01 REMAIN closure update

本觀察清單沒有新增項目。TD15-REMAIN-04～07 的 CSS review 已完成，CSS 最終沒有 deletion candidate；本清單維持歷史 JS observe／closed-for-now 紀錄，不回溯刪除既有鏈。

## R3 現況重核結果（2026-08-31）

已以 [td15_js_residual_audit.py](../regression/td15_js_residual_audit.py) 重建目前 JS residual 證據：`js/legacy-unclassified.js` 為 0 bytes、top-level declaration=0；歷史 58 個符號在目前 HTML／JS／CSS／Python 執行來源為 0 literal hit，`window[...]` dynamic access 亦無任何候選命中。R3 判定 `R3_PASS_NO_DELETION`，不重複處理 H-04-11～H-04-15，也不更新 global-symbol baseline。
