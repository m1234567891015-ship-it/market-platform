"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const acorn = require("acorn");

const ROOT = path.join(__dirname, "..");
const read = (relativePath) => fs.readFileSync(path.join(ROOT, relativePath), "utf8");
const parse = (source, filename) => acorn.parse(source, {
  ecmaVersion: "latest",
  sourceType: "script",
  locations: true,
  filename,
});

function isFunctionNode(node) {
  return node && ["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression"].includes(node.type);
}

function collectPatternNames(pattern, names) {
  if (!pattern) return;
  if (pattern.type === "Identifier") names.add(pattern.name);
  else if (pattern.type === "RestElement") collectPatternNames(pattern.argument, names);
  else if (pattern.type === "AssignmentPattern") collectPatternNames(pattern.left, names);
  else if (pattern.type === "ArrayPattern") pattern.elements.forEach((item) => collectPatternNames(item, names));
  else if (pattern.type === "ObjectPattern") {
    pattern.properties.forEach((property) => collectPatternNames(
      property.type === "RestElement" ? property.argument : property.value,
      names,
    ));
  }
}

function functionBindings(fn) {
  const names = new Set();
  fn.params.forEach((param) => collectPatternNames(param, names));
  if (fn.id) names.add(fn.id.name);

  function collect(node) {
    if (!node || typeof node !== "object") return;
    if (node !== fn && isFunctionNode(node)) {
      if (node.type === "FunctionDeclaration" && node.id) names.add(node.id.name);
      return;
    }
    if (node.type === "VariableDeclarator") collectPatternNames(node.id, names);
    else if (node.type === "ClassDeclaration" && node.id) names.add(node.id.name);
    else if (node.type === "CatchClause") collectPatternNames(node.param, names);
    for (const [key, value] of Object.entries(node)) {
      if (["start", "end", "loc", "range", "raw"].includes(key)) continue;
      if (Array.isArray(value)) value.forEach(collect);
      else if (value && typeof value === "object") collect(value);
    }
  }
  collect(fn.body);
  return names;
}

function isReference(identifier, parent, key) {
  if (!parent) return false;
  if (isFunctionNode(parent) && (key === "id" || key === "params")) return false;
  if (["VariableDeclarator", "FunctionDeclaration", "FunctionExpression", "ClassDeclaration", "ClassExpression"].includes(parent.type) && key === "id") return false;
  if ((parent.type === "MemberExpression" || parent.type === "OptionalMemberExpression") && key === "property" && !parent.computed) return false;
  if (parent.type === "Property" && key === "key" && !parent.computed && !parent.shorthand) return false;
  if (["MethodDefinition", "PropertyDefinition", "LabeledStatement", "BreakStatement", "ContinueStatement"].includes(parent.type) && key === "key" || ["LabeledStatement", "BreakStatement", "ContinueStatement"].includes(parent.type) && key === "label") return false;
  if (parent.type === "ImportSpecifier" || parent.type === "ImportDefaultSpecifier" || parent.type === "ImportNamespaceSpecifier") return false;
  return true;
}

function auditAmbientReferences(ast) {
  const prohibited = new Set(["data", "window", "globalThis"]);
  const accesses = [];
  const writes = [];
  let functionCount = 0;

  function visit(node, parent = null, key = null, functionScopes = []) {
    if (!node || typeof node !== "object") return;
    let scopes = functionScopes;
    if (isFunctionNode(node)) {
      functionCount += 1;
      scopes = [...functionScopes, functionBindings(node)];
    }
    if (node.type === "Identifier" && prohibited.has(node.name) && isReference(node, parent, key)) {
      const explicitlyBound = [...scopes].reverse().some((bindings) => bindings.has(node.name));
      const memberBase = (parent?.type === "MemberExpression" || parent?.type === "OptionalMemberExpression")
        && key === "object";
      if (!explicitlyBound && !memberBase) {
        const entry = { name: node.name, line: node.loc.start.line };
        accesses.push(entry);
        const directWrite = (parent?.type === "AssignmentExpression" && key === "left")
          || (parent?.type === "UpdateExpression" && key === "argument");
        if (directWrite) writes.push(entry);
      }
    }
    if ((node.type === "MemberExpression" || node.type === "OptionalMemberExpression")
      && node.object?.type === "Identifier" && prohibited.has(node.object.name)) {
      const explicitlyBound = [...scopes].reverse().some((bindings) => bindings.has(node.object.name));
      if (!explicitlyBound) {
        const entry = { name: node.object.name, line: node.object.loc.start.line };
        accesses.push(entry);
        if ((parent?.type === "AssignmentExpression" && key === "left" && parent.left === node)
          || (parent?.type === "UpdateExpression" && key === "argument" && parent.argument === node)) {
          writes.push(entry);
        }
      }
    }
    for (const [childKey, value] of Object.entries(node)) {
      if (["start", "end", "loc", "range", "raw"].includes(childKey)) continue;
      if (Array.isArray(value)) value.forEach((child) => visit(child, node, childKey, scopes));
      else if (value && typeof value === "object") visit(value, node, childKey, scopes);
    }
  }

  visit(ast);
  return { functionCount, accesses, writes };
}

