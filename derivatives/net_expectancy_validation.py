"""Read-only P3-03 net-expectancy analysis over authoritative P2-01/P2-02 rows."""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from derivatives.execution_costs import CONTRACTS as P0B_CONTRACTS
from derivatives.execution_costs import CONTRACT_VERSION as P0B_CONTRACT_VERSION
from derivatives import walk_forward_validation as p301
from scripts import p204_score_bucket_performance as p204
from scripts import p205_regime_performance as p205


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_DB = (ROOT / "data" / "p203-prospective-ledger.sqlite3").resolve()
CONTRACT_PATH = ROOT / "docs" / "P3_03_NET_EXPECTANCY_VALIDATION_CONTRACT.md"
CONTRACT_ID = "P3_03_NET_EXPECTANCY_VALIDATION_V1"
CONTRACT_SHA256 = "056A9216E693E6E2CF2C403C988B4624C81ED4CF7110314E1C8C8E7F3E6BA058"
REPORT_VERSION = "P3_03_NET_EXPECTANCY_VALIDATION_V1"
OUTCOME_SCHEMA_VERSION = "P2_02_OUTCOME_V1"
OUTCOME_EVALUATION_CONTRACT_VERSION = "P2_02_DIRECTIONAL_OUTCOME_V1"
TARGET_HORIZON = "T+1"
EXPECTED_SQLITE_APPLICATION_ID = 0x50323033
AUTHORITATIVE_EVIDENCE_CLASS = "AUTHORITATIVE_PROSPECTIVE_LEDGER"
TEST_EVIDENCE_CLASS = "SYNTHETIC_TEST_ONLY"

_EXPECTED_DEPENDENCIES = {
    "phase3Contract": (ROOT / "docs" / "PHASE3_MODEL_VALIDATION_CONTRACT.md", "43EBCAD66CD8267C07BCA2419FBBCDECA066E6195EECF1E4AC782FD5954BBC57"),
    "p302Contract": (ROOT / "docs" / "P3_02_REGIME_CONDITIONED_VALIDATION_CONTRACT.md", "EE105670157843B9F90AFC0467B17D2A5B9C19551E4E475C5F693FF055D06629"),
    "p205Contract": (ROOT / "docs" / "P2_05_REGIME_PERFORMANCE_CONTRACT.md", "E65588E9C771A06B6EE51BCCEFA0351033420824E77969092A875AC03EDD11D2"),
    "p301Implementation": (ROOT / "derivatives" / "walk_forward_validation.py", "971F68D5B342384A5F4C74B9F0F0C398F54375EBD8C71C3D3F938C435081E3ED"),
    "p302Implementation": (ROOT / "derivatives" / "regime_conditioned_validation.py", "07CBA886378F7CAEE6328A3C059E9F6B3E8ED02AD46D4970668E3862F0DAE8C7"),
    "p205Implementation": (ROOT / "scripts" / "p205_regime_performance.py", "FC4E5B9DFEF9B945E78CE1410C6E58CD84137578A98323E06C9EA3B9412DDA7A"),
    "p204Closure": (ROOT / "docs" / "P2_04_FORMAL_CLOSURE.md", "E2E7CB55F53C17F876AA882336FEEC69F15A8CAF71217ABBE2CC52C171528962"),
    "p204Implementation": (ROOT / "scripts" / "p204_score_bucket_performance.py", "F9522950422264EDD4BA3CBF4AC87D5F0D59E5F27C945EE1B2CB558CC46D7E6B"),
    "p202Implementation": (ROOT / "derivatives_store.py", "D49B0E4FBCD463472394CE321D37D53C7CD5EBDE34C6266015B2B1317062D092"),
    "p202Regression": (ROOT / "regression" / "test_p2_02_outcome_evaluation.py", "47D269F79C1BCC6F266B8EC5834EEEF3294D147926F94DE51BD51BF204854D0F"),
    "p0bCostImplementation": (ROOT / "derivatives" / "execution_costs.py", "DD16F12610FE789D28386A476CAF319C4F6C3DB0440E0C8618FF54BE7A219D28"),
}


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


