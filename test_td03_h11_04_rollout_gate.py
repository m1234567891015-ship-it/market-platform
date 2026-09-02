"""Tests for the read-only H-11-04 rollout gate."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from regression.td03_h11_04_rollout_gate import rollout_gate


class H1104RolloutGateTests(unittest.TestCase):
    def test_gate_blocks_without_redis_staging_evidence(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            report = rollout_gate()
        self.assertFalse(report["eligible"])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["checks"]["redis_url"]["status"], "blocked")
        self.assertEqual(report["checks"]["real_redis_health"]["status"], "not-run")
        self.assertEqual(report["checks"]["h11_03_real_dual_worker"]["status"], "not-run")
        self.assertEqual(report["checks"]["current_safe_mode"]["status"], "pass")
        self.assertEqual(report["checks"]["deployment_worker_gate"]["status"], "pass")

    def test_gate_never_exposes_redis_url(self) -> None:
        with patch.dict(os.environ, {"MARKET_PULSE_REDIS_URL": "redis://secret.example/0"}, clear=True):
            report = rollout_gate()
        self.assertEqual(report["checks"]["redis_url"]["value"], "present-redacted")
        self.assertNotIn("secret.example", str(report))


if __name__ == "__main__":
    unittest.main()
