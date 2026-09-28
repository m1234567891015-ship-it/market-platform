"""P2-13..P2-16 release provenance generation and validation.

The manifest is deliberately bound to the real repository state.  A dirty
worktree is valid input, but it is never represented as a committed revision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import tempfile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROOF_DIR = ROOT / "release_proof"
MANIFEST_PATH = PROOF_DIR / "p2_release_manifest.json"
EVIDENCE_PATH = PROOF_DIR / "p2_test_evidence.json"
CI_PATH = ROOT / ".github" / "workflows" / "p2-release-provenance.yml"
PROVENANCE_OUTPUTS = {
    "release_proof/p2_release_manifest.json",
    "release_proof/p2_test_evidence.json",
    "release_proof/market-platform-worktree-p2-20.zip",
    "release_proof/market-platform-worktree-p2-20-deterministic.zip",
}

SOURCE_FILES = [
    "app.py", "builders.py", "fetchers.py", "parsers.py", "cache.py",
    "market_config.py", "derivatives_store.py", "routes_system.py",
    "routes_global_market.py", "routes_twse.py", "routes_derivatives.py",
    "js/core.js", "js/api.js", "js/shared-calc.js", "js/state.js",
    "js/render-shared.js", "js/page-global-market-assethub.js",
    "js/page-global-market-options.js", "js/page-global-market-futures.js",
    "js/page-tw.js", "js/page-us.js", "js/page-home.js", "js/stock-detail.js",
    "regression/verify_against_baseline.py",
    "regression/test_p2_backend_boundaries.py",
    "regression/test_p2_frontend_contract.js",
    "regression/test_p2_asset_cost_contract.js",
    "regression/test_td02_01_dependency_matrix.py",
    "regression/p2_release_provenance.py",
    "regression/test_p2_release_provenance.py",
    "regression/test_p2_artifact_hygiene.py",
    "release_proof/build_p2_worktree_package.py",
    "security_guardrail_check.py", "e2e_smoke.py",
]

ARTIFACT_FILES = [
    "regression/baseline/manifest.json",
    "regression/baseline/security_headers.json",
    "docs/TD02-01_dependency_matrix_2026-08-31.json",
    "docs/TD02-01_dependency_matrix_2026-08-31.md",
    "docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",
    "docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",
    "docs/優化作業基線_2026-09-21.md",
    ".github/workflows/p2-release-provenance.yml",
]

P2_SCOPE_FILES = set(SOURCE_FILES + ARTIFACT_FILES)
COMPATIBILITY_FILES = {
    "regression/p2_release_provenance.py",
    "regression/test_p2_release_provenance.py",
    ".github/workflows/p2-release-provenance.yml",
    "release_proof/p2_release_manifest.json",
    "release_proof/p2_test_evidence.json",
}
HEX_SHA = re.compile(r"^[0-9a-f]{40}$")


def run(*args: str) -> str:
    return subprocess.check_output(
        args, cwd=ROOT, text=True, encoding="utf-8", errors="replace", stderr=subprocess.STDOUT
    ).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_status() -> list[str]:
    output = run("git", "status", "--porcelain=v1", "--untracked-files=all")
    lines = output.splitlines() if output else []
    return [line for line in lines if line[3:].replace("\\", "/") not in PROVENANCE_OUTPUTS]


def worktree_digest(status: list[str]) -> str:
    diff = run("git", "diff", "--no-ext-diff", "--binary")
    payload = ("\n".join(status) + "\n---DIFF---\n" + diff).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def status_path(line: str) -> str:
    if len(line) < 4 or line.startswith("warning:"):
        return ""
    path = line[3:]
    if " -> " in path:
        path = path.rsplit(" -> ", 1)[-1]
    return path.strip().strip('"').replace("\\", "/")


def p2_scope_status(status: list[str]) -> list[str]:
    return [line for line in status if status_path(line) in P2_SCOPE_FILES]


def is_ancestor(ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ("git", "merge-base", "--is-ancestor", ancestor, descendant),
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def committed_source_sha(identity: dict[str, object]) -> str:
    return str(identity.get("committed_source_sha") or identity.get("git_head_sha") or "")


def bound_source_from_existing_manifest(current_head: str) -> str:
    if MANIFEST_PATH.is_file():
        try:
            existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            bound = committed_source_sha(existing.get("source_identity", {}))
            if HEX_SHA.fullmatch(bound) and (bound == current_head or is_ancestor(bound, current_head)):
                return bound
        except (OSError, ValueError, TypeError):
            pass
    return current_head


def source_scope_drift(bound_source: str, current_head: str) -> list[str]:
    if bound_source == current_head:
        return []
    drift: list[str] = []
    semantic_files = sorted(P2_SCOPE_FILES - COMPATIBILITY_FILES - PROVENANCE_OUTPUTS)
    for relative in semantic_files:
        path = ROOT / relative
        if not path.is_file():
            drift.append(relative)
            continue
        try:
            committed = subprocess.check_output(
                ("git", "show", f"{bound_source}:{relative}"),
                cwd=ROOT,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            drift.append(relative)
            continue
        if hashlib.sha256(committed).hexdigest() != sha256(path):
            drift.append(relative)
    return drift


def validate_committed_source_identity(
    identity: dict[str, object],
    current_head: str,
    current_status: list[str],
    *,
    ci_environment: bool,
    changed_paths: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    bound_source = committed_source_sha(identity)
    if not HEX_SHA.fullmatch(bound_source):
        errors.append("manifest does not contain a real 40-character committed source SHA")
        return errors
    if bound_source != current_head and not is_ancestor(bound_source, current_head):
        errors.append("committed source SHA is not current HEAD or its ancestor")
    paths = changed_paths if changed_paths is not None else p2_scope_status(current_status)
    semantic_changes = sorted({status_path(path) or path for path in paths} - COMPATIBILITY_FILES - PROVENANCE_OUTPUTS)
    if semantic_changes:
        errors.append("P2 source scope drift after bound commit: " + ", ".join(semantic_changes))
    if ci_environment and current_status:
        errors.append("CI checkout is not clean")
    return errors


def file_records(paths: list[str]) -> list[dict[str, object]]:
    records = []
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        records.append({"path": relative, "sha256": sha256(path), "bytes": path.stat().st_size})
    return records


EVIDENCE_COMMANDS: tuple[dict[str, object], ...] = (
    {"id": "p0-quant-integrity", "command": "python -m regression.test_p0_quant_integrity", "argv": ("-m", "regression.test_p0_quant_integrity"), "python": True, "artifacts": ("docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "p2-asset-cost-contract", "command": "node regression/test_p2_asset_cost_contract.js", "argv": ("node", "regression/test_p2_asset_cost_contract.js"), "artifacts": ("docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "p1-liquidity", "command": "node regression/test_p1_options_liquidity.js", "argv": ("node", "regression/test_p1_options_liquidity.js"), "artifacts": ("docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "p1-execution", "command": "node regression/test_p1_options_execution.js", "argv": ("node", "regression/test_p1_options_execution.js"), "artifacts": ("docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "p1-point-in-time", "command": "node regression/test_p1_point_in_time.js", "argv": ("node", "regression/test_p1_point_in_time.js"), "artifacts": ("docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "existing-options", "command": "node regression/test_options_strategy_analyzer.js", "argv": ("node", "regression/test_options_strategy_analyzer.js"), "artifacts": ("docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "p2-backend-boundaries", "command": "python -m regression.test_p2_backend_boundaries", "argv": ("-m", "regression.test_p2_backend_boundaries"), "python": True, "artifacts": ("docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "p2-frontend-contract", "command": "node regression/test_p2_frontend_contract.js", "argv": ("node", "regression/test_p2_frontend_contract.js"), "artifacts": ("docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "td02-matrix", "command": "python -m regression.test_td02_01_dependency_matrix", "argv": ("-m", "regression.test_td02_01_dependency_matrix"), "python": True, "artifacts": ("docs/TD02-01_dependency_matrix_2026-08-31.json", "docs/TD02-01_dependency_matrix_2026-08-31.md")},
    {"id": "python-unit", "command": "python -m unittest test_derivatives_platform.py", "argv": ("-m", "unittest", "test_derivatives_platform.py"), "python": True, "artifacts": ("docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "security-guardrail", "command": "python security_guardrail_check.py", "argv": ("security_guardrail_check.py",), "python": True, "artifacts": ("docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "e2e-smoke", "command": "python e2e_smoke.py", "argv": ("e2e_smoke.py",), "python": True, "artifacts": ("docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "python-compile", "command": "python -m py_compile app.py builders.py fetchers.py parsers.py", "argv": ("-m", "py_compile", "app.py", "builders.py", "fetchers.py", "parsers.py"), "python": True, "artifacts": ("docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "frontend-syntax", "command": "node --check js/*.js", "argv": ("node", "--check", "js/*.js"), "artifacts": ("docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md",)},
    {"id": "full-baseline", "command": "python regression/verify_against_baseline.py --full", "argv": ("regression/verify_against_baseline.py", "--full"), "python": True, "artifacts": ("docs/優化作業基線_2026-09-21.md",)},
)


def command_invocations(spec: dict[str, object]) -> list[tuple[str, ...]]:
    argv = tuple(spec["argv"])
    if spec.get("python"):
        argv = (sys.executable, *argv)
    if argv[-1:] == ("js/*.js",):
        paths = sorted((ROOT / "js").glob("*.js"))
        return [("node", "--check", path.relative_to(ROOT).as_posix()) for path in paths]
    return [argv]


def run_evidence_command(argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    environment = None
    if argv[-1:] == ("e2e_smoke.py",):
        with tempfile.TemporaryDirectory(prefix="market-platform-p2-e2e-") as directory:
            isolated_root = Path(directory).resolve()
            if isolated_root == ROOT or ROOT in isolated_root.parents:
                raise RuntimeError("E2E evidence paths must remain outside the repository")
            environment = os.environ.copy()
            environment["DERIVATIVES_DB_PATH"] = str(isolated_root / "derivatives.sqlite3")
            environment["MARKET_PULSE_CACHE_FILE"] = str(isolated_root / "twse-cache.json")
            return subprocess.run(
                argv,
                cwd=ROOT,
                env=environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=900,
                check=False,
            )
    return subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=900,
        check=False,
    )


def safe_diagnostic(value: object) -> str:
    """ASCII-escape captured output so Windows console encodings cannot hide evidence."""
    if isinstance(value, str):
        return value.encode("ascii", errors="backslashreplace").decode("ascii")
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _live_api_failures(output: str) -> tuple[list[str], list[str]]:
    allowed_codes = {"sectors": "LIVE_SECTORS_UNAVAILABLE", "overview": "LIVE_OVERVIEW_UNAVAILABLE", "stocks": "LIVE_STOCKS_UNAVAILABLE"}
    found: list[str] = []
    unknown: list[str] = []
    for line in output.splitlines():
        if "/api/twse/live-" not in line or "error_code=" not in line:
            continue
        match = re.search(r"/api/twse/live-(sectors|overview|stocks):[^\r\n]{0,180}?(?:status)?[^0-9]{0,40}=(\d{3}),error_code=([A-Z0-9_]+)", line)
        if not match:
            unknown.append(line.strip())
            continue
        endpoint, status, error_code = match.groups()
        if int(status) != 502 or error_code != allowed_codes[endpoint]:
            unknown.append(line.strip())
            continue
        found.append(f"/api/twse/live-{endpoint}:status={status},error_code={error_code}")
    return sorted(found), unknown


def _baseline_reference_command(root: Path) -> subprocess.CompletedProcess[str]:
    root = root.resolve()
    if root == ROOT or not root.is_dir():
        raise EvidenceExecutionFailure("full-baseline reference must be a separate existing worktree")
    current_tree = run("git", "rev-parse", "HEAD^{tree}")
    reference_tree = subprocess.run(
        ("git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), "rev-parse", "HEAD^{tree}"),
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    reference_status = subprocess.run(
        ("git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if reference_tree.returncode or reference_tree.stdout.strip() != current_tree:
        raise EvidenceExecutionFailure("full-baseline reference source tree does not match current HEAD")
    if reference_status.returncode or reference_status.stdout.strip():
        raise EvidenceExecutionFailure("full-baseline reference worktree is not clean")
    return subprocess.run(
        (sys.executable, "regression/verify_against_baseline.py", "--quick", "--api-live"),
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=900,
        check=False,
    )


def full_baseline_policy(
    result: subprocess.CompletedProcess[str],
    baseline_result: subprocess.CompletedProcess[str] | None = None,
) -> dict[str, object]:
    """Keep raw verifier status distinct from the P2 decision; fail closed on unknown output."""
    output = "\n".join((result.stdout or "", result.stderr or ""))
    raw_ok = re.search(r"(?m)^\s*VERIFY_OK\s*$", output) is not None
    raw_failed = re.search(r"(?m)^\s*VERIFY_FAILED\s*$", output) is not None
    raw_result = "VERIFY_OK" if raw_ok and not raw_failed else "VERIFY_FAILED" if raw_failed and not raw_ok else "UNCLASSIFIABLE"
    exceptions: list[str] = []
    reason = "raw verifier status and exit code are inconsistent or unclassifiable"
    lines = output.splitlines()
    recognized_external: list[str] = []
    unknown_external = False
    for line in lines:
        if "[EXTERNAL]" not in line:
            continue
        categories = re.search(r"\(([^)]*)\)", line)
        if not categories:
            # interaction_check.py emits this exact structured marker without category suffixes.
            recognized_external.append("external_resource")
            continue
        values = {item.strip() for item in categories.group(1).split(",") if item.strip()}
        if not values or not values <= {"external_font", "external_network", "external_resource"}:
            unknown_external = True
        else:
            recognized_external.extend(sorted(values))

    if raw_result == "VERIFY_OK" and result.returncode == 0:
        if recognized_external:
            exceptions.append("recognized external noise: " + ", ".join(sorted(set(recognized_external))))
        if unknown_external:
            exceptions.append("unclassified external-noise diagnostic; raw verifier still passed")
        return {
            "raw_result": raw_result,
            "evidence_decision": "PASS",
            "exceptions": exceptions,
            "new_deterministic_failures": [],
            "worsened_failures": [],
            "decision_reason": "raw verifier passed",
        }

    if raw_result != "VERIFY_FAILED" or result.returncode == 0:
        return {
            "raw_result": raw_result,
            "evidence_decision": "FAIL",
            "exceptions": [],
            "new_deterministic_failures": ["unclassifiable verifier status or exit-code mismatch"],
            "worsened_failures": [],
            "decision_reason": reason,
        }

    failure_markers = [line.strip() for line in lines if "[FAIL]" in line]
    e1_pattern = re.compile(
        r"derivatives-status\.html[^\r\n]{0,240}(?:13\.81%[^\r\n]{0,80}2(?:\.0+)?%|2(?:\.0+)?%[^\r\n]{0,80}13\.81%)"
        r"|(?:13\.81%[^\r\n]{0,240}|2(?:\.0+)?%[^\r\n]{0,240})derivatives-status\.html",
        re.IGNORECASE,
    )
    e1_lines = [line for line in lines if e1_pattern.search(line)]
    e1_failure_lines = [line.strip() for line in e1_lines if "[FAIL]" in line]
    baseline_failure_headers = [line for line in failure_markers if line == "[FAIL] frontend_check.py --compare"]
    unknown_failure_markers = [
        line for line in failure_markers
        if line != "[FAIL] frontend_check.py --compare" and line not in e1_failure_lines
    ]
    # The verifier's only adjudicated deterministic exception is one exact page/value pair.
    e1_candidate = (
        len(baseline_failure_headers) == 1
        and len(e1_lines) == 1
        and len(e1_failure_lines) == 1
        and not unknown_external
    )
    if e1_candidate:
        # Fail closed if the same failed report also contains another concrete gate failure.
        for line in lines:
            lowered = line.lower()
            if any(token in lowered for token in ("console error", "元素數量", "找不到基準", "missing baseline")):
                e1_candidate = False
                break
            if ("502" in lowered or "http error" in lowered or "status code" in lowered) and "[external]" not in lowered and "/api/twse/live-" not in lowered:
                e1_candidate = False
                break
    e1_is_exclusive = e1_candidate and not unknown_failure_markers

    # Current full output can contain environment-blocked live endpoints.  A 502
    # is recognized only when the clean, content-identical P0 reference reports
    # the same endpoint-specific failure fingerprint.
    current_api, current_api_unknown = _live_api_failures(output)
    baseline_exceptions: list[str] = []
    if baseline_result is not None:
        baseline_output = "\n".join((baseline_result.stdout or "", baseline_result.stderr or ""))
        baseline_ok = re.search(r"(?m)^\s*VERIFY_OK\s*$", baseline_output) is not None
        baseline_failed = re.search(r"(?m)^\s*VERIFY_FAILED\s*$", baseline_output) is not None
        baseline_api, baseline_api_unknown = _live_api_failures(baseline_output)
        baseline_api_markers = [line.strip() for line in baseline_output.splitlines() if "[FAIL]" in line]
        current_api_markers = [line for line in failure_markers if line.startswith("[FAIL] API ")]
        current_known_markers = [line for line in failure_markers if line in e1_failure_lines or line == "[FAIL] frontend_check.py --compare" or line.startswith("[FAIL] API ")]
        other_current_markers = [line for line in failure_markers if line not in current_known_markers]
        reference_valid = (
            (baseline_ok and baseline_result.returncode == 0 and not baseline_api and not baseline_api_markers)
            or (
                baseline_failed
                and baseline_result.returncode != 0
                and baseline_api
                and baseline_api_markers
                and all(line.startswith("[FAIL] API ") for line in baseline_api_markers)
            )
        )
        if (
            e1_candidate
            and not other_current_markers
            and not current_api_unknown
            and not baseline_api_unknown
            and reference_valid
            and current_api == baseline_api
            and len(current_api_markers) == (1 if current_api else 0)
        ):
            if current_api:
                baseline_exceptions.append("clean P0 comparison matched live-feed environment failures: " + "; ".join(current_api))
            e1_is_exclusive = True
        else:
            e1_is_exclusive = False
    elif current_api:
        e1_is_exclusive = False

    if e1_is_exclusive:
        exceptions.append("E1 OPEN/PRE-EXISTING: derivatives-status.html visual diff 13.81% > 2.00% (exact adjudicated fingerprint)")
        exceptions.extend(baseline_exceptions)
        if recognized_external:
            exceptions.append("recognized external visual noise: " + ", ".join(sorted(set(recognized_external))))
        decision = "PASS"
        new_failures: list[str] = []
        worsened: list[str] = []
        reason = "all reported failures match the exact unchanged E1 fingerprint; other verifier sections passed"
    else:
        decision = "FAIL"
        new_failures = unknown_failure_markers or current_api_unknown or ["failed verifier output contains no classifiable failure section"]
        worsened = ["E1 was absent, repeated, changed, or accompanied by another failure"]
        if unknown_external:
            new_failures.append("unrecognized external-noise category")
        reason = "new, worsened, or unclassifiable verifier failure"

    comparison = None
    if baseline_result is not None:
        baseline_output = "\n".join((baseline_result.stdout or "", baseline_result.stderr or ""))
        baseline_ok = re.search(r"(?m)^\s*VERIFY_OK\s*$", baseline_output) is not None
        baseline_api, _ = _live_api_failures(baseline_output)
        comparison = {
            "command": "python regression/verify_against_baseline.py --quick --api-live (clean content-identical P0 reference)",
            "raw_result": "VERIFY_OK" if baseline_ok else "VERIFY_FAILED",
            "matched_environmental_failures": baseline_api if baseline_api == current_api else [],
        }
    return {
        "raw_result": raw_result,
        "evidence_decision": decision,
        "exceptions": exceptions,
        "new_deterministic_failures": new_failures,
        "worsened_failures": worsened,
        "decision_reason": reason,
        "baseline_comparison": comparison,
    }


def evidence_record(
    spec: dict[str, object],
    *,
    runner=None,
) -> dict[str, object]:
    execute = runner or run_evidence_command
    results = [execute(argv) for argv in command_invocations(spec)]
    if spec["id"] == "full-baseline":
        reference_root = os.environ.get("P2_FULL_BASELINE_REFERENCE_ROOT")
        baseline_result = _baseline_reference_command(Path(reference_root)) if reference_root else None
        policy = full_baseline_policy(results[0], baseline_result=baseline_result)
        print(f"RAW FULL BASELINE: {policy['raw_result']}")
        for exception in policy["exceptions"]:
            print(f"PRE-EXISTING / ENVIRONMENT EXCEPTIONS: {exception}")
        print(f"NEW DETERMINISTIC FAILURES: {safe_diagnostic(policy['new_deterministic_failures'] or 'NONE')}")
        print(f"WORSENED FAILURES: {safe_diagnostic(policy['worsened_failures'] or 'NONE')}")
        if policy.get("baseline_comparison"):
            print(f"CLEAN REFERENCE COMPARISON: {safe_diagnostic(policy['baseline_comparison'])}")
        print(f"P2 EVIDENCE DECISION: {policy['evidence_decision']}")
        if policy["evidence_decision"] != "PASS":
            details = "\n".join(part for part in (results[0].stdout, results[0].stderr) if part)
            print(f"[EVIDENCE FAIL] {spec['command']}\n{safe_diagnostic(details)}", file=sys.stderr)
        return {
            "id": spec["id"],
            "command": spec["command"],
            "result": policy["evidence_decision"],
            "raw_result": policy["raw_result"],
            "evidence_decision": policy["evidence_decision"],
            "exceptions": policy["exceptions"],
            "new_deterministic_failures": policy["new_deterministic_failures"],
            "worsened_failures": policy["worsened_failures"],
            "baseline_comparison": policy.get("baseline_comparison"),
            "artifacts": list(spec["artifacts"]),
        }
    exit_codes = [int(result.returncode) for result in results]
    exit_code = next((code for code in exit_codes if code != 0), 0)
    if exit_code:
        details = "\n".join(
            part for result in results for part in (result.stdout, result.stderr) if part
        )
        print(f"[EVIDENCE FAIL] {spec['command']} exited {exit_code}\n{safe_diagnostic(details)}", file=sys.stderr)
    return {
        "id": spec["id"],
        "command": spec["command"],
        "result": "PASS" if exit_code == 0 else "FAIL",
        "artifacts": list(spec["artifacts"]),
    }


def evidence_records(source_identity: dict[str, object]) -> list[dict[str, object]]:
    del source_identity  # The evidence contract is tied to execution, not a reported status.
    return [evidence_record(spec) for spec in EVIDENCE_COMMANDS]


class EvidenceExecutionFailure(RuntimeError):
    pass


def source_identity() -> dict[str, object]:
    head = run("git", "rev-parse", "--verify", "HEAD")
    status = git_status()
    bound_source = bound_source_from_existing_manifest(head)
    generation_context = {
        "worktree_dirty": bool(status),
        "worktree_state_sha256": worktree_digest(status),
        "status_entries": status,
        "platform": platform.platform(),
    }
    return {
        "committed_source_sha": bound_source,
        "git_head_sha": bound_source,
        **generation_context,
        "generation_context": generation_context,
    }


def build_manifest(identity: dict[str, object], records: list[dict[str, object]] | None = None) -> dict[str, object]:
    evidence = {"schema": "p2-test-evidence-v1", "source_identity": identity, "records": records if records is not None else evidence_records(identity)}
    return {
        "schema": "p2-release-provenance-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_identity": identity,
        "runtime": {
            "python": sys.version,
            "python_implementation": platform.python_implementation(),
            "node": run("node", "--version"),
            "platform": platform.platform(),
        },
        "entrypoints": {
            "canonical_full_baseline": "python regression/verify_against_baseline.py --full",
            "p2_provenance_validation": "python regression/test_p2_release_provenance.py",
            "application": "app:app",
        },
        "baseline_identity": {
            "manifest": file_records(["regression/baseline/manifest.json"])[0],
            "security_headers": file_records(["regression/baseline/security_headers.json"])[0],
            "verifier": file_records(["regression/verify_against_baseline.py"])[0],
        },
        "required_source_files": file_records(SOURCE_FILES),
        "evidence_artifacts": file_records(ARTIFACT_FILES + ["release_proof/p2_test_evidence.json"]),
        "evidence_binding": "release_proof/p2_test_evidence.json",
        "ci_definition": ".github/workflows/p2-release-provenance.yml",
    }


def write_manifest() -> None:
    PROOF_DIR.mkdir(exist_ok=True)
    identity = source_identity()
    records = evidence_records(identity)
    failures = [record for record in records if record["result"] != "PASS"]
    if failures:
        summary = ", ".join(f"{record['id']}={record['result']}" for record in failures)
        raise EvidenceExecutionFailure(f"refusing to write release proof with failed evidence commands: {summary}")
    evidence = {"schema": "p2-test-evidence-v1", "source_identity": identity, "records": records}
    write_json(EVIDENCE_PATH, evidence)
    manifest = build_manifest(identity, records)
    write_json(MANIFEST_PATH, manifest)
    print(f"P2_PROVENANCE_WRITTEN: {MANIFEST_PATH.relative_to(ROOT)}")


def write_json(path: Path, payload: dict[str, object]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized)


def validate() -> list[str]:
    errors: list[str] = []
    if not MANIFEST_PATH.is_file() or not EVIDENCE_PATH.is_file():
        return ["missing manifest or evidence binding"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    identity = manifest.get("source_identity", {})
    current_head = run("git", "rev-parse", "--verify", "HEAD")
    current_status = git_status()
    errors.extend(validate_committed_source_identity(
        identity,
        current_head,
        current_status,
        ci_environment=os.environ.get("CI", "").lower() == "true",
    ))
    bound_source = committed_source_sha(identity)
    errors.extend(source_scope_drift(bound_source, current_head))
    if evidence.get("source_identity") != identity:
        errors.append("evidence binding source identity mismatch")
    for record in manifest.get("required_source_files", []) + manifest.get("evidence_artifacts", []):
        path = ROOT / record["path"]
        if not path.is_file():
            errors.append(f"missing bound file: {record['path']}")
        elif sha256(path) != record["sha256"]:
            errors.append(f"hash mismatch: {record['path']}")
    artifact_paths = {record["path"] for record in manifest.get("evidence_artifacts", [])}
    for record in evidence.get("records", []):
        if not record.get("command") or not record.get("result"):
            errors.append(f"incomplete evidence record: {record.get('id')}")
        for artifact in record.get("artifacts", []):
            if artifact not in artifact_paths:
                errors.append(f"unbound evidence artifact: {artifact}")
    if not CI_PATH.is_file():
        errors.append("missing CI definition")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        try:
            write_manifest()
        except EvidenceExecutionFailure as exc:
            print(f"[FAIL] {exc}")
            print("P2_PROVENANCE_FAIL")
            return 1
        return 0
    errors = validate()
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print("P2_PROVENANCE_FAIL")
        return 1
    print("P2_PROVENANCE_OK: manifest, evidence binding, source consistency, and CI definition")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
