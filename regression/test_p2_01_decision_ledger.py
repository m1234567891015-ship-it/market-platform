"""P2-01 persistence and read-contract checks for the existing Decision Ledger."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from derivatives_store import DECISION_LEDGER_SCHEMA_VERSION, DerivativesStore


class P201DecisionLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="p201-ledger-")
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "ledger.sqlite3"
        self.store = DerivativesStore(self.db_path)
        self.store.initialize()
        self.snapshot = {
            "market": {"symbol": "TXO", "marketAsOf": "2026-09-30", "dataAsOf": "2026-09-30T05:00:00Z"},
            "scenarioWeights": {"bullish": 58, "neutral": 27, "bearish": 15},
        }
        snapshot_json = json.dumps(self.snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        self.decision = {
            "decision_id": "sha256:fixture-p201-no-trade",
            "symbol": "TXO",
            "instrument": "TXO",
            "decision_time": "2026-10-01T09:00:00+08:00",
            "market_as_of": "2026-09-30",
            "data_as_of": "2026-09-30T05:00:00Z",
            "strategy_id": "derivatives-rules",
            "model_version": "derivatives-model-v1",
            "strategy_version": "derivatives-strategy-v1",
            "input_snapshot_hash": hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest(),
            "input_snapshot": self.snapshot,
            "decision_output": {
                "decisionState": "NO_TRADE",
                "decisionEligible": False,
                "reasonCodes": ["INSUFFICIENT_EVIDENCE"],
                "reasonDetails": ["Decision-time evidence was incomplete."],
                "strategyBias": "偏多",
                "strategySuggestion": "等待更多資料",
                "scenarioWeights": self.snapshot["scenarioWeights"],
                "scenarioSemanticStatus": "HEURISTIC_SCENARIO_WEIGHT",
                "calibrationStatus": "UNCALIBRATED",
                "probabilityLabelAllowed": False,
                "probabilities": self.snapshot["scenarioWeights"],
                "probabilitiesDeprecated": True,
                "riskClassification": {"type": "MARKET_RISK", "score": 72, "status": "KNOWN"},
                "riskClassifications": [
                    {"type": "MARKET_RISK", "score": 72, "status": "KNOWN"},
                    {"type": "STRATEGY_RISK", "score": 48, "status": "KNOWN"},
                ],
                "marketScore": 63,
                "riskScore": 72,
                "valueAtRisk": 0.04,
                "expectedShortfall": 0.06,
                "decisionStateContractVersion": "P1_04_NO_TRADE_V1",
                "executionDirection": "UNAVAILABLE",
                "executionDirectionContractVersion": "P1D_DIRECTION_V1",
            },
            "executionDirection": "UNAVAILABLE",
            "executionDirectionReason": "ANALYSIS_ONLY",
            "executionDirectionContractVersion": "P1D_DIRECTION_V1",
            "data_quality_status": "PARTIAL",
            "data_quality_dimensions": {"freshness": "UNKNOWN", "providerHealth": "KNOWN_BAD"},
            "quality_coverage": {"known": 3, "total": 5},
            "data_quality_dimension_status": {"freshness": "UNKNOWN", "providerHealth": "KNOWN_BAD"},
            "source_updated_at": "2026-09-30T05:00:00Z",
            "source_provenance": {
                "roles": ["TAIFEX_PRIMARY", "YAHOO_SUPPLEMENT"],
                "fields": {"openInterest": "YAHOO_SUPPLEMENT", "chain": "TAIFEX_PRIMARY"},
            },
            "evidence_score": 63,
            "data_quality_score": 55,
            "reference_price": 22000,
            "created_at": "2026-10-01T09:00:02+08:00",
        }

    def test_full_snapshot_round_trip_preserves_p1_context_and_versions(self) -> None:
        self.assertTrue(self.store.record_decision(self.decision))
        saved = self.store.get_decision(self.decision["decision_id"])

        self.assertEqual(saved["decision_schema_version"], DECISION_LEDGER_SCHEMA_VERSION)
        self.assertEqual(saved["snapshot_type"], "RECORDED_DECISION_SNAPSHOT")
        self.assertEqual(saved["decision_created_at"], self.decision["decision_time"])
        self.assertEqual(saved["market_as_of"], self.decision["market_as_of"])
        self.assertEqual(saved["data_as_of"], self.decision["data_as_of"])
        self.assertEqual(saved["created_at"], self.decision["created_at"])
        self.assertEqual(saved["decisionState"], "NO_TRADE")
        self.assertFalse(saved["decisionEligible"])
        self.assertEqual(saved["reasonCodes"], ["INSUFFICIENT_EVIDENCE"])
        self.assertEqual(saved["reasonDetails"], ["Decision-time evidence was incomplete."])
        self.assertEqual(saved["decision_output"]["scenarioWeights"], self.snapshot["scenarioWeights"])
        self.assertEqual(saved["decision_output"]["scenarioSemanticStatus"], "HEURISTIC_SCENARIO_WEIGHT")
        self.assertFalse(saved["decision_output"]["probabilityLabelAllowed"])
        self.assertTrue(saved["decision_output"]["probabilitiesDeprecated"])
        self.assertEqual(
            [item["type"] for item in saved["decision_output"]["riskClassifications"]],
            ["MARKET_RISK", "STRATEGY_RISK"],
        )
        self.assertEqual(saved["source_metadata"]["source_provenance"], self.decision["source_provenance"])
        self.assertEqual(saved["source_metadata"]["quality_coverage"], self.decision["quality_coverage"])
        self.assertEqual(saved["contract_versions"], {
            "decisionState": "P1_04_NO_TRADE_V1",
            "executionDirection": "P1D_DIRECTION_V1",
        })

    def test_all_canonical_decision_states_can_be_recorded(self) -> None:
        cases = (
            ("LONG", "LONG", "EXPLICIT_LONG_DECISION", [], True),
            ("SHORT", "SHORT", "EXPLICIT_SHORT_DECISION", [], True),
            ("HOLD_EXISTING", "UNAVAILABLE", "ANALYSIS_ONLY", [], False),
            ("NO_TRADE", "UNAVAILABLE", "ANALYSIS_ONLY", ["INSUFFICIENT_EVIDENCE"], False),
            ("UNKNOWN", "UNAVAILABLE", "ANALYSIS_ONLY", ["UNKNOWN"], None),
        )
        for index, (state, direction, direction_reason, reason_codes, eligible) in enumerate(cases):
            with self.subTest(state=state):
                decision = {
                    **self.decision,
                    "decision_id": f"state-fixture-{index}",
                    "executionDirection": direction,
                    "executionDirectionReason": direction_reason,
                    "decision_output": {
                        **self.decision["decision_output"],
                        "decisionState": state,
                        "decisionEligible": eligible,
                        "reasonCodes": reason_codes,
                        "executionDirection": direction,
                    },
                }
                self.assertTrue(self.store.record_decision(decision))
                saved = self.store.get_decision(decision["decision_id"])
                self.assertEqual(saved["decisionState"], state)
                self.assertEqual(saved["decisionEligible"], eligible)
                self.assertEqual(saved["reasonCodes"], reason_codes)

    def test_unknown_times_remain_null_and_ledger_write_time_is_separate(self) -> None:
        decision = {
            **self.decision,
            "decision_id": "unknown-times",
            "market_as_of": None,
            "data_as_of": None,
            "source_updated_at": None,
            "created_at": None,
        }
        self.assertTrue(self.store.record_decision(decision))
        saved = self.store.get_decision(decision["decision_id"])
        self.assertIsNone(saved["market_as_of"])
        self.assertIsNone(saved["data_as_of"])
        self.assertEqual(saved["decision_created_at"], decision["decision_time"])
        self.assertNotEqual(saved["created_at"], decision["decision_time"])

    def test_canonical_write_path_freezes_final_strategy_and_explicit_unknown_data_time(self) -> None:
        analysis = {
            "decision_id": "ai-analysis-final-output",
            "symbol": "TXO",
            "decision_time": self.decision["decision_time"],
            "market_as_of": self.decision["market_as_of"],
            "dataAsOf": None,
            "source_updated_at": "2026-09-30T05:00:00Z",
            "model_version": self.decision["model_version"],
            "strategy_version": self.decision["strategy_version"],
            "input_snapshot_hash": self.decision["input_snapshot_hash"],
            "decision_output": {"decisionState": "UNKNOWN", "reasonCodes": ["UNKNOWN"]},
            "decisionState": "UNKNOWN",
            "decisionEligible": None,
            "reasonCodes": ["UNKNOWN"],
            "reasonDetails": ["Eligibility remains unknown."],
            "strategySuggestion": "等待資料，不建立新部位。",
            "strategyBias": "偏多",
            "scenarioWeights": {"bullish": 50, "bearish": 50},
            "scenarioSemanticStatus": "HEURISTIC_SCENARIO_WEIGHT",
            "calibrationStatus": "UNCALIBRATED",
            "probabilityLabelAllowed": False,
            "riskClassifications": [{"type": "MARKET_RISK", "score": 50}],
            "dataQualityStatus": "PARTIAL",
            "qualityCoverage": 60,
            "sourceProvenance": {"roles": ["TAIFEX_PRIMARY"]},
        }
        self.store.record_ai_report(
            "TXO", analysis, "2026-10-01T09:00:02+08:00",
            input_snapshot=self.snapshot,
        )
        saved = self.store.get_decision("ai-analysis-final-output")
        self.assertEqual(saved["data_as_of"], None)
        self.assertEqual(saved["source_metadata"]["source_updated_at"], analysis["source_updated_at"])
        self.assertEqual(saved["decision_output"]["strategySuggestion"], analysis["strategySuggestion"])
        self.assertEqual(saved["decision_output"]["strategyBias"], analysis["strategyBias"])
        self.assertEqual(saved["decision_output"]["scenarioWeights"], analysis["scenarioWeights"])
        self.assertEqual(saved["decision_output"]["riskClassifications"], analysis["riskClassifications"])

    def test_retry_is_idempotent_but_distinct_decisions_for_same_symbol_are_kept(self) -> None:
        self.assertTrue(self.store.record_decision(self.decision))
        self.assertFalse(self.store.record_decision(self.decision))
        second = {
            **self.decision,
            "decision_id": "same-symbol-distinct-decision",
            "market_as_of": "2026-10-01",
            "input_snapshot": {"market": {"symbol": "TXO", "marketAsOf": "2026-10-01"}},
        }
        canonical = json.dumps(second["input_snapshot"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        second["input_snapshot_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertTrue(self.store.record_decision(second))
        self.assertEqual(len(self.store.list_decisions(target_symbol="TXO")), 2)
        conflict = {**self.decision, "decision_output": {**self.decision["decision_output"], "riskScore": 1}}
        with self.assertRaisesRegex(ValueError, "conflicting payload"):
            self.store.record_decision(conflict)

    def test_snapshot_is_stable_when_current_analysis_and_outcomes_change(self) -> None:
        self.store.record_decision(self.decision)
        before = self.store.get_decision(self.decision["decision_id"])
        current_snapshot = {"market": {"symbol": "TXO", "marketAsOf": "2026-10-02", "dataAsOf": "2026-10-02T05:00:00Z"}}
        current_snapshot_json = json.dumps(current_snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        current_decision = {
            **self.decision,
            "decision_id": "later-current-analysis",
            "decision_time": "2026-10-02T09:00:00+08:00",
            "market_as_of": "2026-10-02",
            "data_as_of": "2026-10-02T05:00:00Z",
            "source_updated_at": "2026-10-02T05:00:00Z",
            "input_snapshot": current_snapshot,
            "input_snapshot_hash": hashlib.sha256(current_snapshot_json.encode("utf-8")).hexdigest(),
            "created_at": "2026-10-02T09:00:02+08:00",
            "decision_output": {
                **self.decision["decision_output"],
                "riskScore": 99,
                "scenarioWeights": {"bearish": 100},
                "dataQualityStatus": "FAILED",
            },
        }
        self.assertTrue(self.store.record_decision(current_decision))
        self.store.record_decision_outcome(self.decision["decision_id"], "T+1", {
            "evaluation_time": "2026-10-02T16:00:00+08:00",
            "status": "AVAILABLE",
            "gross_return": 0.01,
            "net_return": 0.009,
            "target_hit": "NOT_HIT",
            "stop_hit": "NOT_HIT",
            "data_quality_status": "GOOD",
            "market_observations": [{"date": "2026-10-02", "close": 22220}],
        })
        after = self.store.get_decision(self.decision["decision_id"])
        self.assertEqual(after, before)
        self.assertEqual(self.store.get_decision(current_decision["decision_id"])["decision_output"]["riskScore"], 99)

    def test_ledger_api_returns_recorded_snapshot_and_not_current_analysis(self) -> None:
        self.store.record_decision(self.decision)
        flask_app = app.create_app({"TESTING": True}, derivatives_store=self.store)
        response = flask_app.test_client().get(f"/api/decision-ledger/{self.decision['decision_id']}")
        self.assertEqual(response.status_code, 200)
        decision = response.get_json()["data"]["decision"]
        self.assertEqual(decision["snapshotType"], "RECORDED_DECISION_SNAPSHOT")
        self.assertEqual(decision["decisionId"], self.decision["decision_id"])
        self.assertEqual(decision["decisionSchemaVersion"], DECISION_LEDGER_SCHEMA_VERSION)
        self.assertEqual(decision["decisionState"], "NO_TRADE")
        self.assertEqual(decision["reasonCodes"], ["INSUFFICIENT_EVIDENCE"])
        self.assertEqual(decision["reasonDetails"], ["Decision-time evidence was incomplete."])
        self.assertEqual(decision["timestamps"], {
            "decisionCreatedAt": self.decision["decision_time"],
            "marketAsOf": self.decision["market_as_of"],
            "dataAsOf": self.decision["data_as_of"],
            "ledgerRecordedAt": self.decision["created_at"],
        })
        self.assertEqual(decision["scenarioSnapshot"]["scenarioWeights"], self.snapshot["scenarioWeights"])
        self.assertFalse(decision["scenarioSnapshot"]["probabilityLabelAllowed"])
        self.assertEqual(decision["riskClassifications"][1]["type"], "STRATEGY_RISK")
        self.assertEqual(decision["sourceProvenance"], self.decision["source_provenance"])
        self.assertEqual(decision["dataQuality"]["status"], "PARTIAL")
        self.assertEqual(decision["dataQuality"]["coverage"], self.decision["quality_coverage"])
        self.assertEqual(decision["dataQuality"]["dimensions"], self.decision["data_quality_dimensions"])
        self.assertEqual(decision["contractVersions"]["decisionState"], "P1_04_NO_TRADE_V1")
        self.assertNotIn("currentMarketAnalysis", decision)

    def test_ledger_api_unknown_id_returns_not_found(self) -> None:
        flask_app = app.create_app({"TESTING": True}, derivatives_store=self.store)
        response = flask_app.test_client().get("/api/decision-ledger/missing-id")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error_code"], "DECISION_NOT_FOUND")

    def test_analysis_api_write_to_ledger_and_read_api_round_trip(self) -> None:
        flask_app = app.create_app({"TESTING": True}, derivatives_store=self.store)
        client = flask_app.test_client()
        with patch("routes_derivatives.fetch_txo_option_chain", return_value={"error": "provider unavailable"}):
            analysis_response = client.get("/api/ai-analysis?target=TXO&source=taifex")
            retry_response = client.get("/api/ai-analysis?target=TXO&source=taifex")
        self.assertEqual(analysis_response.status_code, 200)
        analysis = analysis_response.get_json()["data"]
        retry = retry_response.get_json()["data"]
        self.assertEqual(analysis["decisionState"], "NO_TRADE")
        self.assertEqual(retry["decision_id"], analysis["decision_id"])
        self.assertEqual(len(self.store.list_decisions(target_symbol="TXO")), 1)

        ledger_response = client.get(f"/api/decision-ledger/{analysis['decision_id']}")
        self.assertEqual(ledger_response.status_code, 200)
        saved = ledger_response.get_json()["data"]["decision"]
        self.assertEqual(saved["decisionId"], analysis["decision_id"])
        self.assertEqual(saved["decisionState"], analysis["decisionState"])
        self.assertEqual(saved["decisionEligible"], analysis["decisionEligible"])
        self.assertEqual(saved["reasonCodes"], analysis["reasonCodes"])
        self.assertEqual(saved["dataQuality"]["status"], analysis["dataQualityStatus"])

    def test_schema_version_is_json_metadata_without_database_migration(self) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(decision_ledger)")}
        finally:
            connection.close()
        self.assertNotIn("decision_schema_version", columns)
        self.store.record_decision(self.decision)
        saved = self.store.get_decision(self.decision["decision_id"])
        self.assertEqual(saved["source_metadata"]["ledger_metadata"]["decisionSchemaVersion"], DECISION_LEDGER_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
