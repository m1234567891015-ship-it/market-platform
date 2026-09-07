# TD02-01 前端依賴矩陣（2026-08-31）

> 本文件是 TD02-01 的盤點產物；不切換 HTML、不移除 classic slices、不修改 baseline/CSP/部署。
> 機器可重現來源為同名 `.json` 與 `regression/td02_01_dependency_matrix.py`。

## 1. 盤點結論

- 21 頁目前 production script order 有 1 種：`market-pulse-esm-loader.js`。
- classic fallback 輸入順序共 17 個檔案，global symbol owner 共 895 個，與 baseline SHA-256 `694e4c8d1c4244befbf37e59cb482575b101bdca1f047497e417cc6b612d519e` 對齊。
- 目前偵測到 69 條跨 slice dependency edges、468 個跨 slice symbol references。
- 需要 TD02-02 處理的互相依賴元件：2 組；TD02-01 不接線、不定義正式 bridge API。

## 2. 現況載入與回退契約

| 層 | 現況 | TD02-01 保留的契約 |
|---|---|---|
| Production | `common-runtime.js → route-bundle.js`；status 頁尾端再載入 addon | 不改 HTML 入口 |
| Classic fallback | `pwa.js → js/state.js → js/core.js → js/api.js → js/shared-calc.js → js/render-shared.js → js/charts.js → js/stock-detail.js → js/page-home.js → js/page-us.js → js/page-global-market-futures.js → js/page-global-market-options.js → js/page-global-market-assethub.js → js/page-tw.js → js/legacy-unclassified.js → js/main.js → app.js` | 仍可立即恢復，順序不可重排 |
| Symbol scope | classic source slices 共享全域作用域 | 每個 symbol 一個 owner；bridge 移除前不得遺失 |
| Safety | `escapeHtml`／innerHTML guard 位於 runtime/core | TD02-02 必須維持單一來源與執行時機 |

## 3. Slice → candidate module → bridge

`candidate_module` 是 TD02-02 的候選命名邊界，不代表本批已建立 ESM 檔案或 export/import。所有 bridge symbol 的完整 owner 與 consumer 在 JSON 的 `symbols`、`required_global_bridge` 可逐項核對。

