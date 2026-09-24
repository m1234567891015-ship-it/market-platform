"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const stateSource = fs.readFileSync(path.join(__dirname, "..", "js", "state.js"), "utf8");
const source = fs.readFileSync(path.join(__dirname, "..", "js", "shared-calc.js"), "utf8");
const sandbox = { console, Math, Date, Number, Array, Object, Map, Set, JSON, window: {} };
vm.createContext(sandbox);
vm.runInContext(`${stateSource}\n${source}\nthis.__q3 = { buildBacktestLearningModel };`, sandbox, {
  filename: path.join(__dirname, "..", "js", "shared-calc.js"),
});

const score = sandbox.__q3.buildBacktestLearningModel.calculateRiskAdjustedReturnScore;
const metadata = score.metadata;
const nearlyEqual = (actual, expected) => assert(Math.abs(actual - expected) < 1e-12);

nearlyEqual(score([1, 2, 3]), 2);
nearlyEqual(score([-1, -2, -3]), -2);
assert.strictEqual(score([]), null);
assert.strictEqual(score([1]), null);
assert.strictEqual(score([1, 1, 1]), null);
assert(Number.isFinite(score([1, 2, 3])));
assert(Number.isFinite(score([-1, -2, -3])));

assert.strictEqual(metadata.name, "riskAdjustedReturnScore");
assert.strictEqual(metadata.annualization, "none");
assert.strictEqual(metadata.riskFreeRate, "not applied");
assert(/sampleStandardDeviation/.test(metadata.formula));
assert(/not Sharpe|no risk-free rate/.test(metadata.notSharpeBecause));

const summary = sandbox.__q3.buildBacktestLearningModel.summarizeBacktestObservations(
  [{ index: 0, value: 1 }, { index: 1, value: 2 }, { index: 2, value: 3 }],
);
nearlyEqual(summary.riskAdjustedReturnScore, 2);
assert.strictEqual(summary.sharpe, undefined);
assert.strictEqual(summary.riskAdjustedReturnScoreMeta.name, "riskAdjustedReturnScore");
assert(Number.isFinite(summary.riskAdjustedReturnScore));

console.log("Q3_RISK_METRIC_OK: custom riskAdjustedReturnScore is documented and numerically deterministic");
