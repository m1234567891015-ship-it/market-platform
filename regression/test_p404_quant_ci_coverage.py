from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "P4_04_QUANT_CI_ORPHAN_REGRESSION_CONTRACT.md"
MANIFEST = ROOT / "regression" / "quant_regression_manifest.json"
INVENTORY = ROOT / "docs" / "P4_04_QUANT_REGRESSION_INVENTORY.md"
RUNNER = ROOT / "regression" / "run_quant_regressions.py"
WORKFLOW = ROOT / ".github" / "workflows" / "p1-quality-gate.yml"
EXPECTED_CONTRACT_SHA256 = "1c29612d28801cc3787ebe7794994f6f0f323f1ff13d02fbafc0effe9946df65"
EXPECTED_QUANT_TESTS = (
    "test_derivatives_platform.py",
    "regression/test_p0_quant_integrity.py",
    "regression/test_p0a_market_time_integrity.py",
    "regression/test_p0b_futures_asset_cost_model.js",
    "regression/test_p0b_futures_execution_costs.js",
    "regression/test_p0b1_futures_backtest_cost_wiring.js",
    "regression/test_p1_options_execution.js",
    "regression/test_p1_options_liquidity.js",
    "regression/test_p1_point_in_time.js",
    "regression/test_p1_portfolio_historical_var.js",
    "regression/test_p1_portfolio_risk_contribution.js",
    "regression/test_p1c_sharpe_return_semantics.js",
    "regression/test_p1d_decision_outcome_ledger.py",
    "regression/test_p1d_p0b_cost_contract.py",
    "regression/test_p1_02_scenario_weight_semantics.py",
    "regression/test_options_strategy_analyzer.js",
    "regression/test_p2_asset_cost_contract.js",
    "regression/test_q2_backtest_methodology.js",
    "regression/test_q3_risk_metric.js",
    "regression/test_p2_01_decision_ledger.py",
    "regression/test_p2_02_outcome_evaluation.py",
    "regression/test_p2_03_probability_forecast.py",
    "regression/test_p203_amendment_002_closure.py",
    "regression/test_p203_historical_research_replay.py",
    "regression/test_p203_historical_research_v1r1.py",
    "regression/test_p203_prospective_evidence_runner.py",
    "regression/test_p203_source_provenance.py",
    "regression/test_p203_tx_contract_roll_audit.py",
    "regression/test_p203_v1r1_diagnostic_audit.py",
    "regression/test_p203_v2_historical_development.py",
    "regression/test_p204_score_bucket_performance.py",
    "regression/test_p205_regime_performance.py",
    "regression/test_p301_walk_forward_validation.py",
    "regression/test_p302_regime_conditioned_validation.py",
    "regression/test_p303_net_expectancy_validation.py",
    "regression/test_p304_model_drift_validation.py",
    "regression/test_q5_quant_math.js",
)
EXPECTED_OUT_OF_SCOPE = (
    "regression/test_p1_01_data_quality_remediation.py",
    "regression/test_p1_03_risk_classification.py",
    "regression/test_p1_04_no_trade_state.py",
    "regression/test_p1_04_no_trade_ui_gates.js",
    "regression/test_p2_artifact_hygiene.py",
    "regression/test_p2_backend_boundaries.py",
    "regression/test_p2_frontend_contract.js",
    "regression/test_p2_release_provenance.py",
    "regression/test_q5_decision_quality.py",
)
DIRECT_CI_TESTS = {
    "test_derivatives_platform.py",
    "regression/test_p0_quant_integrity.py",
    "regression/test_p1_options_execution.js",
    "regression/test_p1_options_liquidity.js",
    "regression/test_p1_point_in_time.js",
    "regression/test_options_strategy_analyzer.js",
}
CANDIDATE_PATTERN = re.compile(r"^test_(?:p0|p1|p2|p203|p204|p205|p30|q2|q3|q5)")


