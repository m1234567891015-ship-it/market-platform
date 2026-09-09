"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const context = {
  window: {},
  document: { getElementById: () => null },
  URLSearchParams,
  String,
  Number,
  Array,
  Boolean,
  Object,
  console,
  escapeHtml: (value) => String(value),
  safeUrl: (value) => String(value),
};
vm.runInNewContext(fs.readFileSync(path.join(ROOT, "js", "page-home.js"), "utf8"), context, { filename: "page-home.js" });

const adapter = context.window.buildSelectionFunnelAdapter;
assert.equal(typeof adapter, "function", "Phase B adapter must exist");
const decision = { summary: "既有市場證據", freshness: { status: "Fresh" }, confidence: { label: "有限" }, temperature: { value: 42 } };
const payload = {
  sectorFundFlow: {
    date: "2026-09-09",
    inflows: [
      { name: "電子", netAmountValue: 200, netAmount: "+200", pennyStocks: [
        { code: "1001", name: "甲", score: 88, pct: "+2%", close: "20" },
        { code: "1002", name: "乙", score: 88, pct: "+1%", close: "21" },
      ] },
      { name: "金融", netAmountValue: 100, netAmount: "+100", pennyStocks: [{ code: "2001", name: "丙", score: 70 }] },
    ],
  },
};
const first = adapter(payload, decision);
const second = adapter(payload, decision);
assert.deepEqual(first.sectors.map((item) => item.name), ["電子", "金融"], "existing sector ordering must be preserved");
assert.equal(first.sectors[0].score, 200, "existing sector score must not be recomputed");
assert.deepEqual(first.candidates.map((item) => item.symbol), ["1001", "1002"], "existing candidate and tie ordering must be preserved");
assert.deepEqual(first.candidates.map((item) => item.symbol), second.candidates.map((item) => item.symbol), "same input must produce the same TOP10 order");
assert(first.candidates.length <= 10, "TOP10 must contain at most ten candidates");
assert.equal(first.candidates[0].market, "TWSE", "market identity must be preserved");
assert.equal(first.candidates[0].sector, "電子", "sector identity must be preserved");
assert.equal(first.candidates[0].confidence, null, "missing confidence must not be fabricated");
assert.equal(first.candidates[0].risk, null, "risk evidence must not be rescored");
context.window.__selectionFunnelState.sectorName = "金融";
assert.deepEqual(adapter(payload, decision).candidates.map((item) => item.symbol), ["2001"], "selected sector must constrain the candidate universe");
assert.equal(adapter(payload, decision).sectors.every((item) => item.market === "TWSE"), true, "selected market must constrain downstream sectors");
assert.equal(adapter({ sectorFundFlow: { inflows: [] } }, decision).available, false, "missing required ranking capability must fail closed");
const source = fs.readFileSync(path.join(ROOT, "js", "page-home.js"), "utf8");
assert.doesNotMatch(source, /SelectionEngineV2|UniversalRankingEngine|CompositeAIScore|MetaRanker|CrossMarketRanker|RankingOrchestrator/);
assert.doesNotMatch(source, /scenario|Bull\/Base\/Bear|Support\/Resistance/i, "Phase C logic must not be introduced");
console.log("SELECTION_FUNNEL_TARGETED_TESTS_OK: existing ordering and scores preserved; TOP10 deterministic; missing capability fails closed");
