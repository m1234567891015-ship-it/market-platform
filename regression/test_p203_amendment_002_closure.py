"""P2-03 Amendment 002 contract and frozen historical-feasibility checks."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import patch

from derivatives.probability_forecast import (
    FEATURE_CONTRACT_VERSION,
    MIN_TRAINING_SAMPLES,
    TARGET_CONTRACT_VERSION,
    TARGET_HORIZON,
    fit_probability_forecast,
)
from regression.test_p2_03_probability_forecast import decision_fixture, outcome_fixture
from regression.test_p203_prospective_evidence_runner import decision_exists_for_market_session
from scripts import p203_roll_continuity_feasibility_audit as audit
from derivatives_store import DerivativesStore


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "regression" / "fixtures" / "p203"


class P203Amendment002ClosureTests(unittest.TestCase):
    def _frozen_fixture_hashes(self) -> dict[str, str]:
        v2 = audit.v2
        expected = {
            "docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md": v2.EXPECTED_HASHES["originalProtocol"],
            "docs/P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md": v2.EXPECTED_HASHES["amendment001"],
            "protocol/protocol_manifest.json": v2.EXPECTED_HASHES["originalManifest"],
            "protocol/effective_protocol_identity.json": v2.EXPECTED_HASHES["effectiveIdentity"],
            "protocol/protocol_amendment_001_manifest.json": v2.EXPECTED_HASHES["amendmentManifest"],
        }
        protocol_manifest = json.loads(
            (FIXTURE_ROOT / "protocol" / "protocol_manifest.json").read_text(encoding="utf-8")
        )
        for relative, digest in protocol_manifest["sourceV1R1Hashes"].items():
            expected[f"historical-v1r1/{relative}"] = digest
        for relative, digest in protocol_manifest["diagnosticHashes"].items():
            expected[f"diagnostics/{relative}"] = digest
        for relative, digest in v2.v1r1.EXPECTED_V1_FILE_HASHES.items():
            expected[f"historical-v1/{relative}"] = digest
        expected["historical-asof/taifex_tx_daily_normalized.json"] = audit.v2.v1r1.EXPECTED_OLD_DATA_SHA256
        return expected

    @contextmanager
    def _materialized_frozen_inputs(self, destination: Path):
        destination.mkdir(parents=True)
        shutil.copytree(FIXTURE_ROOT / "docs", destination / "docs")
        for fixture_name, temporary_name in (
            ("protocol", "p203-v2-protocol"),
            ("historical-v1r1", "p203-historical-research-v1r1"),
            ("diagnostics", "p203-v1r1-diagnostic"),
            ("historical-v1", "p203-historical-research-v1"),
        ):
            shutil.copytree(
                FIXTURE_ROOT / fixture_name,
                destination / ".tmp" / temporary_name,
            )
        v2 = audit.v2
        v1r1 = v2.v1r1
        protocol_dir = destination / ".tmp" / "p203-v2-protocol"
        input_dir = destination / ".tmp" / "p203-historical-research-v1r1"
        v1_dir = destination / ".tmp" / "p203-historical-research-v1"
        with ExitStack() as stack:
            for name, value in {
                "ROOT": destination,
                "PROTOCOL_PATH": destination / "docs" / "P2_03_RESEARCH_V2_PRE_REGISTRATION.md",
                "AMENDMENT_PATH": destination / "docs" / "P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md",
                "ORIGINAL_MANIFEST_PATH": protocol_dir / "protocol_manifest.json",
                "IDENTITY_PATH": protocol_dir / "effective_protocol_identity.json",
                "AMENDMENT_MANIFEST_PATH": protocol_dir / "protocol_amendment_001_manifest.json",
                "INPUT_DIR": input_dir,
                "INPUT_INVENTORY_PATH": input_dir / "raw_data_inventory.json",
                "SERIES_PATH": input_dir / "rebuilt_daily_series.csv",
                "SELECTION_TRACE_PATH": input_dir / "selection_trace.csv",
            }.items():
                stack.enter_context(patch.object(v2, name, value))
            stack.enter_context(patch.object(v1r1, "V1_DIR", v1_dir))
            stack.enter_context(patch.object(v1r1, "CONTRACT_PATH", v1_dir / "feature_contract.json"))
            yield destination

    def test_amendment_preserves_production_contract_and_closes_historical_gate(self) -> None:
        text = (ROOT / "docs" / "P2_03_PROTOCOL_AMENDMENT_002.md").read_text(encoding="utf-8")
        for required in (
            "P2_03_PROTOCOL_AMENDMENT_002",
            "HISTORICALLY INFEASIBLE UNDER CURRENT CONTRACT",
            "RESEARCH_ONLY / COMPLETE AS RESEARCH DIAGNOSTIC",
            "Production probability evidence shall be prospective",
            "P2_03_DERIVATIVES_SCORE_FEATURES_V1",
            "DIRECTIONAL_SUCCESS",
            "T+1 observed market session",
            "at least 30 eligible, matured prior labels and both target classes",
            "probabilityLabelAllowed=false",
            "NOT ESTABLISHED",
            "profitability",
            "AUC above 0.5",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertEqual(FEATURE_CONTRACT_VERSION, "P2_03_DERIVATIVES_SCORE_FEATURES_V1")
        self.assertEqual(TARGET_CONTRACT_VERSION, "P2_03_DIRECTIONAL_SUCCESS_V1")
        self.assertEqual(TARGET_HORIZON, "T+1")
        self.assertEqual(MIN_TRAINING_SAMPLES, 30)

    def test_original_protocol_and_amendment_001_remain_byte_identical(self) -> None:
        expected = self._frozen_fixture_hashes()
        actual_paths = {
            path.relative_to(FIXTURE_ROOT).as_posix()
            for path in FIXTURE_ROOT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(set(expected), actual_paths)
        for relative, digest in expected.items():
            with self.subTest(path=relative):
                actual = hashlib.sha256((FIXTURE_ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(digest, actual)

    def test_frozen_roll_feasibility_audit_reproduces_historical_capacity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p203-amendment-002-fixture-") as temporary:
            fixture_root = Path(temporary) / "clean-root"
            with self._materialized_frozen_inputs(fixture_root):
                result = audit.build_report()
        self.assertEqual(result["frozenInputs"]["selectedSessionCount"], 441)
        self.assertEqual(result["funnel"]["frozenSummary"]["maturedEligibleLabels"], 19)
        self.assertEqual(result["trainingCapacity"]["requiredPriorLabels"], 30)
        self.assertEqual(result["trainingCapacity"]["maximumForecastsUnderFrozenRule"], 0)
        self.assertEqual(result["trainingCapacity"]["maximumOosPairsUnderFrozenRule"], 0)
        self.assertEqual(result["contracts"]["runCount"], 23)
        self.assertEqual(len(result["contracts"]["transitions"]), 22)

    def test_cold_start_balanced_and_single_class_synthetic_gates(self) -> None:
        rows = []
        for index in range(40):
            positive = index % 2 == 0
            decision = decision_fixture(
                index,
                direction="LONG" if index % 4 < 2 else "SHORT",
                market_score=75 if positive else 25,
                risk_score=35 if positive else 70,
            )
            rows.append({"decision": decision, "outcome": outcome_fixture(decision, 0.01 if positive else -0.01)})
        current = decision_fixture(
            70, direction="LONG", decision_time="2026-10-20T09:00:00+08:00", market_score=68
        )
        statuses = [fit_probability_forecast(current, rows[:count])["status"] for count in range(30)]
        self.assertTrue(all(status == "INSUFFICIENT_TRAINING_HISTORY" for status in statuses))

        balanced = fit_probability_forecast(current, rows[:30])
        self.assertEqual(balanced["status"], "FORECAST_AVAILABLE")
        self.assertEqual(balanced["probabilityForecast"]["trainingSampleCount"], 30)
        self.assertEqual(balanced["probabilityForecast"]["trainingPositiveCount"], 15)
        self.assertEqual(balanced["probabilityForecast"]["trainingNegativeCount"], 15)
        self.assertNotEqual(balanced["probabilityForecast"]["value"], 0.68)

        one_class = []
        for index in range(30):
            decision = decision_fixture(index, direction="LONG")
            one_class.append({"decision": decision, "outcome": outcome_fixture(decision, 0.01)})
        rejected = fit_probability_forecast(current, one_class)
        self.assertEqual(rejected["status"], "INSUFFICIENT_TARGET_VARIATION")
        self.assertIsNone(rejected["probabilityForecast"])

    def test_isolated_ledger_duplicate_no_trade_and_long_short_cold_start(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p203-amendment-002-") as temp_dir:
            store = DerivativesStore(Path(temp_dir) / "isolated.sqlite3")
            store.initialize()

            def ledger_decision(decision_id: str, state: str) -> dict:
                snapshot = {"market": {"close": 100, "date": "2026-09-01"}}
                snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
                return {
                    "decision_id": decision_id, "symbol": "TX", "instrument": "TX",
                    "decision_time": "2026-09-02T09:00:00+08:00", "market_as_of": "2026-09-01",
                    "data_as_of": "2026-09-01T08:55:00+08:00", "strategy_id": "test-strategy",
                    "strategy_version": "test-strategy-v1", "model_version": "test-model-v1",
                    "input_snapshot_hash": hashlib.sha256(snapshot_json.encode()).hexdigest(),
                    "input_snapshot": snapshot, "reference_price": 100,
                    "evidence_score": 80, "data_quality_score": 75,
                    "executionDirection": state,
                    "executionDirectionReason": f"EXPLICIT_{state}_DECISION",
                    "executionDirectionContractVersion": "P1D_DIRECTION_V1",
                    "source_provenance": {"provider": "TAIFEX", "sourceRole": "PRIMARY"},
                    "decision_output": {"decisionState": state, "decisionEligible": True,
                                        "executionDirection": state, "marketScore": 60,
                                        "riskScore": 40, "evidenceScore": 80, "dataQualityScore": 75},
                }

            for direction in ("LONG", "SHORT"):
                decision = ledger_decision(f"p203-close-{direction.lower()}", direction)
                self.assertTrue(store.record_decision(decision))
                saved = store.get_decision(decision["decision_id"])
                cold_start = fit_probability_forecast(saved, [])
                self.assertEqual(cold_start["status"], "INSUFFICIENT_TRAINING_HISTORY")
                self.assertIsNone(cold_start["probabilityForecast"])

            before_duplicate = len(store.list_decisions(target_symbol="TX", limit=1000))
            self.assertIsNotNone(decision_exists_for_market_session(store, "2026-09-01"))
            self.assertEqual(len(store.list_decisions(target_symbol="TX", limit=1000)), before_duplicate)

            no_trade = ledger_decision("p203-close-no-trade", "UNAVAILABLE")
            no_trade["executionDirectionReason"] = "ANALYSIS_ONLY"
            no_trade["decision_output"].update({"decisionState": "NO_TRADE", "decisionEligible": False,
                                                  "executionDirection": "UNAVAILABLE",
                                                  "executionDirectionReason": "ANALYSIS_ONLY",
                                                  "reasonCodes": ["DATA_QUALITY_INSUFFICIENT"]})
            no_trade["executionDirection"] = "UNAVAILABLE"
            no_trade["executionDirectionReason"] = "ANALYSIS_ONLY"
            no_trade["data_quality_status"] = "FAILED"
            self.assertTrue(store.record_decision(no_trade))
            persisted = store.get_decision("p203-close-no-trade")
            self.assertEqual(persisted["decisionState"], "NO_TRADE")
            self.assertFalse(persisted["decisionEligible"])
            result = fit_probability_forecast(persisted, [])
            self.assertEqual(result["status"], "UNAVAILABLE_INELIGIBLE_DECISION")
            self.assertIsNone(result["probabilityForecast"])


if __name__ == "__main__":
    unittest.main()
