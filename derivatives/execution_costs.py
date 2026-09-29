"""Immutable P0-B futures cost contract and arithmetic for P1-D outcomes.

The constants mirror js/state.js and js/shared-calc.js. Regression parity tests
execute that JavaScript implementation so drift fails deterministically.
"""
from __future__ import annotations

import math
from typing import Any


CONTRACT_VERSION = "P0B_FUTURES_COST_V1"
BASE_SOURCE = "Project Owner authorized P0-B1 BASE assumptions"
CONTRACTS = {
    "TX": {"market": "TAIFEX", "multiplier": 200, "tickSize": 1, "transactionTaxRate": 0.00002, "currency": "TWD", "contractSpecSource": "https://www.taifex.com.tw/cht/2/tX", "brokerCommissionPerContract": 45, "slippageTicks": 1},
    "MTX": {"market": "TAIFEX", "multiplier": 50, "tickSize": 1, "transactionTaxRate": 0.00002, "currency": "TWD", "contractSpecSource": "https://www.taifex.com.tw/cht/2/mTX", "brokerCommissionPerContract": 22.5, "slippageTicks": 1},
    "TMF": {"market": "TAIFEX", "multiplier": 10, "tickSize": 1, "transactionTaxRate": 0.00002, "currency": "TWD", "contractSpecSource": "https://www.taifex.com.tw/cht/2/tMF", "brokerCommissionPerContract": 11, "slippageTicks": 1},
    "TE": {"market": "TAIFEX", "multiplier": 4000, "tickSize": 0.05, "transactionTaxRate": 0.00002, "currency": "TWD", "contractSpecSource": "https://www.taifex.com.tw/cht/2/tE", "brokerCommissionPerContract": 50, "slippageTicks": 1},
    "TF": {"market": "TAIFEX", "multiplier": 1000, "tickSize": 0.2, "transactionTaxRate": 0.00002, "currency": "TWD", "contractSpecSource": "https://www.taifex.com.tw/cht/2/tF", "brokerCommissionPerContract": 50, "slippageTicks": 1},
}


