from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from derivatives_store import DerivativesStore
from derivatives import execution_costs
from derivatives.ai import build_unavailable_ai_analysis
from derivatives.analytics import build_decision_contract, enrich_futures_ai_decision, enrich_option_ai_decision


class DecisionOutcomeLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="p1d-ledger-")
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "ledger.sqlite3"
        self.store = DerivativesStore(self.db_path)
        self.store.initialize()
        self.snapshot = {"item": {"close": 100, "marketAsOf": "2026-09-01"}, "candles": []}
        canonical = json.dumps(self.snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        self.snapshot_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.decision = {
            "decision_id": "decision-fixed-001",
            "symbol": "TX",
            "instrument": "TX",
            "decision_time": "2026-09-02T09:00:00+08:00",
            "market_as_of": "2026-09-01",
            "strategy_id": "derivatives-decision-v1",
            "model_version": "rules-based-derivatives-v1",
            "strategy_version": "derivatives-decision-v1",
            "input_snapshot_hash": self.snapshot_hash,
            "input_snapshot": self.snapshot,
            "decision_output": {
                "target_price": 110,
                "stop_price": 95,
                "bias": "short-term bullish",
                "marketScore": 90,
                "riskScore": 10,
            },
            "executionDirection": "LONG",
            "executionDirectionReason": "EXPLICIT_LONG_DECISION",
            "executionDirectionContractVersion": "P1D_DIRECTION_V1",
            "evidence_score": 75,
            "data_quality_score": 88,
            "reference_price": 100,
            "execution_cost_assumptions": {"status": "UNAVAILABLE", "reason": "NO_DECISION_TIME_COST_CONTRACT"},
            "source_updated_at": "2026-09-01",
            "data_quality_status": "PARTIAL",
            "created_at": "2026-09-02T09:00:00+08:00",
        }

    def _count(self, table: str) -> int:
        connection = sqlite3.connect(self.db_path)
        try:
            return connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        finally:
            connection.close()

    def test_append_reconstruct_and_replay_are_immutable(self) -> None:
        self.assertTrue(self.store.record_decision(self.decision))
        self.assertFalse(self.store.record_decision(self.decision))
        replay = {
            **self.decision,
            "decision_time": "2026-09-02T10:00:00+08:00",
            "created_at": "2026-09-02T10:00:00+08:00",
        }
        self.assertFalse(self.store.record_decision(replay))
        saved = self.store.get_decision(self.decision["decision_id"])
        self.assertEqual(saved["input_snapshot"], self.snapshot)
        self.assertEqual(saved["input_snapshot_hash"], self.snapshot_hash)
        self.assertEqual(saved["model_version"], "rules-based-derivatives-v1")
        self.assertEqual(saved["strategy_version"], "derivatives-decision-v1")
        self.assertEqual(saved["evidence_score"], 75)
        self.assertEqual(saved["data_quality_score"], 88)
        self.assertEqual(saved["decision_time"], self.decision["decision_time"])
        self.assertEqual(saved["executionDirection"], "LONG")
        self.assertEqual(saved["executionDirectionStatus"], "AVAILABLE")
        self.assertEqual(saved["executionDirectionContractVersion"], "P1D_DIRECTION_V1")
        self.assertEqual(saved["execution_cost_assumptions"]["contractVersion"], "P0B_FUTURES_COST_V1")
        self.assertEqual(saved["decision_output"]["executionQuantity"], None)
        self.assertNotIn("predictive_confidence", saved)

    def test_ai_report_path_persists_decision_snapshot(self) -> None:
        analysis = {
            "decision_id": "decision-ai-path",
            "symbol": "TX",
            "decision_time": self.decision["decision_time"],
            "market_as_of": self.decision["market_as_of"],
            "strategy_version": self.decision["strategy_version"],
            "model_version": self.decision["model_version"],
            "input_snapshot_hash": self.snapshot_hash,
            "decision_output": self.decision["decision_output"],
            "executionDirection": "UNAVAILABLE",
            "executionDirectionReason": "ANALYSIS_ONLY",
            "executionDirectionContractVersion": "P1D_DIRECTION_V1",
            "evidenceScore": 75,
            "dataQualityScore": 88,
            "dataQualityStatus": "PARTIAL",
            "reasons": [],
        }
        self.store.record_ai_report(
            "TX", analysis, self.decision["created_at"], self.snapshot, reference_price=100
        )
        saved = self.store.get_decision("decision-ai-path")
        self.assertEqual(saved["input_snapshot"], self.snapshot)
        self.assertEqual(saved["reference_price"], 100)
        self.assertEqual(saved["execution_cost_assumptions"]["contractVersion"], "P0B_FUTURES_COST_V1")
        self.assertEqual(saved["executionDirection"], "UNAVAILABLE")

    def test_contract_keeps_direction_separate_from_bias_and_scores(self) -> None:
        inputs = {"item": {"close": 100}}
        unavailable = build_decision_contract(
            symbol="TX", input_snapshot=inputs,
            decision_output={"bias": "偏多", "marketScore": 99, "riskScore": 1},
            available_evidence=4, evidence_total=4,
        )
        self.assertEqual(unavailable["executionDirection"], "UNAVAILABLE")
        self.assertEqual(unavailable["executionDirectionReason"], "ANALYSIS_ONLY")
        self.assertEqual(unavailable["decision_output"]["executionDirection"], "UNAVAILABLE")

        explicit = build_decision_contract(
            symbol="TX", input_snapshot=inputs,
            decision_output={"bias": "區間震盪", "marketScore": 10, "riskScore": 99},
            available_evidence=4, evidence_total=4,
            execution_direction="LONG", execution_direction_reason="EXPLICIT_LONG_DECISION",
        )
        changed_copy = build_decision_contract(
            symbol="TX", input_snapshot=inputs,
            decision_output={"bias": "完全不同的分析標籤", "marketScore": 2, "riskScore": 70},
            available_evidence=4, evidence_total=4,
            execution_direction="LONG", execution_direction_reason="EXPLICIT_LONG_DECISION",
        )
        self.assertEqual(explicit["executionDirection"], "LONG")
        self.assertEqual(changed_copy["executionDirection"], "LONG")
        self.assertEqual(explicit["decision_id"], changed_copy["decision_id"])

    def test_current_futures_strategy_is_analysis_only(self) -> None:
        analysis = enrich_futures_ai_decision(
            {"target": "TX", "bias": "短線偏多"},
            {"symbol": "TX", "date": "2026-09-01", "pct": 2.0, "openInterest": 10, "volume": 20},
            [{"date": f"2026-08-{day:02d}", "open": 100, "high": 102, "low": 99, "close": 101} for day in range(1, 13)],
        )
        self.assertEqual(analysis["executionDirection"], "UNAVAILABLE")
        self.assertEqual(analysis["executionDirectionReason"], "ANALYSIS_ONLY")
        self.assertIn("可用小部位順勢", analysis["strategySuggestion"])

    def test_options_and_unavailable_data_never_emit_executable_direction(self) -> None:
        option_analysis = enrich_option_ai_decision(
            {"target": "TXO", "bias": "偏多但追價風險升高"},
            {"putCallRatio": 0.6}, [], 22000,
        )
        unavailable = build_unavailable_ai_analysis("TX", "provider unavailable")
        self.assertEqual(option_analysis["executionDirection"], "UNAVAILABLE")
        self.assertEqual(option_analysis["executionDirectionReason"], "NO_EXECUTABLE_POSITION_CONTRACT")
        self.assertEqual(unavailable["executionDirection"], "UNAVAILABLE")
        self.assertEqual(unavailable["executionDirectionReason"], "INSUFFICIENT_DECISION_DATA")

    def test_legacy_row_without_direction_reconstructs_unavailable(self) -> None:
        self.store.record_decision(self.decision)
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "UPDATE decision_ledger SET decision_output_json = ? WHERE decision_id = ?",
                (json.dumps({"bias": "短線偏多", "marketScore": 95}, ensure_ascii=False), self.decision["decision_id"]),
            )
            connection.commit()
        finally:
            connection.close()
        saved = self.store.get_decision(self.decision["decision_id"])
        self.assertEqual(saved["executionDirection"], "UNAVAILABLE")
        self.assertEqual(saved["executionDirectionReason"], "LEGACY_DIRECTION_UNAVAILABLE")

    def test_existing_schema_upgrade_is_additive(self) -> None:
        legacy_path = Path(self.temp_dir.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.execute(
                """CREATE TABLE ai_analysis_report (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, target_symbol TEXT NOT NULL,
                    bias TEXT, support_level REAL, resistance_level REAL, risk_level TEXT,
                    summary TEXT, created_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                "INSERT INTO ai_analysis_report(target_symbol, bias, created_at) VALUES ('TX', '區間震盪', '2026-09-01')"
            )
            connection.commit()
        finally:
            connection.close()
        upgraded = DerivativesStore(legacy_path)
        upgraded.initialize()
        connection = sqlite3.connect(legacy_path)
        try:
            report = connection.execute("SELECT target_symbol, bias FROM ai_analysis_report").fetchone()
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()
        self.assertEqual(report, ("TX", "區間震盪"))
        self.assertIn("decision_ledger", tables)
        self.assertIn("decision_outcome", tables)

    def test_conflicting_duplicate_id_does_not_overwrite(self) -> None:
        self.store.record_decision(self.decision)
        conflict = {
            **self.decision,
            "executionDirection": "SHORT",
            "executionDirectionReason": "EXPLICIT_SHORT_DECISION",
            "decision_output": {**self.decision["decision_output"], "executionDirection": "SHORT"},
        }
        with self.assertRaisesRegex(ValueError, "conflicting payload"):
            self.store.record_decision(conflict)
        self.assertEqual(self.store.get_decision(self.decision["decision_id"])["executionDirection"], "LONG")
        self.assertEqual(self._count("decision_ledger"), 1)

    def test_t_plus_n_evaluation_is_chronological_and_separate(self) -> None:
        self.store.record_decision(self.decision)
        before = self.store.get_decision(self.decision["decision_id"])
        result = self.store.evaluate_decision_outcome(
            self.decision["decision_id"],
            "T+2",
            "2026-09-04T16:00:00+08:00",
            [
                {"date": "2026-09-05", "observed_at": "2026-09-05T16:00:00+08:00", "high": 999, "low": 1, "close": 999},
                {"date": "2026-08-31", "high": 999, "low": 1, "close": 999},
                {"date": "2026-09-04", "observed_at": "2026-09-04T16:00:00+08:00", "high": 112, "low": 99, "close": 106},
                {"date": "2026-09-03", "observed_at": "2026-09-03T16:00:00+08:00", "high": 108, "low": 95, "close": 102},
            ],
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertAlmostEqual(result["gross_return"], 0.06)
        self.assertAlmostEqual(result["mfe"], 0.12)
        self.assertAlmostEqual(result["mae"], -0.05)
        self.assertEqual(result["target_hit"], "HIT")
        self.assertEqual(result["stop_hit"], "HIT")
        self.assertEqual(result["data_quality_status"], "PARTIAL")
        self.assertIsNone(result["net_return"])
        self.assertEqual(result["unavailable_reason"], "MISSING_OR_INVALID_CONTRACT_QUANTITY")
        self.assertEqual(result["costAdjustedResult"]["status"], "UNAVAILABLE")
        self.assertEqual([row["date"] for row in result["market_observations"]], ["2026-09-03", "2026-09-04"])
        self.assertEqual(self.store.get_decision(self.decision["decision_id"]), before)
        self.assertEqual(self._count("decision_outcome"), 1)

        self.store.record_decision_outcome(self.decision["decision_id"], "T+2", result)
        self.assertEqual(self._count("decision_outcome"), 1)
        self.assertEqual([row["evaluation_horizon"] for row in self.store.list_decision_outcomes(self.decision["decision_id"])], ["T+2"])
        repeated = self.store.evaluate_decision_outcome(
            self.decision["decision_id"], "T+2", "2026-09-04T16:00:00+08:00",
            [
                {"date": "2026-09-03", "observed_at": "2026-09-03T16:00:00+08:00", "high": 108, "low": 95, "close": 102},
                {"date": "2026-09-04", "observed_at": "2026-09-04T16:00:00+08:00", "high": 112, "low": 99, "close": 106},
            ],
        )
        self.assertEqual(repeated, result)

    def test_short_mfe_mae_and_no_position_have_no_hypothetical_trade(self) -> None:
        short = {
            **self.decision,
            "decision_id": "decision-short",
            "executionDirection": "SHORT",
            "executionDirectionReason": "EXPLICIT_SHORT_DECISION",
            "decision_output": {"target_price": 90, "stop_price": 110, "bias": "any"},
        }
        self.store.record_decision(short)
        short_result = self.store.evaluate_decision_outcome(
            short["decision_id"], "T+1", "2026-09-03T16:00:00+08:00",
            [{"date": "2026-09-03", "observed_at": "2026-09-03T16:00:00+08:00", "high": 105, "low": 90, "close": 95}],
        )
        self.assertEqual(self.store.get_decision(short["decision_id"])["executionDirection"], "SHORT")
        self.assertAlmostEqual(short_result["gross_return"], (100 - 95) / 100)
        self.assertAlmostEqual(short_result["mfe"], 100 / 90 - 1)
        self.assertAlmostEqual(short_result["mae"], 100 / 105 - 1)
        self.assertEqual(short_result["target_hit"], "HIT")
        self.assertEqual(short_result["stop_hit"], "NOT_HIT")

        flat = {
            **self.decision,
            "decision_id": "decision-flat",
            "executionDirection": "NO_POSITION",
            "executionDirectionReason": "EXPLICIT_NO_POSITION_DECISION",
        }
        self.store.record_decision(flat)
        flat_result = self.store.evaluate_decision_outcome(
            flat["decision_id"], "T+1", "2026-09-03T16:00:00+08:00", []
        )
        self.assertEqual(self.store.get_decision(flat["decision_id"])["executionDirection"], "NO_POSITION")
        self.assertEqual(flat_result["status"], "NOT_APPLICABLE")
        self.assertIsNone(flat_result["gross_return"])
        self.assertIsNone(flat_result["net_return"])

    def test_missing_future_price_is_unavailable_not_zero(self) -> None:
        self.store.record_decision(self.decision)
        result = self.store.evaluate_decision_outcome(
            self.decision["decision_id"], "T+1", "2026-09-04T16:00:00+08:00", []
        )
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["unavailable_reason"], "MISSING_FUTURE_MARKET_PRICE")
        self.assertIsNone(result.get("gross_return"))
        self.assertIsNone(self.store.get_decision_outcome(self.decision["decision_id"], "T+1")["net_return"])

    def test_cost_adjusted_long_and_short_use_frozen_snapshot_and_quantity(self) -> None:
        long = {**self.decision, "decision_id": "decision-cost-long", "executionQuantity": 2}
        self.store.record_decision(long)
        saved_before = self.store.get_decision(long["decision_id"])
        result = self.store.evaluate_decision_outcome(
            long["decision_id"], "T+1", "2026-09-03T16:00:00+08:00",
            [{"date": "2026-09-03", "observed_at": "2026-09-03T16:00:00+08:00", "high": 112, "low": 99, "close": 110}],
        )
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertAlmostEqual(result["costAdjustedResult"]["grossPnl"], 4000)
        self.assertAlmostEqual(result["costAdjustedResult"]["totalCost"], 981.68)
        self.assertAlmostEqual(result["costAdjustedResult"]["netPnl"], 3018.32)
        self.assertAlmostEqual(result["costAdjustedResult"]["costAdjustedReturnPct"], result["net_return"] * 100)
        self.assertAlmostEqual(result["gross_return"] * 100 - result["costAdjustedResult"]["normalizedCostPct"], result["net_return"] * 100)
        self.assertAlmostEqual(result["mfe"], 0.12)
        # A later current-config change is deliberately irrelevant: evaluator
        # receives only the decision's frozen assumptions.
        with patch.dict(execution_costs.CONTRACTS["TX"], {"brokerCommissionPerContract": 500}):
            drifted = self.store.evaluate_decision_outcome(
                long["decision_id"], "T+1", "2026-09-03T16:00:00+08:00",
                [{"date": "2026-09-03", "observed_at": "2026-09-03T16:00:00+08:00", "high": 112, "low": 99, "close": 110}],
            )
        self.assertEqual(drifted["costAdjustedResult"]["commissionCost"], 180)
        self.assertEqual(self.store.get_decision(long["decision_id"])["execution_cost_assumptions"]["brokerCommissionPerContract"], 45)
        self.assertAlmostEqual(self.store.get_decision_outcome(long["decision_id"], "T+1")["cost_adjusted_result"]["totalCost"], 981.68)

        short = {
            **self.decision, "decision_id": "decision-cost-short", "executionQuantity": 2,
            "executionDirection": "SHORT", "executionDirectionReason": "EXPLICIT_SHORT_DECISION",
            "decision_output": {**self.decision["decision_output"], "executionDirection": "SHORT"},
        }
        self.store.record_decision(short)
        short_result = self.store.evaluate_decision_outcome(
            short["decision_id"], "T+1", "2026-09-03T16:00:00+08:00",
            [{"date": "2026-09-03", "observed_at": "2026-09-03T16:00:00+08:00", "high": 101, "low": 88, "close": 90}],
        )
        self.assertEqual(short_result["status"], "AVAILABLE")
        self.assertAlmostEqual(short_result["costAdjustedResult"]["grossPnl"], 4000)
        self.assertAlmostEqual(short_result["costAdjustedResult"]["netPnl"], 3018.48)
        self.assertAlmostEqual(short_result["gross_return"] * 100 - short_result["costAdjustedResult"]["normalizedCostPct"], short_result["net_return"] * 100)

    def test_legacy_cost_contract_is_not_backfilled_and_quantity_is_validated(self) -> None:
        legacy = {**self.decision, "decision_id": "decision-legacy-cost", "executionQuantity": 1}
        self.store.record_decision(legacy)
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute("UPDATE decision_ledger SET execution_cost_assumptions_json = ? WHERE decision_id = ?", ("{}", legacy["decision_id"]))
            connection.commit()
        finally:
            connection.close()
        result = self.store.evaluate_decision_outcome(
            legacy["decision_id"], "T+1", "2026-09-03T16:00:00+08:00",
            [{"date": "2026-09-03", "observed_at": "2026-09-03T16:00:00+08:00", "high": 102, "low": 98, "close": 101}],
        )
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["unavailable_reason"], "LEGACY_DECISION_MISSING_P0B_COST_CONTRACT")
        self.assertAlmostEqual(result["gross_return"], 0.01)
        self.assertIsNone(result["net_return"])
        invalid = {**self.decision, "decision_id": "decision-invalid-quantity", "executionQuantity": 0}
        with self.assertRaisesRegex(ValueError, "executionQuantity"):
            self.store.record_decision(invalid)

    def test_directionless_existing_decision_fails_closed(self) -> None:
        decision = {
            **self.decision,
            "decision_id": "decision-directionless",
            "executionDirection": "UNAVAILABLE",
            "executionDirectionReason": "ANALYSIS_ONLY",
            "decision_output": {"bias": "偏多", "marketScore": 99, "riskScore": 1, "direction": "LONG"},
        }
        self.store.record_decision(decision)
        result = self.store.evaluate_decision_outcome(
            decision["decision_id"], "T+1", "2026-09-03T16:00:00+08:00",
            [{"date": "2026-09-03", "observed_at": "2026-09-03T16:00:00+08:00", "high": 102, "low": 98, "close": 101}],
        )
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["unavailable_reason"], "ANALYSIS_ONLY")

    def test_invalid_horizon_rejected(self) -> None:
        self.store.record_decision(self.decision)
        with self.assertRaisesRegex(ValueError, r"T\+N"):
            self.store.evaluate_decision_outcome(self.decision["decision_id"], "5D", "2026-09-04", [])


if __name__ == "__main__":
    unittest.main()
