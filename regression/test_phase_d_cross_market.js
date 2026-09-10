/* Phase D targeted contract tests.  The adapter assertions are isolated from
 * providers, storage, and the production database; the runtime section also
 * executes the real finance-mode initializer against controlled API fixtures.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("js/shared-calc.js", "utf8");
const assetHubSource = fs.readFileSync("js/page-global-market-assethub.js", "utf8");
const sharedRenderSource = fs.readFileSync("js/render-shared.js", "utf8");
const today = new Date().toISOString().slice(0, 10);
const context = {
  window: {},
  parseMarketNumber(value) {
    const parsed = Number.parseFloat(String(value ?? "").replace(/,/g, "").replace(/%/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  },
  console,
};
context.window.buildSharedFreshnessConfidenceModel = (payload, options = {}) => {
  const status = payload.freshnessStatus || "Fresh";
  return {
    status,
    label: status,
    detail: `fixture ${status}`,
    asOf: payload.snapshotDate || today,
    updatedAt: payload.updatedAt || today,
    confidence: status === "Fresh" && options.hasDecisionEvidence
      ? { label: "有限", detail: "fixture evidence" }
      : { label: "不足", detail: "fixture gate" },
  };
};
vm.runInNewContext(source, context, { filename: "shared-calc.js" });

function item(symbol, pct, extra = {}) {
  return { symbol, close: "100", pct: String(pct), date: today, ...extra };
}

function alignedPayloads() {
  return [
    { category: "tw", snapshotDate: today, updatedAt: today, marketOverview: [{ name: "TAIEX", value: "100", pct: "+1.00%" }] },
    { category: "us-stocks", snapshotDate: today, updatedAt: today, items: [item("^GSPC", 1), item("^VIX", 1)] },
    { category: "us-etf", snapshotDate: today, updatedAt: today, items: [item("SPY", 1)] },
    { category: "futures", snapshotDate: today, updatedAt: today, items: [item("ES=F", 1)] },
    { category: "options", snapshotDate: today, updatedAt: today, items: [item("TXO", 1)] },
    { category: "bonds", snapshotDate: today, updatedAt: today, items: [item("DX-Y.NYB", 1), item("^TNX", 1)] },
    { category: "precious-metals", snapshotDate: today, updatedAt: today, items: [item("GC=F", 1)] },
  ];
}

const runtimeCalls = [];
const runtimeResponses = new Map();
const runtimeContext = {
  console,
  window: null,
  document: {
    body: { dataset: { page: "asset-hub", assetHubMode: "finance" } },
    getElementById(id) {
      return id === "asset-hub-root" ? { innerHTML: "" } : null;
    },
  },
  fetchWithTimeout(url) {
    runtimeCalls.push(url);
    const payload = runtimeResponses.get(url);
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(payload),
    });
  },
  parseMarketNumber(value) {
    const parsed = Number.parseFloat(String(value ?? "").replace(/,/g, "").replace(/%/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  },
  escapeHtml(value) {
    return String(value ?? "");
  },
};
runtimeContext.window = runtimeContext;
runtimeContext.fetchWithTimeout.createRequestScheduler = () => ({
  schedule(load) {
    return load();
  },
});
runtimeContext.window.buildSharedFreshnessConfidenceModel = (payload, options = {}) => {
  const status = payload.freshnessStatus || "Fresh";
  return {
    status,
    label: status,
    detail: `fixture ${status}`,
    asOf: payload.snapshotDate || today,
    updatedAt: payload.updatedAt || today,
    confidence: status === "Fresh" && options.hasDecisionEvidence
      ? { label: "有限", detail: "fixture evidence" }
      : { label: "不足", detail: "fixture gate" },
  };
};
vm.createContext(runtimeContext);
vm.runInContext(fs.readFileSync("js/shared-calc.js", "utf8"), runtimeContext, { filename: "shared-calc.js" });
const assetHubRuntimeSource = fs.readFileSync("js/page-global-market-assethub.js", "utf8");
vm.runInContext(`${assetHubRuntimeSource}
  renderAssetHubPage = (...args) => { globalThis.__renderedAssetHub = args; };
  globalThis.__initAssetHubPage = initAssetHubPage;`, runtimeContext, { filename: "page-global-market-assethub.js" });

function runtimePayloads(twOverrides = {}) {
  return new Map([
    ["/api/twse/live-overview", { category: "tw", snapshotDate: today, updatedAt: today, marketOverview: [{ name: "TAIEX", value: "100", pct: "+1.00%" }], sourceLinks: { market: "https://www.twse.com.tw/" }, ...twOverrides }],
    ["/api/global-market/us-stocks?limit=all", { category: "us-stocks", snapshotDate: today, updatedAt: today, items: [item("^GSPC", 1), item("^VIX", 1)] }],
    ["/api/us-market/etf-center?quoteLimit=48", { category: "us-etf", snapshotDate: today, updatedAt: today, items: [item("SPY", 1)] }],
    ["/api/global-market/futures?limit=all", { category: "futures", snapshotDate: today, updatedAt: today, items: [item("ES=F", 1)] }],
    ["/api/global-market/options?limit=all", { category: "options", snapshotDate: today, updatedAt: today, items: [item("TXO", 1)] }],
    ["/api/global-market/precious-metals?limit=all", { category: "precious-metals", snapshotDate: today, updatedAt: today, items: [item("GC=F", 1)] }],
    ["/api/global-market/bonds?limit=all", { category: "bonds", snapshotDate: today, updatedAt: today, items: [item("DX-Y.NYB", 1), item("^TNX", 1)] }],
    ["/api/us-market/options-chain/SPY", {}],
  ]);
}

async function runFinanceModeRuntime(twOverrides = {}) {
  runtimeCalls.length = 0;
  runtimeContext.__renderedAssetHub = null;
  runtimeResponses.clear();
  for (const [url, payload] of runtimePayloads(twOverrides)) runtimeResponses.set(url, payload);
  await runtimeContext.__initAssetHubPage();
  return {
    calls: runtimeCalls.slice(),
    payloads: runtimeContext.__renderedAssetHub?.[0] || [],
  };
}

async function main() {
  const runtime = await runFinanceModeRuntime();
  assert.ok(runtime.calls.includes("/api/twse/live-overview"), "finance mode must acquire TW through the existing endpoint");
  const twPayload = runtime.payloads.find((payload) => payload.category === "tw");
  assert.ok(twPayload?.marketOverview?.length, "TW response must reach the asset-hub payload path");
  const runtimeDecision = runtimeContext.window.buildCrossMarketDecisionModel(runtime.payloads);
  const runtimeTw = runtimeDecision.inputs.find((input) => input.market === "TW");
  assert.equal(runtimeTw.normalizationStatus, "normalized");
  assert.equal(runtimeTw.canUseForDecision, "YES");
  assert.equal(runtimeTw.provenance, "https://www.twse.com.tw/");
  assert.equal(runtimeTw.timestamp, today);

  const unavailableRuntime = await runFinanceModeRuntime({ freshnessStatus: "Unavailable", error: "fixture unavailable" });
  const unavailableDecision = runtimeContext.window.buildCrossMarketDecisionModel(unavailableRuntime.payloads);
  const unavailableTw = unavailableDecision.inputs.find((input) => input.market === "TW");
  assert.equal(unavailableTw.normalizationStatus, "unsupported");
  assert.equal(unavailableTw.canUseForDecision, "NO");
  assert.ok(unavailableDecision.evidenceGroups.unavailable.some((item) => item.label === "TW"));

const aligned = context.window.buildCrossMarketDecisionModel(alignedPayloads());
assert.equal(aligned.decision, "Aligned up");
assert.ok(aligned.inputs.every((input) => input.normalizationStatus === "normalized"));
assert.ok(aligned.inputs.every((input) => input.canUseForDecision === "YES"));
assert.equal(aligned.temperature.value, null, "D must not invent a cross-market score");
assert.equal(aligned.evidenceGroups.conflicting.length, 0);
assert.ok(aligned.evidenceGroups.confirming.length >= 2);
assert.ok(aligned.marketAlignment.some((input) => input.asset === "VIX"));
assert.ok(aligned.risks.length >= 1);
assert.ok(aligned.actions.length >= 1);
assert.ok(aligned.invalidation.length >= 1);
assert.doesNotMatch(JSON.stringify(aligned), /\b(buy|sell|買進|賣出)\b/i);

const conflicted = context.window.buildCrossMarketDecisionModel([
  { category: "us-stocks", snapshotDate: today, updatedAt: today, items: [item("^GSPC", 1), item("^VIX", 1)] },
  { category: "us-etf", snapshotDate: today, updatedAt: today, items: [item("SPY", -1)] },
]);
assert.equal(conflicted.decision, "Mixed / conflicted");
assert.equal(conflicted.evidenceGroups.conflicting.length, 3);
assert.match(conflicted.actions[0], /衝突/);

const gated = context.window.buildCrossMarketDecisionModel([
  { category: "us-stocks", snapshotDate: today, updatedAt: today, freshnessStatus: "Delayed", items: [item("^GSPC", 1)] },
  { category: "us-etf", snapshotDate: today, updatedAt: today, freshnessStatus: "Unavailable", error: "fixture unavailable", items: [] },
]);
assert.equal(gated.decision, "Unavailable / insufficient evidence");
assert.ok(gated.evidenceGroups.stale.length >= 1);
assert.ok(gated.evidenceGroups.unavailable.length >= 1);
assert.ok(gated.inputs.every((input) => input.canUseForDecision !== "YES"));

const first = JSON.stringify(aligned);
const second = JSON.stringify(context.window.buildCrossMarketDecisionModel(alignedPayloads()));
assert.equal(first, second, "normalization and orchestration must be deterministic");

assert.match(assetHubSource, /id="market-decision-summary"/);
assert.match(assetHubSource, /buildCrossMarketDecisionModel/);
assert.match(assetHubSource, /"us-etf"/);
assert.match(assetHubSource, /market-decision-summary/);
assert.match(sharedRenderSource, /Market Alignment/);
assert.match(sharedRenderSource, /Cross-Market Risks/);
assert.match(sharedRenderSource, /Actions \/ Guidance/);

console.log("PHASE_D_CROSS_MARKET_PASS");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
