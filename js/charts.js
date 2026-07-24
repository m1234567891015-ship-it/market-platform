function renderSectorLineChart(sector) {
  const closes = (sector.candles || [])
    .map((candle) => parseMarketNumber(candle.close))
    .filter((value) => value !== null);

  if (closes.length < 2) {
    return renderSectorSnapshotLineChart(sector);
  }

  const width = 180;
  const height = 56;
  const pad = 6;
  const minValue = Math.min(...closes);
  const maxValue = Math.max(...closes);
  const range = maxValue - minValue || 1;
  const step = (width - pad * 2) / Math.max(closes.length - 1, 1);
  const points = closes.map((value, index) => {
    const x = pad + index * step;
    const y = height - pad - ((value - minValue) / range) * (height - pad * 2);
    return { x, y, value };
  });

  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");

  return `
    <svg class="class-line-chart ${toneClass(sector.tone)}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${sector.name} performance chart">
      <path class="class-line-track" d="${path}"></path>
      <circle class="class-line-end" cx="${points[points.length - 1].x.toFixed(1)}" cy="${points[points.length - 1].y.toFixed(1)}" r="3"></circle>
    </svg>
  `;
}
function renderSectorSnapshotLineChart(sector) {
  const previousClose = parseMarketNumber(sector?.previousClose);
  const open = parseMarketNumber(sector?.open);
  const low = parseMarketNumber(sector?.low);
  const high = parseMarketNumber(sector?.high);
  const close = parseMarketNumber(sector?.value ?? sector?.close);
  const points = [
    { label: "昨收", value: previousClose },
    { label: "開盤", value: open },
    { label: "最低", value: low },
    { label: "最高", value: high },
    { label: "最新", value: close },
  ].filter((point) => Number.isFinite(point.value));

  if (points.length < 2) {
    return '<div class="class-line-empty class-line-empty-compact">資料同步中</div>';
  }

  const width = 180;
  const height = 56;
  const pad = 6;
  const values = points.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;
  const step = (width - pad * 2) / Math.max(points.length - 1, 1);
  const yAt = (value) => range === 0
    ? height / 2
    : height - pad - ((value - minValue) / range) * (height - pad * 2);
  const svgPoints = points.map((point, index) => ({
    ...point,
    x: pad + index * step,
    y: yAt(point.value),
  }));
  const path = svgPoints
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
  const baseLine = Number.isFinite(previousClose)
    ? `<line class="class-line-base" x1="${pad}" y1="${yAt(previousClose).toFixed(1)}" x2="${width - pad}" y2="${yAt(previousClose).toFixed(1)}"></line>`
    : "";
  const endPoint = svgPoints[svgPoints.length - 1];
  const title = `${sector?.name || "類股"} 日內區間：${points.map((point) => `${point.label} ${point.value}`).join("，")}`;

  return `
    <svg class="class-line-chart class-line-chart-snapshot ${toneClass(sector?.tone)}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
      ${baseLine}
      <path class="class-line-track" d="${path}"></path>
      <circle class="class-line-end" cx="${endPoint.x.toFixed(1)}" cy="${endPoint.y.toFixed(1)}" r="3"></circle>
    </svg>
  `;
}
function renderWeightedVixComparisonChart(weightedIndex, volatility, options = {}) {
  const totalPoints = buildWeightedVixComparisonModel(weightedIndex, volatility).length;
  const aligned = buildWeightedVixComparisonModel(weightedIndex, volatility, options.visibleCount, options.panOffset);
  if (aligned.length < 2) {
    return {
      html: '<div class="class-line-empty">台股與 VIX 共同日期資料不足，暫不繪製比對圖。</div>',
      points: [],
      width: 0,
      height: 0,
      totalPoints,
      visiblePoints: 0,
    };
  }

  const width = 980;
  const height = 520;
  const pad = { top: 34, right: 28, bottom: 58, left: 58 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const values = aligned.flatMap((item) => [item.weightedNorm, item.vixNorm]);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  const step = plotWidth / Math.max(aligned.length - 1, 1);
  const xAt = (index) => pad.left + index * step;
  const yAt = (value) => pad.top + ((maxValue - value) / range) * plotHeight;
  const weightedPoints = aligned.map((item, index) => ({ x: xAt(index), y: yAt(item.weightedNorm), value: item.weightedNorm }));
  const vixPoints = aligned.map((item, index) => ({ x: xAt(index), y: yAt(item.vixNorm), value: item.vixNorm }));
  const weightedDelta = aligned.at(-1).weightedNorm - 100;
  const vixDelta = aligned.at(-1).vixNorm - 100;
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
    return `<rect class="sector-hover-zone" x="${left.toFixed(1)}" y="${pad.top}" width="${Math.max(zoneWidth, 8).toFixed(1)}" height="${plotHeight}" data-sync-index="${index}" data-tooltip-mode="vix-compare" data-label="${item.label}" data-taiex-close="${item.close.toFixed(2)}" data-vix-value="${item.vix.toFixed(2)}" data-taiex-base="${item.weightedNorm.toFixed(2)}" data-vix-base="${item.vixNorm.toFixed(2)}" data-base-diff="${(item.weightedNorm - item.vixNorm).toFixed(2)}"></rect>`;
  }).join("");

  return {
    html: `
      <div class="sector-sync-chart-summary">
        <span>台股加權指數與 VIX 比對</span>
        <strong>Base = 100</strong>
        <span>台股 ${weightedDelta >= 0 ? "+" : ""}${weightedDelta.toFixed(2)}% / VIX ${vixDelta >= 0 ? "+" : ""}${vixDelta.toFixed(2)}%</span>
      </div>
      <div class="sector-chart-frame">
        <svg class="sector-comparison-chart weighted-vix-comparison-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="台股加權指數與 VIX 比對圖">
          <g class="chart-grid">${gridLines}</g>
          <line class="sector-base-line" x1="${pad.left}" y1="${yAt(100)}" x2="${width - pad.right}" y2="${yAt(100)}"></line>
          <path class="weighted-vix-taiex-line" d="${buildPath(weightedPoints)}"></path>
          <path class="weighted-vix-risk-line" d="${buildPath(vixPoints)}"></path>
          <line class="sector-hover-guide" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
          <circle class="sector-hover-dot sector-hover-dot-sector" cx="${pad.left}" cy="${pad.top}" r="5"></circle>
          <g class="chart-labels">
            <text x="${pad.left}" y="${height - 18}">${aligned[0].label}</text>
            <text x="${width - pad.right - 90}" y="${height - 18}">${aligned.at(-1).label}</text>
            <text x="${width - pad.right - 230}" y="24">台股加權 / VIX / 共同日期</text>
          </g>
          <g class="sector-hover-zones">${hoverZones}</g>
        </svg>
        <div class="sector-sync-tooltip" hidden></div>
      </div>
      <div class="sector-chart-legend">
        <span><i class="legend-swatch weighted-vix-taiex-swatch"></i>台股加權指數</span>
        <span><i class="legend-swatch weighted-vix-risk-swatch"></i>VIX 指數</span>
        <span>兩條線都從 100 開始</span>
      </div>
    `,
    points: aligned.map((item, index) => ({
      ...item,
      x: xAt(index),
      sectorY: yAt(item.weightedNorm),
    })),
    width,
    height,
    totalPoints,
    visiblePoints: aligned.length,
  };
}
function renderVixSparkline(series = []) {
  const points = (Array.isArray(series) ? series : [])
    .map((item) => ({
      date: item.date || "",
      value: parseMarketNumber(item.value),
    }))
    .filter((item) => Number.isFinite(item.value));
  if (points.length < 2) {
    return '<div class="vix-sparkline-empty">VIX 走勢資料同步中</div>';
  }

  const width = 320;
  const height = 104;
  const pad = { top: 14, right: 12, bottom: 22, left: 12 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const minValue = Math.min(...points.map((item) => item.value));
  const maxValue = Math.max(...points.map((item) => item.value));
  const span = maxValue - minValue || 1;
  const xAt = (index) => pad.left + (points.length === 1 ? 0 : (index / (points.length - 1)) * plotWidth);
  const yAt = (value) => pad.top + (1 - ((value - minValue) / span)) * plotHeight;
  const path = points
    .map((point, index) => `${index ? "L" : "M"} ${xAt(index).toFixed(1)} ${yAt(point.value).toFixed(1)}`)
    .join(" ");
  const latest = points.at(-1);
  const first = points[0];
  const toneClassName = latest.value >= first.value ? "is-up" : "is-down";

  return `
    <div class="vix-sparkline ${toneClassName}" aria-label="VIX 近期走勢圖">
      <svg viewBox="0 0 ${width} ${height}" role="img">
        <line x1="${pad.left}" y1="${yAt(maxValue).toFixed(1)}" x2="${width - pad.right}" y2="${yAt(maxValue).toFixed(1)}"></line>
        <line x1="${pad.left}" y1="${yAt(minValue).toFixed(1)}" x2="${width - pad.right}" y2="${yAt(minValue).toFixed(1)}"></line>
        <path d="${path}"></path>
        <circle cx="${xAt(points.length - 1).toFixed(1)}" cy="${yAt(latest.value).toFixed(1)}" r="4"></circle>
        <text x="${pad.left}" y="${height - 5}">${first.date.slice(5) || first.date}</text>
        <text x="${width - pad.right}" y="${height - 5}" text-anchor="end">${latest.date.slice(5) || latest.date}</text>
      </svg>
      <div>
        <span>區間</span>
        <strong>${minValue.toFixed(2)} - ${maxValue.toFixed(2)}</strong>
      </div>
    </div>
  `;
}
function bindHorizontalChartPan(frame, onPan) {
  if (!frame) return;
  let startX = null;
  frame.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    startX = event.clientX;
    frame.setPointerCapture?.(event.pointerId);
    frame.classList.add("is-panning");
  });
  frame.addEventListener("pointerup", (event) => {
    if (startX === null) return;
    const distance = event.clientX - startX;
    startX = null;
    frame.classList.remove("is-panning");
    if (Math.abs(distance) < 28) return;
    onPan(distance > 0 ? "older" : "newer");
  });
  frame.addEventListener("pointercancel", () => {
    startX = null;
    frame.classList.remove("is-panning");
  });
}
function getChartHistory(detail, interval) {
  const history = normalizeHistory(detail);
  const aggregated = aggregateHistory(history, interval);
  const limits = {
    day: 300,
    week: 260,
    month: 240,
    quarter: 40,
    half: 30,
    year: 20,
    all: aggregated.length,
  };
  return aggregated.slice(-(limits[interval] || aggregated.length));
}
function getChartIntervalLabel(interval) {
  return {
    day: "日線",
    week: "週線",
    month: "月線",
    quarter: "季線",
    half: "半年",
    year: "年線",
    all: "全部",
  }[interval] || "日線";
}
function renderIndicatorChart(detail, interval, indicator, visibleCount = null, panOffset = 0) {
  const fullHistory = getChartHistory(detail, interval);
  const requestedCount = Number(visibleCount);
  const history = Number.isFinite(requestedCount) && requestedCount > 1
    ? sliceVisibleWindow(fullHistory, requestedCount, panOffset)
    : fullHistory;
  if (history.length < 2) {
    return '<div class="stock-detail-empty">查無指標資料。</div>';
  }

  const width = 980;
  const height = 420;
  const pad = { top: 34, right: 28, bottom: 72, left: 58 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const step = plotWidth / Math.max(history.length - 1, 1);
  const xAt = (index) => pad.left + index * step;
  const firstDate = history[0]?.date || "";
  const lastDate = history[history.length - 1]?.date || "";
  const modeLabel = getChartIntervalLabel(interval);
  let title = "";
  let latestLabel = "--";
  let series = [];
  let bars = [];
  let fixedMin = null;
  let fixedMax = null;

  if (indicator === "kd") {
    const kd = calculateKd(history);
    title = "KD 指標";
    latestLabel = `K ${kd[kd.length - 1].k.toFixed(2)} / D ${kd[kd.length - 1].d.toFixed(2)}`;
    fixedMin = 0;
    fixedMax = 100;
    series = [
      { className: "indicator-line-primary", values: kd.map((item) => item.k) },
      { className: "indicator-line-secondary", values: kd.map((item) => item.d) },
    ];
  } else if (indicator === "macd") {
    const macd = calculateMacd(history);
    title = "MACD 指標";
    const latest = macd[macd.length - 1];
    latestLabel = `DIF ${latest.dif?.toFixed(2) || "--"} / MACD ${latest.macd?.toFixed(2) || "--"}`;
    series = [
      { className: "indicator-line-primary", values: macd.map((item) => item.dif) },
      { className: "indicator-line-secondary", values: macd.map((item) => item.macd) },
    ];
    bars = macd.map((item) => item.osc);
  } else if (indicator === "rsi") {
    const rsi = calculateRsi(history);
    title = "RSI 指標";
    latestLabel = `RSI ${rsi[rsi.length - 1]?.toFixed(2) || "--"}`;
    fixedMin = 0;
    fixedMax = 100;
    series = [{ className: "indicator-line-primary", values: rsi }];
  } else if (indicator === "dmi") {
    const dmi = calculateDmi(history);
    title = "DMI 指標";
    const latest = dmi[dmi.length - 1] || {};
    latestLabel = `+DI ${latest.plusDi?.toFixed(2) || "--"} / -DI ${latest.minusDi?.toFixed(2) || "--"} / ADX ${latest.adx?.toFixed(2) || "--"}`;
    fixedMin = 0;
    fixedMax = 100;
    series = [
      { className: "indicator-line-primary", values: dmi.map((item) => item.plusDi) },
      { className: "indicator-line-secondary", values: dmi.map((item) => item.minusDi) },
      { className: "indicator-line-tertiary", values: dmi.map((item) => item.adx) },
    ];
  } else if (indicator === "obv") {
    const obv = calculateObv(history);
    title = "OBV 指標";
    latestLabel = `OBV ${Math.round(obv[obv.length - 1] || 0).toLocaleString("zh-TW")}`;
    series = [{ className: "indicator-line-primary", values: obv }];
  } else {
    const bias = calculateBias(history);
    title = "BIAS";
    latestLabel = `BIAS6 ${bias[bias.length - 1]?.toFixed(2) || "--"}%`;
    series = [{ className: "indicator-line-primary", values: bias }];
  }

  const values = [...series.flatMap((item) => item.values), ...bars].filter((value) => value !== null && Number.isFinite(value));
  const minValue = fixedMin ?? Math.min(...values, 0);
  const maxValue = fixedMax ?? Math.max(...values, 0);
  const valueRange = maxValue - minValue || 1;
  const yAt = (value) => pad.top + ((maxValue - value) / valueRange) * plotHeight;
  const zeroY = yAt(Math.min(Math.max(0, minValue), maxValue));

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * plotHeight;
    const label = maxValue - ratio * valueRange;
    return `
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line>
      <text x="12" y="${y + 5}">${label.toFixed(2)}</text>
    `;
  }).join("");

  const lineHtml = series.map((item) => {
    const points = item.values.map((value, index) => ({
      x: xAt(index),
      y: value === null ? 0 : yAt(value),
      value,
    }));
    return `<path class="${item.className}" d="${buildPath(points)}"></path>`;
  }).join("");

  const barWidth = Math.min(14, Math.max(1.2, step * 0.5));
  const barHtml = bars.map((value, index) => {
    if (value === null) return "";
    const y = yAt(value);
    const top = Math.min(y, zeroY);
    const heightValue = Math.max(Math.abs(y - zeroY), 2);
    const tone = value >= 0 ? "up" : "down";
    return `<rect class="indicator-histogram ${tone}" x="${(xAt(index) - barWidth / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${heightValue.toFixed(1)}" rx="2"></rect>`;
  }).join("");

  return `
    <div class="chart-summary">
      <span>${detail.code} ${detail.name} / ${modeLabel} / ${title}</span>
      <strong>${latestLabel}</strong>
      <span>${firstDate} - ${lastDate}</span>
    </div>
    <svg class="technical-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${detail.code} ${detail.name} ${title} 指標圖">
      <g class="chart-grid">${gridLines}</g>
      <line class="indicator-zero-line" x1="${pad.left}" y1="${zeroY}" x2="${width - pad.right}" y2="${zeroY}"></line>
      <g>${barHtml}</g>
      ${lineHtml}
      <g class="chart-labels">
        <text x="${pad.left}" y="${height - 24}">${firstDate}</text>
        <text x="${width - pad.right - 90}" y="${height - 24}">${lastDate}</text>
      <text class="chart-ma-label" x="${width - pad.right - 238}" y="24">${modeLabel} / ${title}</text>
      </g>
    </svg>
  `;
}
function renderTechnicalChart(detail, interval = "day", overlayIndicators = [], maPeriods = [5], visibleCount = null, panOffset = 0, panelIndicators = ["kd"]) {
  const fullHistory = getChartHistory(detail, interval);
  const requestedCount = Number(visibleCount);
  const history = Number.isFinite(requestedCount) && requestedCount > 1
    ? sliceVisibleWindow(fullHistory, requestedCount, panOffset)
    : fullHistory;

  if (history.length < 2) {
    return '<div class="stock-detail-empty">無可用技術圖資料。</div>';
  }

  const width = 980;
  const isSnapshotHistory = detail.isFallbackHistory || history.length < 6;
  const hasTechnicalIndicators = history.length >= 6;
  const pad = { top: 34, right: 28, bottom: 72, left: 58 };
  const priceHeight = 300;
  const volumeTop = pad.top + priceHeight + 42;
  const volumeHeight = 76;
  const indicatorStartTop = volumeTop + volumeHeight + 42;
  const indicatorHeight = 118;
  const indicatorGap = 32;
  const activePanelIndicators = (Array.isArray(panelIndicators) ? panelIndicators : [panelIndicators])
    .filter((item) => TECHNICAL_PANEL_INDICATOR_KEYS.includes(item));
  const selectedPanelIndicators = activePanelIndicators.length ? activePanelIndicators : ["kd"];
  const indicatorCount = selectedPanelIndicators.length;
  const height = hasTechnicalIndicators
    ? indicatorStartTop + (indicatorHeight + indicatorGap) * (indicatorCount - 1) + indicatorHeight + pad.bottom
    : 520;
  const plotWidth = width - pad.left - pad.right;
  const closes = history.map((day) => day.close);
  const activeOverlayIndicators = (Array.isArray(overlayIndicators) ? overlayIndicators : [overlayIndicators])
    .filter((item) => ["bollinger", "fibonacci", "supportResistance", "smc"].includes(item));
  const activeMaPeriods = [...new Set(maPeriods)].filter((period) => [5, 10, 20, 60, 120, 240].includes(period));
  const maSeries = activeMaPeriods.map((period) => ({
    period,
    values: movingAverage(closes, period),
  }));
  const bollinger = activeOverlayIndicators.includes("bollinger") ? calculateBollingerBands(history) : [];
  const fibonacci = activeOverlayIndicators.includes("fibonacci") ? calculateFibonacciRetracement(history, Math.min(80, history.length)) : null;
  const supportResistance = activeOverlayIndicators.includes("supportResistance") ? calculateSupportResistance(history, Math.min(80, history.length)) : null;
  const smc = activeOverlayIndicators.includes("smc") ? calculateSmartMoneyConcepts(history, Math.min(90, history.length)) : null;
  const overlayValues = [
    ...bollinger.flatMap((item) => [item.upper, item.middle, item.lower]),
    ...(fibonacci?.levels || []).map((item) => item.value),
    ...(supportResistance?.supports || []).map((item) => item.value),
    ...(supportResistance?.resistances || []).map((item) => item.value),
    ...(smc?.levels || []).flatMap((item) => [item.value, item.upper, item.lower]),
  ].filter(Number.isFinite);
  const priceValues = history
    .flatMap((day, index) => [day.high, day.low, ...maSeries.map((series) => series.values[index])])
    .concat(overlayValues)
    .filter((value) => value !== null);
  const rawMinPrice = Math.min(...priceValues);
  const rawMaxPrice = Math.max(...priceValues);
  const rawPriceRange = rawMaxPrice - rawMinPrice;
  const pricePadding = Math.max(rawPriceRange * 0.08, Math.abs(rawMaxPrice) * 0.005, 0.01);
  const minPrice = rawMinPrice - pricePadding;
  const maxPrice = rawMaxPrice + pricePadding;
  const priceRange = maxPrice - minPrice || 1;
  const maxVolume = Math.max(...history.map((day) => day.volume || 0), 1);
  const displaySlots = Math.max(history.length, 30);
  const step = plotWidth / Math.max(displaySlots - 1, 1);
  const xStart = pad.left + (displaySlots - history.length) * step;
  const candleWidth = Math.min(16, Math.max(1.2, step * 0.48));
  const priceY = (value) => pad.top + ((maxPrice - value) / priceRange) * priceHeight;
  const volumeY = (value) => volumeTop + volumeHeight - ((value || 0) / maxVolume) * volumeHeight;
  const xAt = (index) => xStart + index * step;

  const closePoints = history.map((day, index) => ({
    x: xAt(index),
    y: priceY(day.close),
    value: day.close,
  }));
  const maPaths = maSeries.map((series) => {
    const points = series.values.map((value, index) => ({
      x: xAt(index),
      y: value === null ? 0 : priceY(value),
      value,
    }));
    return `<path class="chart-ma-line ma-${series.period}" d="${buildPath(points)}"></path>`;
  }).join("");

  const renderPriceLevel = (level, className, label, dash = false) => {
    if (!Number.isFinite(level)) return "";
    const y = priceY(level);
    return `
      <g class="${className}">
        <line x1="${pad.left}" y1="${y.toFixed(1)}" x2="${width - pad.right}" y2="${y.toFixed(1)}" ${dash ? 'stroke-dasharray="6 6"' : ""}></line>
        <text x="${width - pad.right - 4}" y="${(y - 5).toFixed(1)}" text-anchor="end">${label}</text>
      </g>
    `;
  };

  const bollingerOverlay = activeOverlayIndicators.includes("bollinger") ? (() => {
    const upperPoints = bollinger.map((item, index) => ({ x: xAt(index), y: item.upper === null ? 0 : priceY(item.upper), value: item.upper }));
    const middlePoints = bollinger.map((item, index) => ({ x: xAt(index), y: item.middle === null ? 0 : priceY(item.middle), value: item.middle }));
    const lowerPoints = bollinger.map((item, index) => ({ x: xAt(index), y: item.lower === null ? 0 : priceY(item.lower), value: item.lower }));
    const latestBand = bollinger.at(-1);
    return `
      <g class="chart-overlay bollinger-overlay">
        <path class="bollinger-band-line is-upper" d="${buildPath(upperPoints)}"></path>
        <path class="bollinger-band-line is-middle" d="${buildPath(middlePoints)}"></path>
        <path class="bollinger-band-line is-lower" d="${buildPath(lowerPoints)}"></path>
        <text x="${pad.left}" y="24">布林通道 ${latestBand?.bandwidth ? `帶寬 ${latestBand.bandwidth.toFixed(1)}%` : ""}</text>
      </g>
    `;
  })() : "";

  const fibonacciOverlay = activeOverlayIndicators.includes("fibonacci") && fibonacci ? `
    <g class="chart-overlay fibonacci-overlay">
      ${fibonacci.levels.map((level) => renderPriceLevel(level.value, "fibonacci-level", `Fib ${level.label} ${level.value.toFixed(2)}`, true)).join("")}
      <text x="${pad.left}" y="24">${fibonacci.upSwing ? "上升波回撤" : "下降波反彈"}：${fibonacci.lowPoint.value.toFixed(2)} - ${fibonacci.highPoint.value.toFixed(2)}</text>
    </g>
  ` : "";

  const supportResistanceOverlay = activeOverlayIndicators.includes("supportResistance") && supportResistance ? `
    <g class="chart-overlay support-resistance-overlay">
      ${(supportResistance.supports || []).map((item) => renderPriceLevel(item.value, "support-level", `支撐 ${item.value.toFixed(2)} (${item.touches})`)).join("")}
      ${(supportResistance.resistances || []).map((item) => renderPriceLevel(item.value, "resistance-level", `壓力 ${item.value.toFixed(2)} (${item.touches})`)).join("")}
      <text x="${pad.left}" y="24">Support and Resistance</text>
    </g>
  ` : "";

  const smcOverlay = activeOverlayIndicators.includes("smc") && smc ? `
    <g class="chart-overlay smc-overlay">
      ${(smc.levels || []).map((item) => {
        if (Number.isFinite(item.upper) && Number.isFinite(item.lower)) {
          const yTop = priceY(Math.max(item.upper, item.lower));
          const yBottom = priceY(Math.min(item.upper, item.lower));
          return `
            <rect class="smc-zone ${item.type}" x="${pad.left}" y="${yTop.toFixed(1)}" width="${plotWidth}" height="${Math.max(yBottom - yTop, 3).toFixed(1)}" rx="6"></rect>
            <text x="${pad.left + 8}" y="${(yTop + 14).toFixed(1)}">${item.label}</text>
          `;
        }
        return renderPriceLevel(item.value, `smc-level ${item.type}`, `${item.label} ${item.value.toFixed(2)}`, true);
      }).join("")}
      <text x="${pad.left}" y="24">SMC：${smc.signals?.[0] || "觀察 BOS / 流動性 / FVG"}</text>
    </g>
  ` : "";
  const overlayHtml = `${bollingerOverlay}${fibonacciOverlay}${supportResistanceOverlay}${smcOverlay}`;

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * priceHeight;
    const label = maxPrice - ratio * priceRange;
    return `
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line>
      <text x="12" y="${y + 5}">${label.toFixed(2)}</text>
    `;
  }).join("");

  const candles = history.map((day, index) => {
    const x = xAt(index);
    const openY = priceY(day.open ?? day.close);
    const closeY = priceY(day.close);
    const highY = priceY(day.high ?? day.close);
    const lowY = priceY(day.low ?? day.close);
    const bodyTop = Math.min(openY, closeY);
    const bodyHeight = Math.max(Math.abs(openY - closeY), 3);
    const open = day.open ?? day.close;
    const tone = day.close > open ? "up" : day.close < open ? "down" : "flat";
    return `
      <line class="candle-wick technical-candle-wick ${tone}" x1="${x.toFixed(1)}" y1="${highY.toFixed(1)}" x2="${x.toFixed(1)}" y2="${lowY.toFixed(1)}"></line>
      <rect class="candle-body technical-candle-body ${tone}" x="${(x - candleWidth / 2).toFixed(1)}" y="${bodyTop.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${bodyHeight.toFixed(1)}" rx="2"></rect>
    `;
  }).join("");

  const volumeBars = history.map((day, index) => {
    const x = xAt(index);
    const y = volumeY(day.volume);
    const barHeight = volumeTop + volumeHeight - y;
    const open = day.open ?? day.close;
    const tone = day.close > open ? "up" : day.close < open ? "down" : "flat";
    return `<rect class="technical-volume-bar ${tone}" x="${(x - candleWidth / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="2"></rect>`;
  }).join("");

  const kd = hasTechnicalIndicators ? calculateKd(history) : [];
  const macd = history.length >= 26 ? calculateMacd(history) : [];
  const rsi = history.length >= 14 ? calculateRsi(history) : [];
  const bias = hasTechnicalIndicators ? calculateBias(history) : [];
  const dmi = history.length >= 15 ? calculateDmi(history) : [];
  const obv = hasTechnicalIndicators ? calculateObv(history) : [];
  const atr = history.length >= 15 ? calculateAtr(history) : [];
  const cci = history.length >= 20 ? calculateCci(history) : [];
  const williams = history.length >= 14 ? calculateWilliamsR(history) : [];
  const mfi = history.length >= 15 ? calculateMfi(history) : [];
  const momentum = history.length >= 11 ? calculateMomentum(history) : [];
  const sar = history.length >= 4 ? calculateParabolicSarSeries(history) : [];
  const panelBollinger = history.length >= 20 ? calculateBollingerBands(history) : [];
  const ichimoku = history.length >= 9 ? calculateIchimoku(history) : [];
  const hoverBottom = hasTechnicalIndicators
    ? indicatorStartTop + (indicatorHeight + indicatorGap) * (indicatorCount - 1) + indicatorHeight
    : volumeTop + volumeHeight;
  const crosshairBottom = height - 18;

  // Transparent hover zones — one per candle, covering the full chart stack.
  const hoverZoneWidth = Math.max(step, candleWidth + 4);
  const hoverZones = history.map((day, index) => {
    const x = xAt(index);
    const left = Math.max(pad.left, x - hoverZoneWidth / 2);
    const right = Math.min(width - pad.right, x + hoverZoneWidth / 2);
    const zoneW = right - left;
    const rawChange = typeof day.change === "number" ? day.change : parseFloat(day.change);
    const changeStr = Number.isFinite(rawChange)
      ? (rawChange >= 0 ? "+" : "") + rawChange.toFixed(2)
      : "--";
    return `<rect class="chart-hover-zone"
      x="${left.toFixed(1)}" y="${pad.top}"
      width="${Math.max(zoneW, 8).toFixed(1)}" height="${hoverBottom - pad.top}"
      data-index="${index}"
      data-date="${day.date ?? ""}"
      data-open="${day.open ?? "--"}"
      data-high="${day.high ?? "--"}"
      data-low="${day.low ?? "--"}"
      data-close="${day.close ?? "--"}"
      data-change="${changeStr}"
      data-volume="${typeof day.volume === "number" ? day.volume.toLocaleString() : (day.volume ?? "--")}"
      data-k="${kd[index]?.k?.toFixed(2) ?? "--"}"
      data-d="${kd[index]?.d?.toFixed(2) ?? "--"}"
      data-dif="${macd[index]?.dif?.toFixed(2) ?? "--"}"
      data-macd="${macd[index]?.macd?.toFixed(2) ?? "--"}"
      data-osc="${macd[index]?.osc?.toFixed(2) ?? "--"}"
      data-rsi="${rsi[index]?.toFixed(2) ?? "--"}"
      data-bias="${bias[index]?.toFixed(2) ?? "--"}"
      data-plus-di="${dmi[index]?.plusDi?.toFixed(2) ?? "--"}"
      data-minus-di="${dmi[index]?.minusDi?.toFixed(2) ?? "--"}"
      data-adx="${dmi[index]?.adx?.toFixed(2) ?? "--"}"
      data-obv="${obv[index] !== undefined ? Math.round(obv[index]).toLocaleString() : "--"}"
      data-atr="${atr[index]?.toFixed(2) ?? "--"}"
      data-cci="${cci[index]?.toFixed(2) ?? "--"}"
      data-williams="${williams[index]?.toFixed(2) ?? "--"}"
      data-mfi="${mfi[index]?.toFixed(2) ?? "--"}"
      data-momentum="${momentum[index]?.toFixed(2) ?? "--"}"
      data-sar="${sar[index]?.toFixed(2) ?? "--"}"
      data-bollinger="${panelBollinger[index]?.upper ? `${panelBollinger[index].lower.toFixed(2)} / ${panelBollinger[index].upper.toFixed(2)}` : "--"}"
      data-ichimoku="${ichimoku[index]?.tenkan ? `${ichimoku[index].tenkan.toFixed(2)} / ${ichimoku[index].kijun?.toFixed(2) || "--"} / ${ichimoku[index].senkouB?.toFixed(2) || "--"}` : "--"}"
    ></rect>`;
  }).join("");

  const firstDate = history[0]?.date || "";
  const lastDate = history[history.length - 1]?.date || "";
  const latest = history[history.length - 1];
  const buildPanelConfig = (key, index) => {
    const top = indicatorStartTop + (indicatorHeight + indicatorGap) * index;
    const baseConfig = {
      top,
      height: indicatorHeight,
      width,
      pad,
      xAt,
    };
    const configs = {
      kd: {
      title: "KD",
      ...baseConfig,
      values: kd.map((item) => item.k),
      secondaryValues: kd.map((item) => item.d),
      fixedMin: 0,
      fixedMax: 100,
    },
    macd: {
      title: "MACD",
      ...baseConfig,
      values: macd.map((item) => item.dif),
      secondaryValues: macd.map((item) => item.macd),
      bars: macd.map((item) => item.osc),
    },
    rsi: {
      title: "RSI",
      ...baseConfig,
      values: rsi,
      fixedMin: 0,
      fixedMax: 100,
    },
    bias: {
      title: "BIAS",
      ...baseConfig,
      values: bias,
    },
    dmi: {
      title: "DMI (+DI / -DI / ADX)",
      ...baseConfig,
      values: dmi.map((item) => item.plusDi),
      secondaryValues: dmi.map((item) => item.minusDi),
      tertiaryValues: dmi.map((item) => item.adx),
      fixedMin: 0,
      fixedMax: 100,
    },
    obv: {
      title: "OBV",
      ...baseConfig,
      values: obv,
    },
    atr: {
      title: "ATR",
      ...baseConfig,
      values: atr,
    },
    cci: {
      title: "CCI",
      ...baseConfig,
      values: cci,
    },
    williams: {
      title: "Williams %R",
      ...baseConfig,
      values: williams,
      fixedMin: -100,
      fixedMax: 0,
    },
    mfi: {
      title: "MFI",
      ...baseConfig,
      values: mfi,
      fixedMin: 0,
      fixedMax: 100,
    },
    momentum: {
      title: "Momentum",
      ...baseConfig,
      values: momentum,
    },
    sar: {
      title: "SAR / Close",
      ...baseConfig,
      values: history.map((item) => item.close),
      secondaryValues: sar,
    },
    bollinger: {
      title: "Bollinger",
      ...baseConfig,
      values: panelBollinger.map((item) => item.lower),
      secondaryValues: panelBollinger.map((item) => item.middle),
      tertiaryValues: panelBollinger.map((item) => item.upper),
    },
    ichimoku: {
      title: "Ichimoku",
      ...baseConfig,
      values: ichimoku.map((item) => item.tenkan),
      secondaryValues: ichimoku.map((item) => item.kijun),
      tertiaryValues: ichimoku.map((item) => item.senkouB),
    },
  };
    return configs[key] || configs.kd;
  };
  const combinedIndicators = hasTechnicalIndicators
    ? selectedPanelIndicators.map((key, index) => renderCombinedIndicatorPanel(buildPanelConfig(key, index))).join("")
    : "";
  const modeLabel = {
    day: "日線",
    week: "週線",
    month: "月線",
    all: "全部",
  }[interval] || "日線";
  const overlayLabels = {
    bollinger: "布林通道",
    fibonacci: "斐波那契回撤",
    supportResistance: "支撐壓力",
    smc: "Smart Money Concepts",
  };
  const baseLabel = activeMaPeriods.length ? activeMaPeriods.map((period) => `MA${period}`).join(" ") : "K 線";
  const indicatorLabel = [baseLabel, ...activeOverlayIndicators.map((key) => overlayLabels[key] || key)].join(" / ");
  const panelLabels = {
    kd: "KD",
    macd: "MACD",
    rsi: "RSI",
    dmi: "DMI",
    bias: "BIAS",
    obv: "OBV",
    atr: "ATR",
    cci: "CCI",
    williams: "Williams %R",
    mfi: "MFI",
    momentum: "Momentum",
    sar: "SAR",
    bollinger: "Bollinger",
    ichimoku: "Ichimoku",
  };
  const panelLabel = selectedPanelIndicators.map((key) => panelLabels[key] || key).join(" / ");

  return `
    <div class="chart-summary">
      <span>${detail.code} ${detail.name} / ${modeLabel} / ${indicatorLabel} / 下方指標：${panelLabel}</span>
      <strong>${latest?.close?.toLocaleString() || "--"}</strong>
      <span>${firstDate} - ${lastDate}</span>
    </div>
    ${isSnapshotHistory ? '<p class="chart-data-notice">目前為快取行情快照；歷史資料同步完成後會自動更新完整 K 線與技術指標。</p>' : ""}
    <div class="sector-chart-frame">
      <svg class="technical-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${detail.code} ${detail.name} technical chart">
        <g class="chart-grid">${gridLines}</g>
        <g>${candles}</g>
        <path class="chart-line technical-price-line" d="${buildPath(closePoints)}"></path>
        ${maPaths}
        ${overlayHtml}
        <g class="chart-volume-bars">${volumeBars}</g>
        ${combinedIndicators}
        <g class="chart-labels">
          <text x="${pad.left}" y="${height - 24}">${firstDate}</text>
          <text x="${width - pad.right - 90}" y="${height - 24}">${lastDate}</text>
          <text x="${pad.left}" y="${volumeTop - 12}">成交量</text>
          <text class="chart-ma-label" x="${width - pad.right - 238}" y="24">${modeLabel} / ${indicatorLabel}</text>
        </g>
        <g class="chart-hover-zones">${hoverZones}</g>
        <line class="chart-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${crosshairBottom}" style="display:none"></line>
      </svg>
      <div class="sector-sync-tooltip chart-kline-tooltip" hidden></div>
    </div>
  `;
}
function bindChartHover(chartView) {
  if (!chartView) return;
  const tooltip = chartView.querySelector(".chart-kline-tooltip");
  const crosshair = chartView.querySelector(".chart-crosshair");
  if (!tooltip) return;

  const zones = chartView.querySelectorAll(".chart-hover-zone");

  const hide = () => {
    tooltip.hidden = true;
    if (crosshair) crosshair.style.display = "none";
    chartView.querySelectorAll(".chart-indicator-point.is-active").forEach((point) => {
      point.classList.remove("is-active");
    });
  };

  const positionTooltip = (event, frame) => {
    const frameRect = frame.getBoundingClientRect();
    const tooltipWidth = tooltip.offsetWidth || 230;
    const tooltipHeight = tooltip.offsetHeight || 330;
    const pointerX = event.clientX - frameRect.left;
    const pointerY = event.clientY - frameRect.top;
    const gap = 14;

    let left = pointerX + gap;
    if (left + tooltipWidth > frameRect.width - 6) {
      left = pointerX - tooltipWidth - gap;
    }
    left = Math.max(6, Math.min(left, frameRect.width - tooltipWidth - 6));

    let top = pointerY - tooltipHeight / 2;
    top = Math.max(6, Math.min(top, frameRect.height - tooltipHeight - 6));

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
    tooltip.style.transform = "none";
  };

  zones.forEach((zone) => {
    zone.addEventListener("mouseenter", (event) => {
      const d = zone.dataset;
      const changeVal = parseFloat(d.change);
      const changeCls = isNaN(changeVal) ? "" : changeVal > 0 ? "up" : changeVal < 0 ? "down" : "flat";

      tooltip.hidden = false;
      tooltip.innerHTML = `
        <strong style="font-size:0.9rem;margin-bottom:4px;display:block">${d.date}</strong>
        <span>開　盤：<strong>${d.open}</strong></span>
        <span>最　高：<strong class="up">${d.high}</strong></span>
        <span>最　低：<strong class="down">${d.low}</strong></span>
        <span>收　盤：<strong>${d.close}</strong></span>
        <span>漲　跌：<strong class="${changeCls}">${d.change}</strong></span>
        <span>成交量：<strong>${d.volume}</strong></span>
        <span class="chart-tooltip-divider">KD：<strong>K ${d.k} / D ${d.d}</strong></span>
        <span>MACD：<strong>${d.dif} / ${d.macd}</strong></span>
        <span>OSC：<strong>${d.osc}</strong></span>
        <span>RSI：<strong>${d.rsi}</strong></span>
        <span>BIAS：<strong>${d.bias === "--" ? "--" : `${d.bias}%`}</strong></span>
        <span>DMI：<strong>+DI ${d.plusDi} / -DI ${d.minusDi} / ADX ${d.adx}</strong></span>
        <span>OBV：<strong>${d.obv}</strong></span>
        <span>ATR：<strong>${d.atr}</strong></span>
        <span>CCI：<strong>${d.cci}</strong></span>
        <span>Williams %R：<strong>${d.williams}</strong></span>
        <span>MFI：<strong>${d.mfi}</strong></span>
        <span>Momentum：<strong>${d.momentum}</strong></span>
        <span>SAR：<strong>${d.sar}</strong></span>
        <span>Bollinger：<strong>${d.bollinger}</strong></span>
        <span>Ichimoku：<strong>${d.ichimoku}</strong></span>
      `;

      chartView.querySelectorAll(".chart-indicator-point.is-active").forEach((point) => {
        point.classList.remove("is-active");
      });
      chartView.querySelectorAll(`.chart-indicator-point[data-index="${d.index}"]`).forEach((point) => {
        point.classList.add("is-active");
      });

      // Position tooltip relative to the frame
      const frame = zone.closest(".sector-chart-frame");
      if (!frame) return;
      const zoneRect = zone.getBoundingClientRect();
      positionTooltip(event, frame);

      // Move crosshair
      if (crosshair) {
        const svgEl = frame.querySelector("svg");
        if (svgEl) {
          const svgRect = svgEl.getBoundingClientRect();
          const ratio = svgEl.viewBox.baseVal.width / svgRect.width;
          const cx = (zoneRect.left + zoneRect.width / 2 - svgRect.left) * ratio;
          crosshair.setAttribute("x1", cx.toFixed(1));
          crosshair.setAttribute("x2", cx.toFixed(1));
          crosshair.style.display = "block";
          crosshair.style.opacity = "1";
        }
      }
    });

    zone.addEventListener("mousemove", (event) => {
      const frame = zone.closest(".sector-chart-frame");
      if (frame) positionTooltip(event, frame);
    });

    zone.addEventListener("mouseleave", hide);
  });

  chartView.querySelector(".sector-chart-frame")?.addEventListener("mouseleave", hide);
}
