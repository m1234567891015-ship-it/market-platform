"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const sharedCalcSource = read("js/shared-calc.js");
const stateSource = read("js/state.js");
const coreSource = read("js/core.js");
const twSource = read("js/page-tw.js");
const usPortfolioSource = read("js/render-shared.js");
const usEtfSource = read("js/page-us.js");
const futuresSource = read("js/page-global-market-futures.js");

const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, Element: function Element() {}, window: {} };
vm.createContext(sandbox);
vm.runInContext(`${stateSource}\n${coreSource}\n${sharedCalcSource}\nthis.__p1c = {
  buildPortfolioTheoryAssessment,
  calculatePeriodReturn,
};`, sandbox, {
  filename: path.join(root, "js", "shared-calc.js"),
});
const p1c = sandbox.__p1c;

const closeSeries = (length, base, trend, amplitude, frequency) => Array.from({ length }, (_, index) => ({
  date: new Date(Date.UTC(2026, 0, 1 + index)).toISOString().slice(0, 10),
  close: base * Math.exp(trend * index + amplitude * Math.sin(index / frequency)),
}));

const fullHistory = closeSeries(61, 100, 0.001, 0.004, 2);
assert(Math.abs(p1c.calculatePeriodReturn(fullHistory, 60) - ((fullHistory[60].close / fullHistory[0].close - 1) * 100)) < 1e-10,
  "60-session return keeps using the 61 available closes");

const shortHistory = [{ close: 100 }, { close: 110 }, { close: 120 }];
assert.strictEqual(p1c.calculatePeriodReturn(shortHistory, 60), 20,
  "short history keeps using the full available range");

const fallbackHistory = Array.from({ length: 30 }, (_, index) => ({ close: index === 0 ? 0 : 100 + index }));
assert.strictEqual(p1c.calculatePeriodReturn(fallbackHistory, 60), null,
  "invalid 60-session start remains unavailable");
assert(Number.isFinite(p1c.calculatePeriodReturn(fallbackHistory, 20)),
  "20-session fallback remains available when its own start is valid");
const positions = [
  { shares: 1, marketValue: 25, stock: { code: "A", name: "A" }, detail: { historyDays: closeSeries(61, 100, 0.001, 0.004, 2) } },
  { shares: 1, marketValue: 25, stock: { code: "B", name: "B" }, detail: { historyDays: fallbackHistory } },
  { shares: 1, marketValue: 25, stock: { code: "C", name: "C" }, detail: { historyDays: shortHistory } },
  { shares: 1, marketValue: 25, stock: { code: "D", name: "D" }, detail: { historyDays: [] } },
];
const assessment = p1c.buildPortfolioTheoryAssessment(positions, { totalValue: 100 });
const fullReturn = p1c.calculatePeriodReturn(fullHistory, 60);
const fallbackReturn = p1c.calculatePeriodReturn(fallbackHistory, 20);
const shortReturn = p1c.calculatePeriodReturn(shortHistory, 60);
const expectedSignal = fullReturn * 0.25 + fallbackReturn * 0.25 + shortReturn * 0.25;
assert(Math.abs(assessment.metrics.historicalReturnSignal - expectedSignal) < 1e-10,
  "weighted signal keeps 60-day preference, 20-day fallback, shorter-history fallback, and zero for missing data");
assert(Number.isFinite(assessment.metrics.historicalReturnSignal));
assert.strictEqual(assessment.metrics.expectedReturn60, assessment.metrics.historicalReturnSignal,
  "deprecated expectedReturn60 alias equals the canonical historical signal");
assert(assessment.details.some((line) => line.includes("歷史報酬動能")));
assert(assessment.details.some((line) => line.includes("持倉優先 60 日、缺值回退 20 日")));
assert(!assessment.details.some((line) => /expected|預期|預測/.test(line)));

for (const [name, source] of [["TW portfolio", twSource], ["US portfolio", usPortfolioSource]]) {
  assert(!/sharpeLike|類\s*Sharpe|Sharpe-like/i.test(source), `${name} no longer names the current-move ratio Sharpe`);
  assert(/returnToAverageMoveRatio\s*=\s*avgMove\s*\?\s*netReturn\s*\/\s*avgMove\s*:\s*null/.test(source),
    `${name} retains the existing ratio formula under its truthful name`);
  assert(source.includes("報酬／平均日變動比") && source.includes("持有期間淨報酬 ÷ 當前平均絕對單日漲跌"),
    `${name} explains the formula in user-facing text`);
}

assert(/annualizedReturnVolatilityRatio:\s*Number\.isFinite\(average\)\s*&&\s*dailyStd\s*\?\s*\(average\s*\/\s*dailyStd\)\s*\*\s*Math\.sqrt\(252\)\s*:\s*null/.test(usEtfSource),
  "US ETF annualized mean-return/volatility formula remains unchanged");
assert(!/stats\.sharpe|signals\.sharpe|\bsharpe\s*:/.test(usEtfSource),
  "US ETF active result and consumers no longer use a sharpe field");
assert(usEtfSource.includes("年化報酬／波動比") && usEtfSource.includes("未扣除無風險利率"),
  "US ETF text labels the retained metric and its risk-free treatment truthfully");
assert(!/Sharpe/i.test(futuresSource), "portfolio feature description no longer advertises Sharpe");

assert(/name:\s*"riskAdjustedReturnScore"/.test(sharedCalcSource));
assert(/notSharpeBecause:/.test(sharedCalcSource));
assert(/summary\.sharpe, undefined/.test(read("regression/test_q3_risk_metric.js")),
  "existing backtest regression keeps the custom score distinct from Sharpe");

console.log("P1C_SHARPE_RETURN_SEMANTICS_OK: retained formulas are truthful, historical fallback and alias are preserved");
