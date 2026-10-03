"""Canonical decision-state semantics for existing derivatives gates."""

from __future__ import annotations

from typing import Any


DECISION_STATES = frozenset({"LONG", "SHORT", "HOLD_EXISTING", "NO_TRADE", "UNKNOWN"})
NO_TRADE_REASON_CODES = frozenset({
    "INSUFFICIENT_EVIDENCE",
    "DATA_QUALITY_INSUFFICIENT",
    "SIGNAL_CONFLICT",
    "RISK_TOO_HIGH",
    "EDGE_INSUFFICIENT",
    "COST_TOO_HIGH",
    "LIQUIDITY_INSUFFICIENT",
    "CALIBRATION_INSUFFICIENT",
    "UNSUPPORTED_CONTEXT",
    "UNKNOWN",
})


def _unknown(detail: str = "Decision eligibility is not established by an existing explicit gate.") -> dict[str, Any]:
    return {
        "decisionState": "UNKNOWN",
        "decisionEligible": None,
        "reasonCodes": ["UNKNOWN"],
        "reasonDetails": [detail],
    }


def resolve_decision_state(
    *,
    execution_direction: str,
    execution_direction_reason: str,
    data_quality_status: str,
    explicit_state: Any = None,
    explicit_reason_codes: Any = None,
) -> dict[str, Any]:
    """Map only explicit action or already-defined hard prerequisites.

    Legacy score labels, neutral signals, and unavailable directions do not imply
    a no-trade decision. A caller may supply HOLD_EXISTING only as an explicit
    position-aware decision; no consumer state is inferred here.
    """
    direction = str(execution_direction or "UNAVAILABLE").strip().upper()
    reason = str(execution_direction_reason or "").strip().upper()
    quality = str(data_quality_status or "").strip().upper()
    explicit = str(explicit_state or "").strip().upper()

    # A hold applies to an already-open position and must never be rewritten as
    # an abstention from opening a new one by a later-entry quality gate.
    if explicit == "HOLD_EXISTING":
        return {
            "decisionState": "HOLD_EXISTING",
            "decisionEligible": False,
            "reasonCodes": [],
            "reasonDetails": ["Explicit position-aware instruction to maintain an existing position."],
        }

    # P1-01 defines FAILED as known-bad provider evidence. It blocks a new entry,
    # while PARTIAL/UNAVAILABLE remains distinct and is not silently promoted.
    if quality == "FAILED":
        return {
            "decisionState": "NO_TRADE",
            "decisionEligible": False,
            "reasonCodes": ["DATA_QUALITY_INSUFFICIENT"],
            "reasonDetails": ["Existing data-quality status is FAILED."],
        }

    if explicit:
        if explicit not in DECISION_STATES:
            return _unknown("Unrecognized explicit decision state.")
        if explicit == "NO_TRADE":
            raw_codes = explicit_reason_codes if isinstance(explicit_reason_codes, list) else []
            codes = list(dict.fromkeys(
                str(code).strip().upper() for code in raw_codes
                if str(code).strip().upper() in NO_TRADE_REASON_CODES
            ))
            if not codes:
                return _unknown("Explicit NO_TRADE lacks a recognized reason code.")
            return {
                "decisionState": "NO_TRADE",
                "decisionEligible": False,
                "reasonCodes": codes,
                "reasonDetails": [],
            }
        if explicit in {"LONG", "SHORT"}:
            return {
                "decisionState": explicit,
                "decisionEligible": True,
                "reasonCodes": [],
                "reasonDetails": [],
            }
        return _unknown("An explicit UNKNOWN state was supplied.")

    if direction in {"LONG", "SHORT"}:
        return {
            "decisionState": direction,
            "decisionEligible": True,
            "reasonCodes": [],
            "reasonDetails": [],
        }
    if direction == "NO_POSITION":
        # The existing P1-D field records a known no-position decision. Its
        # rationale is not present, so preserve that uncertainty in reasonCodes.
        return {
            "decisionState": "NO_TRADE",
            "decisionEligible": False,
            "reasonCodes": ["UNKNOWN"],
            "reasonDetails": ["The existing contract records NO_POSITION; its abstention rationale is unspecified."],
        }
    if direction == "UNAVAILABLE" and reason == "INSUFFICIENT_DECISION_DATA":
        return {
            "decisionState": "NO_TRADE",
            "decisionEligible": False,
            "reasonCodes": ["INSUFFICIENT_EVIDENCE"],
            "reasonDetails": ["The existing decision contract explicitly marks required decision data insufficient."],
        }
    return _unknown()
