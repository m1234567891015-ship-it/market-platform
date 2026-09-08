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
function renderOptionsMarketChainSelector(model) {
  const context = getOptionsMarketChainSelectorContext(model);
  if (!context) return "";
  const { groups, selectedGroup, items, selectedItem } = context;
  const selectedMetric = selectedItem ? getAssetHubMetric(selectedItem) : null;
  const selectedOfficial = getTaiwanOptionUnderlyingFromMarketItem(selectedItem || {});
  const selectedSummary = selectedItem ? `
    <div class="options-market-chain-selected">
      <span><small>目前商品</small><b>${escapeHtml(selectedItem.name || selectedItem.symbol || "--")}</b><em>${escapeHtml(selectedItem.symbol || selectedItem.dataSymbol || "--")}</em></span>
      <span><small>來源 / 角色</small><b>${escapeHtml(selectedItem.exchange || selectedItem.dataSource || "--")}</b><em>${escapeHtml(selectedItem.optionSourceRole || selectedItem.type || "--")}</em></span>
      <span><small>價格 / 漲跌</small><b class="${assetHubTone(selectedItem)}">${selectedItem.error ? "--" : formatGlobalValue(selectedItem.close)}</b><em>${selectedItem.error ? "資料待確認" : escapeHtml(selectedItem.pct || "--")}</em></span>
      <span><small>${escapeHtml(selectedMetric?.label || "量能")}</small><b>${formatGlobalVolume(selectedMetric?.value)}</b><em>${selectedOfficial ? "可切官方鏈" : "行情資料"}</em></span>
    </div>
  ` : `
    <div class="options-market-chain-selected">
      <span><small>目前分類</small><b>${escapeHtml(selectedGroup.group.region)}</b><em>${selectedGroup.usableCount} / ${selectedGroup.group.items.length} 筆有效</em></span>
      <span><small>顯示方式</small><b>分類商品清單</b><em>點選商品後更新 AI 分析</em></span>
      <span><small>官方逐履約價</small><b>TXO / TFO / TEO / T50O / CDO / DVO / DHO</b><em>選到台灣官方商品時切換</em></span>
      <span><small>資料規則</small><b>不補假值</b><em>缺資料保留狀態</em></span>
    </div>
  `;
  return `
    <div class="options-market-chain-selector" aria-label="市場選擇權鏈分類與商品切換">
      <div class="options-market-chain-categories">
        ${groups.map(({ group, usableCount, key, strongest }) => {
          const active = selectedGroup.key === key;
          return `
            <button class="${active ? "is-active" : ""}" type="button" data-options-focus-key="${escapeHtml(key)}" aria-pressed="${active ? "true" : "false"}">
              <b>${escapeHtml(group.region)}</b>
              <small>${usableCount}/${group.items.length}</small>
              <em>${strongest ? `${strongest.symbol || "--"} ${strongest.pct || "--"}` : "同步中"}</em>
            </button>
          `;
        }).join("")}
      </div>
      ${selectedSummary}
      <div class="options-market-chain-products" aria-label="${escapeHtml(selectedGroup.group.region)}商品清單">
        ${items.map((item, index) => {
          const itemKey = getOptionsRegionItemFocusKey(selectedGroup.key, item, index);
          const active = derivativesOptionsSelectedFocus === itemKey;
          const officialUnderlying = getTaiwanOptionUnderlyingFromMarketItem(item);
          return `
            <button class="${active ? "is-active" : ""}" type="button"
              data-options-focus-key="${escapeHtml(itemKey)}"
              ${officialUnderlying ? `data-options-chain-underlying="${escapeHtml(officialUnderlying)}"` : ""}
              aria-pressed="${active ? "true" : "false"}">
              <span>
                <small>${escapeHtml(item.optionSubcategory || item.optionSourceRole || selectedGroup.group.region)}</small>
                <b>${escapeHtml(item.name || item.symbol || "--")}</b>
                <em>${escapeHtml(item.symbol || item.dataSymbol || "--")} · ${escapeHtml(item.exchange || item.dataSource || "--")}</em>
              </span>
              <strong class="${assetHubTone(item)}">${item.error ? "--" : formatGlobalValue(item.close)}</strong>
              <i>${officialUnderlying ? "官方鏈" : escapeHtml(item.pct || "--")}</i>
            </button>
          `;
        }).join("") || `<p class="stock-detail-empty">此分類資料同步中。</p>`}
      </div>
    </div>
  `;
}
function renderOptionsOfficialTaiwanChainPanel(model) {
  const chain = model.chain || {};
  const chainError = chain.error || "";
  return `
    <div class="asset-hub-group-heading options-chain-table-heading">
      <div>
        <p class="panel-kicker">Option chain table</p>
        <h5>${escapeHtml(getTaiwanOptionProductLabel(chain))}逐履約價資料</h5>
        <p class="chart-subtitle">官方逐履約價鏈會套用選取履約價、現貨基準線、OI 分布分析與價內價外判讀。</p>
      </div>
      <span>${escapeHtml(chain.selectedExpiry || "--")}</span>
    </div>
    ${renderOptionsChainSourceTabs(chain)}
    ${renderTaiwanOptionExpiryTabs(chain)}
    ${chainError ? `<p class="stock-detail-empty">${escapeHtml(chainError)}</p>` : `
      <div class="tw-option-expiry-summary">
        <span>目前到期月份整體摘要</span>
        ${renderOptionsChainStats(model, "is-compact")}
      </div>
      ${renderOptionsSpotBenchmarkStrip(chain)}
      ${renderOptionsChainTableClean(chain, model)}
    `}
  `;
}
function formatMarketOptionChainIv(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  const pct = Math.abs(parsed) <= 3 ? parsed * 100 : parsed;
  return `${pct.toFixed(1)}%`;
}
function formatMarketOptionContractPrice(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  return parsed.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function pairMarketOptionContracts(chain = {}) {
  const calls = Array.isArray(chain.calls) ? chain.calls : [];
  const puts = Array.isArray(chain.puts) ? chain.puts : [];
  const map = new Map();
  calls.forEach((contract) => {
    const strike = parseMarketNumber(contract.strike);
    if (!Number.isFinite(strike)) return;
    const key = String(strike);
    map.set(key, { ...(map.get(key) || {}), strike, call: contract });
  });
  puts.forEach((contract) => {
    const strike = parseMarketNumber(contract.strike);
    if (!Number.isFinite(strike)) return;
    const key = String(strike);
    map.set(key, { ...(map.get(key) || {}), strike, put: contract });
  });
  return [...map.values()].sort((left, right) => left.strike - right.strike);
}
function normalizeMarketOptionContractForOi(contract = {}) {
  return {
    last: contract.lastPrice,
    settlement: contract.lastPrice,
    bid: contract.bid,
    ask: contract.ask,
    volume: contract.volume,
    openInterest: contract.openInterest,
    impliedVolatility: contract.impliedVolatility,
    delta: contract.delta,
    gamma: contract.gamma,
    theta: contract.theta,
    vega: contract.vega,
  };
}
function buildOptionsModelFromPublicChain(baseModel, chain = {}) {
  const pairedRows = pairMarketOptionContracts(chain);
  const chainRows = pairedRows.map((row) => ({
    strike: row.strike,
    call: normalizeMarketOptionContractForOi(row.call || {}),
    put: normalizeMarketOptionContractForOi(row.put || {}),
  }));
  const distribution = chainRows.map((row) => ({
    strike: row.strike,
    callOpenInterest: row.call.openInterest,
    putOpenInterest: row.put.openInterest,
    callVolume: row.call.volume,
    putVolume: row.put.volume,
  }));
  const spot = parseMarketNumber(chain.price);
  const atmStrike = chainRows.reduce((best, row) => {
    if (!Number.isFinite(spot)) return best;
    if (best === null) return row.strike;
    return Math.abs(row.strike - spot) < Math.abs(best - spot) ? row.strike : best;
  }, null);
  const localMaxPain = calculateOptionsLocalMaxPain(chainRows);
  const callOi = sumOptionFinite(distribution.map((row) => row.callOpenInterest));
  const putOi = sumOptionFinite(distribution.map((row) => row.putOpenInterest));
  const callVolume = sumOptionFinite(distribution.map((row) => row.callVolume));
  const putVolume = sumOptionFinite(distribution.map((row) => row.putVolume));
  const ivValues = chainRows
    .flatMap((row) => [row.call.impliedVolatility, row.put.impliedVolatility])
    .map(optionsNumber)
    .filter((value) => value !== null && value > 0);
  const avgIv = ivValues.length ? ivValues.reduce((sum, value) => sum + value, 0) / ivValues.length : null;
  const maxIv = ivValues.length ? Math.max(...ivValues) : null;
  const minIv = ivValues.length ? Math.min(...ivValues) : null;
  const summary = {
    callOpenInterest: callOi,
    putOpenInterest: putOi,
    putCallRatio: callOi > 0 ? putOi / callOi : null,
    volumePutCallRatio: callVolume > 0 ? putVolume / callVolume : null,
    maxPain: localMaxPain?.strike ?? atmStrike,
    atmStrike,
  };
  const pseudoChain = {
    chain: chainRows,
    distribution,
    summary,
    spot: {
      value: Number.isFinite(spot) ? spot : null,
      change: chain.change,
      pct: chain.pct,
    },
    underlyingPrice: Number.isFinite(spot) ? spot : null,
    selectedExpiry: formatAssetHubExpiration(chain.selectedExpiration),
    selectedExpiryDate: formatAssetHubExpiration(chain.selectedExpiration),
    source: {
      primary: chain.source || "Cboe Delayed Quotes Options",
      primaryUrl: chain.sourceUrl || "",
    },
  };
  const oiWalls = getOptionsMaxOiWalls(pseudoChain);
  return {
    ...baseModel,
    chain: pseudoChain,
    rows: chainRows,
    distribution,
    ivValues,
    avgIv,
    maxIv,
    minIv,
    callOi,
    putOi,
    pcr: summary.putCallRatio,
    volumePcr: summary.volumePutCallRatio,
    maxPain: summary.maxPain,
    atmStrike,
    oiWalls,
    publicChain: chain,
  };
}
function pickMarketOptionChainRows(rows = [], price = null, limit = 28) {
  if (rows.length <= limit) return rows;
  const spot = parseMarketNumber(price);
  if (!Number.isFinite(spot)) return rows.slice(0, limit);
  const centerIndex = rows.reduce((bestIndex, row, index) => {
    const bestDistance = Math.abs((rows[bestIndex]?.strike || 0) - spot);
    const distance = Math.abs((row.strike || 0) - spot);
    return distance < bestDistance ? index : bestIndex;
  }, 0);
  const half = Math.floor(limit / 2);
  const start = Math.max(0, Math.min(centerIndex - half, rows.length - limit));
  return rows.slice(start, start + limit);
}
function renderOptionsMarketOptionExpirationSelect(chain = {}, chainSymbol = "", focusKey = "") {
  const expirations = Array.isArray(chain.expirationDates) ? chain.expirationDates : [];
  if (!expirations.length) return "";
  const selected = String(chain.selectedExpiration || "");
  return `
    <label class="tw-option-expiry-select options-market-expiry-select">
      <select data-options-market-expiration-select data-options-market-chain-symbol="${escapeHtml(chainSymbol)}" data-options-market-focus-key="${escapeHtml(focusKey)}" aria-label="選擇公開選擇權到期日">
        ${expirations.map((expiration) => {
          const value = String(expiration);
          return `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(formatAssetHubExpiration(expiration))}</option>`;
        }).join("")}
      </select>
    </label>
  `;
}
function renderOptionsMarketOptionChainTable(chain = {}, analysisModel = null) {
  const paired = pairMarketOptionContracts(chain);
  const rows = pickMarketOptionChainRows(paired, chain.price, 30);
  if (!rows.length) return `<p class="stock-detail-empty">此商品目前沒有可顯示的逐履約價 Call / Put 資料。</p>`;
  const spot = parseMarketNumber(chain.price);
  const atmStrike = rows.reduce((best, row) => {
    if (!Number.isFinite(spot)) return best;
    if (!best) return row.strike;
    return Math.abs(row.strike - spot) < Math.abs(best - spot) ? row.strike : best;
  }, null);
  const selectedStrike = getSelectedOptionsStrike(rows, atmStrike ?? spot);
  const selectedKey = getOptionsStrikeKey(selectedStrike);
  let spotInserted = false;
  const renderSpotRow = () => `
    <tr class="tw-option-chain-spot-row options-market-spot-row" aria-label="現貨基準 ${formatGlobalValue(spot)}">
      <td colspan="9"><span>${formatGlobalValue(spot)}</span></td>
    </tr>
  `;
  const bodyRows = [];
  rows.forEach((row) => {
    if (Number.isFinite(spot) && !spotInserted && Number(row.strike) >= spot) {
      bodyRows.push(renderSpotRow());
      spotInserted = true;
    }
    const call = row.call || {};
    const put = row.put || {};
    const isAtm = atmStrike !== null && Number(row.strike) === Number(atmStrike);
    const strikeKey = getOptionsStrikeKey(row.strike);
    const isSelected = strikeKey === selectedKey;
    bodyRows.push(`
      <tr class="${[isAtm ? "is-atm" : "", isSelected ? "is-selected" : ""].filter(Boolean).join(" ")}"
        tabindex="0"
        role="button"
        aria-pressed="${isSelected ? "true" : "false"}"
        data-options-chain-strike="${escapeHtml(strikeKey)}">
        <td>${formatMarketOptionContractPrice(call.lastPrice)}</td>
        <td>${formatMarketOptionContractPrice(call.bid)} / ${formatMarketOptionContractPrice(call.ask)}</td>
        <td>${formatGlobalVolume(call.volume)} / ${formatGlobalVolume(call.openInterest)}</td>
        <td>${formatMarketOptionChainIv(call.impliedVolatility)}</td>
        <td><strong>${formatGlobalValue(row.strike)}</strong></td>
        <td>${formatMarketOptionContractPrice(put.lastPrice)}</td>
        <td>${formatMarketOptionContractPrice(put.bid)} / ${formatMarketOptionContractPrice(put.ask)}</td>
        <td>${formatGlobalVolume(put.volume)} / ${formatGlobalVolume(put.openInterest)}</td>
        <td>${formatMarketOptionChainIv(put.impliedVolatility)}</td>
      </tr>
    `);
    if (isSelected && analysisModel) {
      bodyRows.push(`
        <tr class="tw-option-chain-analysis-row options-market-analysis-row">
          <td colspan="9">
            ${renderOptionsChainOiSummary(analysisModel, analysisModel.chain, { embedded: true, rowLimit: 40, sourceLabel: analysisModel.chain?.source?.primary || "Cboe 公開鏈" })}
          </td>
        </tr>
      `);
    }
  });
  if (Number.isFinite(spot) && !spotInserted) bodyRows.push(renderSpotRow());
  return `
    <div class="tw-option-chain-scroll options-market-public-chain-scroll">
      <table class="global-market-table tw-option-chain-table options-market-public-chain-table">
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
function renderOptionsMarketOptionChainPanel(model) {
  const context = getOptionsMarketChainSelectorContext(model);
  if (!context) return `<p class="stock-detail-empty">選擇權市場資料同步中。</p>`;
  const { selectedGroup } = context;
  const targetItem = getOptionsMarketChainItemForFocus(model);
  const chainSymbol = getOptionsMarketOptionChainSymbol(targetItem || {});
  const chain = model.publicChain || {};
  const chainMatches = chainSymbol && String(chain.symbol || "").toUpperCase() === chainSymbol && (!chain.marketFocusKey || chain.marketFocusKey === derivativesOptionsSelectedFocus);
  const callOi = Number(chain.summary?.callOpenInterest) || 0;
  const putOi = Number(chain.summary?.putOpenInterest) || 0;
  const putCallRatio = callOi > 0 ? putOi / callOi : null;
  const publicAnalysisModel = chainMatches && !chain.error ? buildOptionsModelFromPublicChain(model, chain) : null;
  if (!chainSymbol) {
    return `
      <section class="options-market-chain-data-panel">
        <div class="asset-hub-group-heading">
          <div>
            <p class="panel-kicker">Option chain table</p>
            <h5>${escapeHtml(targetItem?.name || selectedGroup.group.region)}逐履約價資料</h5>
            <p class="chart-subtitle">${escapeHtml(targetItem?.optionChainUnavailableReason || "此商品目前沒有可驗證的掛牌逐履約價來源；不使用其他商品代理 Call / Put 表格。")}</p>
          </div>
          <span>未接入本商品來源</span>
        </div>
      </section>
    `;
  }
  const errorText = chain.error && chainMatches
    ? `此商品本身逐履約價暫時無法取得：${chain.error}`
    : `正在抓取 ${escapeHtml(chainSymbol)} 的真實公開 Call / Put 逐履約價資料。`;
  if (!chainMatches || chain.error) {
    return `
      <section class="options-market-chain-data-panel">
        <div class="asset-hub-group-heading">
          <div>
            <p class="panel-kicker">Option chain table</p>
            <h5>${escapeHtml(targetItem?.name || chainSymbol)}逐履約價資料</h5>
            <p class="chart-subtitle">${escapeHtml(errorText)}</p>
          </div>
          <span>${escapeHtml(chainSymbol)}</span>
        </div>
      </section>
    `;
  }
  const lockedSourceNote = chain.sourceLocked ? "API 已鎖定商品本身 Call / Put 逐履約價來源；不使用代理商品鏈、不自動改抓其他來源。" : "";
  return `
    <section class="options-market-chain-data-panel" aria-label="市場選擇權鏈下方資料清單">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Option chain table</p>
          <h5>${escapeHtml(targetItem?.name || chain.name || chainSymbol)}逐履約價資料</h5>
          <p class="chart-subtitle">下方表格承接上方商品切換，使用 ${escapeHtml(chain.source || "Cboe Delayed Quotes Options")} 的 Call / Put / Strike 資料。${escapeHtml(lockedSourceNote)}</p>
        </div>
        <span>${chain.sourceLocked ? "API 已鎖定" : escapeHtml(formatAssetHubExpiration(chain.selectedExpiration))}</span>
      </div>
      <div class="options-market-chain-data-summary">
        <span><small>標的 / root</small><b>${escapeHtml(chain.symbol || chainSymbol)}</b><em>${escapeHtml(targetItem?.symbol || "--")}</em></span>
        <span><small>現價 / 漲跌</small><b class="${assetHubTone({ pct: chain.pct })}">${formatGlobalValue(chain.price)}</b><em>${Number.isFinite(parseMarketNumber(chain.pct)) ? `${parseMarketNumber(chain.pct).toFixed(2)}%` : "--"}</em></span>
        <span><small>Call / Put</small><b>${chain.summary?.callCount ?? "--"} / ${chain.summary?.putCount ?? "--"}</b><em>合約數</em></span>
        <span><small>OI Put / Call</small><b>${putCallRatio === null ? "--" : putCallRatio.toFixed(2)}</b><em>${formatGlobalVolume(putOi)} / ${formatGlobalVolume(callOi)}</em></span>
      </div>
      ${renderOptionsMarketOptionExpirationSelect(chain, chainSymbol, derivativesOptionsSelectedFocus)}
      ${renderOptionsMarketOptionChainTable(chain, publicAnalysisModel)}
    </section>
  `;
}
function renderOptionsMarketWorkbench(model) {
  const chain = model.chain || {};
  const optionLabel = getTaiwanOptionProductLabel(chain);
  const marketContext = getOptionsMarketChainSelectorContext(model);
  const selectedOfficialUnderlying = getTaiwanOptionUnderlyingFromMarketItem(getOptionsMarketChainItemForFocus(model) || marketContext?.selectedItem || {});
  return `
    <section class="section options-market-workbench" id="asset-options">
      <div class="asset-hub-layout asset-hub-options-layout">
        <article class="panel-card tw-option-chain-card">
          <div class="asset-hub-group-heading">
            <div>
              <p class="panel-kicker">Market option chain</p>
              <h4>市場選擇權鏈</h4>
              <p class="chart-subtitle">依選擇權地區市場清單切換分類與商品；${escapeHtml(optionLabel)} 官方逐履約價鏈以 TAIFEX 官方日報優先，無資料時使用 Yahoo 後備。</p>
            </div>
            <span>${escapeHtml(chain.selectedExpiry || "--")} ${escapeHtml(chain.selectedExpiryDate || "")}</span>
          </div>
          ${renderOptionsMarketChainSelector(model)}
          ${selectedOfficialUnderlying ? renderOptionsOfficialTaiwanChainPanel(model) : renderOptionsMarketOptionChainPanel(model)}
        </article>
      </div>
      <div id="options-online-data">
        ${renderAssetHubOnlineTable(model.payload, "選擇權觀察")}
      </div>
    </section>
  `;
}
function renderOptionsSpotBenchmarkStrip(chain = {}) {
  const spot = chain.spot || {};
  const value = optionsNumber(spot.value);
  if (value === null) return "";
  const change = optionsNumber(spot.change);
  const pct = optionsNumber(spot.pct);
  const high = optionsNumber(spot.high);
  const low = optionsNumber(spot.low);
  const volumeBillion = optionsNumber(spot.volumeBillion);
  const toneClass = change === null ? "" : change >= 0 ? "is-up" : "is-down";
  const changeText = change === null
    ? "--"
    : `${change >= 0 ? "▲ " : "▼ "}${optionsDecimal(Math.abs(change))}${pct === null ? "" : ` (${Math.abs(pct).toFixed(2)}%)`}`;
  return `
    <div class="tw-option-spot-benchmark">
      <span><small>加權股價指數</small><b>${optionsDecimal(value)}</b></span>
      <span class="${toneClass}"><small>漲跌(%)</small><b>${escapeHtml(changeText)}</b></span>
      <span><small>最高</small><b>${optionsDecimal(high)}</b></span>
      <span><small>最低</small><b>${optionsDecimal(low)}</b></span>
      <span><small>成交量(億)</small><b>${optionsDecimal(volumeBillion)}</b></span>
    </div>
  `;
}
function renderOptionsVolatilityCenter(model, options = {}) {
  const skew = model.maxIv !== null && model.minIv !== null ? model.maxIv - model.minIv : null;
  const wrapper = options.embedded ? "section" : "article";
  const wrapperClass = options.embedded
    ? "options-ai-submodule asset-option-sentiment options-volatility-card"
    : "panel-card asset-option-sentiment options-volatility-card";
  return `
    <${wrapper} class="${wrapperClass}">
      <p class="panel-kicker">Volatility Center</p>
      <h4>波動率中心</h4>
      <strong>${Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--"}</strong>
      <span>平均 IV ${optionsPct(model.avgIv)} · IV 區間 ${optionsPct(model.minIv)} / ${optionsPct(model.maxIv)}</span>
      <small>Skew 估計 ${optionsPct(skew)}；VIX 與 TXO IV 同步後用於波動率風險判讀。</small>
    </${wrapper}>
  `;
}
function renderOptionsGreeksCenter(model, options = {}) {
  const gammaRisk = model.expiryDays !== null && model.expiryDays <= 7 && model.riskScore >= 60 ? "偏高" : model.expiryDays !== null && model.expiryDays <= 14 ? "中等" : "觀察";
  const vegaRisk = model.avgIv !== null && model.avgIv * 100 >= 25 ? "偏高" : model.avgIv !== null ? "中等" : "待 IV";
  const thetaRisk = model.expiryDays !== null && model.expiryDays <= 7 ? "加速" : model.expiryDays !== null ? "一般" : "待到期日";
  const wrapper = options.embedded ? "section" : "article";
  const wrapperClass = options.embedded
    ? "options-ai-submodule options-greeks-card"
    : "panel-card options-greeks-card";
  return `
    <${wrapper} class="${wrapperClass}">
      <div class="asset-hub-group-heading">
        <div><p class="panel-kicker">Greeks Center</p><h4>希臘值風險中心</h4></div>
        <span>模型估算</span>
      </div>
      <div class="options-output-grid">
        <span><small>Gamma Risk</small><b>${escapeHtml(gammaRisk)}</b><em>到期 ${model.expiryDays ?? "--"} 天</em></span>
        <span><small>Vega Risk</small><b>${escapeHtml(vegaRisk)}</b><em>平均 IV ${optionsPct(model.avgIv)}</em></span>
        <span><small>Theta Decay</small><b>${escapeHtml(thetaRisk)}</b><em>時間價值</em></span>
        <span><small>Delta Bias</small><b>${escapeHtml(model.direction)}</b><em>由 PCR / VIX 推估</em></span>
      </div>
      <div class="options-greek-language-grid">
        <section><small>Delta</small><b>${escapeHtml(model.direction)}</b><p>${model.direction === "偏多" ? "價格上行敏感度較需要確認壓力區突破。" : model.direction === "偏空" ? "價格下行敏感度提高，避險部位優先控管成本。" : "方向敏感度未明顯偏向單邊，先看區間邊界。"}</p></section>
        <section><small>Gamma</small><b>${escapeHtml(gammaRisk)}</b><p>${model.expiryDays !== null && model.expiryDays <= 7 ? "接近到期時 Delta 變化加速，不適合忽略跳動風險。" : "距到期仍有緩衝，可用 OI 牆觀察價格牽引。"}</p></section>
        <section><small>Theta</small><b>${escapeHtml(thetaRisk)}</b><p>${model.expiryDays !== null && model.expiryDays <= 7 ? "時間價值衰減加快，買方需避免只看方向。" : "時間價值壓力中性，可搭配策略適配度觀察。"}</p></section>
        <section><small>Vega</small><b>${escapeHtml(vegaRisk)}</b><p>${model.avgIv !== null && model.avgIv >= 0.25 ? "權利金對 IV 回落較敏感，裸賣與追買都要控管。" : "波動率未顯著昂貴，仍需用 VIX 與 Skew 交叉確認。"}</p></section>
      </div>
      <p class="stock-theory-note">Greeks 為風險輔助欄位；若資料源未提供正式 Greeks，僅以 IV、OI、到期日與方向分數估算，不假造逐檔 Delta / Gamma。</p>
    </${wrapper}>
  `;
}
function getOptionsStrategyGrade(score) {
  if (score >= 76) return { label: "高適配", tone: "green" };
  if (score >= 62) return { label: "可觀察", tone: "blue" };
  if (score >= 48) return { label: "條件不足", tone: "yellow" };
  return { label: "暫緩", tone: "red" };
}
function buildOptionsStrategyRows(model) {
  const isBullish = model.direction === "偏多";
  const isBearish = model.direction === "偏空";
  const isRange = model.direction === "震盪";
  const vixValue = Number.isFinite(model.vixValue) ? model.vixValue : null;
  const hasVol = model.avgIv !== null || vixValue !== null;
  const hasOiWalls = Boolean(model.oiWalls.callWall || model.oiWalls.putWall);
  const shortExpiry = model.expiryDays !== null && model.expiryDays <= 7;
  const mediumExpiry = model.expiryDays !== null && model.expiryDays > 7 && model.expiryDays <= 30;
  const ivHigh = model.avgIv !== null && model.avgIv >= 0.22;
  const vixHigh = vixValue !== null && vixValue >= 22;
  const pcrText = model.pcr === null ? "--" : model.pcr.toFixed(2);
  const vixText = vixValue === null ? "--" : vixValue.toFixed(2);
  const ivText = optionsPct(model.avgIv);
  const expiryText = model.expiryDays === null ? "--" : `${model.expiryDays} 天`;
  const score = (value) => Math.round(clampAssetHubScore(value, 12, 96));
  const rows = [
    {
      key: "bull_call_spread",
      name: "買權價差",
      role: "偏多突破",
      score: score(34 + (isBullish ? 24 : 0) + (model.riskScore < 66 ? 12 : model.riskScore < 78 ? 4 : -8) + (vixValue !== null && vixValue <= 22 ? 8 : 0) + (model.pcr !== null && model.pcr < 1 ? 6 : 0) + (model.macroItems.length ? 4 : 0)),
      evidence: `方向 ${model.direction}，PCR ${pcrText}，VIX ${vixText}，風險分數 ${model.riskScore}/100`,
      control: "只在支撐未跌破、買權 OI 壓力可控時評估；紅燈或跳空風險升高時降級。",
    },
    {
      key: "iron_condor",
      name: "賣出鐵禿鷹",
      role: "區間收斂",
      score: score(28 + (isRange ? 24 : 0) + (ivHigh ? 12 : 0) + (mediumExpiry ? 8 : 0) + (model.riskScore >= 45 && model.riskScore <= 70 ? 8 : 0) - (model.riskScore > 80 ? 14 : 0)),
      evidence: `方向 ${model.direction}，平均 IV ${ivText}，到期 ${expiryText}，最大痛點 ${optionsWhole(model.maxPain)}`,
      control: "必須先估最大損失與保證金壓力；VIX 快速上升或價格靠近 OI 牆時不追價。",
    },
    {
      key: "protective_put",
      name: "保護性 Put",
      role: "下檔避險",
      score: score(36 + (model.riskScore >= 66 ? 20 : 0) + (isBearish ? 12 : 0) + (vixHigh ? 8 : 0) + (model.oiWalls.putWall ? 5 : 0)),
      evidence: `風險燈 ${model.riskLight.label}，VIX ${vixText}，Put OI 牆 ${optionsWhole(model.oiWalls.putWall?.strike)}`,
      control: "用於持倉避險，不當作單邊追空訊號；IV 過高時需控管權利金成本。",
    },
    {
      key: "bear_put_spread",
      name: "賣權價差",
      role: "偏空防守",
      score: score(32 + (isBearish ? 24 : 0) + (model.pcr !== null && model.pcr > 1.05 ? 8 : 0) + (model.riskScore >= 55 ? 8 : 0) + (hasOiWalls ? 4 : 0)),
      evidence: `方向 ${model.direction}，PCR ${pcrText}，支撐 ${optionsWhole(model.oiWalls.putWall?.strike)}，阻力 ${optionsWhole(model.oiWalls.callWall?.strike)}`,
      control: "需搭配停損價與最大損失；若指數回到最大痛點附近，策略分數自動降級。",
    },
    {
      key: "long_straddle_strangle",
      name: "跨式 / 勒式",
      role: "事件波動",
      score: score(26 + (model.riskScore >= 75 ? 18 : 0) + (shortExpiry ? 8 : 0) + (vixHigh ? 8 : 0) + (hasVol ? 6 : 0) - (model.avgIv !== null && model.avgIv > 0.32 ? 8 : 0)),
      evidence: `風險分數 ${model.riskScore}/100，到期 ${expiryText}，平均 IV ${ivText}，VIX ${vixText}`,
      control: "只代表波動條件可追蹤；若 IV 已明顯昂貴，需要確認事件後波動仍可能擴張。",
    },
    {
      key: "calendar_diagonal",
      name: "日曆 / 對角價差",
      role: "時間價值",
      score: score(30 + (isRange ? 12 : 0) + (model.avgIv !== null ? 8 : 0) + (model.expiryDays !== null && model.expiryDays >= 14 ? 10 : 0) + (model.riskScore < 70 ? 6 : -6)),
      evidence: `方向 ${model.direction}，到期 ${expiryText}，平均 IV ${ivText}，信心 ${model.confidenceScore}/100`,
      control: "適合用於時間價值配置；若近月 Gamma 風險升高，需縮小部位或改用保護性結構。",
    },
  ];
  return rows
    .map((row) => ({ ...row, grade: getOptionsStrategyGrade(row.score) }))
    .sort((left, right) => right.score - left.score);
}
function getOptionsActiveStrategy(strategies = []) {
  const active = strategies.find((strategy) => strategy.key === derivativesOptionsSelectedStrategy) || strategies[0] || null;
  if (active && derivativesOptionsSelectedStrategy !== active.key) derivativesOptionsSelectedStrategy = active.key;
  return active;
}
function renderOptionsStrategyDetail(strategy, model) {
  if (!strategy) return "";
  const rows = [
    ["成立條件", strategy.evidence],
    ["風險限制", strategy.control],
    ["關鍵價位", `Put OI 支撐 ${optionsWhole(model.oiWalls.putWall?.strike)}，Call OI 壓力 ${optionsWhole(model.oiWalls.callWall?.strike)}，最大痛點 ${optionsWhole(model.maxPain)}。`],
    ["資料依據", `PCR ${optionsDecimal(model.pcr)}，平均 IV ${optionsPct(model.avgIv)}，VIX ${Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--"}，到期 ${model.expiryDays ?? "--"} 天。`],
  ];
  return `
    <div class="options-strategy-detail" data-options-strategy-detail>
      <div>
        <p class="panel-kicker">Selected Strategy</p>
        <h5>${escapeHtml(strategy.name)} · ${escapeHtml(strategy.role)}</h5>
        <span class="options-strategy-detail-score is-${strategy.grade.tone}">${strategy.score}/100 · ${escapeHtml(strategy.grade.label)}</span>
      </div>
      <div class="options-strategy-detail-grid">
        ${rows.map(([title, text]) => `<section><small>${escapeHtml(title)}</small><p>${escapeHtml(text)}</p></section>`).join("")}
      </div>
    </div>
  `;
}
function renderOptionsStrategyCenter(model, options = {}) {
  const strategies = buildOptionsStrategyRows(model);
  const activeStrategy = getOptionsActiveStrategy(strategies);
  const optionLabel = getTaiwanOptionProductLabel(model.chain);
  const wrapper = options.embedded ? "section" : "article";
  const wrapperClass = options.embedded
    ? "options-ai-submodule options-strategy-card is-wide"
    : "panel-card options-strategy-card";
  const readiness = [
    [`${optionLabel} 鏈`, model.rows.length ? `${model.rows.length} 履約價` : "待資料", model.rows.length ? "已接入" : "未完成"],
    ["OI / PCR", model.pcr !== null ? `PCR ${model.pcr.toFixed(2)}` : "待 PCR", model.callOi !== null || model.putOi !== null ? "可計算" : "未完成"],
    ["IV / VIX", model.avgIv !== null || Number.isFinite(model.vixValue) ? `${optionsPct(model.avgIv)} / ${Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--"}` : "待波動率", model.avgIv !== null || Number.isFinite(model.vixValue) ? "可計算" : "未完成"],
    ["跨市場", model.macroItems.length ? `${model.macroItems.length} 組資料` : "同步中", model.macroItems.length ? "已接入" : "待同步"],
  ];
  return `
    <${wrapper} class="${wrapperClass}" id="options-data-engine">
      <div class="asset-hub-group-heading">
        <div><p class="panel-kicker">Data & Strategy Engine</p><h4>資料與策略引擎</h4></div>
        <span>${strategies[0]?.name || "--"} · ${strategies[0]?.score || "--"}/100</span>
      </div>
      <div class="options-strategy-readiness">
        ${readiness.map(([name, value, status]) => `
          <span>
            <small>${escapeHtml(status)}</small>
            <b>${escapeHtml(name)}</b>
            <em>${escapeHtml(value)}</em>
          </span>
        `).join("")}
      </div>
      <div class="options-model-grid is-strategy">
        ${strategies.map((strategy) => `
          <button class="options-strategy-button is-${strategy.grade.tone} ${activeStrategy?.key === strategy.key ? "is-active" : ""}" type="button" data-options-strategy-key="${escapeHtml(strategy.key)}" aria-pressed="${activeStrategy?.key === strategy.key ? "true" : "false"}">
            <small>${escapeHtml(strategy.grade.label)} · ${strategy.role}</small>
            <b>${escapeHtml(strategy.name)}</b>
            <div class="options-strategy-meter"><i style="--bar:${strategy.score}%"></i><span>${strategy.score}/100</span></div>
            <p>${escapeHtml(strategy.evidence)}</p>
            <em>${escapeHtml(strategy.control)}</em>
          </button>
        `).join("")}
      </div>
      ${renderOptionsStrategyDetail(activeStrategy, model)}
      <p class="stock-theory-note">策略引擎只輸出資料適配度與風險條件，不輸出直接進出場指令；若鏈資料、IV 或跨市場資料缺漏，分數會自動保守。</p>
    </${wrapper}>
  `;
}
function renderOptionsRiskDashboard(model, options = {}) {
  const rows = [
    ["Risk Score", `${model.riskScore}/100`, model.riskLight.label],
    ["部位風險", "待輸入", "需投組部位"],
    ["Gamma Risk", model.expiryDays !== null && model.expiryDays <= 7 ? "高敏感" : "一般", "到期日"],
    ["Vega Risk", model.avgIv !== null && model.avgIv > 0.25 ? "偏高" : "觀察", "IV"],
    ["Theta Decay", model.expiryDays !== null ? `${model.expiryDays} 天` : "--", "時間價值"],
    ["Gap Risk", Number.isFinite(model.vixValue) && model.vixValue > 22 ? "升高" : "正常", "VIX"],
  ];
  const wrapper = options.embedded ? "section" : "article";
  const wrapperClass = options.embedded
    ? "options-ai-submodule options-risk-dashboard-card"
    : "panel-card options-risk-dashboard-card";
  return `
    <${wrapper} class="${wrapperClass}" id="options-risk-center">
      <div class="asset-hub-group-heading">
        <div><p class="panel-kicker">Risk Center</p><h4>風險管理中心</h4></div>
        <span>${escapeHtml(model.riskLight.text)}</span>
      </div>
      <div class="options-output-grid">
        ${rows.map(([name, value, note]) => `<span><small>${escapeHtml(name)}</small><b>${escapeHtml(value)}</b><em>${escapeHtml(note)}</em></span>`).join("")}
      </div>
    </${wrapper}>
  `;
}
function renderOptionsAiFunctionalPage(payload) {
  const model = buildOptionsAiFunctionalModel(payload);
  return `
    ${renderOptionsHeroDashboard(model)}
    ${renderOptionsMarketWorkbench(model)}
  `;
}
function renderDerivativesFuturesSinglePage(payload) {
  return `
    ${renderFuturesAnalysisCenter(payload)}
    ${renderDerivativesFuturesPanel(payload)}
  `;
}
function renderDerivativesOptionsSinglePage(payload) {
  return `
    ${renderOptionsAiFunctionalPage(payload)}
  `;
}
function renderDerivativesSinglePageContent(payload) {
  if (payload.category === "futures") return renderDerivativesFuturesSinglePage(payload);
  if (payload.category === "options") return renderDerivativesOptionsSinglePage(payload);
  return "";
}
function bindDerivativeAssetLoadMore(payload) {
  const root = document.getElementById("global-market-root");
  root?.querySelectorAll("[data-asset-load-more]").forEach((button) => {
    button.addEventListener("click", async () => {
      const category = button.dataset.assetLoadMore || payload?.category || "";
      const limit = Number(button.dataset.assetLoadLimit) || 24;
      if (!category) return;
      button.disabled = true;
      button.textContent = "同步更多行情...";
      try {
        const result = await fetchDerivativesApi(`/api/${encodeURIComponent(category)}?limit=${limit}`, 120000);
        if (result.error) throw new Error(result.error);
        const nextPayload = result.data || {};
        if (category === "options" && payload?.optionChain) nextPayload.optionChain = payload.optionChain;
        if (category === "options" && payload?.taiwanOptionChain) nextPayload.taiwanOptionChain = nextPayload.taiwanOptionChain || payload.taiwanOptionChain;
        renderGlobalMarketPage(nextPayload);
      } catch (error) {
        button.disabled = false;
        button.textContent = "載入更多已驗證行情";
        console.error(`Failed to load more ${category} data:`, error);
      }
    });
  });
}
async function hydrateDerivativesFuturesCandles(payload) {
  const root = document.getElementById("global-market-root");
  const target = root?.querySelector("[data-futures-technical-candle-symbol]");
  const symbol = String(target?.dataset?.futuresTechnicalCandleSymbol || "").toUpperCase();
  const code = String(target?.dataset?.futuresTechnicalCandleCode || "").toUpperCase();
  const interval = String(target?.dataset?.futuresTechnicalCandleInterval || "day").toLowerCase();
  if (!symbol || !code || target.dataset.loading === "1") return;
  const currentItem = (payload.items || []).find((item) => item?.symbol === symbol);
  const selectedContract = (currentItem?.technicalContracts || []).find((contract) => String(contract?.code || "").toUpperCase() === code)
    || getSelectedFuturesTechnicalContract(currentItem);
  const cacheKey = getFuturesTechnicalSeriesCacheKey(symbol, selectedContract, interval);
  if (derivativesFuturesTechnicalSeriesCache.has(cacheKey) || derivativesFuturesTechnicalLoadingKeys.has(cacheKey)) return;
  target.dataset.loading = "1";
  derivativesFuturesTechnicalLoadingKeys.add(cacheKey);
  try {
    const result = await fetchDerivativesApi(`/api/futures/${encodeURIComponent(symbol)}/technical-candles?code=${encodeURIComponent(code)}&interval=${encodeURIComponent(interval)}`, 120000);
    const candles = result.data?.candles || [];
    if (result.error || candles.length < 2) {
      derivativesFuturesTechnicalSeriesCache.set(cacheKey, {
        series: [],
        error: result.error || "TAIFEX 官方 K 線資料仍在同步中，稍後可重新整理。",
        contract: selectedContract,
        source: result.data?.source || "",
      });
      renderGlobalMarketPage(payload);
      return;
    }
    derivativesFuturesTechnicalSeriesCache.set(cacheKey, {
      series: normalizeFuturesTechnicalCandles(candles),
      error: "",
      contract: result.data?.contract || selectedContract,
      source: result.data?.source || "TAIFEX 官方期貨每日交易行情",
      interval: result.data?.interval || interval,
      contractMonth: result.data?.contractMonth || "",
    });
    renderGlobalMarketPage(payload);
  } catch (error) {
    derivativesFuturesTechnicalSeriesCache.set(cacheKey, {
      series: [],
      error: error?.message || "TAIFEX 官方 K 線同步失敗，稍後可重新整理。",
      contract: selectedContract,
      source: "",
    });
    renderGlobalMarketPage(payload);
  } finally {
    derivativesFuturesTechnicalLoadingKeys.delete(cacheKey);
  }
}
function bindDerivativesFuturesPanel(payload) {
  const root = document.getElementById("global-market-root");
  root?.querySelectorAll("[data-futures-framework-scope]").forEach((button) => {
    button.addEventListener("click", () => {
      const scope = button.dataset.futuresFrameworkScope || "taiwan";
      if (scope === derivativesFuturesFrameworkScope) return;
      derivativesFuturesFrameworkScope = scope;
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-futures-detail-scope]").forEach((button) => {
    button.addEventListener("click", () => {
      const scope = button.dataset.futuresDetailScope || "taiwan";
      if (scope === derivativesFuturesMarketScope) return;
      derivativesFuturesMarketScope = scope;
      const config = getFuturesScopeDetailConfig(scope);
      const scopeItems = (payload.items || [])
        .filter((item) => getFuturesMarketScope(item) === scope)
        .filter((item) => !item.error && (parseMarketNumber(item?.close) !== null || (item.series || []).length));
      const preferred = config.preferred
        .map((symbol) => scopeItems.find((item) => item.symbol === symbol))
        .filter(Boolean)[0];
      derivativesFuturesDetailSymbol = preferred?.symbol || scopeItems[0]?.symbol || derivativesFuturesDetailSymbol;
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-futures-detail-symbol]").forEach((button) => {
    button.addEventListener("click", () => {
      derivativesFuturesDetailSymbol = button.dataset.futuresDetailSymbol || "TX";
      derivativesFuturesMarketScope = button.dataset.futuresDetailSymbolScope || derivativesFuturesMarketScope;
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-futures-region-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.futuresRegionToggle || "";
      if (!key) return;
      if (derivativesFuturesRegionalExpandedKeys.has(key)) {
        derivativesFuturesRegionalExpandedKeys.delete(key);
      } else {
        derivativesFuturesRegionalExpandedKeys.add(key);
      }
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-asset-region-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.assetRegionToggle || "";
      if (key === "futures-regional-market") {
        renderGlobalMarketPage(payload);
      }
    });
  });
  root?.querySelectorAll("[data-futures-technical-contract-code]").forEach((button) => {
    button.addEventListener("click", () => {
      const symbol = String(button.dataset.futuresTechnicalContractSymbol || derivativesFuturesDetailSymbol || "").toUpperCase();
      const code = String(button.dataset.futuresTechnicalContractCode || "").toUpperCase();
      if (!symbol || !code) return;
      derivativesFuturesTechnicalContractState.set(symbol, code);
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-futures-technical-interval]").forEach((button) => {
    button.addEventListener("click", () => {
      const symbol = String(button.dataset.futuresTechnicalIntervalSymbol || derivativesFuturesDetailSymbol || "").toUpperCase();
      const interval = String(button.dataset.futuresTechnicalInterval || "day").toLowerCase();
      if (!symbol || !FUTURES_TECHNICAL_INTERVAL_OPTIONS.some((option) => option.key === interval)) return;
      derivativesFuturesTechnicalIntervalState.set(symbol, interval);
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-futures-indicator-view]").forEach((button) => {
    button.addEventListener("click", () => {
      const stateKey = String(button.dataset.futuresIndicatorViewKey || "");
      const view = String(button.dataset.futuresIndicatorView || "ma").toLowerCase();
      if (!stateKey || !FUTURES_TECHNICAL_INDICATOR_OPTIONS.some((option) => option.key === view)) return;
      derivativesFuturesTechnicalIndicatorState.set(stateKey, view);
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-futures-chart-ma]").forEach((button) => {
    button.addEventListener("click", () => {
      const chartKey = String(button.dataset.futuresChartKey || "");
      const period = Number(button.dataset.futuresChartMa);
      if (!chartKey || ![5, 10, 20, 60, 120, 240].includes(period)) return;
      const current = new Set(getFuturesStockStyleMaPeriods(chartKey).map(String));
      if (current.has(String(period))) current.delete(String(period));
      else current.add(String(period));
      setFuturesStockStyleStateList(derivativesFuturesStockStyleMaState, chartKey, [...current].sort((left, right) => Number(left) - Number(right)));
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-futures-chart-indicator]").forEach((button) => {
    button.addEventListener("click", () => {
      const chartKey = String(button.dataset.futuresChartKey || "");
      const key = String(button.dataset.futuresChartIndicator || "");
      if (!chartKey || !["bollinger", "fibonacci", "supportResistance", "smc"].includes(key)) return;
      const current = new Set(getFuturesStockStyleOverlayIndicators(chartKey));
      if (current.has(key)) current.delete(key);
      else current.add(key);
      setFuturesStockStyleStateList(derivativesFuturesStockStyleOverlayState, chartKey, [...current].sort());
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-futures-panel-indicator]").forEach((button) => {
    button.addEventListener("click", () => {
      const chartKey = String(button.dataset.futuresChartKey || "");
      const key = String(button.dataset.futuresPanelIndicator || "");
      if (!chartKey || !TECHNICAL_PANEL_INDICATOR_KEYS.includes(key)) return;
      const current = new Set(getFuturesStockStylePanelIndicators(chartKey));
      if (current.has(key) && current.size > 1) current.delete(key);
      else current.add(key);
      setFuturesStockStyleStateList(derivativesFuturesStockStylePanelState, chartKey, [...current].sort());
      renderGlobalMarketPage(payload);
    });
  });
  const updateFuturesChartZoom = (card, direction) => {
    if (!card) return;
    const chartKey = String(card.dataset.futuresStockChartKey || "");
    const total = Number(card.dataset.futuresStockChartTotal);
    const minimum = Number(card.dataset.futuresStockChartMin);
    const visible = Number(card.dataset.futuresStockChartVisible);
    if (!chartKey || !Number.isFinite(total) || !Number.isFinite(minimum) || !Number.isFinite(visible) || total < 2) return;
    let next = visible;
    if (direction === "in") next = Math.max(minimum, Math.floor(visible * 0.65));
    if (direction === "out") next = Math.min(total, Math.ceil(visible / 0.65));
    if (direction === "reset") next = total;
    if (next === visible) return;
    derivativesFuturesStockStyleVisibleState.set(chartKey, next);
    derivativesFuturesStockStylePanState.set(chartKey, 0);
    renderGlobalMarketPage(payload);
  };
  const updateFuturesChartPan = (card, direction) => {
    if (!card) return;
    const chartKey = String(card.dataset.futuresStockChartKey || "");
    const total = Number(card.dataset.futuresStockChartTotal);
    const visible = Number(card.dataset.futuresStockChartVisible);
    const panOffset = Number(card.dataset.futuresStockChartPan);
    if (!chartKey || !Number.isFinite(total) || !Number.isFinite(visible) || !Number.isFinite(panOffset) || total < 2) return;
    const maxOffset = Math.max(total - visible, 0);
    const step = Math.max(1, Math.round(visible * 0.35));
    const next = direction === "older"
      ? Math.min(maxOffset, panOffset + step)
      : Math.max(0, panOffset - step);
    if (next === panOffset) return;
    derivativesFuturesStockStylePanState.set(chartKey, next);
    renderGlobalMarketPage(payload);
  };
  root?.querySelectorAll("[data-futures-chart-zoom]").forEach((button) => {
    button.addEventListener("click", () => updateFuturesChartZoom(button.closest("[data-futures-stock-chart-key]"), button.dataset.futuresChartZoom));
  });
  root?.querySelectorAll("[data-futures-chart-pan]").forEach((button) => {
    button.addEventListener("click", () => updateFuturesChartPan(button.closest("[data-futures-stock-chart-key]"), button.dataset.futuresChartPan));
  });
  root?.querySelectorAll("[data-futures-technical-chart-view]").forEach((chartView) => {
    bindChartHover(chartView);
    const frame = chartView.querySelector(".sector-chart-frame");
    const card = chartView.closest("[data-futures-stock-chart-key]");
    if (!frame || !card) return;
    frame.addEventListener("wheel", (event) => {
      event.preventDefault();
      updateFuturesChartZoom(card, event.deltaY < 0 ? "in" : "out");
    }, { passive: false });
    bindHorizontalChartPan(frame, (direction) => updateFuturesChartPan(card, direction));
  });
  hydrateDerivativesFuturesCandles(payload);
}
function bindOptionsRiskConeHover(root = document) {
  root.querySelectorAll("[data-options-risk-cone-chart]").forEach((chart) => {
    const xLine = chart.querySelector("[data-options-risk-cone-crosshair-x]");
    const yLine = chart.querySelector("[data-options-risk-cone-crosshair-y]");
    const dot = chart.querySelector("[data-options-risk-cone-crosshair-dot]");
    const tooltip = chart.querySelector("[data-options-risk-cone-tooltip]");
    const zones = chart.querySelectorAll(".options-risk-cone-hover-zone");
    if (!tooltip || !zones.length) return;
    const hide = () => {
      chart.classList.remove("is-hovering");
      xLine?.classList.remove("is-visible");
      yLine?.classList.remove("is-visible");
      dot?.classList.remove("is-visible");
      tooltip.classList.remove("is-visible");
    };
    const show = (event, zone) => {
      const x = Number(zone.dataset.coneX) || 0;
      const y = Number(zone.dataset.coneY) || 0;
      if (xLine) {
        xLine.setAttribute("x1", x.toFixed(1));
        xLine.setAttribute("x2", x.toFixed(1));
        xLine.classList.add("is-visible");
      }
      if (yLine) {
        yLine.setAttribute("y1", y.toFixed(1));
        yLine.setAttribute("y2", y.toFixed(1));
        yLine.classList.add("is-visible");
      }
      if (dot) {
        dot.setAttribute("cx", x.toFixed(1));
        dot.setAttribute("cy", y.toFixed(1));
        dot.classList.add("is-visible");
      }
      chart.classList.add("is-hovering");
      tooltip.innerHTML = `
        <small>${escapeHtml(zone.dataset.coneFocus || "--")} · ${escapeHtml(zone.dataset.coneLabel || "--")}</small>
        <strong>${escapeHtml(zone.dataset.coneDirection || "--")}</strong>
        <div><span>\u4e2d\u5fc3\u50f9</span><b>${escapeHtml(zone.dataset.coneCenter || "--")}</b></div>
        <div><span>\u4e0a\u7de3\u58d3\u529b</span><b>${escapeHtml(zone.dataset.coneUpper || "--")}</b></div>
        <div><span>\u4e0b\u7de3\u652f\u6490</span><b>${escapeHtml(zone.dataset.coneLower || "--")}</b></div>
        <footer>\u504f\u591a ${Number(zone.dataset.coneBullish) || 0}% · \u9707\u76ea ${Number(zone.dataset.coneRange) || 0}% · \u504f\u7a7a ${Number(zone.dataset.coneBearish) || 0}%</footer>
      `;
      const rect = chart.getBoundingClientRect();
      const fallbackX = rect.left + (x / 912) * Math.max(rect.width, 1);
      const fallbackY = rect.top + (y / 320) * Math.max(rect.height, 1);
      const clientX = Number.isFinite(event.clientX) && event.clientX > 0 ? event.clientX : fallbackX;
      const clientY = Number.isFinite(event.clientY) && event.clientY > 0 ? event.clientY : fallbackY;
      const px = Math.min(Math.max(clientX - rect.left + 14, 12), Math.max(rect.width - 226, 12));
      const py = Math.min(Math.max(clientY - rect.top - 8, 12), Math.max(rect.height - 154, 12));
      tooltip.style.left = `${px}px`;
      tooltip.style.top = `${py}px`;
      tooltip.classList.add("is-visible");
    };
    zones.forEach((zone) => {
      zone.addEventListener("pointerenter", (event) => show(event, zone));
      zone.addEventListener("pointermove", (event) => show(event, zone));
      zone.addEventListener("focus", (event) => show(event, zone));
    });
    chart.addEventListener("pointerleave", hide);
    chart.addEventListener("blur", hide, true);
  });
}
async function refreshDerivativesOptionsCurrentExpiry() {
  if (derivativesOptionsAutoRefreshInFlight || document.hidden) return;
  const payload = derivativesOptionsAutoRefreshPayload;
  if (!payload || payload.category !== "options") return;
  const chain = payload.taiwanOptionChain || {};
  const underlying = getActiveTaiwanOptionUnderlying(chain);
  const params = new URLSearchParams({
    underlying,
    source: derivativesOptionsChainSource,
  });
  if (chain.selectedExpiry) params.set("expiry", chain.selectedExpiry);
  derivativesOptionsAutoRefreshInFlight = true;
  try {
    const response = await fetchWithTimeout(`/api/options/chain?${params.toString()}`, { cache: "no-store" }, 30000);
    const result = await response.json();
    if (!response.ok || result.success === false) throw new Error(result?.error?.message || `HTTP ${response.status}`);
    const nextPayload = { ...payload, taiwanOptionChain: result.data };
    derivativesOptionsAutoRefreshPayload = nextPayload;
    renderGlobalMarketPage(nextPayload);
  } catch (error) {
    console.warn("Failed to auto refresh TAIFEX option chain:", error);
  } finally {
    derivativesOptionsAutoRefreshInFlight = false;
  }
}
async function fetchOptionsMarketChainPayload(chainSymbol, focusKey, item = null, expiration = "") {
  const params = new URLSearchParams();
  if (expiration) params.set("expiration", expiration);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetchWithTimeout(`/api/us-market/options-chain/${encodeURIComponent(chainSymbol)}${suffix}`, { cache: "no-store" }, 30000);
  const chain = await response.json();
  if (!response.ok) throw new Error(chain?.error || `HTTP ${response.status}`);
  return attachOptionsMarketChainMeta(chain, focusKey, item);
}
async function hydrateSelectedOptionsMarketChain(payload, options = {}) {
  if (!payload || payload.category !== "options") return false;
  const model = buildOptionsAiFunctionalModel(payload);
  const item = getOptionsMarketChainItemForFocus(model);
  const officialUnderlying = getTaiwanOptionUnderlyingFromMarketItem(item || {});
  if (officialUnderlying) return false;
  const chainSymbol = getOptionsMarketOptionChainSymbol(item || {});
  if (!chainSymbol) return false;
  const focusKey = derivativesOptionsSelectedFocus || "";
  const current = payload.optionChain || {};
  const currentSymbol = String(current.symbol || "").toUpperCase();
  const currentFocus = String(current.marketFocusKey || "");
  const alreadyLoaded = currentSymbol === chainSymbol && (!currentFocus || currentFocus === focusKey);
  if (alreadyLoaded && !options.force) return false;
  const loadKey = `${focusKey}:${chainSymbol}:${options.expiration || ""}`;
  if (derivativesOptionsMarketChainInFlightKey === loadKey) return true;
  derivativesOptionsMarketChainInFlightKey = loadKey;
  try {
    const optionChain = await fetchOptionsMarketChainPayload(chainSymbol, focusKey, item, options.expiration || "");
    renderGlobalMarketPage({ ...payload, optionChain });
    return true;
  } catch (error) {
    renderGlobalMarketPage({
      ...payload,
      optionChain: attachOptionsMarketChainMeta({
        symbol: chainSymbol,
        error: error?.message || "公開選擇權鏈資料暫時無法取得",
        source: "Cboe Delayed Quotes Options",
      }, focusKey, item),
    });
    return true;
  } finally {
    derivativesOptionsMarketChainInFlightKey = "";
  }
}
function scheduleDerivativesOptionsAutoRefresh(payload) {
  if (document.body.dataset.page !== "global-market" || document.body.dataset.marketCategory !== "options") return;
  derivativesOptionsAutoRefreshPayload = payload;
  if (derivativesOptionsAutoRefreshTimer) return;
  derivativesOptionsAutoRefreshTimer = window.setInterval(refreshDerivativesOptionsCurrentExpiry, DERIVATIVES_OPTIONS_AUTO_REFRESH_MS);
}
function bindDerivativesOptionsPanel(payload) {
  const root = document.getElementById("global-market-root");
  scheduleDerivativesOptionsAutoRefresh(payload);
  hydrateSelectedOptionsMarketChain(payload);
  if (root) bindOptionsRiskConeHover(root);
  root?.querySelectorAll("[data-asset-region-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.assetRegionToggle || "";
      if (key !== "options-regional-market") return;
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-options-region-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = String(button.dataset.optionsRegionToggle || "");
      if (!key) return;
      if (derivativesOptionsRegionalExpandedKeys.has(key)) {
        derivativesOptionsRegionalExpandedKeys.delete(key);
      } else {
        derivativesOptionsRegionalExpandedKeys.add(key);
      }
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-options-chain-strike]").forEach((row) => {
    const selectStrike = () => {
      const strike = String(row.dataset.optionsChainStrike || "");
      if (!strike || strike === derivativesOptionsSelectedStrike) return;
      derivativesOptionsSelectedStrike = strike;
      renderGlobalMarketPage(payload);
    };
    row.addEventListener("click", selectStrike);
    row.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      selectStrike();
    });
  });
  root?.querySelectorAll("[data-options-chain-source]").forEach((button) => {
    button.addEventListener("click", async () => {
      const source = String(button.dataset.optionsChainSource || "auto").toLowerCase();
      if (!["auto", "taifex", "yahoo"].includes(source) || source === derivativesOptionsChainSource) return;
      derivativesOptionsChainSource = source;
      button.disabled = true;
      try {
        const underlying = getActiveTaiwanOptionUnderlying(payload.taiwanOptionChain || {});
        const response = await fetchWithTimeout(`/api/options/chain?underlying=${encodeURIComponent(underlying)}&source=${encodeURIComponent(source)}`, { cache: "no-store" }, 30000);
        const result = await response.json();
        if (!response.ok || result.success === false) throw new Error(result?.error?.message || `HTTP ${response.status}`);
        renderGlobalMarketPage({ ...payload, taiwanOptionChain: result.data });
      } catch (error) {
        button.disabled = false;
        console.error("Failed to switch Taiwan option source:", error);
      }
    });
  });
  root?.querySelectorAll("[data-tw-option-product]").forEach((button) => {
    button.addEventListener("click", async () => {
      const underlying = String(button.dataset.twOptionProduct || "").toUpperCase();
      if (!underlying || button.classList.contains("is-active")) return;
      derivativesOptionsSelectedUnderlying = underlying;
      derivativesOptionsSelectedStrike = "";
      const focusKey = getOptionsRegionalFocusKeyBySymbol(buildOptionsAiFunctionalModel(payload), underlying);
      if (focusKey) derivativesOptionsSelectedFocus = focusKey;
      button.disabled = true;
      try {
        const response = await fetchWithTimeout(`/api/options/chain?underlying=${encodeURIComponent(underlying)}&source=${encodeURIComponent(derivativesOptionsChainSource)}`, { cache: "no-store" }, 30000);
        const result = await response.json();
        if (!response.ok || result.success === false) throw new Error(result?.error?.message || `HTTP ${response.status}`);
        renderGlobalMarketPage({ ...payload, taiwanOptionChain: result.data });
      } catch (error) {
        button.disabled = false;
        console.error("Failed to switch Taiwan option product:", error);
      }
    });
  });
  root?.querySelectorAll("[data-tw-option-expiry-select]").forEach((select) => {
    select.addEventListener("change", async () => {
      const expiry = select.value || "";
      if (!expiry) return;
      select.disabled = true;
      try {
        const underlying = getActiveTaiwanOptionUnderlying(payload.taiwanOptionChain || {});
        const response = await fetchWithTimeout(`/api/options/chain?underlying=${encodeURIComponent(underlying)}&expiry=${encodeURIComponent(expiry)}&source=${encodeURIComponent(derivativesOptionsChainSource)}`, { cache: "no-store" }, 30000);
        const result = await response.json();
        if (!response.ok || result.success === false) throw new Error(result?.error?.message || `HTTP ${response.status}`);
        renderGlobalMarketPage({ ...payload, taiwanOptionChain: result.data });
      } catch (error) {
        select.disabled = false;
        console.error("Failed to switch Taiwan option expiry:", error);
      }
    });
  });
  root?.querySelectorAll("[data-options-market-expiration-select]").forEach((select) => {
    select.addEventListener("change", async () => {
      const chainSymbol = String(select.dataset.optionsMarketChainSymbol || "").toUpperCase();
      const focusKey = String(select.dataset.optionsMarketFocusKey || derivativesOptionsSelectedFocus || "");
      const expiration = String(select.value || "");
      if (!chainSymbol || !expiration) return;
      select.disabled = true;
      try {
        const model = buildOptionsAiFunctionalModel(payload);
        const item = getOptionsMarketChainItemForFocus(model);
        const optionChain = await fetchOptionsMarketChainPayload(chainSymbol, focusKey, item, expiration);
        renderGlobalMarketPage({ ...payload, optionChain });
      } catch (error) {
        renderGlobalMarketPage({
          ...payload,
          optionChain: attachOptionsMarketChainMeta({
            symbol: chainSymbol,
            error: error?.message || "公開選擇權鏈資料暫時無法取得",
            source: "Cboe Delayed Quotes Options",
          }, focusKey, getOptionsMarketChainItemForFocus(buildOptionsAiFunctionalModel(payload))),
        });
      }
    });
  });
  root?.querySelectorAll("[data-asset-option-underlying]").forEach((button) => {
    button.addEventListener("click", async () => {
      const underlying = String(button.dataset.assetOptionUnderlying || "").toUpperCase();
      if (!underlying || button.classList.contains("is-active")) return;
      button.disabled = true;
      try {
        const response = await fetchWithTimeout(`/api/us-market/options-chain/${encodeURIComponent(underlying)}`, { cache: "no-store" }, 20000);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const chain = await response.json();
        renderGlobalMarketPage({ ...payload, optionChain: chain });
      } catch (error) {
        button.disabled = false;
        console.error(`Failed to load ${underlying} options chain:`, error);
      }
    });
  });
  root?.querySelectorAll("[data-options-strategy-key]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = String(button.dataset.optionsStrategyKey || "");
      if (!key || key === derivativesOptionsSelectedStrategy) return;
      derivativesOptionsSelectedStrategy = key;
      renderGlobalMarketPage(payload);
    });
  });
  root?.querySelectorAll("[data-options-focus-key]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = String(button.dataset.optionsFocusKey || "");
      if (!key || key === derivativesOptionsSelectedFocus) return;
      derivativesOptionsSelectedFocus = key;
      const selectedModel = buildOptionsAiFunctionalModel(payload);
      const selectedContext = getOptionsMarketChainSelectorContext(selectedModel);
      const selectedMarketItem = getOptionsMarketChainItemForFocus(selectedModel);
      const officialUnderlying = String(button.dataset.optionsChainUnderlying || getTaiwanOptionUnderlyingFromMarketItem(selectedMarketItem || "") || "").toUpperCase();
      if (TAIWAN_OPTION_CHAIN_UNDERLYINGS.has(officialUnderlying)) {
        if (selectedContext?.selectedItem && selectedMarketItem !== selectedContext.selectedItem) {
          const resolvedFocusKey = getOptionsRegionalFocusKeyBySymbol(selectedModel, officialUnderlying);
          if (resolvedFocusKey) derivativesOptionsSelectedFocus = resolvedFocusKey;
        }
        derivativesOptionsSelectedUnderlying = officialUnderlying;
        derivativesOptionsSelectedStrike = "";
        button.disabled = true;
        try {
          const response = await fetchWithTimeout(`/api/options/chain?underlying=${encodeURIComponent(officialUnderlying)}&source=${encodeURIComponent(derivativesOptionsChainSource)}`, { cache: "no-store" }, 30000);
          const result = await response.json();
          if (!response.ok || result.success === false) throw new Error(result?.error?.message || `HTTP ${response.status}`);
          renderGlobalMarketPage({ ...payload, taiwanOptionChain: result.data });
          return;
        } catch (error) {
          button.disabled = false;
          console.error("Failed to switch option chain from regional selection:", error);
        }
      }
      button.disabled = true;
      const loadedMarketChain = await hydrateSelectedOptionsMarketChain(payload, { force: true });
      if (loadedMarketChain) return;
      button.disabled = false;
      renderGlobalMarketPage(payload);
    });
  });
}
async function fetchOptionsAiExtraMarket(category) {
  const response = await fetchWithTimeout(`/api/global-market/${encodeURIComponent(category)}?limit=all`, { cache: "no-store" }, 120000);
  if (!response.ok) throw new Error(`${category} HTTP ${response.status}`);
  return response.json();
}
async function hydrateOptionsAiExtras(payload) {
  if (!payload || payload.category !== "options") return;
  if (payload.optionsAiExtras) return;
  if (optionsAiExtrasCache) {
    renderGlobalMarketPage({ ...payload, optionsAiExtras: optionsAiExtrasCache });
    return;
  }
  if (optionsAiExtrasLoading) return;
  optionsAiExtrasLoading = true;
  try {
    const [usStocks, futures, bonds, preciousMetals] = await Promise.allSettled([
      fetchOptionsAiExtraMarket("us-stocks"),
      fetchOptionsAiExtraMarket("futures"),
      fetchOptionsAiExtraMarket("bonds"),
      fetchOptionsAiExtraMarket("precious-metals"),
    ]);
    optionsAiExtrasCache = {
      usStocks: usStocks.status === "fulfilled" ? usStocks.value : null,
      futures: futures.status === "fulfilled" ? futures.value : null,
      bonds: bonds.status === "fulfilled" ? bonds.value : null,
      preciousMetals: preciousMetals.status === "fulfilled" ? preciousMetals.value : null,
      loadedAt: new Date().toISOString(),
    };
    renderGlobalMarketPage({ ...payload, optionsAiExtras: optionsAiExtrasCache });
  } catch (error) {
    console.warn("Failed to hydrate options AI cross-market data:", error);
  } finally {
    optionsAiExtrasLoading = false;
  }
}
function getUsMarketOverviewModel(payload = {}) {
  const items = Array.isArray(payload.items) ? payload.items : [];
  const majorItems = US_MAJOR_INDEX_SYMBOLS
    .map((symbol) => items.find((item) => item.symbol === symbol))
    .filter(Boolean);
  const vix = items.find((item) => item.symbol === "^VIX") || null;
  const sectorItems = items.filter((item) => item.group === "美股類股指數" && !item.error);
  const equityEtfItems = items.filter((item) => ["美股個股", "美股 ETF"].includes(item.group) && !item.error);
  const pulsePool = equityEtfItems.length
    ? equityEtfItems
    : items.filter((item) => item.group !== "主要指數" && item.symbol !== "^VIX" && !item.error);
  const usablePulseItems = pulsePool.filter((item) => Number.isFinite(parseMarketNumber(item.pct)));
  const advancers = usablePulseItems.filter((item) => parseMarketNumber(item.pct) > 0).length;
  const decliners = usablePulseItems.filter((item) => parseMarketNumber(item.pct) < 0).length;
  const avgPct = usablePulseItems.length
    ? usablePulseItems.reduce((sum, item) => sum + (parseMarketNumber(item.pct) || 0), 0) / usablePulseItems.length
    : null;
  const strongest = usablePulseItems.reduce((best, item) => {
    if (!best) return item;
    return (parseMarketNumber(item.pct) || -Infinity) > (parseMarketNumber(best.pct) || -Infinity) ? item : best;
  }, null);
  const weakest = usablePulseItems.reduce((best, item) => {
    if (!best) return item;
    return (parseMarketNumber(item.pct) || Infinity) < (parseMarketNumber(best.pct) || Infinity) ? item : best;
  }, null);
  const analysis = buildUsMarketPulseAnalysis({
    majorItems,
    usablePulseItems,
    vix,
    avgPct,
    advancers,
    decliners,
    strongest,
    weakest,
  });
  const rankedSectors = sectorItems
    .filter((item) => Number.isFinite(parseMarketNumber(item.pct)))
    .sort((left, right) => (parseMarketNumber(right.pct) || 0) - (parseMarketNumber(left.pct) || 0));
  return {
    payload,
    items,
    majorItems,
    vix,
    sectorItems,
    rankedSectors,
    usablePulseItems,
    advancers,
    decliners,
    avgPct,
    strongest,
    weakest,
    analysis,
    vixBand: getVixSentimentBand(parseMarketNumber(vix?.close)),
  };
}
function getUsMarketTone(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed) || parsed === 0) return "flat";
  return parsed > 0 ? "up" : "down";
}
function formatUsMarketPct(value) {
  const parsed = parseMarketNumber(value);
  return Number.isFinite(parsed) ? `${parsed >= 0 ? "+" : ""}${parsed.toFixed(2)}%` : "--";
}
function renderUsMarketOverviewCards(model) {
  const fallbackItems = model.items
    .filter((item) => item.group !== "美股個股" && item.group !== "美股 ETF" && !item.error)
    .slice(0, 4);
  const cards = model.majorItems.length ? model.majorItems : fallbackItems;
  const vixCard = model.vix && !cards.some((item) => item.symbol === "^VIX") ? [model.vix] : [];
  return [...cards, ...vixCard].slice(0, 5).map((item) => {
    const tone = getUsMarketTone(item.pct);
    const label = item.symbol === "^VIX" ? "VIX 波動率" : getUsBenchmarkDisplayName(item);
    return `
      <article class="metric-card">
        <p>${escapeHtml(label)}</p>
        <h3>${formatGlobalValue(item.close)}</h3>
        <strong class="${toneClass(tone)}">${escapeHtml(item.change || "--")} / ${escapeHtml(item.pct || "--")}</strong>
      </article>
    `;
  }).join("") || '<article class="metric-card"><p>美股盤勢</p><h3>同步中</h3><strong class="flat">--</strong></article>';
}
function renderUsMarketInstitutionSummary(model) {
  const breadthTone = model.advancers > model.decliners ? "up" : model.decliners > model.advancers ? "down" : "flat";
  const avgTone = getUsMarketTone(model.avgPct);
  const vixTone = model.vixBand.tone === "negative" || model.vixBand.tone === "red" ? "down" : model.vixBand.tone === "positive" ? "up" : "flat";
  const cards = [
    {
      key: "breadth",
      name: "市場廣度",
      value: `${model.advancers} / ${model.decliners}`,
      tone: breadthTone,
      leftLabel: "上漲",
      leftValue: model.advancers,
      rightLabel: "下跌",
      rightValue: model.decliners,
    },
    {
      key: "vix",
      name: "VIX 風險",
      value: formatGlobalValue(model.vix?.close),
      tone: vixTone,
      leftLabel: "漲跌幅",
      leftValue: model.vix?.pct || "--",
      rightLabel: "區間",
      rightValue: model.vixBand.label,
    },
    {
      key: "average",
      name: "樣本平均",
      value: formatUsMarketPct(model.avgPct),
      tone: avgTone,
      leftLabel: "最強",
      leftValue: model.strongest?.symbol || "--",
      rightLabel: "最弱",
      rightValue: model.weakest?.symbol || "--",
    },
  ];
  return cards.map((item) => `
    <article class="institution-card institution-card-${escapeHtml(item.key)}">
      <div class="institution-card-title">
        <span>${escapeHtml(item.name)}</span>
        <strong class="${toneClass(item.tone)}">${escapeHtml(item.value)}</strong>
      </div>
      <div class="institution-card-metrics">
        <span>${escapeHtml(item.leftLabel)}<strong>${escapeHtml(item.leftValue)}</strong></span>
        <span>${escapeHtml(item.rightLabel)}<strong>${escapeHtml(item.rightValue)}</strong></span>
      </div>
    </article>
  `).join("");
}
function renderUsMarketInstitutionRows(model) {
  const sectorRows = model.rankedSectors.slice(0, 4);
  const rows = [
    ...model.majorItems.map((item) => ({ ...item, note: "主要指數" })),
    ...(model.vix ? [{ ...model.vix, name: "CBOE VIX", note: model.vixBand.label }] : []),
    ...sectorRows.map((item) => ({ ...item, name: getUsSectorDisplayName(item), note: "類股指數" })),
  ];
  return rows.map((item) => {
    const tone = getUsMarketTone(item.pct);
    return `
      <div class="institution-row">
        <span>${escapeHtml(item.name || item.symbol || "--")}</span>
        <span>${formatGlobalValue(item.close)}</span>
        <span class="${toneClass(tone)}">${escapeHtml(item.pct || "--")}</span>
        <strong class="${toneClass(tone)}">${escapeHtml(item.note || item.group || "--")}</strong>
      </div>
    `;
  }).join("") || '<div class="stock-detail-empty">美股指標資料同步中。</div>';
}
function buildUsMarketRankItems(items, limit = 5) {
  return items.slice(0, limit).map((item) => ({
    name: getUsSectorDisplayName(item),
    pct: item.pct || "--",
    tone: getUsMarketTone(item.pct),
    reason: `${item.symbol || "--"} · 最新 ${formatGlobalValue(item.close)} · 成交量 ${formatGlobalVolume(item.volume)}`,
  }));
}
function renderUsMarketRankList(items, tone) {
  if (!items.length) return '<p class="market-ai-empty">資料同步中。</p>';
  return `
    <div class="market-ai-rank-list">
      ${items.map((item, index) => `
        <article class="market-ai-rank-item is-${tone}">
          <span>${index + 1}</span>
          <div>
            <strong>${escapeHtml(item.name || "--")}</strong>
            <small>${escapeHtml(item.reason || "")}</small>
          </div>
          <b class="${toneClass(item.tone)}">${escapeHtml(item.pct || "--")}</b>
        </article>
      `).join("")}
    </div>
  `;
}
function getUsMarketSectorRankingGroups(model) {
  const itemsBySymbol = new Map(
    (model.items || [])
      .filter((item) => item?.symbol && !item.error)
      .map((item) => [item.symbol, item]),
  );
  const pickSymbols = (symbols) => symbols
    .map((symbol, index) => {
      const item = itemsBySymbol.get(symbol);
      return item ? { ...item, _usRankingOrder: index } : null;
    })
    .filter(Boolean);
  const fallbackSectors = (model.sectorItems || []).map((item, index) => ({ ...item, _usRankingOrder: index }));
  const sp500Sectors = pickSymbols(US_SP500_SECTOR_SYMBOLS);
  const dowSectors = pickSymbols(US_MAJOR_INDEX_SECTOR_SYMBOLS["^DJI"] || []);
  const nasdaqSectors = pickSymbols(US_MAJOR_INDEX_SECTOR_SYMBOLS["^IXIC"] || []);
  const russellSectors = pickSymbols(US_MAJOR_INDEX_SECTOR_SYMBOLS["^RUT"] || []);
  const industrySectors = pickSymbols(US_INDUSTRY_SECTOR_SYMBOLS);
  return [
    { key: "sp500", label: "S&P 500 類股", source: "Yahoo Finance", items: sp500Sectors.length ? sp500Sectors : fallbackSectors },
    { key: "dow", label: "道瓊工業", source: "Yahoo Finance", items: dowSectors },
    { key: "nasdaq", label: "那斯達克", source: "Yahoo Finance", items: nasdaqSectors },
    { key: "russell", label: "羅素2000", source: "Yahoo Finance", items: russellSectors },
    { key: "industry", label: "產業指數", source: "Yahoo Finance", items: industrySectors },
    { key: "major", label: "主要指數", source: "Yahoo Finance", items: pickSymbols([...US_MAJOR_INDEX_SYMBOLS, "^VIX"]) },
  ];
}
function getUsMarketSectorRankingContext(model) {
  const groups = getUsMarketSectorRankingGroups(model);
  const requestedGroup = groups.find((group) => group.key === usMarketSectorRankingState.groupKey);
  const activeGroup = (requestedGroup && requestedGroup.items.length)
    ? requestedGroup
    : groups.find((group) => group.items.length) || groups[0];
  usMarketSectorRankingState.groupKey = activeGroup?.key || "sp500";
  return { groups, activeGroup };
}
function getUsMarketSectorRankingName(item = {}, groupKey = "") {
  if (item.symbol === "^VIX") return "VIX 波動率";
  if (groupKey === "major") return getUsBenchmarkDisplayName(item);
  return getUsSectorDisplayName(item);
}
function getUsMarketRankingTurnover(item = {}) {
  const direct = parseMarketNumber(item.turnoverValue ?? item.turnover);
  if (Number.isFinite(direct)) return direct;
  const close = parseMarketNumber(item.close);
  const volume = parseMarketNumber(item.volumeValue ?? item.volume);
  if (["美股個股", "美股 ETF"].includes(item.group) && Number.isFinite(close) && Number.isFinite(volume)) {
    return close * volume;
  }
  return null;
}
function formatUsMarketRankingAmount(item = {}) {
  const value = getUsMarketRankingTurnover(item);
  if (!Number.isFinite(value)) return "--";
  if (value >= 1000000000000) return `${(value / 1000000000000).toFixed(2)}T`;
  if (value >= 1000000000) return `${(value / 1000000000).toFixed(2)}B`;
  if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`;
  return Math.round(value).toLocaleString("zh-TW");
}
function getUsMarketSectorSortValue(item = {}, key = "source_order", groupKey = "") {
  if (key === "name_asc") return getUsMarketSectorRankingName(item, groupKey);
  if (key === "volume_desc") return parseMarketNumber(item.volumeValue ?? item.volume);
  if (key === "turnover_desc") return getUsMarketRankingTurnover(item);
  if (key === "change_desc") return parseMarketNumber(item.change);
  return parseMarketNumber(item.pct);
}
function sortUsMarketSectorRankingItems(items = [], groupKey = "") {
  const key = usMarketSectorRankingState.sortKey || "source_order";
  if (key === "source_order") {
    return [...items].sort((left, right) => (left._usRankingOrder ?? 0) - (right._usRankingOrder ?? 0));
  }
  return [...items].sort((left, right) => {
    if (key === "name_asc") {
      return String(getUsMarketSectorSortValue(left, key, groupKey) || "").localeCompare(
        String(getUsMarketSectorSortValue(right, key, groupKey) || ""),
        "zh-Hant",
      );
    }
    const leftValue = getUsMarketSectorSortValue(left, key, groupKey);
    const rightValue = getUsMarketSectorSortValue(right, key, groupKey);
    const leftFinite = Number.isFinite(leftValue);
    const rightFinite = Number.isFinite(rightValue);
    if (leftFinite && rightFinite && leftValue !== rightValue) return rightValue - leftValue;
    if (leftFinite !== rightFinite) return leftFinite ? -1 : 1;
    return String(getUsMarketSectorRankingName(left, groupKey)).localeCompare(
      String(getUsMarketSectorRankingName(right, groupKey)),
      "zh-Hant",
    );
  });
}
function formatUsMarketRankingChange(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  return `${parsed > 0 ? "+" : ""}${parsed.toLocaleString("zh-TW", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}
function renderUsMarketSectorRankingTabs(groups = [], activeKey = "sp500") {
  return `
    <div class="market-sector-ranking-tabs" aria-label="美股盤勢排行切換">
      ${groups.map((group) => `
        <button class="class-tab ${group.key === activeKey ? "is-active" : ""}" type="button" data-us-market-sector-ranking-group="${escapeHtml(group.key)}">
          ${escapeHtml(group.label)}
        </button>
      `).join("")}
    </div>
  `;
}
function renderUsMarketSectorSortControl() {
  const options = [
    ["source_order", "預設順序"],
    ["pct_desc", "漲跌幅高到低"],
    ["change_desc", "漲跌高到低"],
    ["volume_desc", "成交量高到低"],
    ["turnover_desc", "成交金額高到低"],
    ["name_asc", "名稱 A-Z"],
  ];
  return `
    <div class="sector-sort-toolbar">
      <label for="us-market-sector-sort-select">類股排序</label>
      <select id="us-market-sector-sort-select" data-us-market-sector-sort>
        ${options.map(([value, label]) => `<option value="${value}" ${value === usMarketSectorRankingState.sortKey ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}
      </select>
    </div>
  `;
}
function renderUsMarketSectorRankingName(item = {}, groupKey = "") {
  const label = getUsMarketSectorRankingName(item, groupKey);
  const symbol = String(item.symbol || "").trim();
  const href = symbol ? buildYahooFinanceUrl(symbol) : "#";
  return `
    <a class="class-name-cell class-stock-link" href="${safeUrl(href)}" target="_blank" rel="noopener noreferrer" title="查看 ${escapeHtml(label)} Yahoo Finance">
      ${escapeHtml(label)}
    </a>
  `;
}
function renderUsMarketSectorLineChart(item = {}, groupKey = "") {
  const series = normalizeGlobalSeries(item.series || []);
  const points = series.map((entry) => ({ value: entry.value })).filter((entry) => Number.isFinite(entry.value));
  const fallbackPoints = [
    parseMarketNumber(item.previousClose),
    parseMarketNumber(item.open),
    parseMarketNumber(item.low),
    parseMarketNumber(item.high),
    parseMarketNumber(item.close),
  ].filter(Number.isFinite).map((value) => ({ value }));
  const chartPoints = points.length >= 2 ? points : fallbackPoints;
  if (chartPoints.length < 2) {
    return '<div class="class-line-empty class-line-empty-compact">資料同步中</div>';
  }
  const width = 180;
  const height = 56;
  const pad = 6;
  const values = chartPoints.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  const step = (width - pad * 2) / Math.max(chartPoints.length - 1, 1);
  const mapped = chartPoints.map((point, index) => ({
    value: point.value,
    x: pad + index * step,
    y: height - pad - ((point.value - minValue) / range) * (height - pad * 2),
  }));
  const path = buildPath(mapped);
  const label = getUsMarketSectorRankingName(item, groupKey);
  const tone = getUsMarketTone(item.pct);
  return `
    <svg class="class-line-chart ${toneClass(tone)}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(label)} 近期走勢圖">
      <path class="class-line-track" d="${path}"></path>
      <circle class="class-line-end" cx="${mapped[mapped.length - 1].x.toFixed(1)}" cy="${mapped[mapped.length - 1].y.toFixed(1)}" r="3"></circle>
    </svg>
  `;
}
function renderUsMarketSectorRankingTable(items = [], groupKey = "") {
  return `
    <div class="class-table-head">
      <span>名稱</span>
      <span>數值</span>
      <span>漲跌</span>
      <span>漲跌幅</span>
      <span>成交量</span>
      <span>成交金額</span>
      <span>走勢圖</span>
    </div>
    ${items.map((item) => {
      const tone = getUsMarketTone(item.pct);
      return `
        <article class="class-table-row" id="${escapeHtml(`us-market-ranking-${item.symbol || item.name || ""}`)}">
          ${renderUsMarketSectorRankingName(item, groupKey)}
          <strong>${formatGlobalValue(item.close)}</strong>
          <strong class="${toneClass(tone)}">${escapeHtml(formatUsMarketRankingChange(item.change))}</strong>
          <strong class="${toneClass(tone)}">${escapeHtml(formatUsMarketPct(item.pct))}</strong>
          <span>${formatGlobalVolume(item.volumeValue ?? item.volume)}</span>
          <span>${formatUsMarketRankingAmount(item)}</span>
          <div class="class-chart-cell">${renderUsMarketSectorLineChart(item, groupKey)}</div>
        </article>
      `;
    }).join("")}
  `;
}
function renderUsMarketSectorRanking(model) {
  const { groups, activeGroup } = getUsMarketSectorRankingContext(model);
  const items = sortUsMarketSectorRankingItems(activeGroup?.items || [], activeGroup?.key || "");
  return `
    <div class="class-board-head">
      <div>
        <p class="eyebrow">族群走勢</p>
        <h3>${escapeHtml(activeGroup?.label || "美股類股")}排行</h3>
      </div>
      <div class="sector-sort-slot">${renderUsMarketSectorSortControl()}</div>
    </div>
    ${renderUsMarketSectorRankingTabs(groups, activeGroup?.key || "sp500")}
    ${items.length
      ? `<div class="class-table">${renderUsMarketSectorRankingTable(items, activeGroup?.key || "")}</div>`
      : `<p class="stock-detail-empty">${escapeHtml(activeGroup?.label || "美股類股")}資料同步中。</p>`}
  `;
}
function bindUsMarketOverviewControls(payload = {}) {
  const root = document.getElementById("global-market-root");
  const ranking = root?.querySelector("[data-us-market-sector-ranking]");
  if (!ranking) return;
  const rerenderRanking = () => {
    ranking.innerHTML = renderUsMarketSectorRanking(getUsMarketOverviewModel(payload));
    bindUsMarketOverviewControls(payload);
  };
  ranking.querySelectorAll("[data-us-market-sector-ranking-group]").forEach((button) => {
    button.addEventListener("click", () => {
      usMarketSectorRankingState.groupKey = button.dataset.usMarketSectorRankingGroup || "sp500";
      rerenderRanking();
    });
  });
  ranking.querySelector("[data-us-market-sector-sort]")?.addEventListener("change", (event) => {
    usMarketSectorRankingState.sortKey = event.target.value || "source_order";
    rerenderRanking();
  });
}
function renderUsMarketInsightPanel(model) {
  const analysis = model.analysis;
  const riskTone = analysis.riskScore >= 70 ? "high" : analysis.riskScore >= 55 ? "medium" : "low";
  const leaders = buildUsMarketRankItems(model.rankedSectors, 5);
  const laggards = buildUsMarketRankItems(model.rankedSectors.slice().reverse(), 5);
  const advice = [
    analysis.action,
    analysis.forecast.summary,
    ...analysis.riskNotes.slice(0, 2),
    ...analysis.opportunityNotes.slice(0, 2),
  ].filter(Boolean).slice(0, 5);
  return `
    <section class="market-ai-panel market-ai-risk-${riskTone}">
      <div class="market-ai-summary-grid">
        <article>
          <span>市場趨勢</span>
          <strong>${escapeHtml(analysis.trendLabel)}</strong>
          <small>${escapeHtml(analysis.indexText)}</small>
        </article>
        <article>
          <span>風險等級</span>
          <strong>${escapeHtml(analysis.riskLevel)}</strong>
          <small>風險分數 ${analysis.riskScore}/100 · VIX ${formatGlobalValue(model.vix?.close)} · ${escapeHtml(model.vixBand.label)}</small>
        </article>
        <article>
          <span>市場廣度</span>
          <strong>${escapeHtml(analysis.breadthText)}</strong>
          <small>${escapeHtml(analysis.breadthDetail)} 樣本平均 ${escapeHtml(analysis.averageText)}。</small>
        </article>
      </div>
      <div class="market-ai-rank-grid">
        <section>
          <h4>推薦類股 TOP5</h4>
          ${renderUsMarketRankList(leaders, "leader")}
        </section>
        <section>
          <h4>避險 / 弱勢觀察 TOP5</h4>
          ${renderUsMarketRankList(laggards, "hedge")}
        </section>
      </div>
      <section class="market-ai-advice">
        <h4>AI 分析建議</h4>
        <ul>${advice.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>美股盤勢資料同步中，請稍後重新整理。</li>"}</ul>
      </section>
    </section>
  `;
}
function renderUsMarketRiskAdviceCard(model) {
  const analysis = model.analysis || {};
  const riskScore = Number.isFinite(Number(analysis.riskScore)) ? Number(analysis.riskScore) : 50;
  const riskTone = riskScore >= 70 ? "high" : riskScore >= 55 ? "medium" : "low";
  const riskLabel = riskTone === "high" ? "高風險" : riskTone === "medium" ? "中度風險" : "低風險";
  const vixValue = parseMarketNumber(model.vix?.close);
  const vixPct = parseMarketNumber(model.vix?.pct);
  const breadthTotal = model.advancers + model.decliners;
  const breadthRatio = breadthTotal ? model.advancers / breadthTotal : null;
  const majorMoves = (model.majorItems || [])
    .map((item) => ({ item, pct: parseMarketNumber(item.pct) }))
    .filter((entry) => Number.isFinite(entry.pct));
  const positiveIndexes = majorMoves.filter((entry) => entry.pct > 0).length;
  const negativeIndexes = majorMoves.filter((entry) => entry.pct < 0).length;
  const indexLeader = majorMoves.slice().sort((left, right) => right.pct - left.pct)[0];
  const indexLaggard = majorMoves.slice().sort((left, right) => left.pct - right.pct)[0];
  const sectorLeader = model.rankedSectors?.[0] || null;
  const sectorLaggard = model.rankedSectors?.at(-1) || null;
  const sectorLeaderPct = parseMarketNumber(sectorLeader?.pct);
  const sectorLaggardPct = parseMarketNumber(sectorLaggard?.pct);
  const sectorSpread = Number.isFinite(sectorLeaderPct) && Number.isFinite(sectorLaggardPct)
    ? sectorLeaderPct - sectorLaggardPct
    : null;
  const exposure = riskScore >= 70
    ? { label: "防守曝險", range: "30-45%", text: "以現金、分批與保護型部位為主，避免追高和槓桿。" }
    : riskScore >= 55
      ? { label: "控管曝險", range: "45-60%", text: "保留核心部位，但新增倉位需等待回測或 VIX 降溫。" }
      : riskScore <= 35
        ? { label: "進攻曝險", range: "65-80%", text: "風險可控時可追蹤強勢類股，但仍以停損控管單筆風險。" }
        : { label: "中性曝險", range: "55-70%", text: "市場尚未明確失控，採強弱分流並避免過度集中。" };
  const hedge = riskScore >= 70
    ? "提高避險權重，槓桿與逆勢攤平暫停。"
    : riskScore >= 55
      ? "保留部分避險，等 VIX 與市場廣度改善再放大部位。"
      : "避險以停損與倉位紀律為主，不需過度壓低有效曝險。";
  const riskDrivers = [
    {
      label: "波動率",
      tone: Number.isFinite(vixValue) && (vixValue >= 25 || (Number.isFinite(vixPct) && vixPct > 4)) ? "negative" : "watch",
      text: `VIX ${formatGlobalValue(model.vix?.close)} / ${model.vix?.pct || "--"}，${model.vixBand?.text || analysis.vixBand?.text || "波動資料同步中。"}`,
    },
    {
      label: "市場廣度",
      tone: Number.isFinite(breadthRatio) ? (breadthRatio >= 0.6 ? "positive" : breadthRatio <= 0.4 ? "negative" : "watch") : "watch",
      text: Number.isFinite(breadthRatio)
        ? `${model.advancers} 檔上漲、${model.decliners} 檔下跌，上漲占比 ${(breadthRatio * 100).toFixed(0)}%。`
        : "上漲下跌樣本不足，暫不提高廣度權重。",
    },
    {
      label: "指數分歧",
      tone: positiveIndexes > negativeIndexes ? "positive" : negativeIndexes > positiveIndexes ? "negative" : "watch",
      text: indexLeader
        ? `${getUsBenchmarkDisplayName(indexLeader.item)} 領先 ${indexLeader.pct >= 0 ? "+" : ""}${indexLeader.pct.toFixed(2)}%，${indexLaggard ? `${getUsBenchmarkDisplayName(indexLaggard.item)} ${indexLaggard.pct >= 0 ? "+" : ""}${indexLaggard.pct.toFixed(2)}%` : "落後指數待確認"}。`
        : "主要指數資料仍在同步。",
    },
    {
      label: "類股落差",
      tone: Number.isFinite(sectorSpread) && sectorSpread >= 3 ? "watch" : "neutral",
      text: sectorLeader && sectorLaggard
        ? `${getUsSectorDisplayName(sectorLeader)} ${sectorLeader.pct || "--"}，${getUsSectorDisplayName(sectorLaggard)} ${sectorLaggard.pct || "--"}，差距 ${Number.isFinite(sectorSpread) ? sectorSpread.toFixed(2) : "--"}pt。`
        : "類股排行仍在同步。",
    },
  ];
  const playbook = [
    {
      label: "部位節奏",
      text: exposure.text,
    },
    {
      label: "避險設定",
      text: hedge,
    },
    {
      label: "觀察主線",
      text: model.strongest
        ? `強勢樣本 ${model.strongest.symbol || model.strongest.name} ${model.strongest.pct || "--"} 續強時，需同步檢查成交量與類股擴散。`
        : "強勢樣本不足，先觀察主要指數與類股是否同向。",
    },
    {
      label: "弱勢警戒",
      text: model.weakest
        ? `弱勢樣本 ${model.weakest.symbol || model.weakest.name} ${model.weakest.pct || "--"} 若擴散到同族群，降低追價權重。`
        : "弱勢樣本不足，暫以 VIX 與廣度做風險警戒。",
    },
  ];
  const triggerCards = [
    {
      label: "提高曝險條件",
      tone: "positive",
      text: "至少 3 個主要指數轉強、VIX 低於 20 或回落、市場廣度站上 60%，再提高新倉權重。",
    },
    {
      label: "降低曝險條件",
      tone: "negative",
      text: "VIX 高於 25 或單日大升、廣度低於 40%、主要指數同步轉弱時，先降槓桿與追價。",
    },
    {
      label: "觀望條件",
      tone: "watch",
      text: "指數分歧但類股有主線時，採小部位測試；若類股也分散，等待下一次資料更新。",
    },
  ];
  return `
    <article class="market-risk-card market-risk-${riskTone}" aria-live="polite">
      <div class="market-risk-heading">
        <div>
          <p class="panel-kicker">AI Risk Advisor</p>
          <h3>AI 風險建議</h3>
        </div>
        <span class="market-risk-level">${escapeHtml(riskLabel)}</span>
      </div>
      <p class="market-risk-summary">
        <b>${escapeHtml(analysis.regime?.label || "市場風險評估")}</b>
        <span>${escapeHtml(analysis.forecast?.label || "情境推估")} · 信心 ${escapeHtml(analysis.confidence || "--")} · ${escapeHtml(analysis.forecast?.horizon || "未來 3-5 個交易日")}</span>
      </p>
      <div class="market-risk-dashboard">
        <div class="market-risk-meter">
          <span>風險分數</span>
          <strong>${Math.round(riskScore)}<small>/100</small></strong>
          <div class="market-risk-meter-bar" style="--risk-score: ${Math.max(0, Math.min(100, riskScore))}%"><i></i></div>
          <p>${escapeHtml(analysis.riskLevel || riskLabel)} · ${escapeHtml(exposure.label)} ${escapeHtml(exposure.range)}</p>
        </div>
        <div class="market-risk-stat-grid">
          <span><b>${escapeHtml(exposure.range)}</b><small>建議研究曝險</small></span>
          <span><b>${formatGlobalValue(model.vix?.close)}</b><small>VIX 最新</small></span>
          <span><b>${Number.isFinite(breadthRatio) ? `${(breadthRatio * 100).toFixed(0)}%` : "--"}</b><small>上漲占比</small></span>
          <span><b>${analysis.forecast?.bearish ?? "--"}%</b><small>空方情境</small></span>
        </div>
      </div>
      <div class="market-risk-content market-risk-content-enhanced">
        <div>
          <h4>主要風險來源</h4>
          <div class="market-risk-driver-list">
            ${riskDrivers.map((item) => `
              <article class="market-risk-driver is-${escapeHtml(item.tone)}">
                <span>${escapeHtml(item.label)}</span>
                <p>${escapeHtml(item.text)}</p>
              </article>
            `).join("")}
          </div>
        </div>
        <div>
          <h4>執行策略</h4>
          <div class="market-risk-playbook">
            ${playbook.map((item) => `
              <article>
                <b>${escapeHtml(item.label)}</b>
                <p>${escapeHtml(item.text)}</p>
              </article>
            `).join("")}
          </div>
        </div>
      </div>
      <div class="market-risk-trigger-grid">
        ${triggerCards.map((item) => `
          <article class="market-risk-trigger is-${escapeHtml(item.tone)}">
            <strong>${escapeHtml(item.label)}</strong>
            <p>${escapeHtml(item.text)}</p>
          </article>
        `).join("")}
      </div>
      <p class="market-risk-disclaimer">AI 分析依 Yahoo Finance 行情、主要指數、VIX 與類股樣本自動推估，僅供風險管理與研究參考，不構成投資建議。</p>
    </article>
  `;
}
function renderUsMarketDecisionInsights(model, upSectors = [], downSectors = [], upStocks = [], downStocks = []) {
  const analysis = model.analysis || {};
  const formatSigned = (value) => Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
  const majorMoves = (model.majorItems || [])
    .map((item) => ({ item, pct: parseMarketNumber(item.pct) }))
    .filter((entry) => Number.isFinite(entry.pct));
  const positiveIndexes = majorMoves.filter((entry) => entry.pct > 0);
  const negativeIndexes = majorMoves.filter((entry) => entry.pct < 0);
  const indexLeader = majorMoves.slice().sort((left, right) => right.pct - left.pct)[0];
  const indexLaggard = majorMoves.slice().sort((left, right) => left.pct - right.pct)[0];
  const vixValue = parseMarketNumber(model.vix?.close);
  const vixPct = parseMarketNumber(model.vix?.pct);
  const breadthTotal = model.advancers + model.decliners;
  const breadthRatio = breadthTotal ? model.advancers / breadthTotal : null;
  const sectorLeader = upSectors[0];
  const sectorLaggard = downSectors[0];
  const sectorLeaderPct = parseMarketNumber(sectorLeader?.pct);
  const sectorLaggardPct = parseMarketNumber(sectorLaggard?.pct);
  const sectorSpread = Number.isFinite(sectorLeaderPct) && Number.isFinite(sectorLaggardPct)
    ? sectorLeaderPct - sectorLaggardPct
    : null;
  const strongestStock = upStocks[0];
  const weakestStock = downStocks[0];
  const indexTone = positiveIndexes.length > negativeIndexes.length
    ? "positive"
    : negativeIndexes.length > positiveIndexes.length
      ? "negative"
      : "watch";
  const vixTone = Number.isFinite(vixValue) && (vixValue >= 25 || (Number.isFinite(vixPct) && vixPct > 4))
    ? "negative"
    : Number.isFinite(vixValue) && vixValue < 20 && (!Number.isFinite(vixPct) || vixPct <= 2)
      ? "positive"
      : "watch";
  const breadthTone = Number.isFinite(breadthRatio)
    ? breadthRatio >= 0.6 ? "positive" : breadthRatio <= 0.4 ? "negative" : "watch"
    : "watch";
  const sectorTone = Number.isFinite(sectorSpread)
    ? sectorSpread >= 3 ? "positive" : sectorSpread <= 1 ? "watch" : "neutral"
    : "watch";
  const strategyTone = analysis.riskScore >= 65
    ? "negative"
    : analysis.trendPower >= 58 && analysis.riskScore <= 55
      ? "positive"
      : "watch";
  const insights = [
    {
      label: "指數共振",
      tone: indexTone,
      value: `${positiveIndexes.length}/${majorMoves.length || "--"} 偏多`,
      body: indexLeader
        ? `${getUsBenchmarkDisplayName(indexLeader.item)} 領先 ${formatSigned(indexLeader.pct)}，${indexLaggard && indexLaggard !== indexLeader ? `${getUsBenchmarkDisplayName(indexLaggard.item)} 落後 ${formatSigned(indexLaggard.pct)}` : "主要指數尚未拉開差距"}。`
        : "主要指數資料仍在同步，暫以類股與 VIX 作輔助判斷。",
      action: positiveIndexes.length >= 3
        ? "多數指數同向時，強勢類股訊號可信度提高。"
        : negativeIndexes.length >= 3
          ? "多數指數轉弱時，先降低追價與槓桿。"
          : "指數不同步時，偏向區間輪動，不宜只看單一指數。",
    },
    {
      label: "VIX 風險",
      tone: vixTone,
      value: `${formatGlobalValue(model.vix?.close)} / ${model.vix?.pct || "--"}`,
      body: `${analysis.vixBand?.label || model.vixBand?.label || "VIX 待確認"}，風險分數 ${analysis.riskScore ?? "--"}/100。`,
      action: vixTone === "negative"
        ? "VIX 升溫時，強勢股也要用較小部位與明確停損。"
        : vixTone === "positive"
          ? "波動低檔時，可觀察突破是否伴隨成交量擴大。"
          : "VIX 中性時，類股擴散比單日漲跌更重要。",
    },
    {
      label: "類股輪動",
      tone: sectorTone,
      value: Number.isFinite(sectorSpread) ? `差距 ${sectorSpread.toFixed(2)}pt` : "--",
      body: sectorLeader && sectorLaggard
        ? `${sectorLeader.name} 領先 ${sectorLeader.pct}，${sectorLaggard.name} 落後 ${sectorLaggard.pct}。`
        : "類股強弱資料仍在同步。",
      action: Number.isFinite(sectorSpread) && sectorSpread >= 3
        ? "強弱差距擴大代表資金有主線，優先追蹤領先類股。"
        : "類股差距不大時，避免過早判定主線，等待連續性。",
    },
    {
      label: "市場廣度",
      tone: breadthTone,
      value: Number.isFinite(breadthRatio) ? `${(breadthRatio * 100).toFixed(0)}% 上漲` : "--",
      body: `${model.advancers} 檔上漲、${model.decliners} 檔下跌，樣本平均 ${analysis.averageText || "--"}。`,
      action: breadthTone === "positive"
        ? "廣度配合上升時，反彈較不容易只靠少數權值股。"
        : breadthTone === "negative"
          ? "廣度不足代表反彈品質偏弱，需觀察是否擴散。"
          : "廣度分歧時，採取強弱分流，比追大盤更有效。",
    },
    {
      label: "隔日策略",
      tone: strategyTone,
      value: analysis.forecast?.label || "情境推估",
      body: strongestStock && weakestStock
        ? `強勢樣本 ${strongestStock.symbol || strongestStock.name} ${strongestStock.pct || "--"}；弱勢樣本 ${weakestStock.symbol || weakestStock.name} ${weakestStock.pct || "--"}。`
        : analysis.action || "等待強弱樣本補齊後再提高訊號權重。",
      action: analysis.action || "先看主要指數、VIX 與類股是否同向確認。",
    },
  ];
  return `
    <div class="market-extreme-decision-head">
      <strong>AI 判讀重點</strong>
      <span>信心 ${escapeHtml(analysis.confidence || "--")} · ${escapeHtml(analysis.forecast?.horizon || "未來 3-5 個交易日")}</span>
    </div>
    <div class="market-decision-grid">
      ${insights.map((item, index) => `
        <article class="market-decision-item is-${escapeHtml(item.tone)}">
          <span>${String(index + 1).padStart(2, "0")}</span>
          <div>
            <b>${escapeHtml(item.label)}</b>
            <em>${escapeHtml(item.value)}</em>
            <p>${escapeHtml(item.body)}</p>
            <small>${escapeHtml(item.action)}</small>
          </div>
        </article>
      `).join("")}
    </div>
    <div class="market-decision-scenario">
      <span>多方 ${analysis.forecast?.bullish ?? "--"}%</span>
      <span>震盪 ${analysis.forecast?.neutral ?? "--"}%</span>
      <span>空方 ${analysis.forecast?.bearish ?? "--"}%</span>
    </div>
  `;
}
function renderUsMarketExtremeObservation(model) {
  const upSectors = buildUsMarketRankItems(model.rankedSectors, 5);
  const downSectors = buildUsMarketRankItems(model.rankedSectors.slice().reverse(), 5);
  const upStocks = model.usablePulseItems
    .slice()
    .sort((left, right) => (parseMarketNumber(right.pct) || 0) - (parseMarketNumber(left.pct) || 0))
    .slice(0, 5);
  const downStocks = model.usablePulseItems
    .slice()
    .sort((left, right) => (parseMarketNumber(left.pct) || 0) - (parseMarketNumber(right.pct) || 0))
    .slice(0, 5);
  const sectorRows = (items, tone) => items.map((item) => `
    <article class="market-extreme-sector ${tone}">
      <div>
        <strong>${escapeHtml(item.name)}</strong>
        <span>${escapeHtml(item.pct)}</span>
      </div>
      <p>${escapeHtml(item.reason)}</p>
      <small>以類股漲跌幅、成交量與主要指數方向作為觀察基準。</small>
    </article>
  `).join("");
  const stockLinks = (items, tone) => items.map((item) => `
    <a class="limit-move-stock-link" href="${safeUrl(buildUsStockSearchUrl(item.symbol))}">
      <strong>${escapeHtml(item.symbol || "--")} ${escapeHtml(item.name || "")}</strong>
      <span class="${toneClass(getUsMarketTone(item.pct))}">${escapeHtml(item.pct || "--")}</span>
      <small>${escapeHtml(item.group || item.exchange || "US")}</small>
    </a>
  `).join("") || '<span class="stock-detail-empty">個股樣本同步中。</span>';
  return `
    <article class="market-extreme-card market-extreme-wide">
      <div class="market-extreme-head">
        <div>
          <p class="panel-kicker">Market movers × AI watchlist</p>
          <h3>美股強弱觀察與 AI 觀察名單</h3>
        </div>
        <span>${escapeHtml(model.analysis.breadthText)}</span>
      </div>
      <p class="market-extreme-summary">以美股類股輪動、主要指數、VIX 與個股 / ETF 樣本同步觀察。${escapeHtml(model.analysis.indexText)}</p>
      <div class="market-extreme-metrics">
        <div><span>上漲樣本</span><strong>${model.advancers}</strong><small>市場廣度</small></div>
        <div><span>下跌樣本</span><strong>${model.decliners}</strong><small>風險擴散</small></div>
        <div><span>樣本平均</span><strong>${escapeHtml(model.analysis.averageText)}</strong><small>漲跌幅</small></div>
        <div><span>觀察模式</span><strong>類股優先</strong><small>VIX 輔助</small></div>
      </div>
      <div class="market-extreme-layout">
        <section>
          <h4>強勢樣本：類股主軸</h4>
          <div class="market-extreme-sector-list">${sectorRows(upSectors, "is-positive")}</div>
          <h4 class="market-extreme-subtitle">個股 / ETF 連結樣本</h4>
          <div class="limit-move-sample-list is-positive">${stockLinks(upStocks, "is-positive")}</div>
        </section>
        <section>
          <h4>弱勢樣本：風險類股</h4>
          <div class="market-extreme-sector-list">${sectorRows(downSectors, "is-negative")}</div>
          <h4 class="market-extreme-subtitle">個股 / ETF 連結樣本</h4>
          <div class="limit-move-sample-list is-negative">${stockLinks(downStocks, "is-negative")}</div>
        </section>
      </div>
      <div class="market-extreme-decision">
        ${renderUsMarketDecisionInsights(model, upSectors, downSectors, upStocks, downStocks)}
      </div>
      <p class="market-extreme-note">此卡用於美股盤勢與隔日觀察排序，不構成投資建議。</p>
    </article>
  `;
}
function normalizeUsNewsText(value) {
  return String(value || "")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201c\u201d]/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}
function buildUsMarketNewsFallbackTitle(title) {
  const text = normalizeUsNewsText(title).toLowerCase();
  const topics = [];
  if (/\bai\b|artificial intelligence/.test(text)) topics.push("AI");
  if (/\betf|exchange-traded/.test(text)) topics.push("ETF");
  if (/s&p 500|spx|spy/.test(text)) topics.push("S&P 500");
  if (/nasdaq|qqq/.test(text)) topics.push("那斯達克");
  if (/dow jones|\bdia\b/.test(text)) topics.push("道瓊");
  if (/russell|iwm/.test(text)) topics.push("羅素2000");
  if (/vix|volatility/.test(text)) topics.push("VIX");
  if (/option/.test(text)) topics.push("選擇權");
  if (/stock|equities|shares/.test(text)) topics.push("美股個股");
  if (/space/i.test(title)) topics.push("SpaceX");
  const uniqueTopics = [...new Set(topics)].slice(0, 3);
  return `${uniqueTopics.length ? uniqueTopics.join("／") : "美股市場"}最新快訊`;
}
function localizeUsMarketNewsTitle(value) {
  const title = normalizeUsNewsText(value);
  if (!title) return "--";
  if (/[\u4e00-\u9fff]/.test(title)) return title;

  const crashMatch = title.match(/^The Next ([\d.]+)% Crash Will Happen\. These (\d+) ETFs Mean You Won't Panic-Sell at the Bottom$/i);
  if (crashMatch) {
    return `下一波 ${crashMatch[1]}% 崩跌將會發生：這 ${crashMatch[2]} 檔 ETF 讓你不會在底部恐慌賣出`;
  }

  const analystMatch = title.match(/^An Analyst Called (.+?)'s Valuation ["']?(.+?)["']?\. Options Traders Are Betting the Other Way$/i);
  if (analystMatch) {
    return `分析師稱 ${analystMatch[1]} 估值「${analystMatch[2]}」；選擇權交易員卻押注相反方向`;
  }

  const predictionMatch = title.match(/^Prediction:\s*This Unstoppable (.+?) ETF Will Beat the S&P 500 in the Second Half of (\d{4})$/i);
  if (predictionMatch) {
    return `預測：這檔強勢 ${predictionMatch[1]} ETF 將在 ${predictionMatch[2]} 下半年擊敗 S&P 500`;
  }

  const bestPerformingMatch = title.match(/^(.+?) Is the Best-Performing S&P 500 Stock During the First Half of (\d{4})\.\s*Here's What Stock I Think Will Dominate the Second Half \(Hint: It's Not (.+?)\)$/i);
  if (bestPerformingMatch) {
    return `${bestPerformingMatch[1]} 是 ${bestPerformingMatch[2]} 上半年 S&P 500 表現最佳股票；我認為下半年將由另一檔股票主導（提示：不是 ${bestPerformingMatch[3]}）`;
  }

  const burryMatch = title.match(/^Michael Burry's newest short reveals what really worries him about AI$/i);
  if (burryMatch) return "Michael Burry 最新放空部位透露他真正擔心的 AI 問題";

  if (/^Exchange-Traded Funds Fall, US Equities Mixed After Midday$/i.test(title)) {
    return "交易所交易基金走跌，美股午盤後漲跌互見";
  }

  const replacements = [
    [/exchange-traded funds/gi, "交易所交易基金"],
    [/\bETFs\b/g, "ETF"],
    [/\bETF\b/g, "ETF"],
    [/\bUS equities\b/gi, "美股"],
    [/\bUS stocks\b/gi, "美股"],
    [/\bWall Street\b/gi, "華爾街"],
    [/\boptions traders\b/gi, "選擇權交易員"],
    [/\banalyst\b/gi, "分析師"],
    [/\banalysts\b/gi, "分析師"],
    [/\bvaluation\b/gi, "估值"],
    [/\bcatastrophic\b/gi, "災難性"],
    [/\bcrash\b/gi, "崩跌"],
    [/\bfall\b/gi, "下跌"],
    [/\bfalls\b/gi, "下跌"],
    [/\bmixed\b/gi, "漲跌互見"],
    [/\bafter midday\b/gi, "午盤後"],
    [/\bprediction\b/gi, "預測"],
    [/\bwill beat\b/gi, "將擊敗"],
    [/\bsecond half\b/gi, "下半年"],
    [/\bfirst half\b/gi, "上半年"],
    [/\bbest-performing\b/gi, "表現最佳"],
    [/\bstock\b/gi, "股票"],
    [/\bstocks\b/gi, "股票"],
    [/\bAI\b/g, "AI"],
  ];
  let translated = title;
  replacements.forEach(([pattern, replacement]) => {
    translated = translated.replace(pattern, replacement);
  });
  const residue = translated
    .replace(/\b(S&P|ETF|ETFs|AI|VIX|NASDAQ|Nasdaq|Dow|Jones|Russell|SpaceX|Vanguard|SanDisk|Sandisk|Michael|Burry|Yahoo|Finance|US)\b/g, "")
    .match(/[A-Za-z]{3,}/g) || [];
  return translated === title || residue.length >= 3 ? buildUsMarketNewsFallbackTitle(title) : translated;
}
function localizeUsMarketNewsTag(value) {
  const tag = normalizeUsNewsText(value);
  if (!tag) return "美股快訊";
  if (/yahoo finance/i.test(tag)) return "美股快訊";
  if (/market news/i.test(tag)) return "市場新聞";
  if (/market breadth/i.test(tag)) return "市場廣度";
  if (/vix watch/i.test(tag)) return "VIX 觀察";
  if (/strong \/ weak/i.test(tag)) return "強弱觀察";
  if (/next session/i.test(tag)) return "下個交易日";
  return /[\u4e00-\u9fff]/.test(tag) ? tag : "美股快訊";
}
function renderUsMarketNewsGrid(model) {
  const onlineNews = Array.isArray(model.payload?.news) ? model.payload.news : [];
  const newsItems = onlineNews.length ? onlineNews.slice(0, 6) : [
    {
      tag: "Market breadth",
      title: model.analysis.breadthText,
      body: `${model.analysis.breadthDetail} 樣本平均 ${model.analysis.averageText}。`,
    },
    {
      tag: "VIX watch",
      title: model.vixBand.label,
      body: model.vixBand.text,
    },
    {
      tag: "Strong / Weak",
      title: `${model.strongest?.symbol || "--"} vs ${model.weakest?.symbol || "--"}`,
      body: `最強樣本 ${model.strongest?.name || "--"} ${model.strongest?.pct || "--"}；最弱樣本 ${model.weakest?.name || "--"} ${model.weakest?.pct || "--"}。`,
    },
    {
      tag: "Next session",
      title: model.analysis.forecast.label,
      body: model.analysis.action,
    },
  ];
  return `
    <div class="news-grid">
      ${newsItems.map((item) => {
        const translatedTitle = localizeUsMarketNewsTitle(item.title);
        const originalTitle = normalizeUsNewsText(item.title);
        const linkTitle = originalTitle && translatedTitle !== originalTitle ? ` title="${escapeHtml(originalTitle)}"` : "";
        return `
          <article class="news-card">
            <span class="news-tag">${escapeHtml(localizeUsMarketNewsTag(item.tag || item.source || "Market news"))}</span>
            <h3>${item.link ? `<a class="global-market-link" href="${safeUrl(item.link)}" target="_blank" rel="noopener noreferrer"${linkTitle}>${escapeHtml(translatedTitle)}</a>` : escapeHtml(translatedTitle)}</h3>
            <p>${escapeHtml(item.body || [item.source, item.publishedAt].filter(Boolean).join(" · ") || "Yahoo Finance 線上新聞")}</p>
          </article>
        `;
      }).join("")}
    </div>
  `;
}
function renderUsMarketOverviewLikeTaiwan(payload = {}) {
  const model = getUsMarketOverviewModel(payload);
  const counts = getUsMarketPayloadCounts(payload);
  return `
    <section class="subpage-hero global-market-hero">
      <p class="eyebrow">美股盤勢</p>
      <h1>主要指數與風險情緒總覽</h1>
      <p class="hero-text">集中查看 S&P 500、Nasdaq、Dow Jones、Russell 2000 與 VIX，並搭配類股輪動、強弱樣本與 AI 風險建議判斷市場氛圍。</p>
      <p class="source-note">資料來源：${escapeHtml(payload.source || "Yahoo Finance")} · 更新時間 ${escapeHtml(payload.updatedAt || "--")} ${payload.cached ? "· 快取" : ""}</p>
      <p class="source-note">盤勢精選行情 ${Number(counts.quoteCount).toLocaleString("zh-TW")} 筆是指數、VIX、類股與代表性個股樣本，不等同於美股上市個股明細總數。</p>
    </section>

    <section class="section" id="us-market-overview">
      <div class="overview-grid">${renderUsMarketOverviewCards(model)}</div>
    </section>

    <section class="section split-layout market-institution-layout">
      <article class="panel-card market-institution-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">市場資金</p>
            <h3>主要指數與類股動向</h3>
          </div>
          <div class="us-summary-actions">
            <span class="chip chip-blue">${escapeHtml(payload.updatedAt || "--")}</span>
            <button class="global-refresh" type="button" data-global-refresh="${escapeHtml(payload.category || "us-stocks")}">重新整理</button>
          </div>
        </div>
        <div class="institution-summary">${renderUsMarketInstitutionSummary(model)}</div>
        <div class="institution-detail-head">
          <span>指標</span>
          <span>最新</span>
          <span>漲跌幅</span>
          <span>觀察</span>
        </div>
        <div class="institution-list">${renderUsMarketInstitutionRows(model)}</div>
        <div class="institution-sector-ranking" data-us-market-sector-ranking>${renderUsMarketSectorRanking(model)}</div>
      </article>

      <article class="panel-card market-notes-card">
        <div class="card-title-row">
          <h3>市場提示</h3>
          <span class="chip chip-gold">自動整理</span>
        </div>
        <div class="market-ai-insight">${renderUsMarketInsightPanel(model)}</div>
      </article>
    </section>

    <section class="section">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">After market</p>
          <h2>美股盤後快訊</h2>
        </div>
        <span class="chip chip-gold">每日盤後整理</span>
      </div>
      ${renderUsMarketRiskAdviceCard(model)}
      ${renderUsMarketExtremeObservation(model)}
      ${renderUsMarketNewsGrid(model)}
    </section>
  `;
}
function renderGlobalMarketPage(payload) {
  const root = document.getElementById("global-market-root");
  if (!root || !payload) return;
  window.currentGlobalMarketPayload = payload;
  const isUsMarketOverviewPage = payload.category === "us-stocks" && document.body.dataset.marketView === "overview";
  if (isUsMarketOverviewPage) {
    root.innerHTML = renderUsMarketOverviewLikeTaiwan(payload);
    bindUsMarketOverviewControls(payload);
    return;
  }
  const isDerivativePage = ["futures", "options"].includes(payload.category);
  const marketSectionItems = payload.category === "us-stocks"
    ? (payload.items || []).filter((item) => item.group !== "主要指數" && item.group !== "美股個股" && item.symbol !== "^VIX")
    : (payload.items || []);
  const architectureHtml = ["us-stocks", "futures"].includes(payload.category) ? "" : renderAssetPlatformDashboard(payload);
  const derivativesHtml = payload.category === "futures"
    ? renderDerivativesFuturesPanel(payload)
    : payload.category === "options"
      ? renderDerivativesOptionsPanel(payload)
      : "";
  root.innerHTML = `
    <section class="subpage-hero global-market-hero">
      <p class="eyebrow">${escapeHtml(getAssetPlatformConfig(payload.category, payload.title).kicker || payload.kicker || "Global Market")}</p>
      <h1>${escapeHtml(getAssetPlatformConfig(payload.category, payload.title).title || payload.title || "全球市場")}</h1>
      <p class="hero-text">${escapeHtml(payload.subtitle || "")}</p>
      <p class="source-note">資料來源：${escapeHtml(payload.source || "Yahoo Finance")} · 更新時間 ${escapeHtml(payload.updatedAt || "--")} ${payload.cached ? "· 快取" : ""}</p>
    </section>

    ${architectureHtml}

    ${isDerivativePage ? renderDerivativesSinglePageContent(payload) : `
    ${renderUsMajorIndexVixCard(payload)}

    ${renderUsSectorIndexComparisonCard(payload)}

    <section class="section" id="us-market-overview">
      ${renderGlobalSummaryCard(payload)}
    </section>

    ${derivativesHtml}

    ${payload.category === "us-stocks" ? renderUsSectorStocksBrowser(payload) : `
    <section class="section">
      ${renderGlobalMarketSections(marketSectionItems)}
    </section>`}

    ${payload.category === "us-stocks" ? "" : `
    <section class="section">
      <article class="panel-card global-table-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">Online data</p>
            <h3>線上資料明細</h3>
          </div>
        </div>
        <div class="global-table-wrap">
          <table class="global-market-table">
            <thead>
              <tr>
                <th>名稱</th>
                <th>代號</th>
                <th>地區</th>
                <th>交易所 / 來源</th>
                <th>分類</th>
                <th>收盤</th>
                <th>漲跌幅</th>
                <th>開盤</th>
                <th>最高</th>
                <th>最低</th>
                <th>量能欄位</th>
                <th>日期</th>
              </tr>
            </thead>
            <tbody>
              ${(payload.category === "us-stocks" ? marketSectionItems : (payload.items || [])).map((item) => {
                const metric = getAssetHubMetric(item);
                const internalLink = payload.category === "us-stocks" ? buildUsStockSearchUrl(item.symbol) : getAssetHubItemUrl(item);
                const targetAttrs = payload.category === "us-stocks" ? "" : ' target="_blank" rel="noopener noreferrer"';
                return `
                <tr>
                  <td><a class="global-market-link" href="${safeUrl(internalLink)}"${targetAttrs}>${escapeHtml(item.name || "--")}</a></td>
                  <td>${escapeHtml(item.symbol || "--")}</td>
                  <td>${escapeHtml(getAssetHubRegion(item))}</td>
                  <td>${escapeHtml(item.exchange || item.dataSource || item.source || "--")}</td>
                  <td>${escapeHtml(item.group || item.type || "--")}</td>
                  <td>${formatGlobalValue(item.close)}</td>
                  <td class="${toneClass((parseMarketNumber(item.pct) || 0) > 0 ? "up" : (parseMarketNumber(item.pct) || 0) < 0 ? "down" : "flat")}">${escapeHtml(item.pct || "--")}</td>
                  <td>${formatGlobalValue(item.open)}</td>
                  <td>${formatGlobalValue(item.high)}</td>
                  <td>${formatGlobalValue(item.low)}</td>
                  <td><span class="asset-table-metric">${escapeHtml(metric.label)}</span>${formatGlobalVolume(metric.value)}</td>
                  <td>${escapeHtml(item.date || "--")}</td>
                </tr>
              `; }).join("")}
            </tbody>
          </table>
        </div>
      </article>
    </section>`}`}
  `;
  if (!isDerivativePage) {
    bindUsMajorIndexVixCard(payload);
    bindUsSectorIndexComparisonCard(payload);
  }
  if (payload.category === "us-stocks") {
    bindUsSectorStocksBrowser();
    loadUsSectorStocks();
  }
  if (payload.category === "futures") bindDerivativesFuturesPanel(payload);
  if (payload.category === "options") bindDerivativesOptionsPanel(payload);
  if (["futures", "options"].includes(payload.category)) bindDerivativeWatchlistControls(payload);
  if (isDerivativePage) bindDerivativeAssetLoadMore(payload);
  if (payload.category === "options") hydrateOptionsAiExtras(payload);
  root.querySelectorAll(".global-technical-chart").forEach((chartView) => bindChartHover(chartView));
}
async function initGlobalMarketPage(refresh = false) {
  const root = document.getElementById("global-market-root");
  const category = document.body.dataset.marketCategory || "";
  if (!root || !category) return;
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">Global Market</p>
      <h1>線上資料載入中</h1>
      <p class="hero-text">正在取得 Yahoo Finance 最新市場資料...</p>
    </section>
  `;
  try {
    const initialLimit = category === "us-stocks" && document.body.dataset.marketView === "overview"
      ? "all"
      : ["precious-metals", "bonds", "futures"].includes(category)
      ? "all"
      : ["futures", "options"].includes(category)
        ? 12
        : 18;
    const queryParams = new URLSearchParams();
    queryParams.set("limit", refresh ? "all" : String(initialLimit));
    if (refresh) queryParams.set("refresh", "1");
    if (category === "options") {
      queryParams.set("source", derivativesOptionsChainSource);
      queryParams.set("underlying", derivativesOptionsSelectedUnderlying);
    }
    const query = `?${queryParams.toString()}`;
    const derivativesApi = ["futures", "options"].includes(category);
    const endpoint = derivativesApi
      ? `/api/${encodeURIComponent(category)}${query}`
      : `/api/global-market/${encodeURIComponent(category)}${query}`;
    const response = await fetchWithTimeout(endpoint, { cache: "no-store" }, 120000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const responsePayload = await response.json();
    if (derivativesApi && responsePayload.success === false) {
      throw new Error(responsePayload?.error?.message || "資料暫不可用");
    }
    const payload = derivativesApi ? responsePayload.data : responsePayload;
    renderGlobalMarketPage(payload);
    if (category === "options" && !payload.optionChain) {
      fetchWithTimeout("/api/us-market/options-chain/SPY", { cache: "no-store" }, 16000)
        .then((optionChainResponse) => optionChainResponse.ok ? optionChainResponse.json() : null)
        .then((chain) => {
          if (chain) renderGlobalMarketPage({ ...payload, optionChain: chain });
        })
        .catch((error) => console.warn("Failed to load SPY options chain:", error));
    }
  } catch (error) {
    root.innerHTML = `
      <section class="subpage-hero">
        <p class="eyebrow">Global Market</p>
        <h1>線上資料暫時無法載入</h1>
        <p class="hero-text">請稍後再試，或確認部署環境可連線 Yahoo Finance。錯誤：${escapeHtml(error.message || error)}</p>
      </section>
    `;
    console.error("Failed to load global market page:", error);
  }
}
