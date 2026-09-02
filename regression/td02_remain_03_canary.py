"""TD02-REMAIN-03 canary assessment for the derivatives status ESM island.

The canary runs the real local page twice with the frozen status-page HAR:
normal ESM mode and an explicit ``td02-esm=off`` rollback mode.  It observes
asset selection, API calls, DOMContentLoaded listeners, intervals, DOM state,
and page errors without changing production assets or baselines.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "regression"
HAR_PATH = REGRESSION / "baseline" / "interactions" / "har" / "derivatives-status.html.har"
FIXED_PORT = 18766

sys.path.insert(0, str(REGRESSION))

from server_harness import start_server  # noqa: E402


class CanaryFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CanaryFailure(message)


INIT_SCRIPT = r'''
(() => {
  const telemetry = { fetches: [], listeners: [], intervals: [] };
  const nativeFetch = window.fetch.bind(window);
  window.fetch = (...args) => {
    telemetry.fetches.push(String(args[0]));
    return nativeFetch(...args);
  };
  const nativeAddEventListener = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (this === document && type === "DOMContentLoaded") {
      telemetry.listeners.push(new Error().stack || "");
    }
    return nativeAddEventListener.call(this, type, listener, options);
  };
  const nativeSetInterval = window.setInterval.bind(window);
  window.setInterval = (...args) => {
    telemetry.intervals.push(new Error().stack || "");
    return nativeSetInterval(...args);
  };
  window.__TD02_CANARY__ = telemetry;
})();
'''


def classify_resource(url: str) -> str:
    path = urlsplit(url).path
    if path.endswith("derivatives-status-esm.js"):
        return "esm-module"
    if path.endswith("derivatives-status-addon.min.js"):
        return "classic-fallback"
    if path.endswith("derivatives-status-esm-loader.js"):
        return "loader"
    return "other"


def run_mode(browser, base_url: str, mode: str) -> dict:
    require(HAR_PATH.is_file(), f"missing frozen status HAR: {HAR_PATH}")
    context = browser.new_context()
    context.route_from_har(str(HAR_PATH), url="**/api/**", not_found="abort")
    context.add_init_script(INIT_SCRIPT)
    page = context.new_page()
    page_errors: list[str] = []
    console_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "console",
        lambda message: console_errors.append(message.text)
        if message.type == "error" and "ERR_NETWORK_ACCESS_DENIED" not in message.text
        else None,
    )
    suffix = "?td02-esm=off" if mode == "rollback" else ""
    page.goto(f"{base_url}/derivatives-status.html{suffix}", wait_until="load", timeout=30000)
    try:
        page.wait_for_selector("#derivatives-status-root .panel-card", timeout=30000)
    except Exception:  # noqa: BLE001
        # Collect the page state below so a canary failure identifies the
        # failing asset/runtime instead of hiding it behind a selector timeout.
        pass
    page.wait_for_timeout(500)
    telemetry = page.evaluate("window.__TD02_CANARY__")
    resources = page.evaluate("performance.getEntriesByType('resource').map((entry) => entry.name)")
    state = page.evaluate("document.documentElement.dataset.td02Esm || ''")
    root_html = page.evaluate("document.getElementById('derivatives-status-root')?.innerHTML || ''")
    context.close()

    resource_kinds = [classify_resource(url) for url in resources]
    status_fetches = [url for url in telemetry["fetches"] if "/api/derivatives/v1-status" in url]
    esm_listeners = [stack for stack in telemetry["listeners"] if "derivatives-status-esm.js" in stack]
    fallback_listeners = [stack for stack in telemetry["listeners"] if "derivatives-status-addon.min.js" in stack]
    esm_intervals = [stack for stack in telemetry["intervals"] if "derivatives-status-esm.js" in stack]

    require("panel-card" in root_html, f"{mode} status island did not render: state={state!r}, resources={resource_kinds}, errors={page_errors + console_errors}, root={root_html[:300]!r}")
    require(not page_errors and not console_errors, f"{mode} page errors: {page_errors + console_errors}")
    require(len(status_fetches) == 1, f"{mode} status API fetch count changed: {status_fetches}")
    require("loader" in resource_kinds, f"{mode} did not load the ESM loader")
    require(esm_intervals == [], f"{mode} ESM module registered polling: {esm_intervals}")
    if mode == "normal":
        require(state == "esm-active", f"normal canary state is {state!r}")
        require("esm-module" in resource_kinds, "normal canary did not load ESM module")
        require("classic-fallback" not in resource_kinds, "normal canary unexpectedly loaded classic fallback")
        require(len(esm_listeners) <= 1, f"normal ESM listener count changed: {esm_listeners}")
        require(fallback_listeners == [], "normal ESM canary registered classic fallback listener")
    else:
        require(state == "classic-fallback", f"rollback canary state is {state!r}")
        require("classic-fallback" in resource_kinds, "rollback canary did not load classic fallback")
        require("esm-module" not in resource_kinds, "rollback canary unexpectedly loaded ESM module")
        require(esm_listeners == [], "rollback canary registered an ESM listener")
        require(len(fallback_listeners) <= 1, f"rollback fallback listener count changed: {fallback_listeners}")
    return {
        "mode": mode,
        "state": state,
        "status_api_fetches": len(status_fetches),
        "resource_kinds": resource_kinds,
        "esm_dom_content_loaded_listeners": len(esm_listeners),
        "classic_fallback_dom_content_loaded_listeners": len(fallback_listeners),
        "esm_intervals": len(esm_intervals),
        "page_errors": page_errors,
        "console_errors": console_errors,
    }


def run() -> dict:
    from playwright.sync_api import sync_playwright

    with start_server(port=FIXED_PORT) as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            normal = run_mode(browser, server.base_url, "normal")
            rollback = run_mode(browser, server.base_url, "rollback")
        finally:
            browser.close()
    return {
        "status": "pass",
        "batch": "TD02-REMAIN-03",
        "canary_scope": "derivatives-status.html only",
        "normal": normal,
        "rollback": rollback,
        "production_pages_expanded": False,
        "baseline_changed": False,
        "rollback_order": [
            "set td02-esm=off or disable ESM loader",
            "load derivatives-status-addon.min.js",
            "restore original status script wiring if island is removed",
        ],
    }


def main() -> int:
    try:
        print("TD02_REMAIN_03_CANARY_OK: " + json.dumps(run(), ensure_ascii=False, sort_keys=True))
        return 0
    except (CanaryFailure, OSError, RuntimeError) as exc:
        print(f"TD02_REMAIN_03_CANARY_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
