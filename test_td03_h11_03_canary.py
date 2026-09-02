"""Contract tests for the H-11-03 offline dual-worker canary."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from regression.td03_h11_03_canary import run_dual_worker_load, run_fault_injection, run_offline_canary


class H1103CanaryTests(unittest.TestCase):
    def test_dual_worker_load_shares_rate_limit_and_leases(self) -> None:
        report = run_dual_worker_load(requests_per_worker=12)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["total_requests"], 24)
        self.assertEqual(report["rate_limit"]["accepted"], 12)
        self.assertEqual(report["rate_limit"]["rejected"], 12)
        self.assertEqual(report["options_owner_token_fencing"], "pass")

    def test_fault_injection_matches_shared_mode_policies(self) -> None:
        outcomes = run_fault_injection()
        self.assertEqual(outcomes["rate_limit"], "fail-closed-503")
        self.assertEqual(outcomes["cache_l2"], "local-fallback")
        self.assertEqual(outcomes["single_flight"], "local-fallback")
        self.assertEqual(outcomes["options_lease"], "local-fallback")
        self.assertEqual(outcomes["background_updater"], "skip-round")

    def test_offline_report_never_claims_real_redis(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            report = run_offline_canary()
        self.assertEqual(report["real_redis_canary"]["status"], "not-run")


if __name__ == "__main__":
    unittest.main()
