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
    targetHref: "derivatives-analytics.html#derivatives-ai-section",
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
