# P4-03 Giant Page Modules Decomposition Contract

**Contract ID:** `P4_03_GIANT_PAGE_MODULES_DECOMPOSITION_V1`

**Status:** FROZEN BEFORE IMPLEMENTATION

**Scope:** P4-03 only

**Frozen against:** working-tree source at HEAD `1211e880fbcdd0bbf8d438555773d060f92f647c`; P4-03 pre-change `js/page-global-market-assethub.js` SHA-256 `ac326185a3455a18256597c91c0b9f8bc877f817459638b8d3e762b786684a62` (423,499 bytes, 6,767 lines).

## 1. Purpose and boundaries

Decompose the existing giant global-market asset hub page module along its existing shared-helper, asset-finance, derivatives, and page-composition responsibilities. Preserve function bodies and observable behavior. This is a structural refactor only.

P4-01 and P4-02 remain closed and unchanged. P4-04 remains not authorized / not started. This contract does not authorize Phase 4 closure, Git promotion, or deployment.

The following semantics are frozen: API and DOM behavior, market calculations, decision and probability behavior, score values, provider selection, transaction costs, P4-02 explicit-input semantics, page routing, and classic-script compatibility. No HTML script-order or markup changes are in scope; existing pages load the generated runtime loader/bundles. The existing ESM build may update only loader cache-busting query values as generated runtime wiring.

## 2. Pre-change structural inventory

AST inventory of the current page JavaScript modules:

| Module | Lines | Function declarations | Existing responsibility |
|---|---:|---:|---|
| `js/page-global-market-assethub.js` | 6,767 | 145 | Asset-hub page, shared asset quote/options widgets, asset-finance, derivatives overview/analytics/AI |
| `js/page-global-market-futures.js` | 4,252 | 92 | Futures/global-market and US-market views |
| `js/page-global-market-options.js` | 4,046 | 131 | Options and global-market views |
| `js/page-tw.js` | 4,202 | 111 | Taiwan market views |
| `js/page-us.js` | 2,965 | 65 | US market views |
| `js/stock-detail.js` | 2,887 | 10 | Stock detail; one large renderer |
| `js/page-home.js` | 1,209 | 33 | Home page |

The target module contains one additional top-level expression: `initDerivativesAnalyticsPage.strategyEngine = (() => { ... })()`. It is derivatives analytics state and must move intact with the derivatives module. Its exact source span is 45,580 bytes; SHA-256 `bac278622b4808e084928eecb67dcd64be17a12b368a2d3646c3bfb3a28f5bc0`.

## 3. Frozen module ownership and load contract

The 145 existing function declarations are assigned exactly once as follows. Preserve original function source text byte-for-byte; keep functions in their original relative order within each owner module.

### `js/page-global-market-shared.js` — 36 functions

Shared data access, quote/region rendering, and Taiwan options-chain helpers consumed by multiple page modules:

```text
renderFuturesBacktestLearningCard, getAssetHubItems, getAssetHubUsableItems, findAssetHubItem, filterAssetHubItems, assetHubDirection, getAssetHubRegion, getAssetHubItemUrl, getAssetHubMetric, groupAssetHubItemsByRegion, renderAssetHubRegionChips, renderAssetHubSchemaPanel, renderAssetHubRegionalGroups, renderAssetHubQuoteGrid, renderAssetHubSummary, renderAssetHubOnlineRows, renderAssetHubOnlineTable, renderAssetHubTaiwanFuturesCard, renderAssetHubOptionContracts, renderAssetHubPublicOptionChainCard, pickTaiwanOptionRows, getTaiwanOptionExpiryPrefix, formatTaiwanOptionExpiryCode, formatTaiwanOptionExpiryLabel, renderTaiwanOptionExpiryTabs, renderTaiwanOptionChainTable, renderTaiwanOptionDistribution, renderTaiwanOptionAnalysis, renderTaiwanOptionChainCard, findAssetHubItemAny, findAssetHubUsableItemAny, getAssetHubItemsBySymbols, getAssetHubUsableBySymbols, uniqueAssetHubItemsBySymbol, clampAssetHubScore, createAssetHubPlaceholder
```

Frozen function-body fingerprint: `1a8760a313a4c72408efae769e43689da75bf776ea8cb270e5efafc4d201cc09`.

