"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const stateSource = fs.readFileSync(path.join(__dirname, "..", "js", "state.js"), "utf8");
const calcSource = fs.readFileSync(path.join(__dirname, "..", "js", "shared-calc.js"), "utf8");
const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {} };
vm.createContext(sandbox);
vm.runInContext(`${stateSource}\n${calcSource}\nthis.__p0b = { buildBacktestLearningModel };`, sandbox, {
  filename: path.join(__dirname, "..", "js", "shared-calc.js"),
});

const backtest = sandbox.__p0b.buildBacktestLearningModel;
const calculateCost = backtest.calculateAssetTransactionCost;
const syntheticSpec = (multiplier, tickSize = 0.5, transactionTaxRate = 0, currency = "TWD") => ({
  symbol: "SYNTH",
  market: "TEST",
  multiplier,
  tickSize,
  transactionTaxRate,
  currency,
  source: "deterministic-test-fixture",
});
const friction = {
  brokerCommissionPerContract: 0,
  slippageTicks: 0,
};
const assertNear = (actual, expected, message) => assert(Math.abs(actual - expected) < 1e-9, message || `${actual} should be near ${expected}`);

function futuresTrade(overrides = {}) {
  return calculateCost({
    assetClass: "FUTURES",
    contractSpec: syntheticSpec(50),
    entryPrice: 100,
    exitPrice: 110,
    contracts: 1,
    ...friction,
    ...overrides,
  });
}

// T1: symbol/spec -> backtest builder -> execution calculator keeps multiplier 50.
const history = Array.from({ length: 720 }, (_, index) => {
  const close = 100 + (index * 0.08) + (Math.sin(index / 9) * 2.5);
  const previous = index ? 100 + ((index - 1) * 0.08) + (Math.sin((index - 1) / 9) * 2.5) : close;
  return {
    date: `2026-${String(Math.floor(index / 30) + 1).padStart(2, "0")}-${String((index % 30) + 1).padStart(2, "0")}`,
    open: close * 0.995,
    high: Math.max(close, previous) * 1.01,
    low: Math.min(close, previous) * 0.99,
    close,
    volume: 100000 + ((index % 11) * 1000),
  };
});
const originalCostCalculator = backtest.calculateAssetTransactionCost;
const multipliersSeenByCalculator = [];
backtest.calculateAssetTransactionCost = (request) => {
  if (request.assetClass === "FUTURES") multipliersSeenByCalculator.push(request.multiplier);
  return originalCostCalculator(request);
};
const model50 = backtest(history, 20, {
  assetClass: "FUTURES",
  instrumentSymbol: "SYNTH",
  contractSpec: syntheticSpec(50),
  brokerCommissionPerContract: 2,
  slippageTicks: 1,
});
backtest.calculateAssetTransactionCost = originalCostCalculator;
assert.strictEqual(model50.costModel.multiplier, 50);
assert.strictEqual(model50.costModel.referenceBreakdown.multiplier, 50);
assert(multipliersSeenByCalculator.length > 1, "reference and trade execution costs must both be calculated");
assert(multipliersSeenByCalculator.every((multiplier) => multiplier === 50), "no execution-cost call may overwrite the multiplier");
const persistedFuturesObservation = model50.signals.flatMap((signal) => signal.observations || []).find((observation) => observation.multiplier === 50);
assert(persistedFuturesObservation, "final futures observations must preserve multiplier and cost/P&L fields");
assert.strictEqual(persistedFuturesObservation.netPnl, persistedFuturesObservation.grossPnl - persistedFuturesObservation.totalCost);
model50.signals.forEach((signal) => assertNear(signal.totalNetPnl, signal.totalGrossPnl - signal.totalCost, "aggregate net P&L must equal gross less costs"));

// T2: multiplier scales currency P&L while price-return inputs remain fixed.
const pnlMultiplier1 = futuresTrade({ contractSpec: syntheticSpec(1), multiplier: 1, entryPrice: 100, exitPrice: 101, contracts: 2 });
const pnlMultiplier50 = futuresTrade({ contractSpec: syntheticSpec(50), multiplier: 50, entryPrice: 100, exitPrice: 101, contracts: 2 });
assert.strictEqual(pnlMultiplier1.grossPnl, 2);
assert.strictEqual(pnlMultiplier50.grossPnl, 100);
assert.strictEqual(pnlMultiplier50.netPnl, pnlMultiplier50.grossPnl - pnlMultiplier50.totalCost);

// T3: commission is a per-contract, per-side input and is charged on entry and exit.
const commissionTrade = futuresTrade({ brokerCommissionPerContract: 1 });
assert.strictEqual(commissionTrade.commissionCost, 2);
assert(commissionTrade.netPnl < commissionTrade.grossPnl);

// T4: slippage ticks convert through tick size, multiplier, contracts, and both sides.
const slippageTrade = futuresTrade({ contracts: 2, slippageTicks: 3, tickSize: 0.5 });
assert.strictEqual(slippageTrade.slippageCost, 2 * 3 * 0.5 * 50 * 2);

// T5: deprecated levy is ignored; exchange transaction tax is charged on both notionals.
const levyTaxTrade = futuresTrade({ levyPerContract: 1, transactionTaxRate: 0.00002 });
assert.strictEqual(levyTaxTrade.levyCost, undefined);
assertNear(levyTaxTrade.taxCost, (100 * 50 + 110 * 50) * 0.00002);

