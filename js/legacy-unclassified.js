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
function getFuturesFiniteVisualSeries(values = []) {
  return (values || [])
    .map((value, index) => ({ value: parseMarketNumber(value), index }))
    .filter((point) => Number.isFinite(point.value));
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
