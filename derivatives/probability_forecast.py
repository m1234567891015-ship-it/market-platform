"""Leakage-safe P2-03 directional-success probability forecast foundation.

Forecasts are produced only from a fixed, versioned decision-time feature
contract and previously evaluated P2-02 outcomes.  Scenario weights and other
heuristic values are never interpreted as probabilities; they may only be
features in a fitted logistic regression.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from typing import Any, Iterable


TARGET_TYPE = "DIRECTIONAL_SUCCESS"
TARGET_CONTRACT_VERSION = "P2_03_DIRECTIONAL_SUCCESS_V1"
FEATURE_CONTRACT_VERSION = "P2_03_DERIVATIVES_SCORE_FEATURES_V1"
MODEL_CONTRACT_VERSION = "P2_03_LOGISTIC_REGRESSION_V1"
TARGET_HORIZON = "T+1"
P2_02_OUTCOME_CONTRACT_VERSION = "P2_02_DIRECTIONAL_OUTCOME_V1"
MIN_TRAINING_SAMPLES = 30
FEATURE_FIELDS = ("marketScore", "riskScore", "evidenceScore", "dataQualityScore")
FEATURE_NAMES = ("marketScore01", "riskScore01", "evidenceScore01", "dataQualityScore01")
CALIBRATION_STATUS_INSUFFICIENT = "INSUFFICIENT_SAMPLE"


def _aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _local_decision_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.date() if parsed.tzinfo is not None else None


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _decision_output(decision: dict[str, Any]) -> dict[str, Any]:
    output = decision.get("decision_output")
    if not isinstance(output, dict):
        output = decision.get("decisionOutput")
    return output if isinstance(output, dict) else {}


def build_feature_vector(decision: dict[str, Any]) -> list[float] | None:
    """Read only immutable score/evidence fields available at decision time."""
    output = _decision_output(decision)
    decision_time = _aware_datetime(decision.get("decision_time") or decision.get("decisionTime"))
    raw_decision_time = decision.get("decision_time") or decision.get("decisionTime")
    decision_date = _local_decision_date(raw_decision_time)
    market_date = _date(decision.get("market_as_of") or decision.get("marketAsOf"))
    if decision_time is None or decision_date is None or market_date is None or market_date > decision_date:
        return None

    data_as_of = decision.get("data_as_of") or decision.get("dataAsOf") or decision.get("source_updated_at")
    if data_as_of:
        data_time = _aware_datetime(data_as_of)
        data_date = _date(data_as_of)
        if data_time is None and data_date is None:
            return None
        if data_time is not None and data_time > decision_time:
            return None
        if data_date is not None and data_date > decision_date:
            return None

    values: list[float] = []
    for field in FEATURE_FIELDS:
        value = output.get(field, decision.get(field))
        if field == "evidenceScore":
            value = decision.get("evidence_score", value)
        elif field == "dataQualityScore":
            value = decision.get("data_quality_score", value)
        parsed = _finite_number(value)
        if parsed is None or parsed < 0 or parsed > 100:
            return None
        values.append(parsed / 100.0)
    return values


def derive_directional_target(
    decision: dict[str, Any], outcome: dict[str, Any], *, horizon: str = TARGET_HORIZON
) -> dict[str, Any]:
    """Derive the P2-03 binary target without modifying the P2-02 outcome."""
    output = _decision_output(decision)
    state = str(decision.get("decisionState") or output.get("decisionState") or "UNKNOWN").upper()
    eligible = decision.get("decisionEligible", output.get("decisionEligible")) is True
    direction = str(decision.get("executionDirection") or output.get("executionDirection") or "").upper()
    metadata = outcome.get("outcome_metadata") or outcome.get("outcomeMetadata")
    if not isinstance(metadata, dict):
        return {"eligible": False, "status": "EXCLUDED_OUTCOME_METADATA_UNAVAILABLE"}

    outcome_status = str(metadata.get("outcomeStatus") or outcome.get("outcome_status") or "UNAVAILABLE").upper()
    outcome_horizon = str(metadata.get("horizon") or outcome.get("evaluation_horizon") or "").upper()
    if state not in {"LONG", "SHORT"} or not eligible or direction != state:
        return {"eligible": False, "status": "EXCLUDED_DECISION_STATE"}
    if outcome_status != "EVALUATED":
        return {"eligible": False, "status": f"EXCLUDED_{outcome_status}"}
    if outcome_horizon != horizon or str(outcome.get("evaluation_horizon") or horizon).upper() != horizon:
        return {"eligible": False, "status": "EXCLUDED_HORIZON_MISMATCH"}
    if metadata.get("evaluationContractVersion") != P2_02_OUTCOME_CONTRACT_VERSION:
        return {"eligible": False, "status": "EXCLUDED_OUTCOME_CONTRACT_MISMATCH"}
    if metadata.get("evaluationBasis") != "DIRECTIONAL_RETURN":
        return {"eligible": False, "status": "EXCLUDED_EVALUATION_BASIS"}

    aligned_return = _finite_number(metadata.get("decisionAlignedReturn"))
    if aligned_return is None:
        return {"eligible": False, "status": "EXCLUDED_RETURN_UNAVAILABLE"}
    if aligned_return == 0:
        return {"eligible": False, "status": "EXCLUDED_FLAT"}

    decision_time = _aware_datetime(decision.get("decision_time") or decision.get("decisionTime"))
    evaluated_at = _aware_datetime(outcome.get("evaluation_time") or metadata.get("timestamps", {}).get("evaluatedAt"))
    if decision_time is None or evaluated_at is None or evaluated_at <= decision_time:
        return {"eligible": False, "status": "EXCLUDED_INVALID_CHRONOLOGY"}
    features = build_feature_vector(decision)
    if features is None:
        return {"eligible": False, "status": "EXCLUDED_INVALID_DECISION_TIME_FEATURES"}
    return {
        "eligible": True,
        "status": "ELIGIBLE",
        "targetType": TARGET_TYPE,
        "targetContractVersion": TARGET_CONTRACT_VERSION,
        "horizon": horizon,
        "value": 1 if aligned_return > 0 else 0,
        "features": features,
        "decisionId": decision.get("decision_id") or decision.get("decisionId"),
        "decisionTime": decision.get("decision_time") or decision.get("decisionTime"),
        "evaluatedAt": outcome.get("evaluation_time") or metadata.get("timestamps", {}).get("evaluatedAt"),
    }


def _sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + inverse)
    exponent = math.exp(max(value, -700.0))
    return exponent / (1.0 + exponent)


def _fit_logistic_regression(samples: list[dict[str, Any]]) -> list[float]:
    """Fixed deterministic batch logistic regression; no tuning/search."""
    feature_count = len(FEATURE_NAMES)
    positive = sum(int(sample["value"]) for sample in samples)
    negative = len(samples) - positive
    weights = [math.log((positive + 0.5) / (negative + 0.5))] + [0.0] * feature_count
    learning_rate = 0.1
    l2_penalty = 0.01
    iterations = 2500
    for _ in range(iterations):
        gradients = [0.0] * (feature_count + 1)
        for sample in samples:
            row = sample["features"]
            probability = _sigmoid(weights[0] + sum(weights[index + 1] * row[index] for index in range(feature_count)))
            error = probability - int(sample["value"])
            gradients[0] += error
            for index, value in enumerate(row):
                gradients[index + 1] += error * value
        scale = 1.0 / len(samples)
        weights[0] -= learning_rate * gradients[0] * scale
        for index in range(feature_count):
            gradient = gradients[index + 1] * scale + l2_penalty * weights[index + 1]
            weights[index + 1] -= learning_rate * gradient
    return weights


def _model_version(samples: list[dict[str, Any]], weights: list[float], fit_cutoff: str) -> str:
    canonical = json.dumps(
        {
            "contract": MODEL_CONTRACT_VERSION,
            "target": TARGET_CONTRACT_VERSION,
            "feature": FEATURE_CONTRACT_VERSION,
            "horizon": TARGET_HORIZON,
            "instrument": samples[0].get("instrument") if samples else None,
            "sampleIds": [sample.get("decisionId") for sample in samples],
            "fitCutoff": fit_cutoff,
            "weights": [round(weight, 14) for weight in weights],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{MODEL_CONTRACT_VERSION}:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def fit_probability_forecast(
    decision: dict[str, Any],
    training_rows: Iterable[dict[str, Any]],
    *,
    horizon: str = TARGET_HORIZON,
    min_samples: int = MIN_TRAINING_SAMPLES,
) -> dict[str, Any]:
    """Fit only on eligible prior outcomes and return a decision-time forecast."""
    decision_time_raw = decision.get("decision_time") or decision.get("decisionTime")
    decision_time = _aware_datetime(decision_time_raw)
    features = build_feature_vector(decision)
    output = _decision_output(decision)
    state = str(decision.get("decisionState") or output.get("decisionState") or "UNKNOWN").upper()
    eligible = decision.get("decisionEligible", output.get("decisionEligible")) is True
    direction = str(decision.get("executionDirection") or output.get("executionDirection") or "").upper()
    if horizon != TARGET_HORIZON:
        return {"probabilityForecast": None, "status": "UNAVAILABLE_HORIZON_CONTRACT_MISMATCH"}
    if decision_time is None or features is None or state not in {"LONG", "SHORT"} or not eligible or direction != state:
        return {"probabilityForecast": None, "status": "UNAVAILABLE_INELIGIBLE_DECISION"}

    samples: list[dict[str, Any]] = []
    for row in training_rows:
        training_decision = row.get("decision") if isinstance(row.get("decision"), dict) else row
        outcome = row.get("outcome") if isinstance(row.get("outcome"), dict) else {}
        sample = derive_directional_target(training_decision, outcome, horizon=horizon)
        if not sample.get("eligible"):
            continue
        current_instrument = str(decision.get("instrument") or "").strip().upper()
        training_instrument = str(training_decision.get("instrument") or "").strip().upper()
        if current_instrument and training_instrument != current_instrument:
            continue
        sample_decision_time = _aware_datetime(sample.get("decisionTime"))
        evaluated_at = _aware_datetime(sample.get("evaluatedAt"))
        if sample_decision_time is None or evaluated_at is None:
            continue
        if sample_decision_time >= decision_time or evaluated_at >= decision_time:
            continue
        sample["instrument"] = training_decision.get("instrument")
        samples.append(sample)
    samples.sort(key=lambda sample: (
        _aware_datetime(sample["decisionTime"]),
        _aware_datetime(sample["evaluatedAt"]),
        str(sample.get("decisionId")),
    ))

    if len(samples) < min_samples:
        return {
            "probabilityForecast": None,
            "status": "INSUFFICIENT_TRAINING_HISTORY",
            "trainingSampleCount": len(samples),
        }
    if {sample["value"] for sample in samples} != {0, 1}:
        return {
            "probabilityForecast": None,
            "status": "INSUFFICIENT_TARGET_VARIATION",
            "trainingSampleCount": len(samples),
        }

    training_positive_count = sum(int(sample["value"]) for sample in samples)
    training_negative_count = len(samples) - training_positive_count
    weights = _fit_logistic_regression(samples)
    prediction = _sigmoid(weights[0] + sum(weights[index + 1] * features[index] for index in range(len(features))))
    latest_sample = max(samples, key=lambda sample: _aware_datetime(sample["evaluatedAt"]))
    earliest_sample = min(samples, key=lambda sample: _aware_datetime(sample["decisionTime"]))
    latest_decision = max(samples, key=lambda sample: _aware_datetime(sample["decisionTime"]))
    fit_cutoff = str(latest_sample["evaluatedAt"])
    fit_cutoff_dt = _aware_datetime(fit_cutoff)
    if fit_cutoff_dt is None or fit_cutoff_dt >= decision_time:
        return {"probabilityForecast": None, "status": "INVALID_FIT_CUTOFF"}
    training_start = str(earliest_sample["decisionTime"])
    training_end = str(latest_decision["decisionTime"])
    forecast = {
        "value": round(min(max(prediction, 0.0), 1.0), 12),
        "targetType": TARGET_TYPE,
        "eventDefinition": "decisionAlignedReturn > 0",
        "targetContractVersion": TARGET_CONTRACT_VERSION,
        "horizon": horizon,
        "decisionId": decision.get("decision_id") or decision.get("decisionId"),
        "instrument": decision.get("instrument"),
        "generatedAt": str(decision_time_raw),
        "modelVersion": _model_version(samples, weights, fit_cutoff),
        "modelType": "LOGISTIC_REGRESSION",
        "modelParameters": {
            "intercept": round(weights[0], 14),
            "coefficients": [round(weight, 14) for weight in weights[1:]],
            "trainer": "FIXED_BATCH_GRADIENT_DESCENT_V1",
            "iterations": 2500,
            "learningRate": 0.1,
            "l2Penalty": 0.01,
        },
        "featureContractVersion": FEATURE_CONTRACT_VERSION,
        "featureNames": list(FEATURE_NAMES),
        "features": {name: round(value, 12) for name, value in zip(FEATURE_NAMES, features)},
        "trainingStart": training_start,
        "trainingEnd": training_end,
        "fitCutoff": fit_cutoff,
        "trainingSampleCount": len(samples),
        "trainingPositiveCount": training_positive_count,
        "trainingNegativeCount": training_negative_count,
        "provenance": "PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT",
        "availability": "PROSPECTIVE_ONLY",
    }
    return {"probabilityForecast": forecast, "status": "FORECAST_AVAILABLE", "trainingSampleCount": len(samples)}


def valid_oos_pair(decision: dict[str, Any], outcome: dict[str, Any], *, horizon: str = TARGET_HORIZON) -> dict[str, Any] | None:
    """Validate one persisted forecast/outcome pair for future OOS reporting."""
    output = _decision_output(decision)
    forecast = output.get("probabilityForecast")
    if not isinstance(forecast, dict):
        return None
    if (
        forecast.get("targetContractVersion") != TARGET_CONTRACT_VERSION
        or forecast.get("featureContractVersion") != FEATURE_CONTRACT_VERSION
        or forecast.get("horizon") != horizon
        or forecast.get("provenance") != "PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT"
    ):
        return None
    decision_time = _aware_datetime(decision.get("decision_time") or decision.get("decisionTime"))
    generated_at = _aware_datetime(forecast.get("generatedAt"))
    fit_cutoff = _aware_datetime(forecast.get("fitCutoff"))
    if decision_time is None or generated_at != decision_time or fit_cutoff is None or fit_cutoff >= decision_time:
        return None
    target = derive_directional_target(decision, outcome, horizon=horizon)
    if not target.get("eligible"):
        return None
    evaluated_at = _aware_datetime(target.get("evaluatedAt"))
    if evaluated_at is None or evaluated_at <= decision_time:
        return None
    probability = _finite_number(forecast.get("value"))
    if probability is None or probability < 0 or probability > 1:
        return None
    return {"decisionId": target.get("decisionId"), "prediction": probability, "outcome": target["value"], "decisionTime": target["decisionTime"], "evaluatedAt": target["evaluatedAt"], "fitCutoff": forecast["fitCutoff"]}
