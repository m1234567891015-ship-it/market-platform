from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")

import app
from derivatives_store import DerivativesStore


class OutcomeEvaluationP202Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="p2-02-outcome-")
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "isolated-ledger.sqlite3"
        self.store = DerivativesStore(self.db_path)
        self.store.initialize()
        self.snapshot = {"item": {"close": 100, "marketAsOf": "2026-09-01"}, "scenarioWeights": {"up": 0.4}}
        snapshot_json = json.dumps(self.snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        self.decision = {
            "decision_id": "p202-outcome-long",
            "symbol": "TX",
            "instrument": "TX",
            "decision_time": "2026-09-02T09:00:00+08:00",
            "market_as_of": "2026-09-01",
            "strategy_id": "test-strategy",
            "model_version": "test-model-v1",
            "strategy_version": "test-strategy-v1",
            "input_snapshot_hash": hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest(),
            "input_snapshot": self.snapshot,
            "decision_output": {
                "decisionState": "LONG", "decisionEligible": True, "reasonCodes": [],
                "scenarioWeights": {"up": 0.4}, "riskClassification": {"type": "MARKET_RISK", "score": 10},
                "dataQualityStatus": "AVAILABLE", "strategySuggestion": "existing suggestion",
                "marketScore": 65, "riskScore": 20,
            },
            "executionDirection": "LONG",
            "executionDirectionReason": "EXPLICIT_LONG_DECISION",
            "executionDirectionContractVersion": "P1D_DIRECTION_V1",
            "reference_price": 100,
            "execution_cost_assumptions": {"status": "UNAVAILABLE", "reason": "NO_DECISION_TIME_COST_CONTRACT"},
            "source_updated_at": "2026-09-01",
            "source_provenance": {"provider": "TAIFEX", "sourceRole": "PRIMARY"},
            "data_quality_status": "AVAILABLE",
            "created_at": "2026-09-02T09:00:00+08:00",
        }
        self.store.record_decision(self.decision)

    @staticmethod
    def bar(day: str, close: float, *, provider: str = "Yahoo") -> dict:
        return {
            "date": day,
            "market_as_of": day,
            "observed_at": f"{day}T16:00:00+08:00",
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "provider": provider,
            "sourceRole": "OUTCOME_PRICE",
        }

    def evaluate(self, decision_id: str, horizon: str, when: str, rows: list[dict], **kwargs) -> dict:
        return self.store.evaluate_decision_outcome(decision_id, horizon, when, rows, **kwargs)

    def test_long_outcome_has_explicit_entry_exit_and_directional_basis(self) -> None:
        result = self.evaluate("p202-outcome-long", "T+1", "2026-09-03T17:00:00+08:00", [self.bar("2026-09-03", 110)])
        self.assertEqual(result["outcome_status"], "EVALUATED")
        self.assertAlmostEqual(result["underlying_return"], 0.1)
        self.assertAlmostEqual(result["decision_aligned_return"], 0.1)
        saved = self.store.get_decision_outcome("p202-outcome-long", "T+1")
        meta = saved["outcome_metadata"]
        self.assertEqual(saved["status"], "EVALUATED")
        self.assertEqual(saved["outcome_status"], "EVALUATED")
        self.assertEqual(saved["data_quality_status"], result["data_quality_status"])
        self.assertEqual(saved["legacy_status"], result["status"])
        self.assertEqual(meta["legacyStatus"], result["status"])
        self.assertEqual(meta["evaluationBasis"], "DIRECTIONAL_RETURN")
        self.assertIsNone(meta["strategyEvaluationBasis"])
        self.assertEqual(meta["entryReference"], {"price": 100.0, "priceType": "DECISION_REFERENCE", "marketAsOf": "2026-09-01", "dataAsOf": "2026-09-01"})
        self.assertEqual(meta["evaluationReference"]["priceType"], "CLOSE")
        self.assertEqual(meta["evaluationReference"]["marketAsOf"], "2026-09-03")
        self.assertEqual(meta["provenance"]["outcome"], {"provider": "Yahoo", "sourceRole": "OUTCOME_PRICE"})
        self.assertEqual(meta["outcomeSchemaVersion"], "P2_02_OUTCOME_V1")

        from scripts import p204_score_bucket_performance as p204
        from derivatives.net_expectancy_validation import build_net_expectancy_report

        self.assertFalse(p204.outcome_status_metadata_mismatch(saved))
        self.assertEqual(p204.normalize_outcome_status(saved), "EVALUATED")
        report = build_net_expectancy_report(
            [self.store.get_decision("p202-outcome-long")], [saved]
        )
        self.assertEqual(report["authoritativeEvidenceClass"], "SYNTHETIC_TEST_ONLY")
        self.assertEqual(report["upstreamContractConflicts"], [])
        self.assertEqual(report["validationPipelineStatus"], "VALIDATION PIPELINE READY")

    def test_short_alignment_is_negative_underlying_return(self) -> None:
        short = {**self.decision, "decision_id": "p202-outcome-short", "executionDirection": "SHORT",
                 "executionDirectionReason": "EXPLICIT_SHORT_DECISION",
                 "decision_output": {**self.decision["decision_output"], "decisionState": "SHORT"}}
        self.store.record_decision(short)
        result = self.evaluate(short["decision_id"], "T+1", "2026-09-03T17:00:00+08:00", [self.bar("2026-09-03", 110)])
        self.assertAlmostEqual(result["underlying_return"], 0.1)
        self.assertAlmostEqual(result["decision_aligned_return"], -0.1)

    def test_flat_return_is_not_assigned_a_win_or_loss_label(self) -> None:
        result = self.evaluate("p202-outcome-long", "T+1", "2026-09-03T17:00:00+08:00", [self.bar("2026-09-03", 100)])
        self.assertEqual(result["outcome_status"], "EVALUATED")
        self.assertEqual(result["gross_return"], 0)
        self.assertEqual(result["decision_aligned_return"], 0)
        self.assertNotIn("win", result)
        self.assertNotIn("loss", result)

    def test_no_trade_is_not_applicable_without_synthetic_zero_return(self) -> None:
        no_trade = {**self.decision, "decision_id": "p202-no-trade", "executionDirection": "UNAVAILABLE",
                    "executionDirectionReason": "ANALYSIS_ONLY",
                    "decision_output": {"decisionState": "NO_TRADE", "reasonCodes": ["EDGE_INSUFFICIENT"]}}
        self.store.record_decision(no_trade)
        result = self.evaluate(no_trade["decision_id"], "T+1", "2026-09-03T17:00:00+08:00", [])
        self.assertEqual(result["outcome_status"], "NOT_APPLICABLE")
        self.assertIsNone(result.get("gross_return"))
        self.assertIsNone(result.get("net_return"))

    def test_unknown_and_hold_existing_fail_closed(self) -> None:
        unknown = {**self.decision, "decision_id": "p202-unknown", "executionDirection": "UNAVAILABLE",
                   "executionDirectionReason": "ANALYSIS_ONLY",
                   "decision_output": {"decisionState": "UNKNOWN", "reasonCodes": ["UNKNOWN"], "bias": "bullish"}}
        hold = {**self.decision, "decision_id": "p202-hold", "executionDirection": "UNAVAILABLE",
                "executionDirectionReason": "ANALYSIS_ONLY",
                "decision_output": {"decisionState": "HOLD_EXISTING", "reasonCodes": []}}
        self.store.record_decision(unknown)
        self.store.record_decision(hold)
        rows = [self.bar("2026-09-03", 110)]
        unknown_result = self.evaluate(unknown["decision_id"], "T+1", "2026-09-03T17:00:00+08:00", rows)
        hold_result = self.evaluate(hold["decision_id"], "T+1", "2026-09-03T17:00:00+08:00", rows)
        self.assertEqual(unknown_result["outcome_status"], "UNAVAILABLE")
        self.assertEqual(unknown_result["unavailable_reason"], "ANALYSIS_ONLY")
        self.assertEqual(hold_result["outcome_status"], "NOT_APPLICABLE")
        self.assertEqual(hold_result["unavailable_reason"], "HOLD_EXISTING_POSITION_CONTEXT_UNAVAILABLE")
        self.assertIsNone(hold_result.get("gross_return"))

    def test_immature_horizon_is_pending_and_mature_missing_price_is_unavailable(self) -> None:
        rows = [self.bar("2026-09-03", 101)]
        pending = self.evaluate("p202-outcome-long", "T+3", "2026-09-03T17:00:00+08:00", rows, horizon_matured=False)
        self.assertEqual(pending["outcome_status"], "PENDING")
        self.assertIsNone(pending.get("gross_return"))
        self.assertIsNone(pending.get("net_return"))

        decision = {**self.decision, "decision_id": "p202-missing-price"}
        self.store.record_decision(decision)
        missing = self.evaluate(decision["decision_id"], "T+1", "2026-09-03T17:00:00+08:00", [], horizon_matured=True)
        self.assertEqual(missing["outcome_status"], "UNAVAILABLE")
        self.assertEqual(missing["unavailable_reason"], "MISSING_FUTURE_MARKET_PRICE")
        self.assertIsNone(missing.get("gross_return"))

    def test_timestamp_integrity_rejects_nonlater_evaluation_and_future_row(self) -> None:
        invalid_eval = self.evaluate("p202-outcome-long", "T+1", "2026-09-02T09:00:00+08:00", [])
        self.assertEqual(invalid_eval["outcome_status"], "INVALID")
        future_source = {**self.decision, "decision_id": "p202-future-data-asof", "source_updated_at": "2026-09-02T09:01:00+08:00"}
        self.store.record_decision(future_source)
        invalid_source_time = self.evaluate(future_source["decision_id"], "T+1", "2026-09-03T17:00:00+08:00", [self.bar("2026-09-03", 110)])
        self.assertEqual(invalid_source_time["outcome_status"], "INVALID")
        decision = {**self.decision, "decision_id": "p202-early-observation"}
        self.store.record_decision(decision)
        early = self.bar("2026-09-03", 110)
        early["observed_at"] = "2026-09-02T08:59:00+08:00"
        invalid_row = self.evaluate(decision["decision_id"], "T+1", "2026-09-03T17:00:00+08:00", [early])
        self.assertEqual(invalid_row["outcome_status"], "INVALID")

    def test_multi_horizon_retry_and_conflicting_duplicate_are_controlled(self) -> None:
        rows = [self.bar("2026-09-03", 101), self.bar("2026-09-04", 102)]
        t1 = self.evaluate("p202-outcome-long", "T+1", "2026-09-04T17:00:00+08:00", rows)
        t2 = self.evaluate("p202-outcome-long", "T+2", "2026-09-04T17:00:00+08:00", rows)
        self.assertEqual([row["evaluation_horizon"] for row in self.store.list_decision_outcomes("p202-outcome-long")], ["T+1", "T+2"])
        self.store.record_decision_outcome("p202-outcome-long", "T+1", t1)
        with self.assertRaisesRegex(ValueError, "conflicting payload"):
            self.store.record_decision_outcome("p202-outcome-long", "T+1", {**t1, "gross_return": 999})
        self.assertEqual(self.store.get_decision_outcome("p202-outcome-long", "T+2")["gross_return"], t2["gross_return"])

    def test_outcome_write_preserves_decision_snapshot_and_numeric_fields(self) -> None:
        before = self.store.get_decision("p202-outcome-long")
        self.evaluate("p202-outcome-long", "T+1", "2026-09-03T17:00:00+08:00", [self.bar("2026-09-03", 110)])
        after = self.store.get_decision("p202-outcome-long")
        for key in ("input_snapshot", "input_snapshot_hash", "decision_output", "decisionState", "source_metadata"):
            self.assertEqual(after[key], before[key])
        for key in ("marketScore", "riskScore", "scenarioWeights", "riskClassification", "strategySuggestion"):
            self.assertEqual(after["decision_output"].get(key), before["decision_output"].get(key))

    def test_directional_return_is_not_options_strategy_pnl(self) -> None:
        options = {**self.decision, "decision_id": "p202-options-direction", "symbol": "TXO", "instrument": "TXO"}
        self.store.record_decision(options)
        result = self.evaluate(options["decision_id"], "T+1", "2026-09-03T17:00:00+08:00", [self.bar("2026-09-03", 110)])
        metadata = self.store.get_decision_outcome(options["decision_id"], "T+1")["outcome_metadata"]
        self.assertEqual(metadata["evaluationBasis"], "DIRECTIONAL_RETURN")
        self.assertIsNone(metadata["strategyReturn"])
        self.assertIsNone(result["net_return"])

    def test_api_read_path_round_trips_outcome_provenance_and_contract(self) -> None:
        result = self.evaluate("p202-outcome-long", "T+1", "2026-09-03T17:00:00+08:00", [self.bar("2026-09-03", 110)])
        flask_app = app.create_app({"TESTING": True}, derivatives_store=self.store)
        response = flask_app.test_client().get("/api/decision-ledger/p202-outcome-long")
        self.assertEqual(response.status_code, 200)
        outcome = response.get_json()["data"]["decision"]["outcomes"][0]
        self.assertEqual(outcome["outcomeStatus"], "EVALUATED")
        self.assertEqual(outcome["legacyStatus"], result["status"])
        self.assertEqual(outcome["evaluationBasis"], "DIRECTIONAL_RETURN")
        self.assertIsNone(outcome["strategyEvaluationBasis"])
        self.assertEqual(outcome["evaluationReference"]["price"], 110)
        self.assertEqual(outcome["provenance"]["outcome"]["provider"], "Yahoo")
        self.assertEqual(outcome["contractVersions"]["outcomeSchema"], "P2_02_OUTCOME_V1")

    def test_unversioned_available_status_is_not_promoted_to_evaluated(self) -> None:
        self.store.record_decision_outcome("p202-outcome-long", "T+1", {
            "evaluation_time": "2026-09-03T17:00:00+08:00",
            "status": "AVAILABLE",
            "gross_return": 0.01,
            "net_return": None,
            "target_hit": "NOT_APPLICABLE",
            "stop_hit": "NOT_APPLICABLE",
            "data_quality_status": "GOOD",
            "market_observations": [],
        })
        saved = self.store.get_decision_outcome("p202-outcome-long", "T+1")
        self.assertEqual(saved["status"], "AVAILABLE")
        self.assertEqual(saved["outcome_status"], "UNAVAILABLE")
        self.assertEqual(saved["legacy_status"], "AVAILABLE")
        from scripts import p204_score_bucket_performance as p204
        self.assertTrue(p204.outcome_status_metadata_mismatch(saved))
        self.assertNotEqual(p204.normalize_outcome_status(saved), "EVALUATED")

    def test_versioned_outcome_rejects_conflicting_raw_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "versioned outcome status must agree"):
            self.store.record_decision_outcome("p202-outcome-long", "T+1", {
                "evaluation_time": "2026-09-03T17:00:00+08:00",
                "status": "INVALID",
                "gross_return": 0.01,
                "target_hit": "NOT_APPLICABLE",
                "stop_hit": "NOT_APPLICABLE",
                "data_quality_status": "UNAVAILABLE",
                "market_observations": [],
                "outcome_metadata": {
                    "outcomeSchemaVersion": "P2_02_OUTCOME_V1",
                    "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
                    "outcomeStatus": "EVALUATED",
                },
            })

    def test_outcome_storage_reuses_existing_schema(self) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(decision_outcome)")}
        finally:
            connection.close()
        self.assertEqual(columns, {
            "decision_id", "evaluation_horizon", "evaluation_time", "status", "gross_return",
            "execution_cost", "net_return", "mfe", "mae", "target_hit", "stop_hit",
            "unavailable_reason", "data_quality_status", "market_observations_json", "cost_adjusted_result_json",
        })


if __name__ == "__main__":
    unittest.main()
