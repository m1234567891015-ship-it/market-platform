from __future__ import annotations

from typing import Any

from .ai import build_unavailable_ai_analysis


def build_unavailable_option_chain(message: str, options_url: str, underlying: str = "TXO") -> dict[str, Any]:
    return {
        "underlying": underlying,
        "name": "臺指選擇權",
        "market": "台灣",
        "exchange": "TAIFEX",
        "tradeDate": None,
        "selectedExpiry": None,
        "expirations": [],
        "summary": {
            "callOpenInterest": None,
            "putOpenInterest": None,
            "putCallRatio": None,
            "volumePutCallRatio": None,
            "maxPain": None,
        },
        "chain": [],
        "distribution": [],
        "analysis": build_unavailable_ai_analysis(underlying, message),
        "source": {
            "primary": "TAIFEX 選擇權每日交易行情查詢",
            "primaryUrl": options_url,
            "status": "source_unavailable",
        },
        "status": "source_unavailable",
        "message": message,
    }

