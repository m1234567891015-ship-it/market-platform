"""TD-02 Phase 4 browser canary for all 21 pages.

Each page is opened in normal ESM mode and explicit ``td02-esm=off`` mode
against its frozen API HAR. The canary verifies the ESM asset, classic
fallback, DOM counts, and page error boundary without changing baselines.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from frontend_check import HAR_DIR, _is_external_resource_error, _measure_page  # noqa: E402
from server_harness import start_server  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / "regression" / "baseline" / "frontend_manifest.json").read_text(encoding="utf-8"))
BASELINE_BY_FILE = {item["file"]: item for item in BASELINE["pages"]}
PAGES = sorted(path.name for path in ROOT.glob("*.html"))
VERSION = "td02-full-esm-20260901-1"


class CanaryFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CanaryFailure(message)


def run_page(browser, base_url: str, page_file: str, rollback: bool) -> dict:
    har_path = HAR_DIR / f"{page_file}.har"
    require(har_path.is_file(), f"missing HAR: {har_path}")
    context = browser.new_context(service_workers="block")
    context.route_from_har(str(har_path), url="**/api/**", not_found="abort")
    page_errors: list[str] = []
    console_errors: list[str] = []
    external_errors: list[str] = []
    page = context.new_page()
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            external_errors if _is_external_resource_error(message.text) else console_errors
        ).append(message.text)
        if message.type == "error"
        else None,
    )
    query = "?td02-esm=off" if rollback else ""
    page.goto(f"{base_url}/{page_file}{query}", wait_until="load", timeout=30000)
    page.wait_for_timeout(1500)
    state = page.evaluate("document.documentElement.dataset.td02Esm || ''")
    page_search = page.evaluate("window.location.search")
    resources = page.evaluate("performance.getEntriesByType('resource').map((entry) => entry.name)")
    counts = _measure_page(page)
    context.close()

    local_resources = [Path(url.split("?", 1)[0]).name for url in resources if "127.0.0.1" in url]
    expected = BASELINE_BY_FILE[page_file]["counts"]
    require(not page_errors and not console_errors, f"{page_file} {'rollback' if rollback else 'normal'} errors: {page_errors + console_errors}")
    require(counts == expected, f"{page_file} {'rollback' if rollback else 'normal'} DOM counts changed: expected={expected}, actual={counts}")
    if rollback:
        require(state == "classic-fallback", f"{page_file} rollback state={state!r} search={page_search!r} url={page.url!r}")
        require("common-runtime.min.js" in local_resources, f"{page_file} rollback missed common fallback")
        require("route-bundle.min.js" in local_resources, f"{page_file} rollback missed route fallback")
        if page_file == "derivatives-status.html":
            require("derivatives-status-addon.min.js" in local_resources, "status rollback missed addon fallback")
        require("market-pulse-esm.min.js" not in local_resources, f"{page_file} rollback loaded ESM")
    else:
        require(state == "esm-active", f"{page_file} normal state={state!r}")
        require("market-pulse-esm.min.js" in local_resources, f"{page_file} normal missed ESM bundle")
        require("common-runtime.min.js" not in local_resources, f"{page_file} normal loaded common fallback")
        require("route-bundle.min.js" not in local_resources, f"{page_file} normal loaded route fallback")
    return {"page": page_file, "mode": "rollback" if rollback else "normal", "state": state, "counts": counts, "local_resources": local_resources, "external_errors": external_errors}


def main() -> None:
    require(len(PAGES) == 21, f"expected 21 pages, found {len(PAGES)}")
    from playwright.sync_api import sync_playwright

    results = []
    with start_server(port=18765) as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for page_file in PAGES:
                print(f"  [normal] {page_file} ...", flush=True)
                results.append(run_page(browser, server.base_url, page_file, False))
                print(f"  [rollback] {page_file} ...", flush=True)
                results.append(run_page(browser, server.base_url, page_file, True))
        finally:
            browser.close()
    print(json.dumps({"status": "TD02_FULL_ESM_CANARY_OK", "pages": len(PAGES), "runs": len(results), "version": VERSION, "baseline_changed": False}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (CanaryFailure, OSError, RuntimeError) as error:
        print(f"TD02_FULL_ESM_CANARY_FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
