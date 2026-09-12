import copy
import os
import tempfile
import unittest
from unittest.mock import patch


class TpexWarmingResilienceTests(unittest.TestCase):
    def test_p2_cooldown_site_data_marks_response_only_and_preserves_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "MARKET_PULSE_CACHE_FILE": os.path.join(temp_dir, "cache.json"),
                "DERIVATIVES_DB_PATH": os.path.join(temp_dir, "derivatives.sqlite3"),
                "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            },
            clear=False,
        ):
            import app
            import routes_twse
            from cache import ProviderCooldownError, cache_lock

            snapshot = {
                "snapshotDate": "2026-09-11",
                "cachedAt": "2026-09-11 08:00:00",
                "source": "TWSE fixture",
                "stocks": [{"code": "2330", "close": 1000}],
            }
            with cache_lock:
                previous = copy.deepcopy(app.cache_data.get("site_data"))
                app.cache_data["site_data"] = copy.deepcopy(snapshot)
            try:
                with patch.object(
                    routes_twse,
                    "build_live_sector_site_data",
                    side_effect=ProviderCooldownError("provider cooldown"),
                ):
                    response = app.app.test_client().get("/api/twse/site-data?refresh=1")
                self.assertEqual(response.status_code, 200)
                payload = response.get_json()
                self.assertTrue(payload["cached"])
                self.assertEqual(payload["cachedAt"], snapshot["cachedAt"])
                self.assertEqual(payload["source"], snapshot["source"])
                self.assertEqual(payload["stocks"], snapshot["stocks"])
                self.assertNotIn("cached", snapshot)
                with cache_lock:
                    self.assertEqual(app.cache_data["site_data"], snapshot)
            finally:
                with cache_lock:
                    if previous is None:
                        app.cache_data.pop("site_data", None)
                    else:
                        app.cache_data["site_data"] = previous

    def test_p2_normal_site_data_response_remains_fresh_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "MARKET_PULSE_CACHE_FILE": os.path.join(temp_dir, "cache.json"),
                "DERIVATIVES_DB_PATH": os.path.join(temp_dir, "derivatives.sqlite3"),
                "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            },
            clear=False,
        ):
            import app
            import routes_twse

            fresh_payload = {"snapshotDate": "2026-09-11", "cachedAt": "2026-09-11 08:00:00", "stocks": []}
            with patch.object(routes_twse, "build_live_sector_site_data", return_value=fresh_payload):
                response = app.app.test_client().get("/api/twse/site-data?refresh=1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), fresh_payload)

    def _prepare_health_state(self, app):
        app.cache_data["site_data"] = {"cachedAt": "2026-09-05 09:00:00"}
        app.cache_data["cached_at"] = "2026-09-05 09:00:00"
        app.cache_data["last_error"] = None
        app.cache_data["provider_status"] = {
            "tpex": {"status": "never_loaded", "lastSuccessAt": None, "lastAttemptAt": None, "lastError": None},
            "twse": {"status": "never_loaded", "lastSuccessAt": None, "lastAttemptAt": None, "lastError": None},
        }

    def test_tpex_empty_refresh_is_not_available(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "MARKET_PULSE_CACHE_FILE": os.path.join(temp_dir, "cache.json"),
                "DERIVATIVES_DB_PATH": os.path.join(temp_dir, "derivatives.sqlite3"),
                "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            },
            clear=False,
        ):
            import app
            import cache
            import fetchers

            self._prepare_health_state(app)
            with patch.object(fetchers, "fetch_from_registry", return_value=[]), patch.object(cache, "refresh_cache"):
                cache._run_background_refresh_tasks()
            payload = app.app.test_client().get("/api/health").get_json()
            self.assertEqual(payload["providers"]["tpex"]["status"], "parse_error")
            self.assertEqual(payload["readiness"], "partial")

    def test_tpex_invalid_shape_refresh_is_not_available(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "MARKET_PULSE_CACHE_FILE": os.path.join(temp_dir, "cache.json"),
                "DERIVATIVES_DB_PATH": os.path.join(temp_dir, "derivatives.sqlite3"),
                "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            },
            clear=False,
        ):
            import app
            import cache
            import fetchers

            self._prepare_health_state(app)
            with patch.object(fetchers, "fetch_from_registry", return_value={}), patch.object(cache, "refresh_cache"):
                cache._run_background_refresh_tasks()
            payload = app.app.test_client().get("/api/health").get_json()
            self.assertEqual(payload["providers"]["tpex"]["status"], "parse_error")
            self.assertEqual(payload["readiness"], "partial")

    def test_tpex_valid_refresh_can_be_available(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "MARKET_PULSE_CACHE_FILE": os.path.join(temp_dir, "cache.json"),
                "DERIVATIVES_DB_PATH": os.path.join(temp_dir, "derivatives.sqlite3"),
                "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            },
            clear=False,
        ):
            import app
            import cache
            import fetchers
            import parsers

            self._prepare_health_state(app)
            valid_row = {
                "SecuritiesCompanyCode": "6488",
                "CompanyName": "測試公司",
                "Close": "100",
                "Change": "1",
                "Open": "99",
                "High": "101",
                "Low": "98",
                "Date": "1150911",
            }
            with patch.object(fetchers, "fetch_from_registry", return_value=[valid_row]):
                quotes, quote_date = fetchers.fetch_tpex_mainboard_quotes()
                stocks = parsers.parse_tpex_quotes(quotes, {})
            self.assertEqual(quote_date, "20260911")
            self.assertTrue(stocks)
            with patch.object(app, "refresh_tpex_cache", return_value=True), patch.object(cache, "refresh_cache"):
                cache._run_background_refresh_tasks()
            payload = app.app.test_client().get("/api/health").get_json()
            self.assertEqual(payload["providers"]["tpex"]["status"], "available")
            self.assertEqual(payload["readiness"], "ready")

    def test_tpex_zero_usable_rows_are_not_available(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "MARKET_PULSE_CACHE_FILE": os.path.join(temp_dir, "cache.json"),
                "DERIVATIVES_DB_PATH": os.path.join(temp_dir, "derivatives.sqlite3"),
                "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            },
            clear=False,
        ):
            import app
            import cache
            import fetchers

            self._prepare_health_state(app)
            unusable_row = {"CompanyName": "無代號資料", "Close": "100"}
            with patch.object(fetchers, "fetch_from_registry", return_value=[unusable_row]), patch.object(cache, "refresh_cache"):
                cache._run_background_refresh_tasks()
            payload = app.app.test_client().get("/api/health").get_json()
            self.assertEqual(payload["providers"]["tpex"]["status"], "parse_error")
            self.assertEqual(payload["readiness"], "partial")

    def test_tpex_timeout_isolated_and_health_is_partial(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "MARKET_PULSE_CACHE_FILE": os.path.join(temp_dir, "cache.json"),
                "DERIVATIVES_DB_PATH": os.path.join(temp_dir, "derivatives.sqlite3"),
                "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            },
            clear=False,
        ):
            import app
            import cache

            app.cache_data["site_data"] = {"cachedAt": "2026-09-05 09:00:00"}
            app.cache_data["cached_at"] = "2026-09-05 09:00:00"
            app.cache_data["last_error"] = None
            app.cache_data["provider_status"] = {
                "tpex": {"status": "never_loaded", "lastSuccessAt": None, "lastAttemptAt": None, "lastError": None},
                "twse": {"status": "never_loaded", "lastSuccessAt": None, "lastAttemptAt": None, "lastError": None},
            }
            with patch.object(app, "refresh_tpex_cache", side_effect=TimeoutError("TPEx timeout")), patch.object(cache, "refresh_cache"):
                cache._run_background_refresh_tasks()
            response = app.app.test_client().get("/api/health")
            payload = response.get_json()
            self.assertEqual(payload["status"], "partial")
            self.assertEqual(payload["readiness"], "partial")
            self.assertEqual(payload["providers"]["tpex"]["status"], "timeout")
            self.assertEqual(payload["providers"]["twse"]["status"], "available")

    def test_tpex_failure_does_not_run_unbounded_retry(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(
            os.environ,
            {
                "MARKET_PULSE_CACHE_FILE": os.path.join(temp_dir, "cache.json"),
                "DERIVATIVES_DB_PATH": os.path.join(temp_dir, "derivatives.sqlite3"),
                "MARKET_PULSE_DISABLE_BACKGROUND": "1",
            },
            clear=False,
        ):
            import app
            import cache

            app.cache_data["site_data"] = {"cachedAt": "2026-09-05 09:00:00"}
            app.cache_data["provider_status"]["tpex"]["status"] = "never_loaded"
            with patch.object(app, "refresh_tpex_cache", side_effect=TimeoutError("TPEx timeout")) as tpex_refresh, patch.object(cache, "refresh_cache"):
                cache._run_background_refresh_tasks()
            self.assertEqual(tpex_refresh.call_count, 1)


if __name__ == "__main__":
    unittest.main()
