# P2-09～P2-12 frontend consolidation evidence

Snapshot: 2026-09-25. Scope is limited to the owner-authorized frontend slice.
Pre-existing worktree changes were preserved. No commit, push, PR, merge, deploy,
release-manifest, packaging, or P2-13+ work was performed.

## P2-09 — shared-calc responsibility map

### Boundary result

`js/shared-calc.js` remains the owner of deterministic technical, portfolio,
market-normalization, and backtest calculations. It has no API request, DOM
operation, event handler, or browser-storage operation after this slice.

The only mixed responsibility found in the selected boundary was market breadth:
the calculation read `localAllStocks` and directly read/wrote `localStorage`.
The minimal extraction is:

```text
state.js
  twEtfState.getMarketBreadthContext(detail)
    ├─ owns localStorage read and localAllStocks access
    └─ passes explicit stocks/history/date; save method owns persistence
         ↓
shared-calc.js
  buildMarketBreadthIndicators(detail, allStocks, history)
    └─ deterministic calculation; returns nextHistory as data
```

The six existing technical-theory call sites now pass the explicit breadth
context. The rendered labels, market breadth semantics, API contracts, and
fallback behavior are unchanged.

| Responsibility | Owner | Classification | Evidence / decision |
|---|---|---|---|
| Pure calculation | `js/shared-calc.js` | KEEP | Technical indicators, portfolio math, deterministic breadth, backtest statistics, risk and execution math. |
| Formatting / calculation-facing labels | `js/shared-calc.js`, `js/core.js` | KEEP / HIGH-RISK-DEFER | Existing deterministic display strings are interleaved with legacy analysis; no broad rewrite was authorized. Canonical HTML escaping remains in `js/core.js`. |
| Market semantics | `js/shared-calc.js` | KEEP | Technical theory, breadth, futures proxies, and normalized market detail remain shared semantic calculations. |
| Execution semantics | `js/shared-calc.js` | KEEP | Backtest T+1 entry, stop/target simulation, costs, and split metadata are deterministic domain logic. |
| Options strategy math | `js/page-global-market-assethub.js` | PAGE-SPECIFIC / HIGH-RISK-DEFER | Strategy engine owns options legs, payoff, execution/liquidity gates, and point-in-time trust. No migration into shared-calc. |
| DOM / UI responsibility | `js/render-shared.js` and page modules | KEEP | Render functions, selectors, event handlers, and page initialization stay outside shared-calc. |
| Shared mutable state | `js/state.js` | KEEP | Storage adapters and page/session state are state-owned; shared-calc receives explicit inputs. |
| Provider / API responsibility | `js/api.js` and page modules | KEEP | Fetch calls remain in API/page orchestration; shared-calc has zero fetch transport calls. |

Static boundary evidence:

- `shared-calc.js`: 3,973 lines, 72 named functions, 0 fetch calls, 0 DOM
  operations, 0 browser-storage references.
- `twEtfState.getMarketBreadthContext` and
  `twEtfState.saveMarketBreadthHistory` are the selected state adapters; they
  are attached to an existing state owner
  so the frozen frontend global-symbol baseline is unchanged.
- `buildBacktestLearningModel.calculateAssetTransactionCost` is a deterministic
  shared calculation consumed by `page-tw.js` and `render-shared.js`; it does
  not own transport or UI.

## P2-10 — large-page audit

Counts below are static evidence from the current source files. `calc` is a
high-recall audit count of calculation/math/metric patterns, not a claim that
every match is an independent responsibility.

| Module | Bytes | Lines | Named funcs | API calls | Calc signals | DOM signals | Events | State signals | Format signals | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `js/page-global-market-assethub.js` | 414,577 | 6,698 | 145 | 9 | 200 | 78 | 18 | 63 | 468 | KEEP; HIGH-RISK / DEFER |
| `js/page-global-market-options.js` | 211,706 | 4,030 | 131 | 10 | 161 | 88 | 33 | 9 | 131 | KEEP; HIGH-RISK / DEFER |
| `js/page-global-market-futures.js` | 231,873 | 4,230 | 92 | 3 | 200 | 67 | 21 | 36 | 248 | KEEP; HIGH-RISK / DEFER |
| `js/page-tw.js` | 216,540 | 4,190 | 112 | 10 | 213 | 192 | 41 | 17 | 180 | KEEP; HIGH-RISK / DEFER |
| `js/page-us.js` | 159,816 | 2,951 | 66 | 8 | 167 | 120 | 22 | 82 | 93 | KEEP; selective shared-calc consumer |
| `js/page-home.js` | 63,268 | 1,208 | 33 | 1 | 44 | 48 | 5 | 3 | 61 | KEEP; no proven extraction target |

