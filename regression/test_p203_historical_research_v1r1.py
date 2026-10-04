from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from scripts import p203_historical_research_replay as v1
from scripts import p203_historical_research_v1r1_replay as v1r1

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "p203"
V1_FIXTURE_DIR = FIXTURE_ROOT / "historical-v1"
V1R1_FIXTURE_DIR = FIXTURE_ROOT / "historical-v1r1"


def _rows(count: int = 150, monotonic: bool = False) -> list[dict[str, object]]:
    result = []
    close = 20000.0
    steps = [0.01, -0.018, -0.007, 0.025, -0.012, 0.005, -0.02, 0.03, 0.002, -0.015]
    first = date(2024, 12, 6)
    for index in range(count):
        if index:
            step = 0.004 if monotonic else steps[index % len(steps)]
            close *= 1 + step
        month = "202501" if index < 45 else "202502" if index < 95 else "202503"
        result.append({
            "time": (first + timedelta(days=index)).isoformat(),
            "contractMonth": month,
            "open": close * 0.999,
            "high": close * 1.006,
            "low": close * 0.994,
            "close": close,
            "volume": 10000 + index * 10,
            "openInterest": 50000 + index * 137 + (index % 7) * 51,
            "settlement": close * 1.0002,
            "source": "fixture-only",
        })
    return result


def _raw_row(day: str, contract_month: str, volume: str, close: str) -> list[str]:
    row = [day, "TX", contract_month, close, close, close, close, "0", "0", volume, close, "50000"]
    row.extend([""] * (17 - len(row)))
    row.append("一般")
    return row


@contextmanager
def _isolated_logical_ledger():
    """Create the frozen one-decision/no-outcome logical state in a temp DB."""
    with tempfile.TemporaryDirectory(prefix="p203-v1r1-ledger-") as directory:
        db_path = Path(directory) / "prospective-ledger.sqlite3"
        connection = sqlite3.connect(db_path)
        try:
            connection.execute("CREATE TABLE decision_ledger (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE decision_outcome (id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO decision_ledger DEFAULT VALUES")
            connection.commit()
        finally:
            connection.close()
        yield db_path


