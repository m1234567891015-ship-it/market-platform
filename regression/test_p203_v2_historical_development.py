from __future__ import annotations

import copy
import math
import random
import shutil
import tempfile
import unittest
from contextlib import contextmanager, ExitStack
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts import p203_v2_historical_development as v2

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "p203"


@contextmanager
def _materialized_frozen_inputs():
    """Materialize immutable tracked evidence under an isolated temporary root."""
    with tempfile.TemporaryDirectory(prefix="p203-v2-frozen-inputs-") as temporary:
        root = Path(temporary)
        temp_artifacts = root / ".tmp"
        temp_artifacts.mkdir()
        materialized = {}
        for fixture_name, temporary_name in (
            ("protocol", "p203-v2-protocol"),
            ("historical-v1r1", "p203-historical-research-v1r1"),
            ("diagnostics", "p203-v1r1-diagnostic"),
            ("historical-v1", "p203-historical-research-v1"),
        ):
            destination = temp_artifacts / temporary_name
            shutil.copytree(FIXTURE_ROOT / fixture_name, destination)
            materialized[fixture_name] = destination

        protocol_dir = materialized["protocol"]
        input_dir = materialized["historical-v1r1"]
        v1_dir = materialized["historical-v1"]
        with ExitStack() as stack:
            for name, value in {
                "ROOT": root,
                "PROTOCOL_PATH": FIXTURE_ROOT / "docs" / "P2_03_RESEARCH_V2_PRE_REGISTRATION.md",
                "AMENDMENT_PATH": FIXTURE_ROOT / "docs" / "P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md",
                "ORIGINAL_MANIFEST_PATH": protocol_dir / "protocol_manifest.json",
                "IDENTITY_PATH": protocol_dir / "effective_protocol_identity.json",
                "AMENDMENT_MANIFEST_PATH": protocol_dir / "protocol_amendment_001_manifest.json",
                "INPUT_DIR": input_dir,
                "INPUT_INVENTORY_PATH": input_dir / "raw_data_inventory.json",
                "SERIES_PATH": input_dir / "rebuilt_daily_series.csv",
                "SELECTION_TRACE_PATH": input_dir / "selection_trace.csv",
            }.items():
                stack.enter_context(patch.object(v2, name, value))
            stack.enter_context(patch.object(v2.v1r1, "V1_DIR", v1_dir))
            stack.enter_context(patch.object(v2.v1r1, "CONTRACT_PATH", v1_dir / "feature_contract.json"))
            yield


def _fixture_rows(count: int = 130) -> list[dict[str, object]]:
    dates = []
    current = date(2025, 1, 1)
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current.isoformat())
        current += timedelta(days=1)
    rng = random.Random(2030301)
    increments = [rng.uniform(-0.022, 0.022) for _ in range(count)]
    close = 20_000.0
    rows = []
    for index, day in enumerate(dates):
        if index:
            close *= 1.0 + increments[index % len(increments)]
        range_pct = 0.003 + (index % 7) * 0.0002
        rows.append({
            "time": day,
            "contractMonth": "202506",
            "open": close * (1.0 - increments[index % len(increments)] / 3.0),
            "high": close * (1.0 + range_pct),
            "low": close * (1.0 - range_pct * 0.9),
            "close": close,
            "change": 0.0,
            "changePct": 0.0,
            "volume": 12_000.0 + index * 37.0 + (index % 5) * 113.0,
            "openInterest": 50_000.0 + index * 17.0,
            "settlement": close,
            "source": "fixture-only",
        })
    return rows


def _run_fixture(rows: list[dict[str, object]]) -> dict[str, object]:
    with patch.object(v2, "BOOTSTRAP_ITERATIONS", 100):
        return v2.run_development(rows)