### Responsibility and risk classification

| Module | API orchestration | Calculation | Render | Events | State | Duplicate / cross-page finding | Classification |
|---|---|---|---|---|---|---|---|
| `page-global-market-assethub.js` | Futures, options, metals, bonds, news, institutional requests | Options strategy math, cost model, liquidity and trust | Asset hub and derivatives cards/tables | Strategy controls, tabs, filters | Options/derivatives page state | Cross-calls global-market cluster; options execution semantics are page-specific | KEEP; EXTRACT TARGET only after separate low-risk proof; HIGH-RISK / DEFER |
| `page-global-market-options.js` | Taiwan/US option chain and global-market requests | Options analysis and derived metrics | Options workbench, chain, risk panels | Chain/source/expiry controls | Local options UI state | Shares the global-market island with futures and asset hub | KEEP; HIGH-RISK / DEFER |
| `page-global-market-futures.js` | Futures and US-market fallback requests | Futures indicators, OHLC technical calculations | K-line, volume, outlook, scope panels | Interval, zoom, pan, selector controls | Futures chart state | Calls shared technical theory and global-market render helpers | KEEP; HIGH-RISK / DEFER |
| `page-tw.js` | TWSE/TPEX/Yahoo requests | Sector/ETF/portfolio calculations | Stock, sector, ETF, portfolio views | Search, tabs, watchlist, portfolio controls | Watchlist and portfolio state | Uses shared backtest cost calculation; page behavior is selector-heavy | KEEP; no broad extraction |
| `page-us.js` | US search, ETF, watchlist, NYSE/Nasdaq requests | US ETF/risk/volume calculations | Search, ETF, watchlist views | Search, filters, chart controls | US watchlist/analysis state | Uses shared technical theory and explicit breadth context | KEEP; no broad extraction |
| `page-home.js` | Home recommendation request | Small summary calculations | Home dashboard | Five event bindings | Minimal page state | No duplicated high-value calculation proven | KEEP |

P2-10 is an audit node. No large page was wholesale split, no new giant shared
module was created, and no page-specific options/execution logic was moved into
shared-calc.

## P2-11 — selected extraction evidence

Selected target: market breadth state boundary, because it was the only direct
storage side effect inside the shared calculation module and had a bounded,
low-risk seam.

- Moved browser storage access to `js/state.js:twEtfState.getMarketBreadthContext`
  and `js/state.js:twEtfState.saveMarketBreadthHistory`.
- Existing page consumers now call the pure shared calculation directly with
  explicit state inputs, then return the computed history to state for saving.
- Made `js/shared-calc.js:buildMarketBreadthIndicators` accept explicit stocks
  and history and return deterministic calculation data.
- Updated the six existing consumers of `analyzeTechnicalTheories` to pass the
  context explicitly.
- Preserved `market-pulse-market-breadth-v1`, ADL history, snapshot date
  fallback, and existing breadth output fields.
- No API path, schema, selector, event behavior, or rendered label was changed.
- Existing cost calculation extraction is covered as a shared-calc consumer
  contract; it was not duplicated or expanded into a new module.

## P2-12 — frontend contract evidence

`regression/test_p2_frontend_contract.js` covers:

- shared-calc boundary: no API/DOM/storage transport responsibility;
- state adapter → shared pure calculation load order;
- deterministic breadth calculation and persistence adapter;
- selected shared-calc cost calculation consumers;
- syntax checks for affected frontend modules;
- page initialization symbols and HTML `data-page` / root selectors;
- representative API path contracts;
- schema/error/fallback presence;
- P1 execution, liquidity, point-in-time, and P/L trust labels/fields;
- event wiring in the affected page modules;
- all six extracted breadth-context consumers and no naked call remaining.

## Known limitations

- Large page modules intentionally remain page-specific; P2-10 did not authorize
  wholesale decomposition.
- Existing global-market island cross-dependencies remain documented and are
  HIGH-RISK / DEFER, not silently rearranged.
- The full baseline harness remains NOT VERIFIED under the external-source
  restriction. No full-baseline PASS is claimed.
- P2-13～P2-20 were not executed.
