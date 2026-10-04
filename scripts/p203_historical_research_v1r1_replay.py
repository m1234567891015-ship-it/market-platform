"""Rebuild a contract-roll-clean TX research dataset and run frozen V1 replay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fetchers import (
    TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
    USER_AGENT,
    parse_taifex_futures_download_candles,
    parse_taifex_market_number,
)
from security import _urlopen_with_ssl_fallback
from scripts import p203_historical_research_replay as v1


OUTPUT_DIR = ROOT / ".tmp" / "p203-historical-research-v1r1"
RAW_DIR = OUTPUT_DIR / "raw"
OLD_DATASET_PATH = ROOT / ".tmp" / "p203-historical-asof-replay" / "taifex_tx_daily_normalized.json"
V1_DIR = ROOT / ".tmp" / "p203-historical-research-v1"
CONTRACT_PATH = V1_DIR / "feature_contract.json"
DB_PATH = ROOT / "data" / "p203-prospective-ledger.sqlite3"
START_DATE = date(2024, 12, 6)
END_DATE = date(2026, 10, 1)
EXPECTED_OLD_DATA_SHA256 = "90b5f772a19e230d2212f66a1c522be0e95801f03fd8079d33235a16d3106930"
EXPECTED_CONTRACT_SHA256 = "79eef16aec59844574b2dbde321a57f0982c844d25b334267eb48808d923f63d"
EXPECTED_V1_INTERNAL_HASHES = {
    "featureRows": "c7607afe3d91f54bb811bc3374f82be4789df5e885c8092254096ce01e799300",
    "forecasts": "211adca196ed69df04c48fbf7ab824771989235cd49ea12bcf89c0a5e6b560de",
    "pairs": "0c38caf5afef5c1a4b0c491531b4974f4042b12d406e9b09116dff2d2892019f",
}
EXPECTED_V1_FILE_HASHES = {
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
EXPECTED_DB_SHA256 = "73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4"
ROLL_POLICY = "CONTRACT_ROLL_CLEAN_V1"
SELECTION_RULE = "HIGHEST_DAILY_VOLUME_TX_CONTRACT; TIES_KEEP_FIRST_ELIGIBLE_ROW_IN_SOURCE_ORDER"
PROVENANCE = "HISTORICAL_RESEARCH_AS_OF_OOS"
RAW_WINDOW_DAYS = 28  # Keep requests below the endpoint's observed one-calendar-month limit.


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _read_csv_bytes(raw_bytes: bytes, content_type: str) -> tuple[str, list[list[str]]]:
    encoding = "cp950" if "ms950" in content_type.lower() or "big5" in content_type.lower() else "utf-8"
    text = raw_bytes.decode(encoding, errors="strict")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2 or len(rows[0]) < 18:
        raise ValueError("TAIFEX response is not a recognizable daily TX CSV")
    return text, rows


def _windows(start: date = START_DATE, end: date = END_DATE) -> list[tuple[date, date]]:
    result = []
    cursor = start
    while cursor <= end:
        last = min(cursor + timedelta(days=RAW_WINDOW_DAYS - 1), end)
        result.append((cursor, last))
        cursor = last + timedelta(days=1)
    return result


def retrieve_raw_windows(
    endpoint: str = TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
    timeout: int = 40,
    pause_seconds: float = 0.15,
) -> list[dict[str, Any]]:
    """Fetch exact response bytes in memory; caller persists them only after all pass."""
    windows = _windows()
    responses = []
    for index, (start, end) in enumerate(windows):
        fields = {
            "down_type": "1",
            "commodity_id": "TX",
            "commodity_id2": "",
            "queryStartDate": start.strftime("%Y/%m/%d"),
            "queryEndDate": end.strftime("%Y/%m/%d"),
        }
        body = urlencode(sorted((str(key), str(value)) for key, value in fields.items())).encode("utf-8")
        request = Request(endpoint, data=body, headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _urlopen_with_ssl_fallback(request, timeout) as response:
            status = int(response.status)
            content_type = str(response.headers.get("Content-Type") or "")
            raw_bytes = response.read()
        if status != 200:
            raise RuntimeError(f"TAIFEX HTTP {status} for window {start}..{end}")
        try:
            text, parsed_rows = _read_csv_bytes(raw_bytes, content_type)
        except (UnicodeError, ValueError) as exc:
            prefix = raw_bytes[:240].decode("cp950", errors="replace").replace("\r", " ").replace("\n", " ")
            raise RuntimeError(
                f"TAIFEX raw window {start}..{end} was not valid CSV "
                f"(HTTP {status}, content-type={content_type!r}, bytes={len(raw_bytes)}, prefix={prefix!r})"
            ) from exc
        parsed_dates = [str(row[0]).strip().replace("/", "-") for row in parsed_rows[1:] if row and row[0].strip()]
        responses.append({
            "windowIndex": index,
            "windowStart": start.isoformat(),
            "windowEnd": end.isoformat(),
            "retrievedAt": retrieved_at,
            "sourceUrl": endpoint,
            "httpStatus": status,
            "contentType": content_type,
            "rawBytes": raw_bytes,
            "text": text,
            "csvRows": parsed_rows,
            "rawDataRowCount": max(0, len(parsed_rows) - 1),
            "firstResponseDate": min(parsed_dates) if parsed_dates else None,
            "lastResponseDate": max(parsed_dates) if parsed_dates else None,
        })
        if pause_seconds and index + 1 < len(windows):
            time.sleep(pause_seconds)
    return responses


def _eligible_candidates(csv_rows: list[list[str]]) -> tuple[dict[str, list[dict[str, Any]]], int]:
    by_date: dict[str, list[dict[str, Any]]] = {}
    raw_data_rows = 0
    for row in csv_rows[1:]:
        raw_data_rows += 1
        if len(row) < 18:
            continue
        market_date = str(row[0] or "").strip().replace("/", "-")
        symbol = str(row[1] or "").strip().upper()
        contract_month = str(row[2] or "").strip()
        session = str(row[17] or "").strip()
        if symbol != "TX" or session != "一般" or not market_date or "/" in contract_month:
            continue
        open_value = parse_taifex_market_number(row[3])
        high_value = parse_taifex_market_number(row[4])
        low_value = parse_taifex_market_number(row[5])
        close_value = parse_taifex_market_number(row[6])
        if None in {open_value, high_value, low_value, close_value}:
            continue
        candidate = {
            "time": market_date,
            "contractMonth": contract_month,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "close": close_value,
            "change": parse_taifex_market_number(row[7]),
            "changePct": parse_taifex_market_number(str(row[8] or "").replace("%", "")),
            "volume": parse_taifex_market_number(row[9]),
            "settlement": parse_taifex_market_number(row[10]),
            "openInterest": parse_taifex_market_number(row[11]),
            "source": "TAIFEX 期貨每日行情下載",
        }
        candidate["_sourceOrder"] = len(by_date.setdefault(market_date, []))
        by_date[market_date].append(candidate)
    return by_date, raw_data_rows


def select_daily_series(responses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    all_candidates: dict[str, list[dict[str, Any]]] = {}
    response_row_count = 0
    for response in responses:
        candidates, raw_rows = _eligible_candidates(response["csvRows"])
        response_row_count += raw_rows
        # Run the actual checked-in parser over each exact raw response and assert
        # our provenance reconstruction follows its selector and tie behavior.
        parser_selected = parse_taifex_futures_download_candles(response["text"], "TX")
        for item in parser_selected:
            day_candidates = candidates.get(str(item["time"]), [])
            if not day_candidates:
                raise ValueError(f"parser selected a row absent from candidate inventory: {item['time']}")
            best_score = max(candidate["volume"] if candidate["volume"] is not None else -1 for candidate in day_candidates)
            expected = next(candidate for candidate in day_candidates if (candidate["volume"] if candidate["volume"] is not None else -1) == best_score)
            if any(item.get(key) != expected.get(key) for key in ("contractMonth", "open", "high", "low", "close", "volume", "openInterest", "settlement")):
                raise ValueError(f"highest-volume reconstruction differs from repository parser on {item['time']}")
            all_candidates.setdefault(str(item["time"]), []).extend(day_candidates)
    selected = []
    trace = []
    tie_dates = []
    for market_date in sorted(all_candidates):
        candidates = all_candidates[market_date]
        scored = [(candidate["volume"] if candidate["volume"] is not None else -1, candidate) for candidate in candidates]
        max_volume = max(score for score, _ in scored)
        winners = [candidate for score, candidate in scored if score == max_volume]
        chosen = winners[0]
        if len(winners) > 1:
            tie_dates.append(market_date)
        clean = {key: value for key, value in chosen.items() if not key.startswith("_")}
        selected.append(clean)
        reason = "HIGHEST_VOLUME" if len(winners) == 1 else "HIGHEST_VOLUME_TIE_FIRST_SOURCE_ROW"
        trace.append({
            "marketDate": market_date,
            "selectedContractMonth": chosen["contractMonth"],
            "selectedVolume": chosen["volume"],
            "candidateContractCount": len(candidates),
            "candidateDistinctContractMonths": len({candidate["contractMonth"] for candidate in candidates}),
            "selectionRule": "HIGHEST_DAILY_VOLUME_TX_CONTRACT",
            "selectionReason": reason,
        })
    summary = {
        "rawDataRows": response_row_count,
        "eligibleCandidateRows": sum(len(items) for items in all_candidates.values()),
        "marketSessions": len(selected),
        "distinctContractMonths": sorted({str(candidate["contractMonth"]) for items in all_candidates.values() for candidate in items}),
        "selectedDistinctContractMonths": sorted({str(row["contractMonth"]) for row in selected}),
        "tieMarketDates": tie_dates,
        "tiePolicy": "Existing parser replaces only on strictly greater volume; first eligible maximum-volume row in source order wins.",
    }
    return selected, trace, summary


def compare_old_vs_rebuilt(old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    old_by_date = {str(row["time"]): row for row in old_rows}
    new_by_date = {str(row["time"]): row for row in new_rows}
    all_dates = sorted(set(old_by_date) | set(new_by_date))
    comparison = []
    contract_mismatches = price_mismatches = volume_mismatches = oi_mismatches = 0
    for day in all_dates:
        old = old_by_date.get(day)
        new = new_by_date.get(day)
        contract_match = old is not None and new is not None and str(old.get("contractMonth")) == str(new.get("contractMonth"))
        close_match = old is not None and new is not None and old.get("close") == new.get("close")
        volume_match = old is not None and new is not None and old.get("volume") == new.get("volume")
        oi_match = old is not None and new is not None and old.get("openInterest") == new.get("openInterest")
        if old is not None and new is not None:
            contract_mismatches += not contract_match
            price_mismatches += not close_match
            volume_mismatches += not volume_match
            oi_mismatches += not oi_match
        comparison.append({
            "marketDate": day,
            "oldContractMonth": old.get("contractMonth") if old else None,
            "newContractMonth": new.get("contractMonth") if new else None,
            "contractMatch": contract_match,
            "oldClose": old.get("close") if old else None,
            "newClose": new.get("close") if new else None,
            "closeMatch": close_match,
            "oldVolume": old.get("volume") if old else None,
            "newVolume": new.get("volume") if new else None,
            "volumeMatch": volume_match,
            "oldOpenInterest": old.get("openInterest") if old else None,
            "newOpenInterest": new.get("openInterest") if new else None,
            "openInterestMatch": oi_match,
        })
    return comparison, {
        "oldSessionCount": len(old_rows),
        "rebuiltSessionCount": len(new_rows),
        "matchingSessionDates": sum(day in old_by_date and day in new_by_date for day in all_dates),
        "missingRebuiltDates": sorted(set(old_by_date) - set(new_by_date)),
        "additionalRebuiltDates": sorted(set(new_by_date) - set(old_by_date)),
        "contractMonthMismatches": contract_mismatches,
        "closeMismatches": price_mismatches,
        "volumeMismatches": volume_mismatches,
        "openInterestMismatches": oi_mismatches,
    }


def _features_and_candidates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    features_out = []
    candidates = []
    counts = {
        "totalMarketSessions": len(rows),
        "dailySelectedRows": len(rows),
        "momentumWarmup": min(v1.WARMUP_SESSIONS, len(rows)),
        "crossContractMomentum": 0,
        "crossContractOi": 0,
        "featureIncomplete": 0,
        "directionUnavailable": 0,
        "crossContractTarget": 0,
        "flatTarget": 0,
        "targetUnavailable": 0,
        "cleanFeatureRows": 0,
        "cleanMaturedLabels": 0,
    }
    for index, row in enumerate(rows):
        if index < v1.WARMUP_SESSIONS:
            continue
        month = str(row["contractMonth"])
        momentum_clean = all(str(rows[pos]["contractMonth"]) == month for pos in range(index - v1.WARMUP_SESSIONS, index + 1))
        oi_clean = str(rows[index - 1]["contractMonth"]) == month
        counts["crossContractMomentum"] += not momentum_clean
        counts["crossContractOi"] += not oi_clean
        features = v1.derive_features(rows, index)
        if features is None:
            counts["featureIncomplete"] += 1
            candidates.append({"index": index, "status": "FEATURE_INCOMPLETE"})
            continue
        if not momentum_clean or not oi_clean:
            status = "EXCLUDED_CROSS_CONTRACT_MOMENTUM_5" if not momentum_clean else "EXCLUDED_CROSS_CONTRACT_OI_CHANGE"
            if not momentum_clean and not oi_clean:
                status = "EXCLUDED_CROSS_CONTRACT_MOMENTUM_5_AND_OI_CHANGE"
            candidates.append({"index": index, "status": status, "features": features})
            continue
        momentum = features["momentum_5"]
        direction = "RESEARCH_LONG" if momentum > 0 else "RESEARCH_SHORT" if momentum < 0 else "UNAVAILABLE"
        feature_row = {
            "marketDate": row["time"],
            "selectedContractMonth": row["contractMonth"],
            "researchDirection": direction,
            **features,
            "replayRevision": "V1R1",
            "rollPolicy": ROLL_POLICY,
        }
        features_out.append(feature_row)
        counts["cleanFeatureRows"] += 1
        if direction == "UNAVAILABLE":
            counts["directionUnavailable"] += 1
            candidates.append({"index": index, "status": "RESEARCH_DIRECTION_UNAVAILABLE", "features": features})
            continue
        if index + 1 >= len(rows):
            counts["targetUnavailable"] += 1
            candidates.append({"index": index, "status": "TARGET_UNAVAILABLE", "features": features})
            continue
        target = rows[index + 1]
        if str(target["contractMonth"]) != month:
            counts["crossContractTarget"] += 1
            candidates.append({"index": index, "status": "EXCLUDED_CROSS_CONTRACT_TARGET", "features": features})
            continue
        close_now = v1._number(row, "close")
        close_next = v1._number(target, "close")
        if close_now is None or close_next is None or close_now <= 0 or close_next <= 0:
            counts["targetUnavailable"] += 1
            candidates.append({"index": index, "status": "TARGET_UNAVAILABLE", "features": features})
            continue
        aligned = (1 if momentum > 0 else -1) * (close_next / close_now - 1.0)
        if aligned == 0:
            counts["flatTarget"] += 1
            candidates.append({"index": index, "status": "EXCLUDED_FLAT", "features": features})
            continue
        candidates.append({
            "index": index,
            "status": "ELIGIBLE_TARGET",
            "features": features,
            "direction": direction,
            "decisionDate": row["time"],
            "targetDate": target["time"],
            "decisionAlignedReturn": aligned,
            "value": 1 if aligned > 0 else 0,
            "provenance": PROVENANCE,
            "replayRevision": "V1R1",
            "rollPolicy": ROLL_POLICY,
        })
        counts["cleanMaturedLabels"] += 1
    return features_out, candidates, counts


def _add_training_eligibility_funnel(rows: list[dict[str, Any]], candidates: list[dict[str, Any]], counts: dict[str, Any]) -> dict[str, Any]:
    result = dict(counts)
    result.update({"insufficientCleanTraining": 0, "singleClassCleanTraining": 0,
                   "forecastEligibleAfterTrainingGates": 0})
    for candidate in candidates:
        if candidate.get("status") != "ELIGIBLE_TARGET":
            continue
        forecast_date = candidate["decisionDate"]
        training = [item for item in candidates if item.get("status") == "ELIGIBLE_TARGET"
                    and item["index"] < candidate["index"]
                    and item["decisionDate"] < forecast_date and item["targetDate"] < forecast_date]
        if len(training) < v1.MIN_TRAINING_SAMPLES:
            result["insufficientCleanTraining"] += 1
        elif {int(item["value"]) for item in training} != {0, 1}:
            result["singleClassCleanTraining"] += 1
        else:
            result["forecastEligibleAfterTrainingGates"] += 1
    result["forecastGenerated"] = result["forecastEligibleAfterTrainingGates"]
    result["validV1R1OosPairs"] = result["forecastEligibleAfterTrainingGates"]
    return result


def run_clean_replay(rows: list[dict[str, Any]], input_hash: str) -> dict[str, Any]:
    feature_rows, candidates, counts = _features_and_candidates(rows)
    forecasts = []
    trace = []
    training_by_forecast: dict[str, list[dict[str, Any]]] = {}
    first_30_clean_history = None
    counts.update({"insufficientCleanTraining": 0, "singleClassCleanTraining": 0, "forecastGenerated": 0, "validV1R1OosPairs": 0})
    for candidate in candidates:
        if candidate.get("status") != "ELIGIBLE_TARGET":
            continue
        forecast_date = candidate["decisionDate"]
        training = [item for item in candidates if item.get("status") == "ELIGIBLE_TARGET"
                    and item["index"] < candidate["index"] and item["decisionDate"] < forecast_date and item["targetDate"] < forecast_date]
        if len(training) < v1.MIN_TRAINING_SAMPLES:
            counts["insufficientCleanTraining"] += 1
            continue
        if first_30_clean_history is None:
            first_30_clean_history = {
                "forecastDate": forecast_date,
                "trainingSampleCount": len(training),
                "trainingPositiveCount": sum(int(item["value"]) for item in training),
                "trainingNegativeCount": sum(1 - int(item["value"]) for item in training),
            }
        if {int(item["value"]) for item in training} != {0, 1}:
            counts["singleClassCleanTraining"] += 1
            continue
        training_by_forecast[forecast_date] = training
        model = v1._fit(training)
        probability = v1._predict(candidate["features"], model)
        naive_probability = sum(int(item["value"]) for item in training) / len(training)
        fit_cutoff = max(item["targetDate"] for item in training)
        forecast = {
            "forecastDate": forecast_date,
            "targetDate": candidate["targetDate"],
            "researchDirection": candidate["direction"],
            "probability": probability,
            "naiveProbability": naive_probability,
            "trainingSampleCount": len(training),
            "trainingPositiveCount": model["positiveCount"],
            "trainingNegativeCount": model["negativeCount"],
            "fitCutoff": fit_cutoff,
            "featureValues": candidate["features"],
            "provenance": PROVENANCE,
            "replayRevision": "V1R1",
            "rollPolicy": ROLL_POLICY,
        }
        forecasts.append(forecast)
        trace.append({
            "forecastDate": forecast_date,
            "targetDate": candidate["targetDate"],
            "fitCutoff": fit_cutoff,
            "trainingSampleCount": len(training),
            "trainingPositiveCount": model["positiveCount"],
            "trainingNegativeCount": model["negativeCount"],
            "trainingStartTargetDate": min(item["targetDate"] for item in training),
            "trainingEndTargetDate": max(item["targetDate"] for item in training),
            "normalizationMeans": model["means"],
            "normalizationPopulationStds": model["stds"],
            "weights": model["weights"],
            "replayRevision": "V1R1",
            "rollPolicy": ROLL_POLICY,
        })
    by_date_index = {str(row["time"]): index for index, row in enumerate(rows)}

    def clean_feature_index(index: int) -> bool:
        month = str(rows[index]["contractMonth"])
        return (index >= v1.WARMUP_SESSIONS
                and all(str(rows[pos]["contractMonth"]) == month for pos in range(index - v1.WARMUP_SESSIONS, index + 1))
                and str(rows[index - 1]["contractMonth"]) == month)

    valid_pair_feature_exposure = 0
    valid_pair_target_exposure = 0
    for forecast in forecasts:
        forecast_index = by_date_index[forecast["forecastDate"]]
        target_index = by_date_index[forecast["targetDate"]]
        valid_pair_feature_exposure += not clean_feature_index(forecast_index)
        valid_pair_target_exposure += str(rows[forecast_index]["contractMonth"]) != str(rows[target_index]["contractMonth"])
        for item in training_by_forecast[forecast["forecastDate"]]:
            index = item["index"]
            if not clean_feature_index(index) or str(rows[index]["contractMonth"]) != str(rows[index + 1]["contractMonth"]):
                raise RuntimeError("ROLL-CLEAN INTEGRITY FAIL in training; calibration was not computed")
    if valid_pair_feature_exposure or valid_pair_target_exposure:
        raise RuntimeError("ROLL-CLEAN INTEGRITY FAIL in OOS pairs; calibration was not computed")

    pairs = []
    for forecast in forecasts:
        candidate = next(item for item in candidates if item.get("status") == "ELIGIBLE_TARGET" and item["decisionDate"] == forecast["forecastDate"])
        pairs.append({
            **forecast,
            "outcome": candidate["value"],
            "decisionAlignedReturn": candidate["decisionAlignedReturn"],
        })
    counts["forecastGenerated"] = len(forecasts)
    counts["validV1R1OosPairs"] = len(pairs)
    predictions = [float(pair["probability"]) for pair in pairs]
    outcomes = [int(pair["outcome"]) for pair in pairs]
    reliability, ece = v1._reliability(pairs)
    naive_reliability, naive_ece = v1._reliability(pairs, probability_key="naiveProbability")
    positive_count = sum(outcomes)
    training_feature_exposure = 0
    training_target_exposure = 0
    for training in training_by_forecast.values():
        for item in training:
            index = item["index"]
            training_feature_exposure += not clean_feature_index(index)
            training_target_exposure += str(rows[index]["contractMonth"]) != str(rows[index + 1]["contractMonth"])
    roll_exposure = {
        "featureRowsWithCrossContractMomentum": counts["crossContractMomentum"],
        "featureRowsWithCrossContractOi": counts["crossContractOi"],
        "validPairFeatureExposure": valid_pair_feature_exposure,
        "validPairTargetExposure": valid_pair_target_exposure,
        "trainingFeatureExposure": training_feature_exposure,
        "trainingTargetExposure": training_target_exposure,
    }
    report = {
        "evidenceClass": PROVENANCE,
        "researchOnly": True,
        "productionOos": False,
        "liveProspectiveOos": False,
        "contractId": v1.FEATURE_CONTRACT_ID,
        "modelId": v1.MODEL_ID,
        "targetContractId": v1.TARGET_CONTRACT_ID,
        "replayRevision": "V1R1",
        "rollPolicy": ROLL_POLICY,
        "inputSha256": input_hash,
        "pairCount": len(pairs),
        "positiveCount": positive_count,
        "negativeCount": len(pairs) - positive_count,
        "positiveRate": positive_count / len(pairs) if pairs else None,
        "meanForecast": sum(predictions) / len(predictions) if predictions else None,
        "minForecast": min(predictions) if predictions else None,
        "maxForecast": max(predictions) if predictions else None,
        "brierScore": v1._brier(pairs, "probability"),
        "reliabilityBins": reliability,
        "ece": ece,
        "pastOnlyNaiveBaseRateBrierScore": v1._brier(pairs, "naiveProbability"),
        "naiveReliabilityBins": naive_reliability,
        "naiveEce": naive_ece,
        "interpretation": "EVIDENCE INCONCLUSIVE" if pairs else "EVIDENCE INSUFFICIENT",
        "promotionThresholdDefined": False,
        "sourceVintageStatus": "NOT PROVEN; historical source lacks per-day publication timestamps, archived vintages, and revision history.",
        "rollExposure": roll_exposure,
        "firstDateWithThirtyCleanMaturedLabels": first_30_clean_history,
    }
    return {"featureRows": feature_rows, "candidates": candidates, "forecasts": forecasts, "pairs": pairs,
            "trainingTrace": trace, "funnel": counts, "report": report}


def _rows_to_csv_bytes(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _db_snapshot(db_path: Path | None = None) -> dict[str, Any]:
    import sqlite3

    db_path = db_path or DB_PATH
    before_hash = sha256_file(db_path)
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        decisions = connection.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]
        outcomes = connection.execute("SELECT COUNT(*) FROM decision_outcome").fetchone()[0]
    finally:
        connection.close()
    return {"sha256": before_hash, "decision_ledger": decisions, "decision_outcome": outcomes}


def _verify_frozen_inputs(v1_dir: Path | None = None) -> dict[str, Any]:
    v1_dir = v1_dir or V1_DIR
    contract_path = v1_dir / "feature_contract.json"
    contract_hash = sha256_file(contract_path)
    if contract_hash != EXPECTED_CONTRACT_SHA256:
        raise RuntimeError(f"frozen V1 contract drift: {contract_hash}")
    v1_hashes = {name: sha256_file(v1_dir / name) for name in EXPECTED_V1_FILE_HASHES}
    for name, expected in EXPECTED_V1_FILE_HASHES.items():
        if v1_hashes[name] != expected:
            raise RuntimeError(f"frozen V1 artifact drift: {name}: {v1_hashes[name]}")
    report = json.loads((v1_dir / "calibration_report.json").read_text(encoding="utf-8"))
    for name, expected in EXPECTED_V1_INTERNAL_HASHES.items():
        key = {"featureRows": "featureMatrixSha256", "forecasts": "forecastSha256", "pairs": "oosPairsSha256"}[name]
        if report[key] != expected:
            raise RuntimeError(f"V1 canonical output fingerprint drift: {name}: {report[key]}")
    return {"contractSha256": contract_hash, "artifactSha256": v1_hashes,
            "internalFingerprints": EXPECTED_V1_INTERNAL_HASHES, "calibrationReport": report}


def _persist_raw(responses: list[dict[str, Any]], raw_dir: Path) -> list[dict[str, Any]]:
    if raw_dir.exists() and any(raw_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing raw responses: {raw_dir}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for item in responses:
        filename = f"tx_{item['windowStart']}_{item['windowEnd']}.csv".replace(":", "-")
        target = raw_dir / filename
        target.write_bytes(item["rawBytes"])
        entries.append({key: item[key] for key in (
            "windowIndex", "windowStart", "windowEnd", "retrievedAt", "sourceUrl", "httpStatus",
            "contentType", "rawDataRowCount", "firstResponseDate", "lastResponseDate",
        )} | {"file": filename, "sha256": sha256_bytes(item["rawBytes"]), "byteCount": len(item["rawBytes"])})
    return entries


def _load_saved_raw(raw_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    expected_windows = _windows()
    paths = sorted(raw_dir.glob("tx_*.csv"))
    if len(paths) != len(expected_windows):
        raise RuntimeError(f"saved raw window count mismatch: expected {len(expected_windows)}, found {len(paths)}")
    responses = []
    entries = []
    for index, (path, (start, end)) in enumerate(zip(paths, expected_windows)):
        raw_bytes = path.read_bytes()
        try:
            text, csv_rows = _read_csv_bytes(raw_bytes, "text/html; charset=MS950")
        except (UnicodeError, ValueError) as exc:
            raise RuntimeError(f"saved raw response is invalid: {path.name}") from exc
        actual_stem = path.stem
        expected_name = f"tx_{start.isoformat()}_{end.isoformat()}"
        if actual_stem != expected_name:
            raise RuntimeError(f"saved raw window does not match expected date coverage: {path.name} != {expected_name}.csv")
        row_dates = [str(row[0]).strip().replace("/", "-") for row in csv_rows[1:] if row and row[0].strip()]
        retrieved_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        entry = {
            "windowIndex": index,
            "windowStart": start.isoformat(),
            "windowEnd": end.isoformat(),
            "retrievedAt": retrieved_at,
            "retrievedAtSource": "RECOVERED_FROM_RAW_FILE_MTIME",
            "sourceUrl": TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
            "httpStatus": 200,
            "contentType": "text/html; charset=MS950 (recovered for local decode)",
            "rawDataRowCount": max(0, len(csv_rows) - 1),
            "firstResponseDate": min(row_dates) if row_dates else None,
            "lastResponseDate": max(row_dates) if row_dates else None,
            "file": path.name,
            "sha256": sha256_bytes(raw_bytes),
            "byteCount": len(raw_bytes),
        }
        entries.append(entry)
        responses.append({
            "windowIndex": index,
            "windowStart": start.isoformat(),
            "windowEnd": end.isoformat(),
            "retrievedAt": retrieved_at,
            "sourceUrl": TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
            "httpStatus": 200,
            "contentType": "text/html; charset=MS950",
            "rawBytes": raw_bytes,
            "text": text,
            "csvRows": csv_rows,
            "rawDataRowCount": max(0, len(csv_rows) - 1),
            "firstResponseDate": min(row_dates) if row_dates else None,
            "lastResponseDate": max(row_dates) if row_dates else None,
        })
    return responses, entries


def _write_outputs(output_dir: Path, raw_entries: list[dict[str, Any]], raw_summary: dict[str, Any],
                   selected: list[dict[str, Any]], selection_trace: list[dict[str, Any]],
                   comparison: list[dict[str, Any]], comparison_summary: dict[str, Any],
                   run1: dict[str, Any], run2: dict[str, Any], input_sha: str, contract_info: dict[str, Any],
                   raw_gate_passed: bool, db_before: dict[str, Any], db_after: dict[str, Any]) -> dict[str, Any]:
    features, candidates, base_funnel = _features_and_candidates(selected)
    funnel = _add_training_eligibility_funnel(selected, candidates, base_funnel)
    clean_gate = raw_gate_passed and comparison_summary["missingRebuiltDates"] == []
    outputs = {
        "selection_trace.csv": _rows_to_csv_bytes(selection_trace, [
            "marketDate", "selectedContractMonth", "selectedVolume", "candidateContractCount",
            "candidateDistinctContractMonths", "selectionRule", "selectionReason",
        ]),
        "rebuilt_daily_series.csv": _rows_to_csv_bytes(selected, [
            "time", "contractMonth", "open", "high", "low", "close", "change", "changePct", "volume",
            "openInterest", "settlement", "source",
        ]),
        "old_vs_rebuilt_comparison.csv": _rows_to_csv_bytes(comparison, [
            "marketDate", "oldContractMonth", "newContractMonth", "contractMatch", "oldClose", "newClose",
            "closeMatch", "oldVolume", "newVolume", "volumeMatch", "oldOpenInterest", "newOpenInterest", "openInterestMatch",
        ]),
        "roll_clean_feature_matrix.csv": _rows_to_csv_bytes(features, [
            "marketDate", "selectedContractMonth", "researchDirection", *v1.FEATURE_NAMES, "replayRevision", "rollPolicy",
        ]),
        "eligibility_funnel.json": canonical_bytes({**funnel, "rawContractRows": raw_summary["rawDataRows"],
            "eligibleDailyContractCandidateRows": raw_summary["eligibleCandidateRows"],
            "selectionRuleGate": "PASS" if raw_gate_passed else "BLOCKED",
            "cleanDatasetGate": "PASS" if clean_gate else "BLOCKED"}),
        "raw_data_inventory.json": canonical_bytes({
            "source": "TAIFEX official futures daily download",
            "sourceEndpoint": TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
            "instrument": "TX",
            "requestedDateRange": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
            "retrievedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rawFiles": raw_entries,
            "rawDataRows": raw_summary["rawDataRows"],
            "eligibleCandidateRows": raw_summary["eligibleCandidateRows"],
            "marketDates": raw_summary["marketSessions"],
            "selectedDistinctContractMonths": raw_summary["selectedDistinctContractMonths"],
            "rawDistinctContractMonths": raw_summary["distinctContractMonths"],
            "tieMarketDates": raw_summary["tieMarketDates"],
            "tiePolicy": raw_summary["tiePolicy"],
            "rawWindowCount": len(raw_entries),
            "selectionRule": SELECTION_RULE,
        }),
    }
    run_fingerprints = []
    for result in (run1, run2):
        run_fingerprints.append({name: sha256_bytes(canonical_bytes(result[name])) for name in (
            "featureRows", "trainingTrace", "forecasts", "pairs", "funnel", "report", "candidates",
        )})
    deterministic = run_fingerprints[0] == run_fingerprints[1]
    v1r1 = run2
    roll_exposure = v1r1["report"]["rollExposure"]
    clean_replay_pass = clean_gate and deterministic and all(value == 0 for key, value in roll_exposure.items()
                            if key in ("validPairFeatureExposure", "validPairTargetExposure", "trainingFeatureExposure", "trainingTargetExposure"))
    first_forecast = v1r1["forecasts"][0] if v1r1["forecasts"] else None
    first_training = v1r1["trainingTrace"][0] if v1r1["trainingTrace"] else None
    summary = {
        "researchContract": v1.FEATURE_CONTRACT_ID,
        "model": v1.MODEL_ID,
        "evidenceClass": PROVENANCE,
        "replayRevision": "V1R1",
        "rollPolicy": ROLL_POLICY,
        "selectionRuleGate": "PASS" if raw_gate_passed else "BLOCKED",
        "v1r1Dataset": "PASS" if clean_gate else "BLOCKED",
        "rollCleanIntegrity": "PASS" if clean_replay_pass else "FAIL" if clean_gate else "NOT RUN",
        "v1r1Replay": "PASS" if clean_replay_pass else "NOT RUN",
        "calibrationInterpretation": v1r1["report"]["interpretation"] if clean_replay_pass else "EVIDENCE INCONCLUSIVE",
        "pairCount": len(v1r1["pairs"]) if clean_replay_pass else 0,
        "sourceVintageStatus": "NOT PROVEN",
        "productionP2_03": "BLOCKED",
        "probabilityLabelAllowed": False,
    }
    outputs.update({
        "training_trace.jsonl": b"".join(canonical_bytes(row) + b"\n" for row in v1r1["trainingTrace"]),
        "reconstructed_forecasts.csv": _rows_to_csv_bytes([
            {**row, **{f"feature_{name}": row["featureValues"][name] for name in v1.FEATURE_NAMES}}
            for row in v1r1["forecasts"]
        ], [
            "forecastDate", "targetDate", "researchDirection", "probability", "naiveProbability", "trainingSampleCount",
            "trainingPositiveCount", "trainingNegativeCount", "fitCutoff", "provenance", "replayRevision", "rollPolicy",
            *[f"feature_{name}" for name in v1.FEATURE_NAMES],
        ]),
        "oos_pairs.csv": _rows_to_csv_bytes(v1r1["pairs"], [
            "forecastDate", "targetDate", "researchDirection", "probability", "naiveProbability", "outcome",
            "decisionAlignedReturn", "trainingSampleCount", "fitCutoff", "provenance", "replayRevision", "rollPolicy",
        ]),
        "calibration_report.json": canonical_bytes({
            **v1r1["report"],
            "calibrationInterpretation": v1r1["report"]["interpretation"],
            "replayRevision": "V1R1",
            "rollPolicy": ROLL_POLICY,
        }),
        "determinism_report.json": canonical_bytes({
            "twoRunsIdentical": deterministic,
            "runFingerprints": run_fingerprints,
            "rawSelectedSeriesSha256": sha256_bytes(canonical_bytes(selected)),
        }),
        "research_summary.json": canonical_bytes({**summary, "funnel": funnel,
            "firstForecast": first_forecast, "firstForecastTrainingTrace": first_training}),
        "v1_vs_v1r1_comparison.json": canonical_bytes({
            "V1": {key: contract_info["calibrationReport"].get(key) for key in (
                "pairCount", "positiveCount", "negativeCount", "positiveRate", "meanForecast", "brierScore",
                "pastOnlyNaiveBaseRateBrierScore", "ece", "naiveEce",
            )},
            "V1R1": {key: v1r1["report"].get(key) for key in (
                "pairCount", "positiveCount", "negativeCount", "positiveRate", "meanForecast", "brierScore",
                "pastOnlyNaiveBaseRateBrierScore", "ece", "naiveEce",
            )},
            "comparisonDoesNotChangeRules": True,
        }),
        "replay_blocker.json": canonical_bytes({
            "datasetGate": "PASS" if clean_gate else "BLOCKED",
            "reason": None if clean_gate else "RAW_COVERAGE_OR_OLD_SESSION_MISSING_FROM_REBUILT_SERIES",
            "selectionRuleGate": "PASS" if raw_gate_passed else "BLOCKED",
            "rollCleanIntegrity": "PASS" if clean_replay_pass else "NOT RUN" if not clean_gate else "FAIL",
        }),
    })
    outputs["roll_clean_feature_matrix.csv"] = _rows_to_csv_bytes(features, [
        "marketDate", "selectedContractMonth", "researchDirection", *v1.FEATURE_NAMES, "replayRevision", "rollPolicy",
    ])
    for name, payload in outputs.items():
        (output_dir / name).write_bytes(payload)
    if db_before != db_after:
        raise RuntimeError("prospective Ledger DB changed during V1R1");
    return {
        "outputDir": str(output_dir),
        "rawDatasetGate": "PASS" if raw_gate_passed else "BLOCKED",
        "cleanReplayGate": "PASS" if clean_replay_pass else "NOT RUN",
        "v1IntegrityUnchanged": True,
        "prospectiveDbBeforeAfter": db_after,
        "outputSha256": {name: sha256_bytes(payload) for name, payload in outputs.items()},
        "summary": summary,
        "comparison": comparison_summary,
        "rawSummary": raw_summary,
        "funnel": funnel,
    }


def execute(output_dir: Path = OUTPUT_DIR, pause_seconds: float = 0.15) -> dict[str, Any]:
    saved_raw = False
    saved_entries = None
    if output_dir.exists() and any(output_dir.iterdir()):
        children = list(output_dir.iterdir())
        raw_dir_existing = output_dir / "raw"
        if len(children) != 1 or children[0] != raw_dir_existing or not raw_dir_existing.is_dir():
            raise FileExistsError(f"refusing to overwrite existing V1R1 output: {output_dir}")
        responses, saved_entries = _load_saved_raw(raw_dir_existing)
        saved_raw = True
    else:
        responses = None
    frozen = _verify_frozen_inputs()
    old_bytes = OLD_DATASET_PATH.read_bytes()
    if sha256_bytes(old_bytes) != EXPECTED_OLD_DATA_SHA256:
        raise RuntimeError("old comparison dataset drift")
    old_rows = json.loads(old_bytes.decode("utf-8"))
    db_before = _db_snapshot()
    if db_before["sha256"] != EXPECTED_DB_SHA256 or db_before["decision_ledger"] != 1 or db_before["decision_outcome"] != 0:
        raise RuntimeError(f"prospective DB baseline drift: {db_before}")
    if responses is None:
        responses = retrieve_raw_windows(pause_seconds=pause_seconds)
    # Verify exact date coverage, raw chronology, and no duplicate selected market dates.
    selected, trace, raw_summary = select_daily_series(responses)
    selected_dates = [row["time"] for row in selected]
    if selected_dates != sorted(selected_dates) or len(set(selected_dates)) != len(selected_dates):
        raise RuntimeError("rebuilt daily series has duplicate or unordered dates")
    if any(day < START_DATE.isoformat() or day > END_DATE.isoformat() for day in selected_dates):
        raise RuntimeError("rebuilt daily series contains dates outside the authorized range")
    old_comparison_rows, comparison_summary = compare_old_vs_rebuilt(old_rows, selected)
    date_coverage_ok = comparison_summary["missingRebuiltDates"] == []
    requested_span_ok = bool(selected and selected_dates[0] == START_DATE.isoformat() and selected_dates[-1] == END_DATE.isoformat())
    # Old rows are comparison-only: additional officially returned sessions are
    # valid rebuilt coverage. Every old observed session must still be present.
    raw_gate_passed = bool(date_coverage_ok and requested_span_ok)
    if not raw_gate_passed:
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_entries = saved_entries if saved_raw else _persist_raw(responses, output_dir / "raw")
        result = _write_outputs(output_dir, raw_entries, raw_summary, selected, trace, old_comparison_rows,
                                comparison_summary, {"featureRows": [], "candidates": [], "trainingTrace": [], "forecasts": [], "pairs": [], "report": {"interpretation": "EVIDENCE INSUFFICIENT", "rollExposure": {}}, "funnel": {}},
                                {"featureRows": [], "candidates": [], "trainingTrace": [], "forecasts": [], "pairs": [], "report": {"interpretation": "EVIDENCE INSUFFICIENT", "rollExposure": {}}, "funnel": {}},
                                sha256_bytes(canonical_bytes(selected)), frozen, False, db_before, db_before)
        return result
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_entries = saved_entries if saved_raw else _persist_raw(responses, raw_dir)
    for entry in raw_entries:
        response = responses[entry["windowIndex"]]
        response["rawFile"] = entry["file"]
        response["rawSha256"] = entry["sha256"]
    selected_sha = sha256_bytes(canonical_bytes(selected))
    run1 = run_clean_replay(selected, selected_sha)
    run2 = run_clean_replay(selected, selected_sha)
    _, _, feature_funnel = _features_and_candidates(selected)
    # Raw rows are stored byte-for-byte. Write artifacts only after both replay
    # fingerprints and every zero-roll assertion have been checked.
    pre_roll_exposure = [
        feature for feature in run2["featureRows"]
        if feature.get("replayRevision") != "V1R1" or feature.get("rollPolicy") != ROLL_POLICY
    ]
    valid_feature_roll_exposure = run2["report"]["rollExposure"]["validPairFeatureExposure"]
    valid_target_roll_exposure = run2["report"]["rollExposure"]["validPairTargetExposure"]
    train_feature_roll_exposure = run2["report"]["rollExposure"]["trainingFeatureExposure"]
    train_target_roll_exposure = run2["report"]["rollExposure"]["trainingTargetExposure"]
    if any((pre_roll_exposure, valid_feature_roll_exposure, valid_target_roll_exposure,
            train_feature_roll_exposure, train_target_roll_exposure)):
        raise RuntimeError("ROLL-CLEAN INTEGRITY FAIL; refusing calibration artifact write")
    db_after = _db_snapshot()
    if db_after != db_before:
        raise RuntimeError("prospective Ledger DB changed during V1R1")
    result = _write_outputs(output_dir, raw_entries, raw_summary, selected, trace, old_comparison_rows,
                            comparison_summary, run1, run2, selected_sha, frozen, True, db_before, db_after)
    frozen_after = _verify_frozen_inputs()
    old_after = sha256_file(OLD_DATASET_PATH)
    db_after_write = _db_snapshot()
    if frozen_after["artifactSha256"] != frozen["artifactSha256"] or old_after != EXPECTED_OLD_DATA_SHA256:
        raise RuntimeError("frozen V1 or old comparison artifact changed during V1R1")
    if db_after_write != db_before:
        raise RuntimeError("prospective Ledger DB changed during V1R1")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--pause-seconds", type=float, default=0.15)
    args = parser.parse_args()
    result = execute(args.output_dir, args.pause_seconds)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
