from __future__ import annotations

import copy
import hashlib
import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts import p204_score_bucket_performance as p204


_DEFAULT_ALIGNED = object()


def decision(decision_id: str, *, direction: str = "LONG", state: str | None = None, score: float | None = 50,
             instrument: str = "TX", evidence: float | None = 50, quality: float | None = 75,
             eligible: object = True) -> dict:
    state = state or direction
    return {
        "decision_id": decision_id, "instrument": instrument, "decision_time": "2026-09-01T09:00:00+08:00",
        "market_as_of": "2026-09-01", "evidence_score": evidence, "data_quality_score": quality,
        "decision_output": {"marketScore": score, "riskScore": 50, "executionDirection": direction,
                            "decisionState": state, "decisionEligible": eligible},
    }


def outcome(decision_id: str, horizon: str = "T+1", status: str = "EVALUATED",
            aligned: Any = _DEFAULT_ALIGNED, basis: str | None = None) -> dict:
    if aligned is _DEFAULT_ALIGNED:
        aligned = 0.1 if status == "EVALUATED" else None
    if basis is None:
        basis = {
            "EVALUATED": "DIRECTIONAL_RETURN", "PENDING": "DIRECTIONAL_RETURN",
            "NOT_APPLICABLE": "NOT_APPLICABLE", "UNAVAILABLE": "DIRECTIONAL_RETURN",
            "INVALID": "UNAVAILABLE",
        }.get(status, "UNKNOWN")
    return {
        "decision_id": decision_id, "evaluation_horizon": horizon, "evaluation_time": "2026-09-03T17:00:00+08:00",
        "status": status,
        "outcome_metadata": {"outcomeStatus": status, "decisionId": decision_id, "horizon": horizon,
                             "evaluationBasis": basis, "decisionAlignedReturn": aligned},
    }


