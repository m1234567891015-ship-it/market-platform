function getWeightedIndexSector() {
  return (data.sectors || []).find((sector) => sector.sourceName === "\u767c\u884c\u91cf\u52a0\u6b0a\u80a1\u50f9\u6307\u6578" || sector.name === "\u53f0\u7063\u52a0\u6b0a\u6307\u6578") || null;
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
