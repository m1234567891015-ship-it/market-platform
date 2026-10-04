"""P3-02 regime partition regressions; every fixture is synthetic test-only."""

from __future__ import annotations

import copy
import math
import unittest
from datetime import datetime, timedelta

from derivatives.probability_forecast import TARGET_HORIZON, fit_probability_forecast
from derivatives.regime_conditioned_validation import build_regime_conditioned_report
from scripts import p205_regime_performance as p205


def _decision(index: int, score: object) -> dict:
    moment = datetime(2026, 1, 1, 9) + timedelta(days=index)
    market_date = moment.date().isoformat()
    provenance = {
        "status": "AVAILABLE",
        "provider": "TAIFEX",
        "source": "isolated P3-02 fixture",
        "sourceRole": "TAIFEX_PRIMARY",
    }
    return {
        "decision_id": f"p302-fixture-{index:03d}",
        "target_symbol": "TX",
        "decision_time": moment.isoformat() + "+08:00",
        "market_as_of": market_date,
        "data_as_of": market_date + "T08:00:00+08:00",
        "instrument": "TX",
        "decisionState": "LONG",
        "decisionEligible": True,
        "executionDirection": "LONG",
        "evidence_score": 65,
        "data_quality_score": 75,
        "source_metadata": {"source_provenance": provenance},
        "decision_output": {
            "decisionState": "LONG",
            "decisionEligible": True,
            "executionDirection": "LONG",
            "marketScore": score,
            "riskScore": 55,
            "evidenceScore": 65,
            "dataQualityScore": 75,
            "probabilityLabelAllowed": False,
        },
    }


def _outcome(decision: dict, success: bool) -> dict:
    decision_time = datetime.fromisoformat(decision["decision_time"])
    evaluated_at = (decision_time + timedelta(hours=8)).isoformat()
    provenance = decision["source_metadata"]["source_provenance"]
    return {
        "decision_id": decision["decision_id"],
        "evaluation_horizon": TARGET_HORIZON,
        "evaluation_time": evaluated_at,
        "status": "EVALUATED",
        "outcome_status": "EVALUATED",
        "outcome_metadata": {
            "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
            "outcomeStatus": "EVALUATED",
            "horizon": TARGET_HORIZON,
            "evaluationBasis": "DIRECTIONAL_RETURN",
            "decisionAlignedReturn": 0.01 if success else -0.01,
            "timestamps": {"evaluatedAt": evaluated_at},
            "provenance": {
                "decision": provenance,
                "outcome": {
                    "provider": "TAIFEX",
                    "source": "isolated P3-02 outcome fixture",
                    "sourceRole": "OUTCOME_PRICE",
                },
            },
        },
    }


def _prospective_fixture(count: int = 60) -> tuple[list[dict], list[dict]]:
    decisions: list[dict] = []
    outcomes: list[dict] = []
    training_rows: list[dict] = []
    for index in range(count):
        score = 20 if index % 2 == 0 else 70
        decision = _decision(index, score)
        fitted = fit_probability_forecast(decision, training_rows)
        forecast = fitted.get("probabilityForecast")
        if isinstance(forecast, dict):
            decision["decision_output"]["probabilityForecast"] = forecast
        outcome = _outcome(decision, success=index % 2 == 0)
        decisions.append(decision)
        outcomes.append(outcome)
        training_rows.append({"decision": decision, "outcome": outcome})
    return decisions, outcomes


