function renderMiniLineChart(series = []) {
  const points = (series || [])
    .map((item, index) => ({ index, value: parseMarketNumber(item.close) }))
    .filter((point) => Number.isFinite(point.value));
  if (points.length < 2) {
    return '<div class="global-chart-empty">線上資料不足，暫無走勢圖。</div>';
  }
  const width = 360;
  const height = 130;
  const min = Math.min(...points.map((point) => point.value));
  const max = Math.max(...points.map((point) => point.value));
  const span = max - min || 1;
  const mapped = points.map((point, index) => ({
    value: point.value,
    x: 12 + (index / Math.max(points.length - 1, 1)) * (width - 24),
    y: 14 + ((max - point.value) / span) * (height - 28),
  }));
  const path = buildPath(mapped);
  const first = series.find((item) => Number.isFinite(parseMarketNumber(item.close)));
  const last = [...series].reverse().find((item) => Number.isFinite(parseMarketNumber(item.close)));
  return `
    <svg class="global-mini-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="近期走勢圖">
      <defs>
        <linearGradient id="globalLineFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#45a6ff" stop-opacity="0.26"></stop>
          <stop offset="100%" stop-color="#45a6ff" stop-opacity="0"></stop>
        </linearGradient>
      </defs>
      <path class="global-mini-area" d="${path} L ${mapped[mapped.length - 1].x.toFixed(1)} ${height - 8} L ${mapped[0].x.toFixed(1)} ${height - 8} Z"></path>
      <path class="global-mini-line" d="${path}"></path>
      <text x="12" y="${height - 8}" class="global-chart-date">${escapeHtml(first?.date || "")}</text>
      <text x="${width - 12}" y="${height - 8}" text-anchor="end" class="global-chart-date">${escapeHtml(last?.date || "")}</text>
    </svg>
  `;
}
function buildUsMarketSentiment(selected, vix, indexReturn, vixReturn) {
  const vixValue = parseMarketNumber(vix?.close);
  const band = getVixSentimentBand(vixValue);
  const riskTemperature = Number.isFinite(vixValue)
    ? Math.max(0, Math.min(100, Math.round(((vixValue - 10) / 35) * 100)))
    : null;
  let signal = "中性觀察";
  let divergence = "未形成明顯背離";
  if (Number.isFinite(vixReturn) && Number.isFinite(indexReturn)) {
    if (indexReturn > 0 && vixReturn < 0) {
      signal = "風險偏好改善";
      divergence = "指數走強且 VIX 回落，屬於偏多確認。";
    } else if (indexReturn < 0 && vixReturn > 0) {
      signal = "避險升溫";
      divergence = "指數走弱且 VIX 上升，市場轉向防禦。";
    } else if (indexReturn > 0 && vixReturn > 0) {
      signal = "上漲但避險同步升溫";
      divergence = "指數上漲但 VIX 同升，代表追價信心不足或事件風險升高。";
    } else if (indexReturn < 0 && vixReturn < 0) {
      signal = "跌勢恐慌降溫";
      divergence = "指數偏弱但 VIX 回落，可能是修正趨緩或賣壓收斂。";
    }
  }
  return {
    band,
    riskTemperature,
    signal,
    divergence,
    label: Number.isFinite(riskTemperature) ? `${riskTemperature}/100` : "--",
    selectedName: selected?.name || selected?.symbol || "主要指數",
  };
}
function renderUsMarketSentimentValueCard({
  sentiment,
  vix,
  selected,
  selectedIndexes = [],
  chartState = {},
  indexReturn = null,
  vixReturn = null,
}) {
  const vixValue = parseMarketNumber(vix?.close);
  const vixDailyPct = parseMarketNumber(vix?.pct);
  const riskTemperature = Number.isFinite(sentiment?.riskTemperature) ? sentiment.riskTemperature : null;
  const riskValue = riskTemperature === null ? "--" : `${riskTemperature}/100`;
  const riskWidth = riskTemperature === null ? "0%" : `${Math.max(0, Math.min(100, riskTemperature))}%`;
  const signed = (value) => Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
  const posture = riskTemperature === null
    ? { label: "等待資料", tone: "watch", action: "VIX 歷史資料不足，先以最新報價與主要指數方向輔助判斷。" }
    : riskTemperature >= 70
      ? { label: "防守優先", tone: "negative", action: "恐慌溫度偏高，降低追價、槓桿與集中部位，等 VIX 回落再提高曝險。" }
      : riskTemperature >= 50
        ? { label: "控管追價", tone: "watch", action: "波動進入警戒，強勢股可觀察但需分批，並把停損條件先寫清楚。" }
        : riskTemperature <= 25
          ? { label: "風險偏好佳", tone: "positive", action: "波動低檔時可追蹤突破與類股擴散，但需留意過度樂觀後的波動回補。" }
          : { label: "中性觀察", tone: "neutral", action: "情緒在常態區間，先用指數方向、成交量與類股輪動確認下一步。" };
  const divergenceTone = sentiment?.signal === "避險升溫" || sentiment?.signal === "上漲但避險同步升溫"
    ? "negative"
    : sentiment?.signal === "風險偏好改善" || sentiment?.signal === "跌勢恐慌降溫"
      ? "positive"
      : "watch";
  const dailyTone = Number.isFinite(vixDailyPct)
    ? vixDailyPct > 3 ? "negative" : vixDailyPct < -3 ? "positive" : "neutral"
    : "watch";
  const scopeLabel = chartState.comparison ? `${selectedIndexes.length} 指數` : getUsBenchmarkDisplayName(selected);
  const metrics = [
    { label: "VIX 最新", value: formatGlobalValue(vix?.close), note: vix?.pct || "--", tone: dailyTone },
    { label: "風險溫度", value: riskValue, note: posture.label, tone: posture.tone },
    { label: "指數區間", value: signed(indexReturn), note: scopeLabel, tone: Number.isFinite(indexReturn) ? (indexReturn >= 0 ? "positive" : "negative") : "watch" },
    { label: "VIX 區間", value: signed(vixReturn), note: "同視窗變化", tone: Number.isFinite(vixReturn) ? (vixReturn <= 0 ? "positive" : "negative") : "watch" },
  ];
  const rules = [
    {
      label: "偏多確認",
      tone: Number.isFinite(indexReturn) && indexReturn > 0 && Number.isFinite(vixReturn) && vixReturn < 0 ? "positive" : "neutral",
      text: "指數走強且 VIX 回落，代表風險偏好較健康。",
    },
    {
      label: "風險警戒",
      tone: Number.isFinite(vixValue) && (vixValue >= 25 || (Number.isFinite(vixDailyPct) && vixDailyPct > 4)) ? "negative" : "neutral",
      text: "VIX 高於 25 或單日快速上升時，追價權重需下降。",
    },
    {
      label: "背離觀察",
      tone: divergenceTone,
      text: sentiment?.divergence || "指數與 VIX 尚未形成明確背離。",
    },
  ];
  return `
    <div class="us-market-sentiment-card is-${escapeHtml(sentiment?.band?.tone || "neutral")}">
      <div class="us-market-sentiment-main">
        <div>
          <span>市場情緒數值</span>
          <strong>VIX ${formatGlobalValue(vix?.close)} · ${escapeHtml(sentiment?.band?.label || "--")}</strong>
          <em>${escapeHtml(sentiment?.signal || "中性觀察")} · ${escapeHtml(posture.label)}</em>
        </div>
        <div class="us-market-sentiment-meter is-${escapeHtml(posture.tone)}">
          <small>風險溫度</small>
          <b>${escapeHtml(riskValue)}</b>
          <i style="--sentiment-risk: ${escapeHtml(riskWidth)}"></i>
        </div>
      </div>
      <div class="us-market-sentiment-metrics">
        ${metrics.map((item) => `
          <article class="is-${escapeHtml(item.tone)}">
            <span>${escapeHtml(item.label)}</span>
            <b>${escapeHtml(item.value)}</b>
            <small>${escapeHtml(item.note)}</small>
          </article>
        `).join("")}
      </div>
      <div class="us-market-sentiment-interpretation">
        <p>${escapeHtml(sentiment?.divergence || "市場情緒資料同步中。")} ${chartState.comparison ? `已選 ${selectedIndexes.length} 個主要指數，折線皆以起點 100 標準化。` : "單一主要指數以 K 線與成交量呈現。"}</p>
        <p>${escapeHtml(posture.action)}</p>
      </div>
      <div class="us-market-sentiment-rules">
        ${rules.map((item) => `
          <article class="is-${escapeHtml(item.tone)}">
            <b>${escapeHtml(item.label)}</b>
            <small>${escapeHtml(item.text)}</small>
          </article>
        `).join("")}
      </div>
    </div>
  `;
}
function renderUsVixSentimentSvg(vix) {
  const fullSeries = normalizeGlobalSeries(vix?.series || []);
  const zoomKey = vix?.symbol || "^VIX";
  const total = fullSeries.length;
  const minimum = Math.min(30, total);
  const savedVisible = usMajorIndexZoomCounts.get(zoomKey);
  const visible = Number.isFinite(savedVisible) ? Math.max(minimum, Math.min(savedVisible, total)) : Math.min(180, total);
  const panOffset = Math.max(0, Math.min(usMajorIndexPanOffsets.get(zoomKey) || 0, Math.max(total - visible, 0)));
  const end = total - panOffset;
  const series = fullSeries.slice(Math.max(0, end - visible), end);
  if (series.length < 2) {
    return '<div class="global-chart-empty">VIX 歷史資料不足，暫無法繪製市場情緒走勢。</div>';
  }
  const width = 920;
  const height = 430;
  const pad = { top: 28, right: 56, bottom: 44, left: 62 };
  const plotHeight = height - pad.top - pad.bottom;
  const plotWidth = width - pad.left - pad.right;
  const values = series.map((item) => item.value).filter(Number.isFinite);
  const min = Math.min(10, ...values);
  const max = Math.max(45, ...values);
  const span = max - min || 1;
  const xFor = (index) => pad.left + (index / Math.max(series.length - 1, 1)) * plotWidth;
  const yFor = (value) => pad.top + ((max - value) / span) * plotHeight;
  const points = series.map((item, index) => ({ x: xFor(index), y: yFor(item.value), value: item.value }));
  const path = buildPath(points);
  const area = `${path} L ${points.at(-1).x.toFixed(1)} ${height - pad.bottom} L ${points[0].x.toFixed(1)} ${height - pad.bottom} Z`;
  const thresholds = [15, 20, 30, 40].map((value) => {
    const y = yFor(value);
    return `
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" class="us-vix-threshold"></line>
      <text x="${width - pad.right + 8}" y="${(y + 4).toFixed(1)}" class="global-chart-date">${value}</text>
    `;
  }).join("");
  const bands = [
    { from: max, to: 40, cls: "panic" },
    { from: 40, to: 30, cls: "high" },
    { from: 30, to: 20, cls: "warning" },
    { from: 20, to: 15, cls: "normal" },
    { from: 15, to: min, cls: "calm" },
  ].map((band) => {
    const y1 = yFor(Math.min(Math.max(band.from, min), max));
    const y2 = yFor(Math.min(Math.max(band.to, min), max));
    return `<rect x="${pad.left}" y="${Math.min(y1, y2).toFixed(1)}" width="${plotWidth}" height="${Math.max(Math.abs(y2 - y1), 1).toFixed(1)}" class="us-vix-band is-${band.cls}"></rect>`;
  }).join("");
  const first = series[0];
  const last = series.at(-1);
  const zoneWidth = plotWidth / Math.max(series.length, 1);
  const hoverZones = series.map((item, index) => {
    const x = xFor(index);
    return `<rect class="us-index-hover-zone" x="${(x - zoneWidth / 2).toFixed(1)}" y="${pad.top}" width="${Math.max(zoneWidth, 8).toFixed(1)}" height="${plotHeight}" data-us-chart-mode="vix" data-x="${x.toFixed(1)}" data-y="${yFor(item.value).toFixed(1)}" data-date="${escapeHtml(item.date)}" data-vix="${item.value.toFixed(2)}"></rect>`;
  }).join("");
  return `
    <svg class="us-index-vix-chart us-vix-sentiment-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="VIX 指數市場情緒走勢圖">
      <rect x="0" y="0" width="${width}" height="${height}" rx="22" class="us-index-chart-bg"></rect>
      ${bands}
      ${thresholds}
      <path class="us-vix-area" d="${area}"></path>
      <path class="us-index-line-vix" d="${path}"></path>
      <text x="${pad.left}" y="${height - 16}" class="global-chart-date">${escapeHtml(first?.date || "")}</text>
      <text x="${width - pad.right}" y="${height - 16}" text-anchor="end" class="global-chart-date">${escapeHtml(last?.date || "")}</text>
      <text x="${pad.left}" y="${pad.top + 12}" class="global-chart-date">VIX 波動率指數，非成交量圖</text>
      <g class="us-index-hover-zones">${hoverZones}</g>
      <line class="chart-crosshair us-index-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" style="display:none"></line>
    </svg>
  `;
}
function renderUsIndexVixSvg(primary, vix) {
  if (primary?.symbol === "^VIX") return renderUsVixSentimentSvg(vix || primary);
  const fullCandles = normalizeGlobalOhlcvSeries(primary?.series || []);
  const zoomKey = primary?.symbol || "^GSPC";
  const total = fullCandles.length;
  const minimum = Math.min(30, total);
  const savedVisible = usMajorIndexZoomCounts.get(zoomKey);
  const visible = Number.isFinite(savedVisible) ? Math.max(minimum, Math.min(savedVisible, total)) : Math.min(140, total);
  const panOffset = Math.max(0, Math.min(usMajorIndexPanOffsets.get(zoomKey) || 0, Math.max(total - visible, 0)));
  const end = total - panOffset;
  const candles = fullCandles.slice(Math.max(0, end - visible), end);
  const vixSeries = normalizeGlobalSeries(vix?.series || []);
  if (candles.length < 2) {
    return '<div class="global-chart-empty">主要指數歷史資料不足，暫無法繪製比對圖。</div>';
  }
  const width = 920;
  const height = 500;
  const pad = { top: 28, right: 56, bottom: 42, left: 62 };
  const priceHeight = 320;
  const volumeTop = pad.top + priceHeight + 30;
  const volumeHeight = height - volumeTop - pad.bottom;
  const prices = candles.flatMap((item) => [item.open, item.high, item.low, item.close]).filter(Number.isFinite);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const plotWidth = width - pad.left - pad.right;
  const candleStep = plotWidth / Math.max(candles.length, 1);
  const candleWidth = Math.max(3, Math.min(10, candleStep * 0.58));
  const xFor = (index) => pad.left + candleStep * index + candleStep / 2;
  const yFor = (value) => pad.top + ((max - value) / span) * priceHeight;
  const maxVolume = Math.max(...candles.map((item) => item.volume || 0), 1);
  const volumeY = (value) => volumeTop + volumeHeight - ((value || 0) / maxVolume) * volumeHeight;
  const vixMap = new Map(vixSeries.map((item) => [item.date, item.value]));
  const alignedVix = candles
    .map((item, index) => ({ date: item.date, x: xFor(index), value: vixMap.get(item.date) }))
    .filter((item) => Number.isFinite(item.value));
  const vixValues = alignedVix.map((item) => item.value);
  const vixMin = Math.min(...vixValues);
  const vixMax = Math.max(...vixValues);
  const vixSpan = vixMax - vixMin || 1;
  const yVix = (value) => pad.top + ((vixMax - value) / vixSpan) * priceHeight;
  const vixPath = usMajorIndexShowVix && primary?.symbol !== "^VIX" && alignedVix.length >= 2
    ? buildPath(alignedVix.map((item) => ({ x: item.x, y: yVix(item.value), value: item.value })))
    : "";
  const grid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * priceHeight;
    const value = max - ratio * span;
    return `<line x1="${pad.left}" x2="${width - pad.right}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" class="us-index-grid"></line>
      <text x="${pad.left - 10}" y="${(y + 4).toFixed(1)}" text-anchor="end" class="global-chart-date">${value.toFixed(2)}</text>`;
  }).join("");
  const first = candles[0];
  const last = candles.at(-1);
  const candleHtml = candles.map((item, index) => {
    const x = xFor(index);
    const openY = yFor(item.open);
    const closeY = yFor(item.close);
    const highY = yFor(item.high);
    const lowY = yFor(item.low);
    const up = item.close >= item.open;
    const bodyY = Math.min(openY, closeY);
    const bodyHeight = Math.max(Math.abs(closeY - openY), 2);
    const volumeTopY = volumeY(item.volume);
    return `
      <g class="${up ? "is-up" : "is-down"}">
        <line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${highY.toFixed(1)}" y2="${lowY.toFixed(1)}" class="us-index-candle-wick"></line>
        <rect x="${(x - candleWidth / 2).toFixed(1)}" y="${bodyY.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${bodyHeight.toFixed(1)}" rx="1.5" class="us-index-candle-body"></rect>
        <rect x="${(x - candleWidth / 2).toFixed(1)}" y="${volumeTopY.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${Math.max(volumeTop + volumeHeight - volumeTopY, 1).toFixed(1)}" rx="1" class="us-index-volume-bar"></rect>
      </g>
    `;
  }).join("");
  const hoverZones = candles.map((item, index) => {
    const x = xFor(index);
    const vixValue = vixMap.get(item.date);
    return `<rect class="us-index-hover-zone" x="${(x - candleStep / 2).toFixed(1)}" y="${pad.top}" width="${Math.max(candleStep, 8).toFixed(1)}" height="${volumeTop + volumeHeight - pad.top}" data-us-chart-mode="index" data-x="${x.toFixed(1)}" data-price-y="${yFor(item.close).toFixed(1)}" data-vix-y="${Number.isFinite(vixValue) ? yVix(vixValue).toFixed(1) : ""}" data-date="${escapeHtml(item.date)}" data-open="${item.open.toFixed(2)}" data-high="${item.high.toFixed(2)}" data-low="${item.low.toFixed(2)}" data-close="${item.close.toFixed(2)}" data-volume="${formatGlobalVolume(item.volume)}" data-vix="${Number.isFinite(vixValue) ? vixValue.toFixed(2) : "--"}"></rect>`;
  }).join("");
  return `
    <svg class="us-index-vix-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(primary?.name || "主要指數")} 與 VIX 指數比對圖">
      <rect x="0" y="0" width="${width}" height="${height}" rx="22" class="us-index-chart-bg"></rect>
      ${grid}
      <line x1="${pad.left}" x2="${width - pad.right}" y1="${volumeTop - 14}" y2="${volumeTop - 14}" class="us-index-grid"></line>
      ${candleHtml}
      ${vixPath ? `<path class="us-index-line-vix" d="${vixPath}"></path>
        <text x="${width - pad.right}" y="${pad.top + 14}" text-anchor="end" class="global-chart-date">VIX 獨立刻度 ${vixMin.toFixed(1)} ~ ${vixMax.toFixed(1)}</text>` : ""}
      <text x="${pad.left}" y="${volumeTop - 20}" class="global-chart-date">成交量</text>
      <text x="${pad.left}" y="${height - 16}" class="global-chart-date">${escapeHtml(first?.date || "")}</text>
      <text x="${width - pad.right}" y="${height - 16}" text-anchor="end" class="global-chart-date">${escapeHtml(last?.date || "")}</text>
      <g class="us-index-hover-zones">${hoverZones}</g>
      <line class="chart-crosshair us-index-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${volumeTop + volumeHeight}" style="display:none"></line>
    </svg>
  `;
}
function getUsIndexLineColor(index) {
  return ["#45a6ff", "#32d59b", "#a97eff", "#ff8f5a"][index % 4];
}
function getUsIndexLineColorBySymbol(symbol, fallbackIndex = 0) {
  const index = ["^GSPC", "^DJI", "^IXIC", "^RUT"].indexOf(symbol);
  return getUsIndexLineColor(index >= 0 ? index : fallbackIndex);
}
function getUsMajorIndexSelection(majorItems = []) {
  const available = new Set(majorItems.map((item) => item.symbol));
  let selected = (usMajorIndexChartSymbols || []).filter((symbol) => available.has(symbol));
  if (!selected.length && available.has(usMajorIndexChartSymbol)) selected = [usMajorIndexChartSymbol];
  if (!selected.length && majorItems[0]?.symbol) selected = [majorItems[0].symbol];
  usMajorIndexChartSymbols = selected;
  usMajorIndexChartSymbol = selected[0] || "^GSPC";
  return selected;
}
function getUsMajorIndexCommonDateCount(indexes = []) {
  const seriesList = indexes
    .map((item) => normalizeGlobalSeries(item?.series || []))
    .filter((series) => series.length >= 2);
  if (!seriesList.length) return 0;
  const valueMaps = seriesList.map((series) => new Map(series.map((point) => [point.date, point.value])));
  return seriesList[0].filter((point) => valueMaps.every((map) => Number.isFinite(map.get(point.date)))).length;
}
function getUsMajorIndexChartState(selectedIndexes = []) {
  const comparison = selectedIndexes.length > 1;
  const primary = selectedIndexes[0];
  return {
    comparison,
    zoomKey: comparison ? "multi-index-vix" : primary?.symbol || "^GSPC",
    totalPoints: comparison
      ? getUsMajorIndexCommonDateCount(selectedIndexes)
      : normalizeGlobalOhlcvSeries(primary?.series || []).length,
    defaultVisible: comparison ? 160 : 140,
  };
}
function buildUsIndexVixAiAnalysis({ selectedIndexes = [], selected, vix, chartState, selectedReturns = [], strongestIndex, weakestIndex, indexReturn, vixReturn }) {
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const formatPct = (value) => Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
  const vixValue = parseMarketNumber(vix?.close);
  const vixDailyPct = parseMarketNumber(vix?.pct);
  const vixBand = getVixSentimentBand(vixValue);
  const vixRisk = Number.isFinite(vixValue)
    ? clamp(Math.round(((vixValue - 10) / 35) * 100), 0, 100)
    : 50;
  const selectedName = getUsBenchmarkDisplayName(selected || selectedIndexes[0] || {});
  const selectedReturnValues = selectedReturns.map((entry) => entry.value).filter(Number.isFinite);
  const averageReturn = selectedReturnValues.length
    ? selectedReturnValues.reduce((sum, value) => sum + value, 0) / selectedReturnValues.length
    : indexReturn;
  const spread = strongestIndex && weakestIndex
    ? Math.abs(strongestIndex.value - weakestIndex.value)
    : 0;
  const positiveCount = selectedReturnValues.filter((value) => value > 0).length;
  let trendPower = 50;
  let trendLabel = "中性震盪";
  let trendBody = "主要指數歷史資料不足，先以 VIX 與最新漲跌確認方向。";

  if (chartState.comparison) {
    trendPower = clamp(Math.round(50 + (Number.isFinite(averageReturn) ? averageReturn * 1.15 : 0) + (positiveCount - selectedReturnValues.length / 2) * 8 - Math.min(spread, 24) * 0.35), 0, 100);
    trendLabel = trendPower >= 66
      ? "同步偏多"
      : trendPower >= 54
        ? "輪動偏多"
        : trendPower <= 34
          ? "同步偏弱"
          : spread >= 12
            ? "分化輪動"
            : "區間比對";
    trendBody = strongestIndex
      ? `已選 ${selectedIndexes.length} 個指數，區間最強為 ${getUsBenchmarkDisplayName(strongestIndex.item)} ${formatPct(strongestIndex.value)}，最弱為 ${weakestIndex ? `${getUsBenchmarkDisplayName(weakestIndex.item)} ${formatPct(weakestIndex.value)}` : "--"}，強弱差 ${formatPct(spread)}。`
      : "已進入多指數比對，但共同日期資料不足，先觀察 VIX 是否同步升溫。";
  } else {
    const candles = normalizeGlobalOhlcvSeries(selected?.series || []);
    const closes = candles.map((point) => point.close).filter(Number.isFinite);
    const latest = closes.at(-1);
    const ma20 = technicalSma(closes, 20).at(-1);
    const ma60 = technicalSma(closes, 60).at(-1);
    const close20 = closes.at(-21);
    const return20 = Number.isFinite(latest) && Number.isFinite(close20) && close20
      ? ((latest - close20) / close20) * 100
      : null;
    const recentVolumes = candles.slice(-20).map((point) => point.volume).filter(Number.isFinite);
    const avgVolume20 = recentVolumes.length ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length : null;
    const latestVolume = candles.at(-1)?.volume;
    const volumeText = Number.isFinite(latestVolume) && Number.isFinite(avgVolume20) && avgVolume20
      ? latestVolume >= avgVolume20 * 1.22
        ? "量能放大"
        : latestVolume <= avgVolume20 * 0.78
          ? "量能收縮"
          : "量能接近均值"
      : "量能待確認";
    trendPower = 50
      + (Number.isFinite(latest) && Number.isFinite(ma20) ? (latest >= ma20 ? 14 : -14) : 0)
      + (Number.isFinite(ma20) && Number.isFinite(ma60) ? (ma20 >= ma60 ? 12 : -12) : 0)
      + (Number.isFinite(return20) ? clamp(return20 * 2.2, -18, 18) : 0)
      + (volumeText === "量能放大" && Number.isFinite(return20) ? (return20 >= 0 ? 5 : -5) : 0);
    trendPower = clamp(Math.round(trendPower), 0, 100);
    trendLabel = trendPower >= 68
      ? "上升趨勢"
      : trendPower >= 55
        ? "偏多整理"
        : trendPower <= 32
          ? "下降趨勢"
          : trendPower <= 45
            ? "偏弱震盪"
            : "中性震盪";
    trendBody = `${selectedName} 近20日 ${formatPct(return20)}，${Number.isFinite(latest) && Number.isFinite(ma20) && latest >= ma20 ? "收盤站上20日線" : "收盤低於20日線"}，20/60日均線${Number.isFinite(ma20) && Number.isFinite(ma60) && ma20 >= ma60 ? "維持多頭排列" : "尚未形成多頭排列"}，${volumeText}。`;
  }

  const representativeReturn = Number.isFinite(averageReturn) ? averageReturn : indexReturn;
  let divergenceLabel = "方向待確認";
  let divergenceText = "指數與 VIX 未形成足夠明確的方向組合。";
  let riskAdjustment = 0;
  if (Number.isFinite(representativeReturn) && Number.isFinite(vixReturn)) {
    if (representativeReturn > 0 && vixReturn < 0) {
      divergenceLabel = "偏多確認";
      divergenceText = "指數走強且 VIX 回落，風險偏好較健康。";
      riskAdjustment -= 10;
    } else if (representativeReturn < 0 && vixReturn > 0) {
      divergenceLabel = "避險升溫";
      divergenceText = "指數轉弱且 VIX 上升，短線需提高防守。";
      riskAdjustment += 18;
    } else if (representativeReturn > 0 && vixReturn > 0) {
      divergenceLabel = "上漲背離";
      divergenceText = "指數上漲但 VIX 也升高，代表追價同時伴隨事件風險。";
      riskAdjustment += 10;
    } else if (representativeReturn < 0 && vixReturn < 0) {
      divergenceLabel = "恐慌降溫";
      divergenceText = "指數偏弱但 VIX 回落，賣壓可能在收斂，仍需等價格止穩。";
      riskAdjustment -= 2;
    }
  }
  const riskScore = clamp(Math.round(vixRisk + riskAdjustment + (Number.isFinite(vixDailyPct) ? clamp(vixDailyPct * 1.2, -8, 12) : 0) + (chartState.comparison ? Math.min(spread, 25) * 0.35 : 0)), 0, 100);
  const riskLabel = riskScore >= 72
    ? "高風險"
    : riskScore >= 56
      ? "風險偏高"
      : riskScore <= 34
        ? "風險偏低"
        : "中性風險";
  const riskTone = riskScore >= 56 ? "negative" : riskScore <= 36 ? "positive" : "watch";
  const trendTone = trendPower >= 55 ? "positive" : trendPower <= 45 ? "negative" : "watch";
  const bias = trendPower - riskScore;
  let bullish = clamp(Math.round(35 + bias * 0.34 + (Number.isFinite(representativeReturn) && representativeReturn > 0 ? 5 : -2)), 14, 72);
  let bearish = clamp(Math.round(27 - bias * 0.3 + (riskScore >= 65 ? 8 : 0)), 12, 70);
  let neutral = Math.max(10, 100 - bullish - bearish);
  const total = bullish + neutral + bearish;
  bullish = Math.round((bullish / total) * 100);
  bearish = Math.round((bearish / total) * 100);
  neutral = Math.max(0, 100 - bullish - bearish);
  const forecastLabel = bullish >= bearish + 12
    ? "偏多延續"
    : bearish >= bullish + 12
      ? "修正風險升高"
      : "震盪整理";
  const forecastTone = bullish > bearish ? "positive" : bearish > bullish ? "negative" : "watch";
  const confidence = [
    selectedIndexes.length > 0,
    selectedReturnValues.length || Number.isFinite(indexReturn),
    Number.isFinite(vixValue),
    Number.isFinite(vixReturn),
    chartState.totalPoints >= 60,
  ].filter(Boolean).length;

  return {
    headline: chartState.comparison ? `${selectedIndexes.length} 指數比對 · ${forecastLabel}` : `${selectedName} · ${forecastLabel}`,
    confidence: `${confidence}/5`,
    modules: [
      {
        title: "AI 趨勢比對",
        label: trendLabel,
        tone: trendTone,
        score: `${trendPower}/100`,
        body: trendBody,
      },
      {
        title: "VIX 風險背離",
        label: `${riskLabel} · ${divergenceLabel}`,
        tone: riskTone,
        score: `${riskScore}/100`,
        body: `${vixBand.label}，${divergenceText} ${vixBand.text}`,
      },
      {
        title: "情境預測",
        label: forecastLabel,
        tone: forecastTone,
        score: `${bullish}/${neutral}/${bearish}`,
        body: `未來 3-5 個交易日情境推估：多方 ${bullish}%、震盪 ${neutral}%、空方 ${bearish}%。此為內建規則模型，用於比對風險，不保證價格。`,
      },
    ],
  };
}
function renderUsMultiIndexVixSvg(selectedIndexes = [], vix) {
  const selectedSeries = selectedIndexes
    .map((item) => ({
      item,
      series: normalizeGlobalSeries(item?.series || []),
    }))
    .filter((entry) => entry.series.length >= 2);
  if (!selectedSeries.length) {
    return '<div class="global-chart-empty">主要指數歷史資料不足，暫無法繪製複數比對圖。</div>';
  }
  const primaryDates = selectedSeries[0].series.map((point) => point.date);
  const valueMaps = selectedSeries.map((entry) => new Map(entry.series.map((point) => [point.date, point.value])));
  const vixSeries = normalizeGlobalSeries(vix?.series || []);
  const vixMap = new Map(vixSeries.map((point) => [point.date, point.value]));
  const allDates = primaryDates.filter((date) => valueMaps.every((map) => Number.isFinite(map.get(date))));
  const total = allDates.length;
  if (total < 2) {
    return '<div class="global-chart-empty">主要指數共同日期資料不足，暫無法繪製複數比對圖。</div>';
  }
  const zoomKey = "multi-index-vix";
  const minimum = Math.min(30, total);
  const savedVisible = usMajorIndexZoomCounts.get(zoomKey);
  const visible = Number.isFinite(savedVisible) ? Math.max(minimum, Math.min(savedVisible, total)) : Math.min(160, total);
  const panOffset = Math.max(0, Math.min(usMajorIndexPanOffsets.get(zoomKey) || 0, Math.max(total - visible, 0)));
  const end = total - panOffset;
  const dates = allDates.slice(Math.max(0, end - visible), end);
  const width = 920;
  const height = 470;
  const pad = { top: 32, right: 58, bottom: 46, left: 62 };
  const plotHeight = height - pad.top - pad.bottom;
  const plotWidth = width - pad.left - pad.right;
  const lineModels = selectedSeries.map((entry, index) => {
    const base = valueMaps[index].get(dates[0]) || 1;
    const points = dates.map((date) => ({
      date,
      raw: valueMaps[index].get(date),
      value: (valueMaps[index].get(date) / base) * 100,
    }));
    return {
      item: entry.item,
      color: getUsIndexLineColorBySymbol(entry.item?.symbol, index),
      points,
      delta: points.at(-1).value - 100,
    };
  });
  const vixValues = dates.map((date) => vixMap.get(date)).filter(Number.isFinite);
  const normalizedValues = lineModels.flatMap((model) => model.points.map((point) => point.value));
  const min = Math.min(...normalizedValues, 98);
  const max = Math.max(...normalizedValues, 102);
  const span = max - min || 1;
  const xFor = (index) => pad.left + (index / Math.max(dates.length - 1, 1)) * plotWidth;
  const yFor = (value) => pad.top + ((max - value) / span) * plotHeight;
  const vixMin = Math.min(...vixValues);
  const vixMax = Math.max(...vixValues);
  const vixSpan = vixMax - vixMin || 1;
  const yVix = (value) => pad.top + ((vixMax - value) / vixSpan) * plotHeight;
  const grid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * plotHeight;
    const value = max - ratio * span;
    return `<line x1="${pad.left}" x2="${width - pad.right}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" class="us-index-grid"></line>
      <text x="${pad.left - 10}" y="${(y + 4).toFixed(1)}" text-anchor="end" class="global-chart-date">${value.toFixed(1)}</text>`;
  }).join("");
  const paths = lineModels.map((model) => {
    const points = model.points.map((point, index) => ({ x: xFor(index), y: yFor(point.value), value: point.value }));
    return `<path class="us-index-line-primary us-index-line-multi" style="stroke:${model.color}" d="${buildPath(points)}"></path>
      <circle cx="${points.at(-1).x.toFixed(1)}" cy="${points.at(-1).y.toFixed(1)}" r="4" fill="${model.color}"></circle>`;
  }).join("");
  const vixPath = usMajorIndexShowVix && vixValues.length >= 2
    ? buildPath(dates.map((date, index) => ({ x: xFor(index), y: yVix(vixMap.get(date)), value: vixMap.get(date) })).filter((point) => Number.isFinite(point.y)))
    : "";
  const zoneWidth = plotWidth / Math.max(dates.length, 1);
  const hoverZones = dates.map((date, index) => {
    const payload = lineModels.map((model) => ({
      symbol: model.item.symbol,
      name: getUsBenchmarkDisplayName(model.item),
      value: model.points[index].value.toFixed(2),
      raw: model.points[index].raw.toFixed(2),
      delta: (model.points[index].value - 100).toFixed(2),
    }));
    const vixValue = vixMap.get(date);
    return `<rect class="us-index-hover-zone" x="${(xFor(index) - zoneWidth / 2).toFixed(1)}" y="${pad.top}" width="${Math.max(zoneWidth, 8).toFixed(1)}" height="${plotHeight}" data-us-chart-mode="multi-index" data-x="${xFor(index).toFixed(1)}" data-date="${escapeHtml(date)}" data-lines="${escapeHtml(JSON.stringify(payload))}" data-vix="${Number.isFinite(vixValue) ? vixValue.toFixed(2) : "--"}"></rect>`;
  }).join("");
  const first = dates[0];
  const last = dates.at(-1);
  return `
    <svg class="us-index-vix-chart us-index-vix-multi-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="美股主要指數與 VIX 複數比對圖">
      <rect x="0" y="0" width="${width}" height="${height}" rx="22" class="us-index-chart-bg"></rect>
      ${grid}
      <line x1="${pad.left}" y1="${yFor(100).toFixed(1)}" x2="${width - pad.right}" y2="${yFor(100).toFixed(1)}" class="us-index-base-line"></line>
      ${paths}
      ${vixPath ? `<path class="us-index-line-vix" d="${vixPath}"></path>
        <text x="${width - pad.right}" y="${pad.top + 14}" text-anchor="end" class="global-chart-date">VIX 獨立刻度 ${vixMin.toFixed(1)} ~ ${vixMax.toFixed(1)}</text>` : ""}
      <text x="${pad.left}" y="${height - 16}" class="global-chart-date">${escapeHtml(first || "")}</text>
      <text x="${width - pad.right}" y="${height - 16}" text-anchor="end" class="global-chart-date">${escapeHtml(last || "")}</text>
      <text x="${pad.left}" y="${pad.top + 14}" class="global-chart-date">基準 100，相對位置越高代表區間表現越強</text>
      <g class="us-index-hover-zones">${hoverZones}</g>
      <line class="chart-crosshair us-index-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" style="display:none"></line>
    </svg>
  `;
}
function renderUsMajorIndexVixCard(payload) {
  if (payload?.category !== "us-stocks") return "";
  const items = payload.items || [];
  const majorSymbols = ["^GSPC", "^DJI", "^IXIC", "^RUT"];
  const majorItems = majorSymbols.map((symbol) => items.find((item) => item.symbol === symbol)).filter(Boolean);
  const vix = items.find((item) => item.symbol === "^VIX");
  if (majorItems.length < 2) return "";
  const selectedSymbols = getUsMajorIndexSelection(majorItems);
  const selectedIndexes = selectedSymbols.map((symbol) => majorItems.find((item) => item.symbol === symbol)).filter(Boolean);
  const selected = selectedIndexes[0] || majorItems[0];
  const chartState = getUsMajorIndexChartState(selectedIndexes);
  const totalPoints = chartState.totalPoints;
  const zoomKey = chartState.zoomKey;
  const minimumVisible = Math.min(30, totalPoints);
  const savedVisible = usMajorIndexZoomCounts.get(zoomKey);
  const visibleCount = Number.isFinite(savedVisible) ? Math.max(minimumVisible, Math.min(savedVisible, totalPoints)) : Math.min(chartState.defaultVisible, totalPoints);
  const panOffset = Math.max(0, Math.min(usMajorIndexPanOffsets.get(zoomKey) || 0, Math.max(totalPoints - visibleCount, 0)));
  const selectedSeries = normalizeGlobalSeries(selected.series || []);
  const vixSeries = normalizeGlobalSeries(vix?.series || []);
  const indexReturn = selectedSeries.length >= 2
    ? ((selectedSeries.at(-1).value - selectedSeries[0].value) / selectedSeries[0].value) * 100
    : null;
  const vixReturn = vixSeries.length >= 2
    ? ((vixSeries.at(-1).value - vixSeries[0].value) / vixSeries[0].value) * 100
    : null;
  const vixBand = getVixSentimentBand(parseMarketNumber(vix?.close));
  const sentiment = buildUsMarketSentiment(selected, vix, indexReturn, vixReturn);
  const riskText = Number.isFinite(vixReturn) && Number.isFinite(indexReturn)
    ? vixReturn > 8 && indexReturn < 0
      ? "VIX 上升且指數偏弱，市場風險偏好轉保守。"
      : vixReturn < -8 && indexReturn > 0
        ? "VIX 回落且指數走強，風險偏好改善。"
        : "指數與 VIX 未出現明顯背離，先以量能與類股輪動確認。"
    : "VIX 或指數歷史資料不足，先以最新報價與單項走勢判斷。";
  const selectedReturns = selectedIndexes
    .map((item) => {
      const series = normalizeGlobalSeries(item.series || []);
      const first = series[0]?.value;
      const last = series.at(-1)?.value;
      const value = Number.isFinite(first) && Number.isFinite(last) && first ? ((last - first) / first) * 100 : null;
      return { item, value };
    })
    .filter((entry) => Number.isFinite(entry.value))
    .sort((a, b) => b.value - a.value);
  const strongestIndex = selectedReturns[0];
  const weakestIndex = selectedReturns.at(-1);
  const aiAnalysis = buildUsIndexVixAiAnalysis({
    selectedIndexes,
    selected,
    vix,
    chartState,
    selectedReturns,
    strongestIndex,
    weakestIndex,
    indexReturn,
    vixReturn,
  });
  return `
    <section class="section" id="us-major-index-vix">
      <article class="panel-card us-index-vix-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">Major indexes × VIX</p>
            <h3>${chartState.comparison ? "美股主要指數 × VIX 複數比對" : `${escapeHtml(getUsBenchmarkDisplayName(selected))} K 線走勢 × VIX`}</h3>
          </div>
          <span class="chip chip-blue">${chartState.comparison ? "多指數 / Base 100 / VIX" : "K 線 / 成交量 / VIX"}</span>
        </div>
        <div class="us-index-switcher">
          ${majorItems.map((item) => `
            <button class="range-button ${selectedSymbols.includes(item.symbol) ? "is-active" : ""}" type="button" data-us-major-index="${escapeHtml(item.symbol)}" aria-pressed="${selectedSymbols.includes(item.symbol) ? "true" : "false"}">
              ${escapeHtml(getUsBenchmarkDisplayName(item))}
            </button>
          `).join("")}
          <button class="range-button ${selectedSymbols.length === majorItems.length ? "is-active" : ""}" type="button" data-us-major-index-all="1">
            全選
          </button>
          <button class="range-button ${usMajorIndexShowVix ? "is-active" : ""}" type="button" data-us-vix-toggle="1">
            ${usMajorIndexShowVix ? "隱藏 VIX 比對" : "顯示 VIX 比對"}
          </button>
        </div>
        <div class="sector-chart-zoom us-index-chart-zoom" aria-label="美股走勢圖縮放控制">
          <button type="button" data-us-index-zoom="in" ${visibleCount <= minimumVisible ? "disabled" : ""}>＋ 放大</button>
          <button type="button" data-us-index-zoom="out" ${visibleCount >= totalPoints ? "disabled" : ""}>－ 縮小</button>
          <button type="button" data-us-index-zoom="reset" ${visibleCount >= totalPoints ? "disabled" : ""}>重設</button>
          <button type="button" data-us-index-pan="older" ${panOffset >= totalPoints - visibleCount ? "disabled" : ""}>← 往前</button>
          <button type="button" data-us-index-pan="newer" ${panOffset <= 0 ? "disabled" : ""}>往後 →</button>
          <span>顯示 ${visibleCount} / ${totalPoints} 根</span>
        </div>
        <div class="us-index-vix-chart-wrap">
          ${chartState.comparison ? renderUsMultiIndexVixSvg(selectedIndexes, vix) : renderUsIndexVixSvg(selected, vix)}
          <div class="sector-sync-tooltip us-index-tooltip" hidden></div>
        </div>
        <div class="us-index-vix-legend">
          ${chartState.comparison
            ? selectedIndexes.map((item, index) => `<span><i style="background:${getUsIndexLineColorBySymbol(item.symbol, index)}"></i>${escapeHtml(getUsBenchmarkDisplayName(item))} ${escapeHtml(item.pct || "--")}</span>`).join("")
            : `<span><i class="primary"></i>${escapeHtml(getUsBenchmarkDisplayName(selected))} K 線 ${escapeHtml(selected?.pct || "--")}</span>`}
          ${usMajorIndexShowVix ? `<span><i class="vix"></i>VIX 比對線 ${escapeHtml(vix?.pct || "--")}</span>` : ""}
        </div>
        <div class="global-summary-grid us-index-vix-stats">
          <span><b>${selectedIndexes.length}</b><small>已選主要指數</small></span>
          <span><b>${escapeHtml(strongestIndex ? getUsBenchmarkDisplayName(strongestIndex.item) : "--")}</b><small>區間最強 ${strongestIndex ? `${strongestIndex.value >= 0 ? "+" : ""}${strongestIndex.value.toFixed(2)}%` : "--"}</small></span>
          <span><b>${escapeHtml(weakestIndex ? getUsBenchmarkDisplayName(weakestIndex.item) : "--")}</b><small>區間最弱 ${weakestIndex ? `${weakestIndex.value >= 0 ? "+" : ""}${weakestIndex.value.toFixed(2)}%` : "--"}</small></span>
          <span><b>${formatGlobalValue(vix?.close)}</b><small>VIX 最新</small></span>
          <span><b>${escapeHtml(sentiment.band.label)}</b><small>VIX 區間</small></span>
          <span><b>${escapeHtml(sentiment.signal)}</b><small>比對訊號</small></span>
        </div>
        <div class="us-index-ai-analysis">
          <div class="us-index-ai-head">
            <div>
              <span>Built-in AI comparison</span>
              <strong>內建 AI 比對分析</strong>
            </div>
            <small>${escapeHtml(aiAnalysis.headline)} · 信心 ${escapeHtml(aiAnalysis.confidence)}</small>
          </div>
          <div class="us-ai-evaluation-grid us-index-ai-grid">
            ${aiAnalysis.modules.map((module) => `
              <section class="us-ai-evaluation-card is-${escapeHtml(module.tone)}">
                <span>${escapeHtml(module.title)}</span>
                <strong>${escapeHtml(module.label)}</strong>
                <b>${escapeHtml(module.score)}</b>
                <p>${escapeHtml(module.body)}</p>
              </section>
            `).join("")}
          </div>
        </div>
        ${renderUsMarketSentimentValueCard({
          sentiment,
          vix,
          selected,
          selectedIndexes,
          chartState,
          indexReturn,
          vixReturn,
        })}
        <p class="global-insight">${escapeHtml(riskText)}</p>
      </article>
    </section>
  `;
}
function bindUsMajorIndexVixCard(payload) {
  const card = document.getElementById("us-major-index-vix");
  if (!card) return;
  const items = payload?.items || [];
  const majorItems = ["^GSPC", "^DJI", "^IXIC", "^RUT"].map((symbol) => items.find((item) => item.symbol === symbol)).filter(Boolean);
  const selectedSymbols = getUsMajorIndexSelection(majorItems);
  const selectedItems = selectedSymbols.map((symbol) => majorItems.find((item) => item.symbol === symbol)).filter(Boolean);
  const chartState = getUsMajorIndexChartState(selectedItems);
  const totalPoints = chartState.totalPoints;
  const zoomKey = chartState.zoomKey;
  const getItemsBySymbols = (symbols) => symbols.map((symbol) => majorItems.find((item) => item.symbol === symbol)).filter(Boolean);
  const rerender = () => {
    const replacement = renderUsMajorIndexVixCard(payload);
    if (replacement) {
      card.outerHTML = replacement;
      bindUsMajorIndexVixCard(payload);
    }
  };
  card.querySelectorAll("[data-us-major-index]").forEach((button) => {
    button.addEventListener("click", (event) => {
      const symbol = button.dataset.usMajorIndex || "";
      const current = new Set(getUsMajorIndexSelection(majorItems));
      const additiveClick = event.ctrlKey || event.metaKey || event.shiftKey;
      if (symbol && current.size === 1 && !current.has(symbol) && !additiveClick) {
        current.clear();
        current.add(symbol);
      } else if (current.has(symbol) && current.size > 1) {
        current.delete(symbol);
      } else if (symbol) {
        current.add(symbol);
      }
      usMajorIndexChartSymbols = majorItems.map((item) => item.symbol).filter((itemSymbol) => current.has(itemSymbol));
      usMajorIndexChartSymbol = usMajorIndexChartSymbols[0] || "^GSPC";
      usMajorIndexPanOffsets.set(getUsMajorIndexChartState(getItemsBySymbols(usMajorIndexChartSymbols)).zoomKey, 0);
      rerender();
    });
  });
  card.querySelector("[data-us-major-index-all]")?.addEventListener("click", () => {
    const allSymbols = majorItems.map((item) => item.symbol);
    usMajorIndexChartSymbols = selectedSymbols.length === allSymbols.length ? [allSymbols[0]] : allSymbols;
    usMajorIndexChartSymbol = usMajorIndexChartSymbols[0] || "^GSPC";
    usMajorIndexPanOffsets.set(getUsMajorIndexChartState(getItemsBySymbols(usMajorIndexChartSymbols)).zoomKey, 0);
    rerender();
  });
  card.querySelector("[data-us-vix-toggle]")?.addEventListener("click", () => {
    usMajorIndexShowVix = !usMajorIndexShowVix;
    rerender();
  });
  const updateZoom = (direction) => {
    const minimum = Math.min(30, totalPoints);
    const current = usMajorIndexZoomCounts.get(zoomKey) || Math.min(chartState.defaultVisible, totalPoints);
    let next = current;
    if (direction === "in") next = Math.max(minimum, Math.floor(current * 0.68));
    if (direction === "out") next = Math.min(totalPoints, Math.ceil(current / 0.68));
    if (direction === "reset") next = totalPoints;
    if (next === current) return;
    usMajorIndexZoomCounts.set(zoomKey, next);
    usMajorIndexPanOffsets.set(zoomKey, 0);
    rerender();
  };
  const updatePan = (direction) => {
    const currentVisible = usMajorIndexZoomCounts.get(zoomKey) || Math.min(chartState.defaultVisible, totalPoints);
    const visible = Math.min(currentVisible, totalPoints);
    const current = usMajorIndexPanOffsets.get(zoomKey) || 0;
    const maxOffset = Math.max(totalPoints - visible, 0);
    const step = Math.max(1, Math.round(visible * 0.35));
    const next = direction === "older"
      ? Math.min(maxOffset, current + step)
      : Math.max(0, current - step);
    if (next === current) return;
    usMajorIndexPanOffsets.set(zoomKey, next);
    rerender();
  };
  card.querySelectorAll("[data-us-index-zoom]").forEach((button) => {
    button.addEventListener("click", () => updateZoom(button.dataset.usIndexZoom));
  });
  card.querySelectorAll("[data-us-index-pan]").forEach((button) => {
    button.addEventListener("click", () => updatePan(button.dataset.usIndexPan));
  });
  const frame = card.querySelector(".us-index-vix-chart-wrap");
  frame?.addEventListener("wheel", (event) => {
    event.preventDefault();
    updateZoom(event.deltaY < 0 ? "in" : "out");
  }, { passive: false });
  bindHorizontalChartPan(frame, updatePan);
  bindUsIndexChartHover(card);
}
function bindUsIndexChartHover(card) {
  const frame = card.querySelector(".us-index-vix-chart-wrap");
  const tooltip = card.querySelector(".us-index-tooltip");
  const crosshair = card.querySelector(".us-index-crosshair");
  const zones = card.querySelectorAll(".us-index-hover-zone");
  if (!frame || !tooltip || !zones.length) return;
  const hide = () => {
    tooltip.hidden = true;
    if (crosshair) crosshair.style.display = "none";
  };
  const positionTooltip = (zone) => {
    const frameRect = frame.getBoundingClientRect();
    const zoneRect = zone.getBoundingClientRect();
    const tooltipWidth = tooltip.offsetWidth || 240;
    const tooltipHeight = tooltip.offsetHeight || 220;
    const cursorLeft = zoneRect.left - frameRect.left + zoneRect.width / 2;
    let left = cursorLeft + 14;
    if (left + tooltipWidth > frameRect.width - 6) left = cursorLeft - tooltipWidth - 14;
    left = Math.max(6, Math.min(left, frameRect.width - tooltipWidth - 6));
    let top = zoneRect.top - frameRect.top + 12;
    top = Math.max(6, Math.min(top, frameRect.height - tooltipHeight - 6));
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
    tooltip.style.transform = "none";
  };
  zones.forEach((zone) => {
    zone.addEventListener("mouseenter", () => {
      tooltip.hidden = false;
      if (zone.dataset.usChartMode === "multi-index") {
        let lines = [];
        try {
          lines = JSON.parse(zone.dataset.lines || "[]");
        } catch (error) {
          lines = [];
        }
        const vixValue = parseMarketNumber(zone.dataset.vix);
        const band = getVixSentimentBand(vixValue);
        tooltip.innerHTML = `
          <strong>${escapeHtml(zone.dataset.date || "--")}</strong>
          ${lines.map((line) => `
            <span>${escapeHtml(line.name || line.symbol || "--")}：<strong>${escapeHtml(line.value || "--")}</strong>（原值 ${escapeHtml(line.raw || "--")} / ${Number.parseFloat(line.delta) >= 0 ? "+" : ""}${escapeHtml(line.delta || "--")}）</span>
          `).join("")}
          <span class="chart-tooltip-divider">VIX：<strong>${escapeHtml(zone.dataset.vix || "--")}</strong> · ${escapeHtml(band.label)}</span>
        `;
      } else if (zone.dataset.usChartMode === "vix") {
        const value = parseMarketNumber(zone.dataset.vix);
        const band = getVixSentimentBand(value);
        tooltip.innerHTML = `
          <strong>${escapeHtml(zone.dataset.date || "--")}</strong>
          <span>VIX：<strong>${escapeHtml(zone.dataset.vix || "--")}</strong></span>
          <span>區間：<strong>${escapeHtml(band.label)}</strong></span>
          <span>${escapeHtml(band.text)}</span>
        `;
      } else {
        const vixValue = parseMarketNumber(zone.dataset.vix);
        const band = getVixSentimentBand(vixValue);
        const riskTemperature = Number.isFinite(vixValue)
          ? Math.max(0, Math.min(100, Math.round(((vixValue - 10) / 35) * 100)))
          : null;
        tooltip.innerHTML = `
          <strong>${escapeHtml(zone.dataset.date || "--")}</strong>
          <span>開盤：<strong>${escapeHtml(zone.dataset.open || "--")}</strong></span>
          <span>最高：<strong>${escapeHtml(zone.dataset.high || "--")}</strong></span>
          <span>最低：<strong>${escapeHtml(zone.dataset.low || "--")}</strong></span>
          <span>收盤：<strong>${escapeHtml(zone.dataset.close || "--")}</strong></span>
          <span>成交量：<strong>${escapeHtml(zone.dataset.volume || "--")}</strong></span>
          <span class="chart-tooltip-divider">VIX：<strong>${escapeHtml(zone.dataset.vix || "--")}</strong></span>
          <span>市場情緒：<strong>${escapeHtml(band.label)}</strong></span>
          <span>風險溫度：<strong>${riskTemperature ?? "--"}/100</strong></span>
        `;
      }
      positionTooltip(zone);
      if (crosshair) {
        const x = zone.dataset.x || "0";
        crosshair.setAttribute("x1", x);
        crosshair.setAttribute("x2", x);
        crosshair.style.display = "block";
        crosshair.style.opacity = "1";
      }
    });
    zone.addEventListener("mousemove", () => positionTooltip(zone));
    zone.addEventListener("mouseleave", hide);
  });
  frame.addEventListener("mouseleave", hide);
}
function buildUsSectorComparisonModel(benchmark, sector) {
  const benchmarkSeries = normalizeGlobalSeries(benchmark?.series || []);
  const sectorSeries = (sector?.series || [])
    .map((item) => ({
      date: item.date || item.time || "",
      value: parseMarketNumber(item.close),
      volume: parseMarketNumber(item.volumeValue ?? item.volume),
      raw: item,
    }))
    .filter((item) => item.date && Number.isFinite(item.value));
  const benchmarkMap = new Map(benchmarkSeries.map((item) => [item.date, item.value]));
  const aligned = sectorSeries
    .filter((item) => benchmarkMap.has(item.date))
    .map((item) => ({
      date: item.date,
      benchmark: benchmarkMap.get(item.date),
      sector: item.value,
      sectorVolume: item.volume,
    }))
    .filter((item) => Number.isFinite(item.benchmark) && Number.isFinite(item.sector));
  const sliced = aligned.slice(-180);
  if (sliced.length < 2) return [];
  const baseBenchmark = sliced[0].benchmark || 1;
  const baseSector = sliced[0].sector || 1;
  return sliced.map((item) => ({
    date: item.date,
    benchmark: (item.benchmark / baseBenchmark) * 100,
    sector: (item.sector / baseSector) * 100,
    alpha: (item.sector / baseSector) * 100 - (item.benchmark / baseBenchmark) * 100,
    benchmarkRaw: item.benchmark,
    sectorRaw: item.sector,
    sectorVolume: item.sectorVolume ?? 0,
  }));
}
function buildUsSectorComparisonAnalysis(aligned = [], benchmark = {}, sector = {}) {
  const first = aligned[0];
  const last = aligned.at(-1);
  if (!first || !last) {
    return {
      alpha: null,
      alpha20: null,
      slope: null,
      leadDays20: 0,
      signal: "共同資料不足，暫以單一走勢判斷。",
      stance: "觀察",
      tone: "neutral",
      bullets: ["等待共同歷史資料補齊後，再判斷相對強弱。"],
    };
  }
  const alpha = last.alpha;
  const recent = aligned.slice(-20);
  const first20 = recent[0] || first;
  const alpha20 = last.alpha - first20.alpha;
  const leadDays20 = recent.filter((item) => item.alpha > 0).length;
  const slope = recent.length >= 2 ? (recent.at(-1).alpha - recent[0].alpha) / Math.max(recent.length - 1, 1) : 0;
  let stance = "觀察";
  let tone = "neutral";
  let signal = "類股與大盤接近同步，等待量能或消息面催化。";
  if (alpha > 3 && alpha20 > 0) {
    stance = "相對強勢";
    tone = "positive";
    signal = `${sector.name || "此類股"}同時領先${benchmark.name || "大盤"}且近20日差值擴大，資金偏向集中。`;
  } else if (alpha > 3 && alpha20 <= 0) {
    stance = "高位鈍化";
    tone = "watch";
    signal = "類股仍領先大盤，但近20日相對優勢收斂，需留意追價效率下降。";
  } else if (alpha < -3 && alpha20 < 0) {
    stance = "相對弱勢";
    tone = "negative";
    signal = `${sector.name || "此類股"}落後大盤且差值擴大，短線資金動能偏弱。`;
  } else if (alpha < -3 && alpha20 >= 0) {
    stance = "落後修復";
    tone = "watch";
    signal = "類股仍落後大盤，但近20日差值改善，可觀察是否形成補漲或跌深反彈。";
  }
  const bullets = [
    `近20日領先天數 ${leadDays20}/20，代表資金相對偏好的穩定度。`,
    `相對強弱斜率 ${slope >= 0 ? "+" : ""}${slope.toFixed(2)}，${slope > 0 ? "短線差值正在擴大" : slope < 0 ? "短線差值正在收斂" : "短線差值持平"}。`,
    alpha > 0
      ? "若大盤同步走強，領先類股可作為多方主線觀察。"
      : "若大盤轉弱且類股持續落後，應降低追價與集中曝險。",
  ];
  return { alpha, alpha20, slope, leadDays20, signal, stance, tone, bullets };
}
function getUsBenchmarkDisplayName(item = {}) {
  const names = {
    "^GSPC": "標普500",
    "^DJI": "道瓊工業",
    "^IXIC": "那斯達克綜合",
    "^RUT": "羅素2000",
  };
  return names[item.symbol] || item.name || item.symbol || "大盤指數";
}
function getUsSectorDisplayName(item = {}) {
  const names = {
    "^SP500-45": "科技",
    "^SP500-40": "金融",
    "^SP500-35": "醫療保健",
    "^SP500-25": "非必需消費",
    "^SP500-50": "通訊服務",
    "^SP500-20": "工業",
    "^SP500-30": "必需消費",
    "^SP500-10": "能源",
    "^SP500-15": "原物料",
    "^SP500-55": "公用事業",
    "^SP500-60": "不動產",
    "^SOX": "半導體",
    "^DJUSTC": "美國科技產業",
    "^DJUSFN": "美國金融產業",
    "^DJUSHC": "美國醫療產業",
    "^DJUSEN": "美國能源產業",
    "^DJUSRE": "美國不動產產業",
  };
  return names[item.symbol] || String(item.name || item.symbol || "類股指數")
    .replace("S&P 500 ", "")
    .replace("Dow Jones U.S. ", "");
}
function getUsSectorOptionsForBenchmark(items = [], benchmarkSymbol = "^GSPC") {
  const usableSectors = items.filter((item) => (
    item.group === "美股類股指數"
    && !item.error
    && normalizeGlobalSeries(item.series || []).length >= 2
  ));
  const sectorBySymbol = new Map(usableSectors.map((item) => [item.symbol, item]));
  const mappedSymbols = US_MAJOR_INDEX_SECTOR_SYMBOLS[benchmarkSymbol] || US_SP500_SECTOR_SYMBOLS;
  const mappedSectors = mappedSymbols
    .map((symbol) => sectorBySymbol.get(symbol))
    .filter(Boolean);
  return mappedSectors.length ? mappedSectors : usableSectors;
}
function renderUsSectorComparisonSvg(benchmark, sector, analysis = null) {
  const aligned = buildUsSectorComparisonModel(benchmark, sector);
  if (aligned.length < 2) {
    return '<div class="global-chart-empty">類股與大盤共同歷史資料不足，暫無法產生比對圖。</div>';
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
  const values = aligned.flatMap((item) => [item.benchmark, item.sector]);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;
  const xFor = (index) => pad.left + index * step;
  const yFor = (value) => pad.top + ((maxValue - value) / range) * plotHeight;
  const activityTop = pad.top + plotHeight + activityGap;
  const benchmarkPoints = aligned.map((item, index) => ({ x: xFor(index), y: yFor(item.benchmark), value: item.benchmark }));
  const sectorPoints = aligned.map((item, index) => ({ x: xFor(index), y: yFor(item.sector), value: item.sector }));
  const sectorAreaPath = `${buildPath(sectorPoints)} L ${sectorPoints.at(-1).x.toFixed(1)} ${(pad.top + plotHeight).toFixed(1)} L ${sectorPoints[0].x.toFixed(1)} ${(pad.top + plotHeight).toFixed(1)} Z`;
  const volumeValues = aligned.map((item) => Number.isFinite(item.sectorVolume) ? item.sectorVolume : 0);
  const maxVolume = Math.max(...volumeValues, 1);
  const volumeBarWidth = Math.min(14, Math.max(2, step * 0.58));
  const volumeBars = aligned.map((item, index) => {
    const h = Math.max(1, (volumeValues[index] / maxVolume) * activityHeight);
    const y = activityTop + activityHeight - h;
    const tone = index === 0 || item.sector >= aligned[index - 1].sector ? "up" : "down";
    return `<rect class="sector-activity-volume ${tone}" x="${(xFor(index) - volumeBarWidth / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${volumeBarWidth.toFixed(1)}" height="${h.toFixed(1)}" rx="2"></rect>`;
  }).join("");
  const grid = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * plotHeight;
    const value = maxValue - ratio * range;
    return `<line x1="${pad.left}" y1="${y.toFixed(1)}" x2="${width - pad.right}" y2="${y.toFixed(1)}"></line>
      <text x="8" y="${(y + 5).toFixed(1)}">${value.toFixed(1)}</text>`;
  }).join("");
  const first = aligned[0];
  const last = aligned.at(-1);
  const alpha = last.sector - last.benchmark;
  const sectorDelta = last.sector - 100;
  const benchmarkDelta = last.benchmark - 100;
  const focusTone = alpha >= 0 ? "up" : "down";
  const hoverZones = aligned.map((item, index) => {
    const left = index === 0 ? pad.left : xFor(index) - step / 2;
    const zoneWidth = index === aligned.length - 1 ? (width - pad.right) - left : step;
    return `<rect class="us-sector-compare-hover-zone sector-hover-zone" x="${left.toFixed(1)}" y="${pad.top}" width="${Math.max(zoneWidth, 12).toFixed(1)}" height="${plotHeight + activityGap + activityHeight}" data-x="${xFor(index).toFixed(1)}" data-date="${escapeHtml(item.date)}" data-benchmark="${item.benchmark.toFixed(2)}" data-sector="${item.sector.toFixed(2)}" data-alpha="${item.alpha.toFixed(2)}" data-benchmark-raw="${item.benchmarkRaw.toFixed(2)}" data-sector-raw="${item.sectorRaw.toFixed(2)}" data-volume="${formatGlobalVolume(item.sectorVolume)}"></rect>`;
  }).join("");
  const benchmarkName = getUsBenchmarkDisplayName(benchmark);
  const sectorName = getUsSectorDisplayName(sector);
  return `
    <svg class="sector-comparison-chart us-sector-compare-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(sectorName)} 與 ${escapeHtml(benchmarkName)} 比較走勢圖">
      <defs>
        <linearGradient id="usSectorAreaGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${focusTone === "up" ? "var(--green)" : "var(--red)"}" stop-opacity="0.28"></stop>
          <stop offset="100%" stop-color="${focusTone === "up" ? "var(--green)" : "var(--red)"}" stop-opacity="0.01"></stop>
        </linearGradient>
      </defs>
      <rect class="sector-plot-surface" x="${pad.left}" y="${pad.top}" width="${plotWidth}" height="${plotHeight}" rx="12"></rect>
      <g class="chart-grid">${grid}</g>
      <rect class="sector-base-band" x="${pad.left}" y="${Math.max(pad.top, yFor(100.2)).toFixed(1)}" width="${plotWidth}" height="${Math.max(2, Math.abs(yFor(99.8) - yFor(100.2))).toFixed(1)}"></rect>
      <line class="sector-base-line" x1="${pad.left}" y1="${yFor(100).toFixed(1)}" x2="${width - pad.right}" y2="${yFor(100).toFixed(1)}"></line>
      <path class="sector-focus-area ${focusTone} us-sector-focus-area" d="${sectorAreaPath}"></path>
      <path class="sector-benchmark-line" d="${buildPath(benchmarkPoints)}"></path>
      <path class="sector-focus-line ${focusTone}" d="${buildPath(sectorPoints)}"></path>
      <line class="sector-activity-boundary" x1="${pad.left}" y1="${(activityTop - 12).toFixed(1)}" x2="${width - pad.right}" y2="${(activityTop - 12).toFixed(1)}"></line>
      <g class="sector-activity-bars">${volumeBars}</g>
      <text class="sector-activity-label" x="${pad.left}" y="${(activityTop - 17).toFixed(1)}">成交量（柱狀越高代表交易越熱絡）</text>
      <line class="sector-hover-guide us-sector-compare-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${activityTop + activityHeight}" style="display:none"></line>
      <circle class="sector-focus-end ${focusTone}" cx="${sectorPoints.at(-1).x.toFixed(1)}" cy="${sectorPoints.at(-1).y.toFixed(1)}" r="4"></circle>
      <circle class="sector-benchmark-end" cx="${benchmarkPoints.at(-1).x.toFixed(1)}" cy="${benchmarkPoints.at(-1).y.toFixed(1)}" r="4"></circle>
      <g class="sector-end-label sector-end-label-primary" transform="translate(${(sectorPoints.at(-1).x - 138).toFixed(1)} ${(sectorPoints.at(-1).y - 28).toFixed(1)})">
        <rect width="134" height="22" rx="11"></rect>
        <text x="67" y="15" text-anchor="middle">${escapeHtml(sectorName)} ${sectorDelta >= 0 ? "+" : ""}${sectorDelta.toFixed(2)}%</text>
      </g>
      <g class="sector-end-label sector-end-label-benchmark" transform="translate(${(benchmarkPoints.at(-1).x - 108).toFixed(1)} ${(benchmarkPoints.at(-1).y + 9).toFixed(1)})">
        <rect width="104" height="22" rx="11"></rect>
        <text x="52" y="15" text-anchor="middle">大盤 ${benchmarkDelta >= 0 ? "+" : ""}${benchmarkDelta.toFixed(2)}%</text>
      </g>
      <g class="chart-labels">
        <text x="${pad.left}" y="${height - 18}">${escapeHtml(first.date)}</text>
        <text x="${width - pad.right - 90}" y="${height - 18}">${escapeHtml(last.date)}</text>
        <text x="${width - pad.right - 244}" y="24">${escapeHtml(sectorName)} / ${escapeHtml(benchmarkName)} / 日線</text>
      </g>
      <g>${hoverZones}</g>
    </svg>
  `;
}
function renderUsSectorIndexComparisonCard(payload) {
  if (payload?.category !== "us-stocks") return "";
  const items = payload.items || [];
  const benchmarks = US_MAJOR_INDEX_SYMBOLS.map((symbol) => items.find((item) => item.symbol === symbol)).filter(Boolean);
  if (!benchmarks.length) return "";
  const benchmark = benchmarks.find((item) => item.symbol === usSectorBenchmarkSymbol) || benchmarks[0];
  usSectorBenchmarkSymbol = benchmark.symbol;
  const sectors = getUsSectorOptionsForBenchmark(items, benchmark.symbol);
  if (!sectors.length) return "";
  const sector = sectors.find((item) => item.symbol === usSectorCompareSymbol) || sectors[0];
  usSectorCompareSymbol = sector.symbol;
  const aligned = buildUsSectorComparisonModel(benchmark, sector);
  const first = aligned[0];
  const last = aligned.at(-1);
  const benchmarkReturn = first && last ? last.benchmark - first.benchmark : null;
  const sectorReturn = first && last ? last.sector - first.sector : null;
  const alpha = Number.isFinite(sectorReturn) && Number.isFinite(benchmarkReturn) ? sectorReturn - benchmarkReturn : null;
  const analysis = buildUsSectorComparisonAnalysis(aligned, benchmark, sector);
  const sectorName = getUsSectorDisplayName(sector);
  const benchmarkName = getUsBenchmarkDisplayName(benchmark);
  const comparisonText = Number.isFinite(alpha)
    ? alpha >= 0
      ? `${sectorName} 目前領先 ${benchmarkName} ${alpha.toFixed(2)}%`
      : `${sectorName} 目前落後 ${benchmarkName} ${Math.abs(alpha).toFixed(2)}%`
    : `${sectorName} 與 ${benchmarkName} 比對中`;
  const latestVolume = aligned.at(-1)?.sectorVolume;
  return `
    <section class="section" id="us-sector-index-comparison">
      <article class="panel-card us-sector-compare-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">類股指數比對</p>
            <h3>大盤指數 × 美股類股指數比對</h3>
          </div>
          <span class="chip ${Number.isFinite(alpha) && alpha >= 0 ? "chip-green" : "chip-red"}">${Number.isFinite(alpha) ? `相對差 ${alpha >= 0 ? "+" : ""}${alpha.toFixed(2)}` : "Base=100"}</span>
        </div>
        <div class="us-index-switcher">
          ${benchmarks.map((item) => `
            <button class="range-button ${item.symbol === benchmark.symbol ? "is-active" : ""}" type="button" data-us-sector-benchmark="${escapeHtml(item.symbol)}">${escapeHtml(getUsBenchmarkDisplayName(item))}</button>
          `).join("")}
        </div>
        <div class="us-sector-chip-grid">
          ${sectors.map((item) => `
            <button class="range-button ${item.symbol === sector.symbol ? "is-active" : ""}" type="button" data-us-sector-index="${escapeHtml(item.symbol)}">${escapeHtml(getUsSectorDisplayName(item))}</button>
          `).join("")}
        </div>
        <div class="sector-sync-chart-summary">
          <strong>${escapeHtml(sectorName)} 與大盤走勢比較</strong>
          <span>兩條線都從 100 開始，位置越高代表表現越好</span>
        </div>
        <div class="sector-plain-result ${Number.isFinite(alpha) && alpha >= 0 ? "is-ahead" : "is-behind"}">
          <strong>${escapeHtml(comparisonText)}</strong>
          <span>日線期間：${escapeHtml(sectorName)} ${Number.isFinite(sectorReturn) && sectorReturn >= 0 ? "上漲" : "下跌"} ${Number.isFinite(sectorReturn) ? Math.abs(sectorReturn).toFixed(2) : "--"}%，${escapeHtml(benchmarkName)} ${Number.isFinite(benchmarkReturn) && benchmarkReturn >= 0 ? "上漲" : "下跌"} ${Number.isFinite(benchmarkReturn) ? Math.abs(benchmarkReturn).toFixed(2) : "--"}%</span>
        </div>
        <div class="sector-chart-stat-strip without-trades">
          <span>成交量<strong>${formatGlobalVolume(latestVolume)}</strong></span>
          <span>類股日漲跌<strong>${escapeHtml(sector.pct || "--")}</strong></span>
          <span>大盤日漲跌<strong>${escapeHtml(benchmark.pct || "--")}</strong></span>
          <span>${Number.isFinite(alpha) && alpha >= 0 ? "領先大盤" : "落後大盤"}<strong class="${Number.isFinite(alpha) && alpha >= 0 ? "up" : "down"}">${Number.isFinite(alpha) ? `${Math.abs(alpha).toFixed(2)}%` : "--"}</strong></span>
        </div>
        <div class="sector-chart-frame us-sector-compare-chart-wrap">
          ${renderUsSectorComparisonSvg(benchmark, sector, analysis)}
          <div class="sector-sync-tooltip us-sector-compare-tooltip" hidden></div>
        </div>
        <div class="sector-chart-legend">
          <span><i class="legend-swatch legend-swatch-sector ${Number.isFinite(alpha) && alpha >= 0 ? "up" : "down"}"></i>${escapeHtml(getUsSectorDisplayName(sector))}</span>
          <span><i class="legend-swatch legend-swatch-market"></i>${escapeHtml(getUsBenchmarkDisplayName(benchmark))}</span>
          <span>起點 = 100，直接比較誰漲得多</span>
        </div>
        <div class="global-summary-grid us-index-vix-stats">
          <span><b>${escapeHtml(sector.pct || "--")}</b><small>類股日漲跌幅</small></span>
          <span><b>${escapeHtml(benchmark.pct || "--")}</b><small>大盤日漲跌幅</small></span>
          <span><b>${Number.isFinite(sectorReturn) ? `${sectorReturn >= 0 ? "+" : ""}${sectorReturn.toFixed(2)}` : "--"}</b><small>類股區間報酬</small></span>
          <span><b>${Number.isFinite(benchmarkReturn) ? `${benchmarkReturn >= 0 ? "+" : ""}${benchmarkReturn.toFixed(2)}` : "--"}</b><small>大盤區間報酬</small></span>
          <span><b>${Number.isFinite(analysis.alpha20) ? `${analysis.alpha20 >= 0 ? "+" : ""}${analysis.alpha20.toFixed(2)}` : "--"}</b><small>近20日相對變化</small></span>
          <span><b>${analysis.leadDays20}/20</b><small>近20日領先天數</small></span>
        </div>
        <div class="us-sector-analysis-grid">
          <section class="us-sector-analysis-card is-${escapeHtml(analysis.tone)}">
            <p class="panel-kicker">相對強弱</p>
            <h4>${escapeHtml(analysis.stance)}</h4>
            <p>${escapeHtml(analysis.signal)}</p>
          </section>
          <section class="us-sector-analysis-card">
            <p class="panel-kicker">判讀說明</p>
            <h4>判讀邏輯</h4>
            <ul>
              ${analysis.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
            </ul>
          </section>
        </div>
        <p class="global-insight">這張圖不是預測價格，而是用相對強弱判斷資金偏向：差值持續擴大代表類股比大盤更強，差值收斂則代表優勢降溫或落後修復。</p>
      </article>
    </section>
  `;
}
function bindUsSectorIndexComparisonCard(payload) {
  const card = document.getElementById("us-sector-index-comparison");
  if (!card) return;
  const rerender = () => {
    const replacement = renderUsSectorIndexComparisonCard(payload);
    if (replacement) {
      card.outerHTML = replacement;
      bindUsSectorIndexComparisonCard(payload);
    }
  };
  card.querySelectorAll("[data-us-sector-benchmark]").forEach((button) => {
    button.addEventListener("click", () => {
      usSectorBenchmarkSymbol = button.dataset.usSectorBenchmark || "^GSPC";
      rerender();
    });
  });
  card.querySelectorAll("[data-us-sector-index]").forEach((button) => {
    button.addEventListener("click", () => {
      usSectorCompareSymbol = button.dataset.usSectorIndex || "";
      rerender();
    });
  });
  const frame = card.querySelector(".us-sector-compare-chart-wrap");
  const tooltip = card.querySelector(".us-sector-compare-tooltip");
  const crosshair = card.querySelector(".us-sector-compare-crosshair");
  if (!frame || !tooltip) return;
  const hide = () => {
    tooltip.hidden = true;
    if (crosshair) {
      crosshair.classList.remove("is-visible");
      crosshair.style.display = "none";
    }
  };
  const positionTooltip = (event, zone) => {
    const frameRect = frame.getBoundingClientRect();
    const zoneRect = zone.getBoundingClientRect();
    const pointerX = Number.isFinite(event?.clientX) ? event.clientX : zoneRect.left + zoneRect.width / 2;
    const pointerY = Number.isFinite(event?.clientY) ? event.clientY : zoneRect.top + zoneRect.height / 2;
    const width = tooltip.offsetWidth || 260;
    const height = tooltip.offsetHeight || 142;
    const preferredLeft = pointerX - frameRect.left + 16;
    const preferredTop = pointerY - frameRect.top - height - 14;
    const left = Math.max(8, Math.min(preferredLeft, frameRect.width - width - 8));
    const top = preferredTop >= 8
      ? preferredTop
      : Math.min(pointerY - frameRect.top + 18, frameRect.height - height - 8);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${Math.max(8, top)}px`;
    tooltip.style.transform = "none";
  };
  const show = (event, zone) => {
    tooltip.hidden = false;
    tooltip.innerHTML = `
      <strong>${escapeHtml(zone.dataset.date || "--")}</strong>
      <span>大盤：<strong>${escapeHtml(zone.dataset.benchmark || "--")}</strong>（原值 ${escapeHtml(zone.dataset.benchmarkRaw || "--")}）</span>
      <span>類股：<strong>${escapeHtml(zone.dataset.sector || "--")}</strong>（原值 ${escapeHtml(zone.dataset.sectorRaw || "--")}）</span>
      <span>相對差：<strong>${escapeHtml(zone.dataset.alpha || "--")}</strong></span>
      <span>成交量：<strong>${escapeHtml(zone.dataset.volume || "--")}</strong></span>
    `;
    positionTooltip(event, zone);
    if (crosshair) {
      crosshair.setAttribute("x1", zone.dataset.x || "0");
      crosshair.setAttribute("x2", zone.dataset.x || "0");
      crosshair.style.display = "block";
      crosshair.classList.add("is-visible");
    }
  };
  card.querySelectorAll(".us-sector-compare-hover-zone").forEach((zone) => {
    zone.addEventListener("mouseenter", (event) => show(event, zone));
    zone.addEventListener("mousemove", (event) => show(event, zone));
    zone.addEventListener("mouseleave", hide);
  });
  frame.addEventListener("mouseleave", hide);
}
function buildGlobalMarketInsight(payload) {
  const summary = payload?.summary || {};
  const avg = parseMarketNumber(summary.avgPct);
  const breadth = (summary.advancers || 0) - (summary.decliners || 0);
  if (!Number.isFinite(avg)) return "資料仍在更新，建議先以各商品卡片的漲跌與成交量做個別觀察。";
  if (avg > 0.6 && breadth > 0) return "整體偏多，平均漲幅與上漲家數同步改善，短線風險偏好回升。";
  if (avg < -0.6 && breadth < 0) return "整體偏弱，平均跌幅與下跌家數同步擴大，建議提高風險控管。";
  return "市場呈現分歧，需搭配強弱商品與成交量判斷是否為輪動或避險資金切換。";
}
function buildUsMarketPulseAnalysis({ majorItems, usablePulseItems, vix, avgPct, advancers, decliners, strongest, weakest }) {
  const formatPulsePct = (value) => Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const vixValue = parseMarketNumber(vix?.close);
  const vixPct = parseMarketNumber(vix?.pct);
  const vixBand = getVixSentimentBand(vixValue);
  const vixRisk = Number.isFinite(vixValue)
    ? Math.max(0, Math.min(100, Math.round(((vixValue - 10) / 35) * 100)))
    : null;
  const rankedIndexes = majorItems
    .filter((item) => Number.isFinite(parseMarketNumber(item.pct)))
    .sort((a, b) => (parseMarketNumber(b.pct) || 0) - (parseMarketNumber(a.pct) || 0));
  const leader = rankedIndexes[0];
  const laggard = rankedIndexes.at(-1);
  const breadthTotal = advancers + decliners;
  const breadthRatio = breadthTotal ? advancers / breadthTotal : null;
  const breadthText = Number.isFinite(breadthRatio)
    ? breadthRatio >= 0.62
      ? "廣度偏多"
      : breadthRatio <= 0.38
        ? "廣度偏空"
        : "廣度分歧"
    : "廣度待確認";
  const indexScore = Number.isFinite(parseMarketNumber(leader?.pct))
    ? parseMarketNumber(leader?.pct) > 0 ? 1 : -1
    : 0;
  const breadthScore = Number.isFinite(breadthRatio)
    ? breadthRatio >= 0.58 ? 1 : breadthRatio <= 0.42 ? -1 : 0
    : 0;
  const avgScore = Number.isFinite(avgPct)
    ? avgPct > 0.35 ? 1 : avgPct < -0.35 ? -1 : 0
    : 0;
  const vixScore = Number.isFinite(vixValue)
    ? vixValue < 20 ? 1 : vixValue >= 30 ? -2 : vixValue >= 25 ? -1 : 0
    : 0;
  const vixDirectionScore = Number.isFinite(vixPct)
    ? vixPct < -2 ? 1 : vixPct > 4 ? -1 : 0
    : 0;
  const score = indexScore + breadthScore + avgScore + vixScore + vixDirectionScore;
  const regime = score >= 3
    ? { label: "風險偏好回升", tone: "green" }
    : score >= 1
      ? { label: "偏多但需確認", tone: "blue" }
      : score <= -3
        ? { label: "防守優先", tone: "red" }
        : score <= -1
          ? { label: "震盪偏弱", tone: "yellow" }
          : { label: "中性輪動", tone: "neutral" };
  const confidence = [
    Number.isFinite(avgPct),
    Number.isFinite(breadthRatio),
    rankedIndexes.length >= 2,
    Number.isFinite(vixValue),
  ].filter(Boolean).length;
  const indexText = leader
    ? `${leader.name.replace(" Industrial Average", "")} 目前領先 ${leader.pct || "--"}，${laggard && laggard !== leader ? `${laggard.name.replace(" Industrial Average", "")} 相對落後 ${laggard.pct || "--"}。` : "主要指數方向仍需同步確認。"}`
    : "主要指數資料仍在同步。";
  const breadthDetail = Number.isFinite(breadthRatio)
    ? `${advancers} 檔上漲、${decliners} 檔下跌，上漲占比 ${(breadthRatio * 100).toFixed(0)}%。`
    : "樣本廣度不足，暫不判定資金擴散。";
  const action = score >= 3
    ? "可優先追蹤強勢族群與突破型個股，但仍以分批與停損控管追價風險。"
    : score >= 1
      ? "偏多訊號尚可，適合觀察回測支撐後的續強標的，避免一次建立完整部位。"
      : score <= -3
        ? "防守優先，降低槓桿與追高，等 VIX 降溫及主要指數止跌再提高曝險。"
        : score <= -1
          ? "盤勢偏弱或分歧，先控倉位，強勢股僅採小部位試單。"
          : "市場輪動中，建議用大盤、VIX、成交量與強弱股同步確認方向。";
  const riskNotes = [
    vixBand.text,
    Number.isFinite(vixPct) && vixPct > 4 ? "VIX 單日升幅偏大，代表避險需求正在升高。" : "",
    Number.isFinite(breadthRatio) && breadthRatio < 0.45 ? "上漲家數不足，指數若上漲可能偏少數權值股撐盤。" : "",
    Number.isFinite(avgPct) && avgPct < 0 ? "樣本平均仍為負值，短線需避免忽略個股分化。" : "",
  ].filter(Boolean);
  const opportunityNotes = [
    strongest ? `強勢觀察：${strongest.symbol || strongest.name} ${strongest.pct || "--"}，可檢查是否有量價同步。` : "",
    weakest ? `弱勢警訊：${weakest.symbol || weakest.name} ${weakest.pct || "--"}，留意是否拖累同族群。` : "",
    leader ? `指數領先：${leader.name.replace(" Industrial Average", "")}，用於判斷資金偏向。` : "",
  ].filter(Boolean);
  const indexTrendModels = majorItems
    .map((item) => {
      const series = normalizeGlobalSeries(item.series || []);
      if (series.length < 22) return null;
      const closes = series.map((point) => point.value).filter(Number.isFinite);
      const latest = closes.at(-1);
      const ma20 = technicalSma(closes, 20).at(-1);
      const ma60 = technicalSma(closes, 60).at(-1);
      const close20 = closes.at(-21);
      const return20 = Number.isFinite(latest) && Number.isFinite(close20) && close20
        ? ((latest - close20) / close20) * 100
        : null;
      let trendScore = 0;
      if (Number.isFinite(latest) && Number.isFinite(ma20)) trendScore += latest >= ma20 ? 1 : -1;
      if (Number.isFinite(ma20) && Number.isFinite(ma60)) trendScore += ma20 >= ma60 ? 1 : -1;
      if (Number.isFinite(return20)) trendScore += return20 > 2 ? 1 : return20 < -2 ? -1 : 0;
      return { item, latest, ma20, ma60, return20, trendScore };
    })
    .filter(Boolean);
  const trendScoreTotal = indexTrendModels.reduce((sum, model) => sum + model.trendScore, 0);
  const maxTrendScore = Math.max(indexTrendModels.length * 3, 1);
  const trendPower = Math.round(((trendScoreTotal + maxTrendScore) / (maxTrendScore * 2)) * 100);
  const trendLabel = trendPower >= 68
    ? "上升趨勢"
    : trendPower >= 54
      ? "偏多整理"
      : trendPower <= 32
        ? "下降趨勢"
        : trendPower <= 46
          ? "偏弱震盪"
          : "中性震盪";
  const trendTone = trendPower >= 54 ? "positive" : trendPower <= 46 ? "negative" : "watch";
  const trendDrivers = indexTrendModels
    .slice()
    .sort((a, b) => b.trendScore - a.trendScore)
    .slice(0, 2)
    .map((model) => `${getUsBenchmarkDisplayName(model.item)} 近20日 ${formatPulsePct(model.return20)}，${Number.isFinite(model.latest) && Number.isFinite(model.ma20) && model.latest >= model.ma20 ? "站上20日線" : "低於20日線"}`);
  const riskScoreRaw = 50
    + (Number.isFinite(vixRisk) ? (vixRisk - 45) * 0.55 : 0)
    + (Number.isFinite(breadthRatio) ? (0.5 - breadthRatio) * 42 : 0)
    + (Number.isFinite(avgPct) ? clamp(-avgPct * 7, -12, 12) : 0)
    + (trendPower < 45 ? 12 : trendPower > 62 ? -8 : 0)
    + (Number.isFinite(vixPct) ? clamp(vixPct * 1.2, -8, 12) : 0);
  const riskScore = Math.round(clamp(riskScoreRaw, 0, 100));
  const riskLevel = riskScore >= 70
    ? "高風險"
    : riskScore >= 55
      ? "風險偏高"
      : riskScore <= 32
        ? "風險偏低"
        : "中性風險";
  const riskTone = riskScore >= 55 ? "negative" : riskScore <= 35 ? "positive" : "watch";
  const bullishRaw = 34 + score * 6 + (trendPower - 50) * 0.45 + (Number.isFinite(breadthRatio) ? (breadthRatio - 0.5) * 35 : 0) - (riskScore - 50) * 0.22;
  const bearishRaw = 28 - score * 4 + (50 - trendPower) * 0.38 + (riskScore - 50) * 0.36 + (Number.isFinite(vixPct) ? Math.max(vixPct, 0) * 0.8 : 0);
  const bullish = Math.round(clamp(bullishRaw, 15, 72));
  const bearish = Math.round(clamp(bearishRaw, 12, 70));
  const neutral = Math.max(10, 100 - bullish - bearish);
  const normalizedTotal = bullish + neutral + bearish;
  const forecast = {
    horizon: "未來 3-5 個交易日",
    bullish: Math.round((bullish / normalizedTotal) * 100),
    neutral: Math.round((neutral / normalizedTotal) * 100),
    bearish: Math.round((bearish / normalizedTotal) * 100),
  };
  forecast.label = forecast.bullish >= forecast.bearish + 12
    ? "偏多延續"
    : forecast.bearish >= forecast.bullish + 12
      ? "修正風險升高"
      : "區間震盪機率高";
  forecast.summary = `${forecast.horizon} 情境推估：多方 ${forecast.bullish}%、震盪 ${forecast.neutral}%、空方 ${forecast.bearish}%。此為內建規則模型，不是價格保證。`;
  const aiModules = [
    {
      title: "趨勢評估",
      label: trendLabel,
      tone: trendTone,
      score: `${trendPower}/100`,
      body: trendDrivers.length ? trendDrivers.join("；") : "主要指數歷史資料不足，趨勢信心偏低。",
    },
    {
      title: "風險評估",
      label: riskLevel,
      tone: riskTone,
      score: `${riskScore}/100`,
      body: `${vixBand.label}，${breadthDetail}${Number.isFinite(avgPct) ? ` 樣本平均 ${formatPulsePct(avgPct)}。` : ""}`,
    },
    {
      title: "情境預測",
      label: forecast.label,
      tone: forecast.bullish > forecast.bearish ? "positive" : forecast.bearish > forecast.bullish ? "negative" : "watch",
      score: `${forecast.bullish}/${forecast.neutral}/${forecast.bearish}`,
      body: forecast.summary,
    },
  ];
  return {
    vixBand,
    vixRisk,
    regime,
    score,
    confidence: `${confidence}/4`,
    breadthText,
    breadthDetail,
    indexText,
    action,
    riskNotes,
    opportunityNotes,
    averageText: formatPulsePct(avgPct),
    trendLabel,
    trendPower,
    riskLevel,
    riskScore,
    forecast,
    aiModules,
    leader,
    laggard,
  };
}
function renderGlobalSummaryCard(payload) {
  const summary = payload?.summary || {};
  const formatPulsePct = (value) => Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "--";
  if (payload?.category !== "us-stocks") {
    return `
      <article class="panel-card global-summary-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">Market pulse</p>
            <h3>${escapeHtml(payload?.title || "全球市場")}即時摘要</h3>
          </div>
          <button class="global-refresh" type="button" data-global-refresh="${escapeHtml(payload?.category || "")}">重新整理</button>
        </div>
        <div class="global-summary-grid">
          <span><b>${summary.count ?? "--"}</b><small>有效商品</small></span>
          <span><b>${summary.advancers ?? "--"} / ${summary.decliners ?? "--"}</b><small>上漲 / 下跌</small></span>
          <span><b>${escapeHtml(summary.avgPct || "--")}</b><small>平均漲跌幅</small></span>
          <span><b>${escapeHtml(summary.strongest || "--")}</b><small>最強 ${escapeHtml(summary.strongestPct || "--")}</small></span>
          <span><b>${escapeHtml(summary.weakest || "--")}</b><small>最弱 ${escapeHtml(summary.weakestPct || "--")}</small></span>
        </div>
        <p class="global-insight">${escapeHtml(buildGlobalMarketInsight(payload))}</p>
      </article>
    `;
  }

  const items = payload.items || [];
  const vix = items.find((item) => item.symbol === "^VIX");
  const majorItems = items.filter((item) => item.group === "主要指數");
  const equityEtfItems = items.filter((item) => ["美股個股", "美股 ETF"].includes(item.group));
  const usablePulseItems = equityEtfItems.filter((item) => Number.isFinite(parseMarketNumber(item.pct)));
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
  const vixValue = parseMarketNumber(vix?.close);
  const pulseText = Number.isFinite(avgPct)
    ? avgPct > 0.45 && advancers > decliners
      ? `美股樣本平均 ${formatPulsePct(avgPct)}，上漲家數占優，短線風險偏好較佳。`
      : avgPct < -0.45 && decliners > advancers
        ? `美股樣本平均 ${formatPulsePct(avgPct)}，下跌家數占優，短線宜提高風控。`
        : `美股樣本平均 ${formatPulsePct(avgPct)}，市場偏輪動，需搭配 VIX 與成交量確認。`
    : "美股樣本資料仍在同步，先觀察 VIX 與主要指數方向。";
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

  return `
    <article class="panel-card global-summary-card us-summary-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">Market pulse</p>
          <h3>美股即時摘要</h3>
        </div>
        <div class="us-summary-actions">
          <span class="chip chip-blue">${escapeHtml(payload.updatedAt || "--")}</span>
          <button class="global-refresh" type="button" data-global-refresh="${escapeHtml(payload.category || "")}">重新整理</button>
        </div>
      </div>
      <div class="us-summary-lead">
        <div class="us-summary-brief is-${escapeHtml(analysis.regime.tone)}">
          <span>內建 AI 市場分析</span>
          <strong>${escapeHtml(analysis.regime.label)} · 評分 ${analysis.score >= 0 ? "+" : ""}${analysis.score}</strong>
          <p>${escapeHtml(analysis.indexText)} ${escapeHtml(pulseText)} ${escapeHtml(analysis.forecast.label)}。</p>
        </div>
        <div class="us-summary-vix is-${escapeHtml(analysis.vixBand.tone)}">
          <span>VIX risk temperature</span>
          <strong>${formatGlobalValue(vix?.close)} <small>${escapeHtml(vix?.pct || "--")}</small></strong>
          <p>${escapeHtml(analysis.vixBand.label)} · 風險溫度 ${analysis.vixRisk ?? "--"}/100 · 信心 ${escapeHtml(analysis.confidence)}</p>
        </div>
      </div>
      <div class="global-summary-grid us-summary-grid">
        <span><b>${usablePulseItems.length || "--"}</b><small>個股 / ETF 樣本</small></span>
        <span><b>${advancers} / ${decliners}</b><small>上漲 / 下跌</small></span>
        <span><b>${analysis.averageText}</b><small>樣本平均漲跌</small></span>
        <span><b>${escapeHtml(analysis.trendLabel)}</b><small>趨勢分數 ${analysis.trendPower}/100</small></span>
        <span><b>${escapeHtml(analysis.riskLevel)}</b><small>風險分數 ${analysis.riskScore}/100</small></span>
        <span><b>${escapeHtml(analysis.forecast.label)}</b><small>${escapeHtml(analysis.forecast.horizon)}</small></span>
        <span><b>${escapeHtml(strongest?.symbol || "--")}</b><small>最強 ${escapeHtml(strongest?.pct || "--")}</small></span>
        <span><b>${escapeHtml(weakest?.symbol || "--")}</b><small>最弱 ${escapeHtml(weakest?.pct || "--")}</small></span>
        <span><b>${escapeHtml(analysis.breadthText)}</b><small>${escapeHtml(analysis.breadthDetail)}</small></span>
      </div>
      <div class="us-ai-evaluation-grid">
        ${analysis.aiModules.map((module) => `
          <section class="us-ai-evaluation-card is-${escapeHtml(module.tone)}">
            <span>${escapeHtml(module.title)}</span>
            <strong>${escapeHtml(module.label)}</strong>
            <b>${escapeHtml(module.score)}</b>
            <p>${escapeHtml(module.body)}</p>
          </section>
        `).join("")}
      </div>
      <div class="us-summary-diagnostics">
        <section>
          <h4>操作節奏</h4>
          <p>${escapeHtml(analysis.action)}</p>
        </section>
        <section>
          <h4>機會觀察</h4>
          <ul>${analysis.opportunityNotes.map((note) => `<li>${escapeHtml(note)}</li>`).join("") || "<li>強弱資料仍在同步。</li>"}</ul>
        </section>
        <section>
          <h4>風險提醒</h4>
          <ul>${analysis.riskNotes.map((note) => `<li>${escapeHtml(note)}</li>`).join("") || "<li>目前未偵測到明顯風險升溫。</li>"}</ul>
        </section>
      </div>
      <p class="global-insight">${escapeHtml(analysis.vixBand.text)} ${escapeHtml(analysis.forecast.summary)} ${escapeHtml(analysis.action)}</p>
    </article>
  `;
}
function renderGlobalMarketCards(items = []) {
  return items.map((item) => {
    const pct = parseMarketNumber(item.pct);
    const tone = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
    const metric = getAssetHubMetric(item);
    return `
      <article class="global-market-card">
        <div class="global-card-head">
          <div>
            <p>${escapeHtml(getAssetHubRegion(item))} · ${escapeHtml(item.type || "市場商品")} · ${escapeHtml(item.symbol || "")}</p>
            <h3>${escapeHtml(item.name || item.symbol || "--")}</h3>
          </div>
          <span class="chip ${tone === "up" ? "chip-green" : tone === "down" ? "chip-red" : "chip-blue"}">${escapeHtml(item.pct || "--")}</span>
        </div>
        ${item.error ? `<div class="global-error">資料暫時無法取得：${escapeHtml(item.error)}</div>` : `
          <div class="global-price-row">
            <strong>${formatGlobalValue(item.close)}</strong>
            <span class="${toneClass(tone)}">${escapeHtml(item.change || "--")} / ${escapeHtml(item.pct || "--")}</span>
          </div>
          ${renderMiniLineChart(item.series)}
          <div class="global-market-facts">
            <span><b>開盤</b>${formatGlobalValue(item.open)}</span>
            <span><b>昨收</b>${formatGlobalValue(item.previousClose)}</span>
            <span><b>最高</b>${formatGlobalValue(item.high)}</span>
            <span><b>最低</b>${formatGlobalValue(item.low)}</span>
            <span><b>${escapeHtml(metric.label)}</b>${formatGlobalVolume(metric.value)}</span>
            <span><b>6月報酬</b>${escapeHtml(item.periodReturn || "--")}</span>
            <span><b>來源</b>${escapeHtml(item.exchange || item.dataSource || "--")}</span>
          </div>
        `}
      </article>
    `;
  }).join("");
}
function getUsSectorStockSelectionStore(selectors = []) {
  const raw = sessionStorage.getItem(US_SECTOR_STOCK_SELECTION_KEY) || "";
  if (!raw) return { benchmark: "", sector: "" };
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      return {
        benchmark: parsed.benchmark || "",
        sector: parsed.sector || "",
      };
    }
  } catch (error) {
    // Backward compatible with the earlier single-symbol storage.
  }
  const legacy = selectors.find((item) => item.symbol === raw);
  return legacy?.group === "主要指數"
    ? { benchmark: raw, sector: "" }
    : { benchmark: "", sector: raw };
}
function saveUsSectorStockSelection() {
  sessionStorage.setItem(US_SECTOR_STOCK_SELECTION_KEY, JSON.stringify({
    benchmark: usSectorStockBenchmarkSymbol || "",
    sector: usSectorStockSymbol || "",
  }));
}
function getUsSectorStockLabel(item) {
  if (!item) return "";
  return item.group === "主要指數" ? getUsBenchmarkDisplayName(item) : getUsSectorDisplayName(item);
}
function renderUsSectorIndexSummaryContent(benchmark, sector) {
  const focus = sector || benchmark;
  const focusTone = (parseMarketNumber(focus?.pct) || 0) > 0 ? "up" : (parseMarketNumber(focus?.pct) || 0) < 0 ? "down" : "flat";
  const benchmarkLabel = getUsSectorStockLabel(benchmark) || "主要指數";
  const sectorLabel = getUsSectorStockLabel(sector);
  const title = sector ? `${benchmarkLabel} × ${sectorLabel}` : benchmarkLabel;
  const symbolText = sector
    ? `${benchmark?.symbol || "--"} / ${sector?.symbol || "--"}`
    : benchmark?.symbol || "--";
  const note = sector
    ? `${benchmarkLabel} 作為大盤基準，${sectorLabel} 作為目前類股觀察。`
    : `${benchmarkLabel} 作為目前大盤基準。`;
  return `
    <div>
      <p class="panel-kicker">目前指數 / 類股</p>
      <h4>${escapeHtml(title)}</h4>
      <span>${escapeHtml(symbolText)} · ${escapeHtml(note)}</span>
    </div>
    <div class="us-sector-index-metrics">
      <span><b>${formatGlobalValue(benchmark?.close)}</b><small>${escapeHtml(benchmarkLabel)} 最新</small></span>
      <span><b class="${toneClass((parseMarketNumber(benchmark?.pct) || 0) > 0 ? "up" : (parseMarketNumber(benchmark?.pct) || 0) < 0 ? "down" : "flat")}">${escapeHtml(benchmark?.pct || "--")}</b><small>大盤漲跌幅</small></span>
      <span><b>${formatGlobalValue(focus?.close)}</b><small>${escapeHtml(sectorLabel || benchmarkLabel)} 最新</small></span>
      <span><b class="${toneClass(focusTone)}">${escapeHtml(focus?.pct || "--")}</b><small>觀察漲跌幅</small></span>
    </div>
  `;
}
function normalizeUsScopeSymbol(symbol) {
  return String(symbol || "").trim().toUpperCase();
}
function usSectorItemMatchesQuery(item, query) {
  const keyword = String(query || "").trim().toLowerCase();
  if (!keyword) return true;
  return ["symbol", "name", "type", "group", "exchange", "scopeRelationText"]
    .some((key) => String(item?.[key] || "").toLowerCase().includes(keyword));
}
function buildUsSectorScopeItems(scopePayloads, query) {
  const scoped = new Map();
  scopePayloads.filter(Boolean).forEach((payload, payloadIndex) => {
    const roleLabel = payload.scopeRoleLabel || payload.label || "觀察池";
    (payload.items || []).forEach((item, itemIndex) => {
      if (item?.error) return;
      const symbol = normalizeUsScopeSymbol(item.symbol);
      if (!symbol) return;
      const current = scoped.get(symbol) || {
        ...item,
        symbol,
        group: item.group || "美股個股",
        exchange: item.exchange || "Yahoo",
        source: item.source || "Yahoo Finance 線上資料",
        scopeRelations: new Set(),
        scopeRank: payloadIndex * 100 + itemIndex,
      };
      current.scopeRelations.add(roleLabel);
      current.scopeRank = Math.min(current.scopeRank, payloadIndex * 100 + itemIndex);
      scoped.set(symbol, current);
    });
  });
  return Array.from(scoped.values())
    .map((item) => {
      const scopeRelationText = Array.from(item.scopeRelations || []).join(" / ");
      const scopeStrength = item.scopeRelations?.size || 0;
      const cleaned = { ...item, scopeRelationText, scopeStrength, isScopeItem: true };
      delete cleaned.scopeRelations;
      return cleaned;
    })
    .filter((item) => usSectorItemMatchesQuery(item, query));
}
function mergeUsSectorDirectoryWithScope(directoryPayload, scopePayloads, options = {}) {
  const query = usSectorNyseStockState.query || "";
  const scopeOnly = Boolean(options.scopeOnly);
  const directoryItems = directoryPayload?.results || directoryPayload?.items || [];
  const scopeItems = buildUsSectorScopeItems(scopePayloads, query);
  const merged = new Map();

  scopeItems.forEach((item) => {
    merged.set(normalizeUsScopeSymbol(item.symbol), item);
  });

  directoryItems.forEach((item, index) => {
    const symbol = normalizeUsScopeSymbol(item.symbol);
    if (!symbol) return;
    const existing = merged.get(symbol);
    if (scopeOnly && !existing) return;
    const base = {
      ...item,
      symbol,
      directoryRank: index,
      scopeRelationText: existing?.scopeRelationText || "",
      scopeStrength: existing?.scopeStrength || 0,
      isScopeItem: Boolean(existing),
    };
    merged.set(symbol, existing
      ? {
        ...base,
        ...existing,
        exchange: item.exchange || existing.exchange,
        nyseUrl: item.nyseUrl || existing.nyseUrl,
        source: `${existing.source || "Yahoo Finance 線上資料"} + ${item.source || directoryPayload?.source || "NYSE Listings Directory"}`,
      }
      : base);
  });

  const items = Array.from(merged.values()).sort((left, right) => {
    const leftScope = left.scopeStrength || 0;
    const rightScope = right.scopeStrength || 0;
    if (leftScope !== rightScope) return rightScope - leftScope;
    if (leftScope || rightScope) return (left.scopeRank ?? 9999) - (right.scopeRank ?? 9999);
    return String(left.symbol || "").localeCompare(String(right.symbol || ""));
  });
  const total = scopeOnly ? items.length : directoryPayload?.total || directoryPayload?.count || directoryItems.length;
  return {
    ...directoryPayload,
    items,
    results: items,
    total,
    count: items.length,
    scopeCount: scopeItems.length,
    scopeOnly,
    scopeLabel: options.scopeLabel || "",
    directoryCount: directoryItems.length,
    source: scopeOnly ? "Yahoo Finance 成分股資料 + NYSE Listings Directory" : directoryPayload?.source || "NYSE Listings Directory",
    error: directoryPayload?.error || "",
  };
}
function renderUsSectorStocksBrowser(payload) {
  if (payload?.category !== "us-stocks") return "";
  const items = payload.items || [];
  const counts = getUsMarketPayloadCounts(payload);
  const benchmarks = US_MAJOR_INDEX_SYMBOLS.map((symbol) => items.find((item) => item.symbol === symbol)).filter(Boolean);
  const spSectors = US_SP500_SECTOR_SYMBOLS
    .map((symbol) => items.find((item) => item.symbol === symbol))
    .filter(Boolean);
  const industrySectors = US_INDUSTRY_SECTOR_SYMBOLS
    .map((symbol) => items.find((item) => item.symbol === symbol))
    .filter(Boolean);
  const allSectorSelectors = [...spSectors, ...industrySectors];
  const selectors = [...benchmarks, ...allSectorSelectors];
  if (!selectors.length) return "";
  const savedSelection = getUsSectorStockSelectionStore(selectors);
  const activeBenchmark = benchmarks.find((item) => item.symbol === (savedSelection.benchmark || usSectorStockBenchmarkSymbol))
    || benchmarks[0]
    || selectors[0];
  const sectorSelectors = getUsSectorOptionsForBenchmark(items, activeBenchmark?.symbol || "^GSPC");
  const activeSector = sectorSelectors.find((item) => item.symbol === (savedSelection.sector || usSectorStockSymbol))
    || sectorSelectors[0]
    || null;
  usSectorStockBenchmarkSymbol = activeBenchmark?.symbol || "";
  usSectorStockSymbol = activeSector?.symbol || "";
  const focus = activeSector || activeBenchmark;
  const activeTone = (parseMarketNumber(focus?.pct) || 0) > 0 ? "up" : (parseMarketNumber(focus?.pct) || 0) < 0 ? "down" : "flat";
  const renderSelectorButtons = (rows) => rows.map((row) => `
    <div class="us-sector-selector-row">
      ${row.map((item) => `
        <button class="range-button ${item.group === "主要指數" ? item.symbol === usSectorStockBenchmarkSymbol ? "is-active" : "" : item.symbol === usSectorStockSymbol ? "is-active" : ""}" type="button" data-us-sector-stock="${escapeHtml(item.symbol)}" data-us-sector-stock-role="${item.group === "主要指數" ? "benchmark" : "sector"}">
          ${escapeHtml(getUsSectorStockLabel(item))}
        </button>
      `).join("")}
    </div>
  `).join("");
  return `
    <section class="section" id="us-sector-stock-browser" data-selected-benchmark="${escapeHtml(usSectorStockBenchmarkSymbol)}" data-selected-sector="${escapeHtml(usSectorStockSymbol)}" ${activeSector ? `data-selected-sector-name="${escapeHtml(activeSector.name)}"` : ""}>
      <article class="panel-card us-sector-stock-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">類股個股明細</p>
            <h3>美股個股線上資料明細</h3>
            <p class="source-note">此區為 NYSE / Nasdaq 上市個股清單與目前指數 / 類股成分股；上方盤勢精選行情為 ${Number(counts.quoteCount).toLocaleString("zh-TW")} 筆，不代表個股明細總數。</p>
          </div>
          <span id="us-sector-stock-count" class="chip chip-blue">明細載入中</span>
        </div>
        <div class="us-sector-selector-grid">
          ${renderSelectorButtons([benchmarks, sectorSelectors])}
        </div>
        <div id="us-sector-index-summary" class="us-sector-index-summary is-${activeTone}">
          ${renderUsSectorIndexSummaryContent(activeBenchmark, activeSector)}
        </div>
        <form class="us-directory-tools" data-us-sector-nyse-search-form>
          <label for="us-sector-nyse-search">搜尋股票</label>
          <input id="us-sector-nyse-search" type="search" value="${escapeHtml(usSectorNyseStockState.query)}" placeholder="輸入代號或名稱，例如 AAPL、Tesla、Bank">
          <button type="submit" class="btn-primary">搜尋</button>
          <button type="button" class="btn-secondary" data-us-sector-nyse-reset>清除</button>
        </form>
        <p id="us-sector-stock-status" class="source-note">正在載入目前類股成分股...</p>
        <div id="us-sector-stock-table" class="global-table-wrap us-sector-stock-table-wrap">
          <div class="stock-detail-empty">美股個股線上資料載入中。</div>
        </div>
        <div id="us-sector-stock-pager" class="us-directory-pager"></div>
      </article>
    </section>
  `;
}
function renderUsSectorStockItems(payload) {
  const table = document.getElementById("us-sector-stock-table");
  const count = document.getElementById("us-sector-stock-count");
  const status = document.getElementById("us-sector-stock-status");
  const pager = document.getElementById("us-sector-stock-pager");
  if (!table) return;
  usSectorNyseStockState.payload = payload;
  const items = payload?.items || [];
  const total = payload?.total || payload?.count || items.length;
  const totalPages = Math.max(Math.ceil(items.length / US_NYSE_DIRECTORY_PAGE_SIZE), 1);
  usSectorNyseStockState.page = Math.max(1, Math.min(usSectorNyseStockState.page || 1, totalPages));
  const start = (usSectorNyseStockState.page - 1) * US_NYSE_DIRECTORY_PAGE_SIZE;
  const pageItems = items.slice(start, start + US_NYSE_DIRECTORY_PAGE_SIZE);
  const selectorItems = window.currentGlobalMarketPayload?.items || [];
  const activeBenchmark = selectorItems.find((item) => item.symbol === usSectorStockBenchmarkSymbol);
  const activeSector = selectorItems.find((item) => item.symbol === usSectorStockSymbol);
  const activeLabel = [getUsSectorStockLabel(activeBenchmark), getUsSectorStockLabel(activeSector)].filter(Boolean).join(" / ") || "目前指數";
  const scopeLabel = payload?.scopeLabel || getUsSectorStockLabel(activeSector) || getUsSectorStockLabel(activeBenchmark) || "目前類股";
  if (count) {
    const scopeText = payload?.scopeCount ? `｜觀察池 ${Number(payload.scopeCount).toLocaleString("zh-TW")} 檔` : "";
    count.textContent = payload?.scopeOnly
      ? usSectorNyseStockState.query
        ? `${scopeLabel} 搜尋結果：${Number(items.length).toLocaleString("zh-TW")} 檔`
        : `目前類股成分股：${Number(total).toLocaleString("zh-TW")} 檔`
      : usSectorNyseStockState.query
        ? `搜尋結果：${Number(items.length).toLocaleString("zh-TW")} 檔${scopeText}`
        : `上市個股清單：${Number(total).toLocaleString("zh-TW")} 檔${scopeText}`;
  }
  if (status) {
    const rangeText = items.length ? `第 ${Number(start + 1).toLocaleString("zh-TW")} - ${Number(Math.min(start + pageItems.length, items.length)).toLocaleString("zh-TW")} 筆` : "無結果";
    const scopeText = payload?.scopeCount ? ` · 已將 ${payload.scopeCount} 檔相關觀察池置頂` : "";
    status.textContent = payload?.scopeOnly
      ? `${payload?.source || "Yahoo Finance 成分股資料"} · ${rangeText} · 目前顯示：${scopeLabel} 成分股，與盤勢精選行情不同資料範圍${usSectorNyseStockState.query ? ` · 搜尋：${usSectorNyseStockState.query}` : ""}${payload?.error ? ` · 備援資料：${payload.error}` : ""}`
      : `${payload?.source || "NYSE Listings Directory"} · ${rangeText} · 目前參考：${activeLabel}${scopeText} · 此處為上市個股清單，不是盤勢精選行情總數${usSectorNyseStockState.query ? ` · 搜尋：${usSectorNyseStockState.query}` : ""}${payload?.error ? ` · 備援資料：${payload.error}` : ""}`;
  }
  if (!items.length) {
    table.innerHTML = '<div class="stock-detail-empty">目前沒有可顯示的美股個股明細。</div>';
    if (pager) pager.innerHTML = "";
    return;
  }
  table.innerHTML = `
    <table class="global-market-table us-sector-stock-table">
      <thead>
        <tr>
          <th>名稱</th>
          <th>代號</th>
          <th>交易所</th>
          <th>分類</th>
          <th>選取關聯</th>
          <th>資料來源</th>
        </tr>
      </thead>
      <tbody>
        ${pageItems.map((item) => {
    return `
          <tr>
            <td><a class="global-market-link" href="${safeUrl(buildUsStockSearchUrl(item.symbol))}">${escapeHtml(item.name || item.symbol || "--")}</a></td>
            <td>${escapeHtml(item.symbol || "--")}</td>
            <td>${escapeHtml(item.exchange || "NYSE")}</td>
            <td>${escapeHtml(item.group || item.type || "美股個股")}</td>
            <td>${item.scopeRelationText ? `<span class="chip chip-blue">${escapeHtml(item.scopeRelationText)}</span>` : '<span class="muted">全清單</span>'}</td>
            <td>${item.nyseUrl ? `<a class="global-market-link" href="${safeUrl(item.nyseUrl)}" target="_blank" rel="noopener noreferrer">NYSE</a>` : escapeHtml(item.source || "NYSE")}</td>
          </tr>
    `;
  }).join("")}
      </tbody>
    </table>
  `;
  if (pager) {
    pager.innerHTML = `
      <button type="button" data-us-sector-nyse-page="first" ${usSectorNyseStockState.page <= 1 ? "disabled" : ""}>第一頁</button>
      <button type="button" data-us-sector-nyse-page="prev" ${usSectorNyseStockState.page <= 1 ? "disabled" : ""}>上一頁</button>
      <span>第 <b>${usSectorNyseStockState.page}</b> / ${totalPages} 頁，每頁 ${US_NYSE_DIRECTORY_PAGE_SIZE} 筆</span>
      <button type="button" data-us-sector-nyse-page="next" ${usSectorNyseStockState.page >= totalPages ? "disabled" : ""}>下一頁</button>
      <button type="button" data-us-sector-nyse-page="last" ${usSectorNyseStockState.page >= totalPages ? "disabled" : ""}>最後頁</button>
    `;
  }
  syncUsSectorStockSelectorState();
}
function syncUsSectorStockSelectorState() {
  const section = document.getElementById("us-sector-stock-browser");
  if (!section) return;
  section.dataset.selectedBenchmark = usSectorStockBenchmarkSymbol || "";
  section.dataset.selectedSector = usSectorStockSymbol || "";
  section.querySelectorAll("[data-us-sector-stock]").forEach((node) => {
    const selected = node.dataset.usSectorStockRole === "benchmark"
      ? node.dataset.usSectorStock === usSectorStockBenchmarkSymbol
      : node.dataset.usSectorStock === usSectorStockSymbol;
    node.classList.toggle("is-active", selected);
    node.setAttribute("aria-pressed", selected ? "true" : "false");
  });
}
async function fetchUsSectorDirectoryPayload() {
  const queryParam = usSectorNyseStockState.query ? `&q=${encodeURIComponent(usSectorNyseStockState.query)}` : "";
  if (
    usSectorNyseStockState.directoryPayload
    && usSectorNyseStockState.directoryQuery === usSectorNyseStockState.query
  ) {
    return usSectorNyseStockState.directoryPayload;
  }
  let payload;
  try {
    const response = await fetchWithTimeout(`/api/us-market/nyse-listed?kind=stock&limit=7000${queryParam}`, { cache: "no-store" }, 26000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    payload = await response.json();
  } catch (primaryError) {
    const fallbackResponse = await fetchWithTimeout(`/api/us-market/listed?limit=8000${queryParam}`, { cache: "no-store" }, 26000);
    if (!fallbackResponse.ok) throw primaryError;
    const fallbackPayload = await fallbackResponse.json();
    const filtered = (fallbackPayload.results || []).filter((item) => item.group === "美股個股");
    payload = {
      ...fallbackPayload,
      source: `${fallbackPayload.source || "Nasdaq Trader 官方 Symbol Directory"}（NYSE API 備援）`,
      total: usSectorNyseStockState.query ? filtered.length : fallbackPayload.totals?.["美股個股"] || filtered.length,
      count: filtered.length,
      returned: filtered.length,
      results: filtered,
      error: primaryError?.message || String(primaryError),
    };
  }
  payload = { ...payload, items: payload.results || payload.items || [] };
  usSectorNyseStockState.directoryPayload = payload;
  usSectorNyseStockState.directoryQuery = usSectorNyseStockState.query;
  return payload;
}
async function fetchUsSectorScopePayload(symbol, roleLabel) {
  const cleanSymbol = normalizeUsScopeSymbol(symbol);
  if (!cleanSymbol) return null;
  const cacheKey = `${cleanSymbol}:${roleLabel}`;
  if (usSectorNyseStockState.scopeCache.has(cacheKey)) {
    return usSectorNyseStockState.scopeCache.get(cacheKey);
  }
  try {
    const response = await fetchWithTimeout(`/api/us-market/sector-stocks?sector=${encodeURIComponent(cleanSymbol)}&limit=30`, { cache: "no-store" }, 18000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const enriched = { ...payload, scopeRoleLabel: roleLabel };
    usSectorNyseStockState.scopeCache.set(cacheKey, enriched);
    return enriched;
  } catch (error) {
    return {
      sector: cleanSymbol,
      label: roleLabel,
      scopeRoleLabel: roleLabel,
      items: [],
      error: error?.message || String(error),
    };
  }
}
async function loadUsSectorStocks() {
  const table = document.getElementById("us-sector-stock-table");
  if (!table || (!usSectorStockBenchmarkSymbol && !usSectorStockSymbol)) return;
  const status = document.getElementById("us-sector-stock-status");
  try {
    const selectorItems = window.currentGlobalMarketPayload?.items || [];
    const benchmark = selectorItems.find((item) => item.symbol === usSectorStockBenchmarkSymbol);
    const sector = selectorItems.find((item) => item.symbol === usSectorStockSymbol);
    const focusSymbol = usSectorStockSymbol || usSectorStockBenchmarkSymbol;
    const focusLabel = getUsSectorStockLabel(sector || benchmark) || "目前類股";
    if (status) status.textContent = `正在載入 ${focusLabel} 成分股，並補齊 NYSE 交易所資料...`;
    table.innerHTML = `<div class="stock-detail-empty">${escapeHtml(focusLabel)} 成分股載入中。</div>`;
    const scopeRequests = [
      focusSymbol ? fetchUsSectorScopePayload(focusSymbol, `${focusLabel}成分股`) : null,
    ].filter(Boolean);
    const [directoryPayload, scopePayloads] = await Promise.all([
      fetchUsSectorDirectoryPayload(),
      Promise.all(scopeRequests),
    ]);
    renderUsSectorStockItems(mergeUsSectorDirectoryWithScope(directoryPayload, scopePayloads, {
      scopeOnly: Boolean(focusSymbol),
      scopeLabel: focusLabel,
    }));
  } catch (error) {
    if (status) status.textContent = `美股個股線上資料暫時無法載入：${error.message || error}`;
    table.innerHTML = '<div class="stock-detail-empty">美股個股線上資料載入失敗，請稍後重新整理。</div>';
  }
}
function bindUsSectorStocksBrowser() {
  const section = document.getElementById("us-sector-stock-browser");
  if (!section) return;
  syncUsSectorStockSelectorState();
  section.addEventListener("click", (event) => {
    const sectorButton = event.target.closest("[data-us-sector-stock]");
    if (sectorButton) {
      event.preventDefault();
      event.stopPropagation();
      const selectedSymbol = sectorButton.dataset.usSectorStock || "";
      if (sectorButton.dataset.usSectorStockRole === "benchmark") {
        usSectorStockBenchmarkSymbol = selectedSymbol || usSectorStockBenchmarkSymbol;
        const selectorItems = window.currentGlobalMarketPayload?.items || [];
        const sectorOptions = getUsSectorOptionsForBenchmark(selectorItems, usSectorStockBenchmarkSymbol);
        if (!sectorOptions.some((item) => item.symbol === usSectorStockSymbol)) {
          usSectorStockSymbol = sectorOptions[0]?.symbol || "";
        }
        saveUsSectorStockSelection();
        const replacement = renderUsSectorStocksBrowser(window.currentGlobalMarketPayload);
        if (replacement) {
          section.outerHTML = replacement;
          bindUsSectorStocksBrowser();
        }
        usSectorNyseStockState.page = 1;
        loadUsSectorStocks();
        return;
      } else {
        usSectorStockSymbol = selectedSymbol || usSectorStockSymbol;
      }
      saveUsSectorStockSelection();
      syncUsSectorStockSelectorState();
      const selectorItems = window.currentGlobalMarketPayload?.items || [];
      const activeBenchmark = selectorItems.find((item) => item.symbol === usSectorStockBenchmarkSymbol);
      const activeSector = selectorItems.find((item) => item.symbol === usSectorStockSymbol);
      const active = activeSector || activeBenchmark;
      const summary = document.getElementById("us-sector-index-summary");
      if (summary && active) {
        const activeTone = (parseMarketNumber(active.pct) || 0) > 0 ? "up" : (parseMarketNumber(active.pct) || 0) < 0 ? "down" : "flat";
        summary.className = `us-sector-index-summary is-${activeTone}`;
        summary.innerHTML = renderUsSectorIndexSummaryContent(activeBenchmark, activeSector);
      }
      const label = sectorButton.textContent.trim();
      const status = document.getElementById("us-sector-stock-status");
      if (status) {
        const activeLabel = [getUsSectorStockLabel(activeBenchmark), getUsSectorStockLabel(activeSector)].filter(Boolean).join(" / ");
        status.textContent = `目前參考已切換為 ${activeLabel || label}，正在套用觀察池與全清單排序。`;
      }
      usSectorNyseStockState.page = 1;
      loadUsSectorStocks();
      syncUsSectorStockSelectorState();
      return;
    }
  });
  section.querySelector("[data-us-sector-nyse-search-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.getElementById("us-sector-nyse-search");
    usSectorNyseStockState.query = (input?.value || "").trim();
    usSectorNyseStockState.page = 1;
    loadUsSectorStocks();
  });
  section.querySelector("[data-us-sector-nyse-reset]")?.addEventListener("click", () => {
    const input = document.getElementById("us-sector-nyse-search");
    if (input) input.value = "";
    usSectorNyseStockState.query = "";
    usSectorNyseStockState.page = 1;
    loadUsSectorStocks();
  });
  section.addEventListener("click", (event) => {
    const button = event.target.closest("[data-us-sector-nyse-page]");
    if (!button) return;
    const items = usSectorNyseStockState.payload?.items || usSectorNyseStockState.payload?.results || [];
    const totalPages = Math.max(Math.ceil(items.length / US_NYSE_DIRECTORY_PAGE_SIZE), 1);
    if (button.dataset.usSectorNysePage === "first") usSectorNyseStockState.page = 1;
    if (button.dataset.usSectorNysePage === "prev") usSectorNyseStockState.page = Math.max(1, usSectorNyseStockState.page - 1);
    if (button.dataset.usSectorNysePage === "next") usSectorNyseStockState.page = Math.min(totalPages, usSectorNyseStockState.page + 1);
    if (button.dataset.usSectorNysePage === "last") usSectorNyseStockState.page = totalPages;
    if (usSectorNyseStockState.payload) renderUsSectorStockItems(usSectorNyseStockState.payload);
  });
}
function renderGlobalMarketSections(items = []) {
  const groups = [];
  (items || []).forEach((item) => {
    const groupName = item.group || item.type || "市場商品";
    let group = groups.find((entry) => entry.name === groupName);
    if (!group) {
      group = { name: groupName, items: [] };
      groups.push(group);
    }
    group.items.push(item);
  });
  if (groups.length <= 1) {
    return `<div class="global-market-grid">${renderGlobalMarketCards(items)}</div>`;
  }
  return groups.map((group) => `
    <section class="global-market-group">
      <div class="global-group-heading">
        <div>
          <p class="panel-kicker">Yahoo Finance</p>
          <h3>${escapeHtml(group.name)}</h3>
        </div>
        <span class="chip chip-blue">${group.items.length} 檔</span>
      </div>
      <div class="global-market-grid">
        ${renderGlobalMarketCards(group.items)}
      </div>
    </section>
  `).join("");
}
function getUsMarketPayloadCounts(payload = {}) {
  const items = Array.isArray(payload.items) ? payload.items : [];
  const quoteCount = Number(payload.loadedCount) || items.length;
  const usableCount = Number(payload?.summary?.count) || items.filter((item) => !item.error && Number.isFinite(parseMarketNumber(item.close))).length;
  const majorCount = items.filter((item) => item.group === "主要指數" || item.symbol === "^VIX").length;
  const sectorCount = items.filter((item) => item.group === "美股類股指數").length;
  const stockCount = items.filter((item) => item.group === "美股個股").length;
  const etfCount = items.filter((item) => item.group === "美股 ETF").length;
  return { quoteCount, usableCount, majorCount, sectorCount, stockCount, etfCount };
}
function renderUsMarketScopeNote(payload = {}) {
  const counts = getUsMarketPayloadCounts(payload);
  const etfText = counts.etfCount ? `、ETF ${Number(counts.etfCount).toLocaleString("zh-TW")} 筆` : "";
  return `
    <p class="source-note us-market-scope-note">
      盤勢精選行情 ${Number(counts.quoteCount).toLocaleString("zh-TW")} 筆，包含主要指數 / VIX ${Number(counts.majorCount).toLocaleString("zh-TW")} 筆、類股指數 ${Number(counts.sectorCount).toLocaleString("zh-TW")} 筆、代表性個股 ${Number(counts.stockCount).toLocaleString("zh-TW")} 筆${etfText}；個股明細使用 NYSE / Nasdaq 上市清單或所選類股成分股，兩者不是同一個總數。
    </p>
  `;
}
function renderUsPlatformDashboard(payload) {
  const summary = payload?.summary || {};
  const counts = getUsMarketPayloadCounts(payload);
  const modules = [
    {
      title: "首頁",
      en: "Dashboard",
      tone: "blue",
      href: "us-stocks.html",
      desc: "集中查看美股指數、風險情緒、熱門股票與 ETF。",
      items: ["S&P 500", "NASDAQ", "Dow Jones", "Russell 2000"],
    },
    {
      title: "市場總覽",
      en: "Market Overview",
      tone: "green",
      href: "#us-market-overview",
      desc: "看指數行情、產業板塊、漲跌排行、成交量與資金流向。",
      items: ["指數行情", "產業板塊", "漲跌排行", "成交量排行"],
    },
    {
      title: "個股分析",
      en: "Stock Analysis",
      tone: "orange",
      href: "us-stock-search.html",
      desc: "搜尋美股個股，查看走勢圖、技術分析與 AI 趨勢風向。",
      items: ["公司資訊", "基本面", "技術分析", "AI 評分"],
    },
    {
      title: "ETF 分析",
      en: "ETF Center",
      tone: "gold",
      href: "us-etf.html",
      desc: "進入美股ETF獨立頁，依指數、產業、債券、REITs、槓桿與反向分類觀察。",
      items: ["ETF 總覽", "ETF 分類", "配息分析", "AI ETF 評分"],
    },
    {
      title: "衍生性金融商品",
      en: "Derivatives",
      tone: "purple",
      href: "options.html",
      desc: "整合選擇權、期貨與波動率，用於風險控管與避險判斷。",
      items: ["Options", "Futures", "Greeks", "IV 分析"],
    },
    {
      title: "AI 選股中心",
      en: "AI Stock Screener",
      tone: "cyan",
      href: "#us-ai-screener",
      desc: "依成長、價值、高股息、動能與籌碼條件建立觀察名單。",
      items: ["成長股", "價值股", "動能股", "AI 推薦"],
    },
    {
      title: "自選股中心",
      en: "Watchlist",
      tone: "red",
      href: "tw-Optional-stocks.html",
      desc: "管理追蹤清單、異動通知與 AI 監控。",
      items: ["我的自選股", "追蹤清單", "異動通知", "AI 監控"],
    },
    {
      title: "投資組合管理",
      en: "Portfolio",
      tone: "blue",
      href: "tw-Optional-stocks.html#portfolio",
      desc: "評估資產配置、投資組合績效、Sharpe、Beta、Alpha 與最大回撤。",
      items: ["資產配置", "績效", "VaR", "最大回撤"],
    },
    {
      title: "模擬交易系統",
      en: "Paper Trading",
      tone: "green",
      href: "#us-paper-trading",
      desc: "以模擬買賣驗證策略，追蹤損益與交易紀律。",
      items: ["模擬買進", "模擬賣出", "模擬 ETF", "損益統計"],
    },
    {
      title: "AI 投資顧問",
      en: "AI Advisor",
      tone: "orange",
      href: "#us-ai-advisor",
      desc: "整合市場、個股、風險與投資建議，輸出 AI 分析報告。",
      items: ["市場分析", "個股診斷", "風險評估", "投資報告"],
    },
    {
      title: "風險管理中心",
      en: "Risk Management",
      tone: "purple",
      href: "#us-risk",
      desc: "用 VaR、壓力測試、Monte Carlo 與 Black-Scholes 衡量風險。",
      items: ["VaR", "壓力測試", "Monte Carlo", "Black-Scholes"],
    },
    {
      title: "新聞與研究中心",
      en: "News & Research",
      tone: "blue",
      href: "#us-news",
      desc: "整理即時新聞、財報日曆、經濟數據、FED 動態與研究摘要。",
      items: ["即時新聞", "財報日曆", "FED 動態", "AI 摘要"],
    },
    {
      title: "學習中心",
      en: "Learning Center",
      tone: "green",
      href: "#us-learning",
      desc: "提供股票、ETF、選擇權、技術分析與基本面教學入口。",
      items: ["股票教學", "ETF 教學", "技術分析", "策略課程"],
    },
    {
      title: "系統管理",
      en: "System Admin",
      tone: "orange",
      href: "#us-admin",
      desc: "處理 API、通知、資料同步與系統監控設定。",
      items: ["API 設定", "通知設定", "資料同步", "系統監控"],
    },
  ];
  return `
    <section class="section us-platform-section">
      <article class="panel-card us-platform-dashboard">
        <div class="us-platform-head">
          <p class="eyebrow">US Market Data</p>
          <h2>美股市場資料中心</h2>
          <p>整合美股總覽、個股分析、ETF 搜尋與跨資產資料入口，集中查看行情、技術與風險訊號。</p>
        </div>
        <div class="us-platform-snapshot">
          <span><b>${counts.quoteCount || summary.count || "--"}</b><small>盤勢精選行情</small></span>
          <span><b>${summary.advancers ?? "--"} / ${summary.decliners ?? "--"}</b><small>上漲 / 下跌</small></span>
          <span><b>${escapeHtml(summary.avgPct || "--")}</b><small>平均漲跌幅</small></span>
          <span><b>${counts.stockCount || "--"}</b><small>代表個股樣本</small></span>
        </div>
        ${renderUsMarketScopeNote(payload)}
        <div class="us-module-grid">
          ${modules.map((module, index) => `
            <a class="us-module-card is-${module.tone}" href="${safeUrl(module.href)}">
              <span class="us-module-number">${index + 1}</span>
              <div>
                <strong>${escapeHtml(module.title)}</strong>
                <small>${escapeHtml(module.en)}</small>
              </div>
              <p>${escapeHtml(module.desc)}</p>
              <div class="us-module-tags">${module.items.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
            </a>
          `).join("")}
        </div>
        <div class="us-support-grid">
          <section>
            <h3>平台核心技術與數據引擎</h3>
            <div>${["即時行情數據", "財報數據庫", "AI 大數據引擎", "策略回測引擎", "RAG 財報知識庫", "多市場整合"].map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          </section>
          <section>
            <h3>AI 多模型分析引擎</h3>
            <div>${["市場分析模型", "基本面模型", "技術分析模型", "籌碼分析模型", "風險管理模型", "投資組合模型", "學習校準模型"].map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          </section>
        </div>
      </article>
    </section>
  `;
}
function renderUsPlatformArchitecture() {
  return `
    <section class="section us-platform-section">
      <article class="panel-card us-platform-dashboard">
        <div class="us-platform-head">
          <p class="eyebrow">US Market Data</p>
          <h2>美股市場資料中心</h2>
          <p>市場資料模組正在載入。</p>
        </div>
        <div class="us-support-grid">
          <section>
            <h3>平台核心技術與數據引擎</h3>
            <div><span>即時行情數據</span><span>策略回測引擎</span><span>AI 大數據引擎</span></div>
          </section>
          <section>
          <h3>AI 多模型分析引擎</h3>
            <div><span>市場分析模型</span><span>技術分析模型</span><span>風險管理模型</span></div>
          </section>
        </div>
      </article>
    </section>
  `;
}
function getAssetPlatformConfig(category, title) {
  const configs = {
    "us-stocks": {
      kicker: "US Market Data",
      title: "美股市場資料中心",
      intro: "以美股市場、盤勢總覽、個股/ETF 搜尋、衍生資產與美股自選股管理建立每日觀察流程。",
      modules: [
        ["美股市場", "US Market", "blue", "us-stocks.html", "保留原本美股市場頁，集中查看主要指數、類股比對、個股清單與 ETF 入口。", ["S&P 500", "NASDAQ", "Dow Jones", "Russell 2000"]],
        ["美股盤勢", "Market Overview", "green", "us-market-overview.html", "以台股盤勢同格式整理指數行情、VIX、類股排行與盤後快訊。", ["指數行情", "產業板塊", "漲跌排行", "成交量排行"]],
        ["個股分析", "Stock Analysis", "orange", "us-stock-search.html", "進入美股個股搜尋，查看公司行情、技術走勢與 AI 趨勢風向。", ["公司資訊", "技術分析", "AI 評分", "風險摘要"]],
        ["ETF 分析", "ETF Center", "gold", "us-etf.html", "進入美股ETF獨立頁，觀察總覽、分類、排行、比較、配息、風險與 AI 摘要。", ["ETF 總覽", "ETF 分類", "排行比較", "AI ETF 評分"]],
        ["美股自選股", "US Watchlist", "cyan", "us-watchlist.html", "建立美股與 ETF 自選清單，集中追蹤價格、漲跌與技術分析。", ["我的自選", "即時報價", "快速分析", "Yahoo 資料"]],
        ["期權中心", "Futures & Options", "purple", "derivatives-assets.html", "集中查看期貨、選擇權、波動率與未平倉資料。", ["Futures", "Options", "VIX", "Open Interest"]],
        ["貴金屬與債券", "Metals & Bonds", "gold", "international-finance.html", "集中查看債券、殖利率曲線、貴金屬與避險資產。", ["Bonds", "Yield", "Metals", "Gold"]],
        ["追蹤清單", "Tracking List", "red", "us-watchlist.html#tracking", "針對關注標的做分組、移除與查看分析，方便每日檢查。", ["持續追蹤", "分組管理", "個股連結", "ETF 觀察"]],
        ["AI 監控", "AI Monitor", "blue", "us-watchlist.html#alerts", "以自選股為基礎輸出技術風向、風險提示與後續觀察重點。", ["AI 摘要", "風險提示", "技術訊號", "投組觀察"]],
      ],
    },
    futures: {
      kicker: "Global Futures Analysis Center",
      title: "全球期貨分析中心",
      intro: "整合台灣、美國與國際期貨市場，提供行情、技術分析、籌碼分析、風險控管與 AI 趨勢判斷。",
      modules: [
        ["全球期貨主控台", "Dashboard", "blue", "futures.html#futures-analysis-center", "整合台灣、美國與國際期貨市場的線上資料與 AI 主結論。", ["台灣", "美國", "國際", "AI"]],
        ["三大市場框架", "Market framework", "green", "futures.html#futures-analysis-center", "依台灣期貨、美國期貨與國際期貨分層整理商品與來源。", ["TAIFEX", "CME", "ICE", "SGX"]],
        ["AI 期貨分析模組", "AI futures", "cyan", "futures.html#futures-analysis-center", "輸出趨勢、多空分數、支撐壓力、波動、籌碼與風險等級。", ["趨勢", "多空", "籌碼", "風險"]],
        ["商品與分析矩陣", "Product matrix", "orange", "futures.html#futures-analysis-center", "把金融期貨、商品期貨、技術分析、籌碼分析與風控放在同一架構。", ["金融", "商品", "技術", "風控"]],
        ["期貨線上資料", "Live data", "purple", "futures.html#asset-futures", "保留 TAIFEX 官方未平倉、地區市場分組與線上資料明細。", ["未平倉", "地區", "明細", "量能"]],
        ["期貨技術走勢", "Technical", "gold", "futures.html#futures-detail", "只對有足夠歷史序列的商品繪製走勢，避免空圖或推估。", ["走勢", "均線", "支撐", "壓力"]],
      ],
    },
    options: {
      kicker: "Options",
      title: "市場選擇權鏈",
      intro: "整合市場選擇權鏈、AI 盤勢摘要、VIX 情緒、地區市場與線上明細。",
      modules: [
        ["市場選擇權鏈", "TAIFEX option chain", "green", "options.html#asset-options", "對應 Call / Put、履約價、成交量、未平倉與 IV 表格。", ["Call", "Put", "Strike", "OI"]],
        ["台灣選擇權 AI 盤勢摘要", "AI analysis", "cyan", "derivatives-analytics.html#derivative-ai-options", "對應市場選擇權鏈、PCR 與最大痛點的 AI 盤勢摘要。", ["方向", "理由", "情境", "風險"]],
        ["CBOE VIX 市場情緒", "Volatility signal", "purple", "options.html#asset-options", "對應 VIX 數值、情緒區間與風險溫度。", ["VIX", "樂觀", "警戒", "恐慌"]],
        ["選擇權觀察線上資料明細", "Online data", "orange", "options.html#asset-options", "對應選擇權觀察標的線上明細表。", ["名稱", "代號", "來源", "日期"]],
      ],
    },
    "precious-metals": {
      kicker: "Precious Metals Platform",
      title: "貴金屬避險分析平台",
      intro: "整合黃金、白銀、鉑金、鈀金與相關 ETF，觀察美元、利率與避險資金。",
      modules: [
        ["貴金屬總覽", "Dashboard", "blue", "precious-metals.html", "查看黃金、白銀、鉑金與鈀金走勢。", ["Gold", "Silver", "Platinum", "Palladium"]],
        ["避險情緒", "Safe Haven", "green", "#metals-sentiment", "搭配美元、利率與 VIX 判斷避險需求。", ["美元", "利率", "VIX", "地緣風險"]],
        ["ETF 中心", "ETF Center", "gold", "us-stock-search.html?q=Gold ETF", "追蹤 GLD、IAU、SLV 等金屬 ETF。", ["GLD", "IAU", "SLV", "USO"]],
        ["技術分析", "Technical", "orange", "#us-market-overview", "以均線、支撐壓力、突破與回撤判斷趨勢。", ["均線", "突破", "回撤", "壓力"]],
        ["資金流向", "Flow", "purple", "#metals-flow", "觀察 ETF 資金、期貨倉位與避險輪動。", ["ETF Flow", "期貨倉位", "美元", "債券"]],
        ["AI 觀察", "AI Insight", "cyan", "#metals-ai", "產出避險、通膨與利率情境下的操作節奏。", ["通膨", "降息", "避險", "突破"]],
      ],
    },
    bonds: {
      kicker: "Bonds Platform",
      title: "債券與殖利率分析平台",
      intro: "以美債殖利率曲線、債券 ETF、信用利差與久期風險建立債券分析流程。",
      modules: [
        ["債券總覽", "Dashboard", "blue", "bonds.html", "查看短中長天期殖利率與債券 ETF。", ["IRX", "FVX", "TNX", "TYX"]],
        ["殖利率曲線", "Yield Curve", "green", "#bond-yield-curve", "觀察短端、長端與倒掛/陡峭化。", ["短端", "長端", "倒掛", "陡峭化"]],
        ["債券 ETF", "Bond ETF", "gold", "us-stock-search.html?q=Bond ETF", "追蹤 SHY、IEF、TLT、BND、AGG 等 ETF。", ["SHY", "IEF", "TLT", "BND"]],
        ["信用風險", "Credit Risk", "orange", "#bond-credit", "觀察投資級與高收益債 ETF 風險偏好。", ["LQD", "HYG", "Spread", "Default"]],
        ["久期管理", "Duration", "purple", "#bond-duration", "用久期、凸性與利率敏感度控管部位。", ["Duration", "Convexity", "DV01", "Rate"]],
        ["AI 利率情境", "AI Rate Scenario", "cyan", "#bond-ai", "整合 Fed、通膨與就業數據產出利率情境。", ["Fed", "CPI", "就業", "降息"]],
      ],
    },
  };
  return configs[category] || {
    kicker: "Asset Platform",
    title: `${title || "全球市場"}分析平台`,
    intro: "整合行情、技術、風險與 AI 分析模組。",
    modules: [["市場總覽", "Overview", "blue", "#us-market-overview", "查看行情與市場脈絡。", ["行情", "趨勢", "風險"]]],
  };
}
function renderAssetPlatformDashboard(payload) {
  const summary = payload?.summary || {};
  const config = getAssetPlatformConfig(payload?.category, payload?.title);
  return `
    <section class="section us-platform-section">
      <article class="panel-card us-platform-dashboard">
        <div class="us-platform-head">
          <p class="eyebrow">${escapeHtml(config.kicker)}</p>
          <h2>${escapeHtml(config.title)}</h2>
          <p>${escapeHtml(config.intro)}</p>
        </div>
        <div class="us-platform-snapshot">
          <span><b>${summary.count ?? "--"}</b><small>追蹤商品</small></span>
          <span><b>${summary.advancers ?? "--"} / ${summary.decliners ?? "--"}</b><small>上漲 / 下跌</small></span>
          <span><b>${escapeHtml(summary.avgPct || "--")}</b><small>平均漲跌幅</small></span>
          <span><b>${escapeHtml(summary.strongest || "--")}</b><small>最強勢</small></span>
        </div>
        <div class="us-module-grid">
          ${config.modules.map((module, index) => {
            const [title, en, tone, href, desc, items] = module;
            return `
              <a class="us-module-card is-${tone}" href="${safeUrl(href)}">
                <span class="us-module-number">${index + 1}</span>
                <div>
                  <strong>${escapeHtml(title)}</strong>
                  <small>${escapeHtml(en)}</small>
                </div>
                <p>${escapeHtml(desc)}</p>
                <div class="us-module-tags">${items.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
              </a>
            `;
          }).join("")}
        </div>
        <div class="us-support-grid">
          <section>
            <h3>資料與策略模組</h3>
            <div>${["線上行情", "技術指標", "策略回測", "風險模型", "AI 摘要"].map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          </section>
          <section>
            <h3>AI 多模型分析</h3>
            <div>${["市場模型", "技術模型", "風險模型", "投組模型", "學習模型"].map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          </section>
        </div>
      </article>
    </section>
  `;
}
function renderDerivativeNameMappingCard(key) {
  const config = DERIVATIVE_ASSET_NAME_MAP[key];
  if (!config) return "";
  return `
    <section class="section">
      <article class="panel-card global-table-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">Name mapping</p>
            <h3>${escapeHtml(config.sourceName)} 一名稱對應導入</h3>
            <p class="chart-subtitle">左側為 derivatives-assets.html 的原區塊名稱，右側為目前頁面使用的同名區塊。</p>
          </div>
          <a class="global-refresh" href="${safeUrl(config.sourceHref)}">回到來源區塊</a>
        </div>
        <div class="global-table-wrap">
          <table class="global-market-table">
            <thead><tr><th>derivatives-assets.html 原名稱</th><th>${escapeHtml(config.targetName)} 導入名稱</th></tr></thead>
            <tbody>
              ${config.rows.map(([source, target]) => `<tr><td>${escapeHtml(source)}</td><td><strong>${escapeHtml(target)}</strong></td></tr>`).join("")}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  `;
}
function readDerivativesWatchlist() {
  try {
    const items = JSON.parse(localStorage.getItem(DERIVATIVES_WATCHLIST_STORAGE_KEY) || "[]");
    return Array.isArray(items) ? items : [];
  } catch (error) {
    return [];
  }
}
function hasDerivativeWatchSymbol(symbol) {
  const cleanSymbol = String(symbol || "").toUpperCase();
  return readDerivativesWatchlist().some((item) => String(item?.symbol || "").toUpperCase() === cleanSymbol);
}
function renderDerivativeWatchButton(symbol, name, type) {
  const watching = hasDerivativeWatchSymbol(symbol);
  return `<button class="global-refresh" type="button" data-derivative-watch-symbol="${escapeHtml(symbol)}" data-derivative-watch-name="${escapeHtml(name)}" data-derivative-watch-type="${escapeHtml(type)}">${watching ? "移除自選" : "加入自選"}</button>`;
}
function bindDerivativeWatchlistControls(payload) {
  const root = document.getElementById("global-market-root");
  root?.querySelectorAll("[data-derivative-watch-symbol]").forEach((button) => {
    button.addEventListener("click", () => {
      const symbol = String(button.dataset.derivativeWatchSymbol || "").toUpperCase();
      if (!symbol) return;
      const items = readDerivativesWatchlist();
      const index = items.findIndex((item) => String(item?.symbol || "").toUpperCase() === symbol);
      if (index >= 0) {
        items.splice(index, 1);
      } else {
        items.push({
          symbol,
          name: button.dataset.derivativeWatchName || symbol,
          type: button.dataset.derivativeWatchType || "derivative",
          addedAt: new Date().toISOString(),
        });
      }
      localStorage.setItem(DERIVATIVES_WATCHLIST_STORAGE_KEY, JSON.stringify(items));
      renderGlobalMarketPage(payload);
    });
  });
}
function getFuturesMarketScope(item) {
  const region = getAssetHubRegion(item);
  const exchange = String(item?.exchange || item?.dataSource || "").toUpperCase();
  if (region === "台灣" || /TAIFEX/.test(exchange)) return "taiwan";
  if (/ICE|SGX|JPX|HKEX|EUREX/.test(exchange)) return "international";
  if (/CME|CBOT|NYMEX|COMEX/.test(exchange) || region === "美國") return "us";
  return "international";
}
function buildFuturesCenterModel(payload = {}) {
  const items = getAssetHubItems(payload);
  const usable = getAssetHubUsableItems(payload);
  const taiwanItems = items.filter((item) => getFuturesMarketScope(item) === "taiwan");
  const usItems = items.filter((item) => getFuturesMarketScope(item) === "us");
  const internationalItems = items.filter((item) => getFuturesMarketScope(item) === "international");
  const futuresMarketBreakdown = (payload.futuresMarketBreakdown || []).reduce((map, item) => {
    if (item?.key) map[item.key] = item;
    return map;
  }, {});
  const strongest = usable
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(right.pct) || -999) - (parseMarketNumber(left.pct) || -999))[0] || null;
  const weakest = usable
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(left.pct) || 999) - (parseMarketNumber(right.pct) || 999))[0] || null;
  const pctValues = usable.map((item) => parseMarketNumber(item?.pct)).filter(Number.isFinite);
  const avgPct = pctValues.length ? pctValues.reduce((sum, value) => sum + value, 0) / pctValues.length : null;
  const advancers = pctValues.filter((value) => value > 0).length;
  const decliners = pctValues.filter((value) => value < 0).length;
  const taifexContracts = ["TX", "MTX", "TMF", "TE", "TF", "XIF", "SOF"].map((symbol) => findAssetHubItem(payload, symbol)).filter(Boolean);
  const aiScore = Math.round(clampAssetHubScore(
    50
      + (Number.isFinite(avgPct) ? avgPct * 4 : 0)
      + (strongest ? 8 : 0)
      - (weakest && parseMarketNumber(weakest.pct) < -2 ? 6 : 0),
    18,
    92,
  ));
  const aiTone = aiScore >= 62 ? "up" : aiScore <= 42 ? "down" : "flat";
  return {
    items,
    usable,
    taiwanItems,
    usItems,
    internationalItems,
    strongest,
    weakest,
    avgPct,
    advancers,
    decliners,
    taifexContracts,
    aiScore,
    aiTone,
    futuresMarketBreakdown,
    sourceInfo: payload.sourceInfo || {},
    updatedAt: payload.updatedAt || "",
    catalogCount: Number(payload.catalogCount) || items.length,
  };
}
function renderFuturesCenterHero(payload, model) {
  const leaderText = model.strongest
    ? `${model.strongest.name || model.strongest.symbol} ${model.strongest.pct || "--"}`
    : "等待期貨線上行情同步";
  const decisionText = model.aiTone === "up"
    ? "多方動能較強，優先觀察股指、能源與金屬期貨是否同步擴散。"
    : model.aiTone === "down"
      ? "風險偏保守，先看未平倉量、波動與支撐是否止穩。"
      : "市場方向尚未一致，適合用台灣、美國、國際三組市場分層確認。";
  const stats = [
    ["線上資料", `${model.usable.length} / ${model.catalogCount}`, "可用 / 目錄"],
    ["台灣", `${model.taiwanItems.length} 檔`, "TAIFEX"],
    ["美國", `${model.usItems.length} 檔`, "CME / CBOT"],
    ["國際", `${model.internationalItems.length} 檔`, "ICE / SGX"],
    ["漲跌廣度", `${model.advancers} / ${model.decliners}`, "上漲 / 下跌"],
    ["相對強勢", model.strongest?.symbol || "--", model.strongest?.pct || "--"],
  ];
  const flow = [
    ["行情", "Yahoo / TAIFEX"],
    ["分類", "台灣 / 美國 / 國際"],
    ["技術", "走勢 / 支撐壓力"],
    ["籌碼", "未平倉 / 量能"],
    ["風控", "槓桿 / 停損"],
    ["AI", "趨勢分數"],
  ];
  return `
    <article class="panel-card futures-center-hero-card">
      <div class="futures-center-hero-layout">
        <div class="futures-center-title-block">
          <div class="futures-center-title-row">
            <div>
              <p class="panel-kicker">Global futures analysis center</p>
              <h3>全球期貨分析中心</h3>
            </div>
            <span class="chip chip-blue">${escapeHtml(payload?.updatedAt || "--")}</span>
          </div>
          <p class="chart-subtitle">整合台灣、美國與國際期貨市場，將行情、技術分析、籌碼分析、風險控管與 AI 趨勢判斷收斂成同一個期貨決策台。</p>
          <p class="futures-center-ai-brief is-${model.aiTone}"><b>AI 期貨主結論</b><span>${escapeHtml(`${decisionText} 目前相對強勢：${leaderText}。`)}</span></p>
          <div class="futures-center-flow">
            ${flow.map(([label, text]) => `<span><b>${escapeHtml(label)}</b><small>${escapeHtml(text)}</small></span>`).join("")}
          </div>
        </div>
        <div class="futures-center-decision-panel is-${model.aiTone}">
          <small>AI futures score</small>
          <strong>${model.aiScore}<em>/100</em></strong>
          <p>${escapeHtml(decisionText)}</p>
        </div>
      </div>
      <div class="futures-center-hero-grid">
        ${stats.map(([label, value, detail]) => `
          <span>
            <small>${escapeHtml(label)}</small>
            <b>${escapeHtml(value)}</b>
            <em>${escapeHtml(detail)}</em>
          </span>
        `).join("")}
      </div>
      ${renderFuturesCenterRegionalMarket(payload)}
    </article>
  `;
}
function getFuturesRegionToggleKey(region) {
  const text = String(region || "其他").trim();
  if (text.includes("台灣")) return "taiwan";
  if (text.includes("美國")) return "us";
  if (text.includes("歐洲")) return "europe";
  if (text.includes("亞洲")) return "asia";
  const hash = Array.from(text).reduce((sum, character) => sum + character.charCodeAt(0), 0);
  return `other-${hash || "region"}`;
}
function renderFuturesCenterRegionalMarket(payload) {
  const items = getAssetHubItems(payload);
  const groups = groupAssetHubItemsByRegion(items);
  if (!groups.length) {
    return `
      <div class="futures-center-region-map is-empty">
        <p class="stock-detail-empty">期貨地區市場資料同步中。</p>
      </div>
    `;
  }
  const summaryGroups = groups.map((group) => {
    const usableCount = group.items.filter((item) => !item.error && Number.isFinite(parseMarketNumber(item.close))).length;
    const strongest = group.items
      .map((item) => ({ item, pct: parseMarketNumber(item?.pct) }))
      .filter((entry) => Number.isFinite(entry.pct))
      .sort((left, right) => right.pct - left.pct)[0]?.item || null;
    const key = getFuturesRegionToggleKey(group.region);
    return { group, usableCount, strongest, key, expanded: derivativesFuturesRegionalExpandedKeys.has(key) };
  });
  return `
    <div class="futures-center-region-map is-individual-collapse">
      <div class="futures-center-region-head">
        <div>
          <p class="panel-kicker">Regional market map</p>
          <h4>期貨地區市場</h4>
        </div>
        <span>${items.length} 筆</span>
        <em class="futures-center-region-hint">台灣 / 美國 / 歐洲 / 亞洲個別收放</em>
      </div>
      <div class="asset-hub-region-groups futures-center-region-groups">
        ${summaryGroups.map(({ group, usableCount, strongest, key, expanded }) => `
          <section class="asset-hub-region-block futures-center-region-block ${expanded ? "is-expanded" : "is-collapsed"}">
            <div class="asset-hub-region-head futures-center-region-block-head">
              <div>
                <strong>${escapeHtml(group.region)}</strong>
                <small>${usableCount} / ${group.items.length} 筆有效</small>
              </div>
              <button class="global-refresh asset-hub-region-toggle" type="button" data-futures-region-toggle="${escapeHtml(key)}" aria-expanded="${expanded ? "true" : "false"}">${expanded ? "收合" : "展開"}</button>
            </div>
            ${expanded ? renderAssetHubQuoteGrid(group.items, "期貨資料同步中。") : `
              <div class="futures-center-region-mini">
                <span><b>${usableCount}</b><small>有效資料</small></span>
                <span><b>${escapeHtml(strongest?.symbol || "--")}</b><small>${escapeHtml(strongest?.pct || "等待同步")}</small></span>
              </div>
            `}
          </section>
        `).join("")}
      </div>
    </div>
  `;
}
function renderFuturesInvestmentLiveDataPanel(model) {
  const leader = model.usable
    .filter((item) => (item.series || []).length >= 30)
    .sort((a, b) => (parseMarketNumber(b.pct) || -Infinity) - (parseMarketNumber(a.pct) || -Infinity))[0]
    || model.strongest;
  const contracts = model.taifexContracts.slice(0, 6);
  const leaderText = leader
    ? `${leader.name || leader.symbol} ${leader.pct || "--"}`
    : "等待 Yahoo Finance 與 TAIFEX 同步";
  const loadedText = `${model.usable.length} / ${model.catalogCount}`;
  const quoteSourceUrl = leader?.quoteSourceUrl || leader?.sourceLink || "";
  const officialSourceUrl = contracts.find((item) => item.taifexSourceLink || item.sourceUrl)?.taifexSourceLink
    || contracts.find((item) => item.sourceUrl)?.sourceUrl
    || "";
  return `
    <div class="futures-investment-note futures-investment-live-note">
      <p>專業判讀原則：價格走勢只使用已取得足夠歷史序列的商品；未平倉、期現貨價差、五檔與逐筆成交若未接入合法線上來源，保留為資料欄位，不用推估值替代。</p>
      <div class="futures-investment-live-data">
        <section class="futures-investment-live-card">
          <small>Live futures data</small>
          <h5>期貨線上資料與官方未平倉</h5>
          <strong>${escapeHtml(leader?.name || "等待資料")}</strong>
          <p>${leader ? `${leaderText}，可搭配股指期貨、美債期貨與台指期貨未平倉確認風險偏好。` : "等待線上行情同步後，將呈現最強期貨與跨市場判讀。"}</p>
          <div class="futures-investment-live-metrics">
            <span><b>${escapeHtml(loadedText)}</b><small>線上資料</small></span>
            <span><b>${escapeHtml(model.updatedAt || "--")}</b><small>更新時間</small></span>
            <span><b>${escapeHtml(leader?.symbol || "--")}</b><small>相對強勢</small></span>
            <span><b>${contracts.length}</b><small>TAIFEX 契約</small></span>
          </div>
          <div class="futures-investment-source-row">
            ${quoteSourceUrl ? `<a href="${safeUrl(quoteSourceUrl)}" target="_blank" rel="noopener noreferrer">Yahoo 未平倉&十大</a>` : ""}
            ${officialSourceUrl ? `<a href="${safeUrl(officialSourceUrl)}" target="_blank" rel="noopener noreferrer">TAIFEX 官方日報</a>` : ""}
          </div>
          <em>期貨具槓桿與到期特性，請搭配保證金與停損管理。</em>
        </section>
        <section class="futures-investment-oi-card">
          <div class="futures-investment-oi-head">
            <div>
              <small>TAIFEX futures</small>
              <h5>國內期貨未平倉資料</h5>
            </div>
            <em>官方日報</em>
          </div>
          ${contracts.length ? `
            <div class="futures-investment-oi-grid">
              ${contracts.map((item) => `
                <span>
                  <b>${formatAssetOptionWhole(item.openInterest)}</b>
                  <small>${escapeHtml(item.symbol)} · ${escapeHtml(item.pct || "--")}</small>
                </span>
              `).join("")}
            </div>
            <p>${contracts.map((item) => `${item.symbol} ${item.date || "--"}`).join(" · ")}；資料為 TAIFEX 一般交易時段未沖銷契約量，並非價格推估。</p>
          ` : '<p class="stock-detail-empty">TAIFEX 期貨未平倉資料同步中。</p>'}
        </section>
      </div>
    </div>
  `;
}
