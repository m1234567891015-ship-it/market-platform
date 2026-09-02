/* shadow-input:derivatives-ui.js */
(function () {
  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    const body = await response.json();
    if (!response.ok || body.success === false) throw new Error(body.error?.message || response.statusText);
    return body.data || body;
  }

  function statusChip(status) {
    const label = status === "connected" ? "已接入" : status === "imported" ? "已匯入" : "資料源待接入";
    const color = status === "connected" || status === "imported" ? "chip-green" : "chip-gold";
    return `<span class="chip ${color}">${escapeHtml(label)}</span>`;
  }

  function renderProducts(title, items) {
    return `
      <article class="panel-card global-table-card">
        <div class="card-title-row"><div><p class="panel-kicker">V1 catalog</p><h3>${escapeHtml(title)}</h3></div></div>
        <div class="global-table-wrap">
          <table class="global-market-table">
            <thead><tr><th>代號</th><th>名稱</th><th>分類</th><th>狀態</th><th>資料說明</th></tr></thead>
            <tbody>
              ${(items || []).map((item) => `<tr><td><strong>${escapeHtml(item.symbol)}</strong></td><td>${escapeHtml(item.name)}</td><td>${escapeHtml(item.group || item.type)}</td><td>${statusChip(item.v1Status)}</td><td>${escapeHtml(item.dataStatus || "TAIFEX 資料已接入")}</td></tr>`).join("")}
            </tbody>
          </table>
        </div>
      </article>
    `;
  }

  function renderStatus(data) {
    const coverage = data.coverage || {};
    const futures = coverage.futures || {};
    const options = coverage.options || {};
    const formula = data.aiScoreFormula || {};
    return `
      <section class="subpage-hero">
        <p class="eyebrow">Derivatives V1 status</p>
        <h1>V1 國內期權資料狀態</h1>
        <p class="hero-text">本頁列出國內期貨、國內選擇權、法人匯入、期現貨價差與 AI 分數依據；資料源未接入項目不以外部官網跳轉代替功能。</p>
      </section>
      <section class="section">
        <div class="asset-hub-stat-grid">
          <span><b>${futures.connected ?? 0}/${futures.total ?? 0}</b><small>期貨已接入</small></span>
          <span><b>${options.connected ?? 0}/${options.total ?? 0}</b><small>選擇權已接入</small></span>
          <span><b>${data.institutionImport?.currentProductRows ?? 0}</b><small>法人匯入筆數</small></span>
          <span><b>Basis</b><small>${escapeHtml(data.basis?.formula || "--")}</small></span>
        </div>
      </section>
      <section class="section"><div class="asset-hub-layout asset-hub-options-layout">${renderProducts("國內期貨", data.futures)}${renderProducts("國內選擇權", data.options)}</div></section>
      <section class="section">
        <article class="panel-card asset-hub-schema-card">
          <div class="card-title-row"><div><p class="panel-kicker">AI score formula</p><h3>AI 分數計算依據</h3></div></div>
          <div class="asset-hub-source-stack">
            <span><b>marketScore</b><small>${escapeHtml(formula.marketScore)}</small></span>
            <span><b>riskScore</b><small>${escapeHtml(formula.riskScore)}</small></span>
            <span><b>confidenceScore</b><small>${escapeHtml(formula.confidenceScore)}</small></span>
            <span><b>sourcePendingPenalty</b><small>${escapeHtml(formula.sourcePendingPenalty)}</small></span>
          </div>
        </article>
      </section>
    `;
  }

  async function init() {
    const root = document.getElementById("derivatives-status-root");
    if (!root) return;
    root.innerHTML = '<section class="subpage-hero"><p class="eyebrow">Loading</p><h1>V1 資料狀態載入中</h1></section>';
    try {
      root.innerHTML = renderStatus(await fetchJson("/api/derivatives/v1-status"));
    } catch (error) {
      root.innerHTML = `<section class="subpage-hero"><p class="eyebrow">Error</p><h1>資料狀態暫不可用</h1><p class="hero-text">${escapeHtml(error.message)}</p></section>`;
    }
  }

  document.addEventListener("DOMContentLoaded", init);
}());
