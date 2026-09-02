# Cloud Deployment Notes

Date: 2026-06-22

## Render Blueprint

`render.yaml` defines one web service:

- Runtime: Python
- Start command: `gunicorn --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:$PORT app:app`
- Health check: `/api/health`
- Persistent disk mount: `/var/data`

## Persistent Data Paths

The application supports path overrides through environment variables:

- `MARKET_PULSE_CACHE_FILE=/var/data/twse-cache.json`
- `DERIVATIVES_DB_PATH=/var/data/derivatives-platform.sqlite3`

`DerivativesStore` creates the DB parent directory automatically and initializes the
SQLite schema on startup.

## Important Render Plan Note

Persistent disks require a Render plan that supports disks. If the service is deployed
without a persistent disk, the platform filesystem may reset after redeploys, restarts,
or cold starts. In that case:

- imported institutional rows may be lost;
- accumulated AI reports may be lost;
- system logs stored in SQLite may be lost.

For production use, keep the persistent disk enabled or migrate the SQLite store to a
managed external database.

## Workers And Scheduler

The current background updater is process-local. Keep the service at one Gunicorn worker
unless a cross-worker scheduler lock or external cron-based refresh is introduced.

The checked-in `Procfile` and `render.yaml` both use `gunicorn --workers 1 --threads 4`.
At application startup, an explicitly detected Gunicorn worker count greater than one
emits a warning because rate-limit state, cache entries, and in-flight locks are still
process-local. `MARKET_PULSE_API_RATE_LIMIT_MAX_CLIENTS` bounds the in-process rate-limit
identity map (default: 10,000 clients).

## Cache Policy And Lifecycle

TTL values are centrally declared in `market_config.py` under `CACHE_TTL_SECONDS`.
Per-key memory-cache capacities are declared under `CACHE_BUCKET_MAX_ENTRIES` and
enforced by `cache.enforce_bucket_cap()` on writes. The bounded buckets include stock
details, option chains, external text, global-market responses, sector charts, future
technical candles, TAIFEX OpenAPI lists, and live-search deduplication.

The remaining process-local snapshots (`site_data`, international indexes, treasury
yields, listed-universe data, shareholder distributions, and Taiwan futures quotes)
replace one complete generation rather than accumulating one entry per request. Their
TTL and replacement lifecycle remain explicit in the named aliases backed by the same
central TTL registry. In-flight events are created per refresh key and removed in a
`finally` path after completion or failure.

Moving these states to Redis or another shared store remains a separate design task;
this batch deliberately keeps the current single-worker deployment contract.

## SSL Fallback

`ALLOW_UNVERIFIED_SSL_FALLBACK=1` is for local maintenance only. It is ignored in
production/Render environments to avoid accidental certificate-verification bypass.

## Service Worker Cache Version (breaking frontend/backend changes)

Static assets (`app.js`, `styles.css`, `pwa.js`, page shells, icons, manifest) are cached
client-side by `service-worker.js` using stale-while-revalidate (TD-09). `pwa.js` compares
its own `VERSION` constant against a value stored in the visitor's `localStorage`
(`market-pulse-static-version`); when they differ, it unregisters any existing service
worker and clears all Cache Storage before re-registering, so a version bump is the only
mechanism that forces every returning visitor's stale cache to fully clear.

**Any deploy that changes the contract between the cached frontend and the backend it
talks to (renamed/removed API routes or response fields the frontend depends on, changed
request formats, anything that would break if an old cached `app.js` kept running against
the new backend) must bump both:**

- `CACHE_VERSION` in `service-worker.js`
- `VERSION` in `pwa.js`

in the same deploy. Skipping this means visitors with a previously cached `app.js` can
keep running old frontend code against the new backend indefinitely, since the server
already serves all static files with `Cache-Control: no-store` (so the *files themselves*
are always fetched fresh) but that does nothing to evict what's already sitting in a
visitor's Cache Storage from a prior visit - only the `pwa.js` version-compare check does
that, and only if `pwa.js`'s own `VERSION` actually changed.

Routine, backward-compatible frontend/backend changes do not require a bump - the SW's
stale-while-revalidate strategy already refreshes the cache in the background on every
matching request, so visitors self-heal within a page load or two on their own.
