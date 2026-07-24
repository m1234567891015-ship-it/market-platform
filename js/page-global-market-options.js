function renderDerivativesOptionsPanel(payload) {
  const chain = payload.taiwanOptionChain || {};
  return `
    <section class="section" id="options-chain">
      <article class="panel-card asset-hub-summary-card"><div class="card-title-row"><div><p class="panel-kicker">LocalStorage watchlist</p><h3>TXO 自選商品</h3><p class="chart-subtitle">自選只保存在目前瀏覽器，不需登入，也不會送到伺服器。</p></div><div class="asset-hub-summary-actions">${renderDerivativeWatchButton("TXO", "臺指選擇權", "option")}</div></div></article>
      <div class="asset-hub-layout asset-hub-options-layout">
        ${renderTaiwanOptionChainCard(chain)}
        ${renderTaiwanOptionAnalysis(chain)}
      </div>
    </section>
  `;
}
function getTaiwanOptionProducts(chain = {}) {
  const products = Array.isArray(chain.availableProducts) && chain.availableProducts.length
    ? chain.availableProducts
    : TAIWAN_OPTION_PRODUCT_FALLBACKS;
  return products.map((item) => ({
    symbol: String(item.symbol || "").toUpperCase(),
    name: item.name || item.symbol || "--",
    shortName: item.shortName || item.name || item.symbol || "--",
  })).filter((item) => item.symbol);
}
function getActiveTaiwanOptionUnderlying(chain = {}) {
  return String(chain.underlying || derivativesOptionsSelectedUnderlying || "TXO").toUpperCase();
}
function getTaiwanOptionProductLabel(chain = {}) {
  const active = getActiveTaiwanOptionUnderlying(chain);
  const product = getTaiwanOptionProducts(chain).find((item) => item.symbol === active);
  return product?.shortName || chain.shortName || chain.name || active;
}
function renderTaiwanOptionProductTabs(chain = {}) {
  const products = getTaiwanOptionProducts(chain);
  const active = getActiveTaiwanOptionUnderlying(chain);
  return `
    <div class="tw-option-product-tabs" aria-label="市場選擇權商品切換">
      ${products.map((item) => `
        <button class="${item.symbol === active ? "is-active" : ""}" type="button" data-tw-option-product="${escapeHtml(item.symbol)}" aria-pressed="${item.symbol === active ? "true" : "false"}">
          <b>${escapeHtml(item.shortName)}</b>
          <small>${escapeHtml(item.symbol)}</small>
        </button>
      `).join("")}
    </div>
  `;
}
function getOptionsChainRows(chain = {}) {
  return Array.isArray(chain.chain) ? chain.chain : [];
}
function getOptionsDistributionRows(chain = {}) {
  return Array.isArray(chain.distribution) && chain.distribution.length
    ? chain.distribution
    : getOptionsChainRows(chain).map((row) => ({
      strike: row.strike,
      callOpenInterest: row.call?.openInterest,
      putOpenInterest: row.put?.openInterest,
      callVolume: row.call?.volume,
      putVolume: row.put?.volume,
    }));
}
function getOptionsIvValues(chain = {}) {
  return getOptionsChainRows(chain)
    .flatMap((row) => [row.call?.impliedVolatility, row.put?.impliedVolatility])
    .map(Number)
    .filter((value) => Number.isFinite(value) && value > 0);
}
function getOptionsDaysToExpiry(chain = {}) {
  const dateText = chain.selectedExpiryDate || chain.expiryDate || "";
  if (!dateText) return null;
  const expiry = new Date(`${dateText}T13:30:00+08:00`);
  if (Number.isNaN(expiry.getTime())) return null;
  const days = Math.ceil((expiry.getTime() - Date.now()) / 86400000);
  return Number.isFinite(days) ? Math.max(days, 0) : null;
}
function getOptionsMaxOiWalls(chain = {}) {
  const rows = getOptionsDistributionRows(chain);
  const callWall = rows
    .map((row) => ({ strike: optionsNumber(row.strike), value: optionsNumber(row.callOpenInterest) || 0 }))
    .filter((row) => row.strike !== null && row.value > 0)
    .sort((left, right) => right.value - left.value)[0] || null;
  const putWall = rows
    .map((row) => ({ strike: optionsNumber(row.strike), value: optionsNumber(row.putOpenInterest) || 0 }))
    .filter((row) => row.strike !== null && row.value > 0)
    .sort((left, right) => right.value - left.value)[0] || null;
  return { callWall, putWall };
}
function normalizeOptionsOiRow(row = {}) {
  const call = row.call || {};
  const put = row.put || {};
  const strike = optionsNumber(row.strike);
  return {
    strike,
    callOpenInterest: optionsNumber(row.callOpenInterest ?? call.openInterest) || 0,
    putOpenInterest: optionsNumber(row.putOpenInterest ?? put.openInterest) || 0,
    callVolume: optionsNumber(row.callVolume ?? call.volume) || 0,
    putVolume: optionsNumber(row.putVolume ?? put.volume) || 0,
  };
}
function getOptionsLocalOiWalls(rows = []) {
  const normalized = rows.map(normalizeOptionsOiRow).filter((row) => row.strike !== null);
  const callWall = normalized
    .map((row) => ({ strike: row.strike, value: row.callOpenInterest }))
    .filter((row) => row.value > 0)
    .sort((left, right) => right.value - left.value)[0] || null;
  const putWall = normalized
    .map((row) => ({ strike: row.strike, value: row.putOpenInterest }))
    .filter((row) => row.value > 0)
    .sort((left, right) => right.value - left.value)[0] || null;
  return { callWall, putWall };
}
function calculateOptionsLocalMaxPain(rows = []) {
  const normalized = rows.map(normalizeOptionsOiRow).filter((row) => row.strike !== null);
  if (!normalized.some((row) => row.callOpenInterest > 0 || row.putOpenInterest > 0)) {
    return null;
  }
  let bestStrike = null;
  let bestLoss = null;
  normalized.forEach((candidate) => {
    const loss = normalized.reduce((sum, row) => {
      const callLoss = row.callOpenInterest * Math.max(0, candidate.strike - row.strike);
      const putLoss = row.putOpenInterest * Math.max(0, row.strike - candidate.strike);
      return sum + callLoss + putLoss;
    }, 0);
    if (bestLoss === null || loss < bestLoss) {
      bestLoss = loss;
      bestStrike = candidate.strike;
    }
  });
  return bestStrike === null ? null : { strike: bestStrike, loss: bestLoss };
}
function optionsOiWhole(value) {
  const parsed = optionsNumber(value);
  return parsed === null || parsed <= 0 ? "--" : optionsWhole(parsed);
}
function sumOptionFinite(values = []) {
  return values.reduce((sum, value) => {
    const parsed = optionsNumber(value);
    return parsed === null ? sum : sum + parsed;
  }, 0);
}
function findOptionsExtraItem(extras = {}, symbols = []) {
  const payloads = [extras.usStocks, extras.futures, extras.bonds, extras.preciousMetals].filter(Boolean);
  for (const payload of payloads) {
    const found = findAssetHubItemAny(payload, symbols);
    if (found) return found;
  }
  return null;
}
function buildOptionsHiddenDecisionFactors({ vix, vixValue, dxy, us10y, gold, oil } = {}) {
  const factor = (key, name, item, move, ready, pressure, bias, note) => ({
    key,
    name,
    item: item || null,
    value: key === "vix" && Number.isFinite(vixValue) ? vixValue : parseMarketNumber(item?.close),
    move,
    ready: Boolean(ready),
    pressure,
    bias,
    note,
  });
  const dxyMove = parseMarketNumber(dxy?.pct);
  const rateMove = parseMarketNumber(us10y?.pct);
  const goldMove = parseMarketNumber(gold?.pct);
  const oilMove = parseMarketNumber(oil?.pct);
  const vixMove = parseMarketNumber(vix?.pct);
  const vixReady = Number.isFinite(vixValue);
  const vixHigh = vixReady && vixValue >= 22;
  const vixLow = vixReady && vixValue < 18;
  const factors = [
    factor(
      "vix",
      "VIX",
      vix,
      Number.isFinite(vixMove) ? vixMove : null,
      vixReady,
      vixHigh || (Number.isFinite(vixMove) && vixMove > 3) ? 8 : vixLow && (!Number.isFinite(vixMove) || vixMove <= 0) ? -3 : 0,
      vixHigh || (Number.isFinite(vixMove) && vixMove > 3) ? -0.75 : vixLow && (!Number.isFinite(vixMove) || vixMove <= 0) ? 0.35 : 0,
      vixHigh ? "波動率偏高，權利金與避險需求升溫。" : vixLow ? "波動率偏低，方向交易壓力較小。" : "波動率中性，需搭配 OI 牆確認。",
    ),
    factor(
      "dxy",
      "美元指數",
      dxy,
      Number.isFinite(dxyMove) ? dxyMove : null,
      Boolean(dxy && Number.isFinite(parseMarketNumber(dxy.close))),
      Number.isFinite(dxyMove) && dxyMove > 0.25 ? 5 : Number.isFinite(dxyMove) && dxyMove < -0.25 ? -2 : 0,
      Number.isFinite(dxyMove) && dxyMove > 0.25 ? -0.38 : Number.isFinite(dxyMove) && dxyMove < -0.25 ? 0.22 : 0,
      Number.isFinite(dxyMove) && dxyMove > 0.25 ? "美元走強，風險資產承壓。" : Number.isFinite(dxyMove) && dxyMove < -0.25 ? "美元轉弱，外部壓力緩和。" : "美元變動有限。",
    ),
    factor(
      "us10y",
      "10Y 利率",
      us10y,
      Number.isFinite(rateMove) ? rateMove : null,
      Boolean(us10y && Number.isFinite(parseMarketNumber(us10y.close))),
      Number.isFinite(rateMove) && rateMove > 0.08 ? 5 : Number.isFinite(rateMove) && rateMove < -0.08 ? -2 : 0,
      Number.isFinite(rateMove) && rateMove > 0.08 ? -0.34 : Number.isFinite(rateMove) && rateMove < -0.08 ? 0.2 : 0,
      Number.isFinite(rateMove) && rateMove > 0.08 ? "利率壓力上升，科技與成長股敏感度提高。" : Number.isFinite(rateMove) && rateMove < -0.08 ? "利率壓力緩和，估值壓力下降。" : "利率變動有限。",
    ),
    factor(
      "gold",
      "黃金",
      gold,
      Number.isFinite(goldMove) ? goldMove : null,
      Boolean(gold && Number.isFinite(parseMarketNumber(gold.close))),
      Number.isFinite(goldMove) && goldMove > 0.3 && vixHigh ? 6 : Number.isFinite(goldMove) && goldMove > 0.3 ? 2 : 0,
      Number.isFinite(goldMove) && goldMove > 0.3 && vixHigh ? -0.26 : Number.isFinite(goldMove) && goldMove < -0.3 && !vixHigh ? 0.14 : 0,
      Number.isFinite(goldMove) && goldMove > 0.3 && vixHigh ? "黃金與 VIX 同步偏強，避險訊號升高。" : "黃金作為避險校正因子。",
    ),
    factor(
      "oil",
      "原油",
      oil,
      Number.isFinite(oilMove) ? oilMove : null,
      Boolean(oil && Number.isFinite(parseMarketNumber(oil.close))),
      Number.isFinite(oilMove) && oilMove > 0.5 ? 4 : Number.isFinite(oilMove) && oilMove < -0.5 ? -1 : 0,
      Number.isFinite(oilMove) && oilMove > 0.5 ? -0.22 : Number.isFinite(oilMove) && oilMove < -0.5 ? 0.12 : 0,
      Number.isFinite(oilMove) && oilMove > 0.5 ? "油價上行，通膨與成本壓力提高。" : Number.isFinite(oilMove) && oilMove < -0.5 ? "油價回落，通膨壓力稍緩。" : "油價變動有限。",
    ),
  ];
  const readyFactors = factors.filter((item) => item.ready);
  const pressureScore = readyFactors.reduce((sum, item) => sum + item.pressure, 0);
  const biasScore = readyFactors.reduce((sum, item) => sum + item.bias, 0);
  const dominant = readyFactors
    .slice()
    .sort((left, right) => Math.abs(right.pressure) + Math.abs(right.bias) - Math.abs(left.pressure) - Math.abs(left.bias))[0] || null;
  const riskAdjustment = Math.round(clampAssetHubScore(pressureScore, -8, 22));
  const directionBias = clampAssetHubScore(biasScore, -1.6, 1.6);
  const summary = dominant
    ? `${dominant.name} 為目前最主要外部校正因子；${dominant.note}`
    : "外部決策因子同步中，AI 以選擇權鏈與 OI 資料為主。";
  return {
    factors,
    readyCount: readyFactors.length,
    totalCount: factors.length,
    riskAdjustment,
    directionBias,
    dominant,
    summary,
  };
}
function buildOptionsAiFunctionalModel(payload = {}) {
  const items = getAssetHubItems(payload);
  const usable = getAssetHubUsableItems(payload);
  const chain = payload.taiwanOptionChain || {};
  const summary = chain.summary || {};
  const rows = getOptionsChainRows(chain);
  const distribution = getOptionsDistributionRows(chain);
  const ivValues = getOptionsIvValues(chain);
  const avgIv = ivValues.length ? ivValues.reduce((sum, value) => sum + value, 0) / ivValues.length : null;
  const maxIv = ivValues.length ? Math.max(...ivValues) : null;
  const minIv = ivValues.length ? Math.min(...ivValues) : null;
  const pcr = optionsNumber(summary.putCallRatio);
  const volumePcr = optionsNumber(summary.volumePutCallRatio);
  const callOi = optionsNumber(summary.callOpenInterest);
  const putOi = optionsNumber(summary.putOpenInterest);
  const maxPain = optionsNumber(summary.maxPain);
  const atmStrike = optionsNumber(summary.atmStrike);
  const maxPainGap = atmStrike !== null && maxPain !== null ? atmStrike - maxPain : null;
  const expiryDays = getOptionsDaysToExpiry(chain);
  const oiWalls = getOptionsMaxOiWalls(chain);
  const vix = findAssetHubItemAny(payload, ["^VIX", "VIX", "VIXY"]);
  const vixValue = parseMarketNumber(vix?.close);
  const extras = payload.optionsAiExtras || {};
  const sp500 = findOptionsExtraItem(extras, ["^GSPC", "SPY"]);
  const nasdaq = findOptionsExtraItem(extras, ["^IXIC", "QQQ", "NQ=F"]);
  const dxy = findOptionsExtraItem(extras, ["DX-Y.NYB", "DXY"]);
  const us10y = findOptionsExtraItem(extras, ["ZN=F", "US10Y", "10Y"]);
  const gold = findOptionsExtraItem(extras, ["GC=F", "XAU"]);
  const oil = findOptionsExtraItem(extras, ["CL=F", "BZ=F"]);
  const macroItems = [sp500, nasdaq, dxy, us10y, gold, oil].filter(Boolean);
  const decisionFactors = buildOptionsHiddenDecisionFactors({ vix, vixValue, dxy, us10y, gold, oil });
  const pcrPressure = pcr !== null ? Math.min(Math.abs(pcr - 1) * 24, 26) : 8;
  const volumePressure = volumePcr !== null ? Math.min(Math.abs(volumePcr - 1) * 14, 18) : 5;
  const vixPressure = Number.isFinite(vixValue) ? Math.max(0, vixValue - 16) * 1.8 : 8;
  const ivPressure = avgIv !== null ? Math.max(0, avgIv * 100 - 18) * 1.15 : 5;
  const expiryPressure = expiryDays !== null && expiryDays <= 5 ? 8 : expiryDays !== null && expiryDays <= 12 ? 4 : 0;
  const gapPressure = maxPainGap !== null && atmStrike ? Math.min(Math.abs(maxPainGap / atmStrike) * 420, 10) : 4;
  const riskScore = Math.round(clampAssetHubScore(28 + pcrPressure + volumePressure + vixPressure + ivPressure + expiryPressure + gapPressure + decisionFactors.riskAdjustment, 12, 96));
  const confidenceScore = Math.round(clampAssetHubScore(
    34
      + (rows.length ? 14 : 0)
      + (distribution.length ? 10 : 0)
      + (pcr !== null ? 10 : 0)
      + (vix ? 8 : 0)
      + (ivValues.length ? 8 : 0)
      + Math.min(decisionFactors.readyCount * 3, 12)
      + Math.min(macroItems.length * 4, 16),
    22,
    96,
  ));
  const bullishRaw = 32
    + (pcr !== null && pcr < 0.9 ? 12 : 0)
    + (volumePcr !== null && volumePcr < 0.9 ? 8 : 0)
    + (Number.isFinite(vixValue) && vixValue < 18 ? 10 : 0)
    + (callOi !== null && putOi !== null && callOi > putOi ? 6 : 0)
    + Math.max(0, decisionFactors.directionBias) * 8
    - (riskScore > 70 ? 10 : 0);
  const bearishRaw = 30
    + (pcr !== null && pcr > 1.1 ? 12 : 0)
    + (volumePcr !== null && volumePcr > 1.1 ? 8 : 0)
    + (Number.isFinite(vixValue) && vixValue > 22 ? 12 : 0)
    + (putOi !== null && callOi !== null && putOi > callOi ? 6 : 0)
    + Math.max(0, -decisionFactors.directionBias) * 9;
  const chopRaw = 28
    + (Math.abs((pcr || 1) - 1) < 0.12 ? 10 : 0)
    + (expiryDays !== null && expiryDays <= 7 ? 4 : 0)
    + (Math.abs(decisionFactors.directionBias) < 0.24 ? 4 : 0);
  const totalProb = Math.max(bullishRaw + bearishRaw + chopRaw, 1);
  const probabilities = {
    bullish: Math.round(bullishRaw / totalProb * 100),
    bearish: Math.round(bearishRaw / totalProb * 100),
  };
  probabilities.range = Math.max(0, 100 - probabilities.bullish - probabilities.bearish);
  const riskLight = riskScore >= 82
    ? { label: "紅燈", tone: "red", text: "極端風險或重大波動環境" }
    : riskScore >= 66
      ? { label: "橘燈", tone: "orange", text: "高風險，需控管槓桿與到期日" }
      : riskScore >= 48
        ? { label: "黃燈", tone: "yellow", text: "需留意波動與 OI 變化" }
        : { label: "綠燈", tone: "green", text: "風險正常，等待訊號確認" };
  const direction = probabilities.bullish > probabilities.bearish + 8
    ? "偏多"
    : probabilities.bearish > probabilities.bullish + 8
      ? "偏空"
      : "震盪";
  const primaryRisk = riskScore >= 66
    ? "波動率與避險需求偏高"
    : expiryDays !== null && expiryDays <= 7
      ? "到期週 Gamma / Theta 變化"
      : "區間壓力與未平倉牆";
  return {
    payload,
    items,
    usable,
    chain,
    rows,
    distribution,
    ivValues,
    avgIv,
    maxIv,
    minIv,
    pcr,
    volumePcr,
    callOi,
    putOi,
    maxPain,
    atmStrike,
    maxPainGap,
    expiryDays,
    oiWalls,
    vix,
    vixValue,
    extras,
    macroItems,
    decisionFactors,
    sp500,
    nasdaq,
    dxy,
    us10y,
    gold,
    oil,
    riskScore,
    confidenceScore,
    probabilities,
    riskLight,
    direction,
    primaryRisk,
    updatedAt: payload.updatedAt || "",
    publicChain: payload.optionChain || {},
  };
}
function getOptionsUnderlyingPrice(model) {
  return optionsNumber(model.chain?.spot?.value ?? model.chain?.underlyingPrice ?? model.atmStrike ?? model.maxPain);
}
function getOptionsFocusMove(item) {
  const parsed = parseMarketNumber(item?.pct);
  return Number.isFinite(parsed) ? parsed : null;
}
function getOptionsRegionItemFocusKey(regionKey, item = {}, index = 0) {
  const token = String(item.symbol || item.dataSymbol || item.name || index)
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^\w.-]/g, "");
  return `${regionKey}::item::${token || index}::${index}`;
}
function isOptionsRegionFocusActive(regionKey) {
  const selected = String(derivativesOptionsSelectedFocus || "");
  return selected === regionKey || selected.startsWith(`${regionKey}::item::`);
}
function getOptionsFocusScopeLabel(focus = {}) {
  if (focus.kind === "regional-item") return "\u500b\u5225\u6a19\u7684";
  if (focus.kind === "region") return "\u5340\u57df\u5e02\u5834";
  return "\u8de8\u5e02\u5834\u56e0\u5b50";
}
function getOptionsRegionalFocusItems(model) {
  return buildOptionsRegionalSummary(model.payload).map(({ group, usableCount, strongest, key }) => ({
    key,
    group: "\u9078\u64c7\u6b0a\u5730\u5340\u5e02\u5834",
    name: `${group.region}\u5e02\u5834`,
    value: `${usableCount}/${group.items.length}`,
    pct: strongest ? `${strongest.symbol || "--"} ${strongest.pct || "--"}` : "--",
    kind: "region",
    item: strongest,
    region: group.region,
    usableCount,
    totalCount: group.items.length,
  }));
}
function getOptionsRegionalItemFocusItems(model) {
  return buildOptionsRegionalSummary(model.payload).flatMap(({ group, key }) => group.items.map((item, index) => ({
    key: getOptionsRegionItemFocusKey(key, item, index),
    group: `${group.region}\u500b\u5225\u6a19\u7684`,
    name: item.name || item.symbol || "\u672a\u547d\u540d\u6a19\u7684",
    value: item.error ? "\u8cc7\u6599\u5f85\u78ba\u8a8d" : formatGlobalValue(item.close),
    pct: item.error ? "\u8cc7\u6599\u5f85\u78ba\u8a8d" : item.pct || "--",
    kind: "regional-item",
    item,
    region: group.region,
    dataSource: item.exchange || item.dataSource || "--",
  })));
}
function getOptionsFocusItems(model) {
  const regionalFocusItems = getOptionsRegionalFocusItems(model);
  const regionalItemFocusItems = getOptionsRegionalItemFocusItems(model);
  const optionLabel = getTaiwanOptionProductLabel(model.chain);
  const optionSymbol = getActiveTaiwanOptionUnderlying(model.chain);
  return [
    ...regionalFocusItems,
    ...regionalItemFocusItems,
    { key: "txo", group: "台灣", name: `${optionLabel} ${optionSymbol}`, value: model.chain?.selectedExpiry || "--", pct: model.rows.length ? `履約價 ${model.rows.length} 檔` : "--", kind: "options", item: null },
    { key: "sp500", group: "美國", name: "S&P 500", value: formatGlobalValue(model.sp500?.close), pct: model.sp500?.pct || "--", kind: "equity", item: model.sp500 },
    { key: "nasdaq", group: "美國", name: "Nasdaq", value: formatGlobalValue(model.nasdaq?.close), pct: model.nasdaq?.pct || "--", kind: "equity", item: model.nasdaq },
    { key: "vix", group: "波動率", name: "VIX", value: Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--", pct: model.vix?.pct || "--", kind: "vix", item: model.vix },
    { key: "dxy", group: "總經", name: "美元指數", value: formatGlobalValue(model.dxy?.close), pct: model.dxy?.pct || "--", kind: "dxy", item: model.dxy },
    { key: "us10y", group: "利率", name: "10Y 利率", value: formatGlobalValue(model.us10y?.close), pct: model.us10y?.pct || "--", kind: "rate", item: model.us10y },
    { key: "gold", group: "避險", name: "黃金", value: formatGlobalValue(model.gold?.close), pct: model.gold?.pct || "--", kind: "gold", item: model.gold },
    { key: "oil", group: "商品", name: "原油", value: formatGlobalValue(model.oil?.close), pct: model.oil?.pct || "--", kind: "oil", item: model.oil },
  ];
}
function getOptionsActiveFocus(model) {
  const items = getOptionsFocusItems(model);
  const active = items.find((item) => item.key === derivativesOptionsSelectedFocus) || items[0];
  if (active.key !== derivativesOptionsSelectedFocus) derivativesOptionsSelectedFocus = active.key;
  return active;
}
function getOptionsRiskLightFromScore(score) {
  return score >= 82
    ? { label: "紅燈", tone: "red", text: "極端風險或重大波動環境" }
    : score >= 66
      ? { label: "橘燈", tone: "orange", text: "高風險，需控管槓桿與到期日" }
      : score >= 48
        ? { label: "黃燈", tone: "yellow", text: "需留意波動與 OI 變化" }
        : { label: "綠燈", tone: "green", text: "風險正常，等待訊號確認" };
}
function buildOptionsFocusAnalysis(model) {
  const focus = getOptionsActiveFocus(model);
  const decisionFactors = model.decisionFactors || buildOptionsHiddenDecisionFactors({
    vix: model.vix,
    vixValue: model.vixValue,
    dxy: model.dxy,
    us10y: model.us10y,
    gold: model.gold,
    oil: model.oil,
  });
  const factorSummary = decisionFactors.summary || "外部決策因子同步中。";
  const factorCoverageText = `隱性決策因子 ${decisionFactors.readyCount || 0}/${decisionFactors.totalCount || 5} 已納入。`;
  if (focus.key === "txo") {
    const coneBias = clampAssetHubScore(
      (model.direction === "偏多" ? 1 : model.direction === "偏空" ? -1 : 0) + (decisionFactors.directionBias || 0) * 0.35,
      -1,
      1,
    );
    return {
      focus,
      direction: model.direction,
      primaryRisk: `${model.primaryRisk}；${factorSummary}`,
      riskScore: model.riskScore,
      confidenceScore: model.confidenceScore,
      probabilities: model.probabilities,
      riskLight: model.riskLight,
      evidenceText: `判斷來源：IV、Put/Call Ratio、OI 牆、最大痛點、到期日與跨市場風險資料；${factorCoverageText}`,
      decisionText: model.direction === "偏多"
        ? `多方訊號略占優勢，但仍需確認壓力區是否被有效突破；${factorSummary}`
        : model.direction === "偏空"
          ? `避險與下檔風險較需要優先管理，追價前先確認 Put OI 與波動因子是否續升；${factorSummary}`
          : `盤面較偏區間震盪，策略重點放在波動率、時間價值與區間邊界；${factorSummary}`,
      coneBias,
    };
  }
  const move = getOptionsFocusMove(focus);
  const moveValue = move ?? 0;
  let direction = moveValue >= 0.35 ? "偏多" : moveValue <= -0.35 ? "偏空" : "震盪";
  const optionLabel = getTaiwanOptionProductLabel(model.chain);
  let primaryRisk = `${focus.name} 變動仍需與 ${optionLabel} OI 牆交叉確認`;
  let pressure = Math.min(Math.abs(moveValue) * 9, 24);
  let coneBias = moveValue > 0 ? 0.45 : moveValue < 0 ? -0.45 : 0;
  if (focus.kind === "region") {
    const coverage = focus.totalCount ? focus.usableCount / focus.totalCount : 0;
    direction = moveValue >= 0.35 ? "區域偏多" : moveValue <= -0.35 ? "區域偏空" : "區域震盪";
    primaryRisk = `${focus.region || focus.name}有效資料 ${focus.usableCount || 0}/${focus.totalCount || 0}，代表標的 ${focus.pct || "--"}，需同步觀察 ${optionLabel} OI、VIX 與美股波動。`;
    pressure = moveValue < 0 ? pressure + 12 : Math.max(pressure - 3, 0);
    if (coverage < 0.55) pressure += 8;
    coneBias = moveValue > 0 ? 0.45 : moveValue < 0 ? -0.55 : 0;
  } else if (focus.kind === "regional-item") {
    const item = focus.item || {};
    const closeReady = Number.isFinite(parseMarketNumber(item.close));
    const metric = getAssetHubMetric(item);
    const metricValue = formatGlobalVolume(metric.value);
    const sourceText = `${item.exchange || item.dataSource || focus.dataSource || "--"}${item.date ? ` / ${item.date}` : ""}`;
    direction = !closeReady
      ? "\u8cc7\u6599\u5f85\u78ba\u8a8d"
      : moveValue >= 0.35
        ? "\u500b\u5225\u504f\u591a"
        : moveValue <= -0.35
          ? "\u500b\u5225\u504f\u7a7a"
          : "\u500b\u5225\u9707\u76ea";
    primaryRisk = !closeReady
      ? `${focus.name}\u7dda\u4e0a\u5546\u54c1\u5831\u50f9\u8cc7\u6599\u4e0d\u5b8c\u6574\uff1a${item.error || "\u7f3a\u5c11\u6700\u65b0\u50f9\u683c"}\uff1bAI \u5df2\u964d\u4f4e\u4fe1\u5fc3\uff0c\u4e0d\u4ee5\u5340\u57df\u7e3d\u9ad4\u7d50\u8ad6\u4ee3\u66ff\u8a72\u5546\u54c1\u3002`
      : `${focus.name}\u5546\u54c1\u8cc7\u6599\uff1a\u50f9\u683c ${focus.value}\u3001\u6f32\u8dcc ${focus.pct}\u3001${metric.label} ${metricValue}\u3001\u4f86\u6e90 ${sourceText}\uff1b\u4ee5\u8a72\u5546\u54c1\u672c\u8eab\u52d5\u80fd\u4ea4\u53c9 TXO OI\u7246\u3001VIX \u8207\u9078\u64c7\u6b0a\u98a8\u96aa\u71c8\u865f\u9032\u884c\u500b\u5225\u5206\u6790\u3002`;
    pressure = !closeReady ? pressure + 16 : moveValue < 0 ? pressure + 10 : Math.max(pressure - 2, 0);
    coneBias = moveValue > 0 ? 0.5 : moveValue < 0 ? -0.65 : 0;
  } else if (focus.kind === "vix") {
    direction = moveValue > 0.2 || (Number.isFinite(model.vixValue) && model.vixValue >= 20) ? "避險升溫" : "風險降溫";
    primaryRisk = `VIX ${focus.value}、變動 ${focus.pct}，會直接影響權利金與避險需求。`;
    pressure = Math.max(pressure, Number.isFinite(model.vixValue) ? Math.max(0, model.vixValue - 14) * 2.6 : 10);
    coneBias = direction === "避險升溫" ? -0.75 : 0.35;
  } else if (focus.kind === "dxy") {
    direction = moveValue > 0.15 ? "美元壓力" : moveValue < -0.15 ? "美元緩和" : "震盪";
    primaryRisk = `美元指數 ${focus.value}、${focus.pct}；美元走強通常壓抑風險資產與外資情緒。`;
    pressure = moveValue > 0 ? pressure + 10 : Math.max(pressure - 2, 0);
    coneBias = moveValue > 0 ? -0.55 : 0.35;
  } else if (focus.kind === "rate") {
    direction = moveValue > 0.08 ? "利率壓力" : moveValue < -0.08 ? "利率緩和" : "震盪";
    primaryRisk = `10Y 利率 ${focus.value}、${focus.pct}；折現率變化會影響科技股與選擇權風險偏好。`;
    pressure = moveValue > 0 ? pressure + 12 : Math.max(pressure - 2, 0);
    coneBias = moveValue > 0 ? -0.55 : 0.32;
  } else if (focus.kind === "gold") {
    direction = moveValue > 0.2 ? "避險買盤" : moveValue < -0.2 ? "避險降溫" : "震盪";
    primaryRisk = `黃金 ${focus.value}、${focus.pct}；若與 VIX 同步轉強，代表避險情緒升溫。`;
    pressure = moveValue > 0 ? pressure + 6 : pressure;
    coneBias = moveValue > 0 ? -0.25 : 0.22;
  } else if (focus.kind === "oil") {
    direction = moveValue > 0.4 ? "通膨壓力" : moveValue < -0.4 ? "成本緩和" : "震盪";
    primaryRisk = `原油 ${focus.value}、${focus.pct}；油價上行會提高通膨與利率敏感度。`;
    pressure = moveValue > 0 ? pressure + 7 : Math.max(pressure - 2, 0);
    coneBias = moveValue > 0 ? -0.3 : 0.25;
  } else if (focus.kind === "equity") {
    primaryRisk = `${focus.name} ${focus.value}、${focus.pct}；美股方向會影響台指風險偏好與隔日開盤情緒。`;
    pressure = moveValue < 0 ? pressure + 10 : Math.max(pressure - 4, 0);
    coneBias = moveValue > 0 ? 0.58 : moveValue < 0 ? -0.68 : 0;
  }
  pressure += Math.max(0, decisionFactors.riskAdjustment || 0) * 0.45;
  coneBias = clampAssetHubScore(coneBias + (decisionFactors.directionBias || 0) * 0.35, -1, 1);
  const riskScore = Math.round(clampAssetHubScore(model.riskScore * 0.55 + 24 + pressure, 12, 96));
  const focusQuoteReady = focus.kind !== "regional-item" || Number.isFinite(parseMarketNumber(focus.item?.close));
  const confidenceScore = Math.round(clampAssetHubScore(
    model.confidenceScore
      - 4
      + (focus.item && focusQuoteReady ? 7 : 0)
      + Math.min((decisionFactors.readyCount || 0) * 2, 8)
      - (!focusQuoteReady ? 12 : 0),
    24,
    96,
  ));
  const bullishRaw = 32 + (coneBias > 0 ? 18 : 0) + (model.direction === "偏多" ? 8 : 0) - (riskScore > 70 ? 8 : 0);
  const bearishRaw = 30 + (coneBias < 0 ? 18 : 0) + (riskScore >= 66 ? 8 : 0);
  const rangeRaw = 28 + (Math.abs(moveValue) < 0.25 ? 12 : 0);
  const total = Math.max(bullishRaw + bearishRaw + rangeRaw, 1);
  const probabilities = {
    bullish: Math.round(bullishRaw / total * 100),
    bearish: Math.round(bearishRaw / total * 100),
  };
  probabilities.range = Math.max(0, 100 - probabilities.bullish - probabilities.bearish);
  const riskLight = getOptionsRiskLightFromScore(riskScore);
  return {
    focus,
    direction,
    primaryRisk,
    riskScore,
    confidenceScore,
    probabilities,
    riskLight,
    evidenceText: `目前焦點：${focus.name} ${focus.value} / ${focus.pct}；同步比對 ${optionLabel} PCR ${optionsDecimal(model.pcr)}、OI 牆、最大痛點與隱性決策因子。${factorCoverageText}`,
    decisionText: `${focus.name} 被選為主控因子；AI 會把該標的變動映射到 ${optionLabel} 的方向、波動率與避險需求，並由隱性決策因子校正風險分數。${factorSummary}`,
    coneBias,
  };
}
function formatOptionsDistanceText(anchor, target, label) {
  const anchorValue = optionsNumber(anchor);
  const targetValue = optionsNumber(target);
  if (anchorValue === null || targetValue === null) return `${label} --`;
  const gap = targetValue - anchorValue;
  const pct = anchorValue ? (gap / anchorValue) * 100 : null;
  const side = gap >= 0 ? "上方" : "下方";
  const pctText = pct === null ? "" : `，約 ${Math.abs(pct).toFixed(2)}%`;
  return `${label}在${side} ${optionsWhole(Math.abs(gap))} 點${pctText}`;
}
function buildOptionsInvestorPlaybook(model, analysis = buildOptionsFocusAnalysis(model)) {
  const putWall = model.oiWalls.putWall?.strike;
  const callWall = model.oiWalls.callWall?.strike;
  const maxPain = model.maxPain;
  const spot = getOptionsUnderlyingPrice(model) ?? model.atmStrike ?? maxPain;
  const skew = model.maxIv !== null && model.minIv !== null ? model.maxIv - model.minIv : null;
  const directionText = String(analysis.direction || "");
  const bullish = Number(analysis.probabilities?.bullish) || 0;
  const bearish = Number(analysis.probabilities?.bearish) || 0;
  const range = Number(analysis.probabilities?.range) || 0;
  const focusName = analysis.focus?.name || "目前標的";
  const focusSignal = `${analysis.focus?.value || "--"} / ${analysis.focus?.pct || "--"}`;
  const hasWalls = optionsNumber(putWall) !== null && optionsNumber(callWall) !== null;
  const rangeText = hasWalls ? `${optionsWhole(putWall)} - ${optionsWhole(callWall)}` : "等待 OI 牆回補";
  const isBullish = directionText.includes("偏多") || (bullish >= bearish + 7 && bullish >= range);
  const isBearish = directionText.includes("偏空") || directionText.includes("避險") || (bearish >= bullish + 7 && bearish >= range);
  const isRange = !isBullish && !isBearish;
  const premiumState = model.avgIv === null
    ? "權利金資料同步中"
    : model.avgIv >= 0.55
      ? "權利金偏貴"
      : model.avgIv <= 0.28
        ? "權利金成本較低"
        : "權利金中性";
  const stance = isBullish
    ? "偏多但等突破確認"
    : isBearish
      ? "防守優先"
      : "區間震盪優先";
  const priority = isBullish
    ? "回測支撐不破再加碼；突破壓力才追方向"
    : isBearish
      ? "先降槓桿與保護部位；跌破支撐不攤平"
      : "區間內不追高殺低，等待邊界訊號";
  const setupText = isBullish
    ? `${focusName} 目前偏向多方，但上方 ${optionsWhole(callWall)} 仍是主要壓力；沒有站上壓力前，策略以拉回守穩 ${optionsWhole(putWall)} 後分批布局較清楚。`
    : isBearish
      ? `${focusName} 顯示避險或下行壓力較高；${optionsWhole(putWall)} 是第一道支撐，若失守且 VIX 或 Put OI 續升，應先降低方向性曝險。`
      : `${focusName} 未形成明確單邊趨勢；目前以 ${rangeText} 作為交易區間，靠近壓力看保守、靠近支撐看防守反彈。`;
  const triggerText = isBullish
    ? `有效突破 ${optionsWhole(callWall)}，且成交量或 IV 同步放大，才把偏多假設升級；若跌回 ${optionsWhole(maxPain)} 附近，改看震盪。`
    : isBearish
      ? `跌破 ${optionsWhole(putWall)} 並伴隨 Put OI 或 VIX 增加，代表風險擴散；若收回 ${optionsWhole(maxPain)}，空方壓力才可降級。`
      : `向上突破 ${optionsWhole(callWall)} 或向下跌破 ${optionsWhole(putWall)} 前，方向訊號都只視為區間內波動。`;
  const premiumText = `${premiumState}：平均 IV ${optionsPct(model.avgIv)}、Skew ${optionsPct(skew)}、Volume PCR ${optionsDecimal(model.volumePcr)}；IV 快速擴張時避免用裸賣承擔隔夜風險。`;
  const riskText = analysis.riskScore >= 66
    ? `風險分數 ${analysis.riskScore}/100 偏高，部位應先小、停損先定，避免在到期前用高槓桿押單邊。`
    : `風險分數 ${analysis.riskScore}/100 尚可，但仍需用 ${optionsWhole(putWall)} 與 ${optionsWhole(callWall)} 管理失效點。`;
  const locationText = [
    `現貨/平值 ${optionsWhole(spot)}`,
    formatOptionsDistanceText(spot, putWall, "支撐"),
    formatOptionsDistanceText(spot, callWall, "壓力"),
  ].join("；");
  const dataText = `${focusName} ${focusSignal}；PCR ${optionsDecimal(model.pcr)}、信心 ${analysis.confidenceScore}/100、機率 多 ${bullish}% / 震 ${range}% / 空 ${bearish}%。`;
  return {
    stance,
    priority,
    rangeText,
    setupText,
    triggerText,
    premiumText,
    riskText,
    locationText,
    dataText,
    headline: `${focusName}：${stance}，先用 ${rangeText} 定義支撐與壓力`,
    summary: `${setupText} ${premiumText}`,
  };
}
function formatOptionsConeValue(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  const abs = Math.abs(parsed);
  const digits = abs >= 1000 ? 0 : abs >= 10 ? 2 : 4;
  return parsed.toLocaleString("en-US", {
    minimumFractionDigits: digits >= 4 ? 2 : 0,
    maximumFractionDigits: digits,
  });
}
function buildOptionsRiskConeProjection(model, analysis) {
  const txoSpot = getOptionsUnderlyingPrice(model);
  const txoAtm = model.atmStrike ?? txoSpot;
  const txoMaxPain = model.maxPain ?? txoAtm ?? txoSpot;
  const txoCallWall = model.oiWalls.callWall?.strike ?? txoAtm ?? txoSpot;
  const txoPutWall = model.oiWalls.putWall?.strike ?? txoAtm ?? txoSpot;
  const selectedStrike = optionsNumber(derivativesOptionsSelectedStrike);
  const chainRows = getOptionsChainRows(model.chain || {});
  const selectedStrikeExists = selectedStrike !== null && chainRows.some((row) => optionsNumber(row.strike) === selectedStrike);
  const chainAnchor = selectedStrikeExists ? selectedStrike : txoAtm;
  const chainGap = selectedStrikeExists && txoSpot !== null ? selectedStrike - txoSpot : 0;
  const chainRange = Math.max(
    Math.abs((txoCallWall ?? txoSpot ?? 0) - (txoPutWall ?? txoSpot ?? 0)),
    Math.abs(txoSpot || 0) * 0.025,
    1,
  );
  const chainExtraBias = selectedStrikeExists ? clampAssetHubScore(chainGap / chainRange, -0.75, 0.75) : 0;
  const focus = analysis.focus || {};
  const focusItem = focus.item || null;
  const focusClose = parseMarketNumber(focusItem?.close);
  const useFocusProjection = focus.key !== "txo"
    && focus.kind !== "options"
    && Number.isFinite(focusClose)
    && focusClose > 0;
  if (!useFocusProjection) {
    return {
      mode: "option-chain",
      spot: txoSpot,
      atm: chainAnchor,
      maxPain: txoMaxPain,
      callWall: txoCallWall,
      putWall: txoPutWall,
      upperLabel: "Call",
      lowerLabel: "Put",
      extraBias: chainExtraBias,
      noteLabels: [
        ["現價", txoSpot],
        ...(selectedStrikeExists ? [["選取履約價", selectedStrike]] : []),
        ["最大痛點", txoMaxPain],
        ["Put 牆", txoPutWall],
        ["Call 牆", txoCallWall],
      ],
      note: selectedStrikeExists
        ? `風險錐已切換到選取履約價 ${formatOptionsConeValue(selectedStrike)}；中心線會依該履約價相對現價與最大痛點的位置重新投影。`
        : model.direction === "偏多"
          ? "風險錐上緣向壓力區延伸，需確認 Call OI 牆是否被有效消化。"
          : model.direction === "偏空"
            ? "風險錐下緣向 Put OI 支撐靠攏，避險需求與 VIX 變化需優先觀察。"
            : "風險錐集中於最大痛點與 ATM 附近，策略以區間與時間價值控管為主。",
    };
  }

  const move = getOptionsFocusMove(focus) ?? parseMarketNumber(focusItem?.pct) ?? 0;
  const vixFactor = Number.isFinite(model.vixValue) ? model.vixValue / 100 : 0.18;
  const ivFactor = model.avgIv !== null ? model.avgIv : vixFactor;
  const absMoveRatio = Math.abs(move) / 100;
  const volatilityRatio = clampAssetHubScore(Math.max(0.018, Math.min(0.18, ivFactor * 0.2 + absMoveRatio * 0.75)), 0.012, 0.22);
  const baseBand = Math.max(focusClose * volatilityRatio, focusClose * 0.015, 0.05);
  const directionalBias = clampAssetHubScore(Number(analysis.coneBias) || 0, -1, 1);
  const moveBias = focusClose * (move / 100) * 0.65;
  const bias = baseBand * directionalBias + moveBias;
  const pressureBoost = 1 + Math.min(Math.abs(directionalBias) * 0.35 + absMoveRatio * 3.5, 0.75);
  const upperBand = focusClose + baseBand * (1.15 * pressureBoost);
  const lowerBand = Math.max(0, focusClose - baseBand * (1.15 * pressureBoost));
  const midline = focusClose + bias * 0.35;
  return {
    mode: "focus-proxy",
    spot: focusClose,
    atm: focusClose,
    maxPain: midline,
    callWall: upperBand,
    putWall: lowerBand,
    upperLabel: "上緣",
    lowerLabel: "下緣",
    extraBias: 0,
    focusMove: move,
    noteLabels: [
      ["標的現價", focusClose],
      ["風險中軸", midline],
      ["下緣", lowerBand],
      ["上緣", upperBand],
    ],
    note: `${focus.name} 已切換為目前風險錐基準；本圖用該標的價格 ${formatOptionsConeValue(focusClose)}、漲跌 ${focus.pct || "--"}、隱性決策因子與選擇權波動率重算上下風險帶，不沿用 TXO 固定 Call/Put 牆。`,
  };
}
function renderOptionsRiskConeContent(model, analysis = buildOptionsFocusAnalysis(model)) {
  const projection = buildOptionsRiskConeProjection(model, analysis);
  const { spot, atm, maxPain, callWall, putWall } = projection;
  if (spot === null || atm === null) {
    return "";
  }
  const vixFactor = Number.isFinite(model.vixValue) ? model.vixValue / 100 : 0.18;
  const ivFactor = model.avgIv !== null ? model.avgIv : vixFactor;
  const minBand = projection.mode === "focus-proxy" ? Math.max(Math.abs(spot) * 0.015, 0.05) : 80;
  const baseBand = Math.max(Math.abs(callWall - putWall) * 0.22, spot * Math.max(ivFactor, 0.06) * 0.16, minBand);
  const coneBias = clampAssetHubScore((Number(analysis.coneBias) || 0) + (Number(projection.extraBias) || 0), -1, 1);
  const bias = baseBand * coneBias;
  const centerValues = [
    spot,
    (spot + maxPain) / 2,
    maxPain,
    atm,
    spot + bias * 0.62,
    spot + bias,
  ];
  const upperValues = centerValues.map((value, index) => value + baseBand * (0.7 + index * 0.1));
  const lowerValues = centerValues.map((value, index) => value - baseBand * (0.7 + index * 0.1));
  const allValues = [...upperValues, ...lowerValues, callWall, putWall, maxPain, spot].filter((value) => Number.isFinite(value));
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const pad = Math.max((maxValue - minValue) * 0.12, 1);
  const low = minValue - pad;
  const high = maxValue + pad;
  const xs = [46, 210, 374, 538, 702, 866];
  const y = (value) => 260 - ((value - low) / Math.max(high - low, 1)) * 196;
  const toPoints = (values) => values.map((value, index) => `${xs[index].toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  const upperPoints = toPoints(upperValues);
  const lowerPoints = toPoints(lowerValues);
  const centerPoints = toPoints(centerValues);
  const areaPoints = `${upperPoints} ${[...lowerValues].reverse().map((value, index) => `${xs[xs.length - 1 - index].toFixed(1)},${y(value).toFixed(1)}`).join(" ")}`;
  const coneLabels = ["\u73fe\u50f9", "5\u65e5", "10\u65e5", "20\u65e5", "40\u65e5", "60\u65e5"];
  const coneNodes = centerValues.map((value, index) => ({
    label: coneLabels[index] || `${index + 1}`,
    x: xs[index],
    y: y(value),
    center: value,
    upper: upperValues[index],
    lower: lowerValues[index],
  }));
  const hoverZones = coneNodes.map((node, index) => {
    const left = index === 0 ? 32 : (xs[index - 1] + node.x) / 2;
    const right = index === xs.length - 1 ? 882 : (node.x + xs[index + 1]) / 2;
    return `
      <rect class="options-risk-cone-hover-zone" tabindex="0" role="button" x="${left.toFixed(1)}" y="36" width="${Math.max(right - left, 12).toFixed(1)}" height="242"
        data-cone-x="${node.x.toFixed(1)}"
        data-cone-y="${node.y.toFixed(1)}"
        data-cone-label="${escapeHtml(node.label)}"
        data-cone-center="${escapeHtml(formatOptionsConeValue(node.center))}"
        data-cone-upper="${escapeHtml(formatOptionsConeValue(node.upper))}"
        data-cone-lower="${escapeHtml(formatOptionsConeValue(node.lower))}"
        data-cone-focus="${escapeHtml(analysis.focus.name)}"
        data-cone-direction="${escapeHtml(analysis.direction)}"
        data-cone-bullish="${Number(analysis.probabilities.bullish) || 0}"
        data-cone-bearish="${Number(analysis.probabilities.bearish) || 0}"
        data-cone-range="${Number(analysis.probabilities.range) || 0}">
      </rect>
    `;
  }).join("");
  const labels = projection.noteLabels || [];
  return `
        <div class="asset-hub-group-heading">
          <div>
            <p class="panel-kicker">Signature Visual</p>
            <h4>風險錐：趨勢延伸與波動率風險帶</h4>
          </div>
          <span>${escapeHtml(analysis.focus.name)} · ${escapeHtml(analysis.direction)} · 信心 ${analysis.confidenceScore}/100</span>
        </div>
        <div class="options-risk-cone-layout">
          <div class="options-risk-cone-chart" aria-label="選擇權風險錐" data-options-risk-cone-chart>
            <svg viewBox="0 0 912 320" role="img" aria-label="動態風險錐">
              <defs>
                <linearGradient id="optionsConeFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="rgba(232,84,62,0.24)"></stop>
                  <stop offset="52%" stop-color="rgba(231,185,76,0.12)"></stop>
                  <stop offset="100%" stop-color="rgba(53,184,140,0.22)"></stop>
                </linearGradient>
              </defs>
              <line x1="38" y1="${y(callWall).toFixed(1)}" x2="882" y2="${y(callWall).toFixed(1)}" class="is-call-wall"></line>
              <line x1="38" y1="${y(putWall).toFixed(1)}" x2="882" y2="${y(putWall).toFixed(1)}" class="is-put-wall"></line>
              <polygon points="${areaPoints}" class="is-risk-area"></polygon>
              <polyline points="${upperPoints}" class="is-upper-line"></polyline>
              <polyline points="${lowerPoints}" class="is-lower-line"></polyline>
              <polyline points="${centerPoints}" class="is-center-line"></polyline>
              ${centerValues.map((value, index) => `<circle cx="${xs[index]}" cy="${y(value).toFixed(1)}" r="${index === centerValues.length - 1 ? 5 : 4}" class="is-center-dot"></circle>`).join("")}
              <text x="42" y="${Math.max(18, y(callWall) - 6).toFixed(1)}" class="is-call-label">${escapeHtml(projection.upperLabel || "Call")} ${formatOptionsConeValue(callWall)}</text>
              <text x="42" y="${Math.min(304, y(putWall) + 18).toFixed(1)}" class="is-put-label">${escapeHtml(projection.lowerLabel || "Put")} ${formatOptionsConeValue(putWall)}</text>
              <line class="options-risk-cone-crosshair is-x" x1="46" x2="46" y1="36" y2="278" data-options-risk-cone-crosshair-x></line>
              <line class="options-risk-cone-crosshair is-y" x1="32" x2="882" y1="260" y2="260" data-options-risk-cone-crosshair-y></line>
              <circle class="options-risk-cone-crosshair-dot" cx="46" cy="260" r="5" data-options-risk-cone-crosshair-dot></circle>
              ${hoverZones}
            </svg>
            <div class="options-risk-cone-tooltip" data-options-risk-cone-tooltip></div>
          </div>
          <div class="options-risk-cone-notes">
            ${labels.map(([label, value]) => `<span><small>${escapeHtml(label)}</small><b>${formatOptionsConeValue(value)}</b></span>`).join("")}
            <p>${escapeHtml(projection.note || "")}</p>
          </div>
        </div>
  `;
}
function getOptionsStrikeKey(value) {
  const strike = optionsNumber(value);
  return strike === null ? "" : String(strike);
}
function getSelectedOptionsStrike(rows = [], fallback = null) {
  const validKeys = new Set(rows.map((row) => getOptionsStrikeKey(row.strike)).filter(Boolean));
  const requested = getOptionsStrikeKey(derivativesOptionsSelectedStrike);
  if (requested && validKeys.has(requested)) return Number(requested);
  const fallbackKey = getOptionsStrikeKey(fallback);
  const selected = fallbackKey && validKeys.has(fallbackKey)
    ? Number(fallbackKey)
    : optionsNumber(rows[Math.floor(rows.length / 2)]?.strike);
  derivativesOptionsSelectedStrike = getOptionsStrikeKey(selected);
  return selected;
}
function optionsSignedWhole(value) {
  const parsed = optionsNumber(value);
  if (parsed === null) return "--";
  const rounded = Math.round(parsed);
  return `${rounded > 0 ? "+" : ""}${rounded.toLocaleString("en-US")}`;
}
function renderOptionsChainStats(model, extraClass = "", selected = null) {
  if (selected) {
    return `
      <div class="asset-option-chain-stats tw-option-stats ${escapeHtml(extraClass)}">
        <span><b>${optionsOiWhole(selected.callOi)}</b><small>選取 Call OI</small></span>
        <span><b>${optionsOiWhole(selected.putOi)}</b><small>選取 Put OI</small></span>
        <span><b>${optionsDecimal(selected.oiPcr)}</b><small>選取 OI Put / Call</small></span>
        <span><b>${optionsSignedWhole(selected.maxPainGap)}</b><small>距最大痛點</small></span>
        <span><b>${optionsSignedWhole(selected.atmGap)}</b><small>距平值履約價</small></span>
        <span><b>${optionsDecimal(selected.volumePcr)}</b><small>選取 Volume PCR</small></span>
      </div>
    `;
  }
  return `
    <div class="asset-option-chain-stats tw-option-stats ${escapeHtml(extraClass)}">
      <span><b>${optionsWhole(model.callOi)}</b><small>Call OI</small></span>
      <span><b>${optionsWhole(model.putOi)}</b><small>Put OI</small></span>
      <span><b>${optionsDecimal(model.pcr)}</b><small>OI Put / Call</small></span>
      <span><b>${optionsWhole(model.maxPain)}</b><small>最大痛點</small></span>
      <span><b>${optionsWhole(model.atmStrike)}</b><small>平值履約價</small></span>
      <span><b>${optionsDecimal(model.volumePcr)}</b><small>Volume PCR</small></span>
    </div>
  `;
}
function renderOptionsChainOiSummary(model, chain = {}, options = {}) {
  const rowLimit = Number(options.rowLimit) || 22;
  const chainRows = pickTaiwanOptionRows(getOptionsChainRows(chain), model.atmStrike, rowLimit)
    .slice()
    .sort((left, right) => Number(left.strike) - Number(right.strike));
  const distributionRows = pickTaiwanOptionRows(model.distribution || [], model.atmStrike, rowLimit)
    .slice()
    .sort((left, right) => Number(left.strike) - Number(right.strike));
  const sourceRows = chainRows.length ? chainRows : distributionRows;
  const rows = sourceRows.map(normalizeOptionsOiRow);
  if (!rows.length) return "";
  const selectedStrike = getSelectedOptionsStrike(rows, model.atmStrike ?? model.maxPain);
  const selectedKey = getOptionsStrikeKey(selectedStrike);
  const selectedDistribution = rows.find((item) => getOptionsStrikeKey(item.strike) === selectedKey) || {};
  const selectedChain = chainRows.find((item) => getOptionsStrikeKey(item.strike) === selectedKey) || {};
  const selectedCall = selectedChain.call || {};
  const selectedPut = selectedChain.put || {};
  const selectedCallOi = optionsNumber(selectedDistribution.callOpenInterest ?? selectedCall.openInterest);
  const selectedPutOi = optionsNumber(selectedDistribution.putOpenInterest ?? selectedPut.openInterest);
  const selectedCallVolume = optionsNumber(selectedDistribution.callVolume ?? selectedCall.volume);
  const selectedPutVolume = optionsNumber(selectedDistribution.putVolume ?? selectedPut.volume);
  const spotPrice = optionsNumber(
    chain.spot?.value
    ?? chain.underlyingPrice
    ?? model.chain?.spot?.value
    ?? model.chain?.underlyingPrice
  );
  const underlyingPrice = spotPrice ?? optionsNumber(model.atmStrike);
  const priceBasisLabel = spotPrice === null ? "平值履約價基準" : "現貨基準";
  const atmTolerance = underlyingPrice !== null ? Math.max(25, Math.abs(underlyingPrice) * 0.001) : 25;
  const strikeGap = selectedStrike !== null && underlyingPrice !== null ? selectedStrike - underlyingPrice : null;
  const strikeGapPct = strikeGap !== null && underlyingPrice ? (strikeGap / underlyingPrice) * 100 : null;
  const isAtTheMoney = strikeGap !== null && Math.abs(strikeGap) <= atmTolerance;
  const callMoneyness = strikeGap === null
    ? "Call 定位不足"
    : isAtTheMoney ? "Call 價平"
      : strikeGap < 0 ? "Call 價內" : "Call 價外";
  const putMoneyness = strikeGap === null
    ? "Put 定位不足"
    : isAtTheMoney ? "Put 價平"
      : strikeGap > 0 ? "Put 價內" : "Put 價外";
  const moneynessTitle = strikeGap === null
    ? "價內 / 價外資料不足"
    : `${callMoneyness} / ${putMoneyness}`;
  const moneynessDetail = strikeGap === null
    ? "現貨價或履約價不足，暫不判斷價內價外。"
    : `${priceBasisLabel} ${optionsWhole(underlyingPrice)}；選取 ${optionsWhole(selectedStrike)}；${strikeGap >= 0 ? "高於基準" : "低於基準"} ${optionsWhole(Math.abs(strikeGap))} 點${strikeGapPct === null ? "" : `（${strikeGapPct >= 0 ? "+" : ""}${strikeGapPct.toFixed(2)}%）`}。`;
  const localWalls = getOptionsLocalOiWalls(rows);
  const localMaxPain = calculateOptionsLocalMaxPain(rows);
  const maxCall = localWalls.callWall;
  const maxPut = localWalls.putWall;
  const maxPainStrike = localMaxPain?.strike ?? null;
  const hasLocalOi = rows.some((row) => row.callOpenInterest > 0 || row.putOpenInterest > 0);
  const gammaLow = hasLocalOi
    ? Math.min(...[maxPut?.strike, maxPainStrike, maxCall?.strike].map(optionsNumber).filter((value) => value !== null))
    : null;
  const gammaHigh = hasLocalOi
    ? Math.max(...[maxPut?.strike, maxPainStrike, maxCall?.strike].map(optionsNumber).filter((value) => value !== null))
    : null;
  const selectedTone = !hasLocalOi
    ? `本表區間 OI 不足，${moneynessTitle}；先用成交量、IV 與上下檔 Bid/Ask 判斷交易熱度。`
    : getOptionsStrikeKey(maxCall?.strike) === selectedKey
      ? `接近本表 Call Wall，${callMoneyness}，上方壓力與賣權補避險需同步觀察。`
      : getOptionsStrikeKey(maxPut?.strike) === selectedKey
        ? `接近本表 Put Wall，${putMoneyness}，下方支撐與跌破後避險需求需同步觀察。`
        : getOptionsStrikeKey(maxPainStrike) === selectedKey
          ? `接近本表 Max Pain，${callMoneyness} / ${putMoneyness}，結算牽引與區間震盪機率較高。`
          : selectedStrike !== null && maxPainStrike !== null && selectedStrike > Number(maxPainStrike)
            ? `位於本表 Max Pain 上方，${callMoneyness}，偏壓力側，觀察 Call OI 是否被消化。`
            : `位於本表 Max Pain 下方或附近，${putMoneyness}，偏支撐側，觀察 Put OI 是否擴張。`;
  const selectedDetail = [
    `Call OI ${optionsOiWhole(selectedCallOi)}`,
    `Put OI ${optionsOiWhole(selectedPutOi)}`,
    `量 ${optionsWhole(selectedCallVolume)} / ${optionsWhole(selectedPutVolume)}`,
    `IV ${optionsPct(selectedCall.impliedVolatility)} / ${optionsPct(selectedPut.impliedVolatility)}`,
  ].join("；");
  const selectedTotalOi = (selectedCallOi || 0) + (selectedPutOi || 0);
  const selectedOiPcr = selectedCallOi ? selectedPutOi / selectedCallOi : null;
  const selectedVolumePcr = selectedCallVolume ? selectedPutVolume / selectedCallVolume : null;
  const selectedOiBias = selectedTotalOi <= 0
    ? "OI 不足"
    : selectedPutOi > selectedCallOi
    ? "Put OI 較集中"
    : selectedCallOi > selectedPutOi
      ? "Call OI 較集中"
      : "Call / Put OI 接近";
  const relationToSelected = (target, equalText) => {
    const targetValue = optionsNumber(target);
    if (selectedStrike === null || targetValue === null) return "--";
    const gap = selectedStrike - targetValue;
    if (Math.abs(gap) < 0.001) return equalText;
    return gap > 0 ? `高於 ${optionsWhole(Math.abs(gap))} 點` : `低於 ${optionsWhole(Math.abs(gap))} 點`;
  };
  const callWallRelation = maxCall ? relationToSelected(maxCall.strike, "位於 Call Wall") : "本表 Call OI 不足";
  const putWallRelation = maxPut ? relationToSelected(maxPut.strike, "位於 Put Wall") : "本表 Put OI 不足";
  const maxPainRelation = maxPainStrike !== null ? relationToSelected(maxPainStrike, "位於 Max Pain") : "本表 OI 不足";
  const rankedRows = rows
    .map((item) => ({
      strike: optionsNumber(item.strike),
      callOi: Number(item.callOpenInterest) || 0,
      putOi: Number(item.putOpenInterest) || 0,
      totalOi: (Number(item.callOpenInterest) || 0) + (Number(item.putOpenInterest) || 0),
    }))
    .filter((item) => item.strike !== null && item.totalOi > 0)
    .sort((left, right) => right.totalOi - left.totalOi);
  const selectedRankIndex = rankedRows.findIndex((item) => getOptionsStrikeKey(item.strike) === selectedKey);
  const selectedRankText = selectedRankIndex >= 0 ? `OI 排名 ${selectedRankIndex + 1} / ${rankedRows.length}` : "OI 排名 --";
  const hotRows = rankedRows.slice(0, 3);
  const hotZoneLow = hotRows.length ? Math.min(...hotRows.map((item) => item.strike)) : null;
  const hotZoneHigh = hotRows.length ? Math.max(...hotRows.map((item) => item.strike)) : null;
  const selectedInHotZone = selectedStrike !== null && hotZoneLow !== null && hotZoneHigh !== null
    && selectedStrike >= hotZoneLow && selectedStrike <= hotZoneHigh;
  const hotZoneText = hotRows.length
    ? selectedInHotZone ? `選取在熱區：${optionsWhole(selectedStrike)}` : `選取不在熱區：${optionsWhole(selectedStrike)}`
    : "本表 OI 不足";
  const hotZoneDetail = hotRows.length
    ? `${selectedRankText}；Top：${hotRows.map((item) => `${optionsWhole(item.strike)}：${optionsWhole(item.totalOi)}`).join(" / ")}`
    : "目前表格區間 OI 為 0 或不足；請以市場選擇權鏈的全市場摘要與選取履約價分析交叉確認。";
  const gammaRelation = gammaLow === null || gammaHigh === null
    ? "OI 不足，暫不判讀壓力帶"
    : selectedStrike !== null && selectedStrike >= gammaLow && selectedStrike <= gammaHigh
      ? "選取位於壓力帶內"
      : selectedStrike !== null && selectedStrike > gammaHigh
        ? "選取高於壓力帶"
        : "選取低於壓力帶";
  const supportPressureFocus = !hasLocalOi
    ? "本表 OI 不足，改看成交量與價內價外"
    : getOptionsStrikeKey(maxCall?.strike) === selectedKey
    ? "選取在上方主要壓力牆"
    : getOptionsStrikeKey(maxPut?.strike) === selectedKey
      ? "選取在下方主要支撐牆"
      : selectedStrike !== null && maxPainStrike !== null && selectedStrike > Number(maxPainStrike)
        ? "選取偏壓力側"
        : "選取偏支撐側";
  const supportPressureText = `${supportPressureFocus}；${moneynessTitle}；Call/Put OI ${optionsOiWhole(selectedCallOi)} / ${optionsOiWhole(selectedPutOi)}；${hasLocalOi ? "以本表 OI 牆與本表 Max Pain 觀察支撐壓力。" : "等待官方 OI 回補後再輸出牆位。"}`;
  const gammaBandText = gammaLow === null || gammaHigh === null
    ? "等待 OI 回補"
    : `壓力帶 ${optionsWhole(gammaLow)} - ${optionsWhole(gammaHigh)}；選取 ${optionsWhole(selectedStrike)}`;
  const selectedStats = {
    callOi: selectedCallOi,
    putOi: selectedPutOi,
    oiPcr: selectedOiPcr,
    volumePcr: selectedVolumePcr,
    maxPainGap: selectedStrike !== null && maxPainStrike !== null ? selectedStrike - maxPainStrike : null,
    atmGap: selectedStrike !== null && model.atmStrike !== null ? selectedStrike - Number(model.atmStrike) : null,
  };
  return `
    <div class="options-chain-oi-summary ${options.embedded ? "is-embedded" : ""}">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Open Interest Lens</p>
          <h4>${options.embedded ? "選取履約價 OI 分布分析" : "OI 分布分析"}</h4>
        </div>
        <span>${escapeHtml(options.sourceLabel || "TAIFEX 官方日報")}</span>
      </div>
      ${renderOptionsChainStats(model, options.embedded ? "is-embedded" : "", selectedStats)}
      <div class="options-chain-oi-grid">
        <span class="is-call"><small>Call Wall</small><b>${escapeHtml(callWallRelation)}</b><em>本表 ${optionsWhole(maxCall?.strike)} / Call OI ${optionsOiWhole(maxCall?.value)}</em></span>
        <span class="is-put"><small>Put Wall</small><b>${escapeHtml(putWallRelation)}</b><em>本表 ${optionsWhole(maxPut?.strike)} / Put OI ${optionsOiWhole(maxPut?.value)}</em></span>
        <span><small>Max Pain</small><b>${escapeHtml(maxPainRelation)}</b><em>本表估算 ${optionsWhole(maxPainStrike)} / 全市場 ${optionsWhole(model.maxPain)}</em></span>
        <span class="is-wide"><small>OI 集中區</small><b>${escapeHtml(hotZoneText)}</b><em>${escapeHtml(hotZoneDetail)}</em></span>
        <span class="is-selected is-wide"><small>選取履約價</small><b>${optionsWhole(selectedStrike)} · ${escapeHtml(selectedOiBias)}</b><em>${escapeHtml(selectedDetail)}</em></span>
        <span class="is-selected is-wide"><small>價內 / 價外定位</small><b>${escapeHtml(moneynessTitle)}</b><em>${escapeHtml(moneynessDetail)}</em></span>
        <span class="is-selected is-wide"><small>選取判讀</small><b>${escapeHtml(selectedTone)}</b><em>選取總 OI ${optionsWhole(selectedTotalOi)}；點選下方任一履約價列，可切換本區分析。</em></span>
        <span class="is-wide"><small>Gamma / 壓力帶</small><b>${escapeHtml(gammaRelation)}</b><em>${escapeHtml(gammaBandText)}</em></span>
        <span class="is-wide"><small>支撐 / 壓力判讀</small><b>${escapeHtml(supportPressureFocus)}</b><em>${escapeHtml(supportPressureText)}</em></span>
      </div>
      <p class="stock-theory-note">下方完整選擇權鏈保留逐履約價明細；本區只摘要 OI 牆、最大痛點與集中區，避免和明細表重複。</p>
    </div>
  `;
}
function buildOptionsCrossValidationModules(model, analysis = buildOptionsFocusAnalysis(model)) {
  const optionLabel = getTaiwanOptionProductLabel(model.chain);
  const decisionFactors = model.decisionFactors || {};
  const hiddenFactorSummary = decisionFactors.summary || "外部決策因子同步中。";
  const skew = model.maxIv !== null && model.minIv !== null ? model.maxIv - model.minIv : null;
  const vixText = Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--";
  return [
    ["技術分析模型", model.macroItems.length ? "同步中" : "待跨市場資料", `${analysis.focus.name} 已納入主控因子；隱性決策因子同步校正風險錐斜率。`],
    ["籌碼模型", model.pcr !== null ? "已啟用" : `待 ${optionLabel} 鏈`, `PCR ${optionsDecimal(model.pcr)}，Call / Put OI ${optionsWhole(model.callOi)} / ${optionsWhole(model.putOi)}。`],
    ["波動率模型", model.avgIv !== null || Number.isFinite(model.vixValue) ? "已啟用" : "待 IV / VIX", `VIX ${vixText}，平均 IV ${optionsPct(model.avgIv)}，Skew ${optionsPct(skew)}。`],
    ["總經模型", model.macroItems.length ? "部分啟用" : "待同步", `已載入 ${model.macroItems.length} 組跨市場資料；${hiddenFactorSummary}`],
  ];
}
function renderOptionsCrossValidationInline(model, analysis = buildOptionsFocusAnalysis(model)) {
  const modules = buildOptionsCrossValidationModules(model, analysis);
  return `
    <div class="options-cross-validation-inline" id="options-cross-validation">
      <div class="asset-hub-group-heading">
        <div><p class="panel-kicker">Cross Validation Engine</p><h4>AI 多模型交叉驗證</h4></div>
        <span>${analysis.confidenceScore}/100</span>
      </div>
      <div class="options-model-grid is-hero">
        ${modules.map(([title, status, text]) => `
          <section>
            <small>${escapeHtml(status)}</small>
            <b>${escapeHtml(title)}</b>
            <p>${escapeHtml(text)}</p>
          </section>
        `).join("")}
      </div>
    </div>
  `;
}
function renderOptionsInsightFeedContent(model, analysis = buildOptionsFocusAnalysis(model)) {
  const playbook = buildOptionsInvestorPlaybook(model, analysis);
  const vixText = Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--";
  const skew = model.maxIv !== null && model.minIv !== null ? model.maxIv - model.minIv : null;
  const putWall = model.oiWalls.putWall?.strike;
  const callWall = model.oiWalls.callWall?.strike;
  const maxPain = model.maxPain;
  const volumeBias = model.volumePcr !== null
    ? model.volumePcr > 1.08 ? "\u4e0b\u65b9\u907f\u96aa\u9700\u6c42\u504f\u5f37" : model.volumePcr < 0.92 ? "\u8ffd\u50f9\u8cb7\u6b0a\u9700\u6c42\u504f\u5f37" : "\u8cb7\u8ce3\u6b0a\u91cf\u80fd\u63a5\u8fd1\u5747\u8861"
    : "\u91cf\u80fd\u4ee3\u7406\u8cc7\u6599\u4e0d\u8db3";
  const insights = [
    {
      tone: analysis.coneBias < 0 ? "put" : analysis.coneBias > 0 ? "call" : "gold",
      label: "主線判讀",
      metric: playbook.stance,
      text: playbook.setupText,
      action: playbook.dataText,
      confidence: analysis.confidenceScore,
    },
    {
      tone: "call",
      label: "上方壓力與突破條件",
      metric: optionsWhole(callWall),
      text: `Call OI 牆位在 ${optionsWhole(callWall)}，接近該區時容易遇到獲利了結、賣方防守或 Gamma 壓力。若只碰到壓力未放量，不宜直接把它解讀成趨勢突破。`,
      action: playbook.triggerText,
      confidence: Math.max(48, analysis.confidenceScore - 8),
    },
    {
      tone: "put",
      label: "下方支撐與失守風險",
      metric: optionsWhole(putWall),
      text: `Put OI 牆位在 ${optionsWhole(putWall)}，是目前賣權避險最需要觀察的支撐帶；若跌破後 Put OI 與 VIX 同步升溫，代表避險需求擴散。`,
      action: `最大痛點 ${optionsWhole(maxPain)} 可當作中性牽引位；跌破支撐前看區間，跌破後先看風控。`,
      confidence: Math.max(48, analysis.confidenceScore - 6),
    },
    {
      tone: "gold",
      label: "權利金與波動率成本",
      metric: `IV ${optionsPct(model.avgIv)} / VIX ${vixText}`,
      text: `Skew ${optionsPct(skew)}，${volumeBias}。波動率上升代表保護成本變貴，也代表裸賣承擔的跳空風險提高。`,
      action: playbook.premiumText,
      confidence: Math.max(42, analysis.confidenceScore - 4),
    },
  ];
  return `
        <div class="options-insight-feed is-upgraded">
          ${insights.map((item) => `
            <section class="is-${escapeHtml(item.tone)}">
              <div class="options-insight-card-head">
                <small>${escapeHtml(item.label)}</small>
                <b>${Math.round(item.confidence)}/100</b>
              </div>
              <strong>${escapeHtml(item.metric)}</strong>
              <p>${escapeHtml(item.text)}</p>
              <span>${escapeHtml(item.action)}</span>
            </section>
          `).join("")}
          ${renderOptionsCrossValidationInline(model, analysis)}
        </div>
  `;
}
function getOptionsDocumentCategory(item = {}) {
  const category = String(item.optionCategory || item.documentCategory || item.group || "").trim();
  if (category) return category;
  const type = String(item.type || "").trim();
  if (type.includes("ETF")) return "ETF 選擇權";
  if (type.includes("股票")) return "股票選擇權";
  if (type.includes("波動")) return "波動率選擇權";
  if (type.includes("商品")) return "商品選擇權";
  return "其他選擇權";
}
function groupOptionsItemsByDocumentCategory(items = []) {
  const groups = new Map();
  items.forEach((item) => {
    const category = getOptionsDocumentCategory(item);
    if (!groups.has(category)) groups.set(category, []);
    groups.get(category).push(item);
  });
  const ordered = OPTIONS_DOCUMENT_CATEGORY_ORDER.filter((category) => groups.has(category));
  ordered.push(...Array.from(groups.keys()).filter((category) => !ordered.includes(category)).sort((a, b) => a.localeCompare(b, "zh-Hant")));
  return ordered.map((category) => ({ region: category, category, items: groups.get(category) || [] }));
}
function buildOptionsRegionalSummary(payload) {
  const items = getAssetHubItems(payload).filter(() => true);
  const groups = groupOptionsItemsByDocumentCategory(items);
  return groups.map((group, index) => {
    const usableCount = group.items.filter((item) => !item.error && Number.isFinite(parseMarketNumber(item.close))).length;
    const strongest = group.items
      .map((item) => ({ item, pct: parseMarketNumber(item?.pct) }))
      .filter((entry) => Number.isFinite(entry.pct))
      .sort((left, right) => right.pct - left.pct)[0]?.item || null;
    return { group, usableCount, strongest, key: `option-region-${index}` };
  });
}
function renderOptionsRegionAnalysisQuoteGrid(items = [], focusKey = "", emptyText = "Options data syncing.") {
  if (!items.length) return `<p class="stock-detail-empty">${escapeHtml(emptyText)}</p>`;
  return `
    <div class="asset-quote-grid options-region-analysis-grid">
      ${items.map((item, index) => {
        const metric = getAssetHubMetric(item);
        const itemFocusKey = getOptionsRegionItemFocusKey(focusKey, item, index);
        const isItemActive = derivativesOptionsSelectedFocus === itemFocusKey;
        const officialUnderlying = getTaiwanOptionUnderlyingFromMarketItem(item);
        return `
          <button class="asset-quote-card options-region-quote-card ${isItemActive ? "is-active" : ""}" type="button"
            data-options-focus-key="${escapeHtml(itemFocusKey)}"
            ${officialUnderlying ? `data-options-chain-underlying="${escapeHtml(officialUnderlying)}"` : ""}
            aria-pressed="${isItemActive ? "true" : "false"}">
            ${isItemActive ? `<span class="options-region-selected-chip">\u76ee\u524d\u5206\u6790</span>` : ""}
            <span class="asset-quote-type">${escapeHtml(item.optionSubcategory || getAssetHubRegion(item))} · ${escapeHtml(item.optionSourceRole || item.type || item.group || "Options")}</span>
            <strong>${escapeHtml(item.name || "--")}</strong>
            <small>${escapeHtml(item.symbol || "--")} · ${escapeHtml(item.exchange || item.dataSource || "--")} · ${escapeHtml(item.date || "--")}</small>
            ${item.error ? `<p class="asset-quote-error">${escapeHtml(item.error)}</p>` : `
              <div class="asset-quote-price">
                <b>${formatGlobalValue(item.close)}</b>
                <em class="${assetHubTone(item)}">${escapeHtml(item.pct || "--")}</em>
              </div>
              <footer>${escapeHtml(metric.label)} <b>${formatGlobalVolume(metric.value)}</b></footer>
            `}
          </button>
        `;
      }).join("")}
    </div>
  `;
}
function renderOptionsHeroMarketPanelV2(model) {
  const summaryGroups = buildOptionsRegionalSummary(model.payload);
  const totalCount = summaryGroups.reduce((sum, { group }) => sum + group.items.length, 0);
  const activeFocus = getOptionsActiveFocus(model);
  const activeRegionLabel = activeFocus?.name || "\u5c1a\u672a\u9078\u53d6";
  return `
    <div class="options-hero-market-panel" id="options-regional-market">
      <section class="options-hero-region-map">
        <div class="asset-hub-group-heading">
          <div>
            <p class="panel-kicker">Options category map</p>
            <h4>\u9078\u64c7\u6b0a\u5730\u5340\u5e02\u5834</h4>
          </div>
          <div class="options-region-heading-meta">
            <span class="options-region-selected-pill">\u76ee\u524d\u5206\u6790\uff1a${escapeHtml(activeRegionLabel)}</span>
            <span>${totalCount} \u7b46</span>
          </div>
        </div>
        <div class="asset-hub-region-groups options-hero-region-groups">
          ${summaryGroups.map(({ group, usableCount, strongest, key }) => {
            const expanded = derivativesOptionsRegionalExpandedKeys.has(key);
            const active = isOptionsRegionFocusActive(key);
            const regionSelected = derivativesOptionsSelectedFocus === key;
            return `
              <section class="asset-hub-region-block options-region-block ${active ? "is-active" : ""} ${expanded ? "is-expanded" : "is-collapsed"}">
                <div class="asset-hub-region-head options-region-head">
                  <button class="options-region-focus-card ${regionSelected ? "is-active" : ""}" type="button" data-options-focus-key="${escapeHtml(key)}" aria-pressed="${regionSelected ? "true" : "false"}">
                    ${regionSelected ? `<span class="options-region-selected-chip">\u76ee\u524d\u5206\u6790</span>` : active ? `<span class="options-region-selected-chip">\u542b\u76ee\u524d\u6a19\u7684</span>` : ""}
                    <b>${escapeHtml(group.region)}</b>
                    <small>${usableCount} / ${group.items.length} \u7b46\u6709\u6548</small>
                    <em>${strongest ? `${strongest.symbol || "--"} ${strongest.pct || "--"}` : "\u8cc7\u6599\u540c\u6b65\u4e2d"}</em>
                  </button>
                  <button class="global-refresh asset-hub-region-toggle options-region-toggle" type="button" data-options-region-toggle="${escapeHtml(key)}" aria-expanded="${expanded ? "true" : "false"}">${expanded ? "\u6536\u5408" : "\u5c55\u958b"}</button>
                </div>
                ${expanded ? renderOptionsRegionAnalysisQuoteGrid(group.items, key, "\u9078\u64c7\u6b0a\u8cc7\u6599\u540c\u6b65\u4e2d\u3002") : ""}
              </section>
            `;
          }).join("")}
        </div>
      </section>
    </div>
  `;
}
function renderOptionsHeroMergedIntelligence(model) {
  const analysis = buildOptionsFocusAnalysis(model);
  const playbook = buildOptionsInvestorPlaybook(model, analysis);
  const optionLabel = getTaiwanOptionProductLabel(model.chain);
  const decisionFactors = model.decisionFactors || {};
  const hiddenFactorStatus = `${decisionFactors.readyCount || 0}/${decisionFactors.totalCount || 5}`;
  const strategies = buildOptionsStrategyRows(model);
  const topStrategy = strategies[0] || null;
  const putWall = model.oiWalls.putWall?.strike;
  const callWall = model.oiWalls.callWall?.strike;
  const skew = model.maxIv !== null && model.minIv !== null ? model.maxIv - model.minIv : null;
  const expiryText = model.expiryDays === null ? "待同步" : `${model.expiryDays} 天`;
  const decisionRangeText = `${optionsWhole(putWall)} - ${optionsWhole(callWall)}`;
  const decisionProbText = `\u591a ${analysis.probabilities.bullish}% / \u9707 ${analysis.probabilities.range}% / \u7a7a ${analysis.probabilities.bearish}%`;
  const actionRows = [
    ["交易節奏", playbook.priority],
    ["突破 / 失守", playbook.triggerText],
    ["權利金控管", playbook.premiumText],
    ["風險界線", playbook.riskText],
  ];

  return `
    <div class="options-hero-merged-intelligence">
      <section class="options-hero-module is-cone" id="options-risk-cone">
        ${renderOptionsRiskConeContent(model, analysis)}
      </section>
      ${renderOptionsAiRiskModuleDeck(model)}
      <section class="options-hero-module is-decision" id="options-decision-brief">
        <div class="asset-hub-group-heading">
          <div><p class="panel-kicker">AI Decision Brief</p><h4>AI 決策摘要</h4></div>
          <span>${escapeHtml(analysis.riskLight.label)} · ${analysis.riskScore}/100</span>
        </div>
        <div class="options-decision-summary-strip">
          <span><small>\u5e02\u5834\u72c0\u614b</small><b>${escapeHtml(playbook.stance)}</b></span>
          <span><small>\u5206\u6790\u6a19\u7684</small><b>${escapeHtml(analysis.focus.name)}</b></span>
          <span><small>\u53ef\u4ea4\u6613\u5340\u9593</small><b>${escapeHtml(decisionRangeText)}</b></span>
          <span><small>\u6a5f\u7387\u5206\u4f48</small><b>${escapeHtml(decisionProbText)}</b></span>
        </div>
        <div class="options-brief-grid is-compact">
          <section><small>目前位置</small><b>${optionsWhole(getOptionsUnderlyingPrice(model) ?? model.atmStrike)}</b><p>${escapeHtml(playbook.locationText)}</p></section>
          <section><small>價位邊界</small><b>${optionsWhole(putWall)} / ${optionsWhole(callWall)}</b><p>最大痛點 ${optionsWhole(model.maxPain)}，到期 ${escapeHtml(expiryText)}；靠近邊界時先看確認訊號。</p></section>
          <section><small>策略排序</small><b>${escapeHtml(topStrategy?.name || "--")}</b><p>${topStrategy ? `${topStrategy.score}/100，${topStrategy.evidence}` : "等待鏈資料、IV 與跨市場資料完成同步。"}</p></section>
          <section><small>資料信心</small><b>${analysis.confidenceScore}/100</b><p>${escapeHtml(`${optionLabel} ${model.rows.length ? `${model.rows.length} 檔` : "同步中"}；隱性決策因子 ${hiddenFactorStatus}。`)}</p></section>
        </div>
        <ul class="options-brief-actions is-compact">
          ${actionRows.map(([title, text]) => `<li><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></li>`).join("")}
        </ul>
        <div class="options-brief-lead is-${analysis.riskLight.tone}">
          <div>
            <small>核心結論</small>
            <strong>${escapeHtml(playbook.headline)}</strong>
            <p>${escapeHtml(playbook.summary)}</p>
          </div>
          <div class="options-brief-score">
            <span><b>${analysis.probabilities.bullish}%</b><small>多方</small></span>
            <span><b>${analysis.probabilities.bearish}%</b><small>空方</small></span>
            <span><b>${analysis.probabilities.range}%</b><small>震盪</small></span>
          </div>
        </div>
      </section>
      <section class="options-hero-module is-insights" id="options-insight-feed">
        <div class="asset-hub-group-heading">
          <div><p class="panel-kicker">AI Market Insights</p><h4>AI 即時洞察</h4></div>
          <span>${escapeHtml(analysis.focus.name)}</span>
        </div>
        ${renderOptionsInsightFeedContent(model, analysis)}
      </section>

      <div class="options-hero-regional-market is-hidden">
        ${renderAssetHubRegionalGroups(model.payload, "選擇權地區市場", () => true, "選擇權資料同步中。", {
          collapsible: true,
          expanded: false,
          toggleKey: "options-regional-market",
        })}
      </div>
    </div>
  `;
}
function renderOptionsAiRiskModuleDeck(model) {
  return `
    <section class="options-ai-risk-module-deck" aria-label="選擇權風險趨勢 AI 分析中心子模組">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI Risk Modules</p>
          <h4>風險趨勢分析模組</h4>
          <p class="chart-subtitle">整合波動率、希臘值、策略適配與風險控管；所有模組共用目前選取商品、逐履約價鏈、OI 分布與跨市場因子。</p>
        </div>
        <span>4 模組</span>
      </div>
      <div class="options-ai-risk-module-grid">
        ${renderOptionsVolatilityCenter(model, { embedded: true })}
        ${renderOptionsGreeksCenter(model, { embedded: true })}
        ${renderOptionsRiskDashboard(model, { embedded: true })}
        ${renderOptionsStrategyCenter(model, { embedded: true })}
      </div>
    </section>
  `;
}
function renderOptionsHeroDashboard(model) {
  const analysis = buildOptionsFocusAnalysis(model);
  const playbook = buildOptionsInvestorPlaybook(model, analysis);
  const analysisScopeLabel = getOptionsFocusScopeLabel(analysis.focus);
  const optionLabel = getTaiwanOptionProductLabel(model.chain);
  const primaryFocusKeys = ["txo", "sp500", "nasdaq"];
  return `
    <section class="section options-ai-dashboard" id="options-ai-center">
      <article class="panel-card options-terminal-card">
        <div class="options-terminal-head">
          <div>
            <p class="panel-kicker">Options AI Trend & Risk Intelligence Center</p>
            <h3>選擇權風險趨勢 AI 分析中心</h3>
            <p class="chart-subtitle">以 ${escapeHtml(optionLabel)}、TAIFEX 官方日報、Yahoo 後備資料、CBOE VIX、美股 Options Chain 與跨市場資料輸出風險觀察、情境推演與決策輔助；不以靜態文字替代真實資料。</p>
          </div>
          <span class="options-risk-light is-${analysis.riskLight.tone}">${escapeHtml(analysis.riskLight.label)}</span>
        </div>
        ${renderOptionsHeroMarketPanelV2(model)}
        <div class="options-today-grid">
          <section class="options-ai-direction is-${analysis.riskLight.tone}">
            <small>AI \u4eca\u65e5\u5e02\u5834\u5206\u6790 \u00b7 ${escapeHtml(analysisScopeLabel)} \u00b7 ${escapeHtml(analysis.focus.name)}</small>
            <strong>${escapeHtml(playbook.headline)}</strong>
            <p>${escapeHtml(playbook.setupText)}；AI 信心 ${analysis.confidenceScore}/100，風險分數 ${analysis.riskScore}/100。</p>
            <div class="options-probability-bars">
              ${[["多方", analysis.probabilities.bullish, "up"], ["空方", analysis.probabilities.bearish, "down"], ["震盪", analysis.probabilities.range, "flat"]].map(([label, value, tone]) => `
                <span class="is-${tone}"><b>${escapeHtml(label)}</b><i style="--bar:${Number(value) || 0}%"></i><em>${Number(value) || 0}%</em></span>
              `).join("")}
            </div>
          </section>
          <section class="options-risk-explain">
            <small>AI 風險燈號</small>
            <strong>${escapeHtml(analysis.riskLight.text)}</strong>
            <p>${escapeHtml(`${playbook.riskText} ${analysis.evidenceText}`)}</p>
          </section>
        </div>
        ${renderOptionsHeroMergedIntelligence(model)}
      </article>
    </section>
  `;
}
function renderOptionsChainTableClean(chain = {}, model = null) {
  const summary = chain.summary || {};
  const rows = pickTaiwanOptionRows(getOptionsChainRows(chain), summary.atmStrike, 22);
  const optionLabel = getTaiwanOptionProductLabel(chain);
  if (!rows.length) return `<p class="stock-detail-empty">${escapeHtml(optionLabel)}選擇權鏈資料同步中。</p>`;
  const selectedStrike = getSelectedOptionsStrike(rows, summary.atmStrike);
  const selectedKey = getOptionsStrikeKey(selectedStrike);
  const spotPrice = optionsNumber(chain.spot?.value ?? chain.underlyingPrice);
  let spotInserted = false;
  const renderSpotRow = () => `
    <tr class="tw-option-chain-spot-row" aria-label="現貨基準 ${optionsDecimal(spotPrice)}">
      <td colspan="9"><span>${optionsDecimal(spotPrice)}</span></td>
    </tr>
  `;
  const bodyRows = [];
  rows.forEach((row) => {
    if (spotPrice !== null && !spotInserted && Number(row.strike) >= spotPrice) {
      bodyRows.push(renderSpotRow());
      spotInserted = true;
    }
    const call = row.call || {};
    const put = row.put || {};
    const isAtm = Number(row.strike) === Number(summary.atmStrike);
    const strikeKey = getOptionsStrikeKey(row.strike);
    const isSelected = strikeKey === selectedKey;
    bodyRows.push(`
      <tr class="${[isAtm ? "is-atm" : "", isSelected ? "is-selected" : ""].filter(Boolean).join(" ")}"
        tabindex="0"
        role="button"
        aria-pressed="${isSelected ? "true" : "false"}"
        data-options-chain-strike="${escapeHtml(strikeKey)}">
        <td>${optionsDecimal(call.last ?? call.settlement)}</td>
        <td>${optionsDecimal(call.bid)} / ${optionsDecimal(call.ask)}</td>
        <td>${optionsWhole(call.volume)} / ${optionsWhole(call.openInterest)}</td>
        <td>${optionsPct(call.impliedVolatility)}</td>
        <td><strong>${optionsWhole(row.strike)}</strong></td>
        <td>${optionsDecimal(put.last ?? put.settlement)}</td>
        <td>${optionsDecimal(put.bid)} / ${optionsDecimal(put.ask)}</td>
        <td>${optionsWhole(put.volume)} / ${optionsWhole(put.openInterest)}</td>
        <td>${optionsPct(put.impliedVolatility)}</td>
      </tr>
    `);
    if (isSelected && model) {
      bodyRows.push(`
        <tr class="tw-option-chain-analysis-row">
          <td colspan="9">
            ${renderOptionsChainOiSummary(model, chain, { embedded: true })}
          </td>
        </tr>
      `);
    }
  });
  if (spotPrice !== null && !spotInserted) bodyRows.push(renderSpotRow());
  return `
    <div class="tw-option-chain-scroll">
      <table class="global-market-table tw-option-chain-table">
        <thead>
          <tr><th colspan="4">Call</th><th>履約價</th><th colspan="4">Put</th></tr>
          <tr><th>成交</th><th>Bid / Ask</th><th>量 / OI</th><th>IV</th><th>Strike</th><th>成交</th><th>Bid / Ask</th><th>量 / OI</th><th>IV</th></tr>
        </thead>
        <tbody>
          ${bodyRows.join("")}
        </tbody>
      </table>
    </div>
  `;
}
function renderOptionsChainSourceTabs(chain = {}) {
  const source = chain.source || {};
  const sourceUrl = source.officialReferenceUrl || source.primaryUrl || "https://www.taifex.com.tw/cht/3/optDailyMarketReport";
  return `
    <div class="tw-option-expiry-tabs options-source-tabs" aria-label="台灣選擇權官方日報">
      <button class="is-active" type="button" aria-pressed="true">
        <b>TAIFEX</b><small>官方日報</small>
      </button>
    </div>
    <p class="source-note options-source-note">
      目前來源：${escapeHtml(source.primary || "--")}
      ${sourceUrl && sourceUrl !== "#" ? ` · <a href="${safeUrl(sourceUrl)}" target="_blank" rel="noopener noreferrer">查看來源</a>` : ""}
    </p>
  `;
}
function getTaiwanOptionUnderlyingFromMarketItem(item = {}) {
  const candidates = [item.taifexCommodity, item.symbol, item.dataSymbol]
    .map((value) => String(value || "").trim().toUpperCase())
    .filter(Boolean);
  return candidates.find((symbol) => TAIWAN_OPTION_CHAIN_UNDERLYINGS.has(symbol)) || "";
}
function isOptionsMarketChainCandidateSymbol(symbol) {
  const clean = String(symbol || "").trim().toUpperCase();
  if (!clean) return false;
  if (TAIWAN_OPTION_CHAIN_UNDERLYINGS.has(clean) || ["STO", "ETO"].includes(clean)) return false;
  if (OPTIONS_MARKET_CHAIN_FUTURES_SYMBOLS.has(clean)) return true;
  if (/^(DERIBIT_(BTC|ETH)|BYBIT_(SOL|XRP))$/.test(clean)) return true;
  if (clean.startsWith("^")) return false;
  if (clean.includes(".TW") || clean.includes(".TWO") || clean.includes(".T")) return false;
  if (clean.includes("=F") || clean.includes("=X") || clean.endsWith("-USD")) return false;
  return /^[A-Z0-9.^_-]{1,12}$/.test(clean);
}
function getOptionsMarketOptionChainSymbols(item = {}) {
  const rawSymbol = String(item.symbol || item.dataSymbol || "").trim().toUpperCase();
  const configuredSymbol = String(item.optionChainSymbol || "").trim().toUpperCase();
  const candidates = [
    configuredSymbol,
    OPTIONS_MARKET_CHAIN_SYMBOL_ALIASES[rawSymbol],
    rawSymbol,
  ].filter(Boolean);
  const picked = candidates
    .map((symbol) => String(OPTIONS_MARKET_CHAIN_SYMBOL_ALIASES[String(symbol).toUpperCase()] || symbol).trim().toUpperCase())
    .filter(isOptionsMarketChainCandidateSymbol);
  return Array.from(new Set(picked));
}
function getOptionsMarketOptionChainSymbol(item = {}) {
  return getOptionsMarketOptionChainSymbols(item)[0] || "";
}
function attachOptionsMarketChainMeta(chain = {}, focusKey = "", item = null) {
  return {
    ...(chain || {}),
    marketFocusKey: focusKey || derivativesOptionsSelectedFocus || "",
    marketSourceSymbol: item?.symbol || item?.dataSymbol || "",
    marketSourceName: item?.name || "",
  };
}
function getOptionsRegionalFocusKeyBySymbol(model, symbol) {
  const target = String(symbol || "").trim().toUpperCase();
  if (!target) return "";
  const groups = buildOptionsRegionalSummary(model.payload);
  for (const { group, key } of groups) {
    const index = (group.items || []).findIndex((item) => String(item.taifexCommodity || item.symbol || "").trim().toUpperCase() === target);
    if (index >= 0) return getOptionsRegionItemFocusKey(key, group.items[index], index);
  }
  return "";
}
function getOptionsMarketChainSelectorContext(model) {
  const groups = buildOptionsRegionalSummary(model.payload);
  if (!groups.length) return null;
  const selectedKey = String(derivativesOptionsSelectedFocus || "");
  const selectedGroup = groups.find(({ key }) => selectedKey === key || selectedKey.startsWith(`${key}::item::`)) || groups[0];
  const items = selectedGroup.group.items || [];
  const selectedIndex = items.findIndex((item, index) => getOptionsRegionItemFocusKey(selectedGroup.key, item, index) === selectedKey);
  const selectedItem = selectedIndex >= 0 ? items[selectedIndex] : null;
  return { groups, selectedGroup, items, selectedIndex, selectedItem };
}
function getOptionsMarketChainItemForFocus(model) {
  const context = getOptionsMarketChainSelectorContext(model);
  if (!context) return null;
  const supportsVerifiedChain = (item) => Boolean(getTaiwanOptionUnderlyingFromMarketItem(item) || getOptionsMarketOptionChainSymbol(item));
  if (context.selectedItem && supportsVerifiedChain(context.selectedItem)) return context.selectedItem;
  const selectedSymbol = String(context.selectedItem?.symbol || context.selectedItem?.dataSymbol || "").toUpperCase();
  const selectedRole = String(context.selectedItem?.optionSourceRole || "");
  const isAggregateEntry = Boolean(context.selectedItem) && (
    ["STO", "ETO"].includes(selectedSymbol)
    || selectedRole.includes("彙總")
    || String(context.selectedItem?.name || "").includes("彙總")
  );
  if (isAggregateEntry || !context.selectedItem) {
    return (context.items || []).find(supportsVerifiedChain) || context.selectedItem || null;
  }
  return context.selectedItem;
}