### `js/page-global-market-asset-finance.js` — 79 functions

```text
normalizeTreasuryYieldValue, getAssetHubTreasuryYieldPoint, formatAssetHubYield, formatAssetHubRatio, buildAssetHubFinanceModel, buildAssetHubFinanceScenarios, buildAssetHubAllocationAdvice, renderAssetFinanceSignal, renderAssetFinanceSignalPanel, renderAssetFinanceCoreDashboard, renderAssetFinanceMetalsPanel, getAssetFinanceTrendRange, buildAssetFinanceTrendDataset, buildAssetFinanceTrendPoints, buildAssetFinanceTrendSeriesList, renderAssetFinanceTrendBody, getAssetFinanceTrendStatus, bindAssetFinanceTrendCursor, initAssetFinanceTrendSwitchers, renderAssetFinanceTrendPanelContent, renderAssetFinanceMetalProfilesPanel, buildAssetFinanceGlobalVenueInsight, renderAssetFinanceDriverFactorCard, formatAssetFinanceMetricPct, averageAssetFinanceValues, standardDeviationAssetFinanceValues, buildAssetFinanceForecastItem, buildAssetFinancePriceForecastItems, renderAssetFinancePriceForecastBody, renderAssetFinancePriceForecastContent, renderAssetFinanceMetalDriversPanel, renderAssetFinanceDecisionCenterPanel, renderAssetFinanceSelectableMetalOnlineRows, renderAssetFinanceSelectableBondOnlineRows, buildAssetFinanceMetalsEtfConclusion, renderAssetFinanceVolumeTrendChart, getAssetFinanceVolumePayloadItem, renderAssetFinanceSingleTrendRiskAnalysis, getAssetFinanceBondProfile, getAssetFinanceBondEtfLens, renderAssetFinanceBondSingleAnalysis, initAssetFinanceVolumeSelectors, bindAssetFinanceVolumeCursor, renderAssetFinanceMetalEtfSyncPanel, buildAssetFinanceBondResearchImport, renderAssetFinanceBondResearchHero, renderAssetFinanceBondResearchMarketAnalysis, renderAssetFinanceBondResearchPanel, renderAssetFinanceScenarioPanel, averageAssetFinancePct, strongestAssetFinanceItem, formatAssetFinancePct, assetFinancePctTone, renderAssetFinanceSyncStat, renderAssetFinanceMetalsResearchSection, getAssetFinanceBondRows, isAssetFinanceTaiwanBond, filterAssetFinanceBondRows, getAssetFinanceBondFocusKey, getAssetFinanceRateMoveTone, getAssetFinanceBondFocusKind, buildAssetFinanceBondFocusEtfPulse, buildAssetFinanceBondFocusMetricSet, buildAssetFinanceBondYieldFocusInsight, buildAssetFinanceBondDashboardCommentary, getAssetFinanceBondCommentaryPoints, renderAssetFinanceBondCommentarySection, renderAssetFinanceBondDashboardCommentary, buildAssetFinanceBondMacroContext, renderAssetFinanceBondDecisionOverview, renderAssetFinanceBondCenterDashboard, renderAssetFinanceBondRegionalMarketPanel, renderAssetFinanceBondEtfCenterPanel, renderAssetFinanceBondsResearchSection, renderAssetFinanceCrossReferenceSection, renderAssetHubFinanceDashboard, renderAssetHubCompactQuotePanel, renderAssetHubMetals, renderAssetHubBonds
```

Frozen function-body fingerprint: `22866255eaba81cbe25fe4b60714fc8ac6cbbdbf415d661ac0177a3e476df35b`.

### `js/page-global-market-derivatives.js` — 23 functions plus the strategyEngine assignment

```text
getDerivativeOverviewItems, renderDerivativeOverviewQuote, renderDerivativeOverviewMetric, getDerivativeOverviewTechnicalModel, renderDerivativeOverviewInstitutionSummary, buildDerivativeFuturesPositionAnalysis, renderDerivativeFuturesPositionCard, renderDerivativeOverviewInstitution, getDerivativeOverviewNewsImpact, buildDerivativeOverviewImpactModel, renderDerivativeOverviewNews, renderDerivativesMarketOverview, renderDerivativePcrHistory, renderDerivativeNewsItems, renderDerivativeBasisCard, renderInstitutionPositionCard, loadDerivativesAssetHubPayloads, renderDerivativePayloadSnapshot, renderDerivativesAssetSnapshotGrid, initDerivativesAnalyticsPage, renderDerivativeAiReport, renderDerivativeAiArchitectureCard, initDerivativesAiPage
```

