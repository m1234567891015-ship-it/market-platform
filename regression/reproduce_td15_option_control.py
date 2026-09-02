"""Acceptance fixture for the public US options control on derivatives-assets.html.

The page is served by the normal app, while all external-data API responses are
isolated in Playwright. The test covers the reachable control, a successful
symbol switch, and a failed switch with a visible retryable state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REGRESSION_DIR = Path(__file__).resolve().parent


def payloads():
    futures = {
        "category": "futures", "title": "期貨", "items": [
            {"symbol": "TX", "name": "臺指期", "close": 22000, "pct": 0.8, "region": "台灣"},
        ], "catalogCount": 1, "sourceInfo": {}, "updatedAt": "2026-01-10 12:00:00",
    }
    options = {
        "category": "options", "title": "選擇權", "items": [
            {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "close": 500, "pct": 0.4},
            {"symbol": "^VIX", "name": "CBOE Volatility Index", "close": 16.2, "pct": -0.3},
        ], "catalogCount": 2, "sourceInfo": {}, "updatedAt": "2026-01-10 12:00:00",
    }
    return futures, options


def chain_body(symbol: str):
    return {
        "symbol": symbol, "selectedExpiration": "2026-02-20", "summary": {
            "callCount": 12, "putCount": 10, "callOpenInterest": 1200,
            "putOpenInterest": 900,
        }, "calls": [{"strike": 500, "openInterest": 300, "impliedVolatility": 0.2}],
        "puts": [{"strike": 490, "openInterest": 250, "impliedVolatility": 0.22}],
    }


def worker() -> None:
    sys.path.insert(0, str(REGRESSION_DIR))
    from server_harness import start_server  # noqa: E402
    from playwright.sync_api import sync_playwright  # noqa: E402

    futures, options = payloads()
    handle = start_server()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.set_default_timeout(10000)

            def handle_route(route):
                url = route.request.url
                if "/api/futures" in url:
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"data": futures}))
                elif "/api/options" in url and "/api/options/chain" not in url:
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"data": options}))
                elif "/api/institution" in url:
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"data": {}}))
                elif "/api/news" in url:
                    route.fulfill(status=200, content_type="application/json", body=json.dumps({"data": {"items": []}}))
                elif "/api/us-market/options-chain/SPY" in url:
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(chain_body("SPY")))
                elif "/api/us-market/options-chain/QQQ" in url:
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(chain_body("QQQ")))
                elif "/api/us-market/options-chain/NVDA" in url:
                    route.fulfill(status=502, content_type="application/json", body=json.dumps({"error": "fixture failure"}))
                else:
                    route.continue_()

            page.route("**/*", handle_route)
            page.goto(f"{handle.base_url}/derivatives-assets.html", wait_until="load", timeout=15000)
            page.wait_for_selector('[data-asset-option-underlying="SPY"]')
            controls = page.locator("[data-asset-option-underlying]")
            if controls.count() != 5:
                raise AssertionError(f"expected five option controls, got {controls.count()}")

            page.locator('[data-asset-option-underlying="QQQ"]').click()
            try:
                page.locator("#asset-public-options h4", has_text="QQQ").wait_for()
            except Exception:
                print(json.dumps({
                    "debug_heading": page.locator("#asset-public-options h4").all_inner_texts(),
                    "debug_status": page.locator("[data-asset-option-status]").all_inner_texts(),
                    "debug_errors": page.locator("body").inner_text()[-500:],
                }))
                raise
            if page.locator('[data-asset-option-status][data-state="ready"]').count() != 1:
                raise AssertionError("successful option switch did not render ready status")

            page.locator('[data-asset-option-underlying="NVDA"]').click()
            page.locator('[data-asset-option-status][data-state="error"]').wait_for()
            failed_button = page.locator('[data-asset-option-underlying="NVDA"]')
            if failed_button.is_disabled():
                raise AssertionError("failed option switch left the control disabled")

            print(json.dumps({
                "controls": controls.count(), "success_symbol": "QQQ",
                "failure_state": page.locator("[data-asset-option-status]").get_attribute("data-state"),
            }))
            browser.close()
    finally:
        handle.stop()


if __name__ == "__main__":
    worker()