function walk(node, visitor, parent = null) {
  if (!node || typeof node !== "object") return;
  if (typeof node.type === "string") visitor(node, parent);
  for (const [key, value] of Object.entries(node)) {
    if (["start", "end", "loc", "range", "raw"].includes(key)) continue;
    if (Array.isArray(value)) value.forEach((child) => walk(child, visitor, node));
    else if (value && typeof value === "object") walk(value, visitor, node);
  }
}

const sharedCalcSource = read("js/shared-calc.js");
const sharedCalcAst = parse(sharedCalcSource, "js/shared-calc.js");
const ambientAudit = auditAmbientReferences(sharedCalcAst);
assert.deepEqual(ambientAudit.accesses, [], "shared-calc calculation code must not use ambient data/window/globalThis");
assert.deepEqual(ambientAudit.writes, [], "shared-calc must not write ambient semantic state");

const frameworkNode = sharedCalcAst.body.find((node) => node.type === "FunctionDeclaration" && node.id?.name === "buildInstitutionalBacktestFramework");
assert(frameworkNode, "institutional backtest framework must remain in shared-calc");
assert(frameworkNode.params.some((param) => (
  param.type === "Identifier" && param.name === "marketContext"
) || (
  param.type === "AssignmentPattern" && param.left.type === "Identifier" && param.left.name === "marketContext"
)), "market context must be an explicit calculation input");
assert.match(sharedCalcSource, /marketContext\?\.marketInternationalIndexes/);
assert.match(sharedCalcSource, /marketContext\?\.marketMacroFactors/);
assert.match(sharedCalcSource, /marketContext\?\.marketVolatility/);
assert.match(sharedCalcSource, /marketContext\?\.marketOverview/);

const pageFiles = fs.readdirSync(path.join(ROOT, "js")).filter((name) => name.endsWith(".js"));
const callSites = [];
for (const name of pageFiles) {
  const relativePath = `js/${name}`;
  const ast = parse(read(relativePath), relativePath);
  walk(ast, (node) => {
    if (node.type !== "CallExpression" || node.callee.type !== "Identifier" || node.callee.name !== "analyzeTechnicalTheories") return;
    callSites.push({ relativePath, node });
  });
}
assert.equal(callSites.length, 6, "all six existing page callers must remain accounted for");
for (const { relativePath, node } of callSites) {
  const options = node.arguments[1];
  assert.equal(options?.type, "ObjectExpression", `${relativePath}:${node.loc.start.line}: options object required`);
  const marketBreadth = options.properties.find((property) => property.key?.name === "marketBreadth");
  const marketContext = options.properties.find((property) => property.key?.name === "marketContext");
  assert(marketBreadth, `${relativePath}:${node.loc.start.line}: explicit marketBreadth required`);
  assert(marketContext, `${relativePath}:${node.loc.start.line}: explicit marketContext required`);
  assert.equal(marketContext.value.type, "MemberExpression");
  assert.equal(marketContext.value.object.name, "marketBreadthContext");
  assert.equal(marketContext.value.property.name, "marketContext");
}