// T6: every friction sums once; net P&L is gross less the component total.
const allCostsTrade = futuresTrade({
  contracts: 3,
  brokerCommissionPerContract: 2,
  levyPerContract: 1,
  transactionTaxRate: 0.00002,
  slippageTicks: 2,
  tickSize: 0.5,
});
assert.strictEqual(allCostsTrade.grossPnl, 1500);
assert.strictEqual(allCostsTrade.commissionCost, 12);
assertNear(allCostsTrade.taxCost, 0.63);
assert.strictEqual(allCostsTrade.slippageCost, 300);
assertNear(allCostsTrade.totalCost, 312.63);
assert.strictEqual(allCostsTrade.totalCost, allCostsTrade.commissionCost + allCostsTrade.taxCost + allCostsTrade.slippageCost);
assertNear(allCostsTrade.netPnl, 1187.37);

// T7: an unverified instrument without multiplier cannot produce performance metrics.
const missingMultiplier = backtest(history, 20, {
  assetClass: "FUTURES",
  instrumentSymbol: "UNVERIFIED=F",
  brokerCommissionPerContract: 0,
  slippageTicks: 0,
});
assert.strictEqual(missingMultiplier.costModel.supported, false);
assert.strictEqual(missingMultiplier.performance, null);
assert.strictEqual(missingMultiplier.costModel.reason, "MISSING_FUTURES_MULTIPLIER");

// T8: active slippage with no verified tick size fails closed.
const missingTick = calculateCost({
  assetClass: "FUTURES",
  contractSpec: { symbol: "SYNTH", multiplier: 50, transactionTaxRate: 0, currency: "TWD", source: "deterministic-test-fixture" },
  entryPrice: 100,
  exitPrice: 110,
  contracts: 1,
  brokerCommissionPerContract: 0,
  slippageTicks: 1,
});
assert.strictEqual(missingTick.supported, false);
assert.strictEqual(missingTick.reason, "MISSING_FUTURES_TICK_SIZE");

// T9: explicit zero commission, tax, and slippage are accepted; omitted values are not.
const explicitZero = calculateCost({
  assetClass: "FUTURES",
  contractSpec: syntheticSpec(50, 0.5, 0),
  entryPrice: 100,
  exitPrice: 110,
  contracts: 1,
  brokerCommissionPerContract: 0,
  slippageTicks: 0,
});
assert.strictEqual(explicitZero.supported, true);
assert.strictEqual(explicitZero.totalCost, 0);
assert.strictEqual(explicitZero.netPnl, explicitZero.grossPnl);
const omittedCosts = calculateCost({
  assetClass: "FUTURES",
  contractSpec: syntheticSpec(50),
  entryPrice: 100,
  exitPrice: 110,
  contracts: 1,
});
assert.strictEqual(omittedCosts.supported, false);
assert(["brokerCommissionPerContract", "slippageTicks"].every((field) => omittedCosts.missing.includes(field)));
for (const field of ["brokerCommissionPerContract", "slippageTicks"]) {
  const partialEconomics = {
    assetClass: "FUTURES",
    contractSpec: syntheticSpec(50),
    entryPrice: 100,
    exitPrice: 110,
    contracts: 1,
    brokerCommissionPerContract: 0,
    slippageTicks: 0,
  };
  delete partialEconomics[field];
  const unavailable = calculateCost(partialEconomics);
  assert.strictEqual(unavailable.supported, false, `${field} must fail closed when missing`);
  assert(unavailable.missing.includes(field), `${field} must be identified as missing`);
}
const unverifiedSpec = calculateCost({
  assetClass: "FUTURES",
  contractSpec: { symbol: "UNVERIFIED=F", multiplier: 50, tickSize: 0.5, transactionTaxRate: 0, currency: "USD" },
  entryPrice: 100,
  exitPrice: 110,
  contracts: 1,
  brokerCommissionPerContract: 0,
  slippageTicks: 0,
});
assert.strictEqual(unverifiedSpec.supported, false);
assert.strictEqual(unverifiedSpec.reason, "UNVERIFIED_FUTURES_CONTRACT_SPECIFICATION");

// T10: verified TAIFEX product specs are centralized; conflicting overrides fail closed.
assert.strictEqual(backtest.getFuturesContractSpecification("TX").multiplier, 200);
assert.strictEqual(backtest.getFuturesContractSpecification("MTX").multiplier, 50);
assert.strictEqual(backtest.getFuturesContractSpecification("TMF").multiplier, 10);
assert.strictEqual(backtest.getFuturesContractSpecification("TE").tickSize, 0.05);
assert.strictEqual(backtest.getFuturesContractSpecification("TF").tickSize, 0.2);
const conflictingSpec = calculateCost({
  assetClass: "FUTURES",
  instrumentSymbol: "TX",
  multiplier: 50,
  brokerCommissionPerContract: 0,
  slippageTicks: 0,
  entryPrice: 100,
  exitPrice: 101,
  contracts: 1,
});
assert.strictEqual(conflictingSpec.supported, false);
assert.strictEqual(conflictingSpec.reason, "FUTURES_CONTRACT_SPECIFICATION_CONFLICT");

console.log("P0B_FUTURES_EXECUTION_COSTS_OK: spec flow, multiplier preservation, P&L, all frictions, and fail-closed economics");
