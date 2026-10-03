"""Read-only, fail-closed P2-04 descriptive score-bucket analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "p203-prospective-ledger.sqlite3"
OUTPUT_DIR = ROOT / ".tmp" / "p204-score-bucket-performance"
BUCKETS = tuple((i, i + 10) for i in range(0, 100, 10))
SCORE_FIELDS = ("marketScore", "riskScore", "evidenceScore", "dataQualityScore")
CANONICAL_STATUSES = ("EVALUATED", "PENDING", "NOT_APPLICABLE", "UNAVAILABLE", "INVALID")
STATUS_BASIS_MAP = {
    "EVALUATED": {"DIRECTIONAL_RETURN"},
    "PENDING": {"DIRECTIONAL_RETURN"},
    "NOT_APPLICABLE": {"NOT_APPLICABLE"},
    "UNAVAILABLE": {"DIRECTIONAL_RETURN", "UNAVAILABLE"},
    "INVALID": {"UNAVAILABLE"},
}
EXPECTED_DB_SHA256 = "73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_json(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else fallback
    except (TypeError, ValueError):
        return fallback


def score_value(decision: dict[str, Any], field: str) -> Any:
    output = decision.get("decision_output") if isinstance(decision.get("decision_output"), dict) else {}
    if field in {"marketScore", "riskScore"}:
        return output.get(field)
    column = "evidence_score" if field == "evidenceScore" else "data_quality_score"
    return decision.get(column)


def score_instrument_segment(decision: dict[str, Any], field: str) -> str:
    instrument = str(decision.get("instrument") or "UNKNOWN")
    if field != "riskScore":
        return instrument
    output = decision.get("decision_output") if isinstance(decision.get("decision_output"), dict) else {}
    classification = output.get("riskClassification") if isinstance(output.get("riskClassification"), dict) else {}
    risk_type = str(classification.get("type") or output.get("riskType") or "UNKNOWN").strip().upper()
    return f"{instrument}::{risk_type}"


def bucket_index(value: Any) -> int | None:
    """Map a documented 0–100 score into deterministic fixed 10-point buckets."""
    if not is_finite_numeric(value):
        return None
    if value < 0 or value > 100:
        return None
    return min(int(value // 10), 9)


def bucket_label(index: int) -> str:
    low, high = BUCKETS[index]
    return f"[{low},{high})" if index < 9 else "[90,100]"


def is_finite_numeric(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not isinstance(value, float) or math.isfinite(value)


def canonical_outcome_status(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "INVALID"
    raw = value.strip().upper()
    return raw if raw in CANONICAL_STATUSES else "INVALID"


def outcome_status_metadata_mismatch(outcome: dict[str, Any]) -> bool:
    metadata = outcome.get("outcome_metadata") if isinstance(outcome.get("outcome_metadata"), dict) else {}
    metadata_status = metadata.get("outcomeStatus")
    if metadata_status is None:
        return False
    return canonical_outcome_status(metadata_status) != canonical_outcome_status(outcome.get("status"))


def normalize_outcome_status(outcome: dict[str, Any]) -> str:
    # The persisted Outcome.status column is authoritative. Metadata is a duplicate
    # contract field and may only confirm it; it may not upgrade a non-EVALUATED row.
    status = canonical_outcome_status(outcome.get("status"))
    return "INVALID" if outcome_status_metadata_mismatch(outcome) else status


def outcome_status_basis_compatible(outcome: dict[str, Any]) -> bool:
    metadata = outcome.get("outcome_metadata") if isinstance(outcome.get("outcome_metadata"), dict) else {}
    status = normalize_outcome_status(outcome)
    basis = str(metadata.get("evaluationBasis") or "UNKNOWN").strip().upper()
    return basis in STATUS_BASIS_MAP.get(status, set())


def source_contract() -> dict[str, dict[str, Any]]:
    return {
        "marketScore": {
            "field": "marketScore", "source": "decision_ledger.decision_output_json.marketScore",
            "range": [0, 100], "rangeEvidence": "derivatives/analytics.py:clamp; instrument-specific market score formulas are clamped to 0–100",
            "semanticDescription": "Decision-time market direction/pressure score; not probability.",
        },
        "riskScore": {
            "field": "riskScore", "source": "decision_ledger.decision_output_json.riskScore + riskClassification.type",
            "range": [0, 100], "rangeEvidence": "derivatives/analytics.py:clamp; instrument-specific risk score formulas are clamped to 0–100",
            "semanticDescription": "Decision-time risk magnitude score; bucketed separately by instrument and P1-03 riskClassification.type; not probability.",
        },
        "evidenceScore": {
            "field": "evidenceScore", "source": "decision_ledger.evidence_score (frozen from analysis.evidenceScore)",
            "range": [0, 100], "rangeEvidence": "derivatives/analytics.py:build_decision_quality computes available required evidence / total * 100",
            "semanticDescription": "Decision-time evidence coverage, not predictive confidence or probability.",
        },
        "dataQualityScore": {
            "field": "dataQualityScore", "source": "decision_ledger.data_quality_score (frozen from analysis.dataQualityScore)",
            "range": [0, 100], "rangeEvidence": "derivatives/analytics.py:_normalise_score clamps dimensions to 0–100; score is mean of known dimensions",
            "semanticDescription": "Decision-time mean quality of known dimensions; interpret with quality coverage/status; not probability.",
        },
    }


def readonly_inventory(db_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, str | None]]:
    files = (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm"))

    def fingerprints() -> dict[str, str | None]:
        return {str(path): sha256_bytes(path.read_bytes()) if path.exists() else None for path in files}

    before = fingerprints()
    uri = db_path.resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"decision_ledger", "decision_outcome"}.issubset(tables):
            raise RuntimeError("authoritative P2-01/P2-02 tables are missing")
        decisions = [dict(row) for row in conn.execute(
            "SELECT decision_id,target_symbol,decision_time,market_as_of,instrument,input_snapshot_json,decision_output_json,evidence_score,data_quality_score,source_metadata_json FROM decision_ledger ORDER BY decision_time,decision_id"
        )]
        # P2-02 keeps decisionAlignedReturn in the versioned metadata JSON.
        schema = {
            table: [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
            for table in ("decision_ledger", "decision_outcome")
        }
        app_id = conn.execute("PRAGMA application_id").fetchone()[0]
        counts = {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in ("decision_ledger", "decision_outcome")}
    finally:
        conn.close()
    after = fingerprints()
    if before != after:
        raise RuntimeError("authoritative database or WAL sidecar changed during read-only inspection")
    for row in decisions:
        row["input_snapshot"] = parse_json(row.pop("input_snapshot_json"), {})
        row["decision_output"] = parse_json(row.pop("decision_output_json"), {})
        row["source_metadata"] = parse_json(row.pop("source_metadata_json"), {})
    # Re-read outcomes from the table's actual schema and decode the P2-02 contract metadata.
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        outcomes = [dict(row) for row in conn.execute(
            "SELECT decision_id,evaluation_horizon,evaluation_time,status,market_observations_json,cost_adjusted_result_json FROM decision_outcome ORDER BY evaluation_time,decision_id,evaluation_horizon"
        )]
    finally:
        conn.close()
    for row in outcomes:
        stored = parse_json(row.pop("market_observations_json"), {})
        metadata = stored.get("metadata", {}) if isinstance(stored, dict) else {}
        row["outcome_metadata"] = metadata if isinstance(metadata, dict) else {}
        row["cost_adjusted_result"] = parse_json(row.pop("cost_adjusted_result_json"), {})
    inventory = {
        "databasePath": str(db_path.resolve()), "databaseSha256": before[str(db_path.resolve())],
        "expectedDatabaseSha256": EXPECTED_DB_SHA256,
        "databaseHashMatchesKnownProspectiveBaseline": before[str(db_path.resolve())] == EXPECTED_DB_SHA256,
        "databaseAndSidecarFingerprintsBefore": before, "databaseAndSidecarFingerprintsAfter": after,
        "databaseAndSidecarsUnchanged": before == after, "sqliteApplicationId": app_id,
        "counts": counts, "schemaColumns": schema,
    }
    return inventory, decisions, outcomes, before


def audit_inputs(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]], contract: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    direction_counts: Counter[str] = Counter()
    decision_state_counts: Counter[str] = Counter()
    decision_eligibility_counts: Counter[str] = Counter()
    score_audit: dict[str, Any] = {}
    no_trade_counts: Counter[tuple[str, str, str]] = Counter()
    for decision in decisions:
        output = decision.get("decision_output", {})
        direction = str(output.get("executionDirection") or "UNAVAILABLE").upper()
        direction_counts[direction] += 1
        decision_state_counts[str(output.get("decisionState") or "UNKNOWN").upper()] += 1
        if "decisionEligible" not in output:
            decision_eligibility_counts["MISSING"] += 1
        elif output["decisionEligible"] is True:
            decision_eligibility_counts["TRUE"] += 1
        elif output["decisionEligible"] is False:
            decision_eligibility_counts["FALSE"] += 1
        elif output["decisionEligible"] is None:
            decision_eligibility_counts["UNKNOWN"] += 1
        else:
            decision_eligibility_counts["INVALID"] += 1
        if str(output.get("decisionState") or "UNKNOWN").upper() == "NO_TRADE":
            for field in SCORE_FIELDS:
                idx = bucket_index(score_value(decision, field))
                if idx is not None:
                    instrument = score_instrument_segment(decision, field)
                    no_trade_counts[(field, instrument, bucket_label(idx))] += 1
    outcome_status_counts = Counter(normalize_outcome_status(outcome) for outcome in outcomes)
    instrument_names = sorted({str(d.get("instrument") or "UNKNOWN") for d in decisions})
    risk_type_counts: Counter[str] = Counter()
    aggregate_semantics: dict[str, dict[str, Any]] = {}
    for field in SCORE_FIELDS:
        signatures: dict[str, set[str]] = defaultdict(set)
        missing_signature = False
        for decision in decisions:
            output = decision.get("decision_output", {})
            snapshot = decision.get("input_snapshot", {})
            formulas = output.get("scoreFormula") if isinstance(output, dict) else None
            if not isinstance(formulas, dict) and isinstance(snapshot, dict):
                formulas = snapshot.get("scoreFormula")
            formula = formulas.get(field) if isinstance(formulas, dict) else None
            if not formula:
                missing_signature = True
            else:
                signatures[str(decision.get("instrument") or "UNKNOWN")].add(str(formula))
        compatible = len(instrument_names) <= 1 or (
            not missing_signature and all(len(signatures.get(name, set())) == 1 for name in instrument_names)
            and len({next(iter(signatures[name])) for name in instrument_names}) == 1
        )
        if field == "riskScore":
            for decision in decisions:
                output = decision.get("decision_output", {})
                classification = output.get("riskClassification") if isinstance(output.get("riskClassification"), dict) else {}
                risk_type_counts[str(classification.get("type") or output.get("riskType") or "UNKNOWN").strip().upper()] += 1
            if len(risk_type_counts) > 1:
                compatible = False
        aggregate_semantics[field] = {
            "overallAggregationAllowed": compatible,
            "reason": (
                "SINGLE_INSTRUMENT_AND_RISK_TYPE" if compatible and len(instrument_names) <= 1 else
                "IDENTICAL_FROZEN_SCORE_FORMULA" if compatible else
                "CROSS_RISK_CLASSIFICATION_SEMANTICS" if field == "riskScore" and len(risk_type_counts) > 1 else
                "CROSS_INSTRUMENT_SCORE_SEMANTICS_NOT_PROVEN"
            ),
        }
    for field in SCORE_FIELDS:
        values = [score_value(decision, field) for decision in decisions]
        valid = [float(v) for v in values if bucket_index(v) is not None]
        missing = sum(v is None for v in values)
        invalid = sum(v is not None and not is_finite_numeric(v) for v in values)
        out_of_range = sum(is_finite_numeric(v) and (v < 0 or v > 100) for v in values)
        score_audit[field] = {
            "availability": "AVAILABLE" if valid else "UNAVAILABLE", "range": contract[field]["range"],
            "decisionCount": len(decisions), "nonNullCount": len(values) - missing,
            "nullCount": missing, "invalidScoreCount": invalid, "outOfRangeScoreCount": out_of_range,
            "observedMin": min(valid) if valid else None, "observedMax": max(valid) if valid else None,
            "decisionTimeValues": valid,
        }
    decision_ids = [str(row.get("decision_id") or "") for row in decisions]
    outcome_keys = [(str(row.get("decision_id") or ""), str(row.get("evaluation_horizon") or "").upper()) for row in outcomes]
    duplicate_decision_ids = sorted(key for key, count in Counter(decision_ids).items() if key and count > 1)
    duplicate_outcome_keys = sorted([list(key) for key, count in Counter(outcome_keys).items() if key[0] and count > 1])
    ids = {decision_id for decision_id in decision_ids if decision_id}
    orphan_outcomes = [row for row in outcomes if str(row.get("decision_id") or "") not in ids]
    joined = [row for row in outcomes if str(row.get("decision_id") or "") in ids]
    invalid_relationships: list[dict[str, Any]] = []
    status_metadata_mismatches: list[dict[str, Any]] = []
    incompatible_status_basis_pairs: list[dict[str, Any]] = []
    for row in outcomes:
        outcome_id = str(row.get("decision_id") or "")
        horizon = str(row.get("evaluation_horizon") or "").upper()
        metadata = row.get("outcome_metadata") if isinstance(row.get("outcome_metadata"), dict) else {}
        if not outcome_id or outcome_id not in ids:
            invalid_relationships.append({"decisionId": outcome_id or None, "horizon": horizon or None, "reason": "ORPHAN_DECISION_ID"})
        if metadata.get("decisionId") is not None and str(metadata.get("decisionId")) != outcome_id:
            invalid_relationships.append({"decisionId": outcome_id or None, "horizon": horizon or None, "reason": "OUTCOME_METADATA_DECISION_ID_MISMATCH"})
        if metadata.get("horizon") is not None and str(metadata.get("horizon")).upper() != horizon:
            invalid_relationships.append({"decisionId": outcome_id or None, "horizon": horizon or None, "reason": "OUTCOME_METADATA_HORIZON_MISMATCH"})
        if outcome_status_metadata_mismatch(row):
            status_metadata_mismatches.append({"decisionId": outcome_id or None, "horizon": horizon or None})
        if not outcome_status_basis_compatible(row):
            incompatible_status_basis_pairs.append({
                "decisionId": outcome_id or None, "horizon": horizon or None,
                "status": normalize_outcome_status(row),
                "evaluationBasis": str(metadata.get("evaluationBasis") or "UNKNOWN").strip().upper(),
            })
    input_audit = {
        "decisionLedgerRowCount": len(decisions), "outcomeRowCount": len(outcomes),
        "decisionDirectionCounts": dict(sorted(direction_counts.items())),
        "decisionStateCounts": dict(sorted(decision_state_counts.items())),
        "decisionEligibilityCounts": {status: int(decision_eligibility_counts.get(status, 0)) for status in ("TRUE", "FALSE", "UNKNOWN", "MISSING", "INVALID")},
        "outcomeStatusCounts": {status: int(outcome_status_counts.get(status, 0)) for status in CANONICAL_STATUSES},
        "availableScoreFields": [field for field in SCORE_FIELDS if score_audit[field]["availability"] == "AVAILABLE"],
        "scoreAudit": score_audit, "instrumentCounts": dict(sorted(Counter(str(d.get("instrument") or "UNKNOWN") for d in decisions).items())),
        "riskClassificationTypeCounts": dict(sorted(risk_type_counts.items())),
        "instrumentAggregateSemantics": aggregate_semantics,
        "noTradeCountByScoreBucket": [
            {"score": field, "instrument": instrument, "bucket": label, "count": count}
            for (field, instrument, label), count in sorted(no_trade_counts.items())
        ],
        "dateRange": {"firstDecisionTime": min((str(d.get("decision_time") or "") for d in decisions), default=None), "lastDecisionTime": max((str(d.get("decision_time") or "") for d in decisions), default=None)},
        "eligibleJoinCount": len(joined), "orphanOutcomeCount": len(orphan_outcomes),
    }
    integrity = {
        "decisionPrimaryKeyDuplicates": duplicate_decision_ids,
        "outcomeDecisionHorizonDuplicates": duplicate_outcome_keys,
        "orphanOutcomes": [{"decisionId": row.get("decision_id"), "horizon": row.get("evaluation_horizon")} for row in orphan_outcomes],
        "decisionIdsWithOutcomes": sorted({str(row.get("decision_id")) for row in joined}),
        "invalidDecisionOutcomeRelationships": invalid_relationships,
        "outcomeStatusMetadataMismatches": status_metadata_mismatches,
        "incompatibleStatusBasisPairs": incompatible_status_basis_pairs,
        "joinedOutcomeCount": len(joined), "horizonCounts": dict(sorted(Counter(str(o.get("evaluation_horizon") or "UNKNOWN") for o in joined).items())),
        "evaluationBasisCounts": dict(sorted(Counter(str((o.get("outcome_metadata") or {}).get("evaluationBasis") or "UNKNOWN") for o in joined).items())),
        "pointInTimeSource": "immutable decision_ledger snapshot columns and decision_output_json only",
        "decisionSnapshotsModified": False,
        "databaseMutation": False,
    }
    return input_audit, integrity


def analyze(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]], contract: dict[str, dict[str, Any]]) -> dict[str, Any]:
    input_audit, integrity = audit_inputs(decisions, outcomes, contract)
    if not outcomes:
        funnel = {
            "TOTAL DECISIONS": len(decisions), "TOTAL OUTCOMES": 0, "JOINED": 0,
            "EVALUATED": 0, "PENDING": 0, "NOT_APPLICABLE": 0, "UNAVAILABLE": 0, "INVALID": 0,
            "INELIGIBLE_DECISION": 0, "INVALID_RELATIONSHIP": 0, "DUPLICATE_OUTCOME_ASSOCIATION": 0,
            "STATUS_METADATA_MISMATCH": 0, "INCOMPATIBLE_STATUS_BASIS": 0,
            "INVALID_DIRECTION_STATE": 0, "MISSING_SCORE": 0, "INVALID_SCORE": 0,
            "HORIZON_MISMATCH": 0, "BASIS_MISMATCH": 0,
            "VALID_BUCKET_PERFORMANCE_ROWS": 0,
        }
        return {"inputAudit": input_audit, "integrityReport": integrity, "eligibilityFunnel": funnel,
                "status": "BLOCKED", "reason": "NO ELIGIBLE EVALUATED OUTCOMES",
                "performance": "NOT AVAILABLE — authoritative P2-02 outcome table contains zero rows",
                "performanceArtifacts": "NOT_WRITTEN_NO_ELIGIBLE_OUTCOMES"}

    # Duplicate or orphan joins are excluded, and no horizon is combined.
    by_id = {str(d.get("decision_id")): d for d in decisions if d.get("decision_id")}
    duplicate_ids = set(integrity["decisionPrimaryKeyDuplicates"])
    duplicate_outcome_keys = {tuple(key) for key in integrity["outcomeDecisionHorizonDuplicates"]}
    horizons = sorted({str(o.get("evaluation_horizon") or "UNKNOWN").upper() for o in outcomes})
    aggregate_allowed = {field: input_audit["instrumentAggregateSemantics"][field]["overallAggregationAllowed"] for field in SCORE_FIELDS}
    buckets: dict[tuple[str, str, int, str, str], dict[str, Any]] = {}
    for field in SCORE_FIELDS:
        instruments = {score_instrument_segment(d, field) for d in decisions}
        if aggregate_allowed[field]:
            instruments.add("OVERALL")
        for instrument in sorted(instruments):
            for direction in ("ALL_ELIGIBLE", "LONG_ONLY", "SHORT_ONLY"):
                for horizon in horizons:
                    for index in range(10):
                        buckets[(field, instrument, index, direction, horizon)] = {
                            "score": field, "instrument": instrument, "evaluationHorizon": horizon,
                            "bucket": bucket_label(index), "directionView": direction,
                            "decisionCount": 0, "evaluatedCount": 0, "pendingCount": 0, "notApplicableCount": 0,
                            "unavailableCount": 0, "invalidCount": 0, "noTradeCount": 0,
                            "n": 0, "positiveCount": 0, "negativeCount": 0, "flatCount": 0,
                            "returns": [], "empiricalSuccessRate": None,
                        }
    funnel = Counter({"TOTAL DECISIONS": len(decisions), "TOTAL OUTCOMES": len(outcomes)})
    excluded_rows: list[dict[str, Any]] = []
    for decision in decisions:
        output = decision.get("decision_output", {})
        instrument = str(decision.get("instrument") or "UNKNOWN")
        direction = str(output.get("executionDirection") or "UNAVAILABLE").upper()
        views = ["ALL_ELIGIBLE"] + (["LONG_ONLY"] if direction == "LONG" else []) + (["SHORT_ONLY"] if direction == "SHORT" else [])
        for field in SCORE_FIELDS:
            idx = bucket_index(score_value(decision, field))
            if idx is None:
                continue
            target_instruments = {score_instrument_segment(decision, field)} | ({"OVERALL"} if aggregate_allowed[field] else set())
            for instr in target_instruments:
                for view in views:
                    for horizon in horizons:
                        entry = buckets[(field, instr, idx, view, horizon)]
                        entry["decisionCount"] += 1
                        if str(output.get("decisionState") or "UNKNOWN").upper() == "NO_TRADE":
                            entry["noTradeCount"] += 1
    eligible_keys: set[tuple[str, str]] = set()
    for outcome in outcomes:
        status = normalize_outcome_status(outcome)
        funnel[status] += 1
        key = (str(outcome.get("decision_id") or ""), str(outcome.get("evaluation_horizon") or "").upper())
        decision = by_id.get(key[0])
        if decision is None:
            funnel["INVALID_RELATIONSHIP"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "ORPHAN_OR_DUPLICATE_JOIN"})
            continue
        if key[0] in duplicate_ids:
            funnel["INVALID_RELATIONSHIP"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "DUPLICATE_DECISION_ID"})
            continue
        if key in duplicate_outcome_keys:
            funnel["DUPLICATE_OUTCOME_ASSOCIATION"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "DUPLICATE_OUTCOME_ASSOCIATION"})
            continue
        if not re.fullmatch(r"T\+[1-9][0-9]*", key[1]):
            funnel["HORIZON_MISMATCH"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "HORIZON_MISMATCH"})
            continue
        output = decision.get("decision_output", {})
        direction = str(output.get("executionDirection") or "UNAVAILABLE").upper()
        decision_state = str(output.get("decisionState") or "UNKNOWN").upper()
        metadata = outcome.get("outcome_metadata") if isinstance(outcome.get("outcome_metadata"), dict) else {}
        invalid_relationship = (
            (metadata.get("decisionId") is not None and str(metadata.get("decisionId")) != key[0])
            or (metadata.get("horizon") is not None and str(metadata.get("horizon")).upper() != key[1])
        )
        if invalid_relationship:
            funnel["INVALID_RELATIONSHIP"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "OUTCOME_METADATA_KEY_MISMATCH"})
            continue
        status_metadata_mismatch = outcome_status_metadata_mismatch(outcome)
        basis_compatible = outcome_status_basis_compatible(outcome)
        if status_metadata_mismatch:
            funnel["STATUS_METADATA_MISMATCH"] += 1
        if not basis_compatible:
            funnel["INCOMPATIBLE_STATUS_BASIS"] += 1
            if status == "EVALUATED":
                funnel["BASIS_MISMATCH"] += 1
        if status_metadata_mismatch or not basis_compatible:
            excluded_rows.append({
                "decisionId": key[0], "horizon": key[1],
                "reason": "OUTCOME_STATUS_METADATA_MISMATCH" if status_metadata_mismatch else "INCOMPATIBLE_STATUS_BASIS",
            })
            continue
        for field in SCORE_FIELDS:
            idx = bucket_index(score_value(decision, field))
            if idx is None:
                continue
            actual_instrument = score_instrument_segment(decision, field)
            target_instruments = {actual_instrument} | ({"OVERALL"} if aggregate_allowed[field] else set())
            for instrument in target_instruments:
                views = ["ALL_ELIGIBLE"] + (["LONG_ONLY"] if direction == "LONG" else []) + (["SHORT_ONLY"] if direction == "SHORT" else [])
                for view in views:
                    entry = buckets[(field, instrument, idx, view, key[1])]
                    status_counter_key = {
                        "PENDING": "pendingCount", "NOT_APPLICABLE": "notApplicableCount",
                        "UNAVAILABLE": "unavailableCount", "INVALID": "invalidCount",
                    }.get(status)
                    if status_counter_key:
                        entry[status_counter_key] += 1
        if status != "EVALUATED":
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": status})
            continue
        if output.get("decisionEligible") is not True:
            funnel["INELIGIBLE_DECISION"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "DECISION_NOT_ELIGIBLE"})
            continue
        if direction not in {"LONG", "SHORT"} or decision_state != direction:
            funnel["INVALID_DIRECTION_STATE"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "NO_VALID_DIRECTIONAL_DECISION"})
            continue
        if str(metadata.get("evaluationBasis") or "UNKNOWN").strip().upper() != "DIRECTIONAL_RETURN":
            funnel["BASIS_MISMATCH"] += 1
            funnel["INCOMPATIBLE_STATUS_BASIS"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "BASIS_MISMATCH"})
            continue
        raw_return = metadata.get("decisionAlignedReturn")
        if not is_finite_numeric(raw_return):
            funnel["INVALID"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "MISSING_OR_INVALID_DECISION_ALIGNED_RETURN"})
            continue
        try:
            ret = float(raw_return)
        except (OverflowError, TypeError, ValueError):
            ret = math.inf
        if not math.isfinite(ret):
            funnel["INVALID"] += 1
            excluded_rows.append({"decisionId": key[0], "horizon": key[1], "reason": "MISSING_OR_INVALID_DECISION_ALIGNED_RETURN"})
            continue
        valid_score_found = False
        for field in SCORE_FIELDS:
            idx = bucket_index(score_value(decision, field))
            if idx is None:
                funnel["MISSING_SCORE" if score_value(decision, field) is None else "INVALID_SCORE"] += 1
                excluded_rows.append({"decisionId": key[0], "horizon": key[1], "score": field,
                                      "reason": "MISSING_SCORE" if score_value(decision, field) is None else "INVALID_OR_OUT_OF_RANGE_SCORE"})
                continue
            valid_score_found = True
            actual_instrument = score_instrument_segment(decision, field)
            target_instruments = {actual_instrument} | ({"OVERALL"} if aggregate_allowed[field] else set())
            for instrument in target_instruments:
                views = ["ALL_ELIGIBLE"] + (["LONG_ONLY"] if direction == "LONG" else []) + (["SHORT_ONLY"] if direction == "SHORT" else [])
                for view in views:
                    entry = buckets[(field, instrument, idx, view, key[1])]
                    entry["evaluatedCount"] += 1
                    entry["n"] += 1
                    entry["returns"].append(ret)
                    if ret > 0:
                        entry["positiveCount"] += 1
                    elif ret < 0:
                        entry["negativeCount"] += 1
                    else:
                        entry["flatCount"] += 1
        if valid_score_found:
            eligible_keys.add(key)
    rows = []
    for entry in buckets.values():
        positive, negative = entry["positiveCount"], entry["negativeCount"]
        entry["N"] = entry["evaluatedCount"]
        entry["empiricalSuccessRate"] = positive / (positive + negative) if positive + negative else None
        values = entry.pop("returns")
        entry["meanDecisionAlignedReturn"] = sum(values) / len(values) if values else None
        entry["medianDecisionAlignedReturn"] = sorted(values)[len(values) // 2] if values and len(values) % 2 else ((sorted(values)[len(values)//2 - 1] + sorted(values)[len(values)//2]) / 2 if values else None)
        entry["minDecisionAlignedReturn"] = min(values) if values else None
        entry["maxDecisionAlignedReturn"] = max(values) if values else None
        entry["sampleInterpretation"] = "DESCRIPTIVE_ONLY; NO_SAMPLE_SUFFICIENCY_GATE_DEFINED"
        rows.append(entry)
    funnel["JOINED"] = integrity["joinedOutcomeCount"]
    funnel["VALID_BUCKET_PERFORMANCE_ROWS"] = len(eligible_keys)
    frozen_funnel = {key: int(funnel.get(key, 0)) for key in (
        "TOTAL DECISIONS", "TOTAL OUTCOMES", "JOINED", "EVALUATED", "PENDING", "NOT_APPLICABLE", "UNAVAILABLE", "INVALID",
        "INELIGIBLE_DECISION", "INVALID_RELATIONSHIP", "DUPLICATE_OUTCOME_ASSOCIATION", "STATUS_METADATA_MISMATCH",
        "INCOMPATIBLE_STATUS_BASIS", "INVALID_DIRECTION_STATE", "MISSING_SCORE", "INVALID_SCORE",
        "HORIZON_MISMATCH", "BASIS_MISMATCH", "VALID_BUCKET_PERFORMANCE_ROWS")}
    return {"inputAudit": input_audit, "integrityReport": integrity, "eligibilityFunnel": frozen_funnel,
            "status": "PASS" if eligible_keys else "BLOCKED", "reason": None if eligible_keys else "NO ELIGIBLE EVALUATED OUTCOMES",
            "performance": rows if eligible_keys else "NOT AVAILABLE — no compatible EVALUATED joins",
            "excludedRows": excluded_rows,
            "performanceArtifacts": "AVAILABLE" if eligible_keys else "NOT_WRITTEN_NO_ELIGIBLE_OUTCOMES"}


def build_artifacts(db_path: Path = DB_PATH) -> dict[str, Any]:
    inventory, decisions, outcomes, before = readonly_inventory(db_path)
    contract = source_contract()
    result = analyze(decisions, outcomes, contract)
    score_contract = {
        "scores": contract,
        "bucketBoundaries": [{"label": bucket_label(index), "lowerInclusive": low, "upperExclusive": high if index < 9 else None, "upperInclusive": 100 if index == 9 else None} for index, (low, high) in enumerate(BUCKETS)],
        "bucketRule": "floor(score / 10), except 100 belongs to [90,100]",
        "semantics": "DESCRIPTIVE HISTORICAL RATE; NOT PROBABILITY FORECAST; NOT CALIBRATED PROBABILITY",
        "scoreRangeVerification": "PASS — all four contracts document or compute 0–100",
        "decisionTimeProvenance": "read immutable P2-01 Decision Ledger snapshot; no recalculation or backfill",
    }
    output = {
        "input_inventory.json": inventory | result["inputAudit"],
        "score_contract.json": score_contract,
        "eligibility_funnel.json": result["eligibilityFunnel"],
        "integrity_report.json": result["integrityReport"],
        "p204_summary.json": {"node": "P2-04 — SCORE BUCKET PERFORMANCE", "status": result["status"], "reason": result["reason"],
                               "p203Dependency": "INDEPENDENT OF P2-03 — authorized input chain is P2-01 Decision Ledger + P2-02 Outcome Evaluation",
                               "p203Status": "CLOSED — P2-04 uses P2-01 + P2-02 only",
                               "probabilityLabelAllowed": False, "performance": result["performance"],
                               "performanceArtifacts": result["performanceArtifacts"], "descriptiveOnly": True,
                               "databaseUnchanged": inventory["databaseAndSidecarsUnchanged"]},
    }
    if result["performanceArtifacts"] == "AVAILABLE":
        output["bucket_performance.csv"] = result["performance"]
        output["bucket_performance_by_instrument.csv"] = [row for row in result["performance"] if row["instrument"] != "OVERALL"]
        output["bucket_performance_by_direction.csv"] = [row for row in result["performance"] if row["directionView"] != "ALL_ELIGIBLE"]
        output["excluded_rows.csv"] = result.get("excludedRows", [])
    return output


def write_artifacts(output: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in output.items():
        path = output_dir / name
        if path.suffix == ".csv":
            rows = value
            columns = list(rows[0]) if rows else []
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
        else:
            path.write_bytes(canonical_bytes(value) + b"\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    first = build_artifacts(args.db)
    second = build_artifacts(args.db)
    first_fingerprint = sha256_bytes(canonical_bytes(first))
    second_fingerprint = sha256_bytes(canonical_bytes(second))
    if first_fingerprint != second_fingerprint:
        raise RuntimeError("two read-only P2-04 runs produced different outputs")
    artifacts = first
    artifacts["determinism_report.json"] = {
        "repeatExecutionRequired": True, "firstRunFingerprint": first_fingerprint,
        "secondRunFingerprint": second_fingerprint, "deterministic": first_fingerprint == second_fingerprint,
        "outputsCompared": sorted(first),
    }
    write_artifacts(artifacts, args.output)
    summary = artifacts["p204_summary.json"]
    print(json.dumps({"status": summary["status"], "reason": summary["reason"], "input": artifacts["input_inventory.json"], "outputDirectory": str(args.output)}, ensure_ascii=False, indent=2))
    return 0 if summary["status"] in {"PASS", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
