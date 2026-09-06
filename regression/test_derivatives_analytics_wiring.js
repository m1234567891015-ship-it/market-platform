const fs = require("node:fs");
const crypto = require("node:crypto");
const { execFileSync } = require("node:child_process");

const page = fs.readFileSync("derivatives-analytics.html", "utf8");
const loader = fs.readFileSync("market-pulse-esm-loader.js", "utf8");
const pwa = fs.readFileSync("pwa.js", "utf8");
const serviceWorker = fs.readFileSync("service-worker.js", "utf8");
const moduleSource = fs.readFileSync("js/page-global-market-assethub.js", "utf8");
const main = fs.readFileSync("js/main.js", "utf8");
const shared = fs.readFileSync("js/render-shared.js", "utf8");
const api = fs.readFileSync("js/api.js", "utf8");
const bundled = fs.readFileSync("market-pulse-esm.min.js", "utf8");
const manifest = JSON.parse(fs.readFileSync("docs/TD02_FULL_ESM_build_manifest_2026-09-01.json", "utf8"));

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function sha256(file) {
  return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
}

assert(page.includes('<body data-page="derivatives-analytics">'), "page identity missing");
const pageVersion = page.match(/market-pulse-esm-loader\.js\?v=([^"']+)/)?.[1];
assert(pageVersion && pageVersion === manifest.version, "page loader version is not the build version");
const computedVersion = execFileSync(process.execPath, ["regression/td02_full_esm_build.js", "--print-version"], { encoding: "utf8" }).trim();
assert(computedVersion === manifest.version, "build version is not reproducible from runtime inputs");
assert(sha256("market-pulse-esm.min.js") === manifest.output.sha256, "ESM bundle hash is not the manifest hash");
assert(sha256("market-pulse-esm.min.js.map") === manifest.sourceMap.sha256, "ESM source map hash is not the manifest hash");
assert(loader.includes(`const CURRENT_BUILD_VERSION = "${manifest.version}";`), "loader does not carry the generated current build version");
assert(loader.includes("document.currentScript"), "loader does not derive runtime version from its own URL");
assert(loader.includes("encodeURIComponent(runtimeVersion)"), "loader does not forward runtime version to bundle");
assert(loader.includes("stale runtime generation detected"), "legacy runtime mismatch recovery is missing");
assert(loader.includes("recovery already attempted; refusing reload loop"), "legacy recovery loop guard is missing");
assert(loader.includes('key.startsWith(APP_CACHE_PREFIX)'), "legacy recovery does not use an app-owned cache prefix");
assert(bundled.includes(`market-pulse-esm.min.js.map?v=${manifest.version}`), "bundle source map version is stale");
assert(pwa.includes(`const VERSION = "${manifest.version}";`), "PWA version is not the build version");
assert(pwa.includes(`service-worker.js?v=${manifest.version}`), "PWA service-worker URL is not the build version");
assert(pwa.includes('registrations.filter(isAppRegistration)'), "PWA unregisters registrations without app ownership checks");
assert(pwa.includes('keys.filter((key) => key.startsWith(APP_CACHE_PREFIX))'), "PWA deletes caches without app ownership checks");
assert(serviceWorker.includes(`market-pulse-swr-${manifest.version}`), "service-worker cache generation is not the build version");
assert(serviceWorker.includes("self.skipWaiting()"), "service-worker install does not activate the new generation");
assert(serviceWorker.includes("self.clients.claim()"), "service-worker activate does not claim clients");
assert(serviceWorker.includes("key !== RUNTIME_CACHE"), "service-worker does not remove obsolete cache generations");
assert(serviceWorker.includes("return cached || revalidate"), "service-worker runtime cache strategy changed unexpectedly");
assert(!serviceWorker.includes("20260901-td02-full-esm-1"), "service-worker still pins the retired cache generation");
assert(serviceWorker.includes("CACHEABLE_STATIC_EXTENSIONS = [\".js\", \".css\", \".svg\", \".png\", \".webmanifest\"]"), "service-worker still caches HTML documents");
assert(serviceWorker.includes('url.pathname.startsWith("/api/")'), "service-worker API bypass was removed");
assert(shared.includes('response.headers.get("content-type")'), "derivatives API content-type validation is missing");
assert(shared.includes("await response.text()"), "derivatives API body validation is missing");
assert(shared.includes("INVALID_RESPONSE"), "derivatives API invalid-response contract is missing");
assert(api.includes('controlledError.code = timedOut ? "TIMEOUT" : "CANCELLED";'), "fetch timeout/abort normalization is missing");
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
assert(shared.includes("data: null") && shared.includes("errorCode: code"), "API client fail-closed contract missing");
assert(moduleSource.includes("const futuresPayload = assetPayloads.futuresPayload"), "futures success payload binding missing");
assert(moduleSource.includes("chainResult.error ?"), "partial chain failure rendering missing");
assert(moduleSource.includes("不產生策略組合或損益判斷"), "strategy fail-closed copy missing");
assert(bundled.includes("/api/options/chain"), "ESM bundle is stale");
assert(!page.includes("td02-full-esm-20260901-1"), "page still pins the retired fixed runtime version");
console.log("DERIVATIVES_ANALYTICS_WIRING_OK");
