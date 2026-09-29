"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const root = path.join(__dirname, "..");
const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {} };
vm.createContext(sandbox);
vm.runInContext(
  `${fs.readFileSync(path.join(root, "js", "state.js"), "utf8")}\n${fs.readFileSync(path.join(root, "js", "shared-calc.js"), "utf8")}\nthis.__p0b = { buildBacktestLearningModel };`,
  sandbox,
  { filename: path.join(root, "js", "shared-calc.js") },
);
const model = sandbox.__p0b.buildBacktestLearningModel;
const requests = JSON.parse(fs.readFileSync(0, "utf8"));
const result = requests.map((item) => {
  const assumptions = model.resolveFuturesExecutionAssumptions(item.symbol, item.overrides || {});
  if (!assumptions.supported) return { assumptions, cost: assumptions };
  const cost = model.calculateAssetTransactionCost({
    assetClass: "FUTURES", instrumentSymbol: item.symbol, direction: item.direction,
    entryPrice: item.entryPrice, exitPrice: item.exitPrice, quantity: item.quantity,
    brokerCommissionPerContract: assumptions.brokerCommissionPerContract,
    slippageTicks: assumptions.slippageTicks,
    ...item.overrides,
  });
  const grossReturnPct = item.direction === "SHORT"
    ? ((item.entryPrice - item.exitPrice) / item.entryPrice) * 100
    : ((item.exitPrice - item.entryPrice) / item.entryPrice) * 100;
  return { assumptions, cost, netReturnPct: model.calculateNetReturn(grossReturnPct, cost.normalizedCostPct) };
});
process.stdout.write(JSON.stringify(result));
