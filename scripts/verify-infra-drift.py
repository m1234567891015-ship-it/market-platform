#!/usr/bin/env python3
"""Verify the adjudicated R3 infrastructure contract from local observations.

The observation JSON is data only.  This tool reads local repository files and the
materialized observation; it never contacts or mutates a remote service.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
EXIT_OK = 0
EXIT_UNVERIFIED = 2
EXIT_REMEDIATION = 3
EXIT_INVALID = 4

EXPECTED_BUILD_COMMAND = "pip install -r requirements.txt"
EXPECTED_START_COMMAND = (
    "gunicorn --workers 1 --threads 4 --timeout 180 "
    "--bind 0.0.0.0:$PORT app:app"
)
EXPECTED_HEALTH_PATH = "/api/health"
EXPECTED_PLAN = "free"
EXPECTED_AUTODEPLOY = False
EXPECTED_CLOUDFLARE_NAME = "market-pulse-hybrid-local"


class InvalidInput(ValueError):
    """The observation or a required local contract file is unreadable."""


def _scalar(value: str) -> Any:
    value = value.strip()
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InvalidInput(f"cannot read {path}: {exc}") from exc


def parse_render_contract(path: Path) -> dict[str, Any]:
    """Parse only the fixed service fields used by this verifier."""
    text = _read_text(path)
    fields: dict[str, Any] = {}
    for key in (
        "buildCommand",
        "startCommand",
        "healthCheckPath",
        "plan",
        "autoDeploy",
    ):
        match = re.search(rf"(?m)^\s{{4}}{key}:\s*(.*?)\s*$", text)
        if match:
            fields[key] = _scalar(match.group(1))
    missing = [
        key for key in ("buildCommand", "startCommand", "healthCheckPath", "plan", "autoDeploy")
        if key not in fields
    ]
    if missing:
        raise InvalidInput(f"render.yaml missing required fields: {', '.join(missing)}")
    if not isinstance(fields["autoDeploy"], bool):
        raise InvalidInput("render.yaml autoDeploy must be boolean")
    return fields


def parse_procfile(path: Path) -> str:
    text = _read_text(path)
    for line in text.splitlines():
        if line.startswith("web:"):
            command = line[len("web:"):].strip()
            if command:
                return command
    raise InvalidInput("Procfile does not contain a web command")


def parse_cloudflare_config(path: Path) -> dict[str, Any]:
    text = _read_text(path)
    name_match = re.search(r'(?m)^\s*"name"\s*:\s*"([^"]+)"', text)
    workers_match = re.search(r'(?m)^\s*"workers_dev"\s*:\s*(true|false)\s*,?\s*$', text)
    if not name_match or not workers_match:
        raise InvalidInput("cloudflare/wrangler.jsonc missing required fixed fields")
    return {
        "name": name_match.group(1),
        "workers_dev": workers_match.group(1) == "true",
    }


def load_observation(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise InvalidInput(f"malformed observation JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidInput("observation root must be an object")
    for section in ("github", "render"):
        if not isinstance(data.get(section), dict):
            raise InvalidInput(f"observation.{section} must be an object")
    cloudflare = data.get("cloudflare")
    if cloudflare is not None and not isinstance(cloudflare, dict):
        raise InvalidInput("observation.cloudflare must be an object or null")
    return data


def _check(
    check_id: str,
    component: str,
    expected: Any,
    actual: Any,
    *,
    reason: str,
    missing_unverified: bool = True,
    matches: bool | None = None,
) -> dict[str, Any]:
    if actual is None and missing_unverified:
        return {
            "id": check_id,
            "component": component,
            "expected": expected,
            "actual": None,
            "status": "UNVERIFIED",
            "classification": "UNVERIFIED",
            "reason": f"{reason}; actual observation is missing and verification is unavailable",
        }
    if matches is None:
        matches = actual == expected
    if matches:
        return {
            "id": check_id,
            "component": component,
            "expected": expected,
            "actual": actual,
            "status": "MATCH",
            "classification": "NO_ACTION_REQUIRED",
            "reason": f"{reason}; expected and actual match",
        }
    return {
        "id": check_id,
        "component": component,
        "expected": expected,
        "actual": actual,
        "status": "DRIFT",
        "classification": "REMEDIATION_REQUIRED",
        "reason": f"{reason}; expected and actual differ",
    }


def _value(section: dict[str, Any], key: str) -> Any:
    return section.get(key)


def _documentation_evidence(documentation: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return an auditable D08 expectation and the evidence found in the document."""
    expected = {
        "cache_path": "/tmp/market-pulse-cache.json",
        "db_path": "/tmp/derivatives-platform.sqlite3",
        "storage": "EPHEMERAL",
        "migration_owner": "R4 Data Durability",
    }
    normalized = documentation.lower()
    actual = {
        "cache_path_documented": expected["cache_path"].lower() in normalized,
        "db_path_documented": expected["db_path"].lower() in normalized,
        "ephemeral_documented": "ephemeral" in normalized,
        "r4_deferred": expected["migration_owner"].lower() in normalized,
        "stale_current_var_data_claim": "/var/data" in normalized,
    }
    return expected, actual


