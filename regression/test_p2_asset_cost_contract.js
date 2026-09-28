"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const statePath = path.join(__dirname, "..", "js", "state.js");
const calcPath = path.join(__dirname, "..", "js", "shared-calc.js");
const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {} };
vm.createContext(sandbox);
vm.runInContext(
  `${fs.readFileSync(statePath, "utf8")}\n${fs.readFileSync(calcPath, "utf8")}\nthis.__p2 = { PORTFOLIO_COST_MODEL, buildBacktestLearningModel };`,
  sandbox,
  { filename: calcPath },
);

const { PORTFOLIO_COST_MODEL, buildBacktestLearningModel: model } = sandbox.__p2;
const calculate = model.calculateAssetTransactionCost;
const near = (actual, expected, label) => {
  assert(Number.isFinite(actual), `${label}: expected finite value, got ${actual}`);
  assert(Math.abs(actual - expected) < 1e-9, `${label}: expected ${expected}, got ${actual}`);
};

// Taiwan stock and ETF trades route the sell-side tax through the matching rate.
const twStockRequest = {
  assetClass: "TW_EQUITY", entryPrice: 100, exitPrice: 110, quantity: 10,
  entrySide: "BUY", exitSide: "SELL",
};
const twStock = calculate(twStockRequest);
const twEtf = calculate({ ...twStockRequest, securityType: "ETF" });
assert.strictEqual(twStock.supported, true);
near(twStock.taxCost, 3.3, "Taiwan stock sell tax");
near(twEtf.taxCost, 1.1, "Taiwan ETF sell tax");
near(twStock.commissionCost, (1000 + 1100) * (PORTFOLIO_COST_MODEL.feePct / 100), "Taiwan stock commission routing");
near(twStock.roundTripCost, twStock.totalEntryCost + twStock.totalExitCost, "Taiwan stock stable breakdown");

// US equity applies its explicit commission model and no Taiwan transaction tax.
const us = calculate({
  assetClass: "US_EQUITY", entryPrice: 100, exitPrice: 110, quantity: 10,
  entrySide: "BUY", exitSide: "SELL",
});
assert.strictEqual(us.supported, true);
near(us.commissionCost, 1.575, "US equity commission");
near(us.taxCost, 0, "US equity has no Taiwan sell tax");

// Model A futures cost semantics: per-side commission, tax on both notionals,
// tick slippage converted through the canonical synthetic contract economics.
const syntheticSpec = {
  symbol: "P2SYN", market: "TEST", multiplier: 50, tickSize: 0.5,
  transactionTaxRate: 0.00002, currency: "TWD", source: "P2 committed contract fixture",
};
const futuresRequest = {
  assetClass: "FUTURES", contractSpec: syntheticSpec, entryPrice: 100, exitPrice: 110,
  contracts: 2, brokerCommissionPerContract: 3, slippageTicks: 2,
};
const futures = calculate(futuresRequest);
assert.strictEqual(futures.supported, true);
near(futures.grossPnl, 1000, "futures gross P&L");
near(futures.commissionCost, 12, "futures two-sided commission");
near(futures.taxCost, 0.42, "futures entry and exit transaction tax");
near(futures.slippageCost, 200, "futures tick slippage");
near(futures.totalCost, 212.42, "futures Model A total");
near(futures.netPnl, futures.grossPnl - futures.totalCost, "futures net P&L reconciliation");

// Options aggregate each leg's round-trip costs and preserve component totals.
const optionLegs = [
  { quantity: 2, multiplier: 50, entryPrice: 5, exitPrice: 6, commission: 1, exchangeFee: 2, slippage: 0.1 },
  { quantity: 1, multiplier: 50, entryPrice: 4, exitPrice: 3, commission: 1, exchangeFee: 2, slippage: 0.1 },
];
const options = calculate({ assetClass: "OPTIONS", legs: optionLegs });
assert.strictEqual(options.supported, true);
assert.strictEqual(options.legs.length, 2);
near(options.roundTripCost, options.legs.reduce((sum, leg) => sum + leg.roundTripCost, 0), "options multi-leg aggregate");
near(options.commissionCost, options.legs.reduce((sum, leg) => sum + leg.commissionCost, 0), "options commission aggregate");
near(options.regulatoryCost, options.legs.reduce((sum, leg) => sum + leg.regulatoryCost, 0), "options regulatory aggregate");

// Explicit component overrides take effect; missing required futures inputs fail closed.
const overridden = calculate({ ...twStockRequest, commissionPct: 0.5, slippagePct: 0, sellTaxPct: 0 });
near(overridden.commissionCost, 10.5, "explicit equity commission override");
near(overridden.taxCost, 0, "explicit equity tax override");
near(overridden.slippageCost, 0, "explicit zero slippage override");
const missingFuturesCommission = model.getAssetCostModel("FUTURES", {
  instrumentSymbol: "TX", slippageTicks: 1,
});
assert.strictEqual(missingFuturesCommission.supported, false, "missing futures commission must fail closed");
assert(missingFuturesCommission.missing.includes("brokerCommissionPerContract"));
const explicitZeroFutures = model.getAssetCostModel("FUTURES", {
  instrumentSymbol: "TX", brokerCommissionPerContract: 0, slippageTicks: 0,
});
assert.strictEqual(explicitZeroFutures.supported, true, "explicit zero futures costs are valid");
const unknown = calculate({ assetClass: "CRYPTO", entryPrice: 100, exitPrice: 110, quantity: 1 });
assert.strictEqual(unknown.supported, false, "unknown asset class must fail closed");
assert.strictEqual(unknown.reason, "UNKNOWN_ASSET_CLASS");

// Identical requests return identical serialized breakdowns, including nested legs.
for (const request of [twStockRequest, futuresRequest, { assetClass: "OPTIONS", legs: optionLegs }]) {
  assert.strictEqual(
    JSON.stringify(calculate(request)),
    JSON.stringify(calculate(request)),
    `${request.assetClass} breakdown must be deterministic`,
  );
}

console.log("P2_ASSET_COST_CONTRACT_OK: TW equity/ETF, US equity, futures Model A, options multi-leg, overrides, fail-closed, explicit zero, deterministic breakdown");
