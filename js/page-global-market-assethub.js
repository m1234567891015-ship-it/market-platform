
function renderAssetHubFallbackPage(payloads = []) {
  const root = document.getElementById("asset-hub-root");
  if (!root) return;
  const availablePayloads = payloads.filter(Boolean);
  const cards = [
    ["期貨", "Futures", "futures", "觀察股指、能源、金屬與波動率期貨，作為風險偏好與隔夜方向參考。"],
    ["選擇權", "Options", "options", "整合 VIX、SPY、QQQ、IWM 等標的，搭配波動率與市場風險判斷。"],
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