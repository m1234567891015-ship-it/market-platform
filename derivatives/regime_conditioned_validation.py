"""Read-only P3-02 validation over the frozen P2-03/P2-05 contracts."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from derivatives import calibration
from derivatives.probability_forecast import TARGET_HORIZON, derive_directional_target
from derivatives import walk_forward_validation as p301
from scripts import p205_regime_performance as p205


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_DB = p301.AUTHORITATIVE_DB
CONTRACT_PATH = ROOT / "docs" / "P3_02_REGIME_CONDITIONED_VALIDATION_CONTRACT.md"
P205_CONTRACT_PATH = ROOT / "docs" / "P2_05_REGIME_PERFORMANCE_CONTRACT.md"
PHASE3_CONTRACT_PATH = ROOT / "docs" / "PHASE3_MODEL_VALIDATION_CONTRACT.md"
REPORT_VERSION = "P3_02_REGIME_CONDITIONED_VALIDATION_V1"
CONTRACT_ID = "P3_02_REGIME_CONDITIONED_VALIDATION_V1"
CONTRACT_SHA256 = "EE105670157843B9F90AFC0467B17D2A5B9C19551E4E475C5F693FF055D06629"
P205_CONTRACT_SHA256 = "E65588E9C771A06B6EE51BCCEFA0351033420824E77969092A875AC03EDD11D2"
PHASE3_CONTRACT_SHA256 = "43EBCAD66CD8267C07BCA2419FBBCDECA066E6195EECF1E4AC782FD5954BBC57"
P205_ANALYZER_SHA256 = "FC4E5B9DFEF9B945E78CE1410C6E58CD84137578A98323E06C9EA3B9412DDA7A"
P301_IMPLEMENTATION_SHA256 = "971F68D5B342384A5F4C74B9F0F0C398F54375EBD8C71C3D3F938C435081E3ED"
REGIMES = tuple(p205.REGIME_LABELS)
AUTHORITATIVE_EVIDENCE_CLASS = p301.AUTHORITATIVE_EVIDENCE_CLASS
TEST_EVIDENCE_CLASS = p301.TEST_EVIDENCE_CLASS

_FORECAST_VERIFIED_STATUSES = {
    "OUTCOME_NOT_YET_PRESENT",
    "DUPLICATE_OUTCOME_RECORD",
    "OOS_PAIR_INVALID_OR_NOT_MATURE",
    "OUTCOME_PROVENANCE_UNVERIFIED",
    "VALID_PROSPECTIVE_OOS_PAIR",
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_dependencies() -> dict[str, dict[str, str]]:
    expected = (
        (CONTRACT_PATH, CONTRACT_SHA256, "P3-02 contract"),
        (P205_CONTRACT_PATH, P205_CONTRACT_SHA256, "frozen P2-05 contract"),
        (PHASE3_CONTRACT_PATH, PHASE3_CONTRACT_SHA256, "frozen Phase 3 contract"),
        (Path(p205.__file__).resolve(), P205_ANALYZER_SHA256, "P2-05 implementation"),
        (Path(p301.__file__).resolve(), P301_IMPLEMENTATION_SHA256, "P3-01 implementation"),
    )
    identity: dict[str, dict[str, str]] = {}
    for path, expected_sha256, label in expected:
        if not path.is_file():
            raise FileNotFoundError(f"{label} is missing: {path}")
        actual = _sha256_file(path).upper()
        if actual != expected_sha256:
            raise RuntimeError(f"{label} SHA-256 does not match its frozen identity")
        identity[label] = {"path": str(path.relative_to(ROOT)), "sha256": actual.lower()}
    return identity


def _output(decision: dict[str, Any]) -> dict[str, Any]:
    value = decision.get("decision_output")
    return value if isinstance(value, dict) else {}


def _round_metric(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, 12)


def _empty_group() -> dict[str, Any]:
    return {
        "decisionCount": 0,
        "eligibleEvaluatedDirectionalOutcomeCount": 0,
        "eligibleObservationCount": 0,
        "positiveTargetCount": 0,
        "negativeTargetCount": 0,
        "replayVerifiedForecastCount": 0,
        "validOosPairCount": 0,
        "positiveOosPairCount": 0,
        "negativeOosPairCount": 0,
        "predictions": [],
        "labels": [],
        "returns": [],
    }


def _build_report(
    decisions: Iterable[dict[str, Any]],
    outcomes: Iterable[dict[str, Any]],
    *,
    evidence_class: str,
    input_fingerprint: str | None = None,
) -> dict[str, Any]:
    dependencies = _verify_dependencies()
    decision_rows = [row for row in decisions if isinstance(row, dict)]
    outcome_rows = [row for row in outcomes if isinstance(row, dict)]
    decision_rows.sort(key=lambda row: (
        str(row.get("decision_time") or ""), str(row.get("decision_id") or "")
    ))
    outcome_rows.sort(key=lambda row: (
        str(row.get("evaluation_time") or ""), str(row.get("decision_id") or ""),
        str(row.get("evaluation_horizon") or ""),
    ))

    walk = p301.build_walk_forward_report(
        decision_rows,
        outcome_rows,
        evidence_class=evidence_class,
        input_fingerprint=input_fingerprint,
    )
    # P2-05 owns regime classification and the evaluated directional-outcome audit.
    regime_audit = p205.analyze(decision_rows, outcome_rows)
    groups = {regime: _empty_group() for regime in REGIMES}
    invalid_score_count = 0
    invalid_score_reasons: Counter[str] = Counter()
    decisions_by_id: dict[str, dict[str, Any]] = {}
    duplicate_decision_ids = {
        decision_id for decision_id, count in Counter(
            str(row.get("decision_id") or "") for row in decision_rows
        ).items() if decision_id and count > 1
    }
    for row in decision_rows:
        decision_id = str(row.get("decision_id") or "")
        if decision_id and decision_id not in duplicate_decision_ids:
            decisions_by_id[decision_id] = row
        regime, reason = p205.decision_regime(row)
        if regime in groups:
            groups[regime]["decisionCount"] += 1
        else:
            invalid_score_count += 1
            invalid_score_reasons[str(reason or "INVALID_SCORE")] += 1

    eligible_keys: set[tuple[str, str]] = set()
    for row in regime_audit["eligibilityRows"]:
        if row.get("eligible") == "true":
            eligible_keys.add((str(row.get("decisionId") or ""), str(row.get("evaluationHorizon") or "").upper()))

    outcomes_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for outcome in outcome_rows:
        key = (
            str(outcome.get("decision_id") or ""),
            str(outcome.get("evaluation_horizon") or "").strip().upper(),
        )
        outcomes_by_key[key].append(outcome)

    eligible_observation_keys: set[tuple[str, str]] = set()
    eligible_return_by_key: dict[tuple[str, str], float] = {}
    for key in sorted(eligible_keys):
        decision_id, horizon = key
        if horizon != TARGET_HORIZON or decision_id in duplicate_decision_ids:
            continue
        decision = decisions_by_id.get(decision_id)
        matching = outcomes_by_key.get(key, [])
        if decision is None or len(matching) != 1:
            continue
        target = derive_directional_target(decision, matching[0], horizon=TARGET_HORIZON)
        if target.get("eligible") is not True:
            continue
        regime, _reason = p205.decision_regime(decision)
        if regime not in groups:
            continue
        group = groups[regime]
        group["eligibleEvaluatedDirectionalOutcomeCount"] += 1
        group["eligibleObservationCount"] += 1
        group["positiveTargetCount"] += int(target["value"] == 1)
        group["negativeTargetCount"] += int(target["value"] == 0)
        eligible_observation_keys.add(key)
        aligned = matching[0].get("outcome_metadata", {}).get("decisionAlignedReturn")
        if isinstance(aligned, (int, float)) and not isinstance(aligned, bool) and math.isfinite(float(aligned)):
            eligible_return_by_key[key] = float(aligned)

    verified_forecast_count = 0
    invalid_regime_forecast_count = 0
    for fold in walk["folds"]:
        if fold.get("status") not in _FORECAST_VERIFIED_STATUSES:
            continue
        decision_id = str(fold.get("decisionId") or "")
        decision = decisions_by_id.get(decision_id)
        if decision is None:
            continue
        regime, _reason = p205.decision_regime(decision)
        if regime not in groups:
            invalid_regime_forecast_count += 1
            continue
        groups[regime]["replayVerifiedForecastCount"] += 1
        verified_forecast_count += 1

    pair_eligibility_conflicts: list[str] = []
    valid_pair_count_without_regime = 0
    for fold in walk["folds"]:
        if fold.get("status") != "VALID_PROSPECTIVE_OOS_PAIR":
            continue
        decision_id = str(fold.get("decisionId") or "")
        decision = decisions_by_id.get(decision_id)
        key = (decision_id, TARGET_HORIZON)
        regime = p205.decision_regime(decision)[0] if decision is not None else None
        if regime not in groups:
            valid_pair_count_without_regime += 1
            continue
        if key not in eligible_keys or key not in eligible_observation_keys:
            pair_eligibility_conflicts.append(decision_id)
            continue
        target_value = fold.get("targetClass")
        prediction = fold.get("prediction")
        if target_value not in (0, 1) or isinstance(target_value, bool):
            pair_eligibility_conflicts.append(decision_id)
            continue
        if not isinstance(prediction, (int, float)) or isinstance(prediction, bool) \
                or not math.isfinite(float(prediction)) or not 0 <= float(prediction) <= 1:
            pair_eligibility_conflicts.append(decision_id)
            continue
        group = groups[regime]
        group["validOosPairCount"] += 1
        group["positiveOosPairCount"] += int(target_value == 1)
        group["negativeOosPairCount"] += int(target_value == 0)
        group["predictions"].append(float(prediction))
        group["labels"].append(int(target_value))
        group["returns"].append(eligible_return_by_key[key])

    regime_rows: list[dict[str, Any]] = []
    for regime in REGIMES:
        group = groups[regime]
        pair_count = int(group["validOosPairCount"])
        positive_pairs = int(group["positiveOosPairCount"])
        negative_pairs = int(group["negativeOosPairCount"])
        if pair_count == 0:
            sufficiency = "NOT AVAILABLE — NO VALID PROSPECTIVE OOS PAIRS"
        elif pair_count >= p301.MIN_TRAINING_SAMPLES and positive_pairs > 0 and negative_pairs > 0:
            sufficiency = "MATURE_PENDING_OWNER_ADJUDICATION"
        else:
            sufficiency = "INSUFFICIENT_SAMPLE"
        predictions = group.pop("predictions")
        labels = group.pop("labels")
        returns = group.pop("returns")
        has_pairs = bool(pair_count)
        regime_rows.append({
            "regime": regime,
            **group,
            "meanForecast": _round_metric(math.fsum(predictions) / pair_count) if has_pairs else None,
            "realizedPositiveRate": positive_pairs / pair_count if has_pairs else None,
            "brierScore": calibration.calculate_brier_score(predictions, labels) if has_pairs else None,
            "brierSkillScore": None,
            "brierSkillStatus": "NOT_CALCULATED_NO_FROZEN_PROSPECTIVE_REFERENCE",
            "meanDecisionAlignedReturn": _round_metric(math.fsum(returns) / len(returns)) if returns else None,
            "netReturn": None,
            "netReturnStatus": "NOT_CALCULATED_P3_03_SCOPE",
            "sampleSufficiencyStatus": sufficiency,
            "evidenceClass": "AUTHORITATIVE_PROSPECTIVE_LEDGER" if evidence_class == AUTHORITATIVE_EVIDENCE_CLASS
                else TEST_EVIDENCE_CLASS,
        })

    observed_regimes = [row for row in regime_rows if row["validOosPairCount"] > 0]
    if evidence_class != AUTHORITATIVE_EVIDENCE_CLASS:
        maturity = "SYNTHETIC_TEST_ONLY_NOT_AUTHORITATIVE"
    elif not observed_regimes or not any(row["eligibleObservationCount"] for row in regime_rows):
        maturity = "STATISTICAL VALIDATION EVIDENCE NOT YET MATURE"
    elif all(row["sampleSufficiencyStatus"] == "MATURE_PENDING_OWNER_ADJUDICATION" for row in observed_regimes):
        maturity = "MATURE_PENDING_OWNER_ADJUDICATION"
    else:
        maturity = "STATISTICAL VALIDATION EVIDENCE NOT YET MATURE"

    pair_count = sum(int(row["validOosPairCount"]) for row in regime_rows)
    eligible_outcome_count = sum(int(row["eligibleEvaluatedDirectionalOutcomeCount"]) for row in regime_rows)
    pipeline_blockers: list[str] = []
    if duplicate_decision_ids:
        pipeline_blockers.append("DUPLICATE_DECISION_IDS")
    if pair_eligibility_conflicts:
        pipeline_blockers.append("P3_01_P2_05_PAIR_ELIGIBILITY_DISAGREEMENT")
    if any(_output(row).get("probabilityLabelAllowed") is not False for row in decision_rows):
        pipeline_blockers.append("PROBABILITY_LABEL_NOT_EXPLICITLY_FALSE")
    pipeline_status = "BLOCKED — " + ";".join(pipeline_blockers) if pipeline_blockers else "VALIDATION PIPELINE READY"

    authoritative = evidence_class == AUTHORITATIVE_EVIDENCE_CLASS
    report: dict[str, Any] = {
        "reportVersion": REPORT_VERSION,
        "contractId": CONTRACT_ID,
        "contractSha256": CONTRACT_SHA256.lower(),
        "evidenceClass": AUTHORITATIVE_EVIDENCE_CLASS if authoritative else TEST_EVIDENCE_CLASS,
        "engineeringStatus": "PASS" if not pipeline_blockers else "BLOCKED",
        "validationPipelineStatus": pipeline_status,
        "statisticalEvidenceMaturity": maturity,
        "realizedRegimeStatistics": {
            "status": "AVAILABLE — VALID PROSPECTIVE OOS PAIRS" if pair_count else "NOT AVAILABLE — NO VALID PROSPECTIVE OOS PAIRS",
            "authoritativeEvidenceCount": pair_count if authoritative else 0,
            "eligibleEvaluatedDirectionalOutcomeCount": eligible_outcome_count if authoritative else 0,
        },
        "regimeContract": {
            "identity": p205.CONTRACT_NAME,
            "sha256": P205_CONTRACT_SHA256.lower(),
            "source": "persisted decision_output_json.marketScore",
            "boundaries": {"LOW": "[0,40)", "MID": "[40,60)", "HIGH": "[60,100]"},
            "invalidMarketScoreCount": invalid_score_count,
            "invalidMarketScoreReasons": dict(sorted(invalid_score_reasons.items())),
            "invalidRegimeForecastCount": invalid_regime_forecast_count,
            "validOosPairWithoutRegimeCount": valid_pair_count_without_regime,
        },
        "baseline": {
            "targetContractVersion": p301.TARGET_CONTRACT_VERSION,
            "featureContractVersion": p301.FEATURE_CONTRACT_VERSION,
            "modelContractVersion": p301.MODEL_CONTRACT_VERSION,
            "horizon": TARGET_HORIZON,
            "probabilityLabelAllowed": False,
            "regimeSpecificModelFit": False,
        },
        "counts": {
            "decisionRows": len(decision_rows),
            "outcomeRows": len(outcome_rows),
            "regimeCoverage": {regime: int(next(row["decisionCount"] for row in regime_rows if row["regime"] == regime))
                                for regime in REGIMES},
            "eligibleEvaluatedDirectionalT1Outcomes": eligible_outcome_count,
            "eligibleNonFlatTargetObservations": sum(int(row["eligibleObservationCount"]) for row in regime_rows),
            "replayVerifiedForecasts": verified_forecast_count,
            "validProspectiveOosPairs": pair_count,
            "authoritativeEvidenceCount": pair_count if authoritative else 0,
            "testOnlySyntheticPairCount": 0 if authoritative else pair_count,
            "validPairsWithoutValidRegime": valid_pair_count_without_regime,
            "p3P2EligibilityConflicts": len(pair_eligibility_conflicts),
        },
        "regimeRows": regime_rows,
        "sampleSufficiency": {
            "minimumPairsPerRegime": p301.MIN_TRAINING_SAMPLES,
            "requiresBothTargetClasses": True,
            "gateSource": "FROZEN P2-03 / P3-01 MINIMUM TRAINING AND CLASS-VARIATION GATE",
        },
        "chronologyAndLeakageChecks": {
            "strictMaturedLabelCutoffEnforced": walk["chronologyChecks"]["strictMaturedLabelCutoffEnforced"],
            "persistedForecastReplayEnforced": walk["chronologyChecks"]["persistedForecastReplayedAgainstFrozenBaseline"],
            "heldOutOutcomeMustFollowDecision": walk["chronologyChecks"]["heldOutOutcomeMustFollowDecision"],
            "observedValidOosPairs": pair_count,
            "actualChronologyObserved": pair_count > 0,
            "chronologyStatus": "PASS" if pair_count else "NOT OBSERVED — NO VALID OOS PAIRS",
            "regimeAssignmentUsesOutcomeOrForecast": False,
            "eachMetricPairAssignedToExactlyOnePersistedScoreRegime": True,
            "metricsComputedOnlyWithinAssignedRegime": True,
            "regimeSpecificModelFit": False,
            "status": "PASS" if pair_count else "ENFORCED; PAIR-LEVEL OBSERVATION NOT AVAILABLE",
        },
        "walkForward": {
            "contractSha256": walk["contractSha256"],
            "foldContract": walk["foldContract"],
            "counts": walk["counts"],
            "chronologyChecks": walk["chronologyChecks"],
        },
        "dependencyIdentity": dependencies,
        "p2_05EligibilityAudit": {
            "eligibleEvaluatedLongShortCount": regime_audit["summary"]["eligibleEvaluatedLongShortCount"],
            "joinIntegrity": regime_audit["summary"]["joinIntegrity"],
            "probabilityLabelAllowed": regime_audit["summary"]["probabilityLabelAllowed"],
        },
        "database": {"access": "NOT PERFORMED — SYNTHETIC TEST FIXTURE"} if not authoritative else None,
        "inputFingerprint": input_fingerprint or _sha256_bytes(
            _canonical_json({"decisions": decision_rows, "outcomes": outcome_rows}).encode("utf-8")
        ),
    }
    report["reportFingerprint"] = _sha256_bytes(_canonical_json(report).encode("utf-8"))
    return report


def build_regime_conditioned_report(
    decisions: Iterable[dict[str, Any]], outcomes: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Pure helper for deterministic test fixtures; it can never claim authority."""
    return _build_report(decisions, outcomes, evidence_class=TEST_EVIDENCE_CLASS)


