"""Read-only P3-04 prospective model-drift / temporal-stability analysis."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from derivatives import calibration
from derivatives import net_expectancy_validation as p303
from derivatives import probability_forecast as p2
from derivatives import regime_conditioned_validation as p302
from derivatives import walk_forward_validation as p301
from scripts import p205_regime_performance as p205
from scripts.p203_v2_historical_development import _roc_auc as _research_roc_auc


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_DB = p301.AUTHORITATIVE_DB
CONTRACT_PATH = ROOT / "docs" / "P3_04_MODEL_DRIFT_TEMPORAL_STABILITY_CONTRACT.md"
CONTRACT_ID = "P3_04_TEMPORAL_STABILITY_V1"
CONTRACT_SHA256 = "95E13031CEDF996A7A6935C33B9FB01C20776F91F58D64C71B7C9AF0F63E6BD6"
PHASE3_CONTRACT_SHA256 = "43EBCAD66CD8267C07BCA2419FBBCDECA066E6195EECF1E4AC782FD5954BBC57"
P205_CONTRACT_SHA256 = "E65588E9C771A06B6EE51BCCEFA0351033420824E77969092A875AC03EDD11D2"
P302_CONTRACT_SHA256 = "EE105670157843B9F90AFC0467B17D2A5B9C19551E4E475C5F693FF055D06629"
P303_CONTRACT_SHA256 = "056A9216E693E6E2CF2C403C988B4624C81ED4CF7110314E1C8C8E7F3E6BA058"
P2_FEATURE_IMPLEMENTATION_SHA256 = "52AC6F8CA6066893D4E7E959069C6CDC0481C31C8EA696690D4C8EA111487A09"
CALIBRATION_IMPLEMENTATION_SHA256 = "8A9908EA56D91AA75198C5F9B15A1E0C95EA173EBC04C4B3C0E530D29A5490D4"
P301_IMPLEMENTATION_SHA256 = "971F68D5B342384A5F4C74B9F0F0C398F54375EBD8C71C3D3F938C435081E3ED"
P302_IMPLEMENTATION_SHA256 = "07CBA886378F7CAEE6328A3C059E9F6B3E8ED02AD46D4970668E3862F0DAE8C7"
P303_IMPLEMENTATION_SHA256 = "2EAC2A24A366297581AA8C7C1310AB3B3B6AA06BD16AD558608C75765C19B4D9"
P205_IMPLEMENTATION_SHA256 = "FC4E5B9DFEF9B945E78CE1410C6E58CD84137578A98323E06C9EA3B9412DDA7A"
ROC_AUC_HELPER_SHA256 = "2637C9C3A7768EABB116219472866AC67190B0B8B462015C95FC63357044E078"
EXPECTED_SQLITE_APPLICATION_ID = 0x50323033
REPORT_VERSION = CONTRACT_ID
AUTHORITATIVE_EVIDENCE_CLASS = "AUTHORITATIVE_PROSPECTIVE_LEDGER"
TEST_EVIDENCE_CLASS = "SYNTHETIC_TEST_ONLY"
WINDOW_SIZE = 30
PSI_EPSILON = 0.000001
FEATURE_FIELDS = tuple(p2.FEATURE_FIELDS)
FEATURE_LABELS = {
    "marketScore": "marketScore",
    "riskScore": "riskScore",
    "evidenceScore": "evidenceScore",
    "dataQualityScore": "dataQualityScore",
}
SCORE_BINS = tuple(range(0, 101, 10))
PROBABILITY_BINS = tuple(index / 10 for index in range(11))
FORECAST_VERIFIED_STATUSES = frozenset({
    "OUTCOME_NOT_YET_PRESENT",
    "DUPLICATE_OUTCOME_RECORD",
    "OOS_PAIR_INVALID_OR_NOT_MATURE",
    "OUTCOME_PROVENANCE_UNVERIFIED",
    "VALID_PROSPECTIVE_OOS_PAIR",
})
ELIGIBLE_COST_AUDIT_STATES = frozenset({
    "DIRECTIONAL_ELIGIBLE_COST_EXCLUDED",
    "INCLUDED_NET_EXPECTANCY",
})


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _canonical_safe(value: Any) -> Any:
    """Make rejected non-finite fixture evidence hashable without accepting it."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"$nonFiniteNumber": "NaN" if math.isnan(value) else "Infinity" if value > 0 else "-Infinity"}
    if isinstance(value, dict):
        return {str(key): _canonical_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_safe(child) for child in value]
    return value


def _fingerprint_inputs(decisions: Iterable[dict[str, Any]], outcomes: Iterable[dict[str, Any]]) -> str:
    safe_decisions = [_canonical_safe(row) for row in decisions]
    safe_outcomes = [_canonical_safe(row) for row in outcomes]
    safe_decisions.sort(key=_canonical_json)
    safe_outcomes.sort(key=_canonical_json)
    payload = {"decisions": safe_decisions, "outcomes": safe_outcomes}
    return _sha256_bytes(_canonical_json(payload).encode("utf-8"))


