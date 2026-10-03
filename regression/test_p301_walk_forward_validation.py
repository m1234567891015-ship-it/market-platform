"""P3-01 expanding walk-forward pipeline tests; fixtures are never evidence."""

from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta

from derivatives.probability_forecast import TARGET_HORIZON, fit_probability_forecast
from derivatives.walk_forward_validation import (
    TEST_EVIDENCE_CLASS,
    build_walk_forward_report,
)


def _decision(index: int) -> dict:
    decision_time = datetime(2026, 1, 1, 9) + timedelta(days=index)
    stamp = decision_time.isoformat() + "+08:00"
    market_date = decision_time.date().isoformat()
    source = {
        "status": "AVAILABLE",
        "provider": "TAIFEX",
        "source": "isolated P3-01 fixture",
        "sourceRole": "TAIFEX_PRIMARY",
    }
    return {
        "decision_id": f"p301-fixture-{index:03d}",
        "target_symbol": "TX",
        "decision_time": stamp,
        "market_as_of": market_date,
        "data_as_of": market_date + "T08:00:00+08:00",
        "instrument": "TX",
        "decisionState": "LONG",
        "decisionEligible": True,
        "executionDirection": "LONG",
        "evidence_score": 65,
        "data_quality_score": 75,
        "source_metadata": {"source_provenance": source},
        "decision_output": {
            "decisionState": "LONG",
            "decisionEligible": True,
            "executionDirection": "LONG",
            "marketScore": 35 if index % 2 else 70,
            "riskScore": 55,
            "evidenceScore": 65,
            "dataQualityScore": 75,
            "probabilityLabelAllowed": False,
        },
    }


def _outcome(decision: dict, success: bool) -> dict:
    decision_time = datetime.fromisoformat(decision["decision_time"])
    evaluated_at = (decision_time + timedelta(hours=8)).isoformat()
    return {
        "decision_id": decision["decision_id"],
        "evaluation_horizon": TARGET_HORIZON,
        "evaluation_time": evaluated_at,
        "status": "AVAILABLE",
        "outcome_status": "EVALUATED",
        "outcome_metadata": {
            "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
            "outcomeStatus": "EVALUATED",
            "horizon": TARGET_HORIZON,
            "evaluationBasis": "DIRECTIONAL_RETURN",
            "decisionAlignedReturn": 0.01 if success else -0.01,
            "timestamps": {"evaluatedAt": evaluated_at},
            "provenance": {
                "decision": decision["source_metadata"]["source_provenance"],
                "outcome": {
                    "provider": "TAIFEX",
                    "source": "isolated P3-01 outcome fixture",
                    "sourceRole": "OUTCOME_PRICE",
                },
            },
        },
    }


def _prospective_fixture(count: int) -> tuple[list[dict], list[dict]]:
    decisions: list[dict] = []
    outcomes: list[dict] = []
    training_rows: list[dict] = []
    for index in range(count):
        decision = _decision(index)
        fitted = fit_probability_forecast(decision, training_rows)
        forecast = fitted.get("probabilityForecast")
        if isinstance(forecast, dict):
            decision["decision_output"]["probabilityForecast"] = forecast
        outcome = _outcome(decision, success=(index % 2 == 0))
        decisions.append(decision)
        outcomes.append(outcome)
        training_rows.append({"decision": decision, "outcome": outcome})
    return decisions, outcomes


class P301WalkForwardValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decisions, cls.outcomes = _prospective_fixture(60)

    def test_empty_pipeline_is_ready_but_fixture_data_is_not_authoritative(self) -> None:
        report = build_walk_forward_report([], [])
        self.assertEqual(report["validationPipelineStatus"], "VALIDATION PIPELINE READY")
        self.assertEqual(report["statisticalEvidenceMaturity"], "SYNTHETIC_OR_NONAUTHORITATIVE_EVIDENCE_ONLY")
        self.assertEqual(report["counts"]["authoritativeEvidenceCount"], 0)
        self.assertEqual(report["counts"]["eligibleProspectiveOosPairs"], 0)
        self.assertEqual(report["chronologyChecks"]["status"], "NOT OBSERVED — NO VALID OOS PAIRS")

    def test_expanding_folds_replay_deterministically_and_require_authoritative_identity(self) -> None:
        first = build_walk_forward_report(self.decisions, self.outcomes, evidence_class=TEST_EVIDENCE_CLASS)
        second = build_walk_forward_report(self.decisions, self.outcomes, evidence_class=TEST_EVIDENCE_CLASS)
        self.assertEqual(first["reportFingerprint"], second["reportFingerprint"])
        self.assertEqual(first["counts"]["eligibleProspectiveOosPairs"], 30)
        self.assertEqual(first["counts"]["testOnlySyntheticPairCount"], 30)
        self.assertEqual(first["counts"]["authoritativeEvidenceCount"], 0)
        self.assertEqual(first["statisticalEvidenceMaturity"], "SYNTHETIC_OR_NONAUTHORITATIVE_EVIDENCE_ONLY")
        self.assertEqual(first["calibration"]["calibrationStatus"], "UNCALIBRATED")
        self.assertFalse(first["calibration"]["probabilityLabelAllowed"])
        self.assertEqual(first["counts"]["replayMismatches"], 0)
        self.assertEqual(first["chronologyChecks"]["status"], "PASS")

        with_future, future_outcomes = _prospective_fixture(61)
        future_report = build_walk_forward_report(with_future, future_outcomes)
        last_current_id = self.decisions[-1]["decision_id"]
        current_fold = next(row for row in first["folds"] if row["decisionId"] == last_current_id)
        future_fold = next(row for row in future_report["folds"] if row["decisionId"] == last_current_id)
        self.assertEqual(current_fold, future_fold)

    def test_replay_mismatch_and_unknown_provenance_are_excluded(self) -> None:
        decisions = copy.deepcopy(self.decisions)
        decisions[-1]["decision_output"]["probabilityForecast"]["value"] += 0.01
        mismatch = build_walk_forward_report(decisions, self.outcomes)
        self.assertEqual(mismatch["counts"]["replayMismatches"], 1)
        self.assertEqual(mismatch["counts"]["eligibleProspectiveOosPairs"], 29)
        self.assertEqual(mismatch["folds"][-1]["status"], "DETERMINISTIC_REPLAY_MISMATCH")

        unknown = copy.deepcopy(self.decisions)
        unknown[-1]["source_metadata"]["source_provenance"] = {"status": "UNKNOWN"}
        unknown_report = build_walk_forward_report(unknown, self.outcomes)
        self.assertEqual(unknown_report["counts"]["provenanceExclusions"], 1)
        self.assertEqual(unknown_report["counts"]["eligibleProspectiveOosPairs"], 29)
        self.assertEqual(unknown_report["folds"][-1]["status"], "DECISION_PROVENANCE_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
