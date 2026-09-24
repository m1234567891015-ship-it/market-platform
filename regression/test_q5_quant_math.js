"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const nearlyEqual = (actual, expected, tolerance = 1e-10) => {
  assert(Number.isFinite(actual), `expected a finite number, got ${actual}`);
  assert(Math.abs(actual - expected) <= tolerance, `expected ${expected}, got ${actual}`);
};

const stateSource = fs.readFileSync(path.join(__dirname, "..", "js", "state.js"), "utf8");
const calcSource = fs.readFileSync(path.join(__dirname, "..", "js", "shared-calc.js"), "utf8");
const calcSandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {} };
vm.createContext(calcSandbox);
vm.runInContext(`${stateSource}\n${calcSource}\nthis.__q5 = {
  calculatePortfolioReturns,
  calculatePeriodReturn,
  calculateMaxDrawdownPct,
  calculateBacktestWinRate,
  calculateBacktestAverageReturn,
  calculateBacktestProfitFactor,
  buildBacktestLearningModel,
};`, calcSandbox, { filename: path.join(__dirname, "..", "js", "shared-calc.js") });

const quant = calcSandbox.__q5;
const prices = [100, 110, 99].map((close, index) => ({
  date: `2026-01-0${index + 1}`,
  close,
}));
assert.deepStrictEqual(Array.from(quant.calculatePortfolioReturns(prices)), [0.1, -0.1]);
const cumulativeReturn = quant.calculatePortfolioReturns(prices).reduce((equity, value) => equity * (1 + value), 1) - 1;
nearlyEqual(cumulativeReturn, -0.01);
nearlyEqual(quant.calculatePeriodReturn(prices, 2), -1);
nearlyEqual(quant.calculateMaxDrawdownPct([10, -20, 10]), -20);
assert.strictEqual(quant.calculateMaxDrawdownPct([]), 0);

const returns = [10, -5, 0, 15, -10];
nearlyEqual(quant.calculateBacktestWinRate(returns), 0.4);
nearlyEqual(quant.calculateBacktestAverageReturn(returns), 2);
nearlyEqual(quant.calculateBacktestProfitFactor(returns), 25 / 15);
assert.strictEqual(quant.calculateBacktestProfitFactor([1, 2]), null, "zero-loss profit factor remains unbounded");
assert.strictEqual(quant.calculateBacktestProfitFactor([-1, -2]), 0, "zero-win profit factor is zero");

const segment = quant.buildBacktestLearningModel.summarizeBacktestObservations(
  returns.map((value, index) => ({ index, value })),
);
assert.strictEqual(segment.samples, 5);
nearlyEqual(segment.winRate, 0.4);
nearlyEqual(1 - segment.winRate, 0.6);
nearlyEqual(segment.averageReturn, 2);
nearlyEqual(segment.maxDrawdown, -10);
assert(Number.isFinite(segment.riskAdjustedReturnScore));
assert.strictEqual(quant.buildBacktestLearningModel.summarizeBacktestObservations([]).profitFactor, null);
const riskScore = quant.buildBacktestLearningModel.calculateRiskAdjustedReturnScore;
assert.strictEqual(riskScore([]), null);
assert.strictEqual(riskScore([1]), null);
assert.strictEqual(riskScore([1, 1, 1]), null);
assert(Number.isFinite(riskScore([-1, -2, -3])));

const observations = Array.from({ length: 10 }, (_, index) => ({ index, value: index - 4 }));
assert.strictEqual(quant.buildBacktestLearningModel.countEffectiveBacktestSamples(observations, 3), 4);
const split = quant.buildBacktestLearningModel.splitBacktestObservations(observations);
assert.strictEqual(split.train.length, 6);
assert.strictEqual(split.validation.length, 2);
assert.strictEqual(split.test.length, 2);
assert(split.train.at(-1).index < split.validation[0].index);
assert(split.validation.at(-1).index < split.test[0].index);

const shortHistory = [{ close: 100 }, { close: 101 }];
const insufficient = quant.buildBacktestLearningModel(shortHistory, 240);
assert.strictEqual(insufficient.signals.length, 0);
assert.strictEqual(insufficient.performance, null);
assert(insufficient.qualityChecks.length > 0);

