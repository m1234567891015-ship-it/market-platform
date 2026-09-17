"""Deterministic offline tests for the R1-03 observability contract."""

from __future__ import annotations

import os
import json
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")

import observability as obs


class ObservabilityContractTests(unittest.TestCase):
    def setUp(self) -> None:
        obs.reset_observability()

    def snapshot(self, now: float = 10_000.0) -> dict:
        return obs.get_observability_snapshot(now=now)

    def test_api_request_count_and_percentiles(self) -> None:
        for index in range(20):
            obs.record_api_request("/api/twse/stock/<code>", "GET", 200, 100 + index, timestamp=10_000 + index)
        metrics = self.snapshot()["api"]
        self.assertEqual(metrics["request_count"], 20)
        self.assertEqual(metrics["latency_ms"]["p50"], 109.5)
        self.assertEqual(metrics["latency_ms"]["p95"], 118.05)
        self.assertEqual(metrics["by_route"].keys(), {"/api/twse/stock/<code>"})

    def test_api_status_class_and_5xx_rate(self) -> None:
        for index in range(19):
            obs.record_api_request("/api/health", "GET", 200, 20, timestamp=10_000 + index)
        obs.record_api_request("/api/health?request_id=secret", "GET", 503, 20, timestamp=10_020)
        snapshot = self.snapshot(10_020)
        self.assertEqual(snapshot["api.response.5xx.count"], 1)
        self.assertEqual(snapshot["api"]["five_xx_rate"], 0.05)
        self.assertEqual(snapshot["alerts"]["conditions"][0]["status"], "WARNING")
        self.assertNotIn("secret", str(snapshot))

    def test_generic_api_instrumentation_records_query_free_method_and_status(self) -> None:
        import app

        client = app.app.test_client()
        response_2xx = client.get("/api/health?query=dummy-api-key")
        response_4xx = client.get("/api/does-not-exist?request_id=TEST_REQUEST_ID")
        self.assertEqual(response_2xx.status_code, 200)
        self.assertEqual(response_4xx.status_code, 404)
        samples = list(obs.STATE.api_samples)
        self.assertEqual(samples[-2]["route"], "/api/health")
        self.assertEqual(samples[-2]["method"], "GET")
        self.assertEqual(samples[-2]["status_class"], "2xx")
        self.assertEqual(samples[-1]["status_class"], "4xx")
        self.assertEqual(self.snapshot()["api.response.5xx.count"], 0)
        self.assertNotIn("dummy-api-key", str(self.snapshot()))
        self.assertNotIn("TEST_REQUEST_ID", str(self.snapshot()))

    def test_api_route_exposes_bounded_error_class(self) -> None:
        obs.record_api_request("/api/orders", "POST", 429, 40, error_class="rate_limited", timestamp=10_000)
        route = self.snapshot()["api"]["by_route"]["/api/orders"]
        self.assertEqual(route["status_classes"], {"4xx": 1})
        self.assertEqual(route["error_classes"], {"rate_limited": 1})

    def test_empty_and_single_latency_samples_are_deterministic(self) -> None:
        self.assertIsNone(self.snapshot()["api"]["latency_ms"]["p99"])
        obs.record_api_request("/api/health", "GET", 200, 123.456, timestamp=10_000)
        self.assertEqual(self.snapshot()["api"]["latency_ms"]["p99"], 123.456)

    def test_5xx_alert_requires_minimum_sample(self) -> None:
        for index in range(10):
            obs.record_api_request("/api/health", "GET", 500, 20, timestamp=10_000 + index)
        self.assertEqual(self.snapshot(10_010)["alerts"]["conditions"][0]["status"], "NORMAL")

    def test_5xx_rate_below_two_percent_is_normal_at_minimum_sample(self) -> None:
        for index in range(20):
            obs.record_api_request("/api/health", "GET", 200, 20, timestamp=10_000 + index)
        alerts = self.snapshot(10_020)["alerts"]
        self.assertEqual(alerts["conditions"][0]["status"], "NORMAL")
        self.assertEqual(alerts["status"], "NORMAL")

    def test_latency_warning_requires_twenty_requests(self) -> None:
        for index in range(10):
            obs.record_api_request("/api/slow", "GET", 200, 6_001, timestamp=10_000 + index)
        alerts = self.snapshot(10_010)["alerts"]
        latency = next(item for item in alerts["conditions"] if item["name"] == "api_latency")
        self.assertEqual(latency["status"], "NORMAL")

    def test_latency_at_five_seconds_is_normal_with_required_sample(self) -> None:
        for index in range(20):
            obs.record_api_request("/api/slow", "GET", 200, 5_000, timestamp=10_000 + index)
        self.assertEqual(self.snapshot(10_020)["alerts"]["status"], "NORMAL")

    def test_latency_warning_and_critical_thresholds(self) -> None:
        for index in range(20):
            obs.record_api_request("/api/slow", "GET", 200, 6_000, timestamp=10_000 + index)
        self.assertEqual(self.snapshot(10_020)["alerts"]["status"], "WARNING")
        obs.reset_observability()
        for index in range(10):
            obs.record_api_request("/api/slow", "GET", 200, 10_001, timestamp=10_000 + index)
        self.assertEqual(self.snapshot(10_010)["alerts"]["status"], "CRITICAL")

    def test_provider_attempt_success_and_failure_state(self) -> None:
        obs.record_provider_attempt("https://api.example.invalid", timestamp=10_000)
        obs.record_provider_failure("api.example.invalid", error=TimeoutError("timeout"), timestamp=10_001)
        obs.record_provider_attempt("api.example.invalid", timestamp=10_002)
        obs.record_provider_success("api.example.invalid", timestamp=10_003)
        provider = self.snapshot(10_003)["providers"]["other"]
        self.assertEqual(provider["attempt_count"], 2)
        self.assertEqual(provider["success_count"], 1)
        self.assertEqual(provider["failure_count"], 1)
        self.assertEqual(provider["consecutive_failures"], 0)
        self.assertEqual(provider["current_state"], "available")

    def test_provider_failure_class_normalization(self) -> None:
        cases = {
            429: "rate_limited",
            503: "http_error",
        }
        for index, (status, expected) in enumerate(cases.items()):
            self.assertEqual(obs.normalize_failure_class(http_status=status), expected)
            obs.record_provider_attempt("taifex", timestamp=10_000 + index)
            obs.record_provider_failure("taifex", http_status=status, timestamp=10_000 + index)
        obs.record_provider_attempt("taifex", timestamp=10_010)
        obs.record_provider_failure("taifex", error=ValueError("parse_error"), timestamp=10_010)
        self.assertEqual(self.snapshot(10_010)["providers"]["taifex"]["last_failure_class"], "parse_error")

    def test_provider_validation_failure_is_visible(self) -> None:
        obs.record_provider_attempt("yahoo", timestamp=10_000)
        obs.record_provider_success("yahoo", timestamp=10_000)
        obs.record_provider_validation_failure("yahoo", "invalid_response", timestamp=10_001)
        provider = self.snapshot(10_001)["providers"]["yahoo"]
        self.assertEqual(provider["validation_failure_count"], 1)
        self.assertEqual(provider["last_failure_class"], "invalid_response")

    def test_empty_response_provider_failure_is_bounded_and_counted(self) -> None:
        import fetchers

        class EmptyResponse:
            headers = {"Content-Type": "application/json"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b""

        with patch.object(fetchers, "_urlopen_with_ssl_fallback", return_value=EmptyResponse()), \
                self.assertLogs("market_pulse", level="INFO") as records:
            with self.assertRaises(json.JSONDecodeError):
                fetchers.fetch_json("https://www.taifex.com.tw/api?api_key=secret-token")
        provider = self.snapshot()["providers"]["taifex"]
        self.assertEqual(provider["failure_count"], 1)
        self.assertEqual(provider["validation_failure_count"], 1)
        self.assertEqual(provider["last_failure_class"], "empty_response")
        self.assertNotIn("secret-token", str(self.snapshot()))
        self.assertNotIn("secret-token", "\n".join(records.output))

    def test_provider_warning_minimum_attempts_and_consecutive_failures(self) -> None:
        for index in range(5):
            obs.record_provider_attempt("yahoo", timestamp=10_000 + index)
            if index < 2:
                obs.record_provider_failure("yahoo", "network_error", timestamp=10_000 + index)
            else:
                obs.record_provider_success("yahoo", timestamp=10_000 + index)
        self.assertEqual(self.snapshot(10_010)["alerts"]["status"], "WARNING")

    def test_provider_consecutive_failure_boundary(self) -> None:
        for index in range(3):
            obs.record_provider_attempt("taifex", timestamp=10_000 + index)
            obs.record_provider_failure("taifex", "network_error", timestamp=10_000 + index)
            provider = self.snapshot(10_000 + index)["providers"]["taifex"]
            self.assertEqual(provider["consecutive_failures"], index + 1)
            condition = next(
                item for item in self.snapshot(10_000 + index)["alerts"]["conditions"]
                if item["name"] == "provider:taifex"
            )
            self.assertEqual(condition["status"], "WARNING" if index == 2 else "NORMAL")

    def test_provider_failure_rate_below_twenty_percent_is_normal(self) -> None:
        for index in range(6):
            obs.record_provider_attempt("yahoo", timestamp=10_000 + index)
            if index == 0:
                obs.record_provider_failure("yahoo", "network_error", timestamp=10_000 + index)
            else:
                obs.record_provider_success("yahoo", timestamp=10_000 + index)
        condition = next(
            item for item in self.snapshot(10_010)["alerts"]["conditions"]
            if item["name"] == "provider:yahoo"
        )
        self.assertEqual(condition["status"], "NORMAL")

    def test_unknown_exception_maps_to_bounded_other_without_raw_text_dimension(self) -> None:
        raw = "unknown-secret-exception-TEST_SECRET"
        obs.record_provider_attempt("tdcc", timestamp=10_000)
        obs.record_provider_failure("tdcc", error=RuntimeError(raw), timestamp=10_000)
        provider = self.snapshot()["providers"]["tdcc"]
        self.assertEqual(provider["last_failure_class"], "other_bounded_class")
        self.assertNotIn(raw, str(self.snapshot()))

    def test_timeout_and_network_failure_classes_are_bounded(self) -> None:
        self.assertEqual(obs.normalize_failure_class(TimeoutError("deadline")), "timeout")
        self.assertEqual(obs.normalize_failure_class(OSError("connection refused")), "network_error")

    def test_provider_critical_requires_continuous_unavailability(self) -> None:
        obs.record_provider_attempt("tdcc", timestamp=10_000)
        obs.record_provider_failure("tdcc", "network_error", timestamp=10_000)
        self.assertEqual(self.snapshot(10_000 + 15 * 60)["alerts"]["status"], "CRITICAL")

    def test_cache_fresh_stale_and_missing_states(self) -> None:
        obs.record_cache_state("stock_details", 9_900, 300, timestamp=10_000)
        obs.record_cache_state("global_markets", 9_000, 300, timestamp=10_000)
        obs.record_cache_state("site_data", None, 300, timestamp=10_000)
        caches = self.snapshot()["caches"]
        self.assertEqual(caches["stock_details"]["status"], "fresh")
        self.assertEqual(caches["global_markets"]["status"], "stale")
        self.assertEqual(caches["site_data"]["status"], "missing")

    def test_cache_age_alert_uses_configured_ttl(self) -> None:
        obs.record_cache_state("stock_details", 8_000, 300, timestamp=10_000)
        self.assertEqual(self.snapshot()["alerts"]["status"], "CRITICAL")

    def test_non_applicable_cache_suppresses_age_alert(self) -> None:
        obs.record_cache_state("stock_details", 8_000, 300, timestamp=10_000)
        alerts = obs.evaluate_alert_conditions(now=10_000, applicable_caches={"global_markets"})
        self.assertNotIn("cache:stock_details", {item["name"] for item in alerts["conditions"]})
        self.assertEqual(alerts["status"], "NORMAL")

    def test_missing_cache_does_not_alert_without_age(self) -> None:
        obs.record_cache_state("stock_details", None, 300, timestamp=10_000)
        self.assertEqual(self.snapshot()["alerts"]["status"], "NORMAL")

    def test_stale_fallback_count_and_warning(self) -> None:
        for index in range(5):
            obs.record_stale_fallback("taifex", "taifex_options_chain", "provider_unavailable", timestamp=10_000 + index)
        stale = self.snapshot(10_005)["stale_fallback"]
        self.assertEqual(stale["event_count_15m"], 5)
        self.assertEqual(self.snapshot(10_005)["alerts"]["status"], "WARNING")

    def test_stale_fallback_critical_requires_continuous_window(self) -> None:
        obs.record_stale_fallback("tdcc", "shareholder_distributions", "empty_response", timestamp=10_000)
        self.assertEqual(self.snapshot(10_000 + 30 * 60)["alerts"]["status"], "CRITICAL")

    def test_single_stale_fallback_within_age_limit_is_not_frequency_warning(self) -> None:
        obs.record_stale_fallback(
            "taifex",
            "taifex_options_chain",
            "provider_unavailable",
            stale_at=9_900,
            ttl_seconds=300,
            timestamp=10_000,
        )
        alerts = self.snapshot(10_000)["alerts"]
        stale = next(item for item in alerts["conditions"] if item["name"] == "stale_fallback")
        self.assertEqual(stale["status"], "NORMAL")

    def test_stale_age_warning_uses_event_ttl(self) -> None:
        obs.record_stale_fallback(
            "taifex",
            "taifex_options_chain",
            "provider_timeout",
            stale_at=9_000,
            ttl_seconds=300,
            timestamp=10_000,
        )
        condition = next(item for item in self.snapshot()["alerts"]["conditions"] if item["name"] == "stale_fallback")
        self.assertEqual(condition["status"], "WARNING")

    def test_readiness_vocabulary_and_sustained_alert(self) -> None:
        for state in ("warming", "degraded", "partial", "ready"):
            obs.record_readiness(state, timestamp=10_000)
            self.assertEqual(self.snapshot(10_000)["readiness"]["current"], state)
        obs.record_readiness("degraded", timestamp=10_001)
        self.assertEqual(self.snapshot(10_001 + 15 * 60)["alerts"]["status"], "CRITICAL")

    def test_readiness_alert_suppression_for_startup_or_deploy_window(self) -> None:
        obs.record_readiness("warming", timestamp=10_000)
        self.assertEqual(
            obs.evaluate_alert_conditions(now=10_000 + 15 * 60, cold_start=True)["status"],
            "NORMAL",
        )
        self.assertEqual(
            obs.evaluate_alert_conditions(now=10_000 + 15 * 60, authorized_window=True)["status"],
            "NORMAL",
        )

    def test_single_non_ready_observation_is_not_critical(self) -> None:
        obs.record_readiness("warming", timestamp=10_000)
        self.assertEqual(obs.evaluate_alert_conditions(now=10_000)["status"], "NORMAL")

    def test_non_ready_under_fifteen_minutes_is_not_critical(self) -> None:
        obs.record_readiness("partial", timestamp=10_000)
        self.assertEqual(obs.evaluate_alert_conditions(now=10_000 + 899)["status"], "NORMAL")

    def test_ready_readiness_is_normal(self) -> None:
        obs.record_readiness("ready", timestamp=10_000)
        self.assertEqual(obs.evaluate_alert_conditions(now=10_000)["status"], "NORMAL")

    def test_authorization_header_is_not_emitted_by_observability(self) -> None:
        import app

        client = app.app.test_client()
        with self.assertLogs("market_pulse", level="INFO") as records:
            response = client.get("/api/health", headers={"Authorization": "Bearer TEST_SECRET_SHOULD_NOT_APPEAR"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("TEST_SECRET_SHOULD_NOT_APPEAR", "\n".join(records.output))

    def test_provider_applicability_exclusion_suppresses_non_applicable_provider(self) -> None:
        obs.record_provider_attempt("cboe", timestamp=10_000)
        obs.record_provider_failure("cboe", "network_error", timestamp=10_000)
        alerts = obs.evaluate_alert_conditions(now=10_000 + 15 * 60, applicable_providers={"twse"})
        self.assertNotIn("provider:cboe", {item["name"] for item in alerts["conditions"]})

    def test_bounded_dimensions(self) -> None:
        self.assertEqual(obs.normalize_provider("https://unbounded.example/secret/2330"), "other")
        self.assertEqual(obs.normalize_route("/api/stock/2330?query=secret"), "/api/<unmatched>")

    def test_old_api_samples_expire_without_sleep_and_current_sample_remains(self) -> None:
        obs.record_api_request("/api/old", "GET", 200, 1, timestamp=10_000)
        current = 10_000 + obs.API_WINDOW_SECONDS + 1
        obs.record_api_request("/api/current", "GET", 200, 2, timestamp=current)
        self.assertEqual(len(obs.STATE.api_samples), 1)
        self.assertEqual(obs.STATE.api_samples[0]["route"], "/api/current")
        self.assertEqual(self.snapshot(current)["api"]["request_count"], 1)

    def test_health_endpoint_preserves_default_contract_and_opt_in_snapshot(self) -> None:
        import app

        client = app.app.test_client()
        default_response = client.get("/api/health")
        observed_response = client.get("/api/health?observability=1")
        default = default_response.get_json()
        observed = observed_response.get_json()
        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(observed_response.status_code, 200)
        for field in ("status", "readiness", "cachedAt", "lastError", "providers"):
            self.assertIn(field, default)
            self.assertEqual(default[field], observed[field])
        self.assertNotIn("observability", default)
        self.assertIn("observability", observed)
        self.assertIn(observed["readiness"], {"warming", "degraded", "partial", "ready"})
        self.assertEqual(default["readiness"], observed["readiness"])
        self.assertEqual(default["status"], "ok" if default["readiness"] == "ready" else default["readiness"])

    def test_cloudflare_proxy_failure_classes_are_bounded_and_recorded(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "cloudflare" / "src" / "worker.ts").read_text(encoding="utf-8")
        for code in (
            "UPSTREAM_NOT_CONFIGURED",
            "UPSTREAM_UNAVAILABLE",
            "UPSTREAM_INVALID_RESPONSE",
            "UPSTREAM_NON_2XX",
        ):
            self.assertIn(code, source)
        self.assertIn("getProxyObservabilitySnapshot", source)
        self.assertIn("recordProxyFailure", source)
        self.assertIn('"UPSTREAM_NOT_CONFIGURED"', source)
        self.assertIn('"UPSTREAM_UNAVAILABLE"', source)
        self.assertIn('"UPSTREAM_INVALID_RESPONSE"', source)
        self.assertIn('"UPSTREAM_NON_2XX"', source)
        self.assertIn('"API 上游回應為空"', source)
        self.assertIn('"API 上游回應格式錯誤"', source)
        self.assertIn('recordProxyFailure("UPSTREAM_NON_2XX")', source)


if __name__ == "__main__":
    unittest.main()
