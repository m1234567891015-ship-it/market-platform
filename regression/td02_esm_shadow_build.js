/* TD-02 full-site ESM preflight: combine the currently shipped bundles in an
 * isolated output so browser behavior can be tested before production wiring. */
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const ROOT = path.resolve(__dirname, "..");
const DEFAULT_OUTPUT = path.join(ROOT, ".tmp", "td02-esm-shadow", "market-pulse-esm.js");
const INPUTS = ["common-runtime.js", "route-bundle.js"];

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function outputPath() {
  const index = process.argv.indexOf("--out");
  return path.resolve(index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : DEFAULT_OUTPUT);
}

function assertIsolated(target) {
  if (!target.startsWith(path.join(ROOT, ".tmp") + path.sep)) {
    throw new Error("output must remain inside .tmp");
  }
}

function main() {
  const target = outputPath();
  assertIsolated(target);
  const parts = [];
  const inputs = [];
  for (const relative of INPUTS) {
    const sourcePath = path.join(ROOT, relative);
    const source = fs.readFileSync(sourcePath);
    inputs.push({ path: relative, bytes: source.length, sha256: sha256(source) });
    parts.push(Buffer.from(`/* esm-shadow-input:${relative} */\n`, "utf8"), source, Buffer.from("\n", "utf8"));
  }
  parts.push(Buffer.from(
    "/* explicit bridge: status ESM and future route modules consume this safety owner */\n" +
    "globalThis.escapeHtml = escapeHtml;\n",
    "utf8",
  ));
  const output = Buffer.concat(parts);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, output);
  fs.writeFileSync(
    path.join(path.dirname(target), "manifest.json"),
    JSON.stringify({
      schemaVersion: 1,
      mode: "td02-full-site-esm-shadow",
      productionWiringChanged: false,
      inputs,
      output: { path: path.relative(ROOT, target).replaceAll(path.sep, "/"), bytes: output.length, sha256: sha256(output) },
      bridge: { escapeHtmlOwner: "js/core.js", explicitGlobal: "globalThis.escapeHtml" },
    }, null, 2) + "\n",
    "utf8",
  );
  process.stdout.write(`TD02_ESM_SHADOW_OK: output=${path.relative(ROOT, target)} bytes=${output.length}\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`TD02_ESM_SHADOW_FAIL: ${error.message}\n`);
  process.exitCode = 1;
}
