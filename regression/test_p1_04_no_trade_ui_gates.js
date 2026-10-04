"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");

const sourcePath = "js/page-global-market-derivatives.js";
const source = fs.readFileSync(sourcePath, "utf8");
const start = source.indexOf("initDerivativesAnalyticsPage.strategyEngine = (() => {");
const endMarker = "\n})();";
const end = source.indexOf(endMarker, start);
assert(start >= 0 && end > start, "strategy engine must expose its in-scope canonical gate resolver");
const sandbox = { initDerivativesAnalyticsPage: {} };
require("node:vm").runInNewContext(source.slice(start, end + endMarker.length), sandbox, { filename: sourcePath });
const resolver = sandbox.initDerivativesAnalyticsPage.strategyEngine.decisionStateFromExistingGates;
assert.equal(typeof resolver, "function");

const unknown = resolver({});
assert.equal(unknown.decisionState, "UNKNOWN");
assert.equal(unknown.decisionEligible, null);
assert.deepEqual(Array.from(unknown.reasonCodes), ["UNKNOWN"]);

const untrusted = resolver({ executionTrust: { status: "UNTRUSTED", failedLegs: [{ reasons: ["QUOTE_INVALID"] }] } });
assert.equal(untrusted.decisionState, "NO_TRADE");
assert.equal(untrusted.decisionEligible, false);
assert.ok(untrusted.reasonCodes.includes("INSUFFICIENT_EVIDENCE"));

const illiquid = resolver({ liquidityGate: { eligible: false, failedLegCount: 2 } });
assert.equal(illiquid.decisionState, "NO_TRADE");
assert.ok(illiquid.reasonCodes.includes("LIQUIDITY_INSUFFICIENT"));

const unsupported = resolver({ pointInTime: { aligned: false, reasons: ["DECISION_AS_OF_UNAVAILABLE"] } });
assert.equal(unsupported.decisionState, "NO_TRADE");
assert.ok(unsupported.reasonCodes.includes("UNSUPPORTED_CONTEXT"));

const candidateOnly = resolver({
  executionTrust: { status: "TRUSTED", failedLegs: [] },
  liquidityGate: { eligible: true, failedLegCount: 0 },
  pointInTime: { aligned: true, reasons: [] },
});
assert.equal(candidateOnly.decisionState, "UNKNOWN");
assert.equal(candidateOnly.decisionEligible, null);

// Generic risk and signal values are deliberately not inputs to a new gate.
const highRiskWithoutGate = resolver({ riskScore: 100, signalConflict: true });
assert.equal(highRiskWithoutGate.decisionState, "UNKNOWN");

console.log("P1-04 UI gate semantics: 6 checks PASS");