const historicalContext = {
  marketInternationalIndexes: [
    { key: "sox", name: "SOX Semiconductor", pct: 1.2, value: 5000 },
    { key: "nasdaq", name: "NASDAQ", pct: 0.8, value: 18000 },
    { key: "sp500", name: "S&P 500", pct: 0.5, value: 5500 },
    { key: "russell", name: "Russell 2000", pct: 0.3, value: 2100 },
    { key: "vix", name: "VIX", pct: -2, value: 16 },
  ],
  marketMacroFactors: {
    dxy: { pct: -0.2 },
    us10y: { pct: -0.1 },
    usdTwd: { pct: 0.1 },
    txOpenInterest: { changePct: 1.5 },
    marginTrading: { financingChangePct: 1, shortChangePct: -1 },
  },
  marketVolatility: { pct: -2, value: 16 },
  marketOverview: [{ name: "加權指數", pct: 0.4 }],
};
const unrelatedCurrentContext = {
  marketInternationalIndexes: [
    { key: "sox", name: "SOX Semiconductor", pct: -4, value: 4200 },
    { key: "nasdaq", name: "NASDAQ", pct: -2, value: 17000 },
    { key: "sp500", name: "S&P 500", pct: -1.5, value: 5200 },
    { key: "russell", name: "Russell 2000", pct: -2, value: 1900 },
    { key: "vix", name: "VIX", pct: 8, value: 38 },
  ],
  marketMacroFactors: {
    dxy: { pct: 1 },
    us10y: { pct: 0.8 },
    usdTwd: { pct: 1.5 },
    txOpenInterest: { changePct: -4 },
    marginTrading: { financingChangePct: 5, shortChangePct: 4 },
  },
  marketVolatility: { pct: 8, value: 38 },
  marketOverview: [{ name: "加權指數", pct: -2 }],
};
const partialContext = {
  marketInternationalIndexes: [{ key: "sox", name: "SOX Semiconductor", pct: 1.2, value: 5000 }],
  marketMacroFactors: {},
  marketVolatility: null,
  marketOverview: [],
};
const invalidContext = {
  marketInternationalIndexes: [{ key: "sox", name: "SOX Semiconductor", pct: "not-a-number", value: "invalid" }],
  marketMacroFactors: { dxy: { pct: "invalid" } },
  marketVolatility: null,
  marketOverview: [],
};

const storage = { getItem: () => null, setItem: () => {} };
const sandbox = {
  console,
  Math,
  Date,
  Number,
  Array,
  Object,
  Map,
  Set,
  JSON,
  Element: function Element() {},
  localStorage: storage,
  sessionStorage: storage,
  window: { TWSE_DATA: historicalContext, TWSE_ALL_STOCKS: [] },
};
vm.createContext(sandbox);
for (const relativePath of ["js/state.js", "js/core.js", "js/shared-calc.js"]) {
  vm.runInContext(read(relativePath), sandbox, { filename: relativePath });
}

const history = Array.from({ length: 260 }, (_, index) => {
  const close = 100 + (index * 0.08) + (Math.sin(index / 9) * 2.5);
  const previous = index
    ? 100 + ((index - 1) * 0.08) + (Math.sin((index - 1) / 9) * 2.5)
    : close;
  return {
    date: new Date(Date.UTC(2025, 0, index + 1)).toISOString().slice(0, 10),
    open: close * 0.995,
    high: Math.max(close, previous) * 1.01,
    low: Math.min(close, previous) * 0.99,
    close,
    volume: 100000 + ((index % 11) * 1000),
  };
});
const detail = {
  name: "半導體測試",
  industry: "半導體",
  category: "電子",
  market: "TW",
  symbol: "TEST",
  institutionalTrades: { totalValue: 1000000, foreignValue: 500000 },
  shareholderDistribution: { largeHolderRatio: 55 },
  historyDays: history,
};
const backtestLearning = { signals: [], validation: null };
const normalize = (value) => JSON.parse(JSON.stringify(value));
const buildFramework = (marketContext) => normalize(
  sandbox.buildInstitutionalBacktestFramework(detail, history, backtestLearning, marketContext),
);
const setAmbientData = (value) => vm.runInContext(`data = ${JSON.stringify(value)}`, sandbox);

sandbox.__p402Detail = detail;
const adapterContext = vm.runInContext(
  "twEtfState.getMarketBreadthContext(__p402Detail).marketContext",
  sandbox,
);
assert.deepEqual(normalize(adapterContext), normalize(historicalContext), "state adapter must expose current market inputs explicitly");

const frameworkA = buildFramework(adapterContext);
assert.equal(frameworkA.totalScore, 59, "market formula output remains compatible for the accepted fixture");
assert.equal(frameworkA.marketState, "Neutral");
assert.equal(frameworkA.coverage, 100);
assert.ok(Math.abs(frameworkA.layers.find((layer) => layer.key === "market").score - 56.607142857142854) < 1e-12);
assert.deepEqual(frameworkA.judgement, {
  label: "觀望",
  tone: "neutral",
  action: "多空因子未形成明確共振，控制部位並等待方向確認。",
});

setAmbientData(unrelatedCurrentContext);
const frameworkWithDifferentAmbientState = buildFramework(historicalContext);
assert.deepEqual(frameworkWithDifferentAmbientState, frameworkA, "fixed explicit inputs must ignore changed ambient market state");
const bearishFramework = buildFramework(unrelatedCurrentContext);
assert(
  bearishFramework.layers.find((layer) => layer.key === "market").score < frameworkA.layers.find((layer) => layer.key === "market").score,
  "a relevant explicit-input change must affect the market layer",
);
assert.equal(bearishFramework.marketState, "Risk-Off");

