"""Focused P3-03 synthetic-only tests; fixtures never count as ledger evidence."""

from __future__ import annotations

import copy
import unittest

from derivatives.net_expectancy_validation import (
    P0B_CONTRACT_VERSION,
    TEST_EVIDENCE_CLASS,
    build_net_expectancy_report,
)


def decision(decision_id: str = "d1", *, instrument: str = "TX", direction: str = "LONG", eligible=True) -> dict:
    return {
        "decision_id": decision_id,
        "target_symbol": instrument,
        "instrument": instrument,
        "decision_time": "2026-01-01T09:00:00+08:00",
        "decision_output": {
            "decisionState": direction,
            "executionDirection": direction,
            "decisionEligible": eligible,
            "probabilityLabelAllowed": False,
        },
        "execution_cost_assumptions": {
            "status": "AVAILABLE",
            "contractVersion": P0B_CONTRACT_VERSION,
            "instrumentSymbol": instrument,
            "currency": "TWD",
        },
    }


def outcome(
    decision_id: str = "d1", *, horizon: str = "T+1", raw_status: str = "EVALUATED",
    gross_pct: float = 10.0, normalized_cost_pct: float = 2.0,
    net_return_override: float | None = None, evaluation_time: str = "2026-01-02T14:00:00+08:00",
) -> dict:
    net_pct = gross_pct - normalized_cost_pct
    total_cost = 4.0
    gross_pnl = 2.0 * gross_pct
    result = {
        "status": "AVAILABLE",
        "contractVersion": P0B_CONTRACT_VERSION,
        "instrumentSymbol": "TX",
        "currency": "TWD",
        "grossPnl": gross_pnl,
        "commissionCost": 2.0,
        "taxCost": 1.0,
        "slippageCost": 1.0,
        "otherCost": 0.0,
        "totalCost": total_cost,
        "netPnl": gross_pnl - total_cost,
        "normalizedCostPct": normalized_cost_pct,
        "grossDirectionalReturnPct": gross_pct,
        "costAdjustedReturnPct": net_pct,
    }
    return {
        "decision_id": decision_id,
        "evaluation_horizon": horizon,
        "evaluation_time": evaluation_time,
        "status": raw_status,
        "gross_return": gross_pct / 100,
        "execution_cost": total_cost,
        "net_return": net_pct / 100 if net_return_override is None else net_return_override,
        "outcome_metadata": {
            "outcomeStatus": "EVALUATED",
            "outcomeSchemaVersion": "P2_02_OUTCOME_V1",
            "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
            "decisionId": decision_id,
            "horizon": horizon,
            "evaluationBasis": "DIRECTIONAL_RETURN",
            "decisionAlignedReturn": gross_pct / 100,
            "strategyEvaluationBasis": "STRATEGY_RETURN",
            "strategyReturn": copy.deepcopy(result),
        },
        "cost_adjusted_result": result,
    }


def scope_for(report: dict, instrument: str = "TX") -> dict:
    return next(scope for scope in report["scopes"] if scope["instrument"] == instrument)


