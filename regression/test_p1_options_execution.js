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
  settlement: 9.8,
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
  source: { primary: "P1 execution regression fixture" },
  chain: [90, 95, 100, 105, 110, 115].map((strike) => ({
    strike,
    call: quote(quoteOverrides.call?.[strike]),
    put: quote(quoteOverrides.put?.[strike]),
  })),
});
const validMarket = {
  chain: makeChain(),
  spot: 100,
  direction: "Bullish",
  futuresPct: 0.2,
  volumePcr: 1,
  maxPainGapPct: 0,
  expiryChains: [
    { expiryDate: dateOffset(15), chain: makeChain().chain },
    { expiryDate: dateOffset(45), chain: makeChain().chain },
  ],
};

const normalBuy = engine.executionPrice(quote(), "BUY");
const normalSell = engine.executionPrice(quote(), "SELL");
assert.strictEqual(normalBuy.price, 10.5, "BUY must execute at ask");
assert.strictEqual(normalBuy.source, "ask");
assert.strictEqual(normalBuy.status, "EXECUTABLE");
assert.strictEqual(normalBuy.executionClass, "EXECUTABLE");
assert.strictEqual(normalSell.price, 9.5, "SELL must execute at bid");
assert.strictEqual(normalSell.source, "bid");
assert.strictEqual(normalSell.status, "EXECUTABLE");
assert.strictEqual(engine.executionPrice(quote({ bid: 10, ask: 10 }), "BUY").price, 10, "bid=ask is a valid boundary quote");
assert.strictEqual(engine.executionPrice(quote({ bid: 9, ask: 11 }), "BUY").price, 11, "bid<ask must use ask for BUY");
assert.strictEqual(engine.executionPrice(quote({ bid: 9, ask: 11 }), "SELL").price, 9, "bid<ask must use bid for SELL");

const missingAsk = engine.executionPrice({ bid: 9, last: null, settlement: null }, "BUY");
const missingBid = engine.executionPrice({ ask: 11, last: null, settlement: null }, "SELL");
const bothMissing = engine.executionPrice({ last: null, settlement: null }, "BUY");
assert.strictEqual(missingAsk.price, null);
assert.strictEqual(missingAsk.status, "UNAVAILABLE");
assert.strictEqual(missingAsk.reason, "MISSING_ASK");
assert.strictEqual(missingBid.price, null);
assert.strictEqual(missingBid.status, "UNAVAILABLE");
assert.strictEqual(missingBid.reason, "MISSING_BID");
assert.strictEqual(bothMissing.status, "UNAVAILABLE");
assert.strictEqual(bothMissing.reason, "BID_ASK_BOTH_MISSING");
assert.strictEqual(bothMissing.source, "unavailable");

const lastFallback = engine.executionPrice({ bid: 9, ask: null, last: 10 }, "BUY");
const settlementFallback = engine.executionPrice({ bid: null, ask: 11, last: null, settlement: 10 }, "SELL");
const lastWins = engine.executionPrice({ bid: null, ask: null, last: 10, settlement: 9 }, "BUY");
assert.strictEqual(lastFallback.price, 10);
assert.strictEqual(lastFallback.source, "last");
assert.strictEqual(lastFallback.status, "DEGRADED_FALLBACK");
assert.strictEqual(lastFallback.executionClass, "NON_EXECUTABLE");
assert.strictEqual(lastFallback.executable, false);
assert.strictEqual(lastFallback.reason, "MISSING_ASK");
assert.strictEqual(settlementFallback.price, 10);
assert.strictEqual(settlementFallback.source, "settlement");
assert.strictEqual(settlementFallback.status, "DEGRADED_FALLBACK");
assert.strictEqual(settlementFallback.reason, "MISSING_BID");
assert.strictEqual(lastWins.source, "last", "last must take precedence over settlement when both exist");

const crossedFallback = engine.executionPrice({ bid: 12, ask: 10, last: 11 }, "BUY");
const crossedUnavailable = engine.executionPrice({ bid: 12, ask: 10, last: null, settlement: null }, "BUY");
assert.strictEqual(crossedFallback.status, "DEGRADED_FALLBACK");
assert.strictEqual(crossedFallback.reason, "CROSSED_MARKET");
assert.strictEqual(crossedFallback.source, "last");
assert.strictEqual(crossedFallback.executionClass, "NON_EXECUTABLE");
assert.strictEqual(crossedUnavailable.status, "INVALID");
assert.strictEqual(crossedUnavailable.reason, "CROSSED_MARKET");
assert.strictEqual(crossedUnavailable.price, null, "crossed market must not be repaired with midpoint");

