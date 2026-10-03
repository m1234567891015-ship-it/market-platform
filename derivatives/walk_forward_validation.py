"""Read-only P3-01 walk-forward validation for the frozen P2-03 forecast.

The authoritative entry point is deliberately pinned to the local prospective
evidence ledger. Pure evaluation helpers default to test-only evidence so
synthetic fixtures cannot be counted as authoritative observations.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from derivatives.calibration import build_oos_calibration_report
from derivatives.probability_forecast import (
    FEATURE_CONTRACT_VERSION,
    MIN_TRAINING_SAMPLES,
    MODEL_CONTRACT_VERSION,
    TARGET_CONTRACT_VERSION,
    TARGET_HORIZON,
    derive_directional_target,
    fit_probability_forecast,
    valid_oos_pair,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_DB = (REPOSITORY_ROOT / "data" / "p203-prospective-ledger.sqlite3").resolve()
CONTRACT_PATH = REPOSITORY_ROOT / "docs" / "PHASE3_MODEL_VALIDATION_CONTRACT.md"
CONTRACT_ID = "PHASE3_MODEL_VALIDATION_V1"
CONTRACT_SHA256 = "43EBCAD66CD8267C07BCA2419FBBCDECA066E6195EECF1E4AC782FD5954BBC57"
REPORT_VERSION = "P3_01_WALK_FORWARD_VALIDATION_V1"
EXPECTED_SQLITE_APPLICATION_ID = 0x50323033
AUTHORITATIVE_EVIDENCE_CLASS = "AUTHORITATIVE_PROSPECTIVE_LEDGER"
TEST_EVIDENCE_CLASS = "SYNTHETIC_TEST_ONLY"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


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


def _decision_output(decision: dict[str, Any]) -> dict[str, Any]:
    output = decision.get("decision_output")
    if not isinstance(output, dict):
        output = decision.get("decisionOutput")
    return output if isinstance(output, dict) else {}


def _decision_source_provenance(decision: dict[str, Any]) -> dict[str, Any] | None:
    metadata = decision.get("source_metadata")
    if not isinstance(metadata, dict):
        metadata = decision.get("sourceMetadata")
    if not isinstance(metadata, dict):
        return None
    provenance = metadata.get("source_provenance") or metadata.get("sourceProvenance")
    return provenance if isinstance(provenance, dict) else None


def _known_provider_provenance(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if str(value.get("status") or "").strip().upper() == "UNKNOWN":
        return False
    return bool(str(value.get("provider") or value.get("providerName") or value.get("source") or "").strip())


def _outcome_source_provenance(outcome: dict[str, Any]) -> dict[str, Any] | None:
    metadata = outcome.get("outcome_metadata")
    if not isinstance(metadata, dict):
        metadata = outcome.get("outcomeMetadata")
    if not isinstance(metadata, dict):
        return None
    provenance = metadata.get("provenance")
    if not isinstance(provenance, dict):
        return None
    source = provenance.get("outcome")
    return source if isinstance(source, dict) else None


def _outcome_rows_by_decision(outcomes: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        horizon = str(outcome.get("evaluation_horizon") or outcome.get("evaluationHorizon") or "").upper()
        decision_id = str(outcome.get("decision_id") or outcome.get("decisionId") or "")
        if horizon == TARGET_HORIZON and decision_id:
            # The canonical ledger has one outcome per Decision / horizon. Keep
            # duplicate inputs visible as invalid instead of silently choosing.
            if decision_id in result:
                result[decision_id] = {"_duplicateOutcome": True}
            else:
                result[decision_id] = outcome
    return result


def _is_candidate_decision(decision: dict[str, Any]) -> bool:
    output = _decision_output(decision)
    state = str(decision.get("decisionState") or output.get("decisionState") or "UNKNOWN").upper()
    direction = str(decision.get("executionDirection") or output.get("executionDirection") or "").upper()
    eligible = decision.get("decisionEligible", output.get("decisionEligible")) is True
    return state in {"LONG", "SHORT"} and eligible and direction == state


def _training_provenance_is_complete(
    current: dict[str, Any], training_rows: list[dict[str, Any]]
) -> bool:
    current_time = _aware_datetime(current.get("decision_time") or current.get("decisionTime"))
    current_instrument = str(current.get("instrument") or "").strip().upper()
    if current_time is None:
        return False
    for row in training_rows:
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else row
        outcome = row.get("outcome") if isinstance(row.get("outcome"), dict) else {}
        target = derive_directional_target(decision, outcome, horizon=TARGET_HORIZON)
        if not target.get("eligible"):
            continue
        training_instrument = str(decision.get("instrument") or "").strip().upper()
        if current_instrument and training_instrument != current_instrument:
            continue
        decision_time = _aware_datetime(target.get("decisionTime"))
        evaluated_at = _aware_datetime(target.get("evaluatedAt"))
        if decision_time is None or evaluated_at is None:
            continue
        if decision_time >= current_time or evaluated_at >= current_time:
            continue
        if not _known_provider_provenance(_decision_source_provenance(decision)):
            return False
        if not _known_provider_provenance(_outcome_source_provenance(outcome)):
            return False
    return True


def _eligible_training_labels(decisions: list[dict[str, Any]], outcomes: dict[str, dict[str, Any]]) -> int:
    count = 0
    for decision in decisions:
        decision_id = str(decision.get("decision_id") or decision.get("decisionId") or "")
        outcome = outcomes.get(decision_id)
        if outcome and not outcome.get("_duplicateOutcome"):
            count += int(derive_directional_target(decision, outcome, horizon=TARGET_HORIZON).get("eligible") is True)
    return count


def _set_contract_identity() -> str:
    if not CONTRACT_PATH.is_file():
        raise FileNotFoundError("frozen Phase 3 contract is missing")
    actual = _sha256_file(CONTRACT_PATH).upper()
    if actual != CONTRACT_SHA256:
        raise RuntimeError("frozen Phase 3 contract SHA-256 does not match the recorded identity")
    return actual


def build_walk_forward_report(
    decisions: Iterable[dict[str, Any]],
    outcomes: Iterable[dict[str, Any]],
    *,
    evidence_class: str = TEST_EVIDENCE_CLASS,
    input_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Build deterministic expanding-window folds without mutating input.

    The default evidence class is test-only. Only the read-only authoritative
    database entry point supplies ``AUTHORITATIVE_PROSPECTIVE_LEDGER``.
    """
    _set_contract_identity()
    normalized_decisions = [item for item in decisions if isinstance(item, dict)]
    normalized_decisions.sort(key=lambda item: (
        _aware_datetime(item.get("decision_time") or item.get("decisionTime")) or datetime.max.replace(tzinfo=timezone.utc),
        str(item.get("decision_id") or item.get("decisionId") or ""),
    ))
    outcome_values = [item for item in outcomes if isinstance(item, dict)]
    outcome_map = _outcome_rows_by_decision(outcome_values)
    training_rows = [
        {"decision": decision, "outcome": outcome_map[str(decision.get("decision_id") or decision.get("decisionId") or "")]}
        for decision in normalized_decisions
        if str(decision.get("decision_id") or decision.get("decisionId") or "") in outcome_map
        and not outcome_map[str(decision.get("decision_id") or decision.get("decisionId") or "")].get("_duplicateOutcome")
    ]

    eligible_decisions = 0
    excluded_decisions = 0
    malformed_decisions = sum(
        1 for decision in normalized_decisions
        if _aware_datetime(decision.get("decision_time") or decision.get("decisionTime")) is None
    )
    folds: list[dict[str, Any]] = []
    accepted_pairs: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    replay_mismatches = 0
    provenance_exclusions = 0
    missing_forecasts = 0
    missing_outcomes = 0
    duplicate_outcomes = sum(1 for value in outcome_map.values() if value.get("_duplicateOutcome"))

    for decision in normalized_decisions:
        if not _is_candidate_decision(decision):
            excluded_decisions += 1
            continue
        decision_time = _aware_datetime(decision.get("decision_time") or decision.get("decisionTime"))
        decision_id = str(decision.get("decision_id") or decision.get("decisionId") or "")
        if decision_time is None or not decision_id:
            excluded_decisions += 1
            continue
        eligible_decisions += 1
        generated = fit_probability_forecast(decision, training_rows, horizon=TARGET_HORIZON)
        recomputed = generated.get("probabilityForecast")
        output = _decision_output(decision)
        persisted = output.get("probabilityForecast")
        fold: dict[str, Any] = {
            "foldIndex": len(folds) + 1,
            "decisionId": decision_id,
            "decisionTime": decision.get("decision_time") or decision.get("decisionTime"),
            "trainingSampleCount": int(generated.get("trainingSampleCount", 0)),
            "trainingGateStatus": generated.get("status"),
        }
        status: str
        if not isinstance(recomputed, dict):
            status = str(generated.get("status") or "FORECAST_UNAVAILABLE")
        elif not isinstance(persisted, dict):
            missing_forecasts += 1
            status = "PERSISTED_FORECAST_MISSING"
        elif _canonical_json(recomputed) != _canonical_json(persisted):
            replay_mismatches += 1
            status = "DETERMINISTIC_REPLAY_MISMATCH"
        elif not _training_provenance_is_complete(decision, training_rows):
            provenance_exclusions += 1
            status = "TRAINING_PROVENANCE_UNVERIFIED"
        elif not _known_provider_provenance(_decision_source_provenance(decision)):
            provenance_exclusions += 1
            status = "DECISION_PROVENANCE_UNVERIFIED"
        else:
            outcome = outcome_map.get(decision_id)
            if outcome is None:
                missing_outcomes += 1
                status = "OUTCOME_NOT_YET_PRESENT"
            elif outcome.get("_duplicateOutcome"):
                status = "DUPLICATE_OUTCOME_RECORD"
            else:
                pair = valid_oos_pair(decision, outcome, horizon=TARGET_HORIZON)
                if pair is None:
                    status = "OOS_PAIR_INVALID_OR_NOT_MATURE"
                elif not _known_provider_provenance(_outcome_source_provenance(outcome)):
                    provenance_exclusions += 1
                    status = "OUTCOME_PROVENANCE_UNVERIFIED"
                else:
                    status = "VALID_PROSPECTIVE_OOS_PAIR"
                    accepted_pairs.append(pair)
                    fold["targetClass"] = int(pair["outcome"])
                    fold["prediction"] = float(pair["prediction"])
                    fold["fitCutoff"] = pair["fitCutoff"]
                    fold["evaluatedAt"] = pair["evaluatedAt"]
        fold["status"] = status
        status_counts[status] = status_counts.get(status, 0) + 1
        folds.append(fold)

    predictions = [pair["prediction"] for pair in accepted_pairs]
    labels = [pair["outcome"] for pair in accepted_pairs]
    calibration = build_oos_calibration_report(
        predictions,
        labels,
        data_split="out_of_sample",
        min_samples=MIN_TRAINING_SAMPLES,
    )
    positive_count = sum(int(label == 1) for label in labels)
    negative_count = sum(int(label == 0) for label in labels)
    authoritative = str(evidence_class).upper() == AUTHORITATIVE_EVIDENCE_CLASS
    mature = len(accepted_pairs) >= MIN_TRAINING_SAMPLES and positive_count > 0 and negative_count > 0
    if authoritative:
        maturity = "MATURE_PENDING_OWNER_ADJUDICATION" if mature else "STATISTICAL_VALIDATION_EVIDENCE_NOT_YET_MATURE"
    else:
        maturity = "SYNTHETIC_OR_NONAUTHORITATIVE_EVIDENCE_ONLY"

    record_identity = {
        "decisions": normalized_decisions,
        "outcomes": outcome_values,
    }
    report: dict[str, Any] = {
        "reportVersion": REPORT_VERSION,
        "contractId": CONTRACT_ID,
        "contractSha256": CONTRACT_SHA256,
        "evidenceClass": AUTHORITATIVE_EVIDENCE_CLASS if authoritative else TEST_EVIDENCE_CLASS,
        "validationPipelineStatus": "VALIDATION PIPELINE READY",
        "statisticalEvidenceMaturity": maturity,
        "dataSplit": "EXPANDING_PREQUENTIAL_WALK_FORWARD_OOS",
        "foldContract": {
            "unit": "ONE_ELIGIBLE_DECISION_PER_HOLDOUT_FOLD",
            "trainingWindow": "EXPANDING_ALL_ELIGIBLE_MATURED_PRIOR_LABELS",
            "minimumTrainingLabels": MIN_TRAINING_SAMPLES,
            "requiresBothTrainingClasses": True,
            "horizon": TARGET_HORIZON,
            "purgeRule": "OUTCOME_EVALUATION_TIME_STRICTLY_BEFORE_HELD_OUT_DECISION_TIME",
            "additionalCalendarEmbargoDays": 0,
            "randomShuffle": False,
        },
        "baseline": {
            "targetContractVersion": TARGET_CONTRACT_VERSION,
            "featureContractVersion": FEATURE_CONTRACT_VERSION,
            "modelContractVersion": MODEL_CONTRACT_VERSION,
            "probabilityLabelAllowed": False,
        },
        "counts": {
            "decisionRows": len(normalized_decisions),
            "eligibleCandidateDecisions": eligible_decisions,
            "excludedDecisions": excluded_decisions,
            "eligibleMaturedLabels": _eligible_training_labels(normalized_decisions, outcome_map),
            "persistedProspectiveForecasts": sum(
                isinstance(_decision_output(item).get("probabilityForecast"), dict) for item in normalized_decisions
            ),
            "folds": len(folds),
            "eligibleProspectiveOosPairs": len(accepted_pairs),
            "authoritativeEvidenceCount": len(accepted_pairs) if authoritative else 0,
            "testOnlySyntheticPairCount": 0 if authoritative else len(accepted_pairs),
            "positiveOosLabels": positive_count if authoritative else 0,
            "negativeOosLabels": negative_count if authoritative else 0,
            "replayMismatches": replay_mismatches,
            "provenanceExclusions": provenance_exclusions,
            "missingPersistedForecasts": missing_forecasts,
            "outcomesNotYetPresent": missing_outcomes,
            "duplicateOutcomes": duplicate_outcomes,
            "malformedDecisionTimestamps": malformed_decisions,
        },
        "chronologyChecks": {
            "strictMaturedLabelCutoffEnforced": True,
            "persistedForecastReplayedAgainstFrozenBaseline": True,
            "heldOutOutcomeMustFollowDecision": True,
            "observedValidPairs": len(accepted_pairs),
            "observedChronologyViolations": 0,
            "status": "NOT OBSERVED — NO VALID OOS PAIRS" if not accepted_pairs else "PASS",
        },
        "calibration": calibration,
        "folds": folds,
        "inputFingerprint": input_fingerprint or _sha256_bytes(_canonical_json(record_identity).encode("utf-8")),
    }
    report["reportFingerprint"] = _sha256_bytes(_canonical_json(report).encode("utf-8"))
    return report


