"""Safety and chronology tests for the one-shot P2-03 evidence runner."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from derivatives.probability_forecast import TARGET_HORIZON, valid_oos_pair
from derivatives_store import DerivativesStore
from scripts.p203_prospective_evidence_runner import (
    EXPECTED_DB,
    decision_exists_for_market_session,
    evaluate_due_outcomes,
    observation_provenance,
    validate_evidence_db,
)


class P203ProspectiveEvidenceRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="p203-runner-")
        self.addCleanup(self.temp_dir.cleanup)
        self.store = DerivativesStore(Path(self.temp_dir.name) / "isolated.sqlite3")
        self.store.initialize()

    def decision(self, decision_id: str = "p203-runner-decision", state: str = "LONG") -> dict:
        snapshot = {"market": {"close": 100, "date": "2026-09-01"}}
        snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
        return {
            "decision_id": decision_id, "symbol": "TX", "instrument": "TX",
            "decision_time": "2026-09-02T09:00:00+08:00", "market_as_of": "2026-09-01",
            "data_as_of": "2026-09-01T08:55:00+08:00", "strategy_id": "test-strategy",
            "strategy_version": "test-strategy-v1", "model_version": "test-model-v1",
            "input_snapshot_hash": hashlib.sha256(snapshot_json.encode()).hexdigest(),
            "input_snapshot": snapshot, "reference_price": 100,
            "executionDirection": state, "executionDirectionReason": f"EXPLICIT_{state}_DECISION",
            "executionDirectionContractVersion": "P1D_DIRECTION_V1",
            "source_provenance": {"provider": "TAIFEX", "sourceRole": "PRIMARY"},
            "decision_output": {"decisionState": state, "decisionEligible": True,
                                "executionDirection": state, "marketScore": 60,
                                "riskScore": 40, "evidenceScore": 80, "dataQualityScore": 75},
        }

    def test_wrong_and_production_like_paths_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_evidence_db(Path(self.temp_dir.name) / "prod.sqlite3")
        with self.assertRaises(ValueError):
            validate_evidence_db(Path(self.temp_dir.name) / "isolated.sqlite3")
        self.assertTrue(str(EXPECTED_DB).endswith("p203-prospective-ledger.sqlite3"))

    def test_unknown_or_invalid_provider_observation_is_not_accepted(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.assertIsNone(observation_provenance({"time": "invalid", "close": 100}, now))
        self.assertIsNone(observation_provenance({"time": "2026-09-03", "close": 0, "provider": "TAIFEX"}, now))
        row = observation_provenance({"time": "2026-09-03", "close": 101,
                                      "open": 100, "high": 102, "low": 99}, now)
        self.assertEqual(row["provider"], "TAIFEX")
        self.assertEqual(row["sourceRole"], "OUTCOME_PRICE")

    def test_immature_t1_is_reported_pending_without_immutable_outcome_row(self) -> None:
        self.store.record_decision(self.decision())
        result = evaluate_due_outcomes(self.store, [], "2026-09-02T10:00:00+08:00")
        self.assertEqual(result["pending"], 1)
        self.assertIsNone(self.store.get_decision_outcome("p203-runner-decision", TARGET_HORIZON))

    def test_same_market_session_is_deduplicated(self) -> None:
        self.store.record_decision(self.decision())
        self.assertEqual(decision_exists_for_market_session(self.store, "2026-09-01")["decision_id"],
                         "p203-runner-decision")
        self.assertIsNone(decision_exists_for_market_session(self.store, "2026-09-02"))

    def test_mature_t1_uses_p2_02_and_preserves_provider_provenance(self) -> None:
        self.store.record_decision(self.decision())
        observed_at = datetime.now(timezone.utc).isoformat()
        observation = observation_provenance({"time": "2026-09-03", "open": 100,
                                              "high": 103, "low": 99, "close": 102}, observed_at)
        result = evaluate_due_outcomes(self.store, [observation], observed_at)
        self.assertEqual(result["evaluated"], 1)
        saved = self.store.get_decision_outcome("p203-runner-decision", TARGET_HORIZON)
        self.assertEqual(saved["outcome_status"], "EVALUATED")
        self.assertEqual(saved["outcome_metadata"]["provenance"]["outcome"]["provider"], "TAIFEX")

    def test_no_trade_is_not_evaluated_as_directional_training(self) -> None:
        no_trade = self.decision("p203-runner-no-trade", state="NO_POSITION")
        no_trade["decision_output"].update({"decisionState": "NO_TRADE", "decisionEligible": False})
        no_trade["decision_output"]["reasonCodes"] = ["DATA_QUALITY_INSUFFICIENT"]
        no_trade["executionDirection"] = "UNAVAILABLE"
        no_trade["executionDirectionReason"] = "ANALYSIS_ONLY"
        no_trade["decision_output"]["executionDirection"] = "UNAVAILABLE"
        no_trade["data_quality_status"] = "FAILED"
        self.store.record_decision(no_trade)
        result = evaluate_due_outcomes(self.store, [], "2026-09-02T10:00:00+08:00")
        self.assertEqual(result["pending"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertIsNone(self.store.get_decision_outcome("p203-runner-no-trade", TARGET_HORIZON))

    def test_oos_pair_requires_original_forecast_provenance(self) -> None:
        decision = self.decision()
        decision["decision_output"].update({
            "probabilityForecast": {
                "value": 0.6, "targetContractVersion": "P2_03_DIRECTIONAL_SUCCESS_V1",
                "featureContractVersion": "P2_03_DERIVATIVES_SCORE_FEATURES_V1",
                "horizon": "T+1", "generatedAt": decision["decision_time"],
                "fitCutoff": "2026-09-01T17:00:00+08:00",
                "provenance": "PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT",
            }
        })
        outcome = {"evaluation_horizon": "T+1", "evaluation_time": "2026-09-03T17:00:00+08:00",
                   "outcome_status": "EVALUATED", "outcome_metadata": {
                       "outcomeStatus": "EVALUATED", "horizon": "T+1",
                       "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
                       "evaluationBasis": "DIRECTIONAL_RETURN", "decisionAlignedReturn": 0.01}}
        self.assertIsNotNone(valid_oos_pair(decision, outcome))
        decision["decision_output"]["probabilityForecast"]["provenance"] = "UNKNOWN"
        self.assertIsNone(valid_oos_pair(decision, outcome))
        decision["decision_output"]["probabilityForecast"]["provenance"] = "PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT"
        outcome["evaluation_horizon"] = "T+5"
        self.assertIsNone(valid_oos_pair(decision, outcome))


if __name__ == "__main__":
    unittest.main()
