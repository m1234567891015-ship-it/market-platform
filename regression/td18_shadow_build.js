/*
 * TD-18 H-10-01: deterministic, isolated shadow build.
 *
 * This is intentionally a shadow-only concatenation builder. It never writes
 * to production assets, HTML, baselines, CSP or deployment configuration.
 */
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const BUILDER_NAME = "td18-shadow-concat";
const BUILDER_VERSION = "1.0.0";
const LOCKFILE_NAME = "td18_shadow_build.lock.json";
const ROOT = path.resolve(__dirname, "..");
const LOCKFILE_PATH = path.join(__dirname, LOCKFILE_NAME);

function fail(message) {
  throw new Error("[td18-shadow-build] " + message);
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (error) {
    fail("cannot read JSON " + filePath + ": " + error.message);
  }
}

function parseOutputArgument() {
  const index = process.argv.indexOf("--out");
  if (index < 0 || !process.argv[index + 1]) {
    fail("usage: node regression/td18_shadow_build.js --out <isolated-directory>");
  }
  return path.resolve(process.argv[index + 1]);
}

function assertLock(lock) {
  if (lock.lockfileVersion !== 1) fail("unsupported lockfileVersion");
  if (lock.nodeVersion !== process.versions.node) {
    fail("Node version " + process.versions.node + " does not match locked " + lock.nodeVersion);
  }
  if (!lock.builder || lock.builder.name !== BUILDER_NAME || lock.builder.version !== BUILDER_VERSION) {
    fail("builder lock does not match this implementation");
  }
  if (lock.builder.sourceMapVersion !== 3) fail("source map version must be 3");
  if (!Array.isArray(lock.bundles) || lock.bundles.length !== 3) {
    fail("lock must define exactly three shadow bundles");
  }
}

function assertIsolatedOutput(outDir) {
  const forbidden = new Set([
    ROOT,
    path.join(ROOT, "js"),
    path.join(ROOT, "assets"),
    path.join(ROOT, "regression", "baseline"),
  ]);
  if (forbidden.has(outDir)) fail("refusing non-isolated output directory " + outDir);
  if (!outDir.startsWith(ROOT + path.sep)) {
    fail("output directory must be inside the repository workspace: " + outDir);
  }
}

function sourceMapFor(bundle, outputName) {
  return {
    version: 3,
    file: outputName,
    sourceRoot: "",
    sources: bundle.inputs.map((input) => input.replaceAll(path.sep, "/")),
    names: [],
    mappings: "",
  };
}

function buildBundle(bundle, outDir) {
  const parts = [];
  const inputs = [];
  for (const relativeInput of bundle.inputs) {
    const inputPath = path.join(ROOT, relativeInput);
    if (!fs.existsSync(inputPath)) fail("locked input does not exist: " + relativeInput);
    const content = fs.readFileSync(inputPath);
    inputs.push({
      path: relativeInput.replaceAll(path.sep, "/"),
      bytes: content.length,
      sha256: sha256(content),
    });
    parts.push(Buffer.from("/* shadow-input:" + relativeInput.replaceAll(path.sep, "/") + " */\n", "utf8"));
    parts.push(content);
    parts.push(Buffer.from("\n", "utf8"));
  }
  const output = Buffer.concat(parts);
  const outputPath = path.join(outDir, bundle.output);
  const mapPath = path.join(outDir, bundle.sourceMap);
  const map = Buffer.from(JSON.stringify(sourceMapFor(bundle, bundle.output), null, 2) + "\n", "utf8");
  fs.writeFileSync(outputPath, output);
  fs.writeFileSync(mapPath, map);
  return {
    name: bundle.name,
    output: bundle.output,
    sourceMap: bundle.sourceMap,
    bytes: output.length,
    sha256: sha256(output),
    sourceMapBytes: map.length,
    sourceMapSha256: sha256(map),
    inputs,
  };
}

function main() {
  const outDir = parseOutputArgument();
  assertIsolatedOutput(outDir);
  const lock = readJson(LOCKFILE_PATH);
  assertLock(lock);
  fs.mkdirSync(outDir, { recursive: true });

  const bundles = lock.bundles.map((bundle) => buildBundle(bundle, outDir));
  const manifest = {
    schemaVersion: 1,
    builder: {
      name: BUILDER_NAME,
      version: BUILDER_VERSION,
      nodeVersion: process.versions.node,
      lockfile: LOCKFILE_NAME,
    },
    policy: {
      mode: "shadow-only",
      productionAssetsModified: false,
      htmlModified: false,
      baselineModified: false,
      cspModified: false,
      deploymentModified: false,
      sourceMapMode: "v3-empty-mappings-with-fixed-source-list",
    },
    bundles,
  };
  const manifestPath = path.join(outDir, "manifest.json");
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n", "utf8");
  process.stdout.write(JSON.stringify({ output: outDir, manifest: "manifest.json", bundles }, null, 2) + "\n");
}

try {
  main();
} catch (error) {
  process.stderr.write(error.message + "\n");
  process.exitCode = 1;
}
