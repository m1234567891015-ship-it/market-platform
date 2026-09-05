/* shadow-input:pwa.js */
(() => {
  const VERSION = "td02-full-esm-d8ed112bf37ba078";
  const STORAGE_KEY = "market-pulse-static-version";
  const SERVICE_WORKER_URL = "service-worker.js?v=td02-full-esm-d8ed112bf37ba078";
  const APP_SCOPE_PATH = "/";
  const APP_SERVICE_WORKER_PATH = "/service-worker.js";
  const APP_CACHE_PREFIX = "market-pulse-swr-";

  function isAppWorker(worker) {
    if (!worker?.scriptURL) return false;
    try {
      const scriptUrl = new URL(worker.scriptURL, window.location.href);
      return scriptUrl.origin === window.location.origin && scriptUrl.pathname === APP_SERVICE_WORKER_PATH;
    } catch {
      return false;
    }
  }

  function isAppRegistration(registration) {
    if (!registration?.scope) return false;
    try {
      const scopeUrl = new URL(registration.scope, window.location.href);
      if (scopeUrl.origin !== window.location.origin || scopeUrl.pathname !== APP_SCOPE_PATH) return false;
      return [registration.active, registration.waiting, registration.installing].some(isAppWorker);
    } catch {
      return false;
    }
  }

  async function unregisterServiceWorkers() {
    if (!("serviceWorker" in navigator)) return;
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.filter(isAppRegistration).map((registration) => registration.unregister()));
  }

  async function clearBrowserCaches() {
    if (!("caches" in window)) return;
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith(APP_CACHE_PREFIX)).map((key) => caches.delete(key)));
  }

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
      await navigator.serviceWorker.register(SERVICE_WORKER_URL);
    } catch (error) {
      console.warn(`PWA service worker registration failed`, error);
    }
  }

  function createControls() {
    const controls = document.createElement("div");
    controls.className = "pwa-controls";
    controls.setAttribute("aria-live", "polite");
    controls.innerHTML = `
      <span class="pwa-network" title="同步連線">
        <i></i><span>同步連線</span>
      </span>
    `;
    document.body.appendChild(controls);
    return controls;
  }

  function updateNetworkState(controls) {
    const status = controls.querySelector(".pwa-network");
    const label = status?.querySelector("span");
    if (!status || !label) return;
    status.classList.toggle("is-offline", !navigator.onLine);
    label.textContent = navigator.onLine ? "同步連線" : "離線";
  }

  async function syncRuntimeVersion() {
    const previousVersion = localStorage.getItem(STORAGE_KEY);
    if (previousVersion === VERSION) {
      await registerServiceWorker();
      return;
    }
    // Version bumped: flush any service worker/cache state left over from
    // the previous version before registering the current one, so a bad
    // cached state from an earlier release can never persist across a
    // version change (this is the same flush this file has always done -
    // it's now followed by a registration instead of leaving the site with
    // no service worker at all).
    await Promise.all([unregisterServiceWorkers(), clearBrowserCaches()]);
    await registerServiceWorker();
    localStorage.setItem(STORAGE_KEY, VERSION);
  }

  function bootstrapPwa() {
    const controls = createControls();
    updateNetworkState(controls);
    window.addEventListener("online", () => updateNetworkState(controls));
    window.addEventListener("offline", () => updateNetworkState(controls));
    syncRuntimeVersion()
      .catch((error) => console.warn(`PWA runtime sync ${VERSION} failed`, error));
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bootstrapPwa, { once: true });
  else bootstrapPwa();
})();

/* shadow-input:js/state.js */
let data = window.TWSE_DATA || null;
let localAllStocks = window.TWSE_ALL_STOCKS || [];
let activeStockCode = null;
let activeStockMarket = "";
let activeRenderedStockDetail = null;
let stockDetailRequestId = 0;
let stockSearchRequestId = 0;
const yahooSectorQuoteCache = new Map();
const yahooSectorChartLoading = new Set();
const yahooSectorChartErrors = new Map();
const activeYahooSectorCategories = {};
const activeYahooSectorStocks = {};
const activeYahooSectorModes = {};
const defaultYahooSectorCategoryAttempts = new Set();
const sectorComparisonZoomCounts = new Map();
const sectorComparisonPanOffsets = new Map();
const sectorSortState = { key: "source_order" };
const marketSectorRankingState = { groupKey: "listed" };
const sectorFundFlowState = { mode: "inflow" };
const usMarketSectorRankingState = { groupKey: "sp500", sortKey: "source_order" };
let assetFinanceBondFocusKey = "";
let assetFinanceBondEtfBucketKey = "all";
const SECTOR_SYNC_PICKER_LIMIT = 8;
let yahooSectorRequestId = 0;
const WATCHLIST_STORAGE_KEY = "market-pulse-watchlist-v1";
const US_WATCHLIST_STORAGE_KEY = "market-pulse-us-watchlist-v1";
const PORTFOLIO_SIM_STORAGE_KEY = "market-pulse-portfolio-sim-v1";
const US_PORTFOLIO_SIM_STORAGE_KEY = "market-pulse-us-portfolio-sim-v1";
const MARKET_BREADTH_STORAGE_KEY = "market-pulse-market-breadth-v1";
const watchlistAnalysisCache = new Map();
const watchlistDetailCache = new Map();
const usWatchlistAnalysisCache = new Map();
const usWatchlistDetailCache = new Map();
const stockSearchCache = new Map();
const stockDetailCache = new Map();
const stockDetailPending = new Map();
const stockFullDetailCache = new Map();
const stockFullDetailPending = new Map();
let internationalIndexesPromise = null;
let homePennySectorPayload = null;
let homePennySectorPromise = null;
let homePennySectorMarket = "listed";
const stockInstitutionHistoryCache = new Map();
const stockInstitutionHistoryPending = new Map();
// TD-16: structural circuit breaker for loadInstitutionalTradeHistoryIfNeeded -
// guarantees at most one trigger per stockCode for the page's lifetime,
// independent of (and in addition to) the logic-level termination check inside
// that function, so a future bug there can't regress into infinite recursion
// with renderStockDetail. See js/stock-detail.js.
const stockInstitutionHistoryAttempted = new Set();
const stockInstitutionRangeHistoryCache = new Map();
const stockShareholderCache = new Map();
const stockShareholderPending = new Map();
const stockInstitutionPeriodState = new Map();
const stockInstitutionRangeState = new Map();
const stockInstitutionSeriesState = new Map();
const stockMarginRangeState = new Map();
const stockMarginSummaryModeState = new Map();
const stockMarginTableTypeState = new Map();
const stockMarginPeriodState = new Map();
const stockChipTabState = new Map();
let liveStockDirectoryPromise = null;
let liveStockDirectoryLoaded = Boolean(localAllStocks.length);
let watchlistAnalysisRequestId = 0;
let usWatchlistAnalysisRequestId = 0;
let twEtfPayload = null;
let twEtfSelectedCode = "";
const TW_ETF_DEFAULT_PAGE_SIZE = 25;
const TW_ETF_PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
const twEtfState = {
  page: 1,
  pageSize: TW_ETF_DEFAULT_PAGE_SIZE,
  query: "",
  category: "all",
  sort: "return_desc",
};
let usMajorIndexChartSymbol = "^GSPC";
let usMajorIndexChartSymbols = ["^GSPC"];
let usMajorIndexShowVix = true;
const usMajorIndexZoomCounts = new Map();
const usMajorIndexPanOffsets = new Map();
let usSectorCompareSymbol = "";
let usSectorBenchmarkSymbol = "^GSPC";
let usSectorStockBenchmarkSymbol = "";
let usSectorStockSymbol = "";
const usSectorNyseStockState = {
  query: "",
  page: 1,
  payload: null,
  directoryPayload: null,
  directoryQuery: "",
  scopeCache: new Map(),
};
const US_SECTOR_STOCK_SELECTION_KEY = "market-pulse-us-sector-stock-selection";
const US_MAJOR_INDEX_SYMBOLS = ["^GSPC", "^DJI", "^IXIC", "^RUT"];
const US_SP500_SECTOR_SYMBOLS = ["^SP500-45", "^SP500-40", "^SP500-35", "^SP500-25", "^SP500-50", "^SP500-20", "^SP500-30", "^SP500-10", "^SP500-15", "^SP500-55", "^SP500-60"];
const US_INDUSTRY_SECTOR_SYMBOLS = ["^SOX", "^DJUSTC", "^DJUSFN", "^DJUSHC", "^DJUSEN", "^DJUSRE"];
const US_MAJOR_INDEX_SECTOR_SYMBOLS = {
  "^GSPC": US_SP500_SECTOR_SYMBOLS,
  "^DJI": ["^DJUSTC", "^DJUSFN", "^DJUSHC", "^DJUSEN", "^SP500-20", "^SP500-25", "^SP500-15", "^SP500-30"],
  "^IXIC": ["^DJUSTC", "^SOX", "^SP500-50", "^SP500-25", "^SP500-35", "^DJUSFN"],
  "^RUT": ["^SP500-20", "^SP500-40", "^SP500-25", "^SP500-35", "^SP500-10", "^SP500-15", "^SP500-60"],
};

let nativeInnerHtmlDescriptor = null;

const EXCLUDED_SECTOR_SOURCE_NAMES = new Set(["\u767c\u884c\u91cf\u52a0\u6b0a\u80a1\u50f9\u6307\u6578", "\u73bb\u7483\u9676\u74f7\u985e\u6307\u6578"]);

const WEIGHTED_SECTOR_THEME_RULES = [
  {
    id: "ai-server",
    label: "AI 伺服器鏈",
    description: "半導體、電腦週邊、電子零組件、其他電子、通訊網路與資訊服務若同步轉強，代表加權指數的 AI 硬體主線正在擴散。",
    match: /半導體|電腦週邊|電子零組件|其他電子|通訊網路|資訊服務/,
  },
  {
    id: "capital-equipment",
    label: "設備與電力鏈",
    description: "電機機械、電器電纜與油電燃氣偏強時，偏向電力、散熱、機電與基礎建設需求延伸。",
    match: /電機機械|電器電纜|油電燃氣/,
  },
  {
    id: "materials",
    label: "原物料循環",
    description: "塑膠、化學、鋼鐵、橡膠與造紙偏強時，通常反映景氣循環、報價或庫存回補題材。",
    match: /塑膠|化學|鋼鐵|橡膠|造紙/,
  },
  {
    id: "finance-defensive",
    label: "金融防禦",
    description: "金融業領先時，多半代表資金轉向高權值防禦、殖利率或利率題材。",
    match: /金融/,
  },
  {
    id: "domestic-demand",
    label: "內需消費",
    description: "食品、觀光餐旅、貿易百貨、居家生活與運動休閒偏強時，偏向內需與消費復甦輪動。",
    match: /食品|觀光餐旅|貿易百貨|居家生活|運動休閒/,
  },
];

function getWatchlist() {
  try {
    const items = JSON.parse(localStorage.getItem(WATCHLIST_STORAGE_KEY) || "[]");
    return Array.isArray(items) ? items : [];
  } catch {
    return [];
  }
}

function saveWatchlist(items) {
  localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(items));
}

function watchlistKey(stock) {
  return `${String(stock.market || "").toUpperCase()}:${stock.code}`;
}

const PORTFOLIO_FACTOR_SOURCE = {
  title: "ChatGPT 自選組合投資因素",
  url: "https://chatgpt.com/share/6a2bfa06-09ac-83e8-8d3f-6833ec6f0863",
};

const PORTFOLIO_COST_MODEL = {
  feePct: 0.1425,
  stockTaxPct: 0.3,
  etfTaxPct: 0.1,
  slippagePct: 0.1,
};

const BACKTEST_BENCHMARK_SOURCE = {
  title: "ChatGPT 股票回溯測試因素",
  url: "https://chatgpt.com/share/6a2bbd80-901c-83e8-adac-42b971b2d474",
};

const BACKTEST_DRIFT_SOURCE = {
  title: "ChatGPT 股票回測模型失真",
  url: "https://chatgpt.com/share/6a2be9b7-4548-83ee-a10f-75fff91a607c",
};

const BACKTEST_FACTOR_BASELINE = [
  "資料品質 OHLCV",
  "估值 PER/PBR/殖利率",
  "趨勢 MA",
  "動能 RSI/KD/MACD",
  "波動 ATR/布林",
  "籌碼法人/集保",
  "交易成本",
  "風控停損停利",
  "績效 MDD/Sharpe/PF",
];

const US_NYSE_DIRECTORY_PAGE_SIZE = 50;
const US_ETF_DEFAULT_PAGE_SIZE = 25;
const US_ETF_PAGE_SIZE_OPTIONS = [10, 25, 50, 100];
const usNyseDirectoryState = {
  stock: { query: "", page: 1, payload: null },
  etf: {
    query: "",
    page: 1,
    pageSize: US_ETF_DEFAULT_PAGE_SIZE,
    payload: null,
    category: "all",
    sort: "return_desc",
    quoteItems: [],
  },
};
let usEtfSelectedSymbol = "";
const US_ETF_CATEGORY_DEFINITIONS = [
  { key: "all", label: "全部" },
  { key: "market", label: "大盤指數" },
  { key: "sector", label: "產業類股" },
  { key: "bond", label: "債券" },
  { key: "dividend", label: "股息收益" },
  { key: "international", label: "海外市場" },
  { key: "factor", label: "因子風格" },
  { key: "commodity", label: "商品原物料" },
  { key: "crypto", label: "加密資產" },
  { key: "leveraged", label: "槓桿 / 反向" },
  { key: "thematic", label: "主題 / REIT" },
  { key: "other", label: "其他" },
];
const US_ETF_CATEGORY_LABELS = Object.fromEntries(US_ETF_CATEGORY_DEFINITIONS.map((item) => [item.key, item.label]));
const US_ETF_DIRECTORY_SORT_OPTIONS = [
  ["return_desc", "漲幅高到低"],
  ["return_asc", "跌幅高到低"],
  ["volume_desc", "成交量高到低"],
  ["volatility_desc", "波動高到低"],
  ["symbol", "代號排序"],
];

let derivativesFuturesDetailSymbol = "TX";
let derivativesFuturesMarketScope = "taiwan";
let derivativesFuturesFrameworkScope = "taiwan";
const derivativesFuturesRegionalExpandedKeys = new Set();
const derivativesFuturesTechnicalChartStates = new Map();
const derivativesFuturesTechnicalContractState = new Map();
const derivativesFuturesTechnicalIntervalState = new Map();
const derivativesFuturesTechnicalIndicatorState = new Map();
const derivativesFuturesStockStyleMaState = new Map();
const derivativesFuturesStockStyleOverlayState = new Map();
const derivativesFuturesStockStylePanelState = new Map();
const derivativesFuturesStockStyleVisibleState = new Map();
const derivativesFuturesStockStylePanState = new Map();
const derivativesFuturesTechnicalSeriesCache = new Map();
const derivativesFuturesTechnicalLoadingKeys = new Set();
const FUTURES_TECHNICAL_INTERVAL_OPTIONS = [
  { key: "day", label: "日線" },
  { key: "week", label: "週線" },
  { key: "month", label: "月線" },
];
const FUTURES_TECHNICAL_INDICATOR_OPTIONS = [
  { key: "ma", label: "均線" },
  { key: "macd", label: "MACD" },
  { key: "oscillator", label: "RSI / KD" },
  { key: "trend", label: "趨勢" },
  { key: "volume", label: "量能" },
  { key: "chips", label: "籌碼" },
];
const TECHNICAL_PANEL_INDICATOR_OPTIONS = [
  ["kd", "KD"],
  ["macd", "MACD"],
  ["rsi", "RSI"],
  ["dmi", "DMI"],
  ["bias", "BIAS"],
  ["obv", "OBV"],
  ["atr", "ATR"],
  ["cci", "CCI"],
  ["williams", "Williams %R"],
  ["mfi", "MFI"],
  ["momentum", "Momentum"],
  ["sar", "SAR"],
  ["bollinger", "Bollinger"],
  ["ichimoku", "Ichimoku"],
];
const TECHNICAL_PANEL_INDICATOR_KEYS = TECHNICAL_PANEL_INDICATOR_OPTIONS.map(([key]) => key);
const DERIVATIVES_WATCHLIST_STORAGE_KEY = "market-pulse-derivatives-watchlist-v1";
const DERIVATIVE_ASSET_NAME_MAP = {
  futures: {
    sourceName: "期貨",
    sourceHref: "derivatives-assets.html#asset-futures",
    targetName: "futures.html",
    targetHref: "futures.html",
    rows: [
      ["期貨市場", "期貨市場"],
      ["期貨資料來源", "期貨資料來源"],
      ["國內期貨未平倉資料", "國內期貨未平倉資料"],
      ["期貨地區市場", "期貨地區市場"],
      ["期貨線上資料明細", "期貨線上資料明細"],
      ["期貨 AI 風險情境", "期貨 AI 風險情境"],
    ],
  },
  options: {
    sourceName: "市場選擇權鏈",
    sourceHref: "derivatives-assets.html#asset-options",
    targetName: "options.html",
    targetHref: "options.html",
    rows: [
      ["市場選擇權鏈", "市場選擇權鏈"],
      ["台灣選擇權 AI 盤勢摘要", "台灣選擇權 AI 盤勢摘要"],
      ["CBOE VIX 市場情緒", "CBOE VIX 市場情緒"],
      ["選擇權地區市場", "選擇權地區市場"],
      ["選擇權觀察線上資料明細", "選擇權觀察線上資料明細"],
    ],
  },
  ai: {
    sourceName: "AI analysis",
    sourceHref: "derivatives-assets.html#asset-options",
    targetName: "derivatives-analytics.html",
    targetHref: "derivatives-analytics.html#derivatives-analytics-market-state",
    rows: [
      ["台灣選擇權 AI 盤勢摘要", "台灣選擇權 AI 盤勢摘要"],
      ["TXO 選擇權資料架構", "TXO 選擇權資料架構"],
      ["期貨 AI 風險情境", "期貨 AI 風險情境"],
      ["資料庫與官方來源架構", "資料庫與官方來源架構"],
      ["期貨 / 選擇權資料快照", "期貨 / 選擇權資料快照"],
    ],
  },
};

function getSelectedFuturesTechnicalContract(item) {
  const contracts = Array.isArray(item?.technicalContracts) ? item.technicalContracts : [];
  if (!contracts.length) return null;
  const symbol = String(item?.symbol || "").toUpperCase();
  const selectedCode = String(derivativesFuturesTechnicalContractState.get(symbol) || "").toUpperCase();
  return contracts.find((contract) => String(contract?.code || "").toUpperCase() === selectedCode)
    || contracts.find((contract) => contract?.isPrimary)
    || contracts[0];
}

function getSelectedFuturesTechnicalInterval(item) {
  const symbol = String(item?.symbol || "").toUpperCase();
  const selected = String(derivativesFuturesTechnicalIntervalState.get(symbol) || "day").toLowerCase();
  return FUTURES_TECHNICAL_INTERVAL_OPTIONS.some((option) => option.key === selected) ? selected : "day";
}

function getFuturesTechnicalIntervalLabel(interval) {
  return FUTURES_TECHNICAL_INTERVAL_OPTIONS.find((option) => option.key === interval)?.label || "日線";
}

function getFuturesTechnicalIndicatorStateKey(item) {
  const symbol = String(item?.symbol || "").toUpperCase();
  const contract = getSelectedFuturesTechnicalContract(item);
  const interval = item?.technicalCandleInterval || getSelectedFuturesTechnicalInterval(item);
  return getFuturesTechnicalSeriesCacheKey(symbol, contract, interval);
}

function getSelectedFuturesTechnicalIndicatorView(item) {
  const stateKey = getFuturesTechnicalIndicatorStateKey(item);
  const selected = String(derivativesFuturesTechnicalIndicatorState.get(stateKey) || "ma").toLowerCase();
  return FUTURES_TECHNICAL_INDICATOR_OPTIONS.some((option) => option.key === selected) ? selected : "ma";
}

function getFuturesTechnicalSeriesCacheKey(symbol, contract, interval) {
  const cleanSymbol = String(symbol || "").toUpperCase();
  const cleanCode = String(contract?.code || "").toUpperCase();
  const cleanInterval = String(interval || "day").toLowerCase();
  return `${cleanSymbol}:${cleanCode}:${cleanInterval}`;
}

function getFuturesTechnicalCachedPayload(item) {
  const selectedContract = getSelectedFuturesTechnicalContract(item);
  const interval = getSelectedFuturesTechnicalInterval(item);
  const key = getFuturesTechnicalSeriesCacheKey(item?.symbol, selectedContract, interval);
  return {
    key,
    interval,
    selectedContract,
    cached: derivativesFuturesTechnicalSeriesCache.get(key) || null,
    isLoading: derivativesFuturesTechnicalLoadingKeys.has(key),
  };
}

const TAIWAN_OPTION_PRODUCT_FALLBACKS = [
  { symbol: "TXO", name: "臺指選擇權", shortName: "台指選" },
  { symbol: "MXO", name: "小型臺指選擇權", shortName: "小台選" },
  { symbol: "TFO", name: "金融選擇權", shortName: "金指選" },
  { symbol: "TEO", name: "電子選擇權", shortName: "電指選" },
  { symbol: "CDO", name: "台積電選擇權", shortName: "台積電選" },
  { symbol: "DVO", name: "聯發科選擇權", shortName: "聯發科選" },
  { symbol: "DHO", name: "鴻海選擇權", shortName: "鴻海選" },
  { symbol: "T50O", name: "臺灣50選擇權", shortName: "臺灣50選" },
];

const TAIWAN_OPTION_CHAIN_UNDERLYINGS = new Set(TAIWAN_OPTION_PRODUCT_FALLBACKS.map((item) => item.symbol));

const OPTIONS_DOCUMENT_CATEGORY_ORDER = [
  "指數選擇權",
  "股票選擇權",
  "ETF 選擇權",
  "商品選擇權",
  "外匯選擇權",
  "利率選擇權",
  "波動率選擇權",
  "加密貨幣選擇權",
  "天氣選擇權",
  "碳權選擇權",
];

const OPTIONS_MARKET_CHAIN_SYMBOL_ALIASES = {
  "^GSPC": "_SPX",
  "^SPX": "_SPX",
  "^NDX": "_NDX",
  "^DJI": "_DJX",
  "^DJX": "_DJX",
  "^XSP": "_XSP",
  "^RUT": "_RUT",
  "^VIX": "_VIX",
  "BTC-USD": "DERIBIT_BTC",
  "ETH-USD": "DERIBIT_ETH",
  "SOL-USD": "BYBIT_SOL",
  "XRP-USD": "BYBIT_XRP",
  "EURUSD=X": "E6=F",
  "JPY=X": "J6=F",
  "GBPUSD=X": "B6=F",
  "AUDUSD=X": "A6=F",
  "DX-Y.NYB": "D6=F",
};

const OPTIONS_MARKET_CHAIN_FUTURES_SYMBOLS = new Set([
  "GC=F", "SI=F", "PL=F", "PA=F", "HG=F",
  "CL=F", "NG=F", "RB=F", "HO=F",
  "ZS=F", "ZC=F", "ZW=F", "KC=F", "CC=F", "SB=F", "CT=F", "LE=F", "HE=F",
  "ZQ=F", "ZT=F", "ZF=F", "ZN=F", "ZB=F", "E6=F", "J6=F", "B6=F", "A6=F", "D6=F",
]);

let derivativesOptionsSelectedStrategy = "";
let derivativesOptionsChainSource = "auto";
let derivativesOptionsSelectedUnderlying = "TXO";
let derivativesOptionsSelectedFocus = "option-region-0";
let derivativesOptionsSelectedStrike = "";
const derivativesOptionsRegionalExpandedKeys = new Set();
const DERIVATIVES_OPTIONS_AUTO_REFRESH_MS = 5 * 60 * 1000;
let derivativesOptionsAutoRefreshTimer = null;
let derivativesOptionsAutoRefreshPayload = null;
let derivativesOptionsAutoRefreshInFlight = false;

let derivativesOptionsMarketChainInFlightKey = "";

let optionsAiExtrasCache = null;
let optionsAiExtrasLoading = false;

let usStockSearchRequestId = 0;

const ASSET_HUB_REGION_ORDER = ["台灣", "美國", "歐洲", "亞洲", "全球 / 其他"];
const ASSET_HUB_SCHEMA_FALLBACK = {
  automation: "API 取數、ETL 清洗、資料庫寫入、排程更新與異常監控",
  dashboardSignals: [
    "Yield Curve",
    "Credit Spread",
    "DXY",
    "VIX",
    "Gold / Silver Ratio",
    "Global Futures",
    "Central Bank Rates",
  ],
  sources: [
    { name: "Bloomberg / LSEG Refinitiv / FactSet", role: "機構級行情、基本資料與跨資產資料庫" },
    { name: "Morningstar / S&P Global Market Intelligence", role: "基金、ETF、債券與信用資料補充" },
    { name: "TAIFEX / CME / ICE / Eurex / SGX", role: "期貨與選擇權交易所官方合約與未平倉資料" },
    { name: "U.S. Treasury / FRED", role: "美債殖利率曲線、利率與總體時間序列" },
    { name: "LBMA / COMEX", role: "貴金屬價格、期貨與參考資料" },
    { name: "OCC / Cboe", role: "公開市場波動率與風險指數" },
  ],
  tables: [
    { name: "futures_master", label: "期貨商品主檔" },
    { name: "options_chain", label: "選擇權鏈與未平倉" },
    { name: "bond_master", label: "債券主檔" },
    { name: "bond_yield_history", label: "債券殖利率歷史" },
    { name: "rating_history", label: "信評歷史" },
    { name: "macro_indicator", label: "總體指標" },
    { name: "fx_rates", label: "外匯匯率" },
  ],
};

const ASSET_HUB_OPTION_CHAIN_UNDERLYINGS = [
  ["SPY", "標普 500 ETF"],
  ["QQQ", "那斯達克 100 ETF"],
  ["IWM", "羅素 2000 ETF"],
  ["NVDA", "NVIDIA"],
  ["TSLA", "Tesla"],
];

const ASSET_FINANCE_TREND_RANGES = [
  { key: "1m", label: "1M", limit: 22 },
  { key: "3m", label: "3M", limit: 66 },
  { key: "6m", label: "6M", limit: 126 },
  { key: "1y", label: "1Y", limit: 240 },
];

const ASSET_FINANCE_TREND_FILTERS = [
  { key: "all", label: "全部" },
  { key: "gold", label: "黃金" },
  { key: "silver", label: "白銀" },
  { key: "platinum", label: "鉑金" },
  { key: "palladium", label: "鈀金" },
];

let assetFinanceTrendChartCounter = 0;

/* shadow-input:js/core.js */
function toneClass(tone) {
  if (tone === "up") return "up";
  if (tone === "down") return "down";
  return "flat";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function normalizeSafeUrl(value, fallback = "#") {
  const raw = String(value ?? "").trim();
  const fallbackUrl = String(fallback ?? "#").trim() || "#";
  if (!raw) return fallbackUrl;
  const compact = raw.replace(/[\u0000-\u001f\u007f\s]+/g, "").toLowerCase();
  if (compact.startsWith("javascript:") || compact.startsWith("data:") || compact.startsWith("vbscript:")) return fallbackUrl;
  if (raw.startsWith("#") || raw.startsWith("/") || raw.startsWith("./") || raw.startsWith("../")) return raw;
  try {
    const parsed = new URL(raw, window.location.origin);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? raw : fallbackUrl;
  } catch {
    return fallbackUrl;
  }
}

function safeUrl(value, fallback = "#") {
  return escapeHtml(normalizeSafeUrl(value, fallback));
}

function sanitizeHtml(value) {
  const template = document.createElement("template");
  const html = String(value ?? "");
  if (nativeInnerHtmlDescriptor?.set) {
    nativeInnerHtmlDescriptor.set.call(template, html);
  } else {
    template.innerHTML = html;
  }
  template.content.querySelectorAll("script, iframe, object, embed").forEach((node) => node.remove());
  template.content.querySelectorAll("*").forEach((node) => {
    [...node.attributes].forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      if (name.startsWith("on")) {
        node.removeAttribute(attribute.name);
        return;
      }
      if (["href", "src", "xlink:href", "formaction"].includes(name)) {
        node.setAttribute(attribute.name, normalizeSafeUrl(attribute.value));
      }
    });
  });
  if (nativeInnerHtmlDescriptor?.get) {
    return nativeInnerHtmlDescriptor.get.call(template);
  }
  return template.innerHTML;
}

(function enforceSafeInnerHtml() {
  if (window.__MARKET_PULSE_SAFE_INNER_HTML__) return;
  const descriptor = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
  if (!descriptor?.set || !descriptor?.get) return;
  nativeInnerHtmlDescriptor = descriptor;
  window.__MARKET_PULSE_SAFE_INNER_HTML__ = true;
  Object.defineProperty(Element.prototype, "innerHTML", {
    configurable: descriptor.configurable,
    enumerable: descriptor.enumerable,
    get() {
      return descriptor.get.call(this);
    },
    set(value) {
      descriptor.set.call(this, sanitizeHtml(value));
    },
  });
})();

function formatRocDateFromDate(date) {
  const year = String(date.getFullYear() - 1911).padStart(3, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}/${month}/${day}`;
}

function parseTwseNumber(value) {
  const parsed = Number(String(value ?? "").replace(/,/g, "").trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function formatYmdDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function parseYmdDate(value) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return new Date();
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day));
}

function clampScore(value) {
  if (!Number.isFinite(value)) return 50;
  return Math.max(0, Math.min(100, Math.round(value)));
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function parseAnalysisNumber(value) {
  if (value === null || value === undefined || value === "" || value === "--") return null;
  const parsed = Number(String(value).replace(/,/g, "").replace("%", "").trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function parseMarketNumber(value) {
  if (value === null || value === undefined) return null;
  const parsed = Number(String(value).replace(/,/g, "").replace("%", "").trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function formatGlobalValue(value, digits = 2) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  return parsed.toLocaleString("zh-TW", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatGlobalVolume(value) {
  const parsed = parseMarketNumber(value);
  if (!Number.isFinite(parsed)) return "--";
  if (parsed >= 1000000000) return `${(parsed / 1000000000).toFixed(2)}B`;
  if (parsed >= 1000000) return `${(parsed / 1000000).toFixed(2)}M`;
  return Math.round(parsed).toLocaleString("zh-TW");
}

function formatSignedPercentValue(value, digits = 2) {
  return Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%` : "--";
}

function formatUsDetailMetric(value, digits = 2) {
  const parsed = parseMarketNumber(value);
  return Number.isFinite(parsed) ? parsed.toLocaleString("zh-TW", { maximumFractionDigits: digits }) : "--";
}

function formatBacktestRatio(value, digits = 2) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : "--";
}

function formatBacktestPercent(value, digits = 0) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "--";
  const percent = Math.abs(parsed) <= 1 ? parsed * 100 : parsed;
  return `${percent.toFixed(digits)}%`;
}

function formatUsSimulationMoney(value) {
  if (!Number.isFinite(value)) return "--";
  const prefix = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${prefix}US$${Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function assetHubTone(item) {
  const pct = parseMarketNumber(item?.pct);
  return pct > 0 ? "up" : pct < 0 ? "down" : "flat";
}

function formatAssetHubExpiration(value) {
  const text = String(value || "").trim();
  const timestamp = Number(text);
  if (!text) return "--";
  if (!Number.isFinite(timestamp) || timestamp <= 0) return text;
  return new Date(timestamp * 1000).toISOString().slice(0, 10);
}

function formatAssetOptionNumber(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return number.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function formatAssetOptionWhole(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return Math.round(number).toLocaleString("en-US");
}

function formatAssetOptionIv(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${(number * 100).toFixed(1)}%`;
}

function formatChartDate(date) {
  if (!date) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/* shadow-input:js/api.js */
async function fetchWithTimeout(url, options = {}, timeoutMs = 8000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

/* shadow-input:js/shared-calc.js */
function normalizePortfolioHistory(detail) {
  return (detail?.historyDays || [])
    .map((item) => ({
      date: item.date || item.label || "",
      close: parseAnalysisNumber(item.close),
      high: parseAnalysisNumber(item.high),
      low: parseAnalysisNumber(item.low),
      volume: parseAnalysisNumber(item.volume),
    }))
    .filter((item) => Number.isFinite(item.close));
}
function calculatePortfolioReturns(history, lookback = 80) {
  const window = history.slice(-lookback);
  const returns = [];
  for (let index = 1; index < window.length; index += 1) {
    const previous = window[index - 1]?.close;
    const current = window[index]?.close;
    if (previous > 0 && current > 0) returns.push((current - previous) / previous);
  }
  return returns;
}
function calculatePortfolioStdDev(values) {
  const clean = values.filter(Number.isFinite);
  if (clean.length < 2) return 0;
  const average = clean.reduce((sum, value) => sum + value, 0) / clean.length;
  const variance = clean.reduce((sum, value) => sum + (value - average) ** 2, 0) / (clean.length - 1);
  return Math.sqrt(Math.max(variance, 0));
}
function calculatePortfolioCorrelation(left, right) {
  const length = Math.min(left.length, right.length);
  if (length < 8) return null;
  const a = left.slice(-length);
  const b = right.slice(-length);
  const avgA = a.reduce((sum, value) => sum + value, 0) / length;
  const avgB = b.reduce((sum, value) => sum + value, 0) / length;
  let numerator = 0;
  let denomA = 0;
  let denomB = 0;
  for (let index = 0; index < length; index += 1) {
    const da = a[index] - avgA;
    const db = b[index] - avgB;
    numerator += da * db;
    denomA += da * da;
    denomB += db * db;
  }
  const denominator = Math.sqrt(denomA * denomB);
  return denominator ? numerator / denominator : null;
}
function calculatePeriodReturn(history, days) {
  if (!Array.isArray(history) || history.length < 2) return null;
  const end = history.at(-1)?.close;
  const start = history.length > days ? history.at(-(days + 1))?.close : history[0]?.close;
  if (!(start > 0) || !(end > 0)) return null;
  return ((end - start) / start) * 100;
}
function buildPortfolioTheoryAssessment(active, totals) {
  if (!active.length || !(totals.totalValue > 0)) {
    return {
      label: "等待部位資料",
      tone: "neutral",
      details: ["尚未建立持股權重，暫無法計算均值-變異、相關性與風險貢獻。"],
      actions: ["先輸入股數與進場價，再檢查單一權重、相關性與組合波動。"],
      metrics: {
        expectedReturn60: null,
        portfolioVolatility: null,
        averageCorrelation: null,
        diversificationRatio: null,
        effectivePositions: 0,
        efficiencyScore: null,
        topRiskContributor: null,
      },
    };
  }

  const items = active.map((position) => {
    const history = normalizePortfolioHistory(position.detail);
    const returns = calculatePortfolioReturns(history, 90);
    const dailyVolatility = calculatePortfolioStdDev(returns);
    const annualVolatility = dailyVolatility * Math.sqrt(252) * 100;
    const return20 = calculatePeriodReturn(history, 20);
    const return60 = calculatePeriodReturn(history, 60);
    const weight = position.marketValue / totals.totalValue;
    return {
      ...position,
      history,
      returns,
      dailyVolatility,
      annualVolatility,
      return20,
      return60,
      weight,
    };
  });

  const expectedReturn60 = items.reduce((sum, item) => sum + item.weight * (Number.isFinite(item.return60) ? item.return60 : Number.isFinite(item.return20) ? item.return20 : 0), 0);
  let covarianceSum = 0;
  let correlationSum = 0;
  let correlationCount = 0;
  for (let i = 0; i < items.length; i += 1) {
    for (let j = 0; j < items.length; j += 1) {
      const corr = i === j ? 1 : calculatePortfolioCorrelation(items[i].returns, items[j].returns);
      const safeCorr = Number.isFinite(corr) ? corr : 0.35;
      covarianceSum += items[i].weight * items[j].weight * items[i].dailyVolatility * items[j].dailyVolatility * safeCorr;
      if (j > i && Number.isFinite(corr)) {
        correlationSum += corr;
        correlationCount += 1;
      }
    }
  }
  const portfolioVolatility = Math.sqrt(Math.max(covarianceSum, 0)) * Math.sqrt(252) * 100;
  const weightedVolatility = items.reduce((sum, item) => sum + item.weight * item.annualVolatility, 0);
  const diversificationRatio = portfolioVolatility > 0 ? weightedVolatility / portfolioVolatility : null;
  const averageCorrelation = correlationCount ? correlationSum / correlationCount : null;
  const hhi = items.reduce((sum, item) => sum + item.weight ** 2, 0);
  const effectivePositions = hhi ? 1 / hhi : 0;
  const efficiencyScore = portfolioVolatility > 0 ? expectedReturn60 / portfolioVolatility : null;
  const riskBase = items.reduce((sum, item) => sum + item.weight * item.dailyVolatility, 0);
  const riskContributors = items.map((item) => ({
    code: item.stock.code,
    name: item.stock.name,
    contribution: riskBase ? (item.weight * item.dailyVolatility / riskBase) * 100 : item.weight * 100,
  })).sort((a, b) => b.contribution - a.contribution);
  const topRiskContributor = riskContributors[0] || null;

  const tone = portfolioVolatility >= 45 || effectivePositions < 2 || (averageCorrelation ?? 0) >= 0.75
    ? "negative"
    : portfolioVolatility >= 28 || effectivePositions < 3 || (averageCorrelation ?? 0) >= 0.55
      ? "neutral"
      : "positive";
  const label = tone === "positive" ? "組合理論結構健康" : tone === "negative" ? "組合理論風險偏高" : "組合理論需再平衡";
  const details = [
    `均值-變異：60 日權重動能 ${expectedReturn60 >= 0 ? "+" : ""}${expectedReturn60.toFixed(2)}%，年化波動估計 ${portfolioVolatility.toFixed(2)}%。`,
    `分散化：有效持股數 ${effectivePositions.toFixed(1)} 檔，分散化比率 ${Number.isFinite(diversificationRatio) ? diversificationRatio.toFixed(2) : "--"}。`,
    `相關性：平均相關係數 ${Number.isFinite(averageCorrelation) ? averageCorrelation.toFixed(2) : "資料不足"}，用於辨識同漲同跌風險。`,
    topRiskContributor ? `風險貢獻：${topRiskContributor.code} ${topRiskContributor.name} 約占 ${topRiskContributor.contribution.toFixed(1)}%。` : "風險貢獻資料不足。",
  ];
  const actions = [];
  if (effectivePositions < 2) actions.push("有效持股數偏低，組合接近單押，建議加入低相關標的或降低單一部位。");
  if ((averageCorrelation ?? 0) >= 0.65) actions.push("持股相關性偏高，分散看似增加但實際風險可能仍集中。");
  if (portfolioVolatility >= 35) actions.push("組合波動偏高，應降低高波動持股權重或提高現金/ETF 比例。");
  if (topRiskContributor?.contribution >= 45) actions.push(`最大風險貢獻集中在 ${topRiskContributor.code}，再平衡時優先檢查該部位。`);
  if (Number.isFinite(efficiencyScore) && efficiencyScore < 0) actions.push("風險效率為負，代表近期承擔波動未換得正向動能，宜保守。");
  if (!actions.length) actions.push("權重、相關性與波動暫未出現重大失衡，可依停損停利紀律持續監控。");

  return {
    label,
    tone,
    details,
    actions,
    metrics: {
      expectedReturn60,
      portfolioVolatility,
      averageCorrelation,
      diversificationRatio,
      effectivePositions,
      efficiencyScore,
      topRiskContributor,
    },
  };
}
function getSimulationSignal(analysis, currentPrice, entryPrice, shares, stopLossPct, takeProfitPct) {
  if (!(shares > 0) || !(entryPrice > 0) || !(currentPrice > 0)) {
    if (analysis?.score >= 5) return { label: "偏多等待回檔", tone: "positive", note: `型態與指標多方訊號較一致；${analysis.patterns?.[0] || "仍宜設定停損後再評估進場"}。` };
    if (analysis?.score <= -5) return { label: "暫緩進場", tone: "negative", note: `型態與指標偏弱；${analysis.indicators?.[0] || "等待趨勢止穩較為穩健"}。` };
    return { label: "等待確認", tone: "neutral", note: "目前尚未建立模擬部位，先觀察趨勢與籌碼共振。" };
  }

  const returnPct = ((currentPrice - entryPrice) / entryPrice) * 100;
  if (returnPct <= -stopLossPct) {
    return { label: "停損條件觸發", tone: "negative", note: "目前跌幅已超過設定停損，應重新檢視原始投資假設。" };
  }
  if (returnPct >= takeProfitPct) {
    return { label: "進入停利區間", tone: "positive", note: "已達模擬停利條件，可評估分批落袋或移動停利。" };
  }
  if (returnPct <= -stopLossPct * 0.7) {
    return { label: "接近停損", tone: "negative", note: "距離停損條件已近，避免因情緒任意放寬風險界線。" };
  }
  if (analysis?.score <= -5) {
    return { label: "弱勢減碼觀察", tone: "negative", note: `技術理論與多因子偏弱，${analysis.patterns?.[0] || "持有部位宜優先控制曝險"}。` };
  }
  if (analysis?.score >= 5 && returnPct >= 0) {
    return { label: "趨勢續抱觀察", tone: "positive", note: `損益與技術訊號同向，${analysis.indicators?.[0] || "可依原訂停利停損紀律續抱"}。` };
  }
  return { label: "區間持有觀察", tone: "neutral", note: "尚未觸及停損停利，持續觀察均線、法人與量價變化。" };
}
function technicalSma(values, period) {
  return values.map((_, index) => {
    if (index + 1 < period) return null;
    const window = values.slice(index - period + 1, index + 1);
    return window.every(Number.isFinite)
      ? window.reduce((sum, value) => sum + value, 0) / period
      : null;
  });
}
function technicalSlope(values) {
  const clean = values.filter(Number.isFinite);
  if (clean.length < 2) return 0;
  const center = (clean.length - 1) / 2;
  const average = clean.reduce((sum, value) => sum + value, 0) / clean.length;
  let numerator = 0;
  let denominator = 0;
  clean.forEach((value, index) => {
    const offset = index - center;
    numerator += offset * (value - average);
    denominator += offset * offset;
  });
  return denominator ? numerator / denominator : 0;
}
function technicalPivots(history, radius = 2) {
  const pivots = [];
  for (let index = radius; index < history.length - radius; index += 1) {
    const window = history.slice(index - radius, index + radius + 1);
    const high = history[index].high;
    const low = history[index].low;
    if (window.every((item) => high >= item.high)) pivots.push({ index, type: "high", value: high });
    if (window.every((item) => low <= item.low)) pivots.push({ index, type: "low", value: low });
  }
  return pivots.sort((a, b) => a.index - b.index);
}
function buildMarketBreadthIndicators(detail) {
  const requestedMarket = String(detail.market || "").toUpperCase();
  const stocks = (localAllStocks || []).filter((stock) => {
    const market = String(stock.market || "").toUpperCase();
    const securityType = String(stock.securityType || "").toUpperCase();
    const code = String(stock.code || "");
    const isStock = securityType
      ? securityType === "STOCK"
      : /^\d{4}$/.test(code) && !code.startsWith("00");
    return isStock && (!requestedMarket || market === requestedMarket);
  });
  const advancing = stocks.filter((stock) => parseAnalysisNumber(stock.pct) > 0).length;
  const declining = stocks.filter((stock) => parseAnalysisNumber(stock.pct) < 0).length;
  const unchanged = stocks.filter((stock) => parseAnalysisNumber(stock.pct) === 0).length;
  if (!advancing && !declining) return null;

  const adr = declining ? (advancing / declining) * 100 : advancing ? 999 : 100;
  const obos = advancing - declining;
  const date = detail.snapshotDate || data?.snapshotDate || new Date().toISOString().slice(0, 10);
  let history = [];
  try {
    history = JSON.parse(localStorage.getItem(MARKET_BREADTH_STORAGE_KEY) || "[]");
    if (!Array.isArray(history)) history = [];
  } catch {
    history = [];
  }
  const marketKey = requestedMarket || "ALL";
  const previous = [...history].reverse().find((item) => item.market === marketKey && item.date < date);
  const adl = (Number(previous?.adl) || 0) + obos;
  const snapshot = { date, market: marketKey, advancing, declining, unchanged, adr, obos, adl };
  const nextHistory = [
    ...history.filter((item) => !(item.market === marketKey && item.date === date)),
    snapshot,
  ].sort((a, b) => String(a.date).localeCompare(String(b.date))).slice(-180);
  try {
    localStorage.setItem(MARKET_BREADTH_STORAGE_KEY, JSON.stringify(nextHistory));
  } catch {
    // Storage can be unavailable in private or restricted browser contexts.
  }
  const marketHistory = nextHistory.filter((item) => item.market === marketKey);
  const previousAdl = marketHistory.length >= 2 ? Number(marketHistory.at(-2).adl) : null;
  return { ...snapshot, previousAdl, historyCount: marketHistory.length };
}
function buildFuturesBreadthProxyIndicators(history, period = 20) {
  if (!Array.isArray(history) || history.length < 6) return [];
  const comparable = history
    .map((row, index) => (index > 0 ? { row, previous: history[index - 1] } : null))
    .filter(Boolean)
    .slice(-Math.min(period, Math.max(history.length - 1, 1)));
  if (!comparable.length) return [];

  const advancing = comparable.filter(({ row, previous }) => row.close > previous.close).length;
  const declining = comparable.filter(({ row, previous }) => row.close < previous.close).length;
  const unchanged = comparable.length - advancing - declining;
  const adr = declining ? (advancing / declining) * 100 : advancing ? 999 : 100;
  const obos = advancing - declining;
  const obosPct = (obos / Math.max(comparable.length, 1)) * 100;
  const upVolume = comparable
    .filter(({ row, previous }) => row.close > previous.close)
    .reduce((sum, { row }) => sum + (Number.isFinite(row.volume) ? row.volume : 0), 0);
  const downVolume = comparable
    .filter(({ row, previous }) => row.close < previous.close)
    .reduce((sum, { row }) => sum + (Number.isFinite(row.volume) ? row.volume : 0), 0);
  const volumeBreadth = upVolume + downVolume > 0 ? (upVolume / (upVolume + downVolume)) * 100 : null;
  const deltaVolume = upVolume - downVolume;
  const firstClose = comparable[0]?.previous?.close;
  const latestClose = comparable.at(-1)?.row?.close;
  const closeChangePct = Number.isFinite(firstClose) && firstClose !== 0 && Number.isFinite(latestClose)
    ? ((latestClose - firstClose) / firstClose) * 100
    : null;
  const oiWindow = history
    .slice(-Math.min(period + 1, history.length))
    .map((row) => parseAnalysisNumber(row.openInterest))
    .filter(Number.isFinite);
  const oiChange = oiWindow.length >= 2 ? oiWindow.at(-1) - oiWindow[0] : null;
  const oiChangePct = Number.isFinite(oiChange) && Number.isFinite(oiWindow[0]) && oiWindow[0] !== 0
    ? (oiChange / oiWindow[0]) * 100
    : null;
  const signals = [];
  const periodText = `近 ${comparable.length} 根`;
  const adrDirection = adr >= 125 ? "bullish" : adr <= 80 ? "bearish" : "neutral";
  signals.push({
    name: "漲跌K比率 ADR代理",
    value: `${adr.toFixed(1)}%`,
    text: `${periodText}上漲 ${advancing} 根、下跌 ${declining} 根、平盤 ${unchanged} 根；以期貨自身 K 線替代市場廣度。`,
    direction: adrDirection,
    scoreDelta: adrDirection === "bullish" ? 1 : adrDirection === "bearish" ? -1 : 0,
  });
  const obosDirection = obosPct >= 15 ? "bullish" : obosPct <= -15 ? "bearish" : "neutral";
  signals.push({
    name: "OBOS K線代理",
    value: `${obos > 0 ? "+" : ""}${obos}`,
    text: `淨上漲 K 數占比 ${obosPct.toFixed(1)}%；${Math.abs(obosPct) >= 25 ? "短線情緒偏極端，需搭配量能確認" : "多空尚未過度擁擠"}。`,
    direction: obosDirection,
    scoreDelta: obosDirection === "bullish" ? 1 : obosDirection === "bearish" ? -1 : 0,
  });
  if (Number.isFinite(volumeBreadth)) {
    const volumeDirection = volumeBreadth >= 55 ? "bullish" : volumeBreadth <= 45 ? "bearish" : "neutral";
    signals.push({
      name: "上漲量占比",
      value: `${volumeBreadth.toFixed(1)}%`,
      text: `上漲 K 成交量 ${formatGlobalVolume(upVolume)}、下跌 K 成交量 ${formatGlobalVolume(downVolume)}；Delta Volume ${deltaVolume >= 0 ? "+" : ""}${formatGlobalVolume(deltaVolume)}。`,
      direction: volumeDirection,
      scoreDelta: volumeDirection === "bullish" ? 1 : volumeDirection === "bearish" ? -1 : 0,
    });
  }
  if (Number.isFinite(oiChange)) {
    const oiDirection = oiChange > 0 ? "bullish" : oiChange < 0 ? "bearish" : "neutral";
    signals.push({
      name: "未平倉 OI 趨勢",
      value: `${oiChange >= 0 ? "+" : ""}${formatGlobalVolume(oiChange)}`,
      text: `${periodText}未平倉${oiChange >= 0 ? "增加" : "下降"}${Number.isFinite(oiChangePct) ? ` ${oiChangePct >= 0 ? "+" : ""}${oiChangePct.toFixed(2)}%` : ""}；用來判斷部位是否留在場內。`,
      direction: oiDirection,
      scoreDelta: oiDirection === "bullish" ? 1 : oiDirection === "bearish" ? -1 : 0,
    });
    const structureDirection = Number.isFinite(closeChangePct)
      ? closeChangePct >= 0 && oiChange >= 0
        ? "bullish"
        : closeChangePct < 0 && oiChange >= 0
          ? "bearish"
          : closeChangePct >= 0 && oiChange < 0
            ? "neutral"
            : "bearish"
      : "neutral";
    const structureText = Number.isFinite(closeChangePct)
      ? closeChangePct >= 0 && oiChange >= 0
        ? "價格上行且 OI 增加，偏向多方增倉推進。"
        : closeChangePct < 0 && oiChange >= 0
          ? "價格下行但 OI 增加，偏向空方增倉壓制。"
          : closeChangePct >= 0 && oiChange < 0
            ? "價格上行但 OI 下降，可能是空方回補，延續性需看量能。"
            : "價格下行且 OI 下降，偏向多方減倉或退場。"
      : "價格與 OI 結構仍需更多資料確認。";
    signals.push({
      name: "價量 OI 結構",
      value: `${Number.isFinite(closeChangePct) ? `${closeChangePct >= 0 ? "+" : ""}${closeChangePct.toFixed(2)}%` : "--"} / ${oiChange >= 0 ? "+" : ""}${formatGlobalVolume(oiChange)}`,
      text: structureText,
      direction: structureDirection,
      scoreDelta: structureDirection === "bullish" ? 1 : structureDirection === "bearish" ? -1 : 0,
    });
  }
  return signals;
}
function calculatePsy(history, period = 12) {
  if (history.length < period + 1) return null;
  const window = history.slice(-(period + 1));
  let advances = 0;
  for (let index = 1; index < window.length; index += 1) {
    if (window[index].close > window[index - 1].close) advances += 1;
  }
  return (advances / period) * 100;
}
function classifyVolumePriceNinePatterns({ latest, previous, volumeRatio, averageTrend = null }) {
  const priceChangePct = previous?.close
    ? ((latest.close - previous.close) / previous.close) * 100
    : 0;
  const priceState = priceChangePct >= 0.3 ? "up" : priceChangePct <= -0.3 ? "down" : "flat";
  const volumeState = volumeRatio >= 1.15 ? "up" : volumeRatio <= 0.85 ? "down" : "flat";
  const trendText = averageTrend === null
    ? ""
    : `；均量趨勢 ${averageTrend >= 0 ? "+" : ""}${averageTrend.toFixed(1)}%`;
  const key = `${priceState}-${volumeState}`;
  const patterns = {
    "up-up": {
      name: "價漲量增",
      text: `量價同步轉強，上漲較有確認${trendText}`,
      direction: "bullish",
      score: 1,
    },
    "up-flat": {
      name: "價漲量平",
      text: `股價上漲但量能未明顯擴張，屬溫和上攻${trendText}`,
      direction: "bullish",
      score: 1,
    },
    "up-down": {
      name: "價漲量縮",
      text: `上攻量能不足，追價需防動能遞減${trendText}`,
      direction: "bearish",
      score: -1,
    },
    "flat-up": {
      name: "價平量增",
      text: `量能放大但價格未表態，可能有換手或主力吸籌/出貨${trendText}`,
      direction: "neutral",
      score: 0,
    },
    "flat-flat": {
      name: "價平量平",
      text: `量價皆平，市場觀望，等待突破或跌破確認${trendText}`,
      direction: "neutral",
      score: 0,
    },
    "flat-down": {
      name: "價平量縮",
      text: `量縮整理，籌碼沉澱但方向尚未明朗${trendText}`,
      direction: "neutral",
      score: 0,
    },
    "down-up": {
      name: "價跌量增",
      text: `下跌伴隨放量，賣壓較明顯${trendText}`,
      direction: "bearish",
      score: -1,
    },
    "down-flat": {
      name: "價跌量平",
      text: `股價走弱但量能未放大，偏弱整理仍需觀察支撐${trendText}`,
      direction: "bearish",
      score: -1,
    },
    "down-down": {
      name: "價跌量縮",
      text: `下跌量縮，賣壓未擴大但仍需止跌訊號${trendText}`,
      direction: "neutral",
      score: 0,
    },
  };
  return {
    ...(patterns[key] || patterns["flat-flat"]),
    priceChangePct,
    priceState,
    volumeState,
  };
}
function calculateBacktestAtrPct(history, period = 14) {
  if (!Array.isArray(history) || history.length <= period) return null;
  const trueRanges = [];
  for (let index = 1; index < history.length; index += 1) {
    const current = history[index];
    const previous = history[index - 1];
    if (![current.high, current.low, previous.close].every(Number.isFinite)) continue;
    trueRanges.push(Math.max(
      current.high - current.low,
      Math.abs(current.high - previous.close),
      Math.abs(current.low - previous.close),
    ));
  }
  if (trueRanges.length < period) return null;
  const atr = trueRanges.slice(-period).reduce((sum, value) => sum + value, 0) / period;
  const latestClose = history.at(-1)?.close;
  return Number.isFinite(latestClose) && latestClose ? (atr / latestClose) * 100 : null;
}
function calculateMaxDrawdownPct(returns) {
  if (!Array.isArray(returns) || !returns.length) return 0;
  let equity = 1;
  let peak = 1;
  let maxDrawdown = 0;
  returns.forEach((value) => {
    equity *= 1 + (value / 100);
    peak = Math.max(peak, equity);
    if (peak > 0) {
      maxDrawdown = Math.min(maxDrawdown, ((equity - peak) / peak) * 100);
    }
  });
  return maxDrawdown;
}
function calculateSharpeLikeScore(returns) {
  if (!Array.isArray(returns) || returns.length < 2) return null;
  const average = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const variance = returns.reduce((sum, value) => sum + ((value - average) ** 2), 0) / (returns.length - 1);
  const sigma = Math.sqrt(variance);
  return sigma ? average / sigma : null;
}
function calculateBacktestWinRate(returns) {
  if (!Array.isArray(returns) || !returns.length) return null;
  return returns.filter((value) => value > 0).length / returns.length;
}
function calculateBacktestAverageReturn(returns) {
  if (!Array.isArray(returns) || !returns.length) return null;
  return returns.reduce((sum, value) => sum + value, 0) / returns.length;
}
function calculateBacktestProfitFactor(returns) {
  if (!Array.isArray(returns) || !returns.length) return null;
  const profit = returns.filter((value) => value > 0).reduce((sum, value) => sum + value, 0);
  const loss = Math.abs(returns.filter((value) => value < 0).reduce((sum, value) => sum + value, 0));
  if (!loss) return profit ? Infinity : 0;
  return profit / loss;
}
function calculateMaxLosingStreak(returns) {
  if (!Array.isArray(returns) || !returns.length) return 0;
  let current = 0;
  let maxStreak = 0;
  returns.forEach((value) => {
    if (value < 0) {
      current += 1;
      maxStreak = Math.max(maxStreak, current);
    } else {
      current = 0;
    }
  });
  return maxStreak;
}
function summarizeBacktestSegment(returns) {
  return {
    samples: returns.length,
    winRate: calculateBacktestWinRate(returns),
    averageReturn: calculateBacktestAverageReturn(returns),
    profitFactor: calculateBacktestProfitFactor(returns),
    maxDrawdown: calculateMaxDrawdownPct(returns),
    maxLosingStreak: calculateMaxLosingStreak(returns),
    sharpe: calculateSharpeLikeScore(returns),
  };
}
function buildBacktestModelValidation(leader) {
  const returns = Array.isArray(leader?.returns) ? leader.returns.filter(Number.isFinite) : [];
  if (returns.length < 20) {
    return {
      status: "insufficient",
      label: "樣本不足",
      driftCount: 0,
      recommendation: "樣本不足，暫不判定模型失真，也不強制調整權重。",
      reasons: ["樣本數不足 20 筆，無法進行穩定的樣本內/樣本外驗證"],
      source: BACKTEST_DRIFT_SOURCE,
      inSample: summarizeBacktestSegment([]),
      outSample: summarizeBacktestSegment([]),
    };
  }

  const splitIndex = Math.max(10, Math.floor(returns.length * 0.7));
  const inReturns = returns.slice(0, splitIndex);
  const outReturns = returns.slice(splitIndex);
  const inSample = summarizeBacktestSegment(inReturns);
  const outSample = summarizeBacktestSegment(outReturns);
  const reasons = [];
  const inWin = inSample.winRate ?? 0;
  const outWin = outSample.winRate ?? 0;
  const inPf = Number.isFinite(inSample.profitFactor) ? inSample.profitFactor : 9;
  const outPf = Number.isFinite(outSample.profitFactor) ? outSample.profitFactor : 9;

  if (inWin >= 0.55 && outWin < 0.45) reasons.push("勝率由樣本內優勢降至樣本外 45% 以下");
  if (outSample.maxDrawdown <= -25 || outSample.maxDrawdown <= inSample.maxDrawdown - 10) reasons.push("樣本外最大回撤超過歷史容忍範圍");
  if (inPf >= 1.2 && outPf < 1) reasons.push("樣本外盈虧比惡化為小於 1");
  if (outSample.maxLosingStreak > Math.max(inSample.maxLosingStreak + 1, 3)) reasons.push("樣本外連續虧損次數異常增加");
  if (
    Number.isFinite(inSample.averageReturn)
    && Number.isFinite(outSample.averageReturn)
    && inSample.averageReturn > 0
    && outSample.averageReturn < 0
    && Math.abs(inSample.averageReturn - outSample.averageReturn) >= 6
  ) {
    reasons.push("樣本內與樣本外平均報酬差距過大，疑似過度擬合");
  }

  const driftCount = reasons.length;
  const status = driftCount >= 3 || (outWin < 0.35 && outPf < 0.8)
    ? "rebuild"
    : driftCount >= 2
      ? "recalibrate"
      : driftCount === 1
        ? "watch"
        : "healthy";
  const label = {
    healthy: "通過校準",
    watch: "輕微失真",
    recalibrate: "需調整參數",
    rebuild: "需重新建模",
  }[status] || "樣本不足";
  const recommendation = {
    healthy: "樣本外表現仍可接受，可保留目前權重校準。",
    watch: "出現一次失真，先觀察並降低模型信心。",
    recalibrate: "連續或多項失真，建議調整參數並檢查市場環境。",
    rebuild: "模型績效結構已失效，停用權重調整並重新建立模型。",
  }[status] || "樣本不足，暫不判定模型失真。";

  return {
    status,
    label,
    driftCount,
    recommendation,
    reasons: reasons.length ? reasons : ["未觸發明顯模型失真條件"],
    source: BACKTEST_DRIFT_SOURCE,
    inSample,
    outSample,
  };
}
function buildBacktestModelRebuildResult(failedModel, candidates) {
  const candidateRows = (Array.isArray(candidates) ? candidates : [])
    .filter((item) => item && item.name !== failedModel?.name && Array.isArray(item.returns) && item.returns.length >= 20)
    .map((item) => {
      const validation = buildBacktestModelValidation(item);
      const outWin = validation.outSample?.winRate ?? 0;
      const outPf = Number.isFinite(validation.outSample?.profitFactor) ? validation.outSample.profitFactor : 9;
      const outMdd = Number.isFinite(validation.outSample?.maxDrawdown) ? validation.outSample.maxDrawdown : 0;
      const score = (outWin * 100)
        + Math.min(outPf, 3) * 12
        + Math.max(outMdd, -30) * 0.7
        + Math.max(-8, Math.min(8, item.averageReturn || 0));
      return { model: item, validation, score };
    })
    .sort((left, right) => right.score - left.score);

  const replacement = candidateRows.find((item) => (
    ["healthy", "watch"].includes(item.validation.status)
    && (item.validation.outSample?.winRate ?? 0) >= 0.5
    && (!Number.isFinite(item.validation.outSample?.profitFactor) || item.validation.outSample.profitFactor >= 1)
  ));

  if (!replacement) {
    return {
      status: "failed",
      label: "重建失敗",
      oldModel: failedModel?.name || "--",
      newModel: null,
      summary: "已掃描替代模型，但尚未找到樣本外勝率、Profit Factor 與回撤都可接受的新模型，維持中性權重。",
      candidates: candidateRows.slice(0, 3).map((item) => ({
        name: item.model.name,
        status: item.validation.label,
        outWinRate: item.validation.outSample?.winRate ?? null,
        outProfitFactor: item.validation.outSample?.profitFactor ?? null,
        outMaxDrawdown: item.validation.outSample?.maxDrawdown ?? null,
      })),
    };
  }

  return {
    status: "rebuilt",
    label: "已重新建置",
    oldModel: failedModel?.name || "--",
    newModel: replacement.model.name,
    model: replacement.model,
    validation: replacement.validation,
    summary: `舊模型 ${failedModel?.name || "--"} 失真後，已改用 ${replacement.model.name}；新模型樣本外勝率 ${((replacement.validation.outSample?.winRate || 0) * 100).toFixed(0)}%，PF ${Number.isFinite(replacement.validation.outSample?.profitFactor) ? replacement.validation.outSample.profitFactor.toFixed(2) : "--"}。`,
    candidates: candidateRows.slice(0, 3).map((item) => ({
      name: item.model.name,
      status: item.validation.label,
      outWinRate: item.validation.outSample?.winRate ?? null,
      outProfitFactor: item.validation.outSample?.profitFactor ?? null,
      outMaxDrawdown: item.validation.outSample?.maxDrawdown ?? null,
    })),
  };
}
function buildBacktestTrendForecast(history, signals = [], validation = null) {
  const latest = Array.isArray(history) ? history.at(-1) : null;
  if (!latest || !Number.isFinite(latest.close)) {
    return {
      confidence: "低",
      summary: "歷史價格資料不足，暫不產生未來走勢情境推估。",
      scenarios: [],
      support: null,
      resistance: null,
      priceTargets: [],
      caveat: "回溯測試只能估計歷史訊號後的機率傾向，不保證未來價格。",
    };
  }

  const closes = history.map((item) => item.close);
  const ma20 = technicalSma(closes, 20).at(-1);
  const ma60 = technicalSma(closes, 60).at(-1);
  const ma120 = technicalSma(closes, 120).at(-1);
  const recentWindow = history.slice(-60);
  const recentLows = recentWindow.map((item) => item.low).filter(Number.isFinite);
  const recentHighs = recentWindow.map((item) => item.high).filter(Number.isFinite);
  const support = recentLows.length ? Math.min(...recentLows) : null;
  const resistance = recentHighs.length ? Math.max(...recentHighs) : null;
  const atrPct = calculateBacktestAtrPct(history, 14) || 0;
  const validSignals = (Array.isArray(signals) ? signals : []).filter((item) => item.samples >= 10);
  const bullishPower = validSignals
    .filter((item) => item.direction === "bullish")
    .reduce((sum, item) => sum + ((item.winRate - 0.5) * 100) + Math.max(-8, Math.min(8, item.averageReturn || 0)), 0);
  const bearishPower = validSignals
    .filter((item) => item.direction === "bearish")
    .reduce((sum, item) => sum + ((item.winRate - 0.5) * 100) + Math.max(-8, Math.min(8, item.averageReturn || 0)), 0);
  let trendScore = bullishPower - bearishPower;
  if ([ma20, ma60].every(Number.isFinite)) {
    if (latest.close > ma20 && ma20 > ma60) trendScore += 10;
    if (latest.close < ma20 && ma20 < ma60) trendScore -= 10;
  }
  if ([ma60, ma120].every(Number.isFinite)) {
    if (latest.close > ma60 && ma60 > ma120) trendScore += 6;
    if (latest.close < ma60 && ma60 < ma120) trendScore -= 6;
  }
  if (validation?.status === "rebuild") trendScore = 0;
  if (validation?.status === "recalibrate") trendScore *= 0.45;
  if (validation?.status === "watch") trendScore *= 0.7;

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const baseBullish = clamp(42 + trendScore * 0.55 - atrPct * 0.45, 12, 78);
  const baseBearish = clamp(30 - trendScore * 0.42 + atrPct * 0.45, 10, 70);
  const normalizeScenario = (bullish, bearish) => {
    const neutral = clamp(100 - bullish - bearish, 12, 55);
    const total = bullish + bearish + neutral || 1;
    return {
      bullish: Math.round((bullish / total) * 100),
      neutral: Math.round((neutral / total) * 100),
      bearish: Math.max(0, 100 - Math.round((bullish / total) * 100) - Math.round((neutral / total) * 100)),
    };
  };
  const horizons = [
    { days: 5, label: "5 日", factor: 0.42 },
    { days: 10, label: "10 日", factor: 0.56 },
    { days: 20, label: "20 日", factor: 0.72 },
    { days: 60, label: "60 日", factor: 0.9 },
    { days: 120, label: "120 日", factor: 1.05 },
    { days: 240, label: "240 日", factor: 1.18 },
  ];
  const scenarios = horizons.map((item) => ({
    ...item,
    ...normalizeScenario(
      clamp(baseBullish + (trendScore > 0 ? item.factor * 3 : -item.factor * 1.2), 10, 82),
      clamp(baseBearish + (trendScore < 0 ? item.factor * 3 : -item.factor * 1.2), 8, 78),
    ),
  }));
  const atrPrice = latest.close * (atrPct / 100);
  const confidenceMultiplier = validation?.status === "healthy"
    ? 1
    : validation?.status === "watch"
      ? 0.82
      : validation?.status === "recalibrate"
        ? 0.62
        : validation?.status === "rebuild"
          ? 0.35
          : 0.55;
  const priceTargets = horizons.map((item) => {
    const scenario = scenarios.find((entry) => entry.days === item.days) || {};
    const directionalBias = ((scenario.bullish || 0) - (scenario.bearish || 0)) / 100;
    const signalReturn = validSignals.length
      ? validSignals.reduce((sum, signal) => {
          const direction = signal.direction === "bullish" ? 1 : signal.direction === "bearish" ? -1 : 0;
          return sum + (direction * (Number(signal.averageReturn) || 0));
        }, 0) / validSignals.length
      : 0;
    const trendReturn = clamp((directionalBias * atrPct * Math.sqrt(item.days / 20) * 1.8) + (signalReturn * (item.days / 240)), -35, 35) * confidenceMultiplier;
    const median = latest.close * (1 + trendReturn / 100);
    const volatilityBand = Math.max(atrPrice * Math.sqrt(item.days / 20), latest.close * 0.015) * (validation?.status === "rebuild" ? 1.35 : 1);
    const lowerAnchor = Number.isFinite(support) ? support : latest.close - volatilityBand;
    const upperAnchor = Number.isFinite(resistance) ? resistance : latest.close + volatilityBand;
    const lower = Math.max(0, Math.min(median - volatilityBand, lowerAnchor * 0.98));
    const upper = Math.max(median + volatilityBand, upperAnchor * 1.02);
    return {
      days: item.days,
      label: item.label,
      median,
      lower,
      upper,
      expectedReturnPct: ((median - latest.close) / latest.close) * 100,
      basis: validation?.status === "rebuild"
        ? "模型失真，僅保留寬區間風險參考"
        : "依情境機率、ATR、支撐壓力與回測平均報酬估算",
    };
  });
  const leader = validSignals[0];
  const confidence = validation?.status === "healthy" && validSignals.length >= 3
    ? "中高"
    : validation?.status === "rebuild" || !validSignals.length
      ? "低"
      : "中";
  const summary = leader
    ? `依 ${leader.name} 與多因子回測，未來走勢偏向${trendScore > 8 ? "多方延續" : trendScore < -8 ? "偏空修正" : "區間震盪"}；模型信心 ${confidence}。`
    : `目前可用回測訊號不足，未來走勢以區間震盪情境為主；模型信心 ${confidence}。`;
  return {
    confidence,
    summary,
    scenarios,
    support,
    resistance,
    atrPct,
    trendScore,
    priceTargets,
    trendLabel: trendScore > 8 ? "偏多延續" : trendScore < -8 ? "偏空修正" : "區間震盪",
    caveat: "這是基於歷史訊號與目前價量結構的機率情境與價格區間推估，不是保證價格或投資建議。",
  };
}
function buildBacktestLearningModel(history, horizon = 240) {
  const costModel = {
    feePct: 0.1425,
    sellTaxPct: 0.3,
    slippagePct: 0.1,
    roundTripPct: 0.1425 * 2 + 0.3 + 0.1 * 2,
  };
  const riskModel = {
    stopLossPct: -8,
    takeProfitPct: 20,
    maxSinglePositionPct: 20,
  };
  if (!Array.isArray(history) || history.length < horizon + 90) {
    return {
      scoreAdjustment: 0,
      evidenceCount: 0,
      horizon,
      successThreshold: 5,
      testedBars: 0,
      summary: `歷史資料不足 ${horizon} 日後報酬回測，暫不啟用回溯校準`,
      signals: [],
      factors: BACKTEST_FACTOR_BASELINE,
      benchmarkSource: BACKTEST_BENCHMARK_SOURCE,
      driftSource: BACKTEST_DRIFT_SOURCE,
      costModel,
      riskModel,
      qualityChecks: ["OHLCV 歷史資料不足，暫不啟用完整基準"],
      performance: null,
      validation: buildBacktestModelValidation(null),
      forecast: buildBacktestTrendForecast(history, [], null),
    };
  }

  const stats = new Map();
  const allNetReturns = [];
  const addResult = (name, direction, futureReturnPct, context = {}) => {
    if (!direction || direction === "neutral" || !Number.isFinite(futureReturnPct)) return;
    const directionalReturn = direction === "bullish" ? futureReturnPct : -futureReturnPct;
    const netReturnPct = directionalReturn - costModel.roundTripPct;
    if (!stats.has(name)) {
      stats.set(name, {
        name,
        direction,
        samples: 0,
        wins: 0,
        totalReturn: 0,
        grossTotalReturn: 0,
        totalProfit: 0,
        totalLoss: 0,
        returns: [],
        riskHits: 0,
      });
    }
    const item = stats.get(name);
    item.samples += 1;
    item.totalReturn += netReturnPct;
    item.grossTotalReturn += directionalReturn;
    item.returns.push(netReturnPct);
    allNetReturns.push(netReturnPct);
    if (netReturnPct > 0) item.totalProfit += netReturnPct;
    if (netReturnPct < 0) item.totalLoss += Math.abs(netReturnPct);
    if (context.riskTriggered) item.riskHits += 1;
    if (netReturnPct > 5) {
      item.wins += 1;
    }
  };

  for (let index = 60; index < history.length - horizon; index += 1) {
    const window = history.slice(0, index + 1);
    const latest = window.at(-1);
    const previous = window.at(-2);
    const future = history[index + horizon];
    if (!latest || !previous || !future || !latest.close) continue;
    const futureReturnPct = ((future.close - latest.close) / latest.close) * 100;
    const futureWindow = history.slice(index + 1, index + horizon + 1);
    const maxFutureGainPct = futureWindow.length
      ? ((Math.max(...futureWindow.map((item) => item.high).filter(Number.isFinite)) - latest.close) / latest.close) * 100
      : futureReturnPct;
    const maxFutureLossPct = futureWindow.length
      ? ((Math.min(...futureWindow.map((item) => item.low).filter(Number.isFinite)) - latest.close) / latest.close) * 100
      : futureReturnPct;
    const bullishRiskTriggered = maxFutureLossPct <= riskModel.stopLossPct || maxFutureGainPct >= riskModel.takeProfitPct;
    const bearishRiskTriggered = maxFutureGainPct >= Math.abs(riskModel.stopLossPct) || maxFutureLossPct <= -riskModel.takeProfitPct;
    const closes = window.map((item) => item.close);
    const ma5 = technicalSma(closes, 5).at(-1);
    const ma10 = technicalSma(closes, 10).at(-1);
    const ma20 = technicalSma(closes, 20).at(-1);
    const ma60 = technicalSma(closes, 60).at(-1);

    if ([ma20, ma60].every(Number.isFinite)) {
      if (latest.close > ma20 && ma20 > ma60) addResult("均線多頭排列", "bullish", futureReturnPct);
      if (latest.close < ma20 && ma20 < ma60) addResult("均線空頭排列", "bearish", futureReturnPct);
    }
    if ([ma5, ma10, ma20].every(Number.isFinite)) {
      if (latest.close > ma5 && ma5 > ma10 && ma10 > ma20) addResult("重建候選：短均多頭排列", "bullish", futureReturnPct);
      if (latest.close < ma5 && ma5 < ma10 && ma10 < ma20) addResult("重建候選：短均空頭排列", "bearish", futureReturnPct);
      if (previous.close <= ma10 && latest.close > ma10 && ma10 > ma20) addResult("重建候選：10 日線轉強", "bullish", futureReturnPct);
      if (previous.close >= ma10 && latest.close < ma10 && ma10 < ma20) addResult("重建候選：10 日線轉弱", "bearish", futureReturnPct);
    }

    const rsi = calculateRsi(window).at(-1);
    const kd = window.length >= 9 ? calculateKd(window).at(-1) : null;
    if (Number.isFinite(rsi)) {
      if (rsi >= 55 && rsi < 75) addResult("RSI 多方區", "bullish", futureReturnPct);
      if (rsi >= 50 && rsi < 68) addResult("重建候選：RSI 50 多方守穩", "bullish", futureReturnPct);
      if (rsi < 45) addResult("重建候選：RSI 45 空方跌破", "bearish", futureReturnPct);
    }

    const macd = window.length >= 26 ? calculateMacd(window).at(-1) : null;
    if (macd && Number.isFinite(macd.osc)) {
      if (macd.osc > 0) addResult("MACD 正柱", "bullish", futureReturnPct);
      if (macd.osc < 0) addResult("MACD 負柱", "bearish", futureReturnPct);
    }

    const recentVolumes = window.slice(-6, -1).map((item) => item.volume).filter(Number.isFinite);
    const averageVolume = recentVolumes.length
      ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
      : null;
    const volumeRatio = averageVolume && latest.volume ? latest.volume / averageVolume : null;

    const band = window.length >= 20 ? calculateBollingerBands(window).at(-1) : null;
    if (band && [band.upper, band.lower].every(Number.isFinite)) {
      if (latest.close > band.upper) addResult("布林上軌突破", "bullish", futureReturnPct);
      if (latest.close < band.lower) addResult("布林下軌跌破", "bearish", futureReturnPct);
    }

    const ma120 = technicalSma(closes, 120).at(-1);
    const ma240 = technicalSma(closes, 240).at(-1);
    const momentum60 = closes.length >= 61 && closes.at(-61)
      ? ((latest.close - closes.at(-61)) / closes.at(-61)) * 100
      : null;
    const atrPct = calculateBacktestAtrPct(window, 14);
    const prior20 = window.slice(-21, -1);
    const priorHigh = prior20.length ? Math.max(...prior20.map((item) => item.high)) : null;
    const priorLow = prior20.length ? Math.min(...prior20.map((item) => item.low)) : null;
    const recent60 = window.slice(-60);
    const volatilityPct = recent60.length >= 20
      ? ((Math.max(...recent60.map((item) => item.high)) - Math.min(...recent60.map((item) => item.low))) / latest.close) * 100
      : null;

    if ([ma20, ma60, ma120].every(Number.isFinite)) {
      if (latest.close > ma20 && ma20 > ma60 && ma60 > ma120 && macd?.osc > 0) {
        addResult("趨勢動能共振", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
      }
      if (latest.close < ma20 && ma20 < ma60 && ma60 < ma120 && macd?.osc < 0) {
        addResult("趨勢動能轉弱", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
      }
    }
    if ([ma60, ma120, ma240].every(Number.isFinite)) {
      if (latest.close > ma60 && ma60 > ma120 && ma120 > ma240) {
        addResult("長週期多頭結構", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
      }
      if (latest.close < ma60 && ma60 < ma120 && ma120 < ma240) {
        addResult("長週期空頭結構", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
      }
    }
    if (priorHigh && volumeRatio && latest.close > priorHigh && volumeRatio >= 1.1) {
      addResult("放量突破 20 日高", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
    }
    if (priorLow && volumeRatio && latest.close < priorLow && volumeRatio >= 1.1) {
      addResult("放量跌破 20 日低", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
    }
    if (band && [band.upper, band.middle, ma20, ma60].every(Number.isFinite) && latest.close > band.middle && ma20 > ma60 && volumeRatio && volumeRatio >= 0.9) {
      addResult("布林中軌上方趨勢延續", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
    }
    if ([ma60, rsi, macd?.osc, kd?.k, kd?.d, momentum60].every(Number.isFinite)) {
      if (latest.close > ma60 && rsi >= 50 && macd.osc > 0 && kd.k >= kd.d && momentum60 > 0) {
        addResult("趨勢動能多因子", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
      }
      if (latest.close < ma60 && rsi < 50 && macd.osc < 0 && kd.k < kd.d && momentum60 < 0) {
        addResult("趨勢動能空因子", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
      }
    }
    if ([ma60, atrPct, band?.bandwidth].every(Number.isFinite)) {
      if (latest.close > ma60 && atrPct < 4.5 && band.bandwidth < 18) {
        addResult("低波動趨勢基準", "bullish", futureReturnPct, { riskTriggered: bullishRiskTriggered });
      }
      if (latest.close < ma60 && atrPct >= 4.5 && band.bandwidth >= 18) {
        addResult("高波動風險基準", "bearish", futureReturnPct, { riskTriggered: bearishRiskTriggered });
      }
    }
    if (Number.isFinite(volatilityPct)) {
      if (volatilityPct <= 18 && Number.isFinite(ma60) && latest.close > ma60 && macd?.osc > 0) {
        addResult("低波動趨勢延續", "bullish", futureReturnPct);
      }
      if (volatilityPct >= 35 && Number.isFinite(ma60) && latest.close < ma60 && macd?.osc < 0) {
        addResult("高波動弱勢延伸", "bearish", futureReturnPct);
      }
    }
    if ([ma10, ma20, volumeRatio, rsi].every(Number.isFinite)) {
      if (latest.close > ma10 && ma10 >= ma20 && volumeRatio >= 0.9 && rsi >= 48) {
        addResult("重建候選：短線趨勢量能確認", "bullish", futureReturnPct);
      }
      if (latest.close < ma10 && ma10 <= ma20 && volumeRatio >= 0.9 && rsi < 50) {
        addResult("重建候選：短線弱勢量能確認", "bearish", futureReturnPct);
      }
    }
  }

  const rankedAll = [...stats.values()]
    .filter((item) => item.samples >= 10)
    .map((item) => ({
      ...item,
      winRate: item.wins / item.samples,
      averageReturn: item.totalReturn / item.samples,
      grossAverageReturn: item.grossTotalReturn / item.samples,
      profitFactor: item.totalLoss ? item.totalProfit / item.totalLoss : (item.totalProfit ? Infinity : 0),
      maxDrawdown: calculateMaxDrawdownPct(item.returns),
      sharpe: calculateSharpeLikeScore(item.returns),
      riskHitRate: item.riskHits / item.samples,
    }))
    .sort((a, b) => {
      const scoreA = Math.abs(a.winRate - 0.5) + Math.max(-0.3, Math.min(0.3, (a.profitFactor || 0) / 10));
      const scoreB = Math.abs(b.winRate - 0.5) + Math.max(-0.3, Math.min(0.3, (b.profitFactor || 0) / 10));
      return scoreB - scoreA;
    });
  const ranked = rankedAll.slice(0, 5);

  if (!ranked.length) {
    return {
      scoreAdjustment: 0,
      evidenceCount: 0,
      horizon,
      successThreshold: 5,
      testedBars: Math.max(history.length - horizon - 60, 0),
      summary: `${horizon} 日後報酬回溯樣本不足，暫不調整 AI 權重`,
      signals: [],
      factors: BACKTEST_FACTOR_BASELINE,
      benchmarkSource: BACKTEST_BENCHMARK_SOURCE,
      driftSource: BACKTEST_DRIFT_SOURCE,
      costModel,
      riskModel,
      qualityChecks: ["OHLCV 已檢查", "有效訊號樣本不足", "避免樣本不足時硬調權重"],
      performance: {
        maxDrawdown: calculateMaxDrawdownPct(allNetReturns),
        sharpe: calculateSharpeLikeScore(allNetReturns),
      },
      validation: buildBacktestModelValidation(null),
      forecast: buildBacktestTrendForecast(history, [], null),
    };
  }

  const scoreAdjustment = ranked.reduce((sum, item) => {
    if (item.winRate >= 0.58) return sum + (item.direction === "bullish" ? 1 : -1);
    if (item.winRate <= 0.42) return sum - (item.direction === "bullish" ? 1 : -1);
    return sum;
  }, 0);
  const leader = ranked[0];
  const validation = buildBacktestModelValidation(leader);
  const modelRebuild = ["rebuild", "recalibrate"].includes(validation.status)
    ? buildBacktestModelRebuildResult(leader, rankedAll)
    : { status: "not_required", label: "不需重建", oldModel: leader.name, newModel: null, summary: "目前模型尚未達重建條件。" };
  const activeLeader = modelRebuild.status === "rebuilt" ? modelRebuild.model : leader;
  const activeValidation = modelRebuild.status === "rebuilt" ? modelRebuild.validation : validation;
  const activeRanked = modelRebuild.status === "rebuilt"
    ? [modelRebuild.model, ...ranked.filter((item) => item.name !== leader.name && item.name !== modelRebuild.model.name)].slice(0, 5)
    : ranked;
  const activeScoreAdjustment = activeRanked.reduce((sum, item) => {
    if (item.winRate >= 0.58) return sum + (item.direction === "bullish" ? 1 : -1);
    if (item.winRate <= 0.42) return sum - (item.direction === "bullish" ? 1 : -1);
    return sum;
  }, 0);
  const rawAdjustment = Math.max(-3, Math.min(3, scoreAdjustment));
  const activeRawAdjustment = Math.max(-3, Math.min(3, activeScoreAdjustment));
  const clippedAdjustment = modelRebuild.status === "rebuilt"
    ? activeRawAdjustment
    : activeValidation.status === "rebuild"
    ? 0
    : activeValidation.status === "recalibrate"
      ? Math.max(-1, Math.min(1, rawAdjustment))
      : activeValidation.status === "watch"
        ? Math.trunc(rawAdjustment / 2)
        : rawAdjustment;
  const summary = modelRebuild.status === "rebuilt"
    ? `模型已重新建置：${leader.name} 失真後改用 ${activeLeader.name}，樣本外通過校準`
    : activeValidation.status === "rebuild"
      ? `回測偵測模型失真，${leader.name} 暫停權重調整；替代模型尚未通過校準`
      : `回測 ${horizon} 日後淨報酬，${activeLeader.name} 勝率 ${(activeLeader.winRate * 100).toFixed(0)}%，淨均報酬 ${activeLeader.averageReturn >= 0 ? "+" : ""}${activeLeader.averageReturn.toFixed(2)}%`;

  return {
    scoreAdjustment: clippedAdjustment,
    evidenceCount: ranked.reduce((sum, item) => sum + item.samples, 0),
    horizon,
    successThreshold: 5,
    testedBars: Math.max(history.length - horizon - 60, 0),
    summary,
    signals: activeRanked,
    factors: BACKTEST_FACTOR_BASELINE,
    benchmarkSource: BACKTEST_BENCHMARK_SOURCE,
    driftSource: BACKTEST_DRIFT_SOURCE,
    costModel,
    riskModel,
    qualityChecks: ["OHLCV 已檢查", "以當下可得資料計算", "納入交易成本", "納入停損停利風控觀察"],
    performance: {
      maxDrawdown: calculateMaxDrawdownPct(allNetReturns),
      sharpe: calculateSharpeLikeScore(allNetReturns),
      profitFactor: activeRanked.reduce((sum, item) => sum + (Number.isFinite(item.profitFactor) ? item.profitFactor : 0), 0) / activeRanked.length,
    },
    validation: activeValidation,
    originalValidation: validation,
    modelRebuild,
    forecast: buildBacktestTrendForecast(history, activeRanked, activeValidation),
  };
}
function buildInstitutionalBacktestFramework(detail, history, backtestLearning) {
  const clampScore = (value) => Math.max(0, Math.min(100, value));
  const scoreFromPct = (value, sensitivity = 7) => (
    Number.isFinite(value) ? clampScore(50 + (value * sensitivity)) : null
  );
  const averageAvailable = (items, fallback = 50) => {
    const available = items.filter((item) => Number.isFinite(item.score));
    if (!available.length) return { score: fallback, coverage: 0, available: [] };
    const totalWeight = available.reduce((sum, item) => sum + (item.weight || 1), 0);
    return {
      score: available.reduce((sum, item) => sum + (item.score * (item.weight || 1)), 0) / totalWeight,
      coverage: available.length / items.length,
      available,
    };
  };
  const international = Array.isArray(data?.marketInternationalIndexes)
    ? data.marketInternationalIndexes
    : [];
  const macroFactors = data?.marketMacroFactors || {};
  const findIndex = (...needles) => international.find((item) => {
    const haystack = `${item.key || ""} ${item.symbol || ""} ${item.name || ""}`.toLowerCase();
    return needles.some((needle) => haystack.includes(needle));
  });
  const readPct = (item) => parseAnalysisNumber(
    item?.pct ?? item?.changePercent ?? item?.changePct ?? item?.change_rate,
  );
  const soxPct = readPct(findIndex("sox", "semiconductor", "費城半導體"));
  const nasdaqPct = readPct(findIndex("nasdaq", "ixic"));
  const sp500Pct = readPct(findIndex("sp500", "s&p 500", "gspc"));
  const russellPct = readPct(findIndex("russell", "rut"));
  const vixItem = findIndex("vix", "volatility");
  const vixPct = readPct(vixItem) ?? parseAnalysisNumber(data?.marketVolatility?.pct);
  const vixValue = parseAnalysisNumber(vixItem?.value ?? vixItem?.close ?? data?.marketVolatility?.value);
  const dxyPct = parseAnalysisNumber(macroFactors.dxy?.pct);
  const us10yPct = parseAnalysisNumber(macroFactors.us10y?.pct);
  const usdTwdPct = parseAnalysisNumber(macroFactors.usdTwd?.pct);
  const vixLevelScore = Number.isFinite(vixValue)
    ? vixValue < 15 ? 72 : vixValue < 20 ? 62 : vixValue < 30 ? 42 : vixValue < 40 ? 24 : 8
    : null;
  const marketFactors = [
    { name: "SOX 半導體", score: scoreFromPct(soxPct, 9), weight: 3, value: soxPct },
    { name: "NASDAQ", score: scoreFromPct(nasdaqPct, 8), weight: 3, value: nasdaqPct },
    {
      name: "VIX 風險",
      score: Number.isFinite(vixLevelScore)
        ? clampScore((vixLevelScore * 0.7) + ((scoreFromPct(Number.isFinite(vixPct) ? -vixPct : null, 5) ?? 50) * 0.3))
        : scoreFromPct(Number.isFinite(vixPct) ? -vixPct : null, 5),
      weight: 3,
      value: vixValue,
    },
    { name: "S&P 500", score: scoreFromPct(sp500Pct, 7), weight: 1, value: sp500Pct },
    { name: "Russell 2000", score: scoreFromPct(russellPct, 7), weight: 1, value: russellPct },
    { name: "美元指數", score: scoreFromPct(Number.isFinite(dxyPct) ? -dxyPct : null, 6), weight: 1, value: dxyPct },
    { name: "美債 10 年殖利率", score: scoreFromPct(Number.isFinite(us10yPct) ? -us10yPct : null, 5), weight: 1, value: us10yPct },
    { name: "美元兌臺幣", score: scoreFromPct(Number.isFinite(usdTwdPct) ? -usdTwdPct : null, 6), weight: 1, value: usdTwdPct },
  ];
  const marketLayer = averageAvailable(marketFactors);

  const institutional = parseAnalysisNumber(detail.institutionalTrades?.totalValue);
  const foreign = parseAnalysisNumber(
    detail.institutionalTrades?.foreignValue
      ?? detail.institutionalTrades?.foreign
      ?? detail.institutionalTrades?.foreignInvestors,
  );
  const largeHolder = parseAnalysisNumber(detail.shareholderDistribution?.largeHolderRatio);
  const latest = history.at(-1);
  const recentVolumes = history.slice(-21, -1).map((item) => item.volume).filter(Number.isFinite);
  const average20Volume = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const volumeRatio = Number.isFinite(latest?.volume) && average20Volume
    ? latest.volume / average20Volume
    : null;
  const futuresOiChangePct = parseAnalysisNumber(macroFactors.txOpenInterest?.changePct);
  const weightedPct = parseAnalysisNumber(
    (data?.marketOverview || []).find((item) => /加權|TAIEX/i.test(item?.name || ""))?.pct,
  );
  const futuresOiScore = Number.isFinite(futuresOiChangePct)
    ? futuresOiChangePct > 0
      ? Number.isFinite(weightedPct) && weightedPct < 0 ? 32 : 68
      : Number.isFinite(weightedPct) && weightedPct < 0 ? 58 : 45
    : null;
  const financingChangePct = parseAnalysisNumber(macroFactors.marginTrading?.financingChangePct);
  const shortChangePct = parseAnalysisNumber(macroFactors.marginTrading?.shortChangePct);
  const marginScore = Number.isFinite(financingChangePct)
    ? financingChangePct > 3
      ? 32
      : financingChangePct >= 0
        ? 58
        : financingChangePct <= -3
          ? 52
          : 48
    : null;
  const shortScore = Number.isFinite(shortChangePct)
    ? shortChangePct > 3 ? 38 : shortChangePct < -3 ? 60 : 50
    : null;
  const capitalFactors = [
    {
      name: "外資買賣超",
      score: Number.isFinite(foreign) ? (foreign > 0 ? 70 : foreign < 0 ? 30 : 50) : null,
      weight: 2,
      value: foreign,
    },
    {
      name: "三大法人",
      score: Number.isFinite(institutional) ? (institutional > 0 ? 68 : institutional < 0 ? 32 : 50) : null,
      weight: 2,
      value: institutional,
    },
    {
      name: "大戶持股",
      score: Number.isFinite(largeHolder) ? clampScore(30 + (largeHolder * 0.7)) : null,
      weight: 1.5,
      value: largeHolder,
    },
    {
      name: "量能流入",
      score: Number.isFinite(volumeRatio) ? clampScore(50 + ((volumeRatio - 1) * 35)) : null,
      weight: 1,
      value: volumeRatio,
    },
    {
      name: "臺指期未平倉",
      score: futuresOiScore,
      weight: 1.5,
      value: futuresOiChangePct,
    },
    {
      name: "融資餘額",
      score: marginScore,
      weight: 1,
      value: financingChangePct,
    },
    {
      name: "融券餘額",
      score: shortScore,
      weight: 0.5,
      value: shortChangePct,
    },
  ];
  const capitalLayer = averageAvailable(capitalFactors);

  const closes = history.map((item) => item.close);
  const ma20 = technicalSma(closes, 20).at(-1);
  const ma60 = technicalSma(closes, 60).at(-1);
  const ma120 = technicalSma(closes, 120).at(-1);
  const ma240 = technicalSma(closes, 240).at(-1);
  const returnFor = (period) => (
    history.length > period && Number.isFinite(history.at(-(period + 1))?.close)
      ? ((latest.close - history.at(-(period + 1)).close) / history.at(-(period + 1)).close) * 100
      : null
  );
  const dayTrend = returnFor(20);
  const weekTrend = returnFor(60);
  const monthTrend = returnFor(240) ?? returnFor(120);
  const maAlignmentScore = [latest?.close, ma20, ma60].every(Number.isFinite)
    ? latest.close > ma20 && ma20 > ma60
      ? 75
      : latest.close < ma20 && ma20 < ma60
        ? 25
        : 50
    : null;
  const longAlignmentScore = [latest?.close, ma60, ma120, ma240].every(Number.isFinite)
    ? latest.close > ma60 && ma60 > ma120 && ma120 > ma240
      ? 82
      : latest.close < ma60 && ma60 < ma120 && ma120 < ma240
        ? 18
        : 50
    : null;
  const recent60 = history.slice(-60);
  const support = recent60.length ? Math.min(...recent60.map((item) => item.low).filter(Number.isFinite)) : null;
  const resistance = recent60.length ? Math.max(...recent60.map((item) => item.high).filter(Number.isFinite)) : null;
  const rangePosition = [support, resistance, latest?.close].every(Number.isFinite) && resistance > support
    ? ((latest.close - support) / (resistance - support)) * 100
    : null;
  const trendFactors = [
    { name: "月線結構", score: scoreFromPct(monthTrend, 2.2), weight: 3, value: monthTrend },
    { name: "週線趨勢", score: scoreFromPct(weekTrend, 3.5), weight: 2, value: weekTrend },
    { name: "日線動能", score: scoreFromPct(dayTrend, 5), weight: 1, value: dayTrend },
    { name: "均線排列", score: maAlignmentScore, weight: 2, value: ma20 },
    { name: "長週期結構", score: longAlignmentScore, weight: 2, value: ma240 },
    {
      name: "支撐壓力",
      score: Number.isFinite(rangePosition) ? clampScore(35 + (rangePosition * 0.3)) : null,
      weight: 1,
      value: rangePosition,
    },
  ];
  const trendLayer = averageAvailable(trendFactors);

  const macd = calculateMacd(history).at(-1);
  const rsi = calculateRsi(history).at(-1);
  const dmi = calculateDmi(history).at(-1);
  const kd = calculateKd(history).at(-1);
  const candleScore = latest && history.at(-2)
    ? latest.close > latest.open && latest.close >= history.at(-2).close ? 70
      : latest.close < latest.open && latest.close <= history.at(-2).close ? 30
        : 50
    : null;
  const timingFactors = [
    {
      name: "MACD",
      score: Number.isFinite(macd?.osc) ? clampScore(50 + (Math.sign(macd.osc) * Math.min(30, Math.abs(macd.osc) * 5))) : null,
      weight: 40,
      value: macd?.osc,
    },
    {
      name: "RSI",
      score: Number.isFinite(rsi) ? clampScore(rsi >= 50 ? 50 + Math.min(25, (rsi - 50) * 1.3) : 50 - Math.min(25, (50 - rsi) * 1.3)) : null,
      weight: 25,
      value: rsi,
    },
    {
      name: "DMI",
      score: [dmi?.plusDi, dmi?.minusDi].every(Number.isFinite)
        ? clampScore(50 + ((dmi.plusDi - dmi.minusDi) * 1.3))
        : null,
      weight: 20,
      value: dmi?.adx,
    },
    { name: "K 線", score: candleScore, weight: 10, value: latest?.close },
    {
      name: "KD",
      score: [kd?.k, kd?.d].every(Number.isFinite) ? clampScore(50 + ((kd.k - kd.d) * 1.8)) : null,
      weight: 5,
      value: kd?.k,
    },
  ];
  const timingLayerRaw = averageAvailable(timingFactors);
  const priceDirection = timingLayerRaw.score >= 55 ? 1 : timingLayerRaw.score <= 45 ? -1 : 0;
  const volumeDirection = Number.isFinite(volumeRatio) ? (volumeRatio >= 1.1 ? 1 : volumeRatio <= 0.8 ? -1 : 0) : 0;
  const volumePenalty = priceDirection && volumeDirection && priceDirection !== volumeDirection ? 8 : 0;
  const timingLayer = {
    ...timingLayerRaw,
    score: clampScore(timingLayerRaw.score - volumePenalty),
    volumePenalty,
  };

  const layers = [
    { key: "market", label: "市場環境", weight: 45, ...marketLayer },
    { key: "capital", label: "資金面", weight: 25, ...capitalLayer },
    { key: "trend", label: "趨勢面", weight: 20, ...trendLayer },
    { key: "timing", label: "進出場", weight: 10, ...timingLayer },
  ];
  const totalScore = Math.round(layers.reduce((sum, layer) => sum + (layer.score * layer.weight / 100), 0));
  const judgement = totalScore >= 80
    ? { label: "積極偏多", tone: "bullish", action: "市場、資金與趨勢共振，仍以分批進場及停損紀律執行。" }
    : totalScore >= 60
      ? { label: "偏多", tone: "bullish", action: "可偏多觀察，等待量價與進場訊號同步後分批布局。" }
      : totalScore >= 40
        ? { label: "觀望", tone: "neutral", action: "多空因子未形成明確共振，控制部位並等待方向確認。" }
        : totalScore >= 20
          ? { label: "偏空", tone: "bearish", action: "降低部位，優先確認支撐、法人方向與波動風險。" }
          : { label: "積極防守", tone: "bearish", action: "風險因子集中，避免逆勢加碼並提高現金水位。" };

  const leader = backtestLearning?.signals?.[0];
  const recent20Returns = Array.isArray(leader?.returns) ? leader.returns.slice(-20) : [];
  const recent20 = summarizeBacktestSegment(recent20Returns);
  const recentWinPct = Number.isFinite(recent20.winRate) ? recent20.winRate * 100 : null;
  const recentWinState = Number.isFinite(recentWinPct)
    ? recentWinPct > 60 ? "模型正常" : recentWinPct >= 50 ? "持續觀察" : recentWinPct >= 40 ? "降低部位" : "模型失真警報"
    : "樣本不足";
  const pfState = Number.isFinite(recent20.profitFactor)
    ? recent20.profitFactor > 1.5 ? "正常" : recent20.profitFactor >= 1 ? "觀察" : "模型失真"
    : "樣本不足";
  const mddState = Number.isFinite(recent20.maxDrawdown) && recent20.maxDrawdown <= -15
    ? "啟動風控警報"
    : "風險可控";
  const aiIndustryMatch = /半導體|電子|AI|資訊|電腦/i.test(`${detail.industry || ""} ${detail.category || ""} ${detail.name || ""}`);
  const driftChecks = [
    { label: "SOX 週期", status: Number.isFinite(soxPct) ? (soxPct >= 0 ? "穩定" : "轉弱") : "待資料" },
    { label: "NASDAQ 轉折", status: Number.isFinite(nasdaqPct) ? (nasdaqPct >= 0 ? "偏多" : "偏空") : "待資料" },
    { label: "VIX 異常", status: Number.isFinite(vixValue) ? (vixValue >= 30 ? "警戒" : "正常") : "待資料" },
    { label: "外資反向", status: Number.isFinite(foreign) ? (foreign < 0 ? "流出" : "流入") : "待資料" },
    { label: "AI 產業氣候", status: aiIndustryMatch ? (Number.isFinite(soxPct) && soxPct < 0 ? "轉弱" : "追蹤中") : "非核心產業" },
  ];
  const marketState = marketLayer.score >= 60 && (!Number.isFinite(vixValue) || vixValue < 20)
    ? "Risk-On"
    : marketLayer.score < 40 || (Number.isFinite(vixValue) && vixValue >= 30)
      ? "Risk-Off"
      : "Neutral";

  return {
    layers,
    totalScore,
    judgement,
    marketState,
    coverage: Math.round((layers.reduce((sum, layer) => sum + layer.coverage, 0) / layers.length) * 100),
    recent20: {
      ...recent20,
      winState: recentWinState,
      pfState,
      mddState,
    },
    driftChecks,
    outputSteps: [
      `市場環境：${marketState}，評分 ${Math.round(marketLayer.score)}`,
      `資金面：${capitalLayer.score >= 60 ? "偏流入" : capitalLayer.score < 40 ? "偏流出" : "中性"}，評分 ${Math.round(capitalLayer.score)}`,
      `趨勢面：${trendLayer.score >= 60 ? "多方" : trendLayer.score < 40 ? "空方" : "整理"}，評分 ${Math.round(trendLayer.score)}`,
      `進出場：${timingLayer.score >= 60 ? "偏多訊號" : timingLayer.score < 40 ? "偏空訊號" : "等待確認"}，評分 ${Math.round(timingLayer.score)}`,
      `AI 產業週期：${aiIndustryMatch ? "已納入 SOX 與 NASDAQ 氣候" : "非 AI 核心產業，維持一般市場權重"}`,
      `模型失真檢查：${backtestLearning?.validation?.label || "樣本不足"}；近 20 筆 ${recentWinState}`,
      `綜合評分：${totalScore} / 100，${judgement.label}`,
      `操作建議：${judgement.action}`,
    ],
  };
}
function buildFuturesBacktestFramework(detail, history, backtestLearning) {
  const clampScore = (value) => Math.max(0, Math.min(100, Number(value) || 0));
  const snapshot = buildFuturesTechnicalSnapshot(history);
  const latest = history.at(-1) || {};
  const previous = history.at(-2) || {};
  const priorClose = history.length > 20 ? history.at(-21)?.close : history[0]?.close;
  const periodChangePct = Number.isFinite(latest.close) && Number.isFinite(priorClose) && priorClose !== 0
    ? ((latest.close - priorClose) / priorClose) * 100
    : null;
  const latestChange = Number.isFinite(latest.close) && Number.isFinite(previous.close)
    ? latest.close - previous.close
    : null;
  const recentVolumes = history.slice(-21, -1).map((row) => row.volume).filter((value) => Number.isFinite(value) && value > 0);
  const averageVolume = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const volumeRatio = Number.isFinite(latest.volume) && averageVolume ? latest.volume / averageVolume : null;
  const makeLayer = (key, label, weight, factors) => {
    const available = factors.filter((factor) => Number.isFinite(factor.score));
    return {
      key,
      label,
      weight,
      score: available.length ? available.reduce((sum, factor) => sum + factor.score, 0) / available.length : 50,
      coverage: available.length / Math.max(factors.length, 1),
      available,
    };
  };
  const trendLayer = makeLayer("trend", "契約趨勢", 40, [
    { name: "近 20 根報酬", score: Number.isFinite(periodChangePct) ? clampScore(50 + periodChangePct * 4) : null, value: periodChangePct },
    { name: "價格／20 期均線", score: [latest.close, snapshot.ma?.[20]].every(Number.isFinite) ? (latest.close >= snapshot.ma[20] ? 65 : 35) : null, value: snapshot.ma?.[20] },
    { name: "5／20 期均線", score: [snapshot.ma?.[5], snapshot.ma?.[20]].every(Number.isFinite) ? (snapshot.ma[5] >= snapshot.ma[20] ? 65 : 35) : null, value: snapshot.ma?.[5] },
    { name: "MACD 趨勢", score: [snapshot.macd, snapshot.macdSignal].every(Number.isFinite) ? (snapshot.macd >= snapshot.macdSignal ? 64 : 36) : null, value: snapshot.macd },
  ]);
  const volumeLayer = makeLayer("volume", "成交量能", 25, [
    { name: "Delta Volume", score: Number.isFinite(snapshot.deltaVolume) ? (snapshot.deltaVolume > 0 ? 64 : snapshot.deltaVolume < 0 ? 36 : 50) : null, value: snapshot.deltaVolume },
    {
      name: "量價配合",
      score: Number.isFinite(volumeRatio) && Number.isFinite(latestChange)
        ? volumeRatio >= 1.2 ? (latestChange >= 0 ? 68 : 32) : latestChange >= 0 ? 56 : 44
        : null,
      value: volumeRatio,
    },
    { name: "OBV", score: Number.isFinite(snapshot.obv) ? (latestChange > 0 ? 60 : latestChange < 0 ? 40 : 50) : null, value: snapshot.obv },
  ]);
  const oiLayer = makeLayer("open-interest", "未平倉結構", 20, [
    {
      name: "價量 OI 結構",
      score: Number.isFinite(snapshot.oiChange) && Number.isFinite(latestChange)
        ? latestChange >= 0 && snapshot.oiChange > 0 ? 68
          : latestChange < 0 && snapshot.oiChange > 0 ? 32
            : latestChange >= 0 && snapshot.oiChange < 0 ? 55
              : latestChange < 0 && snapshot.oiChange < 0 ? 45
                : 50
        : null,
      value: snapshot.oiChange,
    },
    { name: "未平倉量", score: Number.isFinite(snapshot.openInterest) ? 50 : null, value: snapshot.openInterest },
  ]);
  const timingLayer = makeLayer("timing", "進出場訊號", 15, [
    { name: "RSI", score: Number.isFinite(snapshot.rsi) ? clampScore(20 + snapshot.rsi * 0.6) : null, value: snapshot.rsi },
    { name: "KD", score: [snapshot.kd?.k, snapshot.kd?.d].every(Number.isFinite) ? (snapshot.kd.k >= snapshot.kd.d ? 62 : 38) : null, value: snapshot.kd?.k },
    { name: "BIAS 20", score: Number.isFinite(snapshot.bias20) ? clampScore(50 + snapshot.bias20 * 2) : null, value: snapshot.bias20 },
  ]);
  const layers = [trendLayer, volumeLayer, oiLayer, timingLayer];
  const totalScore = Math.round(layers.reduce((sum, layer) => sum + layer.score * layer.weight / 100, 0));
  const judgement = totalScore >= 62
    ? { label: "期貨結構偏多", tone: "bullish", action: "趨勢與量價偏正向，仍須以支撐、保證金與停損管理部位。" }
    : totalScore <= 38
      ? { label: "期貨結構偏空", tone: "bearish", action: "趨勢與部位結構偏弱，反彈時優先控制槓桿與隔夜風險。" }
      : { label: "期貨結構中性", tone: "neutral", action: "多空因子互有抵銷，等待價格、成交量與 OI 同向確認。" };
  const leader = backtestLearning?.signals?.[0];
  const recent20 = summarizeBacktestSegment(Array.isArray(leader?.returns) ? leader.returns.slice(-20) : []);
  const recentWinPct = Number.isFinite(recent20.winRate) ? recent20.winRate * 100 : null;
  return {
    layers,
    totalScore,
    judgement,
    marketState: totalScore >= 62 ? "多方結構" : totalScore <= 38 ? "空方結構" : "中性整理",
    coverage: Math.round((layers.reduce((sum, layer) => sum + layer.coverage, 0) / layers.length) * 100),
    recent20: {
      ...recent20,
      winState: Number.isFinite(recentWinPct) ? (recentWinPct >= 50 ? "模型觀察正常" : "降低訊號權重") : "樣本不足",
      pfState: Number.isFinite(recent20.profitFactor) ? (recent20.profitFactor >= 1 ? "正常" : "模型失真") : "樣本不足",
      mddState: Number.isFinite(recent20.maxDrawdown) && recent20.maxDrawdown <= -15 ? "啟動風控警報" : "風險可控",
    },
    driftChecks: [],
    outputSteps: [
      `契約趨勢 ${Math.round(trendLayer.score)} / 100`,
      `成交量能 ${Math.round(volumeLayer.score)} / 100`,
      `未平倉結構 ${Math.round(oiLayer.score)} / 100`,
      `進出場訊號 ${Math.round(timingLayer.score)} / 100`,
      `綜合評分 ${totalScore} / 100，${judgement.label}`,
    ],
  };
}
function calculateBollingerBands(history, period = 20, deviation = 2) {
  const closes = history.map((day) => day.close);
  const middle = movingAverage(closes, period);
  return closes.map((close, index) => {
    if (index + 1 < period || middle[index] === null) {
      return { middle: null, upper: null, lower: null, bandwidth: null };
    }
    const window = closes.slice(index - period + 1, index + 1).filter(Number.isFinite);
    if (window.length < period) return { middle: null, upper: null, lower: null, bandwidth: null };
    const average = middle[index];
    const variance = window.reduce((sum, value) => sum + ((value - average) ** 2), 0) / period;
    const sigma = Math.sqrt(variance);
    const upper = average + sigma * deviation;
    const lower = average - sigma * deviation;
    const bandwidth = average ? ((upper - lower) / average) * 100 : null;
    return { middle: average, upper, lower, bandwidth };
  });
}
function calculateFibonacciRetracement(history, lookback = 80) {
  const window = history.slice(-lookback);
  if (window.length < 10) return null;
  const highPoint = window.reduce((best, item, index) => (
    item.high > best.value ? { value: item.high, index, date: item.date } : best
  ), { value: -Infinity, index: -1, date: "" });
  const lowPoint = window.reduce((best, item, index) => (
    item.low < best.value ? { value: item.low, index, date: item.date } : best
  ), { value: Infinity, index: -1, date: "" });
  const range = highPoint.value - lowPoint.value;
  if (!Number.isFinite(range) || range <= 0) return null;
  const upSwing = highPoint.index > lowPoint.index;
  const ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  const levels = ratios.map((ratio) => ({
    ratio,
    label: `${Math.round(ratio * 1000) / 10}%`,
    value: upSwing
      ? highPoint.value - range * ratio
      : lowPoint.value + range * ratio,
  }));
  return { highPoint, lowPoint, range, upSwing, levels };
}
function calculateSupportResistance(history, lookback = 80) {
  const window = history.slice(-lookback);
  if (window.length < 8) return { supports: [], resistances: [] };
  const pivots = technicalPivots(window, 2);
  const latest = window.at(-1);
  const lows = pivots.filter((item) => item.type === "low").map((item) => item.value);
  const highs = pivots.filter((item) => item.type === "high").map((item) => item.value);
  if (lows.length < 2) lows.push(Math.min(...window.map((item) => item.low)));
  if (highs.length < 2) highs.push(Math.max(...window.map((item) => item.high)));

  const cluster = (values, side) => {
    const tolerance = Math.max(latest.close * 0.012, 0.01);
    const sorted = [...values].sort((a, b) => a - b);
    const groups = [];
    sorted.forEach((value) => {
      const group = groups.find((item) => Math.abs(item.average - value) <= tolerance);
      if (group) {
        group.values.push(value);
        group.average = group.values.reduce((sum, item) => sum + item, 0) / group.values.length;
      } else {
        groups.push({ values: [value], average: value });
      }
    });
    return groups
      .map((group) => ({
        value: group.average,
        touches: group.values.length,
        distancePct: ((group.average - latest.close) / latest.close) * 100,
        side,
      }))
      .sort((a, b) => Math.abs(a.distancePct) - Math.abs(b.distancePct))
      .slice(0, 3);
  };

  const supports = cluster(lows.filter((value) => value <= latest.close * 1.02), "support");
  const resistances = cluster(highs.filter((value) => value >= latest.close * 0.98), "resistance");
  return { supports, resistances };
}
function calculateSmartMoneyConcepts(history, lookback = 90) {
  const window = history.slice(-lookback);
  if (window.length < 12) {
    return { bias: "neutral", signals: [], levels: [] };
  }
  const pivots = technicalPivots(window, 2);
  const swingHighs = pivots.filter((item) => item.type === "high");
  const swingLows = pivots.filter((item) => item.type === "low");
  const latest = window.at(-1);
  const previousHigh = swingHighs.at(-1);
  const previousLow = swingLows.at(-1);
  const signals = [];
  const levels = [];
  let score = 0;

  if (previousHigh) {
    levels.push({ type: "liquidity-high", label: "買方流動性", value: previousHigh.value });
    if (latest.close > previousHigh.value) {
      score += 2;
      signals.push(`BOS 向上突破前高 ${previousHigh.value.toFixed(2)}`);
    } else if (latest.high > previousHigh.value && latest.close < previousHigh.value) {
      score -= 1;
      signals.push("掃過前高後收回，疑似上方流動性獵取");
    }
  }
  if (previousLow) {
    levels.push({ type: "liquidity-low", label: "賣方流動性", value: previousLow.value });
    if (latest.close < previousLow.value) {
      score -= 2;
      signals.push(`BOS 向下跌破前低 ${previousLow.value.toFixed(2)}`);
    } else if (latest.low < previousLow.value && latest.close > previousLow.value) {
      score += 1;
      signals.push("跌破前低後收回，疑似下方流動性回收");
    }
  }

  const recentFvg = window.slice(-24).map((item, index, items) => {
    if (index < 2) return null;
    const twoBack = items[index - 2];
    if (item.low > twoBack.high) return { type: "bullish-fvg", label: "多方 FVG", upper: item.low, lower: twoBack.high };
    if (item.high < twoBack.low) return { type: "bearish-fvg", label: "空方 FVG", upper: twoBack.low, lower: item.high };
    return null;
  }).filter(Boolean).at(-1);
  if (recentFvg) {
    levels.push({ type: recentFvg.type, label: recentFvg.label, value: (recentFvg.upper + recentFvg.lower) / 2, upper: recentFvg.upper, lower: recentFvg.lower });
    signals.push(`${recentFvg.label} ${recentFvg.lower.toFixed(2)} ~ ${recentFvg.upper.toFixed(2)} 尚可作為失衡區觀察`);
    score += recentFvg.type === "bullish-fvg" ? 1 : -1;
  }

  const bias = score > 0 ? "bullish" : score < 0 ? "bearish" : "neutral";
  return { bias, score, signals, levels };
}
function buildChipIndicator(detail) {
  const institutional = parseAnalysisNumber(detail.institutionalTrades?.totalValue);
  const large = parseAnalysisNumber(detail.shareholderDistribution?.largeHolderRatio);
  const retail = parseAnalysisNumber(detail.shareholderDistribution?.retailHolderRatio);
  let chipScore = 0;
  const notes = [];
  if (institutional !== null) {
    if (institutional > 0) {
      chipScore += 1;
      notes.push("法人買超");
    } else if (institutional < 0) {
      chipScore -= 1;
      notes.push("法人賣超");
    }
  }
  if (large !== null) {
    if (large >= 60) chipScore += 1;
    else if (large < 35) chipScore -= 1;
    notes.push(`大戶 ${large.toFixed(1)}%`);
  }
  if (retail !== null) {
    if (retail >= 35) chipScore -= 1;
    else if (retail < 15) chipScore += 1;
    notes.push(`散戶 ${retail.toFixed(1)}%`);
  }
  if (!notes.length) return null;
  return {
    score: chipScore,
    value: `${chipScore > 0 ? "+" : ""}${chipScore}`,
    text: `${notes.join("、")}；${chipScore >= 2 ? "籌碼偏集中" : chipScore <= -2 ? "籌碼偏鬆動" : "籌碼訊號分歧"}`,
    direction: chipScore > 0 ? "bullish" : chipScore < 0 ? "bearish" : "neutral",
  };
}
function buildMovingAverageIndicator(history, { isEtf = false, isFutures = false, assetLabel = "股價", periodUnit = "日" } = {}) {
  if (!Array.isArray(history) || history.length < 20) return null;
  const closes = history.map((item) => item.close).filter(Number.isFinite);
  const latestClose = closes.at(-1);
  if (!Number.isFinite(latestClose)) return null;

  const periods = [5, 10, 20, 60, 120, 240];
  const series = Object.fromEntries(periods.map((period) => [
    period,
    technicalSma(closes, period),
  ]));
  const current = Object.fromEntries(periods.map((period) => [period, series[period].at(-1)]));
  const previous = Object.fromEntries(periods.map((period) => [period, series[period].at(-2)]));
  const availablePeriods = periods.filter((period) => Number.isFinite(current[period]));
  if (availablePeriods.length < 2) return null;

  const shortPeriods = [5, 10, 20].filter((period) => Number.isFinite(current[period]));
  const longPeriods = [60, 120, 240].filter((period) => Number.isFinite(current[period]));
  const isDescending = (items) => items.length >= 2 && items.every((period, index) => (
    index === 0 || current[items[index - 1]] > current[period]
  ));
  const isAscending = (items) => items.length >= 2 && items.every((period, index) => (
    index === 0 || current[items[index - 1]] < current[period]
  ));
  const bullishOrder = isDescending(availablePeriods);
  const bearishOrder = isAscending(availablePeriods);
  const shortBullish = isDescending(shortPeriods);
  const shortBearish = isAscending(shortPeriods);
  const longBullish = isDescending(longPeriods);
  const longBearish = isAscending(longPeriods);

  const slopePeriods = availablePeriods.filter((period) => Number.isFinite(previous[period]));
  const risingCount = slopePeriods.filter((period) => current[period] > previous[period]).length;
  const fallingCount = slopePeriods.filter((period) => current[period] < previous[period]).length;
  const recentCrosses = [];
  const crossPairs = [[5, 10], [5, 20], [10, 20], [20, 60], [60, 120], [120, 240]];
  crossPairs.forEach(([fast, slow]) => {
    if (![current[fast], current[slow], previous[fast], previous[slow]].every(Number.isFinite)) return;
    if (previous[fast] <= previous[slow] && current[fast] > current[slow]) {
      recentCrosses.push(`${fast} ${periodUnit}均線黃金交叉 ${slow} ${periodUnit}均線`);
    } else if (previous[fast] >= previous[slow] && current[fast] < current[slow]) {
      recentCrosses.push(`${fast} ${periodUnit}均線死亡交叉 ${slow} ${periodUnit}均線`);
    }
  });

  const values = availablePeriods.map((period) => current[period]);
  const spreadPct = values.length >= 2
    ? ((Math.max(...values) - Math.min(...values)) / latestClose) * 100
    : null;
  const referencePeriod = Number.isFinite(current[20]) ? 20 : availablePeriods[0];
  const priceBias = ((latestClose - current[referencePeriod]) / current[referencePeriod]) * 100;
  const recentVolumes = history.slice(-21, -1).map((item) => item.volume).filter(Number.isFinite);
  const averageVolume = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const volumeRatio = averageVolume && Number.isFinite(history.at(-1)?.volume)
    ? history.at(-1).volume / averageVolume
    : null;
  let direction = "neutral";
  let analysisScore = 0;
  const notes = [];
  const confirmations = [];
  const risks = [];

  if (bullishOrder || (shortBullish && longBullish)) {
    direction = "bullish";
    analysisScore += 2;
    notes.push("短中長期均線呈多頭排列");
  } else if (bearishOrder || (shortBearish && longBearish)) {
    direction = "bearish";
    analysisScore -= 2;
    notes.push("短中長期均線呈空頭排列");
  } else if (shortBullish) {
    direction = "bullish";
    analysisScore += 1;
    notes.push("短期均線轉為多頭排列，中長期仍待確認");
  } else if (shortBearish) {
    direction = "bearish";
    analysisScore -= 1;
    notes.push("短期均線轉為空頭排列，中長期仍待確認");
  } else {
    notes.push("均線順序交錯，趨勢處於整理或轉折");
  }

  if (risingCount >= Math.ceil(slopePeriods.length * 0.7)) {
    analysisScore += 1;
    notes.push(`${risingCount} 條均線同步上揚`);
    if (direction === "neutral") direction = "bullish";
  } else if (fallingCount >= Math.ceil(slopePeriods.length * 0.7)) {
    analysisScore -= 1;
    notes.push(`${fallingCount} 條均線同步下彎`);
    if (direction === "neutral") direction = "bearish";
  }

  if (recentCrosses.length) {
    const bullishCrosses = recentCrosses.filter((item) => item.includes("黃金")).length;
    const bearishCrosses = recentCrosses.filter((item) => item.includes("死亡")).length;
    analysisScore += Math.sign(bullishCrosses - bearishCrosses);
    notes.push(recentCrosses.join("、"));
    if (bullishCrosses > bearishCrosses) direction = "bullish";
    if (bearishCrosses > bullishCrosses) direction = "bearish";
  }

  if (Number.isFinite(spreadPct) && spreadPct <= 2.5) {
    notes.push(`均線幅度僅 ${spreadPct.toFixed(1)}%，屬糾結區，等待放量表態`);
    risks.push("均線糾結時容易產生假突破，不宜只憑交叉追價");
    analysisScore = Math.sign(analysisScore) * Math.min(Math.abs(analysisScore), 1);
  }
  if (Math.abs(priceBias) >= 10) {
    notes.push(`${assetLabel}距 ${referencePeriod} ${periodUnit}均線 ${priceBias >= 0 ? "+" : ""}${priceBias.toFixed(1)}%，乖離偏大`);
    risks.push(priceBias > 0 ? "正乖離偏大，短線追價風險升高" : "負乖離偏大，需等待止跌而非直接搶反彈");
    analysisScore -= Math.sign(priceBias);
    if (priceBias > 0 && direction === "bullish") direction = "neutral";
  } else {
    notes.push(`${assetLabel}距 ${referencePeriod} ${periodUnit}均線 ${priceBias >= 0 ? "+" : ""}${priceBias.toFixed(1)}%`);
  }

  if (latestClose > current[referencePeriod]) {
    confirmations.push(`${assetLabel}站上 ${referencePeriod} ${periodUnit}均線，短線支撐較有利`);
  } else {
    confirmations.push(`${assetLabel}跌破 ${referencePeriod} ${periodUnit}均線，短線壓力增加`);
  }
  if (Number.isFinite(current[60])) {
    confirmations.push(latestClose >= current[60] ? `${assetLabel}位於 60 ${periodUnit}均線上方，中期結構較穩` : `${assetLabel}位於 60 ${periodUnit}均線下方，中期趨勢偏弱`);
  }
  if (Number.isFinite(volumeRatio)) {
    confirmations.push(volumeRatio >= 1.2
      ? `成交量為 20 日均量 ${volumeRatio.toFixed(2)} 倍，量能確認較強`
      : volumeRatio <= 0.8
        ? `成交量僅 20 日均量 ${volumeRatio.toFixed(2)} 倍，訊號可信度降低`
        : `成交量為 20 日均量 ${volumeRatio.toFixed(2)} 倍，量能屬正常`);
    if (volumeRatio <= 0.8) risks.push("量能不足，均線突破或跌破仍需後續確認");
  }
  if (!risks.length) risks.push("均線屬落後指標，仍須搭配成交量、MACD、RSI、K 線與支撐壓力");

  const periodRoles = {
    5: "週線／短線強弱",
    10: "雙週線／短線操作",
    20: "月線／波段關鍵",
    60: "季線／中期趨勢",
    120: "半年線／中長期方向",
    240: "年線／長期多空分界",
  };
  const headline = direction === "bullish"
    ? "均線結構偏多"
    : direction === "bearish"
      ? "均線結構偏空"
      : "均線結構整理";
  const practical = direction === "bullish"
    ? "優先觀察回測上揚均線不破、量能配合後的續強機會，不在乖離過大時追價。"
    : direction === "bearish"
      ? "反彈若無法站回下彎均線，仍以風險控管為主；重新站回季線後再提高信心。"
      : "等待均線脫離糾結並由價格、斜率與成交量同向確認，再判斷趨勢方向。";

  return {
    score: Math.max(-3, Math.min(3, analysisScore)),
    direction,
    value: `${headline} · ${analysisScore > 0 ? "+" : ""}${Math.max(-3, Math.min(3, analysisScore))}`,
    text: notes.join("；"),
    headline,
    periods: availablePeriods.map((period) => ({
      period,
      label: `${period} ${periodUnit}均線`,
      role: isFutures ? ({ 5: "短線動能", 10: "短線趨勢", 20: "波段關鍵", 60: "中期趨勢", 120: "長期方向", 240: "超長期方向" }[period]) : periodRoles[period],
      value: current[period],
      slope: Number.isFinite(previous[period])
        ? current[period] > previous[period] ? "向上" : current[period] < previous[period] ? "向下" : "走平"
        : "--",
      position: latestClose >= current[period] ? `${assetLabel}在上` : `${assetLabel}在下`,
    })),
    confirmations,
    crosses: recentCrosses.length ? recentCrosses : ["近期未出現新黃金交叉或死亡交叉"],
    practical,
    risks,
    suitability: isFutures
      ? `期貨契約建議以 5、20、60 ${periodUnit}均線搭配 MACD、RSI、成交量與未平倉量確認，並納入槓桿及轉倉風險。`
      : isEtf
        ? "ETF 建議以 20 日線＋60 日線＋成交量為主，適合波段操作、定期加碼與資產配置。"
        : "個股建議以 5 日線＋20 日線＋60 日線，搭配 MACD、RSI、成交量及籌碼面交叉確認。",
  };
}
function analyzeTechnicalTheories(detail) {
  const history = (detail.historyDays || [])
    .map((item) => ({
      ...item,
      open: parseAnalysisNumber(item.open),
      high: parseAnalysisNumber(item.high),
      low: parseAnalysisNumber(item.low),
      close: parseAnalysisNumber(item.close),
      volume: parseAnalysisNumber(item.volume),
      openInterest: parseAnalysisNumber(item.openInterest),
    }))
    .filter((item) => [item.open, item.high, item.low, item.close].every(Number.isFinite));
  if (history.length < 5) {
    return {
      score: 0,
      evidenceCount: 0,
      patterns: ["歷史資料不足，無法形成型態判斷"],
      indicators: ["指標資料不足"],
      priceIndicators: [],
      volumeIndicators: [],
      breadthIndicators: [],
      indicatorSummary: "價量指標資料不足",
    };
  }

  let score = 0;
  let evidenceCount = 0;
  const patterns = [];
  const theorySignals = [];
  const indicators = [];
  const priceIndicators = [];
  const volumeIndicators = [];
  const breadthIndicators = [];
  const latest = history.at(-1);
  const previous = history.at(-2);
  const isFuturesDetail = Boolean(detail.futuresNativeInterval || history.some((item) => Number.isFinite(item.openInterest)));
  const futuresPeriodUnit = detail.futuresNativeInterval === "week" ? "週" : detail.futuresNativeInterval === "month" ? "月" : "日";
  const assetLabel = isFuturesDetail ? "期貨價格" : "股價";
  const ma5 = parseAnalysisNumber(detail.ma5);
  const ma20 = parseAnalysisNumber(detail.ma20);
  const ma60 = parseAnalysisNumber(detail.ma60);
  const prior20 = history.slice(-21, -1);
  const priorHigh = prior20.length ? Math.max(...prior20.map((item) => item.high)) : null;
  const priorLow = prior20.length ? Math.min(...prior20.map((item) => item.low)) : null;
  const recentVolumes = history.slice(-6, -1).map((item) => item.volume).filter(Number.isFinite);
  const averageVolume = recentVolumes.length
    ? recentVolumes.reduce((sum, value) => sum + value, 0) / recentVolumes.length
    : null;
  const closes = history.map((item) => item.close);
  const ma20Series = technicalSma(closes, 20);
  const currentMa20 = ma20Series.at(-1);
  const previousMa20 = ma20Series.at(-2);
  const recent = history.slice(-40);
  const recentPivots = technicalPivots(recent);
  const pivotHighs = recentPivots.filter((item) => item.type === "high");
  const pivotLows = recentPivots.filter((item) => item.type === "low");

  const recordIndicator = (group, name, value, text, direction = "neutral", meta = {}) => {
    const item = { name, value, text, direction, ...meta };
    if (group === "volume") volumeIndicators.push(item);
    else if (group === "breadth") breadthIndicators.push(item);
    else priceIndicators.push(item);
    indicators.push(`${name} ${value}：${text}`);
  };

  const recordScoredIndicator = (group, name, value, text, direction = "neutral", scoreDelta = 0, meta = {}) => {
    evidenceCount += 1;
    score += scoreDelta;
    recordIndicator(group, name, value, text, direction, meta);
  };

  const addTheory = (name, text, theoryScore = 0) => {
    const direction = theoryScore > 0 ? "bullish" : theoryScore < 0 ? "bearish" : "neutral";
    score += theoryScore;
    evidenceCount += 1;
    theorySignals.push({ name, text, score: theoryScore, direction });
    patterns.push(`${name}：${text}`);
  };

  // Dow Theory: use successive swing highs/lows and the medium-term average direction.
  if (pivotHighs.length >= 2 && pivotLows.length >= 2) {
    const higherHigh = pivotHighs.at(-1).value > pivotHighs.at(-2).value;
    const higherLow = pivotLows.at(-1).value > pivotLows.at(-2).value;
    const lowerHigh = pivotHighs.at(-1).value < pivotHighs.at(-2).value;
    const lowerLow = pivotLows.at(-1).value < pivotLows.at(-2).value;
    if (higherHigh && higherLow) {
      addTheory("道氏理論", "波段高點與低點同步墊高，主要趨勢偏多", 1);
    } else if (lowerHigh && lowerLow) {
      addTheory("道氏理論", "波段高點與低點同步下移，主要趨勢偏空", -1);
    } else {
      addTheory("道氏理論", "高低點未形成同向序列，趨勢仍在轉折或盤整", 0);
    }
  } else {
    addTheory("道氏理論", "有效波段轉折點不足，暫以均線及區間方向輔助", 0);
  }

  // Elliott Wave: classify recent alternating pivots as a probable impulse or correction.
  const alternatingPivots = recentPivots.reduce((items, pivot) => {
    const previousPivot = items.at(-1);
    if (!previousPivot || previousPivot.type !== pivot.type) items.push(pivot);
    else if (
      (pivot.type === "high" && pivot.value > previousPivot.value)
      || (pivot.type === "low" && pivot.value < previousPivot.value)
    ) items[items.length - 1] = pivot;
    return items;
  }, []).slice(-6);
  if (alternatingPivots.length >= 5) {
    const first = alternatingPivots[0];
    const last = alternatingPivots.at(-1);
    const risingSwings = alternatingPivots.filter((item, index) => index > 0 && item.value > alternatingPivots[index - 1].value).length;
    const fallingSwings = alternatingPivots.length - 1 - risingSwings;
    if (last.value > first.value && risingSwings >= 3) {
      addTheory("波浪理論", "近期轉折近似多方推進浪，仍須防範第五浪末端震盪", 1);
    } else if (last.value < first.value && fallingSwings >= 3) {
      addTheory("波浪理論", "近期轉折近似空方推進或 ABC 修正延伸", -1);
    } else {
      addTheory("波浪理論", "波段重疊度高，浪型尚未完成確認", 0);
    }
  } else {
    addTheory("波浪理論", "可辨識轉折不足，暫不強行標定浪數", 0);
  }

  // Granville's eight rules around the 20-day moving average.
  if ([currentMa20, previousMa20].every(Number.isFinite)) {
    const distancePct = ((latest.close - currentMa20) / currentMa20) * 100;
    const crossedUp = previous.close <= previousMa20 && latest.close > currentMa20;
    const crossedDown = previous.close >= previousMa20 && latest.close < currentMa20;
    const maRising = currentMa20 > previousMa20;
    if (crossedUp && maRising) {
      addTheory("葛蘭碧八大法則", `${assetLabel}向上突破走升的 20 ${futuresPeriodUnit}均線，符合第一買進法則`, 1);
    } else if (crossedDown && !maRising) {
      addTheory("葛蘭碧八大法則", `${assetLabel}向下跌破走弱的 20 ${futuresPeriodUnit}均線，符合第一賣出法則`, -1);
    } else if (maRising && latest.low <= currentMa20 * 1.01 && latest.close > currentMa20) {
      addTheory("葛蘭碧八大法則", "回測上升均線後重新站回，接近第二或第三買進法則", 1);
    } else if (!maRising && latest.high >= currentMa20 * 0.99 && latest.close < currentMa20) {
      addTheory("葛蘭碧八大法則", "反彈受下降均線壓制，接近第二或第三賣出法則", -1);
    } else if (distancePct >= 10) {
      addTheory("葛蘭碧八大法則", `${assetLabel}高於 20 ${futuresPeriodUnit}均線 ${distancePct.toFixed(1)}%，正乖離過大`, -1);
    } else if (distancePct <= -10) {
      addTheory("葛蘭碧八大法則", `${assetLabel}低於 20 ${futuresPeriodUnit}均線 ${Math.abs(distancePct).toFixed(1)}%，具超跌反彈條件但需止跌`, 0);
    } else {
      addTheory("葛蘭碧八大法則", `${assetLabel}與 20 ${futuresPeriodUnit}均線距離正常，尚無明確買賣法則觸發`, 0);
    }
  } else {
    addTheory("葛蘭碧八大法則", "20 日均線資料不足", 0);
  }

  // Reversal patterns: double top/bottom with tolerance based on recent volatility.
  if (pivotHighs.length >= 2 || pivotLows.length >= 2) {
    const highs = pivotHighs.slice(-2);
    const lows = pivotLows.slice(-2);
    const topTolerance = highs.length === 2 ? Math.abs(highs[1].value - highs[0].value) / highs[0].value : 1;
    const bottomTolerance = lows.length === 2 ? Math.abs(lows[1].value - lows[0].value) / lows[0].value : 1;
    if (highs.length === 2 && topTolerance <= 0.035 && latest.close < Math.min(...recent.slice(highs[0].index, highs[1].index + 1).map((item) => item.low))) {
      addTheory("反轉型態理論", "近似雙重頂且跌破頸線，反轉風險升高", -1);
    } else if (lows.length === 2 && bottomTolerance <= 0.035 && latest.close > Math.max(...recent.slice(lows[0].index, lows[1].index + 1).map((item) => item.high))) {
      addTheory("反轉型態理論", "近似雙重底且突破頸線，反轉向上機率提高", 1);
    } else if (topTolerance <= 0.035) {
      addTheory("反轉型態理論", "高檔近似雙重頂，但尚未有效跌破頸線", 0);
    } else if (bottomTolerance <= 0.035) {
      addTheory("反轉型態理論", "低檔近似雙重底，但尚未有效突破頸線", 0);
    } else {
      addTheory("反轉型態理論", "未形成已確認的雙頂、雙底或明顯頭肩反轉", 0);
    }
  } else {
    addTheory("反轉型態理論", "轉折點不足，尚無可確認反轉型態", 0);
  }

  // Continuation patterns: rectangle or converging triangle followed by breakout.
  const consolidation = history.slice(-16, -1);
  if (consolidation.length >= 10) {
    const consolidationHighs = consolidation.map((item) => item.high);
    const consolidationLows = consolidation.map((item) => item.low);
    const rangeHigh = Math.max(...consolidationHighs);
    const rangeLow = Math.min(...consolidationLows);
    const rangePct = ((rangeHigh - rangeLow) / Math.max(rangeLow, 0.0001)) * 100;
    const converging = technicalSlope(consolidationHighs) < 0 && technicalSlope(consolidationLows) > 0;
    if (latest.close > rangeHigh) {
      addTheory("連續整理型態理論", `${converging ? "三角收斂" : "箱型整理"}後向上突破`, 1);
    } else if (latest.close < rangeLow) {
      addTheory("連續整理型態理論", `${converging ? "三角收斂" : "箱型整理"}後向下跌破`, -1);
    } else if (converging) {
      addTheory("連續整理型態理論", "高點下降、低點上升，呈三角收斂等待方向", 0);
    } else if (rangePct <= 10) {
      addTheory("連續整理型態理論", `近 15 日箱型幅度約 ${rangePct.toFixed(1)}%，仍在整理區`, 0);
    } else {
      addTheory("連續整理型態理論", "區間波動較大，尚未形成穩定旗形、三角形或箱型", 0);
    }
  }

  // Trendline theory based on regression slopes of recent highs and lows.
  const trendWindow = history.slice(-20);
  if (trendWindow.length >= 10) {
    const lowSlope = technicalSlope(trendWindow.map((item) => item.low));
    const highSlope = technicalSlope(trendWindow.map((item) => item.high));
    const normalizedSlope = ((lowSlope + highSlope) / 2) / Math.max(latest.close, 0.0001) * 100;
    if (lowSlope > 0 && highSlope > 0) {
      addTheory("趨勢線理論", `高低軌同步上揚，日均斜率約 ${normalizedSlope.toFixed(2)}%`, 1);
    } else if (lowSlope < 0 && highSlope < 0) {
      addTheory("趨勢線理論", `高低軌同步下彎，日均斜率約 ${normalizedSlope.toFixed(2)}%`, -1);
    } else {
      addTheory("趨勢線理論", "上下軌斜率分歧，趨勢線處於收斂或擴張階段", 0);
    }
  }

  if ([ma5, ma20, ma60].every(Number.isFinite)) {
    evidenceCount += 1;
    if (latest.close > ma5 && ma5 > ma20 && ma20 > ma60) {
      score += 2;
      patterns.push("均線呈多頭排列，趨勢結構偏強");
    } else if (latest.close < ma5 && ma5 < ma20 && ma20 < ma60) {
      score -= 2;
      patterns.push("均線呈空頭排列，趨勢結構偏弱");
    } else {
      patterns.push("均線交錯，價格仍處於整理或轉折階段");
    }
  }
  if (priorHigh !== null && latest.close > priorHigh) {
    evidenceCount += 1;
    score += averageVolume && latest.volume > averageVolume * 1.2 ? 2 : 1;
    patterns.push(averageVolume && latest.volume > averageVolume * 1.2 ? "放量突破近 20 日壓力" : "突破近 20 日壓力，但量能確認有限");
  } else if (priorLow !== null && latest.close < priorLow) {
    evidenceCount += 1;
    score -= averageVolume && latest.volume > averageVolume * 1.2 ? 2 : 1;
    patterns.push(averageVolume && latest.volume > averageVolume * 1.2 ? "放量跌破近 20 日支撐" : "跌破近 20 日支撐");
  }

  const latestBody = Math.abs(latest.close - latest.open);
  const latestRange = Math.max(latest.high - latest.low, 0.0001);
  const upperShadow = latest.high - Math.max(latest.open, latest.close);
  const lowerShadow = Math.min(latest.open, latest.close) - latest.low;
  const previousBearish = previous.close < previous.open;
  const previousBullish = previous.close > previous.open;
  if (
    previousBearish && latest.close > latest.open
    && latest.open <= previous.close && latest.close >= previous.open
  ) {
    evidenceCount += 1;
    score += 1;
    patterns.push("出現多方吞噬型態，短線具反轉意義");
    addTheory("K 線理論", "多方吞噬前一根黑 K，短線買盤轉強", 1);
  } else if (
    previousBullish && latest.close < latest.open
    && latest.open >= previous.close && latest.close <= previous.open
  ) {
    evidenceCount += 1;
    score -= 1;
    patterns.push("出現空方吞噬型態，短線需防轉弱");
    addTheory("K 線理論", "空方吞噬前一根紅 K，短線賣壓轉強", -1);
  } else if (lowerShadow >= latestBody * 2 && upperShadow <= latestBody && latest.close >= latest.open) {
    addTheory("K 線理論", "出現長下影錘頭線，低檔承接力增強", 1);
  } else if (upperShadow >= latestBody * 2 && lowerShadow <= latestBody && latest.close <= latest.open) {
    addTheory("K 線理論", "出現長上影射擊之星，短線上檔賣壓增強", -1);
  } else if (latestBody / latestRange < 0.15) {
    evidenceCount += 1;
    patterns.push("出現十字線，市場多空進入觀望");
    addTheory("K 線理論", "十字線顯示多空平衡，需由下一根 K 線確認", 0);
  } else {
    addTheory("K 線理論", latest.close > latest.open ? "實體紅 K，由買方掌握當日收盤" : "實體黑 K，由賣方掌握當日收盤", latest.close > latest.open ? 1 : -1);
  }

  // Gap theory checks the latest session and whether a recent gap remains unfilled.
  const upwardGap = latest.low > previous.high;
  const downwardGap = latest.high < previous.low;
  if (upwardGap) {
    addTheory("缺口理論", `向上跳空 ${((latest.low - previous.high) / previous.high * 100).toFixed(2)}%，缺口未回補前偏多`, 1);
  } else if (downwardGap) {
    addTheory("缺口理論", `向下跳空 ${((previous.low - latest.high) / previous.low * 100).toFixed(2)}%，缺口未回補前偏空`, -1);
  } else {
    const recentGap = history.slice(-16, -1).map((item, index, items) => {
      if (!index) return null;
      if (item.low > items[index - 1].high) return { type: "up", boundary: items[index - 1].high };
      if (item.high < items[index - 1].low) return { type: "down", boundary: items[index - 1].low };
      return null;
    }).filter(Boolean).at(-1);
    if (recentGap?.type === "up" && latest.low > recentGap.boundary) {
      addTheory("缺口理論", "近期向上缺口仍未完全回補，可視為潛在支撐", 1);
    } else if (recentGap?.type === "down" && latest.high < recentGap.boundary) {
      addTheory("缺口理論", "近期向下缺口仍未完全回補，可視為潛在壓力", -1);
    } else {
      addTheory("缺口理論", "近期無有效未回補缺口", 0);
    }
  }

  const supportResistance = calculateSupportResistance(history);
  const nearestSupport = supportResistance.supports?.[0];
  const nearestResistance = supportResistance.resistances?.[0];
  if (nearestSupport || nearestResistance) {
    const supportText = nearestSupport
      ? `近支撐 ${nearestSupport.value.toFixed(2)}（距離 ${nearestSupport.distancePct.toFixed(1)}%）`
      : "下方有效支撐不足";
    const resistanceText = nearestResistance
      ? `近壓力 ${nearestResistance.value.toFixed(2)}（距離 +${nearestResistance.distancePct.toFixed(1)}%）`
      : "上方壓力尚未明顯";
    const srScore = nearestResistance && latest.close > nearestResistance.value
      ? 1
      : nearestSupport && latest.close < nearestSupport.value
        ? -1
        : 0;
    const srActionText = latest.close > (nearestResistance?.value || Infinity)
      ? "已突破主要壓力，觀察是否站穩"
      : latest.close < (nearestSupport?.value || -Infinity)
        ? "已跌破主要支撐，風險升高"
        : "目前位於支撐與壓力區間內";
    addTheory("Support and Resistance", `${supportText}；${resistanceText}；${srActionText}`, srScore);
  }

  const fibonacci = calculateFibonacciRetracement(history);
  if (fibonacci) {
    const sortedByDistance = [...fibonacci.levels].sort((a, b) => Math.abs(a.value - latest.close) - Math.abs(b.value - latest.close));
    const nearestFib = sortedByDistance[0];
    const golden = fibonacci.levels.find((item) => item.ratio === 0.618);
    const fibDirection = fibonacci.upSwing
      ? latest.close >= (golden?.value || latest.close) ? "bullish" : "neutral"
      : latest.close <= (golden?.value || latest.close) ? "bearish" : "neutral";
    addTheory(
      "斐波那契回撤",
      `${fibonacci.upSwing ? "上升波回撤" : "下降波反彈"}，目前接近 ${nearestFib.label} ${nearestFib.value.toFixed(2)}，61.8% 關鍵位 ${golden?.value.toFixed(2) || "--"}；${fibonacci.upSwing ? "用回撤位判斷多方防守區" : "用反彈位判斷空方壓力區"}`,
      fibDirection === "bullish" ? 1 : fibDirection === "bearish" ? -1 : 0,
    );
  }

  const smc = calculateSmartMoneyConcepts(history);
  if (smc.signals.length) {
    score += Math.sign(smc.score || 0);
    evidenceCount += 1;
    const smcBiasText = smc.bias === "bullish" ? "偏多結構" : smc.bias === "bearish" ? "偏空結構" : "中性結構";
    addTheory("Smart Money Concepts", `${smcBiasText}；${smc.signals.slice(0, 2).join("；")}`, smc.bias === "bullish" ? 1 : smc.bias === "bearish" ? -1 : 0);
  } else {
    addTheory("Smart Money Concepts", "尚未偵測到明確 BOS、流動性掃蕩或 FVG 失衡區", 0);
  }

  if (averageVolume && latest.volume) {
    evidenceCount += 1;
    const volumeRatio = latest.volume / averageVolume;
    const priorAverageVolume = history.slice(-11, -6)
      .map((item) => item.volume)
      .filter(Number.isFinite);
    const priorAverage = priorAverageVolume.length
      ? priorAverageVolume.reduce((sum, value) => sum + value, 0) / priorAverageVolume.length
      : null;
    const averageTrend = priorAverage ? ((averageVolume - priorAverage) / priorAverage) * 100 : null;
    const volumePricePattern = classifyVolumePriceNinePatterns({ latest, previous, volumeRatio, averageTrend });
    score += volumePricePattern.score;
    patterns.push(`量價九式：${volumePricePattern.name}（量比 ${volumeRatio.toFixed(2)}，價變 ${volumePricePattern.priceChangePct >= 0 ? "+" : ""}${volumePricePattern.priceChangePct.toFixed(2)}%）`);
    recordIndicator(
      "volume",
      "平均成交量",
      `量價九式：${volumePricePattern.name}`,
      `${volumePricePattern.text}；量比 ${volumeRatio.toFixed(2)}，價變 ${volumePricePattern.priceChangePct >= 0 ? "+" : ""}${volumePricePattern.priceChangePct.toFixed(2)}%`,
      volumePricePattern.direction,
    );
  }

  const movingAverageIndicator = buildMovingAverageIndicator(history, {
    isEtf: Boolean(detail.isEtf),
    isFutures: isFuturesDetail,
    assetLabel,
    periodUnit: futuresPeriodUnit,
  });
  if (movingAverageIndicator) {
    evidenceCount += 1;
    score += movingAverageIndicator.score;
    recordIndicator(
      "price",
      "均線分析法",
      movingAverageIndicator.value,
      movingAverageIndicator.text,
      movingAverageIndicator.direction,
      { movingAverage: movingAverageIndicator },
    );
  }

  if (history.length >= 9) {
    const kd = calculateKd(history);
    const current = kd.at(-1);
    const prior = kd.at(-2);
    if (current && prior) {
      evidenceCount += 1;
      if (prior.k <= prior.d && current.k > current.d) {
        score += current.k < 30 ? 2 : 1;
        recordIndicator("price", "KD", `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`, "黃金交叉，短線動能轉強", "bullish");
      } else if (prior.k >= prior.d && current.k < current.d) {
        score -= current.k > 70 ? 2 : 1;
        recordIndicator("price", "KD", `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`, "死亡交叉，短線動能轉弱", "bearish");
      } else if (current.k > 80 && current.d > 80) {
        recordIndicator("price", "KD", `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`, "位於超買區，留意高檔鈍化或拉回", "bearish");
      } else if (current.k < 20 && current.d < 20) {
        recordIndicator("price", "KD", `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`, "位於超賣區，等待止跌訊號", "neutral");
      } else {
        recordIndicator(
          "price",
          "KD",
          `K ${current.k.toFixed(1)} / D ${current.d.toFixed(1)}`,
          current.k >= current.d ? "K 值位於 D 值上方，短線偏多" : "K 值位於 D 值下方，短線偏弱",
          current.k >= current.d ? "bullish" : "bearish",
        );
      }
    }
  }
  if (history.length >= 26) {
    const macd = calculateMacd(history);
    const current = macd.at(-1);
    const prior = macd.at(-2);
    if (current?.dif !== null && current?.macd !== null && prior?.dif !== null && prior?.macd !== null) {
      evidenceCount += 1;
      if (prior.dif <= prior.macd && current.dif > current.macd) {
        score += current.osc >= 0 ? 2 : 1;
        recordIndicator("price", "MACD", `DIF ${current.dif.toFixed(2)} / DEA ${current.macd.toFixed(2)}`, "黃金交叉，動能轉強", "bullish");
      } else if (prior.dif >= prior.macd && current.dif < current.macd) {
        score -= current.osc <= 0 ? 2 : 1;
        recordIndicator("price", "MACD", `DIF ${current.dif.toFixed(2)} / DEA ${current.macd.toFixed(2)}`, "死亡交叉，動能轉弱", "bearish");
      } else if (current.osc > 0 && current.osc > prior.osc) {
        score += 1;
        recordIndicator("price", "MACD", `OSC ${current.osc.toFixed(2)}`, "柱狀體位於零軸上方且擴張", "bullish");
      } else if (current.osc < 0 && current.osc < prior.osc) {
        score -= 1;
        recordIndicator("price", "MACD", `OSC ${current.osc.toFixed(2)}`, "負柱擴張，空方動能增強", "bearish");
      } else {
        recordIndicator(
          "price",
          "MACD",
          `OSC ${current.osc.toFixed(2)}`,
          current.osc >= 0 ? "柱狀體位於零軸上方，動能偏多" : "柱狀體位於零軸下方，動能偏弱",
          current.osc >= 0 ? "bullish" : "bearish",
        );
      }
    }
  }
  if (history.length >= 14) {
    const rsi = calculateRsi(history).at(-1);
    if (Number.isFinite(rsi)) {
      evidenceCount += 1;
      if (rsi >= 70) recordIndicator("price", "RSI", rsi.toFixed(1), "進入超買區，留意過熱修正", "bearish");
      else if (rsi <= 30) recordIndicator("price", "RSI", rsi.toFixed(1), "進入超賣區，等待止跌確認", "neutral");
      else if (rsi >= 50) {
        score += 1;
        recordIndicator("price", "RSI", rsi.toFixed(1), "位於多方區", "bullish");
      } else {
        score -= 1;
        recordIndicator("price", "RSI", rsi.toFixed(1), "位於空方區", "bearish");
      }
    }
    const dmi = calculateDmi(history).at(-1);
    if (dmi && Number.isFinite(dmi.plusDi) && Number.isFinite(dmi.minusDi)) {
      evidenceCount += 1;
      if (dmi.plusDi > dmi.minusDi && (dmi.adx || 0) >= 20) {
        score += 1;
        recordIndicator("price", "DMI", `+DI ${dmi.plusDi.toFixed(1)} / -DI ${dmi.minusDi.toFixed(1)} / ADX ${(dmi.adx || 0).toFixed(1)}`, "多方占優且趨勢成形", "bullish");
      } else if (dmi.minusDi > dmi.plusDi && (dmi.adx || 0) >= 20) {
        score -= 1;
        recordIndicator("price", "DMI", `+DI ${dmi.plusDi.toFixed(1)} / -DI ${dmi.minusDi.toFixed(1)} / ADX ${(dmi.adx || 0).toFixed(1)}`, "空方占優且趨勢成形", "bearish");
      } else {
        recordIndicator("price", "DMI", `+DI ${dmi.plusDi.toFixed(1)} / -DI ${dmi.minusDi.toFixed(1)} / ADX ${(dmi.adx || 0).toFixed(1)}`, "趨勢強度不足，較偏區間震盪", "neutral");
      }
    }
  }
  if (history.length >= 20) {
    const bollinger = calculateBollingerBands(history);
    const currentBand = bollinger.at(-1);
    const priorBand = bollinger.at(-6);
    if (currentBand && [currentBand.upper, currentBand.middle, currentBand.lower].every(Number.isFinite)) {
      evidenceCount += 1;
      const position = ((latest.close - currentBand.lower) / Math.max(currentBand.upper - currentBand.lower, 0.0001)) * 100;
      const bandwidthTrend = Number.isFinite(priorBand?.bandwidth)
        ? currentBand.bandwidth - priorBand.bandwidth
        : null;
      if (latest.close > currentBand.upper) {
        score += 1;
        recordIndicator("price", "布林通道", `上軌 ${currentBand.upper.toFixed(2)}`, "收盤突破上軌，趨勢動能強但需防短線過熱", "bullish");
      } else if (latest.close < currentBand.lower) {
        score -= 1;
        recordIndicator("price", "布林通道", `下軌 ${currentBand.lower.toFixed(2)}`, "收盤跌破下軌，弱勢延伸或超跌反彈皆需確認", "bearish");
      } else if (position >= 70) {
        recordIndicator("price", "布林通道", `${position.toFixed(0)}%`, `價格位於通道偏上緣${bandwidthTrend !== null ? `，帶寬${bandwidthTrend >= 0 ? "擴張" : "收斂"}` : ""}`, "bullish");
      } else if (position <= 30) {
        recordIndicator("price", "布林通道", `${position.toFixed(0)}%`, `價格位於通道偏下緣${bandwidthTrend !== null ? `，帶寬${bandwidthTrend >= 0 ? "擴張" : "收斂"}` : ""}`, "bearish");
      } else {
        recordIndicator("price", "布林通道", `${position.toFixed(0)}%`, `價格位於中性區，帶寬 ${currentBand.bandwidth?.toFixed(1) || "--"}%`, "neutral");
      }
    }
  }
  if (history.length >= 6) {
    const bias = calculateBias(history).at(-1);
    if (Number.isFinite(bias)) {
      evidenceCount += 1;
      if (bias >= 8) {
        score -= 1;
        recordIndicator("price", "BIAS", `${bias.toFixed(1)}%`, "正乖離偏大，追價風險升高", "bearish");
      } else if (bias <= -8) {
        recordIndicator("price", "BIAS", `${bias.toFixed(1)}%`, "負乖離偏大，等待止跌與均值回歸", "neutral");
      } else {
        recordIndicator(
          "price",
          "BIAS",
          `${bias.toFixed(1)}%`,
          bias >= 0 ? `${assetLabel}位於短期均線上方，乖離仍在可控區` : `${assetLabel}位於短期均線下方，乖離仍在可控區`,
          bias >= 0 ? "bullish" : "bearish",
        );
      }
    }
    const obv = calculateObv(history);
    const currentObv = obv.at(-1);
    const priorObv = obv.at(-6);
    if (Number.isFinite(currentObv) && Number.isFinite(priorObv)) {
      evidenceCount += 1;
      if (currentObv > priorObv && latest.close >= history.at(-6).close) {
        score += 1;
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "與價格同步走高，資金動能偏正向", "bullish");
      } else if (currentObv < priorObv && latest.close <= history.at(-6).close) {
        score -= 1;
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "與價格同步走低，資金動能偏弱", "bearish");
      } else if (currentObv > priorObv && latest.close < history.at(-6).close) {
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "正背離，價格轉弱但量能未同步惡化", "bullish");
      } else if (currentObv < priorObv && latest.close > history.at(-6).close) {
        score -= 1;
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "負背離，價格上漲但量能未跟進", "bearish");
      } else {
        recordIndicator("volume", "OBV", Math.round(currentObv).toLocaleString("zh-TW"), "近期變化有限，資金方向尚未明朗", "neutral");
      }
    }
  }

  if (history.length >= 15) {
    const atrSeries = calculateAtr(history);
    const currentAtr = atrSeries.at(-1);
    const priorAtr = atrSeries.at(-6);
    if (Number.isFinite(currentAtr)) {
      const atrPct = (currentAtr / Math.max(Math.abs(latest.close), 0.0001)) * 100;
      const atrExpanding = Number.isFinite(priorAtr) && currentAtr > priorAtr * 1.08;
      const atrCooling = Number.isFinite(priorAtr) && currentAtr < priorAtr * 0.92;
      const priceUp = latest.close >= previous.close;
      const direction = atrExpanding
        ? priceUp ? "bullish" : "bearish"
        : "neutral";
      const scoreDelta = atrExpanding
        ? priceUp ? 1 : -1
        : 0;
      const volatilityText = atrPct >= 5
        ? "波動偏高，停損與部位需保守"
        : atrPct >= 2.5
          ? "波動中等，適合搭配支撐壓力控管"
          : "波動收斂，需等待方向突破";
      const trendText = atrExpanding
        ? priceUp ? "ATR 擴張且收盤上行，趨勢推進力偏多" : "ATR 擴張但收盤下行，空方波動風險升高"
        : atrCooling
          ? "ATR 收斂，行情進入整理或等待新方向"
          : "ATR 變化平穩，趨勢動能未明顯放大";
      recordScoredIndicator("price", "ATR", `${currentAtr.toFixed(2)} / ${atrPct.toFixed(2)}%`, `${trendText}；${volatilityText}`, direction, scoreDelta);
    }
  }

  if (history.length >= 20) {
    const cci = calculateCci(history).at(-1);
    if (Number.isFinite(cci)) {
      if (cci >= 100) {
        recordScoredIndicator("price", "CCI", cci.toFixed(1), "突破 +100，商品通道動能偏強，趨勢延續機率較高", "bullish", 1);
      } else if (cci <= -100) {
        recordScoredIndicator("price", "CCI", cci.toFixed(1), "跌破 -100，弱勢動能仍在，需等回到 -100 上方再確認修復", "bearish", -1);
      } else {
        recordScoredIndicator("price", "CCI", cci.toFixed(1), "位於中性通道，價格尚未形成明確趨勢推力", "neutral", 0);
      }
    }
  }

  if (history.length >= 14) {
    const williams = calculateWilliamsR(history).at(-1);
    if (Number.isFinite(williams)) {
      if (williams >= -20) {
        recordScoredIndicator("price", "Williams %R", williams.toFixed(1), "進入短線超買區，續強時可鈍化，但追價風險升高", "bearish", -1);
      } else if (williams <= -80) {
        recordScoredIndicator("price", "Williams %R", williams.toFixed(1), "進入短線超賣區，需觀察是否出現止跌反彈訊號", "neutral", 0);
      } else if (williams >= -50) {
        recordScoredIndicator("price", "Williams %R", williams.toFixed(1), "位於多方半場，短線買盤仍有支撐", "bullish", 1);
      } else {
        recordScoredIndicator("price", "Williams %R", williams.toFixed(1), "位於空方半場，短線反彈仍需量能確認", "bearish", -1);
      }
    }
  }

  if (history.length >= 15) {
    const mfi = calculateMfi(history).at(-1);
    if (Number.isFinite(mfi)) {
      if (mfi >= 80) {
        recordScoredIndicator("volume", "MFI", mfi.toFixed(1), "資金流量進入超買區，價格續強時需留意獲利了結", "bearish", -1);
      } else if (mfi <= 20) {
        recordScoredIndicator("volume", "MFI", mfi.toFixed(1), "資金流量進入超賣區，若價格止跌可視為反彈觀察點", "neutral", 0);
      } else if (mfi >= 50) {
        recordScoredIndicator("volume", "MFI", mfi.toFixed(1), "資金流量位於多方區，量價資金支持仍在", "bullish", 1);
      } else {
        recordScoredIndicator("volume", "MFI", mfi.toFixed(1), "資金流量位於空方區，買盤承接力仍偏弱", "bearish", -1);
      }
    }
  }

  if (history.length >= 11) {
    const momentumSeries = calculateMomentum(history);
    const currentMomentum = momentumSeries.at(-1);
    const priorMomentum = momentumSeries.at(-2);
    if (Number.isFinite(currentMomentum)) {
      const improving = Number.isFinite(priorMomentum) && currentMomentum > priorMomentum;
      const weakening = Number.isFinite(priorMomentum) && currentMomentum < priorMomentum;
      if (currentMomentum > 0 && improving) {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "10 期動能為正且持續改善，趨勢推升力偏多", "bullish", 1);
      } else if (currentMomentum < 0 && weakening) {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "10 期動能為負且持續惡化，下行壓力仍在", "bearish", -1);
      } else if (currentMomentum > 0) {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "動能仍為正，但擴張力道需要重新確認", "bullish", 0);
      } else if (currentMomentum < 0) {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "動能仍為負，反彈需要突破短期壓力", "bearish", 0);
      } else {
        recordScoredIndicator("price", "Momentum", currentMomentum.toFixed(2), "動能接近零軸，多空進入平衡", "neutral", 0);
      }
    }
  }

  if (history.length >= 4) {
    const sarSeries = calculateParabolicSarSeries(history);
    const currentSar = sarSeries.at(-1);
    const priorSar = sarSeries.at(-2);
    if (Number.isFinite(currentSar)) {
      const crossedUp = Number.isFinite(priorSar) && previous.close <= priorSar && latest.close > currentSar;
      const crossedDown = Number.isFinite(priorSar) && previous.close >= priorSar && latest.close < currentSar;
      if (latest.close > currentSar) {
        recordScoredIndicator("price", "SAR", currentSar.toFixed(2), crossedUp ? "價格重新站上 SAR，短線止跌轉強訊號成立" : "價格位於 SAR 上方，追蹤停利線維持偏多", "bullish", crossedUp ? 2 : 1);
      } else {
        recordScoredIndicator("price", "SAR", currentSar.toFixed(2), crossedDown ? "價格跌破 SAR，短線轉弱訊號成立" : "價格位於 SAR 下方，趨勢仍偏弱", "bearish", crossedDown ? -2 : -1);
      }
    }
  }

  if (history.length >= 26) {
    const ichimokuSeries = calculateIchimoku(history);
    const currentIchimoku = ichimokuSeries.at(-1);
    if (
      Number.isFinite(currentIchimoku?.tenkan)
      && Number.isFinite(currentIchimoku?.kijun)
    ) {
      const senkouA = (currentIchimoku.tenkan + currentIchimoku.kijun) / 2;
      const hasCloud = Number.isFinite(currentIchimoku.senkouB);
      const cloudTop = hasCloud ? Math.max(senkouA, currentIchimoku.senkouB) : Math.max(currentIchimoku.tenkan, currentIchimoku.kijun);
      const cloudBottom = hasCloud ? Math.min(senkouA, currentIchimoku.senkouB) : Math.min(currentIchimoku.tenkan, currentIchimoku.kijun);
      const tenkanAbove = currentIchimoku.tenkan >= currentIchimoku.kijun;
      if (latest.close > cloudTop && tenkanAbove) {
        recordScoredIndicator(
          "price",
          "Ichimoku",
          `${currentIchimoku.tenkan.toFixed(2)} / ${currentIchimoku.kijun.toFixed(2)} / ${hasCloud ? currentIchimoku.senkouB.toFixed(2) : "--"}`,
          "價格位於雲層上方且轉換線高於基準線，一目均衡表偏多",
          "bullish",
          2,
        );
      } else if (latest.close < cloudBottom && !tenkanAbove) {
        recordScoredIndicator(
          "price",
          "Ichimoku",
          `${currentIchimoku.tenkan.toFixed(2)} / ${currentIchimoku.kijun.toFixed(2)} / ${hasCloud ? currentIchimoku.senkouB.toFixed(2) : "--"}`,
          "價格位於雲層下方且轉換線低於基準線，一目均衡表偏空",
          "bearish",
          -2,
        );
      } else {
        recordScoredIndicator(
          "price",
          "Ichimoku",
          `${currentIchimoku.tenkan.toFixed(2)} / ${currentIchimoku.kijun.toFixed(2)} / ${hasCloud ? currentIchimoku.senkouB.toFixed(2) : "--"}`,
          "價格與雲層、轉換線及基準線交錯，趨勢仍需等待方向確認",
          "neutral",
          0,
        );
      }
    }
  }

  const breadth = isFuturesDetail ? null : buildMarketBreadthIndicators(detail);
  if (breadth) {
    evidenceCount += 3;
    const breadthTotal = Math.max(breadth.advancing + breadth.declining, 1);
    const obosPct = (breadth.obos / breadthTotal) * 100;
    if (breadth.adr >= 200) {
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；多方廣度過熱`, "bearish");
    } else if (breadth.adr >= 125) {
      score += 1;
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；市場廣度偏多`, "bullish");
    } else if (breadth.adr <= 50) {
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；空方廣度過度擴張`, "neutral");
    } else if (breadth.adr <= 80) {
      score -= 1;
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；市場廣度偏空`, "bearish");
    } else {
      recordIndicator("breadth", "漲跌比率 ADR", `${breadth.adr.toFixed(1)}%`, `上漲 ${breadth.advancing} 家、下跌 ${breadth.declining} 家；多空家數接近`, "neutral");
    }

    if (breadth.previousAdl === null) {
      recordIndicator("breadth", "騰落指標 ADL", Math.round(breadth.adl).toLocaleString("zh-TW"), "已建立首日基準，累積更多交易日後判斷趨勢", "neutral");
    } else if (breadth.adl > breadth.previousAdl) {
      score += 1;
      recordIndicator("breadth", "騰落指標 ADL", Math.round(breadth.adl).toLocaleString("zh-TW"), `較前值上升，市場參與廣度改善；已累積 ${breadth.historyCount} 日`, "bullish");
    } else if (breadth.adl < breadth.previousAdl) {
      score -= 1;
      recordIndicator("breadth", "騰落指標 ADL", Math.round(breadth.adl).toLocaleString("zh-TW"), `較前值下降，市場參與廣度轉弱；已累積 ${breadth.historyCount} 日`, "bearish");
    } else {
      recordIndicator("breadth", "騰落指標 ADL", Math.round(breadth.adl).toLocaleString("zh-TW"), "與前值持平，市場廣度無明顯變化", "neutral");
    }

    if (obosPct >= 20) {
      recordIndicator("breadth", "超買超賣指標 OBOS", `${breadth.obos > 0 ? "+" : ""}${breadth.obos}`, `淨上漲家數占比 ${obosPct.toFixed(1)}%，市場進入超買區`, "bearish");
    } else if (obosPct <= -20) {
      recordIndicator("breadth", "超買超賣指標 OBOS", `${breadth.obos}`, `淨下跌家數占比 ${obosPct.toFixed(1)}%，市場進入超賣區`, "bullish");
    } else {
      recordIndicator("breadth", "超買超賣指標 OBOS", `${breadth.obos > 0 ? "+" : ""}${breadth.obos}`, `淨漲跌家數占比 ${obosPct.toFixed(1)}%，尚未進入極端區`, obosPct > 5 ? "bullish" : obosPct < -5 ? "bearish" : "neutral");
    }
  }

  if (!breadth && isFuturesDetail) {
    buildFuturesBreadthProxyIndicators(history).forEach((item) => {
      recordScoredIndicator("breadth", item.name, item.value, item.text, item.direction, item.scoreDelta || 0);
    });
  }

  const psy = calculatePsy(history);
  if (Number.isFinite(psy)) {
    evidenceCount += 1;
    if (psy >= 75) {
      score -= 1;
      recordIndicator("breadth", "心理線 PSY", `${psy.toFixed(1)}%`, "近 12 日上漲天數過多，市場情緒偏熱", "bearish");
    } else if (psy <= 25) {
      recordIndicator("breadth", "心理線 PSY", `${psy.toFixed(1)}%`, "近 12 日上漲天數偏少，情緒超賣但仍需止跌確認", "bullish");
    } else {
      recordIndicator("breadth", "心理線 PSY", `${psy.toFixed(1)}%`, psy >= 50 ? "多方交易日略占優勢" : "空方交易日略占優勢", psy >= 50 ? "bullish" : "bearish");
    }
  }

  const chipIndicator = buildChipIndicator(detail);
  if (chipIndicator) {
    evidenceCount += 1;
    score += Math.sign(chipIndicator.score);
    recordIndicator("breadth", "籌碼面指標", chipIndicator.value, chipIndicator.text, chipIndicator.direction);
  }

  const backtestLearning = buildBacktestLearningModel(history);
  backtestLearning.institutionalFramework = isFuturesDetail
    ? buildFuturesBacktestFramework(detail, history, backtestLearning)
    : buildInstitutionalBacktestFramework(detail, history, backtestLearning);
  if (backtestLearning.evidenceCount) {
    score += backtestLearning.scoreAdjustment;
    evidenceCount += 1;
  }

  const priceBullish = priceIndicators.filter((item) => item.direction === "bullish").length;
  const priceBearish = priceIndicators.filter((item) => item.direction === "bearish").length;
  const volumeBullish = volumeIndicators.filter((item) => item.direction === "bullish").length;
  const volumeBearish = volumeIndicators.filter((item) => item.direction === "bearish").length;
  const priceDirection = Math.sign(priceBullish - priceBearish);
  const volumeDirection = Math.sign(volumeBullish - volumeBearish);
  const priceVolumeAligned = priceDirection !== 0 && priceDirection === volumeDirection;
  const priceVolumeConflict = priceDirection !== 0 && volumeDirection !== 0 && priceDirection !== volumeDirection;
  if (priceVolumeAligned) score += priceDirection;
  if (priceVolumeConflict && score !== 0) score -= Math.sign(score);
  const indicatorSummary = priceVolumeAligned
    ? `價指標與量指標同步${priceDirection > 0 ? "偏多" : "偏空"}，獲得價量共振確認`
    : priceVolumeConflict
      ? "價指標與量指標方向背離，已自動降低權重"
      : "價量方向尚未形成一致確認";
  const breadthBullish = breadthIndicators.filter((item) => item.direction === "bullish").length;
  const breadthBearish = breadthIndicators.filter((item) => item.direction === "bearish").length;
  const breadthDirection = Math.sign(breadthBullish - breadthBearish);
  const technicalDirection = Math.sign(priceDirection + volumeDirection);
  const breadthAligned = breadthDirection !== 0 && technicalDirection !== 0 && breadthDirection === technicalDirection;
  const breadthConflict = breadthDirection !== 0 && technicalDirection !== 0 && breadthDirection !== technicalDirection;
  if (breadthAligned) score += breadthDirection;
  if (breadthConflict && score !== 0) score -= Math.sign(score);
  const breadthSummary = breadthAligned
    ? `市場廣度、心理與籌碼綜合${breadthDirection > 0 ? "偏多" : "偏空"}，並與價量方向一致`
    : breadthConflict
      ? "市場廣度／籌碼與價量技術方向衝突，已降低權重"
      : "市場廣度、心理與籌碼訊號尚未形成一致方向";

  const bullishTheories = theorySignals.filter((item) => item.direction === "bullish").length;
  const bearishTheories = theorySignals.filter((item) => item.direction === "bearish").length;
  const agreement = Math.max(bullishTheories, bearishTheories) / Math.max(bullishTheories + bearishTheories, 1);
  const conflictPenalty = Math.min(bullishTheories, bearishTheories) >= 3 ? 2 : 0;
  score -= Math.sign(score) * conflictPenalty;
  const theoryDirection = Math.sign(bullishTheories - bearishTheories);
  const scoreDirectionConflict = score !== 0 && theoryDirection !== 0 && Math.sign(score) !== theoryDirection;
  const adaptiveConfidence = scoreDirectionConflict || priceVolumeConflict || breadthConflict
    ? "低"
    : evidenceCount >= 16 && agreement >= 0.7
    ? "高"
    : evidenceCount >= 10 && agreement >= 0.55
      ? "中"
      : "低";
  const directionSummary = bullishTheories > bearishTheories
    ? `${bullishTheories} 項偏多、${bearishTheories} 項偏空`
    : bearishTheories > bullishTheories
      ? `${bearishTheories} 項偏空、${bullishTheories} 項偏多`
      : "多空理論數量接近";
  const adaptiveSummary = [
    directionSummary,
    backtestLearning.summary,
    scoreDirectionConflict ? "型態與綜合指標方向衝突，已自動降低信心" : "",
    indicatorSummary,
    breadthSummary,
  ].filter(Boolean).join("；");

  return {
    score: Math.max(-18, Math.min(18, score)),
    evidenceCount,
    patterns: patterns.slice(0, 14),
    indicators,
    priceIndicators,
    volumeIndicators,
    breadthIndicators,
    indicatorSummary,
    breadthSummary,
    priceVolumeAligned,
    priceVolumeConflict,
    breadthAligned,
    breadthConflict,
    theorySignals,
    adaptiveConfidence,
    adaptiveSummary,
    backtestLearning,
  };
}
function movingAverage(values, windowSize) {
  return values.map((_, index) => {
    const slice = values.slice(Math.max(0, index - windowSize + 1), index + 1).filter((value) => value !== null);
    if (slice.length < Math.min(windowSize, index + 1)) return null;
    return slice.reduce((sum, value) => sum + value, 0) / slice.length;
  });
}
function buildGlobalMarketDetail(item) {
  const historyDays = (item.series || []).map((day) => {
    const open = parseMarketNumber(day.open);
    const high = parseMarketNumber(day.high);
    const low = parseMarketNumber(day.low);
    const close = parseMarketNumber(day.close);
    const volume = parseMarketNumber(day.volumeValue ?? day.volume);
    return {
      date: day.date || day.time || "",
      open: Number.isFinite(open) ? open : close,
      high: Number.isFinite(high) ? high : close,
      low: Number.isFinite(low) ? low : close,
      close,
      change: null,
      volume: Number.isFinite(volume) ? volume : 0,
    };
  }).filter((day) => day.date && Number.isFinite(day.close));
  const closes = historyDays.map((day) => day.close);
  const latest = historyDays.at(-1) || {};
  const maValue = (period) => technicalSma(closes, period).at(-1);
  return {
    code: item.symbol || "",
    name: item.name || item.symbol || "",
    market: "US",
    isEtf: String(item.group || item.type || "").toUpperCase().includes("ETF"),
    snapshotDate: item.date || latest.date || "",
    currentPrice: item.close,
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
    volume: item.volume,
    change: item.change,
    pct: item.pct,
    ma5: maValue(5),
    ma20: maValue(20),
    ma60: maValue(60),
    ma120: maValue(120),
    ma240: maValue(240),
    historyDays,
    historyCount: historyDays.length,
    historyStartDate: historyDays[0]?.date || "",
    historyEndDate: latest.date || "",
    chartIntervals: { supported: ["day", "week", "month"], intradayAvailable: false },
  };
}
function averageFuturesValues(values) {
  const cleanValues = values.filter(Number.isFinite);
  return cleanValues.length ? cleanValues.reduce((sum, value) => sum + value, 0) / cleanValues.length : null;
}
function lastFiniteFuturesValue(values = []) {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    const value = parseMarketNumber(values[index]);
    if (Number.isFinite(value)) return value;
  }
  return null;
}
function calculateFuturesEmaSeries(values = [], period = 12) {
  const cleanValues = values.map((value) => parseMarketNumber(value));
  const result = Array(cleanValues.length).fill(null);
  if (cleanValues.length < period) return result;
  const seed = cleanValues.slice(0, period);
  if (!seed.every(Number.isFinite)) return result;
  let ema = averageFuturesValues(seed);
  result[period - 1] = ema;
  const weight = 2 / (period + 1);
  for (let index = period; index < cleanValues.length; index += 1) {
    const value = cleanValues[index];
    if (!Number.isFinite(value)) continue;
    ema = value * weight + ema * (1 - weight);
    result[index] = ema;
  }
  return result;
}
function calculateFuturesRollingAverageSeries(values = [], period = 5) {
  const cleanValues = values.map((value) => parseMarketNumber(value));
  return cleanValues.map((_, index) => {
    if (index + 1 < period) return null;
    const windowValues = cleanValues.slice(index - period + 1, index + 1);
    return windowValues.every(Number.isFinite) ? averageFuturesValues(windowValues) : null;
  });
}
function calculateFuturesRsiSeries(closes = [], period = 14) {
  const cleanCloses = closes.map((value) => parseMarketNumber(value));
  return cleanCloses.map((_, index) => {
    if (index <= period) return null;
    return calculateFuturesRsi(cleanCloses.slice(0, index + 1), period);
  });
}
function calculateFuturesKdSeries(rows = [], period = 9) {
  const kValues = Array(rows.length).fill(null);
  const dValues = Array(rows.length).fill(null);
  let k = 50;
  let d = 50;
  for (let index = period - 1; index < rows.length; index += 1) {
    const windowRows = rows.slice(index - period + 1, index + 1);
    const high = Math.max(...windowRows.map((row) => row.high).filter(Number.isFinite));
    const low = Math.min(...windowRows.map((row) => row.low).filter(Number.isFinite));
    const close = rows[index]?.close;
    if (!Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close) || high === low) continue;
    const rsv = ((close - low) / (high - low)) * 100;
    k = (2 / 3) * k + (1 / 3) * rsv;
    d = (2 / 3) * d + (1 / 3) * k;
    kValues[index] = k;
    dValues[index] = d;
  }
  return { k: kValues, d: dValues };
}
function calculateFuturesVwapSeries(rows = [], period = 40) {
  return rows.map((_, index) => {
    const windowRows = rows.slice(Math.max(0, index - period + 1), index + 1);
    const numerator = windowRows.reduce((sum, row) => sum + ((row.high + row.low + row.close) / 3) * (row.volume || 0), 0);
    const denominator = windowRows.reduce((sum, row) => sum + (row.volume || 0), 0);
    return denominator ? numerator / denominator : null;
  });
}
function calculateFuturesObvSeries(rows = []) {
  let obv = 0;
  return rows.map((row, index) => {
    if (index === 0) return 0;
    const previous = rows[index - 1];
    obv += row.close > previous.close ? row.volume || 0 : row.close < previous.close ? -(row.volume || 0) : 0;
    return obv;
  });
}
function calculateFuturesMfi(rows = [], period = 14) {
  const windowRows = rows.slice(-(period + 1));
  if (windowRows.length <= period) return null;
  let positiveFlow = 0;
  let negativeFlow = 0;
  for (let index = 1; index < windowRows.length; index += 1) {
    const currentTypical = (windowRows[index].high + windowRows[index].low + windowRows[index].close) / 3;
    const previousTypical = (windowRows[index - 1].high + windowRows[index - 1].low + windowRows[index - 1].close) / 3;
    const flow = currentTypical * (windowRows[index].volume || 0);
    if (currentTypical >= previousTypical) positiveFlow += flow;
    else negativeFlow += flow;
  }
  return negativeFlow ? 100 - (100 / (1 + positiveFlow / negativeFlow)) : (positiveFlow ? 100 : null);
}
function calculateFuturesRollingIndicatorSeries(rows = [], minRows = 2, resolver = () => null) {
  return rows.map((_, index) => (index + 1 >= minRows ? resolver(rows.slice(0, index + 1)) : null));
}
function calculateFuturesRsi(closes = [], period = 14) {
  if (closes.length <= period) return null;
  const changes = closes.slice(1).map((value, index) => value - closes[index]);
  const recent = changes.slice(-period);
  const gains = recent.map((value) => Math.max(value, 0));
  const losses = recent.map((value) => Math.max(-value, 0));
  const avgGain = averageFuturesValues(gains);
  const avgLoss = averageFuturesValues(losses);
  if (!Number.isFinite(avgGain) || !Number.isFinite(avgLoss)) return null;
  if (avgLoss === 0) return 100;
  return 100 - (100 / (1 + avgGain / avgLoss));
}
function calculateFuturesKd(rows = [], period = 9) {
  if (rows.length < period) return { k: null, d: null };
  let k = 50;
  let d = 50;
  for (let index = period - 1; index < rows.length; index += 1) {
    const windowRows = rows.slice(index - period + 1, index + 1);
    const high = Math.max(...windowRows.map((row) => row.high).filter(Number.isFinite));
    const low = Math.min(...windowRows.map((row) => row.low).filter(Number.isFinite));
    const close = rows[index]?.close;
    if (!Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close) || high === low) continue;
    const rsv = ((close - low) / (high - low)) * 100;
    k = (2 / 3) * k + (1 / 3) * rsv;
    d = (2 / 3) * d + (1 / 3) * k;
  }
  return { k, d };
}
function calculateFuturesAtr(rows = [], period = 14) {
  if (rows.length <= period) return null;
  const ranges = rows.slice(1).map((row, index) => {
    const previousClose = rows[index]?.close;
    if (![row.high, row.low, previousClose].every(Number.isFinite)) return null;
    return Math.max(row.high - row.low, Math.abs(row.high - previousClose), Math.abs(row.low - previousClose));
  }).filter(Number.isFinite);
  return averageFuturesValues(ranges.slice(-period));
}
function calculateFuturesCci(rows = [], period = 20) {
  if (rows.length < period) return null;
  const windowRows = rows.slice(-period);
  const typicalPrices = windowRows.map((row) => (row.high + row.low + row.close) / 3).filter(Number.isFinite);
  if (typicalPrices.length < period) return null;
  const mean = averageFuturesValues(typicalPrices);
  const meanDeviation = averageFuturesValues(typicalPrices.map((value) => Math.abs(value - mean)));
  const latest = typicalPrices.at(-1);
  return meanDeviation ? (latest - mean) / (0.015 * meanDeviation) : null;
}
function calculateFuturesWilliamsR(rows = [], period = 14) {
  if (rows.length < period) return null;
  const windowRows = rows.slice(-period);
  const high = Math.max(...windowRows.map((row) => row.high).filter(Number.isFinite));
  const low = Math.min(...windowRows.map((row) => row.low).filter(Number.isFinite));
  const close = windowRows.at(-1)?.close;
  return high !== low && Number.isFinite(close) ? ((high - close) / (high - low)) * -100 : null;
}
function calculateFuturesDmiAdx(rows = [], period = 14) {
  if (rows.length <= period * 2) return { plusDi: null, minusDi: null, adx: null };
  const points = [];
  for (let index = 1; index < rows.length; index += 1) {
    const current = rows[index];
    const previous = rows[index - 1];
    const upMove = current.high - previous.high;
    const downMove = previous.low - current.low;
    const plusDm = upMove > downMove && upMove > 0 ? upMove : 0;
    const minusDm = downMove > upMove && downMove > 0 ? downMove : 0;
    const tr = Math.max(current.high - current.low, Math.abs(current.high - previous.close), Math.abs(current.low - previous.close));
    points.push({ plusDm, minusDm, tr });
  }
  const recent = points.slice(-period);
  const trSum = recent.reduce((sum, row) => sum + row.tr, 0);
  if (!trSum) return { plusDi: null, minusDi: null, adx: null };
  const plusDi = recent.reduce((sum, row) => sum + row.plusDm, 0) / trSum * 100;
  const minusDi = recent.reduce((sum, row) => sum + row.minusDm, 0) / trSum * 100;
  const dxRows = points.slice(-period * 2).map((_, index, array) => {
    const windowRows = array.slice(Math.max(0, index - period + 1), index + 1);
    const windowTr = windowRows.reduce((sum, row) => sum + row.tr, 0);
    if (!windowTr) return null;
    const windowPlus = windowRows.reduce((sum, row) => sum + row.plusDm, 0) / windowTr * 100;
    const windowMinus = windowRows.reduce((sum, row) => sum + row.minusDm, 0) / windowTr * 100;
    return (Math.abs(windowPlus - windowMinus) / Math.max(windowPlus + windowMinus, 1)) * 100;
  }).filter(Number.isFinite);
  return { plusDi, minusDi, adx: averageFuturesValues(dxRows.slice(-period)) };
}
function calculateFuturesParabolicSar(rows = []) {
  if (rows.length < 4) return null;
  let bullish = rows[1].close >= rows[0].close;
  let sar = bullish ? rows[0].low : rows[0].high;
  let extreme = bullish ? rows[1].high : rows[1].low;
  let acceleration = 0.02;
  for (let index = 2; index < rows.length; index += 1) {
    const row = rows[index];
    sar += acceleration * (extreme - sar);
    if (bullish) {
      if (row.low < sar) {
        bullish = false;
        sar = extreme;
        extreme = row.low;
        acceleration = 0.02;
      } else if (row.high > extreme) {
        extreme = row.high;
        acceleration = Math.min(acceleration + 0.02, 0.2);
      }
    } else if (row.high > sar) {
      bullish = true;
      sar = extreme;
      extreme = row.high;
      acceleration = 0.02;
    } else if (row.low < extreme) {
      extreme = row.low;
      acceleration = Math.min(acceleration + 0.02, 0.2);
    }
  }
  return sar;
}
function buildFuturesTechnicalSnapshot(rows = []) {
  const cleanRows = rows.filter((row) => [row.open, row.high, row.low, row.close].every(Number.isFinite));
  const closes = cleanRows.map((row) => row.close);
  const highs = cleanRows.map((row) => row.high);
  const lows = cleanRows.map((row) => row.low);
  const volumes = cleanRows.map((row) => row.volume || 0);
  const latest = cleanRows.at(-1) || {};
  const maSeries = Object.fromEntries([5, 10, 20, 60, 120, 240].map((period) => [period, calculateFuturesRollingAverageSeries(closes, period)]));
  const ma = Object.fromEntries([5, 10, 20, 60, 120, 240].map((period) => [period, lastFiniteFuturesValue(maSeries[period])]));
  const ema12 = calculateFuturesEmaSeries(closes, 12);
  const ema26 = calculateFuturesEmaSeries(closes, 26);
  const macdRaw = closes.map((_, index) => (
    Number.isFinite(ema12[index]) && Number.isFinite(ema26[index]) ? ema12[index] - ema26[index] : null
  ));
  const macdRows = macdRaw.filter(Number.isFinite);
  const macdSignalRows = calculateFuturesEmaSeries(macdRows, 9);
  const macdHistogramRows = macdRows.map((value, index) => (
    Number.isFinite(value) && Number.isFinite(macdSignalRows[index]) ? value - macdSignalRows[index] : null
  ));
  const macd = lastFiniteFuturesValue(macdRows);
  const macdSignal = lastFiniteFuturesValue(macdSignalRows);
  const kdSeries = calculateFuturesKdSeries(cleanRows);
  const kd = { k: lastFiniteFuturesValue(kdSeries.k), d: lastFiniteFuturesValue(kdSeries.d) };
  const atrSeries = calculateFuturesRollingIndicatorSeries(cleanRows, 15, (windowRows) => calculateFuturesAtr(windowRows));
  const atr = calculateFuturesAtr(cleanRows);
  const cciSeries = calculateFuturesRollingIndicatorSeries(cleanRows, 20, (windowRows) => calculateFuturesCci(windowRows));
  const cci = calculateFuturesCci(cleanRows);
  const williamsRSeries = calculateFuturesRollingIndicatorSeries(cleanRows, 14, (windowRows) => calculateFuturesWilliamsR(windowRows));
  const williamsR = calculateFuturesWilliamsR(cleanRows);
  const dmi = calculateFuturesDmiAdx(cleanRows);
  const rsiSeries = calculateFuturesRsiSeries(closes);
  const rsi = lastFiniteFuturesValue(rsiSeries);
  const momentumSeries = closes.map((close, index) => (index >= 10 && Number.isFinite(close) && Number.isFinite(closes[index - 10]) ? close - closes[index - 10] : null));
  const momentum = lastFiniteFuturesValue(momentumSeries);
  const bias20Series = closes.map((close, index) => {
    const base = maSeries[20]?.[index];
    return Number.isFinite(close) && Number.isFinite(base) && base !== 0 ? ((close - base) / base) * 100 : null;
  });
  const bias20 = lastFiniteFuturesValue(bias20Series);
  const bollingerMid = ma[20];
  const bollingerSd = closes.length >= 20 ? Math.sqrt(averageFuturesValues(closes.slice(-20).map((value) => (value - bollingerMid) ** 2))) : null;
  const obvSeries = calculateFuturesObvSeries(cleanRows);
  const obv = lastFiniteFuturesValue(obvSeries);
  const mfiSeries = calculateFuturesRollingIndicatorSeries(cleanRows, 15, (windowRows) => calculateFuturesMfi(windowRows));
  const mfi = lastFiniteFuturesValue(mfiSeries);
  const vwapSeries = calculateFuturesVwapSeries(cleanRows);
  const vwapNumerator = cleanRows.slice(-40).reduce((sum, row) => sum + ((row.high + row.low + row.close) / 3) * (row.volume || 0), 0);
  const vwapDenominator = cleanRows.slice(-40).reduce((sum, row) => sum + (row.volume || 0), 0);
  const support20 = lows.length ? Math.min(...lows.slice(-20)) : null;
  const resistance20 = highs.length ? Math.max(...highs.slice(-20)) : null;
  const high60 = highs.length ? Math.max(...highs.slice(-60)) : null;
  const low60 = lows.length ? Math.min(...lows.slice(-60)) : null;
  const fib38 = Number.isFinite(high60) && Number.isFinite(low60) ? high60 - (high60 - low60) * 0.382 : null;
  const fib62 = Number.isFinite(high60) && Number.isFinite(low60) ? high60 - (high60 - low60) * 0.618 : null;
  const tenkan = highs.length >= 9 && lows.length >= 9 ? (Math.max(...highs.slice(-9)) + Math.min(...lows.slice(-9))) / 2 : null;
  const kijun = highs.length >= 26 && lows.length >= 26 ? (Math.max(...highs.slice(-26)) + Math.min(...lows.slice(-26))) / 2 : null;
  const senkouB = highs.length >= 52 && lows.length >= 52 ? (Math.max(...highs.slice(-52)) + Math.min(...lows.slice(-52))) / 2 : null;
  const openInterestSeries = cleanRows.map((row) => parseMarketNumber(row.openInterest));
  const openInterest = openInterestSeries.filter(Number.isFinite);
  const oiChange = openInterest.length >= 2 ? openInterest.at(-1) - openInterest.at(-2) : null;
  const oiChangeSeries = openInterestSeries.map((value, index) => (
    index > 0 && Number.isFinite(value) && Number.isFinite(openInterestSeries[index - 1]) ? value - openInterestSeries[index - 1] : null
  ));
  const buckets = [];
  if (Number.isFinite(high60) && Number.isFinite(low60) && high60 !== low60) {
    const bucketCount = 6;
    for (let index = 0; index < bucketCount; index += 1) buckets.push({ volume: 0, low: low60 + ((high60 - low60) / bucketCount) * index, high: low60 + ((high60 - low60) / bucketCount) * (index + 1) });
    cleanRows.slice(-60).forEach((row) => {
      const bucketIndex = Math.min(bucketCount - 1, Math.max(0, Math.floor(((row.close - low60) / (high60 - low60)) * bucketCount)));
      buckets[bucketIndex].volume += row.volume || 0;
    });
  }
  const pointOfControl = buckets.length ? buckets.slice().sort((left, right) => right.volume - left.volume)[0] : null;
  const deltaVolumeSeries = cleanRows.map((row) => (row.close >= row.open ? row.volume || 0 : -(row.volume || 0)));
  const deltaVolume = deltaVolumeSeries.slice(-20).reduce((sum, value) => sum + value, 0);
  return {
    ma,
    macd,
    macdSignal,
    rsi,
    kd,
    atr,
    cci,
    williamsR,
    dmi,
    bias20,
    momentum,
    bollinger: {
      mid: bollingerMid,
      upper: Number.isFinite(bollingerMid) && Number.isFinite(bollingerSd) ? bollingerMid + bollingerSd * 2 : null,
      lower: Number.isFinite(bollingerMid) && Number.isFinite(bollingerSd) ? bollingerMid - bollingerSd * 2 : null,
    },
    obv,
    mfi,
    sar: calculateFuturesParabolicSar(cleanRows),
    ichimoku: { tenkan, kijun, senkouB },
    support20,
    resistance20,
    fib38,
    fib62,
    vwap: vwapDenominator ? vwapNumerator / vwapDenominator : null,
    pointOfControl,
    deltaVolume,
    openInterest: openInterest.at(-1),
    oiChange,
    count: cleanRows.length,
    series: {
      close: closes,
      volume: volumes,
      ma: maSeries,
      macd: {
        dif: macdRows,
        signal: macdSignalRows,
        histogram: macdHistogramRows,
      },
      rsi: rsiSeries,
      kd: kdSeries,
      atr: atrSeries,
      cci: cciSeries,
      williamsR: williamsRSeries,
      bias20: bias20Series,
      momentum: momentumSeries,
      obv: obvSeries,
      mfi: mfiSeries,
      vwap: vwapSeries,
      deltaVolume: deltaVolumeSeries,
      openInterest: openInterestSeries,
      oiChange: oiChangeSeries,
      support20: Array(closes.length).fill(support20),
      resistance20: Array(closes.length).fill(resistance20),
      fib38: Array(closes.length).fill(fib38),
      fib62: Array(closes.length).fill(fib62),
    },
  };
}
function parseRocDate(value) {
  const str = String(value || "").trim();
  // ISO format: YYYY-MM-DD (e.g. "2026-05-27")
  const isoMatch = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const d = new Date(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3]));
    return Number.isNaN(d.getTime()) ? null : d;
  }
  // ISO week format from futures aggregation: YYYY-WNN.
  const weekMatch = str.match(/^(\d{4})-W(\d{2})$/i);
  if (weekMatch) {
    const year = Number(weekMatch[1]);
    const week = Number(weekMatch[2]);
    if (!Number.isFinite(year) || !Number.isFinite(week) || week < 1 || week > 53) return null;
    const jan4 = new Date(year, 0, 4);
    const weekStart = new Date(jan4);
    weekStart.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7) + (week - 1) * 7);
    return Number.isNaN(weekStart.getTime()) ? null : weekStart;
  }
  // Month format from futures aggregation: YYYY-MM.
  const monthMatch = str.match(/^(\d{4})-(\d{2})$/);
  if (monthMatch) {
    const d = new Date(Number(monthMatch[1]), Number(monthMatch[2]) - 1, 1);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  // ROC format: YYY/MM/DD (e.g. "115/06/09")
  const parts = str.split("/").map((part) => Number(part));
  if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part))) return null;
  // Guard: if first part looks like a 4-digit western year, treat as western
  const year = parts[0] > 1900 ? parts[0] : parts[0] + 1911;
  const d = new Date(year, parts[1] - 1, parts[2]);
  return Number.isNaN(d.getTime()) ? null : d;
}
function isValidTechnicalOhlc(open, high, low, close) {
  const values = [open, high, low, close];
  if (!values.every((value) => Number.isFinite(value) && value > 0)) return false;
  return high >= Math.max(open, close) && low <= Math.min(open, close);
}
function normalizeHistory(detail) {
  return (detail.historyDays || [])
    .map((day) => {
      const close = parseMarketNumber(day.close);
      const open = parseMarketNumber(day.open);
      const rawHigh = parseMarketNumber(day.high);
      const rawLow = parseMarketNumber(day.low);
      if (!isValidTechnicalOhlc(open, rawHigh, rawLow, close)) return null;
      return {
        date: day.date,
        parsedDate: parseRocDate(day.date),
        open,
        high: rawHigh,
        low: rawLow,
        close,
        change: parseMarketNumber(day.change),
        volume: Math.max(parseMarketNumber(day.volume) || 0, 0),
      };
    })
    .filter((day) => day && day.parsedDate !== null);
}
function exponentialMovingAverage(values, windowSize) {
  const multiplier = 2 / (windowSize + 1);
  let previous = null;
  return values.map((value, index) => {
    if (value === null) return null;
    if (previous === null) {
      const slice = values.slice(Math.max(0, index - windowSize + 1), index + 1).filter((item) => item !== null);
      previous = slice.reduce((sum, item) => sum + item, 0) / slice.length;
      return previous;
    }
    previous = (value - previous) * multiplier + previous;
    return previous;
  });
}
function calculateKd(history, period = 9) {
  let k = 50;
  let d = 50;
  return history.map((day, index) => {
    const slice = history.slice(Math.max(0, index - period + 1), index + 1);
    const high = Math.max(...slice.map((item) => item.high ?? item.close));
    const low = Math.min(...slice.map((item) => item.low ?? item.close));
    const rsv = high === low ? 50 : ((day.close - low) / (high - low)) * 100;
    k = (k * 2 + rsv) / 3;
    d = (d * 2 + k) / 3;
    return { k, d };
  });
}
function calculateMacd(history) {
  const closes = history.map((day) => day.close);
  const ema12 = exponentialMovingAverage(closes, 12);
  const ema26 = exponentialMovingAverage(closes, 26);
  const dif = closes.map((_, index) => (
    ema12[index] === null || ema26[index] === null ? null : ema12[index] - ema26[index]
  ));
  const macd = exponentialMovingAverage(dif, 9);
  return dif.map((value, index) => ({
    dif: value,
    macd: macd[index],
    osc: value === null || macd[index] === null ? null : (value - macd[index]) * 2,
  }));
}
function calculateRsi(history, period = 14) {
  return history.map((day, index) => {
    if (index === 0) return null;
    const start = Math.max(1, index - period + 1);
    const changes = history.slice(start, index + 1).map((item, itemIndex, items) => {
      const previousIndex = start + itemIndex - 1;
      const previous = history[previousIndex]?.close ?? items[itemIndex - 1]?.close ?? item.close;
      return item.close - previous;
    });
    const gains = changes.map((change) => Math.max(change, 0));
    const losses = changes.map((change) => Math.abs(Math.min(change, 0)));
    const averageGain = gains.reduce((sum, value) => sum + value, 0) / changes.length;
    const averageLoss = losses.reduce((sum, value) => sum + value, 0) / changes.length;
    if (averageLoss === 0) return 100;
    const rs = averageGain / averageLoss;
    return 100 - (100 / (1 + rs));
  });
}
function calculateBias(history, period = 6) {
  const closes = history.map((day) => day.close);
  const ma = movingAverage(closes, period);
  return closes.map((close, index) => (
    ma[index] === null || ma[index] === 0 ? null : ((close - ma[index]) / ma[index]) * 100
  ));
}
function calculateDmi(history, period = 14) {
  let smoothedTr = 0;
  let smoothedPlusDm = 0;
  let smoothedMinusDm = 0;
  let adx = null;
  const dxValues = [];

  return history.map((day, index) => {
    if (index === 0) return { plusDi: null, minusDi: null, adx: null };
    const previous = history[index - 1];
    const high = day.high ?? day.close;
    const low = day.low ?? day.close;
    const previousHigh = previous.high ?? previous.close;
    const previousLow = previous.low ?? previous.close;
    const trueRange = Math.max(
      high - low,
      Math.abs(high - previous.close),
      Math.abs(low - previous.close),
    );
    const upMove = high - previousHigh;
    const downMove = previousLow - low;
    const plusDm = upMove > downMove && upMove > 0 ? upMove : 0;
    const minusDm = downMove > upMove && downMove > 0 ? downMove : 0;

    if (index <= period) {
      smoothedTr += trueRange;
      smoothedPlusDm += plusDm;
      smoothedMinusDm += minusDm;
    } else {
      smoothedTr = smoothedTr - smoothedTr / period + trueRange;
      smoothedPlusDm = smoothedPlusDm - smoothedPlusDm / period + plusDm;
      smoothedMinusDm = smoothedMinusDm - smoothedMinusDm / period + minusDm;
    }
    if (index < period || smoothedTr === 0) {
      return { plusDi: null, minusDi: null, adx: null };
    }

    const plusDi = (smoothedPlusDm / smoothedTr) * 100;
    const minusDi = (smoothedMinusDm / smoothedTr) * 100;
    const denominator = plusDi + minusDi;
    const dx = denominator === 0 ? 0 : (Math.abs(plusDi - minusDi) / denominator) * 100;
    dxValues.push(dx);
    if (dxValues.length === period) {
      adx = dxValues.reduce((sum, value) => sum + value, 0) / period;
    } else if (dxValues.length > period && adx !== null) {
      adx = ((adx * (period - 1)) + dx) / period;
    }
    return { plusDi, minusDi, adx };
  });
}
function calculateObv(history) {
  let obv = 0;
  return history.map((day, index) => {
    if (index > 0) {
      if (day.close > history[index - 1].close) obv += day.volume || 0;
      if (day.close < history[index - 1].close) obv -= day.volume || 0;
    }
    return obv;
  });
}
function calculateAtr(history, period = 14) {
  const ranges = history.map((day, index) => {
    if (index === 0) return null;
    const previous = history[index - 1];
    const high = day.high ?? day.close;
    const low = day.low ?? day.close;
    return Math.max(high - low, Math.abs(high - previous.close), Math.abs(low - previous.close));
  });
  return ranges.map((_, index) => {
    if (index < period) return null;
    const window = ranges.slice(index - period + 1, index + 1).filter(Number.isFinite);
    return window.length === period ? window.reduce((sum, value) => sum + value, 0) / period : null;
  });
}
function calculateCci(history, period = 20) {
  const typicalPrices = history.map((day) => ((day.high ?? day.close) + (day.low ?? day.close) + day.close) / 3);
  return typicalPrices.map((typical, index) => {
    if (index + 1 < period) return null;
    const window = typicalPrices.slice(index - period + 1, index + 1).filter(Number.isFinite);
    if (window.length < period) return null;
    const average = window.reduce((sum, value) => sum + value, 0) / period;
    const meanDeviation = window.reduce((sum, value) => sum + Math.abs(value - average), 0) / period;
    return meanDeviation ? (typical - average) / (0.015 * meanDeviation) : null;
  });
}
function calculateWilliamsR(history, period = 14) {
  return history.map((day, index) => {
    if (index + 1 < period) return null;
    const window = history.slice(index - period + 1, index + 1);
    const highest = Math.max(...window.map((item) => item.high ?? item.close).filter(Number.isFinite));
    const lowest = Math.min(...window.map((item) => item.low ?? item.close).filter(Number.isFinite));
    return highest !== lowest ? ((highest - day.close) / (highest - lowest)) * -100 : null;
  });
}
function calculateMfi(history, period = 14) {
  const typicalPrices = history.map((day) => ((day.high ?? day.close) + (day.low ?? day.close) + day.close) / 3);
  const flows = history.map((day, index) => ({
    typical: typicalPrices[index],
    flow: typicalPrices[index] * (day.volume || 0),
  }));
  return flows.map((row, index) => {
    if (index < period) return null;
    let positiveFlow = 0;
    let negativeFlow = 0;
    for (let cursor = index - period + 1; cursor <= index; cursor += 1) {
      const current = flows[cursor];
      const previous = flows[cursor - 1];
      if (!current || !previous) continue;
      if (current.typical >= previous.typical) positiveFlow += current.flow;
      else negativeFlow += current.flow;
    }
    if (!negativeFlow) return positiveFlow ? 100 : null;
    return 100 - (100 / (1 + positiveFlow / negativeFlow));
  });
}
function calculateMomentum(history, period = 10) {
  return history.map((day, index) => (
    index >= period && Number.isFinite(history[index - period]?.close) ? day.close - history[index - period].close : null
  ));
}
function calculateParabolicSarSeries(history) {
  const result = Array(history.length).fill(null);
  if (history.length < 4) return result;
  let bullish = history[1].close >= history[0].close;
  let sar = bullish ? history[0].low : history[0].high;
  let extreme = bullish ? history[1].high : history[1].low;
  let acceleration = 0.02;
  result[1] = sar;
  for (let index = 2; index < history.length; index += 1) {
    const row = history[index];
    sar += acceleration * (extreme - sar);
    if (bullish) {
      if (row.low < sar) {
        bullish = false;
        sar = extreme;
        extreme = row.low;
        acceleration = 0.02;
      } else if (row.high > extreme) {
        extreme = row.high;
        acceleration = Math.min(acceleration + 0.02, 0.2);
      }
    } else if (row.high > sar) {
      bullish = true;
      sar = extreme;
      extreme = row.high;
      acceleration = 0.02;
    } else if (row.low < extreme) {
      extreme = row.low;
      acceleration = Math.min(acceleration + 0.02, 0.2);
    }
    result[index] = sar;
  }
  return result;
}
function calculateIchimoku(history) {
  const midpoint = (window) => {
    const highs = window.map((item) => item.high ?? item.close).filter(Number.isFinite);
    const lows = window.map((item) => item.low ?? item.close).filter(Number.isFinite);
    return highs.length && lows.length ? (Math.max(...highs) + Math.min(...lows)) / 2 : null;
  };
  return history.map((_, index) => {
    const tenkan = index + 1 >= 9 ? midpoint(history.slice(index - 8, index + 1)) : null;
    const kijun = index + 1 >= 26 ? midpoint(history.slice(index - 25, index + 1)) : null;
    const senkouB = index + 1 >= 52 ? midpoint(history.slice(index - 51, index + 1)) : null;
    return { tenkan, kijun, senkouB };
  });
}

/* shadow-input:js/render-shared.js */
function renderSharedNavigation() {
  const BRAND_TEXT = "Market Pulse";
  const NAV_LINKS = [
    ["market-overview.html", "台股盤勢"],
    ["tw-stocks.html", "台股類股"],
    ["tw-etf.html", "台股 ETF"],
    ["tw-stock-search.html", "個股搜尋"],
    ["tw-Optional-stocks.html", "自選股"],
    ["us-market-overview.html", "美股盤勢"],
    ["us-stocks.html", "美股市場"],
    ["us-etf.html", "美股ETF"],
    ["us-stock-search.html", "美股搜尋"],
    ["us-watchlist.html", "美股自選"],
    ["international-finance.html", "貴金屬與債券"],
    ["bonds.html", "債券"],
    ["precious-metals.html", "貴金屬"],
    ["derivatives-assets.html", "期權"],
    ["futures.html", "期貨"],
    ["options.html", "選擇權"],
    ["derivatives-analytics.html", "期權分析"],
    ["derivatives-status.html", "系統維護"],
  ];
  const current = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".navbar").forEach((nav) => {
    const brandLabel = nav.querySelector(".brand span:last-child");
    if (brandLabel) brandLabel.textContent = BRAND_TEXT;
    const links = nav.querySelector(".nav-links");
    if (!links) return;
    links.innerHTML = "";
    NAV_LINKS.forEach(([href, label]) => {
      const link = document.createElement("a");
      link.href = href;
      link.textContent = label;
      if (href === current) link.classList.add("is-active");
      links.appendChild(link);
    });
  });
}
function isExcludedSector(sector) {
  if (!sector) return false;
  return EXCLUDED_SECTOR_SOURCE_NAMES.has(sector.sourceName) || EXCLUDED_SECTOR_SOURCE_NAMES.has(sector.name);
}
function sectorMatchesAnyLabel(sector, labels) {
  if (!sector || !labels || !labels.length) return false;
  const candidates = [sector.sourceName, sector.name].filter(Boolean);
  return candidates.some((value) => labels.has(value));
}
function normalizeSectorSummaryItem(item, fallbackName) {
  return {
    name: item.name || fallbackName,
    value: item.value || "--",
    change: item.change || "--",
    pct: item.pct || "--",
    tone: item.tone || "flat",
    volume: item.volume || "--",
    turnover: item.turnover || "--",
    trades: item.trades || "--",
    hideTrades: Boolean(item.hideTrades),
    note: String(item.note || "").replace("Yahoo奇摩股市同步資料", "同步資料"),
    sourceName: item.sourceName || item.name || fallbackName,
    exchange: item.exchange || "",
    open: item.open || "--",
    high: item.high || "--",
    low: item.low || "--",
    previousClose: item.previousClose || "--",
    time: item.time || "--",
    candles: item.candles || [],
    comparisonSeries: item.comparisonSeries || { day: [] },
    benchmarkComparisonSeries: item.benchmarkComparisonSeries || { day: [] },
    technicalAnalysis: item.technicalAnalysis || {},
    chartIntervals: item.chartIntervals || {},
    summaryOnly: item.summaryOnly !== undefined ? item.summaryOnly : true,
  };
}
function renderSectorStockName(item) {
  const symbol = String(item.sourceName || "").trim();
  const match = symbol.match(/^([0-9A-Z]+)\.(TW|TWO)$/i);
  if (!match) return `<span class="class-name-cell">${escapeHtml(item.name)}</span>`;
  const code = match[1];
  const market = match[2].toUpperCase() === "TW" ? "TWSE" : "TPEX";
  const href = `tw-stock-search.html?q=${encodeURIComponent(code)}&market=${encodeURIComponent(market)}`;
  return `<a class="class-name-cell class-stock-link" href="${safeUrl(href)}" title="查看 ${escapeHtml(item.name)} 個股詳情">${escapeHtml(item.name)}</a>`;
}
function sectorSortValue(item, key) {
  if (key === "name_asc") return String(item.name || "");
  if (key === "volume_desc") return parseMarketNumber(item.volumeValue ?? item.volume);
  if (key === "turnover_desc") return parseMarketNumber(item.turnoverValue ?? item.turnover);
  if (key === "change_desc") return parseMarketNumber(item.change);
  return parseMarketNumber(item.pct);
}
function sortSectorItemsByActiveMode(items) {
  const key = sectorSortState.key || "source_order";
  if (key === "source_order") return [...(items || [])];
  return [...(items || [])].sort((left, right) => {
    if (key === "name_asc") {
      return String(left.name || "").localeCompare(String(right.name || ""), "zh-Hant");
    }
    const leftValue = sectorSortValue(left, key);
    const rightValue = sectorSortValue(right, key);
    const leftFinite = Number.isFinite(leftValue);
    const rightFinite = Number.isFinite(rightValue);
    if (leftFinite && rightFinite && leftValue !== rightValue) return rightValue - leftValue;
    if (leftFinite !== rightFinite) return leftFinite ? -1 : 1;
    return String(left.name || "").localeCompare(String(right.name || ""), "zh-Hant");
  });
}
function renderSectorSortControl() {
  const options = [
    ["source_order", "\u9810\u8a2d\u9806\u5e8f"],
    ["pct_desc", "\u6f32\u8dcc\u5e45\u9ad8\u5230\u4f4e"],
    ["change_desc", "\u6f32\u8dcc\u9ad8\u5230\u4f4e"],
    ["volume_desc", "\u6210\u4ea4\u91cf\u9ad8\u5230\u4f4e"],
    ["turnover_desc", "\u6210\u4ea4\u91d1\u984d\u9ad8\u5230\u4f4e"],
    ["name_asc", "\u540d\u7a31 A-Z"],
  ];
  return `
    <div class="sector-sort-toolbar">
      <label for="sector-sort-select">\u985e\u80a1\u6392\u5e8f</label>
      <select id="sector-sort-select" data-sector-sort>
        ${options.map(([value, label]) => `<option value="${value}" ${value === sectorSortState.key ? "selected" : ""}>${label}</option>`).join("")}
      </select>
    </div>
  `;
}
function renderScrollableClassTable(content, label = "類股排行表格") {
  return `
    <div class="class-table-scroll" tabindex="0" role="region" aria-label="${escapeHtml(label)}">
      ${content}
    </div>
  `;
}
function getSectorPageGroups() {
  const sectors = (data.sectors || []).filter((sector) => !isExcludedSector(sector));
  const yahooGroups = data.yahooSectorGroups || {};
  const yahooCatalog = data.yahooSectorCatalog || {};
  const yahooItems = (key, fallbackName) =>
    (yahooGroups[key] || []).map((item) => normalizeSectorSummaryItem(item, fallbackName));
  const listedYahoo = yahooItems("listed", "Listed");
  const otcYahoo = yahooItems("otc", "OTC");
  const emergingYahoo = yahooItems("emerging", "Emerging");
  const electronicYahoo = yahooItems("electronic", "Electronic");
  const conceptYahoo = yahooItems("concept", "Concept");
  const groupYahoo = yahooItems("group", "Group");
  const activeYahooItems = (key, fallbackItems) => {
    const active = activeYahooSectorCategories[key];
    if (!active) return fallbackItems;
    return (yahooSectorQuoteCache.get(`${key}:${active.index}`)?.items || []).map((item) =>
      normalizeSectorSummaryItem(item, active.name),
    );
  };
  const listedActive = Boolean(activeYahooSectorCategories.listed);
  const listed = activeYahooItems("listed", sectors);
  const electronicSet = new Set(["\u534a\u5c0e\u9ad4", "\u96fb\u8166\u9031\u908a", "\u5149\u96fb", "\u901a\u8a0a\u7db2\u8def", "\u96fb\u5b50\u96f6\u7d44\u4ef6", "\u96fb\u5b50\u901a\u8def", "\u8cc7\u8a0a\u670d\u52d9", "\u5176\u4ed6\u96fb\u5b50", "\u96fb\u5b50", "\u96fb\u5b50\u7522\u696d"]);
  const conceptSet = new Set(["\u904b\u52d5\u4f11\u9592", "\u5c45\u5bb6\u751f\u6d3b", "\u6578\u4f4d\u96f2\u7aef", "\u7da0\u80fd\u74b0\u4fdd", "\u6982\u5ff5\u80a1", "\u6982\u5ff5"]);
  const electronic = activeYahooItems("electronic", electronicYahoo.length
    ? electronicYahoo
    : sectors.filter((sector) => sectorMatchesAnyLabel(sector, electronicSet)));
  const concept = activeYahooItems("concept", conceptYahoo.length
    ? conceptYahoo
    : sectors.filter((sector) => sectorMatchesAnyLabel(sector, conceptSet)));
  const grouped = activeYahooItems("group", groupYahoo.length ? groupYahoo : [...sectors]
    .sort((left, right) => (parseMarketNumber(right.volume) || 0) - (parseMarketNumber(left.volume) || 0))
    .slice(0, 12));
  const tpexHighlights = data.tpexHighlights || {};
  const otc = activeYahooItems("otc", otcYahoo.length
    ? otcYahoo
    : (tpexHighlights.mainboard || []).map((item) => normalizeSectorSummaryItem(item, "OTC")));
  const emerging = activeYahooItems("emerging", emergingYahoo.length
    ? emergingYahoo
    : [...(tpexHighlights.emerging || []), ...(tpexHighlights.emergingStats || [])].map((item) =>
        normalizeSectorSummaryItem(item, "Emerging"),
      ));

  return [
    { key: "listed", label: "上市類股", kind: listedActive ? "summary" : "sector", source: listedActive ? "Yahoo奇摩股市" : "證交所", items: listed, catalog: yahooCatalog.listed || [] },
    { key: "otc", label: "上櫃類股", kind: "summary", source: "Yahoo奇摩股市", items: otc, catalog: yahooCatalog.otc || [] },
    { key: "emerging", label: "興櫃類股", kind: "summary", source: "Yahoo奇摩股市", items: emerging, catalog: yahooCatalog.emerging || [] },
    { key: "electronic", label: "電子產業", kind: electronicYahoo.length ? "summary" : "sector", source: electronicYahoo.length ? "Yahoo奇摩股市" : "證交所", items: electronic, catalog: yahooCatalog.electronic || [] },
    { key: "concept", label: "概念股", kind: conceptYahoo.length ? "summary" : "sector", source: conceptYahoo.length ? "Yahoo奇摩股市" : "證交所", items: concept, catalog: yahooCatalog.concept || [] },
    { key: "group", label: "集團股", kind: groupYahoo.length ? "summary" : "sector", source: groupYahoo.length ? "Yahoo奇摩股市" : "證交所", items: grouped, catalog: yahooCatalog.group || [] },
  ];
}
function buildTechnicalTrendSummary(detail, technicalTheory) {
  const theorySignals = Array.isArray(technicalTheory?.theorySignals) ? technicalTheory.theorySignals : [];
  const priceIndicators = Array.isArray(technicalTheory?.priceIndicators) ? technicalTheory.priceIndicators : [];
  const volumeIndicators = Array.isArray(technicalTheory?.volumeIndicators) ? technicalTheory.volumeIndicators : [];
  const breadthIndicators = Array.isArray(technicalTheory?.breadthIndicators) ? technicalTheory.breadthIndicators : [];
  const allSignals = [...theorySignals, ...priceIndicators, ...volumeIndicators, ...breadthIndicators];
  const bullish = allSignals.filter((item) => item.direction === "bullish").length;
  const bearish = allSignals.filter((item) => item.direction === "bearish").length;
  const neutral = allSignals.length - bullish - bearish;
  const netSignal = bullish - bearish;
  const backtest = technicalTheory?.backtestLearning || {};
  const framework = backtest.institutionalFramework || {};
  const forecast = backtest.forecast || {};
  const validation = backtest.validation || {};
  const movingAverage = priceIndicators.find((item) => item.movingAverage)?.movingAverage || null;
  const score = Number(technicalTheory?.score || 0);
  const combinedScore = Number.isFinite(framework.totalScore)
    ? Math.round((Math.max(0, Math.min(100, 50 + score * 2.6)) * 0.55) + (framework.totalScore * 0.45))
    : Math.round(Math.max(0, Math.min(100, 50 + score * 2.8)));
  const tone = combinedScore >= 65 || netSignal >= 5
    ? "bullish"
    : combinedScore <= 35 || netSignal <= -5
      ? "bearish"
      : "neutral";
  const label = combinedScore >= 75
    ? "多方風向"
    : combinedScore >= 60
      ? "偏多風向"
      : combinedScore > 40
        ? "震盪整理"
        : combinedScore >= 25
          ? "偏空風向"
          : "空方風向";

  const periodMap = new Map((movingAverage?.periods || []).map((item) => [item.period, item]));
  const periodDirection = (periods) => {
    const items = periods.map((period) => periodMap.get(period)).filter(Boolean);
    if (!items.length) return "資料不足";
    const positive = items.filter((item) => item.slope === "向上" && item.position === "股價在上").length;
    const negative = items.filter((item) => item.slope === "向下" && item.position === "股價在下").length;
    if (positive > negative) return "偏多";
    if (negative > positive) return "偏空";
    return "整理";
  };
  const timeframes = [
    { label: "短線", value: periodDirection([5, 10, 20]) },
    { label: "中期", value: periodDirection([20, 60, 120]) },
    { label: "長期", value: periodDirection([120, 240]) },
  ];
  const confirmations = [
    movingAverage ? `均線：${movingAverage.headline}；${movingAverage.confirmations?.[0] || movingAverage.text}` : "",
    technicalTheory.indicatorSummary ? `價量：${technicalTheory.indicatorSummary}` : "",
    technicalTheory.breadthSummary ? `市場與籌碼：${technicalTheory.breadthSummary}` : "",
    Number.isFinite(framework.totalScore)
      ? `多因子：${framework.totalScore} 分，${framework.judgement?.label || "中性"}`
      : "",
    backtest.summary ? `回測：${backtest.summary}` : "",
  ].filter(Boolean);
  const risks = [];
  if (technicalTheory.priceVolumeConflict) risks.push("價格指標與量能方向背離");
  if (technicalTheory.breadthConflict) risks.push("市場廣度或籌碼與技術方向衝突");
  if (validation.status === "watch") risks.push("回測模型出現輕微失真");
  if (validation.status === "recalibrate") risks.push("回測模型需重新校準參數");
  if (validation.status === "rebuild") risks.push("回測模型失真，暫停提高訊號權重");
  if (Number.isFinite(forecast.atrPct) && forecast.atrPct >= 5) risks.push(`ATR ${forecast.atrPct.toFixed(2)}%，波動偏高`);
  if (movingAverage?.risks?.length) risks.push(...movingAverage.risks.slice(0, 2));
  if (!risks.length) risks.push("目前未見重大技術衝突，但仍須以停損與部位管理控制風險");

  const forecastScenarios = Array.isArray(forecast.scenarios) ? forecast.scenarios : [];
  const forecastTargets = Array.isArray(forecast.priceTargets)
    ? forecast.priceTargets.filter((item) => (
        item
        && Number.isFinite(item.lower)
        && Number.isFinite(item.upper)
        && Number.isFinite(item.median)
        && Number.isFinite(item.expectedReturnPct)
      ))
    : [];
  const pickPreferredForecastRows = (items) => {
    const preferredDays = [5, 20, 60];
    const picked = preferredDays
      .map((days) => items.find((item) => Number(item.days) === days))
      .filter(Boolean);
    const remaining = items.filter((item) => !picked.includes(item));
    return [...picked, ...remaining].slice(0, 3);
  };
  const visibleScenarios = pickPreferredForecastRows(forecastScenarios);
  const visibleTargets = pickPreferredForecastRows(forecastTargets);
  const primaryTarget = forecastTargets.find((item) => Number(item.days) === 20)
    || forecastTargets.find((item) => Number(item.days) === 60)
    || forecastTargets[0]
    || null;
  const primaryScenario = primaryTarget
    ? forecastScenarios.find((item) => Number(item.days) === Number(primaryTarget.days))
    : forecastScenarios.find((item) => Number(item.days) === 20) || forecastScenarios[0] || null;
  const forecastBiasText = primaryScenario
    ? `多方 ${Number.isFinite(primaryScenario.bullish) ? primaryScenario.bullish : "--"}%、震盪 ${Number.isFinite(primaryScenario.neutral) ? primaryScenario.neutral : "--"}%、空方 ${Number.isFinite(primaryScenario.bearish) ? primaryScenario.bearish : "--"}%`
    : "情境比例不足";
  const priceForecastText = primaryTarget
    ? `${primaryTarget.label || `${primaryTarget.days} 日`}預估中位 ${primaryTarget.median.toFixed(2)}，區間 ${primaryTarget.lower.toFixed(2)} ~ ${primaryTarget.upper.toFixed(2)}，預估報酬 ${primaryTarget.expectedReturnPct >= 0 ? "+" : ""}${primaryTarget.expectedReturnPct.toFixed(2)}%。`
    : "歷史序列或回測樣本不足，暫不輸出預估價格區間。";
  const forecastSummary = forecast.summary
    ? `${forecast.summary} ${priceForecastText}`
    : priceForecastText;

  const supportText = Number.isFinite(forecast.support) ? forecast.support.toFixed(2) : "--";
  const resistanceText = Number.isFinite(forecast.resistance) ? forecast.resistance.toFixed(2) : "--";
  const action = tone === "bullish"
    ? `風向偏多，優先等回測支撐 ${supportText} 或量價續強再分批布局；接近壓力 ${resistanceText} 避免追高。${primaryTarget ? ` 參考${primaryTarget.label || "預估"}中位 ${primaryTarget.median.toFixed(2)}。` : ""}`
    : tone === "bearish"
      ? `風向偏空，反彈至壓力 ${resistanceText} 仍需保守，跌破支撐 ${supportText} 應優先控管回撤。${primaryTarget ? ` 預估區間先看 ${primaryTarget.lower.toFixed(2)} ~ ${primaryTarget.upper.toFixed(2)}。` : ""}`
      : `多空訊號分歧，暫以 ${supportText} 至 ${resistanceText} 區間觀察，等待均線、量能與籌碼同向表態。${primaryTarget ? ` 預估中位 ${primaryTarget.median.toFixed(2)} 僅作區間參考。` : ""}`;

  return {
    tone,
    label,
    score: combinedScore,
    summary: `${detail.code || ""} ${detail.name || ""} 綜合 ${allSignals.length} 項技術訊號：偏多 ${bullish}、偏空 ${bearish}、中性 ${neutral}；目前判定為${label}，預測走勢為${forecast.trendLabel || "區間震盪"}。`,
    timeframes,
    confirmations: confirmations.slice(0, 5),
    risks: [...new Set(risks)].slice(0, 4),
    action,
    confidence: technicalTheory.adaptiveConfidence || "低",
    forecast: {
      confidence: forecast.confidence || technicalTheory.adaptiveConfidence || "低",
      trendLabel: forecast.trendLabel || "區間震盪",
      summary: forecastSummary,
      support: forecast.support,
      resistance: forecast.resistance,
      atrPct: forecast.atrPct,
      scenarios: visibleScenarios,
      priceTargets: visibleTargets,
      primaryTarget,
      primaryScenario,
      forecastBiasText,
      caveat: forecast.caveat || "預測價格為區間模型估算，不是保證價格或投資建議。",
    },
  };
}
function renderTechnicalTrendForecastSummary(technicalTrendSummary, options = {}) {
  const forecast = technicalTrendSummary?.forecast || {};
  const assetLabel = options.assetLabel || "股價";
  const titleText = options.title || `預測${assetLabel}與走勢`;
  const targetTitle = options.targetTitle || `預估${assetLabel}區間`;
  const scenarios = Array.isArray(forecast.scenarios) ? forecast.scenarios : [];
  const priceTargets = Array.isArray(forecast.priceTargets) ? forecast.priceTargets : [];
  const supportText = Number.isFinite(forecast.support) ? forecast.support.toFixed(2) : "--";
  const resistanceText = Number.isFinite(forecast.resistance) ? forecast.resistance.toFixed(2) : "--";
  const atrText = Number.isFinite(forecast.atrPct) ? `${forecast.atrPct.toFixed(2)}%` : "--";
  if (!scenarios.length && !priceTargets.length) {
    return `
      <div class="technical-summary-forecast">
        <div class="technical-summary-forecast-head">
          <div>
            <span>Forecast path</span>
            <strong>${escapeHtml(titleText)}</strong>
          </div>
          <small>信心 ${escapeHtml(forecast.confidence || "低")} · ${escapeHtml(forecast.trendLabel || "區間震盪")}</small>
        </div>
        <p>${escapeHtml(forecast.summary || `歷史資料不足，暫不輸出預測${assetLabel}與走勢區間。`)}</p>
      </div>
    `;
  }
  return `
    <div class="technical-summary-forecast">
      <div class="technical-summary-forecast-head">
        <div>
          <span>Forecast path</span>
          <strong>${escapeHtml(titleText)}</strong>
        </div>
        <small>信心 ${escapeHtml(forecast.confidence || "低")} · ${escapeHtml(forecast.trendLabel || "區間震盪")}</small>
      </div>
      <p>${escapeHtml(forecast.summary || "以情境機率、ATR、支撐壓力與回測平均報酬估算預測區間。")}</p>
      <div class="backtest-forecast-levels technical-summary-levels">
        <span>支撐區 <b>${supportText}</b></span>
        <span>壓力區 <b>${resistanceText}</b></span>
        <span>ATR 波動 <b>${atrText}</b></span>
      </div>
      ${scenarios.length ? `
        <div class="backtest-forecast-grid technical-summary-scenarios">
          ${scenarios.map((item) => `
            <div class="backtest-forecast-item">
              <strong>${escapeHtml(item.label || `${item.days || "--"} 日`)}</strong>
              <span class="is-bullish">偏多 ${Number.isFinite(item.bullish) ? item.bullish : "--"}%</span>
              <span>震盪 ${Number.isFinite(item.neutral) ? item.neutral : "--"}%</span>
              <span class="is-bearish">偏空 ${Number.isFinite(item.bearish) ? item.bearish : "--"}%</span>
            </div>
          `).join("")}
        </div>
      ` : ""}
      ${priceTargets.length ? `
        <div class="backtest-price-targets technical-summary-targets">
          <div class="backtest-price-targets-head">
            <strong>${escapeHtml(targetTitle)}</strong>
            <span>${escapeHtml(forecast.forecastBiasText || "情境比例計算中")}</span>
          </div>
          <div class="backtest-price-target-grid">
            ${priceTargets.map((item) => `
              <div class="backtest-price-target">
                <span>${escapeHtml(item.label || `${item.days || "--"} 日`)}</span>
                <strong>${Number.isFinite(item.lower) ? item.lower.toFixed(2) : "--"} ~ ${Number.isFinite(item.upper) ? item.upper.toFixed(2) : "--"}</strong>
                <small>中位 ${Number.isFinite(item.median) ? item.median.toFixed(2) : "--"}｜預估 ${Number.isFinite(item.expectedReturnPct) ? `${item.expectedReturnPct >= 0 ? "+" : ""}${item.expectedReturnPct.toFixed(2)}%` : "--"}</small>
                <em>${escapeHtml(item.basis || "")}</em>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ""}
      <p class="technical-summary-caveat">${escapeHtml(forecast.caveat || `預測${assetLabel}為區間模型估算，不是保證價格或投資建議。`)}</p>
    </div>
  `;
}
function buildPath(points) {
  return points
    .filter((point) => Number.isFinite(point.value) && Number.isFinite(point.x) && Number.isFinite(point.y))
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
}
function normalizeGlobalSeries(series = []) {
  return (series || [])
    .map((item) => ({
      date: item.date || item.time || "",
      value: parseMarketNumber(item.close),
    }))
    .filter((item) => item.date && Number.isFinite(item.value));
}
function normalizeGlobalOhlcvSeries(series = []) {
  return (series || [])
    .map((item) => {
      const close = parseMarketNumber(item.close);
      const open = parseMarketNumber(item.open);
      const high = parseMarketNumber(item.high);
      const low = parseMarketNumber(item.low);
      const volume = parseMarketNumber(item.volumeValue ?? item.volume);
      return {
        date: item.date || item.time || "",
        open: Number.isFinite(open) ? open : close,
        high: Number.isFinite(high) ? high : Math.max(open || close || 0, close || 0),
        low: Number.isFinite(low) ? low : Math.min(open || close || 0, close || 0),
        close,
        volume: Number.isFinite(volume) ? volume : 0,
        openInterest: parseMarketNumber(item.openInterest),
        settlement: parseMarketNumber(item.settlement),
      };
    })
    .filter((item) => item.date && Number.isFinite(item.close));
}
function getVixSentimentBand(value) {
  if (!Number.isFinite(value)) return { label: "--", tone: "neutral", text: "VIX 資料不足。" };
  if (value < 15) return { label: "低於 15", tone: "green", text: "市場情緒偏樂觀，但需留意過度樂觀後的波動回補。" };
  if (value < 20) return { label: "15 ~ 20", tone: "green", text: "常態穩定區，風險溫度相對健康。" };
  if (value < 30) return { label: "20 ~ 30", tone: "yellow", text: "警戒區，波動升溫，留意修正與多空交戰。" };
  if (value < 40) return { label: "30 ~ 40", tone: "red", text: "高恐慌區，短線波動劇烈，避免追價。" };
  return { label: "高於 40", tone: "purple", text: "極端恐慌區，可能有非理性賣壓，也需觀察反彈契機。" };
}
function buildYahooFinanceUrl(symbol) {
  const cleanSymbol = encodeURIComponent(String(symbol || "").trim());
  return cleanSymbol ? `https://finance.yahoo.com/quote/${cleanSymbol}` : "#";
}
function buildUsStockSearchUrl(symbol) {
  const cleanSymbol = encodeURIComponent(String(symbol || "").trim().toUpperCase());
  return cleanSymbol ? `us-stock-search.html?symbol=${cleanSymbol}` : "us-stock-search.html";
}
function normalizeFuturesTechnicalCandles(candles = []) {
  return (candles || []).map((row) => ({
    date: String(row.time || row.date || "").trim(),
    open: parseMarketNumber(row.open),
    high: parseMarketNumber(row.high),
    low: parseMarketNumber(row.low),
    close: parseMarketNumber(row.close),
    volume: parseMarketNumber(row.volumeValue ?? row.volume),
    volumeValue: parseMarketNumber(row.volumeValue ?? row.volume),
    settlement: parseMarketNumber(row.settlement),
    openInterest: parseMarketNumber(row.openInterestValue ?? row.openInterest),
  })).filter((row) => row.date);
}
function optionsNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function optionsWhole(value) {
  const parsed = optionsNumber(value);
  return parsed === null ? "--" : Math.round(parsed).toLocaleString("en-US");
}
function optionsDecimal(value, digits = 2) {
  const parsed = optionsNumber(value);
  return parsed === null ? "--" : parsed.toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}
function optionsPct(value, digits = 1) {
  const parsed = optionsNumber(value);
  return parsed === null ? "--" : `${(parsed * 100).toFixed(digits)}%`;
}
function averageUsHistoryField(history, field, lookback = 5) {
  const values = history.slice(-lookback).map((item) => parseMarketNumber(item[field])).filter(Number.isFinite);
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
}
function buildUsSearchDetail(item) {
  const detail = buildGlobalMarketDetail(item);
  const history = detail.historyDays || [];
  const close = parseMarketNumber(item.close);
  const pct = parseMarketNumber(item.pct);
  const tone = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  const recentWindow = history.slice(-22);
  const monthHigh = Math.max(...recentWindow.map((day) => day.high).filter(Number.isFinite));
  const monthLow = Math.min(...recentWindow.map((day) => day.low).filter(Number.isFinite));
  const avgVolume5 = averageUsHistoryField(history, "volume", 5);
  const latest = history.at(-1) || {};
  const maText = (value) => Number.isFinite(value) ? value.toFixed(2) : "--";
  const volumeText = (value) => Number.isFinite(value) ? Math.round(value).toLocaleString("zh-TW") : "--";
  const ma5 = detail.ma5;
  const ma20 = detail.ma20;
  const ma60 = detail.ma60;
  const trendParts = [];
  if (Number.isFinite(close) && Number.isFinite(ma20)) {
    trendParts.push(close >= ma20 ? "價格位於 20 日均線上方，短線結構偏強。" : "價格位於 20 日均線下方，短線仍需觀察修復。");
  }
  if (Number.isFinite(ma20) && Number.isFinite(ma60)) {
    trendParts.push(ma20 >= ma60 ? "20 日均線高於 60 日均線，中期趨勢尚未轉弱。" : "20 日均線低於 60 日均線，中期趨勢偏保守。");
  }
  if (Number.isFinite(avgVolume5) && Number.isFinite(latest.volume)) {
    trendParts.push(latest.volume >= avgVolume5 ? "成交量高於 5 日均量，量能有放大跡象。" : "成交量低於 5 日均量，追價動能仍需確認。");
  }
  const recentDays = history.slice(-5).reverse().map((day) => ({
    date: day.date || "--",
    close: formatUsDetailMetric(day.close),
    high: formatUsDetailMetric(day.high),
    low: formatUsDetailMetric(day.low),
    volume: volumeText(day.volume),
  }));
  return {
    ...detail,
    rawItem: item,
    code: item.symbol || detail.code,
    name: item.name || detail.name || item.symbol || "",
    market: "US",
    marketLabel: item.exchange || "US",
    snapshotDate: item.date || detail.snapshotDate || "",
    close: formatGlobalValue(item.close),
    open: formatGlobalValue(item.open),
    high: formatGlobalValue(item.high),
    low: formatGlobalValue(item.low),
    previousClose: formatGlobalValue(item.previousClose),
    pct: item.pct || "--",
    change: item.change || "--",
    tone,
    ma5: maText(ma5),
    ma20: maText(ma20),
    ma60: maText(ma60),
    ma120: maText(detail.ma120),
    ma240: maText(detail.ma240),
    avgVolume5: volumeText(avgVolume5),
    monthHigh: Number.isFinite(monthHigh) ? monthHigh.toFixed(2) : "--",
    monthLow: Number.isFinite(monthLow) ? monthLow.toFixed(2) : "--",
    turnover: "Yahoo 未提供",
    trend: trendParts.join(" ") || "Yahoo Finance 歷史資料不足，暫以行情快照觀察。",
    recentDays,
    historyDays: history,
    historyCount: history.length,
    historyStartDate: history[0]?.date || "",
    historyEndDate: history.at(-1)?.date || "",
    allHistoryLoaded: true,
    isFallbackHistory: false,
    source: item.source || "Yahoo Finance",
    sourceLink: buildYahooFinanceUrl(item.symbol),
    valuation: item.valuation || {},
    valuationHistory: Array.isArray(item.valuationHistory) ? item.valuationHistory : [],
    companyProfile: item.companyProfile || {},
    companyNews: Array.isArray(item.companyNews) ? item.companyNews : [],
    marginTrading: item.marginTrading || {},
    ownershipTrading: item.ownershipTrading || {},
    etfComponents: item.etfComponents || {},
    isEtf: Boolean(item.isEtf ?? detail.isEtf)
      || /ETF|FUND/.test(String(item.group || item.type || item.quoteType || "").toUpperCase()),
    detailMode: item.detailMode || "full",
    newsLinks: item.newsLinks || {
      yahoo: `${buildYahooFinanceUrl(item.symbol)}/news`,
      profile: `${buildYahooFinanceUrl(item.symbol)}/profile`,
    },
    chartIntervals: { supported: ["day", "week", "month"], intradayAvailable: false },
  };
}
function renderUsBacktestLearningCard(technicalTheory, options = {}) {
  const targetLabel = options.targetLabel || "股價";
  const priceTargetTitle = options.priceTargetTitle || `預估${targetLabel}區間`;
  const factorSubtitle = options.factorSubtitle || "以市場環境、資金面、趨勢面與進出場訊號分層驗證。";
  const frameworkKicker = options.frameworkKicker || "Institutional multi-factor";
  const frameworkTitle = options.frameworkTitle || "機構多因子回溯統整";
  const frameworkStateLabel = options.frameworkStateLabel || "市場狀態";
  const finalNote = options.finalNote || "回測只作訊號校準與風險管理參考，不保證未來價格走勢；美股基本面與籌碼資料口徑不同於台股，需搭配 SEC / 公司 IR 核對。";
  const learning = technicalTheory.backtestLearning || {};
  const validation = learning.validation || {};
  const originalValidation = learning.originalValidation || {};
  const modelRebuild = learning.modelRebuild || {};
  const best = learning.signals?.[0] || learning.bestSignal || {};
  const forecast = learning.forecast || {};
  const scenarios = Array.isArray(forecast.scenarios) ? forecast.scenarios : [];
  const priceTargets = Array.isArray(forecast.priceTargets) ? forecast.priceTargets : [];
  const performance = learning.performance || {};
  const costModel = learning.costModel || {};
  const riskModel = learning.riskModel || {};
  const institutionalFramework = learning.institutionalFramework || {};
  const institutionalLayers = Array.isArray(institutionalFramework.layers) ? institutionalFramework.layers : [];
  const recent20 = institutionalFramework.recent20 || {};
  const validationTone = validation.status === "healthy"
    ? "bullish"
    : validation.status === "watch"
      ? "neutral"
      : validation.status === "recalibrate" || validation.status === "rebuild"
        ? "bearish"
        : "neutral";
  const supportText = Number.isFinite(forecast.support) ? forecast.support.toFixed(2) : "--";
  const resistanceText = Number.isFinite(forecast.resistance) ? forecast.resistance.toFixed(2) : "--";
  const atrText = Number.isFinite(forecast.atrPct) ? `${forecast.atrPct.toFixed(2)}%` : "--";
  const adjustment = Number(learning.scoreAdjustment || 0);
  const adjustmentText = adjustment > 0 ? `+${adjustment} 偏多校準` : adjustment < 0 ? `${adjustment} 偏空校準` : "0 中性";
  const decisionTips = [
    modelRebuild.status === "rebuilt"
      ? `模型已重建：舊模型 ${modelRebuild.oldModel || "--"} 改為 ${modelRebuild.newModel || "--"}。`
      : modelRebuild.status === "failed"
        ? "替代模型尚未通過樣本外驗證，暫不提高訊號權重。"
        : "",
    validation.status === "healthy"
      ? "樣本外驗證維持健康，可保留目前技術訊號權重。"
      : validation.status === "rebuild"
        ? "模型失真偏高，需降低此標的技術訊號權重。"
        : validation.recommendation || "",
    Number.isFinite(forecast.support) && Number.isFinite(forecast.resistance)
      ? `區間參考：接近 ${supportText} 觀察承接，接近 ${resistanceText} 留意壓力。`
      : "",
    Number.isFinite(forecast.atrPct) ? `波動參考 ATR 約 ${atrText}，部位大小需搭配停損距離。` : "",
    ...(Array.isArray(options.extraDecisionTips) ? options.extraDecisionTips : []),
  ].filter(Boolean);
  return `
    <div class="stock-backtest-learning">
      <div class="backtest-learning-head">
        <span>Backtest learning</span>
        <strong>回溯學習校準</strong>
        <small>${escapeHtml(learning.summary || "歷史樣本不足，暫不調整 AI 權重")}</small>
      </div>
      <div class="institutional-backtest-card is-${escapeHtml(institutionalFramework.judgement?.tone || "neutral")}">
        <div class="institutional-backtest-head">
          <div>
            <span>${escapeHtml(frameworkKicker)}</span>
            <strong>${escapeHtml(frameworkTitle)}</strong>
            <small>${escapeHtml(factorSubtitle)}</small>
          </div>
          <div class="institutional-total-score">
            <b>${Number.isFinite(institutionalFramework.totalScore) ? institutionalFramework.totalScore : "--"}</b>
            <span>/ 100</span>
            <small>${escapeHtml(institutionalFramework.judgement?.label || "資料不足")}</small>
          </div>
        </div>
        <div class="institutional-layer-grid">
          ${institutionalLayers.map((layer) => `
            <article>
              <div><strong>${escapeHtml(layer.label || "--")}</strong><span>權重 ${layer.weight ?? "--"}%</span></div>
              <b>${Number.isFinite(layer.score) ? Math.round(layer.score) : "--"}</b>
              <div class="institutional-score-track"><i style="width:${Number.isFinite(layer.score) ? Math.round(layer.score) : 0}%"></i></div>
              <small>資料涵蓋 ${Math.round((layer.coverage || 0) * 100)}% · ${(layer.available || []).map((item) => escapeHtml(item.name)).join("、") || "等待資料"}</small>
            </article>
          `).join("") || '<p class="stock-detail-empty">多因子分層資料不足。</p>'}
        </div>
        <div class="institutional-monitor-grid">
          <div><span>${escapeHtml(frameworkStateLabel)}</span><strong>${escapeHtml(institutionalFramework.marketState || "--")}</strong></div>
          <div><span>近 20 筆勝率</span><strong>${formatBacktestPercent(recent20.winRate)} · ${escapeHtml(recent20.winState || "樣本不足")}</strong></div>
          <div><span>近 20 筆 PF</span><strong>${formatBacktestRatio(recent20.profitFactor)} · ${escapeHtml(recent20.pfState || "樣本不足")}</strong></div>
          <div><span>近 20 筆 MDD</span><strong>${formatBacktestRatio(recent20.maxDrawdown)}% · ${escapeHtml(recent20.mddState || "樣本不足")}</strong></div>
        </div>
      </div>
      <div class="backtest-forecast-card">
        <div class="backtest-forecast-head">
          <div>
            <span>Scenario forecast</span>
            <strong>未來走勢情境推估</strong>
          </div>
          <small>模型信心：${escapeHtml(forecast.confidence || "低")} · ${escapeHtml(forecast.trendLabel || "區間震盪")}</small>
        </div>
        <p>${escapeHtml(forecast.summary || "回測資料不足，暫以中性震盪情境觀察。")}</p>
        <div class="backtest-forecast-grid">
          ${scenarios.map((item) => `
            <div class="backtest-forecast-item">
              <strong>${escapeHtml(item.label || `${item.days || "--"} 日`)}</strong>
              <span class="is-bullish">偏多 ${Number.isFinite(item.bullish) ? item.bullish : "--"}%</span>
              <span>震盪 ${Number.isFinite(item.neutral) ? item.neutral : "--"}%</span>
              <span class="is-bearish">偏空 ${Number.isFinite(item.bearish) ? item.bearish : "--"}%</span>
            </div>
          `).join("") || '<p class="stock-detail-empty">樣本不足，暫不輸出情境比例。</p>'}
        </div>
        <div class="backtest-forecast-levels">
          <span>支撐區 <b>${supportText}</b></span>
          <span>壓力區 <b>${resistanceText}</b></span>
          <span>波動參考 <b>${atrText}</b></span>
        </div>
        ${priceTargets.length ? `
          <div class="backtest-price-targets">
            <div class="backtest-price-targets-head"><strong>${escapeHtml(priceTargetTitle)}</strong><span>以區間與中位價呈現</span></div>
            <div class="backtest-price-target-grid">
              ${priceTargets.map((item) => `
                <div class="backtest-price-target">
                  <span>${escapeHtml(item.label || "--")}</span>
                  <strong>${Number.isFinite(item.lower) ? item.lower.toFixed(2) : "--"} ~ ${Number.isFinite(item.upper) ? item.upper.toFixed(2) : "--"}</strong>
                  <small>中位 ${Number.isFinite(item.median) ? item.median.toFixed(2) : "--"}｜預估 ${Number.isFinite(item.expectedReturnPct) ? `${item.expectedReturnPct >= 0 ? "+" : ""}${item.expectedReturnPct.toFixed(2)}%` : "--"}</small>
                  <em>${escapeHtml(item.basis || "")}</em>
                </div>
              `).join("")}
            </div>
          </div>
        ` : ""}
        <p class="backtest-forecast-caveat">${escapeHtml(forecast.caveat || "情境推估只作風險管理參考，不保證未來價格。")}</p>
      </div>
      <div class="backtest-validation-card is-${validationTone}">
        <div class="backtest-validation-head">
          <strong>模型準確性驗證：${escapeHtml(validation.label || "樣本不足")}</strong>
        </div>
        <p>${escapeHtml(validation.recommendation || "樣本不足，暫不判定模型失真。")}</p>
        <p>原模型狀態：${escapeHtml(originalValidation.label || "未提供")}；最佳訊號 ${escapeHtml(best.name || "--")}。</p>
        <div class="backtest-validation-grid">
          <span>樣本內勝率 <b>${formatBacktestPercent(validation.inSample?.winRate)}</b></span>
          <span>樣本外勝率 <b>${formatBacktestPercent(validation.outSample?.winRate)}</b></span>
          <span>樣本外 MDD <b>${formatBacktestRatio(validation.outSample?.maxDrawdown)}%</b></span>
          <span>樣本外 PF <b>${formatBacktestRatio(validation.outSample?.profitFactor)}</b></span>
        </div>
        <ul>${(validation.reasons || ["未取得模型失真檢查資料"]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
      <div class="backtest-metrics">
        <div><span>回測週期</span><strong>${learning.horizon || 240} 日後報酬</strong></div>
        <div><span>成功門檻</span><strong>±${learning.successThreshold || 5}%</strong></div>
        <div><span>有效樣本</span><strong>${learning.evidenceCount || 0}</strong></div>
        <div><span>權重調整</span><strong class="${adjustment > 0 ? "up" : adjustment < 0 ? "down" : ""}">${adjustmentText}</strong></div>
        <div><span>交易成本</span><strong>${formatBacktestRatio(costModel.roundTripPct)}%</strong></div>
        <div><span>停損 / 停利</span><strong>${riskModel.stopLossPct || -8}% / +${riskModel.takeProfitPct || 20}%</strong></div>
        <div><span>最大回撤</span><strong class="down">${formatBacktestRatio(performance.maxDrawdown)}%</strong></div>
        <div><span>Profit Factor</span><strong>${formatBacktestRatio(best.profitFactor ?? performance.profitFactor)}</strong></div>
        <div><span>模型狀態</span><strong class="${validation.status === "rebuild" ? "down" : validation.status === "healthy" ? "up" : ""}">${escapeHtml(validation.label || "樣本不足")}</strong></div>
        <div><span>失真次數</span><strong>${validation.driftCount ?? 0}</strong></div>
      </div>
      <div class="backtest-action-card">
        <div><span>Action calibration</span><strong>操作校準提示</strong></div>
        <ul>${decisionTips.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>樣本不足，先採中性觀察。</li>"}</ul>
      </div>
      <p class="stock-theory-note">${escapeHtml(finalNote)}</p>
    </div>
  `;
}
function normalizeUsWatchlistItem(rawItem = {}) {
  const symbol = String(rawItem.symbol || rawItem.code || "").trim().toUpperCase();
  return {
    ...rawItem,
    symbol,
    code: symbol,
    market: "US",
    marketLabel: rawItem.marketLabel || rawItem.exchange || rawItem.group || "美股 / ETF",
    name: rawItem.name || rawItem.shortName || symbol,
    group: rawItem.group || rawItem.type || "美股 / ETF",
    type: rawItem.type || rawItem.group || "US Market",
  };
}
function usWatchlistKey(item) {
  return String(item?.symbol || item?.code || "").trim().toUpperCase();
}
function getUsWatchlist() {
  try {
    const parsed = JSON.parse(localStorage.getItem(US_WATCHLIST_STORAGE_KEY) || "[]");
    return Array.isArray(parsed)
      ? parsed.map(normalizeUsWatchlistItem).filter((item) => item.symbol)
      : [];
  } catch (error) {
    return [];
  }
}
function saveUsWatchlist(items) {
  localStorage.setItem(US_WATCHLIST_STORAGE_KEY, JSON.stringify(items));
}
function upsertUsWatchlistSymbol(rawItem, options = {}) {
  const normalized = normalizeUsWatchlistItem(rawItem);
  const symbol = normalized.symbol;
  if (!symbol) return false;
  const items = getUsWatchlist();
  const nextItem = {
    ...normalized,
    addedAt: normalized.addedAt || new Date().toISOString(),
  };
  const index = items.findIndex((item) => String(item.symbol).toUpperCase() === symbol);
  if (index >= 0) items[index] = { ...items[index], ...nextItem };
  else items.push(nextItem);
  saveUsWatchlist(items);
  if (options.render !== false) renderUsWatchlist();
  return true;
}
function getUsPortfolioSimulation() {
  try {
    const value = JSON.parse(localStorage.getItem(US_PORTFOLIO_SIM_STORAGE_KEY) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}
function saveUsPortfolioSimulation(value) {
  localStorage.setItem(US_PORTFOLIO_SIM_STORAGE_KEY, JSON.stringify(value));
}
function classifyUsPortfolioAsset(stock) {
  const text = [stock?.group, stock?.type, stock?.name, stock?.symbol].join(" ");
  return /ETF|FUND|TRUST/i.test(text) ? "ETF" : "股票";
}
function estimateUsPortfolioTransactionCost(position) {
  if (!(position?.shares > 0) || !(position?.entryPrice > 0) || !(position?.currentPrice > 0)) return 0;
  const buyValue = position.entryPrice * position.shares;
  const sellValue = position.currentPrice * position.shares;
  const rate = 0.0015;
  return (buyValue + sellValue) * rate;
}
function renderUsWatchlistAiSummary(items) {
  const container = document.getElementById("us-watchlist-ai-summary");
  if (!container) return;
  if (!items.length) {
    container.innerHTML = "";
    return;
  }
  const analyses = items.map((item) => usWatchlistAnalysisCache.get(usWatchlistKey(item))).filter(Boolean);
  if (!analyses.length) {
    container.innerHTML = '<div class="watchlist-ai-loading">正在整理美股自選的技術、量價、Short Interest 與估值訊號...</div>';
    return;
  }
  const positive = analyses.filter((item) => item.tone === "positive").length;
  const negative = analyses.filter((item) => item.tone === "negative").length;
  const pending = items.length - analyses.length;
  const overview = positive > negative
    ? "整體美股自選訊號偏正向，但仍應留意市場波動與集中度。"
    : negative > positive
      ? "目前風險訊號較多，建議優先檢視弱勢或高波動持股。"
      : "多空訊號接近，適合等待個股趨勢與市場情緒進一步確認。";
  container.innerHTML = `
    <div>
      <span class="news-tag">AI 多因子摘要</span>
      <h4>${overview}</h4>
      <p>偏正向 ${positive} 檔、偏弱 ${negative} 檔${pending ? `，另有 ${pending} 檔分析中` : ""}。</p>
    </div>
    <small>依 Yahoo Finance 行情、均線、量價、Short Interest 與估值資料計算，僅供研究參考。</small>
  `;
}
function renderUsWatchlist() {
  const grid = document.getElementById("us-watchlist-grid");
  const count = document.getElementById("us-watchlist-count");
  if (!grid) return;
  const items = getUsWatchlist();
  if (count) count.textContent = `${items.length} 檔`;
  if (!items.length) {
    grid.innerHTML = '<div class="watchlist-empty">尚未加入美股自選股，請至美股搜尋頁開啟個股或 ETF 詳情後加入。</div>';
    renderUsWatchlistAiSummary(items);
    renderUsPortfolioSimulator(items);
    return;
  }
  renderUsWatchlistAiSummary(items);
  renderUsPortfolioSimulator(items);
  grid.innerHTML = items.map((item) => {
    const pct = parseMarketNumber(item.pct);
    const tone = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
    const key = usWatchlistKey(item);
    const analysis = usWatchlistAnalysisCache.get(key);
    const detailUrl = buildUsStockSearchUrl(key);
    return `
      <article class="watchlist-card is-clickable" role="link" tabindex="0" data-us-watchlist-detail-url="${escapeHtml(detailUrl)}" aria-label="查看 ${escapeHtml(item.symbol)} ${escapeHtml(item.name)} 美股詳情">
        <div class="watchlist-card-head">
          <div>
            <span>${escapeHtml(item.group || "美股 / ETF")}</span>
            <h3>${escapeHtml(item.symbol || "--")} ${escapeHtml(item.name || "")}</h3>
          </div>
          <button class="watchlist-remove" type="button" data-us-watch-remove="${escapeHtml(key)}">移除</button>
        </div>
        <div class="watchlist-quote">
          <strong>${formatGlobalValue(item.close)}</strong>
          <span class="${toneClass(tone)}">${escapeHtml(item.change || "--")} / ${escapeHtml(item.pct || "--")}</span>
        </div>
        <div class="watchlist-ai-card ${analysis ? `is-${analysis.tone}` : "is-loading"}">
          ${analysis ? `
            <div class="watchlist-ai-title">
              <span>AI 分析建議</span>
              <strong>${escapeHtml(analysis.label)}</strong>
            </div>
            <p>${escapeHtml(analysis.suggestion)}</p>
            <div class="watchlist-theory-groups">
              <div>
                <strong>型態技術</strong>
                <span>${escapeHtml(analysis.adaptiveSummary || analysis.patterns?.[0] || "型態訊號不足")}</span>
              </div>
              <div>
                <strong>指標技術</strong>
                <span>${escapeHtml(analysis.indicatorSummary || analysis.indicators?.[0] || "指標訊號不足")}</span>
              </div>
            </div>
            <ul>${analysis.reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>
            <small>信心 ${escapeHtml(analysis.confidence)} · 資料日 ${escapeHtml(analysis.date)}</small>
          ` : `
            <span>AI 分析建議</span>
            <p>正在讀取完整美股資料...</p>
          `}
        </div>
        <a class="watchlist-detail-link" href="${safeUrl(detailUrl)}">查看美股分析</a>
      </article>
    `;
  }).join("");
  grid.querySelectorAll("[data-us-watchlist-detail-url]").forEach((card) => {
    const openDetail = () => {
      const url = card.dataset.usWatchlistDetailUrl;
      if (url) window.location.href = url;
    };
    card.addEventListener("click", (event) => {
      if (event.target.closest("button, a, input, label, select, textarea")) return;
      openDetail();
    });
    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openDetail();
    });
  });
  grid.querySelectorAll("[data-us-watch-remove]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.usWatchRemove;
      saveUsWatchlist(getUsWatchlist().filter((item) => usWatchlistKey(item) !== key));
      usWatchlistAnalysisCache.delete(key);
      usWatchlistDetailCache.delete(key);
      renderUsWatchlist();
      setText("us-watchlist-status", "已從美股自選股移除。");
    });
  });
}
function buildUsPortfolioFactorAssessment(positions, totals) {
  const active = positions.filter((item) => item.shares > 0);
  const analyzed = active.map((item) => item.analysis).filter(Boolean);
  const assetCounts = active.reduce((acc, item) => {
    const kind = classifyUsPortfolioAsset(item.stock);
    acc[kind] = (acc[kind] || 0) + 1;
    return acc;
  }, {});
  const maxWeight = totals.totalValue > 0
    ? Math.max(...active.map((item) => (item.marketValue / totals.totalValue) * 100), 0)
    : 0;
  const stopRiskRatio = totals.totalCost > 0 ? (totals.totalRisk / totals.totalCost) * 100 : 0;
  const netReturn = totals.totalCost > 0 ? (totals.netPnl / totals.totalCost) * 100 : 0;
  const pctMoves = active
    .map((item) => Math.abs(parseAnalysisNumber(item.detail?.pct ?? item.stock.pct) ?? 0))
    .filter(Number.isFinite);
  const avgMove = pctMoves.length ? pctMoves.reduce((sum, value) => sum + value, 0) / pctMoves.length : 0;
  const var95 = totals.totalValue * (avgMove / 100) * 1.65;
  const sharpeLike = avgMove ? netReturn / avgMove : null;
  const positiveAi = analyzed.filter((item) => item.tone === "positive").length;
  const negativeAi = analyzed.filter((item) => item.tone === "negative").length;
  const neutralAi = Math.max(analyzed.length - positiveAi - negativeAi, 0);
  const averageAiScore = analyzed.length
    ? analyzed.reduce((sum, item) => sum + (Number(item.score) || 0), 0) / analyzed.length
    : 0;
  const portfolioTheory = buildPortfolioTheoryAssessment(active, totals);

  if (!active.length) {
    return {
      tone: "neutral",
      label: "等待建立部位",
      summary: "尚未輸入股數，系統先保留美元成本、資產配置、相關性、分散化與風險貢獻的檢查框架。",
      factors: ["請輸入進場價與股數後，系統會估算美元淨損益、交易成本、集中度、VaR、相關性與分散化。"],
      actions: ["建立部位前先設定單筆停損與停利條件，並規劃單一標的權重上限。"],
      theoryDetails: portfolioTheory.details,
      theoryActions: portfolioTheory.actions,
      metrics: { maxWeight, stopRiskRatio, var95, sharpeLike, avgMove, ...portfolioTheory.metrics },
      source: PORTFOLIO_FACTOR_SOURCE,
    };
  }

  const factors = [
    `資產配置：${Object.entries(assetCounts).map(([key, count]) => `${key} ${count} 檔`).join("、") || "未分類"}。`,
    `交易成本以單邊手續費與滑價合計 0.15% 估算，成本後淨損益 ${formatUsSimulationMoney(totals.netPnl)}。`,
    `單一商品最高權重 ${maxWeight.toFixed(1)}%，組合停損風險約 ${stopRiskRatio.toFixed(1)}%。`,
    `以目前自選標的日波動估算 95% 單日 VaR 約 ${formatUsSimulationMoney(var95)}。`,
    `資產投資組合理論：${portfolioTheory.label}，已納入均值-變異、相關性、分散化比率與風險貢獻。`,
  ];
  if (analyzed.length) {
    factors.push(`AI 技術覆蓋：已納入 ${analyzed.length}/${active.length} 檔的型態理論、均線、價量、Short Interest 與回溯校準。`);
    factors.push(`技術方向：偏正向 ${positiveAi} 檔、中性 ${neutralAi} 檔、偏弱 ${negativeAi} 檔，平均 AI 分數 ${averageAiScore.toFixed(1)}。`);
  } else {
    factors.push("AI 技術覆蓋：完整美股資料尚未載入，暫以損益、權重、成本與歷史波動先行評估。");
  }
  if (Number.isFinite(sharpeLike)) factors.push(`類 Sharpe 風險效率 ${sharpeLike.toFixed(2)}，用於比較近期損益是否足以補償波動。`);

  const actions = [];
  if (maxWeight > 50) actions.push("單一商品超過 50%，組合接近單押，建議分散或設定更嚴格停損。");
  else if (maxWeight > 20) actions.push("單一商品超過 20%，需確認是否符合自己的持股上限。");
  else actions.push("單一商品權重未明顯過度集中。");
  if (stopRiskRatio >= 15) actions.push("組合停損風險高於 15%，應檢查是否降低股數或收窄停損。");
  else actions.push("組合停損風險低於 15%，風控結構相對可控。");
  if (totals.netPnl < 0 && stopRiskRatio >= 10) actions.push("淨損益為負且停損風險偏高，優先檢查弱勢持股。");
  if (negativeAi > positiveAi) actions.push("組合內偏弱 AI 訊號較多，優先檢查技術結構或 Short Interest 壓力。");
  else if (positiveAi > negativeAi) actions.push("多數持股 AI 訊號偏正向，仍應依原訂停損停利紀律分批管理。");
  actions.push(...portfolioTheory.actions.slice(0, 3));
  actions.push("未納入匯率、股息稅、券商固定費、SEC/FINRA 費用與槓桿，實際交易前需依券商規則校正。");

  const riskScore = (maxWeight > 50 ? 2 : maxWeight > 20 ? 1 : 0)
    + (stopRiskRatio >= 15 ? 2 : stopRiskRatio >= 10 ? 1 : 0)
    + (totals.netPnl < 0 ? 1 : 0)
    + (negativeAi > positiveAi ? 1 : 0)
    + (portfolioTheory.tone === "negative" ? 2 : portfolioTheory.tone === "neutral" ? 1 : 0);
  const tone = riskScore >= 4 ? "negative" : riskScore >= 2 ? "neutral" : "positive";
  const label = tone === "positive" ? "配置風險可控" : tone === "negative" ? "組合風險偏高" : "需再平衡觀察";
  return {
    tone,
    label,
    summary: `${label}：已依美元成本、資產配置、均值-變異、相關性、風險貢獻、停損停利、VaR 與個股 AI 多因子訊號整合評估。`,
    factors,
    actions,
    theoryDetails: portfolioTheory.details,
    theoryActions: portfolioTheory.actions,
    metrics: { maxWeight, stopRiskRatio, var95, sharpeLike, avgMove, averageAiScore, ...portfolioTheory.metrics },
    source: PORTFOLIO_FACTOR_SOURCE,
  };
}
function renderUsPortfolioSimulator(items = getUsWatchlist()) {
  const summary = document.getElementById("us-portfolio-simulator-summary");
  const table = document.getElementById("us-portfolio-simulator-table");
  if (!summary || !table) return;
  if (!items.length) {
    summary.innerHTML = "";
    table.innerHTML = '<div class="watchlist-empty">加入美股自選股後即可建立美元組合損益模擬。</div>';
    return;
  }
  const saved = getUsPortfolioSimulation();
  const positions = items.map((rawStock) => {
    const stock = normalizeUsWatchlistItem(rawStock);
    const key = usWatchlistKey(stock);
    const detail = usWatchlistDetailCache.get(key);
    const currentPrice = parseAnalysisNumber(detail?.close ?? stock.close) || 0;
    const setting = saved[key] || {};
    const entryPrice = parseAnalysisNumber(setting.entryPrice) || currentPrice;
    const shares = Math.max(0, parseAnalysisNumber(setting.shares) || 0);
    const stopLossPct = Math.max(0, parseAnalysisNumber(setting.stopLossPct) ?? 8);
    const takeProfitPct = Math.max(0, parseAnalysisNumber(setting.takeProfitPct) ?? 15);
    const cost = entryPrice * shares;
    const marketValue = currentPrice * shares;
    const pnl = marketValue - cost;
    const transactionCost = estimateUsPortfolioTransactionCost({ stock, currentPrice, entryPrice, shares });
    const netPnl = pnl - transactionCost;
    const returnPct = cost > 0 ? (pnl / cost) * 100 : 0;
    const netReturnPct = cost > 0 ? (netPnl / cost) * 100 : 0;
    const riskAmount = entryPrice * shares * (stopLossPct / 100);
    const analysis = usWatchlistAnalysisCache.get(key);
    return {
      stock, detail, key, currentPrice, entryPrice, shares, stopLossPct, takeProfitPct,
      cost, marketValue, pnl, transactionCost, netPnl, returnPct, netReturnPct, riskAmount,
      analysis,
      signal: getSimulationSignal(analysis, currentPrice, entryPrice, shares, stopLossPct, takeProfitPct),
    };
  });
  const active = positions.filter((item) => item.shares > 0);
  const totalCost = active.reduce((sum, item) => sum + item.cost, 0);
  const totalValue = active.reduce((sum, item) => sum + item.marketValue, 0);
  const totalPnl = totalValue - totalCost;
  const totalTransactionCost = active.reduce((sum, item) => sum + item.transactionCost, 0);
  const netPnl = totalPnl - totalTransactionCost;
  const totalReturn = totalCost > 0 ? (totalPnl / totalCost) * 100 : 0;
  const netReturn = totalCost > 0 ? (netPnl / totalCost) * 100 : 0;
  const totalRisk = active.reduce((sum, item) => sum + item.riskAmount, 0);
  const maxPosition = totalValue > 0 ? Math.max(...active.map((item) => (item.marketValue / totalValue) * 100), 0) : 0;
  const riskLabel = !active.length
    ? "尚未建立模擬部位"
    : maxPosition > 50
      ? "單一持股集中度偏高"
      : totalRisk / Math.max(totalCost, 1) > 0.1
        ? "組合停損風險偏高"
        : "風險設定在可控區間";
  const portfolioAssessment = buildUsPortfolioFactorAssessment(positions, {
    totalCost, totalValue, totalPnl, totalTransactionCost, netPnl, totalReturn, netReturn, totalRisk,
  });

  summary.innerHTML = `
    <div><span>模擬投入成本</span><strong>${formatUsSimulationMoney(totalCost)}</strong></div>
    <div><span>目前市值</span><strong>${formatUsSimulationMoney(totalValue)}</strong></div>
    <div><span>未實現損益</span><strong class="${totalPnl > 0 ? "up" : totalPnl < 0 ? "down" : "flat"}">${formatUsSimulationMoney(totalPnl)}</strong></div>
    <div><span>估計交易成本</span><strong>${formatUsSimulationMoney(totalTransactionCost)}</strong></div>
    <div><span>成本後淨損益</span><strong class="${netPnl > 0 ? "up" : netPnl < 0 ? "down" : "flat"}">${formatUsSimulationMoney(netPnl)}</strong></div>
    <div><span>組合報酬率</span><strong class="${totalReturn > 0 ? "up" : totalReturn < 0 ? "down" : "flat"}">${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(2)}%</strong></div>
    <div><span>淨報酬率</span><strong class="${netReturn > 0 ? "up" : netReturn < 0 ? "down" : "flat"}">${netReturn >= 0 ? "+" : ""}${netReturn.toFixed(2)}%</strong></div>
    <div><span>停損風險金額</span><strong>${formatUsSimulationMoney(totalRisk)}</strong></div>
    <div><span>95% VaR 估計</span><strong>${formatUsSimulationMoney(portfolioAssessment.metrics.var95 || 0)}</strong></div>
    <div><span>單一最高權重</span><strong>${(portfolioAssessment.metrics.maxWeight || 0).toFixed(1)}%</strong></div>
    <div><span>組合年化波動</span><strong>${Number.isFinite(portfolioAssessment.metrics.portfolioVolatility) ? `${portfolioAssessment.metrics.portfolioVolatility.toFixed(1)}%` : "--"}</strong></div>
    <div><span>有效持股數</span><strong>${Number.isFinite(portfolioAssessment.metrics.effectivePositions) ? `${portfolioAssessment.metrics.effectivePositions.toFixed(1)} 檔` : "--"}</strong></div>
    <div><span>平均相關性</span><strong>${Number.isFinite(portfolioAssessment.metrics.averageCorrelation) ? portfolioAssessment.metrics.averageCorrelation.toFixed(2) : "--"}</strong></div>
    <div><span>分散化比率</span><strong>${Number.isFinite(portfolioAssessment.metrics.diversificationRatio) ? portfolioAssessment.metrics.diversificationRatio.toFixed(2) : "--"}</strong></div>
    <div><span>效率分數</span><strong class="${portfolioAssessment.metrics.efficiencyScore > 0 ? "up" : portfolioAssessment.metrics.efficiencyScore < 0 ? "down" : "flat"}">${Number.isFinite(portfolioAssessment.metrics.efficiencyScore) ? portfolioAssessment.metrics.efficiencyScore.toFixed(2) : "--"}</strong></div>
    <div><span>AI 平均分數</span><strong class="${portfolioAssessment.metrics.averageAiScore > 0 ? "up" : portfolioAssessment.metrics.averageAiScore < 0 ? "down" : "flat"}">${portfolioAssessment.metrics.averageAiScore > 0 ? "+" : ""}${(portfolioAssessment.metrics.averageAiScore || 0).toFixed(1)}</strong></div>
    <div><span>風險摘要</span><strong>${riskLabel}</strong></div>
  `;
  table.innerHTML = `
    <article class="portfolio-factor-card is-${portfolioAssessment.tone}">
      <div class="portfolio-factor-head">
        <div>
          <p class="panel-kicker">US portfolio factors</p>
          <h4>${escapeHtml(portfolioAssessment.label)}</h4>
        </div>
        <a href="${safeUrl(portfolioAssessment.source.url)}" target="_blank" rel="noreferrer noopener">自選組合因素基準</a>
      </div>
      <p>${escapeHtml(portfolioAssessment.summary)}</p>
      <div class="portfolio-factor-grid">
        <section><h5>納入考量</h5><ul>${portfolioAssessment.factors.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
        <section><h5>風險與再平衡</h5><ul>${portfolioAssessment.actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
        <section><h5>資產組合理論</h5><ul>${(portfolioAssessment.theoryDetails || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></section>
      </div>
    </article>
    <div class="portfolio-table-head">
      <span>個股</span><span>目前價</span><span>模擬進場價</span><span>股數</span>
      <span>停損 / 停利</span><span>淨損益</span><span>判別訊號</span>
    </div>
    ${positions.map((item) => `
      <div class="portfolio-position-row">
        <div class="portfolio-stock-name"><strong>${escapeHtml(item.stock.code)}</strong><span>${escapeHtml(item.stock.name)}</span></div>
        <strong>${item.currentPrice ? `US$${item.currentPrice.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "--"}</strong>
        <label><span>進場價 (USD)</span><input type="number" min="0" step="0.01" value="${item.entryPrice || ""}" data-us-portfolio-key="${escapeHtml(item.key)}" data-us-portfolio-field="entryPrice"></label>
        <label><span>股數</span><input type="number" min="0" step="1" value="${item.shares || 0}" data-us-portfolio-key="${escapeHtml(item.key)}" data-us-portfolio-field="shares"></label>
        <div class="portfolio-risk-inputs">
          <label><span>停損 %</span><input type="number" min="0" step="0.5" value="${item.stopLossPct}" data-us-portfolio-key="${escapeHtml(item.key)}" data-us-portfolio-field="stopLossPct"></label>
          <label><span>停利 %</span><input type="number" min="0" step="0.5" value="${item.takeProfitPct}" data-us-portfolio-key="${escapeHtml(item.key)}" data-us-portfolio-field="takeProfitPct"></label>
        </div>
        <div class="portfolio-pnl ${item.netPnl > 0 ? "up" : item.netPnl < 0 ? "down" : "flat"}">
          <strong>${formatUsSimulationMoney(item.netPnl)}</strong>
          <span>淨 ${item.netReturnPct >= 0 ? "+" : ""}${item.netReturnPct.toFixed(2)}%｜成本 ${formatUsSimulationMoney(item.transactionCost)}</span>
        </div>
        <div class="portfolio-signal is-${item.signal.tone}"><strong>${escapeHtml(item.signal.label)}</strong><span>${escapeHtml(item.signal.note)}</span></div>
      </div>
    `).join("")}
  `;
  table.querySelectorAll("[data-us-portfolio-key]").forEach((input) => {
    input.addEventListener("change", () => {
      const value = Math.max(0, Number(input.value) || 0);
      const simulation = getUsPortfolioSimulation();
      const key = input.dataset.usPortfolioKey;
      simulation[key] = { ...(simulation[key] || {}), [input.dataset.usPortfolioField]: value };
      saveUsPortfolioSimulation(simulation);
      renderUsPortfolioSimulator();
    });
  });
}
function sliceVisibleWindow(items, visibleCount, panOffset = 0) {
  const count = Math.min(Math.max(Math.round(Number(visibleCount)) || items.length, 1), items.length);
  const offset = Math.min(Math.max(Math.round(Number(panOffset)) || 0, 0), Math.max(items.length - count, 0));
  const end = items.length - offset;
  return items.slice(Math.max(0, end - count), end);
}
function getWeekKey(date) {
  const start = new Date(date);
  start.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return formatChartDate(start);
}
function getPeriodKey(date, interval) {
  const year = date.getFullYear();
  const month = date.getMonth();
  if (interval === "week") return getWeekKey(date);
  if (interval === "month") return `${year}-${String(month + 1).padStart(2, "0")}`;
  if (interval === "quarter") return `${year}-Q${Math.floor(month / 3) + 1}`;
  if (interval === "half") return `${year}-H${month < 6 ? 1 : 2}`;
  if (interval === "year") return `${year}`;
  return formatChartDate(date);
}
function aggregateHistory(history, interval) {
  if (interval === "day" || interval === "all") return history;

  const groups = new Map();
  history.forEach((day) => {
    const key = getPeriodKey(day.parsedDate, interval);
    if (!groups.has(key)) {
      groups.set(key, {
        date: key,
        parsedDate: day.parsedDate,
        open: day.open,
        high: day.high ?? day.close,
        low: day.low ?? day.close,
        close: day.close,
        volume: day.volume || 0,
      });
      return;
    }

    const item = groups.get(key);
    item.high = Math.max(item.high, day.high ?? day.close);
    item.low = Math.min(item.low, day.low ?? day.close);
    item.close = day.close;
    item.volume += day.volume || 0;
    item.parsedDate = day.parsedDate;
  });

  return Array.from(groups.values());
}
function renderCombinedIndicatorPanel({ title, top, height, width, pad, xAt, values, secondaryValues = [], tertiaryValues = [], bars = [], fixedMin = null, fixedMax = null }) {
  const allValues = [...values, ...secondaryValues, ...tertiaryValues, ...bars].filter((value) => value !== null && Number.isFinite(value));
  if (!allValues.length) return "";

  const minValue = fixedMin ?? Math.min(...allValues, 0);
  const maxValue = fixedMax ?? Math.max(...allValues, 0);
  const valueRange = maxValue - minValue || 1;
  const yAt = (value) => top + ((maxValue - value) / valueRange) * height;
  const zeroY = yAt(Math.min(Math.max(0, minValue), maxValue));

  const primaryPoints = values.map((value, index) => ({
    x: xAt(index),
    y: value === null ? 0 : yAt(value),
    value,
  }));
  const secondaryPoints = secondaryValues.map((value, index) => ({
    x: xAt(index),
    y: value === null ? 0 : yAt(value),
    value,
  }));
  const tertiaryPoints = tertiaryValues.map((value, index) => ({
    x: xAt(index),
    y: value === null ? 0 : yAt(value),
    value,
  }));
  const pointStep = Math.abs(xAt(1) - xAt(0)) || 2;
  const barWidth = Math.min(12, Math.max(1.2, pointStep * 0.48));
  const barHtml = bars.map((value, index) => {
    if (value === null) return "";
    const y = yAt(value);
    const barTop = Math.min(y, zeroY);
    const barHeight = Math.max(Math.abs(y - zeroY), 2);
    const tone = value >= 0 ? "up" : "down";
    return `<rect class="indicator-histogram ${tone}" x="${(xAt(index) - barWidth / 2).toFixed(1)}" y="${barTop.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="2"></rect>`;
  }).join("");
  const primaryMarkers = primaryPoints.map((point, index) => (
    !Number.isFinite(point.value) || !Number.isFinite(point.x) || !Number.isFinite(point.y)
      ? ""
      : `<circle class="chart-indicator-point is-primary" data-index="${index}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4"></circle>`
  )).join("");
  const secondaryMarkers = secondaryPoints.map((point, index) => (
    !Number.isFinite(point.value) || !Number.isFinite(point.x) || !Number.isFinite(point.y)
      ? ""
      : `<circle class="chart-indicator-point is-secondary" data-index="${index}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4"></circle>`
  )).join("");
  const tertiaryMarkers = tertiaryPoints.map((point, index) => (
    !Number.isFinite(point.value) || !Number.isFinite(point.x) || !Number.isFinite(point.y)
      ? ""
      : `<circle class="chart-indicator-point is-tertiary" data-index="${index}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4"></circle>`
  )).join("");

  return `
    <g class="combined-indicator-panel">
      <text class="combined-indicator-title" x="12" y="${top + 18}">${title}</text>
      <line class="combined-indicator-boundary" x1="${pad.left}" y1="${top}" x2="${width - pad.right}" y2="${top}"></line>
      <line class="indicator-zero-line" x1="${pad.left}" y1="${zeroY}" x2="${width - pad.right}" y2="${zeroY}"></line>
      ${barHtml}
      <path class="indicator-line-primary" d="${buildPath(primaryPoints)}"></path>
      ${secondaryValues.length ? `<path class="indicator-line-secondary" d="${buildPath(secondaryPoints)}"></path>` : ""}
      ${tertiaryValues.length ? `<path class="indicator-line-tertiary" d="${buildPath(tertiaryPoints)}"></path>` : ""}
      ${primaryMarkers}
      ${secondaryMarkers}
      ${tertiaryMarkers}
    </g>
  `;
}
async function fetchDerivativesApi(url, timeoutMs = 30000) {
  try {
    const response = await fetchWithTimeout(url, { cache: "no-store" }, timeoutMs);
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      return { data: null, error: payload?.error?.message || `HTTP ${response.status}` };
    }
    return { data: payload.data, error: "" };
  } catch (error) {
    return { data: null, error: error?.message || String(error) };
  }
}
function twEtfWeightText(value) {
  const weight = Number(value);
  if (!Number.isFinite(weight)) return "--";
  return `${weight.toFixed(Math.abs(weight % 1) > 0 ? 1 : 0)}%`;
}
renderSharedNavigation();

/* shadow-input:js/charts.js */
function renderSectorLineChart(sector) {
  const closes = (sector.candles || [])
    .map((candle) => parseMarketNumber(candle.close))
    .filter((value) => value !== null);

  if (closes.length < 2) {
    return renderSectorSnapshotLineChart(sector);
  }

  const width = 180;
  const height = 56;
  const pad = 6;
  const minValue = Math.min(...closes);
  const maxValue = Math.max(...closes);
  const range = maxValue - minValue || 1;
  const step = (width - pad * 2) / Math.max(closes.length - 1, 1);
  const points = closes.map((value, index) => {
    const x = pad + index * step;
    const y = height - pad - ((value - minValue) / range) * (height - pad * 2);
    return { x, y, value };
  });

  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");

  return `
    <svg class="class-line-chart ${toneClass(sector.tone)}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${sector.name} performance chart">
      <path class="class-line-track" d="${path}"></path>
      <circle class="class-line-end" cx="${points[points.length - 1].x.toFixed(1)}" cy="${points[points.length - 1].y.toFixed(1)}" r="3"></circle>
    </svg>
  `;
}
function renderSectorSnapshotLineChart(sector) {
  const previousClose = parseMarketNumber(sector?.previousClose);
  const open = parseMarketNumber(sector?.open);
  const low = parseMarketNumber(sector?.low);
  const high = parseMarketNumber(sector?.high);
  const close = parseMarketNumber(sector?.value ?? sector?.close);
  const points = [
    { label: "昨收", value: previousClose },
    { label: "開盤", value: open },
    { label: "最低", value: low },
    { label: "最高", value: high },
    { label: "最新", value: close },
  ].filter((point) => Number.isFinite(point.value));

  if (points.length < 2) {
    return '<div class="class-line-empty class-line-empty-compact">資料同步中</div>';
  }

  const width = 180;
  const height = 56;
  const pad = 6;
  const values = points.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue;
  const step = (width - pad * 2) / Math.max(points.length - 1, 1);
  const yAt = (value) => range === 0
    ? height / 2
    : height - pad - ((value - minValue) / range) * (height - pad * 2);
  const svgPoints = points.map((point, index) => ({
    ...point,
    x: pad + index * step,
    y: yAt(point.value),
  }));
  const path = svgPoints
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    .join(" ");
  const baseLine = Number.isFinite(previousClose)
    ? `<line class="class-line-base" x1="${pad}" y1="${yAt(previousClose).toFixed(1)}" x2="${width - pad}" y2="${yAt(previousClose).toFixed(1)}"></line>`
    : "";
  const endPoint = svgPoints[svgPoints.length - 1];
  const title = `${sector?.name || "類股"} 日內區間：${points.map((point) => `${point.label} ${point.value}`).join("，")}`;

  return `
    <svg class="class-line-chart class-line-chart-snapshot ${toneClass(sector?.tone)}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
      ${baseLine}
      <path class="class-line-track" d="${path}"></path>
      <circle class="class-line-end" cx="${endPoint.x.toFixed(1)}" cy="${endPoint.y.toFixed(1)}" r="3"></circle>
    </svg>
  `;
}
function renderVixSparkline(series = []) {
  const points = (Array.isArray(series) ? series : [])
    .map((item) => ({
      date: item.date || "",
      value: parseMarketNumber(item.value),
    }))
    .filter((item) => Number.isFinite(item.value));
  if (points.length < 2) {
    return '<div class="vix-sparkline-empty">VIX 走勢資料同步中</div>';
  }

  const width = 320;
  const height = 104;
  const pad = { top: 14, right: 12, bottom: 22, left: 12 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const minValue = Math.min(...points.map((item) => item.value));
  const maxValue = Math.max(...points.map((item) => item.value));
  const span = maxValue - minValue || 1;
  const xAt = (index) => pad.left + (points.length === 1 ? 0 : (index / (points.length - 1)) * plotWidth);
  const yAt = (value) => pad.top + (1 - ((value - minValue) / span)) * plotHeight;
  const path = points
    .map((point, index) => `${index ? "L" : "M"} ${xAt(index).toFixed(1)} ${yAt(point.value).toFixed(1)}`)
    .join(" ");
  const latest = points.at(-1);
  const first = points[0];
  const toneClassName = latest.value >= first.value ? "is-up" : "is-down";

  return `
    <div class="vix-sparkline ${toneClassName}" aria-label="VIX 近期走勢圖">
      <svg viewBox="0 0 ${width} ${height}" role="img">
        <line x1="${pad.left}" y1="${yAt(maxValue).toFixed(1)}" x2="${width - pad.right}" y2="${yAt(maxValue).toFixed(1)}"></line>
        <line x1="${pad.left}" y1="${yAt(minValue).toFixed(1)}" x2="${width - pad.right}" y2="${yAt(minValue).toFixed(1)}"></line>
        <path d="${path}"></path>
        <circle cx="${xAt(points.length - 1).toFixed(1)}" cy="${yAt(latest.value).toFixed(1)}" r="4"></circle>
        <text x="${pad.left}" y="${height - 5}">${first.date.slice(5) || first.date}</text>
        <text x="${width - pad.right}" y="${height - 5}" text-anchor="end">${latest.date.slice(5) || latest.date}</text>
      </svg>
      <div>
        <span>區間</span>
        <strong>${minValue.toFixed(2)} - ${maxValue.toFixed(2)}</strong>
      </div>
    </div>
  `;
}
function bindHorizontalChartPan(frame, onPan) {
  if (!frame) return;
  let startX = null;
  frame.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    startX = event.clientX;
    frame.setPointerCapture?.(event.pointerId);
    frame.classList.add("is-panning");
  });
  frame.addEventListener("pointerup", (event) => {
    if (startX === null) return;
    const distance = event.clientX - startX;
    startX = null;
    frame.classList.remove("is-panning");
    if (Math.abs(distance) < 28) return;
    onPan(distance > 0 ? "older" : "newer");
  });
  frame.addEventListener("pointercancel", () => {
    startX = null;
    frame.classList.remove("is-panning");
  });
}
function getChartHistory(detail, interval) {
  const history = normalizeHistory(detail);
  const aggregated = aggregateHistory(history, interval);
  const limits = {
    day: 300,
    week: 260,
    month: 240,
    quarter: 40,
    half: 30,
    year: 20,
    all: aggregated.length,
  };
  return aggregated.slice(-(limits[interval] || aggregated.length));
}
function getChartIntervalLabel(interval) {
  return {
    day: "日線",
    week: "週線",
    month: "月線",
    quarter: "季線",
    half: "半年",
    year: "年線",
    all: "全部",
  }[interval] || "日線";
}
function renderIndicatorChart(detail, interval, indicator, visibleCount = null, panOffset = 0) {
  const fullHistory = getChartHistory(detail, interval);
  const requestedCount = Number(visibleCount);
  const history = Number.isFinite(requestedCount) && requestedCount > 1
    ? sliceVisibleWindow(fullHistory, requestedCount, panOffset)
    : fullHistory;
  if (history.length < 2) {
    return '<div class="stock-detail-empty">查無指標資料。</div>';
  }

  const width = 980;
  const height = 420;
  const pad = { top: 34, right: 28, bottom: 72, left: 58 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const step = plotWidth / Math.max(history.length - 1, 1);
  const xAt = (index) => pad.left + index * step;
  const firstDate = history[0]?.date || "";
  const lastDate = history[history.length - 1]?.date || "";
  const modeLabel = getChartIntervalLabel(interval);
  let title = "";
  let latestLabel = "--";
  let series = [];
  let bars = [];
  let fixedMin = null;
  let fixedMax = null;

  if (indicator === "kd") {
    const kd = calculateKd(history);
    title = "KD 指標";
    latestLabel = `K ${kd[kd.length - 1].k.toFixed(2)} / D ${kd[kd.length - 1].d.toFixed(2)}`;
    fixedMin = 0;
    fixedMax = 100;
    series = [
      { className: "indicator-line-primary", values: kd.map((item) => item.k) },
      { className: "indicator-line-secondary", values: kd.map((item) => item.d) },
    ];
  } else if (indicator === "macd") {
    const macd = calculateMacd(history);
    title = "MACD 指標";
    const latest = macd[macd.length - 1];
    latestLabel = `DIF ${latest.dif?.toFixed(2) || "--"} / MACD ${latest.macd?.toFixed(2) || "--"}`;
    series = [
      { className: "indicator-line-primary", values: macd.map((item) => item.dif) },
      { className: "indicator-line-secondary", values: macd.map((item) => item.macd) },
    ];
    bars = macd.map((item) => item.osc);
  } else if (indicator === "rsi") {
    const rsi = calculateRsi(history);
    title = "RSI 指標";
    latestLabel = `RSI ${rsi[rsi.length - 1]?.toFixed(2) || "--"}`;
    fixedMin = 0;
    fixedMax = 100;
    series = [{ className: "indicator-line-primary", values: rsi }];
  } else if (indicator === "dmi") {
    const dmi = calculateDmi(history);
    title = "DMI 指標";
    const latest = dmi[dmi.length - 1] || {};
    latestLabel = `+DI ${latest.plusDi?.toFixed(2) || "--"} / -DI ${latest.minusDi?.toFixed(2) || "--"} / ADX ${latest.adx?.toFixed(2) || "--"}`;
    fixedMin = 0;
    fixedMax = 100;
    series = [
      { className: "indicator-line-primary", values: dmi.map((item) => item.plusDi) },
      { className: "indicator-line-secondary", values: dmi.map((item) => item.minusDi) },
      { className: "indicator-line-tertiary", values: dmi.map((item) => item.adx) },
    ];
  } else if (indicator === "obv") {
    const obv = calculateObv(history);
    title = "OBV 指標";
    latestLabel = `OBV ${Math.round(obv[obv.length - 1] || 0).toLocaleString("zh-TW")}`;
    series = [{ className: "indicator-line-primary", values: obv }];
  } else {
    const bias = calculateBias(history);
    title = "BIAS";
    latestLabel = `BIAS6 ${bias[bias.length - 1]?.toFixed(2) || "--"}%`;
    series = [{ className: "indicator-line-primary", values: bias }];
  }

  const values = [...series.flatMap((item) => item.values), ...bars].filter((value) => value !== null && Number.isFinite(value));
  const minValue = fixedMin ?? Math.min(...values, 0);
  const maxValue = fixedMax ?? Math.max(...values, 0);
  const valueRange = maxValue - minValue || 1;
  const yAt = (value) => pad.top + ((maxValue - value) / valueRange) * plotHeight;
  const zeroY = yAt(Math.min(Math.max(0, minValue), maxValue));

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * plotHeight;
    const label = maxValue - ratio * valueRange;
    return `
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line>
      <text x="12" y="${y + 5}">${label.toFixed(2)}</text>
    `;
  }).join("");

  const lineHtml = series.map((item) => {
    const points = item.values.map((value, index) => ({
      x: xAt(index),
      y: value === null ? 0 : yAt(value),
      value,
    }));
    return `<path class="${item.className}" d="${buildPath(points)}"></path>`;
  }).join("");

  const barWidth = Math.min(14, Math.max(1.2, step * 0.5));
  const barHtml = bars.map((value, index) => {
    if (value === null) return "";
    const y = yAt(value);
    const top = Math.min(y, zeroY);
    const heightValue = Math.max(Math.abs(y - zeroY), 2);
    const tone = value >= 0 ? "up" : "down";
    return `<rect class="indicator-histogram ${tone}" x="${(xAt(index) - barWidth / 2).toFixed(1)}" y="${top.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${heightValue.toFixed(1)}" rx="2"></rect>`;
  }).join("");

  return `
    <div class="chart-summary">
      <span>${detail.code} ${detail.name} / ${modeLabel} / ${title}</span>
      <strong>${latestLabel}</strong>
      <span>${firstDate} - ${lastDate}</span>
    </div>
    <svg class="technical-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${detail.code} ${detail.name} ${title} 指標圖">
      <g class="chart-grid">${gridLines}</g>
      <line class="indicator-zero-line" x1="${pad.left}" y1="${zeroY}" x2="${width - pad.right}" y2="${zeroY}"></line>
      <g>${barHtml}</g>
      ${lineHtml}
      <g class="chart-labels">
        <text x="${pad.left}" y="${height - 24}">${firstDate}</text>
        <text x="${width - pad.right - 90}" y="${height - 24}">${lastDate}</text>
      <text class="chart-ma-label" x="${width - pad.right - 238}" y="24">${modeLabel} / ${title}</text>
      </g>
    </svg>
  `;
}
function renderTechnicalChart(detail, interval = "day", overlayIndicators = [], maPeriods = [5], visibleCount = null, panOffset = 0, panelIndicators = ["kd"]) {
  const fullHistory = getChartHistory(detail, interval);
  const requestedCount = Number(visibleCount);
  const history = Number.isFinite(requestedCount) && requestedCount > 1
    ? sliceVisibleWindow(fullHistory, requestedCount, panOffset)
    : fullHistory;

  if (history.length < 2) {
    return '<div class="stock-detail-empty">無可用技術圖資料。</div>';
  }

  const width = 980;
  const isSnapshotHistory = detail.isFallbackHistory || history.length < 6;
  const hasTechnicalIndicators = history.length >= 6;
  const pad = { top: 34, right: 28, bottom: 72, left: 58 };
  const priceHeight = 300;
  const volumeTop = pad.top + priceHeight + 42;
  const volumeHeight = 76;
  const indicatorStartTop = volumeTop + volumeHeight + 42;
  const indicatorHeight = 118;
  const indicatorGap = 32;
  const activePanelIndicators = (Array.isArray(panelIndicators) ? panelIndicators : [panelIndicators])
    .filter((item) => TECHNICAL_PANEL_INDICATOR_KEYS.includes(item));
  const selectedPanelIndicators = activePanelIndicators.length ? activePanelIndicators : ["kd"];
  const indicatorCount = selectedPanelIndicators.length;
  const height = hasTechnicalIndicators
    ? indicatorStartTop + (indicatorHeight + indicatorGap) * (indicatorCount - 1) + indicatorHeight + pad.bottom
    : 520;
  const plotWidth = width - pad.left - pad.right;
  const closes = history.map((day) => day.close);
  const activeOverlayIndicators = (Array.isArray(overlayIndicators) ? overlayIndicators : [overlayIndicators])
    .filter((item) => ["bollinger", "fibonacci", "supportResistance", "smc"].includes(item));
  const activeMaPeriods = [...new Set(maPeriods)].filter((period) => [5, 10, 20, 60, 120, 240].includes(period));
  const maSeries = activeMaPeriods.map((period) => ({
    period,
    values: movingAverage(closes, period),
  }));
  const bollinger = activeOverlayIndicators.includes("bollinger") ? calculateBollingerBands(history) : [];
  const fibonacci = activeOverlayIndicators.includes("fibonacci") ? calculateFibonacciRetracement(history, Math.min(80, history.length)) : null;
  const supportResistance = activeOverlayIndicators.includes("supportResistance") ? calculateSupportResistance(history, Math.min(80, history.length)) : null;
  const smc = activeOverlayIndicators.includes("smc") ? calculateSmartMoneyConcepts(history, Math.min(90, history.length)) : null;
  const overlayValues = [
    ...bollinger.flatMap((item) => [item.upper, item.middle, item.lower]),
    ...(fibonacci?.levels || []).map((item) => item.value),
    ...(supportResistance?.supports || []).map((item) => item.value),
    ...(supportResistance?.resistances || []).map((item) => item.value),
    ...(smc?.levels || []).flatMap((item) => [item.value, item.upper, item.lower]),
  ].filter(Number.isFinite);
  const priceValues = history
    .flatMap((day, index) => [day.high, day.low, ...maSeries.map((series) => series.values[index])])
    .concat(overlayValues)
    .filter((value) => value !== null);
  const rawMinPrice = Math.min(...priceValues);
  const rawMaxPrice = Math.max(...priceValues);
  const rawPriceRange = rawMaxPrice - rawMinPrice;
  const pricePadding = Math.max(rawPriceRange * 0.08, Math.abs(rawMaxPrice) * 0.005, 0.01);
  const minPrice = rawMinPrice - pricePadding;
  const maxPrice = rawMaxPrice + pricePadding;
  const priceRange = maxPrice - minPrice || 1;
  const maxVolume = Math.max(...history.map((day) => day.volume || 0), 1);
  const displaySlots = Math.max(history.length, 30);
  const step = plotWidth / Math.max(displaySlots - 1, 1);
  const xStart = pad.left + (displaySlots - history.length) * step;
  const candleWidth = Math.min(16, Math.max(1.2, step * 0.48));
  const priceY = (value) => pad.top + ((maxPrice - value) / priceRange) * priceHeight;
  const volumeY = (value) => volumeTop + volumeHeight - ((value || 0) / maxVolume) * volumeHeight;
  const xAt = (index) => xStart + index * step;

  const closePoints = history.map((day, index) => ({
    x: xAt(index),
    y: priceY(day.close),
    value: day.close,
  }));
  const maPaths = maSeries.map((series) => {
    const points = series.values.map((value, index) => ({
      x: xAt(index),
      y: value === null ? 0 : priceY(value),
      value,
    }));
    return `<path class="chart-ma-line ma-${series.period}" d="${buildPath(points)}"></path>`;
  }).join("");

  const buildOverlayMarkup = () => {
    const renderPriceLevel = (level, className, label, dash = false) => {
      if (!Number.isFinite(level)) return "";
      const y = priceY(level);
      return `
        <g class="${className}">
          <line x1="${pad.left}" y1="${y.toFixed(1)}" x2="${width - pad.right}" y2="${y.toFixed(1)}" ${dash ? 'stroke-dasharray="6 6"' : ""}></line>
          <text x="${width - pad.right - 4}" y="${(y - 5).toFixed(1)}" text-anchor="end">${label}</text>
        </g>
      `;
    };

    const bollingerOverlay = activeOverlayIndicators.includes("bollinger") ? (() => {
      const upperPoints = bollinger.map((item, index) => ({ x: xAt(index), y: item.upper === null ? 0 : priceY(item.upper), value: item.upper }));
      const middlePoints = bollinger.map((item, index) => ({ x: xAt(index), y: item.middle === null ? 0 : priceY(item.middle), value: item.middle }));
      const lowerPoints = bollinger.map((item, index) => ({ x: xAt(index), y: item.lower === null ? 0 : priceY(item.lower), value: item.lower }));
      const latestBand = bollinger.at(-1);
      return `
        <g class="chart-overlay bollinger-overlay">
          <path class="bollinger-band-line is-upper" d="${buildPath(upperPoints)}"></path>
          <path class="bollinger-band-line is-middle" d="${buildPath(middlePoints)}"></path>
          <path class="bollinger-band-line is-lower" d="${buildPath(lowerPoints)}"></path>
          <text x="${pad.left}" y="24">布林通道 ${latestBand?.bandwidth ? `帶寬 ${latestBand.bandwidth.toFixed(1)}%` : ""}</text>
        </g>
      `;
    })() : "";

    const fibonacciOverlay = activeOverlayIndicators.includes("fibonacci") && fibonacci ? `
      <g class="chart-overlay fibonacci-overlay">
        ${fibonacci.levels.map((level) => renderPriceLevel(level.value, "fibonacci-level", `Fib ${level.label} ${level.value.toFixed(2)}`, true)).join("")}
        <text x="${pad.left}" y="24">${fibonacci.upSwing ? "上升波回撤" : "下降波反彈"}：${fibonacci.lowPoint.value.toFixed(2)} - ${fibonacci.highPoint.value.toFixed(2)}</text>
      </g>
    ` : "";

    const supportResistanceOverlay = activeOverlayIndicators.includes("supportResistance") && supportResistance ? `
      <g class="chart-overlay support-resistance-overlay">
        ${(supportResistance.supports || []).map((item) => renderPriceLevel(item.value, "support-level", `支撐 ${item.value.toFixed(2)} (${item.touches})`)).join("")}
        ${(supportResistance.resistances || []).map((item) => renderPriceLevel(item.value, "resistance-level", `壓力 ${item.value.toFixed(2)} (${item.touches})`)).join("")}
        <text x="${pad.left}" y="24">Support and Resistance</text>
      </g>
    ` : "";

    const smcOverlay = activeOverlayIndicators.includes("smc") && smc ? `
      <g class="chart-overlay smc-overlay">
        ${(smc.levels || []).map((item) => {
          if (Number.isFinite(item.upper) && Number.isFinite(item.lower)) {
            const yTop = priceY(Math.max(item.upper, item.lower));
            const yBottom = priceY(Math.min(item.upper, item.lower));
            return `
              <rect class="smc-zone ${item.type}" x="${pad.left}" y="${yTop.toFixed(1)}" width="${plotWidth}" height="${Math.max(yBottom - yTop, 3).toFixed(1)}" rx="6"></rect>
              <text x="${pad.left + 8}" y="${(yTop + 14).toFixed(1)}">${item.label}</text>
            `;
          }
          return renderPriceLevel(item.value, `smc-level ${item.type}`, `${item.label} ${item.value.toFixed(2)}`, true);
        }).join("")}
        <text x="${pad.left}" y="24">SMC：${smc.signals?.[0] || "觀察 BOS / 流動性 / FVG"}</text>
      </g>
    ` : "";
    return `${bollingerOverlay}${fibonacciOverlay}${supportResistanceOverlay}${smcOverlay}`;
  };
  const overlayHtml = buildOverlayMarkup();

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
    const y = pad.top + ratio * priceHeight;
    const label = maxPrice - ratio * priceRange;
    return `
      <line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}"></line>
      <text x="12" y="${y + 5}">${label.toFixed(2)}</text>
    `;
  }).join("");

  const candles = history.map((day, index) => {
    const x = xAt(index);
    const openY = priceY(day.open ?? day.close);
    const closeY = priceY(day.close);
    const highY = priceY(day.high ?? day.close);
    const lowY = priceY(day.low ?? day.close);
    const bodyTop = Math.min(openY, closeY);
    const bodyHeight = Math.max(Math.abs(openY - closeY), 3);
    const open = day.open ?? day.close;
    const tone = day.close > open ? "up" : day.close < open ? "down" : "flat";
    return `
      <line class="candle-wick technical-candle-wick ${tone}" x1="${x.toFixed(1)}" y1="${highY.toFixed(1)}" x2="${x.toFixed(1)}" y2="${lowY.toFixed(1)}"></line>
      <rect class="candle-body technical-candle-body ${tone}" x="${(x - candleWidth / 2).toFixed(1)}" y="${bodyTop.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${bodyHeight.toFixed(1)}" rx="2"></rect>
    `;
  }).join("");

  const volumeBars = history.map((day, index) => {
    const x = xAt(index);
    const y = volumeY(day.volume);
    const barHeight = volumeTop + volumeHeight - y;
    const open = day.open ?? day.close;
    const tone = day.close > open ? "up" : day.close < open ? "down" : "flat";
    return `<rect class="technical-volume-bar ${tone}" x="${(x - candleWidth / 2).toFixed(1)}" y="${y.toFixed(1)}" width="${candleWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="2"></rect>`;
  }).join("");

  const kd = hasTechnicalIndicators ? calculateKd(history) : [];
  const macd = history.length >= 26 ? calculateMacd(history) : [];
  const rsi = history.length >= 14 ? calculateRsi(history) : [];
  const bias = hasTechnicalIndicators ? calculateBias(history) : [];
  const dmi = history.length >= 15 ? calculateDmi(history) : [];
  const obv = hasTechnicalIndicators ? calculateObv(history) : [];
  const atr = history.length >= 15 ? calculateAtr(history) : [];
  const cci = history.length >= 20 ? calculateCci(history) : [];
  const williams = history.length >= 14 ? calculateWilliamsR(history) : [];
  const mfi = history.length >= 15 ? calculateMfi(history) : [];
  const momentum = history.length >= 11 ? calculateMomentum(history) : [];
  const sar = history.length >= 4 ? calculateParabolicSarSeries(history) : [];
  const panelBollinger = history.length >= 20 ? calculateBollingerBands(history) : [];
  const ichimoku = history.length >= 9 ? calculateIchimoku(history) : [];
  const hoverBottom = hasTechnicalIndicators
    ? indicatorStartTop + (indicatorHeight + indicatorGap) * (indicatorCount - 1) + indicatorHeight
    : volumeTop + volumeHeight;
  const crosshairBottom = height - 18;

  const buildHoverZones = () => {
    // Transparent hover zones — one per candle, covering the full chart stack.
    const hoverZoneWidth = Math.max(step, candleWidth + 4);
    return history.map((day, index) => {
      const x = xAt(index);
      const left = Math.max(pad.left, x - hoverZoneWidth / 2);
      const right = Math.min(width - pad.right, x + hoverZoneWidth / 2);
      const zoneW = right - left;
      const rawChange = typeof day.change === "number" ? day.change : parseFloat(day.change);
      const changeStr = Number.isFinite(rawChange)
        ? (rawChange >= 0 ? "+" : "") + rawChange.toFixed(2)
        : "--";
      return `<rect class="chart-hover-zone"
        x="${left.toFixed(1)}" y="${pad.top}"
        width="${Math.max(zoneW, 8).toFixed(1)}" height="${hoverBottom - pad.top}"
        data-index="${index}"
        data-date="${day.date ?? ""}"
        data-open="${day.open ?? "--"}"
        data-high="${day.high ?? "--"}"
        data-low="${day.low ?? "--"}"
        data-close="${day.close ?? "--"}"
        data-change="${changeStr}"
        data-volume="${typeof day.volume === "number" ? day.volume.toLocaleString() : (day.volume ?? "--")}"
        data-k="${kd[index]?.k?.toFixed(2) ?? "--"}"
        data-d="${kd[index]?.d?.toFixed(2) ?? "--"}"
        data-dif="${macd[index]?.dif?.toFixed(2) ?? "--"}"
        data-macd="${macd[index]?.macd?.toFixed(2) ?? "--"}"
        data-osc="${macd[index]?.osc?.toFixed(2) ?? "--"}"
        data-rsi="${rsi[index]?.toFixed(2) ?? "--"}"
        data-bias="${bias[index]?.toFixed(2) ?? "--"}"
        data-plus-di="${dmi[index]?.plusDi?.toFixed(2) ?? "--"}"
        data-minus-di="${dmi[index]?.minusDi?.toFixed(2) ?? "--"}"
        data-adx="${dmi[index]?.adx?.toFixed(2) ?? "--"}"
        data-obv="${obv[index] !== undefined ? Math.round(obv[index]).toLocaleString() : "--"}"
        data-atr="${atr[index]?.toFixed(2) ?? "--"}"
        data-cci="${cci[index]?.toFixed(2) ?? "--"}"
        data-williams="${williams[index]?.toFixed(2) ?? "--"}"
        data-mfi="${mfi[index]?.toFixed(2) ?? "--"}"
        data-momentum="${momentum[index]?.toFixed(2) ?? "--"}"
        data-sar="${sar[index]?.toFixed(2) ?? "--"}"
        data-bollinger="${panelBollinger[index]?.upper ? `${panelBollinger[index].lower.toFixed(2)} / ${panelBollinger[index].upper.toFixed(2)}` : "--"}"
        data-ichimoku="${ichimoku[index]?.tenkan ? `${ichimoku[index].tenkan.toFixed(2)} / ${ichimoku[index].kijun?.toFixed(2) || "--"} / ${ichimoku[index].senkouB?.toFixed(2) || "--"}` : "--"}"
      ></rect>`;
    }).join("");
  };
  const hoverZones = buildHoverZones();

  const firstDate = history[0]?.date || "";
  const lastDate = history[history.length - 1]?.date || "";
  const latest = history[history.length - 1];
  const buildCombinedIndicators = () => {
    const buildPanelConfig = (key, index) => {
      const top = indicatorStartTop + (indicatorHeight + indicatorGap) * index;
      const baseConfig = {
        top,
        height: indicatorHeight,
        width,
        pad,
        xAt,
      };
      const configs = {
        kd: {
          title: "KD",
          ...baseConfig,
          values: kd.map((item) => item.k),
          secondaryValues: kd.map((item) => item.d),
          fixedMin: 0,
          fixedMax: 100,
        },
        macd: {
          title: "MACD",
          ...baseConfig,
          values: macd.map((item) => item.dif),
          secondaryValues: macd.map((item) => item.macd),
          bars: macd.map((item) => item.osc),
        },
        rsi: {
          title: "RSI",
          ...baseConfig,
          values: rsi,
          fixedMin: 0,
          fixedMax: 100,
        },
        bias: {
          title: "BIAS",
          ...baseConfig,
          values: bias,
        },
        dmi: {
          title: "DMI (+DI / -DI / ADX)",
          ...baseConfig,
          values: dmi.map((item) => item.plusDi),
          secondaryValues: dmi.map((item) => item.minusDi),
          tertiaryValues: dmi.map((item) => item.adx),
          fixedMin: 0,
          fixedMax: 100,
        },
        obv: {
          title: "OBV",
          ...baseConfig,
          values: obv,
        },
        atr: {
          title: "ATR",
          ...baseConfig,
          values: atr,
        },
        cci: {
          title: "CCI",
          ...baseConfig,
          values: cci,
        },
        williams: {
          title: "Williams %R",
          ...baseConfig,
          values: williams,
          fixedMin: -100,
          fixedMax: 0,
        },
        mfi: {
          title: "MFI",
          ...baseConfig,
          values: mfi,
          fixedMin: 0,
          fixedMax: 100,
        },
        momentum: {
          title: "Momentum",
          ...baseConfig,
          values: momentum,
        },
        sar: {
          title: "SAR / Close",
          ...baseConfig,
          values: history.map((item) => item.close),
          secondaryValues: sar,
        },
        bollinger: {
          title: "Bollinger",
          ...baseConfig,
          values: panelBollinger.map((item) => item.lower),
          secondaryValues: panelBollinger.map((item) => item.middle),
          tertiaryValues: panelBollinger.map((item) => item.upper),
        },
        ichimoku: {
          title: "Ichimoku",
          ...baseConfig,
          values: ichimoku.map((item) => item.tenkan),
          secondaryValues: ichimoku.map((item) => item.kijun),
          tertiaryValues: ichimoku.map((item) => item.senkouB),
        },
      };
      return configs[key] || configs.kd;
    };

    return hasTechnicalIndicators
      ? selectedPanelIndicators.map((key, index) => renderCombinedIndicatorPanel(buildPanelConfig(key, index))).join("")
      : "";
  };
  const combinedIndicators = buildCombinedIndicators();
  const modeLabel = {
    day: "日線",
    week: "週線",
    month: "月線",
    all: "全部",
  }[interval] || "日線";
  const overlayLabels = {
    bollinger: "布林通道",
    fibonacci: "斐波那契回撤",
    supportResistance: "支撐壓力",
    smc: "Smart Money Concepts",
  };
  const baseLabel = activeMaPeriods.length ? activeMaPeriods.map((period) => `MA${period}`).join(" ") : "K 線";
  const indicatorLabel = [baseLabel, ...activeOverlayIndicators.map((key) => overlayLabels[key] || key)].join(" / ");
  const panelLabels = {
    kd: "KD",
    macd: "MACD",
    rsi: "RSI",
    dmi: "DMI",
    bias: "BIAS",
    obv: "OBV",
    atr: "ATR",
    cci: "CCI",
    williams: "Williams %R",
    mfi: "MFI",
    momentum: "Momentum",
    sar: "SAR",
    bollinger: "Bollinger",
    ichimoku: "Ichimoku",
  };
  const panelLabel = selectedPanelIndicators.map((key) => panelLabels[key] || key).join(" / ");

  const renderChartMarkup = () => `
      <div class="chart-summary">
        <span>${detail.code} ${detail.name} / ${modeLabel} / ${indicatorLabel} / 下方指標：${panelLabel}</span>
        <strong>${latest?.close?.toLocaleString() || "--"}</strong>
        <span>${firstDate} - ${lastDate}</span>
      </div>
      ${isSnapshotHistory ? '<p class="chart-data-notice">目前為快取行情快照；歷史資料同步完成後會自動更新完整 K 線與技術指標。</p>' : ""}
      <div class="sector-chart-frame">
        <svg class="technical-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${detail.code} ${detail.name} technical chart">
          <g class="chart-grid">${gridLines}</g>
          <g>${candles}</g>
          <path class="chart-line technical-price-line" d="${buildPath(closePoints)}"></path>
          ${maPaths}
          ${overlayHtml}
          <g class="chart-volume-bars">${volumeBars}</g>
          ${combinedIndicators}
          <g class="chart-labels">
            <text x="${pad.left}" y="${height - 24}">${firstDate}</text>
            <text x="${width - pad.right - 90}" y="${height - 24}">${lastDate}</text>
            <text x="${pad.left}" y="${volumeTop - 12}">成交量</text>
            <text class="chart-ma-label" x="${width - pad.right - 238}" y="24">${modeLabel} / ${indicatorLabel}</text>
          </g>
          <g class="chart-hover-zones">${hoverZones}</g>
          <line class="chart-crosshair" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${crosshairBottom}" style="display:none"></line>
        </svg>
        <div class="sector-sync-tooltip chart-kline-tooltip" hidden></div>
      </div>
    `;
  return renderChartMarkup();
}
function bindChartHover(chartView) {
  if (!chartView) return;
  const tooltip = chartView.querySelector(".chart-kline-tooltip");
  const crosshair = chartView.querySelector(".chart-crosshair");
  if (!tooltip) return;

  const zones = chartView.querySelectorAll(".chart-hover-zone");

  const hide = () => {
    tooltip.hidden = true;
    if (crosshair) crosshair.style.display = "none";
    chartView.querySelectorAll(".chart-indicator-point.is-active").forEach((point) => {
      point.classList.remove("is-active");
    });
  };

  const positionTooltip = (event, frame) => {
    const frameRect = frame.getBoundingClientRect();
    const tooltipWidth = tooltip.offsetWidth || 230;
    const tooltipHeight = tooltip.offsetHeight || 330;
    const pointerX = event.clientX - frameRect.left;
    const pointerY = event.clientY - frameRect.top;
    const gap = 14;

    let left = pointerX + gap;
    if (left + tooltipWidth > frameRect.width - 6) {
      left = pointerX - tooltipWidth - gap;
    }
    left = Math.max(6, Math.min(left, frameRect.width - tooltipWidth - 6));

    let top = pointerY - tooltipHeight / 2;
    top = Math.max(6, Math.min(top, frameRect.height - tooltipHeight - 6));

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
    tooltip.style.transform = "none";
  };

  zones.forEach((zone) => {
    zone.addEventListener("mouseenter", (event) => {
      const d = zone.dataset;
      const changeVal = parseFloat(d.change);
      const changeCls = isNaN(changeVal) ? "" : changeVal > 0 ? "up" : changeVal < 0 ? "down" : "flat";

      tooltip.hidden = false;
      tooltip.innerHTML = `
        <strong style="font-size:0.9rem;margin-bottom:4px;display:block">${d.date}</strong>
        <span>開　盤：<strong>${d.open}</strong></span>
        <span>最　高：<strong class="up">${d.high}</strong></span>
        <span>最　低：<strong class="down">${d.low}</strong></span>
        <span>收　盤：<strong>${d.close}</strong></span>
        <span>漲　跌：<strong class="${changeCls}">${d.change}</strong></span>
        <span>成交量：<strong>${d.volume}</strong></span>
        <span class="chart-tooltip-divider">KD：<strong>K ${d.k} / D ${d.d}</strong></span>
        <span>MACD：<strong>${d.dif} / ${d.macd}</strong></span>
        <span>OSC：<strong>${d.osc}</strong></span>
        <span>RSI：<strong>${d.rsi}</strong></span>
        <span>BIAS：<strong>${d.bias === "--" ? "--" : `${d.bias}%`}</strong></span>
        <span>DMI：<strong>+DI ${d.plusDi} / -DI ${d.minusDi} / ADX ${d.adx}</strong></span>
        <span>OBV：<strong>${d.obv}</strong></span>
        <span>ATR：<strong>${d.atr}</strong></span>
        <span>CCI：<strong>${d.cci}</strong></span>
        <span>Williams %R：<strong>${d.williams}</strong></span>
        <span>MFI：<strong>${d.mfi}</strong></span>
        <span>Momentum：<strong>${d.momentum}</strong></span>
        <span>SAR：<strong>${d.sar}</strong></span>
        <span>Bollinger：<strong>${d.bollinger}</strong></span>
        <span>Ichimoku：<strong>${d.ichimoku}</strong></span>
      `;

      chartView.querySelectorAll(".chart-indicator-point.is-active").forEach((point) => {
        point.classList.remove("is-active");
      });
      chartView.querySelectorAll(`.chart-indicator-point[data-index="${d.index}"]`).forEach((point) => {
        point.classList.add("is-active");
      });

      // Position tooltip relative to the frame
      const frame = zone.closest(".sector-chart-frame");
      if (!frame) return;
      const zoneRect = zone.getBoundingClientRect();
      positionTooltip(event, frame);

      // Move crosshair
      if (crosshair) {
        const svgEl = frame.querySelector("svg");
        if (svgEl) {
          const svgRect = svgEl.getBoundingClientRect();
          const ratio = svgEl.viewBox.baseVal.width / svgRect.width;
          const cx = (zoneRect.left + zoneRect.width / 2 - svgRect.left) * ratio;
          crosshair.setAttribute("x1", cx.toFixed(1));
          crosshair.setAttribute("x2", cx.toFixed(1));
          crosshair.style.display = "block";
          crosshair.style.opacity = "1";
        }
      }
    });

    zone.addEventListener("mousemove", (event) => {
      const frame = zone.closest(".sector-chart-frame");
      if (frame) positionTooltip(event, frame);
    });

    zone.addEventListener("mouseleave", hide);
  });

  chartView.querySelector(".sector-chart-frame")?.addEventListener("mouseleave", hide);
}

/* shadow-input:js/stock-detail.js */
function buildFallbackStockDetail(stock) {
  if (!stock) return null;

  const close = parseMarketNumber(stock.close);
  if (close === null) return null;

  const change = parseMarketNumber(stock.change) || 0;
  const previousClose = close - change;
  const snapshot = data?.snapshotDate ? new Date(`${data.snapshotDate}T00:00:00`) : new Date();
  const currentDate = Number.isNaN(snapshot.getTime()) ? new Date() : snapshot;
  const previousDate = new Date(currentDate);
  previousDate.setDate(previousDate.getDate() - 1);
  while (previousDate.getDay() === 0 || previousDate.getDay() === 6) {
    previousDate.setDate(previousDate.getDate() - 1);
  }
  const volume = stock.volume || "0";
  const historyDays = [
    {
      date: formatRocDateFromDate(previousDate),
      open: previousClose,
      high: previousClose,
      low: previousClose,
      close: previousClose,
      change: 0,
      volume: 0,
    },
    {
      date: formatRocDateFromDate(currentDate),
      open: parseMarketNumber(stock.open) ?? previousClose,
      high: parseMarketNumber(stock.high) ?? close,
      low: parseMarketNumber(stock.low) ?? close,
      close,
      change,
      volume,
    },
  ];

  return {
    ...stock,
    snapshotDate: data?.snapshotDate || formatChartDate(currentDate),
    ma5: "--",
    ma20: "--",
    ma60: "--",
    avgVolume5: "--",
    monthHigh: stock.high || stock.close || "--",
    monthLow: stock.low || stock.close || "--",
    trend: "先顯示本機快取行情，完整歷史資料同步中。",
    historyDays,
    recentDays: historyDays,
    historyCount: historyDays.length,
    historyStartDate: historyDays[0].date,
    historyEndDate: historyDays[historyDays.length - 1].date,
    isFallbackHistory: true,
    chartIntervals: {
      supported: ["day", "week", "month"],
      intradayAvailable: false,
      intradayUnavailableReason: "目前顯示本機快取行情。",
    },
  };
}
function buildLatestInstitutionalTradeFromHistory(history) {
  const latest = Array.isArray(history?.rows) ? history.rows[0] : null;
  if (!latest) return {};
  const formatSigned = (value) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return "--";
    return `${parsed > 0 ? "+" : ""}${Math.round(parsed).toLocaleString("zh-TW")}`;
  };
  return {
    date: latest.date || "",
    foreign: formatSigned(latest.foreignValue),
    trust: formatSigned(latest.trustValue),
    dealer: formatSigned(latest.dealerValue),
    total: formatSigned(latest.totalValue),
    foreignValue: latest.foreignValue,
    trustValue: latest.trustValue,
    dealerValue: latest.dealerValue,
    totalValue: latest.totalValue,
  };
}
function loadInstitutionalTradeHistoryIfNeeded(detail) {
  const code = String(detail?.code || "").trim();
  const market = String(detail?.market || activeStockMarket || "").trim().toUpperCase();
  if (!code || market !== "TWSE") return;
  const key = getStockDetailCacheKey(code, market);
  // TD-16 structural guard: checked and set before any other logic, so it stays
  // a real circuit breaker even if the logic-level check below is ever broken.
  if (stockInstitutionHistoryAttempted.has(key)) return;
  stockInstitutionHistoryAttempted.add(key);
  const history = detail.institutionalTradeHistory;
  // TD-16 logic-level fix: terminate once we have ANY definitive result,
  // including a genuinely empty one - a stock with <5 days of institutional
  // trade history (new listing, thinly traded) is normal, valid data, not a
  // "not done yet" signal. Conflating "insufficient rows" with "haven't loaded
  // yet" (the old `rows.length >= 5` check) is what caused the infinite
  // renderStockDetail <-> loadInstitutionalTradeHistoryIfNeeded recursion.
  //
  // The check must be "does history have a `rows` array" (Array.isArray), not
  // just "is history truthy": the full stock-detail payload (fetched before
  // this function ever runs) already sets detail.institutionalTradeHistory to
  // `{}` as a placeholder for every stock, with no `rows` key at all - only
  // *this* function's own dedicated /institutional-history fetch ever
  // populates a `rows` array (always present, possibly empty; confirmed in
  // fetchers.py:fetch_stock_institutional_trade_history and
  // builders.py:build_institutional_history_from_yahoo, both of which always
  // include "rows"). Treating the placeholder `{}` as "already resolved"
  // would skip the dedicated fetch entirely for every stock, not just sparse
  // ones - a regression discovered and fixed during Part 2 testing.
  if (Array.isArray(history?.rows)) return;
  const cached = stockInstitutionHistoryCache.get(key);
  if (cached) {
    const current = activeRenderedStockDetail || detail;
    const nextDetail = {
      ...current,
      institutionalTradeHistory: cached,
      institutionalTrades: current.institutionalTrades || buildLatestInstitutionalTradeFromHistory(cached),
    };
    renderStockDetail(nextDetail);
    return;
  }
  if (stockInstitutionHistoryPending.has(key)) return;
  const status = document.getElementById("search-status");
  if (status) status.textContent = `${code} 法人買賣超 5/10/20/30 日明細正在同步證交所 live 資料...`;
  const params = new URLSearchParams();
  if (market) params.set("market", market);
  const pending = fetchWithTimeout(
    `/api/twse/stock/${encodeURIComponent(code)}/institutional-history?${params.toString()}`,
    { cache: "no-store" },
    45000,
  )
    .then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      const loadedHistory = payload.institutionalTradeHistory || {};
      stockInstitutionHistoryCache.set(key, loadedHistory);
      if (code !== activeStockCode || market !== activeStockMarket) return;
      const current = activeRenderedStockDetail || detail;
      const nextDetail = {
        ...current,
        institutionalTradeHistory: loadedHistory,
        institutionalTrades: payload.institutionalTrades || current.institutionalTrades || buildLatestInstitutionalTradeFromHistory(loadedHistory),
      };
      renderStockDetail(nextDetail);
      if (status) status.textContent = `${code} 法人買賣超 5/10/20/30 日明細已同步證交所 live 資料。`;
    })
    .catch((error) => {
      console.error("Failed to load client institutional trade history:", error);
      if (code === activeStockCode && market === activeStockMarket && status) {
        status.textContent = `${code} 法人買賣超明細同步失敗，請重新整理或重啟後端服務後再試。`;
      }
    })
    .finally(() => {
      stockInstitutionHistoryPending.delete(key);
    });
  stockInstitutionHistoryPending.set(key, pending);
}
function isStockInWatchlist(stock) {
  return getWatchlist().some((item) => watchlistKey(item) === watchlistKey(stock));
}
function toggleWatchlistStock(stock) {
  const items = getWatchlist();
  const key = watchlistKey(stock);
  const exists = items.some((item) => watchlistKey(item) === key);
  saveWatchlist(exists ? items.filter((item) => watchlistKey(item) !== key) : [...items, stock]);
  return !exists;
}
function renderStockDetail(detail) {
  const container = document.getElementById("stock-detail");
  if (!container) return;
  const institutionCacheKey = getStockDetailCacheKey(detail.code, detail.market || activeStockMarket);
  const cachedInstitutionHistory = stockInstitutionHistoryCache.get(institutionCacheKey);
  if (
    cachedInstitutionHistory
    && (!Array.isArray(detail.institutionalTradeHistory?.rows) || !detail.institutionalTradeHistory.rows.length)
  ) {
    detail = {
      ...detail,
      institutionalTradeHistory: cachedInstitutionHistory,
      institutionalTrades: detail.institutionalTrades || buildLatestInstitutionalTradeFromHistory(cachedInstitutionHistory),
    };
  }
  activeRenderedStockDetail = detail;
  let chartDetail = detail;
  const defaultVisibleChartCount = (interval = "day") => {
    const total = getChartHistory(chartDetail, interval).length;
    if (interval === "day") return Math.min(total, 120);
    return total;
  };
  const historySummary = detail.historyCount
    ? `歷史資料：${detail.historyCount} 筆，${detail.historyStartDate || "--"} 至 ${detail.historyEndDate || "--"}`
    : "尚無歷史資料。";
  const chartIntervals = detail.chartIntervals || {};
  const supportedIntervals = new Set(chartIntervals.supported || ["day", "week", "month"]);
  const intervalButtons = [
    ["day", "日線"],
    ["week", "週線"],
    ["month", "月線"],
  ].map(([interval, label]) => {
    const unavailable = !supportedIntervals.has(interval);
    const className = unavailable ? "range-button is-disabled" : "range-button";
    return `<button class="${className}" type="button" data-interval="${interval}">${label}</button>`;
  }).join("");
  const maOptions = [5, 10, 20, 60, 120, 240];
  const chartIndicatorOptions = [
    ["bollinger", "布林通道"],
    ["fibonacci", "斐波那契"],
    ["supportResistance", "支撐壓力"],
    ["smc", "SMC"],
  ];
  const panelIndicatorOptions = TECHNICAL_PANEL_INDICATOR_OPTIONS;

  const analysisSections = detail.analysis
    ? [
        { ...detail.analysis.technical, key: "technical", title: "技術面" },
        { ...detail.analysis.fundamental, key: "fundamental", title: "基本面" },
        { ...detail.analysis.chips, key: "chips", title: "籌碼面" },
      ].filter(Boolean)
    : [];
  let technicalSummaryHtml = "";

  const renderHolderDistribution = (distribution) => {
    if (!distribution || !Object.keys(distribution).length) {
      return '<div class="stock-detail-empty">集保持股分布目前未取得。</div>';
    }
    if (distribution.available === false) {
      return `
        <div class="stock-detail-empty">
          ${escapeHtml(distribution.sourceNote || "集保持股分布目前未取得。")}
          ${distribution.sourceLink ? `<br><a href="${safeUrl(distribution.sourceLink)}" target="_blank" rel="noreferrer noopener">查看集保來源</a>` : ""}
        </div>
      `;
    }
    const largeRaw = Number(distribution.largeHolderRatio);
    const retailRaw = Number(distribution.retailHolderRatio);
    const otherRaw = Number(distribution.otherHolderRatio);
    const hasLarge = Number.isFinite(largeRaw);
    const hasRetail = Number.isFinite(retailRaw);
    const hasOther = Number.isFinite(otherRaw);
    if (!distribution.date || (!hasLarge && !hasRetail && !hasOther)) {
      return '<div class="stock-detail-empty">集保持股分布目前未取得。</div>';
    }
    const large = hasLarge ? largeRaw : 0;
    const retail = hasRetail ? retailRaw : 0;
    const other = hasOther ? otherRaw : Math.max(0, 100 - large - retail);
    if (large <= 0 && retail <= 0 && other >= 99.99 && !hasOther) {
      return '<div class="stock-detail-empty">集保持股分布目前未取得。</div>';
    }
    const liquidItems = [
      { key: "large", label: "大戶", value: large, note: distribution.largeHolderThreshold || "400 張以上" },
      { key: "retail", label: "散戶", value: retail, note: distribution.retailHolderThreshold || "10 張以下" },
      { key: "other", label: "其他", value: other, note: "10 至 400 張" },
    ].map((item) => ({
      ...item,
      value: Math.max(0, Math.min(100, item.value)),
    }));
    return `
      <div class="holder-ratio-chart" role="img" aria-label="大戶 ${large.toFixed(2)}%，散戶 ${retail.toFixed(2)}%，其他 ${other.toFixed(2)}%">
        <div class="holder-ratio-bar">
          <span class="holder-ratio-segment is-large" style="width:${large}%"></span>
          <span class="holder-ratio-segment is-other" style="width:${other}%"></span>
          <span class="holder-ratio-segment is-retail" style="width:${retail}%"></span>
        </div>
        <div class="holder-combined-panel">
          <div class="holder-liquid-chart" aria-label="集保持股液位圖">
            ${liquidItems.map((item) => `
              <div class="holder-liquid-item is-${item.key}">
                <div class="holder-liquid-head">
                  <span><i class="is-${item.key}"></i>${item.label}</span>
                  <strong>${item.value.toFixed(2)}%</strong>
                </div>
                <div class="holder-liquid-tank">
                  <span class="holder-liquid-fill" style="height:${item.value}%"></span>
                </div>
                <div class="holder-liquid-label">
                  <small>${item.note}</small>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
        <p class="holder-ratio-source">${escapeHtml(distribution.sourceNote || `集保資料日期 ${distribution.date || "--"}`)}</p>
      </div>
    `;
  };

  const renderMarginTrading = (margin) => {
    if (!margin || !Object.keys(margin).length) return "";
    const numberValue = (value) => {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const formatShares = (value, signed = false) => {
      const parsed = numberValue(value);
      if (parsed === null) return "--";
      const prefix = signed && parsed > 0 ? "+" : "";
      return `${prefix}${Math.round(parsed).toLocaleString("zh-TW")} 張`;
    };
    const financingChange = numberValue(margin.financingChange);
    const shortChange = numberValue(margin.shortChange);
    const ratio = numberValue(margin.shortFinancingRatio);
    const financingTone = financingChange > 0 ? "is-warning" : financingChange < 0 ? "is-positive" : "";
    const shortTone = shortChange > 0 ? "is-negative" : shortChange < 0 ? "is-positive" : "";
    return `
      <section class="margin-trading-card">
        <div class="margin-trading-head">
          <div>
            <span>Margin trading</span>
            <strong>融資融券</strong>
          </div>
          <small>資料日期 ${escapeHtml(margin.date || detail.snapshotDate || "--")}</small>
        </div>
        <div class="margin-trading-grid">
          <div>
            <span>融資餘額</span>
            <strong>${formatShares(margin.financingBalance)}</strong>
            <small class="${financingTone}">日增減 ${formatShares(financingChange, true)}</small>
          </div>
          <div>
            <span>融券餘額</span>
            <strong>${formatShares(margin.shortBalance)}</strong>
            <small class="${shortTone}">日增減 ${formatShares(shortChange, true)}</small>
          </div>
          <div>
            <span>券資比</span>
            <strong>${ratio === null ? "--" : `${ratio.toFixed(2)}%`}</strong>
            <small>融券餘額 ÷ 融資餘額</small>
          </div>
          <div>
            <span>資券互抵</span>
            <strong>${formatShares(margin.offsetting)}</strong>
            <small>當日沖銷張數</small>
          </div>
        </div>
        <div class="margin-trading-flow">
          <span>融資買進 <b>${formatShares(margin.financingBuy)}</b></span>
          <span>融資賣出 <b>${formatShares(margin.financingSell)}</b></span>
          <span>融券賣出 <b>${formatShares(margin.shortSell)}</b></span>
          <span>融券回補 <b>${formatShares(margin.shortBuy)}</b></span>
        </div>
        <p>${escapeHtml(margin.sourceNote || "融資融券資料以交易所公告為準。")} ${margin.sourceLink ? `<a href="${safeUrl(margin.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
      </section>
    `;
  };

  const renderInstitutionalTradeHistory = (history) => {
    if (!history || !Object.keys(history).length) return "";
    const rows = Array.isArray(history.rows) ? history.rows : [];
    const periods = (Array.isArray(history.periods) && history.periods.length ? history.periods : [5, 10, 20, 30])
      .map((period) => Number(period))
      .filter((period) => Number.isFinite(period) && period > 0);
    const stateKey = getStockDetailCacheKey(detail.code, detail.market || activeStockMarket);
    const requestedPeriod = Number(stockInstitutionPeriodState.get(stateKey) || history.defaultPeriod || 5);
    const activePeriod = periods.includes(requestedPeriod) ? requestedPeriod : periods[0] || 5;
    const summaries = history.summaries && typeof history.summaries === "object" ? history.summaries : {};
    const summary = summaries[String(activePeriod)] || history.summary || null;
    const visibleRows = rows.slice(0, activePeriod);
    if (!visibleRows.length && !summary) {
      return `
        <section class="institution-trade-panel is-loading" aria-label="法人買賣超明細">
          <div class="institution-trade-head">
            <div>
              <span>Institutional flow</span>
              <strong>法人籌碼買賣</strong>
            </div>
            <small>TWSE T86 · 單位 ${escapeHtml(history.unit || "張")}</small>
          </div>
          <div class="institution-period-switcher" aria-label="法人買賣超期間切換">
            ${periods.map((period) => `
              <button class="${period === activePeriod ? "is-active" : ""}" type="button" data-institution-period="${period}">
                ${period}日
              </button>
            `).join("")}
          </div>
          <p class="stock-detail-empty">${escapeHtml(history.sourceNote || "法人買賣超明細同步中。")}</p>
        </section>
      `;
    }
    const valueKeys = [
      { key: "foreign", label: "外資", tone: "foreign" },
      { key: "trust", label: "投信", tone: "trust" },
      { key: "dealer", label: "自營商", tone: "dealer" },
      { key: "total", label: "合計", tone: "total" },
    ];
    const numberValue = (value) => {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const getLotsValue = (record, key) => {
      const lots = numberValue(record?.[`${key}LotsValue`]);
      if (lots !== null) return lots;
      const shares = numberValue(record?.[`${key}Value`]);
      return shares === null ? null : shares / 1000;
    };
    const valueTone = (value) => {
      if (value === null || value === 0) return "is-flat";
      return value > 0 ? "is-buy" : "is-sell";
    };
    const formatValue = (value) => {
      if (value === null) return "--";
      const rounded = Math.round(value);
      const normalized = Math.abs(value - rounded) < 0.05 ? rounded : value;
      return normalized.toLocaleString("zh-TW", { maximumFractionDigits: 1 });
    };
    const renderRow = (record, extraClass = "") => `
      <div class="institution-trade-row ${extraClass}" role="row">
        <span class="institution-trade-date" role="cell">${escapeHtml(record.label || record.displayDate || record.date || "--")}</span>
        ${valueKeys.map((item) => {
          const value = getLotsValue(record, item.key);
          return `<strong class="${valueTone(value)}" role="cell">${formatValue(value)}</strong>`;
        }).join("")}
      </div>
    `;
    const sourceDate = rows[0]?.date || detail.snapshotDate || "--";
    return `
      <section class="institution-trade-panel" aria-label="法人買賣超明細">
        <div class="institution-trade-head">
          <div>
            <span>Institutional flow</span>
            <strong>法人籌碼買賣</strong>
          </div>
          <small>TWSE T86 · 單位 ${escapeHtml(history.unit || "張")}</small>
        </div>
        <div class="institution-period-switcher" aria-label="法人買賣超期間切換">
          ${periods.map((period) => `
            <button class="${period === activePeriod ? "is-active" : ""}" type="button" data-institution-period="${period}">
              ${period}日
            </button>
          `).join("")}
        </div>
        <div class="institution-trade-table" role="table">
          <div class="institution-trade-row is-head" role="row">
            <span role="columnheader">日期</span>
            ${valueKeys.map((item) => `
              <span class="institution-trade-label is-${item.tone}" role="columnheader"><i></i>${item.label}</span>
            `).join("")}
          </div>
          ${summary ? renderRow(summary, "is-summary") : ""}
          ${visibleRows.map((row) => renderRow(row)).join("")}
        </div>
        <p>單位：${escapeHtml(history.unit || "張")}｜資料日期 ${escapeHtml(sourceDate)} ${history.sourceLink ? `<a href="${safeUrl(history.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
      </section>
    `;
  };

  const pickHolderDistribution = (section) => (
    section.holderDistribution && Object.keys(section.holderDistribution).length
      ? section.holderDistribution
      : detail.shareholderDistribution
  );

  const renderChipDashboard = (section) => {
    const backendCards = Array.isArray(section?.chipSummary?.cards)
      ? section.chipSummary.cards
      : Array.isArray(detail.chipSummary?.cards) ? detail.chipSummary.cards : [];
    const backendCard = (key) => backendCards.find((card) => card?.key === key) || {};
    const numberValue = (value) => {
      const parsed = parseAnalysisNumber(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const formatLots = (value, signed = false, digits = 0) => {
      const parsed = numberValue(value);
      if (parsed === null) return "--";
      const prefix = signed && parsed > 0 ? "+" : "";
      return `${prefix}${parsed.toLocaleString("zh-TW", { minimumFractionDigits: digits, maximumFractionDigits: digits })} 張`;
    };
    const formatPercentText = (value, signed = false, digits = 2) => {
      const parsed = numberValue(value);
      if (parsed === null) return "--";
      const prefix = signed && parsed > 0 ? "+" : "";
      return `${prefix}${parsed.toFixed(digits)}%`;
    };
    const formatPlainNumber = (value, signed = false, digits = 0) => {
      const parsed = numberValue(value);
      if (parsed === null) return "--";
      const prefix = signed && parsed > 0 ? "+" : "";
      return `${prefix}${parsed.toLocaleString("zh-TW", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
    };
    const toneFromValue = (value) => {
      const parsed = numberValue(value);
      if (parsed === null || parsed === 0) return "flat";
      return parsed > 0 ? "up" : "down";
    };
    const valueToneClass = (value) => {
      const tone = toneFromValue(value);
      return tone === "up" ? "is-up" : tone === "down" ? "is-down" : "is-flat";
    };
    const metric = (label, value) => ({ label, value });
    const market = String(detail.market || activeStockMarket || "").toUpperCase();
    const suffix = market === "TPEX" ? "TWO" : "TW";
    const yahooChipUrl = (page) => `https://tw.stock.yahoo.com/quote/${encodeURIComponent(`${detail.code}.${suffix}`)}/${page}`;
    const yahooInstitutional = detail.yahooInstitutionalTrading || {};
    const yahooInstitutionalOverviewRows = Array.isArray(yahooInstitutional.overviewRows)
      ? yahooInstitutional.overviewRows
      : [];
    const yahooInstitutionalRow = (name) => yahooInstitutionalOverviewRows.find((row) => row?.name === name) || {};
    const yahooInstitutionalDailyRows = Array.isArray(yahooInstitutional.dailyRows)
      ? yahooInstitutional.dailyRows
      : [];
    const exchangeInstitutionalRows = Array.isArray(detail.institutionalTradeHistory?.rows)
      ? detail.institutionalTradeHistory.rows
      : [];
    const institutionalRows = [...exchangeInstitutionalRows, ...yahooInstitutionalDailyRows];
    const institutional = detail.institutionalTrades && Object.keys(detail.institutionalTrades).length
      ? detail.institutionalTrades
      : buildLatestInstitutionalTradeFromHistory(detail.institutionalTradeHistory || {});
    const totalInstitution = numberValue(institutional?.totalValue);
    const foreignInstitution = numberValue(institutional?.foreignValue);
    const trustInstitution = numberValue(institutional?.trustValue);
    const dealerInstitution = numberValue(institutional?.dealerValue);
    const totalInstitutionLots = numberValue(yahooInstitutionalRow("三大法人").netLots) ?? (totalInstitution === null ? null : totalInstitution / 1000);
    const foreignInstitutionLots = numberValue(yahooInstitutionalRow("外資").netLots) ?? (foreignInstitution === null ? null : foreignInstitution / 1000);
    const trustInstitutionLots = numberValue(yahooInstitutionalRow("投信").netLots) ?? (trustInstitution === null ? null : trustInstitution / 1000);
    const dealerInstitutionLots = numberValue(yahooInstitutionalRow("自營商").netLots) ?? (dealerInstitution === null ? null : dealerInstitution / 1000);
    const institutionalFallback = backendCard("institutional");
    const institutionalCard = {
      key: "institutional",
      tab: "法人買賣",
      title: "法人買賣變化",
      label: totalInstitutionLots === null ? (institutionalFallback.label || "待同步") : totalInstitutionLots > 0 ? "買超" : totalInstitutionLots < 0 ? "賣超" : "中性",
      tone: totalInstitutionLots === null ? (institutionalFallback.tone || "flat") : toneFromValue(totalInstitutionLots),
      metrics: [
        metric("三大法人", formatLots(totalInstitutionLots, true)),
        metric("外資", formatLots(foreignInstitutionLots, true)),
        metric("投信", formatLots(trustInstitutionLots, true)),
        metric("自營商", formatLots(dealerInstitutionLots, true)),
      ],
      sourceNote: detail.institutionalTradeHistory?.sourceNote || yahooInstitutional.sourceNote || institutionalFallback.sourceNote || "法人買賣超明細同步自交易所公開資料。",
      sourceLink: yahooInstitutional.sourceLink || detail.institutionalTradeHistory?.sourceLink || institutionalFallback.sourceLink || yahooChipUrl("institutional-trading"),
    };
    const broker = detail.brokerTrading || {};
    const brokerSummary = broker.summary || {};
    const brokerNet = numberValue(brokerSummary.netLots);
    const hasBroker = Boolean(brokerNet !== null || broker.buyBrokers?.length || broker.sellBrokers?.length);
    const mainCard = {
      key: "mainForce",
      tab: "主力進出",
      title: "主力進出",
      label: !hasBroker ? "同步中" : brokerNet > 0 ? "偏買進" : brokerNet < 0 ? "偏賣出" : "換手觀察",
      tone: hasBroker ? toneFromValue(brokerNet) : "flat",
      metrics: [
        metric("主力買賣超", hasBroker ? formatLots(brokerNet, true) : "--"),
        metric("主力買超", formatLots(brokerSummary.buyLots)),
        metric("主力賣超", formatLots(brokerSummary.sellLots)),
        metric("佔成交量", brokerSummary.volumeRatio || "--"),
      ],
      sourceNote: broker.sourceNote || "主力進出同步自 Yahoo 股市券商分點頁。",
      sourceLink: broker.sourceLink || yahooChipUrl("broker-trading"),
    };
    const margin = detail.marginTrading || {};
    const marginOverviewRows = Array.isArray(margin.overviewRows) ? margin.overviewRows : [];
    const marginDailyRows = Array.isArray(margin.dailyRows) ? margin.dailyRows : [];
    const marginOverviewByKey = (key) => marginOverviewRows.find((row) => row?.key === key) || {};
    const financingOverview = marginOverviewByKey("financing");
    const shortOverview = marginOverviewByKey("short");
    const latestMarginDaily = marginDailyRows[0] || {};
    const financingChange = numberValue(financingOverview.change) ?? numberValue(latestMarginDaily.financingChange) ?? numberValue(margin.financingChange);
    const shortChange = numberValue(shortOverview.change) ?? numberValue(latestMarginDaily.shortChange) ?? numberValue(margin.shortChange);
    const financingBalance = numberValue(financingOverview.balance) ?? numberValue(latestMarginDaily.financingBalance) ?? numberValue(margin.financingBalance);
    const shortBalance = numberValue(shortOverview.balance) ?? numberValue(latestMarginDaily.shortBalance) ?? numberValue(margin.shortBalance);
    const shortFinancingRatio = numberValue(shortOverview.shortFinancingRatio) ?? numberValue(latestMarginDaily.shortFinancingRatio) ?? numberValue(margin.shortFinancingRatio);
    const marginLabel = shortChange !== null && shortChange > 0 && (financingChange || 0) <= 0
      ? "券增資減"
      : financingChange !== null && financingChange > 0 && (shortChange || 0) <= 0
        ? "資增券減"
        : financingChange !== null || shortChange !== null ? "同步觀察" : "待同步";
    const marginCard = {
      key: "margin",
      tab: "資券變化",
      title: "資券變化",
      label: marginLabel,
      tone: marginLabel === "券增資減" ? "down" : marginLabel === "資增券減" ? "up" : "flat",
      metrics: [
        metric("融資增減", formatLots(financingChange, true)),
        metric("融券增減", formatLots(shortChange, true)),
        metric("融資餘額", formatLots(financingBalance)),
        metric("券資比", formatPercentText(shortFinancingRatio)),
      ],
      sourceNote: margin.sourceNote || "融資融券資料以交易所公告為準。",
      sourceLink: margin.sourceLink || yahooChipUrl("margin"),
    };
    const holders = pickHolderDistribution(section) || {};
    const majorData = detail.majorHolderData || {};
    const majorLatest = majorData.latest || {};
    const majorRowsForFallback = Array.isArray(majorData.rows) ? majorData.rows : [];
    const majorFallbackRow = [majorLatest, ...majorRowsForFallback].find((row) => numberValue(row?.majorHolderRatio) !== null) || majorLatest;
    const large = numberValue(holders.largeHolderRatio) ?? numberValue(majorFallbackRow.majorHolderRatio);
    const retail = numberValue(holders.retailHolderRatio);
    const other = numberValue(holders.otherHolderRatio);
    const foreignChip = numberValue(majorLatest.foreignChipRatio) ?? numberValue(majorFallbackRow.foreignChipRatio);
    const directorHolding = numberValue(majorLatest.directorHoldingRatio) ?? numberValue(majorFallbackRow.directorHoldingRatio);
    const holderAvailable = (holders.available !== false && large !== null) || foreignChip !== null;
    const holderLabel = !holderAvailable ? "同步中" : large !== null && large >= 60 ? "集中" : large !== null && large < 35 ? "分散" : large === null && foreignChip !== null ? "外資籌碼" : "觀察";
    const holderCard = {
      key: "largeHolder",
      tab: "大戶籌碼",
      title: "大戶籌碼",
      label: holderLabel,
      tone: holderLabel === "集中" ? "up" : holderLabel === "分散" ? "down" : "flat",
      metrics: [
        metric("大戶", formatPercentText(large)),
        metric("外資籌碼", formatPercentText(foreignChip)),
        metric("董監持股", formatPercentText(directorHolding)),
        metric("日期", holders.date || majorFallbackRow.date || majorData.date || "--"),
      ],
      sourceNote: holders.sourceNote || majorData.sourceNote || "大戶籌碼同步自 Yahoo 股市大戶籌碼頁與集保資料。",
      sourceLink: holders.sourceLink || majorData.sourceLink || yahooChipUrl("major-holders"),
    };
    const holderVisualDistribution = (() => {
      const hasTdccLarge = holders.available !== false && numberValue(holders.largeHolderRatio) !== null;
      if (hasTdccLarge) return holders;
      const yahooLarge = numberValue(majorFallbackRow.majorHolderRatio);
      if (yahooLarge === null) return holders;
      const fallbackRetail = numberValue(holders.retailHolderRatio) ?? 0;
      const fallbackOther = numberValue(holders.otherHolderRatio) ?? Math.max(0, 100 - yahooLarge - fallbackRetail);
      return {
        available: true,
        date: majorFallbackRow.date || majorData.date || majorLatest.date || holders.date || "--",
        largeHolderRatio: yahooLarge,
        retailHolderRatio: fallbackRetail,
        otherHolderRatio: fallbackOther,
        largeHolderThreshold: "Yahoo 大戶籌碼",
        retailHolderThreshold: holders.retailHolderThreshold || "TDCC 待恢復",
        source: majorData.source || "Yahoo 股市大戶籌碼",
        sourceLink: majorData.sourceLink || yahooChipUrl("major-holders"),
        sourceNote: holders.sourceNote
          ? `${holders.sourceNote}；液位圖暫以 Yahoo 大戶籌碼維持顯示，散戶比例待 TDCC 恢復後更新。`
          : "液位圖暫以 Yahoo 大戶籌碼維持顯示，散戶比例待 TDCC 恢復後更新。",
      };
    })();
    const cards = [institutionalCard, mainCard, marginCard, holderCard];
    const stateKey = getStockDetailCacheKey(detail.code, detail.market || activeStockMarket);
    const requestedTab = stockChipTabState.get(stateKey) || "institutional";
    const activeCard = cards.find((card) => card.key === requestedTab) || cards[0];
    const institutionRangeOptions = [
      { key: "1m", label: "1個月", months: 1, fallbackCount: 24 },
      { key: "3m", label: "3個月", months: 3, fallbackCount: 66 },
      { key: "6m", label: "6個月", months: 6, fallbackCount: 90 },
      { key: "1y", label: "1年", years: 1, fallbackCount: 110 },
    ];
    const activeInstitutionRangeKey = stockInstitutionRangeState.get(stateKey) || "1m";
    const activeInstitutionRange = institutionRangeOptions.find((item) => item.key === activeInstitutionRangeKey)
      || institutionRangeOptions.find((item) => item.key === "1m")
      || institutionRangeOptions[0];
    const defaultInstitutionSeries = ["price", "foreign", "trust", "dealer"];
    const savedInstitutionSeries = String(stockInstitutionSeriesState.get(stateKey) || defaultInstitutionSeries.join(","))
      .split(",")
      .filter(Boolean);
    const activeInstitutionSeries = new Set(savedInstitutionSeries.length ? savedInstitutionSeries : defaultInstitutionSeries);
    const institutionSeriesOptions = [
      { key: "price", label: "股價" },
      { key: "foreign", label: "外資" },
      { key: "trust", label: "投信" },
      { key: "dealer", label: "自營商" },
    ];
    const normalizeInstitutionDate = (value) => {
      const text = String(value || "").trim();
      if (!text) return "";
      if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
      if (/^\d{4}\/\d{2}\/\d{2}$/.test(text)) return text.replaceAll("/", "-");
      const roc = text.match(/^(\d{2,3})\/(\d{2})\/(\d{2})$/);
      if (roc) return `${Number(roc[1]) + 1911}-${roc[2]}-${roc[3]}`;
      return text;
    };
    const priceHistory = normalizePortfolioHistory(detail)
      .map((item) => ({ ...item, isoDate: normalizeInstitutionDate(item.date) }))
      .filter((item) => item.isoDate && Number.isFinite(item.close));
    const priceByDate = new Map(priceHistory.map((item) => [item.isoDate, item.close]));
    const buildInstitutionRowsForRange = (rows, option) => {
      const normalizedRows = Array.isArray(rows)
        ? rows
            .map((row) => ({ ...row, date: normalizeInstitutionDate(row?.date || row?.label) }))
            .filter((row) => row.date)
        : [];
      const sourceRows = [...new Map(normalizedRows.map((row) => [row.date, row])).values()]
        .sort((left, right) => String(right.date || "").localeCompare(String(left.date || "")));
      const datedTimes = [
        ...sourceRows.map((row) => new Date(row.date).getTime()),
        ...priceHistory.map((item) => new Date(item.isoDate).getTime()),
      ].filter(Number.isFinite);
      if (!datedTimes.length) return sourceRows.slice(0, option.fallbackCount || sourceRows.length);
      const latestTime = Math.max(...datedTimes);
      const cutoff = new Date(latestTime);
      if (option.years) cutoff.setFullYear(cutoff.getFullYear() - option.years);
      else cutoff.setMonth(cutoff.getMonth() - (option.months || 1));
      const cutoffTime = cutoff.getTime();
      const inRange = (date) => {
        const time = new Date(date).getTime();
        return Number.isFinite(time) && time >= cutoffTime && time <= latestTime;
      };
      const rangedFlows = sourceRows.filter((row) => inRange(row.date));
      const longRange = Boolean(option.years || (option.months || 0) >= 6);
      const rangedPrices = priceHistory.filter((item) => inRange(item.isoDate));
      const oldestFlowTime = rangedFlows.length
        ? Math.min(...rangedFlows.map((row) => new Date(row.date).getTime()).filter(Number.isFinite))
        : Number.POSITIVE_INFINITY;
      const hasLongerPriceCoverage = rangedPrices.some((item) => {
        const time = new Date(item.isoDate).getTime();
        return Number.isFinite(time) && time < oldestFlowTime - 7 * 24 * 60 * 60 * 1000;
      });
      if (!longRange || !rangedPrices.length || !hasLongerPriceCoverage) {
        return (rangedFlows.length ? rangedFlows : sourceRows).slice(0, option.fallbackCount || sourceRows.length);
      }
      const flowByDate = new Map(rangedFlows.map((row) => [row.date, row]));
      const merged = rangedPrices.map((price) => {
        const flow = flowByDate.get(price.isoDate) || {};
        return {
          ...flow,
          date: price.isoDate,
          label: price.isoDate.slice(5),
          priceValue: price.close,
          priceVolume: price.volume,
          isPriceOnly: !flowByDate.has(price.isoDate),
        };
      });
      rangedFlows.forEach((row) => {
        if (!priceByDate.has(row.date)) merged.push({ ...row, label: row.label || row.date.slice(5) });
      });
      return merged
        .sort((left, right) => String(right.date || "").localeCompare(String(left.date || "")))
        .slice(0, option.fallbackCount || merged.length);
    };
    const activeInstitutionRows = buildInstitutionRowsForRange(institutionalRows, activeInstitutionRange);
    const activeInstitutionFlowCount = activeInstitutionRows.filter((row) => (
      Number.isFinite(numberValue(row.foreignLotsValue))
      || Number.isFinite(numberValue(row.trustLotsValue))
      || Number.isFinite(numberValue(row.dealerLotsValue))
      || Number.isFinite(numberValue(row.totalLotsValue))
    )).length;
    const renderMetrics = (card) => `
      <div class="chip-summary-metrics">
        ${(card.metrics || []).map((item) => `
          <div><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(item.value)}</strong></div>
        `).join("")}
      </div>
    `;
    const renderChipVisualLegend = (items) => `
      <div class="chip-visual-legend">
        ${items.map((item) => `<span><i class="is-${item.key}"></i>${escapeHtml(item.label)}</span>`).join("")}
      </div>
    `;
    const renderInstitutionOverview = () => {
      const rows = yahooInstitutionalOverviewRows.length
        ? yahooInstitutionalOverviewRows
        : [
            { name: "外資", buyLots: null, sellLots: null, netLots: foreignInstitutionLots, streak: "--" },
            { name: "投信", buyLots: null, sellLots: null, netLots: trustInstitutionLots, streak: "--" },
            { name: "自營商", buyLots: null, sellLots: null, netLots: dealerInstitutionLots, streak: "--" },
            { name: "三大法人", buyLots: null, sellLots: null, netLots: totalInstitutionLots, streak: "--" },
          ].filter((row) => numberValue(row.netLots) !== null);
      if (!rows.length) return "";
      return `
        <div class="chip-overview-table chip-institution-overview">
          <div class="chip-overview-row is-head"><span>法人</span><span>買進</span><span>賣出</span><span>買賣超</span><span>連買連賣</span></div>
          ${rows.map((row) => `
            <div class="chip-overview-row">
              <span>${escapeHtml(row.name || "--")}</span>
              <strong>${formatLots(row.buyLots)}</strong>
              <strong>${formatLots(row.sellLots)}</strong>
              <strong class="${valueToneClass(row.netLots)}">${formatLots(row.netLots, true)}</strong>
              <span>${escapeHtml(row.streak || "--")}</span>
            </div>
          `).join("")}
        </div>
      `;
    };
    const renderInstitutionControls = () => `
      <div class="institution-chart-controls" aria-label="法人買賣變化控制">
        <div class="institution-range-buttons" role="group" aria-label="法人買賣變化區間">
          ${institutionRangeOptions.map((option) => `
            <button class="range-button ${option.key === activeInstitutionRange.key ? "is-active" : ""}" type="button" data-institution-range="${escapeHtml(option.key)}">${escapeHtml(option.label)}</button>
          `).join("")}
        </div>
        <div class="institution-series-buttons" role="group" aria-label="法人買賣變化項目">
          ${institutionSeriesOptions.map((item) => `
            <button class="institution-series-button is-${escapeHtml(item.key)} ${activeInstitutionSeries.has(item.key) ? "is-active" : ""}" type="button" data-institution-series="${escapeHtml(item.key)}" aria-pressed="${activeInstitutionSeries.has(item.key) ? "true" : "false"}">
              <i class="is-${escapeHtml(item.key)}"></i>${escapeHtml(item.label)}
            </button>
          `).join("")}
        </div>
      </div>
    `;
    const renderInstitutionChart = () => {
      const rows = activeInstitutionRows.slice().reverse();
      if (!rows.length) return "";
      const width = 760;
      const height = 230;
      const pad = { left: 36, right: 18, top: 18, bottom: 34 };
      const mid = 122;
      const barScale = 82;
      const usableWidth = width - pad.left - pad.right;
      const step = rows.length > 1 ? usableWidth / (rows.length - 1) : usableWidth;
      const priceStart = Math.max(0, priceHistory.length - rows.length);
      const points = rows.map((row, index) => {
        const fallbackPrice = priceHistory[priceStart + index]?.close;
        const rowDate = normalizeInstitutionDate(row.date || row.label || "");
        return {
          date: rowDate,
          label: row.label || String(rowDate || "").slice(5),
          x: pad.left + (rows.length > 1 ? index * step : usableWidth / 2),
          foreign: numberValue(row.foreignLotsValue),
          trust: numberValue(row.trustLotsValue),
          dealer: numberValue(row.dealerLotsValue),
          price: numberValue(row.priceValue) ?? numberValue(priceByDate.get(rowDate)) ?? fallbackPrice ?? null,
          total: numberValue(row.totalLotsValue),
          foreignChip: numberValue(row.foreignChipRatio),
          changePct: numberValue(row.changePct),
          volume: numberValue(row.volume) ?? numberValue(row.priceVolume),
        };
      });
      const flowKeys = ["foreign", "trust", "dealer"].filter((key) => activeInstitutionSeries.has(key));
      const maxAbs = Math.max(1, ...points.flatMap((item) => flowKeys.map((key) => Math.abs(item[key] || 0))));
      const prices = points.map((item) => item.price).filter(Number.isFinite);
      const minPrice = prices.length ? Math.min(...prices) : 0;
      const maxPrice = prices.length ? Math.max(...prices) : 1;
      const priceRange = Math.max(maxPrice - minPrice, 1);
      const barWidth = flowKeys.length ? Math.max(2.4, Math.min(8, step * (0.46 / flowKeys.length))) : 0;
      const bar = (x, value, key, offset) => {
        if (!Number.isFinite(value)) return "";
        const normalized = value;
        const y = normalized >= 0 ? mid - (normalized / maxAbs) * barScale : mid;
        const h = Math.max(1, Math.abs((normalized / maxAbs) * barScale));
        return `<rect class="chip-flow-bar is-${key}" x="${(x + offset).toFixed(2)}" y="${y.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${h.toFixed(2)}" rx="1.6"></rect>`;
      };
      const barOffsets = flowKeys.map((_, index) => (index - (flowKeys.length - 1) / 2) * (barWidth + 1.4));
      const yPriceFor = (value) => pad.top + ((maxPrice - value) / priceRange) * (height - pad.top - pad.bottom);
      const yFlowFor = (value) => {
        const normalized = Number.isFinite(value) ? value : 0;
        return normalized >= 0 ? mid - (normalized / maxAbs) * barScale : mid + Math.abs((normalized / maxAbs) * barScale);
      };
      const pricePath = activeInstitutionSeries.has("price") ? points
        .filter((item) => Number.isFinite(item.price))
        .map((item, index) => `${index ? "L" : "M"} ${item.x.toFixed(2)} ${yPriceFor(item.price).toFixed(2)}`)
        .join(" ") : "";
      const zoneWidth = rows.length > 1 ? Math.max(10, step) : usableWidth;
      const cursorYFor = (item) => {
        if (activeInstitutionSeries.has("price") && Number.isFinite(item.price)) return yPriceFor(item.price);
        const firstFlowKey = flowKeys.find((key) => Number.isFinite(item[key]));
        return firstFlowKey ? yFlowFor(item[firstFlowKey]) : mid;
      };
      const hoverZones = points.map((item) => {
        const zoneX = rows.length > 1
          ? Math.max(pad.left, Math.min(width - pad.right - zoneWidth, item.x - zoneWidth / 2))
          : pad.left;
        return `<rect class="institution-hover-zone" x="${zoneX.toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${height - pad.top - pad.bottom}" data-x="${item.x.toFixed(2)}" data-y="${cursorYFor(item).toFixed(2)}" data-date="${escapeHtml(item.date || "--")}" data-price="${escapeHtml(Number.isFinite(item.price) ? item.price.toLocaleString("zh-TW") : "--")}" data-foreign="${escapeHtml(formatLots(item.foreign, true))}" data-trust="${escapeHtml(formatLots(item.trust, true))}" data-dealer="${escapeHtml(formatLots(item.dealer, true))}" data-total="${escapeHtml(formatLots(item.total, true))}" data-foreign-chip="${escapeHtml(formatPercentText(item.foreignChip))}" data-change="${escapeHtml(formatPercentText(item.changePct, true))}" data-volume="${escapeHtml(formatPlainNumber(item.volume))}" data-show-price="${activeInstitutionSeries.has("price") ? "1" : "0"}" data-show-foreign="${activeInstitutionSeries.has("foreign") ? "1" : "0"}" data-show-trust="${activeInstitutionSeries.has("trust") ? "1" : "0"}" data-show-dealer="${activeInstitutionSeries.has("dealer") ? "1" : "0"}"></rect>`;
      }).join("");
      return `
        <div class="chip-visual-card chip-institution-chart">
          <div class="chip-visual-head"><span>法人買賣變化</span><strong>${escapeHtml(activeInstitutionRange.label)} / ${escapeHtml(rows.at(-1)?.date || detail.snapshotDate || "--")}</strong></div>
          ${renderInstitutionControls()}
          <div class="institution-chart-stage">
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="法人買賣變化圖">
              <line class="chip-chart-axis" x1="${pad.left}" y1="${mid}" x2="${width - pad.right}" y2="${mid}"></line>
              ${points.map((item) => flowKeys.map((key, index) => bar(item.x, item[key], key, barOffsets[index])).join("")).join("")}
              ${pricePath ? `<path class="chip-price-line" d="${pricePath}"></path>` : ""}
              <line class="institution-crosshair is-x" data-institution-cursor-x x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
              <line class="institution-crosshair is-y" data-institution-cursor-y x1="${pad.left}" y1="${mid}" x2="${width - pad.right}" y2="${mid}"></line>
              <circle class="institution-crosshair-dot" data-institution-cursor-dot cx="${pad.left}" cy="${mid}" r="4"></circle>
              ${hoverZones}
            </svg>
            <div class="institution-chart-tooltip" hidden></div>
          </div>
          <p class="institution-chart-note">顯示 ${activeInstitutionRows.length.toLocaleString("zh-TW")} 個時間點，法人買賣 ${activeInstitutionFlowCount.toLocaleString("zh-TW")} 筆；長區間會合併價格歷史，法人資料不足的日期以 -- 標示。</p>
        </div>
      `;
    };
    const renderInstitutionRows = () => {
      const rows = activeInstitutionRows;
      if (!rows.length) return '<p class="stock-detail-empty">法人逐日買賣超目前未取得。</p>';
      const selectedFlowColumns = [
        { key: "foreign", label: "外資", valueKey: "foreignLotsValue" },
        { key: "trust", label: "投信", valueKey: "trustLotsValue" },
        { key: "dealer", label: "自營商", valueKey: "dealerLotsValue" },
      ].filter((item) => activeInstitutionSeries.has(item.key));
      const showYahooColumns = rows.some((row) => row.foreignChipRatio !== undefined || row.changePct !== undefined || row.volume !== undefined);
      const showForeignChip = showYahooColumns && activeInstitutionSeries.has("foreign");
      const showPriceColumns = showYahooColumns && activeInstitutionSeries.has("price");
      return `
        <div class="chip-data-table chip-institution-daily-table">
          <div class="chip-data-row is-head is-institution-daily-dynamic" style="--institution-cols:${1 + selectedFlowColumns.length + (showForeignChip ? 1 : 0) + (showPriceColumns ? 2 : 0)}">
            <span>日期</span>
            ${selectedFlowColumns.map((item) => `<span>${escapeHtml(item.label)}</span>`).join("")}
            <span>合計</span>
            ${showForeignChip ? "<span>外資籌碼</span>" : ""}
            ${showPriceColumns ? "<span>漲跌幅</span><span>成交量</span>" : ""}
          </div>
          ${rows.map((row) => `
            <div class="chip-data-row is-institution-daily-dynamic" style="--institution-cols:${1 + selectedFlowColumns.length + (showForeignChip ? 1 : 0) + (showPriceColumns ? 2 : 0)}">
              <span>${escapeHtml(row.date || "--")}</span>
              ${selectedFlowColumns.map((item) => `<strong class="${valueToneClass(row[item.valueKey])}">${formatLots(numberValue(row[item.valueKey]), true)}</strong>`).join("")}
              <strong class="${valueToneClass(row.totalLotsValue)}">${formatLots(numberValue(row.totalLotsValue), true)}</strong>
              ${showForeignChip ? `<strong>${formatPercentText(row.foreignChipRatio)}</strong>` : ""}
              ${showPriceColumns ? `<strong class="${valueToneClass(row.changePct)}">${formatPercentText(row.changePct, true)}</strong><strong>${formatPlainNumber(row.volume)}</strong>` : ""}
            </div>
          `).join("")}
        </div>
      `;
    };
    const renderBrokerBalanceBar = () => {
      const buyLots = Math.abs(numberValue(brokerSummary.buyLots) || 0);
      const sellLots = Math.abs(numberValue(brokerSummary.sellLots) || 0);
      const totalLots = buyLots + sellLots;
      if (!totalLots) return "";
      const buyPct = Math.round((buyLots / totalLots) * 100);
      const sellPct = Math.max(0, 100 - buyPct);
      return `
        <div class="broker-balance-card" aria-label="主力買賣超比例">
          <div class="broker-balance-head">
            <span>主力買賣超比例</span>
            <strong>${buyPct}% / ${sellPct}%</strong>
          </div>
          <div class="broker-balance-track">
            <span class="is-buy" style="width:${buyPct}%"></span>
            <span class="is-sell" style="width:${sellPct}%"></span>
          </div>
          <div class="broker-balance-labels">
            <span><i class="is-buy"></i>買超 ${formatLots(buyLots)}</span>
            <span><i class="is-sell"></i>賣超 ${formatLots(sellLots)}</span>
          </div>
        </div>
      `;
    };
    const renderBrokerRowsWithBars = (rows, title, tone = "buy") => {
      const visibleRows = (rows || []).slice(0, 12);
      const maxNet = Math.max(...visibleRows.map((row) => Math.abs(numberValue(row.net) || 0)), 1);
      const rowTone = tone === "sell" ? "sell" : "buy";
      return `
        <div class="chip-broker-table is-${rowTone}">
          <h5>${escapeHtml(title)}</h5>
          <div class="chip-data-row is-head"><span>券商</span><span>買進</span><span>賣出</span><span>買賣超張數</span></div>
          ${visibleRows.map((row) => {
            const net = numberValue(row.net);
            const width = Math.max(4, Math.min(100, (Math.abs(net || 0) / maxNet) * 100));
            return `
              <div class="chip-data-row chip-broker-row is-${rowTone}">
                <span>${escapeHtml(row.broker || "--")}</span>
                <strong>${formatLots(row.buy)}</strong>
                <strong>${formatLots(row.sell)}</strong>
                <strong class="chip-broker-net">
                  <span class="chip-broker-bar" style="width:${width}%"></span>
                  <b>${formatLots(net, true)}</b>
                </strong>
              </div>
            `;
          }).join("") || '<p class="stock-detail-empty">券商分點資料同步中。</p>'}
        </div>
      `;
    };
    const renderBrokerRows = (rows, title) => `
      <div class="chip-broker-table">
        <h5>${escapeHtml(title)}</h5>
        <div class="chip-data-row is-head"><span>券商</span><span>買進</span><span>賣出</span><span>買賣超</span></div>
        ${(rows || []).slice(0, 10).map((row) => `
          <div class="chip-data-row">
            <span>${escapeHtml(row.broker || "--")}</span>
            <strong>${formatLots(row.buy)}</strong>
            <strong>${formatLots(row.sell)}</strong>
            <strong>${formatLots(row.net, true)}</strong>
          </div>
        `).join("") || '<p class="stock-detail-empty">正在同步券商分點明細。</p>'}
      </div>
    `;
    const formatLotsPlain = (value, signed = false) => formatPlainNumber(value, signed, 0);
    const formatMarginDate = (row, includeEnd = false) => {
      const toSlashDate = (value) => {
        const normalized = normalizeInstitutionDate(value || "");
        return normalized && /^\d{4}-\d{2}-\d{2}$/.test(normalized) ? normalized.replaceAll("-", "/") : (normalized || "--");
      };
      const start = toSlashDate(row?.date);
      const end = toSlashDate(row?.endDate);
      if (includeEnd && end !== "--" && end !== start) return `${start} - ${end.slice(5)}`;
      return start;
    };
    const marginSummaryModeOptions = [
      { key: "today", label: "當日" },
      { key: "acc", label: "累計" },
    ];
    const marginTableTypeOptions = [
      { key: "marginBalance", label: "資券餘額" },
      { key: "lendingBalance", label: "借券賣出餘額" },
    ];
    const marginPeriodOptions = [
      { key: "day", label: "日", title: "逐日" },
      { key: "week", label: "週", title: "逐週" },
      { key: "month", label: "月", title: "逐月" },
      { key: "quarter", label: "季", title: "逐季" },
    ];
    const renderMarginOverviewRows = () => {
      const activeSummaryMode = stockMarginSummaryModeState.get(stateKey) || "today";
      const rows = marginOverviewRows.length
        ? marginOverviewRows
        : [
            {
              key: "financing",
              name: "融資",
              buy: margin.financingBuy,
              sell: margin.financingSell,
              repayment: margin.financingCashRedemption,
              change: financingChange,
              balance: financingBalance,
              utilizationRate: margin.financingUtilizationRate,
              streak: "--",
            },
            {
              key: "short",
              name: "融券",
              buy: margin.shortBuy,
              sell: margin.shortSell,
              repayment: margin.shortStockRedemption,
              change: shortChange,
              balance: shortBalance,
              utilizationRate: margin.shortUtilizationRate,
              streak: "--",
              offsetting: margin.offsetting,
              shortFinancingRatio,
            },
          ].filter((row) => numberValue(row.change) !== null || numberValue(row.balance) !== null);
      if (!rows.length) return "";
      const financingRow = rows.find((row) => row?.key === "financing") || {};
      const shortRow = rows.find((row) => row?.key === "short") || {};
      const tabs = `
        <div class="margin-switch-buttons" role="group" aria-label="資券變化總覽模式">
          ${marginSummaryModeOptions.map((option) => `<button class="range-button ${option.key === activeSummaryMode ? "is-active" : ""}" type="button" data-margin-summary-mode="${escapeHtml(option.key)}" aria-pressed="${option.key === activeSummaryMode ? "true" : "false"}">${escapeHtml(option.label)}</button>`).join("")}
        </div>
      `;
      const renderTodaySummary = () => `
        <div class="margin-table-scroll">
          <div class="margin-summary-table is-today">
            <div class="margin-summary-row is-head">
              <span></span><span>買進</span><span>賣出</span><span>現償</span><span>增減</span><span>餘額</span><span>使用率</span><span>連增連減</span><span>資券互抵</span><span>券資比</span>
            </div>
            <div class="margin-summary-row">
              <span>融資</span>
              <strong>${formatLotsPlain(financingRow.buy)}</strong>
              <strong>${formatLotsPlain(financingRow.sell)}</strong>
              <strong>${formatLotsPlain(financingRow.repayment)}</strong>
              <strong class="${valueToneClass(financingRow.change)}">${formatLotsPlain(financingRow.change, true)}</strong>
              <strong>${formatLotsPlain(financingRow.balance)}</strong>
              <strong>${formatPercentText(financingRow.utilizationRate)}</strong>
              <span>${escapeHtml(financingRow.streak || "--")}</span>
              <strong>${formatLotsPlain(shortRow.offsetting)}</strong>
              <strong class="is-muted">--</strong>
            </div>
            <div class="margin-summary-row">
              <span>融券</span>
              <strong>${formatLotsPlain(shortRow.buy)}</strong>
              <strong>${formatLotsPlain(shortRow.sell)}</strong>
              <strong>${formatLotsPlain(shortRow.repayment)}</strong>
              <strong class="${valueToneClass(shortRow.change)}">${formatLotsPlain(shortRow.change, true)}</strong>
              <strong>${formatLotsPlain(shortRow.balance)}</strong>
              <strong>${formatPercentText(shortRow.utilizationRate)}</strong>
              <span>${escapeHtml(shortRow.streak || "--")}</span>
              <strong class="is-muted">--</strong>
              <strong class="margin-ratio-cell">${formatPercentText(shortRow.shortFinancingRatio)}${shortRow.ratioStreak ? `<small>(${escapeHtml(shortRow.ratioStreak)})</small>` : ""}</strong>
            </div>
          </div>
        </div>
      `;
      const renderAccumulationSummary = () => {
        const accRows = Array.isArray(margin.marginSummaryAccumulationRows) ? margin.marginSummaryAccumulationRows : [];
        const accByKey = new Map(accRows.map((row) => [String(row.periodSum || ""), row]));
        const periods = [
          { key: "2D", label: "2日" },
          { key: "3D", label: "3日" },
          { key: "5D", label: "5日" },
          { key: "10D", label: "10日" },
          { key: "1M", label: "1月" },
          { key: "3M", label: "3月" },
          { key: "6M", label: "6月" },
          { key: "1Y", label: "1年" },
        ];
        const cell = (period, key, formatter) => {
          const row = accByKey.get(period.key) || {};
          const value = row[key];
          return `<strong class="${valueToneClass(value)}">${formatter(value)}</strong>`;
        };
        return `
          <div class="margin-table-scroll">
            <div class="margin-summary-table is-acc">
              <div class="margin-summary-row is-head">
                <span>項目</span>${periods.map((period) => `<span>${escapeHtml(period.label)}</span>`).join("")}
              </div>
              <div class="margin-summary-row">
                <span>融資增減</span>${periods.map((period) => cell(period, "financingChange", (value) => formatLotsPlain(value, true))).join("")}
              </div>
              <div class="margin-summary-row">
                <span>融券增減</span>${periods.map((period) => cell(period, "shortChange", (value) => formatLotsPlain(value, true))).join("")}
              </div>
              <div class="margin-summary-row">
                <span>券資比增減</span>${periods.map((period) => cell(period, "shortFinancingRatioChange", (value) => formatPercentText(value, true))).join("")}
              </div>
            </div>
          </div>
        `;
      };
      return `
        <div class="chip-visual-card margin-summary-card">
          <div class="chip-visual-head"><span>資券變化總覽</span><strong>資料時間：${escapeHtml(formatMarginDate({ date: margin.date || detail.snapshotDate }))}</strong></div>
          ${tabs}
          ${activeSummaryMode === "acc" ? renderAccumulationSummary() : renderTodaySummary()}
        </div>
      `;
    };
    const renderMarginDailyRows = () => {
      const activeTableType = stockMarginTableTypeState.get(stateKey) || "marginBalance";
      const activePeriodKey = stockMarginPeriodState.get(stateKey) || "day";
      const activePeriod = marginPeriodOptions.find((option) => option.key === activePeriodKey) || marginPeriodOptions[0];
      const periodRows = margin.marginBalancePeriodRows && typeof margin.marginBalancePeriodRows === "object"
        ? margin.marginBalancePeriodRows
        : {};
      const sourceRows = Array.isArray(periodRows[activePeriod.key]) && periodRows[activePeriod.key].length
        ? periodRows[activePeriod.key]
        : activePeriod.key === "day" ? marginDailyRows : [];
      const rows = sourceRows.slice(0, 30);
      if (!rows.length) return "";
      const controls = `
        <div class="margin-table-controls">
          <div class="margin-switch-buttons" role="group" aria-label="資券餘額表格類型">
            ${marginTableTypeOptions.map((option) => `<button class="range-button ${option.key === activeTableType ? "is-active" : ""}" type="button" data-margin-table-type="${escapeHtml(option.key)}" aria-pressed="${option.key === activeTableType ? "true" : "false"}">${escapeHtml(option.label)}</button>`).join("")}
          </div>
          <div class="margin-switch-buttons" role="group" aria-label="資券餘額期間">
            ${marginPeriodOptions.map((option) => `<button class="range-button ${option.key === activePeriod.key ? "is-active" : ""}" type="button" data-margin-period="${escapeHtml(option.key)}" aria-pressed="${option.key === activePeriod.key ? "true" : "false"}">${escapeHtml(option.label)}</button>`).join("")}
          </div>
        </div>
      `;
      const renderMarginBalanceTable = () => `
        <div class="margin-table-scroll">
          <div class="margin-period-grid is-margin">
            <div class="margin-period-row is-group is-margin">
              <span></span><strong class="margin-period-group is-financing">融資</strong><strong class="margin-period-group is-short">融券</strong><span></span><span></span>
            </div>
            <div class="margin-period-row is-head is-margin">
              <span>日期</span><span>增減</span><span>餘額</span><span>使用率%</span><span>增減</span><span>餘額</span><span>使用率%</span><span>券資比</span><span>資券互抵</span>
            </div>
            ${rows.map((row) => `
              <div class="margin-period-row is-margin">
                <span>${escapeHtml(formatMarginDate(row, activePeriod.key !== "day"))}</span>
                <strong class="${valueToneClass(row.financingChange)}">${formatLotsPlain(row.financingChange, true)}</strong>
                <strong>${formatLotsPlain(row.financingBalance)}</strong>
                <strong>${formatPercentText(row.financingUtilizationRate)}</strong>
                <strong class="${valueToneClass(row.shortChange)}">${formatLotsPlain(row.shortChange, true)}</strong>
                <strong>${formatLotsPlain(row.shortBalance)}</strong>
                <strong>${formatPercentText(row.shortUtilizationRate)}</strong>
                <strong>${formatPercentText(row.shortFinancingRatio)}</strong>
                <strong>${formatLotsPlain(row.offsetting)}</strong>
              </div>
            `).join("")}
          </div>
        </div>
      `;
      const renderLendingBalanceTable = () => `
        <div class="margin-table-scroll">
          <div class="margin-period-grid is-lending">
            <div class="margin-period-row is-group is-lending">
              <span></span><strong class="margin-period-group is-short">融券</strong><strong class="margin-period-group is-lending">借券賣出</strong>
            </div>
            <div class="margin-period-row is-head is-lending">
              <span>日期</span><span>增減</span><span>餘額</span><span>限額</span><span>增減</span><span>餘額</span>
            </div>
            ${rows.map((row) => `
              <div class="margin-period-row is-lending">
                <span>${escapeHtml(formatMarginDate(row, activePeriod.key !== "day"))}</span>
                <strong class="${valueToneClass(row.shortChange)}">${formatLotsPlain(row.shortChange, true)}</strong>
                <strong>${formatLotsPlain(row.shortBalance)}</strong>
                <strong>${formatLotsPlain(row.shortLimit)}</strong>
                <strong class="${valueToneClass(row.lendingChange)}">${formatLotsPlain(row.lendingChange, true)}</strong>
                <strong>${formatLotsPlain(row.lendingBalance)}</strong>
              </div>
            `).join("")}
          </div>
        </div>
      `;
      return `
        <div class="chip-visual-card margin-period-card">
          <div class="chip-visual-head"><span>${activeTableType === "lendingBalance" ? "借券賣出餘額" : "資券餘額"}${activePeriod.title}增減</span><strong>${escapeHtml(rows[0]?.date ? formatMarginDate(rows[0]) : margin.date || "--")}</strong></div>
          ${controls}
          ${activeTableType === "lendingBalance" ? renderLendingBalanceTable() : renderMarginBalanceTable()}
        </div>
      `;
    };
    const renderMarginRows = () => {
      const overview = renderMarginOverviewRows();
      const daily = renderMarginDailyRows();
      if (overview || daily) return `${overview}${daily}`;
      return `
        <div class="chip-data-table">
          <div class="chip-data-row is-head"><span>項目</span><span>買進/賣出</span><span>償還</span><span>增減</span><span>餘額</span></div>
          <div class="chip-data-row"><span>融資</span><strong>${formatLots(margin.financingBuy)}</strong><strong>${formatLots(margin.financingCashRedemption)}</strong><strong>${formatLots(financingChange, true)}</strong><strong>${formatLots(financingBalance)}</strong></div>
          <div class="chip-data-row"><span>融券</span><strong>${formatLots(margin.shortSell)}</strong><strong>${formatLots(margin.shortStockRedemption)}</strong><strong>${formatLots(shortChange, true)}</strong><strong>${formatLots(shortBalance)}</strong></div>
        </div>
      `;
    };
    const renderMarginBalanceVisual = () => {
      const chartRows = Array.isArray(margin.marginBalanceChartRows) ? margin.marginBalanceChartRows : [];
      const sourceRows = (chartRows.length ? chartRows : marginDailyRows)
        .map((row) => ({
          ...row,
          date: normalizeInstitutionDate(row?.date || row?.fullDate || ""),
          label: row?.label || String(row?.date || "").slice(5).replace("-", "/"),
          price: numberValue(row?.closePrice),
          financing: numberValue(row?.financingBalance),
          financingChange: numberValue(row?.financingChange),
          short: numberValue(row?.shortBalance),
          shortChange: numberValue(row?.shortChange),
          lending: numberValue(row?.lendingBalance),
          lendingChange: numberValue(row?.lendingChange),
          changePct: numberValue(row?.changePct),
        }))
        .filter((row) => row.date)
        .sort((left, right) => String(left.date || "").localeCompare(String(right.date || "")));
      if (sourceRows.length < 2) {
        return "";
      }

      const marginRangeOptions = [
        { key: "1m", label: "1個月", days: 31, fallbackCount: 30 },
        { key: "3m", label: "3個月", days: 93, fallbackCount: 90 },
        { key: "6m", label: "6個月", days: 186, fallbackCount: 182 },
        { key: "1y", label: "1年", days: 366, fallbackCount: 365 },
      ];
      const activeMarginRangeKey = stockMarginRangeState.get(stateKey) || "1m";
      const activeMarginRange = marginRangeOptions.find((item) => item.key === activeMarginRangeKey) || marginRangeOptions[0];
      const latestTime = Math.max(...sourceRows.map((row) => new Date(row.date).getTime()).filter(Number.isFinite));
      const cutoffTime = Number.isFinite(latestTime) ? latestTime - activeMarginRange.days * 24 * 60 * 60 * 1000 : null;
      const rangedRows = cutoffTime
        ? sourceRows.filter((row) => {
            const time = new Date(row.date).getTime();
            return Number.isFinite(time) && time >= cutoffTime && time <= latestTime;
          })
        : [];
      const rows = (rangedRows.length >= 2 ? rangedRows : sourceRows.slice(-activeMarginRange.fallbackCount));
      const width = 760;
      const panelHeight = 64;
      const panelGap = 15;
      const pad = { left: 42, right: 78, top: 14, bottom: 30 };
      const height = pad.top + pad.bottom + panelHeight * 4 + panelGap * 3;
      const usableWidth = width - pad.left - pad.right;
      const step = rows.length > 1 ? usableWidth / (rows.length - 1) : usableWidth;
      const points = rows.map((row, index) => ({
        ...row,
        x: pad.left + (rows.length > 1 ? index * step : usableWidth / 2),
      }));
      const series = [
        { key: "price", label: "股價", valueKey: "price", changeKey: "changePct", valueFormatter: (value) => formatPlainNumber(value, false, Number(value) >= 100 ? 0 : 2), axisFormatter: (value) => formatPlainNumber(value, false, Number(value) >= 100 ? 0 : 2), changeFormatter: (value) => formatPercentText(value, true), panel: 0 },
        { key: "financing", label: "融資餘額", valueKey: "financing", changeKey: "financingChange", valueFormatter: (value) => formatLots(value), axisFormatter: (value) => formatPlainNumber(value, false, 0), changeFormatter: (value) => formatLots(value, true), panel: 1 },
        { key: "short", label: "融券餘額", valueKey: "short", changeKey: "shortChange", valueFormatter: (value) => formatLots(value), axisFormatter: (value) => formatPlainNumber(value, false, 0), changeFormatter: (value) => formatLots(value, true), panel: 2 },
        { key: "lending", label: "借券賣出餘額", valueKey: "lending", changeKey: "lendingChange", valueFormatter: (value) => formatLots(value), axisFormatter: (value) => formatPlainNumber(value, false, 0), changeFormatter: (value) => formatLots(value, true), panel: 3 },
      ];
      const panelTop = (index) => pad.top + index * (panelHeight + panelGap);
      const panelBottom = (index) => panelTop(index) + panelHeight;
      const niceAxisStep = (rawStep) => {
        const value = Math.abs(Number(rawStep) || 0);
        if (!Number.isFinite(value) || value <= 0) return 1;
        const power = Math.pow(10, Math.floor(Math.log10(value)));
        const fraction = value / power;
        const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
        return niceFraction * power;
      };
      const buildMarginAxisStats = (item) => {
        const values = points.map((point) => point[item.valueKey]).filter(Number.isFinite);
        let rawMin = values.length ? Math.min(...values) : 0;
        let rawMax = values.length ? Math.max(...values) : 1;
        const nonNegativeAxis = item.key !== "price";
        if (nonNegativeAxis) rawMin = Math.max(0, rawMin);
        if (rawMax === rawMin) {
          const spread = Math.max(Math.abs(rawMax || 1) * 0.08, 1);
          rawMin -= spread;
          rawMax += spread;
          if (nonNegativeAxis) rawMin = 0;
        }

        if (nonNegativeAxis) {
          let zeroStep = niceAxisStep(Math.max(rawMax, 1) / 2);
          if (rawMin <= zeroStep * 1.25) {
            let tickMax = zeroStep * 2;
            for (let attempt = 0; rawMax > tickMax + zeroStep * 0.02 && attempt < 8; attempt += 1) {
              const nextStep = niceAxisStep(zeroStep * 1.25);
              zeroStep = nextStep > zeroStep ? nextStep : zeroStep * 2;
              tickMax = zeroStep * 2;
            }
            return {
              values,
              minValue: 0,
              maxValue: tickMax + zeroStep * 0.04,
              ticks: [tickMax, zeroStep, 0],
            };
          }
        }

        const rawRange = Math.max(rawMax - rawMin, Math.abs(rawMax || 1) * 0.04, 1);
        let step = niceAxisStep(rawRange / 2);
        let tickMin = 0;
        let tickMax = 0;
        for (let attempt = 0; attempt < 8; attempt += 1) {
          tickMin = Math.floor(rawMin / step) * step;
          if (nonNegativeAxis) tickMin = Math.max(0, tickMin);
          tickMax = tickMin + step * 2;
          while (rawMax > tickMax + step * 0.02 && tickMin + step <= rawMin) {
            tickMin += step;
            tickMax += step;
          }
          if (rawMax <= tickMax + step * 0.02 || attempt === 7) break;
          const nextStep = niceAxisStep(step * 1.25);
          step = nextStep > step ? nextStep : step * 2;
        }
        const topOverflow = Math.max(0, rawMax - tickMax);
        const bottomOverflow = Math.max(0, tickMin - rawMin);
        return {
          values,
          minValue: Math.max(nonNegativeAxis ? 0 : -Infinity, tickMin - Math.max(bottomOverflow, step * 0.04)),
          maxValue: tickMax + Math.max(topOverflow, step * 0.04),
          ticks: [tickMax, tickMin + step, tickMin],
        };
      };
      const seriesStats = new Map(series.map((item) => [item.key, buildMarginAxisStats(item)]));
      const yFor = (seriesItem, value) => {
        const stats = seriesStats.get(seriesItem.key);
        const top = panelTop(seriesItem.panel);
        const bottom = panelBottom(seriesItem.panel);
        if (!stats || !Number.isFinite(value)) return bottom;
        return top + ((stats.maxValue - value) / Math.max(stats.maxValue - stats.minValue, 1)) * (bottom - top);
      };
      const linePath = (seriesItem) => points
        .filter((point) => Number.isFinite(point[seriesItem.valueKey]))
        .map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(2)} ${yFor(seriesItem, point[seriesItem.valueKey]).toFixed(2)}`)
        .join(" ");
      const areaPath = (seriesItem) => {
        const usable = points.filter((point) => Number.isFinite(point[seriesItem.valueKey]));
        if (usable.length < 2) return "";
        const line = usable.map((point, index) => `${index ? "L" : "M"} ${point.x.toFixed(2)} ${yFor(seriesItem, point[seriesItem.valueKey]).toFixed(2)}`).join(" ");
        const bottom = panelBottom(seriesItem.panel);
        return `${line} L ${usable.at(-1).x.toFixed(2)} ${bottom.toFixed(2)} L ${usable[0].x.toFixed(2)} ${bottom.toFixed(2)} Z`;
      };
      const panelGrid = series.map((item) => {
        const stats = seriesStats.get(item.key);
        const top = panelTop(item.panel);
        const bottom = panelBottom(item.panel);
        const axisFormatter = item.axisFormatter || item.valueFormatter;
        const tickLines = (Array.isArray(stats?.ticks) ? stats.ticks : [stats?.maxValue, (stats?.maxValue + stats?.minValue) / 2, stats?.minValue])
          .filter(Number.isFinite)
          .map((value) => {
            const y = yFor(item, value);
            const labelY = Math.max(top + 10, Math.min(bottom - 6, y));
            return `
              <line class="chip-margin-grid-line" x1="${pad.left}" y1="${y.toFixed(2)}" x2="${width - pad.right}" y2="${y.toFixed(2)}"></line>
              <text class="chip-margin-axis-label" x="${width - pad.right + 12}" y="${labelY.toFixed(2)}">${escapeHtml(axisFormatter(value))}</text>
            `;
          }).join("");
        return `
          <g class="chip-margin-panel is-${item.key}">
            ${tickLines}
          </g>
        `;
      }).join("");
      const paths = series.map((item) => {
        const path = linePath(item);
        const area = areaPath(item);
        return `
          ${area ? `<path class="chip-margin-area is-${item.key}" d="${area}"></path>` : ""}
          ${path ? `<path class="chip-margin-line is-${item.key}" d="${path}"></path>` : ""}
        `;
      }).join("");
      const tickIndexes = [...new Set([0, Math.floor((rows.length - 1) * 0.2), Math.floor((rows.length - 1) * 0.4), Math.floor((rows.length - 1) * 0.6), Math.floor((rows.length - 1) * 0.8), rows.length - 1])];
      const ticks = tickIndexes.map((index) => {
        const point = points[index];
        if (!point) return "";
        return `<text class="chip-margin-date-label" x="${point.x.toFixed(2)}" y="${height - 8}" text-anchor="${index === 0 ? "start" : index === rows.length - 1 ? "end" : "middle"}">${escapeHtml(point.label || String(point.date || "").slice(5))}</text>`;
      }).join("");
      const zoneWidth = rows.length > 1 ? Math.max(8, step) : usableWidth;
      const hoverZones = points.map((point) => {
        const primarySeries = series.find((item) => Number.isFinite(point[item.valueKey])) || series[0];
        const zoneX = rows.length > 1
          ? Math.max(pad.left, Math.min(width - pad.right - zoneWidth, point.x - zoneWidth / 2))
          : pad.left;
        return `<rect class="margin-hover-zone" x="${zoneX.toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${(height - pad.top - pad.bottom).toFixed(2)}" data-x="${point.x.toFixed(2)}" data-y="${yFor(primarySeries, point[primarySeries.valueKey]).toFixed(2)}" data-date="${escapeHtml(point.date || "--")}" data-price="${escapeHtml(series[0].valueFormatter(point.price))}" data-price-change="${escapeHtml(series[0].changeFormatter(point.changePct))}" data-financing="${escapeHtml(series[1].valueFormatter(point.financing))}" data-financing-change="${escapeHtml(series[1].changeFormatter(point.financingChange))}" data-short="${escapeHtml(series[2].valueFormatter(point.short))}" data-short-change="${escapeHtml(series[2].changeFormatter(point.shortChange))}" data-lending="${escapeHtml(series[3].valueFormatter(point.lending))}" data-lending-change="${escapeHtml(series[3].changeFormatter(point.lendingChange))}"></rect>`;
      }).join("");
      const unavailableLongRange = ["6m", "1y"].includes(activeMarginRange.key) && rows.length < activeMarginRange.fallbackCount * 0.65;
      return `
        <div class="chip-visual-card margin-balance-visual">
          <div class="chip-visual-head"><span>資券餘額變化</span><strong>資料時間：${escapeHtml(margin.date || rows.at(-1)?.date || detail.snapshotDate || "--")}</strong></div>
          <div class="margin-range-buttons" role="group" aria-label="資券餘額期間">
            ${marginRangeOptions.map((option) => `<button class="range-button ${option.key === activeMarginRange.key ? "is-active" : ""}" type="button" data-margin-range="${escapeHtml(option.key)}">${escapeHtml(option.label)}</button>`).join("")}
          </div>
          ${renderChipVisualLegend([
            { key: "price", label: "股價" },
            { key: "financing", label: "融資餘額" },
            { key: "short", label: "融券餘額" },
            { key: "lending", label: "借券賣出餘額" },
          ])}
          <div class="margin-balance-chart-stage">
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="資券餘額變化圖">
              ${panelGrid}
              ${paths}
              ${ticks}
              <line class="institution-crosshair is-x" data-margin-cursor-x x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
              <circle class="institution-crosshair-dot" data-margin-cursor-dot cx="${pad.left}" cy="${panelTop(0)}" r="4"></circle>
              ${hoverZones}
            </svg>
            <div class="institution-chart-tooltip margin-chart-tooltip" hidden></div>
          </div>
          <p class="institution-chart-note">${unavailableLongRange ? "Yahoo 目前頁面預載未涵蓋完整長區間，已顯示可取得的線上真實資料。" : `顯示 ${rows.length.toLocaleString("zh-TW")} 筆 Yahoo 線上真實資料。`}</p>
        </div>
      `;
    };
    const renderMajorHolderChart = () => {
      const chartRows = Array.isArray(majorData.rows) ? majorData.rows : [];
      const rows = chartRows
        .map((row) => ({
          ...row,
          date: normalizeInstitutionDate(row?.date || ""),
          foreign: numberValue(row?.foreignChipRatio),
          major: numberValue(row?.majorHolderRatio),
          director: numberValue(row?.directorHoldingRatio),
          price: numberValue(row?.price),
        }))
        .filter((row) => row.date && (
          Number.isFinite(row.foreign)
          || Number.isFinite(row.major)
          || Number.isFinite(row.director)
          || Number.isFinite(row.price)
        ))
        .sort((left, right) => String(left.date || "").localeCompare(String(right.date || "")))
        .slice(-260);
      if (rows.length < 2) return "";

      const width = 760;
      const height = 290;
      const pad = { left: 50, right: 64, top: 18, bottom: 56 };
      const plotHeight = height - pad.top - pad.bottom;
      const usableWidth = width - pad.left - pad.right;
      const step = rows.length > 1 ? usableWidth / (rows.length - 1) : usableWidth;
      const points = rows.map((row, index) => ({
        ...row,
        x: pad.left + (rows.length > 1 ? index * step : usableWidth / 2),
        label: String(row.date || "").replace(/-/g, "/"),
      }));

      const niceAxisStep = (rawStep) => {
        const value = Math.abs(Number(rawStep) || 0);
        if (!Number.isFinite(value) || value <= 0) return 1;
        const power = Math.pow(10, Math.floor(Math.log10(value)));
        const fraction = value / power;
        const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
        return niceFraction * power;
      };
      const prices = points.map((item) => item.price).filter(Number.isFinite);
      const rawPriceMin = prices.length ? Math.min(...prices) : 0;
      const rawPriceMax = prices.length ? Math.max(...prices) : 1;
      let priceStep = niceAxisStep(Math.max(rawPriceMax - rawPriceMin, Math.abs(rawPriceMax || 1) * 0.08, 1) / 7);
      let priceAxisMin = Math.floor(rawPriceMin / priceStep) * priceStep;
      let priceAxisMax = Math.ceil(rawPriceMax / priceStep) * priceStep;
      for (let guard = 0; (priceAxisMax - priceAxisMin) / priceStep > 8 && guard < 8; guard += 1) {
        priceStep = niceAxisStep(priceStep * 1.8);
        priceAxisMin = Math.floor(rawPriceMin / priceStep) * priceStep;
        priceAxisMax = Math.ceil(rawPriceMax / priceStep) * priceStep;
      }
      if (priceAxisMax <= priceAxisMin) priceAxisMax = priceAxisMin + priceStep;
      const priceTicks = [];
      for (let value = priceAxisMin; value <= priceAxisMax + priceStep * 0.02; value += priceStep) {
        priceTicks.push(value);
      }

      const yPercent = (value) => pad.top + ((100 - Math.max(0, Math.min(100, value || 0))) / 100) * plotHeight;
      const yPrice = (value) => pad.top + ((priceAxisMax - value) / Math.max(priceAxisMax - priceAxisMin, 1)) * plotHeight;
      const path = (key, yGetter) => points
        .filter((item) => Number.isFinite(item[key]))
        .map((item, index) => `${index ? "L" : "M"} ${item.x.toFixed(2)} ${yGetter(item[key]).toFixed(2)}`)
        .join(" ");
      const pricePath = path("price", yPrice);
      const areaPath = pricePath
        ? `${pricePath} L ${points.at(-1).x.toFixed(2)} ${yPrice(priceAxisMin).toFixed(2)} L ${points[0].x.toFixed(2)} ${yPrice(priceAxisMin).toFixed(2)} Z`
        : "";
      const percentTicks = [100, 80, 60, 40, 20, 0];
      const gridLines = percentTicks.map((value) => {
        const y = yPercent(value);
        return `
          <line class="chip-holder-grid-line" x1="${pad.left}" y1="${y.toFixed(2)}" x2="${width - pad.right}" y2="${y.toFixed(2)}"></line>
          <text class="chip-holder-axis-label is-percent" x="${pad.left - 8}" y="${y.toFixed(2)}">${value}%</text>
        `;
      }).join("");
      const priceAxisLabels = priceTicks.map((value) => {
        const y = yPrice(value);
        return `<text class="chip-holder-axis-label is-price" x="${width - pad.right + 8}" y="${y.toFixed(2)}">${escapeHtml(formatPlainNumber(value, false, 0))}</text>`;
      }).join("");
      const tickIndexes = [...new Set([
        0,
        Math.floor((rows.length - 1) * 0.12),
        Math.floor((rows.length - 1) * 0.24),
        Math.floor((rows.length - 1) * 0.36),
        Math.floor((rows.length - 1) * 0.48),
        Math.floor((rows.length - 1) * 0.60),
        Math.floor((rows.length - 1) * 0.72),
        Math.floor((rows.length - 1) * 0.84),
        rows.length - 1,
      ])];
      const dateTicks = tickIndexes.map((index) => {
        const point = points[index];
        if (!point) return "";
        return `<text class="chip-holder-date-label" x="${point.x.toFixed(2)}" y="${height - 12}" transform="rotate(-45 ${point.x.toFixed(2)} ${height - 12})">${escapeHtml(point.label)}</text>`;
      }).join("");
      const zoneWidth = rows.length > 1 ? Math.max(8, step) : usableWidth;
      const hoverZones = points.map((point) => {
        const zoneX = rows.length > 1
          ? Math.max(pad.left, Math.min(width - pad.right - zoneWidth, point.x - zoneWidth / 2))
          : pad.left;
        const primaryY = Number.isFinite(point.major)
          ? yPercent(point.major)
          : Number.isFinite(point.price) ? yPrice(point.price) : pad.top + plotHeight / 2;
        return `<rect class="holder-hover-zone" x="${zoneX.toFixed(2)}" y="${pad.top}" width="${zoneWidth.toFixed(2)}" height="${plotHeight.toFixed(2)}" data-x="${point.x.toFixed(2)}" data-y="${primaryY.toFixed(2)}" data-y-price="${Number.isFinite(point.price) ? yPrice(point.price).toFixed(2) : ""}" data-y-foreign="${Number.isFinite(point.foreign) ? yPercent(point.foreign).toFixed(2) : ""}" data-y-major="${Number.isFinite(point.major) ? yPercent(point.major).toFixed(2) : ""}" data-y-director="${Number.isFinite(point.director) ? yPercent(point.director).toFixed(2) : ""}" data-date="${escapeHtml(point.label || "--")}" data-price="${escapeHtml(formatPlainNumber(point.price, false, Number(point.price) >= 100 ? 0 : 2))}" data-foreign="${escapeHtml(formatPercentText(point.foreign))}" data-major="${escapeHtml(formatPercentText(point.major))}" data-director="${escapeHtml(formatPercentText(point.director))}"></rect>`;
      }).join("");

      return `
        <div class="chip-visual-card major-holder-chart">
          <div class="chip-visual-head">
            <span>大戶籌碼 <i class="chip-info-icon" title="同步 Yahoo 股市大戶籌碼，左軸為籌碼比例，右軸為股價。">i</i></span>
            <strong>資料時間：${escapeHtml(majorData.date || rows.at(-1)?.date || holders.date || "--")}</strong>
          </div>
          ${renderChipVisualLegend([
            { key: "price", label: "股價" },
            { key: "foreign", label: "外資籌碼" },
            { key: "major", label: "大戶籌碼" },
            { key: "director", label: "董監持股" },
          ])}
          <div class="major-holder-chart-stage">
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="大戶籌碼趨勢圖">
              <line class="chip-chart-axis" x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}"></line>
              ${gridLines}
              ${priceAxisLabels}
              ${areaPath ? `<path class="chip-holder-price-area" d="${areaPath}"></path>` : ""}
              ${pricePath ? `<path class="chip-holder-price-line" d="${pricePath}"></path>` : ""}
              <path class="chip-holder-line is-foreign" d="${path("foreign", yPercent)}"></path>
              <path class="chip-holder-line is-major" d="${path("major", yPercent)}"></path>
              <path class="chip-holder-line is-director" d="${path("director", yPercent)}"></path>
              ${dateTicks}
              <line class="institution-crosshair is-x" data-holder-cursor-x x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
              <circle class="institution-crosshair-dot chip-holder-dot is-price" data-holder-cursor-dot="price" cx="${pad.left}" cy="${pad.top}" r="4"></circle>
              <circle class="institution-crosshair-dot chip-holder-dot is-foreign" data-holder-cursor-dot="foreign" cx="${pad.left}" cy="${pad.top}" r="4"></circle>
              <circle class="institution-crosshair-dot chip-holder-dot is-major" data-holder-cursor-dot="major" cx="${pad.left}" cy="${pad.top}" r="4"></circle>
              <circle class="institution-crosshair-dot chip-holder-dot is-director" data-holder-cursor-dot="director" cx="${pad.left}" cy="${pad.top}" r="4"></circle>
              ${hoverZones}
            </svg>
            <div class="institution-chart-tooltip holder-chart-tooltip" hidden></div>
          </div>
        </div>
      `;
    };
    const renderHolderRows = () => `
      <div class="holder-ratio-chart chip-holder-panel">
        <div class="holder-ratio-bar">
          <span class="holder-ratio-segment is-large" style="width:${Math.max(0, Math.min(100, large || 0))}%"></span>
          <span class="holder-ratio-segment is-other" style="width:${Math.max(0, Math.min(100, other || 0))}%"></span>
          <span class="holder-ratio-segment is-retail" style="width:${Math.max(0, Math.min(100, retail || 0))}%"></span>
        </div>
        <div class="chip-data-table">
          <div class="chip-data-row is-head"><span>資料日</span><span>大戶</span><span>外資籌碼</span><span>董監持股</span><span>股價</span></div>
          ${(Array.isArray(majorData.rows) && majorData.rows.length ? majorData.rows.slice(0, 12) : [{ date: holders.date, majorHolderRatio: large, foreignChipRatio: foreignChip, directorHoldingRatio: directorHolding, price: detail.close }]).map((row) => `
            <div class="chip-data-row"><span>${escapeHtml(row.date || "--")}</span><strong>${formatPercentText(row.majorHolderRatio)}</strong><strong>${formatPercentText(row.foreignChipRatio)}</strong><strong>${formatPercentText(row.directorHoldingRatio)}</strong><strong>${escapeHtml(row.price ?? "--")}</strong></div>
          `).join("")}
        </div>
      </div>
    `;
    const renderActiveContent = () => {
      if (activeCard.key === "institutional") return `${renderMetrics(activeCard)}${renderInstitutionOverview()}${renderInstitutionChart()}${renderInstitutionRows()}`;
      if (activeCard.key === "mainForce") return `${renderMetrics(activeCard)}${renderBrokerBalanceBar()}<div class="chip-broker-grid">${renderBrokerRowsWithBars(broker.buyBrokers, "買超券商", "buy")}${renderBrokerRowsWithBars(broker.sellBrokers, "賣超券商", "sell")}</div>`;
      if (activeCard.key === "margin") return `${renderMetrics(activeCard)}${renderMarginBalanceVisual()}${Object.keys(margin).length ? renderMarginRows() : '<p class="stock-detail-empty">資券資料目前未取得。</p>'}`;
      return `${renderMetrics(activeCard)}${renderMajorHolderChart()}${holderAvailable ? renderHolderRows() : `<p class="stock-detail-empty">正在同步 Yahoo 大戶籌碼資料。</p>`}`;
    };
    return `
      <section class="chip-tab-shell" aria-label="籌碼分頁">
        <div class="chip-tab-bar" role="tablist">
          ${cards.map((card) => `<button class="${card.key === activeCard.key ? "is-active" : ""}" type="button" data-chip-tab="${card.key}" role="tab">${escapeHtml(card.tab)}</button>`).join("")}
        </div>
        <article class="chip-tab-panel is-${escapeHtml(activeCard.tone || "flat")}">
          <div class="chip-summary-head">
            <div><span>${escapeHtml(activeCard.key === "mainForce" ? "Broker flow" : activeCard.key === "largeHolder" ? "Holder" : activeCard.key === "margin" ? "Margin" : "Institution")}</span><strong>${escapeHtml(activeCard.title)}</strong></div>
            <b>${escapeHtml(activeCard.label || "--")}</b>
          </div>
          ${renderActiveContent()}
          <p class="chip-source-note">${escapeHtml(activeCard.sourceNote || "")} ${activeCard.sourceLink ? `<a href="${safeUrl(activeCard.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
        </article>
        ${renderHolderDistribution(holderVisualDistribution)}
      </section>
    `;
  };

  const analysisHtml = analysisSections.map((section) => `
    <article class="analysis-card ${section.key === "chips" ? "analysis-card-chips" : ""}">
      <div class="card-title-row">
        <h4>${section.title}</h4>
      </div>
      <p class="card-copy">${section.summary}</p>
      ${section.key === "chips" ? renderChipDashboard(section) : ""}
      <ul class="analysis-list">
        ${(section.items || []).map((item) => `<li>${item}</li>`).join("")}
      </ul>
    </article>
  `).join("");
  const companyNews = Array.isArray(detail.companyNews) ? detail.companyNews : [];
  const isEtfDetail = Boolean(detail.isEtf);
  const newsKicker = isEtfDetail ? "ETF news" : "Company news";
  const newsSubtitle = isEtfDetail
    ? `${escapeHtml(detail.code)} ${escapeHtml(detail.name)} 近期 ETF 新聞、配息公告與發行投信消息。`
    : `${escapeHtml(detail.code)} ${escapeHtml(detail.name)} 近期公司新聞與公開消息。`;
  const newsEmptyText = isEtfDetail
    ? "目前未取得即時 ETF 新聞，請使用下方 ETF 消息來源查詢。"
    : "目前未取得近期公司新聞，可使用下方來源連結查詢。";
  const companyNewsHtml = `
    <section class="company-news-card">
      <div class="card-title-row">
        <div>
          <p class="panel-kicker">${newsKicker}</p>
          <h3>消息面</h3>
          <p class="chart-subtitle">${newsSubtitle}</p>
        </div>
        <span class="chip chip-blue">${companyNews.length} 則消息</span>
      </div>
      <div class="company-news-list">
        ${companyNews.map((item) => `
          <a class="company-news-item" href="${safeUrl(item.link)}" target="_blank" rel="noreferrer noopener">
            <div>
              <strong>${escapeHtml(item.title)}</strong>
              <span>${escapeHtml(item.source || "新聞來源")} · ${escapeHtml(item.publishedAt || "--")}</span>
            </div>
            <b>閱讀消息</b>
          </a>
        `).join("") || `<p class="stock-detail-empty">${newsEmptyText}</p>`}
      </div>
      <div class="company-news-sources">
        ${detail.newsLinks?.yahoo ? `<a href="${safeUrl(detail.newsLinks.yahoo)}" target="_blank" rel="noreferrer noopener">${isEtfDetail ? "Yahoo ETF 新聞" : "Yahoo 個股新聞"}</a>` : ""}
        ${detail.newsLinks?.google ? `<a href="${safeUrl(detail.newsLinks.google)}" target="_blank" rel="noreferrer noopener">Google 新聞搜尋</a>` : ""}
        ${detail.newsLinks?.mops ? `<a href="${safeUrl(detail.newsLinks.mops)}" target="_blank" rel="noreferrer noopener">公開資訊觀測站重大訊息</a>` : ""}
      </div>
      <p class="stock-theory-note">新聞標題與時間由外部來源彙整，請點入原始頁面核對完整內容及發布時間。</p>
    </section>
  `;

  const renderEtfDividendCard = () => {
    const info = detail.etfDividendInfo || {};
    const latest = info.latest || {};
    const totals = info.totals || {};
    const recent = Array.isArray(info.recent) ? info.recent : [];
    if (!detail.isEtf || (!latest.cashDividend && !recent.length)) return "";
    return `
      <section class="company-news-card etf-dividend-card">
        <div class="card-title-row">
          <div>
            <p class="panel-kicker">ETF Dividend</p>
            <h3>${escapeHtml(info.title || "ETF 股利資訊")}</h3>
            <p class="chart-subtitle">${escapeHtml(info.summary || "同步 ETF 實際配息與除息紀錄。")}</p>
          </div>
          <span class="chip chip-gold">${escapeHtml(latest.period || "最新配息")}</span>
        </div>
        <div class="etf-dividend-metrics">
          <div><span>最新現金股利</span><strong>${escapeHtml(latest.cashDividend || "--")} 元</strong></div>
          <div><span>除息日</span><strong>${escapeHtml(latest.exDate || "--")}</strong></div>
          <div><span>發放日</span><strong>${escapeHtml(latest.cashPayDate || "--")}</strong></div>
          <div><span>累計股利</span><strong>${escapeHtml(totals.totalDividends || "--")} 元</strong></div>
          <div><span>平均殖利率</span><strong>${escapeHtml(totals.averageYield || "--")}%</strong></div>
          <div><span>連續配息年數</span><strong>${escapeHtml(totals.continuousYears || "--")} 年</strong></div>
        </div>
        <div class="etf-dividend-list">
          ${recent.slice(0, 4).map((item) => `
            <div class="etf-dividend-row">
              <div>
                <strong>${escapeHtml(item.year || "--")} ${escapeHtml(item.period || "")}</strong>
                <span>除息 ${escapeHtml(item.exDate || "--")} · 發放 ${escapeHtml(item.cashPayDate || "--")}</span>
              </div>
              <div>
                <b>${escapeHtml(item.cashDividend || "--")} 元</b>
                <small>殖利率 ${escapeHtml(item.yieldByExDate || "--")}% · 填息 ${escapeHtml(item.recoveryDays || "--")} 天</small>
              </div>
            </div>
          `).join("")}
        </div>
        <p class="stock-theory-note">${escapeHtml(info.sourceNote || "ETF 股利資料請以發行投信公告為準。")} ${info.sourceLink ? `<a href="${safeUrl(info.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
      </section>
    `;
  };

  const etfDividendHtml = renderEtfDividendCard();

  const historyHtml = (detail.recentDays || []).map((day) => `
    <div class="history-row">
      <span>${day.date}</span>
      <span>收盤：${day.close}</span>
      <span>最高：${day.high}</span>
      <span>最低：${day.low}</span>
      <span>成量：${day.volume}</span>
    </div>
  `).join("") || '<div class="stock-detail-empty">無可用歷史資料。</div>';

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
            const dateLabel = String(item.date || "--").replaceAll("-", "/");
            return `
              <div class="valuation-bar-item" title="${item.date} ${label} ${item.value.toFixed(2)}${unit}">
                <strong>${item.value.toFixed(2)}${unit}</strong>
                <span class="valuation-bar-track"><i style="height:${height}%"></i></span>
                <small>${dateLabel}</small>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  };

  const profile = detail.companyProfile || {};
  const isProfileMissing = (value) => {
    const text = String(value ?? "").trim();
    return !text || ["--", "-", "N/A", "NA", "--%", "-%"].includes(text);
  };
  const displayProfile = Object.keys(profile).length
    ? profile
    : {
        fullName: `${detail.code || ""} ${detail.name || ""}`.trim(),
        industry: detail.marketLabel || detail.market || "--",
        website: detail.sourceLink || detail.newsLinks?.yahoo || "",
        sourceStatus: "fallback",
        sourceNote: "公司基本資料仍在同步；目前先顯示個股行情可判斷的市場資訊與來源連結。",
      };
  const profileRows = [
    ["市場 / 產業", [detail.marketLabel || detail.market, displayProfile.industry].filter((item) => !isProfileMissing(item)).join(" / ")],
    ["董事長", displayProfile.chairman],
    ["總經理", displayProfile.generalManager],
    ["實收資本額", displayProfile.capital],
    ["成立日期", displayProfile.establishedDate],
    ["掛牌日期", displayProfile.listingDate],
    ["電話", displayProfile.telephone],
    ["地址", displayProfile.address, "is-wide"],
    ["估值摘要", displayProfile.summary, "is-wide"],
  ].filter(([, value]) => !isProfileMissing(value));
  const profileSourceLabel = displayProfile.sourceStatus === "fallback" ? "資料待補" : "官方資料";
  const websiteLabel = displayProfile.sourceStatus === "fallback" ? "Yahoo 個股資料" : "公司網站";
  const companyProfileHtml = `
    <aside class="company-profile ${displayProfile.sourceStatus === "fallback" ? "is-fallback" : ""}">
      <div>
        <p class="eyebrow">Company profile</p>
        <h4>${escapeHtml(displayProfile.fullName || `${detail.code} ${detail.name}`)}</h4>
      </div>
      <span class="chip ${displayProfile.sourceStatus === "fallback" ? "chip-blue" : "chip-gold"}">${escapeHtml(profileSourceLabel)}</span>
      <dl>
        ${profileRows.map(([label, value, className]) => `
          <div class="${className || ""}"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || "--")}</dd></div>
        `).join("") || '<div class="is-wide"><dt>資料狀態</dt><dd>公司基本資料仍在同步</dd></div>'}
      </dl>
      <div class="company-profile-links">
        ${displayProfile.website ? `<a class="company-website" href="${safeUrl(displayProfile.website)}" target="_blank" rel="noreferrer noopener">${escapeHtml(websiteLabel)}</a>` : ""}
        ${displayProfile.sourceLink ? `<a class="company-website" href="${safeUrl(displayProfile.sourceLink)}" target="_blank" rel="noreferrer noopener">交易所來源</a>` : ""}
      </div>
      ${displayProfile.sourceNote ? `<p class="stock-theory-note">${escapeHtml(displayProfile.sourceNote)}</p>` : ""}
    </aside>
  `;

  const renderEtfComponentsCard = () => {
    const components = detail.etfComponents || {};
    const holdings = Array.isArray(components.holdings) ? components.holdings : [];
    if (!holdings.length) return "";
    return `
      <section class="valuation-company-card etf-components-card">
        <div class="card-title-row">
          <div>
            <h3>${escapeHtml(components.title || "ETF 成分股比例")}</h3>
            <p class="chart-subtitle">${escapeHtml(components.summary || "ETF 以成分股或追蹤標的配置觀察，不適用一般個股估值與公司資料。")}</p>
          </div>
          <span class="chip chip-blue">${holdings.length} 項配置</span>
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
                <b>${weight.toFixed(1)}%</b>
              </div>
            `;
          }).join("")}
        </div>
        <p class="stock-theory-note">${escapeHtml(components.sourceNote || "實際持股比例請以投信公告為準。")} ${components.sourceLink ? `<a href="${safeUrl(components.sourceLink)}" target="_blank" rel="noreferrer noopener">查看來源</a>` : ""}</p>
      </section>
    `;
  };

  const valuationAndCompanyHtml = detail.isEtf || detail.etfComponents
    ? renderEtfComponentsCard()
    : `
      <section class="valuation-company-card">
        <div class="card-title-row">
          <div>
            <h3>估值歷史與公司資料</h3>
            <p class="chart-subtitle">近六個月月底交易日；上市股利依官方收盤價與殖利率還原。</p>
          </div>
        </div>
        <div class="valuation-company-grid">
          <div class="valuation-chart-grid">
            ${renderValuationBars("peRatio", "本益比")}
            ${renderValuationBars("dividendYield", "殖利率", "%")}
            ${renderValuationBars("dividendPerShare", "每股股利", " 元")}
            ${renderValuationBars("pbRatio", "股價淨值比")}
          </div>
          ${companyProfileHtml}
        </div>
      </section>
    `;

  const technicalTheory = analyzeTechnicalTheories(detail);
  const technicalTrendSummary = buildTechnicalTrendSummary(detail, technicalTheory);
  technicalSummaryHtml = `
    <article class="stock-market-context technical-trend-summary is-${technicalTrendSummary.tone}">
      <div class="technical-summary-head">
        <div class="stock-theory-title">
          <span>Technical outlook</span>
          <h4>技術分析總結</h4>
        </div>
        <div class="technical-summary-score">
          <b>${technicalTrendSummary.score}</b>
          <span>${escapeHtml(technicalTrendSummary.label)}</span>
        </div>
      </div>
      <p>${escapeHtml(technicalTrendSummary.summary)}</p>
      <div class="technical-summary-timeframes">
        ${technicalTrendSummary.timeframes.map((item) => `
          <span><small>${escapeHtml(item.label)}</small><b>${escapeHtml(item.value)}</b></span>
        `).join("")}
        <span><small>分析信心</small><b>${escapeHtml(technicalTrendSummary.confidence)}</b></span>
      </div>
      ${renderTechnicalTrendForecastSummary(technicalTrendSummary)}
      <div class="technical-summary-columns">
        <section>
          <h5>趨勢共振依據</h5>
          <ul>${technicalTrendSummary.confirmations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </section>
        <section>
          <h5>風險與反向訊號</h5>
          <ul>${technicalTrendSummary.risks.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </section>
      </div>
      <div class="technical-summary-action">
        <strong>目前風向與操作節奏</strong>
        <span>${escapeHtml(technicalTrendSummary.action)}</span>
      </div>
    </article>
  `;
  const theoryTone = technicalTheory.score >= 3
    ? "positive"
    : technicalTheory.score <= -3
      ? "negative"
      : "neutral";
  const theoryLabel = theoryTone === "positive"
    ? "偏多結構"
    : theoryTone === "negative"
      ? "偏空結構"
      : "中性整理";
  const backtestLearning = technicalTheory.backtestLearning || {};
  const backtestAdjustment = Number(backtestLearning.scoreAdjustment || 0);
  const backtestAdjustmentText = backtestAdjustment > 0
    ? `+${backtestAdjustment} 偏多校準`
    : backtestAdjustment < 0
      ? `${backtestAdjustment} 偏空校準`
      : "0 中性校準";
  const backtestBest = backtestLearning.signals?.[0];
  const backtestPerformance = backtestLearning.performance || {};
  const backtestCostModel = backtestLearning.costModel || {};
  const backtestRiskModel = backtestLearning.riskModel || {};
  const backtestValidation = backtestLearning.validation || {};
  const backtestOriginalValidation = backtestLearning.originalValidation || {};
  const backtestModelRebuild = backtestLearning.modelRebuild || {};
  const backtestForecast = backtestLearning.forecast || {};
  const institutionalFramework = backtestLearning.institutionalFramework || {};
  const institutionalLayers = Array.isArray(institutionalFramework.layers)
    ? institutionalFramework.layers
    : [];
  const institutionalRecent20 = institutionalFramework.recent20 || {};
  const backtestForecastScenarios = Array.isArray(backtestForecast.scenarios)
    ? backtestForecast.scenarios
    : [];
  const backtestPriceTargets = Array.isArray(backtestForecast.priceTargets)
    ? backtestForecast.priceTargets
    : [];
  const backtestSupportText = Number.isFinite(backtestForecast.support)
    ? backtestForecast.support.toFixed(2)
    : "--";
  const backtestResistanceText = Number.isFinite(backtestForecast.resistance)
    ? backtestForecast.resistance.toFixed(2)
    : "--";
  const backtestAtrText = Number.isFinite(backtestForecast.atrPct)
    ? `${backtestForecast.atrPct.toFixed(2)}%`
    : "--";
  const formatBacktestRatio = (value, digits = 2) => (
    Number.isFinite(value) ? value.toFixed(digits) : "--"
  );
  const formatBacktestPercent = (value, digits = 0) => (
    Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : "--"
  );
  const validationTone = backtestValidation.status === "healthy"
    ? "bullish"
    : backtestValidation.status === "watch"
      ? "neutral"
      : backtestValidation.status === "recalibrate" || backtestValidation.status === "rebuild"
        ? "bearish"
        : "neutral";
  const backtestSignalNames = (backtestLearning.signals || [])
    .slice(0, 5)
    .map((item) => item.name)
    .join("、");
  const backtestIntegratedSummary = backtestBest
    ? `整合回測結果以 ${backtestSignalNames || backtestBest.name} 作為主要觀察組合；目前 ${backtestBest.name} 的樣本勝率 ${(backtestBest.winRate * 100).toFixed(0)}%，淨均報酬 ${backtestBest.averageReturn >= 0 ? "+" : ""}${backtestBest.averageReturn.toFixed(2)}%，並已扣除交易成本與納入停損停利檢查。`
    : "目前歷史樣本或訊號數不足，暫不輸出最佳訊號，模型維持中性校準。";
  const backtestBaselineSummary = "分析已整合回溯測試因素基準中的資料品質、估值、技術、籌碼、交易成本、風控、資金管理與績效評估，不再以單一訊號獨立判定模型準確性。";
  const backtestDecisionTips = [
    backtestModelRebuild.status === "rebuilt"
      ? `模型已重建：舊模型 ${backtestModelRebuild.oldModel || "--"} 改為 ${backtestModelRebuild.newModel || "--"}，後續權重以新模型為主。`
      : backtestModelRebuild.status === "failed"
        ? "已嘗試重新建模，但替代模型未通過樣本外校準，暫維持中性權重。"
        : "目前未觸發重新建模條件。",
    backtestValidation.status === "healthy"
      ? "模型通過樣本外校準，可保留目前 AI 權重，但仍需等待價量與趨勢同向確認。"
      : backtestValidation.status === "rebuild"
        ? "模型偵測失真，暫停提高權重，先以人工風控與重新建模為主。"
        : "模型仍需觀察，建議降低單筆部位並等待下一次資料校準。",
    Number.isFinite(backtestForecast.support) && Number.isFinite(backtestForecast.resistance)
      ? `區間參考：接近 ${backtestSupportText} 觀察承接，接近 ${backtestResistanceText} 留意壓力與獲利了結。`
      : "支撐壓力資料不足時，不以單一價位作為進出場依據。",
    backtestPriceTargets.length
      ? `預估股價採區間而非單點：${backtestPriceTargets[0].label}參考中位 ${backtestPriceTargets[0].median.toFixed(2)}，區間 ${backtestPriceTargets[0].lower.toFixed(2)} ~ ${backtestPriceTargets[0].upper.toFixed(2)}。`
      : "預估股價資料不足，暫不輸出價格區間。",
    Number.isFinite(backtestForecast.atrPct) && backtestForecast.atrPct >= 5
      ? `波動偏高，ATR 約 ${backtestAtrText}，停損與部位需同步放寬或縮小部位。`
      : `波動參考 ${backtestAtrText}，可用分批進出降低一次判斷錯誤風險。`,
    backtestAdjustment > 0
      ? "權重偏多時仍需確認量能延續，避免只因回測勝率高而追價。"
      : backtestAdjustment < 0
        ? "權重偏空時優先控管回撤，等待重新站回關鍵均線後再提高信心。"
        : "權重中性時以區間策略與風險報酬比優先，不急著放大部位。",
  ];
  const technicalTheoryHtml = `
    <section class="stock-theory-section">
      <div class="card-title-row">
        <div>
          <h3>進階技術分析理論</h3>
          <p class="chart-subtitle">整合型態、價量、市場廣度、心理線與籌碼指標，透過 ADR、ADL、OBOS、PSY 及多因子一致性動態調整信心。</p>
        </div>
        <span class="stock-theory-score is-${theoryTone}">${theoryLabel} · ${technicalTheory.score > 0 ? "+" : ""}${technicalTheory.score}</span>
      </div>
      <div class="stock-theory-adaptive">
        <strong>多理論共振：${technicalTheory.adaptiveConfidence || "低"}信心</strong>
        <span>${technicalTheory.adaptiveSummary || "目前多空理論尚未形成一致方向"}</span>
      </div>
      <div class="stock-theory-grid">
        <article class="stock-theory-card">
          <div class="stock-theory-title">
            <span>Pattern theory</span>
            <h4>型態技術分析</h4>
          </div>
          <div class="stock-theory-signal-list">
            ${(technicalTheory.theorySignals || []).map((item) => `
              <div class="stock-theory-signal is-${item.direction}">
                <strong>${item.name}</strong>
                <span>${item.text}</span>
              </div>
            `).join("") || `<ul>${(technicalTheory.patterns || []).map((item) => `<li>${item}</li>`).join("")}</ul>`}
          </div>
          ${technicalSummaryHtml}
        </article>
        <article class="stock-theory-card">
          <div class="stock-theory-title">
            <span>Indicator theory</span>
            <h4>指標類技術分析</h4>
          </div>
          <div class="indicator-resonance ${technicalTheory.priceVolumeConflict ? "is-conflict" : technicalTheory.priceVolumeAligned ? "is-aligned" : ""}">
            ${technicalTheory.indicatorSummary || "價量方向尚未形成一致確認"}
          </div>
          <div class="indicator-theory-groups">
            <section>
              <h5>價的技術指標</h5>
              <div class="indicator-signal-list">
                ${(technicalTheory.priceIndicators || []).map((item) => item.movingAverage ? `
                  <div class="indicator-signal moving-average-analysis is-${item.direction}">
                    <div class="moving-average-head">
                      <div>
                        <strong>${escapeHtml(item.name)}</strong>
                        <span>${escapeHtml(item.movingAverage.headline)}</span>
                      </div>
                      <b>${item.movingAverage.score > 0 ? "+" : ""}${item.movingAverage.score}</b>
                    </div>
                    <div class="moving-average-periods">
                      ${item.movingAverage.periods.map((period) => `
                        <div>
                          <strong>${escapeHtml(period.label)}</strong>
                          <b>${period.value.toFixed(2)}</b>
                          <span>${escapeHtml(period.role)}</span>
                          <small>${escapeHtml(period.slope)} · ${escapeHtml(period.position)}</small>
                        </div>
                      `).join("")}
                    </div>
                    <div class="moving-average-sections">
                      <section>
                        <h6>趨勢與交叉</h6>
                        <ul>
                          ${item.movingAverage.crosses.map((text) => `<li>${escapeHtml(text)}</li>`).join("")}
                          ${item.movingAverage.confirmations.map((text) => `<li>${escapeHtml(text)}</li>`).join("")}
                        </ul>
                      </section>
                      <section>
                        <h6>實戰判讀</h6>
                        <p>${escapeHtml(item.movingAverage.practical)}</p>
                        <p>${escapeHtml(item.movingAverage.suitability)}</p>
                      </section>
                    </div>
                    <div class="moving-average-risk">
                      <strong>風險提醒</strong>
                      <span>${item.movingAverage.risks.map((text) => escapeHtml(text)).join("；")}</span>
                    </div>
                  </div>
                ` : `
                  <div class="indicator-signal is-${item.direction}">
                    <strong>${item.name}</strong>
                    <span>${item.value}</span>
                    <small>${item.text}</small>
                  </div>
                `).join("") || "<p>價格指標資料不足</p>"}
              </div>
            </section>
            <section>
              <h5>量的技術指標</h5>
              <div class="indicator-signal-list">
                ${(technicalTheory.volumeIndicators || []).map((item) => `
                  <div class="indicator-signal is-${item.direction}">
                    <strong>${item.name}</strong>
                    <span>${item.value}</span>
                    <small>${item.text}</small>
                  </div>
                `).join("") || "<p>量能指標資料不足</p>"}
              </div>
            </section>
            <section>
              <h5>市場廣度、心理與籌碼指標</h5>
              <div class="indicator-resonance ${technicalTheory.breadthConflict ? "is-conflict" : technicalTheory.breadthAligned ? "is-aligned" : ""}">
                ${technicalTheory.breadthSummary || "市場廣度與籌碼方向尚未形成一致確認"}
              </div>
              <div class="indicator-signal-list">
                ${(technicalTheory.breadthIndicators || []).map((item) => `
                  <div class="indicator-signal is-${item.direction}">
                    <strong>${item.name}</strong>
                    <span>${item.value}</span>
                    <small>${item.text}</small>
                  </div>
                `).join("") || "<p>市場廣度或籌碼資料不足</p>"}
              </div>
            </section>
          </div>
        </article>
      </div>
      <div class="stock-backtest-learning">
        <div class="backtest-learning-head">
          <span>Backtest learning</span>
          <strong>回溯學習校準</strong>
          <small>${backtestLearning.summary || "歷史樣本不足，暫不調整 AI 權重"}</small>
        </div>
        <div class="institutional-backtest-card is-${escapeHtml(institutionalFramework.judgement?.tone || "neutral")}">
          <div class="institutional-backtest-head">
            <div>
              <span>Institutional multi-factor</span>
              <strong>機構多因子回溯統整</strong>
              <small>依市場環境、資金面、趨勢面與進出場訊號逐層驗證，不以單一技術指標直接下結論。</small>
            </div>
            <div class="institutional-total-score">
              <b>${Number.isFinite(institutionalFramework.totalScore) ? institutionalFramework.totalScore : "--"}</b>
              <span>/ 100</span>
              <small>${escapeHtml(institutionalFramework.judgement?.label || "資料不足")}</small>
            </div>
          </div>
          <div class="institutional-layer-grid">
            ${institutionalLayers.map((layer) => `
              <article>
                <div>
                  <strong>${escapeHtml(layer.label)}</strong>
                  <span>權重 ${layer.weight}%</span>
                </div>
                <b>${Math.round(layer.score)}</b>
                <div class="institutional-score-track">
                  <i style="width:${Math.round(layer.score)}%"></i>
                </div>
                <small>資料涵蓋 ${Math.round(layer.coverage * 100)}% · ${(layer.available || []).map((item) => escapeHtml(item.name)).join("、") || "等待資料"}</small>
              </article>
            `).join("")}
          </div>
          <div class="institutional-monitor-grid">
            <div>
              <span>市場狀態</span>
              <strong>${escapeHtml(institutionalFramework.marketState || "--")}</strong>
            </div>
            <div>
              <span>近 20 筆勝率</span>
              <strong>${formatBacktestPercent(institutionalRecent20.winRate)} · ${escapeHtml(institutionalRecent20.winState || "樣本不足")}</strong>
            </div>
            <div>
              <span>近 20 筆 PF</span>
              <strong>${formatBacktestRatio(institutionalRecent20.profitFactor)} · ${escapeHtml(institutionalRecent20.pfState || "樣本不足")}</strong>
            </div>
            <div>
              <span>近 20 筆 MDD</span>
              <strong>${formatBacktestRatio(institutionalRecent20.maxDrawdown)}% · ${escapeHtml(institutionalRecent20.mddState || "樣本不足")}</strong>
            </div>
          </div>
          <div class="institutional-backtest-body">
            <section>
              <h5>標準分析輸出</h5>
              <ol>
                ${(institutionalFramework.outputSteps || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
              </ol>
            </section>
          </div>
        </div>
        <div class="backtest-forecast-card">
          <div class="backtest-forecast-head">
            <div>
              <span>Scenario forecast</span>
              <strong>未來走勢情境推估</strong>
            </div>
            <small>模型信心：${escapeHtml(backtestForecast.confidence || "低")} · ${escapeHtml(backtestForecast.trendLabel || "區間震盪")}</small>
          </div>
          <p>${escapeHtml(backtestForecast.summary || "回測資料不足，暫以中性震盪情境觀察。")}</p>
          <div class="backtest-forecast-grid">
            ${backtestForecastScenarios.map((item) => `
              <div class="backtest-forecast-item">
                <strong>${escapeHtml(item.label || `${item.days || "--"} 日`)}</strong>
                <span class="is-bullish">偏多 ${Number.isFinite(item.bullish) ? item.bullish : "--"}%</span>
                <span>震盪 ${Number.isFinite(item.neutral) ? item.neutral : "--"}%</span>
                <span class="is-bearish">偏空 ${Number.isFinite(item.bearish) ? item.bearish : "--"}%</span>
              </div>
            `).join("") || '<p class="stock-detail-empty">樣本不足，暫不輸出情境比例。</p>'}
          </div>
          <div class="backtest-forecast-levels">
            <span>支撐區 <b>${backtestSupportText}</b></span>
            <span>壓力區 <b>${backtestResistanceText}</b></span>
            <span>波動參考 <b>${backtestAtrText}</b></span>
          </div>
          ${backtestPriceTargets.length ? `
            <div class="backtest-price-targets">
              <div class="backtest-price-targets-head">
                <strong>預估股價區間</strong>
                <span>以區間與中位價呈現，避免單點喊價</span>
              </div>
              <div class="backtest-price-target-grid">
                ${backtestPriceTargets.map((item) => `
                  <div class="backtest-price-target">
                    <span>${escapeHtml(item.label)}</span>
                    <strong>${item.lower.toFixed(2)} ~ ${item.upper.toFixed(2)}</strong>
                    <small>中位 ${item.median.toFixed(2)}｜預估 ${item.expectedReturnPct >= 0 ? "+" : ""}${item.expectedReturnPct.toFixed(2)}%</small>
                    <em>${escapeHtml(item.basis)}</em>
                  </div>
                `).join("")}
              </div>
            </div>
          ` : ""}
          <p class="backtest-forecast-caveat">${escapeHtml(backtestForecast.caveat || "情境推估只作風險管理參考，不保證未來價格。")}</p>
        </div>
        <div class="backtest-validation-card is-${validationTone}">
          <div class="backtest-validation-head">
            <strong>模型準確性驗證：${escapeHtml(backtestValidation.label || "樣本不足")}</strong>
          </div>
          <p>${escapeHtml(backtestValidation.recommendation || "樣本不足，暫不判定模型失真。")}</p>
          <p>${escapeHtml(backtestIntegratedSummary)}</p>
          <p>${escapeHtml(backtestBaselineSummary)}</p>
          <div class="backtest-validation-grid">
            <span>樣本內勝率 <b>${formatBacktestPercent(backtestValidation.inSample?.winRate)}</b></span>
            <span>樣本外勝率 <b>${formatBacktestPercent(backtestValidation.outSample?.winRate)}</b></span>
            <span>樣本外 MDD <b>${formatBacktestRatio(backtestValidation.outSample?.maxDrawdown)}%</b></span>
            <span>樣本外 PF <b>${formatBacktestRatio(backtestValidation.outSample?.profitFactor)}</b></span>
          </div>
          <ul>
            ${(backtestValidation.reasons || ["未取得模型失真檢查資料"]).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </div>
        ${backtestModelRebuild.status && backtestModelRebuild.status !== "not_required" ? `
          <div class="backtest-rebuild-card is-${backtestModelRebuild.status === "rebuilt" ? "bullish" : "bearish"}">
            <div class="backtest-rebuild-head">
              <div>
                <span>Model rebuild</span>
                <strong>模型重新建置：${escapeHtml(backtestModelRebuild.label || "--")}</strong>
              </div>
              <small>原模型狀態：${escapeHtml(backtestOriginalValidation.label || "未提供")}</small>
            </div>
            <p>${escapeHtml(backtestModelRebuild.summary || "尚無重建結果。")}</p>
            <div class="backtest-rebuild-switch">
              <span>舊模型 <b>${escapeHtml(backtestModelRebuild.oldModel || "--")}</b></span>
              <span>新模型 <b>${escapeHtml(backtestModelRebuild.newModel || "尚未通過")}</b></span>
            </div>
            <div class="backtest-rebuild-candidates">
              ${(backtestModelRebuild.candidates || []).map((item) => `
                <div>
                  <strong>${escapeHtml(item.name || "--")}</strong>
                  <span>${escapeHtml(item.status || "--")}｜樣本外勝率 ${formatBacktestPercent(item.outWinRate)}｜PF ${formatBacktestRatio(item.outProfitFactor)}｜MDD ${formatBacktestRatio(item.outMaxDrawdown)}%</span>
                </div>
              `).join("") || '<span>替代模型樣本不足。</span>'}
            </div>
          </div>
        ` : ""}
        <div class="backtest-metrics">
          <div><span>回測週期</span><strong>${backtestLearning.horizon || 240} 日後報酬</strong></div>
          <div><span>成功門檻</span><strong>±${backtestLearning.successThreshold || 5}%</strong></div>
          <div><span>有效樣本</span><strong>${backtestLearning.evidenceCount || 0}</strong></div>
          <div><span>權重調整</span><strong class="${backtestAdjustment > 0 ? "up" : backtestAdjustment < 0 ? "down" : ""}">${backtestAdjustmentText}</strong></div>
          <div><span>交易成本</span><strong>${formatBacktestRatio(backtestCostModel.roundTripPct)}%</strong></div>
          <div><span>停損 / 停利</span><strong>${backtestRiskModel.stopLossPct || -8}% / +${backtestRiskModel.takeProfitPct || 20}%</strong></div>
          <div><span>最大回撤</span><strong class="down">${formatBacktestRatio(backtestPerformance.maxDrawdown)}%</strong></div>
          <div><span>Profit Factor</span><strong>${formatBacktestRatio(backtestBest?.profitFactor ?? backtestPerformance.profitFactor)}</strong></div>
          <div><span>模型狀態</span><strong class="${backtestValidation.status === "rebuild" ? "down" : backtestValidation.status === "healthy" ? "up" : ""}">${backtestValidation.label || "樣本不足"}</strong></div>
          <div><span>失真次數</span><strong>${backtestValidation.driftCount ?? 0}</strong></div>
        </div>
        <div class="backtest-action-card">
          <div>
            <span>Action calibration</span>
            <strong>操作校準提示</strong>
          </div>
          <ul>
            ${backtestDecisionTips.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
          </ul>
        </div>
        <p class="backtest-filter-note">模型已排除短線雜訊較高的單因子訊號作為最佳歷史訊號候選，改以趨勢、動能、量能、波動、成本、風控與績效指標交叉確認，並避免未來函數、樣本不足與過度擬合。</p>
        <p class="stock-theory-note">回溯學習使用歷史資料做訊號校準，只調整分析權重，不代表未來必然重複；若樣本數不足，系統會維持中性權重。</p>
      </div>
      <p class="stock-theory-note">「動態強化」是依理論一致度、量價與指標確認調整權重，不是模型自行學習或保證預測；技術分析仍應搭配基本面、籌碼與停損紀律。</p>
    </section>
  `;

  const watchlistAdded = isStockInWatchlist(detail);
  const fullDetailNoticeHtml = detail.detailMode === "quick"
    ? `<div class="stock-detail-empty">即時行情與近期技術資料已載入；基本面、籌碼面、消息面、估值歷史與公司資料正在同步線上完整資料。</div>`
    : "";
  container.innerHTML = `
    <div class="card-title-row">
      <h3>${detail.code} ${detail.name}</h3>
      <div class="stock-detail-actions">
        <button class="watchlist-toggle ${watchlistAdded ? "is-added" : ""}" type="button" data-stock-watchlist-toggle>
          ${watchlistAdded ? "移除自選" : "加入自選"}
        </button>
        <span class="chip ${detail.tone === "up" ? "chip-green" : detail.tone === "down" ? "chip-red" : "chip-blue"}">${detail.snapshotDate || "--"}</span>
      </div>
    </div>
    ${fullDetailNoticeHtml}
    <div class="detail-metrics">
      <div><span>收盤價</span><strong>${detail.close}</strong></div>
      <div><span>漲跌幅</span><strong class="${toneClass(detail.tone)}">${detail.pct}</strong></div>
      <div><span>MA5 / MA20 / MA60</span><strong>${detail.ma5} / ${detail.ma20} / ${detail.ma60}</strong></div>
      <div><span>5 日均量</span><strong>${detail.avgVolume5}</strong></div>
      <div><span>成交金額</span><strong>${detail.turnover}</strong></div>
      <div><span>月高</span><strong>${detail.monthHigh}</strong></div>
      <div><span>月低</span><strong>${detail.monthLow}</strong></div>
    </div>
    <p class="card-copy">${detail.trend}</p>
    <section class="technical-chart-card">
      <div class="card-title-row">
        <div>
          <h3>技術走勢圖</h3>
          <p class="chart-subtitle">K 線與可選均線。${historySummary} ${chartIntervals.intradayUnavailableReason || "盤中歷史資料不可用。"}</p>
        </div>
        <div class="range-switcher" aria-label="技術圖時間切換">
          ${intervalButtons}
        </div>
      </div>
      <div class="ma-switcher" aria-label="移動平均線選項">
        <span>均線</span>
        ${maOptions.map((period) => `
          <button class="ma-option ${period === 5 ? "is-active" : ""}" type="button" data-ma-period="${period}">
            <i class="ma-color ma-${period}"></i>MA${period}
          </button>
        `).join("")}
      </div>
      <div class="indicator-switcher" aria-label="技術指標切換">
        <span>主圖疊加（可複選）</span>
        ${chartIndicatorOptions.map(([key, label]) => `
          <button class="indicator-option" type="button" data-chart-indicator="${key}">
            ${label}
          </button>
        `).join("")}
      </div>
      <div class="indicator-switcher panel-indicator-switcher" aria-label="下方技術指標切換">
        <span>下方指標（可複選）</span>
        ${panelIndicatorOptions.map(([key, label]) => `
          <button class="indicator-option ${key === "kd" ? "is-active" : ""}" type="button" data-panel-indicator="${key}">
            ${label}
          </button>
        `).join("")}
      </div>
      <div class="stock-chart-zoom" aria-label="個股走勢圖縮放控制">
        <button type="button" data-stock-zoom="in">＋ 放大</button>
        <button type="button" data-stock-zoom="out" disabled>－ 縮小</button>
        <button type="button" data-stock-zoom="reset" disabled>重設</button>
        <button type="button" data-stock-pan="older" disabled>← 往前</button>
        <button type="button" data-stock-pan="newer" disabled>往後 →</button>
        <span data-stock-zoom-status>顯示 ${getChartHistory(detail, "day").length} / ${getChartHistory(detail, "day").length} 根</span>
      </div>
      ${detail.historyWarning ? `<p class="chart-data-notice">${escapeHtml(detail.historyWarning)}</p>` : ""}
      <div id="technical-chart-view">${renderTechnicalChart(detail, "day", [], [5], defaultVisibleChartCount("day"), 0, ["kd"])}</div>
    </section>
    <section class="recent-trades-card">
      <div class="card-title-row">
        <h3>近五日交易</h3>
      </div>
      <div class="detail-history">${historyHtml}</div>
    </section>
    ${technicalTheoryHtml}
    <div class="analysis-grid">${analysisHtml}</div>
    ${companyNewsHtml}
    ${etfDividendHtml}
    ${valuationAndCompanyHtml}
  `;

  container.querySelector("[data-stock-watchlist-toggle]")?.addEventListener("click", (event) => {
    const added = toggleWatchlistStock(detail);
    event.currentTarget.textContent = added ? "移除自選" : "加入自選";
    event.currentTarget.classList.toggle("is-added", added);
    const status = document.getElementById("search-status");
    if (status) {
      status.textContent = added
        ? `已將 ${detail.code} ${detail.name} 加入自選股。`
        : `已將 ${detail.code} ${detail.name} 從自選股移除。`;
    }
  });

  container.querySelectorAll("[data-institution-period]").forEach((button) => {
    button.addEventListener("click", () => {
      const period = Number(button.dataset.institutionPeriod);
      if (!Number.isFinite(period)) return;
      stockInstitutionPeriodState.set(getStockDetailCacheKey(detail.code, detail.market || activeStockMarket), period);
      renderStockDetail(detail);
    });
  });

  container.querySelectorAll("[data-institution-range]").forEach((button) => {
    button.addEventListener("click", async () => {
      const range = String(button.dataset.institutionRange || "");
      if (!range) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const code = currentDetail.code || detail.code;
      const marketValue = currentDetail.market || detail.market || activeStockMarket || "";
      const stateKey = getStockDetailCacheKey(code, marketValue);
      const rangeCacheKey = `${stateKey}:${range}`;
      stockInstitutionRangeState.set(stateKey, range);
      const renderWithoutJump = (nextDetail) => {
        const scrollY = window.scrollY;
        renderStockDetail(nextDetail);
        requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
      };
      const mergeInstitutionPayload = (baseDetail, payload) => {
        const loadedHistory = payload?.institutionalTradeHistory || {};
        if (!Array.isArray(loadedHistory.rows) || !loadedHistory.rows.length) return baseDetail;
        return {
          ...baseDetail,
          institutionalTradeHistory: loadedHistory,
          institutionalTrades: payload.institutionalTrades || baseDetail.institutionalTrades || buildLatestInstitutionalTradeFromHistory(loadedHistory),
        };
      };
      const shouldFetchRealRange = ["6m", "1y"].includes(range);
      if (shouldFetchRealRange) {
        const cached = stockInstitutionRangeHistoryCache.get(rangeCacheKey);
        if (cached) {
          renderWithoutJump(mergeInstitutionPayload(currentDetail, cached));
          return;
        }
        const status = document.getElementById("search-status");
        if (status) status.textContent = `${code} 法人 ${range} 真實資料載入中...`;
        try {
          const marketQuery = marketValue ? `&market=${encodeURIComponent(marketValue)}` : "";
          const [rangeResponse, fullResponse] = await Promise.all([
            fetchWithTimeout(
              `/api/twse/stock/${encodeURIComponent(code)}/institutional-history?range=${encodeURIComponent(range)}${marketQuery}`,
              { cache: "no-store" },
              120000,
            ),
            currentDetail.allHistoryLoaded ? Promise.resolve(null) : fetchWithTimeout(
              `/api/twse/stock/${encodeURIComponent(code)}?history=all&refresh=1&deferSlow=1${marketQuery}`,
              { cache: "no-store" },
              30000,
            ).catch(() => null),
          ]);
          if (!rangeResponse.ok) throw new Error(`HTTP ${rangeResponse.status}`);
          const rangePayload = await rangeResponse.json();
          stockInstitutionRangeHistoryCache.set(rangeCacheKey, rangePayload);
          let mergedDetail = currentDetail;
          if (fullResponse && fullResponse.ok) {
            const fullDetail = await fullResponse.json();
            mergedDetail = { ...currentDetail, ...fullDetail };
            if (currentDetail.shareholderDistribution && Object.keys(currentDetail.shareholderDistribution).length && (!fullDetail.shareholderDistribution || !Object.keys(fullDetail.shareholderDistribution).length)) {
              mergedDetail.shareholderDistribution = currentDetail.shareholderDistribution;
            }
          }
          renderWithoutJump(mergeInstitutionPayload(mergedDetail, rangePayload));
          return;
        } catch (error) {
          console.error("Failed to load real institution range history:", error);
          if (status) status.textContent = `${code} 法人 ${range} 真實資料暫時無法連線，先顯示已取得資料。`;
        }
      }
      renderWithoutJump(currentDetail);
    });
  });

  container.querySelectorAll("[data-margin-range]").forEach((button) => {
    button.addEventListener("click", () => {
      const range = String(button.dataset.marginRange || "");
      if (!range) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const stateKey = getStockDetailCacheKey(currentDetail.code || detail.code, currentDetail.market || detail.market || activeStockMarket);
      const scrollY = window.scrollY;
      stockMarginRangeState.set(stateKey, range);
      renderStockDetail(currentDetail);
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
    });
  });

  container.querySelectorAll("[data-margin-summary-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      const mode = String(button.dataset.marginSummaryMode || "");
      if (!mode) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const stateKey = getStockDetailCacheKey(currentDetail.code || detail.code, currentDetail.market || detail.market || activeStockMarket);
      const scrollY = window.scrollY;
      stockMarginSummaryModeState.set(stateKey, mode);
      renderStockDetail(currentDetail);
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
    });
  });

  container.querySelectorAll("[data-margin-table-type]").forEach((button) => {
    button.addEventListener("click", () => {
      const type = String(button.dataset.marginTableType || "");
      if (!type) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const stateKey = getStockDetailCacheKey(currentDetail.code || detail.code, currentDetail.market || detail.market || activeStockMarket);
      const scrollY = window.scrollY;
      stockMarginTableTypeState.set(stateKey, type);
      renderStockDetail(currentDetail);
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
    });
  });

  container.querySelectorAll("[data-margin-period]").forEach((button) => {
    button.addEventListener("click", () => {
      const period = String(button.dataset.marginPeriod || "");
      if (!period) return;
      const currentDetail = activeRenderedStockDetail || detail;
      const stateKey = getStockDetailCacheKey(currentDetail.code || detail.code, currentDetail.market || detail.market || activeStockMarket);
      const scrollY = window.scrollY;
      stockMarginPeriodState.set(stateKey, period);
      renderStockDetail(currentDetail);
      requestAnimationFrame(() => window.scrollTo({ top: scrollY, left: window.scrollX, behavior: "auto" }));
    });
  });

  container.querySelectorAll("[data-institution-series]").forEach((button) => {
    button.addEventListener("click", () => {
      const series = String(button.dataset.institutionSeries || "");
      if (!series) return;
      const stateKey = getStockDetailCacheKey(detail.code, detail.market || activeStockMarket);
      const current = new Set(String(stockInstitutionSeriesState.get(stateKey) || "price,foreign,trust,dealer").split(",").filter(Boolean));
      if (current.has(series)) current.delete(series);
      else current.add(series);
      const flowCount = ["foreign", "trust", "dealer"].filter((key) => current.has(key)).length;
      if (!flowCount) current.add(series === "price" ? "foreign" : series);
      stockInstitutionSeriesState.set(stateKey, ["price", "foreign", "trust", "dealer"].filter((key) => current.has(key)).join(","));
      renderStockDetail(detail);
    });
  });

  container.querySelectorAll("[data-chip-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      const tab = String(button.dataset.chipTab || "");
      if (!tab) return;
      stockChipTabState.set(getStockDetailCacheKey(detail.code, detail.market || activeStockMarket), tab);
      renderStockDetail(detail);
    });
  });

  initInstitutionChartCursor(container);
  initMajorHolderChartCursor(container);
  initMarginBalanceChartCursor(container);

  loadInstitutionalTradeHistoryIfNeeded(detail);

  let activeInterval = "day";
  const activeOverlayIndicators = new Set();
  const activePanelIndicators = new Set(["kd"]);
  const activeMaPeriods = new Set([5]);
  const zoomCounts = new Map();
  const panOffsets = new Map();

  const getZoomState = () => {
    const total = getChartHistory(chartDetail, activeInterval).length;
    const minimum = activeInterval === "day" ? 20 : activeInterval === "week" ? 8 : 4;
    const overlayStateKey = [...activeOverlayIndicators].sort().join(",");
    const panelStateKey = [...activePanelIndicators].sort().join(",");
    const chartStateKey = `${activeInterval}:${overlayStateKey}:${panelStateKey}`;
    const saved = zoomCounts.get(chartStateKey);
    const visible = Number.isFinite(saved) ? Math.max(minimum, Math.min(saved, total)) : defaultVisibleChartCount(activeInterval);
    const panOffset = Math.max(0, Math.min(panOffsets.get(chartStateKey) || 0, total - visible));
    return { total, minimum: Math.min(minimum, total), visible, panOffset };
  };

  const updateZoomControls = () => {
    const { total, minimum, visible, panOffset } = getZoomState();
    const zoomIn = container.querySelector('[data-stock-zoom="in"]');
    const zoomOut = container.querySelector('[data-stock-zoom="out"]');
    const reset = container.querySelector('[data-stock-zoom="reset"]');
    const older = container.querySelector('[data-stock-pan="older"]');
    const newer = container.querySelector('[data-stock-pan="newer"]');
    const status = container.querySelector("[data-stock-zoom-status]");
    if (zoomIn) zoomIn.disabled = visible <= minimum;
    if (zoomOut) zoomOut.disabled = visible >= total;
    if (reset) reset.disabled = visible >= total;
    if (older) older.disabled = panOffset >= total - visible;
    if (newer) newer.disabled = panOffset <= 0;
    if (status) status.textContent = `顯示 ${visible} / ${total} 根`;
  };

  const bindTechnicalChartWheel = (chartView) => {
    const frame = chartView?.querySelector(".sector-chart-frame");
    if (!frame) return;
    frame.addEventListener("wheel", (event) => {
      event.preventDefault();
      updateStockZoom(event.deltaY < 0 ? "in" : "out");
    }, { passive: false });
    bindHorizontalChartPan(frame, updateStockPan);
  };

  async function updateTechnicalChart() {
    const chartView = document.getElementById("technical-chart-view");
    if (!chartView) return;
    const longestMaPeriod = Math.max(...activeMaPeriods, 0);
    const availableSeriesCount = getChartHistory(chartDetail, activeInterval).length;
    const structureNeedsHistory = activeOverlayIndicators.size > 0;
    const panelNeedsHistory = [...activePanelIndicators].some((item) => ["macd", "dmi", "obv"].includes(item));
    const needsHistoryLoad = (
      (["week", "month"].includes(activeInterval) && chartDetail.isFallbackHistory)
      || (longestMaPeriod > availableSeriesCount && !chartDetail.allHistoryLoaded)
      || (structureNeedsHistory && availableSeriesCount < 80 && !chartDetail.allHistoryLoaded)
      || (panelNeedsHistory && availableSeriesCount < 40 && !chartDetail.allHistoryLoaded)
    );
    if (needsHistoryLoad) {
      const previousHtml = chartView.innerHTML;
      chartView.innerHTML = '<div class="stock-detail-empty">載入完整歷史資料中...</div>';
      try {
        const marketQuery = detail.market ? `&market=${encodeURIComponent(detail.market)}` : "";
        const response = await fetchWithTimeout(
          `/api/twse/stock/${encodeURIComponent(detail.code)}?history=all&refresh=1${marketQuery}`,
          { cache: "no-store" },
          15000,
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        chartDetail = await response.json();
        if (!Array.isArray(chartDetail.historyDays) || chartDetail.historyDays.length < 2 || chartDetail.isFallbackHistory) {
          throw new Error("Historical data unavailable");
        }
      } catch (error) {
        chartView.innerHTML = previousHtml;
        const status = document.getElementById("search-status");
        if (status) status.textContent = `${detail.code} 完整歷史資料暫時無法連線。`;
        console.error("Failed to load full stock history:", error);
        return;
      }
    }
    const { visible, panOffset } = getZoomState();
    chartView.innerHTML = renderTechnicalChart(chartDetail, activeInterval, [...activeOverlayIndicators], [...activeMaPeriods], visible, panOffset, [...activePanelIndicators]);
    bindChartHover(chartView);
    bindTechnicalChartWheel(chartView);
    updateZoomControls();
  }

  bindChartHover(document.getElementById("technical-chart-view"));
  bindTechnicalChartWheel(document.getElementById("technical-chart-view"));
  updateZoomControls();

  async function updateStockZoom(direction) {
    const { total, minimum, visible } = getZoomState();
    let next = visible;
    if (direction === "in") next = Math.max(minimum, Math.floor(visible * 0.65));
    if (direction === "out") next = Math.min(total, Math.ceil(visible / 0.65));
    if (direction === "reset") next = total;
    if (next === visible) return;
    const chartStateKey = `${activeInterval}:${[...activeOverlayIndicators].sort().join(",")}:${[...activePanelIndicators].sort().join(",")}`;
    zoomCounts.set(chartStateKey, next);
    panOffsets.set(chartStateKey, 0);
    await updateTechnicalChart();
  }

  async function updateStockPan(direction) {
    const { total, visible, panOffset } = getZoomState();
    const maxOffset = Math.max(total - visible, 0);
    const step = Math.max(1, Math.round(visible * 0.35));
    const next = direction === "older"
      ? Math.min(maxOffset, panOffset + step)
      : Math.max(0, panOffset - step);
    if (next === panOffset) return;
    panOffsets.set(`${activeInterval}:${[...activeOverlayIndicators].sort().join(",")}:${[...activePanelIndicators].sort().join(",")}`, next);
    await updateTechnicalChart();
  }

  container.querySelectorAll("[data-interval]").forEach((button) => {
    const interval = button.dataset.interval;
    if (interval === activeInterval) button.classList.add("is-active");
    button.addEventListener("click", async () => {
      if (button.classList.contains("is-disabled")) return;
      activeInterval = interval;
      container.querySelectorAll("[data-interval]").forEach((item) => item.classList.remove("is-active"));
      button.classList.add("is-active");
      await updateTechnicalChart();
    });
  });

  container.querySelectorAll("[data-stock-zoom]").forEach((button) => {
    button.addEventListener("click", () => updateStockZoom(button.dataset.stockZoom));
  });

  container.querySelectorAll("[data-stock-pan]").forEach((button) => {
    button.addEventListener("click", () => updateStockPan(button.dataset.stockPan));
  });

  container.querySelectorAll("[data-ma-period]").forEach((button) => {
    button.addEventListener("click", async () => {
      const period = Number(button.dataset.maPeriod);
      if (activeMaPeriods.has(period)) {
        activeMaPeriods.delete(period);
        button.classList.remove("is-active");
      } else {
        activeMaPeriods.add(period);
        button.classList.add("is-active");
      }
      await updateTechnicalChart();
    });
  });

  container.querySelectorAll("[data-chart-indicator]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.chartIndicator || "";
      if (activeOverlayIndicators.has(key)) {
        activeOverlayIndicators.delete(key);
      } else if (key) {
        activeOverlayIndicators.add(key);
      }
      container.querySelectorAll("[data-chart-indicator]").forEach((item) => {
        item.classList.toggle("is-active", activeOverlayIndicators.has(item.dataset.chartIndicator));
      });
      await updateTechnicalChart();
    });
  });

  container.querySelectorAll("[data-panel-indicator]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.panelIndicator || "kd";
      if (activePanelIndicators.has(key) && activePanelIndicators.size > 1) {
        activePanelIndicators.delete(key);
      } else {
        activePanelIndicators.add(key);
      }
      container.querySelectorAll("[data-panel-indicator]").forEach((item) => {
        item.classList.toggle("is-active", activePanelIndicators.has(item.dataset.panelIndicator));
      });
      await updateTechnicalChart();
    });
  });
}
function initInstitutionChartCursor(root = document) {
  root.querySelectorAll(".chip-institution-chart").forEach((chart) => {
    const svg = chart.querySelector("svg");
    const tooltip = chart.querySelector(".institution-chart-tooltip");
    if (!svg || !tooltip) return;
    const xLine = svg.querySelector("[data-institution-cursor-x]");
    const yLine = svg.querySelector("[data-institution-cursor-y]");
    const dot = svg.querySelector("[data-institution-cursor-dot]");
    const zones = svg.querySelectorAll(".institution-hover-zone");
    const hide = () => {
      tooltip.hidden = true;
      xLine?.classList.remove("is-visible");
      yLine?.classList.remove("is-visible");
      dot?.classList.remove("is-visible");
    };
    const tooltipToneClass = (value) => {
      const parsed = parseAnalysisNumber(value);
      if (!Number.isFinite(parsed) || parsed === 0) return "is-flat";
      return parsed > 0 ? "is-up" : "is-down";
    };
    const rowHtml = (label, value, tone = "") => {
      if (!value || value === "--") return "";
      return `<span><em>${escapeHtml(label)}</em><strong class="${tone}">${escapeHtml(value)}</strong></span>`;
    };
    const show = (zone, event) => {
      const x = Number(zone.dataset.x);
      const y = Number(zone.dataset.y);
      if (Number.isFinite(x) && xLine) {
        xLine.setAttribute("x1", x.toFixed(2));
        xLine.setAttribute("x2", x.toFixed(2));
        xLine.classList.add("is-visible");
      }
      if (Number.isFinite(y) && yLine) {
        yLine.setAttribute("y1", y.toFixed(2));
        yLine.setAttribute("y2", y.toFixed(2));
        yLine.classList.add("is-visible");
      }
      if (Number.isFinite(x) && Number.isFinite(y) && dot) {
        dot.setAttribute("cx", x.toFixed(2));
        dot.setAttribute("cy", y.toFixed(2));
        dot.classList.add("is-visible");
      }
      const rows = [
        zone.dataset.showPrice === "1" ? rowHtml("股價", zone.dataset.price) : "",
        zone.dataset.showForeign === "1" ? rowHtml("外資", zone.dataset.foreign, tooltipToneClass(zone.dataset.foreign)) : "",
        zone.dataset.showTrust === "1" ? rowHtml("投信", zone.dataset.trust, tooltipToneClass(zone.dataset.trust)) : "",
        zone.dataset.showDealer === "1" ? rowHtml("自營商", zone.dataset.dealer, tooltipToneClass(zone.dataset.dealer)) : "",
        rowHtml("合計", zone.dataset.total, tooltipToneClass(zone.dataset.total)),
        zone.dataset.showForeign === "1" ? rowHtml("外資籌碼", zone.dataset.foreignChip) : "",
        zone.dataset.showPrice === "1" ? rowHtml("漲跌幅", zone.dataset.change, tooltipToneClass(zone.dataset.change)) : "",
        zone.dataset.showPrice === "1" ? rowHtml("成交量", zone.dataset.volume) : "",
      ].filter(Boolean).join("");
      tooltip.innerHTML = `<b>${escapeHtml(zone.dataset.date || "--")}</b>${rows}`;
      tooltip.hidden = false;
      const chartRect = chart.getBoundingClientRect();
      const leftBase = event.clientX - chartRect.left + 14;
      const topBase = event.clientY - chartRect.top - 10;
      const maxLeft = Math.max(12, chartRect.width - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, chartRect.height - tooltip.offsetHeight - 12);
      tooltip.style.left = `${Math.max(12, Math.min(leftBase, maxLeft))}px`;
      tooltip.style.top = `${Math.max(12, Math.min(topBase, maxTop))}px`;
    };
    zones.forEach((zone) => {
      zone.addEventListener("mouseenter", (event) => show(zone, event));
      zone.addEventListener("mousemove", (event) => show(zone, event));
      zone.addEventListener("mouseleave", hide);
    });
    chart.addEventListener("mouseleave", hide);
  });
}
function initMajorHolderChartCursor(root = document) {
  root.querySelectorAll(".major-holder-chart").forEach((chart) => {
    const svg = chart.querySelector("svg");
    const tooltip = chart.querySelector(".holder-chart-tooltip");
    if (!svg || !tooltip) return;
    const xLine = svg.querySelector("[data-holder-cursor-x]");
    const dots = {
      price: svg.querySelector('[data-holder-cursor-dot="price"]'),
      foreign: svg.querySelector('[data-holder-cursor-dot="foreign"]'),
      major: svg.querySelector('[data-holder-cursor-dot="major"]'),
      director: svg.querySelector('[data-holder-cursor-dot="director"]'),
    };
    const zones = svg.querySelectorAll(".holder-hover-zone");
    const hide = () => {
      tooltip.hidden = true;
      xLine?.classList.remove("is-visible");
      Object.values(dots).forEach((dot) => dot?.classList.remove("is-visible"));
    };
    const rowHtml = (label, value) => {
      if (!value || value === "--") return "";
      return `<span><em>${escapeHtml(label)}</em><strong>${escapeHtml(value)}</strong></span>`;
    };
    const moveDot = (dot, x, yValue) => {
      const y = Number(yValue);
      if (!dot || !Number.isFinite(x) || !Number.isFinite(y)) {
        dot?.classList.remove("is-visible");
        return;
      }
      dot.setAttribute("cx", x.toFixed(2));
      dot.setAttribute("cy", y.toFixed(2));
      dot.classList.add("is-visible");
    };
    const show = (zone, event) => {
      const x = Number(zone.dataset.x);
      if (Number.isFinite(x) && xLine) {
        xLine.setAttribute("x1", x.toFixed(2));
        xLine.setAttribute("x2", x.toFixed(2));
        xLine.classList.add("is-visible");
      }
      moveDot(dots.price, x, zone.dataset.yPrice);
      moveDot(dots.foreign, x, zone.dataset.yForeign);
      moveDot(dots.major, x, zone.dataset.yMajor);
      moveDot(dots.director, x, zone.dataset.yDirector);
      const rows = [
        rowHtml("外資籌碼", zone.dataset.foreign),
        rowHtml("大戶籌碼", zone.dataset.major),
        rowHtml("董監持股", zone.dataset.director),
        rowHtml("股價", zone.dataset.price),
      ].filter(Boolean).join("");
      tooltip.innerHTML = `<b>${escapeHtml(zone.dataset.date || "--")}</b>${rows}`;
      tooltip.hidden = false;
      const chartRect = chart.getBoundingClientRect();
      const leftBase = event.clientX - chartRect.left + 14;
      const topBase = event.clientY - chartRect.top - 10;
      const maxLeft = Math.max(12, chartRect.width - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, chartRect.height - tooltip.offsetHeight - 12);
      tooltip.style.left = `${Math.max(12, Math.min(leftBase, maxLeft))}px`;
      tooltip.style.top = `${Math.max(12, Math.min(topBase, maxTop))}px`;
    };
    zones.forEach((zone) => {
      zone.addEventListener("mouseenter", (event) => show(zone, event));
      zone.addEventListener("mousemove", (event) => show(zone, event));
      zone.addEventListener("mouseleave", hide);
    });
    chart.addEventListener("mouseleave", hide);
  });
}
function initMarginBalanceChartCursor(root = document) {
  root.querySelectorAll(".margin-balance-visual").forEach((chart) => {
    const svg = chart.querySelector("svg");
    const tooltip = chart.querySelector(".margin-chart-tooltip");
    if (!svg || !tooltip) return;
    const xLine = svg.querySelector("[data-margin-cursor-x]");
    const dot = svg.querySelector("[data-margin-cursor-dot]");
    const zones = svg.querySelectorAll(".margin-hover-zone");
    const hide = () => {
      tooltip.hidden = true;
      xLine?.classList.remove("is-visible");
      dot?.classList.remove("is-visible");
    };
    const toneClass = (value) => {
      const parsed = parseAnalysisNumber(value);
      if (!Number.isFinite(parsed) || parsed === 0) return "is-flat";
      return parsed > 0 ? "is-up" : "is-down";
    };
    const rowHtml = (label, value, change, changeLabel = "當日增減") => `
      <span>
        <em>${escapeHtml(label)}</em>
        <strong>${escapeHtml(value || "--")}${change && change !== "--" ? ` <small class="${toneClass(change)}">/ ${escapeHtml(changeLabel)} ${escapeHtml(change)}</small>` : ""}</strong>
      </span>
    `;
    const show = (zone, event) => {
      const x = Number(zone.dataset.x);
      const y = Number(zone.dataset.y);
      if (Number.isFinite(x) && xLine) {
        xLine.setAttribute("x1", x.toFixed(2));
        xLine.setAttribute("x2", x.toFixed(2));
        xLine.classList.add("is-visible");
      }
      if (Number.isFinite(x) && Number.isFinite(y) && dot) {
        dot.setAttribute("cx", x.toFixed(2));
        dot.setAttribute("cy", y.toFixed(2));
        dot.classList.add("is-visible");
      }
      tooltip.innerHTML = `
        <b>${escapeHtml(zone.dataset.date || "--")}</b>
        ${rowHtml("股價", zone.dataset.price, zone.dataset.priceChange, "漲跌幅")}
        ${rowHtml("融資餘額", zone.dataset.financing, zone.dataset.financingChange)}
        ${rowHtml("融券餘額", zone.dataset.short, zone.dataset.shortChange)}
        ${rowHtml("借券賣出餘額", zone.dataset.lending, zone.dataset.lendingChange)}
      `;
      tooltip.hidden = false;
      const chartRect = chart.getBoundingClientRect();
      const leftBase = event.clientX - chartRect.left + 14;
      const topBase = event.clientY - chartRect.top - 10;
      const maxLeft = Math.max(12, chartRect.width - tooltip.offsetWidth - 12);
      const maxTop = Math.max(12, chartRect.height - tooltip.offsetHeight - 12);
      tooltip.style.left = `${Math.max(12, Math.min(leftBase, maxLeft))}px`;
      tooltip.style.top = `${Math.max(12, Math.min(topBase, maxTop))}px`;
    };
    zones.forEach((zone) => {
      zone.addEventListener("mouseenter", (event) => show(zone, event));
      zone.addEventListener("mousemove", (event) => show(zone, event));
      zone.addEventListener("mouseleave", hide);
    });
    chart.addEventListener("mouseleave", hide);
  });
}
function getStockDetailCacheKey(code, market = "") {
  return `${String(market || "").trim().toUpperCase()}:${String(code || "").trim()}`;
}
