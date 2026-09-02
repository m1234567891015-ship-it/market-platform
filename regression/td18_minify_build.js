/*
 * TD-18: deterministic Terser minify build for the locked bundle inputs.
 *
 * The builder is safe by construction: output must be an isolated directory
 * inside the workspace. It never writes production assets, HTML, baselines,
 * CSP, Service Worker or deployment configuration.
 */
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { minify } = require("terser");

const BUILDER_NAME = "td18-minify-terser";
const BUILDER_VERSION = "1.0.0";
const LOCKFILE_NAME = "td18_minify_build.lock.json";
const ROOT = path.resolve(__dirname, "..");
const LOCKFILE_PATH = path.join(__dirname, LOCKFILE_NAME);

function fail(message) {
  throw new Error("[td18-minify-build] " + message);
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
    fail("usage: node regression/td18_minify_build.js --out <isolated-directory>");
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
  if (lock.builder.terserVersion !== require("terser/package.json").version) {
    fail("installed Terser does not match the lockfile");
  }
  if (lock.options.mangleTopLevel || lock.options.compressTopLevel) {
    fail("top-level mangling/compression must remain disabled for classic globals");
  }
  if (!Array.isArray(lock.bundles) || lock.bundles.length !== 3) {
    fail("lock must define exactly three minified bundles");
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

async function buildBundle(bundle, outDir, lock) {
  const files = {};
  const inputs = [];
  for (const relativeInput of bundle.inputs) {
    const inputPath = path.join(ROOT, relativeInput);
    if (!fs.existsSync(inputPath)) fail("locked input does not exist: " + relativeInput);
    const content = fs.readFileSync(inputPath);
    const normalized = relativeInput.replaceAll(path.sep, "/");
    files[normalized] = content.toString("utf8");
    inputs.push({
      path: normalized,
      bytes: content.length,
      sha256: sha256(content),
    });
  }

  const result = await minify(files, {
    compress: lock.options.compress,
    mangle: lock.options.mangle,
    format: lock.options.format,
    sourceMap: {
      filename: bundle.output,
      url: bundle.sourceMap,
      includeSources: true,
    },
  });
  if (!result.code || !result.map) fail("Terser returned incomplete output for " + bundle.name);

  const output = Buffer.from(result.code + "\n", "utf8");
  const map = Buffer.from(result.map + "\n", "utf8");
  const outputPath = path.join(outDir, bundle.output);
  const mapPath = path.join(outDir, bundle.sourceMap);
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

async function main() {
  const outDir = parseOutputArgument();
  assertIsolatedOutput(outDir);
  const lock = readJson(LOCKFILE_PATH);
  assertLock(lock);
  fs.mkdirSync(outDir, { recursive: true });

  const bundles = [];
  for (const bundle of lock.bundles) {
    bundles.push(await buildBundle(bundle, outDir, lock));
  }
  const manifest = {
    schemaVersion: 1,
    builder: {
      name: BUILDER_NAME,
      version: BUILDER_VERSION,
      nodeVersion: process.versions.node,
      terserVersion: require("terser/package.json").version,
      lockfile: LOCKFILE_NAME,
    },
    policy: {
      mode: "minify-shadow-only",
      productionAssetsModified: false,
      htmlModified: false,
      baselineModified: false,
      cspModified: false,
      serviceWorkerModified: false,
      deploymentModified: false,
      topLevelMangling: false,
      sourceMapMode: "terser-v3-with-sources",
    },
    bundles,
  };
  fs.writeFileSync(path.join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");
  process.stdout.write(JSON.stringify({ output: outDir, manifest: "manifest.json", bundles }, null, 2) + "\n");
}

main().catch((error) => {
  process.stderr.write(error.message + "\n");
  process.exitCode = 1;
});
