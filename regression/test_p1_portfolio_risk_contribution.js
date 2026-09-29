"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const stateSource = fs.readFileSync(path.join(root, "js", "state.js"), "utf8");
const calcSource = fs.readFileSync(path.join(root, "js", "shared-calc.js"), "utf8");
const sandbox = {
  console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {},
  parseAnalysisNumber(value) {
    if (value === null || value === undefined || value === "" || value === "--") return null;
    const parsed = Number(String(value).replace(/,/g, "").replace("%", "").trim());
    return Number.isFinite(parsed) ? parsed : null;
  },
};
vm.createContext(sandbox);
vm.runInContext(`${stateSource}\n${calcSource}\nthis.__risk = buildBacktestLearningModel.calculatePortfolioEulerRisk; this.__theory = buildPortfolioTheoryAssessment;`, sandbox);
const calculate = sandbox.__risk;
const theory = sandbox.__theory;
const start = Date.UTC(2025, 0, 1);
const dateAt = (index) => new Date(start + index * 86400000).toISOString().slice(0, 10);
const historyFromReturns = (returns, offset = 0, base = 100) => {
  const historyDays = [{ date: dateAt(offset), close: base }];
  for (let index = 0; index < returns.length; index += 1) {
    historyDays.push({ date: dateAt(offset + index + 1), close: historyDays.at(-1).close * (1 + returns[index]) });
  }
  return { historyDays };
};
const position = (returns, marketValue, options = {}) => ({
  shares: 1,
  marketValue,
  stock: { code: options.code || "T", name: options.name || "Test" },
  detail: options.detail || historyFromReturns(returns, options.offset || 0),
});
const close = (actual, expected, tolerance = 1e-10) => assert(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);
const x = Array.from({ length: 60 }, (_, index) => (index % 4 < 2 ? 0.01 : -0.01));
const y = Array.from({ length: 60 }, (_, index) => ([1, -1, 1, -1][index % 4] * 0.02));

// A: perfectly correlated returns retain the exact volatility-weighted Euler shares.
const perfect = calculate([position(x, 50), position(x.map((value) => value * 2), 50)], 100);
assert.strictEqual(perfect.supported, true);
close(perfect.contributionPct[0], 1 / 3);
close(perfect.contributionPct[1], 2 / 3);
close(perfect.covariance[0][1], perfect.covariance[0][0] * 2);

// B/F: orthogonal, zero-mean returns give a deterministic known sample covariance matrix.
const lowCorrelation = calculate([position(x, 50), position(y, 50)], 100);
assert.strictEqual(lowCorrelation.supported, true);
const expectedVarA = (60 / 59) * 0.01 ** 2;
const expectedVarB = (60 / 59) * 0.02 ** 2;
close(lowCorrelation.covariance[0][0], expectedVarA);
close(lowCorrelation.covariance[1][1], expectedVarB);
close(lowCorrelation.covariance[0][1], 0);
close(lowCorrelation.portfolioVariance, (expectedVarA + expectedVarB) / 4);
assert(Math.abs(lowCorrelation.contributionPct[0] - 1 / 3) > 0.1, "covariance-aware result collapsed to weight × standalone volatility");

// C: a negatively correlated constituent can have a valid negative component contribution.
const negative = calculate([position(x, 50), position(x.map((value) => value * -0.5), 50)], 100);
assert.strictEqual(negative.supported, true);
assert(negative.componentRisk[1] < 0);
close(negative.contributionPct[0], 2);
close(negative.contributionPct[1], -1);

// D: one asset has its own sample volatility and 100% contribution.
const single = calculate([position(x, 100)], 100);
assert.strictEqual(single.supported, true);
close(single.dailyVolatility, Math.sqrt(expectedVarA));
close(single.componentRisk[0], single.dailyVolatility);
close(single.contributionPct[0], 1);

// E: unequal market-value weights flow directly into Euler component risk.
const unequal = calculate([position(x, 25), position(x.map((value) => value * 2), 75)], 100);
assert.strictEqual(unequal.supported, true);
close(unequal.contributionPct[0], 1 / 7);
close(unequal.contributionPct[1], 6 / 7);

