from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts import p205_regime_performance as p205


MISSING = object()


def decision(
    decision_id: str,
    *,
    score: Any = 50,
    direction: str = "LONG",
    state: str | None = None,
    eligible: Any = True,
) -> dict[str, Any]:
    output = {
        "marketScore": score,
        "executionDirection": direction,
        "decisionState": state or direction,
        "probabilityLabelAllowed": False,
    }
    if eligible is not MISSING:
        output["decisionEligible"] = eligible
    return {
        "decision_id": decision_id,
        "decision_time": "2026-09-01T09:00:00+08:00",
        "market_as_of": "2026-09-01",
        "instrument": "TX",
        "decision_output": output,
    }


def outcome(
    decision_id: str,
    *,
    horizon: str = "T+1",
    status: str = "EVALUATED",
    aligned: Any = 0.1,
    basis: str | None = None,
    meta_decision_id: str | None = None,
    meta_horizon: str | None = None,
    meta_status: str | None = None,
) -> dict[str, Any]:
    if basis is None:
        basis = "DIRECTIONAL_RETURN" if status in {"EVALUATED", "PENDING", "UNAVAILABLE"} else status
    metadata = {
        "decisionId": meta_decision_id if meta_decision_id is not None else decision_id,
        "horizon": meta_horizon if meta_horizon is not None else horizon,
        "outcomeStatus": meta_status if meta_status is not None else status,
        "evaluationBasis": basis,
        "decisionAlignedReturn": aligned,
    }
    return {
        "decision_id": decision_id,
        "evaluation_horizon": horizon,
        "evaluation_time": "2026-09-03T17:00:00+08:00",
        "status": status,
        "outcome_metadata": metadata,
    }


