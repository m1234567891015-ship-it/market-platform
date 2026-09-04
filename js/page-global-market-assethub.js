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
function buildAssetFinanceGlobalVenueInsight(model) {
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const platinumPct = parseMarketNumber(model.platinum?.pct);
  const palladiumPct = parseMarketNumber(model.palladium?.pct);
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const tenYear = model.yields[2] || {};
  const tenYearValue = tenYear.value;
  const etfAvg = averageAssetFinancePct(model.globalMetalEtfs);
  const minerAvg = averageAssetFinancePct(model.minerStocks);
  const taiwanAvg = averageAssetFinancePct(model.taiwanMetalEtfs);
  const metalAvg = averageAssetFinanceValues([goldPct, silverPct, platinumPct, palladiumPct]);
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : null;
  const taiwanSpread = Number.isFinite(taiwanAvg) && Number.isFinite(metalAvg) ? taiwanAvg - metalAvg : null;
  const macroPressure = (Number.isFinite(dxyPct) && dxyPct > 0.35) || (Number.isFinite(tenYearValue) && tenYearValue >= 4.2);
  const fundPulse = averageAssetFinanceValues([etfAvg, minerAvg].filter(Number.isFinite));
  const venueConclusion = macroPressure && Number.isFinite(goldPct) && goldPct > 0
    ? "AI 判讀：美元或利率偏強但黃金抗跌，全球場域重點放在倫敦現貨與 COMEX 期貨是否同步承接避險買盤。"
    : Number.isFinite(silverLead) && silverLead > 0 && Number.isFinite(fundPulse) && fundPulse > 0
      ? "AI 判讀：白銀、ETF 與礦商同步轉強，場域重點從黃金現貨擴散到 COMEX 流動性與亞洲實體需求。"
      : Number.isFinite(fundPulse) && fundPulse < 0
        ? "AI 判讀：價格與資金面沒有共振，全球場域先看 COMEX 成交與 ETF 是否回流，避免把單日反彈誤判成趨勢。"
        : "AI 判讀：全球場域仍屬等待確認，先用倫敦現貨定價、COMEX 期貨流動性與亞洲實需交叉驗證。";
  const markets = [
    [
      "倫敦 LBMA / OTC",
      "現貨定價核心",
      Number.isFinite(goldPct) && goldPct > 0
        ? `黃金 ${formatAssetFinancePct(goldPct)}，現貨防禦需求仍在。`
        : `黃金 ${model.gold?.pct || "--"}，先看現貨基準是否止穩。`,
    ],
    [
      "美國 COMEX / CME",
      "期貨流動性核心",
      Number.isFinite(silverLead) && silverLead > 0
        ? `白銀相對黃金 ${formatAssetFinancePct(silverLead)}，短線槓桿資金有擴散跡象。`
        : `ETF ${formatAssetFinancePct(etfAvg)} / 礦商 ${formatAssetFinancePct(minerAvg)}，需等期貨資金確認。`,
    ],
    [
      "上海 SGE",
      "亞洲實體需求",
      Number.isFinite(taiwanSpread)
        ? `台灣商品相對國際 ${formatAssetFinancePct(taiwanSpread)}，可作亞洲需求與匯率落差參考。`
        : "亞洲實體需求同步中，先用黃金與白銀國際價格判讀。",
    ],
    [
      "香港",
      "實體流通樞紐",
      macroPressure
        ? "美元利率壓力下，留意亞洲實體買盤是否承接回檔。"
        : "用庫存、轉口與亞洲溢價觀察中國與國際市場連動。",
    ],
    [
      "日本 OSE",
      "區域避險補充",
      model.riskScore >= 72
        ? `避險分數 ${model.riskScore}/100，日圓與亞洲避險需求需要同步觀察。`
        : `10Y ${formatAssetHubYield(tenYearValue)}，區域期貨先作輔助確認。`,
    ],
  ];
  return { venueConclusion, markets };
}
function renderAssetFinanceDriverFactorCard(factor) {
  const score = Math.round(clampAssetHubScore(factor.score, 0, 100));
  return `
    <section class="asset-finance-driver-factor is-${escapeHtml(factor.tone || "flat")}">
      <span>
        <small>${escapeHtml(factor.label)}</small>
        <b>${escapeHtml(factor.status)}</b>
      </span>
      <strong>${escapeHtml(factor.value)}</strong>
      <div class="asset-finance-driver-meter" style="--driver-score:${score}%"><i></i></div>
      <p>${escapeHtml(factor.detail)}</p>
      <div class="asset-finance-driver-predict"><b>預測影響</b><small>${escapeHtml(factor.forecast || "")}</small></div>
      <em>${escapeHtml(factor.watch)}</em>
    </section>
  `;
}
function formatAssetFinanceMetricPct(value) {
  return Number.isFinite(value) ? formatAssetFinancePct(value) : "--";
}
function averageAssetFinanceValues(values = []) {
  const clean = values.filter(Number.isFinite);
  if (!clean.length) return null;
  return clean.reduce((sum, value) => sum + value, 0) / clean.length;
}
function standardDeviationAssetFinanceValues(values = []) {
  const avg = averageAssetFinanceValues(values);
  if (!Number.isFinite(avg)) return null;
  const variance = values
    .filter(Number.isFinite)
    .reduce((sum, value) => sum + ((value - avg) ** 2), 0) / Math.max(values.filter(Number.isFinite).length, 1);
  return Math.sqrt(variance);
}
function buildAssetFinanceForecastItem({ label, code, key, item, model }) {
  const series = normalizeGlobalSeries(item?.series || []);
  const close = parseMarketNumber(item?.close) || series.at(-1)?.value;
  if (!Number.isFinite(close) || close <= 0) return null;
  const values = series.map((point) => point.value).filter(Number.isFinite);
  const lastValue = values.at(-1) || close;
  const returns = [];
  for (let index = 1; index < values.length; index += 1) {
    const prev = values[index - 1];
    const current = values[index];
    if (Number.isFinite(prev) && prev > 0 && Number.isFinite(current)) {
      returns.push(((current / prev) - 1) * 100);
    }
  }
  const recentReturns = returns.slice(-20);
  const dailyAvg = averageAssetFinanceValues(recentReturns) ?? (parseMarketNumber(item?.pct) || 0);
  const dailyVol = standardDeviationAssetFinanceValues(recentReturns) ?? 1.2;
  const momentum5 = values.length >= 6 ? ((lastValue / values[values.length - 6]) - 1) * 100 : (parseMarketNumber(item?.pct) || 0);
  const momentum20 = values.length >= 21 ? ((lastValue / values[values.length - 21]) - 1) * 100 : momentum5;
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const etfAvg = averageAssetFinancePct(model.globalMetalEtfs);
  const minerAvg = averageAssetFinancePct(model.minerStocks);
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : 0;
  let macroBias = 0;
  if (Number.isFinite(dxyPct)) macroBias += dxyPct < 0 ? Math.min(Math.abs(dxyPct) * 0.08, 0.18) : -Math.min(dxyPct * 0.08, 0.18);
  if (model.riskScore >= 72) macroBias += key === "gold" ? 0.18 : 0.04;
  if (model.riskScore <= 46 && key !== "gold") macroBias += 0.08;
  if (key !== "gold" && Number.isFinite(silverLead)) macroBias += clampAssetHubScore(silverLead * 0.05, -0.16, 0.18);
  if (Number.isFinite(etfAvg)) macroBias += clampAssetHubScore(etfAvg * 0.025, -0.12, 0.12);
  if (Number.isFinite(minerAvg) && key !== "gold") macroBias += clampAssetHubScore(minerAvg * 0.018, -0.1, 0.12);
  const baseDailyPct = clampAssetHubScore((dailyAvg * 0.38) + ((momentum5 / 5) * 0.32) + ((momentum20 / 20) * 0.18) + macroBias, -1.8, 1.8);
  const horizons = [
    { label: "1日", days: 1 },
    { label: "5日", days: 5 },
    { label: "20日", days: 20 },
  ].map((horizon) => {
    const expectedPct = clampAssetHubScore(baseDailyPct * horizon.days, -24, 24);
    const rangePct = clampAssetHubScore(dailyVol * Math.sqrt(horizon.days) * 1.08, 0.28, 18);
    return {
      ...horizon,
      expectedPct,
      target: close * (1 + expectedPct / 100),
      low: close * (1 + (expectedPct - rangePct * 0.55) / 100),
      high: close * (1 + (expectedPct + rangePct * 0.55) / 100),
    };
  });
  const medium = horizons.find((entry) => entry.days === 20) || horizons.at(-1);
  const tone = medium.expectedPct > 1.2 ? "up" : medium.expectedPct < -1.2 ? "down" : "flat";
  const direction = tone === "up" ? "偏多預測" : tone === "down" ? "偏弱預測" : "區間預測";
  const confidence = Math.round(clampAssetHubScore(42 + Math.min(series.length, 90) * 0.35 + (model.confidence || 0) * 0.12 - Math.max(0, dailyVol - 2.2) * 4, 35, 92));
  const basis = [
    `5日動能 ${formatAssetFinanceMetricPct(momentum5)}`,
    `20日動能 ${formatAssetFinanceMetricPct(momentum20)}`,
    `日波動 ${formatAssetFinanceMetricPct(dailyVol)}`,
  ].join(" / ");
  const assumption = tone === "up"
    ? "預測成立條件：美元利率不再同步上壓，ETF 或礦商至少一項維持正向。"
    : tone === "down"
      ? "預測成立條件：美元利率壓力延續，且 ETF 或礦商未出現回補買盤。"
      : "預測成立條件：主要因子未共振，價格維持區間波動並等待新訊號。";
  return {
    label,
    code,
    key,
    close,
    pct: item?.pct || "--",
    tone,
    direction,
    confidence,
    momentum5,
    momentum20,
    dailyVol,
    basis,
    assumption,
    horizons,
  };
}
function buildAssetFinancePriceForecastItems(model) {
  return [
    { label: "黃金", code: "XAU", key: "gold", item: model.gold },
    { label: "白銀", code: "XAG", key: "silver", item: model.silver },
    { label: "鉑金", code: "XPT", key: "platinum", item: model.platinum },
    { label: "鈀金", code: "XPD", key: "palladium", item: model.palladium },
  ].map((entry) => buildAssetFinanceForecastItem({ ...entry, model })).filter(Boolean);
}
function renderAssetFinancePriceForecastBody(forecasts = [], metalKey = "all", rangeKey = "1m") {
  const selectedForecasts = metalKey === "all"
    ? forecasts
    : forecasts.filter((forecast) => forecast.key === metalKey);
  const visibleForecasts = selectedForecasts.length ? selectedForecasts : forecasts;
  const horizon20 = forecasts
    .map((item) => ({ item, target: item.horizons.find((entry) => entry.days === 20) }))
    .filter((entry) => entry.target);
  const focusedForecast = metalKey === "all" ? null : visibleForecasts[0];
  const focused20 = focusedForecast?.horizons.find((entry) => entry.days === 20);
  const strongestForecast = [...horizon20].sort((left, right) => right.target.expectedPct - left.target.expectedPct)[0];
  const weakestForecast = [...horizon20].sort((left, right) => left.target.expectedPct - right.target.expectedPct)[0];
  const avgForecastPct = averageAssetFinanceValues(horizon20.map((entry) => entry.target.expectedPct));
  const activeFilter = ASSET_FINANCE_TREND_FILTERS.find((filter) => filter.key === metalKey)?.label || "全部";
  const activeRange = getAssetFinanceTrendRange(rangeKey);
  const forecastTheme = Number.isFinite(avgForecastPct) && avgForecastPct > 1.2
    ? "整體預測偏多"
    : Number.isFinite(avgForecastPct) && avgForecastPct < -1.2
      ? "整體預測偏弱"
      : "整體預測區間震盪";
  const readoutHtml = focusedForecast
    ? `
        <span><small>檢視標的</small><b>${escapeHtml(focusedForecast.label)} / ${escapeHtml(activeRange.label)}</b></span>
        <span><small>20日預測</small><b class="${assetFinancePctTone(focused20?.expectedPct)}">${focused20 ? `${formatGlobalValue(focused20.target)} ${formatAssetFinancePct(focused20.expectedPct)}` : "--"}</b></span>
        <span><small>20日風險區間</small><b>${focused20 ? `${formatGlobalValue(focused20.low)} - ${formatGlobalValue(focused20.high)}` : "--"}</b></span>
        <span><small>模型信心</small><b>${focusedForecast.confidence}/100</b></span>
      `
    : `
        <span><small>預測主題</small><b>${escapeHtml(forecastTheme)}</b></span>
        <span><small>20日強勢</small><b>${strongestForecast ? `${escapeHtml(strongestForecast.item.label)} ${formatAssetFinancePct(strongestForecast.target.expectedPct)}` : "--"}</b></span>
        <span><small>20日弱勢</small><b>${weakestForecast ? `${escapeHtml(weakestForecast.item.label)} ${formatAssetFinancePct(weakestForecast.target.expectedPct)}` : "--"}</b></span>
        <span><small>平均預測</small><b class="${assetFinancePctTone(avgForecastPct)}">${formatAssetFinancePct(avgForecastPct)}</b></span>
      `;
  return `
      <div class="asset-finance-forecast-readout">
        ${readoutHtml}
      </div>
      <div class="asset-finance-forecast-grid ${focusedForecast ? "is-focused" : ""}">
        ${visibleForecasts.map((forecast) => `
          <section class="is-${escapeHtml(forecast.tone)}">
            <div class="asset-finance-forecast-head">
              <small>${escapeHtml(forecast.code)}</small>
              <em>信心 ${forecast.confidence}/100</em>
            </div>
            <h5>${escapeHtml(forecast.label)}</h5>
            <div class="asset-finance-forecast-current">
              <span><small>現價</small><b>${formatGlobalValue(forecast.close)}</b></span>
              <span><small>模型方向</small><b class="${escapeHtml(forecast.tone)}">${escapeHtml(forecast.direction)}</b></span>
            </div>
            <div class="asset-finance-forecast-rows">
              ${forecast.horizons.map((target) => `
                <span>
                  <b>${escapeHtml(target.label)}</b>
                  <strong>${formatGlobalValue(target.target)}</strong>
                  <small class="${assetFinancePctTone(target.expectedPct)}">${formatAssetFinancePct(target.expectedPct)}</small>
                  <em>${formatGlobalValue(target.low)} - ${formatGlobalValue(target.high)}</em>
                </span>
              `).join("")}
            </div>
            <p>${escapeHtml(forecast.basis)}。</p>
            <p class="asset-finance-forecast-assumption">${escapeHtml(forecast.assumption)}</p>
          </section>
        `).join("") || `<p class="stock-detail-empty">價格序列同步中，暫無可用預測。</p>`}
      </div>
      <p class="stock-theory-note">目前跟隨走勢圖切換：${escapeHtml(activeRange.label)} / ${escapeHtml(activeFilter)}。分析預測模型使用歷史序列、短中期動能、美元利率、避險分數、ETF 與礦商確認計算；輸出為情境價格與風險區間，不是保證價格。</p>
  `;
}
function renderAssetFinancePriceForecastContent(model, options = {}) {
  const forecasts = buildAssetFinancePriceForecastItems(model);
  const embedded = Boolean(options.embedded);
  const payload = JSON.stringify(forecasts);
  return `
    <div class="asset-finance-forecast-content ${embedded ? "is-embedded" : ""}" data-asset-finance-forecast-panel data-asset-finance-forecast-payload="${escapeHtml(payload)}">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI price forecast</p>
          <h4>AI 貴金屬分析預測</h4>
        </div>
        <span>1日 / 5日 / 20日</span>
      </div>
      <div data-asset-finance-forecast-view>
        ${renderAssetFinancePriceForecastBody(forecasts)}
      </div>
    </div>
  `;
}
function renderAssetFinanceMetalDriversPanel(model) {
  const tenYear = model.yields[2] || {};
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const tenYearValue = tenYear.value;
  const vixValue = parseMarketNumber(model.vix?.close);
  const vixPct = parseMarketNumber(model.vix?.pct);
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const platinumPct = parseMarketNumber(model.platinum?.pct);
  const palladiumPct = parseMarketNumber(model.palladium?.pct);
  const industrialPulseValues = [silverPct, platinumPct, palladiumPct].filter(Number.isFinite);
  const industrialPulse = industrialPulseValues.length
    ? industrialPulseValues.reduce((sum, value) => sum + value, 0) / industrialPulseValues.length
    : null;
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : null;
  const dxyPressure = Number.isFinite(dxyPct) ? clampAssetHubScore(50 + dxyPct * 55, 8, 96) : 50;
  const ratePressure = Number.isFinite(tenYearValue) ? clampAssetHubScore(44 + (tenYearValue - 3.6) * 22, 8, 96) : 50;
  const hedgePulse = Number.isFinite(model.riskScore) ? clampAssetHubScore(model.riskScore, 8, 96) : 50;
  const industrialScore = Number.isFinite(industrialPulse) ? clampAssetHubScore(50 + industrialPulse * 9, 8, 96) : 50;
  const ratioScore = Number.isFinite(model.goldSilverRatio) ? clampAssetHubScore((model.goldSilverRatio - 55) * 2.25, 8, 96) : 50;
  const etfAvg = averageAssetFinancePct(model.globalMetalEtfs);
  const minerAvg = averageAssetFinancePct(model.minerStocks);
  const fundPulseValues = [etfAvg, minerAvg].filter(Number.isFinite);
  const fundPulse = fundPulseValues.length
    ? fundPulseValues.reduce((sum, value) => sum + value, 0) / fundPulseValues.length
    : null;
  const macroScore = Math.round((dxyPressure + ratePressure) / 2);
  const capitalScore = Number.isFinite(fundPulse)
    ? clampAssetHubScore(50 + fundPulse * 8 + (Number.isFinite(model.goldSilverRatio) && model.goldSilverRatio < 72 ? 8 : 0), 8, 96)
    : ratioScore;
  const macroTone = (Number.isFinite(dxyPct) && dxyPct > 0.25) || (Number.isFinite(tenYearValue) && tenYearValue >= 4.2)
    ? "down"
    : (Number.isFinite(dxyPct) && dxyPct < -0.25) && (Number.isFinite(tenYearValue) ? tenYearValue < 4.2 : true)
      ? "up"
      : "flat";
  const fundTone = Number.isFinite(fundPulse) && fundPulse > 0.35
    ? "up"
    : Number.isFinite(fundPulse) && fundPulse < -0.35
      ? "down"
      : "flat";
  const factors = [
    {
      label: "美元利率壓力",
      value: `DXY ${model.dxy?.pct || "--"} / 10Y ${formatAssetHubYield(tenYearValue)}`,
      score: macroScore,
      tone: macroTone,
      status: macroTone === "down" ? "機會成本偏高" : macroTone === "up" ? "壓力降溫" : "宏觀壓力中性",
      detail: "美元與美債殖利率共同決定無息資產的持有成本；若兩者上行，黃金需靠避險或通膨預期抵消壓力。",
      forecast: macroTone === "down" ? "下修短線目標價權重，預測更偏區間或回檔。" : macroTone === "up" ? "提高 1日與5日反彈機率，黃金預測彈性優先。" : "維持中性假設，等待美元與10Y同向突破。",
      watch: `DXY ${model.dxy?.pct || "--"}、10Y 變動 ${tenYear.item?.pct || "--"}，同步走強時降低追價。`,
    },
    {
      label: "避險需求",
      value: `VIX ${formatGlobalValue(model.vix?.close)}`,
      score: hedgePulse,
      tone: model.riskScore >= 72 ? "up" : model.riskScore >= 52 ? "flat" : "down",
      status: model.riskScore >= 72 ? "避險需求升溫" : model.riskScore >= 52 ? "防禦需求中性" : "風險偏好較穩",
      detail: "VIX、曲線倒掛、美元與黃金同漲時，黃金通常優先受益；白銀需等待風險偏好回穩。",
      forecast: model.riskScore >= 72 ? "提高黃金預測支撐，但白銀與鉑鈀需等風險偏好回穩。" : "避險溢價有限，預測需更依賴動能與資金確認。",
      watch: `VIX 日變動 ${Number.isFinite(vixPct) ? formatAssetFinancePct(vixPct) : "--"}，避險分數 ${model.riskScore}/100。`,
    },
    {
      label: "工業需求脈動",
      value: Number.isFinite(industrialPulse) ? formatAssetFinancePct(industrialPulse) : "--",
      score: industrialScore,
      tone: Number.isFinite(industrialPulse) && industrialPulse > 0.35 ? "up" : Number.isFinite(industrialPulse) && industrialPulse < -0.35 ? "down" : "flat",
      status: Number.isFinite(silverLead) && silverLead > 0 ? "白銀與工業金屬追上" : "工業端等待確認",
      detail: "白銀、鉑金、鈀金更受太陽能、汽車觸媒、氫能與礦產供給影響，常用來判斷行情是否由避險擴散到景氣交易。",
      forecast: Number.isFinite(silverLead) && silverLead > 0 ? "提高白銀、鉑金與鈀金的20日預測彈性。" : "工業金屬未接棒時，預測重心仍偏黃金防禦。",
      watch: `白銀相對黃金 ${formatAssetFinanceMetricPct(silverLead)}，鉑鈀需看供給與車市循環。`,
    },
    {
      label: "資金與相對價值",
      value: `ETF ${formatAssetFinanceMetricPct(etfAvg)} / 金銀比 ${formatAssetHubRatio(model.goldSilverRatio)}`,
      score: capitalScore,
      tone: fundTone,
      status: fundTone === "up" ? "資金確認偏多" : fundTone === "down" ? "資金動能偏弱" : model.goldSilverRatio <= 70 ? "白銀追價偏強" : "等待資金確認",
      detail: "ETF 與礦商用來確認價格是否有資金跟進；金銀比則判斷行情集中在黃金防禦，或已擴散到白銀與工業需求。",
      forecast: fundTone === "up" ? "提高預測信心與延續性，尤其是白銀與礦商相關標的。" : fundTone === "down" ? "降低趨勢延伸假設，目標價需保守。" : "先保留區間預測，等待資金確認。",
      watch: `礦商平均 ${formatAssetFinanceMetricPct(minerAvg)}；若礦商強於 ETF，行情延續性較佳。`,
    },
  ];
  const dominantFactor = [...factors].sort((left, right) => right.score - left.score)[0];
  const silverLeadText = Number.isFinite(silverLead) ? formatAssetFinanceMetricPct(silverLead) : "--";
  const driverFundingText = `ETF ${formatAssetFinanceMetricPct(etfAvg)} / 礦商 ${formatAssetFinanceMetricPct(minerAvg)}`;
  const driverHeadline = (() => {
    if (fundTone === "up" && Number.isFinite(silverLead) && silverLead > 0) {
      return `資金與價格同時轉強，${driverFundingText}，白銀相對黃金 ${silverLeadText}；這代表買盤不只停在黃金避險，而是擴散到白銀與礦商彈性。`;
    }
    if (Number.isFinite(dxyPct) && dxyPct > 0 && Number.isFinite(goldPct) && goldPct > 0) {
      return "美元與黃金同漲，偏向避險或通膨疑慮主導；若 ETF 與礦商未同步補強，仍不宜把單日上漲解讀成完整多頭。";
    }
    if (model.riskScore >= 72) {
      return `避險分數 ${model.riskScore}/100 偏高，黃金仍是第一層防禦；白銀與礦商需要資金確認，才算從防守轉為進攻。`;
    }
    return "目前驅動因子仍在拉扯，先以區間模型處理，等待價格、資金與美元利率至少兩項同向後再提高預測信心。";
  })();
  const driverConfirmation = dominantFactor?.label === "美元利率壓力"
    ? `確認黃金是否能在 DXY ${model.dxy?.pct || "--"}、10Y ${formatAssetHubYield(tenYearValue)} 下維持抗跌。`
    : dominantFactor?.label === "避險需求"
      ? `確認 VIX ${formatGlobalValue(model.vix?.close)} 與金銀比 ${formatAssetHubRatio(model.goldSilverRatio)} 是否同步走高。`
      : dominantFactor?.label === "工業需求脈動"
        ? `確認白銀相對黃金 ${silverLeadText}，以及鉑鈀是否延續補漲。`
        : `確認 ${driverFundingText} 是否同向，若礦商續強，代表市場願意押槓桿彈性。`;
  const driverForecastAxis = dominantFactor?.forecast || "模型暫以區間預測為主，等待價格與資金共振。";
  const driverFailure = macroTone === "down" && fundTone !== "up"
    ? "若美元利率續強且 ETF 未流入，偏多預測失效。"
    : model.riskScore >= 72
      ? "若 VIX 回落但白銀與礦商未接棒，避險行情可能退潮。"
      : "若價格突破但資金與礦商背離，預測需下修為區間。";
  const driverNextStep = Number.isFinite(silverLead) && silverLead > 0 && Number.isFinite(fundPulse) && fundPulse > 0
    ? "先看白銀、礦商與 ETF 是否連續領先；若續強，代表行情正在從黃金防禦擴散到高 Beta 標的。"
    : model.riskScore >= 72
      ? "先看黃金能否守穩，再看白銀與礦商是否補強，避免只追避險急漲。"
      : "先以區間判讀，等待美元利率、ETF 資金與工業金屬至少兩項同向。";
  const dominantScore = Math.round(clampAssetHubScore(dominantFactor?.score ?? 50, 0, 100));
  const metalMomentum = [
    { label: "黃金", value: goldPct },
    { label: "白銀", value: silverPct },
    { label: "鉑金", value: platinumPct },
    { label: "鈀金", value: palladiumPct },
  ].filter((item) => Number.isFinite(item.value));
  const strongestMetal = [...metalMomentum].sort((left, right) => right.value - left.value)[0] || null;
  const weakestMetal = [...metalMomentum].sort((left, right) => left.value - right.value)[0] || null;
  const forecastBias = fundTone === "up" && Number.isFinite(silverLead) && silverLead > 0
    ? {
      label: "擴散偏多",
      detail: "資金與白銀同時轉強，預測可由黃金防禦延伸到白銀與礦商彈性。",
      base: "基準路徑：偏多仍以擴散行情為主，黃金提供底部支撐，白銀與礦商負責彈性。",
      upgrade: "追價條件：ETF、礦商連續轉強，且 DXY 或 10Y 不再同步上壓。",
      downgrade: "降級警戒：金銀比回升或白銀轉弱，代表擴散行情退回黃金防禦。",
    }
    : macroTone === "down" && fundTone !== "up"
      ? {
        label: "壓力區間",
        detail: "美元利率壓力仍在，預測需降低追價假設，先看支撐與波動區間。",
        base: "基準路徑：價格以區間震盪為主，黃金抗跌性優於工業金屬。",
        upgrade: "轉強條件：美元或 10Y 轉弱，黃金仍守高檔並帶動 ETF 回流。",
        downgrade: "降級警戒：美元利率續強且礦商走弱，20日目標需保守下修。",
      }
      : model.riskScore >= 72
        ? {
          label: "黃金防禦",
          detail: "避險需求主導，預測重心先放在黃金支撐，白銀與鉑鈀等補強確認。",
          base: "基準路徑：黃金維持防禦溢價，白銀與鉑鈀需等待風險偏好回穩。",
          upgrade: "轉強條件：VIX 高檔但美元未續強，ETF 與礦商同步補量。",
          downgrade: "降級警戒：VIX 回落且資金未接棒，避險買盤可能快速退潮。",
        }
        : {
          label: "等待共振",
          detail: "單一因子不足以推升預測信心，需等待價格、資金、美元利率至少兩項同向。",
          base: "基準路徑：維持區間模型，短線以 1日與5日目標作風險控管。",
          upgrade: "轉強條件：ETF、礦商或工業金屬補強，推升20日預測彈性。",
          downgrade: "降級警戒：價格突破但量能與資金背離，模型降回中性震盪。",
        };
  const driverPulse = [
    ["主導因子", dominantFactor?.label || "--", `分數 ${dominantScore}/100；${dominantFactor?.status || "同步中"}`],
    ["預測傾向", forecastBias.label, forecastBias.detail],
    ["領先 / 落後", strongestMetal ? `${strongestMetal.label} ${formatAssetFinanceMetricPct(strongestMetal.value)}` : "--", weakestMetal ? `落後 ${weakestMetal.label} ${formatAssetFinanceMetricPct(weakestMetal.value)}；白銀相對黃金 ${silverLeadText}` : "金屬同步中"],
    ["資金驗證", driverFundingText, fundTone === "up" ? "資金與價格同向，延續性提高。" : fundTone === "down" ? "資金尚未跟上，追價需保守。" : "等待 ETF 與礦商同步。"],
  ];
  const driverScenarios = [
    ["基準路徑", forecastBias.base],
    ["轉強條件", forecastBias.upgrade],
    ["降級警戒", forecastBias.downgrade],
  ];
  return `
    <article class="panel-card asset-finance-module-card asset-finance-metal-driver-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Price drivers</p>
          <h4>貴金屬價格驅動因素</h4>
        </div>
        <span>${escapeHtml(dominantFactor?.label || "Macro + supply")}</span>
      </div>
      <div class="asset-finance-driver-factor-grid">
        ${factors.map(renderAssetFinanceDriverFactorCard).join("")}
      </div>
      <div class="asset-finance-driver-readout is-${escapeHtml(dominantFactor?.tone || "flat")}">
        <div class="asset-finance-driver-readout-head">
          <div>
            <small>目前主線</small>
            <strong>${escapeHtml(dominantFactor?.status || "等待資料同步")}</strong>
          </div>
          <span>${dominantScore}/100</span>
        </div>
        <div class="asset-finance-driver-pulse-row">
          ${driverPulse.map(([label, value, detail]) => `
            <span>
              <small>${escapeHtml(label)}</small>
              <b>${escapeHtml(value)}</b>
              <em>${escapeHtml(detail)}</em>
            </span>
          `).join("")}
        </div>
        <p class="asset-finance-driver-thesis"><b>AI 判讀</b>${escapeHtml(driverHeadline)}</p>
        <div class="asset-finance-driver-scenario-grid">
          ${driverScenarios.map(([label, text]) => `
            <section>
              <b>${escapeHtml(label)}</b>
              <small>${escapeHtml(text)}</small>
            </section>
          `).join("")}
        </div>
        <div class="asset-finance-driver-summary-grid">
          <span><b>預測主軸</b><small>${escapeHtml(driverForecastAxis)}</small></span>
          <span><b>模型驗證</b><small>${escapeHtml(driverConfirmation)}</small></span>
          <span><b>失效條件</b><small>${escapeHtml(driverFailure)}</small></span>
          <span><b>下一步觀察</b><small>${escapeHtml(driverNextStep)}</small></span>
        </div>
      </div>
    </article>
  `;
}
function renderAssetFinanceDecisionCenterPanel(model) {
  const goldPct = parseMarketNumber(model.gold?.pct);
  const silverPct = parseMarketNumber(model.silver?.pct);
  const platinumPct = parseMarketNumber(model.platinum?.pct);
  const palladiumPct = parseMarketNumber(model.palladium?.pct);
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const etfAvg = averageAssetFinancePct(model.globalMetalEtfs);
  const minerAvg = averageAssetFinancePct(model.minerStocks);
  const taiwanAvg = averageAssetFinancePct(model.taiwanMetalEtfs);
  const bestEtf = strongestAssetFinanceItem(model.globalMetalEtfs);
  const bestMiner = strongestAssetFinanceItem(model.minerStocks);
  const silverLead = Number.isFinite(silverPct) && Number.isFinite(goldPct) ? silverPct - goldPct : null;
  const minerSpread = Number.isFinite(minerAvg) && Number.isFinite(etfAvg) ? minerAvg - etfAvg : null;
  const metalPctValues = [goldPct, silverPct, platinumPct, palladiumPct].filter(Number.isFinite);
  const positiveMetals = metalPctValues.filter((value) => value > 0).length;
  const tenYear = model.yields[2] || {};
  const tenYearValue = tenYear.value;
  const expectedMetalCount = metalPctValues.length || 4;
  const globalMetalAvg = averageAssetFinanceValues(metalPctValues);
  const taiwanSpread = Number.isFinite(taiwanAvg) && Number.isFinite(globalMetalAvg) ? taiwanAvg - globalMetalAvg : null;
  const broadMetalStrength = positiveMetals >= Math.min(3, expectedMetalCount);
  const silverLeadership = Number.isFinite(silverLead) && silverLead > 0;
  const fundConfirmation = Number.isFinite(etfAvg) && Number.isFinite(minerAvg) && etfAvg > 0 && minerAvg > 0;
  const minerLeadership = Number.isFinite(minerSpread) && minerSpread > 0;
  const dxyPressure = Number.isFinite(dxyPct) && dxyPct > 0.35;
  const ratePressure = Number.isFinite(tenYearValue) && tenYearValue >= 4.2;
  const macroPressure = dxyPressure || ratePressure;
  const fundDrag = Number.isFinite(etfAvg) && Number.isFinite(minerAvg) && etfAvg <= 0 && minerAvg <= 0;
  const goldResilience = Number.isFinite(goldPct) && goldPct > 0;
  const hedgeDemand = model.riskScore >= 72;
  const pressureProfile = (() => {
    if (fundDrag && !macroPressure) {
      return {
        label: "資金斷層",
        action: "美元與 10Y 尚未形成明顯壓力，但 ETF 與礦商沒有跟上，先判定為資金斷層，等待買盤確認再提高權重。",
        focus: "價格若走強但 ETF / 礦商背離，決策重心要放在延續性，而不是單日漲跌。",
        unlock: "ETF 與礦商任一組轉正，且金銀比不再惡化。",
        risk: "資金未回流時，金屬上漲可能缺乏第二段推力。",
      };
    }
    if (!macroPressure || fundConfirmation) return null;
    if (dxyPressure && ratePressure) {
      return {
        label: "雙壓觀望",
        action: goldResilience
          ? "美元與 10Y 同時施壓，但黃金仍抗跌；先視為避險買盤測試，不急著追白銀與礦商。"
          : "美元與 10Y 同時施壓且黃金未抗跌，觀望層級提高，先等待利率或美元至少一項降溫。",
        focus: "雙壓環境下，偏多訊號需同時看到 ETF 回流與礦商止穩，否則容易只是短線反彈。",
        unlock: "DXY 轉弱或 10Y 回落，且 ETF / 礦商至少一項轉正。",
        risk: "雙壓未解除時，追價容易被美元與實質利率壓回。",
      };
    }
    if (dxyPressure) {
      return {
        label: "美元壓制",
        action: goldResilience
          ? "美元走強但黃金仍抗跌，代表避險或通膨買盤仍在；先看金價能否守住，白銀等補強。"
          : "美元走強正在壓制金屬彈性，先降低追價，等待 DXY 轉弱或資金流回補。",
        focus: "美元壓制時，黃金抗跌比白銀追漲更重要；ETF 流入是解除壓力的第一訊號。",
        unlock: "DXY 漲幅收斂，且黃金維持正報酬或 ETF 平均轉正。",
        risk: "美元續強會讓金屬上漲缺乏延續性。",
      };
    }
    if (ratePressure) {
      return {
        label: "利率壓制",
        action: goldResilience
          ? "10Y 殖利率偏高但黃金仍能守穩，先看作防禦需求支撐，需等礦商或 ETF 補量再提高曝險。"
          : "10Y 殖利率偏高使持有黃金的機會成本升高，先以區間與停損控管，不放大槓桿。",
        focus: "利率壓制時，礦商若弱於 ETF 代表市場仍不願意押槓桿彈性。",
        unlock: "10Y 回落或礦商平均轉強，並帶動白銀相對黃金改善。",
        risk: "殖利率續高會壓低無息資產估值，偏多情境需下修。",
      };
    }
    return null;
  })();
  let score = 50;
  if (Number.isFinite(goldPct)) score += clampAssetHubScore(goldPct * 5, -12, 12);
  if (silverLeadership) score += 4;
  if (broadMetalStrength) score += 5;
  if (Number.isFinite(dxyPct)) score += dxyPct < 0 ? 6 : -4;
  if (Number.isFinite(etfAvg)) score += clampAssetHubScore(etfAvg * 2, -6, 6);
  if (Number.isFinite(minerAvg)) score += clampAssetHubScore(minerAvg * 2, -6, 6);
  if (fundConfirmation) score += 5;
  if (hedgeDemand) score += 6;
  if (macroPressure && !fundConfirmation) score -= 5;
  score = Math.round(clampAssetHubScore(score, 0, 100));
  const label = score >= 70 && silverLeadership && fundConfirmation
    ? "多頭擴散"
    : score >= 70 && hedgeDemand
      ? "避險偏多"
      : pressureProfile
        ? pressureProfile.label
        : score >= 48 && hedgeDemand
        ? "高波動防守"
        : score >= 48
          ? "區間輪動"
          : "轉弱降槓桿";
  const action = label === "多頭擴散"
    ? "價格擴散與資金確認同時成立，可把觀察重心從黃金延伸到白銀、礦商與 ETF。"
    : label === "避險偏多"
      ? "避險分數支撐黃金核心，但加碼前仍要確認美元與 10Y 利率沒有同步上壓。"
      : pressureProfile
        ? pressureProfile.action
        : label === "高波動防守"
          ? "避險需求升溫但波動也升高，保留黃金核心，避免追價白銀與礦商。"
          : label === "區間輪動"
            ? "多空訊號尚未共振，等待價格、ETF、礦商或美元利率至少兩項轉為同向。"
            : "價格與資金面未修復，降低追價權重，等待金銀比或礦商先行止穩。";
  const evidenceCards = [
    {
      title: "價格證據",
      tone: broadMetalStrength ? "up" : positiveMetals === 0 ? "down" : "flat",
      value: `${positiveMetals}/${expectedMetalCount} 金屬走強`,
      detail: [
        `黃金 ${model.gold?.pct || "--"}`,
        `白銀 ${model.silver?.pct || "--"}`,
        Number.isFinite(silverLead) ? `白銀相對黃金 ${formatAssetFinancePct(silverLead)}` : "金銀相對強弱同步中",
      ].join("；"),
    },
    {
      title: "資金證據",
      tone: fundConfirmation ? "up" : Number.isFinite(etfAvg) && etfAvg < 0 && Number.isFinite(minerAvg) && minerAvg < 0 ? "down" : "flat",
      value: `ETF ${formatAssetFinancePct(etfAvg)} / 礦商 ${formatAssetFinancePct(minerAvg)}`,
      detail: fundConfirmation
        ? `${bestEtf ? `${bestEtf.symbol} ${bestEtf.pct || "--"}` : "ETF"} 與 ${bestMiner ? `${bestMiner.symbol} ${bestMiner.pct || "--"}` : "礦商"} 同向，趨勢確認度提高。`
        : minerLeadership
          ? `礦商強於 ETF ${formatAssetFinancePct(minerSpread)}，可觀察是否帶動 ETF 補強。`
          : "ETF 與礦商尚未同步，價格訊號暫不視為完整趨勢。",
    },
    {
      title: "總體牽制",
      tone: macroPressure ? "down" : Number.isFinite(dxyPct) && dxyPct < 0 ? "up" : "flat",
      value: `DXY ${model.dxy?.pct || "--"} / 10Y ${formatAssetHubYield(tenYearValue)}`,
      detail: pressureProfile
        ? pressureProfile.focus
        : macroPressure
        ? "美元或殖利率壓力仍在，金屬上漲需靠 ETF 流入或避險需求抵消。"
        : "總體壓力未明顯升高，價格訊號可優先看資金與金銀比確認。",
    },
    {
      title: "台灣驗證",
      tone: Number.isFinite(taiwanSpread) ? assetFinancePctTone(taiwanSpread) : "flat",
      value: `${formatAssetFinancePct(taiwanAvg)} 平均`,
      detail: Number.isFinite(taiwanSpread)
        ? `台灣商品相對國際金屬 ${formatAssetFinancePct(taiwanSpread)}，需留意匯率、折溢價與交易時段差。`
        : "台灣貴金屬資料同步中，先以國際期貨與 ETF 作主要判讀。",
    },
  ];
  const entryBias = score >= 70
    ? "可保留偏多核心"
    : score >= 48
      ? "維持中性觀察"
      : "縮小風險曝險";
  const addCondition = fundConfirmation && (silverLeadership || broadMetalStrength) && !macroPressure
    ? "白銀、ETF、礦商已形成加碼條件"
    : pressureProfile
      ? pressureProfile.unlock
      : "等待白銀、ETF、礦商至少兩項補強";
  const riskCondition = pressureProfile
    ? pressureProfile.label
    : macroPressure
    ? "美元利率壓力偏高"
    : hedgeDemand
      ? "避險波動偏高"
      : "目前風險中性";
  const pressureSource = dxyPressure && ratePressure
    ? "美元與 10Y 同時偏強"
    : dxyPressure
      ? "美元走強"
      : ratePressure
        ? "10Y 殖利率偏高"
        : fundDrag
          ? "ETF 與礦商資金未跟上"
          : "";
  const aiConclusion = (() => {
    if (pressureProfile) {
      return `AI 結論：目前屬於「${pressureProfile.label}」，主因是${pressureSource}；解除觀望需看到 ${pressureProfile.unlock}`;
    }
    if (label === "多頭擴散") {
      return `AI 結論：價格擴散與資金確認同時成立，${positiveMetals}/${expectedMetalCount} 項金屬走強，白銀相對黃金 ${formatAssetFinancePct(silverLead)}，可視為偏多延伸行情。`;
    }
    if (label === "避險偏多") {
      return `AI 結論：避險需求支撐黃金核心，風險分數 ${model.riskScore}/100；若美元與 10Y 未再上壓，可維持防禦型偏多。`;
    }
    if (label === "高波動防守") {
      return `AI 結論：避險訊號偏強但波動同步升高，黃金優先於白銀與礦商，策略重點是控槓桿與等回檔確認。`;
    }
    if (label === "區間輪動") {
      return `AI 結論：多空訊號尚未共振，價格、資金與總體條件互相拉扯，暫以區間輪動與等待確認為主。`;
    }
    return `AI 結論：價格與資金面偏弱，尚未形成有效修復訊號，應降低追價並等待金銀比或礦商先止穩。`;
  })();
  const decisionPaths = [
    {
      title: "目前動作",
      tone: score >= 70 ? "up" : score < 48 ? "down" : "flat",
      value: entryBias,
      detail: action,
    },
    {
      title: "加碼條件",
      tone: fundConfirmation && (silverLeadership || broadMetalStrength) ? "up" : "flat",
      value: fundConfirmation && (silverLeadership || broadMetalStrength) ? "可分批提高" : "等待資金補強",
      detail: fundConfirmation
        ? `${addCondition}；下一步看白銀與鉑鈀是否延續，避免只押單一黃金訊號。`
        : `${addCondition}；資金未同步前，偏多預測只作觀察，不直接放大槓桿。`,
    },
    {
      title: "降級條件",
      tone: macroPressure || model.riskScore >= 78 ? "down" : "flat",
      value: riskCondition,
      detail: pressureProfile
        ? pressureProfile.risk
        : macroPressure
        ? "若 DXY 或 10Y 持續走強，同時 ETF / 礦商未補量，偏多判讀降為區間。"
        : "若 VIX 升、美元升、礦商弱，降低追價權重並回到黃金核心。",
    },
  ];
  const checklist = [
    ["成立條件", `${score}/100`, `${label}：${entryBias}`],
    ["加碼訊號", fundConfirmation ? "已確認" : "等待", addCondition],
    ["壓力來源", pressureProfile ? pressureProfile.label : macroPressure ? "總體壓力" : "未啟動", pressureProfile ? pressureProfile.focus : macroPressure ? "美元利率續強且資金未流入。" : "若資金背離或金銀比轉弱再降級。"],
    ["下一步驗證", `信心 ${model.confidence}`, Number.isFinite(taiwanSpread) ? "對照台灣商品與國際金屬是否隔日同向。" : "等待台灣商品同步後再做在地確認。"],
  ];
  const venueInsight = buildAssetFinanceGlobalVenueInsight(model);
  return `
    <article class="panel-card asset-finance-module-card asset-finance-decision-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI Decision Center</p>
          <h4>全球貴金屬 AI 決策中心</h4>
        </div>
        <span>${score} / 100 · ${escapeHtml(label)}</span>
      </div>
      <div class="asset-finance-decision-brief">
        <strong>${escapeHtml(label)}</strong>
        <p>${escapeHtml(aiConclusion)} 模型信心 ${model.confidence}；${escapeHtml(action)}</p>
      </div>
      <div class="asset-finance-decision-venue">
        <div class="asset-finance-decision-section-head">
          <div>
            <p class="panel-kicker">Global venues</p>
            <h5>全球交易市場 AI 場域判讀</h5>
          </div>
          <span>現貨 / 期貨 / 實需</span>
        </div>
        <p class="asset-finance-market-brief">${escapeHtml(venueInsight.venueConclusion)}</p>
        <div class="asset-finance-market-list">
          ${venueInsight.markets.map(([name, role, text]) => `<span><b>${escapeHtml(name)}</b><em>${escapeHtml(role)}</em><small>${escapeHtml(text)}</small></span>`).join("")}
        </div>
      </div>
      <div class="asset-finance-decision-grid">
        ${evidenceCards.map((item) => `
          <section class="is-${escapeHtml(item.tone)}">
            <small>${escapeHtml(item.title)}</small>
            <strong>${escapeHtml(item.value)}</strong>
            <p>${escapeHtml(item.detail)}</p>
          </section>
        `).join("")}
      </div>
      <div class="asset-finance-decision-section-head is-compact">
        <div>
          <p class="panel-kicker">Action path</p>
          <h5>AI 行動路徑</h5>
        </div>
        <span>動作 / 加碼 / 降級</span>
      </div>
      <div class="asset-finance-decision-paths">
        ${decisionPaths.map((item) => `
          <section class="is-${escapeHtml(item.tone)}">
            <small>${escapeHtml(item.title)}</small>
            <strong>${escapeHtml(item.value)}</strong>
            <p>${escapeHtml(item.detail)}</p>
          </section>
        `).join("")}
      </div>
      <div class="asset-finance-decision-section-head is-compact">
        <div>
          <p class="panel-kicker">Decision checks</p>
          <h5>檢核門檻</h5>
        </div>
        <span>分數 / 資金 / 壓力 / 驗證</span>
      </div>
      <div class="asset-finance-decision-checklist">
        ${checklist.map(([name, value, detail]) => `
          <span>
            <b>${escapeHtml(name)}</b>
            <strong>${escapeHtml(value)}</strong>
            <small>${escapeHtml(detail)}</small>
          </span>
        `).join("")}
      </div>
      <p class="stock-theory-note">研究訊號以線上行情、台灣備援資料、ETF / 礦商相對強弱與總體因子計算，作為市場判讀參考。</p>
    </article>
  `;
}
function renderAssetFinanceSelectableMetalOnlineRows(items = [], activeSymbol = "") {
  const active = String(activeSymbol || "").toUpperCase();
  return items.map((item) => {
    const symbol = String(item?.symbol || "").toUpperCase();
    const metric = getAssetHubMetric(item);
    return `
      <tr class="${symbol === active ? "is-active" : ""}" data-asset-finance-volume-row="${escapeHtml(symbol)}">
        <td><button class="asset-finance-etf-select" type="button" data-asset-finance-volume-symbol="${escapeHtml(symbol)}">${escapeHtml(item.name || "--")}</button></td>
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
function renderAssetFinanceSelectableBondOnlineRows(items = [], activeSymbol = "") {
  const active = String(activeSymbol || "").toUpperCase();
  return items.map((item) => {
    const symbol = String(item?.symbol || "").toUpperCase();
    const metric = getAssetHubMetric(item);
    return `
      <tr class="${symbol === active ? "is-active" : ""}" data-asset-finance-volume-row="${escapeHtml(symbol)}">
        <td><button class="asset-finance-etf-select" type="button" data-asset-finance-volume-symbol="${escapeHtml(symbol)}">${escapeHtml(item.name || "--")}</button></td>
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
function buildAssetFinanceMetalsEtfConclusion(items = [], { avgPct = null, best = null, weakest = null } = {}) {
  const usable = items.filter((item) => Number.isFinite(parseMarketNumber(item?.pct)));
  const physicalEtfs = usable.filter((item) => {
    const type = String(item.type || "");
    return type.includes("ETF") && !type.includes("礦業") && getAssetHubRegion(item) !== "台灣";
  });
  const miningEtfs = usable.filter((item) => String(item.type || "").includes("礦業"));
  const taiwanEtfs = usable.filter((item) => getAssetHubRegion(item) === "台灣");
  const physicalAvg = averageAssetFinancePct(physicalEtfs);
  const miningAvg = averageAssetFinancePct(miningEtfs);
  const taiwanAvg = averageAssetFinancePct(taiwanEtfs);
  const miningSpread = Number.isFinite(miningAvg) && Number.isFinite(physicalAvg) ? miningAvg - physicalAvg : null;
  const taiwanSpread = Number.isFinite(taiwanAvg) && Number.isFinite(physicalAvg) ? taiwanAvg - physicalAvg : null;
  const tone = Number.isFinite(avgPct) && avgPct > 0.45
    ? "up"
    : Number.isFinite(avgPct) && avgPct < -0.45
      ? "down"
      : "flat";
  let thesis = "ETF 線上行情仍在補齊，先用已同步標的觀察資金是否集中於黃金、白銀或礦業槓桿。";
  if (Number.isFinite(miningSpread) && miningSpread > 0.8 && Number.isFinite(miningAvg) && miningAvg > 0) {
    thesis = "礦業 ETF 明顯強於實物 ETF，資金正在追逐金屬上漲的營運槓桿，行情偏進攻，但波動也會放大。";
  } else if (Number.isFinite(miningSpread) && miningSpread < -0.8 && Number.isFinite(physicalAvg) && physicalAvg > 0) {
    thesis = "實物 ETF 強於礦業 ETF，買盤偏向金屬本身與避險需求，趨勢確認度需等礦業 ETF 跟上。";
  } else if (Number.isFinite(physicalAvg) && Number.isFinite(miningAvg) && physicalAvg > 0 && miningAvg > 0) {
    thesis = "實物 ETF 與礦業 ETF 同步轉強，價格端與股權端有共振，偏多延續性較佳。";
  } else if (Number.isFinite(physicalAvg) && Number.isFinite(miningAvg) && physicalAvg < 0 && miningAvg < 0) {
    thesis = "實物 ETF 與礦業 ETF 同步偏弱，貴金屬資金面缺乏承接，先以防守與等待確認為主。";
  } else if (Number.isFinite(physicalAvg) && Number.isFinite(miningAvg)) {
    thesis = "實物 ETF 與礦業 ETF 走勢分歧，市場仍在避險金屬與景氣槓桿之間拉扯，需等待強弱收斂。";
  } else if (Number.isFinite(avgPct) && avgPct > 0) {
    thesis = "已同步 ETF 平均仍為正報酬，短線資金偏向承接貴金屬題材，但仍需觀察礦業 ETF 是否補強。";
  } else if (Number.isFinite(avgPct) && avgPct < 0) {
    thesis = "已同步 ETF 平均偏弱，短線資金沒有明顯回流，追價前需等待實物 ETF 或礦業 ETF 重新轉強。";
  }
  const relative = Number.isFinite(taiwanSpread)
    ? `台灣商品平均 ${formatAssetFinancePct(taiwanAvg)}，相對國際實物 ETF ${taiwanSpread >= 0 ? "高" : "低"} ${Math.abs(taiwanSpread).toFixed(2)} 個百分點，需留意交易時差與匯率影響。`
    : "台灣商品與國際 ETF 的同步差仍在補資料，暫以國際 ETF 與礦業 ETF 強弱為主。";
  const leader = best
    ? `相對強勢為 ${best.symbol || "--"} ${best.pct || "--"}`
    : "相對強勢標的同步中";
  const laggard = weakest
    ? `相對弱勢為 ${weakest.symbol || "--"} ${weakest.pct || "--"}`
    : "相對弱勢標的同步中";
  return {
    tone,
    text: `${thesis} ${leader}，${laggard}。${relative}`,
  };
}
function renderAssetFinanceVolumeTrendChart(item, label = "走勢與成交量") {
  const rows = normalizeGlobalOhlcvSeries(item?.series || []).slice(-24);
  if (rows.length < 2) {
    return `
      <div class="asset-finance-volume-chart">
        <div class="asset-finance-volume-chart-head">
          <span><small>Trend / volume</small><b>${escapeHtml(label)}</b></span>
          <em>資料同步中</em>
        </div>
        <p class="stock-detail-empty">走勢與成交量資料不足，暫無法繪製柱狀圖。</p>
      </div>
    `;
  }
  const width = 920;
  const height = 300;
  const pad = { top: 24, right: 24, bottom: 36, left: 52 };
  const priceHeight = 166;
  const volumeTop = pad.top + priceHeight + 22;
  const volumeHeight = height - volumeTop - pad.bottom;
  const plotWidth = width - pad.left - pad.right;
  const closes = rows.map((row) => row.close).filter(Number.isFinite);
  const volumes = rows.map((row) => row.volume || 0);
  const minClose = Math.min(...closes);
  const maxClose = Math.max(...closes);
  const closeSpan = maxClose - minClose || 1;
  const maxVolume = Math.max(...volumes, 1);
  const xFor = (index) => pad.left + (index / Math.max(rows.length - 1, 1)) * plotWidth;
  const yForClose = (value) => pad.top + ((maxClose - value) / closeSpan) * priceHeight;
  const barWidth = Math.max(6, plotWidth / rows.length * 0.58);
  const points = rows.map((row, index) => ({
    x: xFor(index),
    y: yForClose(row.close),
    value: row.close,
    close: row.close,
    volume: row.volume || 0,
    pct: index > 0 && rows[index - 1]?.close ? ((row.close / rows[index - 1].close) - 1) * 100 : null,
    date: row.date,
  }));
  const path = buildPath(points);
  const first = rows[0];
  const last = rows.at(-1);
  const changePct = first?.close ? ((last.close / first.close) - 1) * 100 : null;
  const avgVolume = averageAssetFinanceValues(volumes.filter((value) => value > 0));
  return `
    <div class="asset-finance-volume-chart">
      <div class="asset-finance-volume-chart-head">
        <span><small>Trend / volume</small><b>${escapeHtml(label)}</b></span>
        <em>${escapeHtml(item?.symbol || "--")} · ${formatAssetFinancePct(changePct)} · 均量 ${formatGlobalVolume(avgVolume)}</em>
      </div>
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(label)}走勢與成交量柱狀圖">
        <rect class="asset-finance-volume-bg" x="${pad.left}" y="${pad.top}" width="${plotWidth}" height="${priceHeight}"></rect>
        <line class="asset-finance-volume-grid" x1="${pad.left}" y1="${yForClose(maxClose).toFixed(2)}" x2="${width - pad.right}" y2="${yForClose(maxClose).toFixed(2)}"></line>
        <line class="asset-finance-volume-grid" x1="${pad.left}" y1="${yForClose(minClose).toFixed(2)}" x2="${width - pad.right}" y2="${yForClose(minClose).toFixed(2)}"></line>
        <text class="asset-finance-volume-axis" x="${pad.left - 10}" y="${(yForClose(maxClose) + 4).toFixed(2)}" text-anchor="end">${formatGlobalValue(maxClose)}</text>
        <text class="asset-finance-volume-axis" x="${pad.left - 10}" y="${(yForClose(minClose) + 4).toFixed(2)}" text-anchor="end">${formatGlobalValue(minClose)}</text>
        <path class="asset-finance-volume-area" d="${path} L ${points.at(-1).x.toFixed(2)} ${(pad.top + priceHeight).toFixed(2)} L ${points[0].x.toFixed(2)} ${(pad.top + priceHeight).toFixed(2)} Z"></path>
        <path class="asset-finance-volume-line" d="${path}"></path>
        ${rows.map((row, index) => {
          const barHeight = ((row.volume || 0) / maxVolume) * volumeHeight;
          const x = xFor(index) - barWidth / 2;
          const y = volumeTop + volumeHeight - barHeight;
          const isUp = index === 0 || row.close >= rows[index - 1].close;
          return `<rect class="asset-finance-volume-bar ${isUp ? "is-up" : "is-down"}" x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${Math.max(1, barHeight).toFixed(2)}"></rect>`;
        }).join("")}
        <line class="asset-finance-volume-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${(volumeTop + volumeHeight).toFixed(2)}" data-asset-finance-volume-crosshair-x></line>
        <line class="asset-finance-volume-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${width - pad.right}" y2="${pad.top}" data-asset-finance-volume-crosshair-y></line>
        <circle class="asset-finance-volume-crosshair-dot" cx="${pad.left}" cy="${pad.top}" r="4.5" data-asset-finance-volume-crosshair-dot></circle>
        ${points.map((point, index) => {
          const previousX = index > 0 ? points[index - 1].x : pad.left;
          const nextX = index < points.length - 1 ? points[index + 1].x : width - pad.right;
          const zoneWidth = Math.max(8, (nextX - previousX) / 2);
          return `<rect class="asset-finance-volume-hover-zone" x="${(point.x - zoneWidth / 2).toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${(volumeTop + volumeHeight - pad.top).toFixed(2)}" data-x="${point.x.toFixed(2)}" data-y="${point.y.toFixed(2)}" data-date="${escapeHtml(point.date)}" data-close="${escapeHtml(formatGlobalValue(point.close))}" data-pct="${escapeHtml(formatAssetFinancePct(point.pct))}" data-volume="${escapeHtml(formatGlobalVolume(point.volume))}"></rect>`;
        }).join("")}
        <text class="asset-finance-volume-date" x="${pad.left}" y="${height - 12}" text-anchor="start">${escapeHtml(first.date)}</text>
        <text class="asset-finance-volume-date" x="${width - pad.right}" y="${height - 12}" text-anchor="end">${escapeHtml(last.date)}</text>
      </svg>
      <div class="asset-finance-volume-tooltip" hidden></div>
    </div>
  `;
}
function getAssetFinanceVolumePayloadItem(item = {}) {
  return {
    symbol: item.symbol || "",
    name: item.name || item.symbol || "",
    type: item.type || item.group || "",
    group: item.group || "",
    region: getAssetHubRegion(item),
    exchange: item.exchange || item.dataSource || "",
    dataSource: item.dataSource || "",
    close: item.close,
    open: item.open,
    high: item.high,
    low: item.low,
    pct: item.pct,
    volume: item.volume,
    volumeValue: item.volumeValue,
    periodReturn: item.periodReturn,
    date: item.date,
    series: Array.isArray(item.series) ? item.series : [],
  };
}
function renderAssetFinanceSingleTrendRiskAnalysis(item = {}) {
  const rows = normalizeGlobalOhlcvSeries(item?.series || []).slice(-24);
  const latest = rows.at(-1);
  const previous = rows.at(-2);
  const close = latest?.close ?? parseMarketNumber(item?.close);
  const dayPct = latest && previous?.close ? ((latest.close / previous.close) - 1) * 100 : parseMarketNumber(item?.pct);
  const valueAt = (days) => rows.length > days ? rows[rows.length - 1 - days]?.close : null;
  const momentum5 = Number.isFinite(close) && Number.isFinite(valueAt(5)) && valueAt(5) > 0 ? ((close / valueAt(5)) - 1) * 100 : null;
  const momentum20 = Number.isFinite(close) && Number.isFinite(valueAt(20)) && valueAt(20) > 0 ? ((close / valueAt(20)) - 1) * 100 : null;
  const returns = [];
  for (let index = 1; index < rows.length; index += 1) {
    const prev = rows[index - 1]?.close;
    const current = rows[index]?.close;
    if (Number.isFinite(prev) && prev > 0 && Number.isFinite(current)) returns.push(((current / prev) - 1) * 100);
  }
  const volatility = standardDeviationAssetFinanceValues(returns);
  const highClose = Math.max(...rows.map((row) => row.close).filter(Number.isFinite), close || 0);
  const drawdown = Number.isFinite(close) && highClose > 0 ? ((close / highClose) - 1) * 100 : null;
  const volumes = rows.map((row) => row.volume || 0).filter((value) => value > 0);
  const avgVolume = averageAssetFinanceValues(volumes.slice(-10));
  const latestVolume = latest?.volume || parseMarketNumber(item?.volumeValue ?? item?.volume);
  const volumeRatio = Number.isFinite(latestVolume) && Number.isFinite(avgVolume) && avgVolume > 0 ? latestVolume / avgVolume : null;
  const trendTone = Number.isFinite(momentum20) && momentum20 > 6 && Number.isFinite(momentum5) && momentum5 > 0
    ? "up"
    : Number.isFinite(momentum20) && momentum20 < -6
      ? "down"
      : "flat";
  const riskScore = clampAssetHubScore(
    42
      + (Number.isFinite(volatility) ? volatility * 9 : 8)
      + (Number.isFinite(drawdown) ? Math.abs(Math.min(drawdown, 0)) * 1.4 : 0)
      + (Number.isFinite(volumeRatio) && volumeRatio > 1.8 ? 8 : 0),
    20,
    92,
  );
  const riskTone = riskScore >= 68 ? "down" : riskScore >= 48 ? "flat" : "up";
  const trendText = trendTone === "up"
    ? "近 20 日趨勢偏多，短線動能仍有延續條件。"
    : trendTone === "down"
      ? "近 20 日趨勢偏弱，反彈需要先觀察量價是否止穩。"
      : "近 20 日偏區間整理，方向仍需等待突破或跌破確認。";
  const riskText = riskTone === "down"
    ? "波動或回撤偏高，追價風險較大，需用成交量與支撐位控管。"
    : riskTone === "up"
      ? "波動與回撤相對溫和，風險結構較穩，但仍需避免單日量縮追高。"
      : "風險屬中性，適合用分批與停損距離管理波動。";
  const volumeText = Number.isFinite(volumeRatio)
    ? volumeRatio >= 1.35
      ? `最新成交量為 10 日均量 ${volumeRatio.toFixed(2)} 倍，量能有放大跡象。`
      : volumeRatio <= 0.75
        ? `最新成交量僅 10 日均量 ${volumeRatio.toFixed(2)} 倍，動能確認度偏低。`
        : `最新成交量約為 10 日均量 ${volumeRatio.toFixed(2)} 倍，量能大致正常。`
    : "成交量均值仍在同步中，量能判讀暫以圖表柱狀變化為主。";
  return `
    <div class="asset-finance-single-ai is-${riskTone}" data-asset-finance-single-analysis>
      <div class="asset-finance-single-ai-head">
        <span><small>Single asset AI</small><b>${escapeHtml(item?.name || item?.symbol || "--")}</b></span>
        <em>${escapeHtml(item?.symbol || "--")} · ${escapeHtml(item?.type || "")}</em>
      </div>
      <div class="asset-finance-single-ai-grid">
        <span><small>趨勢</small><b class="${trendTone}">${formatAssetFinancePct(momentum20)}</b><em>${escapeHtml(trendText)}</em></span>
        <span><small>風險</small><b class="${riskTone}">${Math.round(riskScore)}/100</b><em>${escapeHtml(riskText)}</em></span>
        <span><small>波動</small><b>${formatAssetFinancePct(volatility)}</b><em>近 24 日日報酬標準差</em></span>
        <span><small>成交量</small><b>${formatGlobalVolume(latestVolume)}</b><em>${escapeHtml(volumeText)}</em></span>
      </div>
      <p>${escapeHtml(`AI 分析：${trendText} ${riskText} ${volumeText} 目前收盤 ${formatGlobalValue(close)}，日漲跌 ${formatAssetFinancePct(dayPct)}，近高點回撤 ${formatAssetFinancePct(drawdown)}。`)}</p>
    </div>
  `;
}
function getAssetFinanceBondProfile(item = {}) {
  const symbol = String(item?.symbol || "").toUpperCase();
  const text = `${item?.name || ""} ${item?.type || ""} ${item?.group || ""} ${item?.exchange || ""}`.toLowerCase();
  let duration = {
    label: "綜合久期",
    score: 52,
    note: "同時承受短端與長端利率變化，適合作為核心債券配置觀察。",
  };
  if (["BIL", "SGOV", "SHY", "VGSH", "USFR"].includes(symbol) || /short|ultra.?short|floating|t-bill|貨幣|短天期/.test(text)) {
    duration = {
      label: "短天期 / 浮動利率",
      score: 24,
      note: "價格對利率變動較不敏感，主要風險在再投資利率與收益下修。",
    };
  } else if (["IEF", "VGIT"].includes(symbol) || /intermediate|中天期|7-10/.test(text)) {
    duration = {
      label: "中天期核心債",
      score: 48,
      note: "兼具收益與價格彈性，適合觀察 5Y 至 10Y 殖利率變化。",
    };
  } else if (["TLT", "VGLT"].includes(symbol) || /long|20\+|20 year|長天期/.test(text)) {
    duration = {
      label: "長天期高久期",
      score: 82,
      note: "對降息預期最敏感，但殖利率上行時回撤也會明顯放大。",
    };
  } else if (["BND", "AGG", "BNDX"].includes(symbol) || /aggregate|total bond|總債|綜合/.test(text)) {
    duration = {
      label: "綜合核心債",
      score: 55,
      note: "分散不同天期與債種，適合用來看整體債市風向。",
    };
  }

  let credit = {
    label: "投資級債券",
    score: 34,
    note: "信用風險相對可控，主要觀察利率與信用利差變化。",
  };
  if (["HYG", "JNK"].includes(symbol) || /high yield|junk|高收益|非投資/.test(text)) {
    credit = {
      label: "高收益 / 非投資級",
      score: 74,
      note: "殖利率補償較高，但景氣放緩時需優先監控信用利差與違約風險。",
    };
  } else if (["LQD"].includes(symbol) || /corporate|公司債|投資級/.test(text)) {
    credit = {
      label: "投資級公司債",
      score: 46,
      note: "同時受利率與企業信用利差影響，需看評等與產業循環。",
    };
  } else if (["TIP"].includes(symbol) || /tips|inflation|抗通膨|通膨/.test(text)) {
    credit = {
      label: "抗通膨公債",
      score: 30,
      note: "信用風險偏低，重點在實質利率與通膨預期變化。",
    };
  } else if (/treasury|government|公債|美債|國債/.test(text) || ["SHY", "VGSH", "IEF", "VGIT", "TLT", "VGLT", "BIL", "SGOV", "USFR"].includes(symbol)) {
    credit = {
      label: "政府公債",
      score: 22,
      note: "信用風險低，價格主要由殖利率曲線與久期控制。",
    };
  } else if (/taiwan|twse|tpex|\.tw|\.two|台灣/.test(`${symbol} ${text}`)) {
    credit = {
      label: "台灣掛牌債券 ETF",
      score: 38,
      note: "需同時留意海外債券價格、匯率、折溢價與台灣交易時段落差。",
    };
  }
  return { duration, credit };
}
function getAssetFinanceBondEtfLens(item = {}) {
  const symbol = String(item?.symbol || "").toUpperCase();
  const text = `${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.region || ""} ${item?.market || ""} ${item?.exchange || ""}`.toLowerCase();
  const has = (pattern) => pattern.test(`${symbol} ${text}`);
  const isTaiwanListed = /\.TW$|\.TWO$/i.test(symbol) || /台灣|臺灣|tpex|twse/.test(text);
  let strategyBucket = "綜合債券";
  let role = "核心債券觀察";
  let centerUse = "放入債券 ETF 分析中心，和短債、核心債、長債、信用債比較廣度與強弱。";
  let taiwanUse = "台灣研究：若以台幣帳戶交易，需同步看折溢價、匯率與台灣交易時差。";
  let globalUse = "國際研究：用美債曲線、美元、VIX 與信用利差確認債券風險是否可承擔。";
  let keyRisk = "主要風險來自殖利率反向、流動性與信用利差變化。";

  if (has(/SHY|VGSH|BIL|SGOV|USFR|TFLO|short|短天|短債|貨幣|浮動|0-1|1-3/i)) {
    strategyBucket = "短天期 / 貨幣市場";
    role = "現金替代與短端防守";
    centerUse = "用來確認資金是否偏向避險與等待利率訊號，適合和 2Y 殖利率、Fed Funds 對照。";
    globalUse = "國際研究：短端收益受政策利率與再投資收益支配，降息循環開始後殖利率可能逐步下修。";
    keyRisk = "降息後收益率下滑，價格彈性有限，過度集中會降低修復彈性。";
  } else if (has(/IEF|VGIT|BND|AGG|中天|核心|綜合|aggregate|3-7|5-10/i)) {
    strategyBucket = "中天期 / 核心綜合債";
    role = "核心配置與利率中樞觀察";
    centerUse = "作為 ETF 中心的核心債基準，拿來比較短債防守與長債修復誰佔優勢。";
    globalUse = "國際研究：對 5Y/10Y 殖利率敏感，需確認曲線倒掛是否收斂且通膨未再升溫。";
    keyRisk = "若中長端利率重新上行，淨值會受壓，但波動通常低於長天期公債。";
  } else if (has(/TLT|VGLT|EDV|GOVZ|20|30|長天|長債|long|10-20|15\+/i)) {
    strategyBucket = "長天期公債";
    role = "降息交易與高久期修復";
    centerUse = "放在 ETF 中心的高久期桶，和 10Y/30Y 殖利率及曲線斜率同步追蹤。";
    globalUse = "國際研究：長端價格高度受實質利率、期限溢酬與通膨預期影響。";
    keyRisk = "長端殖利率反彈時回撤會放大，不適合只因配息率高而追價。";
  } else if (has(/LQD|HYG|JNK|VCSH|VCIT|IGIB|SJNK|ANGL|corporate|公司|信用|high yield|高收益|非投資/i)) {
    strategyBucket = "信用債 / 高收益";
    role = "收益增強與信用風險交易";
    centerUse = "在 ETF 中心需和 LQD/HYG/JNK 同類比較，觀察利差補償是否足以承擔信用風險。";
    globalUse = "國際研究：信用債要和景氣、失業率、VIX 與高收益利差一起判讀。";
    keyRisk = "景氣轉弱或利差擴大時，可能和股票同步下跌。";
  } else if (has(/TIP|SCHP|VTIP|MUB|VTEB|MBB|VMBS|tips|inflation|抗通膨|通膨|市政|mbs/i)) {
    strategyBucket = "抗通膨 / 市政 / MBS";
    role = "特殊債種與利差觀察";
    centerUse = "用來補足 TIPS、MBS、市政債等非一般公債風險，避免只用殖利率曲線判斷。";
    globalUse = "國際研究：需拆開看實質利率、通膨預期、提前還款與流動性。";
    keyRisk = "利差、提前還款或通膨預期變化，可能讓價格表現不同於一般公債。";
  } else if (has(/BNDX|IAGG|EMB|international|emerging|global|全球|國際|新興|美元債|歐債|日債/i)) {
    strategyBucket = "全球 / 新興市場";
    role = "非美利率與美元信用風險";
    centerUse = "用來和美債核心桶比較，確認資金是否願意承擔匯率、主權與新興市場信用風險。";
    globalUse = "國際研究：同步看美元指數、ECB/BOJ 政策與新興市場利差。";
    keyRisk = "美元走強、主權利差擴大或新興市場資金流出時，價格容易受壓。";
  }

  if (isTaiwanListed) {
    return {
      bucket: "台灣債券 ETF",
      strategyBucket,
      role: `${role}，台灣掛牌追蹤`,
      centerUse: `先列入台灣債券 ETF，再和「${strategyBucket}」同類海外 ETF 比較折溢價、流動性與追蹤差。`,
      taiwanUse: "台灣研究：重點看台幣交易時段、匯率避險成本、折溢價與 ETF 規模是否支撐進出場。",
      globalUse,
      keyRisk: `${keyRisk} 台灣掛牌商品還需額外監控匯率、折溢價與海外市場開盤落差。`,
    };
  }

  return {
    bucket: strategyBucket,
    strategyBucket,
    role,
    centerUse,
    taiwanUse,
    globalUse,
    keyRisk,
  };
}
function renderAssetFinanceBondSingleAnalysis(item = {}) {
  if (!item || !item.symbol) {
    return `<p class="stock-detail-empty">請點選債券商品名稱，查看單一商品 AI 結論。</p>`;
  }
  const rows = normalizeGlobalOhlcvSeries(item?.series || []).slice(-24);
  const latest = rows.at(-1);
  const previous = rows.at(-2);
  const close = latest?.close ?? parseMarketNumber(item?.close);
  const dayPct = latest && previous?.close ? ((latest.close / previous.close) - 1) * 100 : parseMarketNumber(item?.pct);
  const valueAt = (days) => rows.length > days ? rows[rows.length - 1 - days]?.close : null;
  const momentum20 = Number.isFinite(close) && Number.isFinite(valueAt(20)) && valueAt(20) > 0 ? ((close / valueAt(20)) - 1) * 100 : null;
  const returns = [];
  for (let index = 1; index < rows.length; index += 1) {
    const prev = rows[index - 1]?.close;
    const current = rows[index]?.close;
    if (Number.isFinite(prev) && prev > 0 && Number.isFinite(current)) returns.push(((current / prev) - 1) * 100);
  }
  const volatility = standardDeviationAssetFinanceValues(returns);
  const highClose = Math.max(...rows.map((row) => row.close).filter(Number.isFinite), close || 0);
  const drawdown = Number.isFinite(close) && highClose > 0 ? ((close / highClose) - 1) * 100 : null;
  const latestVolume = latest?.volume || parseMarketNumber(item?.volumeValue ?? item?.volume);
  const profile = getAssetFinanceBondProfile(item);
  const etfLens = getAssetFinanceBondEtfLens(item);
  const trendTone = Number.isFinite(momentum20) && momentum20 > 1.2
    ? "up"
    : Number.isFinite(momentum20) && momentum20 < -1.2
      ? "down"
      : assetFinancePctTone(dayPct);
  const riskScore = clampAssetHubScore(
    24
      + profile.duration.score * 0.38
      + profile.credit.score * 0.34
      + (Number.isFinite(volatility) ? volatility * 7 : 5)
      + (Number.isFinite(drawdown) ? Math.abs(Math.min(drawdown, 0)) * 1.1 : 0),
    18,
    94,
  );
  const riskTone = riskScore >= 68 ? "down" : riskScore >= 48 ? "flat" : "up";
  const trendText = trendTone === "up"
    ? "價格動能偏正，若殖利率續降或信用利差未擴大，仍有延續條件。"
    : trendTone === "down"
      ? "價格動能偏弱，需等待殖利率壓力降溫或量價止穩。"
      : "價格偏整理，短線方向需等殖利率、信用利差或成交量提供確認。";
  const isShortDuration = profile.duration.score <= 30;
  const isLongDuration = profile.duration.score >= 70;
  const isHighYield = profile.credit.score >= 65;
  const isGovernment = profile.credit.label.includes("政府") || profile.credit.label.includes("公債");
  const isTaiwanListed = profile.credit.label.includes("台灣");
  const creditQualityScore = Math.round(clampAssetHubScore(
    100 - profile.credit.score + (isGovernment ? 8 : 0) - (isHighYield ? 6 : 0),
    12,
    98,
  ));
  const creditGrade = creditQualityScore >= 92
    ? "AAA"
    : creditQualityScore >= 84
      ? "AA"
      : creditQualityScore >= 74
        ? "A"
        : creditQualityScore >= 62
          ? "BBB"
          : creditQualityScore >= 48
            ? "BB"
            : creditQualityScore >= 34
              ? "B"
              : "CCC";
  const ratingBand = ["AAA", "AA", "A", "BBB"].includes(creditGrade) ? "投資級" : "非投資級";
  const ratingText = `模型估算 ${creditGrade} / ${creditQualityScore} 分，屬 ${ratingBand} 分層，非官方信評。`;
  const positionText = isShortDuration
    ? "偏現金管理與等待利率訊號，適合降低淨值波動。"
    : isLongDuration
      ? "偏降息交易與高久期防守，價格彈性高但不適合無停損追價。"
      : isHighYield
        ? "偏收益增強與信用風險交易，需和股票風險一起看。"
        : "偏核心債券配置，可用來平衡股票與商品資產波動。";
  const watchText = isLongDuration
    ? "優先看 10Y / 30Y 殖利率是否下行，若長端利率續升，價格容易再受壓。"
    : isShortDuration
      ? "優先看短端政策利率與再投資收益，下行循環開始後收益率可能逐步下降。"
      : isHighYield
        ? "優先看信用利差、景氣數據與高收益債資金流，利差擴大時不宜只看殖利率。"
        : "優先看 5Y / 10Y 殖利率、ETF 折溢價與成交量是否同步改善。";
  const riskWarning = isHighYield
    ? "若景氣轉弱、違約率升高或信用利差擴大，價格可能和股票同步下跌。"
    : isLongDuration
      ? "若通膨或長端殖利率重新上行，高久期部位回撤會比短債更大。"
      : isTaiwanListed
        ? "台灣掛牌商品還要留意匯率、交易時差、折溢價與海外債券開盤落差。"
        : "主要風險來自殖利率反向變動、流動性變差與短線量縮。";
  const useCaseText = isGovernment
    ? "適合作為防守、利率觀察與資產配置穩定器。"
    : isHighYield
      ? "適合小比例收益增強，不宜當成低風險債券核心部位。"
      : isTaiwanListed
        ? "適合用台幣帳戶追蹤海外債券，但需搭配匯率與折溢價觀察。"
        : "適合放在核心收益或信用債觀察清單，搭配公債 ETF 比較。";
  const entrySignal = trendTone === "up"
    ? "可觀察回測不破短線均價且成交量維持，代表買盤承接仍在。"
    : "等待價格站回短線區間、日漲跌轉正且量能不萎縮後再提高信心。";
  const failSignal = riskTone === "down"
    ? "若價格續創低、成交量放大且回撤擴大，代表風險尚未釋放完。"
    : "若價格跌破近 20 日區間低點或殖利率重新上行，原本判讀需降級。";
  const strategyLabel = riskTone === "down"
    ? "保守觀察"
    : trendTone === "up" && ratingBand === "投資級"
      ? "分批追蹤"
      : trendTone === "up"
        ? "收益型觀察"
        : "等待確認";
  const strategyText = riskTone === "down"
    ? `目前風險分數 ${Math.round(riskScore)}/100，先等價格止穩或殖利率壓力降溫，再提高部位信心。`
    : trendTone === "up" && ratingBand === "投資級"
      ? `趨勢偏正且信用分層為 ${ratingBand}，可用回測不破短線區間作為分批觀察條件。`
      : trendTone === "up"
        ? `價格動能改善，但信用分層為 ${ratingBand}，適合小比例收益型觀察，不宜視為低風險核心債。`
        : `趨勢與量能尚未同步確認，先把 ${profile.duration.label} 與 ${profile.credit.label} 的風險分開追蹤。`;
  const allocationRole = isShortDuration
    ? "短端防守 / 現金替代"
    : isLongDuration
      ? "久期修復 / 降息交易"
      : isHighYield
        ? "收益衛星 / 信用風險"
        : isGovernment
          ? "核心防守 / 利率觀察"
          : "核心收益 / 分散配置";
  const thesisText = `${item.symbol || "--"} 的研究主軸是「${profile.duration.label} × ${profile.credit.label} × ${etfLens.bucket}」。不要只看配息率，需把殖利率方向、信用補償、ETF 折溢價與流動性一起判斷。`;
  const marketFocus = isLongDuration
    ? "主看 10Y/30Y 殖利率是否轉弱，若長端利率回落才有較完整的價格修復條件。"
    : isShortDuration
      ? "主看 Fed / 短端政策利率與再投資收益，適合等待利率轉折時維持低波動。"
      : isHighYield
        ? "主看信用利差、VIX、失業率與景氣數據，收益補償不足時不宜擴大部位。"
        : "主看 5Y/10Y 殖利率、ETF 廣度與同類標的強弱，確認核心債是否重新吸引資金。";
  const nextStepText = riskTone === "down"
    ? "下一步先確認價格不再破底、回撤收斂且日漲跌轉正，再把它列回可操作清單。"
    : trendTone === "up"
      ? "下一步觀察回測是否守住短線區間；若同類 ETF 廣度同步改善，信心可上調。"
      : "下一步等待量價、殖利率與信用訊號至少兩項轉正，再從觀察轉為分批追蹤。";
  const setupChecks = isLongDuration
    ? ["10Y/30Y 殖利率不再創高或轉下行", "長天期同類 ETF 不再落後短債"]
    : isShortDuration
      ? ["短端政策利率預期穩定", "再投資收益仍高於核心債波動成本"]
      : isHighYield
        ? ["信用利差未擴大", "VIX 與景氣數據未同步惡化"]
        : ["5Y/10Y 殖利率降溫", "核心債 ETF 廣度與同類強弱改善"];
  if (isTaiwanListed) setupChecks.push("折溢價收斂且台幣匯率波動未放大");
  setupChecks.push(trendTone === "up" ? "回測短線區間不破且成交量維持" : "日漲跌轉正且近 20 日動能止跌");
  const setupConditionText = `${setupChecks.join("；")}。${trendTone === "up" ? "目前已有價格動能，重點是確認利率與同類 ETF 是否跟上。" : "目前仍屬觀察，至少需先看到利率/信用與量價兩條線同時改善。"}`;
  const singleBriefRows = [
    ["研究主軸", thesisText],
    ["配置角色", `${allocationRole}；${useCaseText}`],
    ["現在焦點", marketFocus],
    ["下一步", nextStepText],
  ];
  const detailCards = [
    ["配置定位", `${allocationRole}：${positionText} ETF 中心角色為「${etfLens.role}」。`],
    ["觸發條件", setupConditionText],
    ["執行方式", riskTone === "down" ? "先不追價，等待價格止穩與利率壓力降溫；若要觀察，只適合小部位追蹤。" : `${entrySignal} 達成後再用分批方式提高信心。`],
    ["風險界線", `${riskWarning} ${failSignal}`],
  ];
  const etfLensRows = [
    ["ETF 中心用途", etfLens.centerUse],
    ["台灣市場研究", etfLens.taiwanUse],
    ["國際市場研究", etfLens.globalUse],
    ["分類風險", etfLens.keyRisk],
  ];
  const evidenceRows = [
    ["利率與久期", `${profile.duration.note} ${watchText}`],
    ["信用與評等", `${profile.credit.note} ${ratingText}`],
    ["量價與流動性", `收盤 ${formatGlobalValue(close)}，日漲跌 ${formatAssetFinancePct(dayPct)}，近 20 日 ${formatAssetFinancePct(momentum20)}，波動 ${formatAssetFinancePct(volatility)}，回撤 ${formatAssetFinancePct(drawdown)}，成交量 ${formatGlobalVolume(latestVolume)}。`],
  ];
  const commentaryRows = [
    [
      "總結",
      `${item.symbol || "--"} 目前以「${allocationRole}」評估，ETF 中心歸類為「${etfLens.bucket}」。${trendText}`,
    ],
    [
      "成立條件",
      setupConditionText,
    ],
    [
      "風險界線",
      `${riskWarning} ${failSignal}`,
    ],
    [
      "數據狀態",
      `收盤 ${formatGlobalValue(close)}，日漲跌 ${formatAssetFinancePct(dayPct)}，近 20 日 ${formatAssetFinancePct(momentum20)}，成交量 ${formatGlobalVolume(latestVolume)}。`,
    ],
  ];
  return `
    <div class="asset-finance-single-ai asset-finance-bond-single-ai is-${riskTone}" data-asset-finance-single-analysis>
      <div class="asset-finance-single-ai-head">
        <span><small>Bond single AI research</small><b>${escapeHtml(item?.name || item?.symbol || "--")}</b></span>
        <em>${escapeHtml(item?.symbol || "--")} · ${escapeHtml(getAssetHubRegion(item))}</em>
      </div>
      <div class="asset-finance-bond-single-summary is-${riskTone}">
        <span><small>AI 研究結論</small><b>${escapeHtml(strategyLabel)}</b></span>
        <p>${escapeHtml(strategyText)}</p>
      </div>
      <div class="asset-finance-bond-single-brief">
        ${singleBriefRows.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-single-ai-grid">
        <span><small>久期定位</small><b>${escapeHtml(profile.duration.label)}</b><em>${escapeHtml(profile.duration.note)}</em></span>
        <span><small>信用分類</small><b>${escapeHtml(profile.credit.label)}</b><em>${escapeHtml(profile.credit.note)}</em></span>
        <span><small>信用評級</small><b class="${ratingBand === "投資級" ? "up" : "down"}">${escapeHtml(creditGrade)} · ${creditQualityScore}/100</b><em>${escapeHtml(ratingBand)}；模型估算非官方信評</em></span>
        <span><small>趨勢</small><b class="${trendTone}">${formatAssetFinancePct(momentum20)}</b><em>${escapeHtml(trendText)}</em></span>
        <span><small>風險分數</small><b class="${riskTone}">${Math.round(riskScore)}/100</b><em>波動 ${formatAssetFinancePct(volatility)}，回撤 ${formatAssetFinancePct(drawdown)}</em></span>
        <span><small>ETF 中心分類</small><b>${escapeHtml(etfLens.bucket)}</b><em>${escapeHtml(etfLens.role)}</em></span>
      </div>
      <div class="asset-finance-bond-single-etf-lens">
        ${etfLensRows.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-bond-single-subhead">
        <b>策略執行條件</b>
        <small>把定位、觸發、執行與失效界線拆開，避免只用配息率或單日漲跌判斷。</small>
      </div>
      <div class="asset-finance-bond-single-content-grid">
        ${detailCards.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-bond-single-subhead">
        <b>研究證據基準</b>
        <small>利率、信用與量價三條線同時追蹤，作為 AI 評論升降級依據。</small>
      </div>
      <div class="asset-finance-bond-single-evidence">
        ${evidenceRows.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-bond-single-commentary is-${riskTone}">
        <div class="asset-finance-bond-single-commentary-head">
          <span><small>AI research commentary</small><b>AI 研究評論</b></span>
          <em>${escapeHtml(strategyLabel)} · ${escapeHtml(etfLens.bucket)}</em>
        </div>
        <div class="asset-finance-bond-single-commentary-grid">
          ${commentaryRows.map(([label, text]) => `
            <span>
              <b>${escapeHtml(label)}</b>
              <small>${escapeHtml(text)}</small>
            </span>
          `).join("")}
        </div>
      </div>
    </div>
  `;
}
function initAssetFinanceVolumeSelectors(root = document) {
  root.querySelectorAll("[data-asset-finance-volume-card]").forEach((card) => {
    if (card.dataset.assetFinanceVolumeBound === "1") return;
    card.dataset.assetFinanceVolumeBound = "1";
    let items = [];
    try {
      items = JSON.parse(card.dataset.assetFinanceVolumePayload || "[]");
    } catch (error) {
      console.warn("Failed to parse ETF volume payload:", error);
      items = [];
    }
    const itemMap = new Map(items.map((item) => [String(item.symbol || "").toUpperCase(), item]));
    const view = card.querySelector("[data-asset-finance-volume-view]");
    const analysisView = card.querySelector("[data-asset-finance-single-analysis-view]");
    const analysisMode = card.dataset.assetFinanceAnalysisMode || "default";
    const renderAnalysis = analysisMode === "bond" ? renderAssetFinanceBondSingleAnalysis : renderAssetFinanceSingleTrendRiskAnalysis;
    const setActive = (symbol) => {
      const cleanSymbol = String(symbol || "").toUpperCase();
      const item = itemMap.get(cleanSymbol);
      if (!item) return;
      if (view) {
        view.innerHTML = renderAssetFinanceVolumeTrendChart(item, `${item.name || item.symbol} 近 24 日`);
        bindAssetFinanceVolumeCursor(view);
      }
      if (analysisView) analysisView.innerHTML = renderAnalysis(item);
      card.querySelectorAll("[data-asset-finance-volume-row]").forEach((row) => {
        row.classList.toggle("is-active", row.dataset.assetFinanceVolumeRow === cleanSymbol);
      });
      card.querySelectorAll("[data-asset-finance-volume-symbol]").forEach((button) => {
        button.classList.toggle("is-active", button.dataset.assetFinanceVolumeSymbol === cleanSymbol);
      });
    };
    card.querySelectorAll("[data-asset-finance-volume-symbol]").forEach((button) => {
      button.addEventListener("click", () => setActive(button.dataset.assetFinanceVolumeSymbol));
    });
    bindAssetFinanceVolumeCursor(card);
  });
}
function bindAssetFinanceVolumeCursor(root = document) {
  root.querySelectorAll(".asset-finance-volume-chart").forEach((chart) => {
    if (chart.dataset.assetFinanceVolumeCursorBound === "1") return;
    chart.dataset.assetFinanceVolumeCursorBound = "1";
    const svg = chart.querySelector("svg");
    const tooltip = chart.querySelector(".asset-finance-volume-tooltip");
    if (!svg || !tooltip) return;
    const xLine = svg.querySelector("[data-asset-finance-volume-crosshair-x]");
    const yLine = svg.querySelector("[data-asset-finance-volume-crosshair-y]");
    const dot = svg.querySelector("[data-asset-finance-volume-crosshair-dot]");
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
      tooltip.innerHTML = `
        <strong>${escapeHtml(zone.dataset.date || "--")}</strong>
        <span><b>收盤</b><em>${escapeHtml(zone.dataset.close || "--")}</em></span>
        <span><b>日漲跌</b><em class="${assetFinancePctTone(parseMarketNumber(zone.dataset.pct))}">${escapeHtml(zone.dataset.pct || "--")}</em></span>
        <span><b>成交量</b><em>${escapeHtml(zone.dataset.volume || "--")}</em></span>
      `;
      tooltip.hidden = false;
      const chartRect = chart.getBoundingClientRect();
      const leftBase = event.clientX - chartRect.left + chart.scrollLeft + 14;
      const topBase = event.clientY - chartRect.top + 12;
      const maxLeft = Math.max(12, chart.scrollLeft + chart.clientWidth - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, chart.clientHeight - tooltip.offsetHeight - 12);
      tooltip.style.left = `${Math.min(Math.max(12, leftBase), maxLeft)}px`;
      tooltip.style.top = `${Math.min(Math.max(12, topBase), maxTop)}px`;
    };
    svg.querySelectorAll(".asset-finance-volume-hover-zone").forEach((zone) => {
      zone.addEventListener("mouseenter", (event) => show(event, zone));
      zone.addEventListener("mousemove", (event) => show(event, zone));
      zone.addEventListener("mouseleave", hide);
    });
    chart.addEventListener("mouseleave", hide);
  });
}
function renderAssetFinanceMetalEtfSyncPanel(model) {
  const taiwanRows = (model.taiwanMetalEtfs || []).filter((item) => item && !item.error);
  const etfRows = (model.metalEtfs || []).filter((item) => item && !item.error);
  const sortedRows = [...etfRows]
    .sort((left, right) => Math.abs(parseMarketNumber(right.pct) || 0) - Math.abs(parseMarketNumber(left.pct) || 0));
  const avgPct = averageAssetFinancePct(sortedRows);
  const best = strongestAssetFinanceItem(sortedRows);
  const weakest = sortedRows
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(left.pct) || 999) - (parseMarketNumber(right.pct) || 999))[0] || null;
  const analysis = buildAssetFinanceMetalsEtfConclusion(sortedRows, { avgPct, best, weakest });
  const onlineRows = Array.isArray(model.metalOnlineRows) ? model.metalOnlineRows : [];
  const onlineCatalogCount = Number(model.metalCatalogCount) || onlineRows.length;
  const displayRows = uniqueAssetHubItemsBySymbol(onlineRows.length ? onlineRows : sortedRows)
    .sort((left, right) => Math.abs(parseMarketNumber(right.pct) || 0) - Math.abs(parseMarketNumber(left.pct) || 0));
  const chartItem = [best, ...displayRows].find((item) => normalizeGlobalOhlcvSeries(item?.series || []).length >= 2) || displayRows[0];
  const shownCount = sortedRows.length;
  const activeSymbol = String(chartItem?.symbol || "").toUpperCase();
  const chartPayload = JSON.stringify(displayRows.map(getAssetFinanceVolumePayloadItem));

  const globalRows = [model.gold, model.silver, model.platinum, model.palladium, ...model.globalMetalEtfs.slice(0, 6)]
    .filter((item) => item && !item.error);
  const taiwanAvg = averageAssetFinancePct(taiwanRows);
  const globalAvg = averageAssetFinancePct(globalRows);
  const bestTaiwan = strongestAssetFinanceItem(taiwanRows);
  const bestGlobal = strongestAssetFinanceItem(globalRows);
  const goldSpread = Number.isFinite(parseMarketNumber(model.taiwanGold?.pct)) && Number.isFinite(parseMarketNumber(model.gold?.pct))
    ? parseMarketNumber(model.taiwanGold.pct) - parseMarketNumber(model.gold.pct)
    : null;
  const stats = [
    renderAssetFinanceSyncStat("台灣貴金屬", formatAssetFinancePct(taiwanAvg), bestTaiwan ? `最強 ${bestTaiwan.symbol} ${bestTaiwan.pct || "--"}` : "等待台灣貴金屬", assetFinancePctTone(taiwanAvg)),
    renderAssetFinanceSyncStat("國際金屬標的", formatAssetFinancePct(globalAvg), bestGlobal ? `最強 ${bestGlobal.symbol} ${bestGlobal.pct || "--"}` : "等待國際金屬標的", assetFinancePctTone(globalAvg)),
    renderAssetFinanceSyncStat("黃金同步差", formatAssetFinancePct(goldSpread), "台灣黃金 - 國際黃金期貨", assetFinancePctTone(goldSpread)),
    renderAssetFinanceSyncStat("金銀比", formatAssetHubRatio(model.goldSilverRatio), model.goldSilverRatio >= 85 ? "黃金相對強勢" : "金銀比中性", model.goldSilverRatio >= 85 ? "down" : "flat"),
  ];
  const syncContext = [
    ["用途", "用台灣黃金、白銀商品對照 COMEX 與國際 ETF，觀察隔日跟漲或補跌。"],
    ["注意", "台幣計價、期貨展期、折溢價與交易時段會造成短線落差。"],
  ];
  return `
    <article class="panel-card asset-finance-etf-card asset-finance-compare-card asset-finance-metal-etf-sync-card" data-asset-finance-volume-card data-asset-finance-volume-payload="${escapeHtml(chartPayload)}">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Metals ETF</p>
          <h4>貴金屬 ETF 與礦業 ETF</h4>
        </div>
        <span>線上 ${displayRows.length} / 目錄 ${onlineCatalogCount} 筆 · ETF/礦業 ${shownCount} 檔</span>
      </div>
      <div class="asset-finance-etf-summary">
        <span><small>平均漲跌</small><b class="${assetFinancePctTone(avgPct)}">${formatAssetFinancePct(avgPct)}</b></span>
        <span><small>相對強勢</small><b>${best ? `${escapeHtml(best.symbol)} ${escapeHtml(best.pct || "--")}` : "--"}</b></span>
        <span><small>相對弱勢</small><b>${weakest ? `${escapeHtml(weakest.symbol)} ${escapeHtml(weakest.pct || "--")}` : "--"}</b></span>
      </div>
      <p class="asset-finance-etf-brief is-${escapeHtml(analysis.tone)}"><b>AI 結論</b><span>${escapeHtml(analysis.text)}</span></p>
      <div class="global-table-wrap asset-finance-table-wrap">
        <table class="global-market-table">
          <thead><tr><th>名稱</th><th>代號</th><th>地區</th><th>交易所 / 來源</th><th>分類</th><th>收盤</th><th>漲跌幅</th><th>開盤</th><th>最高</th><th>最低</th><th>量能欄位</th><th>日期</th></tr></thead>
          <tbody>${renderAssetFinanceSelectableMetalOnlineRows(displayRows, activeSymbol) || '<tr><td colspan="12">貴金屬線上資料同步中。</td></tr>'}</tbody>
        </table>
      </div>
      <div data-asset-finance-volume-view>
        ${renderAssetFinanceVolumeTrendChart(chartItem, chartItem ? `${chartItem.name || chartItem.symbol} 近 24 日` : "ETF 近 24 日")}
      </div>
      <div class="asset-finance-merged-subhead">
        <div>
          <p class="panel-kicker">Metals sync</p>
          <h4>貴金屬：台灣與國際同步比較</h4>
        </div>
        <span>${taiwanRows.length} 檔台灣 / ${globalRows.length} 檔國際</span>
      </div>
      <div class="asset-finance-sync-grid">
        ${stats.join("")}
      </div>
      <div class="asset-finance-sync-context">
        ${syncContext.map(([title, text]) => `<span><b>${escapeHtml(title)}</b><small>${escapeHtml(text)}</small></span>`).join("")}
      </div>
      <div data-asset-finance-single-analysis-view>
        ${renderAssetFinanceSingleTrendRiskAnalysis(chartItem)}
      </div>
    </article>
  `;
}
function buildAssetFinanceBondResearchImport(model) {
  const etfRows = (model.bondEtfs || []).filter((item) => item && !item.error);
  const onlineRows = Array.isArray(model.bondOnlineRows) ? model.bondOnlineRows.filter((item) => item && !item.error) : [];
  const bondRows = getAssetFinanceBondRows(model);
  const taiwanRows = bondRows.filter(isAssetFinanceTaiwanBond);
  const taiwanEtfs = taiwanRows.filter((item) => String(item?.type || "").includes("ETF"));
  const internationalRows = bondRows.filter((item) => !isAssetFinanceTaiwanBond(item));
  const internationalEtfs = internationalRows.filter((item) => String(item?.type || "").includes("ETF"));
  const tenYear = model.yields[2] || {};
  const twoYear = model.yields[0] || {};
  const fiveYear = model.yields[1] || {};
  const thirtyYear = model.yields[3] || {};
  const avgPct = averageAssetFinancePct(etfRows);
  const taiwanAvgPct = averageAssetFinancePct(taiwanEtfs);
  const internationalAvgPct = averageAssetFinancePct(internationalEtfs);
  const best = strongestAssetFinanceItem(etfRows);
  const weakest = etfRows
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(left.pct) || 999) - (parseMarketNumber(right.pct) || 999))[0] || null;
  const taiwanBest = strongestAssetFinanceItem(taiwanEtfs);
  const internationalBest = strongestAssetFinanceItem(internationalEtfs);
  const positiveEtfs = etfRows.filter((item) => parseMarketNumber(item?.pct) > 0).length;
  const negativeEtfs = etfRows.filter((item) => parseMarketNumber(item?.pct) < 0).length;
  const tltPct = parseMarketNumber(model.tlt?.pct);
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const germanyTenYearValue = parseMarketNumber(model.germanyTenYear?.close);
  const japanTenYearValue = parseMarketNumber(model.japanTenYear?.close);
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const twUsSpread = Number.isFinite(taiwanTenYearValue) && Number.isFinite(tenYear.value) ? taiwanTenYearValue - tenYear.value : null;
  const curveTone = Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "down" : "flat";
  const durationTone = tltPct > 0 ? "up" : "flat";
  const creditTone = Number.isFinite(avgPct) && avgPct < -0.35 ? "down" : "flat";
  const curveText = Number.isFinite(model.curveSlope) && model.curveSlope < 0
    ? `10Y-2Y 利差 ${formatAssetHubYield(model.curveSlope)}，曲線仍偏倒掛，長天期債券需用久期分層控管。`
    : `10Y-2Y 利差 ${formatAssetHubYield(model.curveSlope)}，曲線未明顯倒掛，短中長天期可分開比較。`;
  const durationText = tltPct > 0
    ? `TLT ${model.tlt?.pct || "--"}，長天期公債價格有修復跡象，可觀察殖利率是否續降。`
    : `TLT ${model.tlt?.pct || "--"}，長天期久期仍承壓，先看 10Y 殖利率是否轉弱。`;
  const creditText = Number.isFinite(avgPct)
    ? `債券 ETF 平均 ${formatAssetFinancePct(avgPct)}，強勢為 ${best?.symbol || "--"}，弱勢為 ${weakest?.symbol || "--"}。`
    : "債券 ETF 報價尚未完整，信用與久期相對強弱等待線上資料補齊。";
  const breadthText = etfRows.length
    ? `${positiveEtfs} 檔上漲 / ${negativeEtfs} 檔下跌`
    : "ETF 樣本同步中";
  const decisionLabel = Number.isFinite(model.curveSlope) && model.curveSlope < 0 && tltPct <= 0
    ? "防守分層"
    : tltPct > 0 && Number.isFinite(avgPct) && avgPct > 0
      ? "久期修復"
      : Number.isFinite(avgPct) && avgPct < 0
        ? "信用降溫"
        : "雙軸觀察";
  const taiwanResearchText = Number.isFinite(twUsSpread)
    ? `台灣市場：台灣 10Y ${formatAssetHubYield(taiwanTenYearValue)}，相對美國 10Y 利差 ${formatAssetHubYield(twUsSpread)}；本地收益補償偏低，台幣帳戶應把美債久期、美元/台幣與 ETF 折溢價分開控管。`
    : `台灣市場：台灣 10Y ${formatAssetHubYield(taiwanTenYearValue)}，台美利差同步中；先以台灣債券 ETF 廣度 ${formatAssetFinancePct(taiwanAvgPct)} 與海外美債曲線判斷配置節奏。`;
  const globalResearchText = `國際市場：美國 2Y ${formatAssetHubYield(twoYear.value)}、10Y ${formatAssetHubYield(tenYear.value)}，${Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "曲線仍倒掛，短端政策壓力尚未解除" : "曲線偏正斜率，短中長天期可分層比較"}；德國 10Y ${formatAssetHubYield(germanyTenYearValue)}、日本 10Y ${formatAssetHubYield(japanTenYearValue)} 作為非美元核心債利率錨。`;
  const allocationResearchText = Number.isFinite(avgPct)
    ? `配置判讀：整體債券 ETF 平均 ${formatAssetFinancePct(avgPct)}，強勢 ${best?.symbol || "--"}、弱勢 ${weakest?.symbol || "--"}；若強勢集中在台灣掛牌美債 ETF 而全球債偏弱，先以美債久期主線為主，不急著擴到全球信用曝險。`
    : "配置判讀：ETF 樣本尚未完整，先以主權利率、美元與 VIX 判斷債券風險溫度。";
  const riskResearchText = `${durationText} ${creditText}`;
  return {
    avgPct,
    best,
    weakest,
    decisionLabel,
    heroTitle: `${decisionLabel}：台灣收益補償 × 國際久期`,
    conclusion: `AI 結論：目前債券研究主軸為「${decisionLabel}」。導入內容聚焦台灣債券市場與國際債券市場：台灣看本地利率、台幣帳戶 ETF、折溢價與匯率；國際看美債曲線、歐日主權利率、美元流動性與信用利差。${curveText} ${durationText}`,
    summaryPoints: [
      `AI 研究主軸：${decisionLabel}。本區不做泛用資料摘要，改以「台灣市場收益補償」與「國際市場久期/信用」兩條線交叉判讀。`,
      taiwanResearchText,
      globalResearchText,
      allocationResearchText,
      riskResearchText,
    ],
    radar: [
      ["10Y 殖利率", formatAssetHubYield(tenYear.value), tenYear.date || "U.S. Treasury", assetHubTone(tenYear.item)],
      ["10Y-2Y 利差", formatAssetHubYield(model.curveSlope), Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "曲線倒掛" : "正利差 / 未明顯倒掛", curveTone],
      ["久期代表", model.tlt?.pct || "--", `TLT 收盤 ${formatGlobalValue(model.tlt?.close)}`, durationTone],
      ["ETF 廣度", breadthText, `平均 ${formatAssetFinancePct(avgPct)}`, assetFinancePctTone(avgPct)],
    ],
    marketAnalysis: [
      {
        title: "台灣債券市場研究",
        tag: "Taiwan bond market",
        aiTheme: "台灣利率、台幣 ETF、折溢價與匯率風險",
        tone: assetFinancePctTone(taiwanAvgPct),
        thesis: "台灣債券市場的分析重點不是單看殖利率，而是把本地利率、台幣匯率、海外債券曝險與 ETF 折溢價放在同一張表裡。",
        metrics: [
          ["台灣 10Y", formatAssetHubYield(taiwanTenYearValue), model.taiwanTenYear?.date || "OTC / Trading Economics", assetHubTone(model.taiwanTenYear)],
          ["台美 10Y 利差", formatAssetHubYield(twUsSpread), "台灣 10Y - 美國 10Y", "flat"],
          ["台灣 ETF 廣度", formatAssetFinancePct(taiwanAvgPct), taiwanBest ? `較強 ${taiwanBest.symbol} ${taiwanBest.pct || "--"}` : "等待 ETF 同步", assetFinancePctTone(taiwanAvgPct)],
        ],
        points: [
          "本地政府公債、公司債、金融債與 Formosa Bond 用來判斷台幣資金利率結構；台灣掛牌美債 ETF 則反映海外久期與匯率。",
          "若台美利差維持大幅負值，台灣投資人買美債 ETF 的主要風險會落在美元/台幣、折溢價與長天期久期波動。",
          "台灣債券 ETF 需拆開看 20 年美債、7-10 年美債、投資級債與金融債，不能只用配息率排序。",
        ],
        action: "AI 研判：台灣債券配置應先確認台幣匯率與折溢價，再用美債 2Y/10Y 曲線決定短、中、長天期 ETF 權重。",
      },
      {
        title: "國際債券市場研究",
        tag: "Global bond market",
        aiTheme: "美債曲線、歐日主權利率、美元與信用利差",
        tone: assetFinancePctTone(internationalAvgPct),
        thesis: "國際債券市場以美債曲線為核心，再用歐洲、日本、新興市場與美元流動性判斷分散配置是否成立。",
        metrics: [
          ["美債 10Y-2Y", formatAssetHubYield(model.curveSlope), model.curveSlope < 0 ? "曲線倒掛" : "曲線正常化", curveTone],
          ["德日 10Y", `${formatAssetHubYield(germanyTenYearValue)} / ${formatAssetHubYield(japanTenYearValue)}`, "德國 / 日本主權利率", "flat"],
          ["國際 ETF 廣度", formatAssetFinancePct(internationalAvgPct), internationalBest ? `較強 ${internationalBest.symbol} ${internationalBest.pct || "--"}` : "等待 ETF 同步", assetFinancePctTone(internationalAvgPct)],
        ],
        points: [
          `美債短端 ${formatAssetHubYield(twoYear.value)} 仍代表政策利率壓力，10Y ${formatAssetHubYield(tenYear.value)} 代表全球折現率核心，兩者決定久期配置節奏。`,
          "歐洲與日本主權利率反映 ECB / BOJ 政策分化，若美元偏強，非美債與新興市場美元債需提高匯率與信用風險權重。",
          "國際債券要分層看公債、投資級債、高收益債、新興市場債與抗通膨債，避免把利率下行行情誤讀成信用風險改善。",
        ],
        action: Number.isFinite(dxyPct) && dxyPct > 0
          ? "AI 研判：美元偏強時先保守看非美債，等 BNDX/IAGG 止穩與 EMB 相對強弱改善後，再提高國際債配置。"
          : "AI 研判：美元壓力不高時，可用國際投資級債作分散來源；若 EMB 轉強，再評估新興市場債風險預算。",
      },
    ],
    playbook: [
      {
        title: "短端防守",
        tag: "SHY / VGSH / BIL",
        tone: Number.isFinite(model.curveSlope) && model.curveSlope < 0 ? "up" : "flat",
        taiwan: `台灣 10Y ${formatAssetHubYield(taiwanTenYearValue)}、台美利差 ${formatAssetHubYield(twUsSpread)}，本地收益補償偏低時，台灣帳戶先保留短天期與現金替代部位。`,
        global: `美國 2Y ${formatAssetHubYield(twoYear.value)} 仍是政策利率壓力核心；曲線倒掛時，短債比追長債更能控制波動。`,
        action: "操作：維持短天期與流動性，等 2Y 下行或 5Y/10Y 同步轉弱，再把久期往中段延伸。",
      },
      {
        title: "中天期核心債",
        tag: "IEF / VGIT / BND / AGG",
        tone: "flat",
        taiwan: "台灣掛牌 7-10 年美債與投資級債 ETF 可作核心層，但要先確認折溢價與美元/台幣方向沒有同時不利。",
        global: `5Y ${formatAssetHubYield(fiveYear.value)}、10Y ${formatAssetHubYield(tenYear.value)} 若同步回落，代表政策壓力開始傳導到核心折現率。`,
        action: "操作：短債之外逐步增加 IEF/VGIT/BND/AGG 類核心債，台灣 ETF 用分批方式降低匯率與時差風險。",
      },
      {
        title: "長天期美債",
        tag: "TLT / VGLT / 台灣美債 ETF",
        tone: durationTone,
        taiwan: "台灣 20 年美債 ETF 價格彈性大，但報酬會同時受海外久期、美元/台幣與折溢價影響，不能只看配息率。",
        global: `TLT ${model.tlt?.pct || "--"} 是長久期修復溫度計；10Y ${formatAssetHubYield(tenYear.value)} 若未轉弱，長債仍可能反覆震盪。`,
        action: "操作：只有在 10Y 回落、通膨/就業支持降息且 TLT 轉強時，才提高長天期權重；否則維持小比例分批。",
      },
      {
        title: "信用與新興市場",
        tag: "LQD / HYG",
        tone: creditTone,
        taiwan: "台灣投資人若透過海外債 ETF 追收益，需把信用利差、匯率與流動性折價一起看，避免只追高配息。",
        global: `信用債需等 HYG/LQD 或 Baa-Aaa 改善再加碼；美元偏強時，EMB 與非美債的匯率與信用風險會一起放大。`,
        action: "操作：投資級債優先於高收益債；HYG/LQD 轉強、美元降溫後，再評估高收益與新興市場債。",
      },
    ],
    checks: [
      ["利率主軸", curveText],
      ["久期觀察", durationText],
      ["信用風險", creditText],
      ["30Y 參考", `30Y ${formatAssetHubYield(thirtyYear.value)}，用來判斷長端通膨與期限溢酬。`],
      ["資料廣度", `線上債券資料 ${onlineRows.length || etfRows.length} 筆，ETF 樣本 ${etfRows.length} 檔。`],
      ["保留邏輯", "已移除靜態商品地圖與評等教材；保留可轉成配置動作的久期與信用策略矩陣。"],
    ],
  };
}
function renderAssetFinanceBondResearchHero(research, tone) {
  const summaryPoints = Array.isArray(research.summaryPoints) ? research.summaryPoints : [research.conclusion];
  const bestLabel = research.best ? `${research.best.symbol} ${research.best.pct || "--"}` : "--";
  const weakestLabel = research.weakest ? `${research.weakest.symbol} ${research.weakest.pct || "--"}` : "--";
  return `
    <div class="asset-finance-bond-research-hero is-${escapeHtml(tone)}">
      <section>
        <small>AI research import · Taiwan / global bond market</small>
        <h5>${escapeHtml(research.heroTitle || research.decisionLabel)}</h5>
        <ul>
          ${summaryPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
        </ul>
      </section>
      <aside>
        <span>
          <small>整體 ETF 廣度</small>
          <b>${escapeHtml(formatAssetFinancePct(research.avgPct))}</b>
        </span>
        <span>
          <small>主線標的</small>
          <b>${escapeHtml(bestLabel)}</b>
        </span>
        <span>
          <small>落後觀察</small>
          <b>${escapeHtml(weakestLabel)}</b>
        </span>
      </aside>
    </div>
  `;
}
function renderAssetFinanceBondResearchMarketAnalysis(research) {
  const items = Array.isArray(research.marketAnalysis) ? research.marketAnalysis : [];
  if (!items.length) return "";
  return `
    <div class="asset-finance-bond-market-analysis-grid">
      ${items.map((item) => `
        <section class="is-${escapeHtml(item.tone || "flat")}">
          <div class="asset-finance-bond-market-analysis-head">
            <span>
              <small>${escapeHtml(item.tag || "Bond market")}</small>
              <h5>${escapeHtml(item.title)}</h5>
            </span>
            <em>${escapeHtml(item.aiTheme ? `AI 主題：${item.aiTheme}` : "AI 主題同步中")}</em>
          </div>
          <p>${escapeHtml(item.thesis || "")}</p>
          <div class="asset-finance-bond-region-metrics">
            ${(item.metrics || []).map(([label, value, detail, tone]) => `
              <span>
                <small>${escapeHtml(label)}</small>
                <b class="${escapeHtml(tone || "flat")}">${escapeHtml(value)}</b>
                <em>${escapeHtml(detail)}</em>
              </span>
            `).join("")}
          </div>
          <ul>
            ${(item.points || []).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
          </ul>
          <p class="asset-finance-bond-region-ai">${escapeHtml(item.action || "")}</p>
        </section>
      `).join("")}
    </div>
  `;
}
function renderAssetFinanceBondResearchPanel(model) {
  const research = buildAssetFinanceBondResearchImport(model);
  const tone = Number.isFinite(research.avgPct) && research.avgPct > 0 ? "up" : Number.isFinite(research.avgPct) && research.avgPct < 0 ? "down" : "flat";
  return `
    <article class="panel-card asset-finance-module-card asset-finance-bond-research-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Imported bond research</p>
          <h4>AI 台灣與國際債券研究分析</h4>
        </div>
        <span>台灣市場 / 國際市場研究分析</span>
      </div>
      ${renderAssetFinanceBondResearchHero(research, tone)}
      <div class="asset-finance-bond-radar-grid">
        ${research.radar.map(([label, value, detail, itemTone]) => renderAssetFinanceSyncStat(label, value, detail, itemTone)).join("")}
      </div>
      <div class="asset-finance-bond-section-head">
        <span><small>Market research analysis</small><b>台灣債券市場與國際債券市場</b></span>
        <em>研究導入主內容</em>
      </div>
      ${renderAssetFinanceBondResearchMarketAnalysis(research)}
      <div class="asset-finance-bond-section-head">
        <span><small>Duration / credit playbook</small><b>久期與信用配置矩陣</b></span>
        <em>導入台灣市場與國際市場研究</em>
      </div>
      <div class="asset-finance-bond-playbook-grid">
        ${research.playbook.map((item) => `
          <section class="is-${escapeHtml(item.tone)}">
            <small>${escapeHtml(item.tag)}</small>
            <b>${escapeHtml(item.title)}</b>
            <div class="asset-finance-bond-playbook-lenses">
              <span>
                <strong>台灣研究</strong>
                <em>${escapeHtml(item.taiwan || "")}</em>
              </span>
              <span>
                <strong>國際研究</strong>
                <em>${escapeHtml(item.global || "")}</em>
              </span>
            </div>
            <p>${escapeHtml(item.action || item.text || "")}</p>
          </section>
        `).join("")}
      </div>
      <div class="asset-finance-bond-check-grid">
        ${research.checks.map(([label, text]) => `
          <span>
            <b>${escapeHtml(label)}</b>
            <small>${escapeHtml(text)}</small>
          </span>
        `).join("")}
      </div>
    </article>
  `;
}
function renderAssetFinanceScenarioPanel(model) {
  return `
    <article class="panel-card asset-finance-module-card asset-finance-scenario-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">AI scenario simulation</p>
          <h4>AI 價格 / 殖利率情境模擬</h4>
        </div>
        <span>信心 ${model.confidence}</span>
      </div>
      <div class="asset-finance-scenario-grid">
        ${model.scenarios.map((item) => `
          <section class="is-${item.tone}">
            <b>${escapeHtml(item.name)}</b>
            <small>${escapeHtml(item.condition)}</small>
            <p>${escapeHtml(item.view)}</p>
          </section>
        `).join("")}
      </div>
    </article>
  `;
}
function averageAssetFinancePct(items = []) {
  const values = items.map((item) => parseMarketNumber(item?.pct)).filter(Number.isFinite);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}
function strongestAssetFinanceItem(items = []) {
  return items
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(right.pct) || -999) - (parseMarketNumber(left.pct) || -999))[0] || null;
}
function formatAssetFinancePct(value) {
  if (!Number.isFinite(value)) return "--";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}
function assetFinancePctTone(value) {
  if (!Number.isFinite(value)) return "flat";
  return value >= 0 ? "up" : "down";
}
function renderAssetFinanceSyncStat(label, value, detail, tone = "flat", options = {}) {
  const isButton = Boolean(options.focusKey || options.button);
  const className = [
    "asset-finance-sync-stat",
    `is-${tone}`,
    isButton ? "is-clickable" : "",
    options.active ? "is-active" : "",
  ].filter(Boolean).join(" ");
  const attrs = isButton
    ? ` type="button"${options.focusKey ? ` data-bond-yield-focus="${escapeHtml(options.focusKey)}"` : ""} aria-pressed="${options.active ? "true" : "false"}"${options.ariaLabel ? ` aria-label="${escapeHtml(options.ariaLabel)}"` : ""}`
    : "";
  const tag = isButton ? "button" : "span";
  return `
    <${tag} class="${escapeHtml(className)}"${attrs}>
      <small>${escapeHtml(label)}</small>
      <strong>${escapeHtml(value)}</strong>
      <em>${escapeHtml(detail || "")}</em>
    </${tag}>
  `;
}
function renderAssetFinanceMetalsResearchSection(model) {
  return `
    <div class="asset-finance-zone-section is-metals" id="asset-finance-metals-dashboard">
      <div class="asset-finance-zone-heading">
        <div>
          <p class="panel-kicker">Precious metals research</p>
          <h3>貴金屬研究區</h3>
        </div>
        <p>集中查看黃金、白銀、鉑鈀、國際貴金屬 ETF 與台灣貴金屬同步狀態。</p>
      </div>
      <div class="asset-finance-zone-layout" id="asset-finance-compare">
        ${renderAssetFinanceMetalProfilesPanel(model)}
        ${renderAssetFinanceMetalsPanel(model)}
        ${renderAssetFinanceMetalDriversPanel(model)}
        ${renderAssetFinanceDecisionCenterPanel(model)}
        ${renderAssetFinanceMetalEtfSyncPanel(model)}
      </div>
    </div>
  `;
}
function getAssetFinanceBondRows(model) {
  return uniqueAssetHubItemsBySymbol(
    (Array.isArray(model?.bondOnlineRows) && model.bondOnlineRows.length ? model.bondOnlineRows : model?.bondEtfs || [])
      .filter((item) => item && !item.error)
  );
}
function isAssetFinanceTaiwanBond(item) {
  const text = `${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.region || ""} ${item?.market || ""}`;
  return /\.TW|\.TWO/i.test(String(item?.symbol || "")) || /台灣|TPEx|TPEX|臺灣/.test(text);
}
function filterAssetFinanceBondRows(rows, pattern) {
  return rows.filter((item) => pattern.test(`${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.region || ""} ${item?.market || ""} ${item?.exchange || ""}`));
}
function getAssetFinanceBondFocusKey(scope, label) {
  const slug = String(label || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `bond-${scope}-${slug || "yield"}`;
}
function getAssetFinanceRateMoveTone(item) {
  const move = parseMarketNumber(item?.pct ?? item?.change);
  if (Number.isFinite(move) && move > 0.01) return "down";
  if (Number.isFinite(move) && move < -0.01) return "up";
  return assetHubTone(item);
}
function getAssetFinanceBondFocusKind(focus) {
  const key = String(focus?.key || "");
  const maturity = String(focus?.maturity || focus?.shortLabel || "");
  if (/taiwan/i.test(key)) return "taiwan";
  if (/germany/i.test(key)) return "germany";
  if (/japan/i.test(key)) return "japan";
  if (/2/.test(maturity)) return "short";
  if (/5/.test(maturity)) return "belly";
  if (/30/.test(maturity)) return "long";
  return "core";
}
function buildAssetFinanceBondFocusEtfPulse(model, focus) {
  const kind = getAssetFinanceBondFocusKind(focus);
  const symbolsByKind = {
    short: ["SHY", "VGSH", "BIL", "SGOV", "USFR", "TFLO"],
    belly: ["IEF", "VGIT", "BND", "AGG"],
    core: ["IEF", "BND", "AGG", "TLT"],
    long: ["TLT", "VGLT", "EDV", "GOVZ"],
    taiwan: ["00679B.TWO", "00687B.TWO", "00696B.TWO", "00697B.TWO", "00795B.TWO", "00857B.TWO", "00931B.TWO"],
    germany: ["BNDX", "IAGG", "EMB"],
    japan: ["BNDX", "IAGG", "EMB"],
  };
  const labelsByKind = {
    short: "短天期 ETF",
    belly: "中天期 ETF",
    core: "核心債 ETF",
    long: "長天期 ETF",
    taiwan: "台灣美債 ETF",
    germany: "國際債 ETF",
    japan: "國際債 ETF",
  };
  const payload = { items: getAssetFinanceBondRows(model) };
  const rows = getAssetHubUsableBySymbols(payload, symbolsByKind[kind] || symbolsByKind.core);
  const avg = averageAssetFinancePct(rows);
  const best = strongestAssetFinanceItem(rows);
  return [
    labelsByKind[kind] || "焦點 ETF",
    formatAssetFinancePct(avg),
    best ? `代表 ${best.symbol} ${best.pct || "--"}` : "等待焦點 ETF 同步",
    assetFinancePctTone(avg),
  ];
}
function buildAssetFinanceBondFocusMetricSet(model, context = {}, focus) {
  const kind = getAssetFinanceBondFocusKind(focus);
  const twoYear = model.yields?.[0]?.value;
  const fiveYear = model.yields?.[1]?.value;
  const tenYear = model.yields?.[2]?.value;
  const thirtyYear = model.yields?.[3]?.value;
  const focusValue = focus?.value;
  const fedRate = parseMarketNumber(model.fedFunds?.close);
  const ecbRate = parseMarketNumber(model.ecbDepositRate?.close);
  const bojRate = parseMarketNumber(model.bojCallRate?.close);
  const taiwanTenYear = parseMarketNumber(model.taiwanTenYear?.close);
  const germanyTenYear = parseMarketNumber(model.germanyTenYear?.close);
  const japanTenYear = parseMarketNumber(model.japanTenYear?.close);
  const twUsSpread = context.twUsSpread;
  const creditSpread = context.creditSpread;
  const aaaValue = context.aaaValue;
  const baaValue = context.baaValue;
  const creditRiskPulse = context.creditRiskPulse;
  const creditHot = Number.isFinite(creditSpread) && creditSpread > 1;
  const curveMetricByKind = {
    short: ["2Y-Fed 壓力", formatAssetHubYield(Number.isFinite(focusValue) && Number.isFinite(fedRate) ? focusValue - fedRate : null), "短端高於政策利率時，短債與現金替代優先", "down"],
    belly: ["5Y-2Y 轉折", formatAssetHubYield(Number.isFinite(fiveYear) && Number.isFinite(twoYear) ? fiveYear - twoYear : null), "中段若先回落，代表降息與景氣放緩預期升溫", Number.isFinite(fiveYear) && Number.isFinite(twoYear) && fiveYear < twoYear ? "up" : "flat"],
    core: ["10Y-2Y 曲線", formatAssetHubYield(model.curveSlope), model.curveSlope < 0 ? "倒掛仍偏防守" : "正斜率可分層配置", model.curveSlope < 0 ? "down" : "up"],
    long: ["30Y-10Y 長端", formatAssetHubYield(Number.isFinite(thirtyYear) && Number.isFinite(tenYear) ? thirtyYear - tenYear : null), "長端期限溢酬決定 TLT/EDV 波動", Number.isFinite(thirtyYear) && Number.isFinite(tenYear) && thirtyYear > tenYear ? "down" : "flat"],
    taiwan: ["台美 10Y 利差", formatAssetHubYield(twUsSpread), "台灣掛牌美債 ETF 需同步看匯率與折溢價", "flat"],
    germany: ["德美 10Y 利差", formatAssetHubYield(Number.isFinite(germanyTenYear) && Number.isFinite(tenYear) ? germanyTenYear - tenYear : null), "歐元區利率錨影響國際核心債分散配置", "flat"],
    japan: ["日美 10Y 利差", formatAssetHubYield(Number.isFinite(japanTenYear) && Number.isFinite(tenYear) ? japanTenYear - tenYear : null), "日本利率正常化會牽動全球長端利率", "flat"],
  };
  const sovereignMetricByKind = {
    short: ["政策利率錨", `Fed ${formatAssetHubYield(fedRate)} / ECB ${formatAssetHubYield(ecbRate)}`, "短端焦點先看央行路徑", (Number.isFinite(fedRate) && fedRate >= 3.5) || (Number.isFinite(ecbRate) && ecbRate >= 2) ? "down" : "flat"],
    belly: ["景氣折現錨", formatAssetHubYield(fiveYear), "5Y 對降息節奏與景氣轉折最敏感", "flat"],
    core: ["全球折現錨", formatAssetHubYield(tenYear), "10Y 是核心債與投資級債的估值中心", Number.isFinite(tenYear) && tenYear >= 4.2 ? "down" : "flat"],
    long: ["期限溢酬錨", formatAssetHubYield(thirtyYear), "30Y 上行時不宜把久期一次拉滿", Number.isFinite(thirtyYear) && thirtyYear >= 4.8 ? "down" : "flat"],
    taiwan: ["本地利率錨", formatAssetHubYield(taiwanTenYear), `台美利差 ${formatAssetHubYield(twUsSpread)}`, assetHubTone(model.taiwanTenYear)],
    germany: ["歐元利率錨", formatAssetHubYield(germanyTenYear), `ECB ${formatAssetHubYield(ecbRate)}，觀察歐債與美元互動`, assetHubTone(model.germanyTenYear)],
    japan: ["日本政策錨", formatAssetHubYield(japanTenYear), `BOJ 代理 ${formatAssetHubYield(bojRate)}，觀察資金回流`, assetHubTone(model.japanTenYear)],
  };
  const ratingDetailByKind = {
    short: "短端焦點下，信用下沉的必要性較低",
    belly: "中天期焦點需用 Aaa/Baa 驗證信用補償",
    core: "核心債配置以評等利差判斷信用溫度",
    long: "長久期不宜再疊加過多信用 beta",
    taiwan: "台灣 ETF 需拆開看海外信用與台幣匯率",
    germany: "非美債配置需比較歐元信用補償",
    japan: "日本利率上行時，低評等與長久期都要降槓桿",
  };
  const riskMetricByKind = {
    short: ["短端信用溫度", formatAssetFinancePct(creditRiskPulse), "HYG-LQD；短端收益足夠時不急著信用下沉", assetFinancePctTone(creditRiskPulse)],
    belly: ["中段信用補償", formatAssetHubYield(creditSpread), "Baa-Aaa；5Y 轉折要等信用同步", creditHot ? "down" : "flat"],
    core: ["核心信用補償", formatAssetHubYield(creditSpread), "Baa-Aaa；核心債配置的信用門檻", creditHot ? "down" : "flat"],
    long: ["長端信用疊加", `${formatAssetHubYield(creditSpread)} / TLT ${model.tlt?.pct || "--"}`, "長久期加信用 beta 時需提高門檻", creditHot || parseMarketNumber(model.tlt?.pct) < 0 ? "down" : "flat"],
    taiwan: ["台灣 ETF 風險補償", formatAssetHubYield(twUsSpread), "台美利差代表匯率與海外久期補償", "flat"],
    germany: ["歐債相對補償", formatAssetHubYield(Number.isFinite(germanyTenYear) && Number.isFinite(tenYear) ? germanyTenYear - tenYear : null), "德美 10Y 利差衡量非美核心債吸引力", "flat"],
    japan: ["日債相對補償", formatAssetHubYield(Number.isFinite(japanTenYear) && Number.isFinite(tenYear) ? japanTenYear - tenYear : null), "日美 10Y 利差衡量資金回流壓力", "flat"],
  };
  return [
    curveMetricByKind[kind] || curveMetricByKind.core,
    sovereignMetricByKind[kind] || sovereignMetricByKind.core,
    ["評等風險基準", kind === "short" ? formatAssetHubYield(aaaValue) : kind === "long" ? formatAssetHubYield(baaValue) : `Aaa ${formatAssetHubYield(aaaValue)} / Baa ${formatAssetHubYield(baaValue)}`, ratingDetailByKind[kind] || ratingDetailByKind.core, assetHubTone(model.moodyBaa)],
    riskMetricByKind[kind] || riskMetricByKind.core,
    buildAssetFinanceBondFocusEtfPulse(model, focus),
  ];
}
function buildAssetFinanceBondYieldFocusInsight(focus, model, context = {}) {
  if (!focus) {
    return {
      title: "利率焦點",
      headline: context.bondFocusLabel || "債券配置",
      summary: "點選殖利率卡片後，AI 會切換為該利率點的久期、曲線與信用風險判讀。",
      action: "",
      metric: null,
    };
  }
  const valueText = focus.valueText || formatAssetHubYield(focus.value);
  const curveSlope = context.curveSlope ?? model.curveSlope;
  const twUsSpread = context.twUsSpread;
  const fedRate = parseMarketNumber(model.fedFunds?.close);
  const ecbRate = parseMarketNumber(model.ecbDepositRate?.close);
  const bojRate = parseMarketNumber(model.bojCallRate?.close);
  const selectedLabel = focus.label || focus.shortLabel || "利率焦點";
  const moveText = focus.tone === "down"
    ? "殖利率上行會壓抑債券價格，先看防守與分批。"
    : focus.tone === "up"
      ? "殖利率回落有利久期修復，但仍需觀察是否擴散到 ETF 廣度。"
      : "殖利率變化中性，重點在曲線相對位置與下一個數據催化。";
  let title = `${selectedLabel} 焦點`;
  let summary = `${selectedLabel} 目前 ${valueText}。${moveText}`;
  let action = "AI 焦點建議：用這個利率點作為配置節奏，不要只看單日價格。";
  if (focus.scope === "us-yield") {
    const maturity = String(focus.maturity || focus.shortLabel || "");
    if (/2/.test(maturity)) {
      title = "短端政策利率焦點";
      summary = `美國 2Y 目前 ${valueText}，主要反映 Fed 路徑與再投資利率；Fed Funds ${formatAssetHubYield(fedRate)} 下，短債與現金替代仍是防守核心。${moveText}`;
      action = "AI 焦點建議：2Y 偏高時，短天期債與浮動利率工具優先；只有在 2Y 明確下行並帶動 5Y/10Y 時，再提高中長天期久期。";
    } else if (/5/.test(maturity)) {
      title = "中短端轉折焦點";
      summary = `美國 5Y 目前 ${valueText}，介於政策路徑與景氣折現之間；若 5Y 先於 10Y 下行，通常代表市場開始押注降息與成長放緩。${moveText}`;
      action = "AI 焦點建議：5Y 改善時可從短債逐步移向中天期核心債，但信用債仍需等 Baa-Aaa 或 HYG/LQD 同步確認。";
    } else if (/30/.test(maturity)) {
      title = "長端期限溢酬焦點";
      summary = `美國 30Y 目前 ${valueText}，對通膨預期、發債供給與期限溢酬更敏感；長端若上行，TLT/EDV 類長久期 ETF 波動會放大。${moveText}`;
      action = "AI 焦點建議：30Y 未轉弱前不宜把久期一次拉滿；若 30Y 與 10Y 同步回落，才提高長天期債權重。";
    } else {
      title = "核心折現率焦點";
      summary = `美國 10Y 目前 ${valueText}，是公債、投資級債、房貸與全球美元資產的核心折現率；10Y-2Y 曲線 ${formatAssetHubYield(curveSlope)}。${moveText}`;
      action = "AI 焦點建議：10Y 下行且 ETF 廣度轉正時，核心債與中長天期公債勝率提高；10Y 上行時先維持短中天期分層。";
    }
  } else if (focus.key === "bond-global-taiwan-10y") {
    title = "台灣主權利率焦點";
    summary = `台灣 10Y 目前 ${valueText}，台美 10Y 利差 ${formatAssetHubYield(twUsSpread)}；台灣美債 ETF 報酬需同時看海外久期、台幣匯率與折溢價。`;
    action = "AI 焦點建議：台灣 10Y 偏低時，本地債券收益補償有限，台灣掛牌美債 ETF 更要用匯率與美債曲線來決定進場節奏。";
  } else if (focus.key === "bond-global-germany-10y") {
    title = "歐元區主權利率焦點";
    summary = `德國 10Y 目前 ${valueText}，可作為歐元區無風險利率錨；ECB 存款利率 ${formatAssetHubYield(ecbRate)}，會影響歐洲投資級債與全球避險資金輪動。`;
    action = "AI 焦點建議：若德債殖利率回落且美元不再走強，全球核心債配置可更分散；若德債上行，非美債 ETF 先保守。";
  } else if (focus.key === "bond-global-japan-10y") {
    title = "日本利率正常化焦點";
    summary = `日本 10Y 目前 ${valueText}，BOJ 代理利率 ${formatAssetHubYield(bojRate)}；日本利率上行常牽動日圓、海外資金回流與全球長端利率。`;
    action = "AI 焦點建議：日本 10Y 若持續上行，長天期美債與全球債波動可能升高；要等 BOJ 壓力緩和後再放大久期。";
  }
  return {
    title,
    headline: `${selectedLabel} · ${valueText}`,
    summary,
    action,
    metric: ["目前焦點", valueText, `${selectedLabel} · ${focus.detail || "資料同步中"}`, focus.tone || "flat"],
  };
}
function buildAssetFinanceBondDashboardCommentary(model, context = {}) {
  const avgPct = context.avgPct;
  const aaaValue = context.aaaValue;
  const baaValue = context.baaValue;
  const creditSpread = context.creditSpread;
  const creditRiskPulse = context.creditRiskPulse;
  const twUsSpread = context.twUsSpread;
  const tltPct = parseMarketNumber(model.tlt?.pct);
  const tenYear = model.yields[2]?.value;
  const vixValue = parseMarketNumber(model.vix?.close);
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const fedRate = parseMarketNumber(model.fedFunds?.close);
  const ecbRate = parseMarketNumber(model.ecbDepositRate?.close);
  const bojRate = parseMarketNumber(model.bojCallRate?.close);
  const cpiPct = parseMarketNumber(model.usCpi?.pct);
  const pcePct = parseMarketNumber(model.usPce?.pct);
  const unemploymentRate = parseMarketNumber(model.usUnemployment?.close);
  const unemploymentChange = parseMarketNumber(model.usUnemployment?.change);
  const curveInverted = Number.isFinite(model.curveSlope) && model.curveSlope < 0;
  const creditHot = Number.isFinite(creditSpread) && creditSpread > 1;
  const durationRepair = Number.isFinite(tltPct) && tltPct > 0.15;
  const etfBreadthPositive = Number.isFinite(avgPct) && avgPct >= 0;
  const policyStillTight = (Number.isFinite(fedRate) && fedRate >= 3.5) || (Number.isFinite(ecbRate) && ecbRate >= 2);
  const inflationSticky = (Number.isFinite(cpiPct) && cpiPct > 0) || (Number.isFinite(pcePct) && pcePct > 0);
  const laborSoftening = (Number.isFinite(unemploymentChange) && unemploymentChange > 0) || (Number.isFinite(unemploymentRate) && unemploymentRate >= 4.3);
  const macroPressure = (Number.isFinite(tenYear) && tenYear >= 4.2) || (Number.isFinite(dxyPct) && dxyPct > 0.35) || (Number.isFinite(vixValue) && vixValue >= 20) || (policyStillTight && inflationSticky && !laborSoftening);
  const tone = creditHot || (curveInverted && !durationRepair) || macroPressure
    ? "down"
    : durationRepair && etfBreadthPositive
      ? "up"
      : "flat";
  const title = tone === "down"
    ? "防守優先，先控久期與信用曝險"
    : tone === "up"
      ? "久期修復可延伸，但要等曲線確認"
      : "核心債分層，等待利率與信用共振";
  const curveView = curveInverted
    ? "曲線倒掛代表短端壓力仍高，短債與現金再投資價值較突出。"
    : "曲線維持正斜率，短中長天期可分層配置，不必只押單一久期。";
  const durationView = durationRepair
    ? `TLT ${model.tlt?.pct || "--"}，長天期債已有修復訊號，但仍要觀察 10Y 是否同步下行。`
    : `TLT ${model.tlt?.pct || "--"}，長天期債尚未形成明確追價條件，久期先分批而非一次拉滿。`;
  const macroView = policyStillTight
    ? `Fed ${formatAssetHubYield(fedRate)}、ECB ${formatAssetHubYield(ecbRate)}、BOJ 代理利率 ${formatAssetHubYield(bojRate)}，政策利率仍是久期估值的主要約束；${inflationSticky ? "CPI/PCE 仍偏上行，降息交易不宜過度提前。" : "通膨動能若降溫，久期勝率才會改善。"}`
    : `Fed ${formatAssetHubYield(fedRate)}、ECB ${formatAssetHubYield(ecbRate)}、BOJ 代理利率 ${formatAssetHubYield(bojRate)}，政策壓力較前期緩和，需觀察 CPI/PCE 與就業是否支持殖利率下行。`;
  const laborView = laborSoftening
    ? `非農 ${formatGlobalValue(model.usPayrolls?.close, 0)}K、失業率 ${formatAssetHubYield(unemploymentRate)}，就業若轉弱會提高核心債與長天期債的修復條件。`
    : `非農 ${formatGlobalValue(model.usPayrolls?.close, 0)}K、失業率 ${formatAssetHubYield(unemploymentRate)}，就業尚未給出明確衰退訊號，信用債不宜只看殖利率高低。`;
  const creditView = Number.isFinite(creditRiskPulse)
    ? `Moody's Aaa ${formatAssetHubYield(aaaValue)}、Baa ${formatAssetHubYield(baaValue)}，Baa-Aaa 利差 ${formatAssetHubYield(creditSpread)}；HYG-LQD 相對強弱 ${formatAssetFinancePct(creditRiskPulse)}，若轉弱代表信用利差補償仍不足。`
    : `Moody's Aaa ${formatAssetHubYield(aaaValue)}、Baa ${formatAssetHubYield(baaValue)}，Baa-Aaa 利差 ${formatAssetHubYield(creditSpread)}，先用信用評等殖利率判斷風險溫度。`;
  const sovereignView = Number.isFinite(twUsSpread)
    ? `台美 10Y 利差 ${formatAssetHubYield(twUsSpread)}，台灣美債 ETF 需把匯率、折溢價與海外久期一起看。`
    : "台美 10Y 利差仍在同步，台灣債券 ETF 先以美債曲線與匯率作主要判讀。";
  const macroContext = context.macroContext || {};
  const macroMetrics = (macroContext.macroRows || []).map(([label, value, detail, tone]) => [
    `總體 · ${label}`,
    value,
    detail,
    tone,
  ]);
  const focusInsight = buildAssetFinanceBondYieldFocusInsight(context.yieldFocus, model, {
    bondFocusLabel: context.bondFocusLabel,
    curveSlope: model.curveSlope,
    twUsSpread,
  });
  const focusMetrics = buildAssetFinanceBondFocusMetricSet(model, {
    aaaValue,
    baaValue,
    creditRiskPulse,
    creditSpread,
    twUsSpread,
  }, context.yieldFocus);
  const action = tone === "down"
    ? "AI 評論：目前不適合只追長債價格彈性，配置順序以短天期、投資級核心債、再到長天期債為主；若 CPI/PCE 未降溫或失業率未轉弱，信用債需等利差或 HYG/LQD 相對強弱改善。"
    : tone === "up"
      ? "AI 評論：若 ETF 廣度維持為正、10Y 殖利率回落，且通膨或就業資料支持政策轉鬆，久期修復行情可延伸到中長天期公債；信用債仍需用 Baa-Aaa 與 HYG/LQD 驗證。"
      : "AI 評論：目前較像等待確認的核心債環境，短天期保留防守，中天期作核心，長天期只在殖利率下行、通膨降溫或 TLT 續強時提高權重。";
  return {
    tone,
    title: `${focusInsight.title}：${title}`,
    confidence: model.confidence,
    headline: `${focusInsight.headline} · ${context.research?.decisionLabel || "訊號同步中"}`,
    summary: `${focusInsight.summary} ${curveView} ${sovereignView} ${macroView} ${laborView} ${durationView} ${creditView}`,
    action: `${focusInsight.action} ${action}`,
    metrics: [
      ...(focusInsight.metric ? [focusInsight.metric] : []),
      ...focusMetrics,
      ...macroMetrics,
    ],
    macroCommentary: macroContext.macroCommentary || "",
  };
}
function getAssetFinanceBondCommentaryPoints(text, limit = 8) {
  const normalized = String(text || "")
    .replace(/\s+/g, " ")
    .replace(/^AI\s*總體基準以\s*/, "以 ")
    .replace(/AI\s*焦點建議：/g, "焦點建議：")
    .replace(/AI\s*評論：/g, "AI 評估：")
    .trim();
  if (!normalized) return [];
  const points = normalized.match(/[^。；]+[。；]?/g) || [normalized];
  return points
    .map((point) => point.trim())
    .filter(Boolean)
    .slice(0, limit);
}
function renderAssetFinanceBondCommentarySection(title, text, tone = "flat", limit = 8) {
  const points = getAssetFinanceBondCommentaryPoints(text, limit);
  if (!points.length) return "";
  return `
    <section class="asset-finance-bond-ai-section is-${escapeHtml(tone)}">
      <h5>${escapeHtml(title)}</h5>
      <ul>
        ${points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}
      </ul>
    </section>
  `;
}
function renderAssetFinanceBondDashboardCommentary(commentary) {
  return `
    <div class="asset-finance-single-ai asset-finance-bond-dashboard-ai is-${escapeHtml(commentary.tone)}" id="asset-finance-bond-dashboard-commentary">
      <div class="asset-finance-single-ai-head">
        <span>
          <small>AI analysis commentary</small>
          <b>AI 分析評論：${escapeHtml(commentary.title)}</b>
        </span>
        <em>${escapeHtml(commentary.headline)} · 信心 ${escapeHtml(commentary.confidence || "--")}</em>
      </div>
      <div class="asset-finance-single-ai-grid">
        ${commentary.metrics.map(([label, value, detail, tone]) => `
          <span>
            <small>${escapeHtml(label)}</small>
            <b class="${escapeHtml(tone)}">${escapeHtml(value)}</b>
            <em>${escapeHtml(detail)}</em>
          </span>
        `).join("")}
      </div>
      <div class="asset-finance-bond-ai-sections">
        ${renderAssetFinanceBondCommentarySection("總體因子基準", commentary.macroCommentary, commentary.tone, 4)}
        ${renderAssetFinanceBondCommentarySection("市場判讀", commentary.summary, commentary.tone, 7)}
        ${renderAssetFinanceBondCommentarySection("AI 焦點建議", commentary.action, commentary.tone, 5)}
      </div>
    </div>
  `;
}
function buildAssetFinanceBondMacroContext(model, rows = getAssetFinanceBondRows(model), focus = null) {
  const bondPayload = { items: rows };
  const lqd = findAssetHubItem(bondPayload, "LQD");
  const hyg = findAssetHubItem(bondPayload, "HYG");
  const creditSpreadProxy = Number.isFinite(parseMarketNumber(hyg?.pct)) && Number.isFinite(parseMarketNumber(lqd?.pct))
    ? parseMarketNumber(hyg.pct) - parseMarketNumber(lqd.pct)
    : null;
  const macroTone = (item) => assetHubTone(item);
  const rateDetail = (item, fallback = "FRED") => item?.date ? `${item.date} · ${fallback}` : fallback;
  const fedRate = parseMarketNumber(model.fedFunds?.close);
  const ecbRate = parseMarketNumber(model.ecbDepositRate?.close);
  const bojRate = parseMarketNumber(model.bojCallRate?.close);
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const vixValue = parseMarketNumber(model.vix?.close);
  const policyTight = (Number.isFinite(fedRate) && fedRate >= 3.5) || (Number.isFinite(ecbRate) && ecbRate >= 2);
  const focusKind = getAssetFinanceBondFocusKind(focus);
  const focusLabel = focus?.shortLabel || focus?.label || "利率焦點";
  const focusValue = focus?.value;
  const useEuroMacro = focusKind === "germany";
  const useJapanMacro = focusKind === "japan";
  const macroRegionLabel = useEuroMacro ? "歐元區" : useJapanMacro ? "日本" : "美國";
  const macroLensLabel = focusKind === "taiwan"
    ? "台灣美債 ETF"
    : useEuroMacro
      ? "德債與歐元核心債"
      : useJapanMacro
        ? "日債與日圓利率"
        : "美債曲線";
  const inflationPrimary = useEuroMacro
    ? { label: "HICP", item: model.euroHicp, source: "FRED / Eurostat" }
    : useJapanMacro
      ? { label: "CPI", item: model.japanCpi, source: "FRED / OECD" }
      : { label: "CPI", item: model.usCpi, source: "FRED / BLS" };
  const inflationSecondary = useEuroMacro || useJapanMacro
    ? null
    : { label: "PCE", item: model.usPce, source: "FRED / BEA" };
  const laborPrimary = useEuroMacro
    ? { label: "失業率", item: model.euroUnemployment, source: "FRED / OECD" }
    : useJapanMacro
      ? { label: "失業率", item: model.japanUnemployment, source: "FRED / OECD" }
      : { label: "失業率", item: model.usUnemployment, source: "FRED / BLS" };
  const laborSecondary = useEuroMacro || useJapanMacro
    ? null
    : { label: "NFP", item: model.usPayrolls, source: "FRED / BLS", digits: 0, suffix: "K" };
  const policyDetailByKind = {
    short: "短端焦點：政策利率決定再投資與現金替代價值",
    belly: "中段焦點：政策轉向會先影響 5Y 評價",
    core: "10Y 焦點：政策路徑仍是核心折現率上緣",
    long: "長端焦點：政策若維持高位，期限溢酬容易放大",
    taiwan: "台灣焦點：本地利率低於美元利率時要看匯率補償",
    germany: "德國焦點：ECB 利率牽動歐債與非美核心債",
    japan: "日本焦點：BOJ 正常化會牽動全球長端利率",
  };
  const dxyDetailByKind = {
    short: "美元偏強會延後非美債修復",
    belly: "美元走弱有利中天期債估值修復",
    core: "10Y 焦點需同步看美元流動性",
    long: "美元與期限溢酬同向上行時，長債波動放大",
    taiwan: "台灣美債 ETF 需把美元與台幣匯率一起看",
    germany: "德債焦點需比較歐元與美元資金流",
    japan: "日債焦點需同步看日圓資金回流與美元壓力",
  };
  const inflationDetailByKind = {
    short: "通膨偏黏會延後短端降息定價",
    belly: "通膨回落才會提高 5Y 轉折可信度",
    core: "10Y 需要 CPI/PCE 降溫才有穩定下行條件",
    long: "長端最怕通膨預期與期限溢酬一起上行",
    taiwan: "美國通膨仍主導台灣美債 ETF 的海外久期",
    germany: "歐債焦點需比較通膨與 ECB 降息空間",
    japan: "日本焦點下，通膨會影響 BOJ 正常化節奏",
  };
  const laborDetailByKind = {
    short: "就業韌性會讓 Fed 維持高利率更久",
    belly: "就業轉弱會讓 5Y 率先反映降息與景氣放緩",
    core: "就業放緩有利 10Y 下行，但信用債需防違約風險",
    long: "就業轉弱支撐長債，但衰退風險會放大波動",
    taiwan: "就業數據影響美債 ETF 久期，同時牽動美元與台幣",
    germany: "歐元區就業若降溫，ECB 降息空間與德債支撐會同步提高",
    japan: "日本就業與薪資若續強，BOJ 正常化壓力會提高",
  };
  const policyValueByKind = {
    short: `${focusLabel} ${formatAssetHubYield(focusValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    belly: `${focusLabel} ${formatAssetHubYield(focusValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    core: `${focusLabel} ${formatAssetHubYield(focusValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    long: `${focusLabel} ${formatAssetHubYield(focusValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    taiwan: `台灣 ${formatAssetHubYield(taiwanTenYearValue)} / Fed ${formatAssetHubYield(fedRate)}`,
    germany: `德國 ${formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close))} / ECB ${formatAssetHubYield(ecbRate)}`,
    japan: `日本 ${formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close))} / BOJ ${formatAssetHubYield(bojRate)}`,
  };
  const sovereignValueByKind = {
    short: `2Y ${formatAssetHubYield(focusValue)} / 10Y ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    belly: `5Y ${formatAssetHubYield(focusValue)} / 10Y ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    core: `10Y ${formatAssetHubYield(focusValue)} / 30Y ${formatAssetHubYield(model.yields?.[3]?.value)}`,
    long: `30Y ${formatAssetHubYield(focusValue)} / 10Y ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    taiwan: `台灣 ${formatAssetHubYield(taiwanTenYearValue)} / 美國 ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    germany: `德國 ${formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close))} / 美國 ${formatAssetHubYield(model.yields?.[2]?.value)}`,
    japan: `日本 ${formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close))} / 美國 ${formatAssetHubYield(model.yields?.[2]?.value)}`,
  };
  const liquidityValueByKind = {
    short: `DXY ${formatGlobalValue(model.dxy?.close)} / 2Y ${formatAssetHubYield(focusValue)}`,
    belly: `DXY ${formatGlobalValue(model.dxy?.close)} / 5Y ${formatAssetHubYield(focusValue)}`,
    core: `DXY ${formatGlobalValue(model.dxy?.close)} / 10Y ${formatAssetHubYield(focusValue)}`,
    long: `DXY ${formatGlobalValue(model.dxy?.close)} / 30Y ${formatAssetHubYield(focusValue)}`,
    taiwan: `DXY ${formatGlobalValue(model.dxy?.close)} / 台灣10Y ${formatAssetHubYield(taiwanTenYearValue)}`,
    germany: `DXY ${formatGlobalValue(model.dxy?.close)} / 德10Y ${formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close))}`,
    japan: `DXY ${formatGlobalValue(model.dxy?.close)} / 日10Y ${formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close))}`,
  };
  const macroMoveOrLevel = (item, digits = 2) => {
    const pct = parseMarketNumber(item?.pct);
    if (Number.isFinite(pct)) return formatAssetFinancePct(pct);
    return formatGlobalValue(item?.close, digits);
  };
  const macroLevel = (item, digits = 2, suffix = "") => {
    const value = formatGlobalValue(item?.close, digits);
    return value === "--" ? value : `${value}${suffix}`;
  };
  const macroDate = (item) => item?.date || "同步中";
  const inflationValue = inflationSecondary
    ? `${inflationPrimary.label} ${macroMoveOrLevel(inflationPrimary.item)} / ${inflationSecondary.label} ${macroMoveOrLevel(inflationSecondary.item)}`
    : `${macroRegionLabel} ${inflationPrimary.label} ${macroMoveOrLevel(inflationPrimary.item)}`;
  const inflationDetail = inflationSecondary
    ? `${inflationDetailByKind[focusKind] || inflationDetailByKind.core}；指數 ${macroLevel(inflationPrimary.item)} / ${macroLevel(inflationSecondary.item)}`
    : `${inflationDetailByKind[focusKind] || inflationDetailByKind.core}；${macroRegionLabel} ${inflationPrimary.label} 指數 ${macroLevel(inflationPrimary.item)} · ${macroDate(inflationPrimary.item)}`;
  const unemploymentRate = parseMarketNumber(laborPrimary.item?.close);
  const laborValue = laborSecondary
    ? `${laborPrimary.label} ${formatAssetHubYield(unemploymentRate)} / ${laborSecondary.label} ${macroLevel(laborSecondary.item, laborSecondary.digits, laborSecondary.suffix)}`
    : `${macroRegionLabel}${laborPrimary.label} ${formatAssetHubYield(unemploymentRate)}`;
  const laborDetail = laborSecondary
    ? `${laborDetailByKind[focusKind] || laborDetailByKind.core}；${laborSecondary.label} ${laborSecondary.item?.pct || "--"} / 失業率變動 ${laborPrimary.item?.pct || "--"}`
    : `${laborDetailByKind[focusKind] || laborDetailByKind.core}；${macroRegionLabel}${laborPrimary.label} ${macroDate(laborPrimary.item)} · 變動 ${laborPrimary.item?.pct || "--"}`;
  const inflationTone = [inflationPrimary.item, inflationSecondary?.item]
    .some((item) => Number.isFinite(parseMarketNumber(item?.pct)) && parseMarketNumber(item.pct) > 0)
    ? "down"
    : "flat";
  const unemploymentChange = parseMarketNumber(laborPrimary.item?.change);
  const unemploymentPct = parseMarketNumber(laborPrimary.item?.pct);
  const payrollPct = parseMarketNumber(laborSecondary?.item?.pct);
  const laborCooling = (Number.isFinite(unemploymentChange) && unemploymentChange > 0)
    || (Number.isFinite(unemploymentPct) && unemploymentPct > 0)
    || (Number.isFinite(payrollPct) && payrollPct < 0);
  const inflationCardLabel = `${macroRegionLabel}通膨基準`;
  const laborCardLabel = `${macroRegionLabel}就業循環`;
  const macroRows = [
    [`${focusLabel} 政策壓力`, policyValueByKind[focusKind] || policyValueByKind.core, policyDetailByKind[focusKind] || policyDetailByKind.core, policyTight ? "down" : "flat"],
    [`${focusLabel} 主權錨`, sovereignValueByKind[focusKind] || sovereignValueByKind.core, `焦點利率相對位置 · ${focus?.detail || "資料同步中"}`, assetHubTone(focus)],
    [`${focusLabel} 美元流動性`, liquidityValueByKind[focusKind] || liquidityValueByKind.core, model.dxy?.pct ? `DXY ${model.dxy.pct} · ${dxyDetailByKind[focusKind] || dxyDetailByKind.core}` : dxyDetailByKind[focusKind] || "ICE / Yahoo Finance", assetHubTone(model.dxy)],
    [`${focusLabel} 風險溫度`, `VIX ${formatGlobalValue(model.vix?.close)} / ${focusLabel} ${formatAssetHubYield(focusValue)}`, model.vix?.pct ? `VIX ${model.vix.pct} · 風險升溫時先控信用債` : "Cboe / Yahoo Finance", Number.isFinite(vixValue) && vixValue >= 20 ? "down" : macroTone(model.vix)],
    [`${focusLabel} 信用代理`, formatAssetFinancePct(creditSpreadProxy), "HYG - LQD 相對強弱，驗證信用風險 appetite", assetFinancePctTone(creditSpreadProxy)],
    [inflationCardLabel, inflationValue, inflationDetail, inflationTone],
    [laborCardLabel, laborValue, laborDetail, laborCooling ? "up" : "flat"],
  ];
  const fed = formatAssetHubYield(fedRate);
  const ecb = formatAssetHubYield(ecbRate);
  const boj = formatAssetHubYield(bojRate);
  const policyText = useEuroMacro
    ? `ECB ${ecb}`
    : useJapanMacro
      ? `BOJ ${boj}`
      : `Fed ${fed}`;
  const inflationText = inflationSecondary
    ? `${inflationPrimary.label} ${macroLevel(inflationPrimary.item)}、${inflationSecondary.label} ${macroLevel(inflationSecondary.item)}`
    : `${macroRegionLabel} ${inflationPrimary.label} ${macroLevel(inflationPrimary.item)}`;
  const laborText = laborSecondary
    ? `${laborPrimary.label} ${formatAssetHubYield(unemploymentRate)}、${laborSecondary.label} ${macroLevel(laborSecondary.item, laborSecondary.digits, laborSecondary.suffix)}`
    : `${macroRegionLabel}${laborPrimary.label} ${formatAssetHubYield(unemploymentRate)}`;
  return {
    macroRows,
    macroCommentary: `AI 總體基準以 ${focusLabel} 為鏡頭：${macroLensLabel} 的通膨基準看 ${inflationText} 是否仍壓住 ${policyText} 的降息空間；就業循環看 ${laborText} 是否轉弱並提高久期修復條件。若政策利率偏高且通膨未明顯降溫，久期不宜一次拉長；若就業轉弱、美元與 VIX 降溫，${focusLabel} 對應的債券修復條件會提高。`,
    macroNote: "資料源：Fed / ECB / BOJ 代理利率、美國 CPI/PCE/非農/失業率、歐元區 HICP/失業率、日本 CPI/失業率使用 FRED；台灣使用 10Y 公債殖利率作央行與本地利率參考；美元、VIX 與信用債代理使用 Yahoo Finance / ETF 行情。",
  };
}
function renderAssetFinanceBondDecisionOverview(model, context = {}) {
  const avgPct = context.avgPct;
  const bondFocusLabel = context.bondFocusLabel || "債券配置";
  const research = context.research || {};
  const selectedYieldFocus = context.selectedYieldFocus;
  const twUsSpread = context.twUsSpread;
  const creditSpread = context.creditSpread;
  const creditRiskPulse = context.creditRiskPulse;
  const twoYearValue = model.yields?.[0]?.value;
  const usTenYearValue = model.yields?.[2]?.value;
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const aaaValue = context.aaaValue;
  const baaValue = context.baaValue;
  const curveInverted = Number.isFinite(model.curveSlope) && model.curveSlope < 0;
  const creditHot = Number.isFinite(creditSpread) && creditSpread > 1;
  const breadthTone = assetFinancePctTone(avgPct);
  const overviewTone = creditHot || curveInverted || breadthTone === "down" ? "down" : breadthTone === "up" ? "up" : "flat";
  const focusText = selectedYieldFocus
    ? `${selectedYieldFocus.label || selectedYieldFocus.shortLabel} ${selectedYieldFocus.valueText || formatAssetHubYield(selectedYieldFocus.value)}`
    : "利率焦點同步中";
  const curveText = curveInverted ? "曲線倒掛，短端防守優先" : "曲線正斜率，短中長天期可分層";
  const sovereignText = Number.isFinite(twUsSpread)
    ? twUsSpread < -1
      ? "台灣利率明顯低於美國，台灣美債 ETF 需同步看匯率與折溢價"
      : "台美利差接近，主權利率壓力較均衡"
    : "台美利差同步中";
  const creditText = creditHot
    ? "Baa-Aaa 利差偏高，信用債需要更高風險補償"
    : "信用利差目前中性，核心債可優先於高收益債";
  const metrics = [
    ["利率曲線", formatAssetHubYield(model.curveSlope), `2Y ${formatAssetHubYield(twoYearValue)} / 10Y ${formatAssetHubYield(usTenYearValue)}`, curveInverted ? "down" : "up"],
    ["主權利差", formatAssetHubYield(twUsSpread), `台灣 ${formatAssetHubYield(taiwanTenYearValue)} / 美國 ${formatAssetHubYield(usTenYearValue)}`, "flat"],
    ["信用風險", formatAssetHubYield(creditSpread), `Aaa ${formatAssetHubYield(aaaValue)} / Baa ${formatAssetHubYield(baaValue)}`, creditHot ? "down" : "flat"],
    ["ETF 廣度", formatAssetFinancePct(avgPct), `HYG-LQD ${formatAssetFinancePct(creditRiskPulse)}`, breadthTone],
  ];
  return `
    <div class="asset-finance-bond-decision-overview is-${escapeHtml(overviewTone)}">
      <section class="asset-finance-bond-decision-main">
        <small>Integrated bond signal</small>
        <h5>${escapeHtml(bondFocusLabel)}</h5>
        <p>AI 統整：目前以 ${escapeHtml(focusText)} 作為利率焦點；${escapeHtml(curveText)}。${escapeHtml(sovereignText)}。${escapeHtml(creditText)}。</p>
        <div class="asset-finance-bond-decision-tags">
          <span>樣本 ${escapeHtml(context.rowsLength ?? "--")} 筆</span>
          <span>${escapeHtml(research.decisionLabel || "訊號同步中")}</span>
          <span>${escapeHtml(selectedYieldFocus?.shortLabel || "10Y")} 焦點</span>
        </div>
      </section>
      <div class="asset-finance-bond-decision-metrics">
        ${metrics.map(([label, value, detail, tone]) => `
          <span class="is-${escapeHtml(tone)}">
            <small>${escapeHtml(label)}</small>
            <b>${escapeHtml(value)}</b>
            <em>${escapeHtml(detail)}</em>
          </span>
        `).join("")}
      </div>
    </div>
  `;
}
function renderAssetFinanceBondCenterDashboard(model) {
  const rows = getAssetFinanceBondRows(model);
  const research = buildAssetFinanceBondResearchImport(model);
  const etfRows = (model.bondEtfs || []).filter((item) => item && !item.error);
  const avgPct = averageAssetFinancePct(etfRows);
  const usTenYear = model.yields[2] || {};
  const usTenYearValue = usTenYear.value;
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const twUsSpread = Number.isFinite(taiwanTenYearValue) && Number.isFinite(usTenYearValue) ? taiwanTenYearValue - usTenYearValue : null;
  const aaaValue = parseMarketNumber(model.moodyAaa?.close);
  const baaValue = parseMarketNumber(model.moodyBaa?.close);
  const creditSpread = Number.isFinite(aaaValue) && Number.isFinite(baaValue) ? baaValue - aaaValue : null;
  const tltPct = parseMarketNumber(model.tlt?.pct);
  const lqd = rows.find((item) => String(item?.symbol || "").toUpperCase() === "LQD");
  const hyg = rows.find((item) => String(item?.symbol || "").toUpperCase() === "HYG");
  const creditRiskPulse = Number.isFinite(parseMarketNumber(hyg?.pct)) && Number.isFinite(parseMarketNumber(lqd?.pct))
    ? parseMarketNumber(hyg.pct) - parseMarketNumber(lqd.pct)
    : null;
  const usYieldFocusRows = model.yields.map((point) => ({
    key: getAssetFinanceBondFocusKey("us-yield", point.maturity),
    scope: "us-yield",
    label: `美國 ${point.maturity}`,
    shortLabel: point.maturity,
    maturity: point.maturity,
    value: point.value,
    valueText: formatAssetHubYield(point.value),
    detail: point.source || "--",
    tone: getAssetFinanceRateMoveTone(point.item || point),
  }));
  const globalYieldRows = [
    { key: "bond-global-taiwan-10y", scope: "global", label: "台灣 10Y", shortLabel: "台灣 10Y", value: taiwanTenYearValue, valueText: formatAssetHubYield(taiwanTenYearValue), detail: model.taiwanTenYear?.date || "Trading Economics / OTC interbank", tone: getAssetFinanceRateMoveTone(model.taiwanTenYear) },
    { key: "bond-global-germany-10y", scope: "global", label: "德國 10Y", shortLabel: "德國 10Y", value: parseMarketNumber(model.germanyTenYear?.close), valueText: formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close)), detail: model.germanyTenYear?.date || "FRED / OECD", tone: getAssetFinanceRateMoveTone(model.germanyTenYear) },
    { key: "bond-global-japan-10y", scope: "global", label: "日本 10Y", shortLabel: "日本 10Y", value: parseMarketNumber(model.japanTenYear?.close), valueText: formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close)), detail: model.japanTenYear?.date || "FRED / OECD", tone: getAssetFinanceRateMoveTone(model.japanTenYear) },
  ];
  const yieldFocusRows = [...usYieldFocusRows, ...globalYieldRows];
  const defaultFocus = yieldFocusRows.find((item) => item.key === "bond-us-yield-2-yr") || yieldFocusRows[0] || null;
  const selectedYieldFocus = yieldFocusRows.find((item) => item.key === assetFinanceBondFocusKey) || defaultFocus;
  if (selectedYieldFocus && assetFinanceBondFocusKey !== selectedYieldFocus.key) assetFinanceBondFocusKey = selectedYieldFocus.key;
  const macroContext = buildAssetFinanceBondMacroContext(model, rows, selectedYieldFocus);
  const bondFocusLabel = Number.isFinite(model.curveSlope) && model.curveSlope < 0
    ? "短天期防守"
    : Number.isFinite(tltPct) && tltPct > 0.15
      ? "久期修復"
      : Number.isFinite(avgPct) && avgPct >= 0
        ? "核心債分層"
        : "信用與久期降溫";
  const commentary = buildAssetFinanceBondDashboardCommentary(model, {
    aaaValue,
    avgPct,
    baaValue,
    bondFocusLabel,
    creditRiskPulse,
    creditSpread,
    research,
    twUsSpread,
    yieldFocus: selectedYieldFocus,
    macroContext,
  });
  return `
    <article class="panel-card asset-finance-module-card asset-finance-bond-research-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Bond Market Analysis Center</p>
          <h4>債券利率、久期與信用風險 Dashboard</h4>
        </div>
        <span>${escapeHtml(bondFocusLabel)} · Yield curve / global spread / credit</span>
      </div>
      ${renderAssetFinanceBondDecisionOverview(model, {
        aaaValue,
        avgPct,
        baaValue,
        bondFocusLabel,
        creditRiskPulse,
        creditSpread,
        research,
        rowsLength: rows.length,
        selectedYieldFocus,
        twUsSpread,
      })}
      <p class="stock-theory-note">美債殖利率曲線</p>
      <div class="asset-finance-yield-grid">
        ${usYieldFocusRows.map((focus) => renderAssetFinanceSyncStat(
          focus.shortLabel,
          focus.valueText,
          focus.detail,
          focus.tone,
          {
            focusKey: focus.key,
            active: selectedYieldFocus?.key === focus.key,
            ariaLabel: `切換 AI 分析評論：${focus.label}`,
          }
        )).join("")}
      </div>
      <p class="stock-theory-note">全球殖利率與主權利率</p>
      <div class="asset-finance-bond-radar-grid">
        ${globalYieldRows.map((focus) => renderAssetFinanceSyncStat(
          focus.shortLabel,
          focus.valueText,
          focus.detail,
          focus.tone,
          {
            focusKey: focus.key,
            active: selectedYieldFocus?.key === focus.key,
            ariaLabel: `切換 AI 分析評論：${focus.label}`,
          }
        )).join("")}
      </div>
      ${renderAssetFinanceBondDashboardCommentary(commentary)}
      <p class="stock-theory-note">資料統整：美債採 U.S. Treasury 官方曲線；台灣 10Y 讀取 Trading Economics 公開頁；德國、日本透過 FRED 讀取；Moody's Aaa/Baa 併入 AI 信用評等分析。${escapeHtml(macroContext.macroNote)}</p>
    </article>
  `;
}
function renderAssetFinanceBondRegionalMarketPanel(model) {
  const rows = getAssetFinanceBondRows(model);
  const bondPayload = { items: rows };
  const taiwanRows = rows.filter(isAssetFinanceTaiwanBond);
  const taiwanEtfs = taiwanRows.filter((item) => String(item?.type || "").includes("ETF"));
  const usRows = rows.filter((item) => {
    if (isAssetFinanceTaiwanBond(item)) return false;
    const text = `${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.market || ""} ${item?.region || ""}`;
    return getAssetHubRegion(item) === "美國" && /Treasury|TIPS|Corporate|High Yield|Muni|MBS|Bond|債券|公債|信用債|市政債|抗通膨|殖利率/i.test(text);
  });
  const usEtfs = usRows.filter((item) => String(item?.type || "").includes("ETF"));
  const globalRows = rows.filter((item) => {
    const text = `${item?.symbol || ""} ${item?.name || ""} ${item?.type || ""} ${item?.market || ""} ${item?.region || ""}`;
    return /DE10Y|JP10Y|BNDX|IAGG|EMB|德國|日本|全球|International|Emerging|新興|非美|JGB|Gilts|歐洲|亞洲/i.test(text);
  });
  const globalEtfs = globalRows.filter((item) => String(item?.type || "").includes("ETF"));
  const taiwanTenYearValue = parseMarketNumber(model.taiwanTenYear?.close);
  const usTenYear = model.yields[2] || {};
  const usTenYearValue = usTenYear.value;
  const twUsSpread = Number.isFinite(taiwanTenYearValue) && Number.isFinite(usTenYearValue) ? taiwanTenYearValue - usTenYearValue : null;
  const dxyPct = parseMarketNumber(model.dxy?.pct);
  const lqd = findAssetHubItem(bondPayload, "LQD");
  const hyg = findAssetHubItem(bondPayload, "HYG");
  const creditPulse = Number.isFinite(parseMarketNumber(hyg?.pct)) && Number.isFinite(parseMarketNumber(lqd?.pct))
    ? parseMarketNumber(hyg.pct) - parseMarketNumber(lqd.pct)
    : null;
  const strongestLabel = (items) => {
    const best = strongestAssetFinanceItem(items);
    return best ? `${best.symbol} ${best.pct || "--"}` : "同步中";
  };
  const examplesLabel = (items, fallback = []) => {
    const examples = items.length
      ? items.slice(0, 5).map((item) => `${item.symbol || "--"} ${item.pct || "--"}`)
      : fallback;
    return examples.join(" / ");
  };
  const groups = [
    {
      title: "台灣債券市場",
      tag: "TPEx / TWSE / CBC",
      rows: taiwanRows,
      tone: assetFinancePctTone(averageAssetFinancePct(taiwanEtfs)),
      role: "台幣帳戶觀察海外債券曝險與本地利率定位，重點不是只看配息，而是匯率、折溢價、久期與交易時差。",
      metrics: [
        ["台灣 10Y", formatAssetHubYield(taiwanTenYearValue), model.taiwanTenYear?.date || "OTC interbank", assetHubTone(model.taiwanTenYear)],
        ["台美 10Y 利差", formatAssetHubYield(twUsSpread), "台灣 10Y - 美國 10Y", "flat"],
        ["ETF 平均", formatAssetFinancePct(averageAssetFinancePct(taiwanEtfs)), `最強 ${strongestLabel(taiwanEtfs)}`, assetFinancePctTone(averageAssetFinancePct(taiwanEtfs))],
      ],
      ai: Number.isFinite(twUsSpread)
        ? `AI 觀察：台灣 10Y 明顯低於美國 10Y，台灣美債 ETF 的報酬主要來自海外久期與匯率；若台幣走強或折溢價擴大，需降低追價。`
        : "AI 觀察：台灣 10Y 資料同步中，先以台灣美債 ETF 平均漲跌、成交量與海外美債久期方向交叉判讀。",
      watch: "觀察央行政策、台幣匯率、ETF 折溢價、20 年美債 ETF 與 7-10 年美債 ETF 的強弱差。",
      examples: examplesLabel(taiwanEtfs, ["00679B", "00687B", "00696B", "00697B", "00795B"]),
    },
    {
      title: "美國債券市場",
      tag: "Treasury / FINRA / FRED",
      rows: usRows,
      tone: assetFinancePctTone(averageAssetFinancePct(usEtfs)),
      role: "全球無風險利率與信用定價核心；先看短端、10Y、30Y 曲線，再分公債、TIPS、投資級債、高收益與 MBS。",
      metrics: [
        ["10Y-2Y 曲線", formatAssetHubYield(model.curveSlope), model.curveSlope < 0 ? "倒掛壓力" : "正斜率", model.curveSlope < 0 ? "down" : "up"],
        ["長天期 TLT", model.tlt?.pct || "--", `收盤 ${formatGlobalValue(model.tlt?.close)}`, assetHubTone(model.tlt)],
        ["信用債脈衝", formatAssetFinancePct(creditPulse), "HYG - LQD", assetFinancePctTone(creditPulse)],
      ],
      ai: Number.isFinite(model.curveSlope) && model.curveSlope < 0
        ? "AI 觀察：曲線倒掛時不要只追長天期公債彈性，短天期與核心綜合債仍是防守底盤；信用債需等 HYG 相對 LQD 轉強。"
        : "AI 觀察：曲線轉正時可把核心債從短天期延伸到中天期，長天期需等 10Y 殖利率回落與 TLT 轉強確認。",
      watch: "觀察 Fed 路徑、2Y/10Y、TLT/IEF/SHY 輪動、LQD/HYG 信用風險與 TIPS 通膨預期。",
      examples: examplesLabel(usEtfs, ["SHY", "IEF", "TLT", "BND", "LQD"]),
    },
    {
      title: "國際與新興市場債券",
      tag: "EU / JGB / Gilts / EM",
      rows: globalRows,
      tone: assetFinancePctTone(averageAssetFinancePct(globalEtfs)),
      role: "補足非美利率、匯率避險與美元債風險；核心差異在外匯、央行政策分化與新興市場信用溢價。",
      metrics: [
        ["德國 10Y", formatAssetHubYield(parseMarketNumber(model.germanyTenYear?.close)), model.germanyTenYear?.date || "FRED", assetHubTone(model.germanyTenYear)],
        ["日本 10Y", formatAssetHubYield(parseMarketNumber(model.japanTenYear?.close)), model.japanTenYear?.date || "FRED", assetHubTone(model.japanTenYear)],
        ["全球 ETF", formatAssetFinancePct(averageAssetFinancePct(globalEtfs)), `最強 ${strongestLabel(globalEtfs)}`, assetFinancePctTone(averageAssetFinancePct(globalEtfs))],
      ],
      ai: Number.isFinite(dxyPct) && dxyPct > 0
        ? "AI 觀察：美元偏強時，非美債與新興市場債需提高匯率與美元債信用風險權重；先看 BNDX/IAGG 是否止穩，再看 EMB 是否補強。"
        : "AI 觀察：美元壓力不高時，國際投資級債可作分散來源；若 EMB 強於 BNDX/IAGG，代表風險偏好正在向新興市場擴散。",
      watch: "觀察 ECB、BOJ、美元指數、匯率避險成本、BNDX/IAGG 與 EMB 的相對強弱。",
      examples: examplesLabel(globalRows, ["BNDX", "IAGG", "EMB", "DE10Y", "JP10Y"]),
    },
  ];
  return `
    <article class="panel-card asset-finance-module-card">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Regional bond markets</p>
          <h4>台灣、美國與國際債券市場</h4>
        </div>
        <span>${rows.length} 筆線上樣本</span>
      </div>
      <div class="asset-finance-bond-research-grid">
        ${groups.map((group) => `
          <section class="is-${escapeHtml(group.tone)}">
            <small>${escapeHtml(group.tag)} · ${group.rows.length || "待接"} 筆</small>
            <h5>${escapeHtml(group.title)}</h5>
            <p class="asset-finance-bond-region-role">${escapeHtml(group.role)}</p>
            <div class="asset-finance-bond-region-metrics">
              ${group.metrics.map(([label, value, detail, tone]) => `
                <span>
                  <small>${escapeHtml(label)}</small>
                  <b class="${escapeHtml(tone)}">${escapeHtml(value)}</b>
                  <em>${escapeHtml(detail)}</em>
                </span>
              `).join("")}
            </div>
            <p class="asset-finance-bond-region-ai">${escapeHtml(group.ai)}</p>
            <ul>
              <li>${escapeHtml(group.watch)}</li>
              <li>${escapeHtml(`代表標的：${group.examples}`)}</li>
            </ul>
          </section>
        `).join("")}
      </div>
    </article>
  `;
}
function renderAssetFinanceBondEtfCenterPanel(model) {
  const rows = getAssetFinanceBondRows(model);
  const bondPayload = { items: rows };
  const etfRows = (model.bondEtfs || []).filter((item) => item && !item.error);
  const onlineRows = Array.isArray(model.bondOnlineRows) ? model.bondOnlineRows.filter((item) => item && !item.error) : [];
  const etfUniverse = uniqueAssetHubItemsBySymbol([
    ...etfRows,
    ...onlineRows.filter((item) => /ETF/i.test(String(item?.type || ""))),
  ]);
  const allRows = etfUniverse.length ? etfUniverse : etfRows;
  const catalogCount = Number(model.bondCatalogCount) || onlineRows.length || allRows.length;
  const avgPct = averageAssetFinancePct(etfRows);
  const best = strongestAssetFinanceItem(etfRows);
  const shortDurationRows = getAssetHubItemsBySymbols(bondPayload, ["SHY", "VGSH", "BIL", "SGOV", "USFR", "TFLO"]);
  const middleDurationRows = getAssetHubItemsBySymbols(bondPayload, ["IEF", "VGIT", "BND", "AGG"]);
  const longDurationRows = getAssetHubItemsBySymbols(bondPayload, ["TLT", "VGLT", "EDV", "GOVZ"]);
  const buckets = [
    { key: "short", title: "短天期 / 貨幣市場", rows: shortDurationRows, detail: "用途：利率不確定時降低價格波動；風險：降息後收益率下滑、價格彈性有限。" },
    { key: "core", title: "中天期 / 核心綜合債", rows: middleDurationRows, detail: "用途：追蹤核心債與中段久期；風險：5Y/10Y 殖利率反彈造成淨值受壓。" },
    { key: "long", title: "長天期公債", rows: longDurationRows, detail: "用途：降息交易與高久期修復；風險：期限溢酬或通膨預期上升時回撤放大。" },
    { key: "credit", title: "信用債 / 高收益", rows: filterAssetFinanceBondRows(allRows, /LQD|HYG|JNK|VCSH|VCIT|IGIB|SJNK|ANGL|信用債|High Yield|Corporate/i), detail: "用途：收益增強與信用利差交易；風險：景氣轉弱時利差擴大。" },
    { key: "special", title: "抗通膨 / 市政 / MBS", rows: filterAssetFinanceBondRows(allRows, /TIP|SCHP|VTIP|MUB|VTEB|MBB|VMBS|抗通膨|市政|MBS/i), detail: "用途：補足特殊債種暴露；風險：實質利率、提前還款、稅務與流動性。" },
    { key: "global", title: "全球 / 新興市場", rows: filterAssetFinanceBondRows(allRows, /BNDX|IAGG|EMB|全球|International|Emerging/i), detail: "用途：補足非美利率、美元債與新興市場配置；風險：美元、主權利差與資金流。" },
    { key: "taiwan", title: "台灣債券 ETF", rows: allRows.filter(isAssetFinanceTaiwanBond), detail: "用途：台幣帳戶追蹤海外債券；風險：匯率、折溢價、交易時差與流動性。" },
    { key: "all", title: "全部債券 ETF", rows: allRows, detail: "用途：總覽線上債券 ETF 標的池；風險：需再依久期、信用、匯率與流動性分層。" },
  ].map((bucket) => ({ ...bucket, rows: uniqueAssetHubItemsBySymbol(bucket.rows || []) }));
  const selectedBucket = buckets.find((bucket) => bucket.key === assetFinanceBondEtfBucketKey) || buckets[0];
  if (selectedBucket.key !== assetFinanceBondEtfBucketKey) assetFinanceBondEtfBucketKey = selectedBucket.key;
  const selectedRows = selectedBucket.rows;
  const selectedAvgPct = averageAssetFinancePct(selectedRows);
  const selectedBest = strongestAssetFinanceItem(selectedRows);
  const selectedWeakest = selectedRows
    .filter((item) => Number.isFinite(parseMarketNumber(item?.pct)))
    .sort((left, right) => (parseMarketNumber(left.pct) || 999) - (parseMarketNumber(right.pct) || 999))[0] || null;
  const selectedSymbols = selectedRows.length
    ? selectedRows.slice(0, 8).map((item) => `${item.symbol || "--"} ${item.pct || "--"}`).join(" / ")
    : "此分類暫無線上標的";
  const activeItem = [selectedBest, best, ...selectedRows, ...allRows].find((item) => item && item.symbol);
  const activeSymbol = String(activeItem?.symbol || "").toUpperCase();
  const selectedLensCounts = selectedRows.reduce((map, item) => {
    const lens = getAssetFinanceBondEtfLens(item);
    const label = lens.strategyBucket || lens.bucket || "未分類";
    map.set(label, (map.get(label) || 0) + 1);
    return map;
  }, new Map());
  const selectedDurationMix = selectedLensCounts.size
    ? [...selectedLensCounts.entries()]
      .sort((left, right) => right[1] - left[1])
      .map(([label, count]) => `${label} ${count} 檔`)
      .join(" / ")
    : "此分類暫無久期樣本";
  const selectedAdvancers = selectedRows.filter((item) => {
    const pct = parseMarketNumber(item?.pct);
    return Number.isFinite(pct) && pct > 0;
  }).length;
  const selectedDecliners = selectedRows.filter((item) => {
    const pct = parseMarketNumber(item?.pct);
    return Number.isFinite(pct) && pct < 0;
  }).length;
  const activeTone = activeItem ? assetFinancePctTone(parseMarketNumber(activeItem?.pct)) : "flat";
  const etfSignals = [
    [
      "久期輪動",
      selectedRows.length ? `${selectedRows.length} 檔` : "--",
      `${selectedBucket.title}：${selectedDurationMix}。${selectedBest ? `目前代表 ${selectedBest.symbol} ${selectedBest.pct || "--"}。` : "等待此分類標的同步。"}`,
      assetFinancePctTone(selectedAvgPct),
    ],
    [
      "ETF 廣度",
      selectedRows.length ? `${selectedAdvancers}/${selectedRows.length} 檔轉強` : "--",
      `${selectedBucket.title}平均 ${formatAssetFinancePct(selectedAvgPct)}；轉弱 ${selectedDecliners} 檔；${selectedBest ? `強勢 ${selectedBest.symbol} ${selectedBest.pct || "--"}` : "尚無強勢標的"}${selectedWeakest ? `，弱勢 ${selectedWeakest.symbol} ${selectedWeakest.pct || "--"}。` : "。"}`,
      assetFinancePctTone(selectedAvgPct),
    ],
    [
      "Bond single AI 連動",
      activeItem?.symbol || "--",
      activeItem
        ? `目前以 ${activeItem.symbol} 作為「${selectedBucket.title}」預設分析標的；點選下方表格其他檔，Bond single AI 會改用該檔重新判讀。`
        : `「${selectedBucket.title}」暫無可分析標的。`,
      activeTone,
    ],
  ];
  const analysisPayload = JSON.stringify(selectedRows.map(getAssetFinanceVolumePayloadItem));
  return `
    <article class="panel-card asset-finance-module-card asset-finance-bond-etf-center-card" id="asset-finance-bond-etf-center" data-asset-finance-volume-card data-asset-finance-analysis-mode="bond" data-asset-finance-volume-payload="${escapeHtml(analysisPayload)}">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">Bond ETF center</p>
          <h4>債券 ETF 標的池、久期與信用分類</h4>
        </div>
        <span>${escapeHtml(selectedBucket.title)} · ${selectedRows.length} 檔 / 全部 ${allRows.length} 檔</span>
      </div>
      <div class="asset-finance-bond-etf-selected">
        <span><small>目前分類</small><b>${escapeHtml(selectedBucket.title)}</b><em>${selectedRows.length} 檔 · 目錄 ${catalogCount} 筆</em></span>
        <span><small>平均漲跌</small><b class="${assetFinancePctTone(selectedAvgPct)}">${formatAssetFinancePct(selectedAvgPct)}</b><em>${escapeHtml(selectedBucket.detail)}</em></span>
        <span><small>相對強勢</small><b>${selectedBest ? `${escapeHtml(selectedBest.symbol)} ${escapeHtml(selectedBest.pct || "--")}` : "--"}</b><em>${escapeHtml(selectedBest?.name || "等待線上資料")}</em></span>
        <span><small>相對弱勢</small><b>${selectedWeakest ? `${escapeHtml(selectedWeakest.symbol)} ${escapeHtml(selectedWeakest.pct || "--")}` : "--"}</b><em>${escapeHtml(selectedWeakest?.name || "等待線上資料")}</em></span>
      </div>
      <div class="asset-finance-bond-signal-grid">
        ${etfSignals.map(([title, value, detail, tone]) => `
          <section class="is-${escapeHtml(tone)}">
            <small>${escapeHtml(value)}</small>
            <b>${escapeHtml(title)}</b>
            <p>${escapeHtml(detail)}</p>
          </section>
        `).join("")}
      </div>
      <div class="asset-finance-bond-bucket-grid" aria-label="債券 ETF 分類檔數選擇">
        ${buckets.map((bucket) => {
          const bucketAvgPct = averageAssetFinancePct(bucket.rows);
          const bucketBest = strongestAssetFinanceItem(bucket.rows);
          const active = bucket.key === selectedBucket.key;
          return `
            <button class="asset-finance-bond-bucket-card is-${assetFinancePctTone(bucketAvgPct)}${active ? " is-active" : ""}" type="button" data-bond-etf-bucket="${escapeHtml(bucket.key)}" aria-pressed="${active ? "true" : "false"}">
              <small>${bucket.rows.length} 檔 · 平均 ${formatAssetFinancePct(bucketAvgPct)}</small>
              <b>${escapeHtml(bucket.title)}</b>
              <p>${escapeHtml(bucketBest ? `代表 ${bucketBest.symbol} ${bucketBest.pct || "--"}。${bucket.detail}` : `${bucket.detail} 點選後下方顯示此分類檔數與明細。`)}</p>
            </button>
          `;
        }).join("")}
      </div>
      <div class="asset-finance-bond-etf-current-list">
        <b>${escapeHtml(selectedBucket.title)}代表標的 · ${selectedRows.length} 檔</b>
        <span>${escapeHtml(selectedSymbols)}</span>
      </div>
      <div class="asset-finance-bond-etf-table-head">
        <span>
          <small>Filtered ETF list</small>
          <b>${escapeHtml(selectedBucket.title)}明細</b>
        </span>
        <em>${selectedRows.length} 檔 · 平均 ${formatAssetFinancePct(selectedAvgPct)} · ${selectedBest ? `強勢 ${escapeHtml(selectedBest.symbol || "--")}` : "等待線上資料"}</em>
      </div>
      <div class="global-table-wrap asset-finance-table-wrap">
        <table class="global-market-table">
          <thead><tr><th>名稱</th><th>代號</th><th>地區</th><th>交易所 / 來源</th><th>分類</th><th>收盤</th><th>漲跌幅</th><th>開盤</th><th>最高</th><th>最低</th><th>量能欄位</th><th>日期</th></tr></thead>
          <tbody>${renderAssetFinanceSelectableBondOnlineRows(selectedRows, activeSymbol) || '<tr><td colspan="12">此分類債券 ETF 線上資料同步中。</td></tr>'}</tbody>
        </table>
      </div>
      <div data-asset-finance-single-analysis-view>
        ${renderAssetFinanceBondSingleAnalysis(activeItem)}
      </div>
    </article>
  `;
}
function renderAssetFinanceBondsResearchSection(model) {
  return `
    <div class="asset-finance-zone-section is-bonds" id="asset-finance-bonds-dashboard">
      <div class="asset-finance-zone-heading">
        <div>
          <p class="panel-kicker">Bond research</p>
          <h3>債券研究區</h3>
        </div>
        <p>集中查看美債殖利率曲線、久期 ETF、信用債與台灣美債 ETF，同一區只放債券資料。</p>
      </div>
      <div class="asset-finance-zone-layout">
        ${renderAssetFinanceBondRegionalMarketPanel(model)}
        ${renderAssetFinanceBondCenterDashboard(model)}
        ${renderAssetFinanceBondResearchPanel(model)}
        ${renderAssetFinanceBondEtfCenterPanel(model)}
      </div>
    </div>
  `;
}
function renderAssetFinanceCrossReferenceSection(model) {
  return `
    <div class="asset-finance-zone-section is-cross">
      <div class="asset-finance-zone-heading">
        <div>
          <p class="panel-kicker">Cross-asset reference</p>
          <h3>跨資產風險參考</h3>
        </div>
        <p>美元、VIX、情境模擬與配置建議只作為風險參考，不與貴金屬或債券明細混表。</p>
      </div>
      <div class="asset-finance-cross-layout">
        ${renderAssetFinanceScenarioPanel(model)}
      </div>
    </div>
  `;
}
function renderAssetHubFinanceDashboard(metals, bonds, options = {}) {
  const model = buildAssetHubFinanceModel(metals, bonds);
  const view = options.view || "combined";
  const isBondsPage = view === "bonds";
  const isMetalsPage = view === "metals";
  const sections = [
    view === "combined" ? renderAssetFinanceCoreDashboard(model, metals, bonds) : "",
    !isBondsPage ? renderAssetFinanceMetalsResearchSection(model) : "",
    isBondsPage ? renderAssetFinanceBondsResearchSection(model) : "",
    !isBondsPage && !isMetalsPage ? renderAssetFinanceCrossReferenceSection(model) : "",
  ].filter(Boolean);
  return `
    <section class="section asset-finance-dashboard-section" id="asset-finance-dashboard">
      <div class="asset-finance-dashboard-stack">
        ${sections.join("")}
      </div>
    </section>
  `;
}
function initAssetFinanceBondFocusControls(root, payloads = []) {
  root.querySelectorAll("[data-bond-yield-focus]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextFocus = button.dataset.bondYieldFocus || "";
      if (!nextFocus || nextFocus === assetFinanceBondFocusKey) return;
      assetFinanceBondFocusKey = nextFocus;
      renderAssetHubPage(payloads);
      document.getElementById("asset-finance-bond-dashboard-commentary")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  });
  root.querySelectorAll("[data-bond-etf-bucket]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextBucket = button.dataset.bondEtfBucket || "all";
      if (!nextBucket || nextBucket === assetFinanceBondEtfBucketKey) return;
      assetFinanceBondEtfBucketKey = nextBucket;
      renderAssetHubPage(payloads);
      document.getElementById("asset-finance-bond-etf-center")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    });
  });
}
function renderAssetHubCompactQuotePanel(kicker, title, items = [], badge = "", emptyText = "線上資料同步中。") {
  return `
    <article class="panel-card asset-hub-group-card asset-finance-quote-panel">
      <div class="asset-hub-group-heading">
        <div>
          <p class="panel-kicker">${escapeHtml(kicker)}</p>
          <h4>${escapeHtml(title)}</h4>
        </div>
        ${badge ? `<span>${escapeHtml(badge)}</span>` : ""}
      </div>
      ${renderAssetHubQuoteGrid(items, emptyText)}
    </article>
  `;
}
function renderAssetHubMetals() {
  return "";
}
function renderAssetHubBonds(payload) {
  const yields = [
    getAssetHubTreasuryYieldPoint(payload, "2 Yr", ["US2Y", "^UST2Y"]),
    getAssetHubTreasuryYieldPoint(payload, "5 Yr", ["^FVX"]),
    getAssetHubTreasuryYieldPoint(payload, "10 Yr", ["^TNX"]),
    getAssetHubTreasuryYieldPoint(payload, "30 Yr", ["^TYX"]),
  ];
  const twoYear = yields[0]?.value;
  const tenYear = yields[2]?.value;
  const curveSlope = Number.isFinite(tenYear) && Number.isFinite(twoYear) ? tenYear - twoYear : null;
  const curveLabel = curveSlope === null ? "資料不足" : curveSlope >= 0 ? "長短端正利差" : "殖利率曲線倒掛";
  const treasuryCurve = payload?.validation?.treasuryCurve || {};
  const secondaryMatched = Number(payload?.validation?.secondaryMatchedCount) || 0;
  const macroItems = getAssetHubUsableBySymbols(payload, ["US2Y", "^FVX", "^TNX", "^TYX", "DX-Y.NYB", "^VIX"]);
  const taiwanEtfs = getAssetHubUsableItems(payload).filter((item) => getAssetHubRegion(item) === "台灣" && String(item.type || "").includes("債券 ETF"));
  const treasuryEtfs = getAssetHubUsableBySymbols(payload, ["SHY", "VGSH", "IEF", "VGIT", "TLT", "VGLT", "BND", "AGG", "BNDX"]);
  const creditEtfs = getAssetHubUsableItems(payload).filter((item) => /信用債|High Yield|Investment Grade|新興市場債|抗通膨債|MBS|市政債/i.test(`${item.type || ""} ${item.name || ""}`));
  return `
    <section class="section asset-hub-section" id="asset-bonds">
      ${renderAssetHubSummary(payload, "債券研究區", "Bonds", "只整理美債殖利率曲線、久期 ETF、信用債、抗通膨債與台灣美債 ETF。", "bonds.html")}
      <div class="asset-hub-layout asset-hub-bonds-layout">
        <article class="panel-card asset-yield-curve-card"><div class="asset-hub-group-heading"><div><p class="panel-kicker">Yield curve</p><h4>美債殖利率曲線</h4></div><span>${escapeHtml(curveLabel)}</span></div><div class="asset-yield-points">${yields.map((point) => `<div><span>${escapeHtml(point.maturity)}</span><strong>${formatAssetHubYield(point.value)}</strong><small class="${assetHubTone(point.item)}">${escapeHtml(point.pct || "--")}</small></div>`).join("") || '<p class="stock-detail-empty">殖利率資料同步中。</p>'}</div><p>10 年期減 2 年期利差：<b>${curveSlope === null ? "--" : `${curveSlope >= 0 ? "+" : ""}${curveSlope.toFixed(2)} 個百分點`}</b>。${treasuryCurve.date ? ` 美國財政部官方曲線 ${escapeHtml(treasuryCurve.date)}，已比對 ${secondaryMatched} 個期限。` : " 美國財政部官方曲線暫時無法同步，僅顯示 Yahoo Finance 行情。"}</p></article>
        ${renderAssetHubCompactQuotePanel("Macro risk", "美元、VIX 與利率風險", macroItems, `${macroItems.length} 筆`, "總體風險資料同步中。")}
        ${renderAssetHubCompactQuotePanel("Taiwan bond ETF", "台灣美債 ETF", taiwanEtfs, `${taiwanEtfs.length} 檔`, "台灣債券 ETF 同步中。")}
        ${renderAssetHubCompactQuotePanel("Treasury ETF", "國際公債 ETF 久期分層", treasuryEtfs, `${treasuryEtfs.length} 檔`, "公債 ETF 同步中。")}
        ${renderAssetHubCompactQuotePanel("Credit / inflation", "信用債、抗通膨債與其他債券", creditEtfs.slice(0, 10), `${creditEtfs.length} 檔`, "信用債與抗通膨債資料同步中。")}
        ${renderAssetHubRegionalGroups(payload, "債券地區市場", () => true, "債券資料同步中。")}
      </div>
      ${renderAssetHubOnlineTable(payload, "債券")}
    </section>
  `;
}
function createAssetHubPlaceholder(category, title, kicker) {
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
      primary: "Yahoo Finance 線上資料",
      reference: "來源同步中",
    },
    source: "Yahoo Finance 線上資料",
    updatedAt: "--",
  };
}
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
  const bullish = Number(optionsModel.probabilities?.bullish) || 0;
  const bearish = Number(optionsModel.probabilities?.bearish) || 0;
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
      evidence: `多 ${bullish}% / 空 ${bearish}% / 震盪 ${optionsModel.probabilities.range}%；PCR ${optionsDecimal(optionsModel.pcr)}；VIX ${Number.isFinite(optionsModel.vixValue) ? optionsModel.vixValue.toFixed(2) : "--"}。`,
      conclusion: optionsModel.riskScore >= 66 ? "避險與權利金風險偏高，會壓抑追價與槓桿承受度。" : optionScore >= 58 ? "選擇權結構支持偏多情境，但仍需突破 Call OI 壓力確認。" : optionScore <= 42 ? "Put、VIX 或風險分數偏高，對盤勢形成下行壓力。" : "PCR 與 OI 接近平衡，選擇權偏向區間牽引。",
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
  const chain = optionsModel.chain || {};
  const chainAnalysis = chain.analysis || {};
  const chainSource = chain.source || {};
  const skew = optionsModel.maxIv !== null && optionsModel.minIv !== null ? optionsModel.maxIv - optionsModel.minIv : null;
  const topStrategy = buildOptionsStrategyRows(optionsModel)[0] || null;
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
            <strong>${escapeHtml(optionsModel.direction)} · 風險 ${optionsModel.riskScore}/100</strong>
            <p>${escapeHtml(optionsModel.primaryRisk)}；信心分數 ${optionsModel.confidenceScore}/100。</p>
            <div class="options-probability-bars">
              ${[["多方", optionsModel.probabilities.bullish, "up"], ["空方", optionsModel.probabilities.bearish, "down"], ["震盪", optionsModel.probabilities.range, "flat"]].map(([label, value, tone]) => `<span class="is-${tone}"><b>${label}</b><i style="--bar:${Number(value) || 0}%"></i><em>${Number(value) || 0}%</em></span>`).join("")}
            </div>
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
          <strong>${escapeHtml(chainAnalysis.bias || optionsModel.direction || "盤勢同步中")} · ${escapeHtml(chainAnalysis.strategySuggestion || topStrategy?.name || "等待策略條件")}</strong>
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
          <div class="asset-hub-group-heading"><div><p class="panel-kicker">AI Decision Brief</p><h4>AI 今日結論與策略</h4></div><span>信心 ${chainAnalysis.confidenceScore ?? optionsModel.confidenceScore}/100</span></div>
          <div class="derivatives-overview-decision-lead is-${optionDirectionTone}">
            <small>${escapeHtml(chainAnalysis.bias || optionsModel.direction || "盤勢同步中")}</small>
            <strong>${escapeHtml(chainAnalysis.strategySuggestion || topStrategy?.name || "等待策略條件")}</strong>
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
              ["波動風險", optionsModel.riskScore],
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
function renderAssetHubPage(payloads = []) {
  const root = document.getElementById("asset-hub-root");
  if (!root) return;
  const mode = document.body.dataset.assetHubMode || "derivatives";
  const availablePayloads = payloads.filter(Boolean);
  const byCategory = new Map(availablePayloads.map((payload) => [payload.category, payload]));
  const futures = byCategory.get("futures") || createAssetHubPlaceholder("futures", "期貨", "Futures");
  const options = byCategory.get("options") || createAssetHubPlaceholder("options", "選擇權", "Options");
  const metals = byCategory.get("precious-metals") || createAssetHubPlaceholder("precious-metals", "貴金屬", "Precious Metals");
  const bonds = byCategory.get("bonds") || createAssetHubPlaceholder("bonds", "債券", "Bonds");
  const isBondsMode = mode === "bonds";
  const isMetalsMode = mode === "precious-metals";
  const isFinanceMode = ["finance", "bonds", "precious-metals"].includes(mode);
  const financeView = isBondsMode ? "bonds" : isMetalsMode ? "metals" : "combined";
  const bindPublicOptionControls = () => {
    root.querySelectorAll("[data-asset-option-underlying]").forEach((button) => {
      button.addEventListener("click", async () => {
        const underlying = String(button.dataset.assetOptionUnderlying || "").toUpperCase();
        if (!underlying || button.classList.contains("is-active")) return;
        const status = root.querySelector("[data-asset-option-status]");
        button.disabled = true;
        if (status) {
          status.dataset.state = "loading";
          status.textContent = `正在載入 ${underlying} 公開選擇權鏈...`;
        }
        try {
          const response = await fetchWithTimeout(`/api/us-market/options-chain/${encodeURIComponent(underlying)}`, { cache: "no-store" }, 20000);
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const chain = await response.json();
          const optionsPayload = byCategory.get("options") || options;
          const nextOptions = { ...optionsPayload, optionChain: chain };
          renderAssetHubPage(availablePayloads.map((item) => item.category === "options" ? nextOptions : item));
        } catch (error) {
          button.disabled = false;
          if (status) {
            status.dataset.state = "error";
            status.textContent = `${underlying} 公開選擇權鏈暫時無法取得，請稍後再試。`;
          }
          console.error(`Failed to load ${underlying} options chain:`, error);
        }
      });
    });
  };
  if (!isFinanceMode) {
    root.innerHTML = renderDerivativesMarketOverview(futures, options);
    bindPublicOptionControls();
    return;
  }
  const navigation = isFinanceMode
    ? isBondsMode
      ? [
        ["債券研究區", "Bonds", "bonds", "#asset-finance-bonds-dashboard", bonds],
        ["貴金屬與債券", "Finance hub", "dashboard", "international-finance.html", bonds],
      ]
      : isMetalsMode
        ? [
          ["貴金屬研究區", "Precious metals", "metals", "#asset-finance-metals-dashboard", metals],
          ["債券研究區", "Bonds", "bonds", "bonds.html", bonds],
          ["貴金屬與債券", "Finance hub", "dashboard", "international-finance.html", metals],
        ]
        : [
          ["貴金屬", "Precious metals", "metals", "#asset-finance-metals-dashboard", metals],
          ["債券", "Bonds", "bonds", "bonds.html", bonds],
        ]
    : [
      ["期貨", "Futures", "futures", "#asset-futures", futures],
      ["選擇權", "Options", "options", "#asset-options", options],
    ];
  const hero = isBondsMode
    ? {
      kicker: "Bonds Platform",
      title: "債券與殖利率分析平台",
      text: "集中查看美債殖利率曲線、久期 ETF、信用債、台灣美債 ETF 與 AI 債券研究導入。",
    }
    : isMetalsMode
      ? {
        kicker: "Precious Metals Platform",
        title: "貴金屬避險分析平台",
        text: "集中查看黃金、白銀、鉑鈀、國際貴金屬 ETF 與台灣貴金屬同步狀態。",
      }
      : isFinanceMode
    ? {
      kicker: "Metals & Bonds",
      title: "貴金屬與債券研究平台",
      text: "整合 Yahoo Finance 線上行情與 U.S. Treasury 官方殖利率曲線；貴金屬與跨資產參考留在此頁，債券研究區移至獨立頁。",
    }
    : {
      kicker: "Futures & Options",
      title: "期權分析中心",
      text: "整合 TAIFEX、CME / ICE、Cboe / OCC 與 Yahoo Finance 線上資料；期貨、選擇權與未平倉依台灣、美國與其他市場分區呈現。",
    };
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">${escapeHtml(hero.kicker)}</p>
      <h1>${escapeHtml(hero.title)}</h1>
      <p class="hero-text">${escapeHtml(hero.text)}</p>
    </section>
    <section class="section asset-hub-navigation-section">
      <div class="asset-hub-navigation">
        ${navigation.map(([title, en, key, href, payload]) => `<a class="asset-hub-nav-card is-${key}" href="${safeUrl(href)}"><span>${escapeHtml(en)}</span><strong>${escapeHtml(title)}</strong><small>有效 ${payload?.summary?.count ?? 0} / 目錄 ${payload?.catalogCount ?? getAssetHubItems(payload).length} 筆 · ${escapeHtml((payload?.regionBreakdown || []).map((item) => item.region).join(" / ") || "地區同步中")}</small></a>`).join("")}
      </div>
    </section>
    ${isFinanceMode ? renderAssetHubFinanceDashboard(metals, bonds, { view: financeView }) : ""}
    ${isFinanceMode ? "" : renderAssetHubSchemaPanel(navigation.map(([, , , , payload]) => payload))}
    ${isFinanceMode ? "" : `${renderAssetHubFutures(futures)}${renderAssetHubOptions(options)}`}
  `;
  initAssetFinanceTrendSwitchers(root);
  initAssetFinanceVolumeSelectors(root);
  initAssetFinanceBondFocusControls(root, availablePayloads);
  const bindAssetHubPageControls = () => {
  root.querySelectorAll("[data-asset-load-more]").forEach((button) => {
    button.addEventListener("click", async () => {
      const category = button.dataset.assetLoadMore || "";
      const limit = Number(button.dataset.assetLoadLimit) || 24;
      if (!category) return;
      button.disabled = true;
      button.textContent = "同步更多行情...";
      try {
        const response = await fetchWithTimeout(`/api/global-market/${encodeURIComponent(category)}?limit=${limit}`, { cache: "no-store" }, 75000);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const nextPayload = await response.json();
        const current = byCategory.get(category);
        if (category === "options" && current?.optionChain) nextPayload.optionChain = current.optionChain;
        if (category === "options" && current?.taiwanOptionChain) nextPayload.taiwanOptionChain = current.taiwanOptionChain;
        renderAssetHubPage(availablePayloads.map((payload) => payload.category === category ? nextPayload : payload));
      } catch (error) {
        button.disabled = false;
        button.textContent = "載入更多已驗證行情";
        console.error(`Failed to load more ${category} data:`, error);
      }
    });
  });
  root.querySelectorAll("[data-tw-option-expiry-select]").forEach((select) => {
    select.addEventListener("change", async () => {
      const expiry = select.value || "";
      if (!expiry) return;
      select.disabled = true;
      try {
        const optionsPayload = byCategory.get("options") || options;
        const underlying = getActiveTaiwanOptionUnderlying(optionsPayload.taiwanOptionChain || {});
        const response = await fetchWithTimeout(`/api/options/chain?underlying=${encodeURIComponent(underlying)}&expiry=${encodeURIComponent(expiry)}&source=${encodeURIComponent(derivativesOptionsChainSource)}`, { cache: "no-store" }, 30000);
        const payload = await response.json();
        if (!response.ok || payload.success === false) throw new Error(payload?.error?.message || `HTTP ${response.status}`);
        const nextOptions = { ...optionsPayload, taiwanOptionChain: payload.data };
        renderAssetHubPage(availablePayloads.map((item) => item.category === "options" ? nextOptions : item));
      } catch (error) {
        select.disabled = false;
        console.error("Failed to switch Taiwan option expiry:", error);
      }
    });
  });
  root.querySelectorAll("[data-tw-option-product]").forEach((button) => {
    button.addEventListener("click", async () => {
      const underlying = String(button.dataset.twOptionProduct || "").toUpperCase();
      if (!underlying || button.classList.contains("is-active")) return;
      derivativesOptionsSelectedUnderlying = underlying;
      derivativesOptionsSelectedStrike = "";
      button.disabled = true;
      try {
        const response = await fetchWithTimeout(`/api/options/chain?underlying=${encodeURIComponent(underlying)}&source=${encodeURIComponent(derivativesOptionsChainSource)}`, { cache: "no-store" }, 30000);
        const payload = await response.json();
        if (!response.ok || payload.success === false) throw new Error(payload?.error?.message || `HTTP ${response.status}`);
        const optionsPayload = byCategory.get("options") || options;
        const nextOptions = { ...optionsPayload, taiwanOptionChain: payload.data };
        renderAssetHubPage(availablePayloads.map((item) => item.category === "options" ? nextOptions : item));
      } catch (error) {
        button.disabled = false;
        console.error("Failed to switch Taiwan option product:", error);
      }
    });
  });
  };
  bindAssetHubPageControls();
  bindPublicOptionControls();
}
async function initAssetHubPage() {
  const root = document.getElementById("asset-hub-root");
  if (!root) return;
  const mode = document.body.dataset.assetHubMode || "derivatives";
  const isBondsMode = mode === "bonds";
  const isMetalsMode = mode === "precious-metals";
  const isFinanceMode = ["finance", "bonds", "precious-metals"].includes(mode);
  const loadingCopy = isBondsMode
    ? {
      eyebrow: "Bonds Platform",
      title: "債券與殖利率資料載入中",
      text: "正在取得債券、殖利率曲線與 ETF 資料...",
      errorTitle: "債券資料暫時無法載入",
    }
    : isMetalsMode
      ? {
        eyebrow: "Precious Metals Platform",
        title: "貴金屬資料載入中",
        text: "正在取得貴金屬與 ETF 資料...",
        errorTitle: "貴金屬資料暫時無法載入",
      }
      : isFinanceMode
        ? {
          eyebrow: "Metals & Bonds",
          title: "貴金屬與債券線上資料載入中",
          text: "正在取得債券與貴金屬資料...",
          errorTitle: "貴金屬與債券資料暫時無法載入",
        }
        : {
          eyebrow: "Futures & Options Overview",
          title: "期貨及選擇權盤勢總覽載入中",
          text: "正在同步主要期貨合約、TAIFEX 選擇權鏈、PCR、VIX 與風險訊號...",
          errorTitle: "期貨及選擇權盤勢暫時無法載入",
        };
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">${escapeHtml(loadingCopy.eyebrow)}</p>
      <h1>${escapeHtml(loadingCopy.title)}</h1>
      <p class="hero-text">${escapeHtml(loadingCopy.text)}</p>
    </section>
  `;
  const categories = isBondsMode
    ? ["bonds"]
    : isMetalsMode
      ? ["precious-metals"]
      : isFinanceMode
        ? ["precious-metals", "bonds"]
        : ["futures", "options"];
  const results = await Promise.allSettled(categories.map((category) => {
    const endpoint = isFinanceMode
      ? `/api/global-market/${encodeURIComponent(category)}?limit=all`
      : `/api/${encodeURIComponent(category)}?limit=all`;
    return fetchWithTimeout(endpoint, { cache: "no-store" }, 120000)
      .then((response) => {
        if (!response.ok) throw new Error(`${category} HTTP ${response.status}`);
        return response.json();
      })
      .then((responsePayload) => {
        if (!isFinanceMode && responsePayload?.success === false) {
          throw new Error(responsePayload?.error?.message || `${category} 資料暫不可用`);
        }
        return isFinanceMode ? responsePayload : responsePayload?.data;
      });
  }));
  const payloads = results.map((result) => result.status === "fulfilled" ? result.value : null).filter(Boolean);
  if (!payloads.length) {
    root.innerHTML = `
      <section class="subpage-hero">
        <p class="eyebrow">${escapeHtml(loadingCopy.eyebrow)}</p>
        <h1>${escapeHtml(loadingCopy.errorTitle)}</h1>
        <p class="hero-text">請稍後再試，或確認部署環境可連線 Yahoo Finance。</p>
      </section>
    `;
    return;
  }
  if (!isFinanceMode) {
    const taiwanInstitutionSymbols = ["TX", "MTX", "TMF", "TE", "TF", "SOF", "XIF", "STF", "ETF-F"];
    const [institutionResult, newsResult] = await Promise.allSettled([
      Promise.allSettled(taiwanInstitutionSymbols.map(async (symbol) => {
        const response = await fetchWithTimeout(`/api/institution?product=${encodeURIComponent(symbol)}`, { cache: "no-store" }, 20000);
        if (!response.ok) throw new Error(`${symbol} institution HTTP ${response.status}`);
        const responsePayload = await response.json();
        return [symbol, responsePayload?.data || {}];
      })).then((results) => Object.fromEntries(results.filter((result) => result.status === "fulfilled").map((result) => result.value))),
      fetchWithTimeout("/api/news?category=derivatives&symbol=%5EVIX&limit=8", { cache: "no-store" }, 20000).then(async (response) => {
        if (!response.ok) throw new Error(`news HTTP ${response.status}`);
        const responsePayload = await response.json();
        return responsePayload?.data?.items || [];
      }),
    ]);
    const futuresPayload = payloads.find((payload) => payload.category === "futures");
    const optionsPayload = payloads.find((payload) => payload.category === "options");
    if (futuresPayload && institutionResult.status === "fulfilled") {
      futuresPayload.overviewInstitutions = institutionResult.value;
      futuresPayload.overviewInstitution = institutionResult.value.TX || {};
    }
    if (optionsPayload && newsResult.status === "fulfilled") optionsPayload.overviewNews = newsResult.value;
  }
  const optionsPayload = payloads.find((payload) => payload.category === "options");
  renderAssetHubPage(payloads);
  if (optionsPayload) {
    fetchWithTimeout("/api/us-market/options-chain/SPY", { cache: "no-store" }, 16000)
      .then((response) => response.ok ? response.json() : null)
      .then((chain) => {
        if (chain) {
          optionsPayload.optionChain = chain;
          renderAssetHubPage(payloads);
        }
      })
      .catch((error) => console.warn("Failed to load SPY options chain:", error));
  }
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
  const basis = Number(data.basis);
  const basisPct = Number(data.basisPct);
  return `
    <article class="panel-card asset-option-sentiment">
      <p class="panel-kicker">Basis</p>
      <h4>期現貨價差</h4>
      <strong>${Number.isFinite(basis) ? `${basis >= 0 ? "+" : ""}${basis.toFixed(0)}` : "--"}</strong>
      <span>期貨 ${formatAssetOptionNumber(data.futurePrice)} / 現貨 ${formatAssetOptionNumber(data.spotPrice)}</span>
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
  const futuresPayload = futuresResult.data || createAssetHubPlaceholder("futures", "期貨", "Futures");
  const optionsPayload = optionsResult.data || createAssetHubPlaceholder("options", "選擇權", "Options");
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
        <span><b>${summary.count ?? 0}</b><small>有效資料</small></span>
        <span><b>${summary.advancers ?? 0} / ${summary.decliners ?? 0}</b><small>上漲 / 下跌</small></span>
        <span><b>${escapeHtml(summary.avgPct || "--")}</b><small>平均漲跌幅</small></span>
        <span><b>${escapeHtml(summary.strongest || "--")}</b><small>最強標的</small></span>
      </div>
      ${renderAssetHubRegionChips(payload)}
      <p class="asset-hub-insight">驗證 ${Number(validation.verifiedCount) || 0} 筆、限制 ${Number(validation.limitedCount) || 0} 筆、失敗 ${Number(validation.failedCount) || 0} 筆；主來源：${escapeHtml(validation.primary || payload?.source || "--")}。</p>
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
  if (!root) return;
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
              <span class="derivatives-market-state-risk">${model.riskLabel}</span>
            </div>
          </div>
          <div class="derivatives-market-state-metrics">
            <span class="derivatives-market-state-metric"><b>${value(model.futuresPrice, (item) => formatAssetOptionWhole(item))}</b><small>TX Futures · ${derivativesSignalLabel(model.futuresPct, "偏強", "偏弱", "中性")}</small></span>
            <span class="derivatives-market-state-metric"><b>${value(model.basis, (item) => `${item >= 0 ? "+" : ""}${item.toFixed(0)}`)}</b><small>Basis · ${derivativesSignalLabel(model.basis, "正價差", "逆價差", "接近現貨")}</small></span>
            <span class="derivatives-market-state-metric"><b>${value(model.oiPcr)}</b><small>OI PCR · ${Number.isFinite(model.oiPcr) ? model.oiPcr >= 1.25 ? "防守增加" : model.oiPcr <= 0.75 ? "多方集中" : "中性" : "資料不足"}</small></span>
            <span class="derivatives-market-state-metric"><b>${value(model.volumePcr)}</b><small>Volume PCR · ${Number.isFinite(model.volumePcr) ? model.volumePcr >= 1.1 ? "偏空交易" : model.volumePcr <= 0.9 ? "偏多交易" : "中性" : "資料不足"}</small></span>
            <span class="derivatives-market-state-metric"><b>${value(model.maxPain, (item) => formatAssetOptionWhole(item))}</b><small>Max Pain · ${Number.isFinite(model.maxPain) ? "到期中性參考" : "資料不足"}</small></span>
            <span class="derivatives-market-state-metric"><b>${signedWhole(model.institutionNet)}</b><small>Institution · ${derivativesSignalLabel(model.institutionNet, "偏多", "偏空", "中性")}</small></span>
            <span class="derivatives-market-state-metric derivatives-market-state-metric-risk"><b>${riskValue}</b><small>Risk Score · ${model.riskLabel}</small></span>
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
    if (!model || !model.available) return `<div class="derivatives-strategy-unavailable"><h4 class="derivatives-strategy-detail-title">${model?.name || "Strategy"} · 策略分析暫不可用</h4><p>策略分析暫不可用：${model?.reason || "缺少必要資料"}。不產生策略組合或損益判斷。</p></div>`;
    const metrics = model.metrics;
    const legs = model.legs.map((leg) => `<tr class="derivatives-strategy-leg"><td>${leg.side}</td><td>${leg.optionType === "call" ? "Call" : "Put"}</td><td>${strategyNumber(leg.strike)}</td><td>${escapeHtml(leg.expiry)}</td><td>${strategyNumber(leg.premium)}</td><td>${leg.quantity}</td></tr>`).join("");
    const maxProfit = strategyMoney(metrics.maxProfit, metrics.maxProfitLabel);
    const maxLoss = strategyMoney(metrics.maxLoss, metrics.maxLossLabel);
    const dteText = model.calendar ? `Near DTE ${model.nearDte} / Far DTE ${model.farDte}` : `DTE ${initDerivativesAnalyticsPage.strategyEngine.daysTo(model.legs[0].expiry)}`;
    return `<div class="derivatives-strategy-detail-title-row"><div><span class="chip chip-cyan">${model.label} · ${model.score}/100</span><h4 class="derivatives-strategy-detail-title">${model.name} · ${model.zh}</h4><p>${model.formula}</p></div><span class="derivatives-strategy-regime">${model.regime.direction} · ${model.regime.volatility}</span></div><div class="derivatives-strategy-leg-table-wrap"><table class="derivatives-strategy-leg-table"><thead><tr><th>Side</th><th>Type</th><th>Strike</th><th>Expiry</th><th>Premium</th><th>Qty/Ratio</th></tr></thead><tbody>${legs}</tbody></table></div><div class="derivatives-strategy-metrics"><span><b>${strategyNumber(metrics.netPremium)}</b><small>${metrics.netLabel}</small></span><span><b>${maxProfit}</b><small>Max Profit</small></span><span><b>${maxLoss}</b><small>Max Loss</small></span><span><b>${metrics.breakEven.length ? metrics.breakEven.map(strategyNumber).join(", ") : "--"}</b><small>Break-even</small></span><span><b>${metrics.riskReward}</b><small>Risk / Reward</small></span><span><b>${dteText}</b><small>Expiry / DTE</small></span></div><p class="derivatives-strategy-zones"><strong>Profit / Loss Zone：</strong>${metrics.zones}</p>${renderStrategyChart(model, currentSpot)}<div class="derivatives-strategy-score"><strong>Compatibility Score Breakdown</strong><span>Direction Fit ${model.breakdown.directionFit}</span><span>Volatility Fit ${model.breakdown.volatilityFit}</span><span>IV Fit ${model.breakdown.ivFit} · Historical IV Context = Unavailable</span><span>Price Structure Fit ${model.breakdown.priceStructureFit}</span><span>Time Fit ${model.breakdown.timeFit}</span><span>Liquidity Fit ${model.breakdown.liquidityFit}</span><span>Risk Penalty ${model.breakdown.riskPenalty}</span></div><p class="derivatives-strategy-warning">${model.warning}</p><p class="derivatives-strategy-invalidation"><strong>Invalidation：</strong>${model.invalidation}</p></div>`;
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
  const daysTo = (value) => { const parsed = dateValue(value); return parsed === null ? null : Math.ceil((parsed - todayUtc()) / 86400000); };
  const quotePremium = (quote) => {
    if (!quote || typeof quote !== "object") return null;
    for (const field of ["last", "settlement", "lastPrice"]) {
      const value = numeric(quote[field]);
      if (finite(value) && value > 0) return value;
    }
    const bid = numeric(quote.bid);
    const ask = numeric(quote.ask);
    return finite(bid) && finite(ask) && bid >= 0 && ask >= bid && ask > 0 ? (bid + ask) / 2 : null;
  };
  const liquidity = (quote) => {
    const volume = numeric(quote?.volume);
    const openInterest = numeric(quote?.openInterest);
    return finite(volume) && finite(openInterest) ? { verified: true, volume, openInterest } : { verified: false, volume, openInterest };
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
  const legFrom = (group, optionType, side, quantity, expiry) => {
    const quote = group?.[optionType];
    const premium = quotePremium(quote);
    if (!quote || !finite(premium) || premium <= 0) return { failure: `${optionType === "call" ? "Call" : "Put"} 權利金缺失` };
    const quoteLiquidity = liquidity(quote);
    if (!quoteLiquidity.verified) return { failure: `${optionType === "call" ? "Call" : "Put"} 流動性資料未驗證` };
    return { leg: { side, optionType, strike: group.strike, premium, quantity, expiry, volume: quoteLiquidity.volume, openInterest: quoteLiquidity.openInterest } };
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
      const result = legFrom(group, type, side, quantity, expiry);
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
      const nearResult = legFrom(selected.nearGroup, selected.type, "SELL", 1, near.expiryDate);
      const farResult = legFrom(selected.farGroup, selected.type, "BUY", 1, far.expiryDate);
      if (nearResult.failure || farResult.failure) return { failure: nearResult.failure || farResult.failure };
      return { legs: [nearResult.leg, farResult.leg], calendar: true, nearDte: daysTo(near.expiryDate), farDte: daysTo(far.expiryDate) };
    }
    return { failure: "策略合約未定義" };
  };
  const intrinsic = (leg, price) => leg.optionType === "call" ? Math.max(price - leg.strike, 0) : Math.max(leg.strike - price, 0);
  const payoff = (legs, price) => {
    if (!Array.isArray(legs) || !finite(price) || legs.length === 0) return null;
    return legs.reduce((total, leg) => {
      const qty = numeric(leg.quantity); const premium = numeric(leg.premium); const strike = numeric(leg.strike);
      if (!finite(qty) || qty <= 0 || !finite(premium) || premium <= 0 || !finite(strike)) return NaN;
      const value = intrinsic({ ...leg, strike }, price);
      return total + (leg.side === "BUY" ? qty * (value - premium) : qty * (premium - value));
    }, 0);
  };
  const netPremium = (legs) => legs.reduce((total, leg) => total + (leg.side === "BUY" ? 1 : -1) * leg.quantity * leg.premium, 0);
  const metrics = (legs, calendar = false) => {
    const debitCredit = netPremium(legs);
    if (calendar) return { netPremium: debitCredit, netLabel: debitCredit >= 0 ? "Net Debit" : "Net Credit", exactPayoffAvailable: false, maxProfit: null, maxLoss: null, maxProfitLabel: "Model Dependent / Not Available", maxLossLabel: "Model Dependent / Not Available", breakEven: [], zones: "Model Dependent / Not Available", riskReward: "Model Dependent / Not Available" };
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
    return { netPremium: debitCredit, netLabel: debitCredit >= 0 ? "Net Debit" : "Net Credit", exactPayoffAvailable: true, maxProfit, maxLoss, maxProfitLabel: profitUnbounded ? "Unlimited upside" : "", maxLossLabel: lossUnbounded ? "Theoretical unlimited" : "", breakEven: uniqueBe, zones: uniqueBe.length ? `損益臨界點 ${uniqueBe.map((value) => value.toFixed(2)).join(", ")}` : "目前模型範圍內無損益臨界點", riskReward: finite(maxProfit) && finite(maxLoss) && maxLoss < 0 ? (maxProfit / Math.abs(maxLoss)).toFixed(2) : "N/A" };
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
    const liquidityFit = model.legs.every((leg) => leg.volume >= 0 && leg.openInterest >= 0) ? 10 : 0;
    const dte = daysTo(model.legs[0].expiry); const timeFit = dte > 30 ? 10 : dte > 14 ? 8 : dte > 7 ? 5 : 3;
    const breakdown = { directionFit: directionFit(contract, marketRegime.direction), volatilityFit: volatilityFit(contract, marketRegime.volatility), ivFit: marketRegime.ivState === "Unavailable" ? 0 : marketRegime.ivState === "Normal" ? 10 : marketRegime.ivState === "Low" ? 12 : 7, priceStructureFit: finite(numeric(market.spot)) ? 18 : 0, timeFit, liquidityFit, riskPenalty: riskPenalty(contract) };
    const score = Math.max(0, Math.min(100, Object.values(breakdown).reduce((sum, value) => sum + value, 0)));
    const label = score >= 80 ? "高相容" : score >= 60 ? "相容" : score >= 40 ? "中性" : score >= 20 ? "低相容" : "不相容";
    return { score, label, breakdown };
  };
  const analyze = (market = {}) => {
    const currentRegime = regime(market);
    return CONTRACTS.map((contract) => {
      const selection = makeLegs(contract, market);
      if (selection.failure) return { ...contract, available: false, reason: selection.failure, score: null, label: "不相容", regime: currentRegime };
      const contractMetrics = metrics(selection.legs, selection.calendar);
      const scored = scoreModel(contract, { legs: selection.legs }, currentRegime, market);
      const warning = ["short-straddle", "short-strangle"].includes(contract.id) ? "高尾部風險；跳空、保證金、指派／結算風險需另行確認。Margin Requirement = Unavailable。" : "不代表獲利保證；到期前價格、波動率與流動性變化可能使結果失效。";
      const invalidation = contract.bias === "bullish" ? "現貨跌破選定結構的關鍵支撐或多頭方向假設失效。" : contract.bias === "bearish" ? "現貨突破選定結構的關鍵壓力或空頭方向假設失效。" : contract.vol === "expansion" ? "實現波動率未擴張、權利金時間價值流失或突破假設失效。" : "現貨大幅脫離結構區間、波動率／期限結構改變或流動性惡化。";
      return { ...contract, available: true, legs: selection.legs, calendar: Boolean(selection.calendar), nearDte: selection.nearDte, farDte: selection.farDte, metrics: contractMetrics, score: scored.score, label: scored.label, breakdown: scored.breakdown, regime: currentRegime, warning, invalidation };
    });
  };
  const chartPoints = (model, spot) => {
    if (!model?.available || model.calendar) return [];
    const strikes = model.legs.map((leg) => leg.strike); const maxStrike = Math.max(...strikes, spot || 0); const upper = Math.max(maxStrike * 1.25, (spot || 0) * 1.25, maxStrike + 1);
    return Array.from({ length: 25 }, (_, index) => { const price = upper * index / 24; return { price, payoff: payoff(model.legs, price) }; });
  };
  return { contracts: CONTRACTS, analyze, payoff, metrics, chartPoints, daysTo };
})();
function renderDerivativeAiReport(title, analysis = {}, error = "", id = "") {
  const idAttr = id ? ` id="${escapeHtml(id)}"` : "";
  if (error) return `<article class="panel-card"${idAttr}><h3>${escapeHtml(title)}</h3><p class="stock-detail-empty">AI 分析資料暫不可用：${escapeHtml(error)}</p></article>`;
  const scenarios = Array.isArray(analysis.scenarios) ? analysis.scenarios : [];
  const crossValidation = Array.isArray(analysis.crossValidation) ? analysis.crossValidation : [];
  return `
    <article class="panel-card tw-option-ai-card"${idAttr}>
      <div class="asset-hub-group-heading"><div><p class="panel-kicker">AI analysis</p><h3>${escapeHtml(title)}</h3></div><span>風險 ${escapeHtml(analysis.riskLevel || "--")}</span></div>
      <div class="tw-option-ai-main"><strong>${escapeHtml(analysis.bias || "資料不足")}</strong><p>${escapeHtml((analysis.reasons || [])[0] || "尚無足夠資料說明方向。")}</p></div>
      <div class="asset-option-chain-stats"><span><b>${formatAssetOptionNumber(analysis.supportLevel)}</b><small>支撐</small></span><span><b>${formatAssetOptionNumber(analysis.resistanceLevel)}</b><small>壓力</small></span><span><b>${escapeHtml(analysis.riskLevel || "--")}</b><small>風險等級</small></span><span><b>${Number.isFinite(Number(analysis.marketScore)) ? Number(analysis.marketScore).toFixed(0) : "--"}</b><small>市場分數</small></span><span><b>${Number.isFinite(Number(analysis.riskScore)) ? Number(analysis.riskScore).toFixed(0) : "--"}</b><small>風險分數</small></span><span><b>${Number.isFinite(Number(analysis.confidenceScore)) ? Number(analysis.confidenceScore).toFixed(0) : "--"}</b><small>AI 信心</small></span></div>
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