def _load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class P404QuantCiCoverageTests(unittest.TestCase):
    def test_contract_identity_is_frozen(self):
        contract_bytes = CONTRACT.read_bytes()
        self.assertEqual(hashlib.sha256(contract_bytes).hexdigest(), EXPECTED_CONTRACT_SHA256)
        self.assertIn(b"P4_04_QUANT_CI_ORPHAN_REGRESSION_V1", contract_bytes)

    def test_manifest_has_exact_deterministic_membership_and_classification(self):
        manifest = _load_manifest()
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["contractId"], "P4_04_QUANT_CI_ORPHAN_REGRESSION_V1")
        entries = manifest["tests"]
        paths = [entry["path"] for entry in entries]
        self.assertEqual(tuple(paths), EXPECTED_QUANT_TESTS)
        self.assertEqual(len(paths), len(set(paths)))
        for entry in entries:
            self.assertTrue((ROOT / entry["path"]).is_file(), entry["path"])
            self.assertIn(entry["classification"], {"CI_ENFORCED_DIRECT", "CI_ENFORCED_VIA_SUITE"})
            self.assertTrue(entry["domain"].strip())
            self.assertTrue(entry["ciPath"].strip())
            if entry["path"] in DIRECT_CI_TESTS:
                self.assertEqual(entry["classification"], "CI_ENFORCED_DIRECT")
                self.assertIn("p2-release-provenance.yml", entry["ciPath"])
            else:
                self.assertEqual(entry["classification"], "CI_ENFORCED_VIA_SUITE")
                self.assertIn("p1-quality-gate.yml", entry["ciPath"])

    def test_adjacent_candidate_tests_are_explicitly_excluded_with_reasons(self):
        manifest = _load_manifest()
        exclusions = manifest["outOfScopeCandidates"]
        paths = tuple(entry["path"] for entry in exclusions)
        self.assertEqual(paths, EXPECTED_OUT_OF_SCOPE)
        for entry in exclusions:
            self.assertTrue((ROOT / entry["path"]).is_file(), entry["path"])
            self.assertTrue(entry["reason"].strip(), entry["path"])

    def test_numbered_candidate_search_has_no_unclassified_regression(self):
        discovered = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "regression").glob("test_*.*")
            if path.suffix in {".py", ".js"} and CANDIDATE_PATTERN.match(path.name)
        }
        discovered.update({"regression/test_options_strategy_analyzer.js", "test_derivatives_platform.py"})
        manifest = _load_manifest()
        classified = {entry["path"] for entry in manifest["tests"]}
        excluded = {entry["path"] for entry in manifest["outOfScopeCandidates"]}
        self.assertFalse(classified & excluded)
        self.assertEqual(discovered, classified | excluded, sorted(discovered ^ (classified | excluded)))

    def test_inventory_lists_each_mandatory_and_excluded_candidate_once(self):
        document = INVENTORY.read_text(encoding="utf-8")
        manifest = _load_manifest()
        for entry in manifest["tests"]:
            row_marker = f"| `{entry['path']}` |"
            self.assertEqual(document.count(row_marker), 1, entry["path"])
        for entry in manifest["outOfScopeCandidates"]:
            row_marker = f"| `{entry['path']}` |"
            self.assertEqual(document.count(row_marker), 1, entry["path"])

    def test_runner_and_required_workflow_are_wired_without_failure_suppression(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        runner_source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("python -B regression/run_quant_regressions.py", workflow)
        self.assertIn("python -B -m unittest regression.test_p404_quant_ci_coverage", workflow)
        self.assertIn("MANIFEST = ROOT / \"regression\" / \"quant_regression_manifest.json\"", runner_source)
        self.assertNotRegex(workflow, r"(?im)^\s*continue-on-error:\s*true\s*$")
        self.assertNotRegex(workflow, r"\|\|\s*true")

    def test_q2_fixture_preserves_frozen_cost_and_timing_assertions(self):
        source = (ROOT / "regression" / "test_q2_backtest_methodology.js").read_text(encoding="utf-8")
        self.assertIn('assetClass: "TW_EQUITY"', source)
        self.assertIn('assert.strictEqual(model.signalTiming, "T close")', source)
        self.assertIn('assert.strictEqual(model.executionTiming, "T+1 open")', source)
        self.assertIn("model.costModel.roundTripPct > 0", source)

    def test_historical_replay_guard_uses_only_isolated_database_fixture(self):
        source = (ROOT / "regression" / "test_p203_historical_research_replay.py").read_text(encoding="utf-8")
        self.assertIn('TemporaryDirectory(prefix="p203-replay-db-isolation-")', source)
        self.assertIn('patch.object(replay, "ROOT", isolated_root)', source)
        self.assertNotIn('replay.ROOT / "data" / "p203-prospective-ledger.sqlite3"', source)

    def test_runner_propagates_controlled_child_failure(self):
        completed = subprocess.run(
            [sys.executable, "-B", str(RUNNER), "--verify-failure-propagation"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 23, completed.stdout + completed.stderr)
        self.assertIn("FAILURE_PROPAGATION_PROBE_NONZERO_PROPAGATED", completed.stdout)


if __name__ == "__main__":
    unittest.main()