def _database_snapshot(path: Path) -> dict[str, Any]:
    before_sha = _sha256_file(path)
    uri = f"file:{path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        tables = [str(row[0]) for row in table_rows]
        counts: dict[str, int] = {}
        for table in ("decision_ledger", "decision_outcome"):
            if table not in tables:
                raise RuntimeError(f"authoritative evidence database is missing {table}")
            counts[table] = int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        schema_rows = connection.execute(
            "SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master "
            "WHERE type IN ('table','index','trigger','view') ORDER BY type,name"
        ).fetchall()
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    after_sha = _sha256_file(path)
    if before_sha != after_sha:
        raise RuntimeError("authoritative database changed while being read")
    return {
        "path": str(path),
        "applicationId": application_id,
        "sha256": after_sha,
        "sizeBytes": path.stat().st_size,
        "counts": counts,
        "schemaSha256": _sha256_bytes(_canonical_json(schema_rows).encode("utf-8")),
        "integrityCheck": integrity,
    }


def _read_authoritative_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    uri = f"file:{path.as_posix()}?mode=ro"
    malformed_decisions = malformed_outcomes = 0
    decisions: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    with sqlite3.connect(uri, uri=True) as connection:
        raw_decisions = connection.execute(
            "SELECT decision_id,target_symbol,decision_time,market_as_of,instrument,decision_output_json,"
            "evidence_score,data_quality_score,source_metadata_json "
            "FROM decision_ledger WHERE target_symbol=? ORDER BY decision_time,decision_id",
            ("TX",),
        ).fetchall()
        for row in raw_decisions:
            try:
                decision_output = json.loads(row[5])
                source_metadata = json.loads(row[8])
            except (TypeError, ValueError):
                malformed_decisions += 1
                continue
            if not isinstance(decision_output, dict) or not isinstance(source_metadata, dict):
                malformed_decisions += 1
                continue
            ledger_metadata = source_metadata.get("ledger_metadata")
            if not isinstance(ledger_metadata, dict):
                ledger_metadata = {}
            decisions.append({
                "decision_id": row[0],
                "target_symbol": row[1],
                "decision_time": row[2],
                "market_as_of": row[3],
                "instrument": row[4],
                "data_as_of": ledger_metadata.get("dataAsOf", source_metadata.get("source_updated_at")),
                "decision_output": decision_output,
                "decisionState": decision_output.get("decisionState", "UNKNOWN"),
                "decisionEligible": decision_output.get("decisionEligible"),
                "executionDirection": decision_output.get("executionDirection", "UNAVAILABLE"),
                "evidence_score": row[6],
                "data_quality_score": row[7],
                "source_metadata": source_metadata,
            })
        raw_outcomes = connection.execute(
            "SELECT o.decision_id,o.evaluation_horizon,o.evaluation_time,o.status,o.market_observations_json "
            "FROM decision_outcome AS o JOIN decision_ledger AS d ON d.decision_id=o.decision_id "
            "WHERE d.target_symbol=? AND o.evaluation_horizon=? ORDER BY o.evaluation_time,o.decision_id",
            ("TX", TARGET_HORIZON),
        ).fetchall()
        for row in raw_outcomes:
            try:
                stored_observations = json.loads(row[4])
            except (TypeError, ValueError):
                malformed_outcomes += 1
                continue
            if not isinstance(stored_observations, dict):
                malformed_outcomes += 1
                continue
            metadata = stored_observations.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            outcomes.append({
                "decision_id": row[0],
                "evaluation_horizon": row[1],
                "evaluation_time": row[2],
                "status": row[3],
                "outcome_status": metadata.get("outcomeStatus", "UNAVAILABLE"),
                "outcome_metadata": metadata,
            })
    return decisions, outcomes, {
        "malformedDecisionRows": malformed_decisions,
        "malformedOutcomeRows": malformed_outcomes,
    }