def _number(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def resolve_cost_snapshot(instrument: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    symbol = str(instrument or "").strip().upper()
    canonical = CONTRACTS.get(symbol)
    if canonical is None:
        return {"status": "UNAVAILABLE", "reason": "UNVERIFIED_FUTURES_CONTRACT_SPECIFICATION", "assetClass": "FUTURES", "instrumentSymbol": symbol or None}
    supplied = overrides if isinstance(overrides, dict) else {}
    spec = supplied.get("contractSpec") if isinstance(supplied.get("contractSpec"), dict) else {}
    for key, canonical_key in (("multiplier", "multiplier"), ("contractMultiplier", "multiplier"), ("tickSize", "tickSize"), ("transactionTaxRate", "transactionTaxRate"), ("currency", "currency")):
        value = spec.get(key) if key in spec else supplied.get(key)
        if value is not None and str(value) != str(canonical[canonical_key]):
            return {"status": "UNAVAILABLE", "reason": "FUTURES_CONTRACT_SPECIFICATION_CONFLICT", "assetClass": "FUTURES", "instrumentSymbol": symbol}
    commission_key = next((key for key in ("brokerCommissionPerContract", "commissionPerContract", "commission") if key in supplied), None)
    commission = _number(supplied.get(commission_key)) if commission_key else canonical["brokerCommissionPerContract"]
    slip = _number(supplied.get("slippageTicks")) if "slippageTicks" in supplied else canonical["slippageTicks"]
    if commission is None or commission < 0:
        return {"status": "UNAVAILABLE", "reason": "MISSING_OR_INVALID_BROKER_COMMISSION_CONFIGURATION", "assetClass": "FUTURES", "instrumentSymbol": symbol}
    if slip is None or slip < 0:
        return {"status": "UNAVAILABLE", "reason": "MISSING_OR_INVALID_SLIPPAGE_CONFIGURATION", "assetClass": "FUTURES", "instrumentSymbol": symbol}
    return {
        "contractVersion": CONTRACT_VERSION, "status": "AVAILABLE", "assetClass": "FUTURES",
        "instrumentSymbol": symbol, **{key: canonical[key] for key in ("market", "multiplier", "tickSize", "transactionTaxRate", "currency", "contractSpecSource")},
        "brokerCommissionPerContract": commission, "slippageTicks": slip,
        "commissionCurrency": "TWD", "commissionUnit": "per-contract-one-way",
        "executionAssumptionSource": "explicit backtest configuration" if commission_key or "slippageTicks" in supplied else BASE_SOURCE,
    }


def calculate_futures_cost(snapshot: dict[str, Any], direction: str, entry_price: Any, exit_price: Any, quantity: Any) -> dict[str, Any]:
    if not isinstance(snapshot, dict) or snapshot.get("contractVersion") != CONTRACT_VERSION or snapshot.get("status") != "AVAILABLE":
        return {"supported": False, "reason": (snapshot.get("reason") if isinstance(snapshot, dict) else None) or "MISSING_OR_INVALID_DECISION_TIME_COST_CONTRACT"}
    direction = str(direction or "").upper()
    if direction not in {"LONG", "SHORT"}:
        return {"supported": False, "reason": "INVALID_EXECUTION_DIRECTION"}
    q, entry, exit_ = _number(quantity), _number(entry_price), _number(exit_price)
    multiplier, tick = _number(snapshot.get("multiplier")), _number(snapshot.get("tickSize"))
    commission, slip = _number(snapshot.get("brokerCommissionPerContract")), _number(snapshot.get("slippageTicks"))
    tax_rate = _number(snapshot.get("transactionTaxRate"))
    if q is None or q <= 0:
        return {"supported": False, "reason": "MISSING_OR_INVALID_CONTRACT_QUANTITY"}
    if entry is None or exit_ is None or entry <= 0 or exit_ <= 0:
        return {"supported": False, "reason": "MISSING_EXECUTION_PRICE"}
    if multiplier is None or multiplier <= 0 or tick is None or tick <= 0 or commission is None or commission < 0 or slip is None or slip < 0 or tax_rate is None or tax_rate < 0 or not str(snapshot.get("currency") or "").strip():
        return {"supported": False, "reason": "INVALID_DECISION_TIME_COST_CONTRACT"}
    entry_side, exit_side = (("BUY", "SELL") if direction == "LONG" else ("SELL", "BUY"))
    entry_notional, exit_notional = entry * q * multiplier, exit_ * q * multiplier
    per_side_commission = q * commission
    entry_tax, exit_tax = entry_notional * tax_rate, exit_notional * tax_rate
    per_side_slippage = q * slip * tick * multiplier
    entry_cost = per_side_commission + entry_tax + per_side_slippage
    exit_cost = per_side_commission + exit_tax + per_side_slippage
    total_cost = entry_cost + exit_cost
    gross = ((exit_ - entry) if direction == "LONG" else (entry - exit_)) * q * multiplier
    normalized = total_cost / entry_notional * 100
    gross_return_pct = ((exit_ - entry) if direction == "LONG" else (entry - exit_)) / entry * 100
    return {
        "supported": True, "status": "supported", "assetClass": "FUTURES", "market": snapshot.get("market"),
        "instrumentSymbol": snapshot.get("instrumentSymbol"), "contractSpecSource": snapshot.get("contractSpecSource"),
        "executionAssumptionSource": snapshot.get("executionAssumptionSource"), "currency": snapshot["currency"],
        "side": {"entry": entry_side, "exit": exit_side}, "entryPrice": entry, "exitPrice": exit_,
        "quantity": q, "multiplier": multiplier, "tickSize": tick,
        "brokerCommissionPerContract": commission, "transactionTaxRate": tax_rate, "slippageTicks": slip,
        "grossPnl": gross, "commissionCost": per_side_commission * 2, "taxCost": entry_tax + exit_tax,
        "slippageCost": per_side_slippage * 2, "otherCost": 0, "totalEntryCost": entry_cost,
        "totalExitCost": exit_cost, "totalCost": total_cost, "roundTripCost": total_cost,
        "netPnl": gross - total_cost, "normalizedCostPct": normalized,
        "grossDirectionalReturnPct": gross_return_pct,
        "costAdjustedReturnPct": gross_return_pct - normalized,
    }
