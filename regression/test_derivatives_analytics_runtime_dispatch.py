import json
import re
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_harness import start_server


class DerivativesAnalyticsRuntimeDispatchTests(unittest.TestCase):
    def test_real_html_loader_bundle_dispatches_analytics_and_status_control(self):
        with start_server() as server, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            requests = []

            html_response = context.request.get(f"{server.base_url}/derivatives-analytics.html")
            self.assertEqual(html_response.status, 200)
            html = html_response.text()
            version = re.search(r"market-pulse-esm-loader\.js\?v=([^\"']+)", html).group(1)
            manifest = json.loads((Path(__file__).resolve().parents[1] / "docs" / "TD02_FULL_ESM_build_manifest_2026-09-01.json").read_text(encoding="utf-8"))
            self.assertEqual(version, manifest["version"])
            self.assertNotIn("td02-full-esm-20260901-1", html)
            self.assertIn("no-store", html_response.headers.get("cache-control", ""))
            loader_response = context.request.get(f"{server.base_url}/market-pulse-esm-loader.js?v={version}")
            self.assertEqual(loader_response.status, 200)
            self.assertIn("encodeURIComponent(runtimeVersion)", loader_response.text())
            bundle_response = context.request.get(f"{server.base_url}/market-pulse-esm.min.js?v={version}")
            self.assertEqual(bundle_response.status, 200)
            self.assertIn("immutable", bundle_response.headers.get("cache-control", ""))

            def fulfill_api(route):
                url = route.request.url
                requests.append(url)
                if "/api/derivatives/v1-status" in url:
                    data = {"coverage": {"futures": {}, "options": {}}, "futures": [], "options": []}
                else:
                    data = {}
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"success": True, "data": data}))

            context.route("**/api/**", fulfill_api)
            status_page = context.new_page()
            status_page.goto(f"{server.base_url}/derivatives-status.html", wait_until="load")
            status_page.wait_for_timeout(500)
            self.assertIn("V1 國內期權資料狀態", status_page.locator("#derivatives-status-root").inner_text())
            self.assertTrue(any("/api/derivatives/v1-status" in url for url in requests))

            requests.clear()
            analytics_page = context.new_page()
            analytics_page.goto(f"{server.base_url}/derivatives-analytics.html", wait_until="load")
            analytics_page.locator("#derivatives-analytics-root").get_by_text("衍生品市場狀態", exact=False).first.wait_for(state="visible", timeout=10000)
            required = {
                "/api/futures?limit=12",
                "/api/options?limit=12",
                "/api/options/chain?underlying=TXO&source=auto",
                "/api/pcr?underlying=TXO&source=auto",
                "/api/institution?product=TX",
                "/api/basis?future=TX&spot=TAIEX",
            }
            observed = {url.split(server.base_url, 1)[-1] for url in requests}
            for endpoint in required:
                self.assertIn(endpoint, observed)
            analytics_text = analytics_page.locator("#derivatives-analytics-root").inner_text()
            self.assertIn("TAIFEX", analytics_text)
            browser.close()


if __name__ == "__main__":
    unittest.main()
