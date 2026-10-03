
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
  const bullish = Number(optionsModel.scenarioWeights?.bullish) || 0;
  const bearish = Number(optionsModel.scenarioWeights?.bearish) || 0;
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
      evidence: `多方權重 ${bullish}% / 空方權重 ${bearish}% / 震盪權重 ${optionsModel.scenarioWeights.range}%；PCR ${optionsDecimal(optionsModel.pcr)}；VIX ${Number.isFinite(optionsModel.vixValue) ? optionsModel.vixValue.toFixed(2) : "--"}。這些是規則式情境權重，不代表統計漲跌機率。`,
      conclusion: optionsModel.riskScore >= 66 ? "選擇權市場風險與權利金風險偏高，會壓抑追價與槓桿承受度。" : optionScore >= 58 ? "選擇權結構支持偏多情境，但仍需突破 Call OI 壓力確認。" : optionScore <= 42 ? "Put、VIX 或市場風險分數偏高，對盤勢形成下行壓力。" : "PCR 與 OI 接近平衡，選擇權偏向區間牽引。",
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
  const topStrategy = buildOptionsStrategyRows(optionsModel)[0] || null;
  const chain = optionsModel.chain || {};
  const chainAnalysis = chain.analysis || {};
  const allowedDecisionStates = new Set(["LONG", "SHORT", "HOLD_EXISTING", "NO_TRADE", "UNKNOWN"]);
  const rawDecisionState = String(chainAnalysis.decisionState || "UNKNOWN").toUpperCase();
  const decisionState = allowedDecisionStates.has(rawDecisionState) ? rawDecisionState : "UNKNOWN";
  const decisionReasons = Array.isArray(chainAnalysis.reasonCodes) && chainAnalysis.reasonCodes.length ? chainAnalysis.reasonCodes : ["UNKNOWN"];
  const decisionStateLabel = ({ LONG: "明確偏多決策", SHORT: "明確偏空決策", HOLD_EXISTING: "維持現有部位", NO_TRADE: "暫不交易", UNKNOWN: "交易決策未確認" })[decisionState];
  const optionStrategyDescription = chainAnalysis.strategySuggestion || topStrategy?.name || "等待策略條件";
  const decisionEligibilityText = decisionState === "NO_TRADE"
    ? "不可建立新部位"
    : decisionState === "HOLD_EXISTING"
      ? "維持現有部位；不代表可建立新部位"
      : ["LONG", "SHORT"].includes(decisionState) && chainAnalysis.decisionEligible === true
        ? "此方向符合既有明確決策資格"
        : "是否可建立新部位尚未確認";
  const decisionStateNotice = `<div class="stock-theory-note decision-state-notice is-${decisionState.toLowerCase()}" role="status"><b>${escapeHtml(decisionStateLabel)}</b><span>${escapeHtml(decisionEligibilityText)}</span><small>原因代碼：${escapeHtml(decisionReasons.map((code) => String(code || "UNKNOWN").toUpperCase()).join(", "))}</small>${["UNKNOWN", "NO_TRADE"].includes(decisionState) ? `<small>策略傾向（僅供研究描述）：${escapeHtml(optionStrategyDescription)}</small>` : ""}</div>`;
  const chainSource = chain.source || {};
  const skew = optionsModel.maxIv !== null && optionsModel.minIv !== null ? optionsModel.maxIv - optionsModel.minIv : null;
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
            <strong>${escapeHtml(optionsModel.direction)} · 市場風險 ${optionsModel.riskScore}/100</strong>
            <p>${escapeHtml(optionsModel.primaryRisk)}；證據強度 ${optionsModel.evidenceScore}/100。</p>
            <div class="options-probability-bars">
              ${[["多方權重", optionsModel.scenarioWeights.bullish, "up"], ["空方權重", optionsModel.scenarioWeights.bearish, "down"], ["震盪權重", optionsModel.scenarioWeights.range, "flat"]].map(([label, value, tone]) => `<span class="is-${tone}"><b>${label}</b><i style="--bar:${Number(value) || 0}%"></i><em>${Number(value) || 0}%</em></span>`).join("")}
            </div>
            <small>情境權重不代表統計漲跌機率；總和為 100 不代表機率校準。</small>
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
          <strong>${escapeHtml(chainAnalysis.bias || optionsModel.direction || "盤勢同步中")} · ${escapeHtml(optionStrategyDescription)}</strong>
          ${decisionStateNotice}
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
          <div class="asset-hub-group-heading"><div><p class="panel-kicker">AI Decision Brief</p><h4>AI 今日結論與策略</h4></div><span>證據強度 ${chainAnalysis.evidenceScore ?? optionsModel.evidenceScore}/100</span></div>
          ${decisionStateNotice}
          <div class="derivatives-overview-decision-lead is-${optionDirectionTone}">
            <small>${escapeHtml(chainAnalysis.bias || optionsModel.direction || "盤勢同步中")}</small>
            <strong>${escapeHtml(optionStrategyDescription)}</strong>
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
              ["市場風險", optionsModel.riskScore],
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

    <section class="section" id="asset-public-options">
      ${renderAssetHubPublicOptionChainCard(options.optionChain || {})}
    </section>

  `;
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
  const formatBasisNumber = (value) => {
    if (value === null || value === undefined || String(value).trim() === "") return "--";
    const number = Number(value);
    if (!Number.isFinite(number)) return "--";
    return number.toLocaleString("en-US", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  };
  const finiteBasisValue = (value) => {
    if (value === null || value === undefined || String(value).trim() === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const basis = finiteBasisValue(data.basis);
  const basisPct = finiteBasisValue(data.basisPct);
  return `
    <article class="panel-card asset-option-sentiment">
      <p class="panel-kicker">Basis</p>
      <h4>期現貨價差</h4>
      <strong>${Number.isFinite(basis) ? `${basis >= 0 ? "+" : ""}${basis.toFixed(0)}` : "--"}</strong>
      <span>期貨 ${formatBasisNumber(data.futurePrice)} / 現貨 ${formatBasisNumber(data.spotPrice)}</span>
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
  const futuresPayload = futuresResult.data || createAssetHubPlaceholder("futures", "期貨", "Futures", futuresResult.error);
  const optionsPayload = optionsResult.data || createAssetHubPlaceholder("options", "選擇權", "Options", optionsResult.error);
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
  const escapeText = escapeHtml;
  const unavailable = payload?.status === "unavailable";
  const count = unavailable ? "--" : summary.count ?? 0;
  const direction = unavailable ? "-- / --" : `${summary.advancers ?? 0} / ${summary.decliners ?? 0}`;
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
        <span><b>${count}</b><small>${unavailable ? "資料暫不可用" : "有效資料"}</small></span>
        <span><b>${direction}</b><small>上漲 / 下跌</small></span>
        <span><b>${escapeHtml(summary.avgPct || "--")}</b><small>平均漲跌幅</small></span>
        <span><b>${escapeHtml(summary.strongest || "--")}</b><small>最強標的</small></span>
      </div>
      ${renderAssetHubRegionChips(payload)}
      <p class="asset-hub-insight">${unavailable ? `資料暫不可用：${escapeText(payload.error || "transport failure")}` : `驗證 ${Number(validation.verifiedCount) || 0} 筆、限制 ${Number(validation.limitedCount) || 0} 筆、失敗 ${Number(validation.failedCount) || 0} 筆；主來源：${escapeHtml(validation.primary || payload?.source || "--")}。`}</p>
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
  if (!root) {
    console.error("Derivatives analytics initialization aborted: #derivatives-analytics-root not found");
    return;
  }
  const derivativesNumeric = (value) => {
    const parsed = parseMarketNumber(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const derivativesSignalLabel = (value, positiveLabel, negativeLabel, neutralLabel) => {
    if (!Number.isFinite(value)) return "資料不足";
    if (value > 0) return positiveLabel;
    if (value < 0) return negativeLabel;
    return neutralLabel;
  };
  const buildDerivativesMarketStateModel = (futuresPayload, chain, pcr, basisResult, institutionResult, analysis, futureAnalysis) => {
    const futuresItem = findAssetHubItem(futuresPayload, "TX") || {};
    const spot = derivativesNumeric(chain?.spot?.value);
    const maxPain = derivativesNumeric(chain?.summary?.maxPain);
    const oiPcr = derivativesNumeric(chain?.summary?.putCallRatio ?? pcr?.putCallRatio);
    const volumePcr = derivativesNumeric(chain?.summary?.volumePutCallRatio ?? pcr?.volumePutCallRatio);
    const basis = derivativesNumeric(basisResult?.data?.basis);
    const institutionNet = derivativesNumeric(institutionResult?.data?.summary?.netContracts);
    const futuresPrice = derivativesNumeric(futuresItem.close || futuresItem.last || futuresItem.settlement);
    const futuresPct = derivativesNumeric(futuresItem.pct);
    const riskScore = [analysis?.riskScore, futureAnalysis?.riskScore]
      .map(derivativesNumeric)
      .find(Number.isFinite) ?? null;
    const riskType = "UNKNOWN";
    const maxPainGap = Number.isFinite(spot) && Number.isFinite(maxPain) ? spot - maxPain : null;
    const maxPainGapPct = Number.isFinite(maxPainGap) && spot ? maxPainGap / spot : null;
    const coreDataReady = [futuresPrice, spot, maxPain, oiPcr, volumePcr].every(Number.isFinite);

    let directionScore = 0;
    if (Number.isFinite(oiPcr)) directionScore += oiPcr >= 1.25 ? -2 : oiPcr <= 0.75 ? 2 : 0;
    if (Number.isFinite(volumePcr)) directionScore += volumePcr >= 1.1 ? -1 : volumePcr <= 0.9 ? 1 : 0;
    if (Number.isFinite(basis)) directionScore += basis > 0 ? 1 : basis < 0 ? -1 : 0;
    if (Number.isFinite(institutionNet)) directionScore += institutionNet > 0 ? 1 : institutionNet < 0 ? -1 : 0;
    if (Number.isFinite(futuresPct)) directionScore += futuresPct > 0.5 ? 1 : futuresPct < -0.5 ? -1 : 0;
    if (Number.isFinite(maxPainGapPct)) directionScore += maxPainGapPct > 0.01 ? 1 : maxPainGapPct < -0.01 ? -1 : 0;

    const marketState = !coreDataReady
      ? "資料不足"
      : directionScore >= 3
        ? "偏多"
        : directionScore >= 1
          ? "震盪偏多"
          : directionScore <= -3
            ? "偏空"
            : directionScore <= -1
              ? "震盪偏空"
              : "震盪";
    const riskLabel = Number.isFinite(riskScore)
      ? riskScore >= 72 ? "高風險" : riskScore >= 55 ? "中高風險" : riskScore >= 40 ? "中風險" : "低風險"
      : "資料不足";
    const reasons = [];
    if (Number.isFinite(oiPcr)) reasons.push(oiPcr >= 1.25 ? "OI PCR 偏高，避險需求增加" : oiPcr <= 0.75 ? "OI PCR 偏低，Call OI 相對集中" : "OI PCR 接近多空平衡");
    if (Number.isFinite(basis)) reasons.push(basis < 0 ? "期貨呈現逆價差" : basis > 0 ? "期貨呈現正價差" : "期貨與現貨接近");
    if (Number.isFinite(institutionNet)) reasons.push(institutionNet < 0 ? "法人淨部位偏空" : institutionNet > 0 ? "法人淨部位偏多" : "法人淨部位接近中性");
    if (Number.isFinite(maxPainGapPct) && Math.abs(maxPainGapPct) <= 0.01) reasons.push("現貨接近 Max Pain");
    if (Number.isFinite(futuresPct) && Math.abs(futuresPct) > 0.5) reasons.push(futuresPct < 0 ? "TX 期貨價格偏弱" : "TX 期貨價格偏強");
    const explanation = !coreDataReady
      ? "目前缺少足夠的期貨 / 選擇權資料，暫不產生方向性判斷。"
      : `綜合判斷：${reasons.slice(0, 3).join("、")}，目前較符合${marketState}結構。`;
    return {
      marketState,
      riskScore,
      riskType,
      riskClassification: { type: riskType, score: riskScore, comparability: "WITHIN_RISK_TYPE_ONLY" },
      riskLabel,
      explanation,
      futuresPrice,
      futuresPct,
      basis,
      oiPcr,
      volumePcr,
      maxPain,
      institutionNet,
    };
  };
  const renderDerivativesMarketStateSummary = (model) => {
    const value = (number, formatter = (item) => formatAssetOptionNumber(item)) => Number.isFinite(number) ? formatter(number) : "--";
    const signedWhole = (number) => Number.isFinite(number) ? `${number >= 0 ? "+" : ""}${Math.round(number).toLocaleString("en-US")}` : "--";
    const riskValue = Number.isFinite(model.riskScore) ? `${Math.round(model.riskScore)} / 100` : "--";
    return `
      <section class="section">
        <article class="panel-card derivatives-market-state-summary" id="derivatives-analytics-market-state" aria-labelledby="derivatives-market-state-title">
          <div class="derivatives-market-state-header">
            <div>
              <p class="panel-kicker">Market state summary</p>
              <h2 id="derivatives-market-state-title">衍生品市場狀態</h2>
            </div>
            <div class="derivatives-market-state-badges">
              <strong class="derivatives-market-state-value">${model.marketState}</strong>
      <span class="derivatives-market-state-risk">市場風險類別未確認 · ${model.riskLabel}</span>
            </div>
          </div>
          <div class="derivatives-market-state-metrics">
            <span class="derivatives-market-state-metric"><b>${value(model.futuresPrice, (item) => formatAssetOptionWhole(item))}</b><small>TX Futures · ${derivativesSignalLabel(model.futuresPct, "偏強", "偏弱", "中性")}</small></span>
            <span class="derivatives-market-state-metric"><b>${value(model.basis, (item) => `${item >= 0 ? "+" : ""}${item.toFixed(0)}`)}</b><small>Basis · ${derivativesSignalLabel(model.basis, "正價差", "逆價差", "接近現貨")}</small></span>
            <span class="derivatives-market-state-metric"><b>${value(model.oiPcr)}</b><small>OI PCR · ${Number.isFinite(model.oiPcr) ? model.oiPcr >= 1.25 ? "防守增加" : model.oiPcr <= 0.75 ? "多方集中" : "中性" : "資料不足"}</small></span>
            <span class="derivatives-market-state-metric"><b>${value(model.volumePcr)}</b><small>Volume PCR · ${Number.isFinite(model.volumePcr) ? model.volumePcr >= 1.1 ? "偏空交易" : model.volumePcr <= 0.9 ? "偏多交易" : "中性" : "資料不足"}</small></span>
            <span class="derivatives-market-state-metric"><b>${value(model.maxPain, (item) => formatAssetOptionWhole(item))}</b><small>Max Pain · ${Number.isFinite(model.maxPain) ? "到期中性參考" : "資料不足"}</small></span>
            <span class="derivatives-market-state-metric"><b>${signedWhole(model.institutionNet)}</b><small>Institution · ${derivativesSignalLabel(model.institutionNet, "偏多", "偏空", "中性")}</small></span>
            <span class="derivatives-market-state-metric derivatives-market-state-metric-risk"><b>${riskValue}</b><small>UNKNOWN 風險類別 · ${model.riskLabel}</small></span>
          </div>
          <p class="derivatives-market-state-explanation">${model.explanation}</p>
        </article>
      </section>
    `;
  };
  const strategyNumber = (value) => Number.isFinite(value) ? value.toFixed(2) : "--";
  const strategyMoney = (value, label = "") => label || (Number.isFinite(value) ? value.toFixed(2) : "--");
  const renderStrategyChart = (model, currentSpot) => {
    const points = initDerivativesAnalyticsPage.strategyEngine.chartPoints(model, currentSpot);
    if (!points.length) return `<div class="derivatives-strategy-chart-unavailable">Exact Expiration Payoff: Model Dependent / Not Available</div>`;
    const upper = points[points.length - 1].price || 1;
    const maxAbs = Math.max(...points.map((point) => Math.abs(point.payoff)), 1);
    const toX = (price) => (price / upper) * 700 + 10;
    const toY = (value) => 130 - (value / maxAbs) * 96;
    const polyline = points.map((point) => `${toX(point.price).toFixed(1)},${toY(point.payoff).toFixed(1)}`).join(" ");
    const strikeLines = model.legs.filter((leg, index, legs) => legs.findIndex((item) => item.strike === leg.strike) === index)
      .map((leg) => `<line x1="${toX(leg.strike).toFixed(1)}" x2="${toX(leg.strike).toFixed(1)}" y1="28" y2="226" class="derivatives-strategy-chart-strike"/><text x="${toX(leg.strike).toFixed(1)}" y="244" text-anchor="middle">${strategyNumber(leg.strike)}</text>`).join("");
    const breakEvenLines = (model.metrics.breakEven || []).map((value) => `<line x1="${toX(value).toFixed(1)}" x2="${toX(value).toFixed(1)}" y1="28" y2="226" class="derivatives-strategy-chart-be"/>`).join("");
    const spotX = toX(currentSpot);
    return `<svg class="derivatives-strategy-chart" viewBox="0 0 720 260" role="img" aria-label="Strategy payoff chart"><line x1="10" x2="710" y1="130" y2="130" class="derivatives-strategy-chart-axis"/><line x1="${spotX.toFixed(1)}" x2="${spotX.toFixed(1)}" y1="20" y2="226" class="derivatives-strategy-chart-spot"/>${strikeLines}${breakEvenLines}<polyline points="${polyline}" class="derivatives-strategy-chart-line"/><text x="14" y="18">Profit</text><text x="14" y="224">Loss</text><text x="${Math.min(700, Math.max(20, spotX)).toFixed(1)}" y="18" text-anchor="middle">Spot ${strategyNumber(currentSpot)}</text></svg>`;
  };
  const renderStrategyDetail = (model, currentSpot) => {
    const decisionState = ["LONG", "SHORT", "HOLD_EXISTING", "NO_TRADE", "UNKNOWN"].includes(model?.decisionState) ? model.decisionState : "UNKNOWN";
    const decisionSummary = decisionState === "NO_TRADE"
      ? `暫不交易（${(model.reasonCodes || ["UNKNOWN"]).join(", ")}）；不可建立新部位。`
      : decisionState === "HOLD_EXISTING"
        ? "維持現有部位；不代表可建立新部位。"
        : decisionState === "LONG" || decisionState === "SHORT"
          ? `${decisionState}；請依明確決策資格與個人部位條件評估。`
          : "交易決策未確認；不得將缺少訊號推定為持有或暫不交易。";
    if (!model || !model.available) return `<div class="derivatives-strategy-unavailable"><p class="stock-theory-note decision-state-notice is-${decisionState.toLowerCase()}" role="status"><b>${escapeHtml(decisionSummary)}</b>${(model?.reasonDetails || [model?.reason || "決策資格尚未確認。"]).map((item) => `<small>${escapeHtml(item)}</small>`).join("")}</p><h4 class="derivatives-strategy-detail-title">${escapeHtml(model?.name || "Strategy")} · 策略分析暫不可用</h4><p>策略分析暫不可用：${escapeHtml(model?.reason || "缺少必要資料")}。不產生策略組合或損益判斷。</p></div>`;
    const metrics = model.metrics;
    const legs = model.legs.map((leg) => `<tr class="derivatives-strategy-leg"><td>${leg.side}</td><td>${leg.optionType === "call" ? "Call" : "Put"}</td><td>${strategyNumber(leg.strike)}</td><td>${escapeHtml(leg.expiry)}</td><td>${strategyNumber(leg.premium)}</td><td>${leg.quantity}</td><td>${escapeHtml(`${leg.executionStatus || "UNAVAILABLE"} · ${leg.executionSource || "unavailable"}`)}</td></tr>`).join("");
    const maxProfit = strategyMoney(metrics.maxProfit, metrics.maxProfitLabel);
    const maxLoss = strategyMoney(metrics.maxLoss, metrics.maxLossLabel);
    const dteText = model.calendar ? `Near DTE ${model.nearDte} / Far DTE ${model.farDte}` : `DTE ${initDerivativesAnalyticsPage.strategyEngine.daysTo(model.legs[0].expiry)}`;
    const marketInput = model.marketInput || {};
    const provenanceText = `decision_as_of ${model.decisionAsOf || "unavailable"} · ${model.pointInTimeStatus || "UNAVAILABLE"} · ${marketInput.source || "unavailable"} · ${marketInput.provenance?.type || "UNAVAILABLE"} · session ${marketInput.sessionIdentity || "unavailable"} · ${decisionSummary}`;
    return `<div class="derivatives-strategy-detail-title-row"><div><span class="chip chip-cyan">${model.label} · ${model.score}/100</span><h4 class="derivatives-strategy-detail-title">${model.name} · ${model.zh}</h4><p>${model.formula}</p></div><span class="derivatives-strategy-regime">${model.regime.direction} · ${model.regime.volatility}</span></div><p class="derivatives-strategy-provenance">${escapeHtml(provenanceText)}</p><div class="derivatives-strategy-leg-table-wrap"><table class="derivatives-strategy-leg-table"><thead><tr><th>Side</th><th>Type</th><th>Strike</th><th>Expiry</th><th>Premium</th><th>Qty/Ratio</th><th>Execution</th></tr></thead><tbody>${legs}</tbody></table></div><div class="derivatives-strategy-metrics"><span><b>${strategyNumber(metrics.netPremium)}</b><small>${metrics.netLabel}</small></span><span><b>${maxProfit}</b><small>Max Profit</small></span><span><b>${maxLoss}</b><small>Max Loss</small></span><span><b>${metrics.breakEven.length ? metrics.breakEven.map(strategyNumber).join(", ") : "--"}</b><small>Break-even</small></span><span><b>${metrics.riskReward}</b><small>Risk / Reward</small></span><span><b>${dteText}</b><small>Expiry / DTE</small></span><span><b>${escapeHtml(metrics.plTrustStatus || "UNTRUSTED")}</b><small>P/L Trust</small></span></div><p class="derivatives-strategy-zones"><strong>Profit / Loss Zone：</strong>${metrics.zones}</p>${renderStrategyChart(model, currentSpot)}<div class="derivatives-strategy-score"><strong>Compatibility Score Breakdown</strong><span>Direction Fit ${model.breakdown.directionFit}</span><span>Volatility Fit ${model.breakdown.volatilityFit}</span><span>IV Fit ${model.breakdown.ivFit} · Historical IV Context = Unavailable</span><span>Price Structure Fit ${model.breakdown.priceStructureFit}</span><span>Time Fit ${model.breakdown.timeFit}</span><span>Liquidity Fit ${model.breakdown.liquidityFit}</span><span>Risk Penalty ${model.breakdown.riskPenalty}</span></div><p class="derivatives-strategy-warning">${model.warning}</p><p class="derivatives-strategy-invalidation"><strong>Invalidation：</strong>${model.invalidation}</p></div>`;
  };
  const renderOptionsStrategyAnalyzer = (models, currentSpot) => {
    const available = models.filter((model) => model.available && Number.isFinite(model.score)).sort((a, b) => b.score - a.score);
    const top = available.slice(0, 3);
    const lowest = models.filter((model) => !model.available || Number.isFinite(model.score)).sort((a, b) => (a.score ?? -1) - (b.score ?? -1))[0];
    const selected = models[0];
    const ranking = top.length ? top.map((model, index) => `<li><b>#${index + 1} ${model.name}</b><span>${model.score}/100 · ${model.label}</span></li>`).join("") : `<li><b>資料不足</b><span>目前不產生排名或策略建議</span></li>`;
    const lowestText = lowest ? (lowest.available ? `${lowest.name} · ${lowest.score}/100 · ${lowest.label}` : `${lowest.name} · 暫不可用：${lowest.reason}`) : "資料不足";
    const options = initDerivativesAnalyticsPage.strategyEngine.contracts.map((contract) => `<option value="${contract.id}">${contract.name} · ${contract.zh}</option>`).join("");
    const catalog = initDerivativesAnalyticsPage.strategyEngine.contracts.map((contract) => `<li><b>${contract.name}</b><span>${contract.formula}</span></li>`).join("");
    return `<section class="section" id="derivatives-strategy-analyzer"><article class="panel-card derivatives-strategy-analyzer-card"><div class="card-title-row"><div><p class="panel-kicker">Options strategy analyzer</p><h2>期權策略分析器</h2><p class="chart-subtitle">以目前 TXO 實際選擇權鏈建立固定 13 種策略；不補造履約價、權利金或 IV。</p></div><span class="chip chip-blue">13 Strategies</span></div><div class="derivatives-strategy-regime-grid"><span><b>${models[0].regime.direction}</b><small>Direction</small></span><span><b>${models[0].regime.volatility}</b><small>Volatility</small></span><span><b>${models[0].regime.ivState}</b><small>IV State</small></span><span><b>Unavailable</b><small>Historical IV Context</small></span></div><div class="derivatives-strategy-ranking-grid"><div><h3>Top 3 Compatibility</h3><ol>${ranking}</ol></div><div><h3>Lowest Compatibility / Reason</h3><p>${lowestText}</p><small>分數是相容性排序，不是獲利保證。</small></div></div><label class="derivatives-strategy-select-label" for="derivatives-strategy-select">選擇策略檢視實際腿與到期損益</label><select id="derivatives-strategy-select" data-strategy-select>${options}</select><div id="derivatives-strategy-detail" class="derivatives-strategy-detail">${renderStrategyDetail(selected, currentSpot)}</div><details class="derivatives-strategy-catalog"><summary>13 strategy contracts</summary><ul>${catalog}</ul></details><p class="derivatives-strategy-disclaimer">策略分析僅供研究與情境比較，不構成投資、交易、避險或保證獲利建議。最大損益與損益兩平點依實際成交權利金、履約價、到期日、結算規則、手續費、滑價、保證金、指派與流動性而變動；短期權策略可能有重大尾部風險，請勿視為獲利保證。</p></article></section>`;
  };
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
  const apiFailures = [
    ["futures", assetPayloads.errors.futures],
    ["options", assetPayloads.errors.options],
    ["chain", chainResult.error],
    ["pcr", pcrResult.error],
    ["institution", institutionResult.error],
    ["basis", basisResult.error],
    ["options-ai", optionResult.error],
    ["futures-ai", futureResult.error],
    ["news", newsResult.error],
  ].filter(([, error]) => error);
  if (apiFailures.length) console.warn("Derivatives analytics API subsets unavailable:", apiFailures.map(([name, error]) => `${name}: ${error}`).join("; "));
  const futuresPayload = assetPayloads.futuresPayload;
  const optionsPayload = assetPayloads.optionsPayload;
  const chain = chainResult.data || {};
  const summary = chain.summary || {};
  const analysis = chain.analysis || {};
  const pcr = pcrResult.data || {};
  const maxPain = summary.maxPain;
  const spot = Number(chain.spot?.value);
  const gap = Number.isFinite(spot) && Number.isFinite(Number(maxPain)) ? spot - Number(maxPain) : null;
  const optionAnalysis = optionResult.data || chain.analysis || optionsPayload.taiwanOptionChain?.analysis || {};
  const marketStateModel = buildDerivativesMarketStateModel(
    futuresPayload,
    chain,
    pcr,
    basisResult,
    institutionResult,
    optionAnalysis,
    futureResult.data || {},
  );
  const txoChain = {
    ...(optionsPayload.taiwanOptionChain || {}),
    ...chain,
    analysis: optionResult.data || chain.analysis || optionsPayload.taiwanOptionChain?.analysis || {},
  };
  const strategyModels = initDerivativesAnalyticsPage.strategyEngine.analyze({
    chain,
    spot,
    direction: marketStateModel.marketState,
    futuresPct: marketStateModel.futuresPct,
    volumePcr: marketStateModel.volumePcr,
    maxPainGapPct: Number.isFinite(gap) && spot ? gap / spot : null,
  });
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">Derivatives analytics</p>
      <h1>衍生品市場狀態</h1>
      <p class="hero-text">整合 TXO 的 PCR、未平倉分布、最大痛點、期現貨價差、法人籌碼與 AI 風險情境；原 derivatives-ai.html 內容已合併到此頁。</p>
    </section>
    ${renderDerivativesMarketStateSummary(marketStateModel)}
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
    ${renderOptionsStrategyAnalyzer(strategyModels, spot)}
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
  const strategySelect = root.querySelector("[data-strategy-select]");
  const strategyDetail = root.querySelector("#derivatives-strategy-detail");
  if (strategySelect && strategyDetail) strategySelect.addEventListener("change", () => {
    const selectedModel = strategyModels.find((model) => model.id === strategySelect.value);
    strategyDetail.innerHTML = renderStrategyDetail(selectedModel, spot);
  });
}
initDerivativesAnalyticsPage.strategyEngine = (() => {
  const CONTRACTS = [
    { id: "long-straddle", name: "Long Straddle", zh: "買進跨式", family: "volatility", bias: "neutral", vol: "expansion", formula: "BUY 1 Call + BUY 1 Put；同履約價、同到期日" },
    { id: "long-strangle", name: "Long Strangle", zh: "買進勒式", family: "volatility", bias: "neutral", vol: "expansion", formula: "BUY 1 OTM Call + BUY 1 OTM Put；同到期日" },
    { id: "short-straddle", name: "Short Straddle", zh: "賣出跨式", family: "volatility", bias: "neutral", vol: "compression", formula: "SELL 1 Call + SELL 1 Put；同履約價、同到期日" },
    { id: "short-strangle", name: "Short Strangle", zh: "賣出勒式", family: "volatility", bias: "neutral", vol: "compression", formula: "SELL 1 OTM Call + SELL 1 OTM Put；同到期日" },
    { id: "bull-call-spread", name: "Bull Call Spread", zh: "牛市 Call 價差", family: "spread", bias: "bullish", vol: "stable", formula: "BUY 1 lower-strike Call + SELL 1 higher-strike Call" },
    { id: "bear-call-spread", name: "Bear Call Spread", zh: "熊市 Call 價差", family: "spread", bias: "bearish", vol: "stable", formula: "SELL 1 lower-strike Call + BUY 1 higher-strike Call" },
    { id: "bull-put-spread", name: "Bull Put Spread", zh: "牛市 Put 價差", family: "spread", bias: "bullish", vol: "stable", formula: "BUY 1 lower-strike Put + SELL 1 higher-strike Put" },
    { id: "bear-put-spread", name: "Bear Put Spread", zh: "熊市 Put 價差", family: "spread", bias: "bearish", vol: "stable", formula: "SELL 1 lower-strike Put + BUY 1 higher-strike Put" },
    { id: "long-condor", name: "Long Condor", zh: "多頭禿鷹", family: "range", bias: "neutral", vol: "compression", formula: "BUY K1 Call + SELL K2 Call + SELL K3 Call + BUY K4 Call；K1<K2<K3<K4" },
    { id: "short-condor", name: "Short Condor", zh: "空頭禿鷹", family: "range", bias: "neutral", vol: "expansion", formula: "SELL K1 Call + BUY K2 Call + BUY K3 Call + SELL K4 Call；K1<K2<K3<K4" },
    { id: "call-butterfly", name: "Call Butterfly", zh: "Call 蝴蝶", family: "butterfly", bias: "neutral", vol: "compression", formula: "BUY 1 K1 Call + SELL 2 K2 Call + BUY 1 K3 Call；K1<K2<K3" },
    { id: "put-butterfly", name: "Put Butterfly", zh: "Put 蝴蝶", family: "butterfly", bias: "neutral", vol: "compression", formula: "BUY 1 K1 Put + SELL 2 K2 Put + BUY 1 K3 Put；K1<K2<K3" },
    { id: "calendar-spread", name: "Calendar Spread", zh: "日曆價差", family: "calendar", bias: "neutral", vol: "compression", formula: "SELL near 1 Call/Put + BUY far 1 Call/Put；同一或最接近履約價" },
  ];
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const EXECUTION_STATUS = Object.freeze({
    EXECUTABLE: "EXECUTABLE",
    DEGRADED_FALLBACK: "DEGRADED_FALLBACK",
    UNAVAILABLE: "UNAVAILABLE",
    INVALID: "INVALID",
  });
  const LIQUIDITY_THRESHOLDS = Object.freeze({
    minVolume: 0,
    minOpenInterest: 0,
    maxSpreadRatio: 0.1,
    freshQuoteMaxAgeDays: 1,
    degradedQuoteMaxAgeDays: 3,
  });
  const numeric = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const parsed = Number(value);
    return finite(parsed) ? parsed : null;
  };
  const uniqueSorted = (values) => [...new Set(values.filter(finite).map((value) => Number(value.toFixed(8))))].sort((a, b) => a - b);
  const todayUtc = () => { const now = new Date(); return Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()); };
  const dateValue = (value) => {
    const text = String(value || "").trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(text)) return null;
    const parsed = Date.parse(`${text}T00:00:00Z`);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const timestampValue = (value) => {
    if (typeof value === "number" && Number.isFinite(value)) return value > 100000000000 ? value : value * 1000;
    const text = String(value || "").trim();
    if (!text) return null;
    const parsed = Date.parse(text);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const daysTo = (value) => { const parsed = dateValue(value); return parsed === null ? null : Math.ceil((parsed - todayUtc()) / 86400000); };
  const POINT_IN_TIME_STATUS = Object.freeze({
    ALIGNED: "ALIGNED",
    ALIGNED_CACHED: "ALIGNED_CACHED",
    ALIGNED_PREVIOUS_SESSION: "ALIGNED_PREVIOUS_SESSION",
    DECISION_AS_OF_UNAVAILABLE: "DECISION_AS_OF_UNAVAILABLE",
    DECISION_AS_OF_INVALID: "DECISION_AS_OF_INVALID",
    FUTURE_DATA: "FUTURE_DATA",
    DIFFERENT_TRADE_DATE: "DIFFERENT_TRADE_DATE",
    SESSION_MISMATCH: "SESSION_MISMATCH",
    MARKET_MISMATCH: "MARKET_MISMATCH",
    MIXED_FRESH_STALE: "MIXED_FRESH_STALE",
    STALE_INPUT: "STALE_INPUT",
    PROVENANCE_MISMATCH: "PROVENANCE_MISMATCH",
    TIMESTAMP_UNAVAILABLE: "TIMESTAMP_UNAVAILABLE",
  });
  const temporalField = (value) => {
    if (value === null || value === undefined) return { value: null, state: "MISSING_NULL", date: null, epoch: null, precision: null };
    if (value === "") return { value: null, state: "MISSING_EMPTY", date: null, epoch: null, precision: null };
    if (typeof value === "number" && value === 0) return { value, state: "INVALID_ZERO", date: null, epoch: null, precision: null };
    const text = String(value).trim();
    if (!text) return { value: null, state: "MISSING_EMPTY", date: null, epoch: null, precision: null };
    const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(text);
    const epoch = dateOnly ? dateValue(text) : timestampValue(value);
    if (!Number.isFinite(epoch)) return { value: text, state: "INVALID", date: null, epoch: null, precision: null };
    return { value: text, state: "PRESENT", date: new Date(epoch).toISOString().slice(0, 10), epoch, precision: dateOnly ? "DATE" : "TIMESTAMP" };
  };
  const ownValue = (item, key) => item && Object.prototype.hasOwnProperty.call(item, key) ? item[key] : undefined;
  const asUpperStatus = (value) => {
    const text = String(value || "").trim().toUpperCase().replace(/[ -]+/g, "_");
    return text || null;
  };
  const marketInputEnvelope = (market = {}, quote = null) => {
    const chain = market?.chain || {};
    const explicitInput = market?.marketInput || market?.marketInputEnvelope || {};
    const quoteSource = quote && ownValue(quote, "source") ? quote.source : undefined;
    const chainSource = chain.source ?? market.source ?? explicitInput.source ?? null;
    const source = quoteSource ?? chainSource;
    const sourceLabel = typeof source === "string" ? source : source?.primary ?? source?.name ?? null;
    const sourceMode = typeof source === "object" ? source?.mode : null;
    const fallbackFrom = quote?.fallbackFrom ?? chain.fallbackFrom ?? explicitInput.fallbackFrom ?? null;
    const fallbackReason = quote?.fallbackReason ?? chain.fallbackReason ?? explicitInput.fallbackReason ?? null;
    const cached = quote?.cached ?? chain.cached ?? explicitInput.cached ?? false;
    const stale = quote?.stale ?? chain.stale ?? explicitInput.stale ?? false;
    const explicitProvenance = quote?.provenanceType ?? quote?.provenance?.type ?? chain.provenanceType ?? explicitInput.provenanceType;
    const sourceType = asUpperStatus(explicitProvenance)
      || (fallbackFrom || String(sourceMode || "").includes("fallback") ? "FALLBACK" : stale && cached ? "CACHED_PREVIOUS_SESSION" : cached ? "CACHED" : sourceLabel ? "PRIMARY" : "UNAVAILABLE");
    const fallbackStatus = asUpperStatus(quote?.fallbackStatus ?? chain.fallbackStatus ?? explicitInput.fallbackStatus)
      || (fallbackFrom ? "FALLBACK" : stale && cached ? "CACHED_PREVIOUS_SESSION" : cached ? "CACHED" : sourceType === "UNAVAILABLE" ? "UNAVAILABLE" : "NONE");
    const observedRaw = quote?.observedAt ?? quote?.asOf ?? quote?.quoteTime ?? quote?.timestamp ?? quote?.updatedAt
      ?? chain.observedAt ?? chain.asOf ?? chain.updatedAt ?? explicitInput.observedAt ?? explicitInput.asOf;
    const tradeDateRaw = quote?.tradeDate ?? chain.tradeDate ?? market.tradeDate ?? explicitInput.tradeDate;
    const observed = temporalField(observedRaw);
    const tradeDate = temporalField(tradeDateRaw);
    const explicitDecisionRaw = ownValue(market, "decisionAsOf") ? market.decisionAsOf
      : ownValue(market, "decision_as_of") ? market.decision_as_of
        : ownValue(chain, "decisionAsOf") ? chain.decisionAsOf
          : ownValue(explicitInput, "decisionAsOf") ? explicitInput.decisionAsOf : undefined;
    const explicitDecision = explicitDecisionRaw !== undefined ? temporalField(explicitDecisionRaw) : null;
    const decision = explicitDecision || (observed.state === "PRESENT" ? observed : tradeDate.state === "PRESENT" ? tradeDate : temporalField(null));
    const decisionAsOfSource = explicitDecision ? "EXPLICIT" : observed.state === "PRESENT" ? "OBSERVED_AT" : tradeDate.state === "PRESENT" ? "TRADE_DATE" : "UNAVAILABLE";
    const freshnessHint = asUpperStatus(quote?.freshnessStatus ?? chain.freshnessStatus ?? explicitInput.freshnessStatus);
    const freshnessStatus = freshnessHint || (stale ? "STALE" : fallbackStatus === "CACHED_PREVIOUS_SESSION" ? "PREVIOUS_SESSION" : observed.state === "PRESENT" || tradeDate.state === "PRESENT" ? "FRESH" : "TIMESTAMP_UNAVAILABLE");
    const marketIdentity = {
      market: quote?.market ?? chain.market ?? market.market ?? explicitInput.market ?? null,
      exchange: quote?.exchange ?? chain.exchange ?? market.exchange ?? explicitInput.exchange ?? null,
      underlying: quote?.underlying ?? chain.underlying ?? market.underlying ?? explicitInput.underlying ?? null,
    };
    const sessionIdentity = quote?.session ?? quote?.marketSession ?? chain.session ?? chain.marketSession ?? market.session ?? explicitInput.session ?? null;
    return {
      source: sourceLabel,
      sourceType,
      sourceMode: sourceMode || null,
      provenance: { type: sourceType, fallbackStatus, fallbackFrom, fallbackReason },
      observedAt: observed.value,
      observedAtState: observed.state,
      tradeDate: tradeDate.value,
      tradeDateState: tradeDate.state,
      decisionAsOf: decision.value,
      decisionAsOfState: decision.state,
      decisionAsOfSource,
      freshnessStatus,
      stale: freshnessStatus === "STALE" || freshnessStatus === "PREVIOUS_SESSION",
      fallbackStatus,
      marketIdentity,
      sessionIdentity,
      sessionStatus: sessionIdentity === null || sessionIdentity === "" ? "UNAVAILABLE" : "PRESENT",
    };
  };
  const quoteFieldState = (value) => {
    if (value === null || value === undefined || value === "") return "MISSING";
    const parsed = numeric(value);
    if (parsed === null || parsed < 0) return "INVALID";
    if (parsed === 0) return "ZERO";
    return "POSITIVE";
  };
  const executionPrice = (quote, side = "BUY") => {
    const unavailable = (status, reason) => ({
      price: null,
      source: "unavailable",
      status,
      executionClass: "NON_EXECUTABLE",
      executable: false,
      reason,
    });
    if (!quote || typeof quote !== "object") return unavailable(EXECUTION_STATUS.UNAVAILABLE, "QUOTE_UNAVAILABLE");
    const bid = numeric(quote.bid);
    const ask = numeric(quote.ask);
    const bidState = quoteFieldState(quote.bid);
    const askState = quoteFieldState(quote.ask);
    const crossed = bidState === "POSITIVE" && askState === "POSITIVE" && ask < bid;
    const preferredField = side === "SELL" ? "bid" : "ask";
    const preferred = numeric(quote[preferredField]);
    const preferredState = preferredField === "bid" ? bidState : askState;
    if (finite(preferred) && preferred > 0 && !crossed) {
      return { price: preferred, source: preferredField, status: EXECUTION_STATUS.EXECUTABLE, executionClass: "EXECUTABLE", executable: true, reason: "BID_ASK" };
    }
    const fallbackReason = crossed
      ? "CROSSED_MARKET"
      : preferredState === "MISSING"
        ? `MISSING_${preferredField.toUpperCase()}`
        : preferredState === "ZERO"
          ? `${preferredField.toUpperCase()}_ZERO`
          : `${preferredField.toUpperCase()}_INVALID`;
    for (const field of ["last", "settlement", "lastPrice"]) {
      const value = numeric(quote[field]);
      if (finite(value) && value > 0) {
        return { price: value, source: field, status: EXECUTION_STATUS.DEGRADED_FALLBACK, executionClass: "NON_EXECUTABLE", executable: false, reason: fallbackReason };
      }
    }
    if (crossed) return unavailable(EXECUTION_STATUS.INVALID, fallbackReason);
    if (bidState === "MISSING" && askState === "MISSING") return unavailable(EXECUTION_STATUS.UNAVAILABLE, "BID_ASK_BOTH_MISSING");
    if (preferredState === "MISSING") return unavailable(EXECUTION_STATUS.UNAVAILABLE, fallbackReason);
    return unavailable(EXECUTION_STATUS.INVALID, fallbackReason);
  };
  const quotePremium = (quote, side = "BUY") => executionPrice(quote, side).price ?? null;
  const classifyLiquidityMetric = (value) => {
    if (value === null || value === undefined || value === "") return "MISSING";
    const parsed = numeric(value);
    if (parsed === null || parsed < 0) return "INVALID";
    if (parsed === 0) return "ZERO";
    return "POSITIVE";
  };
  const transactionCostValue = (quote, market, field, fallback = 0) => (
    numeric(quote?.[field])
    ?? numeric(market?.optionsCostModel?.[field])
    ?? numeric(market?.transactionCosts?.[field])
    ?? fallback
  );
  const liquidity = (quote, market) => {
    const volume = numeric(quote?.volume);
    const openInterest = numeric(quote?.openInterest);
    const bid = numeric(quote?.bid);
    const ask = numeric(quote?.ask);
    const quotePrice = quotePremium(quote, "BUY") ?? quotePremium(quote, "SELL");
    const quoteValidity = finite(quotePrice) && quotePrice > 0 ? "VALID" : "INVALID";
    const tradability = finite(bid) && bid > 0 && finite(ask) && ask > 0 && ask >= bid ? "TRADABLE" : "NOT_TRADABLE";
    const volumeState = classifyLiquidityMetric(quote?.volume);
    const openInterestState = classifyLiquidityMetric(quote?.openInterest);
    const midpoint = finite(bid) && finite(ask) && bid > 0 && ask >= bid ? (bid + ask) / 2 : null;
    const spreadPct = finite(midpoint) && midpoint > 0 ? (ask - bid) / midpoint : null;
    const spreadScore = finite(spreadPct) ? Math.max(0, Math.min(1, 1 - (spreadPct / LIQUIDITY_THRESHOLDS.maxSpreadRatio))) : 0;
    const quoteTimestamp = timestampValue(quote?.quoteTime ?? quote?.timestamp ?? quote?.updatedAt);
    const quoteAgeDays = quoteTimestamp === null ? null : Math.max(0, (Date.now() - quoteTimestamp) / 86400000);
    const freshnessScore = quoteAgeDays === null ? 0 : quoteAgeDays <= LIQUIDITY_THRESHOLDS.freshQuoteMaxAgeDays ? 1 : quoteAgeDays <= LIQUIDITY_THRESHOLDS.degradedQuoteMaxAgeDays ? 0.5 : 0;
    const volumeScore = finite(volume) && volume > LIQUIDITY_THRESHOLDS.minVolume ? 1 : 0;
    const openInterestScore = finite(openInterest) && openInterest > LIQUIDITY_THRESHOLDS.minOpenInterest ? 1 : 0;
    const eligibilityReasons = [];
    if (quoteValidity !== "VALID") eligibilityReasons.push("QUOTE_INVALID");
    if (tradability !== "TRADABLE") eligibilityReasons.push("BID_ASK_UNTRADABLE");
    if (volumeState !== "POSITIVE") eligibilityReasons.push(`VOLUME_${volumeState}`);
    if (openInterestState !== "POSITIVE") eligibilityReasons.push(`OPEN_INTEREST_${openInterestState}`);
    if (!finite(spreadPct)) eligibilityReasons.push("SPREAD_UNAVAILABLE");
    else if (spreadPct > LIQUIDITY_THRESHOLDS.maxSpreadRatio) eligibilityReasons.push("SPREAD_ABOVE_THRESHOLD");
    const liquidityEligibility = eligibilityReasons.length === 0 ? "ELIGIBLE" : "INELIGIBLE";
    const score = ((volumeScore + openInterestScore + spreadScore + freshnessScore) / 4) * 100;
    return {
      verified: [volumeState, openInterestState].every((state) => ["ZERO", "POSITIVE"].includes(state)),
      quoteValidity,
      tradability,
      liquidityEligibility,
      eligibilityReasons,
      volumeState,
      openInterestState,
      volume,
      openInterest,
      volumeScore,
      openInterestScore,
      spreadPct,
      spreadScore,
      quoteAgeDays,
      freshnessScore,
      score,
      source: market?.chain?.source?.primary || null,
    };
  };
  const expiryFrom = (market) => String(market?.chain?.selectedExpiryDate || market?.selectedExpiryDate || "").trim();
  const baseFailure = (market) => {
    const chain = market?.chain;
    if (!chain || !Array.isArray(chain.chain) || chain.chain.length === 0) return "選擇權鏈資料缺失";
    if (!dateValue(expiryFrom(market)) || (daysTo(expiryFrom(market)) ?? -1) <= 0) return "有效到期日或 DTE 缺失／已過期";
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(chain.tradeDate || ""))) return "行情日期未驗證";
    const age = Math.floor((todayUtc() - dateValue(chain.tradeDate)) / 86400000);
    if (age > 7) return "行情資料過舊";
    if (!chain.source || !chain.source.primary) return "行情來源未驗證";
    if (!finite(numeric(market.spot))) return "現貨資料缺失";
    return "";
  };
  const groups = (market) => (Array.isArray(market?.chain?.chain) ? market.chain.chain : [])
    .map((group) => ({ ...group, strike: numeric(group?.strike) }))
    .filter((group) => finite(group.strike) && group.strike > 0)
    .sort((a, b) => a.strike - b.strike);
  const legFrom = (group, optionType, side, quantity, expiry, market) => {
    const quote = group?.[optionType];
    const execution = executionPrice(quote, side);
    const premium = execution?.price;
    if (!quote || !finite(premium) || premium <= 0) return { failure: `${optionType === "call" ? "Call" : "Put"} 權利金缺失` };
    const quoteLiquidity = liquidity(quote, market);
    if (!quoteLiquidity.verified) return { failure: `${optionType === "call" ? "Call" : "Put"} 流動性資料未驗證` };
    const inputEnvelope = marketInputEnvelope(market, quote);
    return {
      leg: {
        side,
        optionType,
        strike: group.strike,
        premium,
        executionPrice: premium,
        executionSource: execution.source,
        executionStatus: execution.status,
        executionClass: execution.executionClass,
        executionReason: execution.reason,
        marketInput: inputEnvelope,
        quantity,
        expiry,
        volume: quoteLiquidity.volume,
        openInterest: quoteLiquidity.openInterest,
        volumeState: quoteLiquidity.volumeState,
        openInterestState: quoteLiquidity.openInterestState,
        quoteValidity: quoteLiquidity.quoteValidity,
        tradability: quoteLiquidity.tradability,
        liquidityEligibility: quoteLiquidity.liquidityEligibility,
        liquidityEligibilityReasons: quoteLiquidity.eligibilityReasons,
        spreadPct: quoteLiquidity.spreadPct,
        quoteAgeDays: quoteLiquidity.quoteAgeDays,
        liquidityScore: quoteLiquidity.score,
        commission: transactionCostValue(quote, market, "commission"),
        exchangeFee: transactionCostValue(quote, market, "exchangeFee"),
        slippage: transactionCostValue(quote, market, "slippage"),
        contractMultiplier: transactionCostValue(quote, market, "contractMultiplier", 1) > 0 ? transactionCostValue(quote, market, "contractMultiplier", 1) : 1,
      },
    };
  };
  const adjacent = (available, spot, optionType) => {
    const candidates = available.filter((group) => quotePremium(group?.[optionType]) !== null);
    if (candidates.length < 2) return null;
    return candidates.slice(0, -1).map((group, index) => [group, candidates[index + 1]])
      .sort((a, b) => Math.abs((a[0].strike + a[1].strike) / 2 - spot) - Math.abs((b[0].strike + b[1].strike) / 2 - spot))[0];
  };
  const windowed = (available, count, spot, optionType) => {
    const candidates = available.filter((group) => quotePremium(group?.[optionType]) !== null);
    if (candidates.length < count) return null;
    const windows = [];
    for (let index = 0; index <= candidates.length - count; index += 1) {
      const window = candidates.slice(index, index + count);
      windows.push({ window, distance: Math.abs((window[0].strike + window[window.length - 1].strike) / 2 - spot) });
    }
    return windows.sort((a, b) => a.distance - b.distance)[0]?.window || null;
  };
  const straddleGroups = (available, spot) => available.filter((group) => quotePremium(group.call) !== null && quotePremium(group.put) !== null)
    .sort((a, b) => Math.abs(a.strike - spot) - Math.abs(b.strike - spot))[0] || null;
  const strangleGroups = (available, spot) => {
    const puts = available.filter((group) => group.strike < spot && quotePremium(group.put) !== null).sort((a, b) => b.strike - a.strike);
    const calls = available.filter((group) => group.strike > spot && quotePremium(group.call) !== null).sort((a, b) => a.strike - b.strike);
    return puts[0] && calls[0] ? { put: puts[0], call: calls[0] } : null;
  };
  const makeLegs = (contract, market) => {
    const base = baseFailure(market);
    if (base) return { failure: base };
    const available = groups(market);
    const spot = numeric(market.spot);
    const expiry = expiryFrom(market);
    const add = (target, group, type, side, quantity = 1) => {
      const result = legFrom(group, type, side, quantity, expiry, market);
      if (result.failure) return result.failure;
      target.push(result.leg);
      return "";
    };
    const legs = [];
    if (contract.id === "long-straddle" || contract.id === "short-straddle") {
      const group = straddleGroups(available, spot);
      if (!group) return { failure: "缺少同履約價的 Call／Put 有效報價" };
      const side = contract.id.startsWith("long") ? "BUY" : "SELL";
      const failure = add(legs, group, "call", side) || add(legs, group, "put", side);
      return failure ? { failure } : { legs };
    }
    if (contract.id === "long-strangle" || contract.id === "short-strangle") {
      const pair = strangleGroups(available, spot);
      if (!pair) return { failure: "缺少現貨兩側的 OTM Call／Put 有效報價" };
      const side = contract.id.startsWith("long") ? "BUY" : "SELL";
      const failure = add(legs, pair.put, "put", side) || add(legs, pair.call, "call", side);
      return failure ? { failure } : { legs };
    }
    if (["bull-call-spread", "bear-call-spread", "bull-put-spread", "bear-put-spread"].includes(contract.id)) {
      const type = contract.id.includes("call") ? "call" : "put";
      const pair = adjacent(available, spot, type);
      if (!pair) return { failure: `缺少兩個有效 ${type === "call" ? "Call" : "Put"} 履約價` };
      const sides = contract.id === "bull-call-spread" ? ["BUY", "SELL"] : contract.id === "bear-call-spread" ? ["SELL", "BUY"] : contract.id === "bull-put-spread" ? ["BUY", "SELL"] : ["SELL", "BUY"];
      const failure = add(legs, pair[0], type, sides[0]) || add(legs, pair[1], type, sides[1]);
      return failure ? { failure } : { legs };
    }
    if (contract.id === "long-condor" || contract.id === "short-condor") {
      const selected = windowed(available, 4, spot, "call");
      if (!selected) return { failure: "缺少四個連續有效 Call 履約價" };
      const sides = contract.id === "long-condor" ? ["BUY", "SELL", "SELL", "BUY"] : ["SELL", "BUY", "BUY", "SELL"];
      for (let index = 0; index < selected.length; index += 1) {
        const failure = add(legs, selected[index], "call", sides[index]);
        if (failure) return { failure };
      }
      return { legs };
    }
    if (contract.id === "call-butterfly" || contract.id === "put-butterfly") {
      const type = contract.id.startsWith("call") ? "call" : "put";
      const selected = windowed(available, 3, spot, type);
      if (!selected) return { failure: `缺少三個有效 ${type === "call" ? "Call" : "Put"} 履約價` };
      const failures = [add(legs, selected[0], type, "BUY"), add(legs, selected[1], type, "SELL", 2), add(legs, selected[2], type, "BUY")];
      const failure = failures.find(Boolean);
      return failure ? { failure } : { legs };
    }
    if (contract.id === "calendar-spread") {
      const expiryChains = Array.isArray(market.expiryChains) ? market.expiryChains : [];
      const near = expiryChains.filter((item) => (daysTo(item?.expiryDate) ?? -1) > 0).sort((a, b) => daysTo(a.expiryDate) - daysTo(b.expiryDate))[0];
      const far = expiryChains.filter((item) => (daysTo(item?.expiryDate) ?? -1) > (daysTo(near?.expiryDate) ?? 0)).sort((a, b) => daysTo(a.expiryDate) - daysTo(b.expiryDate))[0];
      if (!near || !far || !Array.isArray(near.chain) || !Array.isArray(far.chain)) return { failure: "缺少近月／遠月的實際雙到期日鏈" };
      const nearGroups = near.chain.map((item) => ({ ...item, strike: numeric(item?.strike) })).filter((item) => finite(item.strike));
      const farGroups = far.chain.map((item) => ({ ...item, strike: numeric(item?.strike) })).filter((item) => finite(item.strike));
      const candidates = [];
      for (const nearGroup of nearGroups) for (const farGroup of farGroups) {
        const type = quotePremium(nearGroup.call) !== null && quotePremium(farGroup.call) !== null ? "call" : quotePremium(nearGroup.put) !== null && quotePremium(farGroup.put) !== null ? "put" : null;
        if (type && Math.abs(nearGroup.strike - farGroup.strike) <= Math.max(nearGroup.strike * 0.01, 1)) candidates.push({ nearGroup, farGroup, type, distance: Math.abs(nearGroup.strike - spot) + Math.abs(nearGroup.strike - farGroup.strike) });
      }
      const selected = candidates.sort((a, b) => a.distance - b.distance)[0];
      if (!selected) return { failure: "近月／遠月缺少相同或最接近履約價的有效報價" };
      const nearResult = legFrom(selected.nearGroup, selected.type, "SELL", 1, near.expiryDate, market);
      const farResult = legFrom(selected.farGroup, selected.type, "BUY", 1, far.expiryDate, market);
      if (nearResult.failure || farResult.failure) return { failure: nearResult.failure || farResult.failure };
      return { legs: [nearResult.leg, farResult.leg], calendar: true, nearDte: daysTo(near.expiryDate), farDte: daysTo(far.expiryDate) };
    }
    return { failure: "策略合約未定義" };
  };
  const intrinsic = (leg, price) => leg.optionType === "call" ? Math.max(price - leg.strike, 0) : Math.max(leg.strike - price, 0);
  const legMultiplier = (leg) => {
    const parsed = numeric(leg?.contractMultiplier);
    return parsed === null ? 1 : parsed > 0 ? parsed : null;
  };
  const optionsCostModel = {
    assetClass: "OPTIONS",
    costBasis: "provider-supplied per-leg friction treated as round-trip cost",
    leg: (leg) => {
      const quantity = numeric(leg?.quantity);
      const multiplier = legMultiplier(leg);
      const commission = numeric(leg?.commission) ?? 0;
      const exchangeFee = numeric(leg?.exchangeFee) ?? 0;
      const slippage = numeric(leg?.slippage) ?? 0;
      const bidAskCost = numeric(leg?.bidAskCost) ?? 0;
      if (![quantity, multiplier, commission, exchangeFee, slippage, bidAskCost].every(finite) || quantity <= 0 || commission < 0 || exchangeFee < 0 || slippage < 0 || bidAskCost < 0) return null;
      const commissionCost = quantity * commission;
      const regulatoryCost = quantity * exchangeFee;
      const slippageCost = quantity * slippage * multiplier;
      const otherCost = quantity * bidAskCost;
      const roundTripCost = commissionCost + regulatoryCost + slippageCost + otherCost;
      return {
        assetClass: "OPTIONS",
        quantity,
        multiplier,
        commissionCost,
        taxCost: 0,
        regulatoryCost,
        slippageCost,
        otherCost,
        totalEntryCost: roundTripCost / 2,
        totalExitCost: roundTripCost / 2,
        roundTripCost,
        bidAskExecutionSource: leg?.executionSource || "unavailable",
      };
    },
    strategy: (legs) => {
      if (!Array.isArray(legs) || !legs.length) return { supported: false, assetClass: "OPTIONS", status: "invalid", reason: "MISSING_OPTION_LEGS" };
      const breakdowns = legs.map((leg) => optionsCostModel.leg(leg));
      if (breakdowns.some((item) => !item)) return { supported: false, assetClass: "OPTIONS", status: "invalid", reason: "INVALID_OPTION_LEG" };
      const sum = (key) => breakdowns.reduce((total, item) => total + item[key], 0);
      return {
        supported: true,
        assetClass: "OPTIONS",
        status: "supported",
        legs: breakdowns,
        commissionCost: sum("commissionCost"),
        taxCost: 0,
        regulatoryCost: sum("regulatoryCost"),
        slippageCost: sum("slippageCost"),
        otherCost: sum("otherCost"),
        totalEntryCost: sum("totalEntryCost"),
        totalExitCost: sum("totalExitCost"),
        roundTripCost: sum("roundTripCost"),
      };
    },
  };
  const legTransactionCost = (leg) => {
    const breakdown = optionsCostModel.leg(leg);
    return breakdown ? breakdown.roundTripCost : null;
  };
  const strategyPointInTime = (legs = [], market = {}) => {
    const baseInput = marketInputEnvelope(market);
    const inputs = legs.map((leg) => leg?.marketInput || baseInput);
    const decisionInput = temporalField(baseInput.decisionAsOf);
    const reasons = [];
    if (baseInput.decisionAsOfState === "INVALID" || baseInput.decisionAsOfState === "INVALID_ZERO") reasons.push(POINT_IN_TIME_STATUS.DECISION_AS_OF_INVALID);
    else if (decisionInput.state !== "PRESENT") reasons.push(POINT_IN_TIME_STATUS.DECISION_AS_OF_UNAVAILABLE);
    const decisionDate = decisionInput.date;
    const futureInput = inputs.find((input) => {
      const observed = temporalField(input.observedAt);
      const tradeDate = temporalField(input.tradeDate);
      return (decisionDate && observed.date && observed.date > decisionDate) || (decisionDate && tradeDate.date && tradeDate.date > decisionDate)
        || (decisionInput.precision === "TIMESTAMP" && observed.precision === "TIMESTAMP" && observed.epoch > decisionInput.epoch);
    });
    if (futureInput) reasons.push(POINT_IN_TIME_STATUS.FUTURE_DATA);
    const distinctTradeDates = [...new Set(inputs.map((input) => input.tradeDate).filter((value) => value !== null))];
    if (distinctTradeDates.length > 1) reasons.push(POINT_IN_TIME_STATUS.DIFFERENT_TRADE_DATE);
    const distinctSessions = [...new Set(inputs.map((input) => input.sessionIdentity))];
    if (distinctSessions.length > 1 || inputs.some((input) => input.sessionStatus !== "PRESENT")) reasons.push(POINT_IN_TIME_STATUS.SESSION_MISMATCH);
    const marketKeys = inputs.map((input) => JSON.stringify(input.marketIdentity));
    if (new Set(marketKeys).size > 1) reasons.push(POINT_IN_TIME_STATUS.MARKET_MISMATCH);
    const freshness = new Set(inputs.map((input) => input.freshnessStatus));
    if (freshness.has("STALE") && freshness.has("FRESH")) reasons.push(POINT_IN_TIME_STATUS.MIXED_FRESH_STALE);
    else if (freshness.has("STALE")) reasons.push(POINT_IN_TIME_STATUS.STALE_INPUT);
    if (inputs.some((input) => input.freshnessStatus === "TIMESTAMP_UNAVAILABLE")) reasons.push(POINT_IN_TIME_STATUS.TIMESTAMP_UNAVAILABLE);
    const provenanceKeys = new Set(inputs.map((input) => `${input.sourceType}|${input.fallbackStatus}|${input.source || ""}`));
    if (provenanceKeys.size > 1) reasons.push(POINT_IN_TIME_STATUS.PROVENANCE_MISMATCH);
    const status = reasons[0] || (inputs.every((input) => input.freshnessStatus === "PREVIOUS_SESSION") ? POINT_IN_TIME_STATUS.ALIGNED_PREVIOUS_SESSION : inputs.every((input) => input.sourceType === "CACHED") ? POINT_IN_TIME_STATUS.ALIGNED_CACHED : POINT_IN_TIME_STATUS.ALIGNED);
    return {
      status,
      aligned: [POINT_IN_TIME_STATUS.ALIGNED, POINT_IN_TIME_STATUS.ALIGNED_CACHED].includes(status),
      decisionAsOf: baseInput.decisionAsOf,
      decisionAsOfSource: baseInput.decisionAsOfSource,
      inputs,
      reasons,
      envelope: baseInput,
    };
  };
  const strategyExecutionTrust = (legs = [], pointInTime = null) => {
    const failedLegs = legs.map((leg, index) => {
      const expectedSource = leg?.side === "SELL" ? "bid" : "ask";
      const reasons = [];
      if (leg?.executionStatus !== EXECUTION_STATUS.EXECUTABLE) reasons.push(`EXECUTION_${leg?.executionStatus || "UNAVAILABLE"}`);
      if (leg?.executionSource !== expectedSource) reasons.push("EXECUTION_SOURCE_MISMATCH");
      if (leg?.quoteValidity !== "VALID") reasons.push("QUOTE_INVALID");
      if (leg?.tradability !== "TRADABLE") reasons.push("QUOTE_NOT_TRADABLE");
      if (leg?.liquidityEligibility !== "ELIGIBLE") reasons.push("LIQUIDITY_INELIGIBLE");
      if (pointInTime && !pointInTime.aligned) reasons.push(`POINT_IN_TIME_${pointInTime.status}`);
      return reasons.length ? { index, reasons } : null;
    }).filter(Boolean);
    return {
      status: failedLegs.length ? "UNTRUSTED" : "TRUSTED",
      executionStatus: failedLegs.length ? "NON_EXECUTABLE" : EXECUTION_STATUS.EXECUTABLE,
      failedLegs,
      failedLegIndexes: failedLegs.map((item) => item.index),
      pointInTime: pointInTime || null,
    };
  };
  const payoff = (legs, price) => {
    if (!Array.isArray(legs) || !finite(price) || legs.length === 0) return null;
    return legs.reduce((total, leg) => {
      const qty = numeric(leg.quantity); const premium = numeric(leg.premium); const strike = numeric(leg.strike);
      const multiplier = legMultiplier(leg); const transactionCost = legTransactionCost(leg);
      if (!finite(qty) || qty <= 0 || !finite(premium) || premium <= 0 || !finite(strike) || !finite(multiplier) || !finite(transactionCost)) return NaN;
      const value = intrinsic({ ...leg, strike }, price);
      return total + (leg.side === "BUY" ? qty * (value - premium) : qty * (premium - value)) * multiplier - transactionCost;
    }, 0);
  };
  const netPremium = (legs) => legs.reduce((total, leg) => {
    const quantity = numeric(leg?.quantity);
    const premium = numeric(leg?.premium);
    const multiplier = legMultiplier(leg);
    const transactionCost = legTransactionCost(leg);
    if (![quantity, premium, multiplier, transactionCost].every(finite)) return NaN;
    return total + ((leg.side === "BUY" ? 1 : -1) * quantity * premium * multiplier) + transactionCost;
  }, 0);
  const metrics = (legs, calendar = false, executionTrust = null) => {
    const trust = executionTrust || strategyExecutionTrust(legs);
    const trustFields = {
      executionStatus: trust.executionStatus,
      executionTrustStatus: trust.status,
      plTrustStatus: trust.status,
      executionGrade: trust.status === "TRUSTED" ? "EXECUTION_GRADE" : "MODEL_ONLY",
      trustBoundary: trust,
    };
    const debitCredit = netPremium(legs);
    if (calendar) return { ...trustFields, netPremium: debitCredit, netLabel: debitCredit >= 0 ? "Net Debit" : "Net Credit", exactPayoffAvailable: false, maxProfit: null, maxLoss: null, maxProfitLabel: "Model Dependent / Not Available", maxLossLabel: "Model Dependent / Not Available", breakEven: [], zones: "Model Dependent / Not Available", riskReward: "Model Dependent / Not Available" };
    const strikes = uniqueSorted(legs.map((leg) => numeric(leg.strike)));
    const upper = Math.max(strikes[strikes.length - 1] * 4, strikes[strikes.length - 1] + Math.abs(debitCredit) * 4 + 1);
    const points = uniqueSorted([0, ...strikes, upper]);
    const values = points.map((point) => payoff(legs, point));
    const callSlope = legs.reduce((total, leg) => total + (leg.optionType === "call" ? (leg.side === "BUY" ? leg.quantity : -leg.quantity) : 0), 0);
    const breakEven = [];
    for (let index = 0; index < points.length; index += 1) {
      if (Math.abs(values[index]) < 1e-8) breakEven.push(points[index]);
      if (index === points.length - 1) continue;
      if (values[index] * values[index + 1] < 0) breakEven.push(points[index] + ((0 - values[index]) * (points[index + 1] - points[index])) / (values[index + 1] - values[index]));
    }
    const uniqueBe = uniqueSorted(breakEven);
    const profitUnbounded = callSlope > 0; const lossUnbounded = callSlope < 0;
    const maxProfit = profitUnbounded ? null : Math.max(...values); const maxLoss = lossUnbounded ? null : Math.min(...values);
    return { ...trustFields, netPremium: debitCredit, netLabel: debitCredit >= 0 ? "Net Debit" : "Net Credit", exactPayoffAvailable: true, maxProfit, maxLoss, maxProfitLabel: profitUnbounded ? "Unlimited upside" : "", maxLossLabel: lossUnbounded ? "Theoretical unlimited" : "", breakEven: uniqueBe, zones: uniqueBe.length ? `損益臨界點 ${uniqueBe.map((value) => value.toFixed(2)).join(", ")}` : "目前模型範圍內無損益臨界點", riskReward: finite(maxProfit) && finite(maxLoss) && maxLoss < 0 ? (maxProfit / Math.abs(maxLoss)).toFixed(2) : "N/A" };
  };
  const regime = (market) => {
    const rawDirection = market?.direction || market?.marketStateModel?.marketState || "";
    const directionMap = { 偏多: "Bullish", 震盪偏多: "Slight Bullish", 震盪: "Neutral", 震盪偏空: "Slight Bearish", 偏空: "Bearish" };
    const direction = directionMap[rawDirection] || (["Bullish", "Slight Bullish", "Neutral", "Slight Bearish", "Bearish"].includes(rawDirection) ? rawDirection : "Uncertain");
    const explicitVolatility = ["Expansion", "Stable", "Compression", "Unknown"].includes(market?.volatility) ? market.volatility : "";
    const futuresPct = numeric(market?.futuresPct); const volumePcr = numeric(market?.volumePcr); const maxPainGapPct = numeric(market?.maxPainGapPct);
    const volatility = explicitVolatility || (!finite(futuresPct) && !finite(volumePcr) && !finite(maxPainGapPct) ? "Unknown" : Math.abs(futuresPct || 0) >= 1 || Math.abs((volumePcr || 1) - 1) >= 0.15 ? "Expansion" : finite(maxPainGapPct) && Math.abs(maxPainGapPct) <= 0.01 && Math.abs(futuresPct || 0) <= 0.3 && volumePcr >= 0.9 && volumePcr <= 1.1 ? "Compression" : "Stable");
    const ivState = ["Low", "Normal", "High", "Extreme"].includes(market?.ivState) ? market.ivState : "Unavailable";
    return { direction, volatility, ivState };
  };
  const directionFit = (contract, direction) => {
    if (contract.bias === "bullish") return direction === "Bullish" ? 20 : direction === "Slight Bullish" ? 16 : direction === "Neutral" ? 10 : direction === "Uncertain" ? 8 : 3;
    if (contract.bias === "bearish") return direction === "Bearish" ? 20 : direction === "Slight Bearish" ? 16 : direction === "Neutral" ? 10 : direction === "Uncertain" ? 8 : 3;
    return direction === "Neutral" ? 18 : direction === "Uncertain" ? 10 : 12;
  };
  const volatilityFit = (contract, volatility) => {
    if (volatility === "Unknown") return 4;
    if (contract.vol === "expansion") return volatility === "Expansion" ? 20 : volatility === "Stable" ? 12 : 4;
    if (contract.vol === "compression") return volatility === "Compression" ? 20 : volatility === "Stable" ? 13 : 4;
    return volatility === "Stable" ? 16 : 10;
  };
  const riskPenalty = (contract) => ["short-straddle", "short-strangle"].includes(contract.id) ? -18 : contract.id === "short-condor" ? -5 : ["long-straddle", "long-strangle"].includes(contract.id) ? -3 : -2;
  const scoreModel = (contract, model, marketRegime, market) => {
    const liquidityFit = model.legs.length
      ? Math.round(Math.min(...model.legs.map((leg) => finite(leg.liquidityScore) ? leg.liquidityScore : 0)) / 10)
      : 0;
    const dte = daysTo(model.legs[0].expiry); const timeFit = dte > 30 ? 10 : dte > 14 ? 8 : dte > 7 ? 5 : 3;
    const breakdown = { directionFit: directionFit(contract, marketRegime.direction), volatilityFit: volatilityFit(contract, marketRegime.volatility), ivFit: marketRegime.ivState === "Unavailable" ? 0 : marketRegime.ivState === "Normal" ? 10 : marketRegime.ivState === "Low" ? 12 : 7, priceStructureFit: finite(numeric(market.spot)) ? 18 : 0, timeFit, liquidityFit, riskPenalty: riskPenalty(contract) };
    const score = Math.max(0, Math.min(100, Object.values(breakdown).reduce((sum, value) => sum + value, 0)));
    const label = score >= 80 ? "高相容" : score >= 60 ? "相容" : score >= 40 ? "中性" : score >= 20 ? "低相容" : "不相容";
    return { score, label, breakdown };
  };
  const strategyLiquidityGate = (legs = []) => {
    const failedLegIndexes = legs
      .map((leg, index) => leg?.liquidityEligibility === "ELIGIBLE" ? null : index)
      .filter((index) => index !== null);
    return {
      eligible: failedLegIndexes.length === 0,
      failedLegIndexes,
      failedLegCount: failedLegIndexes.length,
    };
  };
  const decisionStateFromExistingGates = ({ executionTrust, liquidityGate, pointInTime } = {}) => {
    const reasonCodes = [];
    const reasonDetails = [];
    if (pointInTime?.aligned === false) {
      reasonCodes.push("UNSUPPORTED_CONTEXT");
      reasonDetails.push(...(Array.isArray(pointInTime.reasons) ? pointInTime.reasons : []));
    }
    if (executionTrust?.status === "UNTRUSTED") {
      reasonCodes.push("INSUFFICIENT_EVIDENCE");
      (executionTrust.failedLegs || []).forEach((item) => reasonDetails.push(...(item.reasons || [])));
    }
    if (liquidityGate?.eligible === false) {
      reasonCodes.push("LIQUIDITY_INSUFFICIENT");
      if (liquidityGate.failedLegCount) reasonDetails.push(`${liquidityGate.failedLegCount} option leg(s) failed the existing liquidity gate.`);
    }
    if (!reasonCodes.length) {
      return { decisionState: "UNKNOWN", decisionEligible: null, reasonCodes: ["UNKNOWN"], reasonDetails: ["Strategy candidate feasibility is not a portfolio-aware trading instruction."] };
    }
    return { decisionState: "NO_TRADE", decisionEligible: false, reasonCodes: [...new Set(reasonCodes)], reasonDetails: [...new Set(reasonDetails)] };
  };
  const analyze = (market = {}) => {
    const currentRegime = regime(market);
    return CONTRACTS.map((contract) => {
      const selection = makeLegs(contract, market);
      if (selection.failure) return { ...contract, decisionState: "NO_TRADE", decisionEligible: false, reasonCodes: ["INSUFFICIENT_EVIDENCE"], reasonDetails: [selection.failure], available: false, executable: false, tradable: false, liquidityEligible: false, executionStatus: "UNAVAILABLE", executionTrustStatus: "UNTRUSTED", reason: selection.failure, score: null, label: "不相容", regime: currentRegime };
      const pointInTime = strategyPointInTime(selection.legs, market);
      const executionTrust = strategyExecutionTrust(selection.legs, pointInTime);
      const contractMetrics = metrics(selection.legs, selection.calendar, executionTrust);
      const liquidityGate = strategyLiquidityGate(selection.legs);
      const scored = scoreModel(contract, { legs: selection.legs }, currentRegime, market);
      const decisionStateContract = decisionStateFromExistingGates({ executionTrust, liquidityGate, pointInTime });
      const baseWarning = ["short-straddle", "short-strangle"].includes(contract.id) ? "高尾部風險；跳空、保證金、指派／結算風險需另行確認。Margin Requirement = Unavailable。" : "不代表獲利保證；到期前價格、波動率與流動性變化可能使結果失效。";
      const warning = decisionStateContract.decisionState === "NO_TRADE" ? `暫不交易 · ${decisionStateContract.reasonCodes.join(", ")}。${baseWarning}` : `交易決策未確認。${baseWarning}`;
      const invalidation = contract.bias === "bullish" ? "現貨跌破選定結構的關鍵支撐或多頭方向假設失效。" : contract.bias === "bearish" ? "現貨突破選定結構的關鍵壓力或空頭方向假設失效。" : contract.vol === "expansion" ? "實現波動率未擴張、權利金時間價值流失或突破假設失效。" : "現貨大幅脫離結構區間、波動率／期限結構改變或流動性惡化。";
      return { ...contract, ...decisionStateContract, available: true, executable: executionTrust.status === "TRUSTED" && liquidityGate.eligible, tradable: executionTrust.status === "TRUSTED" && liquidityGate.eligible, liquidityEligible: liquidityGate.eligible, executionStatus: executionTrust.executionStatus, executionTrustStatus: executionTrust.status, executionTrust, liquidityGate, pointInTimeStatus: pointInTime.status, decisionAsOf: pointInTime.decisionAsOf, marketInput: pointInTime.envelope, pointInTime, legs: selection.legs, calendar: Boolean(selection.calendar), nearDte: selection.nearDte, farDte: selection.farDte, metrics: contractMetrics, score: scored.score, label: scored.label, breakdown: scored.breakdown, regime: currentRegime, warning, invalidation };
    });
  };
  const chartPoints = (model, spot) => {
    if (!model?.available || model.calendar) return [];
    const strikes = model.legs.map((leg) => leg.strike); const maxStrike = Math.max(...strikes, spot || 0); const upper = Math.max(maxStrike * 1.25, (spot || 0) * 1.25, maxStrike + 1);
    return Array.from({ length: 25 }, (_, index) => { const price = upper * index / 24; return { price, payoff: payoff(model.legs, price) }; });
  };
  return {
    assetClass: "OPTIONS",
    costModel: optionsCostModel,
    contracts: CONTRACTS,
    liquidityThresholds: LIQUIDITY_THRESHOLDS,
    analyze,
    payoff,
    metrics,
    chartPoints,
    costBreakdown: (legs) => optionsCostModel.strategy(legs),
    daysTo,
    executionPrice,
    executionStatuses: EXECUTION_STATUS,
    executionTrust: strategyExecutionTrust,
    marketInputEnvelope,
    pointInTimeStatus: POINT_IN_TIME_STATUS,
    pointInTimeCheck: strategyPointInTime,
    liquidityScore: (quote, market) => liquidity(quote, market),
    liquidityGate: strategyLiquidityGate,
    decisionStateFromExistingGates,
  };
})();
function renderDerivativeAiReport(title, analysis = {}, error = "", id = "") {
  const idAttr = id ? ` id="${escapeHtml(id)}"` : "";
  if (error) return `<article class="panel-card"${idAttr}><h3>${escapeHtml(title)}</h3><p class="stock-detail-empty">AI 分析資料暫不可用：${escapeHtml(error)}</p></article>`;
  const scenarios = Array.isArray(analysis.scenarios) ? analysis.scenarios : [];
  const crossValidation = Array.isArray(analysis.crossValidation) ? analysis.crossValidation : [];
  const allowedDecisionStates = new Set(["LONG", "SHORT", "HOLD_EXISTING", "NO_TRADE", "UNKNOWN"]);
  const rawDecisionState = String(analysis.decisionState || "UNKNOWN").toUpperCase();
  const decisionState = allowedDecisionStates.has(rawDecisionState) ? rawDecisionState : "UNKNOWN";
  const decisionReasons = Array.isArray(analysis.reasonCodes) && analysis.reasonCodes.length ? analysis.reasonCodes : ["UNKNOWN"];
  const decisionLabel = ({ LONG: "明確偏多決策", SHORT: "明確偏空決策", HOLD_EXISTING: "維持現有部位", NO_TRADE: "暫不交易", UNKNOWN: "交易決策未確認" })[decisionState];
  const eligibilityLabel = decisionState === "NO_TRADE" ? "不可建立新部位" : decisionState === "HOLD_EXISTING" ? "維持現有部位；不代表可建立新部位" : ["LONG", "SHORT"].includes(decisionState) && analysis.decisionEligible === true ? "既有決策明確允許該方向" : "是否可建立新部位尚未確認";
  const decisionNotice = `<div class="stock-theory-note decision-state-notice is-${decisionState.toLowerCase()}" role="status"><b>${escapeHtml(decisionLabel)}</b><span>${escapeHtml(eligibilityLabel)}</span><small>原因代碼：${escapeHtml(decisionReasons.map((code) => String(code || "UNKNOWN").toUpperCase()).join(", "))}</small>${(Array.isArray(analysis.reasonDetails) ? analysis.reasonDetails : []).map((item) => `<small>${escapeHtml(item)}</small>`).join("")}${decisionState === "NO_TRADE" ? `<small>策略描述不能覆蓋暫不交易決策。</small>` : ""}</div>`;
  return `
    <article class="panel-card tw-option-ai-card"${idAttr}>
      <div class="asset-hub-group-heading"><div><p class="panel-kicker">AI analysis</p><h3>${escapeHtml(title)}</h3></div><span>${({ MARKET_RISK: "市場風險", SIGNAL_RISK: "訊號風險", STRATEGY_RISK: "策略風險", PORTFOLIO_RISK: "投資組合風險", UNKNOWN: "風險類別未確認" })[analysis.riskType || analysis.riskClassification?.type || "UNKNOWN"] || "風險類別未確認"} · ${escapeHtml(analysis.riskLevel || "--")}</span></div>
      <div class="tw-option-ai-main"><strong>${escapeHtml(analysis.bias || "資料不足")}</strong><p>${escapeHtml((analysis.reasons || [])[0] || "尚無足夠資料說明方向。")}</p></div>
      ${decisionNotice}
       <div class="asset-option-chain-stats"><span><b>${formatAssetOptionNumber(analysis.supportLevel)}</b><small>支撐</small></span><span><b>${formatAssetOptionNumber(analysis.resistanceLevel)}</b><small>壓力</small></span><span><b>${escapeHtml(analysis.riskLevel || "--")}</b><small>風險等級</small></span><span><b>${Number.isFinite(Number(analysis.marketScore)) ? Number(analysis.marketScore).toFixed(0) : "--"}</b><small>市場分數</small></span><span><b>${Number.isFinite(Number(analysis.riskScore)) ? Number(analysis.riskScore).toFixed(0) : "--"}</b><small>${({ MARKET_RISK: "市場風險", SIGNAL_RISK: "訊號風險", STRATEGY_RISK: "策略風險", PORTFOLIO_RISK: "投資組合風險", UNKNOWN: "風險類別未確認" })[analysis.riskType || analysis.riskClassification?.type || "UNKNOWN"] || "風險類別未確認"}分數</small></span><span><b>${Number.isFinite(Number(analysis.evidenceScore)) ? Number(analysis.evidenceScore).toFixed(0) : "--"}</b><small>證據強度</small></span></div>
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
  const rollback = new URLSearchParams(window.location.search).get("td02-esm") === "off";
  window.location.replace(`derivatives-analytics.html${rollback ? "?td02-esm=off" : ""}#derivatives-analytics-market-state`);
}