def _local_cloudflare_evidence(
    wrangler_path: Path, cloudflare_contract: dict[str, Any], readme_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the D10 local-only contract and the locally observed evidence."""
    expected = {
        "wrangler_file_exists": True,
        "readme_exists": True,
        "name": EXPECTED_CLOUDFLARE_NAME,
        "workers_dev": False,
    }
    actual = {
        "wrangler_file_exists": wrangler_path.is_file(),
        "readme_exists": readme_path.is_file(),
        "name": cloudflare_contract["name"],
        "workers_dev": cloudflare_contract["workers_dev"],
    }
    return expected, actual


def verify(root: Path, observation: dict[str, Any]) -> tuple[dict[str, Any], int]:
    render_contract = parse_render_contract(root / "render.yaml")
    procfile_command = parse_procfile(root / "Procfile")
    cloudflare_contract = parse_cloudflare_config(root / "cloudflare" / "wrangler.jsonc")
    cloudflare_readme = root / "cloudflare" / "README.md"
    if not cloudflare_readme.is_file():
        raise InvalidInput(f"required local file is missing: {cloudflare_readme}")
    documentation = _read_text(root / "CLOUD_DEPLOYMENT.md")

    github = observation["github"]
    render = observation["render"]
    cloudflare = observation.get("cloudflare")
    if "auto_deploy" in render and not isinstance(render["auto_deploy"], bool):
        raise InvalidInput("observation.render.auto_deploy must be boolean")
    checks: list[dict[str, Any]] = []

    main_commit = _value(github, "main_commit")
    live_commit = _value(render, "live_commit")
    if main_commit is None or live_commit is None:
        checks.append(_check(
            "D01", "github.main_commit_vs_render.live_commit", main_commit,
            None, reason="GitHub main commit and Render live commit cannot be compared because an observation is missing",
        ))
    else:
        checks.append(_check(
            "D01", "github.main_commit_vs_render.live_commit", main_commit,
            live_commit, reason="GitHub main commit is compared with the observed Render live commit",
        ))

    pages_commit = _value(github, "cloudflare_pages_local_commit")
    checks.append(_check(
        "D02", "github.main_vs_cloudflare_pages_local", main_commit,
        pages_commit, reason="GitHub main commit is compared with the local Cloudflare Pages commit",
    ))
    if checks[-1]["status"] == "DRIFT":
        checks[-1]["classification"] = "DEFER_R8"
        checks[-1]["reason"] = "Cloudflare Pages local SHA differs from GitHub main; branch drift is deferred to R8"

    checks.append(_check(
        "D03", "render.autoDeploy", render_contract["autoDeploy"],
        _value(render, "auto_deploy"), reason="Repository render.yaml autoDeploy is compared with observed Render auto_deploy",
    ))
    checks.append(_check(
        "D04", "render.buildCommand", render_contract["buildCommand"],
        _value(render, "build_command"), reason="Repository render.yaml buildCommand is compared with observed Render build_command",
    ))
    checks.append(_check(
        "D05", "render.startCommand", render_contract["startCommand"],
        _value(render, "start_command"), reason="Repository render.yaml startCommand is compared with observed Render start_command",
    ))
    checks.append(_check(
        "D06", "render.healthCheckPath", render_contract["healthCheckPath"],
        _value(render, "health_check_path"), reason="Repository render.yaml healthCheckPath is compared with observed Render health_check_path",
    ))
    checks.append(_check(
        "D07", "render.plan", render_contract["plan"],
        _value(render, "plan"), reason="Repository render.yaml plan is compared with observed Render plan",
    ))

    d08_expected, d08_actual = _documentation_evidence(documentation)
    checks.append(_check(
        "D08", "deployment.persistence_documentation", d08_expected,
        d08_actual, matches=(
            d08_actual["cache_path_documented"]
            and d08_actual["db_path_documented"]
            and d08_actual["ephemeral_documented"]
            and d08_actual["r4_deferred"]
            and not d08_actual["stale_current_var_data_claim"]
        ), reason="Deployment documentation is checked for the current ephemeral paths and R4 ownership",
    ))
    checks.append(_check(
        "D09", "procfile.startCommand_vs_render.startCommand", procfile_command,
        _value(render, "start_command"), reason="Procfile web command is compared with observed Render start_command",
    ))

    d10_expected, d10_actual = _local_cloudflare_evidence(
        root / "cloudflare" / "wrangler.jsonc", cloudflare_contract, cloudflare_readme
    )
    checks.append(_check(
        "D10", "cloudflare.repo_local_only_contract", d10_expected,
        d10_actual, reason="Local Cloudflare files and settings are checked without asserting production account access",
    ))

    production_verified = bool(
        isinstance(cloudflare, dict)
        and (
            cloudflare.get("production_account_verified") is True
            or isinstance(cloudflare.get("production_account"), dict)
            and cloudflare["production_account"].get("verified") is True
        )
    )
    d11_actual = cloudflare if production_verified else None
    checks.append({
        "id": "D11",
        "component": "cloudflare.production_account",
        "expected": "VERIFIED_ACCOUNT_EVIDENCE",
        "actual": d11_actual,
        "status": "MATCH" if production_verified else "UNVERIFIED",
        "classification": "NO_ACTION_REQUIRED" if production_verified else "UNVERIFIED",
        "reason": (
            "Observation explicitly supplies verified Cloudflare production account evidence"
            if production_verified
            else "No reliable Cloudflare production account evidence was supplied; production account observation is absent"
        ),
    })

    counts = {
        "match": sum(check["status"] == "MATCH" for check in checks),
        "drift": sum(check["status"] == "DRIFT" for check in checks),
        "unverified": sum(check["status"] == "UNVERIFIED" for check in checks),
        "remediation_required": sum(check["classification"] == "REMEDIATION_REQUIRED" for check in checks),
        "defer_r8": sum(check["classification"] == "DEFER_R8" for check in checks),
    }
    if counts["remediation_required"]:
        exit_code = EXIT_REMEDIATION
    elif counts["unverified"]:
        exit_code = EXIT_UNVERIFIED
    else:
        exit_code = EXIT_OK
    overall_status = "DRIFT" if counts["remediation_required"] else "UNVERIFIED" if counts["unverified"] else "MATCH"
    return {
        "schema_version": SCHEMA_VERSION,
        "overall_status": overall_status,
        "exit_code": exit_code,
        "checks": checks,
        "counts": counts,
    }, exit_code


def invalid_report(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "overall_status": "INVALID_INPUT",
        "exit_code": EXIT_INVALID,
        "checks": [{
            "id": "INPUT",
            "component": "observation/local_contract",
            "expected": "readable valid input",
            "actual": None,
            "status": "UNVERIFIED",
            "classification": "UNVERIFIED",
            "reason": reason,
        }],
        "counts": {
            "match": 0,
            "drift": 0,
            "unverified": 1,
            "remediation_required": 0,
            "defer_r8": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", required=True, type=Path)
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    args = parser.parse_args(argv)
    try:
        report, exit_code = verify(args.root.resolve(), load_observation(args.observation.resolve()))
    except (InvalidInput, OSError, KeyError, TypeError, ValueError) as exc:
        report = invalid_report(str(exc))
        exit_code = EXIT_INVALID
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
