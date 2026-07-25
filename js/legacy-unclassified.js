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
