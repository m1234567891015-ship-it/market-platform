"use strict";

/* P2-09..P2-12: deterministic frontend responsibility and contract evidence. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { execFileSync } = require("node:child_process");

const ROOT = path.join(__dirname, "..");
const read = (relativePath) => fs.readFileSync(path.join(ROOT, relativePath), "utf8");
const source = Object.fromEntries([
  "js/state.js",
  "js/shared-calc.js",
  "js/render-shared.js",
  "js/page-home.js",
  "js/page-us.js",
  "js/page-global-market-futures.js",
  "js/page-global-market-options.js",
  "js/page-global-market-assethub.js",
  "js/page-tw.js",
  "js/stock-detail.js",
].map((file) => [file, read(file)]));

// P2-09: shared-calc is not allowed to cross the transport, DOM, or storage boundary.
const sharedCalc = source["js/shared-calc.js"];
assert.doesNotMatch(sharedCalc, /\bfetch\s*\(/, "shared-calc must not issue API requests");
assert.doesNotMatch(sharedCalc, /\b(fetchWithTimeout|XMLHttpRequest)\b/, "shared-calc must not own provider transport");
assert.doesNotMatch(sharedCalc, /\b(localStorage|sessionStorage)\b/, "shared-calc must not own browser storage");
assert.doesNotMatch(sharedCalc, /\b(document\.(querySelector|querySelectorAll|getElementById|createElement)|addEventListener)\b/, "shared-calc must not own DOM/UI wiring");
assert.match(sharedCalc, /function buildMarketBreadthIndicators\(detail, allStocks = \[\], history = \[\]\)/);
assert.match(sharedCalc, /function analyzeTechnicalTheories\(detail, \{ marketBreadth = null \} = \{\}\)/);
assert.match(source["js/state.js"], /twEtfState\.getMarketBreadthContext = \(detail\) =>/);
assert.match(source["js/state.js"], /twEtfState\.saveMarketBreadthHistory = \(history\) =>/);
assert.doesNotMatch(source["js/state.js"], /buildMarketBreadthIndicators/);

// P2-11: the selected pure calculation extraction is deterministic and has explicit consumers.
const storage = {
  values: new Map(),
  getItem(key) { return this.values.get(key) || null; },
  setItem(key, value) { this.values.set(key, String(value)); },
};
const stocks = [
  { market: "TW", securityType: "STOCK", code: "1101", pct: "1.0" },
  { market: "TW", securityType: "STOCK", code: "1102", pct: "-1.0" },
  { market: "TW", securityType: "STOCK", code: "1103", pct: "0" },
];
const sandbox = {
  console,
  Number,
  Math,
  Date,
  JSON,
  Object,
  Array,
  Map,
  Set,
  RegExp,
  Intl,
  parseFloat,
  parseInt,
  localStorage: storage,
  sessionStorage: storage,
  window: { TWSE_DATA: { snapshotDate: "2026-09-25" }, TWSE_ALL_STOCKS: stocks },
};
vm.createContext(sandbox);
vm.runInContext(read("js/state.js"), sandbox, { filename: "js/state.js" });
sandbox.parseAnalysisNumber = (value) => Number(value);
vm.runInContext(sharedCalc, sandbox, { filename: "js/shared-calc.js" });

const history = [{ date: "2026-09-24", market: "TW", adl: 4 }];
const breadthA = sandbox.buildMarketBreadthIndicators(
  { market: "TW", snapshotDate: "2026-09-25" },
  stocks,
  history,
);
const breadthB = sandbox.buildMarketBreadthIndicators(
  { market: "TW", snapshotDate: "2026-09-25" },
  stocks,
  history,
);
assert.deepEqual(JSON.parse(JSON.stringify(breadthA)), JSON.parse(JSON.stringify(breadthB)));
assert.equal(breadthA.advancing, 1);
assert.equal(breadthA.declining, 1);
assert.equal(breadthA.previousAdl, 4);
assert.equal(breadthA.adl, 4);

const stateContext = vm.runInContext(
  'twEtfState.getMarketBreadthContext({ market: "TW", snapshotDate: "2026-09-25" })',
  sandbox,
);
const persistedBreadth = sandbox.buildMarketBreadthIndicators(stateContext.detail, stateContext.stocks, stateContext.history);
sandbox.p2PersistedBreadth = persistedBreadth;
vm.runInContext('twEtfState.saveMarketBreadthHistory(p2PersistedBreadth.nextHistory)', sandbox);
assert.equal(persistedBreadth.historyCount, 1);
assert.ok(storage.getItem("market-pulse-market-breadth-v1"), "state owner must persist breadth history outside shared-calc");
assert.equal(typeof sandbox.buildBacktestLearningModel.calculateAssetTransactionCost, "function");
assert.match(source["js/page-tw.js"], /buildBacktestLearningModel\.calculateAssetTransactionCost/);
assert.match(source["js/render-shared.js"], /buildBacktestLearningModel\.calculateAssetTransactionCost/);

// P2-12: source-load, initialization, API, schema, selector, fallback, and event contracts.
const syntaxFiles = Object.keys(source).filter((file) => file.startsWith("js/"));
syntaxFiles.forEach((file) => execFileSync(process.execPath, ["--check", path.join(ROOT, file)], { stdio: "pipe" }));

const initializationContracts = [
  ["js/page-home.js", "renderMarketPage"],
  ["js/page-us.js", "initUsStockSearchPage"],
  ["js/page-global-market-futures.js", "renderDerivativesFuturesPanel"],
  ["js/page-global-market-options.js", "initGlobalMarketPage"],
  ["js/page-global-market-assethub.js", "initAssetHubPage"],
  ["js/page-tw.js", "initWatchlistPage"],
];
initializationContracts.forEach(([file, symbol]) => assert.match(source[file], new RegExp(`function ${symbol}\\b`), `${file} must retain ${symbol}`));

const apiContracts = [
  ["js/page-home.js", /\/api\/market\/penny-sector-recommendations/],
  ["js/page-us.js", /\/api\/us-market\//],
  ["js/page-global-market-futures.js", /\/api\/us-market\//],
  ["js/page-global-market-options.js", /\/api\/options\/chain/],
  ["js/page-global-market-assethub.js", /\/api\/global-market\//],
  ["js/page-tw.js", /\/api\/twse\//],
];
apiContracts.forEach(([file, contract]) => assert.match(source[file], contract, `${file} API path contract drifted`));

const htmlContracts = [
  ["index.html", /data-page="home"/, /id="source-note"/],
  ["us-stocks.html", /data-page="global-market"/, /id="global-market-root"/],
  ["futures.html", /data-market-category="futures"/, /id="global-market-root"/],
  ["options.html", /data-market-category="options"/, /id="global-market-root"/],
  ["tw-stocks.html", /data-page="sectors"/, /id="sector-grid"/],
];
htmlContracts.forEach(([file, pageContract, selectorContract]) => {
  const html = read(file);
  assert.match(html, pageContract, `${file} page initialization contract drifted`);
  assert.match(html, selectorContract, `${file} DOM selector contract drifted`);
});

const allPageSource = Object.values(source).join("\n");
assert.match(allPageSource, /fallback/i, "fallback rendering contract must remain represented");
assert.match(allPageSource, /catch \(error\)/, "API error rendering contract must remain represented");
assert.match(source["js/page-global-market-assethub.js"], /EXECUTION_STATUS/);
assert.match(source["js/page-global-market-assethub.js"], /liquidityEligibility/);
assert.match(source["js/page-global-market-assethub.js"], /pointInTimeStatus/);
assert.match(source["js/page-global-market-assethub.js"], /P\/L Trust/);
assert.match(source["js/page-global-market-futures.js"], /addEventListener/);
assert.match(source["js/page-global-market-options.js"], /addEventListener/);
assert.match(source["js/page-global-market-assethub.js"], /addEventListener/);
assert.match(source["js/page-tw.js"], /addEventListener/);
assert.match(source["js/page-us.js"], /addEventListener/);

const breadthConsumers = [
  "js/stock-detail.js",
  "js/page-global-market-futures.js",
  "js/page-us.js",
  "js/page-tw.js",
].reduce((count, file) => count + (source[file].match(/twEtfState\.getMarketBreadthContext\(detail\)/g) || []).length, 0);
assert.equal(breadthConsumers, 6, "all existing technical-theory consumers must pass explicit breadth context");
assert.doesNotMatch(allPageSource, /analyzeTechnicalTheories\(detail\);/);
assert.equal((allPageSource.match(/twEtfState\.saveMarketBreadthHistory\(marketBreadth\?\.nextHistory\)/g) || []).length, 6);

console.log("P2_FRONTEND_CONTRACT_OK: shared responsibility, page audit targets, selected extraction, and frontend contract matrix");