const missingContextA = buildFramework(undefined);
assert.equal(missingContextA.layers.find((layer) => layer.key === "market").score, 50);
assert.equal(missingContextA.layers.find((layer) => layer.key === "market").coverage, 0);
assert.equal(missingContextA.layers.find((layer) => layer.key === "market").available.length, 0);
setAmbientData(historicalContext);
const missingContextB = buildFramework(null);
assert.deepEqual(missingContextB, missingContextA, "missing context must preserve the existing unavailable-layer behavior without global fallback");
assert.deepEqual(buildFramework(), missingContextA, "omitted context must match the established missing-data contract");

const partialFramework = buildFramework(partialContext);
assert.equal(partialFramework.layers.find((layer) => layer.key === "market").available.length, 1);
assert.equal(partialFramework.layers.find((layer) => layer.key === "market").coverage, 1 / 8);
const invalidFramework = buildFramework(invalidContext);
assert.equal(invalidFramework.layers.find((layer) => layer.key === "market").available.length, 0);
assert.equal(invalidFramework.layers.find((layer) => layer.key === "market").coverage, 0);

const analyzerResultA = normalize(sandbox.analyzeTechnicalTheories(detail, {
  marketBreadth: null,
  marketContext: historicalContext,
}));
setAmbientData(unrelatedCurrentContext);
const analyzerResultB = normalize(sandbox.analyzeTechnicalTheories(detail, {
  marketBreadth: null,
  marketContext: historicalContext,
}));
assert.deepEqual(analyzerResultB, analyzerResultA, "historical analysis must ignore unrelated current/global market state");
assert.equal(analyzerResultA.backtestLearning.institutionalFramework.totalScore, 59);
assert.equal(analyzerResultA.score, -5);
assert.equal(analyzerResultA.evidenceCount, 29);

const replayBacktestA = normalize(sandbox.buildBacktestLearningModel(history, 20));
setAmbientData(historicalContext);
const replayBacktestB = normalize(sandbox.buildBacktestLearningModel(history, 20));
assert.deepEqual(replayBacktestB, replayBacktestA, "same explicit historical OHLCV input must yield the same backtest result");
assert.equal(JSON.stringify(buildFramework(historicalContext)), JSON.stringify(buildFramework(historicalContext)), "repeated calculation output must be structurally deterministic");

const contractSha256 = crypto.createHash("sha256")
  .update(read("docs/P4_02_SHARED_CALC_HIDDEN_GLOBAL_STATE_CONTRACT.md"))
  .digest("hex");
const auditedSourceFiles = [...new Set([
  "js/state.js",
  "js/shared-calc.js",
  ...callSites.map(({ relativePath }) => relativePath),
])].sort();
const sourceSha256 = crypto.createHash("sha256")
  .update(auditedSourceFiles.map((relativePath) => `${relativePath}\0${read(relativePath)}`).join("\0"))
  .digest("hex");
const resultIdentity = {
  contractSha256,
  sourceSha256,
  functionsAudited: ambientAudit.functionCount,
  hiddenSemanticAccessesBefore: 6,
  hiddenSemanticAccessesAfter: ambientAudit.accesses.length,
  affectedCalculationFunctions: 1,
  updatedCallers: callSites.length,
  semanticGlobalWrites: ambientAudit.writes.length,
  totalScore: frameworkA.totalScore,
  marketLayer: frameworkA.layers.find((layer) => layer.key === "market").score,
  marketCoverage: frameworkA.layers.find((layer) => layer.key === "market").coverage,
  technicalScore: analyzerResultA.score,
  technicalEvidenceCount: analyzerResultA.evidenceCount,
  backtestSignalCount: replayBacktestA.signals.length,
  hiddenAmbientReferencesAfter: ambientAudit.accesses.length,
  hiddenAmbientWritesAfter: ambientAudit.writes.length,
  productionCallers: callSites.length,
};
const fingerprint = crypto.createHash("sha256").update(JSON.stringify(resultIdentity)).digest("hex");
console.log(JSON.stringify({
  P4_02_AUDIT: {
    contractId: "P4_02_SHARED_CALC_EXPLICIT_INPUT_V1",
    contractSha256,
    sourceSha256,
    functionsAudited: ambientAudit.functionCount,
    hiddenSemanticAccessesBefore: 6,
    hiddenSemanticAccessesAfter: ambientAudit.accesses.length,
    affectedCalculationFunctions: 1,
    updatedCallers: callSites.length,
    justifiedAmbientAccessesInCalculation: 0,
    semanticGlobalWrites: ambientAudit.writes.length,
    noContextCoverage: missingContextA.layers.find((layer) => layer.key === "market").coverage,
    replayAndBacktest: "PASS",
    fingerprint,
  },
}));