Frozen function-body fingerprint: `70dea97cbc0cc017ad98ffa35957beb31e70af4ef537f79a26a910bdefb294a4`. Preserve the strategyEngine expression fingerprint recorded in §2.

### `js/page-global-market-assethub.js` — 7 functions

Retain page-level composition and initialization only:

```text
renderAssetHubFallbackPage, renderAssetHubFutures, renderAssetHubOptionsLegacy, renderAssetHubOptions, initAssetFinanceBondFocusControls, renderAssetHubPage, initAssetHubPage
```

Frozen function-body fingerprint: `37f1a34a4609d4c920ab9f4f49cd66543b74863171bde145831101a6aa29c51b`.

### Fingerprint algorithm

Parse each function declaration from the frozen source using Acorn with source ranges. For each group, retain original source order and hash UTF-8 bytes of the concatenation `name + NUL + exact function source`, joined by `LF + NUL`. The regression must recompute the same digest from the post-decomposition files. This pins all 145 bodies while allowing only their ownership/file placement to change.

## 4. Cross-module dependency and runtime order

The proposed route-bundle order is:

```text
page-home
page-us
page-global-market-shared
page-global-market-futures
page-global-market-options
page-global-market-asset-finance
page-global-market-derivatives
page-global-market-assethub (composition/entry)
page-tw
legacy-unclassified
main
app
```

This places the shared helpers before their consumers and keeps the derivatives and page-entry code after its existing futures/options dependencies. `renderTaiwanOptionChainCard` and its expiry helpers move with the shared chain-rendering family, removing the existing `options -> asset-hub entry` dependency. Existing `futures <-> options` cross-page calls are pre-existing and remain outside this contract; do not refactor them.

The generated Classic fallback and ESM source list must be derived from the same frozen source order. Add each new JS file to `market_config.JS_MODULE_STATIC_FILES`, `regression/td18_minify_build.lock.json`, and `regression/td18_shadow_build.lock.json`. Do not add direct per-page script tags or change loader/runtime mode behavior. The ESM build may regenerate existing loader version query strings and linked runtime manifest/cache versions; it must preserve HTML markup and script order. No backend route behavior, API, database, or schema edits are expected.

**Generated-wiring clarification (2026-10-03):** the Project Owner's §14 and §42 explicitly authorize loader-reference, manifest, source-map, and cache-version updates required by the existing ESM/Classic build. This clarification limits HTML updates to the builder-generated cache-busting query value and does not authorize authored markup or script-order changes.

## 5. Required regression and acceptance

Add `regression/test_p403_giant_page_modules_decomposition.js`. It must fail closed if:

- any frozen function is missing, duplicated, newly added to these modules, or owned by a different module;
- any group body fingerprint or the strategyEngine expression fingerprint changes;
- a new module is missing from the static allowlist or either runtime lock, or the frozen source order drifts;
- a non-pre-existing cross-module dependency violates the frozen runtime order;
- the asset-hub entry grows beyond its frozen 7-function responsibility.

Run the focused P4-03 test, P4-02 regression, affected frontend contract/regression tests, syntax checks, TD-18 minify and shadow verification, TD-02 full ESM canary (21 pages / 42 runtime runs), and `git diff --check`. Structural parity is required: existing page/API behavior, P4-02 explicit-input behavior, values, and runtime mode are unchanged. No baseline update is in scope.

Engineering completion may be reported only if all required checks pass. Record implementation as execution complete / engineering pass / formal acceptance pending Project Owner. Do not mark P4-03 formally closed.

## 6. Explicit exclusions

Do not change any function body or business behavior, resize/reroute other modules, modify HTML or visual/API baselines, alter P4-01/P4-02 records, create P4-04 work, change dependencies, access/mutate databases, or perform Git promotion or deployment. Preserve all pre-existing working-tree changes. Stop after reporting the P4-03 evidence.
