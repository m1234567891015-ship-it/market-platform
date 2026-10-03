"""Isolated, deterministic P2-03 historical research replay (stdlib only).

This module deliberately has no production API or Decision Ledger integration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / ".tmp" / "p203-historical-asof-replay" / "taifex_tx_daily_normalized.json"
OUTPUT_DIR = ROOT / ".tmp" / "p203-historical-research-v1"
CONTRACT_PATH = OUTPUT_DIR / "feature_contract.json"
EXPECTED_INPUT_SHA256 = "90b5f772a19e230d2212f66a1c522be0e95801f03fd8079d33235a16d3106930"
FEATURE_CONTRACT_ID = "P2_03_HISTORICAL_RESEARCH_FEATURES_V1"
MODEL_ID = "P2_03_HISTORICAL_RESEARCH_LOGISTIC_V1"
TARGET_CONTRACT_ID = "P2_03_HISTORICAL_RESEARCH_DIRECTIONAL_SUCCESS_V1"
PROVENANCE = "HISTORICAL_RESEARCH_AS_OF_OOS"
FEATURE_NAMES = ("momentum_5", "range_pct_1", "open_interest_change_1")
WARMUP_SESSIONS = 5
MIN_TRAINING_SAMPLES = 30
LOGISTIC_ITERATIONS = 2500
LEARNING_RATE = 0.1
L2_PENALTY = 0.01
CONTRACT_BYTES = CONTRACT_PATH.read_bytes() if CONTRACT_PATH.exists() else b""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_dataset(path: Path = INPUT_PATH, expected_sha256: str = EXPECTED_INPUT_SHA256) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_bytes()
    actual = sha256_bytes(raw)
    if expected_sha256 and actual != expected_sha256.lower():
        raise ValueError(f"input hash mismatch: expected {expected_sha256}, got {actual}")
    rows = json.loads(raw.decode("utf-8"))
    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError("historical input must be a JSON list with at least two sessions")
    dates = [str(row.get("time") or "") for row in rows]
    if any(not value for value in dates) or dates != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError("market dates must be present, unique, and strictly increasing")
    return rows, actual


def _number(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def derive_features(rows: list[dict[str, Any]], index: int) -> dict[str, float] | None:
    """Derive V1 features at index using that row and earlier rows only."""
    if index < WARMUP_SESSIONS or index >= len(rows):
        return None
    close_now = _number(rows[index], "close")
    close_lag5 = _number(rows[index - WARMUP_SESSIONS], "close")
    high_now = _number(rows[index], "high")
    low_now = _number(rows[index], "low")
    oi_now = _number(rows[index], "openInterest")
    oi_prior = _number(rows[index - 1], "openInterest")
    if None in (close_now, close_lag5, high_now, low_now, oi_now, oi_prior):
        return None
    if close_now <= 0 or close_lag5 <= 0 or oi_prior <= 0 or high_now < low_now:
        return None
    values = {
        "momentum_5": close_now / close_lag5 - 1.0,
        "range_pct_1": (high_now - low_now) / close_now,
        "open_interest_change_1": oi_now / oi_prior - 1.0,
    }
    return values if all(math.isfinite(value) for value in values.values()) else None


def _make_candidate(rows: list[dict[str, Any]], index: int) -> dict[str, Any]:
    features = derive_features(rows, index)
    if features is None:
        return {"index": index, "status": "FEATURE_INCOMPLETE"}
    momentum = features["momentum_5"]
    if momentum == 0:
        return {"index": index, "status": "RESEARCH_DIRECTION_UNAVAILABLE", "features": features}
    if index + 1 >= len(rows):
        return {"index": index, "status": "TARGET_UNAVAILABLE", "features": features}
    close_now = _number(rows[index], "close")
    close_next = _number(rows[index + 1], "close")
    if close_now is None or close_next is None or close_now <= 0 or close_next <= 0:
        return {"index": index, "status": "TARGET_UNAVAILABLE", "features": features}
    raw_return = close_next / close_now - 1.0
    direction = 1 if momentum > 0 else -1
    aligned_return = direction * raw_return
    if aligned_return == 0:
        return {
            "index": index,
            "status": "EXCLUDED_FLAT",
            "features": features,
            "direction": "RESEARCH_LONG" if direction > 0 else "RESEARCH_SHORT",
            "targetDate": rows[index + 1]["time"],
            "decisionDate": rows[index]["time"],
            "decisionAlignedReturn": aligned_return,
        }
    return {
        "index": index,
        "status": "ELIGIBLE_TARGET",
        "features": features,
        "direction": "RESEARCH_LONG" if direction > 0 else "RESEARCH_SHORT",
        "directionSign": direction,
        "decisionDate": rows[index]["time"],
        "targetDate": rows[index + 1]["time"],
        "decisionAlignedReturn": aligned_return,
        "value": 1 if aligned_return > 0 else 0,
        "provenance": PROVENANCE,
    }


def _matured_prior(candidates: list[dict[str, Any]], cutoff_date: str, current_index: int) -> list[dict[str, Any]]:
    return [
        item for item in candidates
        if item.get("status") == "ELIGIBLE_TARGET"
        and item["index"] < current_index
        and item["targetDate"] < cutoff_date
    ]


def _sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + inverse)
    exponent = math.exp(max(value, -700.0))
    return exponent / (1.0 + exponent)


def _fit(training: list[dict[str, Any]]) -> dict[str, Any]:
    if len(training) < MIN_TRAINING_SAMPLES:
        raise ValueError("insufficient training samples")
    labels = {int(row["value"]) for row in training}
    if labels != {0, 1}:
        raise ValueError("both training classes are required")
    feature_count = len(FEATURE_NAMES)
    means = [sum(row["features"][name] for row in training) / len(training) for name in FEATURE_NAMES]
    stds = []
    for feature_index, name in enumerate(FEATURE_NAMES):
        variance = sum((row["features"][name] - means[feature_index]) ** 2 for row in training) / len(training)
        stds.append(math.sqrt(variance))

    def normalized(row: dict[str, Any]) -> list[float]:
        result = []
        for idx, name in enumerate(FEATURE_NAMES):
            result.append((row["features"][name] - means[idx]) / stds[idx] if stds[idx] > 0 else 0.0)
        return result

    matrix = [normalized(row) for row in training]
    positives = sum(int(row["value"]) for row in training)
    negatives = len(training) - positives
    weights = [math.log((positives + 0.5) / (negatives + 0.5))] + [0.0] * feature_count
    for _ in range(LOGISTIC_ITERATIONS):
        gradients = [0.0] * (feature_count + 1)
        for features, row in zip(matrix, training):
            probability = _sigmoid(weights[0] + sum(weights[idx + 1] * features[idx] for idx in range(feature_count)))
            error = probability - int(row["value"])
            gradients[0] += error
            for idx, value in enumerate(features):
                gradients[idx + 1] += error * value
        scale = 1.0 / len(training)
        weights[0] -= LEARNING_RATE * gradients[0] * scale
        for idx in range(feature_count):
            weights[idx + 1] -= LEARNING_RATE * (gradients[idx + 1] * scale + L2_PENALTY * weights[idx + 1])
    return {"means": means, "stds": stds, "weights": weights, "positiveCount": positives, "negativeCount": negatives}


def _predict(features: dict[str, float], model: dict[str, Any]) -> float:
    standardized = [
        (features[name] - model["means"][idx]) / model["stds"][idx] if model["stds"][idx] > 0 else 0.0
        for idx, name in enumerate(FEATURE_NAMES)
    ]
    return _sigmoid(model["weights"][0] + sum(model["weights"][idx + 1] * value for idx, value in enumerate(standardized)))


def _brier(pairs: list[dict[str, Any]], key: str) -> float | None:
    if not pairs:
        return None
    return sum((float(pair[key]) - int(pair["outcome"])) ** 2 for pair in pairs) / len(pairs)


def _reliability(pairs: list[dict[str, Any]], bucket_count: int = 10, probability_key: str = "probability") -> tuple[list[dict[str, Any]], float | None]:
    buckets = [[] for _ in range(bucket_count)]
    for pair in pairs:
        probability = float(pair[probability_key])
        index = min(int(probability * bucket_count), bucket_count - 1)
        buckets[index].append(pair)
    result = []
    ece = 0.0
    total = len(pairs)
    for idx, bucket in enumerate(buckets):
        count = len(bucket)
        mean_probability = sum(float(item[probability_key]) for item in bucket) / count if count else None
        event_rate = sum(int(item["outcome"]) for item in bucket) / count if count else None
        if count and total:
            ece += count / total * abs(mean_probability - event_rate)
        result.append({
            "bucketRange": [idx / bucket_count, (idx + 1) / bucket_count],
            "count": count,
            "meanProbability": mean_probability,
            "eventRate": event_rate,
        })
    return result, (ece if total else None)


def run_replay(rows: list[dict[str, Any]], input_hash: str) -> dict[str, Any]:
    candidates = [_make_candidate(rows, index) for index in range(len(rows))]
    feature_rows = []
    for index in range(WARMUP_SESSIONS, len(rows)):
        features = derive_features(rows, index)
        if features is not None:
            momentum = features["momentum_5"]
            feature_rows.append({
                "marketDate": rows[index]["time"],
                "researchDirection": "RESEARCH_LONG" if momentum > 0 else "RESEARCH_SHORT" if momentum < 0 else "UNAVAILABLE",
                **features,
            })

    forecasts: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    counts = {
        "totalHistoricalSessions": len(rows),
        "inputHashValid": True,
        "warmupExcluded": min(WARMUP_SESSIONS, len(rows)),
        "featureIncomplete": 0,
        "researchDirectionUnavailable": 0,
        "targetUnavailable": 0,
        "flatTarget": 0,
        "insufficientTraining": 0,
        "singleClassTraining": 0,
        "forecastGenerated": 0,
        "tPlus1TargetMatured": 0,
        "validHistoricalResearchOosPairs": 0,
    }
    for item in candidates:
        if item["index"] < WARMUP_SESSIONS:
            continue
        status = item["status"]
        if status == "FEATURE_INCOMPLETE":
            counts["featureIncomplete"] += 1
        elif status == "RESEARCH_DIRECTION_UNAVAILABLE":
            counts["researchDirectionUnavailable"] += 1
        elif status == "TARGET_UNAVAILABLE":
            counts["targetUnavailable"] += 1
        elif status == "EXCLUDED_FLAT":
            counts["flatTarget"] += 1
        elif status == "ELIGIBLE_TARGET":
            counts["tPlus1TargetMatured"] += 1

    for index in range(WARMUP_SESSIONS, len(rows) - 1):
        candidate = candidates[index]
        if candidate["status"] != "ELIGIBLE_TARGET":
            continue
        cutoff = rows[index]["time"]
        training = _matured_prior(candidates, cutoff, index)
        if len(training) < MIN_TRAINING_SAMPLES:
            counts["insufficientTraining"] += 1
            continue
        if {row["value"] for row in training} != {0, 1}:
            counts["singleClassTraining"] += 1
            continue
        model = _fit(training)
        probability = _predict(candidate["features"], model)
        naive = sum(int(row["value"]) for row in training) / len(training)
        fit_cutoff = max(row["targetDate"] for row in training)
        forecast = {
            "forecastDate": candidate["decisionDate"],
            "targetDate": candidate["targetDate"],
            "researchDirection": candidate["direction"],
            "probability": probability,
            "naiveProbability": naive,
            "trainingSampleCount": len(training),
            "trainingPositiveCount": model["positiveCount"],
            "trainingNegativeCount": model["negativeCount"],
            "fitCutoff": fit_cutoff,
            "featureValues": candidate["features"],
            "provenance": PROVENANCE,
        }
        forecasts.append(forecast)
        trace.append({
            "forecastDate": candidate["decisionDate"],
            "targetDate": candidate["targetDate"],
            "fitCutoff": fit_cutoff,
            "trainingSampleCount": len(training),
            "trainingPositiveCount": model["positiveCount"],
            "trainingNegativeCount": model["negativeCount"],
            "trainingStartTargetDate": min(row["targetDate"] for row in training),
            "trainingEndTargetDate": max(row["targetDate"] for row in training),
            "normalizationMeans": model["means"],
            "normalizationPopulationStds": model["stds"],
            "weights": model["weights"],
        })
    counts["forecastGenerated"] = len(forecasts)
    counts["validHistoricalResearchOosPairs"] = len(forecasts)
    pairs = []
    by_decision_index = {item["decisionDate"]: item for item in candidates if item.get("status") == "ELIGIBLE_TARGET"}
    for forecast in forecasts:
        target = by_decision_index[forecast["forecastDate"]]
        pairs.append({
            **forecast,
            "outcome": target["value"],
            "decisionAlignedReturn": target["decisionAlignedReturn"],
        })
    predictions = [float(pair["probability"]) for pair in pairs]
    outcomes = [int(pair["outcome"]) for pair in pairs]
    reliability, ece = _reliability(pairs)
    naive_reliability, naive_ece = _reliability(pairs, probability_key="naiveProbability")
    positive_count = sum(outcomes)
    report = {
        "evidenceClass": PROVENANCE,
        "researchOnly": True,
        "productionOos": False,
        "liveProspectiveOos": False,
        "productionContractReconstructedOos": False,
        "inputSha256": input_hash,
        "contractId": FEATURE_CONTRACT_ID,
        "modelId": MODEL_ID,
        "targetContractId": TARGET_CONTRACT_ID,
        "pairCount": len(pairs),
        "positiveCount": positive_count,
        "negativeCount": len(pairs) - positive_count,
        "positiveRate": positive_count / len(pairs) if pairs else None,
        "meanForecast": sum(predictions) / len(predictions) if predictions else None,
        "minForecast": min(predictions) if predictions else None,
        "maxForecast": max(predictions) if predictions else None,
        "brierScore": _brier(pairs, "probability"),
        "reliabilityBins": reliability,
        "ece": ece,
        "pastOnlyNaiveBaseRateBrierScore": _brier(pairs, "naiveProbability"),
        "naiveReliabilityBins": naive_reliability,
        "naiveEce": naive_ece,
        "interpretation": "EVIDENCE INCONCLUSIVE" if pairs else "EVIDENCE INSUFFICIENT",
        "promotionThresholdDefined": False,
        "sourceVintageStatus": "NOT PROVEN; current historical export has no archived per-date publication timestamp or revision history.",
    }
    return {"featureRows": feature_rows, "forecasts": forecasts, "pairs": pairs, "trainingTrace": trace, "funnel": counts, "report": report}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash_value(value: Any) -> str:
    return sha256_bytes(_canonical_bytes(value))


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def execute(input_path: Path = INPUT_PATH, output_dir: Path = OUTPUT_DIR, expected_sha256: str = EXPECTED_INPUT_SHA256) -> dict[str, Any]:
    rows, input_hash = load_dataset(input_path, expected_sha256)
    if not CONTRACT_BYTES:
        raise RuntimeError("frozen research feature_contract.json is missing")
    contract = json.loads(CONTRACT_BYTES.decode("utf-8"))
    if contract.get("contractId") != FEATURE_CONTRACT_ID or contract.get("input", {}).get("sha256") != input_hash:
        raise RuntimeError("frozen research contract does not match the validated input")
    contract_hash = sha256_bytes(CONTRACT_BYTES)
    first = run_replay(rows, input_hash)
    second = run_replay(rows, input_hash)
    output_names = ("featureRows", "forecasts", "pairs", "trainingTrace", "funnel", "report")
    run_fingerprints = [
        {name: _hash_value(run[name]) for name in output_names}
        for run in (first, second)
    ]
    deterministic = run_fingerprints[0] == run_fingerprints[1]
    if not deterministic:
        raise RuntimeError("deterministic replay fingerprints differ")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "feature_contract.json").write_bytes(CONTRACT_BYTES)
    _write_csv(output_dir / "feature_matrix.csv", second["featureRows"], ["marketDate", "researchDirection", *FEATURE_NAMES])
    (output_dir / "eligibility_funnel.json").write_bytes(_canonical_bytes(second["funnel"]) + b"\n")
    (output_dir / "training_trace.jsonl").write_bytes(b"".join(_canonical_bytes(item) + b"\n" for item in second["trainingTrace"]))
    forecast_rows = []
    for row in second["forecasts"]:
        forecast_rows.append({**{key: value for key, value in row.items() if key != "featureValues"}, **{f"feature_{key}": value for key, value in row["featureValues"].items()}})
    _write_csv(output_dir / "reconstructed_forecasts.csv", forecast_rows, [
        "forecastDate", "targetDate", "researchDirection", "probability", "naiveProbability",
        "trainingSampleCount", "trainingPositiveCount", "trainingNegativeCount", "fitCutoff", "provenance",
        *[f"feature_{name}" for name in FEATURE_NAMES],
    ])
    _write_csv(output_dir / "oos_pairs.csv", second["pairs"], [
        "forecastDate", "targetDate", "researchDirection", "probability", "naiveProbability", "outcome",
        "decisionAlignedReturn", "trainingSampleCount", "fitCutoff", "provenance",
    ])
    report = {**second["report"], "contractSha256": contract_hash, "featureMatrixSha256": run_fingerprints[1]["featureRows"], "forecastSha256": run_fingerprints[1]["forecasts"], "oosPairsSha256": run_fingerprints[1]["pairs"]}
    (output_dir / "calibration_report.json").write_bytes(_canonical_bytes(report) + b"\n")
    determinism = {
        "inputSha256": input_hash,
        "contractSha256": contract_hash,
        "twoRunsIdentical": deterministic,
        "runFingerprints": run_fingerprints,
    }
    (output_dir / "determinism_report.json").write_bytes(_canonical_bytes(determinism) + b"\n")
    summary = {
        "researchContract": FEATURE_CONTRACT_ID,
        "model": MODEL_ID,
        "evidenceClass": PROVENANCE,
        "sourceVintageStatus": report["sourceVintageStatus"],
        "funnel": second["funnel"],
        "interpretation": report["interpretation"],
        "productionP2_03": "BLOCKED",
        "probabilityLabelAllowed": False,
        "productionFeatureContractChanged": False,
    }
    (output_dir / "research_summary.json").write_bytes(_canonical_bytes(summary) + b"\n")
    return {"report": report, "funnel": second["funnel"], "determinism": determinism, "outputDir": str(output_dir)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=INPUT_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--expected-sha256", default=EXPECTED_INPUT_SHA256)
    args = parser.parse_args()
    result = execute(args.input, args.output_dir, args.expected_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
