"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

function loadFuturesCostModel() {
  const statePath = path.join(__dirname, "..", "js", "state.js");
  const calcPath = path.join(__dirname, "..", "js", "shared-calc.js");
  const stateSource = fs.readFileSync(statePath, "utf8");
  const calcSource = fs.readFileSync(calcPath, "utf8");
  const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {} };
  vm.createContext(sandbox);
  vm.runInContext(`${stateSource}\n${calcSource}\nthis.__p0 = { PORTFOLIO_COST_MODEL, buildBacktestLearningModel };`, sandbox, {
    filename: calcPath,
  });
  return sandbox.__p0;
}

function near(actual, expected, label) {
  assert(Number.isFinite(actual), `${label}: expected a finite number, got ${actual}`);
  assert(Math.abs(actual - expected) < 1e-9, `${label}: expected ${expected}, got ${actual}`);
}

const { PORTFOLIO_COST_MODEL, buildBacktestLearningModel: model } = loadFuturesCostModel();
const expectedProducts = {
  TX: { multiplier: 200, tickSize: 1, commission: 45 },
  MTX: { multiplier: 50, tickSize: 1, commission: 22.5 },
  TMF: { multiplier: 10, tickSize: 1, commission: 11 },
  TE: { multiplier: 4000, tickSize: 0.05, commission: 50 },
  TF: { multiplier: 1000, tickSize: 0.2, commission: 50 },
};

// Each supported product resolves its canonical economics and owner-authorized BASE assumptions.
for (const [symbol, expected] of Object.entries(expectedProducts)) {
  const spec = model.getFuturesContractSpecification(symbol);
  assert.strictEqual(spec.supported, true, `${symbol} must be supported`);
  assert.strictEqual(spec.multiplier, expected.multiplier, `${symbol} multiplier`);
  assert.strictEqual(spec.tickSize, expected.tickSize, `${symbol} tick size`);
  assert.strictEqual(spec.transactionTaxRate, 0.00002, `${symbol} transaction tax rate`);
  assert.strictEqual(spec.currency, "TWD", `${symbol} currency`);

  const assumptions = model.resolveFuturesExecutionAssumptions(symbol);
  assert.strictEqual(assumptions.supported, true, `${symbol} execution assumptions`);
  assert.strictEqual(assumptions.brokerCommissionPerContract, expected.commission, `${symbol} one-way commission`);
  assert.strictEqual(assumptions.commissionCurrency, "TWD", `${symbol} commission currency`);
  assert.strictEqual(assumptions.commissionUnit, "per-contract-one-way", `${symbol} commission unit`);
  assert.strictEqual(assumptions.slippageTicks, 1, `${symbol} BASE slippage`);

  const completeCostModel = model.getAssetCostModel("FUTURES", {
    instrumentSymbol: symbol,
    brokerCommissionPerContract: expected.commission,
    slippageTicks: 1,
  });
  assert.strictEqual(completeCostModel.supported, true, `${symbol} complete cost model`);
  assert.strictEqual(completeCostModel.multiplier, expected.multiplier, `${symbol} preserved multiplier`);
  assert.strictEqual(completeCostModel.tickSize, expected.tickSize, `${symbol} preserved tick size`);
  assert.strictEqual(completeCostModel.transactionTaxRate, 0.00002, `${symbol} preserved tax rate`);
  assert.strictEqual(completeCostModel.currency, "TWD", `${symbol} preserved currency`);
}

// Model A: one deterministic TX round trip proves each customer cost component and net P&L.
const txAssumptions = model.resolveFuturesExecutionAssumptions("TX");
const trade = model.calculateAssetTransactionCost({
  assetClass: "FUTURES",
  instrumentSymbol: "TX",
  entryPrice: 100,
  exitPrice: 110,
  contracts: 2,
  entrySide: "BUY",
  brokerCommissionPerContract: txAssumptions.brokerCommissionPerContract,
  slippageTicks: txAssumptions.slippageTicks,
  // Supplying these legacy/reference fields must not add customer trading cost.
  exchangeTradingFeePerContract: 999,
  clearingFeePerContract: 999,
  levyPerContract: 999,
});
assert.strictEqual(trade.supported, true, "deterministic TX trade must be supported");
near(trade.grossPnl, 4000, "gross P&L");
near(trade.commissionCost, 180, "round-trip broker commission");
near(trade.taxCost, (100 * 2 * 200 + 110 * 2 * 200) * 0.00002, "entry plus exit transaction tax");
near(trade.taxCost, 1.68, "transaction tax amount");
near(trade.slippageCost, 800, "round-trip slippage");
near(trade.totalCost, 981.68, "Model A total cost");
near(trade.otherCost, 0, "no additional exchange/clearing/levy cost");
near(trade.netPnl, 3018.32, "net P&L");
near(trade.netPnl, trade.grossPnl - trade.commissionCost - trade.taxCost - trade.slippageCost, "Model A reconciliation");
assert.strictEqual(trade.levyCost, undefined, "levy must not be separately deducted");
const oneContractTrade = model.calculateAssetTransactionCost({
  assetClass: "FUTURES",
  instrumentSymbol: "TX",
  entryPrice: 100,
  exitPrice: 110,
  contracts: 1,
  entrySide: "BUY",
  brokerCommissionPerContract: txAssumptions.brokerCommissionPerContract,
  slippageTicks: txAssumptions.slippageTicks,
  exchangeTradingFeePerContract: 0,
  clearingFeePerContract: 0,
  levyPerContract: 0,
});
for (const field of ["grossPnl", "commissionCost", "taxCost", "slippageCost", "totalCost", "netPnl"]) {
  near(trade[field], oneContractTrade[field] * 2, `two-contract ${field} scales linearly`);
}

