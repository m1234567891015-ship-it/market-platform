"""One-shot, provider-backed P2-03 prospective evidence collection.

This runner is intentionally local and fixed to the non-production evidence
database. It evaluates due T+1 outcomes first, then asks the existing analysis
API to capture at most one current TX decision through the normal Ledger path.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DB = (REPO_ROOT / "data" / "p203-prospective-ledger.sqlite3").resolve()
EXPECTED_APP_ID = 0x50323033
INSTRUMENT = "TX"
HORIZON = "T+1"
MANIFEST_LABELS = {"P2_03_EVIDENCE_CAPTURE", "NON_PRODUCTION", "PROSPECTIVE_ONLY"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_evidence_db(path: str | Path, manifest_path: str | Path | None = None) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved != EXPECTED_DB or any(token in str(resolved).lower() for token in ("prod", "render", "remote")):
        raise ValueError("refusing non-canonical or production-like P2-03 evidence path")
    if not resolved.is_file():
        raise ValueError("P2-03 evidence database does not exist")
    manifest = Path(manifest_path).resolve() if manifest_path else resolved.with_suffix(".manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    flattened = {str(value).upper() for value in payload.values() if isinstance(value, (str, int, float))}
    if not MANIFEST_LABELS.issubset(flattened):
        raise ValueError("evidence manifest identity is incomplete")
    uri = f"file:{resolved.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        app_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if app_id != EXPECTED_APP_ID or not {"decision_ledger", "decision_outcome"}.issubset(tables):
        raise ValueError("wrong P2-03 evidence database identity")
    return resolved


def database_snapshot(path: Path) -> dict[str, Any]:
    uri = f"file:{path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        app_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
        table_names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        counts = {name: int(connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]) for name in table_names}
        schema_rows = connection.execute(
            "SELECT type,name,tbl_name,COALESCE(sql,'') FROM sqlite_master "
            "WHERE type IN ('table','index','trigger','view') ORDER BY type,name"
        ).fetchall()
    return {
        "path": str(path), "applicationId": app_id, "sizeBytes": path.stat().st_size,
        "sha256": _sha256(path), "counts": counts,
        "schemaSha256": hashlib.sha256(json.dumps(schema_rows, separators=(",", ":")).encode()).hexdigest(),
    }


def observation_provenance(row: dict[str, Any], observed_at: str) -> dict[str, Any] | None:
    market_date = str(row.get("time") or row.get("date") or "").strip()
    try:
        datetime.strptime(market_date, "%Y-%m-%d")
    except ValueError:
        return None
    close = row.get("close")
    if not isinstance(close, (int, float)) or close <= 0:
        return None
    return {
        "date": market_date, "market_as_of": market_date, "observed_at": observed_at,
        "open": row.get("open"), "high": row.get("high"), "low": row.get("low"), "close": close,
        "provider": "TAIFEX", "source": "TAIFEX official futures daily market observations",
        "sourceRole": "OUTCOME_PRICE", "sourceLink": "https://www.taifex.com.tw/cht/3/futDailyMarketReport",
    }


def evaluate_due_outcomes(store: Any, observations: list[dict[str, Any]], evaluation_time: str) -> dict[str, Any]:
    """Persist only mature, provenance-backed eligible directional outcomes."""
    from derivatives.probability_forecast import TARGET_HORIZON, valid_oos_pair

    checked = evaluated = pending = skipped = 0
    normalized = [row for row in observations if isinstance(row, dict) and row.get("provider") == "TAIFEX"
                 and row.get("sourceRole") == "OUTCOME_PRICE" and row.get("market_as_of")]
    for decision in store.list_decisions(target_symbol=INSTRUMENT, limit=1000):
        checked += 1
        decision_id = str(decision.get("decision_id") or "")
        if not decision_id or store.get_decision_outcome(decision_id, TARGET_HORIZON):
            continue
        metadata = decision.get("source_metadata") if isinstance(decision.get("source_metadata"), dict) else {}
        decision_source = metadata.get("source_provenance")
        if (
            not isinstance(decision_source, dict)
            or str(decision_source.get("status") or "").upper() == "UNKNOWN"
            or not (decision_source.get("provider") or decision_source.get("source"))
        ):
            skipped += 1
            continue
        if decision.get("decisionState") not in {"LONG", "SHORT"} or decision.get("decisionEligible") is not True:
            skipped += 1
            continue
        market_date = str(decision.get("market_as_of") or "")
        future_rows = [row for row in normalized if str(row["market_as_of"]) > market_date]
        # P2-02 is immutable. Do not save PENDING for an immature horizon,
        # because that row cannot later be upgraded without violating its contract.
        if not future_rows:
            pending += 1
            continue
        result = store.evaluate_decision_outcome(
            decision_id, TARGET_HORIZON, evaluation_time, future_rows, horizon_matured=True
        )
        if result.get("outcome_status") == "EVALUATED":
            evaluated += 1
    pairs = 0
    for decision in store.list_decisions(target_symbol=INSTRUMENT, limit=1000):
        outcome = store.get_decision_outcome(str(decision.get("decision_id") or ""), TARGET_HORIZON)
        if outcome and valid_oos_pair(decision, outcome, horizon=TARGET_HORIZON):
            pairs += 1
    return {"checked": checked, "evaluated": evaluated, "pending": pending, "skipped": skipped, "validPairs": pairs}


def collect_counts(store: Any) -> dict[str, int]:
    from derivatives.probability_forecast import TARGET_HORIZON, derive_directional_target, valid_oos_pair

    decisions = store.list_decisions(target_symbol=INSTRUMENT, limit=1000)
    outcomes = 0
    eligible_training = 0
    eligible_positive = 0
    eligible_negative = 0
    persisted_forecasts = 0
    mature_forecasts = 0
    pairs = positives = negatives = 0
    for decision in decisions:
        forecast = (decision.get("decision_output") or {}).get("probabilityForecast")
        if isinstance(forecast, dict):
            persisted_forecasts += 1
        outcome = store.get_decision_outcome(str(decision.get("decision_id") or ""), TARGET_HORIZON)
        if not outcome:
            continue
        outcomes += 1
        target = derive_directional_target(decision, outcome, horizon=TARGET_HORIZON)
        if target.get("eligible"):
            eligible_training += 1
            if target.get("value") == 1:
                eligible_positive += 1
            elif target.get("value") == 0:
                eligible_negative += 1
        if isinstance(forecast, dict) and outcome.get("outcome_status") == "EVALUATED":
            mature_forecasts += 1
        pair = valid_oos_pair(decision, outcome, horizon=TARGET_HORIZON)
        if pair:
            pairs += 1
            positives += int(pair["outcome"] == 1)
            negatives += int(pair["outcome"] == 0)
    latest = decisions[-1] if decisions else {}
    latest_state = str(latest.get("decisionState") or "UNKNOWN").upper()
    latest_eligible = latest.get("decisionEligible") is True and latest_state in {"LONG", "SHORT"}
    prior_rows = store.list_probability_training_rows(TARGET_HORIZON, str(latest.get("decision_time") or "")) if latest else []
    prior_targets = [derive_directional_target(row.get("decision", {}), row.get("outcome", {}), horizon=TARGET_HORIZON)
                     for row in prior_rows]
    prior_eligible = [target for target in prior_targets if target.get("eligible")]
    prior_positive = sum(target.get("value") == 1 for target in prior_eligible)
    prior_negative = sum(target.get("value") == 0 for target in prior_eligible)
    forecast_capable = latest_eligible and len(prior_eligible) >= 30 and prior_positive > 0 and prior_negative > 0
    return {
        "totalDecisions": len(decisions), "totalOutcomes": outcomes,
        "eligibleTrainingRows": eligible_training, "eligibleTrainingPositive": eligible_positive,
        "eligibleTrainingNegative": eligible_negative, "currentTrainingHistoryRows": len(prior_eligible),
        "currentForecastCapable": bool(forecast_capable),
        "persistedProbabilityForecasts": persisted_forecasts,
        "matureProspectiveForecasts": mature_forecasts, "validProspectiveOosPairs": pairs,
        "positiveOosLabels": positives, "negativeOosLabels": negatives,
    }


def decision_exists_for_market_session(store: Any, market_as_of: str) -> dict[str, Any] | None:
    for decision in store.list_decisions(target_symbol=INSTRUMENT, limit=1000):
        if str(decision.get("market_as_of") or "") == str(market_as_of or ""):
            return decision
    return None


def _current_market_snapshot() -> dict[str, Any] | None:
    import fetchers

    return fetchers.fetch_taifex_latest_futures_market_snapshot(INSTRUMENT)


def _provider_outcome_observations() -> tuple[list[dict[str, Any]], str | None]:
    import fetchers

    candles = fetchers.fetch_taifex_futures_price_candles(INSTRUMENT, max_observations=30)
    observed_at = datetime.now(timezone.utc).isoformat()
    output = []
    for candle in candles:
        row = observation_provenance(candle, observed_at)
        if row:
            output.append(row)
    # The existing fetcher obtains its data only from TAIFEX download/daily
    # report paths. Cache/source details are not surfaced by that function;
    # the report therefore records its official provider-level provenance.
    return output, observed_at if output else None


def run_once() -> dict[str, Any]:
    if os.environ.get("DERIVATIVES_DB_PATH") and Path(os.environ["DERIVATIVES_DB_PATH"]).expanduser().resolve() != EXPECTED_DB:
        raise ValueError("DERIVATIVES_DB_PATH must resolve to the canonical local P2-03 evidence database")
    os.environ["DERIVATIVES_DB_PATH"] = str(EXPECTED_DB)
    os.environ["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
    path = validate_evidence_db(EXPECTED_DB)
    before = database_snapshot(path)
    sys.path.insert(0, str(REPO_ROOT))

    # Import only after process-local evidence DB wiring is established.
    import app
    import fetchers
    from derivatives.probability_forecast import TARGET_HORIZON
    from derivatives_store import DerivativesStore

    store = DerivativesStore(path)
    # Identity/schema were verified read-only; skip initialize() so the runner
    # cannot perform an automatic schema migration.
    store._initialized = True
    configured_store = app.DerivativesStore(os.environ["DERIVATIVES_DB_PATH"])
    configured_store._initialized = True
    app.DERIVATIVES_STORE = configured_store

    # Phase 1: request one real provider observation set, then evaluate only
    # already-due decisions. No pending rows are written for immature horizons.
    due_observations, evaluation_time = _provider_outcome_observations()
    phase_one = evaluate_due_outcomes(store, due_observations, evaluation_time or datetime.now(timezone.utc).isoformat())

    # Phase 2: fetch official market date before invoking the existing API.
    snapshot = _current_market_snapshot()
    market_as_of = str((snapshot or {}).get("date") or "").strip()
    if not market_as_of:
        after = database_snapshot(path)
        return {"status": "REAL_CAPTURE_NOT_OBSERVED", "reason": "TAIFEX_MARKET_DATE_UNAVAILABLE",
                "phaseOne": phase_one, "before": before, "after": after, "counts": collect_counts(store)}
    prior = decision_exists_for_market_session(store, market_as_of)
    if prior:
        after = database_snapshot(path)
        return {"status": "DUPLICATE_MARKET_SESSION_SKIPPED", "marketAsOf": market_as_of,
                "existingDecisionId": prior.get("decision_id"), "phaseOne": phase_one,
                "before": before, "after": after, "counts": collect_counts(store)}

    flask_app = app.create_app({"TESTING": True}, derivatives_store=configured_store)
    client = flask_app.test_client()
    response = client.get("/api/ai-analysis?target=TX")
    payload = response.get_json(silent=True) or {}
    body = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    decision_id = str(body.get("decision_id") or body.get("decisionId") or "") if isinstance(body, dict) else ""
    record = store.get_decision(decision_id) if decision_id else None
    if record:
        output = record.get("decision_output") if isinstance(record.get("decision_output"), dict) else {}
        forecast = output.get("probabilityForecast")
        state = record.get("decisionState")
        eligible = record.get("decisionEligible")
        forecast_status = output.get("probabilityForecastStatus")
        item = (record.get("input_snapshot") or {}).get("item") or {}
        source_metadata = record.get("source_metadata") or {}
        source_evidence = {
            "primarySource": item.get("dataSource") or item.get("source"),
            "primarySourceUrl": item.get("sourceUrl"),
            "quoteSource": item.get("quoteSource"),
            "sourceProvenance": source_metadata.get("source_provenance"),
            "qualityStatus": source_metadata.get("data_quality_status"),
            "qualityCoverage": source_metadata.get("quality_coverage"),
            "qualityDimensions": source_metadata.get("data_quality_dimensions"),
        }
    else:
        forecast = None
        state = body.get("decisionState") if isinstance(body, dict) else None
        eligible = body.get("decisionEligible") if isinstance(body, dict) else None
        forecast_status = body.get("probabilityForecastStatus") if isinstance(body, dict) else None
        source_evidence = None

    after = database_snapshot(path)
    if after["schemaSha256"] != before["schemaSha256"]:
        raise RuntimeError("evidence DB schema changed during run; refusing to report success")
    for name, old_count in before["counts"].items():
        delta = after["counts"].get(name, 0) - old_count
        allowed = {"decision_ledger", "decision_outcome", "ai_analysis_report"}
        if delta < 0 or (name not in allowed and delta != 0):
            raise RuntimeError(f"unexpected evidence DB row-count change in {name}: {delta}")
    counts = collect_counts(store)
    return {
        "status": "REAL_CAPTURE_OBSERVED" if record else "REAL_CAPTURE_NOT_OBSERVED",
        "httpStatus": response.status_code,
        "provider": "TAIFEX primary analysis path; Yahoo may be supplemental if existing builder uses it",
        "instrument": INSTRUMENT, "marketAsOf": (record or {}).get("market_as_of") or market_as_of,
        "dataAsOf": (record or {}).get("data_as_of"), "decisionPersisted": bool(record),
        "decisionId": decision_id or None, "decisionState": state,
        "decisionEligible": eligible, "forecastStatus": forecast_status,
        "sourceEvidence": source_evidence,
        "probabilityPersisted": isinstance(forecast, dict), "forecast": forecast,
        "outcomeStatus": "PENDING" if record and not store.get_decision_outcome(decision_id, TARGET_HORIZON) else
                         (store.get_decision_outcome(decision_id, TARGET_HORIZON) or {}).get("outcome_status"),
        "phaseOne": phase_one, "counts": counts, "before": before, "after": after,
        "probabilityLabelAllowed": (record or {}).get("decision_output", {}).get("probabilityLabelAllowed", False),
    }


def main() -> int:
    try:
        report = run_once()
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with a concise reason.
        print(json.dumps({"status": "FAILED_CLOSED", "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