| classic source | candidate module | bundle | fallback order | owned globals | route pages | immediate cross-slice refs | dependency targets |
|---|---|---|---:|---:|---|---|---|
| `app.js` | `compat/app-shell` | `route-bundle` | 17 | 0 | shared/all pages | — | — |
| `derivatives-ui.js` | `route/derivatives-status-addon` | `derivatives-status-addon` | 18 | 0 | derivatives-status.html | — | js/core.js, js/state.js |
| `js/api.js` | `runtime/api` | `common-runtime` | 4 | 1 | shared/all pages | — | — |
| `js/charts.js` | `runtime/charts` | `common-runtime` | 7 | 9 | shared/all pages | — | js/core.js, js/render-shared.js, js/shared-calc.js, js/state.js |
| `js/core.js` | `runtime/core` | `common-runtime` | 3 | 26 | shared/all pages | nativeInnerHtmlDescriptor | js/state.js |
| `js/legacy-unclassified.js` | `route/legacy-unclassified` | `route-bundle` | 15 | 0 | shared/all pages | — | — |
| `js/main.js` | `runtime/bootstrap` | `route-bundle` | 16 | 2 | shared/all pages | initSearchPage, initWatchlistPage, initGlobalMarketPage, loadYahooSectorCategory | js/api.js, js/core.js, js/page-global-market-assethub.js, js/page-global-market-options.js, js/page-home.js, js/page-tw.js, js/page-us.js, js/state.js |
| `js/page-global-market-assethub.js` | `route/global-market-assethub` | `route-bundle` | 13 | 145 | bonds.html, derivatives-ai.html, derivatives-analytics.html, derivatives-assets.html, international-finance.html, precious-metals.html | fetchWithTimeout | js/api.js, js/core.js, js/page-global-market-futures.js, js/page-global-market-options.js, js/render-shared.js, js/shared-calc.js, js/state.js |
| `js/page-global-market-futures.js` | `route/global-market-futures` | `route-bundle` | 11 | 92 | futures.html, us-market-overview.html, us-stocks.html | — | js/api.js, js/charts.js, js/core.js, js/page-global-market-assethub.js, js/page-global-market-options.js, js/render-shared.js, js/shared-calc.js, js/state.js |
| `js/page-global-market-options.js` | `route/global-market-options` | `route-bundle` | 12 | 131 | options.html | — | js/api.js, js/charts.js, js/core.js, js/page-global-market-assethub.js, js/page-global-market-futures.js, js/render-shared.js, js/state.js |
| `js/page-home.js` | `route/page-home` | `route-bundle` | 9 | 33 | index.html, market-overview.html, news.html | — | js/api.js, js/charts.js, js/core.js, js/render-shared.js, js/state.js |
| `js/page-tw.js` | `route/page-tw` | `route-bundle` | 14 | 111 | tw-etf.html, tw-Optional-stocks.html, tw-stock-search.html, tw-stocks.html | — | js/api.js, js/charts.js, js/core.js, js/main.js, js/render-shared.js, js/shared-calc.js, js/state.js, js/stock-detail.js |
| `js/page-us.js` | `route/page-us` | `route-bundle` | 10 | 65 | us-etf.html, us-stock-search.html, us-watchlist.html | — | js/api.js, js/charts.js, js/core.js, js/render-shared.js, js/shared-calc.js, js/state.js, js/stock-detail.js |
| `js/render-shared.js` | `runtime/render-shared` | `common-runtime` | 6 | 46 | shared/all pages | — | js/api.js, js/core.js, js/shared-calc.js, js/state.js |
| `js/shared-calc.js` | `runtime/shared-calc` | `common-runtime` | 5 | 72 | shared/all pages | — | js/core.js, js/state.js |
| `js/state.js` | `runtime/state` | `common-runtime` | 2 | 152 | shared/all pages | — | — |
| `js/stock-detail.js` | `route/stock-detail` | `common-runtime` | 8 | 10 | shared/all pages | — | js/api.js, js/charts.js, js/core.js, js/render-shared.js, js/shared-calc.js, js/state.js |
| `pwa.js` | `runtime/pwa` | `common-runtime` | 1 | 0 | shared/all pages | — | — |

## 4. 跨 slice dependency edges

以下每列的 symbol 都有唯一 owner；遷移過渡期先視為 required global bridge，TD02-02 再決定改成 named import、deferred entrypoint 或保留 bridge。