def _verify_dependencies() -> dict[str, Any]:
    direct = {
        "p304Contract": (CONTRACT_PATH, CONTRACT_SHA256),
        "phase3Contract": (ROOT / "docs" / "PHASE3_MODEL_VALIDATION_CONTRACT.md", PHASE3_CONTRACT_SHA256),
        "p205Contract": (ROOT / "docs" / "P2_05_REGIME_PERFORMANCE_CONTRACT.md", P205_CONTRACT_SHA256),
        "p302Contract": (ROOT / "docs" / "P3_02_REGIME_CONDITIONED_VALIDATION_CONTRACT.md", P302_CONTRACT_SHA256),
        "p303Contract": (ROOT / "docs" / "P3_03_NET_EXPECTANCY_VALIDATION_CONTRACT.md", P303_CONTRACT_SHA256),
        "p2FeatureImplementation": (Path(p2.__file__).resolve(), P2_FEATURE_IMPLEMENTATION_SHA256),
        "calibrationImplementation": (Path(calibration.__file__).resolve(), CALIBRATION_IMPLEMENTATION_SHA256),
        "p301Implementation": (Path(p301.__file__).resolve(), P301_IMPLEMENTATION_SHA256),
        "p302Implementation": (Path(p302.__file__).resolve(), P302_IMPLEMENTATION_SHA256),
        "p303Implementation": (Path(p303.__file__).resolve(), P303_IMPLEMENTATION_SHA256),
        "p205Implementation": (Path(p205.__file__).resolve(), P205_IMPLEMENTATION_SHA256),
        "rocAucHelper": (ROOT / "scripts" / "p203_v2_historical_development.py", ROC_AUC_HELPER_SHA256),
    }
    identity: dict[str, Any] = {}
    for name, (path, expected) in direct.items():
        if not path.is_file():
            raise FileNotFoundError(f"frozen P3-04 dependency is missing: {path}")
        actual = _sha256_file(path).upper()
        if actual != expected:
            raise RuntimeError(f"frozen P3-04 dependency SHA-256 mismatch: {name}")
        identity[name] = {"path": str(path.relative_to(ROOT)), "sha256": actual.lower()}
    # These existing validators verify their own deeper frozen dependency sets.
    identity["p302VerifiedDependencies"] = p302._verify_dependencies()
    identity["p303VerifiedDependencies"] = p303._verify_dependencies()
    return identity


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _round_metric(value: float | None) -> float | None:
    return round(value, 12) if value is not None and math.isfinite(value) else None


def _timestamp(decision: dict[str, Any]) -> Any:
    return decision.get("decision_time") or decision.get("decisionTime")


def _decision_output(decision: dict[str, Any]) -> dict[str, Any]:
    output = decision.get("decision_output")
    if not isinstance(output, dict):
        output = decision.get("decisionOutput")
    return output if isinstance(output, dict) else {}


