"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const acorn = require("acorn");

const ROOT = path.join(__dirname, "..");
const read = (relativePath) => fs.readFileSync(path.join(ROOT, relativePath), "utf8");
const sha256 = (value) => crypto.createHash("sha256").update(value, "utf8").digest("hex");
const parse = (source, filename) => acorn.parse(source, {
  ecmaVersion: "latest",
  sourceType: "script",
  allowAwaitOutsideFunction: true,
  locations: true,
  filename,
});

const contractPath = "docs/P4_03_GIANT_PAGE_MODULES_DECOMPOSITION_CONTRACT.md";
const contract = read(contractPath);
assert.match(contract, /Contract ID:\*\* `P4_03_GIANT_PAGE_MODULES_DECOMPOSITION_V1`/);
assert.equal(
  sha256(contract),
  "9ec9a9905ad697ce696e40c6ec8e9742e28f2af06541dbc39008ad213215b96b",
  "the frozen P4-03 contract must remain unchanged",
);

const groups = [
  {
    file: "js/page-global-market-shared.js",
    fingerprint: "1a8760a313a4c72408efae769e43689da75bf776ea8cb270e5efafc4d201cc09",
    members: `
      renderFuturesBacktestLearningCard getAssetHubItems getAssetHubUsableItems findAssetHubItem filterAssetHubItems
      assetHubDirection getAssetHubRegion getAssetHubItemUrl getAssetHubMetric groupAssetHubItemsByRegion
      renderAssetHubRegionChips renderAssetHubSchemaPanel renderAssetHubRegionalGroups renderAssetHubQuoteGrid
      renderAssetHubSummary renderAssetHubOnlineRows renderAssetHubOnlineTable renderAssetHubTaiwanFuturesCard
      renderAssetHubOptionContracts renderAssetHubPublicOptionChainCard pickTaiwanOptionRows getTaiwanOptionExpiryPrefix
      formatTaiwanOptionExpiryCode formatTaiwanOptionExpiryLabel renderTaiwanOptionExpiryTabs renderTaiwanOptionChainTable
      renderTaiwanOptionDistribution renderTaiwanOptionAnalysis renderTaiwanOptionChainCard findAssetHubItemAny
      findAssetHubUsableItemAny getAssetHubItemsBySymbols getAssetHubUsableBySymbols uniqueAssetHubItemsBySymbol
      clampAssetHubScore createAssetHubPlaceholder
    `.trim().split(/\s+/),
  },
  {
    file: "js/page-global-market-asset-finance.js",
    fingerprint: "22866255eaba81cbe25fe4b60714fc8ac6cbbdbf415d661ac0177a3e476df35b",
    members: `
      normalizeTreasuryYieldValue getAssetHubTreasuryYieldPoint formatAssetHubYield formatAssetHubRatio
      buildAssetHubFinanceModel buildAssetHubFinanceScenarios buildAssetHubAllocationAdvice renderAssetFinanceSignal
      renderAssetFinanceSignalPanel renderAssetFinanceCoreDashboard renderAssetFinanceMetalsPanel getAssetFinanceTrendRange
      buildAssetFinanceTrendDataset buildAssetFinanceTrendPoints buildAssetFinanceTrendSeriesList renderAssetFinanceTrendBody
      getAssetFinanceTrendStatus bindAssetFinanceTrendCursor initAssetFinanceTrendSwitchers renderAssetFinanceTrendPanelContent
      renderAssetFinanceMetalProfilesPanel buildAssetFinanceGlobalVenueInsight renderAssetFinanceDriverFactorCard
      formatAssetFinanceMetricPct averageAssetFinanceValues standardDeviationAssetFinanceValues buildAssetFinanceForecastItem
      buildAssetFinancePriceForecastItems renderAssetFinancePriceForecastBody renderAssetFinancePriceForecastContent
      renderAssetFinanceMetalDriversPanel renderAssetFinanceDecisionCenterPanel renderAssetFinanceSelectableMetalOnlineRows
      renderAssetFinanceSelectableBondOnlineRows buildAssetFinanceMetalsEtfConclusion renderAssetFinanceVolumeTrendChart
      getAssetFinanceVolumePayloadItem renderAssetFinanceSingleTrendRiskAnalysis getAssetFinanceBondProfile
      getAssetFinanceBondEtfLens renderAssetFinanceBondSingleAnalysis initAssetFinanceVolumeSelectors
      bindAssetFinanceVolumeCursor renderAssetFinanceMetalEtfSyncPanel buildAssetFinanceBondResearchImport
      renderAssetFinanceBondResearchHero renderAssetFinanceBondResearchMarketAnalysis renderAssetFinanceBondResearchPanel
      renderAssetFinanceScenarioPanel averageAssetFinancePct strongestAssetFinanceItem formatAssetFinancePct
      assetFinancePctTone renderAssetFinanceSyncStat renderAssetFinanceMetalsResearchSection getAssetFinanceBondRows
      isAssetFinanceTaiwanBond filterAssetFinanceBondRows getAssetFinanceBondFocusKey getAssetFinanceRateMoveTone
      getAssetFinanceBondFocusKind buildAssetFinanceBondFocusEtfPulse buildAssetFinanceBondFocusMetricSet
      buildAssetFinanceBondYieldFocusInsight buildAssetFinanceBondDashboardCommentary getAssetFinanceBondCommentaryPoints
      renderAssetFinanceBondCommentarySection renderAssetFinanceBondDashboardCommentary buildAssetFinanceBondMacroContext
      renderAssetFinanceBondDecisionOverview renderAssetFinanceBondCenterDashboard renderAssetFinanceBondRegionalMarketPanel
      renderAssetFinanceBondEtfCenterPanel renderAssetFinanceBondsResearchSection renderAssetFinanceCrossReferenceSection
      renderAssetHubFinanceDashboard renderAssetHubCompactQuotePanel renderAssetHubMetals renderAssetHubBonds
    `.trim().split(/\s+/),
  },
  {
    file: "js/page-global-market-derivatives.js",
    fingerprint: "70dea97cbc0cc017ad98ffa35957beb31e70af4ef537f79a26a910bdefb294a4",
    members: `
      getDerivativeOverviewItems renderDerivativeOverviewQuote renderDerivativeOverviewMetric
      getDerivativeOverviewTechnicalModel renderDerivativeOverviewInstitutionSummary buildDerivativeFuturesPositionAnalysis
      renderDerivativeFuturesPositionCard renderDerivativeOverviewInstitution getDerivativeOverviewNewsImpact
      buildDerivativeOverviewImpactModel renderDerivativeOverviewNews renderDerivativesMarketOverview
      renderDerivativePcrHistory renderDerivativeNewsItems renderDerivativeBasisCard renderInstitutionPositionCard
      loadDerivativesAssetHubPayloads renderDerivativePayloadSnapshot renderDerivativesAssetSnapshotGrid
      initDerivativesAnalyticsPage renderDerivativeAiReport renderDerivativeAiArchitectureCard initDerivativesAiPage
    `.trim().split(/\s+/),
  },
  {
    file: "js/page-global-market-assethub.js",
    fingerprint: "37f1a34a4609d4c920ab9f4f49cd66543b74863171bde145831101a6aa29c51b",
    members: `
      renderAssetHubFallbackPage renderAssetHubFutures renderAssetHubOptionsLegacy renderAssetHubOptions
      initAssetFinanceBondFocusControls renderAssetHubPage initAssetHubPage
    `.trim().split(/\s+/),
  },
];

