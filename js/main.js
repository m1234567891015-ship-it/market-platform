function renderCurrentPage() {
  const page = document.body.dataset.page;
  if (page === "global-market") {
    initGlobalMarketPage(false);
    return;
  }
  if (page === "us-stock-search") {
    initUsStockSearchPage();
    return;
  }
  if (page === "us-etf") {
    initUsEtfPage();
    return;
  }
  if (page === "tw-etf") {
    initTwEtfPage();
    return;
  }
  if (page === "asset-hub") {
    initAssetHubPage();
    return;
  }
  if (page === "us-watchlist") {
    initUsWatchlistPage();
    return;
  }
  if (page === "derivatives-analytics") {
    initDerivativesAnalyticsPage();
    return;
  }
  if (page === "derivatives-ai") {
    initDerivativesAiPage();
    return;
  }
  if (!data) return;
  if (page === "home") renderHome();
  if (page === "market") renderMarketPage();
  if (page === "sectors") { renderSectorPageV2(); startVixPolling(); }
  if (page === "watchlist") renderWatchlist();
}
async function loadLiveData() {
  const page = document.body.dataset.page;
  const endpoint = page === "sectors"
    ? "/api/twse/live-sectors"
    : page === "market"
      ? "/api/twse/live-overview"
      : "/api/twse/site-data?refresh=1";
  const timeoutMs = page === "sectors" ? 45000 : 90000;
  if (page === "sectors") {
    setText("sector-source-note", "正在快速匯入 live 類股、加權指數與 VIX 資料...");
  }
  if (page === "market") {
    setText("institution-date", "live 同步中");
    const grid = document.getElementById("market-index-grid");
    if (grid && !grid.children.length) {
      grid.innerHTML = '<article class="overview-card"><span>資料狀態</span><strong>同步中</strong><small>正在同步 live 大盤、法人、VIX 與國際指數。</small></article>';
    }
  }
  try {
    const response = await fetchWithTimeout(
      endpoint,
      { cache: "no-store" },
      timeoutMs,
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const sourceStatus = payload.sourceStatus || "healthy";
    if (sourceStatus === "invalid_payload" || sourceStatus === "temporarily_unavailable") {
      const statusLabels = { invalid_payload: "來源資料格式異常", temporarily_unavailable: "來源暫時無法連線" };
      const statusText = statusLabels[sourceStatus] + "；保留上一份資料。更新時間：" + (payload.sourceUpdatedAt || "--") + "。";
      if (page === "sectors") setText("sector-source-note", statusText);
      if (page === "market") setText("institution-date", statusText);
      if (page === "home") setText("source-note", statusText);
      return false;
    }
    data = payload;
    if (Array.isArray(data.stocks)) {
      localAllStocks = data.stocks;
    }
    renderCurrentPage();
    const sourceLabels = { healthy: "來源正常", stale: "使用快取資料", temporarily_unavailable: "來源暫時無法連線", invalid_payload: "來源資料格式異常" };
    const sourceLabel = sourceLabels[sourceStatus] || sourceLabels.temporarily_unavailable;
    const updatedAt = payload.sourceUpdatedAt || payload.refreshedAt || payload.cachedAt || payload.snapshotDate || "--";
    if (page === "home") setText("source-note", formatUpdateText(data.snapshotDate, data.cachedAt) + " 來源狀態：" + sourceLabel + "；資料時間：" + updatedAt + "。");
    if (page === "market") setText("institution-date", (data.institutionDate ? "資料日期 " + data.institutionDate : "每 60 秒更新") + " · " + sourceLabel + " · 更新時間 " + updatedAt);
    if (page === "watchlist") setText("watchlist-status", "資料來源狀態：" + sourceLabel + "；資料時間：" + updatedAt + "。");
    return true;
  } catch (error) {
    const sectorNote = document.getElementById("sector-source-note");
    if (page === "sectors" && sectorNote) {
      sectorNote.textContent = "live 類股資料同步失敗，請稍後重新整理。";
    }
    if (page === "market") {
      setText("institution-date", "live 同步失敗");
      const grid = document.getElementById("market-index-grid");
      if (grid) grid.innerHTML = '<article class="overview-card"><span>資料狀態</span><strong>同步失敗</strong><small>live 大盤資料暫時無法載入。</small></article>';
    }
    if (page === "watchlist") {
      setText("watchlist-status", "live 大盤資料同步失敗，請稍後再試。");
    }
    if (page === "home") {
      setText("source-note", "來源暫時無法連線；保留目前資料。更新時間：" + (data?.sourceUpdatedAt || data?.cachedAt || data?.snapshotDate || "--") + "。");
    }
    console.error("Failed to load live TWSE data:", error);
    return false;
  }
}
if (document.body.dataset.page === "search") initSearchPage();
if (document.body.dataset.page === "watchlist") initWatchlistPage();
document.addEventListener("click", (event) => {
  const refreshButton = event.target.closest("[data-global-refresh]");
  if (refreshButton) {
    initGlobalMarketPage(true);
    return;
  }
  const button = event.target.closest("[data-yahoo-sector-group][data-yahoo-sector-index]");
  if (!button) return;
  const groupKey = button.dataset.yahooSectorGroup || "";
  const categoryIndex = Number(button.dataset.yahooSectorIndex);
  if (!groupKey || !Number.isInteger(categoryIndex)) return;
  loadYahooSectorCategory(groupKey, categoryIndex, button.textContent.trim());
});
renderCurrentPage();
if (!["search", "watchlist", "global-market", "tw-etf", "us-etf", "us-stock-search", "asset-hub", "us-watchlist", "derivatives-analytics", "derivatives-ai"].includes(document.body.dataset.page)) {
  loadLiveData();
  setInterval(loadLiveData, document.body.dataset.page === "sectors" ? 5 * 60 * 1000 : 60 * 1000);
}
