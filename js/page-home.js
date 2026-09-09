function formatSectorFundFlowAmount(value, signed = true) {
  const amount = parseMarketNumber(value);
  if (!Number.isFinite(amount)) return "--";
  const hundredMillions = amount / 100000000;
  const prefix = signed && hundredMillions > 0 ? "+" : "";
  return `${prefix}${hundredMillions.toLocaleString("zh-TW", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })} 億`;
}
function formatSectorFundFlowPct(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  const prefix = parsed > 0 ? "+" : "";
  return `${prefix}${parsed.toFixed(2)}%`;
}
function sectorFundFlowTone(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed) || parsed === 0) return "flat";
  return parsed > 0 ? "up" : "down";
}
function getSectorFundFlowRows(payload, mode) {
  const rows = Array.isArray(payload?.rows) ? payload.rows : [];
  if (mode === "inflow") {
    const inflows = Array.isArray(payload?.inflows) ? payload.inflows : [];
    return inflows.length ? inflows : rows.filter((item) => (parseMarketNumber(item.netAmountValue) || 0) > 0);
  }
  if (mode === "outflow") {
    const outflows = Array.isArray(payload?.outflows) ? payload.outflows : [];
    return outflows.length ? outflows : rows.filter((item) => (parseMarketNumber(item.netAmountValue) || 0) < 0);
  }
  return rows;
}
function renderSectorFundFlowMetric(label, value, tone = "flat") {
  return `
    <div class="sector-flow-metric">
      <span>${escapeHtml(label)}</span>
      <strong class="${toneClass(tone)}">${escapeHtml(value)}</strong>
    </div>
  `;
}
function renderSectorFundFlowRow(item) {
  const netAmount = parseMarketNumber(item.netAmountValue) || 0;
  const flowShare = Math.max(0, Math.min(100, parseMarketNumber(item.flowSharePct) || 0));
  const flowWidth = Math.max(4, flowShare);
  const topStocks = Array.isArray(item.topStocks) ? item.topStocks.slice(0, 3) : [];
  const directionText = netAmount >= 0 ? "流入" : "流出";
  return `
    <article class="sector-flow-row ${netAmount >= 0 ? "is-inflow" : "is-outflow"}">
      <div class="sector-flow-main">
        <div>
          <strong>${escapeHtml(item.name || "--")}</strong>
          <span>${escapeHtml(directionText)}占比 ${Number.isFinite(flowShare) ? flowShare.toFixed(1) : "--"}% · ${escapeHtml(String(item.stockCount ?? "--"))} 檔</span>
        </div>
        <b class="${toneClass(item.tone)}">${escapeHtml(formatSectorFundFlowAmount(item.netAmountValue, true))}</b>
      </div>
      <div class="sector-flow-bar" aria-hidden="true"><span style="--flow-width: ${flowWidth.toFixed(1)}%;"></span></div>
      <div class="sector-flow-breakdown">
        <span>外資 <b class="${toneClass(sectorFundFlowTone(item.foreignAmountValue))}">${escapeHtml(formatSectorFundFlowAmount(item.foreignAmountValue, true))}</b></span>
        <span>投信 <b class="${toneClass(sectorFundFlowTone(item.trustAmountValue))}">${escapeHtml(formatSectorFundFlowAmount(item.trustAmountValue, true))}</b></span>
        <span>自營商 <b class="${toneClass(sectorFundFlowTone(item.dealerAmountValue))}">${escapeHtml(formatSectorFundFlowAmount(item.dealerAmountValue, true))}</b></span>
        <span>均漲跌 <b class="${toneClass(sectorFundFlowTone(item.avgPctValue))}">${escapeHtml(formatSectorFundFlowPct(item.avgPctValue))}</b></span>
      </div>
      <div class="sector-flow-stocks">
        ${topStocks.map((stock) => `
          <span class="sector-flow-stock">
            <span>${escapeHtml(stock.code || "")} ${escapeHtml(stock.name || "")}</span>
            <strong class="${toneClass(stock.tone)}">${escapeHtml(formatSectorFundFlowAmount(stock.netAmountValue, true))}</strong>
          </span>
        `).join("") || '<span class="sector-flow-stock is-empty">個股貢獻同步中</span>'}
      </div>
    </article>
  `;
}
function renderSectorFundFlow() {
  const container = document.getElementById("sector-fund-flow");
  if (!container) return;

  const payload = data?.sectorFundFlow || {};
  const rows = Array.isArray(payload.rows) ? payload.rows : [];
  const modeOptions = [
    ["inflow", "流入"],
    ["outflow", "流出"],
    ["all", "全部"],
  ];
  if (!modeOptions.some(([key]) => key === sectorFundFlowState.mode)) {
    sectorFundFlowState.mode = "inflow";
  }

  if (!rows.length || payload.available === false) {
    container.innerHTML = `
      <div class="sector-flow-head">
        <div>
          <p class="panel-kicker">Fund flow</p>
          <h3>資金流向類股</h3>
        </div>
        <span class="chip chip-blue">${escapeHtml(payload.date || data?.institutionDate || "同步中")}</span>
      </div>
      <p class="stock-detail-empty">${escapeHtml(payload.sourceNote || "上市類股法人資金流向同步中。")}</p>
    `;
    return;
  }

  const activeRows = getSectorFundFlowRows(payload, sectorFundFlowState.mode);
  const topInflow = (Array.isArray(payload.inflows) ? payload.inflows : [])[0];
  const topOutflow = (Array.isArray(payload.outflows) ? payload.outflows : [])[0];
  container.innerHTML = `
    <div class="sector-flow-head">
      <div>
        <p class="panel-kicker">Fund flow</p>
        <h3>資金流向類股</h3>
      </div>
      <span class="chip chip-blue">${escapeHtml(payload.date || data?.institutionDate || "--")}</span>
    </div>
    <div class="sector-flow-summary">
      ${renderSectorFundFlowMetric("最強流入", topInflow ? `${topInflow.name} ${formatSectorFundFlowAmount(topInflow.netAmountValue, true)}` : "--", "up")}
      ${renderSectorFundFlowMetric("最強流出", topOutflow ? `${topOutflow.name} ${formatSectorFundFlowAmount(topOutflow.netAmountValue, true)}` : "--", "down")}
      ${renderSectorFundFlowMetric("合計淨流", formatSectorFundFlowAmount(payload.netTotalValue, true), sectorFundFlowTone(payload.netTotalValue))}
      ${renderSectorFundFlowMetric("覆蓋股票", `${payload.coveredStockCount || rows.reduce((sum, item) => sum + (parseMarketNumber(item.stockCount) || 0), 0)} 檔`, "flat")}
    </div>
    <div class="sector-flow-tabs" aria-label="資金流向切換">
      ${modeOptions.map(([key, label]) => `
        <button class="class-tab ${sectorFundFlowState.mode === key ? "is-active" : ""}" type="button" data-sector-flow-mode="${key}">
          ${label}
        </button>
      `).join("")}
    </div>
    <div class="sector-flow-list" tabindex="0" role="region" aria-label="資金流向類股清單">
      ${activeRows.map(renderSectorFundFlowRow).join("") || '<p class="stock-detail-empty">目前沒有符合條件的類股資金流資料。</p>'}
    </div>
    <p class="sector-flow-note">${escapeHtml(payload.sourceNote || "以法人買賣超股數乘以收盤價估算。")}</p>
  `;

  container.querySelectorAll("[data-sector-flow-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      sectorFundFlowState.mode = button.dataset.sectorFlowMode || "inflow";
      renderSectorFundFlow();
    });
  });
}
function buildInstitutionSummaryFromRows(institutions) {
  const visibleInstitutions = (institutions || []).filter((item) => item.name !== "外資自營商");
  const groups = [
    { key: "foreign", name: "外資", matches: (label) => label.startsWith("外資") },
    { key: "dealer", name: "自營商", matches: (label) => label.startsWith("自營商") },
    { key: "trust", name: "投信", matches: (label) => label === "投信" },
  ];
  return groups.map((group) => {
    const matched = visibleInstitutions.filter((item) => group.matches(String(item.name || "")));
    if (!matched.length) return null;
    const sum = (field, fallbackField) => matched.reduce(
      (total, item) => total + (parseMarketNumber(item[field] ?? item[fallbackField]) || 0),
      0,
    );
    const buyValue = sum("buyValue", "buy");
    const sellValue = sum("sellValue", "sell");
    const diffValue = sum("diffValue", "diff");
    return {
      key: group.key,
      name: group.name,
      buyValue,
      sellValue,
      diffValue,
      tone: diffValue > 0 ? "up" : diffValue < 0 ? "down" : "flat",
    };
  }).filter(Boolean);
}
function buildSectorCategoryUrl(groupKey, categoryName) {
  const category = String(categoryName || "").trim();
  const params = new URLSearchParams({ group: groupKey || "listed", category });
  return `tw-stocks.html?${params.toString()}#class-hero-card`;
}
function renderSectorCategoryLink(sector, groupKey) {
  const name = String(sector?.name || sector?.sourceName || "--");
  return `<a class="class-name-cell class-stock-link" href="${safeUrl(buildSectorCategoryUrl(groupKey, name))}" title="查看 ${escapeHtml(name)} 類股成分股排行">${escapeHtml(name)}</a>`;
}
function renderMarketSectorRankingName(sector, groupKey) {
  return ["listed", "otc"].includes(groupKey)
    ? renderSectorCategoryLink(sector, groupKey)
    : renderSectorStockName(sector);
}
function renderMarketSectorRankingTable(items, groupKey) {
  return `
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
          (sector) => `
        <article class="class-table-row" id="${escapeHtml(`market-sector-${sector.sourceName || sector.name}`)}">
          ${renderMarketSectorRankingName(sector, groupKey)}
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
    `, "大盤類股排行表格")}
  `;
}
function renderMarketSectorRankingTabs(activeKey) {
  const tabs = [
    ["listed", "上市類股"],
    ["otc", "上櫃類股"],
    ["emerging", "興櫃類股"],
  ];
  return `
    <div class="market-sector-ranking-tabs" aria-label="類股排行市場切換">
      ${tabs.map(([key, label]) => `
        <button class="class-tab ${key === activeKey ? "is-active" : ""}" type="button" data-market-sector-ranking-group="${key}">
          ${label}
        </button>
      `).join("")}
    </div>
  `;
}
function renderMarketListedSectorRanking() {
  const container = document.getElementById("market-sector-ranking");
  if (!container) return;
  const availableKeys = new Set(["listed", "otc", "emerging"]);
  const activeKey = availableKeys.has(marketSectorRankingState.groupKey) ? marketSectorRankingState.groupKey : "listed";
  const groups = getSectorPageGroups().filter((group) => availableKeys.has(group.key));
  const activeGroup = groups.find((group) => group.key === activeKey) || groups[0];
  marketSectorRankingState.groupKey = activeGroup?.key || "listed";
  const items = sortSectorItemsByActiveMode((activeGroup?.items || []).map((item) => ({ ...item, hideTrades: true })));
  if (!items.length) {
    container.innerHTML = `
      <div class="class-board-head">
        <div>
          <p class="eyebrow">族群走勢</p>
          <h3>${escapeHtml(activeGroup?.label || "類股")}排行</h3>
        </div>
      </div>
      ${renderMarketSectorRankingTabs(marketSectorRankingState.groupKey)}
      <p class="stock-detail-empty">${escapeHtml(activeGroup?.label || "類股")}資料同步中。</p>
    `;
    container.querySelectorAll("[data-market-sector-ranking-group]").forEach((button) => {
      button.addEventListener("click", () => {
        marketSectorRankingState.groupKey = button.dataset.marketSectorRankingGroup || "listed";
        renderMarketListedSectorRanking();
      });
    });
    return;
  }
  container.innerHTML = `
    <div class="class-board-head">
      <div>
        <p class="eyebrow">族群走勢</p>
        <h3>${escapeHtml(activeGroup.label)}排行</h3>
      </div>
      <div class="sector-sort-slot">${renderSectorSortControl()}</div>
    </div>
    ${renderMarketSectorRankingTabs(activeGroup.key)}
    <div class="class-table">${renderMarketSectorRankingTable(items, activeGroup.key)}</div>
  `;
  container.querySelectorAll("[data-market-sector-ranking-group]").forEach((button) => {
    button.addEventListener("click", () => {
      marketSectorRankingState.groupKey = button.dataset.marketSectorRankingGroup || "listed";
      renderMarketListedSectorRanking();
    });
  });
  container.querySelector("[data-sector-sort]")?.addEventListener("change", (event) => {
    sectorSortState.key = event.target.value || "source_order";
    renderMarketListedSectorRanking();
  });
}
function formatUpdateText(snapshotDate, cachedAt) {
  const parts = ["證交所資料已更新"];
  if (snapshotDate) parts.push(`日期：${snapshotDate}`);
  if (cachedAt) parts.push(`快取時間：${cachedAt}`);
  return parts.join(" | ");
}
(() => {
  const selectionFunnelState = window.__selectionFunnelState || (window.__selectionFunnelState = { market: "TWSE", sectorName: "" });
  function buildSelectionFunnelAdapter(payload, marketDecision = null) {
  const sectorFundFlow = payload?.sectorFundFlow;
  const rankedSectors = Array.isArray(sectorFundFlow?.inflows) ? sectorFundFlow.inflows : [];
  const marketEvidence = marketDecision && typeof marketDecision === "object" ? marketDecision : null;
  const market = {
    identity: "TWSE",
    name: "台灣上市",
    rank: null,
    score: null,
    reason: marketEvidence?.summary || null,
    risk: marketEvidence?.temperature?.value ?? null,
    freshness: marketEvidence?.freshness?.status || null,
    confidence: marketEvidence?.confidence || null,
    source: "既有市場決策與上市類股法人資金流",
  };
  const sectors = rankedSectors
    .filter((sector) => Array.isArray(sector?.pennyStocks) && sector.pennyStocks.length)
    .map((sector, index) => ({
      identity: String(sector.name || ""),
      name: String(sector.name || "--"),
      market: market.identity,
      rank: index + 1,
      score: sector.netAmountValue ?? null,
      scoreLabel: sector.netAmount || null,
      reason: "既有法人淨流入類股排序",
      risk: null,
      freshness: sectorFundFlow?.date || null,
      confidence: null,
      source: "sectorFundFlow.inflows",
      candidates: sector.pennyStocks,
    }));
  const selectedSector = sectors.find((sector) => sector.identity === selectionFunnelState.sectorName) || sectors[0] || null;
  if (selectedSector) selectionFunnelState.sectorName = selectedSector.identity;
  const candidates = (selectedSector?.candidates || [])
    .filter((stock) => String(stock?.code || "").trim())
    .slice(0, 10)
    .map((stock, index) => ({
    identity: String(stock.code || ""),
    symbol: String(stock.code || ""),
    name: String(stock.name || "--"),
    market: market.identity,
    sector: selectedSector?.name || null,
    rank: index + 1,
    score: stock.score ?? null,
    reason: "既有銅板股排序",
    risk: null,
    freshness: sectorFundFlow?.date || null,
    confidence: null,
    source: "sectorFundFlow.pennyStocks",
    pct: stock.pct || null,
      close: stock.close || null,
    }));
  return {
    available: Boolean(marketEvidence && rankedSectors.length && selectedSector && candidates.length),
    market,
    sectors,
    selectedSector,
    candidates,
    source: "sectorFundFlow",
  };
}
window.buildSelectionFunnelAdapter = buildSelectionFunnelAdapter;
  function buildSelectionFunnelStockUrl(candidate) {
  const params = new URLSearchParams({
    q: candidate.symbol,
    market: candidate.market,
    selectionSource: candidate.source,
    selectionSector: candidate.sector || "",
    selectionRank: String(candidate.rank),
    selectionReason: candidate.reason,
  });
  return `tw-stock-search.html?${params.toString()}`;
}
  function renderSelectionFunnel() {
  const root = document.getElementById("selection-funnel-root");
  if (!root) return;
  const decision = typeof window.buildSharedMarketDecisionModel === "function"
    ? window.buildSharedMarketDecisionModel()
    : null;
  const model = buildSelectionFunnelAdapter(data, decision);
  if (!model.available) {
    root.innerHTML = '<article class="panel-card"><p class="stock-detail-empty">必要的既有市場決策、類股資金流或候選排序尚未齊備；依規則暫不產生 TOP10。</p></article>';
    return;
  }
  const selected = model.selectedSector;
  root.innerHTML = `
    <div class="tri-grid">
      <article class="panel-card">
        <div class="card-title-row"><h3>1. 市場</h3><span class="chip chip-blue">既有 A 證據</span></div>
        <p><strong>${escapeHtml(model.market.name)}</strong> · ${escapeHtml(model.market.freshness || "--")}</p>
        <p class="card-copy">${escapeHtml(model.market.reason || "既有市場決策資料不足")}</p>
      </article>
      <article class="panel-card">
        <div class="card-title-row"><h3>2. 類股</h3><span class="chip chip-green">既有淨流入排序</span></div>
        <div class="mini-list">
          ${model.sectors.slice(0, 10).map((sector) => `<button class="mini-row ${sector.identity === selected.identity ? "is-active" : ""}" type="button" data-selection-sector="${escapeHtml(sector.identity)}"><span><b>${sector.rank}.</b> ${escapeHtml(sector.name)}</span><strong>${escapeHtml(sector.scoreLabel || "--")}</strong></button>`).join("")}
        </div>
      </article>
      <article class="panel-card">
        <div class="card-title-row"><h3>3. TOP10</h3><span class="chip chip-gold">${model.candidates.length} 檔</span></div>
        <div class="mini-list">
          ${model.candidates.map((candidate) => `<a class="mini-row" href="${safeUrl(buildSelectionFunnelStockUrl(candidate))}"><span><b>${candidate.rank}.</b> ${escapeHtml(candidate.symbol)} ${escapeHtml(candidate.name)}</span><strong>評分 ${escapeHtml(String(candidate.score ?? "--"))}</strong></a>`).join("")}
        </div>
        <p class="source-note">${escapeHtml(selected.name)} · ${escapeHtml(selected.scoreLabel || "--")} · 分數與排序均沿用既有資料。</p>
      </article>
    </div>
  `;
  root.querySelectorAll("[data-selection-sector]").forEach((button) => {
    button.addEventListener("click", () => {
      selectionFunnelState.sectorName = button.dataset.selectionSector || "";
      renderSelectionFunnel();
    });
  });
}
window.renderSelectionFunnel = renderSelectionFunnel;
})();
function renderHomePennyTrend() {
  const root = document.getElementById("penny-trend-grid");
  const controls = document.getElementById("penny-trend-controls");
  const summary = document.getElementById("penny-trend-summary");
  if (!root) return;
  const markets = Array.isArray(homePennySectorPayload?.markets) ? homePennySectorPayload.markets : [];
  if (!markets.length) {
    root.innerHTML = '<article class="panel-card"><p class="stock-detail-empty">正在整理上市、上櫃、興櫃全部類股成分股...</p></article>';
    if (controls) controls.innerHTML = "";
    return;
  }
  const activeMarket = markets.find((market) => market.key === homePennySectorMarket) || markets[0];
  homePennySectorMarket = activeMarket.key;
  if (controls) {
    controls.innerHTML = markets.map((market) => `
      <button class="class-tab ${market.key === activeMarket.key ? "is-active" : ""}" type="button" data-home-penny-market="${escapeHtml(market.key)}">
        ${escapeHtml(market.label)} <small>${Number(market.availableSectorCount || 0).toLocaleString("zh-TW")} 類</small>
      </button>
    `).join("");
    controls.querySelectorAll("[data-home-penny-market]").forEach((button) => {
      button.addEventListener("click", () => {
        homePennySectorMarket = button.dataset.homePennyMarket || "listed";
        renderHomePennyTrend();
      });
    });
  }
  if (summary) {
    summary.textContent = `${activeMarket.label}目錄 ${Number(activeMarket.catalogCount || 0).toLocaleString("zh-TW")} 類；已整理 ${Number(activeMarket.sectorCount || 0).toLocaleString("zh-TW")} 類，其中 ${Number(activeMarket.availableSectorCount || 0).toLocaleString("zh-TW")} 類有 50 元以下成分股，共 ${Number(activeMarket.pennyStockCount || 0).toLocaleString("zh-TW")} 檔次。更新時間 ${homePennySectorPayload.updatedAt || "--"}`;
  }
  const sectors = Array.isArray(activeMarket.sectors) ? activeMarket.sectors : [];
  root.innerHTML = sectors.map((sector, sectorIndex) => {
    const stocks = Array.isArray(sector.pennyStocks) ? sector.pennyStocks.slice(0, 5) : [];
    return `
      <article class="panel-card penny-trend-card penny-trend-sector-card ${stocks.length ? "" : "is-empty"}">
        <span class="penny-trend-rank">${sectorIndex + 1}</span>
        <div class="penny-trend-main">
          <span class="penny-sector-label">${escapeHtml(activeMarket.label)}類股</span>
          <strong>${escapeHtml(sector.name || "--")}</strong>
          <p>成分股 ${Number(sector.stockCount || 0).toLocaleString("zh-TW")} 檔 · 銅板股 ${Number(sector.pennyStockCount || 0).toLocaleString("zh-TW")} 檔</p>
        </div>
        <div class="penny-trend-top-list">
          ${stocks.length ? stocks.map((stock, stockIndex) => `
            <a class="penny-trend-top-row" href="${safeUrl(`tw-stock-search.html?code=${encodeURIComponent(stock.code || "")}&market=${encodeURIComponent(stock.market || "")}`)}" title="查看 ${escapeHtml(stock.code || "")} ${escapeHtml(stock.name || "")} 個股資料">
              <span class="penny-trend-top-rank">${stockIndex + 1}</span>
              <span class="penny-trend-top-identity"><b class="penny-trend-top-code">${escapeHtml(stock.code || "--")}</b><span class="penny-trend-top-name">${escapeHtml(stock.name || "--")}</span></span>
              <span class="penny-trend-top-price">${escapeHtml(stock.close || "--")} 元</span>
              <span class="penny-trend-top-pct ${toneClass(stock.tone)}">${escapeHtml(stock.pct || "--")}</span>
              <span class="penny-trend-top-score">評分 ${escapeHtml(String(stock.score ?? "--"))}</span>
            </a>
          `).join("") : '<p class="stock-detail-empty">此類股目前沒有 50 元以下成分股。</p>'}
        </div>
      </article>
    `;
  }).join("") || '<article class="panel-card"><p class="stock-detail-empty">此市場類股資料暫時無法取得。</p></article>';
}
function loadHomePennySectorRecommendations() {
  if (!document.getElementById("penny-trend-grid") || homePennySectorPayload || homePennySectorPromise) return;
  homePennySectorPromise = fetchWithTimeout(
    "/api/market/penny-sector-recommendations",
    { cache: "no-store" },
    120000,
  )
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      homePennySectorPayload = payload;
      renderHomePennyTrend();
    })
    .catch((error) => {
      const root = document.getElementById("penny-trend-grid");
      if (root) root.innerHTML = `<article class="panel-card"><p class="stock-detail-empty">三市場類股成分股同步失敗：${escapeHtml(error.message || String(error))}</p></article>`;
    })
    .finally(() => {
      homePennySectorPromise = null;
    });
}
window.buildSharedMarketDecisionModel = function () {
  const payload = data && typeof data === "object" ? data : {};
  const overviewRows = Array.isArray(payload.marketOverview) ? payload.marketOverview : [];
  const overview = overviewRows.find((item) => item && (item.value || item.pct)) || null;
  const sectors = (Array.isArray(payload.sectors) ? payload.sectors : [])
    .filter((item) => item && item.name !== "台灣加權指數" && !isExcludedSector(item))
    .map((item) => ({ ...item, pctValue: parseMarketNumber(item.pct) }))
    .filter((item) => Number.isFinite(item.pctValue));
  const institutions = Array.isArray(payload.institutions) ? payload.institutions : [];
  const institutionSummary = Array.isArray(payload.institutionSummary) ? payload.institutionSummary : [];
  const hasInstitutions = institutions.length > 0 || institutionSummary.length > 0;
  const hasBreadth = sectors.length >= 3;
  const hasCoreEvidence = Boolean(overview && hasBreadth && hasInstitutions);
  const freshness = window.buildSharedFreshnessConfidenceModel(payload, {
    requirePrimary: true,
    hasDecisionEvidence: hasCoreEvidence,
  });
  const hasFreshDecisionEvidence = hasCoreEvidence && freshness.status === "Fresh";

  let insight = null;
  let risk = null;
  let tomorrow = null;
  if (hasCoreEvidence) {
    try { insight = buildMarketAiInsightModel(); } catch (error) { console.warn("Decision insight unavailable", error); }
    try { risk = buildMarketRiskAdvice(); } catch (error) { console.warn("Decision risk unavailable", error); }
    try { tomorrow = buildAfterMarketWatchCard(); } catch (error) { console.warn("Decision watch unavailable", error); }
  }
  const ranked = [...sectors].sort((left, right) => right.pctValue - left.pctValue);
  const leaders = ranked.slice(0, 3).map((item) => ({ name: item.name, pct: item.pct || "--" }));
  const laggards = [...ranked].reverse().slice(0, 3).map((item) => ({ name: item.name, pct: item.pct || "--" }));
  const confidence = hasFreshDecisionEvidence
    ? freshness.confidence
    : { label: "不足", detail: "核心證據未齊或資料不是 Fresh，禁止產生高信心方向結論。" };
  const decision = insight && hasFreshDecisionEvidence
    ? insight.trendLabel
    : "暫不下方向結論";
  const reasons = insight && hasFreshDecisionEvidence
    ? [insight.trendSummary, `市場廣度：${insight.breadthText}`, `法人方向：${insight.institutionText}`, `波動背景：${insight.vixText}`]
    : ["資料不是 Fresh 或核心證據不足，等待來源更新後重新評估。"];
  const risks = risk && hasFreshDecisionEvidence
    ? risk.factors.map((text) => ({ text, source: "既有市場風險因子" }))
    : [{ text: "核心資料不足或已延遲，暫不下方向性風險結論。", source: "資料完整性閘門" }];
  const strategy = risk && hasFreshDecisionEvidence
    ? { advice: risk.actions, next: tomorrow ? [tomorrow.body] : ["等待量能、法人與族群輪動同向確認。"] }
    : { advice: ["資料狀態不是 Fresh，暫不使用方向性策略分類。"], next: ["待加權指數、廣度與法人資料齊全且新鮮後重新評估。"] };
  const temperatureValue = insight && hasCoreEvidence && Number.isFinite(Number(insight.riskScore)) ? Number(insight.riskScore) : null;
  const evidence = [
    { label: "市場狀態", value: decision, source: "既有市場趨勢與廣度邏輯", asOf: freshness.asOf, status: freshness.status },
    { label: "市場風險分數", value: temperatureValue === null ? "未評定" : `${temperatureValue}/100`, source: "既有 market risk score；數值越高代表風險越高", asOf: freshness.asOf, status: freshness.status },
    { label: "組裝時間", value: payload.cachedAt || "--", source: "伺服器組裝時間，非行情來源時間", asOf: payload.cachedAt || "--", status: "Evidence" },
  ];
  return {
    decision,
    summary: insight?.trendSummary || "目前沒有足夠資料整理市場狀態。",
    confidence,
    freshness,
    asOf: freshness.asOf,
    updatedAt: freshness.updatedAt,
    temperature: { value: temperatureValue, label: "既有市場風險分數", detail: "此數值維持既有語義；越高代表風險越高，不是溫度或報酬預測。" },
    reasons,
    risks,
    strategy,
    invalidation: tomorrow && hasFreshDecisionEvidence ? [tomorrow.title, tomorrow.body] : ["核心資料更新或來源日期變動後重新評估。"],
    leaders,
    laggards,
    evidence,
    limitations: ["資料新鮮度與分析信心分開呈現。", "本區不新增評分、推薦或個人化投資建議。"],
  };
};
function renderHome() {
  setText("source-note", formatUpdateText(data.snapshotDate, data.cachedAt));
  if (data.marketOverview?.length) {
    setText("hero-index", `${data.marketOverview[0].value} ${data.marketOverview[0].pct}`);
  }
  const heroMetrics = document.getElementById("hero-metrics");
  if (heroMetrics) {
    heroMetrics.innerHTML = `
      <div class="metric-pill">
        <span>法人動向</span>
        <strong class="${toneClass(data.institutions?.[0]?.tone)}">${data.institutions?.[0]?.diff || "--"}</strong>
      </div>
      <div class="metric-pill">
        <span>族群表現</span>
        <strong class="${toneClass(data.sectors?.[0]?.tone)}">${data.sectors?.[0]?.pct || "--"}</strong>
      </div>
      <div class="metric-pill">
        <span>上市股票數</span>
        <strong>${data.stockCount || "--"}</strong>
      </div>
    `;
  }

  const fundamentals = document.getElementById("fundamental-cards");
  if (fundamentals) {
    fundamentals.innerHTML = (data.marketOverview || []).map((item) => `
      <div class="mini-item">
        <span>${item.name}</span>
        <strong>${item.value}</strong>
      </div>
    `).join("");
  }

  const chips = document.getElementById("chip-cards");
  if (chips) {
    chips.innerHTML = (data.institutions || []).slice(0, 4).map((item) => `
      <div class="mini-item">
        <span>${item.name}</span>
        <strong class="${toneClass(item.tone)}">${item.diff}</strong>
      </div>
    `).join("");
  }

  const technicals = document.getElementById("technical-cards");
  if (technicals) {
    technicals.innerHTML = (data.sectors || []).slice(0, 4).map((sector) => `
      <div class="mini-item">
        <span>${sector.name}</span>
        <strong class="${toneClass(sector.tone)}">${sector.pct}</strong>
      </div>
    `).join("");
  }
  renderHomePennyTrend();
  window.renderSelectionFunnel?.();
  loadHomePennySectorRecommendations();
  window.renderSharedMarketDecisionSummary(window.buildSharedMarketDecisionModel());
}
function buildMarketRiskAdvice() {
  const overview = data.marketOverview?.[0] || {};
  const indexPct = parseMarketNumber(overview.pct) || 0;
  const marketSector = (data.sectors || []).find((item) => item.name === "台灣加權指數")
    || data.sectors?.[0]
    || {};
  const candles = Array.isArray(marketSector.candles) ? marketSector.candles : [];
  const highs = candles.map((item) => parseMarketNumber(item.high)).filter(Number.isFinite);
  const lows = candles.map((item) => parseMarketNumber(item.low)).filter(Number.isFinite);
  const referenceClose = parseMarketNumber(overview.value) || parseMarketNumber(marketSector.value);
  const amplitude = highs.length && lows.length && referenceClose
    ? ((Math.max(...highs) - Math.min(...lows)) / referenceClose) * 100
    : 0;

  const sectorRows = (data.sectors || []).filter((item) => item.name !== "台灣加權指數");
  const decliningSectors = sectorRows.filter((item) => (parseMarketNumber(item.pct) || 0) < 0).length;
  const advancingSectors = sectorRows.filter((item) => (parseMarketNumber(item.pct) || 0) > 0).length;
  const breadthTotal = advancingSectors + decliningSectors;
  const declineRatio = breadthTotal ? decliningSectors / breadthTotal : 0.5;

  const institutionTotal = (data.institutions || []).find((item) => item.name === "合計");
  const institutionNet = parseMarketNumber(institutionTotal?.diffValue ?? institutionTotal?.diff)
    ?? (data.institutionSummary || []).reduce(
      (sum, item) => sum + (parseMarketNumber(item.diffValue) || 0),
      0,
    );

  let score = 0;
  const factors = [];
  if (Math.abs(indexPct) >= 2) score += 2;
  else if (Math.abs(indexPct) >= 1) score += 1;
  if (indexPct <= -1) factors.push(`加權指數下跌 ${Math.abs(indexPct).toFixed(2)}%，短線賣壓偏強。`);
  else if (indexPct >= 1) factors.push(`加權指數上漲 ${indexPct.toFixed(2)}%，仍需留意高檔追價風險。`);
  else factors.push(`加權指數漲跌 ${indexPct >= 0 ? "+" : ""}${indexPct.toFixed(2)}%，收盤方向尚未明顯失衡。`);

  if (amplitude >= 3) score += 2;
  else if (amplitude >= 2) score += 1;
  factors.push(amplitude
    ? `盤中振幅約 ${amplitude.toFixed(2)}%，${amplitude >= 2 ? "價格震盪較大。" : "波動仍在相對溫和區間。"}`
    : "盤中振幅資料不足，風險判讀以收盤與法人資料為主。");

  if (institutionNet <= -30000000000) score += 2;
  else if (institutionNet <= -10000000000) score += 1;
  else if (institutionNet >= 30000000000) score -= 1;
  factors.push(`三大法人合計${institutionNet >= 0 ? "買超" : "賣超"} ${formatInstitutionAmount(Math.abs(institutionNet))}。`);

  if (declineRatio >= 0.65) score += 2;
  else if (declineRatio >= 0.55) score += 1;
  else if (declineRatio <= 0.35) score -= 1;
  factors.push(`類股漲跌分布為 ${advancingSectors} 個上漲、${decliningSectors} 個下跌，市場廣度${declineRatio >= 0.6 ? "偏弱" : declineRatio <= 0.4 ? "偏強" : "分歧"}。`);

  const level = score >= 5
    ? { label: "高風險", tone: "high", summary: "波動與資金面風險同步升高，隔日應優先防守。" }
    : score >= 2
      ? { label: "中度風險", tone: "medium", summary: "多空訊號交錯，建議降低追價並等待方向確認。" }
      : { label: "低度風險", tone: "low", summary: "目前市場風險相對可控，但仍應依個股條件設定停損。" };

  const actions = level.tone === "high"
    ? ["降低單一持股與整體曝險，保留較高現金水位。", "弱勢股反彈不追價，跌破支撐應依原定紀律停損。", "等待指數止穩、量價改善及法人賣壓收斂後再分批布局。"]
    : level.tone === "medium"
      ? ["採分批進出，避免開盤波動時一次建立完整部位。", "以近期支撐或可承受損失設定停損，不任意向下放寬。", "優先選擇趨勢與成交量同步轉強的個股。"]
      : ["維持既定資金配置，避免因低風險評級過度集中持股。", "新部位仍應設定停損與合理風險報酬比。", "若法人轉賣或市場廣度惡化，應重新降低曝險。"];

  return { ...level, factors, actions };
}
function buildMarketThemeNewsCards() {
  const overviewRows = data.marketOverview || [];
  const overview = overviewRows[0] || {};
  const sectorRows = (data.sectors || []).filter((item) => item.name !== "台灣加權指數");
  const sectorsWithPct = sectorRows
    .map((item) => ({ ...item, pctValue: parseMarketNumber(item.pct) }))
    .filter((item) => Number.isFinite(item.pctValue));
  const ranked = [...sectorsWithPct].sort((left, right) => right.pctValue - left.pctValue);
  const strongest = ranked[0] || null;
  const weakest = ranked.length ? ranked[ranked.length - 1] : null;
  const advancing = sectorsWithPct.filter((item) => item.pctValue > 0).length;
  const declining = sectorsWithPct.filter((item) => item.pctValue < 0).length;
  const unchanged = sectorsWithPct.filter((item) => item.pctValue === 0).length;
  const breadthTotal = advancing + declining + unchanged;
  const breadthRatio = breadthTotal ? advancing / breadthTotal : 0.5;
  const breadthText = breadthRatio >= 0.6 ? "買盤擴散" : breadthRatio <= 0.4 ? "賣壓擴散" : "多空分歧";
  const breadthPercent = breadthTotal ? `${(breadthRatio * 100).toFixed(0)}%` : "--";
  const indexPct = parseMarketNumber(overview.pct);
  const marketDirection = Number.isFinite(indexPct) && indexPct >= 0.5
    ? "偏多續航"
    : Number.isFinite(indexPct) && indexPct >= 0
      ? "震盪偏穩"
      : Number.isFinite(indexPct) && indexPct <= -0.5
        ? "回測承壓"
        : "小幅整理";
  const turnover = parseMarketNumber(overview.turnoverValue ?? overview.turnover ?? data.marketStats?.turnoverValue ?? data.marketStats?.turnover);
  const volume = parseMarketNumber(overview.volumeValue ?? overview.volume ?? data.marketStats?.volumeValue ?? data.marketStats?.volume);
  const trades = parseMarketNumber(overview.tradeCount ?? overview.trades ?? data.marketStats?.tradeCount ?? data.marketStats?.trades);
  const turnoverText = Number.isFinite(turnover) ? `${(turnover / 100000000).toLocaleString("zh-TW", { maximumFractionDigits: 1, minimumFractionDigits: 1 })} 億元` : "--";
  const volumeText = Number.isFinite(volume) ? `${(volume / 100000000).toLocaleString("zh-TW", { maximumFractionDigits: 1, minimumFractionDigits: 1 })} 億股` : "--";
  const tradeText = Number.isFinite(trades) ? `${(trades / 10000).toLocaleString("zh-TW", { maximumFractionDigits: 1, minimumFractionDigits: 1 })} 萬筆` : "--";
  const sectorText = (item) => item ? `${item.name || "族群"} ${item.pct || "--"}` : "資料同步中";
  const topText = ranked.slice(0, 3).map(sectorText).join("、") || "強勢族群同步中";
  const weakText = [...ranked].reverse().slice(0, 3).map(sectorText).join("、") || "弱勢族群同步中";
  const spread = strongest && weakest ? strongest.pctValue - weakest.pctValue : null;
  const spreadText = Number.isFinite(spread) ? `${spread.toFixed(2)} 個百分點` : "--";
  const findIndexRow = (...keywords) => [...overviewRows, ...sectorsWithPct].find((item) => {
    const name = String(item.name || "");
    return keywords.every((keyword) => name.includes(keyword));
  });
  const electronic = findIndexRow("電子");
  const semiconductor = findIndexRow("半導體");
  const techContext = [
    electronic ? `電子 ${electronic.pct || "--"}` : "",
    semiconductor ? `半導體 ${semiconductor.pct || "--"}` : "",
  ].filter(Boolean).join("、") || "權值科技資料同步中";
  const institutionTotal = (data.institutions || []).find((item) => item.name === "合計");
  const institutionNet = parseMarketNumber(institutionTotal?.diffValue ?? institutionTotal?.diff)
    ?? (data.institutionSummary || []).reduce((sum, item) => sum + (parseMarketNumber(item.diffValue) || 0), 0);
  const foreign = (data.institutionSummary || []).find((item) => item.key === "foreign");
  const trust = (data.institutionSummary || []).find((item) => item.key === "trust");
  const dealer = (data.institutionSummary || []).find((item) => item.key === "dealer");
  const trendLabel = (key) => data.institutionTrend?.[key]?.label || "連續性待同步";
  const foreignValue = parseMarketNumber(foreign?.diffValue ?? foreign?.diff);
  const trustValue = parseMarketNumber(trust?.diffValue ?? trust?.diff);
  const institutionalPressure = Number.isFinite(foreignValue) && foreignValue < 0 && institutionNet < 0
    ? "外資主導調節"
    : Number.isFinite(foreignValue) && foreignValue > 0 && institutionNet > 0
      ? "外資帶動回補"
      : Number.isFinite(foreignValue) && Number.isFinite(trustValue) && foreignValue * trustValue < 0
        ? "法人結構分歧"
        : "資金面中性觀察";
  const netDirection = institutionNet >= 0 ? "買超" : "賣超";
  const netContext = institutionNet >= 0 ? "資金面對指數形成支撐" : "資金面仍偏向調節";
  const marketLink = data.sourceLinks?.market || "";
  const institutionLink = data.sourceLinks?.institutions || "";

  return [
    {
      tag: "大盤",
      title: `${data.snapshotDate || "--"} 加權指數 ${overview.value || "--"} 點，${marketDirection}但廣度${breadthText}`,
      body: `加權指數漲跌幅 ${overview.pct || "--"}、成交金額 ${turnoverText}、成交量 ${volumeText}，成交筆數約 ${tradeText}。${breadthTotal || "--"} 個追蹤類股中 ${advancing} 漲、${declining} 跌、${unchanged} 平，上漲占比 ${breadthPercent}，顯示盤勢不是只看指數點位，而要同步檢查買盤是否擴散。隔日若量能維持且強勢族群未快速退潮，盤勢較有機會延續；若指數守平盤但廣度轉弱，需防震盪整理。`,
      link: marketLink,
    },
    {
      tag: "指數",
      title: `${strongest?.name || "強勢族群"} 領先，${weakest?.name || "弱勢族群"} 落後，強弱差 ${spreadText}`,
      body: `領漲端為 ${topText}，落後端為 ${weakText}。權值科技同步觀察 ${techContext}，若科技權值偏弱但傳產或防禦族群走強，代表資金正在輪動而非全面追價。操作上可優先比對領先族群的成交金額與個股擴散度；若強弱差收斂，則表示輪動降溫，追高勝率會下降。`,
      link: marketLink,
    },
    {
      tag: "法人",
      title: `三大法人合計${netDirection} ${formatInstitutionAmount(Math.abs(institutionNet))}，${institutionalPressure}`,
      body: `外資 ${formatInstitutionAmount(foreign?.diffValue ?? foreign?.diff, true)}（${trendLabel("foreign")}）、投信 ${formatInstitutionAmount(trust?.diffValue ?? trust?.diff, true)}（${trendLabel("trust")}）、自營商 ${formatInstitutionAmount(dealer?.diffValue ?? dealer?.diff, true)}（${trendLabel("dealer")}）。目前${netContext}；若法人賣超集中在外資且指數仍小漲，代表內資與族群輪動正在吸收賣壓，隔日需追蹤外資賣超是否收斂，以及投信承接是否仍集中在強勢族群。`,
      link: institutionLink,
    },
  ];
}
function buildAfterMarketWatchCard() {
  const overview = data.marketOverview?.[0] || {};
  const indexPct = parseMarketNumber(overview.pct) || 0;
  const sectorRows = (data.sectors || []).filter((item) => item.name !== "台灣加權指數");
  const sectorsWithPct = sectorRows
    .map((item) => ({ ...item, pctValue: parseMarketNumber(item.pct) }))
    .filter((item) => Number.isFinite(item.pctValue));
  const strongest = sectorsWithPct.length
    ? sectorsWithPct.reduce((best, item) => (item.pctValue > best.pctValue ? item : best), sectorsWithPct[0])
    : null;
  const weakest = sectorsWithPct.length
    ? sectorsWithPct.reduce((worst, item) => (item.pctValue < worst.pctValue ? item : worst), sectorsWithPct[0])
    : null;
  const advancing = sectorsWithPct.filter((item) => item.pctValue > 0).length;
  const declining = sectorsWithPct.filter((item) => item.pctValue < 0).length;
  const unchanged = sectorsWithPct.filter((item) => item.pctValue === 0).length;
  const topSectors = [...sectorsWithPct].sort((left, right) => right.pctValue - left.pctValue).slice(0, 3);
  const weakSectors = [...sectorsWithPct].sort((left, right) => left.pctValue - right.pctValue).slice(0, 3);
  const institutionTotal = (data.institutions || []).find((item) => item.name === "合計");
  const institutionNet = parseMarketNumber(institutionTotal?.diffValue ?? institutionTotal?.diff)
    ?? (data.institutionSummary || []).reduce(
      (sum, item) => sum + (parseMarketNumber(item.diffValue) || 0),
      0,
    );
  const foreign = (data.institutionSummary || []).find((item) => item.key === "foreign")
    || (data.institutions || []).find((item) => String(item.name || "").startsWith("外資") && item.name !== "外資自營商");
  const trust = (data.institutionSummary || []).find((item) => item.key === "trust")
    || (data.institutions || []).find((item) => item.name === "投信");
  const dealer = (data.institutionSummary || []).find((item) => item.key === "dealer")
    || (data.institutions || []).find((item) => String(item.name || "").includes("自營商") && !String(item.name || "").includes("避險"));
  const netText = Number.isFinite(institutionNet)
    ? `三大法人合計${institutionNet >= 0 ? "買超" : "賣超"} ${formatInstitutionAmount(Math.abs(institutionNet))}`
    : "三大法人合計資料仍在同步";
  const breadthText = advancing || declining
    ? `類股廣度 ${advancing} 漲 / ${declining} 跌 / ${unchanged} 平`
    : "類股廣度資料不足";
  const breadthBias = advancing > declining * 1.25
    ? "多方擴散"
    : declining > advancing * 1.15
      ? "賣壓擴散"
      : "多空分歧";
  const leadText = strongest && weakest
    ? `${strongest.name} 領先、${weakest.name} 落後`
    : "等待族群強弱資料同步";
  const topText = topSectors.length ? topSectors.map((item) => `${item.name} ${item.pct}`).join("、") : "強勢族群同步中";
  const weakText = weakSectors.length ? weakSectors.map((item) => `${item.name} ${item.pct}`).join("、") : "弱勢族群同步中";
  const foreignText = foreign ? `外資 ${formatInstitutionAmount(foreign.diffValue ?? foreign.diff, true)}` : "外資待同步";
  const trustText = trust ? `投信 ${formatInstitutionAmount(trust.diffValue ?? trust.diff, true)}` : "投信待同步";
  const dealerText = dealer ? `自營商 ${formatInstitutionAmount(dealer.diffValue ?? dealer.diff, true)}` : "自營商待同步";
  const action = indexPct < -1 || declining > advancing
    ? "隔日先看弱勢族群是否止穩與法人賣壓是否收斂，反彈量縮時不急追價。"
    : indexPct > 1 || advancing > declining * 1.4
      ? "隔日留意強勢族群是否續量，若法人仍買超且開高不爆量，主線延續機率較高。"
      : "隔日等待量能、法人與族群輪動同向；若強弱族群快速互換，部位以短打與風控為主。";

  return {
    tag: "明日觀察",
    title: `觀察清單：${leadText}`,
    body: `${overview.value ? `加權指數 ${overview.value}，漲跌幅 ${overview.pct}，市場廣度呈現${breadthBias}。` : "加權指數資料同步中。"}${netText}，${foreignText}、${trustText}、${dealerText}。強勢端：${topText}；弱勢端：${weakText}。${breadthText}。${action}`,
  };
}
function formatInstitutionAmount(value, signed = false) {
  const amount = parseMarketNumber(value);
  if (!Number.isFinite(amount)) return "--";
  const hundredMillions = amount / 100000000;
  const prefix = signed && hundredMillions > 0 ? "+" : "";
  return `${prefix}${hundredMillions.toLocaleString("zh-TW", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} 億`;
}
function getVixSentiment(value) {
  if (!Number.isFinite(value)) {
    return {
      range: "--",
      mood: "資料同步中",
      meaning: "VIX 資料同步後，將依區間判斷市場情緒與對大盤的影響。",
      short: "--",
    };
  }
  if (value < 15) {
    return {
      range: "低於 15",
      mood: "非理性樂觀 / 樂觀",
      meaning: "大盤通常處於牛市或緩漲波段，但須留意市場過度樂觀，可能隱含賣壓風險。",
      short: "低於 15，非理性樂觀，留意賣壓風險",
    };
  }
  if (value < 20) {
    return {
      range: "15 ~ 20",
      mood: "常態區間 / 穩定",
      meaning: "市場預期變動不大，大盤走勢相對平穩，屬於健康的交易環境。",
      short: "15 ~ 20，常態穩定，交易環境健康",
    };
  }
  if (value < 30) {
    return {
      range: "20 ~ 30",
      mood: "警戒區間 / 焦慮",
      meaning: "市場波動開始加劇，大盤可能面臨修正或多空交戰，投資人應注意風險。",
      short: "20 ~ 30，警戒焦慮，注意修正或震盪",
    };
  }
  if (value >= 40) {
    return {
      range: "高於 40",
      mood: "極度恐慌 / 非理性恐慌",
      meaning: "大盤通常伴隨非理性大規模拋售，但也暗示市場可能短期內出現落底反彈契機。",
      short: "高於 40，極度恐慌，觀察落底反彈契機",
    };
  }
  return {
    range: "30 ~ 40",
    mood: "高恐慌 / 高波動",
    meaning: "市場恐慌情緒偏高，短線波動可能劇烈，操作宜降低追價與槓桿。",
    short: "30 ~ 40，高恐慌，短線波動劇烈",
  };
}
function buildInstitutionContinuityModel(key, label, currentItem) {
  const trend = data?.institutionTrend?.[key] || {};
  const rows = Array.isArray(data?.institutionTrend?.rows) ? data.institutionTrend.rows : [];
  const latestRow = rows[0] || {};
  const previousRow = rows[1] || {};
  const valueKey = `${key}Value`;
  const latestValue = parseMarketNumber(latestRow[valueKey] ?? currentItem?.diffValue ?? currentItem?.diff);
  const previousValue = parseMarketNumber(previousRow[valueKey]);
  if (!Number.isFinite(latestValue)) {
    return {
      short: "連續性待資料",
      advice: `${label}連續性資料仍在同步，暫以三大法人合計與類股強弱判斷資金方向。`,
      tone: "flat",
    };
  }

  const count = Math.max(1, Number(trend.count) || 1);
  const direction = latestValue > 0 ? "buy" : latestValue < 0 ? "sell" : "flat";
  const directionText = direction === "buy" ? "買超" : direction === "sell" ? "賣超" : "持平";
  const amountText = formatInstitutionAmount(Math.abs(latestValue));
  const short = count >= 2 ? `連 ${count} ${directionText}` : `今日${directionText}`;
  const turned = Number.isFinite(previousValue)
    && ((latestValue > 0 && previousValue < 0) || (latestValue < 0 && previousValue > 0));
  const turnText = turned
    ? latestValue > 0
      ? "今日由賣轉買，代表賣壓先暫停，但仍需隔日續買才算確認。"
      : "今日由買轉賣，代表外資動能轉弱，需降低追價權重。"
    : "";

  let advice = "";
  if (direction === "buy") {
    advice = count >= 2
      ? `${label}${short} ${amountText}，外資延續性已確認，資金面可支持強勢族群續攻；若明日量能不退，可提高推薦類股觀察權重。`
      : `${label}今日買超 ${amountText}，但尚未形成連續買超；${turnText || "先視為單日回補，明日若續買才提高資金延續評分。"}`;
  } else if (direction === "sell") {
    advice = count >= 2
      ? `${label}${short} ${amountText}，外資賣壓具連續性，指數反彈應先看量能與權值股是否止穩，防守類股權重需提高。`
      : `${label}今日賣超 ${amountText}，尚未形成連續賣超；${turnText || "若明日再賣，需下修強勢族群追價權重。"}`;
  } else {
    advice = `${label}今日接近持平，連續性訊號不明，資金判斷以投信、自營商與類股成交量為主。`;
  }

  return {
    short,
    advice,
    tone: direction === "buy" ? "up" : direction === "sell" ? "down" : "flat",
  };
}
function buildMarketAiInsightModel() {
  const overview = data.marketOverview?.[0] || {};
  const indexPct = parseMarketNumber(overview.pct) || 0;
  const sectors = (data.sectors || [])
    .filter((item) => !isExcludedSector(item) && item.name !== "台灣加權指數")
    .map((item) => {
      const pctValue = parseMarketNumber(item.pct);
      const changeValue = parseMarketNumber(item.change);
      const volumeValue = parseMarketNumber(item.volumeValue ?? item.volume);
      const activityScore = parseMarketNumber(item.technicalAnalysis?.activityScore);
      return {
        ...item,
        pctValue: Number.isFinite(pctValue) ? pctValue : null,
        changeValue: Number.isFinite(changeValue) ? changeValue : null,
        volumeValue: Number.isFinite(volumeValue) ? volumeValue : 0,
        activityScore: Number.isFinite(activityScore) ? activityScore : null,
      };
    })
    .filter((item) => Number.isFinite(item.pctValue));
  const advancing = sectors.filter((item) => item.pctValue > 0).length;
  const declining = sectors.filter((item) => item.pctValue < 0).length;
  const unchanged = sectors.filter((item) => item.pctValue === 0).length;
  const breadthRatio = sectors.length ? advancing / sectors.length : 0.5;
  const topPct = [...sectors].sort((left, right) => right.pctValue - left.pctValue);
  const weakPct = [...sectors].sort((left, right) => left.pctValue - right.pctValue);
  const maxVolume = Math.max(...sectors.map((item) => item.volumeValue || 0), 1);
  const volumeScore = (item) => Math.log10((item.volumeValue || 0) + 1) / Math.log10(maxVolume + 1) * 12;
  const defensiveNames = new Set(["食品", "生技", "金融保險", "水泥", "造紙", "通信網路", "居家生活", "油電燃氣"]);
  const isDefensive = (item) => {
    const name = String(item.name || "");
    return [...defensiveNames].some((keyword) => name.includes(keyword));
  };
  const flowPayload = data?.sectorFundFlow || {};
  const flowRows = Array.isArray(flowPayload.rows) ? flowPayload.rows : [];
  const flowByName = new Map(flowRows.map((item) => [String(item.name || ""), item]));
  const matchFlow = (sector) => {
    const name = String(sector?.name || "");
    if (!name) return null;
    if (flowByName.has(name)) return flowByName.get(name);
    return flowRows.find((item) => {
      const flowName = String(item.name || "");
      return flowName && (name.includes(flowName) || flowName.includes(name));
    }) || null;
  };
  const bounded = (value, min, max) => Math.max(min, Math.min(max, value));
  const flowAmountScore = (value, scale = 12, min = -22, max = 26) => {
    const parsed = parseMarketNumber(value);
    if (!Number.isFinite(parsed)) return 0;
    return bounded((parsed / 100000000) / scale, min, max);
  };
  const flowToneText = (flow) => {
    const amount = parseMarketNumber(flow?.netAmountValue);
    if (!Number.isFinite(amount)) return "資金同步中";
    return amount > 0 ? "資金流入" : amount < 0 ? "資金流出" : "資金持平";
  };

  const institutionTotal = (data.institutions || []).find((item) => item.name === "合計");
  const institutionNet = parseMarketNumber(institutionTotal?.diffValue ?? institutionTotal?.diff)
    ?? (data.institutionSummary || []).reduce((sum, item) => sum + (parseMarketNumber(item.diffValue) || 0), 0);
  const foreign = (data.institutions || []).find((item) => String(item.name || "").startsWith("外資") && item.name !== "外資自營商");
  const dealer = (data.institutions || []).find((item) => String(item.name || "").includes("自營商") && !String(item.name || "").includes("避險"));
  const foreignContinuity = buildInstitutionContinuityModel("foreign", "外資", foreign);
  const vixValue = parseMarketNumber(data?.marketVolatility?.value);
  const vixBand = getVixSentiment(vixValue);
  const flowNetTotal = parseMarketNumber(flowPayload.netTotalValue);
  const flowRiskAdjustment = Number.isFinite(flowNetTotal)
    ? flowNetTotal < 0
      ? Math.min(14, Math.abs(flowNetTotal / 100000000) / 60)
      : -Math.min(8, (flowNetTotal / 100000000) / 80)
    : 0;
  const riskScore = clampScore(
    44
    - indexPct * 5
    + (declining / Math.max(sectors.length, 1)) * 32
    + (Number.isFinite(institutionNet) && institutionNet < 0 ? 13 : -6)
    + (Number.isFinite(vixValue) ? Math.max(0, vixValue - 18) * 1.7 : 0)
    + flowRiskAdjustment,
  );
  const riskLabel = riskScore >= 70 ? "高風險" : riskScore >= 55 ? "中高風險" : riskScore >= 40 ? "中性震盪" : "風險可控";
  const riskTone = riskScore >= 60 ? "high" : riskScore >= 40 ? "medium" : "low";
  const trendLabel = indexPct > 0.7 && breadthRatio >= 0.55
    ? "多方輪動"
    : indexPct >= 0 && breadthRatio >= 0.45
      ? "震盪偏多"
      : indexPct < -0.7 || breadthRatio < 0.38
        ? "修正防守"
        : "多空拉鋸";
  const trendSummary = overview.value
    ? `加權指數 ${overview.value}，日漲跌幅 ${overview.pct || "--"}；類股 ${advancing} 漲、${declining} 跌、${unchanged} 平，市場廣度${breadthRatio >= 0.55 ? "偏多" : breadthRatio <= 0.4 ? "偏弱" : "分歧"}。`
    : `類股 ${advancing} 漲、${declining} 跌、${unchanged} 平，主要指數資料仍在同步。`;

  const topInflow = (Array.isArray(flowPayload.inflows) ? flowPayload.inflows : [])[0];
  const topOutflow = (Array.isArray(flowPayload.outflows) ? flowPayload.outflows : [])[0];
  const fundFlowText = flowRows.length
    ? `資金流向：流入 ${topInflow ? `${topInflow.name} ${formatSectorFundFlowAmount(topInflow.netAmountValue, true)}` : "--"}，流出 ${topOutflow ? `${topOutflow.name} ${formatSectorFundFlowAmount(topOutflow.netAmountValue, true)}` : "--"}`
    : "資金流向同步中";
  const fundFlowRiskText = Number.isFinite(flowNetTotal)
    ? `${flowNetTotal >= 0 ? "整體資金淨流入" : "整體資金淨流出"} ${formatSectorFundFlowAmount(flowNetTotal, true)}`
    : "整體資金流向同步中";

  const recommended = sectors
    .map((item) => {
      const flow = matchFlow(item);
      const flowAmount = parseMarketNumber(flow?.netAmountValue);
      const foreignFlow = parseMarketNumber(flow?.foreignAmountValue);
      const trustFlow = parseMarketNumber(flow?.trustAmountValue);
      const flowBonus = flowAmountScore(flowAmount, 11, -24, 28);
      const foreignBonus = flowAmountScore(foreignFlow, 22, -10, 12);
      const trustBonus = flowAmountScore(trustFlow, 8, -10, 14);
      const chaseRiskPenalty = riskScore >= 60 ? Math.max(0, item.pctValue) * 1.6 : 0;
      const score = clampScore(
        50
        + item.pctValue * 5.8
        + volumeScore(item)
        + (Number.isFinite(item.activityScore) ? (item.activityScore - 50) * 0.12 : 0)
        + (item.changeValue > 0 ? 3 : item.changeValue < 0 ? -4 : 0)
        + flowBonus
        + foreignBonus
        + trustBonus
        - chaseRiskPenalty,
      );
      const flowText = flow
        ? `${flowToneText(flow)} ${formatSectorFundFlowAmount(flowAmount, true)}`
        : "資金流向同步中";
      return {
        ...item,
        fundFlow: flow,
        score,
        reason: `${item.pct || "--"}，${flowText}；成交量 ${item.volume || "--"}，量價與法人資金同向者優先。`,
      };
    })
    .sort((left, right) => right.score - left.score)
    .slice(0, 10);

  const hedge = sectors
    .map((item) => {
      const flow = matchFlow(item);
      const flowAmount = parseMarketNumber(flow?.netAmountValue);
      const defensiveBonus = isDefensive(item) ? 20 : 0;
      const stabilityBonus = Math.max(0, 12 - Math.abs(item.pctValue) * 3);
      const flowDefenseBonus = Number.isFinite(flowAmount)
        ? flowAmount >= 0
          ? Math.min(16, (flowAmount / 100000000) / 18)
          : Math.max(-14, (flowAmount / 100000000) / 14)
        : 0;
      const riskModeBonus = riskScore >= 60 && isDefensive(item) ? 8 : 0;
      const score = clampScore(
        42
        + defensiveBonus
        + stabilityBonus
        + Math.max(-8, Math.min(8, item.pctValue * 3))
        + volumeScore(item) * 0.45
        + flowDefenseBonus
        + riskModeBonus,
      );
      const flowText = flow
        ? `${flowToneText(flow)} ${formatSectorFundFlowAmount(flowAmount, true)}`
        : "資金流向同步中";
      return {
        ...item,
        fundFlow: flow,
        score,
        reason: `${isDefensive(item) ? "防守屬性" : "波動相對收斂"}，${item.pct || "--"}，${flowText}；風險升溫時優先看抗跌與資金承接。`,
      };
    })
    .sort((left, right) => right.score - left.score)
    .slice(0, 10);

  const leaderText = recommended.length ? recommended.map((item) => item.name).join("、") : "等待資料";
  const hedgeText = hedge.length ? hedge.map((item) => item.name).join("、") : "等待資料";
  const recommendedFlowAligned = recommended.filter((item) => (parseMarketNumber(item.fundFlow?.netAmountValue) || 0) > 0).length;
  const hedgeFlowSupported = hedge.filter((item) => (parseMarketNumber(item.fundFlow?.netAmountValue) || 0) >= 0).length;
  const aiAdvice = [
    riskScore >= 60
      ? `風險分數 ${riskScore}/100，先降低追價與槓桿；推薦 TOP10 需同時確認資金流入與成交量延續，避險 TOP10 提高權重。`
      : `風險分數 ${riskScore}/100，若推薦 TOP10 續強且資金淨流入，可採強勢族群優先、弱勢族群迴避。`,
    Number.isFinite(institutionNet)
      ? `法人合計${institutionNet >= 0 ? "買超" : "賣超"} ${formatInstitutionAmount(Math.abs(institutionNet))}；${foreignContinuity.advice}`
      : "法人合計資料不足，暫以類股強弱與 VIX 風險溫度判斷。",
    `${fundFlowText}；推薦 TOP10 中 ${recommendedFlowAligned} 檔有資金淨流入，避險 TOP10 中 ${hedgeFlowSupported} 檔資金未明顯外流。`,
    `推薦類股 TOP10：${leaderText}；避險類股 TOP10：${hedgeText}。若兩組同時走強，代表資金在攻守並行，宜降低單一題材集中度。`,
    Number.isFinite(vixValue)
      ? `VIX ${vixValue.toFixed(2)}，${vixBand.short}。`
      : "VIX 尚未同步，盤中先用類股廣度與法人方向控管風險。",
  ];

  return {
    overview,
    trendLabel,
    trendSummary,
    riskLabel,
    riskTone,
    riskScore,
    breadthText: `${advancing} 漲 / ${declining} 跌 / ${unchanged} 平`,
    institutionText: Number.isFinite(institutionNet) ? `${institutionNet >= 0 ? "買超" : "賣超"} ${formatInstitutionAmount(Math.abs(institutionNet))}` : "--",
    fundFlowText,
    fundFlowRiskText,
    foreignText: foreign?.diff || "--",
    foreignTrendText: foreignContinuity.short,
    dealerText: dealer?.diff || "--",
    vixText: Number.isFinite(vixValue) ? `${vixValue.toFixed(2)} · ${vixBand.mood}` : "--",
    recommended,
    hedge,
    aiAdvice,
  };
}
function renderMarketInsightRankList(items, tone, label = "市場提示類股排行") {
  if (!items.length) return '<p class="market-ai-empty">資料同步中。</p>';
  return `
    <div class="market-ai-rank-list" tabindex="0" role="region" aria-label="${escapeHtml(label)}">
      ${items.map((item, index) => `
        <article class="market-ai-rank-item is-${tone}">
          <span>${index + 1}</span>
          <div>
            <strong>${escapeHtml(item.name || "--")}</strong>
            <small>${escapeHtml(item.reason || "")}</small>
          </div>
          <b class="${toneClass(item.tone)}">${escapeHtml(item.pct || "--")}</b>
        </article>
      `).join("")}
    </div>
  `;
}
function renderMarketInsightPanel() {
  const model = buildMarketAiInsightModel();
  return `
    <section class="market-ai-panel market-ai-risk-${model.riskTone}">
      <div class="market-ai-summary-grid">
        <article>
          <span>市場趨勢</span>
          <strong>${escapeHtml(model.trendLabel)}</strong>
          <small>${escapeHtml(model.trendSummary)}</small>
        </article>
        <article>
          <span>風險等級</span>
          <strong>${escapeHtml(model.riskLabel)}</strong>
          <small>風險分數 ${model.riskScore}/100 · VIX ${escapeHtml(model.vixText)} · ${escapeHtml(model.fundFlowRiskText)}</small>
        </article>
        <article>
          <span>市場廣度</span>
          <strong>${escapeHtml(model.breadthText)}</strong>
          <small>法人合計 ${escapeHtml(model.institutionText)}；外資 ${escapeHtml(model.foreignText)}（${escapeHtml(model.foreignTrendText)}）；${escapeHtml(model.fundFlowText)}</small>
        </article>
      </div>
      <div class="market-ai-rank-grid">
        <section>
          <h4>推薦類股 TOP10</h4>
          ${renderMarketInsightRankList(model.recommended, "leader", "推薦類股 TOP10 清單")}
        </section>
        <section>
          <h4>避險類股 TOP10</h4>
          ${renderMarketInsightRankList(model.hedge, "hedge", "避險類股 TOP10 清單")}
        </section>
      </div>
      <section class="market-ai-advice">
        <h4>AI 分析建議</h4>
        <ul>${model.aiAdvice.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </section>
    </section>
  `;
}
function getMarketSortedSectors(direction = "up", limit = 5) {
  return (data.sectors || [])
    .filter((sector) => !isExcludedSector(sector))
    .map((sector) => ({ ...sector, pctValue: parseMarketNumber(sector.pct) || 0 }))
    .sort((left, right) => direction === "up" ? right.pctValue - left.pctValue : left.pctValue - right.pctValue)
    .slice(0, limit);
}
function getMarketLimitSamples(direction = "up", limit = 8) {
  return (localAllStocks || [])
    .filter((stock) => stock.code && stock.name && !String(stock.name).includes("主動"))
    .map((stock) => ({ ...stock, pctValue: parseMarketNumber(stock.pct) || 0 }))
    .sort((left, right) => direction === "up" ? right.pctValue - left.pctValue : left.pctValue - right.pctValue)
    .slice(0, limit);
}
function getMarketExtremeSummary(upSectors, downSectors) {
  const sectorPool = (data.sectors || [])
    .filter((sector) => !isExcludedSector(sector))
    .map((sector) => parseMarketNumber(sector.pct))
    .filter((value) => Number.isFinite(value));
  const advancing = sectorPool.filter((value) => value > 0).length;
  const declining = sectorPool.filter((value) => value < 0).length;
  const strongest = upSectors[0];
  const weakest = downSectors[0];
  const spread = strongest && weakest ? (strongest.pctValue - weakest.pctValue).toFixed(2) : "--";
  const breadth = advancing >= declining * 1.4 ? "多方擴散" : declining >= advancing * 1.2 ? "空方擴散" : "多空分歧";
  const signal = strongest && weakest
    ? `${strongest.name} 領漲、${weakest.name} 承壓，強弱差 ${spread} 個百分點。`
    : "類股資料不足，暫以大盤與法人方向輔助判斷。";
  return { advancing, declining, breadth, signal, spread };
}
function renderLimitMoveStockLink(stock) {
  const code = encodeURIComponent(stock.code || "");
  const market = encodeURIComponent(stock.market || "");
  const href = `tw-stock-search.html?q=${code}&market=${market}`;
  return `
    <a class="limit-move-stock-link" href="${safeUrl(href)}">
      <strong>${escapeHtml(stock.code)} ${escapeHtml(stock.name)}</strong>
      <span class="${toneClass(stock.tone)}">${escapeHtml(stock.pct || "--")}</span>
      <small>${escapeHtml(stock.marketLabel || stock.market || "上市櫃")}</small>
    </a>
  `;
}
function renderMarketExtremeObservationCard() {
  const container = document.getElementById("market-limit-move-card");
  if (!container) return;
  const upSectors = getMarketSortedSectors("up", 5);
  const downSectors = getMarketSortedSectors("down", 5);
  const upSamples = getMarketLimitSamples("up", 5);
  const downSamples = getMarketLimitSamples("down", 5);
  const newsThemes = (data.news || []).slice(0, 3);
  const summary = getMarketExtremeSummary(upSectors, downSectors);
  const sectorRows = (items, tone) => items.map((sector) => `
    <article class="market-extreme-sector ${tone}">
      <div>
        <strong>${escapeHtml(sector.name)}</strong>
        <span>${escapeHtml(sector.pct)}</span>
      </div>
      <p>${escapeHtml(sector.value || "--")} · 成交量 ${escapeHtml(sector.volume || "--")}</p>
      <small>${escapeHtml(sector.note || "以類股漲跌幅、成交量與市場輪動作為觀察基準。")}</small>
    </article>
  `).join("");
  container.innerHTML = `
    <article class="market-extreme-card market-extreme-wide">
      <div class="market-extreme-head">
        <div>
          <p class="panel-kicker">Limit move × AI watchlist</p>
          <h3>類股漲跌停觀察與 AI 觀察名單</h3>
        </div>
        <span>${summary.breadth}</span>
      </div>
      <p class="market-extreme-summary">接近漲停、接近跌停樣本以類股輪動為主；新聞 × 趨勢候選股以題材、資金流與相對強弱作為輔助，不單靠單一個股漲跌幅判斷。${summary.signal}</p>
      <div class="market-extreme-metrics">
        <div><span>上漲類股</span><strong>${summary.advancing}</strong><small>類股廣度</small></div>
        <div><span>下跌類股</span><strong>${summary.declining}</strong><small>風險擴散</small></div>
        <div><span>強弱差</span><strong>${summary.spread}</strong><small>百分點</small></div>
        <div><span>觀察模式</span><strong>類股優先</strong><small>題材輔助</small></div>
      </div>
      <div class="market-extreme-layout">
        <section>
          <h4>接近漲停樣本：類股主軸</h4>
          <div class="market-extreme-sector-list">${sectorRows(upSectors, "is-positive")}</div>
          <h4 class="market-extreme-subtitle">個股連結樣本</h4>
          <div class="limit-move-sample-list is-positive">${upSamples.map(renderLimitMoveStockLink).join("")}</div>
        </section>
        <section>
          <h4>接近跌停樣本：風險類股</h4>
          <div class="market-extreme-sector-list">${sectorRows(downSectors, "is-negative")}</div>
          <h4 class="market-extreme-subtitle">個股連結樣本</h4>
          <div class="limit-move-sample-list is-negative">${downSamples.map(renderLimitMoveStockLink).join("")}</div>
        </section>
      </div>
      <div class="market-extreme-decision">
        <strong>AI 判讀重點</strong>
        <ul>
          <li>先看強勢類股是否連續擴散，再挑個股，不以單一漲停樣本追價。</li>
          <li>若弱勢類股集中且大盤量能放大，隔日優先控管持股風險。</li>
          <li>新聞題材需與類股強弱同向，才列入較高優先觀察。</li>
        </ul>
      </div>
      <div class="market-extreme-theme-list">
        ${newsThemes.map((item) => `
          <article class="market-extreme-theme">
            <div class="market-extreme-theme-head"><b>${escapeHtml(item.tag || "題材")}</b><span>新聞 × 趨勢候選</span></div>
            <strong>${escapeHtml(item.title)}</strong>
            <span>${escapeHtml(item.body)}</span>
          </article>
        `).join("")}
      </div>
      <p class="market-extreme-note">樣本可點擊連至個股詳情；此卡用於盤後觀察與風險排序，不構成投資建議。</p>
    </article>
  `;
}
function renderMarketPage() {
  window.renderSharedMarketDecisionSummary(window.buildSharedMarketDecisionModel());
  const marketGrid = document.getElementById("market-index-grid");
  if (marketGrid) {
    marketGrid.innerHTML = (data.marketOverview || []).map((item) => `
      <article class="metric-card">
        <p>${escapeHtml(item.name)}</p>
        <h3>${escapeHtml(item.value)}</h3>
        <strong class="${toneClass(item.tone)}">${escapeHtml(item.change)} / ${escapeHtml(item.pct)}</strong>
      </article>
    `).join("");
  }

  setText(
    "institution-date",
    data.institutionDate ? `資料日期 ${data.institutionDate}` : "每 60 秒更新",
  );

  const institutionSummary = document.getElementById("institution-summary");
  if (institutionSummary) {
    const summaries = data.institutionSummary?.length
      ? data.institutionSummary
      : buildInstitutionSummaryFromRows(data.institutions);
    institutionSummary.innerHTML = summaries.map((item) => `
      <article class="institution-card institution-card-${escapeHtml(item.key || "detail")}">
        <div class="institution-card-title">
          <span>${escapeHtml(item.name)}</span>
          <strong class="${toneClass(item.tone)}">${formatInstitutionAmount(item.diffValue, true)}</strong>
        </div>
        <div class="institution-card-metrics">
          <span>買進<strong>${formatInstitutionAmount(item.buyValue)}</strong></span>
          <span>賣出<strong>${formatInstitutionAmount(item.sellValue)}</strong></span>
        </div>
      </article>
    `).join("");
  }

  const institutionGrid = document.getElementById("institution-grid");
  if (institutionGrid) {
    institutionGrid.innerHTML = (data.institutions || [])
      .filter((item) => item.name !== "外資自營商")
      .map((item) => `
      <div class="institution-row">
        <span>${escapeHtml(item.name)}</span>
        <span>${formatInstitutionAmount(item.buyValue ?? item.buy)}</span>
        <span>${formatInstitutionAmount(item.sellValue ?? item.sell)}</span>
        <strong class="${toneClass(item.tone)}">${formatInstitutionAmount(item.diffValue ?? item.diff, true)}</strong>
      </div>
    `).join("");
  }
  renderSectorFundFlow();
  renderMarketListedSectorRanking();

  const marketNotes = document.getElementById("market-notes");
  if (marketNotes) {
    marketNotes.innerHTML = renderMarketInsightPanel();
  }

  const newsGrid = document.getElementById("market-news-grid");
  const riskCard = document.getElementById("market-risk-advice");
  if (riskCard) {
    const risk = buildMarketRiskAdvice();
    riskCard.className = `market-risk-card market-risk-${risk.tone}`;
    riskCard.innerHTML = `
      <div class="market-risk-heading">
        <div>
          <p class="panel-kicker">AI Risk Advisor</p>
          <h3>AI 風險建議</h3>
        </div>
        <span class="market-risk-level">${risk.label}</span>
      </div>
      <p class="market-risk-summary">${risk.summary}</p>
      <div class="market-risk-content">
        <div>
          <h4>風險因子</h4>
          <ul>${risk.factors.map((item) => `<li>${item}</li>`).join("")}</ul>
        </div>
        <div>
          <h4>隔日風險策略</h4>
          <ul>${risk.actions.map((item) => `<li>${item}</li>`).join("")}</ul>
        </div>
      </div>
      <p class="market-risk-disclaimer">AI 分析依當日公開市場數據自動推估，僅供風險管理與研究參考，不構成投資建議。</p>
    `;
  }

  renderMarketExtremeObservationCard();

  if (newsGrid) {
    const newsItems = [...buildMarketThemeNewsCards(), buildAfterMarketWatchCard()];
    newsGrid.innerHTML = newsItems.map((item, index) => `
      <article class="news-card">
        <span class="news-tag">${escapeHtml(item.tag)}</span>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.body)}</p>
      </article>
    `).join("") || '<div class="stock-detail-empty">目前沒有盤後快訊。</div>';
  }
}
