"""Unit tests for the read-only R3 infrastructure drift verifier."""

from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify-infra-drift.py"
SPEC = importlib.util.spec_from_file_location("verify_infra_drift", SCRIPT)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


RENDER_YAML = """services:
  - type: web
    name: taiwan-market-pulse
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:$PORT app:app
    healthCheckPath: /api/health
    autoDeploy: false
"""

CURRENT_DOCUMENTATION = """# Cloud Deployment Notes

Render plan: `free`.

`MARKET_PULSE_CACHE_FILE=/tmp/market-pulse-cache.json`
`DERIVATIVES_DB_PATH=/tmp/derivatives-platform.sqlite3`

The filesystem is ephemeral and may be lost after redeploy, restart, or cold start /
instance replacement.

Persistence redesign / PostgreSQL / Redis / persistent disk migration belongs to R4 Data Durability.
R3 does not authorize persistence migration.
"""

SYNTHETIC_CLOUDFLARE = {
    "production_account_verified": True,
    "evidence_label": "SYNTHETIC TEST FIXTURE - NOT PRODUCTION EVIDENCE",
}

PROCFILE = "web: gunicorn --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:$PORT app:app\n"
CLOUDFLARE_CONFIG = """{
  "name": "market-pulse-hybrid-local",
  "workers_dev": false
}
"""


def _observation(*, branch_drift: bool = False, cloudflare: object = None) -> dict[str, object]:
    return {
        "github": {
            "main_commit": "main-sha",
            "cloudflare_pages_local_commit": "pages-sha" if branch_drift else "main-sha",
            "main_ahead_by": 1,
            "main_behind_by": 0,
        },
        "render": {
            "repo": "m1234567891015-ship-it/market-platform",
            "branch": "main",
            "live_commit": "main-sha",
            "build_command": "pip install -r requirements.txt",
            "start_command": "gunicorn --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:$PORT app:app",
            "health_check_path": "/api/health",
            "plan": "free",
            "auto_deploy": False,
        },
        "cloudflare": cloudflare,
    }


class InfraDriftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "cloudflare").mkdir()
        (self.root / "render.yaml").write_text(RENDER_YAML, encoding="utf-8")
        (self.root / "CLOUD_DEPLOYMENT.md").write_text(CURRENT_DOCUMENTATION, encoding="utf-8")
        (self.root / "Procfile").write_text(PROCFILE, encoding="utf-8")
        (self.root / "cloudflare" / "wrangler.jsonc").write_text(CLOUDFLARE_CONFIG, encoding="utf-8")
        (self.root / "cloudflare" / "README.md").write_text("local-only\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, observation: object, *, raw: str | None = None) -> tuple[int, dict[str, object]]:
        path = self.root / "observation.json"
        path.write_text(raw if raw is not None else json.dumps(observation), encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            code = verifier.main(["--root", str(self.root), "--observation", str(path)])
        return code, json.loads(output.getvalue())

    @staticmethod
    def _checks(report: dict[str, object]) -> dict[str, dict[str, object]]:
        return {item["id"]: item for item in report["checks"]}

    def test_t01_render_yaml_autodeploy_false_parses(self) -> None:
        contract = verifier.parse_render_contract(self.root / "render.yaml")
        self.assertIs(contract["autoDeploy"], False)

    def test_t01_all_checks_use_complete_schema_and_meaningful_reasons(self) -> None:
        required = {"id", "component", "expected", "actual", "status", "classification", "reason"}
        _, report = self._run(_observation(cloudflare=SYNTHETIC_CLOUDFLARE))
        checks = self._checks(report)
        self.assertEqual(set(checks), {f"D{i:02d}" for i in range(1, 12)})
        for check in checks.values():
            self.assertTrue(required <= set(check))
            self.assertIsInstance(check["reason"], str)
            self.assertTrue(check["reason"].strip())
            if check["id"] != "D11":
                self.assertIn("expected and actual match", check["reason"])

    def test_t02_repo_and_render_autodeploy_match(self) -> None:
        code, report = self._run(_observation())
        check = self._checks(report)["D03"]
        self.assertIsInstance(check["expected"], bool)
        self.assertIsInstance(check["actual"], bool)
        self.assertEqual(code, 2)
        self.assertEqual(check["status"], "MATCH")
        self.assertEqual(check["classification"], "NO_ACTION_REQUIRED")

    def test_t03_autodeploy_mismatch_is_remediation_exit_three(self) -> None:
        observation = _observation()
        observation["render"]["auto_deploy"] = True
        code, report = self._run(observation)
        check = self._checks(report)["D03"]
        self.assertEqual(check["status"], "DRIFT")
        self.assertEqual(check["classification"], "REMEDIATION_REQUIRED")
        self.assertEqual(code, 3)

    def test_t04_github_main_equals_render_live_commit(self) -> None:
        code, report = self._run(_observation())
        check = self._checks(report)["D01"]
        self.assertEqual(check["component"], "github.main_commit_vs_render.live_commit")
        self.assertEqual(check["expected"], "main-sha")
        self.assertEqual(check["actual"], "main-sha")
        self.assertEqual(check["status"], "MATCH")
        self.assertEqual(code, 2)

    def test_t05_github_main_mismatch_is_remediation(self) -> None:
        observation = _observation()
        observation["render"]["live_commit"] = "different-sha"
        code, report = self._run(observation)
        check = self._checks(report)["D01"]
        self.assertEqual(check["status"], "DRIFT")
        self.assertEqual(check["classification"], "REMEDIATION_REQUIRED")
        self.assertEqual(code, 3)

    def test_t06_cloudflare_pages_sha_drift_is_defer_r8(self) -> None:
        code, report = self._run(_observation(branch_drift=True, cloudflare=SYNTHETIC_CLOUDFLARE))
        check = self._checks(report)["D02"]
        self.assertEqual(check["component"], "github.main_vs_cloudflare_pages_local")
        self.assertEqual(check["expected"], "main-sha")
        self.assertEqual(check["actual"], "pages-sha")
        self.assertEqual(check["status"], "DRIFT")
        self.assertEqual(check["classification"], "DEFER_R8")
        self.assertIn("deferred to R8", check["reason"])
        self.assertEqual(code, 0)

    def test_t07_missing_cloudflare_observation_is_unverified_exit_two(self) -> None:
        code, report = self._run(_observation())
        check = self._checks(report)["D11"]
        self.assertEqual(check["status"], "UNVERIFIED")
        self.assertEqual(check["classification"], "UNVERIFIED")
        self.assertIsNone(check["actual"])
        self.assertIn("production account evidence", check["reason"])
        self.assertIn("absent", check["reason"])
        self.assertEqual(code, 2)

    def test_t08_malformed_observation_is_exit_four(self) -> None:
        code, report = self._run({}, raw="{not-json")
        self.assertEqual(code, 4)
        self.assertEqual(report["exit_code"], 4)
        self.assertEqual(report["overall_status"], "INVALID_INPUT")

    def test_t09_build_command_comparison(self) -> None:
        observation = _observation(cloudflare={"production_account_verified": True})
        code, report = self._run(observation)
        match_check = self._checks(report)["D04"]
        self.assertEqual(match_check["status"], "MATCH")
        self.assertIn("expected and actual match", match_check["reason"])
        self.assertNotIn("expected and actual differ", match_check["reason"])
        self.assertEqual(code, 0)
        observation["render"]["build_command"] = "pip install other.txt"
        code, report = self._run(observation)
        drift_check = self._checks(report)["D04"]
        self.assertEqual(drift_check["status"], "DRIFT")
        self.assertEqual(drift_check["classification"], "REMEDIATION_REQUIRED")
        self.assertIn("expected and actual differ", drift_check["reason"])
        self.assertNotIn("matches", drift_check["reason"].lower())
        self.assertEqual(code, 3)
        for field, check_id in (
            ("build_command", "D04"),
            ("start_command", "D05"),
            ("health_check_path", "D06"),
            ("plan", "D07"),
        ):
            missing_observation = _observation(cloudflare={"production_account_verified": True})
            missing_observation["render"][field] = None
            code, report = self._run(missing_observation)
            missing_check = self._checks(report)[check_id]
            self.assertEqual(missing_check["status"], "UNVERIFIED")
            self.assertEqual(missing_check["classification"], "UNVERIFIED")
            self.assertIn("actual observation is missing", missing_check["reason"])
            self.assertNotIn("matches", missing_check["reason"].lower())
            self.assertEqual(code, 2)

    def test_t10_start_command_comparison(self) -> None:
        observation = _observation(cloudflare={"production_account_verified": True})
        observation["render"]["start_command"] = "gunicorn other-app:app"
        code, report = self._run(observation)
        check = self._checks(report)["D05"]
        self.assertEqual(check["status"], "DRIFT")
        self.assertEqual(check["classification"], "REMEDIATION_REQUIRED")
        self.assertIn("expected and actual differ", check["reason"])
        self.assertNotIn("matches", check["reason"].lower())
        self.assertEqual(code, 3)

    def test_t11_health_path_comparison(self) -> None:
        observation = _observation(cloudflare={"production_account_verified": True})
        observation["render"]["health_check_path"] = "/wrong-health"
        code, report = self._run(observation)
        check = self._checks(report)["D06"]
        self.assertEqual(check["status"], "DRIFT")
        self.assertEqual(check["classification"], "REMEDIATION_REQUIRED")
        self.assertIn("expected and actual differ", check["reason"])
        self.assertNotIn("matches", check["reason"].lower())
        self.assertEqual(code, 3)

    def test_t12_plan_comparison(self) -> None:
        observation = _observation(cloudflare={"production_account_verified": True})
        observation["render"]["plan"] = "starter"
        code, report = self._run(observation)
        check = self._checks(report)["D07"]
        self.assertEqual(check["status"], "DRIFT")
        self.assertEqual(check["classification"], "REMEDIATION_REQUIRED")
        self.assertIn("expected and actual differ", check["reason"])
        self.assertNotIn("matches", check["reason"].lower())
        self.assertEqual(code, 3)

    def test_t13_procfile_comparison(self) -> None:
        code, report = self._run(_observation(cloudflare={"production_account_verified": True}))
        self.assertEqual(self._checks(report)["D09"]["status"], "MATCH")
        self.assertEqual(code, 0)

    def test_t14_current_documentation_topology_matches(self) -> None:
        code, report = self._run(_observation(cloudflare=SYNTHETIC_CLOUDFLARE))
        check = self._checks(report)["D08"]
        self.assertEqual(check["component"], "deployment.persistence_documentation")
        self.assertIsInstance(check["expected"], dict)
        self.assertIsInstance(check["actual"], dict)
        self.assertEqual(check["status"], "MATCH")
        self.assertEqual(code, 0)

    def test_t15_stale_var_data_topology_is_drift(self) -> None:
        stale = CURRENT_DOCUMENTATION + "\nPersistent disk mount: /var/data\n"
        (self.root / "CLOUD_DEPLOYMENT.md").write_text(stale, encoding="utf-8")
        code, report = self._run(_observation(cloudflare={"production_account_verified": True}))
        check = self._checks(report)["D08"]
        self.assertEqual(check["status"], "DRIFT")
        self.assertEqual(check["classification"], "REMEDIATION_REQUIRED")
        self.assertEqual(code, 3)

    def test_t16_tool_has_no_remote_mutation_surface(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("requests", "urllib.request", "subprocess", "git push", "render_api"):
            self.assertNotIn(forbidden, source)
        self.assertNotIn("write_text", source)

    def test_t17_fully_matching_fixture_exits_zero(self) -> None:
        self.assertIn("SYNTHETIC TEST FIXTURE", SYNTHETIC_CLOUDFLARE["evidence_label"])
        self.assertIn("NOT PRODUCTION EVIDENCE", SYNTHETIC_CLOUDFLARE["evidence_label"])
        code, report = self._run(_observation(cloudflare=SYNTHETIC_CLOUDFLARE))
        self.assertEqual(code, 0)
        self.assertEqual(report["overall_status"], "MATCH")
        self.assertEqual(report["counts"]["remediation_required"], 0)
        self.assertEqual(report["counts"]["unverified"], 0)

    def test_t12_remediation_plus_unverified_keeps_exit_three(self) -> None:
        observation = _observation()
        observation["render"]["auto_deploy"] = True
        code, report = self._run(observation)
        self.assertEqual(code, 3)
        self.assertEqual(report["counts"]["remediation_required"], 1)
        self.assertEqual(report["counts"]["unverified"], 1)

    def test_t13_invalid_input_dominates_other_possible_outcomes(self) -> None:
        observation = _observation()
        observation["render"]["auto_deploy"] = True
        code, report = self._run(observation, raw="{not-json")
        self.assertEqual(code, 4)
        self.assertEqual(report["exit_code"], 4)

    def test_t14_report_counts_match_check_objects(self) -> None:
        _, report = self._run(_observation(branch_drift=True))
        checks = report["checks"]
        counts = report["counts"]
        self.assertEqual(counts["match"], sum(c["status"] == "MATCH" for c in checks))
        self.assertEqual(counts["drift"], sum(c["status"] == "DRIFT" for c in checks))
        self.assertEqual(counts["unverified"], sum(c["status"] == "UNVERIFIED" for c in checks))
        self.assertEqual(
            counts["remediation_required"],
            sum(c["classification"] == "REMEDIATION_REQUIRED" for c in checks),
        )
        self.assertEqual(counts["defer_r8"], sum(c["classification"] == "DEFER_R8" for c in checks))

    def test_case_a_cloudflare_unavailable_is_fail_closed_without_branch_remediation(self) -> None:
        code, report = self._run(_observation(branch_drift=True))
        checks = self._checks(report)
        self.assertEqual(checks["D01"]["status"], "MATCH")
        self.assertEqual(checks["D02"]["classification"], "DEFER_R8")
        for check_id in ("D03", "D04", "D05", "D06", "D07", "D08", "D09", "D10"):
            self.assertEqual(checks[check_id]["status"], "MATCH")
        self.assertEqual(checks["D11"]["status"], "UNVERIFIED")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
