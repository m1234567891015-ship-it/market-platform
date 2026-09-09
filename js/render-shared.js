function renderSharedNavigation() {
  const BRAND_TEXT = "Market Pulse";
  const NAV_LINKS = [
    ["market-overview.html", "台股盤勢"],
    ["tw-stocks.html", "台股類股"],
    ["tw-etf.html", "台股 ETF"],
    ["tw-stock-search.html", "個股搜尋"],
    ["tw-Optional-stocks.html", "自選股"],
    ["us-market-overview.html", "美股盤勢"],
    ["us-stocks.html", "美股市場"],
    ["us-etf.html", "美股ETF"],
    ["us-stock-search.html", "美股搜尋"],
    ["us-watchlist.html", "美股自選"],
    ["international-finance.html", "貴金屬與債券"],
    ["bonds.html", "債券"],
    ["precious-metals.html", "貴金屬"],
    ["derivatives-assets.html", "期權"],
    ["futures.html", "期貨"],
    ["options.html", "選擇權"],
    ["derivatives-analytics.html", "期權分析"],
    ["derivatives-status.html", "系統維護"],
  ];
  const current = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".navbar").forEach((nav) => {
    const brandLabel = nav.querySelector(".brand span:last-child");
    if (brandLabel) brandLabel.textContent = BRAND_TEXT;
    const links = nav.querySelector(".nav-links");
    if (!links) return;
    links.innerHTML = "";
    NAV_LINKS.forEach(([href, label]) => {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = label;
      if (href === current) link.classList.add("is-active");
      links.appendChild(link);
    });
  });
}
function isExcludedSector(sector) {
  if (!sector) return false;
  return EXCLUDED_SECTOR_SOURCE_NAMES.has(sector.sourceName) || EXCLUDED_SECTOR_SOURCE_NAMES.has(sector.name);
}
function sectorMatchesAnyLabel(sector, labels) {
  if (!sector || !labels || !labels.length) return false;
  const candidates = [sector.sourceName, sector.name].filter(Boolean);
  return candidates.some((value) => labels.has(value));
}
function normalizeSectorSummaryItem(item, fallbackName) {
  return {
    name: item.name || fallbackName,
    value: item.value || "--",
    change: item.change || "--",
    pct: item.pct || "--",
    tone: item.tone || "flat",
    volume: item.volume || "--",
    turnover: item.turnover || "--",
    trades: item.trades || "--",
    hideTrades: Boolean(item.hideTrades),
    note: String(item.note || "").replace("Yahoo奇摩股市同步資料", "同步資料"),
    sourceName: item.sourceName || item.name || fallbackName,
    exchange: item.exchange || "",
    open: item.open || "--",
    high: item.high || "--",
    low: item.low || "--",
    previousClose: item.previousClose || "--",
    time: item.time || "--",
    candles: item.candles || [],
    comparisonSeries: item.comparisonSeries || { day: [] },
    benchmarkComparisonSeries: item.benchmarkComparisonSeries || { day: [] },
    technicalAnalysis: item.technicalAnalysis || {},
    chartIntervals: item.chartIntervals || {},
    summaryOnly: item.summaryOnly !== undefined ? item.summaryOnly : true,
  };
}
function renderSectorStockName(item) {
  const symbol = String(item.sourceName || "").trim();
  const match = symbol.match(/^([0-9A-Z]+)\.(TW|TWO)$/i);
  if (!match) return `<span class="class-name-cell">${escapeHtml(item.name)}</span>`;
  const code = match[1];
  const market = match[2].toUpperCase() === "TW" ? "TWSE" : "TPEX";
  const href = `tw-stock-search.html?q=${encodeURIComponent(code)}&market=${encodeURIComponent(market)}`;
  return `<a class="class-name-cell class-stock-link" href="${safeUrl(href)}" title="查看 ${escapeHtml(item.name)} 個股詳情">${escapeHtml(item.name)}</a>`;
}
function sectorSortValue(item, key) {
  if (key === "name_asc") return String(item.name || "");
  if (key === "volume_desc") return parseMarketNumber(item.volumeValue ?? item.volume);
  if (key === "turnover_desc") return parseMarketNumber(item.turnoverValue ?? item.turnover);
  if (key === "change_desc") return parseMarketNumber(item.change);
  return parseMarketNumber(item.pct);
}
function sortSectorItemsByActiveMode(items) {
  const key = sectorSortState.key || "source_order";
  if (key === "source_order") return [...(items || [])];
  return [...(items || [])].sort((left, right) => {
    if (key === "name_asc") {
      return String(left.name || "").localeCompare(String(right.name || ""), "zh-Hant");
    }
    const leftValue = sectorSortValue(left, key);
    const rightValue = sectorSortValue(right, key);
    const leftFinite = Number.isFinite(leftValue);
    const rightFinite = Number.isFinite(rightValue);
    if (leftFinite && rightFinite && leftValue !== rightValue) return rightValue - leftValue;
    if (leftFinite !== rightFinite) return leftFinite ? -1 : 1;
    return String(left.name || "").localeCompare(String(right.name || ""), "zh-Hant");
  });
}
function renderSectorSortControl() {
  const options = [
    ["source_order", "\u9810\u8a2d\u9806\u5e8f"],
    ["pct_desc", "\u6f32\u8dcc\u5e45\u9ad8\u5230\u4f4e"],
    ["change_desc", "\u6f32\u8dcc\u9ad8\u5230\u4f4e"],
    ["volume_desc", "\u6210\u4ea4\u91cf\u9ad8\u5230\u4f4e"],
    ["turnover_desc", "\u6210\u4ea4\u91d1\u984d\u9ad8\u5230\u4f4e"],
    ["name_asc", "\u540d\u7a31 A-Z"],
  ];
  return `
    <div class="sector-sort-toolbar">
      <label for="sector-sort-select">\u985e\u80a1\u6392\u5e8f</label>
      <select id="sector-sort-select" data-sector-sort>
        ${options.map(([value, label]) => `<option value="${value}" ${value === sectorSortState.key ? "selected" : ""}>${label}</option>`).join("")}
      </select>
    </div>
  `;
}
function renderScrollableClassTable(content, label = "類股排行表格") {
  return `
    <div class="class-table-scroll" tabindex="0" role="region" aria-label="${escapeHtml(label)}">
      ${content}
    </div>
  `;
}
function getSectorPageGroups() {
  const sectors = (data.sectors || []).filter((sector) => !isExcludedSector(sector));
  const yahooGroups = data.yahooSectorGroups || {};
  const yahooCatalog = data.yahooSectorCatalog || {};
  const yahooItems = (key, fallbackName) =>
    (yahooGroups[key] || []).map((item) => normalizeSectorSummaryItem(item, fallbackName));
  const listedYahoo = yahooItems("listed", "Listed");
  const otcYahoo = yahooItems("otc", "OTC");
  const emergingYahoo = yahooItems("emerging", "Emerging");
  const electronicYahoo = yahooItems("electronic", "Electronic");
  const conceptYahoo = yahooItems("concept", "Concept");
  const groupYahoo = yahooItems("group", "Group");
  const activeYahooItems = (key, fallbackItems) => {
    const active = activeYahooSectorCategories[key];
    if (!active) return fallbackItems;
    return (yahooSectorQuoteCache.get(`${key}:${active.index}`)?.items || []).map((item) =>
      normalizeSectorSummaryItem(item, active.name),
    );
  };
  const listedActive = Boolean(activeYahooSectorCategories.listed);
  const listed = activeYahooItems("listed", sectors);
  const electronicSet = new Set(["\u534a\u5c0e\u9ad4", "\u96fb\u8166\u9031\u908a", "\u5149\u96fb", "\u901a\u8a0a\u7db2\u8def", "\u96fb\u5b50\u96f6\u7d44\u4ef6", "\u96fb\u5b50\u901a\u8def", "\u8cc7\u8a0a\u670d\u52d9", "\u5176\u4ed6\u96fb\u5b50", "\u96fb\u5b50", "\u96fb\u5b50\u7522\u696d"]);
  const conceptSet = new Set(["\u904b\u52d5\u4f11\u9592", "\u5c45\u5bb6\u751f\u6d3b", "\u6578\u4f4d\u96f2\u7aef", "\u7da0\u80fd\u74b0\u4fdd", "\u6982\u5ff5\u80a1", "\u6982\u5ff5"]);
  const electronic = activeYahooItems("electronic", electronicYahoo.length
    ? electronicYahoo
    : sectors.filter((sector) => sectorMatchesAnyLabel(sector, electronicSet)));
  const concept = activeYahooItems("concept", conceptYahoo.length
    ? conceptYahoo
    : sectors.filter((sector) => sectorMatchesAnyLabel(sector, conceptSet)));
  const grouped = activeYahooItems("group", groupYahoo.length ? groupYahoo : [...sectors]
    .sort((left, right) => (parseMarketNumber(right.volume) || 0) - (parseMarketNumber(left.volume) || 0))
    .slice(0, 12));
  const tpexHighlights = data.tpexHighlights || {};
  const otc = activeYahooItems("otc", otcYahoo.length
    ? otcYahoo
    : (tpexHighlights.mainboard || []).map((item) => normalizeSectorSummaryItem(item, "OTC")));
  const emerging = activeYahooItems("emerging", emergingYahoo.length
    ? emergingYahoo
    : [...(tpexHighlights.emerging || []), ...(tpexHighlights.emergingStats || [])].map((item) =>
        normalizeSectorSummaryItem(item, "Emerging"),
      ));

  return [
    { key: "listed", label: "上市類股", kind: listedActive ? "summary" : "sector", source: listedActive ? "Yahoo奇摩股市" : "證交所", items: listed, catalog: yahooCatalog.listed || [] },
    { key: "otc", label: "上櫃類股", kind: "summary", source: "Yahoo奇摩股市", items: otc, catalog: yahooCatalog.otc || [] },
    { key: "emerging", label: "興櫃類股", kind: "summary", source: "Yahoo奇摩股市", items: emerging, catalog: yahooCatalog.emerging || [] },
    { key: "electronic", label: "電子產業", kind: electronicYahoo.length ? "summary" : "sector", source: electronicYahoo.length ? "Yahoo奇摩股市" : "證交所", items: electronic, catalog: yahooCatalog.electronic || [] },
    { key: "concept", label: "概念股", kind: conceptYahoo.length ? "summary" : "sector", source: conceptYahoo.length ? "Yahoo奇摩股市" : "證交所", items: concept, catalog: yahooCatalog.concept || [] },
    { key: "group", label: "集團股", kind: groupYahoo.length ? "summary" : "sector", source: groupYahoo.length ? "Yahoo奇摩股市" : "證交所", items: grouped, catalog: yahooCatalog.group || [] },
  ];
}
function buildTechnicalTrendSummary(detail, technicalTheory) {
  const theorySignals = Array.isArray(technicalTheory?.theorySignals) ? technicalTheory.theorySignals : [];
  const priceIndicators = Array.isArray(technicalTheory?.priceIndicators) ? technicalTheory.priceIndicators : [];
  const volumeIndicators = Array.isArray(technicalTheory?.volumeIndicators) ? technicalTheory.volumeIndicators : [];
  const breadthIndicators = Array.isArray(technicalTheory?.breadthIndicators) ? technicalTheory.breadthIndicators : [];
  const allSignals = [...theorySignals, ...priceIndicators, ...volumeIndicators, ...breadthIndicators];
  const bullish = allSignals.filter((item) => item.direction === "bullish").length;
  const bearish = allSignals.filter((item) => item.direction === "bearish").length;
  const neutral = allSignals.length - bullish - bearish;
  const netSignal = bullish - bearish;
  const backtest = technicalTheory?.backtestLearning || {};
  const framework = backtest.institutionalFramework || {};
  const forecast = backtest.forecast || {};
  const validation = backtest.validation || {};
  const movingAverage = priceIndicators.find((item) => item.movingAverage)?.movingAverage || null;
  const score = Number(technicalTheory?.score || 0);
  const combinedScore = Number.isFinite(framework.totalScore)
    ? Math.round((Math.max(0, Math.min(100, 50 + score * 2.6)) * 0.55) + (framework.totalScore * 0.45))
    : Math.round(Math.max(0, Math.min(100, 50 + score * 2.8)));
  const tone = combinedScore >= 65 || netSignal >= 5
    ? "bullish"
    : combinedScore <= 35 || netSignal <= -5
      ? "bearish"
      : "neutral";
  const label = combinedScore >= 75
    ? "多方風向"
    : combinedScore >= 60
      ? "偏多風向"
      : combinedScore > 40
        ? "震盪整理"
        : combinedScore >= 25
          ? "偏空風向"
          : "空方風向";

  const periodMap = new Map((movingAverage?.periods || []).map((item) => [item.period, item]));
  const periodDirection = (periods) => {
    const items = periods.map((period) => periodMap.get(period)).filter(Boolean);
    if (!items.length) return "資料不足";
    const positive = items.filter((item) => item.slope === "向上" && item.position === "股價在上").length;
    const negative = items.filter((item) => item.slope === "向下" && item.position === "股價在下").length;
    if (positive > negative) return "偏多";
    if (negative > positive) return "偏空";
    return "整理";
  };
  const timeframes = [
    { label: "短線", value: periodDirection([5, 10, 20]) },
    { label: "中期", value: periodDirection([20, 60, 120]) },
    { label: "長期", value: periodDirection([120, 240]) },
  ];
  const confirmations = [
    movingAverage ? `均線：${movingAverage.headline}；${movingAverage.confirmations?.[0] || movingAverage.text}` : "",
    technicalTheory.indicatorSummary ? `價量：${technicalTheory.indicatorSummary}` : "",
    technicalTheory.breadthSummary ? `市場與籌碼：${technicalTheory.breadthSummary}` : "",
    Number.isFinite(framework.totalScore)
      ? `多因子：${framework.totalScore} 分，${framework.judgement?.label || "中性"}`
      : "",
    backtest.summary ? `回測：${backtest.summary}` : "",
  ].filter(Boolean);
  const risks = [];
  if (technicalTheory.priceVolumeConflict) risks.push("價格指標與量能方向背離");
  if (technicalTheory.breadthConflict) risks.push("市場廣度或籌碼與技術方向衝突");
  if (validation.status === "watch") risks.push("回測模型出現輕微失真");
  if (validation.status === "recalibrate") risks.push("回測模型需重新校準參數");
  if (validation.status === "rebuild") risks.push("回測模型失真，暫停提高訊號權重");
  if (Number.isFinite(forecast.atrPct) && forecast.atrPct >= 5) risks.push(`ATR ${forecast.atrPct.toFixed(2)}%，波動偏高`);
  if (movingAverage?.risks?.length) risks.push(...movingAverage.risks.slice(0, 2));
  if (!risks.length) risks.push("目前未見重大技術衝突，但仍須以停損與部位管理控制風險");

  const forecastScenarios = Array.isArray(forecast.scenarios) ? forecast.scenarios : [];
  const forecastTargets = Array.isArray(forecast.priceTargets)
    ? forecast.priceTargets.filter((item) => (
        item
        && Number.isFinite(item.lower)
        && Number.isFinite(item.upper)
        && Number.isFinite(item.median)
        && Number.isFinite(item.expectedReturnPct)
      ))
    : [];
  const pickPreferredForecastRows = (items) => {
    const preferredDays = [5, 20, 60];
    const picked = preferredDays
      .map((days) => items.find((item) => Number(item.days) === days))
      .filter(Boolean);
    const remaining = items.filter((item) => !picked.includes(item));
    return [...picked, ...remaining].slice(0, 3);
  };
  const visibleScenarios = pickPreferredForecastRows(forecastScenarios);
  const visibleTargets = pickPreferredForecastRows(forecastTargets);
  const primaryTarget = forecastTargets.find((item) => Number(item.days) === 20)
    || forecastTargets.find((item) => Number(item.days) === 60)
    || forecastTargets[0]
    || null;
  const primaryScenario = primaryTarget
    ? forecastScenarios.find((item) => Number(item.days) === Number(primaryTarget.days))
    : forecastScenarios.find((item) => Number(item.days) === 20) || forecastScenarios[0] || null;
  const forecastBiasText = primaryScenario
    ? `多方 ${Number.isFinite(primaryScenario.bullish) ? primaryScenario.bullish : "--"}%、震盪 ${Number.isFinite(primaryScenario.neutral) ? primaryScenario.neutral : "--"}%、空方 ${Number.isFinite(primaryScenario.bearish) ? primaryScenario.bearish : "--"}%`
    : "情境比例不足";
  const priceForecastText = primaryTarget
    ? `${primaryTarget.label || `${primaryTarget.days} 日`}預估中位 ${primaryTarget.median.toFixed(2)}，區間 ${primaryTarget.lower.toFixed(2)} ~ ${primaryTarget.upper.toFixed(2)}，預估報酬 ${primaryTarget.expectedReturnPct >= 0 ? "+" : ""}${primaryTarget.expectedReturnPct.toFixed(2)}%。`
    : "歷史序列或回測樣本不足，暫不輸出預估價格區間。";
  const forecastSummary = forecast.summary
    ? `${forecast.summary} ${priceForecastText}`
    : priceForecastText;

  const supportText = Number.isFinite(forecast.support) ? forecast.support.toFixed(2) : "--";
  const resistanceText = Number.isFinite(forecast.resistance) ? forecast.resistance.toFixed(2) : "--";
  const action = tone === "bullish"
    ? `風向偏多，優先等回測支撐 ${supportText} 或量價續強再分批布局；接近壓力 ${resistanceText} 避免追高。${primaryTarget ? ` 參考${primaryTarget.label || "預估"}中位 ${primaryTarget.median.toFixed(2)}。` : ""}`
    : tone === "bearish"
      ? `風向偏空，反彈至壓力 ${resistanceText} 仍需保守，跌破支撐 ${supportText} 應優先控管回撤。${primaryTarget ? ` 預估區間先看 ${primaryTarget.lower.toFixed(2)} ~ ${primaryTarget.upper.toFixed(2)}。` : ""}`
      : `多空訊號分歧，暫以 ${supportText} 至 ${resistanceText} 區間觀察，等待均線、量能與籌碼同向表態。${primaryTarget ? ` 預估中位 ${primaryTarget.median.toFixed(2)} 僅作區間參考。` : ""}`;

  return {
    tone,
    label,
    score: combinedScore,
    summary: `${detail.code || ""} ${detail.name || ""} 綜合 ${allSignals.length} 項技術訊號：偏多 ${bullish}、偏空 ${bearish}、中性 ${neutral}；目前判定為${label}，預測走勢為${forecast.trendLabel || "區間震盪"}。`,
    timeframes,
    confirmations: confirmations.slice(0, 5),
    risks: [...new Set(risks)].slice(0, 4),
    action,
    confidence: technicalTheory.adaptiveConfidence || "低",
    forecast: {
      confidence: forecast.confidence || technicalTheory.adaptiveConfidence || "低",
      trendLabel: forecast.trendLabel || "區間震盪",
      summary: forecastSummary,
      support: forecast.support,
      resistance: forecast.resistance,
      atrPct: forecast.atrPct,
      scenarios: visibleScenarios,
      priceTargets: visibleTargets,
      primaryTarget,
      primaryScenario,
      forecastBiasText,
      caveat: forecast.caveat || "預測價格為區間模型估算，不是保證價格或投資建議。",
    },
  };
}
function renderTechnicalTrendForecastSummary(technicalTrendSummary, options = {}) {
  const forecast = technicalTrendSummary?.forecast || {};
  const assetLabel = options.assetLabel || "股價";
  const titleText = options.title || `預測${assetLabel}與走勢`;
  const targetTitle = options.targetTitle || `預估${assetLabel}區間`;
  const scenarios = Array.isArray(forecast.scenarios) ? forecast.scenarios : [];
  const priceTargets = Array.isArray(forecast.priceTargets) ? forecast.priceTargets : [];
  const supportText = Number.isFinite(forecast.support) ? forecast.support.toFixed(2) : "--";
  const resistanceText = Number.isFinite(forecast.resistance) ? forecast.resistance.toFixed(2) : "--";
  const atrText = Number.isFinite(forecast.atrPct) ? `${forecast.atrPct.toFixed(2)}%` : "--";
  if (!scenarios.length && !priceTargets.length) {
    return `
      <div class="technical-summary-forecast">
        <div class="technical-summary-forecast-head">
          <div>
            <span>Forecast path</span>
            <strong>${escapeHtml(titleText)}</strong>
          </div>
          <small>信心 ${escapeHtml(forecast.confidence || "低")} · ${escapeHtml(forecast.trendLabel || "區間震盪")}</small>
        </div>
        <p>${escapeHtml(forecast.summary || `歷史資料不足，暫不輸出預測${assetLabel}與走勢區間。`)}</p>
      </div>
    `;
  }
  return `
    <div class="technical-summary-forecast">
      <div class="technical-summary-forecast-head">
        <div>
          <span>Forecast path</span>
          <strong>${escapeHtml(titleText)}</strong>
        </div>
        <small>信心 ${escapeHtml(forecast.confidence || "低")} · ${escapeHtml(forecast.trendLabel || "區間震盪")}</small>
      </div>
      <p>${escapeHtml(forecast.summary || "以情境機率、ATR、支撐壓力與回測平均報酬估算預測區間。")}</p>
      <div class="backtest-forecast-levels technical-summary-levels">
        <span>支撐區 <b>${supportText}</b></span>
        <span>壓力區 <b>${resistanceText}</b></span>
        <span>ATR 波動 <b>${atrText}</b></span>
      </div>
      ${scenarios.length ? `
        <div class="backtest-forecast-grid technical-summary-scenarios">
          ${scenarios.map((item) => `
            <div class="backtest-forecast-item">
              <strong>${escapeHtml(item.label || `${item.days || "--"} 日`)}</strong>
              <span class="is-bullish">偏多 ${Number.isFinite(item.bullish) ? item.bullish : "--"}%</span>
              <span>震盪 ${Number.isFinite(item.neutral) ? item.neutral : "--"}%</span>
              <span class="is-bearish">偏空 ${Number.isFinite(item.bearish) ? item.bearish : "--"}%</span>
            </div>
          `).join("")}
        </div>
      ` : ""}
      ${priceTargets.length ? `
        <div class="backtest-price-targets technical-summary-targets">
          <div class="backtest-price-targets-head">
            <strong>${escapeHtml(targetTitle)}</strong>
            <span>${escapeHtml(forecast.forecastBiasText || "情境比例計算中")}</span>
          </div>
          <div class="backtest-price-target-grid">
            ${priceTargets.map((item) => `
              <div class="backtest-price-target">
                <span>${escapeHtml(item.label || `${item.days || "--"} 日`)}</span>
                <strong>${Number.isFinite(item.lower) ? item.lower.toFixed(2) : "--"} ~ ${Number.isFinite(item.upper) ? item.upper.toFixed(2) : "--"}</strong>
                <small>中位 ${Number.isFinite(item.median) ? item.median.toFixed(2) : "--"}｜預估 ${Number.isFinite(item.expectedReturnPct) ? `${item.expectedReturnPct >= 0 ? "+" : ""}${item.expectedReturnPct.toFixed(2)}%` : "--"}</small>
                <em>${escapeHtml(item.basis || "")}</em>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ""}
      <p class="technical-summary-caveat">${escapeHtml(forecast.caveat || `預測${assetLabel}為區間模型估算，不是保證價格或投資建議。`)}</p>
    </div>
  `;
}
function buildPath(points) {
  return points
    .filter((point) => Number.isFinite(point.value) && Number.isFinite(point.x) && Number.isFinite(point.y))
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
}
function normalizeGlobalSeries(series = []) {
  return (series || [])
    .map((item) => ({
      date: item.date || item.time || "",
      value: parseMarketNumber(item.close),
    }))
    .filter((item) => item.date && Number.isFinite(item.value));
}
function normalizeGlobalOhlcvSeries(series = []) {
  return (series || [])
    .map((item) => {
      const close = parseMarketNumber(item.close);
      const open = parseMarketNumber(item.open);
      const high = parseMarketNumber(item.high);
      const low = parseMarketNumber(item.low);
      const volume = parseMarketNumber(item.volumeValue ?? item.volume);
      return {
        date: item.date || item.time || "",
        open: Number.isFinite(open) ? open : close,
        high: Number.isFinite(high) ? high : Math.max(open || close || 0, close || 0),
        low: Number.isFinite(low) ? low : Math.min(open || close || 0, close || 0),
        close,
        volume: Number.isFinite(volume) ? volume : 0,
        openInterest: parseMarketNumber(item.openInterest),
        settlement: parseMarketNumber(item.settlement),
      };
    })
    .filter((item) => item.date && Number.isFinite(item.close));
}
function getVixSentimentBand(value) {
  if (!Number.isFinite(value)) return { label: "--", tone: "neutral", text: "VIX 資料不足。" };
  if (value < 15) return { label: "低於 15", tone: "green", text: "市場情緒偏樂觀，但需留意過度樂觀後的波動回補。" };
  if (value < 20) return { label: "15 ~ 20", tone: "green", text: "常態穩定區，風險溫度相對健康。" };
  if (value < 30) return { label: "20 ~ 30", tone: "yellow", text: "警戒區，波動升溫，留意修正與多空交戰。" };
  if (value < 40) return { label: "30 ~ 40", tone: "red", text: "高恐慌區，短線波動劇烈，避免追價。" };
  return { label: "高於 40", tone: "purple", text: "極端恐慌區，可能有非理性賣壓，也需觀察反彈契機。" };
}
function buildYahooFinanceUrl(symbol) {
  const cleanSymbol = encodeURIComponent(String(symbol || "").trim());
  return cleanSymbol ? `https://finance.yahoo.com/quote/${cleanSymbol}` : "#";
}
function buildUsStockSearchUrl(symbol) {
  const cleanSymbol = encodeURIComponent(String(symbol || "").trim().toUpperCase());
  return cleanSymbol ? `us-stock-search.html?symbol=${cleanSymbol}` : "us-stock-search.html";
}
function normalizeFuturesTechnicalCandles(candles = []) {
  return (candles || []).map((row) => ({
    date: String(row.time || row.date || "").trim(),
    open: parseMarketNumber(row.open),
    high: parseMarketNumber(row.high),
    low: parseMarketNumber(row.low),
    close: parseMarketNumber(row.close),
    volume: parseMarketNumber(row.volumeValue ?? row.volume),
    volumeValue: parseMarketNumber(row.volumeValue ?? row.volume),
    settlement: parseMarketNumber(row.settlement),
    openInterest: parseMarketNumber(row.openInterestValue ?? row.openInterest),
  })).filter((row) => row.date);
}
function optionsNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function optionsWhole(value) {
  const parsed = optionsNumber(value);
  return parsed === null ? "--" : Math.round(parsed).toLocaleString("en-US");
}
function optionsDecimal(value, digits = 2) {
  const parsed = optionsNumber(value);
  return parsed === null ? "--" : parsed.toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}
function optionsPct(value, digits = 1) {
  const parsed = optionsNumber(value);
  return parsed === null ? "--" : `${(parsed * 100).toFixed(digits)}%`;
}
function averageUsHistoryField(history, field, lookback = 5) {
  const values = history.slice(-lookback).map((item) => parseMarketNumber(item[field])).filter(Number.isFinite);
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}
function buildUsSearchDetail(item) {
  const detail = buildGlobalMarketDetail(item);
  const history = detail.historyDays || [];
  const close = parseMarketNumber(item.close);
  const pct = parseMarketNumber(item.pct);
  const tone = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  const recentWindow = history.slice(-22);
  const monthHigh = Math.max(...recentWindow.map((day) => day.high).filter(Number.isFinite));
  const monthLow = Math.min(...recentWindow.map((day) => day.low).filter(Number.isFinite));
  const avgVolume5 = averageUsHistoryField(history, "volume", 5);
  const latest = history.at(-1) || {};
  const maText = (value) => Number.isFinite(value) ? value.toFixed(2) : "--";
  const volumeText = (value) => Number.isFinite(value) ? Math.round(value).toLocaleString("zh-TW") : "--";
  const ma5 = detail.ma5;
  const ma20 = detail.ma20;
  const ma60 = detail.ma60;
  const trendParts = [];
  if (Number.isFinite(close) && Number.isFinite(ma20)) {
    trendParts.push(close >= ma20 ? "價格位於 20 日均線上方，短線結構偏強。" : "價格位於 20 日均線下方，短線仍需觀察修復。");
  }
  if (Number.isFinite(ma20) && Number.isFinite(ma60)) {
    trendParts.push(ma20 >= ma60 ? "20 日均線高於 60 日均線，中期趨勢尚未轉弱。" : "20 日均線低於 60 日均線，中期趨勢偏保守。");
  }
  if (Number.isFinite(avgVolume5) && Number.isFinite(latest.volume)) {
    trendParts.push(latest.volume >= avgVolume5 ? "成交量高於 5 日均量，量能有放大跡象。" : "成交量低於 5 日均量，追價動能仍需確認。");
  }
  const recentDays = history.slice(-5).reverse().map((day) => ({
    date: day.date || "--",
    close: formatUsDetailMetric(day.close),
    high: formatUsDetailMetric(day.high),
    low: formatUsDetailMetric(day.low),
    volume: volumeText(day.volume),
  }));
  return {
    ...detail,
    rawItem: item,
    code: item.symbol || detail.code,
    name: item.name || detail.name || item.symbol || "",
    market: "US",
    marketLabel: item.exchange || "US",
    snapshotDate: item.date || detail.snapshotDate || "",
    close: formatGlobalValue(item.close),
    open: formatGlobalValue(item.open),
    high: formatGlobalValue(item.high),
    low: formatGlobalValue(item.low),
    previousClose: formatGlobalValue(item.previousClose),
    pct: item.pct || "--",
    change: item.change || "--",
    tone,
    ma5: maText(ma5),
    ma20: maText(ma20),
    ma60: maText(ma60),
    ma120: maText(detail.ma120),
    ma240: maText(detail.ma240),
    avgVolume5: volumeText(avgVolume5),
    monthHigh: Number.isFinite(monthHigh) ? monthHigh.toFixed(2) : "--",
    monthLow: Number.isFinite(monthLow) ? monthLow.toFixed(2) : "--",
    turnover: "Yahoo 未提供",
    trend: trendParts.join(" ") || "Yahoo Finance 歷史資料不足，暫以行情快照觀察。",
    recentDays,
    historyDays: history,
    historyCount: history.length,
    historyStartDate: history[0]?.date || "",
    historyEndDate: history.at(-1)?.date || "",
    allHistoryLoaded: true,
    isFallbackHistory: false,
    source: item.source || "Yahoo Finance",
    sourceLink: buildYahooFinanceUrl(item.symbol),
    valuation: item.valuation || {},
    valuationHistory: Array.isArray(item.valuationHistory) ? item.valuationHistory : [],
    companyProfile: item.companyProfile || {},
    companyNews: Array.isArray(item.companyNews) ? item.companyNews : [],
    marginTrading: item.marginTrading || {},
    ownershipTrading: item.ownershipTrading || {},
    etfComponents: item.etfComponents || {},
    isEtf: Boolean(item.isEtf ?? detail.isEtf)
      || /ETF|FUND/.test(String(item.group || item.type || item.quoteType || "").toUpperCase()),
    detailMode: item.detailMode || "full",
    newsLinks: item.newsLinks || {
      yahoo: `${buildYahooFinanceUrl(item.symbol)}/news`,
      profile: `${buildYahooFinanceUrl(item.symbol)}/profile`,
    },
    chartIntervals: { supported: ["day", "week", "month"], intradayAvailable: false },
  };
}
function renderUsBacktestLearningCard(technicalTheory, options = {}) {
  const targetLabel = options.targetLabel || "股價";
  const priceTargetTitle = options.priceTargetTitle || `預估${targetLabel}區間`;
  const factorSubtitle = options.factorSubtitle || "以市場環境、資金面、趨勢面與進出場訊號分層驗證。";
  const frameworkKicker = options.frameworkKicker || "Institutional multi-factor";
  const frameworkTitle = options.frameworkTitle || "機構多因子回溯統整";
  const frameworkStateLabel = options.frameworkStateLabel || "市場狀態";
  const finalNote = options.finalNote || "回測只作訊號校準與風險管理參考，不保證未來價格走勢；美股基本面與籌碼資料口徑不同於台股，需搭配 SEC / 公司 IR 核對。";
  const learning = technicalTheory.backtestLearning || {};
  const validation = learning.validation || {};
  const originalValidation = learning.originalValidation || {};
  const modelRebuild = learning.modelRebuild || {};
  const best = learning.signals?.[0] || learning.bestSignal || {};
  const forecast = learning.forecast || {};
  const scenarios = Array.isArray(forecast.scenarios) ? forecast.scenarios : [];
  const priceTargets = Array.isArray(forecast.priceTargets) ? forecast.priceTargets : [];
  const performance = learning.performance || {};
  const costModel = learning.costModel || {};
  const riskModel = learning.riskModel || {};
  const institutionalFramework = learning.institutionalFramework || {};
  const institutionalLayers = Array.isArray(institutionalFramework.layers) ? institutionalFramework.layers : [];
  const recent20 = institutionalFramework.recent20 || {};
  const validationTone = validation.status === "healthy"
    ? "bullish"
    : validation.status === "watch"
      ? "neutral"
      : validation.status === "recalibrate" || validation.status === "rebuild"
        ? "bearish"
        : "neutral";
  const supportText = Number.isFinite(forecast.support) ? forecast.support.toFixed(2) : "--";
  const resistanceText = Number.isFinite(forecast.resistance) ? forecast.resistance.toFixed(2) : "--";
  const atrText = Number.isFinite(forecast.atrPct) ? `${forecast.atrPct.toFixed(2)}%` : "--";
  const adjustment = Number(learning.scoreAdjustment || 0);
  const adjustmentText = adjustment > 0 ? `+${adjustment} 偏多校準` : adjustment < 0 ? `${adjustment} 偏空校準` : "0 中性";
  const decisionTips = [
    modelRebuild.status === "rebuilt"
      ? `模型已重建：舊模型 ${modelRebuild.oldModel || "--"} 改為 ${modelRebuild.newModel || "--"}。`
      : modelRebuild.status === "failed"
        ? "替代模型尚未通過樣本外驗證，暫不提高訊號權重。"
        : "",
    validation.status === "healthy"
      ? "樣本外驗證維持健康，可保留目前技術訊號權重。"
      : validation.status === "rebuild"
        ? "模型失真偏高，需降低此標的技術訊號權重。"
        : validation.recommendation || "",
    Number.isFinite(forecast.support) && Number.isFinite(forecast.resistance)
      ? `區間參考：接近 ${supportText} 觀察承接，接近 ${resistanceText} 留意壓力。`
      : "",
    Number.isFinite(forecast.atrPct) ? `波動參考 ATR 約 ${atrText}，部位大小需搭配停損距離。` : "",
    ...(Array.isArray(options.extraDecisionTips) ? options.extraDecisionTips : []),
  ].filter(Boolean);
  return `
    <div class="stock-backtest-learning">
      <div class="backtest-learning-head">
        <span>Backtest learning</span>
        <strong>回溯學習校準</strong>
        <small>${escapeHtml(learning.summary || "歷史樣本不足，暫不調整 AI 權重")}</small>
      </div>
      <div class="institutional-backtest-card is-${escapeHtml(institutionalFramework.judgement?.tone || "neutral")}">
        <div class="institutional-backtest-head">
          <div>
            <span>${escapeHtml(frameworkKicker)}</span>
            <strong>${escapeHtml(frameworkTitle)}</strong>
            <small>${escapeHtml(factorSubtitle)}</small>
          </div>
          <div class="institutional-total-score">
            <b>${Number.isFinite(institutionalFramework.totalScore) ? institutionalFramework.totalScore : "--"}</b>
            <span>/ 100</span>
            <small>${escapeHtml(institutionalFramework.judgement?.label || "資料不足")}</small>
          </div>
        </div>
        <div class="institutional-layer-grid">
          ${institutionalLayers.map((layer) => `
            <article>
              <div><strong>${escapeHtml(layer.label || "--")}</strong><span>權重 ${layer.weight ?? "--"}%</span></div>
              <b>${Number.isFinite(layer.score) ? Math.round(layer.score) : "--"}</b>
              <div class="institutional-score-track"><i style="width:${Number.isFinite(layer.score) ? Math.round(layer.score) : 0}%"></i></div>
              <small>資料涵蓋 ${Math.round((layer.coverage || 0) * 100)}% · ${(layer.available || []).map((item) => escapeHtml(item.name)).join("、") || "等待資料"}</small>
            </article>
          `).join("") || '<p class="stock-detail-empty">多因子分層資料不足。</p>'}
        </div>
        <div class="institutional-monitor-grid">
          <div><span>${escapeHtml(frameworkStateLabel)}</span><strong>${escapeHtml(institutionalFramework.marketState || "--")}</strong></div>
          <div><span>近 20 筆勝率</span><strong>${formatBacktestPercent(recent20.winRate)} · ${escapeHtml(recent20.winState || "樣本不足")}</strong></div>
          <div><span>近 20 筆 PF</span><strong>${formatBacktestRatio(recent20.profitFactor)} · ${escapeHtml(recent20.pfState || "樣本不足")}</strong></div>
          <div><span>近 20 筆 MDD</span><strong>${formatBacktestRatio(recent20.maxDrawdown)}% · ${escapeHtml(recent20.mddState || "樣本不足")}</strong></div>
        </div>
      </div>
      <div class="backtest-forecast-card">
        <div class="backtest-forecast-head">
          <div>
            <span>Scenario forecast</span>
            <strong>未來走勢情境推估</strong>
          </div>
          <small>模型信心：${escapeHtml(forecast.confidence || "低")} · ${escapeHtml(forecast.trendLabel || "區間震盪")}</small>
        </div>
        <p>${escapeHtml(forecast.summary || "回測資料不足，暫以中性震盪情境觀察。")}</p>
        <div class="backtest-forecast-grid">
          ${scenarios.map((item) => `
            <div class="backtest-forecast-item">
              <strong>${escapeHtml(item.label || `${item.days || "--"} 日`)}</strong>
              <span class="is-bullish">偏多 ${Number.isFinite(item.bullish) ? item.bullish : "--"}%</span>
              <span>震盪 ${Number.isFinite(item.neutral) ? item.neutral : "--"}%</span>
              <span class="is-bearish">偏空 ${Number.isFinite(item.bearish) ? item.bearish : "--"}%</span>
            </div>
          `).join("") || '<p class="stock-detail-empty">樣本不足，暫不輸出情境比例。</p>'}
        </div>
        <div class="backtest-forecast-levels">
          <span>支撐區 <b>${supportText}</b></span>
          <span>壓力區 <b>${resistanceText}</b></span>
          <span>波動參考 <b>${atrText}</b></span>
        </div>
        ${priceTargets.length ? `
          <div class="backtest-price-targets">
            <div class="backtest-price-targets-head"><strong>${escapeHtml(priceTargetTitle)}</strong><span>以區間與中位價呈現</span></div>
            <div class="backtest-price-target-grid">
              ${priceTargets.map((item) => `
                <div class="backtest-price-target">
                  <span>${escapeHtml(item.label || "--")}</span>
                  <strong>${Number.isFinite(item.lower) ? item.lower.toFixed(2) : "--"} ~ ${Number.isFinite(item.upper) ? item.upper.toFixed(2) : "--"}</strong>
                  <small>中位 ${Number.isFinite(item.median) ? item.median.toFixed(2) : "--"}｜預估 ${Number.isFinite(item.expectedReturnPct) ? `${item.expectedReturnPct >= 0 ? "+" : ""}${item.expectedReturnPct.toFixed(2)}%` : "--"}</small>
                  <em>${escapeHtml(item.basis || "")}</em>
                </div>
              `).join("")}
            </div>
          </div>
        ` : ""}
        <p class="backtest-forecast-caveat">${escapeHtml(forecast.caveat || "情境推估只作風險管理參考，不保證未來價格。")}</p>
      </div>
      <div class="backtest-validation-card is-${validationTone}">
        <div class="backtest-validation-head">
          <strong>模型準確性驗證：${escapeHtml(validation.label || "樣本不足")}</strong>
        </div>
        <p>${escapeHtml(validation.recommendation || "樣本不足，暫不判定模型失真。")}</p>
        <p>原模型狀態：${escapeHtml(originalValidation.label || "未提供")}；最佳訊號 ${escapeHtml(best.name || "--")}。</p>
        <div class="backtest-validation-grid">
          <span>樣本內勝率 <b>${formatBacktestPercent(validation.inSample?.winRate)}</b></span>
          <span>樣本外勝率 <b>${formatBacktestPercent(validation.outSample?.winRate)}</b></span>
          <span>樣本外 MDD <b>${formatBacktestRatio(validation.outSample?.maxDrawdown)}%</b></span>
          <span>樣本外 PF <b>${formatBacktestRatio(validation.outSample?.profitFactor)}</b></span>
        </div>
        <ul>${(validation.reasons || ["未取得模型失真檢查資料"]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
      <div class="backtest-metrics">
        <div><span>回測週期</span><strong>${learning.horizon || 240} 日後報酬</strong></div>
        <div><span>成功門檻</span><strong>±${learning.successThreshold || 5}%</strong></div>
        <div><span>有效樣本</span><strong>${learning.evidenceCount || 0}</strong></div>
        <div><span>權重調整</span><strong class="${adjustment > 0 ? "up" : adjustment < 0 ? "down" : ""}">${adjustmentText}</strong></div>
        <div><span>交易成本</span><strong>${formatBacktestRatio(costModel.roundTripPct)}%</strong></div>
        <div><span>停損 / 停利</span><strong>${riskModel.stopLossPct || -8}% / +${riskModel.takeProfitPct || 20}%</strong></div>
        <div><span>最大回撤</span><strong class="down">${formatBacktestRatio(performance.maxDrawdown)}%</strong></div>
        <div><span>Profit Factor</span><strong>${formatBacktestRatio(best.profitFactor ?? performance.profitFactor)}</strong></div>
        <div><span>模型狀態</span><strong class="${validation.status === "rebuild" ? "down" : validation.status === "healthy" ? "up" : ""}">${escapeHtml(validation.label || "樣本不足")}</strong></div>
        <div><span>失真次數</span><strong>${validation.driftCount ?? 0}</strong></div>
      </div>
      <div class="backtest-action-card">
        <div><span>Action calibration</span><strong>操作校準提示</strong></div>
        <ul>${decisionTips.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>樣本不足，先採中性觀察。</li>"}</ul>
      </div>
      <p class="stock-theory-note">${escapeHtml(finalNote)}</p>
    </div>
  `;
}
function normalizeUsWatchlistItem(rawItem = {}) {
  const symbol = String(rawItem.symbol || rawItem.code || "").trim().toUpperCase();
  return {
    ...rawItem,
    symbol,
    code: symbol,
    market: "US",
    marketLabel: rawItem.marketLabel || rawItem.exchange || rawItem.group || "美股 / ETF",
    name: rawItem.name || rawItem.shortName || symbol,
    group: rawItem.group || rawItem.type || "美股 / ETF",
    type: rawItem.type || rawItem.group || "US Market",
  };
}
function usWatchlistKey(item) {
  return String(item?.symbol || item?.code || "").trim().toUpperCase();
}
function getUsWatchlist() {
  try {
    const parsed = JSON.parse(localStorage.getItem(US_WATCHLIST_STORAGE_KEY) || "[]");
    return Array.isArray(parsed)
      ? parsed.map(normalizeUsWatchlistItem).filter((item) => item.symbol)
      : [];
  } catch (error) {
    return [];
  }
}
function saveUsWatchlist(items) {
  localStorage.setItem(US_WATCHLIST_STORAGE_KEY, JSON.stringify(items));
}
function upsertUsWatchlistSymbol(rawItem, options = {}) {
  const normalized = normalizeUsWatchlistItem(rawItem);
  const symbol = normalized.symbol;
  if (!symbol) return false;
  const items = getUsWatchlist();
  const nextItem = {
    ...normalized,
    addedAt: normalized.addedAt || new Date().toISOString(),
  };
  const index = items.findIndex((item) => String(item.symbol).toUpperCase() === symbol);
  if (index >= 0) items[index] = { ...items[index], ...nextItem };
  else items.push(nextItem);
  saveUsWatchlist(items);
  if (options.render !== false) renderUsWatchlist();
  return true;
}
function getUsPortfolioSimulation() {
  try {
    const value = JSON.parse(localStorage.getItem(US_PORTFOLIO_SIM_STORAGE_KEY) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}
function saveUsPortfolioSimulation(value) {
  localStorage.setItem(US_PORTFOLIO_SIM_STORAGE_KEY, JSON.stringify(value));
}
function classifyUsPortfolioAsset(stock) {
  const text = [stock?.group, stock?.type, stock?.name, stock?.symbol].join(" ");
  return /ETF|FUND|TRUST/i.test(text) ? "ETF" : "股票";
}
function estimateUsPortfolioTransactionCost(position) {
  if (!(position?.shares > 0) || !(position?.entryPrice > 0) || !(position?.currentPrice > 0)) return 0;
  const buyValue = position.entryPrice * position.shares;
  const sellValue = position.currentPrice * position.shares;
  const rate = 0.0015;
  return (buyValue + sellValue) * rate;
}
function renderUsWatchlistAiSummary(items) {
  const container = document.getElementById("us-watchlist-ai-summary");
  if (!container) return;
  if (!items.length) {
    container.innerHTML = "";
    return;
  }
  const analyses = items.map((item) => usWatchlistAnalysisCache.get(usWatchlistKey(item))).filter(Boolean);
  if (!analyses.length) {
    container.innerHTML = '<div class="watchlist-ai-loading">正在整理美股自選的技術、量價、Short Interest 與估值訊號...</div>';
    return;
  }
  const positive = analyses.filter((item) => item.tone === "positive").length;
  const negative = analyses.filter((item) => item.tone === "negative").length;
  const pending = items.length - analyses.length;
  const overview = positive > negative
    ? "整體美股自選訊號偏正向，但仍應留意市場波動與集中度。"
    : negative > positive
      ? "目前風險訊號較多，建議優先檢視弱勢或高波動持股。"
      : "多空訊號接近，適合等待個股趨勢與市場情緒進一步確認。";
  container.innerHTML = `
    <div>
      <span class="news-tag">AI 多因子摘要</span>
      <h4>${overview}</h4>
      <p>偏正向 ${positive} 檔、偏弱 ${negative} 檔${pending ? `，另有 ${pending} 檔分析中` : ""}。</p>
    </div>
    <small>依 Yahoo Finance 行情、均線、量價、Short Interest 與估值資料計算，僅供研究參考。</small>
  `;
}
function renderUsWatchlist() {
  const grid = document.getElementById("us-watchlist-grid");
  const count = document.getElementById("us-watchlist-count");
  if (!grid) return;
  const items = getUsWatchlist();
  if (count) count.textContent = `${items.length} 檔`;
  if (!items.length) {
    grid.innerHTML = '<div class="watchlist-empty">尚未加入美股自選股，請至美股搜尋頁開啟個股或 ETF 詳情後加入。</div>';
    renderUsWatchlistAiSummary(items);
    renderUsPortfolioSimulator(items);
    return;
  }
  renderUsWatchlistAiSummary(items);
  renderUsPortfolioSimulator(items);
  grid.innerHTML = items.map((item) => {
    const pct = parseMarketNumber(item.pct);
    const tone = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
    const key = usWatchlistKey(item);
    const analysis = usWatchlistAnalysisCache.get(key);
    const detailUrl = buildUsStockSearchUrl(key);
    return `
      <article class="watchlist-card is-clickable" role="link" tabindex="0" data-us-watchlist-detail-url="${escapeHtml(detailUrl)}" aria-label="查看 ${escapeHtml(item.symbol)} ${escapeHtml(item.name)} 美股詳情">
        <div class="watchlist-card-head">
          <div>
            <span>${escapeHtml(item.group || "美股 / ETF")}</span>
            <h3>${escapeHtml(item.symbol || "--")} ${escapeHtml(item.name || "")}</h3>
          </div>
          <button class="watchlist-remove" type="button" data-us-watch-remove="${escapeHtml(key)}">移除</button>
        </div>
        <div class="watchlist-quote">
          <strong>${formatGlobalValue(item.close)}</strong>
          <span class="${toneClass(tone)}">${escapeHtml(item.change || "--")} / ${escapeHtml(item.pct || "--")}</span>
        </div>
        <div class="watchlist-ai-card ${analysis ? `is-${analysis.tone}` : "is-loading"}">
          ${analysis ? `
            <div class="watchlist-ai-title">
              <span>AI 分析建議</span>
              <strong>${escapeHtml(analysis.label)}</strong>
            </div>
            <p>${escapeHtml(analysis.suggestion)}</p>
            <div class="watchlist-theory-groups">
              <div>
                <strong>型態技術</strong>
                <span>${escapeHtml(analysis.adaptiveSummary || analysis.patterns?.[0] || "型態訊號不足")}</span>
              </div>
              <div>
                <strong>指標技術</strong>
                <span>${escapeHtml(analysis.indicatorSummary || analysis.indicators?.[0] || "指標訊號不足")}</span>
              </div>
            </div>
            <ul>${analysis.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>
            <small>信心 ${escapeHtml(analysis.confidence)} · 資料日 ${escapeHtml(analysis.date)}</small>
          ` : `
            <span>AI 分析建議</span>
            <p>正在讀取完整美股資料...</p>
          `}
        </div>
        <a class="watchlist-detail-link" href="${safeUrl(detailUrl)}">查看美股分析</a>
      </article>
    `;
  }).join("");
  grid.querySelectorAll("[data-us-watchlist-detail-url]").forEach((card) => {
    const openDetail = () => {
      const url = card.dataset.usWatchlistDetailUrl;
      if (url) window.location.href = url;
    };
    card.addEventListener("click", (event) => {
      if (event.target.closest("button, a, input, label, select, textarea")) return;
      openDetail();
    });
    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openDetail();
    });
  });
  grid.querySelectorAll("[data-us-watch-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.usWatchRemove;
      saveUsWatchlist(getUsWatchlist().filter((item) => usWatchlistKey(item) !== key));
      usWatchlistAnalysisCache.delete(key);
      usWatchlistDetailCache.delete(key);
      renderUsWatchlist();
      setText("us-watchlist-status", "已從美股自選股移除。");
    });
  });
}
function buildUsPortfolioFactorAssessment(positions, totals) {
  const active = positions.filter((item) => item.shares > 0);
  const analyzed = active.map((item) => item.analysis).filter(Boolean);
  const assetCounts = active.reduce((acc, item) => {
    const kind = classifyUsPortfolioAsset(item.stock);
    acc[kind] = (acc[kind] || 0) + 1;
    return acc;
  }, {});
  const maxWeight = totals.totalValue > 0
    ? Math.max(...active.map((item) => (item.marketValue / totals.totalValue) * 100), 0)
    : 0;
  const stopRiskRatio = totals.totalCost > 0 ? (totals.totalRisk / totals.totalCost) * 100 : 0;
  const netReturn = totals.totalCost > 0 ? (totals.netPnl / totals.totalCost) * 100 : 0;
  const pctMoves = active
    .map((item) => Math.abs(parseAnalysisNumber(item.detail?.pct ?? item.stock.pct) ?? 0))
    .filter(Number.isFinite);
  const avgMove = pctMoves.length ? pctMoves.reduce((sum, value) => sum + value, 0) / pctMoves.length : 0;
  const var95 = totals.totalValue * (avgMove / 100) * 1.65;
  const sharpeLike = avgMove ? netReturn / avgMove : null;
  const positiveAi = analyzed.filter((item) => item.tone === "positive").length;
  const negativeAi = analyzed.filter((item) => item.tone === "negative").length;
  const neutralAi = Math.max(analyzed.length - positiveAi - negativeAi, 0);
  const averageAiScore = analyzed.length
    ? analyzed.reduce((sum, item) => sum + (Number(item.score) || 0), 0) / analyzed.length
    : 0;
  const portfolioTheory = buildPortfolioTheoryAssessment(active, totals);

  if (!active.length) {
    return {
      tone: "neutral",
      label: "等待建立部位",
      summary: "尚未輸入股數，系統先保留美元成本、資產配置、相關性、分散化與風險貢獻的檢查框架。",
      factors: ["請輸入進場價與股數後，系統會估算美元淨損益、交易成本、集中度、VaR、相關性與分散化。"],
      actions: ["建立部位前先設定單筆停損與停利條件，並規劃單一標的權重上限。"],
      theoryDetails: portfolioTheory.details,
      theoryActions: portfolioTheory.actions,
      metrics: { maxWeight, stopRiskRatio, var95, sharpeLike, avgMove, ...portfolioTheory.metrics },
      source: PORTFOLIO_FACTOR_SOURCE,
    };
  }

  const factors = [
    `資產配置：${Object.entries(assetCounts).map(([key, count]) => `${key} ${count} 檔`).join("、") || "未分類"}。`,
    `交易成本以單邊手續費與滑價合計 0.15% 估算，成本後淨損益 ${formatUsSimulationMoney(totals.netPnl)}。`,
    `單一商品最高權重 ${maxWeight.toFixed(1)}%，組合停損風險約 ${stopRiskRatio.toFixed(1)}%。`,
    `以目前自選標的日波動估算 95% 單日 VaR 約 ${formatUsSimulationMoney(var95)}。`,
    `資產投資組合理論：${portfolioTheory.label}，已納入均值-變異、相關性、分散化比率與風險貢獻。`,
  ];
  if (analyzed.length) {
    factors.push(`AI 技術覆蓋：已納入 ${analyzed.length}/${active.length} 檔的型態理論、均線、價量、Short Interest 與回溯校準。`);
    factors.push(`技術方向：偏正向 ${positiveAi} 檔、中性 ${neutralAi} 檔、偏弱 ${negativeAi} 檔，平均 AI 分數 ${averageAiScore.toFixed(1)}。`);
  } else {
    factors.push("AI 技術覆蓋：完整美股資料尚未載入，暫以損益、權重、成本與歷史波動先行評估。");
  }
  if (Number.isFinite(sharpeLike)) factors.push(`類 Sharpe 風險效率 ${sharpeLike.toFixed(2)}，用於比較近期損益是否足以補償波動。`);

  const actions = [];
  if (maxWeight > 50) actions.push("單一商品超過 50%，組合接近單押，建議分散或設定更嚴格停損。");
  else if (maxWeight > 20) actions.push("單一商品超過 20%，需確認是否符合自己的持股上限。");
  else actions.push("單一商品權重未明顯過度集中。");
  if (stopRiskRatio >= 15) actions.push("組合停損風險高於 15%，應檢查是否降低股數或收窄停損。");
  else actions.push("組合停損風險低於 15%，風控結構相對可控。");
  if (totals.netPnl < 0 && stopRiskRatio >= 10) actions.push("淨損益為負且停損風險偏高，優先檢查弱勢持股。");
  if (negativeAi > positiveAi) actions.push("組合內偏弱 AI 訊號較多，優先檢查技術結構或 Short Interest 壓力。");
  else if (positiveAi > negativeAi) actions.push("多數持股 AI 訊號偏正向，仍應依原訂停損停利紀律分批管理。");
  actions.push(...portfolioTheory.actions.slice(0, 3));
  actions.push("未納入匯率、股息稅、券商固定費、SEC/FINRA 費用與槓桿，實際交易前需依券商規則校正。");

  const riskScore = (maxWeight > 50 ? 2 : maxWeight > 20 ? 1 : 0)
    + (stopRiskRatio >= 15 ? 2 : stopRiskRatio >= 10 ? 1 : 0)
    + (totals.netPnl < 0 ? 1 : 0)
    + (negativeAi > positiveAi ? 1 : 0)
    + (portfolioTheory.tone === "negative" ? 2 : portfolioTheory.tone === "neutral" ? 1 : 0);
  const tone = riskScore >= 4 ? "negative" : riskScore >= 2 ? "neutral" : "positive";
  const label = tone === "positive" ? "配置風險可控" : tone === "negative" ? "組合風險偏高" : "需再平衡觀察";
  return {
    tone,
    label,
    summary: `${label}：已依美元成本、資產配置、均值-變異、相關性、風險貢獻、停損停利、VaR 與個股 AI 多因子訊號整合評估。`,
    factors,
    actions,
    theoryDetails: portfolioTheory.details,
    theoryActions: portfolioTheory.actions,
    metrics: { maxWeight, stopRiskRatio, var95, sharpeLike, avgMove, averageAiScore, ...portfolioTheory.metrics },
    source: PORTFOLIO_FACTOR_SOURCE,
  };
}
function renderUsPortfolioSimulator(items = getUsWatchlist()) {
  const summary = document.getElementById("us-portfolio-simulator-summary");
  const table = document.getElementById("us-portfolio-simulator-table");
  if (!summary || !table) return;
  if (!items.length) {
    summary.innerHTML = "";
    table.innerHTML = '<div class="watchlist-empty">加入美股自選股後即可建立美元組合損益模擬。</div>';
    return;
  }
  const saved = getUsPortfolioSimulation();
  const positions = items.map((rawStock) => {
    const stock = normalizeUsWatchlistItem(rawStock);
    const key = usWatchlistKey(stock);
    const detail = usWatchlistDetailCache.get(key);
    const currentPrice = parseAnalysisNumber(detail?.close ?? stock.close) || 0;
    const setting = saved[key] || {};
    const entryPrice = parseAnalysisNumber(setting.entryPrice) || currentPrice;
    const shares = Math.max(0, parseAnalysisNumber(setting.shares) || 0);
    const stopLossPct = Math.max(0, parseAnalysisNumber(setting.stopLossPct) ?? 8);
    const takeProfitPct = Math.max(0, parseAnalysisNumber(setting.takeProfitPct) ?? 15);
    const cost = entryPrice * shares;
    const marketValue = currentPrice * shares;
    const pnl = marketValue - cost;
    const transactionCost = estimateUsPortfolioTransactionCost({ stock, currentPrice, entryPrice, shares });
    const netPnl = pnl - transactionCost;
    const returnPct = cost > 0 ? (pnl / cost) * 100 : 0;
    const netReturnPct = cost > 0 ? (netPnl / cost) * 100 : 0;
    const riskAmount = entryPrice * shares * (stopLossPct / 100);
    const analysis = usWatchlistAnalysisCache.get(key);
    return {
      stock, detail, key, currentPrice, entryPrice, shares, stopLossPct, takeProfitPct,
      cost, marketValue, pnl, transactionCost, netPnl, returnPct, netReturnPct, riskAmount,
      analysis,
      signal: getSimulationSignal(analysis, currentPrice, entryPrice, shares, stopLossPct, takeProfitPct),
    };
  });
  const active = positions.filter((item) => item.shares > 0);
  const totalCost = active.reduce((sum, item) => sum + item.cost, 0);
  const totalValue = active.reduce((sum, item) => sum + item.marketValue, 0);
  const totalPnl = totalValue - totalCost;
  const totalTransactionCost = active.reduce((sum, item) => sum + item.transactionCost, 0);
  const netPnl = totalPnl - totalTransactionCost;
  const totalReturn = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
  const netReturn = totalCost > 0 ? (netPnl / totalCost) * 100 : 0;
  const totalRisk = active.reduce((sum, item) => sum + item.riskAmount, 0);
  const maxPosition = totalValue > 0 ? Math.max(...active.map((item) => (item.marketValue / totalValue) * 100), 0) : 0;
  const riskLabel = !active.length
    ? "尚未建立模擬部位"
    : maxPosition > 50
      ? "單一持股集中度偏高"
      : totalRisk / Math.max(totalCost, 1) > 0.1
        ? "組合停損風險偏高"
        : "風險設定在可控區間";
  const portfolioAssessment = buildUsPortfolioFactorAssessment(positions, {
    totalCost, totalValue, totalPnl, totalTransactionCost, netPnl, totalReturn, netReturn, totalRisk,
  });

  summary.innerHTML = `
    <div><span>模擬投入成本</span><strong>${formatUsSimulationMoney(totalCost)}</strong></div>
    <div><span>目前市值</span><strong>${formatUsSimulationMoney(totalValue)}</strong></div>
    <div><span>未實現損益</span><strong class="${totalPnl > 0 ? "up" : totalPnl < 0 ? "down" : "flat"}">${formatUsSimulationMoney(totalPnl)}</strong></div>
    <div><span>估計交易成本</span><strong>${formatUsSimulationMoney(totalTransactionCost)}</strong></div>
    <div><span>成本後淨損益</span><strong class="${netPnl > 0 ? "up" : netPnl < 0 ? "down" : "flat"}">${formatUsSimulationMoney(netPnl)}</strong></div>
    <div><span>組合報酬率</span><strong class="${totalReturn > 0 ? "up" : totalReturn < 0 ? "down" : "flat"}">${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(2)}%</strong></div>
    <div><span>淨報酬率</span><strong class="${netReturn > 0 ? "up" : netReturn < 0 ? "down" : "flat"}">${netReturn >= 0 ? "+" : ""}${netReturn.toFixed(2)}%</strong></div>
    <div><span>停損風險金額</span><strong>${formatUsSimulationMoney(totalRisk)}</strong></div>
    <div><span>95% VaR 估計</span><strong>${formatUsSimulationMoney(portfolioAssessment.metrics.var95 || 0)}</strong></div>
    <div><span>單一最高權重</span><strong>${(portfolioAssessment.metrics.maxWeight || 0).toFixed(1)}%</strong></div>
    <div><span>組合年化波動</span><strong>${Number.isFinite(portfolioAssessment.metrics.portfolioVolatility) ? `${portfolioAssessment.metrics.portfolioVolatility.toFixed(1)}%` : "--"}</strong></div>
    <div><span>有效持股數</span><strong>${Number.isFinite(portfolioAssessment.metrics.effectivePositions) ? `${portfolioAssessment.metrics.effectivePositions.toFixed(1)} 檔` : "--"}</strong></div>
    <div><span>平均相關性</span><strong>${Number.isFinite(portfolioAssessment.metrics.averageCorrelation) ? portfolioAssessment.metrics.averageCorrelation.toFixed(2) : "--"}</strong></div>
    <div><span>分散化比率</span><strong>${Number.isFinite(portfolioAssessment.metrics.diversificationRatio) ? portfolioAssessment.metrics.diversificationRatio.toFixed(2) : "--"}</strong></div>
    <div><span>效率分數</span><strong class="${portfolioAssessment.metrics.efficiencyScore > 0 ? "up" : portfolioAssessment.metrics.efficiencyScore < 0 ? "down" : "flat"}">${Number.isFinite(portfolioAssessment.metrics.efficiencyScore) ? portfolioAssessment.metrics.efficiencyScore.toFixed(2) : "--"}</strong></div>
    <div><span>AI 平均分數</span><strong class="${portfolioAssessment.metrics.averageAiScore > 0 ? "up" : portfolioAssessment.metrics.averageAiScore < 0 ? "down" : "flat"}">${portfolioAssessment.metrics.averageAiScore > 0 ? "+" : ""}${(portfolioAssessment.metrics.averageAiScore || 0).toFixed(1)}</strong></div>
    <div><span>風險摘要</span><strong>${riskLabel}</strong></div>
  `;
  table.innerHTML = `
    <article class="portfolio-factor-card is-${portfolioAssessment.tone}">
      <div class="portfolio-factor-head">
        <div>
          <p class="panel-kicker">US portfolio factors</p>
          <h4>${escapeHtml(portfolioAssessment.label)}</h4>
        </div>
        <a href="${safeUrl(portfolioAssessment.source.url)}" target="_blank" rel="noreferrer noopener">自選組合因素基準</a>
      </div>
      <p>${escapeHtml(portfolioAssessment.summary)}</p>
      <div class="portfolio-factor-grid">
        <section><h5>納入考量</h5><ul>${portfolioAssessment.factors.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
        <section><h5>風險與再平衡</h5><ul>${portfolioAssessment.actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
        <section><h5>資產組合理論</h5><ul>${(portfolioAssessment.theoryDetails || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
      </div>
    </article>
    <div class="portfolio-table-head">
      <span>個股</span><span>目前價</span><span>模擬進場價</span><span>股數</span>
      <span>停損 / 停利</span><span>淨損益</span><span>判別訊號</span>
    </div>
    ${positions.map((item) => `
      <div class="portfolio-position-row">
        <div class="portfolio-stock-name"><strong>${escapeHtml(item.stock.code)}</strong><span>${escapeHtml(item.stock.name)}</span></div>
        <strong>${item.currentPrice ? `US$${item.currentPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "--"}</strong>
        <label><span>進場價 (USD)</span><input type="number" min="0" step="0.01" value="${item.entryPrice || ""}" data-us-portfolio-key="${escapeHtml(item.key)}" data-us-portfolio-field="entryPrice"></label>
        <label><span>股數</span><input type="number" min="0" step="1" value="${item.shares || 0}" data-us-portfolio-key="${escapeHtml(item.key)}" data-us-portfolio-field="shares"></label>
        <div class="portfolio-risk-inputs">
          <label><span>停損 %</span><input type="number" min="0" step="0.5" value="${item.stopLossPct}" data-us-portfolio-key="${escapeHtml(item.key)}" data-us-portfolio-field="stopLossPct"></label>
          <label><span>停利 %</span><input type="number" min="0" step="0.5" value="${item.takeProfitPct}" data-us-portfolio-key="${escapeHtml(item.key)}" data-us-portfolio-field="takeProfitPct"></label>
        </div>
        <div class="portfolio-pnl ${item.netPnl > 0 ? "up" : item.netPnl < 0 ? "down" : "flat"}">
          <strong>${formatUsSimulationMoney(item.netPnl)}</strong>
          <span>淨 ${item.netReturnPct >= 0 ? "+" : ""}${item.netReturnPct.toFixed(2)}%｜成本 ${formatUsSimulationMoney(item.transactionCost)}</span>
        </div>
        <div class="portfolio-signal is-${item.signal.tone}"><strong>${escapeHtml(item.signal.label)}</strong><span>${escapeHtml(item.signal.note)}</span></div>
      </div>
    `).join("")}
  `;
  table.querySelectorAll("[data-us-portfolio-key]").forEach((input) => {
    input.addEventListener("change", () => {
      const value = Math.max(0, Number(input.value) || 0);
      const simulation = getUsPortfolioSimulation();
      const key = input.dataset.usPortfolioKey;
      simulation[key] = { ...(simulation[key] || {}), [input.dataset.usPortfolioField]: value };
      saveUsPortfolioSimulation(simulation);
      renderUsPortfolioSimulator();
    });
  });
}
function sliceVisibleWindow(items, visibleCount, panOffset = 0) {
  const count = Math.min(Math.max(Math.round(Number(visibleCount)) || items.length, 1), items.length);
  const offset = Math.min(Math.max(Math.round(Number(panOffset)) || 0, 0), Math.max(items.length - count, 0));
  const end = items.length - offset;
  return items.slice(Math.max(0, end - count), end);
}
function getWeekKey(date) {
  const start = new Date(date);
  start.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return formatChartDate(start);
}
function getPeriodKey(date, interval) {
  const year = date.getFullYear();
  const month = date.getMonth();
  if (interval === "week") return getWeekKey(date);
  if (interval === "month") return `${year}-${String(month + 1).padStart(2, "0")}`;
  if (interval === "quarter") return `${year}-Q${Math.floor(month / 3) + 1}`;
  if (interval === "half") return `${year}-H${month < 6 ? 1 : 2}`;
  if (interval === "year") return `${year}`;
  return formatChartDate(date);
}
function aggregateHistory(history, interval) {
  if (interval === "day" || interval === "all") return history;

  const groups = new Map();
  history.forEach((day) => {
    const key = getPeriodKey(day.parsedDate, interval);
    if (!groups.has(key)) {
      groups.set(key, {
        date: key,
        parsedDate: day.parsedDate,
        open: day.open,
        high: day.high ?? day.close,
        low: day.low ?? day.close,
        close: day.close,
        volume: day.volume || 0,
      });
      return;
    }

    const item = groups.get(key);
    item.high = Math.max(item.high, day.high ?? day.close);
    item.low = Math.min(item.low, day.low ?? day.close);
    item.close = day.close;
    item.volume += day.volume || 0;
    item.parsedDate = day.parsedDate;
  });

  return Array.from(groups.values());
}
function renderCombinedIndicatorPanel({ title, top, height, width, pad, xAt, values, secondaryValues = [], tertiaryValues = [], bars = [], fixedMin = null, fixedMax = null }) {
  const allValues = [...values, ...secondaryValues, ...tertiaryValues, ...bars].filter((value) => value !== null && Number.isFinite(value));
  if (!allValues.length) return "";

  const minValue = fixedMin ?? Math.min(...allValues, 0);
  const maxValue = fixedMax ?? Math.max(...allValues, 0);
  const valueRange = maxValue - minValue || 1;
  const yAt = (value) => top + ((maxValue - value) / valueRange) * height;
  const zeroY = yAt(Math.min(Math.max(0, minValue), maxValue));

  const primaryPoints = values.map((value, index) => ({
    x: xAt(index),
    y: value === null ? 0 : yAt(value),
    value,
  }));
  const secondaryPoints = secondaryValues.map((value, index) => ({
    x: xAt(index),
    y: value === null ? 0 : yAt(value),
    value,
  }));
  const tertiaryPoints = tertiaryValues.map((value, index) => ({
    x: xAt(index),
    y: value === null ? 0 : yAt(value),
    value,
  }));
  const pointStep = Math.abs(xAt(1) - xAt(0)) || 2;
  const barWidth = Math.min(12, Math.max(1.2, pointStep * 0.48));
  const barHtml = bars.map((value, index) => {
    if (value === null) return "";
    const y = yAt(value);
    const barTop = Math.min(y, zeroY);
    const barHeight = Math.max(Math.abs(y - zeroY), 2);
    const tone = value >= 0 ? "up" : "down";
    return `<rect class="indicator-histogram ${tone}" x="${(xAt(index) - barWidth / 2).toFixed(1)}" y="${barTop.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="2"></rect>`;
  }).join("");
  const primaryMarkers = primaryPoints.map((point, index) => (
    !Number.isFinite(point.value) || !Number.isFinite(point.x) || !Number.isFinite(point.y)
      ? ""
      : `<circle class="chart-indicator-point is-primary" data-index="${index}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4"></circle>`
  )).join("");
  const secondaryMarkers = secondaryPoints.map((point, index) => (
    !Number.isFinite(point.value) || !Number.isFinite(point.x) || !Number.isFinite(point.y)
      ? ""
      : `<circle class="chart-indicator-point is-secondary" data-index="${index}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4"></circle>`
  )).join("");
  const tertiaryMarkers = tertiaryPoints.map((point, index) => (
    !Number.isFinite(point.value) || !Number.isFinite(point.x) || !Number.isFinite(point.y)
      ? ""
      : `<circle class="chart-indicator-point is-tertiary" data-index="${index}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4"></circle>`
  )).join("");

  return `
    <g class="combined-indicator-panel">
      <text class="combined-indicator-title" x="12" y="${top + 18}">${title}</text>
      <line class="combined-indicator-boundary" x1="${pad.left}" y1="${top}" x2="${width - pad.right}" y2="${top}"></line>
      <line class="indicator-zero-line" x1="${pad.left}" y1="${zeroY}" x2="${width - pad.right}" y2="${zeroY}"></line>
      ${barHtml}
      <path class="indicator-line-primary" d="${buildPath(primaryPoints)}"></path>
      ${secondaryValues.length ? `<path class="indicator-line-secondary" d="${buildPath(secondaryPoints)}"></path>` : ""}
      ${tertiaryValues.length ? `<path class="indicator-line-tertiary" d="${buildPath(tertiaryPoints)}"></path>` : ""}
      ${primaryMarkers}
      ${secondaryMarkers}
      ${tertiaryMarkers}
    </g>
  `;
}
async function fetchDerivativesApi(url, timeoutMs = 30000, signal = undefined, requestConfig = {}) {
  const failure = (code, message, status = null) => {
    const suffix = status === null ? "" : ` (HTTP ${status})`;
    return {
      data: null,
      error: `${code}${suffix}: ${message}`,
      errorCode: code,
      status,
    };
  };
  const load = async () => {
    try {
      const response = await fetchWithTimeout(url, { cache: "no-store", signal }, timeoutMs);
      const contentType = String(response.headers.get("content-type") || "").toLowerCase();
      const body = await response.text();
      if (!response.ok) {
        let message = "資料暫不可用";
        if (contentType.includes("json") && body.trim()) {
          try {
            const errorPayload = JSON.parse(body);
            message = errorPayload?.error?.message || message;
          } catch {}
        }
        return failure(response.status === 503 ? "SERVICE_UNAVAILABLE" : "HTTP_ERROR", message, response.status);
      }
      if (!contentType.includes("json")) return failure("INVALID_RESPONSE", "回應格式不是 JSON", response.status);
      if (!body.trim()) return failure("EMPTY", "回應內容為空", response.status);
      let payload;
      try {
        payload = JSON.parse(body);
      } catch {
        return failure("INVALID_RESPONSE", "回應不是有效 JSON", response.status);
      }
      if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
        return failure("INVALID_RESPONSE", "回應結構無效", response.status);
      }
      if (payload.success === false) {
        const code = payload.error?.code || payload.error_code || "PROVIDER_UNAVAILABLE";
        return failure(code, payload.error?.message || "資料暫不可用", response.status);
      }
      if (!("data" in payload)) return failure("INVALID_RESPONSE", "缺少 canonical data 欄位", response.status);
      return { data: payload.data, error: "", errorCode: "", status: response.status };
    } catch (error) {
      if (error?.code === "CANCELLED") return failure("CANCELLED", "要求已取消");
      if (error?.code === "TIMEOUT" || error?.name === "AbortError") return failure("TIMEOUT", "資料要求逾時");
      return failure("NETWORK_ERROR", "網路要求失敗");
    }
  };
  if (requestConfig.scheduler) {
    return requestConfig.scheduler.schedule(load, {
      priority: requestConfig.priority,
      dedupeKey: requestConfig.dedupeKey || `GET ${url}`,
      signal,
    });
  }
  return load();
}
function twEtfWeightText(value) {
  const weight = Number(value);
  if (!Number.isFinite(weight)) return "--";
  return `${weight.toFixed(Math.abs(weight % 1) > 0 ? 1 : 0)}%`;
}
window.buildSharedFreshnessConfidenceModel = function (payload, options = {}) {
  const record = payload && typeof payload === "object" && !Array.isArray(payload) ? payload : {};
  const now = options.now instanceof Date ? options.now : new Date();
  const primaryKeys = options.primaryKeys || ["snapshotDate", "institutionDate", "activityDate", "intradayDate"];
  const parseTimestamp = (value) => {
    if (value instanceof Date && Number.isFinite(value.getTime())) return value;
    const text = String(value || "").trim();
    if (!text) return null;
    const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(text) ? `${text}T23:59:59` : text.replace(" ", "T"));
    return Number.isFinite(parsed.getTime()) ? parsed : null;
  };
  const dateKey = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
  const expectedMarketDate = (date) => {
    const value = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    while (value.getDay() === 0 || value.getDay() === 6) value.setDate(value.getDate() - 1);
    return value;
  };
  const businessDaysBehind = (sourceDate, currentDate) => {
    const cursor = new Date(sourceDate.getFullYear(), sourceDate.getMonth(), sourceDate.getDate());
    const target = expectedMarketDate(currentDate);
    let days = 0;
    while (cursor < target) {
      cursor.setDate(cursor.getDate() + 1);
      if (cursor.getDay() !== 0 && cursor.getDay() !== 6) days += 1;
    }
    return days;
  };
  const primary = primaryKeys.map((key) => ({ key, raw: record[key], date: parseTimestamp(record[key]) }));
  const presentPrimary = primary.filter((item) => item.raw !== null && item.raw !== undefined && String(item.raw).trim() !== "");
  const validPrimary = presentPrimary.filter((item) => item.date);
  const timestampCandidates = ["refreshedAt", "updatedAt"]
    .map((key) => ({ key, raw: record[key], date: parseTimestamp(record[key]) }));
  const presentTimestamps = timestampCandidates.filter((item) => item.raw !== null && item.raw !== undefined && String(item.raw).trim() !== "");
  const timestampFields = presentTimestamps.filter((item) => item.date);
  const hasInvalidTimestamp = presentTimestamps.length > timestampFields.length;
  const clockSkewMs = Number.isFinite(Number(options.clockSkewMs)) ? Number(options.clockSkewMs) : 5 * 60 * 1000;
  const hasFutureTimestamp = timestampFields.some((item) => item.date.getTime() > now.getTime() + clockSkewMs);
  const cachedAt = parseTimestamp(record.cachedAt);
  const sourceStatusValues = [
    record.sourceStatus,
    record.cached ? "cached" : "",
    record.marketVolatility?.sourceStatus,
    ...(Array.isArray(record.marketInternationalIndexes) ? record.marketInternationalIndexes.map((item) => item?.sourceStatus) : []),
  ].map((value) => String(value || "").toLowerCase());
  const hasFallbackSource = sourceStatusValues.some((value) => /fallback|cached|snapshot|unavailable/.test(value));
  const requiredPrimaryMissing = Boolean(options.requirePrimary && (validPrimary.length !== primaryKeys.length || presentPrimary.length !== primaryKeys.length));
  const items = Array.isArray(record.items) ? record.items : null;
  const usableItems = items ? items.filter((item) => item && typeof item === "object" && !item.error) : [];
  const validation = record.validation && typeof record.validation === "object" ? record.validation : null;
  const failedCount = Number(validation?.failedCount);
  const verifiedCount = Number(validation?.verifiedCount);
  const providerFailure = Boolean(record.error || record.directory?.error || record.completenessFailure);
  const allItemsFailed = Boolean(items?.length) && usableItems.length === 0;
  const noUnderlyingData = Boolean(items) && items.length === 0;
  const hasDeclaredUsableData = record.hasUsableData === true;
  const validationFailedWithoutVerifiedData = Number.isFinite(failedCount) && failedCount > 0 && Number.isFinite(verifiedCount) && verifiedCount === 0;
  const materialCompletenessFailure = providerFailure || allItemsFailed || validationFailedWithoutVerifiedData;
  const mixedCompletenessFailure = (Number.isFinite(failedCount) && failedCount > 0) || (Boolean(items?.length) && usableItems.length !== items.length);
  let status = "Unavailable";
  let detail = "本頁來源尚未提供可驗證的資料日期或更新時間。";
  if (materialCompletenessFailure || noUnderlyingData) {
    status = usableItems.length || hasDeclaredUsableData ? "Partial" : "Unavailable";
    detail = usableItems.length || hasDeclaredUsableData
      ? "部分底層來源失敗或驗證不完整，不能視為完整新鮮資料。"
      : "來源回應缺少可用底層資料，不能以組裝時間判定新鮮。";
  } else if (validPrimary.length || timestampFields.length || cachedAt) {
    if (requiredPrimaryMissing || (presentPrimary.length && validPrimary.length !== presentPrimary.length) || hasInvalidTimestamp || hasFutureTimestamp || hasFallbackSource || mixedCompletenessFailure) {
      status = "Partial";
      detail = hasFutureTimestamp
        ? "來源更新時間晚於目前參考時間，不能視為新鮮資料。"
        : hasInvalidTimestamp
          ? "來源更新時間不可解析，資料完整性不足。"
          : mixedCompletenessFailure
            ? "部分底層來源失敗或驗證不完整，不能視為完整新鮮資料。"
          : hasFallbackSource
        ? "來源標示為快取、備援或不可用，不能視為完整新鮮資料。"
        : "必要來源日期缺少或不可解析，資料完整性不足。";
    } else if (validPrimary.length) {
      const keys = new Set(validPrimary.map((item) => dateKey(item.date)));
      if (keys.size > 1) {
        status = "Partial";
        detail = `來源日期不一致（${[...keys].join("、")}），不能合併為單一新鮮判讀。`;
      } else {
        const targetDate = expectedMarketDate(now);
        const sourceDate = new Date(validPrimary[0].date.getFullYear(), validPrimary[0].date.getMonth(), validPrimary[0].date.getDate());
        const behind = Math.max(...validPrimary.map((item) => businessDaysBehind(item.date, now)));
        if (sourceDate > targetDate) {
          status = "Partial";
          detail = `來源日期 ${dateKey(validPrimary[0].date)} 晚於最近交易日 ${dateKey(targetDate)}，日期證據不可用。`;
        } else if (behind > 0) {
          status = "Delayed";
          detail = `來源日期 ${dateKey(validPrimary[0].date)} 落後最近交易日 ${dateKey(expectedMarketDate(now))} ${behind} 個交易日。`;
        } else {
          status = "Fresh";
          detail = `來源日期 ${dateKey(validPrimary[0].date)} 與最近交易日一致。`;
        }
      }
    } else if (timestampFields.length) {
      const newest = Math.max(...timestampFields.map((item) => item.date.getTime()));
      const ageMinutes = Math.floor((now.getTime() - newest) / 60000);
      if (ageMinutes <= 120) {
        status = "Fresh";
        detail = `可驗證更新時間距今約 ${ageMinutes} 分鐘。`;
      } else {
        status = "Delayed";
        detail = `可驗證更新時間距今約 ${ageMinutes} 分鐘，超過兩小時視窗。`;
      }
    } else {
      status = "Partial";
      detail = "只有伺服器組裝時間，不能用它證明底層行情資料新鮮。";
    }
  }
  const suppliedConfidence = options.confidence;
  const confidenceValue = suppliedConfidence && typeof suppliedConfidence === "object"
    ? (suppliedConfidence.label ?? suppliedConfidence.score ?? suppliedConfidence.value)
    : suppliedConfidence;
  const confidenceLabel = confidenceValue === null || confidenceValue === undefined || String(confidenceValue).trim() === ""
    ? ""
    : typeof confidenceValue === "number" ? `${Math.round(confidenceValue)}/100` : String(confidenceValue);
  const confidenceDetail = suppliedConfidence && typeof suppliedConfidence === "object"
    ? String(suppliedConfidence.detail || options.confidenceDetail || "")
    : String(options.confidenceDetail || "");
  const hasExistingConfidence = Boolean(confidenceLabel);
  const confidence = status === "Fresh" && hasExistingConfidence
    ? { label: confidenceLabel, detail: confidenceDetail || "沿用本頁既有分析信心；不另外建立信心分數。" }
    : status === "Fresh" && options.hasDecisionEvidence
      ? { label: "有限", detail: "既有證據可用；此為證據覆蓋度，不是模型信心分數。" }
      : {
        label: "不足",
        detail: hasExistingConfidence
          ? `本頁既有分析信心為 ${confidenceLabel}，但資料狀態為 ${status}，不產生高信心方向結論。`
          : "沒有足夠且可驗證的新鮮證據，不產生高信心方向結論。",
      };
  return {
    status,
    label: status,
    detail,
    asOf: validPrimary[0] ? dateKey(validPrimary[0].date) : timestampFields[0] ? dateKey(timestampFields[0].date) : "--",
    updatedAt: record.refreshedAt || record.updatedAt || record.cachedAt || "--",
    confidence,
  };
};
window.updateSharedFreshnessConfidence = function (payload, context = {}) {
  window.renderSharedFreshnessConfidence(payload, context);
};
window.renderSharedFreshnessConfidence = function (payload, options = {}) {
  if (document.getElementById("market-decision-summary")) return;
  const main = document.querySelector("main");
  if (!main) return;
  let root = document.getElementById("shared-freshness-confidence");
  if (!root) {
    root = document.createElement("section");
    root.id = "shared-freshness-confidence";
    root.className = "shared-freshness-confidence";
    main.insertBefore(root, main.firstElementChild);
  }
  const model = window.buildSharedFreshnessConfidenceModel(payload, options);
  const escape = escapeHtml;
  const statusKey = ["Fresh", "Delayed", "Partial", "Unavailable"].includes(model.status) ? model.status.toLowerCase() : "unavailable";
  root.innerHTML = `<div><span class="shared-freshness-label">Data Freshness</span><strong class="decision-status decision-status-${statusKey}">${escape(model.label)}</strong><small>${escape(model.detail)}</small></div><div><span class="shared-freshness-label">Confidence</span><strong>${escape(model.confidence.label)}</strong><small>${escape(model.confidence.detail)}</small></div>`;
};
window.renderSharedMarketDecisionSummary = function (model) {
  const root = document.getElementById("market-decision-summary");
  if (!root) return;
  const escape = escapeHtml;
  const safe = (value, fallback = "--") => escape(value === null || value === undefined || value === "" ? fallback : String(value));
  const list = (items, empty = "資料同步中") => Array.isArray(items) && items.length
    ? items.map((item) => `<li>${safe(typeof item === "string" ? item : item.text)}</li>`).join("")
    : `<li>${safe(empty)}</li>`;
  const statusKey = ["Fresh", "Delayed", "Partial", "Unavailable"].includes(model?.freshness?.status)
    ? model.freshness.status.toLowerCase()
    : "unavailable";
  const temperatureValue = Number.isFinite(Number(model?.temperature?.value)) ? Math.round(Number(model.temperature.value)) : null;
  const sectors = (items, empty) => Array.isArray(items) && items.length
    ? items.map((item) => `<li><span>${safe(item.name)}</span><b>${safe(item.pct)}</b></li>`).join("")
    : `<li class="decision-empty">${safe(empty)}</li>`;
  root.innerHTML = `
    <div class="decision-center-header">
      <div>
        <p class="panel-kicker">Today Market Decision Center</p>
        <h2>今日市場決策中心</h2>
        <p class="decision-state">${safe(model?.decision, "暫不下方向結論")}</p>
        <p class="decision-summary-copy">${safe(model?.summary, "目前沒有足夠資料整理市場狀態。")}</p>
      </div>
      <div class="decision-center-meta">
        <span class="decision-status decision-status-${statusKey}">${safe(model?.freshness?.status, "Unavailable")}</span>
        <small>來源日期 ${safe(model?.asOf)} · 組裝時間 ${safe(model?.updatedAt)}</small>
      </div>
    </div>
    <div class="decision-metric-grid">
      <article class="decision-metric"><span>Data Freshness</span><strong>${safe(model?.freshness?.label, "Unavailable")}</strong><small>${safe(model?.freshness?.detail)}</small></article>
      <article class="decision-metric"><span>Confidence</span><strong>${safe(model?.confidence?.label, "不足")}</strong><small>${safe(model?.confidence?.detail)}</small></article>
      <article class="decision-metric"><span>${safe(model?.temperature?.label, "既有市場風險分數")}</span><strong>${temperatureValue === null ? "未評定" : `${temperatureValue}/100`}</strong><small>${safe(model?.temperature?.detail)}</small></article>
    </div>
    <div class="decision-center-grid">
      <article class="decision-panel"><h3>判斷依據</h3><ul>${list(model?.reasons)}</ul></article>
      <article class="decision-panel"><h3>今日風險</h3><ul>${list((model?.risks || []).map((item) => `${item.text}（${item.source || "既有資料"}）`), "核心資料不足，暫不下方向性風險結論。")}</ul></article>
      <article class="decision-panel"><h3>今日策略</h3><div class="decision-subsections"><div><b>策略建議</b><ul>${list(model?.strategy?.advice)}</ul></div><div><b>明日確認</b><ul>${list(model?.strategy?.next)}</ul></div></div></article>
      <article class="decision-panel"><h3>族群強弱</h3><div class="decision-sector-columns"><div><b>最強</b><ul>${sectors(model?.leaders, "強勢族群同步中")}</ul></div><div><b>最弱</b><ul>${sectors(model?.laggards, "弱勢族群同步中")}</ul></div></div></article>
    </div>
    <details class="decision-evidence"><summary>Evidence / Invalidation</summary><div class="decision-evidence-grid"><div><h3>證據來源</h3><ul>${(model?.evidence || []).map((item) => `<li><span>${safe(item.label)}</span><b>${safe(item.value)}</b><small>${safe(item.source)} · ${safe(item.asOf)} · ${safe(item.status)}</small></li>`).join("") || `<li>${safe("尚無可驗證證據")}</li>`}</ul></div><div><h3>失效與重新評估</h3><ul>${list(model?.invalidation)}</ul><h3>限制</h3><ul>${list(model?.limitations)}</ul></div></div></details>
  `;
};
renderSharedNavigation();
