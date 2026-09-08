"""Focused offline tests for the Institution deadline-escape fix."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
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
from derivatives.institution import build_pending_institution_payload
from derivatives_store import DerivativesStore


class InstitutionDeadlineEscapeTests(unittest.TestCase):
    def test_inst_esc_01_sqlite_progress_handler_interrupts_after_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DerivativesStore(Path(tmpdir) / "institution.sqlite3")
            clock = [100.0]
            with patch("derivatives_store.time.monotonic", side_effect=lambda: clock[0]):
                connection = store._connect(deadline=101.0, interruptible=True)
                try:
                    clock[0] = 102.0
                    with self.assertRaises(sqlite3.OperationalError) as raised:
                        connection.execute(
                            "WITH RECURSIVE counter(value) AS ("
                            "SELECT 1 UNION ALL SELECT value + 1 FROM counter WHERE value < 1000000"
                            ") SELECT sum(value) FROM counter"
                        ).fetchall()
                finally:
                    connection.set_progress_handler(None, 0)
                    connection.close()
            self.assertIn("interrupted", str(raised.exception).lower())

    def test_inst_esc_02_sqlite_read_cleanup_skips_commit_after_deadline(self) -> None:
        connection = MagicMock()
        clock = [100.0]
        with patch("derivatives_store.sqlite3.connect", return_value=connection), \
                patch("derivatives_store.time.monotonic", side_effect=lambda: clock[0]):
            store = DerivativesStore(Path(tempfile.gettempdir()) / "institution-deadline-test.sqlite3")
            with store._connection(deadline=101.0, read_only=True, interruptible=True):
                clock[0] = 102.0
        connection.commit.assert_not_called()
        connection.close.assert_called_once()
        connection.set_progress_handler.assert_any_call(None, 0)

    def test_inst_esc_03_contended_cleanup_lock_does_not_wait_after_deadline(self) -> None:
        lock = threading.Lock()
        lock.acquire()
        try:
            started = time.monotonic()
            self.assertFalse(cache._acquire_lock_with_deadline(lock, started - 1.0))
            self.assertLess(time.monotonic() - started, 0.5)
        finally:
            lock.release()

    def test_inst_esc_04_expired_deadline_starts_no_provider_or_fallback(self) -> None:
        store = MagicMock()
        store.institutional_positions.return_value = []
        original_store = app.DERIVATIVES_STORE
        app.DERIVATIVES_STORE = store
        try:
            with patch.object(routes_derivatives, "deadline_after", return_value=100.0), \
                    patch.object(routes_derivatives, "remaining_budget", return_value=0.0), \
                    patch.object(routes_derivatives, "build_institution_payload_live") as live:
                response = app.app.test_client().get("/api/institution?product=TX")
        finally:
            app.DERIVATIVES_STORE = original_store
        self.assertEqual(response.status_code, 200)
        live.assert_not_called()
        self.assertEqual(response.get_json()["data"]["summary"]["status"], "source_pending")

    def test_inst_esc_05_fail_closed_path_returns_without_fresh_wait(self) -> None:
        store = MagicMock()
        store.institutional_positions.side_effect = TimeoutError("deadline exhausted")
        original_store = app.DERIVATIVES_STORE
        app.DERIVATIVES_STORE = store
        try:
            with patch.object(routes_derivatives, "deadline_after", return_value=100.0), \
                    patch.object(routes_derivatives, "remaining_budget", return_value=0.0), \
                    patch.object(routes_derivatives, "build_institution_payload_live") as live:
                started = time.monotonic()
                response = app.app.test_client().get("/api/institution?product=TX")
        finally:
            app.DERIVATIVES_STORE = original_store
        self.assertEqual(response.status_code, 200)
        self.assertLess(time.monotonic() - started, 0.5)
        live.assert_not_called()

    def test_inst_esc_06_institution_provider_enables_deadline_cleanup_only(self) -> None:
        with patch.object(fetchers, "fetch_taifex_openapi_list", return_value=[]) as fetch_list:
            fetchers.fetch_taifex_institution_detail_rows("TX", deadline=100.0)
        self.assertTrue(fetch_list.call_args.kwargs["deadline_cleanup"])
        self.assertEqual(fetch_list.call_args.kwargs["deadline"], 100.0)

    def test_inst_esc_06b_optional_cache_write_uses_existing_request_deadline(self) -> None:
        with patch.object(fetchers, "fetch_json", return_value=[]), \
                patch.object(fetchers, "remaining_budget", return_value=1.0), \
                patch.object(fetchers, "write_memory_cache") as write_cache:
            fetchers.fetch_taifex_openapi_list(
                "https://example.invalid",
                60,
                deadline=100.0,
                deadline_cleanup=True,
            )
        self.assertEqual(write_cache.call_args.kwargs["deadline"], 100.0)

    def test_inst_esc_06_optional_cache_write_is_skipped_at_response_margin(self) -> None:
        with patch.object(fetchers, "fetch_json", return_value=[]), \
                patch.object(fetchers, "remaining_budget", return_value=0.0), \
                patch.object(fetchers, "write_memory_cache") as write_cache:
            fetchers.fetch_taifex_openapi_list(
                "https://example.invalid",
                60,
                deadline=100.0,
                deadline_cleanup=True,
            )
        write_cache.assert_not_called()

    def test_inst_esc_07_pending_api_schema_is_preserved(self) -> None:
        payload = build_pending_institution_payload("TX", "https://example.invalid")
        self.assertEqual(set(payload), {"product", "tradeDate", "rows", "summary", "source", "message"})
        self.assertEqual(set(payload["summary"]), {"netContracts", "bias", "status"})
        self.assertEqual(len(payload["rows"]), 4)

    def test_inst_esc_08_unavailable_institution_values_remain_null(self) -> None:
        payload = build_pending_institution_payload("TX", "https://example.invalid")
        self.assertIsNone(payload["summary"]["netContracts"])
        self.assertTrue(all(row["netContracts"] is None for row in payload["rows"]))

    def test_inst_esc_09_option_chain_deadline_path_is_unchanged(self) -> None:
        option_payload = {"underlying": "TXO", "selectedExpiry": None, "chain": []}
        with patch.object(routes_derivatives, "deadline_after", side_effect=lambda seconds: seconds) as make_deadline, \
                patch.object(routes_derivatives, "fetch_txo_option_chain", return_value={**option_payload, "error": "offline"}), \
                patch.object(routes_derivatives, "build_derivatives_unavailable_option_chain", return_value=option_payload):
            response = app.app.test_client().get("/api/options/chain?underlying=TXO&source=auto")
        self.assertEqual(response.status_code, 200)
        make_deadline.assert_called_once_with(29.75)


if __name__ == "__main__":
    unittest.main()
