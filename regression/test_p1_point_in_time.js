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

const TODAY = "2026-09-25";
const AS_OF = "2026-09-25T10:00:00Z";
const dateOffset = (days) => new Date(Date.parse(`${TODAY}T00:00:00Z`) + days * 86400000).toISOString().slice(0, 10);
const quote = (overrides = {}) => ({
  last: 10,
  bid: 9.5,
  ask: 10.5,
  volume: 10,
  openInterest: 100,
  quoteTime: AS_OF,
  ...overrides,
});
const makeChain = ({ quoteOverrides = {}, chainOverrides = {} } = {}) => ({
  tradeDate: TODAY,
  observedAt: AS_OF,
  session: "REGULAR",
  selectedExpiry: "M1",
  selectedExpiryDate: dateOffset(30),
  market: "TAIFEX",
  exchange: "TAIFEX",
  underlying: "TXO",
  decisionAsOf: AS_OF,
  source: { primary: "TAIFEX primary", mode: "taifex" },
  ...chainOverrides,
  chain: [90, 95, 100, 105, 110, 115].map((strike) => ({
    strike,
    call: quote(quoteOverrides.call?.[strike]),
    put: quote(quoteOverrides.put?.[strike]),
  })),
});
const makeMarket = (options = {}) => ({
  chain: makeChain(options),
  spot: 100,
  direction: "Bullish",
  futuresPct: 0.2,
  volumePcr: 1,
  maxPainGapPct: 0,
  expiryChains: [
    { expiryDate: dateOffset(15), chain: makeChain().chain },
    { expiryDate: dateOffset(45), chain: makeChain().chain },
  ],
});

const validMarket = makeMarket();
const envelope = engine.marketInputEnvelope(validMarket);
assert.strictEqual(envelope.source, "TAIFEX primary");
assert.strictEqual(envelope.sourceType, "PRIMARY");
assert.strictEqual(envelope.observedAt, AS_OF);
assert.strictEqual(envelope.tradeDate, TODAY);
assert.strictEqual(envelope.freshnessStatus, "FRESH");
assert.strictEqual(envelope.fallbackStatus, "NONE");
assert.strictEqual(envelope.marketIdentity.exchange, "TAIFEX");
assert.strictEqual(envelope.sessionIdentity, "REGULAR");
assert.strictEqual(envelope.decisionAsOf, AS_OF);
assert.strictEqual(envelope.decisionAsOfSource, "EXPLICIT");

const alignedModels = engine.analyze(validMarket);
assert.strictEqual(alignedModels.length, 13);
assert(alignedModels.every((model) => model.pointInTimeStatus === "ALIGNED"));
assert(alignedModels.every((model) => model.executionTrustStatus === "TRUSTED" && model.metrics.plTrustStatus === "TRUSTED"), "aligned inputs must retain execution/P&L trust");
assert(alignedModels.every((model) => model.legs.every((leg) => leg.marketInput.sessionIdentity === "REGULAR")), "all 13 strategies must carry leg input envelopes");

const sameDateDifferentSession = engine.analyze(makeMarket({ quoteOverrides: { call: { 100: { session: "OVERNIGHT" } } } }))[0];
assert.strictEqual(sameDateDifferentSession.pointInTimeStatus, "SESSION_MISMATCH");
assert.strictEqual(sameDateDifferentSession.executionTrustStatus, "UNTRUSTED");

const differentTradeDate = engine.analyze(makeMarket({ quoteOverrides: { call: { 100: { tradeDate: dateOffset(-1) } } } }))[0];
assert.strictEqual(differentTradeDate.pointInTimeStatus, "DIFFERENT_TRADE_DATE");
assert.strictEqual(differentTradeDate.metrics.executionGrade, "MODEL_ONLY");

const previousSession = makeMarket({ chainOverrides: { tradeDate: dateOffset(-1), freshnessStatus: "PREVIOUS_SESSION", cached: true, fallbackStatus: "CACHED_PREVIOUS_SESSION", provenanceType: "CACHED_PREVIOUS_SESSION" } });
const previousModel = engine.analyze(previousSession)[0];
assert.strictEqual(previousModel.pointInTimeStatus, "ALIGNED_PREVIOUS_SESSION");
assert.strictEqual(previousModel.marketInput.sourceType, "CACHED_PREVIOUS_SESSION");
assert.strictEqual(previousModel.executionTrustStatus, "UNTRUSTED");

const staleModel = engine.analyze(makeMarket({ chainOverrides: { freshnessStatus: "STALE", stale: true } }))[0];
assert.strictEqual(staleModel.pointInTimeStatus, "STALE_INPUT");
assert.strictEqual(staleModel.executionTrustStatus, "UNTRUSTED");

const missingTimestamp = makeMarket({ chainOverrides: { observedAt: null, tradeDate: null } });
missingTimestamp.chain.decisionAsOf = AS_OF;
missingTimestamp.chain.chain.forEach((group) => { group.call.quoteTime = null; group.put.quoteTime = null; });
const missingTimestampEnvelope = engine.marketInputEnvelope(missingTimestamp);
const missingTimestampPointInTime = engine.pointInTimeCheck([{ marketInput: missingTimestampEnvelope }], missingTimestamp);
assert.strictEqual(missingTimestampEnvelope.observedAtState, "MISSING_NULL");
assert.strictEqual(missingTimestampEnvelope.tradeDateState, "MISSING_NULL");
assert.strictEqual(missingTimestampPointInTime.status, "TIMESTAMP_UNAVAILABLE");

