"""Regression coverage for the read-only V1R1 diagnostic audit."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts import p203_v1r1_diagnostic_audit as audit


class P203V1R1DiagnosticAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.input_before = audit._fingerprint_tree(audit.INPUT_DIR)
        cls.db_before = audit._database_snapshot(audit.DB_PATH)

    def test_oos_count_order_and_no_future_training_rows(self) -> None:
        forecasts = audit._read_csv(audit.INPUT_DIR / "reconstructed_forecasts.csv")
        traces = [json.loads(line) for line in (audit.INPUT_DIR / "training_trace.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(forecasts), 272)
        self.assertEqual([row["forecastDate"] for row in forecasts], sorted(row["forecastDate"] for row in forecasts))
        self.assertEqual(len(traces), len(forecasts))
        for forecast, trace in zip(forecasts, traces):
            self.assertLess(trace["fitCutoff"], forecast["forecastDate"])
            self.assertLess(trace["trainingEndTargetDate"], forecast["forecastDate"])
            self.assertEqual(trace["forecastDate"], forecast["forecastDate"])

    def test_recomputed_frozen_metrics_match_v1r1(self) -> None:
        forecasts = audit._read_csv(audit.INPUT_DIR / "reconstructed_forecasts.csv")
        pairs = {row["forecastDate"]: row for row in audit._read_csv(audit.INPUT_DIR / "oos_pairs.csv")}
        outcomes = [int(pairs[row["forecastDate"]]["outcome"]) for row in forecasts]
        model = [float(row["probability"]) for row in forecasts]
        naive = [float(row["naiveProbability"]) for row in forecasts]
        self.assertAlmostEqual(audit._brier(model, outcomes), audit.EXPECTED_METRICS["modelBrier"], places=12)
        self.assertAlmostEqual(audit._brier(naive, outcomes), audit.EXPECTED_METRICS["naiveBrier"], places=12)
        self.assertAlmostEqual(audit._ece(audit._calibration_bins(model, outcomes), len(model)), audit.EXPECTED_METRICS["modelEce"], places=12)
        self.assertAlmostEqual(audit._ece(audit._calibration_bins(naive, outcomes), len(naive)), audit.EXPECTED_METRICS["naiveEce"], places=12)

    def test_two_runs_are_deterministic_and_account_for_every_pair(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p203-v1r1-diagnostic-a-", dir=audit.ROOT / ".tmp") as first_dir:
            with tempfile.TemporaryDirectory(prefix="p203-v1r1-diagnostic-b-", dir=audit.ROOT / ".tmp") as second_dir:
                audit.analyze(audit.INPUT_DIR, Path(first_dir))
                audit.analyze(audit.INPUT_DIR, Path(second_dir))
                first_hashes = {path.name: audit._sha256(path) for path in Path(first_dir).iterdir() if path.is_file()}
                second_hashes = {path.name: audit._sha256(path) for path in Path(second_dir).iterdir() if path.is_file()}
                self.assertEqual(first_hashes, second_hashes)
                with (Path(first_dir) / "reliability_bins.csv").open("r", encoding="utf-8", newline="") as stream:
                    self.assertEqual(sum(int(row["count"]) for row in csv.DictReader(stream)), 272)
                with (Path(first_dir) / "coefficient_trace.csv").open("r", encoding="utf-8", newline="") as stream:
                    self.assertEqual(sum(1 for _ in csv.DictReader(stream)), 272 * 4)
                with (Path(first_dir) / "model_vs_naive.csv").open("r", encoding="utf-8", newline="") as stream:
                    self.assertEqual(sum(1 for _ in csv.DictReader(stream)), 272)

    def test_extreme_forecast_records_keep_features_and_coefficients(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p203-v1r1-diagnostic-extreme-", dir=audit.ROOT / ".tmp") as output:
            audit.analyze(audit.INPUT_DIR, Path(output))
            distribution = json.loads((Path(output) / "forecast_distribution.json").read_text(encoding="utf-8"))
            self.assertEqual(distribution["extremes"], {"pLt010": 3, "pGt090": 2, "pLt020": 4, "pGt080": 2})
            with (Path(output) / "largest_errors.csv").open("r", encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 20)
            for field in ("feature_momentum_5", "feature_range_pct_1", "feature_open_interest_change_1",
                          "coef_intercept", "coef_momentum_5", "coef_range_pct_1", "coef_open_interest_change_1"):
                self.assertIn(field, rows[0])
            with (Path(output) / "extreme_forecasts.csv").open("r", encoding="utf-8", newline="") as stream:
                extreme_rows = list(csv.DictReader(stream))
            self.assertEqual(len(extreme_rows), 6)
            self.assertTrue(all(float(row["forecast"]) < .20 or float(row["forecast"]) > .80 for row in extreme_rows))
            self.assertTrue(all("coef_intercept" in row and "feature_momentum_5" in row for row in extreme_rows))

    def test_v1r1_inputs_contract_and_prospective_db_remain_unchanged(self) -> None:
        self.assertEqual(audit._fingerprint_tree(audit.INPUT_DIR), self.input_before)
        self.assertEqual(audit._sha256(audit.CONTRACT_PATH), audit.EXPECTED_CONTRACT_SHA256)
        self.assertEqual(audit._database_snapshot(audit.DB_PATH), self.db_before)
        self.assertEqual(self.db_before["sha256"], audit.EXPECTED_DB_SHA256)
        self.assertEqual(self.db_before["counts"], {"decision_ledger": 1, "decision_outcome": 0})


if __name__ == "__main__":
    unittest.main()
