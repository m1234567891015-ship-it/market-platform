function normalizePortfolioHistory(detail) {
  return (detail?.historyDays || [])
    .map((item) => ({
      date: item.date || item.label || "",
      close: parseAnalysisNumber(item.close),
      high: parseAnalysisNumber(item.high),
      low: parseAnalysisNumber(item.low),
      volume: parseAnalysisNumber(item.volume),
    }))
    .filter((item) => Number.isFinite(item.close));
}
function calculatePortfolioReturns(history, lookback = 80) {
  const window = history.slice(-lookback);
  const returns = [];
  for (let index = 1; index < window.length; index += 1) {
    const previous = window[index - 1]?.close;
    const current = window[index]?.close;
    if (previous > 0 && current > 0) returns.push((current - previous) / previous);
  }
  return returns;
}
function calculatePortfolioStdDev(values) {
  const clean = values.filter(Number.isFinite);
  if (clean.length < 2) return 0;
  const average = clean.reduce((sum, value) => sum + value, 0) / clean.length;
  const variance = clean.reduce((sum, value) => sum + (value - average) ** 2, 0) / (clean.length - 1);
  return Math.sqrt(Math.max(variance, 0));
}
function calculatePortfolioCorrelation(left, right) {
  const length = Math.min(left.length, right.length);
  if (length < 8) return null;
  const a = left.slice(-length);
  const b = right.slice(-length);
  const avgA = a.reduce((sum, value) => sum + value, 0) / length;
  const avgB = b.reduce((sum, value) => sum + value, 0) / length;
  let numerator = 0;
  let denomA = 0;
  let denomB = 0;
  for (let index = 0; index < length; index += 1) {
    const da = a[index] - avgA;
    const db = b[index] - avgB;
    numerator += da * db;
    denomA += da * da;
    denomB += db * db;
  }
  const denominator = Math.sqrt(denomA * denomB);
  return denominator ? numerator / denominator : null;
}
function calculatePeriodReturn(history, days) {
  if (!Array.isArray(history) || history.length < 2) return null;
  const end = history.at(-1)?.close;
  const start = history.length > days ? history.at(-(days + 1))?.close : history[0]?.close;
  if (!(start > 0) || !(end > 0)) return null;
  return ((end - start) / start) * 100;
}
function buildPortfolioTheoryAssessment(active, totals) {
  if (!active.length || !(totals.totalValue > 0)) {
    return {
      label: "等待部位資料",
      tone: "neutral",
      details: ["尚未建立持股權重，暫無法計算均值-變異、相關性與風險貢獻。"],
      actions: ["先輸入股數與進場價，再檢查單一權重、相關性與組合波動。"],
      metrics: {
        expectedReturn60: null,
        portfolioVolatility: null,
        averageCorrelation: null,
        diversificationRatio: null,
        effectivePositions: 0,
        efficiencyScore: null,
        topRiskContributor: null,
      },
    };
  }

  const items = active.map((position) => {
    const history = normalizePortfolioHistory(position.detail);
    const returns = calculatePortfolioReturns(history, 90);
    const dailyVolatility = calculatePortfolioStdDev(returns);
    const annualVolatility = dailyVolatility * Math.sqrt(252) * 100;
    const return20 = calculatePeriodReturn(history, 20);
    const return60 = calculatePeriodReturn(history, 60);
    const weight = position.marketValue / totals.totalValue;
    return {
      ...position,
      history,
      returns,
      dailyVolatility,
      annualVolatility,
      return20,
      return60,
      weight,
    };
  });

  const expectedReturn60 = items.reduce((sum, item) => sum + item.weight * (Number.isFinite(item.return60) ? item.return60 : Number.isFinite(item.return20) ? item.return20 : 0), 0);
  let covarianceSum = 0;
  let correlationSum = 0;
  let correlationCount = 0;
  for (let i = 0; i < items.length; i += 1) {
    for (let j = 0; j < items.length; j += 1) {
      const corr = i === j ? 1 : calculatePortfolioCorrelation(items[i].returns, items[j].returns);
      const safeCorr = Number.isFinite(corr) ? corr : 0.35;
      covarianceSum += items[i].weight * items[j].weight * items[i].dailyVolatility * items[j].dailyVolatility * safeCorr;
      if (j > i && Number.isFinite(corr)) {
        correlationSum += corr;
        correlationCount += 1;
      }
    }
  }
  const portfolioVolatility = Math.sqrt(Math.max(covarianceSum, 0)) * Math.sqrt(252) * 100;
  const weightedVolatility = items.reduce((sum, item) => sum + item.weight * item.annualVolatility, 0);
  const diversificationRatio = portfolioVolatility > 0 ? weightedVolatility / portfolioVolatility : null;
  const averageCorrelation = correlationCount ? correlationSum / correlationCount : null;
  const hhi = items.reduce((sum, item) => sum + item.weight ** 2, 0);
  const effectivePositions = hhi ? 1 / hhi : 0;
  const efficiencyScore = portfolioVolatility > 0 ? expectedReturn60 / portfolioVolatility : null;
  const riskBase = items.reduce((sum, item) => sum + item.weight * item.dailyVolatility, 0);
  const riskContributors = items.map((item) => ({
    code: item.stock.code,
    name: item.stock.name,
    contribution: riskBase ? (item.weight * item.dailyVolatility / riskBase) * 100 : item.weight * 100,
  })).sort((a, b) => b.contribution - a.contribution);
  const topRiskContributor = riskContributors[0] || null;

  const tone = portfolioVolatility >= 45 || effectivePositions < 2 || (averageCorrelation ?? 0) >= 0.75
    ? "negative"
    : portfolioVolatility >= 28 || effectivePositions < 3 || (averageCorrelation ?? 0) >= 0.55
      ? "neutral"
      : "positive";
  const label = tone === "positive" ? "組合理論結構健康" : tone === "negative" ? "組合理論風險偏高" : "組合理論需再平衡";
  const details = [
    `均值-變異：60 日權重動能 ${expectedReturn60 >= 0 ? "+" : ""}${expectedReturn60.toFixed(2)}%，年化波動估計 ${portfolioVolatility.toFixed(2)}%。`,
    `分散化：有效持股數 ${effectivePositions.toFixed(1)} 檔，分散化比率 ${Number.isFinite(diversificationRatio) ? diversificationRatio.toFixed(2) : "--"}。`,
    `相關性：平均相關係數 ${Number.isFinite(averageCorrelation) ? averageCorrelation.toFixed(2) : "資料不足"}，用於辨識同漲同跌風險。`,
    topRiskContributor ? `風險貢獻：${topRiskContributor.code} ${topRiskContributor.name} 約占 ${topRiskContributor.contribution.toFixed(1)}%。` : "風險貢獻資料不足。",
  ];
  const actions = [];
  if (effectivePositions < 2) actions.push("有效持股數偏低，組合接近單押，建議加入低相關標的或降低單一部位。");
  if ((averageCorrelation ?? 0) >= 0.65) actions.push("持股相關性偏高，分散看似增加但實際風險可能仍集中。");
  if (portfolioVolatility >= 35) actions.push("組合波動偏高，應降低高波動持股權重或提高現金/ETF 比例。");
  if (topRiskContributor?.contribution >= 45) actions.push(`最大風險貢獻集中在 ${topRiskContributor.code}，再平衡時優先檢查該部位。`);
  if (Number.isFinite(efficiencyScore) && efficiencyScore < 0) actions.push("風險效率為負，代表近期承擔波動未換得正向動能，宜保守。");
  if (!actions.length) actions.push("權重、相關性與波動暫未出現重大失衡，可依停損停利紀律持續監控。");

  return {
    label,
    tone,
    details,
    actions,
    metrics: {
      expectedReturn60,
      portfolioVolatility,
      averageCorrelation,
      diversificationRatio,
      effectivePositions,
      efficiencyScore,
      topRiskContributor,
    },
  };
}
function getSimulationSignal(analysis, currentPrice, entryPrice, shares, stopLossPct, takeProfitPct) {
  if (!(shares > 0) || !(entryPrice > 0) || !(currentPrice > 0)) {
    if (analysis?.score >= 5) return { label: "偏多等待回檔", tone: "positive", note: `型態與指標多方訊號較一致；${analysis.patterns?.[0] || "仍宜設定停損後再評估進場"}。` };
    if (analysis?.score <= -5) return { label: "暫緩進場", tone: "negative", note: `型態與指標偏弱；${analysis.indicators?.[0] || "等待趨勢止穩較為穩健"}。` };
    return { label: "等待確認", tone: "neutral", note: "目前尚未建立模擬部位，先觀察趨勢與籌碼共振。" };
  }

  const returnPct = ((currentPrice - entryPrice) / entryPrice) * 100;
  if (returnPct <= -stopLossPct) {
    return { label: "停損條件觸發", tone: "negative", note: "目前跌幅已超過設定停損，應重新檢視原始投資假設。" };
  }
  if (returnPct >= takeProfitPct) {
    return { label: "進入停利區間", tone: "positive", note: "已達模擬停利條件，可評估分批落袋或移動停利。" };
  }
  if (returnPct <= -stopLossPct * 0.7) {
    return { label: "接近停損", tone: "negative", note: "距離停損條件已近，避免因情緒任意放寬風險界線。" };
  }
  if (analysis?.score <= -5) {
    return { label: "弱勢減碼觀察", tone: "negative", note: `技術理論與多因子偏弱，${analysis.patterns?.[0] || "持有部位宜優先控制曝險"}。` };
  }
  if (analysis?.score >= 5 && returnPct >= 0) {
    return { label: "趨勢續抱觀察", tone: "positive", note: `損益與技術訊號同向，${analysis.indicators?.[0] || "可依原訂停利停損紀律續抱"}。` };
  }
  return { label: "區間持有觀察", tone: "neutral", note: "尚未觸及停損停利，持續觀察均線、法人與量價變化。" };
}
function technicalSma(values, period) {
  return values.map((_, index) => {
    if (index + 1 < period) return null;
    const window = values.slice(index - period + 1, index + 1);
    return window.every(Number.isFinite)
      ? window.reduce((sum, value) => sum + value, 0) / period
      : null;
  });
}
function technicalSlope(values) {
  const clean = values.filter(Number.isFinite);
  if (clean.length < 2) return 0;
  const center = (clean.length - 1) / 2;
  const average = clean.reduce((sum, value) => sum + value, 0) / clean.length;
  let numerator = 0;
  let denominator = 0;
  clean.forEach((value, index) => {
    const offset = index - center;
    numerator += offset * (value - average);
    denominator += offset * offset;
  });
  return denominator ? numerator / denominator : 0;
}
function technicalPivots(history, radius = 2) {
  const pivots = [];
  for (let index = radius; index < history.length - radius; index += 1) {
    const window = history.slice(index - radius, index + radius + 1);
    const high = history[index].high;
    const low = history[index].low;
    if (window.every((item) => high >= item.high)) pivots.push({ index, type: "high", value: high });
    if (window.every((item) => low <= item.low)) pivots.push({ index, type: "low", value: low });
  }
  return pivots.sort((a, b) => a.index - b.index);
}
function buildMarketBreadthIndicators(detail) {
  const requestedMarket = String(detail.market || "").toUpperCase();
  const stocks = (localAllStocks || []).filter((stock) => {
    const market = String(stock.market || "").toUpperCase();
    const securityType = String(stock.securityType || "").toUpperCase();
    const code = String(stock.code || "");
    const isStock = securityType
      ? securityType === "STOCK"
      : /^\d{4}$/.test(code) && !code.startsWith("00");
    return isStock && (!requestedMarket || market === requestedMarket);
  });
  const advancing = stocks.filter((stock) => parseAnalysisNumber(stock.pct) > 0).length;
  const declining = stocks.filter((stock) => parseAnalysisNumber(stock.pct) < 0).length;
  const unchanged = stocks.filter((stock) => parseAnalysisNumber(stock.pct) === 0).length;
  if (!advancing && !declining) return null;

  const adr = declining ? (advancing / declining) * 100 : advancing ? 999 : 100;
  const obos = advancing - declining;
  const date = detail.snapshotDate || data?.snapshotDate || new Date().toISOString().slice(0, 10);
  let history = [];
  try {
    history = JSON.parse(localStorage.getItem(MARKET_BREADTH_STORAGE_KEY) || "[]");
    if (!Array.isArray(history)) history = [];
  } catch {
    history = [];
  }
  const marketKey = requestedMarket || "ALL";
  const previous = [...history].reverse().find((item) => item.market === marketKey && item.date < date);
  const adl = (Number(previous?.adl) || 0) + obos;
  const snapshot = { date, market: marketKey, advancing, declining, unchanged, adr, obos, adl };
  const nextHistory = [
    ...history.filter((item) => !(item.market === marketKey && item.date === date)),
    snapshot,
  ].sort((a, b) => String(a.date).localeCompare(String(b.date))).slice(-180);
  try {
    localStorage.setItem(MARKET_BREADTH_STORAGE_KEY, JSON.stringify(nextHistory));
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }
  const marketHistory = nextHistory.filter((item) => item.market === marketKey);
  const previousAdl = marketHistory.length >= 2 ? Number(marketHistory.at(-2).adl) : null;
  return { ...snapshot, previousAdl, historyCount: marketHistory.length };
}
function buildFuturesBreadthProxyIndicators(history, period = 20) {
  if (!Array.isArray(history) || history.length < 6) return [];
  const comparable = history
    .map((row, index) => (index > 0 ? { row, previous: history[index - 1] } : null))
    .filter(Boolean)
    .slice(-Math.min(period, Math.max(history.length - 1, 1)));
  if (!comparable.length) return [];

  const advancing = comparable.filter(({ row, previous }) => row.close > previous.close).length;
  const declining = comparable.filter(({ row, previous }) => row.close < previous.close).length;
  const unchanged = comparable.length - advancing - declining;
  const adr = declining ? (advancing / declining) * 100 : advancing ? 999 : 100;
  const obos = advancing - declining;
  const obosPct = (obos / Math.max(comparable.length, 1)) * 100;
  const upVolume = comparable
    .filter(({ row, previous }) => row.close > previous.close)
    .reduce((sum, { row }) => sum + (Number.isFinite(row.volume) ? row.volume : 0), 0);
  const downVolume = comparable
    .filter(({ row, previous }) => row.close < previous.close)
    .reduce((sum, { row }) => sum + (Number.isFinite(row.volume) ? row.volume : 0), 0);
  const volumeBreadth = upVolume + downVolume > 0 ? (upVolume / (upVolume + downVolume)) * 100 : null;
  const deltaVolume = upVolume - downVolume;
  const firstClose = comparable[0]?.previous?.close;
  const latestClose = comparable.at(-1)?.row?.close;
  const closeChangePct = Number.isFinite(firstClose) && firstClose !== 0 && Number.isFinite(latestClose)
    ? ((latestClose - firstClose) / firstClose) * 100
    : null;
  const oiWindow = history
    .slice(-Math.min(period + 1, history.length))
    .map((row) => parseAnalysisNumber(row.openInterest))
    .filter(Number.isFinite);
  const oiChange = oiWindow.length >= 2 ? oiWindow.at(-1) - oiWindow[0] : null;
  const oiChangePct = Number.isFinite(oiChange) && Number.isFinite(oiWindow[0]) && oiWindow[0] !== 0
    ? (oiChange / oiWindow[0]) * 100
    : null;
  const signals = [];
  const periodText = `近 ${comparable.length} 根`;
  const adrDirection = adr >= 125 ? "bullish" : adr <= 80 ? "bearish" : "neutral";
  signals.push({
    name: "漲跌K比率 ADR代理",
    value: `${adr.toFixed(1)}%`,
    text: `${periodText}上漲 ${advancing} 根、下跌 ${declining} 根、平盤 ${unchanged} 根；以期貨自身 K 線替代市場廣度。`,
    direction: adrDirection,
    scoreDelta: adrDirection === "bullish" ? 1 : adrDirection === "bearish" ? -1 : 0,
  });
  const obosDirection = obosPct >= 15 ? "bullish" : obosPct <= -15 ? "bearish" : "neutral";
  signals.push({
    name: "OBOS K線代理",
    value: `${obos > 0 ? "+" : ""}${obos}`,
    text: `淨上漲 K 數占比 ${obosPct.toFixed(1)}%；${Math.abs(obosPct) >= 25 ? "短線情緒偏極端，需搭配量能確認" : "多空尚未過度擁擠"}。`,
    direction: obosDirection,
    scoreDelta: obosDirection === "bullish" ? 1 : obosDirection === "bearish" ? -1 : 0,
  });
  if (Number.isFinite(volumeBreadth)) {
    const volumeDirection = volumeBreadth >= 55 ? "bullish" : volumeBreadth <= 45 ? "bearish" : "neutral";
    signals.push({
      name: "上漲量占比",
      value: `${volumeBreadth.toFixed(1)}%`,
      text: `上漲 K 成交量 ${formatGlobalVolume(upVolume)}、下跌 K 成交量 ${formatGlobalVolume(downVolume)}；Delta Volume ${deltaVolume >= 0 ? "+" : ""}${formatGlobalVolume(deltaVolume)}。`,
      direction: volumeDirection,
      scoreDelta: volumeDirection === "bullish" ? 1 : volumeDirection === "bearish" ? -1 : 0,
    });
  }
  if (Number.isFinite(oiChange)) {
    const oiDirection = oiChange > 0 ? "bullish" : oiChange < 0 ? "bearish" : "neutral";
    signals.push({
      name: "未平倉 OI 趨勢",
      value: `${oiChange >= 0 ? "+" : ""}${formatGlobalVolume(oiChange)}`,
      text: `${periodText}未平倉${oiChange >= 0 ? "增加" : "下降"}${Number.isFinite(oiChangePct) ? ` ${oiChangePct >= 0 ? "+" : ""}${oiChangePct.toFixed(2)}%` : ""}；用來判斷部位是否留在場內。`,
      direction: oiDirection,
      scoreDelta: oiDirection === "bullish" ? 1 : oiDirection === "bearish" ? -1 : 0,
    });
    const structureDirection = Number.isFinite(closeChangePct)
      ? closeChangePct >= 0 && oiChange >= 0
        ? "bullish"
        : closeChangePct < 0 && oiChange >= 0
          ? "bearish"
          : closeChangePct >= 0 && oiChange < 0
            ? "neutral"
            : "bearish"
      : "neutral";
    const structureText = Number.isFinite(closeChangePct)
      ? closeChangePct >= 0 && oiChange >= 0
        ? "價格上行且 OI 增加，偏向多方增倉推進。"
        : closeChangePct < 0 && oiChange >= 0
          ? "價格下行但 OI 增加，偏向空方增倉壓制。"
          : closeChangePct >= 0 && oiChange < 0
            ? "價格上行但 OI 下降，可能是空方回補，延續性需看量能。"
            : "價格下行且 OI 下降，偏向多方減倉或退場。"
      : "價格與 OI 結構仍需更多資料確認。";
    signals.push({
      name: "價量 OI 結構",
      value: `${Number.isFinite(closeChangePct) ? `${closeChangePct >= 0 ? "+" : ""}${closeChangePct.toFixed(2)}%` : "--"} / ${oiChange >= 0 ? "+" : ""}${formatGlobalVolume(oiChange)}`,
      text: structureText,
      direction: structureDirection,
      scoreDelta: structureDirection === "bullish" ? 1 : structureDirection === "bearish" ? -1 : 0,
    });
  }
  return signals;
}
function calculatePsy(history, period = 12) {
  if (history.length < period + 1) return null;
  const window = history.slice(-(period + 1));
  let advances = 0;
  for (let index = 1; index < window.length; index += 1) {
    if (window[index].close > window[index - 1].close) advances += 1;
  }
  return (advances / period) * 100;
}
function classifyVolumePriceNinePatterns({ latest, previous, volumeRatio, averageTrend = null }) {
  const priceChangePct = previous?.close
    ? ((latest.close - previous.close) / previous.close) * 100
    : 0;
  const priceState = priceChangePct >= 0.3 ? "up" : priceChangePct <= -0.3 ? "down" : "flat";
  const volumeState = volumeRatio >= 1.15 ? "up" : volumeRatio <= 0.85 ? "down" : "flat";
  const trendText = averageTrend === null
    ? ""
    : `；均量趨勢 ${averageTrend >= 0 ? "+" : ""}${averageTrend.toFixed(1)}%`;
  const key = `${priceState}-${volumeState}`;
  const patterns = {
    "up-up": {
      name: "價漲量增",
      text: `量價同步轉強，上漲較有確認${trendText}`,
      direction: "bullish",
      score: 1,
    },
    "up-flat": {
      name: "價漲量平",
      text: `股價上漲但量能未明顯擴張，屬溫和上攻${trendText}`,
      direction: "bullish",
      score: 1,
    },
    "up-down": {
      name: "價漲量縮",
      text: `上攻量能不足，追價需防動能遞減${trendText}`,
      direction: "bearish",
      score: -1,
    },
    "flat-up": {
      name: "價平量增",
      text: `量能放大但價格未表態，可能有換手或主力吸籌/出貨${trendText}`,
      direction: "neutral",
      score: 0,
    },
    "flat-flat": {
      name: "價平量平",
      text: `量價皆平，市場觀望，等待突破或跌破確認${trendText}`,
      direction: "neutral",
      score: 0,
    },
    "flat-down": {
      name: "價平量縮",
      text: `量縮整理，籌碼沉澱但方向尚未明朗${trendText}`,
      direction: "neutral",
      score: 0,
    },
    "down-up": {
      name: "價跌量增",
      text: `下跌伴隨放量，賣壓較明顯${trendText}`,
      direction: "bearish",
      score: -1,
    },
    "down-flat": {
      name: "價跌量平",
      text: `股價走弱但量能未放大，偏弱整理仍需觀察支撐${trendText}`,
      direction: "bearish",
      score: -1,
    },
    "down-down": {
      name: "價跌量縮",
      text: `下跌量縮，賣壓未擴大但仍需止跌訊號${trendText}`,
      direction: "neutral",
      score: 0,
    },
  };
  return {
    ...(patterns[key] || patterns["flat-flat"]),
    priceChangePct,
    priceState,
    volumeState,
  };
}
function calculateBacktestAtrPct(history, period = 14) {
  if (!Array.isArray(history) || history.length <= period) return null;
  const trueRanges = [];
  for (let index = 1; index < history.length; index += 1) {
    const current = history[index];
    const previous = history[index - 1];
    if (![current.high, current.low, previous.close].every(Number.isFinite)) continue;
    trueRanges.push(Math.max(
      current.high - current.low,
      Math.abs(current.high - previous.close),
      Math.abs(current.low - previous.close),
    ));
  }
  if (trueRanges.length < period) return null;
  const atr = trueRanges.slice(-period).reduce((sum, value) => sum + value, 0) / period;
  const latestClose = history.at(-1)?.close;
  return Number.isFinite(latestClose) && latestClose ? (atr / latestClose) * 100 : null;
}
function calculateMaxDrawdownPct(returns) {
  if (!Array.isArray(returns) || !returns.length) return 0;
  let equity = 1;
  let peak = 1;
  let maxDrawdown = 0;
  returns.forEach((value) => {
    equity *= 1 + (value / 100);
    peak = Math.max(peak, equity);
    if (peak > 0) {
      maxDrawdown = Math.min(maxDrawdown, ((equity - peak) / peak) * 100);
    }
  });
  return maxDrawdown;
}
function calculateSharpeLikeScore(returns) {
  if (!Array.isArray(returns) || returns.length < 2) return null;
  const average = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const variance = returns.reduce((sum, value) => sum + ((value - average) ** 2), 0) / (returns.length - 1);
  const sigma = Math.sqrt(variance);
  return sigma ? average / sigma : null;
}
function calculateBacktestWinRate(returns) {
  if (!Array.isArray(returns) || !returns.length) return null;
  return returns.filter((value) => value > 0).length / returns.length;
}
function calculateBacktestAverageReturn(returns) {
  if (!Array.isArray(returns) || !returns.length) return null;
  return returns.reduce((sum, value) => sum + value, 0) / returns.length;
}
function calculateBacktestProfitFactor(returns) {
  if (!Array.isArray(returns) || !returns.length) return null;
  const profit = returns.filter((value) => value > 0).reduce((sum, value) => sum + value, 0);
  const loss = Math.abs(returns.filter((value) => value < 0).reduce((sum, value) => sum + value, 0));
  if (!loss) return profit ? Infinity : 0;
  return profit / loss;
}
function calculateMaxLosingStreak(returns) {
  if (!Array.isArray(returns) || !returns.length) return 0;
  let current = 0;
  let maxStreak = 0;
  returns.forEach((value) => {
    if (value < 0) {
      current += 1;
      maxStreak = Math.max(maxStreak, current);
    } else {
      current = 0;
    }
  });
  return maxStreak;
}
function summarizeBacktestSegment(returns) {
  return {
    samples: returns.length,
    winRate: calculateBacktestWinRate(returns),
    averageReturn: calculateBacktestAverageReturn(returns),
    profitFactor: calculateBacktestProfitFactor(returns),
    maxDrawdown: calculateMaxDrawdownPct(returns),
    maxLosingStreak: calculateMaxLosingStreak(returns),
    sharpe: calculateSharpeLikeScore(returns),
  };
}
function buildBacktestModelValidation(leader) {
  const returns = Array.isArray(leader?.returns) ? leader.returns.filter(Number.isFinite) : [];
  if (returns.length < 20) {
    return {
      status: "insufficient",
      label: "樣本不足",
      driftCount: 0,
      recommendation: "樣本不足，暫不判定模型失真，也不強制調整權重。",
      reasons: ["樣本數不足 20 筆，無法進行穩定的樣本內/樣本外驗證"],
      source: BACKTEST_DRIFT_SOURCE,
      inSample: summarizeBacktestSegment([]),
      outSample: summarizeBacktestSegment([]),
    };
  }

  const splitIndex = Math.max(10, Math.floor(returns.length * 0.7));
  const inReturns = returns.slice(0, splitIndex);
  const outReturns = returns.slice(splitIndex);
  const inSample = summarizeBacktestSegment(inReturns);
  const outSample = summarizeBacktestSegment(outReturns);
  const reasons = [];
  const inWin = inSample.winRate ?? 0;
  const outWin = outSample.winRate ?? 0;
  const inPf = Number.isFinite(inSample.profitFactor) ? inSample.profitFactor : 9;
  const outPf = Number.isFinite(outSample.profitFactor) ? outSample.profitFactor : 9;

  if (inWin >= 0.55 && outWin < 0.45) reasons.push("勝率由樣本內優勢降至樣本外 45% 以下");
  if (outSample.maxDrawdown <= -25 || outSample.maxDrawdown <= inSample.maxDrawdown - 10) reasons.push("樣本外最大回撤超過歷史容忍範圍");
  if (inPf >= 1.2 && outPf < 1) reasons.push("樣本外盈虧比惡化為小於 1");
  if (outSample.maxLosingStreak > Math.max(inSample.maxLosingStreak + 1, 3)) reasons.push("樣本外連續虧損次數異常增加");
  if (
    Number.isFinite(inSample.averageReturn)
    && Number.isFinite(outSample.averageReturn)
    && inSample.averageReturn > 0
    && outSample.averageReturn < 0
    && Math.abs(inSample.averageReturn - outSample.averageReturn) >= 6
  ) {
    reasons.push("樣本內與樣本外平均報酬差距過大，疑似過度擬合");
  }

  const driftCount = reasons.length;
  const status = driftCount >= 3 || (outWin < 0.35 && outPf < 0.8)
    ? "rebuild"
    : driftCount >= 2
      ? "recalibrate"
      : driftCount === 1
        ? "watch"
        : "healthy";
  const label = {
    healthy: "通過校準",
    watch: "輕微失真",
    recalibrate: "需調整參數",
    rebuild: "需重新建模",
  }[status] || "樣本不足";
  const recommendation = {
    healthy: "樣本外表現仍可接受，可保留目前權重校準。",
    watch: "出現一次失真，先觀察並降低模型信心。",
    recalibrate: "連續或多項失真，建議調整參數並檢查市場環境。",
    rebuild: "模型績效結構已失效，停用權重調整並重新建立模型。",
  }[status] || "樣本不足，暫不判定模型失真。";

  return {
    status,
    label,
    driftCount,
    recommendation,
    reasons: reasons.length ? reasons : ["未觸發明顯模型失真條件"],
    source: BACKTEST_DRIFT_SOURCE,
    inSample,
    outSample,
  };
}
function buildBacktestModelRebuildResult(failedModel, candidates) {
  const candidateRows = (Array.isArray(candidates) ? candidates : [])
    .filter((item) => item && item.name !== failedModel?.name && Array.isArray(item.returns) && item.returns.length >= 20)
    .map((item) => {
      const validation = buildBacktestModelValidation(item);
      const outWin = validation.outSample?.winRate ?? 0;
      const outPf = Number.isFinite(validation.outSample?.profitFactor) ? validation.outSample.profitFactor : 9;
      const outMdd = Number.isFinite(validation.outSample?.maxDrawdown) ? validation.outSample.maxDrawdown : 0;
      const score = (outWin * 100)
        + Math.min(outPf, 3) * 12
        + Math.max(outMdd, -30) * 0.7
        + Math.max(-8, Math.min(8, item.averageReturn || 0));
      return { model: item, validation, score };
    })
    .sort((left, right) => right.score - left.score);

  const replacement = candidateRows.find((item) => (
    ["healthy", "watch"].includes(item.validation.status)
    && (item.validation.outSample?.winRate ?? 0) >= 0.5
    && (!Number.isFinite(item.validation.outSample?.profitFactor) || item.validation.outSample.profitFactor >= 1)
  ));

  if (!replacement) {
    return {
      status: "failed",
      label: "重建失敗",
      oldModel: failedModel?.name || "--",
      newModel: null,
      summary: "已掃描替代模型，但尚未找到樣本外勝率、Profit Factor 與回撤都可接受的新模型，維持中性權重。",
      candidates: candidateRows.slice(0, 3).map((item) => ({
        name: item.model.name,
        status: item.validation.label,
        outWinRate: item.validation.outSample?.winRate ?? null,
        outProfitFactor: item.validation.outSample?.profitFactor ?? null,
        outMaxDrawdown: item.validation.outSample?.maxDrawdown ?? null,
      })),
    };
  }

  return {
    status: "rebuilt",
    label: "已重新建置",
    oldModel: failedModel?.name || "--",
    newModel: replacement.model.name,
    model: replacement.model,
    validation: replacement.validation,
    summary: `舊模型 ${failedModel?.name || "--"} 失真後，已改用 ${replacement.model.name}；新模型樣本外勝率 ${((replacement.validation.outSample?.winRate || 0) * 100).toFixed(0)}%，PF ${Number.isFinite(replacement.validation.outSample?.profitFactor) ? replacement.validation.outSample.profitFactor.toFixed(2) : "--"}。`,
    candidates: candidateRows.slice(0, 3).map((item) => ({
      name: item.model.name,
      status: item.validation.label,
      outWinRate: item.validation.outSample?.winRate ?? null,
      outProfitFactor: item.validation.outSample?.profitFactor ?? null,
      outMaxDrawdown: item.validation.outSample?.maxDrawdown ?? null,
    })),
  };
}
function buildBacktestTrendForecast(history, signals = [], validation = null) {
  const latest = Array.isArray(history) ? history.at(-1) : null;
  if (!latest || !Number.isFinite(latest.close)) {
    return {
      confidence: "低",
      summary: "歷史價格資料不足，暫不產生未來走勢情境推估。",
      scenarios: [],
      support: null,
      resistance: null,
      priceTargets: [],
      caveat: "回溯測試只能估計歷史訊號後的機率傾向，不保證未來價格。",
    };
  }

  const closes = history.map((item) => item.close);
  const ma20 = technicalSma(closes, 20).at(-1);
  const ma60 = technicalSma(closes, 60).at(-1);
  const ma120 = technicalSma(closes, 120).at(-1);
  const recentWindow = history.slice(-60);
  const recentLows = recentWindow.map((item) => item.low).filter(Number.isFinite);
  const recentHighs = recentWindow.map((item) => item.high).filter(Number.isFinite);
  const support = recentLows.length ? Math.min(...recentLows) : null;
  const resistance = recentHighs.length ? Math.max(...recentHighs) : null;
  const atrPct = calculateBacktestAtrPct(history, 14) || 0;
  const validSignals = (Array.isArray(signals) ? signals : []).filter((item) => item.samples >= 10);
  const bullishPower = validSignals
    .filter((item) => item.direction === "bullish")
    .reduce((sum, item) => sum + ((item.winRate - 0.5) * 100) + Math.max(-8, Math.min(8, item.averageReturn || 0)), 0);
  const bearishPower = validSignals
    .filter((item) => item.direction === "bearish")
    .reduce((sum, item) => sum + ((item.winRate - 0.5) * 100) + Math.max(-8, Math.min(8, item.averageReturn || 0)), 0);
  let trendScore = bullishPower - bearishPower;
  if ([ma20, ma60].every(Number.isFinite)) {
    if (latest.close > ma20 && ma20 > ma60) trendScore += 10;
    if (latest.close < ma20 && ma20 < ma60) trendScore -= 10;
  }
  if ([ma60, ma120].every(Number.isFinite)) {
    if (latest.close > ma60 && ma60 > ma120) trendScore += 6;
    if (latest.close < ma60 && ma60 < ma120) trendScore -= 6;
  }
  if (validation?.status === "rebuild") trendScore = 0;
  if (validation?.status === "recalibrate") trendScore *= 0.45;
  if (validation?.status === "watch") trendScore *= 0.7;

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const baseBullish = clamp(42 + trendScore * 0.55 - atrPct * 0.45, 12, 78);
  const baseBearish = clamp(30 - trendScore * 0.42 + atrPct * 0.45, 10, 70);
  const normalizeScenario = (bullish, bearish) => {
    const neutral = clamp(100 - bullish - bearish, 12, 55);
    const total = bullish + bearish + neutral || 1;
    return {
      bullish: Math.round((bullish / total) * 100),
      neutral: Math.round((neutral / total) * 100),
      bearish: Math.max(0, 100 - Math.round((bullish / total) * 100) - Math.round((neutral / total) * 100)),
    };
  };
  const horizons = [
    { days: 5, label: "5 日", factor: 0.42 },
    { days: 10, label: "10 日", factor: 0.56 },
    { days: 20, label: "20 日", factor: 0.72 },
    { days: 60, label: "60 日", factor: 0.9 },
    { days: 120, label: "120 日", factor: 1.05 },
    { days: 240, label: "240 日", factor: 1.18 },
  ];
  const scenarios = horizons.map((item) => ({
    ...item,
    ...normalizeScenario(
      clamp(baseBullish + (trendScore > 0 ? item.factor * 3 : -item.factor * 1.2), 10, 82),
      clamp(baseBearish + (trendScore < 0 ? item.factor * 3 : -item.factor * 1.2), 8, 78),
    ),
  }));
  const atrPrice = latest.close * (atrPct / 100);
  const confidenceMultiplier = validation?.status === "healthy"
    ? 1
    : validation?.status === "watch"
      ? 0.82
      : validation?.status === "recalibrate"
        ? 0.62
        : validation?.status === "rebuild"
          ? 0.35
          : 0.55;
  const priceTargets = horizons.map((item) => {
    const scenario = scenarios.find((entry) => entry.days === item.days) || {};
    const directionalBias = ((scenario.bullish || 0) - (scenario.bearish || 0)) / 100;
    const signalReturn = validSignals.length
      ? validSignals.reduce((sum, signal) => {
          const direction = signal.direction === "bullish" ? 1 : signal.direction === "bearish" ? -1 : 0;
          return sum + (direction * (Number(signal.averageReturn) || 0));
        }, 0) / validSignals.length
      : 0;
    const trendReturn = clamp((directionalBias * atrPct * Math.sqrt(item.days / 20) * 1.8) + (signalReturn * (item.days / 240)), -35, 35) * confidenceMultiplier;
    const median = latest.close * (1 + trendReturn / 100);
    const volatilityBand = Math.max(atrPrice * Math.sqrt(item.days / 20), latest.close * 0.015) * (validation?.status === "rebuild" ? 1.35 : 1);
    const lowerAnchor = Number.isFinite(support) ? support : latest.close - volatilityBand;
    const upperAnchor = Number.isFinite(resistance) ? resistance : latest.close + volatilityBand;
    const lower = Math.max(0, Math.min(median - volatilityBand, lowerAnchor * 0.98));
    const upper = Math.max(median + volatilityBand, upperAnchor * 1.02);
    return {
      days: item.days,
      label: item.label,
      median,
      lower,
      upper,
      expectedReturnPct: ((median - latest.close) / latest.close) * 100,
      basis: validation?.status === "rebuild"
        ? "模型失真，僅保留寬區間風險參考"
        : "依情境機率、ATR、支撐壓力與回測平均報酬估算",
    };
  });
  const leader = validSignals[0];
  const confidence = validation?.status === "healthy" && validSignals.length >= 3
    ? "中高"
    : validation?.status === "rebuild" || !validSignals.length
      ? "低"
      : "中";
  const summary = leader
    ? `依 ${leader.name} 與多因子回測，未來走勢偏向${trendScore > 8 ? "多方延續" : trendScore < -8 ? "偏空修正" : "區間震盪"}；模型信心 ${confidence}。`
    : `目前可用回測訊號不足，未來走勢以區間震盪情境為主；模型信心 ${confidence}。`;
  return {
    confidence,
    summary,
    scenarios,
    support,
    resistance,
    atrPct,
    trendScore,
    priceTargets,
    trendLabel: trendScore > 8 ? "偏多延續" : trendScore < -8 ? "偏空修正" : "區間震盪",
    caveat: "這是基於歷史訊號與目前價量結構的機率情境與價格區間推估，不是保證價格或投資建議。",
  };
}
function buildBacktestLearningModel(history, horizon = 240) {
  const costModel = {
    feePct: 0.1425,
    sellTaxPct: 0.3,
    slippagePct: 0.1,
    roundTripPct: 0.1425 * 2 + 0.3 + 0.1 * 2,
  };
  const riskModel = {
    stopLossPct: -8,
    takeProfitPct: 20,
    maxSinglePositionPct: 20,
  };
  if (!Array.isArray(history) || history.length < horizon + 90) {
    return {
      scoreAdjustment: 0,
      evidenceCount: 0,
      horizon,
      successThreshold: 5,
      testedBars: 0,
      summary: `歷史資料不足 ${horizon} 日後報酬回測，暫不啟用回溯校準`,
      signals: [],
      factors: BACKTEST_FACTOR_BASELINE,
      benchmarkSource: BACKTEST_BENCHMARK_SOURCE,
      driftSource: BACKTEST_DRIFT_SOURCE,
      costModel,
      riskModel,
      qualityChecks: ["OHLCV 歷史資料不足，暫不啟用完整基準"],
      performance: null,
      validation: buildBacktestModelValidation(null),
      forecast: buildBacktestTrendForecast(history, [], null),
    };
  }

  const stats = new Map();
  const allNetReturns = [];
  const addResult = (name, direction, futureReturnPct, context = {}) => {
    if (!direction || direction === "neutral" || !Number.isFinite(futureReturnPct)) return;
    const directionalReturn = direction === "bullish" ? futureReturnPct : -futureReturnPct;
    const netReturnPct = directionalReturn - costModel.roundTripPct;
    if (!stats.has(name)) {
      stats.set(name, {
        name,
        direction,
        samples: 0,
        wins: 0,
        totalReturn: 0,
        grossTotalReturn: 0,
        totalProfit: 0,
        totalLoss: 0,
        returns: [],
        riskHits: 0,
      });
    }
    const item = stats.get(name);
    item.samples += 1;
    item.totalReturn += netReturnPct;
    item.grossTotalReturn += directionalReturn;
    item.returns.push(netReturnPct);
    allNetReturns.push(netReturnPct);
    if (netReturnPct > 0) item.totalProfit += netReturnPct;
    if (netReturnPct < 0) item.totalLoss += Math.abs(netReturnPct);
    if (context.riskTriggered) item.riskHits += 1;
    if (netReturnPct > 5) {
      item.wins += 1;
    }
  };

  for (let index = 60; index < history.length - horizon; index += 1) {
    const window = history.slice(0, index + 1);
    const latest = window.at(-1);
    const previous = window.at(-2);
    const future = history[index + horizon];
    if (!latest || !previous || !future || !latest.close) continue;
    const futureReturnPct = ((future.close - latest.close) / latest.close) * 100;
    const futureWindow = history.slice(index + 1, index + horizon + 1);
    const maxFutureGainPct = futureWindow.length
      ? ((Math.max(...futureWindow.map((item) => item.high).filter(Number.isFinite)) - latest.close) / latest.close) * 100
      : futureReturnPct;
    const maxFutureLossPct = futureWindow.length
      ? ((Math.min(...futureWindow.map((item) => item.low).filter(Number.isFinite)) - latest.close) / latest.close) * 100
      : futureReturnPct;
    const bullishRiskTriggered = maxFutureLossPct <= riskModel.stopLossPct || maxFutureGainPct >= riskModel.takeProfitPct;
    const bearishRiskTriggered = maxFutureGainPct >= Math.abs(riskModel.stopLossPct) || maxFutureLossPct <= -riskModel.takeProfitPct;
    const closes = window.map((item) => item.close);
    const ma5 = technicalSma(closes, 5).at(-1);
    const ma10 = technicalSma(closes, 10).at(-1);
    const ma20 = technicalSma(closes, 20).at(-1);
    const ma60 = technicalSma(closes, 60).at(-1);

    if ([ma20, ma60].every(Number.isFinite)) {
      if (latest.close > ma20 && ma20 > ma60) addResult("均線多頭排列", "bullish", futureReturnPct);
      if (latest.close < ma20 && ma20 < ma60) addResult("均線空頭排列", "bearish", futureReturnPct);
    }
    if ([ma5, ma10, ma20].every(Number.isFinite)) {
      if (latest.close > ma5 && ma5 > ma10 && ma10 > ma20) addResult("重建候選：短均多頭排列", "bullish", futureReturnPct);
      if (latest.close < ma5 && ma5 < ma10 && ma10 < ma20) addResult("重建候選：短均空頭排列", "bearish", futureReturnPct);
      if (previous.close <= ma10 && latest.close > ma10 && ma10 > ma20) addResult("重建候選：10 日線轉強", "bullish", futureReturnPct);
      if (previous.close >= ma10 && latest.close < ma10 && ma10 < ma20) addResult("重建候選：10 日線轉弱", "bearish", futureReturnPct);
    }

    const rsi = calculateRsi(window).at(-1);
    const kd = window.length >= 9 ? calculateKd(window).at(-1) : null;
    if (Number.isFinite(rsi)) {
      if (rsi >= 55 && rsi < 75) addResult("RSI 多方區", "bullish", futureReturnPct);
      if (rsi >= 50 && rsi < 68) addResult("重建候選：RSI 50 多方守穩", "bullish", futureReturnPct);
      if (rsi < 45) addResult("重建候選：RSI 45 空方跌破", "bearish", futureReturnPct);
    }

    const macd = window.length >= 26 ? calculateMacd(window).at(-1) : null;
    if (macd && Number.isFinite(macd.osc)) {
      if (macd.osc > 0) addResult("MACD 正柱", "bullish", futureReturnPct);
      if (macd.osc < 0) addResult("MACD 負柱", "bearish", futureReturnPct);
    }

    const recentVolumes = window.slice(-6, -1).map((item) => item.volume).filter(Number.isFinite);
    const averageVolume = recentVolumes.length
      ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
      : null;
    const volumeRatio = averageVolume && latest.volume ? latest.volume / averageVolume : null;

    const band = window.length >= 20 ? calculateBollingerBands(window).at(-1) : null;
    if (band && [band.upper, band.lower].every(Number.isFinite)) {
      if (latest.close > band.upper) addResult("布林上軌突破", "bullish", futureReturnPct);
      if (latest.close < band.lower) addResult("布林下軌跌破", "bearish", futureReturnPct);
    }

    const ma120 = technicalSma(closes, 120).at(-1);
    const ma240 = technicalSma(closes, 240).at(-1);
    const momentum60 = closes.length >= 61 && closes.at(-61)
      ? ((latest.close - closes.at(-61)) / closes.at(-61)) * 100
      : null;
    const atrPct = calculateBacktestAtrPct(window, 14);
    const prior20 = window.slice(-21, -1);
    const priorHigh = prior20.length ? Math.max(...prior20.map((item) => item.high)) : null;
    const priorLow = prior20.length ? Math.min(...prior20.map((item) => item.low)) : null;
    const recent60 = window.slice(-60);
    const volatilityPct = recent60.length >= 20
      ? ((Math.max(...recent60.map((item) => item.high)) - Math.min(...recent60.map((item) => item.low))) / latest.close) * 100
      : null;

    if ([ma20, ma60, ma120].every(Number.isFinite)) {
      if (latest.close > ma20 && ma20 > ma60 && ma60 > ma120 && macd?.osc > 0) {
        addResult("趨勢動能共振", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
      }
      if (latest.close < ma20 && ma20 < ma60 && ma60 < ma120 && macd?.osc < 0) {
        addResult("趨勢動能轉弱", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
      }
    }
    if ([ma60, ma120, ma240].every(Number.isFinite)) {
      if (latest.close > ma60 && ma60 > ma120 && ma120 > ma240) {
        addResult("長週期多頭結構", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
      }
      if (latest.close < ma60 && ma60 < ma120 && ma120 < ma240) {
        addResult("長週期空頭結構", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
      }
    }
    if (priorHigh && volumeRatio && latest.close > priorHigh && volumeRatio >= 1.1) {
      addResult("放量突破 20 日高", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
    }
    if (priorLow && volumeRatio && latest.close < priorLow && volumeRatio >= 1.1) {
      addResult("放量跌破 20 日低", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
    }
    if (band && [band.upper, band.middle, ma20, ma60].every(Number.isFinite) && latest.close > band.middle && ma20 > ma60 && volumeRatio && volumeRatio >= 0.9) {
      addResult("布林中軌上方趨勢延續", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
    }
    if ([ma60, rsi, macd?.osc, kd?.k, kd?.d, momentum60].every(Number.isFinite)) {
      if (latest.close > ma60 && rsi >= 50 && macd.osc > 0 && kd.k >= kd.d && momentum60 > 0) {
        addResult("趨勢動能多因子", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
      }
      if (latest.close < ma60 && rsi < 50 && macd.osc < 0 && kd.k < kd.d && momentum60 < 0) {
        addResult("趨勢動能空因子", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
      }
    }
    if ([ma60, atrPct, band?.bandwidth].every(Number.isFinite)) {
      if (latest.close > ma60 && atrPct < 4.5 && band.bandwidth < 18) {
        addResult("低波動趨勢基準", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
      }
      if (latest.close < ma60 && atrPct >= 4.5 && band.bandwidth >= 18) {
        addResult("高波動風險基準", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
      }
    }
    if (Number.isFinite(volatilityPct)) {
      if (volatilityPct <= 18 && Number.isFinite(ma60) && latest.close > ma60 && macd?.osc > 0) {
        addResult("低波動趨勢延續", "bullish", futureReturnPct);
      }
      if (volatilityPct >= 35 && Number.isFinite(ma60) && latest.close < ma60 && macd?.osc < 0) {
        addResult("高波動弱勢延伸", "bearish", futureReturnPct);
      }
    }
    if ([ma10, ma20, volumeRatio, rsi].every(Number.isFinite)) {
      if (latest.close > ma10 && ma10 >= ma20 && volumeRatio >= 0.9 && rsi >= 48) {
        addResult("重建候選：短線趨勢量能確認", "bullish", futureReturnPct);
      }
      if (latest.close < ma10 && ma10 <= ma20 && volumeRatio >= 0.9 && rsi < 50) {
        addResult("重建候選：短線弱勢量能確認", "bearish", futureReturnPct);
      }
    }
  }

  const rankedAll = [...stats.values()]
    .filter((item) => item.samples >= 10)
    .map((item) => ({
      ...item,
      winRate: item.wins / item.samples,
      averageReturn: item.totalReturn / item.samples,
      grossAverageReturn: item.grossTotalReturn / item.samples,
      profitFactor: item.totalLoss ? item.totalProfit / item.totalLoss : (item.totalProfit ? Infinity : 0),
      maxDrawdown: calculateMaxDrawdownPct(item.returns),
      sharpe: calculateSharpeLikeScore(item.returns),
      riskHitRate: item.riskHits / item.samples,
    }))
    .sort((a, b) => {
      const scoreA = Math.abs(a.winRate - 0.5) + Math.max(-0.3, Math.min(0.3, (a.profitFactor || 0) / 10));
      const scoreB = Math.abs(b.winRate - 0.5) + Math.max(-0.3, Math.min(0.3, (b.profitFactor || 0) / 10));
      return scoreB - scoreA;
    });
  const ranked = rankedAll.slice(0, 5);

  if (!ranked.length) {
    return {
      scoreAdjustment: 0,
      evidenceCount: 0,
      horizon,
      successThreshold: 5,
      testedBars: Math.max(history.length - horizon - 60, 0),
      summary: `${horizon} 日後報酬回溯樣本不足，暫不調整 AI 權重`,
      signals: [],
      factors: BACKTEST_FACTOR_BASELINE,
      benchmarkSource: BACKTEST_BENCHMARK_SOURCE,
      driftSource: BACKTEST_DRIFT_SOURCE,
      costModel,
      riskModel,
      qualityChecks: ["OHLCV 已檢查", "有效訊號樣本不足", "避免樣本不足時硬調權重"],
      performance: {
        maxDrawdown: calculateMaxDrawdownPct(allNetReturns),
        sharpe: calculateSharpeLikeScore(allNetReturns),
      },
      validation: buildBacktestModelValidation(null),
      forecast: buildBacktestTrendForecast(history, [], null),
    };
  }

  const scoreAdjustment = ranked.reduce((sum, item) => {
    if (item.winRate >= 0.58) return sum + (item.direction === "bullish" ? 1 : -1);
    if (item.winRate <= 0.42) return sum - (item.direction === "bullish" ? 1 : -1);
    return sum;
  }, 0);
  const leader = ranked[0];
  const validation = buildBacktestModelValidation(leader);
  const modelRebuild = ["rebuild", "recalibrate"].includes(validation.status)
    ? buildBacktestModelRebuildResult(leader, rankedAll)
    : { status: "not_required", label: "不需重建", oldModel: leader.name, newModel: null, summary: "目前模型尚未達重建條件。" };
  const activeLeader = modelRebuild.status === "rebuilt" ? modelRebuild.model : leader;
  const activeValidation = modelRebuild.status === "rebuilt" ? modelRebuild.validation : validation;
  const activeRanked = modelRebuild.status === "rebuilt"
    ? [modelRebuild.model, ...ranked.filter((item) => item.name !== leader.name && item.name !== modelRebuild.model.name)].slice(0, 5)
    : ranked;
  const activeScoreAdjustment = activeRanked.reduce((sum, item) => {
    if (item.winRate >= 0.58) return sum + (item.direction === "bullish" ? 1 : -1);
    if (item.winRate <= 0.42) return sum - (item.direction === "bullish" ? 1 : -1);
    return sum;
  }, 0);
  const rawAdjustment = Math.max(-3, Math.min(3, scoreAdjustment));
  const activeRawAdjustment = Math.max(-3, Math.min(3, activeScoreAdjustment));
  const clippedAdjustment = modelRebuild.status === "rebuilt"
    ? activeRawAdjustment
    : activeValidation.status === "rebuild"
    ? 0
    : activeValidation.status === "recalibrate"
      ? Math.max(-1, Math.min(1, rawAdjustment))
      : activeValidation.status === "watch"
        ? Math.trunc(rawAdjustment / 2)
        : rawAdjustment;
  const summary = modelRebuild.status === "rebuilt"
    ? `模型已重新建置：${leader.name} 失真後改用 ${activeLeader.name}，樣本外通過校準`
    : activeValidation.status === "rebuild"
      ? `回測偵測模型失真，${leader.name} 暫停權重調整；替代模型尚未通過校準`
      : `回測 ${horizon} 日後淨報酬，${activeLeader.name} 勝率 ${(activeLeader.winRate * 100).toFixed(0)}%，淨均報酬 ${activeLeader.averageReturn >= 0 ? "+" : ""}${activeLeader.averageReturn.toFixed(2)}%`;

  return {
    scoreAdjustment: clippedAdjustment,
    evidenceCount: ranked.reduce((sum, item) => sum + item.samples, 0),
    horizon,
    successThreshold: 5,
    testedBars: Math.max(history.length - horizon - 60, 0),
    summary,
    signals: activeRanked,
    factors: BACKTEST_FACTOR_BASELINE,
    benchmarkSource: BACKTEST_BENCHMARK_SOURCE,
    driftSource: BACKTEST_DRIFT_SOURCE,
    costModel,
    riskModel,
    qualityChecks: ["OHLCV 已檢查", "以當下可得資料計算", "納入交易成本", "納入停損停利風控觀察"],
    performance: {
      maxDrawdown: calculateMaxDrawdownPct(allNetReturns),
      sharpe: calculateSharpeLikeScore(allNetReturns),
      profitFactor: activeRanked.reduce((sum, item) => sum + (Number.isFinite(item.profitFactor) ? item.profitFactor : 0), 0) / activeRanked.length,
    },
    validation: activeValidation,
    originalValidation: validation,
    modelRebuild,
    forecast: buildBacktestTrendForecast(history, activeRanked, activeValidation),
  };
}
function buildInstitutionalBacktestFramework(detail, history, backtestLearning) {
  const clampScore = (value) => Math.max(0, Math.min(100, value));
  const scoreFromPct = (value, sensitivity = 7) => (
    Number.isFinite(value) ? clampScore(50 + (value * sensitivity)) : null
  );
  const averageAvailable = (items, fallback = 50) => {
    const available = items.filter((item) => Number.isFinite(item.score));
    if (!available.length) return { score: fallback, coverage: 0, available: [] };
    const totalWeight = available.reduce((sum, item) => sum + (item.weight || 1), 0);
    return {
      score: available.reduce((sum, item) => sum + (item.score * (item.weight || 1)), 0) / totalWeight,
      coverage: available.length / items.length,
      available,
    };
  };
  const international = Array.isArray(data?.marketInternationalIndexes)
    ? data.marketInternationalIndexes
    : [];
  const macroFactors = data?.marketMacroFactors || {};
  const findIndex = (...needles) => international.find((item) => {
    const haystack = `${item.key || ""} ${item.symbol || ""} ${item.name || ""}`.toLowerCase();
    return needles.some((needle) => haystack.includes(needle));
  });
  const readPct = (item) => parseAnalysisNumber(
    item?.pct ?? item?.changePercent ?? item?.changePct ?? item?.change_rate,
  );
  const soxPct = readPct(findIndex("sox", "semiconductor", "費城半導體"));
  const nasdaqPct = readPct(findIndex("nasdaq", "ixic"));
  const sp500Pct = readPct(findIndex("sp500", "s&p 500", "gspc"));
  const russellPct = readPct(findIndex("russell", "rut"));
  const vixItem = findIndex("vix", "volatility");
  const vixPct = readPct(vixItem) ?? parseAnalysisNumber(data?.marketVolatility?.pct);
  const vixValue = parseAnalysisNumber(vixItem?.value ?? vixItem?.close ?? data?.marketVolatility?.value);
  const dxyPct = parseAnalysisNumber(macroFactors.dxy?.pct);
  const us10yPct = parseAnalysisNumber(macroFactors.us10y?.pct);
  const usdTwdPct = parseAnalysisNumber(macroFactors.usdTwd?.pct);
  const vixLevelScore = Number.isFinite(vixValue)
    ? vixValue < 15 ? 72 : vixValue < 20 ? 62 : vixValue < 30 ? 42 : vixValue < 40 ? 24 : 8
    : null;
  const marketFactors = [
    { name: "SOX 半導體", score: scoreFromPct(soxPct, 9), weight: 3, value: soxPct },
    { name: "NASDAQ", score: scoreFromPct(nasdaqPct, 8), weight: 3, value: nasdaqPct },
    {
      name: "VIX 風險",
      score: Number.isFinite(vixLevelScore)
        ? clampScore((vixLevelScore * 0.7) + ((scoreFromPct(Number.isFinite(vixPct) ? -vixPct : null, 5) ?? 50) * 0.3))
        : scoreFromPct(Number.isFinite(vixPct) ? -vixPct : null, 5),
      weight: 3,
      value: vixValue,
    },
    { name: "S&P 500", score: scoreFromPct(sp500Pct, 7), weight: 1, value: sp500Pct },
    { name: "Russell 2000", score: scoreFromPct(russellPct, 7), weight: 1, value: russellPct },
    { name: "美元指數", score: scoreFromPct(Number.isFinite(dxyPct) ? -dxyPct : null, 6), weight: 1, value: dxyPct },
    { name: "美債 10 年殖利率", score: scoreFromPct(Number.isFinite(us10yPct) ? -us10yPct : null, 5), weight: 1, value: us10yPct },
    { name: "美元兌臺幣", score: scoreFromPct(Number.isFinite(usdTwdPct) ? -usdTwdPct : null, 6), weight: 1, value: usdTwdPct },
  ];
  const marketLayer = averageAvailable(marketFactors);

  const institutional = parseAnalysisNumber(detail.institutionalTrades?.totalValue);
  const foreign = parseAnalysisNumber(
    detail.institutionalTrades?.foreignValue
      ?? detail.institutionalTrades?.foreign
      ?? detail.institutionalTrades?.foreignInvestors,
  );
  const largeHolder = parseAnalysisNumber(detail.shareholderDistribution?.largeHolderRatio);
  const latest = history.at(-1);
  const recentVolumes = history.slice(-21, -1).map((item) => item.volume).filter(Number.isFinite);
  const average20Volume = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const volumeRatio = Number.isFinite(latest?.volume) && average20Volume
    ? latest.volume / average20Volume
    : null;
  const futuresOiChangePct = parseAnalysisNumber(macroFactors.txOpenInterest?.changePct);
  const weightedPct = parseAnalysisNumber(
    (data?.marketOverview || []).find((item) => /加權|TAIEX/i.test(item?.name || ""))?.pct,
  );
  const futuresOiScore = Number.isFinite(futuresOiChangePct)
    ? futuresOiChangePct > 0
      ? Number.isFinite(weightedPct) && weightedPct < 0 ? 32 : 68
      : Number.isFinite(weightedPct) && weightedPct < 0 ? 58 : 45
    : null;
  const financingChangePct = parseAnalysisNumber(macroFactors.marginTrading?.financingChangePct);
  const shortChangePct = parseAnalysisNumber(macroFactors.marginTrading?.shortChangePct);
  const marginScore = Number.isFinite(financingChangePct)
    ? financingChangePct > 3
      ? 32
      : financingChangePct >= 0
        ? 58
        : financingChangePct <= -3
          ? 52
          : 48
    : null;
  const shortScore = Number.isFinite(shortChangePct)
    ? shortChangePct > 3 ? 38 : shortChangePct < -3 ? 60 : 50
    : null;
  const capitalFactors = [
    {
      name: "外資買賣超",
      score: Number.isFinite(foreign) ? (foreign > 0 ? 70 : foreign < 0 ? 30 : 50) : null,
      weight: 2,
      value: foreign,
    },
    {
      name: "三大法人",
      score: Number.isFinite(institutional) ? (institutional > 0 ? 68 : institutional < 0 ? 32 : 50) : null,
      weight: 2,
      value: institutional,
    },
    {
      name: "大戶持股",
      score: Number.isFinite(largeHolder) ? clampScore(30 + (largeHolder * 0.7)) : null,
      weight: 1.5,
      value: largeHolder,
    },
    {
      name: "量能流入",
      score: Number.isFinite(volumeRatio) ? clampScore(50 + ((volumeRatio - 1) * 35)) : null,
      weight: 1,
      value: volumeRatio,
    },
    {
      name: "臺指期未平倉",
      score: futuresOiScore,
      weight: 1.5,
      value: futuresOiChangePct,
    },
    {
      name: "融資餘額",
      score: marginScore,
      weight: 1,
      value: financingChangePct,
    },
    {
      name: "融券餘額",
      score: shortScore,
      weight: 0.5,
      value: shortChangePct,
    },
  ];
  const capitalLayer = averageAvailable(capitalFactors);

  const closes = history.map((item) => item.close);
  const ma20 = technicalSma(closes, 20).at(-1);
  const ma60 = technicalSma(closes, 60).at(-1);
  const ma120 = technicalSma(closes, 120).at(-1);
  const ma240 = technicalSma(closes, 240).at(-1);
  const returnFor = (period) => (
    history.length > period && Number.isFinite(history.at(-(period + 1))?.close)
      ? ((latest.close - history.at(-(period + 1)).close) / history.at(-(period + 1)).close) * 100
      : null
  );
  const dayTrend = returnFor(20);
  const weekTrend = returnFor(60);
  const monthTrend = returnFor(240) ?? returnFor(120);
  const maAlignmentScore = [latest?.close, ma20, ma60].every(Number.isFinite)
    ? latest.close > ma20 && ma20 > ma60
      ? 75
      : latest.close < ma20 && ma20 < ma60
        ? 25
        : 50
    : null;
  const longAlignmentScore = [latest?.close, ma60, ma120, ma240].every(Number.isFinite)
    ? latest.close > ma60 && ma60 > ma120 && ma120 > ma240
      ? 82
      : latest.close < ma60 && ma60 < ma120 && ma120 < ma240
        ? 18
        : 50
    : null;
  const recent60 = history.slice(-60);
  const support = recent60.length ? Math.min(...recent60.map((item) => item.low).filter(Number.isFinite)) : null;
  const resistance = recent60.length ? Math.max(...recent60.map((item) => item.high).filter(Number.isFinite)) : null;
  const rangePosition = [support, resistance, latest?.close].every(Number.isFinite) && resistance > support
    ? ((latest.close - support) / (resistance - support)) * 100
    : null;
  const trendFactors = [
    { name: "月線結構", score: scoreFromPct(monthTrend, 2.2), weight: 3, value: monthTrend },
    { name: "週線趨勢", score: scoreFromPct(weekTrend, 3.5), weight: 2, value: weekTrend },
    { name: "日線動能", score: scoreFromPct(dayTrend, 5), weight: 1, value: dayTrend },
    { name: "均線排列", score: maAlignmentScore, weight: 2, value: ma20 },
    { name: "長週期結構", score: longAlignmentScore, weight: 2, value: ma240 },
    {
      name: "支撐壓力",
      score: Number.isFinite(rangePosition) ? clampScore(35 + (rangePosition * 0.3)) : null,
      weight: 1,
      value: rangePosition,
    },
  ];
  const trendLayer = averageAvailable(trendFactors);

  const macd = calculateMacd(history).at(-1);
  const rsi = calculateRsi(history).at(-1);
  const dmi = calculateDmi(history).at(-1);
  const kd = calculateKd(history).at(-1);
  const candleScore = latest && history.at(-2)
    ? latest.close > latest.open && latest.close >= history.at(-2).close ? 70
      : latest.close < latest.open && latest.close <= history.at(-2).close ? 30
        : 50
    : null;
  const timingFactors = [
    {
      name: "MACD",
      score: Number.isFinite(macd?.osc) ? clampScore(50 + (Math.sign(macd.osc) * Math.min(30, Math.abs(macd.osc) * 5))) : null,
      weight: 40,
      value: macd?.osc,
    },
    {
      name: "RSI",
      score: Number.isFinite(rsi) ? clampScore(rsi >= 50 ? 50 + Math.min(25, (rsi - 50) * 1.3) : 50 - Math.min(25, (50 - rsi) * 1.3)) : null,
      weight: 25,
      value: rsi,
    },
    {
      name: "DMI",
      score: [dmi?.plusDi, dmi?.minusDi].every(Number.isFinite)
        ? clampScore(50 + ((dmi.plusDi - dmi.minusDi) * 1.3))
        : null,
      weight: 20,
      value: dmi?.adx,
    },
    { name: "K 線", score: candleScore, weight: 10, value: latest?.close },
    {
      name: "KD",
      score: [kd?.k, kd?.d].every(Number.isFinite) ? clampScore(50 + ((kd.k - kd.d) * 1.8)) : null,
      weight: 5,
      value: kd?.k,
    },
  ];
  const timingLayerRaw = averageAvailable(timingFactors);
  const priceDirection = timingLayerRaw.score >= 55 ? 1 : timingLayerRaw.score <= 45 ? -1 : 0;
  const volumeDirection = Number.isFinite(volumeRatio) ? (volumeRatio >= 1.1 ? 1 : volumeRatio <= 0.8 ? -1 : 0) : 0;
  const volumePenalty = priceDirection && volumeDirection && priceDirection !== volumeDirection ? 8 : 0;
  const timingLayer = {
    ...timingLayerRaw,
    score: clampScore(timingLayerRaw.score - volumePenalty),
    volumePenalty,
  };

  const layers = [
    { key: "market", label: "市場環境", weight: 45, ...marketLayer },
    { key: "capital", label: "資金面", weight: 25, ...capitalLayer },
    { key: "trend", label: "趨勢面", weight: 20, ...trendLayer },
    { key: "timing", label: "進出場", weight: 10, ...timingLayer },
  ];
  const totalScore = Math.round(layers.reduce((sum, layer) => sum + (layer.score * layer.weight / 100), 0));
  const judgement = totalScore >= 80
    ? { label: "積極偏多", tone: "bullish", action: "市場、資金與趨勢共振，仍以分批進場及停損紀律執行。" }
    : totalScore >= 60
      ? { label: "偏多", tone: "bullish", action: "可偏多觀察，等待量價與進場訊號同步後分批布局。" }
      : totalScore >= 40
        ? { label: "觀望", tone: "neutral", action: "多空因子未形成明確共振，控制部位並等待方向確認。" }
        : totalScore >= 20
          ? { label: "偏空", tone: "bearish", action: "降低部位，優先確認支撐、法人方向與波動風險。" }
          : { label: "積極防守", tone: "bearish", action: "風險因子集中，避免逆勢加碼並提高現金水位。" };

  const leader = backtestLearning?.signals?.[0];
  const recent20Returns = Array.isArray(leader?.returns) ? leader.returns.slice(-20) : [];
  const recent20 = summarizeBacktestSegment(recent20Returns);
  const recentWinPct = Number.isFinite(recent20.winRate) ? recent20.winRate * 100 : null;
  const recentWinState = Number.isFinite(recentWinPct)
    ? recentWinPct > 60 ? "模型正常" : recentWinPct >= 50 ? "持續觀察" : recentWinPct >= 40 ? "降低部位" : "模型失真警報"
    : "樣本不足";
  const pfState = Number.isFinite(recent20.profitFactor)
    ? recent20.profitFactor > 1.5 ? "正常" : recent20.profitFactor >= 1 ? "觀察" : "模型失真"
    : "樣本不足";
  const mddState = Number.isFinite(recent20.maxDrawdown) && recent20.maxDrawdown <= -15
    ? "啟動風控警報"
    : "風險可控";
  const aiIndustryMatch = /半導體|電子|AI|資訊|電腦/i.test(`${detail.industry || ""} ${detail.category || ""} ${detail.name || ""}`);
  const driftChecks = [
    { label: "SOX 週期", status: Number.isFinite(soxPct) ? (soxPct >= 0 ? "穩定" : "轉弱") : "待資料" },
    { label: "NASDAQ 轉折", status: Number.isFinite(nasdaqPct) ? (nasdaqPct >= 0 ? "偏多" : "偏空") : "待資料" },
    { label: "VIX 異常", status: Number.isFinite(vixValue) ? (vixValue >= 30 ? "警戒" : "正常") : "待資料" },
    { label: "外資反向", status: Number.isFinite(foreign) ? (foreign < 0 ? "流出" : "流入") : "待資料" },
    { label: "AI 產業氣候", status: aiIndustryMatch ? (Number.isFinite(soxPct) && soxPct < 0 ? "轉弱" : "追蹤中") : "非核心產業" },
  ];
  const marketState = marketLayer.score >= 60 && (!Number.isFinite(vixValue) || vixValue < 20)
    ? "Risk-On"
    : marketLayer.score < 40 || (Number.isFinite(vixValue) && vixValue >= 30)
      ? "Risk-Off"
      : "Neutral";

  return {
    layers,
    totalScore,
    judgement,
    marketState,
    coverage: Math.round((layers.reduce((sum, layer) => sum + layer.coverage, 0) / layers.length) * 100),
    recent20: {
      ...recent20,
      winState: recentWinState,
      pfState,
      mddState,
    },
    driftChecks,
    outputSteps: [
      `市場環境：${marketState}，評分 ${Math.round(marketLayer.score)}`,
      `資金面：${capitalLayer.score >= 60 ? "偏流入" : capitalLayer.score < 40 ? "偏流出" : "中性"}，評分 ${Math.round(capitalLayer.score)}`,
      `趨勢面：${trendLayer.score >= 60 ? "多方" : trendLayer.score < 40 ? "空方" : "整理"}，評分 ${Math.round(trendLayer.score)}`,
      `進出場：${timingLayer.score >= 60 ? "偏多訊號" : timingLayer.score < 40 ? "偏空訊號" : "等待確認"}，評分 ${Math.round(timingLayer.score)}`,
      `AI 產業週期：${aiIndustryMatch ? "已納入 SOX 與 NASDAQ 氣候" : "非 AI 核心產業，維持一般市場權重"}`,
      `模型失真檢查：${backtestLearning?.validation?.label || "樣本不足"}；近 20 筆 ${recentWinState}`,
      `綜合評分：${totalScore} / 100，${judgement.label}`,
      `操作建議：${judgement.action}`,
    ],
  };
}
function buildFuturesBacktestFramework(detail, history, backtestLearning) {
  const clampScore = (value) => Math.max(0, Math.min(100, Number(value) || 0));
  const snapshot = buildFuturesTechnicalSnapshot(history);
  const latest = history.at(-1) || {};
  const previous = history.at(-2) || {};
  const priorClose = history.length > 20 ? history.at(-21)?.close : history[0]?.close;
  const periodChangePct = Number.isFinite(latest.close) && Number.isFinite(priorClose) && priorClose !== 0
    ? ((latest.close - priorClose) / priorClose) * 100
    : null;
  const latestChange = Number.isFinite(latest.close) && Number.isFinite(previous.close)
    ? latest.close - previous.close
    : null;
  const recentVolumes = history.slice(-21, -1).map((row) => row.volume).filter((value) => Number.isFinite(value) && value > 0);
  const averageVolume = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const volumeRatio = Number.isFinite(latest.volume) && averageVolume ? latest.volume / averageVolume : null;
  const makeLayer = (key, label, weight, factors) => {
    const available = factors.filter((factor) => Number.isFinite(factor.score));
    return {
      key,
      label,
      weight,
      score: available.length ? available.reduce((sum, factor) => sum + factor.score, 0) / available.length : 50,
      coverage: available.length / Math.max(factors.length, 1),
      available,
    };
  };
  const trendLayer = makeLayer("trend", "契約趨勢", 40, [
    { name: "近 20 根報酬", score: Number.isFinite(periodChangePct) ? clampScore(50 + periodChangePct * 4) : null, value: periodChangePct },
    { name: "價格／20 期均線", score: [latest.close, snapshot.ma?.[20]].every(Number.isFinite) ? (latest.close >= snapshot.ma[20] ? 65 : 35) : null, value: snapshot.ma?.[20] },
    { name: "5／20 期均線", score: [snapshot.ma?.[5], snapshot.ma?.[20]].every(Number.isFinite) ? (snapshot.ma[5] >= snapshot.ma[20] ? 65 : 35) : null, value: snapshot.ma?.[5] },
    { name: "MACD 趨勢", score: [snapshot.macd, snapshot.macdSignal].every(Number.isFinite) ? (snapshot.macd >= snapshot.macdSignal ? 64 : 36) : null, value: snapshot.macd },
  ]);
  const volumeLayer = makeLayer("volume", "成交量能", 25, [
    { name: "Delta Volume", score: Number.isFinite(snapshot.deltaVolume) ? (snapshot.deltaVolume > 0 ? 64 : snapshot.deltaVolume < 0 ? 36 : 50) : null, value: snapshot.deltaVolume },
    {
      name: "量價配合",
      score: Number.isFinite(volumeRatio) && Number.isFinite(latestChange)
        ? volumeRatio >= 1.2 ? (latestChange >= 0 ? 68 : 32) : latestChange >= 0 ? 56 : 44
        : null,
      value: volumeRatio,
    },
    { name: "OBV", score: Number.isFinite(snapshot.obv) ? (latestChange > 0 ? 60 : latestChange < 0 ? 40 : 50) : null, value: snapshot.obv },
  ]);
  const oiLayer = makeLayer("open-interest", "未平倉結構", 20, [
    {
      name: "價量 OI 結構",
      score: Number.isFinite(snapshot.oiChange) && Number.isFinite(latestChange)
        ? latestChange >= 0 && snapshot.oiChange > 0 ? 68
          : latestChange < 0 && snapshot.oiChange > 0 ? 32
            : latestChange >= 0 && snapshot.oiChange < 0 ? 55
              : latestChange < 0 && snapshot.oiChange < 0 ? 45
                : 50
        : null,
      value: snapshot.oiChange,
    },
    { name: "未平倉量", score: Number.isFinite(snapshot.openInterest) ? 50 : null, value: snapshot.openInterest },
  ]);
  const timingLayer = makeLayer("timing", "進出場訊號", 15, [
    { name: "RSI", score: Number.isFinite(snapshot.rsi) ? clampScore(20 + snapshot.rsi * 0.6) : null, value: snapshot.rsi },
    { name: "KD", score: [snapshot.kd?.k, snapshot.kd?.d].every(Number.isFinite) ? (snapshot.kd.k >= snapshot.kd.d ? 62 : 38) : null, value: snapshot.kd?.k },
    { name: "BIAS 20", score: Number.isFinite(snapshot.bias20) ? clampScore(50 + snapshot.bias20 * 2) : null, value: snapshot.bias20 },
  ]);
  const layers = [trendLayer, volumeLayer, oiLayer, timingLayer];
  const totalScore = Math.round(layers.reduce((sum, layer) => sum + layer.score * layer.weight / 100, 0));
  const judgement = totalScore >= 62
    ? { label: "期貨結構偏多", tone: "bullish", action: "趨勢與量價偏正向，仍須以支撐、保證金與停損管理部位。" }
    : totalScore <= 38
      ? { label: "期貨結構偏空", tone: "bearish", action: "趨勢與部位結構偏弱，反彈時優先控制槓桿與隔夜風險。" }
      : { label: "期貨結構中性", tone: "neutral", action: "多空因子互有抵銷，等待價格、成交量與 OI 同向確認。" };
  const leader = backtestLearning?.signals?.[0];
  const recent20 = summarizeBacktestSegment(Array.isArray(leader?.returns) ? leader.returns.slice(-20) : []);
  const recentWinPct = Number.isFinite(recent20.winRate) ? recent20.winRate * 100 : null;
  return {
    layers,
    totalScore,
    judgement,
    marketState: totalScore >= 62 ? "多方結構" : totalScore <= 38 ? "空方結構" : "中性整理",
    coverage: Math.round((layers.reduce((sum, layer) => sum + layer.coverage, 0) / layers.length) * 100),
    recent20: {
      ...recent20,
      winState: Number.isFinite(recentWinPct) ? (recentWinPct >= 50 ? "模型觀察正常" : "降低訊號權重") : "樣本不足",
      pfState: Number.isFinite(recent20.profitFactor) ? (recent20.profitFactor >= 1 ? "正常" : "模型失真") : "樣本不足",
      mddState: Number.isFinite(recent20.maxDrawdown) && recent20.maxDrawdown <= -15 ? "啟動風控警報" : "風險可控",
    },
    driftChecks: [],
    outputSteps: [
      `契約趨勢 ${Math.round(trendLayer.score)} / 100`,
      `成交量能 ${Math.round(volumeLayer.score)} / 100`,
      `未平倉結構 ${Math.round(oiLayer.score)} / 100`,
      `進出場訊號 ${Math.round(timingLayer.score)} / 100`,
      `綜合評分 ${totalScore} / 100，${judgement.label}`,
    ],
  };
}
function calculateBollingerBands(history, period = 20, deviation = 2) {
  const closes = history.map((day) => day.close);
  const middle = movingAverage(closes, period);
  return closes.map((close, index) => {
    if (index + 1 < period || middle[index] === null) {
      return { middle: null, upper: null, lower: null, bandwidth: null };
    }
    const window = closes.slice(index - period + 1, index + 1).filter(Number.isFinite);
    if (window.length < period) return { middle: null, upper: null, lower: null, bandwidth: null };
    const average = middle[index];
    const variance = window.reduce((sum, value) => sum + ((value - average) ** 2), 0) / period;
    const sigma = Math.sqrt(variance);
    const upper = average + sigma * deviation;
    const lower = average - sigma * deviation;
    const bandwidth = average ? ((upper - lower) / average) * 100 : null;
    return { middle: average, upper, lower, bandwidth };
  });
}
function calculateFibonacciRetracement(history, lookback = 80) {
  const window = history.slice(-lookback);
  if (window.length < 10) return null;
  const highPoint = window.reduce((best, item, index) => (
    item.high > best.value ? { value: item.high, index, date: item.date } : best
  ), { value: -Infinity, index: -1, date: "" });
  const lowPoint = window.reduce((best, item, index) => (
    item.low < best.value ? { value: item.low, index, date: item.date } : best
  ), { value: Infinity, index: -1, date: "" });
  const range = highPoint.value - lowPoint.value;
  if (!Number.isFinite(range) || range <= 0) return null;
  const upSwing = highPoint.index > lowPoint.index;
  const ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  const levels = ratios.map((ratio) => ({
    ratio,
    label: `${Math.round(ratio * 1000) / 10}%`,
    value: upSwing
      ? highPoint.value - range * ratio
      : lowPoint.value + range * ratio,
  }));
  return { highPoint, lowPoint, range, upSwing, levels };
}
function calculateSupportResistance(history, lookback = 80) {
  const window = history.slice(-lookback);
  if (window.length < 8) return { supports: [], resistances: [] };
  const pivots = technicalPivots(window, 2);
  const latest = window.at(-1);
  const lows = pivots.filter((item) => item.type === "low").map((item) => item.value);
  const highs = pivots.filter((item) => item.type === "high").map((item) => item.value);
  if (lows.length < 2) lows.push(Math.min(...window.map((item) => item.low)));
  if (highs.length < 2) highs.push(Math.max(...window.map((item) => item.high)));

  const cluster = (values, side) => {
    const tolerance = Math.max(latest.close * 0.012, 0.01);
    const sorted = [...values].sort((a, b) => a - b);
    const groups = [];
    sorted.forEach((value) => {
      const group = groups.find((item) => Math.abs(item.average - value) <= tolerance);
      if (group) {
        group.values.push(value);
        group.average = group.values.reduce((sum, item) => sum + item, 0) / group.values.length;
      } else {
        groups.push({ values: [value], average: value });
      }
    });
    return groups
      .map((group) => ({
        value: group.average,
        touches: group.values.length,
        distancePct: ((group.average - latest.close) / latest.close) * 100,
        side,
      }))
      .sort((a, b) => Math.abs(a.distancePct) - Math.abs(b.distancePct))
      .slice(0, 3);
  };

  const supports = cluster(lows.filter((value) => value <= latest.close * 1.02), "support");
  const resistances = cluster(highs.filter((value) => value >= latest.close * 0.98), "resistance");
  return { supports, resistances };
}
function calculateSmartMoneyConcepts(history, lookback = 90) {
  const window = history.slice(-lookback);
  if (window.length < 12) {
    return { bias: "neutral", signals: [], levels: [] };
  }
  const pivots = technicalPivots(window, 2);
  const swingHighs = pivots.filter((item) => item.type === "high");
  const swingLows = pivots.filter((item) => item.type === "low");
  const latest = window.at(-1);
  const previousHigh = swingHighs.at(-1);
  const previousLow = swingLows.at(-1);
  const signals = [];
  const levels = [];
  let score = 0;

  if (previousHigh) {
    levels.push({ type: "liquidity-high", label: "買方流動性", value: previousHigh.value });
    if (latest.close > previousHigh.value) {
      score += 2;
      signals.push(`BOS 向上突破前高 ${previousHigh.value.toFixed(2)}`);
    } else if (latest.high > previousHigh.value && latest.close < previousHigh.value) {
      score -= 1;
      signals.push("掃過前高後收回，疑似上方流動性獵取");
    }
  }
  if (previousLow) {
    levels.push({ type: "liquidity-low", label: "賣方流動性", value: previousLow.value });
    if (latest.close < previousLow.value) {
      score -= 2;
      signals.push(`BOS 向下跌破前低 ${previousLow.value.toFixed(2)}`);
    } else if (latest.low < previousLow.value && latest.close > previousLow.value) {
      score += 1;
      signals.push("跌破前低後收回，疑似下方流動性回收");
    }
  }

  const recentFvg = window.slice(-24).map((item, index, items) => {
    if (index < 2) return null;
    const twoBack = items[index - 2];
    if (item.low > twoBack.high) return { type: "bullish-fvg", label: "多方 FVG", upper: item.low, lower: twoBack.high };
    if (item.high < twoBack.low) return { type: "bearish-fvg", label: "空方 FVG", upper: twoBack.low, lower: item.high };
    return null;
  }).filter(Boolean).at(-1);
  if (recentFvg) {
    levels.push({ type: recentFvg.type, label: recentFvg.label, value: (recentFvg.upper + recentFvg.lower) / 2, upper: recentFvg.upper, lower: recentFvg.lower });
    signals.push(`${recentFvg.label} ${recentFvg.lower.toFixed(2)} ~ ${recentFvg.upper.toFixed(2)} 尚可作為失衡區觀察`);
    score += recentFvg.type === "bullish-fvg" ? 1 : -1;
  }

  const bias = score > 0 ? "bullish" : score < 0 ? "bearish" : "neutral";
  return { bias, score, signals, levels };
}
function buildChipIndicator(detail) {
  const institutional = parseAnalysisNumber(detail.institutionalTrades?.totalValue);
  const large = parseAnalysisNumber(detail.shareholderDistribution?.largeHolderRatio);
  const retail = parseAnalysisNumber(detail.shareholderDistribution?.retailHolderRatio);
  let chipScore = 0;
  const notes = [];
  if (institutional !== null) {
    if (institutional > 0) {
      chipScore += 1;
      notes.push("法人買超");
    } else if (institutional < 0) {
      chipScore -= 1;
      notes.push("法人賣超");
    }
  }
  if (large !== null) {
    if (large >= 60) chipScore += 1;
    else if (large < 35) chipScore -= 1;
    notes.push(`大戶 ${large.toFixed(1)}%`);
  }
  if (retail !== null) {
    if (retail >= 35) chipScore -= 1;
    else if (retail < 15) chipScore += 1;
    notes.push(`散戶 ${retail.toFixed(1)}%`);
  }
  if (!notes.length) return null;
  return {
    score: chipScore,
    value: `${chipScore > 0 ? "+" : ""}${chipScore}`,
    text: `${notes.join("、")}；${chipScore >= 2 ? "籌碼偏集中" : chipScore <= -2 ? "籌碼偏鬆動" : "籌碼訊號分歧"}`,
    direction: chipScore > 0 ? "bullish" : chipScore < 0 ? "bearish" : "neutral",
  };
}
function buildMovingAverageIndicator(history, { isEtf = false, isFutures = false, assetLabel = "股價", periodUnit = "日" } = {}) {
  if (!Array.isArray(history) || history.length < 20) return null;
  const closes = history.map((item) => item.close).filter(Number.isFinite);
  const latestClose = closes.at(-1);
  if (!Number.isFinite(latestClose)) return null;

  const periods = [5, 10, 20, 60, 120, 240];
  const series = Object.fromEntries(periods.map((period) => [
    period,
    technicalSma(closes, period),
  ]));
  const current = Object.fromEntries(periods.map((period) => [period, series[period].at(-1)]));
  const previous = Object.fromEntries(periods.map((period) => [period, series[period].at(-2)]));
  const availablePeriods = periods.filter((period) => Number.isFinite(current[period]));
  if (availablePeriods.length < 2) return null;

  const shortPeriods = [5, 10, 20].filter((period) => Number.isFinite(current[period]));
  const longPeriods = [60, 120, 240].filter((period) => Number.isFinite(current[period]));
  const isDescending = (items) => items.length >= 2 && items.every((period, index) => (
    index === 0 || current[items[index - 1]] > current[period]
  ));
  const isAscending = (items) => items.length >= 2 && items.every((period, index) => (
    index === 0 || current[items[index - 1]] < current[period]
  ));
  const bullishOrder = isDescending(availablePeriods);
  const bearishOrder = isAscending(availablePeriods);
  const shortBullish = isDescending(shortPeriods);
  const shortBearish = isAscending(shortPeriods);
  const longBullish = isDescending(longPeriods);
  const longBearish = isAscending(longPeriods);

  const slopePeriods = availablePeriods.filter((period) => Number.isFinite(previous[period]));
  const risingCount = slopePeriods.filter((period) => current[period] > previous[period]).length;
  const fallingCount = slopePeriods.filter((period) => current[period] < previous[period]).length;
  const recentCrosses = [];
  const crossPairs = [[5, 10], [5, 20], [10, 20], [20, 60], [60, 120], [120, 240]];
  crossPairs.forEach(([fast, slow]) => {
    if (![current[fast], current[slow], previous[fast], previous[slow]].every(Number.isFinite)) return;
    if (previous[fast] <= previous[slow] && current[fast] > current[slow]) {
      recentCrosses.push(`${fast} ${periodUnit}均線黃金交叉 ${slow} ${periodUnit}均線`);
    } else if (previous[fast] >= previous[slow] && current[fast] < current[slow]) {
      recentCrosses.push(`${fast} ${periodUnit}均線死亡交叉 ${slow} ${periodUnit}均線`);
    }
  });

  const values = availablePeriods.map((period) => current[period]);
  const spreadPct = values.length >= 2
    ? ((Math.max(...values) - Math.min(...values)) / latestClose) * 100
    : null;
  const referencePeriod = Number.isFinite(current[20]) ? 20 : availablePeriods[0];
  const priceBias = ((latestClose - current[referencePeriod]) / current[referencePeriod]) * 100;
  const recentVolumes = history.slice(-21, -1).map((item) => item.volume).filter(Number.isFinite);
  const averageVolume = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const volumeRatio = averageVolume && Number.isFinite(history.at(-1)?.volume)
    ? history.at(-1).volume / averageVolume
    : null;
  let direction = "neutral";
  let analysisScore = 0;
  const notes = [];
  const confirmations = [];
  const risks = [];

  if (bullishOrder || (shortBullish && longBullish)) {
    direction = "bullish";
    analysisScore += 2;
    notes.push("短中長期均線呈多頭排列");
  } else if (bearishOrder || (shortBearish && longBearish)) {
    direction = "bearish";
    analysisScore -= 2;
    notes.push("短中長期均線呈空頭排列");
  } else if (shortBullish) {
    direction = "bullish";
    analysisScore += 1;
    notes.push("短期均線轉為多頭排列，中長期仍待確認");
  } else if (shortBearish) {
    direction = "bearish";
    analysisScore -= 1;
    notes.push("短期均線轉為空頭排列，中長期仍待確認");
  } else {
    notes.push("均線順序交錯，趨勢處於整理或轉折");
  }

  if (risingCount >= Math.ceil(slopePeriods.length * 0.7)) {
    analysisScore += 1;
    notes.push(`${risingCount} 條均線同步上揚`);
    if (direction === "neutral") direction = "bullish";
  } else if (fallingCount >= Math.ceil(slopePeriods.length * 0.7)) {
    analysisScore -= 1;
    notes.push(`${fallingCount} 條均線同步下彎`);
    if (direction === "neutral") direction = "bearish";
  }

  if (recentCrosses.length) {
    const bullishCrosses = recentCrosses.filter((item) => item.includes("黃金")).length;
    const bearishCrosses = recentCrosses.filter((item) => item.includes("死亡")).length;
    analysisScore += Math.sign(bullishCrosses - bearishCrosses);
    notes.push(recentCrosses.join("、"));
    if (bullishCrosses > bearishCrosses) direction = "bullish";
    if (bearishCrosses > bullishCrosses) direction = "bearish";
  }

  if (Number.isFinite(spreadPct) && spreadPct <= 2.5) {
    notes.push(`均線幅度僅 ${spreadPct.toFixed(1)}%，屬糾結區，等待放量表態`);
    risks.push("均線糾結時容易產生假突破，不宜只憑交叉追價");
    analysisScore = Math.sign(analysisScore) * Math.min(Math.abs(analysisScore), 1);
  }
  if (Math.abs(priceBias) >= 10) {
    notes.push(`${assetLabel}距 ${referencePeriod} ${periodUnit}均線 ${priceBias >= 0 ? "+" : ""}${priceBias.toFixed(1)}%，乖離偏大`);
    risks.push(priceBias > 0 ? "正乖離偏大，短線追價風險升高" : "負乖離偏大，需等待止跌而非直接搶反彈");
    analysisScore -= Math.sign(priceBias);
    if (priceBias > 0 && direction === "bullish") direction = "neutral";
  } else {
    notes.push(`${assetLabel}距 ${referencePeriod} ${periodUnit}均線 ${priceBias >= 0 ? "+" : ""}${priceBias.toFixed(1)}%`);
  }

  if (latestClose > current[referencePeriod]) {
    confirmations.push(`${assetLabel}站上 ${referencePeriod} ${periodUnit}均線，短線支撐較有利`);
  } else {
    confirmations.push(`${assetLabel}跌破 ${referencePeriod} ${periodUnit}均線，短線壓力增加`);
  }
  if (Number.isFinite(current[60])) {
    confirmations.push(latestClose >= current[60] ? `${assetLabel}位於 60 ${periodUnit}均線上方，中期結構較穩` : `${assetLabel}位於 60 ${periodUnit}均線下方，中期趨勢偏弱`);
  }
  if (Number.isFinite(volumeRatio)) {
    confirmations.push(volumeRatio >= 1.2
      ? `成交量為 20 日均量 ${volumeRatio.toFixed(2)} 倍，量能確認較強`
      : volumeRatio <= 0.8
        ? `成交量僅 20 日均量 ${volumeRatio.toFixed(2)} 倍，訊號可信度降低`
        : `成交量為 20 日均量 ${volumeRatio.toFixed(2)} 倍，量能屬正常`);
    if (volumeRatio <= 0.8) risks.push("量能不足，均線突破或跌破仍需後續確認");
  }
  if (!risks.length) risks.push("均線屬落後指標，仍須搭配成交量、MACD、RSI、K 線與支撐壓力");

  const periodRoles = {
    5: "週線／短線強弱",
    10: "雙週線／短線操作",
    20: "月線／波段關鍵",
    60: "季線／中期趨勢",
    120: "半年線／中長期方向",
    240: "年線／長期多空分界",
  };
  const headline = direction === "bullish"
    ? "均線結構偏多"
    : direction === "bearish"
      ? "均線結構偏空"
      : "均線結構整理";
  const practical = direction === "bullish"
    ? "優先觀察回測上揚均線不破、量能配合後的續強機會，不在乖離過大時追價。"
    : direction === "bearish"
      ? "反彈若無法站回下彎均線，仍以風險控管為主；重新站回季線後再提高信心。"
      : "等待均線脫離糾結並由價格、斜率與成交量同向確認，再判斷趨勢方向。";

  return {
    score: Math.max(-3, Math.min(3, analysisScore)),
    direction,
    value: `${headline} · ${analysisScore > 0 ? "+" : ""}${Math.max(-3, Math.min(3, analysisScore))}`,
    text: notes.join("；"),
    headline,
    periods: availablePeriods.map((period) => ({
      period,
      label: `${period} ${periodUnit}均線`,
      role: isFutures ? ({ 5: "短線動能", 10: "短線趨勢", 20: "波段關鍵", 60: "中期趨勢", 120: "長期方向", 240: "超長期方向" }[period]) : periodRoles[period],
      value: current[period],
      slope: Number.isFinite(previous[period])
        ? current[period] > previous[period] ? "向上" : current[period] < previous[period] ? "向下" : "走平"
        : "--",
      position: latestClose >= current[period] ? `${assetLabel}在上` : `${assetLabel}在下`,
    })),
    confirmations,
    crosses: recentCrosses.length ? recentCrosses : ["近期未出現新黃金交叉或死亡交叉"],
    practical,
    risks,
    suitability: isFutures
      ? `期貨契約建議以 5、20、60 ${periodUnit}均線搭配 MACD、RSI、成交量與未平倉量確認，並納入槓桿及轉倉風險。`
      : isEtf
        ? "ETF 建議以 20 日線＋60 日線＋成交量為主，適合波段操作、定期加碼與資產配置。"
        : "個股建議以 5 日線＋20 日線＋60 日線，搭配 MACD、RSI、成交量及籌碼面交叉確認。",
  };
}
function analyzeTechnicalTheories(detail) {
  const history = (detail.historyDays || [])
    .map((item) => ({
      ...item,
      open: parseAnalysisNumber(item.open),
      high: parseAnalysisNumber(item.high),
      low: parseAnalysisNumber(item.low),
      close: parseAnalysisNumber(item.close),
      volume: parseAnalysisNumber(item.volume),
      openInterest: parseAnalysisNumber(item.openInterest),
    }))
    .filter((item) => [item.open, item.high, item.low, item.close].every(Number.isFinite));
  if (history.length < 5) {
    return {
      score: 0,
      evidenceCount: 0,
      patterns: ["歷史資料不足，無法形成型態判斷"],
      indicators: ["指標資料不足"],
      priceIndicators: [],
      volumeIndicators: [],
      breadthIndicators: [],
      indicatorSummary: "價量指標資料不足",
    };
  }

  let score = 0;
  let evidenceCount = 0;
  const patterns = [];
  const theorySignals = [];
  const indicators = [];
  const priceIndicators = [];
  const volumeIndicators = [];
  const breadthIndicators = [];
  const latest = history.at(-1);
  const previous = history.at(-2);
  const isFuturesDetail = Boolean(detail.futuresNativeInterval || history.some((item) => Number.isFinite(item.openInterest)));
  const futuresPeriodUnit = detail.futuresNativeInterval === "week" ? "週" : detail.futuresNativeInterval === "month" ? "月" : "日";
  const assetLabel = isFuturesDetail ? "期貨價格" : "股價";
  const ma5 = parseAnalysisNumber(detail.ma5);
  const ma20 = parseAnalysisNumber(detail.ma20);
  const ma60 = parseAnalysisNumber(detail.ma60);
  const prior20 = history.slice(-21, -1);
  const priorHigh = prior20.length ? Math.max(...prior20.map((item) => item.high)) : null;
  const priorLow = prior20.length ? Math.min(...prior20.map((item) => item.low)) : null;
  const recentVolumes = history.slice(-6, -1).map((item) => item.volume).filter(Number.isFinite);
  const averageVolume = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const closes = history.map((item) => item.close);
  const ma20Series = technicalSma(closes, 20);
  const currentMa20 = ma20Series.at(-1);
  const previousMa20 = ma20Series.at(-2);
  const recent = history.slice(-40);
  const recentPivots = technicalPivots(recent);
  const pivotHighs = recentPivots.filter((item) => item.type === "high");
  const pivotLows = recentPivots.filter((item) => item.type === "low");

  const recordIndicator = (group, name, value, text, direction = "neutral", meta = {}) => {
    const item = { name, value, text, direction, ...meta };
    if (group === "volume") volumeIndicators.push(item);
    else if (group === "breadth") breadthIndicators.push(item);
    else priceIndicators.push(item);
    indicators.push(`${name} ${value}：${text}`);
  };

  const recordScoredIndicator = (group, name, value, text, direction = "neutral", scoreDelta = 0, meta = {}) => {
    evidenceCount += 1;
    score += scoreDelta;
    recordIndicator(group, name, value, text, direction, meta);
  };

  const addTheory = (name, text, theoryScore = 0) => {
    const direction = theoryScore > 0 ? "bullish" : theoryScore < 0 ? "bearish" : "neutral";
    score += theoryScore;
    evidenceCount += 1;
    theorySignals.push({ name, text, score: theoryScore, direction });
    patterns.push(`${name}：${text}`);
  };

  // Dow Theory: use successive swing highs/lows and the medium-term average direction.
  if (pivotHighs.length >= 2 && pivotLows.length >= 2) {
    const higherHigh = pivotHighs.at(-1).value > pivotHighs.at(-2).value;
    const higherLow = pivotLows.at(-1).value > pivotLows.at(-2).value;
    const lowerHigh = pivotHighs.at(-1).value < pivotHighs.at(-2).value;
    const lowerLow = pivotLows.at(-1).value < pivotLows.at(-2).value;
    if (higherHigh && higherLow) {
      addTheory("道氏理論", "波段高點與低點同步墊高，主要趨勢偏多", 1);
    } else if (lowerHigh && lowerLow) {
      addTheory("道氏理論", "波段高點與低點同步下移，主要趨勢偏空", -1);
    } else {
      addTheory("道氏理論", "高低點未形成同向序列，趨勢仍在轉折或盤整", 0);
    }
  } else {
    addTheory("道氏理論", "有效波段轉折點不足，暫以均線及區間方向輔助", 0);
  }

  // Elliott Wave: classify recent alternating pivots as a probable impulse or correction.
  const alternatingPivots = recentPivots.reduce((items, pivot) => {
    const previousPivot = items.at(-1);
    if (!previousPivot || previousPivot.type !== pivot.type) items.push(pivot);
    else if (
      (pivot.type === "high" && pivot.value > previousPivot.value)
      || (pivot.type === "low" && pivot.value < previousPivot.value)
    ) items[items.length - 1] = pivot;
    return items;
  }, []).slice(-6);
  if (alternatingPivots.length >= 5) {
    const first = alternatingPivots[0];
    const last = alternatingPivots.at(-1);
    const risingSwings = alternatingPivots.filter((item, index) => index > 0 && item.value > alternatingPivots[index - 1].value).length;
    const fallingSwings = alternatingPivots.length - 1 - risingSwings;
    if (last.value > first.value && risingSwings >= 3) {
      addTheory("波浪理論", "近期轉折近似多方推進浪，仍須防範第五浪末端震盪", 1);
    } else if (last.value < first.value && fallingSwings >= 3) {
      addTheory("波浪理論", "近期轉折近似空方推進或 ABC 修正延伸", -1);
    } else {
      addTheory("波浪理論", "波段重疊度高，浪型尚未完成確認", 0);
    }
  } else {
    addTheory("波浪理論", "可辨識轉折不足，暫不強行標定浪數", 0);
  }

  // Granville's eight rules around the 20-day moving average.
  if ([currentMa20, previousMa20].every(Number.isFinite)) {
    const distancePct = ((latest.close - currentMa20) / currentMa20) * 100;
    const crossedUp = previous.close <= previousMa20 && latest.close > currentMa20;
    const crossedDown = previous.close >= previousMa20 && latest.close < currentMa20;
    const maRising = currentMa20 > previousMa20;
    if (crossedUp && maRising) {
      addTheory("葛蘭碧八大法則", `${assetLabel}向上突破走升的 20 ${futuresPeriodUnit}均線，符合第一買進法則`, 1);
    } else if (crossedDown && !maRising) {
      addTheory("葛蘭碧八大法則", `${assetLabel}向下跌破走弱的 20 ${futuresPeriodUnit}均線，符合第一賣出法則`, -1);
    } else if (maRising && latest.low <= currentMa20 * 1.01 && latest.close > currentMa20) {
      addTheory("葛蘭碧八大法則", "回測上升均線後重新站回，接近第二或第三買進法則", 1);
    } else if (!maRising && latest.high >= currentMa20 * 0.99 && latest.close < currentMa20) {
      addTheory("葛蘭碧八大法則", "反彈受下降均線壓制，接近第二或第三賣出法則", -1);
    } else if (distancePct >= 10) {
      addTheory("葛蘭碧八大法則", `${assetLabel}高於 20 ${futuresPeriodUnit}均線 ${distancePct.toFixed(1)}%，正乖離過大`, -1);
    } else if (distancePct <= -10) {
      addTheory("葛蘭碧八大法則", `${assetLabel}低於 20 ${futuresPeriodUnit}均線 ${Math.abs(distancePct).toFixed(1)}%，具超跌反彈條件但需止跌`, 0);
    } else {
      addTheory("葛蘭碧八大法則", `${assetLabel}與 20 ${futuresPeriodUnit}均線距離正常，尚無明確買賣法則觸發`, 0);
    }
  } else {
    addTheory("葛蘭碧八大法則", "20 日均線資料不足", 0);
  }

  // Reversal patterns: double top/bottom with tolerance based on recent volatility.
  if (pivotHighs.length >= 2 || pivotLows.length >= 2) {
    const highs = pivotHighs.slice(-2);
    const lows = pivotLows.slice(-2);
    const topTolerance = highs.length === 2 ? Math.abs(highs[1].value - highs[0].value) / highs[0].value : 1;
    const bottomTolerance = lows.length === 2 ? Math.abs(lows[1].value - lows[0].value) / lows[0].value : 1;
    if (highs.length === 2 && topTolerance <= 0.035 && latest.close < Math.min(...recent.slice(highs[0].index, highs[1].index + 1).map((item) => item.low))) {
      addTheory("反轉型態理論", "近似雙重頂且跌破頸線，反轉風險升高", -1);
    } else if (lows.length === 2 && bottomTolerance <= 0.035 && latest.close > Math.max(...recent.slice(lows[0].index, lows[1].index + 1).map((item) => item.high))) {
      addTheory("反轉型態理論", "近似雙重底且突破頸線，反轉向上機率提高", 1);
    } else if (topTolerance <= 0.035) {
      addTheory("反轉型態理論", "高檔近似雙重頂，但尚未有效跌破頸線", 0);
    } else if (bottomTolerance <= 0.035) {
      addTheory("反轉型態理論", "低檔近似雙重底，但尚未有效突破頸線", 0);
    } else {
      addTheory("反轉型態理論", "未形成已確認的雙頂、雙底或明顯頭肩反轉", 0);
    }
  } else {
    addTheory("反轉型態理論", "轉折點不足，尚無可確認反轉型態", 0);
  }

  // Continuation patterns: rectangle or converging triangle followed by breakout.
  const consolidation = history.slice(-16, -1);
  if (consolidation.length >= 10) {
    const consolidationHighs = consolidation.map((item) => item.high);
    const consolidationLows = consolidation.map((item) => item.low);
    const rangeHigh = Math.max(...consolidationHighs);
    const rangeLow = Math.min(...consolidationLows);
    const rangePct = ((rangeHigh - rangeLow) / Math.max(rangeLow, 0.0001)) * 100;
    const converging = technicalSlope(consolidationHighs) < 0 && technicalSlope(consolidationLows) > 0;
    if (latest.close > rangeHigh) {
      addTheory("連續整理型態理論", `${converging ? "三角收斂" : "箱型整理"}後向上突破`, 1);
    } else if (latest.close < rangeLow) {
      addTheory("連續整理型態理論", `${converging ? "三角收斂" : "箱型整理"}後向下跌破`, -1);
    } else if (converging) {
      addTheory("連續整理型態理論", "高點下降、低點上升，呈三角收斂等待方向", 0);
    } else if (rangePct <= 10) {
      addTheory("連續整理型態理論", `近 15 日箱型幅度約 ${rangePct.toFixed(1)}%，仍在整理區`, 0);
    } else {
      addTheory("連續整理型態理論", "區間波動較大，尚未形成穩定旗形、三角形或箱型", 0);
    }
  }

  // Trendline theory based on regression slopes of recent highs and lows.
  const trendWindow = history.slice(-20);
  if (trendWindow.length >= 10) {
    const lowSlope = technicalSlope(trendWindow.map((item) => item.low));
    const highSlope = technicalSlope(trendWindow.map((item) => item.high));
    const normalizedSlope = ((lowSlope + highSlope) / 2) / Math.max(latest.close, 0.0001) * 100;
    if (lowSlope > 0 && highSlope > 0) {
      addTheory("趨勢線理論", `高低軌同步上揚，日均斜率約 ${normalizedSlope.toFixed(2)}%`, 1);
    } else if (lowSlope < 0 && highSlope < 0) {
      addTheory("趨勢線理論", `高低軌同步下彎，日均斜率約 ${normalizedSlope.toFixed(2)}%`, -1);
    } else {
      addTheory("趨勢線理論", "上下軌斜率分歧，趨勢線處於收斂或擴張階段", 0);
    }
  }

  if ([ma5, ma20, ma60].every(Number.isFinite)) {
    evidenceCount += 1;
    if (latest.close > ma5 && ma5 > ma20 && ma20 > ma60) {
      score += 2;
      patterns.push("均線呈多頭排列，趨勢結構偏強");
    } else if (latest.close < ma5 && ma5 < ma20 && ma20 < ma60) {
      score -= 2;
      patterns.push("均線呈空頭排列，趨勢結構偏弱");
    } else {
      patterns.push("均線交錯，價格仍處於整理或轉折階段");
    }
  }
  if (priorHigh !== null && latest.close > priorHigh) {
    evidenceCount += 1;
    score += averageVolume && latest.volume > averageVolume * 1.2 ? 2 : 1;
    patterns.push(averageVolume && latest.volume > averageVolume * 1.2 ? "放量突破近 20 日壓力" : "突破近 20 日壓力，但量能確認有限");
  } else if (priorLow !== null && latest.close < priorLow) {
    evidenceCount += 1;
    score -= averageVolume && latest.volume > averageVolume * 1.2 ? 2 : 1;
    patterns.push(averageVolume && latest.volume > averageVolume * 1.2 ? "放量跌破近 20 日支撐" : "跌破近 20 日支撐");
  }

  const latestBody = Math.abs(latest.close - latest.open);
  const latestRange = Math.max(latest.high - latest.low, 0.0001);
  const upperShadow = latest.high - Math.max(latest.open, latest.close);
  const lowerShadow = Math.min(latest.open, latest.close) - latest.low;
  const previousBearish = previous.close < previous.open;
  const previousBullish = previous.close > previous.open;
  if (
    previousBearish && latest.close > latest.open
    && latest.open <= previous.close && latest.close >= previous.open
  ) {
    evidenceCount += 1;
    score += 1;
    patterns.push("出現多方吞噬型態，短線具反轉意義");
    addTheory("K 線理論", "多方吞噬前一根黑 K，短線買盤轉強", 1);
  } else if (
    previousBullish && latest.close < latest.open
    && latest.open >= previous.close && latest.close <= previous.open
  ) {
    evidenceCount += 1;
    score -= 1;
    patterns.push("出現空方吞噬型態，短線需防轉弱");
    addTheory("K 線理論", "空方吞噬前一根紅 K，短線賣壓轉強", -1);
  } else if (lowerShadow >= latestBody * 2 && upperShadow <= latestBody && latest.close >= latest.open) {
    addTheory("K 線理論", "出現長下影錘頭線，低檔承接力增強", 1);
  } else if (upperShadow >= latestBody * 2 && lowerShadow <= latestBody && latest.close <= latest.open) {
    addTheory("K 線理論", "出現長上影射擊之星，短線上檔賣壓增強", -1);
  } else if (latestBody / latestRange < 0.15) {
    evidenceCount += 1;
    patterns.push("出現十字線，市場多空進入觀望");
    addTheory("K 線理論", "十字線顯示多空平衡，需由下一根 K 線確認", 0);
  } else {
    addTheory("K 線理論", latest.close > latest.open ? "實體紅 K，由買方掌握當日收盤" : "實體黑 K，由賣方掌握當日收盤", latest.close > latest.open ? 1 : -1);
  }

  // Gap theory checks the latest session and whether a recent gap remains unfilled.
  const upwardGap = latest.low > previous.high;
  const downwardGap = latest.high < previous.low;
  if (upwardGap) {
    addTheory("缺口理論", `向上跳空 ${((latest.low - previous.high) / previous.high * 100).toFixed(2)}%，缺口未回補前偏多`, 1);
  } else if (downwardGap) {
    addTheory("缺口理論", `向下跳空 ${((previous.low - latest.high) / previous.low * 100).toFixed(2)}%，缺口未回補前偏空`, -1);
  } else {
    const recentGap = history.slice(-16, -1).map((item, index, items) => {
      if (!index) return null;
      if (item.low > items[index - 1].high) return { type: "up", boundary: items[index - 1].high };
      if (item.high < items[index - 1].low) return { type: "down", boundary: items[index - 1].low };
      return null;
    }).filter(Boolean).at(-1);
    if (recentGap?.type === "up" && latest.low > recentGap.boundary) {
      addTheory("缺口理論", "近期向上缺口仍未完全回補，可視為潛在支撐", 1);
    } else if (recentGap?.type === "down" && latest.high < recentGap.boundary) {
      addTheory("缺口理論", "近期向下缺口仍未完全回補，可視為潛在壓力", -1);
    } else {
      addTheory("缺口理論", "近期無有效未回補缺口", 0);
    }
  }

  const supportResistance = calculateSupportResistance(history);
  const nearestSupport = supportResistance.supports?.[0];
  const nearestResistance = supportResistance.resistances?.[0];
  if (nearestSupport || nearestResistance) {
    const supportText = nearestSupport
      ? `近支撐 ${nearestSupport.value.toFixed(2)}（距離 ${nearestSupport.distancePct.toFixed(1)}%）`
      : "下方有效支撐不足";
    const resistanceText = nearestResistance
      ? `近壓力 ${nearestResistance.value.toFixed(2)}（距離 +${nearestResistance.distancePct.toFixed(1)}%）`
      : "上方壓力尚未明顯";
    const srScore = nearestResistance && latest.close > nearestResistance.value
      ? 1
      : nearestSupport && latest.close < nearestSupport.value
        ? -1
        : 0;
    const srActionText = latest.close > (nearestResistance?.value || Infinity)
      ? "已突破主要壓力，觀察是否站穩"
      : latest.close < (nearestSupport?.value || -Infinity)
        ? "已跌破主要支撐，風險升高"
        : "目前位於支撐與壓力區間內";
    addTheory("Support and Resistance", `${supportText}；${resistanceText}；${srActionText}`, srScore);
  }

  const fibonacci = calculateFibonacciRetracement(history);
  if (fibonacci) {
    const sortedByDistance = [...fibonacci.levels].sort((a, b) => Math.abs(a.value - latest.close) - Math.abs(b.value - latest.close));
    const nearestFib = sortedByDistance[0];
    const golden = fibonacci.levels.find((item) => item.ratio === 0.618);
    const fibDirection = fibonacci.upSwing
      ? latest.close >= (golden?.value || latest.close) ? "bullish" : "neutral"
      : latest.close <= (golden?.value || latest.close) ? "bearish" : "neutral";
    addTheory(
      "斐波那契回撤",
      `${fibonacci.upSwing ? "上升波回撤" : "下降波反彈"}，目前接近 ${nearestFib.label} ${nearestFib.value.toFixed(2)}，61.8% 關鍵位 ${golden?.value.toFixed(2) || "--"}；${fibonacci.upSwing ? "用回撤位判斷多方防守區" : "用反彈位判斷空方壓力區"}`,
      fibDirection === "bullish" ? 1 : fibDirection === "bearish" ? -1 : 0,
    );
  }

  const smc = calculateSmartMoneyConcepts(history);
  if (smc.signals.length) {
    score += Math.sign(smc.score || 0);
    evidenceCount += 1;
    const smcBiasText = smc.bias === "bullish" ? "偏多結構" : smc.bias === "bearish" ? "偏空結構" : "中性結構";
    addTheory("Smart Money Concepts", `${smcBiasText}；${smc.signals.slice(0, 2).join("；")}`, smc.bias === "bullish" ? 1 : smc.bias === "bearish" ? -1 : 0);
  } else {
    addTheory("Smart Money Concepts", "尚未偵測到明確 BOS、流動性掃蕩或 FVG 失衡區", 0);
  }

  if (averageVolume && latest.volume) {
    evidenceCount += 1;
    const volumeRatio = latest.volume / averageVolume;
    const priorAverageVolume = history.slice(-11, -6)
      .map((item) => item.volume)
      .filter(Number.isFinite);
    const priorAverage = priorAverageVolume.length
      ? priorAverageVolume.reduce((sum, value) => sum + value, 0) / priorAverageVolume.length
      : null;
    const averageTrend = priorAverage ? ((averageVolume - priorAverage) / priorAverage) * 100 : null;
    const volumePricePattern = classifyVolumePriceNinePatterns({ latest, previous, volumeRatio, averageTrend });
    score += volumePricePattern.score;
    patterns.push(`量價九式：${volumePricePattern.name}（量比 ${volumeRatio.toFixed(2)}，價變 ${volumePricePattern.priceChangePct >= 0 ? "+" : ""}${volumePricePattern.priceChangePct.toFixed(2)}%）`);
    recordIndicator(
      "volume",
      "平均成交量",
      `量價九式：${volumePricePattern.name}`,
      `${volumePricePattern.text}；量比 ${volumeRatio.toFixed(2)}，價變 ${volumePricePattern.priceChangePct >= 0 ? "+" : ""}${volumePricePattern.priceChangePct.toFixed(2)}%`,
      volumePricePattern.direction,
    );
  }

  const movingAverageIndicator = buildMovingAverageIndicator(history, {
    isEtf: Boolean(detail.isEtf),
    isFutures: isFuturesDetail,
    assetLabel,
    periodUnit: futuresPeriodUnit,
  });
  if (movingAverageIndicator) {
    evidenceCount += 1;
    score += movingAverageIndicator.score;
    recordIndicator(
      "price",
      "均線分析法",
      movingAverageIndicator.value,
      movingAverageIndicator.text,
      movingAverageIndicator.direction,
      { movingAverage: movingAverageIndicator },
    );
  }

  if (history.length >= 9) {
    const kd = calculateKd(history);
    const current = kd.at(-1);
    const prior = kd.at(-2);
    if (current && prior) {
      evidenceCount += 1;
      if (prior.k <= prior.d && current.k > current.d) {
        score += current.k < 30 ? 2 : 1;
        recordIndicator("price", "KD", `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`, "黃金交叉，短線動能轉強", "bullish");
      } else if (prior.k >= prior.d && current.k < current.d) {
        score -= current.k > 70 ? 2 : 1;
        recordIndicator("price", "KD", `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`, "死亡交叉，短線動能轉弱", "bearish");
      } else if (current.k > 80 && current.d > 80) {
        recordIndicator("price", "KD", `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`, "位於超買區，留意高檔鈍化或拉回", "bearish");
      } else if (current.k < 20 && current.d < 20) {
        recordIndicator("price", "KD", `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`, "位於超賣區，等待止跌訊號", "neutral");
      } else {
        recordIndicator(
          "price",
          "KD",
          `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`,
          current.k >= current.d ? "K 值位於 D 值上方，短線偏多" : "K 值位於 D 值下方，短線偏弱",
          current.k >= current.d ? "bullish" : "bearish",
        );
      }
    }
  }
  if (history.length >= 26) {
    const macd = calculateMacd(history);
    const current = macd.at(-1);
    const prior = macd.at(-2);
    if (current?.dif !== null && current?.macd !== null && prior?.dif !== null && prior?.macd !== null) {
      evidenceCount += 1;
      if (prior.dif <= prior.macd && current.dif > current.macd) {
        score += current.osc >= 0 ? 2 : 1;
        recordIndicator("price", "MACD", `DIF ${current.dif.toFixed(2)} / DEA ${current.macd.toFixed(2)}`, "黃金交叉，動能轉強", "bullish");
      } else if (prior.dif >= prior.macd && current.dif < current.macd) {
        score -= current.osc <= 0 ? 2 : 1;
        recordIndicator("price", "MACD", `DIF ${current.dif.toFixed(2)} / DEA ${current.macd.toFixed(2)}`, "死亡交叉，動能轉弱", "bearish");
      } else if (current.osc > 0 && current.osc > prior.osc) {
        score += 1;
        recordIndicator("price", "MACD", `OSC ${current.osc.toFixed(2)}`, "柱狀體位於零軸上方且擴張", "bullish");
      } else if (current.osc < 0 && current.osc < prior.osc) {
        score -= 1;
        recordIndicator("price", "MACD", `OSC ${current.osc.toFixed(2)}`, "負柱擴張，空方動能增強", "bearish");
      } else {
        recordIndicator(
          "price",
          "MACD",
          `OSC ${current.osc.toFixed(2)}`,
          current.osc >= 0 ? "柱狀體位於零軸上方，動能偏多" : "柱狀體位於零軸下方，動能偏弱",
          current.osc >= 0 ? "bullish" : "bearish",
        );
      }
    }
  }
  if (history.length >= 14) {
    const rsi = calculateRsi(history).at(-1);
    if (Number.isFinite(rsi)) {
      evidenceCount += 1;
      if (rsi >= 70) recordIndicator("price", "RSI", rsi.toFixed(1), "進入超買區，留意過熱修正", "bearish");
      else if (rsi <= 30) recordIndicator("price", "RSI", rsi.toFixed(1), "進入超賣區，等待止跌確認", "neutral");
      else if (rsi >= 50) {
        score += 1;
        recordIndicator("price", "RSI", rsi.toFixed(1), "位於多方區", "bullish");
      } else {
        score -= 1;
        recordIndicator("price", "RSI", rsi.toFixed(1), "位於空方區", "bearish");
      }
    }
    const dmi = calculateDmi(history).at(-1);
    if (dmi && Number.isFinite(dmi.plusDi) && Number.isFinite(dmi.minusDi)) {
      evidenceCount += 1;
      if (dmi.plusDi > dmi.minusDi && (dmi.adx || 0) >= 20) {
        score += 1;
        recordIndicator("price", "DMI", `+DI ${dmi.plusDi.toFixed(1)} / -DI ${dmi.minusDi.toFixed(1)} / ADX ${(dmi.adx || 0).toFixed(1)}`, "多方占優且趨勢成形", "bullish");
      } else if (dmi.minusDi > dmi.plusDi && (dmi.adx || 0) >= 20) {
        score -= 1;
        recordIndicator("price", "DMI", `+DI ${dmi.plusDi.toFixed(1)} / -DI ${dmi.minusDi.toFixed(1)} / ADX ${(dmi.adx || 0).toFixed(1)}`, "空方占優且趨勢成形", "bearish");
      } else {
        recordIndicator("price", "DMI", `+DI ${dmi.plusDi.toFixed(1)} / -DI ${dmi.minusDi.toFixed(1)} / ADX ${(dmi.adx || 0).toFixed(1)}`, "趨勢強度不足，較偏區間震盪", "neutral");
      }
    }
  }
  if (history.length >= 20) {
    const bollinger = calculateBollingerBands(history);
    const currentBand = bollinger.at(-1);
    const priorBand = bollinger.at(-6);
    if (currentBand && [currentBand.upper, currentBand.middle, currentBand.lower].every(Number.isFinite)) {
      evidenceCount += 1;
      const position = ((latest.close - currentBand.lower) / Math.max(currentBand.upper - currentBand.lower, 0.0001)) * 100;
      const bandwidthTrend = Number.isFinite(priorBand?.bandwidth)
        ? currentBand.bandwidth - priorBand.bandwidth
        : null;
      if (latest.close > currentBand.upper) {
        score += 1;
        recordIndicator("price", "布林通道", `上軌 ${currentBand.upper.toFixed(2)}`, "收盤突破上軌，趨勢動能強但需防短線過熱", "bullish");
      } else if (latest.close < currentBand.lower) {
        score -= 1;
        recordIndicator("price", "布林通道", `下軌 ${currentBand.lower.toFixed(2)}`, "收盤跌破下軌，弱勢延伸或超跌反彈皆需確認", "bearish");
      } else if (position >= 70) {
        recordIndicator("price", "布林通道", `${position.toFixed(0)}%`, `價格位於通道偏上緣${bandwidthTrend !== null ? `，帶寬${bandwidthTrend >= 0 ? "擴張" : "收斂"}` : ""}`, "bullish");
      } else if (position <= 30) {
        recordIndicator("price", "布林通道", `${position.toFixed(0)}%`, `價格位於通道偏下緣${bandwidthTrend !== null ? `，帶寬${bandwidthTrend >= 0 ? "擴張" : "收斂"}` : ""}`, "bearish");
      } else {
        recordIndicator("price", "布林通道", `${position.toFixed(0)}%`, `價格位於中性區，帶寬 ${currentBand.bandwidth?.toFixed(1) || "--"}%`, "neutral");
      }
    }
  }
  if (history.length >= 6) {
    const bias = calculateBias(history).at(-1);
    if (Number.isFinite(bias)) {
      evidenceCount += 1;
      if (bias >= 8) {
        score -= 1;
        recordIndicator("price", "BIAS", `${bias.toFixed(1)}%`, "正乖離偏大，追價風險升高", "bearish");
      } else if (bias <= -8) {
        recordIndicator("price", "BIAS", `${bias.toFixed(1)}%`, "負乖離偏大，等待止跌與均值回歸", "neutral");
      } else {
        recordIndicator(
          "price",
          "BIAS",
          `${bias.toFixed(1)}%`,
          bias >= 0 ? `${assetLabel}位於短期均線上方，乖離仍在可控區` : `${assetLabel}位於短期均線下方，乖離仍在可控區`,
          bias >= 0 ? "bullish" : "bearish",
        );
      }
    }
    const obv = calculateObv(history);
    const currentObv = obv.at(-1);
    const priorObv = obv.at(-6);
    if (Number.isFinite(currentObv) && Number.isFinite(priorObv)) {
      evidenceCount += 1;
      if (currentObv > priorObv && latest.close >= history.at(-6).close) {
        score += 1;
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "與價格同步走高，資金動能偏正向", "bullish");
      } else if (currentObv < priorObv && latest.close <= history.at(-6).close) {
        score -= 1;
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "與價格同步走低，資金動能偏弱", "bearish");
      } else if (currentObv > priorObv && latest.close < history.at(-6).close) {
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "正背離，價格轉弱但量能未同步惡化", "bullish");
      } else if (currentObv < priorObv && latest.close > history.at(-6).close) {
        score -= 1;
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "負背離，價格上漲但量能未跟進", "bearish");
      } else {
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "近期變化有限，資金方向尚未明朗", "neutral");
      }
    }
  }

  if (history.length >= 15) {
    const atrSeries = calculateAtr(history);
    const currentAtr = atrSeries.at(-1);
    const priorAtr = atrSeries.at(-6);
    if (Number.isFinite(currentAtr)) {
      const atrPct = (currentAtr / Math.max(Math.abs(latest.close), 0.0001)) * 100;
      const atrExpanding = Number.isFinite(priorAtr) && currentAtr > priorAtr * 1.08;
      const atrCooling = Number.isFinite(priorAtr) && currentAtr < priorAtr * 0.92;
      const priceUp = latest.close >= previous.close;
      const direction = atrExpanding
        ? priceUp ? "bullish" : "bearish"
        : "neutral";
      const scoreDelta = atrExpanding
        ? priceUp ? 1 : -1
        : 0;
      const volatilityText = atrPct >= 5
        ? "波動偏高，停損與部位需保守"
        : atrPct >= 2.5
          ? "波動中等，適合搭配支撐壓力控管"
          : "波動收斂，需等待方向突破";
      const trendText = atrExpanding
        ? priceUp ? "ATR 擴張且收盤上行，趨勢推進力偏多" : "ATR 擴張但收盤下行，空方波動風險升高"
        : atrCooling
          ? "ATR 收斂，行情進入整理或等待新方向"
          : "ATR 變化平穩，趨勢動能未明顯放大";
      recordScoredIndicator("price", "ATR", `${currentAtr.toFixed(2)} / ${atrPct.toFixed(2)}%`, `${trendText}；${volatilityText}`, direction, scoreDelta);
    }
  }

  if (history.length >= 20) {
    const cci = calculateCci(history).at(-1);
    if (Number.isFinite(cci)) {
      if (cci >= 100) {
        recordScoredIndicator("price", "CCI", cci.toFixed(1), "突破 +100，商品通道動能偏強，趨勢延續機率較高", "bullish", 1);
      } else if (cci <= -100) {
        recordScoredIndicator("price", "CCI", cci.toFixed(1), "跌破 -100，弱勢動能仍在，需等回到 -100 上方再確認修復", "bearish", -1);
      } else {
        recordScoredIndicator("price", "CCI", cci.toFixed(1), "位於中性通道，價格尚未形成明確趨勢推力", "neutral", 0);
      }
    }
  }

  if (history.length >= 14) {
    const williams = calculateWilliamsR(history).at(-1);
    if (Number.isFinite(williams)) {
      if (williams >= -20) {
        recordScoredIndicator("price", "Williams %R", williams.toFixed(1), "進入短線超買區，續強時可鈍化，但追價風險升高", "bearish", -1);
      } else if (williams <= -80) {
        recordScoredIndicator("price", "Williams %R", williams.toFixed(1), "進入短線超賣區，需觀察是否出現止跌反彈訊號", "neutral", 0);
      } else if (williams >= -50) {
        recordScoredIndicator("price", "Williams %R", williams.toFixed(1), "位於多方半場，短線買盤仍有支撐", "bullish", 1);
      } else {
        recordScoredIndicator("price", "Williams %R", williams.toFixed(1), "位於空方半場，短線反彈仍需量能確認", "bearish", -1);
      }
    }
  }

  if (history.length >= 15) {
    const mfi = calculateMfi(history).at(-1);
    if (Number.isFinite(mfi)) {
      if (mfi >= 80) {
        recordScoredIndicator("volume", "MFI", mfi.toFixed(1), "資金流量進入超買區，價格續強時需留意獲利了結", "bearish", -1);
      } else if (mfi <= 20) {
        recordScoredIndicator("volume", "MFI", mfi.toFixed(1), "資金流量進入超賣區，若價格止跌可視為反彈觀察點", "neutral", 0);
      } else if (mfi >= 50) {
        recordScoredIndicator("volume", "MFI", mfi.toFixed(1), "資金流量位於多方區，量價資金支持仍在", "bullish", 1);
      } else {
        recordScoredIndicator("volume", "MFI", mfi.toFixed(1), "資金流量位於空方區，買盤承接力仍偏弱", "bearish", -1);
      }
    }
  }

  if (history.length >= 11) {
    const momentumSeries = calculateMomentum(history);
    const currentMomentum = momentumSeries.at(-1);
    const priorMomentum = momentumSeries.at(-2);
    if (Number.isFinite(currentMomentum)) {
      const improving = Number.isFinite(priorMomentum) && currentMomentum > priorMomentum;
      const weakening = Number.isFinite(priorMomentum) && currentMomentum < priorMomentum;
      if (currentMomentum > 0 && improving) {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "10 期動能為正且持續改善，趨勢推升力偏多", "bullish", 1);
      } else if (currentMomentum < 0 && weakening) {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "10 期動能為負且持續惡化，下行壓力仍在", "bearish", -1);
      } else if (currentMomentum > 0) {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "動能仍為正，但擴張力道需要重新確認", "bullish", 0);
      } else if (currentMomentum < 0) {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "動能仍為負，反彈需要突破短期壓力", "bearish", 0);
      } else {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "動能接近零軸，多空進入平衡", "neutral", 0);
      }
    }
  }

  if (history.length >= 4) {
    const sarSeries = calculateParabolicSarSeries(history);
    const currentSar = sarSeries.at(-1);
    const priorSar = sarSeries.at(-2);
    if (Number.isFinite(currentSar)) {
      const crossedUp = Number.isFinite(priorSar) && previous.close <= priorSar && latest.close > currentSar;
      const crossedDown = Number.isFinite(priorSar) && previous.close >= priorSar && latest.close < currentSar;
      if (latest.close > currentSar) {
        recordScoredIndicator("price", "SAR", currentSar.toFixed(2), crossedUp ? "價格重新站上 SAR，短線止跌轉強訊號成立" : "價格位於 SAR 上方，追蹤停利線維持偏多", "bullish", crossedUp ? 2 : 1);
      } else {
        recordScoredIndicator("price", "SAR", currentSar.toFixed(2), crossedDown ? "價格跌破 SAR，短線轉弱訊號成立" : "價格位於 SAR 下方，趨勢仍偏弱", "bearish", crossedDown ? -2 : -1);
      }
    }
  }

  if (history.length >= 26) {
    const ichimokuSeries = calculateIchimoku(history);
    const currentIchimoku = ichimokuSeries.at(-1);
    if (
      Number.isFinite(currentIchimoku?.tenkan)
      && Number.isFinite(currentIchimoku?.kijun)
    ) {
      const senkouA = (currentIchimoku.tenkan + currentIchimoku.kijun) / 2;
      const hasCloud = Number.isFinite(currentIchimoku.senkouB);
      const cloudTop = hasCloud ? Math.max(senkouA, currentIchimoku.senkouB) : Math.max(currentIchimoku.tenkan, currentIchimoku.kijun);
      const cloudBottom = hasCloud ? Math.min(senkouA, currentIchimoku.senkouB) : Math.min(currentIchimoku.tenkan, currentIchimoku.kijun);
      const tenkanAbove = currentIchimoku.tenkan >= currentIchimoku.kijun;
      if (latest.close > cloudTop && tenkanAbove) {
        recordScoredIndicator(
          "price",
          "Ichimoku",
          `${currentIchimoku.tenkan.toFixed(2)} / ${currentIchimoku.kijun.toFixed(2)} / ${hasCloud ? currentIchimoku.senkouB.toFixed(2) : "--"}`,
          "價格位於雲層上方且轉換線高於基準線，一目均衡表偏多",
          "bullish",
          2,
        );
      } else if (latest.close < cloudBottom && !tenkanAbove) {
        recordScoredIndicator(
          "price",
          "Ichimoku",
          `${currentIchimoku.tenkan.toFixed(2)} / ${currentIchimoku.kijun.toFixed(2)} / ${hasCloud ? currentIchimoku.senkouB.toFixed(2) : "--"}`,
          "價格位於雲層下方且轉換線低於基準線，一目均衡表偏空",
          "bearish",
          -2,
        );
      } else {
        recordScoredIndicator(
          "price",
          "Ichimoku",
          `${currentIchimoku.tenkan.toFixed(2)} / ${currentIchimoku.kijun.toFixed(2)} / ${hasCloud ? currentIchimoku.senkouB.toFixed(2) : "--"}`,
          "價格與雲層、轉換線及基準線交錯，趨勢仍需等待方向確認",
          "neutral",
          0,
        );
      }
    }
  }

  const breadth = isFuturesDetail ? null : buildMarketBreadthIndicators(detail);
  if (breadth) {
    evidenceCount += 3;
    const breadthTotal = Math.max(breadth.advancing + breadth.declining, 1);
    const obosPct = (breadth.obos / breadthTotal) * 100;
    if (breadth.adr >= 200) {
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；多方廣度過熱`, "bearish");
    } else if (breadth.adr >= 125) {
      score += 1;
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；市場廣度偏多`, "bullish");
    } else if (breadth.adr <= 50) {
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；空方廣度過度擴張`, "neutral");
    } else if (breadth.adr <= 80) {
      score -= 1;
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；市場廣度偏空`, "bearish");
    } else {
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；多空家數接近`, "neutral");
    }

    if (breadth.previousAdl === null) {
      recordIndicator("breadth", "騰落指標 ADL", Math.round(breadth.adl).toLocaleString("zh-TW"), "已建立首日基準，累積更多交易日後判斷趨勢", "neutral");
    } else if (breadth.adl > breadth.previousAdl) {
      score += 1;
      recordIndicator("breadth", "騰落指標 ADL", Math.round(breadth.adl).toLocaleString("zh-TW"), `較前值上升，市場參與廣度改善；已累積 ${breadth.historyCount} 日`, "bullish");
    } else if (breadth.adl < breadth.previousAdl) {
      score -= 1;
      recordIndicator("breadth", "騰落指標 ADL", Math.round(breadth.adl).toLocaleString("zh-TW"), `較前值下降，市場參與廣度轉弱；已累積 ${breadth.historyCount} 日`, "bearish");
    } else {
      recordIndicator("breadth", "騰落指標 ADL", Math.round(breadth.adl).toLocaleString("zh-TW"), "與前值持平，市場廣度無明顯變化", "neutral");
    }

    if (obosPct >= 20) {
      recordIndicator("breadth", "超買超賣指標 OBOS", `${breadth.obos > 0 ? "+" : ""}${breadth.obos}`, `淨上漲家數占比 ${obosPct.toFixed(1)}%，市場進入超買區`, "bearish");
    } else if (obosPct <= -20) {
      recordIndicator("breadth", "超買超賣指標 OBOS", `${breadth.obos}`, `淨下跌家數占比 ${obosPct.toFixed(1)}%，市場進入超賣區`, "bullish");
    } else {
      recordIndicator("breadth", "超買超賣指標 OBOS", `${breadth.obos > 0 ? "+" : ""}${breadth.obos}`, `淨漲跌家數占比 ${obosPct.toFixed(1)}%，尚未進入極端區`, obosPct > 5 ? "bullish" : obosPct < -5 ? "bearish" : "neutral");
    }
  }

  if (!breadth && isFuturesDetail) {
    buildFuturesBreadthProxyIndicators(history).forEach((item) => {
      recordScoredIndicator("breadth", item.name, item.value, item.text, item.direction, item.scoreDelta || 0);
    });
  }

  const psy = calculatePsy(history);
  if (Number.isFinite(psy)) {
    evidenceCount += 1;
    if (psy >= 75) {
      score -= 1;
      recordIndicator("breadth", "心理線 PSY", `${psy.toFixed(1)}%`, "近 12 日上漲天數過多，市場情緒偏熱", "bearish");
    } else if (psy <= 25) {
      recordIndicator("breadth", "心理線 PSY", `${psy.toFixed(1)}%`, "近 12 日上漲天數偏少，情緒超賣但仍需止跌確認", "bullish");
    } else {
      recordIndicator("breadth", "心理線 PSY", `${psy.toFixed(1)}%`, psy >= 50 ? "多方交易日略占優勢" : "空方交易日略占優勢", psy >= 50 ? "bullish" : "bearish");
    }
  }

  const chipIndicator = buildChipIndicator(detail);
  if (chipIndicator) {
    evidenceCount += 1;
    score += Math.sign(chipIndicator.score);
    recordIndicator("breadth", "籌碼面指標", chipIndicator.value, chipIndicator.text, chipIndicator.direction);
  }

  const backtestLearning = buildBacktestLearningModel(history);
  backtestLearning.institutionalFramework = isFuturesDetail
    ? buildFuturesBacktestFramework(detail, history, backtestLearning)
    : buildInstitutionalBacktestFramework(detail, history, backtestLearning);
  if (backtestLearning.evidenceCount) {
    score += backtestLearning.scoreAdjustment;
    evidenceCount += 1;
  }

  const priceBullish = priceIndicators.filter((item) => item.direction === "bullish").length;
  const priceBearish = priceIndicators.filter((item) => item.direction === "bearish").length;
  const volumeBullish = volumeIndicators.filter((item) => item.direction === "bullish").length;
  const volumeBearish = volumeIndicators.filter((item) => item.direction === "bearish").length;
  const priceDirection = Math.sign(priceBullish - priceBearish);
  const volumeDirection = Math.sign(volumeBullish - volumeBearish);
  const priceVolumeAligned = priceDirection !== 0 && priceDirection === volumeDirection;
  const priceVolumeConflict = priceDirection !== 0 && volumeDirection !== 0 && priceDirection !== volumeDirection;
  if (priceVolumeAligned) score += priceDirection;
  if (priceVolumeConflict && score !== 0) score -= Math.sign(score);
  const indicatorSummary = priceVolumeAligned
    ? `價指標與量指標同步${priceDirection > 0 ? "偏多" : "偏空"}，獲得價量共振確認`
    : priceVolumeConflict
      ? "價指標與量指標方向背離，已自動降低權重"
      : "價量方向尚未形成一致確認";
  const breadthBullish = breadthIndicators.filter((item) => item.direction === "bullish").length;
  const breadthBearish = breadthIndicators.filter((item) => item.direction === "bearish").length;
  const breadthDirection = Math.sign(breadthBullish - breadthBearish);
  const technicalDirection = Math.sign(priceDirection + volumeDirection);
  const breadthAligned = breadthDirection !== 0 && technicalDirection !== 0 && breadthDirection === technicalDirection;
  const breadthConflict = breadthDirection !== 0 && technicalDirection !== 0 && breadthDirection !== technicalDirection;
  if (breadthAligned) score += breadthDirection;
  if (breadthConflict && score !== 0) score -= Math.sign(score);
  const breadthSummary = breadthAligned
    ? `市場廣度、心理與籌碼綜合${breadthDirection > 0 ? "偏多" : "偏空"}，並與價量方向一致`
    : breadthConflict
      ? "市場廣度／籌碼與價量技術方向衝突，已降低權重"
      : "市場廣度、心理與籌碼訊號尚未形成一致方向";

  const bullishTheories = theorySignals.filter((item) => item.direction === "bullish").length;
  const bearishTheories = theorySignals.filter((item) => item.direction === "bearish").length;
  const agreement = Math.max(bullishTheories, bearishTheories) / Math.max(bullishTheories + bearishTheories, 1);
  const conflictPenalty = Math.min(bullishTheories, bearishTheories) >= 3 ? 2 : 0;
  score -= Math.sign(score) * conflictPenalty;
  const theoryDirection = Math.sign(bullishTheories - bearishTheories);
  const scoreDirectionConflict = score !== 0 && theoryDirection !== 0 && Math.sign(score) !== theoryDirection;
  const adaptiveConfidence = scoreDirectionConflict || priceVolumeConflict || breadthConflict
    ? "低"
    : evidenceCount >= 16 && agreement >= 0.7
    ? "高"
    : evidenceCount >= 10 && agreement >= 0.55
      ? "中"
      : "低";
  const directionSummary = bullishTheories > bearishTheories
    ? `${bullishTheories} 項偏多、${bearishTheories} 項偏空`
    : bearishTheories > bullishTheories
      ? `${bearishTheories} 項偏空、${bullishTheories} 項偏多`
      : "多空理論數量接近";
  const adaptiveSummary = [
    directionSummary,
    backtestLearning.summary,
    scoreDirectionConflict ? "型態與綜合指標方向衝突，已自動降低信心" : "",
    indicatorSummary,
    breadthSummary,
  ].filter(Boolean).join("；");

  return {
    score: Math.max(-18, Math.min(18, score)),
    evidenceCount,
    patterns: patterns.slice(0, 14),
    indicators,
    priceIndicators,
    volumeIndicators,
    breadthIndicators,
    indicatorSummary,
    breadthSummary,
    priceVolumeAligned,
    priceVolumeConflict,
    breadthAligned,
    breadthConflict,
    theorySignals,
    adaptiveConfidence,
    adaptiveSummary,
    backtestLearning,
  };
}
function movingAverage(values, windowSize) {
  return values.map((_, index) => {
    const slice = values.slice(Math.max(0, index - windowSize + 1), index + 1).filter((value) => value !== null);
    if (slice.length < Math.min(windowSize, index + 1)) return null;
    return slice.reduce((sum, value) => sum + value, 0) / slice.length;
  });
}
function buildGlobalMarketDetail(item) {
  const historyDays = (item.series || []).map((day) => {
    const open = parseMarketNumber(day.open);
    const high = parseMarketNumber(day.high);
    const low = parseMarketNumber(day.low);
    const close = parseMarketNumber(day.close);
    const volume = parseMarketNumber(day.volumeValue ?? day.volume);
    return {
      date: day.date || day.time || "",
      open: Number.isFinite(open) ? open : close,
      high: Number.isFinite(high) ? high : close,
      low: Number.isFinite(low) ? low : close,
      close,
      change: null,
      volume: Number.isFinite(volume) ? volume : 0,
    };
  }).filter((day) => day.date && Number.isFinite(day.close));
  const closes = historyDays.map((day) => day.close);
  const latest = historyDays.at(-1) || {};
  const maValue = (period) => technicalSma(closes, period).at(-1);
  return {
    code: item.symbol || "",
    name: item.name || item.symbol || "",
    market: "US",
    isEtf: String(item.group || item.type || "").toUpperCase().includes("ETF"),
    snapshotDate: item.date || latest.date || "",
    currentPrice: item.close,
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
    volume: item.volume,
    change: item.change,
    pct: item.pct,
    ma5: maValue(5),
    ma20: maValue(20),
    ma60: maValue(60),
    ma120: maValue(120),
    ma240: maValue(240),
    historyDays,
    historyCount: historyDays.length,
    historyStartDate: historyDays[0]?.date || "",
    historyEndDate: latest.date || "",
    chartIntervals: { supported: ["day", "week", "month"], intradayAvailable: false },
  };
}
function averageFuturesValues(values) {
  const cleanValues = values.filter(Number.isFinite);
  return cleanValues.length ? cleanValues.reduce((sum, value) => sum + value, 0) / cleanValues.length : null;
}
function lastFiniteFuturesValue(values = []) {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    const value = parseMarketNumber(values[index]);
    if (Number.isFinite(value)) return value;
  }
  return null;
}
function calculateFuturesEmaSeries(values = [], period = 12) {
  const cleanValues = values.map((value) => parseMarketNumber(value));
  const result = Array(cleanValues.length).fill(null);
  if (cleanValues.length < period) return result;
  const seed = cleanValues.slice(0, period);
  if (!seed.every(Number.isFinite)) return result;
  let ema = averageFuturesValues(seed);
  result[period - 1] = ema;
  const weight = 2 / (period + 1);
  for (let index = period; index < cleanValues.length; index += 1) {
    const value = cleanValues[index];
    if (!Number.isFinite(value)) continue;
    ema = value * weight + ema * (1 - weight);
    result[index] = ema;
  }
  return result;
}
function calculateFuturesRollingAverageSeries(values = [], period = 5) {
  const cleanValues = values.map((value) => parseMarketNumber(value));
  return cleanValues.map((_, index) => {
    if (index + 1 < period) return null;
    const windowValues = cleanValues.slice(index - period + 1, index + 1);
    return windowValues.every(Number.isFinite) ? averageFuturesValues(windowValues) : null;
  });
}
function calculateFuturesRsiSeries(closes = [], period = 14) {
  const cleanCloses = closes.map((value) => parseMarketNumber(value));
  return cleanCloses.map((_, index) => {
    if (index <= period) return null;
    return calculateFuturesRsi(cleanCloses.slice(0, index + 1), period);
  });
}
function calculateFuturesKdSeries(rows = [], period = 9) {
  const kValues = Array(rows.length).fill(null);
  const dValues = Array(rows.length).fill(null);
  let k = 50;
  let d = 50;
  for (let index = period - 1; index < rows.length; index += 1) {
    const windowRows = rows.slice(index - period + 1, index + 1);
    const high = Math.max(...windowRows.map((row) => row.high).filter(Number.isFinite));
    const low = Math.min(...windowRows.map((row) => row.low).filter(Number.isFinite));
    const close = rows[index]?.close;
    if (!Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close) || high === low) continue;
    const rsv = ((close - low) / (high - low)) * 100;
    k = (2 / 3) * k + (1 / 3) * rsv;
    d = (2 / 3) * d + (1 / 3) * k;
    kValues[index] = k;
    dValues[index] = d;
  }
  return { k: kValues, d: dValues };
}
function calculateFuturesVwapSeries(rows = [], period = 40) {
  return rows.map((_, index) => {
    const windowRows = rows.slice(Math.max(0, index - period + 1), index + 1);
    const numerator = windowRows.reduce((sum, row) => sum + ((row.high + row.low + row.close) / 3) * (row.volume || 0), 0);
    const denominator = windowRows.reduce((sum, row) => sum + (row.volume || 0), 0);
    return denominator ? numerator / denominator : null;
  });
}
function calculateFuturesObvSeries(rows = []) {
  let obv = 0;
  return rows.map((row, index) => {
    if (index === 0) return 0;
    const previous = rows[index - 1];
    obv += row.close > previous.close ? row.volume || 0 : row.close < previous.close ? -(row.volume || 0) : 0;
    return obv;
  });
}
function calculateFuturesMfi(rows = [], period = 14) {
  const windowRows = rows.slice(-(period + 1));
  if (windowRows.length <= period) return null;
  let positiveFlow = 0;
  let negativeFlow = 0;
  for (let index = 1; index < windowRows.length; index += 1) {
    const currentTypical = (windowRows[index].high + windowRows[index].low + windowRows[index].close) / 3;
    const previousTypical = (windowRows[index - 1].high + windowRows[index - 1].low + windowRows[index - 1].close) / 3;
    const flow = currentTypical * (windowRows[index].volume || 0);
    if (currentTypical >= previousTypical) positiveFlow += flow;
    else negativeFlow += flow;
  }
  return negativeFlow ? 100 - (100 / (1 + positiveFlow / negativeFlow)) : (positiveFlow ? 100 : null);
}
function calculateFuturesRollingIndicatorSeries(rows = [], minRows = 2, resolver = () => null) {
  return rows.map((_, index) => (index + 1 >= minRows ? resolver(rows.slice(0, index + 1)) : null));
}
function calculateFuturesRsi(closes = [], period = 14) {
  if (closes.length <= period) return null;
  const changes = closes.slice(1).map((value, index) => value - closes[index]);
  const recent = changes.slice(-period);
  const gains = recent.map((value) => Math.max(value, 0));
  const losses = recent.map((value) => Math.max(-value, 0));
  const avgGain = averageFuturesValues(gains);
  const avgLoss = averageFuturesValues(losses);
  if (!Number.isFinite(avgGain) || !Number.isFinite(avgLoss)) return null;
  if (avgLoss === 0) return 100;
  return 100 - (100 / (1 + avgGain / avgLoss));
}
function calculateFuturesKd(rows = [], period = 9) {
  if (rows.length < period) return { k: null, d: null };
  let k = 50;
  let d = 50;
  for (let index = period - 1; index < rows.length; index += 1) {
    const windowRows = rows.slice(index - period + 1, index + 1);
    const high = Math.max(...windowRows.map((row) => row.high).filter(Number.isFinite));
    const low = Math.min(...windowRows.map((row) => row.low).filter(Number.isFinite));
    const close = rows[index]?.close;
    if (!Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close) || high === low) continue;
    const rsv = ((close - low) / (high - low)) * 100;
    k = (2 / 3) * k + (1 / 3) * rsv;
    d = (2 / 3) * d + (1 / 3) * k;
  }
  return { k, d };
}
function calculateFuturesAtr(rows = [], period = 14) {
  if (rows.length <= period) return null;
  const ranges = rows.slice(1).map((row, index) => {
    const previousClose = rows[index]?.close;
    if (![row.high, row.low, previousClose].every(Number.isFinite)) return null;
    return Math.max(row.high - row.low, Math.abs(row.high - previousClose), Math.abs(row.low - previousClose));
  }).filter(Number.isFinite);
  return averageFuturesValues(ranges.slice(-period));
}
function calculateFuturesCci(rows = [], period = 20) {
  if (rows.length < period) return null;
  const windowRows = rows.slice(-period);
  const typicalPrices = windowRows.map((row) => (row.high + row.low + row.close) / 3).filter(Number.isFinite);
  if (typicalPrices.length < period) return null;
  const mean = averageFuturesValues(typicalPrices);
  const meanDeviation = averageFuturesValues(typicalPrices.map((value) => Math.abs(value - mean)));
  const latest = typicalPrices.at(-1);
  return meanDeviation ? (latest - mean) / (0.015 * meanDeviation) : null;
}
function calculateFuturesWilliamsR(rows = [], period = 14) {
  if (rows.length < period) return null;
  const windowRows = rows.slice(-period);
  const high = Math.max(...windowRows.map((row) => row.high).filter(Number.isFinite));
  const low = Math.min(...windowRows.map((row) => row.low).filter(Number.isFinite));
  const close = windowRows.at(-1)?.close;
  return high !== low && Number.isFinite(close) ? ((high - close) / (high - low)) * -100 : null;
}
function calculateFuturesDmiAdx(rows = [], period = 14) {
  if (rows.length <= period * 2) return { plusDi: null, minusDi: null, adx: null };
  const points = [];
  for (let index = 1; index < rows.length; index += 1) {
    const current = rows[index];
    const previous = rows[index - 1];
    const upMove = current.high - previous.high;
    const downMove = previous.low - current.low;
    const plusDm = upMove > downMove && upMove > 0 ? upMove : 0;
    const minusDm = downMove > upMove && downMove > 0 ? downMove : 0;
    const tr = Math.max(current.high - current.low, Math.abs(current.high - previous.close), Math.abs(current.low - previous.close));
    points.push({ plusDm, minusDm, tr });
  }
  const recent = points.slice(-period);
  const trSum = recent.reduce((sum, row) => sum + row.tr, 0);
  if (!trSum) return { plusDi: null, minusDi: null, adx: null };
  const plusDi = recent.reduce((sum, row) => sum + row.plusDm, 0) / trSum * 100;
  const minusDi = recent.reduce((sum, row) => sum + row.minusDm, 0) / trSum * 100;
  const dxRows = points.slice(-period * 2).map((_, index, array) => {
    const windowRows = array.slice(Math.max(0, index - period + 1), index + 1);
    const windowTr = windowRows.reduce((sum, row) => sum + row.tr, 0);
    if (!windowTr) return null;
    const windowPlus = windowRows.reduce((sum, row) => sum + row.plusDm, 0) / windowTr * 100;
    const windowMinus = windowRows.reduce((sum, row) => sum + row.minusDm, 0) / windowTr * 100;
    return (Math.abs(windowPlus - windowMinus) / Math.max(windowPlus + windowMinus, 1)) * 100;
  }).filter(Number.isFinite);
  return { plusDi, minusDi, adx: averageFuturesValues(dxRows.slice(-period)) };
}
function calculateFuturesParabolicSar(rows = []) {
  if (rows.length < 4) return null;
  let bullish = rows[1].close >= rows[0].close;
  let sar = bullish ? rows[0].low : rows[0].high;
  let extreme = bullish ? rows[1].high : rows[1].low;
  let acceleration = 0.02;
  for (let index = 2; index < rows.length; index += 1) {
    const row = rows[index];
    sar += acceleration * (extreme - sar);
    if (bullish) {
      if (row.low < sar) {
        bullish = false;
        sar = extreme;
        extreme = row.low;
        acceleration = 0.02;
      } else if (row.high > extreme) {
        extreme = row.high;
        acceleration = Math.min(acceleration + 0.02, 0.2);
      }
    } else if (row.high > sar) {
      bullish = true;
      sar = extreme;
      extreme = row.high;
      acceleration = 0.02;
    } else if (row.low < extreme) {
      extreme = row.low;
      acceleration = Math.min(acceleration + 0.02, 0.2);
    }
  }
  return sar;
}
function buildFuturesTechnicalSnapshot(rows = []) {
  const cleanRows = rows.filter((row) => [row.open, row.high, row.low, row.close].every(Number.isFinite));
  const closes = cleanRows.map((row) => row.close);
  const highs = cleanRows.map((row) => row.high);
  const lows = cleanRows.map((row) => row.low);
  const volumes = cleanRows.map((row) => row.volume || 0);
  const latest = cleanRows.at(-1) || {};
  const maSeries = Object.fromEntries([5, 10, 20, 60, 120, 240].map((period) => [period, calculateFuturesRollingAverageSeries(closes, period)]));
  const ma = Object.fromEntries([5, 10, 20, 60, 120, 240].map((period) => [period, lastFiniteFuturesValue(maSeries[period])]));
  const ema12 = calculateFuturesEmaSeries(closes, 12);
  const ema26 = calculateFuturesEmaSeries(closes, 26);
  const macdRaw = closes.map((_, index) => (
    Number.isFinite(ema12[index]) && Number.isFinite(ema26[index]) ? ema12[index] - ema26[index] : null
  ));
  const macdRows = macdRaw.filter(Number.isFinite);
  const macdSignalRows = calculateFuturesEmaSeries(macdRows, 9);
  const macdHistogramRows = macdRows.map((value, index) => (
    Number.isFinite(value) && Number.isFinite(macdSignalRows[index]) ? value - macdSignalRows[index] : null
  ));
  const macd = lastFiniteFuturesValue(macdRows);
  const macdSignal = lastFiniteFuturesValue(macdSignalRows);
  const kdSeries = calculateFuturesKdSeries(cleanRows);
  const kd = { k: lastFiniteFuturesValue(kdSeries.k), d: lastFiniteFuturesValue(kdSeries.d) };
  const atrSeries = calculateFuturesRollingIndicatorSeries(cleanRows, 15, (windowRows) => calculateFuturesAtr(windowRows));
  const atr = calculateFuturesAtr(cleanRows);
  const cciSeries = calculateFuturesRollingIndicatorSeries(cleanRows, 20, (windowRows) => calculateFuturesCci(windowRows));
  const cci = calculateFuturesCci(cleanRows);
  const williamsRSeries = calculateFuturesRollingIndicatorSeries(cleanRows, 14, (windowRows) => calculateFuturesWilliamsR(windowRows));
  const williamsR = calculateFuturesWilliamsR(cleanRows);
  const dmi = calculateFuturesDmiAdx(cleanRows);
  const rsiSeries = calculateFuturesRsiSeries(closes);
  const rsi = lastFiniteFuturesValue(rsiSeries);
  const momentumSeries = closes.map((close, index) => (index >= 10 && Number.isFinite(close) && Number.isFinite(closes[index - 10]) ? close - closes[index - 10] : null));
  const momentum = lastFiniteFuturesValue(momentumSeries);
  const bias20Series = closes.map((close, index) => {
    const base = maSeries[20]?.[index];
    return Number.isFinite(close) && Number.isFinite(base) && base !== 0 ? ((close - base) / base) * 100 : null;
  });
  const bias20 = lastFiniteFuturesValue(bias20Series);
  const bollingerMid = ma[20];
  const bollingerSd = closes.length >= 20 ? Math.sqrt(averageFuturesValues(closes.slice(-20).map((value) => (value - bollingerMid) ** 2))) : null;
  const obvSeries = calculateFuturesObvSeries(cleanRows);
  const obv = lastFiniteFuturesValue(obvSeries);
  const mfiSeries = calculateFuturesRollingIndicatorSeries(cleanRows, 15, (windowRows) => calculateFuturesMfi(windowRows));
  const mfi = lastFiniteFuturesValue(mfiSeries);
  const vwapSeries = calculateFuturesVwapSeries(cleanRows);
  const vwapNumerator = cleanRows.slice(-40).reduce((sum, row) => sum + ((row.high + row.low + row.close) / 3) * (row.volume || 0), 0);
  const vwapDenominator = cleanRows.slice(-40).reduce((sum, row) => sum + (row.volume || 0), 0);
  const support20 = lows.length ? Math.min(...lows.slice(-20)) : null;
  const resistance20 = highs.length ? Math.max(...highs.slice(-20)) : null;
  const high60 = highs.length ? Math.max(...highs.slice(-60)) : null;
  const low60 = lows.length ? Math.min(...lows.slice(-60)) : null;
  const fib38 = Number.isFinite(high60) && Number.isFinite(low60) ? high60 - (high60 - low60) * 0.382 : null;
  const fib62 = Number.isFinite(high60) && Number.isFinite(low60) ? high60 - (high60 - low60) * 0.618 : null;
  const tenkan = highs.length >= 9 && lows.length >= 9 ? (Math.max(...highs.slice(-9)) + Math.min(...lows.slice(-9))) / 2 : null;
  const kijun = highs.length >= 26 && lows.length >= 26 ? (Math.max(...highs.slice(-26)) + Math.min(...lows.slice(-26))) / 2 : null;
  const senkouB = highs.length >= 52 && lows.length >= 52 ? (Math.max(...highs.slice(-52)) + Math.min(...lows.slice(-52))) / 2 : null;
  const openInterestSeries = cleanRows.map((row) => parseMarketNumber(row.openInterest));
  const openInterest = openInterestSeries.filter(Number.isFinite);
  const oiChange = openInterest.length >= 2 ? openInterest.at(-1) - openInterest.at(-2) : null;
  const oiChangeSeries = openInterestSeries.map((value, index) => (
    index > 0 && Number.isFinite(value) && Number.isFinite(openInterestSeries[index - 1]) ? value - openInterestSeries[index - 1] : null
  ));
  const buckets = [];
  if (Number.isFinite(high60) && Number.isFinite(low60) && high60 !== low60) {
    const bucketCount = 6;
    for (let index = 0; index < bucketCount; index += 1) buckets.push({ volume: 0, low: low60 + ((high60 - low60) / bucketCount) * index, high: low60 + ((high60 - low60) / bucketCount) * (index + 1) });
    cleanRows.slice(-60).forEach((row) => {
      const bucketIndex = Math.min(bucketCount - 1, Math.max(0, Math.floor(((row.close - low60) / (high60 - low60)) * bucketCount)));
      buckets[bucketIndex].volume += row.volume || 0;
    });
  }
  const pointOfControl = buckets.length ? buckets.slice().sort((left, right) => right.volume - left.volume)[0] : null;
  const deltaVolumeSeries = cleanRows.map((row) => (row.close >= row.open ? row.volume || 0 : -(row.volume || 0)));
  const deltaVolume = deltaVolumeSeries.slice(-20).reduce((sum, value) => sum + value, 0);
  return {
    ma,
    macd,
    macdSignal,
    rsi,
    kd,
    atr,
    cci,
    williamsR,
    dmi,
    bias20,
    momentum,
    bollinger: {
      mid: bollingerMid,
      upper: Number.isFinite(bollingerMid) && Number.isFinite(bollingerSd) ? bollingerMid + bollingerSd * 2 : null,
      lower: Number.isFinite(bollingerMid) && Number.isFinite(bollingerSd) ? bollingerMid - bollingerSd * 2 : null,
    },
    obv,
    mfi,
    sar: calculateFuturesParabolicSar(cleanRows),
    ichimoku: { tenkan, kijun, senkouB },
    support20,
    resistance20,
    fib38,
    fib62,
    vwap: vwapDenominator ? vwapNumerator / vwapDenominator : null,
    pointOfControl,
    deltaVolume,
    openInterest: openInterest.at(-1),
    oiChange,
    count: cleanRows.length,
    series: {
      close: closes,
      volume: volumes,
      ma: maSeries,
      macd: {
        dif: macdRows,
        signal: macdSignalRows,
        histogram: macdHistogramRows,
      },
      rsi: rsiSeries,
      kd: kdSeries,
      atr: atrSeries,
      cci: cciSeries,
      williamsR: williamsRSeries,
      bias20: bias20Series,
      momentum: momentumSeries,
      obv: obvSeries,
      mfi: mfiSeries,
      vwap: vwapSeries,
      deltaVolume: deltaVolumeSeries,
      openInterest: openInterestSeries,
      oiChange: oiChangeSeries,
      support20: Array(closes.length).fill(support20),
      resistance20: Array(closes.length).fill(resistance20),
      fib38: Array(closes.length).fill(fib38),
      fib62: Array(closes.length).fill(fib62),
    },
  };
}
function parseRocDate(value) {
  const str = String(value || "").trim();
  // ISO format: YYYY-MM-DD (e.g. "2026-05-27")
  const isoMatch = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const d = new Date(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3]));
    return Number.isNaN(d.getTime()) ? null : d;
  }
  // ISO week format from futures aggregation: YYYY-WNN.
  const weekMatch = str.match(/^(\d{4})-W(\d{2})$/i);
  if (weekMatch) {
    const year = Number(weekMatch[1]);
    const week = Number(weekMatch[2]);
    if (!Number.isFinite(year) || !Number.isFinite(week) || week < 1 || week > 53) return null;
    const jan4 = new Date(year, 0, 4);
    const weekStart = new Date(jan4);
    weekStart.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7) + (week - 1) * 7);
    return Number.isNaN(weekStart.getTime()) ? null : weekStart;
  }
  // Month format from futures aggregation: YYYY-MM.
  const monthMatch = str.match(/^(\d{4})-(\d{2})$/);
  if (monthMatch) {
    const d = new Date(Number(monthMatch[1]), Number(monthMatch[2]) - 1, 1);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  // ROC format: YYY/MM/DD (e.g. "115/06/09")
  const parts = str.split("/").map((part) => Number(part));
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) return null;
  // Guard: if first part looks like a 4-digit western year, treat as western
  const year = parts[0] > 1900 ? parts[0] : parts[0] + 1911;
  const d = new Date(year, parts[1] - 1, parts[2]);
  return Number.isNaN(d.getTime()) ? null : d;
}
function isValidTechnicalOhlc(open, high, low, close) {
  const values = [open, high, low, close];
  if (!values.every((value) => Number.isFinite(value) && value > 0)) return false;
  return high >= Math.max(open, close) && low <= Math.min(open, close);
}
function normalizeHistory(detail) {
  return (detail.historyDays || [])
    .map((day) => {
      const close = parseMarketNumber(day.close);
      const open = parseMarketNumber(day.open);
      const rawHigh = parseMarketNumber(day.high);
      const rawLow = parseMarketNumber(day.low);
      if (!isValidTechnicalOhlc(open, rawHigh, rawLow, close)) return null;
      return {
        date: day.date,
        parsedDate: parseRocDate(day.date),
        open,
        high: rawHigh,
        low: rawLow,
        close,
        change: parseMarketNumber(day.change),
        volume: Math.max(parseMarketNumber(day.volume) || 0, 0),
      };
    })
    .filter((day) => day && day.parsedDate !== null);
}
function exponentialMovingAverage(values, windowSize) {
  const multiplier = 2 / (windowSize + 1);
  let previous = null;
  return values.map((value, index) => {
    if (value === null) return null;
    if (previous === null) {
      const slice = values.slice(Math.max(0, index - windowSize + 1), index + 1).filter((item) => item !== null);
      previous = slice.reduce((sum, item) => sum + item, 0) / slice.length;
      return previous;
    }
    previous = (value - previous) * multiplier + previous;
    return previous;
  });
}
function calculateKd(history, period = 9) {
  let k = 50;
  let d = 50;
  return history.map((day, index) => {
    const slice = history.slice(Math.max(0, index - period + 1), index + 1);
    const high = Math.max(...slice.map((item) => item.high ?? item.close));
    const low = Math.min(...slice.map((item) => item.low ?? item.close));
    const rsv = high === low ? 50 : ((day.close - low) / (high - low)) * 100;
    k = (k * 2 + rsv) / 3;
    d = (d * 2 + k) / 3;
    return { k, d };
  });
}
function calculateMacd(history) {
  const closes = history.map((day) => day.close);
  const ema12 = exponentialMovingAverage(closes, 12);
  const ema26 = exponentialMovingAverage(closes, 26);
  const dif = closes.map((_, index) => (
    ema12[index] === null || ema26[index] === null ? null : ema12[index] - ema26[index]
  ));
  const macd = exponentialMovingAverage(dif, 9);
  return dif.map((value, index) => ({
    dif: value,
    macd: macd[index],
    osc: value === null || macd[index] === null ? null : (value - macd[index]) * 2,
  }));
}
function calculateRsi(history, period = 14) {
  return history.map((day, index) => {
    if (index === 0) return null;
    const start = Math.max(1, index - period + 1);
    const changes = history.slice(start, index + 1).map((item, itemIndex, items) => {
      const previousIndex = start + itemIndex - 1;
      const previous = history[previousIndex]?.close ?? items[itemIndex - 1]?.close ?? item.close;
      return item.close - previous;
    });
    const gains = changes.map((change) => Math.max(change, 0));
    const losses = changes.map((change) => Math.abs(Math.min(change, 0)));
    const averageGain = gains.reduce((sum, value) => sum + value, 0) / changes.length;
    const averageLoss = losses.reduce((sum, value) => sum + value, 0) / changes.length;
    if (averageLoss === 0) return 100;
    const rs = averageGain / averageLoss;
    return 100 - (100 / (1 + rs));
  });
}
function calculateBias(history, period = 6) {
  const closes = history.map((day) => day.close);
  const ma = movingAverage(closes, period);
  return closes.map((close, index) => (
    ma[index] === null || ma[index] === 0 ? null : ((close - ma[index]) / ma[index]) * 100
  ));
}
function calculateDmi(history, period = 14) {
  let smoothedTr = 0;
  let smoothedPlusDm = 0;
  let smoothedMinusDm = 0;
  let adx = null;
  const dxValues = [];

  return history.map((day, index) => {
    if (index === 0) return { plusDi: null, minusDi: null, adx: null };
    const previous = history[index - 1];
    const high = day.high ?? day.close;
    const low = day.low ?? day.close;
    const previousHigh = previous.high ?? previous.close;
    const previousLow = previous.low ?? previous.close;
    const trueRange = Math.max(
      high - low,
      Math.abs(high - previous.close),
      Math.abs(low - previous.close),
    );
    const upMove = high - previousHigh;
    const downMove = previousLow - low;
    const plusDm = upMove > downMove && upMove > 0 ? upMove : 0;
    const minusDm = downMove > upMove && downMove > 0 ? downMove : 0;

    if (index <= period) {
      smoothedTr += trueRange;
      smoothedPlusDm += plusDm;
      smoothedMinusDm += minusDm;
    } else {
      smoothedTr = smoothedTr - smoothedTr / period + trueRange;
      smoothedPlusDm = smoothedPlusDm - smoothedPlusDm / period + plusDm;
      smoothedMinusDm = smoothedMinusDm - smoothedMinusDm / period + minusDm;
    }
    if (index < period || smoothedTr === 0) {
      return { plusDi: null, minusDi: null, adx: null };
    }

    const plusDi = (smoothedPlusDm / smoothedTr) * 100;
    const minusDi = (smoothedMinusDm / smoothedTr) * 100;
    const denominator = plusDi + minusDi;
    const dx = denominator === 0 ? 0 : (Math.abs(plusDi - minusDi) / denominator) * 100;
    dxValues.push(dx);
    if (dxValues.length === period) {
      adx = dxValues.reduce((sum, value) => sum + value, 0) / period;
    } else if (dxValues.length > period && adx !== null) {
      adx = ((adx * (period - 1)) + dx) / period;
    }
    return { plusDi, minusDi, adx };
  });
}
function calculateObv(history) {
  let obv = 0;
  return history.map((day, index) => {
    if (index > 0) {
      if (day.close > history[index - 1].close) obv += day.volume || 0;
      if (day.close < history[index - 1].close) obv -= day.volume || 0;
    }
    return obv;
  });
}
function calculateAtr(history, period = 14) {
  const ranges = history.map((day, index) => {
    if (index === 0) return null;
    const previous = history[index - 1];
    const high = day.high ?? day.close;
    const low = day.low ?? day.close;
    return Math.max(high - low, Math.abs(high - previous.close), Math.abs(low - previous.close));
  });
  return ranges.map((_, index) => {
    if (index < period) return null;
    const window = ranges.slice(index - period + 1, index + 1).filter(Number.isFinite);
    return window.length === period ? window.reduce((sum, value) => sum + value, 0) / period : null;
  });
}
function calculateCci(history, period = 20) {
  const typicalPrices = history.map((day) => ((day.high ?? day.close) + (day.low ?? day.close) + day.close) / 3);
  return typicalPrices.map((typical, index) => {
    if (index + 1 < period) return null;
    const window = typicalPrices.slice(index - period + 1, index + 1).filter(Number.isFinite);
    if (window.length < period) return null;
    const average = window.reduce((sum, value) => sum + value, 0) / period;
    const meanDeviation = window.reduce((sum, value) => sum + Math.abs(value - average), 0) / period;
    return meanDeviation ? (typical - average) / (0.015 * meanDeviation) : null;
  });
}
function calculateWilliamsR(history, period = 14) {
  return history.map((day, index) => {
    if (index + 1 < period) return null;
    const window = history.slice(index - period + 1, index + 1);
    const highest = Math.max(...window.map((item) => item.high ?? item.close).filter(Number.isFinite));
    const lowest = Math.min(...window.map((item) => item.low ?? item.close).filter(Number.isFinite));
    return highest !== lowest ? ((highest - day.close) / (highest - lowest)) * -100 : null;
  });
}
function calculateMfi(history, period = 14) {
  const typicalPrices = history.map((day) => ((day.high ?? day.close) + (day.low ?? day.close) + day.close) / 3);
  const flows = history.map((day, index) => ({
    typical: typicalPrices[index],
    flow: typicalPrices[index] * (day.volume || 0),
  }));
  return flows.map((row, index) => {
    if (index < period) return null;
    let positiveFlow = 0;
    let negativeFlow = 0;
    for (let cursor = index - period + 1; cursor <= index; cursor += 1) {
      const current = flows[cursor];
      const previous = flows[cursor - 1];
      if (!current || !previous) continue;
      if (current.typical >= previous.typical) positiveFlow += current.flow;
      else negativeFlow += current.flow;
    }
    if (!negativeFlow) return positiveFlow ? 100 : null;
    return 100 - (100 / (1 + positiveFlow / negativeFlow));
  });
}
function calculateMomentum(history, period = 10) {
  return history.map((day, index) => (
    index >= period && Number.isFinite(history[index - period]?.close) ? day.close - history[index - period].close : null
  ));
}
function calculateParabolicSarSeries(history) {
  const result = Array(history.length).fill(null);
  if (history.length < 4) return result;
  let bullish = history[1].close >= history[0].close;
  let sar = bullish ? history[0].low : history[0].high;
  let extreme = bullish ? history[1].high : history[1].low;
  let acceleration = 0.02;
  result[1] = sar;
  for (let index = 2; index < history.length; index += 1) {
    const row = history[index];
    sar += acceleration * (extreme - sar);
    if (bullish) {
      if (row.low < sar) {
        bullish = false;
        sar = extreme;
        extreme = row.low;
        acceleration = 0.02;
      } else if (row.high > extreme) {
        extreme = row.high;
        acceleration = Math.min(acceleration + 0.02, 0.2);
      }
    } else if (row.high > sar) {
      bullish = true;
      sar = extreme;
      extreme = row.high;
      acceleration = 0.02;
    } else if (row.low < extreme) {
      extreme = row.low;
      acceleration = Math.min(acceleration + 0.02, 0.2);
    }
    result[index] = sar;
  }
  return result;
}
function calculateIchimoku(history) {
  const midpoint = (window) => {
    const highs = window.map((item) => item.high ?? item.close).filter(Number.isFinite);
    const lows = window.map((item) => item.low ?? item.close).filter(Number.isFinite);
    return highs.length && lows.length ? (Math.max(...highs) + Math.min(...lows)) / 2 : null;
  };
  return history.map((_, index) => {
    const tenkan = index + 1 >= 9 ? midpoint(history.slice(index - 8, index + 1)) : null;
    const kijun = index + 1 >= 26 ? midpoint(history.slice(index - 25, index + 1)) : null;
    const senkouB = index + 1 >= 52 ? midpoint(history.slice(index - 51, index + 1)) : null;
    return { tenkan, kijun, senkouB };
  });
}

// Phase D: reuse market-specific payloads and expose one fail-closed contract.
// This layer only normalizes existing evidence; it does not create a forecast,
// score, risk score, or provider path.
(function registerCrossMarketDecisionLayer() {
  const CROSS_MARKET_INPUT_DEFINITIONS = [
    { key: "TW", label: "TW", payloadKey: "tw", symbols: [] },
    { key: "US", label: "US", payloadKey: "us-stocks", symbols: ["^GSPC", "^IXIC", "^DJI", "^RUT"] },
    { key: "ETF", label: "ETF", payloadKey: "us-etf", symbols: ["SPY", "QQQ", "VOO", "IVV"] },
    { key: "Futures", label: "Futures", payloadKey: "futures", symbols: ["ES=F", "NQ=F", "TX", "YM=F"] },
    { key: "Options", label: "Options", payloadKey: "options", symbols: ["TXO", "^GSPC", "^NDX", "^DJI"] },
    { key: "VIX", label: "VIX", payloadKey: "us-stocks", symbols: ["^VIX", "VIXY", "VXX"], kind: "volatility" },
    { key: "DXY", label: "DXY", payloadKeys: ["bonds", "precious-metals"], symbols: ["DX-Y.NYB", "DXY"] },
    { key: "US10Y", label: "US10Y", payloadKey: "bonds", symbols: ["^TNX", "ZN=F", "US10Y"], maturity: "10 Yr" },
    { key: "Gold", label: "Gold", payloadKey: "precious-metals", symbols: ["GC=F", "MGC=F", "GLD", "IAU", "GLDM"] },
  ];

  function crossMarketNumber(value) {
    if (typeof parseMarketNumber === "function") return parseMarketNumber(value);
    const parsed = Number.parseFloat(String(value ?? "").replace(/,/g, "").replace(/%/g, ""));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function crossMarketPayloadMap(payloads) {
    if (Array.isArray(payloads)) return new Map(payloads.filter(Boolean).map((payload) => [payload.category, payload]));
    if (payloads && typeof payloads === "object") return new Map(Object.entries(payloads).filter(([, payload]) => payload));
    return new Map();
  }

  function crossMarketItems(payload) {
    return Array.isArray(payload?.items) ? payload.items : [];
  }

  function crossMarketFindItem(payloads, definition) {
    const maps = (definition.payloadKeys || [definition.payloadKey])
      .map((key) => payloads.get(key))
      .filter(Boolean);
    for (const payload of maps) {
      const items = crossMarketItems(payload);
      const found = definition.symbols
        .map((symbol) => items.find((item) => String(item?.symbol || "").toUpperCase() === symbol))
        .find(Boolean);
      if (found) return { payload, item: found };
    }
    return { payload: maps[0] || null, item: null };
  }

  function crossMarketTwEvidence(payload) {
    const overview = Array.isArray(payload?.marketOverview) ? payload.marketOverview : [];
    const item = overview.find((entry) => crossMarketNumber(entry?.pct) !== null || crossMarketNumber(entry?.value) !== null) || null;
    return {
      item,
      value: item?.value ?? null,
      pct: item?.pct ?? null,
      date: payload?.snapshotDate || payload?.activityDate || null,
      source: payload?.sourceLinks?.market || "TWSE / TPEX existing market overview",
    };
  }

  function crossMarketOptionsEvidence(payload) {
    const chain = payload?.taiwanOptionChain || {};
    const analysis = chain.analysis && typeof chain.analysis === "object" ? chain.analysis : {};
    const direction = String(analysis.direction || analysis.regime?.direction || "").trim();
    const item = crossMarketItems(payload).find((entry) => !entry?.error && (crossMarketNumber(entry?.close) !== null || crossMarketNumber(entry?.pct) !== null)) || null;
    return {
      item,
      value: item?.close ?? analysis.pcr ?? null,
      pct: item?.pct ?? null,
      direction,
      date: item?.date || chain.tradeDate || payload?.updatedAt || null,
      source: item?.dataSource || item?.source || chain.source?.primary || payload?.source || "Existing options analytics",
    };
  }

  function crossMarketEvidenceFor(definition, payloads) {
    if (definition.key === "TW") {
      const payload = payloads.get("tw") || null;
      const evidence = crossMarketTwEvidence(payload);
      return { payload, ...evidence };
    }
    const { payload, item } = crossMarketFindItem(payloads, definition);
    if (definition.key === "Options") {
      return { payload, ...crossMarketOptionsEvidence(payload) };
    }
    if (definition.key === "US10Y" && !item) {
      const curve = payload?.validation?.treasuryCurve || {};
      const value = crossMarketNumber(curve.yields?.[definition.maturity]);
      if (value !== null) {
        return {
          payload,
          item: null,
          value,
          pct: null,
          date: curve.date || payload?.updatedAt || null,
          source: curve.source || payload?.source || "U.S. Treasury existing yield curve",
        };
      }
    }
    return {
      payload,
      item,
      value: item?.close ?? item?.value ?? payload?.summary?.avgPct ?? null,
      pct: item?.pct ?? (item ? null : payload?.summary?.avgPct) ?? null,
      date: item?.date || payload?.snapshotDate || payload?.updatedAt || null,
      source: item?.dataSource || item?.source || payload?.sourceInfo?.primary || payload?.source || "Existing market analytics",
    };
  }

  function crossMarketDirection(definition, evidence) {
    const explicit = String(evidence.direction || "").toLowerCase();
    if (/bull|偏多|上行|positive|risk.?on/.test(explicit)) return "up";
    if (/bear|偏空|下行|negative|risk.?off/.test(explicit)) return "down";
    const pct = crossMarketNumber(evidence.pct);
    if (pct === null) return null;
    if (pct > 0) return "up";
    if (pct < 0) return "down";
    return "flat";
  }

  function crossMarketRiskHint(definition, evidence, direction) {
    const pct = crossMarketNumber(evidence.pct);
    if (direction === null || pct === null) return null;
    if (definition.key === "VIX" && direction === "up") return { text: "VIX 上行，既有波動訊號顯示風險溫度升高。", source: "VIX existing volatility signal" };
    if (definition.key === "DXY" && direction === "up") return { text: "DXY 上行，既有美元訊號顯示外部風險壓力需留意。", source: "DXY existing market item" };
    if (definition.key === "US10Y" && direction === "up") return { text: "US10Y 上行，既有利率資料顯示估值壓力需留意。", source: "U.S. Treasury / existing rate item" };
    if (definition.key === "Gold" && direction === "up") return { text: "Gold 上行，既有黃金行情顯示避險需求正在變化。", source: "Gold existing market item" };
    return null;
  }

  function crossMarketFreshness(record, hasEvidence) {
    if (typeof window?.buildSharedFreshnessConfidenceModel !== "function") {
      return {
        status: "Unavailable",
        label: "Unavailable",
        detail: "既有 freshness contract 未載入，停止跨市場判讀。",
        asOf: "--",
        updatedAt: "--",
        confidence: { label: "不足", detail: "無法驗證資料新鮮度。" },
      };
    }
    return window.buildSharedFreshnessConfidenceModel(record, {
      primaryKeys: ["snapshotDate"],
      requirePrimary: true,
      hasDecisionEvidence: hasEvidence,
    });
  }

  function crossMarketNormalizeOne(definition, payloads) {
    const evidence = crossMarketEvidenceFor(definition, payloads);
    const payload = evidence.payload || {};
    const item = evidence.item || {};
    const hasValue = crossMarketNumber(evidence.value) !== null || crossMarketNumber(evidence.pct) !== null || Boolean(evidence.direction);
    const hasError = Boolean(payload.error || item.error || item.status === "unavailable");
    const available = Boolean(payload && hasValue && !hasError);
    const normalizationStatus = available ? "normalized" : payload ? "unsupported" : "unavailable";
    const quality = available && (item.verification?.status === "limited" || payload.sourceStatus === "cached") ? "degraded" : available ? "valid" : "unavailable";
    const snapshotDate = evidence.date || null;
    const gateRecord = {
      ...payload,
      items: available ? [item] : [],
      snapshotDate,
      updatedAt: payload.updatedAt || item.updatedAt || snapshotDate || "",
      sourceStatus: item.status || payload.sourceStatus || "",
      error: hasError ? (item.error || payload.error || "unavailable") : "",
    };
    const freshness = crossMarketFreshness(gateRecord, available);
    const direction = available ? crossMarketDirection(definition, evidence) : null;
    const risk = available ? crossMarketRiskHint(definition, evidence, direction) : null;
    const source = evidence.source || payload.source || "Existing analytics";
    return {
      market: definition.key,
      asset: definition.label,
      state: direction === "up" ? "Up" : direction === "down" ? "Down" : direction === "flat" ? "Flat" : "Unavailable",
      direction,
      value: evidence.value ?? null,
      pct: evidence.pct ?? null,
      confidence: freshness.confidence,
      freshness: freshness.status,
      timestamp: snapshotDate || freshness.updatedAt || "--",
      evidence: {
        label: definition.label,
        value: evidence.pct ?? evidence.value ?? "--",
        source,
        asOf: freshness.asOf,
        status: freshness.status,
      },
      risk,
      dataQuality: quality,
      provenance: source,
      available,
      canUseForDecision: available && freshness.status === "Fresh" ? "YES" : available ? "DEGRADED" : "NO",
      normalizationStatus,
      freshnessDetail: freshness.detail,
      rawPayloadCategory: payload.category || definition.payloadKey || definition.key,
    };
  }

  window.buildCrossMarketDecisionModel = function buildCrossMarketDecisionModel(payloads = []) {
    const payloadMap = crossMarketPayloadMap(payloads);
    const inputs = CROSS_MARKET_INPUT_DEFINITIONS.map((definition) => crossMarketNormalizeOne(definition, payloadMap));
    const usable = inputs.filter((item) => item.canUseForDecision === "YES" && item.direction && item.direction !== "flat");
    const up = usable.filter((item) => item.direction === "up");
    const down = usable.filter((item) => item.direction === "down");
    const confirming = up.length && !down.length ? up : down.length && !up.length ? down : [];
    const conflicting = up.length && down.length ? [...up, ...down] : [];
    const stale = inputs.filter((item) => item.available && item.freshness !== "Fresh");
    const unavailable = inputs.filter((item) => !item.available || item.canUseForDecision === "NO");
    const sufficient = usable.length >= 2;
    const decision = !sufficient
      ? "Unavailable / insufficient evidence"
      : conflicting.length
        ? "Mixed / conflicted"
        : up.length
          ? "Aligned up"
          : down.length
            ? "Aligned down"
            : "Mixed / neutral";
    const evidenceText = (item) => `${item.asset} ${item.state}${item.pct !== null && item.pct !== undefined ? `（${item.pct}）` : ""}`;
    const reasons = sufficient
      ? conflicting.length
        ? ["既有市場證據同時出現上行與下行，維持 Mixed / conflicted。", `上行：${up.map(evidenceText).join("、")}`, `下行：${down.map(evidenceText).join("、")}`]
        : [`${confirming.length} 組可用市場證據方向一致：${confirming.map(evidenceText).join("、")}。`]
      : ["Fresh 且可正規化的市場證據少於兩組，停止產生方向性結論。"];
    if (stale.length) reasons.push(`延遲或品質降級資料未納入方向判讀：${stale.map((item) => item.asset).join("、")}。`);
    if (unavailable.length) reasons.push(`不可用資料保持顯示但不計入決策：${unavailable.map((item) => item.asset).join("、")}。`);
    const risks = inputs.map((item) => item.risk).filter(Boolean);
    if (conflicting.length) risks.unshift({ text: "跨市場方向衝突，證據一致性風險升高。", source: "Cross-market evidence" });
    if (stale.length || unavailable.length) risks.push({ text: "部分市場資料延遲或不可用，信心受資料品質限制。", source: "Freshness / data-quality gate" });
    if (!risks.length) risks.push({ text: "目前沒有可由既有資料明確提出的質性風險；仍需持續監測來源狀態。", source: "Existing evidence only" });
    const confidence = sufficient && !conflicting.length && !stale.length && !unavailable.length
      ? { label: "有限", detail: "所有納入市場均通過既有 freshness gate；此為證據覆蓋度，不是新建模型分數。" }
      : { label: "不足", detail: "市場衝突、延遲或不可用資料限制目前判讀；不產生高信心方向結論。" };
    const actions = !sufficient
      ? ["等待必要市場來源恢復並通過 Fresh gate，再重新評估。"]
      : conflicting.length
        ? ["訊號衝突，維持觀察並等待既有市場分析重新確認。"]
        : ["可持續觀察既有市場分析的一致性；本層不輸出買賣或執行指令。"];
    const invalidation = [
      ...usable.map((item) => `${item.asset} 的既有狀態或方向改變時，重新評估跨市場判斷。`),
      "任一納入證據從 Fresh 轉為 Delayed、Partial 或 Unavailable 時，重新評估。",
      "市場衝突增加、資料品質下降或必要來源缺失時，停止沿用目前結論。",
    ];
    const evidenceGroups = {
      confirming: confirming.map((item) => item.evidence),
      conflicting: conflicting.map((item) => item.evidence),
      stale: stale.map((item) => item.evidence),
      unavailable: unavailable.map((item) => item.evidence),
    };
    const freshness = inputs.every((item) => item.freshness === "Fresh") ? "Fresh" : inputs.some((item) => item.freshness === "Fresh") ? "Partial" : "Unavailable";
    return {
      crossMarket: true,
      decision,
      summary: sufficient ? "跨市場層只編排既有方向與資料品質，不重算任何市場預測或分數。" : "跨市場資料不足，已 fail-closed。",
      confidence,
      freshness: { status: freshness, label: freshness, detail: "各市場 freshness 狀態見下方 alignment 與 evidence。" },
      asOf: inputs.map((item) => item.evidence.asOf).find((value) => value && value !== "--") || "--",
      updatedAt: inputs.map((item) => item.timestamp).find((value) => value && value !== "--") || "--",
      temperature: { value: null, label: "Cross-market score", detail: "不建立新的跨市場分數。" },
      reasons,
      risks,
      strategy: { advice: actions, next: invalidation.slice(0, 2) },
      actions,
      conditions: invalidation,
      invalidation,
      limitations: ["市場專屬分析仍是 authoritative input。", "延遲、衝突或不可用資料不會被補值或隱藏。"],
      evidence: inputs.map((item) => item.evidence),
      evidenceGroups,
      marketAlignment: inputs,
      inputs,
    };
  };
  })();
