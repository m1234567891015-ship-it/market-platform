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
