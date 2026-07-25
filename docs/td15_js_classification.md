# TD-15 JS 符號分類表(第一輪,js/legacy-unclassified.js)

依工單 TD-15 第 2 節三重證據標準逐一判定。

**重要更正**:工單開場指令提到「98 個」JS 符號,但 `js/legacy-unclassified.js`
目前實際只有 **58 個**頂層符號(TD-02 批次 22 commit 4cddc9e 的實際搬移數字)。
「98」應是 TD-02 Part 1 盤點階段的粗估(見 `docs/frontend_module_map.md`「無法從任何
已知入口到達」的初步統計),實際執行搬移時精確盤點後確定是 58 個,兩者落差 40。
本分類表以`js/legacy-unclassified.js`**目前實際存在**的 58 個符號為準,不是憑空湊出 98 個。

## 方法

1. **AST 可達性**:與字串掃描證據(下一項)等價——若整個 repo 找不到任何字串形式的
   引用,AST 可達性分析也不可能找到呼叫邊。因此本表用字串掃描的結果同時代表兩項證據。
2. **字串掃描**:對每個符號名在整個 repo(21 個 `.html`、`js/*.js`、`app.js`、
   `split-*.css`、所有 `.py`、`regression/*.py`)做純文字比對(word-boundary,排除子字串
   誤配)。`docs/*.md`、`regression/*.md` 純文件提及(例如本工單自己的分類表、
   `interaction_inventory.md` 的既有死碼記錄)**不算引用**——這些是文件不是可執行程式碼,
   不构成動態呼叫風險,不計入判定。
3. **動態呼叫模式排除**:檢查 `js/legacy-unclassified.js` 全檔——確認沒有
   `window[...]`、`this[...]`、`obj[variable]`、`eval`、`new Function`、
   `setAttribute("on...")` 這類會用變數取用符號的模式(**檔案全域掃描結果:無**,
   下表每一列此項皆同,不重複列出個別依據)。

## 分類表

