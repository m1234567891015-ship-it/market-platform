"""Offline guardrails for request-starvation remediation Slice A."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")

import app
from derivatives.analytics import build_basis_payload
import fetch_registry
import fetchers


class _Response:
    def __init__(self, payload: bytes = b"{}"):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class RequestStarvationSliceATests(unittest.TestCase):
    def test_registry_deadline_shrinks_single_call_timeout(self):
        name = "slice_a_deadline_test"
        fetch_registry.REGISTRY.pop(name, None)
        fetch_registry.register(fetch_registry.SourceSpec(name=name, url="https://example.invalid", timeout=30))
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=_Response()) as opener, \
                patch.object(fetch_registry.time, "monotonic", return_value=102.0):
            fetch_registry.fetch_from_registry(name, deadline=105.0)
        self.assertEqual(opener.call_args.args[1], 3.0)

    def test_expired_deadline_prevents_http_attempt(self):
        request = MagicMock()
        with patch.object(fetchers, "_urlopen_with_ssl_fallback") as opener:
            with self.assertRaises(TimeoutError):
                fetchers.fetch_json("https://example.invalid", timeout=30, deadline=fetch_registry.deadline_after(0))
        opener.assert_not_called()

    def test_twse_recent_date_scan_is_capped_at_three_attempts(self):
        with patch.object(fetchers, "fetch_json", side_effect=URLError("offline")) as fetch_json:
            with self.assertRaises(RuntimeError):
                fetchers.find_latest_dataset(lambda date: date, lookback_days=10, deadline=fetch_registry.deadline_after(60))
        self.assertEqual(fetch_json.call_count, 3)

    def test_twse_success_stops_scan_immediately(self):
        payload = {"stat": "OK", "data": [["row"]]}
        with patch.object(fetchers, "fetch_json", return_value=payload) as fetch_json:
            result = fetchers.find_latest_dataset(lambda date: date, lookback_days=10, deadline=fetch_registry.deadline_after(60))
        self.assertEqual(result[0], payload)
        self.assertEqual(fetch_json.call_count, 1)

    def test_twse_malformed_json_continues_to_previous_date(self):
        payload = {"stat": "OK", "data": [["row"]]}
        malformed = json.JSONDecodeError("invalid JSON", "<provider>", 0)
        with patch.object(fetchers, "fetch_json", side_effect=[malformed, payload]) as fetch_json:
            result = fetchers.find_latest_dataset(lambda date: date, lookback_days=10, deadline=fetch_registry.deadline_after(60))
        self.assertEqual(result[0], payload)
        self.assertEqual(fetch_json.call_count, 2)

    def test_twse_malformed_json_exhaustion_is_controlled(self):
        malformed = json.JSONDecodeError("invalid JSON", "<provider>", 0)
        with patch.object(fetchers, "fetch_json", side_effect=[malformed, malformed, malformed]) as fetch_json:
            with self.assertRaises(RuntimeError):
                fetchers.find_latest_dataset(lambda date: date, lookback_days=10, deadline=fetch_registry.deadline_after(60))
        self.assertEqual(fetch_json.call_count, fetchers.TWSE_MAX_DATE_ATTEMPTS)

    def test_twse_unexpected_exception_is_not_swallowed(self):
        with patch.object(fetchers, "fetch_json", side_effect=TypeError("internal bug")) as fetch_json:
            with self.assertRaises(TypeError):
                fetchers.find_latest_dataset(lambda date: date, lookback_days=10, deadline=fetch_registry.deadline_after(60))
        self.assertEqual(fetch_json.call_count, 1)

    def test_twse_institution_date_scan_is_also_capped(self):
        with patch.object(fetchers, "fetch_from_registry", side_effect=URLError("offline")) as fetch_source:
            payload, used_date = fetchers.fetch_stock_institutions_payload_near("20990105", lookback_days=10)
        self.assertEqual(payload, {})
        self.assertEqual(used_date, "20990105")
        self.assertEqual(fetch_source.call_count, fetchers.TWSE_MAX_DATE_ATTEMPTS)

    def test_taifex_option_chain_is_capped_at_three_weekday_attempts(self):
        with patch.object(fetchers, "fetch_form_text", side_effect=TimeoutError("offline")) as fetch_form, \
                patch.object(fetchers, "fetch_taiwan_option_spot_snapshot", return_value={"value": None}):
            result = fetchers.fetch_taifex_txo_option_chain(
                market_date="20990105",
                expiry="slice-a",
                underlying="TXO",
            )
        self.assertIn("error", result)
        self.assertEqual(fetch_form.call_count, fetchers.TAIFEX_OPTION_CHAIN_MAX_DATE_ATTEMPTS)

    def test_taifex_option_chain_stops_before_third_attempt_when_budget_exhausted(self):
        with patch.object(fetchers, "fetch_form_text", return_value=""), \
                patch.object(fetchers, "fetch_taiwan_option_spot_snapshot", return_value={"value": None}), \
                patch.object(fetchers, "remaining_budget", side_effect=[10.0, 10.0, 0.0]):
            result = fetchers.fetch_taifex_txo_option_chain(
                market_date="20990105",
                expiry="slice-a-budget",
                underlying="TXO",
            )
        self.assertIn("error", result)

    def test_yahoo_options_retry_is_at_most_one_retry(self):
        unauthorized = lambda: fetchers.HTTPError(
            "https://example.invalid", 401, "unauthorized", {}, None
        )
        opener = MagicMock()
        opener.open.side_effect = [unauthorized(), unauthorized()]
        with patch.object(fetchers, "get_yahoo_options_crumb", return_value="crumb"), \
                patch.object(fetchers, "_yahoo_options_opener", opener):
            with self.assertRaises(fetchers.HTTPError):
                fetchers.fetch_yahoo_options_payload("AAPL", deadline=fetch_registry.deadline_after(30))
        self.assertEqual(opener.open.call_count, fetchers.YAHOO_MAX_RETRY + 1)

    def test_unavailable_numeric_values_remain_null(self):
        payload = build_basis_payload({"symbol": "TX"}, {"value": None}, [])
        self.assertIsNone(payload["spotPrice"])
        self.assertIsNone(payload["basis"])
        self.assertIsNone(payload["basisPct"])

    def test_slice_a_static_caps_are_within_authorized_limits(self):
        self.assertLessEqual(fetchers.TWSE_MAX_DATE_ATTEMPTS, 3)
        self.assertLessEqual(fetchers.TAIFEX_OPTION_CHAIN_MAX_DATE_ATTEMPTS, 3)
        self.assertLessEqual(fetchers.YAHOO_MAX_RETRY, 1)
        self.assertLessEqual(fetchers.FUTURES_BACKEND_BUDGET_SECONDS, 25)
        self.assertLessEqual(fetchers.OPTIONS_BACKEND_BUDGET_SECONDS, 40)
        self.assertLessEqual(fetchers.OPTION_CHAIN_BACKEND_BUDGET_SECONDS, 30)
        self.assertLessEqual(fetchers.PCR_BACKEND_BUDGET_SECONDS, 20)
        self.assertLessEqual(fetchers.INSTITUTION_BACKEND_BUDGET_SECONDS, 10)
        self.assertLessEqual(fetchers.BASIS_BACKEND_BUDGET_SECONDS, 20)


if __name__ == "__main__":
    unittest.main()
