"""Targeted local regression coverage for the two production loading failures."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_harness import start_server


class TargetedPageLoadingTests(unittest.TestCase):
    def _load_page(self, base_url: str, page_name: str, root_selector: str, loading_marker: str) -> list[str]:
        requests: list[str] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()

            def fulfill_api(route) -> None:
                path = route.request.url.split(base_url, 1)[-1]
                requests.append(path)
                endpoint = path.split("?", 1)[0]
                if endpoint in {"/api/futures", "/api/options"}:
                    category = endpoint.rsplit("/", 1)[-1]
                    payload = {"category": category, "items": [], "summary": {}}
                elif endpoint == "/api/news":
                    payload = {"items": []}
                else:
                    payload = {}
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"success": True, "data": payload}),
                )

            context.route("**/api/**", fulfill_api)
            page = context.new_page()
            page.goto(f"{base_url}/{page_name}", wait_until="load")
            page.wait_for_function(
                "({selector, marker}) => { const node = document.querySelector(selector); "
                "return Boolean(node && !node.textContent.includes(marker)); }",
                arg={"selector": root_selector, "marker": loading_marker},
                timeout=15000,
            )
            context.close()
            browser.close()
        return requests

    def test_derivatives_assets_exits_initial_loading(self) -> None:
        with start_server() as server:
            requests = self._load_page(
                server.base_url,
                "derivatives-assets.html",
                "#asset-hub-root",
                "載入中",
            )
        derivative_requests = [request for request in requests if request.startswith(("/api/futures?", "/api/options?"))]
        self.assertTrue(any(request.startswith("/api/futures?limit=12") for request in derivative_requests))
        self.assertTrue(any(request.startswith("/api/options?limit=12") for request in derivative_requests))
        self.assertFalse(any("limit=all" in request for request in derivative_requests))

    def test_options_exits_initial_loading(self) -> None:
        with start_server() as server:
            requests = self._load_page(
                server.base_url,
                "options.html",
                "#global-market-root",
                "線上資料載入中",
            )
        option_requests = [request for request in requests if request.startswith("/api/options?")]
        self.assertTrue(any(request.startswith("/api/options?limit=12") for request in option_requests))
        self.assertFalse(any("limit=all" in request for request in option_requests))


if __name__ == "__main__":
    unittest.main()
