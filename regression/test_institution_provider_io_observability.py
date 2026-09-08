"""Offline tests for Institution provider-I/O lifecycle observability."""

from __future__ import annotations

import os
import re
import threading
import time
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from urllib.request import Request

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")

import app
import cache
import fetchers


TAIFEX_URL = "https://openapi.taifex.com.tw/v1/InstitutionTest"


class _FakeResponse:
    headers = {"Content-Type": "application/json"}

    def __init__(self, body: bytes = b"[]", read_error: Exception | None = None) -> None:
        self.body = body
        self.read_error = read_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        if self.read_error is not None:
            raise self.read_error
        return self.body


class InstitutionProviderIoObservabilityTests(unittest.TestCase):
    @contextmanager
    def _active_institution_context(self):
        with app.app.test_request_context("/api/institution?product=TX"):
            app.institution_observability_start("TX")
            app.institution_observability_set_deadline(time.monotonic() + 60.0)
            yield

    @staticmethod
    def _event_lines(records) -> list[str]:
        return [line for line in records.output if "event=institution.provider." in line]

    @staticmethod
    def _event_names(records) -> list[str]:
        return [re.search(r"event=([^ ]+)", line).group(1) for line in InstitutionProviderIoObservabilityTests._event_lines(records)]

    @staticmethod
    def _request_ids(records) -> set[str]:
        return {
            re.search(r"institution_request_id=([^ ]+)", line).group(1)
            for line in InstitutionProviderIoObservabilityTests._event_lines(records)
        }

    def _read_payload(self, response) -> tuple[bytes, str]:
        request = Request(TAIFEX_URL)
        with patch.object(cache, "check_provider_cooldown"), \
                patch.object(cache, "clear_provider_cooldown"), \
                patch.object(cache, "record_provider_failure"):
            return fetchers._read_provider_payload(request, 2.0, deadline=time.monotonic() + 60.0)

    def test_pio_01_provider_events_reuse_existing_request_id(self) -> None:
        with self._active_institution_context(), \
                patch.object(fetchers, "read_memory_cache", return_value=None), \
                patch.object(fetchers, "write_memory_cache"), \
                patch.object(fetchers, "_urlopen_with_ssl_fallback", return_value=_FakeResponse()), \
                self.assertLogs("market_pulse", level="INFO") as records:
            result = fetchers.fetch_taifex_openapi_list(TAIFEX_URL, 60, deadline=time.monotonic() + 60.0)
        self.assertEqual(result, [])
        self.assertEqual(len(self._request_ids(records)), 1)

    def test_pio_02_unrelated_fetch_emits_no_provider_events(self) -> None:
        with patch.object(app.LOGGER, "info") as info, \
                patch.object(fetchers, "read_memory_cache", return_value=None), \
                patch.object(fetchers, "write_memory_cache"), \
                patch.object(fetchers, "fetch_json", return_value=[]):
            fetchers.fetch_taifex_openapi_list(TAIFEX_URL, 60)
        self.assertFalse(any("event=institution.provider." in str(call) for call in info.call_args_list))

    def test_pio_03_cache_hit_has_no_single_flight_or_transport_events(self) -> None:
        with self._active_institution_context(), \
                patch.object(fetchers, "read_memory_cache", return_value=[{"cached": True}]), \
                patch.object(fetchers, "run_cache_single_flight") as flight, \
                self.assertLogs("market_pulse", level="INFO") as records:
            result = fetchers.fetch_taifex_openapi_list(TAIFEX_URL, 60, deadline=time.monotonic() + 60.0)
        self.assertEqual(result, [{"cached": True}])
        flight.assert_not_called()
        names = self._event_names(records)
        self.assertEqual(names, [
            "institution.provider.cache_lookup.begin",
            "institution.provider.cache_lookup.end",
        ])
        self.assertIn("cache_hit=true", " ".join(self._event_lines(records)))

    def test_pio_04_cache_miss_leader_claim_and_operation_order(self) -> None:
        with self._active_institution_context(), \
                patch.object(fetchers, "read_memory_cache", return_value=None), \
                patch.object(fetchers, "write_memory_cache"), \
                patch.object(fetchers, "_urlopen_with_ssl_fallback", return_value=_FakeResponse()), \
                self.assertLogs("market_pulse", level="INFO") as records:
            fetchers.fetch_taifex_openapi_list(TAIFEX_URL, 60, deadline=time.monotonic() + 60.0)
        names = self._event_names(records)
        self.assertLess(names.index("institution.provider.cache_lookup.end"), names.index("institution.provider.single_flight.claim.begin"))
        self.assertLess(names.index("institution.provider.single_flight.claim.begin"), names.index("institution.provider.single_flight.role"))
        self.assertIn("role=leader", " ".join(self._event_lines(records)))
        self.assertLess(names.index("institution.provider.single_flight.role"), names.index("institution.provider.operation.begin"))

    def test_pio_05_successful_open_and_read_have_terminal_events(self) -> None:
        with self._active_institution_context(), \
                patch.object(fetchers, "_urlopen_with_ssl_fallback", return_value=_FakeResponse(b"{}")), \
                self.assertLogs("market_pulse", level="INFO") as records:
            raw, content_type = self._read_payload(_FakeResponse(b"{}"))
        self.assertEqual((raw, content_type), (b"{}", "application/json"))
        names = self._event_names(records)
        for event in (
            "institution.provider.urlopen.begin",
            "institution.provider.urlopen.opened",
            "institution.provider.response_read.begin",
            "institution.provider.response_read.end",
            "institution.provider.operation.end",
        ):
            self.assertIn(event, names)
        self.assertNotIn("institution.provider.urlopen.exception", names)
        self.assertIn("bytes_read=2", " ".join(self._event_lines(records)))

    def test_pio_06_urlopen_timeout_logs_pre_open_exception_only(self) -> None:
        with self._active_institution_context(), \
                patch.object(fetchers, "_urlopen_with_ssl_fallback", side_effect=TimeoutError), \
                self.assertLogs("market_pulse", level="INFO") as records:
            with self.assertRaises(TimeoutError):
                self._read_payload(_FakeResponse())
        names = self._event_names(records)
        self.assertLess(names.index("institution.provider.urlopen.begin"), names.index("institution.provider.urlopen.exception"))
        self.assertNotIn("institution.provider.urlopen.opened", names)
        self.assertNotIn("institution.provider.response_read.begin", names)

    def test_pio_07_response_read_error_has_no_read_end(self) -> None:
        with self._active_institution_context(), \
                patch.object(fetchers, "_urlopen_with_ssl_fallback", return_value=_FakeResponse(read_error=TimeoutError())), \
                self.assertLogs("market_pulse", level="INFO") as records:
            with self.assertRaises(TimeoutError):
                self._read_payload(_FakeResponse())
        names = self._event_names(records)
        self.assertIn("institution.provider.urlopen.opened", names)
        self.assertIn("institution.provider.response_read.begin", names)
        self.assertIn("institution.provider.response_read.exception", names)
        self.assertNotIn("institution.provider.response_read.end", names)

    def test_pio_08_follower_wait_success_has_no_leader_operation(self) -> None:
        handle = cache.CacheFlightHandle(threading.Event())
        handle.result = "cached-result"
        handle.result_ready = True
        with self._active_institution_context(), \
                patch.object(cache, "claim_cache_flight", return_value=(False, handle)), \
                patch.object(cache, "wait_for_cache_flight", return_value=True), \
                self.assertLogs("market_pulse", level="INFO") as records:
            result = cache.run_cache_single_flight(
                "provider-flight-test",
                lambda: self.fail("follower must not run leader operation"),
                provider_key="host:openapi.taifex.com.tw",
            )
        self.assertEqual(result, "cached-result")
        names = self._event_names(records)
        self.assertIn("institution.provider.single_flight.wait.begin", names)
        self.assertIn("institution.provider.single_flight.wait.end", names)
        self.assertNotIn("institution.provider.operation.begin", names)
        self.assertIn("role=follower", " ".join(self._event_lines(records)))

    def test_pio_09_follower_wait_timeout_preserves_exception(self) -> None:
        with self._active_institution_context(), \
                patch.object(cache, "claim_cache_flight", return_value=(False, cache.CacheFlightHandle(threading.Event()))), \
                patch.object(cache, "wait_for_cache_flight", return_value=False), \
                self.assertLogs("market_pulse", level="INFO") as records:
            with self.assertRaises(cache.ProviderFlightUnavailable):
                cache.run_cache_single_flight(
                    "provider-flight-timeout-test",
                    lambda: "not-called",
                    provider_key="host:openapi.taifex.com.tw",
                )
        names = self._event_names(records)
        self.assertIn("institution.provider.single_flight.wait.begin", names)
        self.assertIn("institution.provider.single_flight.wait.timeout", names)
        self.assertNotIn("institution.provider.single_flight.wait.end", names)

    def test_pio_10_leader_exception_class_is_preserved(self) -> None:
        with self._active_institution_context(), \
                patch.object(cache, "check_provider_cooldown"), \
                patch.object(cache, "record_provider_failure"), \
                self.assertLogs("market_pulse", level="INFO") as records:
            with self.assertRaises(ValueError):
                cache.run_cache_single_flight(
                    "provider-operation-error-test",
                    lambda: (_ for _ in ()).throw(ValueError("offline")),
                    provider_key="host:openapi.taifex.com.tw",
                )
        self.assertIn("institution.provider.operation.error", self._event_names(records))
        self.assertIn("exception_class=ValueError", " ".join(self._event_lines(records)))

    def test_pio_11_and_pio_12_response_contract_and_context_isolation(self) -> None:
        store = MagicMock()
        store.initialize.return_value = None
        store.institutional_positions.return_value = []
        original_store = app.DERIVATIVES_STORE
        app.DERIVATIVES_STORE = store
        try:
            with self.assertLogs("market_pulse", level="INFO") as records:
                with patch.object(__import__("routes_derivatives"), "deadline_after", return_value=100.0), \
                        patch.object(__import__("routes_derivatives"), "remaining_budget", return_value=0.0):
                    response = app.app.test_client().get("/api/institution?product=TX")
                    response.close()
                with patch.object(fetchers, "read_memory_cache", return_value=None), \
                        patch.object(fetchers, "fetch_json", return_value=[]), \
                        patch.object(fetchers, "write_memory_cache"):
                    fetchers.fetch_taifex_openapi_list(TAIFEX_URL, 60)
        finally:
            app.DERIVATIVES_STORE = original_store
        body = response.get_json()
        self.assertNotIn("institution_request_id", body)
        self.assertNotIn("institution-request-id", {key.lower() for key in response.headers.keys()})
        provider_lines = self._event_lines(records)
        self.assertEqual(len(self._request_ids(records)), 0)
        self.assertEqual(provider_lines, [])


if __name__ == "__main__":
    unittest.main()
