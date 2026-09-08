"""Offline regression coverage for the three post-deploy API remediations."""

from __future__ import annotations

import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from werkzeug.middleware.proxy_fix import ProxyFix

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")
_tmpdir = tempfile.TemporaryDirectory(prefix="market-pulse-api-remediation-")
os.environ.setdefault("MARKET_PULSE_CACHE_FILE", str(Path(_tmpdir.name) / "cache.json"))
os.environ.setdefault("DERIVATIVES_DB_PATH", str(Path(_tmpdir.name) / "derivatives.sqlite3"))

import app
import cache
import fetchers
import routes_global_market
import routes_twse
import security


def http_error(code: int) -> HTTPError:
    return HTTPError("https://provider.invalid/data", code, "upstream", {}, BytesIO())


class ProductionApiRemediationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.app.test_client()
        self.original_limit = security.API_RATE_LIMIT_PER_WINDOW
        security.API_RATE_LIMIT_PER_WINDOW = 120
        with security.API_RATE_LIMIT_LOCK:
            security.API_RATE_LIMIT_STATE.clear()
        with cache.cache_lock:
            cache.cache_data["site_data"] = None
            cache.cache_data["us_etf_center"].clear()
        cache.provider_cooldowns.clear()

    def tearDown(self) -> None:
        security.API_RATE_LIMIT_PER_WINDOW = self.original_limit
        with security.API_RATE_LIMIT_LOCK:
            security.API_RATE_LIMIT_STATE.clear()
        with cache.cache_lock:
            cache.cache_data["site_data"] = None
            cache.cache_data["us_etf_center"].clear()
        cache.provider_cooldowns.clear()

    def test_news_upstream_429_uses_existing_empty_result_contract(self) -> None:
        with patch.object(fetchers, "fetch_from_registry", side_effect=http_error(429)):
            response = self.client.get("/api/news?symbol=%5EVIX")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["success"])
        self.assertEqual(response.get_json()["error_code"], "EMPTY_RESULT")

    def test_news_non_429_upstream_failure_remains_502(self) -> None:
        with patch.object(fetchers, "fetch_from_registry", side_effect=http_error(500)):
            response = self.client.get("/api/news?symbol=%5EVIX")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error_code"], "DATA_SOURCE_ERROR")

    def test_site_data_refresh_success_contract(self) -> None:
        payload = {"snapshotDate": "2026-09-08", "sectors": [], "news": []}
        with patch.object(routes_twse, "build_live_sector_site_data", return_value=payload):
            response = self.client.get("/api/twse/site-data?refresh=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), payload)

    def test_site_data_refresh_cooldown_uses_cached_snapshot(self) -> None:
        payload = {"snapshotDate": "2026-09-08", "sectors": [], "news": []}
        with cache.cache_lock:
            cache.cache_data["site_data"] = payload
        with patch.object(routes_twse, "build_live_sector_site_data", side_effect=cache.ProviderCooldownError("cooldown")):
            response = self.client.get("/api/twse/site-data?refresh=1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), payload)

    def test_site_data_refresh_without_snapshot_remains_fail_closed(self) -> None:
        with patch.object(routes_twse, "build_live_sector_site_data", side_effect=cache.ProviderCooldownError("cooldown")):
            response = self.client.get("/api/twse/site-data?refresh=1")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.get_json()["error_code"], "LIVE_SITE_DATA_UNAVAILABLE")

    def test_etf_center_normal_success_contract(self) -> None:
        payload = {"category": "us-etf", "items": [], "summary": {}}
        with patch.object(routes_global_market, "build_us_etf_center_payload", return_value=payload):
            response = self.client.get("/api/us-market/etf-center")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["cached"])
        self.assertEqual(response.get_json()["category"], "us-etf")

    def test_etf_center_local_rate_limit_still_works(self) -> None:
        security.API_RATE_LIMIT_PER_WINDOW = 1
        with patch.object(routes_global_market, "build_us_etf_center_payload", return_value={"category": "us-etf"}):
            first = self.client.get("/api/us-market/etf-center", environ_base={"REMOTE_ADDR": "198.51.100.10"})
            second = self.client.get("/api/us-market/etf-center", environ_base={"REMOTE_ADDR": "198.51.100.10"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.get_json()["error_code"], "RATE_LIMITED")

    def test_proxy_clients_do_not_share_loopback_rate_limit_identity(self) -> None:
        security.API_RATE_LIMIT_PER_WINDOW = 1
        original_wsgi_app = app.app.wsgi_app
        app.app.wsgi_app = ProxyFix(original_wsgi_app, x_for=1, x_proto=1, x_host=1)
        try:
            with patch.object(routes_global_market, "build_us_etf_center_payload", return_value={"category": "us-etf"}):
                first = self.client.get(
                    "/api/us-market/etf-center",
                    environ_base={"REMOTE_ADDR": "127.0.0.1"},
                    headers={"X-Forwarded-For": "198.51.100.10"},
                )
                second = self.client.get(
                    "/api/us-market/etf-center",
                    environ_base={"REMOTE_ADDR": "127.0.0.1"},
                    headers={"X-Forwarded-For": "198.51.100.11"},
                )
        finally:
            app.app.wsgi_app = original_wsgi_app
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)

    def test_http_429_does_not_create_provider_cooldown(self) -> None:
        key = "host:query2.finance.yahoo.com"
        error = http_error(429)
        with self.assertRaises(HTTPError):
            cache.run_cache_single_flight("api-429", lambda: (_ for _ in ()).throw(error), provider_key=key)
        error.close()
        self.assertFalse(cache.provider_cooldown_active(key))

    def test_derivatives_asset_hub_uses_bounded_initial_payload(self) -> None:
        source = Path("js/page-global-market-assethub.js").read_text(encoding="utf-8")
        self.assertIn('`/api/${encodeURIComponent(category)}?limit=12`', source)
        bundle = Path("market-pulse-esm.min.js").read_text(encoding="utf-8")
        self.assertIn('`/api/${encodeURIComponent(category)}?limit=12`', bundle)

    def test_options_page_uses_bounded_initial_payload(self) -> None:
        source = Path("js/page-global-market-options.js").read_text(encoding="utf-8")
        self.assertIn('["precious-metals", "bonds", "futures"].includes(category)', source)
        self.assertIn('      : ["futures", "options"].includes(category)\n        ? 12', source)
        bundle = Path("market-pulse-esm.min.js").read_text(encoding="utf-8")
        self.assertIn('["precious-metals","bonds","futures"].includes(category)', bundle)


if __name__ == "__main__":
    unittest.main()
