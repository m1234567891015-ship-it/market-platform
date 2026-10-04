"""Read-only TX contract-month roll exposure audit for P2-03 Research V1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / ".tmp" / "p203-historical-asof-replay" / "taifex_tx_daily_normalized.json"
V1_DIR = ROOT / ".tmp" / "p203-historical-research-v1"
OUTPUT_DIR = ROOT / ".tmp" / "p203-contract-roll-audit"
CONTRACT_PATH = ROOT / "docs" / "P2_03_HISTORICAL_RESEARCH_FEATURE_CONTRACT_V1.md"
DB_PATH = ROOT / "data" / "p203-prospective-ledger.sqlite3"
EXPECTED_INPUT_SHA256 = "90b5f772a19e230d2212f66a1c522be0e95801f03fd8079d33235a16d3106930"
EXPECTED_RESEARCH_CONTRACT_SHA256 = "79eef16aec59844574b2dbde321a57f0982c844d25b334267eb48808d923f63d"
EXPECTED_V1_SHA256 = {
    "feature_contract.json": "79eef16aec59844574b2dbde321a57f0982c844d25b334267eb48808d923f63d",
    "feature_matrix.csv": "dc66541b5804c0574817458196a67cce98bbf4190eb313db2dfe9e432d42a6f1",
    "reconstructed_forecasts.csv": "73a4222e8035d49a57cfb14b9193ea7f72fd56ad82f073d72c2d0018c90b8398",
    "oos_pairs.csv": "4ced3f1a1d9368cf98a15a3f67a9ea4e2237212737be031ee03e677fe7cf0126",
    "training_trace.jsonl": "359a82ab00afbcee8bd4f65c2d109e76fc53bd80c8ec8406ce927efcbe6e6a63",
    "eligibility_funnel.json": "ac90296b5a1d8d68b6e7029b82415c241802dc8d4eff4bd8edf9075f698e02b4",
    "calibration_report.json": "de64d69ddf5794d4f5a566df3f010f27f1a4c4482896dc902371e843591a3cc8",
    "determinism_report.json": "f31cc8a211099292c5d590d7848f438f9f5056be8227bc5b18dca823fce07d03",
    "research_summary.json": "d82a2967d35b75c7b2590da2c552a3aa629a8e80982c87d268494e514b8e8416",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_inputs(input_path: Path = INPUT_PATH, v1_dir: Path = V1_DIR) -> dict[str, Any]:
    input_hash = _sha256(input_path)
    if input_hash != EXPECTED_INPUT_SHA256:
        raise ValueError(f"historical input drift: expected {EXPECTED_INPUT_SHA256}, got {input_hash}")
    contract_hash = _sha256(v1_dir / "feature_contract.json")
    if contract_hash != EXPECTED_RESEARCH_CONTRACT_SHA256:
        raise ValueError(f"research contract drift: expected {EXPECTED_RESEARCH_CONTRACT_SHA256}, got {contract_hash}")
    v1_hashes = {name: _sha256(v1_dir / name) for name in EXPECTED_V1_SHA256}
    for name, expected in EXPECTED_V1_SHA256.items():
        if v1_hashes[name] != expected:
            raise ValueError(f"V1 artifact drift for {name}: expected {expected}, got {v1_hashes[name]}")
    rows = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("historical dataset must be a non-empty JSON list")
    dates = [str(row.get("time") or "") for row in rows]
    if dates != sorted(dates) or len(set(dates)) != len(dates):
        raise ValueError("historical market dates are not strictly ordered and unique")
    months = [str(row.get("contractMonth") or "").strip() for row in rows]
    if any(not month for month in months):
        raise ValueError("contractMonth is missing from one or more sessions")
    return {
        "rows": rows,
        "inputHash": input_hash,
        "contractHash": contract_hash,
        "contractDocumentHash": _sha256(CONTRACT_PATH),
        "v1Hashes": v1_hashes,
        "featureRows": _load_csv(v1_dir / "feature_matrix.csv"),
        "forecasts": _load_csv(v1_dir / "reconstructed_forecasts.csv"),
        "pairs": _load_csv(v1_dir / "oos_pairs.csv"),
        "trainingTrace": [json.loads(line) for line in (v1_dir / "training_trace.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()],
    }


def _float(value: Any) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite value in historical or V1 artifact")
    return parsed


def analyze(inputs: dict[str, Any]) -> dict[str, bytes]:
    rows = inputs["rows"]
    date_index = {row["time"]: idx for idx, row in enumerate(rows)}
    month_by_date = {row["time"]: str(row["contractMonth"]) for row in rows}
    boundaries = []
    for idx in range(1, len(rows)):
        old = rows[idx - 1]
        new = rows[idx]
        if str(old["contractMonth"]) != str(new["contractMonth"]):
            boundaries.append({
                "transitionDate": new["time"],
                "priorDate": old["time"],
                "oldContractMonth": old["contractMonth"],
                "newContractMonth": new["contractMonth"],
                "oldClose": old.get("close"), "newClose": new.get("close"),
                "oldVolume": old.get("volume"), "newVolume": new.get("volume"),
                "oldOpenInterest": old.get("openInterest"), "newOpenInterest": new.get("openInterest"),
            })
    boundary_dates = {row["transitionDate"] for row in boundaries}

    month_sessions: dict[str, list[str]] = {}
    for row in rows:
        month_sessions.setdefault(str(row["contractMonth"]), []).append(str(row["time"]))
    inventory = [
        {"contractMonth": month, "firstDate": dates[0], "lastDate": dates[-1], "sessions": len(dates)}
        for month, dates in sorted(month_sessions.items())
    ]

    feature_exposure = []
    feature_by_date = {}
    for feature in inputs["featureRows"]:
        market_date = feature["marketDate"]
        idx = date_index[market_date]
        momentum_cross = idx >= 5 and month_by_date[market_date] != str(rows[idx - 5]["contractMonth"])
        oi_cross = idx >= 1 and month_by_date[market_date] != str(rows[idx - 1]["contractMonth"])
        boundary = market_date in boundary_dates
        record = {
            "marketDate": market_date,
            "contractMonth": month_by_date[market_date],
            "momentum5AnchorContractMonth": str(rows[idx - 5]["contractMonth"]) if idx >= 5 else "",
            "oiPriorContractMonth": str(rows[idx - 1]["contractMonth"]) if idx >= 1 else "",
            "momentum5": feature["momentum_5"],
            "rangePct1": feature["range_pct_1"],
            "openInterestChange1": feature["open_interest_change_1"],
            "crossContractMomentum5": momentum_cross,
            "crossContractOiChange1": oi_cross,
            "featureRollAffected": momentum_cross or oi_cross,
            "rollBoundarySession": boundary,
            "researchDirection": feature["researchDirection"],
        }
        feature_exposure.append(record)
        feature_by_date[market_date] = record

    pair_exposure = []
    for pair in inputs["pairs"]:
        forecast_date = pair["forecastDate"]
        target_date = pair["targetDate"]
        forecast_feature = feature_by_date[forecast_date]
        target_cross = month_by_date[forecast_date] != month_by_date[target_date]
        forecast_boundary = forecast_date in boundary_dates
        target_boundary = target_date in boundary_dates
        feature_affected = bool(forecast_feature["featureRollAffected"])
        labels = []
        if feature_affected:
            labels.append("ROLL_AFFECTED_FEATURE")
        if forecast_boundary:
            labels.append("ROLL_BOUNDARY_FORECAST_DATE")
        if target_boundary or target_cross:
            labels.append("ROLL_BOUNDARY_TARGET_DATE")
        if not labels:
            labels.append("CLEAN_PAIR")
        pair_exposure.append({
            "forecastDate": forecast_date,
            "targetDate": target_date,
            "forecastContractMonth": month_by_date[forecast_date],
            "targetContractMonth": month_by_date[target_date],
            "researchDirection": pair["researchDirection"],
            "momentum5CrossContract": bool(forecast_feature["crossContractMomentum5"]),
            "oiChange1CrossContract": bool(forecast_feature["crossContractOiChange1"]),
            "featureRollAffected": feature_affected,
            "forecastDateRollBoundary": forecast_boundary,
            "targetDateRollBoundary": target_boundary,
            "targetCrossesContractMonth": target_cross,
            "crossContractTargetReturn": target_cross,
            "classifications": labels,
            "primaryClassification": labels[-1] if labels[-1] != "CLEAN_PAIR" else "CLEAN_PAIR",
            "decisionAlignedReturn": pair["decisionAlignedReturn"],
            "probability": pair["probability"],
        })

    # Reconstruct the frozen V1 training-label eligibility only for attribution.
    candidate_labels = []
    feature_map = feature_by_date
    for idx, row in enumerate(rows):
        current_date = str(row["time"])
        feature = feature_map.get(current_date)
        if feature is None or idx + 1 >= len(rows):
            continue
        momentum = _float(feature["momentum5"])
        if momentum == 0:
            continue
        close_now = _float(row["close"])
        close_next = _float(rows[idx + 1]["close"])
        direction_sign = 1 if momentum > 0 else -1
        aligned = direction_sign * (close_next / close_now - 1.0)
        if aligned == 0:
            continue
        candidate_labels.append({
            "decisionDate": current_date,
            "targetDate": str(rows[idx + 1]["time"]),
            "value": 1 if aligned > 0 else 0,
            "featureRollAffected": bool(feature["featureRollAffected"]),
            "targetRollAffected": str(row["contractMonth"]) != str(rows[idx + 1]["contractMonth"]),
        })
    training_by_forecast = []
    trace_by_forecast = {item["forecastDate"]: item for item in inputs["trainingTrace"]}
    for forecast in inputs["forecasts"]:
        forecast_date = forecast["forecastDate"]
        training = [label for label in candidate_labels if label["decisionDate"] < forecast_date and label["targetDate"] < forecast_date]
        expected_count = int(forecast["trainingSampleCount"])
        if len(training) != expected_count:
            raise ValueError(f"training reconstruction mismatch at {forecast_date}: {len(training)} != {expected_count}")
        trace = trace_by_forecast.get(forecast_date)
        if trace is None:
            raise ValueError(f"training trace missing for forecast {forecast_date}")
        positive_count = sum(int(label["value"]) for label in training)
        negative_count = len(training) - positive_count
        start_target = training[0]["targetDate"] if training else None
        end_target = training[-1]["targetDate"] if training else None
        for field, actual in (
            ("trainingPositiveCount", positive_count),
            ("trainingNegativeCount", negative_count),
            ("trainingStartTargetDate", start_target),
            ("trainingEndTargetDate", end_target),
        ):
            if trace.get(field) != actual:
                raise ValueError(f"training trace mismatch at {forecast_date} for {field}: {actual} != {trace.get(field)}")
        target_contaminated = sum(label["targetRollAffected"] for label in training)
        feature_contaminated = sum(label["featureRollAffected"] for label in training)
        any_contaminated = sum(label["featureRollAffected"] or label["targetRollAffected"] for label in training)
        training_by_forecast.append({
            "forecastDate": forecast_date,
            "trainingSampleCount": len(training),
            "trainingPositiveCount": positive_count,
            "trainingNegativeCount": negative_count,
            "trainingStartTargetDate": start_target,
            "trainingEndTargetDate": end_target,
            "traceReconstructionMatched": True,
            "rollAffectedTrainingLabels": target_contaminated,
            "targetRollAffectedTrainingLabels": target_contaminated,
            "featureRollAffectedTrainingLabels": feature_contaminated,
            "anyRollAffectedTrainingLabels": any_contaminated,
            "containsRollAffectedLabel": any_contaminated > 0,
            "containsRollAffectedFeature": feature_contaminated > 0,
            "containsRollAffectedTarget": target_contaminated > 0,
        })

    extremes = {}
    for feature_name, field_name in (("momentum_5", "momentum5"), ("open_interest_change_1", "openInterestChange1")):
        ordered = sorted(feature_exposure, key=lambda item: abs(_float(item[field_name])), reverse=True)[:10]
        extremes[feature_name] = [
            {
                "marketDate": item["marketDate"],
                "value": _float(item[field_name]),
                "absoluteValue": abs(_float(item[field_name])),
                "rollAffected": item["crossContractMomentum5"] if feature_name == "momentum_5" else item["crossContractOiChange1"],
                "rollBoundarySession": item["rollBoundarySession"],
                "contractMonth": item["contractMonth"],
            }
            for item in ordered
        ]

    feature_count = len(feature_exposure)
    pair_count = len(pair_exposure)
    feature_cross_momentum = [item for item in feature_exposure if item["crossContractMomentum5"]]
    feature_cross_oi = [item for item in feature_exposure if item["crossContractOiChange1"]]
    feature_either = [item for item in feature_exposure if item["featureRollAffected"]]
    pair_feature = [item for item in pair_exposure if item["featureRollAffected"]]
    pair_target = [item for item in pair_exposure if item["targetCrossesContractMonth"]]
    pair_forecast_boundary = [item for item in pair_exposure if item["forecastDateRollBoundary"]]
    pair_clean = [item for item in pair_exposure if item["classifications"] == ["CLEAN_PAIR"]]
    pair_both = [item for item in pair_exposure if item["featureRollAffected"] and item["targetCrossesContractMonth"]]
    training_contaminated = [item for item in training_by_forecast if item["containsRollAffectedLabel"]]
    training_feature_contaminated = [item for item in training_by_forecast if item["containsRollAffectedFeature"]]
    training_target_contaminated = [item for item in training_by_forecast if item["containsRollAffectedTarget"]]
    mean_training_roll_labels = (
        sum(item["anyRollAffectedTrainingLabels"] for item in training_by_forecast) / len(training_by_forecast)
        if training_by_forecast else 0.0
    )
    report = {
        "audit": "P2-03 TX CONTRACT-ROLL INTEGRITY AUDIT",
        "dataset": {"sha256": inputs["inputHash"], "sessions": len(rows), "firstDate": rows[0]["time"], "lastDate": rows[-1]["time"]},
        "researchContractSha256": inputs["contractHash"],
        "researchContractDocumentSha256": inputs["contractDocumentHash"],
        "v1ArtifactSha256": inputs["v1Hashes"],
        "contractSelectionSemantics": {
            "currentRepoRule": "parse_taifex_futures_download_candles filters symbol/general session and, without an explicit contract_month, keeps the highest-volume contract row per date.",
            "historicalArtifactSpecificRule": "NOT DETERMINABLE: the 400-row artifact has no raw competing contract rows or generating command/log. Its source label and one-row-per-date layout are consistent with the parser but do not prove the exact selection path.",
            "frontMonthOrNearestExpiry": "NOT PROVEN; current parser behavior is highest daily volume when no month is requested.",
            "codeHistory": "No material max-volume selection-rule drift found in the inspected Git history from introduction at 7d98e29 through current code; efeb0d0 hardened null-volume ranking. The audited dataset has no missing volume values.",
            "historicalSelectionConsistency": "NOT DETERMINABLE for artifact-specific rows; raw per-contract source rows are absent.",
        },
        "contractMonthInventory": inventory,
        "rollBoundaries": boundaries,
        "featureExposure": {
            "featureRows": feature_count,
            "momentum5CrossContractCount": len(feature_cross_momentum),
            "momentum5CrossContractPercent": len(feature_cross_momentum) / feature_count * 100 if feature_count else 0,
            "momentum5AffectedDates": [item["marketDate"] for item in feature_cross_momentum],
            "openInterestChange1CrossContractCount": len(feature_cross_oi),
            "openInterestChange1CrossContractPercent": len(feature_cross_oi) / feature_count * 100 if feature_count else 0,
            "openInterestChange1AffectedDates": [item["marketDate"] for item in feature_cross_oi],
            "eitherFeatureCrossContractCount": len(feature_either),
            "eitherFeatureCrossContractPercent": len(feature_either) / feature_count * 100 if feature_count else 0,
            "eitherFeatureAffectedDates": [item["marketDate"] for item in feature_either],
            "rangePct1DirectCrossContractDependency": False,
            "rangePct1RollBoundarySessionCount": sum(bool(item["rollBoundarySession"]) for item in feature_exposure),
            "researchDirectionsFromCrossContractMomentum": len(feature_cross_momentum),
        },
        "oosPairExposure": {
            "pairCount": pair_count,
            "cleanPairCount": len(pair_clean),
            "featureRollAffectedCount": len(pair_feature),
            "forecastDateRollBoundaryCount": len(pair_forecast_boundary),
            "targetRollAffectedCount": len(pair_target),
            "targetCrossContractReturnCount": len(pair_target),
            "bothFeatureAndTargetAffectedCount": len(pair_both),
            "anyPotentialRollExposureCount": pair_count - len(pair_clean),
            "anyPotentialRollExposurePercent": (pair_count - len(pair_clean)) / pair_count * 100 if pair_count else 0,
            "exclusivePrimaryClassificationCounts": {
                "ROLL_BOUNDARY_TARGET_DATE": sum(item["primaryClassification"] == "ROLL_BOUNDARY_TARGET_DATE" for item in pair_exposure),
                "ROLL_BOUNDARY_FORECAST_DATE": sum(item["primaryClassification"] == "ROLL_BOUNDARY_FORECAST_DATE" for item in pair_exposure),
                "ROLL_AFFECTED_FEATURE": sum(item["primaryClassification"] == "ROLL_AFFECTED_FEATURE" for item in pair_exposure),
                "CLEAN_PAIR": len(pair_clean),
            },
            "targetAffectedDates": [item["targetDate"] for item in pair_target],
        },
        "trainingExposure": {
            "forecastCount": len(training_by_forecast),
            "forecastCountMatchingFrozenTrainingTrace": sum(item["traceReconstructionMatched"] for item in training_by_forecast),
            "forecastCountWithAtLeastOneRollAffectedTrainingLabel": len(training_contaminated),
            "forecastCountWithAtLeastOneRollAffectedFeature": len(training_feature_contaminated),
            "forecastCountWithAtLeastOneRollAffectedTarget": len(training_target_contaminated),
            "averageRollAffectedTrainingLabelsPerTrainingSet": mean_training_roll_labels,
            "averageRollAffectedLabelsPerTrainingSet": mean_training_roll_labels,
            "maximumRollAffectedLabelsInOneTrainingSet": max((item["anyRollAffectedTrainingLabels"] for item in training_by_forecast), default=0),
            "maximumFeatureRollAffectedLabelsInOneTrainingSet": max((item["featureRollAffectedTrainingLabels"] for item in training_by_forecast), default=0),
            "maximumTargetRollAffectedLabelsInOneTrainingSet": max((item["targetRollAffectedTrainingLabels"] for item in training_by_forecast), default=0),
            "byForecast": training_by_forecast,
        },
        "extremeFeatures": extremes,
        "semanticDrift": "NOT DETERMINABLE for the historical artifact-specific selector; the current code's max-volume rule appears stable over inspected history, but raw competing rows and the artifact creation trace are absent.",
        "conclusion": "EXPOSURE PRESENT" if (feature_either or pair_target or pair_forecast_boundary) else "EXPOSURE NOT PRESENT",
        "calibrationInterpretation": "EVIDENCE INCONCLUSIVE (unchanged)",
        "productionP2_03": "BLOCKED",
        "probabilityLabelAllowed": False,
    }

    feature_csv_columns = ["marketDate", "contractMonth", "momentum5AnchorContractMonth", "oiPriorContractMonth", "momentum5", "rangePct1", "openInterestChange1", "crossContractMomentum5", "crossContractOiChange1", "featureRollAffected", "rollBoundarySession", "researchDirection"]
    boundary_csv_columns = ["transitionDate", "priorDate", "oldContractMonth", "newContractMonth", "oldClose", "newClose", "oldVolume", "newVolume", "oldOpenInterest", "newOpenInterest"]
    pair_csv_columns = ["forecastDate", "targetDate", "forecastContractMonth", "targetContractMonth", "researchDirection", "momentum5CrossContract", "oiChange1CrossContract", "featureRollAffected", "forecastDateRollBoundary", "targetDateRollBoundary", "targetCrossesContractMonth", "crossContractTargetReturn", "classifications", "primaryClassification", "decisionAlignedReturn", "probability"]
    training_json = {
        key: value for key, value in report["trainingExposure"].items() if key != "byForecast"
    }
    output: dict[str, bytes] = {
        "contract_month_inventory.json": _canonical(inventory) + b"\n",
        "roll_boundaries.csv": _csv_bytes(boundaries, boundary_csv_columns),
        "feature_roll_exposure.csv": _csv_bytes(feature_exposure, feature_csv_columns),
        "oos_pair_roll_exposure.csv": _csv_bytes(pair_exposure, pair_csv_columns),
        "training_roll_exposure.json": _canonical(report["trainingExposure"]) + b"\n",
        "roll_integrity_report.json": _canonical(report) + b"\n",
    }
    # Keep the JSON report compact by leaving detailed per-forecast training rows in their own file.
    report["trainingExposure"] = training_json
    output["roll_integrity_report.json"] = _canonical(report) + b"\n"
    return output


def _csv_bytes(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        prepared = dict(row)
        if isinstance(prepared.get("classifications"), list):
            prepared["classifications"] = ";".join(prepared["classifications"])
        writer.writerow(prepared)
    return buffer.getvalue().encode("utf-8")


def _db_snapshot(path: Path = DB_PATH) -> dict[str, Any]:
    result = {"sha256": _sha256(path)}
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        result["decisionCount"] = connection.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]
        result["outcomeCount"] = connection.execute("SELECT COUNT(*) FROM decision_outcome").fetchone()[0]
    finally:
        connection.close()
    return result


def execute(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing audit outputs: {output_dir}")
    inputs = load_inputs()
    db_before = _db_snapshot()
    first = analyze(inputs)
    second = analyze(inputs)
    first_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in first.items()}
    second_hashes = {name: hashlib.sha256(data).hexdigest() for name, data in second.items()}
    if first_hashes != second_hashes:
        raise RuntimeError("contract-roll audit is not deterministic")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in second.items():
        (output_dir / name).write_bytes(content)
    after = load_inputs()
    db_after = _db_snapshot()
    if (inputs["inputHash"] != after["inputHash"] or inputs["contractHash"] != after["contractHash"]
            or inputs["contractDocumentHash"] != after["contractDocumentHash"] or inputs["v1Hashes"] != after["v1Hashes"]):
        raise RuntimeError("input, research contract, or V1 artifact changed during audit")
    if db_before != db_after:
        raise RuntimeError("prospective database changed during read-only audit")
    return {
        "outputDir": str(output_dir),
        "artifactSha256": second_hashes,
        "datasetSha256": inputs["inputHash"],
        "contractSha256": inputs["contractHash"],
        "v1ArtifactsBeforeAfterIdentical": True,
        "prospectiveDbBeforeAfterIdentical": db_before,
        "twoAuditRunsIdentical": True,
        "summary": json.loads(second["roll_integrity_report.json"].decode("utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    print(json.dumps(execute(args.output_dir), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
