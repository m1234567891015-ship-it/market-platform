from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import builders
import fetchers
from derivatives_store import DerivativesStore


TRADE_DATE = "2026-09-29"
OPTION_ROWS = [
    {
        "symbol": f"TXO-202610-{option_type}",
        "underlying": "TXO",
        "expiry": "202610",
        "expiryDate": "2026-10-21",
        "strike": 22000,
        "optionType": option_type,
        "last": 120,
        "settlement": 120,
        "volume": 100,
        "openInterest": 1000 if option_type == "call" else 1100,
        "bid": 115,
        "ask": 125,
        "impliedVolatility": 0.2,
        "source": "fixture",
    }
    for option_type in ("call", "put")
]


class P101DataQualityRemediationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="p1-01-quality-")
        self.addCleanup(self.temp_dir.cleanup)
        self.store = DerivativesStore(Path(self.temp_dir.name) / "ledger.sqlite3")
        self.store.initialize()
        self.previous_store = app.DERIVATIVES_STORE
        app.DERIVATIVES_STORE = self.store
        self.addCleanup(setattr, app, "DERIVATIVES_STORE", self.previous_store)
        self.client = app.app.test_client()

    @staticmethod
    def _taifex_payload():
        return builders.build_taifex_txo_option_payload(
            OPTION_ROWS, TRADE_DATE, "202610", "TXO", {"value": 22000, "date": TRADE_DATE}
        )

    @staticmethod
    def _yahoo_payload(trade_date: str | None = TRADE_DATE):
        return builders.build_yahoo_txo_option_payload(
            OPTION_ROWS, trade_date, "202610", {"value": 22000, "date": trade_date}, "TXO"
        )

    def test_yahoo_market_date_missing_stays_unknown_and_valid_date_is_preserved(self) -> None:
        lines = ["台指2610", "賣權 Put"]
        with patch.object(app, "extract_visible_text_lines", return_value=lines), \
                patch.object(app, "parse_yahoo_txo_option_table", return_value=OPTION_ROWS), \
                patch.object(app, "parse_yahoo_txo_underlying_snapshot", return_value={"value": 22000}), \
                patch.object(app, "fetch_taiwan_option_spot_snapshot", return_value={"value": 22000}):
            missing = app.parse_yahoo_txo_option_page("fixture", expiry="202610")

        self.assertIsNone(missing["tradeDate"])
        self.assertIsNone(missing["analysis"]["market_as_of"])
        self.assertIsNone(missing["analysis"]["source_updated_at"])
        self.assertEqual(missing["analysis"]["dataQualityDimensionStatus"]["freshness"], "UNKNOWN")
        self.assertNotIn("freshness", missing["analysis"]["dataQualityDimensions"])

        with patch.object(app, "extract_visible_text_lines", return_value=[
            "資料時間：2026/09/29 13:45", *lines,
        ]), patch.object(app, "parse_yahoo_txo_option_table", return_value=OPTION_ROWS), \
                patch.object(app, "parse_yahoo_txo_underlying_snapshot", return_value={"value": 22000}):
            valid = app.parse_yahoo_txo_option_page("fixture", expiry="202610")

        self.assertEqual(valid["tradeDate"], TRADE_DATE)
        self.assertEqual(valid["analysis"]["market_as_of"], TRADE_DATE)
        self.assertEqual(valid["analysis"]["source_updated_at"], TRADE_DATE)

    def test_primary_success_and_explicit_yahoo_have_non_fallback_quality(self) -> None:
        primary_payload = self._taifex_payload()
        with patch.object(fetchers, "fetch_taifex_txo_option_chain", return_value=primary_payload):
            primary = fetchers.fetch_taiwan_option_chain(source="auto")
        self.assertEqual(primary["analysis"]["dataQualityDimensions"]["fallbackSource"], 100)
        self.assertIn("TAIFEX_PRIMARY", primary["sourceProvenance"]["sourceRoles"])
        self.assertEqual(primary["analysis"]["sourceProvenance"], primary["sourceProvenance"])

        with patch.object(fetchers, "fetch_yahoo_txo_option_chain", return_value=self._yahoo_payload()):
            explicit = fetchers.fetch_taiwan_option_chain(source="yahoo")
        self.assertEqual(explicit["analysis"]["dataQualityDimensions"]["fallbackSource"], 100)
        self.assertEqual(explicit["sourceProvenance"]["sourceRoles"], ["YAHOO_EXPLICIT"])
        self.assertEqual(explicit["sourceProvenance"]["selectionMode"], "yahoo")

    def test_taifex_yahoo_supplement_provenance_keeps_existing_quality_mapping(self) -> None:
        original = self._taifex_payload()
        with patch.object(
            fetchers,
            "fetch_taifex_txo_option_chain",
            side_effect=lambda **kwargs: app.supplement_taifex_option_payload_with_yahoo_oi(original),
        ), \
                patch.object(app, "fetch_yahoo_txo_option_chain", return_value=self._yahoo_payload()):
            supplemented = fetchers.fetch_taiwan_option_chain(source="taifex")

        self.assertEqual(supplemented["source"]["mode"], "taifex")
        self.assertIsNone(supplemented.get("fallbackFrom"))
        self.assertEqual(supplemented["analysis"]["dataQualityDimensions"]["fallbackSource"], 50)
        self.assertEqual(
            supplemented["sourceProvenance"]["sourceRoles"],
            ["TAIFEX_PRIMARY", "YAHOO_SUPPLEMENT"],
        )
        self.assertEqual(supplemented["sourceProvenance"]["supplements"][0]["kind"], "spot")
        self.assertTrue(supplemented["sourceProvenance"]["supplements"][0]["fields"])
        self.assertEqual(
            supplemented["analysis"]["sourceProvenance"],
            supplemented["sourceProvenance"],
        )
        for key in ("marketScore", "riskScore", "strategySuggestion"):
            self.assertEqual(supplemented["analysis"][key], original["analysis"][key])

    def test_oi_supplement_provenance_lists_fields_that_were_filled(self) -> None:
        zero_oi_rows = [{**row, "openInterest": 0} for row in OPTION_ROWS]
        taifex_payload = builders.build_taifex_txo_option_payload(
            zero_oi_rows, TRADE_DATE, "202610", "TXO", {"value": 22000, "date": TRADE_DATE}
        )
        with patch.object(
            fetchers,
            "fetch_taifex_txo_option_chain",
            side_effect=lambda **kwargs: app.supplement_taifex_option_payload_with_yahoo_oi(taifex_payload),
        ), \
                patch.object(app, "fetch_yahoo_txo_option_chain", return_value=self._yahoo_payload()):
            supplemented = fetchers.fetch_taiwan_option_chain(source="taifex")

        self.assertEqual(
            supplemented["sourceProvenance"]["sourceRoles"],
            ["TAIFEX_PRIMARY", "YAHOO_SUPPLEMENT"],
        )
        supplement = next(
            item for item in supplemented["sourceProvenance"]["supplements"]
            if item["kind"] == "openInterest"
        )
        self.assertEqual(supplement["fields"], ["call.openInterest", "put.openInterest"])
        self.assertEqual(supplement["matchedExpiry"], "202610")
        self.assertEqual(supplemented["analysis"]["dataQualityDimensions"]["fallbackSource"], 50)

    def test_auto_fallback_and_unknown_role_are_not_collapsed(self) -> None:
        with patch.object(fetchers, "fetch_taifex_txo_option_chain", return_value={"error": "TAIFEX unavailable"}), \
                patch.object(fetchers, "fetch_yahoo_txo_option_chain", return_value=self._yahoo_payload()):
            fallback = fetchers.fetch_taiwan_option_chain(source="auto")
        self.assertEqual(fallback["fallbackFrom"], "taifex")
        self.assertEqual(fallback["analysis"]["dataQualityDimensions"]["fallbackSource"], 50)
        self.assertEqual(fallback["sourceProvenance"]["sourceRoles"], ["YAHOO_AUTO_FALLBACK"])
        self.assertEqual(fallback["sourceProvenance"]["fallbackFrom"], "taifex")

        unknown = app.apply_taiwan_option_source_quality(self._yahoo_payload(), "unrecognized")
        self.assertEqual(unknown["analysis"]["dataQualityDimensionStatus"]["fallbackSource"], "UNKNOWN")
        self.assertNotIn("fallbackSource", unknown["analysis"]["dataQualityDimensions"])
        self.assertEqual(unknown["sourceProvenance"]["sourceRoles"], ["UNKNOWN"])

    def test_stale_cache_failure_reaches_api_and_isolated_ledger(self) -> None:
        stale_payload = self._taifex_payload()
        stale_time = "2026-09-30T01:00:00+00:00"
        with patch.object(fetchers, "read_memory_cache", return_value=None), \
                patch.object(fetchers, "claim_taifex_options_chain_flight", return_value=(True, threading.Event())), \
                patch.object(fetchers, "fetch_form_text", side_effect=RuntimeError("fixture provider outage")), \
                patch.object(fetchers.LOGGER, "exception"), \
                patch.object(fetchers, "read_stale_memory_cache", return_value=(stale_payload, stale_time)), \
                patch.object(fetchers, "fetch_taiwan_option_spot_snapshot", return_value={"value": 22000}), \
                patch.object(app, "fetch_yahoo_txo_option_chain", return_value=self._yahoo_payload()), \
                patch.object(fetchers, "finish_taifex_options_chain_flight"), \
                patch.object(fetchers, "write_memory_cache"), \
                patch.object(fetchers, "save_disk_cache"):
            response = self.client.get("/api/ai-analysis?target=TXO&source=auto")

        self.assertEqual(response.status_code, 200)
        analysis = response.get_json()["data"]
        self.assertEqual(analysis["dataQualityStatus"], "FAILED")
        self.assertEqual(analysis["dataQualityDimensions"]["freshness"], 0)
        self.assertEqual(analysis["dataQualityDimensions"]["providerHealth"], 0)
        self.assertEqual(analysis["dataQualityDimensionStatus"]["fallbackSource"], "KNOWN")
        self.assertEqual(analysis["dataQualityDimensions"]["fallbackSource"], 50)
        self.assertEqual(analysis["market_as_of"], TRADE_DATE)
        self.assertEqual(analysis["source_updated_at"], TRADE_DATE)
        self.assertEqual(
            analysis["sourceProvenance"]["sourceRoles"],
            ["CACHE", "TAIFEX_PRIMARY", "YAHOO_SUPPLEMENT"],
        )

        saved = self.store.get_decision(analysis["decision_id"])
        self.assertEqual(saved["market_as_of"], TRADE_DATE)
        self.assertEqual(saved["source_metadata"]["source_updated_at"], TRADE_DATE)
        self.assertEqual(saved["source_metadata"]["data_quality_status"], analysis["dataQualityStatus"])
        self.assertEqual(saved["source_metadata"]["quality_coverage"], analysis["qualityCoverage"])
        self.assertEqual(saved["source_metadata"]["data_quality_dimensions"], analysis["dataQualityDimensions"])
        self.assertEqual(
            saved["source_metadata"]["data_quality_dimension_status"],
            analysis["dataQualityDimensionStatus"],
        )
        self.assertEqual(saved["source_metadata"]["source_provenance"], analysis["sourceProvenance"])
        self.assertEqual(
            saved["source_metadata"]["source_provenance"]["cache"],
            {"used": True, "stale": True, "staleAt": stale_time},
        )
        self.assertEqual(saved["source_metadata"]["data_quality_dimensions"]["fallbackSource"], 50)

    def test_quality_context_refresh_does_not_change_market_or_risk_outputs(self) -> None:
        original = self._yahoo_payload()
        explicit = app.apply_taiwan_option_source_quality(original, "EXPLICIT", provider_status="healthy")
        for key in ("marketScore", "riskScore", "strategySuggestion"):
            self.assertEqual(explicit["analysis"][key], original["analysis"][key])


if __name__ == "__main__":
    unittest.main()