def _authoritative_snapshot(path: Path) -> dict[str, Any]:
    sidecars_before = p205.read_only_fingerprints(path)
    db_before = p301._database_snapshot(path)
    inventory, decisions, outcomes = p205.readonly_inventory(path)
    p205_result = p205.analyze(decisions, outcomes, inventory)
    sidecars_after = p205.read_only_fingerprints(path)
    db_after = p301._database_snapshot(path)
    if sidecars_before != sidecars_after or db_before != db_after:
        raise RuntimeError("authoritative database or SQLite sidecar changed during read-only inspection")
    if inventory["databaseSha256"] != db_before["sha256"]:
        raise RuntimeError("P2-05 and P3-01 read-only database snapshots disagree")
    if inventory.get("databaseAndSidecarsUnchangedDuringRead") is not True:
        raise RuntimeError("P2-05 detected a database or sidecar change during read-only inspection")
    return {
        "path": str(path),
        "databaseSha256": db_before["sha256"],
        "applicationId": db_before["applicationId"],
        "decisionCount": db_before["counts"]["decision_ledger"],
        "outcomeCount": db_before["counts"]["decision_outcome"],
        "schemaFingerprint": db_before["schemaSha256"],
        "integrityCheck": db_before["integrityCheck"],
        "eligibleDirectionalOutcomeCount": p205_result["summary"]["eligibleEvaluatedLongShortCount"],
        "sidecarFingerprints": sidecars_before,
        "sidecarsUnchangedDuringRead": sidecars_before == sidecars_after,
    }