| from | to / owner | symbols |
|---|---|---|
| `derivatives-ui.js` | `js/core.js` (`runtime/core`) | `escapeHtml` |
| `derivatives-ui.js` | `js/state.js` (`runtime/state`) | `data` |
| `js/charts.js` | `js/core.js` (`runtime/core`) | `escapeHtml`, `parseMarketNumber`, `toneClass` |
| `js/charts.js` | `js/render-shared.js` (`runtime/render-shared`) | `aggregateHistory`, `buildPath`, `renderCombinedIndicatorPanel`, `sliceVisibleWindow` |
| `js/charts.js` | `js/shared-calc.js` (`runtime/shared-calc`) | `calculateAtr`, `calculateBias`, `calculateBollingerBands`, `calculateCci`, `calculateDmi`, `calculateFibonacciRetracement`, `calculateIchimoku`, `calculateKd`, `calculateMacd`, `calculateMfi`, `calculateMomentum`, `calculateObv`, `calculateParabolicSarSeries`, `calculateRsi`, `calculateSmartMoneyConcepts`, `calculateSupportResistance`, `calculateWilliamsR`, `movingAverage`, `normalizeHistory` |
| `js/charts.js` | `js/state.js` (`runtime/state`) | `TECHNICAL_PANEL_INDICATOR_KEYS` |
| `js/core.js` | `js/state.js` (`runtime/state`) | `nativeInnerHtmlDescriptor` |
| `js/main.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/main.js` | `js/core.js` (`runtime/core`) | `setText` |
| `js/main.js` | `js/page-global-market-assethub.js` (`route/global-market-assethub`) | `initAssetHubPage`, `initDerivativesAiPage`, `initDerivativesAnalyticsPage` |
| `js/main.js` | `js/page-global-market-options.js` (`route/global-market-options`) | `initGlobalMarketPage` |
| `js/main.js` | `js/page-home.js` (`route/page-home`) | `renderHome`, `renderMarketPage` |
| `js/main.js` | `js/page-tw.js` (`route/page-tw`) | `initSearchPage`, `initTwEtfPage`, `initWatchlistPage`, `loadYahooSectorCategory`, `renderSectorPageV2`, `renderWatchlist`, `startVixPolling` |
| `js/main.js` | `js/page-us.js` (`route/page-us`) | `initUsEtfPage`, `initUsStockSearchPage`, `initUsWatchlistPage` |
| `js/main.js` | `js/state.js` (`runtime/state`) | `data`, `localAllStocks` |
| `js/page-global-market-assethub.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/page-global-market-assethub.js` | `js/core.js` (`runtime/core`) | `assetHubTone`, `escapeHtml`, `formatAssetHubExpiration`, `formatAssetOptionIv`, `formatAssetOptionNumber`, `formatAssetOptionWhole`, `formatGlobalValue`, `formatGlobalVolume`, `parseMarketNumber`, `safeUrl` |
| `js/page-global-market-assethub.js` | `js/page-global-market-futures.js` (`route/global-market-futures`) | `buildFuturesCenterModel`, `buildGlobalMarketInsight`, `formatFuturesIndicatorValue`, `getAssetPlatformConfig`, `getFuturesMarketScope`, `renderDerivativeNameMappingCard`, `renderGlobalMarketSections` |
| `js/page-global-market-assethub.js` | `js/page-global-market-options.js` (`route/global-market-options`) | `buildOptionsAiFunctionalModel`, `buildOptionsStrategyRows`, `getActiveTaiwanOptionUnderlying`, `getTaiwanOptionProductLabel`, `renderTaiwanOptionProductTabs` |
| `js/page-global-market-assethub.js` | `js/render-shared.js` (`runtime/render-shared`) | `buildPath`, `buildYahooFinanceUrl`, `fetchDerivativesApi`, `getVixSentimentBand`, `normalizeFuturesTechnicalCandles`, `normalizeGlobalOhlcvSeries`, `normalizeGlobalSeries`, `optionsDecimal`, `optionsPct`, `optionsWhole`, `renderUsBacktestLearningCard` |
| `js/page-global-market-assethub.js` | `js/shared-calc.js` (`runtime/shared-calc`) | `averageFuturesValues`, `buildFuturesTechnicalSnapshot` |
| `js/page-global-market-assethub.js` | `js/state.js` (`runtime/state`) | `ASSET_FINANCE_TREND_FILTERS`, `ASSET_FINANCE_TREND_RANGES`, `ASSET_HUB_OPTION_CHAIN_UNDERLYINGS`, `ASSET_HUB_REGION_ORDER`, `ASSET_HUB_SCHEMA_FALLBACK`, `assetFinanceBondEtfBucketKey`, `assetFinanceBondFocusKey`, `assetFinanceTrendChartCounter`, `derivativesOptionsChainSource`, `derivativesOptionsSelectedStrike`, `derivativesOptionsSelectedUnderlying` |
| `js/page-global-market-futures.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/page-global-market-futures.js` | `js/charts.js` (`runtime/charts`) | `bindHorizontalChartPan`, `getChartHistory`, `renderTechnicalChart` |
| `js/page-global-market-futures.js` | `js/core.js` (`runtime/core`) | `escapeHtml`, `formatAssetOptionWhole`, `formatGlobalValue`, `formatGlobalVolume`, `parseMarketNumber`, `safeUrl`, `toneClass` |
| `js/page-global-market-futures.js` | `js/page-global-market-assethub.js` (`route/global-market-assethub`) | `clampAssetHubScore`, `findAssetHubItem`, `getAssetHubItems`, `getAssetHubMetric`, `getAssetHubRegion`, `getAssetHubUsableItems`, `groupAssetHubItemsByRegion`, `renderAssetHubOnlineTable`, `renderAssetHubQuoteGrid`, `renderFuturesBacktestLearningCard` |
| `js/page-global-market-futures.js` | `js/page-global-market-options.js` (`route/global-market-options`) | `renderGlobalMarketPage` |
| `js/page-global-market-futures.js` | `js/render-shared.js` (`runtime/render-shared`) | `buildPath`, `buildTechnicalTrendSummary`, `buildUsStockSearchUrl`, `getVixSentimentBand`, `normalizeGlobalOhlcvSeries`, `normalizeGlobalSeries`, `renderTechnicalTrendForecastSummary` |
| `js/page-global-market-futures.js` | `js/shared-calc.js` (`runtime/shared-calc`) | `analyzeTechnicalTheories`, `averageFuturesValues`, `buildFuturesTechnicalSnapshot`, `technicalSma` |
| `js/page-global-market-futures.js` | `js/state.js` (`runtime/state`) | `DERIVATIVES_WATCHLIST_STORAGE_KEY`, `DERIVATIVE_ASSET_NAME_MAP`, `FUTURES_TECHNICAL_INTERVAL_OPTIONS`, `TECHNICAL_PANEL_INDICATOR_KEYS`, `TECHNICAL_PANEL_INDICATOR_OPTIONS`, `US_INDUSTRY_SECTOR_SYMBOLS`, `US_MAJOR_INDEX_SECTOR_SYMBOLS`, `US_MAJOR_INDEX_SYMBOLS`, `US_NYSE_DIRECTORY_PAGE_SIZE`, `US_SECTOR_STOCK_SELECTION_KEY`, `US_SP500_SECTOR_SYMBOLS`, `derivativesFuturesDetailSymbol`, `derivativesFuturesFrameworkScope`, `derivativesFuturesMarketScope`, `derivativesFuturesRegionalExpandedKeys`, `derivativesFuturesStockStyleMaState`, `derivativesFuturesStockStyleOverlayState`, `derivativesFuturesStockStylePanState`, `derivativesFuturesStockStylePanelState`, `derivativesFuturesStockStyleVisibleState`, `getFuturesTechnicalCachedPayload`, `getFuturesTechnicalIndicatorStateKey`, `getFuturesTechnicalIntervalLabel`, `getSelectedFuturesTechnicalContract`, `getSelectedFuturesTechnicalInterval`, `usMajorIndexChartSymbol`, `usMajorIndexChartSymbols`, `usMajorIndexPanOffsets`, `usMajorIndexShowVix`, `usMajorIndexZoomCounts`, `usSectorBenchmarkSymbol`, `usSectorCompareSymbol`, `usSectorNyseStockState`, `usSectorStockBenchmarkSymbol`, `usSectorStockSymbol` |
| `js/page-global-market-options.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/page-global-market-options.js` | `js/charts.js` (`runtime/charts`) | `bindChartHover`, `bindHorizontalChartPan` |
| `js/page-global-market-options.js` | `js/core.js` (`runtime/core`) | `assetHubTone`, `escapeHtml`, `formatAssetHubExpiration`, `formatGlobalValue`, `formatGlobalVolume`, `parseMarketNumber`, `safeUrl`, `toneClass` |
| `js/page-global-market-options.js` | `js/page-global-market-assethub.js` (`route/global-market-assethub`) | `clampAssetHubScore`, `findAssetHubItemAny`, `getAssetHubItemUrl`, `getAssetHubItems`, `getAssetHubMetric`, `getAssetHubRegion`, `getAssetHubUsableItems`, `pickTaiwanOptionRows`, `renderAssetHubOnlineTable`, `renderAssetHubRegionalGroups`, `renderTaiwanOptionAnalysis`, `renderTaiwanOptionChainCard`, `renderTaiwanOptionExpiryTabs` |
| `js/page-global-market-options.js` | `js/page-global-market-futures.js` (`route/global-market-futures`) | `bindDerivativeWatchlistControls`, `bindUsMajorIndexVixCard`, `bindUsSectorIndexComparisonCard`, `bindUsSectorStocksBrowser`, `buildUsMarketPulseAnalysis`, `getAssetPlatformConfig`, `getFuturesMarketScope`, `getFuturesScopeDetailConfig`, `getFuturesStockStyleMaPeriods`, `getFuturesStockStyleOverlayIndicators`, `getFuturesStockStylePanelIndicators`, `getUsBenchmarkDisplayName`, `getUsMarketPayloadCounts`, `getUsSectorDisplayName`, `loadUsSectorStocks`, `renderAssetPlatformDashboard`, `renderDerivativeWatchButton`, `renderDerivativesFuturesPanel`, `renderFuturesAnalysisCenter`, `renderGlobalMarketSections`, `renderGlobalSummaryCard`, `renderUsMajorIndexVixCard`, `renderUsSectorIndexComparisonCard`, `renderUsSectorStocksBrowser`, `setFuturesStockStyleStateList` |
| `js/page-global-market-options.js` | `js/render-shared.js` (`runtime/render-shared`) | `buildPath`, `buildUsStockSearchUrl`, `buildYahooFinanceUrl`, `fetchDerivativesApi`, `getVixSentimentBand`, `normalizeFuturesTechnicalCandles`, `normalizeGlobalSeries`, `optionsDecimal`, `optionsNumber`, `optionsPct`, `optionsWhole` |
| `js/page-global-market-options.js` | `js/state.js` (`runtime/state`) | `DERIVATIVES_OPTIONS_AUTO_REFRESH_MS`, `FUTURES_TECHNICAL_INDICATOR_OPTIONS`, `FUTURES_TECHNICAL_INTERVAL_OPTIONS`, `OPTIONS_DOCUMENT_CATEGORY_ORDER`, `OPTIONS_MARKET_CHAIN_FUTURES_SYMBOLS`, `OPTIONS_MARKET_CHAIN_SYMBOL_ALIASES`, `TAIWAN_OPTION_CHAIN_UNDERLYINGS`, `TAIWAN_OPTION_PRODUCT_FALLBACKS`, `TECHNICAL_PANEL_INDICATOR_KEYS`, `US_INDUSTRY_SECTOR_SYMBOLS`, `US_MAJOR_INDEX_SECTOR_SYMBOLS`, `US_MAJOR_INDEX_SYMBOLS`, `US_SP500_SECTOR_SYMBOLS`, `derivativesFuturesDetailSymbol`, `derivativesFuturesFrameworkScope`, `derivativesFuturesMarketScope`, `derivativesFuturesRegionalExpandedKeys`, `derivativesFuturesStockStyleMaState`, `derivativesFuturesStockStyleOverlayState`, `derivativesFuturesStockStylePanState`, `derivativesFuturesStockStylePanelState`, `derivativesFuturesStockStyleVisibleState`, `derivativesFuturesTechnicalContractState`, `derivativesFuturesTechnicalIndicatorState`, `derivativesFuturesTechnicalIntervalState`, `derivativesFuturesTechnicalLoadingKeys`, `derivativesFuturesTechnicalSeriesCache`, `derivativesOptionsAutoRefreshInFlight`, `derivativesOptionsAutoRefreshPayload`, `derivativesOptionsAutoRefreshTimer`, `derivativesOptionsChainSource`, `derivativesOptionsMarketChainInFlightKey`, `derivativesOptionsRegionalExpandedKeys`, `derivativesOptionsSelectedFocus`, `derivativesOptionsSelectedStrategy`, `derivativesOptionsSelectedStrike`, `derivativesOptionsSelectedUnderlying`, `getFuturesTechnicalSeriesCacheKey`, `getSelectedFuturesTechnicalContract`, `optionsAiExtrasLoading`, `usMarketSectorRankingState` |
| `js/page-home.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/page-home.js` | `js/charts.js` (`runtime/charts`) | `renderSectorLineChart` |
| `js/page-home.js` | `js/core.js` (`runtime/core`) | `clampScore`, `escapeHtml`, `parseMarketNumber`, `safeUrl`, `setText`, `toneClass` |
| `js/page-home.js` | `js/render-shared.js` (`runtime/render-shared`) | `getSectorPageGroups`, `isExcludedSector`, `renderScrollableClassTable`, `renderSectorSortControl`, `renderSectorStockName`, `sortSectorItemsByActiveMode` |
| `js/page-home.js` | `js/state.js` (`runtime/state`) | `data`, `homePennySectorMarket`, `homePennySectorPayload`, `homePennySectorPromise`, `localAllStocks`, `marketSectorRankingState`, `sectorFundFlowState`, `sectorSortState` |
| `js/page-tw.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/page-tw.js` | `js/charts.js` (`runtime/charts`) | `bindHorizontalChartPan`, `renderSectorLineChart` |
| `js/page-tw.js` | `js/core.js` (`runtime/core`) | `clampScore`, `escapeHtml`, `formatGlobalValue`, `formatSignedPercentValue`, `parseAnalysisNumber`, `parseMarketNumber`, `safeUrl`, `setText`, `toneClass` |
| `js/page-tw.js` | `js/main.js` (`runtime/bootstrap`) | `loadLiveData` |
| `js/page-tw.js` | `js/render-shared.js` (`runtime/render-shared`) | `buildPath`, `getSectorPageGroups`, `getVixSentimentBand`, `getWeekKey`, `isExcludedSector`, `renderScrollableClassTable`, `renderSectorSortControl`, `renderSectorStockName`, `sliceVisibleWindow`, `sortSectorItemsByActiveMode`, `twEtfWeightText` |
| `js/page-tw.js` | `js/shared-calc.js` (`runtime/shared-calc`) | `analyzeTechnicalTheories`, `buildPortfolioTheoryAssessment`, `getSimulationSignal`, `movingAverage` |
| `js/page-tw.js` | `js/state.js` (`runtime/state`) | `PORTFOLIO_COST_MODEL`, `PORTFOLIO_FACTOR_SOURCE`, `PORTFOLIO_SIM_STORAGE_KEY`, `SECTOR_SYNC_PICKER_LIMIT`, `TW_ETF_DEFAULT_PAGE_SIZE`, `TW_ETF_PAGE_SIZE_OPTIONS`, `WEIGHTED_SECTOR_THEME_RULES`, `activeRenderedStockDetail`, `activeStockCode`, `activeStockMarket`, `activeYahooSectorCategories`, `activeYahooSectorStocks`, `data`, `defaultYahooSectorCategoryAttempts`, `getWatchlist`, `internationalIndexesPromise`, `localAllStocks`, `saveWatchlist`, `sectorComparisonPanOffsets`, `sectorComparisonZoomCounts`, `sectorSortState`, `stockDetailRequestId`, `stockFullDetailCache`, `stockFullDetailPending`, `stockSearchRequestId`, `stockShareholderCache`, `stockShareholderPending`, `twEtfPayload`, `twEtfSelectedCode`, `twEtfState`, `watchlistAnalysisCache`, `watchlistDetailCache`, `watchlistKey`, `yahooSectorChartErrors`, `yahooSectorChartLoading`, `yahooSectorQuoteCache`, `yahooSectorRequestId` |
| `js/page-tw.js` | `js/stock-detail.js` (`route/stock-detail`) | `getStockDetailCacheKey`, `renderStockDetail` |
| `js/page-us.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/page-us.js` | `js/charts.js` (`runtime/charts`) | `bindChartHover`, `bindHorizontalChartPan`, `getChartHistory`, `renderTechnicalChart` |
| `js/page-us.js` | `js/core.js` (`runtime/core`) | `escapeHtml`, `formatGlobalValue`, `formatGlobalVolume`, `formatSignedPercentValue`, `parseAnalysisNumber`, `parseMarketNumber`, `safeUrl`, `setText`, `toneClass` |
| `js/page-us.js` | `js/render-shared.js` (`runtime/render-shared`) | `buildTechnicalTrendSummary`, `buildUsSearchDetail`, `buildUsStockSearchUrl`, `buildYahooFinanceUrl`, `getUsWatchlist`, `normalizeGlobalSeries`, `renderTechnicalTrendForecastSummary`, `renderUsBacktestLearningCard`, `renderUsPortfolioSimulator`, `renderUsWatchlist`, `saveUsWatchlist`, `twEtfWeightText`, `upsertUsWatchlistSymbol`, `usWatchlistKey` |
| `js/page-us.js` | `js/shared-calc.js` (`runtime/shared-calc`) | `analyzeTechnicalTheories` |
| `js/page-us.js` | `js/state.js` (`runtime/state`) | `TECHNICAL_PANEL_INDICATOR_OPTIONS`, `US_ETF_CATEGORY_DEFINITIONS`, `US_ETF_CATEGORY_LABELS`, `US_ETF_DEFAULT_PAGE_SIZE`, `US_ETF_DIRECTORY_SORT_OPTIONS`, `US_ETF_PAGE_SIZE_OPTIONS`, `US_NYSE_DIRECTORY_PAGE_SIZE`, `US_PORTFOLIO_SIM_STORAGE_KEY`, `stockChipTabState`, `usNyseDirectoryState`, `usStockSearchRequestId`, `usWatchlistAnalysisCache`, `usWatchlistDetailCache` |
| `js/page-us.js` | `js/stock-detail.js` (`route/stock-detail`) | `getStockDetailCacheKey` |
| `js/render-shared.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/render-shared.js` | `js/core.js` (`runtime/core`) | `escapeHtml`, `formatBacktestPercent`, `formatBacktestRatio`, `formatChartDate`, `formatGlobalValue`, `formatUsDetailMetric`, `formatUsSimulationMoney`, `parseAnalysisNumber`, `parseMarketNumber`, `safeUrl`, `setText`, `toneClass` |
| `js/render-shared.js` | `js/shared-calc.js` (`runtime/shared-calc`) | `buildGlobalMarketDetail`, `buildPortfolioTheoryAssessment`, `getSimulationSignal` |
| `js/render-shared.js` | `js/state.js` (`runtime/state`) | `EXCLUDED_SECTOR_SOURCE_NAMES`, `PORTFOLIO_FACTOR_SOURCE`, `US_PORTFOLIO_SIM_STORAGE_KEY`, `US_WATCHLIST_STORAGE_KEY`, `activeYahooSectorCategories`, `data`, `sectorSortState`, `usWatchlistAnalysisCache`, `usWatchlistDetailCache`, `yahooSectorQuoteCache` |
| `js/shared-calc.js` | `js/core.js` (`runtime/core`) | `formatGlobalVolume`, `parseAnalysisNumber`, `parseMarketNumber` |
| `js/shared-calc.js` | `js/state.js` (`runtime/state`) | `BACKTEST_BENCHMARK_SOURCE`, `BACKTEST_DRIFT_SOURCE`, `BACKTEST_FACTOR_BASELINE`, `MARKET_BREADTH_STORAGE_KEY`, `data`, `localAllStocks` |
| `js/stock-detail.js` | `js/api.js` (`runtime/api`) | `fetchWithTimeout` |
| `js/stock-detail.js` | `js/charts.js` (`runtime/charts`) | `bindChartHover`, `bindHorizontalChartPan`, `getChartHistory`, `renderTechnicalChart` |
| `js/stock-detail.js` | `js/core.js` (`runtime/core`) | `escapeHtml`, `formatChartDate`, `formatRocDateFromDate`, `parseAnalysisNumber`, `parseMarketNumber`, `safeUrl`, `toneClass` |
| `js/stock-detail.js` | `js/render-shared.js` (`runtime/render-shared`) | `buildTechnicalTrendSummary`, `renderTechnicalTrendForecastSummary` |
| `js/stock-detail.js` | `js/shared-calc.js` (`runtime/shared-calc`) | `analyzeTechnicalTheories`, `normalizePortfolioHistory` |
| `js/stock-detail.js` | `js/state.js` (`runtime/state`) | `TECHNICAL_PANEL_INDICATOR_OPTIONS`, `activeRenderedStockDetail`, `activeStockMarket`, `data`, `getWatchlist`, `saveWatchlist`, `stockChipTabState`, `stockInstitutionHistoryAttempted`, `stockInstitutionHistoryCache`, `stockInstitutionHistoryPending`, `stockInstitutionPeriodState`, `stockInstitutionRangeHistoryCache`, `stockInstitutionRangeState`, `stockInstitutionSeriesState`, `stockMarginPeriodState`, `stockMarginRangeState`, `stockMarginSummaryModeState`, `stockMarginTableTypeState`, `watchlistKey` |

