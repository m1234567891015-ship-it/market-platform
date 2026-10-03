"""P3-04 temporal-stability regressions; all fixtures are test-only."""

from __future__ import annotations

import copy
import math
import unittest
from datetime import datetime, timedelta

from derivatives import probability_forecast as p2
from derivatives.model_drift_validation import (
    PSI_EPSILON,
    TEST_EVIDENCE_CLASS,
    _auc_window,
    _base_rate_temporal_report,
    _feature_population,
    _feature_temporal_report,
    _forecast_temporal_report,
    _histogram,
    _net_expectancy_temporal_report,
    _paired_performance_temporal_report,
    _probability_bin,
    _psi,
    _score_bin,
    _target_population,
    build_model_drift_report,
)


def _decision(
    index: int,
    *,
    features: tuple[object, object, object, object] = (50, 51, 60, 75),
    state: str = "LONG",
    eligible: bool = True,
) -> dict:
    moment = datetime(2026, 1, 1, 9) + timedelta(days=index)
    market_date = moment.date().isoformat()
    values = dict(zip(("marketScore", "riskScore", "evidenceScore", "dataQualityScore"), features))
    provenance = {
        "status": "AVAILABLE",
        "provider": "TAIFEX",
        "source": "isolated P3-04 fixture",
        "sourceRole": "TAIFEX_PRIMARY",
    }
    return {
        "decision_id": f"p304-fixture-{index:04d}",
        "target_symbol": "TX",
        "decision_time": moment.isoformat() + "+08:00",
        "market_as_of": market_date,
        "data_as_of": market_date + "T08:00:00+08:00",
        "instrument": "TX",
        "decisionState": state,
        "decisionEligible": eligible,
        "executionDirection": state if eligible else "UNAVAILABLE",
        "evidence_score": features[2],
        "data_quality_score": features[3],
        "execution_cost_assumptions": {
            "status": "AVAILABLE",
            "contractVersion": "P0B_FUTURES_COST_V1",
            "instrumentSymbol": "TX",
            "currency": "TWD",
        },
        "source_metadata": {"source_provenance": provenance},
        "decision_output": {
            **values,
            "decisionState": state if eligible else "NO_TRADE",
            "decisionEligible": eligible,
            "executionDirection": state if eligible else "UNAVAILABLE",
            "probabilityLabelAllowed": False,
        },
    }


def _outcome(decision: dict, positive: bool) -> dict:
    decision_time = datetime.fromisoformat(decision["decision_time"])
    evaluated_at = (decision_time + timedelta(hours=8)).isoformat()
    gross_pct = 2.0 if positive else -2.0
    normalized_cost_pct = 0.5
    total_cost = 3.0
    gross_pnl = 100.0
    cost_result = {
        "status": "AVAILABLE",
        "contractVersion": "P0B_FUTURES_COST_V1",
        "instrumentSymbol": "TX",
        "currency": "TWD",
        "grossPnl": gross_pnl,
        "commissionCost": 1.0,
        "taxCost": 1.0,
        "slippageCost": 1.0,
        "otherCost": 0.0,
        "totalCost": total_cost,
        "netPnl": gross_pnl - total_cost,
        "normalizedCostPct": normalized_cost_pct,
        "grossDirectionalReturnPct": gross_pct,
        "costAdjustedReturnPct": gross_pct - normalized_cost_pct,
    }
    decision_provenance = copy.deepcopy(decision["source_metadata"]["source_provenance"])
    return {
        "decision_id": decision["decision_id"],
        "evaluation_horizon": "T+1",
        "evaluation_time": evaluated_at,
        "status": "EVALUATED",
        "outcome_status": "EVALUATED",
        "gross_return": gross_pct / 100,
        "execution_cost": total_cost,
        "net_return": cost_result["costAdjustedReturnPct"] / 100,
        "unavailable_reason": None,
        "target_hit": "NOT_APPLICABLE",
        "stop_hit": "NOT_APPLICABLE",
        "data_quality_status": "AVAILABLE",
        "market_observations": [],
        "cost_adjusted_result": copy.deepcopy(cost_result),
        "outcome_metadata": {
            "outcomeSchemaVersion": "P2_02_OUTCOME_V1",
            "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
            "outcomeStatus": "EVALUATED",
            "decisionId": decision["decision_id"],
            "horizon": "T+1",
            "evaluationBasis": "DIRECTIONAL_RETURN",
            "decisionAlignedReturn": gross_pct / 100,
            "strategyEvaluationBasis": "STRATEGY_RETURN",
            "strategyReturn": copy.deepcopy(cost_result),
            "timestamps": {"evaluatedAt": evaluated_at},
            "provenance": {
                "decision": decision_provenance,
                "outcome": {
                    "provider": "TAIFEX",
                    "source": "isolated P3-04 outcome fixture",
                    "sourceRole": "OUTCOME_PRICE",
                },
            },
        },
    }


