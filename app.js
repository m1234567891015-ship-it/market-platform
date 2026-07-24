
// TD-08: single source of truth for the site nav. Every *.html page ships
// the same static `<nav class="navbar"><a class="brand">...<div
// class="nav-links"></div></nav>` shell; this function is what actually
// populates the brand text and the link list on every page load, so
// changing a nav link/label now means editing this one list instead of
// hand-syncing up to 21 divergent static <nav> blocks.










function normalizeStockSearchTerm(value) {
  return String(value || "").trim().toLowerCase();
}

function searchStocksLocally(query, stocks, limit = 20) {
  const keyword = normalizeStockSearchTerm(query);
  if (!keyword) return [];

  const exactCode = [];
  const prefixCode = [];
  const partialCode = [];
  const prefixName = [];
  const nameMatches = [];

  (stocks || []).forEach((stock) => {
    const code = normalizeStockSearchTerm(stock.code);
    const name = normalizeStockSearchTerm(stock.name);
    if (code === keyword) {
      exactCode.push(stock);
    } else if (code.startsWith(keyword)) {
      prefixCode.push(stock);
    } else if (code.includes(keyword)) {
      partialCode.push(stock);
    } else if (name.startsWith(keyword)) {
      prefixName.push(stock);
    } else if (name.includes(keyword)) {
      nameMatches.push(stock);
    }
  });

  const combined = exactCode.concat(prefixCode, partialCode, prefixName, nameMatches);
  const unique = [];
  const seen = new Set();
  for (const item of combined) {
    const key = `${item.market || ""}:${item.code}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(item);
    if (unique.length >= limit) break;
  }
  return unique;
}







function buildClientInstitutionalTradeRecord(row, dateStr) {
  const foreign = parseTwseNumber(row?.[4]);
  const trust = parseTwseNumber(row?.[10]);
  const dealer = parseTwseNumber(row?.[11]);
  const total = parseTwseNumber(row?.[18]);
  const label = `${dateStr.slice(4, 6)}/${dateStr.slice(6, 8)}`;
  return {
    date: `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`,
    label,
    foreignValue: foreign,
    trustValue: trust,
    dealerValue: dealer,
    totalValue: total,
    foreignLotsValue: foreign === null ? null : foreign / 1000,
    trustLotsValue: trust === null ? null : trust / 1000,
    dealerLotsValue: dealer === null ? null : dealer / 1000,
    totalLotsValue: total === null ? null : total / 1000,
  };
}


function buildClientInstitutionalTradeSummary(rows, period) {
  const summary = { date: "", label: `${period}日` };
  ["foreign", "trust", "dealer", "total"].forEach((key) => {
    const rawKey = `${key}Value`;
    const lotKey = `${key}LotsValue`;
    const values = rows
      .slice(0, period)
      .map((item) => Number(item?.[rawKey]))
      .filter((value) => Number.isFinite(value));
    const total = values.length ? values.reduce((sum, value) => sum + value, 0) : null;
    summary[rawKey] = total;
    summary[lotKey] = total === null ? null : total / 1000;
  });
  return summary;
}



function buildPendingInstitutionalTradeHistory(detail) {
  const market = String(detail?.market || activeStockMarket || "").trim().toUpperCase();
  if (market && market !== "TWSE") return null;
  return {
    available: false,
    loading: true,
    unit: "張",
    periods: [5, 10, 20, 30],
    defaultPeriod: 5,
    rows: [],
    summaries: {},
    source: "TWSE T86",
    sourceNote: "法人買賣超 5/10/20/30 日明細正在同步證交所 T86 live 資料...",
  };
}




function getWeightedIndexSector() {
  return (data.sectors || []).find((sector) => sector.sourceName === "\u767c\u884c\u91cf\u52a0\u6b0a\u80a1\u50f9\u6307\u6578" || sector.name === "\u53f0\u7063\u52a0\u6b0a\u6307\u6578") || null;
}



function alignSectorSeries(sectorCandles, benchmarkCandles) {
  const benchmarkByTime = new Map((benchmarkCandles || []).map((candle) => [candle.time, candle]));
  return (sectorCandles || [])
    .map((candle) => {
      const benchmark = benchmarkByTime.get(candle.time);
      const sectorClose = parseMarketNumber(candle.close);
      const benchmarkClose = parseMarketNumber(benchmark?.close);
      if (!benchmark || sectorClose === null || benchmarkClose === null) return null;
      return {
        time: candle.time,
        sectorClose,
        benchmarkClose,
      };
    })
    .filter(Boolean);
}

function normalizeComparisonSeries(alignedSeries) {
  if (!alignedSeries.length) return [];
  const sectorBase = alignedSeries[0].sectorClose || 1;
  const benchmarkBase = alignedSeries[0].benchmarkClose || 1;
  return alignedSeries.map((item) => ({
    time: item.time || item.label,
    sector: (item.sectorClose / sectorBase) * 100,
    benchmark: (item.benchmarkClose / benchmarkBase) * 100,
  }));
}

function aggregateSectorSeriesByWeek(series) {
  const groups = new Map();
  (series || []).forEach((item) => {
    const parsedDate = item.date ? new Date(item.date) : null;
    if (!parsedDate || Number.isNaN(parsedDate.getTime())) return;
    const key = getWeekKey(parsedDate);
    const existing = groups.get(key);
    const open = parseMarketNumber(item.open);
    const high = parseMarketNumber(item.high);
    const low = parseMarketNumber(item.low);
    const close = parseMarketNumber(item.close);
    const volume = parseMarketNumber(item.volumeValue ?? item.volume);
    const trades = parseMarketNumber(item.trades);
    if (!existing) {
      groups.set(key, {
        date: key,
        open: open ?? close,
        high: high ?? close,
        low: low ?? close,
        close,
        volume: volume ?? 0,
        volumeValue: volume ?? 0,
        trades: trades ?? null,
        turnover: item.turnover || null,
      });
      return;
    }
    existing.high = Math.max(existing.high ?? close, high ?? close);
    existing.low = Math.min(existing.low ?? close, low ?? close);
    existing.close = close;
    existing.volume += volume ?? 0;
    existing.volumeValue = existing.volume;
    if (trades !== null) existing.trades = (existing.trades ?? 0) + trades;
    existing.turnover = item.turnover || existing.turnover;
  });
  return Array.from(groups.values());
}

function aggregateSectorSeriesByMonth(series) {
  const groups = new Map();
  (series || []).forEach((item) => {
    const parsedDate = item.date ? new Date(item.date) : null;
    if (!parsedDate || Number.isNaN(parsedDate.getTime())) return;
    const key = `${parsedDate.getFullYear()}-${String(parsedDate.getMonth() + 1).padStart(2, "0")}`;
    const open = parseMarketNumber(item.open);
    const high = parseMarketNumber(item.high);
    const low = parseMarketNumber(item.low);
    const close = parseMarketNumber(item.close);
    const volume = parseMarketNumber(item.volumeValue ?? item.volume);
    const trades = parseMarketNumber(item.trades);
    const existing = groups.get(key);
    if (!existing) {
      groups.set(key, {
        date: key,
        open: open ?? close,
        high: high ?? close,
        low: low ?? close,
        close,
        volume: volume ?? 0,
        volumeValue: volume ?? 0,
        trades: trades ?? null,
        turnover: parseMarketNumber(item.turnover) ?? null,
      });
      return;
    }
    existing.high = Math.max(existing.high ?? close, high ?? close);
    existing.low = Math.min(existing.low ?? close, low ?? close);
    existing.close = close;
    existing.volume += volume ?? 0;
    existing.volumeValue = existing.volume;
    if (trades !== null) existing.trades = (existing.trades ?? 0) + trades;
    const turnover = parseMarketNumber(item.turnover);
    if (turnover !== null) existing.turnover = (existing.turnover ?? 0) + turnover;
  });
  return Array.from(groups.values());
}

function aggregateIntradaySectorSeries(candles, intervalMinutes) {
  const groups = new Map();
  (candles || []).forEach((item) => {
    const [hour, minute] = String(item.time || "").split(":").map(Number);
    if (!Number.isFinite(hour) || !Number.isFinite(minute)) return;
    const bucketMinute = Math.floor(minute / intervalMinutes) * intervalMinutes;
    const key = `${String(hour).padStart(2, "0")}:${String(bucketMinute).padStart(2, "0")}`;
    const open = parseMarketNumber(item.open);
    const high = parseMarketNumber(item.high);
    const low = parseMarketNumber(item.low);
    const close = parseMarketNumber(item.close);
    if (close === null) return;
    const existing = groups.get(key);
    if (!existing) {
      groups.set(key, {
        label: key,
        open: open ?? close,
        high: high ?? close,
        low: low ?? close,
        close,
      });
      return;
    }
    existing.high = Math.max(existing.high, high ?? close);
    existing.low = Math.min(existing.low, low ?? close);
    existing.close = close;
  });
  return Array.from(groups.values());
}

function getSectorSeriesForMode(sector, mode) {
  if (["minute5", "minute15", "minute30", "intraday"].includes(mode)) {
    const intervalMinutes = mode === "minute30" ? 30 : mode === "minute15" || mode === "intraday" ? 15 : 5;
    return aggregateIntradaySectorSeries(sector?.candles || [], intervalMinutes).map((item) => ({
      label: item.label,
      ...item,
      volume: item.volume || null,
      trades: item.trades || null,
      turnover: item.turnover || null,
    }));
  }

  const daySeries = (sector?.comparisonSeries?.day || []).map((item) => ({
    date: item.date,
    label: item.date,
    open: item.open ?? null,
    high: item.high ?? null,
    low: item.low ?? null,
    close: item.close,
    volume: item.volume || null,
    trades: item.trades || null,
    volumeValue: parseMarketNumber(item.volumeValue ?? item.volume),
    turnover: item.turnover || null,
  }));
  if (mode === "week") {
    return aggregateSectorSeriesByWeek(daySeries).map((item) => ({
      label: item.date,
      open: item.open ?? null,
      high: item.high ?? null,
      low: item.low ?? null,
      close: item.close,
      volume: item.volume || null,
      trades: item.trades != null ? Number(item.trades).toLocaleString("en-US") : null,
      volumeValue: item.volumeValue ?? item.volume ?? null,
      turnover: item.turnover || null,
    }));
  }
  if (mode === "month") {
    return aggregateSectorSeriesByMonth(daySeries).map((item) => ({
      label: item.date,
      open: item.open ?? null,
      high: item.high ?? null,
      low: item.low ?? null,
      close: item.close,
      volume: item.volume ? Number(item.volume).toLocaleString("en-US") : null,
      trades: item.trades != null ? Number(item.trades).toLocaleString("en-US") : null,
      volumeValue: item.volumeValue ?? item.volume ?? null,
      turnover: item.turnover != null ? Number(item.turnover).toLocaleString("en-US") : null,
    }));
  }
  return daySeries;
}

function buildSectorComparisonModel(sector, benchmark, mode, visibleCount = null, panOffset = 0) {
  const sectorSeries = getSectorSeriesForMode(sector, mode);
  const benchmarkSeries = getSectorSeriesForMode(benchmark, mode);
  const benchmarkByLabel = new Map(benchmarkSeries.map((item) => [item.label, item]));
  let alignedRaw = sectorSeries
    .map((item) => {
      const benchmarkItem = benchmarkByLabel.get(item.label);
      const sectorClose = parseMarketNumber(item.close);
      const benchmarkClose = parseMarketNumber(benchmarkItem?.close);
      if (!benchmarkItem || sectorClose === null || benchmarkClose === null) return null;
      return {
        label: item.label,
        sectorClose,
        benchmarkClose,
        sectorItem: item,
        benchmarkItem,
      };
    })
    .filter(Boolean);
  const requestedCount = Number(visibleCount);
  if (Number.isFinite(requestedCount) && requestedCount > 1) {
    alignedRaw = sliceVisibleWindow(alignedRaw, requestedCount, panOffset);
  }

  const normalized = normalizeComparisonSeries(alignedRaw);
  return normalized.map((item, index) => ({
    index,
    label: item.time,
    sectorClose: alignedRaw[index].sectorClose,
    benchmarkClose: alignedRaw[index].benchmarkClose,
    sectorItem: alignedRaw[index].sectorItem,
    benchmarkItem: alignedRaw[index].benchmarkItem,
    sector: item.sector,
    benchmark: item.benchmark,
    diff: item.sector - item.benchmark,
  }));
}

function renderSectorComparisonChart(sector, benchmark, mode = "intraday", options = {}) {
  const totalPoints = buildSectorComparisonModel(sector, benchmark, mode).length;
  const aligned = buildSectorComparisonModel(sector, benchmark, mode, options.visibleCount, options.panOffset);
  if (aligned.length < 2) {
    return {
      html: '<div class="class-line-empty">歷史資料不足，暫不繪製短線直線圖。</div>',
      points: [],
      width: 0,
      height: 0,
    };
  }

  const width = 980;
  const priceHeight = 278;
  const activityGap = 34;
  const activityHeight = 82;
  const pad = { top: 28, right: 24, bottom: 48, left: 50 };
  const height = pad.top + priceHeight + activityGap + activityHeight + pad.bottom;
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = priceHeight;
  const step = plotWidth / Math.max(aligned.length - 1, 1);
  const values = aligned.flatMap((item) => [item.sector, item.benchmark]);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  const xAt = (index) => pad.left + index * step;
  const yAt = (value) => pad.top + ((maxValue - value) / range) * plotHeight;
  const activityTop = pad.top + plotHeight + activityGap;
  const sectorPoints = aligned.map((item, index) => ({ x: xAt(index), y: yAt(item.sector), value: item.sector }));
  const benchmarkPoints = aligned.map((item, index) => ({ x: xAt(index), y: yAt(item.benchmark), value: item.benchmark }));
  const sectorAreaPath = `${buildPath(sectorPoints)} L ${sectorPoints[sectorPoints.length - 1].x.toFixed(1)} ${(pad.top + plotHeight).toFixed(1)} L ${sectorPoints[0].x.toFixed(1)} ${(pad.top + plotHeight).toFixed(1)} Z`;
  const sectorDelta = aligned[aligned.length - 1].sector - 100;
  const benchmarkDelta = aligned[aligned.length - 1].benchmark - 100;
  const diffDelta = sectorDelta - benchmarkDelta;
  const volumeValues = aligned.map((item) => parseMarketNumber(item.sectorItem?.volume) || 0);
  const maxVolume = Math.max(...volumeValues, 1);
  const volumeBarWidth = Math.min(14, Math.max(2, step * 0.58));
  const volumeBars = aligned.map((item, index) => {
    const volume = volumeValues[index];
    const heightValue = Math.max(1, (volume / maxVolume) * activityHeight);
    const tone = index === 0 || item.sector >= aligned[index - 1].sector ? "up" : "down";
    return `<rect class="sector-activity-volume ${tone}" x="${(xAt(index) - volumeBarWidth / 2).toFixed(1)}" y="${(activityTop + activityHeight - heightValue).toFixed(1)}" width="${volumeBarWidth.toFixed(1)}" height="${heightValue.toFixed(1)}" rx="2"></rect>`;
  }).join("");
  const latestItem = aligned[aligned.length - 1].sectorItem || {};
  const showTrades = !sector.hideTrades;
  const comparisonText = diffDelta >= 0
    ? `${sector.name} 目前領先大盤 ${diffDelta.toFixed(2)}%`
    : `${sector.name} 目前落後大盤 ${Math.abs(diffDelta).toFixed(2)}%`;
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * plotHeight;
    const label = maxValue - ratio * range;
    return `
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line>
      <text x="8" y="${y + 5}">${label.toFixed(1)}</text>
    `;
  }).join("");
  const hoverZones = aligned.map((item, index) => {
    const left = index === 0 ? pad.left : xAt(index) - step / 2;
    const zoneWidth = index === aligned.length - 1 ? (width - pad.right) - left : step;
    const sectorOpen = parseMarketNumber(item.sectorItem?.open);
    const sectorHigh = parseMarketNumber(item.sectorItem?.high);
    const sectorLow = parseMarketNumber(item.sectorItem?.low);
    const sectorVolume = item.sectorItem?.volume ?? "";
    const sectorTrades = item.sectorItem?.trades ?? "";
    const sectorTurnover = item.sectorItem?.turnover ?? "";
    return `<rect class="sector-hover-zone" x="${left.toFixed(1)}" y="${pad.top}" width="${Math.max(zoneWidth, 12).toFixed(1)}" height="${plotHeight + activityGap + activityHeight}" data-sync-index="${index}" data-label="${item.label}" data-point-x="${xAt(index).toFixed(1)}" data-sector-y="${yAt(item.sector).toFixed(1)}" data-benchmark-y="${yAt(item.benchmark).toFixed(1)}" data-sector-close="${item.sectorClose.toFixed(2)}" data-benchmark-close="${item.benchmarkClose.toFixed(2)}" data-diff="${item.diff.toFixed(2)}" data-sector-open="${sectorOpen !== null ? sectorOpen.toFixed(2) : ""}" data-sector-high="${sectorHigh !== null ? sectorHigh.toFixed(2) : ""}" data-sector-low="${sectorLow !== null ? sectorLow.toFixed(2) : ""}" data-sector-volume="${sectorVolume}" data-sector-trades="${sectorTrades}" data-show-trades="${showTrades ? "true" : "false"}" data-sector-turnover="${sectorTurnover}"></rect>`;
  }).join("");
  const modeLabel = {
    minute5: "5 分",
    minute15: "15 分",
    minute30: "30 分",
    intraday: "15 分",
    day: "日線",
    week: "週線",
    month: "月線",
  }[mode] || "日線";
  const sectorColor = sector.tone === "up" ? "var(--green)" : sector.tone === "down" ? "var(--red)" : "var(--blue)";

  return {
    html: `
    <div class="sector-sync-chart-summary">
      <strong>${sector.name} 與大盤走勢比較</strong>
      <span>兩條線都從 100 開始，位置越高代表表現越好</span>
    </div>
    <div class="sector-plain-result ${diffDelta >= 0 ? "is-ahead" : "is-behind"}">
      <strong>${comparisonText}</strong>
      <span>${modeLabel}期間：${sector.name} ${sectorDelta >= 0 ? "上漲" : "下跌"} ${Math.abs(sectorDelta).toFixed(2)}%，大盤 ${benchmarkDelta >= 0 ? "上漲" : "下跌"} ${Math.abs(benchmarkDelta).toFixed(2)}%</span>
    </div>
    <div class="sector-chart-stat-strip ${showTrades ? "" : "without-trades"}">
      <span>成交量<strong>${latestItem.volume || sector.volume || "--"}</strong></span>
      <span>成交金額<strong>${latestItem.turnover || sector.turnover || "--"}</strong></span>
      ${showTrades ? `<span>成交筆數<strong>${latestItem.trades || sector.trades || "--"}</strong></span>` : ""}
      <span>${diffDelta >= 0 ? "領先大盤" : "落後大盤"}<strong class="${diffDelta >= 0 ? "up" : "down"}">${Math.abs(diffDelta).toFixed(2)}%</strong></span>
    </div>
    <div class="sector-chart-frame">
      <svg class="sector-comparison-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${sector.name} 與 ${benchmark.name} 比較走勢圖">
        <defs>
          <linearGradient id="sectorAreaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${sectorColor}" stop-opacity="0.28"></stop>
            <stop offset="100%" stop-color="${sectorColor}" stop-opacity="0.01"></stop>
          </linearGradient>
          <filter id="sectorLineGlow" x="-20%" y="-40%" width="140%" height="180%">
            <feGaussianBlur stdDeviation="3" result="blur"></feGaussianBlur>
            <feMerge><feMergeNode in="blur"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge>
          </filter>
        </defs>
        <rect class="sector-plot-surface" x="${pad.left}" y="${pad.top}" width="${plotWidth}" height="${plotHeight}" rx="12"></rect>
        <g class="chart-grid">${gridLines}</g>
        <rect class="sector-base-band" x="${pad.left}" y="${Math.max(pad.top, yAt(100.2)).toFixed(1)}" width="${plotWidth}" height="${Math.max(2, Math.abs(yAt(99.8) - yAt(100.2))).toFixed(1)}"></rect>
        <line class="sector-base-line" x1="${pad.left}" y1="${yAt(100)}" x2="${width - pad.right}" y2="${yAt(100)}"></line>
        <path class="sector-focus-area ${toneClass(sector.tone)}" d="${sectorAreaPath}"></path>
        <path class="sector-benchmark-line" d="${buildPath(benchmarkPoints)}"></path>
        <path class="sector-focus-line ${toneClass(sector.tone)}" filter="url(#sectorLineGlow)" d="${buildPath(sectorPoints)}"></path>
        <line class="sector-activity-boundary" x1="${pad.left}" y1="${activityTop - 12}" x2="${width - pad.right}" y2="${activityTop - 12}"></line>
        <g class="sector-activity-bars">${volumeBars}</g>
        <text class="sector-activity-label" x="${pad.left}" y="${activityTop - 17}">成交量（柱狀越高代表交易越熱絡）</text>
        <line class="sector-hover-guide" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${activityTop + activityHeight}"></line>
        <circle class="sector-hover-dot sector-hover-dot-sector" cx="${pad.left}" cy="${pad.top}" r="5"></circle>
        <circle class="sector-hover-dot sector-hover-dot-market" cx="${pad.left}" cy="${pad.top}" r="5"></circle>
        <circle class="sector-focus-end ${toneClass(sector.tone)}" cx="${sectorPoints[sectorPoints.length - 1].x.toFixed(1)}" cy="${sectorPoints[sectorPoints.length - 1].y.toFixed(1)}" r="4"></circle>
        <circle class="sector-benchmark-end" cx="${benchmarkPoints[benchmarkPoints.length - 1].x.toFixed(1)}" cy="${benchmarkPoints[benchmarkPoints.length - 1].y.toFixed(1)}" r="4"></circle>
        <g class="sector-end-label sector-end-label-primary" transform="translate(${(sectorPoints[sectorPoints.length - 1].x - 138).toFixed(1)} ${(sectorPoints[sectorPoints.length - 1].y - 28).toFixed(1)})">
          <rect width="134" height="22" rx="11"></rect>
          <text x="67" y="15" text-anchor="middle">${sector.name} ${sectorDelta >= 0 ? "+" : ""}${sectorDelta.toFixed(2)}%</text>
        </g>
        <g class="sector-end-label sector-end-label-benchmark" transform="translate(${(benchmarkPoints[benchmarkPoints.length - 1].x - 108).toFixed(1)} ${(benchmarkPoints[benchmarkPoints.length - 1].y + 9).toFixed(1)})">
          <rect width="104" height="22" rx="11"></rect>
          <text x="52" y="15" text-anchor="middle">大盤 ${benchmarkDelta >= 0 ? "+" : ""}${benchmarkDelta.toFixed(2)}%</text>
        </g>
        <g class="chart-labels">
          <text x="${pad.left}" y="${height - 18}">${aligned[0].label}</text>
          <text x="${width - pad.right - 90}" y="${height - 18}">${aligned[aligned.length - 1].label}</text>
          <text x="${width - pad.right - 244}" y="24">${sector.name} / ${benchmark.name} / ${modeLabel}</text>
        </g>
        <g class="sector-hover-zones">${hoverZones}</g>
      </svg>
      <div class="sector-sync-tooltip" hidden></div>
    </div>
    <div class="sector-chart-legend">
      <span><i class="legend-swatch legend-swatch-sector ${toneClass(sector.tone)}"></i>${sector.name}</span>
      <span><i class="legend-swatch legend-swatch-market"></i>大盤</span>
      <span>起點 = 100，直接比較誰漲得多</span>
    </div>
  `,
    points: aligned.map((item, index) => ({
      ...item,
      x: sectorPoints[index].x,
      sectorY: sectorPoints[index].y,
      benchmarkY: benchmarkPoints[index].y,
    })),
    width,
    height,
    totalPoints,
    visiblePoints: aligned.length,
  };
}

function renderSectorSyncView(sectors, benchmark) {
  const container = document.getElementById("sector-sync-view");
  if (!container) return;

  const sectorOnly = sectors.filter((sector) => sector.sourceName !== benchmark?.sourceName);
  const defaultKey = container.dataset.activeSector || sectorOnly[0]?.sourceName || "";
  const activeSector = sectorOnly.find((sector) => sector.sourceName === defaultKey) || sectorOnly[0];

  if (!benchmark || !activeSector) {
    container.innerHTML = '<div class="stock-detail-empty">暫無資料可顯示。</div>';
    return;
  }

  const technical = activeSector.technicalAnalysis || {};
  const benchmarkTechnical = benchmark.technicalAnalysis || {};
  const activityScore = technical.activityScore !== null && technical.activityScore !== undefined ? `${technical.activityScore}%` : "--";
  const benchmarkActivityScore = benchmarkTechnical.activityScore !== null && benchmarkTechnical.activityScore !== undefined ? `${benchmarkTechnical.activityScore}%` : "--";
  const availableModes = [
    { id: "intraday", label: "盤中", enabled: (activeSector.candles || []).length > 1 && (benchmark.candles || []).length > 1 },
    { id: "day", label: "日線", enabled: (activeSector.comparisonSeries?.day || []).length > 1 && (benchmark.comparisonSeries?.day || []).length > 1 },
    { id: "week", label: "週線", enabled: (activeSector.comparisonSeries?.day || []).length > 4 && (benchmark.comparisonSeries?.day || []).length > 4 },
  ];
  const defaultMode = container.dataset.syncMode || "intraday";
  const activeMode = (availableModes.find((item) => item.id === defaultMode && item.enabled) || availableModes.find((item) => item.enabled) || availableModes[0]).id;
  const chart = renderSectorComparisonChart(activeSector, benchmark, activeMode);

  container.dataset.activeSector = activeSector.sourceName;
  container.dataset.syncMode = activeMode;
  container.innerHTML = `
    <div class="sector-sync-layout">
      <div class="sector-sync-main">
        <div class="sector-sync-toolbar">
          <div class="sector-sync-picker">
            ${sectorOnly.map((sector) => `
              <button class="sector-sync-chip ${sector.sourceName === activeSector.sourceName ? "is-active" : ""}" type="button" data-sector-source="${sector.sourceName}">
                ${sector.name}
              </button>
            `).join("")}
          </div>
          <div class="sector-sync-mode-switcher">
            ${availableModes.map((mode) => `
              <button class="sector-sync-mode ${mode.id === activeMode ? "is-active" : ""} ${mode.enabled ? "" : "is-disabled"}" type="button" data-sync-mode="${mode.id}" ${mode.enabled ? "" : "disabled"}>
                ${mode.label}
              </button>
            `).join("")}
          </div>
        </div>
        ${chart.html}
      </div>
      <aside class="sector-sync-side weighted-index-side">
        <article class="analysis-card">
          <div class="card-title-row">
            <h4>${activeSector.name}</h4>
            <span class="chip ${activeSector.tone === "up" ? "chip-green" : activeSector.tone === "down" ? "chip-red" : "chip-blue"}">${technical.signal || "--"}</span>
          </div>
          <p class="card-copy">${technical.summary || "以大盤基準線比較此族群的相對強弱。"}</p>
          <ul class="analysis-list">
            <li>族群漲跌幅：${activeSector.pct} | 大盤漲跌幅：${benchmark.pct}</li>
            <li>族群動能：${technical.momentum || "--"} | 大盤動能：${benchmarkTechnical.momentum || "--"}</li>
            <li>族群活躍度：${technical.activityLevel || "--"} | 分數：${activityScore}</li>
            <li>大盤活躍度：${benchmarkTechnical.activityLevel || "--"} | 分數：${benchmarkActivityScore}</li>
            <li>${activeSector.note || "可在此視圖比較相對強弱。"}</li>
          </ul>
        </article>
      </aside>
    </div>
  `;

  container.querySelectorAll("[data-sector-source]").forEach((button) => {
    button.addEventListener("click", () => {
      container.dataset.activeSector = button.dataset.sectorSource || "";
      renderSectorSyncView(sectors, benchmark);
    });
  });

  container.querySelectorAll("[data-sync-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      container.dataset.syncMode = button.dataset.syncMode || "intraday";
      renderSectorSyncView(sectors, benchmark);
    });
  });

  const tooltip = container.querySelector(".sector-sync-tooltip");
  const frame = container.querySelector(".sector-chart-frame");
  const guide = container.querySelector(".sector-hover-guide");
  const sectorDot = container.querySelector(".sector-hover-dot-sector");
  const benchmarkDot = container.querySelector(".sector-hover-dot-market");
  if (tooltip && frame && guide && sectorDot && benchmarkDot && chart.points.length) {
    const hideTooltip = () => {
      tooltip.hidden = true;
      guide.classList.remove("is-visible");
      sectorDot.classList.remove("is-visible");
      benchmarkDot.classList.remove("is-visible");
    };
    container.querySelectorAll("[data-sync-index]").forEach((zone) => {
      zone.addEventListener("mouseenter", () => {
        const point = chart.points[Number(zone.dataset.syncIndex)];
        if (!point) return;
        tooltip.hidden = false;
        tooltip.innerHTML = `
          <strong>${escapeHtml(point.label)}</strong>
          <span>${escapeHtml(activeSector.name)}：${point.sectorClose.toFixed(2)}（${point.sector.toFixed(2)}）</span>
          <span>${escapeHtml(benchmark.name)}：${point.benchmarkClose.toFixed(2)}（${point.benchmark.toFixed(2)}）</span>
          <span>差異 ${point.diff >= 0 ? "+" : ""}${point.diff.toFixed(2)}%</span>
        `;
        tooltip.style.left = `${(point.x / chart.width) * 100}%`;
        tooltip.style.top = `${(Math.min(point.sectorY, point.benchmarkY) / chart.height) * 100}%`;
        guide.setAttribute("x1", point.x.toFixed(1));
        guide.setAttribute("x2", point.x.toFixed(1));
        sectorDot.setAttribute("cx", point.x.toFixed(1));
        sectorDot.setAttribute("cy", point.sectorY.toFixed(1));
        benchmarkDot.setAttribute("cx", point.x.toFixed(1));
        benchmarkDot.setAttribute("cy", point.benchmarkY.toFixed(1));
        guide.classList.add("is-visible");
        sectorDot.classList.add("is-visible");
        benchmarkDot.classList.add("is-visible");
      });
      zone.addEventListener("mouseleave", hideTooltip);
    });
    frame.addEventListener("mouseleave", hideTooltip);
  }
}

function buildSectorTrendModel(sector, mode) {
  const sectorSeries = getSectorSeriesForMode(sector, mode);
  const aligned = sectorSeries
    .map((item) => {
      const sectorClose = parseMarketNumber(item.close);
      if (sectorClose === null) return null;
      return {
        label: item.label,
        sectorClose,
        open: parseMarketNumber(item.open) ?? null,
        high: parseMarketNumber(item.high) ?? null,
        low: parseMarketNumber(item.low) ?? null,
        volumeValue: item.volumeValue ?? null,
        volume: item.volume || null,
        trades: item.trades || null,
        turnover: item.turnover || null,
      };
    })
    .filter(Boolean);

  if (aligned.length < 2) return [];

  const sectorBase = aligned[0].sectorClose || 1;
  return aligned.map((item, index) => {
    // For day/week: derive open from previous close; high/low from open+close range
    const prevClose = index > 0 ? aligned[index - 1].sectorClose : item.sectorClose;
    const openNorm = item.open !== null ? (item.open / sectorBase) * 100 : (prevClose / sectorBase) * 100;
    const closeNorm = (item.sectorClose / sectorBase) * 100;
    const highNorm = item.high !== null ? (item.high / sectorBase) * 100 : Math.max(openNorm, closeNorm);
    const lowNorm = item.low !== null ? (item.low / sectorBase) * 100 : Math.min(openNorm, closeNorm);
    return {
      index,
      label: item.label,
      sectorClose: item.sectorClose,
      open: item.open ?? prevClose,
      high: item.high ?? Math.max(item.sectorClose, item.open ?? prevClose),
      low: item.low ?? Math.min(item.sectorClose, item.open ?? prevClose),
      sector: closeNorm,
      sectorOpen: openNorm,
      sectorHigh: highNorm,
      sectorLow: lowNorm,
      volumeValue: item.volumeValue,
      volume: item.volume,
      trades: item.trades,
      turnover: item.turnover,
    };
  });
}

function renderSectorTrendChart(sector, mode = "intraday", options = {}) {
  const fullAligned = buildSectorTrendModel(sector, mode);
  const requestedCount = Number(options.visibleCount);
  const aligned = Number.isFinite(requestedCount) && requestedCount > 1
    ? sliceVisibleWindow(fullAligned, requestedCount, options.panOffset)
    : fullAligned;
  if (aligned.length < 2) {
    return {
      html: '<div class="class-line-empty">無可用趨勢資料。</div>',
      points: [],
      width: 0,
      height: 0,
    };
  }

  const validVolumeCount = aligned.filter((item) => item.volumeValue !== null && item.volumeValue > 0).length;
  const hasVolume = validVolumeCount >= Math.min(5, aligned.length);

  const isLarge = options.size === "large";
  const width = 980;
  const priceHeight = isLarge ? 390 : 300;
  const volumePanelHeight = hasVolume ? (isLarge ? 120 : 90) : 0;
  const volumeGap = hasVolume ? (isLarge ? 42 : 36) : 0;
  const pad = { top: 28, right: 24, bottom: 54, left: 58 };
  const height = pad.top + priceHeight + volumeGap + volumePanelHeight + pad.bottom;
  const plotWidth = width - pad.left - pad.right;
  const step = plotWidth / Math.max(aligned.length - 1, 1);
  const candleWidth = Math.min(16, Math.max(1.5, step * 0.6));

  // Price range across raw OHLC values. K-line charts should use real index/price
  // levels; Base 100 is reserved for comparison mode.
  const allPriceValues = aligned
    .flatMap((item) => [item.open, item.high, item.low, item.sectorClose])
    .filter(Number.isFinite);
  const minValue = Math.min(...allPriceValues);
  const maxValue = Math.max(...allPriceValues);
  const valuePad = (maxValue - minValue) * 0.06 || 1;
  const priceMin = minValue - valuePad;
  const priceMax = maxValue + valuePad;
  const priceRange = priceMax - priceMin || 1;

  const xAt = (index) => pad.left + index * step;
  const yAt = (value) => pad.top + ((priceMax - value) / priceRange) * priceHeight;

  // Grid lines (5 horizontal)
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * priceHeight;
    const label = priceMax - ratio * priceRange;
    const digits = Math.abs(label) >= 1000 ? 0 : 2;
    return `
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line>
      <text x="8" y="${y + 5}">${formatGlobalValue(label, digits)}</text>
    `;
  }).join("");

  // MA5 line over closes
  const closeValues = aligned.map((item) => item.sectorClose);
  const ma5 = movingAverage(closeValues, 5);
  const ma5Points = aligned.map((item, index) => ({
    x: xAt(index),
    y: ma5[index] === null ? null : yAt(ma5[index]),
    value: ma5[index],
  })).filter((pt) => pt.value !== null);
  const ma5Path = ma5Points.length > 1
    ? `<path class="chart-ma-line" d="${buildPath(ma5Points)}" opacity="0.7"></path>`
    : "";

  // Candlesticks
  const candles = aligned.map((item, index) => {
    const x = xAt(index);
    const openY = yAt(item.open);
    const closeY = yAt(item.sectorClose);
    const highY = yAt(item.high);
    const lowY = yAt(item.low);
    const bodyTop = Math.min(openY, closeY);
    const bodyH = Math.max(Math.abs(openY - closeY), 2);
    const tone = item.sectorClose >= item.open ? "up" : "down";
    return `
      <line class="candle-wick" x1="${x.toFixed(1)}" y1="${highY.toFixed(1)}" x2="${x.toFixed(1)}" y2="${lowY.toFixed(1)}"></line>
      <rect class="candle-body ${tone}" x="${(x - candleWidth / 2).toFixed(1)}" y="${bodyTop.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${bodyH.toFixed(1)}" rx="1"></rect>
    `;
  }).join("");

  // Volume panel
  const volumeTop = pad.top + priceHeight + volumeGap;
  const volumeValues = aligned.map((item) => item.volumeValue ?? 0);
  const maxVolume = hasVolume ? Math.max(...volumeValues, 1) : 1;
  const volumeBars = hasVolume ? aligned.map((item, index) => {
    const x = xAt(index);
    const vol = item.volumeValue ?? 0;
    const barH = Math.max((vol / maxVolume) * volumePanelHeight, vol > 0 ? 2 : 0);
    const y = volumeTop + volumePanelHeight - barH;
    const tone = item.sectorClose >= item.open ? "up" : "down";
    return `<rect class="chart-volume-bar ${tone}" x="${(x - candleWidth / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${barH.toFixed(1)}" rx="2"></rect>`;
  }).join("") : "";

  const volumeAxisLabels = hasVolume ? (() => {
    const maxLabel = maxVolume >= 1e8 ? `${(maxVolume / 1e8).toFixed(1)}億` : maxVolume >= 1e4 ? `${(maxVolume / 1e4).toFixed(0)}萬` : String(Math.round(maxVolume));
    return `
      <text class="chart-volume-label" x="8" y="${volumeTop + 14}">${maxLabel}</text>
      <text class="chart-volume-label" x="${pad.left}" y="${volumeTop - 10}">成交量</text>
      <line class="combined-indicator-boundary" x1="${pad.left}" y1="${volumeTop}" x2="${width - pad.right}" y2="${volumeTop}"></line>
    `;
  })() : "";

  // Hover zones — height covers only the chart plot + volume area, not the bottom label row
  const hoverBottom = volumeTop + volumePanelHeight;
  const hoverZoneHeight = hoverBottom - pad.top;
  const hoverZones = aligned.map((item, index) => {
    const x = xAt(index);
    const left = index === 0 ? pad.left : x - step / 2;
    const zoneW = index === aligned.length - 1 ? (width - pad.right) - left : step;
    const volDisplay = item.volume || (item.volumeValue != null ? item.volumeValue.toLocaleString() : "--");
    return `<rect class="sector-hover-zone"
      x="${left.toFixed(1)}" y="${pad.top}"
      width="${Math.max(zoneW, 8).toFixed(1)}" height="${hoverZoneHeight}"
      data-sync-index="${index}"
      data-label="${item.label}"
      data-sector-open="${item.open.toFixed(2)}"
      data-sector-high="${item.high.toFixed(2)}"
      data-sector-low="${item.low.toFixed(2)}"
      data-sector-close="${item.sectorClose.toFixed(2)}"
      data-volume="${volDisplay}"
      data-trades="${item.trades || "--"}"
      data-turnover="${item.turnover || "--"}"
    ></rect>`;
  }).join("");

  const modeLabel = mode === "week" ? "週線" : mode === "month" ? "月線" : "日線";
  const firstClose = aligned[0].sectorClose;
  const latestClose = aligned[aligned.length - 1].sectorClose;
  const sectorDelta = firstClose ? ((latestClose - firstClose) / firstClose) * 100 : 0;
  const firstLabel = aligned[0].label;
  const lastLabel = aligned[aligned.length - 1].label;

  return {
    html: `
    <div class="sector-sync-chart-summary">
      <span>${sector.name} ${modeLabel} K 線</span>
      <strong class="${toneClass(sector.tone)}">${sector.pct}</strong>
      <span>實際點位，區間 ${formatGlobalValue(minValue, 0)} 至 ${formatGlobalValue(maxValue, 0)}，${sectorDelta >= 0 ? "+" : ""}${sectorDelta.toFixed(2)}%</span>
    </div>
    <div class="sector-chart-frame">
      <svg class="sector-comparison-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${sector.name} K 線圖">
        <g class="chart-grid">${gridLines}</g>
        <g>${candles}</g>
        ${ma5Path}
        ${volumeAxisLabels}
        <g class="chart-volume-bars">${volumeBars}</g>
        <line class="sector-hover-guide" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${hoverBottom}"></line>
        <circle class="sector-hover-dot sector-hover-dot-sector" cx="${pad.left}" cy="${pad.top}" r="5"></circle>
        <g class="chart-labels">
          <text x="${pad.left}" y="${height - 18}">${firstLabel}</text>
          <text x="${width - pad.right - 90}" y="${height - 18}">${lastLabel}</text>
          <text x="${width - pad.right - 268}" y="22">${sector.name} / ${modeLabel} / K 線 + MA5</text>
        </g>
        <g class="sector-hover-zones">${hoverZones}</g>
      </svg>
      <div class="sector-sync-tooltip" hidden></div>
    </div>
    <div class="sector-chart-legend">
      <span><i class="legend-swatch legend-swatch-sector ${toneClass(sector.tone)}"></i>${sector.name}</span>
      <span class="legend-ma5">— MA5</span>
      <span>Y 軸為實際點位</span>
    </div>
  `,
    points: aligned.map((item, index) => ({
      ...item,
      x: xAt(index),
      sectorY: yAt(item.sectorClose),
    })),
    width,
    height,
    totalPoints: fullAligned.length,
    visiblePoints: aligned.length,
  };
}

function buildWeightedVixComparisonModel(weightedIndex, volatility, visibleCount = null, panOffset = 0) {
  const weightedSeries = (weightedIndex?.comparisonSeries?.day || [])
    .map((item) => ({
      label: item.date,
      date: item.date,
      close: parseMarketNumber(item.close),
    }))
    .filter((item) => item.date && Number.isFinite(item.close));
  const vixByDate = new Map((volatility?.series || [])
    .map((item) => [item.date, parseMarketNumber(item.value)]));
  let aligned = weightedSeries
    .map((item) => {
      const vix = vixByDate.get(item.date);
      if (!Number.isFinite(vix)) return null;
      return { ...item, vix };
    })
    .filter(Boolean);
  const requestedCount = Number(visibleCount);
  if (Number.isFinite(requestedCount) && requestedCount > 1) {
    aligned = sliceVisibleWindow(aligned, requestedCount, panOffset);
  }
  if (aligned.length < 2) return [];
  const weightedBase = aligned[0].close || 1;
  const vixBase = aligned[0].vix || 1;
  return aligned.map((item, index) => ({
    ...item,
    index,
    weightedNorm: item.close / weightedBase * 100,
    vixNorm: item.vix / vixBase * 100,
  }));
}



function isLeveragedSectorDefault(item) {
  const text = `${item?.name || ""} ${item?.sourceName || ""}`.toUpperCase();
  return /(2X|正2|反1|反向|槓桿|期貨|期信)/.test(text);
}

function hasUsableComparisonSeries(item) {
  return (item?.comparisonSeries?.day || []).length >= 20;
}

function hasYahooChartSymbol(item) {
  return /^[0-9A-Z]+\.TWO?$/i.test(String(item?.sourceName || ""));
}

function pickDefaultSectorSyncItem(items, preferredSource = "") {
  const list = (items || []).filter(Boolean);
  const preferred = preferredSource
    ? list.find((item) => item.sourceName === preferredSource)
    : null;
  if (preferred && (!isLeveragedSectorDefault(preferred) || hasUsableComparisonSeries(preferred))) {
    return preferred;
  }

  const ordinary = list.filter((item) => !isLeveragedSectorDefault(item));
  return ordinary.find(hasUsableComparisonSeries)
    || ordinary.find(hasYahooChartSymbol)
    || ordinary[0]
    || list.find(hasUsableComparisonSeries)
    || list.find(hasYahooChartSymbol)
    || list[0]
    || null;
}

function getSectorSyncPickerItems(items, activeSector) {
  const sourceItems = (items || []).filter(Boolean);
  const chartable = sourceItems.filter((item) => hasUsableComparisonSeries(item) || hasYahooChartSymbol(item));
  const pool = chartable.length ? chartable : sourceItems;
  const ordered = activeSector ? [activeSector, ...pool] : pool;
  const seen = new Set();
  const picked = [];
  for (const item of ordered) {
    const key = String(item?.sourceName || item?.name || "");
    if (!key || seen.has(key)) continue;
    seen.add(key);
    picked.push(item);
    if (picked.length >= SECTOR_SYNC_PICKER_LIMIT) break;
  }
  return picked;
}

function renderCompactSectorSyncPicker(items, activeSector, totalCount) {
  const options = getSectorSyncPickerItems(items, activeSector);
  if (options.length <= 1) return "";
  const countText = totalCount > options.length
    ? `<span>${options.length} / ${totalCount}</span>`
    : "";
  return `
    <div class="sector-sync-picker sector-sync-picker-compact">
      <label for="sector-sync-select">比較標的</label>
      <select id="sector-sync-select" data-sector-source-select>
        ${options.map((sector) => `
          <option value="${escapeHtml(sector.sourceName || "")}" ${sector.sourceName === activeSector.sourceName ? "selected" : ""}>
            ${escapeHtml(sector.name || sector.sourceName || "--")}
          </option>
        `).join("")}
      </select>
      ${countText}
    </div>
  `;
}


function normalizeSectorCategoryText(value) {
  return String(value || "")
    .replace(/\s+/g, "")
    .replace(/類股$/, "")
    .replace(/類$/, "")
    .replace(/工業$/, "")
    .replace(/業$/, "");
}

function sectorCategoryTextMatches(left, right) {
  const leftText = normalizeSectorCategoryText(left);
  const rightText = normalizeSectorCategoryText(right);
  if (!leftText || !rightText) return false;
  return leftText === rightText || leftText.startsWith(rightText) || rightText.startsWith(leftText);
}



function buildSectorHeroInsight(item) {
  const direction = item.tone === "up"
    ? "目前呈現上漲走勢，短線買盤相對積極。"
    : item.tone === "down"
      ? "目前呈現回落走勢，短線賣壓相對明顯。"
      : "目前漲跌幅度有限，盤勢偏向整理。";
  const range = item.high !== "--" && item.low !== "--"
    ? `今日波動區間為 ${item.low} 至 ${item.high}。`
    : "";
  return `${direction}${range}`;
}

function renderYahooCategoryLinks(group, fallbackLinks) {
  const catalog = group.catalog || [];
  if (!catalog.length) return fallbackLinks;
  const activeIndex = activeYahooSectorCategories[group.key]?.index;
  return catalog
    .map(
      (item, index) =>
        `<button class="class-link-chip ${index === activeIndex ? "is-active" : ""}" type="button" data-yahoo-sector-group="${escapeHtml(group.key)}" data-yahoo-sector-index="${index}">${escapeHtml(item.name)}</button>`,
    )
    .join("");
}

async function loadYahooSectorCategory(groupKey, categoryIndex, categoryName) {
  const cacheKey = `${groupKey}:${categoryIndex}`;
  activeYahooSectorCategories[groupKey] = { index: categoryIndex, name: categoryName };
  if (yahooSectorQuoteCache.has(cacheKey)) {
    const cachedPayload = yahooSectorQuoteCache.get(cacheKey);
    const activeSource = activeYahooSectorStocks[groupKey];
    const activeItem = pickDefaultSectorSyncItem(cachedPayload?.items || [], activeSource);
    if (activeItem) {
      activeYahooSectorStocks[groupKey] = activeItem.sourceName;
      loadYahooSectorStockChart(groupKey, activeItem);
    }
    renderSectorPageV2();
    return;
  }

  const requestId = ++yahooSectorRequestId;
  const heroCard = document.getElementById("class-hero-card");
  const overviewGrid = document.getElementById("sector-overview-grid");
  const sectorGrid = document.getElementById("sector-grid");
  const syncView = document.getElementById("sector-sync-view");
  [heroCard, overviewGrid, sectorGrid, syncView].forEach((container) => {
    if (container) container.innerHTML = `<div class="stock-detail-empty">正在同步 ${categoryName} Yahoo 行情…</div>`;
  });

  try {
    const response = await fetchWithTimeout(
      `/api/yahoo/sector?group=${encodeURIComponent(groupKey)}&index=${categoryIndex}`,
      { cache: "no-store" },
      30000,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (requestId !== yahooSectorRequestId) return;
    yahooSectorQuoteCache.set(cacheKey, payload);
    const activeItem = pickDefaultSectorSyncItem(payload.items || [], activeYahooSectorStocks[groupKey]);
    if (activeItem) {
      activeYahooSectorStocks[groupKey] = activeItem.sourceName;
    }
    renderSectorPageV2();
    if (activeItem) loadYahooSectorStockChart(groupKey, activeItem);
  } catch (error) {
    if (requestId !== yahooSectorRequestId) return;
    delete activeYahooSectorCategories[groupKey];
    renderSectorPageV2();
    const sourceNote = document.getElementById("sector-source-note");
    if (sourceNote) sourceNote.textContent = `${categoryName} Yahoo 行情同步失敗，已恢復預設資料。`;
    console.error("Failed to load Yahoo sector category:", error);
  }
}

function ensureDefaultYahooSectorCategory(activeKey) {
  if (!["listed", "otc", "emerging"].includes(activeKey) || activeYahooSectorCategories[activeKey]) return false;
  const categories = data?.yahooSectorCatalog?.[activeKey] || [];
  if (!categories.length) return false;
  const params = new URLSearchParams(window.location.search);
  const requestedCategory = params.get("category") || params.get("sector") || "";
  const requestedIndex = Number(params.get("index"));
  const requestedGroup = params.get("group")?.trim() || "";
  const shouldUseRequestedCategory = !requestedGroup || requestedGroup === activeKey;
  const matchedIndex = Number.isInteger(requestedIndex) && requestedIndex >= 0 && requestedIndex < categories.length
    ? requestedIndex
    : requestedCategory && shouldUseRequestedCategory
      ? categories.findIndex((item) => sectorCategoryTextMatches(item.name, requestedCategory))
      : -1;
  if (matchedIndex < 0 && activeKey !== "listed") return false;
  const categoryIndex = matchedIndex >= 0 ? matchedIndex : 0;
  const defaultCategory = categories[categoryIndex];
  const attemptKey = `${activeKey}:${categoryIndex}`;
  if (defaultYahooSectorCategoryAttempts.has(attemptKey)) return false;
  defaultYahooSectorCategoryAttempts.add(attemptKey);
  loadYahooSectorCategory(activeKey, categoryIndex, defaultCategory.name || "水泥");
  return true;
}

function mergeYahooSectorChartPayload(groupKey, item, payload) {
  if (!item || !payload) return;
  const merged = { ...payload, summaryOnly: Boolean(payload.summaryOnly || payload.chartUnavailable) };
  Object.assign(item, merged);
  const sourceName = String(item.sourceName || "");
  const storedItems = data?.yahooSectorGroups?.[groupKey] || [];
  const storedItem = storedItems.find((entry) => String(entry.sourceName || "") === sourceName);
  if (storedItem && storedItem !== item) {
    Object.assign(storedItem, merged);
  }
  const category = activeYahooSectorCategories[groupKey];
  const cachedItems = category ? yahooSectorQuoteCache.get(`${groupKey}:${category.index}`)?.items || [] : [];
  const cachedItem = cachedItems.find((entry) => String(entry.sourceName || "") === sourceName);
  if (cachedItem && cachedItem !== item) {
    Object.assign(cachedItem, merged);
  }
}

async function loadYahooSectorStockChart(groupKey, item, rerender = true) {
  if (!item || (item.comparisonSeries?.day || []).length >= 20) {
    if (rerender) renderSectorPageV2();
    return;
  }
  const chartSymbol = String(item.sourceName || "");
  const loadingKey = `${groupKey}:${chartSymbol}`;
  if (!chartSymbol || yahooSectorChartLoading.has(loadingKey)) return;
  yahooSectorChartErrors.delete(loadingKey);
  yahooSectorChartLoading.add(loadingKey);
  if (rerender) renderSectorPageV2();
  try {
    const response = await fetchWithTimeout(
      `/api/yahoo/sector-chart?symbol=${encodeURIComponent(chartSymbol)}&exchange=${encodeURIComponent(item.exchange || "")}`,
      { cache: "no-store" },
      20000,
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    mergeYahooSectorChartPayload(groupKey, item, payload);
    const historyCount = (item.comparisonSeries?.day || []).length;
    if (historyCount < 20 && !item.summaryOnly) {
      throw new Error(`歷史資料僅有 ${historyCount} 筆`);
    }
  } catch (error) {
    const errorMessage = error?.name === "AbortError"
      ? "連線逾時，尚未取得完整走勢。"
      : error?.message?.startsWith("歷史資料僅有")
        ? `${error.message}，暫時無法繪製比較圖。`
        : "完整走勢暫時無法取得，請稍後重新載入。";
    yahooSectorChartErrors.set(loadingKey, errorMessage);
    console.error("Failed to load Yahoo sector chart:", error);
  } finally {
    yahooSectorChartLoading.delete(loadingKey);
  }
  if (rerender) renderSectorPageV2();
}

function getSectorRankingChangeValue(item) {
  const change = parseMarketNumber(item?.change);
  if (Number.isFinite(change)) return change;
  const close = parseMarketNumber(item?.value ?? item?.close);
  const previousClose = parseMarketNumber(item?.previousClose);
  if (Number.isFinite(close) && Number.isFinite(previousClose)) return close - previousClose;
  return Number.NEGATIVE_INFINITY;
}

function sortSectorsByChange(items) {
  return [...(items || [])].sort((left, right) => {
    const changeDiff = getSectorRankingChangeValue(right) - getSectorRankingChangeValue(left);
    if (Math.abs(changeDiff) > 0.000001) return changeDiff;
    const pctDiff = (parseMarketNumber(right?.pct) || 0) - (parseMarketNumber(left?.pct) || 0);
    if (Math.abs(pctDiff) > 0.000001) return pctDiff;
    return (parseMarketNumber(right?.volume) || 0) - (parseMarketNumber(left?.volume) || 0);
  });
}






function renderSectorGroup(group) {
  const items = sortSectorItemsByActiveMode((group.items || []).map((item) => ({ ...item, hideTrades: true })));
  const topItems = items.slice(0, group.kind === "summary" ? 6 : 8);

  if (group.kind === "summary") {
    const leader = items[0];
    const overview = topItems
      .map(
        (item) => `
          <article class="class-overview-card">
            <p>${item.name}</p>
            <strong>${item.value}</strong>
            <span class="${toneClass(item.tone)}">${item.change} / ${item.pct}</span>
          </article>
        `,
      )
      .join("");

    return {
      hero: leader
        ? `
          <div class="sector-yahoo-hero">
            <div class="sector-yahoo-hero-main">
              <p class="eyebrow">${group.label}</p>
              <h3>${leader.name}</h3>
              <div class="sector-yahoo-price-row">
                <strong>${leader.value}</strong>
                <span class="${toneClass(leader.tone)}">${leader.change} / ${leader.pct}</span>
              </div>
              <p class="card-copy">${leader.note || "可透過主卡片查看族群總覽。"}</p>
              <div class="sector-hero-insight">
                <span>行情解讀</span>
                <p>${buildSectorHeroInsight(leader)}</p>
              </div>
            </div>
            <div class="sector-yahoo-side-grid">
              <div class="mini-item"><span>成交量</span><strong>${leader.volume || "--"}</strong></div>
              <div class="mini-item"><span>成交金額</span><strong>${leader.turnover || "--"}</strong></div>
              <div class="mini-item"><span>開盤 / 昨收</span><strong>${leader.open} / ${leader.previousClose}</strong></div>
              <div class="mini-item"><span>最高 / 最低</span><strong>${leader.high} / ${leader.low}</strong></div>
            </div>
            <div class="sector-hero-meta">
              <span>資料來源：${group.source}</span>
              <span>更新時間：${leader.time || data.snapshotDate || "--"}</span>
            </div>
          </div>
        `
        : '<div class="stock-detail-empty">無可用族群摘要。</div>',
      overview,
      table: `
        ${renderScrollableClassTable(`
          <div class="class-table-head without-note">
            <span>名稱</span>
            <span>數值</span>
            <span>漲跌</span>
            <span>漲跌幅</span>
            <span>成交量</span>
            <span>成交金額</span>
          </div>
          ${items
            .map(
              (item, index) => `
            <article class="class-table-row without-note" id="${group.key}-${index}">
              ${renderSectorStockName(item)}
              <strong>${item.value}</strong>
              <strong class="${toneClass(item.tone)}">${item.change}</strong>
              <strong class="${toneClass(item.tone)}">${item.pct}</strong>
              <span>${item.volume}</span>
              <span>${item.turnover}</span>
            </article>
          `,
            )
            .join("")}
        `, `${group.label}排行表格`)}
      `,
      links: renderYahooCategoryLinks(
        group,
        items.map((item, index) => `<a class="class-link-chip" href="${safeUrl(`#${group.key}-${index}`)}">${escapeHtml(item.name)}</a>`).join(""),
      ),
      sync: renderSectorSyncViewV2(items),
    };
  }

  const leader = items[0];
  const overview = topItems
    .map(
      (sector) => `
        <article class="class-overview-card">
          <p>${sector.name}</p>
          <strong>${sector.value}</strong>
          <span class="${toneClass(sector.tone)}">${sector.pct}</span>
        </article>
      `,
    )
    .join("");

  return {
    hero: leader
      ? `
        <div class="sector-yahoo-hero">
          <div class="sector-yahoo-hero-main">
            <p class="eyebrow">${group.label}</p>
            <h3>${leader.name}</h3>
            <div class="sector-yahoo-price-row">
              <strong>${leader.value}</strong>
              <span class="${toneClass(leader.tone)}">${leader.change} / ${leader.pct}</span>
            </div>
            <p class="card-copy">${leader.note || "可透過主卡片查看族群總覽。"}</p>
          </div>
          <div class="sector-yahoo-side-grid">
            <div class="mini-item"><span>成交量</span><strong>${leader.volume || "--"}</strong></div>
            <div class="mini-item"><span>成交金額</span><strong>${leader.turnover || "--"}</strong></div>
            <div class="mini-item"><span>來源</span><strong>證交所</strong></div>
          </div>
        </div>
      `
      : '<div class="stock-detail-empty">無可用族群摘要。</div>',
    overview,
    table: `
      ${renderScrollableClassTable(`
        <div class="class-table-head">
          <span>名稱</span>
          <span>數值</span>
          <span>漲跌</span>
          <span>漲跌幅</span>
          <span>成交量</span>
          <span>成交金額</span>
          <span>走勢圖</span>
        </div>
        ${items
          .map(
            (sector, index) => `
          <article class="class-table-row" id="${escapeHtml(`sector-${sector.sourceName || sector.name}`)}">
            ${renderSectorStockName(sector)}
            <strong>${sector.value}</strong>
            <strong class="${toneClass(sector.tone)}">${sector.change}</strong>
            <strong class="${toneClass(sector.tone)}">${sector.pct}</strong>
            <span>${sector.volume || "--"}</span>
            <span>${sector.turnover || "--"}</span>
            <div class="class-chart-cell">${renderSectorLineChart(sector)}</div>
          </article>
        `,
          )
          .join("")}
      `, `${group.label}排行表格`)}
    `,
    links: renderYahooCategoryLinks(
      group,
      items.map((sector) => `<a class="class-link-chip" href="${safeUrl(`#sector-${sector.sourceName || sector.name}`)}">${escapeHtml(sector.name)}</a>`).join(""),
    ),
    sync: renderSectorSyncViewV2(items),
  };
}





function shouldRenderSectorPageRanking(group) {
  if (!group) return false;
  return group.key !== "listed" || Boolean(activeYahooSectorCategories.listed);
}

function getSectorPageRankingTitle(group) {
  const activeSubcategory = activeYahooSectorCategories[group.key]?.name;
  if (activeSubcategory) return `${activeSubcategory}類股成分股排行`;
  return `${group.label}排行`;
}

function bindSectorComparisonTooltips(container) {
  const tooltip = container.querySelector(".sector-sync-tooltip");
  const frame = container.querySelector(".sector-chart-frame");
  const guide = container.querySelector(".sector-hover-guide");
  const sectorDot = container.querySelector(".sector-hover-dot-sector");
  const benchmarkDot = container.querySelector(".sector-hover-dot-market");
  if (!tooltip || !frame || !guide || !sectorDot || !benchmarkDot) return;

  const hideTooltip = () => {
    tooltip.hidden = true;
    guide.classList.remove("is-visible");
    sectorDot.classList.remove("is-visible");
    benchmarkDot.classList.remove("is-visible");
  };

  container.querySelectorAll("[data-sync-index]").forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      const label = zone.dataset.label || "--";
      const sectorClose = Number(zone.dataset.sectorClose || "0");
      const benchmarkClose = Number(zone.dataset.benchmarkClose || "0");
      const diff = Number(zone.dataset.diff || "0");
      const sectorOpen = zone.dataset.sectorOpen || "";
      const sectorHigh = zone.dataset.sectorHigh || "";
      const sectorLow = zone.dataset.sectorLow || "";
      const sectorVolume = zone.dataset.sectorVolume || "--";
      const showTrades = zone.dataset.showTrades !== "false";
      const sectorTrades = zone.dataset.sectorTrades || "--";
      const sectorTurnover = zone.dataset.sectorTurnover || "--";
      const pointX = zone.dataset.pointX || zone.getAttribute("x") || "0";
      const sectorY = zone.dataset.sectorY || "0";
      const benchmarkY = zone.dataset.benchmarkY || "0";
      tooltip.hidden = false;
      tooltip.innerHTML = `
        <strong>${escapeHtml(label)}</strong>
        ${sectorOpen ? `<span>開盤：${escapeHtml(sectorOpen)}</span>` : ""}
        ${sectorHigh ? `<span>最高：${escapeHtml(sectorHigh)}</span>` : ""}
        ${sectorLow ? `<span>最低：${escapeHtml(sectorLow)}</span>` : ""}
        <span>收盤：${sectorClose.toFixed(2)}</span>
        <span>大盤：${benchmarkClose.toFixed(2)}</span>
        <span>成交量：${escapeHtml(sectorVolume)}</span>
        ${showTrades ? `<span>成交筆數：${escapeHtml(sectorTrades)}</span>` : ""}
        ${sectorTurnover !== "--" ? `<span>成交金額：${escapeHtml(sectorTurnover)}</span>` : ""}
        <span>差異：${diff >= 0 ? "+" : ""}${diff.toFixed(2)}%</span>
      `;
      const rect = zone.getBoundingClientRect();
      const frameRect = frame.getBoundingClientRect();
      tooltip.style.left = `${((rect.left - frameRect.left) + rect.width / 2) / frameRect.width * 100}%`;
      tooltip.style.top = `${((Math.min(rect.top - frameRect.top, frameRect.height * 0.6)) / frameRect.height) * 100}%`;
      guide.setAttribute("x1", pointX);
      guide.setAttribute("x2", pointX);
      sectorDot.setAttribute("cx", pointX);
      sectorDot.setAttribute("cy", sectorY);
      benchmarkDot.setAttribute("cx", pointX);
      benchmarkDot.setAttribute("cy", benchmarkY);
      guide.classList.add("is-visible");
      sectorDot.classList.add("is-visible");
      benchmarkDot.classList.add("is-visible");
    });
    zone.addEventListener("mouseleave", hideTooltip);
  });

  frame.addEventListener("mouseleave", hideTooltip);
}

function findYahooSectorSourceItem(groupKey, sourceName) {
  const key = String(sourceName || "");
  if (!key) return null;
  const category = activeYahooSectorCategories[groupKey];
  const cachedItems = category ? yahooSectorQuoteCache.get(`${groupKey}:${category.index}`)?.items || [] : [];
  const cachedItem = cachedItems.find((entry) => String(entry.sourceName || "") === key);
  if (cachedItem) return cachedItem;
  const storedItems = data?.yahooSectorGroups?.[groupKey] || [];
  return storedItems.find((entry) => String(entry.sourceName || "") === key) || null;
}

function bindSectorSyncControls(container, groupKey) {
  const select = container.querySelector("[data-sector-source-select]");
  select?.addEventListener("change", () => {
    const sourceName = select.value || "";
    activeYahooSectorStocks[groupKey] = sourceName;
    const item = findYahooSectorSourceItem(groupKey, sourceName);
    if (item) {
      loadYahooSectorStockChart(groupKey, item);
    }
    else renderSectorPageV2();
  });

  container.querySelectorAll("[data-sector-source]").forEach((button) => {
    button.addEventListener("click", () => {
      const sourceName = button.dataset.sectorSource || "";
      activeYahooSectorStocks[groupKey] = sourceName;
      const item = findYahooSectorSourceItem(groupKey, sourceName);
      if (item) {
        loadYahooSectorStockChart(groupKey, item);
      }
      else renderSectorPageV2();
    });
  });

  container.querySelectorAll("[data-retry-sector-chart]").forEach((button) => {
    button.addEventListener("click", () => {
      const sourceName = activeYahooSectorStocks[groupKey] || "";
      const item = findYahooSectorSourceItem(groupKey, sourceName);
      if (item) loadYahooSectorStockChart(groupKey, item);
    });
  });

  const activeSource = activeYahooSectorStocks[groupKey] || "";
  const zoomKey = `${groupKey}:${activeSource}:day`;
  const readZoomValues = () => {
    const text = container.querySelector(".sector-comparison-zoom span")?.textContent || "";
    const match = text.match(/顯示\s+(\d+)\s*\/\s*(\d+)/);
    return match ? { visible: Number(match[1]), total: Number(match[2]) } : null;
  };
  const updateComparisonZoom = (direction) => {
    const values = readZoomValues();
    if (!values) return;
    const minimum = Math.min(20, values.total);
    let next = values.visible;
    if (direction === "in") next = Math.max(minimum, Math.floor(values.visible * 0.65));
    if (direction === "out") next = Math.min(values.total, Math.ceil(values.visible / 0.65));
    if (direction === "reset") next = values.total;
    if (next === values.visible) return;
    sectorComparisonZoomCounts.set(zoomKey, next);
    sectorComparisonPanOffsets.set(zoomKey, 0);
    renderSectorPageV2();
  };

  container.querySelectorAll("[data-comparison-zoom]").forEach((button) => {
    button.addEventListener("click", () => updateComparisonZoom(button.dataset.comparisonZoom));
  });

  const updateComparisonPan = (direction) => {
    const values = readZoomValues();
    if (!values) return;
    const current = sectorComparisonPanOffsets.get(zoomKey) || 0;
    const maxOffset = Math.max(values.total - values.visible, 0);
    const step = Math.max(1, Math.round(values.visible * 0.35));
    const next = direction === "older"
      ? Math.min(maxOffset, current + step)
      : Math.max(0, current - step);
    if (next === current) return;
    sectorComparisonPanOffsets.set(zoomKey, next);
    renderSectorPageV2();
  };

  container.querySelectorAll("[data-comparison-pan]").forEach((button) => {
    button.addEventListener("click", () => updateComparisonPan(button.dataset.comparisonPan));
  });

  const comparisonFrame = container.querySelector(".sector-chart-frame");
  comparisonFrame?.addEventListener("wheel", (event) => {
    event.preventDefault();
    updateComparisonZoom(event.deltaY < 0 ? "in" : "out");
  }, { passive: false });
  bindHorizontalChartPan(comparisonFrame, updateComparisonPan);
}

function renderSectorPageV2() {
  const tabsContainer = document.querySelector(".class-tabs");
  const linksContainer = document.getElementById("class-links");
  const sortSlot = document.getElementById("sector-sort-slot");
  const boardTitle = document.getElementById("sector-board-title");
  const heroCard = document.getElementById("class-hero-card");
  const overviewGrid = document.getElementById("sector-overview-grid");
  const sectorGrid = document.getElementById("sector-grid");
  const syncView = document.getElementById("sector-sync-view");
  const sourceNote = document.getElementById("sector-source-note");
  if (!tabsContainer || !linksContainer || !heroCard || !overviewGrid || !syncView) return;

  renderWeightedIndexPanel();

  const params = new URLSearchParams(window.location.search);
  const requestedGroup = params.get("group")?.trim() || "";
  const supportedGroups = new Set(["listed", "otc", "emerging", "electronic", "concept", "group"]);
  const requestedKey = tabsContainer.dataset.activeCategory
    || (supportedGroups.has(requestedGroup) ? requestedGroup : "listed");
  if (ensureDefaultYahooSectorCategory(requestedKey)) return;

  const groups = getSectorPageGroups();
  const activeKey = requestedKey || groups[0]?.key || "listed";
  const activeGroup = groups.find((group) => group.key === activeKey) || groups[0];
  tabsContainer.dataset.activeCategory = activeGroup?.key || "listed";

  tabsContainer.innerHTML = groups
    .map(
      (group) => `
    <button class="class-tab ${group.key === activeGroup.key ? "is-active" : ""}" type="button" data-category="${group.key}">${group.label}</button>
  `,
    )
    .join("");

  const rendered = renderSectorGroup(activeGroup);
  heroCard.innerHTML = rendered.hero;
  overviewGrid.innerHTML = rendered.overview;
  linksContainer.innerHTML = rendered.links;
  if (sectorGrid) {
    const board = sectorGrid.closest(".class-board");
    const showRanking = shouldRenderSectorPageRanking(activeGroup);
    if (board) board.hidden = !showRanking;
    if (showRanking) {
      sectorGrid.innerHTML = rendered.table;
      if (boardTitle) boardTitle.textContent = getSectorPageRankingTitle(activeGroup);
      if (sortSlot) {
        sortSlot.innerHTML = renderSectorSortControl();
      } else {
        linksContainer.innerHTML = `${renderSectorSortControl()}${rendered.links}`;
      }
    } else {
      sectorGrid.innerHTML = "";
      if (sortSlot) sortSlot.innerHTML = "";
    }
  }
  syncView.innerHTML = rendered.sync;
  bindSectorComparisonTooltips(syncView);
  bindSectorSyncControls(syncView, activeGroup.key);

  if (sourceNote) {
    const snapshotDate = data.snapshotDate || "--";
    const cachedAt = data.cachedAt || "--";
    const activeSubcategory = activeYahooSectorCategories[activeGroup.key]?.name;
    const categoryLabel = activeSubcategory ? `${activeGroup.label} / ${activeSubcategory}` : activeGroup.label;
    sourceNote.textContent = `${categoryLabel} 資料已同步自 ${activeGroup.source}。更新時間：${cachedAt}。資料日期：${snapshotDate}。`;
  }

  tabsContainer.querySelectorAll("[data-category]").forEach((button) => {
    button.addEventListener("click", () => {
      tabsContainer.dataset.activeCategory = button.dataset.category || "listed";
      renderSectorPageV2();
    });
  });
  (sortSlot || linksContainer).querySelector("[data-sector-sort]")?.addEventListener("change", (event) => {
    sectorSortState.key = event.target.value || "source_order";
    renderSectorPageV2();
  });
}

function renderSectorSyncViewV2(sectors) {
  const benchmark = getWeightedIndexSector();
  const sectorOnly = sectors.filter((sector) => !isExcludedSector(sector));
  const groupKey = document.querySelector(".class-tabs")?.dataset.activeCategory || "listed";
  const activeSource = activeYahooSectorStocks[groupKey];
  const activeSector = pickDefaultSectorSyncItem(sectorOnly, activeSource);
  if (!activeSector || !benchmark) {
    return '<div class="stock-detail-empty">無可用比較資料。</div>';
  }
  const historyCount = (activeSector.comparisonSeries?.day || []).length;
  if (historyCount < 20) {
    const loadingKey = `${groupKey}:${activeSector.sourceName || ""}`;
    const isLoading = yahooSectorChartLoading.has(loadingKey);
    const errorMessage = yahooSectorChartErrors.get(loadingKey);
    activeYahooSectorStocks[groupKey] = activeSector.sourceName;
    if (!isLoading && !errorMessage && activeSector.sourceName && hasYahooChartSymbol(activeSector)) {
      setTimeout(() => loadYahooSectorStockChart(groupKey, activeSector), 0);
    }
    if (!hasYahooChartSymbol(activeSector)) {
      return `
        <div class="sector-sync-loading">
          <strong>${activeSector.name} 線上走勢資料同步中</strong>
          <span>目前已取得即時摘要；歷史比較線需要至少 20 筆 TWSE 線上交易日資料。</span>
        </div>
      `;
    }
    if (isLoading) {
      return `
        <div class="sector-sync-loading">
          <strong>正在載入 ${activeSector.name} 完整走勢</strong>
          <span>歷史資料取得中，完成後會自動顯示比較圖。</span>
        </div>
      `;
    }
    if (activeSector.summaryOnly) {
      return `
        <div class="sector-sync-loading">
          <strong>${activeSector.name} 摘要行情</strong>
          <span>${errorMessage ? `${errorMessage} ` : ""}目前顯示 Yahoo 即時摘要；完整比較線請切回證交所類股，或點選具股票代號的分類項目。</span>
          <button class="sector-chart-retry" type="button" data-retry-sector-chart>重新載入</button>
        </div>
      `;
    }
    return `
      <div class="sector-sync-loading is-error">
        <strong>${activeSector.name} 完整走勢資料不足</strong>
        <span>${errorMessage || `目前僅有 ${historyCount} 筆歷史資料，暫時無法繪製比較圖。`}</span>
        <button class="sector-chart-retry" type="button" data-retry-sector-chart>重新載入</button>
      </div>
    `;
  }

  const activeMode = "day";
  activeYahooSectorStocks[groupKey] = activeSector.sourceName;
  const benchmarkForChart = (activeSector.benchmarkComparisonSeries?.day || []).length > 1
    ? { ...benchmark, comparisonSeries: activeSector.benchmarkComparisonSeries }
    : benchmark;
  const totalPoints = buildSectorComparisonModel(activeSector, benchmarkForChart, activeMode).length;
  const zoomKey = `${groupKey}:${activeSector.sourceName}:${activeMode}`;
  const minimumVisible = Math.min(20, totalPoints);
  const savedVisibleCount = sectorComparisonZoomCounts.get(zoomKey);
  const visibleCount = Number.isFinite(savedVisibleCount)
    ? Math.max(minimumVisible, Math.min(savedVisibleCount, totalPoints))
    : totalPoints;
  const panOffset = Math.max(0, Math.min(sectorComparisonPanOffsets.get(zoomKey) || 0, totalPoints - visibleCount));
  const chart = renderSectorComparisonChart(activeSector, benchmarkForChart, activeMode, { visibleCount, panOffset });
  const technical = activeSector.technicalAnalysis || {};
  const benchmarkTechnical = benchmark.technicalAnalysis || {};
  const diff = chart.points.length ? chart.points[chart.points.length - 1].diff : 0;

  return `
    <div class="sector-sync-stage">
      <div class="sector-sync-toolbar">
        ${renderCompactSectorSyncPicker(sectorOnly, activeSector, sectorOnly.length)}
      </div>

      <div class="sector-sync-layout sector-sync-layout-yahoo">
        <div class="sector-sync-main">
          <div class="sector-sync-compare-head">
            <div>
              <p class="eyebrow">主圖 + 比較線</p>
              <h3>${activeSector.name} 對照 ${benchmark.name}</h3>
            </div>
            <div class="sector-sync-compare-tags">
              <span class="compare-tag compare-tag-primary">${activeSector.pct}</span>
              <span class="compare-tag compare-tag-benchmark">${benchmark.pct}</span>
            </div>
          </div>
          <div class="sector-chart-zoom sector-comparison-zoom" aria-label="主圖與比較線縮放控制">
            <button type="button" data-comparison-zoom="in" ${visibleCount <= minimumVisible ? "disabled" : ""}>＋ 放大</button>
            <button type="button" data-comparison-zoom="out" ${visibleCount >= totalPoints ? "disabled" : ""}>－ 縮小</button>
            <button type="button" data-comparison-zoom="reset" ${visibleCount >= totalPoints ? "disabled" : ""}>重設</button>
            <button type="button" data-comparison-pan="older" ${panOffset >= totalPoints - visibleCount ? "disabled" : ""}>← 往前</button>
            <button type="button" data-comparison-pan="newer" ${panOffset <= 0 ? "disabled" : ""}>往後 →</button>
            <span>顯示 ${chart.visiblePoints} / ${chart.totalPoints} 根</span>
          </div>
          ${chart.html}
          <div class="sector-sync-compare-strip">
            <div class="mini-item">
              <span>目前查看</span>
              <strong>${activeSector.name}</strong>
              <small class="${toneClass(activeSector.tone)}">漲跌幅 ${activeSector.pct}</small>
            </div>
            <div class="mini-item">
              <span>對照基準</span>
              <strong>${benchmark.name}</strong>
              <small class="${toneClass(benchmark.tone)}">漲跌幅 ${benchmark.pct}</small>
            </div>
            <div class="mini-item comparison-difference">
              <span>相對差異</span>
              <strong class="${diff >= 0 ? "up" : "down"}">${diff >= 0 ? "+" : ""}${diff.toFixed(2)}%</strong>
              <small>${diff >= 0 ? `${activeSector.name} 相對領先` : `${activeSector.name} 相對落後`}</small>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

function getVolatilityBundle() {
  return { cboe: data?.marketVolatility || null };
}

function normalizeInternationalIndexItem(item) {
  const key = String(item?.key || item?.symbol || item?.name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  const series = (item?.series || [])
    .map((point) => ({
      date: point.date,
      value: point.value ?? point.close,
      open: point.open,
      high: point.high,
      low: point.low,
      volume: point.volume,
    }))
    .filter((point) => point.date && point.value !== undefined && point.value !== null);
  return {
    ...item,
    key,
    name: item?.name || item?.symbol || "Index",
    series,
  };
}

function getInternationalIndexItems(bundle = {}) {
  const items = Array.isArray(data?.marketInternationalIndexes)
    ? data.marketInternationalIndexes.map(normalizeInternationalIndexItem)
    : [];
  const vix = bundle.cboe;
  if (vix?.series?.length) {
    items.unshift(normalizeInternationalIndexItem({
      key: "vix",
      name: "VIX 指數",
      symbol: vix.symbol || "^VIX",
      value: vix.value,
      pct: vix.pct,
      tone: vix.tone,
      series: vix.series.map((point) => ({ date: point.date, value: point.value })),
    }));
  }
  const seen = new Set();
  return items.filter((item) => {
    if (!item.key || seen.has(item.key)) return false;
    seen.add(item.key);
    return true;
  });
}

function loadInternationalIndexesIfNeeded() {
  const page = document.body.dataset.page;
  if (page !== "market") return;
  const current = Array.isArray(data?.marketInternationalIndexes) ? data.marketInternationalIndexes : [];
  if (current.length >= 18 || internationalIndexesPromise) return;
  internationalIndexesPromise = fetchWithTimeout(
    "/api/market/international-indexes",
    { cache: "no-store" },
    90000,
  )
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      const indexes = Array.isArray(payload?.indexes) ? payload.indexes : [];
      if (!indexes.length || !data) return;
      data.marketInternationalIndexes = indexes;
      renderWeightedIndexPanel();
    })
    .catch((error) => console.warn("Failed to load international indexes:", error))
    .finally(() => {
      internationalIndexesPromise = null;
    });
}

function startVixPolling() {
  // VIX is imported as part of the live sectors payload; no separate poller is needed here.
}

function isVixComparisonItem(item) {
  return String(item?.key || "").toLowerCase() === "vix" || /vix|波動|恐慌/i.test(`${item?.name || ""} ${item?.symbol || ""}`);
}

function getComparisonItemLatestValue(item) {
  const daySeries = item?.comparisonSeries?.day || item?.series || [];
  const latestPoint = daySeries.at?.(-1) || {};
  return parseMarketNumber(item?.value ?? latestPoint.close ?? latestPoint.value);
}

function getComparisonItemPreviousValue(item) {
  const daySeries = item?.comparisonSeries?.day || item?.series || [];
  const previousPoint = daySeries.length > 1 ? daySeries[daySeries.length - 2] : {};
  return parseMarketNumber(item?.previousClose ?? previousPoint.close ?? previousPoint.value);
}

function buildVixSentimentMetrics(item, chart) {
  const daySeries = item?.comparisonSeries?.day || item?.series || [];
  const latestPoint = chart.points?.at(-1) || {};
  const latestValue = getComparisonItemLatestValue(item);
  const previousValue = getComparisonItemPreviousValue(item);
  const change = Number.isFinite(latestValue) && Number.isFinite(previousValue) ? latestValue - previousValue : null;
  const changePct = Number.isFinite(change) && previousValue ? (change / previousValue) * 100 : null;
  const band = getVixSentimentBand(latestValue);
  const score = getVixRiskTemperature(latestValue);
  const moveText = item?.pct || formatSignedPercentValue(changePct);
  return [
    { key: "sentiment", label: "恐慌指標", value: "VIX", toneClass: "flat" },
    { key: "vix-level", label: "VIX 指數", value: Number.isFinite(latestValue) ? latestValue.toFixed(2) : item?.value || "--", toneClass: band.tone === "red" || band.tone === "purple" ? "down" : "flat" },
    { key: "band", label: "恐慌區間", value: band.label || "--", toneClass: band.tone === "red" || band.tone === "purple" ? "down" : band.tone === "green" ? "up" : "flat" },
    { key: "risk-temp", label: "風險溫度", value: score === null ? "--" : `${score}/100`, toneClass: score !== null && score >= 45 ? "down" : "up" },
    { key: "vix-change", label: "情緒變化", value: moveText || "--", toneClass: Number.isFinite(change) ? getVixRiskToneClass(change) : toneClass(item?.tone) },
    { key: "visible", label: "顯示情緒點", value: chart.visiblePoints || 0 },
    { key: "total", label: "總情緒點", value: chart.totalPoints || daySeries.length || 0 },
    { key: "latest", label: "最新情緒日", value: latestPoint?.label || latestPoint?.date || daySeries.at(-1)?.date || "--" },
  ];
}

function buildSingleIndexQuoteMetrics(item, chart = {}) {
  if (isVixComparisonItem(item)) return buildVixSentimentMetrics(item, chart);
  const daySeries = item?.comparisonSeries?.day || item?.series || [];
  const latestPoint = daySeries.at?.(-1) || {};
  const previousPoint = daySeries.length > 1 ? daySeries[daySeries.length - 2] : {};
  return [
    { key: "price", label: "成交", value: item?.value || latestPoint.close || latestPoint.value || "--" },
    { key: "pct", label: "漲跌幅", value: item?.pct || "--", toneClass: toneClass(item?.tone) },
    { key: "previous", label: "昨收", value: item?.previousClose || previousPoint.close || previousPoint.value || "--" },
    { key: "open", label: "開盤", value: item?.open || latestPoint.open || "--" },
    { key: "high", label: "最高", value: item?.high || latestPoint.high || "--" },
    { key: "low", label: "最低", value: item?.low || latestPoint.low || "--" },
    { key: "volume", label: "總量", value: item?.volume || latestPoint.volume || "--" },
  ];
}

function buildInternationalSelectionMetrics(chart, items) {
  const latestPoint = chart.points?.at(-1);
  if (items.length === 1) {
    return buildSingleIndexQuoteMetrics(items[0], chart);
  }
  const values = latestPoint?.values || [];
  const ranked = [...values].sort((left, right) => right.norm - left.norm);
  const leader = ranked[0];
  const laggard = ranked.at(-1);
  const spread = leader && laggard ? leader.norm - laggard.norm : null;
  const aboveBase = values.filter((item) => Number.isFinite(item.norm) && item.norm >= 100).length;
  const hasVix = items.some(isVixComparisonItem);
  return [
    { key: "compare-count", label: "對比指數", value: `${items.length || 0} 個` },
    { key: "leader", label: "相對領先", value: leader ? `${leader.name} ${leader.norm.toFixed(2)}` : "--", toneClass: "up" },
    { key: "laggard", label: "相對落後", value: laggard ? `${laggard.name} ${laggard.norm.toFixed(2)}` : "--", toneClass: "down" },
    { key: "spread", label: "分歧幅度", value: Number.isFinite(spread) ? `${spread.toFixed(2)} pt` : "--" },
    { key: "breadth", label: "站上基準", value: `${aboveBase}/${items.length || 0}` },
    { key: "visible", label: "顯示資料點", value: chart.visiblePoints || 0 },
    { key: "total", label: "共同資料點", value: chart.totalPoints || 0 },
    { key: "latest", label: hasVix ? "最新情緒日" : "最新對比日", value: latestPoint?.label || latestPoint?.date || "--" },
  ];
}

function alignIndexSeries(items) {
  const validItems = (items || []).filter((item) => Array.isArray(item.series) && item.series.length);
  if (!validItems.length) return [];
  const dateSets = validItems.map((item) => new Set(item.series.map((point) => point.date).filter(Boolean)));
  const sharedDates = [...dateSets[0]].filter((date) => dateSets.every((set) => set.has(date))).sort();
  const lookups = validItems.map((item) => new Map(item.series.map((point) => [point.date, point])));
  return sharedDates
    .map((date) => {
      const values = validItems.map((item, index) => {
        const point = lookups[index].get(date) || {};
        return {
          key: item.key,
          name: item.name,
          value: parseMarketNumber(point.value ?? point.close),
          open: point.open,
          high: point.high,
          low: point.low,
          volume: point.volume,
        };
      });
      return values.every((item) => Number.isFinite(item.value)) ? { date, label: date, values } : null;
    })
    .filter(Boolean);
}

function renderFreeIndexComparisonChart(items, title, options = {}) {
  const singleVixMode = items.length === 1 && isVixComparisonItem(items[0]);
  const allAligned = alignIndexSeries(items);
  const requestedCount = Number(options.visibleCount);
  const aligned = Number.isFinite(requestedCount) && requestedCount > 1
    ? sliceVisibleWindow(allAligned, requestedCount, options.panOffset || 0)
    : allAligned;
  if (aligned.length < 2 || !items.length) {
    return {
      html: '<div class="class-line-empty">比較資料不足，暫不繪製指數比對圖。</div>',
      points: [],
      totalPoints: allAligned.length,
      visiblePoints: 0,
    };
  }

  const width = 980;
  const height = 520;
  const pad = { top: 34, right: 28, bottom: 58, left: 58 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const bases = new Map(aligned[0].values.map((item) => [item.key, item.value || 1]));
  const normalized = aligned.map((point, index) => ({
    ...point,
    index,
    values: point.values.map((item) => ({
      ...item,
      norm: singleVixMode ? item.value : (item.value / (bases.get(item.key) || 1)) * 100,
    })),
  }));
  const allValues = normalized.flatMap((point) => point.values.map((item) => item.norm));
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const range = maxValue - minValue || 1;
  const step = plotWidth / Math.max(normalized.length - 1, 1);
  const xAt = (index) => pad.left + index * step;
  const yAt = (value) => pad.top + ((maxValue - value) / range) * plotHeight;
  const colors = ["#38bdf8", "#f59e0b", "#22c55e", "#ef4444", "#a78bfa", "#14b8a6", "#f97316"];
  const paths = items.map((item, itemIndex) => {
    const points = normalized.map((point, index) => {
      const value = point.values.find((entry) => entry.key === item.key)?.norm;
      return { x: xAt(index), y: yAt(value), value };
    });
    return `<path d="${buildPath(points)}" fill="none" stroke="${colors[itemIndex % colors.length]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`;
  }).join("");
  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * plotHeight;
    const label = maxValue - ratio * range;
    return `<line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line><text x="8" y="${y + 5}">${label.toFixed(1)}</text>`;
  }).join("");
  const vixThresholdLines = singleVixMode
    ? [15, 20, 30, 40]
      .filter((value) => value >= minValue && value <= maxValue)
      .map((value) => {
        const y = yAt(value);
        return `<line class="vix-threshold-line" x1="${pad.left}" y1="${y.toFixed(1)}" x2="${width - pad.right}" y2="${y.toFixed(1)}"></line><text class="vix-threshold-label" x="${width - pad.right - 54}" y="${(y - 6).toFixed(1)}">VIX ${value}</text>`;
      })
      .join("")
    : "";
  const hoverZones = normalized.map((point, index) => {
    const left = index === 0 ? pad.left : xAt(index) - step / 2;
    const zoneWidth = index === normalized.length - 1 ? (width - pad.right) - left : step;
    const payload = point.values.map((item) => `${item.name}:${Number(item.value).toFixed(2)}:${item.norm.toFixed(2)}`).join("|");
    return `<rect class="sector-hover-zone" x="${left.toFixed(1)}" y="${pad.top}" width="${Math.max(zoneWidth, 8).toFixed(1)}" height="${plotHeight}" data-sync-index="${index}" data-tooltip-mode="free-index" data-label="${escapeHtml(point.label)}" data-payload="${escapeHtml(payload)}"></rect>`;
  }).join("");
  const legend = items.map((item, index) => `<span><i class="legend-swatch" style="background:${colors[index % colors.length]}"></i>${escapeHtml(item.name)}</span>`).join("");
  const latestVix = singleVixMode ? normalized.at(-1)?.values?.[0]?.value : null;
  const latestVixBand = getVixSentimentBand(latestVix);
  const summaryTitle = singleVixMode ? "VIX 市場恐慌情緒走勢" : title;
  const summaryStrong = singleVixMode ? `${latestVixBand.label} · ${latestVix ? latestVix.toFixed(2) : "--"}` : "Base = 100";
  const legendNote = singleVixMode ? "<span>VIX 上升代表避險與恐慌升溫</span>" : "";

  return {
    html: `
      <div class="sector-sync-chart-summary"><span>${escapeHtml(summaryTitle)}</span><strong>${escapeHtml(summaryStrong)}</strong><span>${normalized[0].label} 至 ${normalized.at(-1).label}</span></div>
      <div class="sector-chart-frame">
        <svg class="sector-comparison-chart ${singleVixMode ? "vix-sentiment-comparison-chart" : ""}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(summaryTitle)}">
          <g class="chart-grid">${gridLines}</g>
          ${singleVixMode ? vixThresholdLines : `<line class="sector-base-line" x1="${pad.left}" y1="${yAt(100)}" x2="${width - pad.right}" y2="${yAt(100)}"></line>`}
          ${paths}
          <line class="sector-hover-guide" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
          <circle class="sector-hover-dot sector-hover-dot-sector" cx="${pad.left}" cy="${pad.top}" r="5"></circle>
          <g class="chart-labels"><text x="${pad.left}" y="${height - 18}">${normalized[0].label}</text><text x="${width - pad.right - 90}" y="${height - 18}">${normalized.at(-1).label}</text></g>
          <g class="sector-hover-zones">${hoverZones}</g>
        </svg>
        <div class="sector-sync-tooltip" hidden></div>
      </div>
      <div class="sector-chart-legend">${legend}${legendNote}</div>
    `,
    points: normalized.map((point, index) => ({ ...point, x: xAt(index), sectorY: yAt(point.values[0]?.norm || 100) })),
    totalPoints: allAligned.length,
    visiblePoints: normalized.length,
  };
}

function renderIndexComparisonInsight(chart, activeMode = "comparison", items = []) {
  const latest = chart.points?.at(-1);
  const values = latest?.values || [];
  if (!values.length) {
    return `
      <article class="analysis-card weighted-index-note-card-inline weighted-index-comparison-card">
        <div class="card-title-row"><h4>指數對比判讀</h4><span class="chip chip-gold">資料不足</span></div>
        <p class="card-copy">目前所選指數缺少共同日期資料，暫時無法建立相對強弱、分歧幅度與同步性判讀。</p>
      </article>
    `;
  }
  const ranked = [...values].sort((left, right) => right.norm - left.norm);
  const leader = ranked[0];
  const laggard = ranked.at(-1);
  const spread = leader && laggard ? leader.norm - laggard.norm : null;
  const aboveBase = values.filter((item) => Number.isFinite(item.norm) && item.norm >= 100).length;
  const hasVix = values.some((item) => String(item.key).toLowerCase() === "vix") || items.some(isVixComparisonItem);
  const vixValue = values.find((item) => String(item.key).toLowerCase() === "vix")?.value;
  const vixBand = getVixSentimentBand(vixValue);
  const regime = Number.isFinite(spread) && spread >= 12
    ? "高度分歧"
    : aboveBase >= Math.ceil((values.length || 1) * 0.65)
      ? "同步偏強"
      : aboveBase <= Math.floor((values.length || 1) * 0.35)
        ? "同步偏弱"
        : "輪動分歧";
  const summary = leader && laggard
    ? `${regime}：${leader.name} 目前相對領先，${laggard.name} 相對落後，兩者分歧 ${spread.toFixed(2)} 點；${aboveBase}/${values.length} 個指數站上視窗起點。`
    : "請選擇至少一個指數進行比對。";
  const vixNote = hasVix && Number.isFinite(vixValue)
    ? `VIX 目前 ${vixValue.toFixed(2)}，位於 ${vixBand.label}，${vixBand.text}`
    : "未選入 VIX 時，本卡主要觀察股市指數之間的相對強弱與輪動分歧。";
  return `
    <article class="analysis-card weighted-index-note-card-inline weighted-index-comparison-card">
      <div class="card-title-row"><h4>指數對比判讀</h4><span class="chip chip-blue">${escapeHtml(regime)}</span></div>
      <p class="card-copy">${escapeHtml(summary)}</p>
      <div class="weighted-index-comparison-grid">
        <div><span>相對領先</span><strong class="up">${leader ? `${escapeHtml(leader.name)} ${leader.norm.toFixed(2)}` : "--"}</strong></div>
        <div><span>相對落後</span><strong class="down">${laggard ? `${escapeHtml(laggard.name)} ${laggard.norm.toFixed(2)}` : "--"}</strong></div>
        <div><span>分歧幅度</span><strong>${Number.isFinite(spread) ? `${spread.toFixed(2)} pt` : "--"}</strong></div>
        <div><span>共同日期</span><strong>${chart.visiblePoints || 0} / ${chart.totalPoints || 0}</strong></div>
      </div>
      <ul class="analysis-list weighted-index-comparison-notes">
        <li>${escapeHtml(vixNote)}</li>
        <li>${escapeHtml(Number.isFinite(spread) && spread >= 12 ? "分歧擴大代表資金集中或避險輪動，需確認領先指數是否仍有成交量與基本面支撐。" : "分歧未明顯擴大時，可用多指數同步性判斷風險偏好是否延續。")}</li>
      </ul>
    </article>
  `;
}

function renderSingleIndexComparisonInsight(item, chart) {
  const latest = chart.points?.at(-1);
  const first = chart.points?.[0];
  const latestValue = latest?.values?.[0]?.value ?? getComparisonItemLatestValue(item);
  const firstValue = first?.values?.[0]?.value;
  const previousValue = getComparisonItemPreviousValue(item);
  const windowChange = Number.isFinite(latestValue) && Number.isFinite(firstValue) && firstValue
    ? ((latestValue - firstValue) / firstValue) * 100
    : null;
  if (isVixComparisonItem(item)) {
    const band = getVixSentimentBand(latestValue);
    const score = getVixRiskTemperature(latestValue);
    const dailyChange = Number.isFinite(latestValue) && Number.isFinite(previousValue) ? latestValue - previousValue : null;
    const moveTone = getVixRiskToneClass(dailyChange);
    return `
      <article class="analysis-card weighted-index-note-card-inline weighted-index-comparison-card is-vix-sentiment">
        <div class="card-title-row"><h4>市場恐慌情緒</h4><span class="chip chip-gold">${escapeHtml(band.label)}</span></div>
        <p class="card-copy">VIX 目前 ${Number.isFinite(latestValue) ? latestValue.toFixed(2) : "--"}，風險溫度 ${score === null ? "--" : `${score}/100`}。${escapeHtml(band.text)}</p>
        <div class="weighted-index-comparison-grid">
          <div><span>VIX 指數</span><strong class="${moveTone}">${Number.isFinite(latestValue) ? latestValue.toFixed(2) : "--"}</strong></div>
          <div><span>恐慌區間</span><strong>${escapeHtml(band.label || "--")}</strong></div>
          <div><span>視窗變化</span><strong class="${Number.isFinite(windowChange) ? windowChange > 0 ? "down" : "up" : "flat"}">${formatSignedPercentValue(windowChange)}</strong></div>
          <div><span>情緒樣本</span><strong>${chart.visiblePoints || 0} / ${chart.totalPoints || 0}</strong></div>
        </div>
        <ul class="analysis-list weighted-index-comparison-notes">
          <li>VIX 上升代表避險需求與波動預期升溫；VIX 下降通常代表恐慌降溫、風險偏好改善。</li>
          <li>${escapeHtml(Number.isFinite(latestValue) && latestValue >= 20 ? "目前已進入警戒以上區間，應搭配台股加權與國際指數是否同步轉弱觀察。" : "目前未進入高恐慌區，仍需留意過低波動後的回補風險。")}</li>
        </ul>
      </article>
    `;
  }
  return `
    <article class="analysis-card weighted-index-note-card-inline weighted-index-comparison-card">
      <div class="card-title-row"><h4>單一指數走勢檢視</h4><span class="chip chip-blue">Index</span></div>
      <p class="card-copy">${escapeHtml(item.name)} 在目前視窗 ${Number.isFinite(windowChange) ? `${windowChange >= 0 ? "上漲" : "下跌"} ${Math.abs(windowChange).toFixed(2)}%` : "資料仍在累積"}；此模式用來觀察單一市場自身趨勢，若要判斷資金輪動請勾選兩個以上指數。</p>
      <div class="weighted-index-comparison-grid">
        <div><span>目前指數</span><strong>${Number.isFinite(latestValue) ? formatGlobalValue(latestValue, 2) : item.value || "--"}</strong></div>
        <div><span>視窗變化</span><strong class="${Number.isFinite(windowChange) ? windowChange >= 0 ? "up" : "down" : "flat"}">${formatSignedPercentValue(windowChange)}</strong></div>
        <div><span>顯示資料點</span><strong>${chart.visiblePoints || 0}</strong></div>
        <div><span>最新日期</span><strong>${latest?.label || latest?.date || "--"}</strong></div>
      </div>
    </article>
  `;
}

function renderWeightedTechnicalInsightCard(weightedIndex, activeMode, trendModel = []) {
  const technical = weightedIndex?.technicalAnalysis || {};
  const modeLabel = activeMode === "week" ? "週線" : activeMode === "month" ? "月線" : "日線";
  const points = Array.isArray(trendModel) && trendModel.length
    ? trendModel
    : buildSectorTrendModel(weightedIndex, activeMode);
  if (points.length < 2) {
    return `
      <article class="analysis-card weighted-index-note-card-inline weighted-technical-card">
        <div class="card-title-row"><h4>技術判讀</h4><span class="chip chip-blue">${modeLabel}</span></div>
        <p class="card-copy">${escapeHtml(technical.summary || "目前趨勢資料不足，暫以成交、漲跌幅與 VIX 風險溫度輔助判斷。")}</p>
      </article>
    `;
  }

  const latest = points.at(-1);
  const previous = points.at(-2);
  const closes = points.map((item) => item.sectorClose).filter(Number.isFinite);
  const latestClose = latest.sectorClose;
  const previousClose = previous?.sectorClose;
  const firstClose = points[0]?.sectorClose;
  const periodChange = firstClose ? ((latestClose - firstClose) / firstClose) * 100 : null;
  const lastChange = previousClose ? ((latestClose - previousClose) / previousClose) * 100 : null;
  const ma5 = movingAverage(closes, 5).at(-1);
  const ma20 = movingAverage(closes, 20).at(-1);
  const ma5Gap = Number.isFinite(ma5) && ma5 ? ((latestClose - ma5) / ma5) * 100 : null;
  const ma20Gap = Number.isFinite(ma20) && ma20 ? ((latestClose - ma20) / ma20) * 100 : null;
  const recent = points.slice(-Math.min(20, points.length));
  const recentHigh = Math.max(...recent.map((item) => item.high).filter(Number.isFinite));
  const recentLow = Math.min(...recent.map((item) => item.low).filter(Number.isFinite));
  const rangePosition = Number.isFinite(recentHigh) && Number.isFinite(recentLow) && recentHigh !== recentLow
    ? ((latestClose - recentLow) / (recentHigh - recentLow)) * 100
    : null;
  const rangeLabel = !Number.isFinite(rangePosition)
    ? "區間資料不足"
    : rangePosition >= 75
      ? "接近區間高檔"
      : rangePosition <= 25
        ? "靠近區間低檔"
        : "位於區間中段";
  const latestVolume = parseMarketNumber(latest.volumeValue ?? latest.volume);
  const volumeSamples = recent
    .map((item) => parseMarketNumber(item.volumeValue ?? item.volume))
    .filter(Number.isFinite);
  const avgVolume = volumeSamples.length
    ? volumeSamples.reduce((sum, value) => sum + value, 0) / volumeSamples.length
    : null;
  const volumeRatio = Number.isFinite(latestVolume) && Number.isFinite(avgVolume) && avgVolume
    ? (latestVolume / avgVolume) * 100
    : null;
  const signedPercent = (value) => Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
  const latestTone = Number.isFinite(lastChange) && lastChange > 0 ? "up" : Number.isFinite(lastChange) && lastChange < 0 ? "down" : "flat";
  const maState = Number.isFinite(ma5Gap) && Number.isFinite(ma20Gap)
    ? `收盤位於 MA5 ${signedPercent(ma5Gap)}、MA20 ${signedPercent(ma20Gap)}`
    : Number.isFinite(ma5Gap)
      ? `收盤位於 MA5 ${signedPercent(ma5Gap)}`
      : "均線資料累積中";
  const volumeState = Number.isFinite(volumeRatio)
    ? `最新量能為近 ${volumeSamples.length} 根平均的 ${volumeRatio.toFixed(0)}%`
    : `成交量 ${weightedIndex?.volume || latest.volume || "--"}`;
  const action = (() => {
    if (technical.bias === "bullish" && Number.isFinite(rangePosition) && rangePosition >= 75) {
      return "偏多但已接近近期高檔，追價前先確認量能是否持續放大。";
    }
    if (technical.bias === "bullish") {
      return "趨勢偏多，若回測均線不破，可視為強勢整理觀察點。";
    }
    if (technical.bias === "bearish") {
      return "趨勢偏弱，反彈若無量能配合，應優先控管持股風險。";
    }
    return "多空仍在整理，等待收盤價突破區間或量能明顯擴大再提高判斷權重。";
  })();

  return `
    <article class="analysis-card weighted-index-note-card-inline weighted-technical-card">
      <div class="card-title-row">
        <h4>技術判讀</h4>
        <span class="chip ${technical.bias === "bearish" ? "chip-red" : technical.bias === "bullish" ? "chip-green" : "chip-blue"}">${escapeHtml(technical.signal || modeLabel)}</span>
      </div>
      <p class="weighted-technical-summary">${escapeHtml(technical.summary || "依收盤價、均線、區間與量能綜合判斷目前技術位置。")}</p>
      <div class="weighted-technical-grid">
        <div><span>趨勢</span><strong class="${latestTone}">${signedPercent(periodChange)}</strong><small>${escapeHtml(points[0].label)} 至 ${escapeHtml(latest.label)}</small></div>
        <div><span>均線</span><strong>${Number.isFinite(ma5) ? formatGlobalValue(ma5, 0) : "--"}</strong><small>${escapeHtml(maState)}</small></div>
        <div><span>量能</span><strong>${Number.isFinite(volumeRatio) ? `${volumeRatio.toFixed(0)}%` : "--"}</strong><small>${escapeHtml(volumeState)}</small></div>
        <div><span>區間</span><strong>${Number.isFinite(rangePosition) ? `${rangePosition.toFixed(0)}%` : "--"}</strong><small>${escapeHtml(rangeLabel)}</small></div>
      </div>
      <ul class="analysis-list weighted-technical-list">
        <li>最新一根 ${modeLabel} 漲跌 ${signedPercent(lastChange)}，收盤 ${formatGlobalValue(latestClose, 2)}。</li>
        <li>${escapeHtml(maState)}；近期高低區間 ${formatGlobalValue(recentLow, 2)} 至 ${formatGlobalValue(recentHigh, 2)}。</li>
        <li>${escapeHtml(action)}</li>
      </ul>
    </article>
  `;
}

function getWeightedComponentSectorCandidates(weightedIndex) {
  const weightedSource = String(weightedIndex?.sourceName || "");
  const weightedName = String(weightedIndex?.name || "");
  return (data?.sectors || []).filter((sector) => {
    if (!sector || sector === weightedIndex) return false;
    const source = String(sector.sourceName || sector.name || "");
    const name = String(sector.name || "");
    if (!source || source === weightedSource || name === weightedName) return false;
    if (isExcludedSector(sector)) return false;
    if (sector.chartSource && sector.chartSource !== "twse") return false;
    return ((sector.comparisonSeries || {}).day || []).length >= 8;
  });
}

function getWeightedSectorThemeMatches(name) {
  const text = String(name || "");
  return WEIGHTED_SECTOR_THEME_RULES.filter((theme) => theme.match.test(text));
}

function calculateReturnPct(points) {
  if (!Array.isArray(points) || points.length < 2) return null;
  const first = points[0];
  const latest = points.at(-1);
  if (!first || !latest || !Number.isFinite(first.close) || !Number.isFinite(latest.close) || first.close === 0) return null;
  return ((latest.close - first.close) / first.close) * 100;
}


function averageFinite(values, fallback = null) {
  const clean = (values || []).filter(Number.isFinite);
  if (!clean.length) return fallback;
  return clean.reduce((sum, value) => sum + value, 0) / clean.length;
}

function percentileScore(value, values, higherIsBetter = true) {
  const clean = (values || []).filter(Number.isFinite).sort((left, right) => left - right);
  if (!Number.isFinite(value) || !clean.length) return 50;
  const lowerCount = clean.filter((item) => item < value).length;
  const equalCount = clean.filter((item) => item === value).length || 1;
  const percentile = ((lowerCount + equalCount * 0.5) / clean.length) * 100;
  return clampScore(higherIsBetter ? percentile : 100 - percentile);
}

function scoreRangePosition(position, relative5) {
  if (!Number.isFinite(position)) return 50;
  if (position >= 42 && position <= 78) return 82;
  if (position > 78 && position <= 90) return 68;
  if (position > 90) return Number.isFinite(relative5) && relative5 > 0 ? 54 : 38;
  if (position >= 25 && Number.isFinite(relative5) && relative5 > 0) return 72;
  if (position < 25 && Number.isFinite(relative5) && relative5 > 0) return 60;
  return 42;
}

function buildWeightedSectorTrendModels(weightedIndex) {
  const benchmarkSeries = ((weightedIndex?.comparisonSeries || {}).day || [])
    .map((item) => ({
      date: item.date,
      close: parseMarketNumber(item.close),
    }))
    .filter((item) => item.date && Number.isFinite(item.close));
  const benchmarkByDate = new Map(benchmarkSeries.map((item) => [item.date, item]));
  const benchmarkDailyPct = parseMarketNumber(weightedIndex?.pct);

  const rawModels = getWeightedComponentSectorCandidates(weightedIndex)
    .map((sector) => {
      const aligned = (((sector.comparisonSeries || {}).day || [])
        .map((item) => {
          const benchmark = benchmarkByDate.get(item.date);
          const close = parseMarketNumber(item.close);
          const benchmarkClose = parseMarketNumber(benchmark?.close);
          if (!item.date || !Number.isFinite(close) || !Number.isFinite(benchmarkClose)) return null;
          return {
            date: item.date,
            close,
            benchmarkClose,
            high: parseMarketNumber(item.high) ?? close,
            low: parseMarketNumber(item.low) ?? close,
            volume: parseMarketNumber(item.volumeValue ?? item.volume),
          };
        })
        .filter(Boolean));
      if (aligned.length < 8) return null;

      const analysisWindow = aligned.slice(-Math.min(20, aligned.length));
      const recentWindow = aligned.slice(-Math.min(6, aligned.length));
      const mediumWindow = aligned.slice(-Math.min(11, aligned.length));
      const benchmarkAnalysis = analysisWindow.map((item) => ({ close: item.benchmarkClose }));
      const benchmarkRecent = recentWindow.map((item) => ({ close: item.benchmarkClose }));
      const benchmarkMedium = mediumWindow.map((item) => ({ close: item.benchmarkClose }));
      const sectorReturn20 = calculateReturnPct(analysisWindow);
      const benchmarkReturn20 = calculateReturnPct(benchmarkAnalysis);
      const sectorReturn5 = calculateReturnPct(recentWindow);
      const benchmarkReturn5 = calculateReturnPct(benchmarkRecent);
      const sectorReturn10 = calculateReturnPct(mediumWindow);
      const benchmarkReturn10 = calculateReturnPct(benchmarkMedium);
      const relative20 = Number.isFinite(sectorReturn20) && Number.isFinite(benchmarkReturn20)
        ? sectorReturn20 - benchmarkReturn20
        : null;
      const relative5 = Number.isFinite(sectorReturn5) && Number.isFinite(benchmarkReturn5)
        ? sectorReturn5 - benchmarkReturn5
        : null;
      const relative10 = Number.isFinite(sectorReturn10) && Number.isFinite(benchmarkReturn10)
        ? sectorReturn10 - benchmarkReturn10
        : null;
      const closes = aligned.map((item) => item.close);
      const latest = aligned.at(-1);
      const previous = aligned.at(-2);
      const latestClose = latest?.close;
      const ma5Series = movingAverage(closes, 5);
      const ma20Series = movingAverage(closes, 20);
      const ma5 = ma5Series.at(-1);
      const ma20 = ma20Series.at(-1);
      const ma5Prev = ma5Series.at(-2);
      const ma20Prev = ma20Series.at(-2);
      const ma5Slope = Number.isFinite(ma5) && Number.isFinite(ma5Prev) && ma5Prev ? ((ma5 - ma5Prev) / ma5Prev) * 100 : null;
      const ma20Slope = Number.isFinite(ma20) && Number.isFinite(ma20Prev) && ma20Prev ? ((ma20 - ma20Prev) / ma20Prev) * 100 : null;
      const dailyPct = parseMarketNumber(sector.pct);
      const fallbackDailyPct = previous?.close ? ((latestClose - previous.close) / previous.close) * 100 : null;
      const effectiveDailyPct = Number.isFinite(dailyPct) ? dailyPct : fallbackDailyPct;
      const dailyRelative = Number.isFinite(effectiveDailyPct) && Number.isFinite(benchmarkDailyPct)
        ? effectiveDailyPct - benchmarkDailyPct
        : null;
      const highs = analysisWindow.map((item) => item.high).filter(Number.isFinite);
      const lows = analysisWindow.map((item) => item.low).filter(Number.isFinite);
      const recentHigh = highs.length ? Math.max(...highs) : null;
      const recentLow = lows.length ? Math.min(...lows) : null;
      const rangePosition = Number.isFinite(recentHigh) && Number.isFinite(recentLow) && recentHigh !== recentLow
        ? ((latestClose - recentLow) / (recentHigh - recentLow)) * 100
        : null;
      const drawdown = Number.isFinite(recentHigh) && recentHigh ? ((latestClose - recentHigh) / recentHigh) * 100 : null;
      const volumeSamples = analysisWindow.slice(0, -1).map((item) => item.volume).filter(Number.isFinite);
      const latestVolume = parseMarketNumber(latest?.volume ?? sector.volume);
      const avgVolume = volumeSamples.length
        ? volumeSamples.reduce((sum, value) => sum + value, 0) / volumeSamples.length
        : null;
      const volumeRatio = Number.isFinite(latestVolume) && Number.isFinite(avgVolume) && avgVolume > 0
        ? (latestVolume / avgVolume) * 100
        : null;

      return {
        sector,
        name: sector.name || sector.sourceName || "--",
        themes: getWeightedSectorThemeMatches(sector.name || sector.sourceName || ""),
        latestDate: latest?.date || sector.time || data?.snapshotDate || "--",
        dataPoints: aligned.length,
        relative20,
        relative10,
        relative5,
        dailyRelative,
        sectorReturn20,
        benchmarkReturn20,
        sectorReturn10,
        benchmarkReturn10,
        sectorReturn5,
        benchmarkReturn5,
        effectiveDailyPct,
        latestClose,
        ma5,
        ma20,
        ma5Slope,
        ma20Slope,
        volumeRatio,
        rangePosition,
        drawdown,
        value: sector.value || formatGlobalValue(latestClose, 2),
        pct: sector.pct || formatSignedPercentValue(effectiveDailyPct),
      };
    })
    .filter(Boolean);
  const relative20Values = rawModels.map((item) => item.relative20);
  const relative10Values = rawModels.map((item) => item.relative10);
  const relative5Values = rawModels.map((item) => item.relative5);
  const dailyRelativeValues = rawModels.map((item) => item.dailyRelative);
  const drawdownValues = rawModels.map((item) => item.drawdown);
  const volumeValues = rawModels.map((item) => item.volumeRatio);

  return rawModels
    .map((model) => {
      const relativeStrengthScore = averageFinite([
        percentileScore(model.relative20, relative20Values),
        percentileScore(model.relative10, relative10Values),
        percentileScore(model.relative5, relative5Values),
        percentileScore(model.dailyRelative, dailyRelativeValues),
      ], 50);
      const trendScore = averageFinite([
        Number.isFinite(model.latestClose) && Number.isFinite(model.ma5) ? (model.latestClose >= model.ma5 ? 70 : 35) : null,
        Number.isFinite(model.latestClose) && Number.isFinite(model.ma20) ? (model.latestClose >= model.ma20 ? 76 : 30) : null,
        Number.isFinite(model.ma5) && Number.isFinite(model.ma20) ? (model.ma5 >= model.ma20 ? 70 : 34) : null,
        Number.isFinite(model.ma5Slope) ? (model.ma5Slope > 0 ? 66 : 38) : null,
        Number.isFinite(model.ma20Slope) ? (model.ma20Slope > 0 ? 62 : 42) : null,
        percentileScore(model.drawdown, drawdownValues),
      ], 50);
      const volumeBaseScore = Number.isFinite(model.volumeRatio)
        ? clampScore(50 + ((model.volumeRatio - 100) * (Number.isFinite(model.relative5) && model.relative5 >= 0 ? 0.32 : -0.18)))
        : null;
      const volumeScore = averageFinite([
        volumeBaseScore,
        percentileScore(model.volumeRatio, volumeValues),
      ], 50);
      const rotationScore = averageFinite([
        scoreRangePosition(model.rangePosition, model.relative5),
        Number.isFinite(model.relative5) && Number.isFinite(model.relative20)
          ? clampScore(50 + ((model.relative5 - model.relative20) * 2.8))
          : null,
        Number.isFinite(model.relative10) && Number.isFinite(model.relative20)
          ? clampScore(50 + ((model.relative10 - model.relative20) * 2.2))
          : null,
      ], 50);
      let riskPenalty = 0;
      if (Number.isFinite(model.rangePosition) && model.rangePosition > 92) riskPenalty += 6;
      if (Number.isFinite(model.volumeRatio) && model.volumeRatio >= 150 && Number.isFinite(model.relative5) && model.relative5 < 0) riskPenalty += 12;
      if (Number.isFinite(model.latestClose) && Number.isFinite(model.ma20) && model.latestClose < model.ma20) riskPenalty += 8;
      if (Number.isFinite(model.relative20) && model.relative20 < 0 && Number.isFinite(model.relative5) && model.relative5 < 0) riskPenalty += 8;
      if (Number.isFinite(model.drawdown) && model.drawdown < -8) riskPenalty += 5;
      const score = clampScore(
        relativeStrengthScore * 0.38
        + trendScore * 0.24
        + volumeScore * 0.18
        + rotationScore * 0.12
        + (100 - Math.min(riskPenalty * 4, 45)) * 0.08
        - riskPenalty,
      );
      const action = score >= 70 && relativeStrengthScore >= 62 && trendScore >= 58
        ? "主攻"
        : score >= 55 && rotationScore >= 60 && Number.isFinite(model.relative5) && model.relative5 > 0
          ? "補漲"
          : score <= 45 || riskPenalty >= 16
            ? "避開"
            : "觀察";
      const tone = action === "主攻" ? "leader" : action === "補漲" ? "rotation" : action === "避開" ? "risk" : "watch";
      const confidence = model.dataPoints >= 20 && Number.isFinite(model.volumeRatio) && Number.isFinite(model.ma20)
        ? "高"
        : model.dataPoints >= 14
          ? "中"
          : "低";
      const thesis = action === "主攻"
        ? "相對強弱、均線與量能同向，屬於目前加權指數成分中較有主線條件的族群。"
        : action === "補漲"
          ? "短線相對強度正在改善，但中期領先尚未完全確認，較適合列為輪動觀察。"
          : action === "避開"
            ? "相對大盤落後或量價結構轉弱，短線反彈前仍應先控管風險。"
            : "訊號尚未形成一致方向，等待相對強弱或量能進一步確認。";
      const reasons = [
        `相對強弱分數 ${Math.round(relativeStrengthScore)}/100：20日 ${formatSignedPercentValue(model.relative20)}、5日 ${formatSignedPercentValue(model.relative5)}`,
        `趨勢品質 ${Math.round(trendScore)}/100：${Number.isFinite(model.ma20) && Number.isFinite(model.latestClose) ? `收盤${model.latestClose >= model.ma20 ? "站上" : "跌破"}MA20` : "MA20資料累積中"}`,
        `量能確認 ${Math.round(volumeScore)}/100：${Number.isFinite(model.volumeRatio) ? `近20日均量 ${model.volumeRatio.toFixed(0)}%` : "量能資料不足"}`,
        `輪動位置 ${Math.round(rotationScore)}/100：${Number.isFinite(model.rangePosition) ? `位於20日區間 ${model.rangePosition.toFixed(0)}%` : "區間資料不足"}`,
      ];
      const themeLabel = model.themes?.[0]?.label || "一般類股";
      return {
        ...model,
        score,
        action,
        tone,
        confidence,
        themeLabel,
        thesis,
        riskPenalty,
        subScores: {
          relativeStrength: relativeStrengthScore,
          trend: trendScore,
          volume: volumeScore,
          rotation: rotationScore,
        },
        reasons,
      };
    })
    .sort((left, right) => right.score - left.score);
}

function buildWeightedSectorThemeContext(models) {
  const themes = WEIGHTED_SECTOR_THEME_RULES.map((theme) => {
    const members = models.filter((model) => (model.themes || []).some((item) => item.id === theme.id));
    if (!members.length) return null;
    const avgScore = averageFinite(members.map((item) => item.score), 0);
    const avgRelative20 = averageFinite(members.map((item) => item.relative20), null);
    const avgRelative5 = averageFinite(members.map((item) => item.relative5), null);
    const positive20 = members.filter((item) => Number.isFinite(item.relative20) && item.relative20 > 0).length;
    const positive5 = members.filter((item) => Number.isFinite(item.relative5) && item.relative5 > 0).length;
    const trendConfirmed = members.filter((item) => item.subScores?.trend >= 60).length;
    const leadershipScore = clampScore(
      (avgScore * 0.48)
      + ((positive20 / members.length) * 22)
      + ((positive5 / members.length) * 18)
      + ((trendConfirmed / members.length) * 12),
    );
    const status = leadershipScore >= 74 && positive20 >= Math.ceil(members.length * 0.5)
      ? "主軸確認"
      : leadershipScore >= 62
        ? "題材擴散"
        : positive5 >= Math.ceil(members.length * 0.45)
          ? "短線轉強"
          : "仍待確認";
    const leaders = [...members]
      .sort((left, right) => right.score - left.score)
      .slice(0, 4);
    return {
      ...theme,
      members,
      leaders,
      avgScore,
      avgRelative20,
      avgRelative5,
      positive20,
      positive5,
      trendConfirmed,
      leadershipScore,
      status,
    };
  }).filter(Boolean);
  return themes.sort((left, right) => right.leadershipScore - left.leadershipScore);
}

function buildWeightedSectorMarketContext(models, weightedIndex) {
  const total = models.length || 1;
  const benchmarkReturn20 = models.find((item) => Number.isFinite(item.benchmarkReturn20))?.benchmarkReturn20 ?? null;
  const benchmarkReturn5 = models.find((item) => Number.isFinite(item.benchmarkReturn5))?.benchmarkReturn5 ?? null;
  const relative20Leaders = models.filter((item) => Number.isFinite(item.relative20) && item.relative20 > 0).length;
  const relative5Leaders = models.filter((item) => Number.isFinite(item.relative5) && item.relative5 > 0).length;
  const confirmedTrends = models.filter((item) => item.subScores?.trend >= 60).length;
  const leaderRatio = relative20Leaders / total;
  const shortRatio = relative5Leaders / total;
  const trendRatio = confirmedTrends / total;
  const benchmarkPct = parseMarketNumber(weightedIndex?.pct);
  const regime = Number.isFinite(benchmarkReturn20) && benchmarkReturn20 > 0 && leaderRatio >= 0.5
    ? "多頭輪動擴散"
    : Number.isFinite(benchmarkReturn20) && benchmarkReturn20 > 0
      ? "指數偏強但族群分歧"
      : shortRatio >= 0.45
        ? "短線修復輪動"
        : "防守整理";
  const summary = `${regime}：近20日有 ${relative20Leaders}/${total} 個類股領先大盤，近5日 ${relative5Leaders}/${total} 個類股短線轉強，趨勢確認 ${confirmedTrends}/${total} 個。`;
  return {
    regime,
    summary,
    benchmarkPct,
    benchmarkReturn20,
    benchmarkReturn5,
    leaderRatio,
    shortRatio,
    trendRatio,
    total,
  };
}

function renderWeightedSectorTrendFocus(title, subtitle, model, tone) {
  if (!model) {
    return `
      <article class="weighted-sector-trend-focus-card is-${tone}">
        <span>${escapeHtml(title)}</span>
        <strong>資料不足</strong>
        <small>${escapeHtml(subtitle)}</small>
        <p>目前成分類股歷史資料不足，暫不產生此類推薦。</p>
      </article>
    `;
  }
  return `
    <article class="weighted-sector-trend-focus-card is-${tone}">
      <span>${escapeHtml(title)}</span>
      <div class="weighted-sector-focus-title">
        <strong>${escapeHtml(model.name)}</strong>
        <b>${model.score}/100</b>
      </div>
      <small>${escapeHtml(subtitle)} · ${escapeHtml(model.pct)} · 信心 ${escapeHtml(model.confidence)}</small>
      <p>${escapeHtml(model.thesis)}</p>
      <ul class="weighted-sector-thesis-list">
        ${model.reasons.slice(0, 3).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}
      </ul>
    </article>
  `;
}

function renderWeightedSectorThemeContext(themes) {
  if (!themes.length) return "";
  const topTheme = themes[0];
  const aiTheme = themes.find((theme) => theme.id === "ai-server");
  const highlightedTheme = aiTheme && aiTheme.leadershipScore >= Math.max(56, (topTheme?.leadershipScore || 0) - 10)
    ? aiTheme
    : topTheme;
  const leaderNames = highlightedTheme.leaders.map((item) => `${item.name} ${item.pct || "--"}`).join("、");
  const aiFollowUp = aiTheme && highlightedTheme.id !== "ai-server"
    ? `AI 伺服器鏈追蹤：${aiTheme.status}，20日領先 ${aiTheme.positive20}/${aiTheme.members.length}，5日相對 ${formatSignedPercentValue(aiTheme.avgRelative5)}；領先觀察 ${aiTheme.leaders.map((item) => `${item.name} ${item.pct || "--"}`).join("、") || "--"}。`
    : "";
  return `
    <div class="weighted-sector-theme-context">
      <div>
        <span>主題脈絡</span>
        <strong>${escapeHtml(highlightedTheme.label)} · ${escapeHtml(highlightedTheme.status)}</strong>
        <p>${escapeHtml(highlightedTheme.description)} 目前領先觀察：${escapeHtml(leaderNames || "--")}。</p>
        ${aiFollowUp ? `<small class="weighted-sector-theme-secondary">${escapeHtml(aiFollowUp)}</small>` : ""}
      </div>
      <div class="weighted-sector-theme-stats">
        <span><b>${highlightedTheme.leadershipScore}/100</b><small>主題分數</small></span>
        <span><b>${highlightedTheme.positive20}/${highlightedTheme.members.length}</b><small>20日領先</small></span>
        <span><b>${formatSignedPercentValue(highlightedTheme.avgRelative5)}</b><small>5日相對</small></span>
      </div>
    </div>
  `;
}

function renderWeightedSectorTrendRecommendationCard(weightedIndex) {
  const models = buildWeightedSectorTrendModels(weightedIndex);
  if (!models.length) {
    return `
      <article class="analysis-card weighted-index-note-card-inline weighted-sector-trend-card">
        <div class="card-title-row"><h4>加權成分類股趨勢推薦</h4><span class="chip chip-blue">研究分析</span></div>
        <p class="card-copy">目前證交所類股歷史資料不足，暫時無法建立相對大盤的趨勢推薦。</p>
      </article>
    `;
  }

  const leader = models.find((item) => item.action === "主攻");
  const leaderFocus = leader || models[0];
  const rotation = models.find((item) => item.action === "補漲" && item.name !== leaderFocus?.name);
  const rotationFocus = rotation
    || models.find((item) => item.name !== leaderFocus?.name && item.score >= 52);
  const weakest = [...models].reverse().find((item) => item.name !== leaderFocus?.name && item.name !== rotationFocus?.name) || models.at(-1);
  const themes = buildWeightedSectorThemeContext(models);
  const topRows = models.slice(0, 6);
  const context = buildWeightedSectorMarketContext(models, weightedIndex);
  const benchmarkPct = parseMarketNumber(weightedIndex?.pct);
  const marketText = Number.isFinite(benchmarkPct)
    ? `大盤今日 ${formatSignedPercentValue(benchmarkPct)}。${context.summary} 本卡以相對強弱、趨勢品質、量能確認、輪動位置與風險扣分建立研究排序。`
    : `${context.summary} 本卡以相對強弱、趨勢品質、量能確認、輪動位置與風險扣分建立研究排序。`;

  return `
    <article class="analysis-card weighted-index-note-card-inline weighted-sector-trend-card">
      <div class="card-title-row">
        <h4>加權成分類股趨勢推薦</h4>
        <span class="chip chip-gold">${escapeHtml(context.regime)}</span>
      </div>
      <p class="weighted-sector-trend-summary">${escapeHtml(marketText)}</p>
      ${renderWeightedSectorThemeContext(themes)}
      <div class="weighted-sector-market-context">
        <div><span>大盤20日</span><strong class="${Number.isFinite(context.benchmarkReturn20) ? context.benchmarkReturn20 >= 0 ? "up" : "down" : "flat"}">${formatSignedPercentValue(context.benchmarkReturn20)}</strong></div>
        <div><span>20日領先比</span><strong>${Math.round(context.leaderRatio * 100)}%</strong><small>${models.filter((item) => Number.isFinite(item.relative20) && item.relative20 > 0).length}/${context.total} 類股</small></div>
        <div><span>5日轉強比</span><strong>${Math.round(context.shortRatio * 100)}%</strong><small>${models.filter((item) => Number.isFinite(item.relative5) && item.relative5 > 0).length}/${context.total} 類股</small></div>
        <div><span>模型基準</span><strong>多因子</strong><small>強弱38 / 趨勢24 / 量能18 / 輪動12 / 風險扣分</small></div>
      </div>
      <div class="weighted-sector-trend-focus">
        ${renderWeightedSectorTrendFocus(leader ? "主攻強勢" : "相對強勢候選", leader ? "相對大盤領先且趨勢確認" : "分數最高，但尚未完全達到主攻門檻", leaderFocus, "leader")}
        ${renderWeightedSectorTrendFocus(rotation ? "補漲觀察" : "輪動候選", rotation ? "短線轉強但位置未過熱" : "尚未達補漲門檻，列為次順位追蹤", rotationFocus, "rotation")}
        ${renderWeightedSectorTrendFocus(weakest?.action === "避開" ? "弱勢避開" : "相對弱勢", weakest?.action === "避開" ? "落後大盤或量價背離" : "排序較後，等待轉強證據", weakest, "risk")}
      </div>
      <div class="weighted-sector-trend-table">
        <div class="weighted-sector-trend-row is-head">
          <span>排序 / 結論</span><span>總分</span><span>相對強弱</span><span>趨勢</span><span>量能</span><span>風險</span>
        </div>
        ${topRows.map((item, index) => `
          <div class="weighted-sector-trend-row">
            <span><b>${index + 1}. ${escapeHtml(item.name)}</b><small>${escapeHtml(item.action)} · ${escapeHtml(item.themeLabel)} · 信心 ${escapeHtml(item.confidence)} · ${escapeHtml(item.latestDate)}</small></span>
            <strong>${item.score}/100</strong>
            <strong class="${Number.isFinite(item.relative20) ? item.relative20 >= 0 ? "up" : "down" : "flat"}">${Math.round(item.subScores.relativeStrength)}</strong>
            <strong>${Math.round(item.subScores.trend)}</strong>
            <strong>${Number.isFinite(item.volumeRatio) ? `${item.volumeRatio.toFixed(0)}%` : "--"}</strong>
            <strong>${item.riskPenalty ? `-${item.riskPenalty}` : "低"}</strong>
          </div>
        `).join("")}
      </div>
    </article>
  `;
}

function getVixRiskTemperature(value) {
  if (!Number.isFinite(value)) return null;
  return Math.max(0, Math.min(100, Math.round(((value - 10) / 35) * 100)));
}

function getVixRiskToneClass(change) {
  if (!Number.isFinite(change)) return "flat";
  return change > 0 ? "down" : change < 0 ? "up" : "flat";
}

function renderVixTemperatureMeter(score, band, volatility) {
  const safeScore = Number.isFinite(score) ? score : null;
  const width = safeScore === null ? 0 : Math.max(0, Math.min(100, safeScore));
  const value = escapeHtml(volatility?.value || "--");
  const pct = escapeHtml(volatility?.pct || "--");
  return `
    <div class="vix-temperature-meter is-${escapeHtml(band.tone || "neutral")}">
      <div class="vix-temperature-head">
        <span>風險溫度</span>
        <strong>${safeScore === null ? "--" : safeScore}/100</strong>
      </div>
      <div class="vix-temperature-track" aria-hidden="true"><i style="width:${width}%"></i></div>
      <small>VIX ${value} / ${pct}</small>
    </div>
  `;
}

function renderSectorVixSparkline(volatility) {
  const series = (volatility?.series || [])
    .map((item) => ({
      date: item.date,
      value: parseMarketNumber(item.value),
    }))
    .filter((item) => item.date && Number.isFinite(item.value));
  if (series.length < 2) {
    return '<div class="vix-sparkline-empty">VIX 歷史資料不足。</div>';
  }
  const width = 300;
  const height = 150;
  const pad = { top: 16, right: 16, bottom: 22, left: 34 };
  const values = series.map((item) => item.value);
  const minValue = Math.max(0, Math.min(...values, 15) - 1.5);
  const maxValue = Math.max(...values, 20) + 1.5;
  const range = maxValue - minValue || 1;
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const xAt = (index) => pad.left + (index / Math.max(series.length - 1, 1)) * plotWidth;
  const yAt = (value) => pad.top + ((maxValue - value) / range) * plotHeight;
  const points = series.map((item, index) => ({
    x: xAt(index),
    y: yAt(item.value),
    value: item.value,
  }));
  const latest = series.at(-1);
  const previous = series.at(-2);
  const change = latest.value - previous.value;
  const trendClass = change > 0 ? "is-up" : change < 0 ? "is-down" : "";
  const thresholdLines = [15, 20, 30, 40]
    .filter((value) => value >= minValue && value <= maxValue)
    .map((value) => {
      const y = yAt(value);
      return `<line x1="${pad.left}" y1="${y.toFixed(1)}" x2="${width - pad.right}" y2="${y.toFixed(1)}"></line><text x="2" y="${(y + 4).toFixed(1)}">${value}</text>`;
    })
    .join("");
  const firstLabel = escapeHtml(series[0].date.slice(5));
  const latestLabel = escapeHtml(latest.date.slice(5));
  return `
    <div class="vix-sparkline ${trendClass}">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="VIX 近期走勢">
        ${thresholdLines}
        <path d="${buildPath(points)}"></path>
        <circle cx="${points.at(-1).x.toFixed(1)}" cy="${points.at(-1).y.toFixed(1)}" r="4"></circle>
        <text x="${pad.left}" y="${height - 4}">${firstLabel}</text>
        <text x="${width - pad.right - 32}" y="${height - 4}">${latestLabel}</text>
      </svg>
      <div><span>近期走勢</span><strong>${escapeHtml(latest.date)} · ${latest.value.toFixed(2)}</strong></div>
    </div>
  `;
}

function renderVixRuleList(currentValue) {
  const rules = [
    { max: 15, tone: "green", range: "< 15", label: "樂觀偏熱", note: "風險溫度低，但需留意過度樂觀後的波動回補。" },
    { min: 15, max: 20, tone: "green", range: "15 ~ 20", label: "常態穩定", note: "波動預期溫和，市場風險相對健康。" },
    { min: 20, max: 30, tone: "yellow", range: "20 ~ 30", label: "警戒焦慮", note: "波動升溫，需降低追價與槓桿。" },
    { min: 30, max: 40, tone: "red", range: "30 ~ 40", label: "高恐慌", note: "短線震盪劇烈，優先控管部位風險。" },
    { min: 40, tone: "purple", range: "> 40", label: "極端恐慌", note: "可能出現非理性賣壓，也要觀察反彈條件。" },
  ];
  return `
    <div class="vix-rule-list">
      ${rules.map((rule) => {
        const active = Number.isFinite(currentValue)
          && (rule.min === undefined || currentValue >= rule.min)
          && (rule.max === undefined || currentValue < rule.max);
        return `
          <div class="vix-rule-row vix-signal-row is-${rule.tone} ${active ? "is-active" : ""}">
            <strong>${escapeHtml(rule.range)}</strong>
            <span><i class="vix-signal-light"></i>${escapeHtml(rule.label)}</span>
            <small>${escapeHtml(rule.note)}</small>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderVolatilitySwitchCard(weightedIndex = null) {
  const volatility = data?.marketVolatility;
  if (!volatility) {
    return `
      <article class="weighted-vix-card">
        <div class="card-title-row"><h4>風險溫度</h4><span class="chip chip-gold">VIX</span></div>
        <p>等待 VIX live 資料。</p>
      </article>
    `;
  }
  const value = parseMarketNumber(volatility.value);
  const change = parseMarketNumber(volatility.change);
  const band = getVixSentimentBand(value);
  const score = getVixRiskTemperature(value);
  const moveTone = getVixRiskToneClass(change);
  const summary = volatility.summary || band.text || "以 VIX 觀察外部風險情緒。";
  const source = volatility.sourceNote || "Yahoo Finance ^VIX";
  const vixIndexCard = `
    <div class="vix-index-mini-card">
      <div class="vix-index-mini-head">
        <span>${escapeHtml(volatility.label || "VIX 指數")}</span>
        <b class="${moveTone}">${escapeHtml(volatility.change || "--")} / ${escapeHtml(volatility.pct || "--")}</b>
      </div>
      <strong>${escapeHtml(volatility.value || "--")}</strong>
      <p>${escapeHtml(summary)} 台股目前 ${escapeHtml(weightedIndex?.pct || "--")}。</p>
    </div>
  `;
  const meaning = `
    <div class="vix-current-meaning">
      <span>目前區間</span>
      <strong>${escapeHtml(volatility.level || band.label || "風險觀察")} · ${escapeHtml(band.label || "--")}</strong>
      <p>${escapeHtml(summary)}</p>
    </div>
  `;
  const rules = renderVixRuleList(value);
  const sparkline = renderSectorVixSparkline(volatility);
  return `
    <article class="weighted-vix-card">
      <div class="card-title-row"><h4>風險溫度</h4><span class="chip chip-gold">${score === null ? "VIX" : `${score}/100`}</span></div>
      ${vixIndexCard}
      ${renderVixTemperatureMeter(score, band, volatility)}
      <div class="weighted-vix-body">
        ${sparkline}
        ${meaning}
        ${rules}
      </div>
      <small>${escapeHtml(volatility.date || "--")} · ${escapeHtml(source)}</small>
    </article>
  `;
}

function renderWeightedChartZoomControls(visible, total, minimum, panOffset) {
  return `
    <div class="sector-chart-zoom weighted-chart-zoom" aria-label="加權指數圖表縮放控制">
      <button type="button" data-weighted-chart-zoom="in" ${visible <= minimum ? "disabled" : ""}>＋ 放大</button>
      <button type="button" data-weighted-chart-zoom="out" ${visible >= total ? "disabled" : ""}>－ 縮小</button>
      <button type="button" data-weighted-chart-zoom="reset" ${visible >= total ? "disabled" : ""}>重設</button>
      <button type="button" data-weighted-chart-pan="older" ${panOffset >= total - visible ? "disabled" : ""}>← 往前</button>
      <button type="button" data-weighted-chart-pan="newer" ${panOffset <= 0 ? "disabled" : ""}>往後 →</button>
      <span>顯示 ${visible || 0} / ${total || 0} 根</span>
    </div>
  `;
}

function renderWeightedIndexPanel() {
  const container = document.getElementById("weighted-index-panel");
  if (!container) return;
  const weightedIndex = getWeightedIndexSector();
  if (!weightedIndex) {
    container.innerHTML = '<div class="stock-detail-empty">無可用加權指數資料。</div>';
    return;
  }
  const bundle = getVolatilityBundle();
  const orderedInternational = getInternationalIndexItems(bundle);
  loadInternationalIndexesIfNeeded(container);
  const weightedHistory = weightedIndex.comparisonSeries?.day || [];
  const modes = [
    { id: "day", label: "日線", enabled: weightedHistory.length >= 20 },
    { id: "week", label: "週線", enabled: weightedHistory.length >= 20 },
    { id: "month", label: "月線", enabled: weightedHistory.length >= 40 },
    { id: "comparison", label: "指數比對", enabled: orderedInternational.length >= 1 },
  ];
  const requestedMode = container.dataset.weightedMode || "day";
  const normalizedMode = ["vix", "international"].includes(requestedMode) ? "comparison" : requestedMode;
  const activeMode = (modes.find((mode) => mode.id === normalizedMode && mode.enabled) || modes.find((mode) => mode.enabled) || modes[0]).id;
  if (container.dataset.comparisonInitialized !== "1") {
    container.dataset.internationalSelection = "taiex";
    container.dataset.comparisonInitialized = "1";
  }
  const selectedSet = new Set((container.dataset.internationalSelection || "").split(",").filter(Boolean));
  const activeInternational = orderedInternational.filter((item) => selectedSet.has(item.key));
  const taiexItem = {
    key: "taiex",
    name: "台灣加權指數",
    value: weightedIndex.value,
    open: weightedIndex.open,
    previousClose: weightedIndex.previousClose,
    high: weightedIndex.high,
    low: weightedIndex.low,
    pct: weightedIndex.pct,
    volume: weightedIndex.volume,
    series: weightedHistory.map((item) => ({
      date: item.date,
      value: item.close,
      open: item.open,
      high: item.high,
      low: item.low,
      volume: item.volume,
    })),
  };
  const activeInternationalItems = activeInternational
    .map((item) => item.key === "vix" ? { ...item, name: "VIX 指數" } : item);
  const comparisonItems = activeMode === "comparison"
    ? [...(selectedSet.has("taiex") ? [taiexItem] : []), ...activeInternationalItems]
    : [];
  const weightedTrendModel = ["day", "week", "month"].includes(activeMode)
    ? buildSectorTrendModel(weightedIndex, activeMode)
    : [];
  const totalPoints = ["day", "week", "month"].includes(activeMode)
    ? weightedTrendModel.length
    : alignIndexSeries(comparisonItems).length;
  const minimumVisible = Math.min(activeMode === "comparison" ? 20 : 40, Math.max(totalPoints, 2));
  const comparisonStateKey = comparisonItems.map((item) => item.key).join("_").replace(/[^A-Za-z0-9_]/g, "_");
  const zoomStateKey = `weightedZoom_${activeMode}_${comparisonStateKey}`;
  const panStateKey = `weightedPan_${activeMode}_${comparisonStateKey}`;
  const savedVisible = Number(container.dataset[zoomStateKey]);
  const visibleCount = totalPoints > 0
    ? Math.max(minimumVisible, Math.min(Number.isFinite(savedVisible) && savedVisible > 1 ? savedVisible : totalPoints, totalPoints))
    : 0;
  const panOffset = Math.max(0, Math.min(Number(container.dataset[panStateKey]) || 0, Math.max(totalPoints - visibleCount, 0)));
  const chart = activeMode === "comparison"
    ? renderFreeIndexComparisonChart(comparisonItems, comparisonItems.length === 1 && isVixComparisonItem(comparisonItems[0]) ? "VIX 市場恐慌情緒走勢" : "全球指數自由比對", { visibleCount, panOffset })
      : renderSectorTrendChart(weightedIndex, activeMode, { size: "large", visibleCount, panOffset });
  const technical = weightedIndex.technicalAnalysis || {};
  const singleComparisonMode = activeMode === "comparison" && comparisonItems.length === 1;
  const singleVixComparisonMode = singleComparisonMode && isVixComparisonItem(comparisonItems[0]);
  const quoteMetricsMode = activeMode !== "comparison" || singleComparisonMode;
  const metrics = activeMode === "comparison"
    ? buildInternationalSelectionMetrics(chart, comparisonItems)
      : buildSingleIndexQuoteMetrics(weightedIndex);
  const bottomAnalysisHtml = activeMode === "comparison"
    ? comparisonItems.length > 1
      ? renderIndexComparisonInsight(chart, activeMode, comparisonItems)
      : comparisonItems.length === 1
        ? renderSingleIndexComparisonInsight(comparisonItems[0], chart)
        : '<article class="analysis-card weighted-index-note-card-inline"><div class="card-title-row"><h4>尚未選擇指數</h4><span class="chip chip-gold">等待選擇</span></div><p class="card-copy">請從上方選擇台灣加權指數、VIX 或任一國際指數以顯示走勢資料。</p></article>'
      : `${renderWeightedTechnicalInsightCard(weightedIndex, activeMode, weightedTrendModel)}${renderWeightedSectorTrendRecommendationCard(weightedIndex)}`;
  const weightedPanelTitle = activeMode === "comparison"
    ? singleVixComparisonMode
      ? "VIX 市場恐慌情緒"
      : "全球指數自由比對"
    : "台股加權指數技術走勢";
  container.dataset.weightedMode = activeMode;
  container.innerHTML = `
    <div class="class-board-head weighted-index-head">
      <div><p class="eyebrow">台股加權指數技術趨勢</p><h3>${weightedPanelTitle}</h3></div>
      <span class="chip ${weightedIndex.tone === "up" ? "chip-green" : weightedIndex.tone === "down" ? "chip-red" : "chip-blue"}">${technical.signal || "趨勢觀察"}</span>
    </div>
    <div class="sector-sync-layout sector-sync-layout-yahoo weighted-index-layout">
      <div class="sector-sync-main">
        <div class="weighted-index-chart-card">
          <div class="sector-sync-toolbar weighted-index-toolbar">
            <div class="sector-sync-picker"><button class="sector-sync-chip is-active" type="button">${weightedIndex.name} / 台股加權指數</button></div>
            <div class="sector-sync-mode-switcher">${modes.map((mode) => `<button class="sector-sync-mode ${mode.id === activeMode ? "is-active" : ""} ${mode.enabled ? "" : "is-disabled"}" type="button" data-weighted-mode="${mode.id}" ${mode.enabled ? "" : "disabled"}>${mode.label}</button>`).join("")}</div>
          </div>
          ${activeMode === "comparison" ? `<div class="international-index-picker"><span>台股 / VIX / 國際指數複選</span><div class="sector-sync-picker"><button class="sector-sync-chip ${selectedSet.has("taiex") ? "is-active" : ""}" type="button" data-international-key="taiex">台灣加權指數</button>${orderedInternational.map((item) => `<button class="sector-sync-chip ${selectedSet.has(item.key) ? "is-active" : ""}" type="button" data-international-key="${item.key}">${item.key === "vix" ? "VIX 指數" : item.name}</button>`).join("")}</div></div>` : ""}
          ${renderWeightedChartZoomControls(chart.visiblePoints || visibleCount, chart.totalPoints || totalPoints, minimumVisible, panOffset)}
          ${chart.html}
          <div class="sector-yahoo-metrics weighted-index-inline-metrics ${quoteMetricsMode ? "is-single-index" : ""} ${singleVixComparisonMode ? "is-vix-sentiment" : ""}">${metrics.map((metric) => `<div class="mini-item ${metric.key ? `metric-${metric.key}` : ""}"><span>${metric.label}</span><strong class="${metric.toneClass || ""}">${metric.value}</strong></div>`).join("")}</div>
        </div>
      </div>
      <aside class="sector-sync-side">${renderVolatilitySwitchCard(weightedIndex)}</aside>
      <div class="weighted-index-analysis-stack is-wide">${bottomAnalysisHtml}</div>
    </div>
  `;
  container.querySelectorAll("[data-weighted-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      container.dataset.weightedMode = button.dataset.weightedMode || "day";
      renderWeightedIndexPanel();
    });
  });
  container.querySelectorAll("[data-international-key]").forEach((button) => {
    button.addEventListener("click", () => {
      const current = new Set((container.dataset.internationalSelection || "").split(",").filter(Boolean));
      const key = button.dataset.internationalKey;
      if (current.has(key)) current.delete(key);
      else current.add(key);
      container.dataset.internationalSelection = Array.from(current).join(",");
      renderWeightedIndexPanel();
    });
  });
  const updateWeightedZoom = (direction) => {
    if (!totalPoints) return;
    const current = chart.visiblePoints || visibleCount;
    let next = current;
    if (direction === "in") next = Math.max(minimumVisible, Math.floor(current * 0.65));
    if (direction === "out") next = Math.min(totalPoints, Math.ceil(current / 0.65));
    if (direction === "reset") next = totalPoints;
    if (next === current) return;
    container.dataset[zoomStateKey] = String(next);
    container.dataset[panStateKey] = "0";
    renderWeightedIndexPanel();
  };
  const updateWeightedPan = (direction) => {
    if (!totalPoints) return;
    const maxOffset = Math.max(totalPoints - visibleCount, 0);
    const step = Math.max(1, Math.round(visibleCount * 0.35));
    const next = direction === "older"
      ? Math.min(maxOffset, panOffset + step)
      : Math.max(0, panOffset - step);
    if (next === panOffset) return;
    container.dataset[panStateKey] = String(next);
    renderWeightedIndexPanel();
  };
  container.querySelectorAll("[data-weighted-chart-zoom]").forEach((button) => {
    button.addEventListener("click", () => updateWeightedZoom(button.dataset.weightedChartZoom));
  });
  container.querySelectorAll("[data-weighted-chart-pan]").forEach((button) => {
    button.addEventListener("click", () => updateWeightedPan(button.dataset.weightedChartPan));
  });
  bindWeightedPanelHover(container, chart);
  const frame = container.querySelector(".sector-chart-frame");
  if (frame) {
    frame.addEventListener("wheel", (event) => {
      event.preventDefault();
      updateWeightedZoom(event.deltaY < 0 ? "in" : "out");
    }, { passive: false });
    bindHorizontalChartPan(frame, updateWeightedPan);
  }
}

function bindWeightedPanelHover(container, chart) {
  const tooltip = container.querySelector(".sector-sync-tooltip");
  const frame = container.querySelector(".sector-chart-frame");
  const guide = container.querySelector(".sector-hover-guide");
  const dot = container.querySelector(".sector-hover-dot-sector");
  if (!tooltip || !frame || !guide || !dot || !chart.points?.length) return;
  const hide = () => {
    tooltip.hidden = true;
    guide.classList.remove("is-visible");
    dot.classList.remove("is-visible");
  };
  container.querySelectorAll("[data-sync-index]").forEach((zone) => {
    const show = (event) => {
      const point = chart.points[Number(zone.dataset.syncIndex)];
      if (!point) return;
      tooltip.hidden = false;
      if (zone.dataset.tooltipMode === "free-index") {
        tooltip.innerHTML = `<strong style="display:block;margin-bottom:5px">${escapeHtml(zone.dataset.label || point.label)}</strong>${String(zone.dataset.payload || "").split("|").filter(Boolean).map((entry) => { const [name, value, norm] = entry.split(":"); return `<span>${escapeHtml(name)}：<strong>${escapeHtml(value || "--")}</strong>（Base ${escapeHtml(norm || "--")}）</span>`; }).join("")}`;
      } else {
        const rawClose = parseMarketNumber(zone.dataset.sectorClose);
        const rawOpen = parseMarketNumber(zone.dataset.sectorOpen);
        const chgPct = Number.isFinite(rawClose) && Number.isFinite(rawOpen) && rawOpen > 0
          ? ((rawClose - rawOpen) / rawOpen * 100)
          : null;
        tooltip.innerHTML = `
          <strong style="display:block;margin-bottom:5px">${escapeHtml(point.label)}</strong>
          <span>開　盤：<strong>${escapeHtml(zone.dataset.sectorOpen || "--")}</strong></span>
          <span>最　高：<strong class="up">${escapeHtml(zone.dataset.sectorHigh || "--")}</strong></span>
          <span>最　低：<strong class="down">${escapeHtml(zone.dataset.sectorLow || "--")}</strong></span>
          <span>收　盤：<strong>${escapeHtml(zone.dataset.sectorClose || "--")}</strong></span>
          <span>漲　跌：<strong class="${chgPct !== null && chgPct >= 0 ? "up" : "down"}">${chgPct !== null ? `${chgPct >= 0 ? "+" : ""}${chgPct.toFixed(2)}%` : "--"}</strong></span>
          <span>成交量：<strong>${escapeHtml(zone.dataset.volume || "--")}</strong></span>
          <span>成交筆數：<strong>${escapeHtml(zone.dataset.trades || "--")}</strong></span>
          <span>成交金額：<strong>${escapeHtml(zone.dataset.turnover || "--")}</strong></span>
        `;
      }
      const frameRect = frame.getBoundingClientRect();
      const tooltipWidth = tooltip.offsetWidth || 220;
      const cursorLeft = event ? event.clientX - frameRect.left : (point.x / (chart.width || 980)) * frameRect.width;
      const left = Math.max(4, Math.min(cursorLeft + 14, frameRect.width - tooltipWidth - 4));
      const cursorTop = event ? event.clientY - frameRect.top : 8;
      const top = Math.max(8, Math.min(cursorTop + 12, frameRect.height - 160));
      tooltip.style.transform = "none";
      tooltip.style.top = `${top}px`;
      tooltip.style.left = `${left}px`;
      guide.setAttribute("x1", point.x.toFixed(1));
      guide.setAttribute("x2", point.x.toFixed(1));
      dot.setAttribute("cx", point.x.toFixed(1));
      dot.setAttribute("cy", (point.sectorY || 60).toFixed(1));
      guide.classList.add("is-visible");
      dot.classList.add("is-visible");
    };
    zone.addEventListener("mouseenter", show);
    zone.addEventListener("mousemove", show);
    zone.addEventListener("mouseleave", hide);
  });
  frame.addEventListener("mouseleave", hide);
}













function renderVixSentimentRules(activeRange) {
  const rows = [
    { range: "低於 15", mood: "非理性樂觀 / 樂觀", meaning: "牛市或緩漲波段，但留意過度樂觀與賣壓風險。" },
    { range: "15 ~ 20", mood: "常態區間 / 穩定", meaning: "預期變動不大，大盤走勢相對平穩。" },
    { range: "20 ~ 30", mood: "警戒區間 / 焦慮", meaning: "波動加劇，留意修正或多空交戰。" },
    { range: "30 ~ 40", mood: "高恐慌 / 高波動", meaning: "恐慌偏高，短線波動劇烈，避免追價。" },
    { range: "高於 40", mood: "極度恐慌 / 非理性恐慌", meaning: "可能出現非理性拋售，也觀察落底反彈契機。" },
  ];
  return `
    <div class="vix-rule-list" aria-label="VIX 指數區間判讀">
      ${rows.map((row) => `
        <div class="vix-rule-row ${row.range === activeRange ? "is-active" : ""}">
          <strong>${row.range}</strong>
          <span>${row.mood}</span>
          <small>${row.meaning}</small>
        </div>
      `).join("")}
    </div>
  `;
}

function buildMarketInsightNotes() {
  const overview = data.marketOverview?.[0] || {};
  const indexPct = parseMarketNumber(overview.pct) || 0;
  const sectorRows = (data.sectors || []).filter((item) => item.name !== "台灣加權指數");
  const sectorsWithPct = sectorRows
    .map((item) => ({ ...item, pctValue: parseMarketNumber(item.pct) }))
    .filter((item) => Number.isFinite(item.pctValue));
  const topSectors = [...sectorsWithPct]
    .sort((a, b) => b.pctValue - a.pctValue)
    .slice(0, 3);
  const weakSectors = [...sectorsWithPct]
    .sort((a, b) => a.pctValue - b.pctValue)
    .slice(0, 3);
  const advancing = sectorsWithPct.filter((item) => item.pctValue > 0).length;
  const declining = sectorsWithPct.filter((item) => item.pctValue < 0).length;
  const unchanged = sectorsWithPct.filter((item) => item.pctValue === 0).length;
  const breadthTone = advancing > declining
    ? "偏多"
    : declining > advancing
      ? "偏空"
      : "中性";
  const institutionTotal = (data.institutions || []).find((item) => item.name === "合計");
  const institutionNet = parseMarketNumber(institutionTotal?.diffValue ?? institutionTotal?.diff)
    ?? (data.institutionSummary || []).reduce(
      (sum, item) => sum + (parseMarketNumber(item.diffValue) || 0),
      0,
    );
  const investmentTrust = (data.institutions || []).find((item) => item.name === "投信");
  const dealer = (data.institutions || []).find((item) => item.name.includes("自營商") && !item.name.includes("避險"));
  const notes = [];

  notes.push(
    overview.value
      ? `大盤：加權指數收在 ${overview.value} 點，單日漲跌幅 ${overview.pct}，短線方向${indexPct >= 0 ? "偏穩" : "承壓"}。`
      : "大盤：主要指數資料仍在同步，暫以法人與類股資料輔助判斷。",
  );
  notes.push(
    Number.isFinite(institutionNet)
      ? `法人資金：三大法人合計${institutionNet >= 0 ? "買超" : "賣超"} ${formatInstitutionAmount(Math.abs(institutionNet))}，資金面${institutionNet >= 0 ? "偏向支撐" : "仍有調節壓力"}。`
      : "法人資金：合計買賣超資料不足，需等待下一次資料更新。",
  );
  if (investmentTrust) {
    notes.push(`投信動向：${investmentTrust.name} ${investmentTrust.diff}，可觀察中小型及作帳族群是否延續。`);
  }
  if (dealer) {
    notes.push(`自營商動向：${dealer.name} ${dealer.diff}，短線交易資金方向可作為盤中強弱參考。`);
  }
  notes.push(
    sectorsWithPct.length
      ? `市場廣度：類股 ${advancing} 漲、${declining} 跌、${unchanged} 平，整體廣度${breadthTone}。`
      : "市場廣度：類股漲跌家數不足，暫不判斷廣度。",
  );
  if (topSectors.length) {
    notes.push(`強勢族群：${topSectors.map((item) => `${item.name} ${item.pct}`).join("、")}，優先觀察量價是否同步。`);
  }
  if (weakSectors.length) {
    notes.push(`弱勢族群：${weakSectors.map((item) => `${item.name} ${item.pct}`).join("、")}，避免在未止穩前追低攤平。`);
  }
  return notes;
}











function renderSectorsPage() {
  renderSectorPageV2();
}



// ─────────────────────────────────────────────────────────────────────────────



function getPortfolioSimulation() {
  try {
    const value = JSON.parse(localStorage.getItem(PORTFOLIO_SIM_STORAGE_KEY) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function savePortfolioSimulation(value) {
  localStorage.setItem(PORTFOLIO_SIM_STORAGE_KEY, JSON.stringify(value));
}

function formatSimulationMoney(value) {
  if (!Number.isFinite(value)) return "--";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${Math.round(value).toLocaleString("zh-TW")} 元`;
}







function classifyPortfolioAsset(stock) {
  const code = String(stock?.code || "");
  const name = String(stock?.name || "");
  if (/^00/.test(code) || /ETF/i.test(name)) return "ETF";
  return "股票";
}

function estimatePortfolioTransactionCost(position) {
  if (!(position?.shares > 0) || !(position?.entryPrice > 0) || !(position?.currentPrice > 0)) return 0;
  const isEtf = classifyPortfolioAsset(position.stock) === "ETF";
  const buyValue = position.entryPrice * position.shares;
  const sellValue = position.currentPrice * position.shares;
  const buyCost = buyValue * ((PORTFOLIO_COST_MODEL.feePct + PORTFOLIO_COST_MODEL.slippagePct) / 100);
  const sellCost = sellValue * ((PORTFOLIO_COST_MODEL.feePct + (isEtf ? PORTFOLIO_COST_MODEL.etfTaxPct : PORTFOLIO_COST_MODEL.stockTaxPct) + PORTFOLIO_COST_MODEL.slippagePct) / 100);
  return buyCost + sellCost;
}

function buildPortfolioFactorAssessment(positions, totals) {
  const active = positions.filter((item) => item.shares > 0);
  const analyzed = active.map((item) => item.analysis).filter(Boolean);
  const factors = [];
  const actions = [];
  const assetCounts = active.reduce((acc, item) => {
    const kind = classifyPortfolioAsset(item.stock);
    acc[kind] = (acc[kind] || 0) + 1;
    return acc;
  }, {});
  const maxWeight = totals.totalValue > 0
    ? Math.max(...active.map((item) => item.marketValue / totals.totalValue * 100), 0)
    : 0;
  const stopRiskRatio = totals.totalCost > 0 ? (totals.totalRisk / totals.totalCost) * 100 : 0;
  const netReturn = totals.totalCost > 0 ? (totals.netPnl / totals.totalCost) * 100 : 0;
  const pctMoves = active
    .map((item) => Math.abs(parseAnalysisNumber(item.stock.pct) ?? parseAnalysisNumber(item.detail?.pct) ?? 0))
    .filter(Number.isFinite);
  const avgMove = pctMoves.length
    ? pctMoves.reduce((sum, value) => sum + value, 0) / pctMoves.length
    : 0;
  const var95 = totals.totalValue * (avgMove / 100) * 1.65;
  const sharpeLike = avgMove ? netReturn / avgMove : null;
  const vixValue = parseAnalysisNumber(data?.marketVolatility?.value);
  const vixRisk = vixValue !== null && vixValue >= 20;
  const positiveAi = analyzed.filter((item) => item.tone === "positive").length;
  const negativeAi = analyzed.filter((item) => item.tone === "negative").length;
  const neutralAi = Math.max(analyzed.length - positiveAi - negativeAi, 0);
  const averageAiScore = analyzed.length
    ? analyzed.reduce((sum, item) => sum + (Number(item.score) || 0), 0) / analyzed.length
    : 0;
  const backtestItems = analyzed.map((item) => item.backtestLearning).filter(Boolean);
  const backtestHealthy = backtestItems.filter((item) => item.validation?.status === "healthy").length;
  const backtestWatch = backtestItems.filter((item) => ["watch", "recalibrate"].includes(item.validation?.status)).length;
  const backtestRebuild = backtestItems.filter((item) => item.validation?.status === "rebuild").length;
  const backtestAdjustmentSum = backtestItems.reduce((sum, item) => sum + (Number(item.scoreAdjustment) || 0), 0);
  const highConfidence = analyzed.filter((item) => item.confidence === "高" || item.confidence === "中高").length;
  const portfolioTheory = buildPortfolioTheoryAssessment(active, totals);

  if (!active.length) {
    return {
      tone: "neutral",
      label: "等待建立部位",
      summary: "尚未輸入股數，系統先保留資產配置、成本、風控、總體風險與投資組合理論檢查框架。",
      factors: ["請輸入進場價與股數後，系統會估算淨損益、交易成本、集中度、VaR、相關性、分散化與風險貢獻。"],
      actions: ["建立部位前先設定單筆停損與停利條件，並預先規劃單一權重上限。"],
      theoryDetails: portfolioTheory.details,
      theoryActions: portfolioTheory.actions,
      metrics: { maxWeight, stopRiskRatio, var95, sharpeLike, avgMove, ...portfolioTheory.metrics },
      assetMix: assetCounts,
      source: PORTFOLIO_FACTOR_SOURCE,
    };
  }

  factors.push(`資產配置：${Object.entries(assetCounts).map(([key, count]) => `${key} ${count} 檔`).join("、") || "未分類"}`);
  factors.push(`交易成本已估入手續費、證交稅與滑價，淨損益 ${formatSimulationMoney(totals.netPnl)}。`);
  factors.push(`單一商品最高權重 ${maxWeight.toFixed(1)}%，組合停損風險約 ${stopRiskRatio.toFixed(1)}%。`);
  factors.push(`以目前自選股日波動估算 95% 單日 VaR 約 ${Math.round(var95).toLocaleString("zh-TW")} 元。`);
  factors.push(`資產投資組合理論：${portfolioTheory.label}，已納入均值-變異、相關性、分散化比率與風險貢獻。`);
  if (analyzed.length) {
    factors.push(`AI 技術覆蓋：已納入 ${analyzed.length}/${active.length} 檔個股的型態理論、價量指標、市場廣度、心理線、籌碼與回溯校準。`);
    factors.push(`技術方向：偏正向 ${positiveAi} 檔、中性 ${neutralAi} 檔、偏弱 ${negativeAi} 檔，平均 AI 分數 ${averageAiScore.toFixed(1)}。`);
  } else {
    factors.push("AI 技術覆蓋：個股完整資料尚未載入，暫以損益、權重、成本與總體風險先行評估。");
  }
  if (backtestItems.length) {
    factors.push(`回溯測試：通過校準 ${backtestHealthy} 檔、觀察/調參 ${backtestWatch} 檔、需重建 ${backtestRebuild} 檔，組合權重校準合計 ${backtestAdjustmentSum > 0 ? "+" : ""}${backtestAdjustmentSum}。`);
  }
  if (Number.isFinite(sharpeLike)) factors.push(`類 Sharpe 風險效率 ${sharpeLike.toFixed(2)}，用於比較損益是否足以補償波動。`);
  if (vixValue !== null) factors.push(`VIX ${vixValue.toFixed(2)}，${vixRisk ? "總體風險偏高，應降低槓桿與集中度" : "總體波動尚在可控區間"}。`);

  if (maxWeight > 50) actions.push("單一商品超過 50%，建議分散或設定更嚴格停損。");
  else if (maxWeight > 20) actions.push("單一商品超過 20%，需確認是否符合自訂持股上限。");
  else actions.push("單一商品權重未明顯過度集中。");

  if (stopRiskRatio >= 15) actions.push("組合停損風險高於 15%，應檢查是否需要降低股數或收窄停損。");
  else actions.push("組合停損風險低於 15%，風控結構相對可控。");

  if (totals.netPnl < 0 && stopRiskRatio >= 10) actions.push("淨損益為負且停損風險偏高，優先檢查弱勢持股。");
  if (negativeAi > positiveAi) actions.push("組合內偏弱 AI 訊號較多，優先檢查技術結構轉弱或回測失真的持股。");
  else if (positiveAi > negativeAi && backtestRebuild === 0) actions.push("多數持股 AI 訊號偏正向且未見重建警示，可依原停損停利紀律續觀察。");
  if (backtestRebuild > 0) actions.push("存在回測模型需重建的持股，該部位不應提高權重，需等待重新校準。");
  if (highConfidence < Math.ceil(analyzed.length / 2) && analyzed.length) actions.push("高信心個股不足半數，組合不宜因單一強勢股而放大整體曝險。");
  if (vixRisk) actions.push("VIX 進入警戒區時，避免一次建立完整部位，採分批與再平衡。");
  actions.push(...portfolioTheory.actions.slice(0, 3));
  actions.push("目前未納入槓桿、融資、配息稅務與除權息，實際投資需另行校正。");

  const riskScore = (maxWeight > 50 ? 2 : maxWeight > 20 ? 1 : 0)
    + (stopRiskRatio >= 15 ? 2 : stopRiskRatio >= 10 ? 1 : 0)
    + (vixRisk ? 1 : 0)
    + (totals.netPnl < 0 ? 1 : 0)
    + (negativeAi > positiveAi ? 1 : 0)
    + (backtestRebuild ? 2 : backtestWatch ? 1 : 0)
    + (portfolioTheory.tone === "negative" ? 2 : portfolioTheory.tone === "neutral" ? 1 : 0);
  const tone = riskScore >= 4 ? "negative" : riskScore >= 2 ? "neutral" : "positive";
  const label = tone === "positive" ? "配置風險可控" : tone === "negative" ? "組合風險偏高" : "需再平衡觀察";
  const summary = `${label}：已依資產配置、均值-變異、相關性、風險貢獻、交易成本、資金管理、停損停利、VaR、波動、VIX、個股 AI 技術理論與回溯測試校準整合評估。`;
  return {
    tone,
    label,
    summary,
    factors,
    actions,
    theoryDetails: portfolioTheory.details,
    theoryActions: portfolioTheory.actions,
    metrics: { maxWeight, stopRiskRatio, var95, sharpeLike, avgMove, averageAiScore, backtestHealthy, backtestWatch, backtestRebuild, ...portfolioTheory.metrics },
    assetMix: assetCounts,
    source: PORTFOLIO_FACTOR_SOURCE,
  };
}


function renderPortfolioSimulator(items = getWatchlist()) {
  const summary = document.getElementById("portfolio-simulator-summary");
  const table = document.getElementById("portfolio-simulator-table");
  if (!summary || !table) return;
  if (!items.length) {
    summary.innerHTML = "";
    table.innerHTML = '<div class="watchlist-empty">加入自選股後即可建立組合損益模擬。</div>';
    return;
  }

  const saved = getPortfolioSimulation();
  const positions = items.map((stock) => {
    const key = watchlistKey(stock);
    const detail = watchlistDetailCache.get(key);
    const currentPrice = parseAnalysisNumber(detail?.close ?? stock.close) || 0;
    const setting = saved[key] || {};
    const entryPrice = parseAnalysisNumber(setting.entryPrice) || currentPrice;
    const shares = Math.max(0, parseAnalysisNumber(setting.shares) || 0);
    const stopLossPct = Math.max(0, parseAnalysisNumber(setting.stopLossPct) ?? 8);
    const takeProfitPct = Math.max(0, parseAnalysisNumber(setting.takeProfitPct) ?? 15);
    const cost = entryPrice * shares;
    const marketValue = currentPrice * shares;
    const pnl = marketValue - cost;
    const transactionCost = estimatePortfolioTransactionCost({ stock, currentPrice, entryPrice, shares });
    const netPnl = pnl - transactionCost;
    const returnPct = cost > 0 ? (pnl / cost) * 100 : 0;
    const netReturnPct = cost > 0 ? (netPnl / cost) * 100 : 0;
    const riskAmount = entryPrice * shares * (stopLossPct / 100);
    const analysis = watchlistAnalysisCache.get(key);
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
  const maxPosition = totalValue > 0
    ? Math.max(...active.map((item) => item.marketValue / totalValue * 100), 0)
    : 0;
  const riskLabel = !active.length
    ? "尚未建立模擬部位"
    : maxPosition > 50
      ? "單一持股集中度偏高"
      : totalRisk / Math.max(totalCost, 1) > 0.1
        ? "組合停損風險偏高"
        : "風險設定在可控區間";
  const portfolioAssessment = buildPortfolioFactorAssessment(positions, {
    totalCost,
    totalValue,
    totalPnl,
    totalTransactionCost,
    netPnl,
    totalReturn,
    netReturn,
    totalRisk,
  });

  summary.innerHTML = `
    <div><span>模擬投入成本</span><strong>${Math.round(totalCost).toLocaleString("zh-TW")} 元</strong></div>
    <div><span>目前市值</span><strong>${Math.round(totalValue).toLocaleString("zh-TW")} 元</strong></div>
    <div><span>未實現損益</span><strong class="${totalPnl > 0 ? "up" : totalPnl < 0 ? "down" : "flat"}">${formatSimulationMoney(totalPnl)}</strong></div>
    <div><span>估計交易成本</span><strong>${Math.round(totalTransactionCost).toLocaleString("zh-TW")} 元</strong></div>
    <div><span>成本後淨損益</span><strong class="${netPnl > 0 ? "up" : netPnl < 0 ? "down" : "flat"}">${formatSimulationMoney(netPnl)}</strong></div>
    <div><span>組合報酬率</span><strong class="${totalReturn > 0 ? "up" : totalReturn < 0 ? "down" : "flat"}">${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(2)}%</strong></div>
    <div><span>淨報酬率</span><strong class="${netReturn > 0 ? "up" : netReturn < 0 ? "down" : "flat"}">${netReturn >= 0 ? "+" : ""}${netReturn.toFixed(2)}%</strong></div>
    <div><span>停損風險金額</span><strong>${Math.round(totalRisk).toLocaleString("zh-TW")} 元</strong></div>
    <div><span>95% VaR 估計</span><strong>${Math.round(portfolioAssessment.metrics.var95 || 0).toLocaleString("zh-TW")} 元</strong></div>
    <div><span>單一最高權重</span><strong>${(portfolioAssessment.metrics.maxWeight || 0).toFixed(1)}%</strong></div>
    <div><span>組合年化波動</span><strong>${Number.isFinite(portfolioAssessment.metrics.portfolioVolatility) ? `${portfolioAssessment.metrics.portfolioVolatility.toFixed(1)}%` : "--"}</strong></div>
    <div><span>有效持股數</span><strong>${Number.isFinite(portfolioAssessment.metrics.effectivePositions) ? `${portfolioAssessment.metrics.effectivePositions.toFixed(1)} 檔` : "--"}</strong></div>
    <div><span>平均相關性</span><strong>${Number.isFinite(portfolioAssessment.metrics.averageCorrelation) ? portfolioAssessment.metrics.averageCorrelation.toFixed(2) : "--"}</strong></div>
    <div><span>分散化比率</span><strong>${Number.isFinite(portfolioAssessment.metrics.diversificationRatio) ? portfolioAssessment.metrics.diversificationRatio.toFixed(2) : "--"}</strong></div>
    <div><span>效率分數</span><strong class="${portfolioAssessment.metrics.efficiencyScore > 0 ? "up" : portfolioAssessment.metrics.efficiencyScore < 0 ? "down" : "flat"}">${Number.isFinite(portfolioAssessment.metrics.efficiencyScore) ? portfolioAssessment.metrics.efficiencyScore.toFixed(2) : "--"}</strong></div>
    <div><span>AI 平均分數</span><strong class="${portfolioAssessment.metrics.averageAiScore > 0 ? "up" : portfolioAssessment.metrics.averageAiScore < 0 ? "down" : "flat"}">${portfolioAssessment.metrics.averageAiScore > 0 ? "+" : ""}${(portfolioAssessment.metrics.averageAiScore || 0).toFixed(1)}</strong></div>
    <div><span>回測警示檔數</span><strong class="${portfolioAssessment.metrics.backtestRebuild ? "down" : portfolioAssessment.metrics.backtestWatch ? "flat" : "up"}">${portfolioAssessment.metrics.backtestWatch || 0} 觀察 / ${portfolioAssessment.metrics.backtestRebuild || 0} 重建</strong></div>
    <div><span>風險摘要</span><strong>${riskLabel}</strong></div>
  `;

  table.innerHTML = `
    <article class="portfolio-factor-card is-${portfolioAssessment.tone}">
      <div class="portfolio-factor-head">
        <div>
          <p class="panel-kicker">Portfolio factors</p>
          <h4>${portfolioAssessment.label}</h4>
        </div>
        <a href="${safeUrl(portfolioAssessment.source.url)}" target="_blank" rel="noreferrer noopener">自選組合因素基準</a>
      </div>
      <p>${portfolioAssessment.summary}</p>
      <div class="portfolio-factor-grid">
        <section>
          <h5>納入考量</h5>
          <ul>${portfolioAssessment.factors.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </section>
        <section>
          <h5>風險與再平衡</h5>
          <ul>${portfolioAssessment.actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </section>
        <section>
          <h5>資產組合理論</h5>
          <ul>${(portfolioAssessment.theoryDetails || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </section>
      </div>
    </article>
    <div class="portfolio-table-head">
      <span>個股</span><span>目前價</span><span>模擬進場價</span><span>股數</span>
      <span>停損 / 停利</span><span>淨損益</span><span>判別訊號</span>
    </div>
    ${positions.map((item) => `
      <div class="portfolio-position-row">
        <div class="portfolio-stock-name"><strong>${item.stock.code}</strong><span>${item.stock.name}</span></div>
        <strong>${item.currentPrice ? item.currentPrice.toLocaleString("zh-TW") : "--"}</strong>
        <label><span>進場價</span><input type="number" min="0" step="0.01" value="${item.entryPrice || ""}" data-portfolio-key="${item.key}" data-portfolio-field="entryPrice"></label>
        <label><span>股數</span><input type="number" min="0" step="1" value="${item.shares || 0}" data-portfolio-key="${item.key}" data-portfolio-field="shares"></label>
        <div class="portfolio-risk-inputs">
          <label><span>停損 %</span><input type="number" min="0" step="0.5" value="${item.stopLossPct}" data-portfolio-key="${item.key}" data-portfolio-field="stopLossPct"></label>
          <label><span>停利 %</span><input type="number" min="0" step="0.5" value="${item.takeProfitPct}" data-portfolio-key="${item.key}" data-portfolio-field="takeProfitPct"></label>
        </div>
        <div class="portfolio-pnl ${item.netPnl > 0 ? "up" : item.netPnl < 0 ? "down" : "flat"}">
          <strong>${formatSimulationMoney(item.netPnl)}</strong>
          <span>淨 ${item.netReturnPct >= 0 ? "+" : ""}${item.netReturnPct.toFixed(2)}%｜成本 ${Math.round(item.transactionCost).toLocaleString("zh-TW")}</span>
        </div>
        <div class="portfolio-signal is-${item.signal.tone}">
          <strong>${item.signal.label}</strong>
          <span>${item.signal.note}</span>
        </div>
      </div>
    `).join("")}
  `;

  table.querySelectorAll("[data-portfolio-key]").forEach((input) => {
    input.addEventListener("change", () => {
      const value = Math.max(0, Number(input.value) || 0);
      const simulation = getPortfolioSimulation();
      simulation[input.dataset.portfolioKey] = {
        ...(simulation[input.dataset.portfolioKey] || {}),
        [input.dataset.portfolioField]: value,
      };
      savePortfolioSimulation(simulation);
      renderPortfolioSimulator();
    });
  });
}

































function buildWatchlistAiAnalysis(stock, detail) {
  let score = 0;
  let evidenceCount = 0;
  const positives = [];
  const cautions = [];
  const close = parseAnalysisNumber(detail.close ?? stock.close);
  const ma5 = parseAnalysisNumber(detail.ma5);
  const ma20 = parseAnalysisNumber(detail.ma20);
  const ma60 = parseAnalysisNumber(detail.ma60);
  const pct = parseAnalysisNumber(detail.pct ?? stock.pct);
  const pe = parseAnalysisNumber(detail.valuation?.peRatio);
  const dividendYield = parseAnalysisNumber(detail.valuation?.dividendYield);
  const institutional = parseAnalysisNumber(detail.institutionalTrades?.totalValue);
  const largeHolderRatio = parseAnalysisNumber(detail.shareholderDistribution?.largeHolderRatio);
  const technicalTheory = analyzeTechnicalTheories(detail);
  score += technicalTheory.score;
  evidenceCount += technicalTheory.evidenceCount;

  if (close !== null && ma5 !== null) {
    evidenceCount += 1;
    if (close >= ma5) {
      score += 1;
      positives.push("股價站上 5 日均線，短線動能較穩定");
    } else {
      score -= 1;
      cautions.push("股價位於 5 日均線下方，短線仍需確認支撐");
    }
  }
  if (close !== null && ma20 !== null) {
    evidenceCount += 1;
    if (close >= ma20) {
      score += 1;
      positives.push("股價維持在 20 日均線之上");
    } else {
      score -= 1;
      cautions.push("股價跌破 20 日均線，中期趨勢偏弱");
    }
  }
  if (close !== null && ma60 !== null) {
    evidenceCount += 1;
    if (close >= ma60) score += 1;
    else {
      score -= 1;
      cautions.push("股價低於 60 日均線，波段風險較高");
    }
  }
  if (institutional !== null) {
    evidenceCount += 1;
    if (institutional > 0) {
      score += 1;
      positives.push("三大法人當日呈現買超");
    } else if (institutional < 0) {
      score -= 1;
      cautions.push("三大法人當日賣超，籌碼面偏保守");
    }
  }
  if (largeHolderRatio !== null) {
    evidenceCount += 1;
    if (largeHolderRatio >= 60) {
      score += 1;
      positives.push(`大戶持股約 ${largeHolderRatio.toFixed(1)}%，籌碼集中度較高`);
    } else if (largeHolderRatio < 35) {
      score -= 1;
      cautions.push("大戶持股比例偏低，籌碼較為分散");
    }
  }
  if (pe !== null) {
    evidenceCount += 1;
    if (pe > 40) {
      score -= 1;
      cautions.push(`本益比 ${pe.toFixed(1)}，估值處於較高區間`);
    } else if (pe > 0 && pe <= 20) {
      score += 1;
      positives.push(`本益比 ${pe.toFixed(1)}，估值相對收斂`);
    }
  }
  if (dividendYield !== null) {
    evidenceCount += 1;
    if (dividendYield >= 4) {
      score += 1;
      positives.push(`殖利率約 ${dividendYield.toFixed(2)}%，具收益支撐`);
    } else if (dividendYield < 1) {
      cautions.push("殖利率低於 1%，收益型保護較有限");
    }
  }
  if (pct !== null && Math.abs(pct) >= 5) {
    evidenceCount += 1;
    score += pct > 0 ? 1 : -1;
    cautions.push(`單日波動 ${pct.toFixed(2)}%，短線追價風險較高`);
  }

  let label = "中性觀察";
  let tone = "neutral";
  let suggestion = "等待趨勢與籌碼出現一致方向，再規劃分批操作。";
  if (score >= 5) {
    label = "偏多觀察";
    tone = "positive";
    suggestion = "多項因子偏正向，可續抱觀察；避免急漲時一次追高。";
  } else if (score <= -5) {
    label = "風險控管";
    tone = "negative";
    suggestion = "弱勢因子較多，宜控制部位並設定可承受的停損或減碼條件。";
  } else if (score > 0) {
    label = "中性偏多";
    tone = "positive";
    suggestion = "正向訊號略多，適合等待回檔支撐或量價確認。";
  } else if (score < 0) {
    label = "中性偏弱";
    tone = "negative";
    suggestion = "負向訊號略多，先觀察均線與法人籌碼是否止穩。";
  }

  const reasons = [
    ...technicalTheory.patterns.slice(0, 1),
    ...technicalTheory.indicators.slice(0, 1),
    ...(technicalTheory.breadthIndicators || []).slice(0, 1).map((item) => `${item.name} ${item.value}：${item.text}`),
    ...positives.slice(0, 1),
    ...cautions.slice(0, 1),
  ].slice(0, 4);
  if (!reasons.length) reasons.push("目前可用資料不足，暫不形成明確方向判斷");
  return {
    label,
    tone,
    score,
    suggestion,
    reasons,
    patterns: technicalTheory.patterns,
    indicators: technicalTheory.indicators,
    theorySignals: technicalTheory.theorySignals,
    adaptiveSummary: technicalTheory.adaptiveSummary,
    priceIndicators: technicalTheory.priceIndicators,
    volumeIndicators: technicalTheory.volumeIndicators,
    breadthIndicators: technicalTheory.breadthIndicators,
    indicatorSummary: technicalTheory.indicatorSummary,
    breadthSummary: technicalTheory.breadthSummary,
    backtestLearning: technicalTheory.backtestLearning,
    confidence: technicalTheory.adaptiveConfidence
      || (evidenceCount >= 10 ? "高" : evidenceCount >= 5 ? "中" : "低"),
    date: detail.snapshotDate || data?.snapshotDate || "--",
  };
}

function renderWatchlistAiSummary(items) {
  const container = document.getElementById("watchlist-ai-summary");
  if (!container) return;
  if (!items.length) {
    container.innerHTML = "";
    return;
  }
  const analyses = items.map((item) => watchlistAnalysisCache.get(watchlistKey(item))).filter(Boolean);
  if (!analyses.length) {
    container.innerHTML = '<div class="watchlist-ai-loading">正在整理自選股的技術、籌碼與估值訊號...</div>';
    return;
  }
  const failed = analyses.filter((item) => item.isError).length;
  const usableAnalyses = analyses.filter((item) => !item.isError);
  const positive = usableAnalyses.filter((item) => item.tone === "positive").length;
  const negative = usableAnalyses.filter((item) => item.tone === "negative").length;
  const pending = items.length - analyses.length;
  const overview = failed && !usableAnalyses.length
    ? "自選股資料暫時無法同步，請稍後重新整理。"
    : positive > negative
    ? "整體訊號偏正向，但仍應分散部位並避免追高。"
    : negative > positive
      ? "目前風險訊號較多，建議優先檢視弱勢持股。"
      : "多空訊號接近，適合等待個股趨勢進一步確認。";
  container.innerHTML = `
    <div>
      <span class="news-tag">AI 多因子摘要</span>
      <h4>${overview}</h4>
      <p>偏正向 ${positive} 檔、偏弱 ${negative} 檔${failed ? `，同步失敗 ${failed} 檔` : ""}${pending ? `，另有 ${pending} 檔分析中` : ""}。</p>
    </div>
    <small>依本站行情、均線、法人、集保與估值資料計算，僅供研究參考。</small>
  `;
}

function renderWatchlist() {
  const grid = document.getElementById("watchlist-grid");
  if (!grid) return;
  const items = getWatchlist();
  setText("watchlist-count", `${items.length} 檔`);
  if (!items.length) {
    grid.innerHTML = '<div class="watchlist-empty">尚未加入自選股，請至個股搜尋頁開啟股票詳情後加入。</div>';
    renderPortfolioSimulator(items);
    return;
  }

  renderWatchlistAiSummary(items);
  renderPortfolioSimulator(items);
  grid.innerHTML = items.map((stock) => {
    const analysis = watchlistAnalysisCache.get(watchlistKey(stock));
    const detailUrl = `tw-stock-search.html?q=${encodeURIComponent(stock.code)}&market=${encodeURIComponent(stock.market || "")}`;
    const stockKey = watchlistKey(stock);
    return `
    <article class="watchlist-card is-clickable" role="link" tabindex="0" data-watchlist-detail-url="${escapeHtml(detailUrl)}" aria-label="查看 ${escapeHtml(stock.code)} ${escapeHtml(stock.name)} 個股詳情">
      <div class="watchlist-card-head">
        <div>
          <span>${escapeHtml(stock.marketLabel || stock.market || "--")}</span>
          <h3>${escapeHtml(stock.code)} ${escapeHtml(stock.name)}</h3>
        </div>
        <button class="watchlist-remove" type="button" data-watchlist-remove="${escapeHtml(stockKey)}">移除</button>
      </div>
      <div class="watchlist-quote">
        <strong>${escapeHtml(stock.close || "--")}</strong>
        <span class="${toneClass(stock.tone)}">${escapeHtml(stock.change || "--")} / ${escapeHtml(stock.pct || "--")}</span>
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
          <p>正在讀取完整個股資料...</p>
        `}
      </div>
      <a class="watchlist-detail-link" href="${safeUrl(detailUrl)}">查看個股分析</a>
    </article>
  `;
  }).join("");

  grid.querySelectorAll("[data-watchlist-detail-url]").forEach((card) => {
    const openDetail = () => {
      const url = card.dataset.watchlistDetailUrl;
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

  grid.querySelectorAll("[data-watchlist-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      saveWatchlist(getWatchlist().filter((item) => watchlistKey(item) !== button.dataset.watchlistRemove));
      watchlistAnalysisCache.delete(button.dataset.watchlistRemove);
      watchlistDetailCache.delete(button.dataset.watchlistRemove);
      renderWatchlist();
      setText("watchlist-status", "已從自選股移除。");
    });
  });
}

async function loadWatchlistAiAnalyses(force = false) {
  const items = getWatchlist();
  if (!items.length) return;
  const requestId = ++watchlistAnalysisRequestId;
  if (force) watchlistAnalysisCache.clear();
  renderWatchlist();
  setText("watchlist-status", "正在同步 live 個股資料並更新 AI 多因子分析...");

  const queue = items.filter((item) => !watchlistAnalysisCache.has(watchlistKey(item)));
  let cursor = 0;
  let completed = items.length - queue.length;
  let failed = 0;
  async function runWatchlistAnalysisWorker() {
    while (cursor < queue.length) {
      const stock = queue[cursor++];
      const key = watchlistKey(stock);
      try {
        const params = new URLSearchParams({ quick: "1", refresh: "1" });
        if (stock.market) params.set("market", stock.market);
        const response = await fetchWithTimeout(
          `/api/twse/stock/${encodeURIComponent(stock.code)}?${params.toString()}`,
          { cache: "no-store" },
          45000,
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const detail = await response.json();
        if (requestId !== watchlistAnalysisRequestId) return;
        watchlistDetailCache.set(key, detail);
        watchlistAnalysisCache.set(key, buildWatchlistAiAnalysis(stock, detail));
        completed += 1;
        renderWatchlist();
      } catch (error) {
        failed += 1;
        watchlistAnalysisCache.set(key, {
          label: "資料同步失敗",
          tone: "negative",
          score: 0,
          suggestion: "live 個股資料暫時無法載入，請稍後重新整理或回到個股搜尋頁重試。",
          reasons: ["個股明細 live API 未完成，AI 分析暫停輸出。"],
          patterns: [],
          indicators: [],
          confidence: "低",
          date: data?.snapshotDate || "--",
          isError: true,
        });
        renderWatchlist();
        console.error(`Failed to analyze ${stock.code}:`, error);
      }
    }
  }
  await Promise.all([runWatchlistAnalysisWorker(), runWatchlistAnalysisWorker()]);
  if (requestId === watchlistAnalysisRequestId) {
    const statusText = failed
      ? `AI 分析完成 ${completed}/${items.length} 檔，${failed} 檔資料同步失敗；資料時間 ${data?.snapshotDate || "--"}。`
      : `AI 分析已更新，完成 ${completed}/${items.length} 檔，資料時間 ${data?.snapshotDate || "--"}。`;
    setText("watchlist-status", statusText);
    renderWatchlist();
  }
}

function renderWatchlistSearchResults(results) {
  const container = document.getElementById("watchlist-search-results");
  if (!container) return;
  const selected = new Set(getWatchlist().map(watchlistKey));
  if (!results.length) {
    container.innerHTML = '<div class="stock-detail-empty">查無搜尋結果。</div>';
    return;
  }
  container.innerHTML = results.map((stock) => {
    const key = watchlistKey(stock);
    const added = selected.has(key);
    return `
      <article class="watchlist-search-item">
        <div>
          <strong>${escapeHtml(stock.code)} ${escapeHtml(stock.name)}</strong>
          <span>${escapeHtml(stock.marketLabel || stock.market || "--")} · ${escapeHtml(stock.close || "--")} · <b class="${toneClass(stock.tone)}">${escapeHtml(stock.pct || "--")}</b></span>
        </div>
        <button class="btn ${added ? "" : "btn-primary"}" type="button" data-watchlist-add="${escapeHtml(key)}" ${added ? "disabled" : ""}>
          ${added ? "已加入" : "加入自選"}
        </button>
      </article>
    `;
  }).join("");

  container.querySelectorAll("[data-watchlist-add]:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => {
      const stock = results.find((item) => watchlistKey(item) === button.dataset.watchlistAdd);
      if (!stock) return;
      const items = getWatchlist();
      if (!items.some((item) => watchlistKey(item) === watchlistKey(stock))) {
        items.push(stock);
        saveWatchlist(items);
      }
      renderWatchlist();
      renderWatchlistSearchResults(results);
      setText("watchlist-status", `已加入 ${stock.code} ${stock.name}。`);
    });
  });
}

async function runWatchlistSearch(query) {
  const keyword = String(query || "").trim();
  if (!keyword) return;
  setText("watchlist-status", `正在同步 live 搜尋 ${keyword}...`);
  try {
    const response = await fetchWithTimeout(`/api/twse/live-search?q=${encodeURIComponent(keyword)}`, { cache: "no-store" }, 45000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    renderWatchlistSearchResults(payload.results || []);
    setText("watchlist-status", `live 搜尋找到 ${payload.count || 0} 筆結果，資料時間 ${payload.refreshedAt || payload.snapshotDate || "--"}。`);
  } catch (error) {
    renderWatchlistSearchResults([]);
    setText("watchlist-status", "live 搜尋同步失敗，請稍後再試。");
    console.error("Failed to search watchlist stocks:", error);
  }
}

function initWatchlistPage() {
  renderWatchlist();
  document.getElementById("watchlist-analysis-refresh")?.addEventListener("click", () => {
    loadWatchlistAiAnalyses(true);
  });
  document.getElementById("portfolio-simulator-reset")?.addEventListener("click", () => {
    localStorage.removeItem(PORTFOLIO_SIM_STORAGE_KEY);
    renderPortfolioSimulator();
  });
  if (getWatchlist().length) {
    setText("watchlist-status", "正在同步最新大盤資料...");
    loadLiveData().then((ok) => {
      if (ok === false) {
        setText("watchlist-status", "最新大盤資料同步失敗，AI 分析暫停。");
        return;
      }
      loadWatchlistAiAnalyses();
    });
  }
}

function renderSearchResults(results) {
  const container = document.getElementById("search-results");
  if (!container) return;

  if (!results.length) {
    container.innerHTML = '<div class="stock-detail-empty">查無搜尋結果。</div>';
    return;
  }

  container.innerHTML = results.map((stock) => `
    <button class="search-result-item" type="button" data-code="${escapeHtml(stock.code)}" data-market="${escapeHtml(stock.market || "")}">
      <span class="search-result-main">${escapeHtml(stock.code)} ${escapeHtml(stock.name)}${stock.marketLabel ? ` <small class="search-result-market">${escapeHtml(stock.marketLabel)}</small>` : ""}</span>
      <span class="search-result-sub">${escapeHtml(stock.close)} / <strong class="${toneClass(stock.tone)}">${escapeHtml(stock.pct)}</strong></span>
    </button>
  `).join("");

  container.querySelectorAll("[data-code]").forEach((button) => {
    button.addEventListener("click", () => {
      container.querySelectorAll("[data-code]").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      const fallbackStock = results.find((stock) => (
        String(stock.code) === button.dataset.code
        && (!button.dataset.market || !stock.market || String(stock.market).toUpperCase() === button.dataset.market.toUpperCase())
      ));
      const url = new URL(window.location.href);
      url.searchParams.set("q", button.dataset.code || "");
      if (button.dataset.market) {
        url.searchParams.set("market", button.dataset.market);
      } else {
        url.searchParams.delete("market");
      }
      window.history.replaceState({}, "", url);
      loadStockDetail(button.dataset.code, button.dataset.market, fallbackStock);
    });
  });
}









function alignAndNormalizeSeries(primarySeries = [], comparisonSeries = []) {
  const primaryMap = new Map(normalizeGlobalSeries(primarySeries).map((item) => [item.date, item.value]));
  const comparisonMap = new Map(normalizeGlobalSeries(comparisonSeries).map((item) => [item.date, item.value]));
  const dates = Array.from(primaryMap.keys()).filter((date) => comparisonMap.has(date)).slice(-160);
  if (dates.length < 2) {
    const fallback = normalizeGlobalSeries(primarySeries).slice(-160);
    const base = fallback[0]?.value || 1;
    return fallback.map((item) => ({
      date: item.date,
      primary: (item.value / base) * 100,
      comparison: null,
    }));
  }
  const primaryBase = primaryMap.get(dates[0]) || 1;
  const comparisonBase = comparisonMap.get(dates[0]) || 1;
  return dates.map((date) => ({
    date,
    primary: ((primaryMap.get(date) || primaryBase) / primaryBase) * 100,
    comparison: ((comparisonMap.get(date) || comparisonBase) / comparisonBase) * 100,
  }));
}



























function renderGlobalTechnicalAnalysis(item) {
  const detail = buildGlobalMarketDetail(item);
  if (detail.historyDays.length < 30) {
    return `
      <section class="global-technical-block">
        <h4>技術走勢與分析</h4>
        <p class="source-note">歷史資料不足，暫無法套用完整個股詳情技術分析。</p>
      </section>
    `;
  }
  const technicalTheory = analyzeTechnicalTheories(detail);
  const trendSummary = buildTechnicalTrendSummary(detail, technicalTheory);
  const theoryTone = technicalTheory.score >= 3 ? "positive" : technicalTheory.score <= -3 ? "negative" : "neutral";
  const priceSignals = (technicalTheory.priceIndicators || []).slice(0, 4);
  const volumeSignals = (technicalTheory.volumeIndicators || []).slice(0, 2);
  const chartHtml = renderTechnicalChart(
    detail,
    "day",
    ["bollinger", "supportResistance"],
    [5, 20, 60],
    Math.min(detail.historyDays.length, 120),
    0,
    ["kd", "macd", "rsi"],
  );
  return `
    <section class="global-technical-block">
      <div class="global-technical-head">
        <div>
          <p class="panel-kicker">Technical detail</p>
          <h4>走勢圖與技術分析</h4>
        </div>
        <span class="stock-theory-score is-${theoryTone}">${trendSummary.label} · ${technicalTheory.score > 0 ? "+" : ""}${technicalTheory.score}</span>
      </div>
      <div class="global-technical-chart">${chartHtml}</div>
      <article class="stock-market-context technical-trend-summary is-${trendSummary.tone}">
        <div class="technical-summary-head">
          <div class="stock-theory-title">
            <span>AI technical outlook</span>
            <h4>${escapeHtml(item.name || item.symbol || "--")} 趨勢風向</h4>
          </div>
          <div class="technical-summary-score">
            <b>${escapeHtml(String(trendSummary.score))}</b>
            <span>${escapeHtml(trendSummary.label)}</span>
          </div>
        </div>
        <p>${escapeHtml(trendSummary.summary)}</p>
        <div class="technical-summary-timeframes">
          ${trendSummary.timeframes.map((entry) => `<span><small>${escapeHtml(entry.label)}</small><b>${escapeHtml(entry.value)}</b></span>`).join("")}
          <span><small>分析信心</small><b>${escapeHtml(trendSummary.confidence)}</b></span>
        </div>
        <div class="technical-summary-columns">
          <section>
            <h5>價的技術指標</h5>
            <ul>${priceSignals.map((signal) => `<li>${escapeHtml(signal.name)} ${escapeHtml(signal.value)}：${escapeHtml(signal.text)}</li>`).join("") || "<li>價指標資料不足</li>"}</ul>
          </section>
          <section>
            <h5>量的技術指標</h5>
            <ul>${volumeSignals.map((signal) => `<li>${escapeHtml(signal.name)} ${escapeHtml(signal.value)}：${escapeHtml(signal.text)}</li>`).join("") || "<li>量指標資料不足</li>"}</ul>
          </section>
        </div>
        <div class="technical-summary-action">
          <strong>目前風向與操作節奏</strong>
          <span>${escapeHtml(trendSummary.action)}</span>
        </div>
      </article>
    </section>
  `;
}


























function renderUsEtfDetailSignalCard(title, value, note, tone = "flat") {
  return `
    <article class="us-etf-detail-signal-card ${toneClass(tone)}">
      <span>${escapeHtml(title)}</span>
      <strong>${escapeHtml(value)}</strong>
      <p>${escapeHtml(note)}</p>
    </article>
  `;
}

function renderUsEtfDetailFact(label, value, note, tone = "flat") {
  return `
    <div>
      <span>${escapeHtml(label)}</span>
      <strong class="${toneClass(tone)}">${escapeHtml(value)}</strong>
      <small>${escapeHtml(note)}</small>
    </div>
  `;
}



function renderUsEtfDetailBriefCard(title, insight = {}, tone = "flat") {
  const points = Array.isArray(insight.points) ? insight.points : [];
  return `
    <section class="us-etf-detail-brief-card ${toneClass(tone)}">
      <b>${escapeHtml(title)}</b>
      <p>${escapeHtml(insight.lead || "")}</p>
      <ul>
        ${points.slice(0, 3).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
      </ul>
    </section>
  `;
}










async function loadUsNyseListedStocks() {
  await loadUsNyseDirectory("stock");
}





















































function renderFuturesMarketFramework(model) {
  const cards = [
    {
      kicker: "Taiwan futures",
      title: "台灣期貨市場",
      count: `${model.taiwanItems.length} 檔`,
      text: "台指期、小台指、微台指、電子期、金融期、股票期貨、匯率期貨、ETF 期貨與商品期貨，以 TAIFEX 官方資料作為核心。",
      tags: ["TX", "MTX", "TMF", "TE", "TF", "股票期貨", "ETF 期貨"],
    },
    {
      kicker: "US futures",
      title: "美國期貨市場",
      count: `${model.usItems.length} 檔`,
      text: "涵蓋 S&P 500、Nasdaq 100、Dow、Russell 2000、美債、美元指數、黃金、原油、天然氣與農產品期貨。",
      tags: ["ES", "NQ", "YM", "RTY", "ZN", "GC", "CL", "NG"],
    },
    {
      kicker: "International futures",
      title: "國際期貨市場",
      count: `${model.internationalItems.length} 檔`,
      text: "整理歐洲、新加坡、日本、香港、能源、貴金屬、農產品與外匯期貨，作為跨市場風險參考。",
      tags: ["ICE", "SGX", "JPX", "HKEX", "Eurex", "FX", "Metals"],
    },
  ];
  return `
    <article class="panel-card futures-center-framework-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Website core functions</p>
          <h4>三大期貨市場框架</h4>
        </div>
        <span>台灣 / 美國 / 國際</span>
      </div>
      <div class="futures-market-framework-grid">
        ${cards.map((card) => `
          <section>
            <div><small>${escapeHtml(card.kicker)}</small><b>${escapeHtml(card.count)}</b></div>
            <h5>${escapeHtml(card.title)}</h5>
            <p>${escapeHtml(card.text)}</p>
            <div class="futures-chip-list">${card.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</div>
          </section>
        `).join("")}
      </div>
    </article>
  `;
}

function renderFuturesAiModules(model) {
  const modules = [
    ["AI 期貨趨勢判斷", `${model.aiScore}/100`, model.aiTone, "用股指、利率、能源、金屬與 TAIFEX 未平倉交叉判讀多空。"],
    ["多空方向分數", `${model.advancers} / ${model.decliners}`, model.advancers >= model.decliners ? "up" : "down", "以上漲與下跌廣度作為短線方向參考。"],
    ["支撐壓力分析", model.strongest?.symbol || "--", "flat", "由下方技術走勢區提供均線、區間與回撤觀察。"],
    ["波動率分析", model.weakest?.symbol || "--", model.weakest ? "down" : "flat", "用相對弱勢標的提示風險擴散來源。"],
    ["主力籌碼追蹤", `${model.taifexContracts.length} 檔`, "up", "以 TAIFEX 未平倉量觀察台灣期貨籌碼變化。"],
    ["未平倉量分析", model.taifexContracts[0] ? formatGlobalVolume(model.taifexContracts[0].openInterest || model.taifexContracts[0].close) : "--", "flat", "TX / MTX / TMF / TE / TF 保留官方日報數據。"],
    ["期貨與現貨價差", "保留欄位", "flat", "接入合法即時行情供應商後才顯示，不用日線推估。"],
    ["轉倉成本分析", "近遠月預留", "flat", "保留轉倉與期限結構欄位，避免和即時價格混判。"],
    ["停損停利與風險等級", model.aiTone === "up" ? "偏積極" : model.aiTone === "down" ? "保守" : "中性", model.aiTone, "期貨具槓桿與到期特性，需搭配保證金、停損與部位控管。"],
  ];
  const primaryModules = modules.slice(0, 3);
  const secondaryModules = modules.slice(3);
  const renderModule = ([title, value, tone, text]) => `
    <section class="is-${escapeHtml(tone)}">
      <small>${escapeHtml(title)}</small>
      <b>${escapeHtml(value)}</b>
      <p>${escapeHtml(text)}</p>
    </section>
  `;
  return `
    <article class="panel-card futures-center-ai-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI analysis modules</p>
          <h4>AI 期貨分析模組</h4>
        </div>
        <span>趨勢 / 籌碼 / 風險</span>
      </div>
      <div class="futures-ai-focus-grid">
        ${primaryModules.map(renderModule).join("")}
      </div>
      <div class="futures-center-subhead">
        <b>風險與資料條件</b>
        <small>下列模組以已同步資料為準，未接入合法即時源前不做推估。</small>
      </div>
      <div class="futures-ai-module-grid is-secondary">
        ${secondaryModules.map(renderModule).join("")}
      </div>
    </article>
  `;
}

function renderFuturesProductMatrix() {
  const rows = [
    ["金融期貨", "股指 / 利率 / 外匯", "台指期、美股指數期貨、美債期貨與外匯期貨，用來判斷風險偏好與資金流向。"],
    ["商品期貨", "能源 / 金屬 / 農產品", "原油、天然氣、黃金、白銀、銅、玉米、小麥與黃豆，觀察通膨與供需循環。"],
    ["台灣契約", "TAIFEX 官方日報", "TX、MTX、TMF、TE、TF 以未平倉量為主，不用未平倉推估價格。"],
    ["技術分析", "走勢 / 支撐 / 壓力", "只對有足夠歷史序列的商品繪製走勢，避免空圖或錯誤推論。"],
    ["籌碼分析", "未平倉 / 量能", "台灣期貨看 TAIFEX，國際期貨看成交量欄位與日線資料同步狀態。"],
    ["風險控管", "停損 / 保證金 / 到期", "以槓桿、流動性、到期日與轉倉成本作為期貨風險核心。"],
  ];
  return `
    <article class="panel-card futures-center-product-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Product architecture</p>
          <h4>期貨商品與分析矩陣</h4>
        </div>
        <span>商品 / 技術 / 籌碼 / 風控</span>
      </div>
      <div class="futures-product-matrix">
        ${rows.map(([title, value, text]) => `
          <span>
            <small>${escapeHtml(title)}</small>
            <b>${escapeHtml(value)}</b>
            <em>${escapeHtml(text)}</em>
          </span>
        `).join("")}
      </div>
    </article>
  `;
}







































function clampFuturesVisualValue(value, min = 0, max = 100) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return min;
  return Math.max(min, Math.min(max, parsed));
}

function getFuturesFiniteVisualSeries(values = []) {
  return (values || [])
    .map((value, index) => ({ value: parseMarketNumber(value), index }))
    .filter((point) => Number.isFinite(point.value));
}


function renderFuturesMiniHistogram(values = [], tone = "flat", options = {}) {
  const points = getFuturesFiniteVisualSeries(values).slice(-(options.count || 30));
  if (points.length < 2) return '<span class="futures-mini-indicator is-empty">資料不足</span>';
  const width = 132;
  const height = 40;
  const pad = 5;
  const min = Math.min(...points.map((point) => point.value), 0);
  const max = Math.max(...points.map((point) => point.value), 0);
  const range = max === min ? 1 : max - min;
  const yFor = (value) => height - pad - ((value - min) / range) * (height - pad * 2);
  const baseY = yFor(0);
  const barWidth = Math.max(2, ((width - pad * 2) / points.length) * 0.56);
  const bars = points.map((point, index) => {
    const x = pad + (index / points.length) * (width - pad * 2);
    const y = yFor(point.value);
    return `<rect class="${point.value >= 0 ? "is-up" : "is-down"}" x="${x.toFixed(2)}" y="${Math.min(y, baseY).toFixed(2)}" width="${barWidth.toFixed(2)}" height="${Math.max(Math.abs(baseY - y), 1).toFixed(2)}" rx="1.4"></rect>`;
  }).join("");
  return `
    <svg class="futures-mini-histogram is-${escapeHtml(tone)}" viewBox="0 0 ${width} ${height}" aria-hidden="true">
      <line class="futures-mini-baseline" x1="${pad}" x2="${width - pad}" y1="${baseY.toFixed(2)}" y2="${baseY.toFixed(2)}"></line>
      ${bars}
    </svg>
  `;
}

function renderFuturesIndicatorGauge(value, min = 0, max = 100, tone = "flat") {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed) || max === min) return '<span class="futures-indicator-gauge is-empty"></span>';
  const percent = clampFuturesVisualValue(((parsed - min) / (max - min)) * 100, 0, 100);
  return `
    <span class="futures-indicator-gauge is-${escapeHtml(tone)}" style="--indicator-level:${percent.toFixed(1)}%">
      <span></span>
      <i></i>
    </span>
  `;
}

function renderFuturesIndicatorPlot(series = [], options = {}) {
  const width = 720;
  const height = 250;
  const pad = { top: 22, right: 24, bottom: 28, left: 48 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const visibleCount = options.count || 60;
  const normalized = series.map((item, index) => ({
    ...item,
    className: item.className || `is-line-${index + 1}`,
    values: (item.values || []).map((value) => parseMarketNumber(value)).slice(-visibleCount),
  })).filter((item) => item.values.some(Number.isFinite));
  const finiteValues = normalized.flatMap((item) => item.values.filter(Number.isFinite));
  if (!finiteValues.length) {
    return '<div class="futures-indicator-empty">此切換條件下暫無可繪製資料。</div>';
  }
  const min = Number.isFinite(options.min) ? options.min : Math.min(...finiteValues, Number.isFinite(options.baseline) ? options.baseline : Infinity);
  const max = Number.isFinite(options.max) ? options.max : Math.max(...finiteValues, Number.isFinite(options.baseline) ? options.baseline : -Infinity);
  const range = max === min ? Math.max(Math.abs(max) * 0.01, 1) : max - min;
  const yFor = (value) => pad.top + plotHeight - ((value - min) / range) * plotHeight;
  const xFor = (index, length) => pad.left + (index / Math.max(length - 1, 1)) * plotWidth;
  const grid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * plotHeight;
    const value = max - ratio * range;
    return `
      <line class="futures-indicator-grid" x1="${pad.left}" x2="${width - pad.right}" y1="${y.toFixed(2)}" y2="${y.toFixed(2)}"></line>
      <text class="futures-indicator-axis" x="10" y="${(y + 4).toFixed(2)}">${escapeHtml(formatGlobalValue(value))}</text>
    `;
  }).join("");
  const baseline = Number.isFinite(options.baseline)
    ? `<line class="futures-indicator-baseline" x1="${pad.left}" x2="${width - pad.right}" y1="${yFor(options.baseline).toFixed(2)}" y2="${yFor(options.baseline).toFixed(2)}"></line>`
    : "";
  const shapes = normalized.map((item) => {
    const values = item.values;
    if (item.type === "bar") {
      const baseY = Number.isFinite(options.baseline) ? yFor(options.baseline) : yFor(0);
      const barWidth = Math.max(2, (plotWidth / Math.max(values.length, 1)) * 0.56);
      return values.map((value, index) => {
        if (!Number.isFinite(value)) return "";
        const x = pad.left + (index / Math.max(values.length, 1)) * plotWidth;
        const y = yFor(value);
        return `<rect class="futures-indicator-bar ${item.className} ${value >= 0 ? "is-up" : "is-down"}" x="${x.toFixed(2)}" y="${Math.min(y, baseY).toFixed(2)}" width="${barWidth.toFixed(2)}" height="${Math.max(Math.abs(baseY - y), 1).toFixed(2)}" rx="2"></rect>`;
      }).join("");
    }
    const points = values
      .map((value, index) => (Number.isFinite(value) ? `${xFor(index, values.length).toFixed(2)},${yFor(value).toFixed(2)}` : ""))
      .filter(Boolean)
      .join(" ");
    return points ? `<polyline class="futures-indicator-line ${item.className}" points="${points}"></polyline>` : "";
  }).join("");
  const legend = normalized.map((item) => `
    <span><i class="${escapeHtml(item.className)}"></i>${escapeHtml(item.label || "--")}</span>
  `).join("");
  return `
    <div class="futures-indicator-plot">
      <div class="futures-indicator-plot-head">
        <span>
          <b>${escapeHtml(options.title || "指標圖形")}</b>
          <small>${escapeHtml(options.caption || "")}</small>
        </span>
        <div class="futures-indicator-legend">${legend}</div>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(options.title || "期貨技術指標圖")}">
        ${grid}
        ${baseline}
        ${shapes}
      </svg>
    </div>
  `;
}

function renderFuturesAnalysisMetric(label, value, note = "", tone = "flat", visual = "") {
  return `
    <span class="futures-analysis-metric is-${escapeHtml(tone)}">
      <small>${escapeHtml(label)}</small>
      <b>${escapeHtml(value)}</b>
      ${note ? `<em>${escapeHtml(note)}</em>` : ""}
    </span>
  `;
}



function renderFuturesAdvancedTechnicalPanel(item, rows = []) {
  const snapshot = buildFuturesTechnicalSnapshot(rows);
  const selectedInterval = item?.technicalCandleInterval || getSelectedFuturesTechnicalInterval(item);
  const intervalText = getFuturesTechnicalIntervalLabel(selectedInterval);
  const intervalUnit = selectedInterval === "week" ? "週" : selectedInterval === "month" ? "月" : "日";
  const latestClose = parseMarketNumber(rows.at(-1)?.close);
  const dowText = Number.isFinite(snapshot.ma[20]) && Number.isFinite(snapshot.ma[60])
    ? (snapshot.ma[20] >= snapshot.ma[60] ? "多頭排列觀察" : "空頭/修正觀察")
    : "等待長均線";
  const channelText = Number.isFinite(snapshot.support20) && Number.isFinite(snapshot.resistance20)
    ? `${formatGlobalValue(snapshot.support20)} - ${formatGlobalValue(snapshot.resistance20)}`
    : "--";
  const volumeProfileText = snapshot.pointOfControl
    ? `${formatGlobalValue(snapshot.pointOfControl.low)} - ${formatGlobalValue(snapshot.pointOfControl.high)}`
    : "--";
  const sourceSeries = snapshot.series || {};
  const channelPosition = Number.isFinite(latestClose) && Number.isFinite(snapshot.support20) && Number.isFinite(snapshot.resistance20)
    ? Math.round(((latestClose - snapshot.support20) / Math.max(snapshot.resistance20 - snapshot.support20, 1)) * 100)
    : null;
  const closeTone = rows.length >= 2 && parseMarketNumber(rows.at(-1)?.close) >= parseMarketNumber(rows.at(-2)?.close) ? "up" : "down";
  const rsiTone = Number.isFinite(snapshot.rsi) ? (snapshot.rsi >= 50 ? "up" : "down") : "flat";
  const kdTone = Number.isFinite(snapshot.kd.k) && Number.isFinite(snapshot.kd.d) ? (snapshot.kd.k >= snapshot.kd.d ? "up" : "down") : "flat";
  return `
    <article class="futures-advanced-technical-panel">
      <div class="futures-analysis-head">
        <span>
          <small>Advanced technical</small>
          <b>${escapeHtml(formatFuturesContractLabel(getSelectedFuturesTechnicalContract(item)))} · ${escapeHtml(intervalText)} 技術分析明細</b>
        </span>
        <em>${snapshot.count} 筆 K 線</em>
      </div>
      <div class="futures-analysis-module">
        <h5>均線分析</h5>
        <div class="futures-analysis-grid">
          ${[5, 10, 20, 60, 120, 240].map((period) => {
            const tone = Number.isFinite(latestClose) && Number.isFinite(snapshot.ma[period]) ? (latestClose >= snapshot.ma[period] ? "up" : "down") : "flat";
            return renderFuturesAnalysisMetric(`MA${period}`, formatFuturesIndicatorValue(snapshot.ma[period]), `${period}${intervalUnit}`, tone, renderFuturesMiniSparkline(sourceSeries.ma?.[period] || [], tone));
          }).join("")}
        </div>
      </div>
      <div class="futures-analysis-module">
        <h5>趨勢分析</h5>
        <div class="futures-analysis-grid">
          ${renderFuturesAnalysisMetric("趨勢線", dowText, "Dow Theory", Number.isFinite(snapshot.ma[20]) && Number.isFinite(snapshot.ma[60]) && snapshot.ma[20] >= snapshot.ma[60] ? "up" : "flat", renderFuturesMiniSparkline(sourceSeries.close || [], closeTone))}
          ${renderFuturesAnalysisMetric("支撐 / 壓力", channelText, "近20K", "flat", renderFuturesMiniSparkline(sourceSeries.close || [], closeTone))}
          ${renderFuturesAnalysisMetric("通道", Number.isFinite(channelPosition) ? `${channelPosition}%` : "--", "區間位置", Number.isFinite(channelPosition) && channelPosition >= 50 ? "up" : "down", renderFuturesIndicatorGauge(channelPosition, 0, 100, Number.isFinite(channelPosition) && channelPosition >= 50 ? "up" : "down"))}
          ${renderFuturesAnalysisMetric("Fibonacci", `${formatFuturesIndicatorValue(snapshot.fib38)} / ${formatFuturesIndicatorValue(snapshot.fib62)}`, "38.2 / 61.8", "flat", renderFuturesMiniSparkline(sourceSeries.close || [], closeTone))}
          ${renderFuturesAnalysisMetric("Elliott Wave", rows.length >= 30 ? "波段待人工確認" : "資料不足", "以高低點輔助", "flat", renderFuturesMiniSparkline(sourceSeries.close || [], closeTone))}
        </div>
      </div>
      <div class="futures-analysis-module">
        <h5>技術指標</h5>
        <div class="futures-analysis-grid">
          ${renderFuturesAnalysisMetric("MACD", `${formatFuturesIndicatorValue(snapshot.macd)} / ${formatFuturesIndicatorValue(snapshot.macdSignal)}`, "DIF / Signal", Number.isFinite(snapshot.macd) && Number.isFinite(snapshot.macdSignal) && snapshot.macd >= snapshot.macdSignal ? "up" : "down", renderFuturesMiniHistogram(sourceSeries.macd?.histogram || [], Number.isFinite(snapshot.macd) && Number.isFinite(snapshot.macdSignal) && snapshot.macd >= snapshot.macdSignal ? "up" : "down"))}
          ${renderFuturesAnalysisMetric("RSI", formatFuturesIndicatorValue(snapshot.rsi), "14", rsiTone, `${renderFuturesMiniSparkline(sourceSeries.rsi || [], rsiTone, { min: 0, max: 100, baseline: 50 })}${renderFuturesIndicatorGauge(snapshot.rsi, 0, 100, rsiTone)}`)}
          ${renderFuturesAnalysisMetric("KD", `${formatFuturesIndicatorValue(snapshot.kd.k)} / ${formatFuturesIndicatorValue(snapshot.kd.d)}`, "K / D", kdTone, `${renderFuturesMiniSparkline(sourceSeries.kd?.k || [], kdTone, { min: 0, max: 100, baseline: 50 })}${renderFuturesIndicatorGauge(snapshot.kd.k, 0, 100, kdTone)}`)}
          ${renderFuturesAnalysisMetric("DMI / ADX", `${formatFuturesIndicatorValue(snapshot.dmi.plusDi)} / ${formatFuturesIndicatorValue(snapshot.dmi.minusDi)} / ${formatFuturesIndicatorValue(snapshot.dmi.adx)}`, "+DI / -DI / ADX", Number.isFinite(snapshot.dmi.plusDi) && Number.isFinite(snapshot.dmi.minusDi) && snapshot.dmi.plusDi >= snapshot.dmi.minusDi ? "up" : "down", renderFuturesIndicatorGauge(snapshot.dmi.adx, 0, 60, "flat"))}
          ${renderFuturesAnalysisMetric("ATR", formatFuturesIndicatorValue(snapshot.atr), "14", "flat", renderFuturesMiniSparkline(sourceSeries.atr || [], "flat"))}
          ${renderFuturesAnalysisMetric("CCI", formatFuturesIndicatorValue(snapshot.cci), "20", Number.isFinite(snapshot.cci) && snapshot.cci >= 0 ? "up" : "down", renderFuturesMiniSparkline(sourceSeries.cci || [], Number.isFinite(snapshot.cci) && snapshot.cci >= 0 ? "up" : "down", { baseline: 0 }))}
          ${renderFuturesAnalysisMetric("Williams %R", formatFuturesIndicatorValue(snapshot.williamsR), "14", Number.isFinite(snapshot.williamsR) && snapshot.williamsR > -50 ? "up" : "down", `${renderFuturesMiniSparkline(sourceSeries.williamsR || [], Number.isFinite(snapshot.williamsR) && snapshot.williamsR > -50 ? "up" : "down", { min: -100, max: 0, baseline: -50 })}${renderFuturesIndicatorGauge(snapshot.williamsR, -100, 0, Number.isFinite(snapshot.williamsR) && snapshot.williamsR > -50 ? "up" : "down")}`)}
          ${renderFuturesAnalysisMetric("BIAS", formatFuturesIndicatorValue(snapshot.bias20, 2, "%"), "20", Number.isFinite(snapshot.bias20) && snapshot.bias20 >= 0 ? "up" : "down", renderFuturesMiniSparkline(sourceSeries.bias20 || [], Number.isFinite(snapshot.bias20) && snapshot.bias20 >= 0 ? "up" : "down", { baseline: 0 }))}
          ${renderFuturesAnalysisMetric("OBV", formatGlobalVolume(snapshot.obv), "累積", "flat", renderFuturesMiniSparkline(sourceSeries.obv || [], "flat"))}
          ${renderFuturesAnalysisMetric("MFI", formatFuturesIndicatorValue(snapshot.mfi), "14", Number.isFinite(snapshot.mfi) && snapshot.mfi >= 50 ? "up" : "down", `${renderFuturesMiniSparkline(sourceSeries.mfi || [], Number.isFinite(snapshot.mfi) && snapshot.mfi >= 50 ? "up" : "down", { min: 0, max: 100, baseline: 50 })}${renderFuturesIndicatorGauge(snapshot.mfi, 0, 100, Number.isFinite(snapshot.mfi) && snapshot.mfi >= 50 ? "up" : "down")}`)}
          ${renderFuturesAnalysisMetric("Momentum", formatFuturesIndicatorValue(snapshot.momentum), "10", Number.isFinite(snapshot.momentum) && snapshot.momentum >= 0 ? "up" : "down", renderFuturesMiniSparkline(sourceSeries.momentum || [], Number.isFinite(snapshot.momentum) && snapshot.momentum >= 0 ? "up" : "down", { baseline: 0 }))}
          ${renderFuturesAnalysisMetric("SAR", formatFuturesIndicatorValue(snapshot.sar), "Parabolic", Number.isFinite(latestClose) && Number.isFinite(snapshot.sar) && latestClose >= snapshot.sar ? "up" : "down", renderFuturesMiniSparkline(sourceSeries.close || [], closeTone))}
          ${renderFuturesAnalysisMetric("Bollinger", `${formatFuturesIndicatorValue(snapshot.bollinger.lower)} / ${formatFuturesIndicatorValue(snapshot.bollinger.upper)}`, "Lower / Upper", "flat", renderFuturesMiniSparkline(sourceSeries.close || [], closeTone))}
          ${renderFuturesAnalysisMetric("Ichimoku", `${formatFuturesIndicatorValue(snapshot.ichimoku.tenkan)} / ${formatFuturesIndicatorValue(snapshot.ichimoku.kijun)} / ${formatFuturesIndicatorValue(snapshot.ichimoku.senkouB)}`, "轉換 / 基準 / 雲B", "flat", renderFuturesMiniSparkline(sourceSeries.close || [], closeTone))}
        </div>
      </div>
      <div class="futures-analysis-module">
        <h5>成交量分析</h5>
        <div class="futures-analysis-grid">
          ${renderFuturesAnalysisMetric("Volume", formatGlobalVolume(rows.at(-1)?.volume), "最新", "flat", renderFuturesMiniHistogram(sourceSeries.volume || [], "flat"))}
          ${renderFuturesAnalysisMetric("Volume Profile", volumeProfileText, "近60K POC", "flat", renderFuturesMiniHistogram(sourceSeries.volume || [], "flat"))}
          ${renderFuturesAnalysisMetric("VWAP", formatFuturesIndicatorValue(snapshot.vwap), "近40K", Number.isFinite(latestClose) && Number.isFinite(snapshot.vwap) && latestClose >= snapshot.vwap ? "up" : "down", renderFuturesMiniSparkline(sourceSeries.vwap || [], Number.isFinite(latestClose) && Number.isFinite(snapshot.vwap) && latestClose >= snapshot.vwap ? "up" : "down"))}
          ${renderFuturesAnalysisMetric("Delta Volume", formatGlobalVolume(snapshot.deltaVolume), "近20K 上下量差", Number.isFinite(snapshot.deltaVolume) && snapshot.deltaVolume >= 0 ? "up" : "down", renderFuturesMiniHistogram(sourceSeries.deltaVolume || [], Number.isFinite(snapshot.deltaVolume) && snapshot.deltaVolume >= 0 ? "up" : "down"))}
        </div>
      </div>
      <div class="futures-analysis-module">
        <h5>籌碼分析</h5>
        <div class="futures-analysis-grid">
          ${renderFuturesAnalysisMetric("未平倉量 OI", formatGlobalVolume(snapshot.openInterest), "最新", "flat", renderFuturesMiniSparkline(sourceSeries.openInterest || [], "flat"))}
          ${renderFuturesAnalysisMetric("OI 增減", Number.isFinite(snapshot.oiChange) ? `${snapshot.oiChange >= 0 ? "+" : ""}${formatGlobalVolume(snapshot.oiChange)}` : "--", "前一K比較", Number.isFinite(snapshot.oiChange) && snapshot.oiChange >= 0 ? "up" : "down", renderFuturesMiniHistogram(sourceSeries.oiChange || [], Number.isFinite(snapshot.oiChange) && snapshot.oiChange >= 0 ? "up" : "down"))}
          ${renderFuturesAnalysisMetric("法人多空", "待官方明細", "需三大法人契約資料")}
          ${renderFuturesAnalysisMetric("大戶持倉", "待官方明細", "大額交易人資料")}
          ${renderFuturesAnalysisMetric("前20大交易人", "待官方明細", "交易人集中度")}
        </div>
      </div>
    </article>
  `;
}














function buildOptionsAnalysisCenterModelLegacy(payload = {}) {
  const items = getAssetHubItems(payload);
  const usable = getAssetHubUsableItems(payload);
  const chain = payload.taiwanOptionChain || {};
  derivativesOptionsSelectedUnderlying = getActiveTaiwanOptionUnderlying(chain);
  const summary = chain.summary || {};
  const publicChain = payload.optionChain || {};
  const vix = findAssetHubItemAny(payload, ["^VIX", "VIX", "VIXY"]);
  const vixValue = parseMarketNumber(vix?.close);
  const pcr = Number(summary.putCallRatio);
  const volumePcr = Number(summary.volumePutCallRatio);
  const callOi = Number(summary.callOpenInterest);
  const putOi = Number(summary.putOpenInterest);
  const maxPain = Number(summary.maxPain);
  const atmStrike = Number(summary.atmStrike);
  const ivValues = (Array.isArray(chain.chain) ? chain.chain : [])
    .flatMap((row) => [row?.call?.impliedVolatility, row?.put?.impliedVolatility])
    .map(Number)
    .filter((value) => Number.isFinite(value) && value > 0);
  const avgIv = ivValues.length ? ivValues.reduce((sum, value) => sum + value, 0) / ivValues.length : null;
  const regions = groupAssetHubItemsByRegion(items);
  const pcrRisk = Number.isFinite(pcr) ? Math.abs(pcr - 1) * 18 : 0;
  const vixRisk = Number.isFinite(vixValue) ? Math.max(0, vixValue - 16) * 1.8 : 0;
  const ivRisk = Number.isFinite(avgIv) ? Math.max(0, avgIv * 100 - 18) * 1.4 : 0;
  const riskScore = Math.round(clampAssetHubScore(38 + pcrRisk + vixRisk + ivRisk, 18, 92));
  const confidenceScore = Math.round(clampAssetHubScore(
    44
      + (Number.isFinite(pcr) ? 10 : 0)
      + (Number.isFinite(vixValue) ? 10 : 0)
      + (Number.isFinite(callOi) || Number.isFinite(putOi) ? 10 : 0)
      + (Number.isFinite(avgIv) ? 8 : 0),
    30,
    90,
  ));
  const tone = riskScore >= 68 ? "down" : riskScore <= 44 ? "up" : "flat";
  const stance = tone === "down"
    ? "避險與波動升溫"
    : tone === "up"
      ? "風險偏好多方"
      : "區間觀望等待突破";
  const decision = tone === "down"
    ? "Put / Call 或 VIX 顯示避險需求偏高，策略重點放在部位降槓桿、價差保護與到期風險控管。"
    : tone === "up"
      ? "VIX 與 PCR 壓力較低，偏向順勢或賣方波動策略，但仍需用 OI 壓力牆確認上方阻力。"
      : "PCR、VIX 與未平倉尚未形成單邊訊號，先用最大痛點、ATM 與 Call/Put OI 觀察區間壓力。";
  return {
    items,
    usable,
    regions,
    chain,
    publicChain,
    vix,
    vixValue,
    pcr,
    volumePcr,
    callOi,
    putOi,
    maxPain,
    atmStrike,
    avgIv,
    riskScore,
    confidenceScore,
    tone,
    stance,
    decision,
    updatedAt: payload.updatedAt || "",
    catalogCount: Number(payload.catalogCount) || items.length,
  };
}

function renderOptionsAnalysisCenterLegacy(payload) {
  const model = buildOptionsAnalysisCenterModel(payload);
  const expiryText = model.chain?.selectedExpiry
    ? `${model.chain.selectedExpiry}${model.chain.selectedExpiryDate ? ` / ${model.chain.selectedExpiryDate}` : ""}`
    : "--";
  const maxPainGap = Number.isFinite(model.atmStrike) && Number.isFinite(model.maxPain)
    ? model.atmStrike - model.maxPain
    : null;
  const framework = [
    ["即時行情中心", "台灣選擇權、VIX、美股 ETF 選擇權與地區市場同步監控。", `${model.usable.length} / ${model.catalogCount}`],
    ["Options Chain", "履約價、Bid / Ask、成交量、未平倉與 IV 集中檢核。", expiryText],
    ["Greeks / IV", "Delta、Gamma、Theta、Vega 與 IV Rank 作為下一層風險欄位。", Number.isFinite(model.avgIv) ? `平均 IV ${(model.avgIv * 100).toFixed(1)}%` : "等待 IV"],
    ["PCR / OI", "Put / Call Ratio、Call OI、Put OI 與壓力牆判斷情緒。", Number.isFinite(model.pcr) ? model.pcr.toFixed(2) : "--"],
    ["Max Pain / GEX", "最大痛點、Gamma Exposure、Vanna、Charm 用於到期週風險。", Number.isFinite(model.maxPain) ? formatAssetOptionWhole(model.maxPain) : "--"],
    ["AI 風控", "以 VIX、PCR、OI、IV 與到期日輸出情境、風險與操作條件。", `${model.riskScore}/100`],
  ];
  const sourceRows = [
    ["TAIFEX", "市場選擇權鏈、OI、PCR、最大痛點與到期日。"],
    ["CBOE / OCC", "VIX、公開美股 Options Chain 與清算資料。"],
    ["Nasdaq / NYSE", "SPY、QQQ、IWM、NVDA、TSLA 等標的參考行情。"],
    ["Eurex / JPX / HKEX / SGX", "國際選擇權市場保留擴充入口。"],
  ];
  return `
    <section class="section options-analysis-center" id="options-analysis-center">
      <article class="panel-card options-center-card">
        <div class="options-center-head">
          <div>
            <p class="panel-kicker">Options Analysis Center</p>
            <h3>選擇權 AI 決策中心</h3>
            <p class="chart-subtitle">整合即時行情、Options Chain、Greeks / IV、PCR / OI、Gamma Exposure、Max Pain 與 AI 風控；資料不足的模型欄位會保留待同步狀態，不產生假訊號。</p>
          </div>
          <span class="chip chip-gold">${escapeHtml(model.updatedAt || "Live data")}</span>
        </div>
        <div class="options-center-decision is-${model.tone}">
          <div class="options-center-ai-brief">
            <small>AI 主結論</small>
            <strong>${escapeHtml(model.stance)}</strong>
            <p>${escapeHtml(model.decision)}</p>
          </div>
          <div class="options-center-score">
            <span>風險分數</span>
            <b>${model.riskScore}<small>/100</small></b>
            <em>信心 ${model.confidenceScore}/100</em>
          </div>
        </div>
        <div class="options-center-metrics">
          <span><small>OI Put / Call</small><b>${Number.isFinite(model.pcr) ? model.pcr.toFixed(2) : "--"}</b><em>${Number.isFinite(model.volumePcr) ? `量 PCR ${model.volumePcr.toFixed(2)}` : "量 PCR --"}</em></span>
          <span><small>Call / Put OI</small><b>${formatAssetOptionWhole(model.callOi)} / ${formatAssetOptionWhole(model.putOi)}</b><em>壓力牆樣本</em></span>
          <span><small>最大痛點</small><b>${formatAssetOptionWhole(model.maxPain)}</b><em>${Number.isFinite(maxPainGap) ? `ATM 差 ${maxPainGap >= 0 ? "+" : ""}${formatAssetOptionWhole(maxPainGap)}` : "ATM --"}</em></span>
          <span><small>CBOE VIX</small><b>${Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--"}</b><em>${escapeHtml(model.vix?.pct || "--")}</em></span>
          <span><small>地區市場</small><b>${model.regions.length}</b><em>${model.items.length} 筆線上標的</em></span>
        </div>
        <div class="options-center-framework">
          ${framework.map(([title, text, value]) => `
            <section>
              <small>${escapeHtml(value)}</small>
              <b>${escapeHtml(title)}</b>
              <p>${escapeHtml(text)}</p>
            </section>
          `).join("")}
        </div>
        <div class="options-center-source-grid">
          ${sourceRows.map(([title, text]) => `<span><b>${escapeHtml(title)}</b><small>${escapeHtml(text)}</small></span>`).join("")}
        </div>
      </article>
    </section>
  `;
}






















function getOptionsPlatformReadiness(model) {
  const usChainCount = (model.publicChain?.calls?.length || 0) + (model.publicChain?.puts?.length || 0);
  return Math.round(clampAssetHubScore(
    (model.rows.length ? 24 : 0)
      + (model.distribution.length ? 10 : 0)
      + (model.pcr !== null ? 14 : 0)
      + (model.volumePcr !== null ? 10 : 0)
      + (model.ivValues.length ? 12 : 0)
      + (Number.isFinite(model.vixValue) ? 10 : 0)
      + Math.min(model.macroItems.length * 4, 14)
      + (usChainCount ? 6 : 0),
    0,
    100,
  ));
}

function renderOptionsPlatformConsole(model) {
  return "";
  const source = model.chain?.source || {};
  const sourceName = source.primary || "資料源同步中";
  const optionLabel = getTaiwanOptionProductLabel(model.chain);
  const optionSymbol = getActiveTaiwanOptionUnderlying(model.chain);
  const readiness = getOptionsPlatformReadiness(model);
  const usChainCount = (model.publicChain?.calls?.length || 0) + (model.publicChain?.puts?.length || 0);
  const macroCount = model.macroItems.length;
  const netBias = Math.max(model.probabilities.bullish, model.probabilities.bearish, model.probabilities.range);
  const sourceUrl = source.primaryUrl || source.officialReferenceUrl || "";
  const tickerItems = [
    [optionSymbol, model.chain?.selectedExpiry || "--", model.rows.length ? `${model.rows.length} 履約價` : "同步中"],
    ["現貨", formatGlobalValue(model.chain?.spot?.value ?? model.chain?.underlyingPrice), model.chain?.spot?.date || model.chain?.tradeDate || "--"],
    ["PCR", optionsDecimal(model.pcr), "OI Put / Call"],
    ["VIX", Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--", model.vix?.pct || "波動率"],
    ["S&P 500", formatGlobalValue(model.sp500?.close), model.sp500?.pct || "跨市場"],
    ["Nasdaq", formatGlobalValue(model.nasdaq?.close), model.nasdaq?.pct || "科技股"],
    ["DXY", formatGlobalValue(model.dxy?.close), model.dxy?.pct || "美元"],
    ["Gold", formatGlobalValue(model.gold?.close), model.gold?.pct || "避險"],
  ];
  const dashboardCards = [
    ["全球風險燈號", model.riskLight.label, model.riskLight.text, model.riskLight.tone],
    ["AI 多空分數", `${escapeHtml(model.direction)} ${netBias}%`, `多 ${model.probabilities.bullish}% / 空 ${model.probabilities.bearish}% / 震盪 ${model.probabilities.range}%`, model.direction === "偏多" ? "green" : model.direction === "偏空" ? "red" : "yellow"],
    ["波動率狀態", `VIX ${Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--"}`, `平均 IV ${optionsPct(model.avgIv)}，距到期 ${model.expiryDays ?? "--"} 天`, model.riskScore >= 66 ? "orange" : "blue"],
    ["市場健康度", `${readiness}/100`, `已接入 ${model.rows.length || 0} 檔 ${optionLabel}、${macroCount} 組跨市場資料`, readiness >= 75 ? "green" : readiness >= 48 ? "yellow" : "red"],
  ];
  const navGroups = [
    ["Dashboard", [["AI 決策中心", "#options-ai-center"], ["決策摘要", "#options-decision-brief"], ["多模型驗證", "#options-cross-validation"]]],
    ["Market Center", [["選擇權鏈", "#asset-options"], ["資料與策略引擎", "#options-data-engine"], ["風險中心", "#options-risk-center"]]],
    ["Data Center", [["官方日報", "#asset-options"], ["地區市場", "#options-regional-market"], ["線上明細", "#options-online-data"]]],
  ];
  const dataCards = [
    ["TAIFEX", "主資料源", `${model.rows.length} 檔官方日報`, "good"],
    ["US Chain", usChainCount ? "已接入" : "待同步", usChainCount ? `${usChainCount} 筆 Call / Put 合約` : "保留 SPY / QQQ / IWM 切換", usChainCount ? "good" : "warn"],
    ["Cross Market", macroCount ? "已接入" : "同步中", macroCount ? `${macroCount} 組：美股、美元、利率、商品` : "等待跨市場 API 回傳", macroCount ? "good" : "warn"],
  ];
  const strategies = buildOptionsStrategyRows(model);
  const topStrategy = strategies[0] || null;
  const putWall = model.oiWalls.putWall?.strike;
  const callWall = model.oiWalls.callWall?.strike;
  const overviewOiRows = pickTaiwanOptionRows(model.distribution || [], model.atmStrike, 22)
    .map((item) => ({
      strike: optionsNumber(item.strike),
      totalOi: (Number(item.callOpenInterest) || 0) + (Number(item.putOpenInterest) || 0),
    }))
    .filter((item) => item.strike !== null && item.totalOi > 0)
    .sort((left, right) => right.totalOi - left.totalOi)
    .slice(0, 3);
  const overviewOiZone = overviewOiRows.length
    ? overviewOiRows.map((item) => `${optionsWhole(item.strike)}：${optionsWhole(item.totalOi)}`).join(" / ")
    : "OI 集中區同步中";
  const gammaStatus = model.expiryDays !== null && model.expiryDays <= 7 ? "到期週高敏感" : model.expiryDays !== null ? "一般觀察" : "待到期日";
  const vegaStatus = model.avgIv !== null && model.avgIv >= 0.25 ? "權利金偏貴" : model.avgIv !== null ? "波動正常" : "待 IV";
  const moduleCards = [
    {
      label: "AI Market Summary",
      title: "AI 市場摘要",
      value: `${model.direction} · ${model.riskLight.label}`,
      text: `${model.primaryRisk}；PCR ${optionsDecimal(model.pcr)}、Volume PCR ${optionsDecimal(model.volumePcr)}、信心 ${model.confidenceScore}/100。`,
    },
    {
      label: "AI Trend Prediction",
      title: "AI 趨勢預測",
      value: `多 ${model.probabilities.bullish}% / 空 ${model.probabilities.bearish}%`,
      text: `支撐 ${optionsWhole(putWall)}、壓力 ${optionsWhole(callWall)}、最大痛點 ${optionsWhole(model.maxPain)}，用 OI 牆與波動率交叉判讀。`,
    },
    {
      label: "Full Market OI Summary",
      title: "全市場 OI 摘要",
      value: `Call ${optionsWhole(callWall)} / Put ${optionsWhole(putWall)}`,
      text: `Max Pain ${optionsWhole(model.maxPain)}；OI 集中區 ${overviewOiZone}。這裡是固定全市場摘要，履約價選取分析在市場選擇權鏈內更新。`,
    },
    {
      label: "AI Cross Market Engine",
      title: "跨市場引擎",
      value: `${macroCount} 組資料`,
      text: `同步美股、美元、利率、黃金與原油；目前 VIX ${Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--"}，用來校正 ${optionLabel} 風險分數。`,
    },
    {
      label: "AI Decision Center",
      title: "AI 決策中心",
      value: topStrategy ? `${topStrategy.name} ${topStrategy.score}/100` : "等待策略分數",
      text: topStrategy ? `${topStrategy.evidence}；${topStrategy.control}` : "等待選擇權鏈、IV 與跨市場資料完成同步後輸出策略排序。",
    },
    {
      label: "Risk Center",
      title: "風險中心",
      value: `${model.riskScore}/100`,
      text: `Gamma：${gammaStatus}；Vega：${vegaStatus}；到期 ${model.expiryDays ?? "--"} 天，裸賣與槓桿需依風險燈號調整。`,
    },
    {
      label: "Data Center",
      title: "資料中心",
      value: `${model.rows.length || 0} 檔 ${optionSymbol}`,
      text: `主資料源 ${sourceName}；US chain ${usChainCount || 0} 筆，${optionLabel} 使用 TAIFEX 官方日報優先，缺資料時才啟用 Yahoo 後備。`,
    },
    {
      label: "System Monitor",
      title: "系統監控",
      value: `${readiness}/100`,
      text: `資料完整度由 ${optionLabel} 鏈、PCR、IV、VIX 與跨市場資料計算；缺漏時會保守降權，不補假值。`,
    },
  ];
  return `
    <section class="section options-platform-console" id="options-platform">
      <article class="panel-card options-platform-card">
        <div class="options-platform-head">
          <div>
            <p class="panel-kicker">Global AI Derivatives Intelligence Platform</p>
            <h3>平台總覽已停用</h3>
            <p class="chart-subtitle">導入連結中的核心模組：AI 市場摘要、趨勢預測、跨市場引擎、決策中心、風險中心、資料中心與系統監控；所有行情、PCR、IV、風險燈號與策略分數皆由目前 API 與模型即時計算。</p>
          </div>
          <div class="options-platform-source">
            <small>Active source</small>
            <b>${escapeHtml(sourceName)}</b>
            ${sourceUrl ? `<a href="${safeUrl(sourceUrl)}" target="_blank" rel="noopener noreferrer">查看來源</a>` : ""}
          </div>
        </div>
        <div class="options-platform-shell">
          <aside class="options-platform-rail" aria-label="選擇權平台模組導覽">
            ${navGroups.map(([group, links]) => `
              <div class="options-platform-nav-group">
                <small>${escapeHtml(group)}</small>
                ${links.map(([label, href]) => `<a href="${safeUrl(href)}">${escapeHtml(label)}</a>`).join("")}
              </div>
            `).join("")}
          </aside>
          <div class="options-platform-main">
            <div class="options-platform-ticker" aria-label="即時觀察行情列">
              ${tickerItems.map(([label, value, note]) => `
                <span>
                  <small>${escapeHtml(label)}</small>
                  <b>${escapeHtml(value || "--")}</b>
                  <em>${escapeHtml(note || "--")}</em>
                </span>
              `).join("")}
            </div>
            <div class="options-platform-dashboard">
              ${dashboardCards.map(([title, value, note, tone]) => `
                <section class="is-${escapeHtml(tone)}">
                  <small>${escapeHtml(title)}</small>
                  <b>${escapeHtml(value)}</b>
                  <p>${escapeHtml(note)}</p>
                </section>
              `).join("")}
            </div>
            <div class="options-platform-data-grid">
              ${dataCards.map(([title, status, note, tone]) => `
                <section class="is-${escapeHtml(tone)}">
                  <small>${escapeHtml(status)}</small>
                  <b>${escapeHtml(title)}</b>
                  <p>${escapeHtml(note)}</p>
                </section>
              `).join("")}
            </div>
            <div class="options-platform-module-grid">
              ${moduleCards.map((card) => `
                <section>
                  <small>${escapeHtml(card.label)}</small>
                  <b>${escapeHtml(card.title)}</b>
                  <strong>${escapeHtml(card.value)}</strong>
                  <p>${escapeHtml(card.text)}</p>
                </section>
              `).join("")}
            </div>
          </div>
        </div>
      </article>
    </section>
  `;
}

















function renderOptionsRiskCone(model) {
  const content = renderOptionsRiskConeContent(model);
  return content ? `
    <section class="section options-risk-cone-section">
      <article class="panel-card options-risk-cone-card">
        ${content}
      </article>
    </section>
  ` : "";
}









function renderOptionsInsightFeed(model) {
  return `
    <section class="section options-insight-feed-section">
      <article class="panel-card options-insight-feed-card">
        <div class="asset-hub-group-heading">
          <div>
            <p class="panel-kicker">AI Market Insights</p>
            <h4>AI 即時洞察</h4>
          </div>
          <span>${model.updatedAt ? escapeHtml(model.updatedAt) : "線上資料同步"}</span>
        </div>
        ${renderOptionsInsightFeedContent(model)}
      </article>
    </section>
  `;
}

function renderOptionsFocusSelector(model, activeKey, keys = null, extraClass = "") {
  const allowed = Array.isArray(keys) && keys.length ? new Set(keys) : null;
  const items = getOptionsFocusItems(model).filter((item) => !allowed || allowed.has(item.key));
  return `
    <div class="options-market-strip ${escapeHtml(extraClass)}">
      ${items.map((item) => `
        <button class="${item.key === activeKey ? "is-active" : ""}" type="button" data-options-focus-key="${escapeHtml(item.key)}" aria-pressed="${item.key === activeKey ? "true" : "false"}">
          <small>${escapeHtml(item.group)}</small>
          <b>${escapeHtml(item.name)}</b>
          <strong>${escapeHtml(item.value || "--")}</strong>
          <em>${escapeHtml(item.pct || "--")}</em>
        </button>
      `).join("")}
    </div>
  `;
}





function renderOptionsHeroMarketPanel(model, activeKey, keys = null) {
  const expanded = false;
  const summaryGroups = buildOptionsRegionalSummary(model.payload);
  const totalCount = summaryGroups.reduce((sum, { group }) => sum + group.items.length, 0);
  const regionalContent = summaryGroups.length ? (expanded ? `
    <div class="asset-hub-region-groups options-hero-region-groups">
      ${summaryGroups.map(({ group, usableCount, key }) => `
        <section class="asset-hub-region-block ${derivativesOptionsSelectedFocus === key ? "is-active" : ""}">
          <div class="asset-hub-region-head">
            <strong>${escapeHtml(group.region)}</strong>
            <small>${usableCount} / ${group.items.length} 筆有效</small>
          </div>
          ${renderOptionsRegionAnalysisQuoteGrid(group.items, key, "選擇權資料同步中。")}
        </section>
      `).join("")}
    </div>
  ` : `
    <div class="asset-hub-region-summary-row options-hero-region-summary">
      ${summaryGroups.map(({ group, usableCount, strongest, key }) => `
        <button class="options-region-focus-card ${derivativesOptionsSelectedFocus === key ? "is-active" : ""}" type="button" data-options-focus-key="${escapeHtml(key)}" aria-pressed="${derivativesOptionsSelectedFocus === key ? "true" : "false"}">
          <b>${escapeHtml(group.region)}</b>
          <small>${usableCount} / ${group.items.length} 筆有效</small>
          <em>${strongest ? `${strongest.symbol || "--"} ${strongest.pct || "--"}` : "資料同步中"}</em>
        </button>
      `).join("")}
    </div>
  `) : '<p class="stock-detail-empty">選擇權資料同步中。</p>';
  return `
    <div class="options-hero-market-panel" id="options-regional-market">
      <section class="options-hero-region-map ${expanded ? "is-expanded" : "is-collapsed"}">
        <div class="asset-hub-group-heading">
          <div>
            <p class="panel-kicker">Options category map</p>
            <h4>選擇權地區市場</h4>
          </div>
          <span>${totalCount} 筆</span>
          <button class="global-refresh asset-hub-region-toggle" type="button" data-asset-region-toggle="options-regional-market" aria-expanded="${expanded ? "true" : "false"}">${expanded ? "收合" : "展開"}</button>
        </div>
        ${regionalContent}
      </section>
    </div>
  `;
}





function renderOptionsCoreModelGrid(model) {
  const maxGapPct = model.maxPainGap !== null && model.atmStrike
    ? Math.abs(model.maxPainGap / model.atmStrike) * 100
    : null;
  const optionLabel = getTaiwanOptionProductLabel(model.chain);
  const modules = [
    ["技術分析模型", model.macroItems.length ? "同步中" : "待跨市場資料", "K 線、EMA、SMA、MACD、RSI、KD、Bollinger、ATR、VWAP 預留為下一層走勢模組。"],
    ["籌碼模型", model.pcr !== null ? "已啟用" : `待 ${optionLabel} 鏈`, `PCR ${optionsDecimal(model.pcr)}，Call / Put OI ${optionsWhole(model.callOi)} / ${optionsWhole(model.putOi)}。`],
    ["波動率模型", model.avgIv !== null || Number.isFinite(model.vixValue) ? "已啟用" : "待 IV / VIX", `VIX ${Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--"}，平均 IV ${optionsPct(model.avgIv)}。`],
    ["總經模型", model.macroItems.length ? "部分啟用" : "待同步", `已載入 ${model.macroItems.length} 組跨市場資料，追蹤美元、利率、黃金、原油與美股。`],
    ["情緒模型", model.volumePcr !== null ? "已啟用" : "待成交量", `Volume PCR ${optionsDecimal(model.volumePcr)}，用來檢查短線交易情緒。`],
    ["事件模型", model.expiryDays !== null ? "已啟用" : "待到期日", model.expiryDays !== null ? `距到期約 ${model.expiryDays} 天，評估 Gamma / Theta 到期風險。` : "尚未取得到期日。"],
  ];
  return `
    <section class="section options-ai-model-section" id="options-cross-validation">
      <article class="panel-card options-terminal-card">
        <div class="asset-hub-group-heading">
          <div>
            <p class="panel-kicker">Cross Validation Engine</p>
            <h4>AI 多模型交叉驗證</h4>
          </div>
          <span>${model.confidenceScore}/100</span>
        </div>
        <div class="options-model-grid">
          ${modules.map(([title, status, text]) => `
            <section>
              <small>${escapeHtml(status)}</small>
              <b>${escapeHtml(title)}</b>
              <p>${escapeHtml(text)}</p>
            </section>
          `).join("")}
        </div>
        <div class="options-output-grid">
          <span><small>支撐區</small><b>${optionsWhole(model.oiWalls.putWall?.strike)}</b><em>最大 Put OI</em></span>
          <span><small>壓力區</small><b>${optionsWhole(model.oiWalls.callWall?.strike)}</b><em>最大 Call OI</em></span>
          <span><small>關鍵履約價</small><b>${optionsWhole(model.atmStrike)}</b><em>平值履約價</em></span>
          <span><small>最大痛點差</small><b>${model.maxPainGap === null ? "--" : `${model.maxPainGap >= 0 ? "+" : ""}${optionsWhole(model.maxPainGap)}`}</b><em>${maxGapPct === null ? "--" : `${maxGapPct.toFixed(2)}%`}</em></span>
        </div>
      </article>
    </section>
  `;
}


function getOptionsChainSourceKey(chain = {}) {
  const primary = String((chain.source || {}).primary || "").toLowerCase();
  if (primary.includes("yahoo")) return "yahoo";
  if (primary.includes("taifex")) return "taifex";
  return derivativesOptionsChainSource || "auto";
}






function getOptionsMarketChainSymbolLabel(chainSymbol = "", item = {}) {
  const sourceSymbol = String(item?.symbol || item?.dataSymbol || "").trim().toUpperCase();
  const symbol = String(chainSymbol || "").trim().toUpperCase();
  if (!symbol) return "線上來源";
  if (symbol.startsWith("DERIBIT_")) return `${sourceSymbol || symbol} Deribit 真實選擇權鏈`;
  if (symbol.startsWith("BYBIT_")) return `${sourceSymbol || symbol} Bybit 真實選擇權鏈`;
  if (OPTIONS_MARKET_CHAIN_FUTURES_SYMBOLS.has(symbol)) return `${sourceSymbol || symbol} 商品期權鏈`;
  if (sourceSymbol && symbol !== sourceSymbol) return `${symbol} 官方選擇權 root`;
  return `${symbol} 真實選擇權鏈`;
}

























function renderOptionsDecisionBrief(model) {
  const strategies = buildOptionsStrategyRows(model);
  const topStrategy = strategies[0] || null;
  const putWall = model.oiWalls.putWall?.strike;
  const callWall = model.oiWalls.callWall?.strike;
  const skew = model.maxIv !== null && model.minIv !== null ? model.maxIv - model.minIv : null;
  const vixText = Number.isFinite(model.vixValue) ? model.vixValue.toFixed(2) : "--";
  const expiryText = model.expiryDays === null ? "待同步" : `${model.expiryDays} 天`;
  const directionText = model.direction === "偏多"
    ? "多方訊號略占優勢，但仍需確認壓力區是否被有效突破。"
    : model.direction === "偏空"
      ? "避險與下檔風險較需要優先管理，追價前先確認 Put OI 與 VIX 是否續升。"
      : "盤面較偏區間震盪，策略重點放在波動率、時間價值與區間邊界。";
  const actionRows = [
    ["方向確認", model.direction === "震盪" ? "等待支撐或壓力區被有效突破，再提高方向性策略權重。" : `維持 ${model.direction} 觀察，但需用 OI 牆與 VIX 交叉確認。`],
    ["價位邊界", `下方觀察 ${optionsWhole(putWall)}，上方觀察 ${optionsWhole(callWall)}；價格接近邊界時降低追價。`],
    ["波動控管", `VIX ${vixText}、平均 IV ${optionsPct(model.avgIv)}，若 IV 快速擴張，優先檢查權利金成本。`],
    ["資料狀態", `TXO ${model.rows.length ? `${model.rows.length} 檔` : "同步中"}，跨市場 ${model.macroItems.length ? `${model.macroItems.length} 組` : "同步中"}，信心 ${model.confidenceScore}/100。`],
  ];
  return `
    <section class="section options-decision-brief" id="options-decision-brief">
      <article class="panel-card options-terminal-card">
        <div class="asset-hub-group-heading">
          <div>
            <p class="panel-kicker">AI Decision Brief</p>
            <h4>AI 決策摘要</h4>
          </div>
          <span>${escapeHtml(model.riskLight.label)} · ${model.riskScore}/100</span>
        </div>
        <div class="options-brief-lead is-${model.riskLight.tone}">
          <div>
            <small>核心結論</small>
            <strong>${escapeHtml(model.direction)} · ${escapeHtml(model.primaryRisk)}</strong>
            <p>${escapeHtml(directionText)}</p>
          </div>
          <div class="options-brief-score">
            <span><b>${model.probabilities.bullish}%</b><small>多方</small></span>
            <span><b>${model.probabilities.bearish}%</b><small>空方</small></span>
            <span><b>${model.probabilities.range}%</b><small>震盪</small></span>
          </div>
        </div>
        <div class="options-brief-grid">
          <section>
            <small>關鍵價位</small>
            <b>${optionsWhole(putWall)} / ${optionsWhole(callWall)}</b>
            <p>Put OI 支撐與 Call OI 壓力為主要觀察邊界，ATM ${optionsWhole(model.atmStrike)}，最大痛點 ${optionsWhole(model.maxPain)}。</p>
          </section>
          <section>
            <small>波動結構</small>
            <b>VIX ${escapeHtml(vixText)}</b>
            <p>平均 IV ${optionsPct(model.avgIv)}，Skew ${optionsPct(skew)}，距到期 ${escapeHtml(expiryText)}；到期越近，Gamma 與 Theta 權重越高。</p>
          </section>
          <section>
            <small>策略排序</small>
            <b>${escapeHtml(topStrategy?.name || "--")}</b>
            <p>${topStrategy ? `${topStrategy.score}/100，${topStrategy.evidence}` : "等待鏈資料、IV 與跨市場資料完成同步。"}</p>
          </section>
          <section>
            <small>風控原則</small>
            <b>${escapeHtml(model.riskLight.text)}</b>
            <p>${model.riskScore >= 66 ? "先限制槓桿與裸賣部位，再評估方向性交易。" : "可觀察策略適配度，但仍需用支撐壓力與波動率確認。"}</p>
          </section>
        </div>
        <ul class="options-brief-actions">
          ${actionRows.map(([title, text]) => `<li><b>${escapeHtml(title)}</b><span>${escapeHtml(text)}</span></li>`).join("")}
        </ul>
      </article>
    </section>
  `;
}


function renderOptionsUsChainCard(chain = {}) {
  return "";
  const selectedSymbol = String(chain.symbol || "SPY").toUpperCase();
  const callOi = Number(chain.summary?.callOpenInterest) || 0;
  const putOi = Number(chain.summary?.putOpenInterest) || 0;
  const putCallRatio = callOi > 0 ? putOi / callOi : null;
  return `
    <article class="panel-card asset-option-chain-card">
      <div class="asset-hub-group-heading">
        <div><p class="panel-kicker">US option chain</p><h4>${escapeHtml(selectedSymbol)} 公開選擇權鏈</h4></div>
        <span>${escapeHtml(formatAssetHubExpiration(chain.selectedExpiration))}</span>
      </div>
      <div class="tw-option-expiry-tabs" aria-label="美股選擇權標的切換">
        ${ASSET_HUB_OPTION_CHAIN_UNDERLYINGS.map(([symbol, label]) => `<button class="${symbol === selectedSymbol ? "is-active" : ""}" type="button" data-asset-option-underlying="${symbol}"><b>${symbol}</b><small>${escapeHtml(label)}</small></button>`).join("")}
      </div>
      <div class="asset-option-chain-stats">
        <span><b>${chain.summary?.callCount ?? "--"}</b><small>Call 檔數</small></span>
        <span><b>${chain.summary?.putCount ?? "--"}</b><small>Put 檔數</small></span>
        <span><b>${putCallRatio === null ? "--" : putCallRatio.toFixed(2)}</b><small>Put / Call OI</small></span>
      </div>
      ${chain.error
        ? `<p class="stock-theory-note">公開選擇權鏈暫不可用：${escapeHtml(chain.error)}</p>`
        : `<div class="asset-option-contract-grid">${renderAssetHubOptionContracts(chain.calls, "Call OI 前五檔", "call")}${renderAssetHubOptionContracts(chain.puts, "Put OI 前五檔", "put")}</div>`}
    </article>
  `;
}


function renderDerivativeAssetSummarySection(payload, title, label, description, href) {
  return `
    <section class="section asset-hub-section">
      ${renderAssetHubSummary(payload, title, label, description, href)}
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
    const initialLimit = ["precious-metals", "bonds", "futures", "options"].includes(category)
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












function renderFuturesBacktestLearningCard(technicalTheory) {
  return renderUsBacktestLearningCard(technicalTheory, {
    targetLabel: "期貨價格",
    priceTargetTitle: "預估期貨價格區間",
    frameworkKicker: "Futures native multi-factor",
    frameworkTitle: "期貨原生多因子回溯統整",
    frameworkStateLabel: "契約狀態",
    factorSubtitle: "以契約 K 線、成交量、未平倉量代理、趨勢面與進出場訊號分層驗證。",
    extraDecisionTips: [
      "期貨預估區間以契約價格點數呈現，實際損益需再換算商品乘數、跳動點價值與保證金。",
      "轉倉、近遠月價差與流動性變化會影響模型有效性，不能只看單一技術訊號。",
    ],
    finalNote: "期貨回測只作訊號校準與風險管理參考，不保證未來價格走勢；實際交易需另行換算商品乘數、跳動點價值、保證金、期交稅、手續費、滑價與轉倉成本。",
  });
}














function removeUsWatchlistSymbol(symbol) {
  const cleanSymbol = String(symbol || "").trim().toUpperCase();
  const items = getUsWatchlist().filter((item) => String(item.symbol).toUpperCase() !== cleanSymbol);
  saveUsWatchlist(items);
  renderUsWatchlist();
  setText("us-watchlist-status", `${cleanSymbol} 已從美股自選股移除。`);
}













async function loadUsWatchlistSymbol(symbol) {
  const cleanSymbol = String(symbol || "").trim().toUpperCase();
  if (!cleanSymbol) return;
  setText("us-watchlist-status", `正在載入 ${cleanSymbol} 線上資料...`);
  try {
    const response = await fetchWithTimeout(`/api/us-market/symbol/${encodeURIComponent(cleanSymbol)}`, { cache: "no-store" }, 18000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const item = await response.json();
    renderUsMarketDetailTo("us-watchlist-detail", item);
    upsertUsWatchlistSymbol(item);
    setText("us-watchlist-status", `${cleanSymbol} 已更新，資料來源 Yahoo Finance。`);
    if (window.location.hash !== "#alerts") window.history.replaceState({}, "", `${window.location.pathname}#alerts`);
  } catch (error) {
    renderUsMarketDetailTo("us-watchlist-detail", { error: error.message || String(error) });
    setText("us-watchlist-status", `${cleanSymbol} 資料載入失敗。`);
  }
}

async function runUsWatchlistSearch(query) {
  const keyword = String(query || "").trim();
  if (!keyword) {
    renderUsWatchlistSearchResults([]);
    setText("us-watchlist-status", "請輸入美股或 ETF 代號 / 名稱。");
    return;
  }
  setText("us-watchlist-status", `正在搜尋 ${keyword}...`);
  try {
    const response = await fetchWithTimeout(`/api/us-market/search?q=${encodeURIComponent(keyword)}`, { cache: "no-store" }, 16000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    renderUsWatchlistSearchResults(payload.results || []);
    setText("us-watchlist-status", `列出 ${payload.count || 0} 筆美股 / ETF，可加入自選股。`);
  } catch (error) {
    renderUsWatchlistSearchResults([]);
    setText("us-watchlist-status", "美股搜尋失敗，請稍後再試。");
    console.error("Failed to search US watchlist:", error);
  }
}


function renderAssetHubFallbackPage(payloads = []) {
  const root = document.getElementById("asset-hub-root");
  if (!root) return;
  const availablePayloads = payloads.filter(Boolean);
  const cards = [
    ["期貨", "Futures", "futures", "觀察股指、能源、金屬與波動率期貨，作為風險偏好與隔夜方向參考。"],
    ["選擇權", "Options", "options", "整合 VIX、SPY、QQQ、IWM 等標的，搭配波動率與策略風險判斷。"],
    ["貴金屬", "Precious Metals", "precious-metals", "追蹤黃金、白銀、鉑金與鈀金，判斷避險與美元利率影響。"],
    ["債券", "Bonds", "bonds", "觀察美債殖利率、債券 ETF 與久期風險，輔助資產配置。"],
  ];
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">Futures, Options & Finance</p>
      <h1>期權、貴金屬與債券中心</h1>
      <p class="hero-text">期權頁集中期貨、選擇權與未平倉；貴金屬與債券頁集中債券、殖利率曲線與貴金屬。</p>
    </section>

    <section class="section us-platform-section">
      <article class="panel-card us-platform-dashboard">
        <div class="us-platform-head">
          <p class="eyebrow">Card 5 Structure</p>
          <h2>跨資產風險與避險架構</h2>
          <p>先看風險資產方向，再用波動率、金屬與債券確認市場情緒，避免只用單一市場判斷。</p>
        </div>
        <div class="us-module-grid asset-hub-module-grid">
          ${cards.map(([title, en, category, desc], index) => {
            const payload = availablePayloads.find((item) => item.category === category);
            const summary = payload?.summary || {};
            return `
              <a class="us-module-card is-${["blue", "purple", "gold", "green"][index]}" href="${safeUrl(`#asset-${category}`)}">
                <span class="us-module-number">${index + 1}</span>
                <div>
                  <strong>${escapeHtml(title)}</strong>
                  <small>${escapeHtml(en)}</small>
                </div>
                <p>${escapeHtml(desc)}</p>
                <div class="us-module-tags">
                  <span>${escapeHtml(summary.count ?? "--")} 檔</span>
                  <span>平均 ${escapeHtml(summary.avgPct || "--")}</span>
                  <span>最強 ${escapeHtml(summary.strongest || "--")}</span>
                </div>
              </a>
            `;
          }).join("")}
        </div>
        <div class="us-support-grid">
          <section>
            <h3>美股 / ETF 全上市資料</h3>
            <div>
              <span>Nasdaq Trader Symbol Directory</span>
              <span>NYSE Listings Directory</span>
              <span>Yahoo Finance 行情補充</span>
            </div>
          </section>
          <section>
            <h3>衍生與跨資產資料</h3>
            <div>
              <span>Yahoo Futures</span>
              <span>Yahoo Options Chain</span>
              <span>CBOE VIX 代理</span>
              <span>債券 ETF</span>
              <span>金屬 ETF</span>
            </div>
          </section>
        </div>
      </article>
    </section>

    ${availablePayloads.map((payload) => `
      <section class="section" id="asset-${escapeHtml(payload.category || "")}">
        <article class="panel-card global-summary-card">
          <div class="card-title-row">
            <div>
              <p class="panel-kicker">${escapeHtml(getAssetPlatformConfig(payload.category, payload.title).kicker || "Asset")}</p>
              <h3>${escapeHtml(payload.title || "跨資產資料")}</h3>
            </div>
            <a class="global-refresh" href="${safeUrl(`${payload.category}.html`)}">開啟單頁</a>
          </div>
          <div class="global-summary-grid">
            <span><b>${payload.summary?.count ?? "--"}</b><small>有效商品</small></span>
            <span><b>${payload.summary?.advancers ?? "--"} / ${payload.summary?.decliners ?? "--"}</b><small>上漲 / 下跌</small></span>
            <span><b>${escapeHtml(payload.summary?.avgPct || "--")}</b><small>平均漲跌幅</small></span>
            <span><b>${escapeHtml(payload.summary?.strongest || "--")}</b><small>最強</small></span>
          </div>
          <p class="global-insight">${escapeHtml(buildGlobalMarketInsight(payload))}</p>
        </article>
        ${renderGlobalMarketSections(payload.items || [])}
      </section>
    `).join("")}
  `;
}

function getAssetHubItems(payload) {
  return Array.isArray(payload?.items) ? payload.items : [];
}

function getAssetHubUsableItems(payload) {
  return getAssetHubItems(payload).filter((item) => !item?.error && Number.isFinite(parseMarketNumber(item?.close)));
}

function findAssetHubItem(payload, symbol) {
  return getAssetHubItems(payload).find((item) => String(item?.symbol || "").toUpperCase() === String(symbol || "").toUpperCase()) || null;
}

function filterAssetHubItems(payload, predicate, limit = 12) {
  return getAssetHubUsableItems(payload).filter(predicate).slice(0, limit);
}


function assetHubDirection(payload) {
  const summary = payload?.summary || {};
  if ((summary.advancers || 0) > (summary.decliners || 0)) return "上漲商品較多，短線風險偏好較穩。";
  if ((summary.advancers || 0) < (summary.decliners || 0)) return "下跌商品較多，留意避險與波動升溫。";
  return "多空商品數接近，市場仍在等待下一個方向。";
}

function getAssetHubRegion(item = {}) {
  const region = String(item.region || item.market || "").trim();
  if (!region) return "全球 / 其他";
  if (region.includes("台") || region.toLowerCase() === "taiwan") return "台灣";
  if (region.includes("美") || region.toLowerCase().includes("united states") || region.toLowerCase() === "us") return "美國";
  if (region.includes("歐") || region.toLowerCase().includes("europe")) return "歐洲";
  if (region.includes("亞") || region.includes("日本") || region.includes("香港") || region.includes("新加坡")) return "亞洲";
  return region;
}

function getAssetHubItemUrl(item = {}) {
  return item.sourceLink || item.sourceUrl || buildYahooFinanceUrl(item.dataSymbol || item.symbol);
}

function getAssetHubMetric(item = {}) {
  const label = item.metricLabel || "成交量";
  const value = label === "未平倉量" ? item.openInterest || item.close : item.volume;
  return { label, value };
}

function groupAssetHubItemsByRegion(items = []) {
  const groups = new Map();
  items.forEach((item) => {
    const region = getAssetHubRegion(item);
    if (!groups.has(region)) groups.set(region, []);
    groups.get(region).push(item);
  });
  const ordered = ASSET_HUB_REGION_ORDER.filter((region) => groups.has(region));
  ordered.push(...Array.from(groups.keys()).filter((region) => !ordered.includes(region)).sort((a, b) => a.localeCompare(b, "zh-Hant")));
  return ordered.map((region) => ({ region, items: groups.get(region) || [] }));
}

function renderAssetHubRegionChips(payload) {
  const regions = Array.isArray(payload?.regionBreakdown) ? payload.regionBreakdown : [];
  if (!regions.length) return "";
  return `
    <div class="asset-hub-region-chips" aria-label="地區資料覆蓋">
      ${regions.map((item) => `<span><b>${escapeHtml(item.region || "--")}</b>${Number(item.usable || 0)} / ${Number(item.total || 0)} 筆</span>`).join("")}
    </div>
  `;
}

function renderAssetHubSchemaPanel(payloads = []) {
  const payloadSchema = payloads.find((payload) => payload?.macroSchema)?.macroSchema || {};
  const schema = {
    ...ASSET_HUB_SCHEMA_FALLBACK,
    ...payloadSchema,
    sources: Array.isArray(payloadSchema.sources) && payloadSchema.sources.length ? payloadSchema.sources : ASSET_HUB_SCHEMA_FALLBACK.sources,
    tables: Array.isArray(payloadSchema.tables) && payloadSchema.tables.length ? payloadSchema.tables : ASSET_HUB_SCHEMA_FALLBACK.tables,
    dashboardSignals: Array.isArray(payloadSchema.dashboardSignals) && payloadSchema.dashboardSignals.length ? payloadSchema.dashboardSignals : ASSET_HUB_SCHEMA_FALLBACK.dashboardSignals,
    automation: payloadSchema.automation || ASSET_HUB_SCHEMA_FALLBACK.automation,
  };
  const categories = new Set(payloads.map((payload) => payload?.category).filter(Boolean));
  const isDerivativesOnly = categories.has("futures") || categories.has("options");
  const isFinanceOnly = categories.has("precious-metals") || categories.has("bonds");
  let sources = Array.isArray(schema.sources) ? schema.sources : [];
  let tables = Array.isArray(schema.tables) ? schema.tables : [];
  let signals = Array.isArray(schema.dashboardSignals) ? schema.dashboardSignals : [];
  if (isDerivativesOnly && !isFinanceOnly) {
    sources = sources.filter((item) => /Bloomberg|LSEG|FactSet|TAIFEX|CME|ICE|Eurex|SGX|OCC|Cboe/i.test(item.name || ""));
    tables = tables.filter((item) => ["futures_master", "options_chain", "macro_indicator", "fx_rates"].includes(item.name));
    signals = signals.filter((item) => ["DXY", "VIX", "Global Futures"].includes(item));
  } else if (isFinanceOnly && !isDerivativesOnly) {
    sources = sources.filter((item) => /Bloomberg|LSEG|FactSet|Morningstar|S&P Global|U\.S\. Treasury|FRED|LBMA|COMEX/i.test(item.name || ""));
    tables = tables.filter((item) => ["bond_master", "bond_yield_history", "rating_history", "macro_indicator", "fx_rates"].includes(item.name));
    signals = signals.filter((item) => ["Yield Curve", "Credit Spread", "DXY", "Gold / Silver Ratio", "Central Bank Rates"].includes(item));
  }
  if (!sources.length) sources = ASSET_HUB_SCHEMA_FALLBACK.sources.slice(0, 2);
  if (!tables.length) tables = ASSET_HUB_SCHEMA_FALLBACK.tables.slice(0, 3);
  if (!signals.length) signals = ASSET_HUB_SCHEMA_FALLBACK.dashboardSignals.slice(0, 3);
  return `
    <section id="asset-source-architecture" class="section asset-hub-schema-section">
      <article class="panel-card asset-hub-schema-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">Global Macro data architecture</p>
            <h3>資料庫與官方來源架構</h3>
          </div>
          <span class="chip chip-gold">Docx spec</span>
        </div>
        <div class="asset-hub-schema-grid">
          <section>
            <h4>官方與機構來源</h4>
            <div class="asset-hub-source-stack">
              ${sources.map((item) => `<span><b>${escapeHtml(item.name || "--")}</b><small>${escapeHtml(item.role || "")}</small></span>`).join("")}
            </div>
          </section>
          <section>
            <h4>資料表</h4>
            <div class="asset-hub-table-tags">
              ${tables.map((item) => `<span><b>${escapeHtml(item.name || "--")}</b><small>${escapeHtml(item.label || "")}</small></span>`).join("")}
            </div>
          </section>
          <section>
            <h4>Dashboard 指標</h4>
            <div class="asset-hub-signal-tags">
              ${signals.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
            </div>
            <p>${escapeHtml(schema.automation || "API、ETL、資料庫與異常監控流程。")}</p>
          </section>
        </div>
      </article>
    </section>
  `;
}

function renderAssetHubRegionalGroups(payload, title, predicate = () => true, emptyText = "目前沒有可用線上行情。", options = {}) {
  const items = getAssetHubItems(payload).filter(predicate);
  const groups = groupAssetHubItemsByRegion(items);
  if (!groups.length) return `<article class="panel-card asset-hub-region-card"><p class="stock-detail-empty">${escapeHtml(emptyText)}</p></article>`;
  const collapsible = Boolean(options.collapsible);
  const expanded = !collapsible || Boolean(options.expanded);
  const toggleKey = options.toggleKey || String(title || "regional-market").toLowerCase().replace(/\s+/g, "-");
  const summaryGroups = groups.map((group) => {
    const usableCount = group.items.filter((item) => !item.error && Number.isFinite(parseMarketNumber(item.close))).length;
    const strongest = group.items
      .map((item) => ({ item, pct: parseMarketNumber(item?.pct) }))
      .filter((entry) => Number.isFinite(entry.pct))
      .sort((left, right) => right.pct - left.pct)[0]?.item || null;
    return { group, usableCount, strongest };
  });
  return `
    <article class="panel-card asset-hub-region-card asset-hub-group-card-wide ${collapsible ? "is-collapsible" : ""} ${expanded ? "is-expanded" : "is-collapsed"}">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Regional market map</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
        <span>${items.length} 筆</span>
        ${collapsible ? `<button class="global-refresh asset-hub-region-toggle" type="button" data-asset-region-toggle="${escapeHtml(toggleKey)}" aria-expanded="${expanded ? "true" : "false"}">${expanded ? "收合" : "展開"}</button>` : ""}
      </div>
      ${collapsible && !expanded ? `
        <div class="asset-hub-region-summary-row">
          ${summaryGroups.map(({ group, usableCount, strongest }) => `
            <span>
              <b>${escapeHtml(group.region)}</b>
              <small>${usableCount} / ${group.items.length} 筆有效</small>
              <em>${strongest ? `${strongest.symbol || "--"} ${strongest.pct || "--"}` : "等待同步"}</em>
            </span>
          `).join("")}
        </div>
      ` : `
        <div class="asset-hub-region-groups">
          ${summaryGroups.map(({ group, usableCount }) => `
            <section class="asset-hub-region-block">
              <div class="asset-hub-region-head">
                <strong>${escapeHtml(group.region)}</strong>
                <small>${usableCount} / ${group.items.length} 筆有效</small>
              </div>
              ${renderAssetHubQuoteGrid(group.items, emptyText)}
            </section>
          `).join("")}
        </div>
      `}
    </article>
  `;
}

function renderAssetHubQuoteGrid(items = [], emptyText = "目前沒有可用線上行情。") {
  if (!items.length) return `<p class="stock-detail-empty">${escapeHtml(emptyText)}</p>`;
  return `
    <div class="asset-quote-grid">
      ${items.map((item) => {
        const metric = getAssetHubMetric(item);
        return `
          <a class="asset-quote-card" href="${safeUrl(getAssetHubItemUrl(item))}" target="_blank" rel="noopener noreferrer">
            <span class="asset-quote-type">${escapeHtml(getAssetHubRegion(item))} · ${escapeHtml(item.type || item.group || "市場商品")}</span>
            <strong>${escapeHtml(item.name || "--")}</strong>
            <small>${escapeHtml(item.symbol || "--")} · ${escapeHtml(item.exchange || item.dataSource || "--")} · ${escapeHtml(item.date || "--")}</small>
            ${item.error ? `<p class="asset-quote-error">同步中：${escapeHtml(item.error)}</p>` : `
              <div class="asset-quote-price">
                <b>${formatGlobalValue(item.close)}</b>
                <em class="${assetHubTone(item)}">${escapeHtml(item.pct || "--")}</em>
              </div>
              <footer>${escapeHtml(metric.label)} <b>${formatGlobalVolume(metric.value)}</b></footer>
            `}
          </a>
        `;
      }).join("")}
    </div>
  `;
}

function renderAssetHubSummary(payload, title, label, description, href) {
  const summary = payload?.summary || {};
  const usable = getAssetHubUsableItems(payload);
  const validation = payload?.validation || {};
  const catalogCount = Number(payload?.catalogCount) || getAssetHubItems(payload).length;
  const loadedCount = Number(payload?.loadedCount) || getAssetHubItems(payload).length;
  const verifiedCount = Number(validation.verifiedCount) || 0;
  const secondaryText = validation.secondaryMatchedCount
    ? `；第二來源比對 ${validation.secondaryMatchedCount} 筆一致`
    : "";
  const referenceLink = validation.referenceUrl
    ? ` <a class="asset-hub-source-link" href="${safeUrl(validation.referenceUrl)}" target="_blank" rel="noopener noreferrer">查看參考來源</a>`
    : "";
  const nextLimit = Math.min(loadedCount + 24, catalogCount);
  const loadMoreButton = loadedCount < catalogCount
    ? `<button class="global-refresh asset-hub-load-more" type="button" data-asset-load-more="${escapeHtml(payload?.category || "")}" data-asset-load-limit="${nextLimit}">載入更多已驗證行情</button>`
    : "";
  return `
    <article class="panel-card asset-hub-summary-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">${escapeHtml(label)}</p>
          <h3>${escapeHtml(title)}</h3>
          <p class="chart-subtitle">${escapeHtml(description)}</p>
        </div>
        <div class="asset-hub-summary-actions">${loadMoreButton}<a class="global-refresh" href="${safeUrl(href)}">開啟單頁</a></div>
      </div>
      <div class="asset-hub-stat-grid">
        <span><b>${verifiedCount} / ${loadedCount} / ${catalogCount}</b><small>驗證 / 載入 / 目錄</small></span>
        <span><b>${summary.advancers ?? 0} / ${summary.decliners ?? 0}</b><small>上漲 / 下跌</small></span>
        <span><b>${escapeHtml(summary.avgPct || "--")}</b><small>平均漲跌幅</small></span>
        <span><b>${escapeHtml(summary.strongest || "--")}</b><small>最強標的</small></span>
      </div>
      ${renderAssetHubRegionChips(payload)}
      <p class="asset-hub-insight">${escapeHtml(assetHubDirection(payload))} 主來源：${escapeHtml(validation.primary || payload?.source || "Yahoo Finance")}；參考來源：${escapeHtml(validation.reference || "--")}${escapeHtml(secondaryText)}。更新時間 ${escapeHtml(payload?.updatedAt || "--")}${referenceLink}</p>
    </article>
  `;
}

function renderAssetHubOnlineRows(items = []) {
  return items.map((item) => {
    const metric = getAssetHubMetric(item);
    return `
      <tr>
        <td><a class="global-market-link" href="${safeUrl(getAssetHubItemUrl(item))}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.name || "--")}</a></td>
        <td>${escapeHtml(item.symbol || "--")}</td>
        <td>${escapeHtml(getAssetHubRegion(item))}</td>
        <td>${escapeHtml(item.exchange || item.dataSource || "--")}</td>
        <td>${escapeHtml(item.type || item.group || "--")}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.close)}</td>
        <td class="${assetHubTone(item)}">${escapeHtml(item.error ? "同步中" : item.pct || "--")}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.open)}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.high)}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.low)}</td>
        <td><span class="asset-table-metric">${escapeHtml(metric.label)}</span>${item.error ? "--" : formatGlobalVolume(metric.value)}</td>
        <td>${escapeHtml(item.date || "--")}</td>
      </tr>
    `;
  }).join("");
}

function renderAssetHubOnlineTable(payload, title) {
  const items = getAssetHubItems(payload);
  return `
    <article class="panel-card asset-hub-online-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">Online data</p>
          <h4>${escapeHtml(title)}線上資料明細</h4>
        </div>
        <span class="chip chip-blue">載入 ${items.length} / 目錄 ${payload?.catalogCount || items.length} 筆</span>
      </div>
      <div class="global-table-wrap">
        <table class="global-market-table">
          <thead><tr><th>名稱</th><th>代號</th><th>地區</th><th>交易所 / 來源</th><th>分類</th><th>收盤</th><th>漲跌幅</th><th>開盤</th><th>最高</th><th>最低</th><th>量能欄位</th><th>日期</th></tr></thead>
          <tbody>${renderAssetHubOnlineRows(items) || '<tr><td colspan="12">目前沒有資料。</td></tr>'}</tbody>
        </table>
      </div>
    </article>
  `;
}

function renderAssetHubFutures(payload) {
  const leader = getAssetHubUsableItems(payload).sort((a, b) => (parseMarketNumber(b.pct) || -Infinity) - (parseMarketNumber(a.pct) || -Infinity))[0];
  const sourceInfo = payload?.sourceInfo || {};
  return `
    <section class="section asset-hub-section" id="asset-futures">
      ${renderAssetHubSummary(payload, "期貨市場", "Futures", "以股指、利率、能源與商品期貨觀察隔夜方向、通膨壓力與風險轉移。", "futures.html")}
      <div class="asset-hub-layout asset-hub-futures-layout">
        <article class="panel-card asset-hub-risk-card"><p class="panel-kicker">Overnight signal</p><h4>隔夜市場脈絡</h4><strong>${escapeHtml(leader?.name || "等待資料")}</strong><p>${leader ? `${leader.name} ${leader.pct || "--"}，可搭配股指期貨、美債期貨與台指期貨未平倉確認風險偏好。` : "等待 Yahoo Finance 與 TAIFEX 同步後，將呈現最強期貨與跨市場判讀。"}</p><small>期貨具槓桿與到期特性，請搭配保證金與停損管理。</small></article>
        <article class="panel-card asset-hub-source-card"><p class="panel-kicker">Source routing</p><h4>期貨資料來源</h4><ul><li>台灣：TAIFEX 官方期貨日報，呈現 TX 未平倉量。</li><li>美國：CME / CBOT / NYMEX / COMEX 期貨，以 Yahoo Finance 日線行情同步。</li><li>其他國家：ICE Europe、匯率與商品期貨作跨市場參考。</li></ul><a class="asset-hub-source-link" href="${safeUrl(sourceInfo.referenceUrl || "https://www.cmegroup.com/markets.html")}" target="_blank" rel="noopener noreferrer">參考合約來源</a></article>
        ${renderAssetHubTaiwanFuturesCard(payload)}
        ${renderAssetHubRegionalGroups(payload, "期貨地區市場", () => true, "期貨資料同步中。")}
      </div>
      ${renderAssetHubOnlineTable(payload, "期貨")}
    </section>
  `;
}

function renderAssetHubTaiwanFuturesCard(payload) {
  const symbols = ["TX", "MTX", "TMF", "TE", "TF"];
  const contracts = symbols.map((symbol) => findAssetHubItem(payload, symbol)).filter(Boolean);
  return `
    <article class="panel-card asset-option-chain-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">TAIFEX futures</p>
          <h4>國內期貨未平倉資料</h4>
        </div>
        <span>官方日報</span>
      </div>
      ${contracts.length ? `<div class="asset-option-chain-stats tw-option-stats">
        ${contracts.map((item) => `<span><b>${formatAssetOptionWhole(item.openInterest || item.close)}</b><small>${escapeHtml(item.symbol)} · ${escapeHtml(item.pct || "--")}</small></span>`).join("")}
      </div>
      <p class="stock-theory-note">${contracts.map((item) => `${item.symbol} ${item.date || "--"}`).join(" · ")}；資料為 TAIFEX 一般交易時段未沖銷契約量，並非價格推估。</p>` : '<p class="stock-detail-empty">TAIFEX 期貨未平倉資料同步中。</p>'}
    </article>
  `;
}


function renderAssetHubOptionContracts(contracts = [], title, tone) {
  const ranked = [...contracts].sort((left, right) => (Number(right.openInterest) || 0) - (Number(left.openInterest) || 0)).slice(0, 5);
  return `
    <section class="asset-option-side is-${tone}">
      <h5>${escapeHtml(title)}</h5>
      ${ranked.length ? `<div class="asset-option-rows">${ranked.map((item) => `
        <div><span>${formatGlobalValue(item.strike)}</span><strong>${formatGlobalVolume(item.openInterest)}</strong><small>IV ${Number.isFinite(Number(item.impliedVolatility)) ? `${(Number(item.impliedVolatility) * 100).toFixed(1)}%` : "--"}</small></div>
      `).join("")}</div>` : '<p class="stock-detail-empty">選擇權鏈資料暫時無法取得。</p>'}
    </section>
  `;
}

function renderAssetHubPublicOptionChainCard(chain = {}) {
  const selectedSymbol = String(chain.symbol || "SPY").toUpperCase();
  const callOi = Number(chain.summary?.callOpenInterest) || 0;
  const putOi = Number(chain.summary?.putOpenInterest) || 0;
  const putCallRatio = callOi > 0 ? putOi / callOi : null;
  return `
    <article class="panel-card asset-option-chain-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">US option chain</p>
          <h4>${escapeHtml(selectedSymbol)} 公開選擇權鏈摘要</h4>
        </div>
        <span>${escapeHtml(formatAssetHubExpiration(chain.selectedExpiration))}</span>
      </div>
      <div class="tw-option-expiry-tabs" aria-label="美股選擇權標的切換">
        ${ASSET_HUB_OPTION_CHAIN_UNDERLYINGS.map(([symbol, label]) => `<button class="${symbol === selectedSymbol ? "is-active" : ""}" type="button" data-asset-option-underlying="${symbol}"><b>${symbol}</b><small>${escapeHtml(label)}</small></button>`).join("")}
      </div>
      <div class="asset-option-chain-stats">
        <span><b>${chain.summary?.callCount ?? "--"}</b><small>Call 契約</small></span>
        <span><b>${chain.summary?.putCount ?? "--"}</b><small>Put 契約</small></span>
        <span><b>${putCallRatio === null ? "--" : putCallRatio.toFixed(2)}</b><small>Put / Call OI</small></span>
      </div>
      ${chain.error
        ? '<p class="stock-theory-note">公開選擇權鏈暫時無法取得；保留 VIX、SKEW 與主要選擇權標的即時行情，不以推估資料替代。</p>'
        : `<div class="asset-option-contract-grid">${renderAssetHubOptionContracts(chain.calls, "Call OI 前五檔", "call")}${renderAssetHubOptionContracts(chain.puts, "Put OI 前五檔", "put")}</div><p class="stock-theory-note">Open Interest 為當期未平倉量，不等同交易方向；請連同到期日、履約價、隱含波動率與風險承受度判讀。</p>`}
    </article>
  `;
}




function pickTaiwanOptionRows(chain = [], atmStrike = null, maxRows = 18) {
  const ordered = [...chain].sort((left, right) => Number(left.strike) - Number(right.strike));
  if (ordered.length <= maxRows) return ordered;
  const anchor = Number(atmStrike);
  const anchorIndex = Number.isFinite(anchor)
    ? Math.max(0, ordered.findIndex((item) => Number(item.strike) === anchor))
    : Math.floor(ordered.length / 2);
  const start = Math.max(0, Math.min(ordered.length - maxRows, anchorIndex - Math.floor(maxRows / 2)));
  return ordered.slice(start, start + maxRows);
}

function getTaiwanOptionExpiryPrefix(data = {}) {
  const active = getActiveTaiwanOptionUnderlying(data);
  const fallback = { TXO: "台指", MXO: "小台", TFO: "金指", TEO: "電指", T50O: "臺灣50" }[active] || active;
  const label = String(getTaiwanOptionProductLabel(data) || "").trim();
  return label.replace(/選擇權$/, "").replace(/選$/, "") || fallback;
}

function formatTaiwanOptionExpiryCode(code) {
  const text = String(code || "").trim().toUpperCase();
  const match = text.match(/^20(\d{2})(\d{2})(?:([FW])(\d+))?$/);
  if (!match) return text || "--";
  const [, year, month, marker, week] = match;
  return marker && week ? `${week}${marker}${year}${month}` : `${year}${month}`;
}

function formatTaiwanOptionExpiryLabel(item = {}, data = {}) {
  return `${getTaiwanOptionExpiryPrefix(data)}${formatTaiwanOptionExpiryCode(item.code)}`;
}

function renderTaiwanOptionExpiryTabs(data = {}) {
  const expirations = Array.isArray(data.expirations) ? data.expirations.slice(0, 10) : [];
  if (!expirations.length) return "";
  const selected = data.selectedExpiry || expirations[0]?.code || "";
  const optionLabel = getTaiwanOptionProductLabel(data);
  return `
    <div class="tw-option-expiry-select" aria-label="${escapeHtml(optionLabel)}到期月份切換">
      <select data-tw-option-expiry-select aria-label="${escapeHtml(optionLabel)}到期月份">
        ${expirations.map((item) => `
          <option value="${escapeHtml(item.code || "")}" ${item.code === selected ? "selected" : ""}>
            ${escapeHtml(formatTaiwanOptionExpiryLabel(item, data))}
          </option>
        `).join("")}
      </select>
    </div>
  `;
}

function renderTaiwanOptionChainTable(data = {}) {
  const summary = data.summary || {};
  const rows = pickTaiwanOptionRows(data.chain || [], summary.atmStrike, 20);
  if (!rows.length) return '<p class="stock-detail-empty">TAIFEX 選擇權鏈資料同步中。</p>';
  return `
    <div class="tw-option-chain-scroll">
      <table class="global-market-table tw-option-chain-table">
        <thead>
          <tr>
            <th colspan="4">Call 買權</th>
            <th>履約價</th>
            <th colspan="4">Put 賣權</th>
          </tr>
          <tr>
            <th>成交</th>
            <th>買 / 賣</th>
            <th>量 / OI</th>
            <th>IV</th>
            <th>Strike</th>
            <th>成交</th>
            <th>買 / 賣</th>
            <th>量 / OI</th>
            <th>IV</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((item) => {
            const call = item.call || {};
            const put = item.put || {};
            const isAtm = Number(item.strike) === Number(summary.atmStrike);
            return `
              <tr class="${isAtm ? "is-atm" : ""}">
                <td>${formatAssetOptionNumber(call.last ?? call.settlement)}</td>
                <td>${formatAssetOptionNumber(call.bid)} / ${formatAssetOptionNumber(call.ask)}</td>
                <td>${formatAssetOptionWhole(call.volume)} / ${formatAssetOptionWhole(call.openInterest)}</td>
                <td>${formatAssetOptionIv(call.impliedVolatility)}</td>
                <td><strong>${formatAssetOptionWhole(item.strike)}</strong></td>
                <td>${formatAssetOptionNumber(put.last ?? put.settlement)}</td>
                <td>${formatAssetOptionNumber(put.bid)} / ${formatAssetOptionNumber(put.ask)}</td>
                <td>${formatAssetOptionWhole(put.volume)} / ${formatAssetOptionWhole(put.openInterest)}</td>
                <td>${formatAssetOptionIv(put.impliedVolatility)}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function renderTaiwanOptionDistribution(data = {}) {
  const summary = data.summary || {};
  const rows = pickTaiwanOptionRows(data.distribution || [], summary.atmStrike, 16);
  const maxOi = Math.max(...rows.flatMap((item) => [Number(item.callOpenInterest) || 0, Number(item.putOpenInterest) || 0]), 1);
  if (!rows.length) return "";
  return `
    <div class="tw-option-oi-distribution" aria-label="台指選擇權未平倉分布">
      ${rows.map((item) => {
        const callHeight = Math.max(4, (Number(item.callOpenInterest) || 0) / maxOi * 100);
        const putHeight = Math.max(4, (Number(item.putOpenInterest) || 0) / maxOi * 100);
        return `
          <div>
            <span class="is-call" style="height:${callHeight.toFixed(1)}%"></span>
            <span class="is-put" style="height:${putHeight.toFixed(1)}%"></span>
            <small>${formatAssetOptionWhole(item.strike)}</small>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderTaiwanOptionAnalysis(data = {}) {
  const analysis = data.analysis || {};
  const reasons = Array.isArray(analysis.reasons) ? analysis.reasons : [];
  const scenarios = Array.isArray(analysis.scenarios) ? analysis.scenarios : [];
  const crossValidation = Array.isArray(analysis.crossValidation) ? analysis.crossValidation : [];
  return `
    <article class="panel-card tw-option-ai-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI analysis</p>
          <h4>台灣選擇權 AI 盤勢摘要</h4>
        </div>
        <span>風險 ${escapeHtml(analysis.riskLevel || "--")}</span>
      </div>
      <div class="tw-option-ai-main">
        <strong>${escapeHtml(analysis.bias || "資料同步中")}</strong>
        <p>${escapeHtml(reasons[0] || "等待 TAIFEX 選擇權鏈、PCR 與最大痛點資料。")}</p>
      </div>
      <div class="asset-option-chain-stats">
        <span><b>${Number.isFinite(Number(analysis.marketScore)) ? Number(analysis.marketScore).toFixed(0) : "--"}</b><small>市場分數</small></span>
        <span><b>${Number.isFinite(Number(analysis.riskScore)) ? Number(analysis.riskScore).toFixed(0) : "--"}</b><small>風險分數</small></span>
        <span><b>${Number.isFinite(Number(analysis.confidenceScore)) ? Number(analysis.confidenceScore).toFixed(0) : "--"}</b><small>AI 信心</small></span>
      </div>
      <ul class="tw-option-ai-reasons">
        ${reasons.slice(1, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>資料不足時保留欄位，不以假訊號替代。</li>"}
      </ul>
      <div class="asset-hub-source-stack">
        ${crossValidation.map((item) => `<span><b>${escapeHtml(item.name || "--")}</b><small>${escapeHtml(item.status || "--")} · ${escapeHtml(item.signal || "--")}</small></span>`).join("") || "<span><b>Cross validation</b><small>等待更多公開資料交叉驗證。</small></span>"}
      </div>
      <div class="tw-option-scenarios">
        ${scenarios.map((item) => `
          <section>
            <b>${escapeHtml(item.name || "--")}</b>
            <small>${escapeHtml(item.condition || "")}</small>
            <p>${escapeHtml(item.view || "")}</p>
          </section>
        `).join("")}
      </div>
      <p class="stock-theory-note"><b>策略建議：</b>${escapeHtml(analysis.strategySuggestion || "資料不足時不輸出方向性策略。")}</p>
      <p class="stock-theory-note">${escapeHtml(analysis.disclaimer || "AI 分析僅供研究參考，不保證獲利。")}</p>
    </article>
  `;
}

function renderTaiwanOptionChainCard(data = {}) {
  const summary = data.summary || {};
  const source = data.source || {};
  const error = data.error || "";
  const optionLabel = getTaiwanOptionProductLabel(data);
  const pcr = Number(summary.putCallRatio);
  const volumePcr = Number(summary.volumePutCallRatio);
  return `
    <article class="panel-card tw-option-chain-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">TAIFEX option chain</p>
          <h4>市場選擇權鏈</h4>
          <p class="chart-subtitle">${escapeHtml(optionLabel)} · TAIFEX 官方日報優先，無資料時使用 Yahoo 後備。</p>
        </div>
        <span>${escapeHtml(data.selectedExpiry || "--")} ${escapeHtml(data.selectedExpiryDate || "")}</span>
      </div>
      ${renderTaiwanOptionProductTabs(data)}
      ${renderTaiwanOptionExpiryTabs(data)}
      ${error ? `<p class="stock-detail-empty">${escapeHtml(error)}</p>` : `
        <div class="asset-option-chain-stats tw-option-stats">
          <span><b>${formatAssetOptionWhole(summary.callOpenInterest)}</b><small>Call OI</small></span>
          <span><b>${formatAssetOptionWhole(summary.putOpenInterest)}</b><small>Put OI</small></span>
          <span><b>${Number.isFinite(pcr) ? pcr.toFixed(2) : "--"}</b><small>OI Put / Call</small></span>
          <span><b>${formatAssetOptionWhole(summary.maxPain)}</b><small>最大痛點</small></span>
          <span><b>${formatAssetOptionWhole(summary.atmStrike)}</b><small>ATM 履約價</small></span>
          <span><b>${Number.isFinite(volumePcr) ? volumePcr.toFixed(2) : "--"}</b><small>成交量 Put / Call</small></span>
        </div>
        ${renderTaiwanOptionChainTable(data)}
        ${renderTaiwanOptionDistribution(data)}
        <p class="stock-theory-note">資料源：${escapeHtml(source.primary || "TAIFEX 選擇權每日交易行情查詢")}；IV 為系統估算欄位，正式交易決策仍需比對合法行情商與交易所資料。</p>
      `}
    </article>
  `;
}

function renderAssetHubOptionsLegacy(payload) {
  const vix = findAssetHubItem(payload, "^VIX");
  const vixValue = parseMarketNumber(vix?.close);
  const band = getVixSentimentBand(vixValue);
  const chain = payload?.optionChain || {};
  const taiwanChain = payload?.taiwanOptionChain || {};
  return `
    <section class="section asset-hub-section" id="asset-options">
      ${renderAssetHubSummary(payload, "市場選擇權鏈", "Options", "以 TAIFEX 台灣選擇權鏈、PCR、最大痛點與 VIX 觀察避險需求及波動率結構。", "options.html")}
      <div class="asset-hub-layout asset-hub-options-layout">
        ${renderTaiwanOptionChainCard(taiwanChain)}
        ${renderTaiwanOptionAnalysis(taiwanChain)}
        <article class="panel-card asset-option-sentiment is-${band.tone}"><p class="panel-kicker">Volatility signal</p><h4>CBOE VIX 市場情緒</h4><strong>${Number.isFinite(vixValue) ? vixValue.toFixed(2) : "--"}</strong><span>${escapeHtml(band.label)} · ${escapeHtml(band.text)}</span><small>VIX 變動 ${escapeHtml(vix?.pct || "--")} · 資料日 ${escapeHtml(vix?.date || "--")}</small></article>
        ${renderAssetHubPublicOptionChainCard(chain)}
        ${renderAssetHubRegionalGroups(payload, "選擇權地區市場", () => true, "選擇權資料同步中。")}
      </div>
      ${renderAssetHubOnlineTable(payload, "選擇權觀察")}
    </section>
  `;
}

function renderAssetHubOptions(payload) {
  const vix = findAssetHubItem(payload, "^VIX");
  const vixValue = parseMarketNumber(vix?.close);
  const band = getVixSentimentBand(vixValue);
  const chain = payload?.optionChain || {};
  const taiwanChain = payload?.taiwanOptionChain || {};
  return `
    <section class="section asset-hub-section" id="asset-options">
      <div class="asset-hub-layout asset-hub-options-layout">
        ${renderTaiwanOptionChainCard(taiwanChain)}
        ${renderTaiwanOptionAnalysis(taiwanChain)}
        <article class="panel-card asset-option-sentiment is-${band.tone}">
          <p class="panel-kicker">Volatility signal</p>
          <h4>CBOE VIX 市場情緒</h4>
          <strong>${Number.isFinite(vixValue) ? vixValue.toFixed(2) : "--"}</strong>
          <span>${escapeHtml(band.label)} · ${escapeHtml(band.text)}</span>
          <small>VIX 變動 ${escapeHtml(vix?.pct || "--")} · 資料日 ${escapeHtml(vix?.date || "--")}</small>
        </article>
        ${renderAssetHubPublicOptionChainCard(chain)}
        ${renderAssetHubRegionalGroups(payload, "選擇權地區市場", () => true, "選擇權資料同步中。")}
      </div>
      ${renderAssetHubOnlineTable(payload, "選擇權觀察")}
    </section>
  `;
}

function findAssetHubItemAny(payload, symbols = []) {
  for (const symbol of symbols) {
    const item = findAssetHubItem(payload, symbol);
    if (item) return item;
  }
  return null;
}

function findAssetHubUsableItemAny(payload, symbols = []) {
  for (const symbol of symbols) {
    const item = findAssetHubItem(payload, symbol);
    if (item && !item.error && Number.isFinite(parseMarketNumber(item.close))) return item;
  }
  return findAssetHubItemAny(payload, symbols);
}

function getAssetHubItemsBySymbols(payload, symbols = []) {
  const lookup = new Set(symbols.map((symbol) => String(symbol || "").toUpperCase()));
  return getAssetHubItems(payload).filter((item) => lookup.has(String(item?.symbol || "").toUpperCase()));
}

function getAssetHubUsableBySymbols(payload, symbols = []) {
  return getAssetHubItemsBySymbols(payload, symbols)
    .filter((item) => !item?.error && Number.isFinite(parseMarketNumber(item?.close)));
}

function uniqueAssetHubItemsBySymbol(items = []) {
  const seen = new Set();
  return items.filter((item) => {
    const symbol = String(item?.symbol || "").toUpperCase();
    if (!symbol || seen.has(symbol)) return false;
    seen.add(symbol);
    return true;
  });
}

function normalizeTreasuryYieldValue(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return null;
  return parsed > 20 ? parsed / 10 : parsed;
}

function getAssetHubTreasuryYieldPoint(payload, maturity, symbols = []) {
  const item = findAssetHubItemAny(payload, symbols);
  const treasuryCurve = payload?.validation?.treasuryCurve || {};
  const treasuryValue = parseMarketNumber((treasuryCurve.yields || {})[maturity]);
  if (Number.isFinite(treasuryValue)) {
    return {
      maturity,
      value: treasuryValue,
      item,
      pct: item?.pct || "--",
      date: treasuryCurve.date || item?.date || "--",
      source: treasuryCurve.source || "U.S. Treasury",
    };
  }
  const itemValue = normalizeTreasuryYieldValue(item?.close);
  return {
    maturity,
    value: itemValue,
    item,
    pct: item?.pct || "--",
    date: item?.date || "--",
    source: item?.dataSource || item?.source || "Yahoo Finance",
  };
}

function formatAssetHubYield(value) {
  return Number.isFinite(value) ? `${value.toFixed(2)}%` : "--";
}

function formatAssetHubRatio(value) {
  return Number.isFinite(value) ? value.toFixed(2) : "--";
}

function clampAssetHubScore(value, min = 0, max = 100) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return min;
  return Math.min(max, Math.max(min, parsed));
}

function buildAssetHubFinanceModel(metals, bonds) {
  const gold = findAssetHubUsableItemAny(metals, ["GC=F", "MGC=F", "GLD", "IAU", "GLDM"]);
  const silver = findAssetHubUsableItemAny(metals, ["SI=F", "SIL=F", "SLV", "SIVR", "PSLV"]);
  const platinum = findAssetHubUsableItemAny(metals, ["PL=F", "PPLT", "PLTM"]);
  const palladium = findAssetHubUsableItemAny(metals, ["PA=F", "PALL"]);
  const taiwanGold = findAssetHubItem(metals, "00635U.TW");
  const dxy = findAssetHubItem(bonds, "DX-Y.NYB");
  const vix = findAssetHubItem(bonds, "^VIX");
  const taiwanTenYear = findAssetHubItem(bonds, "TW10Y");
  const germanyTenYear = findAssetHubItem(bonds, "DE10Y");
  const japanTenYear = findAssetHubItem(bonds, "JP10Y");
  const moodyAaa = findAssetHubItem(bonds, "MOODY-AAA");
  const moodyBaa = findAssetHubItem(bonds, "MOODY-BAA");
  const fedFunds = findAssetHubItem(bonds, "FEDFUNDS");
  const ecbDepositRate = findAssetHubItem(bonds, "ECBDFR");
  const bojCallRate = findAssetHubItem(bonds, "IRSTCI01JPM156N");
  const usCpi = findAssetHubItem(bonds, "CPIAUCSL");
  const usPce = findAssetHubItem(bonds, "PCEPI");
  const usPayrolls = findAssetHubItem(bonds, "PAYEMS");
  const usUnemployment = findAssetHubItem(bonds, "UNRATE");
  const euroHicp = findAssetHubItem(bonds, "EURO-HICP");
  const euroUnemployment = findAssetHubItem(bonds, "EURO-UNRATE");
  const japanCpi = findAssetHubItem(bonds, "JPNCPIALLMINMEI");
  const japanUnemployment = findAssetHubItem(bonds, "LRUNTTTTJPM156S");
  const yields = [
    getAssetHubTreasuryYieldPoint(bonds, "2 Yr", ["US2Y", "^UST2Y"]),
    getAssetHubTreasuryYieldPoint(bonds, "5 Yr", ["^FVX"]),
    getAssetHubTreasuryYieldPoint(bonds, "10 Yr", ["^TNX"]),
    getAssetHubTreasuryYieldPoint(bonds, "30 Yr", ["^TYX"]),
  ];
  const twoYear = yields[0]?.value;
  const tenYear = yields[2]?.value;
  const curveSlope = Number.isFinite(twoYear) && Number.isFinite(tenYear) ? tenYear - twoYear : null;
  const goldPrice = parseMarketNumber(gold?.close);
  const silverPrice = parseMarketNumber(silver?.close);
  const goldSilverRatio = Number.isFinite(goldPrice) && Number.isFinite(silverPrice) && silverPrice > 0
    ? goldPrice / silverPrice
    : null;
  const dxyPct = parseMarketNumber(dxy?.pct);
  const vixValue = parseMarketNumber(vix?.close);
  const goldPct = parseMarketNumber(gold?.pct);
  const silverPct = parseMarketNumber(silver?.pct);
  const tlt = findAssetHubItem(bonds, "TLT");
  const tltPct = parseMarketNumber(tlt?.pct);
  let riskScore = 42;
  if (Number.isFinite(vixValue)) riskScore += vixValue >= 25 ? 22 : vixValue >= 19 ? 12 : vixValue <= 13 ? -8 : 0;
  if (Number.isFinite(curveSlope) && curveSlope < 0) riskScore += 12;
  if (Number.isFinite(goldPct) && goldPct > 0.8) riskScore += 7;
  if (Number.isFinite(dxyPct) && dxyPct > 0.35) riskScore += 6;
  if (Number.isFinite(tltPct) && tltPct < -0.8) riskScore += 6;
  if (Number.isFinite(goldSilverRatio) && goldSilverRatio > 85) riskScore += 5;
  if (Number.isFinite(silverPct) && silverPct > goldPct) riskScore -= 4;
  riskScore = Math.round(clampAssetHubScore(riskScore, 8, 96));
  const riskLabel = riskScore >= 72 ? "避險需求升溫" : riskScore >= 52 ? "中性偏防禦" : "風險偏好較穩";
  const signalInputs = [gold, silver, platinum, palladium, taiwanGold, dxy, vix, taiwanTenYear, germanyTenYear, japanTenYear, moodyAaa, moodyBaa, fedFunds, ecbDepositRate, bojCallRate, usCpi, usPce, usPayrolls, usUnemployment, euroHicp, euroUnemployment, japanCpi, japanUnemployment, ...yields.map((item) => item.item || item.value)];
  const availableSignals = signalInputs.filter((item) => {
    if (typeof item === "number") return Number.isFinite(item);
    return item && !item.error && (Number.isFinite(parseMarketNumber(item.close)) || item.value !== null);
  }).length;
  const confidence = Math.round(clampAssetHubScore(42 + (availableSignals / Math.max(signalInputs.length, 1)) * 46 + (Number(bonds?.validation?.secondaryMatchedCount) || 0) * 2, 35, 96));
  const taiwanBondSymbols = ["00679B.TWO", "00687B.TWO", "00696B.TWO", "00697B.TWO", "00795B.TWO", "00857B.TWO", "00931B.TWO"];
  const taiwanMetalSymbols = ["00635U.TW", "00708L.TW", "00674R.TW", "00738U.TW"];
  const preferredMetalEtfOrder = [
    ...taiwanMetalSymbols,
    "GLD", "IAU", "GLDM", "SGOL", "BAR", "AAAU",
    "SLV", "SIVR", "PSLV",
    "PPLT", "PLTM", "PALL", "CPER",
    "GDX", "GDXJ", "RING", "SIL", "SILJ", "COPX",
  ];
  const preferredMetalEtfRank = new Map(preferredMetalEtfOrder.map((symbol, index) => [symbol, index]));
  const metalEtfs = uniqueAssetHubItemsBySymbol([
    ...getAssetHubUsableBySymbols(metals, taiwanMetalSymbols),
    ...getAssetHubUsableItems(metals).filter((item) => String(item.type || "").includes("ETF")),
  ]).sort((left, right) => {
    const leftRank = preferredMetalEtfRank.get(String(left.symbol || "").toUpperCase()) ?? 999;
    const rightRank = preferredMetalEtfRank.get(String(right.symbol || "").toUpperCase()) ?? 999;
    if (leftRank !== rightRank) return leftRank - rightRank;
    return String(left.symbol || "").localeCompare(String(right.symbol || ""));
  });
  const minerStocks = getAssetHubUsableBySymbols(metals, ["NEM", "GOLD", "AEM", "WPM", "FNV"]);
  const bondEtfs = getAssetHubUsableBySymbols(bonds, [...taiwanBondSymbols, "SHY", "VGSH", "IEF", "VGIT", "TLT", "VGLT", "BND", "AGG", "BNDX", "LQD", "HYG", "TIP"]);
  const taiwanMetalEtfs = getAssetHubUsableItems(metals).filter((item) => getAssetHubRegion(item) === "台灣");
  const taiwanBondEtfs = getAssetHubUsableItems(bonds).filter((item) => getAssetHubRegion(item) === "台灣" && String(item.type || "").includes("債券 ETF"));
  const globalMetalEtfs = metalEtfs.filter((item) => getAssetHubRegion(item) !== "台灣");
  const globalBondEtfs = bondEtfs.filter((item) => getAssetHubRegion(item) !== "台灣");
  const metalOnlineRows = getAssetHubItems(metals);
  const metalCatalogCount = Number(metals?.catalogCount) || metalOnlineRows.length;
  const bondOnlineRows = getAssetHubItems(bonds);
  const bondCatalogCount = Number(bonds?.catalogCount) || bondOnlineRows.length;
  const comparisonRows = [
    ...taiwanMetalEtfs,
    ...taiwanBondEtfs,
    ...globalMetalEtfs.slice(0, 5),
    ...globalBondEtfs.slice(0, 8),
  ];
  const scenarios = buildAssetHubFinanceScenarios({
    gold,
    silver,
    dxy,
    vix,
    tlt,
    yields,
    curveSlope,
    riskScore,
    goldSilverRatio,
  });
  const allocation = buildAssetHubAllocationAdvice({ riskScore, goldPct, dxyPct, tltPct, curveSlope });
  return {
    gold,
    silver,
    platinum,
    palladium,
    taiwanGold,
    dxy,
    vix,
    taiwanTenYear,
    germanyTenYear,
    japanTenYear,
    moodyAaa,
    moodyBaa,
    fedFunds,
    ecbDepositRate,
    bojCallRate,
    usCpi,
    usPce,
    usPayrolls,
    usUnemployment,
    euroHicp,
    euroUnemployment,
    japanCpi,
    japanUnemployment,
    tlt,
    yields,
    curveSlope,
    goldSilverRatio,
    riskScore,
    riskLabel,
    confidence,
    availableSignals,
    signalTotal: signalInputs.length,
    metalEtfs,
    minerStocks,
    bondEtfs,
    taiwanMetalEtfs,
    taiwanBondEtfs,
    globalMetalEtfs,
    globalBondEtfs,
    metalOnlineRows,
    metalCatalogCount,
    bondOnlineRows,
    bondCatalogCount,
    comparisonRows,
    scenarios,
    allocation,
  };
}

function buildAssetHubFinanceScenarios(model) {
  const tenYear = model.yields[2]?.value;
  const twoYear = model.yields[0]?.value;
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const goldPct = parseMarketNumber(model.gold?.pct);
  const tltPct = parseMarketNumber(model.tlt?.pct);
  const vixValue = parseMarketNumber(model.vix?.close);
  const scenarios = [
    {
      name: "升息 / 高利率延長",
      condition: Number.isFinite(twoYear) ? `2Y ${formatAssetHubYield(twoYear)}，10Y-2Y ${formatAssetHubYield(model.curveSlope)}` : "2Y 官方資料同步中",
      view: Number.isFinite(model.curveSlope) && model.curveSlope < 0
        ? "曲線仍偏倒掛，短端利率壓力較明顯；長天期債券對利率變動更敏感，宜觀察 TLT / IEF 是否止跌。"
        : "曲線未明顯倒掛，高利率壓力較溫和；債券 ETF 可用久期分層觀察資金是否回流。",
      tone: Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "down" : "flat",
    },
    {
      name: "降息交易",
      condition: `10Y ${formatAssetHubYield(tenYear)}，TLT ${model.tlt?.pct || "--"}`,
      view: Number.isFinite(tltPct) && tltPct > 0
        ? "長天期債 ETF 轉強，市場可能在提前反映殖利率回落；需搭配 10Y 是否同步下行確認。"
        : "長天期債 ETF 尚未給出明確追價訊號，降息交易仍需等待殖利率與價格同步確認。",
      tone: Number.isFinite(tltPct) && tltPct > 0 ? "up" : "flat",
    },
    {
      name: "美元與通膨壓力",
      condition: `DXY ${model.dxy?.pct || "--"}，黃金 ${model.gold?.pct || "--"}`,
      view: Number.isFinite(dxyPct) && dxyPct > 0 && Number.isFinite(goldPct) && goldPct > 0
        ? "美元與黃金同漲，代表避險與通膨疑慮可能同時存在；貴金屬訊號需比對實質利率。"
        : "美元方向未與黃金形成強烈同向壓力，可觀察白銀與礦業 ETF 是否跟上。",
      tone: Number.isFinite(dxyPct) && dxyPct > 0.35 ? "down" : "flat",
    },
    {
      name: "避險需求 / 地緣風險",
      condition: `VIX ${Number.isFinite(vixValue) ? vixValue.toFixed(2) : "--"}，金銀比 ${formatAssetHubRatio(model.goldSilverRatio)}`,
      view: model.riskScore >= 72
        ? "避險分數偏高，黃金、短天期債與現金部位的防守價值上升；追高前仍需看量能與美元。"
        : "避險分數未明顯升溫，可維持核心配置，等待 VIX、金銀比或曲線再次放大訊號。",
      tone: model.riskScore >= 72 ? "down" : "up",
    },
  ];
  return scenarios;
}

function buildAssetHubAllocationAdvice({ riskScore, goldPct, dxyPct, tltPct, curveSlope }) {
  let gold = 18 + riskScore * 0.22 + (Number.isFinite(goldPct) && goldPct > 0 ? 4 : 0);
  let bonds = 36 + (riskScore < 55 ? 6 : 0) + (Number.isFinite(tltPct) && tltPct > 0 ? 6 : 0);
  let cash = 10 + (Number.isFinite(dxyPct) && dxyPct > 0 ? 5 : 0) + (riskScore >= 72 ? 4 : 0);
  if (Number.isFinite(curveSlope) && curveSlope < 0) {
    bonds -= 4;
    cash += 4;
  }
  gold = Math.round(clampAssetHubScore(gold, 14, 42));
  bonds = Math.round(clampAssetHubScore(bonds, 24, 54));
  cash = Math.round(clampAssetHubScore(cash, 8, 24));
  let satellite = 100 - gold - bonds - cash;
  if (satellite < 5) {
    const adjust = 5 - satellite;
    bonds = Math.max(24, bonds - adjust);
    satellite = 100 - gold - bonds - cash;
  }
  return [
    { label: "黃金 / 白銀", value: gold, note: "避險與通膨敏感資產" },
    { label: "公債 / 投資級債", value: bonds, note: "久期依殖利率曲線分層" },
    { label: "美元 / 現金", value: cash, note: "保留再平衡彈性" },
    { label: "衛星部位", value: satellite, note: "礦業、TIPS 或高流動 ETF" },
  ];
}

function renderAssetFinanceSignal(label, kicker, value, detail, tone = "flat", source = "") {
  return `
    <span class="asset-finance-signal is-${tone}">
      <small>${escapeHtml(kicker)}</small>
      <strong>${escapeHtml(value)}</strong>
      <b>${escapeHtml(label)}</b>
      <em class="${tone}">${escapeHtml(detail || "--")}</em>
      ${source ? `<i>${escapeHtml(source)}</i>` : ""}
    </span>
  `;
}

function renderAssetFinanceSignalPanel(kicker, title, text, signals = [], modifier = "") {
  return `
    <section class="asset-finance-signal-panel ${modifier}">
      <div class="asset-finance-signal-panel-head">
        <div>
          <p class="panel-kicker">${escapeHtml(kicker)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
        <small>${escapeHtml(text)}</small>
      </div>
      <div class="asset-finance-signal-grid">
        ${signals.join("")}
      </div>
    </section>
  `;
}

function renderAssetFinanceCoreDashboard(model, metals, bonds) {
  const sourceText = [
    metals?.source || "Yahoo Finance 期貨與 ETF",
    bonds?.validation?.treasuryCurve?.source || bonds?.source || "Yahoo Finance / U.S. Treasury",
  ].filter(Boolean).join(" + ");
  const tenYear = model.yields[2] || {};
  return `
    <article class="panel-card asset-finance-overview-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">Separated defensive asset dashboard</p>
          <h3>貴金屬 / 債券分區總覽</h3>
          <p class="chart-subtitle">貴金屬先看價格、金銀比與 ETF；債券先看殖利率曲線、久期 ETF 與信用風險，跨資產訊號移到下方獨立參考區。</p>
        </div>
        <span class="chip chip-gold">${model.availableSignals} / ${model.signalTotal} 訊號</span>
      </div>
      <div class="asset-finance-overview-split">
        ${renderAssetFinanceSignalPanel("Precious metals", "貴金屬研究入口", "黃金、白銀與金銀比", [
          renderAssetFinanceSignal("黃金期貨", "Gold", formatGlobalValue(model.gold?.close), model.gold?.pct || "--", assetHubTone(model.gold), model.gold?.date),
          renderAssetFinanceSignal("白銀期貨", "Silver", formatGlobalValue(model.silver?.close), model.silver?.pct || "--", assetHubTone(model.silver), model.silver?.date),
          renderAssetFinanceSignal("金銀比", "Gold / Silver", formatAssetHubRatio(model.goldSilverRatio), "黃金 / 白銀", model.goldSilverRatio >= 85 ? "down" : "flat", "線上價格計算"),
        ], "is-metals")}
        ${renderAssetFinanceSignalPanel("Bonds", "債券研究入口", "殖利率曲線與久期 ETF", [
          renderAssetFinanceSignal("10Y 美債殖利率", "10Y Treasury", formatAssetHubYield(tenYear.value), tenYear.pct || "--", assetHubTone(tenYear.item), tenYear.date),
          renderAssetFinanceSignal("10Y-2Y 利差", "Yield curve", formatAssetHubYield(model.curveSlope), model.curveSlope < 0 ? "曲線倒掛" : "正利差", model.curveSlope < 0 ? "down" : "up", bonds?.validation?.treasuryCurve?.date),
          renderAssetFinanceSignal("長天期公債 ETF", "TLT", formatGlobalValue(model.tlt?.close), model.tlt?.pct || "--", assetHubTone(model.tlt), model.tlt?.date),
        ], "is-bonds")}
      </div>
      <p class="asset-hub-insight">AI 避險情緒分數 <b>${model.riskScore}</b>，目前判讀為「${escapeHtml(model.riskLabel)}」；美元、VIX 與配置情境放在「跨資產風險參考」獨立閱讀。資料來源：${escapeHtml(sourceText)}。更新時間 ${escapeHtml([metals?.updatedAt, bonds?.updatedAt].filter(Boolean).join(" / ") || "--")}。</p>
    </article>
  `;
}

function renderAssetFinanceMetalsPanel(model) {
  const metals = [
    ["黃金", model.gold],
    ["白銀", model.silver],
    ["鉑金", model.platinum],
    ["鈀金", model.palladium],
  ];
  const getUnit = (item) => {
    const symbol = String(item?.symbol || "").toUpperCase();
    const type = String(item?.type || "");
    return symbol.endsWith("=F") || type.includes("期貨") ? "USD/oz" : "USD";
  };
  return `
    <article class="panel-card asset-finance-module-card asset-finance-metals-dashboard-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Precious metals</p>
          <h4>貴金屬儀表板</h4>
        </div>
        <span>COMEX / NYMEX</span>
      </div>
      <div class="asset-finance-mini-grid">
        ${metals.map(([label, item]) => `
          <span>
            <small>${escapeHtml(label)} · ${escapeHtml(item?.symbol || "--")}</small>
            <div class="asset-finance-price-line">
              <strong>${formatGlobalValue(item?.close)}</strong>
              <b>${escapeHtml(getUnit(item))}</b>
            </div>
            <em class="${assetHubTone(item)}">${escapeHtml(item?.pct || "--")}</em>
          </span>
        `).join("")}
      </div>
      <p class="stock-theory-note">金銀比 ${formatAssetHubRatio(model.goldSilverRatio)}；${model.taiwanGold && !model.taiwanGold.error ? `台灣黃金 ${model.taiwanGold.pct || "--"}，可與國際黃金期貨同步比較。` : "台灣貴金屬線上行情同步中。"}</p>
      ${renderAssetFinanceTrendPanelContent(model, {
        embedded: true,
        forecastHtml: renderAssetFinancePriceForecastContent(model, { embedded: true }),
      })}
    </article>
  `;
}

function getAssetFinanceTrendRange(rangeKey) {
  return ASSET_FINANCE_TREND_RANGES.find((range) => range.key === rangeKey) || ASSET_FINANCE_TREND_RANGES[1];
}

function buildAssetFinanceTrendDataset(item, limit = 240) {
  const sourceRows = Array.isArray(item?.series) ? item.series : [];
  return sourceRows
    .map((row) => ({
      date: String(row?.date || ""),
      close: parseMarketNumber(row?.close),
    }))
    .filter((row) => row.date && Number.isFinite(row.close) && row.close > 0)
    .slice(-limit);
}

function buildAssetFinanceTrendPoints(rows, limit = 66) {
  const usableRows = (Array.isArray(rows) ? rows : [])
    .filter((row) => row?.date && Number.isFinite(Number(row.close)) && Number(row.close) > 0)
    .slice(-limit)
    .map((row) => ({ date: String(row.date), close: Number(row.close) }));
  if (usableRows.length < 2) return [];
  const base = usableRows.find((row) => Number.isFinite(row.close) && row.close > 0)?.close;
  if (!Number.isFinite(base) || base <= 0) return [];
  return usableRows.map((row) => ({
    ...row,
    value: ((row.close - base) / base) * 100,
  }));
}

function buildAssetFinanceTrendSeriesList(datasets = [], rangeKey = "1m", metalKey = "all") {
  const range = getAssetFinanceTrendRange(rangeKey);
  return datasets
    .filter((metal) => metalKey === "all" || metal.key === metalKey)
    .map((metal) => ({ ...metal, points: buildAssetFinanceTrendPoints(metal.points, range.limit) }))
    .filter((metal) => metal.points.length >= 2);
}

function renderAssetFinanceTrendBody(datasets = [], rangeKey = "1m", metalKey = "all") {
  const range = getAssetFinanceTrendRange(rangeKey);
  let effectiveMetalKey = metalKey;
  let seriesList = buildAssetFinanceTrendSeriesList(datasets, range.key, effectiveMetalKey);
  let fallbackNote = "";
  if (!seriesList.length && effectiveMetalKey !== "all") {
    const requestedFilter = ASSET_FINANCE_TREND_FILTERS.find((filter) => filter.key === effectiveMetalKey)?.label || "該金屬";
    seriesList = buildAssetFinanceTrendSeriesList(datasets, range.key, "all");
    effectiveMetalKey = "all";
    fallbackNote = `${requestedFilter} 目前歷史資料不足，已先顯示可用金屬。`;
  }
  if (!seriesList.length) {
    return `<p class="stock-detail-empty">國際貴金屬歷史資料同步中，請稍後重新整理或使用資料較完整的區間。</p>`;
  }

  const dates = Array.from(new Set(seriesList.flatMap((series) => series.points.map((point) => point.date)))).sort();
  const dateIndex = new Map(dates.map((date, index) => [date, index]));
  const values = seriesList.flatMap((series) => series.points.map((point) => point.value));
  const rawMin = Math.min(0, ...values);
  const rawMax = Math.max(0, ...values);
  const span = rawMax - rawMin || 1;
  const minValue = rawMin - span * 0.12;
  const maxValue = rawMax + span * 0.12;
  const width = 920;
  const height = 350;
  const pad = { top: 28, right: 28, bottom: 44, left: 58 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const xForDate = (date) => {
    const index = dateIndex.get(date) ?? 0;
    return pad.left + (dates.length <= 1 ? 0 : (index / (dates.length - 1)) * plotWidth);
  };
  const yForValue = (value) => pad.top + ((maxValue - value) / (maxValue - minValue || 1)) * plotHeight;
  const gridValues = Array.from(new Set([maxValue, 0, minValue, (maxValue + minValue) / 2].map((value) => Number(value.toFixed(2)))))
    .sort((left, right) => right - left);
  const pathFor = (points) => points
    .map((point, index) => `${index ? "L" : "M"} ${xForDate(point.date).toFixed(2)} ${yForValue(point.value).toFixed(2)}`)
    .join(" ");
  const firstDate = dates[0] || "--";
  const lastDate = dates[dates.length - 1] || "--";
  const activeFilter = ASSET_FINANCE_TREND_FILTERS.find((filter) => filter.key === effectiveMetalKey)?.label || "全部";

  return `
    <div class="asset-finance-trend-stage">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="國際貴金屬百分比走勢圖">
        <rect class="asset-finance-trend-bg" x="${pad.left}" y="${pad.top}" width="${plotWidth}" height="${plotHeight}"></rect>
        ${gridValues.map((value) => `
          <g>
            <line class="asset-finance-trend-grid" x1="${pad.left}" y1="${yForValue(value).toFixed(2)}" x2="${width - pad.right}" y2="${yForValue(value).toFixed(2)}"></line>
            <text class="asset-finance-trend-axis" x="${pad.left - 10}" y="${(yForValue(value) + 4).toFixed(2)}" text-anchor="end">${formatAssetFinancePct(value)}</text>
          </g>
        `).join("")}
        ${dates.length > 1 ? `
          <text class="asset-finance-trend-date" x="${pad.left}" y="${height - 12}" text-anchor="start">${escapeHtml(firstDate)}</text>
          <text class="asset-finance-trend-date" x="${width - pad.right}" y="${height - 12}" text-anchor="end">${escapeHtml(lastDate)}</text>
        ` : ""}
        ${seriesList.map((series) => {
          const last = series.points[series.points.length - 1];
          return `
            <path class="asset-finance-trend-line ${series.className}" d="${pathFor(series.points)}"></path>
            <circle class="asset-finance-trend-dot ${series.className}" cx="${xForDate(last.date).toFixed(2)}" cy="${yForValue(last.value).toFixed(2)}" r="4.8"></circle>
          `;
        }).join("")}
        <line class="asset-finance-trend-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" data-asset-finance-trend-crosshair-x></line>
        <line class="asset-finance-trend-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${width - pad.right}" y2="${pad.top}" data-asset-finance-trend-crosshair-y></line>
        <circle class="asset-finance-trend-crosshair-dot" cx="${pad.left}" cy="${pad.top}" r="4.5" data-asset-finance-trend-crosshair-dot></circle>
        ${dates.map((date, index) => {
          const x = xForDate(date);
          const matched = seriesList.map((series) => {
            const point = series.points.find((item) => item.date === date);
            return point ? `${series.label}:${series.symbol}:${formatAssetFinancePct(point.value)}:${formatGlobalValue(point.close)}:${series.className}:${yForValue(point.value).toFixed(2)}` : "";
          }).filter(Boolean).join("|");
          const firstPoint = seriesList.map((series) => series.points.find((point) => point.date === date)).find(Boolean);
          const y = firstPoint ? yForValue(firstPoint.value) : pad.top;
          const nextX = index < dates.length - 1 ? xForDate(dates[index + 1]) : width - pad.right;
          const previousX = index > 0 ? xForDate(dates[index - 1]) : pad.left;
          const zoneWidth = Math.max(8, (nextX - previousX) / 2);
          return `<rect class="asset-finance-trend-hover-zone" x="${(x - zoneWidth / 2).toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${plotHeight}" data-x="${x.toFixed(2)}" data-y="${y.toFixed(2)}" data-date="${escapeHtml(date)}" data-payload="${escapeHtml(matched)}"></rect>`;
        }).join("")}
      </svg>
      <div class="asset-finance-trend-tooltip" hidden></div>
    </div>
    <div class="asset-finance-trend-legend">
      ${seriesList.map((series) => {
        const last = series.points[series.points.length - 1];
        return `
          <span>
            <i class="${series.className}"></i>
            <b>${escapeHtml(series.label)} · ${escapeHtml(series.symbol)}</b>
            <strong class="${assetFinancePctTone(last.value)}">${formatAssetFinancePct(last.value)}</strong>
            <small>${escapeHtml(last.date)} · 收盤 ${formatGlobalValue(last.close)}</small>
          </span>
        `;
      }).join("")}
    </div>
    <p class="stock-theory-note">${fallbackNote ? `${escapeHtml(fallbackNote)} ` : ""}${escapeHtml(range.label)} · ${escapeHtml(activeFilter)}，以各自區間第一筆收盤價歸零，顯示相對漲跌幅；滑過圖表可查看日期、各金屬相對漲跌與收盤價。</p>
  `;
}

function getAssetFinanceTrendStatus(datasets = [], rangeKey = "1m", metalKey = "all") {
  let seriesList = buildAssetFinanceTrendSeriesList(datasets, rangeKey, metalKey);
  if (!seriesList.length && metalKey !== "all") seriesList = buildAssetFinanceTrendSeriesList(datasets, rangeKey, "all");
  const dates = Array.from(new Set(seriesList.flatMap((series) => series.points.map((point) => point.date)))).sort();
  if (!dates.length) return "資料同步中";
  return `${dates[0]} → ${dates[dates.length - 1]}`;
}

function bindAssetFinanceTrendCursor(card) {
  const stage = card.querySelector(".asset-finance-trend-stage");
  const svg = stage?.querySelector("svg");
  const tooltip = stage?.querySelector(".asset-finance-trend-tooltip");
  if (!stage || !svg || !tooltip) return;
  const xLine = svg.querySelector("[data-asset-finance-trend-crosshair-x]");
  const yLine = svg.querySelector("[data-asset-finance-trend-crosshair-y]");
  const dot = svg.querySelector("[data-asset-finance-trend-crosshair-dot]");
  const hide = () => {
    tooltip.hidden = true;
    xLine?.classList.remove("is-visible");
    yLine?.classList.remove("is-visible");
    dot?.classList.remove("is-visible");
  };
  const show = (event, zone) => {
    const x = Number(zone.dataset.x);
    const y = Number(zone.dataset.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    xLine?.setAttribute("x1", x.toFixed(2));
    xLine?.setAttribute("x2", x.toFixed(2));
    yLine?.setAttribute("y1", y.toFixed(2));
    yLine?.setAttribute("y2", y.toFixed(2));
    dot?.setAttribute("cx", x.toFixed(2));
    dot?.setAttribute("cy", y.toFixed(2));
    xLine?.classList.add("is-visible");
    yLine?.classList.add("is-visible");
    dot?.classList.add("is-visible");
    const rows = String(zone.dataset.payload || "").split("|").filter(Boolean).map((entry) => {
      const [label, symbol, pct, close, className] = entry.split(":");
      return `<span><i class="${escapeHtml(className || "")}"></i><b>${escapeHtml(label || "--")} · ${escapeHtml(symbol || "--")}</b><strong class="${assetFinancePctTone(parseMarketNumber(pct))}">${escapeHtml(pct || "--")}</strong><small>${escapeHtml(close || "--")}</small></span>`;
    }).join("");
    tooltip.innerHTML = `<strong>${escapeHtml(zone.dataset.date || "--")}</strong>${rows || "<span><b>資料同步中</b></span>"}`;
    tooltip.hidden = false;
    const stageRect = stage.getBoundingClientRect();
    const leftBase = event.clientX - stageRect.left + stage.scrollLeft + 14;
    const topBase = event.clientY - stageRect.top + 12;
    const maxLeft = Math.max(12, stage.scrollLeft + stage.clientWidth - tooltip.offsetWidth - 12);
    const maxTop = Math.max(12, stage.clientHeight - tooltip.offsetHeight - 12);
    tooltip.style.left = `${Math.min(Math.max(12, leftBase), maxLeft)}px`;
    tooltip.style.top = `${Math.min(Math.max(12, topBase), maxTop)}px`;
  };
  svg.querySelectorAll(".asset-finance-trend-hover-zone").forEach((zone) => {
    zone.addEventListener("mouseenter", (event) => show(event, zone));
    zone.addEventListener("mousemove", (event) => show(event, zone));
    zone.addEventListener("mouseleave", hide);
  });
  stage.addEventListener("mouseleave", hide);
}

function initAssetFinanceTrendSwitchers(root = document) {
  root.querySelectorAll("[data-asset-finance-trend-card]").forEach((card) => {
    if (card.dataset.assetFinanceTrendBound === "1") return;
    card.dataset.assetFinanceTrendBound = "1";
    let datasets = [];
    try {
      datasets = JSON.parse(card.dataset.assetFinanceTrendPayload || "[]");
    } catch (error) {
      console.warn("Failed to parse precious metal trend payload:", error);
      datasets = [];
    }
    const view = card.querySelector("[data-asset-finance-trend-view]");
    const status = card.querySelector("[data-asset-finance-trend-status]");
    const forecastPanel = card.querySelector("[data-asset-finance-forecast-panel]");
    const forecastView = forecastPanel?.querySelector("[data-asset-finance-forecast-view]");
    let forecasts = [];
    if (forecastPanel) {
      try {
        forecasts = JSON.parse(forecastPanel.dataset.assetFinanceForecastPayload || "[]");
      } catch (error) {
        console.warn("Failed to parse precious metal forecast payload:", error);
        forecasts = [];
      }
    }
    const update = () => {
      const rangeKey = card.dataset.assetFinanceTrendRange || "1m";
      let metalKey = card.dataset.assetFinanceTrendMetal || "all";
      if (metalKey !== "all" && !buildAssetFinanceTrendSeriesList(datasets, rangeKey, metalKey).length) {
        metalKey = "all";
        card.dataset.assetFinanceTrendMetal = "all";
      }
      if (view) view.innerHTML = renderAssetFinanceTrendBody(datasets, rangeKey, metalKey);
      if (status) status.textContent = getAssetFinanceTrendStatus(datasets, rangeKey, metalKey);
      card.querySelectorAll("[data-asset-finance-trend-range]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.assetFinanceTrendRange === rangeKey);
      });
      card.querySelectorAll("[data-asset-finance-trend-metal]").forEach((button) => {
        const key = button.dataset.assetFinanceTrendMetal || "all";
        const available = key === "all" || buildAssetFinanceTrendSeriesList(datasets, rangeKey, key).length > 0;
        button.disabled = !available;
        button.title = available ? "" : "此金屬歷史資料同步中";
        button.classList.toggle("is-disabled", !available);
        button.classList.toggle("is-active", key === metalKey);
      });
      if (forecastView) {
        forecastView.innerHTML = renderAssetFinancePriceForecastBody(forecasts, metalKey, rangeKey);
      }
      bindAssetFinanceTrendCursor(card);
    };
    card.querySelectorAll("[data-asset-finance-trend-range]").forEach((button) => {
      button.addEventListener("click", () => {
        card.dataset.assetFinanceTrendRange = button.dataset.assetFinanceTrendRange || "1m";
        update();
      });
    });
    card.querySelectorAll("[data-asset-finance-trend-metal]").forEach((button) => {
      button.addEventListener("click", () => {
        if (button.disabled) return;
        card.dataset.assetFinanceTrendMetal = button.dataset.assetFinanceTrendMetal || "all";
        update();
      });
    });
    update();
  });
}

function renderAssetFinanceTrendPanelContent(model, options = {}) {
  const metals = [
    { key: "gold", label: "黃金", symbol: model.gold?.symbol || "GC=F", item: model.gold, className: "is-gold" },
    { key: "silver", label: "白銀", symbol: model.silver?.symbol || "SI=F", item: model.silver, className: "is-silver" },
    { key: "platinum", label: "鉑金", symbol: model.platinum?.symbol || "PL=F", item: model.platinum, className: "is-platinum" },
    { key: "palladium", label: "鈀金", symbol: model.palladium?.symbol || "PA=F", item: model.palladium, className: "is-palladium" },
  ];
  const datasets = metals
    .map((metal) => ({ ...metal, points: buildAssetFinanceTrendDataset(metal.item) }))
    .filter((metal) => metal.points.length >= 2);
  const embedded = Boolean(options.embedded);
  const forecastHtml = typeof options.forecastHtml === "string" ? options.forecastHtml : "";
  if (!datasets.length) {
    return `
      <div class="asset-finance-trend-shell ${embedded ? "is-embedded" : ""}">
        <div class="asset-finance-trend-subhead">
          <div><small>International trend</small><strong>國際貴金屬走勢圖</strong></div>
          <span>GC / SI / PL / PA</span>
        </div>
        <p class="stock-detail-empty">國際貴金屬歷史走勢資料同步中。</p>
        ${forecastHtml}
      </div>
    `;
  }
  const initialRange = "1m";
  const initialMetal = "all";
  const chartId = `asset-finance-trend-${++assetFinanceTrendChartCounter}`;
  const payload = JSON.stringify(datasets.map((metal) => ({
    key: metal.key,
    label: metal.label,
    symbol: metal.symbol,
    className: metal.className,
    points: metal.points,
  })));
  const filterButtonHtml = ASSET_FINANCE_TREND_FILTERS.map((filter) => {
    const available = filter.key === "all" || buildAssetFinanceTrendSeriesList(datasets, initialRange, filter.key).length > 0;
    return `<button class="asset-finance-trend-toggle ${filter.key === initialMetal ? "is-active" : ""} ${available ? "" : "is-disabled"}" type="button" data-asset-finance-trend-metal="${escapeHtml(filter.key)}" ${available ? "" : 'disabled title="此金屬歷史資料同步中"'}>${escapeHtml(filter.label)}</button>`;
  }).join("");
  return `
    <div class="asset-finance-trend-shell ${embedded ? "is-embedded" : ""}" id="${escapeHtml(chartId)}" data-asset-finance-trend-card data-asset-finance-trend-range="${initialRange}" data-asset-finance-trend-metal="${initialMetal}" data-asset-finance-trend-payload="${escapeHtml(payload)}">
      <div class="asset-finance-trend-subhead">
        <div><small>International trend</small><strong>國際貴金屬走勢圖</strong></div>
        <span data-asset-finance-trend-status>${escapeHtml(getAssetFinanceTrendStatus(datasets, initialRange, initialMetal))}</span>
      </div>
      <div class="asset-finance-trend-controls" aria-label="國際貴金屬走勢切換">
        <div>
          ${ASSET_FINANCE_TREND_RANGES.map((range) => `<button class="asset-finance-trend-toggle ${range.key === initialRange ? "is-active" : ""}" type="button" data-asset-finance-trend-range="${escapeHtml(range.key)}">${escapeHtml(range.label)}</button>`).join("")}
        </div>
        <div>
          ${filterButtonHtml}
        </div>
      </div>
      <div data-asset-finance-trend-view>
        ${renderAssetFinanceTrendBody(datasets, initialRange, initialMetal)}
      </div>
      ${forecastHtml}
    </div>
  `;
}

function renderAssetFinanceInternationalTrendPanel(model) {
  return `
    <article class="panel-card asset-finance-module-card asset-finance-trend-card">
      ${renderAssetFinanceTrendPanelContent(model)}
    </article>
  `;
}

function renderAssetFinanceMetalProfilesPanel(model) {
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const platinumPct = parseMarketNumber(model.platinum?.pct);
  const palladiumPct = parseMarketNumber(model.palladium?.pct);
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : null;
  const profiles = [
    {
      label: "黃金",
      code: "XAU",
      item: model.gold,
      role: "避險核心",
      focus: "美元、實質利率、央行購金",
      thesis: "利率下行或風險升溫時通常最先反應。",
      signal: model.riskScore >= 72
        ? "防禦需求較強，重點看美元與殖利率是否壓回金價。"
        : "若美元走弱或殖利率回落，黃金較容易維持核心配置角色。",
    },
    {
      label: "白銀",
      code: "XAG",
      item: model.silver,
      role: "工業 + 避險",
      focus: "太陽能、AI、電子與投資需求",
      thesis: "景氣與風險偏好同步改善時彈性較大。",
      signal: Number.isFinite(silverLead) && silverLead > 0
        ? "白銀強於黃金，代表景氣與工業需求開始接棒。"
        : "白銀尚未明顯領先，行情仍偏黃金防禦主導。",
    },
    {
      label: "鉑金",
      code: "XPT",
      item: model.platinum,
      role: "工業供給循環",
      focus: "南非供給、氫能源與汽車需求",
      thesis: "供給擾動與工業需求比避險情緒更關鍵。",
      signal: Number.isFinite(platinumPct) && platinumPct > 0
        ? "鉑金轉強時可視為汽車、氫能與供給壓力的再定價訊號。"
        : "鉑金偏弱時，工業供需尚未成為主線。",
    },
    {
      label: "鈀金",
      code: "XPD",
      item: model.palladium,
      role: "汽車觸媒循環",
      focus: "燃油車景氣、替代材料與庫存",
      thesis: "受車市週期與材料替代影響，波動常較獨立。",
      signal: Number.isFinite(palladiumPct) && palladiumPct > 0
        ? "鈀金轉強多半與汽車觸媒、庫存回補或替代材料預期變化有關。"
        : "鈀金偏弱時，需提防車市週期與替代材料壓力。",
    },
  ];
  return `
    <article class="panel-card asset-finance-module-card asset-finance-metal-profile-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">International metals map</p>
          <h4>四大貴金屬定位</h4>
        </div>
        <span>XAU / XAG / XPT / XPD</span>
      </div>
      <div class="asset-finance-metal-profile-grid">
        ${profiles.map((profile) => `
          <section>
            <div class="asset-finance-profile-top"><small>${escapeHtml(profile.code)}</small><em class="${assetHubTone(profile.item)}">${escapeHtml(profile.item?.pct || "--")}</em></div>
            <strong>${escapeHtml(profile.label)}</strong>
            <b>${formatGlobalValue(profile.item?.close)}</b>
            <p>${escapeHtml(profile.role)}｜${escapeHtml(profile.thesis)}</p>
            <i>觀察：${escapeHtml(profile.focus)}</i>
            <span class="asset-finance-profile-callout"><small>研判</small>${escapeHtml(profile.signal)}</span>
          </section>
        `).join("")}
      </div>
    </article>
  `;
}

function buildAssetFinanceGlobalVenueInsight(model) {
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const platinumPct = parseMarketNumber(model.platinum?.pct);
  const palladiumPct = parseMarketNumber(model.palladium?.pct);
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const tenYear = model.yields[2] || {};
  const tenYearValue = tenYear.value;
  const etfAvg = averageAssetFinancePct(model.globalMetalEtfs);
  const minerAvg = averageAssetFinancePct(model.minerStocks);
  const taiwanAvg = averageAssetFinancePct(model.taiwanMetalEtfs);
  const metalAvg = averageAssetFinanceValues([goldPct, silverPct, platinumPct, palladiumPct]);
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : null;
  const taiwanSpread = Number.isFinite(taiwanAvg) && Number.isFinite(metalAvg) ? taiwanAvg - metalAvg : null;
  const macroPressure = (Number.isFinite(dxyPct) && dxyPct > 0.35) || (Number.isFinite(tenYearValue) && tenYearValue >= 4.2);
  const fundPulse = averageAssetFinanceValues([etfAvg, minerAvg].filter(Number.isFinite));
  const venueConclusion = macroPressure && Number.isFinite(goldPct) && goldPct > 0
    ? "AI 判讀：美元或利率偏強但黃金抗跌，全球場域重點放在倫敦現貨與 COMEX 期貨是否同步承接避險買盤。"
    : Number.isFinite(silverLead) && silverLead > 0 && Number.isFinite(fundPulse) && fundPulse > 0
      ? "AI 判讀：白銀、ETF 與礦商同步轉強，場域重點從黃金現貨擴散到 COMEX 流動性與亞洲實體需求。"
      : Number.isFinite(fundPulse) && fundPulse < 0
        ? "AI 判讀：價格與資金面沒有共振，全球場域先看 COMEX 成交與 ETF 是否回流，避免把單日反彈誤判成趨勢。"
        : "AI 判讀：全球場域仍屬等待確認，先用倫敦現貨定價、COMEX 期貨流動性與亞洲實需交叉驗證。";
  const markets = [
    [
      "倫敦 LBMA / OTC",
      "現貨定價核心",
      Number.isFinite(goldPct) && goldPct > 0
        ? `黃金 ${formatAssetFinancePct(goldPct)}，現貨防禦需求仍在。`
        : `黃金 ${model.gold?.pct || "--"}，先看現貨基準是否止穩。`,
    ],
    [
      "美國 COMEX / CME",
      "期貨流動性核心",
      Number.isFinite(silverLead) && silverLead > 0
        ? `白銀相對黃金 ${formatAssetFinancePct(silverLead)}，短線槓桿資金有擴散跡象。`
        : `ETF ${formatAssetFinancePct(etfAvg)} / 礦商 ${formatAssetFinancePct(minerAvg)}，需等期貨資金確認。`,
    ],
    [
      "上海 SGE",
      "亞洲實體需求",
      Number.isFinite(taiwanSpread)
        ? `台灣商品相對國際 ${formatAssetFinancePct(taiwanSpread)}，可作亞洲需求與匯率落差參考。`
        : "亞洲實體需求同步中，先用黃金與白銀國際價格判讀。",
    ],
    [
      "香港",
      "實體流通樞紐",
      macroPressure
        ? "美元利率壓力下，留意亞洲實體買盤是否承接回檔。"
        : "用庫存、轉口與亞洲溢價觀察中國與國際市場連動。",
    ],
    [
      "日本 OSE",
      "區域避險補充",
      model.riskScore >= 72
        ? `避險分數 ${model.riskScore}/100，日圓與亞洲避險需求需要同步觀察。`
        : `10Y ${formatAssetHubYield(tenYearValue)}，區域期貨先作輔助確認。`,
    ],
  ];
  return { venueConclusion, markets };
}

function renderAssetFinanceGlobalMarketPanel(model) {
  const { venueConclusion, markets } = buildAssetFinanceGlobalVenueInsight(model);
  return `
    <article class="panel-card asset-finance-module-card asset-finance-market-map-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Global venues</p>
          <h4>全球交易市場 AI 場域判讀</h4>
        </div>
        <span>現貨 / 期貨 / 實需</span>
      </div>
      <p class="asset-finance-market-brief">${escapeHtml(venueConclusion)}</p>
      <div class="asset-finance-market-list">
        ${markets.map(([name, role, text]) => `<span><b>${escapeHtml(name)}</b><em>${escapeHtml(role)}</em><small>${escapeHtml(text)}</small></span>`).join("")}
      </div>
    </article>
  `;
}

function renderAssetFinanceDriverFactorCard(factor) {
  const score = Math.round(clampAssetHubScore(factor.score, 0, 100));
  return `
    <section class="asset-finance-driver-factor is-${escapeHtml(factor.tone || "flat")}">
      <span>
        <small>${escapeHtml(factor.label)}</small>
        <b>${escapeHtml(factor.status)}</b>
      </span>
      <strong>${escapeHtml(factor.value)}</strong>
      <div class="asset-finance-driver-meter" style="--driver-score:${score}%"><i></i></div>
      <p>${escapeHtml(factor.detail)}</p>
      <div class="asset-finance-driver-predict"><b>預測影響</b><small>${escapeHtml(factor.forecast || "")}</small></div>
      <em>${escapeHtml(factor.watch)}</em>
    </section>
  `;
}

function formatAssetFinanceMetricPct(value) {
  return Number.isFinite(value) ? formatAssetFinancePct(value) : "--";
}

function averageAssetFinanceValues(values = []) {
  const clean = values.filter(Number.isFinite);
  if (!clean.length) return null;
  return clean.reduce((sum, value) => sum + value, 0) / clean.length;
}

function standardDeviationAssetFinanceValues(values = []) {
  const avg = averageAssetFinanceValues(values);
  if (!Number.isFinite(avg)) return null;
  const variance = values
    .filter(Number.isFinite)
    .reduce((sum, value) => sum + ((value - avg) ** 2), 0) / Math.max(values.filter(Number.isFinite).length, 1);
  return Math.sqrt(variance);
}

function buildAssetFinanceForecastItem({ label, code, key, item, model }) {
  const series = normalizeGlobalSeries(item?.series || []);
  const close = parseMarketNumber(item?.close) || series.at(-1)?.value;
  if (!Number.isFinite(close) || close <= 0) return null;
  const values = series.map((point) => point.value).filter(Number.isFinite);
  const lastValue = values.at(-1) || close;
  const returns = [];
  for (let index = 1; index < values.length; index += 1) {
    const prev = values[index - 1];
    const current = values[index];
    if (Number.isFinite(prev) && prev > 0 && Number.isFinite(current)) {
      returns.push(((current / prev) - 1) * 100);
    }
  }
  const recentReturns = returns.slice(-20);
  const dailyAvg = averageAssetFinanceValues(recentReturns) ?? (parseMarketNumber(item?.pct) || 0);
  const dailyVol = standardDeviationAssetFinanceValues(recentReturns) ?? 1.2;
  const momentum5 = values.length >= 6 ? ((lastValue / values[values.length - 6]) - 1) * 100 : (parseMarketNumber(item?.pct) || 0);
  const momentum20 = values.length >= 21 ? ((lastValue / values[values.length - 21]) - 1) * 100 : momentum5;
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const etfAvg = averageAssetFinancePct(model.globalMetalEtfs);
  const minerAvg = averageAssetFinancePct(model.minerStocks);
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : 0;
  let macroBias = 0;
  if (Number.isFinite(dxyPct)) macroBias += dxyPct < 0 ? Math.min(Math.abs(dxyPct) * 0.08, 0.18) : -Math.min(dxyPct * 0.08, 0.18);
  if (model.riskScore >= 72) macroBias += key === "gold" ? 0.18 : 0.04;
  if (model.riskScore <= 46 && key !== "gold") macroBias += 0.08;
  if (key !== "gold" && Number.isFinite(silverLead)) macroBias += clampAssetHubScore(silverLead * 0.05, -0.16, 0.18);
  if (Number.isFinite(etfAvg)) macroBias += clampAssetHubScore(etfAvg * 0.025, -0.12, 0.12);
  if (Number.isFinite(minerAvg) && key !== "gold") macroBias += clampAssetHubScore(minerAvg * 0.018, -0.1, 0.12);
  const baseDailyPct = clampAssetHubScore((dailyAvg * 0.38) + ((momentum5 / 5) * 0.32) + ((momentum20 / 20) * 0.18) + macroBias, -1.8, 1.8);
  const horizons = [
    { label: "1日", days: 1 },
    { label: "5日", days: 5 },
    { label: "20日", days: 20 },
  ].map((horizon) => {
    const expectedPct = clampAssetHubScore(baseDailyPct * horizon.days, -24, 24);
    const rangePct = clampAssetHubScore(dailyVol * Math.sqrt(horizon.days) * 1.08, 0.28, 18);
    return {
      ...horizon,
      expectedPct,
      target: close * (1 + expectedPct / 100),
      low: close * (1 + (expectedPct - rangePct * 0.55) / 100),
      high: close * (1 + (expectedPct + rangePct * 0.55) / 100),
    };
  });
  const medium = horizons.find((entry) => entry.days === 20) || horizons.at(-1);
  const tone = medium.expectedPct > 1.2 ? "up" : medium.expectedPct < -1.2 ? "down" : "flat";
  const direction = tone === "up" ? "偏多預測" : tone === "down" ? "偏弱預測" : "區間預測";
  const confidence = Math.round(clampAssetHubScore(42 + Math.min(series.length, 90) * 0.35 + (model.confidence || 0) * 0.12 - Math.max(0, dailyVol - 2.2) * 4, 35, 92));
  const basis = [
    `5日動能 ${formatAssetFinanceMetricPct(momentum5)}`,
    `20日動能 ${formatAssetFinanceMetricPct(momentum20)}`,
    `日波動 ${formatAssetFinanceMetricPct(dailyVol)}`,
  ].join(" / ");
  const assumption = tone === "up"
    ? "預測成立條件：美元利率不再同步上壓，ETF 或礦商至少一項維持正向。"
    : tone === "down"
      ? "預測成立條件：美元利率壓力延續，且 ETF 或礦商未出現回補買盤。"
      : "預測成立條件：主要因子未共振，價格維持區間波動並等待新訊號。";
  return {
    label,
    code,
    key,
    close,
    pct: item?.pct || "--",
    tone,
    direction,
    confidence,
    momentum5,
    momentum20,
    dailyVol,
    basis,
    assumption,
    horizons,
  };
}

function buildAssetFinancePriceForecastItems(model) {
  return [
    { label: "黃金", code: "XAU", key: "gold", item: model.gold },
    { label: "白銀", code: "XAG", key: "silver", item: model.silver },
    { label: "鉑金", code: "XPT", key: "platinum", item: model.platinum },
    { label: "鈀金", code: "XPD", key: "palladium", item: model.palladium },
  ].map((entry) => buildAssetFinanceForecastItem({ ...entry, model })).filter(Boolean);
}

function renderAssetFinancePriceForecastBody(forecasts = [], metalKey = "all", rangeKey = "1m") {
  const selectedForecasts = metalKey === "all"
    ? forecasts
    : forecasts.filter((forecast) => forecast.key === metalKey);
  const visibleForecasts = selectedForecasts.length ? selectedForecasts : forecasts;
  const horizon20 = forecasts
    .map((item) => ({ item, target: item.horizons.find((entry) => entry.days === 20) }))
    .filter((entry) => entry.target);
  const focusedForecast = metalKey === "all" ? null : visibleForecasts[0];
  const focused20 = focusedForecast?.horizons.find((entry) => entry.days === 20);
  const strongestForecast = [...horizon20].sort((left, right) => right.target.expectedPct - left.target.expectedPct)[0];
  const weakestForecast = [...horizon20].sort((left, right) => left.target.expectedPct - right.target.expectedPct)[0];
  const avgForecastPct = averageAssetFinanceValues(horizon20.map((entry) => entry.target.expectedPct));
  const activeFilter = ASSET_FINANCE_TREND_FILTERS.find((filter) => filter.key === metalKey)?.label || "全部";
  const activeRange = getAssetFinanceTrendRange(rangeKey);
  const forecastTheme = Number.isFinite(avgForecastPct) && avgForecastPct > 1.2
    ? "整體預測偏多"
    : Number.isFinite(avgForecastPct) && avgForecastPct < -1.2
      ? "整體預測偏弱"
      : "整體預測區間震盪";
  const readoutHtml = focusedForecast
    ? `
        <span><small>檢視標的</small><b>${escapeHtml(focusedForecast.label)} / ${escapeHtml(activeRange.label)}</b></span>
        <span><small>20日預測</small><b class="${assetFinancePctTone(focused20?.expectedPct)}">${focused20 ? `${formatGlobalValue(focused20.target)} ${formatAssetFinancePct(focused20.expectedPct)}` : "--"}</b></span>
        <span><small>20日風險區間</small><b>${focused20 ? `${formatGlobalValue(focused20.low)} - ${formatGlobalValue(focused20.high)}` : "--"}</b></span>
        <span><small>模型信心</small><b>${focusedForecast.confidence}/100</b></span>
      `
    : `
        <span><small>預測主題</small><b>${escapeHtml(forecastTheme)}</b></span>
        <span><small>20日強勢</small><b>${strongestForecast ? `${escapeHtml(strongestForecast.item.label)} ${formatAssetFinancePct(strongestForecast.target.expectedPct)}` : "--"}</b></span>
        <span><small>20日弱勢</small><b>${weakestForecast ? `${escapeHtml(weakestForecast.item.label)} ${formatAssetFinancePct(weakestForecast.target.expectedPct)}` : "--"}</b></span>
        <span><small>平均預測</small><b class="${assetFinancePctTone(avgForecastPct)}">${formatAssetFinancePct(avgForecastPct)}</b></span>
      `;
  return `
      <div class="asset-finance-forecast-readout">
        ${readoutHtml}
      </div>
      <div class="asset-finance-forecast-grid ${focusedForecast ? "is-focused" : ""}">
        ${visibleForecasts.map((forecast) => `
          <section class="is-${escapeHtml(forecast.tone)}">
            <div class="asset-finance-forecast-head">
              <small>${escapeHtml(forecast.code)}</small>
              <em>信心 ${forecast.confidence}/100</em>
            </div>
            <h5>${escapeHtml(forecast.label)}</h5>
            <div class="asset-finance-forecast-current">
              <span><small>現價</small><b>${formatGlobalValue(forecast.close)}</b></span>
              <span><small>模型方向</small><b class="${escapeHtml(forecast.tone)}">${escapeHtml(forecast.direction)}</b></span>
            </div>
            <div class="asset-finance-forecast-rows">
              ${forecast.horizons.map((target) => `
                <span>
                  <b>${escapeHtml(target.label)}</b>
                  <strong>${formatGlobalValue(target.target)}</strong>
                  <small class="${assetFinancePctTone(target.expectedPct)}">${formatAssetFinancePct(target.expectedPct)}</small>
                  <em>${formatGlobalValue(target.low)} - ${formatGlobalValue(target.high)}</em>
                </span>
              `).join("")}
            </div>
            <p>${escapeHtml(forecast.basis)}。</p>
            <p class="asset-finance-forecast-assumption">${escapeHtml(forecast.assumption)}</p>
          </section>
        `).join("") || `<p class="stock-detail-empty">價格序列同步中，暫無可用預測。</p>`}
      </div>
      <p class="stock-theory-note">目前跟隨走勢圖切換：${escapeHtml(activeRange.label)} / ${escapeHtml(activeFilter)}。分析預測模型使用歷史序列、短中期動能、美元利率、避險分數、ETF 與礦商確認計算；輸出為情境價格與風險區間，不是保證價格。</p>
  `;
}

function renderAssetFinancePriceForecastContent(model, options = {}) {
  const forecasts = buildAssetFinancePriceForecastItems(model);
  const embedded = Boolean(options.embedded);
  const payload = JSON.stringify(forecasts);
  return `
    <div class="asset-finance-forecast-content ${embedded ? "is-embedded" : ""}" data-asset-finance-forecast-panel data-asset-finance-forecast-payload="${escapeHtml(payload)}">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI price forecast</p>
          <h4>AI 貴金屬分析預測</h4>
        </div>
        <span>1日 / 5日 / 20日</span>
      </div>
      <div data-asset-finance-forecast-view>
        ${renderAssetFinancePriceForecastBody(forecasts)}
      </div>
    </div>
  `;
}

function renderAssetFinancePriceForecastPanel(model) {
  return `
    <article class="panel-card asset-finance-module-card asset-finance-forecast-card">
      ${renderAssetFinancePriceForecastContent(model)}
    </article>
  `;
}

function renderAssetFinanceMetalDriversPanel(model) {
  const tenYear = model.yields[2] || {};
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const tenYearValue = tenYear.value;
  const vixValue = parseMarketNumber(model.vix?.close);
  const vixPct = parseMarketNumber(model.vix?.pct);
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const platinumPct = parseMarketNumber(model.platinum?.pct);
  const palladiumPct = parseMarketNumber(model.palladium?.pct);
  const industrialPulseValues = [silverPct, platinumPct, palladiumPct].filter(Number.isFinite);
  const industrialPulse = industrialPulseValues.length
    ? industrialPulseValues.reduce((sum, value) => sum + value, 0) / industrialPulseValues.length
    : null;
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : null;
  const dxyPressure = Number.isFinite(dxyPct) ? clampAssetHubScore(50 + dxyPct * 55, 8, 96) : 50;
  const ratePressure = Number.isFinite(tenYearValue) ? clampAssetHubScore(44 + (tenYearValue - 3.6) * 22, 8, 96) : 50;
  const hedgePulse = Number.isFinite(model.riskScore) ? clampAssetHubScore(model.riskScore, 8, 96) : 50;
  const industrialScore = Number.isFinite(industrialPulse) ? clampAssetHubScore(50 + industrialPulse * 9, 8, 96) : 50;
  const ratioScore = Number.isFinite(model.goldSilverRatio) ? clampAssetHubScore((model.goldSilverRatio - 55) * 2.25, 8, 96) : 50;
  const etfAvg = averageAssetFinancePct(model.globalMetalEtfs);
  const minerAvg = averageAssetFinancePct(model.minerStocks);
  const fundPulseValues = [etfAvg, minerAvg].filter(Number.isFinite);
  const fundPulse = fundPulseValues.length
    ? fundPulseValues.reduce((sum, value) => sum + value, 0) / fundPulseValues.length
    : null;
  const macroScore = Math.round((dxyPressure + ratePressure) / 2);
  const capitalScore = Number.isFinite(fundPulse)
    ? clampAssetHubScore(50 + fundPulse * 8 + (Number.isFinite(model.goldSilverRatio) && model.goldSilverRatio < 72 ? 8 : 0), 8, 96)
    : ratioScore;
  const macroTone = (Number.isFinite(dxyPct) && dxyPct > 0.25) || (Number.isFinite(tenYearValue) && tenYearValue >= 4.2)
    ? "down"
    : (Number.isFinite(dxyPct) && dxyPct < -0.25) && (Number.isFinite(tenYearValue) ? tenYearValue < 4.2 : true)
      ? "up"
      : "flat";
  const fundTone = Number.isFinite(fundPulse) && fundPulse > 0.35
    ? "up"
    : Number.isFinite(fundPulse) && fundPulse < -0.35
      ? "down"
      : "flat";
  const factors = [
    {
      label: "美元利率壓力",
      value: `DXY ${model.dxy?.pct || "--"} / 10Y ${formatAssetHubYield(tenYearValue)}`,
      score: macroScore,
      tone: macroTone,
      status: macroTone === "down" ? "機會成本偏高" : macroTone === "up" ? "壓力降溫" : "宏觀壓力中性",
      detail: "美元與美債殖利率共同決定無息資產的持有成本；若兩者上行，黃金需靠避險或通膨預期抵消壓力。",
      forecast: macroTone === "down" ? "下修短線目標價權重，預測更偏區間或回檔。" : macroTone === "up" ? "提高 1日與5日反彈機率，黃金預測彈性優先。" : "維持中性假設，等待美元與10Y同向突破。",
      watch: `DXY ${model.dxy?.pct || "--"}、10Y 變動 ${tenYear.item?.pct || "--"}，同步走強時降低追價。`,
    },
    {
      label: "避險需求",
      value: `VIX ${formatGlobalValue(model.vix?.close)}`,
      score: hedgePulse,
      tone: model.riskScore >= 72 ? "up" : model.riskScore >= 52 ? "flat" : "down",
      status: model.riskScore >= 72 ? "避險需求升溫" : model.riskScore >= 52 ? "防禦需求中性" : "風險偏好較穩",
      detail: "VIX、曲線倒掛、美元與黃金同漲時，黃金通常優先受益；白銀需等待風險偏好回穩。",
      forecast: model.riskScore >= 72 ? "提高黃金預測支撐，但白銀與鉑鈀需等風險偏好回穩。" : "避險溢價有限，預測需更依賴動能與資金確認。",
      watch: `VIX 日變動 ${Number.isFinite(vixPct) ? formatAssetFinancePct(vixPct) : "--"}，避險分數 ${model.riskScore}/100。`,
    },
    {
      label: "工業需求脈動",
      value: Number.isFinite(industrialPulse) ? formatAssetFinancePct(industrialPulse) : "--",
      score: industrialScore,
      tone: Number.isFinite(industrialPulse) && industrialPulse > 0.35 ? "up" : Number.isFinite(industrialPulse) && industrialPulse < -0.35 ? "down" : "flat",
      status: Number.isFinite(silverLead) && silverLead > 0 ? "白銀與工業金屬追上" : "工業端等待確認",
      detail: "白銀、鉑金、鈀金更受太陽能、汽車觸媒、氫能與礦產供給影響，常用來判斷行情是否由避險擴散到景氣交易。",
      forecast: Number.isFinite(silverLead) && silverLead > 0 ? "提高白銀、鉑金與鈀金的20日預測彈性。" : "工業金屬未接棒時，預測重心仍偏黃金防禦。",
      watch: `白銀相對黃金 ${formatAssetFinanceMetricPct(silverLead)}，鉑鈀需看供給與車市循環。`,
    },
    {
      label: "資金與相對價值",
      value: `ETF ${formatAssetFinanceMetricPct(etfAvg)} / 金銀比 ${formatAssetHubRatio(model.goldSilverRatio)}`,
      score: capitalScore,
      tone: fundTone,
      status: fundTone === "up" ? "資金確認偏多" : fundTone === "down" ? "資金動能偏弱" : model.goldSilverRatio <= 70 ? "白銀追價偏強" : "等待資金確認",
      detail: "ETF 與礦商用來確認價格是否有資金跟進；金銀比則判斷行情集中在黃金防禦，或已擴散到白銀與工業需求。",
      forecast: fundTone === "up" ? "提高預測信心與延續性，尤其是白銀與礦商相關標的。" : fundTone === "down" ? "降低趨勢延伸假設，目標價需保守。" : "先保留區間預測，等待資金確認。",
      watch: `礦商平均 ${formatAssetFinanceMetricPct(minerAvg)}；若礦商強於 ETF，行情延續性較佳。`,
    },
  ];
  const dominantFactor = [...factors].sort((left, right) => right.score - left.score)[0];
  const silverLeadText = Number.isFinite(silverLead) ? formatAssetFinanceMetricPct(silverLead) : "--";
  const driverFundingText = `ETF ${formatAssetFinanceMetricPct(etfAvg)} / 礦商 ${formatAssetFinanceMetricPct(minerAvg)}`;
  const driverHeadline = (() => {
    if (fundTone === "up" && Number.isFinite(silverLead) && silverLead > 0) {
      return `資金與價格同時轉強，${driverFundingText}，白銀相對黃金 ${silverLeadText}；這代表買盤不只停在黃金避險，而是擴散到白銀與礦商彈性。`;
    }
    if (Number.isFinite(dxyPct) && dxyPct > 0 && Number.isFinite(goldPct) && goldPct > 0) {
      return "美元與黃金同漲，偏向避險或通膨疑慮主導；若 ETF 與礦商未同步補強，仍不宜把單日上漲解讀成完整多頭。";
    }
    if (model.riskScore >= 72) {
      return `避險分數 ${model.riskScore}/100 偏高，黃金仍是第一層防禦；白銀與礦商需要資金確認，才算從防守轉為進攻。`;
    }
    return "目前驅動因子仍在拉扯，先以區間模型處理，等待價格、資金與美元利率至少兩項同向後再提高預測信心。";
  })();
  const driverConfirmation = dominantFactor?.label === "美元利率壓力"
    ? `確認黃金是否能在 DXY ${model.dxy?.pct || "--"}、10Y ${formatAssetHubYield(tenYearValue)} 下維持抗跌。`
    : dominantFactor?.label === "避險需求"
      ? `確認 VIX ${formatGlobalValue(model.vix?.close)} 與金銀比 ${formatAssetHubRatio(model.goldSilverRatio)} 是否同步走高。`
      : dominantFactor?.label === "工業需求脈動"
        ? `確認白銀相對黃金 ${silverLeadText}，以及鉑鈀是否延續補漲。`
        : `確認 ${driverFundingText} 是否同向，若礦商續強，代表市場願意押槓桿彈性。`;
  const driverForecastAxis = dominantFactor?.forecast || "模型暫以區間預測為主，等待價格與資金共振。";
  const driverFailure = macroTone === "down" && fundTone !== "up"
    ? "若美元利率續強且 ETF 未流入，偏多預測失效。"
    : model.riskScore >= 72
      ? "若 VIX 回落但白銀與礦商未接棒，避險行情可能退潮。"
      : "若價格突破但資金與礦商背離，預測需下修為區間。";
  const driverNextStep = Number.isFinite(silverLead) && silverLead > 0 && Number.isFinite(fundPulse) && fundPulse > 0
    ? "先看白銀、礦商與 ETF 是否連續領先；若續強，代表行情正在從黃金防禦擴散到高 Beta 標的。"
    : model.riskScore >= 72
      ? "先看黃金能否守穩，再看白銀與礦商是否補強，避免只追避險急漲。"
      : "先以區間判讀，等待美元利率、ETF 資金與工業金屬至少兩項同向。";
  const dominantScore = Math.round(clampAssetHubScore(dominantFactor?.score ?? 50, 0, 100));
  const metalMomentum = [
    { label: "黃金", value: goldPct },
    { label: "白銀", value: silverPct },
    { label: "鉑金", value: platinumPct },
    { label: "鈀金", value: palladiumPct },
  ].filter((item) => Number.isFinite(item.value));
  const strongestMetal = [...metalMomentum].sort((left, right) => right.value - left.value)[0] || null;
  const weakestMetal = [...metalMomentum].sort((left, right) => left.value - right.value)[0] || null;
  const forecastBias = fundTone === "up" && Number.isFinite(silverLead) && silverLead > 0
    ? {
      label: "擴散偏多",
      detail: "資金與白銀同時轉強，預測可由黃金防禦延伸到白銀與礦商彈性。",
      base: "基準路徑：偏多仍以擴散行情為主，黃金提供底部支撐，白銀與礦商負責彈性。",
      upgrade: "追價條件：ETF、礦商連續轉強，且 DXY 或 10Y 不再同步上壓。",
      downgrade: "降級警戒：金銀比回升或白銀轉弱，代表擴散行情退回黃金防禦。",
    }
    : macroTone === "down" && fundTone !== "up"
      ? {
        label: "壓力區間",
        detail: "美元利率壓力仍在，預測需降低追價假設，先看支撐與波動區間。",
        base: "基準路徑：價格以區間震盪為主，黃金抗跌性優於工業金屬。",
        upgrade: "轉強條件：美元或 10Y 轉弱，黃金仍守高檔並帶動 ETF 回流。",
        downgrade: "降級警戒：美元利率續強且礦商走弱，20日目標需保守下修。",
      }
      : model.riskScore >= 72
        ? {
          label: "黃金防禦",
          detail: "避險需求主導，預測重心先放在黃金支撐，白銀與鉑鈀等補強確認。",
          base: "基準路徑：黃金維持防禦溢價，白銀與鉑鈀需等待風險偏好回穩。",
          upgrade: "轉強條件：VIX 高檔但美元未續強，ETF 與礦商同步補量。",
          downgrade: "降級警戒：VIX 回落且資金未接棒，避險買盤可能快速退潮。",
        }
        : {
          label: "等待共振",
          detail: "單一因子不足以推升預測信心，需等待價格、資金、美元利率至少兩項同向。",
          base: "基準路徑：維持區間模型，短線以 1日與5日目標作風險控管。",
          upgrade: "轉強條件：ETF、礦商或工業金屬補強，推升20日預測彈性。",
          downgrade: "降級警戒：價格突破但量能與資金背離，模型降回中性震盪。",
        };
  const driverPulse = [
    ["主導因子", dominantFactor?.label || "--", `分數 ${dominantScore}/100；${dominantFactor?.status || "同步中"}`],
    ["預測傾向", forecastBias.label, forecastBias.detail],
    ["領先 / 落後", strongestMetal ? `${strongestMetal.label} ${formatAssetFinanceMetricPct(strongestMetal.value)}` : "--", weakestMetal ? `落後 ${weakestMetal.label} ${formatAssetFinanceMetricPct(weakestMetal.value)}；白銀相對黃金 ${silverLeadText}` : "金屬同步中"],
    ["資金驗證", driverFundingText, fundTone === "up" ? "資金與價格同向，延續性提高。" : fundTone === "down" ? "資金尚未跟上，追價需保守。" : "等待 ETF 與礦商同步。"],
  ];
  const driverScenarios = [
    ["基準路徑", forecastBias.base],
    ["轉強條件", forecastBias.upgrade],
    ["降級警戒", forecastBias.downgrade],
  ];
  return `
    <article class="panel-card asset-finance-module-card asset-finance-metal-driver-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Price drivers</p>
          <h4>貴金屬價格驅動因素</h4>
        </div>
        <span>${escapeHtml(dominantFactor?.label || "Macro + supply")}</span>
      </div>
      <div class="asset-finance-driver-factor-grid">
        ${factors.map(renderAssetFinanceDriverFactorCard).join("")}
      </div>
      <div class="asset-finance-driver-readout is-${escapeHtml(dominantFactor?.tone || "flat")}">
        <div class="asset-finance-driver-readout-head">
          <div>
            <small>目前主線</small>
            <strong>${escapeHtml(dominantFactor?.status || "等待資料同步")}</strong>
          </div>
          <span>${dominantScore}/100</span>
        </div>
        <div class="asset-finance-driver-pulse-row">
          ${driverPulse.map(([label, value, detail]) => `
            <span>
              <small>${escapeHtml(label)}</small>
              <b>${escapeHtml(value)}</b>
              <em>${escapeHtml(detail)}</em>
            </span>
          `).join("")}
        </div>
        <p class="asset-finance-driver-thesis"><b>AI 判讀</b>${escapeHtml(driverHeadline)}</p>
        <div class="asset-finance-driver-scenario-grid">
          ${driverScenarios.map(([label, text]) => `
            <section>
              <b>${escapeHtml(label)}</b>
              <small>${escapeHtml(text)}</small>
            </section>
          `).join("")}
        </div>
        <div class="asset-finance-driver-summary-grid">
          <span><b>預測主軸</b><small>${escapeHtml(driverForecastAxis)}</small></span>
          <span><b>模型驗證</b><small>${escapeHtml(driverConfirmation)}</small></span>
          <span><b>失效條件</b><small>${escapeHtml(driverFailure)}</small></span>
          <span><b>下一步觀察</b><small>${escapeHtml(driverNextStep)}</small></span>
        </div>
      </div>
    </article>
  `;
}

function renderAssetFinanceDecisionCenterPanel(model) {
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const platinumPct = parseMarketNumber(model.platinum?.pct);
  const palladiumPct = parseMarketNumber(model.palladium?.pct);
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const etfAvg = averageAssetFinancePct(model.globalMetalEtfs);
  const minerAvg = averageAssetFinancePct(model.minerStocks);
  const taiwanAvg = averageAssetFinancePct(model.taiwanMetalEtfs);
  const bestEtf = strongestAssetFinanceItem(model.globalMetalEtfs);
  const bestMiner = strongestAssetFinanceItem(model.minerStocks);
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : null;
  const minerSpread = Number.isFinite(minerAvg) && Number.isFinite(etfAvg) ? minerAvg - etfAvg : null;
  const metalPctValues = [goldPct, silverPct, platinumPct, palladiumPct].filter(Number.isFinite);
  const positiveMetals = metalPctValues.filter((value) => value > 0).length;
  const tenYear = model.yields[2] || {};
  const tenYearValue = tenYear.value;
  const expectedMetalCount = metalPctValues.length || 4;
  const globalMetalAvg = averageAssetFinanceValues(metalPctValues);
  const taiwanSpread = Number.isFinite(taiwanAvg) && Number.isFinite(globalMetalAvg) ? taiwanAvg - globalMetalAvg : null;
  const broadMetalStrength = positiveMetals >= Math.min(3, expectedMetalCount);
  const silverLeadership = Number.isFinite(silverLead) && silverLead > 0;
  const fundConfirmation = Number.isFinite(etfAvg) && Number.isFinite(minerAvg) && etfAvg > 0 && minerAvg > 0;
  const minerLeadership = Number.isFinite(minerSpread) && minerSpread > 0;
  const dxyPressure = Number.isFinite(dxyPct) && dxyPct > 0.35;
  const ratePressure = Number.isFinite(tenYearValue) && tenYearValue >= 4.2;
  const macroPressure = dxyPressure || ratePressure;
  const fundDrag = Number.isFinite(etfAvg) && Number.isFinite(minerAvg) && etfAvg <= 0 && minerAvg <= 0;
  const goldResilience = Number.isFinite(goldPct) && goldPct > 0;
  const hedgeDemand = model.riskScore >= 72;
  const pressureProfile = (() => {
    if (fundDrag && !macroPressure) {
      return {
        label: "資金斷層",
        action: "美元與 10Y 尚未形成明顯壓力，但 ETF 與礦商沒有跟上，先判定為資金斷層，等待買盤確認再提高權重。",
        focus: "價格若走強但 ETF / 礦商背離，決策重心要放在延續性，而不是單日漲跌。",
        unlock: "ETF 與礦商任一組轉正，且金銀比不再惡化。",
        risk: "資金未回流時，金屬上漲可能缺乏第二段推力。",
      };
    }
    if (!macroPressure || fundConfirmation) return null;
    if (dxyPressure && ratePressure) {
      return {
        label: "雙壓觀望",
        action: goldResilience
          ? "美元與 10Y 同時施壓，但黃金仍抗跌；先視為避險買盤測試，不急著追白銀與礦商。"
          : "美元與 10Y 同時施壓且黃金未抗跌，觀望層級提高，先等待利率或美元至少一項降溫。",
        focus: "雙壓環境下，偏多訊號需同時看到 ETF 回流與礦商止穩，否則容易只是短線反彈。",
        unlock: "DXY 轉弱或 10Y 回落，且 ETF / 礦商至少一項轉正。",
        risk: "雙壓未解除時，追價容易被美元與實質利率壓回。",
      };
    }
    if (dxyPressure) {
      return {
        label: "美元壓制",
        action: goldResilience
          ? "美元走強但黃金仍抗跌，代表避險或通膨買盤仍在；先看金價能否守住，白銀等補強。"
          : "美元走強正在壓制金屬彈性，先降低追價，等待 DXY 轉弱或資金流回補。",
        focus: "美元壓制時，黃金抗跌比白銀追漲更重要；ETF 流入是解除壓力的第一訊號。",
        unlock: "DXY 漲幅收斂，且黃金維持正報酬或 ETF 平均轉正。",
        risk: "美元續強會讓金屬上漲缺乏延續性。",
      };
    }
    if (ratePressure) {
      return {
        label: "利率壓制",
        action: goldResilience
          ? "10Y 殖利率偏高但黃金仍能守穩，先看作防禦需求支撐，需等礦商或 ETF 補量再提高曝險。"
          : "10Y 殖利率偏高使持有黃金的機會成本升高，先以區間與停損控管，不放大槓桿。",
        focus: "利率壓制時，礦商若弱於 ETF 代表市場仍不願意押槓桿彈性。",
        unlock: "10Y 回落或礦商平均轉強，並帶動白銀相對黃金改善。",
        risk: "殖利率續高會壓低無息資產估值，偏多情境需下修。",
      };
    }
    return null;
  })();
  let score = 50;
  if (Number.isFinite(goldPct)) score += clampAssetHubScore(goldPct * 5, -12, 12);
  if (silverLeadership) score += 4;
  if (broadMetalStrength) score += 5;
  if (Number.isFinite(dxyPct)) score += dxyPct < 0 ? 6 : -4;
  if (Number.isFinite(etfAvg)) score += clampAssetHubScore(etfAvg * 2, -6, 6);
  if (Number.isFinite(minerAvg)) score += clampAssetHubScore(minerAvg * 2, -6, 6);
  if (fundConfirmation) score += 5;
  if (hedgeDemand) score += 6;
  if (macroPressure && !fundConfirmation) score -= 5;
  score = Math.round(clampAssetHubScore(score, 0, 100));
  const label = score >= 70 && silverLeadership && fundConfirmation
    ? "多頭擴散"
    : score >= 70 && hedgeDemand
      ? "避險偏多"
      : pressureProfile
        ? pressureProfile.label
        : score >= 48 && hedgeDemand
        ? "高波動防守"
        : score >= 48
          ? "區間輪動"
          : "轉弱降槓桿";
  const action = label === "多頭擴散"
    ? "價格擴散與資金確認同時成立，可把觀察重心從黃金延伸到白銀、礦商與 ETF。"
    : label === "避險偏多"
      ? "避險分數支撐黃金核心，但加碼前仍要確認美元與 10Y 利率沒有同步上壓。"
      : pressureProfile
        ? pressureProfile.action
        : label === "高波動防守"
          ? "避險需求升溫但波動也升高，保留黃金核心，避免追價白銀與礦商。"
          : label === "區間輪動"
            ? "多空訊號尚未共振，等待價格、ETF、礦商或美元利率至少兩項轉為同向。"
            : "價格與資金面未修復，降低追價權重，等待金銀比或礦商先行止穩。";
  const evidenceCards = [
    {
      title: "價格證據",
      tone: broadMetalStrength ? "up" : positiveMetals === 0 ? "down" : "flat",
      value: `${positiveMetals}/${expectedMetalCount} 金屬走強`,
      detail: [
        `黃金 ${model.gold?.pct || "--"}`,
        `白銀 ${model.silver?.pct || "--"}`,
        Number.isFinite(silverLead) ? `白銀相對黃金 ${formatAssetFinancePct(silverLead)}` : "金銀相對強弱同步中",
      ].join("；"),
    },
    {
      title: "資金證據",
      tone: fundConfirmation ? "up" : Number.isFinite(etfAvg) && etfAvg < 0 && Number.isFinite(minerAvg) && minerAvg < 0 ? "down" : "flat",
      value: `ETF ${formatAssetFinancePct(etfAvg)} / 礦商 ${formatAssetFinancePct(minerAvg)}`,
      detail: fundConfirmation
        ? `${bestEtf ? `${bestEtf.symbol} ${bestEtf.pct || "--"}` : "ETF"} 與 ${bestMiner ? `${bestMiner.symbol} ${bestMiner.pct || "--"}` : "礦商"} 同向，趨勢確認度提高。`
        : minerLeadership
          ? `礦商強於 ETF ${formatAssetFinancePct(minerSpread)}，可觀察是否帶動 ETF 補強。`
          : "ETF 與礦商尚未同步，價格訊號暫不視為完整趨勢。",
    },
    {
      title: "總體牽制",
      tone: macroPressure ? "down" : Number.isFinite(dxyPct) && dxyPct < 0 ? "up" : "flat",
      value: `DXY ${model.dxy?.pct || "--"} / 10Y ${formatAssetHubYield(tenYearValue)}`,
      detail: pressureProfile
        ? pressureProfile.focus
        : macroPressure
        ? "美元或殖利率壓力仍在，金屬上漲需靠 ETF 流入或避險需求抵消。"
        : "總體壓力未明顯升高，價格訊號可優先看資金與金銀比確認。",
    },
    {
      title: "台灣驗證",
      tone: Number.isFinite(taiwanSpread) ? assetFinancePctTone(taiwanSpread) : "flat",
      value: `${formatAssetFinancePct(taiwanAvg)} 平均`,
      detail: Number.isFinite(taiwanSpread)
        ? `台灣商品相對國際金屬 ${formatAssetFinancePct(taiwanSpread)}，需留意匯率、折溢價與交易時段差。`
        : "台灣貴金屬資料同步中，先以國際期貨與 ETF 作主要判讀。",
    },
  ];
  const entryBias = score >= 70
    ? "可保留偏多核心"
    : score >= 48
      ? "維持中性觀察"
      : "縮小風險曝險";
  const addCondition = fundConfirmation && (silverLeadership || broadMetalStrength) && !macroPressure
    ? "白銀、ETF、礦商已形成加碼條件"
    : pressureProfile
      ? pressureProfile.unlock
      : "等待白銀、ETF、礦商至少兩項補強";
  const riskCondition = pressureProfile
    ? pressureProfile.label
    : macroPressure
    ? "美元利率壓力偏高"
    : hedgeDemand
      ? "避險波動偏高"
      : "目前風險中性";
  const pressureSource = dxyPressure && ratePressure
    ? "美元與 10Y 同時偏強"
    : dxyPressure
      ? "美元走強"
      : ratePressure
        ? "10Y 殖利率偏高"
        : fundDrag
          ? "ETF 與礦商資金未跟上"
          : "";
  const aiConclusion = (() => {
    if (pressureProfile) {
      return `AI 結論：目前屬於「${pressureProfile.label}」，主因是${pressureSource}；解除觀望需看到 ${pressureProfile.unlock}`;
    }
    if (label === "多頭擴散") {
      return `AI 結論：價格擴散與資金確認同時成立，${positiveMetals}/${expectedMetalCount} 項金屬走強，白銀相對黃金 ${formatAssetFinancePct(silverLead)}，可視為偏多延伸行情。`;
    }
    if (label === "避險偏多") {
      return `AI 結論：避險需求支撐黃金核心，風險分數 ${model.riskScore}/100；若美元與 10Y 未再上壓，可維持防禦型偏多。`;
    }
    if (label === "高波動防守") {
      return `AI 結論：避險訊號偏強但波動同步升高，黃金優先於白銀與礦商，策略重點是控槓桿與等回檔確認。`;
    }
    if (label === "區間輪動") {
      return `AI 結論：多空訊號尚未共振，價格、資金與總體條件互相拉扯，暫以區間輪動與等待確認為主。`;
    }
    return `AI 結論：價格與資金面偏弱，尚未形成有效修復訊號，應降低追價並等待金銀比或礦商先止穩。`;
  })();
  const decisionPaths = [
    {
      title: "目前動作",
      tone: score >= 70 ? "up" : score < 48 ? "down" : "flat",
      value: entryBias,
      detail: action,
    },
    {
      title: "加碼條件",
      tone: fundConfirmation && (silverLeadership || broadMetalStrength) ? "up" : "flat",
      value: fundConfirmation && (silverLeadership || broadMetalStrength) ? "可分批提高" : "等待資金補強",
      detail: fundConfirmation
        ? `${addCondition}；下一步看白銀與鉑鈀是否延續，避免只押單一黃金訊號。`
        : `${addCondition}；資金未同步前，偏多預測只作觀察，不直接放大槓桿。`,
    },
    {
      title: "降級條件",
      tone: macroPressure || model.riskScore >= 78 ? "down" : "flat",
      value: riskCondition,
      detail: pressureProfile
        ? pressureProfile.risk
        : macroPressure
        ? "若 DXY 或 10Y 持續走強，同時 ETF / 礦商未補量，偏多判讀降為區間。"
        : "若 VIX 升、美元升、礦商弱，降低追價權重並回到黃金核心。",
    },
  ];
  const checklist = [
    ["成立條件", `${score}/100`, `${label}：${entryBias}`],
    ["加碼訊號", fundConfirmation ? "已確認" : "等待", addCondition],
    ["壓力來源", pressureProfile ? pressureProfile.label : macroPressure ? "總體壓力" : "未啟動", pressureProfile ? pressureProfile.focus : macroPressure ? "美元利率續強且資金未流入。" : "若資金背離或金銀比轉弱再降級。"],
    ["下一步驗證", `信心 ${model.confidence}`, Number.isFinite(taiwanSpread) ? "對照台灣商品與國際金屬是否隔日同向。" : "等待台灣商品同步後再做在地確認。"],
  ];
  const venueInsight = buildAssetFinanceGlobalVenueInsight(model);
  return `
    <article class="panel-card asset-finance-module-card asset-finance-decision-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI Decision Center</p>
          <h4>全球貴金屬 AI 決策中心</h4>
        </div>
        <span>${score} / 100 · ${escapeHtml(label)}</span>
      </div>
      <div class="asset-finance-decision-brief">
        <strong>${escapeHtml(label)}</strong>
        <p>${escapeHtml(aiConclusion)} 模型信心 ${model.confidence}；${escapeHtml(action)}</p>
      </div>
      <div class="asset-finance-decision-venue">
        <div class="asset-finance-decision-section-head">
          <div>
            <p class="panel-kicker">Global venues</p>
            <h5>全球交易市場 AI 場域判讀</h5>
          </div>
          <span>現貨 / 期貨 / 實需</span>
        </div>
        <p class="asset-finance-market-brief">${escapeHtml(venueInsight.venueConclusion)}</p>
        <div class="asset-finance-market-list">
          ${venueInsight.markets.map(([name, role, text]) => `<span><b>${escapeHtml(name)}</b><em>${escapeHtml(role)}</em><small>${escapeHtml(text)}</small></span>`).join("")}
        </div>
      </div>
      <div class="asset-finance-decision-grid">
        ${evidenceCards.map((item) => `
          <section class="is-${escapeHtml(item.tone)}">
            <small>${escapeHtml(item.title)}</small>
            <strong>${escapeHtml(item.value)}</strong>
            <p>${escapeHtml(item.detail)}</p>
          </section>
        `).join("")}
      </div>
      <div class="asset-finance-decision-section-head is-compact">
        <div>
          <p class="panel-kicker">Action path</p>
          <h5>AI 行動路徑</h5>
        </div>
        <span>動作 / 加碼 / 降級</span>
      </div>
      <div class="asset-finance-decision-paths">
        ${decisionPaths.map((item) => `
          <section class="is-${escapeHtml(item.tone)}">
            <small>${escapeHtml(item.title)}</small>
            <strong>${escapeHtml(item.value)}</strong>
            <p>${escapeHtml(item.detail)}</p>
          </section>
        `).join("")}
      </div>
      <div class="asset-finance-decision-section-head is-compact">
        <div>
          <p class="panel-kicker">Decision checks</p>
          <h5>檢核門檻</h5>
        </div>
        <span>分數 / 資金 / 壓力 / 驗證</span>
      </div>
      <div class="asset-finance-decision-checklist">
        ${checklist.map(([name, value, detail]) => `
          <span>
            <b>${escapeHtml(name)}</b>
            <strong>${escapeHtml(value)}</strong>
            <small>${escapeHtml(detail)}</small>
          </span>
        `).join("")}
      </div>
      <p class="stock-theory-note">研究訊號以線上行情、台灣備援資料、ETF / 礦商相對強弱與總體因子計算，作為市場判讀參考。</p>
    </article>
  `;
}

function renderAssetFinanceEtfRows(items = [], maxRows = 24) {
  return items.slice(0, maxRows).map((item) => {
    const metric = getAssetHubMetric(item);
    return `
      <tr>
        <td><a class="global-market-link" href="${safeUrl(getAssetHubItemUrl(item))}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.name || "--")}</a></td>
        <td>${escapeHtml(item.symbol || "--")}</td>
        <td>${escapeHtml(getAssetHubRegion(item))}</td>
        <td>${formatGlobalValue(item.close)}</td>
        <td class="${assetHubTone(item)}">${escapeHtml(item.pct || "--")}</td>
        <td>${formatGlobalVolume(metric.value)}</td>
        <td>${escapeHtml(item.periodReturn || "--")}</td>
      </tr>
    `;
  }).join("");
}

function renderAssetFinanceSelectableEtfRows(items = [], activeSymbol = "", maxRows = 24) {
  const active = String(activeSymbol || "").toUpperCase();
  return items.slice(0, maxRows).map((item) => {
    const symbol = String(item?.symbol || "").toUpperCase();
    const metric = getAssetHubMetric(item);
    return `
      <tr class="${symbol === active ? "is-active" : ""}" data-asset-finance-volume-row="${escapeHtml(symbol)}">
        <td><button class="asset-finance-etf-select" type="button" data-asset-finance-volume-symbol="${escapeHtml(symbol)}">${escapeHtml(item.name || "--")}</button></td>
        <td>${escapeHtml(item.symbol || "--")}</td>
        <td>${escapeHtml(getAssetHubRegion(item))}</td>
        <td>${formatGlobalValue(item.close)}</td>
        <td class="${assetHubTone(item)}">${escapeHtml(item.pct || "--")}</td>
        <td>${formatGlobalVolume(metric.value)}</td>
        <td>${escapeHtml(item.periodReturn || "--")}</td>
      </tr>
    `;
  }).join("");
}

function renderAssetFinanceSelectableMetalOnlineRows(items = [], activeSymbol = "") {
  const active = String(activeSymbol || "").toUpperCase();
  return items.map((item) => {
    const symbol = String(item?.symbol || "").toUpperCase();
    const metric = getAssetHubMetric(item);
    return `
      <tr class="${symbol === active ? "is-active" : ""}" data-asset-finance-volume-row="${escapeHtml(symbol)}">
        <td><button class="asset-finance-etf-select" type="button" data-asset-finance-volume-symbol="${escapeHtml(symbol)}">${escapeHtml(item.name || "--")}</button></td>
        <td>${escapeHtml(item.symbol || "--")}</td>
        <td>${escapeHtml(getAssetHubRegion(item))}</td>
        <td>${escapeHtml(item.exchange || item.dataSource || "--")}</td>
        <td>${escapeHtml(item.type || item.group || "--")}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.close)}</td>
        <td class="${assetHubTone(item)}">${escapeHtml(item.error ? "同步中" : item.pct || "--")}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.open)}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.high)}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.low)}</td>
        <td><span class="asset-table-metric">${escapeHtml(metric.label)}</span>${item.error ? "--" : formatGlobalVolume(metric.value)}</td>
        <td>${escapeHtml(item.date || "--")}</td>
      </tr>
    `;
  }).join("");
}

function renderAssetFinanceSelectableBondOnlineRows(items = [], activeSymbol = "") {
  const active = String(activeSymbol || "").toUpperCase();
  return items.map((item) => {
    const symbol = String(item?.symbol || "").toUpperCase();
    const metric = getAssetHubMetric(item);
    return `
      <tr class="${symbol === active ? "is-active" : ""}" data-asset-finance-volume-row="${escapeHtml(symbol)}">
        <td><button class="asset-finance-etf-select" type="button" data-asset-finance-volume-symbol="${escapeHtml(symbol)}">${escapeHtml(item.name || "--")}</button></td>
        <td>${escapeHtml(item.symbol || "--")}</td>
        <td>${escapeHtml(getAssetHubRegion(item))}</td>
        <td>${escapeHtml(item.exchange || item.dataSource || "--")}</td>
        <td>${escapeHtml(item.type || item.group || "--")}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.close)}</td>
        <td class="${assetHubTone(item)}">${escapeHtml(item.error ? "同步中" : item.pct || "--")}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.open)}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.high)}</td>
        <td>${item.error ? "--" : formatGlobalValue(item.low)}</td>
        <td><span class="asset-table-metric">${escapeHtml(metric.label)}</span>${item.error ? "--" : formatGlobalVolume(metric.value)}</td>
        <td>${escapeHtml(item.date || "--")}</td>
      </tr>
    `;
  }).join("");
}

function buildAssetFinanceMetalsEtfConclusion(items = [], { avgPct = null, best = null, weakest = null } = {}) {
  const usable = items.filter((item) => Number.isFinite(parseMarketNumber(item?.pct)));
  const physicalEtfs = usable.filter((item) => {
    const type = String(item.type || "");
    return type.includes("ETF") && !type.includes("礦業") && getAssetHubRegion(item) !== "台灣";
  });
  const miningEtfs = usable.filter((item) => String(item.type || "").includes("礦業"));
  const taiwanEtfs = usable.filter((item) => getAssetHubRegion(item) === "台灣");
  const physicalAvg = averageAssetFinancePct(physicalEtfs);
  const miningAvg = averageAssetFinancePct(miningEtfs);
  const taiwanAvg = averageAssetFinancePct(taiwanEtfs);
  const miningSpread = Number.isFinite(miningAvg) && Number.isFinite(physicalAvg) ? miningAvg - physicalAvg : null;
  const taiwanSpread = Number.isFinite(taiwanAvg) && Number.isFinite(physicalAvg) ? taiwanAvg - physicalAvg : null;
  const tone = Number.isFinite(avgPct) && avgPct > 0.45
    ? "up"
    : Number.isFinite(avgPct) && avgPct < -0.45
      ? "down"
      : "flat";
  let thesis = "ETF 線上行情仍在補齊，先用已同步標的觀察資金是否集中於黃金、白銀或礦業槓桿。";
  if (Number.isFinite(miningSpread) && miningSpread > 0.8 && Number.isFinite(miningAvg) && miningAvg > 0) {
    thesis = "礦業 ETF 明顯強於實物 ETF，資金正在追逐金屬上漲的營運槓桿，行情偏進攻，但波動也會放大。";
  } else if (Number.isFinite(miningSpread) && miningSpread < -0.8 && Number.isFinite(physicalAvg) && physicalAvg > 0) {
    thesis = "實物 ETF 強於礦業 ETF，買盤偏向金屬本身與避險需求，趨勢確認度需等礦業 ETF 跟上。";
  } else if (Number.isFinite(physicalAvg) && Number.isFinite(miningAvg) && physicalAvg > 0 && miningAvg > 0) {
    thesis = "實物 ETF 與礦業 ETF 同步轉強，價格端與股權端有共振，偏多延續性較佳。";
  } else if (Number.isFinite(physicalAvg) && Number.isFinite(miningAvg) && physicalAvg < 0 && miningAvg < 0) {
    thesis = "實物 ETF 與礦業 ETF 同步偏弱，貴金屬資金面缺乏承接，先以防守與等待確認為主。";
  } else if (Number.isFinite(physicalAvg) && Number.isFinite(miningAvg)) {
    thesis = "實物 ETF 與礦業 ETF 走勢分歧，市場仍在避險金屬與景氣槓桿之間拉扯，需等待強弱收斂。";
  } else if (Number.isFinite(avgPct) && avgPct > 0) {
    thesis = "已同步 ETF 平均仍為正報酬，短線資金偏向承接貴金屬題材，但仍需觀察礦業 ETF 是否補強。";
  } else if (Number.isFinite(avgPct) && avgPct < 0) {
    thesis = "已同步 ETF 平均偏弱，短線資金沒有明顯回流，追價前需等待實物 ETF 或礦業 ETF 重新轉強。";
  }
  const relative = Number.isFinite(taiwanSpread)
    ? `台灣商品平均 ${formatAssetFinancePct(taiwanAvg)}，相對國際實物 ETF ${taiwanSpread >= 0 ? "高" : "低"} ${Math.abs(taiwanSpread).toFixed(2)} 個百分點，需留意交易時差與匯率影響。`
    : "台灣商品與國際 ETF 的同步差仍在補資料，暫以國際 ETF 與礦業 ETF 強弱為主。";
  const leader = best
    ? `相對強勢為 ${best.symbol || "--"} ${best.pct || "--"}`
    : "相對強勢標的同步中";
  const laggard = weakest
    ? `相對弱勢為 ${weakest.symbol || "--"} ${weakest.pct || "--"}`
    : "相對弱勢標的同步中";
  return {
    tone,
    text: `${thesis} ${leader}，${laggard}。${relative}`,
  };
}

function renderAssetFinanceEtfPanel(items = [], title = "ETF 比較", kicker = "ETF comparison", emptyText = "ETF 線上行情同步中。", options = {}) {
  const maxRows = Number.isFinite(options.maxRows) ? options.maxRows : 24;
  const sorted = [...items]
    .sort((left, right) => Math.abs(parseMarketNumber(right.pct) || 0) - Math.abs(parseMarketNumber(left.pct) || 0));
  const avgPct = averageAssetFinancePct(sorted);
  const best = strongestAssetFinanceItem(sorted);
  const weakest = sorted
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(left.pct) || 999) - (parseMarketNumber(right.pct) || 999))[0] || null;
  const shownCount = Math.min(sorted.length, maxRows);
  const analysis = options.analysisMode === "metals"
    ? buildAssetFinanceMetalsEtfConclusion(sorted, { avgPct, best, weakest })
    : null;
  return `
    <article class="panel-card asset-finance-etf-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">${escapeHtml(kicker)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
        <span>${shownCount === sorted.length ? `${sorted.length} 檔線上行情` : `顯示 ${shownCount} / ${sorted.length} 檔`}</span>
      </div>
      <div class="asset-finance-etf-summary">
        <span><small>平均漲跌</small><b class="${assetFinancePctTone(avgPct)}">${formatAssetFinancePct(avgPct)}</b></span>
        <span><small>相對強勢</small><b>${best ? `${escapeHtml(best.symbol)} ${escapeHtml(best.pct || "--")}` : "--"}</b></span>
        <span><small>相對弱勢</small><b>${weakest ? `${escapeHtml(weakest.symbol)} ${escapeHtml(weakest.pct || "--")}` : "--"}</b></span>
      </div>
      ${analysis ? `<p class="asset-finance-etf-brief is-${escapeHtml(analysis.tone)}"><b>AI 結論</b><span>${escapeHtml(analysis.text)}</span></p>` : ""}
      <div class="global-table-wrap asset-finance-table-wrap">
        <table class="global-market-table">
          <thead><tr><th>名稱</th><th>代號</th><th>地區</th><th>收盤</th><th>日漲跌</th><th>成交量</th><th>一年區間</th></tr></thead>
          <tbody>${renderAssetFinanceEtfRows(sorted, maxRows) || `<tr><td colspan="7">${escapeHtml(emptyText)}</td></tr>`}</tbody>
        </table>
      </div>
    </article>
  `;
}

function renderAssetFinanceVolumeTrendChart(item, label = "走勢與成交量") {
  const rows = normalizeGlobalOhlcvSeries(item?.series || []).slice(-24);
  if (rows.length < 2) {
    return `
      <div class="asset-finance-volume-chart">
        <div class="asset-finance-volume-chart-head">
          <span><small>Trend / volume</small><b>${escapeHtml(label)}</b></span>
          <em>資料同步中</em>
        </div>
        <p class="stock-detail-empty">走勢與成交量資料不足，暫無法繪製柱狀圖。</p>
      </div>
    `;
  }
  const width = 920;
  const height = 300;
  const pad = { top: 24, right: 24, bottom: 36, left: 52 };
  const priceHeight = 166;
  const volumeTop = pad.top + priceHeight + 22;
  const volumeHeight = height - volumeTop - pad.bottom;
  const plotWidth = width - pad.left - pad.right;
  const closes = rows.map((row) => row.close).filter(Number.isFinite);
  const volumes = rows.map((row) => row.volume || 0);
  const minClose = Math.min(...closes);
  const maxClose = Math.max(...closes);
  const closeSpan = maxClose - minClose || 1;
  const maxVolume = Math.max(...volumes, 1);
  const xFor = (index) => pad.left + (index / Math.max(rows.length - 1, 1)) * plotWidth;
  const yForClose = (value) => pad.top + ((maxClose - value) / closeSpan) * priceHeight;
  const barWidth = Math.max(6, plotWidth / rows.length * 0.58);
  const points = rows.map((row, index) => ({
    x: xFor(index),
    y: yForClose(row.close),
    value: row.close,
    close: row.close,
    volume: row.volume || 0,
    pct: index > 0 && rows[index - 1]?.close ? ((row.close / rows[index - 1].close) - 1) * 100 : null,
    date: row.date,
  }));
  const path = buildPath(points);
  const first = rows[0];
  const last = rows.at(-1);
  const changePct = first?.close ? ((last.close / first.close) - 1) * 100 : null;
  const avgVolume = averageAssetFinanceValues(volumes.filter((value) => value > 0));
  return `
    <div class="asset-finance-volume-chart">
      <div class="asset-finance-volume-chart-head">
        <span><small>Trend / volume</small><b>${escapeHtml(label)}</b></span>
        <em>${escapeHtml(item?.symbol || "--")} · ${formatAssetFinancePct(changePct)} · 均量 ${formatGlobalVolume(avgVolume)}</em>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(label)}走勢與成交量柱狀圖">
        <rect class="asset-finance-volume-bg" x="${pad.left}" y="${pad.top}" width="${plotWidth}" height="${priceHeight}"></rect>
        <line class="asset-finance-volume-grid" x1="${pad.left}" y1="${yForClose(maxClose).toFixed(2)}" x2="${width - pad.right}" y2="${yForClose(maxClose).toFixed(2)}"></line>
        <line class="asset-finance-volume-grid" x1="${pad.left}" y1="${yForClose(minClose).toFixed(2)}" x2="${width - pad.right}" y2="${yForClose(minClose).toFixed(2)}"></line>
        <text class="asset-finance-volume-axis" x="${pad.left - 10}" y="${(yForClose(maxClose) + 4).toFixed(2)}" text-anchor="end">${formatGlobalValue(maxClose)}</text>
        <text class="asset-finance-volume-axis" x="${pad.left - 10}" y="${(yForClose(minClose) + 4).toFixed(2)}" text-anchor="end">${formatGlobalValue(minClose)}</text>
        <path class="asset-finance-volume-area" d="${path} L ${points.at(-1).x.toFixed(2)} ${(pad.top + priceHeight).toFixed(2)} L ${points[0].x.toFixed(2)} ${(pad.top + priceHeight).toFixed(2)} Z"></path>
        <path class="asset-finance-volume-line" d="${path}"></path>
        ${rows.map((row, index) => {
          const barHeight = ((row.volume || 0) / maxVolume) * volumeHeight;
          const x = xFor(index) - barWidth / 2;
          const y = volumeTop + volumeHeight - barHeight;
          const isUp = index === 0 || row.close >= rows[index - 1].close;
          return `<rect class="asset-finance-volume-bar ${isUp ? "is-up" : "is-down"}" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${Math.max(1, barHeight).toFixed(2)}"></rect>`;
        }).join("")}
        <line class="asset-finance-volume-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${(volumeTop + volumeHeight).toFixed(2)}" data-asset-finance-volume-crosshair-x></line>
        <line class="asset-finance-volume-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${width - pad.right}" y2="${pad.top}" data-asset-finance-volume-crosshair-y></line>
        <circle class="asset-finance-volume-crosshair-dot" cx="${pad.left}" cy="${pad.top}" r="4.5" data-asset-finance-volume-crosshair-dot></circle>
        ${points.map((point, index) => {
          const previousX = index > 0 ? points[index - 1].x : pad.left;
          const nextX = index < points.length - 1 ? points[index + 1].x : width - pad.right;
          const zoneWidth = Math.max(8, (nextX - previousX) / 2);
          return `<rect class="asset-finance-volume-hover-zone" x="${(point.x - zoneWidth / 2).toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${(volumeTop + volumeHeight - pad.top).toFixed(2)}" data-x="${point.x.toFixed(2)}" data-y="${point.y.toFixed(2)}" data-date="${escapeHtml(point.date)}" data-close="${escapeHtml(formatGlobalValue(point.close))}" data-pct="${escapeHtml(formatAssetFinancePct(point.pct))}" data-volume="${escapeHtml(formatGlobalVolume(point.volume))}"></rect>`;
        }).join("")}
        <text class="asset-finance-volume-date" x="${pad.left}" y="${height - 12}" text-anchor="start">${escapeHtml(first.date)}</text>
        <text class="asset-finance-volume-date" x="${width - pad.right}" y="${height - 12}" text-anchor="end">${escapeHtml(last.date)}</text>
      </svg>
      <div class="asset-finance-volume-tooltip" hidden></div>
    </div>
  `;
}

function getAssetFinanceVolumePayloadItem(item = {}) {
  return {
    symbol: item.symbol || "",
    name: item.name || item.symbol || "",
    type: item.type || item.group || "",
    group: item.group || "",
    region: getAssetHubRegion(item),
    exchange: item.exchange || item.dataSource || "",
    dataSource: item.dataSource || "",
    close: item.close,
    open: item.open,
    high: item.high,
    low: item.low,
    pct: item.pct,
    volume: item.volume,
    volumeValue: item.volumeValue,
    periodReturn: item.periodReturn,
    date: item.date,
    series: Array.isArray(item.series) ? item.series : [],
  };
}

function renderAssetFinanceSingleTrendRiskAnalysis(item = {}) {
  const rows = normalizeGlobalOhlcvSeries(item?.series || []).slice(-24);
  const latest = rows.at(-1);
  const previous = rows.at(-2);
  const close = latest?.close ?? parseMarketNumber(item?.close);
  const dayPct = latest && previous?.close ? ((latest.close / previous.close) - 1) * 100 : parseMarketNumber(item?.pct);
  const valueAt = (days) => rows.length > days ? rows[rows.length - 1 - days]?.close : null;
  const momentum5 = Number.isFinite(close) && Number.isFinite(valueAt(5)) && valueAt(5) > 0 ? ((close / valueAt(5)) - 1) * 100 : null;
  const momentum20 = Number.isFinite(close) && Number.isFinite(valueAt(20)) && valueAt(20) > 0 ? ((close / valueAt(20)) - 1) * 100 : null;
  const returns = [];
  for (let index = 1; index < rows.length; index += 1) {
    const prev = rows[index - 1]?.close;
    const current = rows[index]?.close;
    if (Number.isFinite(prev) && prev > 0 && Number.isFinite(current)) returns.push(((current / prev) - 1) * 100);
  }
  const volatility = standardDeviationAssetFinanceValues(returns);
  const highClose = Math.max(...rows.map((row) => row.close).filter(Number.isFinite), close || 0);
  const drawdown = Number.isFinite(close) && highClose > 0 ? ((close / highClose) - 1) * 100 : null;
  const volumes = rows.map((row) => row.volume || 0).filter((value) => value > 0);
  const avgVolume = averageAssetFinanceValues(volumes.slice(-10));
  const latestVolume = latest?.volume || parseMarketNumber(item?.volumeValue ?? item?.volume);
  const volumeRatio = Number.isFinite(latestVolume) && Number.isFinite(avgVolume) && avgVolume > 0 ? latestVolume / avgVolume : null;
  const trendTone = Number.isFinite(momentum20) && momentum20 > 6 && Number.isFinite(momentum5) && momentum5 > 0
    ? "up"
    : Number.isFinite(momentum20) && momentum20 < -6
      ? "down"
      : "flat";
  const riskScore = clampAssetHubScore(
    42
      + (Number.isFinite(volatility) ? volatility * 9 : 8)
      + (Number.isFinite(drawdown) ? Math.abs(Math.min(drawdown, 0)) * 1.4 : 0)
      + (Number.isFinite(volumeRatio) && volumeRatio > 1.8 ? 8 : 0),
    20,
    92,
  );
  const riskTone = riskScore >= 68 ? "down" : riskScore >= 48 ? "flat" : "up";
  const trendText = trendTone === "up"
    ? "近 20 日趨勢偏多，短線動能仍有延續條件。"
    : trendTone === "down"
      ? "近 20 日趨勢偏弱，反彈需要先觀察量價是否止穩。"
      : "近 20 日偏區間整理，方向仍需等待突破或跌破確認。";
  const riskText = riskTone === "down"
    ? "波動或回撤偏高，追價風險較大，需用成交量與支撐位控管。"
    : riskTone === "up"
      ? "波動與回撤相對溫和，風險結構較穩，但仍需避免單日量縮追高。"
      : "風險屬中性，適合用分批與停損距離管理波動。";
  const volumeText = Number.isFinite(volumeRatio)
    ? volumeRatio >= 1.35
      ? `最新成交量為 10 日均量 ${volumeRatio.toFixed(2)} 倍，量能有放大跡象。`
      : volumeRatio <= 0.75
        ? `最新成交量僅 10 日均量 ${volumeRatio.toFixed(2)} 倍，動能確認度偏低。`
        : `最新成交量約為 10 日均量 ${volumeRatio.toFixed(2)} 倍，量能大致正常。`
    : "成交量均值仍在同步中，量能判讀暫以圖表柱狀變化為主。";
  return `
    <div class="asset-finance-single-ai is-${riskTone}" data-asset-finance-single-analysis>
      <div class="asset-finance-single-ai-head">
        <span><small>Single asset AI</small><b>${escapeHtml(item?.name || item?.symbol || "--")}</b></span>
        <em>${escapeHtml(item?.symbol || "--")} · ${escapeHtml(item?.type || "")}</em>
      </div>
      <div class="asset-finance-single-ai-grid">
        <span><small>趨勢</small><b class="${trendTone}">${formatAssetFinancePct(momentum20)}</b><em>${escapeHtml(trendText)}</em></span>
        <span><small>風險</small><b class="${riskTone}">${Math.round(riskScore)}/100</b><em>${escapeHtml(riskText)}</em></span>
        <span><small>波動</small><b>${formatAssetFinancePct(volatility)}</b><em>近 24 日日報酬標準差</em></span>
        <span><small>成交量</small><b>${formatGlobalVolume(latestVolume)}</b><em>${escapeHtml(volumeText)}</em></span>
      </div>
      <p>${escapeHtml(`AI 分析：${trendText} ${riskText} ${volumeText} 目前收盤 ${formatGlobalValue(close)}，日漲跌 ${formatAssetFinancePct(dayPct)}，近高點回撤 ${formatAssetFinancePct(drawdown)}。`)}</p>
    </div>
  `;
}

function getAssetFinanceBondProfile(item = {}) {
  const symbol = String(item?.symbol || "").toUpperCase();
  const text = `${item?.name || ""} ${item?.type || ""} ${item?.group || ""} ${item?.exchange || ""}`.toLowerCase();
  let duration = {
    label: "綜合久期",
    score: 52,
    note: "同時承受短端與長端利率變化，適合作為核心債券配置觀察。",
  };
  if (["BIL", "SGOV", "SHY", "VGSH", "USFR"].includes(symbol) || /short|ultra.?short|floating|t-bill|貨幣|短天期/.test(text)) {
    duration = {
      label: "短天期 / 浮動利率",
      score: 24,
      note: "價格對利率變動較不敏感，主要風險在再投資利率與收益下修。",
    };
  } else if (["IEF", "VGIT"].includes(symbol) || /intermediate|中天期|7-10/.test(text)) {
    duration = {
      label: "中天期核心債",
      score: 48,
      note: "兼具收益與價格彈性，適合觀察 5Y 至 10Y 殖利率變化。",
    };
  } else if (["TLT", "VGLT"].includes(symbol) || /long|20\+|20 year|長天期/.test(text)) {
    duration = {
      label: "長天期高久期",
      score: 82,
      note: "對降息預期最敏感，但殖利率上行時回撤也會明顯放大。",
    };
  } else if (["BND", "AGG", "BNDX"].includes(symbol) || /aggregate|total bond|總債|綜合/.test(text)) {
    duration = {
      label: "綜合核心債",
      score: 55,
      note: "分散不同天期與債種，適合用來看整體債市風向。",
    };
  }

  let credit = {
    label: "投資級債券",
    score: 34,
    note: "信用風險相對可控，主要觀察利率與信用利差變化。",
  };
  if (["HYG", "JNK"].includes(symbol) || /high yield|junk|高收益|非投資/.test(text)) {
    credit = {
      label: "高收益 / 非投資級",
      score: 74,
      note: "殖利率補償較高，但景氣放緩時需優先監控信用利差與違約風險。",
    };
  } else if (["LQD"].includes(symbol) || /corporate|公司債|投資級/.test(text)) {
    credit = {
      label: "投資級公司債",
      score: 46,
      note: "同時受利率與企業信用利差影響，需看評等與產業循環。",
    };
  } else if (["TIP"].includes(symbol) || /tips|inflation|抗通膨|通膨/.test(text)) {
    credit = {
      label: "抗通膨公債",
      score: 30,
      note: "信用風險偏低，重點在實質利率與通膨預期變化。",
    };
  } else if (/treasury|government|公債|美債|國債/.test(text) || ["SHY", "VGSH", "IEF", "VGIT", "TLT", "VGLT", "BIL", "SGOV", "USFR"].includes(symbol)) {
    credit = {
      label: "政府公債",
      score: 22,
      note: "信用風險低，價格主要由殖利率曲線與久期控制。",
    };
  } else if (/taiwan|twse|tpex|\.tw|\.two|台灣/.test(`${symbol} ${text}`)) {
    credit = {
      label: "台灣掛牌債券 ETF",
      score: 38,
      note: "需同時留意海外債券價格、匯率、折溢價與台灣交易時段落差。",
    };
  }
  return { duration, credit };
}

function getAssetFinanceBondEtfLens(item = {}) {
  const symbol = String(item?.symbol || "").toUpperCase();
  const text = `${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.region || ""} ${item?.market || ""} ${item?.exchange || ""}`.toLowerCase();
  const has = (pattern) => pattern.test(`${symbol} ${text}`);
  const isTaiwanListed = /\.TW$|\.TWO$/i.test(symbol) || /台灣|臺灣|tpex|twse/.test(text);
  let strategyBucket = "綜合債券";
  let role = "核心債券觀察";
  let centerUse = "放入債券 ETF 分析中心，和短債、核心債、長債、信用債比較廣度與強弱。";
  let taiwanUse = "台灣研究：若以台幣帳戶交易，需同步看折溢價、匯率與台灣交易時差。";
  let globalUse = "國際研究：用美債曲線、美元、VIX 與信用利差確認債券風險是否可承擔。";
  let keyRisk = "主要風險來自殖利率反向、流動性與信用利差變化。";

  if (has(/SHY|VGSH|BIL|SGOV|USFR|TFLO|short|短天|短債|貨幣|浮動|0-1|1-3/i)) {
    strategyBucket = "短天期 / 貨幣市場";
    role = "現金替代與短端防守";
    centerUse = "用來確認資金是否偏向避險與等待利率訊號，適合和 2Y 殖利率、Fed Funds 對照。";
    globalUse = "國際研究：短端收益受政策利率與再投資收益支配，降息循環開始後殖利率可能逐步下修。";
    keyRisk = "降息後收益率下滑，價格彈性有限，過度集中會降低修復彈性。";
  } else if (has(/IEF|VGIT|BND|AGG|中天|核心|綜合|aggregate|3-7|5-10/i)) {
    strategyBucket = "中天期 / 核心綜合債";
    role = "核心配置與利率中樞觀察";
    centerUse = "作為 ETF 中心的核心債基準，拿來比較短債防守與長債修復誰佔優勢。";
    globalUse = "國際研究：對 5Y/10Y 殖利率敏感，需確認曲線倒掛是否收斂且通膨未再升溫。";
    keyRisk = "若中長端利率重新上行，淨值會受壓，但波動通常低於長天期公債。";
  } else if (has(/TLT|VGLT|EDV|GOVZ|20|30|長天|長債|long|10-20|15\+/i)) {
    strategyBucket = "長天期公債";
    role = "降息交易與高久期修復";
    centerUse = "放在 ETF 中心的高久期桶，和 10Y/30Y 殖利率及曲線斜率同步追蹤。";
    globalUse = "國際研究：長端價格高度受實質利率、期限溢酬與通膨預期影響。";
    keyRisk = "長端殖利率反彈時回撤會放大，不適合只因配息率高而追價。";
  } else if (has(/LQD|HYG|JNK|VCSH|VCIT|IGIB|SJNK|ANGL|corporate|公司|信用|high yield|高收益|非投資/i)) {
    strategyBucket = "信用債 / 高收益";
    role = "收益增強與信用風險交易";
    centerUse = "在 ETF 中心需和 LQD/HYG/JNK 同類比較，觀察利差補償是否足以承擔信用風險。";
    globalUse = "國際研究：信用債要和景氣、失業率、VIX 與高收益利差一起判讀。";
    keyRisk = "景氣轉弱或利差擴大時，可能和股票同步下跌。";
  } else if (has(/TIP|SCHP|VTIP|MUB|VTEB|MBB|VMBS|tips|inflation|抗通膨|通膨|市政|mbs/i)) {
    strategyBucket = "抗通膨 / 市政 / MBS";
    role = "特殊債種與利差觀察";
    centerUse = "用來補足 TIPS、MBS、市政債等非一般公債風險，避免只用殖利率曲線判斷。";
    globalUse = "國際研究：需拆開看實質利率、通膨預期、提前還款與流動性。";
    keyRisk = "利差、提前還款或通膨預期變化，可能讓價格表現不同於一般公債。";
  } else if (has(/BNDX|IAGG|EMB|international|emerging|global|全球|國際|新興|美元債|歐債|日債/i)) {
    strategyBucket = "全球 / 新興市場";
    role = "非美利率與美元信用風險";
    centerUse = "用來和美債核心桶比較，確認資金是否願意承擔匯率、主權與新興市場信用風險。";
    globalUse = "國際研究：同步看美元指數、ECB/BOJ 政策與新興市場利差。";
    keyRisk = "美元走強、主權利差擴大或新興市場資金流出時，價格容易受壓。";
  }

  if (isTaiwanListed) {
    return {
      bucket: "台灣債券 ETF",
      strategyBucket,
      role: `${role}，台灣掛牌追蹤`,
      centerUse: `先列入台灣債券 ETF，再和「${strategyBucket}」同類海外 ETF 比較折溢價、流動性與追蹤差。`,
      taiwanUse: "台灣研究：重點看台幣交易時段、匯率避險成本、折溢價與 ETF 規模是否支撐進出場。",
      globalUse,
      keyRisk: `${keyRisk} 台灣掛牌商品還需額外監控匯率、折溢價與海外市場開盤落差。`,
    };
  }

  return {
    bucket: strategyBucket,
    strategyBucket,
    role,
    centerUse,
    taiwanUse,
    globalUse,
    keyRisk,
  };
}

function renderAssetFinanceBondSingleAnalysis(item = {}) {
  if (!item || !item.symbol) {
    return `<p class="stock-detail-empty">請點選債券商品名稱，查看單一商品 AI 結論。</p>`;
  }
  const rows = normalizeGlobalOhlcvSeries(item?.series || []).slice(-24);
  const latest = rows.at(-1);
  const previous = rows.at(-2);
  const close = latest?.close ?? parseMarketNumber(item?.close);
  const dayPct = latest && previous?.close ? ((latest.close / previous.close) - 1) * 100 : parseMarketNumber(item?.pct);
  const valueAt = (days) => rows.length > days ? rows[rows.length - 1 - days]?.close : null;
  const momentum20 = Number.isFinite(close) && Number.isFinite(valueAt(20)) && valueAt(20) > 0 ? ((close / valueAt(20)) - 1) * 100 : null;
  const returns = [];
  for (let index = 1; index < rows.length; index += 1) {
    const prev = rows[index - 1]?.close;
    const current = rows[index]?.close;
    if (Number.isFinite(prev) && prev > 0 && Number.isFinite(current)) returns.push(((current / prev) - 1) * 100);
  }
  const volatility = standardDeviationAssetFinanceValues(returns);
  const highClose = Math.max(...rows.map((row) => row.close).filter(Number.isFinite), close || 0);
  const drawdown = Number.isFinite(close) && highClose > 0 ? ((close / highClose) - 1) * 100 : null;
  const latestVolume = latest?.volume || parseMarketNumber(item?.volumeValue ?? item?.volume);
  const profile = getAssetFinanceBondProfile(item);
  const etfLens = getAssetFinanceBondEtfLens(item);
  const trendTone = Number.isFinite(momentum20) && momentum20 > 1.2
    ? "up"
    : Number.isFinite(momentum20) && momentum20 < -1.2
      ? "down"
      : assetFinancePctTone(dayPct);
  const riskScore = clampAssetHubScore(
    24
      + profile.duration.score * 0.38
      + profile.credit.score * 0.34
      + (Number.isFinite(volatility) ? volatility * 7 : 5)
      + (Number.isFinite(drawdown) ? Math.abs(Math.min(drawdown, 0)) * 1.1 : 0),
    18,
    94,
  );
  const riskTone = riskScore >= 68 ? "down" : riskScore >= 48 ? "flat" : "up";
  const trendText = trendTone === "up"
    ? "價格動能偏正，若殖利率續降或信用利差未擴大，仍有延續條件。"
    : trendTone === "down"
      ? "價格動能偏弱，需等待殖利率壓力降溫或量價止穩。"
      : "價格偏整理，短線方向需等殖利率、信用利差或成交量提供確認。";
  const isShortDuration = profile.duration.score <= 30;
  const isLongDuration = profile.duration.score >= 70;
  const isHighYield = profile.credit.score >= 65;
  const isGovernment = profile.credit.label.includes("政府") || profile.credit.label.includes("公債");
  const isTaiwanListed = profile.credit.label.includes("台灣");
  const creditQualityScore = Math.round(clampAssetHubScore(
    100 - profile.credit.score + (isGovernment ? 8 : 0) - (isHighYield ? 6 : 0),
    12,
    98,
  ));
  const creditGrade = creditQualityScore >= 92
    ? "AAA"
    : creditQualityScore >= 84
      ? "AA"
      : creditQualityScore >= 74
        ? "A"
        : creditQualityScore >= 62
          ? "BBB"
          : creditQualityScore >= 48
            ? "BB"
            : creditQualityScore >= 34
              ? "B"
              : "CCC";
  const ratingBand = ["AAA", "AA", "A", "BBB"].includes(creditGrade) ? "投資級" : "非投資級";
  const ratingText = `模型估算 ${creditGrade} / ${creditQualityScore} 分，屬 ${ratingBand} 分層，非官方信評。`;
  const positionText = isShortDuration
    ? "偏現金管理與等待利率訊號，適合降低淨值波動。"
    : isLongDuration
      ? "偏降息交易與高久期防守，價格彈性高但不適合無停損追價。"
      : isHighYield
        ? "偏收益增強與信用風險交易，需和股票風險一起看。"
        : "偏核心債券配置，可用來平衡股票與商品資產波動。";
  const watchText = isLongDuration
    ? "優先看 10Y / 30Y 殖利率是否下行，若長端利率續升，價格容易再受壓。"
    : isShortDuration
      ? "優先看短端政策利率與再投資收益，下行循環開始後收益率可能逐步下降。"
      : isHighYield
        ? "優先看信用利差、景氣數據與高收益債資金流，利差擴大時不宜只看殖利率。"
        : "優先看 5Y / 10Y 殖利率、ETF 折溢價與成交量是否同步改善。";
  const riskWarning = isHighYield
    ? "若景氣轉弱、違約率升高或信用利差擴大，價格可能和股票同步下跌。"
    : isLongDuration
      ? "若通膨或長端殖利率重新上行，高久期部位回撤會比短債更大。"
      : isTaiwanListed
        ? "台灣掛牌商品還要留意匯率、交易時差、折溢價與海外債券開盤落差。"
        : "主要風險來自殖利率反向變動、流動性變差與短線量縮。";
  const useCaseText = isGovernment
    ? "適合作為防守、利率觀察與資產配置穩定器。"
    : isHighYield
      ? "適合小比例收益增強，不宜當成低風險債券核心部位。"
      : isTaiwanListed
        ? "適合用台幣帳戶追蹤海外債券，但需搭配匯率與折溢價觀察。"
        : "適合放在核心收益或信用債觀察清單，搭配公債 ETF 比較。";
  const entrySignal = trendTone === "up"
    ? "可觀察回測不破短線均價且成交量維持，代表買盤承接仍在。"
    : "等待價格站回短線區間、日漲跌轉正且量能不萎縮後再提高信心。";
  const failSignal = riskTone === "down"
    ? "若價格續創低、成交量放大且回撤擴大，代表風險尚未釋放完。"
    : "若價格跌破近 20 日區間低點或殖利率重新上行，原本判讀需降級。";
  const strategyLabel = riskTone === "down"
    ? "保守觀察"
    : trendTone === "up" && ratingBand === "投資級"
      ? "分批追蹤"
      : trendTone === "up"
        ? "收益型觀察"
        : "等待確認";
  const strategyText = riskTone === "down"
    ? `目前風險分數 ${Math.round(riskScore)}/100，先等價格止穩或殖利率壓力降溫，再提高部位信心。`
    : trendTone === "up" && ratingBand === "投資級"
      ? `趨勢偏正且信用分層為 ${ratingBand}，可用回測不破短線區間作為分批觀察條件。`
      : trendTone === "up"
        ? `價格動能改善，但信用分層為 ${ratingBand}，適合小比例收益型觀察，不宜視為低風險核心債。`
        : `趨勢與量能尚未同步確認，先把 ${profile.duration.label} 與 ${profile.credit.label} 的風險分開追蹤。`;
  const allocationRole = isShortDuration
    ? "短端防守 / 現金替代"
    : isLongDuration
      ? "久期修復 / 降息交易"
      : isHighYield
        ? "收益衛星 / 信用風險"
        : isGovernment
          ? "核心防守 / 利率觀察"
          : "核心收益 / 分散配置";
  const thesisText = `${item.symbol || "--"} 的研究主軸是「${profile.duration.label} × ${profile.credit.label} × ${etfLens.bucket}」。不要只看配息率，需把殖利率方向、信用補償、ETF 折溢價與流動性一起判斷。`;
  const marketFocus = isLongDuration
    ? "主看 10Y/30Y 殖利率是否轉弱，若長端利率回落才有較完整的價格修復條件。"
    : isShortDuration
      ? "主看 Fed / 短端政策利率與再投資收益，適合等待利率轉折時維持低波動。"
      : isHighYield
        ? "主看信用利差、VIX、失業率與景氣數據，收益補償不足時不宜擴大部位。"
        : "主看 5Y/10Y 殖利率、ETF 廣度與同類標的強弱，確認核心債是否重新吸引資金。";
  const nextStepText = riskTone === "down"
    ? "下一步先確認價格不再破底、回撤收斂且日漲跌轉正，再把它列回可操作清單。"
    : trendTone === "up"
      ? "下一步觀察回測是否守住短線區間；若同類 ETF 廣度同步改善，信心可上調。"
      : "下一步等待量價、殖利率與信用訊號至少兩項轉正，再從觀察轉為分批追蹤。";
  const setupChecks = isLongDuration
    ? ["10Y/30Y 殖利率不再創高或轉下行", "長天期同類 ETF 不再落後短債"]
    : isShortDuration
      ? ["短端政策利率預期穩定", "再投資收益仍高於核心債波動成本"]
      : isHighYield
        ? ["信用利差未擴大", "VIX 與景氣數據未同步惡化"]
        : ["5Y/10Y 殖利率降溫", "核心債 ETF 廣度與同類強弱改善"];
  if (isTaiwanListed) setupChecks.push("折溢價收斂且台幣匯率波動未放大");
  setupChecks.push(trendTone === "up" ? "回測短線區間不破且成交量維持" : "日漲跌轉正且近 20 日動能止跌");
  const setupConditionText = `${setupChecks.join("；")}。${trendTone === "up" ? "目前已有價格動能，重點是確認利率與同類 ETF 是否跟上。" : "目前仍屬觀察，至少需先看到利率/信用與量價兩條線同時改善。"}`;
  const singleBriefRows = [
    ["研究主軸", thesisText],
    ["配置角色", `${allocationRole}；${useCaseText}`],
    ["現在焦點", marketFocus],
    ["下一步", nextStepText],
  ];
  const detailCards = [
    ["配置定位", `${allocationRole}：${positionText} ETF 中心角色為「${etfLens.role}」。`],
    ["觸發條件", setupConditionText],
    ["執行方式", riskTone === "down" ? "先不追價，等待價格止穩與利率壓力降溫；若要觀察，只適合小部位追蹤。" : `${entrySignal} 達成後再用分批方式提高信心。`],
    ["風險界線", `${riskWarning} ${failSignal}`],
  ];
  const etfLensRows = [
    ["ETF 中心用途", etfLens.centerUse],
    ["台灣市場研究", etfLens.taiwanUse],
    ["國際市場研究", etfLens.globalUse],
    ["分類風險", etfLens.keyRisk],
  ];
  const evidenceRows = [
    ["利率與久期", `${profile.duration.note} ${watchText}`],
    ["信用與評等", `${profile.credit.note} ${ratingText}`],
    ["量價與流動性", `收盤 ${formatGlobalValue(close)}，日漲跌 ${formatAssetFinancePct(dayPct)}，近 20 日 ${formatAssetFinancePct(momentum20)}，波動 ${formatAssetFinancePct(volatility)}，回撤 ${formatAssetFinancePct(drawdown)}，成交量 ${formatGlobalVolume(latestVolume)}。`],
  ];
  const commentaryRows = [
    [
      "總結",
      `${item.symbol || "--"} 目前以「${allocationRole}」評估，ETF 中心歸類為「${etfLens.bucket}」。${trendText}`,
    ],
    [
      "成立條件",
      setupConditionText,
    ],
    [
      "風險界線",
      `${riskWarning} ${failSignal}`,
    ],
    [
      "數據狀態",
      `收盤 ${formatGlobalValue(close)}，日漲跌 ${formatAssetFinancePct(dayPct)}，近 20 日 ${formatAssetFinancePct(momentum20)}，成交量 ${formatGlobalVolume(latestVolume)}。`,
    ],
  ];
  return `
    <div class="asset-finance-single-ai asset-finance-bond-single-ai is-${riskTone}" data-asset-finance-single-analysis>
      <div class="asset-finance-single-ai-head">
        <span><small>Bond single AI research</small><b>${escapeHtml(item?.name || item?.symbol || "--")}</b></span>
        <em>${escapeHtml(item?.symbol || "--")} · ${escapeHtml(getAssetHubRegion(item))}</em>
      </div>
      <div class="asset-finance-bond-single-summary is-${riskTone}">
        <span><small>AI 研究結論</small><b>${escapeHtml(strategyLabel)}</b></span>
        <p>${escapeHtml(strategyText)}</p>
      </div>
      <div class="asset-finance-bond-single-brief">
        ${singleBriefRows.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-single-ai-grid">
        <span><small>久期定位</small><b>${escapeHtml(profile.duration.label)}</b><em>${escapeHtml(profile.duration.note)}</em></span>
        <span><small>信用分類</small><b>${escapeHtml(profile.credit.label)}</b><em>${escapeHtml(profile.credit.note)}</em></span>
        <span><small>信用評級</small><b class="${ratingBand === "投資級" ? "up" : "down"}">${escapeHtml(creditGrade)} · ${creditQualityScore}/100</b><em>${escapeHtml(ratingBand)}；模型估算非官方信評</em></span>
        <span><small>趨勢</small><b class="${trendTone}">${formatAssetFinancePct(momentum20)}</b><em>${escapeHtml(trendText)}</em></span>
        <span><small>風險分數</small><b class="${riskTone}">${Math.round(riskScore)}/100</b><em>波動 ${formatAssetFinancePct(volatility)}，回撤 ${formatAssetFinancePct(drawdown)}</em></span>
        <span><small>ETF 中心分類</small><b>${escapeHtml(etfLens.bucket)}</b><em>${escapeHtml(etfLens.role)}</em></span>
      </div>
      <div class="asset-finance-bond-single-etf-lens">
        ${etfLensRows.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-bond-single-subhead">
        <b>策略執行條件</b>
        <small>把定位、觸發、執行與失效界線拆開，避免只用配息率或單日漲跌判斷。</small>
      </div>
      <div class="asset-finance-bond-single-content-grid">
        ${detailCards.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-bond-single-subhead">
        <b>研究證據基準</b>
        <small>利率、信用與量價三條線同時追蹤，作為 AI 評論升降級依據。</small>
      </div>
      <div class="asset-finance-bond-single-evidence">
        ${evidenceRows.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-bond-single-commentary is-${riskTone}">
        <div class="asset-finance-bond-single-commentary-head">
          <span><small>AI research commentary</small><b>AI 研究評論</b></span>
          <em>${escapeHtml(strategyLabel)} · ${escapeHtml(etfLens.bucket)}</em>
        </div>
        <div class="asset-finance-bond-single-commentary-grid">
          ${commentaryRows.map(([label, text]) => `
            <span>
              <b>${escapeHtml(label)}</b>
              <small>${escapeHtml(text)}</small>
            </span>
          `).join("")}
        </div>
      </div>
    </div>
  `;
}

function initAssetFinanceVolumeSelectors(root = document) {
  root.querySelectorAll("[data-asset-finance-volume-card]").forEach((card) => {
    if (card.dataset.assetFinanceVolumeBound === "1") return;
    card.dataset.assetFinanceVolumeBound = "1";
    let items = [];
    try {
      items = JSON.parse(card.dataset.assetFinanceVolumePayload || "[]");
    } catch (error) {
      console.warn("Failed to parse ETF volume payload:", error);
      items = [];
    }
    const itemMap = new Map(items.map((item) => [String(item.symbol || "").toUpperCase(), item]));
    const view = card.querySelector("[data-asset-finance-volume-view]");
    const analysisView = card.querySelector("[data-asset-finance-single-analysis-view]");
    const analysisMode = card.dataset.assetFinanceAnalysisMode || "default";
    const renderAnalysis = analysisMode === "bond" ? renderAssetFinanceBondSingleAnalysis : renderAssetFinanceSingleTrendRiskAnalysis;
    const setActive = (symbol) => {
      const cleanSymbol = String(symbol || "").toUpperCase();
      const item = itemMap.get(cleanSymbol);
      if (!item) return;
      if (view) {
        view.innerHTML = renderAssetFinanceVolumeTrendChart(item, `${item.name || item.symbol} 近 24 日`);
        bindAssetFinanceVolumeCursor(view);
      }
      if (analysisView) analysisView.innerHTML = renderAnalysis(item);
      card.querySelectorAll("[data-asset-finance-volume-row]").forEach((row) => {
        row.classList.toggle("is-active", row.dataset.assetFinanceVolumeRow === cleanSymbol);
      });
      card.querySelectorAll("[data-asset-finance-volume-symbol]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.assetFinanceVolumeSymbol === cleanSymbol);
      });
    };
    card.querySelectorAll("[data-asset-finance-volume-symbol]").forEach((button) => {
      button.addEventListener("click", () => setActive(button.dataset.assetFinanceVolumeSymbol));
    });
    bindAssetFinanceVolumeCursor(card);
  });
}

function bindAssetFinanceVolumeCursor(root = document) {
  root.querySelectorAll(".asset-finance-volume-chart").forEach((chart) => {
    if (chart.dataset.assetFinanceVolumeCursorBound === "1") return;
    chart.dataset.assetFinanceVolumeCursorBound = "1";
    const svg = chart.querySelector("svg");
    const tooltip = chart.querySelector(".asset-finance-volume-tooltip");
    if (!svg || !tooltip) return;
    const xLine = svg.querySelector("[data-asset-finance-volume-crosshair-x]");
    const yLine = svg.querySelector("[data-asset-finance-volume-crosshair-y]");
    const dot = svg.querySelector("[data-asset-finance-volume-crosshair-dot]");
    const hide = () => {
      tooltip.hidden = true;
      xLine?.classList.remove("is-visible");
      yLine?.classList.remove("is-visible");
      dot?.classList.remove("is-visible");
    };
    const show = (event, zone) => {
      const x = Number(zone.dataset.x);
      const y = Number(zone.dataset.y);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return;
      xLine?.setAttribute("x1", x.toFixed(2));
      xLine?.setAttribute("x2", x.toFixed(2));
      yLine?.setAttribute("y1", y.toFixed(2));
      yLine?.setAttribute("y2", y.toFixed(2));
      dot?.setAttribute("cx", x.toFixed(2));
      dot?.setAttribute("cy", y.toFixed(2));
      xLine?.classList.add("is-visible");
      yLine?.classList.add("is-visible");
      dot?.classList.add("is-visible");
      tooltip.innerHTML = `
        <strong>${escapeHtml(zone.dataset.date || "--")}</strong>
        <span><b>收盤</b><em>${escapeHtml(zone.dataset.close || "--")}</em></span>
        <span><b>日漲跌</b><em class="${assetFinancePctTone(parseMarketNumber(zone.dataset.pct))}">${escapeHtml(zone.dataset.pct || "--")}</em></span>
        <span><b>成交量</b><em>${escapeHtml(zone.dataset.volume || "--")}</em></span>
      `;
      tooltip.hidden = false;
      const chartRect = chart.getBoundingClientRect();
      const leftBase = event.clientX - chartRect.left + chart.scrollLeft + 14;
      const topBase = event.clientY - chartRect.top + 12;
      const maxLeft = Math.max(12, chart.scrollLeft + chart.clientWidth - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, chart.clientHeight - tooltip.offsetHeight - 12);
      tooltip.style.left = `${Math.min(Math.max(12, leftBase), maxLeft)}px`;
      tooltip.style.top = `${Math.min(Math.max(12, topBase), maxTop)}px`;
    };
    svg.querySelectorAll(".asset-finance-volume-hover-zone").forEach((zone) => {
      zone.addEventListener("mouseenter", (event) => show(event, zone));
      zone.addEventListener("mousemove", (event) => show(event, zone));
      zone.addEventListener("mouseleave", hide);
    });
    chart.addEventListener("mouseleave", hide);
  });
}

function renderAssetFinanceMetalEtfSyncPanel(model) {
  const taiwanRows = (model.taiwanMetalEtfs || []).filter((item) => item && !item.error);
  const etfRows = (model.metalEtfs || []).filter((item) => item && !item.error);
  const sortedRows = [...etfRows]
    .sort((left, right) => Math.abs(parseMarketNumber(right.pct) || 0) - Math.abs(parseMarketNumber(left.pct) || 0));
  const avgPct = averageAssetFinancePct(sortedRows);
  const best = strongestAssetFinanceItem(sortedRows);
  const weakest = sortedRows
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(left.pct) || 999) - (parseMarketNumber(right.pct) || 999))[0] || null;
  const analysis = buildAssetFinanceMetalsEtfConclusion(sortedRows, { avgPct, best, weakest });
  const onlineRows = Array.isArray(model.metalOnlineRows) ? model.metalOnlineRows : [];
  const onlineCatalogCount = Number(model.metalCatalogCount) || onlineRows.length;
  const displayRows = uniqueAssetHubItemsBySymbol(onlineRows.length ? onlineRows : sortedRows)
    .sort((left, right) => Math.abs(parseMarketNumber(right.pct) || 0) - Math.abs(parseMarketNumber(left.pct) || 0));
  const chartItem = [best, ...displayRows].find((item) => normalizeGlobalOhlcvSeries(item?.series || []).length >= 2) || displayRows[0];
  const shownCount = sortedRows.length;
  const activeSymbol = String(chartItem?.symbol || "").toUpperCase();
  const chartPayload = JSON.stringify(displayRows.map(getAssetFinanceVolumePayloadItem));

  const globalRows = [model.gold, model.silver, model.platinum, model.palladium, ...model.globalMetalEtfs.slice(0, 6)]
    .filter((item) => item && !item.error);
  const taiwanAvg = averageAssetFinancePct(taiwanRows);
  const globalAvg = averageAssetFinancePct(globalRows);
  const bestTaiwan = strongestAssetFinanceItem(taiwanRows);
  const bestGlobal = strongestAssetFinanceItem(globalRows);
  const goldSpread = Number.isFinite(parseMarketNumber(model.taiwanGold?.pct)) && Number.isFinite(parseMarketNumber(model.gold?.pct))
    ? parseMarketNumber(model.taiwanGold.pct) - parseMarketNumber(model.gold.pct)
    : null;
  const stats = [
    renderAssetFinanceSyncStat("台灣貴金屬", formatAssetFinancePct(taiwanAvg), bestTaiwan ? `最強 ${bestTaiwan.symbol} ${bestTaiwan.pct || "--"}` : "等待台灣貴金屬", assetFinancePctTone(taiwanAvg)),
    renderAssetFinanceSyncStat("國際金屬標的", formatAssetFinancePct(globalAvg), bestGlobal ? `最強 ${bestGlobal.symbol} ${bestGlobal.pct || "--"}` : "等待國際金屬標的", assetFinancePctTone(globalAvg)),
    renderAssetFinanceSyncStat("黃金同步差", formatAssetFinancePct(goldSpread), "台灣黃金 - 國際黃金期貨", assetFinancePctTone(goldSpread)),
    renderAssetFinanceSyncStat("金銀比", formatAssetHubRatio(model.goldSilverRatio), model.goldSilverRatio >= 85 ? "黃金相對強勢" : "金銀比中性", model.goldSilverRatio >= 85 ? "down" : "flat"),
  ];
  const syncContext = [
    ["用途", "用台灣黃金、白銀商品對照 COMEX 與國際 ETF，觀察隔日跟漲或補跌。"],
    ["注意", "台幣計價、期貨展期、折溢價與交易時段會造成短線落差。"],
  ];
  return `
    <article class="panel-card asset-finance-etf-card asset-finance-compare-card asset-finance-metal-etf-sync-card" data-asset-finance-volume-card data-asset-finance-volume-payload="${escapeHtml(chartPayload)}">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Metals ETF</p>
          <h4>貴金屬 ETF 與礦業 ETF</h4>
        </div>
        <span>線上 ${displayRows.length} / 目錄 ${onlineCatalogCount} 筆 · ETF/礦業 ${shownCount} 檔</span>
      </div>
      <div class="asset-finance-etf-summary">
        <span><small>平均漲跌</small><b class="${assetFinancePctTone(avgPct)}">${formatAssetFinancePct(avgPct)}</b></span>
        <span><small>相對強勢</small><b>${best ? `${escapeHtml(best.symbol)} ${escapeHtml(best.pct || "--")}` : "--"}</b></span>
        <span><small>相對弱勢</small><b>${weakest ? `${escapeHtml(weakest.symbol)} ${escapeHtml(weakest.pct || "--")}` : "--"}</b></span>
      </div>
      <p class="asset-finance-etf-brief is-${escapeHtml(analysis.tone)}"><b>AI 結論</b><span>${escapeHtml(analysis.text)}</span></p>
      <div class="global-table-wrap asset-finance-table-wrap">
        <table class="global-market-table">
          <thead><tr><th>名稱</th><th>代號</th><th>地區</th><th>交易所 / 來源</th><th>分類</th><th>收盤</th><th>漲跌幅</th><th>開盤</th><th>最高</th><th>最低</th><th>量能欄位</th><th>日期</th></tr></thead>
          <tbody>${renderAssetFinanceSelectableMetalOnlineRows(displayRows, activeSymbol) || '<tr><td colspan="12">貴金屬線上資料同步中。</td></tr>'}</tbody>
        </table>
      </div>
      <div data-asset-finance-volume-view>
        ${renderAssetFinanceVolumeTrendChart(chartItem, chartItem ? `${chartItem.name || chartItem.symbol} 近 24 日` : "ETF 近 24 日")}
      </div>
      <div class="asset-finance-merged-subhead">
        <div>
          <p class="panel-kicker">Metals sync</p>
          <h4>貴金屬：台灣與國際同步比較</h4>
        </div>
        <span>${taiwanRows.length} 檔台灣 / ${globalRows.length} 檔國際</span>
      </div>
      <div class="asset-finance-sync-grid">
        ${stats.join("")}
      </div>
      <div class="asset-finance-sync-context">
        ${syncContext.map(([title, text]) => `<span><b>${escapeHtml(title)}</b><small>${escapeHtml(text)}</small></span>`).join("")}
      </div>
      <div data-asset-finance-single-analysis-view>
        ${renderAssetFinanceSingleTrendRiskAnalysis(chartItem)}
      </div>
    </article>
  `;
}

function buildAssetFinanceBondResearchImport(model) {
  const etfRows = (model.bondEtfs || []).filter((item) => item && !item.error);
  const onlineRows = Array.isArray(model.bondOnlineRows) ? model.bondOnlineRows.filter((item) => item && !item.error) : [];
  const bondRows = getAssetFinanceBondRows(model);
  const taiwanRows = bondRows.filter(isAssetFinanceTaiwanBond);
  const taiwanEtfs = taiwanRows.filter((item) => String(item?.type || "").includes("ETF"));
  const internationalRows = bondRows.filter((item) => !isAssetFinanceTaiwanBond(item));
  const internationalEtfs = internationalRows.filter((item) => String(item?.type || "").includes("ETF"));
  const tenYear = model.yields[2] || {};
  const twoYear = model.yields[0] || {};
  const fiveYear = model.yields[1] || {};
  const thirtyYear = model.yields[3] || {};
  const avgPct = averageAssetFinancePct(etfRows);
  const taiwanAvgPct = averageAssetFinancePct(taiwanEtfs);
  const internationalAvgPct = averageAssetFinancePct(internationalEtfs);
  const best = strongestAssetFinanceItem(etfRows);
  const weakest = etfRows
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(left.pct) || 999) - (parseMarketNumber(right.pct) || 999))[0] || null;
  const taiwanBest = strongestAssetFinanceItem(taiwanEtfs);
  const internationalBest = strongestAssetFinanceItem(internationalEtfs);
  const positiveEtfs = etfRows.filter((item) => parseMarketNumber(item?.pct) > 0).length;
  const negativeEtfs = etfRows.filter((item) => parseMarketNumber(item?.pct) < 0).length;
  const tltPct = parseMarketNumber(model.tlt?.pct);
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const germanyTenYearValue = parseMarketNumber(model.germanyTenYear?.close);
  const japanTenYearValue = parseMarketNumber(model.japanTenYear?.close);
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const twUsSpread = Number.isFinite(taiwanTenYearValue) && Number.isFinite(tenYear.value) ? taiwanTenYearValue - tenYear.value : null;
  const curveTone = Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "down" : "flat";
  const durationTone = tltPct > 0 ? "up" : "flat";
  const creditTone = Number.isFinite(avgPct) && avgPct < -0.35 ? "down" : "flat";
  const curveText = Number.isFinite(model.curveSlope) && model.curveSlope < 0
    ? `10Y-2Y 利差 ${formatAssetHubYield(model.curveSlope)}，曲線仍偏倒掛，長天期債券需用久期分層控管。`
    : `10Y-2Y 利差 ${formatAssetHubYield(model.curveSlope)}，曲線未明顯倒掛，短中長天期可分開比較。`;
  const durationText = tltPct > 0
    ? `TLT ${model.tlt?.pct || "--"}，長天期公債價格有修復跡象，可觀察殖利率是否續降。`
    : `TLT ${model.tlt?.pct || "--"}，長天期久期仍承壓，先看 10Y 殖利率是否轉弱。`;
  const creditText = Number.isFinite(avgPct)
    ? `債券 ETF 平均 ${formatAssetFinancePct(avgPct)}，強勢為 ${best?.symbol || "--"}，弱勢為 ${weakest?.symbol || "--"}。`
    : "債券 ETF 報價尚未完整，信用與久期相對強弱等待線上資料補齊。";
  const breadthText = etfRows.length
    ? `${positiveEtfs} 檔上漲 / ${negativeEtfs} 檔下跌`
    : "ETF 樣本同步中";
  const decisionLabel = Number.isFinite(model.curveSlope) && model.curveSlope < 0 && tltPct <= 0
    ? "防守分層"
    : tltPct > 0 && Number.isFinite(avgPct) && avgPct > 0
      ? "久期修復"
      : Number.isFinite(avgPct) && avgPct < 0
        ? "信用降溫"
        : "雙軸觀察";
  const taiwanResearchText = Number.isFinite(twUsSpread)
    ? `台灣市場：台灣 10Y ${formatAssetHubYield(taiwanTenYearValue)}，相對美國 10Y 利差 ${formatAssetHubYield(twUsSpread)}；本地收益補償偏低，台幣帳戶應把美債久期、美元/台幣與 ETF 折溢價分開控管。`
    : `台灣市場：台灣 10Y ${formatAssetHubYield(taiwanTenYearValue)}，台美利差同步中；先以台灣債券 ETF 廣度 ${formatAssetFinancePct(taiwanAvgPct)} 與海外美債曲線判斷配置節奏。`;
  const globalResearchText = `國際市場：美國 2Y ${formatAssetHubYield(twoYear.value)}、10Y ${formatAssetHubYield(tenYear.value)}，${Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "曲線仍倒掛，短端政策壓力尚未解除" : "曲線偏正斜率，短中長天期可分層比較"}；德國 10Y ${formatAssetHubYield(germanyTenYearValue)}、日本 10Y ${formatAssetHubYield(japanTenYearValue)} 作為非美元核心債利率錨。`;
  const allocationResearchText = Number.isFinite(avgPct)
    ? `配置判讀：整體債券 ETF 平均 ${formatAssetFinancePct(avgPct)}，強勢 ${best?.symbol || "--"}、弱勢 ${weakest?.symbol || "--"}；若強勢集中在台灣掛牌美債 ETF 而全球債偏弱，先以美債久期主線為主，不急著擴到全球信用曝險。`
    : "配置判讀：ETF 樣本尚未完整，先以主權利率、美元與 VIX 判斷債券風險溫度。";
  const riskResearchText = `${durationText} ${creditText}`;
  return {
    avgPct,
    best,
    weakest,
    decisionLabel,
    heroTitle: `${decisionLabel}：台灣收益補償 × 國際久期`,
    conclusion: `AI 結論：目前債券研究主軸為「${decisionLabel}」。導入內容聚焦台灣債券市場與國際債券市場：台灣看本地利率、台幣帳戶 ETF、折溢價與匯率；國際看美債曲線、歐日主權利率、美元流動性與信用利差。${curveText} ${durationText}`,
    summaryPoints: [
      `AI 研究主軸：${decisionLabel}。本區不做泛用資料摘要，改以「台灣市場收益補償」與「國際市場久期/信用」兩條線交叉判讀。`,
      taiwanResearchText,
      globalResearchText,
      allocationResearchText,
      riskResearchText,
    ],
    radar: [
      ["10Y 殖利率", formatAssetHubYield(tenYear.value), tenYear.date || "U.S. Treasury", assetHubTone(tenYear.item)],
      ["10Y-2Y 利差", formatAssetHubYield(model.curveSlope), Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "曲線倒掛" : "正利差 / 未明顯倒掛", curveTone],
      ["久期代表", model.tlt?.pct || "--", `TLT 收盤 ${formatGlobalValue(model.tlt?.close)}`, durationTone],
      ["ETF 廣度", breadthText, `平均 ${formatAssetFinancePct(avgPct)}`, assetFinancePctTone(avgPct)],
    ],
    marketAnalysis: [
      {
        title: "台灣債券市場研究",
        tag: "Taiwan bond market",
        aiTheme: "台灣利率、台幣 ETF、折溢價與匯率風險",
        tone: assetFinancePctTone(taiwanAvgPct),
        thesis: "台灣債券市場的分析重點不是單看殖利率，而是把本地利率、台幣匯率、海外債券曝險與 ETF 折溢價放在同一張表裡。",
        metrics: [
          ["台灣 10Y", formatAssetHubYield(taiwanTenYearValue), model.taiwanTenYear?.date || "OTC / Trading Economics", assetHubTone(model.taiwanTenYear)],
          ["台美 10Y 利差", formatAssetHubYield(twUsSpread), "台灣 10Y - 美國 10Y", "flat"],
          ["台灣 ETF 廣度", formatAssetFinancePct(taiwanAvgPct), taiwanBest ? `較強 ${taiwanBest.symbol} ${taiwanBest.pct || "--"}` : "等待 ETF 同步", assetFinancePctTone(taiwanAvgPct)],
        ],
        points: [
          "本地政府公債、公司債、金融債與 Formosa Bond 用來判斷台幣資金利率結構；台灣掛牌美債 ETF 則反映海外久期與匯率。",
          "若台美利差維持大幅負值，台灣投資人買美債 ETF 的主要風險會落在美元/台幣、折溢價與長天期久期波動。",
          "台灣債券 ETF 需拆開看 20 年美債、7-10 年美債、投資級債與金融債，不能只用配息率排序。",
        ],
        action: "AI 研判：台灣債券配置應先確認台幣匯率與折溢價，再用美債 2Y/10Y 曲線決定短、中、長天期 ETF 權重。",
      },
      {
        title: "國際債券市場研究",
        tag: "Global bond market",
        aiTheme: "美債曲線、歐日主權利率、美元與信用利差",
        tone: assetFinancePctTone(internationalAvgPct),
        thesis: "國際債券市場以美債曲線為核心，再用歐洲、日本、新興市場與美元流動性判斷分散配置是否成立。",
        metrics: [
          ["美債 10Y-2Y", formatAssetHubYield(model.curveSlope), model.curveSlope < 0 ? "曲線倒掛" : "曲線正常化", curveTone],
          ["德日 10Y", `${formatAssetHubYield(germanyTenYearValue)} / ${formatAssetHubYield(japanTenYearValue)}`, "德國 / 日本主權利率", "flat"],
          ["國際 ETF 廣度", formatAssetFinancePct(internationalAvgPct), internationalBest ? `較強 ${internationalBest.symbol} ${internationalBest.pct || "--"}` : "等待 ETF 同步", assetFinancePctTone(internationalAvgPct)],
        ],
        points: [
          `美債短端 ${formatAssetHubYield(twoYear.value)} 仍代表政策利率壓力，10Y ${formatAssetHubYield(tenYear.value)} 代表全球折現率核心，兩者決定久期配置節奏。`,
          "歐洲與日本主權利率反映 ECB / BOJ 政策分化，若美元偏強，非美債與新興市場美元債需提高匯率與信用風險權重。",
          "國際債券要分層看公債、投資級債、高收益債、新興市場債與抗通膨債，避免把利率下行行情誤讀成信用風險改善。",
        ],
        action: Number.isFinite(dxyPct) && dxyPct > 0
          ? "AI 研判：美元偏強時先保守看非美債，等 BNDX/IAGG 止穩與 EMB 相對強弱改善後，再提高國際債配置。"
          : "AI 研判：美元壓力不高時，可用國際投資級債作分散來源；若 EMB 轉強，再評估新興市場債風險預算。",
      },
    ],
    playbook: [
      {
        title: "短端防守",
        tag: "SHY / VGSH / BIL",
        tone: Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "up" : "flat",
        taiwan: `台灣 10Y ${formatAssetHubYield(taiwanTenYearValue)}、台美利差 ${formatAssetHubYield(twUsSpread)}，本地收益補償偏低時，台灣帳戶先保留短天期與現金替代部位。`,
        global: `美國 2Y ${formatAssetHubYield(twoYear.value)} 仍是政策利率壓力核心；曲線倒掛時，短債比追長債更能控制波動。`,
        action: "操作：維持短天期與流動性，等 2Y 下行或 5Y/10Y 同步轉弱，再把久期往中段延伸。",
      },
      {
        title: "中天期核心債",
        tag: "IEF / VGIT / BND / AGG",
        tone: "flat",
        taiwan: "台灣掛牌 7-10 年美債與投資級債 ETF 可作核心層，但要先確認折溢價與美元/台幣方向沒有同時不利。",
        global: `5Y ${formatAssetHubYield(fiveYear.value)}、10Y ${formatAssetHubYield(tenYear.value)} 若同步回落，代表政策壓力開始傳導到核心折現率。`,
        action: "操作：短債之外逐步增加 IEF/VGIT/BND/AGG 類核心債，台灣 ETF 用分批方式降低匯率與時差風險。",
      },
      {
        title: "長天期美債",
        tag: "TLT / VGLT / 台灣美債 ETF",
        tone: durationTone,
        taiwan: "台灣 20 年美債 ETF 價格彈性大，但報酬會同時受海外久期、美元/台幣與折溢價影響，不能只看配息率。",
        global: `TLT ${model.tlt?.pct || "--"} 是長久期修復溫度計；10Y ${formatAssetHubYield(tenYear.value)} 若未轉弱，長債仍可能反覆震盪。`,
        action: "操作：只有在 10Y 回落、通膨/就業支持降息且 TLT 轉強時，才提高長天期權重；否則維持小比例分批。",
      },
      {
        title: "信用與新興市場",
        tag: "LQD / HYG",
        tone: creditTone,
        taiwan: "台灣投資人若透過海外債 ETF 追收益，需把信用利差、匯率與流動性折價一起看，避免只追高配息。",
        global: `信用債需等 HYG/LQD 或 Baa-Aaa 改善再加碼；美元偏強時，EMB 與非美債的匯率與信用風險會一起放大。`,
        action: "操作：投資級債優先於高收益債；HYG/LQD 轉強、美元降溫後，再評估高收益與新興市場債。",
      },
    ],
    checks: [
      ["利率主軸", curveText],
      ["久期觀察", durationText],
      ["信用風險", creditText],
      ["30Y 參考", `30Y ${formatAssetHubYield(thirtyYear.value)}，用來判斷長端通膨與期限溢酬。`],
      ["資料廣度", `線上債券資料 ${onlineRows.length || etfRows.length} 筆，ETF 樣本 ${etfRows.length} 檔。`],
      ["保留邏輯", "已移除靜態商品地圖與評等教材；保留可轉成配置動作的久期與信用策略矩陣。"],
    ],
  };
}

function renderAssetFinanceBondResearchHero(research, tone) {
  const summaryPoints = Array.isArray(research.summaryPoints) ? research.summaryPoints : [research.conclusion];
  const bestLabel = research.best ? `${research.best.symbol} ${research.best.pct || "--"}` : "--";
  const weakestLabel = research.weakest ? `${research.weakest.symbol} ${research.weakest.pct || "--"}` : "--";
  return `
    <div class="asset-finance-bond-research-hero is-${escapeHtml(tone)}">
      <section>
        <small>AI research import · Taiwan / global bond market</small>
        <h5>${escapeHtml(research.heroTitle || research.decisionLabel)}</h5>
        <ul>
          ${summaryPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
        </ul>
      </section>
      <aside>
        <span>
          <small>整體 ETF 廣度</small>
          <b>${escapeHtml(formatAssetFinancePct(research.avgPct))}</b>
        </span>
        <span>
          <small>主線標的</small>
          <b>${escapeHtml(bestLabel)}</b>
        </span>
        <span>
          <small>落後觀察</small>
          <b>${escapeHtml(weakestLabel)}</b>
        </span>
      </aside>
    </div>
  `;
}

function renderAssetFinanceBondResearchMarketAnalysis(research) {
  const items = Array.isArray(research.marketAnalysis) ? research.marketAnalysis : [];
  if (!items.length) return "";
  return `
    <div class="asset-finance-bond-market-analysis-grid">
      ${items.map((item) => `
        <section class="is-${escapeHtml(item.tone || "flat")}">
          <div class="asset-finance-bond-market-analysis-head">
            <span>
              <small>${escapeHtml(item.tag || "Bond market")}</small>
              <h5>${escapeHtml(item.title)}</h5>
            </span>
            <em>${escapeHtml(item.aiTheme ? `AI 主題：${item.aiTheme}` : "AI 主題同步中")}</em>
          </div>
          <p>${escapeHtml(item.thesis || "")}</p>
          <div class="asset-finance-bond-region-metrics">
            ${(item.metrics || []).map(([label, value, detail, tone]) => `
              <span>
                <small>${escapeHtml(label)}</small>
                <b class="${escapeHtml(tone || "flat")}">${escapeHtml(value)}</b>
                <em>${escapeHtml(detail)}</em>
              </span>
            `).join("")}
          </div>
          <ul>
            ${(item.points || []).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
          </ul>
          <p class="asset-finance-bond-region-ai">${escapeHtml(item.action || "")}</p>
        </section>
      `).join("")}
    </div>
  `;
}

function renderAssetFinanceBondResearchPanel(model) {
  const research = buildAssetFinanceBondResearchImport(model);
  const tone = Number.isFinite(research.avgPct) && research.avgPct > 0 ? "up" : Number.isFinite(research.avgPct) && research.avgPct < 0 ? "down" : "flat";
  return `
    <article class="panel-card asset-finance-module-card asset-finance-bond-research-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Imported bond research</p>
          <h4>AI 台灣與國際債券研究分析</h4>
        </div>
        <span>台灣市場 / 國際市場研究分析</span>
      </div>
      ${renderAssetFinanceBondResearchHero(research, tone)}
      <div class="asset-finance-bond-radar-grid">
        ${research.radar.map(([label, value, detail, itemTone]) => renderAssetFinanceSyncStat(label, value, detail, itemTone)).join("")}
      </div>
      <div class="asset-finance-bond-section-head">
        <span><small>Market research analysis</small><b>台灣債券市場與國際債券市場</b></span>
        <em>研究導入主內容</em>
      </div>
      ${renderAssetFinanceBondResearchMarketAnalysis(research)}
      <div class="asset-finance-bond-section-head">
        <span><small>Duration / credit playbook</small><b>久期與信用配置矩陣</b></span>
        <em>導入台灣市場與國際市場研究</em>
      </div>
      <div class="asset-finance-bond-playbook-grid">
        ${research.playbook.map((item) => `
          <section class="is-${escapeHtml(item.tone)}">
            <small>${escapeHtml(item.tag)}</small>
            <b>${escapeHtml(item.title)}</b>
            <div class="asset-finance-bond-playbook-lenses">
              <span>
                <strong>台灣研究</strong>
                <em>${escapeHtml(item.taiwan || "")}</em>
              </span>
              <span>
                <strong>國際研究</strong>
                <em>${escapeHtml(item.global || "")}</em>
              </span>
            </div>
            <p>${escapeHtml(item.action || item.text || "")}</p>
          </section>
        `).join("")}
      </div>
      <div class="asset-finance-bond-check-grid">
        ${research.checks.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
    </article>
  `;
}

function renderAssetFinanceScenarioPanel(model) {
  return `
    <article class="panel-card asset-finance-module-card asset-finance-scenario-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI scenario simulation</p>
          <h4>AI 價格 / 殖利率情境模擬</h4>
        </div>
        <span>信心 ${model.confidence}</span>
      </div>
      <div class="asset-finance-scenario-grid">
        ${model.scenarios.map((item) => `
          <section class="is-${item.tone}">
            <b>${escapeHtml(item.name)}</b>
            <small>${escapeHtml(item.condition)}</small>
            <p>${escapeHtml(item.view)}</p>
          </section>
        `).join("")}
      </div>
    </article>
  `;
}

function averageAssetFinancePct(items = []) {
  const values = items.map((item) => parseMarketNumber(item?.pct)).filter(Number.isFinite);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function strongestAssetFinanceItem(items = []) {
  return items
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(right.pct) || -999) - (parseMarketNumber(left.pct) || -999))[0] || null;
}

function formatAssetFinancePct(value) {
  if (!Number.isFinite(value)) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function assetFinancePctTone(value) {
  if (!Number.isFinite(value)) return "flat";
  return value >= 0 ? "up" : "down";
}

function renderAssetFinanceSyncStat(label, value, detail, tone = "flat", options = {}) {
  const isButton = Boolean(options.focusKey || options.button);
  const className = [
    "asset-finance-sync-stat",
    `is-${tone}`,
    isButton ? "is-clickable" : "",
    options.active ? "is-active" : "",
  ].filter(Boolean).join(" ");
  const attrs = isButton
    ? ` type="button"${options.focusKey ? ` data-bond-yield-focus="${escapeHtml(options.focusKey)}"` : ""} aria-pressed="${options.active ? "true" : "false"}"${options.ariaLabel ? ` aria-label="${escapeHtml(options.ariaLabel)}"` : ""}`
    : "";
  const tag = isButton ? "button" : "span";
  return `
    <${tag} class="${escapeHtml(className)}"${attrs}>
      <small>${escapeHtml(label)}</small>
      <strong>${escapeHtml(value)}</strong>
      <em>${escapeHtml(detail || "")}</em>
    </${tag}>
  `;
}

function renderAssetFinanceCompareRow(item) {
  if (!item) return "";
  const metric = getAssetHubMetric(item);
  return `
    <a class="asset-finance-compare-row" href="${safeUrl(getAssetHubItemUrl(item))}" target="_blank" rel="noopener noreferrer">
      <span>
        <b>${escapeHtml(item.name || "--")}</b>
        <small>${escapeHtml(item.symbol || "--")} · ${escapeHtml(item.type || item.group || "--")} · ${escapeHtml(item.date || "--")}</small>
      </span>
      <span>
        <strong>${formatGlobalValue(item.close)}</strong>
        <em class="${assetHubTone(item)}">${escapeHtml(item.pct || "--")}</em>
        <small>${escapeHtml(metric.label)} ${formatGlobalVolume(metric.value)}</small>
      </span>
    </a>
  `;
}

function describeAssetFinanceTaiwanSync(model, taiwanRows, globalRows) {
  const taiwanAvg = averageAssetFinancePct(taiwanRows);
  const globalAvg = averageAssetFinancePct(globalRows);
  const goldPct = parseMarketNumber(model.gold?.pct);
  const taiwanGoldPct = parseMarketNumber(model.taiwanGold?.pct);
  const notes = [];
  if (Number.isFinite(taiwanAvg) && Number.isFinite(globalAvg)) {
    const spread = taiwanAvg - globalAvg;
    notes.push(spread >= 0
      ? `台灣避險 ETF 平均漲跌 ${formatAssetFinancePct(taiwanAvg)}，相對國際樣本高 ${Math.abs(spread).toFixed(2)} 個百分點，台幣計價標的短線跟漲力道較強。`
      : `台灣避險 ETF 平均漲跌 ${formatAssetFinancePct(taiwanAvg)}，相對國際樣本低 ${Math.abs(spread).toFixed(2)} 個百分點，可能受匯率、折溢價或交易時段落差影響。`);
  }
  if (Number.isFinite(goldPct) && Number.isFinite(taiwanGoldPct)) {
    const goldSpread = taiwanGoldPct - goldPct;
    notes.push(goldSpread >= 0
      ? `台灣黃金日漲跌 ${formatAssetFinancePct(taiwanGoldPct)}，高於國際黃金期貨 ${Math.abs(goldSpread).toFixed(2)} 個百分點，需觀察隔日是否回補時差。`
      : `台灣黃金日漲跌 ${formatAssetFinancePct(taiwanGoldPct)}，低於國際黃金期貨 ${Math.abs(goldSpread).toFixed(2)} 個百分點，可能反映交易時段與匯率差。`);
  }
  if (Number.isFinite(model.curveSlope)) {
    notes.push(`美債 10Y-2Y 利差 ${formatAssetHubYield(model.curveSlope)}；${model.curveSlope < 0 ? "曲線倒掛時台灣長天期美債 ETF 對利率變動更敏感。" : "正利差環境下可同步比較短、中、長天期債券 ETF 的輪動。"}`);
  }
  return notes;
}

function renderAssetFinanceTaiwanPanel(model, mode = "metals") {
  const isBonds = mode === "bonds";
  const taiwanRows = (isBonds ? model.taiwanBondEtfs : model.taiwanMetalEtfs).filter((item) => item && !item.error);
  const globalRows = (isBonds
    ? [model.tlt, ...model.globalBondEtfs.slice(0, 10)]
    : [model.gold, model.silver, model.platinum, model.palladium, ...model.globalMetalEtfs.slice(0, 6)]
  ).filter((item) => item && !item.error);
  const taiwanAvg = averageAssetFinancePct(taiwanRows);
  const globalAvg = averageAssetFinancePct(globalRows);
  const bestTaiwan = strongestAssetFinanceItem(taiwanRows);
  const bestGlobal = strongestAssetFinanceItem(globalRows);
  const goldSpread = Number.isFinite(parseMarketNumber(model.taiwanGold?.pct)) && Number.isFinite(parseMarketNumber(model.gold?.pct))
    ? parseMarketNumber(model.taiwanGold.pct) - parseMarketNumber(model.gold.pct)
    : null;
  const stats = isBonds
    ? [
      renderAssetFinanceSyncStat("台灣債券 ETF", formatAssetFinancePct(taiwanAvg), bestTaiwan ? `最強 ${bestTaiwan.symbol} ${bestTaiwan.pct || "--"}` : "等待台灣債券 ETF", assetFinancePctTone(taiwanAvg)),
      renderAssetFinanceSyncStat("國際債券 ETF", formatAssetFinancePct(globalAvg), bestGlobal ? `最強 ${bestGlobal.symbol} ${bestGlobal.pct || "--"}` : "等待國際債券標的", assetFinancePctTone(globalAvg)),
      renderAssetFinanceSyncStat("長天期公債 ETF", model.tlt?.pct || "--", `TLT 收盤 ${formatGlobalValue(model.tlt?.close)}`, assetHubTone(model.tlt)),
      renderAssetFinanceSyncStat("殖利率曲線", formatAssetHubYield(model.curveSlope), model.curveSlope < 0 ? "10Y-2Y 倒掛" : "10Y-2Y 正利差", model.curveSlope < 0 ? "down" : "up"),
    ]
    : [
      renderAssetFinanceSyncStat("台灣貴金屬", formatAssetFinancePct(taiwanAvg), bestTaiwan ? `最強 ${bestTaiwan.symbol} ${bestTaiwan.pct || "--"}` : "等待台灣貴金屬", assetFinancePctTone(taiwanAvg)),
      renderAssetFinanceSyncStat("國際金屬標的", formatAssetFinancePct(globalAvg), bestGlobal ? `最強 ${bestGlobal.symbol} ${bestGlobal.pct || "--"}` : "等待國際金屬標的", assetFinancePctTone(globalAvg)),
      renderAssetFinanceSyncStat("黃金同步差", formatAssetFinancePct(goldSpread), "台灣黃金 - 國際黃金期貨", assetFinancePctTone(goldSpread)),
      renderAssetFinanceSyncStat("金銀比", formatAssetHubRatio(model.goldSilverRatio), model.goldSilverRatio >= 85 ? "黃金相對強勢" : "金銀比中性", model.goldSilverRatio >= 85 ? "down" : "flat"),
    ];
  const notes = isBonds
    ? [
      Number.isFinite(taiwanAvg) && Number.isFinite(globalAvg)
        ? `台灣債券 ETF 平均漲跌 ${formatAssetFinancePct(taiwanAvg)}，國際債券樣本 ${formatAssetFinancePct(globalAvg)}，兩者差異可用來觀察交易時段與匯率影響。`
        : "等待台灣與國際債券 ETF 完成同步後產生相對強弱判讀。",
      Number.isFinite(model.curveSlope)
        ? `美債 10Y-2Y 利差 ${formatAssetHubYield(model.curveSlope)}；${model.curveSlope < 0 ? "倒掛時長天期債券對利率預期更敏感，需分開看久期風險。" : "正利差時可分層比較短、中、長天期 ETF 輪動。"}`
        : "殖利率曲線同步中，債券久期判讀暫以 ETF 行情為主。",
    ]
    : [
      Number.isFinite(taiwanAvg) && Number.isFinite(globalAvg)
        ? `台灣貴金屬平均漲跌 ${formatAssetFinancePct(taiwanAvg)}，國際金屬樣本 ${formatAssetFinancePct(globalAvg)}，差異多半來自匯率、折溢價與交易時段。`
        : "等待台灣與國際金屬標的完成同步後產生相對強弱判讀。",
      Number.isFinite(goldSpread)
        ? `台灣黃金與國際黃金期貨同步差 ${formatAssetFinancePct(goldSpread)}，隔日開盤需留意是否回補海外盤時差。`
        : "台灣黃金或國際黃金期貨尚在同步中，黃金同步差暫不判讀。",
    ];
  const syncContext = isBonds
    ? [
      ["用途", "用台灣 ETF 對照國際債券 ETF，判斷匯率與交易時段落差。"],
      ["注意", "長天期債券 ETF 對殖利率變動更敏感，需與曲線利差一起看。"],
    ]
    : [
      ["用途", "用台灣黃金、白銀商品對照 COMEX 與國際 ETF，觀察隔日跟漲或補跌。"],
      ["注意", "台幣計價、期貨展期、折溢價與交易時段會造成短線落差。"],
    ];
  return `
    <article class="panel-card asset-finance-etf-card asset-finance-compare-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">${isBonds ? "Bond sync" : "Metals sync"}</p>
          <h4>${isBonds ? "債券：台灣與國際同步比較" : "貴金屬：台灣與國際同步比較"}</h4>
        </div>
        <span>${taiwanRows.length} 檔台灣 / ${globalRows.length} 檔國際</span>
      </div>
      <div class="asset-finance-sync-grid">
        ${stats.join("")}
      </div>
      <div class="asset-finance-sync-context">
        ${syncContext.map(([title, text]) => `<span><b>${escapeHtml(title)}</b><small>${escapeHtml(text)}</small></span>`).join("")}
      </div>
      <div class="asset-finance-compare-grid">
        <section>
          <h5>${isBonds ? "台灣債券 ETF" : "台灣貴金屬"}</h5>
          ${taiwanRows.map(renderAssetFinanceCompareRow).join("") || `<p class="stock-detail-empty">${isBonds ? "台灣債券 ETF 線上資料同步中。" : "台灣貴金屬線上資料同步中。"}</p>`}
        </section>
        <section>
          <h5>${isBonds ? "國際債券參考" : "國際貴金屬參考"}</h5>
          ${globalRows.slice(0, 12).map(renderAssetFinanceCompareRow).join("") || `<p class="stock-detail-empty">${isBonds ? "國際債券 ETF 線上資料同步中。" : "國際貴金屬標的線上資料同步中。"}</p>`}
        </section>
      </div>
      <div class="asset-finance-sync-notes">
        ${notes.map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
      </div>
    </article>
  `;
}

function renderAssetFinanceMetalsResearchSection(model) {
  return `
    <div class="asset-finance-zone-section is-metals" id="asset-finance-metals-dashboard">
      <div class="asset-finance-zone-heading">
        <div>
          <p class="panel-kicker">Precious metals research</p>
          <h3>貴金屬研究區</h3>
        </div>
        <p>集中查看黃金、白銀、鉑鈀、國際貴金屬 ETF 與台灣貴金屬同步狀態。</p>
      </div>
      <div class="asset-finance-zone-layout" id="asset-finance-compare">
        ${renderAssetFinanceMetalProfilesPanel(model)}
        ${renderAssetFinanceMetalsPanel(model)}
        ${renderAssetFinanceMetalDriversPanel(model)}
        ${renderAssetFinanceDecisionCenterPanel(model)}
        ${renderAssetFinanceMetalEtfSyncPanel(model)}
      </div>
    </div>
  `;
}

function getAssetFinanceBondRows(model) {
  return uniqueAssetHubItemsBySymbol(
    (Array.isArray(model?.bondOnlineRows) && model.bondOnlineRows.length ? model.bondOnlineRows : model?.bondEtfs || [])
      .filter((item) => item && !item.error)
  );
}

function isAssetFinanceTaiwanBond(item) {
  const text = `${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.region || ""} ${item?.market || ""}`;
  return /\.TW|\.TWO/i.test(String(item?.symbol || "")) || /台灣|TPEx|TPEX|臺灣/.test(text);
}

function filterAssetFinanceBondRows(rows, pattern) {
  return rows.filter((item) => pattern.test(`${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.region || ""} ${item?.market || ""} ${item?.exchange || ""}`));
}

function getAssetFinanceBondFocusKey(scope, label) {
  const slug = String(label || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `bond-${scope}-${slug || "yield"}`;
}

function getAssetFinanceRateMoveTone(item) {
  const move = parseMarketNumber(item?.pct ?? item?.change);
  if (Number.isFinite(move) && move > 0.01) return "down";
  if (Number.isFinite(move) && move < -0.01) return "up";
  return assetHubTone(item);
}

function getAssetFinanceBondFocusKind(focus) {
  const key = String(focus?.key || "");
  const maturity = String(focus?.maturity || focus?.shortLabel || "");
  if (/taiwan/i.test(key)) return "taiwan";
  if (/germany/i.test(key)) return "germany";
  if (/japan/i.test(key)) return "japan";
  if (/2/.test(maturity)) return "short";
  if (/5/.test(maturity)) return "belly";
  if (/30/.test(maturity)) return "long";
  return "core";
}

function buildAssetFinanceBondFocusEtfPulse(model, focus) {
  const kind = getAssetFinanceBondFocusKind(focus);
  const symbolsByKind = {
    short: ["SHY", "VGSH", "BIL", "SGOV", "USFR", "TFLO"],
    belly: ["IEF", "VGIT", "BND", "AGG"],
    core: ["IEF", "BND", "AGG", "TLT"],
    long: ["TLT", "VGLT", "EDV", "GOVZ"],
    taiwan: ["00679B.TWO", "00687B.TWO", "00696B.TWO", "00697B.TWO", "00795B.TWO", "00857B.TWO", "00931B.TWO"],
    germany: ["BNDX", "IAGG", "EMB"],
    japan: ["BNDX", "IAGG", "EMB"],
  };
  const labelsByKind = {
    short: "短天期 ETF",
    belly: "中天期 ETF",
    core: "核心債 ETF",
    long: "長天期 ETF",
    taiwan: "台灣美債 ETF",
    germany: "國際債 ETF",
    japan: "國際債 ETF",
  };
  const payload = { items: getAssetFinanceBondRows(model) };
  const rows = getAssetHubUsableBySymbols(payload, symbolsByKind[kind] || symbolsByKind.core);
  const avg = averageAssetFinancePct(rows);
  const best = strongestAssetFinanceItem(rows);
  return [
    labelsByKind[kind] || "焦點 ETF",
    formatAssetFinancePct(avg),
    best ? `代表 ${best.symbol} ${best.pct || "--"}` : "等待焦點 ETF 同步",
    assetFinancePctTone(avg),
  ];
}

function buildAssetFinanceBondFocusMetricSet(model, context = {}, focus) {
  const kind = getAssetFinanceBondFocusKind(focus);
  const twoYear = model.yields?.[0]?.value;
  const fiveYear = model.yields?.[1]?.value;
  const tenYear = model.yields?.[2]?.value;
  const thirtyYear = model.yields?.[3]?.value;
  const focusValue = focus?.value;
  const fedRate = parseMarketNumber(model.fedFunds?.close);
  const ecbRate = parseMarketNumber(model.ecbDepositRate?.close);
  const bojRate = parseMarketNumber(model.bojCallRate?.close);
  const taiwanTenYear = parseMarketNumber(model.taiwanTenYear?.close);
  const germanyTenYear = parseMarketNumber(model.germanyTenYear?.close);
  const japanTenYear = parseMarketNumber(model.japanTenYear?.close);
  const twUsSpread = context.twUsSpread;
  const creditSpread = context.creditSpread;
  const aaaValue = context.aaaValue;
  const baaValue = context.baaValue;
  const creditRiskPulse = context.creditRiskPulse;
  const creditHot = Number.isFinite(creditSpread) && creditSpread > 1;
  const curveMetricByKind = {
    short: ["2Y-Fed 壓力", formatAssetHubYield(Number.isFinite(focusValue) && Number.isFinite(fedRate) ? focusValue - fedRate : null), "短端高於政策利率時，短債與現金替代優先", "down"],
    belly: ["5Y-2Y 轉折", formatAssetHubYield(Number.isFinite(fiveYear) && Number.isFinite(twoYear) ? fiveYear - twoYear : null), "中段若先回落，代表降息與景氣放緩預期升溫", Number.isFinite(fiveYear) && Number.isFinite(twoYear) && fiveYear < twoYear ? "up" : "flat"],
    core: ["10Y-2Y 曲線", formatAssetHubYield(model.curveSlope), model.curveSlope < 0 ? "倒掛仍偏防守" : "正斜率可分層配置", model.curveSlope < 0 ? "down" : "up"],
    long: ["30Y-10Y 長端", formatAssetHubYield(Number.isFinite(thirtyYear) && Number.isFinite(tenYear) ? thirtyYear - tenYear : null), "長端期限溢酬決定 TLT/EDV 波動", Number.isFinite(thirtyYear) && Number.isFinite(tenYear) && thirtyYear > tenYear ? "down" : "flat"],
    taiwan: ["台美 10Y 利差", formatAssetHubYield(twUsSpread), "台灣掛牌美債 ETF 需同步看匯率與折溢價", "flat"],
    germany: ["德美 10Y 利差", formatAssetHubYield(Number.isFinite(germanyTenYear) && Number.isFinite(tenYear) ? germanyTenYear - tenYear : null), "歐元區利率錨影響國際核心債分散配置", "flat"],
    japan: ["日美 10Y 利差", formatAssetHubYield(Number.isFinite(japanTenYear) && Number.isFinite(tenYear) ? japanTenYear - tenYear : null), "日本利率正常化會牽動全球長端利率", "flat"],
  };
  const sovereignMetricByKind = {
    short: ["政策利率錨", `Fed ${formatAssetHubYield(fedRate)} / ECB ${formatAssetHubYield(ecbRate)}`, "短端焦點先看央行路徑", (Number.isFinite(fedRate) && fedRate >= 3.5) || (Number.isFinite(ecbRate) && ecbRate >= 2) ? "down" : "flat"],
    belly: ["景氣折現錨", formatAssetHubYield(fiveYear), "5Y 對降息節奏與景氣轉折最敏感", "flat"],
    core: ["全球折現錨", formatAssetHubYield(tenYear), "10Y 是核心債與投資級債的估值中心", Number.isFinite(tenYear) && tenYear >= 4.2 ? "down" : "flat"],
    long: ["期限溢酬錨", formatAssetHubYield(thirtyYear), "30Y 上行時不宜把久期一次拉滿", Number.isFinite(thirtyYear) && thirtyYear >= 4.8 ? "down" : "flat"],
    taiwan: ["本地利率錨", formatAssetHubYield(taiwanTenYear), `台美利差 ${formatAssetHubYield(twUsSpread)}`, assetHubTone(model.taiwanTenYear)],
    germany: ["歐元利率錨", formatAssetHubYield(germanyTenYear), `ECB ${formatAssetHubYield(ecbRate)}，觀察歐債與美元互動`, assetHubTone(model.germanyTenYear)],
    japan: ["日本政策錨", formatAssetHubYield(japanTenYear), `BOJ 代理 ${formatAssetHubYield(bojRate)}，觀察資金回流`, assetHubTone(model.japanTenYear)],
  };
  const ratingDetailByKind = {
    short: "短端焦點下，信用下沉的必要性較低",
    belly: "中天期焦點需用 Aaa/Baa 驗證信用補償",
    core: "核心債配置以評等利差判斷信用溫度",
    long: "長久期不宜再疊加過多信用 beta",
    taiwan: "台灣 ETF 需拆開看海外信用與台幣匯率",
    germany: "非美債配置需比較歐元信用補償",
    japan: "日本利率上行時，低評等與長久期都要降槓桿",
  };
  const riskMetricByKind = {
    short: ["短端信用溫度", formatAssetFinancePct(creditRiskPulse), "HYG-LQD；短端收益足夠時不急著信用下沉", assetFinancePctTone(creditRiskPulse)],
    belly: ["中段信用補償", formatAssetHubYield(creditSpread), "Baa-Aaa；5Y 轉折要等信用同步", creditHot ? "down" : "flat"],
    core: ["核心信用補償", formatAssetHubYield(creditSpread), "Baa-Aaa；核心債配置的信用門檻", creditHot ? "down" : "flat"],
    long: ["長端信用疊加", `${formatAssetHubYield(creditSpread)} / TLT ${model.tlt?.pct || "--"}`, "長久期加信用 beta 時需提高門檻", creditHot || parseMarketNumber(model.tlt?.pct) < 0 ? "down" : "flat"],
    taiwan: ["台灣 ETF 風險補償", formatAssetHubYield(twUsSpread), "台美利差代表匯率與海外久期補償", "flat"],
    germany: ["歐債相對補償", formatAssetHubYield(Number.isFinite(germanyTenYear) && Number.isFinite(tenYear) ? germanyTenYear - tenYear : null), "德美 10Y 利差衡量非美核心債吸引力", "flat"],
    japan: ["日債相對補償", formatAssetHubYield(Number.isFinite(japanTenYear) && Number.isFinite(tenYear) ? japanTenYear - tenYear : null), "日美 10Y 利差衡量資金回流壓力", "flat"],
  };
  return [
    curveMetricByKind[kind] || curveMetricByKind.core,
    sovereignMetricByKind[kind] || sovereignMetricByKind.core,
    ["評等風險基準", kind === "short" ? formatAssetHubYield(aaaValue) : kind === "long" ? formatAssetHubYield(baaValue) : `Aaa ${formatAssetHubYield(aaaValue)} / Baa ${formatAssetHubYield(baaValue)}`, ratingDetailByKind[kind] || ratingDetailByKind.core, assetHubTone(model.moodyBaa)],
    riskMetricByKind[kind] || riskMetricByKind.core,
    buildAssetFinanceBondFocusEtfPulse(model, focus),
  ];
}

function buildAssetFinanceBondYieldFocusInsight(focus, model, context = {}) {
  if (!focus) {
    return {
      title: "利率焦點",
      headline: context.bondFocusLabel || "債券配置",
      summary: "點選殖利率卡片後，AI 會切換為該利率點的久期、曲線與信用風險判讀。",
      action: "",
      metric: null,
    };
  }
  const valueText = focus.valueText || formatAssetHubYield(focus.value);
  const curveSlope = context.curveSlope ?? model.curveSlope;
  const twUsSpread = context.twUsSpread;
  const fedRate = parseMarketNumber(model.fedFunds?.close);
  const ecbRate = parseMarketNumber(model.ecbDepositRate?.close);
  const bojRate = parseMarketNumber(model.bojCallRate?.close);
  const selectedLabel = focus.label || focus.shortLabel || "利率焦點";
  const moveText = focus.tone === "down"
    ? "殖利率上行會壓抑債券價格，先看防守與分批。"
    : focus.tone === "up"
      ? "殖利率回落有利久期修復，但仍需觀察是否擴散到 ETF 廣度。"
      : "殖利率變化中性，重點在曲線相對位置與下一個數據催化。";
  let title = `${selectedLabel} 焦點`;
  let summary = `${selectedLabel} 目前 ${valueText}。${moveText}`;
  let action = "AI 焦點建議：用這個利率點作為配置節奏，不要只看單日價格。";
  if (focus.scope === "us-yield") {
    const maturity = String(focus.maturity || focus.shortLabel || "");
    if (/2/.test(maturity)) {
      title = "短端政策利率焦點";
      summary = `美國 2Y 目前 ${valueText}，主要反映 Fed 路徑與再投資利率；Fed Funds ${formatAssetHubYield(fedRate)} 下，短債與現金替代仍是防守核心。${moveText}`;
      action = "AI 焦點建議：2Y 偏高時，短天期債與浮動利率工具優先；只有在 2Y 明確下行並帶動 5Y/10Y 時，再提高中長天期久期。";
    } else if (/5/.test(maturity)) {
      title = "中短端轉折焦點";
      summary = `美國 5Y 目前 ${valueText}，介於政策路徑與景氣折現之間；若 5Y 先於 10Y 下行，通常代表市場開始押注降息與成長放緩。${moveText}`;
      action = "AI 焦點建議：5Y 改善時可從短債逐步移向中天期核心債，但信用債仍需等 Baa-Aaa 或 HYG/LQD 同步確認。";
    } else if (/30/.test(maturity)) {
      title = "長端期限溢酬焦點";
      summary = `美國 30Y 目前 ${valueText}，對通膨預期、發債供給與期限溢酬更敏感；長端若上行，TLT/EDV 類長久期 ETF 波動會放大。${moveText}`;
      action = "AI 焦點建議：30Y 未轉弱前不宜把久期一次拉滿；若 30Y 與 10Y 同步回落，才提高長天期債權重。";
    } else {
      title = "核心折現率焦點";
      summary = `美國 10Y 目前 ${valueText}，是公債、投資級債、房貸與全球美元資產的核心折現率；10Y-2Y 曲線 ${formatAssetHubYield(curveSlope)}。${moveText}`;
      action = "AI 焦點建議：10Y 下行且 ETF 廣度轉正時，核心債與中長天期公債勝率提高；10Y 上行時先維持短中天期分層。";
    }
  } else if (focus.key === "bond-global-taiwan-10y") {
    title = "台灣主權利率焦點";
    summary = `台灣 10Y 目前 ${valueText}，台美 10Y 利差 ${formatAssetHubYield(twUsSpread)}；台灣美債 ETF 報酬需同時看海外久期、台幣匯率與折溢價。`;
    action = "AI 焦點建議：台灣 10Y 偏低時，本地債券收益補償有限，台灣掛牌美債 ETF 更要用匯率與美債曲線來決定進場節奏。";
  } else if (focus.key === "bond-global-germany-10y") {
    title = "歐元區主權利率焦點";
    summary = `德國 10Y 目前 ${valueText}，可作為歐元區無風險利率錨；ECB 存款利率 ${formatAssetHubYield(ecbRate)}，會影響歐洲投資級債與全球避險資金輪動。`;
    action = "AI 焦點建議：若德債殖利率回落且美元不再走強，全球核心債配置可更分散；若德債上行，非美債 ETF 先保守。";
  } else if (focus.key === "bond-global-japan-10y") {
    title = "日本利率正常化焦點";
    summary = `日本 10Y 目前 ${valueText}，BOJ 代理利率 ${formatAssetHubYield(bojRate)}；日本利率上行常牽動日圓、海外資金回流與全球長端利率。`;
    action = "AI 焦點建議：日本 10Y 若持續上行，長天期美債與全球債波動可能升高；要等 BOJ 壓力緩和後再放大久期。";
  }
  return {
    title,
    headline: `${selectedLabel} · ${valueText}`,
    summary,
    action,
    metric: ["目前焦點", valueText, `${selectedLabel} · ${focus.detail || "資料同步中"}`, focus.tone || "flat"],
  };
}

function buildAssetFinanceBondDashboardCommentary(model, context = {}) {
  const avgPct = context.avgPct;
  const aaaValue = context.aaaValue;
  const baaValue = context.baaValue;
  const creditSpread = context.creditSpread;
  const creditRiskPulse = context.creditRiskPulse;
  const twUsSpread = context.twUsSpread;
  const tltPct = parseMarketNumber(model.tlt?.pct);
  const tenYear = model.yields[2]?.value;
  const vixValue = parseMarketNumber(model.vix?.close);
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const fedRate = parseMarketNumber(model.fedFunds?.close);
  const ecbRate = parseMarketNumber(model.ecbDepositRate?.close);
  const bojRate = parseMarketNumber(model.bojCallRate?.close);
  const cpiPct = parseMarketNumber(model.usCpi?.pct);
  const pcePct = parseMarketNumber(model.usPce?.pct);
  const unemploymentRate = parseMarketNumber(model.usUnemployment?.close);
  const unemploymentChange = parseMarketNumber(model.usUnemployment?.change);
  const curveInverted = Number.isFinite(model.curveSlope) && model.curveSlope < 0;
  const creditHot = Number.isFinite(creditSpread) && creditSpread > 1;
  const durationRepair = Number.isFinite(tltPct) && tltPct > 0.15;
  const etfBreadthPositive = Number.isFinite(avgPct) && avgPct >= 0;
  const policyStillTight = (Number.isFinite(fedRate) && fedRate >= 3.5) || (Number.isFinite(ecbRate) && ecbRate >= 2);
  const inflationSticky = (Number.isFinite(cpiPct) && cpiPct > 0) || (Number.isFinite(pcePct) && pcePct > 0);
  const laborSoftening = (Number.isFinite(unemploymentChange) && unemploymentChange > 0) || (Number.isFinite(unemploymentRate) && unemploymentRate >= 4.3);
  const macroPressure = (Number.isFinite(tenYear) && tenYear >= 4.2) || (Number.isFinite(dxyPct) && dxyPct > 0.35) || (Number.isFinite(vixValue) && vixValue >= 20) || (policyStillTight && inflationSticky && !laborSoftening);
  const tone = creditHot || (curveInverted && !durationRepair) || macroPressure
    ? "down"
    : durationRepair && etfBreadthPositive
      ? "up"
      : "flat";
  const title = tone === "down"
    ? "防守優先，先控久期與信用曝險"
    : tone === "up"
      ? "久期修復可延伸，但要等曲線確認"
      : "核心債分層，等待利率與信用共振";
  const curveView = curveInverted
    ? "曲線倒掛代表短端壓力仍高，短債與現金再投資價值較突出。"
    : "曲線維持正斜率，短中長天期可分層配置，不必只押單一久期。";
  const durationView = durationRepair
    ? `TLT ${model.tlt?.pct || "--"}，長天期債已有修復訊號，但仍要觀察 10Y 是否同步下行。`
    : `TLT ${model.tlt?.pct || "--"}，長天期債尚未形成明確追價條件，久期先分批而非一次拉滿。`;
  const macroView = policyStillTight
    ? `Fed ${formatAssetHubYield(fedRate)}、ECB ${formatAssetHubYield(ecbRate)}、BOJ 代理利率 ${formatAssetHubYield(bojRate)}，政策利率仍是久期估值的主要約束；${inflationSticky ? "CPI/PCE 仍偏上行，降息交易不宜過度提前。" : "通膨動能若降溫，久期勝率才會改善。"}`
    : `Fed ${formatAssetHubYield(fedRate)}、ECB ${formatAssetHubYield(ecbRate)}、BOJ 代理利率 ${formatAssetHubYield(bojRate)}，政策壓力較前期緩和，需觀察 CPI/PCE 與就業是否支持殖利率下行。`;
  const laborView = laborSoftening
    ? `非農 ${formatGlobalValue(model.usPayrolls?.close, 0)}K、失業率 ${formatAssetHubYield(unemploymentRate)}，就業若轉弱會提高核心債與長天期債的修復條件。`
    : `非農 ${formatGlobalValue(model.usPayrolls?.close, 0)}K、失業率 ${formatAssetHubYield(unemploymentRate)}，就業尚未給出明確衰退訊號，信用債不宜只看殖利率高低。`;
  const creditView = Number.isFinite(creditRiskPulse)
    ? `Moody's Aaa ${formatAssetHubYield(aaaValue)}、Baa ${formatAssetHubYield(baaValue)}，Baa-Aaa 利差 ${formatAssetHubYield(creditSpread)}；HYG-LQD 相對強弱 ${formatAssetFinancePct(creditRiskPulse)}，若轉弱代表信用利差補償仍不足。`
    : `Moody's Aaa ${formatAssetHubYield(aaaValue)}、Baa ${formatAssetHubYield(baaValue)}，Baa-Aaa 利差 ${formatAssetHubYield(creditSpread)}，先用信用評等殖利率判斷風險溫度。`;
  const sovereignView = Number.isFinite(twUsSpread)
    ? `台美 10Y 利差 ${formatAssetHubYield(twUsSpread)}，台灣美債 ETF 需把匯率、折溢價與海外久期一起看。`
    : "台美 10Y 利差仍在同步，台灣債券 ETF 先以美債曲線與匯率作主要判讀。";
  const macroContext = context.macroContext || {};
  const macroMetrics = (macroContext.macroRows || []).map(([label, value, detail, tone]) => [
    `總體 · ${label}`,
    value,
    detail,
    tone,
  ]);
  const focusInsight = buildAssetFinanceBondYieldFocusInsight(context.yieldFocus, model, {
    bondFocusLabel: context.bondFocusLabel,
    curveSlope: model.curveSlope,
    twUsSpread,
  });
  const focusMetrics = buildAssetFinanceBondFocusMetricSet(model, {
    aaaValue,
    baaValue,
    creditRiskPulse,
    creditSpread,
    twUsSpread,
  }, context.yieldFocus);
  const action = tone === "down"
    ? "AI 評論：目前不適合只追長債價格彈性，配置順序以短天期、投資級核心債、再到長天期債為主；若 CPI/PCE 未降溫或失業率未轉弱，信用債需等利差或 HYG/LQD 相對強弱改善。"
    : tone === "up"
      ? "AI 評論：若 ETF 廣度維持為正、10Y 殖利率回落，且通膨或就業資料支持政策轉鬆，久期修復行情可延伸到中長天期公債；信用債仍需用 Baa-Aaa 與 HYG/LQD 驗證。"
      : "AI 評論：目前較像等待確認的核心債環境，短天期保留防守，中天期作核心，長天期只在殖利率下行、通膨降溫或 TLT 續強時提高權重。";
  return {
    tone,
    title: `${focusInsight.title}：${title}`,
    confidence: model.confidence,
    headline: `${focusInsight.headline} · ${context.research?.decisionLabel || "訊號同步中"}`,
    summary: `${focusInsight.summary} ${curveView} ${sovereignView} ${macroView} ${laborView} ${durationView} ${creditView}`,
    action: `${focusInsight.action} ${action}`,
    metrics: [
      ...(focusInsight.metric ? [focusInsight.metric] : []),
      ...focusMetrics,
      ...macroMetrics,
    ],
    macroCommentary: macroContext.macroCommentary || "",
  };
}

function getAssetFinanceBondCommentaryPoints(text, limit = 8) {
  const normalized = String(text || "")
    .replace(/\s+/g, " ")
    .replace(/^AI\s*總體基準以\s*/, "以 ")
    .replace(/AI\s*焦點建議：/g, "焦點建議：")
    .replace(/AI\s*評論：/g, "AI 評估：")
    .trim();
  if (!normalized) return [];
  const points = normalized.match(/[^。；]+[。；]?/g) || [normalized];
  return points
    .map((point) => point.trim())
    .filter(Boolean)
    .slice(0, limit);
}

function renderAssetFinanceBondCommentarySection(title, text, tone = "flat", limit = 8) {
  const points = getAssetFinanceBondCommentaryPoints(text, limit);
  if (!points.length) return "";
  return `
    <section class="asset-finance-bond-ai-section is-${escapeHtml(tone)}">
      <h5>${escapeHtml(title)}</h5>
      <ul>
        ${points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
      </ul>
    </section>
  `;
}

function renderAssetFinanceBondDashboardCommentary(commentary) {
  return `
    <div class="asset-finance-single-ai asset-finance-bond-dashboard-ai is-${escapeHtml(commentary.tone)}" id="asset-finance-bond-dashboard-commentary">
      <div class="asset-finance-single-ai-head">
        <span>
          <small>AI analysis commentary</small>
          <b>AI 分析評論：${escapeHtml(commentary.title)}</b>
        </span>
        <em>${escapeHtml(commentary.headline)} · 信心 ${escapeHtml(commentary.confidence || "--")}</em>
      </div>
      <div class="asset-finance-single-ai-grid">
        ${commentary.metrics.map(([label, value, detail, tone]) => `
          <span>
            <small>${escapeHtml(label)}</small>
            <b class="${escapeHtml(tone)}">${escapeHtml(value)}</b>
            <em>${escapeHtml(detail)}</em>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-bond-ai-sections">
        ${renderAssetFinanceBondCommentarySection("總體因子基準", commentary.macroCommentary, commentary.tone, 4)}
        ${renderAssetFinanceBondCommentarySection("市場判讀", commentary.summary, commentary.tone, 7)}
        ${renderAssetFinanceBondCommentarySection("AI 焦點建議", commentary.action, commentary.tone, 5)}
      </div>
    </div>
  `;
}

function buildAssetFinanceBondMacroContext(model, rows = getAssetFinanceBondRows(model), focus = null) {
  const bondPayload = { items: rows };
  const lqd = findAssetHubItem(bondPayload, "LQD");
  const hyg = findAssetHubItem(bondPayload, "HYG");
  const creditSpreadProxy = Number.isFinite(parseMarketNumber(hyg?.pct)) && Number.isFinite(parseMarketNumber(lqd?.pct))
    ? parseMarketNumber(hyg.pct) - parseMarketNumber(lqd.pct)
    : null;
  const macroTone = (item) => assetHubTone(item);
  const rateDetail = (item, fallback = "FRED") => item?.date ? `${item.date} · ${fallback}` : fallback;
  const fedRate = parseMarketNumber(model.fedFunds?.close);
  const ecbRate = parseMarketNumber(model.ecbDepositRate?.close);
  const bojRate = parseMarketNumber(model.bojCallRate?.close);
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const vixValue = parseMarketNumber(model.vix?.close);
  const policyTight = (Number.isFinite(fedRate) && fedRate >= 3.5) || (Number.isFinite(ecbRate) && ecbRate >= 2);
  const focusKind = getAssetFinanceBondFocusKind(focus);
  const focusLabel = focus?.shortLabel || focus?.label || "利率焦點";
  const focusValue = focus?.value;
  const useEuroMacro = focusKind === "germany";
  const useJapanMacro = focusKind === "japan";
  const macroRegionLabel = useEuroMacro ? "歐元區" : useJapanMacro ? "日本" : "美國";
  const macroLensLabel = focusKind === "taiwan"
    ? "台灣美債 ETF"
    : useEuroMacro
      ? "德債與歐元核心債"
      : useJapanMacro
        ? "日債與日圓利率"
        : "美債曲線";
  const inflationPrimary = useEuroMacro
    ? { label: "HICP", item: model.euroHicp, source: "FRED / Eurostat" }
    : useJapanMacro
      ? { label: "CPI", item: model.japanCpi, source: "FRED / OECD" }
      : { label: "CPI", item: model.usCpi, source: "FRED / BLS" };
  const inflationSecondary = useEuroMacro || useJapanMacro
    ? null
    : { label: "PCE", item: model.usPce, source: "FRED / BEA" };
  const laborPrimary = useEuroMacro
    ? { label: "失業率", item: model.euroUnemployment, source: "FRED / OECD" }
    : useJapanMacro
      ? { label: "失業率", item: model.japanUnemployment, source: "FRED / OECD" }
      : { label: "失業率", item: model.usUnemployment, source: "FRED / BLS" };
  const laborSecondary = useEuroMacro || useJapanMacro
    ? null
    : { label: "NFP", item: model.usPayrolls, source: "FRED / BLS", digits: 0, suffix: "K" };
  const policyDetailByKind = {
    short: "短端焦點：政策利率決定再投資與現金替代價值",
    belly: "中段焦點：政策轉向會先影響 5Y 評價",
    core: "10Y 焦點：政策路徑仍是核心折現率上緣",
    long: "長端焦點：政策若維持高位，期限溢酬容易放大",
    taiwan: "台灣焦點：本地利率低於美元利率時要看匯率補償",
    germany: "德國焦點：ECB 利率牽動歐債與非美核心債",
    japan: "日本焦點：BOJ 正常化會牽動全球長端利率",
  };
  const dxyDetailByKind = {
    short: "美元偏強會延後非美債修復",
    belly: "美元走弱有利中天期債估值修復",
    core: "10Y 焦點需同步看美元流動性",
    long: "美元與期限溢酬同向上行時，長債波動放大",
    taiwan: "台灣美債 ETF 需把美元與台幣匯率一起看",
    germany: "德債焦點需比較歐元與美元資金流",
    japan: "日債焦點需同步看日圓資金回流與美元壓力",
  };
  const inflationDetailByKind = {
    short: "通膨偏黏會延後短端降息定價",
    belly: "通膨回落才會提高 5Y 轉折可信度",
    core: "10Y 需要 CPI/PCE 降溫才有穩定下行條件",
    long: "長端最怕通膨預期與期限溢酬一起上行",
    taiwan: "美國通膨仍主導台灣美債 ETF 的海外久期",
    germany: "歐債焦點需比較通膨與 ECB 降息空間",
    japan: "日本焦點下，通膨會影響 BOJ 正常化節奏",
  };
  const laborDetailByKind = {
    short: "就業韌性會讓 Fed 維持高利率更久",
    belly: "就業轉弱會讓 5Y 率先反映降息與景氣放緩",
    core: "就業放緩有利 10Y 下行，但信用債需防違約風險",
    long: "就業轉弱支撐長債，但衰退風險會放大波動",
    taiwan: "就業數據影響美債 ETF 久期，同時牽動美元與台幣",
    germany: "歐元區就業若降溫，ECB 降息空間與德債支撐會同步提高",
    japan: "日本就業與薪資若續強，BOJ 正常化壓力會提高",
  };
  const policyValueByKind = {
    short: `${focusLabel} ${formatAssetHubYield(focusValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    belly: `${focusLabel} ${formatAssetHubYield(focusValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    core: `${focusLabel} ${formatAssetHubYield(focusValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    long: `${focusLabel} ${formatAssetHubYield(focusValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    taiwan: `台灣 ${formatAssetHubYield(taiwanTenYearValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    germany: `德國 ${formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close))} / ECB ${formatAssetHubYield(ecbRate)}`,
    japan: `日本 ${formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close))} / BOJ ${formatAssetHubYield(bojRate)}`,
  };
  const sovereignValueByKind = {
    short: `2Y ${formatAssetHubYield(focusValue)} / 10Y ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    belly: `5Y ${formatAssetHubYield(focusValue)} / 10Y ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    core: `10Y ${formatAssetHubYield(focusValue)} / 30Y ${formatAssetHubYield(model.yields?.[3]?.value)}`,
    long: `30Y ${formatAssetHubYield(focusValue)} / 10Y ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    taiwan: `台灣 ${formatAssetHubYield(taiwanTenYearValue)} / 美國 ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    germany: `德國 ${formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close))} / 美國 ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    japan: `日本 ${formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close))} / 美國 ${formatAssetHubYield(model.yields?.[2]?.value)}`,
  };
  const liquidityValueByKind = {
    short: `DXY ${formatGlobalValue(model.dxy?.close)} / 2Y ${formatAssetHubYield(focusValue)}`,
    belly: `DXY ${formatGlobalValue(model.dxy?.close)} / 5Y ${formatAssetHubYield(focusValue)}`,
    core: `DXY ${formatGlobalValue(model.dxy?.close)} / 10Y ${formatAssetHubYield(focusValue)}`,
    long: `DXY ${formatGlobalValue(model.dxy?.close)} / 30Y ${formatAssetHubYield(focusValue)}`,
    taiwan: `DXY ${formatGlobalValue(model.dxy?.close)} / 台灣10Y ${formatAssetHubYield(taiwanTenYearValue)}`,
    germany: `DXY ${formatGlobalValue(model.dxy?.close)} / 德10Y ${formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close))}`,
    japan: `DXY ${formatGlobalValue(model.dxy?.close)} / 日10Y ${formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close))}`,
  };
  const macroMoveOrLevel = (item, digits = 2) => {
    const pct = parseMarketNumber(item?.pct);
    if (Number.isFinite(pct)) return formatAssetFinancePct(pct);
    return formatGlobalValue(item?.close, digits);
  };
  const macroLevel = (item, digits = 2, suffix = "") => {
    const value = formatGlobalValue(item?.close, digits);
    return value === "--" ? value : `${value}${suffix}`;
  };
  const macroDate = (item) => item?.date || "同步中";
  const inflationValue = inflationSecondary
    ? `${inflationPrimary.label} ${macroMoveOrLevel(inflationPrimary.item)} / ${inflationSecondary.label} ${macroMoveOrLevel(inflationSecondary.item)}`
    : `${macroRegionLabel} ${inflationPrimary.label} ${macroMoveOrLevel(inflationPrimary.item)}`;
  const inflationDetail = inflationSecondary
    ? `${inflationDetailByKind[focusKind] || inflationDetailByKind.core}；指數 ${macroLevel(inflationPrimary.item)} / ${macroLevel(inflationSecondary.item)}`
    : `${inflationDetailByKind[focusKind] || inflationDetailByKind.core}；${macroRegionLabel} ${inflationPrimary.label} 指數 ${macroLevel(inflationPrimary.item)} · ${macroDate(inflationPrimary.item)}`;
  const unemploymentRate = parseMarketNumber(laborPrimary.item?.close);
  const laborValue = laborSecondary
    ? `${laborPrimary.label} ${formatAssetHubYield(unemploymentRate)} / ${laborSecondary.label} ${macroLevel(laborSecondary.item, laborSecondary.digits, laborSecondary.suffix)}`
    : `${macroRegionLabel}${laborPrimary.label} ${formatAssetHubYield(unemploymentRate)}`;
  const laborDetail = laborSecondary
    ? `${laborDetailByKind[focusKind] || laborDetailByKind.core}；${laborSecondary.label} ${laborSecondary.item?.pct || "--"} / 失業率變動 ${laborPrimary.item?.pct || "--"}`
    : `${laborDetailByKind[focusKind] || laborDetailByKind.core}；${macroRegionLabel}${laborPrimary.label} ${macroDate(laborPrimary.item)} · 變動 ${laborPrimary.item?.pct || "--"}`;
  const inflationTone = [inflationPrimary.item, inflationSecondary?.item]
    .some((item) => Number.isFinite(parseMarketNumber(item?.pct)) && parseMarketNumber(item.pct) > 0)
    ? "down"
    : "flat";
  const unemploymentChange = parseMarketNumber(laborPrimary.item?.change);
  const unemploymentPct = parseMarketNumber(laborPrimary.item?.pct);
  const payrollPct = parseMarketNumber(laborSecondary?.item?.pct);
  const laborCooling = (Number.isFinite(unemploymentChange) && unemploymentChange > 0)
    || (Number.isFinite(unemploymentPct) && unemploymentPct > 0)
    || (Number.isFinite(payrollPct) && payrollPct < 0);
  const inflationCardLabel = `${macroRegionLabel}通膨基準`;
  const laborCardLabel = `${macroRegionLabel}就業循環`;
  const macroRows = [
    [`${focusLabel} 政策壓力`, policyValueByKind[focusKind] || policyValueByKind.core, policyDetailByKind[focusKind] || policyDetailByKind.core, policyTight ? "down" : "flat"],
    [`${focusLabel} 主權錨`, sovereignValueByKind[focusKind] || sovereignValueByKind.core, `焦點利率相對位置 · ${focus?.detail || "資料同步中"}`, assetHubTone(focus)],
    [`${focusLabel} 美元流動性`, liquidityValueByKind[focusKind] || liquidityValueByKind.core, model.dxy?.pct ? `DXY ${model.dxy.pct} · ${dxyDetailByKind[focusKind] || dxyDetailByKind.core}` : dxyDetailByKind[focusKind] || "ICE / Yahoo Finance", assetHubTone(model.dxy)],
    [`${focusLabel} 風險溫度`, `VIX ${formatGlobalValue(model.vix?.close)} / ${focusLabel} ${formatAssetHubYield(focusValue)}`, model.vix?.pct ? `VIX ${model.vix.pct} · 風險升溫時先控信用債` : "Cboe / Yahoo Finance", Number.isFinite(vixValue) && vixValue >= 20 ? "down" : macroTone(model.vix)],
    [`${focusLabel} 信用代理`, formatAssetFinancePct(creditSpreadProxy), "HYG - LQD 相對強弱，驗證信用風險 appetite", assetFinancePctTone(creditSpreadProxy)],
    [inflationCardLabel, inflationValue, inflationDetail, inflationTone],
    [laborCardLabel, laborValue, laborDetail, laborCooling ? "up" : "flat"],
  ];
  const fed = formatAssetHubYield(fedRate);
  const ecb = formatAssetHubYield(ecbRate);
  const boj = formatAssetHubYield(bojRate);
  const policyText = useEuroMacro
    ? `ECB ${ecb}`
    : useJapanMacro
      ? `BOJ ${boj}`
      : `Fed ${fed}`;
  const inflationText = inflationSecondary
    ? `${inflationPrimary.label} ${macroLevel(inflationPrimary.item)}、${inflationSecondary.label} ${macroLevel(inflationSecondary.item)}`
    : `${macroRegionLabel} ${inflationPrimary.label} ${macroLevel(inflationPrimary.item)}`;
  const laborText = laborSecondary
    ? `${laborPrimary.label} ${formatAssetHubYield(unemploymentRate)}、${laborSecondary.label} ${macroLevel(laborSecondary.item, laborSecondary.digits, laborSecondary.suffix)}`
    : `${macroRegionLabel}${laborPrimary.label} ${formatAssetHubYield(unemploymentRate)}`;
  return {
    macroRows,
    macroCommentary: `AI 總體基準以 ${focusLabel} 為鏡頭：${macroLensLabel} 的通膨基準看 ${inflationText} 是否仍壓住 ${policyText} 的降息空間；就業循環看 ${laborText} 是否轉弱並提高久期修復條件。若政策利率偏高且通膨未明顯降溫，久期不宜一次拉長；若就業轉弱、美元與 VIX 降溫，${focusLabel} 對應的債券修復條件會提高。`,
    macroNote: "資料源：Fed / ECB / BOJ 代理利率、美國 CPI/PCE/非農/失業率、歐元區 HICP/失業率、日本 CPI/失業率使用 FRED；台灣使用 10Y 公債殖利率作央行與本地利率參考；美元、VIX 與信用債代理使用 Yahoo Finance / ETF 行情。",
  };
}

function renderAssetFinanceBondDecisionOverview(model, context = {}) {
  const avgPct = context.avgPct;
  const bondFocusLabel = context.bondFocusLabel || "債券配置";
  const research = context.research || {};
  const selectedYieldFocus = context.selectedYieldFocus;
  const twUsSpread = context.twUsSpread;
  const creditSpread = context.creditSpread;
  const creditRiskPulse = context.creditRiskPulse;
  const twoYearValue = model.yields?.[0]?.value;
  const usTenYearValue = model.yields?.[2]?.value;
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const aaaValue = context.aaaValue;
  const baaValue = context.baaValue;
  const curveInverted = Number.isFinite(model.curveSlope) && model.curveSlope < 0;
  const creditHot = Number.isFinite(creditSpread) && creditSpread > 1;
  const breadthTone = assetFinancePctTone(avgPct);
  const overviewTone = creditHot || curveInverted || breadthTone === "down" ? "down" : breadthTone === "up" ? "up" : "flat";
  const focusText = selectedYieldFocus
    ? `${selectedYieldFocus.label || selectedYieldFocus.shortLabel} ${selectedYieldFocus.valueText || formatAssetHubYield(selectedYieldFocus.value)}`
    : "利率焦點同步中";
  const curveText = curveInverted ? "曲線倒掛，短端防守優先" : "曲線正斜率，短中長天期可分層";
  const sovereignText = Number.isFinite(twUsSpread)
    ? twUsSpread < -1
      ? "台灣利率明顯低於美國，台灣美債 ETF 需同步看匯率與折溢價"
      : "台美利差接近，主權利率壓力較均衡"
    : "台美利差同步中";
  const creditText = creditHot
    ? "Baa-Aaa 利差偏高，信用債需要更高風險補償"
    : "信用利差目前中性，核心債可優先於高收益債";
  const metrics = [
    ["利率曲線", formatAssetHubYield(model.curveSlope), `2Y ${formatAssetHubYield(twoYearValue)} / 10Y ${formatAssetHubYield(usTenYearValue)}`, curveInverted ? "down" : "up"],
    ["主權利差", formatAssetHubYield(twUsSpread), `台灣 ${formatAssetHubYield(taiwanTenYearValue)} / 美國 ${formatAssetHubYield(usTenYearValue)}`, "flat"],
    ["信用風險", formatAssetHubYield(creditSpread), `Aaa ${formatAssetHubYield(aaaValue)} / Baa ${formatAssetHubYield(baaValue)}`, creditHot ? "down" : "flat"],
    ["ETF 廣度", formatAssetFinancePct(avgPct), `HYG-LQD ${formatAssetFinancePct(creditRiskPulse)}`, breadthTone],
  ];
  return `
    <div class="asset-finance-bond-decision-overview is-${escapeHtml(overviewTone)}">
      <section class="asset-finance-bond-decision-main">
        <small>Integrated bond signal</small>
        <h5>${escapeHtml(bondFocusLabel)}</h5>
        <p>AI 統整：目前以 ${escapeHtml(focusText)} 作為利率焦點；${escapeHtml(curveText)}。${escapeHtml(sovereignText)}。${escapeHtml(creditText)}。</p>
        <div class="asset-finance-bond-decision-tags">
          <span>樣本 ${escapeHtml(context.rowsLength ?? "--")} 筆</span>
          <span>${escapeHtml(research.decisionLabel || "訊號同步中")}</span>
          <span>${escapeHtml(selectedYieldFocus?.shortLabel || "10Y")} 焦點</span>
        </div>
      </section>
      <div class="asset-finance-bond-decision-metrics">
        ${metrics.map(([label, value, detail, tone]) => `
          <span class="is-${escapeHtml(tone)}">
            <small>${escapeHtml(label)}</small>
            <b>${escapeHtml(value)}</b>
            <em>${escapeHtml(detail)}</em>
          </span>
        `).join("")}
      </div>
    </div>
  `;
}

function renderAssetFinanceBondCenterDashboard(model) {
  const rows = getAssetFinanceBondRows(model);
  const research = buildAssetFinanceBondResearchImport(model);
  const etfRows = (model.bondEtfs || []).filter((item) => item && !item.error);
  const avgPct = averageAssetFinancePct(etfRows);
  const usTenYear = model.yields[2] || {};
  const usTenYearValue = usTenYear.value;
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const twUsSpread = Number.isFinite(taiwanTenYearValue) && Number.isFinite(usTenYearValue) ? taiwanTenYearValue - usTenYearValue : null;
  const aaaValue = parseMarketNumber(model.moodyAaa?.close);
  const baaValue = parseMarketNumber(model.moodyBaa?.close);
  const creditSpread = Number.isFinite(aaaValue) && Number.isFinite(baaValue) ? baaValue - aaaValue : null;
  const tltPct = parseMarketNumber(model.tlt?.pct);
  const lqd = rows.find((item) => String(item?.symbol || "").toUpperCase() === "LQD");
  const hyg = rows.find((item) => String(item?.symbol || "").toUpperCase() === "HYG");
  const creditRiskPulse = Number.isFinite(parseMarketNumber(hyg?.pct)) && Number.isFinite(parseMarketNumber(lqd?.pct))
    ? parseMarketNumber(hyg.pct) - parseMarketNumber(lqd.pct)
    : null;
  const usYieldFocusRows = model.yields.map((point) => ({
    key: getAssetFinanceBondFocusKey("us-yield", point.maturity),
    scope: "us-yield",
    label: `美國 ${point.maturity}`,
    shortLabel: point.maturity,
    maturity: point.maturity,
    value: point.value,
    valueText: formatAssetHubYield(point.value),
    detail: point.source || "--",
    tone: getAssetFinanceRateMoveTone(point.item || point),
  }));
  const globalYieldRows = [
    { key: "bond-global-taiwan-10y", scope: "global", label: "台灣 10Y", shortLabel: "台灣 10Y", value: taiwanTenYearValue, valueText: formatAssetHubYield(taiwanTenYearValue), detail: model.taiwanTenYear?.date || "Trading Economics / OTC interbank", tone: getAssetFinanceRateMoveTone(model.taiwanTenYear) },
    { key: "bond-global-germany-10y", scope: "global", label: "德國 10Y", shortLabel: "德國 10Y", value: parseMarketNumber(model.germanyTenYear?.close), valueText: formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close)), detail: model.germanyTenYear?.date || "FRED / OECD", tone: getAssetFinanceRateMoveTone(model.germanyTenYear) },
    { key: "bond-global-japan-10y", scope: "global", label: "日本 10Y", shortLabel: "日本 10Y", value: parseMarketNumber(model.japanTenYear?.close), valueText: formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close)), detail: model.japanTenYear?.date || "FRED / OECD", tone: getAssetFinanceRateMoveTone(model.japanTenYear) },
  ];
  const yieldFocusRows = [...usYieldFocusRows, ...globalYieldRows];
  const defaultFocus = yieldFocusRows.find((item) => item.key === "bond-us-yield-2-yr") || yieldFocusRows[0] || null;
  const selectedYieldFocus = yieldFocusRows.find((item) => item.key === assetFinanceBondFocusKey) || defaultFocus;
  if (selectedYieldFocus && assetFinanceBondFocusKey !== selectedYieldFocus.key) assetFinanceBondFocusKey = selectedYieldFocus.key;
  const macroContext = buildAssetFinanceBondMacroContext(model, rows, selectedYieldFocus);
  const bondFocusLabel = Number.isFinite(model.curveSlope) && model.curveSlope < 0
    ? "短天期防守"
    : Number.isFinite(tltPct) && tltPct > 0.15
      ? "久期修復"
      : Number.isFinite(avgPct) && avgPct >= 0
        ? "核心債分層"
        : "信用與久期降溫";
  const commentary = buildAssetFinanceBondDashboardCommentary(model, {
    aaaValue,
    avgPct,
    baaValue,
    bondFocusLabel,
    creditRiskPulse,
    creditSpread,
    research,
    twUsSpread,
    yieldFocus: selectedYieldFocus,
    macroContext,
  });
  return `
    <article class="panel-card asset-finance-module-card asset-finance-bond-research-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Bond Market Analysis Center</p>
          <h4>債券利率、久期與信用風險 Dashboard</h4>
        </div>
        <span>${escapeHtml(bondFocusLabel)} · Yield curve / global spread / credit</span>
      </div>
      ${renderAssetFinanceBondDecisionOverview(model, {
        aaaValue,
        avgPct,
        baaValue,
        bondFocusLabel,
        creditRiskPulse,
        creditSpread,
        research,
        rowsLength: rows.length,
        selectedYieldFocus,
        twUsSpread,
      })}
      <p class="stock-theory-note">美債殖利率曲線</p>
      <div class="asset-finance-yield-grid">
        ${usYieldFocusRows.map((focus) => renderAssetFinanceSyncStat(
          focus.shortLabel,
          focus.valueText,
          focus.detail,
          focus.tone,
          {
            focusKey: focus.key,
            active: selectedYieldFocus?.key === focus.key,
            ariaLabel: `切換 AI 分析評論：${focus.label}`,
          }
        )).join("")}
      </div>
      <p class="stock-theory-note">全球殖利率與主權利率</p>
      <div class="asset-finance-bond-radar-grid">
        ${globalYieldRows.map((focus) => renderAssetFinanceSyncStat(
          focus.shortLabel,
          focus.valueText,
          focus.detail,
          focus.tone,
          {
            focusKey: focus.key,
            active: selectedYieldFocus?.key === focus.key,
            ariaLabel: `切換 AI 分析評論：${focus.label}`,
          }
        )).join("")}
      </div>
      ${renderAssetFinanceBondDashboardCommentary(commentary)}
      <p class="stock-theory-note">資料統整：美債採 U.S. Treasury 官方曲線；台灣 10Y 讀取 Trading Economics 公開頁；德國、日本透過 FRED 讀取；Moody's Aaa/Baa 併入 AI 信用評等分析。${escapeHtml(macroContext.macroNote)}</p>
    </article>
  `;
}

function renderAssetFinanceBondRegionalMarketPanel(model) {
  const rows = getAssetFinanceBondRows(model);
  const bondPayload = { items: rows };
  const taiwanRows = rows.filter(isAssetFinanceTaiwanBond);
  const taiwanEtfs = taiwanRows.filter((item) => String(item?.type || "").includes("ETF"));
  const usRows = rows.filter((item) => {
    if (isAssetFinanceTaiwanBond(item)) return false;
    const text = `${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.market || ""} ${item?.region || ""}`;
    return getAssetHubRegion(item) === "美國" && /Treasury|TIPS|Corporate|High Yield|Muni|MBS|Bond|債券|公債|信用債|市政債|抗通膨|殖利率/i.test(text);
  });
  const usEtfs = usRows.filter((item) => String(item?.type || "").includes("ETF"));
  const globalRows = rows.filter((item) => {
    const text = `${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.market || ""} ${item?.region || ""}`;
    return /DE10Y|JP10Y|BNDX|IAGG|EMB|德國|日本|全球|International|Emerging|新興|非美|JGB|Gilts|歐洲|亞洲/i.test(text);
  });
  const globalEtfs = globalRows.filter((item) => String(item?.type || "").includes("ETF"));
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const usTenYear = model.yields[2] || {};
  const usTenYearValue = usTenYear.value;
  const twUsSpread = Number.isFinite(taiwanTenYearValue) && Number.isFinite(usTenYearValue) ? taiwanTenYearValue - usTenYearValue : null;
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const lqd = findAssetHubItem(bondPayload, "LQD");
  const hyg = findAssetHubItem(bondPayload, "HYG");
  const creditPulse = Number.isFinite(parseMarketNumber(hyg?.pct)) && Number.isFinite(parseMarketNumber(lqd?.pct))
    ? parseMarketNumber(hyg.pct) - parseMarketNumber(lqd.pct)
    : null;
  const strongestLabel = (items) => {
    const best = strongestAssetFinanceItem(items);
    return best ? `${best.symbol} ${best.pct || "--"}` : "同步中";
  };
  const examplesLabel = (items, fallback = []) => {
    const examples = items.length
      ? items.slice(0, 5).map((item) => `${item.symbol || "--"} ${item.pct || "--"}`)
      : fallback;
    return examples.join(" / ");
  };
  const groups = [
    {
      title: "台灣債券市場",
      tag: "TPEx / TWSE / CBC",
      rows: taiwanRows,
      tone: assetFinancePctTone(averageAssetFinancePct(taiwanEtfs)),
      role: "台幣帳戶觀察海外債券曝險與本地利率定位，重點不是只看配息，而是匯率、折溢價、久期與交易時差。",
      metrics: [
        ["台灣 10Y", formatAssetHubYield(taiwanTenYearValue), model.taiwanTenYear?.date || "OTC interbank", assetHubTone(model.taiwanTenYear)],
        ["台美 10Y 利差", formatAssetHubYield(twUsSpread), "台灣 10Y - 美國 10Y", "flat"],
        ["ETF 平均", formatAssetFinancePct(averageAssetFinancePct(taiwanEtfs)), `最強 ${strongestLabel(taiwanEtfs)}`, assetFinancePctTone(averageAssetFinancePct(taiwanEtfs))],
      ],
      ai: Number.isFinite(twUsSpread)
        ? `AI 觀察：台灣 10Y 明顯低於美國 10Y，台灣美債 ETF 的報酬主要來自海外久期與匯率；若台幣走強或折溢價擴大，需降低追價。`
        : "AI 觀察：台灣 10Y 資料同步中，先以台灣美債 ETF 平均漲跌、成交量與海外美債久期方向交叉判讀。",
      watch: "觀察央行政策、台幣匯率、ETF 折溢價、20 年美債 ETF 與 7-10 年美債 ETF 的強弱差。",
      examples: examplesLabel(taiwanEtfs, ["00679B", "00687B", "00696B", "00697B", "00795B"]),
    },
    {
      title: "美國債券市場",
      tag: "Treasury / FINRA / FRED",
      rows: usRows,
      tone: assetFinancePctTone(averageAssetFinancePct(usEtfs)),
      role: "全球無風險利率與信用定價核心；先看短端、10Y、30Y 曲線，再分公債、TIPS、投資級債、高收益與 MBS。",
      metrics: [
        ["10Y-2Y 曲線", formatAssetHubYield(model.curveSlope), model.curveSlope < 0 ? "倒掛壓力" : "正斜率", model.curveSlope < 0 ? "down" : "up"],
        ["長天期 TLT", model.tlt?.pct || "--", `收盤 ${formatGlobalValue(model.tlt?.close)}`, assetHubTone(model.tlt)],
        ["信用債脈衝", formatAssetFinancePct(creditPulse), "HYG - LQD", assetFinancePctTone(creditPulse)],
      ],
      ai: Number.isFinite(model.curveSlope) && model.curveSlope < 0
        ? "AI 觀察：曲線倒掛時不要只追長天期公債彈性，短天期與核心綜合債仍是防守底盤；信用債需等 HYG 相對 LQD 轉強。"
        : "AI 觀察：曲線轉正時可把核心債從短天期延伸到中天期，長天期需等 10Y 殖利率回落與 TLT 轉強確認。",
      watch: "觀察 Fed 路徑、2Y/10Y、TLT/IEF/SHY 輪動、LQD/HYG 信用風險與 TIPS 通膨預期。",
      examples: examplesLabel(usEtfs, ["SHY", "IEF", "TLT", "BND", "LQD"]),
    },
    {
      title: "國際與新興市場債券",
      tag: "EU / JGB / Gilts / EM",
      rows: globalRows,
      tone: assetFinancePctTone(averageAssetFinancePct(globalEtfs)),
      role: "補足非美利率、匯率避險與美元債風險；核心差異在外匯、央行政策分化與新興市場信用溢價。",
      metrics: [
        ["德國 10Y", formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close)), model.germanyTenYear?.date || "FRED", assetHubTone(model.germanyTenYear)],
        ["日本 10Y", formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close)), model.japanTenYear?.date || "FRED", assetHubTone(model.japanTenYear)],
        ["全球 ETF", formatAssetFinancePct(averageAssetFinancePct(globalEtfs)), `最強 ${strongestLabel(globalEtfs)}`, assetFinancePctTone(averageAssetFinancePct(globalEtfs))],
      ],
      ai: Number.isFinite(dxyPct) && dxyPct > 0
        ? "AI 觀察：美元偏強時，非美債與新興市場債需提高匯率與美元債信用風險權重；先看 BNDX/IAGG 是否止穩，再看 EMB 是否補強。"
        : "AI 觀察：美元壓力不高時，國際投資級債可作分散來源；若 EMB 強於 BNDX/IAGG，代表風險偏好正在向新興市場擴散。",
      watch: "觀察 ECB、BOJ、美元指數、匯率避險成本、BNDX/IAGG 與 EMB 的相對強弱。",
      examples: examplesLabel(globalRows, ["BNDX", "IAGG", "EMB", "DE10Y", "JP10Y"]),
    },
  ];
  return `
    <article class="panel-card asset-finance-module-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Regional bond markets</p>
          <h4>台灣、美國與國際債券市場</h4>
        </div>
        <span>${rows.length} 筆線上樣本</span>
      </div>
      <div class="asset-finance-bond-research-grid">
        ${groups.map((group) => `
          <section class="is-${escapeHtml(group.tone)}">
            <small>${escapeHtml(group.tag)} · ${group.rows.length || "待接"} 筆</small>
            <h5>${escapeHtml(group.title)}</h5>
            <p class="asset-finance-bond-region-role">${escapeHtml(group.role)}</p>
            <div class="asset-finance-bond-region-metrics">
              ${group.metrics.map(([label, value, detail, tone]) => `
                <span>
                  <small>${escapeHtml(label)}</small>
                  <b class="${escapeHtml(tone)}">${escapeHtml(value)}</b>
                  <em>${escapeHtml(detail)}</em>
                </span>
              `).join("")}
            </div>
            <p class="asset-finance-bond-region-ai">${escapeHtml(group.ai)}</p>
            <ul>
              <li>${escapeHtml(group.watch)}</li>
              <li>${escapeHtml(`代表標的：${group.examples}`)}</li>
            </ul>
          </section>
        `).join("")}
      </div>
    </article>
  `;
}

function renderAssetFinanceBondEtfCenterPanel(model) {
  const rows = getAssetFinanceBondRows(model);
  const bondPayload = { items: rows };
  const etfRows = (model.bondEtfs || []).filter((item) => item && !item.error);
  const onlineRows = Array.isArray(model.bondOnlineRows) ? model.bondOnlineRows.filter((item) => item && !item.error) : [];
  const etfUniverse = uniqueAssetHubItemsBySymbol([
    ...etfRows,
    ...onlineRows.filter((item) => /ETF/i.test(String(item?.type || ""))),
  ]);
  const allRows = etfUniverse.length ? etfUniverse : etfRows;
  const catalogCount = Number(model.bondCatalogCount) || onlineRows.length || allRows.length;
  const avgPct = averageAssetFinancePct(etfRows);
  const best = strongestAssetFinanceItem(etfRows);
  const shortDurationRows = getAssetHubItemsBySymbols(bondPayload, ["SHY", "VGSH", "BIL", "SGOV", "USFR", "TFLO"]);
  const middleDurationRows = getAssetHubItemsBySymbols(bondPayload, ["IEF", "VGIT", "BND", "AGG"]);
  const longDurationRows = getAssetHubItemsBySymbols(bondPayload, ["TLT", "VGLT", "EDV", "GOVZ"]);
  const buckets = [
    { key: "short", title: "短天期 / 貨幣市場", rows: shortDurationRows, detail: "用途：利率不確定時降低價格波動；風險：降息後收益率下滑、價格彈性有限。" },
    { key: "core", title: "中天期 / 核心綜合債", rows: middleDurationRows, detail: "用途：追蹤核心債與中段久期；風險：5Y/10Y 殖利率反彈造成淨值受壓。" },
    { key: "long", title: "長天期公債", rows: longDurationRows, detail: "用途：降息交易與高久期修復；風險：期限溢酬或通膨預期上升時回撤放大。" },
    { key: "credit", title: "信用債 / 高收益", rows: filterAssetFinanceBondRows(allRows, /LQD|HYG|JNK|VCSH|VCIT|IGIB|SJNK|ANGL|信用債|High Yield|Corporate/i), detail: "用途：收益增強與信用利差交易；風險：景氣轉弱時利差擴大。" },
    { key: "special", title: "抗通膨 / 市政 / MBS", rows: filterAssetFinanceBondRows(allRows, /TIP|SCHP|VTIP|MUB|VTEB|MBB|VMBS|抗通膨|市政|MBS/i), detail: "用途：補足特殊債種暴露；風險：實質利率、提前還款、稅務與流動性。" },
    { key: "global", title: "全球 / 新興市場", rows: filterAssetFinanceBondRows(allRows, /BNDX|IAGG|EMB|全球|International|Emerging/i), detail: "用途：補足非美利率、美元債與新興市場配置；風險：美元、主權利差與資金流。" },
    { key: "taiwan", title: "台灣債券 ETF", rows: allRows.filter(isAssetFinanceTaiwanBond), detail: "用途：台幣帳戶追蹤海外債券；風險：匯率、折溢價、交易時差與流動性。" },
    { key: "all", title: "全部債券 ETF", rows: allRows, detail: "用途：總覽線上債券 ETF 標的池；風險：需再依久期、信用、匯率與流動性分層。" },
  ].map((bucket) => ({ ...bucket, rows: uniqueAssetHubItemsBySymbol(bucket.rows || []) }));
  const selectedBucket = buckets.find((bucket) => bucket.key === assetFinanceBondEtfBucketKey) || buckets[0];
  if (selectedBucket.key !== assetFinanceBondEtfBucketKey) assetFinanceBondEtfBucketKey = selectedBucket.key;
  const selectedRows = selectedBucket.rows;
  const selectedAvgPct = averageAssetFinancePct(selectedRows);
  const selectedBest = strongestAssetFinanceItem(selectedRows);
  const selectedWeakest = selectedRows
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(left.pct) || 999) - (parseMarketNumber(right.pct) || 999))[0] || null;
  const selectedSymbols = selectedRows.length
    ? selectedRows.slice(0, 8).map((item) => `${item.symbol || "--"} ${item.pct || "--"}`).join(" / ")
    : "此分類暫無線上標的";
  const activeItem = [selectedBest, best, ...selectedRows, ...allRows].find((item) => item && item.symbol);
  const activeSymbol = String(activeItem?.symbol || "").toUpperCase();
  const selectedLensCounts = selectedRows.reduce((map, item) => {
    const lens = getAssetFinanceBondEtfLens(item);
    const label = lens.strategyBucket || lens.bucket || "未分類";
    map.set(label, (map.get(label) || 0) + 1);
    return map;
  }, new Map());
  const selectedDurationMix = selectedLensCounts.size
    ? [...selectedLensCounts.entries()]
      .sort((left, right) => right[1] - left[1])
      .map(([label, count]) => `${label} ${count} 檔`)
      .join(" / ")
    : "此分類暫無久期樣本";
  const selectedAdvancers = selectedRows.filter((item) => {
    const pct = parseMarketNumber(item?.pct);
    return Number.isFinite(pct) && pct > 0;
  }).length;
  const selectedDecliners = selectedRows.filter((item) => {
    const pct = parseMarketNumber(item?.pct);
    return Number.isFinite(pct) && pct < 0;
  }).length;
  const activeTone = activeItem ? assetFinancePctTone(parseMarketNumber(activeItem?.pct)) : "flat";
  const etfSignals = [
    [
      "久期輪動",
      selectedRows.length ? `${selectedRows.length} 檔` : "--",
      `${selectedBucket.title}：${selectedDurationMix}。${selectedBest ? `目前代表 ${selectedBest.symbol} ${selectedBest.pct || "--"}。` : "等待此分類標的同步。"}`,
      assetFinancePctTone(selectedAvgPct),
    ],
    [
      "ETF 廣度",
      selectedRows.length ? `${selectedAdvancers}/${selectedRows.length} 檔轉強` : "--",
      `${selectedBucket.title}平均 ${formatAssetFinancePct(selectedAvgPct)}；轉弱 ${selectedDecliners} 檔；${selectedBest ? `強勢 ${selectedBest.symbol} ${selectedBest.pct || "--"}` : "尚無強勢標的"}${selectedWeakest ? `，弱勢 ${selectedWeakest.symbol} ${selectedWeakest.pct || "--"}。` : "。"}`,
      assetFinancePctTone(selectedAvgPct),
    ],
    [
      "Bond single AI 連動",
      activeItem?.symbol || "--",
      activeItem
        ? `目前以 ${activeItem.symbol} 作為「${selectedBucket.title}」預設分析標的；點選下方表格其他檔，Bond single AI 會改用該檔重新判讀。`
        : `「${selectedBucket.title}」暫無可分析標的。`,
      activeTone,
    ],
  ];
  const analysisPayload = JSON.stringify(selectedRows.map(getAssetFinanceVolumePayloadItem));
  return `
    <article class="panel-card asset-finance-module-card asset-finance-bond-etf-center-card" id="asset-finance-bond-etf-center" data-asset-finance-volume-card data-asset-finance-analysis-mode="bond" data-asset-finance-volume-payload="${escapeHtml(analysisPayload)}">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Bond ETF center</p>
          <h4>債券 ETF 標的池、久期與信用分類</h4>
        </div>
        <span>${escapeHtml(selectedBucket.title)} · ${selectedRows.length} 檔 / 全部 ${allRows.length} 檔</span>
      </div>
      <div class="asset-finance-bond-etf-selected">
        <span><small>目前分類</small><b>${escapeHtml(selectedBucket.title)}</b><em>${selectedRows.length} 檔 · 目錄 ${catalogCount} 筆</em></span>
        <span><small>平均漲跌</small><b class="${assetFinancePctTone(selectedAvgPct)}">${formatAssetFinancePct(selectedAvgPct)}</b><em>${escapeHtml(selectedBucket.detail)}</em></span>
        <span><small>相對強勢</small><b>${selectedBest ? `${escapeHtml(selectedBest.symbol)} ${escapeHtml(selectedBest.pct || "--")}` : "--"}</b><em>${escapeHtml(selectedBest?.name || "等待線上資料")}</em></span>
        <span><small>相對弱勢</small><b>${selectedWeakest ? `${escapeHtml(selectedWeakest.symbol)} ${escapeHtml(selectedWeakest.pct || "--")}` : "--"}</b><em>${escapeHtml(selectedWeakest?.name || "等待線上資料")}</em></span>
      </div>
      <div class="asset-finance-bond-signal-grid">
        ${etfSignals.map(([title, value, detail, tone]) => `
          <section class="is-${escapeHtml(tone)}">
            <small>${escapeHtml(value)}</small>
            <b>${escapeHtml(title)}</b>
            <p>${escapeHtml(detail)}</p>
          </section>
        `).join("")}
      </div>
      <div class="asset-finance-bond-bucket-grid" aria-label="債券 ETF 分類檔數選擇">
        ${buckets.map((bucket) => {
          const bucketAvgPct = averageAssetFinancePct(bucket.rows);
          const bucketBest = strongestAssetFinanceItem(bucket.rows);
          const active = bucket.key === selectedBucket.key;
          return `
            <button class="asset-finance-bond-bucket-card is-${assetFinancePctTone(bucketAvgPct)}${active ? " is-active" : ""}" type="button" data-bond-etf-bucket="${escapeHtml(bucket.key)}" aria-pressed="${active ? "true" : "false"}">
              <small>${bucket.rows.length} 檔 · 平均 ${formatAssetFinancePct(bucketAvgPct)}</small>
              <b>${escapeHtml(bucket.title)}</b>
              <p>${escapeHtml(bucketBest ? `代表 ${bucketBest.symbol} ${bucketBest.pct || "--"}。${bucket.detail}` : `${bucket.detail} 點選後下方顯示此分類檔數與明細。`)}</p>
            </button>
          `;
        }).join("")}
      </div>
      <div class="asset-finance-bond-etf-current-list">
        <b>${escapeHtml(selectedBucket.title)}代表標的 · ${selectedRows.length} 檔</b>
        <span>${escapeHtml(selectedSymbols)}</span>
      </div>
      <div class="asset-finance-bond-etf-table-head">
        <span>
          <small>Filtered ETF list</small>
          <b>${escapeHtml(selectedBucket.title)}明細</b>
        </span>
        <em>${selectedRows.length} 檔 · 平均 ${formatAssetFinancePct(selectedAvgPct)} · ${selectedBest ? `強勢 ${escapeHtml(selectedBest.symbol || "--")}` : "等待線上資料"}</em>
      </div>
      <div class="global-table-wrap asset-finance-table-wrap">
        <table class="global-market-table">
          <thead><tr><th>名稱</th><th>代號</th><th>地區</th><th>交易所 / 來源</th><th>分類</th><th>收盤</th><th>漲跌幅</th><th>開盤</th><th>最高</th><th>最低</th><th>量能欄位</th><th>日期</th></tr></thead>
          <tbody>${renderAssetFinanceSelectableBondOnlineRows(selectedRows, activeSymbol) || '<tr><td colspan="12">此分類債券 ETF 線上資料同步中。</td></tr>'}</tbody>
        </table>
      </div>
      <div data-asset-finance-single-analysis-view>
        ${renderAssetFinanceBondSingleAnalysis(activeItem)}
      </div>
    </article>
  `;
}

function renderAssetFinanceBondsResearchSection(model) {
  return `
    <div class="asset-finance-zone-section is-bonds" id="asset-finance-bonds-dashboard">
      <div class="asset-finance-zone-heading">
        <div>
          <p class="panel-kicker">Bond research</p>
          <h3>債券研究區</h3>
        </div>
        <p>集中查看美債殖利率曲線、久期 ETF、信用債與台灣美債 ETF，同一區只放債券資料。</p>
      </div>
      <div class="asset-finance-zone-layout">
        ${renderAssetFinanceBondRegionalMarketPanel(model)}
        ${renderAssetFinanceBondCenterDashboard(model)}
        ${renderAssetFinanceBondResearchPanel(model)}
        ${renderAssetFinanceBondEtfCenterPanel(model)}
      </div>
    </div>
  `;
}

function renderAssetFinanceCrossReferenceSection(model) {
  return `
    <div class="asset-finance-zone-section is-cross">
      <div class="asset-finance-zone-heading">
        <div>
          <p class="panel-kicker">Cross-asset reference</p>
          <h3>跨資產風險參考</h3>
        </div>
        <p>美元、VIX、情境模擬與配置建議只作為風險參考，不與貴金屬或債券明細混表。</p>
      </div>
      <div class="asset-finance-cross-layout">
        ${renderAssetFinanceScenarioPanel(model)}
      </div>
    </div>
  `;
}

function renderAssetHubFinanceDashboard(metals, bonds, options = {}) {
  const model = buildAssetHubFinanceModel(metals, bonds);
  const view = options.view || "combined";
  const isBondsPage = view === "bonds";
  const isMetalsPage = view === "metals";
  const sections = [
    view === "combined" ? renderAssetFinanceCoreDashboard(model, metals, bonds) : "",
    !isBondsPage ? renderAssetFinanceMetalsResearchSection(model) : "",
    isBondsPage ? renderAssetFinanceBondsResearchSection(model) : "",
    !isBondsPage && !isMetalsPage ? renderAssetFinanceCrossReferenceSection(model) : "",
  ].filter(Boolean);
  return `
    <section class="section asset-finance-dashboard-section" id="asset-finance-dashboard">
      <div class="asset-finance-dashboard-stack">
        ${sections.join("")}
      </div>
    </section>
  `;
}

function initAssetFinanceBondFocusControls(root, payloads = []) {
  root.querySelectorAll("[data-bond-yield-focus]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextFocus = button.dataset.bondYieldFocus || "";
      if (!nextFocus || nextFocus === assetFinanceBondFocusKey) return;
      assetFinanceBondFocusKey = nextFocus;
      renderAssetHubPage(payloads);
      document.getElementById("asset-finance-bond-dashboard-commentary")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  });
  root.querySelectorAll("[data-bond-etf-bucket]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextBucket = button.dataset.bondEtfBucket || "all";
      if (!nextBucket || nextBucket === assetFinanceBondEtfBucketKey) return;
      assetFinanceBondEtfBucketKey = nextBucket;
      renderAssetHubPage(payloads);
      document.getElementById("asset-finance-bond-etf-center")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  });
}

function renderAssetHubCompactQuotePanel(kicker, title, items = [], badge = "", emptyText = "線上資料同步中。") {
  return `
    <article class="panel-card asset-hub-group-card asset-finance-quote-panel">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">${escapeHtml(kicker)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
        ${badge ? `<span>${escapeHtml(badge)}</span>` : ""}
      </div>
      ${renderAssetHubQuoteGrid(items, emptyText)}
    </article>
  `;
}

function renderAssetHubMetals() {
  return "";
}

function renderAssetHubBonds(payload) {
  const yields = [
    getAssetHubTreasuryYieldPoint(payload, "2 Yr", ["US2Y", "^UST2Y"]),
    getAssetHubTreasuryYieldPoint(payload, "5 Yr", ["^FVX"]),
    getAssetHubTreasuryYieldPoint(payload, "10 Yr", ["^TNX"]),
    getAssetHubTreasuryYieldPoint(payload, "30 Yr", ["^TYX"]),
  ];
  const twoYear = yields[0]?.value;
  const tenYear = yields[2]?.value;
  const curveSlope = Number.isFinite(tenYear) && Number.isFinite(twoYear) ? tenYear - twoYear : null;
  const curveLabel = curveSlope === null ? "資料不足" : curveSlope >= 0 ? "長短端正利差" : "殖利率曲線倒掛";
  const treasuryCurve = payload?.validation?.treasuryCurve || {};
  const secondaryMatched = Number(payload?.validation?.secondaryMatchedCount) || 0;
  const macroItems = getAssetHubUsableBySymbols(payload, ["US2Y", "^FVX", "^TNX", "^TYX", "DX-Y.NYB", "^VIX"]);
  const taiwanEtfs = getAssetHubUsableItems(payload).filter((item) => getAssetHubRegion(item) === "台灣" && String(item.type || "").includes("債券 ETF"));
  const treasuryEtfs = getAssetHubUsableBySymbols(payload, ["SHY", "VGSH", "IEF", "VGIT", "TLT", "VGLT", "BND", "AGG", "BNDX"]);
  const creditEtfs = getAssetHubUsableItems(payload).filter((item) => /信用債|High Yield|Investment Grade|新興市場債|抗通膨債|MBS|市政債/i.test(`${item.type || ""} ${item.name || ""}`));
  return `
    <section class="section asset-hub-section" id="asset-bonds">
      ${renderAssetHubSummary(payload, "債券研究區", "Bonds", "只整理美債殖利率曲線、久期 ETF、信用債、抗通膨債與台灣美債 ETF。", "bonds.html")}
      <div class="asset-hub-layout asset-hub-bonds-layout">
        <article class="panel-card asset-yield-curve-card"><div class="asset-hub-group-heading"><div><p class="panel-kicker">Yield curve</p><h4>美債殖利率曲線</h4></div><span>${escapeHtml(curveLabel)}</span></div><div class="asset-yield-points">${yields.map((point) => `<div><span>${escapeHtml(point.maturity)}</span><strong>${formatAssetHubYield(point.value)}</strong><small class="${assetHubTone(point.item)}">${escapeHtml(point.pct || "--")}</small></div>`).join("") || '<p class="stock-detail-empty">殖利率資料同步中。</p>'}</div><p>10 年期減 2 年期利差：<b>${curveSlope === null ? "--" : `${curveSlope >= 0 ? "+" : ""}${curveSlope.toFixed(2)} 個百分點`}</b>。${treasuryCurve.date ? ` 美國財政部官方曲線 ${escapeHtml(treasuryCurve.date)}，已比對 ${secondaryMatched} 個期限。` : " 美國財政部官方曲線暫時無法同步，僅顯示 Yahoo Finance 行情。"}</p></article>
        ${renderAssetHubCompactQuotePanel("Macro risk", "美元、VIX 與利率風險", macroItems, `${macroItems.length} 筆`, "總體風險資料同步中。")}
        ${renderAssetHubCompactQuotePanel("Taiwan bond ETF", "台灣美債 ETF", taiwanEtfs, `${taiwanEtfs.length} 檔`, "台灣債券 ETF 同步中。")}
        ${renderAssetHubCompactQuotePanel("Treasury ETF", "國際公債 ETF 久期分層", treasuryEtfs, `${treasuryEtfs.length} 檔`, "公債 ETF 同步中。")}
        ${renderAssetHubCompactQuotePanel("Credit / inflation", "信用債、抗通膨債與其他債券", creditEtfs.slice(0, 10), `${creditEtfs.length} 檔`, "信用債與抗通膨債資料同步中。")}
        ${renderAssetHubRegionalGroups(payload, "債券地區市場", () => true, "債券資料同步中。")}
      </div>
      ${renderAssetHubOnlineTable(payload, "債券")}
    </section>
  `;
}

function createAssetHubPlaceholder(category, title, kicker) {
  return {
    category,
    title,
    kicker,
    items: [],
    catalogCount: 0,
    loadedCount: 0,
    summary: { count: 0, advancers: 0, decliners: 0, avgPct: "--", strongest: "--" },
    validation: {
      verifiedCount: 0,
      primary: "Yahoo Finance 線上資料",
      reference: "來源同步中",
    },
    source: "Yahoo Finance 線上資料",
    updatedAt: "--",
  };
}

function getDerivativeOverviewItems(payload, preferredSymbols = [], limit = 6) {
  const usable = getAssetHubUsableItems(payload);
  const selected = [];
  const used = new Set();
  preferredSymbols.forEach((symbol) => {
    const item = usable.find((entry) => String(entry?.symbol || "").toUpperCase() === String(symbol).toUpperCase());
    if (!item || used.has(item.symbol)) return;
    selected.push(item);
    used.add(item.symbol);
  });
  usable
    .slice()
    .sort((left, right) => Math.abs(parseMarketNumber(right?.pct) || 0) - Math.abs(parseMarketNumber(left?.pct) || 0))
    .forEach((item) => {
      if (selected.length >= limit || used.has(item.symbol)) return;
      selected.push(item);
      used.add(item.symbol);
    });
  return selected.slice(0, limit);
}

function renderDerivativeOverviewQuote(item) {
  if (!item) return "";
  const metric = getAssetHubMetric(item);
  return `
    <article class="asset-quote-card derivatives-overview-quote">
      <span class="asset-quote-type">${escapeHtml(getAssetHubRegion(item))} · ${escapeHtml(item.exchange || item.dataSource || item.type || "市場行情")}</span>
      <strong>${escapeHtml(item.name || item.symbol || "--")}</strong>
      <small>${escapeHtml(item.symbol || "--")} · ${escapeHtml(item.date || "--")}</small>
      <div class="asset-quote-price">
        <b>${formatGlobalValue(item.close)}</b>
        <em class="${assetHubTone(item)}">${escapeHtml(item.pct || "--")}</em>
      </div>
      <footer>${escapeHtml(metric.label)} <b>${formatGlobalVolume(metric.value)}</b></footer>
    </article>
  `;
}

function renderDerivativeOverviewMetric(label, value, note, tone = "flat") {
  return `
    <span class="derivatives-overview-metric is-${escapeHtml(tone)}">
      <small>${escapeHtml(label)}</small>
      <b>${escapeHtml(value ?? "--")}</b>
      <em>${escapeHtml(note || "--")}</em>
    </span>
  `;
}

function buildDerivativeOverviewConclusion(futuresModel, optionsModel) {
  const futuresUp = futuresModel.aiTone === "up";
  const futuresDown = futuresModel.aiTone === "down";
  const optionsRiskHigh = optionsModel.riskScore >= 66;
  const optionsRiskLow = optionsModel.riskScore < 48;
  if (futuresUp && optionsRiskLow) {
    return { tone: "up", label: "風險偏好較穩", text: "期貨廣度偏多，選擇權風險仍在可控區間；續看台指、美股指數期貨與 Call 壓力是否同步上移。" };
  }
  if (futuresDown || optionsRiskHigh) {
    return { tone: "down", label: "波動與防守優先", text: "期貨動能偏弱或選擇權風險升溫；先確認 VIX、PCR、Put 支撐與主要股指期貨是否止穩。" };
  }
  return { tone: "flat", label: "多空拉鋸", text: "期貨廣度與選擇權籌碼尚未形成一致方向；以區間、支撐壓力與風險控管為主。" };
}

function getDerivativeOverviewTechnicalModel(payload) {
  const preferred = ["TX", "ES=F", "NQ=F", "YM=F"]
    .map((symbol) => findAssetHubItem(payload, symbol))
    .filter(Boolean);
  const item = preferred.find((entry) => Array.isArray(entry.series) && entry.series.length >= 60)
    || getAssetHubItems(payload).find((entry) => Array.isArray(entry.series) && entry.series.length >= 60)
    || preferred[0]
    || null;
  const rows = normalizeFuturesTechnicalCandles(item?.series || []);
  const snapshot = buildFuturesTechnicalSnapshot(rows);
  const latest = rows.at(-1)?.close ?? parseMarketNumber(item?.close);
  const toneFor = (positive, ready = true) => !ready ? "flat" : positive ? "up" : "down";
  const ma20Ready = Number.isFinite(snapshot.ma?.[20]) && Number.isFinite(latest);
  const ma60Ready = Number.isFinite(snapshot.ma?.[60]) && Number.isFinite(latest);
  const macdReady = Number.isFinite(snapshot.macd) && Number.isFinite(snapshot.macdSignal);
  const rsiReady = Number.isFinite(snapshot.rsi);
  const kdReady = Number.isFinite(snapshot.kd?.k) && Number.isFinite(snapshot.kd?.d);
  const cciReady = Number.isFinite(snapshot.cci);
  const indicators = [
    ["EMA / MA", ma20Ready ? `${formatGlobalValue(snapshot.ma[5])} / ${formatGlobalValue(snapshot.ma[20])}` : "資料同步中", ma20Ready ? (latest >= snapshot.ma[20] ? "價格位於 MA20 上方" : "價格位於 MA20 下方") : "需完整歷史 K 線", toneFor(latest >= snapshot.ma?.[20], ma20Ready)],
    ["MACD", macdReady ? formatFuturesIndicatorValue(snapshot.macd) : "--", macdReady ? (snapshot.macd >= snapshot.macdSignal ? "動能偏多" : "動能偏空") : "同步中", toneFor(snapshot.macd >= snapshot.macdSignal, macdReady)],
    ["RSI", rsiReady ? formatFuturesIndicatorValue(snapshot.rsi) : "--", rsiReady ? (snapshot.rsi >= 70 ? "偏熱" : snapshot.rsi <= 30 ? "偏弱" : "中性區") : "同步中", rsiReady && snapshot.rsi >= 70 ? "down" : rsiReady && snapshot.rsi >= 50 ? "up" : rsiReady ? "down" : "flat"],
    ["KD", kdReady ? `${formatFuturesIndicatorValue(snapshot.kd.k)} / ${formatFuturesIndicatorValue(snapshot.kd.d)}` : "--", kdReady ? (snapshot.kd.k >= snapshot.kd.d ? "K 值在 D 值上方" : "K 值在 D 值下方") : "同步中", toneFor(snapshot.kd?.k >= snapshot.kd?.d, kdReady)],
    ["CCI", cciReady ? formatFuturesIndicatorValue(snapshot.cci) : "--", cciReady ? (snapshot.cci >= 100 ? "強勢區" : snapshot.cci <= -100 ? "弱勢區" : "常態區") : "同步中", toneFor(snapshot.cci >= 0, cciReady)],
    ["ATR", Number.isFinite(snapshot.atr) ? formatFuturesIndicatorValue(snapshot.atr) : "--", "波動尺度", "flat"],
    ["布林通道", Number.isFinite(snapshot.bollinger?.mid) ? formatGlobalValue(snapshot.bollinger.mid) : "--", Number.isFinite(snapshot.bollinger?.upper) ? `${formatGlobalValue(snapshot.bollinger.lower)} – ${formatGlobalValue(snapshot.bollinger.upper)}` : "同步中", "flat"],
    ["量價 / OBV", Number.isFinite(snapshot.obv) ? formatGlobalVolume(snapshot.obv) : "--", Number.isFinite(snapshot.deltaVolume) ? `Delta ${formatGlobalVolume(snapshot.deltaVolume)}` : "同步中", toneFor(snapshot.deltaVolume >= 0, Number.isFinite(snapshot.deltaVolume))],
  ];
  const timeframe = [
    ["短線", snapshot.ma?.[5], Number.isFinite(snapshot.ma?.[5]) && Number.isFinite(latest) ? (latest >= snapshot.ma[5] ? "偏多" : "偏空") : "待資料"],
    ["中線", snapshot.ma?.[20], ma20Ready ? (latest >= snapshot.ma[20] ? "偏多" : "偏空") : "待資料"],
    ["長線", snapshot.ma?.[60], ma60Ready ? (latest >= snapshot.ma[60] ? "偏多" : "偏空") : "待資料"],
  ];
  return { item, rows, snapshot, latest, indicators, timeframe };
}

function renderDerivativeOverviewInstitutionSummary(data = {}) {
  const institutionOrder = ["外資", "投信", "自營商"];
  const rows = Array.isArray(data.rows)
    ? data.rows
      .filter((row) => row.institution !== "合計")
      .sort((left, right) => institutionOrder.indexOf(left.institution) - institutionOrder.indexOf(right.institution))
    : [];
  if (!rows.length) return '<p class="stock-detail-empty">三大法人資料同步中。</p>';
  const totalRow = (data.rows || []).find((row) => row.institution === "合計") || {};
  const totalLong = parseMarketNumber(totalRow.longContracts) || rows.reduce((sum, row) => sum + (parseMarketNumber(row.longContracts) || 0), 0);
  const totalShort = parseMarketNumber(totalRow.shortContracts) || rows.reduce((sum, row) => sum + (parseMarketNumber(row.shortContracts) || 0), 0);
  const summaryNet = parseMarketNumber(data.summary?.netContracts);
  const totalNet = Number.isFinite(summaryNet)
    ? summaryNet
    : rows.reduce((sum, row) => sum + (parseMarketNumber(row.netContracts) || 0), 0);
  const positiveCount = rows.filter((row) => (parseMarketNumber(row.netContracts) || 0) > 0).length;
  const negativeCount = rows.filter((row) => (parseMarketNumber(row.netContracts) || 0) < 0).length;
  const dominant = rows.slice().sort((left, right) => Math.abs(parseMarketNumber(right.netContracts) || 0) - Math.abs(parseMarketNumber(left.netContracts) || 0))[0];
  const totalTone = totalNet > 0 ? "up" : totalNet < 0 ? "down" : "flat";
  const mixed = positiveCount > 0 && negativeCount > 0;
  const overallLabel = totalNet > 0
    ? mixed ? "總體偏多、內部分歧" : "法人一致偏多"
    : totalNet < 0
      ? mixed ? "總體偏空、內部分歧" : "法人一致偏空"
      : "法人部位中性";
  const conclusion = totalNet > 0
    ? `${dominant?.institution || "法人"}是目前主要推升力量；合計淨多 ${formatGlobalVolume(totalNet)} 口，對盤勢形成下檔支撐${mixed ? "，但仍有反向法人部位抵銷，尚非一致性多方" : "，且三類法人方向一致"}。`
    : totalNet < 0
      ? `${dominant?.institution || "法人"}是目前主要壓力來源；合計淨空 ${formatGlobalVolume(Math.abs(totalNet))} 口，反彈時需留意避險與賣壓${mixed ? "，但部分法人仍有多方部位支撐" : ""}。`
      : "三大法人多空部位接近平衡，籌碼面暫時沒有明確方向推力。";
  const roleImpact = (name, net) => {
    const direction = net > 0 ? "淨多" : net < 0 ? "淨空" : "中性";
    if (name === "外資") return net > 0 ? `外資${direction}，對指數下檔偏支撐；需觀察是否連續增加。` : net < 0 ? `外資${direction}，可能提高指數避險與夜盤壓力。` : "外資部位接近平衡，方向影響有限。";
    if (name === "投信") return net > 0 ? `投信${direction}，偏向本地法人支撐，對回檔承接較有利。` : net < 0 ? `投信${direction}，內資支撐轉弱，需留意現貨同步調節。` : "投信部位中性，尚未形成內資方向。";
    return net > 0 ? `自營商${direction}，短線交易與避險部位偏正向。` : net < 0 ? `自營商${direction}，可能反映短線避險或造市風險升高。` : "自營商部位中性，短線避險影響有限。";
  };
  return `
    <div class="derivatives-overview-institution-summary is-${totalTone}">
      <div>
        <small>法人籌碼總結</small>
        <strong>${escapeHtml(overallLabel)}</strong>
        <p>${escapeHtml(conclusion)}</p>
      </div>
      <div class="derivatives-overview-institution-summary-metrics">
        <span><small>合計淨部位</small><b>${totalNet > 0 ? "+" : ""}${formatGlobalVolume(totalNet)}</b><em>口</em></span>
        <span><small>多 / 空總口數</small><b>${formatGlobalVolume(totalLong)} / ${formatGlobalVolume(totalShort)}</b><em>期貨契約</em></span>
        <span><small>法人方向</small><b>${positiveCount} 多 / ${negativeCount} 空</b><em>${mixed ? "籌碼分歧" : "方向一致"}</em></span>
        <span><small>主導法人</small><b>${escapeHtml(dominant?.institution || "--")}</b><em>${dominant ? `${(parseMarketNumber(dominant.netContracts) || 0) > 0 ? "+" : ""}${formatGlobalVolume(dominant.netContracts)} 口` : "--"}</em></span>
      </div>
    </div>
    <div class="derivatives-overview-institution-grid">
      ${rows.map((row) => {
        const net = parseMarketNumber(row.netContracts);
        const long = parseMarketNumber(row.longContracts) || 0;
        const short = parseMarketNumber(row.shortContracts) || 0;
        const gross = long + short;
        const longShare = gross > 0 ? long / gross * 100 : 50;
        const netRatio = gross > 0 && Number.isFinite(net) ? Math.abs(net) / gross * 100 : 0;
        const tone = net > 0 ? "up" : net < 0 ? "down" : "flat";
        const directionLabel = net > 0 ? "淨多" : net < 0 ? "淨空" : "中性";
        return `
          <section class="derivatives-overview-institution-card is-${tone}">
            <div class="derivatives-overview-institution-card-head">
              <div><small>${escapeHtml(row.institution || "--")}</small><b>${directionLabel}</b></div>
              <strong>${Number.isFinite(net) ? `${net > 0 ? "+" : ""}${formatGlobalVolume(net)}` : "--"}<em>口</em></strong>
            </div>
            <div class="derivatives-overview-institution-position">
              <span><small>多方</small><b>${formatGlobalVolume(long)}</b></span>
              <span><small>空方</small><b>${formatGlobalVolume(short)}</b></span>
            </div>
            <div class="derivatives-overview-institution-balance" style="--long:${longShare.toFixed(1)}%">
              <i></i>
              <div><small>多 ${(longShare).toFixed(1)}%</small><small>空 ${(100 - longShare).toFixed(1)}%</small></div>
            </div>
            <p>${escapeHtml(roleImpact(row.institution, net))}</p>
            <footer>淨部位占總曝險 ${netRatio.toFixed(2)}% · ${escapeHtml(row.status === "connected" ? "TAIFEX 已連線" : row.status || "資料同步中")}</footer>
          </section>
        `;
      }).join("")}
    </div>
    <div class="derivatives-overview-institution-source">
      <span>資料日 ${escapeHtml(data.tradeDate || "--")}</span>
      ${data.source?.url ? `<a href="${safeUrl(data.source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(data.source.name || "TAIFEX 官方來源")}</a>` : ""}
    </div>
  `;
}

function buildDerivativeFuturesPositionAnalysis(item, institutionData = null, scope = "us") {
  const pct = parseMarketNumber(item?.pct);
  const openInterest = parseMarketNumber(item?.openInterestValue ?? item?.openInterest);
  const volume = parseMarketNumber(item?.volumeValue ?? item?.volume);
  const rows = normalizeFuturesTechnicalCandles(item?.series || []);
  const snapshot = buildFuturesTechnicalSnapshot(rows);
  const latest = rows.at(-1)?.close ?? parseMarketNumber(item?.close);
  const ma20 = snapshot.ma?.[20];
  const volumes = rows.map((row) => row.volume).filter(Number.isFinite);
  const averageVolume20 = volumes.length ? averageFuturesValues(volumes.slice(-20)) : null;
  const hasInstitution = scope === "taiwan" && institutionData?.summary?.status === "connected";
  const institutionNet = hasInstitution ? parseMarketNumber(institutionData.summary?.netContracts) : null;
  let score = 50;
  if (hasInstitution) {
    const oiBase = Number.isFinite(openInterest) && openInterest > 0 ? openInterest : null;
    score += oiBase ? clampAssetHubScore(institutionNet / oiBase * 220, -32, 32) : Math.sign(institutionNet || 0) * 8;
  } else {
    if (Number.isFinite(pct)) score += clampAssetHubScore(pct * 4.5, -16, 16);
    if (Number.isFinite(latest) && Number.isFinite(ma20)) score += latest >= ma20 ? 8 : -8;
    if (Number.isFinite(volume) && Number.isFinite(averageVolume20) && averageVolume20 > 0) {
      score += volume >= averageVolume20 * 1.15 ? (Number.isFinite(pct) && pct >= 0 ? 5 : -5) : 0;
    }
  }
  score = Math.round(clampAssetHubScore(score, 12, 88));
  const tone = score >= 56 ? "up" : score <= 44 ? "down" : "flat";
  const label = score >= 64 ? "偏多支撐" : score >= 56 ? "略偏多" : score <= 36 ? "偏空壓力" : score <= 44 ? "略偏空" : "中性整理";
  const institutionRows = hasInstitution
    ? (institutionData.rows || []).filter((row) => row.institution !== "合計")
    : [];
  const sourceRole = hasInstitution ? "TAIFEX 三大法人" : scope === "taiwan" ? "法人資料待接入／行情代理" : "交易所行情部位代理";
  const impact = hasInstitution
    ? institutionNet > 0
      ? `法人淨多 ${formatGlobalVolume(institutionNet)} 口，對 ${item.symbol} 下檔形成籌碼支撐。`
      : institutionNet < 0
        ? `法人淨空 ${formatGlobalVolume(Math.abs(institutionNet))} 口，${item.symbol} 反彈時需留意避險壓力。`
        : `${item.symbol} 法人部位中性，籌碼方向尚未形成。`
    : tone === "up"
      ? `${item.symbol} 價格與量能代理偏多，部位動能對盤勢形成正向影響。`
      : tone === "down"
        ? `${item.symbol} 價格或量能代理偏弱，部位動能對盤勢形成負向壓力。`
        : `${item.symbol} 價量與趨勢代理互相抵銷，暫以中性看待。`;
  return {
    item,
    scope,
    score,
    tone,
    label,
    impact,
    hasInstitution,
    institutionData,
    institutionRows,
    institutionNet,
    sourceRole,
    pct,
    openInterest,
    volume,
    ma20,
    latest,
    averageVolume20,
  };
}

function renderDerivativeFuturesPositionCard(analysis) {
  const { item } = analysis;
  const metrics = analysis.hasInstitution
    ? analysis.institutionRows.map((row) => {
      const net = parseMarketNumber(row.netContracts);
      const tone = net > 0 ? "up" : net < 0 ? "down" : "flat";
      return `<span class="is-${tone}"><small>${escapeHtml(row.institution || "--")}</small><b>${Number.isFinite(net) ? `${net > 0 ? "+" : ""}${formatGlobalVolume(net)}` : "--"}</b></span>`;
    }).join("")
    : [
      ["漲跌", item?.pct || "--", assetHubTone(item)],
      ["成交量", formatGlobalVolume(analysis.volume), "flat"],
      ["未平倉", formatGlobalVolume(analysis.openInterest), "flat"],
    ].map(([label, value, tone]) => `<span class="is-${tone}"><small>${label}</small><b>${escapeHtml(value)}</b></span>`).join("");
  return `
    <article class="derivatives-overview-product-position is-${analysis.tone}">
      <header>
        <div><small>${escapeHtml(item?.exchange || item?.dataSource || analysis.sourceRole)}</small><h5>${escapeHtml(item?.name || item?.symbol || "--")}</h5><em>${escapeHtml(item?.symbol || "--")} · ${escapeHtml(item?.type || "期貨")}</em></div>
        <span><b>${analysis.score}</b><small>/100</small></span>
      </header>
      <div class="derivatives-overview-product-position-signal"><strong>${escapeHtml(analysis.label)}</strong><small>${escapeHtml(analysis.sourceRole)}</small></div>
      <div class="derivatives-overview-product-position-metrics">${metrics}</div>
      <p>${escapeHtml(analysis.impact)}</p>
      <footer>${analysis.hasInstitution ? `資料日 ${escapeHtml(analysis.institutionData?.tradeDate || "--")}` : `MA20 ${formatGlobalValue(analysis.ma20)} · 價格 ${formatGlobalValue(analysis.latest)}`} · ${escapeHtml(item?.date || "--")}</footer>
    </article>
  `;
}

function renderDerivativeOverviewInstitution(data = {}, futuresPayload = {}, institutionMap = {}) {
  const items = getAssetHubItems(futuresPayload);
  const groups = [
    { key: "taiwan", label: "台灣期貨", expected: 9, items: items.filter((item) => getFuturesMarketScope(item) === "taiwan") },
    { key: "us", label: "美國期貨", expected: 42, items: items.filter((item) => getFuturesMarketScope(item) === "us") },
    { key: "international", label: "國際期貨", expected: 6, items: items.filter((item) => getFuturesMarketScope(item) === "international") },
  ];
  const renderedGroups = groups.map((group) => {
    const analyses = group.items.map((item) => buildDerivativeFuturesPositionAnalysis(item, institutionMap[item.symbol], group.key));
    const positive = analyses.filter((item) => item.tone === "up").length;
    const negative = analyses.filter((item) => item.tone === "down").length;
    const averageScore = analyses.length ? Math.round(analyses.reduce((sum, item) => sum + item.score, 0) / analyses.length) : 50;
    const leader = analyses.slice().sort((left, right) => right.score - left.score)[0];
    const laggard = analyses.slice().sort((left, right) => left.score - right.score)[0];
    return `
      <details class="derivatives-overview-position-group is-${group.key}" ${group.key === "taiwan" ? "open" : ""}>
        <summary>
          <div><b>${escapeHtml(group.label)}</b><small>${group.items.length} / ${group.expected} 檔個別分析</small></div>
          <div class="derivatives-overview-position-group-stats"><span>${positive} 偏多</span><span>${negative} 偏空</span><span>均分 ${averageScore}</span></div>
        </summary>
        <div class="derivatives-overview-position-group-brief">
          <span><small>相對強勢</small><b>${escapeHtml(leader?.item?.symbol || "--")}</b><em>${leader?.score ?? "--"}/100</em></span>
          <span><small>相對弱勢</small><b>${escapeHtml(laggard?.item?.symbol || "--")}</b><em>${laggard?.score ?? "--"}/100</em></span>
          <p>${group.key === "taiwan" ? "台灣商品優先使用 TAIFEX 三大法人逐商品口數；來源待接入的商品才使用行情代理。" : `${group.label}沒有台灣外資／投信／自營商分類，依價格、MA20、成交量與可用未平倉輸出部位代理分析。`}</p>
        </div>
        <div class="derivatives-overview-product-position-grid">${analyses.map(renderDerivativeFuturesPositionCard).join("")}</div>
      </details>
    `;
  }).join("");
  return `
    <div class="derivatives-overview-position-coverage">
      <div><small>Coverage</small><strong>57 檔期貨個別籌碼分析</strong><p>台灣採 TAIFEX 三大法人；美國與國際採交易所行情部位代理，分開標示資料口徑。</p></div>
      <div>${groups.map((group) => `<span><b>${group.items.length}</b><small>${escapeHtml(group.label)}</small></span>`).join("")}</div>
    </div>
    <div class="derivatives-overview-position-groups">${renderedGroups}</div>
    ${data?.rows?.length ? `<div class="derivatives-overview-position-benchmark"><p class="panel-kicker">TX Institution Benchmark</p>${renderDerivativeOverviewInstitutionSummary(data)}</div>` : ""}
  `;
}

function getDerivativeOverviewNewsImpact(item = {}) {
  const text = `${item.title || ""} ${item.summary || ""}`.toLowerCase();
  const positivePatterns = [/\brise\b/, /\bgain\b/, /\brally\b/, /reopen/, /diplomatic/, /easing/, /ceasefire/, /lower inflation/, /rate cut/, /降息/, /和談/, /回升/, /上漲/, /降溫/, /改善/];
  const negativePatterns = [/\bfall\b/, /\bdrop\b/, /selloff/, /attack/, /war/, /tariff/, /tension/, /inflation surge/, /rate hike/, /衝突/, /制裁/, /下跌/, /通膨升溫/, /升息/, /惡化/];
  const positive = positivePatterns.filter((pattern) => pattern.test(text)).length;
  const negative = negativePatterns.filter((pattern) => pattern.test(text)).length;
  const categoryRules = [
    ["地緣政治", /iran|china|russia|ukraine|war|attack|ceasefire|diplomatic|tariff|sanction|tension|伊朗|中國|俄羅斯|烏克蘭|戰爭|攻擊|停火|外交|關稅|制裁|衝突/],
    ["總經與利率", /fed|central bank|interest rate|rate cut|rate hike|yield|inflation|cpi|ppi|jobs|payroll|gdp|聯準會|央行|利率|殖利率|通膨|就業|非農|經濟成長/],
    ["能源商品", /crude|oil|opec|natural gas|energy|原油|油價|天然氣|能源/],
    ["股指市場", /equity|stock|index|nasdaq|s&p|dow|nikkei|taiex|股市|股票|指數|那斯達克|標普|道瓊|日經|台股/],
    ["波動風險", /vix|volatility|risk-off|risk on|波動|避險|風險偏好/],
    ["金屬匯率", /gold|silver|copper|dollar|currency|forex|黃金|白銀|銅價|美元|匯率/],
  ];
  const matchedCategories = categoryRules.filter(([, pattern]) => pattern.test(text)).map(([label]) => label);
  const category = matchedCategories[0] || "市場焦點";
  const affectedMarkets = [];
  if (/equity|stock|index|nasdaq|s&p|dow|nikkei|taiex|股市|股票|指數|那斯達克|標普|道瓊|日經|台股/.test(text)) affectedMarkets.push("股指期貨");
  if (/crude|oil|opec|natural gas|energy|原油|油價|天然氣|能源/.test(text)) affectedMarkets.push("能源期貨");
  if (/fed|interest rate|yield|bond|利率|殖利率|債券/.test(text)) affectedMarkets.push("利率期貨");
  if (/gold|silver|copper|黃金|白銀|銅價/.test(text)) affectedMarkets.push("金屬期貨");
  if (/vix|volatility|option|波動|選擇權|避險/.test(text)) affectedMarkets.push("選擇權波動");
  if (!affectedMarkets.length) affectedMarkets.push("整體風險偏好");
  const tone = positive > negative ? "up" : negative > positive ? "down" : "flat";
  const label = tone === "up" ? "偏正向" : tone === "down" ? "偏負向" : "中性觀察";
  const value = tone === "up" ? 1 : tone === "down" ? -1 : 0;
  const effect = tone === "up"
    ? "可能改善風險偏好；仍需確認相關期貨走勢與 VIX 是否同步。"
    : tone === "down"
      ? "可能提高避險需求與隔夜波動；留意台指夜盤及選擇權權利金。"
      : "方向性訊號有限，先觀察期貨價格、成交量與波動率的實際反應。";
  return {
    tone,
    label,
    value,
    category,
    affectedMarkets,
    effect,
    relevance: positive + negative + matchedCategories.length + affectedMarkets.length,
  };
}

function buildDerivativeOverviewImpactModel(futures, options, futuresModel, optionsModel, technicalModel, institution, newsItems) {
  const es = findAssetHubItem(futures, "ES=F");
  const nq = findAssetHubItem(futures, "NQ=F");
  const vix = findAssetHubItemAny(options, ["^VIX", "VIX"]);
  const indexMoves = [es, nq].map((item) => parseMarketNumber(item?.pct)).filter(Number.isFinite);
  const indexAverage = indexMoves.length ? indexMoves.reduce((sum, value) => sum + value, 0) / indexMoves.length : 0;
  const vixMove = parseMarketNumber(vix?.pct);
  const newsImpacts = newsItems.map(getDerivativeOverviewNewsImpact);
  const newsNet = newsImpacts.reduce((sum, item) => sum + item.value, 0);
  const bullish = Number(optionsModel.probabilities?.bullish) || 0;
  const bearish = Number(optionsModel.probabilities?.bearish) || 0;
  const optionScore = Math.round(clampAssetHubScore(
    50 + (bullish - bearish) * 0.55 - Math.max(0, optionsModel.riskScore - 55) * 0.35,
    8,
    92,
  ));
  const internationalScore = Math.round(clampAssetHubScore(
    50 + indexAverage * 8 - (Number.isFinite(vixMove) ? vixMove * 1.4 : 0) + newsNet * 4,
    8,
    92,
  ));
  const institutionMap = futures.overviewInstitutions || {};
  const positionAnalyses = getAssetHubItems(futures).map((item) => buildDerivativeFuturesPositionAnalysis(item, institutionMap[item.symbol], getFuturesMarketScope(item)));
  const institutionScore = positionAnalyses.length
    ? Math.round(positionAnalyses.reduce((sum, item) => sum + item.score, 0) / positionAnalyses.length)
    : 50;
  const institutionPositive = positionAnalyses.filter((item) => item.tone === "up").length;
  const institutionNegative = positionAnalyses.filter((item) => item.tone === "down").length;
  const futuresScore = Math.round(clampAssetHubScore(futuresModel.aiScore, 8, 92));
  const toneForScore = (score) => score >= 58 ? "up" : score <= 42 ? "down" : "flat";
  const labelForScore = (score) => score >= 64 ? "正向推升" : score >= 56 ? "略偏正向" : score <= 36 ? "負向壓力" : score <= 44 ? "略偏負向" : "中性拉鋸";
  const technicalSignal = technicalModel.timeframe.map((item) => item[2]).filter((value) => value === "偏多" || value === "偏空");
  const technicalBullish = technicalSignal.filter((value) => value === "偏多").length;
  const technicalBearish = technicalSignal.filter((value) => value === "偏空").length;
  const factors = [
    {
      key: "trend",
      label: "期貨趨勢",
      score: futuresScore,
      tone: toneForScore(futuresScore),
      impact: labelForScore(futuresScore),
      evidence: `趨勢 ${futuresModel.aiScore}/100；廣度 ${futuresModel.advancers} 漲 / ${futuresModel.decliners} 跌；短中長 ${technicalBullish} 多 / ${technicalBearish} 空。`,
      conclusion: futuresScore >= 58 ? "期貨動能提高風險偏好，對現貨與選擇權方向形成正向支撐。" : futuresScore <= 42 ? "期貨動能轉弱，盤勢需要先確認支撐與量能是否止穩。" : "期貨多空尚未擴散，暫以區間行情解讀。",
    },
    {
      key: "options",
      label: "選擇權風險",
      score: optionScore,
      tone: toneForScore(optionScore),
      impact: labelForScore(optionScore),
      evidence: `多 ${bullish}% / 空 ${bearish}% / 震盪 ${optionsModel.probabilities.range}%；PCR ${optionsDecimal(optionsModel.pcr)}；VIX ${Number.isFinite(optionsModel.vixValue) ? optionsModel.vixValue.toFixed(2) : "--"}。`,
      conclusion: optionsModel.riskScore >= 66 ? "避險與權利金風險偏高，會壓抑追價與槓桿承受度。" : optionScore >= 58 ? "選擇權結構支持偏多情境，但仍需突破 Call OI 壓力確認。" : optionScore <= 42 ? "Put、VIX 或風險分數偏高，對盤勢形成下行壓力。" : "PCR 與 OI 接近平衡，選擇權偏向區間牽引。",
    },
    {
      key: "international",
      label: "國際消息",
      score: internationalScore,
      tone: toneForScore(internationalScore),
      impact: labelForScore(internationalScore),
      evidence: `美股指數期貨平均 ${indexAverage >= 0 ? "+" : ""}${indexAverage.toFixed(2)}%；VIX 變動 ${Number.isFinite(vixMove) ? `${vixMove >= 0 ? "+" : ""}${vixMove.toFixed(2)}%` : "--"}；新聞 ${newsImpacts.filter((item) => item.value > 0).length} 正 / ${newsImpacts.filter((item) => item.value < 0).length} 負。`,
      conclusion: internationalScore >= 58 ? "國際股指、波動率與消息面整體偏正向，降低隔夜外部壓力。" : internationalScore <= 42 ? "國際消息或波動率轉差，可能透過夜盤影響隔日台股與台指期。" : "國際因子互有抵銷，對本地盤勢影響暫時中性。",
    },
    {
      key: "institution",
      label: "法人／期貨籌碼",
      score: institutionScore,
      tone: toneForScore(institutionScore),
      impact: labelForScore(institutionScore),
      evidence: `共 57 檔：台灣 9／美國 42／國際 6；${institutionPositive} 檔偏多、${institutionNegative} 檔偏空。台灣使用 TAIFEX 法人，美國與國際使用部位代理。`,
      conclusion: institutionScore >= 58 ? "台灣法人與全球期貨部位代理整體偏多，對盤勢形成籌碼支撐。" : institutionScore <= 42 ? "法人與全球期貨部位代理整體偏空，反彈時需留意避險與賣壓。" : "57 檔期貨籌碼方向互有抵銷，暫未形成一致推力。",
    },
  ];
  const overallScore = Math.round(
    futuresScore * 0.3
      + optionScore * 0.28
      + internationalScore * 0.22
      + institutionScore * 0.2,
  );
  const overallTone = toneForScore(overallScore);
  const overallLabel = overallScore >= 64 ? "多方條件占優" : overallScore >= 56 ? "盤勢略偏多" : overallScore <= 36 ? "空方風險升高" : overallScore <= 44 ? "盤勢略偏空" : "盤勢震盪拉鋸";
  const support = optionsModel.oiWalls.putWall?.strike ?? technicalModel.snapshot.support20;
  const resistance = optionsModel.oiWalls.callWall?.strike ?? technicalModel.snapshot.resistance20;
  const aiConclusion = overallTone === "up"
    ? `四大因子合成 ${overallScore}/100，多方條件較完整；只要期貨廣度未轉弱、法人部位未翻空，盤勢仍以回測支撐後偏多看待。`
    : overallTone === "down"
      ? `四大因子合成 ${overallScore}/100，風險與空方壓力較高；在國際波動回落、PCR 降溫與期貨止穩前，優先控制槓桿。`
      : `四大因子合成 ${overallScore}/100，目前沒有一致方向；期貨、選擇權與法人籌碼互相抵銷，盤勢以支撐壓力區間處理。`;
  return {
    factors,
    overallScore,
    overallTone,
    overallLabel,
    aiConclusion,
    support,
    resistance,
    bullishCondition: `期貨廣度維持正向、VIX 未升溫，且指數有效站上 ${optionsWhole(resistance)}。`,
    bearishCondition: `指數跌破 ${optionsWhole(support)}，同時 PCR、VIX 或法人空方部位擴大。`,
  };
}

function renderDerivativeOverviewNews(items = []) {
  if (!items.length) return '<p class="stock-detail-empty">市場快訊同步中。</p>';
  const analysed = items.reduce((rows, item, index) => {
    const words = new Set(String(item?.title || "").toLowerCase().match(/[a-z0-9\u4e00-\u9fff]+/g) || []);
    const isNearDuplicate = rows.some((row) => {
      const smallerSize = Math.min(words.size, row.words.size);
      if (smallerSize < 4) return false;
      const overlap = [...words].filter((word) => row.words.has(word)).length;
      return overlap / smallerSize >= 0.72;
    });
    if (!isNearDuplicate) rows.push({ item, index, words, impact: getDerivativeOverviewNewsImpact(item) });
    return rows;
  }, []);
  const visible = analysed
    .slice()
    .sort((left, right) => right.impact.relevance - left.impact.relevance || left.index - right.index)
    .slice(0, 6);
  const positiveCount = analysed.filter(({ impact }) => impact.tone === "up").length;
  const negativeCount = analysed.filter(({ impact }) => impact.tone === "down").length;
  const neutralCount = analysed.length - positiveCount - negativeCount;
  const newsNet = positiveCount - negativeCount;
  const overallTone = newsNet > 0 ? "up" : newsNet < 0 ? "down" : "flat";
  const overallLabel = overallTone === "up" ? "消息面略偏正向" : overallTone === "down" ? "消息面風險升高" : "消息面多空拉鋸";
  const overallText = overallTone === "up"
    ? "正向消息較多，可能支撐風險偏好；仍需由美股指數期貨、台指夜盤與 VIX 共同確認。"
    : overallTone === "down"
      ? "負向消息較多，隔夜波動與避險需求可能提高；操作上宜降低槓桿並確認支撐。"
      : "消息方向尚未一致，暫不以單一標題推論行情，優先觀察價格與波動率反應。";
  const marketFocus = [...new Set(visible.flatMap(({ impact }) => impact.affectedMarkets))].slice(0, 4);
  return `
    <div class="derivatives-overview-news-brief is-${overallTone}">
      <div>
        <small>AI 消息面摘要</small>
        <strong>${overallLabel}</strong>
        <p>${overallText}</p>
      </div>
      <div class="derivatives-overview-news-stats">
        <span class="is-up"><small>偏正向</small><b>${positiveCount}</b></span>
        <span class="is-down"><small>偏負向</small><b>${negativeCount}</b></span>
        <span><small>中性</small><b>${neutralCount}</b></span>
        <span><small>有效事件</small><b>${analysed.length}</b></span>
      </div>
      <div class="derivatives-overview-news-focus">
        <small>主要影響市場</small>
        <div>${marketFocus.map((label) => `<span>${escapeHtml(label)}</span>`).join("") || "<span>等待分類</span>"}</div>
      </div>
    </div>
    <div class="derivatives-overview-news-grid">
      ${visible.map(({ item, impact }, index) => {
        return `<a class="is-${impact.tone}" href="${safeUrl(item.link || "#")}" target="_blank" rel="noopener noreferrer">
          <div class="derivatives-overview-news-card-head"><span>${String(index + 1).padStart(2, "0")} · ${escapeHtml(impact.category)}</span><em>${impact.label}</em></div>
          <b>${escapeHtml(item.title || "市場快訊")}</b>
          <p>${escapeHtml(impact.effect)}</p>
          <div class="derivatives-overview-news-markets">${impact.affectedMarkets.map((label) => `<span>${escapeHtml(label)}</span>`).join("")}</div>
          <footer><span>${escapeHtml(item.source || "公開來源")}</span><time>${escapeHtml(item.publishedAt || "--")}</time><i>閱讀原文 ↗</i></footer>
        </a>`;
      }).join("")}
    </div>
  `;
}

function renderDerivativesMarketOverview(futures, options) {
  const futuresModel = buildFuturesCenterModel(futures);
  const optionsModel = buildOptionsAiFunctionalModel(options);
  const technicalModel = getDerivativeOverviewTechnicalModel(futures);
  const tx = findAssetHubItemAny(futures, ["TX", "MTX", "TMF"]);
  const futuresQuotes = ["TX", "MTX", "TMF", "TE", "TF"].map((symbol) => findAssetHubItem(futures, symbol)).filter(Boolean);
  const optionQuotes = getDerivativeOverviewItems(options, ["^VIX", "^SKEW", "SPY", "QQQ"], 4);
  const strongest = futuresModel.strongest;
  const chain = optionsModel.chain || {};
  const chainAnalysis = chain.analysis || {};
  const chainSource = chain.source || {};
  const skew = optionsModel.maxIv !== null && optionsModel.minIv !== null ? optionsModel.maxIv - optionsModel.minIv : null;
  const topStrategy = buildOptionsStrategyRows(optionsModel)[0] || null;
  const gammaRisk = optionsModel.expiryDays !== null && optionsModel.expiryDays <= 7 && optionsModel.riskScore >= 60 ? "偏高" : optionsModel.expiryDays !== null && optionsModel.expiryDays <= 14 ? "中等" : "觀察";
  const thetaRisk = optionsModel.expiryDays !== null && optionsModel.expiryDays <= 7 ? "加速" : optionsModel.expiryDays !== null ? "一般" : "待到期日";
  const institution = futures.overviewInstitution || {};
  const newsItems = Array.isArray(options.overviewNews) ? options.overviewNews : [];
  const impactModel = buildDerivativeOverviewImpactModel(futures, options, futuresModel, optionsModel, technicalModel, institution, newsItems);
  const futuresSource = futures.source || futures.validation?.primary || "Yahoo Finance / TAIFEX";
  const optionsSource = chainSource.primary || options.source || options.validation?.primary || "TAIFEX / CBOE VIX";
  const updateText = [futures.updatedAt, options.updatedAt].filter(Boolean).join(" / ") || "--";
  const futuresDirection = futuresModel.aiTone === "up" ? "偏多" : futuresModel.aiTone === "down" ? "偏空" : "中性";
  const futuresDirectionText = futuresModel.aiTone === "up"
    ? "上漲商品較多，觀察強勢是否由台灣擴散至美國與國際期貨。"
    : futuresModel.aiTone === "down"
      ? "下跌商品較多，優先控制槓桿並確認主要股指支撐。"
      : "市場方向分歧，適合分區確認股指、利率、能源與金屬。";
  const optionDirectionTone = optionsModel.direction === "偏多" ? "up" : optionsModel.direction === "偏空" ? "down" : "flat";
  return `
    <section class="subpage-hero global-market-hero derivatives-overview-hero">
      <p class="eyebrow">Futures &amp; Options Market Overview</p>
      <h1>期貨及選擇權盤勢總覽</h1>
      <p class="hero-text">整合期貨趨勢、選擇權風險、國際消息與三大法人籌碼，說明各因子對盤勢造成的影響，並輸出 AI 綜合分析結論。</p>
      <p class="source-note">資料來源：${escapeHtml(futuresSource)}；${escapeHtml(optionsSource)} · 更新時間 ${escapeHtml(updateText)}</p>
    </section>

    <section class="section derivatives-overview-impact-section">
      <article class="panel-card derivatives-overview-impact-engine is-${impactModel.overallTone}">
        <div class="derivatives-overview-impact-head">
          <div>
            <p class="panel-kicker">AI Market Impact Engine</p>
            <h2>四大因子盤勢影響</h2>
            <p>由期貨趨勢、選擇權風險、國際消息與三大法人籌碼交叉驗證，不以單一指標直接推論方向。</p>
          </div>
          <span class="derivatives-overview-overall-score is-${impactModel.overallTone}"><small>綜合分數</small><b>${impactModel.overallScore}</b><em>/100</em></span>
        </div>
        <div class="derivatives-overview-factor-grid">
          ${impactModel.factors.map((factor) => `
            <section class="derivatives-overview-factor is-${factor.tone}">
              <div><small>${escapeHtml(factor.label)}</small><span>${escapeHtml(factor.impact)}</span></div>
              <strong>${factor.score}<em>/100</em></strong>
              <i style="--bar:${factor.score}%"></i>
              <p>${escapeHtml(factor.conclusion)}</p>
              <footer>${escapeHtml(factor.evidence)}</footer>
            </section>
          `).join("")}
        </div>
        <div class="derivatives-overview-ai-conclusion is-${impactModel.overallTone}">
          <div>
            <small>AI 綜合分析結論</small>
            <h3>${escapeHtml(impactModel.overallLabel)}</h3>
            <p>${escapeHtml(impactModel.aiConclusion)}</p>
          </div>
          <div class="derivatives-overview-ai-conditions">
            <span class="is-up"><small>多方成立條件</small><b>${escapeHtml(impactModel.bullishCondition)}</b></span>
            <span class="is-down"><small>風險轉弱條件</small><b>${escapeHtml(impactModel.bearishCondition)}</b></span>
          </div>
        </div>
        <div class="derivatives-overview-scoreboard">
          ${renderDerivativeOverviewMetric("臺指期", tx ? formatGlobalValue(tx.close) : "--", tx ? `${tx.symbol} ${tx.pct || "--"}` : "行情同步中", assetHubTone(tx || {}))}
          ${renderDerivativeOverviewMetric("期貨廣度", `${futuresModel.advancers} / ${futuresModel.decliners}`, "上漲 / 下跌", futuresModel.aiTone)}
          ${renderDerivativeOverviewMetric("相對強勢", strongest?.symbol || "--", strongest?.pct || "同步中", strongest ? "up" : "flat")}
          ${renderDerivativeOverviewMetric("VIX", Number.isFinite(optionsModel.vixValue) ? optionsModel.vixValue.toFixed(2) : "--", optionsModel.vix?.pct || "波動率", optionsModel.riskScore >= 66 ? "down" : "flat")}
          ${renderDerivativeOverviewMetric("OI PCR", optionsDecimal(optionsModel.pcr), "Put / Call", optionsModel.pcr !== null && optionsModel.pcr > 1.1 ? "down" : optionsModel.pcr !== null && optionsModel.pcr < 0.9 ? "up" : "flat")}
          ${renderDerivativeOverviewMetric("最大痛點", optionsWhole(optionsModel.maxPain), chain.selectedExpiry || "到期別同步中", "flat")}
        </div>
      </article>
    </section>

    <section class="section asset-hub-navigation-section">
      <div class="asset-hub-navigation derivatives-overview-navigation">
        <a class="asset-hub-nav-card is-futures" href="futures.html">
          <span>Futures Center</span><strong>開啟完整期貨盤勢</strong>
          <small>行情、技術分析、支撐壓力、未平倉、量能與 AI 趨勢分數</small>
        </a>
        <a class="asset-hub-nav-card is-options" href="options.html">
          <span>Options AI Platform</span><strong>開啟完整選擇權盤勢</strong>
          <small>逐履約價鏈、PCR、OI 分布、IV、Greeks、策略與風險中心</small>
        </a>
      </div>
    </section>

    <section class="section derivatives-overview-columns" id="asset-futures">
      <article class="panel-card futures-center-hero-card derivatives-overview-market-card">
        <div class="derivatives-overview-card-head">
          <div>
            <p class="panel-kicker">Global Futures Analysis Center</p>
            <h3>期貨盤勢摘要</h3>
            <p class="chart-subtitle">延續 futures.html 的台灣、美國、國際市場分層與同一批專用 API 行情。</p>
          </div>
          <a class="global-refresh" href="futures.html">查看完整分析</a>
        </div>
        <div class="futures-center-decision-panel is-${futuresModel.aiTone}">
          <small>期貨趨勢分數</small>
          <strong>${futuresModel.aiScore}<em>/100 · ${futuresDirection}</em></strong>
          <p>${escapeHtml(futuresDirectionText)}</p>
        </div>
        <div class="derivatives-overview-summary-block">
          <div class="derivatives-overview-summary-block-head">
            <div><small>趨勢結構與關鍵價位</small><b>${escapeHtml(technicalModel.item?.symbol || "期貨指標")}</b></div>
            <span>${technicalModel.snapshot.count || 0} 筆技術資料</span>
          </div>
          <div class="derivatives-overview-timeframe-grid">
            ${technicalModel.timeframe.map(([label, average, signal]) => `<span class="is-${signal === "偏多" ? "up" : signal === "偏空" ? "down" : "flat"}"><small>${label}趨勢</small><b>${signal}</b><em>${Number.isFinite(average) ? `均線 ${formatGlobalValue(average)}` : "歷史資料同步中"}</em></span>`).join("")}
          </div>
          <div class="derivatives-overview-levels">
            ${renderDerivativeOverviewMetric("支撐", formatGlobalValue(technicalModel.snapshot.support20), "20 日低點", "up")}
            ${renderDerivativeOverviewMetric("壓力", formatGlobalValue(technicalModel.snapshot.resistance20), "20 日高點", "down")}
            ${renderDerivativeOverviewMetric("相對強勢", futuresModel.strongest?.symbol || "--", futuresModel.strongest?.pct || "行情同步中", futuresModel.strongest ? "up" : "flat")}
            ${renderDerivativeOverviewMetric("相對弱勢", futuresModel.weakest?.symbol || "--", futuresModel.weakest?.pct || "行情同步中", futuresModel.weakest ? "down" : "flat")}
          </div>
        </div>
        <div class="derivatives-overview-summary-readout is-${futuresModel.aiTone}">
          <small>盤勢影響</small>
          <strong>${escapeHtml(futuresDirection)} · 漲跌廣度 ${futuresModel.advancers} / ${futuresModel.decliners}</strong>
          <p>${escapeHtml(`目前由 ${futuresModel.strongest?.name || futuresModel.strongest?.symbol || "強勢商品"} 領漲，${futuresModel.weakest?.name || futuresModel.weakest?.symbol || "弱勢商品"} 相對承壓；突破壓力前仍需交叉確認美國與國際期貨是否同步。`)}</p>
        </div>
        <div class="derivatives-overview-mini-stats">
          ${renderDerivativeOverviewMetric("可用行情", `${futuresModel.usable.length} / ${futuresModel.catalogCount}`, "線上 / 目錄")}
          ${renderDerivativeOverviewMetric("台灣期貨", `${futuresModel.taiwanItems.length} 檔`, "TAIFEX")}
          ${renderDerivativeOverviewMetric("美國期貨", `${futuresModel.usItems.length} 檔`, "CME / CBOT")}
          ${renderDerivativeOverviewMetric("國際期貨", `${futuresModel.internationalItems.length} 檔`, "ICE / SGX")}
        </div>
        <div class="asset-quote-grid derivatives-overview-quote-grid">
          ${futuresQuotes.map(renderDerivativeOverviewQuote).join("") || '<p class="stock-detail-empty">期貨行情同步中。</p>'}
        </div>
      </article>

      <article class="panel-card options-terminal-card derivatives-overview-market-card" id="asset-options">
        <div class="options-terminal-head">
          <div>
            <p class="panel-kicker">Options AI Trend &amp; Risk Center</p>
            <h3>選擇權盤勢摘要</h3>
            <p class="chart-subtitle">延續 options.html 的 TAIFEX 鏈、PCR、OI、VIX 與 AI 風險判讀。</p>
          </div>
          <span class="options-risk-light is-${optionsModel.riskLight.tone}">${escapeHtml(optionsModel.riskLight.label)}</span>
        </div>
        <div class="options-today-grid derivatives-overview-options-signal">
          <section class="options-ai-direction is-${optionsModel.riskLight.tone}">
            <small>AI 今日市場分析 · ${escapeHtml(getTaiwanOptionProductLabel(chain))}</small>
            <strong>${escapeHtml(optionsModel.direction)} · 風險 ${optionsModel.riskScore}/100</strong>
            <p>${escapeHtml(optionsModel.primaryRisk)}；信心分數 ${optionsModel.confidenceScore}/100。</p>
            <div class="options-probability-bars">
              ${[["多方", optionsModel.probabilities.bullish, "up"], ["空方", optionsModel.probabilities.bearish, "down"], ["震盪", optionsModel.probabilities.range, "flat"]].map(([label, value, tone]) => `<span class="is-${tone}"><b>${label}</b><i style="--bar:${Number(value) || 0}%"></i><em>${Number(value) || 0}%</em></span>`).join("")}
            </div>
          </section>
          <section class="options-risk-explain">
            <small>核心籌碼</small>
            <strong>PCR ${optionsDecimal(optionsModel.pcr)}</strong>
            <p>ATM ${optionsWhole(optionsModel.atmStrike)} · 最大痛點 ${optionsWhole(optionsModel.maxPain)} · 平均 IV ${optionsPct(optionsModel.avgIv)}</p>
          </section>
        </div>
        <div class="derivatives-overview-summary-block">
          <div class="derivatives-overview-summary-block-head">
            <div><small>部位、波動與到期風險</small><b>${escapeHtml(chain.selectedExpiry || "到期日同步中")}</b></div>
            <span>${escapeHtml(getTaiwanOptionProductLabel(chain))}</span>
          </div>
          <div class="derivatives-overview-exposure-grid">
            ${renderDerivativeOverviewMetric("Call OI", optionsWhole(optionsModel.callOi), "上方供給", "down")}
            ${renderDerivativeOverviewMetric("Put OI", optionsWhole(optionsModel.putOi), "下方支撐", "up")}
            ${renderDerivativeOverviewMetric("Gamma 風險", gammaRisk, `到期 ${optionsModel.expiryDays ?? "--"} 天`, gammaRisk === "偏高" ? "down" : "flat")}
            ${renderDerivativeOverviewMetric("Theta", thetaRisk, "時間價值衰減", thetaRisk === "加速" ? "down" : "flat")}
            ${renderDerivativeOverviewMetric("平均 IV", optionsPct(optionsModel.avgIv), `Skew ${optionsPct(skew)}`, "flat")}
            ${renderDerivativeOverviewMetric("Delta 偏向", optionsModel.direction, "PCR / VIX 綜合", optionDirectionTone)}
          </div>
          <div class="derivatives-overview-levels">
            ${renderDerivativeOverviewMetric("Put 支撐", optionsWhole(chainAnalysis.supportLevel ?? optionsModel.oiWalls.putWall?.strike), "最大 Put OI", "up")}
            ${renderDerivativeOverviewMetric("Call 壓力", optionsWhole(chainAnalysis.resistanceLevel ?? optionsModel.oiWalls.callWall?.strike), "最大 Call OI", "down")}
            ${renderDerivativeOverviewMetric("ATM", optionsWhole(optionsModel.atmStrike), "平值履約價", "flat")}
            ${renderDerivativeOverviewMetric("最大痛點", optionsWhole(optionsModel.maxPain), "到期磁吸參考", "flat")}
          </div>
        </div>
        <div class="derivatives-overview-summary-readout is-${optionDirectionTone}">
          <small>盤勢影響與策略</small>
          <strong>${escapeHtml(chainAnalysis.bias || optionsModel.direction || "盤勢同步中")} · ${escapeHtml(chainAnalysis.strategySuggestion || topStrategy?.name || "等待策略條件")}</strong>
          <p>${escapeHtml((chainAnalysis.reasons || [])[0] || optionsModel.primaryRisk || "等待更多資料交叉驗證。")}</p>
        </div>
        <div class="asset-quote-grid derivatives-overview-quote-grid derivatives-overview-option-quotes">
          ${optionQuotes.map(renderDerivativeOverviewQuote).join("") || '<p class="stock-detail-empty">選擇權觀察行情同步中。</p>'}
        </div>
        <a class="global-refresh derivatives-overview-card-link" href="options.html">查看完整選擇權分析</a>
      </article>
    </section>

    <section class="section derivatives-overview-decision-section">
        <article class="panel-card derivatives-overview-decision-card">
          <div class="asset-hub-group-heading"><div><p class="panel-kicker">AI Decision Brief</p><h4>AI 今日結論與策略</h4></div><span>信心 ${chainAnalysis.confidenceScore ?? optionsModel.confidenceScore}/100</span></div>
          <div class="derivatives-overview-decision-lead is-${optionDirectionTone}">
            <small>${escapeHtml(chainAnalysis.bias || optionsModel.direction || "盤勢同步中")}</small>
            <strong>${escapeHtml(chainAnalysis.strategySuggestion || topStrategy?.name || "等待策略條件")}</strong>
            <p>${escapeHtml((chainAnalysis.reasons || [])[0] || optionsModel.primaryRisk || "等待更多資料交叉驗證。")}</p>
          </div>
          <div class="derivatives-overview-levels">
            ${renderDerivativeOverviewMetric("Put 支撐", optionsWhole(chainAnalysis.supportLevel ?? optionsModel.oiWalls.putWall?.strike), "OI Wall", "up")}
            ${renderDerivativeOverviewMetric("Call 壓力", optionsWhole(chainAnalysis.resistanceLevel ?? optionsModel.oiWalls.callWall?.strike), "OI Wall", "down")}
            ${renderDerivativeOverviewMetric("最大痛點", optionsWhole(optionsModel.maxPain), "到期磁吸參考", "flat")}
            ${renderDerivativeOverviewMetric("策略適配", topStrategy ? `${topStrategy.score}/100` : "--", topStrategy?.name || "同步中", "flat")}
          </div>
          <div class="derivatives-overview-risk-radar">
            ${[
              ["市場風險", Math.max(0, 100 - futuresModel.aiScore)],
              ["波動風險", optionsModel.riskScore],
              ["流動性風險", futuresModel.usable.length ? Math.max(12, 55 - futuresModel.usable.length) : 70],
              ["到期風險", optionsModel.expiryDays !== null ? (optionsModel.expiryDays <= 3 ? 86 : optionsModel.expiryDays <= 7 ? 68 : 34) : 50],
            ].map(([label, score]) => `<span><small>${label}</small><i style="--bar:${Math.round(score)}%"></i><b>${Math.round(score)}</b></span>`).join("")}
          </div>
        </article>
    </section>

    <section class="section derivatives-overview-context-grid is-institution-only">
      <article class="panel-card derivatives-overview-context-card">
        <div class="asset-hub-group-heading"><div><p class="panel-kicker">TAIFEX Institution</p><h4>三大法人期貨籌碼</h4></div><span>${escapeHtml(institution.tradeDate || "--")}</span></div>
        ${renderDerivativeOverviewInstitution(institution, futures, futures.overviewInstitutions || {})}
        <p class="stock-theory-note">${escapeHtml(institution.message || "法人籌碼同步中；不以空白值推估部位。")}</p>
      </article>
    </section>

    <section class="section">
      <article class="panel-card derivatives-overview-news-card">
        <div class="asset-hub-group-heading"><div><p class="panel-kicker">Market Events &amp; News</p><h4>今日市場事件與盤後快訊</h4><p class="chart-subtitle">依期權關聯度整理公開快訊、自動合併相近標題，並標示可能影響市場與風險傳導方向。</p></div><span>${newsItems.length} 則公開來源</span></div>
        ${renderDerivativeOverviewNews(newsItems)}
        <p class="stock-theory-note">方向與分類來自新聞標題語意整理，不代表價格必然反應；正式經濟數據、央行行程與財報日曆須待官方事件資料源接入後才標示。</p>
      </article>
    </section>

  `;
}

function renderAssetHubPage(payloads = []) {
  const root = document.getElementById("asset-hub-root");
  if (!root) return;
  const mode = document.body.dataset.assetHubMode || "derivatives";
  const availablePayloads = payloads.filter(Boolean);
  const byCategory = new Map(availablePayloads.map((payload) => [payload.category, payload]));
  const futures = byCategory.get("futures") || createAssetHubPlaceholder("futures", "期貨", "Futures");
  const options = byCategory.get("options") || createAssetHubPlaceholder("options", "選擇權", "Options");
  const metals = byCategory.get("precious-metals") || createAssetHubPlaceholder("precious-metals", "貴金屬", "Precious Metals");
  const bonds = byCategory.get("bonds") || createAssetHubPlaceholder("bonds", "債券", "Bonds");
  const isBondsMode = mode === "bonds";
  const isMetalsMode = mode === "precious-metals";
  const isFinanceMode = ["finance", "bonds", "precious-metals"].includes(mode);
  const financeView = isBondsMode ? "bonds" : isMetalsMode ? "metals" : "combined";
  if (!isFinanceMode) {
    root.innerHTML = renderDerivativesMarketOverview(futures, options);
    return;
  }
  const navigation = isFinanceMode
    ? isBondsMode
      ? [
        ["債券研究區", "Bonds", "bonds", "#asset-finance-bonds-dashboard", bonds],
        ["貴金屬與債券", "Finance hub", "dashboard", "international-finance.html", bonds],
      ]
      : isMetalsMode
        ? [
          ["貴金屬研究區", "Precious metals", "metals", "#asset-finance-metals-dashboard", metals],
          ["債券研究區", "Bonds", "bonds", "bonds.html", bonds],
          ["貴金屬與債券", "Finance hub", "dashboard", "international-finance.html", metals],
        ]
        : [
          ["貴金屬", "Precious metals", "metals", "#asset-finance-metals-dashboard", metals],
          ["債券", "Bonds", "bonds", "bonds.html", bonds],
        ]
    : [
      ["期貨", "Futures", "futures", "#asset-futures", futures],
      ["選擇權", "Options", "options", "#asset-options", options],
    ];
  const hero = isBondsMode
    ? {
      kicker: "Bonds Platform",
      title: "債券與殖利率分析平台",
      text: "集中查看美債殖利率曲線、久期 ETF、信用債、台灣美債 ETF 與 AI 債券研究導入。",
    }
    : isMetalsMode
      ? {
        kicker: "Precious Metals Platform",
        title: "貴金屬避險分析平台",
        text: "集中查看黃金、白銀、鉑鈀、國際貴金屬 ETF 與台灣貴金屬同步狀態。",
      }
      : isFinanceMode
    ? {
      kicker: "Metals & Bonds",
      title: "貴金屬與債券研究平台",
      text: "整合 Yahoo Finance 線上行情與 U.S. Treasury 官方殖利率曲線；貴金屬與跨資產參考留在此頁，債券研究區移至獨立頁。",
    }
    : {
      kicker: "Futures & Options",
      title: "期權分析中心",
      text: "整合 TAIFEX、CME / ICE、Cboe / OCC 與 Yahoo Finance 線上資料；期貨、選擇權與未平倉依台灣、美國與其他市場分區呈現。",
    };
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">${escapeHtml(hero.kicker)}</p>
      <h1>${escapeHtml(hero.title)}</h1>
      <p class="hero-text">${escapeHtml(hero.text)}</p>
    </section>
    <section class="section asset-hub-navigation-section">
      <div class="asset-hub-navigation">
        ${navigation.map(([title, en, key, href, payload]) => `<a class="asset-hub-nav-card is-${key}" href="${safeUrl(href)}"><span>${escapeHtml(en)}</span><strong>${escapeHtml(title)}</strong><small>有效 ${payload?.summary?.count ?? 0} / 目錄 ${payload?.catalogCount ?? getAssetHubItems(payload).length} 筆 · ${escapeHtml((payload?.regionBreakdown || []).map((item) => item.region).join(" / ") || "地區同步中")}</small></a>`).join("")}
      </div>
    </section>
    ${isFinanceMode ? renderAssetHubFinanceDashboard(metals, bonds, { view: financeView }) : ""}
    ${isFinanceMode ? "" : renderAssetHubSchemaPanel(navigation.map(([, , , , payload]) => payload))}
    ${isFinanceMode ? "" : `${renderAssetHubFutures(futures)}${renderAssetHubOptions(options)}`}
  `;
  initAssetFinanceTrendSwitchers(root);
  initAssetFinanceVolumeSelectors(root);
  initAssetFinanceBondFocusControls(root, availablePayloads);
  root.querySelectorAll("[data-asset-load-more]").forEach((button) => {
    button.addEventListener("click", async () => {
      const category = button.dataset.assetLoadMore || "";
      const limit = Number(button.dataset.assetLoadLimit) || 24;
      if (!category) return;
      button.disabled = true;
      button.textContent = "同步更多行情...";
      try {
        const response = await fetchWithTimeout(`/api/global-market/${encodeURIComponent(category)}?limit=${limit}`, { cache: "no-store" }, 75000);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const nextPayload = await response.json();
        const current = byCategory.get(category);
        if (category === "options" && current?.optionChain) nextPayload.optionChain = current.optionChain;
        if (category === "options" && current?.taiwanOptionChain) nextPayload.taiwanOptionChain = current.taiwanOptionChain;
        renderAssetHubPage(availablePayloads.map((payload) => payload.category === category ? nextPayload : payload));
      } catch (error) {
        button.disabled = false;
        button.textContent = "載入更多已驗證行情";
        console.error(`Failed to load more ${category} data:`, error);
      }
    });
  });
  root.querySelectorAll("[data-tw-option-expiry-select]").forEach((select) => {
    select.addEventListener("change", async () => {
      const expiry = select.value || "";
      if (!expiry) return;
      select.disabled = true;
      try {
        const optionsPayload = byCategory.get("options") || options;
        const underlying = getActiveTaiwanOptionUnderlying(optionsPayload.taiwanOptionChain || {});
        const response = await fetchWithTimeout(`/api/options/chain?underlying=${encodeURIComponent(underlying)}&expiry=${encodeURIComponent(expiry)}&source=${encodeURIComponent(derivativesOptionsChainSource)}`, { cache: "no-store" }, 30000);
        const payload = await response.json();
        if (!response.ok || payload.success === false) throw new Error(payload?.error?.message || `HTTP ${response.status}`);
        const nextOptions = { ...optionsPayload, taiwanOptionChain: payload.data };
        renderAssetHubPage(availablePayloads.map((item) => item.category === "options" ? nextOptions : item));
      } catch (error) {
        select.disabled = false;
        console.error("Failed to switch Taiwan option expiry:", error);
      }
    });
  });
  root.querySelectorAll("[data-tw-option-product]").forEach((button) => {
    button.addEventListener("click", async () => {
      const underlying = String(button.dataset.twOptionProduct || "").toUpperCase();
      if (!underlying || button.classList.contains("is-active")) return;
      derivativesOptionsSelectedUnderlying = underlying;
      derivativesOptionsSelectedStrike = "";
      button.disabled = true;
      try {
        const response = await fetchWithTimeout(`/api/options/chain?underlying=${encodeURIComponent(underlying)}&source=${encodeURIComponent(derivativesOptionsChainSource)}`, { cache: "no-store" }, 30000);
        const payload = await response.json();
        if (!response.ok || payload.success === false) throw new Error(payload?.error?.message || `HTTP ${response.status}`);
        const optionsPayload = byCategory.get("options") || options;
        const nextOptions = { ...optionsPayload, taiwanOptionChain: payload.data };
        renderAssetHubPage(availablePayloads.map((item) => item.category === "options" ? nextOptions : item));
      } catch (error) {
        button.disabled = false;
        console.error("Failed to switch Taiwan option product:", error);
      }
    });
  });
  root.querySelectorAll("[data-asset-option-underlying]").forEach((button) => {
    button.addEventListener("click", async () => {
      const underlying = String(button.dataset.assetOptionUnderlying || "").toUpperCase();
      if (!underlying || button.classList.contains("is-active")) return;
      button.disabled = true;
      try {
        const response = await fetchWithTimeout(`/api/us-market/options-chain/${encodeURIComponent(underlying)}`, { cache: "no-store" }, 20000);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const chain = await response.json();
        const optionsPayload = byCategory.get("options") || options;
        const nextOptions = { ...optionsPayload, optionChain: chain };
        renderAssetHubPage(availablePayloads.map((item) => item.category === "options" ? nextOptions : item));
      } catch (error) {
        button.disabled = false;
        console.error(`Failed to load ${underlying} options chain:`, error);
      }
    });
  });
}

async function initAssetHubPage() {
  const root = document.getElementById("asset-hub-root");
  if (!root) return;
  const mode = document.body.dataset.assetHubMode || "derivatives";
  const isBondsMode = mode === "bonds";
  const isMetalsMode = mode === "precious-metals";
  const isFinanceMode = ["finance", "bonds", "precious-metals"].includes(mode);
  const loadingCopy = isBondsMode
    ? {
      eyebrow: "Bonds Platform",
      title: "債券與殖利率資料載入中",
      text: "正在取得債券、殖利率曲線與 ETF 資料...",
      errorTitle: "債券資料暫時無法載入",
    }
    : isMetalsMode
      ? {
        eyebrow: "Precious Metals Platform",
        title: "貴金屬資料載入中",
        text: "正在取得貴金屬與 ETF 資料...",
        errorTitle: "貴金屬資料暫時無法載入",
      }
      : isFinanceMode
        ? {
          eyebrow: "Metals & Bonds",
          title: "貴金屬與債券線上資料載入中",
          text: "正在取得債券與貴金屬資料...",
          errorTitle: "貴金屬與債券資料暫時無法載入",
        }
        : {
          eyebrow: "Futures & Options Overview",
          title: "期貨及選擇權盤勢總覽載入中",
          text: "正在同步主要期貨合約、TAIFEX 選擇權鏈、PCR、VIX 與風險訊號...",
          errorTitle: "期貨及選擇權盤勢暫時無法載入",
        };
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">${escapeHtml(loadingCopy.eyebrow)}</p>
      <h1>${escapeHtml(loadingCopy.title)}</h1>
      <p class="hero-text">${escapeHtml(loadingCopy.text)}</p>
    </section>
  `;
  const categories = isBondsMode
    ? ["bonds"]
    : isMetalsMode
      ? ["precious-metals"]
      : isFinanceMode
        ? ["precious-metals", "bonds"]
        : ["futures", "options"];
  const results = await Promise.allSettled(categories.map((category) => {
    const endpoint = isFinanceMode
      ? `/api/global-market/${encodeURIComponent(category)}?limit=all`
      : `/api/${encodeURIComponent(category)}?limit=all`;
    return fetchWithTimeout(endpoint, { cache: "no-store" }, 120000)
      .then((response) => {
        if (!response.ok) throw new Error(`${category} HTTP ${response.status}`);
        return response.json();
      })
      .then((responsePayload) => {
        if (!isFinanceMode && responsePayload?.success === false) {
          throw new Error(responsePayload?.error?.message || `${category} 資料暫不可用`);
        }
        return isFinanceMode ? responsePayload : responsePayload?.data;
      });
  }));
  const payloads = results.map((result) => result.status === "fulfilled" ? result.value : null).filter(Boolean);
  if (!payloads.length) {
    root.innerHTML = `
      <section class="subpage-hero">
        <p class="eyebrow">${escapeHtml(loadingCopy.eyebrow)}</p>
        <h1>${escapeHtml(loadingCopy.errorTitle)}</h1>
        <p class="hero-text">請稍後再試，或確認部署環境可連線 Yahoo Finance。</p>
      </section>
    `;
    return;
  }
  if (!isFinanceMode) {
    const taiwanInstitutionSymbols = ["TX", "MTX", "TMF", "TE", "TF", "SOF", "XIF", "STF", "ETF-F"];
    const [institutionResult, newsResult] = await Promise.allSettled([
      Promise.allSettled(taiwanInstitutionSymbols.map(async (symbol) => {
        const response = await fetchWithTimeout(`/api/institution?product=${encodeURIComponent(symbol)}`, { cache: "no-store" }, 20000);
        if (!response.ok) throw new Error(`${symbol} institution HTTP ${response.status}`);
        const responsePayload = await response.json();
        return [symbol, responsePayload?.data || {}];
      })).then((results) => Object.fromEntries(results.filter((result) => result.status === "fulfilled").map((result) => result.value))),
      fetchWithTimeout("/api/news?category=derivatives&symbol=%5EVIX&limit=8", { cache: "no-store" }, 20000).then(async (response) => {
        if (!response.ok) throw new Error(`news HTTP ${response.status}`);
        const responsePayload = await response.json();
        return responsePayload?.data?.items || [];
      }),
    ]);
    const futuresPayload = payloads.find((payload) => payload.category === "futures");
    const optionsPayload = payloads.find((payload) => payload.category === "options");
    if (futuresPayload && institutionResult.status === "fulfilled") {
      futuresPayload.overviewInstitutions = institutionResult.value;
      futuresPayload.overviewInstitution = institutionResult.value.TX || {};
    }
    if (optionsPayload && newsResult.status === "fulfilled") optionsPayload.overviewNews = newsResult.value;
  }
  const optionsPayload = payloads.find((payload) => payload.category === "options");
  renderAssetHubPage(payloads);
  if (optionsPayload) {
    fetchWithTimeout("/api/us-market/options-chain/SPY", { cache: "no-store" }, 16000)
      .then((response) => response.ok ? response.json() : null)
      .then((chain) => {
        if (chain) {
          optionsPayload.optionChain = chain;
          renderAssetHubPage(payloads);
        }
      })
      .catch((error) => console.warn("Failed to load SPY options chain:", error));
  }
}




































async function loadFullStockDetailFromLive(quickDetail, requestId) {
  const status = document.getElementById("search-status");
  const code = String(quickDetail?.code || "").trim();
  const market = String(quickDetail?.market || activeStockMarket || "").trim().toUpperCase();
  if (!code || quickDetail?.detailMode === "full") return;

  const cacheKey = getStockDetailCacheKey(code, market);
  const cached = stockFullDetailCache.get(cacheKey);
  if (cached) {
    if (requestId === stockDetailRequestId && code === activeStockCode && market === activeStockMarket) {
      renderStockDetail(cached);
      loadShareholderDistributionFromLive(cached, requestId);
      if (status) status.textContent = `${cached.code} ${cached.name} 完整基本面、籌碼面、消息面、估值歷史與公司資料已載入，更新時間 ${cached.cachedAt || "--"}。`;
    }
    return;
  }

  if (status) status.textContent = `${code} 即時資料已載入，正在補齊基本面、籌碼面、消息面、估值歷史與公司資料...`;

  let pending = stockFullDetailPending.get(cacheKey);
  if (!pending) {
    const params = new URLSearchParams({ refresh: "1" });
    if (market) params.set("market", market);
    pending = fetchWithTimeout(
      `/api/twse/stock/${encodeURIComponent(code)}?${params.toString()}`,
      { cache: "no-store" },
      120000,
    )
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .finally(() => {
        stockFullDetailPending.delete(cacheKey);
      });
    stockFullDetailPending.set(cacheKey, pending);
  }

  try {
    const fullDetail = await pending;
    stockFullDetailCache.set(cacheKey, fullDetail);
    if (requestId !== stockDetailRequestId || code !== activeStockCode || market !== activeStockMarket) return;
    renderStockDetail(fullDetail);
    loadShareholderDistributionFromLive(fullDetail, requestId);
    if (status) status.textContent = `${fullDetail.code} ${fullDetail.name} 完整基本面、籌碼面、消息面、估值歷史與公司資料已載入，更新時間 ${fullDetail.cachedAt || "--"}。`;
  } catch (error) {
    if (requestId === stockDetailRequestId && code === activeStockCode && market === activeStockMarket && status) {
      status.textContent = `${code} 即時資料已載入；完整基本面、籌碼面、消息面、估值歷史與公司資料同步失敗，請稍後重試。`;
    }
    console.error("Failed to load full stock detail:", error);
  }
}

function renderLiveSearchStockPreview(stock) {
  const container = document.getElementById("stock-detail");
  if (!container || !stock) return;
  const snapshotDate = data?.snapshotDate || new Date().toISOString().slice(0, 10);
  const tone = stock.tone || (parseAnalysisNumber(stock.pct) > 0 ? "up" : parseAnalysisNumber(stock.pct) < 0 ? "down" : "flat");
  container.innerHTML = `
    <div class="card-title-row">
      <h3>${escapeHtml(stock.code)} ${escapeHtml(stock.name)}</h3>
      <div class="stock-detail-actions">
        <span class="chip ${tone === "up" ? "chip-green" : tone === "down" ? "chip-red" : "chip-blue"}">${escapeHtml(snapshotDate)}</span>
      </div>
    </div>
    <div class="stock-detail-empty">live 搜尋行情已載入；技術走勢、籌碼、基本面與消息資料正在同步線上完整資料。</div>
    <div class="detail-metrics">
      <div><span>收盤價</span><strong>${escapeHtml(stock.close || "--")}</strong></div>
      <div><span>漲跌幅</span><strong class="${toneClass(tone)}">${escapeHtml(stock.pct || "--")}</strong></div>
      <div><span>漲跌</span><strong class="${toneClass(tone)}">${escapeHtml(stock.change || "--")}</strong></div>
      <div><span>成交量</span><strong>${escapeHtml(stock.volume || "--")}</strong></div>
      <div><span>成交金額</span><strong>${escapeHtml(stock.turnover || "--")}</strong></div>
      <div><span>開盤</span><strong>${escapeHtml(stock.open || "--")}</strong></div>
      <div><span>最高 / 最低</span><strong>${escapeHtml(stock.high || "--")} / ${escapeHtml(stock.low || "--")}</strong></div>
      <div><span>市場</span><strong>${escapeHtml(stock.marketLabel || stock.market || "--")}</strong></div>
    </div>
  `;
}

async function loadShareholderDistributionFromLive(detail, requestId) {
  const code = String(detail?.code || "").trim();
  const market = String(detail?.market || activeStockMarket || "").trim().toUpperCase();
  if (!code || requestId !== stockDetailRequestId) return;
  const key = getStockDetailCacheKey(code, market);
  const existing = detail.shareholderDistribution;
  if (existing && Object.keys(existing).length && existing.available !== false) return;
  const cached = stockShareholderCache.get(key);
  if (cached) {
    if (requestId === stockDetailRequestId && code === activeStockCode && market === activeStockMarket) {
      renderStockDetail({ ...(activeRenderedStockDetail || detail), shareholderDistribution: cached });
    }
    return;
  }
  let pending = stockShareholderPending.get(key);
  if (!pending) {
    pending = fetchWithTimeout(
      `/api/twse/stock/${encodeURIComponent(code)}/shareholders`,
      { cache: "no-store" },
      30000,
    )
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .finally(() => {
        stockShareholderPending.delete(key);
      });
    stockShareholderPending.set(key, pending);
  }
  try {
    const payload = await pending;
    const distribution = payload.shareholderDistribution || {};
    stockShareholderCache.set(key, distribution);
    if (requestId !== stockDetailRequestId || code !== activeStockCode || market !== activeStockMarket) return;
    renderStockDetail({ ...(activeRenderedStockDetail || detail), shareholderDistribution: distribution });
  } catch (error) {
    console.error("Failed to load shareholder distribution:", error);
  }
}

async function loadStockDetail(code, market = "", fallbackStock = null) {
  const status = document.getElementById("search-status");
  const requestedCode = String(code || "").trim();
  const requestedMarket = String(market || "").trim().toUpperCase();
  if (!requestedCode) return;

  activeStockCode = requestedCode;
  activeStockMarket = requestedMarket;
  const requestId = ++stockDetailRequestId;

  const detailContainer = document.getElementById("stock-detail");
  if (fallbackStock) {
    renderLiveSearchStockPreview(fallbackStock);
  } else if (detailContainer) {
    detailContainer.innerHTML = `<div class="stock-detail-empty">正在同步 ${escapeHtml(requestedCode)} 即時個股資料與近期走勢...</div>`;
  }
  if (status) {
    status.textContent = fallbackStock
      ? `${requestedCode} live 搜尋行情已顯示，正在同步近期技術資料...`
      : `正在同步 ${requestedCode} 即時個股資料...`;
  }

  try {
    const params = new URLSearchParams({ refresh: "1", quick: "1" });
    if (requestedMarket) params.set("market", requestedMarket);
    const detailUrl = `/api/twse/stock/${encodeURIComponent(requestedCode)}?${params.toString()}`;
    const response = await fetchWithTimeout(detailUrl, { cache: "no-store" }, 90000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const detail = await response.json();

    if (requestId !== stockDetailRequestId || detail.code !== activeStockCode) return;
    activeStockMarket = String(detail.market || requestedMarket || "").trim().toUpperCase();

    renderStockDetail(detail);
    loadShareholderDistributionFromLive(detail, requestId);
    if (status) status.textContent = `${detail.code} ${detail.name} 即時行情與近期技術資料已載入，正在補齊完整資料...`;
    loadFullStockDetailFromLive(detail, requestId);
  } catch (error) {
    if (requestId !== stockDetailRequestId) return;
    if (status) {
      status.textContent = `${requestedCode} 即時個股資料同步失敗，請稍後重新搜尋。`;
    }
    if (detailContainer) {
      detailContainer.innerHTML = `<div class="stock-detail-empty">${escapeHtml(requestedCode)} 即時個股資料同步失敗。</div>`;
    }
    console.error("Failed to load stock detail:", error);
  }
}

function pickPreferredStockResult(results, preferredMarket = "") {
  const items = Array.isArray(results) ? results : [];
  const market = String(preferredMarket || "").trim().toUpperCase();
  if (!items.length) return null;
  if (!market) return items[0];
  return items.find((stock) => String(stock.market || "").trim().toUpperCase() === market) || items[0];
}

async function loadLiveStockDirectory() {
  if (liveStockDirectoryPromise) return liveStockDirectoryPromise;
  const status = document.getElementById("search-status");
  if (status) status.textContent = "正在同步最新上市櫃股票清單...";
  liveStockDirectoryPromise = fetchWithTimeout(
    "/api/twse/live-stocks",
    { cache: "no-store" },
    60000,
  )
    .then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      localAllStocks = Array.isArray(payload.stocks) ? payload.stocks : [];
      data = {
        ...(data || {}),
        snapshotDate: payload.snapshotDate,
        cachedAt: payload.refreshedAt,
        stockCount: payload.count,
      };
      liveStockDirectoryLoaded = true;
      if (status) {
        status.textContent = `最新股票清單已同步，共 ${payload.count || localAllStocks.length} 檔，資料時間 ${payload.refreshedAt || payload.snapshotDate || "--"}。`;
      }
      return payload;
    })
    .catch((error) => {
      liveStockDirectoryPromise = null;
      if (status) status.textContent = "最新股票清單同步失敗，請稍後再試。";
      throw error;
    });
  return liveStockDirectoryPromise;
}

async function runStockSearch(query, autoSelect = true, preferredMarket = "") {
  const requestId = ++stockSearchRequestId;
  const status = document.getElementById("search-status");
  const keyword = String(query || "").trim();
  if (!keyword) return;
  if (status) status.textContent = `正在同步 live 搜尋 ${keyword}...`;
  try {
    const params = new URLSearchParams({ q: keyword });
    if (preferredMarket) params.set("market", preferredMarket);
    const response = await fetchWithTimeout(
      `/api/twse/live-search?${params.toString()}`,
      { cache: "no-store" },
      45000,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (requestId !== stockSearchRequestId) return;
    const results = Array.isArray(payload.results) ? payload.results : [];
    renderSearchResults(results);
    if (!results.length) {
      if (status) status.textContent = `live 搜尋查無 ${keyword}。`;
      return;
    }
    localAllStocks = results;
    data = {
      ...(data || {}),
      snapshotDate: payload.snapshotDate,
      cachedAt: payload.refreshedAt,
      stockCount: payload.count,
    };
    if (status) status.textContent = `live 搜尋找到 ${results.length} 筆，資料時間 ${payload.refreshedAt || payload.snapshotDate || "--"}。`;
    const selected = autoSelect ? pickPreferredStockResult(results, preferredMarket) : null;
    if (selected) {
      const selectedButton = Array.from(document.querySelectorAll("#search-results [data-code]"))
        .find((button) => (
          String(button.dataset.code) === String(selected.code)
          && String(button.dataset.market || "").toUpperCase() === String(selected.market || "").toUpperCase()
        ));
      if (selectedButton) selectedButton.classList.add("is-active");
      loadStockDetail(selected.code, selected.market, selected);
    }
  } catch (error) {
    if (requestId === stockSearchRequestId) {
      renderSearchResults([]);
      if (status) status.textContent = "live 搜尋同步失敗，請稍後再試。";
    }
    console.error("Failed to run live stock search:", error);
  }
}

function initSearchPage() {
  const form = document.getElementById("stock-search-form");
  const input = document.getElementById("stock-search-input");
  if (!form || !input) return;
  let searchTimer = null;

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = input.value.trim();
    if (!query) {
      setText("search-status", "請輸入搜尋關鍵字。");
      return;
    }
    runStockSearch(query);
  });

  input.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const query = input.value.trim();
    if (!query) {
      stockSearchRequestId += 1;
      renderSearchResults([]);
      setText("search-status", "可輸入部分代號或名稱搜尋。");
      return;
    }
    searchTimer = setTimeout(() => runStockSearch(query, false), 600);
  });

  const params = new URLSearchParams(window.location.search);
  const initialQuery = params.get("q")?.trim();
  const initialMarket = params.get("market")?.trim().toUpperCase() || "";
  if (initialQuery) {
    input.value = initialQuery;
    runStockSearch(initialQuery, true, initialMarket);
  }
}


function renderDerivativePcrHistory(history = []) {
  const values = history
    .map((item) => ({ date: item.tradeDate || "--", value: Number(item.putCallRatio) }))
    .filter((item) => Number.isFinite(item.value));
  if (values.length < 2) {
    return '<p class="stock-detail-empty">PCR 歷史快照仍在累積；目前先顯示最新 PCR，累積兩個交易日後會繪出折線。</p>';
  }
  const width = 640;
  const height = 190;
  const padding = 24;
  const minValue = Math.min(...values.map((item) => item.value), 0.8);
  const maxValue = Math.max(...values.map((item) => item.value), 1.2);
  const range = Math.max(maxValue - minValue, 0.1);
  const point = (item, index) => {
    const x = padding + index / Math.max(values.length - 1, 1) * (width - padding * 2);
    const y = height - padding - (item.value - minValue) / range * (height - padding * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  };
  const line = values.map(point).join(" ");
  return `
    <div class="global-technical-chart">
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="PCR 歷史折線圖">
        <line x1="${padding}" y1="${height / 2}" x2="${width - padding}" y2="${height / 2}" class="chart-grid-line"></line>
        <polyline points="${line}" fill="none" stroke="#f5bd55" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"></polyline>
        ${values.map((item, index) => { const [x, y] = point(item, index).split(","); return `<circle cx="${x}" cy="${y}" r="4" fill="#5aa2ff"><title>${escapeHtml(item.date)} PCR ${item.value.toFixed(2)}</title></circle>`; }).join("")}
      </svg>
    </div>
  `;
}

function renderDerivativeNewsItems(items = [], error = "") {
  if (error) return `<p class="stock-detail-empty">市場新聞資料暫不可用：${escapeHtml(error)}</p>`;
  if (!items.length) return '<p class="stock-detail-empty">目前沒有可顯示的市場新聞。</p>';
  return `<div class="asset-hub-source-stack">${items.map((item) => `<span><b><a class="asset-hub-source-link" href="${safeUrl(item.link || "#")}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title || "--")}</a></b><small>${escapeHtml(item.source || "--")} · ${escapeHtml(item.publishedAt || "--")}</small></span>`).join("")}</div>`;
}

function renderDerivativeBasisCard(result = {}) {
  const data = result.data || {};
  if (result.error && !data.future) {
    return `<article class="panel-card asset-option-sentiment"><p class="panel-kicker">Basis</p><h4>期現貨價差</h4><p class="stock-detail-empty">期現貨價差暫不可用：${escapeHtml(result.error)}</p></article>`;
  }
  const basis = Number(data.basis);
  const basisPct = Number(data.basisPct);
  return `
    <article class="panel-card asset-option-sentiment">
      <p class="panel-kicker">Basis</p>
      <h4>期現貨價差</h4>
      <strong>${Number.isFinite(basis) ? `${basis >= 0 ? "+" : ""}${basis.toFixed(0)}` : "--"}</strong>
      <span>期貨 ${formatAssetOptionNumber(data.futurePrice)} / 現貨 ${formatAssetOptionNumber(data.spotPrice)}</span>
      <small>${Number.isFinite(basisPct) ? `價差率 ${basisPct >= 0 ? "+" : ""}${basisPct.toFixed(2)}%` : escapeHtml(data.message || "期貨或現貨資料暫不可用。")}</small>
    </article>
  `;
}

function renderInstitutionPositionCard(result = {}) {
  const data = result.data || {};
  const rows = Array.isArray(data.rows) ? data.rows : [];
  if (!rows.length) {
    return `<article class="panel-card asset-hub-source-card"><p class="panel-kicker">Institutional position</p><h4>法人多空部位</h4><p>${escapeHtml(data.message || result.error || "資料來源待接入")}</p><small>依文件規範，不以推估部位替代官方資料。</small></article>`;
  }
  const summary = data.summary || {};
  return `
    <article class="panel-card asset-hub-source-card">
      <p class="panel-kicker">Institutional position</p>
      <h4>法人多空部位</h4>
      <div class="asset-hub-source-stack">
        ${rows.map((row) => {
          const net = Number(row.netContracts);
          return `<span><b>${escapeHtml(row.institution || "--")}</b><small>多 ${formatAssetOptionWhole(row.longContracts)} · 空 ${formatAssetOptionWhole(row.shortContracts)} · 淨 ${Number.isFinite(net) ? `${net >= 0 ? "+" : ""}${formatAssetOptionWhole(net)}` : "--"}</small></span>`;
        }).join("")}
      </div>
      <small>${escapeHtml(summary.bias || "")}${data.tradeDate ? ` · 資料日期 ${escapeHtml(data.tradeDate)}` : ""}｜依文件規範，不以推估部位替代官方資料。</small>
    </article>
  `;
}

async function loadDerivativesAssetHubPayloads(options = {}) {
  const includePublicOptionChain = Boolean(options.includePublicOptionChain);
  const [futuresResult, optionsResult] = await Promise.all([
    fetchDerivativesApi("/api/futures?limit=12", 120000),
    fetchDerivativesApi("/api/options?limit=12", 120000),
  ]);
  const futuresPayload = futuresResult.data || createAssetHubPlaceholder("futures", "期貨", "Futures");
  const optionsPayload = optionsResult.data || createAssetHubPlaceholder("options", "選擇權", "Options");
  if (includePublicOptionChain && !optionsPayload.optionChain) {
    try {
      const response = await fetchWithTimeout("/api/us-market/options-chain/SPY", { cache: "no-store" }, 16000);
      if (response.ok) optionsPayload.optionChain = await response.json();
    } catch (error) {
      console.warn("Failed to load SPY options chain for derivatives payload:", error);
    }
  }
  return {
    futuresPayload,
    optionsPayload,
    payloads: [futuresPayload, optionsPayload],
    errors: {
      futures: futuresResult.error,
      options: optionsResult.error,
    },
  };
}

function renderDerivativePayloadSnapshot(payload, title, href) {
  const summary = payload?.summary || {};
  const validation = payload?.validation || {};
  return `
    <article class="panel-card asset-hub-summary-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">${escapeHtml(payload?.kicker || payload?.category || "Derivatives")}</p>
          <h3>${escapeHtml(title || payload?.title || "期權資料")}</h3>
        </div>
        <a class="global-refresh" href="${safeUrl(href || "derivatives-assets.html")}">開啟來源頁</a>
      </div>
      <div class="asset-hub-stat-grid">
        <span><b>${summary.count ?? 0}</b><small>有效資料</small></span>
        <span><b>${summary.advancers ?? 0} / ${summary.decliners ?? 0}</b><small>上漲 / 下跌</small></span>
        <span><b>${escapeHtml(summary.avgPct || "--")}</b><small>平均漲跌幅</small></span>
        <span><b>${escapeHtml(summary.strongest || "--")}</b><small>最強標的</small></span>
      </div>
      ${renderAssetHubRegionChips(payload)}
      <p class="asset-hub-insight">驗證 ${Number(validation.verifiedCount) || 0} 筆、限制 ${Number(validation.limitedCount) || 0} 筆、失敗 ${Number(validation.failedCount) || 0} 筆；主來源：${escapeHtml(validation.primary || payload?.source || "--")}。</p>
    </article>
  `;
}

function renderDerivativesAssetSnapshotGrid(futuresPayload, optionsPayload) {
  return `
    <section class="section">
      <div class="asset-hub-layout asset-hub-options-layout">
        ${renderDerivativePayloadSnapshot(futuresPayload, "期貨市場", "futures.html")}
        ${renderDerivativePayloadSnapshot(optionsPayload, "市場選擇權鏈", "options.html")}
      </div>
    </section>
  `;
}

async function initDerivativesAnalyticsPage() {
  const root = document.getElementById("derivatives-analytics-root");
  if (!root) return;
  root.innerHTML = '<section class="subpage-hero"><p class="eyebrow">Derivatives analytics</p><h1>期權分析工具載入中</h1><p class="hero-text">正在取得市場選擇權鏈、PCR、OI、最大痛點、AI 分析與市場新聞。</p></section>';
  const [assetPayloads, chainResult, pcrResult, institutionResult, basisResult, optionResult, futureResult, newsResult] = await Promise.all([
    loadDerivativesAssetHubPayloads({ includePublicOptionChain: true }),
    fetchDerivativesApi("/api/options/chain?underlying=TXO&source=auto", 45000),
    fetchDerivativesApi("/api/pcr?underlying=TXO&source=auto", 30000),
    fetchDerivativesApi("/api/institution?product=TX", 12000),
    fetchDerivativesApi("/api/basis?future=TX&spot=TAIEX", 30000),
    fetchDerivativesApi("/api/ai-analysis?target=TXO&source=auto", 45000),
    fetchDerivativesApi("/api/ai-analysis?target=TX", 30000),
    fetchDerivativesApi("/api/news?category=derivatives&symbol=%5EVIX&limit=6", 20000),
  ]);
  const futuresPayload = assetPayloads.futuresPayload;
  const optionsPayload = assetPayloads.optionsPayload;
  const chain = chainResult.data || {};
  const summary = chain.summary || {};
  const analysis = chain.analysis || {};
  const pcr = pcrResult.data || {};
  const maxPain = summary.maxPain;
  const spot = Number(chain.spot?.value);
  const gap = Number.isFinite(spot) && Number.isFinite(Number(maxPain)) ? spot - Number(maxPain) : null;
  const txoChain = {
    ...(optionsPayload.taiwanOptionChain || {}),
    ...chain,
    analysis: optionResult.data || chain.analysis || optionsPayload.taiwanOptionChain?.analysis || {},
  };
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">Derivatives analytics</p>
      <h1>期權分析與 AI 中心</h1>
      <p class="hero-text">整合 TXO 的 PCR、未平倉分布、最大痛點、期現貨價差、法人籌碼與 AI 風險情境；原 derivatives-ai.html 內容已合併到此頁。</p>
    </section>
    ${renderAssetHubSchemaPanel([futuresPayload, optionsPayload])}
    ${renderDerivativesAssetSnapshotGrid(futuresPayload, optionsPayload)}
    <section class="section">
      <div class="asset-hub-layout asset-hub-options-layout">
        <article class="panel-card asset-option-chain-card"><div class="asset-hub-group-heading"><div><p class="panel-kicker">Put / Call Ratio</p><h4>PCR 與未平倉結構</h4></div><span>${escapeHtml(chain.tradeDate || "--")}</span></div><div class="asset-option-chain-stats"><span><b>${Number.isFinite(Number(summary.putCallRatio)) ? Number(summary.putCallRatio).toFixed(2) : "--"}</b><small>OI Put / Call</small></span><span><b>${Number.isFinite(Number(summary.volumePutCallRatio)) ? Number(summary.volumePutCallRatio).toFixed(2) : "--"}</b><small>量 Put / Call</small></span><span><b>${formatAssetOptionWhole(summary.callOpenInterest)}</b><small>Call OI</small></span><span><b>${formatAssetOptionWhole(summary.putOpenInterest)}</b><small>Put OI</small></span></div>${renderDerivativePcrHistory(pcr.history || [])}</article>
        <article class="panel-card asset-option-sentiment"><p class="panel-kicker">Max Pain</p><h4>最大痛點</h4><strong>${formatAssetOptionWhole(maxPain)}</strong><span>${Number.isFinite(gap) ? `現貨與最大痛點差 ${gap >= 0 ? "+" : ""}${gap.toFixed(0)}` : "現貨資料暫不可用"}</span><small>最大痛點為 OI 加權試算，不是價格預測；現貨取自資料來源可用的台灣加權指數快照。</small></article>
        ${renderDerivativeBasisCard(basisResult)}
        <article class="panel-card tw-option-chain-card"><div class="asset-hub-group-heading"><div><p class="panel-kicker">Open interest</p><h4>未平倉分布</h4></div><span>${escapeHtml(chain.selectedExpiry || "--")}</span></div>${chainResult.error ? `<p class="stock-detail-empty">選擇權鏈資料暫不可用：${escapeHtml(chainResult.error)}</p>` : renderTaiwanOptionDistribution(chain)}</article>
        ${renderInstitutionPositionCard(institutionResult)}
      </div>
    </section>
    <section class="section">
      <div class="asset-hub-layout asset-hub-futures-layout">
        ${renderAssetHubTaiwanFuturesCard(futuresPayload)}
        ${renderAssetHubPublicOptionChainCard(optionsPayload.optionChain || {})}
      </div>
    </section>
    <section class="section" id="derivatives-ai-section">
      <article class="panel-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">Merged AI analysis</p>
            <h3>期權 AI 分析中心</h3>
            <p class="chart-subtitle">原 derivatives-ai.html 已合併在此區，以公開行情、未平倉、PCR、最大痛點與期貨資料輸出多空、支撐壓力、風險與情境。</p>
          </div>
          <span class="chip chip-cyan">Analytics + AI</span>
        </div>
      </article>
    </section>
    ${renderDerivativeNameMappingCard("ai")}
    ${renderDerivativeAiArchitectureCard(futuresPayload, optionsPayload)}
    <section class="section">
      <div class="asset-hub-layout asset-hub-options-layout">
        <div id="derivative-ai-options">
          ${renderTaiwanOptionAnalysis(txoChain)}
          ${optionResult.error ? `<p class="stock-detail-empty">選擇權 AI 分析資料暫不可用：${escapeHtml(optionResult.error)}</p>` : ""}
        </div>
        ${renderDerivativeAiReport("期貨 AI 風險情境", futureResult.data || {}, futureResult.error, "derivative-ai-futures")}
      </div>
    </section>
    <section class="section"><article class="panel-card"><div class="card-title-row"><div><p class="panel-kicker">Market news</p><h3>期權市場新聞</h3></div><span class="chip chip-blue">公開來源</span></div>${renderDerivativeNewsItems(newsResult.data?.items || [], newsResult.error)}</article></section>
    <section class="section"><article class="panel-card"><p class="stock-theory-note">${escapeHtml(analysis.disclaimer || "分析工具僅供研究參考，不保證獲利。")}</p></article></section>
  `;
}

function renderDerivativeAiReport(title, analysis = {}, error = "", id = "") {
  const idAttr = id ? ` id="${escapeHtml(id)}"` : "";
  if (error) return `<article class="panel-card"${idAttr}><h3>${escapeHtml(title)}</h3><p class="stock-detail-empty">AI 分析資料暫不可用：${escapeHtml(error)}</p></article>`;
  const scenarios = Array.isArray(analysis.scenarios) ? analysis.scenarios : [];
  const crossValidation = Array.isArray(analysis.crossValidation) ? analysis.crossValidation : [];
  return `
    <article class="panel-card tw-option-ai-card"${idAttr}>
      <div class="asset-hub-group-heading"><div><p class="panel-kicker">AI analysis</p><h3>${escapeHtml(title)}</h3></div><span>風險 ${escapeHtml(analysis.riskLevel || "--")}</span></div>
      <div class="tw-option-ai-main"><strong>${escapeHtml(analysis.bias || "資料不足")}</strong><p>${escapeHtml((analysis.reasons || [])[0] || "尚無足夠資料說明方向。")}</p></div>
      <div class="asset-option-chain-stats"><span><b>${formatAssetOptionNumber(analysis.supportLevel)}</b><small>支撐</small></span><span><b>${formatAssetOptionNumber(analysis.resistanceLevel)}</b><small>壓力</small></span><span><b>${escapeHtml(analysis.riskLevel || "--")}</b><small>風險等級</small></span><span><b>${Number.isFinite(Number(analysis.marketScore)) ? Number(analysis.marketScore).toFixed(0) : "--"}</b><small>市場分數</small></span><span><b>${Number.isFinite(Number(analysis.riskScore)) ? Number(analysis.riskScore).toFixed(0) : "--"}</b><small>風險分數</small></span><span><b>${Number.isFinite(Number(analysis.confidenceScore)) ? Number(analysis.confidenceScore).toFixed(0) : "--"}</b><small>AI 信心</small></span></div>
      <ul class="tw-option-ai-reasons">${(analysis.reasons || []).slice(1, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>資料不足時保留欄位，不以假訊號替代。</li>"}</ul>
      <div class="asset-hub-source-stack">${crossValidation.map((item) => `<span><b>${escapeHtml(item.name || "--")}</b><small>${escapeHtml(item.status || "--")} · ${escapeHtml(item.signal || "--")}</small></span>`).join("") || "<span><b>Cross validation</b><small>等待更多公開資料交叉驗證。</small></span>"}</div>
      <div class="tw-option-scenarios">${scenarios.map((item) => `<section><b>${escapeHtml(item.name || "--")}</b><small>${escapeHtml(item.condition || "")}</small><p>${escapeHtml(item.view || "")}</p></section>`).join("")}</div>
      <p class="stock-theory-note"><b>策略建議：</b>${escapeHtml(analysis.strategySuggestion || "資料不足時不輸出方向性策略。")}</p>
      <p class="stock-theory-note">${escapeHtml(analysis.disclaimer || "AI 分析僅供研究參考，不保證獲利。")}</p>
    </article>
  `;
}

function renderDerivativeAiArchitectureCard(futuresPayload, optionsPayload) {
  const futuresSource = futuresPayload?.sourceInfo || {};
  const optionsSource = optionsPayload?.sourceInfo || {};
  return `
    <section class="section">
      <article class="panel-card asset-hub-schema-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">AI analysis architecture</p>
            <h3>AI 分析資料架構</h3>
            <p class="chart-subtitle">依 derivatives-assets.html 的期貨與選擇權資料區塊輸入，不另外創造未命名資料。</p>
          </div>
          <span class="chip chip-gold">一名稱對應</span>
        </div>
        <div class="asset-hub-schema-grid">
          <section>
            <h4>台灣選擇權 AI 盤勢摘要</h4>
            <div class="asset-hub-table-tags">
              ${["市場選擇權鏈", "PCR 與未平倉結構", "最大痛點", "未平倉分布", "CBOE VIX 市場情緒"].map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
            </div>
            <p>輸出方向、理由、支撐壓力、風險等級與多空情境。</p>
          </section>
          <section>
            <h4>期貨 AI 風險情境</h4>
            <div class="asset-hub-table-tags">
              ${["期貨市場", "國內期貨未平倉資料", "期貨地區市場", "期貨線上資料明細"].map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
            </div>
            <p>輸出短線偏多、震盪或偏空情境，並搭配支撐、壓力與槓桿風險提醒。</p>
          </section>
          <section>
            <h4>資料來源對應</h4>
            <div class="asset-hub-source-stack">
              <span><b>期貨</b><small>${escapeHtml(futuresSource.primary || futuresPayload?.source || "Yahoo Finance / TAIFEX")}</small></span>
              <span><b>選擇權</b><small>${escapeHtml(optionsSource.primary || optionsPayload?.source || "TAIFEX / CBOE / Yahoo Finance")}</small></span>
            </div>
            <p>沒有官方或公開來源的欄位不以推估值替代。</p>
          </section>
        </div>
      </article>
    </section>
  `;
}

async function initDerivativesAiPage() {
  window.location.replace("derivatives-analytics.html#derivatives-ai-section");
}

function twEtfCompactNumber(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  if (Math.abs(parsed) >= 100000000) return `${(parsed / 100000000).toFixed(1)}億`;
  if (Math.abs(parsed) >= 10000) return `${(parsed / 10000).toFixed(1)}萬`;
  return parsed.toLocaleString("zh-TW");
}

function twEtfSignedPct(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  return `${parsed > 0 ? "+" : ""}${parsed.toFixed(2)}%`;
}

function twEtfItemLink(item) {
  const params = new URLSearchParams();
  params.set("q", item.code || "");
  if (item.market) params.set("market", item.market);
  return `tw-stock-search.html?${params.toString()}`;
}

function renderTwEtfSummary(payload) {
  const summary = payload?.summary || {};
  return `
    <section class="section">
      <div class="headline-metrics tw-etf-summary-grid">
        <div><span>ETF 檔數</span><strong>${Number(payload?.totalCount || 0).toLocaleString("zh-TW")}</strong><small>上市 ${summary.twseCount || 0} / 上櫃 ${summary.tpexCount || 0}</small></div>
        <div><span>高股息</span><strong>${summary.highDividendCount || 0}</strong><small>收益與配息觀察池</small></div>
        <div><span>債券 ETF</span><strong>${summary.bondCount || 0}</strong><small>利率與信用風險</small></div>
        <div><span>平均漲跌</span><strong class="${toneClass((summary.averageReturnPct || 0) > 0 ? "up" : (summary.averageReturnPct || 0) < 0 ? "down" : "flat")}">${twEtfSignedPct(summary.averageReturnPct)}</strong><small>目前清單樣本</small></div>
        <div><span>成交量</span><strong>${twEtfCompactNumber(summary.totalVolume)}</strong><small>全 ETF 合計</small></div>
        <div><span>成交值</span><strong>${twEtfCompactNumber(summary.totalTurnover)}</strong><small>流動性觀察</small></div>
      </div>
    </section>
  `;
}

function renderTwEtfRankingList(title, items = [], metric = "pct") {
  return `
    <article class="panel-card">
      <div class="card-title-row"><h3>${escapeHtml(title)}</h3><span class="chip chip-blue">${items.length} 檔</span></div>
      <div class="mini-list">
        ${items.map((item) => `
          <a class="mini-row" href="${safeUrl(twEtfItemLink(item))}">
            <span><b>${escapeHtml(item.code)}</b> ${escapeHtml(item.name)}</span>
            <strong class="${toneClass(item.tone)}">${metric === "volume" ? twEtfCompactNumber(item.volumeValue) : metric === "risk" ? escapeHtml(item.riskLevel) : escapeHtml(item.pct || "--")}</strong>
          </a>
        `).join("") || '<p class="stock-detail-empty">暫無資料。</p>'}
      </div>
    </article>
  `;
}

function renderTwEtfCompareTable(items = []) {
  return `
    <section class="section">
      <article class="panel-card">
        <div class="card-title-row">
          <div><p class="panel-kicker">ETF comparison</p><h3>熱門ETF</h3></div>
          <span class="chip chip-gold">0050 / 006208 / 0056 / 00878 / 00919 / 00929</span>
        </div>
        <div class="table-wrap">
          <table class="global-market-table">
            <thead><tr><th>代號</th><th>名稱</th><th>分類</th><th>收盤</th><th>漲跌幅</th><th>成交量</th><th>風險</th></tr></thead>
            <tbody>
              ${items.map((item) => `
                <tr>
                  <td><a class="global-market-link" href="${safeUrl(twEtfItemLink(item))}">${escapeHtml(item.code)}</a></td>
                  <td>${escapeHtml(item.name)}</td>
                  <td><span class="chip chip-blue">${escapeHtml(item.categoryLabel)}</span></td>
                  <td>${escapeHtml(item.close)}</td>
                  <td class="${toneClass(item.tone)}">${escapeHtml(item.pct || "--")}</td>
                  <td>${twEtfCompactNumber(item.volumeValue)}</td>
                  <td>${escapeHtml(item.riskLevel)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  `;
}

function renderTwEtfFilterForm(payload, categories = []) {
  return `
    <form id="tw-etf-filter-form" class="search-form tw-etf-filter-form">
      <input id="tw-etf-query" class="tw-etf-filter-input" type="search" placeholder="搜尋 0050、00878、高股息、債券、半導體..." value="${escapeHtml(payload?.query || "")}">
      <select id="tw-etf-category">
        ${categories.map((item) => `<option value="${escapeHtml(item.key)}"${item.key === payload?.category ? " selected" : ""}>${escapeHtml(item.label)} (${item.count || 0})</option>`).join("")}
      </select>
      <select id="tw-etf-sort">
        ${[
          ["return_desc", "漲幅高到低"],
          ["return_asc", "跌幅高到低"],
          ["volume_desc", "成交量高到低"],
          ["turnover_desc", "成交值高到低"],
          ["volatility_desc", "波動高到低"],
          ["risk_desc", "風險高到低"],
          ["code", "代號排序"],
        ].map(([value, label]) => `<option value="${value}"${value === payload?.sort ? " selected" : ""}>${label}</option>`).join("")}
      </select>
      <button class="btn" type="submit">篩選</button>
    </form>
  `;
}

function getTwEtfPage(items = []) {
  const pageSize = Number(twEtfState.pageSize) || TW_ETF_DEFAULT_PAGE_SIZE;
  const totalItems = items.length;
  const totalPages = Math.max(Math.ceil(totalItems / pageSize), 1);
  twEtfState.page = Math.max(1, Math.min(Number(twEtfState.page) || 1, totalPages));
  const start = (twEtfState.page - 1) * pageSize;
  return {
    pageItems: items.slice(start, start + pageSize),
    pageSize,
    totalItems,
    totalPages,
    start,
    end: Math.min(start + pageSize, totalItems),
  };
}

function renderTwEtfPager(totalItems = 0) {
  const pageSize = Number(twEtfState.pageSize) || TW_ETF_DEFAULT_PAGE_SIZE;
  const totalPages = Math.max(Math.ceil(totalItems / pageSize), 1);
  twEtfState.page = Math.max(1, Math.min(Number(twEtfState.page) || 1, totalPages));
  const start = totalItems ? (twEtfState.page - 1) * pageSize + 1 : 0;
  const end = Math.min(twEtfState.page * pageSize, totalItems);
  return `
    <section class="section tw-etf-pager-section">
      <div class="us-directory-pager tw-etf-pager">
        <span>顯示 <b>${Number(start).toLocaleString("zh-TW")}</b> - <b>${Number(end).toLocaleString("zh-TW")}</b> / ${Number(totalItems).toLocaleString("zh-TW")} 檔</span>
        <label>
          <span>每頁</span>
          <select id="tw-etf-page-size">
            ${TW_ETF_PAGE_SIZE_OPTIONS.map((size) => `<option value="${size}"${size === pageSize ? " selected" : ""}>${size}</option>`).join("")}
          </select>
        </label>
        <button type="button" data-tw-etf-page="first" ${twEtfState.page <= 1 ? "disabled" : ""}>第一頁</button>
        <button type="button" data-tw-etf-page="prev" ${twEtfState.page <= 1 ? "disabled" : ""}>上一頁</button>
        <span>第 <b>${twEtfState.page}</b> / ${totalPages} 頁</span>
        <button type="button" data-tw-etf-page="next" ${twEtfState.page >= totalPages ? "disabled" : ""}>下一頁</button>
        <button type="button" data-tw-etf-page="last" ${twEtfState.page >= totalPages ? "disabled" : ""}>最後頁</button>
      </div>
    </section>
  `;
}

function setTwEtfPage(action) {
  const items = twEtfPayload?.items || [];
  const pageSize = Number(twEtfState.pageSize) || TW_ETF_DEFAULT_PAGE_SIZE;
  const totalPages = Math.max(Math.ceil(items.length / pageSize), 1);
  const currentPage = Math.max(1, Math.min(Number(twEtfState.page) || 1, totalPages));
  const nextPage = action === "first"
    ? 1
    : action === "prev"
      ? currentPage - 1
      : action === "next"
        ? currentPage + 1
        : action === "last"
          ? totalPages
          : Number(action) || currentPage;
  twEtfState.page = Math.max(1, Math.min(nextPage, totalPages));
  renderTwEtfPage(twEtfPayload);
  setTimeout(() => {
    document.getElementById("tw-etf-table-section")?.scrollIntoView({ block: "start", behavior: "smooth" });
  }, 0);
}

function renderTwEtfTable(items = [], payload = {}) {
  const { pageItems, totalItems, start, end } = getTwEtfPage(items);
  const categories = payload?.categories || [];
  return `
    <section class="section" id="tw-etf-table-section">
      <article class="panel-card tw-etf-list-card">
        <div class="card-title-row"><h3>ETF 清單</h3><span class="chip chip-gold">${totalItems ? `${Number(start + 1).toLocaleString("zh-TW")}-${Number(end).toLocaleString("zh-TW")} / ${Number(totalItems).toLocaleString("zh-TW")}` : "0"} 檔</span></div>
        <div class="tw-etf-list-toolbar">
          ${renderTwEtfFilterForm(payload, categories)}
        </div>
        <div class="table-wrap">
          <table class="global-market-table">
            <thead><tr><th>代號</th><th>名稱</th><th>分類</th><th>收盤</th><th>漲跌幅</th><th>成交量</th><th>波動</th><th>詳情</th></tr></thead>
            <tbody>
              ${pageItems.map((item) => `
                <tr>
                  <td><a class="global-market-link" href="${safeUrl(twEtfItemLink(item))}">${escapeHtml(item.code)}</a></td>
                  <td>${escapeHtml(item.name)}<br><small>${escapeHtml(item.marketLabel || item.market || "")}</small></td>
                  <td><span class="chip chip-blue">${escapeHtml(item.categoryLabel)}</span></td>
                  <td>${escapeHtml(item.close)}</td>
                  <td class="${toneClass(item.tone)}">${escapeHtml(item.pct || "--")}</td>
                  <td>${twEtfCompactNumber(item.volumeValue)}</td>
                  <td>${item.volatilityPct === null || item.volatilityPct === undefined ? "--" : `${Number(item.volatilityPct).toFixed(2)}%`}</td>
                  <td><button class="btn btn-secondary tw-etf-detail-button" type="button" data-tw-etf-detail="${escapeHtml(item.code)}" data-market="${escapeHtml(item.market || "")}" title="查看成分、配息與風險" aria-label="查看 ${escapeHtml(item.code)} ETF 詳情">查看</button></td>
                </tr>
              `).join("") || '<tr><td colspan="8">沒有符合條件的 ETF。</td></tr>'}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  `;
}

function twEtfHasValue(value) {
  const text = String(value ?? "").trim();
  return Boolean(text) && !["--", "-", "N/A", "NA", "--%"].includes(text);
}


function renderTwEtfAnalysisBullets(detail, fallbackItem, components, dividend) {
  const holdings = Array.isArray(components.holdings) ? components.holdings : [];
  const latest = dividend.latest || {};
  const totals = dividend.totals || {};
  const topHolding = holdings[0] || {};
  const topWeight = Number(topHolding.weight);
  const volatility = fallbackItem.volatilityPct ?? (detail.technicalAnalysis || {}).volatilityPct;
  const bullets = [];
  bullets.push(`${fallbackItem.categoryLabel || "ETF"}：${fallbackItem.dividendProfile || "以追蹤標的、流動性與費用結構作為主要觀察重點。"}`);
  if (holdings.length) {
    bullets.push(`成分配置：${topHolding.name || "最大配置"}${Number.isFinite(topWeight) ? ` 約 ${twEtfWeightText(topWeight)}` : ""}，用來判斷集中度與主要風格曝險。`);
  } else {
    bullets.push("成分配置：目前未取得完整持股明細，先以 ETF 名稱與追蹤主題做配置判讀，仍以投信公告為準。");
  }
  if (twEtfHasValue(latest.cashDividend)) {
    bullets.push(`配息觀察：近次現金股利 ${latest.cashDividend} 元，除息日 ${latest.exDate || "--"}，平均殖利率 ${totals.averageYield || "--"}%。`);
  } else {
    bullets.push("配息觀察：尚未取得可用配息紀錄，收益型 ETF 需再搭配除息日與填息天數檢查。");
  }
  bullets.push(`交易風險：成交量 ${twEtfCompactNumber(fallbackItem.volumeValue)}，波動 ${twEtfHasValue(volatility) ? `${volatility}%` : "--"}，目前風險分級為 ${fallbackItem.riskLevel || "--"}。`);
  return bullets;
}

function renderTwEtfComponentsCard(components = {}) {
  const holdings = Array.isArray(components.holdings) ? components.holdings : [];
  return `
    <article class="panel-card etf-components-card tw-etf-components-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">ETF Holdings</p>
          <h3>${escapeHtml(components.title || "ETF 成分股比例")}</h3>
          <p class="chart-subtitle">${escapeHtml(components.summary || "ETF 成分股比例沿用個股搜尋詳情資料；實際持股仍以投信公告為準。")}</p>
        </div>
        <span class="chip chip-blue">${holdings.length ? `${holdings.length} 項配置` : "資料待補"}</span>
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
              <b>${twEtfWeightText(weight)}</b>
            </div>
          `;
        }).join("") || '<p class="stock-detail-empty">此 ETF 尚未取得成分股比例資料。</p>'}
      </div>
      <p class="stock-theory-note">${escapeHtml(components.sourceNote || "成分股比例請以發行投信每日公告為準。")} ${components.sourceLink ? `<a href="${safeUrl(components.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
    </article>
  `;
}

function renderTwEtfDividendCard(dividend = {}) {
  const latest = dividend.latest || {};
  const totals = dividend.totals || {};
  const recent = Array.isArray(dividend.recent) ? dividend.recent : [];
  return `
    <article class="panel-card etf-dividend-card tw-etf-dividend-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">ETF Dividend</p>
          <h3>${escapeHtml(dividend.title || "ETF 股利資訊")}</h3>
          <p class="chart-subtitle">${escapeHtml(dividend.summary || "ETF 股利資訊沿用個股搜尋詳情資料，呈現最新配息與近次除息紀錄。")}</p>
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
        ${recent.slice(0, 6).map((item) => `
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
        `).join("") || '<p class="stock-detail-empty">尚未取得 ETF 配息紀錄。</p>'}
      </div>
      <p class="stock-theory-note">${escapeHtml(dividend.sourceNote || "ETF 股利資料請以發行投信公告為準。")} ${dividend.sourceLink ? `<a href="${safeUrl(dividend.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
    </article>
  `;
}

function renderTwEtfDetail(detail, fallbackItem = {}) {
  const root = document.getElementById("tw-etf-detail");
  if (!root) return;
  if (!detail) {
    root.innerHTML = '<article class="panel-card"><p class="stock-detail-empty">點選 ETF 後，這裡會顯示配息、成分股與風險摘要。</p></article>';
    return;
  }
  const components = detail.etfComponents || {};
  const dividend = detail.etfDividendInfo || {};
  const latest = dividend.latest || {};
  const bullets = renderTwEtfAnalysisBullets(detail, fallbackItem, components, dividend);
  root.innerHTML = `
    <div class="tw-etf-detail-layout">
      <article class="panel-card tw-etf-analysis-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">ETF Analysis</p>
            <h3>${escapeHtml(detail.code || fallbackItem.code || "")} ${escapeHtml(detail.name || fallbackItem.name || "")}</h3>
            <p class="chart-subtitle">整合行情、分類、風險、ETF 成分股比例與 ETF 股利資訊，作為篩選後的分析摘要。</p>
          </div>
          <span class="chip chip-gold">${escapeHtml(fallbackItem.categoryLabel || "ETF")}</span>
        </div>
        <div class="headline-metrics tw-etf-detail-metrics">
          <div><span>收盤</span><strong>${escapeHtml(detail.close || fallbackItem.close || "--")}</strong><small class="${toneClass(detail.tone || fallbackItem.tone)}">${escapeHtml(detail.pct || fallbackItem.pct || "--")}</small></div>
          <div><span>風險分級</span><strong>${escapeHtml(fallbackItem.riskLevel || "--")}</strong><small>分數 ${escapeHtml(fallbackItem.riskScore ?? "--")}</small></div>
          <div><span>成交量</span><strong>${twEtfCompactNumber(fallbackItem.volumeValue)}</strong><small>流動性觀察</small></div>
          <div><span>近次配息</span><strong>${escapeHtml(latest.cashDividend || "--")} 元</strong><small>除息 ${escapeHtml(latest.exDate || "--")}</small></div>
        </div>
        <div class="tw-etf-analysis-notes">
          ${bullets.map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
        </div>
      </article>
      <div class="tw-etf-detail-grid">
        ${renderTwEtfComponentsCard(components)}
        ${renderTwEtfDividendCard(dividend)}
      </div>
    </div>
  `;
}

function bindTwEtfEvents() {
  const filterRoot = document.querySelector(".tw-etf-list-toolbar") || document;
  const form = filterRoot.querySelector("#tw-etf-filter-form");
  const query = filterRoot.querySelector("#tw-etf-query");
  const category = filterRoot.querySelector("#tw-etf-category");
  const sort = filterRoot.querySelector("#tw-etf-sort");
  const pageSize = document.getElementById("tw-etf-page-size");
  const run = () => {
    twEtfState.page = 1;
    loadTwEtfPage({
      q: query?.value || "",
      category: category?.value || "all",
      sort: sort?.value || "return_desc",
      keepListInView: true,
    });
  };
  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    run();
  });
  category?.addEventListener("change", run);
  sort?.addEventListener("change", run);
  pageSize?.addEventListener("change", () => {
    twEtfState.page = 1;
    twEtfState.pageSize = Number(pageSize.value) || TW_ETF_DEFAULT_PAGE_SIZE;
    renderTwEtfPage(twEtfPayload);
  });
  document.querySelectorAll("[data-tw-etf-page]").forEach((button) => {
    button.addEventListener("click", () => setTwEtfPage(button.dataset.twEtfPage || "1"));
  });
  document.querySelectorAll("[data-tw-etf-detail]").forEach((button) => {
    button.addEventListener("click", () => {
      const code = button.dataset.twEtfDetail || "";
      const market = button.dataset.market || "";
      const item = (twEtfPayload?.items || []).find((entry) => entry.code === code)
        || (twEtfPayload?.compare || []).find((entry) => entry.code === code)
        || {};
      loadTwEtfDetail(code, market, item);
      setTimeout(() => {
        document.getElementById("tw-etf-detail")?.scrollIntoView({ block: "start", behavior: "smooth" });
      }, 0);
    });
  });
}

function renderTwEtfPage(payload) {
  const root = document.getElementById("tw-etf-root");
  if (!root) return;
  const categories = payload?.categories || [];
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">Taiwan ETF center</p>
      <h1>台股 ETF 總覽</h1>
      <p class="hero-text">整合台股 ETF 搜尋、分類、排行榜、比較、配息與風險摘要，適合高股息、市值型、科技、債券與槓桿反向 ETF 快速篩選。</p>
    </section>
    <section class="section"><div class="tri-grid">
      ${renderTwEtfRankingList("漲幅排行", payload?.rankings?.topReturn || [])}
      ${renderTwEtfRankingList("成交量排行", payload?.rankings?.topVolume || [], "volume")}
      ${renderTwEtfRankingList("高股息觀察", payload?.rankings?.highDividend || [])}
    </div></section>
    <section class="section">
      <article class="panel-card tw-etf-filter-card">
        <form id="tw-etf-filter-form" class="search-form tw-etf-filter-form">
          <input id="tw-etf-query" class="tw-etf-filter-input" type="search" placeholder="搜尋 0050、00878、高股息、債券、半導體..." value="${escapeHtml(payload?.query || "")}">
          <select id="tw-etf-category">
            ${categories.map((item) => `<option value="${escapeHtml(item.key)}"${item.key === payload?.category ? " selected" : ""}>${escapeHtml(item.label)} (${item.count || 0})</option>`).join("")}
          </select>
          <select id="tw-etf-sort">
            ${[
              ["return_desc", "漲幅高到低"],
              ["return_asc", "跌幅高到低"],
              ["volume_desc", "成交量"],
              ["turnover_desc", "成交值"],
              ["volatility_desc", "波動度"],
              ["risk_desc", "風險分數"],
              ["code", "代號"],
            ].map(([value, label]) => `<option value="${value}"${value === payload?.sort ? " selected" : ""}>${label}</option>`).join("")}
          </select>
          <button class="btn" type="submit">篩選</button>
        </form>
      </article>
    </section>
    ${renderTwEtfCompareTable(payload?.compare || [])}
    ${renderTwEtfTable(payload?.items || [], payload)}
    ${renderTwEtfPager(payload?.items?.length || 0)}
    <section class="section" id="tw-etf-detail"></section>
  `;
  root.querySelector(".tw-etf-filter-card")?.closest(".section")?.remove();
  renderTwEtfDetail(null);
  bindTwEtfEvents();
}

async function loadTwEtfDetail(code, market, fallbackItem = {}) {
  const root = document.getElementById("tw-etf-detail");
  if (root) root.innerHTML = '<article class="panel-card"><p class="stock-detail-empty">正在載入 ETF 配息與成分股資料...</p></article>';
  twEtfSelectedCode = code;
  try {
    const params = new URLSearchParams();
    if (market) params.set("market", market);
    const response = await fetchWithTimeout(`/api/twse/stock/${encodeURIComponent(code)}?${params.toString()}`, { cache: "no-store" }, 60000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const detail = await response.json();
    if (twEtfSelectedCode === code) renderTwEtfDetail(detail, fallbackItem);
  } catch (error) {
    if (root) root.innerHTML = `<article class="panel-card"><p class="stock-detail-empty">ETF 詳情暫時無法載入：${escapeHtml(error.message || String(error))}</p></article>`;
  }
}

async function loadTwEtfPage(options = {}) {
  const root = document.getElementById("tw-etf-root");
  if (!root) return;
  const keepListInView = options.keepListInView === true;
  const listSection = document.getElementById("tw-etf-table-section");
  const listViewportTop = listSection?.getBoundingClientRect().top ?? null;
  if (Object.prototype.hasOwnProperty.call(options, "q")) twEtfState.query = options.q || "";
  if (Object.prototype.hasOwnProperty.call(options, "category")) twEtfState.category = options.category || "all";
  if (Object.prototype.hasOwnProperty.call(options, "sort")) twEtfState.sort = options.sort || "return_desc";
  const params = new URLSearchParams();
  if (twEtfState.query) params.set("q", twEtfState.query);
  params.set("category", twEtfState.category || "all");
  params.set("sort", twEtfState.sort || "return_desc");
  params.set("limit", "all");
  if (keepListInView) {
    document.querySelector(".tw-etf-list-card")?.classList.add("is-loading");
    const submitButton = document.querySelector(".tw-etf-list-toolbar .btn");
    if (submitButton) submitButton.disabled = true;
  } else {
  root.innerHTML = '<section class="section"><article class="panel-card"><p class="stock-detail-empty">正在載入台股 ETF 資料...</p></article></section>';
  }
  try {
    const response = await fetchWithTimeout(`/api/twse/etfs?${params.toString()}`, { cache: "no-store" }, 30000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    twEtfPayload = await response.json();
    renderTwEtfPage(twEtfPayload);
    if (keepListInView && listViewportTop !== null) {
      requestAnimationFrame(() => {
        const nextSection = document.getElementById("tw-etf-table-section");
        if (!nextSection) return;
        window.scrollBy({
          top: nextSection.getBoundingClientRect().top - listViewportTop,
          left: 0,
          behavior: "auto",
        });
      });
    }
  } catch (error) {
    if (keepListInView) {
      document.querySelector(".tw-etf-list-card")?.classList.remove("is-loading");
      const submitButton = document.querySelector(".tw-etf-list-toolbar .btn");
      if (submitButton) submitButton.disabled = false;
      document.querySelector(".tw-etf-filter-error")?.remove();
      document.querySelector(".tw-etf-list-toolbar")?.insertAdjacentHTML(
        "beforeend",
        `<p class="stock-detail-empty tw-etf-filter-error">ETF 篩選暫時無法完成：${escapeHtml(error.message || String(error))}</p>`,
      );
    } else {
    root.innerHTML = `<section class="section"><article class="panel-card"><p class="stock-detail-empty">台股 ETF 資料載入失敗：${escapeHtml(error.message || String(error))}</p></article></section>`;
      root.innerHTML = `<section class="section"><article class="panel-card"><p class="stock-detail-empty">ETF 資料暫時無法載入：${escapeHtml(error.message || String(error))}</p></article></section>`;
    }
  }
}

function initTwEtfPage() {
  loadTwEtfPage();
}

function renderCurrentPage() {
  const page = document.body.dataset.page;
  if (page === "global-market") {
    initGlobalMarketPage(false);
    return;
  }
  if (page === "us-stock-search") {
    initUsStockSearchPage();
    return;
  }
  if (page === "us-etf") {
    initUsEtfPage();
    return;
  }
  if (page === "tw-etf") {
    initTwEtfPage();
    return;
  }
  if (page === "asset-hub") {
    initAssetHubPage();
    return;
  }
  if (page === "us-watchlist") {
    initUsWatchlistPage();
    return;
  }
  if (page === "derivatives-analytics") {
    initDerivativesAnalyticsPage();
    return;
  }
  if (page === "derivatives-ai") {
    initDerivativesAiPage();
    return;
  }
  if (!data) return;
  if (page === "home") renderHome();
  if (page === "market") renderMarketPage();
  if (page === "sectors") { renderSectorPageV2(); startVixPolling(); }
  if (page === "watchlist") renderWatchlist();
}

async function loadLiveData() {
  const page = document.body.dataset.page;
  const endpoint = page === "sectors"
    ? "/api/twse/live-sectors"
    : page === "market"
      ? "/api/twse/live-overview"
      : "/api/twse/site-data?refresh=1";
  const timeoutMs = page === "sectors" ? 45000 : 90000;
  if (page === "sectors") {
    setText("sector-source-note", "正在快速匯入 live 類股、加權指數與 VIX 資料...");
  }
  if (page === "market") {
    setText("institution-date", "live 同步中");
    const grid = document.getElementById("market-index-grid");
    if (grid && !grid.children.length) {
      grid.innerHTML = '<article class="overview-card"><span>資料狀態</span><strong>同步中</strong><small>正在同步 live 大盤、法人、VIX 與國際指數。</small></article>';
    }
  }
  try {
    const response = await fetchWithTimeout(
      endpoint,
      { cache: "no-store" },
      timeoutMs,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    data = await response.json();
    if (Array.isArray(data.stocks)) {
      localAllStocks = data.stocks;
    }
    renderCurrentPage();
    return true;
  } catch (error) {
    const sectorNote = document.getElementById("sector-source-note");
    if (page === "sectors" && sectorNote) {
      sectorNote.textContent = "live 類股資料同步失敗，請稍後重新整理。";
    }
    if (page === "market") {
      setText("institution-date", "live 同步失敗");
      const grid = document.getElementById("market-index-grid");
      if (grid) grid.innerHTML = '<article class="overview-card"><span>資料狀態</span><strong>同步失敗</strong><small>live 大盤資料暫時無法載入。</small></article>';
    }
    if (page === "watchlist") {
      setText("watchlist-status", "live 大盤資料同步失敗，請稍後再試。");
    }
    console.error("Failed to load live TWSE data:", error);
    return false;
  }
}

renderSharedNavigation();
if (document.body.dataset.page === "search") initSearchPage();
if (document.body.dataset.page === "watchlist") initWatchlistPage();
document.addEventListener("click", (event) => {
  const refreshButton = event.target.closest("[data-global-refresh]");
  if (refreshButton) {
    initGlobalMarketPage(true);
    return;
  }
  const button = event.target.closest("[data-yahoo-sector-group][data-yahoo-sector-index]");
  if (!button) return;
  const groupKey = button.dataset.yahooSectorGroup || "";
  const categoryIndex = Number(button.dataset.yahooSectorIndex);
  if (!groupKey || !Number.isInteger(categoryIndex)) return;
  loadYahooSectorCategory(groupKey, categoryIndex, button.textContent.trim());
});
renderCurrentPage();
if (!["search", "watchlist", "global-market", "tw-etf", "us-etf", "us-stock-search", "asset-hub", "us-watchlist", "derivatives-analytics", "derivatives-ai"].includes(document.body.dataset.page)) {
  loadLiveData();
  setInterval(loadLiveData, document.body.dataset.page === "sectors" ? 5 * 60 * 1000 : 60 * 1000);
}
