"""Canonical historical duplicate verifier.

The safe-duplicate contract is deliberately stricter than an exact payload
subgroup count: an entire canonical identity group is safe only when every
material observation in that group is equivalent.  If one conflicting payload
exists, the whole identity group is conflicting and contributes zero safe
duplicate extras.

This module is read-only when auditing SQLite.  It is the single executable
implementation shared by the focused verifier tests and the current-DB audit.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


FUTURES_CANONICAL_IDENTITY = ("symbol", "trade_time", "source")
FUTURES_MATERIAL_PAYLOAD = (
    "last_price",
    "bid",
    "ask",
    "open_price",
    "high_price",
    "low_price",
    "volume",
    "open_interest",
)

OPTIONS_CANONICAL_IDENTITY = ("contract_key", "trade_time")
OPTIONS_MATERIAL_PAYLOAD = (
    "last_price",
    "bid",
    "ask",
    "volume",
    "open_interest",
    "implied_volatility",
)

CHAIN_CANONICAL_IDENTITY = ("underlying", "expiry_date", "trade_date", "canonical_payload")
CHAIN_MATERIAL_PAYLOAD = ("canonical_payload",)

OI_CANONICAL_IDENTITY = ("symbol", "market_type", "trade_date")
OI_MATERIAL_PAYLOAD = ("long_oi", "short_oi", "net_oi")


@dataclass(frozen=True)
class GroupClassification:
    identity: tuple[Any, ...]
    row_count: int
    payload_variants: int
    classification: str
    safe_duplicate_extras: int


@dataclass(frozen=True)
class DuplicateSummary:
    dataset: str
    total_rows: int
    duplicate_identity_groups: int
    safe_duplicate_groups: int
    safe_duplicate_extras: int
    conflicting_groups: int
    conflicting_rows: int
    unknown_groups: int
    legitimate_multi_observation_groups: int
    legacy_exact_payload_groups: int
    legacy_exact_payload_extras: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "total_rows": self.total_rows,
            "duplicate_identity_groups": self.duplicate_identity_groups,
            "safe_duplicate_groups": self.safe_duplicate_groups,
            "safe_duplicate_extras": self.safe_duplicate_extras,
            "conflicting_groups": self.conflicting_groups,
            "conflicting_rows": self.conflicting_rows,
            "unknown_groups": self.unknown_groups,
            "legitimate_multi_observation_groups": self.legitimate_multi_observation_groups,
            "legacy_exact_payload_groups": self.legacy_exact_payload_groups,
            "legacy_exact_payload_extras": self.legacy_exact_payload_extras,
        }


def canonical_option_chain_payload(payload_json: str) -> str:
    """Return semantic JSON identity matching DerivativesStore's markers rule."""
    parsed = json.loads(payload_json)
    if not isinstance(parsed, dict):
        raise ValueError("option-chain payload must be a JSON object")
    canonical = dict(parsed)
    for marker in ("cached", "stale", "staleAt"):
        canonical.pop(marker, None)
    return json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _row_value(row: Mapping[str, Any], field: str) -> Any:
    return row[field]


def _group_key(row: Mapping[str, Any], fields: Sequence[str]) -> tuple[Any, ...]:
    return tuple(_row_value(row, field) for field in fields)


def classify_canonical_groups(
    rows: Iterable[Mapping[str, Any]],
    identity_fields: Sequence[str],
    payload_fields: Sequence[str],
    *,
    dataset: str,
    unknown_conflicts: bool = True,
) -> tuple[DuplicateSummary, tuple[GroupClassification, ...]]:
    """Classify identity groups without collapsing conflicting payloads.

    Python tuples intentionally preserve ``None``, ``""``, and ``0`` as
    distinct values.  No truthiness or string coercion is used here.
    """
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    material_rows = list(rows)
    for row in material_rows:
        grouped[_group_key(row, identity_fields)].append(row)

    classifications: list[GroupClassification] = []
    safe_groups = safe_extras = 0
    conflicting_groups = conflicting_rows = 0
    unknown_groups = 0
    duplicate_identity_groups = 0

    for identity, group in grouped.items():
        if len(group) <= 1:
            continue
        duplicate_identity_groups += 1
        variants = {
            tuple(_row_value(row, field) for field in payload_fields)
            for row in group
        }
        variant_count = len(variants)
        if variant_count == 1:
            classification = "SAFE_DUPLICATE"
            extras = len(group) - 1
            safe_groups += 1
            safe_extras += extras
        else:
            classification = "CONFLICTING"
            extras = 0
            conflicting_groups += 1
            conflicting_rows += len(group)
            if unknown_conflicts:
                unknown_groups += 1
        classifications.append(
            GroupClassification(identity, len(group), variant_count, classification, extras)
        )

    summary = DuplicateSummary(
        dataset=dataset,
        total_rows=len(material_rows),
        duplicate_identity_groups=duplicate_identity_groups,
        safe_duplicate_groups=safe_groups,
        safe_duplicate_extras=safe_extras,
        conflicting_groups=conflicting_groups,
        conflicting_rows=conflicting_rows,
        unknown_groups=unknown_groups,
        legitimate_multi_observation_groups=0,
        legacy_exact_payload_groups=0,
        legacy_exact_payload_extras=0,
    )
    return summary, tuple(classifications)