def _verify_dependencies() -> dict[str, dict[str, str]]:
    expected = {"p303Contract": (CONTRACT_PATH, CONTRACT_SHA256), **_EXPECTED_DEPENDENCIES}
    identities: dict[str, dict[str, str]] = {}
    for name, (path, expected_hash) in expected.items():
        if not path.is_file():
            raise FileNotFoundError(f"frozen P3-03 dependency is missing: {path}")
        actual = _sha256_file(path).upper()
        if actual != expected_hash:
            raise RuntimeError(f"frozen P3-03 dependency hash mismatch: {name}")
        identities[name] = {"path": str(path.relative_to(ROOT)), "sha256": actual.lower()}
    return identities


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _number(value: Any) -> float | None:
    return float(value) if _finite_number(value) else None


def _aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        return None
    return result.astimezone(timezone.utc)


def _close(left: float, right: float, *, currency: bool = False) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-9 if currency else 1e-12)


def _parse_json_object(raw: Any, label: str, diagnostics: list[str]) -> dict[str, Any]:
    if not isinstance(raw, str):
        diagnostics.append(f"{label}:NOT_JSON_TEXT")
        return {}

    def reject_constant(value: str) -> None:
        raise ValueError(f"nonstandard JSON numeric constant {value}")

    try:
        value = json.loads(raw, parse_constant=reject_constant)
    except (TypeError, ValueError, json.JSONDecodeError):
        diagnostics.append(f"{label}:INVALID_JSON")
        return {}
    if not isinstance(value, dict):
        diagnostics.append(f"{label}:NOT_OBJECT")
        return {}

    def finite_tree(item: Any) -> bool:
        if isinstance(item, float):
            return math.isfinite(item)
        if isinstance(item, dict):
            return all(finite_tree(key) and finite_tree(child) for key, child in item.items())
        if isinstance(item, list):
            return all(finite_tree(child) for child in item)
        return True

    if not finite_tree(value):
        diagnostics.append(f"{label}:NONFINITE_JSON_NUMBER")
        return {}
    return value


def _read_authoritative_rows(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    diagnostics: list[str] = []
    uri = path.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        decision_columns = {row[1] for row in connection.execute("PRAGMA table_info(decision_ledger)")}
        outcome_columns = {row[1] for row in connection.execute("PRAGMA table_info(decision_outcome)")}
        required_decision = {
            "decision_id", "target_symbol", "decision_time", "market_as_of", "instrument",
            "decision_output_json", "evidence_score", "data_quality_score", "execution_cost_assumptions_json",
        }
        required_outcome = {
            "decision_id", "evaluation_horizon", "evaluation_time", "status", "gross_return",
            "execution_cost", "net_return", "market_observations_json", "cost_adjusted_result_json",
        }
        if not required_decision.issubset(decision_columns) or not required_outcome.issubset(outcome_columns):
            raise RuntimeError("authoritative P2-01/P2-02 schema does not satisfy the frozen P3-03 input contract")
        decisions = [dict(row) for row in connection.execute(
            "SELECT decision_id,target_symbol,decision_time,market_as_of,instrument,decision_output_json,"
            "evidence_score,data_quality_score,execution_cost_assumptions_json "
            "FROM decision_ledger ORDER BY decision_time,decision_id"
        )]
        outcomes = [dict(row) for row in connection.execute(
            "SELECT decision_id,evaluation_horizon,evaluation_time,status,gross_return,execution_cost,net_return,"
            "market_observations_json,cost_adjusted_result_json "
            "FROM decision_outcome ORDER BY evaluation_time,decision_id,evaluation_horizon"
        )]

    for row in decisions:
        decision_id = str(row.get("decision_id") or "UNKNOWN")
        row["decision_output"] = _parse_json_object(row.pop("decision_output_json"), f"decision:{decision_id}:decision_output", diagnostics)
        row["execution_cost_assumptions"] = _parse_json_object(row.pop("execution_cost_assumptions_json"), f"decision:{decision_id}:cost_snapshot", diagnostics)
    for row in outcomes:
        decision_id = str(row.get("decision_id") or "UNKNOWN")
        stored = _parse_json_object(row.pop("market_observations_json"), f"outcome:{decision_id}:observations", diagnostics)
        metadata = stored.get("metadata")
        if not isinstance(metadata, dict):
            diagnostics.append(f"outcome:{decision_id}:metadata:NOT_OBJECT")
            metadata = {}
        row["outcome_metadata"] = metadata
        row["cost_adjusted_result"] = _parse_json_object(row.pop("cost_adjusted_result_json"), f"outcome:{decision_id}:cost_result", diagnostics)
    return decisions, outcomes, diagnostics


def _database_snapshot(path: Path) -> dict[str, Any]:
    snapshot = p301._database_snapshot(path)
    snapshot["sidecarFingerprints"] = p205.read_only_fingerprints(path)
    return snapshot


def _relation_indexes(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]]) -> tuple[Counter[str], Counter[tuple[str, str]], dict[str, dict[str, Any]]]:
    decision_counts = Counter(str(row.get("decision_id") or "") for row in decisions)
    outcome_counts = Counter((str(row.get("decision_id") or ""), str(row.get("evaluation_horizon") or "").strip().upper()) for row in outcomes)
    decision_by_id = {
        str(row.get("decision_id")): row for row in decisions
        if row.get("decision_id") and decision_counts[str(row.get("decision_id"))] == 1
    }
    return decision_counts, outcome_counts, decision_by_id


