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
  const statusText = chain.error
    ? "公開選擇權鏈暫時無法取得；可重新選取標的再試。"
    : chain.summary
      ? `${selectedSymbol} 公開鏈資料已載入，請選擇其他標的查看。`
      : "選取標的以載入公開選擇權鏈。";
  const statusTone = chain.error ? "error" : chain.summary ? "ready" : "idle";
  const safeSelectedSymbol = escapeHtml(selectedSymbol);
  const safeStatusText = statusText.replace(selectedSymbol, safeSelectedSymbol);
  return `
    <article class="panel-card asset-option-chain-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">US option chain</p>
          <h4>${safeSelectedSymbol} 公開選擇權鏈摘要</h4>
        </div>
        <span>${escapeHtml(formatAssetHubExpiration(chain.selectedExpiration))}</span>
      </div>
      <div class="tw-option-expiry-tabs" aria-label="美股選擇權標的切換">
        ${ASSET_HUB_OPTION_CHAIN_UNDERLYINGS.map(([symbol, label]) => `<button class="${symbol === selectedSymbol ? "is-active" : ""}" type="button" data-asset-option-underlying="${symbol}"><b>${symbol}</b><small>${escapeHtml(label)}</small></button>`).join("")}
      </div>
      <p class="stock-theory-note" data-asset-option-status data-state="${statusTone}">${safeStatusText}</p>
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
  const states = new Set(["LONG", "SHORT", "HOLD_EXISTING", "NO_TRADE", "UNKNOWN"]);
  const rawState = String(analysis.decisionState || "UNKNOWN").toUpperCase();
  const state = states.has(rawState) ? rawState : "UNKNOWN";
  const reasonCodes = Array.isArray(analysis.reasonCodes) && analysis.reasonCodes.length ? analysis.reasonCodes : ["UNKNOWN"];
  const stateLabel = ({ LONG: "明確偏多決策", SHORT: "明確偏空決策", HOLD_EXISTING: "維持現有部位", NO_TRADE: "暫不交易", UNKNOWN: "交易決策未確認" })[state];
  const eligibility = state === "NO_TRADE" ? "不可建立新部位" : state === "HOLD_EXISTING" ? "維持現有部位；不代表可建立新部位" : ["LONG", "SHORT"].includes(state) && analysis.decisionEligible === true ? "此方向符合既有明確決策資格" : "是否可建立新部位尚未確認";
  const decisionNotice = `<div class="stock-theory-note decision-state-notice is-${state.toLowerCase()}" role="status"><b>${escapeHtml(stateLabel)}</b><span>${escapeHtml(eligibility)}</span><small>原因代碼：${escapeHtml(reasonCodes.map((code) => String(code || "UNKNOWN").toUpperCase()).join(", "))}</small>${["UNKNOWN", "NO_TRADE"].includes(state) ? `<small>策略傾向（僅供研究描述）：${escapeHtml(analysis.strategyBias || analysis.strategySuggestion || "尚無策略描述")}</small>` : ""}</div>`;
  return `
    <article class="panel-card tw-option-ai-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI analysis</p>
          <h4>台灣選擇權 AI 盤勢摘要</h4>
        </div>
        <span>${({ MARKET_RISK: "市場風險", SIGNAL_RISK: "訊號風險", STRATEGY_RISK: "策略風險", PORTFOLIO_RISK: "投資組合風險", UNKNOWN: "風險類別未確認" })[analysis.riskType || analysis.riskClassification?.type || "UNKNOWN"] || "風險類別未確認"} · ${escapeHtml(analysis.riskLevel || "--")}</span>
      </div>
      <div class="tw-option-ai-main">
        <strong>${escapeHtml(analysis.bias || "資料同步中")}</strong>
        <p>${escapeHtml(reasons[0] || "等待 TAIFEX 選擇權鏈、PCR 與最大痛點資料。")}</p>
      </div>
      <div class="asset-option-chain-stats">
        <span><b>${Number.isFinite(Number(analysis.marketScore)) ? Number(analysis.marketScore).toFixed(0) : "--"}</b><small>市場分數</small></span>
        <span><b>${Number.isFinite(Number(analysis.riskScore)) ? Number(analysis.riskScore).toFixed(0) : "--"}</b><small>${({ MARKET_RISK: "市場風險", SIGNAL_RISK: "訊號風險", STRATEGY_RISK: "策略風險", PORTFOLIO_RISK: "投資組合風險", UNKNOWN: "風險類別未確認" })[analysis.riskType || analysis.riskClassification?.type || "UNKNOWN"] || "風險類別未確認"}分數</small></span>
        <span><b>${Number.isFinite(Number(analysis.evidenceScore)) ? Number(analysis.evidenceScore).toFixed(0) : "--"}</b><small>證據強度</small></span>
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
      ${decisionNotice}
      <p class="stock-theory-note"><b>策略說明：</b>${escapeHtml(analysis.strategySuggestion || "資料不足時不輸出方向性策略。")}</p>
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
function clampAssetHubScore(value, min = 0, max = 100) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return min;
  return Math.min(max, Math.max(min, parsed));
}
function createAssetHubPlaceholder(category, title, kicker, error = "") {
  const sourceByCategory = {
    futures: "TAIFEX 官方期貨日報",
    options: "TAIFEX / CBOE / Yahoo Finance",
    "precious-metals": "Yahoo Finance / LBMA",
    bonds: "U.S. Treasury / Yahoo Finance",
  };
  const source = sourceByCategory[category] || "公開來源同步中";
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
      primary: source,
      reference: "來源同步中",
    },
    source,
    updatedAt: "--",
    status: error ? "unavailable" : "pending",
    error,
  };
}