def classify_legitimate_multi_observations(
    rows: Iterable[Mapping[str, Any]],
    coarse_identity_fields: Sequence[str],
    observation_fields: Sequence[str],
) -> tuple[GroupClassification, ...]:
    """Classify distinct valid observations sharing a coarse business key."""
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_group_key(row, coarse_identity_fields)].append(row)
    result: list[GroupClassification] = []
    for coarse_identity, group in grouped.items():
        observations = {
            tuple(_row_value(row, field) for field in observation_fields)
            for row in group
        }
        if len(observations) > 1:
            result.append(
                GroupClassification(
                    coarse_identity,
                    len(group),
                    len(observations),
                    "LEGITIMATE_MULTI_OBSERVATION",
                    0,
                )
            )
    return tuple(result)


def _with_legacy_exact_counts(
    summary: DuplicateSummary,
    rows: Iterable[Mapping[str, Any]],
    identity_fields: Sequence[str],
    payload_fields: Sequence[str],
) -> DuplicateSummary:
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_group_key(row, (*identity_fields, *payload_fields))].append(row)
    legacy_groups = sum(1 for group in grouped.values() if len(group) > 1)
    legacy_extras = sum(len(group) - 1 for group in grouped.values() if len(group) > 1)
    return DuplicateSummary(
        **{
            **summary.as_dict(),
            "legacy_exact_payload_groups": legacy_groups,
            "legacy_exact_payload_extras": legacy_extras,
        }
    )


def _fetch_rows(connection: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(query).fetchall()]


def _audit_table(
    connection: sqlite3.Connection,
    *,
    dataset: str,
    query: str,
    identity_fields: Sequence[str],
    payload_fields: Sequence[str],
    add_legacy_counts: bool = True,
) -> tuple[DuplicateSummary, tuple[GroupClassification, ...]]:
    rows = _fetch_rows(connection, query)
    summary, groups = classify_canonical_groups(
        rows,
        identity_fields,
        payload_fields,
        dataset=dataset,
    )
    if add_legacy_counts:
        summary = _with_legacy_exact_counts(summary, rows, identity_fields, payload_fields)
    return summary, groups


def audit_database(path: str | Path) -> dict[str, Any]:
    """Read-only audit of all four canonical duplicate datasets."""
    db_path = Path(path).resolve()
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    uri = f"file:{db_path.as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        futures_summary, futures_groups = _audit_table(
            connection,
            dataset="futures_quote",
            query="""
                SELECT symbol, trade_time, source,
                       last_price, bid, ask, open_price, high_price, low_price,
                       volume, open_interest
                FROM futures_quote
                ORDER BY id
            """,
            identity_fields=FUTURES_CANONICAL_IDENTITY,
            payload_fields=FUTURES_MATERIAL_PAYLOAD,
        )
        options_summary, options_groups = _audit_table(
            connection,
            dataset="options_quote",
            query="""
                SELECT contract_key, trade_time,
                       last_price, bid, ask, volume, open_interest, implied_volatility
                FROM options_quote
                ORDER BY id
            """,
            identity_fields=OPTIONS_CANONICAL_IDENTITY,
            payload_fields=OPTIONS_MATERIAL_PAYLOAD,
        )
        chain_rows = _fetch_rows(
            connection,
            """
            SELECT underlying, expiry_date, trade_date, payload_json
            FROM option_chain_snapshot
            ORDER BY id
            """,
        )
        for row in chain_rows:
            row["canonical_payload"] = canonical_option_chain_payload(row["payload_json"])
        chain_summary, chain_groups = classify_canonical_groups(
            chain_rows,
            CHAIN_CANONICAL_IDENTITY,
            CHAIN_MATERIAL_PAYLOAD,
            dataset="option_chain_snapshot",
        )
        coarse_chain_groups = classify_legitimate_multi_observations(
            chain_rows,
            ("underlying", "expiry_date", "trade_date"),
            ("canonical_payload",),
        )
        chain_summary = DuplicateSummary(
            **{
                **chain_summary.as_dict(),
                "legitimate_multi_observation_groups": len(coarse_chain_groups),
            }
        )
        oi_summary, oi_groups = _audit_table(
            connection,
            dataset="open_interest",
            query="""
                SELECT symbol, market_type, trade_date, long_oi, short_oi, net_oi
                FROM open_interest
                ORDER BY id
            """,
            identity_fields=OI_CANONICAL_IDENTITY,
            payload_fields=OI_MATERIAL_PAYLOAD,
        )
        return {
            "db_path": str(db_path),
            "futures": futures_summary.as_dict(),
            "options_quote": options_summary.as_dict(),
            "chain_snapshot": chain_summary.as_dict(),
            "open_interest": oi_summary.as_dict(),
            "group_classifications": {
                "futures": [group.__dict__ for group in futures_groups],
                "options_quote": [group.__dict__ for group in options_groups],
                "chain_snapshot": [group.__dict__ for group in chain_groups],
                "open_interest": [group.__dict__ for group in oi_groups],
            },
        }
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only canonical duplicate audit")
    parser.add_argument("--db", default="derivatives-platform.sqlite3")
    args = parser.parse_args()
    result = audit_database(args.db)
    compact = {
        key: value
        for key, value in result.items()
        if key not in {"db_path", "group_classifications"}
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
