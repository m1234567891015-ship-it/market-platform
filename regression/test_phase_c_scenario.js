"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const ROOT = path.resolve(__dirname, "..");
const context = {
  console,
  Math,
  Number,
  String,
  Array,
  Set,
  RegExp,
  window: { location: { pathname: "/tw-stock-search.html" } },
  document: {
    querySelectorAll: () => [],
    getElementById: () => null,
    querySelector: () => null,
    createElement: () => ({}),
  },
  escapeHtml: (value) => String(value),
};
vm.runInNewContext(fs.readFileSync(path.join(ROOT, "js", "render-shared.js"), "utf8"), context, { filename: "render-shared.js" });

const build = context.window.buildStockScenarioContract;
const render = context.window.renderStockScenarioContract;
assert.equal(typeof build, "function", "Phase C scenario adapter must exist");
assert.equal(typeof render, "function", "Phase C scenario renderer must exist");

const technicalTheory = {
  evidenceCount: 18,
  backtestLearning: {
    validation: { status: "healthy", label: "模型健康" },
    forecast: {},
  },
};
const summary = {
  label: "偏多風向",
  score: 64,
  confidence: "中",
  confirmations: ["均線既有確認", "價量既有確認"],
  risks: ["價格指標與量能方向背離"],
  forecast: {
    confidence: "中",
    trendLabel: "偏多延續",
    primaryScenario: { days: 20, bullish: 55, neutral: 30, bearish: 15 },
    primaryTarget: { days: 20, lower: 95, median: 105, upper: 115 },
    support: 90,
    resistance: 120,
  },
};
const first = build({ code: "2330", name: "測試股" }, technicalTheory, summary);
const second = build({ code: "2330", name: "測試股" }, technicalTheory, summary);
assert.deepEqual(first, second, "same authoritative inputs must produce deterministic contract");
assert.equal(first.score, 64, "score must reuse the existing technical summary score");
assert.equal(first.confidence, "中", "confidence must reuse the existing technical summary confidence");
assert.equal(first.support, 90, "support must reuse the existing forecast support");
assert.equal(first.resistance, 120, "resistance must reuse the existing forecast resistance");
assert.equal(first.cases.map((item) => item.probability).join(","), "55,30,15", "probabilities must be exact reuse");
assert.equal(first.riskScore, null, "risk score must remain unavailable without an authoritative risk score");
assert.match(first.invalidation.join(" "), /90\.00|120\.00/, "invalidation must link to existing levels");

const missingLevels = build({ code: "2330" }, { evidenceCount: 4, backtestLearning: {} }, {
  label: "中性整理",
  score: 50,
  confidence: "低",
  confirmations: ["既有技術證據"],
  risks: [],
  forecast: { primaryScenario: { bullish: 30, neutral: 40, bearish: 30 }, support: null, resistance: null },
});
assert.equal(missingLevels.support, null, "missing support must remain null");
assert.equal(missingLevels.resistance, null, "missing resistance must remain null");

const unavailable = build({}, { evidenceCount: 0, backtestLearning: {} }, { forecast: {} });
assert.equal(unavailable.available, false, "missing evidence must fail closed");
assert.equal(unavailable.decision, "目前無法產生情境", "missing evidence must not fabricate a decision");
assert.equal(unavailable.score, null, "missing evidence must not fabricate a score");
assert.equal(unavailable.riskScore, null, "missing evidence must not fabricate a risk score");
assert.match(unavailable.invalidation.join(" "), /資料不足|無法/, "missing evidence must fail closed for invalidation");
assert.match(render(first), /Decision scenario/);
assert.match(render(first), /Bull Case/);
assert.match(render(first), /Base Case/);
assert.match(render(first), /Bear Case/);
assert.match(render(first), /Support/);
assert.match(render(first), /Resistance/);
assert.match(render(first), /Risk \/ Counter-evidence/);
assert.match(render(first), /Invalidation condition/);
assert.match(render(unavailable), /目前無法產生情境/);
assert.match(render(missingLevels), /支撐資料不足/);
assert.match(render(missingLevels), /壓力資料不足/);

const riskEvidence = build({ code: "2330" }, {
  evidenceCount: 12,
  backtestLearning: { validation: { status: "recalibrate", label: "需重新校準" } },
}, {
  label: "震盪整理",
  score: 51,
  confidence: "低",
  confirmations: ["既有技術證據"],
  risks: ["ATR 7.00%，波動偏高", "回測模型需重新校準參數"],
  forecast: { primaryScenario: { bullish: 25, neutral: 40, bearish: 35 }, support: 90, resistance: 120 },
});
assert.equal(riskEvidence.riskScore, null, "qualitative risk evidence must not become a fabricated numeric score");
assert.match(riskEvidence.riskReasons.join(" "), /ATR 7\.00%/);
assert.match(riskEvidence.riskReasons.join(" "), /重新校準/);
assert.match(riskEvidence.invalidation.join(" "), /重新評估/);

const stockDetailSource = fs.readFileSync(path.join(ROOT, "js", "stock-detail.js"), "utf8");
assert.match(stockDetailSource, /buildStockScenarioContract/);
assert.match(stockDetailSource, /renderStockScenarioContract/);
assert.doesNotMatch(stockDetailSource, /function\s+buildBacktestTrendForecast/);

const adapterSource = fs.readFileSync(path.join(ROOT, "js", "render-shared.js"), "utf8");
assert.doesNotMatch(adapterSource, /technicalSma|calculateBacktest|calculateSupportResistance/);

console.log("PHASE_C_SCENARIO_TARGETED_TESTS_OK: deterministic adapter, exact evidence reuse, fail-closed states, three conditional cases, levels, risk, invalidation, presentation-only integration");
