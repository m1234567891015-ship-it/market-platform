"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const stateSource = fs.readFileSync(path.join(__dirname, "..", "js", "state.js"), "utf8");
const coreSource = fs.readFileSync(path.join(__dirname, "..", "js", "core.js"), "utf8");
const calcSource = fs.readFileSync(path.join(__dirname, "..", "js", "shared-calc.js"), "utf8");
const futuresPageSource = fs.readFileSync(path.join(__dirname, "..", "js", "page-global-market-futures.js"), "utf8");
const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, Element: function Element() {}, window: {} };
vm.createContext(sandbox);
vm.runInContext(`${stateSource}\n${coreSource}\n${calcSource}\nthis.__p0b1 = { buildBacktestLearningModel, analyzeTechnicalTheories };`, sandbox, {
  filename: path.join(__dirname, "..", "js", "shared-calc.js"),
});

const { buildBacktestLearningModel: backtest, analyzeTechnicalTheories } = sandbox.__p0b1;
const products = {
  TX: { multiplier: 200, tickSize: 1, commission: 45, exchangeFee: 12, clearingFee: 8 },
  MTX: { multiplier: 50, tickSize: 1, commission: 22.5, exchangeFee: 7.5, clearingFee: 5 },
  TMF: { multiplier: 10, tickSize: 1, commission: 11, exchangeFee: 4.8, clearingFee: 3.2 },
  TE: { multiplier: 4000, tickSize: 0.05, commission: 50, exchangeFee: 12, clearingFee: 8 },
  TF: { multiplier: 1000, tickSize: 0.2, commission: 50, exchangeFee: 12, clearingFee: 8 },
};
const assertNear = (actual, expected, label) => assert(Math.abs(actual - expected) < 1e-8, `${label}: expected ${expected}, got ${actual}`);
assert.match(futuresPageSource, /function buildFuturesStockStyleChartDetail[\s\S]*?symbol: item\?\.symbol \|\| item\?\.productSymbol/,
  "formal futures chart detail must preserve the product symbol for execution assumption lookup");
const history = Array.from({ length: 360 }, (_, index) => {
  const close = 100 + (index * 0.08) + (Math.sin(index / 9) * 2.5);
  const previous = index ? 100 + ((index - 1) * 0.08) + (Math.sin((index - 1) / 9) * 2.5) : close;
  return {
    date: `2026-${String(Math.floor(index / 30) + 1).padStart(2, "0")}-${String((index % 30) + 1).padStart(2, "0")}`,
    open: close * 0.995,
    high: Math.max(close, previous) * 1.01,
    low: Math.min(close, previous) * 0.99,
    close,
    volume: 100000 + ((index % 11) * 1000),
    openInterest: 50000 + (index % 100),
  };
});

// The production analysis caller resolves the symbol's owner-authorized application assumptions.
const originalResolver = backtest.resolveFuturesExecutionAssumptions;
const resolverCalls = [];
backtest.resolveFuturesExecutionAssumptions = (symbol, overrides) => {
  resolverCalls.push(symbol);
  return originalResolver(symbol, overrides);
};
for (const [symbol, spec] of Object.entries(products)) {
  const result = analyzeTechnicalTheories({
    symbol,
    futuresNativeInterval: "day",
    historyDays: history,
  });
  const learning = result.backtestLearning;
  assert(learning, `${symbol}: formal caller must return a backtest model`);
  assert.strictEqual(learning.costModel.supported, true, `${symbol}: authorized BASE config should resolve`);
  assert.strictEqual(learning.costModel.brokerCommissionPerContract, spec.commission);
  assert.strictEqual(learning.costModel.slippageTicks, 1);
  assert.strictEqual(learning.costModel.multiplier, spec.multiplier);
  assert.strictEqual(learning.costModel.referenceBreakdown.feeReference.exchangeTradingFeePerContract, spec.exchangeFee);
  assert.strictEqual(learning.costModel.referenceBreakdown.feeReference.clearingFeePerContract, spec.clearingFee);
  assert(learning.performance, `${symbol}: formal backtest must produce net performance`);
  assert.strictEqual(learning.costModel.executionAssumptionSource, "Project Owner authorized P0-B1 BASE assumptions");
  const observations = learning.signals.flatMap((signal) => signal.observations || []);
  for (const trade of observations) {
    assert.strictEqual(trade.multiplier, spec.multiplier);
    assert.strictEqual(trade.netPnl, trade.grossPnl - trade.totalCost);
    assert.strictEqual(trade.levyCost, undefined, "Model A must not expose a levy deduction");
  }
}
backtest.resolveFuturesExecutionAssumptions = originalResolver;
assert.deepStrictEqual(resolverCalls, Object.keys(products), "formal futures callers must resolve each product symbol");

