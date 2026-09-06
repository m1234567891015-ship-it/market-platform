from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

try:
    from .canonical_duplicate_verifier import (
        CHAIN_CANONICAL_IDENTITY,
        CHAIN_MATERIAL_PAYLOAD,
        FUTURES_CANONICAL_IDENTITY,
        FUTURES_MATERIAL_PAYLOAD,
        OI_CANONICAL_IDENTITY,
        OI_MATERIAL_PAYLOAD,
        OPTIONS_CANONICAL_IDENTITY,
        OPTIONS_MATERIAL_PAYLOAD,
        audit_database,
        canonical_option_chain_payload,
        classify_canonical_groups,
        classify_legitimate_multi_observations,
    )
except ImportError:
    from canonical_duplicate_verifier import (
        CHAIN_CANONICAL_IDENTITY,
        CHAIN_MATERIAL_PAYLOAD,
        FUTURES_CANONICAL_IDENTITY,
        FUTURES_MATERIAL_PAYLOAD,
        OI_CANONICAL_IDENTITY,
        OI_MATERIAL_PAYLOAD,
        OPTIONS_CANONICAL_IDENTITY,
        OPTIONS_MATERIAL_PAYLOAD,
        audit_database,
        canonical_option_chain_payload,
        classify_canonical_groups,
        classify_legitimate_multi_observations,
    )


def classify_values(values: list[object]):
    rows = [{"key": "X", "value": value} for value in values]
    summary, groups = classify_canonical_groups(
        rows,
        ("key",),
        ("value",),
        dataset="fixture",
    )
    return summary, groups[0]


class CanonicalDuplicateContractTests(unittest.TestCase):
    def test_case_a_a_is_safe_duplicate(self):
        summary, group = classify_values(["A", "A"])
        self.assertEqual(group.classification, "SAFE_DUPLICATE")
        self.assertEqual(summary.safe_duplicate_extras, 1)

    def test_case_a_a_a_has_two_safe_extras(self):
        summary, group = classify_values(["A", "A", "A"])
        self.assertEqual(group.classification, "SAFE_DUPLICATE")
        self.assertEqual(summary.safe_duplicate_extras, 2)

    def test_case_a_b_is_conflicting(self):
        summary, group = classify_values(["A", "B"])
        self.assertEqual(group.classification, "CONFLICTING")
        self.assertEqual(summary.safe_duplicate_extras, 0)

    def test_case_a_a_b_is_conflicting_not_one_safe_extra(self):
        summary, group = classify_values(["A", "A", "B"])
        self.assertEqual(group.classification, "CONFLICTING")
        self.assertEqual(summary.safe_duplicate_extras, 0)
        self.assertEqual(group.row_count, 3)

    def test_case_a_a_b_b_is_conflicting(self):
        summary, group = classify_values(["A", "A", "B", "B"])
        self.assertEqual(group.classification, "CONFLICTING")
        self.assertEqual(summary.safe_duplicate_extras, 0)

    def test_legitimate_multi_observation_is_not_safe_duplicate(self):
        rows = [
            {"key": "X", "observation": "morning", "value": 100},
            {"key": "X", "observation": "afternoon", "value": 101},
        ]
        groups = classify_legitimate_multi_observations(rows, ("key",), ("observation",))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].classification, "LEGITIMATE_MULTI_OBSERVATION")
        self.assertEqual(groups[0].safe_duplicate_extras, 0)

    def test_null_empty_zero_are_distinct(self):
        summary, group = classify_values([None, "", 0])
        self.assertEqual(group.classification, "CONFLICTING")
        self.assertEqual(group.payload_variants, 3)
        self.assertEqual(summary.safe_duplicate_extras, 0)

    def test_futures_identity_and_payload_contract(self):
        self.assertEqual(FUTURES_CANONICAL_IDENTITY, ("symbol", "trade_time", "source"))
        self.assertEqual(
            FUTURES_MATERIAL_PAYLOAD,
            ("last_price", "bid", "ask", "open_price", "high_price", "low_price", "volume", "open_interest"),
        )

    def test_options_identity_and_payload_contract(self):
        self.assertEqual(OPTIONS_CANONICAL_IDENTITY, ("contract_key", "trade_time"))
        self.assertEqual(
            OPTIONS_MATERIAL_PAYLOAD,
            ("last_price", "bid", "ask", "volume", "open_interest", "implied_volatility"),
        )

    def test_chain_runtime_markers_are_not_material(self):
        left = {"underlying": "TXO", "cached": True, "summary": {"maxPain": 100}}
        right = {"underlying": "TXO", "stale": True, "staleAt": "later", "summary": {"maxPain": 100}}
        self.assertEqual(
            canonical_option_chain_payload(json.dumps(left)),
            canonical_option_chain_payload(json.dumps(right)),
        )
        self.assertEqual(CHAIN_CANONICAL_IDENTITY[-1], "canonical_payload")
        self.assertEqual(CHAIN_MATERIAL_PAYLOAD, ("canonical_payload",))

    def test_oi_identity_and_payload_contract(self):
        self.assertEqual(OI_CANONICAL_IDENTITY, ("symbol", "market_type", "trade_date"))
        self.assertEqual(OI_MATERIAL_PAYLOAD, ("long_oi", "short_oi", "net_oi"))


