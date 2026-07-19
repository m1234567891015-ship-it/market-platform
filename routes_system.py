"""System/infrastructure routes extracted from app.py (TD-01 slice 5, Phase B,
batch B0) - the first of 4 domain Blueprint modules. Holds the 8 routes with
the least business-domain logic (health check, PWA manifest/service-worker,
3 legacy HTML redirects, whitelisted asset serving, and the root static-file
catch-all) plus the 24-entry `PAGE_ROUTES` programmatic registration loop
that serves every top-level HTML page - all originally app.py:830-2488.

Registered on the main `app` object in app.py via
`app.register_blueprint(bp)`. Blueprint endpoint names get an automatic
`system.` prefix (e.g. `system.api_health`) - confirmed safe by a repo-wide
search before this slice began: zero uses of `url_for(`, `request.endpoint`,
`app.view_functions`, or `app.url_map` exist anywhere in this codebase
(app.py, security.py, cache.py, builders.py, fetchers.py, parsers.py,
market_config.py, tests, `*.html` templates, app.js), so nothing depends on
the exact endpoint string - only URL paths matter, and those are unchanged.
The two global security hooks (`add_security_headers`/`enforce_api_rate_limit`,
registered in app.py) dispatch on `request.path`, not endpoint name, so they
keep firing identically regardless of which module defines a view.

`no_store_static_response`/`send_no_store_root_file`/`redirect_legacy_page`
are EXCLUSIVE helpers (grep-confirmed zero callers anywhere outside this
route cluster) and move with their callers. `BASE_DIR` is redefined locally
via the same `Path(__file__).resolve().parent` computation app.py itself
uses - both files live in the same project-root directory, so this evaluates
to an identical path; simpler than a deferred `import app` for a constant
that's purely derived from filesystem location.

Flask gotcha found while moving the `PAGE_ROUTES` loop: `Blueprint.add_url_rule`
rejects any `endpoint=` containing a `.` character (dots are reserved for
blueprint namespacing), but the original app.py code built endpoints like
`f"static_page_{page_index}_{filename}"` where `filename` is e.g.
`"index.html"` - fine for `app.add_url_rule` (no blueprint involved), a hard
`ValueError` for `bp.add_url_rule`. Fixed by `.replace(".", "_")` on the
generated endpoint string. Confirmed safe: nothing in the repo depends on
this exact endpoint string (same `url_for`/`request.endpoint` search as
above), so changing `static_page_0_index.html` to `static_page_0_index_html`
(then further prefixed to `system.static_page_0_index_html` by blueprint
registration) has zero behavioral effect - only the URL path matters, and
that's untouched.

`security_guardrail_check.py`'s S-01 static-whitelist check
(`check_static_whitelist_static`) requires `send_from_directory` to appear in
app.py's or market_config.py's source text; since `whitelisted_assets`/
`static_files` (the two `send_from_directory` call sites) moved here, that
check's scanned-file tuple was extended to include this module too - see the
batch B0 commit for the corresponding `security_guardrail_check.py` change.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, Response, abort, jsonify, redirect, request, send_from_directory

from cache import cache_data, cache_lock
from market_config import ASSET_STATIC_FILES, PAGE_ROUTES, ROOT_STATIC_FILES


BASE_DIR = Path(__file__).resolve().parent

bp = Blueprint("system", __name__)


@bp.route("/api/health")
def api_health():
    with cache_lock:
        return jsonify(
            {
                "status": "ok" if cache_data["site_data"] else "warming",
                "cachedAt": cache_data["cached_at"],
                "lastError": cache_data["last_error"],
            }
        )


@bp.route("/manifest.webmanifest")
def pwa_manifest():
    response = send_from_directory(BASE_DIR, "manifest.webmanifest", mimetype="application/manifest+json")
    return no_store_static_response(response)


@bp.route("/service-worker.js")
def pwa_service_worker():
    response = send_from_directory(BASE_DIR, "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return no_store_static_response(response)


def no_store_static_response(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def send_no_store_root_file(filename: str, **kwargs: Any) -> Response:
    response = send_from_directory(BASE_DIR, filename, **kwargs)
    return no_store_static_response(response)


def redirect_legacy_page(target: str):
    query = request.query_string.decode("utf-8")
    if query:
        target = f"{target}?{query}"
    return redirect(target, code=301)


@bp.route("/sectors.html")
def legacy_sectors_page():
    return redirect_legacy_page("/tw-stocks.html")


@bp.route("/stock-search.html")
def legacy_stock_search_page():
    return redirect_legacy_page("/tw-stock-search.html")


@bp.route("/Optional-stocks.html")
def legacy_optional_stocks_page():
    return redirect_legacy_page("/tw-Optional-stocks.html")


for page_index, (route, filename) in enumerate(PAGE_ROUTES.items()):
    bp.add_url_rule(
        route,
        endpoint=f"static_page_{page_index}_{filename}".replace(".", "_"),
        view_func=lambda filename=filename: send_no_store_root_file(filename),
    )


@bp.route("/assets/<path:filename>")
def whitelisted_assets(filename: str):
    normalized = filename.replace("\\", "/").lstrip("/")
    if "/" in normalized or normalized not in ASSET_STATIC_FILES:
        abort(404)
    return send_from_directory(BASE_DIR / "assets", normalized)


@bp.route("/<path:filename>")
def static_files(filename: str):
    normalized = filename.replace("\\", "/").lstrip("/")
    if "/" in normalized or normalized not in ROOT_STATIC_FILES:
        abort(404)
    return send_no_store_root_file(normalized)
