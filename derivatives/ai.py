from __future__ import annotations

from typing import Any

from .analytics import build_decision_contract


def build_unavailable_ai_analysis(target: str, message: str) -> dict[str, Any]:
    decision_contract = build_decision_contract(
        symbol=target,
        input_snapshot={"target": target, "message": message},
        decision_output={"bias": "資料不足", "marketScore": 50, "riskScore": 60},
        available_evidence=0,
        evidence_total=3,
        decision_context={"provider_status": "failed", "confidence_method": "NOT_CALIBRATED"},
    )
    return {
        "target": target,
        "bias": "資料不足",
        "supportLevel": None,
        "resistanceLevel": None,
        "riskLevel": "中",
        "marketScore": 50,
        "riskScore": 60,
        **decision_contract,
        # Compatibility field. It is the old fixed evidence proxy, not predictive confidence.
        "confidenceScore": 20,
        "deprecatedFields": {
            "confidenceScore": {
                "deprecated": True,
                "replacement": "evidenceScore",
                "semanticStatus": "EVIDENCE_STRENGTH",
            },
        },
        "scoreFormula": {
            "marketScore": "固定中性 50；資料源缺漏時不產生方向性分數。",
            "riskScore": "資料源缺漏時提高到 60，提示資料風險。",
            "evidenceScore": "0；缺少可用證據層，非預測信心。",
            "dataQualityScore": "資料來源失敗時 provider health = 0；無法取得可用決策資料。",
            "modelConfidence": "Unavailable until historical out-of-sample calibration exists; returned as null.",
            "confidenceScore": "DEPRECATED compatibility field: legacy fixed evidence proxy, not calibrated model confidence.",
            "evidenceLayers": [],
        },
        "crossValidation": [
            {"name": "Data source", "status": "missing", "signal": message},
            {"name": "Price", "status": "missing", "signal": "行情暫不可用"},
            {"name": "Open Interest", "status": "missing", "signal": "未平倉暫不可用"},
        ],
        "strategySuggestion": "資料不足時不輸出方向性策略；先等待官方或公開資料恢復。",
        "reasons": [message, "系統保留決策欄位，但不以推估值或外部官網跳轉替代功能。"],
        "scenarios": [],
        "disclaimer": "AI 分析以公開行情與系統規則計算；資料不足時僅提供風險提示，不構成交易建議。",
    }
