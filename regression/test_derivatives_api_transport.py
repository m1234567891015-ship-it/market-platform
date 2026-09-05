import json
import sys
import unittest
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_harness import start_server


ROOT = Path(__file__).resolve().parents[1]


class DerivativesApiTransportTests(unittest.TestCase):
    def _current_html(self, base_url):
        with urllib.request.urlopen(base_url + "/derivatives-analytics.html") as response:
            return response.read().decode("utf-8")

    def _load_page(self, context, base_url, overrides=None):
        overrides = overrides or {}
        requests = []

        def fulfill_api(route):
            path = route.request.url.split(base_url, 1)[-1]
            requests.append(path)
            override = overrides.get(path)
            if override:
                if override.get("action") == "abort":
                    route.abort()
                    return
                route.fulfill(
                    status=override.get("status", 200),
                    content_type=override.get("content_type", "application/json"),
                    body=override.get("body", ""),
                )
                return
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"success": True, "data": {}}))

        context.route("**/api/**", fulfill_api)
        page = context.new_page()
        page.goto(base_url + "/derivatives-analytics.html", wait_until="load")
        page.get_by_text("衍生品市場狀態", exact=False).first.wait_for(state="visible", timeout=15000)
        return page, requests

    def test_html_and_malformed_json_responses_are_structured_failures(self):
        scenarios = [
            (
                "502_html",
                {"/api/basis?future=TX&spot=TAIEX": {"status": 502, "content_type": "text/html", "body": "<!DOCTYPE html><html><body>502</body></html>"}},
                "HTTP_ERROR",
            ),
            (
                "200_html",
                {"/api/basis?future=TX&spot=TAIEX": {"status": 200, "content_type": "text/html", "body": "<!DOCTYPE html><html><body>not json</body></html>"}},
                "INVALID_RESPONSE",
            ),
            (
                "malformed_json",
                {"/api/basis?future=TX&spot=TAIEX": {"status": 200, "content_type": "application/json", "body": "{not-json"}},
                "INVALID_RESPONSE",
            ),
        ]
        with start_server() as server, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for name, overrides, expected_code in scenarios:
                with self.subTest(name=name):
                    context = browser.new_context()
                    page, _ = self._load_page(context, server.base_url, overrides)
                    text = page.locator("#derivatives-analytics-root").inner_text()
                    self.assertIn(expected_code, text)
                    self.assertNotIn("Unexpected token '<'", text)
                    context.close()
            browser.close()

    def test_transport_failure_does_not_render_valid_zero_dataset(self):
        with start_server() as server, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            page, _ = self._load_page(context, server.base_url, {
                "/api/futures?limit=12": {"status": 502, "content_type": "text/html", "body": "<!DOCTYPE html><html><body>502</body></html>"},
            })
            futures_snapshot = page.locator(".asset-hub-summary-card").nth(0).inner_text()
            self.assertIn("資料暫不可用", futures_snapshot)
            self.assertNotIn("0\n有效資料", futures_snapshot)
            context.close()
            browser.close()


if __name__ == "__main__":
    unittest.main()