def _feature_population(decisions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    id_counts = Counter(str(row.get("decision_id") or "") for row in decisions)
    excluded: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        decision_id = str(decision.get("decision_id") or "")
        if not decision_id:
            excluded["MISSING_DECISION_ID"] += 1
            continue
        if id_counts[decision_id] != 1:
            excluded["DUPLICATE_DECISION_ID"] += 1
            continue
        decision_time = p301._aware_datetime(_timestamp(decision))
        if decision_time is None:
            excluded["INVALID_DECISION_TIMESTAMP"] += 1
            continue
        vector = p2.build_feature_vector(decision)
        if vector is None:
            excluded["INVALID_OR_NON_POINT_IN_TIME_P2_03_FEATURE_VECTOR"] += 1
            continue
        values = {name: float(value) * 100.0 for name, value in zip(FEATURE_LABELS, vector)}
        if any(not math.isfinite(value) or value < 0 or value > 100 for value in values.values()):
            excluded["INVALID_P2_03_FEATURE_RANGE"] += 1
            continue
        rows.append({
            "decisionId": decision_id,
            "decisionTime": str(_timestamp(decision)),
            "_sortTime": decision_time,
            "features": values,
        })
    rows.sort(key=lambda row: (row["_sortTime"], row["decisionId"]))
    for row in rows:
        row.pop("_sortTime", None)
    return rows, dict(sorted(excluded.items()))


def _forecast_identity_is_valid(decision: dict[str, Any], forecast: Any) -> bool:
    if not isinstance(forecast, dict):
        return False
    value = _finite_number(forecast.get("value"))
    decision_time = p301._aware_datetime(_timestamp(decision))
    generated_at = p301._aware_datetime(forecast.get("generatedAt"))
    fit_cutoff = p301._aware_datetime(forecast.get("fitCutoff"))
    output = _decision_output(decision)
    expected_instrument = str(decision.get("instrument") or "").strip().upper()
    forecast_instrument = str(forecast.get("instrument") or "").strip().upper()
    return bool(
        value is not None and 0 <= value <= 1
        and decision_time is not None and generated_at == decision_time
        and fit_cutoff is not None and fit_cutoff < decision_time
        and forecast.get("decisionId") == decision.get("decision_id")
        and forecast_instrument == expected_instrument
        and forecast.get("targetType") == p2.TARGET_TYPE
        and forecast.get("targetContractVersion") == p2.TARGET_CONTRACT_VERSION
        and forecast.get("featureContractVersion") == p2.FEATURE_CONTRACT_VERSION
        and forecast.get("horizon") == p2.TARGET_HORIZON
        and forecast.get("modelType") == "LOGISTIC_REGRESSION"
        and str(forecast.get("modelVersion") or "").startswith(p2.MODEL_CONTRACT_VERSION + ":")
        and forecast.get("provenance") == "PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT"
        and forecast.get("availability") == "PROSPECTIVE_ONLY"
        and forecast.get("featureNames") == list(p2.FEATURE_NAMES)
        and output.get("probabilityLabelAllowed") is False
    )


def _forecast_population(
    decisions: list[dict[str, Any]], walk_report: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_id = {str(row.get("decision_id") or ""): row for row in decisions}
    excluded: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    replay_verified_ids: set[str] = set()
    for fold in walk_report.get("folds", []):
        decision_id = str(fold.get("decisionId") or "")
        status = str(fold.get("status") or "UNKNOWN")
        if status not in FORECAST_VERIFIED_STATUSES:
            if status in {
                "PERSISTED_FORECAST_MISSING",
                "DETERMINISTIC_REPLAY_MISMATCH",
                "TRAINING_PROVENANCE_UNVERIFIED",
                "DECISION_PROVENANCE_UNVERIFIED",
                "INSUFFICIENT_TRAINING_HISTORY",
                "INSUFFICIENT_TARGET_VARIATION",
                "UNAVAILABLE_INELIGIBLE_DECISION",
                "INVALID_FIT_CUTOFF",
            }:
                excluded[status] += 1
            continue
        decision = by_id.get(decision_id)
        if decision is None:
            excluded["FORECAST_DECISION_NOT_UNIQUE_OR_MISSING"] += 1
            continue
        forecast = _decision_output(decision).get("probabilityForecast")
        if not _forecast_identity_is_valid(decision, forecast):
            excluded["INVALID_PERSISTED_FORECAST_IDENTITY_OR_VALUE"] += 1
            continue
        replay_verified_ids.add(decision_id)
        rows.append({
            "decisionId": decision_id,
            "decisionTime": str(_timestamp(decision)),
            "_sortTime": p301._aware_datetime(_timestamp(decision)),
            "probability": float(forecast["value"]),
        })
    rows.sort(key=lambda row: (row["_sortTime"], row["decisionId"]))
    for row in rows:
        row.pop("_sortTime", None)
    persisted_objects = sum(
        isinstance(_decision_output(row).get("probabilityForecast"), dict) for row in decisions
    )
    return rows, {
        "persistedForecastObjectCount": persisted_objects,
        "replayVerifiedForecastCount": len(replay_verified_ids),
        "validProspectiveModelForecastCount": len(rows),
        "excludedForecastCount": sum(excluded.values()),
        "forecastExclusionsByReason": dict(sorted(excluded.items())),
    }


def _target_population(
    decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]], net_report: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    decisions_by_id = {str(row.get("decision_id") or ""): row for row in decisions}
    outcomes_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for outcome in outcomes:
        outcomes_by_key[(str(outcome.get("decision_id") or ""), str(outcome.get("evaluation_horizon") or "").upper())].append(outcome)
    eligible_keys = {
        (str(row.get("decisionId") or ""), str(row.get("horizon") or "").upper())
        for row in net_report.get("eligibilityAudit", [])
        if row.get("eligibility") in ELIGIBLE_COST_AUDIT_STATES
    }
    excluded: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for decision_id, horizon in sorted(eligible_keys):
        decision = decisions_by_id.get(decision_id)
        matching = outcomes_by_key.get((decision_id, horizon), [])
        if decision is None or len(matching) != 1:
            excluded["INVALID_OR_NONUNIQUE_DECISION_OUTCOME_ASSOCIATION"] += 1
            continue
        target = p2.derive_directional_target(decision, matching[0], horizon=p2.TARGET_HORIZON)
        if target.get("eligible") is not True:
            excluded[str(target.get("status") or "INVALID_DIRECTIONAL_TARGET")] += 1
            continue
        rows.append({
            "decisionId": decision_id,
            "decisionTime": str(target.get("decisionTime") or _timestamp(decision)),
            "_sortTime": p301._aware_datetime(target.get("decisionTime") or _timestamp(decision)),
            "target": int(target["value"]),
        })
    rows.sort(key=lambda row: (row["_sortTime"] or __import__("datetime").datetime.max.replace(tzinfo=__import__("datetime").timezone.utc), row["decisionId"]))
    for row in rows:
        row.pop("_sortTime", None)
    return rows, {
        "eligibleMaturedDirectionalTargetObservationCount": len(rows),
        "positiveTargetCount": sum(row["target"] == 1 for row in rows),
        "negativeTargetCount": sum(row["target"] == 0 for row in rows),
        "excludedTargetCount": sum(excluded.values()),
        "targetExclusionsByReason": dict(sorted(excluded.items())),
    }


def _oos_population(walk_report: dict[str, Any], decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(row.get("decision_id") or ""): row for row in decisions}
    rows: list[dict[str, Any]] = []
    for fold in walk_report.get("folds", []):
        if fold.get("status") != "VALID_PROSPECTIVE_OOS_PAIR":
            continue
        decision_id = str(fold.get("decisionId") or "")
        decision_time = p301._aware_datetime(_timestamp(by_id.get(decision_id, {})))
        prediction = _finite_number(fold.get("prediction"))
        target = fold.get("targetClass")
        if (
            decision_time is None or prediction is None or not 0 <= prediction <= 1
            or isinstance(target, bool) or target not in (0, 1)
        ):
            continue
        rows.append({
            "decisionId": decision_id,
            "decisionTime": str(_timestamp(by_id[decision_id])),
            "_sortTime": decision_time,
            "probability": prediction,
            "target": int(target),
        })
    rows.sort(key=lambda row: (row["_sortTime"], row["decisionId"]))
    for row in rows:
        row.pop("_sortTime", None)
    return rows


def _cost_qualified_population(
    net_report: dict[str, Any], decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]]
) -> tuple[dict[tuple[str, str, str], list[dict[str, Any]]], dict[str, int]]:
    decisions_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outcomes_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in decisions:
        decisions_by_id[str(row.get("decision_id") or "")].append(row)
    for row in outcomes:
        outcomes_by_key[(str(row.get("decision_id") or ""), str(row.get("evaluation_horizon") or "").upper())].append(row)
    scopes: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    excluded: Counter[str] = Counter()
    for audit in net_report.get("eligibilityAudit", []):
        if audit.get("eligibility") != "INCLUDED_NET_EXPECTANCY":
            continue
        decision_id = str(audit.get("decisionId") or "")
        horizon = str(audit.get("horizon") or "").upper()
        decision_matches = decisions_by_id.get(decision_id, [])
        outcome_matches = outcomes_by_key.get((decision_id, horizon), [])
        if len(decision_matches) != 1 or len(outcome_matches) != 1:
            excluded["P3_03_QUALIFIED_ROW_COULD_NOT_BE_REJOINED"] += 1
            continue
        decision = decision_matches[0]
        outcome = outcome_matches[0]
        decision_time = p301._aware_datetime(decision.get("decision_time"))
        net_return = _finite_number(outcome.get("net_return"))
        cost = decision.get("execution_cost_assumptions") if isinstance(decision.get("execution_cost_assumptions"), dict) else {}
        instrument = str(decision.get("instrument") or "").strip().upper()
        contract = str(cost.get("contractVersion") or "")
        currency = str(cost.get("currency") or "")
        if decision_time is None or net_return is None or not instrument or not contract or not currency:
            excluded["P3_03_QUALIFIED_ROW_MISSING_TEMPORAL_SCOPE_OR_RETURN"] += 1
            continue
        scope_key = (instrument, contract, currency)
        scopes[scope_key].append({
            "decisionId": decision_id,
            "decisionTime": str(decision.get("decision_time")),
            "_sortTime": decision_time,
            "netReturn": net_return,
        })
    for values in scopes.values():
        values.sort(key=lambda row: (row["_sortTime"], row["decisionId"]))
        for row in values:
            row.pop("_sortTime", None)
    return dict(scopes), {
        "costQualifiedObservationCount": sum(len(values) for values in scopes.values()),
        "costScopeCount": len(scopes),
        "costQualifiedJoinExclusionCount": sum(excluded.values()),
        "costQualifiedJoinExclusionsByReason": dict(sorted(excluded.items())),
    }


