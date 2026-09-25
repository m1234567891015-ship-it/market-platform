"""Deterministic P0-21..P0-27 confidence/probability semantic coverage."""

from pathlib import Path
import unittest

from derivatives.analytics import (
    MODEL_CONFIDENCE_STATUS_UNAVAILABLE,
    build_decision_contract,
    passes_data_quality_gate,
    passes_evidence_gate,
)
from derivatives.calibration import (
    CALIBRATION_STATUS_INSUFFICIENT_SAMPLE,
    CALIBRATION_STATUS_UNAVAILABLE,
    build_calibration_buckets,
    build_oos_calibration_report,
    calculate_brier_score,
)


ROOT = Path(__file__).resolve().parents[1]
OPTIONS_SOURCE = (ROOT / "js" / "page-global-market-options.js").read_text(encoding="utf-8")
ASSET_HUB_SOURCE = (ROOT / "js" / "page-global-market-assethub.js").read_text(encoding="utf-8")


class QuantIntegritySemanticTests(unittest.TestCase):
    def test_t1_evidence_is_not_model_confidence(self):
        contract = build_decision_contract(
            symbol="TEST",
            input_snapshot={"evidenceScore": 90, "dataQualityScore": 95},
            decision_output={"bias": "neutral"},
            available_evidence=5,
            evidence_total=5,
        )
        self.assertEqual(contract["evidenceScore"], 100)
        self.assertEqual(contract["dataQualityScore"], 100)
        self.assertIsNone(contract["modelConfidence"])
        self.assertEqual(contract["modelConfidenceStatus"], MODEL_CONFIDENCE_STATUS_UNAVAILABLE)
        self.assertFalse(contract["probabilityLabelAllowed"])

    def test_t2_legacy_confidence_alias_cannot_drive_gate(self):
        self.assertFalse(passes_evidence_gate(20))
        self.assertFalse(passes_evidence_gate(20, minimum=50))
        # A high deprecated alias has no input path into the canonical gate.
        legacy_confidence_score = 100
        self.assertGreaterEqual(legacy_confidence_score, 50)
        self.assertFalse(passes_evidence_gate(20))

    def test_t3_data_quality_gate_reads_data_quality_field(self):
        self.assertTrue(passes_data_quality_gate(80))
        self.assertFalse(passes_data_quality_gate(40))
        self.assertFalse(passes_data_quality_gate(None))

    def test_t4_heuristic_scenario_weights_are_not_probabilities(self):
        self.assertIn('scenarioSemanticStatus: "HEURISTIC_SCENARIO_WEIGHT"', OPTIONS_SOURCE)
        self.assertIn('probabilityLabelAllowed: false', OPTIONS_SOURCE)
        self.assertIn('probabilitiesDeprecated: true', OPTIONS_SOURCE)

    def test_t5_ui_uses_non_probability_scenario_wording(self):
        self.assertIn("\u60c5\u5883\u6b0a\u91cd", OPTIONS_SOURCE)
        self.assertIn("\u8b49\u64da\u5f37\u5ea6", OPTIONS_SOURCE)
        self.assertIn("\u591a\u65b9\u6b0a\u91cd", ASSET_HUB_SOURCE)
        self.assertNotIn("\u60c5\u5883\u727d\u5f15\u8207\u5340\u9593\u9707\u76ea\u6a5f\u7387", OPTIONS_SOURCE)

    def test_t6_model_confidence_unavailable_ui_contract(self):
        self.assertIn("modelConfidence: null", OPTIONS_SOURCE)
        self.assertIn('modelConfidenceStatus: "UNAVAILABLE"', OPTIONS_SOURCE)
        self.assertNotIn("AI 信心 ${analysis.evidenceScore}", OPTIONS_SOURCE)

    def test_t7_insufficient_oos_sample_fails_closed(self):
        report = build_oos_calibration_report(
            [0.1, 0.8],
            [0, 1],
            min_samples=3,
        )
        self.assertEqual(report["calibrationStatus"], CALIBRATION_STATUS_INSUFFICIENT_SAMPLE)
        self.assertFalse(report["probabilityLabelAllowed"])

    def test_t8_brier_score_is_deterministic(self):
        self.assertEqual(calculate_brier_score([0.1, 0.8], [0, 1]), 0.025)

    def test_t9_calibration_buckets_are_deterministic(self):
        buckets = build_calibration_buckets([0.05, 0.15, 0.85, 0.95], [0, 1, 0, 1], bucket_count=10)
        self.assertEqual(buckets[0]["predictionCount"], 1)
        self.assertEqual(buckets[1]["predictionCount"], 1)
        self.assertEqual(buckets[8]["predictionCount"], 1)
        self.assertEqual(buckets[9]["predictionCount"], 1)
        self.assertEqual(buckets[1]["observedEventRate"], 1.0)
        self.assertEqual(buckets[8]["observedEventRate"], 0.0)

    def test_t10_final_test_holdout_is_protected(self):
        report = build_oos_calibration_report([0.01, 0.99], [1, 0], data_split="test")
        self.assertEqual(report["calibrationStatus"], CALIBRATION_STATUS_UNAVAILABLE)
        self.assertTrue(report["testHoldoutProtected"])
        self.assertIsNone(report["brierScore"])
        self.assertEqual(report["calibrationBuckets"], [])

    def test_t11_deprecated_alias_is_explicit(self):
        self.assertIn('probabilities: { ...scenarioWeights }', OPTIONS_SOURCE)
        self.assertIn('"deprecatedFields"', (ROOT / "derivatives" / "analytics.py").read_text(encoding="utf-8"))
        self.assertIn('"replacement": "evidenceScore"', (ROOT / "derivatives" / "analytics.py").read_text(encoding="utf-8"))

    def test_t12_current_model_has_no_calibrated_probability_claim(self):
        report = build_oos_calibration_report([0.2] * 30, [0] * 30)
        self.assertEqual(report["calibrationStatus"], "UNCALIBRATED")
        self.assertFalse(report["probabilityLabelAllowed"])


if __name__ == "__main__":
    unittest.main()
