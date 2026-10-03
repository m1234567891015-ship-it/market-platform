"""Canonical risk-type metadata helpers; numeric risk models remain caller-owned."""
from __future__ import annotations

from typing import Any


RISK_TYPES = frozenset({"MARKET_RISK", "SIGNAL_RISK", "STRATEGY_RISK", "PORTFOLIO_RISK", "UNKNOWN"})


def risk_metadata(risk_type: str, score: Any) -> dict[str, Any]:
    """Return additive metadata; scores compare only within the same risk type."""
    normalized_type = str(risk_type or "UNKNOWN").strip().upper()
    if normalized_type not in RISK_TYPES:
        normalized_type = "UNKNOWN"
    return {
        "riskType": normalized_type,
        "riskClassification": {
            "type": normalized_type,
            "score": score,
            "comparability": "WITHIN_RISK_TYPE_ONLY",
        },
    }
