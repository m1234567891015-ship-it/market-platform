"""Regression coverage for P2-13..P2-16 provenance and CI policy."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    from regression.p2_release_provenance import CI_PATH, EVIDENCE_PATH, MANIFEST_PATH, validate
except ModuleNotFoundError:  # direct `python regression/test_...py` invocation
    from p2_release_provenance import CI_PATH, EVIDENCE_PATH, MANIFEST_PATH, validate


ROOT = Path(__file__).resolve().parent.parent


class P2ReleaseProvenanceTests(unittest.TestCase):
    def test_manifest_evidence_and_source_consistency(self) -> None:
        self.assertTrue(MANIFEST_PATH.is_file())
        self.assertTrue(EVIDENCE_PATH.is_file())
        self.assertEqual(validate(), [])

    def test_manifest_records_dirty_state_and_real_head(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        identity = manifest["source_identity"]
        self.assertRegex(identity["git_head_sha"], r"^[0-9a-f]{40}$")
        self.assertIsInstance(identity["worktree_dirty"], bool)
        if identity["worktree_dirty"]:
            self.assertTrue(identity["status_entries"])
            self.assertTrue(identity["worktree_state_sha256"])

    def test_ci_definition_is_fail_closed_and_scope_complete(self) -> None:
        workflow = CI_PATH.read_text(encoding="utf-8")
        required = [
            "test_p2_release_provenance.py",
            "test_p0_quant_integrity",
            "test_p2_backend_boundaries",
            "test_p2_frontend_contract.js",
            "test_td02_01_dependency_matrix",
            "test_options_strategy_analyzer.js",
            "test_derivatives_platform.py",
            "security_guardrail_check.py",
            "e2e_smoke.py",
            "verify_against_baseline.py --quick",
            "git diff --check",
        ]
        for token in required:
            self.assertIn(token, workflow)
        for forbidden in ("continue-on-error", "|| true", "--skip", "--ignore-failure"):
            self.assertNotIn(forbidden, workflow)


if __name__ == "__main__":
    unittest.main()
