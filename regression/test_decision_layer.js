"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const context = {
  console,
  Date,
  Math,
  Number,
  String,
  Array,
  Set,
  RegExp,
  window: { location: { pathname: "/index.html" } },
  document: {
    querySelectorAll: () => [],
    getElementById: () => null,
    querySelector: () => null,
    createElement: () => ({}),
  },
  escapeHtml: (value) => String(value),
};
vm.runInNewContext(fs.readFileSync(path.join(ROOT, "js", "render-shared.js"), "utf8"), context, { filename: "render-shared.js" });

const build = context.window.buildSharedFreshnessConfidenceModel;
const now = new Date("2026-09-09T12:00:00");
const freshPayload = {
  snapshotDate: "2026-09-09",
  institutionDate: "2026-09-09",
  activityDate: "2026-09-09",
  intradayDate: "2026-09-09",
};
assert.equal(build(freshPayload, { now, requirePrimary: true, hasDecisionEvidence: true }).status, "Fresh", "current complete data must be Fresh");
assert.equal(build({ ...freshPayload, snapshotDate: "2020-01-01", institutionDate: "2020-01-01", activityDate: "2020-01-01", intradayDate: "2020-01-01" }, { now, requirePrimary: true }).status, "Delayed", "old internally consistent data must not be Fresh");
assert.equal(build({ snapshotDate: "2026-09-09" }, { now, requirePrimary: true }).status, "Partial", "incomplete core data must be Partial");
assert.equal(build({ updatedAt: "2026-09-09T11:00:00", items: [{ symbol: "SPY" }] }, { now }).status, "Fresh", "current payload with usable data must be Fresh");
assert.notEqual(build({ updatedAt: "2026-09-09T11:00:00", error: "provider failed", directory: { error: "provider failed" }, items: [] }, { now }).status, "Fresh", "recent assembly time plus provider failure must not be Fresh");
assert.equal(build({ updatedAt: "2026-09-09T11:00:00", validation: { failedCount: 3, verifiedCount: 0 }, items: [{ error: "provider failed" }] }, { now }).status, "Unavailable", "all failed Global Market items must be Unavailable");
assert.equal(build({ updatedAt: "2026-09-09T11:00:00", completenessFailure: true, hasUsableData: true }, { now }).status, "Partial", "mixed Asset Hub sources must be Partial");
const unavailable = build({}, { now, requirePrimary: true, hasDecisionEvidence: true });
assert.equal(unavailable.status, "Unavailable", "missing freshness evidence must be Unavailable");
assert.equal(unavailable.confidence.label, "不足", "unavailable freshness must suppress high-confidence conclusions");
assert.notEqual(build({ updatedAt: "2030-01-01T00:00:00" }, { now }).status, "Fresh", "future timestamps must fail closed");
assert.notEqual(build({ updatedAt: "not-a-timestamp" }, { now }).status, "Fresh", "malformed timestamps must fail closed");

const freshnessRoot = { innerHTML: "" };
context.document.getElementById = (id) => id === "shared-freshness-confidence" ? freshnessRoot : null;
context.document.querySelector = () => ({ firstElementChild: null, insertBefore: () => {} });
const update = context.window.updateSharedFreshnessConfidence;
assert.equal(typeof update, "function", "shared freshness update adapter must exist");
update({ category: "us-etf", updatedAt: "2026-09-09T11:00:00" }, { now, page: "us-etf" });
assert.match(freshnessRoot.innerHTML, /Fresh/, "US ETF payload must update shared freshness");
update({ category: "us-stocks", updatedAt: "2026-09-09T10:30:00" }, { now, page: "global-market" });
assert.match(freshnessRoot.innerHTML, /Fresh/, "US market payload must update shared freshness");
update({ category: "futures", updatedAt: "2020-01-01T00:00:00" }, { now, page: "global-market" });
assert.match(freshnessRoot.innerHTML, /Delayed/, "futures payload must drive its own freshness state");
update({ category: "options", updatedAt: "2030-01-01T00:00:00" }, { now, page: "global-market" });
assert.match(freshnessRoot.innerHTML, /Partial/, "options payload must reject future freshness metadata");
update({ category: "bonds", updatedAt: "2026-09-09T11:30:00" }, { now, page: "asset-hub" });
assert.match(freshnessRoot.innerHTML, /Fresh/, "Asset Hub payload must update shared freshness");
update({ updatedAt: "2026-09-09T11:30:00" }, { now, page: "us-watchlist", confidence: 76 });
assert.match(freshnessRoot.innerHTML, /76\/100/, "existing page confidence must be consumed without creating a new score");
update({ updatedAt: "2026-09-09T11:30:00" }, { now, page: "us-stock-search" });
assert.match(freshnessRoot.innerHTML, /不足/, "pages without confidence evidence must remain insufficient");

