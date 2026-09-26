# P2-00～P2-08 backend / app-factory evidence

Snapshot: 2026-09-25. Scope is limited to the owner-authorized P2-00～P2-08
backend consolidation slice. Existing unrelated worktree changes were left
untouched; no frontend file was changed by this slice.

## P2-00 — dependency map

### Module graph

```text
market_config ───────────────┐
shared_state → cache ────────┼→ app → routes_*
security → fetchers ─────────┤    ├→ builders → fetchers / parsers / derivatives/*
fetch_registry → fetchers ───┤    └→ cache / market_config
fetchers → parsers (module-level parsers → fetchers edge is existing)
parsers → fetchers / cache / market_config
derivatives/* → pure domain helpers; no route or network edge
```

The effective import-time path is intentionally one-way for application
assembly:

```text
app → builders → parsers → fetchers → cache
app → routes_* → builders/fetchers/parsers/cache
```

Runtime-only back-edges are deferred imports and are catalogued in P2-05.
The main circular-risk edges are `cache → app` for refresh orchestration,
`builders → app` for legacy shared utilities/store access, `parsers → app`
for app-local builders/config, and route handlers → `app` for the common API
error/runtime helpers. None of these are module-load-time back-edges.

### Responsibility inventory

| Area | Current owner | Evidence / risk |
|---|---|---|
| HTTP boundary | `routes_system.py`, `routes_global_market.py`, `routes_twse.py`, `routes_derivatives.py` | Flask blueprints; selected `/api/us-market/search` route delegates directly to `us_market_search.build_us_market_search_payload`. |
| Business composition | `builders.py`, `us_market_search.py` | `build_global_market_payload` and the US-market search service compose normalized results and fallback semantics. |
| External transport | `fetchers.py` | `fetch_json`, `post_json`, `fetch_text`, registry adapters, and source-specific fetchers route through the SSL fallback boundary. |
| Parsing / normalization | `parsers.py` plus source-normalization helpers | CBOE contract parsing moved into this layer in this slice; no network call is used by that selected parser path. |
| Cache / shared mutable state | `cache.py` | `cache_data`, locks, single-flight registries, provider status, and background-updater state have one process-local owner. |
| Runtime configuration | `market_config.py`, app factory config, `app.extensions` | Derivatives store is now accessed through `app.get_derivatives_store()` at builder call sites. |
| Persistence | `derivatives_store.py` | Factory-created apps bind exactly one store instance at `app.extensions["derivatives_store"]`; the module-level store remains only as legacy WSGI/test fallback. |

### Shared globals and state access

- `cache.cache_data["provider_status"]` is the provider-status owner.
- `cache.cache_data` plus `cache_lock` owns site data, stock data, cache
  buckets, and cache single-flight coordination.
- `cache.background_updater_started` owns the process-local startup guard;
  factory construction does not start a worker.
- `cache.penny_sector_recommendation_cache` and
  `cache.taifex_options_chain_inflight` remain the existing cache owners.
- `app.DERIVATIVES_STORE` remains a compatibility fallback only. New builder
  persistence access uses `app.get_derivatives_store()`, which resolves the
  active factory-bound store first and avoids a shadow store inside builders.
- `market_config.GLOBAL_MARKET_CATEGORIES` is existing import-time catalog
  configuration; this slice does not duplicate or relocate it.

## P2-01 — builders vertical slice

Selected slice:

```text
/api/global-market/options
  → routes_global_market.api_global_market
  → builders.build_global_market_payload
  → builders.build_cboe_options_chain
  → fetchers.fetch_cboe_options_payload
  → parsers.normalize_cboe_option_contract
  → normalized calls / puts payload
```

The builder keeps selection, expiration choice, aggregation, cache behavior,
fallback/error messages, and output assembly. The route contract is unchanged.
Deterministic regression evidence is in
`regression/test_p2_backend_boundaries.py`:

- route delegates to the builder and preserves the response shape;
- a fixture CBOE payload produces the same normalized call/put shape;
- source URL, expiration, strike, type, and summary counts are asserted.

