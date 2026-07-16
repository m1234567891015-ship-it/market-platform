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

## SSL Fallback

`ALLOW_UNVERIFIED_SSL_FALLBACK=1` is for local maintenance only. It is ignored in
production/Render environments to avoid accidental certificate-verification bypass.