def _eligibility_reason(
    outcome: dict[str, Any], decision: dict[str, Any] | None, decision_counts: Counter[str],
    outcome_counts: Counter[tuple[str, str]],
) -> str | None:
    decision_id = str(outcome.get("decision_id") or "")
    horizon = str(outcome.get("evaluation_horizon") or "").strip().upper()
    if not decision_id or decision_counts.get(decision_id, 0) == 0:
        return "ORPHAN_OUTCOME"
    if decision_counts.get(decision_id, 0) != 1:
        return "DUPLICATE_DECISION_ID"
    if outcome_counts[(decision_id, horizon)] != 1:
        return "DUPLICATE_OUTCOME_ASSOCIATION"
    if horizon != TARGET_HORIZON:
        return "NON_T1_HORIZON"
    metadata = outcome.get("outcome_metadata") if isinstance(outcome.get("outcome_metadata"), dict) else {}
    if metadata.get("decisionId") is not None and str(metadata.get("decisionId")) != decision_id:
        return "OUTCOME_DECISION_ID_METADATA_MISMATCH"
    if metadata.get("horizon") is not None and str(metadata.get("horizon")).strip().upper() != horizon:
        return "OUTCOME_HORIZON_METADATA_MISMATCH"
    if p204.outcome_status_metadata_mismatch(outcome):
        return "OUTCOME_STATUS_METADATA_MISMATCH"
    status = p204.normalize_outcome_status(outcome)
    if status != "EVALUATED":
        return f"OUTCOME_NOT_EVALUATED:{status}"
    if not p204.outcome_status_basis_compatible(outcome):
        return "INCOMPATIBLE_OUTCOME_STATUS_BASIS"
    if str(metadata.get("evaluationBasis") or "UNKNOWN").strip().upper() != "DIRECTIONAL_RETURN":
        return "BASIS_MISMATCH"
    if metadata.get("outcomeSchemaVersion") != OUTCOME_SCHEMA_VERSION or metadata.get("evaluationContractVersion") != OUTCOME_EVALUATION_CONTRACT_VERSION:
        return "OUTCOME_CONTRACT_VERSION_MISMATCH"
    if decision is None:
        return "ORPHAN_OUTCOME"
    output = decision.get("decision_output") if isinstance(decision.get("decision_output"), dict) else {}
    direction = str(output.get("executionDirection") or "UNAVAILABLE").strip().upper()
    state = str(output.get("decisionState") or "UNKNOWN").strip().upper()
    if output.get("decisionEligible") is not True:
        return "DECISION_NOT_EXPLICITLY_ELIGIBLE"
    if direction not in {"LONG", "SHORT"} or state != direction:
        return "NO_VALID_DIRECTIONAL_DECISION"
    decision_time = _aware_datetime(decision.get("decision_time"))
    evaluation_time = _aware_datetime(outcome.get("evaluation_time"))
    if decision_time is None:
        return "INVALID_DECISION_TIMESTAMP"
    if evaluation_time is None:
        return "INVALID_EVALUATION_TIMESTAMP"
    if evaluation_time <= decision_time:
        return "EVALUATION_NOT_AFTER_DECISION"
    if not _finite_number(metadata.get("decisionAlignedReturn")) or not _finite_number(outcome.get("gross_return")):
        return "MISSING_OR_INVALID_GROSS_DIRECTIONAL_RETURN"
    if not _close(float(metadata["decisionAlignedReturn"]), float(outcome["gross_return"])):
        return "GROSS_RETURN_CONFLICT"
    return None