class P303NetExpectancyValidationTests(unittest.TestCase):
    def report(self, decisions=None, outcomes=None):
        return build_net_expectancy_report(decisions or [], outcomes or [])

    def test_empty_sample_is_pipeline_ready_but_metrics_are_unavailable_not_zero(self) -> None:
        report = self.report([decision()], [])
        scope = scope_for(report)
        self.assertEqual(report["authoritativeEvidenceClass"], TEST_EVIDENCE_CLASS)
        self.assertEqual(report["validationPipelineStatus"], "VALIDATION PIPELINE READY")
        self.assertEqual(report["expectancyAvailability"], "NOT AVAILABLE")
        self.assertEqual(scope["includedSampleCount"], 0)
        self.assertIsNone(scope["netExpectancy"])
        self.assertEqual(report["inputCounts"]["costQualifiedExpectancySampleCount"], 0)

    def test_one_eligible_positive_outcome_uses_net_return_and_cost(self) -> None:
        report = self.report([decision()], [outcome()])
        scope = scope_for(report)
        self.assertEqual(report["eligibilityFunnel"]["eligibleEvaluatedDirectionalT1OutcomeCount"], 1)
        self.assertEqual(scope["positiveReturnCount"], 1)
        self.assertAlmostEqual(scope["netExpectancy"], 0.08)
        self.assertAlmostEqual(scope["totalExecutionCost"], 4.0)
        self.assertNotAlmostEqual(scope["netExpectancy"], 0.10)

    def test_one_eligible_negative_outcome_is_negative_net_expectancy(self) -> None:
        report = self.report([decision(direction="SHORT")], [outcome(gross_pct=-5.0)])
        scope = scope_for(report)
        self.assertEqual(scope["negativeReturnCount"], 1)
        self.assertAlmostEqual(scope["netExpectancy"], -0.07)
        self.assertAlmostEqual(scope["averageLoss"], -0.07)

    def test_mixed_win_loss_and_flat_reconcile_to_arithmetic_expectancy(self) -> None:
        decisions = [decision("d1"), decision("d2"), decision("d3")]
        outcomes = [
            outcome("d1", gross_pct=10, normalized_cost_pct=2),
            outcome("d2", gross_pct=-2, normalized_cost_pct=2),
            outcome("d3", gross_pct=2, normalized_cost_pct=2),
        ]
        report = self.report(decisions, outcomes)
        scope = scope_for(report)
        self.assertEqual(scope["includedSampleCount"], 3)
        self.assertEqual((scope["positiveReturnCount"], scope["negativeReturnCount"], scope["zeroReturnCount"]), (1, 1, 1))
        self.assertAlmostEqual(scope["netExpectancy"], 0.013333333333)
        self.assertAlmostEqual(scope["expectancyDecomposition"]["reconciledExpectancy"], scope["netExpectancy"])
        self.assertAlmostEqual(scope["winRate"], 0.5)

    def test_transaction_cost_mismatch_excludes_observation_instead_of_using_gross_return(self) -> None:
        bad = outcome(net_return_override=0.10)
        report = self.report([decision()], [bad])
        self.assertEqual(report["eligibilityFunnel"]["costQualifiedNetExpectancyCount"], 0)
        self.assertEqual(report["eligibilityFunnel"]["costExclusionsByReason"], {"PERSISTED_NET_RETURN_MISMATCH": 1})
        self.assertIsNone(scope_for(report)["netExpectancy"])

    def test_no_trade_is_excluded(self) -> None:
        row = decision(eligible=False)
        row["decision_output"].update(decisionState="NO_TRADE", executionDirection="UNAVAILABLE")
        report = self.report([row], [outcome()])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"DECISION_NOT_EXPLICITLY_ELIGIBLE": 1})
        self.assertEqual(report["eligibilityFunnel"]["costQualifiedNetExpectancyCount"], 0)

    def test_explicit_false_eligibility_is_excluded(self) -> None:
        report = self.report([decision(eligible=False)], [outcome()])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"DECISION_NOT_EXPLICITLY_ELIGIBLE": 1})

    def test_missing_and_non_boolean_eligibility_fail_closed(self) -> None:
        for value, missing in ((None, True), (1, False), ("true", False)):
            with self.subTest(value=value, missing=missing):
                row = decision()
                if missing:
                    row["decision_output"].pop("decisionEligible")
                else:
                    row["decision_output"]["decisionEligible"] = value
                report = self.report([row], [outcome()])
                self.assertEqual(report["eligibilityFunnel"]["costQualifiedNetExpectancyCount"], 0)
                self.assertIn("DECISION_NOT_EXPLICITLY_ELIGIBLE", report["eligibilityFunnel"]["eligibilityExclusionsByReason"])

    def test_non_directional_or_mismatched_direction_is_excluded(self) -> None:
        for state, direction in (("HOLD_EXISTING", "UNAVAILABLE"), ("LONG", "SHORT")):
            with self.subTest(state=state, direction=direction):
                row = decision(direction=direction)
                row["decision_output"]["decisionState"] = state
                report = self.report([row], [outcome()])
                self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"NO_VALID_DIRECTIONAL_DECISION": 1})

    def test_missing_gross_realized_return_fails_closed(self) -> None:
        row = outcome()
        row["outcome_metadata"]["decisionAlignedReturn"] = None
        report = self.report([decision()], [row])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"MISSING_OR_INVALID_GROSS_DIRECTIONAL_RETURN": 1})

    def test_chronology_violation_is_rejected(self) -> None:
        row = outcome(evaluation_time="2026-01-01T09:00:00+08:00")
        report = self.report([decision()], [row])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"EVALUATION_NOT_AFTER_DECISION": 1})

    def test_naive_timestamps_are_rejected(self) -> None:
        d = decision()
        d["decision_time"] = "2026-01-01T09:00:00"
        report = self.report([d], [outcome()])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"INVALID_DECISION_TIMESTAMP": 1})

    def test_orphan_outcome_is_rejected(self) -> None:
        report = self.report([], [outcome("missing")])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"ORPHAN_OUTCOME": 1})

    def test_duplicate_outcome_association_is_rejected(self) -> None:
        report = self.report([decision()], [outcome(), outcome()])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"DUPLICATE_OUTCOME_ASSOCIATION": 2})

    def test_duplicate_decision_association_is_rejected(self) -> None:
        report = self.report([decision(), decision()], [outcome()])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"DUPLICATE_DECISION_ID": 1})

    def test_metadata_association_mismatch_is_rejected(self) -> None:
        row = outcome()
        row["outcome_metadata"]["decisionId"] = "other"
        report = self.report([decision()], [row])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"OUTCOME_DECISION_ID_METADATA_MISMATCH": 1})

    def test_non_t1_horizon_is_not_pooled(self) -> None:
        report = self.report([decision()], [outcome(horizon="T+2")])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"NON_T1_HORIZON": 1})

    def test_unavailable_or_unsupported_cost_is_excluded(self) -> None:
        row = outcome()
        row["cost_adjusted_result"]["status"] = "UNAVAILABLE"
        row["outcome_metadata"]["strategyReturn"]["status"] = "UNAVAILABLE"
        report = self.report([decision()], [row])
        self.assertEqual(report["eligibilityFunnel"]["costExclusionsByReason"], {"OUTCOME_P0B_COST_RESULT_UNAVAILABLE": 1})

    def test_negative_cost_is_rejected(self) -> None:
        row = outcome()
        row["cost_adjusted_result"]["commissionCost"] = -1
        row["outcome_metadata"]["strategyReturn"]["commissionCost"] = -1
        report = self.report([decision()], [row])
        self.assertEqual(report["eligibilityFunnel"]["costExclusionsByReason"], {"NEGATIVE_P0B_COST": 1})

    def test_cost_component_arithmetic_fault_is_rejected(self) -> None:
        row = outcome()
        row["cost_adjusted_result"]["totalCost"] = 100
        row["outcome_metadata"]["strategyReturn"]["totalCost"] = 100
        report = self.report([decision()], [row])
        self.assertEqual(report["eligibilityFunnel"]["costExclusionsByReason"], {"P0B_COST_COMPONENT_RECONCILIATION_FAILED": 1})

    def test_p2_raw_available_status_cannot_be_upgraded_from_metadata(self) -> None:
        row = outcome(raw_status="AVAILABLE")
        report = self.report([decision()], [row])
        self.assertEqual(report["engineeringStatus"], "BLOCKED")
        self.assertEqual(report["validationPipelineStatus"], "BLOCKED — P2-02/P2-04 CONTRACT CONFLICT")
        self.assertIn("P2-02/P2-04 OUTCOME STATUS CONTRACT CONFLICT", report["blockingDiagnostics"])
        self.assertEqual(report["eligibilityFunnel"]["costQualifiedNetExpectancyCount"], 0)

    def test_incompatible_p2_contract_version_is_rejected(self) -> None:
        row = outcome()
        row["outcome_metadata"]["evaluationContractVersion"] = "LEGACY_UNVERSIONED"
        report = self.report([decision()], [row])
        self.assertEqual(report["eligibilityFunnel"]["eligibilityExclusionsByReason"], {"OUTCOME_CONTRACT_VERSION_MISMATCH": 1})

    def test_cost_snapshot_version_mismatch_is_rejected(self) -> None:
        row_decision = decision()
        row_decision["execution_cost_assumptions"]["contractVersion"] = "OTHER"
        report = self.report([row_decision], [outcome()])
        self.assertEqual(report["eligibilityFunnel"]["costExclusionsByReason"], {"DECISION_TIME_P0B_COST_CONTRACT_UNAVAILABLE": 1})

    def test_cross_instrument_pooling_is_suppressed(self) -> None:
        mt = decision("d2", instrument="MTX")
        mt_outcome = outcome("d2")
        mt_outcome["cost_adjusted_result"]["instrumentSymbol"] = "MTX"
        mt_outcome["outcome_metadata"]["strategyReturn"]["instrumentSymbol"] = "MTX"
        report = self.report([decision(), mt], [outcome(), mt_outcome])
        self.assertEqual(len(report["scopes"]), 2)
        self.assertEqual(report["aggregationContract"]["crossInstrumentAggregation"], "SUPPRESSED")
        self.assertAlmostEqual(scope_for(report, "TX")["netExpectancy"], 0.08)
        self.assertAlmostEqual(scope_for(report, "MTX")["netExpectancy"], 0.08)
        self.assertEqual(report["overallRealizedMetrics"], "REPORTED ONLY IN COMPATIBLE INSTRUMENT SCOPES")

    def test_output_is_deterministic_for_identical_inputs(self) -> None:
        decisions = [decision("d2"), decision("d1")]
        outcomes = [outcome("d2"), outcome("d1", gross_pct=-2, normalized_cost_pct=2)]
        first = self.report(decisions, outcomes)
        second = self.report(decisions, outcomes)
        self.assertEqual(first["reportFingerprint"], second["reportFingerprint"])
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
