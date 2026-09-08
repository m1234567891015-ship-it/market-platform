"""Offline full-request deadline tests for the two post-deploy target routes."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")

import app
import cache
import fetchers
import routes_derivatives
from derivatives_store import DerivativesStore


class FullRequestDeadlineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.app.test_client()
        with cache.cache_lock:
            cache.cache_data["taifex_options_chain"].clear()
            cache.cache_data["yahoo_tw_option_chain"].clear()

    def test_route_deadlines_start_at_entry_with_response_margin(self) -> None:
        option_payload = {"underlying": "TXO", "selectedExpiry": None, "chain": []}
        with patch.object(routes_derivatives, "deadline_after", side_effect=lambda seconds: seconds) as make_deadline, \
                patch.object(routes_derivatives, "fetch_txo_option_chain", return_value={**option_payload, "error": "offline"}), \
                patch.object(routes_derivatives, "build_derivatives_unavailable_option_chain", return_value=option_payload):
            response = self.client.get("/api/options/chain?underlying=TXO&source=auto")
        self.assertEqual(response.status_code, 200)
        make_deadline.assert_called_once_with(29.75)

        store = MagicMock()
        store.institutional_positions.return_value = []
        original_store = app.DERIVATIVES_STORE
        app.DERIVATIVES_STORE = store
        try:
            with patch.object(routes_derivatives, "deadline_after", side_effect=lambda seconds: seconds), \
                    patch.object(routes_derivatives, "build_institution_payload_live", return_value=None):
                response = self.client.get("/api/institution?product=TX")
        finally:
            app.DERIVATIVES_STORE = original_store
        self.assertEqual(response.status_code, 200)
        store.institutional_positions.assert_called_once_with("TX", deadline=9.75)

    def test_option_chain_provider_keeps_route_deadline_without_reset(self) -> None:
        with patch.object(fetchers, "fetch_taiwan_option_chain", return_value={"ok": True}) as fetch_chain, \
                patch.object(fetchers, "deadline_after", side_effect=AssertionError("deadline must not reset")):
            result = fetchers.fetch_txo_option_chain(underlying="TXO", deadline=123.0)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(fetch_chain.call_args.kwargs["deadline"], 123.0)

    def test_option_chain_follower_wait_uses_the_provider_deadline(self) -> None:
        handle = MagicMock()
        with patch.object(fetchers, "read_memory_cache", return_value=None), \
                patch.object(fetchers, "claim_taifex_options_chain_flight", return_value=(False, handle)), \
                patch.object(fetchers, "wait_for_cache_flight", return_value=False) as wait_for_flight, \
                patch.object(fetchers, "remaining_budget", return_value=4.0):
            result = fetchers.fetch_taifex_txo_option_chain(underlying="TXO", deadline=77.0)
        self.assertIn("error", result)
        self.assertEqual(wait_for_flight.call_args.kwargs["deadline"], 77.0)
        self.assertEqual(wait_for_flight.call_args.kwargs["max_wait"], 4.0)

    def test_option_chain_date_scan_keeps_three_attempt_cap(self) -> None:
        with patch.object(fetchers, "fetch_form_text", side_effect=TimeoutError("offline")) as fetch_form:
            result = fetchers.fetch_taifex_txo_option_chain(market_date="20990105", underlying="TXO")
        self.assertIn("error", result)
        self.assertEqual(fetch_form.call_count, 3)

    def test_institution_provider_receives_the_database_reduced_deadline(self) -> None:
        store = MagicMock()
        store.institutional_positions.return_value = []
        original_store = app.DERIVATIVES_STORE
        app.DERIVATIVES_STORE = store
        try:
            with patch.object(routes_derivatives, "deadline_after", side_effect=lambda seconds: seconds), \
                    patch.object(routes_derivatives, "remaining_budget", return_value=1.0), \
                    patch.object(routes_derivatives, "build_institution_payload_live", return_value={"summary": {"status": "source_pending"}}) as live:
                response = self.client.get("/api/institution?product=TX")
        finally:
            app.DERIVATIVES_STORE = original_store
        self.assertEqual(response.status_code, 200)
        self.assertEqual(live.call_args.kwargs["deadline"], 9.75)

    def test_cache_lock_wait_is_bounded_by_request_deadline(self) -> None:
        cache.cache_lock.acquire()
        try:
            started = time.monotonic()
            result = cache.read_memory_cache("taifex_options_chain", "deadline-test", 60, deadline=started + 0.02)
        finally:
            cache.cache_lock.release()
        self.assertIsNone(result)
        self.assertLess(time.monotonic() - started, 0.5)

    def test_yahoo_supplement_receives_only_remaining_budget(self) -> None:
        payload = {"underlying": "TXO", "selectedExpiry": "202609", "summary": {"totalOpenInterest": 0}, "chain": []}
        with patch.object(app, "remaining_budget", return_value=0.75), \
                patch.object(app, "fetch_yahoo_txo_option_chain", return_value={"error": "offline"}) as yahoo:
            result = app.supplement_taifex_option_payload_with_yahoo_oi(payload, deadline=50.0)
        self.assertEqual(result, payload)
        self.assertEqual(yahoo.call_args.kwargs["deadline"], 50.0)
        self.assertEqual(yahoo.call_args.kwargs["timeout"], 0.5)

    def test_yahoo_supplement_skips_at_response_margin(self) -> None:
        payload = {"underlying": "TXO", "selectedExpiry": "202609", "summary": {"totalOpenInterest": 0}, "chain": []}
        with patch.object(app, "remaining_budget", return_value=0.25), \
                patch.object(app, "fetch_yahoo_txo_option_chain") as yahoo:
            result = app.supplement_taifex_option_payload_with_yahoo_oi(payload, deadline=50.0)
        self.assertEqual(result, payload)
        yahoo.assert_not_called()

    def test_institution_sqlite_connect_timeout_is_request_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DerivativesStore(Path(tmpdir) / "institution.sqlite3")
            connection = MagicMock()
            connection.execute.return_value.fetchall.return_value = []
            with patch("derivatives_store.sqlite3.connect", return_value=connection) as sqlite_connect, \
                    patch("derivatives_store.time.monotonic", return_value=100.0):
                store.institutional_positions("TX", deadline=108.5)
            self.assertEqual(sqlite_connect.call_args.kwargs["timeout"], 8.5)

    def test_option_persistence_does_not_start_after_deadline_margin(self) -> None:
        store = MagicMock()
        original_store = app.DERIVATIVES_STORE
        app.DERIVATIVES_STORE = store
        try:
            with patch.object(routes_derivatives, "deadline_after", return_value=100.0), \
                    patch.object(routes_derivatives, "remaining_budget", return_value=0.25), \
                    patch.object(routes_derivatives, "fetch_txo_option_chain", return_value={"underlying": "TXO", "chain": []}):
                response = self.client.get("/api/options/chain?underlying=TXO&source=auto")
        finally:
            app.DERIVATIVES_STORE = original_store
        self.assertEqual(response.status_code, 200)
        store.record_option_chain.assert_not_called()


if __name__ == "__main__":
    unittest.main()