def _cost_reason(decision: dict[str, Any], outcome: dict[str, Any]) -> str | None:
    instrument = str(decision.get("instrument") or "").strip().upper()
    if instrument not in P0B_CONTRACTS:
        return "UNSUPPORTED_COST_INSTRUMENT"
    expected = P0B_CONTRACTS[instrument]
    decision_cost = decision.get("execution_cost_assumptions") if isinstance(decision.get("execution_cost_assumptions"), dict) else {}
    cost = outcome.get("cost_adjusted_result") if isinstance(outcome.get("cost_adjusted_result"), dict) else {}
    metadata = outcome.get("outcome_metadata") if isinstance(outcome.get("outcome_metadata"), dict) else {}
    if decision_cost.get("status") != "AVAILABLE" or decision_cost.get("contractVersion") != P0B_CONTRACT_VERSION:
        return "DECISION_TIME_P0B_COST_CONTRACT_UNAVAILABLE"
    if str(decision_cost.get("instrumentSymbol") or "").strip().upper() != instrument:
        return "DECISION_COST_INSTRUMENT_MISMATCH"
    if decision_cost.get("currency") != expected["currency"]:
        return "DECISION_COST_CURRENCY_MISMATCH"
    if cost.get("status") != "AVAILABLE" or cost.get("contractVersion") != P0B_CONTRACT_VERSION:
        return "OUTCOME_P0B_COST_RESULT_UNAVAILABLE"
    if str(cost.get("instrumentSymbol") or "").strip().upper() != instrument:
        return "OUTCOME_COST_INSTRUMENT_MISMATCH"
    if cost.get("currency") != expected["currency"]:
        return "OUTCOME_COST_CURRENCY_MISMATCH"
    if metadata.get("strategyEvaluationBasis") != "STRATEGY_RETURN":
        return "STRATEGY_RETURN_BASIS_MISSING"
    try:
        strategy_return_matches = (
            isinstance(metadata.get("strategyReturn"), dict)
            and _canonical_json(metadata["strategyReturn"]) == _canonical_json(cost)
        )
    except (TypeError, ValueError):
        strategy_return_matches = False
    if not strategy_return_matches:
        return "STRATEGY_RETURN_METADATA_MISMATCH"

    numbers = {
        name: _number(cost.get(name)) for name in (
            "grossPnl", "commissionCost", "taxCost", "slippageCost", "otherCost",
            "totalCost", "netPnl", "normalizedCostPct", "grossDirectionalReturnPct", "costAdjustedReturnPct",
        )
    }
    if any(value is None for value in numbers.values()):
        return "MISSING_OR_INVALID_P0B_COST_NUMERIC"
    if any(numbers[name] < 0 for name in ("commissionCost", "taxCost", "slippageCost", "otherCost", "totalCost")):
        return "NEGATIVE_P0B_COST"
    components = math.fsum(numbers[name] for name in ("commissionCost", "taxCost", "slippageCost", "otherCost"))
    if not _close(numbers["totalCost"], components, currency=True):
        return "P0B_COST_COMPONENT_RECONCILIATION_FAILED"
    if not _close(numbers["netPnl"], numbers["grossPnl"] - numbers["totalCost"], currency=True):
        return "P0B_NET_PNL_RECONCILIATION_FAILED"
    if not _close(numbers["costAdjustedReturnPct"], numbers["grossDirectionalReturnPct"] - numbers["normalizedCostPct"]):
        return "P0B_RETURN_RECONCILIATION_FAILED"

    net_return = _number(outcome.get("net_return"))
    execution_cost = _number(outcome.get("execution_cost"))
    aligned_gross = _number((outcome.get("outcome_metadata") or {}).get("decisionAlignedReturn"))
    if net_return is None:
        return "MISSING_OR_INVALID_NET_RETURN"
    if execution_cost is None or execution_cost < 0:
        return "MISSING_OR_INVALID_EXECUTION_COST"
    if not _close(net_return, numbers["costAdjustedReturnPct"] / 100):
        return "PERSISTED_NET_RETURN_MISMATCH"
    if not _close(execution_cost, numbers["totalCost"], currency=True):
        return "PERSISTED_EXECUTION_COST_MISMATCH"
    if aligned_gross is None or not _close(aligned_gross * 100, numbers["grossDirectionalReturnPct"]):
        return "P2_GROSS_RETURN_COST_RESULT_MISMATCH"
    if not _close(float(outcome["gross_return"]), numbers["grossDirectionalReturnPct"] / 100):
        return "PERSISTED_GROSS_RETURN_COST_RESULT_MISMATCH"
    return None