// G/H: Euler component risk reconciles to portfolio volatility and percentages to one.
close(negative.componentRisk.reduce((sum, value) => sum + value, 0), negative.dailyVolatility);
close(negative.contributionPct.reduce((sum, value) => sum + value, 0), 1);
close(lowCorrelation.componentRisk.reduce((sum, value) => sum + value, 0), lowCorrelation.dailyVolatility);
close(lowCorrelation.contributionPct.reduce((sum, value) => sum + value, 0), 1);

// I: synchronized samples below the existing P1-A 60-return threshold fail closed.
const insufficient = calculate([position(Array(59).fill(0.01), 100)], 100);
assert.strictEqual(insufficient.supported, false);
assert.strictEqual(insufficient.reason, "insufficient_history");
assert.strictEqual(insufficient.sampleCount, 59);
assert.strictEqual(insufficient.portfolioVariance, null);

// J: date alignment uses actual dates; the delayed constituent contributes no fabricated early returns.
const dateReturns = (offset, count) => Array.from({ length: count }, (_, index) => {
  const globalEndDate = offset + index + 1;
  return globalEndDate % 2 ? 0.01 : -0.01;
});
const shifted = calculate([
  position(dateReturns(0, 64), 50),
  position(dateReturns(3, 61), 50, { offset: 3 }),
], 100);
assert.strictEqual(shifted.supported, true);
assert.strictEqual(shifted.sampleCount, 61);
assert.strictEqual(shifted.dates[0], dateAt(4));
assert.strictEqual(shifted.dates.at(-1), dateAt(64));
const shuffledDetail = { historyDays: [...position(x, 100).detail.historyDays].reverse() };
const shuffled = calculate([position([], 100, { detail: shuffledDetail })], 100);
assert.deepStrictEqual(Array.from(shuffled.dates), Array.from(single.dates));
assert.deepStrictEqual(Array.from(shuffled.contributionPct), Array.from(single.contributionPct));

// K: deterministic zero volatility is unavailable and never divides by zero.
const degenerate = calculate([position(Array(60).fill(0), 100)], 100);
assert.strictEqual(degenerate.supported, false);
assert.strictEqual(degenerate.reason, "zero_volatility");
assert.strictEqual(degenerate.dailyVolatility, null);
assert.deepStrictEqual(Array.from(degenerate.contributionPct), []);

// Missing constituent history fails closed, without reweighting the known holding.
const missing = calculate([position(x, 50), position([], 50, { detail: null })], 100);
assert.strictEqual(missing.supported, false);
assert.strictEqual(missing.reason, "insufficient_history");

// L: both user-facing regional paths use the shared assessment; no covariance-free attribution remains.
for (const file of ["js/page-tw.js", "js/render-shared.js"]) {
  const source = fs.readFileSync(path.join(root, file), "utf8");
  assert(/buildPortfolioTheoryAssessment\(active, totals\)/.test(source), `${file} no longer uses the shared risk assessment`);
  assert(!/riskBase\s*=/.test(source), `${file} contains a covariance-free portfolio risk base`);
}
assert(!/riskBase\s*=/.test(calcSource), "shared source retains covariance-free attribution");
const theoryResult = theory([position(x, 50, { code: "AAA" }), position(x.map((value) => value * 2), 50, { code: "BBB" })], { totalValue: 100 });
assert.strictEqual(theoryResult.metrics.topRiskContributor.code, "BBB");
close(theoryResult.metrics.topRiskContributor.contribution, 200 / 3);
assert.strictEqual(theoryResult.metrics.riskContributionStatus.supported, true);
if (process.argv.includes("--production")) {
  for (const file of ["common-runtime.min.js", "route-bundle.min.js", "market-pulse-esm.min.js"]) {
    const source = fs.readFileSync(path.join(root, file), "utf8");
    assert(!/riskBase\s*=/.test(source), `${file} retains covariance-free portfolio risk attribution`);
  }
}

console.log("P1B_RISK_CONTRIBUTION_OK: 12 cases; convention=sample_covariance; minimum=60; aligned_samples=61");
