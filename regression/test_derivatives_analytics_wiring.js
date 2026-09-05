const fs = require("node:fs");
const { execFileSync } = require("node:child_process");

const page = fs.readFileSync("derivatives-analytics.html", "utf8");
const loader = fs.readFileSync("market-pulse-esm-loader.js", "utf8");
const pwa = fs.readFileSync("pwa.js", "utf8");
const serviceWorker = fs.readFileSync("service-worker.js", "utf8");
const moduleSource = fs.readFileSync("js/page-global-market-assethub.js", "utf8");
const main = fs.readFileSync("js/main.js", "utf8");
const shared = fs.readFileSync("js/render-shared.js", "utf8");
const bundled = fs.readFileSync("market-pulse-esm.min.js", "utf8");
const manifest = JSON.parse(fs.readFileSync("docs/TD02_FULL_ESM_build_manifest_2026-09-01.json", "utf8"));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(page.includes('<body data-page="derivatives-analytics">'), "page identity missing");
const pageVersion = page.match(/market-pulse-esm-loader\.js\?v=([^"']+)/)?.[1];
assert(pageVersion && pageVersion === manifest.version, "page loader version is not the build version");
const computedVersion = execFileSync(process.execPath, ["regression/td02_full_esm_build.js", "--print-version"], { encoding: "utf8" }).trim();
assert(computedVersion === manifest.version, "build version is not reproducible from runtime inputs");
assert(loader.includes("document.currentScript"), "loader does not derive runtime version from its own URL");
assert(loader.includes("encodeURIComponent(runtimeVersion)"), "loader does not forward runtime version to bundle");
assert(bundled.includes(`market-pulse-esm.min.js.map?v=${manifest.version}`), "bundle source map version is stale");
assert(pwa.includes(`const VERSION = "${manifest.version}";`), "PWA version is not the build version");
assert(pwa.includes(`service-worker.js?v=${manifest.version}`), "PWA service-worker URL is not the build version");
assert(serviceWorker.includes(`market-pulse-swr-${manifest.version}`), "service-worker cache generation is not the build version");
assert(serviceWorker.includes("self.skipWaiting()"), "service-worker install does not activate the new generation");
assert(serviceWorker.includes("self.clients.claim()"), "service-worker activate does not claim clients");
assert(serviceWorker.includes("key !== RUNTIME_CACHE"), "service-worker does not remove obsolete cache generations");
assert(serviceWorker.includes("return cached || revalidate"), "service-worker runtime cache strategy changed unexpectedly");
assert(!serviceWorker.includes("20260901-td02-full-esm-1"), "service-worker still pins the retired cache generation");
assert(main.includes('page === "derivatives-analytics"'), "main page dispatch missing");
assert(main.includes("initDerivativesAnalyticsPage();"), "initializer invocation missing");
for (const endpoint of [
  "/api/futures?limit=12",
  "/api/options?limit=12",
  "/api/options/chain?underlying=TXO&source=auto",
  "/api/pcr?underlying=TXO&source=auto",
  "/api/institution?product=TX",
  "/api/basis?future=TX&spot=TAIEX",
]) assert(moduleSource.includes(endpoint), `endpoint missing: ${endpoint}`);
assert(moduleSource.includes('futures: "TAIFEX 官方期貨日報"'), "futures placeholder source is not TAIFEX");
assert(moduleSource.includes("Derivatives analytics API subsets unavailable"), "API diagnostics missing");
assert(shared.includes("return { data: null, error:"), "API client fail-closed contract missing");
assert(moduleSource.includes("const futuresPayload = assetPayloads.futuresPayload"), "futures success payload binding missing");
assert(moduleSource.includes("chainResult.error ?"), "partial chain failure rendering missing");
assert(moduleSource.includes("不產生策略組合或損益判斷"), "strategy fail-closed copy missing");
assert(bundled.includes("/api/options/chain"), "ESM bundle is stale");
assert(!page.includes("td02-full-esm-20260901-1"), "page still pins the retired fixed runtime version");
console.log("DERIVATIVES_ANALYTICS_WIRING_OK");