def _round_metric(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, 12)


def _empty_scope(instrument: str) -> dict[str, Any]:
    supported = instrument in P0B_CONTRACTS
    return {
        "instrument": instrument,
        "costContractVersion": P0B_CONTRACT_VERSION if supported else None,
        "currency": P0B_CONTRACTS[instrument]["currency"] if supported else None,
        "aggregationStatus": "SEPARATE_INSTRUMENT_SCOPE" if supported else "SUPPRESSED_UNSUPPORTED_COST_CONTRACT",
        "decisionCount": 0,
        "eligibleEvaluatedDirectionalOutcomeCount": 0,
        "includedSampleCount": 0,
        "positiveReturnCount": 0,
        "negativeReturnCount": 0,
        "zeroReturnCount": 0,
        "winRate": None,
        "averageWin": None,
        "averageLoss": None,
        "netExpectancy": None,
        "expectancyDecomposition": None,
        "minimumNetReturn": None,
        "maximumNetReturn": None,
        "totalExecutionCost": None,
        "averageExecutionCost": None,
        "cumulativeNetReturn": "NOT CALCULATED — POSITION SIZING / OVERLAP SEMANTICS NOT FROZEN",
        "sampleSufficiencyStatus": "NOT DEFINED — DESCRIPTIVE ONLY",
        "statisticalMaturity": "NOT YET MATURE — NO FROZEN P3-03 SUFFICIENCY GATE",
    }


