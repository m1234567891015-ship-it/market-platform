/* TD-02 Phase 3/4: deterministic full-site ESM bundle.
 *
 * The bundle keeps the existing source order in one module so the current
 * dependency graph remains executable while the transitional global bridge
 * exposes the locked 895 names for legacy consumers and rollback diagnostics.
 */
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { minify } = require("terser");

const ROOT = path.resolve(__dirname, "..");
const OUTPUT = path.join(ROOT, "market-pulse-esm.min.js");
const SOURCE_MAP = path.join(ROOT, "market-pulse-esm.min.js.map");
const VERSION = "td02-full-esm-20260901-1";
const LOCK = JSON.parse(fs.readFileSync(path.join(__dirname, "td18_minify_build.lock.json"), "utf8"));
const BASELINE = JSON.parse(fs.readFileSync(path.join(ROOT, "regression", "baseline", "frontend", "global_symbols.json"), "utf8"));

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function sourceInputs() {
  return LOCK.bundles
    .filter((bundle) => bundle.name !== "derivatives-status-addon")
    .flatMap((bundle) => bundle.inputs);
}

function readSources() {
  const files = {};
  for (const relative of sourceInputs()) {
    files[relative] = fs.readFileSync(path.join(ROOT, relative), "utf8");
  }
  files["derivatives-status-esm.js"] = fs.readFileSync(path.join(ROOT, "derivatives-status-esm.js"), "utf8");
  return files;
}

function bridgeSource() {
  const lines = [
    "/* TD-02 transitional global bridge: source owners remain module-local. */",
    "(() => {",
    "  const expose = (name, getter) => {",
    "    try { Object.defineProperty(globalThis, name, { configurable: true, enumerable: false, get: getter }); } catch {}",
    "  };",
  ];
  for (const name of BASELINE) {
    lines.push(`  expose(${JSON.stringify(name)}, () => ${name});`);
  }
  lines.push("})();");
  return lines.join("\n") + "\n";
}

async function main() {
  const files = readSources();
  files["__td02_esm_bridge__.js"] = bridgeSource();
  const result = await minify(files, {
    module: true,
    compress: LOCK.options.compress,
    mangle: false,
    format: LOCK.options.format,
    sourceMap: {
      filename: "market-pulse-esm.min.js",
      url: "market-pulse-esm.min.js.map?v=" + VERSION,
      includeSources: true,
    },
  });
  if (!result.code || !result.map) throw new Error("Terser returned incomplete ESM output");
  const output = Buffer.from(result.code + "\n", "utf8");
  const map = Buffer.from(result.map + "\n", "utf8");
  fs.writeFileSync(OUTPUT, output);
  fs.writeFileSync(SOURCE_MAP, map);
  const manifest = {
    schemaVersion: 1,
    batch: "TD02-FULL-ESM-PHASE-3-4",
    version: VERSION,
    mode: "module-with-transitional-895-symbol-bridge",
    sourceInputs: [...sourceInputs(), "derivatives-status-esm.js"],
    bridgeSymbols: BASELINE.length,
    output: { file: path.basename(OUTPUT), bytes: output.length, sha256: sha256(output) },
    sourceMap: { file: path.basename(SOURCE_MAP), bytes: map.length, sha256: sha256(map) },
    classicFallback: ["common-runtime.min.js", "route-bundle.min.js", "derivatives-status-addon.min.js"],
    productionAssetsModified: true,
    htmlModified: true,
    baselineModified: false,
  };
  fs.writeFileSync(path.join(ROOT, "docs", "TD02_FULL_ESM_build_manifest_2026-09-01.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");
  process.stdout.write(JSON.stringify(manifest, null, 2) + "\n");
}

main().catch((error) => {
  process.stderr.write("TD02_FULL_ESM_BUILD_FAIL: " + error.message + "\n");
  process.exitCode = 1;
});