def _window_descriptor(rows: list[dict[str, Any]], start: int, size: int) -> dict[str, Any]:
    selected = rows[start:start + size]
    return {
        "startIndex": start,
        "endIndexExclusive": start + size,
        "observationCount": len(selected),
        "firstDecisionTime": selected[0]["decisionTime"] if selected else None,
        "lastDecisionTime": selected[-1]["decisionTime"] if selected else None,
        "firstDecisionId": selected[0]["decisionId"] if selected else None,
        "lastDecisionId": selected[-1]["decisionId"] if selected else None,
    }


def _window_pairs(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[tuple[dict[str, Any], list[dict[str, Any]]]], int]:
    count = len(rows)
    if count < 2 * WINDOW_SIZE:
        return {}, [], count
    reference = _window_descriptor(rows, 0, WINDOW_SIZE)
    comparisons = [
        (_window_descriptor(rows, start, WINDOW_SIZE), rows[start:start + WINDOW_SIZE])
        for start in range(WINDOW_SIZE, count - WINDOW_SIZE + 1, WINDOW_SIZE)
    ]
    compared_count = WINDOW_SIZE + len(comparisons) * WINDOW_SIZE
    return reference, comparisons, count - compared_count


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "mean": None, "median": None, "populationStdDev": None, "minimum": None, "maximum": None}
    if any(not math.isfinite(value) for value in values):
        raise ValueError("non-finite values cannot enter temporal statistics")
    return {
        "n": len(values),
        "mean": _round_metric(math.fsum(values) / len(values)),
        "median": _round_metric(float(statistics.median(values))),
        "populationStdDev": _round_metric(float(statistics.pstdev(values))),
        "minimum": _round_metric(min(values)),
        "maximum": _round_metric(max(values)),
    }


