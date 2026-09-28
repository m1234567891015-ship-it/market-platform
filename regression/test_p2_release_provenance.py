"""Regression coverage for P2-13..P2-16 provenance and CI policy."""
from __future__ import annotations

import json
import subprocess
import sys
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

    def test_validator_accepts_consistent_temporary_manifest(self) -> None:
        self.assertTrue(MANIFEST_PATH.is_file())
        self.assertTrue(EVIDENCE_PATH.is_file())
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        head = provenance.run("git", "rev-parse", "--verify", "HEAD")
        identity = dict(manifest["source_identity"])
        identity["committed_source_sha"] = head
        identity["git_head_sha"] = head
        manifest["source_identity"] = identity
        evidence["source_identity"] = identity
        for key in ("required_source_files", "evidence_artifacts"):
            for record in manifest[key]:
                path = ROOT / record["path"]
                record["sha256"] = provenance.sha256(path)
                record["bytes"] = path.stat().st_size
        with tempfile.TemporaryDirectory(prefix="p2-provenance-consistent-") as directory:
            manifest_path = Path(directory) / "manifest.json"
            evidence_path = Path(directory) / "evidence.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8", newline="\n")
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8", newline="\n")
            with (
                patch.object(provenance, "MANIFEST_PATH", manifest_path),
                patch.object(provenance, "EVIDENCE_PATH", evidence_path),
                patch.object(provenance, "git_status", return_value=[]),
                patch.object(provenance, "source_scope_drift", return_value=[]),
            ):
                self.assertEqual(validate(), [])

    def test_successful_command_execution_produces_pass(self) -> None:
        spec = {
            "id": "controlled-success",
            "command": "python -c <success fixture>",
            "argv": ("-c", "print('controlled success')"),
            "python": True,
            "artifacts": (),
        }
        actual = provenance.run_evidence_command(provenance.command_invocations(spec)[0])
        with patch.object(provenance, "run_evidence_command", return_value=actual):
            record = provenance.evidence_record(spec)
        self.assertEqual(record["result"], "PASS")
        self.assertEqual(actual.returncode, 0)

    def test_nonzero_command_execution_cannot_produce_pass(self) -> None:
        spec = {
            "id": "controlled-failure",
            "command": "python -c <failure fixture>",
            "argv": ("-c", "import sys; print('controlled failure'); sys.exit(7)"),
            "python": True,
            "artifacts": (),
        }
        actual = provenance.run_evidence_command(provenance.command_invocations(spec)[0])
        with patch.object(provenance, "run_evidence_command", return_value=actual):
            record = provenance.evidence_record(spec)
        self.assertEqual(record["result"], "FAIL")
        self.assertEqual(actual.returncode, 7)

    def test_command_timeout_propagates_without_pass_record(self) -> None:
        spec = {
            "id": "controlled-timeout",
            "command": "python -c <timeout fixture>",
            "argv": ("-c", "pass"),
            "python": True,
            "artifacts": (),
        }
        timeout = subprocess.TimeoutExpired(cmd=spec["command"], timeout=1)
        with patch.object(provenance, "run_evidence_command", side_effect=timeout):
            with self.assertRaises(subprocess.TimeoutExpired):
                provenance.evidence_record(spec)

    def test_evidence_records_invoke_runner_for_every_command(self) -> None:
        calls: list[tuple[str, ...]] = []

        def successful_runner(argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            output = "VERIFY_OK\n" if argv[-1:] == ("--full",) else "controlled success"
            return subprocess.CompletedProcess(argv, 0, output, "")

        with patch.object(provenance, "run_evidence_command", side_effect=successful_runner):
            records = provenance.evidence_records({})
        expected_invocations = sum(len(provenance.command_invocations(spec)) for spec in provenance.EVIDENCE_COMMANDS)
        self.assertEqual(len(calls), expected_invocations)
        self.assertEqual(len(records), len(provenance.EVIDENCE_COMMANDS))
        self.assertTrue(all(record["result"] == "PASS" for record in records))

    def test_e2e_runner_injects_unique_temporary_paths_and_cleans_them(self) -> None:
        observed: list[tuple[str, str]] = []

        def capture_run(argv, **kwargs):
            db_path = Path(kwargs["env"]["DERIVATIVES_DB_PATH"])
            cache_path = Path(kwargs["env"]["MARKET_PULSE_CACHE_FILE"])
            observed.append((str(db_path), str(cache_path)))
            self.assertNotIn(ROOT, db_path.parents)
            self.assertNotIn(ROOT, cache_path.parents)
            self.assertTrue(db_path.parent.is_dir())
            return subprocess.CompletedProcess(argv, 0, "E2E_SMOKE_OK", "")

        with patch.object(provenance.subprocess, "run", side_effect=capture_run):
            first = provenance.run_evidence_command((sys.executable, "e2e_smoke.py"))
            second = provenance.run_evidence_command((sys.executable, "e2e_smoke.py"))
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        self.assertEqual(len(observed), 2)
        self.assertNotEqual(observed[0][0], observed[1][0])
        self.assertNotEqual(observed[0][1], observed[1][1])
        for db_path, cache_path in observed:
            self.assertFalse(Path(db_path).parent.exists(), "temporary E2E workspace should be cleaned")
            self.assertFalse(Path(cache_path).parent.exists(), "temporary E2E workspace should be cleaned")

    def _full_baseline_result(self, output: str, returncode: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(("verify_against_baseline.py", "--full"), returncode, output, "")

    def test_full_baseline_raw_verify_ok_decides_pass(self) -> None:
        decision = provenance.full_baseline_policy(self._full_baseline_result("VERIFY_OK\n", 0))
        self.assertEqual((decision["raw_result"], decision["evidence_decision"]), ("VERIFY_OK", "PASS"))

    def test_full_baseline_exact_e1_only_failure_decides_pass(self) -> None:
        output = "[FAIL] frontend_check.py --compare\n  [FAIL] [畫面差異] derivatives-status.html: 截圖像素差異率 13.81% > 2.00%\nVERIFY_FAILED\n"
        decision = provenance.full_baseline_policy(self._full_baseline_result(output, 1))
        self.assertEqual(decision["raw_result"], "VERIFY_FAILED")
        self.assertEqual(decision["evidence_decision"], "PASS")
        self.assertEqual(decision["new_deterministic_failures"], [])
        self.assertEqual(decision["worsened_failures"], [])

    def test_full_baseline_recognized_environment_noise_with_no_delta_passes(self) -> None:
        live_line = "    - external /api/twse/live-sectors: unknown upstream label=502,error_code=LIVE_SECTORS_UNAVAILABLE"
        current = "\n".join((
            "[FAIL] frontend_check.py --compare",
            "  [FAIL] [DIFF] derivatives-status.html: visual diff 13.81% > 2.0%",
            "[FAIL] API live endpoint contract",
            live_line,
            "[EXTERNAL] home.html: 1 external errors (external_font,external_network)",
            "VERIFY_FAILED",
        ))
        baseline = "\n".join(("[FAIL] API live endpoint contract", live_line, "VERIFY_FAILED"))
        decision = provenance.full_baseline_policy(
            self._full_baseline_result(current, 1),
            baseline_result=self._full_baseline_result(baseline, 1),
        )
        self.assertEqual(decision["evidence_decision"], "PASS")
        self.assertEqual(decision["new_deterministic_failures"], [])
        self.assertTrue(any("clean P0 comparison matched" in item for item in decision["exceptions"]))

    def test_full_baseline_environment_status_without_matching_clean_delta_fails(self) -> None:
        current = "\n".join((
            "[FAIL] frontend_check.py --compare",
            "  [FAIL] [DIFF] derivatives-status.html: visual diff 13.81% > 2.0%",
            "[FAIL] API live endpoint contract",
            "external /api/twse/live-sectors: unknown upstream label=502,error_code=LIVE_SECTORS_UNAVAILABLE",
            "VERIFY_FAILED",
        ))
        baseline = "VERIFY_OK"
        decision = provenance.full_baseline_policy(
            self._full_baseline_result(current, 1),
            baseline_result=self._full_baseline_result(baseline, 0),
        )
        self.assertEqual(decision["evidence_decision"], "FAIL")

    def test_full_baseline_new_deterministic_failure_decides_fail(self) -> None:
        output = "[FAIL] interaction_check.py --compare\n    - new page interaction mismatch\nVERIFY_FAILED\n"
        decision = provenance.full_baseline_policy(self._full_baseline_result(output, 1))
        self.assertEqual(decision["evidence_decision"], "FAIL")

    def test_full_baseline_worsened_e1_decides_fail(self) -> None:
        output = "[FAIL] frontend_check.py --compare\n  [FAIL] [畫面差異] derivatives-status.html: 截圖像素差異率 13.82% > 2.00%\nVERIFY_FAILED\n"
        decision = provenance.full_baseline_policy(self._full_baseline_result(output, 1))
        self.assertEqual(decision["evidence_decision"], "FAIL")

    def test_full_baseline_unknown_failure_decides_fail(self) -> None:
        output = "[FAIL] api_live.py\nHTTP 502 Bad Gateway\nVERIFY_FAILED\n"
        decision = provenance.full_baseline_policy(self._full_baseline_result(output, 1))
        self.assertEqual(decision["evidence_decision"], "FAIL")

    def test_full_baseline_unclassifiable_failure_decides_fail(self) -> None:
        decision = provenance.full_baseline_policy(self._full_baseline_result("unexpected output", 1))
        self.assertEqual(decision["raw_result"], "UNCLASSIFIABLE")
        self.assertEqual(decision["evidence_decision"], "FAIL")

    def test_full_baseline_exit_code_cannot_be_ignored_for_unknown_failure(self) -> None:
        output = "[FAIL] api_live.py\nHTTP 502 Bad Gateway\nVERIFY_FAILED\n"
        decision = provenance.full_baseline_policy(self._full_baseline_result(output, 1))
        self.assertEqual(decision["raw_result"], "VERIFY_FAILED")
        self.assertEqual(decision["evidence_decision"], "FAIL")

    def test_full_baseline_failed_marker_with_zero_exit_still_fails(self) -> None:
        output = "[FAIL] frontend_check.py --compare\n  [FAIL] [DIFF] derivatives-status.html: visual diff 13.81% > 2.0%\nVERIFY_FAILED\n"
        decision = provenance.full_baseline_policy(self._full_baseline_result(output, 0))
        self.assertEqual(decision["raw_result"], "VERIFY_FAILED")
        self.assertEqual(decision["evidence_decision"], "FAIL")

    def test_failed_evidence_prevents_release_proof_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p2-provenance-no-write-") as directory:
            proof_dir = Path(directory) / "release_proof"
            evidence_path = proof_dir / "p2_test_evidence.json"
            manifest_path = proof_dir / "p2_release_manifest.json"
            failed = [{"id": "controlled-failure", "result": "FAIL"}]
            with (
                patch.object(provenance, "PROOF_DIR", proof_dir),
                patch.object(provenance, "EVIDENCE_PATH", evidence_path),
                patch.object(provenance, "MANIFEST_PATH", manifest_path),
                patch.object(provenance, "source_identity", return_value={}),
                patch.object(provenance, "evidence_records", return_value=failed),
                patch.object(provenance, "write_json") as write_json,
            ):
                with self.assertRaises(provenance.EvidenceExecutionFailure):
                    provenance.write_manifest()
            write_json.assert_not_called()
            self.assertFalse(evidence_path.exists())
            self.assertFalse(manifest_path.exists())

    def test_evidence_record_schema_is_deterministic_and_has_no_runtime_metadata(self) -> None:
        spec = {
            "id": "controlled-schema",
            "command": "python -c <success fixture>",
            "argv": ("-c", "pass"),
            "python": True,
            "artifacts": ("example.json",),
        }
        record = provenance.evidence_record(spec)
        serialized = json.dumps(record, sort_keys=True)
        self.assertEqual(json.loads(serialized), record)
        self.assertEqual(set(record), {"id", "command", "result", "artifacts"})

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
