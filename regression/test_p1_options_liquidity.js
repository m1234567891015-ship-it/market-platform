"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const sourcePath = path.join(__dirname, "..", "js", "page-global-market-assethub.js");
const source = fs.readFileSync(sourcePath, "utf8");
const start = source.indexOf("initDerivativesAnalyticsPage.strategyEngine = (() => {");
const endMarker = "\n})();";
const end = source.indexOf(endMarker, start);
assert(start >= 0 && end > start, "strategy engine assignment must be present");
const sandbox = { initDerivativesAnalyticsPage: {} };
vm.runInNewContext(source.slice(start, end + endMarker.length), sandbox, { filename: sourcePath });
const engine = sandbox.initDerivativesAnalyticsPage.strategyEngine;

const dateOffset = (days) => new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);
const quote = (overrides = {}) => ({
  last: 10,
  bid: 9.5,
  ask: 10.5,
  volume: 10,
  openInterest: 100,
  quoteTime: new Date().toISOString(),
  ...overrides,
});
const makeChain = (quoteOverrides = {}) => ({
  tradeDate: dateOffset(0),
  session: "REGULAR",
  selectedExpiry: "M1",
  selectedExpiryDate: dateOffset(30),
  source: { primary: "P1 regression fixture" },
  chain: [90, 95, 100, 105, 110, 115].map((strike) => ({
    strike,
    call: quote(quoteOverrides.call?.[strike]),
    put: quote(quoteOverrides.put?.[strike]),
  })),
});
const validMarket = { chain: makeChain(), spot: 100, direction: "Bullish", futuresPct: 0.2, volumePcr: 1, maxPainGapPct: 0 };

const valid = engine.liquidityScore(quote(), validMarket);
assert.strictEqual(valid.quoteValidity, "VALID", "valid liquid quote must be quote-valid");
assert.strictEqual(valid.tradability, "TRADABLE", "valid bid/ask must be tradable");
assert.strictEqual(valid.liquidityEligibility, "ELIGIBLE", "valid liquid quote must pass liquidity gate");

for (const field of ["bid", "ask"]) {
  const result = engine.liquidityScore(quote({ [field]: null }), validMarket);
  assert.strictEqual(result.quoteValidity, "VALID", `${field} missing must not erase a valid last quote`);
  assert.strictEqual(result.tradability, "NOT_TRADABLE", `${field} missing must fail tradability`);
  assert.strictEqual(result.liquidityEligibility, "INELIGIBLE", `${field} missing must fail liquidity eligibility`);
}
const bothMissing = engine.liquidityScore(quote({ bid: null, ask: null }), validMarket);
assert.strictEqual(bothMissing.quoteValidity, "VALID");
assert.strictEqual(bothMissing.tradability, "NOT_TRADABLE");
assert.strictEqual(bothMissing.liquidityEligibility, "INELIGIBLE");

const zeroVolume = engine.liquidityScore(quote({ volume: 0 }), validMarket);
const zeroOpenInterest = engine.liquidityScore(quote({ openInterest: 0 }), validMarket);
const missingVolume = engine.liquidityScore(quote({ volume: null }), validMarket);
const missingOpenInterest = engine.liquidityScore(quote({ openInterest: null }), validMarket);
assert.strictEqual(zeroVolume.volumeState, "ZERO");
assert.strictEqual(zeroVolume.verified, true, "legal zero volume is verified, not missing/error");
assert.strictEqual(zeroVolume.liquidityEligibility, "INELIGIBLE");
assert(zeroVolume.eligibilityReasons.includes("VOLUME_ZERO"));
assert.strictEqual(zeroOpenInterest.openInterestState, "ZERO");
assert.strictEqual(zeroOpenInterest.verified, true, "legal zero OI is verified, not missing/error");
assert.strictEqual(zeroOpenInterest.liquidityEligibility, "INELIGIBLE");
assert(zeroOpenInterest.eligibilityReasons.includes("OPEN_INTEREST_ZERO"));
assert.strictEqual(missingVolume.volumeState, "MISSING");
assert.strictEqual(missingVolume.verified, false);
assert.strictEqual(missingOpenInterest.openInterestState, "MISSING");
assert.strictEqual(missingOpenInterest.verified, false);
assert.notStrictEqual(zeroVolume.volumeState, missingVolume.volumeState, "zero and null volume semantics must remain distinct");
assert.notStrictEqual(zeroOpenInterest.openInterestState, missingOpenInterest.openInterestState, "zero and null OI semantics must remain distinct");