class HistoricalResearchV1R1Tests(unittest.TestCase):
    def test_highest_daily_volume_selection_is_deterministic_and_traced(self):
        headers = [f"c{index}" for index in range(18)]
        raw_rows = [headers,
                    _raw_row("2025/01/02", "202501", "200", "100"),
                    _raw_row("2025/01/02", "202502", "300", "110")]
        text = "\n".join(",".join(row) for row in raw_rows)
        selected, trace, summary = v1r1.select_daily_series([{
            "text": text, "csvRows": raw_rows,
        }])
        self.assertEqual("202502", selected[0]["contractMonth"])
        self.assertEqual(2, trace[0]["candidateContractCount"])
        self.assertEqual("HIGHEST_VOLUME", trace[0]["selectionReason"])
        self.assertEqual(["202501", "202502"], summary["distinctContractMonths"])
        self.assertEqual(selected, v1r1.select_daily_series([{"text": text, "csvRows": raw_rows}])[0])

    def test_tie_uses_first_eligible_source_row_like_existing_parser(self):
        headers = [f"c{index}" for index in range(18)]
        raw_rows = [headers,
                    _raw_row("2025/01/02", "202502", "300", "110"),
                    _raw_row("2025/01/02", "202501", "300", "100")]
        text = "\n".join(",".join(row) for row in raw_rows)
        selected, trace, summary = v1r1.select_daily_series([{"text": text, "csvRows": raw_rows}])
        self.assertEqual("202502", selected[0]["contractMonth"])
        self.assertEqual("HIGHEST_VOLUME_TIE_FIRST_SOURCE_ROW", trace[0]["selectionReason"])
        self.assertEqual(["2025-01-02"], summary["tieMarketDates"])

    def test_momentum_and_open_interest_require_contract_continuity(self):
        rows = _rows(150)
        features, candidates, counts = v1r1._features_and_candidates(rows)
        self.assertEqual(10, counts["crossContractMomentum"])
        self.assertEqual(2, counts["crossContractOi"])
        feature_dates = {row["marketDate"] for row in features}
        for index in range(45, 50):
            self.assertNotIn(rows[index]["time"], feature_dates)
        statuses = {item.get("index"): item["status"] for item in candidates}
        self.assertEqual("EXCLUDED_CROSS_CONTRACT_MOMENTUM_5_AND_OI_CHANGE", statuses[45])
        self.assertEqual("EXCLUDED_CROSS_CONTRACT_MOMENTUM_5", statuses[46])

    def test_target_crossing_roll_is_excluded(self):
        rows = _rows(70)
        _, candidates, counts = v1r1._features_and_candidates(rows)
        status_by_index = {item.get("index"): item["status"] for item in candidates}
        self.assertEqual("EXCLUDED_CROSS_CONTRACT_TARGET", status_by_index[44])
        self.assertGreater(counts["crossContractTarget"], 0)

    def test_all_replay_pairs_and_training_rows_are_roll_clean(self):
        rows = _rows(70)
        result = v1r1.run_clean_replay(rows, "fixture-series")
        self.assertGreater(len(result["pairs"]), 0)
        self.assertEqual(0, result["report"]["rollExposure"]["validPairFeatureExposure"])
        self.assertEqual(0, result["report"]["rollExposure"]["validPairTargetExposure"])
        self.assertEqual(0, result["report"]["rollExposure"]["trainingFeatureExposure"])
        self.assertEqual(0, result["report"]["rollExposure"]["trainingTargetExposure"])
        self.assertTrue(all(pair["provenance"] == "HISTORICAL_RESEARCH_AS_OF_OOS" for pair in result["pairs"]))
        self.assertTrue(all(pair["replayRevision"] == "V1R1" and pair["rollPolicy"] == v1r1.ROLL_POLICY for pair in result["pairs"]))
        self.assertTrue(all(pair["trainingSampleCount"] >= 30 for pair in result["pairs"]))
        self.assertTrue(all(pair["trainingPositiveCount"] > 0 and pair["trainingNegativeCount"] > 0 for pair in result["pairs"]))

    def test_clean_training_minimum_is_enforced(self):
        result = v1r1.run_clean_replay(_rows(45), "short-clean-history")
        self.assertGreater(result["funnel"]["insufficientCleanTraining"], 0)
        self.assertTrue(all(row["trainingSampleCount"] >= 30 for row in result["trainingTrace"]))

    def test_both_classes_are_required_for_clean_training(self):
        result = v1r1.run_clean_replay(_rows(90, monotonic=True), "one-class-history")
        self.assertGreater(result["funnel"]["singleClassCleanTraining"], 0)
        self.assertEqual([], result["forecasts"])

    def test_future_data_does_not_change_prior_forecast_or_normalization(self):
        rows = _rows(70)
        first = v1r1.run_clean_replay(rows, "future-invariance")
        first_forecast = first["forecasts"][0]
        first_trace = first["trainingTrace"][0]
        cutoff_index = next(index for index, row in enumerate(rows) if row["time"] == first_forecast["forecastDate"])
        rows[-1]["close"] = float(rows[-1]["close"]) * 4
        rows[-1]["high"] = float(rows[-1]["high"]) * 5
        changed_future = v1r1.run_clean_replay(rows, "future-invariance")
        changed_forecast = next(row for row in changed_future["forecasts"] if row["forecastDate"] == first_forecast["forecastDate"])
        changed_trace = next(row for row in changed_future["trainingTrace"] if row["forecastDate"] == first_forecast["forecastDate"])
        self.assertEqual(first_forecast, changed_forecast)
        self.assertEqual(first_trace, changed_trace)
        # V1 standardization applied to precisely the same clean matured training sample.
        clean_candidates = [item for item in first["candidates"] if item.get("status") == "ELIGIBLE_TARGET"
                            and item["index"] < cutoff_index
                            and item["decisionDate"] < first_forecast["forecastDate"]
                            and item["targetDate"] < first_forecast["forecastDate"]]
        self.assertEqual(first_forecast["trainingSampleCount"], len(clean_candidates))
        for feature_index, name in enumerate(v1.FEATURE_NAMES):
            mean = sum(item["features"][name] for item in clean_candidates) / len(clean_candidates)
            self.assertAlmostEqual(mean, first_trace["normalizationMeans"][feature_index])

    def test_v1_contract_and_artifacts_and_prospective_db_are_unchanged(self):
        before_v1 = v1r1._verify_frozen_inputs(V1_FIXTURE_DIR)
        with _isolated_logical_ledger() as db_path:
            before_db = v1r1._db_snapshot(db_path)
            rows = _rows(30)
            v1r1.run_clean_replay(rows, "integrity-fixture")
            after_v1 = v1r1._verify_frozen_inputs(V1_FIXTURE_DIR)
            after_db = v1r1._db_snapshot(db_path)
            self.assertEqual(before_v1["artifactSha256"], after_v1["artifactSha256"])
            self.assertEqual(before_db, after_db)
            self.assertEqual("73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4",
                             v1r1.EXPECTED_DB_SHA256)
            self.assertEqual(1, before_db["decision_ledger"])
            self.assertEqual(0, before_db["decision_outcome"])

    def test_complete_replay_is_deterministic(self):
        rows = _rows(70)
        first = v1r1.run_clean_replay(rows, "repeatable-series")
        second = v1r1.run_clean_replay(rows, "repeatable-series")
        for key in ("featureRows", "candidates", "forecasts", "pairs", "trainingTrace", "funnel", "report"):
            self.assertEqual(first[key], second[key], key)

    def test_old_vs_rebuilt_comparison_counts_mismatches(self):
        old = _rows(2)
        new = [dict(old[0]), dict(old[1], contractMonth="202505", close=999.0)]
        _, result = v1r1.compare_old_vs_rebuilt(old, new)
        self.assertEqual(2, result["matchingSessionDates"])
        self.assertEqual(1, result["contractMonthMismatches"])
        self.assertEqual(1, result["closeMismatches"])
        self.assertEqual(0, result["volumeMismatches"])
        self.assertEqual(0, result["openInterestMismatches"])

    def test_persisted_v1r1_artifacts_are_clean_and_metrics_round_trip(self):
        output_dir = V1R1_FIXTURE_DIR
        def read_csv(name):
            with (output_dir / name).open(encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))
        series = read_csv("rebuilt_daily_series.csv")
        feature_rows = read_csv("roll_clean_feature_matrix.csv")
        pairs = read_csv("oos_pairs.csv")
        forecasts = read_csv("reconstructed_forecasts.csv")
        traces = [json.loads(line) for line in (output_dir / "training_trace.jsonl").read_text(encoding="utf-8").splitlines() if line]
        series_by_date = {row["time"]: row for row in series}
        index_by_date = {row["time"]: index for index, row in enumerate(series)}
        feature_by_date = {row["marketDate"]: row for row in feature_rows}

        def number(row, field):
            return float(row[field])

        for row in feature_rows:
            index = index_by_date[row["marketDate"]]
            month = series[index]["contractMonth"]
            self.assertGreaterEqual(index, 5)
            self.assertTrue(all(series[pos]["contractMonth"] == month for pos in range(index - 5, index + 1)))
            self.assertEqual(month, series[index - 1]["contractMonth"])
            expected_momentum = number(series[index], "close") / number(series[index - 5], "close") - 1.0
            expected_oi = number(series[index], "openInterest") / number(series[index - 1], "openInterest") - 1.0
            expected_range = (number(series[index], "high") - number(series[index], "low")) / number(series[index], "close")
            self.assertAlmostEqual(expected_momentum, number(row, "momentum_5"), places=14)
            self.assertAlmostEqual(expected_oi, number(row, "open_interest_change_1"), places=14)
            self.assertAlmostEqual(expected_range, number(row, "range_pct_1"), places=14)
            expected_direction = "RESEARCH_LONG" if expected_momentum > 0 else "RESEARCH_SHORT" if expected_momentum < 0 else "UNAVAILABLE"
            self.assertEqual(expected_direction, row["researchDirection"])
            self.assertEqual("V1R1", row["replayRevision"])
            self.assertEqual(v1r1.ROLL_POLICY, row["rollPolicy"])

        outcomes = []
        brier = naive_brier = 0.0
        for pair in pairs:
            index = index_by_date[pair["forecastDate"]]
            self.assertEqual(series[index + 1]["time"], pair["targetDate"])
            self.assertEqual(series[index]["contractMonth"], series[index + 1]["contractMonth"])
            self.assertIn(pair["forecastDate"], feature_by_date)
            self.assertGreaterEqual(number(pair, "probability"), 0.0)
            self.assertLessEqual(number(pair, "probability"), 1.0)
            direction_sign = 1 if pair["researchDirection"] == "RESEARCH_LONG" else -1
            aligned = direction_sign * (number(series[index + 1], "close") / number(series[index], "close") - 1.0)
            self.assertAlmostEqual(aligned, number(pair, "decisionAlignedReturn"), places=14)
            self.assertEqual(1 if aligned > 0 else 0, int(pair["outcome"]))
            outcomes.append((number(pair, "probability"), number(pair, "naiveProbability"), int(pair["outcome"])))
            brier += (number(pair, "probability") - int(pair["outcome"])) ** 2
            naive_brier += (number(pair, "naiveProbability") - int(pair["outcome"])) ** 2

        self.assertEqual(len(pairs), len(forecasts))
        self.assertEqual(len(pairs), len(traces))
        for trace in traces:
            self.assertGreaterEqual(trace["trainingSampleCount"], 30)
            self.assertEqual(trace["trainingSampleCount"], trace["trainingPositiveCount"] + trace["trainingNegativeCount"])
            self.assertLess(trace["fitCutoff"], trace["forecastDate"])
            self.assertEqual(trace["fitCutoff"], trace["trainingEndTargetDate"])
            self.assertLessEqual(trace["trainingStartTargetDate"], trace["trainingEndTargetDate"])

        report = json.loads((output_dir / "calibration_report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(pairs), report["pairCount"])
        self.assertAlmostEqual(brier / len(pairs), report["brierScore"], places=14)
        self.assertAlmostEqual(naive_brier / len(pairs), report["pastOnlyNaiveBaseRateBrierScore"], places=14)
        for key in ("validPairFeatureExposure", "validPairTargetExposure", "trainingFeatureExposure", "trainingTargetExposure"):
            self.assertEqual(0, report["rollExposure"][key])
        self.assertEqual("NOT PROVEN; historical source lacks per-day publication timestamps, archived vintages, and revision history.", report["sourceVintageStatus"])
        self.assertEqual("EVIDENCE INCONCLUSIVE", report["interpretation"])

        determinism = json.loads((output_dir / "determinism_report.json").read_text(encoding="utf-8"))
        self.assertTrue(determinism["twoRunsIdentical"])
        self.assertEqual(determinism["runFingerprints"][0], determinism["runFingerprints"][1])
        raw = json.loads((output_dir / "raw_data_inventory.json").read_text(encoding="utf-8"))
        for entry in raw["rawFiles"]:
            self.assertEqual(entry["sha256"], hashlib.sha256((output_dir / "raw" / entry["file"]).read_bytes()).hexdigest())
        frozen = v1r1._verify_frozen_inputs(V1_FIXTURE_DIR)
        self.assertEqual(v1r1.EXPECTED_V1_FILE_HASHES, frozen["artifactSha256"])
        with _isolated_logical_ledger() as db_path:
            db = v1r1._db_snapshot(db_path)
        self.assertEqual("73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4",
                         v1r1.EXPECTED_DB_SHA256)
        self.assertEqual(1, db["decision_ledger"])
        self.assertEqual(0, db["decision_outcome"])


if __name__ == "__main__":
    unittest.main()
