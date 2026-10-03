"""Run the frozen, research-only P2-03 V2 historical development replay."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import p203_historical_research_v1r1_replay as v1r1


PROTOCOL_PATH = ROOT / "docs" / "P2_03_RESEARCH_V2_PRE_REGISTRATION.md"
AMENDMENT_PATH = ROOT / "docs" / "P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md"
ORIGINAL_MANIFEST_PATH = ROOT / ".tmp" / "p203-v2-protocol" / "protocol_manifest.json"
IDENTITY_PATH = ROOT / ".tmp" / "p203-v2-protocol" / "effective_protocol_identity.json"
AMENDMENT_MANIFEST_PATH = ROOT / ".tmp" / "p203-v2-protocol" / "protocol_amendment_001_manifest.json"
INPUT_DIR = ROOT / ".tmp" / "p203-historical-research-v1r1"
INPUT_INVENTORY_PATH = INPUT_DIR / "raw_data_inventory.json"
SERIES_PATH = INPUT_DIR / "rebuilt_daily_series.csv"
SELECTION_TRACE_PATH = INPUT_DIR / "selection_trace.csv"
DB_PATH = ROOT / "data" / "p203-prospective-ledger.sqlite3"
OUTPUT_DIR = ROOT / ".tmp" / "p203-v2-historical-development"

EXPECTED_HASHES = {
    "originalProtocol": "0ab04d326962a48439f0a762f5967d0268d8137fae6e26e07db5c7ca39c55290",
    "amendment001": "80ae6beafeeebc68776249625162d6a18736cd1c91981708b71c9dbda852ae0a",
    "originalManifest": "9fbfd8cfe02bd47ace7893161bb6a5c1b6e9cba8639c6063c174cd91ef018ffb",
    "effectiveIdentity": "f229f03eb3d931aae96d1e994cb8725f8a73676132632da28c94cc9e4d8fcafc",
    "amendmentManifest": "54b2aa5ba5ad6478d3661c1b73905056ffb26518f2caabd694a3e17f1b734db2",
    "prospectiveDb": "73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4",
}
FEATURE_NAMES = (
    "momentum_strength_5",
    "range_pct_1",
    "trend_alignment_20",
    "volume_confirmation_5",
    "directional_price_location_20",
    "range_pct_5",
)
FEATURE_SPECS = (
    {
        "name": "momentum_strength_5",
        "formula": "abs(close[D] / close[D-5] - 1)",
        "lookbackSessions": 5,
        "requiredFields": ["close"],
        "expectedRelationship": "POSITIVE if directional persistence exists",
    },
    {
        "name": "range_pct_1",
        "formula": "(high[D] - low[D]) / close[D]",
        "lookbackSessions": 0,
        "requiredFields": ["high", "low", "close"],
        "expectedRelationship": "NEGATIVE if wider one-session range reflects noisier follow-through",
    },
    {
        "name": "trend_alignment_20",
        "formula": "sign5(D) * (close[D] / close[D-20] - 1)",
        "lookbackSessions": 20,
        "requiredFields": ["close"],
        "expectedRelationship": "POSITIVE",
    },
    {
        "name": "volume_confirmation_5",
        "formula": "sign5(D) * (close[D] / close[D-1] - 1) * (volume[D] / mean(volume[D-5..D-1]) - 1)",
        "lookbackSessions": 5,
        "requiredFields": ["close", "volume"],
        "expectedRelationship": "POSITIVE if participation confirms follow-through",
    },
    {
        "name": "directional_price_location_20",
        "formula": "sign5(D) * (2 * (close[D] - min(low[D-19..D])) / (max(high[D-19..D]) - min(low[D-19..D])) - 1)",
        "lookbackSessions": 19,
        "requiredFields": ["close", "high", "low"],
        "expectedRelationship": "POSITIVE",
    },
    {
        "name": "range_pct_5",
        "formula": "(max(high[D-4..D]) - min(low[D-4..D])) / close[D]",
        "lookbackSessions": 4,
        "requiredFields": ["high", "low", "close"],
        "expectedRelationship": "NEGATIVE if wider recent range reduces directional predictability",
    },
)
MIN_TRAINING_SAMPLES = 30
LOGISTIC_ITERATIONS = 2500
LEARNING_RATE = 0.1
L2_PENALTY = 0.01
BOOTSTRAP_BLOCK_SIZE = 20
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 2_030_301
ECE_BUCKETS = 10
DEVELOPMENT_START = "2024-12-06"
DEVELOPMENT_END = "2026-10-01"
EVIDENCE_CLASS = "HISTORICAL_RESEARCH_V2_DEVELOPMENT"
CONTRACT_ID = "P2_03_HISTORICAL_RESEARCH_FEATURES_V2"
MODEL_ID = "P2_03_HISTORICAL_RESEARCH_LOGISTIC_V2"
TARGET_ID = "P2_03_HISTORICAL_RESEARCH_DIRECTIONAL_SUCCESS_V2"
ROLL_RULE = "ALL_SELECTED_CONTRACT_MONTHS_D_MINUS_20_THROUGH_D_PLUS_1_MUST_MATCH"
SOURCE_LIMITATION = "Historical publication timing, vintage, and revision history are NOT PROVEN."


class IntegrityError(RuntimeError):
    """Raised when a frozen input or protocol fingerprint does not match."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_effective_protocol() -> dict[str, Any]:
    paths = {
        "originalProtocol": PROTOCOL_PATH,
        "amendment001": AMENDMENT_PATH,
        "originalManifest": ORIGINAL_MANIFEST_PATH,
        "effectiveIdentity": IDENTITY_PATH,
        "amendmentManifest": AMENDMENT_MANIFEST_PATH,
    }
    actual = {key: sha256_file(path) for key, path in paths.items()}
    mismatches = {
        key: {"expected": EXPECTED_HASHES[key], "actual": actual[key]}
        for key in paths
        if actual[key] != EXPECTED_HASHES[key]
    }
    if mismatches:
        raise IntegrityError(f"effective protocol integrity mismatch: {mismatches}")

    identity = _json_file(IDENTITY_PATH)
    manifest = _json_file(AMENDMENT_MANIFEST_PATH)
    original_manifest = _json_file(ORIGINAL_MANIFEST_PATH)
    if identity.get("status") != "FORMALLY_APPROVED_FROZEN":
        raise IntegrityError("effective protocol identity is not formally approved/frozen")
    if identity.get("effectiveProtocol") != "ORIGINAL_PROTOCOL_PLUS_AMENDMENT_001":
        raise IntegrityError("effective protocol identity composition mismatch")
    if identity.get("originalProtocolSha256") != actual["originalProtocol"]:
        raise IntegrityError("effective identity original protocol link mismatch")
    if identity.get("amendmentSha256") != actual["amendment001"]:
        raise IntegrityError("effective identity amendment link mismatch")
    if manifest.get("status") != "FORMALLY_APPROVED_FROZEN":
        raise IntegrityError("Amendment 001 manifest is not formally approved/frozen")
    if manifest.get("originalProtocol", {}).get("sha256") != actual["originalProtocol"]:
        raise IntegrityError("amendment manifest original protocol link mismatch")
    if manifest.get("originalFrozenManifest", {}).get("sha256") != actual["originalManifest"]:
        raise IntegrityError("amendment manifest original manifest link mismatch")
    if manifest.get("amendment", {}).get("sha256") != actual["amendment001"]:
        raise IntegrityError("amendment manifest Amendment 001 link mismatch")
    identity_record = manifest.get("effectiveProtocolIdentity", {})
    if identity_record.get("sha256") != actual["effectiveIdentity"]:
        raise IntegrityError("amendment manifest effective identity link mismatch")
    if original_manifest.get("status") != "FORMALLY_APPROVED_FROZEN_NOT_EXECUTED":
        raise IntegrityError("original frozen manifest status changed")
    return {"hashes": actual, "identity": identity, "manifest": manifest}


