function buildFallbackStockDetail(stock) {
  if (!stock) return null;

  const close = parseMarketNumber(stock.close);
  if (close === null) return null;

  const change = parseMarketNumber(stock.change) || 0;
  const previousClose = close - change;
  const snapshot = data?.snapshotDate ? new Date(`${data.snapshotDate}T00:00:00`) : new Date();
  const currentDate = Number.isNaN(snapshot.getTime()) ? new Date() : snapshot;
  const previousDate = new Date(currentDate);
  previousDate.setDate(previousDate.getDate() - 1);
  while (previousDate.getDay() === 0 || previousDate.getDay() === 6) {
    previousDate.setDate(previousDate.getDate() - 1);
  }
  const volume = stock.volume || "0";
  const historyDays = [
    {
      date: formatRocDateFromDate(previousDate),
      open: previousClose,
      high: previousClose,
      low: previousClose,
      close: previousClose,
      change: 0,
      volume: 0,
    },
    {
      date: formatRocDateFromDate(currentDate),
      open: parseMarketNumber(stock.open) ?? previousClose,
      high: parseMarketNumber(stock.high) ?? close,
      low: parseMarketNumber(stock.low) ?? close,
      close,
      change,
      volume,
    },
  ];

  return {
    ...stock,
    snapshotDate: data?.snapshotDate || formatChartDate(currentDate),
    ma5: "--",
    ma20: "--",
    ma60: "--",
    avgVolume5: "--",
    monthHigh: stock.high || stock.close || "--",
    monthLow: stock.low || stock.close || "--",
    trend: "先顯示本機快取行情，完整歷史資料同步中。",
    historyDays,
    recentDays: historyDays,
    historyCount: historyDays.length,
    historyStartDate: historyDays[0].date,
    historyEndDate: historyDays[historyDays.length - 1].date,
    isFallbackHistory: true,
    chartIntervals: {
      supported: ["day", "week", "month"],
      intradayAvailable: false,
      intradayUnavailableReason: "目前顯示本機快取行情。",
    },
  };
}
function buildLatestInstitutionalTradeFromHistory(history) {
  const latest = Array.isArray(history?.rows) ? history.rows[0] : null;
  if (!latest) return {};
  const formatSigned = (value) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return "--";
    return `${parsed > 0 ? "+" : ""}${Math.round(parsed).toLocaleString("zh-TW")}`;
  };
  return {
    date: latest.date || "",
    foreign: formatSigned(latest.foreignValue),
    trust: formatSigned(latest.trustValue),
    dealer: formatSigned(latest.dealerValue),
    total: formatSigned(latest.totalValue),
    foreignValue: latest.foreignValue,
    trustValue: latest.trustValue,
    dealerValue: latest.dealerValue,
    totalValue: latest.totalValue,
  };
}
function loadInstitutionalTradeHistoryIfNeeded(detail) {
  const code = String(detail?.code || "").trim();
  const market = String(detail?.market || activeStockMarket || "").trim().toUpperCase();
  if (!code || market !== "TWSE") return;
  const key = getStockDetailCacheKey(code, market);
  // TD-16 structural guard: checked and set before any other logic, so it stays
  // a real circuit breaker even if the logic-level check below is ever broken.
  if (stockInstitutionHistoryAttempted.has(key)) return;
  stockInstitutionHistoryAttempted.add(key);
  const history = detail.institutionalTradeHistory;
  // TD-16 logic-level fix: terminate once we have ANY definitive result,
  // including a genuinely empty one - a stock with <5 days of institutional
  // trade history (new listing, thinly traded) is normal, valid data, not a
  // "not done yet" signal. Conflating "insufficient rows" with "haven't loaded
  // yet" (the old `rows.length >= 5` check) is what caused the infinite
  // renderStockDetail <-> loadInstitutionalTradeHistoryIfNeeded recursion.
  //
  // The check must be "does history have a `rows` array" (Array.isArray), not
  // just "is history truthy": the full stock-detail payload (fetched before
  // this function ever runs) already sets detail.institutionalTradeHistory to
  // `{}` as a placeholder for every stock, with no `rows` key at all - only
  // *this* function's own dedicated /institutional-history fetch ever
  // populates a `rows` array (always present, possibly empty; confirmed in
  // fetchers.py:fetch_stock_institutional_trade_history and
  // builders.py:build_institutional_history_from_yahoo, both of which always
  // include "rows"). Treating the placeholder `{}` as "already resolved"
  // would skip the dedicated fetch entirely for every stock, not just sparse
  // ones - a regression discovered and fixed during Part 2 testing.
  if (Array.isArray(history?.rows)) return;
  const cached = stockInstitutionHistoryCache.get(key);
  if (cached) {
    const current = activeRenderedStockDetail || detail;
    const nextDetail = {
      ...current,
      institutionalTradeHistory: cached,
      institutionalTrades: current.institutionalTrades || buildLatestInstitutionalTradeFromHistory(cached),
    };
    renderStockDetail(nextDetail);
    return;
  }
  if (stockInstitutionHistoryPending.has(key)) return;
  const status = document.getElementById("search-status");
  if (status) status.textContent = `${code} 法人買賣超 5/10/20/30 日明細正在同步證交所 live 資料...`;
  const params = new URLSearchParams();
  if (market) params.set("market", market);
  const pending = fetchWithTimeout(
    `/api/twse/stock/${encodeURIComponent(code)}/institutional-history?${params.toString()}`,
    { cache: "no-store" },
    45000,
  )
    .then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      const loadedHistory = payload.institutionalTradeHistory || {};
      stockInstitutionHistoryCache.set(key, loadedHistory);
      if (code !== activeStockCode || market !== activeStockMarket) return;
      const current = activeRenderedStockDetail || detail;
      const nextDetail = {
        ...current,
        institutionalTradeHistory: loadedHistory,
        institutionalTrades: payload.institutionalTrades || current.institutionalTrades || buildLatestInstitutionalTradeFromHistory(loadedHistory),
      };
      renderStockDetail(nextDetail);
      if (status) status.textContent = `${code} 法人買賣超 5/10/20/30 日明細已同步證交所 live 資料。`;
    })
    .catch((error) => {
      console.error("Failed to load client institutional trade history:", error);
      if (code === activeStockCode && market === activeStockMarket && status) {
        status.textContent = `${code} 法人買賣超明細同步失敗，請重新整理或重啟後端服務後再試。`;
      }
    })
    .finally(() => {
      stockInstitutionHistoryPending.delete(key);
    });
  stockInstitutionHistoryPending.set(key, pending);
}
function isStockInWatchlist(stock) {
  return getWatchlist().some((item) => watchlistKey(item) === watchlistKey(stock));
}
function toggleWatchlistStock(stock) {
  const items = getWatchlist();
  const key = watchlistKey(stock);
  const exists = items.some((item) => watchlistKey(item) === key);
  saveWatchlist(exists ? items.filter((item) => watchlistKey(item) !== key) : [...items, stock]);
  return !exists;
}
function renderStockDetail(detail) {
  const container = document.getElementById("stock-detail");
  if (!container) return;
  const institutionCacheKey = getStockDetailCacheKey(detail.code, detail.market || activeStockMarket);
  const cachedInstitutionHistory = stockInstitutionHistoryCache.get(institutionCacheKey);
  if (
    cachedInstitutionHistory
    && (!Array.isArray(detail.institutionalTradeHistory?.rows) || !detail.institutionalTradeHistory.rows.length)
  ) {
    detail = {
      ...detail,
      institutionalTradeHistory: cachedInstitutionHistory,
      institutionalTrades: detail.institutionalTrades || buildLatestInstitutionalTradeFromHistory(cachedInstitutionHistory),
    };
  }
  activeRenderedStockDetail = detail;
  let chartDetail = detail;
  const defaultVisibleChartCount = (interval = "day") => {
    const total = getChartHistory(chartDetail, interval).length;
    if (interval === "day") return Math.min(total, 120);
    return total;
  };
  const historySummary = detail.historyCount
    ? `歷史資料：${detail.historyCount} 筆，${detail.historyStartDate || "--"} 至 ${detail.historyEndDate || "--"}`
    : "尚無歷史資料。";
  const chartIntervals = detail.chartIntervals || {};
  const supportedIntervals = new Set(chartIntervals.supported || ["day", "week", "month"]);
  const intervalButtons = [
    ["day", "日線"],
    ["week", "週線"],
    ["month", "月線"],
  ].map(([interval, label]) => {
    const unavailable = !supportedIntervals.has(interval);
    const className = unavailable ? "range-button is-disabled" : "range-button";
    return `<button class="${className}" type="button" data-interval="${interval}">${label}</button>`;
  }).join("");
  const maOptions = [5, 10, 20, 60, 120, 240];
  const chartIndicatorOptions = [
    ["bollinger", "布林通道"],
    ["fibonacci", "斐波那契"],
    ["supportResistance", "支撐壓力"],
    ["smc", "SMC"],
  ];
  const panelIndicatorOptions = TECHNICAL_PANEL_INDICATOR_OPTIONS;

  const analysisSections = detail.analysis
    ? [
        { ...detail.analysis.technical, key: "technical", title: "技術面" },
        { ...detail.analysis.fundamental, key: "fundamental", title: "基本面" },
        { ...detail.analysis.chips, key: "chips", title: "籌碼面" },
      ].filter(Boolean)
    : [];
  let technicalSummaryHtml = "";

  const renderHolderDistribution = (distribution) => {
    if (!distribution || !Object.keys(distribution).length) {
      return '<div class="stock-detail-empty">集保持股分布目前未取得。</div>';
    }
    if (distribution.available === false) {
      return `
        <div class="stock-detail-empty">
          ${escapeHtml(distribution.sourceNote || "集保持股分布目前未取得。")}
          ${distribution.sourceLink ? `<br><a href="${safeUrl(distribution.sourceLink)}" target="_blank" rel="noreferrer noopener">查看集保來源</a>` : ""}
        </div>
      `;
    }
    const largeRaw = Number(distribution.largeHolderRatio);
    const retailRaw = Number(distribution.retailHolderRatio);
    const otherRaw = Number(distribution.otherHolderRatio);
    const hasLarge = Number.isFinite(largeRaw);
    const hasRetail = Number.isFinite(retailRaw);
    const hasOther = Number.isFinite(otherRaw);
    if (!distribution.date || (!hasLarge && !hasRetail && !hasOther)) {
      return '<div class="stock-detail-empty">集保持股分布目前未取得。</div>';
    }
    const large = hasLarge ? largeRaw : 0;
    const retail = hasRetail ? retailRaw : 0;
    const other = hasOther ? otherRaw : Math.max(0, 100 - large - retail);
    if (large <= 0 && retail <= 0 && other >= 99.99 && !hasOther) {
      return '<div class="stock-detail-empty">集保持股分布目前未取得。</div>';
    }
    const liquidItems = [
      { key: "large", label: "大戶", value: large, note: distribution.largeHolderThreshold || "400 張以上" },
      { key: "retail", label: "散戶", value: retail, note: distribution.retailHolderThreshold || "10 張以下" },
      { key: "other", label: "其他", value: other, note: "10 至 400 張" },
    ].map((item) => ({
      ...item,
      value: Math.max(0, Math.min(100, item.value)),
    }));
    return `
      <div class="holder-ratio-chart" role="img" aria-label="大戶 ${large.toFixed(2)}%，散戶 ${retail.toFixed(2)}%，其他 ${other.toFixed(2)}%">
        <div class="holder-ratio-bar">
          <span class="holder-ratio-segment is-large" style="width:${large}%"></span>
          <span class="holder-ratio-segment is-other" style="width:${other}%"></span>
          <span class="holder-ratio-segment is-retail" style="width:${retail}%"></span>
        </div>
        <div class="holder-combined-panel">
          <div class="holder-liquid-chart" aria-label="集保持股液位圖">
            ${liquidItems.map((item) => `
              <div class="holder-liquid-item is-${item.key}">
                <div class="holder-liquid-head">
                  <span><i class="is-${item.key}"></i>${item.label}</span>
                  <strong>${item.value.toFixed(2)}%</strong>
                </div>
                <div class="holder-liquid-tank">
                  <span class="holder-liquid-fill" style="height:${item.value}%"></span>
                </div>
                <div class="holder-liquid-label">
                  <small>${item.note}</small>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
        <p class="holder-ratio-source">${escapeHtml(distribution.sourceNote || `集保資料日期 ${distribution.date || "--"}`)}</p>
      </div>
    `;
  };

  const renderMarginTrading = (margin) => {
    if (!margin || !Object.keys(margin).length) return "";
    const numberValue = (value) => {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const formatShares = (value, signed = false) => {
      const parsed = numberValue(value);
      if (parsed === null) return "--";
      const prefix = signed && parsed > 0 ? "+" : "";
      return `${prefix}${Math.round(parsed).toLocaleString("zh-TW")} 張`;
    };
    const financingChange = numberValue(margin.financingChange);
    const shortChange = numberValue(margin.shortChange);
    const ratio = numberValue(margin.shortFinancingRatio);
    const financingTone = financingChange > 0 ? "is-warning" : financingChange < 0 ? "is-positive" : "";
    const shortTone = shortChange > 0 ? "is-negative" : shortChange < 0 ? "is-positive" : "";
    return `
      <section class="margin-trading-card">
        <div class="margin-trading-head">
          <div>
            <span>Margin trading</span>
            <strong>融資融券</strong>
          </div>
          <small>資料日期 ${escapeHtml(margin.date || detail.snapshotDate || "--")}</small>
        </div>
        <div class="margin-trading-grid">
          <div>
            <span>融資餘額</span>
            <strong>${formatShares(margin.financingBalance)}</strong>
            <small class="${financingTone}">日增減 ${formatShares(financingChange, true)}</small>
          </div>
          <div>
            <span>融券餘額</span>
            <strong>${formatShares(margin.shortBalance)}</strong>
            <small class="${shortTone}">日增減 ${formatShares(shortChange, true)}</small>
          </div>
          <div>
            <span>券資比</span>
            <strong>${ratio === null ? "--" : `${ratio.toFixed(2)}%`}</strong>
            <small>融券餘額 ÷ 融資餘額</small>
          </div>
          <div>
            <span>資券互抵</span>
            <strong>${formatShares(margin.offsetting)}</strong>
            <small>當日沖銷張數</small>
          </div>
        </div>
        <div class="margin-trading-flow">
          <span>融資買進 <b>${formatShares(margin.financingBuy)}</b></span>
          <span>融資賣出 <b>${formatShares(margin.financingSell)}</b></span>
          <span>融券賣出 <b>${formatShares(margin.shortSell)}</b></span>
          <span>融券回補 <b>${formatShares(margin.shortBuy)}</b></span>
        </div>
        <p>${escapeHtml(margin.sourceNote || "融資融券資料以交易所公告為準。")} ${margin.sourceLink ? `<a href="${safeUrl(margin.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
      </section>
    `;
  };

  const renderInstitutionalTradeHistory = (history) => {
    if (!history || !Object.keys(history).length) return "";
    const rows = Array.isArray(history.rows) ? history.rows : [];
    const periods = (Array.isArray(history.periods) && history.periods.length ? history.periods : [5, 10, 20, 30])
      .map((period) => Number(period))
      .filter((period) => Number.isFinite(period) && period > 0);
    const stateKey = getStockDetailCacheKey(detail.code, detail.market || activeStockMarket);
    const requestedPeriod = Number(stockInstitutionPeriodState.get(stateKey) || history.defaultPeriod || 5);
    const activePeriod = periods.includes(requestedPeriod) ? requestedPeriod : periods[0] || 5;
    const summaries = history.summaries && typeof history.summaries === "object" ? history.summaries : {};
    const summary = summaries[String(activePeriod)] || history.summary || null;
    const visibleRows = rows.slice(0, activePeriod);
    if (!visibleRows.length && !summary) {
      return `
        <section class="institution-trade-panel is-loading" aria-label="法人買賣超明細">
          <div class="institution-trade-head">
            <div>
              <span>Institutional flow</span>
              <strong>法人籌碼買賣</strong>
            </div>
            <small>TWSE T86 · 單位 ${escapeHtml(history.unit || "張")}</small>
          </div>
          <div class="institution-period-switcher" aria-label="法人買賣超期間切換">
            ${periods.map((period) => `
              <button class="${period === activePeriod ? "is-active" : ""}" type="button" data-institution-period="${period}">
                ${period}日
              </button>
            `).join("")}
          </div>
          <p class="stock-detail-empty">${escapeHtml(history.sourceNote || "法人買賣超明細同步中。")}</p>
        </section>
      `;
    }
    const valueKeys = [
      { key: "foreign", label: "外資", tone: "foreign" },
      { key: "trust", label: "投信", tone: "trust" },
      { key: "dealer", label: "自營商", tone: "dealer" },
      { key: "total", label: "合計", tone: "total" },
    ];
    const numberValue = (value) => {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const getLotsValue = (record, key) => {
      const lots = numberValue(record?.[`${key}LotsValue`]);
      if (lots !== null) return lots;
      const shares = numberValue(record?.[`${key}Value`]);
      return shares === null ? null : shares / 1000;
    };
    const valueTone = (value) => {
      if (value === null || value === 0) return "is-flat";
      return value > 0 ? "is-buy" : "is-sell";
    };
    const formatValue = (value) => {
      if (value === null) return "--";
      const rounded = Math.round(value);
      const normalized = Math.abs(value - rounded) < 0.05 ? rounded : value;
      return normalized.toLocaleString("zh-TW", { maximumFractionDigits: 1 });
    };
    const renderRow = (record, extraClass = "") => `
      <div class="institution-trade-row ${extraClass}" role="row">
        <span class="institution-trade-date" role="cell">${escapeHtml(record.label || record.displayDate || record.date || "--")}</span>
        ${valueKeys.map((item) => {
          const value = getLotsValue(record, item.key);
          return `<strong class="${valueTone(value)}" role="cell">${formatValue(value)}</strong>`;
        }).join("")}
      </div>
    `;
    const sourceDate = rows[0]?.date || detail.snapshotDate || "--";
    return `
      <section class="institution-trade-panel" aria-label="法人買賣超明細">
        <div class="institution-trade-head">
          <div>
            <span>Institutional flow</span>
            <strong>法人籌碼買賣</strong>
          </div>
          <small>TWSE T86 · 單位 ${escapeHtml(history.unit || "張")}</small>
        </div>
        <div class="institution-period-switcher" aria-label="法人買賣超期間切換">
          ${periods.map((period) => `
            <button class="${period === activePeriod ? "is-active" : ""}" type="button" data-institution-period="${period}">
              ${period}日
            </button>
          `).join("")}
        </div>
        <div class="institution-trade-table" role="table">
          <div class="institution-trade-row is-head" role="row">
            <span role="columnheader">日期</span>
            ${valueKeys.map((item) => `
              <span class="institution-trade-label is-${item.tone}" role="columnheader"><i></i>${item.label}</span>
            `).join("")}
          </div>
          ${summary ? renderRow(summary, "is-summary") : ""}
          ${visibleRows.map((row) => renderRow(row)).join("")}
        </div>
        <p>單位：${escapeHtml(history.unit || "張")}｜資料日期 ${escapeHtml(sourceDate)} ${history.sourceLink ? `<a href="${safeUrl(history.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
      </section>
    `;
  };

  const pickHolderDistribution = (section) => (
    section.holderDistribution && Object.keys(section.holderDistribution).length
      ? section.holderDistribution
      : detail.shareholderDistribution
  );

  const renderChipDashboard = (section) => {
    const backendCards = Array.isArray(section?.chipSummary?.cards)
      ? section.chipSummary.cards
      : Array.isArray(detail.chipSummary?.cards) ? detail.chipSummary.cards : [];
    const backendCard = (key) => backendCards.find((card) => card?.key === key) || {};
    const numberValue = (value) => {
      const parsed = parseAnalysisNumber(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const formatLots = (value, signed = false, digits = 0) => {
      const parsed = numberValue(value);
      if (parsed === null) return "--";
      const prefix = signed && parsed > 0 ? "+" : "";
      return `${prefix}${parsed.toLocaleString("zh-TW", { minimumFractionDigits: digits, maximumFractionDigits: digits })} 張`;
    };
    const formatPercentText = (value, signed = false, digits = 2) => {
      const parsed = numberValue(value);
      if (parsed === null) return "--";
      const prefix = signed && parsed > 0 ? "+" : "";
      return `${prefix}${parsed.toFixed(digits)}%`;
    };
    const formatPlainNumber = (value, signed = false, digits = 0) => {
      const parsed = numberValue(value);
      if (parsed === null) return "--";
      const prefix = signed && parsed > 0 ? "+" : "";
      return `${prefix}${parsed.toLocaleString("zh-TW", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
    };
    const toneFromValue = (value) => {
      const parsed = numberValue(value);
      if (parsed === null || parsed === 0) return "flat";
      return parsed > 0 ? "up" : "down";
    };
    const valueToneClass = (value) => {
      const tone = toneFromValue(value);
      return tone === "up" ? "is-up" : tone === "down" ? "is-down" : "is-flat";
    };
    const metric = (label, value) => ({ label, value });
    const market = String(detail.market || activeStockMarket || "").toUpperCase();
    const suffix = market === "TPEX" ? "TWO" : "TW";
    const yahooChipUrl = (page) => `https://tw.stock.yahoo.com/quote/${encodeURIComponent(`${detail.code}.${suffix}`)}/${page}`;
    const yahooInstitutional = detail.yahooInstitutionalTrading || {};
    const yahooInstitutionalOverviewRows = Array.isArray(yahooInstitutional.overviewRows)
      ? yahooInstitutional.overviewRows
      : [];
    const yahooInstitutionalRow = (name) => yahooInstitutionalOverviewRows.find((row) => row?.name === name) || {};
    const yahooInstitutionalDailyRows = Array.isArray(yahooInstitutional.dailyRows)
      ? yahooInstitutional.dailyRows
      : [];
    const exchangeInstitutionalRows = Array.isArray(detail.institutionalTradeHistory?.rows)
      ? detail.institutionalTradeHistory.rows
      : [];
    const institutionalRows = [...exchangeInstitutionalRows, ...yahooInstitutionalDailyRows];
    const institutional = detail.institutionalTrades && Object.keys(detail.institutionalTrades).length
      ? detail.institutionalTrades
      : buildLatestInstitutionalTradeFromHistory(detail.institutionalTradeHistory || {});
    const totalInstitution = numberValue(institutional?.totalValue);
    const foreignInstitution = numberValue(institutional?.foreignValue);
    const trustInstitution = numberValue(institutional?.trustValue);
    const dealerInstitution = numberValue(institutional?.dealerValue);
    const totalInstitutionLots = numberValue(yahooInstitutionalRow("三大法人").netLots) ?? (totalInstitution === null ? null : totalInstitution / 1000);
    const foreignInstitutionLots = numberValue(yahooInstitutionalRow("外資").netLots) ?? (foreignInstitution === null ? null : foreignInstitution / 1000);
    const trustInstitutionLots = numberValue(yahooInstitutionalRow("投信").netLots) ?? (trustInstitution === null ? null : trustInstitution / 1000);
    const dealerInstitutionLots = numberValue(yahooInstitutionalRow("自營商").netLots) ?? (dealerInstitution === null ? null : dealerInstitution / 1000);
    const institutionalFallback = backendCard("institutional");
    const institutionalCard = {
      key: "institutional",
      tab: "法人買賣",
      title: "法人買賣變化",
      label: totalInstitutionLots === null ? (institutionalFallback.label || "待同步") : totalInstitutionLots > 0 ? "買超" : totalInstitutionLots < 0 ? "賣超" : "中性",
      tone: totalInstitutionLots === null ? (institutionalFallback.tone || "flat") : toneFromValue(totalInstitutionLots),
      metrics: [
        metric("三大法人", formatLots(totalInstitutionLots, true)),
        metric("外資", formatLots(foreignInstitutionLots, true)),
        metric("投信", formatLots(trustInstitutionLots, true)),
        metric("自營商", formatLots(dealerInstitutionLots, true)),
      ],
      sourceNote: detail.institutionalTradeHistory?.sourceNote || yahooInstitutional.sourceNote || institutionalFallback.sourceNote || "法人買賣超明細同步自交易所公開資料。",
      sourceLink: yahooInstitutional.sourceLink || detail.institutionalTradeHistory?.sourceLink || institutionalFallback.sourceLink || yahooChipUrl("institutional-trading"),
    };
    const broker = detail.brokerTrading || {};
    const brokerSummary = broker.summary || {};
    const brokerNet = numberValue(brokerSummary.netLots);
    const hasBroker = Boolean(brokerNet !== null || broker.buyBrokers?.length || broker.sellBrokers?.length);
    const mainCard = {
      key: "mainForce",
      tab: "主力進出",
      title: "主力進出",
      label: !hasBroker ? "同步中" : brokerNet > 0 ? "偏買進" : brokerNet < 0 ? "偏賣出" : "換手觀察",
      tone: hasBroker ? toneFromValue(brokerNet) : "flat",
      metrics: [
        metric("主力買賣超", hasBroker ? formatLots(brokerNet, true) : "--"),
        metric("主力買超", formatLots(brokerSummary.buyLots)),
        metric("主力賣超", formatLots(brokerSummary.sellLots)),
        metric("佔成交量", brokerSummary.volumeRatio || "--"),
      ],
      sourceNote: broker.sourceNote || "主力進出同步自 Yahoo 股市券商分點頁。",
      sourceLink: broker.sourceLink || yahooChipUrl("broker-trading"),
    };
    const margin = detail.marginTrading || {};
    const marginOverviewRows = Array.isArray(margin.overviewRows) ? margin.overviewRows : [];
    const marginDailyRows = Array.isArray(margin.dailyRows) ? margin.dailyRows : [];
    const marginOverviewByKey = (key) => marginOverviewRows.find((row) => row?.key === key) || {};
    const financingOverview = marginOverviewByKey("financing");
    const shortOverview = marginOverviewByKey("short");
    const latestMarginDaily = marginDailyRows[0] || {};
    const financingChange = numberValue(financingOverview.change) ?? numberValue(latestMarginDaily.financingChange) ?? numberValue(margin.financingChange);
    const shortChange = numberValue(shortOverview.change) ?? numberValue(latestMarginDaily.shortChange) ?? numberValue(margin.shortChange);
    const financingBalance = numberValue(financingOverview.balance) ?? numberValue(latestMarginDaily.financingBalance) ?? numberValue(margin.financingBalance);
    const shortBalance = numberValue(shortOverview.balance) ?? numberValue(latestMarginDaily.shortBalance) ?? numberValue(margin.shortBalance);
    const shortFinancingRatio = numberValue(shortOverview.shortFinancingRatio) ?? numberValue(latestMarginDaily.shortFinancingRatio) ?? numberValue(margin.shortFinancingRatio);
    const marginLabel = shortChange !== null && shortChange > 0 && (financingChange || 0) <= 0
      ? "券增資減"
      : financingChange !== null && financingChange > 0 && (shortChange || 0) <= 0
        ? "資增券減"
        : financingChange !== null || shortChange !== null ? "同步觀察" : "待同步";
    const marginCard = {
      key: "margin",
      tab: "資券變化",
      title: "資券變化",
      label: marginLabel,
      tone: marginLabel === "券增資減" ? "down" : marginLabel === "資增券減" ? "up" : "flat",
      metrics: [
        metric("融資增減", formatLots(financingChange, true)),
        metric("融券增減", formatLots(shortChange, true)),
        metric("融資餘額", formatLots(financingBalance)),
        metric("券資比", formatPercentText(shortFinancingRatio)),
      ],
      sourceNote: margin.sourceNote || "融資融券資料以交易所公告為準。",
      sourceLink: margin.sourceLink || yahooChipUrl("margin"),
    };
    const holders = pickHolderDistribution(section) || {};
    const majorData = detail.majorHolderData || {};
    const majorLatest = majorData.latest || {};
    const majorRowsForFallback = Array.isArray(majorData.rows) ? majorData.rows : [];
    const majorFallbackRow = [majorLatest, ...majorRowsForFallback].find((row) => numberValue(row?.majorHolderRatio) !== null) || majorLatest;
    const large = numberValue(holders.largeHolderRatio) ?? numberValue(majorFallbackRow.majorHolderRatio);
    const retail = numberValue(holders.retailHolderRatio);
    const other = numberValue(holders.otherHolderRatio);
    const foreignChip = numberValue(majorLatest.foreignChipRatio) ?? numberValue(majorFallbackRow.foreignChipRatio);
    const directorHolding = numberValue(majorLatest.directorHoldingRatio) ?? numberValue(majorFallbackRow.directorHoldingRatio);
    const holderAvailable = (holders.available !== false && large !== null) || foreignChip !== null;
    const holderLabel = !holderAvailable ? "同步中" : large !== null && large >= 60 ? "集中" : large !== null && large < 35 ? "分散" : large === null && foreignChip !== null ? "外資籌碼" : "觀察";
    const holderCard = {
      key: "largeHolder",
      tab: "大戶籌碼",
      title: "大戶籌碼",
      label: holderLabel,
      tone: holderLabel === "集中" ? "up" : holderLabel === "分散" ? "down" : "flat",
      metrics: [
        metric("大戶", formatPercentText(large)),
        metric("外資籌碼", formatPercentText(foreignChip)),
        metric("董監持股", formatPercentText(directorHolding)),
        metric("日期", holders.date || majorFallbackRow.date || majorData.date || "--"),
      ],
      sourceNote: holders.sourceNote || majorData.sourceNote || "大戶籌碼同步自 Yahoo 股市大戶籌碼頁與集保資料。",
      sourceLink: holders.sourceLink || majorData.sourceLink || yahooChipUrl("major-holders"),
    };
    const holderVisualDistribution = (() => {
      const hasTdccLarge = holders.available !== false && numberValue(holders.largeHolderRatio) !== null;
      if (hasTdccLarge) return holders;
      const yahooLarge = numberValue(majorFallbackRow.majorHolderRatio);
      if (yahooLarge === null) return holders;
      const fallbackRetail = numberValue(holders.retailHolderRatio) ?? 0;
      const fallbackOther = numberValue(holders.otherHolderRatio) ?? Math.max(0, 100 - yahooLarge - fallbackRetail);
      return {
        available: true,
        date: majorFallbackRow.date || majorData.date || majorLatest.date || holders.date || "--",
        largeHolderRatio: yahooLarge,
        retailHolderRatio: fallbackRetail,
        otherHolderRatio: fallbackOther,
        largeHolderThreshold: "Yahoo 大戶籌碼",
        retailHolderThreshold: holders.retailHolderThreshold || "TDCC 待恢復",
        source: majorData.source || "Yahoo 股市大戶籌碼",
        sourceLink: majorData.sourceLink || yahooChipUrl("major-holders"),
        sourceNote: holders.sourceNote
          ? `${holders.sourceNote}；液位圖暫以 Yahoo 大戶籌碼維持顯示，散戶比例待 TDCC 恢復後更新。`
          : "液位圖暫以 Yahoo 大戶籌碼維持顯示，散戶比例待 TDCC 恢復後更新。",
      };
    })();
    const cards = [institutionalCard, mainCard, marginCard, holderCard];
    const stateKey = getStockDetailCacheKey(detail.code, detail.market || activeStockMarket);
    const requestedTab = stockChipTabState.get(stateKey) || "institutional";
    const activeCard = cards.find((card) => card.key === requestedTab) || cards[0];
    const institutionRangeOptions = [
      { key: "1m", label: "1個月", months: 1, fallbackCount: 24 },
      { key: "3m", label: "3個月", months: 3, fallbackCount: 66 },
      { key: "6m", label: "6個月", months: 6, fallbackCount: 90 },
      { key: "1y", label: "1年", years: 1, fallbackCount: 110 },
    ];
    const activeInstitutionRangeKey = stockInstitutionRangeState.get(stateKey) || "1m";
    const activeInstitutionRange = institutionRangeOptions.find((item) => item.key === activeInstitutionRangeKey)
      || institutionRangeOptions.find((item) => item.key === "1m")
      || institutionRangeOptions[0];
    const defaultInstitutionSeries = ["price", "foreign", "trust", "dealer"];
    const savedInstitutionSeries = String(stockInstitutionSeriesState.get(stateKey) || defaultInstitutionSeries.join(","))
      .split(",")
      .filter(Boolean);
    const activeInstitutionSeries = new Set(savedInstitutionSeries.length ? savedInstitutionSeries : defaultInstitutionSeries);
    const institutionSeriesOptions = [
      { key: "price", label: "股價" },
      { key: "foreign", label: "外資" },
      { key: "trust", label: "投信" },
      { key: "dealer", label: "自營商" },
    ];
    const normalizeInstitutionDate = (value) => {
      const text = String(value || "").trim();
      if (!text) return "";
      if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
      if (/^\d{4}\/\d{2}\/\d{2}$/.test(text)) return text.replaceAll("/", "-");
      const roc = text.match(/^(\d{2,3})\/(\d{2})\/(\d{2})$/);
      if (roc) return `${Number(roc[1]) + 1911}-${roc[2]}-${roc[3]}`;
      return text;
    };
    const priceHistory = normalizePortfolioHistory(detail)
      .map((item) => ({ ...item, isoDate: normalizeInstitutionDate(item.date) }))
      .filter((item) => item.isoDate && Number.isFinite(item.close));
    const priceByDate = new Map(priceHistory.map((item) => [item.isoDate, item.close]));
    const buildInstitutionRowsForRange = (rows, option) => {
      const normalizedRows = Array.isArray(rows)
        ? rows
            .map((row) => ({ ...row, date: normalizeInstitutionDate(row?.date || row?.label) }))
            .filter((row) => row.date)
        : [];
      const sourceRows = [...new Map(normalizedRows.map((row) => [row.date, row])).values()]
        .sort((left, right) => String(right.date || "").localeCompare(String(left.date || "")));
      const datedTimes = [
        ...sourceRows.map((row) => new Date(row.date).getTime()),
        ...priceHistory.map((item) => new Date(item.isoDate).getTime()),
      ].filter(Number.isFinite);
      if (!datedTimes.length) return sourceRows.slice(0, option.fallbackCount || sourceRows.length);
      const latestTime = Math.max(...datedTimes);
      const cutoff = new Date(latestTime);
      if (option.years) cutoff.setFullYear(cutoff.getFullYear() - option.years);
      else cutoff.setMonth(cutoff.getMonth() - (option.months || 1));
      const cutoffTime = cutoff.getTime();
      const inRange = (date) => {
        const time = new Date(date).getTime();
        return Number.isFinite(time) && time >= cutoffTime && time <= latestTime;
      };
      const rangedFlows = sourceRows.filter((row) => inRange(row.date));
      const longRange = Boolean(option.years || (option.months || 0) >= 6);
      const rangedPrices = priceHistory.filter((item) => inRange(item.isoDate));
      const oldestFlowTime = rangedFlows.length
        ? Math.min(...rangedFlows.map((row) => new Date(row.date).getTime()).filter(Number.isFinite))
        : Number.POSITIVE_INFINITY;
      const hasLongerPriceCoverage = rangedPrices.some((item) => {
        const time = new Date(item.isoDate).getTime();
        return Number.isFinite(time) && time < oldestFlowTime - 7 * 24 * 60 * 60 * 1000;
      });
      if (!longRange || !rangedPrices.length || !hasLongerPriceCoverage) {
        return (rangedFlows.length ? rangedFlows : sourceRows).slice(0, option.fallbackCount || sourceRows.length);
      }
      const flowByDate = new Map(rangedFlows.map((row) => [row.date, row]));
      const merged = rangedPrices.map((price) => {
        const flow = flowByDate.get(price.isoDate) || {};
        return {
          ...flow,
          date: price.isoDate,
          label: price.isoDate.slice(5),
          priceValue: price.close,
          priceVolume: price.volume,
          isPriceOnly: !flowByDate.has(price.isoDate),
        };
      });
      rangedFlows.forEach((row) => {
        if (!priceByDate.has(row.date)) merged.push({ ...row, label: row.label || row.date.slice(5) });
      });
      return merged
        .sort((left, right) => String(right.date || "").localeCompare(String(left.date || "")))
        .slice(0, option.fallbackCount || merged.length);
    };
    const activeInstitutionRows = buildInstitutionRowsForRange(institutionalRows, activeInstitutionRange);
    const activeInstitutionFlowCount = activeInstitutionRows.filter((row) => (
      Number.isFinite(numberValue(row.foreignLotsValue))
      || Number.isFinite(numberValue(row.trustLotsValue))
      || Number.isFinite(numberValue(row.dealerLotsValue))
      || Number.isFinite(numberValue(row.totalLotsValue))
    )).length;
    const renderMetrics = (card) => `
      <div class="chip-summary-metrics">
        ${(card.metrics || []).map((item) => `
          <div><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></div>
        `).join("")}
      </div>
    `;
    const renderChipVisualLegend = (items) => `
      <div class="chip-visual-legend">
        ${items.map((item) => `<span><i class="is-${item.key}"></i>${escapeHtml(item.label)}</span>`).join("")}
      </div>
    `;
    const renderInstitutionOverview = () => {
      const rows = yahooInstitutionalOverviewRows.length
        ? yahooInstitutionalOverviewRows
        : [
            { name: "外資", buyLots: null, sellLots: null, netLots: foreignInstitutionLots, streak: "--" },
            { name: "投信", buyLots: null, sellLots: null, netLots: trustInstitutionLots, streak: "--" },
            { name: "自營商", buyLots: null, sellLots: null, netLots: dealerInstitutionLots, streak: "--" },
            { name: "三大法人", buyLots: null, sellLots: null, netLots: totalInstitutionLots, streak: "--" },
          ].filter((row) => numberValue(row.netLots) !== null);
      if (!rows.length) return "";
      return `
        <div class="chip-overview-table chip-institution-overview">
          <div class="chip-overview-row is-head"><span>法人</span><span>買進</span><span>賣出</span><span>買賣超</span><span>連買連賣</span></div>
          ${rows.map((row) => `
            <div class="chip-overview-row">
              <span>${escapeHtml(row.name || "--")}</span>
              <strong>${formatLots(row.buyLots)}</strong>
              <strong>${formatLots(row.sellLots)}</strong>
              <strong class="${valueToneClass(row.netLots)}">${formatLots(row.netLots, true)}</strong>
              <span>${escapeHtml(row.streak || "--")}</span>
            </div>
          `).join("")}
        </div>
      `;
    };
    const renderInstitutionControls = () => `
      <div class="institution-chart-controls" aria-label="法人買賣變化控制">
        <div class="institution-range-buttons" role="group" aria-label="法人買賣變化區間">
          ${institutionRangeOptions.map((option) => `
            <button class="range-button ${option.key === activeInstitutionRange.key ? "is-active" : ""}" type="button" data-institution-range="${escapeHtml(option.key)}">${escapeHtml(option.label)}</button>
          `).join("")}
        </div>
        <div class="institution-series-buttons" role="group" aria-label="法人買賣變化項目">
          ${institutionSeriesOptions.map((item) => `
            <button class="institution-series-button is-${escapeHtml(item.key)} ${activeInstitutionSeries.has(item.key) ? "is-active" : ""}" type="button" data-institution-series="${escapeHtml(item.key)}" aria-pressed="${activeInstitutionSeries.has(item.key) ? "true" : "false"}">
              <i class="is-${escapeHtml(item.key)}"></i>${escapeHtml(item.label)}
            </button>
          `).join("")}
        </div>
      </div>
    `;
    const renderInstitutionChart = () => {
      const rows = activeInstitutionRows.slice().reverse();
      if (!rows.length) return "";
      const width = 760;
      const height = 230;
      const pad = { left: 36, right: 18, top: 18, bottom: 34 };
      const mid = 122;
      const barScale = 82;
      const usableWidth = width - pad.left - pad.right;
      const step = rows.length > 1 ? usableWidth / (rows.length - 1) : usableWidth;
      const priceStart = Math.max(0, priceHistory.length - rows.length);
      const points = rows.map((row, index) => {
        const fallbackPrice = priceHistory[priceStart + index]?.close;
        const rowDate = normalizeInstitutionDate(row.date || row.label || "");
        return {
          date: rowDate,
          label: row.label || String(rowDate || "").slice(5),
          x: pad.left + (rows.length > 1 ? index * step : usableWidth / 2),
          foreign: numberValue(row.foreignLotsValue),
          trust: numberValue(row.trustLotsValue),
          dealer: numberValue(row.dealerLotsValue),
          price: numberValue(row.priceValue) ?? numberValue(priceByDate.get(rowDate)) ?? fallbackPrice ?? null,
          total: numberValue(row.totalLotsValue),
          foreignChip: numberValue(row.foreignChipRatio),
          changePct: numberValue(row.changePct),
          volume: numberValue(row.volume) ?? numberValue(row.priceVolume),
        };
      });
      const flowKeys = ["foreign", "trust", "dealer"].filter((key) => activeInstitutionSeries.has(key));
      const maxAbs = Math.max(1, ...points.flatMap((item) => flowKeys.map((key) => Math.abs(item[key] || 0))));
      const prices = points.map((item) => item.price).filter(Number.isFinite);
      const minPrice = prices.length ? Math.min(...prices) : 0;
      const maxPrice = prices.length ? Math.max(...prices) : 1;
      const priceRange = Math.max(maxPrice - minPrice, 1);
      const barWidth = flowKeys.length ? Math.max(2.4, Math.min(8, step * (0.46 / flowKeys.length))) : 0;
      const bar = (x, value, key, offset) => {
        if (!Number.isFinite(value)) return "";
        const normalized = value;
        const y = normalized >= 0 ? mid - (normalized / maxAbs) * barScale : mid;
        const h = Math.max(1, Math.abs((normalized / maxAbs) * barScale));
        return `<rect class="chip-flow-bar is-${key}" x="${(x + offset).toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${h.toFixed(2)}" rx="1.6"></rect>`;
      };
      const barOffsets = flowKeys.map((_, index) => (index - (flowKeys.length - 1) / 2) * (barWidth + 1.4));
      const yPriceFor = (value) => pad.top + ((maxPrice - value) / priceRange) * (height - pad.top - pad.bottom);
      const yFlowFor = (value) => {
        const normalized = Number.isFinite(value) ? value : 0;
        return normalized >= 0 ? mid - (normalized / maxAbs) * barScale : mid + Math.abs((normalized / maxAbs) * barScale);
      };
      const pricePath = activeInstitutionSeries.has("price") ? points
        .filter((item) => Number.isFinite(item.price))
        .map((item, index) => `${index ? "L" : "M"} ${item.x.toFixed(2)} ${yPriceFor(item.price).toFixed(2)}`)
        .join(" ") : "";
      const zoneWidth = rows.length > 1 ? Math.max(10, step) : usableWidth;
      const cursorYFor = (item) => {
        if (activeInstitutionSeries.has("price") && Number.isFinite(item.price)) return yPriceFor(item.price);
        const firstFlowKey = flowKeys.find((key) => Number.isFinite(item[key]));
        return firstFlowKey ? yFlowFor(item[firstFlowKey]) : mid;
      };
      const hoverZones = points.map((item) => {
        const zoneX = rows.length > 1
          ? Math.max(pad.left, Math.min(width - pad.right - zoneWidth, item.x - zoneWidth / 2))
          : pad.left;
        return `<rect class="institution-hover-zone" x="${zoneX.toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${height - pad.top - pad.bottom}" data-x="${item.x.toFixed(2)}" data-y="${cursorYFor(item).toFixed(2)}" data-date="${escapeHtml(item.date || "--")}" data-price="${escapeHtml(Number.isFinite(item.price) ? item.price.toLocaleString("zh-TW") : "--")}" data-foreign="${escapeHtml(formatLots(item.foreign, true))}" data-trust="${escapeHtml(formatLots(item.trust, true))}" data-dealer="${escapeHtml(formatLots(item.dealer, true))}" data-total="${escapeHtml(formatLots(item.total, true))}" data-foreign-chip="${escapeHtml(formatPercentText(item.foreignChip))}" data-change="${escapeHtml(formatPercentText(item.changePct, true))}" data-volume="${escapeHtml(formatPlainNumber(item.volume))}" data-show-price="${activeInstitutionSeries.has("price") ? "1" : "0"}" data-show-foreign="${activeInstitutionSeries.has("foreign") ? "1" : "0"}" data-show-trust="${activeInstitutionSeries.has("trust") ? "1" : "0"}" data-show-dealer="${activeInstitutionSeries.has("dealer") ? "1" : "0"}"></rect>`;
      }).join("");
      return `
        <div class="chip-visual-card chip-institution-chart">
          <div class="chip-visual-head"><span>法人買賣變化</span><strong>${escapeHtml(activeInstitutionRange.label)} / ${escapeHtml(rows.at(-1)?.date || detail.snapshotDate || "--")}</strong></div>
          ${renderInstitutionControls()}
          <div class="institution-chart-stage">
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="法人買賣變化圖">
              <line class="chip-chart-axis" x1="${pad.left}" y1="${mid}" x2="${width - pad.right}" y2="${mid}"></line>
              ${points.map((item) => flowKeys.map((key, index) => bar(item.x, item[key], key, barOffsets[index])).join("")).join("")}
              ${pricePath ? `<path class="chip-price-line" d="${pricePath}"></path>` : ""}
              <line class="institution-crosshair is-x" data-institution-cursor-x x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
              <line class="institution-crosshair is-y" data-institution-cursor-y x1="${pad.left}" y1="${mid}" x2="${width - pad.right}" y2="${mid}"></line>
              <circle class="institution-crosshair-dot" data-institution-cursor-dot cx="${pad.left}" cy="${mid}" r="4"></circle>
              ${hoverZones}
            </svg>
            <div class="institution-chart-tooltip" hidden></div>
          </div>
          <p class="institution-chart-note">顯示 ${activeInstitutionRows.length.toLocaleString("zh-TW")} 個時間點，法人買賣 ${activeInstitutionFlowCount.toLocaleString("zh-TW")} 筆；長區間會合併價格歷史，法人資料不足的日期以 -- 標示。</p>
        </div>
      `;
    };
    const renderInstitutionRows = () => {
      const rows = activeInstitutionRows;
      if (!rows.length) return '<p class="stock-detail-empty">法人逐日買賣超目前未取得。</p>';
      const selectedFlowColumns = [
        { key: "foreign", label: "外資", valueKey: "foreignLotsValue" },
        { key: "trust", label: "投信", valueKey: "trustLotsValue" },
        { key: "dealer", label: "自營商", valueKey: "dealerLotsValue" },
      ].filter((item) => activeInstitutionSeries.has(item.key));
      const showYahooColumns = rows.some((row) => row.foreignChipRatio !== undefined || row.changePct !== undefined || row.volume !== undefined);
      const showForeignChip = showYahooColumns && activeInstitutionSeries.has("foreign");
      const showPriceColumns = showYahooColumns && activeInstitutionSeries.has("price");
      return `
        <div class="chip-data-table chip-institution-daily-table">
          <div class="chip-data-row is-head is-institution-daily-dynamic" style="--institution-cols:${1 + selectedFlowColumns.length + (showForeignChip ? 1 : 0) + (showPriceColumns ? 2 : 0)}">
            <span>日期</span>
            ${selectedFlowColumns.map((item) => `<span>${escapeHtml(item.label)}</span>`).join("")}
            <span>合計</span>
            ${showForeignChip ? "<span>外資籌碼</span>" : ""}
            ${showPriceColumns ? "<span>漲跌幅</span><span>成交量</span>" : ""}
          </div>
          ${rows.map((row) => `
            <div class="chip-data-row is-institution-daily-dynamic" style="--institution-cols:${1 + selectedFlowColumns.length + (showForeignChip ? 1 : 0) + (showPriceColumns ? 2 : 0)}">
              <span>${escapeHtml(row.date || "--")}</span>
              ${selectedFlowColumns.map((item) => `<strong class="${valueToneClass(row[item.valueKey])}">${formatLots(numberValue(row[item.valueKey]), true)}</strong>`).join("")}
              <strong class="${valueToneClass(row.totalLotsValue)}">${formatLots(numberValue(row.totalLotsValue), true)}</strong>
              ${showForeignChip ? `<strong>${formatPercentText(row.foreignChipRatio)}</strong>` : ""}
              ${showPriceColumns ? `<strong class="${valueToneClass(row.changePct)}">${formatPercentText(row.changePct, true)}</strong><strong>${formatPlainNumber(row.volume)}</strong>` : ""}
            </div>
          `).join("")}
        </div>
      `;
    };
    const renderBrokerBalanceBar = () => {
      const buyLots = Math.abs(numberValue(brokerSummary.buyLots) || 0);
      const sellLots = Math.abs(numberValue(brokerSummary.sellLots) || 0);
      const totalLots = buyLots + sellLots;
      if (!totalLots) return "";
      const buyPct = Math.round((buyLots / totalLots) * 100);
      const sellPct = Math.max(0, 100 - buyPct);
      return `
        <div class="broker-balance-card" aria-label="主力買賣超比例">
          <div class="broker-balance-head">
            <span>主力買賣超比例</span>
            <strong>${buyPct}% / ${sellPct}%</strong>
          </div>
          <div class="broker-balance-track">
            <span class="is-buy" style="width:${buyPct}%"></span>
            <span class="is-sell" style="width:${sellPct}%"></span>
          </div>
          <div class="broker-balance-labels">
            <span><i class="is-buy"></i>買超 ${formatLots(buyLots)}</span>
            <span><i class="is-sell"></i>賣超 ${formatLots(sellLots)}</span>
          </div>
        </div>
      `;
    };
    const renderBrokerRowsWithBars = (rows, title, tone = "buy") => {
      const visibleRows = (rows || []).slice(0, 12);
      const maxNet = Math.max(...visibleRows.map((row) => Math.abs(numberValue(row.net) || 0)), 1);
      const rowTone = tone === "sell" ? "sell" : "buy";
      return `
        <div class="chip-broker-table is-${rowTone}">
          <h5>${escapeHtml(title)}</h5>
          <div class="chip-data-row is-head"><span>券商</span><span>買進</span><span>賣出</span><span>買賣超張數</span></div>
          ${visibleRows.map((row) => {
            const net = numberValue(row.net);
            const width = Math.max(4, Math.min(100, (Math.abs(net || 0) / maxNet) * 100));
            return `
              <div class="chip-data-row chip-broker-row is-${rowTone}">
                <span>${escapeHtml(row.broker || "--")}</span>
                <strong>${formatLots(row.buy)}</strong>
                <strong>${formatLots(row.sell)}</strong>
                <strong class="chip-broker-net">
                  <span class="chip-broker-bar" style="width:${width}%"></span>
                  <b>${formatLots(net, true)}</b>
                </strong>
              </div>
            `;
          }).join("") || '<p class="stock-detail-empty">券商分點資料同步中。</p>'}
        </div>
      `;
    };
    const renderBrokerRows = (rows, title) => `
      <div class="chip-broker-table">
        <h5>${escapeHtml(title)}</h5>
        <div class="chip-data-row is-head"><span>券商</span><span>買進</span><span>賣出</span><span>買賣超</span></div>
        ${(rows || []).slice(0, 10).map((row) => `
          <div class="chip-data-row">
            <span>${escapeHtml(row.broker || "--")}</span>
            <strong>${formatLots(row.buy)}</strong>
            <strong>${formatLots(row.sell)}</strong>
            <strong>${formatLots(row.net, true)}</strong>
          </div>
        `).join("") || '<p class="stock-detail-empty">正在同步券商分點明細。</p>'}
      </div>
    `;
    const formatLotsPlain = (value, signed = false) => formatPlainNumber(value, signed, 0);
    const formatMarginDate = (row, includeEnd = false) => {
      const toSlashDate = (value) => {
        const normalized = normalizeInstitutionDate(value || "");
        return normalized && /^\d{4}-\d{2}-\d{2}$/.test(normalized) ? normalized.replaceAll("-", "/") : (normalized || "--");
      };
      const start = toSlashDate(row?.date);
      const end = toSlashDate(row?.endDate);
      if (includeEnd && end !== "--" && end !== start) return `${start} - ${end.slice(5)}`;
      return start;
    };
    const marginSummaryModeOptions = [
      { key: "today", label: "當日" },
      { key: "acc", label: "累計" },
    ];
    const marginTableTypeOptions = [
      { key: "marginBalance", label: "資券餘額" },
      { key: "lendingBalance", label: "借券賣出餘額" },
    ];
    const marginPeriodOptions = [
      { key: "day", label: "日", title: "逐日" },
      { key: "week", label: "週", title: "逐週" },
      { key: "month", label: "月", title: "逐月" },
      { key: "quarter", label: "季", title: "逐季" },
    ];
    const renderMarginOverviewRows = () => {
      const activeSummaryMode = stockMarginSummaryModeState.get(stateKey) || "today";
      const rows = marginOverviewRows.length
        ? marginOverviewRows
        : [
            {
              key: "financing",
              name: "融資",
              buy: margin.financingBuy,
              sell: margin.financingSell,
              repayment: margin.financingCashRedemption,
              change: financingChange,
              balance: financingBalance,
              utilizationRate: margin.financingUtilizationRate,
              streak: "--",
            },
            {
              key: "short",
              name: "融券",
              buy: margin.shortBuy,
              sell: margin.shortSell,
              repayment: margin.shortStockRedemption,
              change: shortChange,
              balance: shortBalance,
              utilizationRate: margin.shortUtilizationRate,
              streak: "--",
              offsetting: margin.offsetting,
              shortFinancingRatio,
            },
          ].filter((row) => numberValue(row.change) !== null || numberValue(row.balance) !== null);
      if (!rows.length) return "";
      const financingRow = rows.find((row) => row?.key === "financing") || {};
      const shortRow = rows.find((row) => row?.key === "short") || {};
      const tabs = `
        <div class="margin-switch-buttons" role="group" aria-label="資券變化總覽模式">
          ${marginSummaryModeOptions.map((option) => `<button class="range-button ${option.key === activeSummaryMode ? "is-active" : ""}" type="button" data-margin-summary-mode="${escapeHtml(option.key)}" aria-pressed="${option.key === activeSummaryMode ? "true" : "false"}">${escapeHtml(option.label)}</button>`).join("")}
        </div>
      `;
      const renderTodaySummary = () => `
        <div class="margin-table-scroll">
          <div class="margin-summary-table is-today">
            <div class="margin-summary-row is-head">
              <span></span><span>買進</span><span>賣出</span><span>現償</span><span>增減</span><span>餘額</span><span>使用率</span><span>連增連減</span><span>資券互抵</span><span>券資比</span>
            </div>
            <div class="margin-summary-row">
              <span>融資</span>
              <strong>${formatLotsPlain(financingRow.buy)}</strong>
              <strong>${formatLotsPlain(financingRow.sell)}</strong>
              <strong>${formatLotsPlain(financingRow.repayment)}</strong>
              <strong class="${valueToneClass(financingRow.change)}">${formatLotsPlain(financingRow.change, true)}</strong>
              <strong>${formatLotsPlain(financingRow.balance)}</strong>
              <strong>${formatPercentText(financingRow.utilizationRate)}</strong>
              <span>${escapeHtml(financingRow.streak || "--")}</span>
              <strong>${formatLotsPlain(shortRow.offsetting)}</strong>
              <strong class="is-muted">--</strong>
            </div>
            <div class="margin-summary-row">
              <span>融券</span>
              <strong>${formatLotsPlain(shortRow.buy)}</strong>
              <strong>${formatLotsPlain(shortRow.sell)}</strong>
              <strong>${formatLotsPlain(shortRow.repayment)}</strong>
              <strong class="${valueToneClass(shortRow.change)}">${formatLotsPlain(shortRow.change, true)}</strong>
              <strong>${formatLotsPlain(shortRow.balance)}</strong>
              <strong>${formatPercentText(shortRow.utilizationRate)}</strong>
              <span>${escapeHtml(shortRow.streak || "--")}</span>
              <strong class="is-muted">--</strong>
              <strong class="margin-ratio-cell">${formatPercentText(shortRow.shortFinancingRatio)}${shortRow.ratioStreak ? `<small>(${escapeHtml(shortRow.ratioStreak)})</small>` : ""}</strong>
            </div>
          </div>
        </div>
      `;
      const renderAccumulationSummary = () => {
        const accRows = Array.isArray(margin.marginSummaryAccumulationRows) ? margin.marginSummaryAccumulationRows : [];
        const accByKey = new Map(accRows.map((row) => [String(row.periodSum || ""), row]));
        const periods = [
          { key: "2D", label: "2日" },
          { key: "3D", label: "3日" },
          { key: "5D", label: "5日" },
          { key: "10D", label: "10日" },
          { key: "1M", label: "1月" },
          { key: "3M", label: "3月" },
          { key: "6M", label: "6月" },
          { key: "1Y", label: "1年" },
        ];
        const cell = (period, key, formatter) => {
          const row = accByKey.get(period.key) || {};
          const value = row[key];
          return `<strong class="${valueToneClass(value)}">${formatter(value)}</strong>`;
        };
        return `
          <div class="margin-table-scroll">
            <div class="margin-summary-table is-acc">
              <div class="margin-summary-row is-head">
                <span>項目</span>${periods.map((period) => `<span>${escapeHtml(period.label)}</span>`).join("")}
              </div>
              <div class="margin-summary-row">
                <span>融資增減</span>${periods.map((period) => cell(period, "financingChange", (value) => formatLotsPlain(value, true))).join("")}
              </div>
              <div class="margin-summary-row">
                <span>融券增減</span>${periods.map((period) => cell(period, "shortChange", (value) => formatLotsPlain(value, true))).join("")}
              </div>
              <div class="margin-summary-row">
                <span>券資比增減</span>${periods.map((period) => cell(period, "shortFinancingRatioChange", (value) => formatPercentText(value, true))).join("")}
              </div>
            </div>
          </div>
        `;
      };
      return `
        <div class="chip-visual-card margin-summary-card">
          <div class="chip-visual-head"><span>資券變化總覽</span><strong>資料時間：${escapeHtml(formatMarginDate({ date: margin.date || detail.snapshotDate }))}</strong></div>
          ${tabs}
          ${activeSummaryMode === "acc" ? renderAccumulationSummary() : renderTodaySummary()}
        </div>
      `;
    };
    const renderMarginDailyRows = () => {
      const activeTableType = stockMarginTableTypeState.get(stateKey) || "marginBalance";
      const activePeriodKey = stockMarginPeriodState.get(stateKey) || "day";
      const activePeriod = marginPeriodOptions.find((option) => option.key === activePeriodKey) || marginPeriodOptions[0];
      const periodRows = margin.marginBalancePeriodRows && typeof margin.marginBalancePeriodRows === "object"
        ? margin.marginBalancePeriodRows
        : {};
      const sourceRows = Array.isArray(periodRows[activePeriod.key]) && periodRows[activePeriod.key].length
        ? periodRows[activePeriod.key]
        : activePeriod.key === "day" ? marginDailyRows : [];
      const rows = sourceRows.slice(0, 30);
      if (!rows.length) return "";
      const controls = `
        <div class="margin-table-controls">
          <div class="margin-switch-buttons" role="group" aria-label="資券餘額表格類型">
            ${marginTableTypeOptions.map((option) => `<button class="range-button ${option.key === activeTableType ? "is-active" : ""}" type="button" data-margin-table-type="${escapeHtml(option.key)}" aria-pressed="${option.key === activeTableType ? "true" : "false"}">${escapeHtml(option.label)}</button>`).join("")}
          </div>
          <div class="margin-switch-buttons" role="group" aria-label="資券餘額期間">
            ${marginPeriodOptions.map((option) => `<button class="range-button ${option.key === activePeriod.key ? "is-active" : ""}" type="button" data-margin-period="${escapeHtml(option.key)}" aria-pressed="${option.key === activePeriod.key ? "true" : "false"}">${escapeHtml(option.label)}</button>`).join("")}
          </div>
        </div>
      `;
      const renderMarginBalanceTable = () => `
        <div class="margin-table-scroll">
          <div class="margin-period-grid is-margin">
            <div class="margin-period-row is-group is-margin">
              <span></span><strong class="margin-period-group is-financing">融資</strong><strong class="margin-period-group is-short">融券</strong><span></span><span></span>
            </div>
            <div class="margin-period-row is-head is-margin">
              <span>日期</span><span>增減</span><span>餘額</span><span>使用率%</span><span>增減</span><span>餘額</span><span>使用率%</span><span>券資比</span><span>資券互抵</span>
            </div>
            ${rows.map((row) => `
              <div class="margin-period-row is-margin">
                <span>${escapeHtml(formatMarginDate(row, activePeriod.key !== "day"))}</span>
                <strong class="${valueToneClass(row.financingChange)}">${formatLotsPlain(row.financingChange, true)}</strong>
                <strong>${formatLotsPlain(row.financingBalance)}</strong>
                <strong>${formatPercentText(row.financingUtilizationRate)}</strong>
                <strong class="${valueToneClass(row.shortChange)}">${formatLotsPlain(row.shortChange, true)}</strong>
                <strong>${formatLotsPlain(row.shortBalance)}</strong>
                <strong>${formatPercentText(row.shortUtilizationRate)}</strong>
                <strong>${formatPercentText(row.shortFinancingRatio)}</strong>
                <strong>${formatLotsPlain(row.offsetting)}</strong>
              </div>
            `).join("")}
          </div>
        </div>
      `;
      const renderLendingBalanceTable = () => `
        <div class="margin-table-scroll">
          <div class="margin-period-grid is-lending">
            <div class="margin-period-row is-group is-lending">
              <span></span><strong class="margin-period-group is-short">融券</strong><strong class="margin-period-group is-lending">借券賣出</strong>
            </div>
            <div class="margin-period-row is-head is-lending">
              <span>日期</span><span>增減</span><span>餘額</span><span>限額</span><span>增減</span><span>餘額</span>
            </div>
            ${rows.map((row) => `
              <div class="margin-period-row is-lending">
                <span>${escapeHtml(formatMarginDate(row, activePeriod.key !== "day"))}</span>
                <strong class="${valueToneClass(row.shortChange)}">${formatLotsPlain(row.shortChange, true)}</strong>
                <strong>${formatLotsPlain(row.shortBalance)}</strong>
                <strong>${formatLotsPlain(row.shortLimit)}</strong>
                <strong class="${valueToneClass(row.lendingChange)}">${formatLotsPlain(row.lendingChange, true)}</strong>
                <strong>${formatLotsPlain(row.lendingBalance)}</strong>
              </div>
            `).join("")}
          </div>
        </div>
      `;
      return `
        <div class="chip-visual-card margin-period-card">
          <div class="chip-visual-head"><span>${activeTableType === "lendingBalance" ? "借券賣出餘額" : "資券餘額"}${activePeriod.title}增減</span><strong>${escapeHtml(rows[0]?.date ? formatMarginDate(rows[0]) : margin.date || "--")}</strong></div>
          ${controls}
          ${activeTableType === "lendingBalance" ? renderLendingBalanceTable() : renderMarginBalanceTable()}
        </div>
      `;
    };
    const renderMarginRows = () => {
      const overview = renderMarginOverviewRows();
      const daily = renderMarginDailyRows();
      if (overview || daily) return `${overview}${daily}`;
      return `
        <div class="chip-data-table">
          <div class="chip-data-row is-head"><span>項目</span><span>買進/賣出</span><span>償還</span><span>增減</span><span>餘額</span></div>
          <div class="chip-data-row"><span>融資</span><strong>${formatLots(margin.financingBuy)}</strong><strong>${formatLots(margin.financingCashRedemption)}</strong><strong>${formatLots(financingChange, true)}</strong><strong>${formatLots(financingBalance)}</strong></div>
          <div class="chip-data-row"><span>融券</span><strong>${formatLots(margin.shortSell)}</strong><strong>${formatLots(margin.shortStockRedemption)}</strong><strong>${formatLots(shortChange, true)}</strong><strong>${formatLots(shortBalance)}</strong></div>
        </div>
      `;
    };
    const renderMarginBalanceVisual = () => {
      const chartRows = Array.isArray(margin.marginBalanceChartRows) ? margin.marginBalanceChartRows : [];
      const sourceRows = (chartRows.length ? chartRows : marginDailyRows)
        .map((row) => ({
          ...row,
          date: normalizeInstitutionDate(row?.date || row?.fullDate || ""),
          label: row?.label || String(row?.date || "").slice(5).replace("-", "/"),
          price: numberValue(row?.closePrice),
          financing: numberValue(row?.financingBalance),
          financingChange: numberValue(row?.financingChange),
          short: numberValue(row?.shortBalance),
          shortChange: numberValue(row?.shortChange),
          lending: numberValue(row?.lendingBalance),
          lendingChange: numberValue(row?.lendingChange),
          changePct: numberValue(row?.changePct),
        }))
        .filter((row) => row.date)
        .sort((left, right) => String(left.date || "").localeCompare(String(right.date || "")));
      if (sourceRows.length < 2) {
        return "";
      }

      const marginRangeOptions = [
        { key: "1m", label: "1個月", days: 31, fallbackCount: 30 },
        { key: "3m", label: "3個月", days: 93, fallbackCount: 90 },
        { key: "6m", label: "6個月", days: 186, fallbackCount: 182 },
        { key: "1y", label: "1年", days: 366, fallbackCount: 365 },
      ];
      const activeMarginRangeKey = stockMarginRangeState.get(stateKey) || "1m";
      const activeMarginRange = marginRangeOptions.find((item) => item.key === activeMarginRangeKey) || marginRangeOptions[0];
      const latestTime = Math.max(...sourceRows.map((row) => new Date(row.date).getTime()).filter(Number.isFinite));
      const cutoffTime = Number.isFinite(latestTime) ? latestTime - activeMarginRange.days * 24 * 60 * 60 * 1000 : null;
      const rangedRows = cutoffTime
        ? sourceRows.filter((row) => {
            const time = new Date(row.date).getTime();
            return Number.isFinite(time) && time >= cutoffTime && time <= latestTime;
          })
        : [];
      const rows = (rangedRows.length >= 2 ? rangedRows : sourceRows.slice(-activeMarginRange.fallbackCount));
      const width = 760;
      const panelHeight = 64;
      const panelGap = 15;
      const pad = { left: 42, right: 78, top: 14, bottom: 30 };
      const height = pad.top + pad.bottom + panelHeight * 4 + panelGap * 3;
      const usableWidth = width - pad.left - pad.right;
      const step = rows.length > 1 ? usableWidth / (rows.length - 1) : usableWidth;
      const points = rows.map((row, index) => ({
        ...row,
        x: pad.left + (rows.length > 1 ? index * step : usableWidth / 2),
      }));
      const series = [
        { key: "price", label: "股價", valueKey: "price", changeKey: "changePct", valueFormatter: (value) => formatPlainNumber(value, false, Number(value) >= 100 ? 0 : 2), axisFormatter: (value) => formatPlainNumber(value, false, Number(value) >= 100 ? 0 : 2), changeFormatter: (value) => formatPercentText(value, true), panel: 0 },
        { key: "financing", label: "融資餘額", valueKey: "financing", changeKey: "financingChange", valueFormatter: (value) => formatLots(value), axisFormatter: (value) => formatPlainNumber(value, false, 0), changeFormatter: (value) => formatLots(value, true), panel: 1 },
        { key: "short", label: "融券餘額", valueKey: "short", changeKey: "shortChange", valueFormatter: (value) => formatLots(value), axisFormatter: (value) => formatPlainNumber(value, false, 0), changeFormatter: (value) => formatLots(value, true), panel: 2 },
        { key: "lending", label: "借券賣出餘額", valueKey: "lending", changeKey: "lendingChange", valueFormatter: (value) => formatLots(value), axisFormatter: (value) => formatPlainNumber(value, false, 0), changeFormatter: (value) => formatLots(value, true), panel: 3 },
      ];
      const panelTop = (index) => pad.top + index * (panelHeight + panelGap);
      const panelBottom = (index) => panelTop(index) + panelHeight;
      const niceAxisStep = (rawStep) => {
        const value = Math.abs(Number(rawStep) || 0);
        if (!Number.isFinite(value) || value <= 0) return 1;
        const power = Math.pow(10, Math.floor(Math.log10(value)));
        const fraction = value / power;
        const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
        return niceFraction * power;
      };
      const buildMarginAxisStats = (item) => {
        const values = points.map((point) => point[item.valueKey]).filter(Number.isFinite);
        let rawMin = values.length ? Math.min(...values) : 0;
        let rawMax = values.length ? Math.max(...values) : 1;
        const nonNegativeAxis = item.key !== "price";
        if (nonNegativeAxis) rawMin = Math.max(0, rawMin);
        if (rawMax === rawMin) {
          const spread = Math.max(Math.abs(rawMax || 1) * 0.08, 1);
          rawMin -= spread;
          rawMax += spread;
          if (nonNegativeAxis) rawMin = 0;
        }

        if (nonNegativeAxis) {
          let zeroStep = niceAxisStep(Math.max(rawMax, 1) / 2);
          if (rawMin <= zeroStep * 1.25) {
            let tickMax = zeroStep * 2;
            for (let attempt = 0; rawMax > tickMax + zeroStep * 0.02 && attempt < 8; attempt += 1) {
              const nextStep = niceAxisStep(zeroStep * 1.25);
              zeroStep = nextStep > zeroStep ? nextStep : zeroStep * 2;
              tickMax = zeroStep * 2;
            }
            return {
              values,
              minValue: 0,
              maxValue: tickMax + zeroStep * 0.04,
              ticks: [tickMax, zeroStep, 0],
            };
          }
        }

        const rawRange = Math.max(rawMax - rawMin, Math.abs(rawMax || 1) * 0.04, 1);
        let step = niceAxisStep(rawRange / 2);
        let tickMin = 0;
        let tickMax = 0;
        for (let attempt = 0; attempt < 8; attempt += 1) {
          tickMin = Math.floor(rawMin / step) * step;
          if (nonNegativeAxis) tickMin = Math.max(0, tickMin);
          tickMax = tickMin + step * 2;
          while (rawMax > tickMax + step * 0.02 && tickMin + step <= rawMin) {
            tickMin += step;
            tickMax += step;
          }
          if (rawMax <= tickMax + step * 0.02 || attempt === 7) break;
          const nextStep = niceAxisStep(step * 1.25);
          step = nextStep > step ? nextStep : step * 2;
        }
        const topOverflow = Math.max(0, rawMax - tickMax);
        const bottomOverflow = Math.max(0, tickMin - rawMin);
        return {
          values,
          minValue: Math.max(nonNegativeAxis ? 0 : -Infinity, tickMin - Math.max(bottomOverflow, step * 0.04)),
          maxValue: tickMax + Math.max(topOverflow, step * 0.04),
          ticks: [tickMax, tickMin + step, tickMin],
        };
      };
      const seriesStats = new Map(series.map((item) => [item.key, buildMarginAxisStats(item)]));
      const yFor = (seriesItem, value) => {
        const stats = seriesStats.get(seriesItem.key);
        const top = panelTop(seriesItem.panel);
        const bottom = panelBottom(seriesItem.panel);
        if (!stats || !Number.isFinite(value)) return bottom;
        return top + ((stats.maxValue - value) / Math.max(stats.maxValue - stats.minValue, 1)) * (bottom - top);
      };
      const linePath = (seriesItem) => points
        .filter((point) => Number.isFinite(point[seriesItem.valueKey]))
        .map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(2)} ${yFor(seriesItem, point[seriesItem.valueKey]).toFixed(2)}`)
        .join(" ");
      const areaPath = (seriesItem) => {
        const usable = points.filter((point) => Number.isFinite(point[seriesItem.valueKey]));
        if (usable.length < 2) return "";
        const line = usable.map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(2)} ${yFor(seriesItem, point[seriesItem.valueKey]).toFixed(2)}`).join(" ");
        const bottom = panelBottom(seriesItem.panel);
        return `${line} L ${usable.at(-1).x.toFixed(2)} ${bottom.toFixed(2)} L ${usable[0].x.toFixed(2)} ${bottom.toFixed(2)} Z`;
      };
      const panelGrid = series.map((item) => {
        const stats = seriesStats.get(item.key);
        const top = panelTop(item.panel);
        const bottom = panelBottom(item.panel);
        const axisFormatter = item.axisFormatter || item.valueFormatter;
        const tickLines = (Array.isArray(stats?.ticks) ? stats.ticks : [stats?.maxValue, (stats?.maxValue + stats?.minValue) / 2, stats?.minValue])
          .filter(Number.isFinite)
          .map((value) => {
            const y = yFor(item, value);
            const labelY = Math.max(top + 10, Math.min(bottom - 6, y));
            return `
              <line class="chip-margin-grid-line" x1="${pad.left}" y1="${y.toFixed(2)}" x2="${width - pad.right}" y2="${y.toFixed(2)}"></line>
              <text class="chip-margin-axis-label" x="${width - pad.right + 12}" y="${labelY.toFixed(2)}">${escapeHtml(axisFormatter(value))}</text>
            `;
          }).join("");
        return `
          <g class="chip-margin-panel is-${item.key}">
            ${tickLines}
          </g>
        `;
      }).join("");
      const paths = series.map((item) => {
        const path = linePath(item);
        const area = areaPath(item);
        return `
          ${area ? `<path class="chip-margin-area is-${item.key}" d="${area}"></path>` : ""}
          ${path ? `<path class="chip-margin-line is-${item.key}" d="${path}"></path>` : ""}
        `;
      }).join("");
      const tickIndexes = [...new Set([0, Math.floor((rows.length - 1) * 0.2), Math.floor((rows.length - 1) * 0.4), Math.floor((rows.length - 1) * 0.6), Math.floor((rows.length - 1) * 0.8), rows.length - 1])];
      const ticks = tickIndexes.map((index) => {
        const point = points[index];
        if (!point) return "";
        return `<text class="chip-margin-date-label" x="${point.x.toFixed(2)}" y="${height - 8}" text-anchor="${index === 0 ? "start" : index === rows.length - 1 ? "end" : "middle"}">${escapeHtml(point.label || String(point.date || "").slice(5))}</text>`;
      }).join("");
      const zoneWidth = rows.length > 1 ? Math.max(8, step) : usableWidth;
      const hoverZones = points.map((point) => {
        const primarySeries = series.find((item) => Number.isFinite(point[item.valueKey])) || series[0];
        const zoneX = rows.length > 1
          ? Math.max(pad.left, Math.min(width - pad.right - zoneWidth, point.x - zoneWidth / 2))
          : pad.left;
        return `<rect class="margin-hover-zone" x="${zoneX.toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${(height - pad.top - pad.bottom).toFixed(2)}" data-x="${point.x.toFixed(2)}" data-y="${yFor(primarySeries, point[primarySeries.valueKey]).toFixed(2)}" data-date="${escapeHtml(point.date || "--")}" data-price="${escapeHtml(series[0].valueFormatter(point.price))}" data-price-change="${escapeHtml(series[0].changeFormatter(point.changePct))}" data-financing="${escapeHtml(series[1].valueFormatter(point.financing))}" data-financing-change="${escapeHtml(series[1].changeFormatter(point.financingChange))}" data-short="${escapeHtml(series[2].valueFormatter(point.short))}" data-short-change="${escapeHtml(series[2].changeFormatter(point.shortChange))}" data-lending="${escapeHtml(series[3].valueFormatter(point.lending))}" data-lending-change="${escapeHtml(series[3].changeFormatter(point.lendingChange))}"></rect>`;
      }).join("");
      const unavailableLongRange = ["6m", "1y"].includes(activeMarginRange.key) && rows.length < activeMarginRange.fallbackCount * 0.65;
      return `
        <div class="chip-visual-card margin-balance-visual">
          <div class="chip-visual-head"><span>資券餘額變化</span><strong>資料時間：${escapeHtml(margin.date || rows.at(-1)?.date || detail.snapshotDate || "--")}</strong></div>
          <div class="margin-range-buttons" role="group" aria-label="資券餘額期間">
            ${marginRangeOptions.map((option) => `<button class="range-button ${option.key === activeMarginRange.key ? "is-active" : ""}" type="button" data-margin-range="${escapeHtml(option.key)}">${escapeHtml(option.label)}</button>`).join("")}
          </div>
          ${renderChipVisualLegend([
            { key: "price", label: "股價" },
            { key: "financing", label: "融資餘額" },
            { key: "short", label: "融券餘額" },
            { key: "lending", label: "借券賣出餘額" },
          ])}
          <div class="margin-balance-chart-stage">
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="資券餘額變化圖">
              ${panelGrid}
              ${paths}
              ${ticks}
              <line class="institution-crosshair is-x" data-margin-cursor-x x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
              <circle class="institution-crosshair-dot" data-margin-cursor-dot cx="${pad.left}" cy="${panelTop(0)}" r="4"></circle>
              ${hoverZones}
            </svg>
            <div class="institution-chart-tooltip margin-chart-tooltip" hidden></div>
          </div>
          <p class="institution-chart-note">${unavailableLongRange ? "Yahoo 目前頁面預載未涵蓋完整長區間，已顯示可取得的線上真實資料。" : `顯示 ${rows.length.toLocaleString("zh-TW")} 筆 Yahoo 線上真實資料。`}</p>
        </div>
      `;
    };
    const renderMajorHolderChart = () => {
      const chartRows = Array.isArray(majorData.rows) ? majorData.rows : [];
      const rows = chartRows
        .map((row) => ({
          ...row,
          date: normalizeInstitutionDate(row?.date || ""),
          foreign: numberValue(row?.foreignChipRatio),
          major: numberValue(row?.majorHolderRatio),
          director: numberValue(row?.directorHoldingRatio),
          price: numberValue(row?.price),
        }))
        .filter((row) => row.date && (
          Number.isFinite(row.foreign)
          || Number.isFinite(row.major)
          || Number.isFinite(row.director)
          || Number.isFinite(row.price)
        ))
        .sort((left, right) => String(left.date || "").localeCompare(String(right.date || "")))
        .slice(-260);
      if (rows.length < 2) return "";

      const width = 760;
      const height = 290;
      const pad = { left: 50, right: 64, top: 18, bottom: 56 };
      const plotHeight = height - pad.top - pad.bottom;
      const usableWidth = width - pad.left - pad.right;
      const step = rows.length > 1 ? usableWidth / (rows.length - 1) : usableWidth;
      const points = rows.map((row, index) => ({
        ...row,
        x: pad.left + (rows.length > 1 ? index * step : usableWidth / 2),
        label: String(row.date || "").replace(/-/g, "/"),
      }));

      const niceAxisStep = (rawStep) => {
        const value = Math.abs(Number(rawStep) || 0);
        if (!Number.isFinite(value) || value <= 0) return 1;
        const power = Math.pow(10, Math.floor(Math.log10(value)));
        const fraction = value / power;
        const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
        return niceFraction * power;
      };
      const prices = points.map((item) => item.price).filter(Number.isFinite);
      const rawPriceMin = prices.length ? Math.min(...prices) : 0;
      const rawPriceMax = prices.length ? Math.max(...prices) : 1;
      let priceStep = niceAxisStep(Math.max(rawPriceMax - rawPriceMin, Math.abs(rawPriceMax || 1) * 0.08, 1) / 7);
      let priceAxisMin = Math.floor(rawPriceMin / priceStep) * priceStep;
      let priceAxisMax = Math.ceil(rawPriceMax / priceStep) * priceStep;
      for (let guard = 0; (priceAxisMax - priceAxisMin) / priceStep > 8 && guard < 8; guard += 1) {
        priceStep = niceAxisStep(priceStep * 1.8);
        priceAxisMin = Math.floor(rawPriceMin / priceStep) * priceStep;
        priceAxisMax = Math.ceil(rawPriceMax / priceStep) * priceStep;
      }
      if (priceAxisMax <= priceAxisMin) priceAxisMax = priceAxisMin + priceStep;
      const priceTicks = [];
      for (let value = priceAxisMin; value <= priceAxisMax + priceStep * 0.02; value += priceStep) {
        priceTicks.push(value);
      }

      const yPercent = (value) => pad.top + ((100 - Math.max(0, Math.min(100, value || 0))) / 100) * plotHeight;
      const yPrice = (value) => pad.top + ((priceAxisMax - value) / Math.max(priceAxisMax - priceAxisMin, 1)) * plotHeight;
      const path = (key, yGetter) => points
        .filter((item) => Number.isFinite(item[key]))
        .map((item, index) => `${index ? "L" : "M"} ${item.x.toFixed(2)} ${yGetter(item[key]).toFixed(2)}`)
        .join(" ");
      const pricePath = path("price", yPrice);
      const areaPath = pricePath
        ? `${pricePath} L ${points.at(-1).x.toFixed(2)} ${yPrice(priceAxisMin).toFixed(2)} L ${points[0].x.toFixed(2)} ${yPrice(priceAxisMin).toFixed(2)} Z`
        : "";
      const percentTicks = [100, 80, 60, 40, 20, 0];
      const gridLines = percentTicks.map((value) => {
        const y = yPercent(value);
        return `
          <line class="chip-holder-grid-line" x1="${pad.left}" y1="${y.toFixed(2)}" x2="${width - pad.right}" y2="${y.toFixed(2)}"></line>
          <text class="chip-holder-axis-label is-percent" x="${pad.left - 8}" y="${y.toFixed(2)}">${value}%</text>
        `;
      }).join("");
      const priceAxisLabels = priceTicks.map((value) => {
        const y = yPrice(value);
        return `<text class="chip-holder-axis-label is-price" x="${width - pad.right + 8}" y="${y.toFixed(2)}">${escapeHtml(formatPlainNumber(value, false, 0))}</text>`;
      }).join("");
      const tickIndexes = [...new Set([
        0,
        Math.floor((rows.length - 1) * 0.12),
        Math.floor((rows.length - 1) * 0.24),
        Math.floor((rows.length - 1) * 0.36),
        Math.floor((rows.length - 1) * 0.48),
        Math.floor((rows.length - 1) * 0.60),
        Math.floor((rows.length - 1) * 0.72),
        Math.floor((rows.length - 1) * 0.84),
        rows.length - 1,
      ])];
      const dateTicks = tickIndexes.map((index) => {
        const point = points[index];
        if (!point) return "";
        return `<text class="chip-holder-date-label" x="${point.x.toFixed(2)}" y="${height - 12}" transform="rotate(-45 ${point.x.toFixed(2)} ${height - 12})">${escapeHtml(point.label)}</text>`;
      }).join("");
      const zoneWidth = rows.length > 1 ? Math.max(8, step) : usableWidth;
      const hoverZones = points.map((point) => {
        const zoneX = rows.length > 1
          ? Math.max(pad.left, Math.min(width - pad.right - zoneWidth, point.x - zoneWidth / 2))
          : pad.left;
        const primaryY = Number.isFinite(point.major)
          ? yPercent(point.major)
          : Number.isFinite(point.price) ? yPrice(point.price) : pad.top + plotHeight / 2;
        return `<rect class="holder-hover-zone" x="${zoneX.toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${plotHeight.toFixed(2)}" data-x="${point.x.toFixed(2)}" data-y="${primaryY.toFixed(2)}" data-y-price="${Number.isFinite(point.price) ? yPrice(point.price).toFixed(2) : ""}" data-y-foreign="${Number.isFinite(point.foreign) ? yPercent(point.foreign).toFixed(2) : ""}" data-y-major="${Number.isFinite(point.major) ? yPercent(point.major).toFixed(2) : ""}" data-y-director="${Number.isFinite(point.director) ? yPercent(point.director).toFixed(2) : ""}" data-date="${escapeHtml(point.label || "--")}" data-price="${escapeHtml(formatPlainNumber(point.price, false, Number(point.price) >= 100 ? 0 : 2))}" data-foreign="${escapeHtml(formatPercentText(point.foreign))}" data-major="${escapeHtml(formatPercentText(point.major))}" data-director="${escapeHtml(formatPercentText(point.director))}"></rect>`;
      }).join("");

      return `
        <div class="chip-visual-card major-holder-chart">
          <div class="chip-visual-head">
            <span>大戶籌碼 <i class="chip-info-icon" title="同步 Yahoo 股市大戶籌碼，左軸為籌碼比例，右軸為股價。">i</i></span>
            <strong>資料時間：${escapeHtml(majorData.date || rows.at(-1)?.date || holders.date || "--")}</strong>
          </div>
          ${renderChipVisualLegend([
            { key: "price", label: "股價" },
            { key: "foreign", label: "外資籌碼" },
            { key: "major", label: "大戶籌碼" },
            { key: "director", label: "董監持股" },
          ])}
          <div class="major-holder-chart-stage">
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="大戶籌碼趨勢圖">
              <line class="chip-chart-axis" x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}"></line>
              ${gridLines}
              ${priceAxisLabels}
              ${areaPath ? `<path class="chip-holder-price-area" d="${areaPath}"></path>` : ""}
              ${pricePath ? `<path class="chip-holder-price-line" d="${pricePath}"></path>` : ""}
              <path class="chip-holder-line is-foreign" d="${path("foreign", yPercent)}"></path>
              <path class="chip-holder-line is-major" d="${path("major", yPercent)}"></path>
              <path class="chip-holder-line is-director" d="${path("director", yPercent)}"></path>
              ${dateTicks}
              <line class="institution-crosshair is-x" data-holder-cursor-x x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
              <circle class="institution-crosshair-dot chip-holder-dot is-price" data-holder-cursor-dot="price" cx="${pad.left}" cy="${pad.top}" r="4"></circle>
              <circle class="institution-crosshair-dot chip-holder-dot is-foreign" data-holder-cursor-dot="foreign" cx="${pad.left}" cy="${pad.top}" r="4"></circle>
              <circle class="institution-crosshair-dot chip-holder-dot is-major" data-holder-cursor-dot="major" cx="${pad.left}" cy="${pad.top}" r="4"></circle>
              <circle class="institution-crosshair-dot chip-holder-dot is-director" data-holder-cursor-dot="director" cx="${pad.left}" cy="${pad.top}" r="4"></circle>
              ${hoverZones}
            </svg>
            <div class="institution-chart-tooltip holder-chart-tooltip" hidden></div>
          </div>
        </div>
      `;
    };
    const renderHolderRows = () => `
      <div class="holder-ratio-chart chip-holder-panel">
        <div class="holder-ratio-bar">
          <span class="holder-ratio-segment is-large" style="width:${Math.max(0, Math.min(100, large || 0))}%"></span>
          <span class="holder-ratio-segment is-other" style="width:${Math.max(0, Math.min(100, other || 0))}%"></span>
          <span class="holder-ratio-segment is-retail" style="width:${Math.max(0, Math.min(100, retail || 0))}%"></span>
        </div>
        <div class="chip-data-table">
          <div class="chip-data-row is-head"><span>資料日</span><span>大戶</span><span>外資籌碼</span><span>董監持股</span><span>股價</span></div>
          ${(Array.isArray(majorData.rows) && majorData.rows.length ? majorData.rows.slice(0, 12) : [{ date: holders.date, majorHolderRatio: large, foreignChipRatio: foreignChip, directorHoldingRatio: directorHolding, price: detail.close }]).map((row) => `
            <div class="chip-data-row"><span>${escapeHtml(row.date || "--")}</span><strong>${formatPercentText(row.majorHolderRatio)}</strong><strong>${formatPercentText(row.foreignChipRatio)}</strong><strong>${formatPercentText(row.directorHoldingRatio)}</strong><strong>${escapeHtml(row.price ?? "--")}</strong></div>
          `).join("")}
        </div>
      </div>
    `;
    const renderActiveContent = () => {
      if (activeCard.key === "institutional") return `${renderMetrics(activeCard)}${renderInstitutionOverview()}${renderInstitutionChart()}${renderInstitutionRows()}`;
      if (activeCard.key === "mainForce") return `${renderMetrics(activeCard)}${renderBrokerBalanceBar()}<div class="chip-broker-grid">${renderBrokerRowsWithBars(broker.buyBrokers, "買超券商", "buy")}${renderBrokerRowsWithBars(broker.sellBrokers, "賣超券商", "sell")}</div>`;
      if (activeCard.key === "margin") return `${renderMetrics(activeCard)}${renderMarginBalanceVisual()}${Object.keys(margin).length ? renderMarginRows() : '<p class="stock-detail-empty">資券資料目前未取得。</p>'}`;
      return `${renderMetrics(activeCard)}${renderMajorHolderChart()}${holderAvailable ? renderHolderRows() : `<p class="stock-detail-empty">正在同步 Yahoo 大戶籌碼資料。</p>`}`;
    };
    return `
      <section class="chip-tab-shell" aria-label="籌碼分頁">
        <div class="chip-tab-bar" role="tablist">
          ${cards.map((card) => `<button class="${card.key === activeCard.key ? "is-active" : ""}" type="button" data-chip-tab="${card.key}" role="tab">${escapeHtml(card.tab)}</button>`).join("")}
        </div>
        <article class="chip-tab-panel is-${escapeHtml(activeCard.tone || "flat")}">
          <div class="chip-summary-head">
            <div><span>${escapeHtml(activeCard.key === "mainForce" ? "Broker flow" : activeCard.key === "largeHolder" ? "Holder" : activeCard.key === "margin" ? "Margin" : "Institution")}</span><strong>${escapeHtml(activeCard.title)}</strong></div>
            <b>${escapeHtml(activeCard.label || "--")}</b>
          </div>
          ${renderActiveContent()}
          <p class="chip-source-note">${escapeHtml(activeCard.sourceNote || "")} ${activeCard.sourceLink ? `<a href="${safeUrl(activeCard.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
        </article>
        ${renderHolderDistribution(holderVisualDistribution)}
      </section>
    `;
  };

  const analysisHtml = analysisSections.map((section) => `
    <article class="analysis-card ${section.key === "chips" ? "analysis-card-chips" : ""}">
      <div class="card-title-row">
        <h4>${section.title}</h4>
      </div>
      <p class="card-copy">${section.summary}</p>
      ${section.key === "chips" ? renderChipDashboard(section) : ""}
      <ul class="analysis-list">
        ${(section.items || []).map((item) => `<li>${item}</li>`).join("")}
      </ul>
    </article>
  `).join("");
  const companyNews = Array.isArray(detail.companyNews) ? detail.companyNews : [];
  const isEtfDetail = Boolean(detail.isEtf);
  const newsKicker = isEtfDetail ? "ETF news" : "Company news";
  const newsSubtitle = isEtfDetail
    ? `${escapeHtml(detail.code)} ${escapeHtml(detail.name)} 近期 ETF 新聞、配息公告與發行投信消息。`
    : `${escapeHtml(detail.code)} ${escapeHtml(detail.name)} 近期公司新聞與公開消息。`;
  const newsEmptyText = isEtfDetail
    ? "目前未取得即時 ETF 新聞，請使用下方 ETF 消息來源查詢。"
    : "目前未取得近期公司新聞，可使用下方來源連結查詢。";
  const companyNewsHtml = `
    <section class="company-news-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">${newsKicker}</p>
          <h3>消息面</h3>
          <p class="chart-subtitle">${newsSubtitle}</p>
        </div>
        <span class="chip chip-blue">${companyNews.length} 則消息</span>
      </div>
      <div class="company-news-list">
        ${companyNews.map((item) => `
          <a class="company-news-item" href="${safeUrl(item.link)}" target="_blank" rel="noreferrer noopener">
            <div>
              <strong>${escapeHtml(item.title)}</strong>
              <span>${escapeHtml(item.source || "新聞來源")} · ${escapeHtml(item.publishedAt || "--")}</span>
            </div>
            <b>閱讀消息</b>
          </a>
        `).join("") || `<p class="stock-detail-empty">${newsEmptyText}</p>`}
      </div>
      <div class="company-news-sources">
        ${detail.newsLinks?.yahoo ? `<a href="${safeUrl(detail.newsLinks.yahoo)}" target="_blank" rel="noreferrer noopener">${isEtfDetail ? "Yahoo ETF 新聞" : "Yahoo 個股新聞"}</a>` : ""}
        ${detail.newsLinks?.google ? `<a href="${safeUrl(detail.newsLinks.google)}" target="_blank" rel="noreferrer noopener">Google 新聞搜尋</a>` : ""}
        ${detail.newsLinks?.mops ? `<a href="${safeUrl(detail.newsLinks.mops)}" target="_blank" rel="noreferrer noopener">公開資訊觀測站重大訊息</a>` : ""}
      </div>
      <p class="stock-theory-note">新聞標題與時間由外部來源彙整，請點入原始頁面核對完整內容及發布時間。</p>
    </section>
  `;

  const renderEtfDividendCard = () => {
    const info = detail.etfDividendInfo || {};
    const latest = info.latest || {};
    const totals = info.totals || {};
    const recent = Array.isArray(info.recent) ? info.recent : [];
    if (!detail.isEtf || (!latest.cashDividend && !recent.length)) return "";
    return `
      <section class="company-news-card etf-dividend-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">ETF Dividend</p>
            <h3>${escapeHtml(info.title || "ETF 股利資訊")}</h3>
            <p class="chart-subtitle">${escapeHtml(info.summary || "同步 ETF 實際配息與除息紀錄。")}</p>
          </div>
          <span class="chip chip-gold">${escapeHtml(latest.period || "最新配息")}</span>
        </div>
        <div class="etf-dividend-metrics">
          <div><span>最新現金股利</span><strong>${escapeHtml(latest.cashDividend || "--")} 元</strong></div>
          <div><span>除息日</span><strong>${escapeHtml(latest.exDate || "--")}</strong></div>
          <div><span>發放日</span><strong>${escapeHtml(latest.cashPayDate || "--")}</strong></div>
          <div><span>累計股利</span><strong>${escapeHtml(totals.totalDividends || "--")} 元</strong></div>
          <div><span>平均殖利率</span><strong>${escapeHtml(totals.averageYield || "--")}%</strong></div>
          <div><span>連續配息年數</span><strong>${escapeHtml(totals.continuousYears || "--")} 年</strong></div>
        </div>
        <div class="etf-dividend-list">
          ${recent.slice(0, 4).map((item) => `
            <div class="etf-dividend-row">
              <div>
                <strong>${escapeHtml(item.year || "--")} ${escapeHtml(item.period || "")}</strong>
                <span>除息 ${escapeHtml(item.exDate || "--")} · 發放 ${escapeHtml(item.cashPayDate || "--")}</span>
              </div>
              <div>
                <b>${escapeHtml(item.cashDividend || "--")} 元</b>
                <small>殖利率 ${escapeHtml(item.yieldByExDate || "--")}% · 填息 ${escapeHtml(item.recoveryDays || "--")} 天</small>
              </div>
            </div>
          `).join("")}
        </div>
        <p class="stock-theory-note">${escapeHtml(info.sourceNote || "ETF 股利資料請以發行投信公告為準。")} ${info.sourceLink ? `<a href="${safeUrl(info.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
      </section>
    `;
  };

  const etfDividendHtml = renderEtfDividendCard();

  const historyHtml = (detail.recentDays || []).map((day) => `
    <div class="history-row">
      <span>${day.date}</span>
      <span>收盤：${day.close}</span>
      <span>最高：${day.high}</span>
      <span>最低：${day.low}</span>
      <span>成量：${day.volume}</span>
    </div>
  `).join("") || '<div class="stock-detail-empty">無可用歷史資料。</div>';

  const renderValuationBars = (key, label, unit = "") => {
    const points = (detail.valuationHistory || [])
      .map((item) => ({ date: item.date, value: Number(item[key]) }))
      .filter((item) => Number.isFinite(item.value));
    if (!points.length) {
      return `<div class="valuation-mini-chart"><h5>${label}</h5><p class="stock-detail-empty">暫無歷史資料</p></div>`;
    }
    const maxValue = Math.max(...points.map((item) => item.value), 0.01);
    return `
      <div class="valuation-mini-chart">
        <h5>${label}</h5>
        <div class="valuation-bars">
          ${points.map((item) => {
            const height = Math.max(5, (item.value / maxValue) * 100);
            const dateLabel = String(item.date || "--").replaceAll("-", "/");
            return `
              <div class="valuation-bar-item" title="${item.date} ${label} ${item.value.toFixed(2)}${unit}">
                <strong>${item.value.toFixed(2)}${unit}</strong>
                <span class="valuation-bar-track"><i style="height:${height}%"></i></span>
                <small>${dateLabel}</small>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  };

  const profile = detail.companyProfile || {};
  const isProfileMissing = (value) => {
    const text = String(value ?? "").trim();
    return !text || ["--", "-", "N/A", "NA", "--%", "-%"].includes(text);
  };
  const displayProfile = Object.keys(profile).length
    ? profile
    : {
        fullName: `${detail.code || ""} ${detail.name || ""}`.trim(),
        industry: detail.marketLabel || detail.market || "--",
        website: detail.sourceLink || detail.newsLinks?.yahoo || "",
        sourceStatus: "fallback",
        sourceNote: "公司基本資料仍在同步；目前先顯示個股行情可判斷的市場資訊與來源連結。",
      };
  const profileRows = [
    ["市場 / 產業", [detail.marketLabel || detail.market, displayProfile.industry].filter((item) => !isProfileMissing(item)).join(" / ")],
    ["董事長", displayProfile.chairman],
    ["總經理", displayProfile.generalManager],
    ["實收資本額", displayProfile.capital],
    ["成立日期", displayProfile.establishedDate],
    ["掛牌日期", displayProfile.listingDate],
    ["電話", displayProfile.telephone],
    ["地址", displayProfile.address, "is-wide"],
    ["估值摘要", displayProfile.summary, "is-wide"],
  ].filter(([, value]) => !isProfileMissing(value));
  const profileSourceLabel = displayProfile.sourceStatus === "fallback" ? "資料待補" : "官方資料";
  const websiteLabel = displayProfile.sourceStatus === "fallback" ? "Yahoo 個股資料" : "公司網站";
  const companyProfileHtml = `
    <aside class="company-profile ${displayProfile.sourceStatus === "fallback" ? "is-fallback" : ""}">
      <div>
        <p class="eyebrow">Company profile</p>
        <h4>${escapeHtml(displayProfile.fullName || `${detail.code} ${detail.name}`)}</h4>
      </div>
      <span class="chip ${displayProfile.sourceStatus === "fallback" ? "chip-blue" : "chip-gold"}">${escapeHtml(profileSourceLabel)}</span>
      <dl>
        ${profileRows.map(([label, value, className]) => `
          <div class="${className || ""}"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "--")}</dd></div>
        `).join("") || '<div class="is-wide"><dt>資料狀態</dt><dd>公司基本資料仍在同步</dd></div>'}
      </dl>
      <div class="company-profile-links">
        ${displayProfile.website ? `<a class="company-website" href="${safeUrl(displayProfile.website)}" target="_blank" rel="noreferrer noopener">${escapeHtml(websiteLabel)}</a>` : ""}
        ${displayProfile.sourceLink ? `<a class="company-website" href="${safeUrl(displayProfile.sourceLink)}" target="_blank" rel="noreferrer noopener">交易所來源</a>` : ""}
      </div>
      ${displayProfile.sourceNote ? `<p class="stock-theory-note">${escapeHtml(displayProfile.sourceNote)}</p>` : ""}
    </aside>
  `;

  const renderEtfComponentsCard = () => {
    const components = detail.etfComponents || {};
    const holdings = Array.isArray(components.holdings) ? components.holdings : [];
    if (!holdings.length) return "";
    return `
      <section class="valuation-company-card etf-components-card">
        <div class="card-title-row">
          <div>
            <h3>${escapeHtml(components.title || "ETF 成分股比例")}</h3>
            <p class="chart-subtitle">${escapeHtml(components.summary || "ETF 以成分股或追蹤標的配置觀察，不適用一般個股估值與公司資料。")}</p>
          </div>
          <span class="chip chip-blue">${holdings.length} 項配置</span>
        </div>
        <div class="etf-holding-list">
          ${holdings.map((item) => {
            const weight = Math.max(0, Math.min(100, Number(item.weight) || 0));
            return `
              <div class="etf-holding-row">
                <div>
                  <strong>${escapeHtml(item.name || "--")}</strong>
                  <span>${escapeHtml(item.code || "--")}</span>
                </div>
                <div class="etf-holding-bar"><i style="width:${weight}%"></i></div>
                <b>${weight.toFixed(1)}%</b>
              </div>
            `;
          }).join("")}
        </div>
        <p class="stock-theory-note">${escapeHtml(components.sourceNote || "實際持股比例請以投信公告為準。")} ${components.sourceLink ? `<a href="${safeUrl(components.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
      </section>
    `;
  };

  const valuationAndCompanyHtml = detail.isEtf || detail.etfComponents
    ? renderEtfComponentsCard()
    : `
      <section class="valuation-company-card">
        <div class="card-title-row">
          <div>
            <h3>估值歷史與公司資料</h3>
            <p class="chart-subtitle">近六個月月底交易日；上市股利依官方收盤價與殖利率還原。</p>
          </div>
        </div>
        <div class="valuation-company-grid">
          <div class="valuation-chart-grid">
            ${renderValuationBars("peRatio", "本益比")}
            ${renderValuationBars("dividendYield", "殖利率", "%")}
            ${renderValuationBars("dividendPerShare", "每股股利", " 元")}
            ${renderValuationBars("pbRatio", "股價淨值比")}
          </div>
          ${companyProfileHtml}
        </div>
      </section>
    `;

  const technicalTheory = analyzeTechnicalTheories(detail);
  const technicalTrendSummary = buildTechnicalTrendSummary(detail, technicalTheory);
  technicalSummaryHtml = `
    <article class="stock-market-context technical-trend-summary is-${technicalTrendSummary.tone}">
      <div class="technical-summary-head">
        <div class="stock-theory-title">
          <span>Technical outlook</span>
          <h4>技術分析總結</h4>
        </div>
        <div class="technical-summary-score">
          <b>${technicalTrendSummary.score}</b>
          <span>${escapeHtml(technicalTrendSummary.label)}</span>
        </div>
      </div>
      <p>${escapeHtml(technicalTrendSummary.summary)}</p>
      <div class="technical-summary-timeframes">
        ${technicalTrendSummary.timeframes.map((item) => `
          <span><small>${escapeHtml(item.label)}</small><b>${escapeHtml(item.value)}</b></span>
        `).join("")}
        <span><small>分析信心</small><b>${escapeHtml(technicalTrendSummary.confidence)}</b></span>
      </div>
      ${renderTechnicalTrendForecastSummary(technicalTrendSummary)}
      <div class="technical-summary-columns">
        <section>
          <h5>趨勢共振依據</h5>
          <ul>${technicalTrendSummary.confirmations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </section>
        <section>
          <h5>風險與反向訊號</h5>
          <ul>${technicalTrendSummary.risks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </section>
      </div>
      <div class="technical-summary-action">
        <strong>目前風向與操作節奏</strong>
        <span>${escapeHtml(technicalTrendSummary.action)}</span>
      </div>
    </article>
  `;
  const theoryTone = technicalTheory.score >= 3
    ? "positive"
    : technicalTheory.score <= -3
      ? "negative"
      : "neutral";
  const theoryLabel = theoryTone === "positive"
    ? "偏多結構"
    : theoryTone === "negative"
      ? "偏空結構"
      : "中性整理";
  const backtestLearning = technicalTheory.backtestLearning || {};
  const backtestAdjustment = Number(backtestLearning.scoreAdjustment || 0);
  const backtestAdjustmentText = backtestAdjustment > 0
    ? `+${backtestAdjustment} 偏多校準`
    : backtestAdjustment < 0
      ? `${backtestAdjustment} 偏空校準`
      : "0 中性校準";
  const backtestBest = backtestLearning.signals?.[0];
  const backtestPerformance = backtestLearning.performance || {};
  const backtestCostModel = backtestLearning.costModel || {};
  const backtestRiskModel = backtestLearning.riskModel || {};
  const backtestValidation = backtestLearning.validation || {};
  const backtestOriginalValidation = backtestLearning.originalValidation || {};
  const backtestModelRebuild = backtestLearning.modelRebuild || {};
  const backtestForecast = backtestLearning.forecast || {};
  const institutionalFramework = backtestLearning.institutionalFramework || {};
  const institutionalLayers = Array.isArray(institutionalFramework.layers)
    ? institutionalFramework.layers
    : [];
  const institutionalRecent20 = institutionalFramework.recent20 || {};
  const backtestForecastScenarios = Array.isArray(backtestForecast.scenarios)
    ? backtestForecast.scenarios
    : [];
  const backtestPriceTargets = Array.isArray(backtestForecast.priceTargets)
    ? backtestForecast.priceTargets
    : [];
  const backtestSupportText = Number.isFinite(backtestForecast.support)
    ? backtestForecast.support.toFixed(2)
    : "--";
  const backtestResistanceText = Number.isFinite(backtestForecast.resistance)
    ? backtestForecast.resistance.toFixed(2)
    : "--";
  const backtestAtrText = Number.isFinite(backtestForecast.atrPct)
    ? `${backtestForecast.atrPct.toFixed(2)}%`
    : "--";
  const formatBacktestRatio = (value, digits = 2) => (
    Number.isFinite(value) ? value.toFixed(digits) : "--"
  );
  const formatBacktestPercent = (value, digits = 0) => (
    Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : "--"
  );
  const validationTone = backtestValidation.status === "healthy"
    ? "bullish"
    : backtestValidation.status === "watch"
      ? "neutral"
      : backtestValidation.status === "recalibrate" || backtestValidation.status === "rebuild"
        ? "bearish"
        : "neutral";
  const backtestSignalNames = (backtestLearning.signals || [])
    .slice(0, 5)
    .map((item) => item.name)
    .join("、");
  const backtestIntegratedSummary = backtestBest
    ? `整合回測結果以 ${backtestSignalNames || backtestBest.name} 作為主要觀察組合；目前 ${backtestBest.name} 的樣本勝率 ${(backtestBest.winRate * 100).toFixed(0)}%，淨均報酬 ${backtestBest.averageReturn >= 0 ? "+" : ""}${backtestBest.averageReturn.toFixed(2)}%，並已扣除交易成本與納入停損停利檢查。`
    : "目前歷史樣本或訊號數不足，暫不輸出最佳訊號，模型維持中性校準。";
  const backtestBaselineSummary = "分析已整合回溯測試因素基準中的資料品質、估值、技術、籌碼、交易成本、風控、資金管理與績效評估，不再以單一訊號獨立判定模型準確性。";
  const backtestDecisionTips = [
    backtestModelRebuild.status === "rebuilt"
      ? `模型已重建：舊模型 ${backtestModelRebuild.oldModel || "--"} 改為 ${backtestModelRebuild.newModel || "--"}，後續權重以新模型為主。`
      : backtestModelRebuild.status === "failed"
        ? "已嘗試重新建模，但替代模型未通過樣本外校準，暫維持中性權重。"
        : "目前未觸發重新建模條件。",
    backtestValidation.status === "healthy"
      ? "模型通過樣本外校準，可保留目前 AI 權重，但仍需等待價量與趨勢同向確認。"
      : backtestValidation.status === "rebuild"
        ? "模型偵測失真，暫停提高權重，先以人工風控與重新建模為主。"
        : "模型仍需觀察，建議降低單筆部位並等待下一次資料校準。",
    Number.isFinite(backtestForecast.support) && Number.isFinite(backtestForecast.resistance)
      ? `區間參考：接近 ${backtestSupportText} 觀察承接，接近 ${backtestResistanceText} 留意壓力與獲利了結。`
      : "支撐壓力資料不足時，不以單一價位作為進出場依據。",
    backtestPriceTargets.length
      ? `預估股價採區間而非單點：${backtestPriceTargets[0].label}參考中位 ${backtestPriceTargets[0].median.toFixed(2)}，區間 ${backtestPriceTargets[0].lower.toFixed(2)} ~ ${backtestPriceTargets[0].upper.toFixed(2)}。`
      : "預估股價資料不足，暫不輸出價格區間。",
    Number.isFinite(backtestForecast.atrPct) && backtestForecast.atrPct >= 5
      ? `波動偏高，ATR 約 ${backtestAtrText}，停損與部位需同步放寬或縮小部位。`
      : `波動參考 ${backtestAtrText}，可用分批進出降低一次判斷錯誤風險。`,
    backtestAdjustment > 0
      ? "權重偏多時仍需確認量能延續，避免只因回測勝率高而追價。"
      : backtestAdjustment < 0
        ? "權重偏空時優先控管回撤，等待重新站回關鍵均線後再提高信心。"
        : "權重中性時以區間策略與風險報酬比優先，不急著放大部位。",
  ];
  const technicalTheoryHtml = `
    <section class="stock-theory-section">
      <div class="card-title-row">
        <div>
          <h3>進階技術分析理論</h3>
          <p class="chart-subtitle">整合型態、價量、市場廣度、心理線與籌碼指標，透過 ADR、ADL、OBOS、PSY 及多因子一致性動態調整信心。</p>
        </div>
        <span class="stock-theory-score is-${theoryTone}">${theoryLabel} · ${technicalTheory.score > 0 ? "+" : ""}${technicalTheory.score}</span>
      </div>
      <div class="stock-theory-adaptive">
        <strong>多理論共振：${technicalTheory.adaptiveConfidence || "低"}信心</strong>
        <span>${technicalTheory.adaptiveSummary || "目前多空理論尚未形成一致方向"}</span>
      </div>
      <div class="stock-theory-grid">
        <article class="stock-theory-card">
          <div class="stock-theory-title">
            <span>Pattern theory</span>
            <h4>型態技術分析</h4>
          </div>
          <div class="stock-theory-signal-list">
            ${(technicalTheory.theorySignals || []).map((item) => `
              <div class="stock-theory-signal is-${item.direction}">
                <strong>${item.name}</strong>
                <span>${item.text}</span>
              </div>
            `).join("") || `<ul>${(technicalTheory.patterns || []).map((item) => `<li>${item}</li>`).join("")}</ul>`}
          </div>
          ${technicalSummaryHtml}
        </article>
        <article class="stock-theory-card">
          <div class="stock-theory-title">
            <span>Indicator theory</span>
            <h4>指標類技術分析</h4>
          </div>
          <div class="indicator-resonance ${technicalTheory.priceVolumeConflict ? "is-conflict" : technicalTheory.priceVolumeAligned ? "is-aligned" : ""}">
            ${technicalTheory.indicatorSummary || "價量方向尚未形成一致確認"}
          </div>
          <div class="indicator-theory-groups">
            <section>
              <h5>價的技術指標</h5>
              <div class="indicator-signal-list">
                ${(technicalTheory.priceIndicators || []).map((item) => item.movingAverage ? `
                  <div class="indicator-signal moving-average-analysis is-${item.direction}">
                    <div class="moving-average-head">
                      <div>
                        <strong>${escapeHtml(item.name)}</strong>
                        <span>${escapeHtml(item.movingAverage.headline)}</span>
                      </div>
                      <b>${item.movingAverage.score > 0 ? "+" : ""}${item.movingAverage.score}</b>
                    </div>
                    <div class="moving-average-periods">
                      ${item.movingAverage.periods.map((period) => `
                        <div>
                          <strong>${escapeHtml(period.label)}</strong>
                          <b>${period.value.toFixed(2)}</b>
                          <span>${escapeHtml(period.role)}</span>
                          <small>${escapeHtml(period.slope)} · ${escapeHtml(period.position)}</small>
                        </div>
                      `).join("")}
                    </div>
                    <div class="moving-average-sections">
                      <section>
                        <h6>趨勢與交叉</h6>
                        <ul>
                          ${item.movingAverage.crosses.map((text) => `<li>${escapeHtml(text)}</li>`).join("")}
                          ${item.movingAverage.confirmations.map((text) => `<li>${escapeHtml(text)}</li>`).join("")}
                        </ul>
                      </section>
                      <section>
                        <h6>實戰判讀</h6>
                        <p>${escapeHtml(item.movingAverage.practical)}</p>
                        <p>${escapeHtml(item.movingAverage.suitability)}</p>
                      </section>
                    </div>
                    <div class="moving-average-risk">
                      <strong>風險提醒</strong>
                      <span>${item.movingAverage.risks.map((text) => escapeHtml(text)).join("；")}</span>
                    </div>
                  </div>
                ` : `
                  <div class="indicator-signal is-${item.direction}">
                    <strong>${item.name}</strong>
                    <span>${item.value}</span>
                    <small>${item.text}</small>
                  </div>
                `).join("") || "<p>價格指標資料不足</p>"}
              </div>
            </section>
            <section>
              <h5>量的技術指標</h5>
              <div class="indicator-signal-list">
                ${(technicalTheory.volumeIndicators || []).map((item) => `
                  <div class="indicator-signal is-${item.direction}">
                    <strong>${item.name}</strong>
                    <span>${item.value}</span>
                    <small>${item.text}</small>
                  </div>
                `).join("") || "<p>量能指標資料不足</p>"}
              </div>
            </section>
            <section>
              <h5>市場廣度、心理與籌碼指標</h5>
              <div class="indicator-resonance ${technicalTheory.breadthConflict ? "is-conflict" : technicalTheory.breadthAligned ? "is-aligned" : ""}">
                ${technicalTheory.breadthSummary || "市場廣度與籌碼方向尚未形成一致確認"}
              </div>
              <div class="indicator-signal-list">
                ${(technicalTheory.breadthIndicators || []).map((item) => `
                  <div class="indicator-signal is-${item.direction}">
                    <strong>${item.name}</strong>
                    <span>${item.value}</span>
                    <small>${item.text}</small>
                  </div>
                `).join("") || "<p>市場廣度或籌碼資料不足</p>"}
              </div>
            </section>
          </div>
        </article>
      </div>
      <div class="stock-backtest-learning">
        <div class="backtest-learning-head">
          <span>Backtest learning</span>
          <strong>回溯學習校準</strong>
          <small>${backtestLearning.summary || "歷史樣本不足，暫不調整 AI 權重"}</small>
        </div>
        <div class="institutional-backtest-card is-${escapeHtml(institutionalFramework.judgement?.tone || "neutral")}">
          <div class="institutional-backtest-head">
            <div>
              <span>Institutional multi-factor</span>
              <strong>機構多因子回溯統整</strong>
              <small>依市場環境、資金面、趨勢面與進出場訊號逐層驗證，不以單一技術指標直接下結論。</small>
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
                <div>
                  <strong>${escapeHtml(layer.label)}</strong>
                  <span>權重 ${layer.weight}%</span>
                </div>
                <b>${Math.round(layer.score)}</b>
                <div class="institutional-score-track">
                  <i style="width:${Math.round(layer.score)}%"></i>
                </div>
                <small>資料涵蓋 ${Math.round(layer.coverage * 100)}% · ${(layer.available || []).map((item) => escapeHtml(item.name)).join("、") || "等待資料"}</small>
              </article>
            `).join("")}
          </div>
          <div class="institutional-monitor-grid">
            <div>
              <span>市場狀態</span>
              <strong>${escapeHtml(institutionalFramework.marketState || "--")}</strong>
            </div>
            <div>
              <span>近 20 筆勝率</span>
              <strong>${formatBacktestPercent(institutionalRecent20.winRate)} · ${escapeHtml(institutionalRecent20.winState || "樣本不足")}</strong>
            </div>
            <div>
              <span>近 20 筆 PF</span>
              <strong>${formatBacktestRatio(institutionalRecent20.profitFactor)} · ${escapeHtml(institutionalRecent20.pfState || "樣本不足")}</strong>
            </div>
            <div>
              <span>近 20 筆 MDD</span>
              <strong>${formatBacktestRatio(institutionalRecent20.maxDrawdown)}% · ${escapeHtml(institutionalRecent20.mddState || "樣本不足")}</strong>
            </div>
          </div>
          <div class="institutional-backtest-body">
            <section>
              <h5>標準分析輸出</h5>
              <ol>
                ${(institutionalFramework.outputSteps || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
              </ol>
            </section>
          </div>
        </div>
        <div class="backtest-forecast-card">
          <div class="backtest-forecast-head">
            <div>
              <span>Scenario forecast</span>
              <strong>未來走勢情境推估</strong>
            </div>
            <small>模型信心：${escapeHtml(backtestForecast.confidence || "低")} · ${escapeHtml(backtestForecast.trendLabel || "區間震盪")}</small>
          </div>
          <p>${escapeHtml(backtestForecast.summary || "回測資料不足，暫以中性震盪情境觀察。")}</p>
          <div class="backtest-forecast-grid">
            ${backtestForecastScenarios.map((item) => `
              <div class="backtest-forecast-item">
                <strong>${escapeHtml(item.label || `${item.days || "--"} 日`)}</strong>
                <span class="is-bullish">偏多 ${Number.isFinite(item.bullish) ? item.bullish : "--"}%</span>
                <span>震盪 ${Number.isFinite(item.neutral) ? item.neutral : "--"}%</span>
                <span class="is-bearish">偏空 ${Number.isFinite(item.bearish) ? item.bearish : "--"}%</span>
              </div>
            `).join("") || '<p class="stock-detail-empty">樣本不足，暫不輸出情境比例。</p>'}
          </div>
          <div class="backtest-forecast-levels">
            <span>支撐區 <b>${backtestSupportText}</b></span>
            <span>壓力區 <b>${backtestResistanceText}</b></span>
            <span>波動參考 <b>${backtestAtrText}</b></span>
          </div>
          ${backtestPriceTargets.length ? `
            <div class="backtest-price-targets">
              <div class="backtest-price-targets-head">
                <strong>預估股價區間</strong>
                <span>以區間與中位價呈現，避免單點喊價</span>
              </div>
              <div class="backtest-price-target-grid">
                ${backtestPriceTargets.map((item) => `
                  <div class="backtest-price-target">
                    <span>${escapeHtml(item.label)}</span>
                    <strong>${item.lower.toFixed(2)} ~ ${item.upper.toFixed(2)}</strong>
                    <small>中位 ${item.median.toFixed(2)}｜預估 ${item.expectedReturnPct >= 0 ? "+" : ""}${item.expectedReturnPct.toFixed(2)}%</small>
                    <em>${escapeHtml(item.basis)}</em>
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ""}
          <p class="backtest-forecast-caveat">${escapeHtml(backtestForecast.caveat || "情境推估只作風險管理參考，不保證未來價格。")}</p>
        </div>
        <div class="backtest-validation-card is-${validationTone}">
          <div class="backtest-validation-head">
            <strong>模型準確性驗證：${escapeHtml(backtestValidation.label || "樣本不足")}</strong>
          </div>
          <p>${escapeHtml(backtestValidation.recommendation || "樣本不足，暫不判定模型失真。")}</p>
          <p>${escapeHtml(backtestIntegratedSummary)}</p>
          <p>${escapeHtml(backtestBaselineSummary)}</p>
          <div class="backtest-validation-grid">
            <span>樣本內勝率 <b>${formatBacktestPercent(backtestValidation.inSample?.winRate)}</b></span>
            <span>樣本外勝率 <b>${formatBacktestPercent(backtestValidation.outSample?.winRate)}</b></span>
            <span>樣本外 MDD <b>${formatBacktestRatio(backtestValidation.outSample?.maxDrawdown)}%</b></span>
            <span>樣本外 PF <b>${formatBacktestRatio(backtestValidation.outSample?.profitFactor)}</b></span>
          </div>
          <ul>
            ${(backtestValidation.reasons || ["未取得模型失真檢查資料"]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </div>
        ${backtestModelRebuild.status && backtestModelRebuild.status !== "not_required" ? `
          <div class="backtest-rebuild-card is-${backtestModelRebuild.status === "rebuilt" ? "bullish" : "bearish"}">
            <div class="backtest-rebuild-head">
              <div>
                <span>Model rebuild</span>
                <strong>模型重新建置：${escapeHtml(backtestModelRebuild.label || "--")}</strong>
              </div>
              <small>原模型狀態：${escapeHtml(backtestOriginalValidation.label || "未提供")}</small>
            </div>
            <p>${escapeHtml(backtestModelRebuild.summary || "尚無重建結果。")}</p>
            <div class="backtest-rebuild-switch">
              <span>舊模型 <b>${escapeHtml(backtestModelRebuild.oldModel || "--")}</b></span>
              <span>新模型 <b>${escapeHtml(backtestModelRebuild.newModel || "尚未通過")}</b></span>
            </div>
            <div class="backtest-rebuild-candidates">
              ${(backtestModelRebuild.candidates || []).map((item) => `
                <div>
                  <strong>${escapeHtml(item.name || "--")}</strong>
                  <span>${escapeHtml(item.status || "--")}｜樣本外勝率 ${formatBacktestPercent(item.outWinRate)}｜PF ${formatBacktestRatio(item.outProfitFactor)}｜MDD ${formatBacktestRatio(item.outMaxDrawdown)}%</span>
                </div>
              `).join("") || '<span>替代模型樣本不足。</span>'}
            </div>
          </div>
        ` : ""}
        <div class="backtest-metrics">
          <div><span>回測週期</span><strong>${backtestLearning.horizon || 240} 日後報酬</strong></div>
          <div><span>成功門檻</span><strong>±${backtestLearning.successThreshold || 5}%</strong></div>
          <div><span>有效樣本</span><strong>${backtestLearning.evidenceCount || 0}</strong></div>
          <div><span>權重調整</span><strong class="${backtestAdjustment > 0 ? "up" : backtestAdjustment < 0 ? "down" : ""}">${backtestAdjustmentText}</strong></div>
          <div><span>交易成本</span><strong>${formatBacktestRatio(backtestCostModel.roundTripPct)}%</strong></div>
          <div><span>停損 / 停利</span><strong>${backtestRiskModel.stopLossPct || -8}% / +${backtestRiskModel.takeProfitPct || 20}%</strong></div>
          <div><span>最大回撤</span><strong class="down">${formatBacktestRatio(backtestPerformance.maxDrawdown)}%</strong></div>
          <div><span>Profit Factor</span><strong>${formatBacktestRatio(backtestBest?.profitFactor ?? backtestPerformance.profitFactor)}</strong></div>
          <div><span>模型狀態</span><strong class="${backtestValidation.status === "rebuild" ? "down" : backtestValidation.status === "healthy" ? "up" : ""}">${backtestValidation.label || "樣本不足"}</strong></div>
          <div><span>失真次數</span><strong>${backtestValidation.driftCount ?? 0}</strong></div>
        </div>
        <div class="backtest-action-card">
          <div>
            <span>Action calibration</span>
            <strong>操作校準提示</strong>
          </div>
          <ul>
            ${backtestDecisionTips.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </div>
        <p class="backtest-filter-note">模型已排除短線雜訊較高的單因子訊號作為最佳歷史訊號候選，改以趨勢、動能、量能、波動、成本、風控與績效指標交叉確認，並避免未來函數、樣本不足與過度擬合。</p>
        <p class="stock-theory-note">回溯學習使用歷史資料做訊號校準，只調整分析權重，不代表未來必然重複；若樣本數不足，系統會維持中性權重。</p>
      </div>
      <p class="stock-theory-note">「動態強化」是依理論一致度、量價與指標確認調整權重，不是模型自行學習或保證預測；技術分析仍應搭配基本面、籌碼與停損紀律。</p>
    </section>
  `;

  const watchlistAdded = isStockInWatchlist(detail);
  const fullDetailNoticeHtml = detail.detailMode === "quick"
    ? `<div class="stock-detail-empty">即時行情與近期技術資料已載入；基本面、籌碼面、消息面、估值歷史與公司資料正在同步線上完整資料。</div>`
    : "";
  container.innerHTML = `
    <div class="card-title-row">
      <h3>${detail.code} ${detail.name}</h3>
      <div class="stock-detail-actions">
        <button class="watchlist-toggle ${watchlistAdded ? "is-added" : ""}" type="button" data-stock-watchlist-toggle>
          ${watchlistAdded ? "移除自選" : "加入自選"}
        </button>
        <span class="chip ${detail.tone === "up" ? "chip-green" : detail.tone === "down" ? "chip-red" : "chip-blue"}">${detail.snapshotDate || "--"}</span>
      </div>
    </div>
    ${fullDetailNoticeHtml}
    <div class="detail-metrics">
      <div><span>收盤價</span><strong>${detail.close}</strong></div>
      <div><span>漲跌幅</span><strong class="${toneClass(detail.tone)}">${detail.pct}</strong></div>
      <div><span>MA5 / MA20 / MA60</span><strong>${detail.ma5} / ${detail.ma20} / ${detail.ma60}</strong></div>
      <div><span>5 日均量</span><strong>${detail.avgVolume5}</strong></div>
      <div><span>成交金額</span><strong>${detail.turnover}</strong></div>
      <div><span>月高</span><strong>${detail.monthHigh}</strong></div>
      <div><span>月低</span><strong>${detail.monthLow}</strong></div>
    </div>
    <p class="card-copy">${detail.trend}</p>
    <section class="technical-chart-card">
      <div class="card-title-row">
        <div>
          <h3>技術走勢圖</h3>
          <p class="chart-subtitle">K 線與可選均線。${historySummary} ${chartIntervals.intradayUnavailableReason || "盤中歷史資料不可用。"}</p>
        </div>
        <div class="range-switcher" aria-label="技術圖時間切換">
          ${intervalButtons}
        </div>
      </div>
      <div class="ma-switcher" aria-label="移動平均線選項">
        <span>均線</span>
        ${maOptions.map((period) => `
          <button class="ma-option ${period === 5 ? "is-active" : ""}" type="button" data-ma-period="${period}">
            <i class="ma-color ma-${period}"></i>MA${period}
          </button>
        `).join("")}
      </div>
      <div class="indicator-switcher" aria-label="技術指標切換">
        <span>主圖疊加（可複選）</span>
        ${chartIndicatorOptions.map(([key, label]) => `
          <button class="indicator-option" type="button" data-chart-indicator="${key}">
            ${label}
          </button>
        `).join("")}
      </div>
      <div class="indicator-switcher panel-indicator-switcher" aria-label="下方技術指標切換">
        <span>下方指標（可複選）</span>
        ${panelIndicatorOptions.map(([key, label]) => `
          <button class="indicator-option ${key === "kd" ? "is-active" : ""}" type="button" data-panel-indicator="${key}">
            ${label}
          </button>
        `).join("")}
      </div>
      <div class="stock-chart-zoom" aria-label="個股走勢圖縮放控制">
        <button type="button" data-stock-zoom="in">＋ 放大</button>
        <button type="button" data-stock-zoom="out" disabled>－ 縮小</button>
        <button type="button" data-stock-zoom="reset" disabled>重設</button>
        <button type="button" data-stock-pan="older" disabled>← 往前</button>
        <button type="button" data-stock-pan="newer" disabled>往後 →</button>
        <span data-stock-zoom-status>顯示 ${getChartHistory(detail, "day").length} / ${getChartHistory(detail, "day").length} 根</span>
      </div>
      ${detail.historyWarning ? `<p class="chart-data-notice">${escapeHtml(detail.historyWarning)}</p>` : ""}
      <div id="technical-chart-view">${renderTechnicalChart(detail, "day", [], [5], defaultVisibleChartCount("day"), 0, ["kd"])}</div>
    </section>
    <section class="recent-trades-card">
      <div class="card-title-row">
        <h3>近五日交易</h3>
      </div>
      <div class="detail-history">${historyHtml}</div>
    </section>
    ${technicalTheoryHtml}
    <div class="analysis-grid">${analysisHtml}</div>
    ${companyNewsHtml}
    ${etfDividendHtml}
    ${valuationAndCompanyHtml}
  `;

  container.querySelector("[data-stock-watchlist-toggle]")?.addEventListener("click", (event) => {
    const added = toggleWatchlistStock(detail);
    event.currentTarget.textContent = added ? "移除自選" : "加入自選";
    event.currentTarget.classList.toggle("is-added", added);
    const status = document.getElementById("search-status");
    if (status) {
      status.textContent = added
        ? `已將 ${detail.code} ${detail.name} 加入自選股。`
        : `已將 ${detail.code} ${detail.name} 從自選股移除。`;
    }
  });

  container.querySelectorAll("[data-institution-period]").forEach((button) => {
    button.addEventListener("click", () => {
      const period = Number(button.dataset.institutionPeriod);
      if (!Number.isFinite(period)) return;
      stockInstitutionPeriodState.set(getStockDetailCacheKey(detail.code, detail.market || activeStockMarket), period);
      renderStockDetail(detail);
    });
  });

  container.querySelectorAll("[data-institution-range]").forEach((button) => {
    button.addEventListener("click", async () => {
      const range = String(button.dataset.institutionRange || "");
      if (!range) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const code = currentDetail.code || detail.code;
      const marketValue = currentDetail.market || detail.market || activeStockMarket || "";
      const stateKey = getStockDetailCacheKey(code, marketValue);
      const rangeCacheKey = `${stateKey}:${range}`;
      stockInstitutionRangeState.set(stateKey, range);
      const renderWithoutJump = (nextDetail) => {
        const scrollY = window.scrollY;
        renderStockDetail(nextDetail);
        requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
      };
      const mergeInstitutionPayload = (baseDetail, payload) => {
        const loadedHistory = payload?.institutionalTradeHistory || {};
        if (!Array.isArray(loadedHistory.rows) || !loadedHistory.rows.length) return baseDetail;
        return {
          ...baseDetail,
          institutionalTradeHistory: loadedHistory,
          institutionalTrades: payload.institutionalTrades || baseDetail.institutionalTrades || buildLatestInstitutionalTradeFromHistory(loadedHistory),
        };
      };
      const shouldFetchRealRange = ["6m", "1y"].includes(range);
      if (shouldFetchRealRange) {
        const cached = stockInstitutionRangeHistoryCache.get(rangeCacheKey);
        if (cached) {
          renderWithoutJump(mergeInstitutionPayload(currentDetail, cached));
          return;
        }
        const status = document.getElementById("search-status");
        if (status) status.textContent = `${code} 法人 ${range} 真實資料載入中...`;
        try {
          const marketQuery = marketValue ? `&market=${encodeURIComponent(marketValue)}` : "";
          const [rangeResponse, fullResponse] = await Promise.all([
            fetchWithTimeout(
              `/api/twse/stock/${encodeURIComponent(code)}/institutional-history?range=${encodeURIComponent(range)}${marketQuery}`,
              { cache: "no-store" },
              120000,
            ),
            currentDetail.allHistoryLoaded ? Promise.resolve(null) : fetchWithTimeout(
              `/api/twse/stock/${encodeURIComponent(code)}?history=all&refresh=1&deferSlow=1${marketQuery}`,
              { cache: "no-store" },
              30000,
            ).catch(() => null),
          ]);
          if (!rangeResponse.ok) throw new Error(`HTTP ${rangeResponse.status}`);
          const rangePayload = await rangeResponse.json();
          stockInstitutionRangeHistoryCache.set(rangeCacheKey, rangePayload);
          let mergedDetail = currentDetail;
          if (fullResponse && fullResponse.ok) {
            const fullDetail = await fullResponse.json();
            mergedDetail = { ...currentDetail, ...fullDetail };
            if (currentDetail.shareholderDistribution && Object.keys(currentDetail.shareholderDistribution).length && (!fullDetail.shareholderDistribution || !Object.keys(fullDetail.shareholderDistribution).length)) {
              mergedDetail.shareholderDistribution = currentDetail.shareholderDistribution;
            }
          }
          renderWithoutJump(mergeInstitutionPayload(mergedDetail, rangePayload));
          return;
        } catch (error) {
          console.error("Failed to load real institution range history:", error);
          if (status) status.textContent = `${code} 法人 ${range} 真實資料暫時無法連線，先顯示已取得資料。`;
        }
      }
      renderWithoutJump(currentDetail);
    });
  });

  container.querySelectorAll("[data-margin-range]").forEach((button) => {
    button.addEventListener("click", () => {
      const range = String(button.dataset.marginRange || "");
      if (!range) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const stateKey = getStockDetailCacheKey(currentDetail.code || detail.code, currentDetail.market || detail.market || activeStockMarket);
      const scrollY = window.scrollY;
      stockMarginRangeState.set(stateKey, range);
      renderStockDetail(currentDetail);
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
    });
  });

  container.querySelectorAll("[data-margin-summary-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = String(button.dataset.marginSummaryMode || "");
      if (!mode) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const stateKey = getStockDetailCacheKey(currentDetail.code || detail.code, currentDetail.market || detail.market || activeStockMarket);
      const scrollY = window.scrollY;
      stockMarginSummaryModeState.set(stateKey, mode);
      renderStockDetail(currentDetail);
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
    });
  });

  container.querySelectorAll("[data-margin-table-type]").forEach((button) => {
    button.addEventListener("click", () => {
      const type = String(button.dataset.marginTableType || "");
      if (!type) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const stateKey = getStockDetailCacheKey(currentDetail.code || detail.code, currentDetail.market || detail.market || activeStockMarket);
      const scrollY = window.scrollY;
      stockMarginTableTypeState.set(stateKey, type);
      renderStockDetail(currentDetail);
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
    });
  });

  container.querySelectorAll("[data-margin-period]").forEach((button) => {
    button.addEventListener("click", () => {
      const period = String(button.dataset.marginPeriod || "");
      if (!period) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const stateKey = getStockDetailCacheKey(currentDetail.code || detail.code, currentDetail.market || detail.market || activeStockMarket);
      const scrollY = window.scrollY;
      stockMarginPeriodState.set(stateKey, period);
      renderStockDetail(currentDetail);
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
    });
  });

  container.querySelectorAll("[data-institution-series]").forEach((button) => {
    button.addEventListener("click", () => {
      const series = String(button.dataset.institutionSeries || "");
      if (!series) return;
      const stateKey = getStockDetailCacheKey(detail.code, detail.market || activeStockMarket);
      const current = new Set(String(stockInstitutionSeriesState.get(stateKey) || "price,foreign,trust,dealer").split(",").filter(Boolean));
      if (current.has(series)) current.delete(series);
      else current.add(series);
      const flowCount = ["foreign", "trust", "dealer"].filter((key) => current.has(key)).length;
      if (!flowCount) current.add(series === "price" ? "foreign" : series);
      stockInstitutionSeriesState.set(stateKey, ["price", "foreign", "trust", "dealer"].filter((key) => current.has(key)).join(","));
      renderStockDetail(detail);
    });
  });

  container.querySelectorAll("[data-chip-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const tab = String(button.dataset.chipTab || "");
      if (!tab) return;
      stockChipTabState.set(getStockDetailCacheKey(detail.code, detail.market || activeStockMarket), tab);
      renderStockDetail(detail);
    });
  });

  initInstitutionChartCursor(container);
  initMajorHolderChartCursor(container);
  initMarginBalanceChartCursor(container);

  loadInstitutionalTradeHistoryIfNeeded(detail);

  let activeInterval = "day";
  const activeOverlayIndicators = new Set();
  const activePanelIndicators = new Set(["kd"]);
  const activeMaPeriods = new Set([5]);
  const zoomCounts = new Map();
  const panOffsets = new Map();

  const getZoomState = () => {
    const total = getChartHistory(chartDetail, activeInterval).length;
    const minimum = activeInterval === "day" ? 20 : activeInterval === "week" ? 8 : 4;
    const overlayStateKey = [...activeOverlayIndicators].sort().join(",");
    const panelStateKey = [...activePanelIndicators].sort().join(",");
    const chartStateKey = `${activeInterval}:${overlayStateKey}:${panelStateKey}`;
    const saved = zoomCounts.get(chartStateKey);
    const visible = Number.isFinite(saved) ? Math.max(minimum, Math.min(saved, total)) : defaultVisibleChartCount(activeInterval);
    const panOffset = Math.max(0, Math.min(panOffsets.get(chartStateKey) || 0, total - visible));
    return { total, minimum: Math.min(minimum, total), visible, panOffset };
  };

  const updateZoomControls = () => {
    const { total, minimum, visible, panOffset } = getZoomState();
    const zoomIn = container.querySelector('[data-stock-zoom="in"]');
    const zoomOut = container.querySelector('[data-stock-zoom="out"]');
    const reset = container.querySelector('[data-stock-zoom="reset"]');
    const older = container.querySelector('[data-stock-pan="older"]');
    const newer = container.querySelector('[data-stock-pan="newer"]');
    const status = container.querySelector("[data-stock-zoom-status]");
    if (zoomIn) zoomIn.disabled = visible <= minimum;
    if (zoomOut) zoomOut.disabled = visible >= total;
    if (reset) reset.disabled = visible >= total;
    if (older) older.disabled = panOffset >= total - visible;
    if (newer) newer.disabled = panOffset <= 0;
    if (status) status.textContent = `顯示 ${visible} / ${total} 根`;
  };

  const bindTechnicalChartWheel = (chartView) => {
    const frame = chartView?.querySelector(".sector-chart-frame");
    if (!frame) return;
    frame.addEventListener("wheel", (event) => {
      event.preventDefault();
      updateStockZoom(event.deltaY < 0 ? "in" : "out");
    }, { passive: false });
    bindHorizontalChartPan(frame, updateStockPan);
  };

  async function updateTechnicalChart() {
    const chartView = document.getElementById("technical-chart-view");
    if (!chartView) return;
    const longestMaPeriod = Math.max(...activeMaPeriods, 0);
    const availableSeriesCount = getChartHistory(chartDetail, activeInterval).length;
    const structureNeedsHistory = activeOverlayIndicators.size > 0;
    const panelNeedsHistory = [...activePanelIndicators].some((item) => ["macd", "dmi", "obv"].includes(item));
    const needsHistoryLoad = (
      (["week", "month"].includes(activeInterval) && chartDetail.isFallbackHistory)
      || (longestMaPeriod > availableSeriesCount && !chartDetail.allHistoryLoaded)
      || (structureNeedsHistory && availableSeriesCount < 80 && !chartDetail.allHistoryLoaded)
      || (panelNeedsHistory && availableSeriesCount < 40 && !chartDetail.allHistoryLoaded)
    );
    if (needsHistoryLoad) {
      const previousHtml = chartView.innerHTML;
      chartView.innerHTML = '<div class="stock-detail-empty">載入完整歷史資料中...</div>';
      try {
        const marketQuery = detail.market ? `&market=${encodeURIComponent(detail.market)}` : "";
        const response = await fetchWithTimeout(
          `/api/twse/stock/${encodeURIComponent(detail.code)}?history=all&refresh=1${marketQuery}`,
          { cache: "no-store" },
          15000,
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        chartDetail = await response.json();
        if (!Array.isArray(chartDetail.historyDays) || chartDetail.historyDays.length < 2 || chartDetail.isFallbackHistory) {
          throw new Error("Historical data unavailable");
        }
      } catch (error) {
        chartView.innerHTML = previousHtml;
        const status = document.getElementById("search-status");
        if (status) status.textContent = `${detail.code} 完整歷史資料暫時無法連線。`;
        console.error("Failed to load full stock history:", error);
        return;
      }
    }
    const { visible, panOffset } = getZoomState();
    chartView.innerHTML = renderTechnicalChart(chartDetail, activeInterval, [...activeOverlayIndicators], [...activeMaPeriods], visible, panOffset, [...activePanelIndicators]);
    bindChartHover(chartView);
    bindTechnicalChartWheel(chartView);
    updateZoomControls();
  }

  bindChartHover(document.getElementById("technical-chart-view"));
  bindTechnicalChartWheel(document.getElementById("technical-chart-view"));
  updateZoomControls();

  async function updateStockZoom(direction) {
    const { total, minimum, visible } = getZoomState();
    let next = visible;
    if (direction === "in") next = Math.max(minimum, Math.floor(visible * 0.65));
    if (direction === "out") next = Math.min(total, Math.ceil(visible / 0.65));
    if (direction === "reset") next = total;
    if (next === visible) return;
    const chartStateKey = `${activeInterval}:${[...activeOverlayIndicators].sort().join(",")}:${[...activePanelIndicators].sort().join(",")}`;
    zoomCounts.set(chartStateKey, next);
    panOffsets.set(chartStateKey, 0);
    await updateTechnicalChart();
  }

  async function updateStockPan(direction) {
    const { total, visible, panOffset } = getZoomState();
    const maxOffset = Math.max(total - visible, 0);
    const step = Math.max(1, Math.round(visible * 0.35));
    const next = direction === "older"
      ? Math.min(maxOffset, panOffset + step)
      : Math.max(0, panOffset - step);
    if (next === panOffset) return;
    panOffsets.set(`${activeInterval}:${[...activeOverlayIndicators].sort().join(",")}:${[...activePanelIndicators].sort().join(",")}`, next);
    await updateTechnicalChart();
  }

  container.querySelectorAll("[data-interval]").forEach((button) => {
    const interval = button.dataset.interval;
    if (interval === activeInterval) button.classList.add("is-active");
    button.addEventListener("click", async () => {
      if (button.classList.contains("is-disabled")) return;
      activeInterval = interval;
      container.querySelectorAll("[data-interval]").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      await updateTechnicalChart();
    });
  });

  container.querySelectorAll("[data-stock-zoom]").forEach((button) => {
    button.addEventListener("click", () => updateStockZoom(button.dataset.stockZoom));
  });

  container.querySelectorAll("[data-stock-pan]").forEach((button) => {
    button.addEventListener("click", () => updateStockPan(button.dataset.stockPan));
  });

  container.querySelectorAll("[data-ma-period]").forEach((button) => {
    button.addEventListener("click", async () => {
      const period = Number(button.dataset.maPeriod);
      if (activeMaPeriods.has(period)) {
        activeMaPeriods.delete(period);
        button.classList.remove("is-active");
      } else {
        activeMaPeriods.add(period);
        button.classList.add("is-active");
      }
      await updateTechnicalChart();
    });
  });

  container.querySelectorAll("[data-chart-indicator]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.chartIndicator || "";
      if (activeOverlayIndicators.has(key)) {
        activeOverlayIndicators.delete(key);
      } else if (key) {
        activeOverlayIndicators.add(key);
      }
      container.querySelectorAll("[data-chart-indicator]").forEach((item) => {
        item.classList.toggle("is-active", activeOverlayIndicators.has(item.dataset.chartIndicator));
      });
      await updateTechnicalChart();
    });
  });

  container.querySelectorAll("[data-panel-indicator]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.panelIndicator || "kd";
      if (activePanelIndicators.has(key) && activePanelIndicators.size > 1) {
        activePanelIndicators.delete(key);
      } else {
        activePanelIndicators.add(key);
      }
      container.querySelectorAll("[data-panel-indicator]").forEach((item) => {
        item.classList.toggle("is-active", activePanelIndicators.has(item.dataset.panelIndicator));
      });
      await updateTechnicalChart();
    });
  });
}
function initInstitutionChartCursor(root = document) {
  root.querySelectorAll(".chip-institution-chart").forEach((chart) => {
    const svg = chart.querySelector("svg");
    const tooltip = chart.querySelector(".institution-chart-tooltip");
    if (!svg || !tooltip) return;
    const xLine = svg.querySelector("[data-institution-cursor-x]");
    const yLine = svg.querySelector("[data-institution-cursor-y]");
    const dot = svg.querySelector("[data-institution-cursor-dot]");
    const zones = svg.querySelectorAll(".institution-hover-zone");
    const hide = () => {
      tooltip.hidden = true;
      xLine?.classList.remove("is-visible");
      yLine?.classList.remove("is-visible");
      dot?.classList.remove("is-visible");
    };
    const tooltipToneClass = (value) => {
      const parsed = parseAnalysisNumber(value);
      if (!Number.isFinite(parsed) || parsed === 0) return "is-flat";
      return parsed > 0 ? "is-up" : "is-down";
    };
    const rowHtml = (label, value, tone = "") => {
      if (!value || value === "--") return "";
      return `<span><em>${escapeHtml(label)}</em><strong class="${tone}">${escapeHtml(value)}</strong></span>`;
    };
    const show = (zone, event) => {
      const x = Number(zone.dataset.x);
      const y = Number(zone.dataset.y);
      if (Number.isFinite(x) && xLine) {
        xLine.setAttribute("x1", x.toFixed(2));
        xLine.setAttribute("x2", x.toFixed(2));
        xLine.classList.add("is-visible");
      }
      if (Number.isFinite(y) && yLine) {
        yLine.setAttribute("y1", y.toFixed(2));
        yLine.setAttribute("y2", y.toFixed(2));
        yLine.classList.add("is-visible");
      }
      if (Number.isFinite(x) && Number.isFinite(y) && dot) {
        dot.setAttribute("cx", x.toFixed(2));
        dot.setAttribute("cy", y.toFixed(2));
        dot.classList.add("is-visible");
      }
      const rows = [
        zone.dataset.showPrice === "1" ? rowHtml("股價", zone.dataset.price) : "",
        zone.dataset.showForeign === "1" ? rowHtml("外資", zone.dataset.foreign, tooltipToneClass(zone.dataset.foreign)) : "",
        zone.dataset.showTrust === "1" ? rowHtml("投信", zone.dataset.trust, tooltipToneClass(zone.dataset.trust)) : "",
        zone.dataset.showDealer === "1" ? rowHtml("自營商", zone.dataset.dealer, tooltipToneClass(zone.dataset.dealer)) : "",
        rowHtml("合計", zone.dataset.total, tooltipToneClass(zone.dataset.total)),
        zone.dataset.showForeign === "1" ? rowHtml("外資籌碼", zone.dataset.foreignChip) : "",
        zone.dataset.showPrice === "1" ? rowHtml("漲跌幅", zone.dataset.change, tooltipToneClass(zone.dataset.change)) : "",
        zone.dataset.showPrice === "1" ? rowHtml("成交量", zone.dataset.volume) : "",
      ].filter(Boolean).join("");
      tooltip.innerHTML = `<b>${escapeHtml(zone.dataset.date || "--")}</b>${rows}`;
      tooltip.hidden = false;
      const chartRect = chart.getBoundingClientRect();
      const leftBase = event.clientX - chartRect.left + 14;
      const topBase = event.clientY - chartRect.top - 10;
      const maxLeft = Math.max(12, chartRect.width - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, chartRect.height - tooltip.offsetHeight - 12);
      tooltip.style.left = `${Math.max(12, Math.min(leftBase, maxLeft))}px`;
      tooltip.style.top = `${Math.max(12, Math.min(topBase, maxTop))}px`;
    };
    zones.forEach((zone) => {
      zone.addEventListener("mouseenter", (event) => show(zone, event));
      zone.addEventListener("mousemove", (event) => show(zone, event));
      zone.addEventListener("mouseleave", hide);
    });
    chart.addEventListener("mouseleave", hide);
  });
}
function initMajorHolderChartCursor(root = document) {
  root.querySelectorAll(".major-holder-chart").forEach((chart) => {
    const svg = chart.querySelector("svg");
    const tooltip = chart.querySelector(".holder-chart-tooltip");
    if (!svg || !tooltip) return;
    const xLine = svg.querySelector("[data-holder-cursor-x]");
    const dots = {
      price: svg.querySelector('[data-holder-cursor-dot="price"]'),
      foreign: svg.querySelector('[data-holder-cursor-dot="foreign"]'),
      major: svg.querySelector('[data-holder-cursor-dot="major"]'),
      director: svg.querySelector('[data-holder-cursor-dot="director"]'),
    };
    const zones = svg.querySelectorAll(".holder-hover-zone");
    const hide = () => {
      tooltip.hidden = true;
      xLine?.classList.remove("is-visible");
      Object.values(dots).forEach((dot) => dot?.classList.remove("is-visible"));
    };
    const rowHtml = (label, value) => {
      if (!value || value === "--") return "";
      return `<span><em>${escapeHtml(label)}</em><strong>${escapeHtml(value)}</strong></span>`;
    };
    const moveDot = (dot, x, yValue) => {
      const y = Number(yValue);
      if (!dot || !Number.isFinite(x) || !Number.isFinite(y)) {
        dot?.classList.remove("is-visible");
        return;
      }
      dot.setAttribute("cx", x.toFixed(2));
      dot.setAttribute("cy", y.toFixed(2));
      dot.classList.add("is-visible");
    };
    const show = (zone, event) => {
      const x = Number(zone.dataset.x);
      if (Number.isFinite(x) && xLine) {
        xLine.setAttribute("x1", x.toFixed(2));
        xLine.setAttribute("x2", x.toFixed(2));
        xLine.classList.add("is-visible");
      }
      moveDot(dots.price, x, zone.dataset.yPrice);
      moveDot(dots.foreign, x, zone.dataset.yForeign);
      moveDot(dots.major, x, zone.dataset.yMajor);
      moveDot(dots.director, x, zone.dataset.yDirector);
      const rows = [
        rowHtml("外資籌碼", zone.dataset.foreign),
        rowHtml("大戶籌碼", zone.dataset.major),
        rowHtml("董監持股", zone.dataset.director),
        rowHtml("股價", zone.dataset.price),
      ].filter(Boolean).join("");
      tooltip.innerHTML = `<b>${escapeHtml(zone.dataset.date || "--")}</b>${rows}`;
      tooltip.hidden = false;
      const chartRect = chart.getBoundingClientRect();
      const leftBase = event.clientX - chartRect.left + 14;
      const topBase = event.clientY - chartRect.top - 10;
      const maxLeft = Math.max(12, chartRect.width - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, chartRect.height - tooltip.offsetHeight - 12);
      tooltip.style.left = `${Math.max(12, Math.min(leftBase, maxLeft))}px`;
      tooltip.style.top = `${Math.max(12, Math.min(topBase, maxTop))}px`;
    };
    zones.forEach((zone) => {
      zone.addEventListener("mouseenter", (event) => show(zone, event));
      zone.addEventListener("mousemove", (event) => show(zone, event));
      zone.addEventListener("mouseleave", hide);
    });
    chart.addEventListener("mouseleave", hide);
  });
}
function initMarginBalanceChartCursor(root = document) {
  root.querySelectorAll(".margin-balance-visual").forEach((chart) => {
    const svg = chart.querySelector("svg");
    const tooltip = chart.querySelector(".margin-chart-tooltip");
    if (!svg || !tooltip) return;
    const xLine = svg.querySelector("[data-margin-cursor-x]");
    const dot = svg.querySelector("[data-margin-cursor-dot]");
    const zones = svg.querySelectorAll(".margin-hover-zone");
    const hide = () => {
      tooltip.hidden = true;
      xLine?.classList.remove("is-visible");
      dot?.classList.remove("is-visible");
    };
    const toneClass = (value) => {
      const parsed = parseAnalysisNumber(value);
      if (!Number.isFinite(parsed) || parsed === 0) return "is-flat";
      return parsed > 0 ? "is-up" : "is-down";
    };
    const rowHtml = (label, value, change, changeLabel = "當日增減") => `
      <span>
        <em>${escapeHtml(label)}</em>
        <strong>${escapeHtml(value || "--")}${change && change !== "--" ? ` <small class="${toneClass(change)}">/ ${escapeHtml(changeLabel)} ${escapeHtml(change)}</small>` : ""}</strong>
      </span>
    `;
    const show = (zone, event) => {
      const x = Number(zone.dataset.x);
      const y = Number(zone.dataset.y);
      if (Number.isFinite(x) && xLine) {
        xLine.setAttribute("x1", x.toFixed(2));
        xLine.setAttribute("x2", x.toFixed(2));
        xLine.classList.add("is-visible");
      }
      if (Number.isFinite(x) && Number.isFinite(y) && dot) {
        dot.setAttribute("cx", x.toFixed(2));
        dot.setAttribute("cy", y.toFixed(2));
        dot.classList.add("is-visible");
      }
      tooltip.innerHTML = `
        <b>${escapeHtml(zone.dataset.date || "--")}</b>
        ${rowHtml("股價", zone.dataset.price, zone.dataset.priceChange, "漲跌幅")}
        ${rowHtml("融資餘額", zone.dataset.financing, zone.dataset.financingChange)}
        ${rowHtml("融券餘額", zone.dataset.short, zone.dataset.shortChange)}
        ${rowHtml("借券賣出餘額", zone.dataset.lending, zone.dataset.lendingChange)}
      `;
      tooltip.hidden = false;
      const chartRect = chart.getBoundingClientRect();
      const leftBase = event.clientX - chartRect.left + 14;
      const topBase = event.clientY - chartRect.top - 10;
      const maxLeft = Math.max(12, chartRect.width - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, chartRect.height - tooltip.offsetHeight - 12);
      tooltip.style.left = `${Math.max(12, Math.min(leftBase, maxLeft))}px`;
      tooltip.style.top = `${Math.max(12, Math.min(topBase, maxTop))}px`;
    };
    zones.forEach((zone) => {
      zone.addEventListener("mouseenter", (event) => show(zone, event));
      zone.addEventListener("mousemove", (event) => show(zone, event));
      zone.addEventListener("mouseleave", hide);
    });
    chart.addEventListener("mouseleave", hide);
  });
}
function getStockDetailCacheKey(code, market = "") {
  return `${String(market || "").trim().toUpperCase()}:${String(code || "").trim()}`;
}