class CanonicalDuplicateDatabaseTests(unittest.TestCase):
    def _fixture_db(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory(prefix="canonical-duplicate-fixture-")
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "fixture.sqlite3"
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE futures_quote (
                id INTEGER PRIMARY KEY, symbol TEXT, trade_time TEXT, source TEXT,
                last_price REAL, bid REAL, ask REAL, open_price REAL,
                high_price REAL, low_price REAL, volume REAL, open_interest REAL
            );
            CREATE TABLE options_quote (
                id INTEGER PRIMARY KEY, contract_key TEXT, trade_time TEXT,
                last_price REAL, bid REAL, ask REAL, volume REAL,
                open_interest REAL, implied_volatility REAL
            );
            CREATE TABLE option_chain_snapshot (
                id INTEGER PRIMARY KEY, underlying TEXT, expiry_date TEXT,
                trade_date TEXT, payload_json TEXT
            );
            CREATE TABLE open_interest (
                id INTEGER PRIMARY KEY, symbol TEXT, market_type TEXT,
                trade_date TEXT, long_oi REAL, short_oi REAL, net_oi REAL
            );
            """
        )
        futures = ("TX", "2026-09-05", "source", 1, 2, 3, 4, 5, 6, 7, 8)
        connection.executemany(
            "INSERT INTO futures_quote VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(1, *futures), (2, *futures), (3, "TX", "2026-09-05", "source", 9, 2, 3, 4, 5, 6, 7, 8)],
        )
        options = ("TXO:202609F1:100:CALL", "2026-09-05", 1, 2, 3, 4, 5, 6)
        connection.executemany(
            "INSERT INTO options_quote VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(1, *options), (2, *options)],
        )
        payload = json.dumps({"summary": {"maxPain": 100}, "cached": True})
        connection.executemany(
            "INSERT INTO option_chain_snapshot VALUES (?, ?, ?, ?, ?)",
            [(1, "TXO", "202609", "2026-09-05", payload), (2, "TXO", "202609", "2026-09-05", payload)],
        )
        connection.executemany(
            "INSERT INTO open_interest VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(1, "TX", "futures", "2026-09-05", 1, 2, 3), (2, "TX", "futures", "2026-09-05", 1, 2, 3)],
        )
        connection.commit()
        connection.close()
        return path

    def test_database_audit_rejects_exact_subgroup_inside_conflict(self):
        result = audit_database(self._fixture_db())
        self.assertEqual(result["futures"]["safe_duplicate_extras"], 0)
        self.assertEqual(result["futures"]["conflicting_groups"], 1)
        self.assertEqual(result["futures"]["legacy_exact_payload_extras"], 1)
        self.assertEqual(result["options_quote"]["safe_duplicate_extras"], 1)
        self.assertEqual(result["chain_snapshot"]["safe_duplicate_extras"], 1)
        self.assertEqual(result["open_interest"]["safe_duplicate_extras"], 1)

    def test_shared_audit_is_stable_for_completion_and_historical_views(self):
        path = self._fixture_db()
        completion_view = audit_database(path)
        historical_view = audit_database(path)
        for dataset in ("futures", "options_quote", "chain_snapshot", "open_interest"):
            self.assertEqual(
                completion_view[dataset]["safe_duplicate_extras"],
                historical_view[dataset]["safe_duplicate_extras"],
            )


if __name__ == "__main__":
    unittest.main()