## P2-02 — fetchers dependency map

`fetchers.py` currently has 189 top-level functions and owns the outbound
transport families below.

| Provider / source family | Transport responsibility | Normalization / orchestration boundary |
|---|---|---|
| TWSE / TPEX | `fetch_json`, `fetch_text`, OpenAPI and CSV helpers | TWSE/TPEX parser and builder callers |
| TAIFEX | daily reports, form queries, open interest, futures/options endpoints | TAIFEX parser helpers plus builders |
| Yahoo Finance | chart, quote summary, news, margin, holder, option and Taiwan-market requests | source-specific fetch normalization plus builder composition |
| Nasdaq Trader / Nasdaq API | symbol directory and financial supplement requests | listed-universe normalization and US builders |
| NYSE | directory POST requests | listed-universe normalization and search service |
| Cboe | `fetch_cboe_options_payload` added in this slice | `parsers.normalize_cboe_option_contract` + builder aggregation |
| Barchart | cookie/context and quote requests | builder-level contract aggregation remains a later migration target |
| Deribit / Bybit | public options JSON requests | builder-level contract aggregation remains a later migration target |
| FRED / U.S. Treasury / Trading Economics / Google News | text/CSV/JSON transport | builders assemble market-specific response items |

Before this slice, the CBOE builder constructed the provider URL and called
`fetch_json` itself. After this slice, the provider boundary owns URL
construction and transport, while parser and builder responsibilities remain
separate. No route calls `fetch_cboe_options_payload` directly.

## P2-03 — provider extraction

Implemented for the selected CBOE provider slice:

- provider URL and request are in `fetchers.fetch_cboe_options_payload`;
- contract-symbol parsing and normalization are in `parsers.py`;
- expiration selection, cache lookup/write, aggregation, and public payload
  assembly remain in `builders.py`;
- no route or parser network call was added;
- the existing CBOE error/source URL behavior is retained.

The regression test patches the provider boundary, not the HTTP primitive, and
asserts that the builder consumes the provider result exactly once.

## P2-04 — service boundary

The existing US-market search vertical slice is the service-boundary
reference:

```text
/api/us-market/search
  → us_market_search.build_us_market_search_payload
  → fetchers provider functions
  → normalized search result
```

The route only reads the query and serializes the returned payload. Provider
fan-in, fallback handling, deduplication, and result assembly stay in
`us_market_search.py`. The CBOE slice applies the same separation at the
builder boundary. Other legacy routes that still call fetchers directly are
listed as migration targets in Known limitations and were not opportunistically
rewritten.

## P2-05 — deferred `app` import inventory

All runtime imports were inventoried with an AST scan after this slice. The
classification below is by call-site family; no deferred import was removed
blindly.

| Module | Call-site families | Classification |
|---|---|---|
| `cache.py` | `refresh_cache`, `_run_background_refresh_tasks` | `SHARED-STATE ACCESS` + `CIRCULAR-IMPORT WORKAROUND`; cache invokes app-owned composition only at refresh time. |
| `builders.py` | TAIFEX builders, option builders, global-market builders, site-data builders, and logger/TZ helpers | `CIRCULAR-IMPORT WORKAROUND`; `SHARED-STATE ACCESS` for the store path; migration targets where app-local helpers can acquire an explicit boundary. |
| `fetchers.py` | derivative candle builder, institutional builders, live-stock parsers, Taiwan option config, Taiwan technical helpers, option-chain builders, class-quote parser | `CIRCULAR-IMPORT WORKAROUND`; provider/config callbacks remain deferred until their call-time dependency is available. CBOE expiration parsing now defers to `parsers`, removing the former fetchers→builders edge for that parser. |
| `parsers.py` | option config, Taiwan quote parsers, stock/sector enrichment, cache refresh, derivative lookup | `CIRCULAR-IMPORT WORKAROUND` and `SHARED-STATE ACCESS`; network-bearing legacy helpers are explicit migration targets, not silently removed in this slice. |
| `routes_global_market.py` | global market, ETF center, NYSE listed, public options chain handlers | `CIRCULAR-IMPORT WORKAROUND` for common API/runtime helpers. |
| `routes_twse.py` | source/error helpers, cache warming, live/stock/institution routes | `CIRCULAR-IMPORT WORKAROUND` + `SHARED-STATE ACCESS`. |
| `routes_derivatives.py` | all derivatives handlers | `CIRCULAR-IMPORT WORKAROUND` + `SHARED-STATE ACCESS` for persistence/error helpers. |