def _build_report(
    decisions: Iterable[dict[str, Any]], outcomes: Iterable[dict[str, Any]], *,
    evidence_class: str, input_fingerprint: str | None = None,
    blocking_diagnostics: list[str] | None = None,
) -> dict[str, Any]:
    dependencies = _verify_dependencies()
    decision_rows = [row for row in decisions if isinstance(row, dict)]
    outcome_rows = [row for row in outcomes if isinstance(row, dict)]
    decision_rows.sort(key=lambda row: (str(row.get("decision_time") or ""), str(row.get("decision_id") or "")))
    outcome_rows.sort(key=lambda row: (str(row.get("evaluation_time") or ""), str(row.get("decision_id") or ""), str(row.get("evaluation_horizon") or "")))
    decision_counts, outcome_counts, decisions_by_id = _relation_indexes(decision_rows, outcome_rows)
    scopes: dict[str, dict[str, Any]] = {}
    for decision in decision_rows:
        instrument = str(decision.get("instrument") or "UNKNOWN").strip().upper() or "UNKNOWN"
        scopes.setdefault(instrument, _empty_scope(instrument))["decisionCount"] += 1

    eligibility_exclusions: Counter[str] = Counter()
    cost_exclusions: Counter[str] = Counter()
    included: dict[str, list[dict[str, Any]]] = defaultdict(list)
    eligible_directional_count = 0
    eligible_directional_keys: set[tuple[str, str]] = set()
    included_keys: set[tuple[str, str]] = set()
    audit_rows: list[dict[str, Any]] = []
    upstream_contract_conflicts: list[dict[str, Any]] = []

    for outcome in outcome_rows:
        decision_id = str(outcome.get("decision_id") or "")
        horizon = str(outcome.get("evaluation_horizon") or "").strip().upper()
        key = (decision_id, horizon)
        decision = decisions_by_id.get(decision_id)
        outcome_metadata = outcome.get("outcome_metadata") if isinstance(outcome.get("outcome_metadata"), dict) else {}
        raw_status = str(outcome.get("status") or "").strip().upper()
        if (
            raw_status != "EVALUATED"
            and str(outcome_metadata.get("outcomeStatus") or "").strip().upper() == "EVALUATED"
            and outcome_metadata.get("outcomeSchemaVersion") == OUTCOME_SCHEMA_VERSION
            and outcome_metadata.get("evaluationContractVersion") == OUTCOME_EVALUATION_CONTRACT_VERSION
        ):
            upstream_contract_conflicts.append({
                "decisionId": decision_id or None,
                "horizon": horizon or None,
                "persistedStatus": raw_status or None,
                "metadataOutcomeStatus": "EVALUATED",
                "reason": "P2_OUTCOME_STATUS_COLUMN_CONFLICTS_WITH_VERSIONED_METADATA; P2-04 DOES NOT PERMIT STATUS UPGRADE",
            })
        reason = _eligibility_reason(outcome, decision, decision_counts, outcome_counts)
        if reason:
            eligibility_exclusions[reason] += 1
            audit_rows.append({"decisionId": decision_id or None, "horizon": horizon or None, "eligibility": "EXCLUDED", "reason": reason})
            continue

        eligible_directional_count += 1
        eligible_directional_keys.add(key)
        assert decision is not None
        instrument = str(decision.get("instrument") or "UNKNOWN").strip().upper() or "UNKNOWN"
        scope = scopes.setdefault(instrument, _empty_scope(instrument))
        scope["eligibleEvaluatedDirectionalOutcomeCount"] += 1
        cost_reason = _cost_reason(decision, outcome)
        if cost_reason:
            cost_exclusions[cost_reason] += 1
            audit_rows.append({"decisionId": decision_id, "horizon": horizon, "eligibility": "DIRECTIONAL_ELIGIBLE_COST_EXCLUDED", "reason": cost_reason})
            continue

        net_return = float(outcome["net_return"])
        execution_cost = float(outcome["execution_cost"])
        included[instrument].append({"decisionId": decision_id, "horizon": horizon, "netReturn": net_return, "executionCost": execution_cost})
        included_keys.add(key)
        audit_rows.append({"decisionId": decision_id, "horizon": horizon, "eligibility": "INCLUDED_NET_EXPECTANCY", "reason": None})

    for instrument, values in included.items():
        values.sort(key=lambda row: (row["horizon"], row["decisionId"]))
        scope = scopes[instrument]
        returns = [row["netReturn"] for row in values]
        costs = [row["executionCost"] for row in values]
        positive = [value for value in returns if value > 0]
        negative = [value for value in returns if value < 0]
        zero_count = len(returns) - len(positive) - len(negative)
        n = len(returns)
        expectancy = math.fsum(returns) / n if n else None
        average_win = math.fsum(positive) / len(positive) if positive else None
        average_loss = math.fsum(negative) / len(negative) if negative else None
        decomposition = None
        if expectancy is not None:
            positive_contribution = len(positive) / n * (average_win or 0.0)
            negative_contribution = len(negative) / n * (average_loss or 0.0)
            zero_contribution = zero_count / n * 0.0
            decomposed = math.fsum((positive_contribution, negative_contribution, zero_contribution))
            if not _close(expectancy, decomposed):
                raise RuntimeError("net expectancy decomposition failed its frozen arithmetic identity")
            decomposition = {
                "positiveContribution": _round_metric(positive_contribution),
                "negativeContribution": _round_metric(negative_contribution),
                "zeroContribution": 0.0,
                "reconciledExpectancy": _round_metric(decomposed),
            }
        scope.update({
            "includedSampleCount": n,
            "positiveReturnCount": len(positive),
            "negativeReturnCount": len(negative),
            "zeroReturnCount": zero_count,
            "winRate": _round_metric(len(positive) / (len(positive) + len(negative))) if positive or negative else None,
            "averageWin": _round_metric(average_win),
            "averageLoss": _round_metric(average_loss),
            "netExpectancy": _round_metric(expectancy),
            "expectancyDecomposition": decomposition,
            "minimumNetReturn": _round_metric(min(returns)),
            "maximumNetReturn": _round_metric(max(returns)),
            "totalExecutionCost": _round_metric(math.fsum(costs)),
            "averageExecutionCost": _round_metric(math.fsum(costs) / n),
        })

    candidate_decisions_without_t1 = 0
    for decision in decision_rows:
        output = decision.get("decision_output") if isinstance(decision.get("decision_output"), dict) else {}
        state = str(output.get("decisionState") or "UNKNOWN").strip().upper()
        direction = str(output.get("executionDirection") or "UNAVAILABLE").strip().upper()
        if output.get("decisionEligible") is True and state in {"LONG", "SHORT"} and direction == state:
            decision_id = str(decision.get("decision_id") or "")
            if not any(row[0] == decision_id and row[1] == TARGET_HORIZON for row in outcome_counts):
                candidate_decisions_without_t1 += 1

    blocked = sorted(set(blocking_diagnostics or []))
    if upstream_contract_conflicts:
        blocked.append("P2-02/P2-04 OUTCOME STATUS CONTRACT CONFLICT")
    blocked = sorted(set(blocked))
    pipeline_block_reason = (
        "BLOCKED — MALFORMED LEDGER INPUT" if blocking_diagnostics else
        "BLOCKED — P2-02/P2-04 CONTRACT CONFLICT" if upstream_contract_conflicts else None
    )
    status = "BLOCKED" if blocked else "READY"
    report: dict[str, Any] = {
        "reportVersion": REPORT_VERSION,
        "contract": {"id": CONTRACT_ID, "sha256": CONTRACT_SHA256.lower()},
        "dependencyIdentity": dependencies,
        "engineeringStatus": "BLOCKED" if blocked else "PASS",
        "validationPipelineStatus": pipeline_block_reason or "VALIDATION PIPELINE READY",
        "authoritativeEvidenceClass": evidence_class,
        "authoritative": evidence_class == AUTHORITATIVE_EVIDENCE_CLASS,
        "inputCounts": {
            "decisionCount": len(decision_rows),
            "outcomeCount": len(outcome_rows),
            "eligibleEvaluatedDirectionalT1OutcomeCount": eligible_directional_count if evidence_class == AUTHORITATIVE_EVIDENCE_CLASS else 0,
            "costQualifiedExpectancySampleCount": len(included_keys) if evidence_class == AUTHORITATIVE_EVIDENCE_CLASS else 0,
            "candidateDirectionalDecisionsWithoutT1Outcome": candidate_decisions_without_t1 if evidence_class == AUTHORITATIVE_EVIDENCE_CLASS else 0,
        },
        "eligibilityFunnel": {
            "eligibleEvaluatedDirectionalT1OutcomeCount": eligible_directional_count,
            "costQualifiedNetExpectancyCount": len(included_keys),
            "eligibilityExclusionsByReason": dict(sorted(eligibility_exclusions.items())),
            "costExclusionsByReason": dict(sorted(cost_exclusions.items())),
        },
        "upstreamContractConflicts": upstream_contract_conflicts,
        "upstreamProducerCompatibility": {
            "status": "PASS — CANONICAL OUTCOME STATUS AND LEGACY STATUS ARE SEPARATED",
            "evidence": "For the exact P2_02_OUTCOME_V1 / P2_02_DIRECTIONAL_OUTCOME_V1 producer contract, record_decision_outcome persists outcomeStatus in the status column and preserves the evaluator's AVAILABLE/PARTIAL value in legacyStatus metadata. data_quality_status retains its independent input. Unversioned AVAILABLE/PARTIAL rows are not promoted.",
            "behavior": "P2-04/P3-03 continue requiring persisted status=EVALUATED with matching metadata; legacy or conflicting rows remain fail-closed.",
        },
        "expectancyAvailability": "AVAILABLE" if included_keys and not blocked else "NOT AVAILABLE" if not blocked else "BLOCKED",
        "statisticalMaturity": "NOT YET MATURE — NO FROZEN P3-03 SUFFICIENCY GATE",
        "sampleSufficiencyStatus": "NOT DEFINED — DESCRIPTIVE ONLY",
        "aggregationContract": {
            "primaryMetric": "arithmetic mean of persisted decision_outcome.net_return",
            "returnUnit": "fraction of decision-time entry notional; costAdjustedReturnPct / 100",
            "scope": "separate instrument + P0B_FUTURES_COST_V1 + currency",
            "crossInstrumentAggregation": "SUPPRESSED",
            "regimeConditioning": "NOT DEFINED; P2-05/P3-02 semantics unchanged and not used",
            "cumulativeReturn": "NOT CALCULATED — POSITION SIZING / OVERLAP SEMANTICS NOT FROZEN",
        },
        "overallRealizedMetrics": "NOT AVAILABLE — NO COST-QUALIFIED AUTHORITATIVE SAMPLE" if not included_keys else "REPORTED ONLY IN COMPATIBLE INSTRUMENT SCOPES",
        "scopes": [scopes[key] for key in sorted(scopes)],
        "eligibilityAudit": audit_rows,
        "chronologyChecks": {
            "timezoneAwareDecisionAndEvaluationTimesRequired": True,
            "evaluationMustStrictlyFollowDecision": True,
            "observedEligiblePairs": eligible_directional_count,
            "status": "NOT OBSERVED — NO ELIGIBLE EVALUATED T1 OUTCOMES" if eligible_directional_count == 0 else "PASS",
        },
        "statisticalNonClaims": [
            "No claim of positive expectancy, profitability, alpha, trading edge, statistical significance, future performance, or model superiority.",
            "No claim of regime superiority or probability calibration.",
            "probabilityLabelAllowed remains false; P3-03 does not authorize probability-label promotion.",
        ],
        "knownLimitations": [
            "No cumulative return is computed because position sizing, reinvestment, and overlapping-position semantics are not frozen.",
            "No P3-03-specific statistical sample threshold is defined; metrics are descriptive only.",
        ],
        "blockingDiagnostics": blocked,
        "inputFingerprint": input_fingerprint or _sha256_bytes(_canonical_json({"decisions": decision_rows, "outcomes": outcome_rows}).encode("utf-8")),
    }
    if status == "BLOCKED":
        report["reportStatus"] = status
    report["reportFingerprint"] = _sha256_bytes(_canonical_json(report).encode("utf-8"))
    return report


