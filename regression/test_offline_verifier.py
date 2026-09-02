"""Regression tests for the TD-19 offline verifier boundary."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REGRESSION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(REGRESSION_DIR))

import verify_against_baseline as verify  # noqa: E402


class OfflineVerifierTests(unittest.TestCase):
    def test_required_key_policy_covers_manifest(self):
        manifest_path = REGRESSION_DIR / "baseline" / "manifest.json"
        manifest = verify.json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(44, len(manifest["endpoints"]))
        self.assertEqual([], verify._validate_required_key_policy(manifest["endpoints"]))

    def test_quick_api_check_uses_replayable_baseline_fixture(self):
        report = verify.check_api_baseline()
        self.assertTrue(report.ok, report.details)

    def test_missing_required_key_is_reported_as_schema_failure(self):
        endpoint = {
            "name": "api__twse__search",
            "request_path": "/api/twse/search?q=2330",
            "rule": "/api/twse/search",
            "status_code": 200,
            "structure_only": True,
            "mask_paths": [],
            "baseline_file": "api/api__twse__search.json",
        }
        incomplete_body = {"query": "2330", "count": 0}
        with patch.object(verify, "fetch", return_value=(200, "application/json", incomplete_body)):
            failure = verify._check_one_endpoint("http://fixture.invalid", endpoint)
        self.assertIn("缺少必要欄位 results", failure or "")

    def test_missing_nested_required_key_is_reported(self):
        endpoint = {
            "name": "api__twse__search",
            "request_path": "/api/twse/search?q=2330",
            "rule": "/api/twse/search",
            "status_code": 200,
            "structure_only": True,
            "mask_paths": [],
            "baseline_file": "api/api__twse__search.json",
        }
        with patch.dict(verify.REQUIRED_KEY_PATHS, {"api__twse__search": ("payload.items",)}):
            with patch.object(verify, "fetch", return_value=(200, "application/json", {"payload": {}})):
                failure = verify._check_one_endpoint("http://fixture.invalid", endpoint)
        self.assertIn("payload.items", failure or "")

    def test_present_null_and_empty_required_values_are_allowed(self):
        endpoint = {
            "name": "api__twse__search",
            "request_path": "/api/twse/search?q=2330",
            "rule": "/api/twse/search",
            "status_code": 200,
            "structure_only": True,
            "mask_paths": [],
            "baseline_file": "api/api__twse__search.json",
        }
        for results in (None, []):
            body = {"query": "2330", "count": 0, "results": results}
            with patch.object(verify, "fetch", return_value=(200, "application/json", body)):
                self.assertIsNone(verify._check_one_endpoint("http://fixture.invalid", endpoint))

    def test_external_failure_is_classified_before_required_key_check(self):
        endpoint = {
            "name": "api__twse__search",
            "request_path": "/api/twse/search?q=2330",
            "rule": "/api/twse/search",
            "status_code": 200,
            "structure_only": True,
            "mask_paths": [],
            "baseline_file": "api/api__twse__search.json",
        }
        body = {"success": False, "error_code": "UPSTREAM_DOWN"}
        with patch.object(verify, "fetch", return_value=(502, "application/json", body)):
            failure = verify._check_one_endpoint("http://fixture.invalid", endpoint)
        self.assertIn("[外部問題,非程式碼]", failure or "")

    def test_success_response_must_be_an_object(self):
        endpoint = {
            "name": "api__twse__search",
            "request_path": "/api/twse/search?q=2330",
            "rule": "/api/twse/search",
            "status_code": 200,
            "structure_only": True,
            "mask_paths": [],
            "baseline_file": "api/api__twse__search.json",
        }
        with patch.object(verify, "fetch", return_value=(200, "application/json", [])):
            failure = verify._check_one_endpoint("http://fixture.invalid", endpoint)
        self.assertIn("成功回應不是 object", failure or "")

    def test_policy_with_unknown_endpoint_fails_coverage(self):
        manifest_path = REGRESSION_DIR / "baseline" / "manifest.json"
        manifest = verify.json.loads(manifest_path.read_text(encoding="utf-8"))
        with patch.dict(verify.REQUIRED_KEY_PATHS, {"api__unknown": ("data",)}):
            errors = verify._validate_required_key_policy(manifest["endpoints"])
        self.assertTrue(any("policy api__unknown 不存在於 manifest" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
