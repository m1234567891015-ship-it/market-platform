from __future__ import annotations

from math import isfinite
from typing import Any


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


def enrich_option_ai_decision(analysis: dict[str, Any], summary: dict[str, Any], chain: list[dict[str, Any]], spot: float | None) -> dict[str, Any]:
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
    elif market_score >= 62 and confidence_score >= 58:
        suggestion = "多方條件較佳，可用價差或小部位順勢觀察，停損放在主要 Put OI 支撐下方。"
    elif market_score <= 38 and confidence_score >= 58:
        suggestion = "空方壓力較高，可偏向避險或減碼，避免在主要 Put OI 跌破後追高風險。"
    else:
        suggestion = "市場分數居中，先以區間策略、觀察最大痛點與 OI 牆變化為主。"
    return {
        **analysis,
        "marketScore": market_score,
        "riskScore": risk_score,
        "confidenceScore": confidence_score,
        "scoreFormula": {
            "marketScore": "50 + PCR directional pressure + Volume PCR pressure + Max Pain gap direction + OI wall position, clamped 0-100.",
            "riskScore": "48 + PCR risk pressure + Volume PCR imbalance + abs(Max Pain gap) + out-of-range OI wall penalty, clamped 0-100.",
            "confidenceScore": "38 + 12 points per available evidence layer + option-chain depth bonus, clamped 0-100.",
            "evidenceLayers": ["PCR", "Volume PCR", "Max Pain Gap", "OI Wall", "Total OI"],
        },
        "scoreLabels": {
            "market": score_label(market_score),
            "risk": score_label(risk_score),
            "confidence": score_label(confidence_score),
        },
        "crossValidation": cross_validation,
        "strategySuggestion": suggestion,
    }


def enrich_futures_ai_decision(analysis: dict[str, Any], item: dict[str, Any], candles: list[dict[str, Any]]) -> dict[str, Any]:
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
    cross_validation = [
        {"name": "Price Change", "status": "available" if pct is not None else "missing", "signal": item.get("pct") or "--"},
        {"name": "Open Interest", "status": "available" if oi is not None else "missing", "signal": item.get("openInterest") or "--"},
        {"name": "Volume", "status": "available" if volume is not None else "missing", "signal": item.get("volume") or "--"},
        {"name": "Candles", "status": "available" if candles else "missing", "signal": f"{len(candles)} bars"},
    ]
    if risk_score >= 65:
        suggestion = "期貨風險偏高，先控槓桿與保證金，等待價格與未平倉方向一致。"
    elif market_score >= 60 and confidence_score >= 55:
        suggestion = "短線偏多，可用小部位順勢並以近 20 日支撐作風控。"
    elif market_score <= 40 and confidence_score >= 55:
        suggestion = "短線偏空，優先防守與避險，反彈未站回壓力前不追多。"
    else:
        suggestion = "訊號未形成一致方向，以區間與風險控管為主。"
    return {
        **analysis,
        "marketScore": round(clamp(market_score)),
        "riskScore": round(clamp(risk_score)),
        "confidenceScore": round(clamp(confidence_score)),
        "scoreFormula": {
            "marketScore": "50 + futures percent-change directional score, clamped 0-100.",
            "riskScore": "45 + downside momentum penalty + open-interest availability risk premium, clamped 0-100.",
            "confidenceScore": "35 + 14 points per available evidence layer, clamped 0-100.",
            "evidenceLayers": ["Price Change", "Open Interest", "Volume", "Candles"],
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
