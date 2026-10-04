"""P1-02 regression coverage for scenario-weight/probability semantics."""

from pathlib import Path
import unittest

from derivatives.analytics import build_decision_contract
from derivatives.calibration import (
    CALIBRATION_STATUS_CALIBRATED,
    CALIBRATION_STATUS_INSUFFICIENT_SAMPLE,
    CALIBRATION_STATUS_UNCALIBRATED,
    probability_label_allowed,
    build_oos_calibration_report,
)


ROOT = Path(__file__).resolve().parents[1]


def read_source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class ScenarioWeightSemanticTests(unittest.TestCase):
    def test_a_heuristic_weights_are_labeled_and_never_probability(self):
        options = read_source("js/page-global-market-options.js")
        self.assertIn('scenarioSemanticStatus: "HEURISTIC_SCENARIO_WEIGHT"', options)
        self.assertIn("probabilityLabelAllowed: false", options)
        self.assertIn('probabilitiesDeprecated: true', options)

    def test_b_weights_summing_to_100_do_not_open_probability_gate(self):
        weights = {"bullish": 58, "neutral": 27, "bearish": 15}
        self.assertEqual(sum(weights.values()), 100)
        self.assertFalse(probability_label_allowed(CALIBRATION_STATUS_UNCALIBRATED))
        self.assertFalse(probability_label_allowed(None))
        contract = build_decision_contract(
            symbol="TEST",
            input_snapshot={"scenarioWeights": weights},
            decision_output={"bias": "bullish"},
            available_evidence=3,
            evidence_total=3,
        )
        self.assertFalse(contract["probabilityLabelAllowed"])

    def test_c_only_calibrated_status_opens_probability_label_gate(self):
        self.assertTrue(probability_label_allowed(CALIBRATION_STATUS_CALIBRATED))
        self.assertFalse(probability_label_allowed(CALIBRATION_STATUS_UNCALIBRATED))
        self.assertFalse(probability_label_allowed(CALIBRATION_STATUS_INSUFFICIENT_SAMPLE))

    def test_d_oos_sample_count_alone_does_not_claim_calibration(self):
        report = build_oos_calibration_report([0.5] * 30, [1, 0] * 15)
        self.assertEqual(report["calibrationStatus"], CALIBRATION_STATUS_UNCALIBRATED)
        self.assertFalse(report["probabilityLabelAllowed"])
        too_small = build_oos_calibration_report([0.5] * 2, [1, 0])
        self.assertEqual(too_small["calibrationStatus"], CALIBRATION_STATUS_INSUFFICIENT_SAMPLE)
        self.assertFalse(too_small["probabilityLabelAllowed"])

    def test_e_legacy_probability_alias_is_deprecated_and_not_consumed(self):
        options = read_source("js/page-global-market-options.js")
        self.assertIn("probabilities: { ...scenarioWeights }", options)
        self.assertNotRegex(options, r"\.(?:probabilities)(?:\.|\[|\?)")
        self.assertIn("scenarioWeights", options)

    def test_f_user_facing_scenario_consumers_use_weight_semantics(self):
        options = read_source("js/page-global-market-options.js")
        derivatives = read_source("js/page-global-market-derivatives.js")
        futures = read_source("js/page-global-market-futures.js")
        shared = read_source("js/render-shared.js")
        stock_detail = read_source("js/stock-detail.js")
        builders = read_source("builders.py")

        self.assertIn("不代表統計漲跌機率", options)
        self.assertIn("不代表統計漲跌機率", derivatives)
        self.assertIn("不代表統計漲跌機率", futures)
        self.assertIn("不代表統計漲跌機率", shared)
        self.assertIn("不代表統計漲跌機率", stock_detail)
        self.assertIn("情境權重提高", builders)
        self.assertNotIn("短線上攻機率提高", builders)
        self.assertNotIn("預測機率", options + derivatives + futures + shared + stock_detail)

    def test_g_api_contract_uses_the_canonical_calibration_gate(self):
        analytics = read_source("derivatives/analytics.py")
        route_contract = read_source("routes_derivatives.py")
        self.assertIn("probability_label_allowed(CALIBRATION_STATUS_UNAVAILABLE)", analytics)
        self.assertIn('"probabilityLabelAllowed": "Only true when calibrationStatus is CALIBRATED', route_contract)


if __name__ == "__main__":
    unittest.main()