const missingTradeDate = makeMarket({ chainOverrides: { tradeDate: null } });
const missingTradeDateEnvelope = engine.marketInputEnvelope(missingTradeDate);
assert.strictEqual(missingTradeDateEnvelope.tradeDateState, "MISSING_NULL");
assert.strictEqual(missingTradeDateEnvelope.observedAtState, "PRESENT");

const primaryEnvelope = engine.marketInputEnvelope(validMarket);
const fallbackMarket = makeMarket({ chainOverrides: { fallbackFrom: "taifex", fallbackReason: "primary unavailable", provenanceType: "FALLBACK", fallbackStatus: "FALLBACK", source: { primary: "Yahoo fallback", mode: "auto-yahoo-fallback" } } });
const fallbackEnvelope = engine.marketInputEnvelope(fallbackMarket);
const cachedEnvelope = engine.marketInputEnvelope(makeMarket({ chainOverrides: { cached: true } }));
assert.strictEqual(primaryEnvelope.sourceType, "PRIMARY");
assert.strictEqual(fallbackEnvelope.sourceType, "FALLBACK");
assert.strictEqual(fallbackEnvelope.fallbackStatus, "FALLBACK");
assert.strictEqual(cachedEnvelope.sourceType, "CACHED");
assert.strictEqual(cachedEnvelope.fallbackStatus, "CACHED");
assert.strictEqual(fallbackEnvelope.source, "Yahoo fallback");

const mixedFreshStale = engine.analyze(makeMarket({ quoteOverrides: { call: { 100: { freshnessStatus: "STALE", stale: true } } } }))[0];
assert.strictEqual(mixedFreshStale.pointInTimeStatus, "MIXED_FRESH_STALE");
assert.strictEqual(mixedFreshStale.executionTrustStatus, "UNTRUSTED");

const mixedCurrentPrevious = engine.analyze(makeMarket({ quoteOverrides: { call: { 100: { tradeDate: dateOffset(-1), freshnessStatus: "PREVIOUS_SESSION" } } } }))[0];
assert.strictEqual(mixedCurrentPrevious.pointInTimeStatus, "DIFFERENT_TRADE_DATE");

const mixedPrimaryFallback = engine.analyze(makeMarket({ quoteOverrides: { call: { 100: { source: { primary: "fallback source" }, provenanceType: "FALLBACK", fallbackStatus: "FALLBACK" } } } }))[0];
assert.strictEqual(mixedPrimaryFallback.pointInTimeStatus, "PROVENANCE_MISMATCH");

const futureInput = engine.analyze(makeMarket({ quoteOverrides: { call: { 100: { tradeDate: dateOffset(1) } } } }))[0];
assert.strictEqual(futureInput.pointInTimeStatus, "FUTURE_DATA");
assert.strictEqual(futureInput.executionTrustStatus, "UNTRUSTED");

const decisionBeforeObservation = engine.analyze(makeMarket({ chainOverrides: { decisionAsOf: dateOffset(-1), observedAt: TODAY } }))[0];
assert.strictEqual(decisionBeforeObservation.pointInTimeStatus, "FUTURE_DATA");
const decisionEqualObservation = engine.analyze(makeMarket({ chainOverrides: { decisionAsOf: AS_OF, observedAt: AS_OF } }))[0];
assert.strictEqual(decisionEqualObservation.pointInTimeStatus, "ALIGNED");
const decisionAfterObservation = engine.analyze(makeMarket({ chainOverrides: { decisionAsOf: "2026-09-26T10:00:00Z", observedAt: AS_OF } }))[0];
assert.strictEqual(decisionAfterObservation.pointInTimeStatus, "ALIGNED");

const nullTimeEnvelope = engine.marketInputEnvelope(makeMarket({ chainOverrides: { observedAt: null } }));
const emptyTimeEnvelope = engine.marketInputEnvelope(makeMarket({ chainOverrides: { observedAt: "" } }));
const zeroTimeEnvelope = engine.marketInputEnvelope(makeMarket({ chainOverrides: { observedAt: 0 } }));
assert.strictEqual(nullTimeEnvelope.observedAtState, "MISSING_NULL");
assert.strictEqual(emptyTimeEnvelope.observedAtState, "MISSING_EMPTY");
assert.strictEqual(zeroTimeEnvelope.observedAtState, "INVALID_ZERO");

const alignedSpread = alignedModels.find((model) => model.id === "bull-call-spread");
assert.deepStrictEqual(JSON.parse(JSON.stringify(alignedSpread.legs.map((leg) => leg.marketInput.tradeDate))), [TODAY, TODAY]);
assert.strictEqual(alignedSpread.metrics.plTrustStatus, "TRUSTED");

console.log("P1_POINT_IN_TIME_OK: P1-11..P1-17 envelope, as-of, session, stale, provenance, mixed-as-of, future-data matrix");
