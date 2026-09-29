"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const stateSource = fs.readFileSync(path.join(root, "js", "state.js"), "utf8");
const calcSource = fs.readFileSync(path.join(root, "js", "shared-calc.js"), "utf8");
const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {} };
vm.createContext(sandbox);
vm.runInContext(`${stateSource}\n${calcSource}\nthis.__calculate = buildBacktestLearningModel.calculateHistoricalPortfolioVar;`, sandbox);
const calculate = sandbox.__calculate;
const start = Date.UTC(2025, 0, 1);
const dateAt = (index, offset = 0) => new Date(start + (index + offset) * 86400000).toISOString().slice(0, 10);
const historyFromReturns = (returns, offset = 0, base = 100) => {
  const historyDays = [{ date: dateAt(0, offset), close: base }];
  for (let index = 0; index < returns.length; index += 1) {
    historyDays.push({ date: dateAt(index + 1, offset), close: historyDays.at(-1).close * (1 + returns[index]) });
  }
  return { historyDays };
};
const position = (detail, marketValue, shares = 1) => ({ detail, marketValue, shares });
const baseReturns = Array(60).fill(0.01);
baseReturns[0] = -0.1;
baseReturns[1] = -0.08;
baseReturns[2] = -0.06;
const primary = position(historyFromReturns(baseReturns), 100);
const result = calculate([primary], 100);

// A: known nearest-rank 5% quantile and same-distribution ES.
assert.strictEqual(result.supported, true);
assert.strictEqual(result.method, "historical_simulation_nearest_rank");
assert.strictEqual(result.sampleCount, 60);
assert(Math.abs(result.varPct - 0.06) < 1e-10);
assert(Math.abs(result.esPct - 0.08) < 1e-10);
assert(Math.abs(result.varAmount - 6) < 1e-8);
assert(Math.abs(result.esAmount - 8) < 1e-8);
// B: fewer than the documented 60 synchronized daily returns fails closed.
const insufficient = calculate([position(historyFromReturns(Array(59).fill(0.01)), 100)], 100);
assert.strictEqual(insufficient.supported, false);
assert.strictEqual(insufficient.status, "unavailable");
assert.strictEqual(insufficient.reason, "insufficient_history");
assert.strictEqual(insufficient.sampleCount, 59);
assert.strictEqual(insufficient.varAmount, null);
// C: missing one active constituent's history never substitutes zero or renormalizes.
const missing = calculate([primary, position(null, 50)], 150);
assert.strictEqual(missing.supported, false);
assert.strictEqual(missing.varPct, null);
// D: portfolio returns use current market-value weights (25% / 75%).
const rising = position(historyFromReturns(Array(60).fill(0.1)), 25);
const falling = position(historyFromReturns(Array(60).fill(-0.1)), 75);
const weighted = calculate([rising, falling], 100);
assert.strictEqual(weighted.supported, true);
assert(weighted.portfolioReturns.every((value) => Math.abs(value + 0.05) < 1e-10));
assert(Math.abs(weighted.varPct - 0.05) < 1e-10);
// E: constituent calendars overlap by actual end date, despite different start dates.
const offsetA = position(historyFromReturns(Array(65).fill(0.01), 0), 50);
const offsetB = position(historyFromReturns(Array(65).fill(0.01), 2), 50);
const joined = calculate([offsetA, offsetB], 100);
assert.strictEqual(joined.supported, true);
assert.strictEqual(joined.sampleCount, 63);
assert(joined.portfolioReturns.every((value) => Math.abs(value - 0.01) < 1e-10));
// F: unsorted input is normalized chronologically; no future return is shifted backward.
const shuffled = position({ historyDays: [...primary.detail.historyDays].reverse() }, 100);
assert.deepStrictEqual(Array.from(calculate([shuffled], 100).portfolioReturns), Array.from(result.portfolioReturns));
const extended = position(historyFromReturns([...baseReturns, -0.5]), 100);
const extendedResult = calculate([extended], 100);
assert.strictEqual(extendedResult.portfolioReturns.length, 61);
assert(Math.abs(extendedResult.portfolioReturns[59] - 0.01) < 1e-10);
assert(Math.abs(extendedResult.portfolioReturns[60] + 0.5) < 1e-10);
// G: multiplying portfolio value scales loss amounts but leaves rates unchanged.
const scaled = calculate([position(primary.detail, 200)], 200);
assert(Math.abs(scaled.varPct - result.varPct) < 1e-12);
assert(Math.abs(scaled.varAmount - result.varAmount * 2) < 1e-8);
// H: output is deterministic for identical inputs.
assert.strictEqual(JSON.stringify(calculate([primary], 100)), JSON.stringify(calculate([primary], 100)));
// I: VaR and ES use positive loss amounts, floored at zero for non-loss tails.
const gains = calculate([position(historyFromReturns(Array(60).fill(0.01)), 100)], 100);
assert.strictEqual(gains.varPct, 0);
assert.strictEqual(gains.esPct, 0);
// J: ES averages all empirical observations at or below the reported VaR cutoff.
assert(Math.abs(result.esPct - 0.08) < 1e-10);
// K: flat returns remain supported and report zero losses.
const flat = calculate([position(historyFromReturns(Array(60).fill(0)), 100)], 100);
assert.strictEqual(flat.supported, true);
assert.strictEqual(flat.varPct, 0);
assert.strictEqual(flat.esPct, 0);
// L: the TW and US source callers no longer contain the volatility-multiplier heuristic.
for (const file of ["js/page-tw.js", "js/render-shared.js"]) {
  const source = fs.readFileSync(path.join(root, file), "utf8");
  assert(!/avgMove\s*\/\s*100\s*\)\s*\*\s*1\.65/.test(source), `${file} retains the former VaR heuristic`);
  assert(!/以目前自選(?:股|標的)日波動估算 95% 單日 VaR/.test(source), `${file} retains the unsupported VaR claim`);
}
if (process.argv.includes("--production")) {
  const artifacts = ["common-runtime.min.js", "route-bundle.min.js"];
  for (const file of artifacts) {
    const source = fs.readFileSync(path.join(root, file), "utf8");
    assert(!/avgMove\s*\/\s*100\s*\)\s*\*\s*1\.65/.test(source), `${file} retains the former VaR heuristic`);
    assert(!/以目前自選(?:股|標的)日波動估算 95% 單日 VaR/.test(source), `${file} retains the unsupported VaR claim`);
  }
}

console.log(`P1A_HISTORICAL_VAR_OK: 12 checks; minimum=${result.minimumSampleCount}, samples=${result.sampleCount}, VaR=${result.varPct}, ES=${result.esPct}`);
