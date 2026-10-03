"""Read-only, fail-closed P2-05 market-score regime performance analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "p203-prospective-ledger.sqlite3"
OUTPUT_DIR = ROOT / ".tmp" / "p205-regime-performance"
MANIFEST_PATH = ROOT / ".tmp" / "p205-formal-closure" / "manifest.json"
CONTRACT_PATH = ROOT / "docs" / "P2_05_REGIME_PERFORMANCE_CONTRACT.md"
CLOSURE_PATH = ROOT / "docs" / "P2_05_FORMAL_CLOSURE.md"
STATUS_PATH = ROOT / "docs" / "INVESTMENT_DECISION_EXECUTION_STATUS.md"
P204_CLOSURE_PATH = ROOT / "docs" / "P2_04_FORMAL_CLOSURE.md"
CONTRACT_NAME = "P2_05_MARKET_SCORE_REGIME_V1"
REGIME_LABELS = ("LOW", "MID", "HIGH")
CANONICAL_STATUSES = ("EVALUATED", "PENDING", "NOT_APPLICABLE", "UNAVAILABLE", "INVALID")
STATUS_BASIS_MAP = {
    "EVALUATED": {"DIRECTIONAL_RETURN"},
    "PENDING": {"DIRECTIONAL_RETURN"},
    "NOT_APPLICABLE": {"NOT_APPLICABLE"},
    "UNAVAILABLE": {"DIRECTIONAL_RETURN", "UNAVAILABLE"},
    "INVALID": {"UNAVAILABLE"},
}
CSV_FIELDS = {
    "regime_coverage.csv": ("regime", "decisionCount", "count", "missingMarketScoreCount", "invalidMarketScoreCount", "semantics"),
    "decision_outcome_join_audit.csv": ("decisionId", "evaluationHorizon", "regime", "joinStatus", "outcomeStatus", "evaluationBasis", "reasons"),
    "eligibility_audit.csv": ("decisionId", "evaluationHorizon", "regime", "eligible", "reasons"),
    "regime_performance.csv": ("regime", "evaluationHorizon", "contract", "n", "evaluatedCount", "positiveCount", "negativeCount", "flatCount", "successRate", "meanDecisionAlignedReturn", "medianDecisionAlignedReturn", "interpretation"),
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def parse_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def stable_sort_key(value: dict[str, Any]) -> bytes:
    # Inputs may intentionally contain NaN/Infinity so they can fail closed.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=True).encode("utf-8")


def is_finite_numeric(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not isinstance(value, float) or math.isfinite(value)


def stable_mean(values: list[float]) -> float:
    scale = max((abs(value) for value in values), default=0.0)
    if scale == 0:
        return 0.0
    return scale * (math.fsum(value / scale for value in values) / len(values))


def stable_median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return ordered[middle - 1] / 2 + ordered[middle] / 2


def classify_market_score(value: Any) -> tuple[str | None, str | None]:
    """Classify one persisted decision-time score; invalid input is never imputed."""
    if value is None:
        return None, "MISSING_SCORE"
    if not is_finite_numeric(value) or value < 0 or value > 100:
        return None, "INVALID_SCORE"
    if value < 40:
        return "LOW", None
    if value < 60:
        return "MID", None
    return "HIGH", None


def decision_regime(decision: dict[str, Any]) -> tuple[str | None, str | None]:
    output = decision.get("decision_output") if isinstance(decision.get("decision_output"), dict) else {}
    # This is deliberately the only score input. Runtime/current fields are ignored.
    return classify_market_score(output.get("marketScore"))


def canonical_status(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "INVALID"
    normalized = value.strip().upper()
    return normalized if normalized in CANONICAL_STATUSES else "INVALID"


def read_only_fingerprints(db_path: Path) -> dict[str, str | None]:
    files = (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm"))
    return {path.name if path == db_path else path.name: sha256_file(path) if path.exists() else None for path in files}


def readonly_inventory(db_path: Path = DB_PATH) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    db_path = db_path.resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"authoritative ledger does not exist: {db_path}")
    before = read_only_fingerprints(db_path)
    connection = sqlite3.connect(db_path.as_uri() + "?mode=ro&immutable=1", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"decision_ledger", "decision_outcome"}.issubset(tables):
            raise RuntimeError("authoritative P2-01/P2-02 tables are missing")
        schemas = {
            table: [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            for table in ("decision_ledger", "decision_outcome")
        }
        required_decision = {"decision_id", "decision_time", "market_as_of", "instrument", "decision_output_json"}
        required_outcome = {"decision_id", "evaluation_horizon", "evaluation_time", "status", "market_observations_json"}
        if not required_decision.issubset(schemas["decision_ledger"]) or not required_outcome.issubset(schemas["decision_outcome"]):
            raise RuntimeError("authoritative ledger schema does not satisfy the frozen P2-05 read contract")
        decisions = [dict(row) for row in connection.execute(
            "SELECT decision_id,decision_time,market_as_of,instrument,decision_output_json FROM decision_ledger"
        )]
        raw_outcomes = [dict(row) for row in connection.execute(
            "SELECT decision_id,evaluation_horizon,evaluation_time,status,market_observations_json FROM decision_outcome"
        )]
        counts = {
            "decisionCount": int(connection.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]),
            "outcomeCount": int(connection.execute("SELECT COUNT(*) FROM decision_outcome").fetchone()[0]),
        }
        application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    finally:
        connection.close()

    for decision in decisions:
        decision["decision_output"] = parse_object(decision.pop("decision_output_json"))
    outcomes = []
    for raw in raw_outcomes:
        stored = parse_object(raw.pop("market_observations_json"))
        metadata = stored.get("metadata")
        raw["outcome_metadata"] = metadata if isinstance(metadata, dict) else {}
        outcomes.append(raw)
    decisions.sort(key=lambda row: (str(row.get("decision_time") or ""), str(row.get("decision_id") or ""), stable_sort_key(row)))
    outcomes.sort(key=lambda row: (str(row.get("evaluation_time") or ""), str(row.get("decision_id") or ""), str(row.get("evaluation_horizon") or ""), stable_sort_key(row)))
    after = read_only_fingerprints(db_path)
    if before != after:
        raise RuntimeError("authoritative database or SQLite sidecar changed during read-only inspection")
    market_dates = []
    invalid_market_dates = 0
    for row in decisions:
        raw_date = row.get("market_as_of")
        try:
            market_dates.append(date.fromisoformat(str(raw_date)))
        except (TypeError, ValueError):
            if raw_date not in (None, ""):
                invalid_market_dates += 1
    inventory = {
        "databasePath": str(db_path),
        "databaseSha256": before[db_path.name],
        "sidecarFingerprintsBefore": before,
        "sidecarFingerprintsAfter": after,
        "databaseAndSidecarsUnchangedDuringRead": before == after,
        "sqliteApplicationId": application_id,
        "schemaColumns": schemas,
        **counts,
        "eligibleEvaluatedLongShortCount": None,
        "latestMarketDate": max(market_dates).isoformat() if market_dates else None,
        "invalidMarketDateCount": invalid_market_dates,
    }
    return inventory, decisions, outcomes


def outcome_metadata_mismatch(outcome: dict[str, Any], decision_id: str, horizon: str) -> list[str]:
    metadata = outcome.get("outcome_metadata") if isinstance(outcome.get("outcome_metadata"), dict) else {}
    reasons = []
    if metadata.get("decisionId") is not None and str(metadata["decisionId"]) != decision_id:
        reasons.append("OUTCOME_DECISION_ID_METADATA_MISMATCH")
    if metadata.get("horizon") is not None and str(metadata["horizon"]).strip().upper() != horizon:
        reasons.append("OUTCOME_HORIZON_METADATA_MISMATCH")
    status_value = canonical_status(outcome.get("status"))
    metadata_status = metadata.get("outcomeStatus")
    if metadata_status is not None and canonical_status(metadata_status) != status_value:
        reasons.append("OUTCOME_STATUS_METADATA_CONFLICT")
    basis = str(metadata.get("evaluationBasis") or "UNKNOWN").strip().upper()
    allowed = STATUS_BASIS_MAP.get(status_value, set())
    if basis not in allowed:
        reasons.append("OUTCOME_BASIS_CONFLICT")
    return reasons


def analyze(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]], inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    inventory = dict(inventory or {})
    decision_id_counts = Counter(str(row.get("decision_id") or "") for row in decisions)
    duplicate_decision_ids = {key for key, count in decision_id_counts.items() if key and count > 1}
    outcome_keys = [
        (str(row.get("decision_id") or ""), str(row.get("evaluation_horizon") or "").strip().upper())
        for row in outcomes
    ]
    duplicate_outcome_keys = {key for key, count in Counter(outcome_keys).items() if key[0] and count > 1}
    decisions_by_id: dict[str, dict[str, Any]] = {}
    for row in decisions:
        decision_id = str(row.get("decision_id") or "")
        if decision_id and decision_id not in duplicate_decision_ids:
            decisions_by_id[decision_id] = row

    score_audit: dict[str, tuple[str | None, str | None]] = {}
    coverage = Counter({label: 0 for label in REGIME_LABELS})
    missing_score_count = 0
    invalid_score_count = 0
    probability_flags = []
    decision_state_counts = Counter()
    decision_direction_counts = Counter()
    decision_eligibility_counts = Counter()
    for row in decisions:
        decision_id = str(row.get("decision_id") or "")
        regime, invalid_reason = decision_regime(row)
        score_audit[decision_id] = (regime, invalid_reason)
        if regime:
            coverage[regime] += 1
        elif invalid_reason == "MISSING_SCORE":
            missing_score_count += 1
        else:
            invalid_score_count += 1
        output = row.get("decision_output") if isinstance(row.get("decision_output"), dict) else {}
        probability_flags.append(output.get("probabilityLabelAllowed"))
        decision_state_counts[str(output.get("decisionState") or "UNKNOWN").strip().upper()] += 1
        decision_direction_counts[str(output.get("executionDirection") or "UNAVAILABLE").strip().upper()] += 1
        if "decisionEligible" not in output:
            decision_eligibility_counts["MISSING"] += 1
        elif output.get("decisionEligible") is True:
            decision_eligibility_counts["TRUE"] += 1
        elif output.get("decisionEligible") is False:
            decision_eligibility_counts["FALSE"] += 1
        elif output.get("decisionEligible") is None:
            decision_eligibility_counts["UNKNOWN"] += 1
        else:
            decision_eligibility_counts["INVALID"] += 1

    join_rows: list[dict[str, Any]] = []
    eligibility_rows: list[dict[str, Any]] = []
    metric_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    integrity_counts = Counter()
    status_counts = Counter()
    eligible_count = 0

    for outcome in outcomes:
        decision_id = str(outcome.get("decision_id") or "")
        horizon = str(outcome.get("evaluation_horizon") or "").strip().upper()
        key = (decision_id, horizon)
        decision = decisions_by_id.get(decision_id)
        status = canonical_status(outcome.get("status"))
        status_counts[status] += 1
        metadata = outcome.get("outcome_metadata") if isinstance(outcome.get("outcome_metadata"), dict) else {}
        basis = str(metadata.get("evaluationBasis") or "UNKNOWN").strip().upper()
        regime, score_error = score_audit.get(decision_id, (None, "MISSING_SCORE"))
        reasons: list[str] = []

        is_orphan = not decision_id or decision_id not in decision_id_counts
        if is_orphan:
            reasons.append("OUTCOME_WITHOUT_UNAMBIGUOUS_DECISION")
            integrity_counts["orphanOutcomeCount"] += 1
        if decision_id in duplicate_decision_ids:
            reasons.append("DUPLICATE_DECISION_ID")
            integrity_counts["duplicateDecisionIdAssociationCount"] += 1
        if key in duplicate_outcome_keys:
            reasons.append("DUPLICATE_OUTCOME_ASSOCIATION")
            integrity_counts["duplicateOutcomeAssociationCount"] += 1
        metadata_reasons = outcome_metadata_mismatch(outcome, decision_id, horizon)
        reasons.extend(metadata_reasons)
        for reason in metadata_reasons:
            if reason == "OUTCOME_DECISION_ID_METADATA_MISMATCH" or reason == "OUTCOME_HORIZON_METADATA_MISMATCH":
                integrity_counts["decisionOutcomeMetadataMismatchCount"] += 1
            elif reason == "OUTCOME_STATUS_METADATA_CONFLICT":
                integrity_counts["outcomeStatusConflictCount"] += 1
            elif reason == "OUTCOME_BASIS_CONFLICT":
                integrity_counts["outcomeBasisConflictCount"] += 1

        if decision is not None:
            output = decision.get("decision_output") if isinstance(decision.get("decision_output"), dict) else {}
            state = str(output.get("decisionState") or "UNKNOWN").strip().upper()
            direction = str(output.get("executionDirection") or "UNAVAILABLE").strip().upper()
            if state not in {"LONG", "SHORT"} or direction not in {"LONG", "SHORT"} or state != direction:
                reasons.append("DECISION_STATE_DIRECTION_MISMATCH")
                integrity_counts["decisionStateDirectionMismatchCount"] += 1
            if score_error:
                reasons.append("REGIME_INVALID")
            if output.get("decisionEligible") is not True:
                reasons.append("DECISION_NOT_EXPLICITLY_ELIGIBLE")

        if status != "EVALUATED":
            reasons.append(f"OUTCOME_NOT_EVALUATED:{status}")
        raw_return = metadata.get("decisionAlignedReturn")
        numeric_return: float | None = None
        if not is_finite_numeric(raw_return):
            reasons.append("INVALID_DECISION_ALIGNED_RETURN")
        else:
            try:
                numeric_return = float(raw_return)
            except (OverflowError, TypeError, ValueError):
                numeric_return = None
            if numeric_return is None or not math.isfinite(numeric_return):
                numeric_return = None
                reasons.append("INVALID_DECISION_ALIGNED_RETURN")

        eligible = not reasons and decision is not None and regime in REGIME_LABELS and numeric_return is not None
        if eligible:
            eligible_count += 1
            metric_values[(str(regime), horizon)].append(numeric_return)
        join_rows.append({
            "decisionId": decision_id,
            "evaluationHorizon": horizon,
            "regime": regime or "REGIME_INVALID",
            "joinStatus": "JOINED" if decision is not None and not any(r in reasons for r in (
                "DUPLICATE_DECISION_ID", "DUPLICATE_OUTCOME_ASSOCIATION", "OUTCOME_WITHOUT_UNAMBIGUOUS_DECISION",
                "OUTCOME_DECISION_ID_METADATA_MISMATCH", "OUTCOME_HORIZON_METADATA_MISMATCH",
                "OUTCOME_STATUS_METADATA_CONFLICT", "OUTCOME_BASIS_CONFLICT",
            )) else "INVALID",
            "outcomeStatus": status,
            "evaluationBasis": basis,
            "reasons": ";".join(dict.fromkeys(reasons)),
        })
        eligibility_rows.append({
            "decisionId": decision_id,
            "evaluationHorizon": horizon,
            "regime": regime or "REGIME_INVALID",
            "eligible": "true" if eligible else "false",
            "reasons": ";".join(dict.fromkeys(reasons)),
        })

    performance_rows = []
    for regime in REGIME_LABELS:
        for (group_regime, horizon), values in sorted(metric_values.items()):
            if regime != group_regime or not values:
                continue
            positive = sum(value > 0 for value in values)
            negative = sum(value < 0 for value in values)
            flat = sum(value == 0 for value in values)
            performance_rows.append({
                "regime": regime,
                "evaluationHorizon": horizon,
                "contract": CONTRACT_NAME,
                "n": len(values),
                "evaluatedCount": len(values),
                "positiveCount": positive,
                "negativeCount": negative,
                "flatCount": flat,
                "successRate": positive / (positive + negative) if positive + negative else None,
                "meanDecisionAlignedReturn": stable_mean(values),
                "medianDecisionAlignedReturn": stable_median(values),
                "interpretation": "DESCRIPTIVE REGIME PERFORMANCE",
            })

    inventory["eligibleEvaluatedLongShortCount"] = eligible_count
    probability_status = (
        "PASS" if probability_flags and all(value is False for value in probability_flags)
        else "FAIL" if any(value is True for value in probability_flags)
        else "UNVERIFIED"
    )
    engineering_blockers = []
    if probability_status != "PASS":
        engineering_blockers.append("PROBABILITY_LABEL_ALLOWED_NOT_EXPLICITLY_FALSE")
    coverage_rows = [
        {"regime": label, "decisionCount": len(decisions), "count": int(coverage[label]),
         "missingMarketScoreCount": missing_score_count, "invalidMarketScoreCount": invalid_score_count,
         "semantics": "DECISION REGIME COVERAGE ONLY"}
        for label in REGIME_LABELS
    ]
    coverage_rows.append({
        "regime": "REGIME_INVALID", "decisionCount": len(decisions),
        "count": missing_score_count + invalid_score_count,
        "missingMarketScoreCount": missing_score_count, "invalidMarketScoreCount": invalid_score_count,
        "semantics": "MISSING/INVALID PERSISTED MARKET SCORE; EXCLUDED FROM PERFORMANCE",
    })
    no_evidence = eligible_count == 0
    summary = {
        "node": "P2-05 — REGIME PERFORMANCE",
        "engineeringStatus": "ENGINEERING_READY" if not engineering_blockers else "ACTIVE / BLOCKED",
        "engineeringBlockers": engineering_blockers,
        "contract": {"name": CONTRACT_NAME, "version": "V1", "sha256": sha256_file(CONTRACT_PATH)},
        "database": inventory,
        "regimeCoverage": {
            "decisionCount": len(decisions), "LOW": int(coverage["LOW"]), "MID": int(coverage["MID"]),
            "HIGH": int(coverage["HIGH"]), "REGIME_INVALID": missing_score_count + invalid_score_count,
            "missingMarketScoreCount": missing_score_count, "invalidMarketScoreCount": invalid_score_count,
            "semantics": "DECISION COVERAGE; NOT REALIZED PERFORMANCE COVERAGE",
        },
        "decisionStateCounts": dict(sorted(decision_state_counts.items())),
        "decisionDirectionCounts": dict(sorted(decision_direction_counts.items())),
        "decisionEligibilityCounts": {key: int(decision_eligibility_counts[key])
                                       for key in ("TRUE", "FALSE", "UNKNOWN", "MISSING", "INVALID")},
        "pointInTimeIntegrity": {
            "status": "PASS",
            "source": "immutable decision_ledger.decision_output_json.marketScore only",
            "liveOrRuntimeScoreRead": False,
            "historicalScoreRecomputation": False,
            "futureOutcomeOrReturnUsedForClassification": False,
            "ledgerBackfill": False,
        },
        "joinIntegrity": {
            "status": "PASS — INVALID/AMBIGUOUS RELATIONSHIPS FAIL CLOSED AND ARE EXCLUDED",
            "joinedOutcomeCount": sum(row["joinStatus"] == "JOINED" for row in join_rows),
            "orphanOutcomeCount": int(integrity_counts["orphanOutcomeCount"]),
            "duplicateDecisionIdAssociationCount": int(integrity_counts["duplicateDecisionIdAssociationCount"]),
            "duplicateOutcomeAssociationCount": int(integrity_counts["duplicateOutcomeAssociationCount"]),
            "decisionOutcomeMetadataMismatchCount": int(integrity_counts["decisionOutcomeMetadataMismatchCount"]),
            "outcomeStatusConflictCount": int(integrity_counts["outcomeStatusConflictCount"]),
            "outcomeBasisConflictCount": int(integrity_counts["outcomeBasisConflictCount"]),
            "decisionStateDirectionMismatchCount": int(integrity_counts["decisionStateDirectionMismatchCount"]),
        },
        "outcomeStatusCounts": {status: int(status_counts[status]) for status in CANONICAL_STATUSES},
        "eligibleEvaluatedLongShortCount": eligible_count,
        "probabilityLabelAllowed": {"status": probability_status, "allPersistedValuesFalse": probability_status == "PASS"},
        "realizedRegimePerformance": {
            "status": "NOT AVAILABLE — NO ELIGIBLE EVALUATED OUTCOMES" if no_evidence else "DESCRIPTIVE REGIME PERFORMANCE",
            "artifactStatus": "NOT_WRITTEN_NO_ELIGIBLE_EVALUATED_OUTCOMES" if no_evidence else "AVAILABLE",
            "rows": len(performance_rows),
            "minimumSampleGate": "NONE — DESCRIPTIVE ONLY",
        },
        "performanceRows": performance_rows,
        "databaseReadOnly": True,
        "databaseUnchangedDuringRead": inventory.get("databaseAndSidecarsUnchangedDuringRead") is True,
    }
    return {"summary": summary, "coverageRows": coverage_rows, "joinRows": join_rows,
            "eligibilityRows": eligibility_rows, "performanceRows": performance_rows}


def csv_bytes(filename: str, rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS[filename], lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def build_artifacts(db_path: Path = DB_PATH) -> dict[str, bytes]:
    inventory, decisions, outcomes = readonly_inventory(db_path)
    result = analyze(decisions, outcomes, inventory)
    artifacts = {
        "summary.json": canonical_bytes(result["summary"]) + b"\n",
        "regime_coverage.csv": csv_bytes("regime_coverage.csv", result["coverageRows"]),
        "decision_outcome_join_audit.csv": csv_bytes("decision_outcome_join_audit.csv", result["joinRows"]),
        "eligibility_audit.csv": csv_bytes("eligibility_audit.csv", result["eligibilityRows"]),
    }
    if result["performanceRows"]:
        artifacts["regime_performance.csv"] = csv_bytes("regime_performance.csv", result["performanceRows"])
    return artifacts


def write_artifacts(artifacts: dict[str, bytes], output_dir: Path = OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(artifacts.items()):
        (output_dir / name).write_bytes(content)


def build_closure_manifest() -> dict[str, Any]:
    summary_path = OUTPUT_DIR / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    db_path = DB_PATH.resolve()
    current_db_hash = sha256_file(db_path)
    recorded_db_hash = summary["database"]["databaseSha256"]
    if current_db_hash != recorded_db_hash:
        raise RuntimeError("authoritative database hash drifted since the P2-05 analysis")
    return {
        "manifestVersion": "P2_05_CLOSURE_MANIFEST_V1",
        "node": "P2-05 — REGIME PERFORMANCE",
        "regimeContract": CONTRACT_NAME,
        "files": {
            "contract": {"path": "docs/P2_05_REGIME_PERFORMANCE_CONTRACT.md", "sha256": sha256_file(CONTRACT_PATH)},
            "analyzer": {"path": "scripts/p205_regime_performance.py", "sha256": sha256_file(Path(__file__))},
            "regression": {"path": "regression/test_p205_regime_performance.py", "sha256": sha256_file(ROOT / "regression" / "test_p205_regime_performance.py")},
            "closure": {"path": "docs/P2_05_FORMAL_CLOSURE.md", "sha256": sha256_file(CLOSURE_PATH)},
            "canonicalStatus": {"path": "docs/INVESTMENT_DECISION_EXECUTION_STATUS.md", "sha256": sha256_file(STATUS_PATH)},
            "p204ClosureReference": {"path": "docs/P2_04_FORMAL_CLOSURE.md", "sha256": sha256_file(P204_CLOSURE_PATH)},
        },
        "authoritativeDatabase": {
            "path": "data/p203-prospective-ledger.sqlite3",
            "sha256": current_db_hash,
            "decisionCount": summary["database"]["decisionCount"],
            "outcomeCount": summary["database"]["outcomeCount"],
        },
    }


def write_closure_manifest_twice() -> dict[str, str]:
    first = canonical_bytes(build_closure_manifest()) + b"\n"
    first_hash = sha256_bytes(first)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_bytes(first)
    second = canonical_bytes(build_closure_manifest()) + b"\n"
    second_hash = sha256_bytes(second)
    if first != second:
        raise RuntimeError("two P2-05 closure manifest generations differ")
    MANIFEST_PATH.write_bytes(second)
    if sha256_file(MANIFEST_PATH) != first_hash:
        raise RuntimeError("written P2-05 closure manifest hash mismatch")
    return {"firstSha256": first_hash, "secondSha256": second_hash, "identical": first_hash == second_hash}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--write-closure-manifest", action="store_true")
    args = parser.parse_args()
    if args.write_closure_manifest:
        result = write_closure_manifest_twice()
        print(json.dumps(result | {"manifestPath": str(MANIFEST_PATH)}, ensure_ascii=False, indent=2))
        return 0 if result["identical"] else 1
    first = build_artifacts(args.db)
    second = build_artifacts(args.db)
    first_hashes = {name: sha256_bytes(value) for name, value in sorted(first.items())}
    second_hashes = {name: sha256_bytes(value) for name, value in sorted(second.items())}
    fingerprint = sha256_bytes(canonical_bytes(first_hashes))
    if first_hashes != second_hashes:
        raise RuntimeError("two read-only P2-05 analyses produced different artifacts")
    artifacts = dict(first)
    artifacts["determinism_report.json"] = canonical_bytes({
        "deterministic": True, "firstArtifactHashes": first_hashes,
        "secondArtifactHashes": second_hashes, "deterministicFingerprint": fingerprint,
    }) + b"\n"
    write_artifacts(artifacts, args.output)
    summary = json.loads(artifacts["summary.json"])
    print(json.dumps({
        "engineeringStatus": summary["engineeringStatus"],
        "database": summary["database"],
        "regimeCoverage": summary["regimeCoverage"],
        "eligibleEvaluatedLongShortCount": summary["eligibleEvaluatedLongShortCount"],
        "realizedRegimePerformance": summary["realizedRegimePerformance"],
        "deterministicFingerprint": fingerprint,
        "outputDirectory": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0 if summary["engineeringStatus"] == "ENGINEERING_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
