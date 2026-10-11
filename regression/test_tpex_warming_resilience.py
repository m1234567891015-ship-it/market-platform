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
            self.assertEqual(payload["providers"]["tpex"]["consecutiveFailures"], 1)
            self.assertEqual(payload["providers"]["twse"]["consecutiveFailures"], 0)
            self.assertIsInstance(payload["providers"]["tpex"]["lastDurationMs"], int)
            self.assertGreaterEqual(payload["providers"]["tpex"]["lastDurationMs"], 0)
            self.assertIsNotNone(payload["providers"]["tpex"]["lastFailureAt"])
            self.assertIsInstance(payload["dataAgeSeconds"], int)
            self.assertGreaterEqual(payload["dataAgeSeconds"], 0)

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
            self.assertEqual(app.cache_data["provider_status"]["tpex"]["consecutiveFailures"], 1)

    def test_successful_refresh_resets_provider_failure_streak(self):
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

            app.cache_data["provider_status"]["tpex"].update(
                {"status": "timeout", "consecutiveFailures": 3}
            )
            with patch.object(app, "refresh_tpex_cache"), patch.object(cache, "refresh_cache"):
                cache._run_background_refresh_tasks()

            tpex_status = app.cache_data["provider_status"]["tpex"]
            self.assertEqual(tpex_status["status"], "available")
            self.assertEqual(tpex_status["consecutiveFailures"], 0)
            self.assertIsInstance(tpex_status["lastDurationMs"], int)
            self.assertGreaterEqual(tpex_status["lastDurationMs"], 0)

    def test_twse_refresh_failure_records_duration_and_failure_streak(self):
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

            with patch.object(app, "refresh_tpex_cache"), patch.object(
                cache, "refresh_cache", side_effect=TimeoutError("TWSE timeout")
            ):
                cache._run_background_refresh_tasks()

            twse_status = app.cache_data["provider_status"]["twse"]
            self.assertEqual(twse_status["status"], "timeout")
            self.assertEqual(twse_status["consecutiveFailures"], 1)
            self.assertIsInstance(twse_status["lastDurationMs"], int)
            self.assertGreaterEqual(twse_status["lastDurationMs"], 0)
            self.assertIsNotNone(twse_status["lastFailureAt"])

    def test_provider_backoff_skips_only_failed_source_and_resets_on_success(self):
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

            app.cache_data["provider_status"] = {
                "tpex": {"status": "never_loaded", "consecutiveFailures": 0},
                "twse": {"status": "never_loaded", "consecutiveFailures": 0},
            }
            with patch.object(app, "refresh_tpex_cache", side_effect=[TimeoutError(), TimeoutError(), None]) as tpex_refresh, patch.object(
                cache, "refresh_cache"
            ) as twse_refresh, patch.object(cache.random, "uniform", return_value=0), patch.object(
                cache.time, "time", return_value=1000
            ) as clock:
                cache._run_background_refresh_tasks()
                self.assertEqual(app.cache_data["provider_status"]["tpex"]["nextRetryAt"], 1060)
                clock.return_value = 1059
                cache._run_background_refresh_tasks()
                self.assertEqual(tpex_refresh.call_count, 1)
                self.assertEqual(twse_refresh.call_count, 2)
                clock.return_value = 1060
                cache._run_background_refresh_tasks()
                self.assertEqual(app.cache_data["provider_status"]["tpex"]["nextRetryAt"], 1180)
                clock.return_value = 1180
                cache._run_background_refresh_tasks()

            tpex_status = app.cache_data["provider_status"]["tpex"]
            self.assertEqual(tpex_refresh.call_count, 3)
            self.assertEqual(twse_refresh.call_count, 4)
            self.assertEqual(tpex_status["consecutiveFailures"], 0)
            self.assertIsNone(tpex_status["nextRetryAt"])
            self.assertEqual(tpex_status["status"], "available")

    def test_backoff_delay_is_bounded_with_jitter(self):
        import cache

        with patch.object(cache.random, "uniform", side_effect=lambda _start, end: end):
            self.assertEqual(cache._provider_retry_delay_seconds(1), 75)
            self.assertEqual(cache._provider_retry_delay_seconds(2), 150)
            self.assertEqual(cache._provider_retry_delay_seconds(100), 900)

    def test_health_reports_each_provider_refresh_age_without_mutating_cache(self):
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
            import routes_system

            app.cache_data["site_data"] = {"cachedAt": "2026-09-05 09:00:00"}
            app.cache_data["provider_status"] = {
                "tpex": {"status": "available", "lastSuccessAt": 821, "nextRetryAt": None},
                "twse": {"status": "timeout", "lastSuccessAt": 820, "nextRetryAt": 1100},
            }
            with patch.object(routes_system.time, "time", return_value=1000):
                payload = app.app.test_client().get("/api/health").get_json()

            self.assertEqual(payload["providers"]["tpex"]["refreshAgeSeconds"], 179)
            self.assertFalse(payload["providers"]["tpex"]["stale"])
            self.assertEqual(payload["providers"]["twse"]["refreshAgeSeconds"], 180)
            self.assertTrue(payload["providers"]["twse"]["stale"])
            self.assertEqual(payload["providers"]["twse"]["nextRetryAt"], 1100)
            self.assertNotIn("stale", app.cache_data["provider_status"]["twse"])


if __name__ == "__main__":
    unittest.main()
