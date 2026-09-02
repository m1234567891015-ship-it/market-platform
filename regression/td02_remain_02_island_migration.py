"""TD02-REMAIN-02 single-page ESM island migration verifier.

The derivatives status addon is the only production page-specific entry.  The
verifier checks its ESM wiring, explicit ``escapeHtml`` bridge, initialization
guard, and classic fallback loader in isolated Node harnesses.  It never
modifies baselines or starts an ESM entry for any other page.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "regression"
STATUS_PAGE = ROOT / "derivatives-status.html"
MODULE_PATH = ROOT / "derivatives-status-esm.js"
LOADER_PATH = ROOT / "derivatives-status-esm-loader.js"
FALLBACK_PATH = ROOT / "derivatives-status-addon.min.js"
MATRIX_PATH = ROOT / "docs" / "TD02-01_dependency_matrix_2026-08-31.json"
BASELINE_SYMBOLS_PATH = REGRESSION / "baseline" / "frontend" / "global_symbols.json"

sys.path.insert(0, str(REGRESSION))
sys.path.insert(0, str(ROOT))

from td02_remain_01_bridge_shadow import PageAssets, ShadowFailure, require, read_json, verify_symbol_inventory  # noqa: E402
from market_config import ROOT_STATIC_FILES  # noqa: E402


def verify_page_wiring() -> dict:
    pages = sorted(ROOT.glob("*.html"))
    require(len(pages) == 21, f"expected 21 HTML pages, found {len(pages)}")
    status_scripts: list[str] = []
    for page in pages:
        parser = PageAssets()
        parser.feed(page.read_text(encoding="utf-8-sig"))
        require(not parser.inline_script_data, f"{page.name} contains inline script data")
        scripts = [urlsplit(value).path.lstrip("/") for value in parser.scripts]
        expected = ["common-runtime.min.js", "route-bundle.min.js"]
        if page.name == STATUS_PAGE.name:
            expected.append("derivatives-status-esm-loader.js")
            status_scripts = parser.scripts
        require(scripts == expected, f"{page.name} script wiring drifted: {scripts}")
        for asset in scripts:
            require((ROOT / asset).is_file(), f"{page.name} references missing asset: {asset}")
    require(len(status_scripts) == 3, "derivatives-status page must have exactly three external scripts")
    require("v=td02-remain-02-20260901-1" in status_scripts[-1], "status ESM loader version is missing")
    require("derivatives-status-esm.js" in ROOT_STATIC_FILES, "ESM status module missing from root static whitelist")
    require("derivatives-status-esm-loader.js" in ROOT_STATIC_FILES, "ESM loader missing from root static whitelist")
    require(FALLBACK_PATH.is_file(), "classic status addon fallback is missing")
    return {"pages": len(pages), "status_wiring": status_scripts, "classic_fallback": FALLBACK_PATH.name}


def verify_source_contract() -> dict:
    module = MODULE_PATH.read_text(encoding="utf-8-sig")
    loader = LOADER_PATH.read_text(encoding="utf-8-sig")
    for label, source in (("ESM module", module), ("classic loader", loader)):
        require("eval(" not in source and "new Function" not in source, f"{label} contains dynamic code execution")
        require("unsafe-inline" not in source and "unsafe-eval" not in source, f"{label} contains unsafe CSP token")
    require("export async function startDerivativesStatus" in module, "status ESM entry export is missing")
    require(module.count("globalThis.escapeHtml") == 1, "status ESM must use one explicit escapeHtml bridge")
    require("function escapeHtml(" not in module, "status ESM duplicated the escapeHtml function body")
    require("let started = false" in module and "if (started) return" in module, "status ESM initialization guard is missing")
    require("moduleScript.type = \"module\"" in loader, "loader does not create a module script")
    require("moduleScript.onerror = loadClassicFallback" in loader, "loader does not define ESM load fallback")
    require("derivatives-status-addon.min.js" in loader, "loader fallback asset drifted")
    require("noModule" in loader, "loader lacks legacy-browser fallback detection")
    return {
        "module_export": "startDerivativesStatus",
        "escapeHtml_bridge": "globalThis.escapeHtml",
        "initialization": "DOMContentLoaded once + started guard",
        "fallback": "module load error or noModule -> derivatives-status-addon.min.js",
    }


MODULE_HARNESS = r'''
import { pathToFileURL } from "node:url";
const root = { innerHTML: "" };
let listener = null;
let listenerCount = 0;
let fetchCalls = 0;
globalThis.escapeHtml = (value) => String(value ?? "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#039;");
globalThis.document = {
  readyState: "loading",
  getElementById: (id) => id === "derivatives-status-root" ? root : null,
  addEventListener: (name, callback) => {
    if (name === "DOMContentLoaded") { listener = callback; listenerCount += 1; }
  },
};
globalThis.fetch = async () => {
  fetchCalls += 1;
  return {
    ok: true,
    status: 200,
    json: async () => ({ data: {
      coverage: { futures: { connected: 1, total: 1 }, options: { connected: 1, total: 1 } },
      institutionImport: { currentProductRows: 2 },
      basis: { formula: "future - spot" },
      futures: [{ symbol: "TX", name: "TX <safe>", group: "期貨", v1Status: "connected" }],
      options: [{ symbol: "TXO", name: "TXO", group: "選擇權", v1Status: "imported" }],
      aiScoreFormula: { marketScore: "m", riskScore: "r", confidenceScore: "c", sourcePendingPenalty: "p" },
    } }),
  };
};
const api = await import(pathToFileURL(process.argv[2]).href);
if (Object.keys(api).join(",") !== "startDerivativesStatus") throw new Error("unexpected ESM exports");
if (listenerCount !== 1 || !listener) throw new Error("DOMContentLoaded listener was not registered once");
listener();
await new Promise((resolve) => setTimeout(resolve, 0));
if (fetchCalls !== 1) throw new Error(`expected one initialization fetch, got ${fetchCalls}`);
if (!root.innerHTML.includes("TX &lt;safe&gt;") || !root.innerHTML.includes("V1 國內期權資料狀態")) {
  throw new Error("status ESM did not render escaped API data");
}
listener();
await new Promise((resolve) => setTimeout(resolve, 0));
if (fetchCalls !== 1) throw new Error("duplicate DOMContentLoaded invocation was not guarded");
globalThis.fetch = async () => { throw new Error("<injected status failure>"); };
await api.startDerivativesStatus();
if (!root.innerHTML.includes("&lt;injected status failure&gt;")) throw new Error("status error was not escaped");
console.log(JSON.stringify({ exports: Object.keys(api), listenerCount, fetchCalls, escapedData: true, escapedError: true }));
'''


LOADER_HARNESS = r'''
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
const source = readFileSync(process.argv[2], "utf8");
function run(hasNoModule) {
  const appended = [];
  const document = {
    createElement: () => hasNoModule ? { noModule: false } : {},
    head: { appendChild: (node) => appended.push(node) },
  };
  runInNewContext(source, { document }, { filename: "derivatives-status-esm-loader.js" });
  return appended;
}
const legacy = run(false);
if (legacy.length !== 1 || !legacy[0].src.includes("derivatives-status-addon.min.js")) throw new Error("legacy fallback failed");
const modern = run(true);
if (modern.length !== 1 || modern[0].type !== "module") throw new Error("modern module entry failed");
modern[0].onerror();
if (modern.length !== 2 || !modern[1].src.includes("derivatives-status-addon.min.js")) throw new Error("module error fallback failed");
modern[0].onerror();
if (modern.length !== 2) throw new Error("fallback was loaded more than once");
console.log(JSON.stringify({ legacyFallback: true, moduleEntry: true, moduleErrorFallback: true, fallbackLoads: 1 }));
'''


def run_node_harness(source: str, filename: str, harness: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="td02-remain-02-") as temp_dir:
        temp = Path(temp_dir)
        source_path = temp / filename
        harness_path = temp / "harness.mjs"
        source_path.write_text(source, encoding="utf-8", newline="")
        harness_path.write_text(harness, encoding="utf-8", newline="")
        result = subprocess.run(
            ["node", str(harness_path), str(source_path)],
            cwd=temp,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
        require(result.returncode == 0, "Node island harness failed:\n" + (result.stdout + result.stderr).strip())
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        require(lines, "Node island harness produced no result")
        return json.loads(lines[-1])


def run() -> dict:
    matrix = read_json(MATRIX_PATH)
    baseline = read_json(BASELINE_SYMBOLS_PATH)
    require(isinstance(matrix, dict) and isinstance(baseline, list), "invalid TD02 inventory inputs")
    inventory = verify_symbol_inventory(matrix, baseline)
    wiring = verify_page_wiring()
    source_contract = verify_source_contract()
    module = MODULE_PATH.read_text(encoding="utf-8-sig")
    loader = LOADER_PATH.read_text(encoding="utf-8-sig")
    esm_runtime = run_node_harness(module, "status-esm.mjs", MODULE_HARNESS)
    loader_runtime = run_node_harness(loader, "status-loader.cjs", LOADER_HARNESS)
    for path in (MODULE_PATH, LOADER_PATH, FALLBACK_PATH):
        result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True, check=False)
        require(result.returncode == 0, f"node --check failed for {path.name}: {result.stderr}")
    return {
        "status": "pass",
        "batch": "TD02-REMAIN-02",
        "inventory": inventory,
        "wiring": wiring,
        "source_contract": source_contract,
        "esm_runtime": esm_runtime,
        "loader_runtime": loader_runtime,
        "production_pages_changed": ["derivatives-status.html"],
        "classic_fallback_preserved": True,
        "rollback": "restore derivatives-status.html and remove the two ESM assets/whitelist entries; retain classic addon",
    }


def main() -> int:
    try:
        print("TD02_REMAIN_02_ISLAND_OK: " + json.dumps(run(), ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ShadowFailure, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"TD02_REMAIN_02_ISLAND_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
