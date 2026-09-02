"""TD02-03 shadow-only proof for the isolated runtime/api candidate.

The proof never writes production assets.  It materializes an ESM wrapper and
Node harness in a system temporary directory, imports the current classic
slice there, and exercises the wrapper with deterministic fetch doubles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT / "js" / "api.js"
LOCK_PATH = ROOT / "regression" / "td18_shadow_build.lock.json"
MATRIX_PATH = ROOT / "docs" / "TD02-01_dependency_matrix_2026-08-31.json"
BASELINE_SYMBOLS_PATH = ROOT / "regression" / "baseline" / "frontend" / "global_symbols.json"

sys.path.insert(0, str(ROOT))
from security_guardrail_check import (  # noqa: E402
    js_top_level_declared_names,
    js_top_level_immediate_statement_identifiers,
)


class ShadowFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ShadowFailure(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def static_gate(source: str) -> dict:
    declared = sorted(js_top_level_declared_names(source))
    require(declared == ["fetchWithTimeout"], f"unexpected api.js top-level symbols: {declared}")

    immediate = js_top_level_immediate_statement_identifiers(source)
    require(not immediate, f"api.js has top-level immediate references: {immediate}")

    forbidden_runtime_refs = [
        token
        for token in ("document", "window", "localStorage", "location", "innerHTML")
        if token in source
    ]
    require(
        not forbidden_runtime_refs,
        f"runtime/api shadow candidate must not require DOM/window state: {forbidden_runtime_refs}",
    )

    matrix = read_json(MATRIX_PATH)
    symbol_rows = [row for row in matrix["symbols"] if row.get("symbol") == "fetchWithTimeout"]
    require(len(symbol_rows) == 1, "matrix must contain exactly one fetchWithTimeout owner")
    symbol_row = symbol_rows[0]
    require(symbol_row["source"] == "js/api.js", "matrix owner for fetchWithTimeout changed")
    require(symbol_row["candidate_module"] == "runtime/api", "candidate module must remain runtime/api")
    dependency_edges = [
        edge
        for edge in matrix["dependency_edges"]
        if edge.get("from") == "js/api.js" or edge.get("to") == "js/api.js"
    ]
    require(not dependency_edges, f"runtime/api must remain cycle-free in the matrix: {dependency_edges}")

    api_init = [
        row for row in matrix["top_level_initialization_gate"] if row["source"] == "js/api.js"
    ]
    require(len(api_init) == 1, "matrix must contain one api.js initialization row")
    require(not api_init[0]["references"], "matrix reports api.js top-level references")

    lock = read_json(LOCK_PATH)
    common_inputs = next(bundle["inputs"] for bundle in lock["bundles"] if bundle["name"] == "common-runtime")
    require(common_inputs.index("js/core.js") < common_inputs.index("js/api.js"), "api.js must load after core.js")
    require(common_inputs.index("js/api.js") < common_inputs.index("js/shared-calc.js"), "api.js must load before shared-calc.js")

    baseline_symbols = set(read_json(BASELINE_SYMBOLS_PATH))
    immediate_names = {name for _, names in immediate for name in names}
    require(
        not immediate_names.intersection(baseline_symbols),
        "api.js top-level code references a baseline global",
    )

    return {
        "declared_symbols": declared,
        "top_level_immediate_references": [],
        "dom_window_references": [],
        "candidate_module": symbol_row["candidate_module"],
        "owner": symbol_row["source"],
        "dependency_edges": [],
        "classic_order": common_inputs,
        "escapeHtml_check": "delegated to repository-wide source scan in shadow proof",
    }


HARNESS = r'''
const importCalls = [];
const nativeFetch = globalThis.fetch;
globalThis.fetch = async (...args) => {
  importCalls.push(args);
  return { status: 599 };
};

const api = await import("./api-shadow.mjs");
if (Object.keys(api).join(",") !== "fetchWithTimeout") {
  throw new Error(`unexpected ESM exports: ${Object.keys(api).join(",")}`);
}
if (importCalls.length !== 0) {
  throw new Error(`module import performed ${importCalls.length} fetch calls`);
}

const calls = [];
globalThis.fetch = async (url, options) => {
  calls.push({ url, method: options.method, hasSignal: Boolean(options.signal) });
  return { status: 200, ok: true };
};
const success = await api.fetchWithTimeout("/td02-03-ok", { method: "GET" }, 50);
if (success.status !== 200 || calls.length !== 1 || !calls[0].hasSignal || calls[0].method !== "GET") {
  throw new Error("success path did not preserve response, options, and abort signal");
}

globalThis.fetch = async () => {
  throw new Error("injected upstream failure");
};
let upstreamError = "";
try {
  await api.fetchWithTimeout("/td02-03-error", {}, 50);
} catch (error) {
  upstreamError = error.message;
}
if (upstreamError !== "injected upstream failure") {
  throw new Error(`upstream error behavior changed: ${upstreamError}`);
}

globalThis.fetch = (_url, options) => new Promise((_, reject) => {
  options.signal.addEventListener("abort", () => {
    const error = new Error("injected timeout abort");
    error.name = "AbortError";
    reject(error);
  }, { once: true });
});
let timeoutError = { name: "", message: "" };
try {
  await api.fetchWithTimeout("/td02-03-timeout", {}, 10);
} catch (error) {
  timeoutError = { name: error.name, message: error.message };
}
if (timeoutError.name !== "AbortError" || timeoutError.message !== "injected timeout abort") {
  throw new Error(`timeout error behavior changed: ${JSON.stringify(timeoutError)}`);
}

globalThis.fetch = nativeFetch;
console.log(JSON.stringify({
  exports: Object.keys(api),
  importFetchCalls: importCalls.length,
  successStatus: success.status,
  successCall: calls[0],
  upstreamError,
  timeoutError,
}));
'''


def runtime_gate(source: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="td02-03-api-shadow-") as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "api-shadow.mjs").write_text(
            source.rstrip() + "\n\nexport { fetchWithTimeout };\n",
            encoding="utf-8",
            newline="",
        )
        harness_path = temp_path / "harness.mjs"
        harness_path.write_text(HARNESS, encoding="utf-8", newline="")
        completed = subprocess.run(
            ["node", str(harness_path)],
            cwd=temp_path,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        require(
            completed.returncode == 0,
            "Node shadow harness failed:\n" + (completed.stdout + completed.stderr).strip(),
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        require(lines, "Node shadow harness produced no result")
        try:
            result = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            raise ShadowFailure(f"Node shadow harness output is not JSON: {lines[-1]}") from exc
        require(result["exports"] == ["fetchWithTimeout"], "ESM named export contract failed")
        require(result["importFetchCalls"] == 0, "ESM import has an unexpected fetch side effect")
        require(result["successStatus"] == 200, "success response contract failed")
        require(result["successCall"]["hasSignal"], "AbortController signal was not forwarded")
        require(result["successCall"]["method"] == "GET", "fetch options were not forwarded")
        require(result["upstreamError"] == "injected upstream failure", "upstream rejection was not preserved")
        require(result["timeoutError"]["name"] == "AbortError", "timeout did not abort the request")
        return result


def escapehtml_gate() -> dict:
    sources = [ROOT / "app.js", *sorted((ROOT / "js").glob("*.js"))]
    definitions = sum(
        path.read_text(encoding="utf-8-sig").count("function escapeHtml(") for path in sources
    )
    require(definitions == 1, f"escapeHtml definition count changed: {definitions}")
    owner = next(path.relative_to(ROOT).as_posix() for path in sources if "function escapeHtml(" in path.read_text(encoding="utf-8-sig"))
    return {"definitions": definitions, "owner": owner}


def run() -> dict:
    source = SOURCE_PATH.read_text(encoding="utf-8-sig")
    static = static_gate(source)
    escapehtml = escapehtml_gate()
    runtime = runtime_gate(source)
    return {
        "status": "pass",
        "candidate": "runtime/api",
        "source": SOURCE_PATH.relative_to(ROOT).as_posix(),
        "source_sha256": source_sha256(source),
        "static": static,
        "escapeHtml": escapehtml,
        "runtime": runtime,
        "production_wiring": "unchanged; no HTML or bundle modification",
        "rollback": "delete this verifier/report; classic source and lockfile remain authoritative",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="run the deterministic shadow proof")
    args = parser.parse_args()
    del args
    try:
        result = run()
    except (OSError, ShadowFailure, subprocess.SubprocessError) as exc:
        print(f"TD02_03_SHADOW_FAIL: {exc}", file=sys.stderr)
        return 1
    print("TD02_03_SHADOW_OK: " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