const thresholds = engine.liquidityThresholds;
assert.deepStrictEqual(JSON.parse(JSON.stringify(thresholds)), {
  minVolume: 0,
  minOpenInterest: 0,
  maxSpreadRatio: 0.1,
  freshQuoteMaxAgeDays: 1,
  degradedQuoteMaxAgeDays: 3,
});
const atSpreadBoundary = engine.liquidityScore(quote({ bid: 95, ask: 105 }), validMarket);
const aboveSpreadBoundary = engine.liquidityScore(quote({ bid: 94, ask: 106 }), validMarket);
assert.strictEqual(atSpreadBoundary.spreadPct, thresholds.maxSpreadRatio);
assert.strictEqual(atSpreadBoundary.liquidityEligibility, "ELIGIBLE", "spread threshold is inclusive");
assert.strictEqual(aboveSpreadBoundary.liquidityEligibility, "INELIGIBLE");

assert.deepStrictEqual(JSON.parse(JSON.stringify(engine.liquidityGate([{ liquidityEligibility: "ELIGIBLE" }]))), {
  eligible: true,
  failedLegIndexes: [],
  failedLegCount: 0,
});
assert.deepStrictEqual(JSON.parse(JSON.stringify(engine.liquidityGate([{ liquidityEligibility: "INELIGIBLE" }]))), {
  eligible: false,
  failedLegIndexes: [0],
  failedLegCount: 1,
});
assert.deepStrictEqual(JSON.parse(JSON.stringify(engine.liquidityGate([
  { liquidityEligibility: "INELIGIBLE" },
  { liquidityEligibility: "ELIGIBLE" },
  { liquidityEligibility: "INELIGIBLE" },
]))), {
  eligible: false,
  failedLegIndexes: [0, 2],
  failedLegCount: 2,
});

const oneLegFailMarket = {
  ...validMarket,
  chain: makeChain({ call: { 100: { volume: 0 } } }),
};
const oneLegFail = engine.analyze(oneLegFailMarket)[0];
assert(oneLegFail.available, "a valid quote remains available for modeled analysis");
assert.strictEqual(oneLegFail.executable, false);
assert.strictEqual(oneLegFail.tradable, false);
assert.deepStrictEqual(JSON.parse(JSON.stringify(oneLegFail.liquidityGate.failedLegIndexes)), [0]);
assert.strictEqual(oneLegFail.breakdown.liquidityFit, Math.round(Math.min(...oneLegFail.legs.map((leg) => leg.liquidityScore)) / 10), "illiquid leg must set liquidity fit from the weakest leg");

const allLiquidStrategies = engine.analyze({
  ...validMarket,
  expiryChains: [
    { expiryDate: dateOffset(15), chain: makeChain().chain },
    { expiryDate: dateOffset(45), chain: makeChain().chain },
  ],
});
assert(allLiquidStrategies.every((model) => model.available && model.executable && model.tradable && model.liquidityEligible), "all required legs must pass for a multi-leg strategy to be executable");

const zeroQuoteOverrides = {
  call: { 90: { volume: 0 }, 95: { volume: 0 }, 100: { volume: 0 }, 105: { volume: 0 }, 110: { volume: 0 }, 115: { volume: 0 } },
  put: { 90: { openInterest: 0 }, 95: { openInterest: 0 }, 100: { openInterest: 0 }, 105: { openInterest: 0 }, 110: { openInterest: 0 }, 115: { openInterest: 0 } },
};
const allZeroMarket = {
  ...validMarket,
  chain: makeChain(zeroQuoteOverrides),
  expiryChains: [
    { expiryDate: dateOffset(15), chain: makeChain(zeroQuoteOverrides).chain },
    { expiryDate: dateOffset(45), chain: makeChain(zeroQuoteOverrides).chain },
  ],
};
const allStrategies = engine.analyze(allZeroMarket);
assert.strictEqual(allStrategies.length, 13, "all 13 existing options strategies must remain in the contract");
assert(allStrategies.every((model) => model.available), "zero volume/OI must not become missing quote data");
assert(allStrategies.every((model) => model.executable === false && model.tradable === false), "every strategy must fail closed when required legs fail liquidity");
assert(allStrategies.some((model) => model.liquidityGate.failedLegCount > 1), "multi-leg failures must not be masked by another leg");

console.log("P1_OPTIONS_LIQUIDITY_OK: P1-00..P1-04 matrix, 13 strategies, zero/null, leg gates, thresholds");
