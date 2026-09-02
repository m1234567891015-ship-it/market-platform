import json
import subprocess
import sys
import unittest
from pathlib import Path

import regression.td03_shared_state_canary as canary


class TD03SharedStateCanaryTests(unittest.TestCase):
    def test_offline_canary_preflight(self) -> None:
        report = canary.run_offline_canary()
        self.assertEqual(report["deployment"]["workers"], {"Procfile": 1, "render.yaml": 1})
        self.assertEqual(report["normal"]["status"], "pass")
        self.assertEqual(report["fault_injection"]["status"], "pass")
        self.assertEqual(report["real_redis_canary"]["status"], "not-run")

    def test_script_emits_success_marker(self) -> None:
        root = Path(__file__).resolve().parent
        result = subprocess.run(
            [sys.executable, str(root / "regression" / "td03_shared_state_canary.py")],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        self.assertIn("TD03_SHARED_STATE_CANARY_OFFLINE_OK", result.stdout)
        report_text = result.stdout.rsplit("\nTD03_SHARED_STATE_CANARY_OFFLINE_OK", 1)[0]
        report = json.loads(report_text)
        self.assertEqual(report["normal"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