def build_net_expectancy_report(decisions: Iterable[dict[str, Any]], outcomes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Build a deterministic, test-only report. Fixtures can never claim authority."""
    return _build_report(decisions, outcomes, evidence_class=TEST_EVIDENCE_CLASS)


def run_authoritative_validation(path: str | Path = AUTHORITATIVE_DB) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    if resolved != AUTHORITATIVE_DB or not resolved.is_file():
        raise ValueError("P3-03 accepts only the canonical local prospective Decision/Outcome ledger")
    before = _database_snapshot(resolved)
    if before["applicationId"] != EXPECTED_SQLITE_APPLICATION_ID:
        raise ValueError("wrong P2-03 prospective evidence database identity")
    if str(before["integrityCheck"]).lower() != "ok":
        raise RuntimeError("authoritative prospective database integrity check failed")
    decisions, outcomes, diagnostics = _read_authoritative_rows(resolved)
    input_fingerprint = _sha256_bytes(_canonical_json({"decisions": decisions, "outcomes": outcomes}).encode("utf-8"))
    report = _build_report(
        decisions,
        outcomes,
        evidence_class=AUTHORITATIVE_EVIDENCE_CLASS,
        input_fingerprint=input_fingerprint,
        blocking_diagnostics=diagnostics,
    )
    after = _database_snapshot(resolved)
    before_sides = before.pop("sidecarFingerprints")
    after_sides = after.pop("sidecarFingerprints")
    if before != after or before_sides != after_sides:
        raise RuntimeError("authoritative database or WAL/SHM sidecar changed during P3-03 validation")
    if diagnostics:
        report["engineeringStatus"] = "BLOCKED"
        report["validationPipelineStatus"] = "BLOCKED — MALFORMED LEDGER INPUT"
        report["expectancyAvailability"] = "BLOCKED"
        report["reportStatus"] = "BLOCKED"
    report["database"] = {
        "path": str(resolved),
        "before": before | {"sidecarFingerprints": before_sides},
        "after": after | {"sidecarFingerprints": after_sides},
        "unchanged": True,
        "readOnly": True,
    }
    report["database"]["before"]["eligibleEvaluatedDirectionalT1OutcomeCount"] = report["inputCounts"]["eligibleEvaluatedDirectionalT1OutcomeCount"]
    report["database"]["after"]["eligibleEvaluatedDirectionalT1OutcomeCount"] = report["inputCounts"]["eligibleEvaluatedDirectionalT1OutcomeCount"]
    report.pop("reportFingerprint", None)
    report["reportFingerprint"] = _sha256_bytes(_canonical_json(report).encode("utf-8"))
    return report


def main() -> int:
    report = run_authoritative_validation()
    print(_canonical_json(report))
    return 0 if report["validationPipelineStatus"] == "VALIDATION PIPELINE READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
