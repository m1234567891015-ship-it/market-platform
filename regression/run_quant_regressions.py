"""Run the frozen mixed-language quantitative regression inventory."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "regression" / "quant_regression_manifest.json"
CONTRACT_ID = "P4_04_QUANT_CI_ORPHAN_REGRESSION_V1"
UNITTEST_COUNT = re.compile(r"\bRan\s+(\d+)\s+tests?\b")


class QuantGateError(RuntimeError):
    pass


def load_manifest() -> list[dict[str, Any]]:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuantGateError(f"cannot read Quant CI manifest: {exc}") from exc

    if manifest.get("contractId") != CONTRACT_ID:
        raise QuantGateError("Quant CI manifest contract identity mismatch")
    tests = manifest.get("tests")
    if not isinstance(tests, list) or not tests:
        raise QuantGateError("Quant CI manifest must contain a non-empty tests list")

    seen: set[str] = set()
    for entry in tests:
        if not isinstance(entry, dict):
            raise QuantGateError("Quant CI manifest entry must be an object")
        relative = entry.get("path")
        if not isinstance(relative, str) or relative in seen:
            raise QuantGateError(f"missing or duplicate test path: {relative!r}")
        seen.add(relative)
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise QuantGateError(f"test path is missing or outside the repository: {relative}")
        language = entry.get("language")
        if language == "python":
            if not isinstance(entry.get("module"), str):
                raise QuantGateError(f"Python test has no unittest module: {relative}")
        elif language == "node":
            if path.suffix != ".js":
                raise QuantGateError(f"Node regression is not a JavaScript file: {relative}")
        else:
            raise QuantGateError(f"unsupported test language {language!r}: {relative}")
        if entry.get("classification") not in {"CI_ENFORCED_DIRECT", "CI_ENFORCED_VIA_SUITE"}:
            raise QuantGateError(f"mandatory test is not CI-enforced: {relative}")
    return tests


def build_command(entry: dict[str, Any]) -> list[str]:
    if entry["language"] == "python":
        return [sys.executable, "-B", "-m", "unittest", entry["module"]]
    return ["node", entry["path"]]


def verify_failure_propagation() -> int:
    """Exercise the same child-process return-code path with a safe probe."""
    result = subprocess.run(
        [sys.executable, "-B", "-c", "import sys; sys.exit(23)"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"CONTROLLED_CHILD_RETURN_CODE={result.returncode}")
    if result.returncode == 0:
        print("FAILURE_PROPAGATION_PROBE_FAILED")
        return 1
    print("FAILURE_PROPAGATION_PROBE_NONZERO_PROPAGATED")
    return result.returncode if result.returncode > 0 else 1


def run_quant_gate() -> int:
    try:
        tests = load_manifest()
    except QuantGateError as exc:
        print(f"QUANT_GATE_CONFIGURATION_ERROR: {exc}", file=sys.stderr)
        return 2

    started = time.perf_counter()
    unittest_cases = 0
    python_suites = 0
    node_scripts = 0

    with tempfile.TemporaryDirectory(prefix="market-platform-quant-ci-") as temp_name:
        temp_root = Path(temp_name)
        environment = os.environ.copy()
        environment.update({
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUTF8": "1",
            "DERIVATIVES_DB_PATH": str(temp_root / "derivatives-regression.sqlite3"),
            "MARKET_PULSE_CACHE_FILE": str(temp_root / "market-pulse-cache.json"),
            "MARKET_PULSE_DISABLE_BACKGROUND": "1",
        })

        for index, entry in enumerate(tests, start=1):
            command = build_command(entry)
            entry_started = time.perf_counter()
            print(f"[{index}/{len(tests)}] RUN {entry['path']}", flush=True)
            try:
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
            except OSError as exc:
                print(f"[FAIL] {entry['path']}: unable to launch: {exc}", file=sys.stderr)
                return 2

            combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part)
            if combined_output:
                print(combined_output, end="" if combined_output.endswith("\n") else "\n", flush=True)

            duration = time.perf_counter() - entry_started
            if result.returncode:
                print(f"[FAIL] {entry['path']} exit={result.returncode} elapsed={duration:.2f}s", flush=True)
                return result.returncode if result.returncode > 0 else 1

            match = UNITTEST_COUNT.search(combined_output)
            if match:
                unittest_cases += int(match.group(1))
                python_suites += 1
            if entry["language"] == "node":
                node_scripts += 1
            test_count = f", unittest cases={match.group(1)}" if match else ""
            print(f"[PASS] {entry['path']} elapsed={duration:.2f}s{test_count}", flush=True)

    elapsed = time.perf_counter() - started
    print(
        "QUANT_GATE_PASS: "
        f"scripts={len(tests)} python_suites={python_suites} node_scripts={node_scripts} "
        f"unittest_cases={unittest_cases} elapsed={elapsed:.2f}s"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments == ["--verify-failure-propagation"]:
        return verify_failure_propagation()
    if arguments:
        print("usage: python -B regression/run_quant_regressions.py [--verify-failure-propagation]", file=sys.stderr)
        return 2
    return run_quant_gate()


if __name__ == "__main__":
    raise SystemExit(main())
