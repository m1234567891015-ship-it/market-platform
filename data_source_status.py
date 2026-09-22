"""Canonical status metadata for API payloads backed by external data sources."""
from __future__ import annotations

from typing import Any

SOURCE_STATES = frozenset(
    {"healthy", "stale", "temporarily_unavailable", "invalid_payload"}
)


def annotate_source_payload(
    payload: Any,
    required_fields: dict[str, type],
    *,
    stale: bool = False,
    non_empty_fields: tuple[str, ...] = (),
    timestamp_fields: tuple[str, ...] = ("refreshedAt", "cachedAt", "snapshotDate"),
) -> dict[str, Any]:
    """Copy an API payload and attach its canonical status and best available time."""
    if not isinstance(payload, dict):
        return {"sourceStatus": "invalid_payload"}

    result = dict(payload)
    valid = all(
        field in result
        and (expected is Any or isinstance(result[field], expected))
        for field, expected in required_fields.items()
    )
    valid = valid and all(
        field in result and bool(result[field]) for field in non_empty_fields
    )
    result["sourceStatus"] = (
        "invalid_payload" if not valid else "stale" if stale else "healthy"
    )
    updated_at = next(
        (result.get(field) for field in timestamp_fields if result.get(field)), None
    )
    if updated_at is not None:
        result["sourceUpdatedAt"] = updated_at
    return result


def annotate_source_error(payload: Any, status: str) -> dict[str, Any]:
    """Attach an error state without discarding the established error contract."""
    if status not in SOURCE_STATES:
        raise ValueError(f"unsupported source status: {status}")
    result = dict(payload) if isinstance(payload, dict) else {}
    result["sourceStatus"] = status
    return result


def providers_are_stale(provider_status: Any) -> bool:
    """Return whether retained cache data is backed by a failed recent refresh."""
    if not isinstance(provider_status, dict):
        return False
    stale_provider_states = {"timeout", "network_error", "unavailable"}
    return any(
        isinstance(provider, dict)
        and provider.get("status") in stale_provider_states
        for provider in provider_status.values()
    )
