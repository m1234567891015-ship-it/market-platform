"""Regression coverage for P2-13..P2-16 provenance and CI policy."""
from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

try:
    import regression.p2_release_provenance as provenance
except ModuleNotFoundError:  # direct `python regression/test_...py` invocation
    import p2_release_provenance as provenance

CI_PATH = provenance.CI_PATH
EVIDENCE_PATH = provenance.EVIDENCE_PATH
MANIFEST_PATH = provenance.MANIFEST_PATH
validate = provenance.validate
validate_committed_source_identity = provenance.validate_committed_source_identity


ROOT = Path(__file__).resolve().parent.parent


class P2ReleaseProvenanceTests(unittest.TestCase):
    def _validate_temporary_binding(self, manifest: dict, evidence: dict) -> list[str]:
        with tempfile.TemporaryDirectory(prefix="p2-provenance-test-") as directory:
            root = Path(directory)
            manifest_path = root / "manifest.json"
            evidence_path = root / "evidence.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8", newline="\n")
            with patch.object(provenance, "MANIFEST_PATH", manifest_path), patch.object(provenance, "EVIDENCE_PATH", evidence_path):
                return provenance.validate()

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

    def test_generation_context_is_informational_for_clean_ci(self) -> None:
        identity = {
            "committed_source_sha": "a" * 40,
            "git_head_sha": "a" * 40,
            "worktree_dirty": True,
            "worktree_state_sha256": "windows-only-context",
            "status_entries": [" M unrelated.txt"],
        }
        with patch.object(provenance, "is_ancestor", return_value=True):
            self.assertEqual(
                validate_committed_source_identity(
                    identity,
                    "b" * 40,
                    [],
                    ci_environment=True,
                ),
                [],
            )

    def test_bound_source_sha_equal_to_head_passes(self) -> None:
        identity = {"committed_source_sha": "a" * 40}
        self.assertEqual(
            validate_committed_source_identity(
                identity,
                "a" * 40,
                [],
                ci_environment=True,
            ),
            [],
        )

    def test_p2_source_drift_after_bound_commit_fails_closed(self) -> None:
        identity = {"committed_source_sha": "a" * 40}
        with patch.object(provenance, "is_ancestor", return_value=True):
            errors = validate_committed_source_identity(
                identity,
                "b" * 40,
                [],
                ci_environment=True,
                changed_paths=["app.py"],
            )
        self.assertTrue(any("P2 source scope drift" in error for error in errors))

    def test_invalid_source_sha_fails_closed(self) -> None:
        errors = validate_committed_source_identity(
            {"committed_source_sha": "not-a-sha"},
            "b" * 40,
            [],
            ci_environment=True,
        )
        self.assertEqual(errors, ["manifest does not contain a real 40-character committed source SHA"])

    def test_stale_evidence_hash_fails_closed(self) -> None:
        identity = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["source_identity"]
        errors = self._validate_temporary_binding(
            {
                "source_identity": identity,
                "required_source_files": [{"path": "app.py", "sha256": "0" * 64}],
                "evidence_artifacts": [],
            },
            {"source_identity": identity, "records": []},
        )
        self.assertIn("hash mismatch: app.py", errors)

    def test_missing_bound_file_fails_closed(self) -> None:
        identity = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["source_identity"]
        errors = self._validate_temporary_binding(
            {
                "source_identity": identity,
                "required_source_files": [{"path": "missing-bound-file.txt", "sha256": "0" * 64}],
                "evidence_artifacts": [],
            },
            {"source_identity": identity, "records": []},
        )
        self.assertIn("missing bound file: missing-bound-file.txt", errors)

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
