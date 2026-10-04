"""Read-only diagnostics for the frozen P2-03 V1R1 research artifacts.

This module intentionally does not import application or production model code.
It only reads the frozen V1R1 artifacts and writes research diagnostics to an
independent output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / ".tmp" / "p203-historical-research-v1r1"
OUTPUT_DIR = ROOT / ".tmp" / "p203-v1r1-diagnostic"
CONTRACT_PATH = ROOT / ".tmp" / "p203-historical-research-v1" / "feature_contract.json"
DB_PATH = ROOT / "data" / "p203-prospective-ledger.sqlite3"
EXPECTED_CONTRACT_SHA256 = "79eef16aec59844574b2dbde321a57f0982c844d25b334267eb48808d923f63d"
EXPECTED_DB_SHA256 = "73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4"
EXPECTED_METRICS = {
    "modelBrier": 0.25884095240510735,
    "naiveBrier": 0.25324341612661877,
    "modelEce": 0.05953472283565118,
    "naiveEce": 0.030093599776000558,
}
FEATURES = ("momentum_5", "range_pct_1", "open_interest_change_1")
COEFFICIENTS = ("intercept", *FEATURES)
OUTPUT_NAMES = (
    "forecast_distribution.json", "reliability_bins.csv", "temporal_metrics.csv",
    "rolling_metrics.csv", "cumulative_brier.csv", "base_rate_drift.csv",
    "feature_stability.csv", "feature_outcome_quintiles.csv", "extreme_forecasts.csv", "coefficient_trace.csv",
    "coefficient_stability.json", "largest_errors.csv", "model_vs_naive.csv",
    "diagnostic_summary.json",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fingerprint_tree(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)).replace("\\", "/"): _sha256(path)
        for path in sorted(directory.rglob("*")) if path.is_file()
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _num(row: dict[str, str], key: str) -> float:
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f"non-finite {key}: {value}")
    return value


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _quarter(date_text: str) -> str:
    year, month, _ = (int(part) for part in date_text.split("-"))
    return f"{year}-Q{(month - 1) // 3 + 1}"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _calibration_bins(probabilities: list[float], outcomes: list[int], bin_count: int = 10) -> list[dict[str, Any]]:
    bins: list[list[int]] = [[] for _ in range(bin_count)]
    for index, probability in enumerate(probabilities):
        if not 0 <= probability <= 1:
            raise ValueError(f"probability outside [0,1]: {probability}")
        bin_index = min(bin_count - 1, int(probability * bin_count))
        bins[bin_index].append(index)
    result = []
    for bin_index, indexes in enumerate(bins):
        lower, upper = bin_index / bin_count, (bin_index + 1) / bin_count
        result.append({
            "bin": bin_index,
            "lowerInclusive": lower,
            "upperExclusive": upper if bin_index < bin_count - 1 else None,
            "upperInclusive": 1.0 if bin_index == bin_count - 1 else None,
            "count": len(indexes),
            "meanForecast": statistics.mean(probabilities[i] for i in indexes) if indexes else None,
            "actualPositiveRate": statistics.mean(outcomes[i] for i in indexes) if indexes else None,
            "absoluteCalibrationGap": abs(
                statistics.mean(probabilities[i] for i in indexes) - statistics.mean(outcomes[i] for i in indexes)
            ) if indexes else None,
            "signedForecastMinusRate": (
                statistics.mean(probabilities[i] for i in indexes) - statistics.mean(outcomes[i] for i in indexes)
            ) if indexes else None,
        })
    return result


def _ece(bins: list[dict[str, Any]], total: int) -> float:
    return sum((item["count"] / total) * item["absoluteCalibrationGap"] for item in bins if item["count"])


def _brier(probabilities: list[float], outcomes: list[int]) -> float:
    return statistics.mean((p - y) ** 2 for p, y in zip(probabilities, outcomes))


def _auc(probabilities: list[float], outcomes: list[int]) -> float | None:
    positives = sum(outcomes)
    negatives = len(outcomes) - positives
    if not positives or not negatives:
        return None
    ordered = sorted(zip(probabilities, outcomes), key=lambda item: item[0])
    rank_sum = 0.0
    index = 0
    while index < len(ordered):
        stop = index + 1
        while stop < len(ordered) and ordered[stop][0] == ordered[index][0]:
            stop += 1
        average_rank = ((index + 1) + stop) / 2
        rank_sum += average_rank * sum(y for _, y in ordered[index:stop])
        index = stop
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def _calibration_intercept_slope(probabilities: list[float], outcomes: list[int]) -> dict[str, Any]:
    # Logistic calibration regression on logit(p), solved by unpenalized Newton
    # updates. Clipping is solely numerical protection for logit(0/1).
    eps = 1e-12
    xs = [math.log(min(1 - eps, max(eps, p)) / (1 - min(1 - eps, max(eps, p)))) for p in probabilities]
    a, b = 0.0, 1.0
    for _ in range(100):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for x, y in zip(xs, outcomes):
            z = max(-35.0, min(35.0, a + b * x))
            fitted = 1.0 / (1.0 + math.exp(-z))
            weight = fitted * (1.0 - fitted)
            residual = fitted - y
            g0 += residual
            g1 += residual * x
            h00 += weight
            h01 += weight * x
            h11 += weight * x * x
        determinant = h00 * h11 - h01 * h01
        if abs(determinant) < 1e-18:
            return {"status": "NOT CALCULATED", "reason": "singular calibration Hessian"}
        da = (h11 * g0 - h01 * g1) / determinant
        db = (-h01 * g0 + h00 * g1) / determinant
        a -= da
        b -= db
        if max(abs(da), abs(db)) < 1e-10:
            return {"status": "CALCULATED", "intercept": a, "slope": b, "numericalProbabilityClip": eps}
    return {"status": "NOT CALCULATED", "reason": "Newton iteration did not converge"}


def _brier_decomposition(bins: list[dict[str, Any]], outcomes: list[int]) -> dict[str, float]:
    base = statistics.mean(outcomes)
    reliability = 0.0
    resolution = 0.0
    for item in bins:
        if not item["count"]:
            continue
        weight = item["count"] / len(outcomes)
        reliability += weight * (item["meanForecast"] - item["actualPositiveRate"]) ** 2
        resolution += weight * (item["actualPositiveRate"] - base) ** 2
    uncertainty = base * (1 - base)
    return {"reliability": reliability, "resolution": resolution, "uncertainty": uncertainty,
            "reconstructedBrier": reliability - resolution + uncertainty,
            "decompositionBinCount": len(bins)}


def _database_snapshot(path: Path) -> dict[str, Any]:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {}
        for table in ("decision_ledger", "decision_outcome"):
            if table not in tables:
                raise ValueError(f"required table missing: {table}")
            counts[table] = int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        return {"sha256": _sha256(path), "counts": counts, "readOnly": True}
    finally:
        connection.close()


def analyze(
    input_dir: Path = INPUT_DIR,
    output_dir: Path = OUTPUT_DIR,
    *,
    contract_path: Path = CONTRACT_PATH,
    db_path: Path = DB_PATH,
    expected_db_sha256: str | None = EXPECTED_DB_SHA256,
) -> dict[str, Any]:
    if not input_dir.is_dir():
        raise FileNotFoundError(input_dir)
    before_tree = _fingerprint_tree(input_dir)
    contract_hash = _sha256(contract_path)
    if contract_hash != EXPECTED_CONTRACT_SHA256:
        raise ValueError(f"frozen contract hash mismatch: {contract_hash}")
    db_before = _database_snapshot(db_path)
    if (db_before["counts"] != {"decision_ledger": 1, "decision_outcome": 0}
            or (expected_db_sha256 is not None and db_before["sha256"] != expected_db_sha256)):
        raise ValueError(f"prospective DB integrity mismatch: {db_before}")

    summary = json.loads((input_dir / "research_summary.json").read_text(encoding="utf-8"))
    calibration = json.loads((input_dir / "calibration_report.json").read_text(encoding="utf-8"))
    features_rows = _read_csv(input_dir / "roll_clean_feature_matrix.csv")
    forecast_rows = _read_csv(input_dir / "reconstructed_forecasts.csv")
    pair_rows = _read_csv(input_dir / "oos_pairs.csv")
    trace_rows = [json.loads(line) for line in (input_dir / "training_trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(forecast_rows) != 272 or len(pair_rows) != 272 or len(trace_rows) != 272:
        raise ValueError("V1R1 OOS artifacts must each contain exactly 272 rows")
    dates = [row["forecastDate"] for row in forecast_rows]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError("OOS forecasts are not uniquely chronological")
    pair_by_date = {row["forecastDate"]: row for row in pair_rows}
    trace_by_date = {row["forecastDate"]: row for row in trace_rows}
    if set(pair_by_date) != set(dates) or set(trace_by_date) != set(dates):
        raise ValueError("forecast, pair, and coefficient trace dates do not align")
    merged = []
    for forecast in forecast_rows:
        pair, trace = pair_by_date[forecast["forecastDate"]], trace_by_date[forecast["forecastDate"]]
        row = dict(forecast)
        row["outcome"] = int(pair["outcome"])
        row["features"] = {feature: _num(forecast, f"feature_{feature}") for feature in FEATURES}
        weights = trace.get("weights")
        if not isinstance(weights, list) or len(weights) != len(COEFFICIENTS):
            raise ValueError(f"unexpected coefficient vector at {forecast['forecastDate']}")
        row["weights"] = [float(value) for value in weights]
        row["trainingBaseRate"] = int(forecast["trainingPositiveCount"]) / int(forecast["trainingSampleCount"])
        row["probability"] = _num(forecast, "probability")
        row["naiveProbability"] = _num(forecast, "naiveProbability")
        row["loss"] = (row["probability"] - row["outcome"]) ** 2
        row["naiveLoss"] = (row["naiveProbability"] - row["outcome"]) ** 2
        row["lossDifference"] = row["loss"] - row["naiveLoss"]
        merged.append(row)
    probabilities = [row["probability"] for row in merged]
    naive_probabilities = [row["naiveProbability"] for row in merged]
    outcomes = [row["outcome"] for row in merged]
    n = len(merged)
    model_brier, naive_brier = _brier(probabilities, outcomes), _brier(naive_probabilities, outcomes)
    model_bins = _calibration_bins(probabilities, outcomes)
    naive_bins = _calibration_bins(naive_probabilities, outcomes)
    model_ece, naive_ece = _ece(model_bins, n), _ece(naive_bins, n)
    recomputed = {"modelBrier": model_brier, "naiveBrier": naive_brier, "modelEce": model_ece, "naiveEce": naive_ece}
    for name, value in recomputed.items():
        if abs(value - EXPECTED_METRICS[name]) > 1e-9:
            raise ValueError(f"V1R1 metric integrity failure for {name}: {value}")
    if summary.get("pairCount") != n or summary.get("model") != "P2_03_HISTORICAL_RESEARCH_LOGISTIC_V1":
        raise ValueError("V1R1 model identity or pair count mismatch")
    if calibration.get("contractId") != "P2_03_HISTORICAL_RESEARCH_FEATURES_V1":
        raise ValueError("V1R1 contract identity mismatch")

    # Forecast distribution and pre-specified, mutually exclusive ranges.
    dist_ranges = [
        ("<0.10", None, .10), ("0.10-0.20", .10, .20), ("0.20-0.30", .20, .30),
        ("0.30-0.40", .30, .40), ("0.40-0.45", .40, .45), ("0.45-0.50", .45, .50),
        ("0.50-0.55", .50, .55), ("0.55-0.60", .55, .60), ("0.60-0.70", .60, .70),
        ("0.70-0.80", .70, .80), ("0.80-0.90", .80, .90), (">0.90", .90, None),
    ]
    distribution = []
    for label, lower, upper in dist_ranges:
        selected = [row for row in merged if (lower is None or row["probability"] >= lower)
                    and (upper is None or row["probability"] < upper
                         or (label == "0.80-0.90" and row["probability"] == upper))]
        distribution.append({"bucket": label, "count": len(selected), "percentage": len(selected) / n,
                             "actualPositiveRate": statistics.mean(row["outcome"] for row in selected) if selected else None,
                             "meanForecast": statistics.mean(row["probability"] for row in selected) if selected else None})
    distribution_summary = {
        "count": n, "mean": statistics.mean(probabilities), "median": statistics.median(probabilities),
        "stdPopulation": statistics.pstdev(probabilities), "min": min(probabilities), "max": max(probabilities),
        "p05": _quantile(probabilities, .05), "p10": _quantile(probabilities, .10),
        "p25": _quantile(probabilities, .25), "p50": _quantile(probabilities, .50),
        "p75": _quantile(probabilities, .75), "p90": _quantile(probabilities, .90), "p95": _quantile(probabilities, .95),
        "buckets": distribution,
        "between040And060": {"count": sum(.40 <= p < .60 for p in probabilities),
                             "percentage": sum(.40 <= p < .60 for p in probabilities) / n},
        "extremes": {"pLt010": sum(p < .10 for p in probabilities), "pGt090": sum(p > .90 for p in probabilities),
                     "pLt020": sum(p < .20 for p in probabilities), "pGt080": sum(p > .80 for p in probabilities)},
    }
    extreme_rows = []
    for row in merged:
        p = row["probability"]
        if p < .20 or p > .80:
            extreme_rows.append({"forecastDate": row["forecastDate"], "targetDate": row["targetDate"],
                                 "forecast": p, "target": row["outcome"], "trainingSampleCount": row["trainingSampleCount"],
                                 "trainingBaseRate": row["trainingBaseRate"],
                                 **{f"feature_{feature}": row["features"][feature] for feature in FEATURES},
                                 **{f"coef_{name}": row["weights"][index] for index, name in enumerate(COEFFICIENTS)}})

    # Reliability, calibration direction, Brier decomposition, and discrimination.
    reliability_rows = []
    for m_bin, n_bin in zip(model_bins, naive_bins):
        reliability_rows.append({
            "bin": m_bin["bin"], "lowerInclusive": m_bin["lowerInclusive"],
            "upperExclusive": m_bin["upperExclusive"], "upperInclusive": m_bin["upperInclusive"],
            "count": m_bin["count"], "meanForecast": m_bin["meanForecast"],
            "actualPositiveRate": m_bin["actualPositiveRate"], "absoluteCalibrationGap": m_bin["absoluteCalibrationGap"],
            "naiveCount": n_bin["count"], "naiveMeanForecast": n_bin["meanForecast"],
            "naiveActualPositiveRate": n_bin["actualPositiveRate"], "naiveAbsoluteCalibrationGap": n_bin["absoluteCalibrationGap"],
        })
    aggregate_gap = statistics.mean(probabilities) - statistics.mean(outcomes)
    slope = _calibration_intercept_slope(probabilities, outcomes)
    brier_decomp = _brier_decomposition(model_bins, outcomes)
    naive_decomp = _brier_decomposition(naive_bins, outcomes)
    aggregate_direction = "FORECAST BELOW REALIZED RATE" if aggregate_gap < 0 else "FORECAST ABOVE REALIZED RATE" if aggregate_gap > 0 else "EQUAL"
    calibration_direction = "NOT ESTABLISHED"  # Per-bin signed gaps are mixed; calibration slope did not converge.

    # Chronological quarter and cumulative metrics.
    quarters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in merged:
        quarters[_quarter(row["forecastDate"])].append(row)
    temporal_rows = []
    for quarter, rows in sorted(quarters.items()):
        ps, nps, ys = [r["probability"] for r in rows], [r["naiveProbability"] for r in rows], [r["outcome"] for r in rows]
        mb, nb = _brier(ps, ys), _brier(nps, ys)
        me = _ece(_calibration_bins(ps, ys), len(rows))
        ne = _ece(_calibration_bins(nps, ys), len(rows))
        temporal_rows.append({"quarter": quarter, "sampleCount": len(rows), "positiveRate": statistics.mean(ys),
                              "meanForecast": statistics.mean(ps), "modelBrier": mb, "naiveBrier": nb,
                              "brierDifferenceModelMinusNaive": mb - nb, "modelEce": me, "naiveEce": ne,
                              "modelLowerBrier": mb < nb, "modelHigherBrier": mb > nb})
    cumulative_rows, cumulative_model, cumulative_naive = [], 0.0, 0.0
    rolling_rows = []
    for index, row in enumerate(merged, start=1):
        cumulative_model += row["loss"]
        cumulative_naive += row["naiveLoss"]
        cumulative_rows.append({"index": index, "forecastDate": row["forecastDate"], "target": row["outcome"],
                                "cumulativeModelBrier": cumulative_model / index,
                                "cumulativeNaiveBrier": cumulative_naive / index,
                                "cumulativeBrierDifference": (cumulative_model - cumulative_naive) / index})
        if index >= 20:
            window = merged[index - 20:index]
            rolling_rows.append({"index": index, "windowSize": 20, "startDate": window[0]["forecastDate"],
                                 "endDate": row["forecastDate"], "rollingModelBrier": statistics.mean(r["loss"] for r in window),
                                 "rollingNaiveBrier": statistics.mean(r["naiveLoss"] for r in window),
                                 "rollingForecastMean": statistics.mean(r["probability"] for r in window),
                                 "rollingRealizedPositiveRate": statistics.mean(r["outcome"] for r in window)})

    base_rate_rows = [{"forecastDate": row["forecastDate"], "targetDate": row["targetDate"],
                       "trainingSampleCount": row["trainingSampleCount"], "trainingPositiveCount": row["trainingPositiveCount"],
                       "trainingBaseRate": row["trainingBaseRate"], "forecast": row["probability"], "naiveForecast": row["naiveProbability"],
                       "realizedTarget": row["outcome"]} for row in merged]

    # Feature distribution by calendar quarter, using all frozen clean rows.
    feature_quarters: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in features_rows:
        feature_quarters[_quarter(row["marketDate"])].append(row)
    feature_stability_rows = []
    for quarter, rows in sorted(feature_quarters.items()):
        for feature in FEATURES:
            values = [float(row[feature]) for row in rows]
            feature_stability_rows.append({"quarter": quarter, "feature": feature, "count": len(values),
                                           "mean": statistics.mean(values), "stdPopulation": statistics.pstdev(values),
                                           "median": statistics.median(values), "p10": _quantile(values, .10), "p90": _quantile(values, .90)})

    coefficient_rows = []
    for row in merged:
        for index, name in enumerate(COEFFICIENTS):
            coefficient_rows.append({"forecastDate": row["forecastDate"], "fitCutoff": row["fitCutoff"],
                                     "coefficient": name, "weight": row["weights"][index]})
    coefficient_stability = {}
    for index, name in enumerate(COEFFICIENTS):
        values = [row["weights"][index] for row in merged]
        signs = [1 if value > 0 else -1 if value < 0 else 0 for value in values]
        flips = [{"fromDate": merged[i - 1]["forecastDate"], "toDate": merged[i]["forecastDate"],
                  "fromSign": signs[i - 1], "toSign": signs[i]} for i in range(1, n) if signs[i] != signs[i - 1]]
        coefficient_stability[name] = {"count": len(values), "mean": statistics.mean(values), "median": statistics.median(values),
                                       "stdPopulation": statistics.pstdev(values), "min": min(values), "max": max(values),
                                       "first": values[0], "last": values[-1], "positiveCount": sum(v > 0 for v in values),
                                       "negativeCount": sum(v < 0 for v in values), "exactZeroCount": sum(v == 0 for v in values),
                                       "nearZeroThreshold": "NOT DEFINED; exact sign only", "signTransitions": len(flips),
                                       "signFlipDates": flips}

    # Top errors and per-observation comparison retain all observations.
    sorted_errors = sorted(merged, key=lambda row: (-row["loss"], row["forecastDate"]))
    largest_errors = [{"rank": index, "forecastDate": row["forecastDate"], "targetDate": row["targetDate"],
                       "forecast": row["probability"], "target": row["outcome"], "squaredError": row["loss"],
                       "trainingBaseRate": row["trainingBaseRate"], "trainingSampleCount": row["trainingSampleCount"],
                       **{f"feature_{feature}": row["features"][feature] for feature in FEATURES},
                       **{f"coef_{name}": row["weights"][index] for index, name in enumerate(COEFFICIENTS)}}
                      for index, row in enumerate(sorted_errors[:20], start=1)]
    total_loss = sum(row["loss"] for row in merged)
    error_concentration = {f"top{count}BrierLossShare": sum(row["loss"] for row in sorted_errors[:count]) / total_loss for count in (10, 20)}
    comparison_rows = [{"forecastDate": row["forecastDate"], "targetDate": row["targetDate"], "forecast": row["probability"],
                        "naiveForecast": row["naiveProbability"], "target": row["outcome"], "modelSquaredError": row["loss"],
                        "naiveSquaredError": row["naiveLoss"], "modelMinusNaiveLoss": row["lossDifference"],
                        "modelBetter": row["loss"] < row["naiveLoss"], "modelWorse": row["loss"] > row["naiveLoss"],
                        "tie": row["loss"] == row["naiveLoss"]} for row in merged]
    better = sum(row["lossDifference"] < 0 for row in merged)
    worse = sum(row["lossDifference"] > 0 for row in merged)
    ties = n - better - worse

    # Descriptive full-sample quintiles are explicitly post-hoc, never model inputs.
    feature_outcome_rows = []
    for feature in FEATURES:
        values = [row["features"][feature] for row in merged]
        cutoffs = [_quantile(values, q / 5) for q in (1, 2, 3, 4)]
        for quintile in range(5):
            selected = [row for row in merged if sum(row["features"][feature] > cutoff for cutoff in cutoffs) == quintile]
            feature_outcome_rows.append({"feature": feature, "quintile": quintile + 1, "count": len(selected),
                                         "minimum": min((row["features"][feature] for row in selected), default=None),
                                         "maximum": max((row["features"][feature] for row in selected), default=None),
                                         "actualPositiveRate": statistics.mean(row["outcome"] for row in selected) if selected else None,
                                         "thresholds": json.dumps(cutoffs, separators=(",", ":")),
                                         "classification": "POST-HOC DESCRIPTIVE DIAGNOSTIC; NOT FORECAST INPUT"})

    source_limitations = summary.get("sourceVintageStatus", "NOT PROVEN")
    bss = 1 - model_brier / naive_brier
    auc = _auc(probabilities, outcomes)
    diagnostic_summary = {
        "status": "ROOT CAUSE EVIDENCE AVAILABLE",
        "scope": "P2-03 historical research V1R1 only",
        "evidenceClass": summary.get("evidenceClass"), "contractId": calibration.get("contractId"),
        "modelId": summary.get("model"), "replayRevision": summary.get("replayRevision"),
        "oosPairCount": n, "firstForecastDate": dates[0], "lastForecastDate": dates[-1],
        "inputFingerprints": before_tree, "contractSha256": contract_hash,
        "contractSha256Expected": EXPECTED_CONTRACT_SHA256,
        "metrics": {**recomputed, "modelPositiveRate": statistics.mean(outcomes),
                    "meanForecastMinusRealizedRate": aggregate_gap, "aggregateDirection": aggregate_direction,
                    "calibrationDirection": calibration_direction,
                    "brierSkillScore": bss, "brierSkillSign": "positive" if bss > 0 else "negative" if bss < 0 else "zero",
                    "modelAuc": auc, "accuracyAt050": sum((p >= .5) == bool(y) for p, y in zip(probabilities, outcomes)) / n,
                    "calibrationInterceptSlope": slope, "modelBrierDecomposition": brier_decomp,
                    "naiveBrierDecomposition": naive_decomp,
                    "brierDecompositionCaveat": "Fixed 10-bin grouped decomposition; exact finite-sample identity can differ from ungrouped Brier."},
        "temporalQuarterCount": len(temporal_rows), "quartersModelLowerBrier": sum(row["modelLowerBrier"] for row in temporal_rows),
        "quartersModelHigherBrier": sum(row["modelHigherBrier"] for row in temporal_rows),
        "observationComparison": {"modelBetterCount": better, "modelWorseCount": worse, "tieCount": ties,
                                  "meanLossDifference": statistics.mean(row["lossDifference"] for row in merged),
                                  "medianLossDifference": statistics.median(row["lossDifference"] for row in merged)},
        "errorConcentration": error_concentration,
        "sourceVintage": source_limitations,
        "diagnosticClassification": [],
        "interpretation": "EVIDENCE INCONCLUSIVE",
        "probabilityLabelAllowed": False,
        "productionP2_03": "BLOCKED — INSUFFICIENT PROSPECTIVE OOS CALIBRATION HISTORY",
    }
    classifications = diagnostic_summary["diagnosticClassification"]
    if auc is not None and abs(auc - .5) < .05:
        classifications.append({"category": "WEAK DISCRIMINATION SIGNAL", "evidence": {"auc": auc}})
    else:
        classifications.append({"category": "NOT ESTABLISHED", "evidence": {"auc": auc, "reason": "diagnostic does not establish stable discrimination"}})
    classifications.append({"category": "CALIBRATION BIAS", "evidence": {"aggregateForecastMinusObservedRate": aggregate_gap, "modelEce": model_ece, "naiveEce": naive_ece}})
    classifications.append({"category": "COEFFICIENT INSTABILITY", "evidence": {name: {"signTransitions": values["signTransitions"], "stdPopulation": values["stdPopulation"], "min": values["min"], "max": values["max"]} for name, values in coefficient_stability.items()}})
    classifications.append({"category": "BASE-RATE DRIFT", "evidence": {"trainingBaseRateMin": min(row["trainingBaseRate"] for row in merged),
                                                                                "trainingBaseRateMax": max(row["trainingBaseRate"] for row in merged),
                                                                                "realizedRate": statistics.mean(outcomes),
                                                                                "quarterRates": [{"quarter": row["quarter"], "positiveRate": row["positiveRate"]} for row in temporal_rows]}})
    classifications.append({"category": "NOT ESTABLISHED", "evidence": {"featureDistributionDrift": "Quarter-level descriptive variation is reported, but no prespecified drift threshold or inferential test was authorized."}})
    classifications.append({"category": "NOT ESTABLISHED", "evidence": {"errorConcentration": error_concentration,
                                                                           "interpretation": "Top 10/20 loss shares are quantified; no concentration threshold was prespecified."}})
    classifications.append({"category": "SOURCE LIMITATION", "evidence": {"sourceVintageStatus": source_limitations}})

    # Freeze check after all reads/calculations; no source artifact may change.
    after_tree = _fingerprint_tree(input_dir)
    db_after = _database_snapshot(db_path)
    if before_tree != after_tree:
        raise RuntimeError("V1R1 input artifacts changed during diagnostic")
    if db_before != db_after:
        raise RuntimeError("prospective DB changed during diagnostic")

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "forecast_distribution.json", distribution_summary)
    _write_csv(output_dir / "reliability_bins.csv", reliability_rows,
               ["bin", "lowerInclusive", "upperExclusive", "upperInclusive", "count", "meanForecast", "actualPositiveRate", "absoluteCalibrationGap", "naiveCount", "naiveMeanForecast", "naiveActualPositiveRate", "naiveAbsoluteCalibrationGap"])
    _write_csv(output_dir / "temporal_metrics.csv", temporal_rows, list(temporal_rows[0]))
    _write_csv(output_dir / "rolling_metrics.csv", rolling_rows, list(rolling_rows[0]))
    _write_csv(output_dir / "cumulative_brier.csv", cumulative_rows, list(cumulative_rows[0]))
    _write_csv(output_dir / "base_rate_drift.csv", base_rate_rows, list(base_rate_rows[0]))
    _write_csv(output_dir / "feature_stability.csv", feature_stability_rows, list(feature_stability_rows[0]))
    _write_csv(output_dir / "feature_outcome_quintiles.csv", feature_outcome_rows, list(feature_outcome_rows[0]))
    _write_csv(output_dir / "extreme_forecasts.csv", extreme_rows,
               ["forecastDate", "targetDate", "forecast", "target", "trainingSampleCount", "trainingBaseRate",
                *[f"feature_{feature}" for feature in FEATURES], *[f"coef_{name}" for name in COEFFICIENTS]])
    _write_csv(output_dir / "coefficient_trace.csv", coefficient_rows, list(coefficient_rows[0]))
    _write_json(output_dir / "coefficient_stability.json", coefficient_stability)
    _write_csv(output_dir / "largest_errors.csv", largest_errors, list(largest_errors[0]))
    _write_csv(output_dir / "model_vs_naive.csv", comparison_rows, list(comparison_rows[0]))
    _write_json(output_dir / "diagnostic_summary.json", diagnostic_summary)
    output_hashes = {path.name: _sha256(path) for path in sorted(output_dir.iterdir()) if path.is_file() and path.name != "determinism_report.json"}
    _write_json(output_dir / "determinism_report.json", {
        "status": "INPUT READ-ONLY VERIFIED",
        "twoRunComparison": "RUN SCRIPT TWICE AND COMPARE OUTPUT HASHES; regression test does this in isolated temp dirs",
        "inputTreeFingerprintBefore": before_tree,
        "inputTreeFingerprintAfter": after_tree,
        "outputHashes": output_hashes,
        "prospectiveDbBefore": db_before,
        "prospectiveDbAfter": db_after,
        "prospectiveDbUnchanged": True,
    })
    return diagnostic_summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    result = analyze(args.input_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
