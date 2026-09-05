import os
import tempfile
import unittest
from unittest.mock import patch


class TpexWarmingResilienceTests(unittest.TestCase):
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