def sqlite_fixture(path: Path, decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE decision_ledger (
            decision_id TEXT PRIMARY KEY, target_symbol TEXT, decision_time TEXT, market_as_of TEXT,
            instrument TEXT, input_snapshot_json TEXT, decision_output_json TEXT, evidence_score REAL,
            data_quality_score REAL, source_metadata_json TEXT
        );
        CREATE TABLE decision_outcome (
            decision_id TEXT, evaluation_horizon TEXT, evaluation_time TEXT, status TEXT,
            market_observations_json TEXT, cost_adjusted_result_json TEXT
        );
    """)
    for row in decisions:
        connection.execute(
            "INSERT INTO decision_ledger VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["decision_id"], row["decision_id"], row["decision_time"], row["market_as_of"], row["instrument"],
             "{}", json.dumps(row["decision_output"]), 50, 75, "{}"),
        )
    for row in outcomes:
        connection.execute(
            "INSERT INTO decision_outcome VALUES (?,?,?,?,?,?)",
            (row["decision_id"], row["evaluation_horizon"], row["evaluation_time"], row["status"],
             json.dumps({"metadata": row["outcome_metadata"]}), "{}"),
        )
    connection.commit()
    connection.close()


class P205RegimePerformanceTests(unittest.TestCase):
    def test_owner_frozen_regime_boundaries_are_gapless(self) -> None:
        cases = ((0, "LOW"), (39.999, "LOW"), (40, "MID"), (59.999, "MID"), (60, "HIGH"), (100, "HIGH"))
        self.assertEqual([(p205.classify_market_score(value)[0], p205.classify_market_score(value)[1]) for value, _ in cases],
                         [(expected, None) for _, expected in cases])

    def test_missing_invalid_and_out_of_range_scores_fail_closed(self) -> None:
        for value, expected_reason in (
            (None, "MISSING_SCORE"), ("50", "INVALID_SCORE"), (True, "INVALID_SCORE"),
            (math.nan, "INVALID_SCORE"), (math.inf, "INVALID_SCORE"), (-0.001, "INVALID_SCORE"),
            (100.001, "INVALID_SCORE"), (10 ** 500, "INVALID_SCORE"),
        ):
            with self.subTest(value=repr(value)[:30]):
                self.assertEqual(p205.classify_market_score(value), (None, expected_reason))

    def test_classification_reads_only_persisted_decision_output_market_score(self) -> None:
        row = decision("pit", score=60)
        row["runtimeMarketScore"] = 5
        first = p205.decision_regime(row)
        row["runtimeMarketScore"] = 99
        row["currentMarketScore"] = 0
        second = p205.decision_regime(row)
        self.assertEqual(first, ("HIGH", None))
        self.assertEqual(second, first)

    def test_exact_metrics_are_reported_per_regime(self) -> None:
        rows = [
            ("low-positive", 20, "LONG", 0.2), ("low-negative", 30, "SHORT", -0.1), ("low-flat", 10, "LONG", 0.0),
            ("mid-positive", 40, "LONG", 0.4), ("mid-negative", 50, "SHORT", -0.2), ("mid-flat", 59.999, "LONG", 0.0),
            ("high-positive-a", 60, "LONG", 0.3), ("high-negative", 80, "SHORT", -0.1), ("high-positive-b", 100, "LONG", 0.2),
        ]
        decisions = [decision(name, score=score, direction=direction) for name, score, direction, _ in rows]
        outcomes = [outcome(name, aligned=aligned) for name, _, _, aligned in rows]
        result = p205.analyze(decisions, outcomes)
        actual = {row["regime"]: row for row in result["performanceRows"]}
        self.assertEqual(set(actual), {"LOW", "MID", "HIGH"})
        self.assertEqual((actual["LOW"]["n"], actual["LOW"]["evaluatedCount"], actual["LOW"]["positiveCount"],
                          actual["LOW"]["negativeCount"], actual["LOW"]["flatCount"], actual["LOW"]["successRate"]),
                         (3, 3, 1, 1, 1, 0.5))
        self.assertAlmostEqual(actual["LOW"]["meanDecisionAlignedReturn"], 0.1 / 3)
        self.assertEqual(actual["LOW"]["medianDecisionAlignedReturn"], 0.0)
        self.assertEqual((actual["MID"]["n"], actual["MID"]["positiveCount"], actual["MID"]["negativeCount"], actual["MID"]["successRate"]),
                         (3, 1, 1, 0.5))
        self.assertAlmostEqual(actual["MID"]["meanDecisionAlignedReturn"], 0.2 / 3)
        self.assertEqual((actual["HIGH"]["n"], actual["HIGH"]["positiveCount"], actual["HIGH"]["negativeCount"], actual["HIGH"]["successRate"]),
                         (3, 2, 1, 2 / 3))
        self.assertAlmostEqual(actual["HIGH"]["meanDecisionAlignedReturn"], 0.4 / 3)
        self.assertEqual(actual["HIGH"]["medianDecisionAlignedReturn"], 0.2)
        self.assertTrue(all(row["interpretation"] == "DESCRIPTIVE REGIME PERFORMANCE" for row in actual.values()))

    def test_long_and_short_positive_negative_directional_returns(self) -> None:
        rows = [
            ("long-positive", "LONG", 0.12), ("long-negative", "LONG", -0.08),
            ("short-positive", "SHORT", 0.07), ("short-negative", "SHORT", -0.11),
        ]
        result = p205.analyze(
            [decision(name, score=50, direction=direction) for name, direction, _ in rows],
            [outcome(name, aligned=aligned) for name, _, aligned in rows],
        )
        metric = result["performanceRows"][0]
        self.assertEqual((metric["n"], metric["positiveCount"], metric["negativeCount"], metric["flatCount"], metric["successRate"]),
                         (4, 2, 2, 0, 0.5))
        self.assertAlmostEqual(metric["meanDecisionAlignedReturn"], 0.0)
        self.assertAlmostEqual(metric["medianDecisionAlignedReturn"], -0.005)

    def test_outcome_horizons_are_not_pooled(self) -> None:
        rows = [decision("same", score=41)]
        result = p205.analyze(rows, [outcome("same", horizon="T+1", aligned=0.1), outcome("same", horizon="T+2", aligned=-0.2)])
        self.assertEqual({(row["regime"], row["evaluationHorizon"], row["n"]) for row in result["performanceRows"]},
                         {("MID", "T+1", 1), ("MID", "T+2", 1)})

    def test_directional_semantics_and_fail_closed_exclusions(self) -> None:
        decisions = [
            decision("no-trade", score=50, direction="UNAVAILABLE", state="NO_TRADE"),
            decision("hold", score=50, direction="UNAVAILABLE", state="HOLD_EXISTING"),
            decision("unknown", score=50, direction="UNAVAILABLE", state="UNKNOWN"),
            decision("false", eligible=False), decision("missing", eligible=MISSING), decision("nonboolean", eligible="true"),
            decision("direction-mismatch", direction="SHORT", state="LONG"),
        ]
        outcomes = [outcome(row["decision_id"]) for row in decisions]
        outcomes.extend(outcome(f"status-{status.lower()}", status=status, aligned=None)
                        for status in ("PENDING", "NOT_APPLICABLE", "UNAVAILABLE", "INVALID"))
        decisions.extend(decision(f"status-{status.lower()}")
                         for status in ("PENDING", "NOT_APPLICABLE", "UNAVAILABLE", "INVALID"))
        result = p205.analyze(decisions, outcomes)
        self.assertEqual(result["summary"]["eligibleEvaluatedLongShortCount"], 0)
        reasons = " ".join(row["reasons"] for row in result["eligibilityRows"])
        for expected in (
            "DECISION_STATE_DIRECTION_MISMATCH", "DECISION_NOT_EXPLICITLY_ELIGIBLE",
            "OUTCOME_NOT_EVALUATED:PENDING", "OUTCOME_NOT_EVALUATED:NOT_APPLICABLE",
            "OUTCOME_NOT_EVALUATED:UNAVAILABLE", "OUTCOME_NOT_EVALUATED:INVALID",
        ):
            self.assertIn(expected, reasons)

    def test_invalid_basis_and_non_finite_returns_are_excluded(self) -> None:
        decisions = [decision("basis"), decision("nan"), decision("inf"), decision("string"), decision("huge")]
        outcomes = [
            outcome("basis", basis="UNKNOWN"), outcome("nan", aligned=math.nan), outcome("inf", aligned=math.inf),
            outcome("string", aligned="0.1"), outcome("huge", aligned=10 ** 500),
        ]
        result = p205.analyze(decisions, outcomes)
        self.assertEqual(result["summary"]["eligibleEvaluatedLongShortCount"], 0)
        self.assertTrue(all("INVALID_DECISION_ALIGNED_RETURN" in row["reasons"] or "OUTCOME_BASIS_CONFLICT" in row["reasons"]
                            for row in result["eligibilityRows"]))

    def test_orphan_duplicate_metadata_and_direction_conflicts_fail_closed(self) -> None:
        decisions = [decision("dup"), decision("direction", direction="SHORT", state="LONG")]
        outcomes = [
            outcome("orphan"), outcome("dup"), outcome("dup"),
            outcome("direction"), outcome("direction", meta_decision_id="wrong"),
            outcome("direction", meta_horizon="T+9"), outcome("direction", status="PENDING", meta_status="EVALUATED"),
            outcome("direction", basis="UNKNOWN"),
        ]
        # Duplicate decision IDs are represented in-memory because the production schema primary key forbids them.
        decisions.append(decision("dup", score=55))
        result = p205.analyze(decisions, outcomes)
        integrity = result["summary"]["joinIntegrity"]
        self.assertGreaterEqual(integrity["orphanOutcomeCount"], 1)
        self.assertGreaterEqual(integrity["duplicateDecisionIdAssociationCount"], 2)
        self.assertGreaterEqual(integrity["duplicateOutcomeAssociationCount"], 2)
        self.assertGreaterEqual(integrity["decisionOutcomeMetadataMismatchCount"], 2)
        self.assertGreaterEqual(integrity["outcomeStatusConflictCount"], 1)
        self.assertGreaterEqual(integrity["outcomeBasisConflictCount"], 1)
        self.assertGreaterEqual(integrity["decisionStateDirectionMismatchCount"], 1)
        self.assertEqual(result["summary"]["eligibleEvaluatedLongShortCount"], 0)

    def test_missing_score_is_coverage_audit_only(self) -> None:
        result = p205.analyze([decision("missing-score", score=None), decision("valid", score=50)],
                              [outcome("missing-score"), outcome("valid")])
        self.assertEqual(result["summary"]["regimeCoverage"]["MID"], 1)
        self.assertEqual(result["summary"]["regimeCoverage"]["REGIME_INVALID"], 1)
        self.assertEqual(result["summary"]["regimeCoverage"]["missingMarketScoreCount"], 1)
        self.assertEqual(result["summary"]["eligibleEvaluatedLongShortCount"], 1)
        self.assertTrue(any(row["regime"] == "REGIME_INVALID" and "REGIME_INVALID" in row["reasons"]
                            for row in result["eligibilityRows"]))

    def test_zero_evidence_has_no_performance_artifact_or_synthetic_rows(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p205-zero-") as temporary:
            path = Path(temporary) / "ledger.sqlite3"
            sqlite_fixture(path, [decision("d1")], [])
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            artifacts = p205.build_artifacts(path)
            after = hashlib.sha256(path.read_bytes()).hexdigest()
            summary = json.loads(artifacts["summary.json"])
            self.assertEqual(before, after)
            self.assertEqual(summary["realizedRegimePerformance"]["status"], "NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES")
            self.assertEqual(summary["eligibleEvaluatedLongShortCount"], 0)
            self.assertNotIn("regime_performance.csv", artifacts)
            self.assertEqual(artifacts["eligibility_audit.csv"].count(b"\n"), 1)

    def test_immutable_sqlite_inventory_reports_counts_dates_and_unchanged_hash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p205-readonly-") as temporary:
            path = Path(temporary) / "ledger.sqlite3"
            sqlite_fixture(path, [decision("d1", score=50)], [outcome("d1")])
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            inventory, decisions, outcomes = p205.readonly_inventory(path)
            after = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(inventory["databaseSha256"], before)
            self.assertEqual(inventory["decisionCount"], 1)
            self.assertEqual(inventory["outcomeCount"], 1)
            self.assertEqual(inventory["latestMarketDate"], "2026-09-01")
            self.assertTrue(inventory["databaseAndSidecarsUnchangedDuringRead"])
            self.assertEqual((len(decisions), len(outcomes)), (1, 1))
            self.assertEqual(after, before)

    def test_zero_evidence_sqlite_artifacts_are_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p205-determinism-") as temporary:
            path = Path(temporary) / "ledger.sqlite3"
            sqlite_fixture(path, [decision("d1", score=50)], [])
            first = p205.build_artifacts(path)
            second = p205.build_artifacts(path)
            self.assertEqual({key: p205.sha256_bytes(value) for key, value in first.items()},
                             {key: p205.sha256_bytes(value) for key, value in second.items()})
            self.assertNotIn("regime_performance.csv", first)

    def test_probability_label_remains_explicitly_false(self) -> None:
        result = p205.analyze([decision("d1")], [])
        self.assertEqual(result["summary"]["probabilityLabelAllowed"]["status"], "PASS")
        self.assertTrue(result["summary"]["probabilityLabelAllowed"]["allPersistedValuesFalse"])
        row = decision("true", score=50)
        row["decision_output"]["probabilityLabelAllowed"] = True
        self.assertEqual(p205.analyze([row], [])["summary"]["probabilityLabelAllowed"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
