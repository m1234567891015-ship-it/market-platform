from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    from .canonical_duplicate_verifier import (
        CHAIN_CANONICAL_IDENTITY,
        CHAIN_MATERIAL_PAYLOAD,
        OPTIONS_CANONICAL_IDENTITY,
        OPTIONS_MATERIAL_PAYLOAD,
        canonical_option_chain_payload,
        classify_canonical_groups,
    )
except ImportError:
    from canonical_duplicate_verifier import (
        CHAIN_CANONICAL_IDENTITY,
        CHAIN_MATERIAL_PAYLOAD,
        OPTIONS_CANONICAL_IDENTITY,
        OPTIONS_MATERIAL_PAYLOAD,
        canonical_option_chain_payload,
        classify_canonical_groups,
    )
from derivatives_store import DerivativesStore


def _chain_payload(call_last: float, put_last: float) -> dict:
    return {
        "underlying": "FIXED-TXO",
        "name": "Fixed test option",
        "tradeDate": "2026-06-20",
        "selectedExpiry": "202606",
        "summary": {"putCallRatio": 1.1, "volumePutCallRatio": 0.9, "maxPain": 21000},
        "chain": [
            {
                "strike": 21000,
                "call": {
                    "last": call_last,
                    "bid": call_last - 1,
                    "ask": call_last + 1,
                    "volume": 1,
                    "openInterest": 2,
                    "impliedVolatility": 0.2,
                },
                "put": {
                    "last": put_last,
                    "bid": put_last - 1,
                    "ask": put_last + 1,
                    "volume": 3,
                    "openInterest": 4,
                    "impliedVolatility": 0.3,
                },
            }
        ],
        "distribution": [],
        "expirations": [{"code": "202606", "expiryDate": "2026-06-17"}],
        "source": {"primary": "fixed-fixture"},
    }


class RuntimePersistenceIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="runtime-persistence-")
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "derivatives.sqlite3"
        self.store = DerivativesStore(self.db_path)
        self.store.initialize()

    def _count(self, table: str, where: str = "", params: tuple = ()) -> int:
        connection = sqlite3.connect(self.db_path)
        try:
            return connection.execute(f'SELECT COUNT(*) FROM "{table}" {where}', params).fetchone()[0]
        finally:
            connection.close()

    def _option_rows(self) -> list[dict]:
        connection = sqlite3.connect(self.db_path)
        try:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(options_quote)")]
            return [dict(zip(columns, row)) for row in connection.execute("SELECT * FROM options_quote")]
        finally:
            connection.close()

    def test_fixed_payload_a_twice_is_idempotent(self) -> None:
        payload = _chain_payload(10, 12)
        self.store.record_option_chain(payload, "2026-06-20T12:00:00+08:00")
        first = (self._count("option_chain_snapshot"), self._count("options_quote"))
        self.store.record_option_chain(payload, "2026-06-20T12:01:00+08:00")
        second = (self._count("option_chain_snapshot"), self._count("options_quote"))
        self.assertEqual(first, (1, 2))
        self.assertEqual(second, first)

    def test_canonical_payload_matches_existing_runtime_marker(self) -> None:
        payload = _chain_payload(10, 12)
        legacy_payload = {**payload, "cached": True}
        self.store.record_option_chain(legacy_payload, "2026-06-20T12:00:00+08:00")
        first = (self._count("option_chain_snapshot"), self._count("options_quote"))
        self.store.record_option_chain(payload, "2026-06-20T12:01:00+08:00")
        second = (self._count("option_chain_snapshot"), self._count("options_quote"))
        self.assertEqual(first, (1, 2))
        self.assertEqual(second, first)

    def test_conflict_is_preserved_without_reinserting_a_after_b(self) -> None:
        payload_a = _chain_payload(10, 12)
        payload_b = _chain_payload(11, 13)
        self.store.record_option_chain(payload_a, "2026-06-20T12:00:00+08:00")
        self.store.record_option_chain(payload_b, "2026-06-20T12:01:00+08:00")
        self.store.record_option_chain(payload_a, "2026-06-20T12:02:00+08:00")
        self.assertEqual(self._count("option_chain_snapshot"), 2)
        self.assertEqual(self._count("options_quote"), 4)
        rows = self._option_rows()
        summary, groups = classify_canonical_groups(
            rows,
            OPTIONS_CANONICAL_IDENTITY,
            OPTIONS_MATERIAL_PAYLOAD,
            dataset="options_quote",
        )
        self.assertEqual(summary.safe_duplicate_extras, 0)
        self.assertEqual(summary.conflicting_groups, 2)
        self.assertTrue(all(group.classification == "CONFLICTING" for group in groups))

        chain_rows = []
        connection = sqlite3.connect(self.db_path)
        try:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(option_chain_snapshot)")]
            chain_rows = [dict(zip(columns, row)) for row in connection.execute("SELECT * FROM option_chain_snapshot")]
        finally:
            connection.close()
        for row in chain_rows:
            row["canonical_payload"] = canonical_option_chain_payload(row["payload_json"])
        chain_summary, _ = classify_canonical_groups(
            chain_rows,
            CHAIN_CANONICAL_IDENTITY,
            CHAIN_MATERIAL_PAYLOAD,
            dataset="chain_snapshot",
        )
        self.assertEqual(chain_summary.safe_duplicate_extras, 0)

    def test_concurrent_same_payload_is_idempotent(self) -> None:
        payload = _chain_payload(10, 12)

        def write_once() -> None:
            DerivativesStore(self.db_path).record_option_chain(payload, "2026-06-20T12:00:00+08:00")

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(lambda _: write_once(), range(8)))
        self.assertEqual(self._count("option_chain_snapshot"), 1)
        self.assertEqual(self._count("options_quote"), 2)

    def test_fixed_news_payload_three_times_inserts_once(self) -> None:
        item = {
            "title": "Fixed news",
            "source": "fixed-fixture",
            "link": "https://example.invalid/fixed-news",
            "summary": "same payload",
            "publishedAt": "2026-06-20 12:00",
        }
        for _ in range(3):
            self.store.record_news("fixed-news", [item])
        self.assertEqual(self._count("market_news", "WHERE category = ?", ("fixed-news",)), 1)


if __name__ == "__main__":
    unittest.main()
