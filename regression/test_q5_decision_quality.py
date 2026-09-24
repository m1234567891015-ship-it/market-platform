"""Deterministic Q5 coverage for decision evidence, quality, and provenance."""

import unittest

from derivatives.analytics import (
    MODEL_CONFIDENCE_STATUS_UNAVAILABLE,
    build_decision_contract,
    build_decision_provenance,
    build_decision_quality,
)


class DecisionQualityTests(unittest.TestCase):
    def test_complete_evidence_and_healthy_sources(self):
        result = build_decision_quality(
            5,
            5,
            {
                "freshness_score": 95,
                "provider_health_score": 100,
                "consistency_score": 90,
                "fallback_used": False,
            },
        )
        self.assertEqual(result["evidenceScore"], 100)
        self.assertEqual(result["dataQualityScore"], 97)
        self.assertEqual(result["dataQualityStatus"], "AVAILABLE")
        self.assertEqual(result["dataQualityDimensions"]["fallbackSource"], 100)

    def test_partial_evidence_is_not_predictive_confidence(self):
        result = build_decision_quality(
            2,
            5,
            {"provider_status": "healthy", "fallback_used": True},
        )
        self.assertEqual(result["evidenceScore"], 40)
        self.assertEqual(result["dataQualityStatus"], "PARTIAL")
        self.assertEqual(result["dataQualityDimensions"]["fallbackSource"], 50)

    def test_stale_and_failed_provider_are_explicit(self):
        result = build_decision_quality(
            5,
            5,
            {"provider_status": "failed", "stale": True},
        )
        self.assertEqual(result["evidenceScore"], 100)
        self.assertEqual(result["dataQualityScore"], 33)
        self.assertEqual(result["dataQualityStatus"], "FAILED")
        self.assertEqual(result["dataQualityDimensions"]["providerHealth"], 0)
        self.assertEqual(result["dataQualityDimensions"]["freshness"], 0)

    def test_contract_keeps_calibrated_confidence_unavailable(self):
        contract = build_decision_contract(
            symbol="TXO",
            input_snapshot={"spot": 22000, "pcr": 1.05},
            decision_output={"bias": "neutral"},
            available_evidence=1,
            evidence_total=2,
            decision_context={
                "market_as_of": "2026-09-24",
                "source_updated_at": "2026-09-24T06:00:00Z",
                "decision_time": "2026-09-24T06:01:00Z",
            },
        )
        self.assertIsNone(contract["modelConfidence"])
        self.assertEqual(contract["modelConfidenceStatus"], MODEL_CONFIDENCE_STATUS_UNAVAILABLE)
        self.assertIsNone(contract["model_confidence"])
        self.assertEqual(contract["evidenceScore"], 50)
        self.assertEqual(contract["data_quality_score"], contract["dataQualityScore"])
        for key in (
            "decision_id",
            "symbol",
            "decision_time",
            "market_as_of",
            "source_updated_at",
            "model_version",
            "strategy_version",
            "input_snapshot_hash",
            "confidence_method",
            "decision_output",
        ):
            self.assertIn(key, contract)

    def test_same_snapshot_is_reproducible(self):
        context = {
            "market_as_of": "2026-09-24",
            "decision_time": "2026-09-24T06:01:00Z",
        }
        first = build_decision_provenance("TXO", {"pcr": 1.05, "spot": 22000}, {"bias": "neutral"}, context)
        second = build_decision_provenance("TXO", {"spot": 22000, "pcr": 1.05}, {"bias": "neutral"}, context)
        self.assertEqual(first["input_snapshot_hash"], second["input_snapshot_hash"])
        self.assertEqual(first["decision_id"], second["decision_id"])
        self.assertEqual(first["confidence_method"], "NOT_CALIBRATED")


if __name__ == "__main__":
    unittest.main()