def _prospective_fixture(count: int, label_fn=None) -> tuple[list[dict], list[dict]]:
    decisions: list[dict] = []
    outcomes: list[dict] = []
    training_rows: list[dict] = []
    for index in range(count):
        positive = bool(label_fn(index) if label_fn else index % 2 == 0)
        decision = _decision(index, features=(20 + index % 10, 30 + index % 7, 50 + index % 9, 65 + index % 6))
        forecast = p2.fit_probability_forecast(decision, training_rows).get("probabilityForecast")
        if isinstance(forecast, dict):
            decision["decision_output"]["probabilityForecast"] = forecast
        outcome = _outcome(decision, positive)
        decisions.append(decision)
        outcomes.append(outcome)
        training_rows.append({"decision": decision, "outcome": outcome})
    return decisions, outcomes


class P304ModelDriftValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decisions90, cls.outcomes90 = _prospective_fixture(90)
        cls.report90 = build_model_drift_report(cls.decisions90, cls.outcomes90)

    def test_empty_pipeline_is_ready_but_synthetic_evidence_is_never_authoritative(self) -> None:
        report = build_model_drift_report([], [])
        self.assertEqual(report["engineeringStatus"], "PASS")
        self.assertEqual(report["temporalStabilityPipelineStatus"], "READY")
        self.assertEqual(report["evidenceClass"], TEST_EVIDENCE_CLASS)
        self.assertEqual(report["authoritativeDriftEvidence"], "SYNTHETIC_TEST_ONLY — NEVER AUTHORITATIVE")
        self.assertEqual(report["counts"]["testOnlySyntheticEvidenceCount"], 0)
        self.assertFalse(report["monitoringContract"]["probabilityLabelAllowed"])

    def test_exactly_59_is_insufficient_and_exactly_60_creates_30_30_windows(self) -> None:
        decisions59 = [_decision(index) for index in range(59)]
        rows59, _ = _feature_population(decisions59)
        report59 = _feature_temporal_report(rows59)
        self.assertEqual(report59["status"], "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS")
        self.assertEqual(report59["eligibleObservationCount"], 59)
        self.assertEqual(report59["referenceWindow"], None)
        self.assertEqual(report59["uncomparedTailObservationCount"], 59)

        decisions60 = [_decision(index) for index in range(60)]
        rows60, _ = _feature_population(decisions60)
        report60 = _feature_temporal_report(rows60)
        self.assertEqual(report60["status"], "AVAILABLE")
        self.assertEqual(report60["referenceWindow"]["observationCount"], 30)
        self.assertEqual(report60["features"]["marketScore"]["comparisons"][0]["currentWindow"]["observationCount"], 30)
        self.assertEqual(report60["uncomparedTailObservationCount"], 0)

    def test_ordering_is_chronological_and_future_rows_do_not_rewrite_reference(self) -> None:
        rows, _ = _feature_population(self.decisions90)
        reversed_rows, _ = _feature_population(list(reversed(self.decisions90)))
        forward = _feature_temporal_report(rows)
        reversed_report = _feature_temporal_report(reversed_rows)
        self.assertEqual(forward, reversed_report)

        extended_decisions = copy.deepcopy(self.decisions90)
        future = _decision(90, features=(100, 100, 100, 100))
        extended_decisions.append(future)
        extended_rows, _ = _feature_population(extended_decisions)
        extended = _feature_temporal_report(extended_rows)
        self.assertEqual(
            forward["referenceWindow"],
            extended["referenceWindow"],
        )
        self.assertEqual(
            forward["features"]["marketScore"]["reference"],
            extended["features"]["marketScore"]["reference"],
        )

    def test_missing_invalid_nonfinite_and_out_of_range_features_fail_closed(self) -> None:
        valid = _decision(0)
        missing = _decision(1)
        missing["decision_output"].pop("riskScore")
        boolean = _decision(2)
        boolean["decision_output"]["marketScore"] = True
        nan_row = _decision(3)
        nan_row["decision_output"]["marketScore"] = math.nan
        infinity = _decision(4)
        infinity["decision_output"]["marketScore"] = math.inf
        out_of_range = _decision(5)
        out_of_range["decision_output"]["marketScore"] = 101
        bad_time = _decision(6)
        bad_time["decision_time"] = "2026-01-07T09:00:00"
        future_asof = _decision(7)
        future_asof["data_as_of"] = "2026-01-09T00:00:00+08:00"
        rows, excluded = _feature_population([valid, missing, boolean, nan_row, infinity, out_of_range, bad_time, future_asof])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["decisionId"], valid["decision_id"])
        self.assertEqual(sum(excluded.values()), 7)

        decisions = [_decision(index) for index in range(60)]
        decisions[-1]["decision_output"]["riskScore"] = math.nan
        report = build_model_drift_report(decisions, [])
        self.assertEqual(report["counts"]["validInputFeatureObservations"], 59)
        self.assertEqual(report["inputFeatureTemporalStability"]["status"], "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS")

    def test_duplicate_decision_ids_are_excluded_from_input_population(self) -> None:
        first = _decision(0)
        duplicate = copy.deepcopy(first)
        duplicate["decision_time"] = "2026-01-02T09:00:00+08:00"
        rows, excluded = _feature_population([first, duplicate])
        self.assertEqual(rows, [])
        self.assertEqual(excluded, {"DUPLICATE_DECISION_ID": 2})

    def test_fixed_score_and_probability_boundaries(self) -> None:
        self.assertEqual([_score_bin(value) for value in range(0, 101, 10)], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9])
        self.assertEqual([_probability_bin(value / 10) for value in range(11)], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9])
        with self.assertRaises(ValueError):
            _probability_bin(math.nan)
        with self.assertRaises(ValueError):
            _probability_bin(1.01)

    def test_psi_is_zero_for_identical_distributions_and_finite_for_zero_bins(self) -> None:
        same = [0.0] * 15 + [50.0] * 15
        self.assertEqual(_psi(same, same, _score_bin), 0.0)
        shifted = _psi([0.0] * 30, [100.0] * 30, _score_bin)
        self.assertIsNotNone(shifted)
        self.assertGreater(shifted, 0)
        self.assertEqual(shifted, _psi([0.0] * 30, [100.0] * 30, _score_bin))
        self.assertEqual(PSI_EPSILON, 0.000001)
        self.assertEqual(sum(_histogram([0.0, 100.0], _score_bin)), 2)
        self.assertIsNone(_psi([], [1.0], _score_bin))

    def test_forecast_population_requires_replayed_real_probability_and_never_substitutes(self) -> None:
        report = self.report90
        self.assertEqual(report["counts"]["validProspectiveModelForecasts"], 60)
        self.assertEqual(report["forecastOutputTemporalStability"]["status"], "AVAILABLE")
        self.assertEqual(len(report["forecastOutputTemporalStability"]["comparisons"]), 1)
        self.assertTrue(all(item["psi"] is not None for item in report["forecastOutputTemporalStability"]["comparisons"]))
        self.assertEqual(report["baseline"]["modelContractVersion"], "P2_03_LOGISTIC_REGRESSION_V1")

        no_forecast = [_decision(index, eligible=False) for index in range(60)]
        missing_report = build_model_drift_report(no_forecast, [])
        self.assertEqual(missing_report["counts"]["validProspectiveModelForecasts"], 0)
        self.assertEqual(missing_report["forecastOutputTemporalStability"]["status"], "NOT AVAILABLE — NO VALID PROSPECTIVE MODEL FORECASTS")
        self.assertIsNone(missing_report["forecastOutputTemporalStability"].get("reference"))

    def test_forecast_replay_mismatch_is_not_counted_as_valid_output(self) -> None:
        decisions, outcomes = _prospective_fixture(61)
        decisions[-1]["decision_output"]["probabilityForecast"]["value"] += 0.01
        report = build_model_drift_report(decisions, outcomes)
        self.assertEqual(report["counts"]["validProspectiveModelForecasts"], 30)
        self.assertEqual(report["forecastOutputTemporalStability"]["status"], "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS")
        self.assertGreater(report["populationExclusions"]["forecast"].get("DETERMINISTIC_REPLAY_MISMATCH", 0), 0)

    def test_forecast_probability_stats_are_chronological_and_probability_label_remains_false(self) -> None:
        report = self.report90
        current = report["forecastOutputTemporalStability"]["comparisons"][0]
        self.assertEqual(current["currentWindow"]["observationCount"], 30)
        self.assertEqual(len(current["referenceBinCounts"]), 10)
        self.assertFalse(report["baseline"]["probabilityLabelAllowed"])

    def test_base_rate_delta_is_reference_minus_current_in_chronological_windows(self) -> None:
        rows = [
            {"decisionId": f"d{i:03d}", "decisionTime": f"2026-01-{i + 1:02d}T09:00:00+08:00", "target": 0}
            for i in range(30)
        ] + [
            {"decisionId": f"d{i + 30:03d}", "decisionTime": f"2026-02-{i + 1:02d}T09:00:00+08:00", "target": 1}
            for i in range(30)
        ]
        report = _base_rate_temporal_report(rows)
        self.assertEqual(report["reference"]["positiveTargetRate"], 0.0)
        self.assertEqual(report["comparisons"][0]["current"]["positiveTargetRate"], 1.0)
        self.assertEqual(report["comparisons"][0]["positiveTargetRateDelta"], 1.0)

    def test_brier_windows_are_separate_and_auc_requires_both_classes(self) -> None:
        pairs = [
            {"decisionId": f"r{i:02d}", "decisionTime": f"2026-01-{i + 1:02d}T09:00:00+08:00", "probability": 0.2, "target": 0}
            for i in range(30)
        ] + [
            {"decisionId": f"c{i:02d}", "decisionTime": f"2026-02-{i + 1:02d}T09:00:00+08:00", "probability": 0.2, "target": 1}
            for i in range(30)
        ]
        report = _paired_performance_temporal_report(pairs)
        self.assertEqual(report["reference"]["brierScore"], 0.04)
        self.assertEqual(report["comparisons"][0]["current"]["brierScore"], 0.64)
        self.assertEqual(report["comparisons"][0]["brierScoreDelta"], 0.6)
        self.assertEqual(report["reference"]["auc"]["status"], "NOT AVAILABLE — SINGLE CLASS")
        self.assertEqual(report["comparisons"][0]["current"]["auc"]["status"], "NOT AVAILABLE — SINGLE CLASS")
        self.assertIsNone(_auc_window([{"probability": 0.1, "target": 1}] * 30)["value"])
        both = _auc_window([
            {"probability": 0.1, "target": 0},
            {"probability": 0.9, "target": 1},
        ])
        self.assertEqual(both["value"], 1.0)

    def test_no_trade_pending_not_applicable_and_invalid_basis_are_not_targets(self) -> None:
        no_trade = _decision(0, eligible=False)
        no_trade_outcome = _outcome(no_trade, True)
        pending_decision = _decision(1)
        pending = _outcome(pending_decision, True)
        pending["status"] = pending["outcome_status"] = "PENDING"
        pending["outcome_metadata"]["outcomeStatus"] = "PENDING"
        na_decision = _decision(2)
        not_applicable = _outcome(na_decision, True)
        not_applicable["status"] = not_applicable["outcome_status"] = "NOT_APPLICABLE"
        not_applicable["outcome_metadata"].update(outcomeStatus="NOT_APPLICABLE", evaluationBasis="NOT_APPLICABLE")
        invalid_decision = _decision(3)
        invalid_basis = _outcome(invalid_decision, True)
        invalid_basis["outcome_metadata"]["evaluationBasis"] = "UNKNOWN"
        report = build_model_drift_report(
            [no_trade, pending_decision, na_decision, invalid_decision],
            [no_trade_outcome, pending, not_applicable, invalid_basis],
        )
        self.assertEqual(report["counts"]["eligibleMaturedDirectionalTargetObservations"], 0)
        self.assertEqual(report["baseRateTemporalStability"]["status"], "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS")

    def test_p3_03_cost_qualification_is_reused_without_reimplementing_cost_rules(self) -> None:
        first = _decision(0)
        second = _decision(1)
        valid = _outcome(first, True)
        invalid_cost = _outcome(second, False)
        invalid_cost["cost_adjusted_result"]["totalCost"] = 99.0
        decisions = [first, second]
        outcomes = [valid, invalid_cost]
        report = build_model_drift_report(decisions, outcomes)
        self.assertEqual(report["counts"]["eligibleMaturedDirectionalTargetObservations"], 2)
        self.assertEqual(report["counts"]["costQualifiedObservationsAllP3_03Scopes"], 1)
        self.assertEqual(report["netExpectancyTemporalStability"]["costRulesReusedFrom"], "P3_03_NET_EXPECTANCY_VALIDATION_V1")
        self.assertEqual(report["netExpectancyTemporalStability"]["scopes"][0]["costQualifiedObservationCount"], 1)
        self.assertEqual(report["netExpectancyTemporalStability"]["scopes"][0]["status"], "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS")

    def test_regime_composition_reuses_p205_boundaries_without_a_new_taxonomy(self) -> None:
        scores = [0, 39.999, 40, 59.999, 60, 100]
        decisions = [_decision(index, features=(score, 50, 60, 70)) for index, score in enumerate(scores)]
        rows, _ = _feature_population(decisions)
        report = build_model_drift_report(decisions, [])
        self.assertEqual(report["regimeCompositionTemporalStability"]["contract"], "P2_05_MARKET_SCORE_REGIME_V1")
        self.assertEqual(report["regimeCompositionTemporalStability"]["eligibleObservationCount"], 6)
        self.assertIsNone(report["regimeCompositionTemporalStability"]["referenceWindow"])
        self.assertEqual(len(rows), 6)

    def test_authoritative_empty_windows_have_no_zero_metric_or_drift_classification(self) -> None:
        decisions = [_decision(index, eligible=False) for index in range(59)]
        report = build_model_drift_report(decisions, [])
        self.assertEqual(report["inputFeatureTemporalStability"]["status"], "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS")
        self.assertIsNone(report["brierAndAucTemporalStability"]["reference"]["brierScore"])
        self.assertEqual(report["driftSeverity"], "NOT GOVERNANCE-CLASSIFIED")
        self.assertTrue(any("No claim that drift is present or absent" in item for item in report["explicitNonClaims"]))

    def test_report_is_deterministic_for_identical_synthetic_inputs(self) -> None:
        decisions = [_decision(index) for index in range(4)]
        first = build_model_drift_report(decisions, [])
        second = build_model_drift_report(copy.deepcopy(decisions), [])
        reordered = build_model_drift_report(list(reversed(decisions)), [])
        self.assertEqual(first["reportFingerprint"], second["reportFingerprint"])
        self.assertEqual(first["reportFingerprint"], reordered["reportFingerprint"])
        self.assertEqual(first["counts"], second["counts"])
        self.assertEqual(first["evidenceClass"], TEST_EVIDENCE_CLASS)
        self.assertEqual(first["authoritativeDriftEvidence"], "SYNTHETIC_TEST_ONLY — NEVER AUTHORITATIVE")


if __name__ == "__main__":
    unittest.main()