def _verify_source_evidence_hashes() -> dict[str, Any]:
    original_manifest = _json_file(ORIGINAL_MANIFEST_PATH)
    source_roots = {
        "sourceV1R1Hashes": INPUT_DIR,
        "diagnosticHashes": ROOT / ".tmp" / "p203-v1r1-diagnostic",
    }
    checked: dict[str, dict[str, str]] = {}
    for group, root in source_roots.items():
        expected_map = original_manifest.get(group)
        if not isinstance(expected_map, dict):
            raise IntegrityError(f"missing source evidence hash map: {group}")
        checked[group] = {}
        for relative, expected in expected_map.items():
            path = root / Path(relative)
            if not path.is_file():
                raise IntegrityError(f"source evidence file missing: {path}")
            actual = sha256_file(path)
            if actual != expected:
                raise IntegrityError(f"source evidence drift: {path}: {actual} != {expected}")
            checked[group][relative] = actual

    v1_feature_contract = ROOT / ".tmp" / "p203-historical-research-v1" / "feature_contract.json"
    v1_contract_hash = sha256_file(v1_feature_contract)
    expected_v1_contract_hash = original_manifest["sourceV1"]["featureContractJsonSha256"]
    if v1_contract_hash != expected_v1_contract_hash:
        raise IntegrityError("frozen V1 feature contract hash drift")
    v1r1_integrity = v1r1._verify_frozen_inputs()
    return {
        "sourceV1": {"feature_contract.json": v1_contract_hash},
        **checked,
        "v1r1VerifiedArtifacts": v1r1_integrity["artifactSha256"],
    }


def _database_snapshot() -> dict[str, Any]:
    digest = sha256_file(DB_PATH)
    connection = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        ledger_count = connection.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]
        outcome_count = connection.execute("SELECT COUNT(*) FROM decision_outcome").fetchone()[0]
    finally:
        connection.close()
    result = {
        "sha256": digest,
        "decision_ledger": int(ledger_count),
        "decision_outcome": int(outcome_count),
    }
    if result != {
        "sha256": EXPECTED_HASHES["prospectiveDb"],
        "decision_ledger": 1,
        "decision_outcome": 0,
    }:
        raise IntegrityError(f"prospective DB baseline drift: {result}")
    return result


def _float_value(raw: Any, field: str, row_index: int) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise IntegrityError(f"invalid numeric {field} at selected-series row {row_index}: {raw!r}") from exc
    if not math.isfinite(value):
        raise IntegrityError(f"non-finite {field} at selected-series row {row_index}")
    return value