def run_authoritative_validation(path: str | Path = AUTHORITATIVE_DB) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if resolved != AUTHORITATIVE_DB or not resolved.is_file():
        raise ValueError("P3-02 accepts only the canonical local prospective evidence ledger")
    dependencies = _verify_dependencies()
    before = _authoritative_snapshot(resolved)
    if before["applicationId"] != p301.EXPECTED_SQLITE_APPLICATION_ID:
        raise ValueError("wrong P2-03 prospective evidence database identity")
    if before["integrityCheck"].lower() != "ok":
        raise RuntimeError("authoritative prospective database integrity check failed")
    if before["eligibleDirectionalOutcomeCount"] < 0:
        raise RuntimeError("eligible directional Outcome count is invalid")

    decisions, outcomes, malformed = p301._read_authoritative_rows(resolved)
    input_fingerprint = _sha256_bytes(_canonical_json({"decisions": decisions, "outcomes": outcomes}).encode("utf-8"))
    report = _build_report(
        decisions,
        outcomes,
        evidence_class=AUTHORITATIVE_EVIDENCE_CLASS,
        input_fingerprint=input_fingerprint,
    )
    after = _authoritative_snapshot(resolved)
    if before != after:
        raise RuntimeError("authoritative database or SQLite sidecar changed during P3-02 validation")
    report["dependencyIdentity"] = dependencies
    report["database"] = {"before": before, "after": after, "unchanged": True, "readOnly": True}
    report["loadDiagnostics"] = malformed
    if malformed["malformedDecisionRows"] or malformed["malformedOutcomeRows"]:
        report["engineeringStatus"] = "BLOCKED"
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