const owners = new Map();
const sources = new Map();
for (const group of groups) {
  assert.equal(new Set(group.members).size, group.members.length, `${group.file}: duplicate frozen member`);
  const source = read(group.file);
  sources.set(group.file, source);
  const ast = parse(source, group.file);
  const functions = ast.body.filter((node) => node.type === "FunctionDeclaration");
  const actualNames = functions.map((node) => node.id.name);
  assert.deepEqual(actualNames, group.members, `${group.file}: function ownership/order drifted`);
  for (const member of group.members) {
    assert(!owners.has(member), `${member}: duplicate owner`);
    owners.set(member, group.file);
  }
  const fingerprint = sha256(functions
    .map((node) => `${node.id.name}\0${source.slice(node.start, node.end)}`)
    .join("\n\0"));
  assert.equal(fingerprint, group.fingerprint, `${group.file}: frozen function bodies changed`);
  const topLevelExtras = ast.body.filter((node) => node.type !== "FunctionDeclaration");
  if (group.file === "js/page-global-market-derivatives.js") {
    assert.equal(topLevelExtras.length, 1, "strategyEngine assignment must remain the only extra top-level statement");
    const expression = topLevelExtras[0];
    assert.equal(expression.type, "ExpressionStatement");
    assert.match(source.slice(expression.start, expression.end), /^initDerivativesAnalyticsPage\.strategyEngine\s*=\s*\(\(\)\s*=>/);
    assert.equal(
      sha256(source.slice(expression.start, expression.end)),
      "bac278622b4808e084928eecb67dcd64be17a12b368a2d3646c3bfb3a28f5bc0",
      "derivatives strategyEngine assignment changed",
    );
  } else {
    assert.deepEqual(topLevelExtras, [], `${group.file}: unexpected top-level runtime state`);
  }
}
assert.equal(owners.size, 145, "all 145 original functions must have exactly one owner");

const expectedRouteInputs = [
  "js/page-home.js",
  "js/page-us.js",
  "js/page-global-market-shared.js",
  "js/page-global-market-futures.js",
  "js/page-global-market-options.js",
  "js/page-global-market-asset-finance.js",
  "js/page-global-market-derivatives.js",
  "js/page-global-market-assethub.js",
  "js/page-tw.js",
  "js/legacy-unclassified.js",
  "js/main.js",
  "app.js",
];
const minifyLock = JSON.parse(read("regression/td18_minify_build.lock.json"));
const shadowLock = JSON.parse(read("regression/td18_shadow_build.lock.json"));
const routeInputs = (lock) => lock.bundles.find((bundle) => bundle.name === "route-bundle")?.inputs;
assert.deepEqual(routeInputs(minifyLock), expectedRouteInputs, "minified Classic/ESM route source order drifted");
assert.deepEqual(routeInputs(shadowLock), expectedRouteInputs, "shadow Classic route source order drifted");

const marketConfig = read("market_config.py");
for (const group of groups) {
  const basename = path.basename(group.file);
  assert.match(marketConfig, new RegExp(`\\"${basename}\\"`), `${basename} must be in the static allowlist`);
}

const routeRank = new Map(expectedRouteInputs.map((file, index) => [file, index]));
const allowedLegacyCycle = new Set([
  "js/page-global-market-futures.js->js/page-global-market-options.js",
  "js/page-global-market-options.js->js/page-global-market-futures.js",
]);
const pageSourceFiles = fs.readdirSync(path.join(ROOT, "js"))
  .filter((filename) => filename.endsWith(".js"))
  .map((filename) => `js/${filename}`);
const violations = [];
for (const callerFile of pageSourceFiles) {
  const source = read(callerFile);
  const ast = parse(source, callerFile);
  function visit(node) {
    if (!node || typeof node !== "object") return;
    if (node.type === "CallExpression" && node.callee.type === "Identifier" && owners.has(node.callee.name)) {
      const providerFile = owners.get(node.callee.name);
      const cycleKey = `${callerFile}->${providerFile}`;
      if (callerFile !== providerFile
        && !allowedLegacyCycle.has(cycleKey)
        && routeRank.has(callerFile)
        && routeRank.has(providerFile)
        && routeRank.get(providerFile) > routeRank.get(callerFile)) {
        violations.push(`${callerFile}:${node.loc.start.line} calls later module ${providerFile} (${node.callee.name})`);
      }
    }
    for (const [key, value] of Object.entries(node)) {
      if (["start", "end", "loc", "range", "raw"].includes(key)) continue;
      if (Array.isArray(value)) value.forEach(visit);
      else if (value && typeof value === "object") visit(value);
    }
  }
  visit(ast);
}
assert.deepEqual(violations, [], "a new route dependency violates the frozen runtime load order");

const runtime = {
  ASSET_HUB_REGION_ORDER: ["台灣", "美國", "歐洲", "亞洲", "全球 / 其他"],
  ASSET_HUB_SCHEMA_FALLBACK: { sources: [], tables: [], dashboardSignals: [], automation: "" },
  ASSET_HUB_OPTION_CHAIN_UNDERLYINGS: [["SPY", "S&P 500"]],
  parseMarketNumber(value) {
    if (value === null || value === undefined || value === "") return Number.NaN;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
  },
  escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
    })[character]);
  },
  safeUrl(value) { return String(value || "#"); },
  buildYahooFinanceUrl(symbol) { return `https://finance.example/${encodeURIComponent(symbol || "")}`; },
  formatGlobalValue(value) { return String(value ?? "--"); },
  formatGlobalVolume(value) { return String(value ?? "--"); },
  assetHubTone(item) { return Number(item?.pct) >= 0 ? "tone-up" : "tone-down"; },
  formatAssetOptionWhole(value) { return String(value ?? "--"); },
  formatAssetHubExpiration(value) { return String(value || "--"); },
  getActiveTaiwanOptionUnderlying() { return "TXO"; },
  getTaiwanOptionProductLabel() { return "台指選擇權"; },
};
vm.createContext(runtime);
for (const group of groups) {
  vm.runInContext(sources.get(group.file), runtime, { filename: group.file });
}
const fixtureItems = [
  { symbol: "TX", name: "<Taiwan Spot>", region: "台灣", close: 22000, pct: "1.2%", volume: 1200, date: "2026-10-02", sourceLink: "https://example.test/tx" },
  { symbol: "ES", name: "S&P Futures", region: "美國", close: 5000, pct: "-0.8%", volume: 800, date: "2026-10-02", sourceLink: "https://example.test/es" },
  { symbol: "BAD", name: "Unavailable", region: "美國", close: "n/a", pct: "--" },
];
const payload = { items: fixtureItems };
assert.deepEqual(
  Array.from(runtime.getAssetHubUsableItems(payload), (item) => item.symbol),
  ["TX", "ES"],
  "shared data helper must preserve usable-item filtering",
);
assert.equal(runtime.assetHubDirection({ summary: { advancers: 2, decliners: 1 } }), "上漲商品較多，短線風險偏好較穩。");
assert.deepEqual(
  Array.from(runtime.groupAssetHubItemsByRegion(fixtureItems), (group) => group.region),
  ["台灣", "美國"],
  "regional ordering must remain stable",
);
const quoteHtml = runtime.renderAssetHubQuoteGrid(fixtureItems.slice(0, 2));
assert.match(quoteHtml, /class="asset-quote-grid"/);
assert.match(quoteHtml, /&lt;Taiwan Spot&gt;/, "quote rendering must preserve escaped display text");
assert(quoteHtml.indexOf("TX") < quoteHtml.indexOf("ES"), "quote rendering must preserve input order");
assert.equal(runtime.formatAssetHubYield(3.25), "3.25%", "asset-finance formatter output must remain stable");
assert.deepEqual(
  Array.from(runtime.getDerivativeOverviewItems(payload, ["ES"], 2), (item) => item.symbol),
  ["ES", "TX"],
  "derivatives view-model selection must preserve preferred-symbol ordering",
);

const fingerprint = sha256(JSON.stringify(groups.map(({ file, fingerprint: digest, members }) => ({ file, digest, members }))));
console.log(`P4-03 decomposition/parity PASS: ${owners.size} functions, 4 modules, fingerprint=${fingerprint}`);
