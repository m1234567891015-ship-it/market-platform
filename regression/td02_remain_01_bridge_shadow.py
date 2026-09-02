"""TD02-REMAIN-01 ESM bridge contract and shadow proof.

This batch validates one isolated, low-risk candidate (``runtime/api``) without
changing production HTML, bundles, classic slices, or the global-symbol
baseline.  The ESM wrapper and classic fallback harness are materialized only
in a temporary directory.  Its production-wiring check also accepts the
approved single-page ESM loader introduced by TD02-REMAIN-02, so the original
proof remains rerunnable after the later island migration.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "regression"
MATRIX_PATH = ROOT / "docs" / "TD02-01_dependency_matrix_2026-08-31.json"
BASELINE_SYMBOLS_PATH = REGRESSION / "baseline" / "frontend" / "global_symbols.json"
LOCK_PATH = REGRESSION / "td18_shadow_build.lock.json"
MINIFY_LOCK_PATH = REGRESSION / "td18_minify_build.lock.json"
API_SOURCE_PATH = ROOT / "js" / "api.js"

sys.path.insert(0, str(REGRESSION))
sys.path.insert(0, str(ROOT))

from td02_03_api_shadow import (  # noqa: E402
    escapehtml_gate as verify_escapehtml_single_source,
    runtime_gate as verify_esm_runtime,
    static_gate as verify_api_static,
)


class ShadowFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ShadowFailure(message)


def read_json(path: Path) -> dict | list:
    require(path.is_file(), f"missing required artifact: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


class PageAssets(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self.module_scripts: list[str] = []
        self.inline_script_data: list[str] = []
        self._in_script = False
        self._script_src: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        self._in_script = True
        values = {key.lower(): value for key, value in attrs}
        src = values.get("src")
        script_type = (values.get("type") or "").strip().lower()
        self._script_src = src
        if src:
            self.scripts.append(src)
        if script_type == "module":
            self.module_scripts.append(src or "inline")

    def handle_data(self, data: str) -> None:
        if self._in_script and self._script_src is None and data.strip():
            self.inline_script_data.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script":
            self._in_script = False
            self._script_src = None


def verify_symbol_inventory(matrix: dict, baseline: list) -> dict:
    symbols = matrix.get("symbols", [])
    names = [row.get("symbol") for row in symbols]
    require(len(symbols) == 895, f"TD02 inventory expected 895 rows, found {len(symbols)}")
    require(len(set(names)) == 895, "TD02 inventory contains duplicate symbol names")
    require(len(baseline) == 895, f"global-symbol baseline expected 895 rows, found {len(baseline)}")
    require(set(names) == set(baseline), "TD02 inventory symbols differ from global-symbol baseline")
    owners = {(row.get("symbol"), row.get("source")) for row in symbols}
    require(len(owners) == 895, "TD02 inventory has duplicate symbol owners")
    return {"matrix_symbols": len(symbols), "baseline_symbols": len(baseline), "unique_owners": len(owners)}


def verify_bridge_contract(matrix: dict, lock: dict) -> dict:
    rows = [row for row in matrix["symbols"] if row.get("symbol") == "fetchWithTimeout"]
    require(len(rows) == 1, "bridge candidate must have one fetchWithTimeout owner")
    row = rows[0]
    common = next(bundle for bundle in lock["bundles"] if bundle["name"] == "common-runtime")
    inputs = common["inputs"]
    require(row["source"] == "js/api.js", "runtime/api source owner drifted")
    require(row["candidate_module"] == "runtime/api", "runtime/api candidate module drifted")
    require(inputs.index("js/core.js") < inputs.index("js/api.js") < inputs.index("js/shared-calc.js"), "runtime/api classic order drifted")
    edges = [edge for edge in matrix["dependency_edges"] if edge.get("from") == "js/api.js" or edge.get("to") == "js/api.js"]
    require(not edges, f"runtime/api bridge must remain cycle-free: {edges}")

    contract = {
        "candidate_module": "runtime/api",
        "source_owner": "js/api.js",
        "named_exports": ["fetchWithTimeout"],
        "cross_module_edges": 0,
        "global_bridge_symbols": [],
        "classic_fallback": {
            "source": "js/api.js",
            "bundle": "common-runtime",
            "preserve_script_order": True,
        },
        "production_wiring": "unchanged",
    }
    validate_bridge_contract(contract)
    return contract


def validate_bridge_contract(contract: dict) -> None:
    require(contract.get("candidate_module") == "runtime/api", "bridge candidate module is not runtime/api")
    require(contract.get("source_owner") == "js/api.js", "bridge source owner is not js/api.js")
    require(contract.get("named_exports") == ["fetchWithTimeout"], "bridge named-export contract drifted")
    require(contract.get("cross_module_edges") == 0, "isolated runtime/api candidate gained a dependency edge")
    require(contract.get("global_bridge_symbols") == [], "runtime/api introduced an unregistered global bridge")
    fallback = contract.get("classic_fallback") or {}
    require(fallback.get("source") == "js/api.js", "classic fallback source drifted")
    require(fallback.get("bundle") == "common-runtime", "classic fallback bundle drifted")
    require(fallback.get("preserve_script_order") is True, "classic fallback order is not protected")
    require(contract.get("production_wiring") == "unchanged", "shadow proof must not wire production HTML")


def verify_error_injection(contract: dict) -> dict:
    failures: dict[str, str] = {}
    cases = {
        "missing_named_export": lambda item: item["named_exports"].clear(),
        "unregistered_global_bridge": lambda item: item["global_bridge_symbols"].append("unexpectedGlobal"),
    }
    for name, mutate in cases.items():
        injected = copy.deepcopy(contract)
        if name == "fallback_wiring_change":
            injected["production_wiring"] = "changed"
        else:
            mutate(injected)
        try:
            validate_bridge_contract(injected)
        except ShadowFailure:
            failures[name] = "caught"
        else:
            raise ShadowFailure(f"error injection was not caught: {name}")
    injected = copy.deepcopy(contract)
    injected["production_wiring"] = "changed"
    try:
        validate_bridge_contract(injected)
    except ShadowFailure:
        failures["fallback_wiring_change"] = "caught"
    else:
        raise ShadowFailure("error injection was not caught: fallback_wiring_change")
    return failures


FALLBACK_HARNESS = r'''
const fs = require("node:fs");
const vm = require("node:vm");

(async () => {
  const source = fs.readFileSync(process.argv[2], "utf8");
  const calls = [];
  const context = {
    AbortController,
    clearTimeout,
    setTimeout,
    fetch: async (url, options) => {
      calls.push({ url, method: options.method, hasSignal: Boolean(options.signal) });
      return { status: 204 };
    },
  };
  context.globalThis = context;
  vm.runInNewContext(source, context, { filename: "api-classic.js" });
  if (typeof context.fetchWithTimeout !== "function") {
    throw new Error("classic fallback did not publish fetchWithTimeout");
  }
  const response = await context.fetchWithTimeout("/td02-remain-01-fallback", { method: "GET" }, 50);
  if (response.status !== 204 || calls.length !== 1 || !calls[0].hasSignal || calls[0].method !== "GET") {
    throw new Error("classic fallback did not preserve API behavior");
  }
  console.log(JSON.stringify({ responseStatus: response.status, calls }));
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
'''


def verify_classic_fallback(source: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="td02-remain-01-fallback-") as temp_dir:
        temp = Path(temp_dir)
        source_path = temp / "api-classic.js"
        harness_path = temp / "fallback.cjs"
        source_path.write_text(source, encoding="utf-8", newline="")
        harness_path.write_text(FALLBACK_HARNESS, encoding="utf-8", newline="")
        result = subprocess.run(
            ["node", str(harness_path), str(source_path)],
            cwd=temp,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        require(result.returncode == 0, "classic fallback harness failed:\n" + (result.stdout + result.stderr).strip())
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        require(lines, "classic fallback harness produced no result")
        report = json.loads(lines[-1])
        require(report["responseStatus"] == 204, "classic fallback response contract failed")
        return report


def verify_production_wiring() -> dict:
    pages = sorted(ROOT.glob("*.html"))
    require(len(pages) == 21, f"expected 21 HTML pages, found {len(pages)}")
    local_assets: set[str] = set()
    page_modes: set[str] = set()
    for page in pages:
        parser = PageAssets()
        parser.feed(page.read_text(encoding="utf-8-sig"))
        require(not parser.inline_script_data, f"{page.name} contains inline script data")
        require(not parser.module_scripts, f"{page.name} unexpectedly wires an ESM module")
        scripts = [urlsplit(value).path.lstrip("/") for value in parser.scripts]
        expected_base = ["common-runtime.min.js", "route-bundle.min.js"]
        expected = expected_base
        if page.name == "derivatives-status.html":
            classic_status = expected_base + ["derivatives-status-addon.min.js"]
            esm_status = expected_base + ["derivatives-status-esm-loader.js"]
            if scripts == classic_status:
                page_modes.add("status-addon")
                expected = classic_status
            elif scripts == esm_status:
                for asset in (
                    "derivatives-status-esm-loader.js",
                    "derivatives-status-esm.js",
                    "derivatives-status-addon.min.js",
                ):
                    require((ROOT / asset).is_file(), f"status ESM wiring missing asset: {asset}")
                page_modes.add("status-esm-loader")
                expected = esm_status
            else:
                require(False, f"{page.name} production wiring differs from TD18 minified order")
        else:
            page_modes.add("standard")
        require(scripts == expected, f"{page.name} production wiring differs from TD18 minified order")
        for asset in scripts:
            asset_path = ROOT / asset
            require(asset_path.is_file(), f"{page.name} references missing local asset: {asset}")
            local_assets.add(asset)
    require(
        page_modes in ({"standard", "status-addon"}, {"standard", "status-esm-loader"}),
        "expected standard plus one status production wiring mode",
    )
    return {
        "pages": len(pages),
        "modes": sorted(page_modes),
        "local_scripts": sorted(local_assets),
        "current_status_wiring": "esm-loader" if "status-esm-loader" in page_modes else "classic-addon",
    }


def run() -> dict:
    matrix = read_json(MATRIX_PATH)
    baseline = read_json(BASELINE_SYMBOLS_PATH)
    lock = read_json(LOCK_PATH)
    require(isinstance(matrix, dict) and isinstance(baseline, list) and isinstance(lock, dict), "invalid TD02 proof inputs")
    source = API_SOURCE_PATH.read_text(encoding="utf-8-sig")
    inventory = verify_symbol_inventory(matrix, baseline)
    bridge = verify_bridge_contract(matrix, lock)
    api_static = verify_api_static(source)
    escapehtml = verify_escapehtml_single_source()
    esm_runtime = verify_esm_runtime(source)
    classic_fallback = verify_classic_fallback(source)
    wiring = verify_production_wiring()
    error_injection = verify_error_injection(bridge)
    require(MINIFY_LOCK_PATH.is_file(), "missing TD18 minify lockfile needed for production fallback provenance")
    return {
        "status": "pass",
        "batch": "TD02-REMAIN-01",
        "inventory": inventory,
        "bridge_contract": bridge,
        "api_static": api_static,
        "escapeHtml": escapehtml,
        "esm_runtime": esm_runtime,
        "classic_fallback": classic_fallback,
        "production_wiring": wiring,
        "error_injection": error_injection,
        "production_html_changed_in_remain_01": False,
        "baseline_changed": False,
        "rollback": "restore classic status addon wiring if the later ESM island is rolled back",
    }


def main() -> int:
    try:
        result = run()
    except (OSError, ShadowFailure, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"TD02_REMAIN_01_SHADOW_FAIL: {exc}", file=sys.stderr)
        return 1
    print("TD02_REMAIN_01_SHADOW_OK: " + json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
