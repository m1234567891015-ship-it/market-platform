from __future__ import annotations

from typing import Any


def is_source_pending_product(spec: dict[str, Any]) -> bool:
    return spec.get("v1Status") == "source_pending" or spec.get("dataProvider") in {
        "taifex_product_status",
        "taifex_option_product_status",
    }


def build_source_pending_market_item(base_item: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    symbol = str(spec.get("symbol") or base_item.get("symbol") or "").strip()
    return {
        **base_item,
        "dataSymbol": symbol,
        "date": "--",
        "open": "--",
        "high": "--",
        "low": "--",
        "close": "--",
        "volume": "--",
        "openInterest": "--",
        "status": "source_pending",
        "v1Status": "source_pending",
        "dataStatus": spec.get("dataStatus") or "資料源待接入，不以外部官網跳轉代替內部功能。",
        "sourceNote": spec.get("dataStatus") or "",
        "series": [],
    }

