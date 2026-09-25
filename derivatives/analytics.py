from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from typing import Any

from .calibration import CALIBRATION_STATUS_UNAVAILABLE


DECISION_MODEL_VERSION = "rules-based-derivatives-v1"
DECISION_STRATEGY_VERSION = "derivatives-decision-v1"
MODEL_CONFIDENCE_STATUS_UNAVAILABLE = "UNAVAILABLE"
MIN_EVIDENCE_SCORE_FOR_DIRECTIONAL_SUGGESTION = 50


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if isfinite(float(value)) else None
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in {"", "--", "-", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def positive_number(*values: Any) -> float | None:
    """Return the first finite, positive market value without zero defaults."""
    for value in values:
        parsed = number(value)
        if parsed is not None and isfinite(parsed) and parsed > 0:
            return parsed
    return None


def score_label(score: float) -> str:
    if score >= 72:
        return "高"
    if score >= 55:
        return "中高"
    if score >= 40:
        return "中"
    return "低"


def _normalise_score(value: Any) -> float | None:
    parsed = number(value)
    if parsed is None:
        return None
    return clamp(parsed)


def passes_evidence_gate(evidence_score: Any, minimum: float = MIN_EVIDENCE_SCORE_FOR_DIRECTIONAL_SUGGESTION) -> bool:
    parsed = _normalise_score(evidence_score)
    return parsed is not None and parsed >= minimum


def passes_data_quality_gate(data_quality_score: Any, minimum: float = MIN_EVIDENCE_SCORE_FOR_DIRECTIONAL_SUGGESTION) -> bool:
    parsed = _normalise_score(data_quality_score)
    return parsed is not None and parsed >= minimum


def build_decision_quality(
    available_evidence: int,
    evidence_total: int,
    quality_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return explainable data coverage and quality scores.

    This is deliberately a data-quality heuristic, not a predictive-confidence
    estimate. Unknown quality dimensions are omitted instead of being treated as
    healthy. ``quality_context`` may provide explicit 0-100 scores for freshness,
    provider health, consistency, or fallback-source use.
    """
    context = quality_context or {}
    total = max(int(evidence_total or 0), 0)
    available = max(min(int(available_evidence or 0), total), 0) if total else 0
    evidence_score = round((available / total) * 100) if total else 0
    dimensions: dict[str, float] = {"completeness": float(evidence_score)}

    explicit_dimensions = {
        "freshness": context.get("freshness_score"),
        "providerHealth": context.get("provider_health_score"),
        "consistency": context.get("consistency_score"),
        "fallbackSource": context.get("fallback_source_score"),
    }
    for name, value in explicit_dimensions.items():
        score = _normalise_score(value)
        if score is not None:
            dimensions[name] = score

    provider_status = str(context.get("provider_status") or "").strip().lower()
    if provider_status in {"failed", "error", "unavailable"}:
        dimensions["providerHealth"] = 0.0
    if context.get("stale") is True:
        dimensions["freshness"] = 0.0
    if "fallback_used" in context and "fallbackSource" not in dimensions:
        dimensions["fallbackSource"] = 50.0 if context["fallback_used"] else 100.0

    data_quality_score = round(sum(dimensions.values()) / len(dimensions)) if dimensions else None
    if provider_status in {"failed", "error", "unavailable"}:
        status = "FAILED"
    elif data_quality_score is None or not dimensions:
        status = "UNAVAILABLE"
    elif evidence_score == 100 and data_quality_score >= 80:
        status = "AVAILABLE"
    else:
        status = "PARTIAL"
    return {
        "evidenceScore": evidence_score,
        "dataQualityScore": data_quality_score,
        "dataQualityStatus": status,
        "dataQualityDimensions": dimensions,
    }


def build_decision_provenance(
    symbol: str,
    input_snapshot: dict[str, Any],
    decision_output: dict[str, Any],
    decision_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build reproducibility metadata without adding persistence.

    The hash covers only the decision inputs. Timestamps and identifiers are
    metadata and therefore do not make identical input snapshots hash differently.
    """
    context = decision_context or {}
    canonical_snapshot = json.dumps(
        input_snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    input_snapshot_hash = hashlib.sha256(canonical_snapshot.encode("utf-8")).hexdigest()
    symbol_text = str(symbol or "unknown").strip() or "unknown"
    model_version = str(context.get("model_version") or DECISION_MODEL_VERSION)
    strategy_version = str(context.get("strategy_version") or DECISION_STRATEGY_VERSION)
    market_as_of = context.get("market_as_of")
    decision_id_seed = "|".join(
        [symbol_text, str(market_as_of or ""), model_version, strategy_version, input_snapshot_hash]
    )
    decision_id = hashlib.sha256(decision_id_seed.encode("utf-8")).hexdigest()
    decision_time = context.get("decision_time") or datetime.now(timezone.utc).isoformat()
    confidence_method = str(context.get("confidence_method") or "NOT_CALIBRATED")
    return {
        "decision_id": decision_id,
        "symbol": symbol_text,
        "decision_time": str(decision_time),
        "market_as_of": market_as_of,
        "source_updated_at": context.get("source_updated_at"),
        "model_version": model_version,
        "strategy_version": strategy_version,
        "input_snapshot_hash": input_snapshot_hash,
        "confidence_method": confidence_method,
        "decision_output": decision_output,
    }


def build_decision_contract(
    *,
    symbol: str,
    input_snapshot: dict[str, Any],
    decision_output: dict[str, Any],
    available_evidence: int,
    evidence_total: int,
    decision_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quality = build_decision_quality(available_evidence, evidence_total, decision_context)
    return {
        **quality,
        # Snake_case aliases mirror the provenance contract while camelCase fields
        # remain the public API convention used by the existing frontend.
        "evidence_score": quality["evidenceScore"],
        "data_quality_score": quality["dataQualityScore"],
        "modelConfidence": None,
        "modelConfidenceStatus": MODEL_CONFIDENCE_STATUS_UNAVAILABLE,
        "model_confidence": None,
        "calibrationStatus": CALIBRATION_STATUS_UNAVAILABLE,
        "probabilityLabelAllowed": False,
        **build_decision_provenance(symbol, input_snapshot, decision_output, decision_context),
    }


def enrich_option_ai_decision(
    analysis: dict[str, Any],
    summary: dict[str, Any],
    chain: list[dict[str, Any]],
    spot: float | None,
    decision_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pcr = number(summary.get("putCallRatio"))
    volume_pcr = number(summary.get("volumePutCallRatio"))
    max_pain = number(summary.get("maxPain") or analysis.get("maxPain"))
    total_oi = number(summary.get("totalOpenInterest")) or 0
    support = number(analysis.get("supportLevel"))
    resistance = number(analysis.get("resistanceLevel"))
    evidence = 0
    directional = 50.0
    risk = 48.0

    if pcr is not None:
        evidence += 1
        directional += clamp((pcr - 1.0) * 22, -18, 18)
        risk += clamp((pcr - 1.0) * 18, -12, 22)
    if volume_pcr is not None:
        evidence += 1
        directional += clamp((volume_pcr - 1.0) * 12, -10, 10)
        risk += clamp(abs(volume_pcr - 1.0) * 16, 0, 14)
    if spot and max_pain:
        evidence += 1
        gap_pct = abs(spot - max_pain) / spot
        risk += clamp(gap_pct * 650, 0, 24)
        directional += clamp((spot - max_pain) / spot * 450, -12, 12)
    if support and resistance and spot:
        evidence += 1
        if support <= spot <= resistance:
            risk -= 4
        else:
            risk += 8
    if total_oi > 0:
        evidence += 1

    market_score = round(clamp(directional))
    risk_score = round(clamp(risk))
    confidence_score = round(clamp(38 + evidence * 12 + (10 if len(chain) >= 10 else 0)))
    decision_contract = build_decision_contract(
        symbol=str((decision_context or {}).get("symbol") or analysis.get("target") or "unknown"),
        input_snapshot={"summary": summary, "chain": chain, "spot": spot},
        decision_output={"bias": analysis.get("bias"), "marketScore": market_score, "riskScore": risk_score},
        available_evidence=evidence,
        evidence_total=5,
        decision_context=decision_context,
    )
    cross_validation = [
        {
            "name": "PCR",
            "status": "available" if pcr is not None else "missing",
            "signal": f"{pcr:.2f}" if pcr is not None else "資料不足",
        },
        {
            "name": "Volume PCR",
            "status": "available" if volume_pcr is not None else "missing",
            "signal": f"{volume_pcr:.2f}" if volume_pcr is not None else "資料不足",
        },
        {
            "name": "Max Pain Gap",
            "status": "available" if spot and max_pain else "missing",
            "signal": f"{spot - max_pain:+.0f}" if spot and max_pain else "現貨或最大痛點不足",
        },
        {
            "name": "OI Wall",
            "status": "available" if support and resistance else "missing",
            "signal": f"支撐 {support:.0f} / 壓力 {resistance:.0f}" if support and resistance else "OI 牆不足",
        },
    ]
    if risk_score >= 70:
        suggestion = "風險分數偏高，優先降低槓桿、縮小裸賣方部位，等待 PCR 與最大痛點重新收斂。"
    elif market_score >= 62 and passes_evidence_gate(decision_contract["evidenceScore"]):
        suggestion = "多方條件較佳，可用價差或小部位順勢觀察，停損放在主要 Put OI 支撐下方。"
    elif market_score <= 38 and passes_evidence_gate(decision_contract["evidenceScore"]):
        suggestion = "空方壓力較高，可偏向避險或減碼，避免在主要 Put OI 跌破後追高風險。"
    else:
        suggestion = "市場分數居中，先以區間策略、觀察最大痛點與 OI 牆變化為主。"
    return {
        **analysis,
        "marketScore": market_score,
        "riskScore": risk_score,
        **decision_contract,
        # Compatibility field. It is the pre-Q1 evidence proxy, not predictive confidence.
        "confidenceScore": confidence_score,
        "scoreFormula": {
            "marketScore": "50 + PCR directional pressure + Volume PCR pressure + Max Pain gap direction + OI wall position, clamped 0-100.",
            "riskScore": "48 + PCR risk pressure + Volume PCR imbalance + abs(Max Pain gap) + out-of-range OI wall penalty, clamped 0-100.",
            "evidenceScore": "Available required evidence layers / 5 * 100; coverage only, not predictive confidence.",
            "dataQualityScore": "Mean of known completeness, freshness, provider-health, consistency, and fallback-source dimensions; unknown dimensions are omitted.",
            "modelConfidence": "Unavailable until historical out-of-sample calibration exists; returned as null.",
            "confidenceScore": "DEPRECATED compatibility field: legacy evidence proxy, not calibrated model confidence.",
            "evidenceLayers": ["PCR", "Volume PCR", "Max Pain Gap", "OI Wall", "Total OI"],
        },
        "scoreLabels": {
            "market": score_label(market_score),
            "risk": score_label(risk_score),
            "evidence": score_label(decision_contract["evidenceScore"]),
            "confidence": score_label(confidence_score),
        },
        "deprecatedFields": {
            "confidenceScore": {
                "deprecated": True,
                "replacement": "evidenceScore",
                "semanticStatus": "EVIDENCE_STRENGTH",
            },
        },
        "crossValidation": cross_validation,
        "strategySuggestion": suggestion,
    }


def enrich_futures_ai_decision(
    analysis: dict[str, Any],
    item: dict[str, Any],
    candles: list[dict[str, Any]],
    decision_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pct = number(item.get("pct"))
    oi = number(item.get("openInterest"))
    volume = number(item.get("volume"))
    evidence = 1 if pct is not None else 0
    if oi is not None:
        evidence += 1
    if volume is not None:
        evidence += 1
    if len(candles) >= 10:
        evidence += 1

    market_score = 50 + (clamp((pct or 0) * 8, -22, 22) if pct is not None else 0)
    risk_score = 45 + (10 if pct is not None and pct < -0.8 else 0) + (6 if oi else 0)
    confidence_score = 35 + evidence * 14
    context = decision_context or {
        "symbol": item.get("symbol"),
        "market_as_of": item.get("date"),
        "source_updated_at": item.get("date"),
        "provider_status": "failed" if item.get("error") else "healthy",
        "fallback_used": str(item.get("sourceStatus") or "").lower() in {"fallback", "snapshot"},
    }
    decision_contract = build_decision_contract(
        symbol=str(context.get("symbol") or analysis.get("target") or item.get("symbol") or "unknown"),
        input_snapshot={"item": item, "candles": candles},
        decision_output={"bias": analysis.get("bias"), "marketScore": round(clamp(market_score)), "riskScore": round(clamp(risk_score))},
        available_evidence=evidence,
        evidence_total=4,
        decision_context=context,
    )
    cross_validation = [
        {"name": "Price Change", "status": "available" if pct is not None else "missing", "signal": item.get("pct") or "--"},
        {"name": "Open Interest", "status": "available" if oi is not None else "missing", "signal": item.get("openInterest") or "--"},
        {"name": "Volume", "status": "available" if volume is not None else "missing", "signal": item.get("volume") or "--"},
        {"name": "Candles", "status": "available" if candles else "missing", "signal": f"{len(candles)} bars"},
    ]
    if risk_score >= 65:
        suggestion = "期貨風險偏高，先控槓桿與保證金，等待價格與未平倉方向一致。"
    elif market_score >= 60 and passes_evidence_gate(decision_contract["evidenceScore"]):
        suggestion = "短線偏多，可用小部位順勢並以近 20 日支撐作風控。"
    elif market_score <= 40 and passes_evidence_gate(decision_contract["evidenceScore"]):
        suggestion = "短線偏空，優先防守與避險，反彈未站回壓力前不追多。"
    else:
        suggestion = "訊號未形成一致方向，以區間與風險控管為主。"
    return {
        **analysis,
        "marketScore": round(clamp(market_score)),
        "riskScore": round(clamp(risk_score)),
        **decision_contract,
        # Compatibility field. It is the pre-Q1 evidence proxy, not predictive confidence.
        "confidenceScore": round(clamp(confidence_score)),
        "scoreFormula": {
            "marketScore": "50 + futures percent-change directional score, clamped 0-100.",
            "riskScore": "45 + downside momentum penalty + open-interest availability risk premium, clamped 0-100.",
            "evidenceScore": "Available required evidence layers / 4 * 100; coverage only, not predictive confidence.",
            "dataQualityScore": "Mean of known completeness, freshness, provider-health, consistency, and fallback-source dimensions; unknown dimensions are omitted.",
            "modelConfidence": "Unavailable until historical out-of-sample calibration exists; returned as null.",
            "confidenceScore": "DEPRECATED compatibility field: legacy evidence proxy, not calibrated model confidence.",
            "evidenceLayers": ["Price Change", "Open Interest", "Volume", "Candles"],
        },
        "deprecatedFields": {
            "confidenceScore": {
                "deprecated": True,
                "replacement": "evidenceScore",
                "semanticStatus": "EVIDENCE_STRENGTH",
            },
        },
        "crossValidation": cross_validation,
        "strategySuggestion": suggestion,
    }


def build_basis_payload(future: dict[str, Any], spot_snapshot: dict[str, Any], history: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    future_price = positive_number(future.get("close"), future.get("last"), future.get("settlement"))
    spot = positive_number(spot_snapshot.get("value"), spot_snapshot.get("close"))
    basis = future_price - spot if future_price is not None and spot is not None else None
    basis_pct = (basis / spot * 100) if basis is not None and spot is not None else None
    return {
        "future": future.get("symbol"),
        "spot": "TAIEX",
        "futurePrice": future_price,
        "spotPrice": spot,
        "basis": basis,
        "basisPct": basis_pct,
        "date": future.get("date") or spot_snapshot.get("date"),
        "source": {
            "future": future.get("source") or future.get("sourceLink") or "TAIFEX / Yahoo Finance",
            "spot": spot_snapshot.get("source") or "TWSE 加權指數",
        },
        "history": history or [],
        "status": "available" if basis is not None else "source_pending",
        "message": "期現貨價差已由期貨價格與台灣加權指數現貨計算。" if basis is not None else "期貨或現貨資料暫不可用，保留欄位不以假資料替代。",
    }
