"""P2-03 probability forecast target, chronology, model, and Ledger guards."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import app
import routes_derivatives
from derivatives.analytics import build_decision_contract
from derivatives.probability_forecast import (
    FEATURE_CONTRACT_VERSION,
    TARGET_CONTRACT_VERSION,
    TARGET_HORIZON,
    derive_directional_target,
    fit_probability_forecast,
    valid_oos_pair,
)
from derivatives_store import DerivativesStore


def decision_fixture(
    index: int = 0,
    *,
    direction: str = "LONG",
    decision_time: str | None = None,
    market_score: float = 60,
    risk_score: float = 40,
    evidence_score: float = 80,
    data_quality_score: float = 75,
) -> dict:
    when = decision_time or (datetime(2026, 9, 1, 9) + timedelta(days=index)).isoformat() + "+08:00"
    date_text = when[:10]
    return {
        "decision_id": f"p203-fixture-{index}",
        "decision_time": when,
        "market_as_of": date_text,
        "data_as_of": f"{date_text}T08:55:00+08:00",
        "decisionState": direction,
        "decisionEligible": True,
        "executionDirection": direction,
        "evidence_score": evidence_score,
        "data_quality_score": data_quality_score,
        "decision_output": {
            "decisionState": direction,
            "decisionEligible": True,
            "executionDirection": direction,
            "marketScore": market_score,
            "riskScore": risk_score,
            "scenarioWeights": {"up": 0.7, "down": 0.3},
        },
    }


def outcome_fixture(decision: dict, aligned_return: float, *, horizon: str = TARGET_HORIZON, status: str = "EVALUATED") -> dict:
    decision_dt = datetime.fromisoformat(decision["decision_time"])
    evaluated_at = decision_dt + timedelta(hours=8)
    return {
        "decision_id": decision["decision_id"],
        "evaluation_horizon": horizon,
        "evaluation_time": evaluated_at.isoformat(),
        "status": "AVAILABLE" if status == "EVALUATED" else status,
        "outcome_status": status,
        "outcome_metadata": {
            "outcomeStatus": status,
            "horizon": horizon,
            "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
            "evaluationBasis": "DIRECTIONAL_RETURN",
            "decisionAlignedReturn": aligned_return,
            "timestamps": {"evaluatedAt": evaluated_at.isoformat()},
        },
    }


class P203ProbabilityForecastTests(unittest.TestCase):
    def test_target_contract_long_short_flat_and_ineligible_states(self) -> None:
        long = decision_fixture(1, direction="LONG")
        self.assertEqual(derive_directional_target(long, outcome_fixture(long, 0.02))["value"], 1)
        self.assertEqual(derive_directional_target(long, outcome_fixture(long, -0.02))["value"], 0)

        short = decision_fixture(2, direction="SHORT")
        self.assertEqual(derive_directional_target(short, outcome_fixture(short, 0.02))["value"], 1)
        self.assertEqual(derive_directional_target(short, outcome_fixture(short, -0.02))["value"], 0)
        self.assertEqual(derive_directional_target(long, outcome_fixture(long, 0))["status"], "EXCLUDED_FLAT")

        for state in ("NO_TRADE", "HOLD_EXISTING", "UNKNOWN"):
            excluded = decision_fixture(3, direction=state)
            excluded["decisionEligible"] = False
            excluded["decision_output"]["decisionEligible"] = False
            self.assertFalse(derive_directional_target(excluded, outcome_fixture(excluded, 0.1))["eligible"])

        for status in ("PENDING", "NOT_APPLICABLE", "UNAVAILABLE", "INVALID"):
            with self.subTest(outcome_status=status):
                self.assertEqual(
                    derive_directional_target(long, outcome_fixture(long, 0.1, status=status))["status"],
                    f"EXCLUDED_{status}",
                )
        self.assertEqual(derive_directional_target(long, outcome_fixture(long, 0.1, horizon="T+5"))["status"], "EXCLUDED_HORIZON_MISMATCH")
        wrong_basis = outcome_fixture(long, 0.1)
        wrong_basis["outcome_metadata"]["evaluationBasis"] = "STRATEGY_RETURN"
        self.assertEqual(derive_directional_target(long, wrong_basis)["status"], "EXCLUDED_EVALUATION_BASIS")

    def test_feature_contract_rejects_future_or_missing_time_evidence(self) -> None:
        future = decision_fixture(1, decision_time="2026-09-01T09:00:00+08:00")
        future["data_as_of"] = "2026-09-01T09:01:00+08:00"
        self.assertIsNone(fit_probability_forecast(future, []) ["probabilityForecast"])

        bad_market_date = decision_fixture(2, decision_time="2026-09-01T09:00:00+08:00")
        bad_market_date["market_as_of"] = "2026-09-02"
        self.assertEqual(fit_probability_forecast(bad_market_date, [])["status"], "UNAVAILABLE_INELIGIBLE_DECISION")

    def test_model_is_deterministic_probability_and_ignores_future_rows(self) -> None:
        rows = []
        for index in range(40):
            success = index % 2 == 0
            direction = "LONG" if index % 4 < 2 else "SHORT"
            prior = decision_fixture(
                index,
                direction=direction,
                market_score=75 if success else 25,
                risk_score=35 if success else 70,
            )
            rows.append({"decision": prior, "outcome": outcome_fixture(prior, 0.01 if success else -0.01)})

        current = decision_fixture(
            70,
            direction="LONG",
            decision_time="2026-10-01T09:00:00+08:00",
            market_score=68,
            risk_score=42,
        )
        first = fit_probability_forecast(current, rows)
        forecast = first["probabilityForecast"]
        self.assertIsNotNone(forecast)
        self.assertGreaterEqual(forecast["value"], 0)
        self.assertLessEqual(forecast["value"], 1)
        self.assertEqual(forecast["targetContractVersion"], TARGET_CONTRACT_VERSION)
        self.assertEqual(forecast["featureContractVersion"], FEATURE_CONTRACT_VERSION)
        self.assertEqual(forecast["horizon"], "T+1")
        self.assertLess(datetime.fromisoformat(forecast["fitCutoff"]), datetime.fromisoformat(current["decision_time"]))
        self.assertEqual(forecast["availability"], "PROSPECTIVE_ONLY")
        self.assertEqual(forecast["provenance"], "PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT")
        self.assertEqual(forecast["trainingPositiveCount"], 15)
        self.assertEqual(forecast["trainingNegativeCount"], 15)
        parameters = forecast["modelParameters"]
        linear_value = parameters["intercept"] + sum(
            coefficient * forecast["features"][feature]
            for coefficient, feature in zip(parameters["coefficients"], forecast["featureNames"])
        )
        expected_probability = 1 / (1 + math.exp(-linear_value))
        self.assertAlmostEqual(forecast["value"], expected_probability, places=12)

        future_decision = decision_fixture(99, decision_time="2026-10-02T09:00:00+08:00")
        future_row = {"decision": future_decision, "outcome": outcome_fixture(future_decision, 0.5)}
        second = fit_probability_forecast(current, [*rows, future_row])
        self.assertEqual(second["probabilityForecast"], forecast)

        pair = valid_oos_pair(
            {**current, "decision_output": {**current["decision_output"], "probabilityForecast": forecast}},
            outcome_fixture(current, 0.01),
        )
        self.assertIsNotNone(pair)
        self.assertEqual(pair["outcome"], 1)

    def test_insufficient_training_history_fails_closed(self) -> None:
        current = decision_fixture(70, decision_time="2026-10-01T09:00:00+08:00")
        result = fit_probability_forecast(current, [])
        self.assertIsNone(result["probabilityForecast"])
        self.assertEqual(result["status"], "INSUFFICIENT_TRAINING_HISTORY")
        self.assertEqual(result["trainingSampleCount"], 0)

    def test_ai_api_generates_and_ledger_round_trips_prospective_forecast(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p203-api-") as temp_dir:
            store = DerivativesStore(Path(temp_dir) / "isolated.sqlite3")
            store.initialize()
            for index in range(40):
                success = index % 2 == 0
                direction = "LONG" if index % 4 < 2 else "SHORT"
                decision = decision_fixture(
                    index,
                    direction=direction,
                    market_score=75 if success else 25,
                    risk_score=35 if success else 70,
                )
                decision["instrument"] = "TXO"
                snapshot = {"marketAsOf": decision["market_as_of"], "row": index}
                snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
                ledger_decision = {
                    **decision,
                    "symbol": "TXO",
                    "strategy_id": "P2_03_TEST",
                    "strategy_version": "P2_03_TEST_V1",
                    "model_version": "rules-v1",
                    "input_snapshot": snapshot,
                    "input_snapshot_hash": hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest(),
                    "evidence_score": decision["evidence_score"],
                    "data_quality_score": decision["data_quality_score"],
                    "executionDirectionReason": f"EXPLICIT_{direction}_DECISION",
                    "executionDirectionContractVersion": "P1D_DIRECTION_V1",
                    "created_at": decision["decision_time"],
                }
                self.assertTrue(store.record_decision(ledger_decision))
                store.record_decision_outcome(decision["decision_id"], TARGET_HORIZON, {
                    "evaluation_time": (datetime.fromisoformat(decision["decision_time"]) + timedelta(hours=8)).isoformat(),
                    "status": "AVAILABLE",
                    "gross_return": 0.01 if success else -0.01,
                    "net_return": None,
                    "target_hit": "NOT_APPLICABLE",
                    "stop_hit": "NOT_APPLICABLE",
                    "data_quality_status": "PARTIAL",
                    "market_observations": [],
                    "outcome_metadata": {
                        "outcomeSchemaVersion": "P2_02_OUTCOME_V1",
                        "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
                        "outcomeStatus": "EVALUATED",
                        "horizon": TARGET_HORIZON,
                        "evaluationBasis": "DIRECTIONAL_RETURN",
                        "decisionAlignedReturn": 0.01 if success else -0.01,
                    },
                })

            immutable_decision_id = "p203-fixture-0"
            before_decision = store.get_decision(immutable_decision_id)
            before_outcome = store.get_decision_outcome(immutable_decision_id, TARGET_HORIZON)

            input_snapshot = {"summary": {"marketAsOf": "2026-10-20"}, "chain": [], "spot": 100}
            current = build_decision_contract(
                symbol="TXO",
                input_snapshot=input_snapshot,
                decision_output={"bias": "bullish", "marketScore": 68, "riskScore": 42},
                available_evidence=5,
                evidence_total=5,
                decision_context={
                    "decision_time": "2026-10-20T09:00:00+08:00",
                    "market_as_of": "2026-10-20",
                    "source_updated_at": "2026-10-20T08:55:00+08:00",
                },
                execution_direction="LONG",
                execution_direction_reason="EXPLICIT_LONG_DECISION",
            )
            analysis = {
                **current,
                "target": "TXO",
                "marketScore": 68,
                "riskScore": 42,
                "evidenceScore": 100,
                "dataQualityScore": current["dataQualityScore"],
            }
            fetched = {
                "analysis": analysis,
                "summary": input_snapshot["summary"],
                "chain": input_snapshot["chain"],
                "spot": {"value": 100},
            }
            flask_app = app.create_app({"TESTING": True}, derivatives_store=store)
            with patch.object(routes_derivatives, "fetch_txo_option_chain", return_value=fetched):
                response = flask_app.test_client().get("/api/ai-analysis?target=TXO")
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()["data"]
            forecast = payload["probabilityForecast"]
            self.assertIsNotNone(forecast)
            self.assertEqual(forecast["targetType"], "DIRECTIONAL_SUCCESS")
            self.assertEqual(forecast["horizon"], TARGET_HORIZON)
            self.assertEqual(payload["marketScore"], 68)
            self.assertFalse(payload["probabilityLabelAllowed"])

            saved = store.get_decision(forecast["decisionId"])
            self.assertEqual(saved["decision_output"]["probabilityForecast"], forecast)
            ledger_response = flask_app.test_client().get(f"/api/decision-ledger/{forecast['decisionId']}")
            self.assertEqual(ledger_response.status_code, 200)
            ledger_decision = ledger_response.get_json()["data"]["decision"]
            self.assertEqual(ledger_decision["probabilityForecast"], forecast)
            self.assertEqual(ledger_decision["decisionOutput"]["marketScore"], 68)
            self.assertFalse(ledger_decision["decisionOutput"]["probabilityLabelAllowed"])
            self.assertEqual(store.get_decision(immutable_decision_id), before_decision)
            self.assertEqual(store.get_decision_outcome(immutable_decision_id, TARGET_HORIZON), before_outcome)

    def test_ledger_training_query_and_api_round_trip_preserve_forecast(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p203-ledger-") as temp_dir:
            store = DerivativesStore(Path(temp_dir) / "isolated.sqlite3")
            store.initialize()
            decision = decision_fixture(1)
            snapshot = {"marketAsOf": decision["market_as_of"], "features": [1, 2, 3]}
            snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
            ledger_decision = {
                **decision,
                "symbol": "TXF",
                "instrument": "TXF",
                "strategy_id": "P2_03_TEST",
                "strategy_version": "P2_03_TEST_V1",
                "model_version": "existing-rules-v1",
                "input_snapshot": snapshot,
                "input_snapshot_hash": hashlib.sha256(snapshot_json.encode("utf-8")).hexdigest(),
                "decision_output": {
                    **decision["decision_output"],
                    "probabilityForecast": {
                        "value": 0.63,
                        "targetType": "DIRECTIONAL_SUCCESS",
                        "targetContractVersion": TARGET_CONTRACT_VERSION,
                        "horizon": TARGET_HORIZON,
                        "generatedAt": decision["decision_time"],
                        "modelVersion": "P2_03_LOGISTIC_REGRESSION_V1:test",
                        "featureContractVersion": FEATURE_CONTRACT_VERSION,
                        "fitCutoff": "2026-08-31T16:00:00+08:00",
                        "provenance": "PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT",
                    },
                    "probabilityLabelAllowed": False,
                },
                "executionDirectionReason": "EXPLICIT_LONG_DECISION",
                "executionDirectionContractVersion": "P1D_DIRECTION_V1",
                "created_at": decision["decision_time"],
            }
            self.assertTrue(store.record_decision(ledger_decision))
            round_trip = store.get_decision(ledger_decision["decision_id"])
            self.assertEqual(round_trip["decision_output"]["probabilityForecast"]["value"], 0.63)

            flask_app = app.create_app({"TESTING": True}, derivatives_store=store)
            response = flask_app.test_client().get(f"/api/decision-ledger/{ledger_decision['decision_id']}")
            self.assertEqual(response.status_code, 200)
            returned = response.get_json()["data"]["decision"]
            self.assertEqual(returned["probabilityForecast"]["value"], 0.63)
            self.assertFalse(returned["decisionOutput"]["probabilityLabelAllowed"])

            store.record_decision_outcome(ledger_decision["decision_id"], TARGET_HORIZON, {
                "evaluation_time": "2026-09-02T16:00:00+08:00",
                "status": "AVAILABLE",
                "gross_return": 0.01,
                "net_return": None,
                "target_hit": "NOT_APPLICABLE",
                "stop_hit": "NOT_APPLICABLE",
                "data_quality_status": "PARTIAL",
                "market_observations": [{"date": "2026-09-02", "close": 101}],
                "outcome_metadata": {
                    "outcomeSchemaVersion": "P2_02_OUTCOME_V1",
                    "evaluationContractVersion": "P2_02_DIRECTIONAL_OUTCOME_V1",
                    "outcomeStatus": "EVALUATED",
                    "horizon": TARGET_HORIZON,
                    "evaluationBasis": "DIRECTIONAL_RETURN",
                    "decisionAlignedReturn": 0.01,
                    "timestamps": {"evaluatedAt": "2026-09-02T16:00:00+08:00"},
                },
            })
            training = store.list_probability_training_rows(TARGET_HORIZON, "2026-09-03T09:00:00+08:00")
            self.assertEqual(len(training), 1)
            self.assertEqual(training[0]["outcome"]["outcome_metadata"]["outcomeStatus"], "EVALUATED")


if __name__ == "__main__":
    unittest.main()