class HistoricalResearchV2DevelopmentTests(unittest.TestCase):
    def setUp(self):
        self._frozen_inputs_context = _materialized_frozen_inputs()
        self._frozen_inputs_context.__enter__()

    def tearDown(self):
        self._frozen_inputs_context.__exit__(None, None, None)

    def test_effective_protocol_hashes_and_source_inventory_are_frozen(self):
        protocol = v2._verify_effective_protocol()
        self.assertEqual(v2.EXPECTED_HASHES["originalProtocol"], protocol["hashes"]["originalProtocol"])
        self.assertEqual(v2.EXPECTED_HASHES["amendment001"], protocol["hashes"]["amendment001"])
        hashes = v2._verify_source_evidence_hashes()
        self.assertEqual(38, len(hashes["sourceV1R1Hashes"]))
        self.assertEqual(15, len(hashes["diagnosticHashes"]))
        rows, inventory = v2._load_selected_series()
        self.assertEqual(441, len(rows))
        self.assertEqual(["2024-12-06", "2026-10-01"], [rows[0]["time"], rows[-1]["time"]])
        self.assertEqual(24, inventory["rawWindowCount"])
        self.assertEqual(v2.v1r1.SELECTION_RULE, inventory["selectionRule"])

    def test_frozen_historical_window_is_blocked_by_insufficient_roll_clean_training(self):
        rows, _ = v2._load_selected_series()
        result = v2.run_development(rows)
        self.assertEqual(441, result["funnel"]["totalSelectedSessions"])
        self.assertEqual(401, result["funnel"]["rollIneligible"])
        self.assertEqual(19, result["funnel"]["maturedEligibleLabels"])
        self.assertEqual(19, result["funnel"]["insufficientTrainingUnder30"])
        self.assertEqual(0, result["funnel"]["forecastGenerated"])
        self.assertEqual(0, result["funnel"]["validDevelopmentOosPairs"])
        self.assertEqual("BLOCKED", result["summary"]["developmentStatus"])
        self.assertEqual("NOT_RUN_NO_VALID_DEVELOPMENT_OOS_PAIRS", result["bootstrap"]["status"])

    def test_protocol_hash_mismatch_fails_closed(self):
        with patch.dict(v2.EXPECTED_HASHES, {"amendment001": "0" * 64}):
            with self.assertRaises(v2.IntegrityError):
                v2._verify_effective_protocol()

    def test_exact_six_feature_contract(self):
        self.assertEqual(
            (
                "momentum_strength_5", "range_pct_1", "trend_alignment_20",
                "volume_confirmation_5", "directional_price_location_20", "range_pct_5",
            ),
            v2.FEATURE_NAMES,
        )
        self.assertEqual(6, len(v2.FEATURE_SPECS))
        self.assertEqual(20, max(item["lookbackSessions"] for item in v2.FEATURE_SPECS))
        contract = v2._run_outputs(_run_fixture(_fixture_rows(65)), {"fixture": True})
        import json
        runtime = json.loads(contract["feature_contract_runtime.json"].decode("utf-8"))
        self.assertEqual(list(v2.FEATURE_NAMES), [feature["name"] for feature in runtime["features"]])
        self.assertTrue(all(feature["rollRule"] == v2.ROLL_RULE for feature in runtime["features"]))

    def test_six_feature_formulas_match_frozen_definitions(self):
        rows = _fixture_rows(35)
        index = 27
        features, direction, sign5 = v2.derive_features(rows, index)
        self.assertIsNotNone(features)
        self.assertIn(direction, {"RESEARCH_LONG", "RESEARCH_SHORT"})
        close = lambda i: float(rows[i]["close"])
        high = lambda i: float(rows[i]["high"])
        low = lambda i: float(rows[i]["low"])
        volume = lambda i: float(rows[i]["volume"])
        sign = 1.0 if close(index) / close(index - 5) - 1 > 0 else -1.0
        self.assertEqual(sign, sign5)
        self.assertAlmostEqual(abs(close(index) / close(index - 5) - 1), features["momentum_strength_5"], places=14)
        self.assertAlmostEqual((high(index) - low(index)) / close(index), features["range_pct_1"], places=14)
        self.assertAlmostEqual(sign * (close(index) / close(index - 20) - 1), features["trend_alignment_20"], places=14)
        prior_mean_volume = sum(volume(pos) for pos in range(index - 5, index)) / 5
        expected_volume = sign * (close(index) / close(index - 1) - 1) * (volume(index) / prior_mean_volume - 1)
        self.assertAlmostEqual(expected_volume, features["volume_confirmation_5"], places=14)
        location_range = max(high(pos) for pos in range(index - 19, index + 1)) - min(low(pos) for pos in range(index - 19, index + 1))
        location = sign * (2 * (close(index) - min(low(pos) for pos in range(index - 19, index + 1))) / location_range - 1)
        self.assertAlmostEqual(location, features["directional_price_location_20"], places=14)
        expected_range_5 = (max(high(pos) for pos in range(index - 4, index + 1)) - min(low(pos) for pos in range(index - 4, index + 1))) / close(index)
        self.assertAlmostEqual(expected_range_5, features["range_pct_5"], places=14)

    def test_lookback_warmup_missing_data_and_zero_direction_fail_closed(self):
        rows = _fixture_rows(50)
        self.assertEqual("LOOKBACK_WARMUP_EXCLUDED", v2._candidate_for_index(rows, 19)["status"])
        missing = copy.deepcopy(rows)
        missing[24]["volume"] = None
        features, _, _ = v2.derive_features(missing, 27)
        self.assertIsNone(features)
        zero_direction = copy.deepcopy(rows)
        zero_direction[25]["close"] = zero_direction[20]["close"]
        zero_direction[25]["high"] = float(zero_direction[25]["close"]) * 1.01
        zero_direction[25]["low"] = float(zero_direction[25]["close"]) * 0.99
        zero_direction[25]["volume"] = 13_000.0
        self.assertEqual("DIRECTION_INELIGIBLE", v2._candidate_for_index(zero_direction, 25)["status"])

    def test_roll_window_and_target_roll_are_separately_identified(self):
        rows = _fixture_rows(80)
        for index in range(30, len(rows)):
            rows[index]["contractMonth"] = "202507"
        feature_roll = v2._candidate_for_index(rows, 30)
        self.assertEqual("ROLL_INELIGIBLE", feature_roll["status"])
        self.assertTrue(feature_roll["featureRollIneligible"])
        clean = v2._candidate_for_index(rows, 55)
        self.assertEqual("ELIGIBLE_MATURED_LABEL", clean["status"])

        target_roll = _fixture_rows(80)
        target_roll[55]["contractMonth"] = "202507"
        result = v2._candidate_for_index(target_roll, 54)
        self.assertEqual("ROLL_INELIGIBLE", result["status"])
        self.assertFalse(result["featureRollIneligible"])
        self.assertTrue(result["targetRollIneligible"])

    def test_target_unavailable_and_flat_target_are_excluded(self):
        rows = _fixture_rows(45)
        self.assertEqual("TARGET_UNAVAILABLE", v2._candidate_for_index(rows, 44)["status"])
        flat = _fixture_rows(50)
        flat[31]["close"] = flat[30]["close"]
        flat[31]["high"] = float(flat[31]["close"]) * 1.01
        flat[31]["low"] = float(flat[31]["close"]) * 0.99
        self.assertEqual("FLAT_TARGET_EXCLUDED", v2._candidate_for_index(flat, 30)["status"])

    def test_v1_compatible_intercept_and_zero_feature_weight_initialization(self):
        training = []
        for index in range(32):
            training.append({
                "value": 1 if index % 3 else 0,
                "features": {name: (index + 1) * (position + 2) / 100.0 for position, name in enumerate(v2.FEATURE_NAMES)},
            })
        model = v2.fit_logistic(training)
        positives = sum(row["value"] for row in training)
        negatives = len(training) - positives
        expected = math.log((positives + 0.5) / (negatives + 0.5))
        self.assertAlmostEqual(expected, model["initialWeights"][0], places=15)
        self.assertEqual([0.0] * 6, model["initialWeights"][1:])
        self.assertEqual(2500, v2.LOGISTIC_ITERATIONS)
        self.assertEqual(0.1, v2.LEARNING_RATE)
        self.assertEqual(0.01, v2.L2_PENALTY)

        v1 = v2.v1r1.v1
        v1_training = [
            {
                "value": index % 2,
                "features": {name: (index * (position + 3) % 17) / 13.0 for position, name in enumerate(v1.FEATURE_NAMES)},
            }
            for index in range(40)
        ]
        with patch.object(v2, "FEATURE_NAMES", v1.FEATURE_NAMES):
            v2_parity_model = v2.fit_logistic(v1_training)
        v1_model = v1._fit(v1_training)
        self.assertEqual(v1_model["means"], v2_parity_model["means"])
        self.assertEqual(v1_model["stds"], v2_parity_model["stds"])
        self.assertEqual(v1_model["weights"], v2_parity_model["weights"])
        self.assertEqual(v1._sigmoid(0.73), v2._sigmoid(0.73))

    def test_training_gate_requires_30_prior_matured_rows_and_both_classes(self):
        training = [{"value": index % 2, "features": {name: float(index) for name in v2.FEATURE_NAMES}} for index in range(29)]
        with self.assertRaises(ValueError):
            v2.fit_logistic(training)
        training.append({"value": 1, "features": {name: 30.0 for name in v2.FEATURE_NAMES}})
        training[:] = [{**row, "value": 1} for row in training]
        with self.assertRaises(ValueError):
            v2.fit_logistic(training)

    def test_replay_uses_only_strictly_prior_matured_labels_and_past_only_naive(self):
        result = _run_fixture(_fixture_rows(65))
        self.assertGreater(len(result["pairs"]), 0)
        for pair, trace in zip(result["pairs"], result["trainingTrace"]):
            self.assertLess(trace["fitCutoff"], pair["forecastDate"])
            self.assertLess(trace["trainingEndTargetDate"], pair["forecastDate"])
            self.assertGreaterEqual(trace["trainingSampleCount"], 30)
            self.assertGreater(trace["trainingPositiveCount"], 0)
            self.assertGreater(trace["trainingNegativeCount"], 0)
            self.assertEqual(trace["trainingSampleCount"], trace["trainingPositiveCount"] + trace["trainingNegativeCount"])
            self.assertAlmostEqual(
                trace["trainingPositiveCount"] / trace["trainingSampleCount"],
                pair["naiveProbability"], places=15,
            )

    def test_future_observations_do_not_change_earlier_forecast_or_normalization(self):
        rows = _fixture_rows(65)
        baseline = _run_fixture(rows)
        changed = copy.deepcopy(rows)
        changed[-1]["close"] = float(changed[-1]["close"]) * 1.4
        changed[-1]["high"] = float(changed[-1]["high"]) * 1.5
        changed[-1]["low"] = float(changed[-1]["low"]) * 0.7
        changed[-1]["volume"] = float(changed[-1]["volume"]) * 3.0
        future_modified = _run_fixture(changed)
        self.assertEqual(baseline["forecasts"][0], future_modified["forecasts"][0])
        self.assertEqual(baseline["trainingTrace"][0], future_modified["trainingTrace"][0])

    def test_fixed_ece_bins_and_past_only_bootstrap_parameters(self):
        pairs = [
            {"probability": 0.0, "naiveProbability": 0.1, "outcome": 0},
            {"probability": 0.1, "naiveProbability": 0.9, "outcome": 1},
        ]
        bins, ece = v2._reliability(pairs, "probability")
        self.assertEqual(10, len(bins))
        self.assertEqual(1, bins[0]["count"])
        self.assertEqual(1, bins[1]["count"])
        self.assertAlmostEqual(0.45, ece)
        bootstrap = v2._bootstrap(pairs)
        self.assertEqual(20, bootstrap["blockSize"])
        self.assertEqual(10_000, bootstrap["iterations"])
        self.assertEqual(2_030_301, bootstrap["seed"])
        self.assertEqual(10_000, bootstrap["validAucReplicates"] + bootstrap["invalidSingleClassAucReplicates"])
        self.assertEqual(2, len(bootstrap["brierDifference95Ci"]))

    def test_full_replay_outputs_are_deterministic_and_never_claim_final_signal(self):
        rows = _fixture_rows(65)
        first = _run_fixture(rows)
        second = _run_fixture(rows)
        first_files = v2._run_outputs(first, {"fixture": "same"})
        second_files = v2._run_outputs(second, {"fixture": "same"})
        self.assertEqual(first_files, second_files)
        self.assertEqual("NOT EVALUATED — HISTORICAL DEVELOPMENT IS NOT FINAL VALIDATION", first["summary"]["researchSignalSupported"])
        self.assertFalse(first["summary"]["probabilityLabelAllowed"])
        self.assertEqual("BLOCKED — INSUFFICIENT PROSPECTIVE OOS CALIBRATION HISTORY", first["summary"]["productionP2_03"])
        self.assertEqual("NOT STARTED", first["summary"]["v2FinalEvaluation"])
        self.assertEqual(10_000, v2.BOOTSTRAP_ITERATIONS)
        funnel = first["funnel"]
        self.assertEqual(len(rows), funnel["totalSelectedSessions"])
        self.assertEqual(len(first["pairs"]), funnel["validDevelopmentOosPairs"])


if __name__ == "__main__":
    unittest.main()