def _score_bin(value: float) -> int:
    return min(int(value // 10), 9)


def _probability_bin(value: float) -> int:
    if not math.isfinite(value) or value < 0 or value > 1:
        raise ValueError("probability must be finite and within [0,1]")
    return min(int(value * 10), 9)


def _histogram(values: list[float], bin_index) -> list[int]:
    counts = [0] * 10
    for value in values:
        counts[bin_index(value)] += 1
    return counts


def _psi(reference: list[float], current: list[float], bin_index) -> float | None:
    if not reference or not current:
        return None
    ref_counts = _histogram(reference, bin_index)
    cur_counts = _histogram(current, bin_index)
    bins = len(ref_counts)
    ref_denominator = len(reference) + bins * PSI_EPSILON
    cur_denominator = len(current) + bins * PSI_EPSILON
    ref_props = [(count + PSI_EPSILON) / ref_denominator for count in ref_counts]
    cur_props = [(count + PSI_EPSILON) / cur_denominator for count in cur_counts]
    value = math.fsum((q - p) * math.log(q / p) for p, q in zip(ref_props, cur_props))
    return _round_metric(value)


def _comparison_status(count: int) -> str:
    return "AVAILABLE" if count >= 2 * WINDOW_SIZE else "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS"


def _feature_temporal_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference, comparisons, remainder = _window_pairs(rows)
    report: dict[str, Any] = {
        "status": _comparison_status(len(rows)),
        "eligibleObservationCount": len(rows),
        "windowSize": WINDOW_SIZE,
        "completeComparisonCount": len(comparisons),
        "uncomparedTailObservationCount": remainder,
        "referenceWindow": reference or None,
        "features": {},
    }
    if not comparisons:
        return report
    ref_rows = rows[:WINDOW_SIZE]
    ref_features: dict[str, Any] = {}
    for field in FEATURE_FIELDS:
        label = FEATURE_LABELS[field]
        ref_values = [float(row["features"][label]) for row in ref_rows]
        ref_features[field] = _stats(ref_values)
        feature_comparisons = []
        for descriptor, current_rows in comparisons:
            cur_values = [float(row["features"][label]) for row in current_rows]
            cur_stats = _stats(cur_values)
            feature_comparisons.append({
                "currentWindow": descriptor,
                "current": cur_stats,
                "meanDelta": _round_metric(cur_stats["mean"] - ref_features[field]["mean"]),
                "medianDelta": _round_metric(cur_stats["median"] - ref_features[field]["median"]),
                "populationStdDevDelta": _round_metric(cur_stats["populationStdDev"] - ref_features[field]["populationStdDev"]),
                "psi": _psi(ref_values, cur_values, _score_bin),
            })
        report["features"][field] = {"reference": ref_features[field], "comparisons": feature_comparisons}
    return report


def _regime_temporal_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference, comparisons, remainder = _window_pairs(rows)
    report: dict[str, Any] = {
        "contract": p205.CONTRACT_NAME,
        "contractSha256": P205_CONTRACT_SHA256.lower(),
        "source": "P2-03 feature-eligible immutable decision-time marketScore",
        "status": _comparison_status(len(rows)),
        "eligibleObservationCount": len(rows),
        "windowSize": WINDOW_SIZE,
        "uncomparedTailObservationCount": remainder,
        "referenceWindow": reference or None,
        "comparisons": [],
    }
    if not comparisons:
        return report

    def composition(selected: list[dict[str, Any]]) -> dict[str, Any]:
        counts = {name: 0 for name in p205.REGIME_LABELS}
        for row in selected:
            regime, _reason = p205.classify_market_score(row["features"]["marketScore"])
            if regime in counts:
                counts[regime] += 1
        total = sum(counts.values())
        return {"counts": counts, "proportions": {key: round(value / total, 12) if total else None for key, value in counts.items()}}

    ref_composition = composition(rows[:WINDOW_SIZE])
    report["reference"] = ref_composition
    for descriptor, current_rows in comparisons:
        current_composition = composition(current_rows)
        report["comparisons"].append({
            "currentWindow": descriptor,
            "current": current_composition,
            "countDelta": {key: current_composition["counts"][key] - ref_composition["counts"][key] for key in p205.REGIME_LABELS},
            "proportionDelta": {key: _round_metric(current_composition["proportions"][key] - ref_composition["proportions"][key]) for key in p205.REGIME_LABELS},
        })
    return report


def _forecast_temporal_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference, comparisons, remainder = _window_pairs(rows)
    report: dict[str, Any] = {
        "status": "NOT AVAILABLE — NO VALID PROSPECTIVE MODEL FORECASTS" if not rows else _comparison_status(len(rows)),
        "eligibleObservationCount": len(rows),
        "windowSize": WINDOW_SIZE,
        "uncomparedTailObservationCount": remainder,
        "referenceWindow": reference or None,
        "comparisons": [],
    }
    if not comparisons:
        return report
    ref_values = [float(row["probability"]) for row in rows[:WINDOW_SIZE]]
    report["reference"] = _stats(ref_values)
    for descriptor, current_rows in comparisons:
        cur_values = [float(row["probability"]) for row in current_rows]
        report["comparisons"].append({
            "currentWindow": descriptor,
            "current": _stats(cur_values),
            "meanDelta": _round_metric(_stats(cur_values)["mean"] - report["reference"]["mean"]),
            "medianDelta": _round_metric(_stats(cur_values)["median"] - report["reference"]["median"]),
            "populationStdDevDelta": _round_metric(_stats(cur_values)["populationStdDev"] - report["reference"]["populationStdDev"]),
            "referenceBinCounts": _histogram(ref_values, _probability_bin),
            "currentBinCounts": _histogram(cur_values, _probability_bin),
            "psi": _psi(ref_values, cur_values, _probability_bin),
        })
    return report


def _base_rate_temporal_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference, comparisons, remainder = _window_pairs(rows)
    report: dict[str, Any] = {
        "status": _comparison_status(len(rows)),
        "eligibleMaturedTargetCount": len(rows),
        "windowSize": WINDOW_SIZE,
        "uncomparedTailObservationCount": remainder,
        "referenceWindow": reference or None,
        "comparisons": [],
    }
    if not comparisons:
        return report
    ref = rows[:WINDOW_SIZE]
    ref_positive = sum(row["target"] == 1 for row in ref)
    ref_negative = len(ref) - ref_positive
    ref_rate = ref_positive / len(ref)
    report["reference"] = {"positiveTargetCount": ref_positive, "negativeTargetCount": ref_negative, "positiveTargetRate": _round_metric(ref_rate)}
    for descriptor, current_rows in comparisons:
        positive = sum(row["target"] == 1 for row in current_rows)
        negative = len(current_rows) - positive
        rate = positive / len(current_rows)
        report["comparisons"].append({
            "currentWindow": descriptor,
            "current": {"positiveTargetCount": positive, "negativeTargetCount": negative, "positiveTargetRate": _round_metric(rate)},
            "positiveTargetRateDelta": _round_metric(rate - ref_rate),
        })
    return report


def _auc_window(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [int(row["target"]) for row in rows]
    if not labels or 0 not in labels or 1 not in labels:
        return {"value": None, "status": "NOT AVAILABLE — SINGLE CLASS"}
    pairs = [{"probability": float(row["probability"]), "outcome": int(row["target"])} for row in rows]
    return {"value": _round_metric(_research_roc_auc(pairs, "probability")), "status": "AVAILABLE"}


def _paired_performance_temporal_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference, comparisons, remainder = _window_pairs(rows)
    report: dict[str, Any] = {
        "status": _comparison_status(len(rows)),
        "validProspectiveOosPairCount": len(rows),
        "windowSize": WINDOW_SIZE,
        "uncomparedTailObservationCount": remainder,
        "referenceWindow": reference or None,
        "comparisons": [],
    }
    if not comparisons:
        report.update({
            "reference": {"brierScore": None, "auc": {"value": None, "status": "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS"}},
            "metricsAvailable": False,
        })
        return report
    ref = rows[:WINDOW_SIZE]
    ref_probs = [float(row["probability"]) for row in ref]
    ref_labels = [int(row["target"]) for row in ref]
    ref_brier = calibration.calculate_brier_score(ref_probs, ref_labels)
    ref_auc = _auc_window(ref)
    report["reference"] = {"brierScore": ref_brier, "auc": ref_auc}
    report["metricsAvailable"] = True
    for descriptor, current_rows in comparisons:
        probs = [float(row["probability"]) for row in current_rows]
        labels = [int(row["target"]) for row in current_rows]
        brier = calibration.calculate_brier_score(probs, labels)
        auc = _auc_window(current_rows)
        report["comparisons"].append({
            "currentWindow": descriptor,
            "current": {"brierScore": brier, "auc": auc},
            "brierScoreDelta": _round_metric(brier - ref_brier) if brier is not None and ref_brier is not None else None,
        })
    return report


def _net_expectancy_temporal_report(
    samples_by_scope: dict[tuple[str, str, str], list[dict[str, Any]]],
    known_scope_rows: list[dict[str, Any]],
    net_counts: dict[str, int],
) -> dict[str, Any]:
    keys = set(samples_by_scope)
    for scope in known_scope_rows:
        instrument = str(scope.get("instrument") or "").upper()
        version = str(scope.get("costContractVersion") or "")
        currency = str(scope.get("currency") or "")
        if instrument and version and currency:
            keys.add((instrument, version, currency))
    scope_reports = []
    for key in sorted(keys):
        rows = samples_by_scope.get(key, [])
        reference, comparisons, remainder = _window_pairs(rows)
        scope_report: dict[str, Any] = {
            "instrument": key[0],
            "costContractVersion": key[1],
            "currency": key[2],
            "status": _comparison_status(len(rows)) if rows else "NOT AVAILABLE — NO COST-QUALIFIED OBSERVATIONS",
            "costQualifiedObservationCount": len(rows),
            "windowSize": WINDOW_SIZE,
            "uncomparedTailObservationCount": remainder,
            "referenceWindow": reference or None,
            "comparisons": [],
        }
        if comparisons:
            ref_values = [float(row["netReturn"]) for row in rows[:WINDOW_SIZE]]
            ref_mean = math.fsum(ref_values) / WINDOW_SIZE
            scope_report["referenceNetExpectancy"] = _round_metric(ref_mean)
            for descriptor, current_rows in comparisons:
                current_mean = math.fsum(float(row["netReturn"]) for row in current_rows) / WINDOW_SIZE
                scope_report["comparisons"].append({
                    "currentWindow": descriptor,
                    "currentNetExpectancy": _round_metric(current_mean),
                    "netExpectancyDelta": _round_metric(current_mean - ref_mean),
                })
        else:
            scope_report["referenceNetExpectancy"] = None
        scope_reports.append(scope_report)
    return {
        "status": "AVAILABLE" if any(row["comparisons"] for row in scope_reports) else "NOT AVAILABLE",
        "authoritativeCostQualifiedObservationCount": net_counts.get("costQualifiedObservationCount", 0),
        "scopes": scope_reports,
        "costRulesReusedFrom": "P3_03_NET_EXPECTANCY_VALIDATION_V1",
    }


def _build_report(
    decisions: Iterable[dict[str, Any]],
    outcomes: Iterable[dict[str, Any]],
    *,
    evidence_class: str,
    input_fingerprint: str,
    walk_report: dict[str, Any] | None = None,
    net_report: dict[str, Any] | None = None,
    cost_decisions: list[dict[str, Any]] | None = None,
    cost_outcomes: list[dict[str, Any]] | None = None,
    dependencies: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dependencies = dependencies or _verify_dependencies()
    decision_rows = [row for row in decisions if isinstance(row, dict)]
    outcome_rows = [row for row in outcomes if isinstance(row, dict)]
    if walk_report is None:
        walk_report = p301.build_walk_forward_report(
            decision_rows, outcome_rows,
            evidence_class=p301.TEST_EVIDENCE_CLASS,
            input_fingerprint=input_fingerprint,
        )
    if net_report is None:
        net_report = p303._build_report(
            decision_rows, outcome_rows,
            evidence_class=p303.TEST_EVIDENCE_CLASS,
            input_fingerprint=input_fingerprint,
        )
    feature_rows, feature_exclusions = _feature_population(decision_rows)
    forecast_rows, forecast_counts = _forecast_population(decision_rows, walk_report)
    target_rows, target_counts = _target_population(decision_rows, outcome_rows, net_report)
    oos_rows = _oos_population(walk_report, decision_rows)
    cost_rows, cost_counts = _cost_qualified_population(
        net_report,
        cost_decisions if cost_decisions is not None else decision_rows,
        cost_outcomes if cost_outcomes is not None else outcome_rows,
    )
    duplicate_ids = sorted(
        decision_id for decision_id, count in Counter(str(row.get("decision_id") or "") for row in decision_rows).items()
        if decision_id and count > 1
    )
    pipeline_blockers: list[str] = []
    if duplicate_ids:
        pipeline_blockers.append("DUPLICATE_DECISION_IDS")
    if walk_report.get("validationPipelineStatus") != "VALIDATION PIPELINE READY":
        pipeline_blockers.append("P3_01_WALK_FORWARD_PIPELINE_BLOCKED")
    if net_report.get("engineeringStatus") != "PASS":
        pipeline_blockers.append("P3_03_NET_EXPECTANCY_PIPELINE_BLOCKED")
    for key, value in (net_report.get("inputCounts") or {}).items():
        if key in {"eligibleEvaluatedDirectionalT1OutcomeCount", "costQualifiedExpectancySampleCount"} and not isinstance(value, int):
            pipeline_blockers.append("INVALID_P3_03_EVIDENCE_COUNT")
    if cost_counts["costQualifiedJoinExclusionCount"]:
        pipeline_blockers.append("P3_03_QUALIFIED_ROW_JOIN_CONFLICT")
    pipeline_blockers = sorted(set(pipeline_blockers))
    authoritative = evidence_class == AUTHORITATIVE_EVIDENCE_CLASS
    regime_invalid_market_score = sum(1 for row in decision_rows if p205.decision_regime(row)[0] is None)
    regime_report = _regime_temporal_report(feature_rows)
    feature_report = _feature_temporal_report(feature_rows)
    forecast_report = _forecast_temporal_report(forecast_rows)
    base_rate_report = _base_rate_temporal_report(target_rows)
    paired_report = _paired_performance_temporal_report(oos_rows)
    expectancy_report = _net_expectancy_temporal_report(
        cost_rows, net_report.get("scopes", []), cost_counts
    )
    comparisons_available = any((
        feature_report.get("status") == "AVAILABLE",
        forecast_report.get("status") == "AVAILABLE",
        base_rate_report.get("status") == "AVAILABLE",
        paired_report.get("status") == "AVAILABLE",
        expectancy_report.get("status") == "AVAILABLE",
    ))
    report: dict[str, Any] = {
        "reportVersion": REPORT_VERSION,
        "contract": {"id": CONTRACT_ID, "sha256": CONTRACT_SHA256.lower()},
        "evidenceClass": AUTHORITATIVE_EVIDENCE_CLASS if authoritative else TEST_EVIDENCE_CLASS,
        "engineeringStatus": "PASS" if not pipeline_blockers else "BLOCKED",
        "temporalStabilityPipelineStatus": "READY" if not pipeline_blockers else "NOT READY",
        "authoritativeDriftEvidence": (
            "AVAILABLE — DESCRIPTIVE COMPARISONS EXIST" if authoritative and comparisons_available
            else "NOT AVAILABLE — INSUFFICIENT TEMPORAL OBSERVATIONS" if authoritative
            else "SYNTHETIC_TEST_ONLY — NEVER AUTHORITATIVE"
        ),
        "driftSeverity": "NOT GOVERNANCE-CLASSIFIED",
        "monitoringContract": {
            "windowSize": WINDOW_SIZE,
            "reference": "FIRST 30 ELIGIBLE OBSERVATIONS IN EACH INDEPENDENT POPULATION; FIXED",
            "currentWindows": "SUBSEQUENT NON-OVERLAPPING CHRONOLOGICAL BLOCKS OF 30",
            "ordering": "DECISION_TIMESTAMP_ASCENDING_THEN_DECISION_ID; NO SHUFFLE",
            "minimumObservationsForComparison": 2 * WINDOW_SIZE,
            "psiEpsilonPerBin": PSI_EPSILON,
            "probabilityLabelAllowed": False,
        },
        "baseline": {
            "targetContractVersion": p2.TARGET_CONTRACT_VERSION,
            "horizon": p2.TARGET_HORIZON,
            "featureContractVersion": p2.FEATURE_CONTRACT_VERSION,
            "featureFields": list(FEATURE_FIELDS),
            "modelContractVersion": p2.MODEL_CONTRACT_VERSION,
            "modelType": "DETERMINISTIC_STANDARD_LIBRARY_LOGISTIC_REGRESSION",
            "probabilityLabelAllowed": False,
        },
        "counts": {
            "decisionRowsInPhase3ModelCohort": len(decision_rows),
            "outcomeRowsInPhase3ModelCohort": len(outcome_rows),
            "validInputFeatureObservations": len(feature_rows),
            "validProspectiveModelForecasts": forecast_counts["validProspectiveModelForecastCount"],
            "eligibleMaturedDirectionalTargetObservations": target_counts["eligibleMaturedDirectionalTargetObservationCount"],
            "validProspectiveOosPairs": len(oos_rows),
            "costQualifiedObservationsAllP3_03Scopes": cost_counts["costQualifiedObservationCount"],
            "persistedForecastObjects": forecast_counts["persistedForecastObjectCount"],
            "testOnlySyntheticEvidenceCount": 0 if authoritative else len(decision_rows) + len(outcome_rows),
        },
        "populationExclusions": {
            "feature": feature_exclusions,
            "forecast": forecast_counts["forecastExclusionsByReason"],
            "maturedTarget": target_counts["targetExclusionsByReason"],
            "costQualifiedRejoin": cost_counts["costQualifiedJoinExclusionsByReason"],
            "duplicateDecisionIds": duplicate_ids,
            "invalidMarketScoreDecisionCount": regime_invalid_market_score,
        },
        "inputFeatureTemporalStability": feature_report,
        "forecastOutputTemporalStability": forecast_report,
        "baseRateTemporalStability": base_rate_report,
        "brierAndAucTemporalStability": paired_report,
        "netExpectancyTemporalStability": expectancy_report,
        "regimeCompositionTemporalStability": regime_report,
        "chronologyAndLeakageChecks": {
            "decisionTimeOrderingAndStableIdTieBreak": True,
            "noShuffledOrOverlappingCurrentWindows": True,
            "referenceWindowNeverRedefined": True,
            "pointInTimeFeatureChecksReused": True,
            "forecastReplayAndMaturedLabelPurgeReused": walk_report.get("chronologyChecks", {}).get("strictMaturedLabelCutoffEnforced") is True,
            "heldOutForecastVerifiedBeforeOutcome": walk_report.get("chronologyChecks", {}).get("persistedForecastReplayedAgainstFrozenBaseline") is True,
            "outcomeMustFollowDecision": walk_report.get("chronologyChecks", {}).get("heldOutOutcomeMustFollowDecision") is True,
            "authoritativeChronologyObserved": bool(oos_rows),
            "probabilityLabelsPromoted": False,
        },
        "dependencyIdentity": dependencies,
        "upstreamExecutionFingerprints": {
            "p301ReportFingerprint": walk_report.get("reportFingerprint"),
            "p303ReportFingerprint": net_report.get("reportFingerprint"),
        },
        "inputFingerprint": input_fingerprint,
        "knownLimitations": [
            "A complete deterministic comparison window is not a statistical significance test.",
            "The contract defines no drift-severity, alert, model-invalidity, retraining, or promotion threshold.",
            "Sparse outcome and cost-qualified populations may remain unavailable after input-feature windows become measurable.",
        ],
        "explicitNonClaims": [
            "No claim that drift is present or absent.",
            "No predictive-validity, profitability, alpha, trading-edge, or statistical-significance claim.",
            "No retraining recommendation, model invalidation, model replacement, or probability-label promotion.",
        ],
        "pipelineBlockers": pipeline_blockers,
    }
    if authoritative:
        report["database"] = None
    report["reportFingerprint"] = _sha256_bytes(_canonical_json(report).encode("utf-8"))
    return report


def build_model_drift_report(
    decisions: Iterable[dict[str, Any]], outcomes: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """Build a deterministic test-only report; fixtures cannot claim authority."""
    decision_rows = [row for row in decisions if isinstance(row, dict)]
    outcome_rows = [row for row in outcomes if isinstance(row, dict)]
    input_fingerprint = _fingerprint_inputs(decision_rows, outcome_rows)
    return _build_report(
        decision_rows,
        outcome_rows,
        evidence_class=TEST_EVIDENCE_CLASS,
        input_fingerprint=input_fingerprint,
    )


def run_authoritative_validation(path: str | Path = AUTHORITATIVE_DB) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if resolved != AUTHORITATIVE_DB or not resolved.is_file():
        raise ValueError("P3-04 accepts only the canonical local prospective evidence ledger")
    dependencies = _verify_dependencies()
    before = p303._database_snapshot(resolved)
    if before.get("applicationId") != EXPECTED_SQLITE_APPLICATION_ID:
        raise ValueError("wrong P2-03 prospective evidence database identity")
    if str(before.get("integrityCheck") or "").lower() != "ok":
        raise RuntimeError("authoritative prospective database integrity check failed")

    decisions, outcomes, malformed = p301._read_authoritative_rows(resolved)
    walk_report = p301.run_authoritative_validation(resolved)
    net_report = p303.run_authoritative_validation(resolved)
    cost_decisions, cost_outcomes, cost_diagnostics = p303._read_authoritative_rows(resolved)
    after = p303._database_snapshot(resolved)
    if before != after:
        raise RuntimeError("authoritative database or WAL/SHM sidecar changed during P3-04 validation")
    if walk_report.get("database", {}).get("unchanged") is not True:
        raise RuntimeError("P3-01 could not verify unchanged authoritative database")
    if net_report.get("database", {}).get("unchanged") is not True:
        raise RuntimeError("P3-03 could not verify unchanged authoritative database")
    if malformed.get("malformedDecisionRows") or malformed.get("malformedOutcomeRows") or cost_diagnostics:
        malformed_blockers = sorted(
            [f"P3_01_{key.upper()}={value}" for key, value in malformed.items() if value]
            + [f"P3_03_{item}" for item in cost_diagnostics]
        )
    else:
        malformed_blockers = []

    input_fingerprint = _fingerprint_inputs(decisions, outcomes)
    report = _build_report(
        decisions,
        outcomes,
        evidence_class=AUTHORITATIVE_EVIDENCE_CLASS,
        input_fingerprint=input_fingerprint,
        walk_report=walk_report,
        net_report=net_report,
        cost_decisions=cost_decisions,
        cost_outcomes=cost_outcomes,
        dependencies=dependencies,
    )
    report["database"] = {
        "path": str(resolved),
        "before": before,
        "after": after,
        "unchanged": True,
        "readOnly": True,
        "eligibleFeatureObservationCount": report["counts"]["validInputFeatureObservations"],
        "validProspectiveModelForecastCount": report["counts"]["validProspectiveModelForecasts"],
        "eligibleMaturedDirectionalTargetObservationCount": report["counts"]["eligibleMaturedDirectionalTargetObservations"],
        "costQualifiedObservationCount": report["counts"]["costQualifiedObservationsAllP3_03Scopes"],
    }
    if malformed_blockers:
        report["pipelineBlockers"] = sorted(set(report["pipelineBlockers"] + malformed_blockers))
        report["engineeringStatus"] = "BLOCKED"
        report["temporalStabilityPipelineStatus"] = "NOT READY"
        report["authoritativeDriftEvidence"] = "BLOCKED — MALFORMED AUTHORITATIVE LEDGER INPUT"
    report.pop("reportFingerprint", None)
    report["reportFingerprint"] = _sha256_bytes(_canonical_json(report).encode("utf-8"))
    return report


def main() -> int:
    report = run_authoritative_validation()
    print(_canonical_json(report))
    return 0 if report["temporalStabilityPipelineStatus"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
