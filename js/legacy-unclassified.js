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
function twEtfSignedPct(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  return `${parsed > 0 ? "+" : ""}${parsed.toFixed(2)}%`;
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