// Missing commission or slippage remains unavailable; explicit zero is valid.
const missingCommission = model.getAssetCostModel("FUTURES", { instrumentSymbol: "TX", slippageTicks: 1 });
assert.strictEqual(missingCommission.supported, false, "missing commission must fail closed");
assert(missingCommission.missing.includes("brokerCommissionPerContract"));
const missingSlippage = model.getAssetCostModel("FUTURES", { instrumentSymbol: "TX", brokerCommissionPerContract: 45 });
assert.strictEqual(missingSlippage.supported, false, "missing slippage must fail closed");
assert(missingSlippage.missing.includes("slippageTicks"));
const explicitZero = model.getAssetCostModel("FUTURES", {
  instrumentSymbol: "TX",
  brokerCommissionPerContract: 0,
  slippageTicks: 0,
});
assert.strictEqual(explicitZero.supported, true, "explicit zero costs must be valid");
assert.strictEqual(explicitZero.brokerCommissionPerContract, 0);
assert.strictEqual(explicitZero.slippageTicks, 0);
assert.strictEqual(model.resolveFuturesExecutionAssumptions("TX", { brokerCommissionPerContract: undefined }).supported, false,
  "explicitly missing commission must not fall back to configured zero");
assert.strictEqual(model.resolveFuturesExecutionAssumptions("TX", { slippageTicks: undefined }).supported, false,
  "explicitly missing slippage must not fall back to configured zero");

// Canonical multiplier/tick conflicts and incomplete custom specifications fail closed.
const badMultiplier = model.getAssetCostModel("FUTURES", {
  instrumentSymbol: "TX", multiplier: 1, brokerCommissionPerContract: 45, slippageTicks: 1,
});
assert.strictEqual(badMultiplier.supported, false, "incorrect multiplier must fail closed");
assert.strictEqual(badMultiplier.reason, "FUTURES_CONTRACT_SPECIFICATION_CONFLICT");
const badTickSize = model.getAssetCostModel("FUTURES", {
  instrumentSymbol: "TX", tickSize: 0, brokerCommissionPerContract: 45, slippageTicks: 1,
});
assert.strictEqual(badTickSize.supported, false, "invalid tick size must fail closed");
const missingTickSize = model.getAssetCostModel("FUTURES", {
  instrumentSymbol: "SYNTH",
  contractSpec: { symbol: "SYNTH", market: "TEST", multiplier: 50, transactionTaxRate: 0.00002, currency: "TWD", source: "P0 test fixture" },
  brokerCommissionPerContract: 0,
  slippageTicks: 1,
});
assert.strictEqual(missingTickSize.supported, false, "active slippage without a tick size must fail closed");
assert(missingTickSize.missing.includes("tickSize"));

const unknown = model.getAssetCostModel("FUTURES", { instrumentSymbol: "UNKNOWN", brokerCommissionPerContract: 0, slippageTicks: 0 });
assert.strictEqual(unknown.supported, false, "unknown futures must fail closed");
assert.strictEqual(model.getAssetCostModel("FUTURES", { instrumentSymbol: "SOF", brokerCommissionPerContract: 0, slippageTicks: 0 }).supported, false,
  "SOF must fail closed");

// Exchange and clearing schedules can be exposed as reference metadata only.
assert(PORTFOLIO_COST_MODEL.taifexFuturesFeeReference.products.TX.exchangeTradingFeePerContract > 0);
assert(PORTFOLIO_COST_MODEL.taifexFuturesFeeReference.products.TX.clearingFeePerContract > 0);

console.log("P0B_FUTURES_ASSET_COST_MODEL_OK: TX/MTX/TMF/TE/TF economics, Model A reconciliation, fail-closed configuration, multiplier/tick integrity, SOF");