## 5. 循環與頂層初始化

循環依賴不可在 TD02-01 直接消除：

- `js/main.js ↔ js/page-tw.js`：mutual cross-slice references; do not perform direct ESM cutover until TD02-02 defines a deferred entrypoint or temporary bridge
- `js/page-global-market-assethub.js ↔ js/page-global-market-futures.js ↔ js/page-global-market-options.js`：mutual cross-slice references; do not perform direct ESM cutover until TD02-02 defines a deferred entrypoint or temporary bridge

頂層立即執行引用：

| source | line | symbols | gate |
|---|---:|---|---|
| `js/core.js` | 63 | `nativeInnerHtmlDescriptor` | ESM execution must import or bridge before evaluation |
| `js/main.js` | 89 | `initSearchPage` | ESM execution must import or bridge before evaluation |
| `js/main.js` | 90 | `initWatchlistPage` | ESM execution must import or bridge before evaluation |
| `js/main.js` | 91 | `initGlobalMarketPage`, `loadYahooSectorCategory` | ESM execution must import or bridge before evaluation |
| `js/page-global-market-assethub.js` | 5470 | `fetchWithTimeout` | ESM execution must import or bridge before evaluation |

## 6. Dynamic window bridge

| property | owner | reads | writes | reason |
|---|---|---|---|---|
| `TWSE_ALL_STOCKS` | external/server-seeded window property | 2 | — | state.js reads an optional preloaded seed before live fetch; preserve as an explicit runtime input |
| `TWSE_DATA` | external/server-seeded window property | 1 | — | state.js reads an optional preloaded seed before live fetch; preserve as an explicit runtime input |
| `__MARKET_PULSE_SAFE_INNER_HTML__` | js/core.js | 64 | 68 | idempotence sentinel for the innerHTML safety guard; keep private to the safety adapter |
| `currentGlobalMarketPayload` | js/page-us.js + js/page-global-market-options.js | 1911, 2052, 2087, 2093, 2106 | 1287, 3850 | cross-route window payload handoff; replace with an explicit store/import before removing the bridge |