const root = { innerHTML: "" };
context.document.getElementById = (id) => id === "market-decision-summary" ? root : null;
context.window.renderSharedMarketDecisionSummary({
  decision: "測試",
  summary: "測試",
  freshness: { status: "Fresh", label: "Fresh", detail: "測試" },
  confidence: { label: "有限", detail: "測試" },
  temperature: { value: 50, label: "既有市場風險分數", detail: "測試" },
  strategy: { advice: ["優先選擇趨勢與成交量同步轉強的個股。", "弱勢股反彈不追價。"], next: ["等待確認"] },
  reasons: [], risks: [], leaders: [], laggards: [], evidence: [], invalidation: [], limitations: [],
});
assert.match(root.innerHTML, /策略建議/);
assert.match(root.innerHTML, /優先選擇趨勢與成交量同步轉強/);
assert.match(root.innerHTML, /弱勢股反彈不追價/);
assert.doesNotMatch(root.innerHTML, /可以做|不要做/, "neutral advice must not misclassify positive or avoidance actions");

const pages = fs.readdirSync(ROOT).filter((name) => name.endsWith(".html"));
assert.equal(pages.length, 21, "all Production pages must remain present");
assert(pages.every((name) => /<body[^>]*data-page=/.test(fs.readFileSync(path.join(ROOT, name), "utf8"))), "every Production page must be eligible for shared runtime injection");
assert.match(fs.readFileSync(path.join(ROOT, "js", "main.js"), "utf8"), /window\.renderSharedFreshnessConfidence\(data, \{ page \}\)/, "shared freshness renderer must be invoked for every page route");
const mainSource = fs.readFileSync(path.join(ROOT, "js", "main.js"), "utf8");
const statusEsmSource = fs.readFileSync(path.join(ROOT, "derivatives-status-esm.js"), "utf8");
const statusClassicSource = fs.readFileSync(path.join(ROOT, "derivatives-ui.js"), "utf8");
assert.match(mainSource, /"derivatives-status"/, "derivatives status must be excluded from the generic TWSE loader");
assert.match(statusEsmSource, /fetchJson\("\/api\/derivatives\/v1-status"\)/, "derivatives status must keep its own health request");
assert.match(statusEsmSource, /updateSharedFreshnessConfidence\?\.\(payload, \{ page: "derivatives-status" \}\)/, "derivatives health payload must drive shared freshness");
assert.match(statusClassicSource, /updateSharedFreshnessConfidence\?\.\(payload, \{ page: "derivatives-status" \}\)/, "static derivatives status source must retain the authorized integration");
for (const filename of ["js/page-us.js", "js/page-global-market-options.js", "js/page-global-market-assethub.js", "js/page-tw.js"]) {
  assert.match(fs.readFileSync(path.join(ROOT, filename), "utf8"), /updateSharedFreshnessConfidence/, `${filename} must update shared freshness after async page data resolves`);
}
assert.match(fs.readFileSync(path.join(ROOT, "js", "page-global-market-options.js"), "utf8"), /buildOptionsAiFunctionalModel\(payload\)\.confidenceScore/, "options shared confidence must reuse existing analysis evidence");
assert.match(fs.readFileSync(path.join(ROOT, "js", "page-global-market-assethub.js"), "utf8"), /buildAssetHubFinanceModel\(/, "Asset Hub shared confidence must reuse existing finance evidence");
assert.match(fs.readFileSync(path.join(ROOT, "js", "page-global-market-assethub.js"), "utf8"), /hasUsableData/, "mixed Asset Hub source status must retain usable-data evidence");
const distDerivativesUi = path.join(ROOT, "dist", "cloudflare-static", "derivatives-ui.js");
assert.equal(fs.readFileSync(path.join(ROOT, "derivatives-ui.js"), "utf8"), fs.readFileSync(distDerivativesUi, "utf8"), "Cloudflare static derivatives UI must reproduce its root source exactly");

console.log("DECISION_LAYER_TARGETED_TESTS_OK: false-Fresh closure, static source alignment, freshness validation, page payload adapters, confidence evidence, derivatives domain, strategy semantics, full-site injection");
