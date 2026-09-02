from __future__ import annotations

from typing import Any


def build_unavailable_ai_analysis(target: str, message: str) -> dict[str, Any]:
    return {
        "target": target,
        "bias": "資料不足",
        "supportLevel": None,
        "resistanceLevel": None,
        "riskLevel": "中",
        "marketScore": 50,
        "riskScore": 60,
        "confidenceScore": 20,
        "scoreFormula": {
            "marketScore": "固定中性 50；資料源缺漏時不產生方向性分數。",
            "riskScore": "資料源缺漏時提高到 60，提示資料風險。",
            "confidenceScore": "固定 20；缺少可交叉驗證資料。",
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
