const fs = require("node:fs");

const page = fs.readFileSync("derivatives-analytics.html", "utf8");
const loader = fs.readFileSync("market-pulse-esm-loader.js", "utf8");
const moduleSource = fs.readFileSync("js/page-global-market-assethub.js", "utf8");
const main = fs.readFileSync("js/main.js", "utf8");
const shared = fs.readFileSync("js/render-shared.js", "utf8");
const bundled = fs.readFileSync("market-pulse-esm.min.js", "utf8");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

assert(page.includes('<body data-page="derivatives-analytics">'), "page identity missing");
assert(page.includes("market-pulse-esm-loader.js"), "ESM loader missing");
assert(loader.includes("market-pulse-esm.min.js"), "loader bundle missing");
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
console.log("DERIVATIVES_ANALYTICS_WIRING_OK");
