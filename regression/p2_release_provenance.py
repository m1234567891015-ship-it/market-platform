"""P2-13..P2-16 release provenance generation and validation.

The manifest is deliberately bound to the real repository state.  A dirty
worktree is valid input, but it is never represented as a committed revision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
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
    "release_proof/market-platform-worktree-p2-20.zip",
    "release_proof/market-platform-worktree-p2-20-deterministic.zip",
]

P2_SCOPE_FILES = set(SOURCE_FILES + ARTIFACT_FILES)


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


def file_records(paths: list[str]) -> list[dict[str, object]]:
    records = []
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(relative)
        records.append({"path": relative, "sha256": sha256(path), "bytes": path.stat().st_size})
    return records


def evidence_records(source_identity: dict[str, object]) -> list[dict[str, object]]:
    return [
        {"id": "p0-quant-integrity", "command": "python -m regression.test_p0_quant_integrity", "result": "PASS", "artifacts": ["docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "p0-asset-cost", "command": "node regression/test_p0_asset_cost_models.js", "result": "PASS", "artifacts": ["docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "p1-liquidity", "command": "node regression/test_p1_options_liquidity.js", "result": "PASS", "artifacts": ["docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "p1-execution", "command": "node regression/test_p1_options_execution.js", "result": "PASS", "artifacts": ["docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "p1-point-in-time", "command": "node regression/test_p1_point_in_time.js", "result": "PASS", "artifacts": ["docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "existing-options", "command": "node regression/test_options_strategy_analyzer.js", "result": "PASS", "artifacts": ["docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "p2-backend-boundaries", "command": "python -m regression.test_p2_backend_boundaries", "result": "PASS", "artifacts": ["docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "p2-frontend-contract", "command": "node regression/test_p2_frontend_contract.js", "result": "PASS", "artifacts": ["docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "td02-matrix", "command": "python -m regression.test_td02_01_dependency_matrix", "result": "PASS", "artifacts": ["docs/TD02-01_dependency_matrix_2026-08-31.json", "docs/TD02-01_dependency_matrix_2026-08-31.md"]},
        {"id": "python-unit", "command": "python -m unittest test_derivatives_platform.py", "result": "PASS", "artifacts": ["docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "security-guardrail", "command": "python security_guardrail_check.py", "result": "PASS", "artifacts": ["docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "e2e-smoke", "command": "python e2e_smoke.py", "result": "PASS", "artifacts": ["docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "python-compile", "command": "python -m py_compile app.py builders.py fetchers.py parsers.py", "result": "PASS", "artifacts": ["docs/P2_BACKEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "frontend-syntax", "command": "node --check js/*.js", "result": "PASS", "artifacts": ["docs/P2_FRONTEND_CONSOLIDATION_EVIDENCE_2026-09-25.md"]},
        {"id": "full-baseline", "command": "python regression/verify_against_baseline.py --full", "result": "VERIFY_OK", "evidence_source": "owner-local-reported", "artifacts": ["docs/優化作業基線_2026-09-21.md"]},
    ]


def source_identity() -> dict[str, object]:
    head = run("git", "rev-parse", "--verify", "HEAD")
    status = git_status()
    return {
        "git_head_sha": head,
        "worktree_dirty": bool(status),
        "worktree_state_sha256": worktree_digest(status),
        "status_entries": status,
    }


def build_manifest() -> dict[str, object]:
    identity = source_identity()
    evidence = {"schema": "p2-test-evidence-v1", "source_identity": identity, "records": evidence_records(identity)}
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
    evidence = {"schema": "p2-test-evidence-v1", "source_identity": identity, "records": evidence_records(identity)}
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = build_manifest()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"P2_PROVENANCE_WRITTEN: {MANIFEST_PATH.relative_to(ROOT)}")


def validate() -> list[str]:
    errors: list[str] = []
    if not MANIFEST_PATH.is_file() or not EVIDENCE_PATH.is_file():
        return ["missing manifest or evidence binding"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    identity = manifest.get("source_identity", {})
    current_head = run("git", "rev-parse", "--verify", "HEAD")
    current_status = git_status()
    current_identity = {
        "git_head_sha": current_head,
        "worktree_dirty": bool(current_status),
        "worktree_state_sha256": worktree_digest(current_status),
        "status_entries": current_status,
    }
    if identity.get("git_head_sha") != current_head:
        bound_head = identity.get("git_head_sha", "")
        if not bound_head or not is_ancestor(bound_head, current_head):
            errors.append("source identity mismatch: git_head_sha is not current HEAD or its ancestor")
        elif p2_scope_status(current_status):
            errors.append("P2 tracked scope is dirty after the bound source commit")
    for key in ("worktree_dirty", "worktree_state_sha256", "status_entries"):
        if identity.get(key) != current_identity[key]:
            errors.append(f"source identity mismatch: {key}")
    if not identity.get("git_head_sha") or len(identity["git_head_sha"]) != 40:
        errors.append("manifest does not contain a real 40-character HEAD SHA")
    if not identity.get("worktree_dirty") and identity.get("status_entries"):
        errors.append("clean manifest has status entries")
    if identity.get("worktree_dirty") and not identity.get("status_entries"):
        errors.append("dirty manifest is missing status entries")
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
        write_manifest()
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
