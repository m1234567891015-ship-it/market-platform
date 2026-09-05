import json
import re
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from server_harness import start_server


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "docs" / "TD02_FULL_ESM_build_manifest_2026-09-01.json").read_text(encoding="utf-8"))
CURRENT_VERSION = MANIFEST["version"]
LEGACY_VERSION = "td02-full-esm-legacy-simulation"


def install_browser_mocks(context, *, seed_recovery=False, healthy=False):
    current_version = json.dumps(CURRENT_VERSION)
    marker = json.dumps(CURRENT_VERSION if seed_recovery else "")
    initial_caches = json.dumps([
        "market-pulse-swr-td02-full-esm-legacy-runtime",
        "unrelated-origin-cache",
    ])
    context.add_init_script(f"""
        (() => {{
          const stateKey = "__market_pulse_recovery_test_state";
          const currentVersion = {current_version};
          const state = JSON.parse(sessionStorage.getItem(stateKey) || {json.dumps(json.dumps({
              "registrationRemoved": False,
              "unregisterCount": 0,
              "unrelatedUnregisterCount": 0,
              "deletedCaches": [],
              "caches": json.loads(initial_caches),
              "registered": [],
          }))});
          const save = () => sessionStorage.setItem(stateKey, JSON.stringify(state));
          if (!sessionStorage.getItem("market-pulse-runtime-recovery-attempted") && {json.dumps(seed_recovery)}) {{
            sessionStorage.setItem("market-pulse-runtime-recovery-attempted", {marker});
          }}
          if ({json.dumps(healthy)}) {{
            state.registrationRemoved = false;
            localStorage.setItem("market-pulse-static-version", currentVersion);
            save();
          }}
          if (!{json.dumps(healthy)}) localStorage.setItem("market-pulse-watchlist-v1", "[\\\"TX\\\"]");
          const appRegistration = () => ({{
            scope: location.origin + "/",
            active: {{ scriptURL: location.origin + "/service-worker.js?v=legacy" }},
            waiting: null,
            installing: null,
            unregister: async () => {{ state.unregisterCount += 1; state.registrationRemoved = true; save(); return true; }},
          }});
          const unrelatedRegistration = () => ({{
            scope: location.origin + "/unrelated/",
            active: {{ scriptURL: location.origin + "/unrelated-worker.js" }},
            waiting: null,
            installing: null,
            unregister: async () => {{ state.unrelatedUnregisterCount += 1; save(); return true; }},
          }});
          const serviceWorker = {{
            get controller() {{
              return state.registrationRemoved ? null : {{ scriptURL: location.origin + "/service-worker.js?v=legacy" }};
            }},
            getRegistrations: async () => state.registrationRemoved ? [] : [appRegistration(), unrelatedRegistration()],
            register: async (url) => {{ state.registered.push(url); save(); return appRegistration(); }},
          }};
          const cacheStorage = {{
            keys: async () => [...state.caches],
            delete: async (key) => {{ state.deletedCaches.push(key); state.caches = state.caches.filter((value) => value !== key); save(); return true; }},
          }};
          Object.defineProperty(navigator, "serviceWorker", {{ configurable: true, value: serviceWorker }});
          Object.defineProperty(window, "caches", {{ configurable: true, value: cacheStorage }});
          save();
        }})();
    """)


def read_state(page):
    return page.evaluate("JSON.parse(sessionStorage.getItem('__market_pulse_recovery_test_state'))")