class P302RegimeConditionedValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decisions, cls.outcomes = _prospective_fixture()
        cls.report = build_regime_conditioned_report(cls.decisions, cls.outcomes)
        cls.repeat_report = build_regime_conditioned_report(cls.decisions, cls.outcomes)

    def test_reuses_frozen_p205_boundaries_and_invalid_score_rules(self) -> None:
        cases = (
            (0, "LOW"), (39.999, "LOW"), (40, "MID"),
            (59.999, "MID"), (60, "HIGH"), (100, "HIGH"),
        )
        for score, expected in cases:
            with self.subTest(score=score):
                self.assertEqual(p205.classify_market_score(score), (expected, None))
        for score in (None, "50", True, math.nan, math.inf, -0.01, 100.01):
            with self.subTest(invalid_score=repr(score)):
                self.assertIsNone(p205.classify_market_score(score)[0])

        invalid = [_decision(0, None), _decision(1, True), _decision(2, 101)]
        for row in invalid:
            row["decisionState"] = "NO_TRADE"
            row["executionDirection"] = "UNAVAILABLE"
            row["decisionEligible"] = False
            row["decision_output"].update({
                "decisionState": "NO_TRADE", "executionDirection": "UNAVAILABLE", "decisionEligible": False,
            })
        report = build_regime_conditioned_report(invalid, [])
        self.assertEqual(report["regimeContract"]["invalidMarketScoreCount"], 3)
        self.assertEqual(report["counts"]["validProspectiveOosPairs"], 0)
        self.assertEqual(report["realizedRegimeStatistics"]["authoritativeEvidenceCount"], 0)

    def test_metrics_are_partitioned_by_persisted_regime_without_pooling(self) -> None:
        first = self.report
        self.assertEqual(first["counts"]["validProspectiveOosPairs"], 30)
        self.assertEqual(first["counts"]["authoritativeEvidenceCount"], 0)
        self.assertEqual(first["counts"]["testOnlySyntheticPairCount"], 30)
        rows = {row["regime"]: row for row in first["regimeRows"]}
        self.assertEqual(rows["LOW"]["validOosPairCount"], 15)
        self.assertEqual(rows["HIGH"]["validOosPairCount"], 15)
        self.assertEqual(rows["MID"]["validOosPairCount"], 0)
        self.assertEqual(rows["LOW"]["positiveOosPairCount"], 15)
        self.assertEqual(rows["LOW"]["negativeOosPairCount"], 0)
        self.assertEqual(rows["HIGH"]["positiveOosPairCount"], 0)
        self.assertEqual(rows["HIGH"]["negativeOosPairCount"], 15)
        self.assertEqual(rows["LOW"]["realizedPositiveRate"], 1.0)
        self.assertEqual(rows["HIGH"]["realizedPositiveRate"], 0.0)
        self.assertTrue(first["chronologyAndLeakageChecks"]["metricsComputedOnlyWithinAssignedRegime"])
        self.assertEqual(first["chronologyAndLeakageChecks"]["chronologyStatus"], "PASS")
        self.assertEqual(first["statisticalEvidenceMaturity"], "SYNTHETIC_TEST_ONLY_NOT_AUTHORITATIVE")

    def test_deterministic_report_fingerprint_and_fail_closed_probability_policy(self) -> None:
        first = self.report
        second = self.repeat_report
        self.assertEqual(first["reportFingerprint"], second["reportFingerprint"])
        self.assertFalse(first["baseline"]["probabilityLabelAllowed"])
        self.assertTrue(all(row["brierSkillScore"] is None for row in first["regimeRows"]))
        self.assertTrue(all(row["netReturn"] is None for row in first["regimeRows"]))

    def test_no_trade_and_noneligible_decisions_are_not_directional_observations(self) -> None:
        decisions = copy.deepcopy(self.decisions)
        decisions[-1]["decisionState"] = "NO_TRADE"
        decisions[-1]["executionDirection"] = "UNAVAILABLE"
        decisions[-1]["decisionEligible"] = False
        decisions[-1]["decision_output"].update({
            "decisionState": "NO_TRADE",
            "executionDirection": "UNAVAILABLE",
            "decisionEligible": False,
        })
        decisions[-2]["decisionEligible"] = False
        decisions[-2]["decision_output"]["decisionEligible"] = False
        report = build_regime_conditioned_report(decisions, self.outcomes)
        self.assertEqual(report["counts"]["validProspectiveOosPairs"], 28)
        self.assertEqual(report["counts"]["eligibleEvaluatedDirectionalT1Outcomes"], 58)
        self.assertEqual(report["p2_05EligibilityAudit"]["eligibleEvaluatedLongShortCount"], 58)

    def test_outcome_before_decision_is_excluded_by_frozen_chronology(self) -> None:
        outcomes = copy.deepcopy(self.outcomes)
        last_decision = self.decisions[-1]
        earlier = (datetime.fromisoformat(last_decision["decision_time"]) - timedelta(minutes=1)).isoformat()
        outcomes[-1]["evaluation_time"] = earlier
        outcomes[-1]["outcome_metadata"]["timestamps"]["evaluatedAt"] = earlier
        report = build_regime_conditioned_report(self.decisions, outcomes)
        self.assertEqual(report["counts"]["validProspectiveOosPairs"], 29)
        self.assertEqual(report["chronologyAndLeakageChecks"]["observedValidOosPairs"], 29)


if __name__ == "__main__":
    unittest.main()
