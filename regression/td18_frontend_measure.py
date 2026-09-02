"""TD-18 H-06-02: measure cold/warm frontend loading without touching baselines.

The existing API HAR files are replayed so external market data does not affect
the measurements.  Browser HTTP cache is isolated per context: cold uses a new
context, warm is a reload in the same context, and refresh is a second reload.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from interaction_check import _background_route_handler  # noqa: E402
from interaction_specs import PAGES  # noqa: E402
from server_harness import start_server  # noqa: E402

REGRESSION_DIR = Path(__file__).resolve().parent
BASELINE_DIR = REGRESSION_DIR / "baseline"
HAR_DIR = BASELINE_DIR / "interactions" / "har"
FIXED_SERVER_PORT = 18766


def _route_api_har(context, page_file: str) -> None:
    har_path = HAR_DIR / f"{page_file}.har"
    if not har_path.exists():
        raise SystemExit(f"missing interaction HAR: {har_path}")
    context.route_from_har(str(har_path), url="**/api/**", not_found="abort")
    context.route("**/api/**", lambda route: _background_route_handler(route, page_file))


def _meaningful(page) -> bool:
    return bool(
        page.evaluate(
            """() => {
                const main = document.querySelector("main, [role='main'], #app, body");
                return !!main && (main.innerText || "").trim().length >= 120;
            }"""
        )
    )


def _wait_meaningful(page, start: float, timeout: float = 45.0) -> float | None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            if _meaningful(page):
                return (time.perf_counter() - start) * 1000
            page.wait_for_timeout(100)
        except Exception:  # noqa: BLE001
            # Redirect pages (currently derivatives-ai.html) can replace the
            # document between the evaluate and the next polling tick.
            continue
    return None


def _page_metrics(page, elapsed_ms: float, meaningful_ms: float | None, failed: list[str]) -> dict:
    raw = page.evaluate(
        """() => {
            const nav = performance.getEntriesByType("navigation")[0] || {};
            const resources = performance.getEntriesByType("resource").map((entry) => ({
                name: entry.name,
                initiatorType: entry.initiatorType,
                transferSize: entry.transferSize || 0,
                encodedBodySize: entry.encodedBodySize || 0,
                decodedBodySize: entry.decodedBodySize || 0,
            }));
            return {
                navigation: {
                    duration: nav.duration || 0,
                    domContentLoaded: nav.domContentLoadedEventEnd || 0,
                    loadEventEnd: nav.loadEventEnd || 0,
                    responseEnd: nav.responseEnd || 0,
                },
                resources,
            };
        }"""
    )
    resources = raw["resources"]
    assets = [
        item
        for item in resources
        if any(
            marker in item["name"]
            for marker in (
                "/js/",
                "/split-",
                "/app.js",
                "/pwa.js",
                "/derivatives-ui.js",
            )
        )
    ]
    cached = [item for item in assets if item["transferSize"] == 0]
    return {
        "elapsed_ms": round(elapsed_ms, 1),
        "first_meaningful_render_proxy_ms": round(meaningful_ms, 1) if meaningful_ms is not None else None,
        "navigation_ms": round(raw["navigation"]["duration"], 1),
        "dom_content_loaded_ms": round(raw["navigation"]["domContentLoaded"], 1),
        "load_event_end_ms": round(raw["navigation"]["loadEventEnd"], 1),
        "request_count": len(resources),
        "asset_request_count": len(assets),
        "asset_transfer_bytes": sum(item["transferSize"] for item in assets),
        "asset_encoded_bytes": sum(item["encodedBodySize"] for item in assets),
        "asset_cache_hit_count": len(cached),
        "asset_cache_miss_count": len(assets) - len(cached),
        "api_request_count": sum(1 for item in resources if "/api/" in item["name"]),
        "error_count": len(failed),
        "errors": failed[:3],
    }


def _visit(context, base_url: str, page_file: str, reload_page=None) -> tuple[object, dict]:
    page = reload_page or context.new_page()
    failed: list[str] = []
    page.on("requestfailed", lambda request: failed.append(request.url))
    start = time.perf_counter()
    try:
        if reload_page is None:
            page.goto(f"{base_url}/{page_file}", wait_until="commit", timeout=30000)
        else:
            page.reload(wait_until="commit", timeout=30000)
    except Exception:  # noqa: BLE001
        # A same-page redirect may destroy the execution context after the
        # initial response; the final document is still usable for metrics.
        pass
    meaningful_ms = _wait_meaningful(page, start)
    try:
        page.wait_for_load_state("load", timeout=30000)
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(300)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return page, _page_metrics(page, elapsed_ms, meaningful_ms, failed)


def _representative_interaction(page, spec) -> dict:
    step = next((item for item in spec.steps if item.action is not None), None)
    if step is None:
        return {"id": None, "status": "render-only"}
    result = {"id": step.id, "status": "ok"}
    try:
        if step.pre_fill:
            selector, value = step.pre_fill
            page.locator(selector).first.evaluate("(el, v) => { el.value = v; }", value)
        locator = page.locator(step.selector).nth(step.action_index)
        if step.action == "click":
            locator.click(timeout=10000)
        elif step.action == "fill":
            locator.click(timeout=10000)
            locator.fill(step.action_value or "", timeout=10000)
        elif step.action == "select":
            if step.action_value is None:
                locator.select_option(index=1, timeout=10000)
            else:
                locator.select_option(step.action_value, timeout=10000)
        page.wait_for_timeout(500)
    except Exception as exc:  # noqa: BLE001
        result["status"] = "error"
        result["error"] = str(exc).splitlines()[0][:240]
    return result


def run() -> dict:
    from playwright.sync_api import sync_playwright

    rows = []
    with start_server(port=FIXED_SERVER_PORT) as server, sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for spec in PAGES:
                print(f"  [measure] {spec.file} ...", flush=True)
                cold_context = browser.new_context(service_workers="block")
                _route_api_har(cold_context, spec.file)
                _, cold = _visit(cold_context, server.base_url, spec.file)
                cold_context.close()

                warm_context = browser.new_context(service_workers="block")
                _route_api_har(warm_context, spec.file)
                page, _ = _visit(warm_context, server.base_url, spec.file)
                _, warm = _visit(warm_context, server.base_url, spec.file, reload_page=page)
                interaction = _representative_interaction(page, spec)
                _, refresh = _visit(warm_context, server.base_url, spec.file, reload_page=page)
                warm_context.close()
                rows.append({"page": spec.file, "cold": cold, "warm": warm, "refresh": refresh, "interaction": interaction})
        finally:
            browser.close()

    def avg(mode: str, key: str) -> float:
        values = [row[mode][key] for row in rows if row[mode][key] is not None]
        return round(sum(values) / len(values), 1) if values else 0.0

    return {
        "method": {
            "pages": len(rows),
            "cold": "new browser context and first navigation",
            "warm": "reload in same context after first navigation",
            "refresh": "second reload in same context",
            "api_source": "regression/baseline/interactions/har/*.har",
            "service_workers": "blocked; browser HTTP cache remains measurable",
        },
        "aggregate": {
            "cold_avg_navigation_ms": avg("cold", "navigation_ms"),
            "warm_avg_navigation_ms": avg("warm", "navigation_ms"),
            "refresh_avg_navigation_ms": avg("refresh", "navigation_ms"),
            "cold_avg_meaningful_ms": avg("cold", "first_meaningful_render_proxy_ms"),
            "warm_avg_meaningful_ms": avg("warm", "first_meaningful_render_proxy_ms"),
            "refresh_avg_meaningful_ms": avg("refresh", "first_meaningful_render_proxy_ms"),
            "cold_total_asset_transfer_bytes": sum(row["cold"]["asset_transfer_bytes"] for row in rows),
            "warm_total_asset_transfer_bytes": sum(row["warm"]["asset_transfer_bytes"] for row in rows),
            "refresh_total_asset_transfer_bytes": sum(row["refresh"]["asset_transfer_bytes"] for row in rows),
            "cold_total_asset_cache_hits": sum(row["cold"]["asset_cache_hit_count"] for row in rows),
            "warm_total_asset_cache_hits": sum(row["warm"]["asset_cache_hit_count"] for row in rows),
            "refresh_total_asset_cache_hits": sum(row["refresh"]["asset_cache_hit_count"] for row in rows),
            "interaction_ok": sum(row["interaction"]["status"] in ("ok", "render-only") for row in rows),
            "interaction_errors": sum(row["interaction"]["status"] == "error" for row in rows),
        },
        "pages": rows,
    }


if __name__ == "__main__":
    result = run()
    output = result
    if "--summary" in sys.argv:
        fields = (
            "navigation_ms",
            "first_meaningful_render_proxy_ms",
            "request_count",
            "asset_request_count",
            "asset_transfer_bytes",
            "asset_cache_hit_count",
        )
        summary = {
            "aggregate": result["aggregate"],
            "pages": [
                {
                    "page": row["page"],
                    "cold": {key: row["cold"][key] for key in fields},
                    "warm": {key: row["warm"][key] for key in fields},
                    "refresh": {key: row["refresh"][key] for key in fields},
                    "interaction": row["interaction"],
                }
                for row in result["pages"]
            ],
        }
        output = summary
    json_out = next((sys.argv[index + 1] for index, value in enumerate(sys.argv[:-1]) if value == "--json-out"), None)
    if json_out:
        Path(json_out).write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