There are no `from app import ...` statements in the production modules listed
above. Deferred imports are `import app`, `import builders`, or the one
call-time `from parsers import parse_cboe_expiration_request`; test-only
imports are outside the production inventory.

## P2-06 — shared-state migration

The minimal ownership migration is complete for the selected persistence path:

```text
route/builder call
  → app.get_derivatives_store()
  → current_app.extensions["derivatives_store"]
  → one DerivativesStore instance
```

`builders.build_global_market_payload` no longer reaches the module-level
`app.DERIVATIVES_STORE` directly. The legacy fallback remains intentionally for
`app:app` compatibility and old tests; no duplicate builder-local store or
shadow cache was introduced.

## P2-07 — App Factory boundary

`create_app(config=None, derivatives_store=None)` remains the application
assembly boundary and now registers the existing 404/500 handlers on every
factory-created app. It is responsible for Flask creation, config, store
binding, proxy middleware, request hooks, error handlers, and blueprint
registration. The compatibility `app = create_app(...)` WSGI entrypoint and
`python app.py` startup path remain intact.

The factory path performs no provider/network request and does not start the
background updater during construction. Repeated construction produces the
same route set without duplicate blueprint registration or worker startup.

## P2-08 — circular-import regression

`regression/test_p2_backend_boundaries.py` runs isolated subprocess checks for:

- `app → builders`;
- `builders → fetchers`;
- `fetchers → parsers`;
- `routes_twse → builders`;
- `routes_derivatives → builders`;
- repeated `create_app()` construction.

The same test module also asserts factory error handling, stable route counts,
the selected route→builder boundary, and the builder→provider→parser slice.

## Known limitations

- This batch does not migrate every legacy route that still calls a fetcher
  directly, nor every parser helper that predates the current layer split.
  Those are explicitly inventoried migration targets and were not broadened
  into an unrelated rewrite.
- Barchart, Deribit, and Bybit provider transport remains in the existing
  options-builder cluster; CBOE is the authorized representative extraction
  slice for this batch.
- No frontend, deployment, release-manifest, packaging, commit, push, PR,
  merge, or deploy action is part of this evidence.

## Verification record

| Command | Result |
|---|---|
| `python -m py_compile app.py builders.py fetchers.py parsers.py regression/test_p2_backend_boundaries.py` | PASS |
| `python -m unittest test_derivatives_platform.py` | PASS — 206 tests |
| `python -m unittest regression.test_p2_backend_boundaries` | PASS — 4 tests |
| `python -m unittest regression.test_data_source_contracts` | PASS — 9 tests |
| `python -m unittest regression.test_runtime_persistence_idempotency` | PASS — 5 tests |
| `python regression/test_derivatives_api_transport.py` | PASS — 2 tests |
| `python security_guardrail_check.py` | PASS — 16 checks |
| `python e2e_smoke.py` | PASS — `E2E_SMOKE_OK`; external market sources were unavailable and were handled by existing fallback paths |
| `node --version` | PASS — `v24.18.0` |
| `node regression/test_p0_asset_cost_models.js` | PASS |
| `node regression/test_p1_options_execution.js` | PASS |
| `node regression/test_p1_options_liquidity.js` | PASS |
| `node regression/test_p1_point_in_time.js` | PASS |
| `git diff --check` | PASS |
| `python regression/verify_against_baseline.py --full` | NOT COMPLETED — the full harness produced no output for more than two minutes under the local external-source restriction and was stopped with Ctrl+C; no baseline result is claimed |