| 符號名 | 所在行號 | 字串掃描(repo 內非文件引用) | 判定 | 依據 |
|---|---|---|---|---|
| `normalizeStockSearchTerm` | js/legacy-unclassified.js:1 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `searchStocksLocally` | js/legacy-unclassified.js:4 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `buildClientInstitutionalTradeRecord` | js/legacy-unclassified.js:42 | 有 | 第二層(標記觀察) | js/api.js:19 (real call, inside fetchClientInstitutionalTradeHistory — but that caller itself has zero callers anywhere, so still an isolated dead cluster; disqualified from Layer 1 purely on the literal no-external-string-hit rule) |
| `buildClientInstitutionalTradeSummary` | js/legacy-unclassified.js:61 | 有 | 第二層(標記觀察) | js/api.js:55 (same caller, fetchClientInstitutionalTradeHistory, as above) |
| `buildPendingInstitutionalTradeHistory` | js/legacy-unclassified.js:76 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `alignSectorSeries` | js/legacy-unclassified.js:91 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `buildWeightedVixComparisonModel` | js/legacy-unclassified.js:107 | 有 | 第二層(標記觀察) | js/charts.js:86-87 (real call, inside renderWeightedVixComparisonChart — that function itself has zero callers anywhere) |
| `getSectorRankingChangeValue` | js/legacy-unclassified.js:138 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `sortSectorsByChange` | js/legacy-unclassified.js:146 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderVixSentimentRules` | js/legacy-unclassified.js:155 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `buildMarketInsightNotes` | js/legacy-unclassified.js:175 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `runWatchlistSearch` | js/legacy-unclassified.js:235 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `alignAndNormalizeSeries` | js/legacy-unclassified.js:251 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderGlobalTechnicalAnalysis` | js/legacy-unclassified.js:272 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderUsEtfDetailSignalCard` | js/legacy-unclassified.js:340 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderUsEtfDetailFact` | js/legacy-unclassified.js:349 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderUsEtfDetailBriefCard` | js/legacy-unclassified.js:358 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `loadUsNyseListedStocks` | js/legacy-unclassified.js:370 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderFuturesMarketFramework` | js/legacy-unclassified.js:373 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderFuturesAiModules` | js/legacy-unclassified.js:419 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderFuturesProductMatrix` | js/legacy-unclassified.js:462 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `clampFuturesVisualValue` | js/legacy-unclassified.js:492 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `getFuturesFiniteVisualSeries` | js/legacy-unclassified.js:497 | 有 | 第二層(標記觀察) | js/page-global-market-futures.js:3549 (real call, inside renderFuturesMiniSparkline — that function is only ever called from within legacy-unclassified.js itself, no external caller) |
| `renderFuturesMiniHistogram` | js/legacy-unclassified.js:502 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderFuturesIndicatorGauge` | js/legacy-unclassified.js:526 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderFuturesIndicatorPlot` | js/legacy-unclassified.js:537 | 有 | 第二層(標記觀察) | js/page-global-market-futures.js:3598/3604/3610/3619/3625/3628/3633 (real calls, inside renderFuturesIndicatorSwitchChart — that function itself has zero callers anywhere) |
| `renderFuturesAnalysisMetric` | js/legacy-unclassified.js:607 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderFuturesAdvancedTechnicalPanel` | js/legacy-unclassified.js:616 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `buildOptionsAnalysisCenterModelLegacy` | js/legacy-unclassified.js:707 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsAnalysisCenterLegacy` | js/legacy-unclassified.js:776 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `getOptionsPlatformReadiness` | js/legacy-unclassified.js:844 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsPlatformConsole` | js/legacy-unclassified.js:859 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsRiskCone` | js/legacy-unclassified.js:1031 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsInsightFeed` | js/legacy-unclassified.js:1041 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsFocusSelector` | js/legacy-unclassified.js:1057 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsHeroMarketPanel` | js/legacy-unclassified.js:1073 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsCoreModelGrid` | js/legacy-unclassified.js:1116 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `getOptionsChainSourceKey` | js/legacy-unclassified.js:1158 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `getOptionsMarketChainSymbolLabel` | js/legacy-unclassified.js:1164 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsDecisionBrief` | js/legacy-unclassified.js:1174 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderOptionsUsChainCard` | js/legacy-unclassified.js:1244 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderDerivativeAssetSummarySection` | js/legacy-unclassified.js:1270 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `removeUsWatchlistSymbol` | js/legacy-unclassified.js:1277 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `loadUsWatchlistSymbol` | js/legacy-unclassified.js:1284 | 有 | 第二層(標記觀察) | js/page-us.js:2865 (real call inside an addEventListener, inside renderUsWatchlistSearchResults — that function is only called by runUsWatchlistSearch (legacy-unclassified.js, zero external callers) and recursively by itself; initUsWatchlistPage, the real us-watchlist.html entry point, does not call it) |
| `runUsWatchlistSearch` | js/legacy-unclassified.js:1301 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderAssetFinanceInternationalTrendPanel` | js/legacy-unclassified.js:1321 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderAssetFinanceGlobalMarketPanel` | js/legacy-unclassified.js:1328 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderAssetFinancePriceForecastPanel` | js/legacy-unclassified.js:1346 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderAssetFinanceEtfRows` | js/legacy-unclassified.js:1353 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderAssetFinanceSelectableEtfRows` | js/legacy-unclassified.js:1369 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderAssetFinanceEtfPanel` | js/legacy-unclassified.js:1387 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderAssetFinanceCompareRow` | js/legacy-unclassified.js:1424 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `describeAssetFinanceTaiwanSync` | js/legacy-unclassified.js:1441 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderAssetFinanceTaiwanPanel` | js/legacy-unclassified.js:1464 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `buildDerivativeOverviewConclusion` | js/legacy-unclassified.js:1548 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `loadLiveStockDirectory` | js/legacy-unclassified.js:1561 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `twEtfSignedPct` | js/legacy-unclassified.js:1595 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |
| `renderTwEtfSummary` | js/legacy-unclassified.js:1600 | 無 | 第一層(可刪) | 僅自身宣告 + 檔案內部互相呼叫(同屬待刪叢集),repo 內無其他引用 |

## 統計

- 第一層(可刪候選):52 個
- 第二層(標記觀察,本輪不刪):6 個
- 合計:58 個(非工單開場指令提到的 98,見上方更正說明)

## 第二層符號的補充說明

這 6 個符號都通過了「字面文字沒有隱藏動態呼叫」的檢查,但字串掃描本身抓到
它們被**其他活著的檔案**(`js/api.js`、`js/charts.js`、`js/page-global-market-futures.js`、
`js/page-us.js`)裡的函式呼叫。往上追一層呼叫鏈,追到的呼叫者(`fetchClientInstitutionalTradeHistory`、
`renderWeightedVixComparisonChart`、`renderFuturesMiniSparkline`、`renderFuturesIndicatorSwitchChart`、
`renderUsWatchlistSearchResults`/`runUsWatchlistSearch`)本身也都各自零呼叫者、不在任何頁面
入口鏈上——換句話說,這 6 個符號**可能實際上也是死碼**,只是被 TD-02 依原始檔案位置切分時,
剛好跟它們唯一的呼叫者分到了不同檔案。但依工單第 2 節的字面標準("確認連字串形式都不出現"),
這 6 個在 repo 內**確實有字串形式出現**(只是出現在另一段同樣可能死掉的程式碼裡),不滿足
第一項全過的門檻,所以依規則降級到第二層,不在本輪刪除範圍——這正是「寧可漏刪」原則要處理的
情境:證據上模稜兩可時不刪。