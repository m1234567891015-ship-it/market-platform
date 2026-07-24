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