const zeroAsk = engine.executionPrice({ bid: 9, ask: 0, last: 10 }, "BUY");
const zeroBid = engine.executionPrice({ bid: 0, ask: 11, last: 10 }, "SELL");
const nullAsk = engine.executionPrice({ bid: 9, ask: null, last: 10 }, "BUY");
assert.strictEqual(zeroAsk.status, "DEGRADED_FALLBACK");
assert.strictEqual(zeroAsk.reason, "ASK_ZERO");
assert.strictEqual(zeroBid.status, "DEGRADED_FALLBACK");
assert.strictEqual(zeroBid.reason, "BID_ZERO");
assert.strictEqual(nullAsk.reason, "MISSING_ASK");
assert.notStrictEqual(zeroAsk.reason, nullAsk.reason, "zero and null execution inputs must remain distinct");
assert.strictEqual(engine.executionPrice({ bid: 0, ask: 11 }, "BUY").status, "EXECUTABLE", "BUY direction uses a valid ask even when bid is zero");

const models = engine.analyze(validMarket);
assert.strictEqual(models.length, 13, "all 13 existing options strategies must remain covered");
assert(models.every((model) => model.available && model.executable && model.tradable), "valid bid/ask must make all strategies executable");
assert(models.every((model) => model.executionStatus === "EXECUTABLE" && model.executionTrustStatus === "TRUSTED"), "strategy execution status must be explicit");
assert(models.every((model) => model.metrics.plTrustStatus === "TRUSTED" && model.metrics.executionGrade === "EXECUTION_GRADE"), "trusted strategies must expose execution-grade P/L");
assert(models.every((model) => model.legs.every((leg) => leg.executionStatus === "EXECUTABLE" && leg.executionSource === (leg.side === "BUY" ? "ask" : "bid"))), "every leg must preserve BUY ask / SELL bid provenance");
const mixedModel = models.find((model) => model.id === "bull-call-spread");
assert.deepStrictEqual(JSON.parse(JSON.stringify(mixedModel.legs.map((leg) => leg.executionSource))), ["ask", "bid"], "mixed BUY/SELL strategy legs must preserve direction");

const fallbackMarket = {
  ...validMarket,
  chain: makeChain({ call: { 100: { ask: null } } }),
};
const fallbackModel = engine.analyze(fallbackMarket)[0];
assert(fallbackModel.available, "fallback can remain available for modeled analysis");
assert.strictEqual(fallbackModel.legs[0].executionSource, "last");
assert.strictEqual(fallbackModel.legs[0].executionStatus, "DEGRADED_FALLBACK");
assert.strictEqual(fallbackModel.executionStatus, "NON_EXECUTABLE");
assert.strictEqual(fallbackModel.executionTrustStatus, "UNTRUSTED");
assert.strictEqual(fallbackModel.metrics.plTrustStatus, "UNTRUSTED");
assert.strictEqual(fallbackModel.metrics.executionGrade, "MODEL_ONLY");
assert.strictEqual(fallbackModel.metrics.trustBoundary.failedLegIndexes.includes(0), true);

const crossedMarket = {
  ...validMarket,
  chain: makeChain({ call: { 100: { bid: 12, ask: 10, last: 11 } } }),
};
const crossedModel = engine.analyze(crossedMarket)[0];
assert.strictEqual(crossedModel.legs[0].executionReason, "CROSSED_MARKET");
assert.strictEqual(crossedModel.executionTrustStatus, "UNTRUSTED");
assert.strictEqual(crossedModel.metrics.executionGrade, "MODEL_ONLY");

const oneInvalidLegTrust = engine.executionTrust([
  { side: "BUY", executionStatus: "EXECUTABLE", executionSource: "ask", quoteValidity: "VALID", tradability: "TRADABLE", liquidityEligibility: "ELIGIBLE" },
  { side: "SELL", executionStatus: "INVALID", executionSource: "unavailable", quoteValidity: "VALID", tradability: "NOT_TRADABLE", liquidityEligibility: "INELIGIBLE" },
]);
assert.strictEqual(oneInvalidLegTrust.status, "UNTRUSTED");
assert.deepStrictEqual(JSON.parse(JSON.stringify(oneInvalidLegTrust.failedLegIndexes)), [1]);

console.log("P1_OPTIONS_EXECUTION_OK: P1-05..P1-10 status, direction, fallback, crossed, 13 strategies, P/L trust");