const strategySource = fs.readFileSync(path.join(__dirname, "..", "js", "page-global-market-assethub.js"), "utf8");
const strategyStart = strategySource.indexOf("initDerivativesAnalyticsPage.strategyEngine = (() => {");
const strategyEndMarker = "\n})();";
const strategyEnd = strategySource.indexOf(strategyEndMarker, strategyStart);
assert(strategyStart >= 0 && strategyEnd > strategyStart, "strategy engine assignment must be present");
const strategySandbox = { initDerivativesAnalyticsPage: {}, Date, Math, Number, Array, Object, JSON };
vm.runInNewContext(strategySource.slice(strategyStart, strategyEnd + strategyEndMarker.length), strategySandbox, {
  filename: path.join(__dirname, "..", "js", "page-global-market-assethub.js"),
});
const engine = strategySandbox.initDerivativesAnalyticsPage.strategyEngine;

const longCall = [{ side: "BUY", optionType: "call", strike: 100, premium: 5, quantity: 1, contractMultiplier: 1, commission: 0, exchangeFee: 0, slippage: 0 }];
const shortCall = [{ side: "SELL", optionType: "call", strike: 100, premium: 5, quantity: 1, contractMultiplier: 1, commission: 0, exchangeFee: 0, slippage: 0 }];
const longCallMetrics = engine.metrics(longCall);
const shortCallMetrics = engine.metrics(shortCall);
nearlyEqual(engine.payoff(longCall, 110), 5);
nearlyEqual(engine.payoff(shortCall, 110), -5);
nearlyEqual(longCallMetrics.netPremium, 5);
nearlyEqual(shortCallMetrics.netPremium, -5);
nearlyEqual(longCallMetrics.breakEven[0], 105);
nearlyEqual(shortCallMetrics.breakEven[0], 105);
assert.strictEqual(longCallMetrics.maxProfit, null, "long call upside is unlimited");
nearlyEqual(longCallMetrics.maxLoss, -5);
nearlyEqual(shortCallMetrics.maxProfit, 5);
assert.strictEqual(shortCallMetrics.maxLoss, null, "short call loss is theoretically unlimited");

const frictionalLegs = [{
  side: "BUY", optionType: "call", strike: 100, premium: 5, quantity: 2,
  contractMultiplier: 50, commission: 1, exchangeFee: 2, slippage: 0.1,
}];
nearlyEqual(engine.payoff(frictionalLegs, 110), 484);
assert(Number.isFinite(engine.payoff(frictionalLegs, 100)));

const quoteTime = new Date().toISOString();
const market = { spot: 100, direction: "Bullish", futuresPct: 0.1, volumePcr: 1, maxPainGapPct: 0 };
const liquid = engine.liquidityScore({ bid: 9, ask: 11, volume: 10, openInterest: 100, quoteTime }, market);
const zeroLiquidity = engine.liquidityScore({ bid: 9, ask: 11, volume: 0, openInterest: 0, quoteTime }, market);
const staleLiquidity = engine.liquidityScore({ bid: 9, ask: 11, volume: 10, openInterest: 100, quoteTime: "2020-01-01T00:00:00.000Z" }, market);
assert(liquid.score > zeroLiquidity.score);
assert.strictEqual(zeroLiquidity.volumeScore, 0);
assert.strictEqual(zeroLiquidity.openInterestScore, 0);
assert.strictEqual(staleLiquidity.freshnessScore, 0);
assert.strictEqual(engine.executionPrice({ bid: 9, ask: 11, last: 10 }, "BUY").source, "ask");
assert.strictEqual(engine.executionPrice({ bid: 9, ask: 11, last: 10 }, "SELL").source, "bid");
assert.strictEqual(engine.executionPrice({ bid: 12, ask: 10, last: 11 }, "BUY").source, "last");

console.log("Q5_QUANT_MATH_OK: deterministic returns, risk metrics, backtest splits, options payoff, costs, and liquidity");