class LegacyServiceWorkerRecoveryTests(unittest.TestCase):
    def test_legacy_recovery_healthy_client_loop_guard_and_reinstall(self):
        with start_server() as server, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            current_html = server_request(server.base_url, "/derivatives-analytics.html")
            current_loader_version = re.search(r"market-pulse-esm-loader\.js\?v=([^\"']+)", current_html).group(1)
            self.assertEqual(current_loader_version, CURRENT_VERSION)

            def fulfill_api(route):
                route.fulfill(status=200, content_type="application/json", body=json.dumps({"success": True, "data": {}}))

            recovery_context = browser.new_context()
            install_browser_mocks(recovery_context)
            recovery_context.route("**/api/**", fulfill_api)
            recovery_requests = []
            recovery_context.on("request", lambda request: recovery_requests.append(request.url))
            recovery_context.route(
                "**/legacy-derivatives-analytics.html**",
                lambda route: route.fulfill(
                    status=200,
                    content_type="text/html",
                    body=current_html if "runtime_recovery=" in route.request.url else current_html.replace(
                        f"market-pulse-esm-loader.js?v={CURRENT_VERSION}",
                        f"market-pulse-esm-loader.js?v={LEGACY_VERSION}",
                    ),
                ),
            )
            recovery_page = recovery_context.new_page()
            recovery_page.goto(f"{server.base_url}/legacy-derivatives-analytics.html", wait_until="load")
            recovery_page.wait_for_function(
                "document.querySelector('#derivatives-analytics-root')?.textContent.includes('衍生品市場狀態')",
                timeout=15000,
            )
            recovery_page.wait_for_function(
                "JSON.parse(sessionStorage.getItem('__market_pulse_recovery_test_state')).registered.some((url) => url.includes('service-worker.js?v=' + " + json.dumps(CURRENT_VERSION) + "))",
                timeout=5000,
            )
            state = read_state(recovery_page)
            self.assertTrue(any(f"/market-pulse-esm-loader.js?v={LEGACY_VERSION}" in url for url in recovery_requests))
            self.assertEqual(sum("runtime_recovery=" in url for url in recovery_requests), 1)
            self.assertEqual(state["unregisterCount"], 1)
            self.assertEqual(state["unrelatedUnregisterCount"], 0)
            self.assertEqual(state["deletedCaches"], ["market-pulse-swr-td02-full-esm-legacy-runtime"])
            self.assertIn("unrelated-origin-cache", state["caches"])
            self.assertTrue(any("market-pulse-esm-loader.js?v=" + CURRENT_VERSION in url for url in recovery_requests))
            self.assertIn("service-worker.js?v=" + CURRENT_VERSION, state["registered"])
            self.assertEqual(recovery_page.evaluate("localStorage.getItem('market-pulse-watchlist-v1')"), '["TX"]')
            required = {
                "/api/futures?limit=12",
                "/api/options?limit=12",
                "/api/options/chain?underlying=TXO&source=auto",
                "/api/pcr?underlying=TXO&source=auto",
                "/api/institution?product=TX",
                "/api/basis?future=TX&spot=TAIEX",
            }
            observed = {url.split(server.base_url, 1)[-1] for url in recovery_requests}
            self.assertTrue(required.issubset(observed))
            recovery_context.close()

            healthy_context = browser.new_context()
            install_browser_mocks(healthy_context, healthy=True)
            healthy_context.route("**/api/**", fulfill_api)
            healthy_page = healthy_context.new_page()
            healthy_page.goto(f"{server.base_url}/derivatives-analytics.html", wait_until="load")
            healthy_page.wait_for_function(
                "document.querySelector('#derivatives-analytics-root')?.textContent.includes('衍生品市場狀態')",
                timeout=15000,
            )
            healthy_state = read_state(healthy_page)
            self.assertEqual(healthy_state["unregisterCount"], 0)
            self.assertEqual(healthy_state["deletedCaches"], [])
            healthy_context.close()

            loop_context = browser.new_context()
            install_browser_mocks(loop_context, seed_recovery=True)
            loop_context.route("**/legacy-derivatives-analytics.html**", lambda route: route.fulfill(status=200, content_type="text/html", body=current_html.replace(
                f"market-pulse-esm-loader.js?v={CURRENT_VERSION}",
                f"market-pulse-esm-loader.js?v={LEGACY_VERSION}",
            )))
            diagnostics = []
            loop_context.on("console", lambda message: diagnostics.append(message.text))
            loop_requests = []
            loop_context.on("request", lambda request: loop_requests.append(request.url))
            loop_page = loop_context.new_page()
            loop_page.goto(f"{server.base_url}/legacy-derivatives-analytics.html", wait_until="load")
            loop_page.wait_for_timeout(500)
            loop_state = read_state(loop_page)
            self.assertTrue(any("recovery already attempted; refusing reload loop" in message for message in diagnostics))
            self.assertEqual(sum("runtime_recovery=" in url for url in loop_requests), 0)
            self.assertEqual(loop_state["unregisterCount"], 0)
            self.assertEqual(loop_state["deletedCaches"], [])
            loop_context.close()
            browser.close()


def server_request(base_url, path):
    import urllib.request

    with urllib.request.urlopen(base_url + path) as response:
        return response.read().decode("utf-8")


if __name__ == "__main__":
    unittest.main()
