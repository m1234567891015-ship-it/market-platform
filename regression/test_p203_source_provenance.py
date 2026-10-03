"""P2-03 future-record provenance normalization and API/Ledger round trip."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")

import app
import routes_derivatives
from builders import (
    _build_taifex_futures_source_provenance,
    build_futures_ai_analysis,
    build_taifex_open_interest_item,
    normalize_futures_source_provenance,
)
from derivatives_store import DerivativesStore


TRADE_DATE = "2026-10-01"
TAIFEX_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
YAHOO_URL = "https://tw.stock.yahoo.com/quote/TX=F"


def source_item(provenance: dict | None = None) -> dict:
    item = {
        "symbol": "TX", "dataSymbol": "TX", "date": TRADE_DATE,
        "open": "100", "high": "102", "low": "99", "close": "101",
        "pct": "1.0%", "volume": "1000", "openInterest": "5000",
        "series": [{"date": TRADE_DATE, "open": 100, "high": 102, "low": 99,
                    "close": 101, "volume": 1000, "openInterest": 5000}],
    }
    if provenance is not None:
        item["sourceProvenance"] = provenance
    return item


class P203SourceProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="p203-source-provenance-")
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "ledger.sqlite3"
        self.store = DerivativesStore(self.path)
        self.flask_app = app.create_app({"TESTING": True}, derivatives_store=self.store)

    @staticmethod
    def snapshot() -> dict:
        return {
            "date": TRADE_DATE, "open": 100, "high": 103, "low": 99,
            "close": 102, "volume": 1000, "openInterest": 5000,
            "settlement": 101, "sourceLink": TAIFEX_URL,
        }

    @staticmethod
    def yahoo_quote() -> dict:
        return {
            "date": TRADE_DATE, "open": 100, "high": 104, "low": 99,
            "close": 103, "volume": 1200, "openInterest": 5200,
            "change": 2, "changePct": 2.0, "bid": 102, "ask": 104,
            "basis": 10, "referencePrice": 100, "quoteTime": "13:30",
            "yahooCode": "TX=F",
        }

    def build_item(self, snapshot, quote):
        with patch("builders.build_yahoo_taiwan_future_technical_profile", return_value={}), \
                patch("builders.fetch_taifex_latest_futures_market_snapshot", return_value=snapshot), \
                patch("builders.fetch_yahoo_taiwan_future_quote", return_value=quote):
            return build_taifex_open_interest_item({"symbol": "TX", "name": "TX Futures"})

    def test_taifex_primary_plus_yahoo_supplement_is_field_attributed(self) -> None:
        item = self.build_item(self.snapshot(), self.yahoo_quote())
        provenance = item["sourceProvenance"]
        self.assertEqual(provenance["sourceRoles"], ["TAIFEX_PRIMARY", "YAHOO_SUPPLEMENT"])
        self.assertIn("TAIFEX_PRIMARY", provenance["fields"].values())
        self.assertIn("YAHOO_SUPPLEMENT", provenance["fields"].values())
        self.assertEqual(provenance["supplements"][0]["provider"], "Yahoo")
        self.assertIn("close", provenance["supplements"][0]["fields"])

    def test_taifex_only_does_not_invent_yahoo_role(self) -> None:
        item = self.build_item(self.snapshot(), None)
        self.assertEqual(item["sourceProvenance"]["sourceRoles"], ["TAIFEX_PRIMARY"])
        self.assertEqual(item["sourceProvenance"]["supplements"], [])

    def test_yahoo_only_is_automatic_fallback_not_primary(self) -> None:
        item = self.build_item(None, self.yahoo_quote())
        provenance = item["sourceProvenance"]
        self.assertEqual(provenance["sourceRoles"], ["YAHOO_AUTO_FALLBACK"])
        self.assertEqual(provenance["fallbackFrom"], "TAIFEX")
        self.assertNotIn("TAIFEX_PRIMARY", provenance["sourceRoles"])

    def test_existing_explicit_and_unknown_roles_are_preserved_fail_closed(self) -> None:
        explicit = {"sourceRole": "YAHOO_EXPLICIT", "sourceRoles": ["YAHOO_EXPLICIT"], "selectionMode": "yahoo"}
        fallback = {"sourceRole": "YAHOO_AUTO_FALLBACK", "sourceRoles": ["YAHOO_AUTO_FALLBACK"], "selectionMode": "auto"}
        self.assertEqual(normalize_futures_source_provenance({"sourceProvenance": explicit}), explicit)
        self.assertEqual(normalize_futures_source_provenance({"sourceProvenance": fallback}), fallback)
        self.assertEqual(normalize_futures_source_provenance({})["sourceRoles"], ["UNKNOWN"])
        self.assertEqual(normalize_futures_source_provenance({"sourceProvenance": {"sourceRoles": ["TAIFEX"]}})["sourceRoles"], ["UNKNOWN"])

    def test_analysis_api_and_ledger_round_trip_keep_identical_provenance_and_old_row(self) -> None:
        self.store.initialize()
        old_snapshot = {"instrument": "TX", "market_as_of": "2026-09-30"}
        old_json = json.dumps(old_snapshot, sort_keys=True, separators=(",", ":"))
        self.store.record_decision({
            "decision_id": "p203-historical-null-provenance", "symbol": "TX", "instrument": "TX",
            "decision_time": "2026-10-01T09:00:00+08:00", "market_as_of": "2026-09-30",
            "strategy_id": "test", "strategy_version": "test-v1", "model_version": "test-v1",
            "input_snapshot_hash": hashlib.sha256(old_json.encode()).hexdigest(),
            "input_snapshot": old_snapshot,
            "decision_output": {"decisionState": "UNKNOWN", "decisionEligible": False,
                                "executionDirection": "UNAVAILABLE", "reasonCodes": ["UNKNOWN"]},
            "executionDirection": "UNAVAILABLE", "executionDirectionReason": "ANALYSIS_ONLY",
            "data_quality_status": "PARTIAL",
        })
        provenance = self.build_item(self.snapshot(), self.yahoo_quote())["sourceProvenance"]
        item = source_item(provenance)
        with patch.object(routes_derivatives, "build_global_market_item", return_value=item):
            response = self.flask_app.test_client().get("/api/ai-analysis?target=TX")
        self.assertEqual(response.status_code, 200)
        analysis = response.get_json()["data"]
        self.assertEqual(analysis["sourceProvenance"], provenance)
        saved = self.store.get_decision(analysis["decision_id"])
        self.assertEqual(saved["source_metadata"]["source_provenance"], provenance)
        ledger_response = self.flask_app.test_client().get(f"/api/decision-ledger/{analysis['decision_id']}")
        self.assertEqual(ledger_response.get_json()["data"]["decision"]["sourceProvenance"], provenance)
        historical = self.store.get_decision("p203-historical-null-provenance")
        self.assertIsNone(historical["source_metadata"].get("source_provenance"))

    def test_provenance_does_not_change_scores_strategy_or_probability_gate(self) -> None:
        provenance = _build_taifex_futures_source_provenance(
            self.snapshot(), self.yahoo_quote(), use_yahoo_quote=True, open_interest_source="Yahoo"
        )
        with_provenance = build_futures_ai_analysis(source_item(provenance))
        without_provenance = build_futures_ai_analysis(source_item())
        for field in ("decisionState", "decisionEligible", "marketScore", "riskScore",
                      "scenarioWeights", "strategySuggestion", "probabilityForecast"):
            self.assertEqual(with_provenance.get(field), without_provenance.get(field))
        self.assertEqual(with_provenance["sourceProvenance"], provenance)


if __name__ == "__main__":
    unittest.main()
