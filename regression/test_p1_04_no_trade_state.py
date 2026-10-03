from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
from derivatives.ai import build_unavailable_ai_analysis
from derivatives.analytics import build_decision_contract, enrich_option_ai_decision
from derivatives.decision_state import resolve_decision_state
from derivatives_store import DerivativesStore


class NoTradeDecisionStateTests(unittest.TestCase):
    def contract(self, **overrides):
        arguments = {
            "symbol": "TXO",
            "input_snapshot": {"market": {"spot": 100}},
            "decision_output": {"bias": "neutral", "marketScore": 50, "riskScore": 95},
            "available_evidence": 1,
            "evidence_total": 3,
            "decision_context": {"provider_status": "healthy", "data_quality_score": 70},
            "execution_direction": "UNAVAILABLE",
            "execution_direction_reason": "ANALYSIS_ONLY",
        }
        arguments.update(overrides)
        return build_decision_contract(**arguments)

    def test_analysis_only_and_neutral_are_unknown_not_no_trade_or_hold(self):
        result = self.contract()
        self.assertEqual(result["decisionState"], "UNKNOWN")
        self.assertIsNone(result["decisionEligible"])
        self.assertEqual(result["reasonCodes"], ["UNKNOWN"])

    def test_data_quality_failed_blocks_with_machine_reason(self):
        result = self.contract(decision_context={"provider_status": "failed"})
        self.assertEqual(result["decisionState"], "NO_TRADE")
        self.assertFalse(result["decisionEligible"])
        self.assertEqual(result["reasonCodes"], ["DATA_QUALITY_INSUFFICIENT"])

    def test_existing_insufficient_decision_data_gate_blocks_without_new_threshold(self):
        result = self.contract(
            execution_direction_reason="INSUFFICIENT_DECISION_DATA",
            available_evidence=0,
            decision_context={"provider_status": "healthy"},
        )
        self.assertEqual(result["decisionState"], "NO_TRADE")
        self.assertEqual(result["reasonCodes"], ["INSUFFICIENT_EVIDENCE"])

    def test_partial_quality_and_calibration_unavailable_do_not_create_a_gate(self):
        result = self.contract(
            decision_context={"provider_status": "healthy", "freshness_score": 0},
            execution_direction_reason="ANALYSIS_ONLY",
        )
        self.assertEqual(result["dataQualityStatus"], "PARTIAL")
        self.assertEqual(result["decisionState"], "UNKNOWN")
        self.assertFalse(result["probabilityLabelAllowed"])

    def test_unrecognized_signal_conflict_or_high_risk_is_not_a_gate(self):
        result = self.contract(
            decision_output={"riskScore": 99},
            execution_direction_reason="SIGNAL_CONFLICT",
        )
        self.assertEqual(result["decisionState"], "UNKNOWN")

    def test_explicit_long_short_and_position_aware_hold_are_distinct(self):
        long = self.contract(execution_direction="LONG", execution_direction_reason="EXPLICIT_LONG_DECISION")
        short = self.contract(execution_direction="SHORT", execution_direction_reason="EXPLICIT_SHORT_DECISION")
        hold = self.contract(decision_context={"canonical_decision_state": "HOLD_EXISTING"})
        self.assertEqual((long["decisionState"], long["decisionEligible"]), ("LONG", True))
        self.assertEqual((short["decisionState"], short["decisionEligible"]), ("SHORT", True))
        self.assertEqual((hold["decisionState"], hold["decisionEligible"]), ("HOLD_EXISTING", False))
        self.assertNotEqual(hold["decisionState"], "NO_TRADE")

    def test_no_position_maps_to_abstention_with_unknown_reason(self):
        result = self.contract(execution_direction="NO_POSITION", execution_direction_reason="EXPLICIT_NO_POSITION_DECISION")
        self.assertEqual(result["decisionState"], "NO_TRADE")
        self.assertFalse(result["decisionEligible"])
        self.assertEqual(result["reasonCodes"], ["UNKNOWN"])

    def test_ai_provider_failure_cannot_recommend_entry(self):
        result = build_unavailable_ai_analysis("TXO", "provider unavailable")
        self.assertEqual(result["decisionState"], "NO_TRADE")
        self.assertIn("DATA_QUALITY_INSUFFICIENT", result["reasonCodes"])
        self.assertIn("暫不交易", result["strategySuggestion"])
        self.assertNotIn("立即買進", result["strategySuggestion"])

    def test_option_data_failure_keeps_numeric_scores_and_gates_suggestion(self):
        result = enrich_option_ai_decision(
            {"target": "TXO", "bias": "neutral", "supportLevel": 95, "resistanceLevel": 105},
            {"putCallRatio": 1.2, "volumePutCallRatio": 1.1, "maxPain": 100, "totalOpenInterest": 20},
            [{"strike": 100}],
            100,
            {"provider_status": "failed"},
        )
        self.assertEqual(result["decisionState"], "NO_TRADE")
        self.assertIn("暫不交易", result["strategySuggestion"])
        self.assertIn("strategyBias", result)
        self.assertEqual((result["marketScore"], result["riskScore"]), (56, 49))

    def test_unknown_explicit_reason_cannot_fabricate_no_trade(self):
        result = resolve_decision_state(
            execution_direction="UNAVAILABLE",
            execution_direction_reason="ANALYSIS_ONLY",
            data_quality_status="PARTIAL",
            explicit_state="NO_TRADE",
            explicit_reason_codes=["made-up-gate"],
        )
        self.assertEqual(result["decisionState"], "UNKNOWN")

    def test_ledger_round_trip_and_outcome_isolation(self):
        with tempfile.TemporaryDirectory(prefix="p104-ledger-") as temp_dir:
            db_path = Path(temp_dir) / "ledger.sqlite3"
            store = DerivativesStore(db_path)
            store.initialize()
            snapshot = {"market": {"spot": 100}}
            result = build_decision_contract(
                symbol="TXO",
                input_snapshot=snapshot,
                decision_output={"riskScore": 60, "strategySuggestion": "暫不交易"},
                available_evidence=0,
                evidence_total=3,
                decision_context={
                    "symbol": "TXO",
                    "market_as_of": "2026-09-01",
                    "decision_time": "2026-09-02T09:00:00+08:00",
                    "provider_status": "failed",
                },
                execution_direction="UNAVAILABLE",
                execution_direction_reason="INSUFFICIENT_DECISION_DATA",
            )
            decision = {
                **result,
                "decision_id": result["decision_id"],
                "symbol": "TXO",
                "instrument": "TXO",
                "strategy_id": "test-p104",
                "strategy_version": "test-p104-v1",
                "input_snapshot": snapshot,
                "decision_output": result["decision_output"],
                "reference_price": 100,
                "execution_cost_assumptions": {},
                "data_quality_status": result["dataQualityStatus"],
                "created_at": "2026-09-02T09:00:00+08:00",
            }
            self.assertTrue(store.record_decision(decision))
            saved = store.get_decision(result["decision_id"])
            self.assertEqual(saved["decisionState"], "NO_TRADE")
            self.assertFalse(saved["decisionEligible"])
            self.assertEqual(saved["reasonCodes"], ["DATA_QUALITY_INSUFFICIENT"])
            self.assertEqual(saved["decision_output"]["reasonCodes"], saved["reasonCodes"])
            outcome = store.evaluate_decision_outcome(
                result["decision_id"],
                "T+1",
                "2026-09-03T09:00:00+08:00",
                [{"date": "2026-09-03", "observed_at": "2026-09-03T09:00:00+08:00", "high": 110, "low": 90, "close": 105}],
            )
            self.assertEqual(outcome["status"], "NOT_APPLICABLE")
            self.assertIsNone(outcome.get("gross_return"))
            self.assertIsNone(outcome.get("net_return"))
            self.assertEqual(outcome["unavailable_reason"], "NO_TRADE_DECISION")

    def test_api_to_isolated_ledger_preserves_no_trade_contract(self):
        with tempfile.TemporaryDirectory(prefix="p104-api-ledger-") as temp_dir:
            db_path = Path(temp_dir) / "api-ledger.sqlite3"
            store = DerivativesStore(db_path)
            flask_app = app.create_app({"TESTING": True}, derivatives_store=store)
            with patch("routes_derivatives.fetch_txo_option_chain", return_value={"error": "provider unavailable"}):
                response = flask_app.test_client().get("/api/ai-analysis?target=TXO&source=taifex")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()["data"]
            self.assertEqual(payload["decisionState"], "NO_TRADE")
            self.assertFalse(payload["decisionEligible"])
            self.assertEqual(payload["reasonCodes"], ["DATA_QUALITY_INSUFFICIENT"])
            self.assertEqual(payload["dataQualityStatus"], "FAILED")

            saved = store.get_decision(payload["decision_id"])
            self.assertEqual(saved["decisionState"], payload["decisionState"])
            self.assertEqual(saved["decisionEligible"], payload["decisionEligible"])
            self.assertEqual(saved["reasonCodes"], payload["reasonCodes"])
            self.assertEqual(saved["source_metadata"]["data_quality_status"], payload["dataQualityStatus"])
            self.assertEqual(saved["source_metadata"]["quality_coverage"], payload["qualityCoverage"])
            self.assertEqual(saved["source_metadata"]["data_quality_dimensions"], payload["dataQualityDimensions"])
            self.assertEqual(saved["source_metadata"]["data_quality_dimension_status"], payload["dataQualityDimensionStatus"])
            self.assertEqual(saved["decision_output"]["decisionState"], payload["decisionState"])
            self.assertEqual(saved["decision_output"]["reasonCodes"], payload["reasonCodes"])


if __name__ == "__main__":
    unittest.main()
