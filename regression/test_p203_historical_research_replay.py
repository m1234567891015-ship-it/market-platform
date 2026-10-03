from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from derivatives import probability_forecast as production_forecast
from scripts import p203_historical_research_replay as replay


def _rows(count: int = 70) -> list[dict[str, object]]:
    result = []
    close = 20000.0
    steps = [0.006, -0.004, 0.003, -0.007, 0.009, -0.002, 0.005, -0.006]
    first = date(2025, 1, 1)
    for index in range(count):
        if index:
            close *= 1 + steps[index % len(steps)]
        result.append({
            "time": (first + timedelta(days=index)).isoformat(),
            "open": close * 0.999,
            "high": close * 1.006,
            "low": close * 0.994,
            "close": close,
            "changePct": steps[index % len(steps)] * 100,
            "volume": 30000 + index * 37,
            "openInterest": 50000 + index * 113 + (index % 5) * 41,
            "settlement": close * 1.0002,
            "contractMonth": "202501",
            "source": "synthetic-test-only",
        })
    return result


def _training_rows(count: int = 32) -> list[dict[str, object]]:
    rows = []
    for index in range(count):
        rows.append({
            "index": index,
            "status": "ELIGIBLE_TARGET",
            "decisionDate": f"2025-01-{index + 1:02d}",
            "targetDate": f"2025-01-{index + 2:02d}",
            "value": index % 2,
            "features": {
                "momentum_5": index / 100.0,
                "range_pct_1": (index % 7) / 1000.0,
                "open_interest_change_1": (index % 5) / 100.0,
            },
        })
    return rows


class HistoricalResearchReplayTests(unittest.TestCase):
    def test_future_row_cannot_change_prior_features(self):
        rows = _rows()
        original = replay.derive_features(rows, 12)
        rows[13]["close"] = float(rows[13]["close"]) * 9
        rows[40]["high"] = float(rows[40]["high"]) * 8
        self.assertEqual(original, replay.derive_features(rows, 12))

    def test_future_target_is_excluded_from_training(self):
        candidates = _training_rows(8)
        matured = replay._matured_prior(candidates, "2025-01-05", 5)
        self.assertEqual(["2025-01-02", "2025-01-03", "2025-01-04"], [row["targetDate"] for row in matured])
        self.assertTrue(all(row["targetDate"] < "2025-01-05" for row in matured))

    def test_normalization_uses_only_passed_training_rows(self):
        training = _training_rows()
        model = replay._fit(training)
        for index, name in enumerate(replay.FEATURE_NAMES):
            expected = sum(row["features"][name] for row in training) / len(training)
            self.assertAlmostEqual(expected, model["means"][index])
        future_row = _training_rows(1)[0]
        future_row["features"] = {name: 1e9 for name in replay.FEATURE_NAMES}
        self.assertNotIn(future_row, training)
        self.assertAlmostEqual(
            sum(row["features"][replay.FEATURE_NAMES[0]] for row in training) / len(training),
            model["means"][0],
        )

    def test_warmup_is_excluded(self):
        rows = _rows()
        self.assertIsNone(replay.derive_features(rows, 4))
        self.assertIsNotNone(replay.derive_features(rows, 5))

    def test_minimum_training_sample_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "insufficient training"):
            replay._fit(_training_rows(29))

    def test_both_classes_are_required(self):
        training = _training_rows()
        for row in training:
            row["value"] = 1
        with self.assertRaisesRegex(ValueError, "both training classes"):
            replay._fit(training)

    def test_target_is_exactly_next_observed_session(self):
        rows = _rows(10)
        candidate = replay._make_candidate(rows, 5)
        self.assertEqual(rows[5]["time"], candidate["decisionDate"])
        self.assertEqual(rows[6]["time"], candidate["targetDate"])

    def test_flat_target_is_excluded(self):
        rows = _rows(10)
        rows[6]["close"] = rows[5]["close"]
        candidate = replay._make_candidate(rows, 5)
        self.assertEqual("EXCLUDED_FLAT", candidate["status"])

    def test_input_hash_validation_rejects_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "input.json"
            path.write_text(json.dumps(_rows(8)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "input hash mismatch"):
                replay.load_dataset(path, "0" * 64)

    def test_research_provenance_is_exact(self):
        candidate = replay._make_candidate(_rows(), 10)
        self.assertEqual("ELIGIBLE_TARGET", candidate["status"])
        self.assertEqual("HISTORICAL_RESEARCH_AS_OF_OOS", candidate["provenance"])
        self.assertNotEqual("PROSPECTIVE_DECISION_TIME_MODEL_OUTPUT", candidate["provenance"])

    def test_production_feature_contract_is_unchanged_and_separate(self):
        self.assertEqual("P2_03_DERIVATIVES_SCORE_FEATURES_V1", production_forecast.FEATURE_CONTRACT_VERSION)
        self.assertEqual(("marketScore", "riskScore", "evidenceScore", "dataQualityScore"), production_forecast.FEATURE_FIELDS)
        self.assertEqual("P2_03_HISTORICAL_RESEARCH_FEATURES_V1", replay.FEATURE_CONTRACT_ID)
        self.assertNotIn("dataQualityScore", replay.FEATURE_NAMES)

    def test_replay_core_does_not_touch_prospective_database(self):
        with tempfile.TemporaryDirectory(prefix="p203-replay-db-isolation-") as temp_dir:
            isolated_root = Path(temp_dir)
            db_path = isolated_root / "data" / "p203-prospective-ledger.sqlite3"
            db_path.parent.mkdir(parents=True)
            db_path.write_bytes(b"isolated-test-database-sentinel")
            before = hashlib.sha256(db_path.read_bytes()).hexdigest()
            with patch.object(replay, "ROOT", isolated_root):
                replay.run_replay(_rows(20), "test-input-sha256")
            after = hashlib.sha256(db_path.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_replay_core_is_deterministic(self):
        rows = _rows(62)
        first = replay.run_replay(rows, "fixture-hash")
        second = replay.run_replay(rows, "fixture-hash")
        for field in ("featureRows", "forecasts", "pairs", "trainingTrace", "funnel", "report"):
            self.assertEqual(first[field], second[field], field)


if __name__ == "__main__":
    unittest.main()
