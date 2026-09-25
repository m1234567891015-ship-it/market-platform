"""Deterministic, out-of-sample calibration primitives.

This module deliberately does not turn heuristic scores into probabilities.  A
caller must provide prediction/outcome pairs from an out-of-sample split, and
the resulting status remains ``UNCALIBRATED`` until an independently verified
calibration process explicitly promotes it.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Iterable


CALIBRATION_STATUS_UNAVAILABLE = "UNAVAILABLE"
CALIBRATION_STATUS_INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
CALIBRATION_STATUS_UNCALIBRATED = "UNCALIBRATED"
CALIBRATION_STATUS_CALIBRATED = "CALIBRATED"
CALIBRATION_STATUS_DEGRADED = "DEGRADED"
MIN_CALIBRATION_SAMPLE = 30


def _probability(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError("predicted probability must be numeric") from None
    if not isfinite(parsed) or parsed < 0 or parsed > 1:
        raise ValueError("predicted probability must be between 0 and 1")
    return parsed


def _outcome(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError("observed outcome must be numeric") from None
    if parsed not in (0.0, 1.0):
        raise ValueError("observed outcome must be 0 or 1")
    return parsed


def _normalise_pairs(predictions: Iterable[Any], outcomes: Iterable[Any]) -> list[tuple[float, float]]:
    prediction_values = list(predictions or [])
    outcome_values = list(outcomes or [])
    if len(prediction_values) != len(outcome_values):
        raise ValueError("predictions and outcomes must have equal length")
    return [(_probability(prediction), _outcome(outcome)) for prediction, outcome in zip(prediction_values, outcome_values)]


def calculate_brier_score(predictions: Iterable[Any], outcomes: Iterable[Any]) -> float | None:
    """Return mean((predictedProbability - observedOutcome)^2)."""
    pairs = _normalise_pairs(predictions, outcomes)
    if not pairs:
        return None
    return round(sum((prediction - outcome) ** 2 for prediction, outcome in pairs) / len(pairs), 12)


def build_calibration_buckets(
    predictions: Iterable[Any],
    outcomes: Iterable[Any],
    bucket_count: int = 10,
) -> list[dict[str, Any]]:
    """Build deterministic reliability-curve bucket data."""
    if not isinstance(bucket_count, int) or bucket_count < 1:
        raise ValueError("bucket_count must be a positive integer")
    pairs = _normalise_pairs(predictions, outcomes)
    buckets = [
        {"predictionSum": 0.0, "outcomeSum": 0.0, "predictionCount": 0}
        for _ in range(bucket_count)
    ]
    for prediction, outcome in pairs:
        index = min(int(prediction * bucket_count), bucket_count - 1)
        bucket = buckets[index]
        bucket["predictionSum"] += prediction
        bucket["outcomeSum"] += outcome
        bucket["predictionCount"] += 1

    result = []
    for index, bucket in enumerate(buckets):
        count = bucket["predictionCount"]
        lower = index / bucket_count
        upper = (index + 1) / bucket_count
        result.append(
            {
                "bucketRange": [round(lower, 12), round(upper, 12)],
                "predictionCount": count,
                "meanPredictedProbability": round(bucket["predictionSum"] / count, 12) if count else None,
                "observedEventRate": round(bucket["outcomeSum"] / count, 12) if count else None,
            }
        )
    return result


def build_oos_calibration_report(
    predictions: Iterable[Any],
    outcomes: Iterable[Any],
    *,
    data_split: str = "validation",
    min_samples: int = MIN_CALIBRATION_SAMPLE,
    bucket_count: int = 10,
) -> dict[str, Any]:
    """Summarise OOS calibration evidence without claiming calibration.

    The final Test holdout is never consumed here.  It is reported as
    protected, with no Brier score or bucket calculations.
    """
    split = str(data_split or "").strip().lower()
    if split == "test":
        return {
            "calibrationStatus": CALIBRATION_STATUS_UNAVAILABLE,
            "sampleCount": 0,
            "brierScore": None,
            "calibrationBuckets": [],
            "dataSplit": "test",
            "oos": False,
            "testHoldoutProtected": True,
            "probabilityLabelAllowed": False,
        }
    if split not in {"validation", "oos", "out_of_sample"}:
        raise ValueError("calibration requires validation or out-of-sample data")
    if not isinstance(min_samples, int) or min_samples < 1:
        raise ValueError("min_samples must be a positive integer")
    pairs = _normalise_pairs(predictions, outcomes)
    prediction_values = [prediction for prediction, _ in pairs]
    outcome_values = [outcome for _, outcome in pairs]
    sample_count = len(pairs)
    status = (
        CALIBRATION_STATUS_INSUFFICIENT_SAMPLE
        if sample_count < min_samples
        else CALIBRATION_STATUS_UNCALIBRATED
    )
    return {
        "calibrationStatus": status,
        "sampleCount": sample_count,
        "brierScore": calculate_brier_score(prediction_values, outcome_values),
        "calibrationBuckets": build_calibration_buckets(prediction_values, outcome_values, bucket_count),
        "dataSplit": "validation" if split == "validation" else "out_of_sample",
        "oos": True,
        "testHoldoutProtected": True,
        "probabilityLabelAllowed": status == CALIBRATION_STATUS_CALIBRATED,
    }


def probability_label_allowed(calibration_status: str | None) -> bool:
    return str(calibration_status or "").upper() == CALIBRATION_STATUS_CALIBRATED
