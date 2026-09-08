"""Focused offline tests for Institution request-lifecycle observability."""

from __future__ import annotations

import os
import re
import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")

import app
import builders
import routes_derivatives


class InstitutionObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.app.test_client()

    def _institution_request(
        self,
        *,
        rows: list[dict] | None = None,
        remaining: float = 0.0,
        live_payload: dict | None = None,
        store_exception: Exception | None = None,
        use_real_live_builder: bool = False,
    ):
        store = MagicMock()
        store.initialize.return_value = None
        if store_exception is not None:
            store.institutional_positions.side_effect = store_exception
        else:
            store.institutional_positions.return_value = rows or []
        original_store = app.DERIVATIVES_STORE
        app.DERIVATIVES_STORE = store
        try:
            patches = [
                patch.object(routes_derivatives, "deadline_after", return_value=100.0),
                patch.object(routes_derivatives, "remaining_budget", return_value=remaining),
            ]
            if not use_real_live_builder:
                patches.append(patch.object(routes_derivatives, "build_institution_payload_live", return_value=live_payload))
            with patches[0], patches[1], patches[2] if len(patches) == 3 else nullcontext():
                response = self.client.get("/api/institution?product=TX")
                response.close()
                return response
        finally:
            app.DERIVATIVES_STORE = original_store

    @staticmethod
    def _event_lines(records) -> list[str]:
        return [line for line in records.output if "event=institution." in line]

    @staticmethod
    def _event_names(lines: list[str]) -> list[str]:
        return [re.search(r"event=([^ ]+)", line).group(1) for line in lines]

    @staticmethod
    def _request_ids(lines: list[str]) -> set[str]:
        return {re.search(r"institution_request_id=([^ ]+)", line).group(1) for line in lines}

    def test_obs_01_and_obs_02_request_entry_and_shared_id(self) -> None:
        with self.assertLogs("market_pulse", level="INFO") as records:
            response = self._institution_request()
        self.assertEqual(response.status_code, 200)
        lines = self._event_lines(records)
        self.assertEqual(sum("event=institution.request.enter" in line for line in lines), 1)
        self.assertEqual(len(self._request_ids(lines)), 1)

    def test_obs_03_sqlite_success_begin_then_end(self) -> None:
        rows = [{"institution": "外資及陸資", "net_contracts": 1, "trade_date": "2026-09-08"}]
        with patch.object(routes_derivatives, "build_institution_payload_from_rows", return_value={"rows": rows}), \
                self.assertLogs("market_pulse", level="INFO") as records:
            self._institution_request(rows=rows)
        names = self._event_names(self._event_lines(records))
        self.assertLess(names.index("institution.sqlite.begin"), names.index("institution.sqlite.end"))
        self.assertNotIn("institution.sqlite.timeout", names)
        self.assertNotIn("institution.sqlite.error", names)

    def test_obs_04_sqlite_timeout_begin_then_timeout(self) -> None:
        with self.assertLogs("market_pulse", level="INFO") as records:
            self._institution_request(store_exception=TimeoutError("deadline exhausted"))
        names = self._event_names(self._event_lines(records))
        self.assertLess(names.index("institution.sqlite.begin"), names.index("institution.sqlite.timeout"))
        self.assertNotIn("institution.sqlite.end", names)

    def test_obs_05_live_fallback_timeout_is_distinguished(self) -> None:
        with patch.object(builders, "fetch_taifex_institution_detail_rows", side_effect=TimeoutError("offline")), \
                self.assertLogs("market_pulse", level="INFO") as records:
            self._institution_request(remaining=1.0, use_real_live_builder=True)
        names = self._event_names(self._event_lines(records))
        self.assertLess(names.index("institution.live_fallback.begin"), names.index("institution.live_fallback.timeout"))
        self.assertNotIn("institution.live_fallback.end", names)

    def test_obs_05_live_fallback_success_begin_then_end(self) -> None:
        with self.assertLogs("market_pulse", level="INFO") as records:
            response = self._institution_request(remaining=1.0, live_payload={"product": "TX"})
        self.assertEqual(response.status_code, 200)
        names = self._event_names(self._event_lines(records))
        self.assertLess(names.index("institution.live_fallback.begin"), names.index("institution.live_fallback.end"))
        self.assertNotIn("institution.live_fallback.timeout", names)

    def test_obs_06_pending_deadline_exhausted_begin_end(self) -> None:
        with self.assertLogs("market_pulse", level="INFO") as records:
            self._institution_request(remaining=0.0)
        names = self._event_names(self._event_lines(records))
        self.assertLess(names.index("institution.pending.begin"), names.index("institution.pending.end"))
        self.assertIn("reason=deadline_exhausted", " ".join(self._event_lines(records)))

    def test_obs_07_to_obs_10_response_and_contract_unchanged(self) -> None:
        with self.assertLogs("market_pulse", level="INFO") as records:
            response = self._institution_request()
        names = self._event_names(self._event_lines(records))
        self.assertIn("institution.route.return", names)
        self.assertIn("institution.after_request", names)
        self.assertIn("institution.response.close", names)
        self.assertIn("institution.response.build.begin", names)
        self.assertIn("institution.response.build.end", names)
        body = response.get_json()
        self.assertEqual(set(body["data"]), {"product", "tradeDate", "rows", "summary", "source", "message"})
        self.assertNotIn("institution_request_id", body)
        self.assertNotIn("X-Institution-Request-Id", response.headers)
        self.assertNotIn("institution-request-id", {key.lower() for key in response.headers.keys()})

    def test_obs_11_option_chain_has_no_institution_events(self) -> None:
        option_payload = {"underlying": "TXO", "selectedExpiry": None, "chain": []}
        with patch.object(routes_derivatives, "deadline_after", side_effect=lambda seconds: seconds), \
                patch.object(routes_derivatives, "fetch_txo_option_chain", return_value={**option_payload, "error": "offline"}), \
                patch.object(routes_derivatives, "build_derivatives_unavailable_option_chain", return_value=option_payload), \
                patch.object(app.LOGGER, "info") as info:
            response = self.client.get("/api/options/chain?underlying=TXO&source=auto")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any("event=institution." in str(call) for call in info.call_args_list))

    def test_obs_12_request_context_does_not_leak(self) -> None:
        with self.assertLogs("market_pulse", level="INFO") as records:
            self._institution_request()
            self.client.get("/api/health")
        lines = self._event_lines(records)
        self.assertEqual(len(self._request_ids(lines)), 1)
        self.assertEqual(sum("event=institution.request.enter" in line for line in lines), 1)

if __name__ == "__main__":
    unittest.main()
