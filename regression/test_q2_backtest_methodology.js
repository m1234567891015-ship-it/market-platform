"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const stateSource = fs.readFileSync(path.join(__dirname, "..", "js", "state.js"), "utf8");
const source = fs.readFileSync(path.join(__dirname, "..", "js", "shared-calc.js"), "utf8");
const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {} };
vm.createContext(sandbox);
vm.runInContext(`${stateSource}\n${source}\nthis.__q2 = { buildBacktestLearningModel, calculateBacktestProfitFactor };`, sandbox, {
  filename: path.join(__dirname, "..", "js", "shared-calc.js"),
});

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

const model = sandbox.__q2.buildBacktestLearningModel(history, 20);
assert.strictEqual(sandbox.__q2.calculateBacktestProfitFactor([1, 2, 3]), null);
assert.strictEqual(model.signalTiming, "T close");
assert.strictEqual(model.executionTiming, "T+1 open");
assert(/T\+1 open/.test(model.executionPriceMethod));
assert.strictEqual(model.sampleMethod, "chronological non-overlapping effective sample estimate");
assert(Array.isArray(model.signals) && model.signals.length > 0, "fixture must produce backtest signals");

for (const signal of model.signals) {
  assert.strictEqual(signal.rawSamples, signal.samples);
  assert(signal.effectiveSamples > 0 && signal.effectiveSamples <= signal.rawSamples);
  assert(signal.overlapRatio >= 0 && signal.overlapRatio < 1);
  assert(signal.split.train.lastIndex < signal.split.validation.firstIndex);
  assert(signal.split.validation.lastIndex < signal.split.test.firstIndex);
}

assert(model.validation?.testUntouchedBySelection === true);
assert(model.costModel.roundTripPct > 0);
assert(model.signals.every((signal) => signal.grossAverageReturn >= signal.averageReturn));
assert(model.signals.some((signal) => signal.grossAverageReturn > signal.averageReturn));
console.log("Q2_BACKTEST_METHODOLOGY_OK: chronological split, effective samples, execution timing");