// A shorter deterministic backtest window yields concrete trades for trade-level net P&L assertions.
for (const symbol of Object.keys(products)) {
  const assumptions = originalResolver(symbol);
  const model = backtest(history, 20, {
    assetClass: "FUTURES",
    instrumentSymbol: symbol,
    ...assumptions,
  });
  assert(model.performance, `${symbol}: backtest builder must produce net performance`);
  const trade = model.signals.flatMap((signal) => signal.observations || [])[0];
  assert(trade, `${symbol}: deterministic backtest must produce a trade`);
  assert.strictEqual(trade.netPnl, trade.grossPnl - trade.totalCost);
  assert.strictEqual(trade.levyCost, undefined);
  for (const signal of model.signals) {
    assertNear(signal.totalNetPnl, signal.totalGrossPnl - signal.totalCost, `${symbol} aggregate net P&L`);
  }
}

// End-to-end hand check for every product: commission, statutory tax and slippage only.
for (const [symbol, spec] of Object.entries(products)) {
  const assumptions = backtest.resolveFuturesExecutionAssumptions(symbol);
  const trade = backtest.calculateAssetTransactionCost({
    assetClass: "FUTURES",
    instrumentSymbol: symbol,
    ...assumptions,
    entryPrice: 100,
    exitPrice: 101,
    contracts: 2,
  });
  const gross = (101 - 100) * 2 * spec.multiplier;
  const commission = spec.commission * 2 * 2;
  const tax = (100 * 2 * spec.multiplier + 101 * 2 * spec.multiplier) * 0.00002;
  const slippage = spec.tickSize * spec.multiplier * 2 * 2;
  assertNear(trade.grossPnl, gross, `${symbol} gross`);
  assertNear(trade.commissionCost, commission, `${symbol} commission`);
  assertNear(trade.taxCost, tax, `${symbol} tax`);
  assertNear(trade.slippageCost, slippage, `${symbol} slippage`);
  assertNear(trade.totalCost, commission + tax + slippage, `${symbol} total`);
  assertNear(trade.netPnl, gross - commission - tax - slippage, `${symbol} net`);
}

for (const symbol of ["TE", "TF"]) {
  const spec = products[symbol];
  const base = backtest.resolveFuturesExecutionAssumptions(symbol);
  const stress = backtest.resolveFuturesExecutionAssumptions(symbol, { slippageTicks: 2 });
  const request = { assetClass: "FUTURES", instrumentSymbol: symbol, entryPrice: 100, exitPrice: 101, contracts: 2, brokerCommissionPerContract: base.brokerCommissionPerContract };
  const baseCost = backtest.calculateAssetTransactionCost({ ...request, slippageTicks: base.slippageTicks });
  const stressCost = backtest.calculateAssetTransactionCost({ ...request, slippageTicks: stress.slippageTicks });
  assert.strictEqual(stress.slippageTicks, 2);
  assertNear(stressCost.slippageCost, baseCost.slippageCost * 2, `${symbol} two-tick sensitivity`);
  assert(spec.tickSize > 0);
}

// Missing settings fail closed; explicit zeros remain valid and distinct from missing.
const missingCommission = backtest.resolveFuturesExecutionAssumptions("TX", { brokerCommissionPerContract: null });
assert.strictEqual(missingCommission.supported, false);
assert.strictEqual(missingCommission.reason, "MISSING_OR_INVALID_BROKER_COMMISSION_CONFIGURATION");
const missingSlippage = backtest.resolveFuturesExecutionAssumptions("TX", { slippageTicks: null });
assert.strictEqual(missingSlippage.supported, false);
assert.strictEqual(missingSlippage.reason, "MISSING_OR_INVALID_SLIPPAGE_CONFIGURATION");
const explicitZero = backtest.calculateAssetTransactionCost({
  assetClass: "FUTURES",
  instrumentSymbol: "TX",
  brokerCommissionPerContract: 0,
  slippageTicks: 0,
  entryPrice: 100,
  exitPrice: 101,
  contracts: 1,
});
assert.strictEqual(explicitZero.supported, true);
assert.strictEqual(explicitZero.commissionCost, 0);
assert.strictEqual(explicitZero.slippageCost, 0);

const conflict = backtest.calculateAssetTransactionCost({
  assetClass: "FUTURES", instrumentSymbol: "TX", multiplier: 50,
  brokerCommissionPerContract: 0, slippageTicks: 0,
  entryPrice: 100, exitPrice: 101, contracts: 1,
});
assert.strictEqual(conflict.supported, false);
assert.strictEqual(conflict.reason, "FUTURES_CONTRACT_SPECIFICATION_CONFLICT");
for (const symbol of ["UNKNOWN=F", "SOF"]) {
  const unsupported = backtest(history, 20, {
    assetClass: "FUTURES", instrumentSymbol: symbol,
    brokerCommissionPerContract: 0, slippageTicks: 0,
  });
  assert.strictEqual(unsupported.costModel.supported, false, `${symbol} must remain fail closed`);
  assert.strictEqual(unsupported.performance, null, `${symbol} must not produce net performance`);
}

console.log("P0B1_FUTURES_BACKTEST_COST_WIRING_OK: formal caller, five supported products, Model A costs, fail-closed and numerical proof");
