function getUsEtfCategoryLabel(key) {
  return US_ETF_CATEGORY_LABELS[key] || US_ETF_CATEGORY_LABELS.other;
}
function getUsEtfCategoryKey(item = {}) {
  const symbol = String(item.symbol || "").trim().toUpperCase();
  const text = `${symbol} ${item.name || ""} ${item.type || ""}`.toLowerCase();
  const exact = (symbols) => symbols.includes(symbol);
  if (exact(["TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXU", "QLD", "QID", "SSO", "SDS", "SH", "PSQ", "TNA", "TZA", "UDOW", "SDOW", "TECL", "TECS", "FAS", "FAZ", "LABU", "LABD"]) || /\b(ultrapro|ultra|2x|3x|inverse|bear|daily .* bull|daily .* bear|short qqq|short s&p)\b/.test(text)) {
    return "leveraged";
  }
  if (exact(["BITO", "IBIT", "GBTC", "FBTC", "ARKB", "BITB", "HODL", "EZBC", "BTCW", "ETHA", "ETHE"]) || /\b(bitcoin|ether|ethereum|crypto|blockchain)\b/.test(text)) {
    return "crypto";
  }
  if (exact(["GLD", "IAU", "GLDM", "SGOL", "BAR", "AAAU", "SLV", "SIVR", "PSLV", "PPLT", "PLTM", "PALL", "USO", "UNG", "CPER", "COPX", "DBA", "DBC", "GDX", "GDXJ", "SIL", "SILJ", "RING"]) || /\b(gold|silver|oil|natural gas|commodity|commodities|copper|platinum|palladium|agriculture|miners?)\b/.test(text)) {
    return "commodity";
  }
  if (exact(["TLT", "IEF", "SHY", "BND", "AGG", "LQD", "HYG", "JNK", "TIP", "MUB", "VGIT", "VGSH", "VGLT", "BIL", "SGOV", "USFR"]) || /\b(bond|treasury|income bond|aggregate|credit|corporate|municipal|high yield|floating rate|t-bill|ultrashort|short duration)\b/.test(text)) {
    return "bond";
  }
  if (exact(["SCHD", "VIG", "VYM", "JEPI", "JEPQ", "DGRW", "DVY", "SDY", "NOBL", "HDV"]) || /\b(dividend|income|equity premium|covered call|yield|distribution)\b/.test(text)) {
    return "dividend";
  }
  if (exact(["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLB", "XLU", "XLRE", "SMH", "SOXX", "XBI", "KRE", "XRT", "ITA", "IYT"]) || /\b(select sector|sector|technology|financial|health care|healthcare|energy|utilities|industrial|materials|consumer|communication|semiconductor|biotech|bank|retail|transportation|aerospace)\b/.test(text)) {
    return "sector";
  }
  if (exact(["EFA", "EEM", "VEA", "VWO", "IEFA", "IEMG", "VXUS", "ACWX", "EWJ", "EWZ", "FXI", "ASHR", "MCHI", "INDA", "EWT"]) || /\b(international|global ex|ex-us|emerging|developed markets|eafe|china|japan|europe|india|brazil|taiwan|foreign)\b/.test(text)) {
    return "international";
  }
  if (exact(["USMV", "MTUM", "QUAL", "VUG", "VTV", "IWF", "IWD", "IJR", "MDY", "VB", "VO", "RSP"]) || /\b(factor|momentum|quality|minimum volatility|min vol|value|growth|small-cap|midcap|mid-cap|equal weight|low volatility)\b/.test(text)) {
    return "factor";
  }
  if (exact(["SPY", "IVV", "VOO", "SPLG", "QQQ", "QQQM", "DIA", "IWM", "VTI", "ITOT", "SCHB", "VT"]) || /\b(s&p 500|nasdaq-?100|dow jones|russell 2000|total stock market|large cap|broad market|whole market)\b/.test(text)) {
    return "market";
  }
  if (exact(["ARKK", "ARKW", "ARKG", "ARKF", "BOTZ", "ROBO", "CIBR", "HACK", "ICLN", "TAN", "LIT", "DRIV", "VNQ", "IYR"]) || /\b(innovation|internet|robotics|cyber|clean energy|solar|lithium|electric vehicle|genomics|fintech|theme|thematic|next generation|reit|real estate)\b/.test(text)) {
    return "thematic";
  }
  return "other";
}
function enrichUsEtfDirectoryItems(items = []) {
  return items.map((item) => {
    const etfCategoryKey = getUsEtfCategoryKey(item);
    return {
      ...item,
      etfCategoryKey,
      etfCategoryLabel: getUsEtfCategoryLabel(etfCategoryKey),
    };
  });
}
function renderUsEtfCategoryFilters(items = [], activeCategory = "all") {
  const counts = new Map();
  items.forEach((item) => counts.set(item.etfCategoryKey || "other", (counts.get(item.etfCategoryKey || "other") || 0) + 1));
  const total = items.length;
  return US_ETF_CATEGORY_DEFINITIONS
    .filter((category) => category.key === "all" || category.key === activeCategory || !items.length || counts.get(category.key))
    .map((category) => {
      const count = category.key === "all" ? total : counts.get(category.key) || 0;
      const countText = items.length ? ` <small>${Number(count).toLocaleString("zh-TW")}</small>` : "";
      return `<button class="range-button ${category.key === activeCategory ? "is-active" : ""}" type="button" data-us-etf-category="${escapeHtml(category.key)}">${escapeHtml(category.label)}${countText}</button>`;
    })
    .join("");
}
function renderUsEtfCategoryOptions(items = [], activeCategory = "all") {
  const counts = new Map();
  items.forEach((item) => counts.set(item.etfCategoryKey || "other", (counts.get(item.etfCategoryKey || "other") || 0) + 1));
  const total = items.length;
  return US_ETF_CATEGORY_DEFINITIONS
    .filter((category) => category.key === "all" || category.key === activeCategory || !items.length || counts.get(category.key))
    .map((category) => {
      const count = category.key === "all" ? total : counts.get(category.key) || 0;
      const label = category.key === "all" ? `全部 ETF (${Number(total).toLocaleString("zh-TW")})` : `${category.label} (${Number(count).toLocaleString("zh-TW")})`;
      return `<option value="${escapeHtml(category.key)}"${category.key === activeCategory ? " selected" : ""}>${escapeHtml(label)}</option>`;
    })
    .join("");
}
function renderUsEtfSortOptions(activeSort = "return_desc") {
  return US_ETF_DIRECTORY_SORT_OPTIONS
    .map(([value, label]) => `<option value="${escapeHtml(value)}"${value === activeSort ? " selected" : ""}>${escapeHtml(label)}</option>`)
    .join("");
}
function normalizeUsEtfSymbolKey(symbol) {
  return String(symbol || "").trim().toUpperCase().replace(/\./g, "-");
}
function getUsEtfQuoteMap(payload = {}) {
  const quoteItems = Array.isArray(payload.quoteItems) && payload.quoteItems.length
    ? payload.quoteItems
    : usNyseDirectoryState.etf.quoteItems || [];
  const map = new Map();
  quoteItems.forEach((item) => {
    const key = normalizeUsEtfSymbolKey(item.symbol);
    if (key && !map.has(key)) map.set(key, item);
  });
  return map;
}
function buildUsEtfDirectoryRows(payload = {}) {
  const quoteMap = getUsEtfQuoteMap(payload);
  return enrichUsEtfDirectoryItems(payload?.results || []).map((item) => {
    const symbol = String(item.symbol || "").trim().toUpperCase();
    const quoteItem = quoteMap.get(normalizeUsEtfSymbolKey(symbol));
    const stats = quoteItem ? getUsEtfReturnStats(quoteItem) : {};
    const dailyPct = parseMarketNumber(quoteItem?.pct ?? item.pct);
    const tone = dailyPct > 0 ? "up" : dailyPct < 0 ? "down" : "flat";
    return {
      ...item,
      quoteItem,
      close: quoteItem?.close ?? item.close ?? "--",
      pct: quoteItem?.pct ?? item.pct ?? "--",
      volume: quoteItem?.volume ?? item.volume ?? "--",
      volatilityPct: Number.isFinite(stats.volatility) ? stats.volatility : null,
      returnPct: Number.isFinite(stats.returnPct) ? stats.returnPct : null,
      tone,
      hasQuote: Boolean(quoteItem && !quoteItem.error),
    };
  });
}
function getUsEtfDirectorySortValue(item, sort) {
  if (sort === "volume_desc") return parseMarketNumber(item.volume);
  if (sort === "volatility_desc") return item.volatilityPct;
  return parseMarketNumber(item.pct);
}
function getUsEtfFilteredDirectoryRows(payload = {}) {
  const state = usNyseDirectoryState.etf;
  const activeCategory = state.category || "all";
  const rows = buildUsEtfDirectoryRows(payload);
  const filtered = activeCategory === "all"
    ? rows
    : rows.filter((item) => item.etfCategoryKey === activeCategory);
  const sort = state.sort || "return_desc";
  return filtered.slice().sort((a, b) => {
    if (sort === "symbol") {
      return String(a.symbol || "").localeCompare(String(b.symbol || ""), "en");
    }
    const aValue = getUsEtfDirectorySortValue(a, sort);
    const bValue = getUsEtfDirectorySortValue(b, sort);
    const aHasValue = Number.isFinite(aValue);
    const bHasValue = Number.isFinite(bValue);
    if (aHasValue !== bHasValue) return aHasValue ? -1 : 1;
    if (!aHasValue && !bHasValue) {
      return String(a.symbol || "").localeCompare(String(b.symbol || ""), "en");
    }
    return sort === "return_asc" ? aValue - bValue : bValue - aValue;
  });
}
function getUsEtfDirectoryPage(payload = {}) {
  const state = usNyseDirectoryState.etf;
  const pageSize = Number(state.pageSize) || US_ETF_DEFAULT_PAGE_SIZE;
  const rows = getUsEtfFilteredDirectoryRows(payload);
  const totalItems = rows.length;
  const totalPages = Math.max(Math.ceil(totalItems / pageSize), 1);
  state.page = Math.max(1, Math.min(Number(state.page) || 1, totalPages));
  const start = (state.page - 1) * pageSize;
  return {
    allRows: buildUsEtfDirectoryRows(payload),
    rows,
    pageItems: rows.slice(start, start + pageSize),
    pageSize,
    totalItems,
    totalPages,
    start,
    end: Math.min(start + pageSize, totalItems),
  };
}
function getUsNyseDirectoryConfig(kind = "stock") {
  return kind === "etf"
    ? {
      key: "etf",
      sectionId: "us-nyse-listed-etfs",
      countId: "us-nyse-etf-count",
      statusId: "us-nyse-etf-status",
      tableId: "us-nyse-etf-table",
      pagerId: "us-nyse-etf-pager",
      searchId: "us-nyse-etf-search",
      kicker: "US listed ETFs",
      title: "美股ETF線上資料明細",
      loadingText: "正在同步美股 ETF 官方上市清單...",
      emptyText: "目前沒有可顯示的美股 ETF 資料。",
      failText: "美股 ETF 資料載入失敗，請稍後重新整理。",
      group: "美股 ETF",
      label: "ETF",
      apiKind: "etf",
      apiLimit: 6000,
      fallbackLimit: 8000,
    }
    : {
      key: "stock",
      sectionId: "us-nyse-listed-stocks",
      countId: "us-nyse-listed-count",
      statusId: "us-nyse-listed-status",
      tableId: "us-nyse-listed-table",
      pagerId: "us-nyse-listed-pager",
      searchId: "us-nyse-listed-search",
      kicker: "NYSE listed stocks",
      title: "美股個股線上資料明細",
      loadingText: "正在同步 NYSE Listings Directory 股票清單...",
      emptyText: "目前沒有可顯示的 NYSE 股票資料。",
      failText: "NYSE 股票資料載入失敗，請稍後重新整理。",
      group: "美股個股",
      label: "股票",
      apiKind: "stock",
      apiLimit: 7000,
      fallbackLimit: 7000,
    };
}
function renderUsNyseDirectorySection(kind = "stock") {
  const config = getUsNyseDirectoryConfig(kind);
  const state = usNyseDirectoryState[config.key];
  return `
    <section class="section" id="${config.sectionId}" data-us-nyse-kind="${config.key}">
      <article class="panel-card global-table-card us-nyse-listed-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">${config.kicker}</p>
            <h3>${config.title}</h3>
          </div>
          <span id="${config.countId}" class="chip ${config.key === "etf" ? "chip-gold" : "chip-blue"}">載入中</span>
        </div>
        ${config.key === "etf" ? `
          <div class="tw-etf-list-toolbar us-etf-list-toolbar">
            <form class="search-form tw-etf-filter-form us-etf-filter-form" data-us-nyse-search-form="${config.key}">
              <input id="${config.searchId}" class="tw-etf-filter-input" type="search" value="${escapeHtml(state.query)}" placeholder="搜尋 SPY、QQQ、高股息、債券、半導體...">
              <select id="us-nyse-etf-category">
                ${renderUsEtfCategoryOptions([], state.category || "all")}
              </select>
              <select id="us-nyse-etf-sort">
                ${renderUsEtfSortOptions(state.sort || "return_desc")}
              </select>
              <button class="btn" type="submit">篩選</button>
            </form>
          </div>
        ` : `
          <form class="us-directory-tools" data-us-nyse-search-form="${config.key}">
            <label for="${config.searchId}">搜尋${config.label}</label>
            <input id="${config.searchId}" type="search" value="${escapeHtml(state.query)}" placeholder="輸入代號或名稱，例如 AAPL、Vanguard">
            <button type="submit" class="btn-primary">搜尋</button>
            <button type="button" class="btn-secondary" data-us-nyse-reset="${config.key}">清除</button>
          </form>
        `}
        <p id="${config.statusId}" class="source-note">${config.loadingText}</p>
        <div id="${config.tableId}" class="global-table-wrap">
          <div class="stock-detail-empty">NYSE ${config.label}資料載入中。</div>
        </div>
        <div id="${config.pagerId}" class="us-directory-pager"></div>
      </article>
    </section>
  `;
}
function renderUsNyseListedStocksSection() {
  return renderUsNyseDirectorySection("stock");
}
function renderUsNyseListedEtfsSection() {
  return renderUsNyseDirectorySection("etf");
}
function renderUsEtfDirectoryTable(payload = {}) {
  const config = getUsNyseDirectoryConfig("etf");
  const state = usNyseDirectoryState.etf;
  state.payload = payload;
  if (Array.isArray(payload.quoteItems)) {
    state.quoteItems = payload.quoteItems;
  }
  const target = document.getElementById(config.tableId);
  const count = document.getElementById(config.countId);
  const status = document.getElementById(config.statusId);
  const pager = document.getElementById(config.pagerId);
  if (!target) return;
  const { allRows, rows, pageItems, pageSize, totalItems, totalPages, start, end } = getUsEtfDirectoryPage(payload);
  const activeCategory = state.category || "all";
  const categorySelect = document.getElementById("us-nyse-etf-category");
  const sortSelect = document.getElementById("us-nyse-etf-sort");
  const searchInput = document.getElementById(config.searchId);
  if (categorySelect) categorySelect.innerHTML = renderUsEtfCategoryOptions(allRows, activeCategory);
  if (sortSelect) sortSelect.innerHTML = renderUsEtfSortOptions(state.sort || "return_desc");
  if (searchInput && searchInput.value !== state.query) searchInput.value = state.query || "";
  if (count) {
    count.textContent = totalItems
      ? `${Number(start + 1).toLocaleString("zh-TW")}-${Number(end).toLocaleString("zh-TW")} / ${Number(totalItems).toLocaleString("zh-TW")} 檔`
      : "0 檔";
  }
  if (status) {
    const quoteCount = rows.filter((item) => item.hasQuote).length;
    const categoryText = activeCategory === "all" ? "全部 ETF" : getUsEtfCategoryLabel(activeCategory);
    const rangeText = totalItems
      ? `第 ${Number(start + 1).toLocaleString("zh-TW")} - ${Number(end).toLocaleString("zh-TW")} 筆`
      : "無結果";
    status.textContent = `${payload?.source || "Nasdaq Trader 官方 Symbol Directory"} · 分類：${categoryText} · Yahoo 行情 ${Number(quoteCount).toLocaleString("zh-TW")} 檔 · ${rangeText}${state.query ? ` · 搜尋：${state.query}` : ""}${payload?.error ? ` · 備援資料：${payload.error}` : ""}`;
  }
  if (!rows.length) {
    target.innerHTML = `<div class="stock-detail-empty">${config.emptyText}</div>`;
    if (pager) pager.innerHTML = "";
    return;
  }
  target.innerHTML = `
    <table class="global-market-table us-nyse-listed-table us-etf-list-table">
      <thead>
        <tr>
          <th>代號</th>
          <th>名稱</th>
          <th>分類</th>
          <th>收盤</th>
          <th>漲跌幅</th>
          <th>成交量</th>
          <th>波動</th>
          <th>詳情</th>
        </tr>
      </thead>
      <tbody>
        ${pageItems.map((item) => `
          <tr class="${item.hasQuote ? "" : "is-muted"}">
            <td><a class="global-market-link" href="${safeUrl(buildUsStockSearchUrl(item.symbol))}">${escapeHtml(item.symbol || "--")}</a></td>
            <td>${escapeHtml(item.name || item.symbol || "--")}<br><small>${escapeHtml(item.exchange || item.source || "美股 ETF")}</small></td>
            <td><span class="chip chip-blue">${escapeHtml(item.etfCategoryLabel || "其他")}</span></td>
            <td>${formatGlobalValue(item.close)}</td>
            <td class="${toneClass(item.tone)}">${escapeHtml(item.pct || "--")}</td>
            <td>${formatGlobalVolume(item.volume)}</td>
            <td>${Number.isFinite(item.volatilityPct) ? `${item.volatilityPct.toFixed(2)}%` : "--"}</td>
            <td><button class="btn btn-secondary tw-etf-detail-button" type="button" data-us-etf-detail="${escapeHtml(item.symbol || "")}" title="查看行情、分類與風險" aria-label="查看 ${escapeHtml(item.symbol || "ETF")} 詳情">查看</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  if (pager) {
    const first = totalItems ? start + 1 : 0;
    pager.innerHTML = `
      <span>顯示 <b>${Number(first).toLocaleString("zh-TW")}</b> - <b>${Number(end).toLocaleString("zh-TW")}</b> / ${Number(totalItems).toLocaleString("zh-TW")} 檔</span>
      <label>
        <span>每頁</span>
        <select data-us-nyse-page-size="etf">
          ${US_ETF_PAGE_SIZE_OPTIONS.map((size) => `<option value="${size}"${size === pageSize ? " selected" : ""}>${size}</option>`).join("")}
        </select>
      </label>
      <button type="button" data-us-nyse-page="etf" data-page="first" ${state.page <= 1 ? "disabled" : ""}>第一頁</button>
      <button type="button" data-us-nyse-page="etf" data-page="prev" ${state.page <= 1 ? "disabled" : ""}>上一頁</button>
      <span>第 <b>${state.page}</b> / ${totalPages} 頁</span>
      <button type="button" data-us-nyse-page="etf" data-page="next" ${state.page >= totalPages ? "disabled" : ""}>下一頁</button>
      <button type="button" data-us-nyse-page="etf" data-page="last" ${state.page >= totalPages ? "disabled" : ""}>最後頁</button>
    `;
  }
}
function findUsEtfDirectoryRow(symbol, payload = usNyseDirectoryState.etf.payload) {
  const key = normalizeUsEtfSymbolKey(symbol);
  return buildUsEtfDirectoryRows(payload || {}).find((item) => normalizeUsEtfSymbolKey(item.symbol) === key) || {};
}
function getUsEtfDetailTone(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "flat";
  if (parsed > 0) return "up";
  if (parsed < 0) return "down";
  return "flat";
}
function getUsEtfDetailSignals(item = {}, stats = {}, dailyPct = null, volume = null) {
  const categoryKey = getUsEtfCategoryKey(item);
  const returnPct = Number.isFinite(stats.returnPct) ? stats.returnPct : null;
  const volatility = Number.isFinite(stats.volatility) ? stats.volatility : null;
  const drawdown = Number.isFinite(stats.maxDrawdown) ? stats.maxDrawdown : null;
  const sharpe = Number.isFinite(stats.sharpe) ? stats.sharpe : null;
  const volumeValue = parseMarketNumber(volume);
  const dailyTone = getUsEtfDetailTone(dailyPct);
  const trendTone = getUsEtfDetailTone(returnPct);
  const trendLabel = returnPct === null
    ? "趨勢待同步"
    : returnPct >= 12
      ? "區間動能強"
      : returnPct >= 0
        ? "區間偏多"
        : returnPct <= -20
          ? "區間承壓"
          : "區間修正";
  const riskLabel = ["leveraged", "crypto"].includes(categoryKey)
    ? "高風險工具"
    : volatility === null
      ? "風險待同步"
      : volatility >= 45
        ? "高波動"
        : volatility >= 25
          ? "中高波動"
          : "波動較穩";
  const liquidityLabel = volumeValue === null
    ? "流動性待同步"
    : volumeValue >= 10000000
      ? "流動性充足"
      : volumeValue >= 1000000
        ? "流動性普通"
        : "流動性偏低";
  return {
    categoryKey,
    dailyTone,
    trendTone,
    trendLabel,
    riskLabel,
    liquidityLabel,
    returnPct,
    volatility,
    drawdown,
    sharpe,
    volumeValue,
  };
}
function getUsEtfDetailPositionInsight(item = {}, categoryLabel = "ETF", signals = {}, metrics = {}) {
  const categoryKey = signals.categoryKey || getUsEtfCategoryKey(item);
  const trend = signals.trendLabel || "趨勢待同步";
  const symbol = String(item.symbol || "").toUpperCase() || "此 ETF";
  const templates = {
    market: {
      lead: `${symbol} 屬於核心大盤曝險，可用來觀察美股主線是否延續。`,
      points: [`目前趨勢為「${trend}」，適合和 SPY、QQQ、VTI 等核心 ETF 做相對強弱比較。`, "若成交量同步放大，代表資金對大盤方向的確認度較高。"],
    },
    sector: {
      lead: `${symbol} 偏向產業輪動工具，重點在追蹤資金是否集中到特定產業。`,
      points: [`分類為「${categoryLabel}」，可搭配同產業 ETF 與龍頭股確認輪動是否延續。`, `區間績效 ${metrics.returnText || "--"}，若量能沒有跟上，容易變成短線題材反彈。`],
    },
    leveraged: {
      lead: `${symbol} 是槓桿 / 反向型工具，定位偏短線戰術，不適合用核心配置邏輯看待。`,
      points: ["重點是方向、時間與停損，不宜用長期持有假設評估。", "每日重置會讓長期報酬偏離標的，震盪盤尤其需要控管部位。"],
    },
    bond: {
      lead: `${symbol} 偏向利率或信用曝險工具，可用來觀察資金是否轉向防守。`,
      points: ["價格通常受殖利率、久期與信用利差影響。", `目前趨勢為「${trend}」，需搭配美債殖利率方向判讀。`],
    },
    dividend: {
      lead: `${symbol} 偏收益配置，重點是股息來源、波動控制與價格穩定性。`,
      points: ["適合和高股息、covered call 或收益型 ETF 做同類比較。", "若價格趨勢轉弱，配息吸引力可能被本金波動抵銷。"],
    },
    international: {
      lead: `${symbol} 提供美國以外或特定區域曝險，可作為分散配置觀察。`,
      points: ["除了 ETF 本身走勢，也要留意美元、區域政策與匯率波動。", `目前區間績效 ${metrics.returnText || "--"}，可和美股大盤 ETF 做強弱比較。`],
    },
    factor: {
      lead: `${symbol} 屬於風格因子配置，用來觀察成長、價值、品質或低波動風格輪動。`,
      points: ["適合搭配大盤 ETF，看目前市場是追逐 beta 還是偏好特定因子。", `目前趨勢為「${trend}」，若 Sharpe 改善，代表風險調整後動能較有支撐。`],
    },
    commodity: {
      lead: `${symbol} 偏商品或避險題材，常受美元、利率、通膨與供需事件影響。`,
      points: ["不宜只看股市方向，需同步觀察美元與商品現貨脈絡。", "若單日漲跌擴大，通常代表事件或避險情緒正在升溫。"],
    },
    crypto: {
      lead: `${symbol} 連動加密資產，定位是高波動題材曝險而非傳統核心 ETF。`,
      points: ["適合小比例觀察風險偏好，不宜用低波動資產的方式配置。", "需留意加密現貨、監管消息與週末跳空風險。"],
    },
    thematic: {
      lead: `${symbol} 屬於主題型 ETF，重點在成長敘事是否轉化成量價延續。`,
      points: ["主題 ETF 常有持股集中與估值波動，需觀察龍頭股是否同步轉強。", `目前區間績效 ${metrics.returnText || "--"}，若回撤擴大要降低追價。`],
    },
    other: {
      lead: `${symbol} 可作為 ETF 觀察名單的一部分，先用流動性、趨勢與風險辨識用途。`,
      points: [`目前分類為「${categoryLabel}」，適合先和同類 ETF 排行比較。`, "資料不足時以官方清單為主，不把缺行情 ETF 當成已驗證交易標的。"],
    },
  };
  return templates[categoryKey] || templates.other;
}
function getUsEtfDetailRiskInsight(item = {}, signals = {}, metrics = {}) {
  const categoryKey = signals.categoryKey || getUsEtfCategoryKey(item);
  const points = [];
  if (Number.isFinite(signals.volatility)) points.push(`年化波動約 ${metrics.volatilityText}，最大回撤 ${metrics.drawdownText}，先判斷是否符合自己的部位承受度。`);
  else points.push("波動資料尚未完整，風險判斷以清單分類與成交量先行。");
  if (signals.liquidityLabel === "流動性偏低") points.push(`成交量 ${metrics.volumeText} 偏低，進出場可能有滑價與買賣價差風險。`);
  else if (signals.liquidityLabel === "流動性充足") points.push(`成交量 ${metrics.volumeText}，流動性相對充足，但高波動時仍需分批。`);
  else points.push(`成交量 ${metrics.volumeText}，流動性需和同類 ETF 比較後再判斷。`);
  if (["leveraged", "crypto"].includes(categoryKey)) {
    points.push("此類 ETF 容易因高波動、重置或事件風險放大損益，宜設定明確停損與持有時間。");
  } else if (Number.isFinite(signals.returnPct) && signals.returnPct < 0) {
    points.push("區間績效偏弱時，反彈需搭配量能與同類 ETF 同步轉強，避免只追單日反彈。");
  } else {
    points.push("若趨勢延續但波動升高，仍要用分批與停損管理追價風險。");
  }
  return {
    lead: `${signals.riskLabel || "風險觀察"}：風險不是只看漲跌，還要同時看波動、回撤與流動性。`,
    points,
  };
}
function renderUsEtfSourceStep(label, status, sourceText, note, tone = "flat") {
  const chipClass = tone === "up" ? "chip-green" : tone === "down" ? "chip-red" : "chip-blue";
  return `
    <section class="us-etf-source-step">
      <div>
        <b>${escapeHtml(label)}</b>
        <span class="chip ${chipClass}">${escapeHtml(status)}</span>
      </div>
      <strong>${escapeHtml(sourceText)}</strong>
      <p>${escapeHtml(note)}</p>
    </section>
  `;
}
function renderUsEtfComponentsCard(components = {}, symbol = "") {
  const holdings = Array.isArray(components.holdings) ? components.holdings : [];
  return `
    <article class="panel-card etf-components-card tw-etf-components-card us-etf-components-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">ETF Holdings</p>
          <h3>${escapeHtml(components.title || "ETF 成分股比例")}</h3>
          <p class="chart-subtitle">${escapeHtml(components.summary || "美股 ETF 成分資料優先取 Yahoo Finance Top Holdings；實際權重仍以發行商公告為準。")}</p>
        </div>
        <span class="chip chip-blue">${holdings.length ? `${holdings.length} 項配置` : "資料待補"}</span>
      </div>
      <div class="etf-holding-list">
        ${holdings.map((item) => {
          const weight = Math.max(0, Math.min(100, Number(item.weight) || 0));
          return `
            <div class="etf-holding-row">
              <div>
                <strong>${escapeHtml(item.name || "--")}</strong>
                <span>${escapeHtml(item.code || "--")}</span>
              </div>
              <div class="etf-holding-bar"><i style="width:${weight}%"></i></div>
              <b>${twEtfWeightText(weight)}</b>
            </div>
          `;
        }).join("") || '<p class="stock-detail-empty">此 ETF 尚未取得成分股比例資料。</p>'}
      </div>
      <p class="stock-theory-note">${escapeHtml(components.sourceNote || "成分股比例請以發行商公告為準。")} ${components.sourceLink ? `<a href="${safeUrl(components.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : symbol ? `<a href="${safeUrl(`${buildYahooFinanceUrl(symbol)}/holdings`)}" target="_blank" rel="noreferrer noopener">Yahoo holdings</a>` : ""}</p>
    </article>
  `;
}
function renderUsEtfIncomeCard(symbolDetail = {}, valuation = {}) {
  const history = Array.isArray(symbolDetail.valuationHistory) ? symbolDetail.valuationHistory : [];
  const latest = {
    cashDividend: valuation.dividendPerShare,
    dividendYield: valuation.dividendYield,
    expenseRatio: valuation.expenseRatio,
    aum: valuation.aum,
    beta: valuation.beta,
    range: valuation.fiftyTwoWeekRange,
  };
  const hasValue = (value) => {
    const text = String(value ?? "").trim();
    return Boolean(text) && !["--", "-", "N/A", "NA", "--%"].includes(text.toUpperCase());
  };
  return `
    <article class="panel-card etf-dividend-card tw-etf-dividend-card us-etf-income-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">ETF Dividend</p>
          <h3>ETF 股利與收益資訊</h3>
          <p class="chart-subtitle">美股 ETF 以 Yahoo / Nasdaq 可取得的年化股息、股息率、AUM 與費用率呈現；實際配息頻率請核對發行商。</p>
        </div>
        <span class="chip chip-gold">${hasValue(latest.dividendYield) ? `${escapeHtml(latest.dividendYield)}%` : "收益待補"}</span>
      </div>
      <div class="etf-dividend-metrics">
        <div><span>年化股息</span><strong>${escapeHtml(latest.cashDividend || "--")} USD</strong></div>
        <div><span>股息率</span><strong>${escapeHtml(latest.dividendYield || "--")}%</strong></div>
        <div><span>費用率</span><strong>${escapeHtml(latest.expenseRatio || "--")}</strong></div>
        <div><span>AUM</span><strong>${escapeHtml(latest.aum || valuation.marketCap || "--")}</strong></div>
        <div><span>Beta</span><strong>${escapeHtml(latest.beta || "--")}</strong></div>
        <div><span>52 週區間</span><strong>${escapeHtml(latest.range || "--")}</strong></div>
      </div>
      <div class="etf-dividend-list">
        ${history.slice(-6).reverse().map((item) => `
          <div class="etf-dividend-row">
            <div>
              <strong>${escapeHtml(item.date || "--")}</strong>
              <span>月末收盤 ${escapeHtml(item.close ?? "--")} USD</span>
            </div>
            <div>
              <b>${escapeHtml(item.dividendPerShare ?? "--")} USD</b>
              <small>股息率 ${escapeHtml(item.dividendYield ?? "--")}% · PB ${escapeHtml(item.pbRatio ?? "--")}</small>
            </div>
          </div>
        `).join("") || '<p class="stock-detail-empty">尚未取得 ETF 配息或收益歷史資料。</p>'}
      </div>
      <p class="stock-theory-note">${escapeHtml(valuation.sourceNote || "美股 ETF 股利資料請以發行商公告、Yahoo Finance 與 Nasdaq 公開資料交叉核對。")}</p>
    </article>
  `;
}
function renderUsEtfDetail(detail, fallbackItem = {}) {
  const root = document.getElementById("us-etf-detail");
  if (!root) return;
  if (!detail) {
    root.innerHTML = '<article class="panel-card"><p class="stock-detail-empty">點選 ETF 後，這裡會顯示配息、成分股、風險摘要與資料來源。</p></article>';
    return;
  }
  const directoryItem = detail.directoryItem || fallbackItem || {};
  const quoteItem = detail.quoteItem || fallbackItem.quoteItem || {};
  const symbolDetail = detail.symbolDetail || {};
  const valuation = symbolDetail.valuation || {};
  const components = symbolDetail.etfComponents || {};
  const enriched = enrichUsEtfDirectoryItems([directoryItem])[0] || {};
  const symbol = String(directoryItem.symbol || quoteItem.symbol || fallbackItem.symbol || "").toUpperCase();
  const name = directoryItem.name || quoteItem.name || fallbackItem.name || symbol || "ETF";
  const hasQuote = Boolean(quoteItem && Object.keys(quoteItem).length && !quoteItem.error);
  const stats = hasQuote ? getUsEtfReturnStats(quoteItem) : {
    returnPct: fallbackItem.returnPct,
    volatility: fallbackItem.volatilityPct,
  };
  const dailyPct = parseMarketNumber(quoteItem.pct ?? fallbackItem.pct);
  const tone = dailyPct > 0 ? "up" : dailyPct < 0 ? "down" : "flat";
  const close = quoteItem.close ?? fallbackItem.close;
  const pct = quoteItem.pct ?? fallbackItem.pct ?? "--";
  const volume = quoteItem.volume ?? fallbackItem.volume;
  const exchange = directoryItem.exchange || quoteItem.exchange || fallbackItem.exchange || "--";
  const categoryLabel = enriched.etfCategoryLabel || fallbackItem.etfCategoryLabel || "其他";
  const source = detail.source || quoteItem.dataSource || directoryItem.source || fallbackItem.source || "美股 ETF 線上清單";
  const signals = getUsEtfDetailSignals({ ...directoryItem, ...quoteItem }, stats, dailyPct, volume);
  const sourceNote = hasQuote
    ? "Yahoo Finance 行情已同步；官方上市資料來自 Nasdaq Trader Symbol Directory 或 NYSE Listings Directory。"
    : "此檔目前尚未取得 Yahoo 行情，先顯示官方清單資料。";
  const trendText = Number.isFinite(stats.returnPct)
    ? `近期績效 ${formatSignedPercentValue(stats.returnPct)}，日漲跌 ${pct}。`
    : `日漲跌 ${pct}，近期績效資料仍在同步。`;
  const categoryInsight = getUsEtfPopularThemeNote({ ...directoryItem, ...quoteItem }, stats);
  const riskInsight = getUsEtfPopularRiskText({ ...directoryItem, ...quoteItem }, stats);
  const drawdownText = Number.isFinite(signals.drawdown) ? formatSignedPercentValue(signals.drawdown) : "--";
  const sharpeText = Number.isFinite(signals.sharpe) ? signals.sharpe.toFixed(2) : "--";
  const volatilityText = Number.isFinite(signals.volatility) ? `${signals.volatility.toFixed(2)}%` : "--";
  const returnText = formatSignedPercentValue(signals.returnPct);
  const dailyText = Number.isFinite(dailyPct) ? formatSignedPercentValue(dailyPct) : pct;
  const directorySourceText = directoryItem.source || detail.directorySource || "Nasdaq Trader Symbol Directory";
  const quoteSourceText = hasQuote ? quoteItem.dataSource || "Yahoo Finance 美股 ETF 行情" : "尚未同步 Yahoo 行情";
  const qualityScore = [Boolean(directoryItem.symbol), hasQuote, Number.isFinite(signals.returnPct), Number.isFinite(signals.volatility)].filter(Boolean).length;
  const qualityLabel = qualityScore >= 4 ? "完整" : qualityScore >= 2 ? "可用" : "清單優先";
  const qualityTone = qualityScore >= 4 ? "up" : qualityScore >= 2 ? "flat" : "down";
  const positionInsight = getUsEtfDetailPositionInsight({ ...directoryItem, ...quoteItem }, categoryLabel, signals, { returnText, dailyText });
  const riskBriefInsight = getUsEtfDetailRiskInsight({ ...directoryItem, ...quoteItem }, signals, {
    volatilityText,
    drawdownText,
    volumeText: formatGlobalVolume(volume),
  });
  const holdings = Array.isArray(components.holdings) ? components.holdings : [];
  const topHolding = holdings[0] || {};
  const topWeight = Number(topHolding.weight);
  const dividendYield = valuation.dividendYield;
  const annualDividend = valuation.dividendPerShare;
  const bullets = [
    `${categoryLabel}：${positionInsight.lead}`,
    holdings.length
      ? `成分配置：${topHolding.name || "最大配置"}${Number.isFinite(topWeight) ? ` 約 ${twEtfWeightText(topWeight)}` : ""}，用來判斷集中度與主要風格曝險。`
      : "成分配置：目前未取得完整持股明細，先以 ETF 名稱、分類與行情做配置判讀，仍以發行商公告為準。",
    dividendYield && !["N/A", "NA", "--", "-"].includes(String(dividendYield).toUpperCase())
      ? `收益觀察：股息率 ${dividendYield}%${annualDividend ? `，年化股息 ${annualDividend} USD` : ""}，需搭配除息日與配息頻率核對。`
      : "收益觀察：尚未取得可用股息率或年化股息，收益型 ETF 需再查發行商配息頁。",
    `交易風險：成交量 ${formatGlobalVolume(volume)}，波動 ${volatilityText}，最大回撤 ${drawdownText}，目前風險判定為 ${signals.riskLabel || "--"}。`,
  ];
  root.innerHTML = `
    <div class="tw-etf-detail-layout us-etf-detail-layout">
      <article class="panel-card tw-etf-analysis-card us-etf-detail-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">ETF Analysis</p>
            <h3>${escapeHtml(symbol)} ${escapeHtml(name)}</h3>
            <p class="chart-subtitle">整合行情、分類、風險、美股 ETF 成分股比例與股利收益資訊，作為篩選後的分析摘要。</p>
          </div>
          <span class="chip chip-gold">${escapeHtml(categoryLabel)}</span>
        </div>
        <div class="headline-metrics tw-etf-detail-metrics">
          <div><span>收盤</span><strong>${escapeHtml(formatGlobalValue(close))}</strong><small class="${toneClass(tone)}">${escapeHtml(pct)}</small></div>
          <div><span>風險分級</span><strong>${escapeHtml(signals.riskLabel || "--")}</strong><small>波動 ${escapeHtml(volatilityText)}</small></div>
          <div><span>成交量</span><strong>${escapeHtml(formatGlobalVolume(volume))}</strong><small>${escapeHtml(signals.liquidityLabel || "--")}</small></div>
          <div><span>股息率</span><strong>${escapeHtml(dividendYield || "--")}%</strong><small>年化 ${escapeHtml(annualDividend || "--")} USD</small></div>
        </div>
        <div class="tw-etf-analysis-notes">
          ${bullets.map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
        </div>
        <div class="us-etf-detail-actions">
          <a class="btn btn-primary" href="${safeUrl(buildYahooFinanceUrl(symbol))}" target="_blank" rel="noopener noreferrer">Yahoo Finance</a>
          <a class="btn btn-secondary" href="${safeUrl(buildUsStockSearchUrl(symbol))}">美股搜尋</a>
        </div>
      </article>
      <div class="tw-etf-detail-grid">
        ${renderUsEtfComponentsCard(components, symbol)}
        ${renderUsEtfIncomeCard(symbolDetail, valuation)}
        <article class="panel-card us-etf-detail-source-card">
          <div class="us-etf-source-head">
            <div>
              <p class="panel-kicker">Data source</p>
              <h3>資料來源</h3>
              <p>拆分官方清單、行情、成分股與衍生指標，避免把不同來源混成同一個數字。</p>
            </div>
            <span class="chip ${qualityTone === "up" ? "chip-green" : qualityTone === "down" ? "chip-red" : "chip-blue"}">資料${qualityLabel}</span>
          </div>
          <div class="us-etf-source-timeline">
            ${renderUsEtfSourceStep("1 官方清單", directoryItem.symbol ? "已匹配" : "待匹配", directorySourceText, `確認 ${symbol || "ETF"} 是否為美股 ETF、交易所與上市名稱。`, directoryItem.symbol ? "up" : "flat")}
            ${renderUsEtfSourceStep("2 Yahoo 行情", hasQuote ? "已同步" : "待同步", quoteSourceText, hasQuote ? "提供收盤、漲跌、成交量與近期價格序列。" : "行情缺值時保留官方清單，不使用假價格。", hasQuote ? "up" : "down")}
            ${renderUsEtfSourceStep("3 成分 / 收益", holdings.length || annualDividend ? "已同步" : "待同步", "Yahoo quote summary / Top Holdings", "提供 ETF 持股、年化股息、股息率、AUM 與費用率；缺漏時保留資料待補。", holdings.length || annualDividend ? "up" : "flat")}
            ${renderUsEtfSourceStep("4 風險指標", Number.isFinite(signals.volatility) ? "已計算" : "待計算", `波動 ${volatilityText} / 回撤 ${drawdownText}`, "由 Yahoo 價格序列推估區間績效、波動、回撤與 Sharpe。", Number.isFinite(signals.volatility) ? "up" : "flat")}
          </div>
          <div class="company-news-sources">
            <a href="${safeUrl(buildYahooFinanceUrl(symbol))}" target="_blank" rel="noopener noreferrer">Yahoo Finance</a>
            <a href="${safeUrl(`${buildYahooFinanceUrl(symbol)}/holdings`)}" target="_blank" rel="noopener noreferrer">Yahoo Holdings</a>
            <a href="${safeUrl(`https://www.nasdaq.com/market-activity/etf/${encodeURIComponent(symbol.toLowerCase())}`)}" target="_blank" rel="noopener noreferrer">Nasdaq ETF</a>
          </div>
          <p class="stock-theory-note">${escapeHtml(`${sourceNote} 目前 API 組合：${source}`)}</p>
        </article>
      </div>
    </div>
  `;
}
async function loadUsEtfDetail(symbol, fallbackItem = {}) {
  const root = document.getElementById("us-etf-detail");
  if (!root) return;
  const cleanSymbol = String(symbol || "").trim().toUpperCase();
  if (!cleanSymbol) return;
  root.innerHTML = '<article class="panel-card"><p class="stock-detail-empty">正在載入美股 ETF 行情與明細資料...</p></article>';
  usEtfSelectedSymbol = cleanSymbol;
  try {
    const [response, symbolResponse] = await Promise.all([
      fetchWithTimeout(`/api/us-market/etf-center?directoryLimit=80&quoteLimit=12&q=${encodeURIComponent(cleanSymbol)}`, { cache: "no-store" }, 120000),
      fetchWithTimeout(`/api/us-market/symbol/${encodeURIComponent(cleanSymbol)}`, { cache: "no-store" }, 24000).catch(() => null),
    ]);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    const symbolDetail = symbolResponse?.ok ? await symbolResponse.json() : {};
    const directoryRows = enrichUsEtfDirectoryItems(payload.directory?.results || []);
    const key = normalizeUsEtfSymbolKey(cleanSymbol);
    const directoryItem = directoryRows.find((item) => normalizeUsEtfSymbolKey(item.symbol) === key)
      || directoryRows[0]
      || fallbackItem;
    const quoteItem = (payload.items || []).find((item) => normalizeUsEtfSymbolKey(item.symbol) === key)
      || (payload.items || [])[0]
      || fallbackItem.quoteItem
      || {};
    if (quoteItem.symbol) {
      usNyseDirectoryState.etf.quoteItems = [
        quoteItem,
        ...(usNyseDirectoryState.etf.quoteItems || []).filter((item) => normalizeUsEtfSymbolKey(item.symbol) !== normalizeUsEtfSymbolKey(quoteItem.symbol)),
      ];
    }
    if (usEtfSelectedSymbol === cleanSymbol) {
      renderUsEtfDetail({
        directoryItem,
        quoteItem,
        symbolDetail,
        source: payload.source,
        directorySource: payload.directory?.source,
        updatedAt: payload.updatedAt,
      }, fallbackItem);
    }
  } catch (error) {
    if (usEtfSelectedSymbol === cleanSymbol) {
      renderUsEtfDetail({
        directoryItem: fallbackItem,
        quoteItem: fallbackItem.quoteItem || {},
        source: `資料載入失敗：${error.message || error}`,
        updatedAt: "--",
      }, fallbackItem);
    }
  }
}
function renderUsNyseDirectoryTable(kind, payload) {
  const config = getUsNyseDirectoryConfig(kind);
  const state = usNyseDirectoryState[config.key];
  state.payload = payload;
  if (config.key === "etf") {
    renderUsEtfDirectoryTable(payload);
    return;
  }
  const target = document.getElementById(config.tableId);
  const count = document.getElementById(config.countId);
  const status = document.getElementById(config.statusId);
  const pager = document.getElementById(config.pagerId);
  if (!target) return;
  const rawResults = payload?.results || [];
  const allResults = config.key === "etf" ? enrichUsEtfDirectoryItems(rawResults) : rawResults;
  const activeCategory = config.key === "etf" ? state.category || "all" : "all";
  const results = config.key === "etf" && activeCategory !== "all"
    ? allResults.filter((item) => item.etfCategoryKey === activeCategory)
    : allResults;
  const total = config.key === "etf" ? results.length : payload?.total || payload?.count || 0;
  const categoryFilters = config.key === "etf" ? document.getElementById("us-nyse-etf-category-filters") : null;
  if (categoryFilters) categoryFilters.innerHTML = renderUsEtfCategoryFilters(allResults, activeCategory);
  const totalPages = Math.max(Math.ceil(results.length / US_NYSE_DIRECTORY_PAGE_SIZE), 1);
  state.page = Math.max(1, Math.min(state.page || 1, totalPages));
  const start = (state.page - 1) * US_NYSE_DIRECTORY_PAGE_SIZE;
  const pageItems = results.slice(start, start + US_NYSE_DIRECTORY_PAGE_SIZE);
  if (count) {
    count.textContent = config.key === "etf"
      ? `${getUsEtfCategoryLabel(activeCategory)}：${Number(results.length).toLocaleString("zh-TW")} / ${Number(allResults.length).toLocaleString("zh-TW")}`
      : `NYSE ${config.label}總數：${Number(total).toLocaleString("zh-TW")}`;
  }
  if (status) {
    const rangeText = results.length ? `第 ${Number(start + 1).toLocaleString("zh-TW")} - ${Number(Math.min(start + pageItems.length, results.length)).toLocaleString("zh-TW")} 筆` : "無結果";
    const categoryText = config.key === "etf" ? ` · 分類：${getUsEtfCategoryLabel(activeCategory)}` : "";
    status.textContent = `${payload?.source || "NYSE Listings Directory"} · 已載入 ${Number(allResults.length).toLocaleString("zh-TW")} 筆${categoryText} · ${rangeText}${state.query ? ` · 搜尋：${state.query}` : ""}${payload?.error ? ` · 備援資料：${payload.error}` : ""}`;
  }
  if (!results.length) {
    target.innerHTML = `<div class="stock-detail-empty">${config.emptyText}</div>`;
    if (pager) pager.innerHTML = "";
    return;
  }
  target.innerHTML = `
    <table class="global-market-table us-nyse-listed-table">
      <thead>
        <tr>
          <th>名稱</th>
          <th>代號</th>
          <th>交易所</th>
          <th>${config.key === "etf" ? "整理分類" : "分類"}</th>
          <th>資料來源</th>
        </tr>
      </thead>
      <tbody>
        ${pageItems.map((item) => `
          <tr>
            <td><a class="global-market-link" href="${safeUrl(buildUsStockSearchUrl(item.symbol))}">${escapeHtml(item.name || item.symbol || "--")}</a></td>
            <td>${escapeHtml(item.symbol || "--")}</td>
            <td>${escapeHtml(item.exchange || "NYSE")}</td>
            <td>${config.key === "etf" ? `<span class="chip chip-blue">${escapeHtml(item.etfCategoryLabel || "其他")}</span>` : escapeHtml(item.group || item.type || config.group)}</td>
            <td>${item.nyseUrl ? `<a class="global-market-link" href="${safeUrl(item.nyseUrl)}" target="_blank" rel="noopener noreferrer">NYSE</a>` : escapeHtml(item.source || "NYSE")}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  if (pager) {
    pager.innerHTML = `
      <button type="button" data-us-nyse-page="${config.key}" data-page="first" ${state.page <= 1 ? "disabled" : ""}>第一頁</button>
      <button type="button" data-us-nyse-page="${config.key}" data-page="prev" ${state.page <= 1 ? "disabled" : ""}>上一頁</button>
      <span>第 <b>${state.page}</b> / ${totalPages} 頁，每頁 ${US_NYSE_DIRECTORY_PAGE_SIZE} 筆</span>
      <button type="button" data-us-nyse-page="${config.key}" data-page="next" ${state.page >= totalPages ? "disabled" : ""}>下一頁</button>
      <button type="button" data-us-nyse-page="${config.key}" data-page="last" ${state.page >= totalPages ? "disabled" : ""}>最後頁</button>
    `;
  }
}
function renderUsNyseListedStocksTable(payload) {
  renderUsNyseDirectoryTable("stock", payload);
}
function renderUsNyseListedEtfsTable(payload) {
  renderUsNyseDirectoryTable("etf", payload);
}
async function loadUsNyseDirectory(kind = "stock") {
  const config = getUsNyseDirectoryConfig(kind);
  const state = usNyseDirectoryState[config.key];
  if (!document.getElementById(config.tableId)) return;
  const queryParam = state.query ? `&q=${encodeURIComponent(state.query)}` : "";
  try {
    let payload;
    try {
      const primaryUrl = config.key === "etf"
        ? `/api/us-market/etf-center?directoryLimit=${config.apiLimit}&quoteLimit=56${queryParam}`
        : `/api/us-market/nyse-listed?kind=${config.apiKind}&limit=${config.apiLimit}${queryParam}`;
      const response = await fetchWithTimeout(primaryUrl, { cache: "no-store" }, config.key === "etf" ? 120000 : 22000);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const primaryPayload = await response.json();
      if (config.key === "etf") {
        payload = primaryPayload.directory || primaryPayload;
        payload.quoteItems = primaryPayload.items || [];
        state.quoteItems = primaryPayload.items || [];
      } else {
        payload = primaryPayload;
      }
    } catch (primaryError) {
      const fallbackResponse = await fetchWithTimeout(`/api/us-market/listed?limit=${config.fallbackLimit}${queryParam}`, { cache: "no-store" }, 22000);
      if (!fallbackResponse.ok) throw primaryError;
      const fallbackPayload = await fallbackResponse.json();
      const filtered = (fallbackPayload.results || []).filter((item) => item.group === config.group);
      payload = {
        ...fallbackPayload,
        source: `${fallbackPayload.source || "Nasdaq Trader 官方 Symbol Directory"}（NYSE API 備援）`,
        total: state.query ? filtered.length : fallbackPayload.totals?.[config.group] || filtered.length,
        count: filtered.length,
        returned: filtered.length,
        results: filtered,
        error: primaryError?.message || String(primaryError),
      };
    }
    renderUsNyseDirectoryTable(config.key, payload);
  } catch (error) {
    const target = document.getElementById(config.tableId);
    const status = document.getElementById(config.statusId);
    if (status) status.textContent = `${config.label}資料暫時無法載入：${error.message || error}`;
    if (target) target.innerHTML = `<div class="stock-detail-empty">${config.failText}</div>`;
  }
}
async function loadUsNyseListedEtfs() {
  await loadUsNyseDirectory("etf");
}
function getUsEtfMarketItems(payload = {}) {
  return (payload.items || []).filter((item) => item.group === "美股 ETF" && !item.error);
}
function getUsEtfDirectoryItems(payload = {}) {
  return payload.directory?.results || [];
}
function getUsEtfReturnStats(item = {}) {
  const series = normalizeGlobalSeries(item.series || []);
  if (series.length < 2) {
    return {
      returnPct: parseMarketNumber(item.periodReturn),
      volatility: null,
      sharpe: null,
      maxDrawdown: null,
      latestClose: parseMarketNumber(item.close),
    };
  }
  const first = series[0].value;
  const last = series.at(-1).value;
  const returns = [];
  for (let index = 1; index < series.length; index += 1) {
    const previous = series[index - 1].value;
    const current = series[index].value;
    if (Number.isFinite(previous) && previous !== 0 && Number.isFinite(current)) {
      returns.push((current - previous) / previous);
    }
  }
  const average = returns.length ? returns.reduce((sum, value) => sum + value, 0) / returns.length : null;
  const variance = returns.length && Number.isFinite(average)
    ? returns.reduce((sum, value) => sum + ((value - average) ** 2), 0) / returns.length
    : null;
  const dailyStd = Number.isFinite(variance) ? Math.sqrt(variance) : null;
  let runningHigh = first;
  let maxDrawdown = 0;
  series.forEach((point) => {
    if (point.value > runningHigh) runningHigh = point.value;
    if (runningHigh > 0) {
      const drawdown = ((point.value - runningHigh) / runningHigh) * 100;
      if (drawdown < maxDrawdown) maxDrawdown = drawdown;
    }
  });
  return {
    returnPct: first ? ((last - first) / first) * 100 : null,
    volatility: Number.isFinite(dailyStd) ? dailyStd * Math.sqrt(252) * 100 : null,
    sharpe: Number.isFinite(average) && dailyStd ? (average / dailyStd) * Math.sqrt(252) : null,
    maxDrawdown,
    latestClose: last,
  };
}
function getUsEtfRankedItems(items = [], mode = "performance", limit = 6) {
  const withStats = items.map((item) => ({ item, stats: getUsEtfReturnStats(item) }));
  if (mode === "volume") {
    return withStats
      .sort((left, right) => (parseMarketNumber(right.item.volume) || 0) - (parseMarketNumber(left.item.volume) || 0))
      .slice(0, limit);
  }
  if (mode === "risk") {
    return withStats
      .sort((left, right) => (right.stats.volatility || 0) - (left.stats.volatility || 0))
      .slice(0, limit);
  }
  return withStats
    .sort((left, right) => (right.stats.returnPct || -Infinity) - (left.stats.returnPct || -Infinity))
    .slice(0, limit);
}
function getUsEtfComparisonItems(items = []) {
  const preferred = ["SPY", "QQQ", "VOO", "IVV", "VTI", "IWM", "SCHD", "TLT", "GLD", "IBIT", "TQQQ"];
  const bySymbol = new Map(items.map((item) => [String(item.symbol || "").toUpperCase(), item]));
  const selected = preferred.map((symbol) => bySymbol.get(symbol)).filter(Boolean);
  if (selected.length >= 5) return selected;
  return [...selected, ...items.filter((item) => !selected.includes(item)).slice(0, 8 - selected.length)];
}
function renderUsEtfRankRows(rankItems = [], metric = "performance") {
  return rankItems.map(({ item, stats }, index) => {
    const metricText = metric === "volume"
      ? formatGlobalVolume(item.volume)
      : metric === "risk"
        ? formatSignedPercentValue(stats.volatility, 1).replace("+", "")
        : formatSignedPercentValue(stats.returnPct);
    const metricLabel = metric === "volume" ? "成交量" : metric === "risk" ? "年化波動" : "區間績效";
    return `
      <a class="us-etf-rank-row" href="${safeUrl(buildUsStockSearchUrl(item.symbol))}">
        <span>${index + 1}</span>
        <div>
          <strong>${escapeHtml(item.symbol || "--")}</strong>
          <small>${escapeHtml(item.name || "--")}</small>
        </div>
        <b>${escapeHtml(metricText)}</b>
        <em>${metricLabel}</em>
      </a>
    `;
  }).join("") || '<p class="stock-detail-empty">ETF 行情資料同步中。</p>';
}
function renderUsEtfPageHero(payload = {}) {
  return `
    <section class="subpage-hero global-market-hero us-etf-hero">
      <p class="eyebrow">US ETF Center</p>
      <h1>美股ETF</h1>
      <p class="hero-text">依股票、債券、科技、AI、半導體、能源、金融、醫療、REIT、商品、黃金、比特幣、槓桿與反向 ETF 分類，整合市場總覽、排行、比較、成分、配息、風險與 AI 分析。</p>
      <p class="source-note">資料來源：${escapeHtml(payload.source || "Yahoo Finance / NYSE Listings Directory")} · 更新時間 ${escapeHtml(payload.updatedAt || "--")}</p>
    </section>
  `;
}
function renderUsEtfOverview(payload = {}) {
  const items = getUsEtfMarketItems(payload);
  const directoryItems = getUsEtfDirectoryItems(payload);
  const categorySource = directoryItems.length ? directoryItems : items;
  const enriched = enrichUsEtfDirectoryItems(categorySource);
  const advancers = items.filter((item) => (parseMarketNumber(item.pct) || 0) > 0).length;
  const decliners = items.filter((item) => (parseMarketNumber(item.pct) || 0) < 0).length;
  const avgPct = items.length
    ? items.reduce((sum, item) => sum + (parseMarketNumber(item.pct) || 0), 0) / items.length
    : null;
  const volumeLeaders = getUsEtfRankedItems(items, "volume", 5);
  const directoryTotal = payload.directory?.total || directoryItems.length || payload.summary?.directoryTotal || 0;
  const quoteCount = payload.summary?.quoteCount || items.length;
  const activeMoves = advancers + decliners;
  const breadthPct = activeMoves ? Math.round((advancers / activeMoves) * 100) : null;
  const avgTone = Number.isFinite(avgPct) && avgPct > 0 ? "up" : Number.isFinite(avgPct) && avgPct < 0 ? "down" : "flat";
  const dailyPctItems = items.filter((item) => Number.isFinite(parseMarketNumber(item.pct)));
  const sortedByDailyPct = [...dailyPctItems].sort((left, right) => (parseMarketNumber(right.pct) || -Infinity) - (parseMarketNumber(left.pct) || -Infinity));
  const strongestDaily = sortedByDailyPct[0] || null;
  const weakestDaily = sortedByDailyPct.at(-1) || null;
  const syncSource = payload.directory?.source || payload.source || "美股 ETF 官方清單";
  const syncStatus = "線上資料";
  const syncFreshness = payload.cached ? "最近 5 分鐘內同步" : "剛剛同步";
  const categories = US_ETF_CATEGORY_DEFINITIONS
    .filter((category) => category.key !== "all")
    .map((category) => ({
      ...category,
      count: enriched.filter((item) => item.etfCategoryKey === category.key).length,
    }))
    .filter((category) => category.count)
    .sort((left, right) => right.count - left.count)
    .slice(0, 8);
  const categoryTotal = enriched.length || categories.reduce((sum, category) => sum + category.count, 0) || 1;
  const dataNoteHtml = `<p class="global-insight us-etf-data-note">目前以 ${escapeHtml(syncSource)} 匯入 ETF 明細，並用 Yahoo Finance 美股 ETF 行情補上熱門 ETF、排行、比較與波動風險指標。</p>`;
  const categoryCards = categories.map((category) => {
    const share = Math.max(2, Math.round((category.count / categoryTotal) * 100));
    return `<span><b>${escapeHtml(category.label)}</b><small>${Number(category.count).toLocaleString("zh-TW")} 檔 · ${share}%</small><i style="--share:${share}%"></i></span>`;
  });
  const noteAnchorKeys = new Set(["factor", "international", "sector", "market"]);
  const noteIndex = Math.max(
    -1,
    ...categories.map((category, index) => noteAnchorKeys.has(category.key) ? index : -1),
  ) + 1;
  const categoryMapHtml = categoryCards.length
    ? [
      ...categoryCards.slice(0, noteIndex || categoryCards.length),
      dataNoteHtml,
      ...categoryCards.slice(noteIndex || categoryCards.length),
    ].join("")
    : `<span><b>分類同步中</b><small>等待 ETF 資料載入</small></span>${dataNoteHtml}`;
  return `
    <section class="section" id="us-etf-overview">
      <div class="us-etf-overview-layout">
        <article class="panel-card us-etf-overview-card">
          <div class="card-title-row">
            <div>
              <p class="panel-kicker">ETF market overview</p>
              <h3>ETF 市場總覽</h3>
            </div>
            <span class="chip chip-gold">${escapeHtml(payload.updatedAt || "--")}</span>
          </div>
          <div class="global-summary-grid us-etf-summary-grid">
            <span><b>${directoryTotal ? Number(directoryTotal).toLocaleString("zh-TW") : "--"}</b><small>美股 ETF 清單</small></span>
            <span><b>${quoteCount || "--"}</b><small>Yahoo 美股行情</small></span>
            <span><b>${advancers} / ${decliners}</b><small>上漲 / 下跌</small></span>
            <span><b>${formatSignedPercentValue(avgPct)}</b><small>平均漲跌幅</small></span>
            <span><b>${payload.summary?.volumeLeader || volumeLeaders[0]?.item?.symbol || "--"}</b><small>成交量領先</small></span>
          </div>
          <div class="us-etf-overview-pulse">
            <section class="us-etf-pulse-card us-etf-breadth-card">
              <div class="us-etf-pulse-title">
                <span>行情廣度</span>
                <strong class="${toneClass(avgTone)}">${breadthPct === null ? "--" : `${breadthPct}%`}</strong>
              </div>
              <div class="us-etf-breadth-track"><i style="--breadth:${breadthPct ?? 0}%"></i></div>
              <small>上漲 ${advancers} 檔， 下跌 ${decliners} 檔，平均 ${formatSignedPercentValue(avgPct)}</small>
            </section>
            <section class="us-etf-pulse-card">
              <span>強勢 ETF</span>
              <strong>${escapeHtml(strongestDaily?.symbol || payload.summary?.strongest || "--")}</strong>
              <small>${escapeHtml(strongestDaily?.name || "--")} · <b class="${toneClass("up")}">${escapeHtml(strongestDaily?.pct || payload.summary?.strongestPct || "--")}</b></small>
            </section>
            <section class="us-etf-pulse-card">
              <span>弱勢 ETF</span>
              <strong>${escapeHtml(weakestDaily?.symbol || payload.summary?.weakest || "--")}</strong>
              <small>${escapeHtml(weakestDaily?.name || "--")} · <b class="${toneClass("down")}">${escapeHtml(weakestDaily?.pct || payload.summary?.weakestPct || "--")}</b></small>
            </section>
            <section class="us-etf-pulse-card">
              <span>資料同步</span>
              <strong>${escapeHtml(syncStatus)}</strong>
              <small>${escapeHtml(syncFreshness)} · ${quoteCount || 0} 檔行情</small>
            </section>
          </div>
          <div class="us-etf-category-map">
            ${categoryMapHtml}
          </div>
        </article>
        <article class="panel-card us-etf-hot-card">
          <div class="card-title-row">
            <div>
              <p class="panel-kicker">Popular ETFs</p>
              <h3>熱門ETF</h3>
            </div>
            <span class="chip chip-blue">Yahoo Finance 美股</span>
          </div>
          <div class="us-etf-hot-list">
            ${getUsEtfComparisonItems(items).slice(0, 6).map((item) => {
              const stats = getUsEtfReturnStats(item);
              const tone = (parseMarketNumber(item.pct) || 0) >= 0 ? "up" : "down";
              return `
                <a class="us-etf-hot-item" href="${safeUrl(buildUsStockSearchUrl(item.symbol))}">
                  <span>${escapeHtml(item.symbol || "--")}</span>
                  <strong>${escapeHtml(item.name || "--")}</strong>
                  <small class="${toneClass(tone)}">${escapeHtml(item.pct || "--")} · 區間 ${formatSignedPercentValue(stats.returnPct)}</small>
                </a>
              `;
            }).join("") || '<p class="stock-detail-empty">熱門 ETF 資料同步中。</p>'}
          </div>
        </article>
      </div>
    </section>
  `;
}
function renderUsEtfAiAllocation(payload = {}) {
  const items = getUsEtfMarketItems(payload);
  const entries = items.map((item) => {
    const stats = getUsEtfReturnStats(item);
    const categoryKey = getUsEtfCategoryKey(item);
    const dailyPct = parseMarketNumber(item.pct);
    const volume = parseMarketNumber(item.volume);
    return { item, stats, categoryKey, dailyPct, volume };
  }).filter((entry) => Number.isFinite(entry.dailyPct) || Number.isFinite(entry.stats.returnPct));
  const averageDaily = entries.length
    ? entries.reduce((sum, entry) => sum + (Number.isFinite(entry.dailyPct) ? entry.dailyPct : 0), 0) / entries.length
    : null;
  const advancers = entries.filter((entry) => (entry.dailyPct || 0) > 0).length;
  const decliners = entries.filter((entry) => (entry.dailyPct || 0) < 0).length;
  const breadthPct = advancers + decliners ? Math.round((advancers / (advancers + decliners)) * 100) : null;
  const scoreGrowth = (entry) => (
    (Number.isFinite(entry.stats.returnPct) ? entry.stats.returnPct * 0.55 : 0)
    + (Number.isFinite(entry.dailyPct) ? entry.dailyPct * 2 : 0)
    + (Number.isFinite(entry.stats.sharpe) ? entry.stats.sharpe * 8 : 0)
    - (Number.isFinite(entry.stats.volatility) ? entry.stats.volatility * 0.08 : 0)
    + (Number.isFinite(entry.volume) ? Math.log10(Math.max(entry.volume, 1)) * 0.25 : 0)
  );
  const scoreDefensive = (entry) => (
    (Number.isFinite(entry.stats.sharpe) ? entry.stats.sharpe * 9 : 0)
    + (Number.isFinite(entry.stats.returnPct) ? entry.stats.returnPct * 0.35 : 0)
    + (Number.isFinite(entry.dailyPct) ? entry.dailyPct * 1.2 : 0)
    - (Number.isFinite(entry.stats.volatility) ? entry.stats.volatility * 0.12 : 0)
    + (entry.categoryKey === "dividend" ? 1.5 : 0)
  );
  const scoreRisk = (entry) => (
    (Number.isFinite(entry.stats.volatility) ? entry.stats.volatility * 0.55 : 0)
    + (Number.isFinite(entry.dailyPct) ? Math.abs(entry.dailyPct) * 2.2 : 0)
    + (Number.isFinite(entry.stats.maxDrawdown) ? Math.abs(entry.stats.maxDrawdown) * 0.28 : 0)
  );
  const byScore = (scoreFn) => (left, right) => scoreFn(right) - scoreFn(left);
  const pickSymbols = (list, fallback) => list.slice(0, 3).map((entry) => entry.item.symbol).filter(Boolean).join(" / ") || fallback;
  const growthEntries = entries
    .filter((entry) => ["market", "sector", "thematic", "factor"].includes(entry.categoryKey))
    .sort(byScore(scoreGrowth));
  const defensiveEntries = entries
    .filter((entry) => ["bond", "dividend"].includes(entry.categoryKey))
    .sort(byScore(scoreDefensive));
  const highRiskEntries = entries
    .filter((entry) => ["leveraged", "crypto", "commodity"].includes(entry.categoryKey) || (entry.stats.volatility || 0) >= 35)
    .sort(byScore(scoreRisk));
  const growthLeader = growthEntries[0];
  const defensiveLeader = defensiveEntries[0];
  const highRiskLeader = highRiskEntries[0];
  const riskOn = (breadthPct ?? 0) >= 58 && (averageDaily ?? 0) >= 0 && (growthLeader?.stats.returnPct ?? 0) >= 0;
  const defensiveMode = (breadthPct ?? 50) <= 45 || (averageDaily ?? 0) < 0;
  const marketSignal = riskOn ? "偏多輪動" : defensiveMode ? "防禦優先" : "中性觀望";
  const coreLabel = riskOn ? "成長主軸" : defensiveMode ? "控制追價" : "核心觀察";
  const defensiveLabel = defensiveMode ? "提高防禦" : "防禦待命";
  const riskLabel = (highRiskLeader?.stats.volatility || 0) >= 55 || Math.abs(highRiskLeader?.dailyPct || 0) >= 8 ? "高波動警示" : "限額工具";
  const coreBody = riskOn
    ? `行情廣度 ${breadthPct ?? "--"}%，平均漲跌 ${formatSignedPercentValue(averageDaily)}，成長與產業 ETF 排名靠前；核心部位可優先觀察 ${growthLeader?.item.symbol || "大盤 ETF"} 的區間績效與量能延續。`
    : defensiveMode
      ? `行情廣度 ${breadthPct ?? "--"}%，平均漲跌 ${formatSignedPercentValue(averageDaily)}，風險資產動能不足；核心配置以大盤 ETF 分批觀察，避免追逐單日急漲題材。`
      : `行情廣度 ${breadthPct ?? "--"}%，市場尚未形成明確方向；核心配置可維持分散，等待績效排行與成交量排行同步轉強。`;
  const defensiveBody = defensiveMode
    ? `防禦組合以 ${defensiveLeader?.item.symbol || "債券 / 股息 ETF"} 為優先觀察，重點看 Sharpe、最大回撤與利率敏感度，降低組合波動。`
    : `防禦 ETF 目前作為組合穩定器，若廣度降到 45% 以下或平均漲跌轉負，應提高債券與股息型 ETF 權重觀察。`;
  const highRiskBody = `高風險籃以 ${highRiskLeader?.item.symbol || "槓桿 / 商品 / 加密 ETF"} 波動最需要控管；年化波動 ${formatSignedPercentValue(highRiskLeader?.stats.volatility, 1).replace("+", "")}、最大回撤 ${formatSignedPercentValue(highRiskLeader?.stats.maxDrawdown)}，適合戰術部位而非長期配置假設。`;
  const metricBadges = [
    ["市場訊號", marketSignal],
    ["行情廣度", breadthPct === null ? "--" : `${breadthPct}%`],
    ["平均漲跌", formatSignedPercentValue(averageDaily)],
    ["樣本", `${entries.length} 檔`],
  ];
  return `
    <section class="section" id="us-etf-ai">
      <article class="panel-card us-etf-ai-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">AI ETF analysis</p>
            <h3>AI 分析與資產配置建議</h3>
          </div>
          <span class="chip chip-gold">趨勢規則版</span>
        </div>
        <div class="us-etf-ai-signal-row">
          ${metricBadges.map(([label, value]) => `<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value)}</b></span>`).join("")}
        </div>
        <div class="us-ai-evaluation-grid">
          <section class="us-ai-evaluation-card is-positive"><span>核心配置</span><strong>${escapeHtml(pickSymbols(growthEntries, "SPY / QQQ / SMH"))}</strong><b>${escapeHtml(coreLabel)}</b><p>${escapeHtml(coreBody)}</p></section>
          <section class="us-ai-evaluation-card is-watch"><span>防禦配置</span><strong>${escapeHtml(pickSymbols(defensiveEntries, "BND / TLT / SCHD"))}</strong><b>${escapeHtml(defensiveLabel)}</b><p>${escapeHtml(defensiveBody)}</p></section>
          <section class="us-ai-evaluation-card is-negative"><span>高風險工具</span><strong>${escapeHtml(pickSymbols(highRiskEntries, "TQQQ / IBIT / GLD"))}</strong><b>${escapeHtml(riskLabel)}</b><p>${escapeHtml(highRiskBody)}</p></section>
        </div>
      </article>
    </section>
  `;
}
function renderUsEtfRanking(payload = {}) {
  const items = getUsEtfMarketItems(payload);
  return `
    <section class="section" id="us-etf-ranking">
      <div class="us-etf-ranking-grid">
        <article class="panel-card us-etf-ranking-card">
          <div class="card-title-row"><div><p class="panel-kicker">Performance ranking</p><h3>ETF 績效排行榜</h3></div></div>
          <div class="us-etf-rank-list">${renderUsEtfRankRows(getUsEtfRankedItems(items, "performance", 6), "performance")}</div>
        </article>
        <article class="panel-card us-etf-ranking-card">
          <div class="card-title-row"><div><p class="panel-kicker">Volume ranking</p><h3>成交量排行</h3></div></div>
          <div class="us-etf-rank-list">${renderUsEtfRankRows(getUsEtfRankedItems(items, "volume", 6), "volume")}</div>
        </article>
        <article class="panel-card us-etf-ranking-card">
          <div class="card-title-row"><div><p class="panel-kicker">Risk ranking</p><h3>波動風險排行</h3></div></div>
          <div class="us-etf-rank-list">${renderUsEtfRankRows(getUsEtfRankedItems(items, "risk", 6), "risk")}</div>
        </article>
      </div>
    </section>
  `;
}
function getUsEtfPopularThemeNote(item = {}, stats = {}) {
  const categoryKey = getUsEtfCategoryKey(item);
  const returnText = Number.isFinite(stats.returnPct) && stats.returnPct >= 0 ? "區間動能偏強" : "區間表現待修復";
  const themeMap = {
    market: `核心大盤配置，${returnText}，適合追蹤市場主線。`,
    sector: `產業輪動題材，${returnText}，需搭配成交量確認延續性。`,
    bond: `債券與利率敏感資產，觀察殖利率變化與避險需求。`,
    dividend: `股息收益配置，重點看波動控制與收益穩定性。`,
    international: `海外市場分散配置，需同時留意匯率與區域風險。`,
    factor: `風格因子配置，觀察價值、成長、品質或低波動輪動。`,
    commodity: `商品與避險題材，受美元、通膨與供需變化影響較大。`,
    crypto: `加密資產連動度高，適合小比例觀察高波動題材。`,
    leveraged: `槓桿 / 反向工具，偏短線戰術，不適合用長期持有假設評估。`,
    thematic: `主題型 ETF，成長性高但集中度與估值波動也較高。`,
    other: `熱門 ETF 觀察名單，重點看流動性、趨勢與風險。`,
  };
  return themeMap[categoryKey] || themeMap.other;
}
function getUsEtfPopularRiskText(item = {}, stats = {}) {
  const categoryKey = getUsEtfCategoryKey(item);
  if (["leveraged", "crypto"].includes(categoryKey)) return "高波動，需嚴格控管部位。";
  if (Number.isFinite(stats.volatility) && stats.volatility >= 45) return "年化波動偏高，留意追高風險。";
  if (Number.isFinite(stats.maxDrawdown) && stats.maxDrawdown <= -25) return "歷史回撤較深，需分批觀察。";
  if (categoryKey === "bond") return "利率變化會影響價格彈性。";
  if (categoryKey === "commodity") return "商品價格容易受事件與美元影響。";
  if (categoryKey === "sector" || categoryKey === "thematic") return "產業集中度較高，需留意輪動降溫。";
  return "以成交量與趨勢延續性作為追蹤重點。";
}
function renderUsEtfComparison(payload = {}) {
  const items = getUsEtfComparisonItems(getUsEtfMarketItems(payload)).slice(0, 12);
  return `
    <section class="section" id="us-etf-compare">
      <article class="panel-card global-table-card us-etf-compare-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">Popular ETF watchlist</p>
            <h3>熱門ETF</h3>
          </div>
          <span class="chip chip-blue">Yahoo 美股 / 主題觀察</span>
        </div>
        <div class="global-table-wrap">
          <table class="global-market-table us-etf-compare-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>熱門ETF</th>
                <th>主題</th>
                <th>價格</th>
                <th>日漲跌</th>
                <th>區間績效</th>
                <th>成交量</th>
                <th>熱門觀察</th>
                <th>風險提示</th>
              </tr>
            </thead>
            <tbody>
              ${items.map((item, index) => {
                const enriched = enrichUsEtfDirectoryItems([item])[0] || item;
                const stats = getUsEtfReturnStats(item);
                const tone = (parseMarketNumber(item.pct) || 0) >= 0 ? "up" : "down";
                return `
                  <tr>
                    <td><strong>${index + 1}</strong></td>
                    <td><a class="global-market-link" href="${safeUrl(buildUsStockSearchUrl(item.symbol))}">${escapeHtml(item.symbol || "--")} · ${escapeHtml(item.name || "--")}</a></td>
                    <td><span class="chip chip-blue">${escapeHtml(enriched.etfCategoryLabel || "其他")}</span></td>
                    <td>${formatGlobalValue(item.close)}</td>
                    <td class="${toneClass(tone)}">${escapeHtml(item.pct || "--")}</td>
                    <td>${formatSignedPercentValue(stats.returnPct)}</td>
                    <td>${formatGlobalVolume(item.volume)}</td>
                    <td>${escapeHtml(getUsEtfPopularThemeNote(item, stats))}</td>
                    <td>${escapeHtml(getUsEtfPopularRiskText(item, stats))}</td>
                  </tr>
                `;
              }).join("") || '<tr><td colspan="9">熱門 ETF 資料同步中。</td></tr>'}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  `;
}
function renderUsEtfPage(payload = {}) {
  const root = document.getElementById("us-etf-root");
  if (!root) return;
  window.currentGlobalMarketPayload = payload;
  root.innerHTML = `
    ${renderUsEtfPageHero(payload)}
    ${renderUsEtfOverview(payload)}
    ${renderUsEtfAiAllocation(payload)}
    ${renderUsEtfRanking(payload)}
    ${renderUsEtfComparison(payload)}
    ${renderUsNyseListedEtfsSection()}
    <section class="section" id="us-etf-detail"></section>
  `;
  bindUsNyseDirectoryControls();
  if (payload.directory?.results?.length) {
    usNyseDirectoryState.etf.payload = payload.directory;
    usNyseDirectoryState.etf.query = payload.directory.query || "";
    usNyseDirectoryState.etf.quoteItems = payload.items || [];
    usNyseDirectoryState.etf.page = 1;
    renderUsNyseDirectoryTable("etf", { ...payload.directory, quoteItems: payload.items || [] });
  } else {
    loadUsNyseListedEtfs();
  }
  renderUsEtfDetail(null);
  root.querySelectorAll(".global-technical-chart").forEach((chartView) => bindChartHover(chartView));
}
async function initUsEtfPage() {
  const root = document.getElementById("us-etf-root");
  if (!root) return;
  root.innerHTML = `
    <section class="subpage-hero">
      <p class="eyebrow">US ETF Center</p>
      <h1>美股ETF資料載入中</h1>
      <p class="hero-text">正在取得美股 ETF 行情、分類與線上資料明細...</p>
    </section>
  `;
  try {
    const response = await fetchWithTimeout("/api/us-market/etf-center?directoryLimit=7000&quoteLimit=56", { cache: "no-store" }, 120000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    renderUsEtfPage(payload);
  } catch (error) {
    renderUsEtfPage({
      category: "us-etf",
      title: "美股ETF",
      source: "Nasdaq Trader 官方 Symbol Directory / Yahoo Finance 美股 ETF 行情",
      updatedAt: "--",
      items: [],
      error: error.message || String(error),
    });
    const note = document.querySelector("#us-etf-root .source-note");
    if (note) note.textContent = `美股 ETF 行情暫時無法載入，但美股 ETF 明細仍會嘗試同步。錯誤：${error.message || error}`;
  }
}
function bindUsNyseDirectoryControls() {
  document.querySelectorAll("[data-us-nyse-search-form]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const kind = form.dataset.usNyseSearchForm;
      const config = getUsNyseDirectoryConfig(kind);
      const input = document.getElementById(config.searchId);
      const state = usNyseDirectoryState[config.key];
      state.query = (input?.value || "").trim();
      if (config.key === "etf") {
        state.category = document.getElementById("us-nyse-etf-category")?.value || "all";
        state.sort = document.getElementById("us-nyse-etf-sort")?.value || "return_desc";
      }
      state.page = 1;
      loadUsNyseDirectory(config.key);
    });
  });
  document.querySelectorAll("[data-us-nyse-reset]").forEach((button) => {
    button.addEventListener("click", () => {
      const kind = button.dataset.usNyseReset;
      const config = getUsNyseDirectoryConfig(kind);
      const input = document.getElementById(config.searchId);
      if (input) input.value = "";
      usNyseDirectoryState[config.key].query = "";
      usNyseDirectoryState[config.key].page = 1;
      if (config.key === "etf") {
        usNyseDirectoryState[config.key].category = "all";
        usNyseDirectoryState[config.key].sort = "return_desc";
      }
      loadUsNyseDirectory(config.key);
    });
  });
  document.querySelectorAll("[data-us-nyse-kind]").forEach((section) => {
    section.addEventListener("change", (event) => {
      const pageSizeSelect = event.target.closest("[data-us-nyse-page-size]");
      if (!pageSizeSelect) return;
      const kind = pageSizeSelect.dataset.usNysePageSize;
      const config = getUsNyseDirectoryConfig(kind);
      const state = usNyseDirectoryState[config.key];
      state.pageSize = Number(pageSizeSelect.value) || US_ETF_DEFAULT_PAGE_SIZE;
      state.page = 1;
      if (state.payload) renderUsNyseDirectoryTable(config.key, state.payload);
    });
    section.addEventListener("click", (event) => {
      const detailButton = event.target.closest("[data-us-etf-detail]");
      if (detailButton) {
        event.preventDefault();
        const symbol = detailButton.dataset.usEtfDetail || "";
        const fallbackItem = findUsEtfDirectoryRow(symbol);
        loadUsEtfDetail(symbol, fallbackItem);
        setTimeout(() => {
          document.getElementById("us-etf-detail")?.scrollIntoView({ block: "start", behavior: "smooth" });
        }, 0);
        return;
      }
      const categoryButton = event.target.closest("[data-us-etf-category]");
      if (categoryButton) {
        event.preventDefault();
        const state = usNyseDirectoryState.etf;
        state.category = categoryButton.dataset.usEtfCategory || "all";
        state.page = 1;
        if (state.payload) renderUsNyseDirectoryTable("etf", state.payload);
        return;
      }
      const button = event.target.closest("[data-us-nyse-page]");
      if (!button) return;
      const kind = button.dataset.usNysePage;
      const config = getUsNyseDirectoryConfig(kind);
      const state = usNyseDirectoryState[config.key];
      let results = state.payload?.results || [];
      if (config.key === "etf") {
        results = getUsEtfFilteredDirectoryRows(state.payload);
      }
      const pageSize = config.key === "etf" ? Number(state.pageSize) || US_ETF_DEFAULT_PAGE_SIZE : US_NYSE_DIRECTORY_PAGE_SIZE;
      const totalPages = Math.max(Math.ceil(results.length / pageSize), 1);
      if (button.dataset.page === "first") state.page = 1;
      if (button.dataset.page === "prev") state.page = Math.max(1, state.page - 1);
      if (button.dataset.page === "next") state.page = Math.min(totalPages, state.page + 1);
      if (button.dataset.page === "last") state.page = totalPages;
      renderUsNyseDirectoryTable(config.key, state.payload);
    });
  });
}
function isUsStockInWatchlist(item) {
  const symbol = String(item?.symbol || item?.code || "").trim().toUpperCase();
  return Boolean(symbol && getUsWatchlist().some((entry) => String(entry.symbol || "").toUpperCase() === symbol));
}
function toggleUsDetailWatchlist(detail) {
  const symbol = String(detail?.code || detail?.symbol || "").trim().toUpperCase();
  if (!symbol) return false;
  if (isUsStockInWatchlist({ symbol })) {
    saveUsWatchlist(getUsWatchlist().filter((entry) => String(entry.symbol || "").toUpperCase() !== symbol));
    return false;
  }
  upsertUsWatchlistSymbol({
    symbol,
    name: detail.name,
    group: detail.rawItem?.group || detail.rawItem?.type || "美股 / ETF",
    type: detail.rawItem?.type || detail.rawItem?.group || "US Market",
    close: detail.close,
    change: detail.change,
    pct: detail.pct,
  });
  return true;
}
function renderUsDetailAnalysisCards(detail, technicalTheory) {
  const priceSignals = (technicalTheory.priceIndicators || []).slice(0, 4);
  const volumeSignals = (technicalTheory.volumeIndicators || []).slice(0, 3);
  const breadthSignals = (technicalTheory.breadthIndicators || []).slice(0, 3);
  const valuation = detail.valuation || {};
  const margin = detail.marginTrading || {};
  const ownership = detail.ownershipTrading || {};
  const ownershipMetrics = ownership.metrics || {};
  const profile = detail.companyProfile || {};
  const avgVolume = parseMarketNumber(detail.avgVolume5);
  const latestHistoryDay = (detail.historyDays || []).at(-1);
  const latestVolume = parseMarketNumber(latestHistoryDay?.volume);
  const volumeRatio = Number.isFinite(avgVolume) && avgVolume > 0 && Number.isFinite(latestVolume)
    ? latestVolume / avgVolume
    : null;
  const parsePercentMetric = (value) => {
    const parsed = parseMarketNumber(value);
    return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : null;
  };
  const shortFloatPct = parsePercentMetric(margin.shortPercentOfFloat);
  const shortOutstandingPct = parsePercentMetric(margin.shortPercentOfSharesOutstanding);
  const institutionHeldPct = parsePercentMetric(ownershipMetrics.institutionsHeldPct);
  const insiderHeldPct = parsePercentMetric(ownershipMetrics.insiderHeldPct);
  const availableFloatPct = shortFloatPct === null ? null : Math.max(0, 100 - shortFloatPct);
  const valueTone = (value) => {
    const parsed = parseMarketNumber(value);
    if (!Number.isFinite(parsed) || parsed === 0) return "flat";
    return parsed > 0 ? "up" : "down";
  };
  const valueToneClass = (value) => {
    const tone = valueTone(value);
    return tone === "up" ? "is-up" : tone === "down" ? "is-down" : "is-flat";
  };
  const formatPercentMetric = (value, signed = false) => {
    const parsed = parseMarketNumber(value);
    if (!Number.isFinite(parsed)) return "--";
    const prefix = signed && parsed > 0 ? "+" : "";
    return `${prefix}${parsed.toFixed(2)}%`;
  };
  const displayValue = (value) => {
    const text = String(value ?? "").trim();
    return text && !["N/A", "NA", "--", "-"].includes(text.toUpperCase()) ? text : "--";
  };
  const latestHistory = (detail.historyDays || []).at(-1) || {};
  const previousHistory = (detail.historyDays || []).at(-2) || {};
  const latestClose = parseMarketNumber(latestHistory.close ?? detail.close);
  const previousClose = parseMarketNumber(previousHistory.close);
  const closeChange = Number.isFinite(latestClose) && Number.isFinite(previousClose) && previousClose
    ? ((latestClose - previousClose) / previousClose) * 100
    : null;
  const obvSignal = (technicalTheory.volumeIndicators || []).find((item) => String(item.name || "").toUpperCase().includes("OBV"));
  const shortFloatTone = shortFloatPct === null
    ? "flat"
    : shortFloatPct >= 10 ? "down" : shortFloatPct <= 3 ? "up" : "flat";
  const volumeTone = volumeRatio === null
    ? "flat"
    : volumeRatio >= 1.2 && (closeChange || 0) >= 0 ? "up"
      : volumeRatio >= 1.2 && (closeChange || 0) < 0 ? "down"
        : "flat";
  const renderUsShortFloatProxy = () => `
    <div class="holder-ratio-chart us-float-proxy-chart" role="img" aria-label="Short interest ${shortFloatPct === null ? "--" : shortFloatPct.toFixed(2)}%">
      <div class="holder-ratio-bar">
        <span class="holder-ratio-segment is-large" style="width:${shortFloatPct || 0}%"></span>
        <span class="holder-ratio-segment is-other" style="width:${availableFloatPct ?? 100}%"></span>
      </div>
      <div class="holder-combined-panel">
        <div class="holder-liquid-chart">
          ${[
            { key: "large", label: "放空流通股", value: shortFloatPct, note: "Short % of float" },
            { key: "other", label: "未放空流通股", value: availableFloatPct, note: "Float proxy" },
            { key: "retail", label: "在外股放空", value: shortOutstandingPct, note: "Short % shares" },
          ].map((item) => {
            const value = Number.isFinite(item.value) ? item.value : 0;
            return `
              <div class="holder-liquid-item is-${item.key}">
                <div class="holder-liquid-head">
                  <span><i class="is-${item.key}"></i>${escapeHtml(item.label)}</span>
                  <strong>${Number.isFinite(item.value) ? `${item.value.toFixed(2)}%` : "--"}</strong>
                </div>
                <div class="holder-liquid-tank">
                  <span class="holder-liquid-fill" style="height:${Math.max(0, Math.min(100, value))}%"></span>
                </div>
                <div class="holder-liquid-label"><small>${escapeHtml(item.note)}</small></div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
      <p class="holder-ratio-source">資料日期 ${escapeHtml(margin.date || detail.snapshotDate || "--")}；美股以 Short Interest 作為籌碼代理。</p>
    </div>
  `;
  const renderUsMarginProxyCard = () => `
    <section class="margin-trading-card">
      <div class="margin-trading-head">
        <div>
          <span>Margin trading</span>
          <strong>融資融券替代指標</strong>
        </div>
        <small>資料日期 ${escapeHtml(margin.date || detail.snapshotDate || "--")}</small>
      </div>
      <div class="margin-trading-grid">
        <div><span>Short interest</span><strong>${escapeHtml(margin.shortInterest || "--")}</strong><small>前期 ${escapeHtml(margin.shortInterestPrior || "--")}</small></div>
        <div><span>Days to cover</span><strong>${escapeHtml(margin.shortRatio || "--")}</strong><small>空單回補天數代理</small></div>
        <div><span>Short % float</span><strong>${escapeHtml(margin.shortPercentOfFloat || "--")}</strong><small>流通股放空比例</small></div>
        <div><span>Short % shares</span><strong>${escapeHtml(margin.shortPercentOfSharesOutstanding || "--")}</strong><small>在外股數放空比例</small></div>
      </div>
      <div class="margin-trading-flow">
        <span>流通股 <b>${escapeHtml(margin.floatShares || "--")}</b></span>
        <span>在外股數 <b>${escapeHtml(margin.sharesOutstanding || "--")}</b></span>
        <span>空方變化 <b>${escapeHtml(margin.shortInterestChange || "--")}</b></span>
        <span>資料口徑 <b>Short Interest</b></span>
      </div>
      <p>${escapeHtml(margin.sourceNote || "美股沒有台股融資融券同口徑資料，請以交易所、券商與 SEC 文件交叉核對。")}</p>
    </section>
  `;
  const renderUsVolumeChart = () => {
    const rows = (detail.historyDays || []).slice(-36);
    if (!rows.length) return '<p class="stock-detail-empty">成交量歷史資料不足。</p>';
    const width = 760;
    const height = 230;
    const pad = { left: 36, right: 18, top: 18, bottom: 34 };
    const mid = 122;
    const usableWidth = width - pad.left - pad.right;
    const step = rows.length > 1 ? usableWidth / (rows.length - 1) : usableWidth;
    const volumes = rows.map((row) => parseMarketNumber(row.volume)).filter(Number.isFinite);
    const prices = rows.map((row) => parseMarketNumber(row.close)).filter(Number.isFinite);
    const maxVolume = Math.max(...volumes, 1);
    const minPrice = prices.length ? Math.min(...prices) : 0;
    const maxPrice = prices.length ? Math.max(...prices) : 1;
    const priceRange = Math.max(maxPrice - minPrice, 1);
    const barWidth = Math.max(3, Math.min(8, step * 0.48));
    const points = rows.map((row, index) => {
      const closeValue = parseMarketNumber(row.close);
      const previousCloseValue = parseMarketNumber(rows[index - 1]?.close);
      const changePct = Number.isFinite(closeValue) && Number.isFinite(previousCloseValue) && previousCloseValue
        ? ((closeValue - previousCloseValue) / previousCloseValue) * 100
        : null;
      const volumeValue = parseMarketNumber(row.volume) || 0;
      const barHeight = Math.max(1, (volumeValue / maxVolume) * 82);
      const priceY = Number.isFinite(closeValue)
        ? pad.top + ((maxPrice - closeValue) / priceRange) * (height - pad.top - pad.bottom)
        : mid;
      return {
        date: row.date || "",
        label: String(row.date || "").slice(5),
        x: pad.left + (rows.length > 1 ? index * step : usableWidth / 2),
        volume: volumeValue,
        price: closeValue,
        priceY,
        volumeY: mid - barHeight,
        barHeight,
        changePct,
        closeText: formatGlobalValue(row.close),
        changeText: changePct === null ? "--" : formatPercentMetric(changePct, true),
        volumeText: formatGlobalVolume(row.volume),
        volumeShareText: `${((volumeValue / maxVolume) * 100).toFixed(1)}%`,
      };
    });
    const pricePath = points
      .filter((item) => Number.isFinite(item.price))
      .map((item, index) => {
        return `${index ? "L" : "M"} ${item.x.toFixed(2)} ${item.priceY.toFixed(2)}`;
      })
      .join(" ");
    const hoverZones = points.map((item, index) => {
      const zoneWidth = rows.length > 1 ? Math.max(8, step) : usableWidth;
      const zoneX = Math.max(pad.left, item.x - zoneWidth / 2);
      const widthValue = index === points.length - 1
        ? Math.min(zoneWidth, width - pad.right - zoneX)
        : Math.min(zoneWidth, width - pad.right - zoneX);
      return `<rect class="us-volume-hover-zone" x="${zoneX.toFixed(2)}" y="${pad.top}" width="${Math.max(6, widthValue).toFixed(2)}" height="${height - pad.top - pad.bottom}" data-x="${item.x.toFixed(2)}" data-y-price="${item.priceY.toFixed(2)}" data-y-volume="${item.volumeY.toFixed(2)}" data-date="${escapeHtml(item.date || "--")}" data-close="${escapeHtml(item.closeText)}" data-change="${escapeHtml(item.changeText)}" data-change-tone="${item.changePct === null ? "flat" : item.changePct > 0 ? "up" : item.changePct < 0 ? "down" : "flat"}" data-volume="${escapeHtml(item.volumeText)}" data-volume-share="${escapeHtml(item.volumeShareText)}"></rect>`;
    }).join("");
    return `
      <div class="chip-visual-card us-volume-momentum-chart">
        <div class="chip-visual-head"><span>量價資金變化</span><strong>${escapeHtml(rows.at(-1)?.date || detail.snapshotDate || "--")}</strong></div>
        <div class="us-volume-chart-stage">
          <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="美股成交量與價格變化圖">
            <line class="chip-chart-axis" x1="${pad.left}" y1="${mid}" x2="${width - pad.right}" y2="${mid}"></line>
            ${points.map((item) => `<rect class="chip-flow-bar is-foreign" x="${(item.x - barWidth / 2).toFixed(2)}" y="${item.volumeY.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${item.barHeight.toFixed(2)}" rx="1.6"></rect>`).join("")}
            ${pricePath ? `<path class="chip-price-line" d="${pricePath}"></path>` : ""}
            ${hoverZones}
            <line class="institution-crosshair is-x" data-us-volume-cursor-x x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
            <line class="institution-crosshair is-y" data-us-volume-cursor-y x1="${pad.left}" y1="${mid}" x2="${width - pad.right}" y2="${mid}"></line>
            <circle class="institution-crosshair-dot us-volume-dot is-price" data-us-volume-cursor-dot="price" cx="${pad.left}" cy="${mid}" r="4"></circle>
            <circle class="institution-crosshair-dot us-volume-dot is-volume" data-us-volume-cursor-dot="volume" cx="${pad.left}" cy="${mid}" r="3.6"></circle>
          </svg>
          <div class="institution-chart-tooltip us-volume-chart-tooltip" hidden></div>
        </div>
        <div class="chip-visual-legend"><span><i class="is-price"></i>股價</span><span><i class="is-foreign"></i>成交量</span></div>
      </div>
    `;
  };
  const renderUsVolumeRows = () => {
    const rows = (detail.historyDays || []).slice(-10).reverse();
    if (!rows.length) return '<p class="stock-detail-empty">逐日成交資料同步中。</p>';
    return `
      <div class="chip-data-table">
        <div class="chip-data-row is-head"><span>日期</span><span>收盤</span><span>漲跌幅</span><span>成交量</span></div>
        ${rows.map((row, index) => {
          const current = parseMarketNumber(row.close);
          const next = parseMarketNumber(rows[index + 1]?.close);
          const pctValue = Number.isFinite(current) && Number.isFinite(next) && next ? ((current - next) / next) * 100 : null;
          return `
            <div class="chip-data-row">
              <span>${escapeHtml(row.date || "--")}</span>
              <strong>${escapeHtml(formatGlobalValue(row.close))}</strong>
              <strong class="${valueToneClass(pctValue)}">${pctValue === null ? "--" : `${pctValue >= 0 ? "+" : ""}${pctValue.toFixed(2)}%`}</strong>
              <strong>${escapeHtml(formatGlobalVolume(row.volume))}</strong>
            </div>
          `;
        }).join("")}
      </div>
    `;
  };
  const renderUsShareRows = () => `
    <div class="chip-overview-table chip-margin-overview">
      <div class="chip-overview-row is-head is-us-share-structure"><span>項目</span><span>目前值</span><span>說明</span><span>資料來源</span></div>
      ${[
        ["Short Interest", margin.shortInterest, "已公布空單股數", "Nasdaq / Yahoo"],
        ["Short Interest 前期", margin.shortInterestPrior, "前一期空單股數", "Nasdaq / Yahoo"],
        ["Float Shares", margin.floatShares, "流通股數", "Yahoo / 估算"],
        ["Shares Outstanding", margin.sharesOutstanding, "在外股數", "Yahoo / 估算"],
        ["Institution Held", ownershipMetrics.institutionsHeldPct, "機構持股比例", "Yahoo Holders"],
        ["Insider Held", ownershipMetrics.insiderHeldPct, "內部人持股比例", "Yahoo Holders"],
        ["Institution Count", ownershipMetrics.institutionsCount, "持股機構家數", "Yahoo Holders"],
        ["Market Cap", valuation.marketCap, "市值", "Yahoo / Nasdaq"],
        ["Beta", valuation.beta, "市場敏感度", "Yahoo / 估算"],
      ].map(([label, value, note, source]) => `
        <div class="chip-overview-row is-us-share-structure">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(displayValue(value))}</strong>
          <span>${escapeHtml(note)}</span>
          <span>${escapeHtml(source)}</span>
        </div>
      `).join("")}
    </div>
  `;
  const renderUsOwnershipRows = () => {
    const institutionRows = Array.isArray(ownership.institutionOwners) ? ownership.institutionOwners : [];
    const activityRows = Array.isArray(ownership.positionActivity) ? ownership.positionActivity : [];
    const insiderRows = Array.isArray(ownership.insiderTransactions) ? ownership.insiderTransactions : [];
    const holderRows = Array.isArray(ownership.insiderHolders) ? ownership.insiderHolders : [];
    const renderOwnerTable = (title, rows, emptyText, labels = ["名稱", "申報日", "持股%", "股數", "市值"]) => `
      <section class="us-ownership-section">
        <div class="chip-visual-head">
          <span>${escapeHtml(title)}</span>
          <strong>${rows.length ? `${rows.length} 筆` : "待同步"}</strong>
        </div>
        <div class="chip-data-table">
          <div class="chip-data-row is-head is-us-owner-row">${labels.map((label) => `<span>${escapeHtml(label)}</span>`).join("")}</div>
          ${rows.map((row) => `
            <div class="chip-data-row is-us-owner-row">
              <span>${escapeHtml(row.name || "--")}</span>
              <span>${escapeHtml(row.reportDate || "--")}</span>
              <strong>${escapeHtml(displayValue(row.pctHeld))}</strong>
              <strong>${escapeHtml(displayValue(row.position))}</strong>
              <strong>${escapeHtml(displayValue(row.value))}</strong>
            </div>
          `).join("") || `<p class="stock-detail-empty">${escapeHtml(emptyText)}</p>`}
        </div>
      </section>
    `;
    const renderInsiderTransactions = () => `
      <section class="us-ownership-section">
        <div class="chip-visual-head">
          <span>內部人交易</span>
          <strong>${insiderRows.length ? `${insiderRows.length} 筆` : "待同步"}</strong>
        </div>
        <div class="chip-data-table">
          <div class="chip-data-row is-head is-us-insider-row"><span>姓名</span><span>日期</span><span>交易</span><span>持有型態</span><span>股數</span><span>金額</span></div>
          ${insiderRows.map((row) => `
            <div class="chip-data-row is-us-insider-row">
              <span>${escapeHtml(row.name || "--")}</span>
              <span>${escapeHtml(row.date || "--")}</span>
              <span>${escapeHtml(row.transaction || "--")}</span>
              <span>${escapeHtml(row.ownership || "--")}</span>
              <strong>${escapeHtml(displayValue(row.shares))}</strong>
              <strong>${escapeHtml(displayValue(row.value))}</strong>
            </div>
          `).join("") || '<p class="stock-detail-empty">目前未取得內部人交易明細。</p>'}
        </div>
      </section>
    `;
    const renderInsiderHolders = () => `
      <section class="us-ownership-section">
        <div class="chip-visual-head">
          <span>內部人持股</span>
          <strong>${holderRows.length ? `${holderRows.length} 筆` : "待同步"}</strong>
        </div>
        <div class="chip-data-table">
          <div class="chip-data-row is-head is-us-insider-holder-row"><span>姓名</span><span>關係</span><span>最近日期</span><span>直接持股</span><span>間接持股</span></div>
          ${holderRows.map((row) => `
            <div class="chip-data-row is-us-insider-holder-row">
              <span>${escapeHtml(row.name || "--")}</span>
              <span>${escapeHtml(row.relation || "--")}</span>
              <span>${escapeHtml(row.latestDate || "--")}</span>
              <strong>${escapeHtml(displayValue(row.directShares))}</strong>
              <strong>${escapeHtml(displayValue(row.indirectShares))}</strong>
            </div>
          `).join("") || '<p class="stock-detail-empty">目前未取得內部人持股明細。</p>'}
        </div>
      </section>
    `;
    return `
      <div class="us-ownership-summary">
        <div><span>機構持股</span><strong>${escapeHtml(displayValue(ownershipMetrics.institutionsHeldPct))}</strong></div>
        <div><span>機構持有流通股</span><strong>${escapeHtml(displayValue(ownershipMetrics.institutionsFloatPct))}</strong></div>
        <div><span>內部人持股</span><strong>${escapeHtml(displayValue(ownershipMetrics.insiderHeldPct))}</strong></div>
        <div><span>內部人淨變化</span><strong>${escapeHtml(displayValue(ownershipMetrics.netInsiderShares))}</strong></div>
      </div>
      <div class="us-ownership-grid">
        ${renderOwnerTable("機構持有人", institutionRows, "目前未取得機構持有人明細。")}
        ${renderOwnerTable("機構增減統計", activityRows, "目前未取得機構增減統計。", ["分類", "日期", "持有人", "股數", "說明"])}
        ${renderInsiderTransactions()}
        ${renderInsiderHolders()}
      </div>
      ${ownership.sourceLink ? `<a class="chip-source-link" href="${safeUrl(ownership.sourceLink)}" target="_blank" rel="noreferrer noopener">Yahoo Holders</a>` : ""}
    `;
  };
  const renderUsSourceLinks = () => `
    <div class="company-news-sources">
      <a href="${safeUrl(buildYahooFinanceUrl(detail.code))}" target="_blank" rel="noreferrer noopener">Yahoo Finance</a>
      <a href="${safeUrl(detail.newsLinks?.profile || `${buildYahooFinanceUrl(detail.code)}/profile`)}" target="_blank" rel="noreferrer noopener">Yahoo Profile</a>
      <a href="${safeUrl(detail.newsLinks?.sec || `https://www.sec.gov/edgar/search/#/q=${encodeURIComponent(detail.code || "")}`)}" target="_blank" rel="noreferrer noopener">SEC EDGAR</a>
      <a href="${safeUrl(`https://www.nasdaq.com/market-activity/stocks/${encodeURIComponent(String(detail.code || "").toLowerCase())}`)}" target="_blank" rel="noreferrer noopener">Nasdaq</a>
    </div>
  `;
  const renderUsChipDashboard = () => {
    const stateKey = getStockDetailCacheKey(detail.code, detail.market || "US");
    const cards = [
      {
        key: "shortInterest",
        tab: "空方籌碼",
        title: "Short Interest 空方籌碼",
        label: shortFloatPct === null ? "待同步" : shortFloatPct >= 10 ? "空方偏高" : shortFloatPct <= 3 ? "空方低檔" : "中性觀察",
        tone: shortFloatTone,
        metrics: [
          ["Short Interest", displayValue(margin.shortInterest)],
          ["Days to cover", displayValue(margin.shortRatio)],
          ["Short % float", displayValue(margin.shortPercentOfFloat)],
          ["Short % shares", displayValue(margin.shortPercentOfSharesOutstanding)],
        ],
        body: `${renderUsShortFloatProxy()}${renderUsMarginProxyCard()}`,
        sourceNote: margin.sourceNote || "美股以 Short Interest 作為空方籌碼代理，不等同台股融資融券。",
      },
      {
        key: "volume",
        tab: "量價資金",
        title: "量價資金動能",
        label: volumeRatio === null ? "待同步" : volumeRatio >= 1.2 ? "量能放大" : volumeRatio <= 0.8 ? "量能收縮" : "量能平穩",
        tone: volumeTone,
        metrics: [
          ["成交量", formatGlobalVolume(detail.rawItem?.volume)],
          ["5 日均量", detail.avgVolume5],
          ["量比", Number.isFinite(volumeRatio) ? volumeRatio.toFixed(2) : "--"],
          ["OBV", obvSignal?.value || "--"],
        ],
        body: `${renderUsVolumeChart()}${renderUsVolumeRows()}`,
        sourceNote: "量價資金以 Yahoo Finance 歷史成交量、OBV 與價格同步性判讀。",
      },
      {
        key: "shares",
        tab: "股本結構",
        title: "股本與流通結構",
        label: displayValue(margin.floatShares) !== "--" ? "已同步" : "待同步",
        tone: "flat",
        metrics: [
          ["流通股數", displayValue(margin.floatShares)],
          ["在外股數", displayValue(margin.sharesOutstanding)],
          ["市值", displayValue(valuation.marketCap)],
          ["Beta", displayValue(valuation.beta)],
        ],
        body: renderUsShareRows(),
        sourceNote: "若交易所未提供直接欄位，部分股本比例會以市值與股價近似估算並標示來源。",
      },
      {
        key: "holders",
        tab: "持有人",
        title: "機構、基金與內部人持股",
        label: displayValue(ownershipMetrics.institutionsHeldPct) !== "--" || displayValue(ownershipMetrics.insiderHeldPct) !== "--" ? "已同步" : "待同步",
        tone: "flat",
        metrics: [
          ["機構持股", displayValue(ownershipMetrics.institutionsHeldPct)],
          ["機構持有流通股", displayValue(ownershipMetrics.institutionsFloatPct)],
          ["內部人持股", displayValue(ownershipMetrics.insiderHeldPct)],
          ["機構家數", displayValue(ownershipMetrics.institutionsCount)],
        ],
        body: renderUsOwnershipRows(),
        sourceNote: ownership.sourceNote || "持有人資料同步自 Yahoo Finance holders 模組；申報明細仍以 SEC EDGAR 為準。",
      },
      {
        key: "sources",
        tab: "資料來源",
        title: "美股資料來源",
        label: "Yahoo / Nasdaq / SEC",
        tone: "flat",
        metrics: [
          ["行情", "Yahoo Finance"],
          ["估值", "Yahoo / Nasdaq"],
          ["空方籌碼", "Nasdaq Short Interest"],
          ["申報", "SEC EDGAR"],
        ],
        body: renderUsSourceLinks(),
        sourceNote: "美股沒有台股三大法人、主力分點、集保與融資融券同口徑公開資料，本頁以公開來源代理欄位呈現。",
      },
    ];
    const requestedTab = stockChipTabState.get(stateKey) || "shortInterest";
    const activeCard = cards.find((card) => card.key === requestedTab) || cards[0];
    const renderCardPanel = (card) => `
      <article class="chip-tab-panel is-${escapeHtml(card.tone || "flat")} ${card.key === activeCard.key ? "is-active" : ""}" data-us-chip-panel="${escapeHtml(card.key)}" ${card.key === activeCard.key ? "" : "hidden"}>
        <div class="chip-summary-head">
          <div>
            <span>${escapeHtml(card.tab)}</span>
            <strong>${escapeHtml(card.title)}</strong>
          </div>
          <b>${escapeHtml(card.label)}</b>
        </div>
        <div class="chip-summary-metrics">
          ${card.metrics.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("")}
        </div>
        ${card.body}
        <p class="chip-source-note">${escapeHtml(card.sourceNote || "")}</p>
      </article>
    `;
    return `
      <section class="chip-tab-shell" data-us-chip-shell aria-label="美股籌碼分頁">
        <div class="chip-tab-bar" role="tablist">
          ${cards.map((card) => `<button class="${card.key === activeCard.key ? "is-active" : ""}" type="button" data-us-chip-tab="${escapeHtml(card.key)}" role="tab" aria-selected="${card.key === activeCard.key ? "true" : "false"}">${escapeHtml(card.tab)}</button>`).join("")}
        </div>
        ${cards.map(renderCardPanel).join("")}
      </section>
    `;
  };
  const cards = [
    {
      title: "技術面",
      key: "technical",
      summary: technicalTheory.adaptiveSummary || "整合均線、型態、價量與指標訊號判斷趨勢。",
      items: [
        ...(technicalTheory.theorySignals || []).slice(0, 4).map((item) => `${item.name}：${item.text}`),
        ...(priceSignals.length ? priceSignals.map((item) => `${item.name} ${item.value}：${item.text}`) : ["價的技術指標資料不足。"]),
      ],
    },
    {
      title: "基本面",
      key: "fundamental",
      summary: valuation.peRatio || valuation.marketCap
        ? `估值：本益比 ${valuation.peRatio || "--"}、Forward PE ${valuation.forwardPE || "--"}、市值 ${valuation.marketCap || "--"}。`
        : "美股基本資料以 Yahoo Finance 與交易所代號資料呈現；詳細財報仍需至 SEC / 公司 IR 核對。",
      items: [
        `市場 / 交易所：${detail.marketLabel || "--"}`,
        `產業 / 類別：${profile.sector || "--"} / ${profile.industry || detail.rawItem?.type || "--"}`,
        `市值：${valuation.marketCap || "--"}，Enterprise Value：${valuation.enterpriseValue || "--"}`,
        `本益比：${valuation.peRatio || "--"}，Forward PE：${valuation.forwardPE || "--"}，PB：${valuation.pbRatio || "--"}`,
        `股息率：${valuation.dividendYield || "--"}%，每股股利：${valuation.dividendPerShare || "--"}`,
        `Beta：${valuation.beta || "--"}，營收成長：${valuation.revenueGrowth || "--"}，淨利率：${valuation.profitMargins || "--"}`,
      ],
    },
    {
      title: "籌碼面",
      key: "chips",
      summary: "美股缺少台股三大法人、主力分點與集保口徑，改以 Short Interest、成交量、OBV 與股本結構作為公開籌碼代理。",
      items: [
        `成交量：${formatGlobalVolume(detail.rawItem?.volume)}，5 日均量：${detail.avgVolume5}`,
        `量比：${Number.isFinite(volumeRatio) ? volumeRatio.toFixed(2) : "--"}`,
        `Short % float：${displayValue(margin.shortPercentOfFloat)}，Days to cover：${displayValue(margin.shortRatio)}`,
        ...(volumeSignals.length ? volumeSignals.map((item) => `${item.name} ${item.value}：${item.text}`) : ["OBV / 平均成交量資料不足。"]),
        ...(breadthSignals.length ? breadthSignals.map((item) => `${item.name} ${item.value}：${item.text}`) : []),
      ],
      chipProxy: true,
    },
  ];
  return `
    <div class="analysis-grid">
      ${cards.map((card) => `
        <article class="analysis-card ${card.chipProxy ? "analysis-card-chips" : ""}">
          <div class="card-title-row"><h4>${escapeHtml(card.title)}</h4></div>
          <p class="card-copy">${escapeHtml(card.summary)}</p>
          ${card.chipProxy ? renderUsChipDashboard() : ""}
          <ul class="analysis-list">${card.items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </article>
      `).join("")}
    </div>
  `;
}
function renderUsDetailNewsCard(detail) {
  const yahooNews = detail.newsLinks?.yahoo || `${buildYahooFinanceUrl(detail.code)}/news`;
  const profile = detail.newsLinks?.profile || `${buildYahooFinanceUrl(detail.code)}/profile`;
  const secLink = detail.newsLinks?.sec || `https://www.sec.gov/edgar/search/#/q=${encodeURIComponent(detail.code || "")}`;
  const news = Array.isArray(detail.companyNews) ? detail.companyNews : [];
  const newsEmptyText = "目前未取得近期公司新聞，可使用下方來源連結查詢。";
  return `
    <section class="company-news-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">Company news</p>
          <h3>消息面</h3>
          <p class="chart-subtitle">${escapeHtml(detail.code)} ${escapeHtml(detail.name)} 近期公司新聞、ETF 公告與公開消息。</p>
        </div>
        <span class="chip chip-blue">${news.length} 則消息</span>
      </div>
      <div class="company-news-list">
        ${news.map((item) => `
          <a class="company-news-item" href="${safeUrl(item.link || yahooNews)}" target="_blank" rel="noreferrer noopener">
            <div>
              <strong>${escapeHtml(item.title || "--")}</strong>
              <span>${escapeHtml(item.source || "Yahoo Finance")} · ${escapeHtml(item.publishedAt || "--")}</span>
            </div>
            <b>閱讀消息</b>
          </a>
        `).join("") || `<p class="stock-detail-empty">${newsEmptyText}</p>`}
      </div>
      <div class="company-news-sources">
        <a href="${safeUrl(yahooNews)}" target="_blank" rel="noreferrer noopener">Yahoo 個股新聞</a>
        <a href="${safeUrl(profile)}" target="_blank" rel="noreferrer noopener">Yahoo Profile</a>
        <a href="${safeUrl(secLink)}" target="_blank" rel="noreferrer noopener">SEC EDGAR</a>
      </div>
      <p class="stock-theory-note">美股新聞與公司資料由外部來源提供，請點入原始頁面核對發布時間與完整內容。</p>
    </section>
  `;
}
function renderUsValuationCompanyCard(detail) {
  const valuation = detail.valuation || {};
  const profile = detail.companyProfile || {};
  const components = detail.etfComponents || {};
  const holdings = Array.isArray(components.holdings) ? components.holdings : [];
  const isMissingValue = (value) => {
    const text = String(value ?? "").trim();
    return !text || ["--", "-", "N/A", "NA", "--%", "-%"].includes(text);
  };
  const renderMetricGrid = (metrics) => `
    <div class="us-valuation-profile-grid">
      ${metrics.filter(([, value]) => !isMissingValue(value)).map(([label, value]) => `
        <div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value || "--")}</strong></div>
      `).join("") || '<div><span>資料狀態</span><strong>等待公開資料</strong></div>'}
    </div>
  `;
  const hasFundamentalValuationHistory = (detail.valuationHistory || []).some((item) => (
    Number.isFinite(Number(item.peRatio))
    || Number.isFinite(Number(item.pbRatio))
    || Number.isFinite(Number(item.dividendYield))
    || Number.isFinite(Number(item.dividendPerShare))
  ));
  const renderValuationBars = (key, label, unit = "") => {
    const points = (detail.valuationHistory || [])
      .map((item) => ({ date: item.date, value: Number(item[key]) }))
      .filter((item) => Number.isFinite(item.value));
    if (!points.length) {
      return `<div class="valuation-mini-chart"><h5>${label}</h5><p class="stock-detail-empty">暫無歷史資料</p></div>`;
    }
    const maxValue = Math.max(...points.map((item) => item.value), 0.01);
    return `
      <div class="valuation-mini-chart">
        <h5>${label}</h5>
        <div class="valuation-bars">
          ${points.map((item) => {
            const height = Math.max(5, (item.value / maxValue) * 100);
            return `
              <div class="valuation-bar-item" title="${escapeHtml(item.date || "--")} ${escapeHtml(label)} ${item.value.toFixed(2)}${unit}">
                <strong>${item.value.toFixed(2)}${unit}</strong>
                <span class="valuation-bar-track"><i style="height:${height}%"></i></span>
                <small>${escapeHtml(String(item.date || "--").replaceAll("-", "/"))}</small>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  };
  const profileRows = [
    ["市場 / 交易所", detail.marketLabel || profile.exchange],
    ["產業", [profile.sector, profile.industry].filter((item) => !isMissingValue(item)).join(" / ")],
    ["國家", profile.country],
    ["員工數", profile.employees],
    ["電話", profile.telephone],
    ["地址", profile.address, "is-wide"],
  ].filter(([, value]) => !isMissingValue(value));
  const profileSourceLabel = isMissingValue(profile.businessSummary) ? "資料待補" : "Yahoo / Nasdaq";
  const companyProfileHtml = `
    <aside class="company-profile ${isMissingValue(profile.businessSummary) ? "is-fallback" : ""}">
      <div>
        <p class="eyebrow">Company profile</p>
        <h4>${escapeHtml(profile.fullName || `${detail.code} ${detail.name}`)}</h4>
      </div>
      <span class="chip ${isMissingValue(profile.businessSummary) ? "chip-blue" : "chip-gold"}">${escapeHtml(profileSourceLabel)}</span>
      <dl>
        ${profileRows.map(([label, value, className]) => `
          <div class="${className || ""}"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "--")}</dd></div>
        `).join("") || '<div><dt>資料狀態</dt><dd>等待公開資料</dd></div>'}
      </dl>
      <div class="company-profile-links">
        ${profile.website ? `<a class="company-website" href="${safeUrl(profile.website)}" target="_blank" rel="noreferrer noopener">公司網站</a>` : ""}
        <a class="company-website" href="${safeUrl(buildYahooFinanceUrl(detail.code))}" target="_blank" rel="noreferrer noopener">Yahoo 個股資料</a>
        <a class="company-website" href="${safeUrl(detail.newsLinks?.sec || `https://www.sec.gov/edgar/search/#/q=${encodeURIComponent(detail.code || "")}`)}" target="_blank" rel="noreferrer noopener">SEC 申報</a>
      </div>
      <p class="stock-theory-note">${escapeHtml(profile.businessSummary || "公司摘要目前未取得。")}</p>
    </aside>
  `;
  if (detail.isEtf && holdings.length) {
    return `
      <section class="valuation-company-card etf-components-card">
        <div class="card-title-row">
          <div>
            <h3>${escapeHtml(components.title || "ETF 成分股比例")}</h3>
            <p class="chart-subtitle">${escapeHtml(components.summary || "ETF 持股資料依 Yahoo Finance Top Holdings 整理。")}</p>
          </div>
          <span class="chip chip-blue">${holdings.length} 項配置</span>
        </div>
        <div class="etf-holding-list">
          ${holdings.map((item) => {
            const weight = Math.max(0, Math.min(100, Number(item.weight) || 0));
            return `
              <div class="etf-holding-row">
                <div><strong>${escapeHtml(item.name || "--")}</strong><span>${escapeHtml(item.code || "--")}</span></div>
                <div class="etf-holding-bar"><i style="width:${weight}%"></i></div>
                <b>${weight.toFixed(2)}%</b>
              </div>
            `;
          }).join("")}
        </div>
        <p class="stock-theory-note">${escapeHtml(components.sourceNote || "實際持股比例請以發行商公告為準。")}</p>
      </section>
    `;
  }
  return `
    <section class="valuation-company-card">
      <div class="card-title-row">
        <div>
          <h3>估值歷史與公司資料</h3>
          <p class="chart-subtitle">估值歷史以 Yahoo 最新 EPS / Book Value / Dividend Rate 回推近月價格區間，實際財報請以 SEC 與公司 IR 為準。</p>
        </div>
        <a class="global-refresh" href="${safeUrl(buildYahooFinanceUrl(detail.code))}" target="_blank" rel="noreferrer noopener">Yahoo Finance</a>
      </div>
      <div class="valuation-company-grid">
        <div>
          <div class="valuation-chart-grid">
            ${hasFundamentalValuationHistory
              ? `${renderValuationBars("peRatio", "本益比")}
                ${renderValuationBars("dividendYield", "股息率", "%")}
                ${renderValuationBars("dividendPerShare", "每股股利")}
                ${renderValuationBars("pbRatio", "股價淨值比")}`
              : `${renderValuationBars("close", "月末收盤價")}
                <div class="valuation-mini-chart"><h5>估值資料</h5><p class="stock-detail-empty">Yahoo 進階估值暫時無法授權取得，先以價格歷史輔助判斷。</p></div>`}
          </div>
          ${renderMetricGrid(detail.isEtf ? [
              ["市值", valuation.marketCap],
              ["AUM", valuation.aum],
              ["費用率", valuation.expenseRatio],
              ["Beta", valuation.beta],
              ["50 日均量", valuation.averageVolume],
              ["52 週區間", valuation.fiftyTwoWeekRange],
              ["股息率", isMissingValue(valuation.dividendYield) ? "" : `${valuation.dividendYield}%`],
              ["年化股息", valuation.dividendPerShare],
            ] : [
              ["市值", valuation.marketCap],
              ["本益比", valuation.peRatio],
              ["股價淨值比", valuation.pbRatio],
              ["股價營收比", valuation.priceToSales],
              ["股息率", isMissingValue(valuation.dividendYield) ? "" : `${valuation.dividendYield}%`],
              ["每股股利", valuation.dividendPerShare],
              ["Beta", valuation.beta],
              ["營收成長", isMissingValue(valuation.revenueGrowth) ? "" : `${valuation.revenueGrowth}%`],
              ["淨利率", isMissingValue(valuation.profitMargins) ? "" : `${valuation.profitMargins}%`],
              ["1 年目標價", valuation.oneYearTarget],
              ["Enterprise Value", valuation.enterpriseValue],
            ])}
        </div>
        ${companyProfileHtml}
      </div>
      <p class="stock-theory-note">${escapeHtml(valuation.sourceNote || "美股估值與公司資料請搭配 SEC / 公司 IR 核對。")}</p>
    </section>
  `;
}
function renderUsTechnicalTheorySection(detail, technicalTheory) {
  const trendSummary = buildTechnicalTrendSummary(detail, technicalTheory);
  const theoryTone = technicalTheory.score >= 3 ? "positive" : technicalTheory.score <= -3 ? "negative" : "neutral";
  const theoryLabel = theoryTone === "positive"
    ? "偏多結構"
    : theoryTone === "negative"
      ? "偏空結構"
      : "中性整理";
  const priceSignals = technicalTheory.priceIndicators || [];
  const volumeSignals = technicalTheory.volumeIndicators || [];
  const breadthSignals = technicalTheory.breadthIndicators || [];
  const theorySignals = technicalTheory.theorySignals || [];
  const technicalSummaryHtml = `
    <article class="stock-market-context technical-trend-summary is-${trendSummary.tone}">
      <div class="technical-summary-head">
        <div class="stock-theory-title">
          <span>Technical outlook</span>
          <h4>技術分析總結</h4>
        </div>
        <div class="technical-summary-score">
          <b>${escapeHtml(String(trendSummary.score))}</b>
          <span>${escapeHtml(trendSummary.label)}</span>
        </div>
      </div>
      <p>${escapeHtml(trendSummary.summary)}</p>
      <div class="technical-summary-timeframes">
        ${trendSummary.timeframes.map((item) => `<span><small>${escapeHtml(item.label)}</small><b>${escapeHtml(item.value)}</b></span>`).join("")}
        <span><small>分析信心</small><b>${escapeHtml(trendSummary.confidence)}</b></span>
      </div>
      ${renderTechnicalTrendForecastSummary(trendSummary)}
      <div class="technical-summary-columns">
        <section>
          <h5>趨勢共振依據</h5>
          <ul>${trendSummary.confirmations.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>尚未形成明確共振。</li>"}</ul>
        </section>
        <section>
          <h5>風險與反向訊號</h5>
          <ul>${trendSummary.risks.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>目前未偵測到重大衝突。</li>"}</ul>
        </section>
      </div>
      <div class="technical-summary-action">
        <strong>目前風向與操作節奏</strong>
        <span>${escapeHtml(trendSummary.action)}</span>
      </div>
    </article>
  `;
  return `
    <section class="stock-theory-section">
      <div class="card-title-row">
        <div>
          <h3>進階技術分析理論</h3>
          <p class="chart-subtitle">整合型態、價量、市場廣度、心理線與籌碼代理指標，透過多因子一致性動態調整信心。</p>
        </div>
        <span class="stock-theory-score is-${theoryTone}">${theoryLabel} · ${technicalTheory.score > 0 ? "+" : ""}${technicalTheory.score}</span>
      </div>
      <div class="stock-theory-adaptive">
        <strong>多理論共振：${escapeHtml(technicalTheory.adaptiveConfidence || "低")}信心</strong>
        <span>${escapeHtml(technicalTheory.adaptiveSummary || "目前多空理論尚未形成一致方向")}</span>
      </div>
      <div class="stock-theory-grid">
        <article class="stock-theory-card">
          <div class="stock-theory-title">
            <span>Pattern theory</span>
            <h4>型態技術分析</h4>
          </div>
          <div class="stock-theory-signal-list">
            ${theorySignals.map((item) => `
              <div class="stock-theory-signal is-${escapeHtml(item.direction || "neutral")}">
                <strong>${escapeHtml(item.name || "--")}</strong>
                <span>${escapeHtml(item.text || "")}</span>
              </div>
            `).join("") || `<ul>${(technicalTheory.patterns || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`}
          </div>
          ${technicalSummaryHtml}
        </article>
        <article class="stock-theory-card">
          <div class="stock-theory-title">
            <span>Indicator theory</span>
            <h4>指標類技術分析</h4>
          </div>
          <div class="indicator-resonance ${technicalTheory.priceVolumeConflict ? "is-conflict" : technicalTheory.priceVolumeAligned ? "is-aligned" : ""}">
            ${escapeHtml(technicalTheory.indicatorSummary || "價量方向尚未形成一致確認")}
          </div>
          <div class="indicator-theory-groups">
            <section>
              <h5>價的技術指標</h5>
              <div class="indicator-signal-list">
                ${priceSignals.map((item) => item.movingAverage ? `
                  <div class="indicator-signal moving-average-analysis is-${escapeHtml(item.direction || "neutral")}">
                    <div class="moving-average-head">
                      <div>
                        <strong>${escapeHtml(item.name || "--")}</strong>
                        <span>${escapeHtml(item.movingAverage.headline || "--")}</span>
                      </div>
                      <b>${Number(item.movingAverage.score || 0) > 0 ? "+" : ""}${escapeHtml(String(item.movingAverage.score ?? "--"))}</b>
                    </div>
                    <div class="moving-average-periods">
                      ${(item.movingAverage.periods || []).map((period) => `
                        <div>
                          <strong>${escapeHtml(period.label || "--")}</strong>
                          <b>${Number.isFinite(period.value) ? period.value.toFixed(2) : "--"}</b>
                          <span>${escapeHtml(period.role || "--")}</span>
                          <small>${escapeHtml(period.slope || "--")} · ${escapeHtml(period.position || "--")}</small>
                        </div>
                      `).join("")}
                    </div>
                    <div class="moving-average-sections">
                      <section>
                        <h6>趨勢與交叉</h6>
                        <ul>
                          ${(item.movingAverage.crosses || []).map((text) => `<li>${escapeHtml(text)}</li>`).join("")}
                          ${(item.movingAverage.confirmations || []).map((text) => `<li>${escapeHtml(text)}</li>`).join("")}
                        </ul>
                      </section>
                      <section>
                        <h6>實戰判讀</h6>
                        <p>${escapeHtml(item.movingAverage.practical || "--")}</p>
                        <p>${escapeHtml(item.movingAverage.suitability || "--")}</p>
                      </section>
                    </div>
                    <div class="moving-average-risk">
                      <strong>風險提醒</strong>
                      <span>${(item.movingAverage.risks || []).map((text) => escapeHtml(text)).join("；") || "等待更多樣本確認"}</span>
                    </div>
                  </div>
                ` : `
                  <div class="indicator-signal is-${escapeHtml(item.direction || "neutral")}">
                    <strong>${escapeHtml(item.name || "--")}</strong>
                    <span>${escapeHtml(item.value || "")}</span>
                    <small>${escapeHtml(item.text || "")}</small>
                  </div>
                `).join("") || "<p>價格指標資料不足</p>"}
              </div>
            </section>
            <section>
              <h5>量的技術指標</h5>
              <div class="indicator-signal-list">
                ${volumeSignals.map((item) => `
                  <div class="indicator-signal is-${escapeHtml(item.direction || "neutral")}">
                    <strong>${escapeHtml(item.name || "--")}</strong>
                    <span>${escapeHtml(item.value || "")}</span>
                    <small>${escapeHtml(item.text || "")}</small>
                  </div>
                `).join("") || "<p>量能指標資料不足</p>"}
              </div>
            </section>
            <section>
              <h5>市場廣度、心理與籌碼指標</h5>
              <div class="indicator-resonance ${technicalTheory.breadthConflict ? "is-conflict" : technicalTheory.breadthAligned ? "is-aligned" : ""}">
                ${escapeHtml(technicalTheory.breadthSummary || "市場廣度與籌碼方向尚未形成一致確認")}
              </div>
              <div class="indicator-signal-list">
                ${breadthSignals.map((item) => `
                  <div class="indicator-signal is-${escapeHtml(item.direction || "neutral")}">
                    <strong>${escapeHtml(item.name || "--")}</strong>
                    <span>${escapeHtml(item.value || "")}</span>
                    <small>${escapeHtml(item.text || "")}</small>
                  </div>
                `).join("") || "<p>市場廣度或籌碼資料不足</p>"}
              </div>
            </section>
          </div>
        </article>
      </div>
      ${renderUsBacktestLearningCard(technicalTheory)}
      <p class="stock-theory-note">「動態強化」會依理論一致度、量價與指標確認調整權重；美股籌碼面採成交量、OBV、Short Interest 等代理資料，不等同台股三大法人與融資融券口徑。</p>
    </section>
  `;
}
function bindUsDetailChartControls(root, detail, chartViewId, statusId) {
  let activeInterval = "day";
  const activeOverlayIndicators = new Set();
  const activePanelIndicators = new Set(["kd"]);
  const activeMaPeriods = new Set([5]);
  const zoomCounts = new Map();
  const panOffsets = new Map();

  const getChartKey = () => `${activeInterval}:${[...activeOverlayIndicators].sort().join(",")}:${[...activePanelIndicators].sort().join(",")}`;
  const getZoomState = () => {
    const total = getChartHistory(detail, activeInterval).length;
    const minimum = activeInterval === "day" ? 20 : activeInterval === "week" ? 8 : 4;
    const saved = zoomCounts.get(getChartKey());
    const visible = Number.isFinite(saved) ? Math.max(Math.min(minimum, total), Math.min(saved, total)) : total;
    const panOffset = Math.max(0, Math.min(panOffsets.get(getChartKey()) || 0, Math.max(total - visible, 0)));
    return { total, minimum: Math.min(minimum, total), visible, panOffset };
  };
  const updateControls = () => {
    const { total, minimum, visible, panOffset } = getZoomState();
    root.querySelector('[data-us-stock-zoom="in"]')?.toggleAttribute("disabled", visible <= minimum);
    root.querySelector('[data-us-stock-zoom="out"]')?.toggleAttribute("disabled", visible >= total);
    root.querySelector('[data-us-stock-zoom="reset"]')?.toggleAttribute("disabled", visible >= total);
    root.querySelector('[data-us-stock-pan="older"]')?.toggleAttribute("disabled", panOffset >= total - visible);
    root.querySelector('[data-us-stock-pan="newer"]')?.toggleAttribute("disabled", panOffset <= 0);
    const status = root.querySelector("[data-us-stock-zoom-status]");
    if (status) status.textContent = `顯示 ${visible} / ${total} 根`;
  };
  const renderChart = () => {
    const chartView = document.getElementById(chartViewId);
    if (!chartView) return;
    const { visible, panOffset } = getZoomState();
    chartView.innerHTML = renderTechnicalChart(detail, activeInterval, [...activeOverlayIndicators], [...activeMaPeriods], visible, panOffset, [...activePanelIndicators]);
    bindChartHover(chartView);
    bindHorizontalChartPan(chartView.querySelector(".sector-chart-frame"), (direction) => {
      const { total, visible, panOffset } = getZoomState();
      const step = Math.max(1, Math.round(visible * 0.35));
      const next = direction === "older"
        ? Math.min(Math.max(total - visible, 0), panOffset + step)
        : Math.max(0, panOffset - step);
      panOffsets.set(getChartKey(), next);
      renderChart();
    });
    chartView.querySelector(".sector-chart-frame")?.addEventListener("wheel", (event) => {
      event.preventDefault();
      updateZoom(event.deltaY < 0 ? "in" : "out");
    }, { passive: false });
    updateControls();
  };
  const updateZoom = (direction) => {
    const { total, minimum, visible } = getZoomState();
    let next = visible;
    if (direction === "in") next = Math.max(minimum, Math.floor(visible * 0.65));
    if (direction === "out") next = Math.min(total, Math.ceil(visible / 0.65));
    if (direction === "reset") next = total;
    if (next === visible) return;
    zoomCounts.set(getChartKey(), next);
    panOffsets.set(getChartKey(), 0);
    renderChart();
  };

  root.querySelectorAll("[data-us-interval]").forEach((button) => {
    if (button.dataset.usInterval === activeInterval) button.classList.add("is-active");
    button.addEventListener("click", () => {
      activeInterval = button.dataset.usInterval || "day";
      root.querySelectorAll("[data-us-interval]").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      renderChart();
    });
  });
  root.querySelectorAll("[data-us-ma-period]").forEach((button) => {
    button.addEventListener("click", () => {
      const period = Number(button.dataset.usMaPeriod);
      if (activeMaPeriods.has(period)) activeMaPeriods.delete(period);
      else activeMaPeriods.add(period);
      button.classList.toggle("is-active", activeMaPeriods.has(period));
      renderChart();
    });
  });
  root.querySelectorAll("[data-us-chart-indicator]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.usChartIndicator || "";
      if (activeOverlayIndicators.has(key)) activeOverlayIndicators.delete(key);
      else if (key) activeOverlayIndicators.add(key);
      button.classList.toggle("is-active", activeOverlayIndicators.has(key));
      renderChart();
    });
  });
  root.querySelectorAll("[data-us-panel-indicator]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.usPanelIndicator || "kd";
      if (activePanelIndicators.has(key) && activePanelIndicators.size > 1) activePanelIndicators.delete(key);
      else activePanelIndicators.add(key);
      root.querySelectorAll("[data-us-panel-indicator]").forEach((item) => {
        item.classList.toggle("is-active", activePanelIndicators.has(item.dataset.usPanelIndicator));
      });
      renderChart();
    });
  });
  root.querySelectorAll("[data-us-stock-zoom]").forEach((button) => {
    button.addEventListener("click", () => updateZoom(button.dataset.usStockZoom));
  });
  root.querySelectorAll("[data-us-stock-pan]").forEach((button) => {
    button.addEventListener("click", () => {
      const { total, visible, panOffset } = getZoomState();
      const step = Math.max(1, Math.round(visible * 0.35));
      const next = button.dataset.usStockPan === "older"
        ? Math.min(Math.max(total - visible, 0), panOffset + step)
        : Math.max(0, panOffset - step);
      panOffsets.set(getChartKey(), next);
      renderChart();
    });
  });
  renderChart();
  if (statusId) setText(statusId, `${detail.code} ${detail.name} 完整分析已載入。`);
}
function renderUsMarketDetailTo(rootId, item) {
  const detailRoot = document.getElementById(rootId);
  if (!detailRoot) return;
  if (!item || item.error) {
    detailRoot.innerHTML = `
      <article class="panel-card">
        <h3>查無可用資料</h3>
        <p class="source-note">${escapeHtml(item?.error || "請輸入有效的美股或 ETF 代號。")}</p>
      </article>
    `;
    return;
  }
  const detail = buildUsSearchDetail(item);
  const technicalTheory = analyzeTechnicalTheories(detail);
  const chartViewId = `${rootId}-technical-chart-view`;
  const statusId = rootId === "us-stock-detail" ? "us-stock-search-status" : "us-watchlist-status";
  const watchlistAdded = isUsStockInWatchlist({ symbol: detail.code });
  const historySummary = detail.historyCount
    ? `歷史資料：${detail.historyCount} 筆，${detail.historyStartDate || "--"} 至 ${detail.historyEndDate || "--"}`
    : "尚無歷史資料。";
  const recentHtml = detail.recentDays.map((day) => `
    <div class="history-row">
      <span>${escapeHtml(day.date)}</span>
      <span>收盤：${escapeHtml(day.close)}</span>
      <span>最高：${escapeHtml(day.high)}</span>
      <span>最低：${escapeHtml(day.low)}</span>
      <span>成交量：${escapeHtml(day.volume)}</span>
    </div>
  `).join("") || '<div class="stock-detail-empty">無可用歷史資料。</div>';
  const maOptions = [5, 10, 20, 60, 120, 240];
  const overlayOptions = [["bollinger", "布林通道"], ["fibonacci", "斐波那契"], ["supportResistance", "支撐壓力"], ["smc", "SMC"]];
  const panelOptions = TECHNICAL_PANEL_INDICATOR_OPTIONS;

  detailRoot.innerHTML = `
    <div class="card-title-row">
      <h3>${escapeHtml(detail.code)} ${escapeHtml(detail.name)}</h3>
      <div class="stock-detail-actions">
        <button class="watchlist-toggle ${watchlistAdded ? "is-added" : ""}" type="button" data-us-stock-watchlist-toggle>
          ${watchlistAdded ? "移除美股自選" : "加入美股自選"}
        </button>
        <a class="global-refresh" href="${safeUrl(buildYahooFinanceUrl(detail.code))}" target="_blank" rel="noopener noreferrer">Yahoo Finance</a>
        <span class="chip ${detail.tone === "up" ? "chip-green" : detail.tone === "down" ? "chip-red" : "chip-blue"}">${escapeHtml(detail.snapshotDate || "--")}</span>
      </div>
    </div>
    <div class="detail-metrics">
      <div><span>收盤價</span><strong>${detail.close}</strong></div>
      <div><span>漲跌幅</span><strong class="${toneClass(detail.tone)}">${escapeHtml(detail.change)} / ${escapeHtml(detail.pct)}</strong></div>
      <div><span>MA5 / MA20 / MA60</span><strong>${detail.ma5} / ${detail.ma20} / ${detail.ma60}</strong></div>
      <div><span>5 日均量</span><strong>${detail.avgVolume5}</strong></div>
      <div><span>成交量</span><strong>${formatGlobalVolume(detail.rawItem?.volume)}</strong></div>
      <div><span>月高 / 月低</span><strong>${detail.monthHigh} / ${detail.monthLow}</strong></div>
    </div>
    <p class="card-copy">${escapeHtml(detail.trend)}</p>
    <section class="technical-chart-card">
      <div class="card-title-row">
        <div>
          <h3>技術走勢圖</h3>
          <p class="chart-subtitle">K 線、均線、主圖疊加與下方指標。${escapeHtml(historySummary)}</p>
        </div>
        <div class="range-switcher" aria-label="美股技術圖時間切換">
          ${[["day", "日線"], ["week", "週線"], ["month", "月線"]].map(([key, label]) => `
            <button class="range-button" type="button" data-us-interval="${key}">${label}</button>
          `).join("")}
        </div>
      </div>
      <div class="ma-switcher" aria-label="移動平均線選項">
        <span>均線</span>
        ${maOptions.map((period) => `
          <button class="ma-option ${period === 5 ? "is-active" : ""}" type="button" data-us-ma-period="${period}">
            <i class="ma-color ma-${period}"></i>MA${period}
          </button>
        `).join("")}
      </div>
      <div class="indicator-switcher" aria-label="主圖疊加指標">
        <span>主圖疊加（可複選）</span>
        ${overlayOptions.map(([key, label]) => `<button class="indicator-option" type="button" data-us-chart-indicator="${key}">${label}</button>`).join("")}
      </div>
      <div class="indicator-switcher panel-indicator-switcher" aria-label="下方技術指標">
        <span>下方指標（可複選）</span>
        ${panelOptions.map(([key, label]) => `<button class="indicator-option ${key === "kd" ? "is-active" : ""}" type="button" data-us-panel-indicator="${key}">${label}</button>`).join("")}
      </div>
      <div class="stock-chart-zoom" aria-label="美股走勢圖縮放控制">
        <button type="button" data-us-stock-zoom="in">＋ 放大</button>
        <button type="button" data-us-stock-zoom="out" disabled>－ 縮小</button>
        <button type="button" data-us-stock-zoom="reset" disabled>重設</button>
        <button type="button" data-us-stock-pan="older" disabled>← 往前</button>
        <button type="button" data-us-stock-pan="newer" disabled>往後 →</button>
        <span data-us-stock-zoom-status>顯示 ${getChartHistory(detail, "day").length} / ${getChartHistory(detail, "day").length} 根</span>
      </div>
      <div id="${chartViewId}"></div>
    </section>
    <section class="recent-trades-card">
      <div class="card-title-row"><h3>近五日交易</h3></div>
      <div class="detail-history">${recentHtml}</div>
    </section>
    ${renderUsTechnicalTheorySection(detail, technicalTheory)}
    ${renderUsDetailAnalysisCards(detail, technicalTheory)}
    ${renderUsDetailNewsCard(detail)}
    ${renderUsValuationCompanyCard(detail)}
  `;

  detailRoot.querySelector("[data-us-stock-watchlist-toggle]")?.addEventListener("click", (event) => {
    const added = toggleUsDetailWatchlist(detail);
    event.currentTarget.textContent = added ? "移除美股自選" : "加入美股自選";
    event.currentTarget.classList.toggle("is-added", added);
    setText(statusId, added ? `已將 ${detail.code} ${detail.name} 加入美股自選。` : `已將 ${detail.code} ${detail.name} 從美股自選移除。`);
  });
  detailRoot.querySelectorAll("[data-us-chip-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const tab = String(button.dataset.usChipTab || "");
      if (!tab) return;
      stockChipTabState.set(getStockDetailCacheKey(detail.code, detail.market || "US"), tab);
      const shell = button.closest("[data-us-chip-shell]");
      if (!shell) return;
      shell.querySelectorAll("[data-us-chip-tab]").forEach((item) => {
        const active = item.dataset.usChipTab === tab;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", active ? "true" : "false");
      });
      shell.querySelectorAll("[data-us-chip-panel]").forEach((panel) => {
        const active = panel.dataset.usChipPanel === tab;
        panel.hidden = !active;
        panel.classList.toggle("is-active", active);
      });
    });
  });
  initUsVolumeMomentumCursor(detailRoot);
  bindUsDetailChartControls(detailRoot, detail, chartViewId, statusId);
}
function renderUsStockSearchDetail(item) {
  renderUsMarketDetailTo("us-stock-detail", item);
}
function renderUsStockSearchResults(results = []) {
  const container = document.getElementById("us-search-results");
  if (!container) return;
  if (!results.length) {
    container.innerHTML = '<div class="stock-detail-empty">查無美股或 ETF 搜尋結果。</div>';
    return;
  }

  container.innerHTML = results.map((item) => `
    <div class="search-result-item us-result-card" data-us-result-card>
      <button class="us-result-main-button" type="button" data-us-symbol="${escapeHtml(item.symbol || "")}">
        <span class="search-result-main">
          ${escapeHtml(item.symbol || "--")} ${escapeHtml(item.name || "")}
          <small class="search-result-market">${escapeHtml(item.group || "美股 / ETF")}</small>
        </span>
        <span class="search-result-sub">
          ${escapeHtml(item.type || "--")}
          ${item.exchange ? ` · ${escapeHtml(item.exchange)}` : ""}
          ${item.source ? ` · ${escapeHtml(item.source)}` : ""}
        </span>
      </button>
      ${item.nyseUrl ? `<a class="us-result-source-link" href="${safeUrl(item.nyseUrl)}" target="_blank" rel="noopener noreferrer">NYSE 來源</a>` : ""}
    </div>
  `).join("");

  container.querySelectorAll(".us-result-main-button[data-us-symbol]").forEach((button) => {
    button.addEventListener("click", () => {
      container.querySelectorAll("[data-us-result-card]").forEach((item) => item.classList.remove("is-active"));
      button.closest("[data-us-result-card]")?.classList.add("is-active");
      loadUsStockSymbol(button.dataset.usSymbol);
    });
  });
}
async function loadUsStockSymbol(symbol) {
  const status = document.getElementById("us-stock-search-status");
  const input = document.getElementById("us-stock-search-input");
  const cleanSymbol = String(symbol || "").trim().toUpperCase();
  if (!cleanSymbol) {
    if (status) status.textContent = "請輸入美股或 ETF 代號，例如 AAPL、NVDA、SPY、QQQ。";
    return;
  }
  if (input) input.value = cleanSymbol;
  if (status) status.textContent = `正在載入 ${cleanSymbol} 線上資料...`;
  try {
    const response = await fetchWithTimeout(`/api/us-market/symbol/${encodeURIComponent(cleanSymbol)}`, { cache: "no-store" }, 18000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const item = await response.json();
    renderUsStockSearchDetail(item);
    if (status) status.textContent = `${cleanSymbol} 已載入，資料來源 Yahoo Finance。`;
    const url = new URL(window.location.href);
    url.searchParams.set("symbol", cleanSymbol);
    url.searchParams.delete("q");
    window.history.replaceState({}, "", url);
  } catch (error) {
    if (status) status.textContent = `${cleanSymbol} 資料載入失敗。`;
    renderUsStockSearchDetail({ error: error.message || String(error) });
  }
}
async function runUsStockSearch(query, autoSelect = false) {
  const requestId = ++usStockSearchRequestId;
  const status = document.getElementById("us-stock-search-status");
  const keyword = String(query || "").trim();
  if (status) status.textContent = keyword ? `正在搜尋 ${keyword}...` : "正在載入美股與 ETF 清單...";
  try {
    const response = await fetchWithTimeout(`/api/us-market/search?q=${encodeURIComponent(keyword)}`, { cache: "no-store" }, 16000);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    if (requestId !== usStockSearchRequestId) return;
    renderUsStockSearchResults(payload.results || []);
    const totals = payload.totals || {};
    const totalText = totals["美股個股"] || totals["美股 ETF"]
      ? `全上市目錄：個股 ${totals["美股個股"] || 0} 筆、ETF ${totals["美股 ETF"] || 0} 筆。`
      : "";
    if (status) status.textContent = `列出 ${payload.count || 0} 筆結果。${totalText}來源：${payload.source || "NYSE / Yahoo Finance"}。`;
    const url = new URL(window.location.href);
    if (keyword) url.searchParams.set("q", keyword);
    else url.searchParams.delete("q");
    url.searchParams.delete("symbol");
    window.history.replaceState({}, "", url);
    if (autoSelect && payload.results?.length) {
      const first = payload.results[0];
      const selectedButton = Array.from(document.querySelectorAll("#us-search-results .us-result-main-button[data-us-symbol]"))
        .find((button) => String(button.dataset.usSymbol) === String(first.symbol));
      selectedButton?.closest("[data-us-result-card]")?.classList.add("is-active");
      loadUsStockSymbol(first.symbol);
    }
  } catch (error) {
    if (requestId !== usStockSearchRequestId) return;
    if (status) status.textContent = "美股搜尋失敗，請稍後再試。";
    renderUsStockSearchResults([]);
    console.error("Failed to search US stocks:", error);
  }
}