def run_authoritative_validation(path: str | Path = AUTHORITATIVE_DB) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if resolved != AUTHORITATIVE_DB or not resolved.is_file():
        raise ValueError("P3-01 accepts only the canonical local prospective evidence ledger")
    before = _database_snapshot(resolved)
    if before["applicationId"] != EXPECTED_SQLITE_APPLICATION_ID:
        raise ValueError("wrong P2-03 prospective evidence database identity")
    if before["integrityCheck"].lower() != "ok":
        raise RuntimeError("authoritative prospective database integrity check failed")
    decisions, outcomes, malformed = _read_authoritative_rows(resolved)
    input_fingerprint = _sha256_bytes(_canonical_json({"decisions": decisions, "outcomes": outcomes}).encode("utf-8"))
    report = build_walk_forward_report(
        decisions,
        outcomes,
        evidence_class=AUTHORITATIVE_EVIDENCE_CLASS,
        input_fingerprint=input_fingerprint,
    )
    after = _database_snapshot(resolved)
    if before != after:
        raise RuntimeError("authoritative prospective database integrity changed during validation")
    report["database"] = {"before": before, "after": after, "unchanged": True}
    report["loadDiagnostics"] = malformed
    report["authoritativeRecordIntegrity"] = (
        "PASS" if malformed["malformedDecisionRows"] == 0 and malformed["malformedOutcomeRows"] == 0 else "FAIL"
    )
    if report["authoritativeRecordIntegrity"] != "PASS":
        report["validationPipelineStatus"] = "BLOCKED — MALFORMED LEDGER RECORDS"
    report.pop("reportFingerprint", None)
    report["reportFingerprint"] = _sha256_bytes(_canonical_json(report).encode("utf-8"))
    return report


def main() -> int:
    report = run_authoritative_validation()
    print(_canonical_json(report))
    return 0 if report["validationPipelineStatus"] == "VALIDATION PIPELINE READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
