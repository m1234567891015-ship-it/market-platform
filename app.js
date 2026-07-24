
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

































































function renderAssetFinanceInternationalTrendPanel(model) {
  return `
    <article class="panel-card asset-finance-module-card asset-finance-trend-card">
      ${renderAssetFinanceTrendPanelContent(model)}
    </article>
  `;
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









function renderAssetFinancePriceForecastPanel(model) {
  return `
    <article class="panel-card asset-finance-module-card asset-finance-forecast-card">
      ${renderAssetFinancePriceForecastContent(model)}
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
