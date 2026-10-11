from __future__ import annotations

import unittest
import hashlib
import json
import tempfile
from pathlib import Path

from derivatives.ai import build_unavailable_ai_analysis
from derivatives.analytics import enrich_futures_ai_decision, enrich_option_ai_decision
from derivatives_store import DerivativesStore
from builders import build_taifex_option_ai_analysis
from risk_taxonomy import risk_metadata


class RiskClassificationTests(unittest.TestCase):
    def test_active_consumers_declare_their_risk_type(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source_contracts = {
            "js/page-home.js": 'riskType: "MARKET_RISK"',
            "js/page-us.js": 'riskType: "MARKET_RISK"',
            "js/page-global-market-futures.js": 'riskType: "MARKET_RISK"',
            "js/page-global-market-options.js": 'riskType: "STRATEGY_RISK"',
            "js/page-global-market-derivatives.js": 'const riskType = "UNKNOWN"',
            "js/page-tw.js": 'riskType: "PORTFOLIO_RISK"',
            "js/render-shared.js": 'riskType: "PORTFOLIO_RISK"',
        }
        for relative_path, expected in source_contracts.items():
            with self.subTest(path=relative_path):
                self.assertIn(expected, (root / relative_path).read_text(encoding="utf-8"))

    def test_options_market_and_focus_scores_keep_distinct_types(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "js/page-global-market-options.js").read_text(encoding="utf-8")
        self.assertIn('riskType: "MARKET_RISK"', source)
        self.assertIn('riskType: "STRATEGY_RISK"', source)

    def test_supported_classes_are_explicit_and_not_score_aliases(self) -> None:
        from risk_taxonomy import RISK_TYPES

        self.assertEqual(
            RISK_TYPES,
            {"MARKET_RISK", "SIGNAL_RISK", "STRATEGY_RISK", "PORTFOLIO_RISK", "UNKNOWN"},
        )

    def test_same_numeric_score_keeps_distinct_risk_types(self) -> None:
        market = risk_metadata("MARKET_RISK", 75)
        portfolio = risk_metadata("PORTFOLIO_RISK", 75)
        self.assertEqual(market["riskClassification"]["score"], 75)
        self.assertEqual(portfolio["riskClassification"]["score"], 75)
        self.assertEqual(market["riskType"], "MARKET_RISK")
        self.assertEqual(portfolio["riskType"], "PORTFOLIO_RISK")
        self.assertNotEqual(market["riskType"], portfolio["riskType"])
        self.assertEqual(market["riskClassification"]["comparability"], "WITHIN_RISK_TYPE_ONLY")

    def test_invalid_type_fails_closed_to_unknown(self) -> None:
        result = risk_metadata("UNREVIEWED_RISK", 75)
        self.assertEqual(result["riskType"], "UNKNOWN")
        self.assertEqual(result["riskClassification"]["type"], "UNKNOWN")

    def test_derivatives_market_risk_retains_numeric_formula_outputs(self) -> None:
        options = enrich_option_ai_decision(
            {"target": "TXO", "bias": "區間震盪"}, {}, [], None,
        )
        futures = enrich_futures_ai_decision(
            {"target": "TX", "bias": "短線偏空"},
            {"symbol": "TX", "pct": -1.0},
            [],
        )
        self.assertEqual(options["riskScore"], 48)
        self.assertEqual(options["riskType"], "MARKET_RISK")
        self.assertEqual(options["riskClassification"]["score"], options["riskScore"])
        self.assertEqual(futures["riskScore"], 55)
        self.assertEqual(futures["riskType"], "MARKET_RISK")
        self.assertEqual(futures["riskClassification"]["score"], futures["riskScore"])

    def test_provider_unavailable_risk_is_signal_risk(self) -> None:
        result = build_unavailable_ai_analysis("TX", "provider unavailable")
        self.assertEqual(result["riskScore"], 60)
        self.assertEqual(result["riskType"], "SIGNAL_RISK")
        self.assertEqual(result["riskClassification"]["type"], "SIGNAL_RISK")

    def test_taifex_market_level_risk_is_classified_at_its_existing_score(self) -> None:
        result = build_taifex_option_ai_analysis(
            {"putCallRatio": 1.5}, [], {"strike": None}, None,
        )
        self.assertEqual(result["riskType"], "MARKET_RISK")
        self.assertEqual(result["riskLevel"], "高")
        self.assertEqual(result["riskClassification"]["score"], result["riskScore"])

    def test_computed_market_risk_survives_ledger_round_trip(self) -> None:
        summary = {"spotPrice": 22000}
        chain = []
        snapshot = {"summary": summary, "chain": chain, "spot": 22000}
        snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        analysis = enrich_option_ai_decision(
            {"target": "TXO", "bias": "區間震盪"}, summary, chain, {
                "symbol": "TXO",
                "market_as_of": "2026-09-30",
                "source_updated_at": "2026-09-30T05:00:00Z",
                "decision_time": "2026-10-01T00:00:00Z",
            },
        )
        decision = {
            **analysis,
            "decision_id": "p103-market-risk-round-trip",
            "symbol": "TXO",
            "instrument": "TXO",
            "strategy_id": analysis["strategy_version"],
            "model_version": analysis["model_version"],
            "strategy_version": analysis["strategy_version"],
            "input_snapshot": snapshot,
            "input_snapshot_hash": hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest(),
            "executionDirection": "UNAVAILABLE",
            "executionDirectionReason": "ANALYSIS_ONLY",
        }
        with tempfile.TemporaryDirectory(prefix="p103-risk-ledger-") as temp_dir:
            store = DerivativesStore(Path(temp_dir) / "ledger.sqlite3")
            store.initialize()
            self.assertTrue(store.record_decision(decision))
            restored = store.get_decision(decision["decision_id"])
        self.assertEqual(restored["decision_output"]["riskScore"], analysis["riskScore"])
        self.assertEqual(restored["decision_output"]["riskType"], "MARKET_RISK")
        self.assertEqual(restored["decision_output"]["riskClassification"]["type"], "MARKET_RISK")
        self.assertEqual(restored["decision_output"]["riskClassification"]["score"], analysis["riskScore"])


if __name__ == "__main__":
    unittest.main()
