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

assert.strictEqual(engine.contracts.length, 13, "exactly 13 contracts are required");
assert.strictEqual(JSON.stringify(engine.contracts.map((item) => item.name)), JSON.stringify([
  "Long Straddle", "Long Strangle", "Short Straddle", "Short Strangle",
  "Bull Call Spread", "Bear Call Spread", "Bull Put Spread", "Bear Put Spread",
  "Long Condor", "Short Condor", "Call Butterfly", "Put Butterfly", "Calendar Spread",
]));

const buy = (optionType, strike, premium, quantity = 1) => ({ side: "BUY", optionType, strike, premium, quantity });
const sell = (optionType, strike, premium, quantity = 1) => ({ side: "SELL", optionType, strike, premium, quantity });
const cases = [
  ["long-straddle", [buy("call", 100, 5), buy("put", 100, 4)], ["below", "at", "above"]],
  ["long-strangle", [buy("put", 95, 3), buy("call", 105, 3)], ["below", "at", "between", "above"]],
  ["short-straddle", [sell("call", 100, 5), sell("put", 100, 4)], ["below", "at", "above"]],
  ["short-strangle", [sell("put", 95, 3), sell("call", 105, 3)], ["below", "at", "between", "above"]],
  ["bull-call-spread", [buy("call", 100, 5), sell("call", 110, 2)], ["below", "at", "between", "at-high", "above"]],
  ["bear-call-spread", [sell("call", 100, 5), buy("call", 110, 2)], ["below", "at", "between", "at-high", "above"]],
  ["bull-put-spread", [buy("put", 90, 2), sell("put", 100, 5)], ["below", "at", "between", "at-high", "above"]],
  ["bear-put-spread", [sell("put", 90, 2), buy("put", 100, 5)], ["below", "at", "between", "at-high", "above"]],
  ["long-condor", [buy("call", 90, 8), sell("call", 100, 4), sell("call", 110, 3), buy("call", 120, 1)], ["below", "at", "between", "at-high", "above"]],
  ["short-condor", [sell("call", 90, 8), buy("call", 100, 4), buy("call", 110, 3), sell("call", 120, 1)], ["below", "at", "between", "at-high", "above"]],
  ["call-butterfly", [buy("call", 90, 8), sell("call", 100, 2, 2), buy("call", 110, 1)], ["below", "at", "between", "at-high", "above"]],
  ["put-butterfly", [buy("put", 90, 1), sell("put", 100, 2, 2), buy("put", 110, 8)], ["below", "at", "between", "at-high", "above"]],
];
const testPrices = [80, 90, 95, 100, 105, 110, 120, 130];
for (const [id, legs, labels] of cases) {
  assert(labels.length >= 3, `${id} must cover below/at/between/at-high/above regimes`);
  for (const price of testPrices) assert(Number.isFinite(engine.payoff(legs, price)), `${id} payoff must be finite at ${price}`);
  const result = engine.metrics(legs);
  assert(result.exactPayoffAvailable, `${id} must use the exact single-expiry payoff engine`);
  assert(result.breakEven.length >= 1, `${id} must expose a break-even result`);
}
assert.strictEqual(JSON.stringify(engine.metrics(cases[0][1]).breakEven.map((value) => Number(value.toFixed(6)))), JSON.stringify([91, 109]));
assert.strictEqual(JSON.stringify(engine.metrics(cases[4][1]).breakEven.map((value) => Number(value.toFixed(6)))), JSON.stringify([103]));

const dateOffset = (days) => new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);
const quote = (price) => ({ last: price, bid: price - 0.2, ask: price + 0.2, volume: 10, openInterest: 100 });
const makeChain = (overrides = {}) => ({
  tradeDate: dateOffset(0),
  selectedExpiry: "M1",
  selectedExpiryDate: dateOffset(30),
  source: { primary: "test fixture" },
  chain: [90, 95, 100, 105, 110, 115].map((strike) => ({ strike, call: quote(12 - (strike - 90) / 10), put: quote(2 + (strike - 90) / 10), ...overrides[strike] })),
});
const validMarket = { chain: makeChain(), spot: 100, direction: "Bullish", futuresPct: 0.2, volumePcr: 1, maxPainGapPct: 0 };
const analyzed = engine.analyze(validMarket);
assert.strictEqual(analyzed.length, 13);
assert(analyzed.slice(0, 12).every((model) => model.available), "all single-expiry strategies should be selectable from a complete chain");
assert(analyzed[12].available === false && /雙到期日/.test(analyzed[12].reason), "calendar must fail closed without a second actual expiry chain");

const expiryChains = [
  { expiryDate: dateOffset(15), chain: makeChain().chain },
  { expiryDate: dateOffset(45), chain: makeChain().chain.map((group) => ({ ...group, call: quote(10), put: quote(4) })) },
];
const calendar = engine.analyze({ ...validMarket, expiryChains })[12];
assert(calendar.available && calendar.calendar, "calendar requires two actual expiry chains");
assert.strictEqual(calendar.metrics.exactPayoffAvailable, false);
assert(/Model Dependent/.test(calendar.metrics.maxProfitLabel));

const unavailable = (mutator, message) => {
  const model = engine.analyze(mutator(JSON.parse(JSON.stringify(validMarket))))[0];
  assert.strictEqual(model.available, false, message);
  assert(/策略合約|缺失|缺少|過舊|未驗證|資料/.test(model.reason), `${message}: reason must be explicit`);
};
unavailable((market) => { market.chain.chain = []; return market; }, "missing chain must fail closed");
unavailable((market) => { market.chain.selectedExpiryDate = ""; return market; }, "missing expiry must fail closed");
unavailable((market) => { market.chain.chain.forEach((group) => { group.strike = "malformed"; }); return market; }, "malformed strike must fail closed");
unavailable((market) => { market.chain.chain.forEach((group) => { group.call.last = null; group.call.bid = null; group.call.ask = null; group.put.last = null; group.put.bid = null; group.put.ask = null; }); return market; }, "missing premium must fail closed");
unavailable((market) => { market.chain.chain.forEach((group) => { delete group.call.volume; delete group.call.openInterest; delete group.put.volume; delete group.put.openInterest; }); return market; }, "missing liquidity must fail closed");

console.log("OPTIONS_STRATEGY_ANALYZER_OK: 13 contracts, 12 payoff suites, calendar, BE, fail-closed");