class P204ScoreBucketTests(unittest.TestCase):
    def test_all_boundaries_are_gapless_and_100_is_in_final_bucket(self) -> None:
        boundaries = [0, 9.999999, 10, 20, 30, 40, 50, 60, 70, 80, 90, 99.999999, 100]
        expected = [0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9]
        self.assertEqual([p204.bucket_index(value) for value in boundaries], expected)
        intervals = [(low, high) for low, high in p204.BUCKETS]
        self.assertEqual(intervals[0][0], 0)
        self.assertEqual(intervals[-1][1], 100)
        self.assertTrue(all(intervals[i][1] == intervals[i + 1][0] for i in range(9)))
        self.assertEqual(p204.bucket_label(9), "[90,100]")

    def test_boundary_values_land_in_expected_performance_buckets(self) -> None:
        values = (0, 9.999999, 10, 99.999999, 100)
        decisions = [decision(f"edge-{index}", score=value) for index, value in enumerate(values)]
        outcomes = [outcome(row["decision_id"]) for row in decisions]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["status"], "PASS")
        expected = {0: 2, 1: 1, 9: 2}
        for idx, count in expected.items():
            row = next(row for row in result["performance"] if row["score"] == "marketScore" and
                       row["instrument"] == "OVERALL" and row["bucket"] == p204.bucket_label(idx) and
                       row["directionView"] == "ALL_ELIGIBLE" and row["evaluationHorizon"] == "T+1")
            self.assertEqual(row["n"], count)
            self.assertEqual(row["N"], count)
        middle = next(row for row in result["performance"] if row["score"] == "marketScore" and
                      row["instrument"] == "OVERALL" and row["bucket"] == "[10,20)" and
                      row["directionView"] == "ALL_ELIGIBLE" and row["evaluationHorizon"] == "T+1")
        self.assertEqual(middle["n"], 1)

    def test_directional_long_and_short_returns_preserve_positive_negative_semantics(self) -> None:
        decisions = [
            decision("long-positive", direction="LONG"), decision("long-negative", direction="LONG"),
            decision("short-positive", direction="SHORT"), decision("short-negative", direction="SHORT"),
        ]
        outcomes = [
            outcome("long-positive", aligned=0.12), outcome("long-negative", aligned=-0.08),
            outcome("short-positive", aligned=0.07), outcome("short-negative", aligned=-0.11),
        ]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["status"], "PASS")
        for direction in ("LONG_ONLY", "SHORT_ONLY"):
            row = next(row for row in result["performance"] if row["score"] == "marketScore" and
                       row["instrument"] == "OVERALL" and row["bucket"] == "[50,60)" and
                       row["directionView"] == direction and row["evaluationHorizon"] == "T+1")
            self.assertEqual((row["n"], row["positiveCount"], row["negativeCount"], row["empiricalSuccessRate"]),
                             (2, 1, 1, 0.5))
            self.assertEqual(row["sampleInterpretation"], "DESCRIPTIVE_ONLY; NO_SAMPLE_SUFFICIENCY_GATE_DEFINED")

    def test_invalid_score_values_fail_closed_in_coverage_and_buckets(self) -> None:
        values = (-0.1, 100.1, None, "50", math.nan, math.inf, True, 10 ** 500)
        decisions = [decision(f"invalid-{index}", score=value) for index, value in enumerate(values)]
        outcomes = [outcome(row["decision_id"]) for row in decisions]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        audit = result["inputAudit"]["scoreAudit"]["marketScore"]
        self.assertEqual((audit["nullCount"], audit["invalidScoreCount"], audit["outOfRangeScoreCount"]), (1, 4, 3))
        self.assertEqual(result["eligibilityFunnel"]["MISSING_SCORE"], 1)
        self.assertEqual(result["eligibilityFunnel"]["INVALID_SCORE"], 7)
        self.assertFalse(any(row["n"] for row in result["performance"] if row["score"] == "marketScore"))

    def test_invalid_decision_aligned_returns_never_enter_performance(self) -> None:
        values = (None, True, "0.1", math.nan, math.inf, 10 ** 500)
        decisions = [decision(f"return-{index}") for index in range(len(values))]
        outcomes = [outcome(row["decision_id"], aligned=value) for row, value in zip(decisions, values)]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["eligibilityFunnel"]["EVALUATED"], len(values))
        self.assertEqual(result["eligibilityFunnel"]["INVALID"], len(values))
        self.assertEqual(result["eligibilityFunnel"]["VALID_BUCKET_PERFORMANCE_ROWS"], 0)
        self.assertTrue(all(row["reason"] == "MISSING_OR_INVALID_DECISION_ALIGNED_RETURN" for row in result["excludedRows"]))

    def test_missing_invalid_and_out_of_range_scores_fail_closed(self) -> None:
        for value in (None, "50", True, float("nan"), float("inf"), -0.001, 100.001):
            with self.subTest(value=value):
                self.assertIsNone(p204.bucket_index(value))

    def test_scores_are_read_from_frozen_decision_time_fields(self) -> None:
        row = decision("d1", score=61, evidence=42, quality=88)
        self.assertEqual(p204.score_value(row, "marketScore"), 61)
        self.assertEqual(p204.score_value(row, "riskScore"), 50)
        self.assertEqual(p204.score_value(row, "evidenceScore"), 42)
        self.assertEqual(p204.score_value(row, "dataQualityScore"), 88)
        self.assertIsNone(p204.score_value(decision("missing", score=None), "marketScore"))

    def test_evaluated_only_flat_is_separate_and_horizons_are_not_combined(self) -> None:
        decisions = [decision("long", direction="LONG"), decision("short", direction="SHORT")]
        outcomes = [outcome("long", "T+1", aligned=0.2), outcome("short", "T+2", aligned=0.0)]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["status"], "PASS")
        rows = result["performance"]
        t1 = next(row for row in rows if row["score"] == "marketScore" and row["bucket"] == "[50,60)" and row["evaluationHorizon"] == "T+1" and row["instrument"] == "OVERALL" and row["directionView"] == "LONG_ONLY")
        t2 = next(row for row in rows if row["score"] == "marketScore" and row["bucket"] == "[50,60)" and row["evaluationHorizon"] == "T+2" and row["instrument"] == "OVERALL" and row["directionView"] == "SHORT_ONLY")
        self.assertEqual((t1["N"], t1["positiveCount"], t1["empiricalSuccessRate"]), (1, 1, 1.0))
        self.assertEqual((t2["N"], t2["flatCount"], t2["empiricalSuccessRate"]), (1, 1, None))
        self.assertEqual(t2["meanDecisionAlignedReturn"], 0.0)
        self.assertEqual(result["eligibilityFunnel"]["VALID_BUCKET_PERFORMANCE_ROWS"], 2)

    def test_non_evaluated_statuses_and_no_trade_do_not_enter_performance(self) -> None:
        states = ["PENDING", "NOT_APPLICABLE", "UNAVAILABLE", "INVALID"]
        decisions = [decision("no-trade", direction="UNAVAILABLE", state="NO_TRADE")]
        outcomes = [outcome("no-trade", status=status) for status in states]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["eligibilityFunnel"]["PENDING"], 1)
        self.assertEqual(result["eligibilityFunnel"]["NOT_APPLICABLE"], 1)
        self.assertEqual(result["eligibilityFunnel"]["UNAVAILABLE"], 1)
        self.assertEqual(result["eligibilityFunnel"]["INVALID"], 1)
        self.assertIn("NOT AVAILABLE", result["performance"])
        self.assertTrue(any(row == {"score": "marketScore", "instrument": "TX", "bucket": "[50,60)", "count": 1}
                            for row in result["inputAudit"]["noTradeCountByScoreBucket"]))
        self.assertEqual(result["performanceArtifacts"], "NOT_WRITTEN_NO_ELIGIBLE_OUTCOMES")

    def test_no_trade_hold_and_unknown_never_become_directional_performance(self) -> None:
        decisions = [
            decision("no", direction="UNAVAILABLE", state="NO_TRADE"),
            decision("hold", direction="UNAVAILABLE", state="HOLD_EXISTING"),
            decision("unknown", direction="UNAVAILABLE", state="UNKNOWN"),
        ]
        outcomes = [outcome(row["decision_id"]) for row in decisions]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("NOT AVAILABLE", result["performance"])

    def test_evaluated_outcomes_require_explicit_true_decision_eligibility(self) -> None:
        rows = [
            decision("false", eligible=False), decision("unknown", eligible=None),
            decision("invalid", eligible="true"), decision("missing"),
        ]
        rows[3]["decision_output"].pop("decisionEligible")
        result = p204.analyze(rows, [outcome(row["decision_id"]) for row in rows], p204.source_contract())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["eligibilityFunnel"]["EVALUATED"], 4)
        self.assertEqual(result["eligibilityFunnel"]["INELIGIBLE_DECISION"], 4)
        self.assertEqual(result["eligibilityFunnel"]["VALID_BUCKET_PERFORMANCE_ROWS"], 0)
        self.assertEqual(result["inputAudit"]["decisionEligibilityCounts"], {
            "TRUE": 0, "FALSE": 1, "UNKNOWN": 1, "MISSING": 1, "INVALID": 1,
        })
        self.assertTrue(all(row["reason"] == "DECISION_NOT_ELIGIBLE" for row in result["excludedRows"]))

    def test_decision_state_and_execution_direction_must_match(self) -> None:
        row = decision("direction-conflict", direction="SHORT", state="LONG")
        result = p204.analyze([row], [outcome("direction-conflict")], p204.source_contract())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["eligibilityFunnel"]["INVALID_DIRECTION_STATE"], 1)

    def test_status_metadata_basis_and_relationship_conflicts_fail_closed(self) -> None:
        decisions = [decision(name) for name in ("status-meta", "basis", "decision-id", "horizon", "pending-basis")]
        outcomes = [
            outcome("status-meta", status="PENDING"),
            outcome("basis", basis="UNKNOWN"),
            outcome("decision-id"),
            outcome("horizon"),
            outcome("pending-basis", status="PENDING", basis="NOT_APPLICABLE"),
        ]
        outcomes[0]["outcome_metadata"]["outcomeStatus"] = "EVALUATED"
        outcomes[2]["outcome_metadata"]["decisionId"] = "other-decision"
        outcomes[3]["outcome_metadata"]["horizon"] = "T+2"
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["eligibilityFunnel"]["STATUS_METADATA_MISMATCH"], 1)
        self.assertEqual(result["eligibilityFunnel"]["INCOMPATIBLE_STATUS_BASIS"], 3)
        self.assertEqual(result["eligibilityFunnel"]["BASIS_MISMATCH"], 1)
        self.assertEqual(result["eligibilityFunnel"]["INVALID_RELATIONSHIP"], 2)
        self.assertEqual(len(result["integrityReport"]["outcomeStatusMetadataMismatches"]), 1)
        self.assertEqual(len(result["integrityReport"]["incompatibleStatusBasisPairs"]), 3)
        self.assertEqual(len(result["integrityReport"]["invalidDecisionOutcomeRelationships"]), 2)

    def test_noncanonical_legacy_outcome_statuses_cannot_be_upgraded_to_evaluated(self) -> None:
        decisions = [decision("available"), decision("partial")]
        outcomes = [
            outcome("available", status="AVAILABLE", basis="DIRECTIONAL_RETURN"),
            outcome("partial", status="PARTIAL", basis="DIRECTIONAL_RETURN"),
        ]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["eligibilityFunnel"]["EVALUATED"], 0)
        self.assertEqual(result["eligibilityFunnel"]["INVALID"], 2)
        self.assertEqual(result["eligibilityFunnel"]["VALID_BUCKET_PERFORMANCE_ROWS"], 0)

    def test_basis_mismatch_duplicate_join_and_orphan_are_excluded(self) -> None:
        decisions = [decision("d1"), decision("d2")]
        outcomes = [
            outcome("d2", horizon="T+1", basis="UNKNOWN"),
            outcome("d1"), outcome("d1"),
            outcome("orphan"),
        ]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertEqual(result["integrityReport"]["orphanOutcomes"], [{"decisionId": "orphan", "horizon": "T+1"}])
        self.assertEqual(result["integrityReport"]["outcomeDecisionHorizonDuplicates"], [["d1", "T+1"]])
        self.assertEqual(result["integrityReport"]["decisionIdsWithOutcomes"], ["d1", "d2"])
        self.assertEqual(result["integrityReport"]["invalidDecisionOutcomeRelationships"], [
            {"decisionId": "orphan", "horizon": "T+1", "reason": "ORPHAN_DECISION_ID"},
        ])
        self.assertEqual(result["eligibilityFunnel"]["BASIS_MISMATCH"], 1)
        self.assertEqual(result["status"], "BLOCKED")

    def test_missing_scores_are_excluded_without_backfill(self) -> None:
        row = decision("d1", score=None, evidence=None, quality=None)
        row["decision_output"]["riskScore"] = None
        result = p204.analyze([row], [outcome("d1")], p204.source_contract())
        self.assertEqual(result["inputAudit"]["scoreAudit"]["marketScore"]["nullCount"], 1)
        self.assertEqual(result["inputAudit"]["scoreAudit"]["evidenceScore"]["nullCount"], 1)
        self.assertEqual(result["eligibilityFunnel"]["MISSING_SCORE"], 4)
        self.assertEqual(result["status"], "BLOCKED")

    def test_horizon_mismatch_is_excluded(self) -> None:
        result = p204.analyze([decision("d1")], [outcome("d1", horizon="T+0")], p204.source_contract())
        self.assertEqual(result["eligibilityFunnel"]["HORIZON_MISMATCH"], 1)
        self.assertEqual(result["status"], "BLOCKED")

    def test_zero_authoritative_outcomes_returns_explicit_blocker_not_empty_performance(self) -> None:
        result = p204.analyze([decision("d1")], [], p204.source_contract())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["reason"], "NO ELIGIBLE EVALUATED OUTCOMES")
        self.assertIn("NOT AVAILABLE", result["performance"])
        self.assertEqual(result["performanceArtifacts"], "NOT_WRITTEN_NO_ELIGIBLE_OUTCOMES")

    def test_repeat_analysis_is_byte_deterministic(self) -> None:
        decisions = [decision("d1")]
        outcomes = [outcome("d1")]
        first = p204.analyze(copy.deepcopy(decisions), copy.deepcopy(outcomes), p204.source_contract())
        second = p204.analyze(copy.deepcopy(decisions), copy.deepcopy(outcomes), p204.source_contract())
        self.assertEqual(p204.canonical_bytes(first), p204.canonical_bytes(second))

    def test_different_instrument_score_semantics_are_not_aggregated(self) -> None:
        decisions = [decision("tx", instrument="TX"), decision("txo", instrument="TXO")]
        outcomes = [outcome("tx"), outcome("txo")]
        result = p204.analyze(decisions, outcomes, p204.source_contract())
        self.assertFalse(result["inputAudit"]["instrumentAggregateSemantics"]["marketScore"]["overallAggregationAllowed"])
        self.assertTrue(all(row["instrument"] != "OVERALL" for row in result["performance"]))

    def test_risk_score_is_partitioned_by_canonical_risk_classification(self) -> None:
        market = decision("market-risk")
        portfolio = decision("portfolio-risk")
        market["decision_output"]["riskClassification"] = {"type": "MARKET_RISK"}
        portfolio["decision_output"]["riskClassification"] = {"type": "PORTFOLIO_RISK"}
        result = p204.analyze([market, portfolio], [outcome("market-risk"), outcome("portfolio-risk")], p204.source_contract())
        self.assertFalse(result["inputAudit"]["instrumentAggregateSemantics"]["riskScore"]["overallAggregationAllowed"])
        risk_rows = [row for row in result["performance"] if row["score"] == "riskScore"]
        self.assertEqual({row["instrument"] for row in risk_rows}, {"TX::MARKET_RISK", "TX::PORTFOLIO_RISK"})

    def test_readonly_ledger_inventory_preserves_database_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p204-readonly-") as temp_dir:
            path = Path(temp_dir) / "ledger.sqlite3"
            conn = sqlite3.connect(path)
            conn.executescript("""
                CREATE TABLE decision_ledger (
                    decision_id TEXT PRIMARY KEY, target_symbol TEXT, decision_time TEXT, market_as_of TEXT,
                    instrument TEXT, input_snapshot_json TEXT, decision_output_json TEXT, evidence_score REAL, data_quality_score REAL,
                    source_metadata_json TEXT
                );
                CREATE TABLE decision_outcome (
                    decision_id TEXT, evaluation_horizon TEXT, evaluation_time TEXT, status TEXT,
                    market_observations_json TEXT, cost_adjusted_result_json TEXT
                );
            """)
            conn.execute("INSERT INTO decision_ledger VALUES (?,?,?,?,?,?,?,?,?,?)", (
                "d1", "TX", "2026-09-01T09:00:00+08:00", "2026-09-01", "TX",
                "{}", json.dumps({"marketScore": 50, "riskScore": 40}), 50, 60, "{}",
            ))
            conn.commit()
            conn.close()
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            inventory, decisions, outcomes, fingerprints = p204.readonly_inventory(path)
            after = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertTrue(inventory["databaseAndSidecarsUnchanged"])
            self.assertEqual(len(decisions), 1)
            self.assertEqual(outcomes, [])
            self.assertEqual(fingerprints[str(path.resolve())], before)
            summary = p204.build_artifacts(path)["p204_summary.json"]
            self.assertEqual(summary["p203Status"], "CLOSED — P2-04 uses P2-01 + P2-02 only")
            self.assertEqual(summary["status"], "BLOCKED")
            self.assertNotIn("bucket_performance.csv", p204.build_artifacts(path))


if __name__ == "__main__":
    unittest.main()