## 7. TD02-02 handoff rules

1. 以 JSON 的 symbol owner 作唯一 owner；不得複製 `escapeHtml` 或其他 global definition。
2. `required_global_bridge` 在 consumer 改成顯式 import、或由 deferred entrypoint 接手前必須保留；不得先刪 classic binding。
3. `top_level_initialization_gate` 的引用在 ESM 執行前必須可取得；函式本體內的晚載入引用可延後到呼叫時，但必須在 TD02-02 逐項確認。
4. 三個 global-market source 與 `main`／`page-tw` 的循環需採 deferred entrypoint 或暫時 bridge；不得以重排 HTML 掩蓋循環。
5. `currentGlobalMarketPayload`、server-seeded `TWSE_DATA`／`TWSE_ALL_STOCKS` 與 innerHTML safety sentinel 是動態 window 契約，不能只靠靜態 export/import 推測。

## 8. 回退與明確排除

回退方式：將 HTML script list 恢復為 lockfile 的 classic 順序：`pwa.js → js/state.js → js/core.js → js/api.js → js/shared-calc.js → js/render-shared.js → js/charts.js → js/stock-detail.js → js/page-home.js → js/page-us.js → js/page-global-market-futures.js → js/page-global-market-options.js → js/page-global-market-assethub.js → js/page-tw.js → js/legacy-unclassified.js → js/main.js → app.js`；`derivatives-status.html` 再接 `derivatives-ui.js`。本批沒有改動可回退的 production wiring。

本批明確不做：ESM 接線、移除 classic slices、改變頁面行為、更新 global-symbol baseline、CSP、Service Worker、cache、部署設定、SQLite 或 `twse-cache.json`。

## 9. 重現指令

權威 generator：`regression/td02_01_dependency_matrix.py`。權威輸入是 `regression/td18_shadow_build.lock.json`、`regression/baseline/frontend/global_symbols.json`、根目錄 21 個 HTML 與 lockfile 指定的 classic source slices；輸出是本文件與同名 JSON。

generator 先建立一份 normalized matrix，再由同一份 model 產生 JSON 與 Markdown；generation timestamp、absolute machine/temp paths 與其他環境 metadata 不進入 canonical evidence。generated files 不得手動編輯。

```text
python regression/td02_01_dependency_matrix.py --write
python regression/td02_01_dependency_matrix.py --check
python -m unittest regression.test_td02_01_dependency_matrix
sha256sum docs/TD02-01_dependency_matrix_2026-08-31.json docs/TD02-01_dependency_matrix_2026-08-31.md
```
