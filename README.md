# Market Pulse / Derivatives Platform V1.0 R6

Date: 2026-06-22

This package contains the Taiwan market dashboard and V1.0 futures/options platform.
The R6 revision applies the Final Candidate R5 review fixes: cloud database persistence,
broader tests, cold-cache refresh locking, SQLite WAL mode, tighter CSP, production-safe
SSL behavior, and schema-only clean delivery packaging.

## Run

```bash
python app.py
```

Default local URL:

```text
http://127.0.0.1:5000/
```

## Test

```bash
python -m py_compile app.py market_config.py derivatives_store.py clean_derivatives_db.py e2e_smoke.py verify_release_integrity.py live_source_validation.py build_portable_package.py test_derivatives_platform.py
python -m unittest test_derivatives_platform.py
python e2e_smoke.py
python verify_release_integrity.py
```

## Regression Baseline System (TD refactor gate)

Before any TD-01~TD-13 refactor ticket, `regression/` captures a full behavior
snapshot of the current app so later changes can be checked for parity.
Details: `docs/工單00_行為基準驗證系統.md`.

```bash
# One-time, only on the pre-refactor original code:
pip install -r regression/requirements-regression.txt
playwright install chromium
python regression/capture_baseline.py     # -> regression/baseline/api/*.json, manifest.json
python regression/frontend_check.py --capture   # -> regression/baseline/screenshots/*.png
python regression/interaction_check.py --capture   # -> regression/baseline/interactions/{manifest,results}.json

# Repeated during refactor work, to check for behavior drift:
python regression/verify_against_baseline.py --quick         # cache-backed API endpoints + security checks (~1-2 min, no live external fetch — see TD-17)
python regression/verify_against_baseline.py --quick --api-live  # + the 4 always-live endpoints (live-sectors/live-overview/live-stocks/live-search)
python regression/verify_against_baseline.py --quick --interactions  # + interaction checks (P0+P1, ~2 min)
python regression/verify_against_baseline.py --full           # quick + --api-live + Playwright frontend compare + interaction checks
```

Each TD ticket's definition of done requires both `python -m unittest
test_derivatives_platform.py` and `python regression/verify_against_baseline.py --full`
to pass. A `Stop` hook in `.claude/settings.json` also runs `--quick`
automatically after each turn and reports PASS/FAIL without blocking.

Notes:
- `regression/baseline/` is frozen once captured — do not regenerate it during
  a refactor. If a compare fails, fix the code, not the baseline (the one
  exception is a genuine baseline-capture defect, e.g. a missed dynamic-field
  mask, which should be explained in the commit message).
- Most API endpoints serve live TWSE/TAIFEX/Yahoo data that keeps changing
  independently of any code change, so `capture_baseline.py` marks nearly all
  of them `structure_only` (JSON shape/schema comparison only). Only a couple
  of static endpoints (`/api/health`, `/api/derivatives/v1-status`) get full
  value comparison with masked timestamps.
- `verify_against_baseline.py` retries a failing endpoint once after a short
  delay before treating it as a real failure, to absorb transient external
  data source outages.
- TD-17: `--quick` warms the cache once (generous timeout) before comparing
  the 40 cache-backed endpoints; a warm-up failure aborts immediately and is
  labeled `[外部問題,非程式碼]` instead of surfacing as 44 unlabeled
  per-endpoint timeouts. The 4 endpoints that always fetch live with no
  caching layer by design (`live-sectors`/`live-overview`/`live-stocks`/
  `live-search`) live under a separate `--api-live` flag — `--full` includes
  it automatically, `--quick` does not. Every failure message is tagged
  `[外部問題,非程式碼]` or `[程式碼可能改動回應格式]` so a red light is
  legible at a glance.
- `interaction_check.py` (工單 00-B) covers 21 pages / 94 real click/select/
  submit interaction steps (P0+P1 tier; P2 — zoom/pan/hover — not yet
  implemented, see `regression/interaction_inventory.md`). It replays a
  frozen HAR per page so the underlying data never varies between runs;
  full suite runtime is ~1m50s, well under the 5-minute budget, so P0+P1
  stays the default and there is no separate opt-in flag needed today.

Build a clean portable package:

```bash
python build_portable_package.py
```

Current verified result:

- Unit tests: 24 tests OK
- E2E smoke: `E2E_SMOKE_OK`
- Release integrity: `db_unchanged=true`, `mock_free=true`
- Portable ZIP smoke: `E2E_SMOKE_OK` after clean extraction

## Security Notes

- Arbitrary static file downloads are blocked.
- Source code, SQLite databases, old backup files, and documents are not served by Flask.
- `POST /api/institution/import` requires `DERIVATIVES_ADMIN_TOKEN` and a matching admin token
  in the `X-Admin-Token` or `X-Derivatives-Admin-Token` request header.
- `/api/*` routes have an in-memory per-client rate limit. Set `MARKET_PULSE_API_RATE_LIMIT_PER_MINUTE=0`
  to disable it for trusted local maintenance.
- Rate limiting uses `request.remote_addr` by default and does not trust user-supplied
  `X-Forwarded-For`. Set `MARKET_PULSE_TRUST_PROXY=1` only behind a trusted reverse proxy.
- Basic security response headers are applied globally.
- `ALLOW_UNVERIFIED_SSL_FALLBACK=1` is ignored in production/Render environments.

## Cloud Persistence

`render.yaml` sets persistent paths for deployments with a Render persistent disk:

- `MARKET_PULSE_CACHE_FILE=/var/data/twse-cache.json`
- `DERIVATIVES_DB_PATH=/var/data/derivatives-platform.sqlite3`

The SQLite store creates parent directories automatically and initializes the schema on
startup. Without a persistent disk, platform restarts may reset imported rows, AI reports,
and structured logs.

## Main Pages

- `index.html`
- `market-overview.html`
- `tw-stocks.html`
- `tw-etf.html`
- `tw-stock-search.html`
- `tw-Optional-stocks.html`
- `us-stocks.html`
- `us-etf.html`
- `us-stock-search.html`
- `us-watchlist.html`
- `derivatives-assets.html`
- `futures.html`
- `options.html`
- `derivatives-analytics.html`
- `derivatives-ai.html`
- `derivatives-status.html` / System Maintenance
- `international-finance.html`
- `precious-metals.html`
- `bonds.html`

## Key API Routes

- `GET /api/derivatives/v1-status`
- `GET /api/twse/etfs`
- `GET /api/futures`
- `GET /api/futures/<symbol>`
- `GET /api/options`
- `GET /api/options/chain`
- `GET /api/pcr`
- `GET /api/maxpain`
- `GET /api/open-interest`
- `GET /api/basis`
- `GET /api/institution`
- `POST /api/institution/import`
- `GET /api/ai-analysis`

## Portable Layout

- `app.py`: Flask app, route wiring, source fetching, parsing, cache coordination.
- `market_config.py`: market catalogs, route allowlists, API endpoint constants, and static asset allowlists.
- `derivatives/`: derivatives scoring, catalog helpers, institution import, and options helpers.
- `derivatives_store.py`: SQLite repository and schema initialization.
- `build_portable_package.py`: creates `market-platform-portable-optimized.zip` from a clean allowlist, excluding old release folders and generated files.

## Delivery Notes

The R6 ZIP is generated from an explicit allowlist. It excludes archived release folders,
old ZIPs, DOCX validation reports, personal files, obsolete backup files, and zero-byte
leftovers. The shipped SQLite database is schema-only for reproducible delivery; runtime
data is populated after startup or protected imports.