def _load_selected_series() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inventory = _json_file(INPUT_INVENTORY_PATH)
    raw_entries = inventory.get("rawFiles", [])
    if len(raw_entries) != 24:
        raise IntegrityError(f"expected 24 frozen raw TX response windows, found {len(raw_entries)}")
    raw_dir = INPUT_DIR / "raw"
    responses, loaded_entries = v1r1._load_saved_raw(raw_dir)
    if len(responses) != 24 or len(loaded_entries) != 24:
        raise IntegrityError("saved raw response window inventory is incomplete")
    rebuilt, trace, raw_summary = v1r1.select_daily_series(responses)

    with SERIES_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    with SELECTION_TRACE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        trace_rows = list(csv.DictReader(handle))
    if len(csv_rows) != 441 or len(rebuilt) != 441 or len(trace_rows) != 441 or len(trace) != 441:
        raise IntegrityError("selected series or selection trace row count differs from frozen 441-session inventory")

    parsed_rows: list[dict[str, Any]] = []
    previous_day: str | None = None
    seen: set[str] = set()
    for index, csv_row in enumerate(csv_rows):
        day = str(csv_row.get("time") or "")
        if not day or day in seen or (previous_day is not None and day <= previous_day):
            raise IntegrityError(f"selected market sessions are duplicate or unordered at row {index}: {day!r}")
        seen.add(day)
        previous_day = day
        if not DEVELOPMENT_START <= day <= DEVELOPMENT_END:
            raise IntegrityError(f"selected session outside frozen development window: {day}")
        month = str(csv_row.get("contractMonth") or "")
        row = {
            "time": day,
            "contractMonth": month,
            "open": _float_value(csv_row.get("open"), "open", index),
            "high": _float_value(csv_row.get("high"), "high", index),
            "low": _float_value(csv_row.get("low"), "low", index),
            "close": _float_value(csv_row.get("close"), "close", index),
            "change": _float_value(csv_row.get("change"), "change", index),
            "changePct": _float_value(csv_row.get("changePct"), "changePct", index),
            "volume": _float_value(csv_row.get("volume"), "volume", index),
            "openInterest": _float_value(csv_row.get("openInterest"), "openInterest", index),
            "settlement": _float_value(csv_row.get("settlement"), "settlement", index),
            "source": str(csv_row.get("source") or ""),
        }
        reconstructed = rebuilt[index]
        if row["time"] != reconstructed["time"] or row["contractMonth"] != str(reconstructed["contractMonth"]):
            raise IntegrityError(f"selected row differs from reconstruction from frozen raw inputs: {day}")
        for field in ("open", "high", "low", "close", "change", "changePct", "volume", "openInterest", "settlement"):
            if row[field] != float(reconstructed[field]):
                raise IntegrityError(f"selected {field} differs from raw rebuild on {day}")

        trace_row = trace_rows[index]
        rebuilt_trace = trace[index]
        if trace_row["marketDate"] != day or trace_row["selectedContractMonth"] != month:
            raise IntegrityError(f"selection trace date/contract mismatch on {day}")
        if trace_row["selectionRule"] != "HIGHEST_DAILY_VOLUME_TX_CONTRACT":
            raise IntegrityError(f"selection rule drift on {day}: {trace_row['selectionRule']}")
        if trace_row["selectionReason"] not in {"HIGHEST_VOLUME", "HIGHEST_VOLUME_TIE_FIRST_SOURCE_ROW"}:
            raise IntegrityError(f"unexpected selection reason on {day}: {trace_row['selectionReason']}")
        if float(trace_row["selectedVolume"]) != row["volume"]:
            raise IntegrityError(f"selection trace volume mismatch on {day}")
        if trace_row["marketDate"] != rebuilt_trace["marketDate"]:
            raise IntegrityError(f"selection trace differs from frozen-raw reconstruction on {day}")
        parsed_rows.append(row)

    if parsed_rows[0]["time"] != DEVELOPMENT_START or parsed_rows[-1]["time"] != DEVELOPMENT_END:
        raise IntegrityError("selected series does not span the exact authorized date window")
    if inventory.get("selectionRule") != v1r1.SELECTION_RULE:
        raise IntegrityError("raw inventory selection rule differs from frozen V1R1 contract")
    if inventory.get("tieMarketDates"):
        raise IntegrityError("V1R1 inventory unexpectedly contains maximum-volume ties")
    source_hashes = _verify_source_evidence_hashes()
    if len(inventory.get("selectedDistinctContractMonths", [])) == 0:
        raise IntegrityError("raw inventory has no selected contract-month provenance")

    raw_windows = [
        {
            "file": entry["file"],
            "sha256": entry["sha256"],
            "windowStart": entry["windowStart"],
            "windowEnd": entry["windowEnd"],
            "retrievedAt": entry.get("retrievedAt"),
            "retrievedAtSource": entry.get("retrievedAtSource"),
            "httpStatus": entry.get("httpStatus"),
        }
        for entry in raw_entries
    ]
    input_inventory = {
        "evidenceClass": EVIDENCE_CLASS,
        "classification": "RESEARCH_ONLY / NOT_PRODUCTION / NOT_FINAL_VALIDATION / NOT_PROSPECTIVE",
        "source": inventory.get("source"),
        "sourceEndpoint": inventory.get("sourceEndpoint"),
        "sourceDatasetDateRange": {"start": parsed_rows[0]["time"], "end": parsed_rows[-1]["time"]},
        "selectedSessionCount": len(parsed_rows),
        "selectedSeriesPath": str(SERIES_PATH.relative_to(ROOT)).replace("\\", "/"),
        "selectedSeriesSha256": sha256_file(SERIES_PATH),
        "selectionTracePath": str(SELECTION_TRACE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "selectionTraceSha256": sha256_file(SELECTION_TRACE_PATH),
        "rawInventoryPath": str(INPUT_INVENTORY_PATH.relative_to(ROOT)).replace("\\", "/"),
        "rawInventorySha256": sha256_file(INPUT_INVENTORY_PATH),
        "rawWindowCount": len(raw_windows),
        "rawWindows": raw_windows,
        "selectionRule": v1r1.SELECTION_RULE,
        "tieMarketDates": inventory.get("tieMarketDates", []),
        "selectedContractMonths": inventory.get("selectedDistinctContractMonths", []),
        "sourceEvidenceHashes": source_hashes,
        "sourceVintageStatus": "NOT PROVEN",
        "historicalPublicationTiming": "NOT PROVEN",
        "historicalVintage": "NOT PROVEN",
        "revisionHistory": "NOT PROVEN",
        "retrievedAtNote": "V1R1 retrieval timestamps were recovered from raw-file modification times; they are not historical provider publication timestamps.",
    }
    return parsed_rows, input_inventory


def _number(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def derive_features(rows: list[dict[str, Any]], index: int) -> tuple[dict[str, float] | None, str | None, float | None]:
    """Derive the six frozen V2 features at session D without imputation."""
    if index < 20:
        return None, None, None
    close_d = _number(rows[index], "close")
    close_5 = _number(rows[index - 5], "close")
    close_1 = _number(rows[index - 1], "close")
    close_20 = _number(rows[index - 20], "close")
    high_d = _number(rows[index], "high")
    low_d = _number(rows[index], "low")
    volume_d = _number(rows[index], "volume")
    volumes_prior = [_number(rows[pos], "volume") for pos in range(index - 5, index)]
    highs_20 = [_number(rows[pos], "high") for pos in range(index - 19, index + 1)]
    lows_20 = [_number(rows[pos], "low") for pos in range(index - 19, index + 1)]
    highs_5 = [_number(rows[pos], "high") for pos in range(index - 4, index + 1)]
    lows_5 = [_number(rows[pos], "low") for pos in range(index - 4, index + 1)]
    needed = [close_d, close_5, close_1, close_20, high_d, low_d, volume_d, *volumes_prior, *highs_20, *lows_20, *highs_5, *lows_5]
    if any(value is None for value in needed):
        return None, None, None
    assert close_d is not None and close_5 is not None and close_1 is not None and close_20 is not None
    assert high_d is not None and low_d is not None and volume_d is not None
    prior_volumes = [float(value) for value in volumes_prior if value is not None]
    high_values_20 = [float(value) for value in highs_20 if value is not None]
    low_values_20 = [float(value) for value in lows_20 if value is not None]
    high_values_5 = [float(value) for value in highs_5 if value is not None]
    low_values_5 = [float(value) for value in lows_5 if value is not None]
    if close_d <= 0 or close_5 <= 0 or close_1 <= 0 or close_20 <= 0:
        return None, None, None
    if not (high_d >= low_d and all(high >= low for high, low in zip(high_values_20, low_values_20))):
        return None, None, None
    momentum_return = close_d / close_5 - 1.0
    sign5 = 1.0 if momentum_return > 0 else -1.0 if momentum_return < 0 else 0.0
    prior_volume_mean = sum(prior_volumes) / 5.0
    location_range = max(high_values_20) - min(low_values_20)
    if prior_volume_mean <= 0 or location_range <= 0:
        return None, None, None
    features = {
        "momentum_strength_5": abs(momentum_return),
        "range_pct_1": (high_d - low_d) / close_d,
        "trend_alignment_20": sign5 * (close_d / close_20 - 1.0),
        "volume_confirmation_5": sign5 * (close_d / close_1 - 1.0) * (volume_d / prior_volume_mean - 1.0),
        "directional_price_location_20": sign5 * (
            2.0 * (close_d - min(low_values_20)) / location_range - 1.0
        ),
        "range_pct_5": (max(high_values_5) - min(low_values_5)) / close_d,
    }
    if any(not math.isfinite(value) for value in features.values()):
        return None, None, None
    direction = "RESEARCH_LONG" if sign5 > 0 else "RESEARCH_SHORT" if sign5 < 0 else "UNAVAILABLE"
    return features, direction, sign5


def _candidate_for_index(rows: list[dict[str, Any]], index: int) -> dict[str, Any]:
    row = rows[index]
    base = {"index": index, "decisionDate": row["time"], "selectedContractMonth": row["contractMonth"]}
    if index < 20:
        return {**base, "status": "LOOKBACK_WARMUP_EXCLUDED", "exclusionReason": "LESS_THAN_20_PRIOR_SESSIONS"}
    features, direction, sign5 = derive_features(rows, index)
    if features is None or direction is None or sign5 is None:
        return {**base, "status": "FEATURE_INCOMPLETE", "exclusionReason": "MISSING_OR_INVALID_REQUIRED_FEATURE_FIELD"}
    if direction == "UNAVAILABLE":
        return {**base, "status": "DIRECTION_INELIGIBLE", "features": features, "exclusionReason": "ZERO_FIVE_SESSION_DIRECTION"}
    if index + 1 >= len(rows):
        return {**base, "status": "TARGET_UNAVAILABLE", "features": features, "direction": direction,
                "exclusionReason": "NO_NEXT_OBSERVED_MARKET_SESSION"}
    next_close = _number(rows[index + 1], "close")
    current_close = _number(row, "close")
    if next_close is None or current_close is None or next_close <= 0 or current_close <= 0:
        return {**base, "status": "TARGET_UNAVAILABLE", "features": features, "direction": direction,
                "exclusionReason": "MISSING_OR_INVALID_TARGET_CLOSE"}

    month = str(row["contractMonth"])
    feature_roll = any(str(rows[pos]["contractMonth"]) != month for pos in range(index - 20, index + 1))
    target_roll = str(rows[index + 1]["contractMonth"]) != month
    if feature_roll or target_roll:
        reasons = []
        if feature_roll:
            reasons.append("FEATURE_WINDOW_CONTRACT_TRANSITION_D_MINUS_20_TO_D")
        if target_roll:
            reasons.append("TARGET_CONTRACT_TRANSITION_D_TO_D_PLUS_1")
        return {
            **base,
            "status": "ROLL_INELIGIBLE",
            "features": features,
            "direction": direction,
            "featureRollIneligible": feature_roll,
            "targetRollIneligible": target_roll,
            "exclusionReason": "+".join(reasons),
        }

    aligned_return = (1.0 if sign5 > 0 else -1.0) * (next_close / current_close - 1.0)
    if aligned_return == 0:
        return {**base, "status": "FLAT_TARGET_EXCLUDED", "features": features, "direction": direction,
                "targetDate": rows[index + 1]["time"], "exclusionReason": "FLAT_ALIGNED_T_PLUS_1_RETURN"}
    return {
        **base,
        "status": "ELIGIBLE_MATURED_LABEL",
        "features": features,
        "direction": direction,
        "targetDate": rows[index + 1]["time"],
        "decisionAlignedReturn": aligned_return,
        "value": 1 if aligned_return > 0 else 0,
        "labelMaturityBasis": "NEXT_OBSERVED_MARKET_SESSION_DATE; SOURCE_PUBLICATION_AVAILABILITY_NOT_PROVEN",
        "exclusionReason": None,
    }


def _sigmoid(value: float) -> float:
    if value >= 0:
        inverse = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + inverse)
    exponent = math.exp(max(value, -700.0))
    return exponent / (1.0 + exponent)


def fit_logistic(training: list[dict[str, Any]]) -> dict[str, Any]:
    if len(training) < MIN_TRAINING_SAMPLES:
        raise ValueError("insufficient prior matured training samples")
    labels = {int(row["value"]) for row in training}
    if labels != {0, 1}:
        raise ValueError("both prior matured target classes are required")
    means = [sum(float(row["features"][name]) for row in training) / len(training) for name in FEATURE_NAMES]
    stds = []
    for feature_index, name in enumerate(FEATURE_NAMES):
        variance = sum((float(row["features"][name]) - means[feature_index]) ** 2 for row in training) / len(training)
        stds.append(math.sqrt(variance))
    normalized_matrix = [
        [
            (float(row["features"][name]) - means[index]) / stds[index] if stds[index] > 0 else 0.0
            for index, name in enumerate(FEATURE_NAMES)
        ]
        for row in training
    ]
    positives = sum(int(row["value"]) for row in training)
    negatives = len(training) - positives
    intercept_initialization = math.log((positives + 0.5) / (negatives + 0.5))
    initial_weights = [intercept_initialization] + [0.0] * len(FEATURE_NAMES)
    weights = list(initial_weights)
    for _ in range(LOGISTIC_ITERATIONS):
        gradients = [0.0] * (len(FEATURE_NAMES) + 1)
        for features, row in zip(normalized_matrix, training):
            probability = _sigmoid(weights[0] + sum(weights[idx + 1] * features[idx] for idx in range(len(FEATURE_NAMES))))
            error = probability - int(row["value"])
            gradients[0] += error
            for index, feature_value in enumerate(features):
                gradients[index + 1] += error * feature_value
        scale = 1.0 / len(training)
        weights[0] -= LEARNING_RATE * gradients[0] * scale
        for index in range(len(FEATURE_NAMES)):
            weights[index + 1] -= LEARNING_RATE * (
                gradients[index + 1] * scale + L2_PENALTY * weights[index + 1]
            )
    return {
        "means": means,
        "stds": stds,
        "weights": weights,
        "initialWeights": initial_weights,
        "interceptInitialization": intercept_initialization,
        "positiveCount": positives,
        "negativeCount": negatives,
    }


def predict_probability(features: dict[str, float], model: dict[str, Any]) -> float:
    normalized = [
        (float(features[name]) - model["means"][index]) / model["stds"][index]
        if model["stds"][index] > 0 else 0.0
        for index, name in enumerate(FEATURE_NAMES)
    ]
    return _sigmoid(model["weights"][0] + sum(model["weights"][index + 1] * value for index, value in enumerate(normalized)))


def _brier(pairs: list[dict[str, Any]], key: str) -> float | None:
    if not pairs:
        return None
    return sum((float(pair[key]) - int(pair["outcome"])) ** 2 for pair in pairs) / len(pairs)


def _roc_auc(pairs: list[dict[str, Any]], probability_key: str = "probability") -> float | None:
    positives = sum(int(pair["outcome"]) for pair in pairs)
    negatives = len(pairs) - positives
    if not positives or not negatives:
        return None
    ordered = sorted((float(pair[probability_key]), int(pair["outcome"])) for pair in pairs)
    positive_rank_sum = 0.0
    rank = 1
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        average_rank = (rank + rank + (end - index) - 1) / 2.0
        positive_rank_sum += average_rank * sum(label for _, label in ordered[index:end])
        rank += end - index
        index = end
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def _reliability(pairs: list[dict[str, Any]], key: str) -> tuple[list[dict[str, Any]], float | None]:
    buckets: list[list[dict[str, Any]]] = [[] for _ in range(ECE_BUCKETS)]
    for pair in pairs:
        probability = float(pair[key])
        bucket_index = min(int(probability * ECE_BUCKETS), ECE_BUCKETS - 1)
        buckets[bucket_index].append(pair)
    rows = []
    ece = 0.0
    total = len(pairs)
    for index, bucket in enumerate(buckets):
        count = len(bucket)
        mean_probability = sum(float(row[key]) for row in bucket) / count if count else None
        event_rate = sum(int(row["outcome"]) for row in bucket) / count if count else None
        if count:
            ece += count / total * abs(mean_probability - event_rate)
        rows.append({
            "bucketIndex": index,
            "lowerInclusive": index / ECE_BUCKETS,
            "upperExclusive": (index + 1) / ECE_BUCKETS if index < ECE_BUCKETS - 1 else 1.0,
            "count": count,
            "meanProbability": mean_probability,
            "eventRate": event_rate,
        })
    return rows, ece if total else None


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _bootstrap(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    if not pairs:
        return {
            "status": "NOT_RUN_NO_VALID_DEVELOPMENT_OOS_PAIRS",
            "method": "PAIRED_CIRCULAR_MOVING_BLOCK_BOOTSTRAP",
            "blockSize": BOOTSTRAP_BLOCK_SIZE,
            "iterations": BOOTSTRAP_ITERATIONS,
            "seed": BOOTSTRAP_SEED,
            "confidenceLevel": 0.95,
            "invalidSingleClassAucReplicates": 0,
            "validAucReplicates": 0,
            "brierDifference95Ci": None,
            "auc95Ci": None,
        }
    rng = random.Random(BOOTSTRAP_SEED)
    count = len(pairs)
    brier_differences: list[float] = []
    auc_values: list[float] = []
    invalid_auc = 0
    for _ in range(BOOTSTRAP_ITERATIONS):
        sampled_indices: list[int] = []
        while len(sampled_indices) < count:
            start = rng.randrange(count)
            sampled_indices.extend((start + offset) % count for offset in range(BOOTSTRAP_BLOCK_SIZE))
        sample = [pairs[index] for index in sampled_indices[:count]]
        brier_differences.append(_brier(sample, "probability") - _brier(sample, "naiveProbability"))
        auc = _roc_auc(sample)
        if auc is None:
            invalid_auc += 1
        else:
            auc_values.append(auc)
    return {
        "status": "COMPLETE",
        "method": "PAIRED_CIRCULAR_MOVING_BLOCK_BOOTSTRAP",
        "blockSize": BOOTSTRAP_BLOCK_SIZE,
        "iterations": BOOTSTRAP_ITERATIONS,
        "seed": BOOTSTRAP_SEED,
        "confidenceLevel": 0.95,
        "brierDifferenceDefinition": "MODEL_BRIER_MINUS_PAST_ONLY_NAIVE_BRIER",
        "brierDifference95Ci": [_percentile(brier_differences, 0.025), _percentile(brier_differences, 0.975)],
        "auc95Ci": [_percentile(auc_values, 0.025), _percentile(auc_values, 0.975)] if auc_values else None,
        "validAucReplicates": len(auc_values),
        "invalidSingleClassAucReplicates": invalid_auc,
        "invalidAucReplicatesWereNotReplaced": True,
        "samplePairCount": count,
        "developmentOnly": True,
        "notFinalValidation": True,
    }


def _quarter(day: str) -> str:
    parsed = date.fromisoformat(day)
    return f"{parsed.year}-Q{(parsed.month - 1) // 3 + 1}"


def _distribution(pairs: list[dict[str, Any]], key: str) -> dict[str, Any]:
    values = [float(row[key]) for row in pairs]
    counts = [0] * ECE_BUCKETS
    for value in values:
        counts[min(int(value * ECE_BUCKETS), ECE_BUCKETS - 1)] += 1
    return {
        "count": len(values),
        "mean": sum(values) / len(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        "bins": [
            {"lowerInclusive": i / ECE_BUCKETS, "upperExclusive": (i + 1) / ECE_BUCKETS if i < ECE_BUCKETS - 1 else 1.0,
             "count": counts[i]}
            for i in range(ECE_BUCKETS)
        ],
    }


def _coefficient_diagnostics(training_trace: list[dict[str, Any]]) -> dict[str, Any]:
    names = ["intercept", *FEATURE_NAMES]
    by_name: dict[str, Any] = {}
    for index, name in enumerate(names):
        values = [float(row["finalCoefficients"][index]) for row in training_trace]
        signs = [1 if value > 0 else -1 if value < 0 else 0 for value in values]
        nonzero_signs = [sign for sign in signs if sign]
        transitions = sum(left != right for left, right in zip(nonzero_signs, nonzero_signs[1:]))
        by_name[name] = {
            "count": len(values),
            "mean": sum(values) / len(values) if values else None,
            "populationStd": math.sqrt(sum((value - sum(values) / len(values)) ** 2 for value in values) / len(values)) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "signTransitionsIgnoringExactZero": transitions,
        }
    return {
        "coefficients": by_name,
        "initializationContract": {
            "intercept": "log((positive_count + 0.5) / (negative_count + 0.5)) per prior training set",
            "featureWeights": "all six initialize to 0.0",
        },
    }


def _metric_bundle(pairs: list[dict[str, Any]], traces: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    count = len(pairs)
    positives = sum(int(row["outcome"]) for row in pairs)
    negatives = count - positives
    model_brier = _brier(pairs, "probability")
    naive_brier = _brier(pairs, "naiveProbability")
    brier_difference = model_brier - naive_brier if model_brier is not None and naive_brier is not None else None
    bss = 1.0 - model_brier / naive_brier if model_brier is not None and naive_brier not in (None, 0.0) else None
    model_bins, model_ece = _reliability(pairs, "probability")
    naive_bins, naive_ece = _reliability(pairs, "naiveProbability")
    reliability_rows = [
        {"series": name, **row}
        for name, bucket_rows in (("model", model_bins), ("naive", naive_bins))
        for row in bucket_rows
    ]

    overall_rate = positives / count if count else None
    reliability = resolution = uncertainty = None
    if count:
        reliability = sum((row["count"] / count) * (row["meanProbability"] - row["eventRate"]) ** 2
                          for row in model_bins if row["count"])
        resolution = sum((row["count"] / count) * (row["eventRate"] - overall_rate) ** 2
                         for row in model_bins if row["count"])
        uncertainty = overall_rate * (1.0 - overall_rate)

    quarterly: dict[str, list[dict[str, Any]]] = {}
    for pair in pairs:
        quarterly.setdefault(_quarter(pair["forecastDate"]), []).append(pair)
    quarterly_rows = []
    for quarter, rows in sorted(quarterly.items()):
        quarter_positive = sum(int(row["outcome"]) for row in rows)
        quarterly_rows.append({
            "quarter": quarter,
            "pairCount": len(rows),
            "positiveRate": quarter_positive / len(rows),
            "modelBrier": _brier(rows, "probability"),
            "naiveBrier": _brier(rows, "naiveProbability"),
            "modelAuc": _roc_auc(rows),
        })
    rolling_rows = []
    for index, pair in enumerate(pairs):
        window = pairs[max(0, index - 19):index + 1]
        rolling_rows.append({
            "forecastDate": pair["forecastDate"],
            "windowCount": len(window),
            "rolling20Brier": _brier(window, "probability"),
            "expandingCumulativeBrier": _brier(pairs[:index + 1], "probability"),
        })

    model_losses = sorted(
        [((float(row["probability"]) - int(row["outcome"])) ** 2, row) for row in pairs],
        key=lambda item: (-item[0], item[1]["forecastDate"]),
    )
    total_model_loss = sum(loss for loss, _ in model_losses)
    cumulative = 0.0
    largest_error_rows = []
    for rank, (loss, pair) in enumerate(model_losses, 1):
        cumulative += loss
        largest_error_rows.append({
            "rankByModelBrierLoss": rank,
            "forecastDate": pair["forecastDate"],
            "targetDate": pair["targetDate"],
            "probability": pair["probability"],
            "outcome": pair["outcome"],
            "modelBrierLoss": loss,
            "shareOfTotalModelBrierLoss": loss / total_model_loss if total_model_loss else None,
            "cumulativeShare": cumulative / total_model_loss if total_model_loss else None,
        })
    top10 = sum(loss for loss, _ in model_losses[:10]) / total_model_loss if total_model_loss else None
    top20 = sum(loss for loss, _ in model_losses[:20]) / total_model_loss if total_model_loss else None

    base_rate_rows = []
    for quarter, rows in sorted(quarterly.items()):
        base_rate_rows.append({
            "quarter": quarter,
            "pairCount": len(rows),
            "meanPastOnlyTrainingBaseRate": sum(float(row["naiveProbability"]) for row in rows) / len(rows),
            "realizedPositiveRate": sum(int(row["outcome"]) for row in rows) / len(rows),
            "realizedMinusMeanPastBaseRate": sum(int(row["outcome"]) for row in rows) / len(rows)
            - sum(float(row["naiveProbability"]) for row in rows) / len(rows),
        })

    model_vs_naive = []
    for pair in pairs:
        model_loss = (float(pair["probability"]) - int(pair["outcome"])) ** 2
        naive_loss = (float(pair["naiveProbability"]) - int(pair["outcome"])) ** 2
        model_vs_naive.append({
            **pair,
            "modelBrierLoss": model_loss,
            "naiveBrierLoss": naive_loss,
            "modelMinusNaiveBrierLoss": model_loss - naive_loss,
            "calendarQuarter": _quarter(pair["forecastDate"]),
        })

    metrics = {
        "evidenceClass": EVIDENCE_CLASS,
        "classification": "HISTORICAL DEVELOPMENT ONLY / NOT FINAL VALIDATION",
        "pairCount": count,
        "positiveCount": positives,
        "negativeCount": negatives,
        "realizedPositiveRate": overall_rate,
        "modelBrier": model_brier,
        "naiveBrier": naive_brier,
        "brierDifferenceModelMinusNaive": brier_difference,
        "brierSkillScore": bss,
        "rocAucDiscrimination": _roc_auc(pairs),
        "modelEce10EqualWidthBins": model_ece,
        "naiveEce10EqualWidthBins": naive_ece,
        "brierDecomposition": {
            "reliability": reliability,
            "resolution": resolution,
            "uncertainty": uncertainty,
            "reliabilityMinusResolutionPlusUncertainty": reliability - resolution + uncertainty
            if reliability is not None and resolution is not None and uncertainty is not None else None,
            "limitation": "Binned descriptive decomposition; finite-bin approximation is not an exact unbinned identity.",
        },
        "quarterlyPerformance": quarterly_rows,
        "rollingAndCumulativeBrier": rolling_rows,
        "top10BrierLossShare": top10,
        "top20BrierLossShare": top20,
        "coefficientStability": _coefficient_diagnostics(traces),
        "sourceLimitations": {
            "historicalPublicationTiming": "NOT PROVEN",
            "historicalVintage": "NOT PROVEN",
            "revisionHistory": "NOT PROVEN",
        },
    }
    return metrics, reliability_rows, _distribution(pairs, "probability"), base_rate_rows, largest_error_rows, model_vs_naive


def run_development(rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [_candidate_for_index(rows, index) for index in range(len(rows))]
    funnel = {
        "totalSelectedSessions": len(rows),
        "lookbackWarmupExcluded": sum(row["status"] == "LOOKBACK_WARMUP_EXCLUDED" for row in candidates),
        "rollIneligible": sum(row["status"] == "ROLL_INELIGIBLE" for row in candidates),
        "featureRollIneligible": sum(bool(row.get("featureRollIneligible")) for row in candidates),
        "targetRollIneligible": sum(bool(row.get("targetRollIneligible")) for row in candidates),
        "featureIncomplete": sum(row["status"] == "FEATURE_INCOMPLETE" for row in candidates),
        "directionIneligible": sum(row["status"] == "DIRECTION_INELIGIBLE" for row in candidates),
        "targetUnavailable": sum(row["status"] == "TARGET_UNAVAILABLE" for row in candidates),
        "flatTargetExcluded": sum(row["status"] == "FLAT_TARGET_EXCLUDED" for row in candidates),
        "maturedEligibleLabels": sum(row["status"] == "ELIGIBLE_MATURED_LABEL" for row in candidates),
        "insufficientTrainingUnder30": 0,
        "singleClassTraining": 0,
        "forecastGenerated": 0,
        "validDevelopmentOosPairs": 0,
    }
    forecasts: list[dict[str, Any]] = []
    pairs: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    eligible = [row for row in candidates if row["status"] == "ELIGIBLE_MATURED_LABEL"]
    for candidate in eligible:
        forecast_date = candidate["decisionDate"]
        training = [
            item for item in eligible
            if item["index"] < candidate["index"]
            and item["decisionDate"] < forecast_date
            and item["targetDate"] < forecast_date
        ]
        if len(training) < MIN_TRAINING_SAMPLES:
            funnel["insufficientTrainingUnder30"] += 1
            continue
        if {int(item["value"]) for item in training} != {0, 1}:
            funnel["singleClassTraining"] += 1
            continue
        model = fit_logistic(training)
        probability = predict_probability(candidate["features"], model)
        naive_probability = sum(int(item["value"]) for item in training) / len(training)
        fit_cutoff = max(item["targetDate"] for item in training)
        if not fit_cutoff < forecast_date:
            raise IntegrityError(f"future or unmatured training label entered fit for {forecast_date}")
        if not all(item["targetDate"] < forecast_date and item["decisionDate"] < forecast_date for item in training):
            raise IntegrityError(f"training row chronology failed for {forecast_date}")
        trace = {
            "forecastDate": forecast_date,
            "targetDate": candidate["targetDate"],
            "fitCutoff": fit_cutoff,
            "trainingSampleCount": len(training),
            "trainingPositiveCount": model["positiveCount"],
            "trainingNegativeCount": model["negativeCount"],
            "trainingStartDecisionDate": training[0]["decisionDate"],
            "trainingEndDecisionDate": training[-1]["decisionDate"],
            "trainingStartTargetDate": training[0]["targetDate"],
            "trainingEndTargetDate": training[-1]["targetDate"],
            "labelMaturityBasis": "TARGET_DATE_STRICTLY_BEFORE_FORECAST; SOURCE_PUBLICATION_AVAILABILITY_NOT_PROVEN",
            "normalizationSourceRange": [training[0]["decisionDate"], training[-1]["decisionDate"]],
            "normalizationMeans": model["means"],
            "normalizationPopulationStds": model["stds"],
            "interceptInitialization": model["interceptInitialization"],
            "featureWeightInitialization": [0.0] * len(FEATURE_NAMES),
            "initialCoefficients": model["initialWeights"],
            "finalCoefficients": model["weights"],
            "coefficientOrder": ["intercept", *FEATURE_NAMES],
            "featureValues": candidate["features"],
            "trainingValuesFingerprint": sha256_bytes(canonical_json_bytes([
                {"decisionDate": item["decisionDate"], "targetDate": item["targetDate"], "value": item["value"], "features": item["features"]}
                for item in training
            ])),
            "contractMonth": candidate["selectedContractMonth"],
            "evidenceClass": EVIDENCE_CLASS,
            "modelId": MODEL_ID,
        }
        forecast = {
            "forecastDate": forecast_date,
            "targetDate": candidate["targetDate"],
            "fitCutoff": fit_cutoff,
            "researchDirection": candidate["direction"],
            "selectedContractMonth": candidate["selectedContractMonth"],
            "probability": probability,
            "naiveProbability": naive_probability,
            "trainingSampleCount": len(training),
            "trainingPositiveCount": model["positiveCount"],
            "trainingNegativeCount": model["negativeCount"],
            "featureValues": candidate["features"],
            "evidenceClass": EVIDENCE_CLASS,
            "contractId": CONTRACT_ID,
            "modelId": MODEL_ID,
            "targetId": TARGET_ID,
            "finalValidation": False,
            **{f"feature_{name}": candidate["features"][name] for name in FEATURE_NAMES},
        }
        pair = {
            **forecast,
            "outcome": candidate["value"],
            "decisionAlignedReturn": candidate["decisionAlignedReturn"],
            "targetMaturedDate": candidate["targetDate"],
        }
        forecasts.append(forecast)
        pairs.append(pair)
        traces.append(trace)

    funnel["forecastGenerated"] = len(forecasts)
    funnel["validDevelopmentOosPairs"] = len(pairs)
    feature_matrix = []
    for candidate in candidates:
        row = {
            "marketDate": candidate["decisionDate"],
            "selectedContractMonth": candidate["selectedContractMonth"],
            "status": candidate["status"],
            "exclusionReason": candidate.get("exclusionReason"),
            "targetDate": candidate.get("targetDate"),
            "researchDirection": candidate.get("direction"),
            "featureRollIneligible": candidate.get("featureRollIneligible"),
            "targetRollIneligible": candidate.get("targetRollIneligible"),
            "decisionAlignedReturn": candidate.get("decisionAlignedReturn"),
            "target": candidate.get("value"),
        }
        row.update(candidate.get("features", {}))
        feature_matrix.append(row)

    metrics, reliability_rows, distribution, base_rate_rows, largest_errors, model_vs_naive = _metric_bundle(pairs, traces)
    bootstrap = _bootstrap(pairs)
    brier_ci = bootstrap.get("brierDifference95Ci")
    auc_ci = bootstrap.get("auc95Ci")
    if not pairs or metrics["rocAucDiscrimination"] is None or auc_ci is None or brier_ci is None:
        gate = "NOT AVAILABLE — REQUIRED DEVELOPMENT OOS EVIDENCE IS INSUFFICIENT"
        development_status = "BLOCKED"
    elif brier_ci[1] < 0 and auc_ci[0] > 0.5:
        gate = "WOULD MEET FROZEN CRITERIA"
        development_status = "COMPLETE"
    else:
        gate = "WOULD NOT MEET FROZEN CRITERIA"
        development_status = "COMPLETE"

    first_forecast = None
    if forecasts:
        first = forecasts[0]
        first_trace = traces[0]
        first_forecast = {
            "forecastDate": first["forecastDate"],
            "fitCutoff": first["fitCutoff"],
            "trainingSampleCount": first["trainingSampleCount"],
            "trainingPositiveCount": first["trainingPositiveCount"],
            "trainingNegativeCount": first["trainingNegativeCount"],
            "normalizationSourceRange": first_trace["normalizationSourceRange"],
            "contractMonth": first["selectedContractMonth"],
            "strictlyPriorFitCutoff": first["fitCutoff"] < first["forecastDate"],
        }
    outcomes = [int(pair["outcome"]) for pair in pairs]
    development_summary = {
        "developmentStatus": development_status,
        "evidenceClass": EVIDENCE_CLASS,
        "classification": "HISTORICAL DEVELOPMENT ONLY — NOT FINAL VALIDATION / NOT PROSPECTIVE",
        "contractId": CONTRACT_ID,
        "modelId": MODEL_ID,
        "targetId": TARGET_ID,
        "dateRange": {"start": rows[0]["time"], "end": rows[-1]["time"]},
        "selectedSessionCount": len(rows),
        "eligibilityFunnel": funnel,
        "firstForecast": first_forecast,
        "oos": {
            "pairCount": len(pairs),
            "firstForecastDate": pairs[0]["forecastDate"] if pairs else None,
            "lastForecastDate": pairs[-1]["forecastDate"] if pairs else None,
            "positiveCount": sum(outcomes),
            "negativeCount": len(outcomes) - sum(outcomes),
        },
        "primaryMetrics": {key: metrics[key] for key in (
            "modelBrier", "naiveBrier", "brierDifferenceModelMinusNaive", "brierSkillScore", "rocAucDiscrimination"
        )},
        "developmentGateDiagnostic": gate,
        "researchSignalSupported": "NOT EVALUATED — HISTORICAL DEVELOPMENT IS NOT FINAL VALIDATION",
        "bootstrapStatus": bootstrap["status"],
        "sourceLimitations": {
            "historicalPublicationTiming": "NOT PROVEN",
            "historicalVintage": "NOT PROVEN",
            "revisionHistory": "NOT PROVEN",
        },
        "prospectiveEvidence": {"seedLabels": 0, "finalPairs": 0, "unchanged": True},
        "probabilityLabelAllowed": False,
        "productionP2_03": "BLOCKED — INSUFFICIENT PROSPECTIVE OOS CALIBRATION HISTORY",
        "v2FinalEvaluation": "NOT STARTED",
    }
    return {
        "featureMatrix": feature_matrix,
        "candidates": candidates,
        "funnel": funnel,
        "trainingTrace": traces,
        "forecasts": forecasts,
        "pairs": pairs,
        "metrics": metrics,
        "reliabilityRows": reliability_rows,
        "forecastDistribution": {
            "model": distribution,
            "naive": _distribution(pairs, "naiveProbability"),
            "classification": "DEVELOPMENT ONLY / NOT FINAL VALIDATION",
        },
        "baseRateDriftRows": base_rate_rows,
        "largestErrorRows": largest_errors,
        "modelVsNaiveRows": model_vs_naive,
        "bootstrap": bootstrap,
        "summary": development_summary,
    }


def _csv_bytes(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _run_outputs(run: dict[str, Any], input_inventory: dict[str, Any]) -> dict[str, bytes]:
    input_bytes = canonical_json_bytes(input_inventory) + b"\n"
    contract = {
        "contractId": CONTRACT_ID,
        "modelId": MODEL_ID,
        "evidenceClass": EVIDENCE_CLASS,
        "classification": "RESEARCH_ONLY / NOT_PRODUCTION / NOT_FINAL_VALIDATION / NOT_PROSPECTIVE",
        "effectiveProtocol": {
            "composition": "ORIGINAL_PROTOCOL_PLUS_AMENDMENT_001",
            "originalProtocolSha256": EXPECTED_HASHES["originalProtocol"],
            "amendment001Sha256": EXPECTED_HASHES["amendment001"],
            "effectiveIdentitySha256": EXPECTED_HASHES["effectiveIdentity"],
            "amendmentManifestSha256": EXPECTED_HASHES["amendmentManifest"],
        },
        "features": [
            {
                **spec,
                "formulaSection": "Original protocol §4; Amendment 001 changes initialization only",
                "lookbackStartOffset": {
                    "momentum_strength_5": -5, "range_pct_1": 0, "trend_alignment_20": -20,
                    "volume_confirmation_5": -5, "directional_price_location_20": -19, "range_pct_5": -4,
                }[spec["name"]],
                "lookbackEndOffset": 0,
                "rollRule": ROLL_RULE,
                "normalization": "PER_FORECAST_PRIOR_ELIGIBLE_TRAINING_ONLY; POPULATION_STD; ZERO_STD_MAPS_TO_ZERO",
                "pointInTimeRule": "FEATURES USE OBSERVATIONS AT OR BEFORE SESSION D; HISTORICAL SOURCE PUBLICATION AVAILABILITY NOT PROVEN",
                "missingDataRule": "EXCLUDE_ROW; NO_IMPUTATION",
            }
            for spec in FEATURE_SPECS
        ],
        "direction": "RESEARCH_LONG/SHORT from sign(close[D]/close[D-5]-1); zero excluded",
        "target": "DIRECTIONAL_SUCCESS",
        "horizon": "T+1 observed market session",
        "minimumTrainingSamples": MIN_TRAINING_SAMPLES,
        "bothClassesRequired": True,
        "training": "CHRONOLOGICAL_EXPANDING; PRIOR MATURED ELIGIBLE LABELS ONLY; TARGET DATE STRICTLY BEFORE FORECAST",
        "modelFamily": "DETERMINISTIC_STANDARD_LIBRARY_LOGISTIC_REGRESSION",
        "initialization": {
            "intercept": "math.log((positive_count + 0.5) / (negative_count + 0.5)) per prior training set",
            "featureWeights": "all six coefficients initialize to 0.0",
            "sourceV1Implementation": "scripts/p203_historical_research_replay.py:_fit",
        },
        "iterations": LOGISTIC_ITERATIONS,
        "learningRate": LEARNING_RATE,
        "l2Penalty": L2_PENALTY,
        "normalization": "PRIOR TRAINING ROWS ONLY; POPULATION STANDARD DEVIATION; ZERO STD MAPS TO ZERO",
        "naiveReference": "EXPANDING POSITIVE RATE FROM THE SAME PRIOR MATURED TRAINING LABELS",
        "sourceSelection": v1r1.SELECTION_RULE,
        "historicalFinalEvaluation": "NOT PRISTINE / NOT AVAILABLE",
        "independentFinalValidation": "FUTURE PROSPECTIVE DATA ONLY",
        "sourceLimitations": SOURCE_LIMITATION,
    }

    feature_columns = [
        "marketDate", "selectedContractMonth", "status", "exclusionReason", "targetDate", "researchDirection",
        "featureRollIneligible", "targetRollIneligible", "decisionAlignedReturn", "target", *FEATURE_NAMES,
    ]
    forecast_columns = [
        "forecastDate", "targetDate", "fitCutoff", "researchDirection", "selectedContractMonth", "probability",
        "naiveProbability", "trainingSampleCount", "trainingPositiveCount", "trainingNegativeCount",
        "evidenceClass", "contractId", "modelId", "targetId", "finalValidation",
        *[f"feature_{name}" for name in FEATURE_NAMES],
    ]
    trace_bytes = b"".join(canonical_json_bytes(row) + b"\n" for row in run["trainingTrace"])
    pair_columns = forecast_columns + ["outcome", "decisionAlignedReturn", "targetMaturedDate"]
    reliability_columns = ["series", "bucketIndex", "lowerInclusive", "upperExclusive", "count", "meanProbability", "eventRate"]
    drift_columns = ["quarter", "pairCount", "meanPastOnlyTrainingBaseRate", "realizedPositiveRate", "realizedMinusMeanPastBaseRate"]
    error_columns = ["rankByModelBrierLoss", "forecastDate", "targetDate", "probability", "outcome", "modelBrierLoss", "shareOfTotalModelBrierLoss", "cumulativeShare"]
    model_compare_columns = pair_columns + ["modelBrierLoss", "naiveBrierLoss", "modelMinusNaiveBrierLoss", "calendarQuarter"]
    return {
        "input_inventory.json": input_bytes,
        "feature_contract_runtime.json": canonical_json_bytes(contract) + b"\n",
        "feature_matrix.csv": _csv_bytes(run["featureMatrix"], feature_columns),
        "eligibility_funnel.json": canonical_json_bytes(run["funnel"]) + b"\n",
        "training_trace.jsonl": trace_bytes,
        "reconstructed_forecasts.csv": _csv_bytes(run["forecasts"], forecast_columns),
        "oos_pairs.csv": _csv_bytes(run["pairs"], pair_columns),
        "development_metrics.json": canonical_json_bytes(run["metrics"]) + b"\n",
        "reliability_bins.csv": _csv_bytes(run["reliabilityRows"], reliability_columns),
        "forecast_distribution.json": canonical_json_bytes(run["forecastDistribution"]) + b"\n",
        "coefficient_stability.json": canonical_json_bytes(run["metrics"]["coefficientStability"]) + b"\n",
        "base_rate_drift.csv": _csv_bytes(run["baseRateDriftRows"], drift_columns),
        "largest_errors.csv": _csv_bytes(run["largestErrorRows"], error_columns),
        "model_vs_naive.csv": _csv_bytes(run["modelVsNaiveRows"], model_compare_columns),
        "bootstrap_development_diagnostic.json": canonical_json_bytes(run["bootstrap"]) + b"\n",
        "development_summary.json": canonical_json_bytes(run["summary"]) + b"\n",
    }


def _ensure_output_isolated(output_dir: Path) -> None:
    temp_root = (ROOT / ".tmp").resolve()
    resolved = output_dir.resolve()
    if resolved == temp_root or temp_root not in resolved.parents:
        raise ValueError(f"research outputs must remain under {temp_root}")
    if resolved.exists() and any(resolved.iterdir()):
        raise FileExistsError(f"refusing to overwrite existing development artifacts: {resolved}")


def execute(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    _ensure_output_isolated(output_dir)
    protocol = _verify_effective_protocol()
    source_hashes_before = _verify_source_evidence_hashes()
    db_before = _database_snapshot()
    rows, input_inventory = _load_selected_series()

    first_run = run_development(rows)
    second_run = run_development(rows)
    first_outputs = _run_outputs(first_run, input_inventory)
    second_outputs = _run_outputs(second_run, input_inventory)
    first_fingerprints = {name: sha256_bytes(payload) for name, payload in sorted(first_outputs.items())}
    second_fingerprints = {name: sha256_bytes(payload) for name, payload in sorted(second_outputs.items())}
    if first_fingerprints != second_fingerprints:
        raise IntegrityError("two full V2 development replay runs produced different artifact fingerprints")

    determinism = {
        "twoRunsIdentical": True,
        "runCount": 2,
        "runFingerprints": [first_fingerprints, second_fingerprints],
        "comparedArtifacts": sorted(first_fingerprints),
        "evidenceClass": EVIDENCE_CLASS,
        "notFinalValidation": True,
    }
    determinism_bytes = canonical_json_bytes(determinism) + b"\n"
    outputs = {**first_outputs, "determinism_report.json": determinism_bytes}

    protocol_after = _verify_effective_protocol()
    source_hashes_after = _verify_source_evidence_hashes()
    db_after = _database_snapshot()
    if protocol_after["hashes"] != protocol["hashes"]:
        raise IntegrityError("frozen protocol artifact changed during V2 development")
    if source_hashes_after != source_hashes_before:
        raise IntegrityError("V1/V1R1/diagnostic source artifacts changed during V2 development")
    if db_after != db_before:
        raise IntegrityError("prospective DB changed during V2 development")

    manifest = {
        "manifestVersion": "P2-03-V2-HISTORICAL-DEVELOPMENT-1",
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "developmentStatus": first_run["summary"]["developmentStatus"],
        "evidenceClass": EVIDENCE_CLASS,
        "classification": "HISTORICAL DEVELOPMENT ONLY / NOT FINAL VALIDATION / NOT PROSPECTIVE / NOT PRODUCTION",
        "featureContractId": CONTRACT_ID,
        "modelId": MODEL_ID,
        "targetId": TARGET_ID,
        "effectiveProtocolHashes": protocol["hashes"],
        "inputInventorySha256": sha256_bytes(outputs["input_inventory.json"]),
        "selectedInputSha256": input_inventory["selectedSeriesSha256"],
        "selectionTraceSha256": input_inventory["selectionTraceSha256"],
        "rawInventorySha256": input_inventory["rawInventorySha256"],
        "sourceEvidenceHashesUnchanged": True,
        "prospectiveDbBeforeAfter": {"before": db_before, "after": db_after},
        "determinism": determinism,
        "outputSha256": {name: sha256_bytes(payload) for name, payload in sorted(outputs.items())},
        "protocolSourceLimitations": {
            "historicalPublicationTiming": "NOT PROVEN",
            "historicalVintage": "NOT PROVEN",
            "revisionHistory": "NOT PROVEN",
        },
        "probabilityLabelAllowed": False,
        "productionP2_03": "BLOCKED",
        "v2FinalEvaluation": "NOT STARTED",
    }
    outputs["development_manifest.json"] = canonical_json_bytes(manifest) + b"\n"

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in outputs.items():
        target = output_dir / name
        if target.exists():
            raise FileExistsError(f"refusing to overwrite development artifact: {target}")
        target.write_bytes(payload)
    written_hashes = {name: sha256_file(output_dir / name) for name in outputs}
    expected_written_hashes = manifest["outputSha256"]
    if any(written_hashes[name] != expected for name, expected in expected_written_hashes.items()):
        raise IntegrityError("written V2 development artifact hash mismatch")
    if _database_snapshot() != db_before:
        raise IntegrityError("prospective DB changed after development output write")
    return {
        "outputDir": str(output_dir),
        "developmentStatus": first_run["summary"]["developmentStatus"],
        "evidenceClass": EVIDENCE_CLASS,
        "pairCount": len(first_run["pairs"]),
        "developmentGateDiagnostic": first_run["summary"]["developmentGateDiagnostic"],
        "twoRunsIdentical": True,
        "outputSha256": written_hashes,
        "manifestSha256": sha256_file(output_dir / "development_manifest.json"),
        "summary": first_run["summary"],
        "dbBeforeAfter": {"before": db_before, "after": db_after},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    result = execute(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
