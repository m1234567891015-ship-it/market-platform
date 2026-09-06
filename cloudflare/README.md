# Cloudflare hybrid migration (local only)

This directory contains the local-only Worker and Wrangler configuration for the
hybrid topology:

```text
browser -> same-origin Worker on :8787 -> Flask backend on :5103
browser -> Static Assets served from dist/cloudflare-static
Flask  -> existing persistent SQLite (unchanged)
```

The browser keeps using relative `/api/*` URLs. The Worker has one fixed
`ORIGIN_API_BASE`; it never accepts an upstream URL from a request parameter,
header, body, or cookie. Static assets are built from explicit project
allowlists, and the generated `dist/` directory is ignored by Git.

## Local run

```powershell
Copy-Item cloudflare/.dev.vars.example cloudflare/.dev.vars
python scripts/build-cloudflare-static.py
python scripts/verify-cloudflare-dist.py
python app.py
npm run cloudflare:dev -- --port 8787 --show-interactive-dev-session=false
```

The commands above are local development commands only. `cloudflare:dry-run`
bundles and validates the Worker without uploading it.

The production origin, DNS, routes, Cloudflare resources, Render shutdown,
SQLite migration, queues, Durable Objects, KV, R2, Hyperdrive, Cron, and
Workflows are deliberately out of scope for this phase.
