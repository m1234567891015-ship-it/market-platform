"""TD-18: verify deterministic Terser artifacts without touching production wiring."""
from __future__ import annotations

import json
import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGRESSION = ROOT / "regression"
LOCKFILE = REGRESSION / "td18_minify_build.lock.json"
BUILDER = REGRESSION / "td18_minify_build.js"
BASELINE_SYMBOLS = REGRESSION / "baseline" / "frontend" / "global_symbols.json"
PACKAGE_JSON = ROOT / "package.json"
PACKAGE_LOCK = ROOT / "package-lock.json"
PRODUCTION_MANIFEST = ROOT / "td18-minify-bundle-manifest.json"


class VerificationFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def has_minifiable_code(relative: str) -> bool:
    source = (ROOT / relative).read_text(encoding="utf-8-sig")
    without_comments = re.sub(r"/\*[\s\S]*?\*/|^\s*//.*$", "", source, flags=re.MULTILINE)
    return bool(without_comments.strip())


def run_builder(output_dir: Path) -> dict:
    result = subprocess.run(
        ["node", str(BUILDER), "--out", str(output_dir)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    require(result.returncode == 0, "minify builder failed: " + result.stderr.strip())
    return json.loads(result.stdout)


def verify_package_lock() -> dict:
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
    require(package["devDependencies"]["terser"] == "5.51.2", "package.json Terser version drifted")
    terser = lock["packages"].get("node_modules/terser", {})
    require(terser.get("version") == "5.51.2", "package-lock Terser version drifted")
    return {"node": "24.18.0", "terser": terser["version"]}


def verify_artifacts(lock: dict, result: dict, output_dir: Path) -> dict:
    actual = {item["name"]: item for item in result["bundles"]}
    require(set(actual) == {item["name"] for item in lock["bundles"]}, "bundle set drifted")
    compression = {}
    for expected in lock["bundles"]:
        item = actual[expected["name"]]
        require(item["output"] == expected["output"], f"{expected['name']} output drifted")
        require(item["sourceMap"] == expected["sourceMap"], f"{expected['name']} source map drifted")
        require([source["path"] for source in item["inputs"]] == expected["inputs"], f"{expected['name']} input order drifted")
        output = output_dir / item["output"]
        source_map = output_dir / item["sourceMap"]
        require(output.is_file() and source_map.is_file(), f"missing artifact for {expected['name']}")
        parsed_map = json.loads(source_map.read_text(encoding="utf-8"))
        require(parsed_map.get("version") == 3, f"{expected['name']} source map is not v3")
        expected_sources = [relative for relative in expected["inputs"] if has_minifiable_code(relative)]
        require(parsed_map.get("sources") == expected_sources, f"{expected['name']} source map sources drifted")
        require(parsed_map.get("sourcesContent"), f"{expected['name']} source map lacks sourcesContent")
        syntax = subprocess.run(
            ["node", "--check", str(output)], cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8"
        )
        require(syntax.returncode == 0, f"{expected['name']} failed node --check: {syntax.stderr}")
        shadow_size = sum(source["bytes"] for source in item["inputs"])
        compression[expected["name"]] = {
            "sourceBytes": shadow_size,
            "minifiedBytes": output.stat().st_size,
            "reductionPct": round((1 - output.stat().st_size / shadow_size) * 100, 2),
        }
    return compression


def verify_global_tokens(lock: dict, output_dir: Path) -> dict:
    baseline = json.loads(BASELINE_SYMBOLS.read_text(encoding="utf-8"))
    source = "\n".join(
        (output_dir / item["output"]).read_text(encoding="utf-8")
        for item in lock["bundles"]
        if item["name"] in {"common-runtime", "route-bundle"}
    )
    missing = [
        symbol for symbol in baseline if not re.search(r"(?<![\w$])" + re.escape(symbol) + r"(?![\w$])", source)
    ]
    require(not missing, "minified output removed or renamed global tokens: " + ", ".join(missing[:10]))
    require(source.count("function escapeHtml(") == 1, "minified output must retain one escapeHtml definition")
    return {"baseline_symbols": len(baseline), "missing_global_tokens": len(missing), "escapeHtml_definitions": 1}


def verify_production_manifest() -> dict:
    manifest = json.loads(PRODUCTION_MANIFEST.read_text(encoding="utf-8"))
    require(manifest["policy"]["mode"] == "production-minified-rollout", "production minify manifest mode drifted")
    checked = []
    for bundle in manifest["bundles"]:
        for field in ("output", "sourceMap"):
            path = ROOT / bundle[field]
            require(path.is_file(), f"production artifact missing: {path.name}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            expected_digest = bundle["sha256"] if field == "output" else bundle["sourceMapSha256"]
            expected_bytes = bundle["bytes"] if field == "output" else bundle["sourceMapBytes"]
            require(path.stat().st_size == expected_bytes, f"production artifact bytes drifted: {path.name}")
            require(digest == expected_digest, f"production artifact hash drifted: {path.name}")
        checked.append(bundle["output"])
    return {"production_manifest": PRODUCTION_MANIFEST.name, "checked_artifacts": len(checked)}


def main() -> None:
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    package = verify_package_lock()
    with tempfile.TemporaryDirectory(prefix="td18-minify-verify-", dir=ROOT / ".tmp") as first, tempfile.TemporaryDirectory(
        prefix="td18-minify-verify-", dir=ROOT / ".tmp"
    ) as second:
        first_result = run_builder(Path(first))
        second_result = run_builder(Path(second))
        require(first_result["bundles"] == second_result["bundles"], "two minify builds are not deterministic")
        compression = verify_artifacts(lock, first_result, Path(first))
        globals_result = verify_global_tokens(lock, Path(first))
    production = verify_production_manifest()
    print(json.dumps({"status": "TD18_MINIFY_VERIFY_OK", "package": package, "compression": compression, **globals_result, **production}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, VerificationFailure, subprocess.SubprocessError, json.JSONDecodeError) as error:
        print(f"TD18_MINIFY_VERIFY_FAILED: {error}")
        raise SystemExit(1) from error
