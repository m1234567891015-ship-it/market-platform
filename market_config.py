from __future__ import annotations

from datetime import datetime
from urllib.parse import urlencode

LISTED_SECTOR_INDEX_SPECS = [
    {"key": "水泥", "display": "水泥", "aliases": ["水泥類指數", "水泥工業類指數", "水泥類"]},
    {"key": "食品", "display": "食品", "aliases": ["食品類指數", "食品工業類指數", "食品類"]},
    {"key": "塑膠", "display": "塑膠", "aliases": ["塑膠類指數", "塑膠工業類指數", "塑膠類"]},
    {"key": "紡織", "display": "紡織", "aliases": ["紡織纖維類指數", "紡織類指數"]},
    {"key": "電機機械", "display": "電機機械", "aliases": ["電機機械類指數", "機電類指數"]},
    {"key": "電器電纜", "display": "電器電纜", "aliases": ["電器電纜類指數"]},
    {"key": "化學", "display": "化學", "aliases": ["化學類指數", "化學工業類指數"]},
    {"key": "生技", "display": "生技", "aliases": ["生技醫療類指數"]},
    {"key": "造紙", "display": "造紙", "aliases": ["造紙類指數", "造紙工業類指數"]},
    {"key": "鋼鐵", "display": "鋼鐵", "aliases": ["鋼鐵類指數", "鋼鐵工業類指數"]},
    {"key": "橡膠", "display": "橡膠", "aliases": ["橡膠類指數", "橡膠工業類指數"]},
    {"key": "汽車", "display": "汽車", "aliases": ["汽車類指數", "汽車工業類指數"]},
    {"key": "半導體", "display": "半導體", "aliases": ["半導體類指數"]},
    {"key": "電腦週邊", "display": "電腦週邊", "aliases": ["電腦及週邊設備類指數"]},
    {"key": "光電", "display": "光電", "aliases": ["光電類指數"]},
    {"key": "通訊網路", "display": "通訊網路", "aliases": ["通信網路類指數", "通訊網路類指數"]},
    {"key": "電子零組件", "display": "電子零組件", "aliases": ["電子零組件類指數"]},
    {"key": "電子通路", "display": "電子通路", "aliases": ["電子通路類指數"]},
    {"key": "資訊服務", "display": "資訊服務", "aliases": ["資訊服務類指數"]},
    {"key": "其他電子", "display": "其他電子", "aliases": ["其他電子類指數"]},
    {"key": "營建", "display": "營建", "aliases": ["建材營造類指數", "營造建材類指數"]},
    {"key": "航運", "display": "航運", "aliases": ["航運類指數"]},
    {"key": "觀光餐旅", "display": "觀光餐旅", "aliases": ["觀光餐旅類指數", "觀光事業類指數"]},
    {"key": "金融業", "display": "金融業", "aliases": ["金融保險類指數"]},
    {"key": "貿易百貨", "display": "貿易百貨", "aliases": ["貿易百貨類指數"]},
    {"key": "油電燃氣", "display": "油電燃氣", "aliases": ["油電燃氣類指數"]},
    {"key": "存託憑證", "display": "存託憑證", "aliases": ["存託憑證類指數", "TDR類指數"]},
    {"key": "ETF", "display": "ETF", "aliases": ["ETF", "ETF類指數"]},
    {"key": "受益證券", "display": "受益證券", "aliases": ["受益證券", "受益證券類指數"]},
    {"key": "ETN", "display": "ETN", "aliases": ["ETN", "ETN類指數"]},
    {"key": "其他", "display": "其他", "aliases": ["其他類指數", "其他"]},
    {"key": "市認購", "display": "市認購", "aliases": ["市認購", "市認購(售)權證類指數", "市認購類指數"]},
    {"key": "市認售", "display": "市認售", "aliases": ["市認售", "市認購(售)權證類指數", "市認售類指數"]},
    {"key": "指數類", "display": "指數類", "aliases": ["指數類", "指數類指數"]},
    {"key": "市牛證", "display": "市牛證", "aliases": ["市牛證", "市牛證類指數"]},
    {"key": "市熊證", "display": "市熊證", "aliases": ["市熊證", "市熊證類指數"]},
    {"key": "運動休閒", "display": "運動休閒", "aliases": ["運動休閒類指數"]},
    {"key": "居家生活", "display": "居家生活", "aliases": ["居家生活類指數"]},
    {"key": "數位雲端", "display": "數位雲端", "aliases": ["數位雲端類指數"]},
    {"key": "綠能環保", "display": "綠能環保", "aliases": ["綠能環保類指數"]},
]
LISTED_SECTOR_INDEX_ORDER = [item["key"] for item in LISTED_SECTOR_INDEX_SPECS]
SECTOR_INDEX_LOOKUP = {
    alias: item["key"]
    for item in [{"key": "發行量加權股價指數", "aliases": ["發行量加權股價指數"]}, *LISTED_SECTOR_INDEX_SPECS]
    for alias in [item["key"], *item.get("aliases", [])]
}
SECTOR_INDEX_DISPLAY_NAMES = {
    "發行量加權股價指數": "台灣加權指數",
    **{item["key"]: item["display"] for item in LISTED_SECTOR_INDEX_SPECS},
}
TARGET_INDEX_NAMES = ["發行量加權股價指數", *LISTED_SECTOR_INDEX_ORDER]
INDEX_DISPLAY_NAMES = dict(SECTOR_INDEX_DISPLAY_NAMES)
EXCLUDED_SECTOR_SOURCE_NAMES = {"玻璃陶瓷類指數"}
SUPPORTED_CHART_INTERVALS = ["day", "week", "month", "all"]
PAGE_ROUTES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/market-overview.html": "market-overview.html",
    "/tw-stocks.html": "tw-stocks.html",
    "/tw-etf.html": "tw-etf.html",
    "/tw-Optional-stocks.html": "tw-Optional-stocks.html",
    "/tw-stock-search.html": "tw-stock-search.html",
    "/news.html": "news.html",
    "/us-market-overview.html": "us-market-overview.html",
    "/us-stocks.html": "us-stocks.html",
    "/us-etf.html": "us-etf.html",
    "/us-stock-search.html": "us-stock-search.html",
    "/derivatives-assets.html": "derivatives-assets.html",
    "/international-finance.html": "international-finance.html",
    "/us-watchlist.html": "us-watchlist.html",
    "/futures.html": "futures.html",
    "/options.html": "options.html",
    "/derivatives-analytics.html": "derivatives-analytics.html",
    "/derivatives-ai.html": "derivatives-ai.html",
    "/derivatives-status.html": "derivatives-status.html",
    "/analytics": "derivatives-analytics.html",
    "/ai-analysis": "derivatives-ai.html",
    "/precious-metals.html": "precious-metals.html",
    "/bonds.html": "bonds.html",
}
ROOT_STATIC_FILES = {
    "app.js",
    "derivatives-ui.js",
    "pwa.js",
    "styles.css",
    "twse-cache.json",
    "twse-data.js",
}
ASSET_STATIC_FILES = {
    "app-icon.svg",
    "app-icon-192.png",
    "app-icon-512.png",
    "background.jpg",
}
# TD-02:app.js 拆分後的模組檔案,從 js/ 目錄以白名單方式提供(比照
# ASSET_STATIC_FILES 的模式),每完成一個批次就補上對應檔名。
JS_MODULE_STATIC_FILES = {
    "state.js",
    "core.js",
    "api.js",
    "shared-calc.js",
    "render-shared.js",
    "charts.js",
    "stock-detail.js",
    "page-home.js",
    "page-us.js",
    "page-global-market-futures.js",
    "page-global-market-options.js",
    "page-global-market-assethub.js",
    "page-tw.js",
    "legacy-unclassified.js",
    "main.js",
}
# CSS 拆分(styles.css → css/ 目錄),同樣以白名單方式提供,每完成一個
# 批次就補上對應檔名,比照 JS_MODULE_STATIC_FILES 的模式。
CSS_MODULE_STATIC_FILES = {
    "charts.css",
}
TWSE_BASE = "https://www.twse.com.tw"
TWSE_OPENAPI_BASE = "https://openapi.twse.com.tw/v1"
TPEX_OPENAPI_BASE = "https://www.tpex.org.tw/openapi/v1"
FRED_GRAPH_CSV_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_SERIES_BASE = "https://fred.stlouisfed.org/series"
TRADING_ECONOMICS_TAIWAN_10Y_URL = "https://tradingeconomics.com/taiwan/government-bond-yield"
YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
YAHOO_SEARCH_BASE = "https://query2.finance.yahoo.com/v1/finance/search"
CBOE_OPTIONS_BASE = "https://cdn.cboe.com/api/global/delayed_quotes/options"
YAHOO_QUOTE_SUMMARY_BASE = "https://query2.finance.yahoo.com/v10/finance/quoteSummary"
NASDAQ_API_BASE = "https://api.nasdaq.com/api"
NYSE_QUOTES_FILTER_URL = "https://www.nyse.com/api/quotes/filter"
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
NASDAQ_OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
TWSE_MARGIN_URL = f"{TWSE_OPENAPI_BASE}/exchangeReport/MI_MARGN"
TAIFEX_FUTURES_DAILY_URL = "https://www.taifex.com.tw/cht/3/futDailyMarketReport"
TAIFEX_OPTIONS_DAILY_URL = "https://www.taifex.com.tw/cht/3/optDailyMarketReport"
TAIFEX_OPTIONS_PC_RATIO_URL = "https://www.taifex.com.tw/cht/3/pcRatio"
# TD-12: merged with builders.py's former US_/YAHOO_/BARCHART_OPTIONS_CHAIN_CACHE_SECONDS
# (also 300s, also gating options-chain freshness, just for different sources/buckets)
# into one shared constant - all 4 were the same "5-minute options chain freshness"
# concept under different names. DERIBIT_/BYBIT_OPTIONS_CHAIN_CACHE_SECONDS (60s,
# builders.py) stay separate: 24/7 crypto markets genuinely need fresher data than
# session-hours markets, not a coincidental value match.
OPTIONS_CHAIN_CACHE_SECONDS = 5 * 60
TDCC_HOLDING_DISTRIBUTION_URL = "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"
TDCC_HOLDING_DISTRIBUTION_FALLBACK_URL = "http://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"
TDCC_HOLDING_CACHE_SECONDS = 6 * 60 * 60
US_TREASURY_YIELD_CURVE_YEAR = datetime.now().year
US_TREASURY_YIELD_CURVE_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    f"daily-treasury-rates.csv/{US_TREASURY_YIELD_CURVE_YEAR}/all?"
    f"type=daily_treasury_yield_curve&field_tdr_date_value={US_TREASURY_YIELD_CURVE_YEAR}&page&_format=csv"
)
YAHOO_CLASS_HOME_URL = "https://tw.stock.yahoo.com/class/"
YAHOO_TPEX_ETF_URL = "https://tw.stock.yahoo.com/class-quote?exchange=TWO&sectorId=172"
YAHOO_LISTED_CLASS_URL = "https://tw.stock.yahoo.com/class-quote?exchange=TAI&sectorId=33"
YAHOO_TPEX_OTC_CLASS_URL = "https://tw.stock.yahoo.com/class-quote?exchange=TWO&sectorId=33"
YAHOO_TPEX_EMERGING_CLASS_URL = "https://tw.stock.yahoo.com/class-quote?exchange=OES&sectorId=99311"
YAHOO_ELECTRONIC_CLASS_URL = (
    "https://tw.stock.yahoo.com/class-quote?"
    + urlencode({"category": "設備或廠務工程", "categoryLabel": "電子產業"})
)
YAHOO_CONCEPT_CLASS_URL = (
    "https://tw.stock.yahoo.com/class-quote?"
    + urlencode({"category": "AI人工智慧", "categoryLabel": "概念股"})
)
YAHOO_GROUP_CLASS_URL = (
    "https://tw.stock.yahoo.com/class-quote?"
    + urlencode({"category": "中纖", "categoryLabel": "集團股"})
)
USER_AGENT = "Mozilla/5.0 (compatible; MarketPulseBot/1.0)"
NASDAQ_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
GOOGLE_NEWS_RSS_BASE = "https://news.google.com/rss/search"
INTERNATIONAL_INDEX_SPECS = [
    {"key": "sp500", "name": "S&P 500", "symbol": "^GSPC", "market": "美國"},
    {"key": "dow", "name": "Dow Jones Industrial Average", "symbol": "^DJI", "market": "美國"},
    {"key": "nasdaq", "name": "NASDAQ Composite", "symbol": "^IXIC", "market": "美國"},
    {"key": "russell2000", "name": "Russell 2000", "symbol": "^RUT", "market": "美國"},
    {"key": "stoxx600", "name": "STOXX Europe 600", "symbol": "^STOXX", "fallbackSymbols": ["EXSA.DE"], "market": "歐洲"},
    {"key": "dax", "name": "DAX", "symbol": "^GDAXI", "market": "德國"},
    {"key": "cac40", "name": "CAC 40", "symbol": "^FCHI", "market": "法國"},
    {"key": "ftse100", "name": "FTSE 100", "symbol": "^FTSE", "market": "英國"},
    {"key": "nikkei225", "name": "Nikkei 225", "symbol": "^N225", "market": "日本"},
    {"key": "topix", "name": "TOPIX", "symbol": "^TOPX", "fallbackSymbols": ["1306.T"], "market": "日本"},
    {"key": "hangseng", "name": "Hang Seng Index", "symbol": "^HSI", "market": "香港"},
    {"key": "shanghai", "name": "Shanghai Composite Index", "symbol": "000001.SS", "market": "中國"},
    {"key": "shenzhen", "name": "Shenzhen Component Index", "symbol": "399001.SZ", "market": "中國"},
    {"key": "kospi", "name": "KOSPI", "symbol": "^KS11", "market": "韓國"},
    {"key": "sox", "name": "Philadelphia Semiconductor Index", "symbol": "^SOX", "market": "美國半導體"},
    {"key": "msciworld", "name": "MSCI World Index", "symbol": "URTH", "market": "全球成熟市場", "proxy": "iShares MSCI World ETF"},
    {"key": "msciem", "name": "MSCI Emerging Markets Index", "symbol": "EEM", "market": "新興市場", "proxy": "iShares MSCI Emerging Markets ETF"},
    {"key": "vix", "name": "VIX 指數", "symbol": "^VIX", "market": "波動率"},
]
GLOBAL_MARKET_CACHE_SECONDS = 5 * 60
GLOBAL_MARKET_DEFAULT_LOAD_LIMIT = 36
GLOBAL_MARKET_MAX_LOAD_LIMIT = 160
US_LISTED_UNIVERSE_CACHE_SECONDS = 12 * 60 * 60
GLOBAL_MARKET_CATEGORIES = {
    "us-stocks": {
        "title": "美股",
        "kicker": "US Stocks",
        "subtitle": "追蹤美國主要指數、美股個股與美股 ETF，觀察全球風險偏好、科技股資金與 ETF 輪動。",
        "items": [
            {"symbol": "^GSPC", "name": "S&P 500", "type": "美國指數", "group": "主要指數"},
            {"symbol": "^DJI", "name": "Dow Jones Industrial Average", "type": "美國指數", "group": "主要指數"},
            {"symbol": "^IXIC", "name": "NASDAQ Composite", "type": "美國指數", "group": "主要指數"},
            {"symbol": "^RUT", "name": "Russell 2000", "type": "美國指數", "group": "主要指數"},
            {"symbol": "^VIX", "fallbackSymbols": ["VIXY", "VXX"], "name": "VIX 指數", "type": "波動率", "group": "市場情緒"},
            {"symbol": "AAPL", "name": "Apple", "type": "大型科技股", "group": "美股個股"},
            {"symbol": "MSFT", "name": "Microsoft", "type": "大型科技股", "group": "美股個股"},
            {"symbol": "NVDA", "name": "NVIDIA", "type": "AI 半導體", "group": "美股個股"},
            {"symbol": "AMD", "name": "AMD", "type": "AI 半導體", "group": "美股個股"},
            {"symbol": "AVGO", "name": "Broadcom", "type": "AI 半導體", "group": "美股個股"},
            {"symbol": "AMZN", "name": "Amazon", "type": "消費科技", "group": "美股個股"},
            {"symbol": "GOOGL", "name": "Alphabet", "type": "大型科技股", "group": "美股個股"},
            {"symbol": "META", "name": "Meta Platforms", "type": "大型科技股", "group": "美股個股"},
            {"symbol": "TSLA", "name": "Tesla", "type": "成長股", "group": "美股個股"},
            {"symbol": "JPM", "name": "JPMorgan Chase", "type": "金融股", "group": "美股個股"},
            {"symbol": "^SP500-45", "fallbackSymbols": ["XLK"], "name": "S&P 500 Information Technology", "type": "科技類股指數", "group": "美股類股指數"},
            {"symbol": "^SP500-40", "fallbackSymbols": ["XLF"], "name": "S&P 500 Financials", "type": "金融類股指數", "group": "美股類股指數"},
            {"symbol": "^SP500-35", "fallbackSymbols": ["XLV"], "name": "S&P 500 Health Care", "type": "醫療保健指數", "group": "美股類股指數"},
            {"symbol": "^SP500-25", "fallbackSymbols": ["XLY"], "name": "S&P 500 Consumer Discretionary", "type": "非必需消費指數", "group": "美股類股指數"},
            {"symbol": "^SP500-50", "fallbackSymbols": ["XLC"], "name": "S&P 500 Communication Services", "type": "通訊服務指數", "group": "美股類股指數"},
            {"symbol": "^SP500-20", "fallbackSymbols": ["XLI"], "name": "S&P 500 Industrials", "type": "工業類股指數", "group": "美股類股指數"},
            {"symbol": "^SP500-30", "fallbackSymbols": ["XLP"], "name": "S&P 500 Consumer Staples", "type": "必需消費指數", "group": "美股類股指數"},
            {"symbol": "^SP500-10", "fallbackSymbols": ["XLE"], "name": "S&P 500 Energy", "type": "能源類股指數", "group": "美股類股指數"},
            {"symbol": "^SP500-15", "fallbackSymbols": ["XLB"], "name": "S&P 500 Materials", "type": "原物料指數", "group": "美股類股指數"},
            {"symbol": "^SP500-55", "fallbackSymbols": ["XLU"], "name": "S&P 500 Utilities", "type": "公用事業指數", "group": "美股類股指數"},
            {"symbol": "^SP500-60", "fallbackSymbols": ["XLRE"], "name": "S&P 500 Real Estate", "type": "不動產指數", "group": "美股類股指數"},
            {"symbol": "^SOX", "fallbackSymbols": ["SMH", "SOXX"], "name": "Philadelphia Semiconductor Index", "type": "半導體產業指數", "group": "美股類股指數"},
            {"symbol": "^DJUSTC", "fallbackSymbols": ["XLK"], "name": "Dow Jones U.S. Technology Index", "type": "科技產業指數", "group": "美股類股指數"},
            {"symbol": "^DJUSFN", "fallbackSymbols": ["XLF"], "name": "Dow Jones U.S. Financials Index", "type": "金融產業指數", "group": "美股類股指數"},
            {"symbol": "^DJUSHC", "fallbackSymbols": ["XLV"], "name": "Dow Jones U.S. Health Care Index", "type": "醫療產業指數", "group": "美股類股指數"},
            {"symbol": "^DJUSEN", "fallbackSymbols": ["XLE"], "name": "Dow Jones U.S. Energy Index", "type": "能源產業指數", "group": "美股類股指數"},
            {"symbol": "^DJUSRE", "fallbackSymbols": ["XLRE"], "name": "Dow Jones U.S. Real Estate Index", "type": "不動產產業指數", "group": "美股類股指數"},
        ],
    },
    "futures": {
        "title": "全球期貨分析中心",
        "kicker": "Futures",
        "subtitle": "整合台灣、美國與國際期貨市場，提供行情、技術分析、籌碼分析、風險控管與 AI 趨勢判斷。",
        "items": [
            {"symbol": "TX", "name": "臺股期貨 TX 未平倉", "type": "台灣股指期貨", "group": "台灣期貨", "region": "台灣", "market": "台灣", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方期貨日報", "referenceSource": "TAIFEX 臺股期貨契約規格", "sourceUrl": TAIFEX_FUTURES_DAILY_URL, "dataProvider": "taifex_tx_open_interest", "metricLabel": "未平倉量"},
            {"symbol": "MTX", "name": "小型臺指期貨 MTX 未平倉", "type": "台灣股指期貨", "group": "台灣期貨", "region": "台灣", "market": "台灣", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方期貨日報", "referenceSource": "TAIFEX 小型臺指期貨契約規格", "sourceUrl": TAIFEX_FUTURES_DAILY_URL, "dataProvider": "taifex_futures_open_interest", "taifexCommodity": "MTX", "metricLabel": "未平倉量"},
            {"symbol": "TMF", "name": "微型臺指期貨 TMF 未平倉", "type": "台灣股指期貨", "group": "台灣期貨", "region": "台灣", "market": "台灣", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方期貨日報", "referenceSource": "TAIFEX 微型臺指期貨契約規格", "sourceUrl": TAIFEX_FUTURES_DAILY_URL, "dataProvider": "taifex_futures_open_interest", "taifexCommodity": "TMF", "metricLabel": "未平倉量"},
            {"symbol": "TE", "name": "電子期貨 TE 未平倉", "type": "台灣類股期貨", "group": "台灣期貨", "region": "台灣", "market": "台灣", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方期貨日報", "referenceSource": "TAIFEX 電子期貨契約規格", "sourceUrl": TAIFEX_FUTURES_DAILY_URL, "dataProvider": "taifex_futures_open_interest", "taifexCommodity": "TE", "metricLabel": "未平倉量"},
            {"symbol": "TF", "name": "金融期貨 TF 未平倉", "type": "台灣類股期貨", "group": "台灣期貨", "region": "台灣", "market": "台灣", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方期貨日報", "referenceSource": "TAIFEX 金融期貨契約規格", "sourceUrl": TAIFEX_FUTURES_DAILY_URL, "dataProvider": "taifex_futures_open_interest", "taifexCommodity": "TF", "metricLabel": "未平倉量"},
            {"symbol": "SOF", "name": "櫃買期貨 SOF 未平倉", "type": "台灣櫃買指數期貨", "group": "國內指數期貨", "region": "台灣", "market": "台灣", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方期貨日報", "referenceSource": "TAIFEX 櫃買期貨契約規格", "sourceUrl": TAIFEX_FUTURES_DAILY_URL, "dataProvider": "taifex_futures_open_interest", "taifexCommodity": "SOF", "metricLabel": "未平倉量", "v1Status": "connected"},
            {"symbol": "STF", "name": "股票期貨", "type": "股票期貨", "group": "國內股票期貨", "region": "台灣", "market": "台灣", "exchange": "TAIFEX", "dataSource": "TAIFEX OpenAPI 股票期貨標的清單 + 每日行情", "referenceSource": "TAIFEX 股票期貨契約規格", "sourceUrl": TAIFEX_FUTURES_DAILY_URL, "dataProvider": "taifex_product_status", "metricLabel": "未平倉量", "v1Status": "connected", "dataStatus": "TAIFEX OpenAPI 即時彙總所有股票期貨契約之未平倉量與成交量。"},
            {"symbol": "ETF-F", "name": "ETF 期貨", "type": "ETF期貨", "group": "國內ETF期貨", "region": "台灣", "market": "台灣", "exchange": "TAIFEX", "dataSource": "TAIFEX OpenAPI ETF期貨標的清單 + 每日行情", "referenceSource": "TAIFEX ETF 期貨契約規格", "sourceUrl": TAIFEX_FUTURES_DAILY_URL, "dataProvider": "taifex_product_status", "metricLabel": "未平倉量", "v1Status": "connected", "dataStatus": "TAIFEX OpenAPI 即時彙總所有 ETF 期貨契約之未平倉量與成交量。"},
            {"symbol": "ES=F", "name": "S&P 500 E-mini Futures", "type": "股指期貨", "exchange": "CME"},
            {"symbol": "MES=F", "name": "Micro E-mini S&P 500 Futures", "type": "股指期貨", "exchange": "CME"},
            {"symbol": "NQ=F", "name": "Nasdaq 100 E-mini Futures", "type": "股指期貨", "exchange": "CME"},
            {"symbol": "MNQ=F", "name": "Micro E-mini Nasdaq 100 Futures", "type": "股指期貨", "exchange": "CME"},
            {"symbol": "YM=F", "name": "Dow Futures", "type": "股指期貨", "exchange": "CBOT"},
            {"symbol": "RTY=F", "name": "Russell 2000 Futures", "type": "股指期貨", "exchange": "CME"},
            {"symbol": "ZB=F", "name": "U.S. Treasury Bond Futures", "type": "利率期貨"},
            {"symbol": "ZN=F", "name": "10-Year T-Note Futures", "type": "利率期貨"},
            {"symbol": "ZF=F", "name": "5-Year T-Note Futures", "type": "利率期貨"},
            {"symbol": "ZT=F", "name": "2-Year T-Note Futures", "type": "利率期貨"},
            {"symbol": "6E=F", "name": "Euro FX Futures", "type": "外匯期貨", "region": "歐洲", "market": "歐元區", "exchange": "CME"},
            {"symbol": "6J=F", "name": "Japanese Yen Futures", "type": "外匯期貨", "region": "亞洲", "market": "日本", "exchange": "CME"},
            {"symbol": "6B=F", "name": "British Pound Futures", "type": "外匯期貨", "region": "歐洲", "market": "英國", "exchange": "CME"},
            {"symbol": "CL=F", "name": "WTI Crude Oil Futures", "type": "能源期貨"},
            {"symbol": "BZ=F", "name": "Brent Crude Oil Futures", "type": "能源期貨", "region": "歐洲", "market": "英國 / 歐洲", "exchange": "ICE Europe"},
            {"symbol": "NG=F", "name": "Natural Gas Futures", "type": "能源期貨"},
            {"symbol": "RB=F", "name": "RBOB Gasoline Futures", "type": "能源期貨"},
            {"symbol": "HO=F", "name": "Heating Oil Futures", "type": "能源期貨"},
            {"symbol": "GC=F", "name": "Gold Futures", "type": "貴金屬期貨"},
            {"symbol": "SI=F", "name": "Silver Futures", "type": "貴金屬期貨"},
            {"symbol": "PL=F", "name": "Platinum Futures", "type": "貴金屬期貨"},
            {"symbol": "PA=F", "name": "Palladium Futures", "type": "貴金屬期貨"},
            {"symbol": "HG=F", "name": "Copper Futures", "type": "金屬期貨"},
            {"symbol": "ZC=F", "name": "Corn Futures", "type": "農產品期貨"},
            {"symbol": "ZW=F", "name": "Wheat Futures", "type": "農產品期貨"},
            {"symbol": "ZS=F", "name": "Soybean Futures", "type": "農產品期貨"},
            {"symbol": "KC=F", "name": "Coffee Futures", "type": "軟性商品期貨"},
            {"symbol": "SB=F", "name": "Sugar Futures", "type": "軟性商品期貨"},
            {"symbol": "CT=F", "name": "Cotton Futures", "type": "軟性商品期貨"},
            {"symbol": "LE=F", "name": "Live Cattle Futures", "type": "畜牧期貨"},
            {"symbol": "HE=F", "name": "Lean Hogs Futures", "type": "畜牧期貨"},
        ],
    },
    "options": {
        "title": "選擇權",
        "kicker": "Options",
        "subtitle": "依文件分類整合指數、股票、ETF、商品、外匯、利率、波動率、加密、天氣與碳權選擇權市場；官方鏈優先，無公開鏈時以線上標的行情代理觀察。",
        "items": [
            {"symbol": "TXO", "name": "臺指選擇權 TXO", "type": "指數選擇權", "group": "台灣指數選擇權", "region": "台灣", "market": "TAIFEX", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方選擇權日報", "referenceSource": "TAIFEX 臺指選擇權契約規格", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "dataProvider": "taifex_txo_open_interest", "metricLabel": "未平倉量", "optionCategory": "指數選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方逐履約價鏈"},
            {"symbol": "MXO", "fallbackSymbols": ["^TWII", "EWT", "0050.TW"], "name": "小型臺指選擇權", "type": "指數選擇權同標的參照", "group": "台灣指數選擇權", "region": "台灣", "market": "TAIFEX", "exchange": "TAIFEX", "dataSource": "TAIFEX 臺指選擇權官方逐履約價（同標的參照）", "referenceSource": "TAIFEX 選擇權每日交易行情查詢", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "metricLabel": "未平倉量", "dataStatus": "TAIFEX 目前未列獨立小型臺指選擇權逐履約價；系統以同標的 TXO 官方鏈作風險參照並明確標示。", "optionCategory": "指數選擇權", "optionSubcategory": "台灣", "optionSourceRole": "同標的官方鏈"},
            {"symbol": "TEO", "name": "電子選擇權 TEO", "type": "指數選擇權", "group": "台灣指數選擇權", "region": "台灣", "market": "TAIFEX", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方選擇權日報", "referenceSource": "TAIFEX 電子選擇權契約規格", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "dataProvider": "taifex_txo_open_interest", "taifexCommodity": "TEO", "metricLabel": "未平倉量", "optionCategory": "指數選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方逐履約價鏈"},
            {"symbol": "TFO", "name": "金融選擇權 TFO", "type": "指數選擇權", "group": "台灣指數選擇權", "region": "台灣", "market": "TAIFEX", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方選擇權日報", "referenceSource": "TAIFEX 金融選擇權契約規格", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "dataProvider": "taifex_txo_open_interest", "taifexCommodity": "TFO", "metricLabel": "未平倉量", "optionCategory": "指數選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方逐履約價鏈"},
            {"symbol": "T50O", "fallbackSymbols": ["0050.TW", "006208.TW", "^TWII", "EWT"], "name": "臺灣50選擇權", "type": "ETF 選擇權", "group": "台灣指數選擇權", "region": "台灣", "market": "TAIFEX", "exchange": "TAIFEX", "dataSource": "TAIFEX 官方選擇權日報 NYO", "referenceSource": "TAIFEX 元大台灣50 ETF 選擇權", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "metricLabel": "未平倉量", "dataStatus": "TAIFEX 官方逐履約價商品代碼 NYO；畫面以 T50O 顯示方便分類辨識。", "optionCategory": "指數選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方逐履約價鏈"},
            {"symbol": "^GSPC", "name": "S&P 500 Index Options", "type": "指數選擇權標的", "group": "美國指數選擇權", "region": "美國", "market": "Cboe / SPX", "exchange": "Yahoo Finance / Cboe", "fallbackSymbols": ["SPY", "VOO", "IVV"], "optionCategory": "指數選擇權", "optionSubcategory": "美國", "optionSourceRole": "指數行情代理"},
            {"symbol": "^NDX", "name": "NASDAQ-100 Index Options", "type": "指數選擇權標的", "group": "美國指數選擇權", "region": "美國", "market": "Nasdaq / NDX", "exchange": "Yahoo Finance / Nasdaq", "fallbackSymbols": ["QQQ", "QQQM", "^IXIC"], "optionCategory": "指數選擇權", "optionSubcategory": "美國", "optionSourceRole": "指數行情代理"},
            {"symbol": "^DJI", "name": "Dow Jones Index Options", "type": "指數選擇權標的", "group": "美國指數選擇權", "region": "美國", "market": "DJX / Dow", "exchange": "Yahoo Finance / Cboe", "fallbackSymbols": ["DIA", "^DJI"], "optionCategory": "指數選擇權", "optionSubcategory": "美國", "optionSourceRole": "指數行情代理"},
            {"symbol": "^RUT", "name": "Russell 2000 Index Options", "type": "指數選擇權標的", "group": "美國指數選擇權", "region": "美國", "market": "RUT", "exchange": "Yahoo Finance / Cboe", "fallbackSymbols": ["IWM", "VTWO"], "optionCategory": "指數選擇權", "optionSubcategory": "美國", "optionSourceRole": "指數行情代理"},
            {"symbol": "STO", "name": "台灣股票選擇權彙總", "type": "股票選擇權", "group": "台灣股票選擇權", "region": "台灣", "market": "TAIFEX", "exchange": "TAIFEX", "dataSource": "TAIFEX OpenAPI 股票選擇權標的清單 + 每日行情", "referenceSource": "TAIFEX 股票選擇權契約規格", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "dataProvider": "taifex_option_product_status", "metricLabel": "未平倉量", "v1Status": "connected", "dataStatus": "TAIFEX OpenAPI 即時彙總所有股票選擇權契約之未平倉量與成交量。", "optionCategory": "股票選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方彙總"},
            {"symbol": "2330.TW", "name": "台積電股票選擇權 CDO", "type": "股票選擇權", "group": "台灣股票選擇權", "region": "台灣", "market": "TAIFEX / TWSE", "exchange": "TAIFEX", "dataSource": "TAIFEX 選擇權官方日報 CDO", "referenceSource": "TAIFEX 股票選擇權契約", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "taifexCommodity": "CDO", "optionCategory": "股票選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方逐履約價鏈"},
            {"symbol": "2454.TW", "name": "聯發科股票選擇權 DVO", "type": "股票選擇權", "group": "台灣股票選擇權", "region": "台灣", "market": "TAIFEX / TWSE", "exchange": "TAIFEX", "dataSource": "TAIFEX 選擇權官方日報 DVO", "referenceSource": "TAIFEX 股票選擇權契約", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "taifexCommodity": "DVO", "optionCategory": "股票選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方逐履約價鏈"},
            {"symbol": "2317.TW", "name": "鴻海股票選擇權 DHO", "type": "股票選擇權", "group": "台灣股票選擇權", "region": "台灣", "market": "TAIFEX / TWSE", "exchange": "TAIFEX", "dataSource": "TAIFEX 選擇權官方日報 DHO", "referenceSource": "TAIFEX 股票選擇權契約", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "taifexCommodity": "DHO", "optionCategory": "股票選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方逐履約價鏈"},
            {"symbol": "AAPL", "name": "Apple Options", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國", "optionSourceRole": "個股標的行情代理"},
            {"symbol": "NVDA", "name": "NVIDIA Options", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國", "optionSourceRole": "個股標的行情代理"},
            {"symbol": "TSLA", "name": "Tesla Options", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國", "optionSourceRole": "個股標的行情代理"},
            {"symbol": "TSM", "name": "TSMC ADR Options", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / NYSE", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國", "optionSourceRole": "ADR 標的行情代理"},
            {"symbol": "ETO", "name": "台灣 ETF 選擇權彙總", "type": "ETF 選擇權", "group": "台灣 ETF 選擇權", "region": "台灣", "market": "TAIFEX", "exchange": "TAIFEX", "dataSource": "TAIFEX OpenAPI ETF選擇權標的清單 + 每日行情", "referenceSource": "TAIFEX ETF 選擇權契約規格", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "dataProvider": "taifex_option_product_status", "metricLabel": "未平倉量", "v1Status": "connected", "dataStatus": "TAIFEX OpenAPI 即時彙總所有 ETF 選擇權契約之未平倉量與成交量。", "optionCategory": "ETF 選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方彙總"},
            {"symbol": "0050.TW", "name": "元大台灣50 ETF 選擇權 NYO", "type": "ETF 選擇權", "group": "台灣 ETF 選擇權", "region": "台灣", "market": "TAIFEX / TWSE", "exchange": "TAIFEX", "dataSource": "TAIFEX 選擇權官方日報 NYO", "referenceSource": "TAIFEX 元大台灣50 ETF 選擇權", "sourceUrl": TAIFEX_OPTIONS_DAILY_URL, "taifexCommodity": "T50O", "optionCategory": "ETF 選擇權", "optionSubcategory": "台灣", "optionSourceRole": "官方逐履約價鏈"},
            {"symbol": "0056.TW", "name": "元大高股息 ETF（無掛牌選擇權）", "type": "ETF 期貨參考標的", "group": "台灣 ETF 選擇權", "region": "台灣", "market": "TWSE / TAIFEX", "exchange": "TWSE", "optionCategory": "ETF 選擇權", "optionSubcategory": "台灣", "optionSourceRole": "目前僅有 ETF 期貨", "optionChainUnavailableReason": "TAIFEX 現行清單中 0056 僅有 ETF 期貨，沒有掛牌選擇權，因此沒有真實 Call / Put 履約價可匯入。"},
            {"symbol": "SPY", "name": "SPY Options", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "美國", "optionSourceRole": "ETF 標的行情代理"},
            {"symbol": "QQQ", "name": "QQQ Options", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "美國", "optionSourceRole": "ETF 標的行情代理"},
            {"symbol": "IWM", "name": "IWM Options", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "美國", "optionSourceRole": "ETF 標的行情代理"},
            {"symbol": "GLD", "name": "GLD Options", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "美國", "optionSourceRole": "黃金 ETF 標的行情代理"},
            {"symbol": "SLV", "name": "SLV Options", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "美國", "optionSourceRole": "白銀 ETF 標的行情代理"},
            {"symbol": "TLT", "name": "TLT Options", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "美國", "optionSourceRole": "美債 ETF 標的行情代理"},
            {"symbol": "GC=F", "fallbackSymbols": ["GLD", "IAU", "MGC=F"], "name": "黃金選擇權標的", "type": "商品選擇權標的", "group": "金屬選擇權", "region": "全球 / 其他", "market": "COMEX Gold", "exchange": "COMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "金屬", "optionSourceRole": "期貨行情代理"},
            {"symbol": "SI=F", "fallbackSymbols": ["SLV", "SIL=F"], "name": "白銀選擇權標的", "type": "商品選擇權標的", "group": "金屬選擇權", "region": "全球 / 其他", "market": "COMEX Silver", "exchange": "COMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "金屬", "optionSourceRole": "期貨行情代理"},
            {"symbol": "PL=F", "fallbackSymbols": ["PPLT"], "name": "白金選擇權標的", "type": "商品選擇權標的", "group": "金屬選擇權", "region": "全球 / 其他", "market": "NYMEX Platinum", "exchange": "NYMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "金屬", "optionSourceRole": "期貨行情代理"},
            {"symbol": "PA=F", "fallbackSymbols": ["PALL"], "name": "鈀金選擇權標的", "type": "商品選擇權標的", "group": "金屬選擇權", "region": "全球 / 其他", "market": "NYMEX Palladium", "exchange": "NYMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "金屬", "optionSourceRole": "期貨行情代理"},
            {"symbol": "HG=F", "name": "銅選擇權標的", "type": "商品選擇權標的", "group": "金屬選擇權", "region": "全球 / 其他", "market": "COMEX Copper", "exchange": "COMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "金屬", "optionSourceRole": "期貨行情代理"},
            {"symbol": "CL=F", "name": "WTI 原油選擇權標的", "type": "商品選擇權標的", "group": "能源選擇權", "region": "全球 / 其他", "market": "NYMEX WTI Crude", "exchange": "NYMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "能源", "optionSourceRole": "期貨行情代理"},
            {"symbol": "BZ=F", "name": "Brent 原油選擇權標的", "type": "商品選擇權標的", "group": "能源選擇權", "region": "全球 / 其他", "market": "ICE Brent", "exchange": "ICE / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "能源", "optionSourceRole": "期貨行情代理"},
            {"symbol": "NG=F", "fallbackSymbols": ["UNG", "QG=F", "BOIL"], "name": "天然氣選擇權標的", "type": "商品選擇權標的", "group": "能源選擇權", "region": "全球 / 其他", "market": "NYMEX Natural Gas", "exchange": "NYMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "能源", "optionSourceRole": "期貨行情代理"},
            {"symbol": "RB=F", "fallbackSymbols": ["UGA", "USO"], "name": "汽油選擇權標的", "type": "商品選擇權標的", "group": "能源選擇權", "region": "全球 / 其他", "market": "NYMEX RBOB Gasoline", "exchange": "NYMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "能源", "optionSourceRole": "期貨行情代理"},
            {"symbol": "HO=F", "name": "柴油 / 取暖油選擇權標的", "type": "商品選擇權標的", "group": "能源選擇權", "region": "全球 / 其他", "market": "NYMEX Heating Oil", "exchange": "NYMEX / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "能源", "optionSourceRole": "期貨行情代理"},
            {"symbol": "ZS=F", "name": "黃豆選擇權標的", "type": "商品選擇權標的", "group": "農產品選擇權", "region": "全球 / 其他", "market": "CBOT Soybeans", "exchange": "CBOT / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "農產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "ZC=F", "name": "玉米選擇權標的", "type": "商品選擇權標的", "group": "農產品選擇權", "region": "全球 / 其他", "market": "CBOT Corn", "exchange": "CBOT / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "農產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "ZW=F", "name": "小麥選擇權標的", "type": "商品選擇權標的", "group": "農產品選擇權", "region": "全球 / 其他", "market": "CBOT Wheat", "exchange": "CBOT / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "農產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "KC=F", "fallbackSymbols": ["JO", "DBA"], "name": "咖啡選擇權標的", "type": "商品選擇權標的", "group": "農產品選擇權", "region": "全球 / 其他", "market": "ICE Coffee", "exchange": "ICE / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "農產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "CC=F", "name": "可可選擇權標的", "type": "商品選擇權標的", "group": "農產品選擇權", "region": "全球 / 其他", "market": "ICE Cocoa", "exchange": "ICE / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "農產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "SB=F", "fallbackSymbols": ["CANE", "DBA"], "name": "糖選擇權標的", "type": "商品選擇權標的", "group": "農產品選擇權", "region": "全球 / 其他", "market": "ICE Sugar", "exchange": "ICE / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "農產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "CT=F", "fallbackSymbols": ["DBA"], "name": "棉花選擇權標的", "type": "商品選擇權標的", "group": "農產品選擇權", "region": "全球 / 其他", "market": "ICE Cotton", "exchange": "ICE / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "農產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "LE=F", "name": "活牛選擇權標的", "type": "商品選擇權標的", "group": "畜產品選擇權", "region": "全球 / 其他", "market": "CME Live Cattle", "exchange": "CME / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "畜產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "HE=F", "fallbackSymbols": ["COW", "DBA"], "name": "瘦肉豬選擇權標的", "type": "商品選擇權標的", "group": "畜產品選擇權", "region": "全球 / 其他", "market": "CME Lean Hogs", "exchange": "CME / Yahoo Finance", "optionCategory": "商品選擇權", "optionSubcategory": "畜產品", "optionSourceRole": "期貨行情代理"},
            {"symbol": "TWD=X", "name": "USD/TWD 匯率（無掛牌選擇權鏈）", "type": "外匯參考行情", "group": "外匯選擇權", "region": "全球 / 其他", "market": "USD/TWD", "exchange": "Yahoo Finance FX", "optionCategory": "外匯選擇權", "optionSubcategory": "FX", "optionSourceRole": "匯率參考行情", "optionChainUnavailableReason": "目前公開交易所來源沒有可驗證的 USD/TWD 逐履約價 Call / Put 掛牌鏈；系統不以 EWT 或其他商品冒充。"},
            {"symbol": "JPY=X", "name": "JPY/USD CME FX Options", "type": "外匯期貨選擇權", "group": "外匯選擇權", "region": "全球 / 其他", "market": "CME JPY/USD", "exchange": "CME / Barchart", "optionChainSymbol": "J6=F", "optionCategory": "外匯選擇權", "optionSubcategory": "FX", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "EURUSD=X", "name": "EUR/USD CME FX Options", "type": "外匯期貨選擇權", "group": "外匯選擇權", "region": "全球 / 其他", "market": "CME EUR/USD", "exchange": "CME / Barchart", "optionChainSymbol": "E6=F", "optionCategory": "外匯選擇權", "optionSubcategory": "FX", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "GBPUSD=X", "name": "GBP/USD CME FX Options", "type": "外匯期貨選擇權", "group": "外匯選擇權", "region": "全球 / 其他", "market": "CME GBP/USD", "exchange": "CME / Barchart", "optionChainSymbol": "B6=F", "optionCategory": "外匯選擇權", "optionSubcategory": "FX", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "AUDUSD=X", "name": "AUD/USD CME FX Options", "type": "外匯期貨選擇權", "group": "外匯選擇權", "region": "全球 / 其他", "market": "CME AUD/USD", "exchange": "CME / Barchart", "optionChainSymbol": "A6=F", "optionCategory": "外匯選擇權", "optionSubcategory": "FX", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "CNY=X", "name": "USD/CNY 匯率（目前無活躍公開鏈）", "type": "外匯參考行情", "group": "外匯選擇權", "region": "全球 / 其他", "market": "USD/CNY", "exchange": "Yahoo Finance FX", "optionCategory": "外匯選擇權", "optionSubcategory": "FX", "optionSourceRole": "匯率參考行情", "optionChainUnavailableReason": "CME 人民幣選擇權雖有契約規格，但目前公開來源未回傳可驗證的活躍逐履約價資料；系統不使用過期 CYB 鏈或其他商品替代。"},
            {"symbol": "ZT=F", "name": "美國2年期公債期貨選擇權", "type": "利率期貨選擇權", "group": "利率選擇權", "region": "美國", "market": "CBOT 2-Year T-Note", "exchange": "CBOT / Barchart", "dataSource": "Barchart Futures Options", "optionCategory": "利率選擇權", "optionSubcategory": "美國公債", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "ZF=F", "name": "美國5年期公債期貨選擇權", "type": "利率期貨選擇權", "group": "利率選擇權", "region": "美國", "market": "CBOT 5-Year T-Note", "exchange": "CBOT / Barchart", "dataSource": "Barchart Futures Options", "optionCategory": "利率選擇權", "optionSubcategory": "美國公債", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "ZN=F", "name": "美國10年期公債期貨選擇權", "type": "利率期貨選擇權", "group": "利率選擇權", "region": "美國", "market": "CBOT 10-Year T-Note", "exchange": "CBOT / Barchart", "dataSource": "Barchart Futures Options", "optionCategory": "利率選擇權", "optionSubcategory": "美國公債", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "ZB=F", "name": "美國30年期公債期貨選擇權", "type": "利率期貨選擇權", "group": "利率選擇權", "region": "美國", "market": "CBOT 30-Year T-Bond", "exchange": "CBOT / Barchart", "dataSource": "Barchart Futures Options", "optionCategory": "利率選擇權", "optionSubcategory": "美國公債", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "ZQ=F", "name": "Fed Funds 期貨選擇權", "type": "利率期貨選擇權", "group": "利率選擇權", "region": "美國", "market": "CME Fed Funds", "exchange": "CME / Barchart", "dataSource": "Barchart Futures Options", "optionCategory": "利率選擇權", "optionSubcategory": "Fed Funds", "optionSourceRole": "真實期貨選擇權鏈"},
            {"symbol": "^VIX", "name": "Cboe VIX Options", "type": "波動率指數選擇權", "group": "波動率選擇權", "region": "美國", "market": "Cboe VIX", "exchange": "Cboe", "optionChainSymbol": "_VIX", "optionCategory": "波動率選擇權", "optionSubcategory": "VIX", "optionSourceRole": "真實指數選擇權鏈"},
            {"symbol": "UVIX", "name": "UVIX 2x 波動率 ETF Options", "type": "槓桿波動率 ETF 選擇權", "group": "波動率選擇權", "region": "美國", "market": "Cboe / NYSE Arca", "exchange": "Cboe", "optionCategory": "波動率選擇權", "optionSubcategory": "2x VIX ETF", "optionSourceRole": "真實 ETF 選擇權鏈"},
            {"symbol": "VXX", "name": "VXX 波動率 ETN Options", "type": "波動率 ETN 選擇權", "group": "波動率選擇權", "region": "美國", "market": "Cboe / Nasdaq", "exchange": "Cboe", "optionCategory": "波動率選擇權", "optionSubcategory": "VIX ETN", "optionSourceRole": "真實 ETN 選擇權鏈"},
            {"symbol": "UVXY", "name": "UVXY 波動率 ETF Options", "type": "槓桿波動率 ETF 選擇權", "group": "波動率選擇權", "region": "美國", "market": "Cboe / Nasdaq", "exchange": "Cboe", "optionCategory": "波動率選擇權", "optionSubcategory": "槓桿 VIX ETF", "optionSourceRole": "真實 ETF 選擇權鏈"},
            {"symbol": "SVXY", "name": "SVXY 波動率 ETF Options", "type": "反向波動率 ETF 選擇權", "group": "波動率選擇權", "region": "美國", "market": "Cboe / NYSE Arca", "exchange": "Cboe", "optionCategory": "波動率選擇權", "optionSubcategory": "反向 VIX ETF", "optionSourceRole": "真實 ETF 選擇權鏈"},
            {"symbol": "VIXY", "name": "VIXY 波動率 ETF Options", "type": "波動率 ETF 選擇權", "group": "波動率選擇權", "region": "美國", "market": "NYSE Arca", "exchange": "Cboe / NYSE Arca", "optionCategory": "波動率選擇權", "optionSubcategory": "VIX ETF", "optionSourceRole": "真實 ETF 選擇權鏈"},
            {"symbol": "BTC-USD", "name": "Bitcoin Deribit Options", "type": "加密貨幣選擇權", "group": "加密貨幣選擇權", "region": "全球 / 其他", "market": "Deribit BTC", "exchange": "Deribit", "optionChainSymbol": "DERIBIT_BTC", "optionCategory": "加密貨幣選擇權", "optionSubcategory": "Crypto", "optionSourceRole": "真實加密選擇權鏈"},
            {"symbol": "ETH-USD", "name": "Ethereum Deribit Options", "type": "加密貨幣選擇權", "group": "加密貨幣選擇權", "region": "全球 / 其他", "market": "Deribit ETH", "exchange": "Deribit", "optionChainSymbol": "DERIBIT_ETH", "optionCategory": "加密貨幣選擇權", "optionSubcategory": "Crypto", "optionSourceRole": "真實加密選擇權鏈"},
            {"symbol": "SOL-USD", "name": "SOL Bybit Options", "type": "加密貨幣選擇權", "group": "加密貨幣選擇權", "region": "全球 / 其他", "market": "Bybit SOL", "exchange": "Bybit", "optionChainSymbol": "BYBIT_SOL", "optionCategory": "加密貨幣選擇權", "optionSubcategory": "Crypto", "optionSourceRole": "真實加密選擇權鏈"},
            {"symbol": "XRP-USD", "name": "XRP Bybit Options", "type": "加密貨幣選擇權", "group": "加密貨幣選擇權", "region": "全球 / 其他", "market": "Bybit XRP", "exchange": "Bybit", "optionChainSymbol": "BYBIT_XRP", "optionCategory": "加密貨幣選擇權", "optionSubcategory": "Crypto", "optionSourceRole": "真實加密選擇權鏈"},
            {"symbol": "UNG", "name": "Heating / Cooling Degree Days Proxy", "type": "天氣選擇權標的", "group": "天氣選擇權", "region": "全球 / 其他", "market": "Natural gas weather demand", "exchange": "NYSE Arca / Yahoo Finance", "optionCategory": "天氣選擇權", "optionSubcategory": "HDD / CDD", "optionSourceRole": "天然氣 ETF 代理"},
            {"symbol": "XLU", "fallbackSymbols": ["VPU", "IDU"], "name": "Utilities Weather Demand Proxy", "type": "天氣選擇權標的", "group": "天氣選擇權", "region": "美國", "market": "Utilities demand", "exchange": "NYSE Arca / Yahoo Finance", "optionCategory": "天氣選擇權", "optionSubcategory": "HDD / CDD", "optionSourceRole": "公用事業 ETF 代理"},
            {"symbol": "KRBN", "fallbackSymbols": ["GRN", "KCCA"], "name": "歐盟碳排放權 EUA Options Proxy", "type": "碳權選擇權標的", "group": "碳權選擇權", "region": "歐洲", "market": "Global carbon allowances", "exchange": "NYSE Arca / Yahoo Finance", "optionCategory": "碳權選擇權", "optionSubcategory": "EUA / global carbon", "optionSourceRole": "碳權 ETF 代理"},
            {"symbol": "GRN", "name": "美國碳權 Options Proxy", "type": "碳權選擇權標的", "group": "碳權選擇權", "region": "美國", "market": "Carbon ETN", "exchange": "NYSE Arca / Yahoo Finance", "optionCategory": "碳權選擇權", "optionSubcategory": "US carbon", "optionSourceRole": "碳權 ETN 代理"},
        ],
    },
    "precious-metals": {
        "title": "貴金屬",
        "kicker": "Precious Metals",
        "subtitle": "追蹤黃金、白銀、鉑金與鈀金，觀察避險需求、美元與實質利率影響。",
        "items": [
            {"symbol": "GC=F", "name": "Gold Futures", "type": "期貨"},
            {"symbol": "SI=F", "name": "Silver Futures", "type": "期貨"},
            {"symbol": "PL=F", "name": "Platinum Futures", "type": "期貨"},
            {"symbol": "PA=F", "name": "Palladium Futures", "type": "期貨"},
            {"symbol": "HG=F", "name": "Copper Futures", "type": "期貨"},
            {"symbol": "00635U.TW", "name": "期元大 S&P 黃金", "type": "黃金期貨基金", "group": "台灣貴金屬", "region": "台灣", "market": "台灣", "exchange": "TWSE", "referenceSource": "TWSE / Yahoo Finance 台灣貴金屬行情"},
            {"symbol": "00708L.TW", "name": "期元大 S&P 黃金正2", "type": "黃金槓桿型", "group": "台灣貴金屬", "region": "台灣", "market": "台灣", "exchange": "TWSE", "referenceSource": "TWSE / Yahoo Finance 台灣貴金屬行情"},
            {"symbol": "00674R.TW", "name": "期元大 S&P 黃金反1", "type": "黃金反向型", "group": "台灣貴金屬", "region": "台灣", "market": "台灣", "exchange": "TWSE", "referenceSource": "TWSE / Yahoo Finance 台灣貴金屬行情"},
            {"symbol": "00738U.TW", "name": "期元大 道瓊白銀", "type": "白銀期貨基金", "group": "台灣貴金屬", "region": "台灣", "market": "台灣", "exchange": "TWSE", "referenceSource": "TWSE / Yahoo Finance 台灣貴金屬行情"},
            {"symbol": "GLD", "name": "SPDR Gold Shares", "type": "ETF"},
            {"symbol": "IAU", "name": "iShares Gold Trust", "type": "ETF"},
            {"symbol": "GLDM", "name": "SPDR Gold MiniShares Trust", "type": "ETF"},
            {"symbol": "SLV", "name": "iShares Silver Trust", "type": "ETF"},
            {"symbol": "PPLT", "name": "abrdn Physical Platinum Shares ETF", "type": "ETF"},
            {"symbol": "PALL", "name": "abrdn Physical Palladium Shares ETF", "type": "ETF"},
            {"symbol": "CPER", "name": "United States Copper Index Fund", "type": "ETF"},
            {"symbol": "SGOL", "name": "abrdn Physical Gold Shares ETF", "type": "ETF"},
            {"symbol": "BAR", "name": "GraniteShares Gold Trust", "type": "ETF"},
            {"symbol": "AAAU", "name": "Goldman Sachs Physical Gold ETF", "type": "ETF"},
            {"symbol": "SIVR", "name": "abrdn Physical Silver Shares ETF", "type": "ETF"},
            {"symbol": "PSLV", "name": "Sprott Physical Silver Trust", "type": "ETF"},
            {"symbol": "PLTM", "name": "GraniteShares Platinum Trust", "type": "ETF"},
            {"symbol": "GDX", "name": "VanEck Gold Miners ETF", "type": "礦業 ETF"},
            {"symbol": "GDXJ", "name": "VanEck Junior Gold Miners ETF", "type": "礦業 ETF"},
            {"symbol": "SIL", "name": "Global X Silver Miners ETF", "type": "礦業 ETF"},
            {"symbol": "SILJ", "name": "Amplify Junior Silver Miners ETF", "type": "礦業 ETF"},
            {"symbol": "RING", "name": "iShares MSCI Global Gold Miners ETF", "type": "礦業 ETF"},
            {"symbol": "COPX", "name": "Global X Copper Miners ETF", "type": "礦業 ETF"},
        ],
    },
    "bonds": {
        "title": "債券",
        "kicker": "Bonds",
        "subtitle": "以美債殖利率與債券 ETF 觀察利率預期、避險資金與股債輪動。",
        "items": [
            {"symbol": "^IRX", "name": "美國 13 週 Treasury Bill", "type": "殖利率"},
            {"symbol": "US2Y", "name": "美國 2 年期公債殖利率", "type": "殖利率", "region": "美國", "market": "美國公債", "exchange": "U.S. Treasury", "dataSource": "U.S. Treasury Daily Treasury Par Yield Curve", "referenceSource": "U.S. Treasury Daily Treasury Par Yield Curve", "sourceUrl": US_TREASURY_YIELD_CURVE_CSV_URL, "dataProvider": "us_treasury_yield_curve", "treasuryMaturity": "2 Yr", "metricLabel": "官方殖利率"},
            {"symbol": "^FVX", "name": "美國 5 年期殖利率", "type": "殖利率"},
            {"symbol": "^TNX", "name": "美國 10 年期殖利率", "type": "殖利率"},
            {"symbol": "^TYX", "name": "美國 30 年期殖利率", "type": "殖利率"},
            {"symbol": "TW10Y", "name": "台灣 10 年期公債殖利率", "type": "殖利率", "region": "台灣", "market": "台灣公債", "exchange": "OTC interbank quote", "dataSource": "Trading Economics Taiwan 10-Year Government Bond Yield", "referenceSource": "Trading Economics / over-the-counter interbank yield quotes", "sourceUrl": TRADING_ECONOMICS_TAIWAN_10Y_URL, "dataProvider": "trading_economics_taiwan_10y", "metricLabel": "10Y 殖利率", "fallbackObservation": {"date": "2026-07-03", "value": 1.71, "change": 0.01, "source": "Trading Economics snapshot fallback"}},
            {"symbol": "DE10Y", "name": "德國 10 年期公債殖利率", "type": "殖利率", "region": "歐洲", "market": "德國公債", "exchange": "FRED / OECD", "dataSource": "FRED OECD Long-Term Government Bond Yields", "referenceSource": "FRED IRLTLT01DEM156N", "sourceUrl": f"{FRED_SERIES_BASE}/IRLTLT01DEM156N", "dataProvider": "fred_latest_observation", "fredSeriesId": "IRLTLT01DEM156N", "metricLabel": "10Y 殖利率", "fallbackObservation": {"date": "2026-05-01", "value": 3.05, "source": "FRED snapshot fallback"}},
            {"symbol": "JP10Y", "name": "日本 10 年期公債殖利率", "type": "殖利率", "region": "亞洲", "market": "日本公債", "exchange": "FRED / OECD", "dataSource": "FRED OECD Long-Term Government Bond Yields", "referenceSource": "FRED IRLTLT01JPM156N", "sourceUrl": f"{FRED_SERIES_BASE}/IRLTLT01JPM156N", "dataProvider": "fred_latest_observation", "fredSeriesId": "IRLTLT01JPM156N", "metricLabel": "10Y 殖利率", "fallbackObservation": {"date": "2026-05-01", "value": 2.65, "source": "FRED snapshot fallback"}},
            {"symbol": "MOODY-AAA", "name": "Moody's Aaa 公司債殖利率", "type": "信用殖利率", "region": "美國", "market": "美國公司債", "exchange": "FRED / Moody's", "dataSource": "FRED Moody's Seasoned Aaa Corporate Bond Yield", "referenceSource": "FRED DAAA", "sourceUrl": f"{FRED_SERIES_BASE}/DAAA", "dataProvider": "fred_latest_observation", "fredSeriesId": "DAAA", "metricLabel": "Aaa 殖利率", "fallbackObservation": {"date": "2026-07-01", "value": 5.60, "source": "FRED snapshot fallback"}},
            {"symbol": "MOODY-BAA", "name": "Moody's Baa 公司債殖利率", "type": "信用殖利率", "region": "美國", "market": "美國公司債", "exchange": "FRED / Moody's", "dataSource": "FRED Moody's Seasoned Baa Corporate Bond Yield", "referenceSource": "FRED DBAA", "sourceUrl": f"{FRED_SERIES_BASE}/DBAA", "dataProvider": "fred_latest_observation", "fredSeriesId": "DBAA", "metricLabel": "Baa 殖利率", "fallbackObservation": {"date": "2026-07-01", "value": 6.02, "source": "FRED snapshot fallback"}},
            {"symbol": "FEDFUNDS", "name": "Federal Funds Effective Rate", "type": "政策利率", "region": "美國", "market": "Fed / FOMC", "exchange": "FRED / Federal Reserve", "dataSource": "FRED Federal Funds Effective Rate", "referenceSource": "FRED FEDFUNDS", "sourceUrl": f"{FRED_SERIES_BASE}/FEDFUNDS", "dataProvider": "fred_latest_observation", "fredSeriesId": "FEDFUNDS", "metricLabel": "Fed Funds", "fallbackObservation": {"date": "2026-06-01", "value": 3.63, "source": "FRED snapshot fallback"}},
            {"symbol": "ECBDFR", "name": "ECB Deposit Facility Rate", "type": "政策利率", "region": "歐洲", "market": "ECB", "exchange": "FRED / ECB", "dataSource": "FRED ECB Deposit Facility Rate", "referenceSource": "FRED ECBDFR", "sourceUrl": f"{FRED_SERIES_BASE}/ECBDFR", "dataProvider": "fred_latest_observation", "fredSeriesId": "ECBDFR", "metricLabel": "ECB Deposit Rate", "fallbackObservation": {"date": "2026-07-03", "value": 2.25, "source": "FRED snapshot fallback"}},
            {"symbol": "IRSTCI01JPM156N", "name": "日本隔夜拆款利率", "type": "政策利率代理", "region": "亞洲", "market": "BOJ / Japan", "exchange": "FRED / OECD", "dataSource": "FRED OECD Japan Call Money / Interbank Rate", "referenceSource": "FRED IRSTCI01JPM156N", "sourceUrl": f"{FRED_SERIES_BASE}/IRSTCI01JPM156N", "dataProvider": "fred_latest_observation", "fredSeriesId": "IRSTCI01JPM156N", "metricLabel": "BOJ rate proxy", "fallbackObservation": {"date": "2026-05-01", "value": 0.727, "source": "FRED snapshot fallback"}},
            {"symbol": "CPIAUCSL", "name": "美國 CPI 指數", "type": "通膨指標", "region": "美國", "market": "Inflation", "exchange": "FRED / BLS", "dataSource": "FRED Consumer Price Index", "referenceSource": "FRED CPIAUCSL", "sourceUrl": f"{FRED_SERIES_BASE}/CPIAUCSL", "dataProvider": "fred_latest_observation", "fredSeriesId": "CPIAUCSL", "metricLabel": "CPI Index", "fallbackObservation": {"date": "2026-05-01", "value": 333.979, "source": "FRED snapshot fallback"}},
            {"symbol": "PCEPI", "name": "美國 PCE 物價指數", "type": "通膨指標", "region": "美國", "market": "Inflation", "exchange": "FRED / BEA", "dataSource": "FRED PCE Price Index", "referenceSource": "FRED PCEPI", "sourceUrl": f"{FRED_SERIES_BASE}/PCEPI", "dataProvider": "fred_latest_observation", "fredSeriesId": "PCEPI", "metricLabel": "PCE Price Index", "fallbackObservation": {"date": "2026-05-01", "value": 131.527, "source": "FRED snapshot fallback"}},
            {"symbol": "PAYEMS", "name": "美國非農就業人數", "type": "就業指標", "region": "美國", "market": "Labor", "exchange": "FRED / BLS", "dataSource": "FRED Total Nonfarm Payrolls", "referenceSource": "FRED PAYEMS", "sourceUrl": f"{FRED_SERIES_BASE}/PAYEMS", "dataProvider": "fred_latest_observation", "fredSeriesId": "PAYEMS", "metricLabel": "Nonfarm Payrolls", "fallbackObservation": {"date": "2026-06-01", "value": 158984, "source": "FRED snapshot fallback"}},
            {"symbol": "UNRATE", "name": "美國失業率", "type": "就業指標", "region": "美國", "market": "Labor", "exchange": "FRED / BLS", "dataSource": "FRED Unemployment Rate", "referenceSource": "FRED UNRATE", "sourceUrl": f"{FRED_SERIES_BASE}/UNRATE", "dataProvider": "fred_latest_observation", "fredSeriesId": "UNRATE", "metricLabel": "Unemployment Rate", "fallbackObservation": {"date": "2026-06-01", "value": 4.2, "source": "FRED snapshot fallback"}},
            {"symbol": "EURO-HICP", "name": "歐元區 HICP 指數", "type": "通膨指標", "region": "歐洲", "market": "Inflation", "exchange": "FRED / Eurostat", "dataSource": "FRED Euro Area HICP", "referenceSource": "FRED CP0000EZ19M086NEST", "sourceUrl": f"{FRED_SERIES_BASE}/CP0000EZ19M086NEST", "dataProvider": "fred_latest_observation", "fredSeriesId": "CP0000EZ19M086NEST", "metricLabel": "Euro HICP", "fallbackObservation": {"date": "2026-05-01", "value": 103.10, "source": "FRED snapshot fallback"}},
            {"symbol": "EURO-UNRATE", "name": "歐元區失業率", "type": "就業指標", "region": "歐洲", "market": "Labor", "exchange": "FRED / OECD", "dataSource": "FRED Euro Area Harmonised Unemployment", "referenceSource": "FRED LRHUTTTTEZM156S", "sourceUrl": f"{FRED_SERIES_BASE}/LRHUTTTTEZM156S", "dataProvider": "fred_latest_observation", "fredSeriesId": "LRHUTTTTEZM156S", "metricLabel": "Euro unemployment", "fallbackObservation": {"date": "2023-01-01", "value": 6.7, "source": "FRED snapshot fallback"}},
            {"symbol": "JPNCPIALLMINMEI", "name": "日本 CPI 指數", "type": "通膨指標", "region": "亞洲", "market": "Inflation", "exchange": "FRED / OECD", "dataSource": "FRED Japan Consumer Price Index", "referenceSource": "FRED JPNCPIALLMINMEI", "sourceUrl": f"{FRED_SERIES_BASE}/JPNCPIALLMINMEI", "dataProvider": "fred_latest_observation", "fredSeriesId": "JPNCPIALLMINMEI", "metricLabel": "Japan CPI", "fallbackObservation": {"date": "2021-06-01", "value": 101.298, "source": "FRED snapshot fallback"}},
            {"symbol": "LRUNTTTTJPM156S", "name": "日本失業率", "type": "就業指標", "region": "亞洲", "market": "Labor", "exchange": "FRED / OECD", "dataSource": "FRED Japan Unemployment Rate", "referenceSource": "FRED LRUNTTTTJPM156S", "sourceUrl": f"{FRED_SERIES_BASE}/LRUNTTTTJPM156S", "dataProvider": "fred_latest_observation", "fredSeriesId": "LRUNTTTTJPM156S", "metricLabel": "Japan unemployment", "fallbackObservation": {"date": "2026-04-01", "value": 2.5, "source": "FRED snapshot fallback"}},
            {"symbol": "DX-Y.NYB", "name": "美元指數 DXY", "type": "總體指標", "region": "美國", "market": "美元", "exchange": "ICE / Yahoo Finance"},
            {"symbol": "^VIX", "name": "CBOE VIX 指數", "type": "市場風險指標", "region": "美國", "market": "波動率", "exchange": "Cboe / Yahoo Finance"},
            {"symbol": "00679B.TWO", "name": "元大美債20年 ETF", "type": "台灣債券 ETF", "region": "台灣", "market": "台灣", "exchange": "TPEx", "referenceSource": "TPEx / Yahoo Finance 台灣 ETF 行情"},
            {"symbol": "00687B.TWO", "name": "國泰 20 年美債 ETF", "type": "台灣債券 ETF", "region": "台灣", "market": "台灣", "exchange": "TPEx", "referenceSource": "TPEx / Yahoo Finance 台灣 ETF 行情"},
            {"symbol": "00696B.TWO", "name": "富邦美債20年 ETF", "type": "台灣債券 ETF", "region": "台灣", "market": "台灣", "exchange": "TPEx", "referenceSource": "TPEx / Yahoo Finance 台灣 ETF 行情"},
            {"symbol": "00697B.TWO", "name": "元大美債7-10 ETF", "type": "台灣債券 ETF", "region": "台灣", "market": "台灣", "exchange": "TPEx", "referenceSource": "TPEx / Yahoo Finance 台灣 ETF 行情"},
            {"symbol": "00795B.TWO", "name": "中信美國公債 20 年 ETF", "type": "台灣債券 ETF", "region": "台灣", "market": "台灣", "exchange": "TPEx", "referenceSource": "TPEx / Yahoo Finance 台灣 ETF 行情"},
            {"symbol": "00857B.TWO", "name": "永豐20年美公債 ETF", "type": "台灣債券 ETF", "region": "台灣", "market": "台灣", "exchange": "TPEx", "referenceSource": "TPEx / Yahoo Finance 台灣 ETF 行情"},
            {"symbol": "00931B.TWO", "name": "統一美債20年 ETF", "type": "台灣債券 ETF", "region": "台灣", "market": "台灣", "exchange": "TPEx", "referenceSource": "TPEx / Yahoo Finance 台灣 ETF 行情"},
            {"symbol": "SHY", "name": "1-3 Year Treasury ETF", "type": "債券 ETF"},
            {"symbol": "VGSH", "name": "Vanguard Short-Term Treasury ETF", "type": "債券 ETF"},
            {"symbol": "IEF", "name": "7-10 Year Treasury ETF", "type": "債券 ETF"},
            {"symbol": "VGIT", "name": "Vanguard Intermediate-Term Treasury ETF", "type": "債券 ETF"},
            {"symbol": "TLT", "name": "20+ Year Treasury ETF", "type": "債券 ETF"},
            {"symbol": "VGLT", "name": "Vanguard Long-Term Treasury ETF", "type": "債券 ETF"},
            {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "type": "債券 ETF"},
            {"symbol": "AGG", "name": "iShares Core U.S. Aggregate Bond ETF", "type": "債券 ETF"},
            {"symbol": "BNDX", "name": "Vanguard Total International Bond ETF", "type": "全球債券 ETF", "region": "全球 / 其他", "market": "全球非美債券", "exchange": "Nasdaq ETF"},
            {"symbol": "IAGG", "name": "iShares International Aggregate Bond ETF", "type": "全球債券 ETF", "region": "全球 / 其他", "market": "國際投資級債", "exchange": "NYSE Arca"},
            {"symbol": "EMB", "name": "iShares J.P. Morgan USD Emerging Markets Bond ETF", "type": "新興市場債 ETF", "region": "全球 / 其他", "market": "新興市場", "exchange": "Nasdaq ETF"},
            {"symbol": "LQD", "name": "Investment Grade Corporate Bond ETF", "type": "信用債 ETF"},
            {"symbol": "HYG", "name": "High Yield Corporate Bond ETF", "type": "信用債 ETF"},
            {"symbol": "JNK", "name": "SPDR Bloomberg High Yield Bond ETF", "type": "信用債 ETF"},
            {"symbol": "TIP", "name": "iShares TIPS Bond ETF", "type": "抗通膨債 ETF"},
            {"symbol": "MUB", "name": "iShares National Muni Bond ETF", "type": "市政債 ETF"},
        ],
    },
}

ASSET_CATEGORY_SOURCE_INFO = {
    "us-stocks": {
        "primary": "Yahoo Finance 線上行情 / Yahoo Finance News",
        "reference": "Nasdaq Trader Symbol Directory / NYSE Listings Directory",
        "referenceUrl": "https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs",
    },
    "futures": {
        "primary": "Yahoo Finance 歷史行情 / TAIFEX 官方期貨日報",
        "reference": "TAIFEX / CME Group / ICE 合約目錄",
        "referenceUrl": "https://www.cmegroup.com/markets.html",
    },
    "options": {
        "primary": "Yahoo Finance 指數與標的行情 / TAIFEX 官方選擇權日報",
        "reference": "TAIFEX 選擇權每日交易行情 / Put Call Ratio / Cboe 波動率指數 / OCC 合約規格",
        "referenceUrl": TAIFEX_OPTIONS_DAILY_URL,
    },
    "precious-metals": {
        "primary": "Yahoo Finance 期貨、現貨與 ETF 行情",
        "reference": "LBMA / COMEX 貴金屬參考資料",
        "referenceUrl": "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
    },
    "bonds": {
        "primary": "Yahoo Finance 殖利率、總體指標與債券 ETF 行情",
        "reference": "U.S. Treasury Daily Treasury Par Yield Curve / FRED",
        "referenceUrl": US_TREASURY_YIELD_CURVE_CSV_URL,
    },
}

GLOBAL_MACRO_ASSET_SCHEMA = {
    "sources": [
        {"name": "Bloomberg / LSEG Refinitiv / FactSet", "role": "機構級行情、基本資料與跨資產資料庫"},
        {"name": "Morningstar / S&P Global Market Intelligence", "role": "基金、ETF、債券與信用資料補充"},
        {"name": "TAIFEX / CME / ICE / Eurex / SGX", "role": "期貨與選擇權交易所官方合約與未平倉資料"},
        {"name": "U.S. Treasury / FRED", "role": "美債殖利率曲線、利率與總體時間序列"},
        {"name": "LBMA / COMEX", "role": "貴金屬價格、期貨與參考資料"},
        {"name": "OCC / Cboe", "role": "美股選擇權鏈、波動率與風險指數"},
    ],
    "tables": [
        {"name": "futures_master", "label": "期貨商品主檔"},
        {"name": "options_product", "label": "選擇權商品主檔"},
        {"name": "options_contract", "label": "選擇權契約與到期月份"},
        {"name": "options_quote", "label": "選擇權 Call/Put 報價"},
        {"name": "options_chain", "label": "選擇權鏈與未平倉"},
        {"name": "open_interest", "label": "未平倉與 PCR 分析"},
        {"name": "ai_analysis_report", "label": "AI 盤勢與風險報告"},
        {"name": "bond_master", "label": "債券主檔"},
        {"name": "bond_yield_history", "label": "債券殖利率歷史"},
        {"name": "rating_history", "label": "信評歷史"},
        {"name": "macro_indicator", "label": "總體指標"},
        {"name": "fx_rates", "label": "外匯匯率"},
    ],
    "dashboardSignals": [
        "Yield Curve",
        "Credit Spread",
        "DXY",
        "VIX",
        "Gold / Silver Ratio",
        "Global Futures",
        "Central Bank Rates",
    ],
    "automation": "API 取數、ETL 清洗、資料庫寫入、排程更新與異常監控",
}

ASSET_REGION_ORDER = ["台灣", "美國", "歐洲", "亞洲", "全球 / 其他"]


US_SECTOR_STOCK_GROUPS = {
    "^GSPC": {
        "label": "標普500",
        "stocks": [
            {"symbol": "AAPL", "name": "Apple", "type": "標普500權重股"},
            {"symbol": "MSFT", "name": "Microsoft", "type": "標普500權重股"},
            {"symbol": "NVDA", "name": "NVIDIA", "type": "標普500權重股"},
            {"symbol": "AMZN", "name": "Amazon", "type": "標普500權重股"},
            {"symbol": "META", "name": "Meta Platforms", "type": "標普500權重股"},
            {"symbol": "GOOGL", "name": "Alphabet", "type": "標普500權重股"},
            {"symbol": "AVGO", "name": "Broadcom", "type": "標普500權重股"},
            {"symbol": "JPM", "name": "JPMorgan Chase", "type": "標普500權重股"},
        ],
    },
    "^DJI": {
        "label": "道瓊工業",
        "stocks": [
            {"symbol": "UNH", "name": "UnitedHealth", "type": "道瓊成分股"},
            {"symbol": "GS", "name": "Goldman Sachs", "type": "道瓊成分股"},
            {"symbol": "MSFT", "name": "Microsoft", "type": "道瓊成分股"},
            {"symbol": "HD", "name": "Home Depot", "type": "道瓊成分股"},
            {"symbol": "CAT", "name": "Caterpillar", "type": "道瓊成分股"},
            {"symbol": "MCD", "name": "McDonald's", "type": "道瓊成分股"},
            {"symbol": "AMGN", "name": "Amgen", "type": "道瓊成分股"},
            {"symbol": "V", "name": "Visa", "type": "道瓊成分股"},
        ],
    },
    "^IXIC": {
        "label": "那斯達克綜合",
        "stocks": [
            {"symbol": "AAPL", "name": "Apple", "type": "那斯達克代表股"},
            {"symbol": "MSFT", "name": "Microsoft", "type": "那斯達克代表股"},
            {"symbol": "NVDA", "name": "NVIDIA", "type": "那斯達克代表股"},
            {"symbol": "AMZN", "name": "Amazon", "type": "那斯達克代表股"},
            {"symbol": "META", "name": "Meta Platforms", "type": "那斯達克代表股"},
            {"symbol": "AVGO", "name": "Broadcom", "type": "那斯達克代表股"},
            {"symbol": "TSLA", "name": "Tesla", "type": "那斯達克代表股"},
            {"symbol": "NFLX", "name": "Netflix", "type": "那斯達克代表股"},
        ],
    },
    "^RUT": {
        "label": "羅素2000",
        "stocks": [
            {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "type": "小型股ETF"},
            {"symbol": "SMCI", "name": "Super Micro Computer", "type": "小型成長"},
            {"symbol": "CELH", "name": "Celsius", "type": "小型消費"},
            {"symbol": "MARA", "name": "MARA Holdings", "type": "加密題材"},
            {"symbol": "RIOT", "name": "Riot Platforms", "type": "加密題材"},
            {"symbol": "SAVA", "name": "Cassava Sciences", "type": "生技"},
            {"symbol": "AAOI", "name": "Applied Optoelectronics", "type": "通訊設備"},
            {"symbol": "HIMS", "name": "Hims & Hers", "type": "醫療平台"},
        ],
    },
    "^SP500-45": {
        "label": "科技",
        "stocks": [
            {"symbol": "AAPL", "name": "Apple", "type": "科技硬體"},
            {"symbol": "MSFT", "name": "Microsoft", "type": "雲端軟體"},
            {"symbol": "NVDA", "name": "NVIDIA", "type": "AI 晶片"},
            {"symbol": "AVGO", "name": "Broadcom", "type": "半導體"},
            {"symbol": "ORCL", "name": "Oracle", "type": "企業軟體"},
            {"symbol": "CRM", "name": "Salesforce", "type": "雲端軟體"},
            {"symbol": "ADBE", "name": "Adobe", "type": "創意軟體"},
            {"symbol": "AMD", "name": "AMD", "type": "半導體"},
        ],
    },
    "^SP500-40": {
        "label": "金融",
        "stocks": [
            {"symbol": "JPM", "name": "JPMorgan Chase", "type": "銀行"},
            {"symbol": "BAC", "name": "Bank of America", "type": "銀行"},
            {"symbol": "WFC", "name": "Wells Fargo", "type": "銀行"},
            {"symbol": "GS", "name": "Goldman Sachs", "type": "投資銀行"},
            {"symbol": "MS", "name": "Morgan Stanley", "type": "投資銀行"},
            {"symbol": "BLK", "name": "BlackRock", "type": "資產管理"},
            {"symbol": "AXP", "name": "American Express", "type": "支付金融"},
            {"symbol": "C", "name": "Citigroup", "type": "銀行"},
        ],
    },
    "^SP500-35": {
        "label": "醫療保健",
        "stocks": [
            {"symbol": "LLY", "name": "Eli Lilly", "type": "製藥"},
            {"symbol": "UNH", "name": "UnitedHealth", "type": "醫療保險"},
            {"symbol": "JNJ", "name": "Johnson & Johnson", "type": "醫療產品"},
            {"symbol": "MRK", "name": "Merck", "type": "製藥"},
            {"symbol": "ABBV", "name": "AbbVie", "type": "製藥"},
            {"symbol": "TMO", "name": "Thermo Fisher", "type": "醫療設備"},
            {"symbol": "ABT", "name": "Abbott", "type": "醫療設備"},
            {"symbol": "PFE", "name": "Pfizer", "type": "製藥"},
        ],
    },
    "^SP500-25": {
        "label": "非必需消費",
        "stocks": [
            {"symbol": "AMZN", "name": "Amazon", "type": "電商"},
            {"symbol": "TSLA", "name": "Tesla", "type": "電動車"},
            {"symbol": "HD", "name": "Home Depot", "type": "零售"},
            {"symbol": "MCD", "name": "McDonald's", "type": "餐飲"},
            {"symbol": "NKE", "name": "Nike", "type": "品牌消費"},
            {"symbol": "SBUX", "name": "Starbucks", "type": "餐飲"},
            {"symbol": "LOW", "name": "Lowe's", "type": "零售"},
            {"symbol": "BKNG", "name": "Booking Holdings", "type": "旅遊平台"},
        ],
    },
    "^SP500-50": {
        "label": "通訊服務",
        "stocks": [
            {"symbol": "GOOGL", "name": "Alphabet", "type": "網路平台"},
            {"symbol": "META", "name": "Meta Platforms", "type": "社群平台"},
            {"symbol": "NFLX", "name": "Netflix", "type": "串流媒體"},
            {"symbol": "DIS", "name": "Disney", "type": "娛樂媒體"},
            {"symbol": "TMUS", "name": "T-Mobile US", "type": "電信"},
            {"symbol": "VZ", "name": "Verizon", "type": "電信"},
            {"symbol": "T", "name": "AT&T", "type": "電信"},
            {"symbol": "CMCSA", "name": "Comcast", "type": "媒體電信"},
        ],
    },
    "^SP500-20": {
        "label": "工業",
        "stocks": [
            {"symbol": "GE", "name": "GE Aerospace", "type": "航太工業"},
            {"symbol": "CAT", "name": "Caterpillar", "type": "重工機械"},
            {"symbol": "RTX", "name": "RTX", "type": "航太國防"},
            {"symbol": "HON", "name": "Honeywell", "type": "工業科技"},
            {"symbol": "UNP", "name": "Union Pacific", "type": "鐵路運輸"},
            {"symbol": "BA", "name": "Boeing", "type": "航太"},
            {"symbol": "UPS", "name": "UPS", "type": "物流"},
            {"symbol": "DE", "name": "Deere", "type": "農機"},
        ],
    },
    "^SP500-30": {
        "label": "必需消費",
        "stocks": [
            {"symbol": "WMT", "name": "Walmart", "type": "零售"},
            {"symbol": "COST", "name": "Costco", "type": "倉儲零售"},
            {"symbol": "PG", "name": "Procter & Gamble", "type": "民生用品"},
            {"symbol": "KO", "name": "Coca-Cola", "type": "飲料"},
            {"symbol": "PEP", "name": "PepsiCo", "type": "飲料食品"},
            {"symbol": "PM", "name": "Philip Morris", "type": "菸草"},
            {"symbol": "MDLZ", "name": "Mondelez", "type": "食品"},
            {"symbol": "CL", "name": "Colgate-Palmolive", "type": "民生用品"},
        ],
    },
    "^SP500-10": {
        "label": "能源",
        "stocks": [
            {"symbol": "XOM", "name": "Exxon Mobil", "type": "石油天然氣"},
            {"symbol": "CVX", "name": "Chevron", "type": "石油天然氣"},
            {"symbol": "COP", "name": "ConocoPhillips", "type": "能源探勘"},
            {"symbol": "SLB", "name": "Schlumberger", "type": "油服"},
            {"symbol": "EOG", "name": "EOG Resources", "type": "能源探勘"},
            {"symbol": "MPC", "name": "Marathon Petroleum", "type": "煉油"},
            {"symbol": "PSX", "name": "Phillips 66", "type": "煉油"},
            {"symbol": "OXY", "name": "Occidental Petroleum", "type": "能源探勘"},
        ],
    },
    "^SP500-15": {
        "label": "原物料",
        "stocks": [
            {"symbol": "LIN", "name": "Linde", "type": "工業氣體"},
            {"symbol": "SHW", "name": "Sherwin-Williams", "type": "化工塗料"},
            {"symbol": "FCX", "name": "Freeport-McMoRan", "type": "銅礦"},
            {"symbol": "APD", "name": "Air Products", "type": "工業氣體"},
            {"symbol": "ECL", "name": "Ecolab", "type": "化工服務"},
            {"symbol": "NEM", "name": "Newmont", "type": "黃金礦業"},
            {"symbol": "DOW", "name": "Dow", "type": "化學"},
            {"symbol": "DD", "name": "DuPont", "type": "材料科技"},
        ],
    },
    "^SP500-55": {
        "label": "公用事業",
        "stocks": [
            {"symbol": "NEE", "name": "NextEra Energy", "type": "電力"},
            {"symbol": "SO", "name": "Southern", "type": "電力"},
            {"symbol": "DUK", "name": "Duke Energy", "type": "電力"},
            {"symbol": "AEP", "name": "American Electric Power", "type": "電力"},
            {"symbol": "SRE", "name": "Sempra", "type": "公用事業"},
            {"symbol": "D", "name": "Dominion Energy", "type": "電力"},
            {"symbol": "EXC", "name": "Exelon", "type": "電力"},
            {"symbol": "XEL", "name": "Xcel Energy", "type": "電力"},
        ],
    },
    "^SP500-60": {
        "label": "不動產",
        "stocks": [
            {"symbol": "PLD", "name": "Prologis", "type": "工業 REIT"},
            {"symbol": "AMT", "name": "American Tower", "type": "通訊 REIT"},
            {"symbol": "EQIX", "name": "Equinix", "type": "資料中心 REIT"},
            {"symbol": "WELL", "name": "Welltower", "type": "醫療 REIT"},
            {"symbol": "SPG", "name": "Simon Property", "type": "商場 REIT"},
            {"symbol": "O", "name": "Realty Income", "type": "零售 REIT"},
            {"symbol": "DLR", "name": "Digital Realty", "type": "資料中心 REIT"},
            {"symbol": "PSA", "name": "Public Storage", "type": "倉儲 REIT"},
        ],
    },
    "^SOX": {
        "label": "半導體",
        "stocks": [
            {"symbol": "NVDA", "name": "NVIDIA", "type": "AI 晶片"},
            {"symbol": "AMD", "name": "AMD", "type": "CPU/GPU"},
            {"symbol": "AVGO", "name": "Broadcom", "type": "通訊晶片"},
            {"symbol": "TSM", "name": "Taiwan Semiconductor", "type": "晶圓代工"},
            {"symbol": "ASML", "name": "ASML", "type": "半導體設備"},
            {"symbol": "AMAT", "name": "Applied Materials", "type": "半導體設備"},
            {"symbol": "MU", "name": "Micron", "type": "記憶體"},
            {"symbol": "QCOM", "name": "Qualcomm", "type": "行動晶片"},
        ],
    },
}

US_SECTOR_STOCK_GROUPS["^DJUSTC"] = US_SECTOR_STOCK_GROUPS["^SP500-45"]
US_SECTOR_STOCK_GROUPS["^DJUSFN"] = US_SECTOR_STOCK_GROUPS["^SP500-40"]
US_SECTOR_STOCK_GROUPS["^DJUSHC"] = US_SECTOR_STOCK_GROUPS["^SP500-35"]
US_SECTOR_STOCK_GROUPS["^DJUSEN"] = US_SECTOR_STOCK_GROUPS["^SP500-10"]
US_SECTOR_STOCK_GROUPS["^DJUSRE"] = US_SECTOR_STOCK_GROUPS["^SP500-60"]
US_MARKET_SEARCH_UNIVERSE = [
    *GLOBAL_MARKET_CATEGORIES["us-stocks"]["items"],
    {"symbol": "BRK-B", "name": "Berkshire Hathaway", "type": "控股公司", "group": "美股個股"},
    {"symbol": "LLY", "name": "Eli Lilly", "type": "醫療保健", "group": "美股個股"},
    {"symbol": "UNH", "name": "UnitedHealth Group", "type": "醫療保健", "group": "美股個股"},
    {"symbol": "V", "name": "Visa", "type": "金融科技", "group": "美股個股"},
    {"symbol": "MA", "name": "Mastercard", "type": "金融科技", "group": "美股個股"},
    {"symbol": "WMT", "name": "Walmart", "type": "消費零售", "group": "美股個股"},
    {"symbol": "COST", "name": "Costco Wholesale", "type": "消費零售", "group": "美股個股"},
    {"symbol": "HD", "name": "Home Depot", "type": "消費零售", "group": "美股個股"},
    {"symbol": "MCD", "name": "McDonald's", "type": "消費服務", "group": "美股個股"},
    {"symbol": "NFLX", "name": "Netflix", "type": "串流媒體", "group": "美股個股"},
    {"symbol": "CRM", "name": "Salesforce", "type": "企業軟體", "group": "美股個股"},
    {"symbol": "ORCL", "name": "Oracle", "type": "企業軟體", "group": "美股個股"},
    {"symbol": "ADBE", "name": "Adobe", "type": "企業軟體", "group": "美股個股"},
    {"symbol": "NOW", "name": "ServiceNow", "type": "企業軟體", "group": "美股個股"},
    {"symbol": "INTC", "name": "Intel", "type": "半導體", "group": "美股個股"},
    {"symbol": "QCOM", "name": "Qualcomm", "type": "半導體", "group": "美股個股"},
    {"symbol": "MU", "name": "Micron Technology", "type": "記憶體", "group": "美股個股"},
    {"symbol": "TXN", "name": "Texas Instruments", "type": "類比半導體", "group": "美股個股"},
    {"symbol": "AMAT", "name": "Applied Materials", "type": "半導體設備", "group": "美股個股"},
    {"symbol": "LRCX", "name": "Lam Research", "type": "半導體設備", "group": "美股個股"},
    {"symbol": "ASML", "name": "ASML Holding", "type": "半導體設備", "group": "美股個股"},
    {"symbol": "TSM", "name": "Taiwan Semiconductor ADR", "type": "半導體 ADR", "group": "美股個股"},
    {"symbol": "BABA", "name": "Alibaba ADR", "type": "中概 ADR", "group": "美股個股"},
    {"symbol": "NIO", "name": "NIO", "type": "電動車", "group": "美股個股"},
    {"symbol": "PLTR", "name": "Palantir", "type": "AI 軟體", "group": "美股個股"},
    {"symbol": "SNOW", "name": "Snowflake", "type": "雲端資料", "group": "美股個股"},
    {"symbol": "COIN", "name": "Coinbase", "type": "加密資產", "group": "美股個股"},
    {"symbol": "HOOD", "name": "Robinhood", "type": "金融科技", "group": "美股個股"},
    {"symbol": "UBER", "name": "Uber Technologies", "type": "平台經濟", "group": "美股個股"},
    {"symbol": "DIS", "name": "Walt Disney", "type": "媒體娛樂", "group": "美股個股"},
    {"symbol": "KO", "name": "Coca-Cola", "type": "防禦消費", "group": "美股個股"},
    {"symbol": "PEP", "name": "PepsiCo", "type": "防禦消費", "group": "美股個股"},
    {"symbol": "PG", "name": "Procter & Gamble", "type": "防禦消費", "group": "美股個股"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "type": "醫療保健", "group": "美股個股"},
    {"symbol": "MRK", "name": "Merck", "type": "製藥", "group": "美股個股"},
    {"symbol": "ABBV", "name": "AbbVie", "type": "製藥", "group": "美股個股"},
    {"symbol": "PFE", "name": "Pfizer", "type": "製藥", "group": "美股個股"},
    {"symbol": "XOM", "name": "Exxon Mobil", "type": "能源", "group": "美股個股"},
    {"symbol": "CVX", "name": "Chevron", "type": "能源", "group": "美股個股"},
    {"symbol": "CAT", "name": "Caterpillar", "type": "工業", "group": "美股個股"},
    {"symbol": "GE", "name": "GE Aerospace", "type": "航太工業", "group": "美股個股"},
    {"symbol": "BA", "name": "Boeing", "type": "航太工業", "group": "美股個股"},
    {"symbol": "LMT", "name": "Lockheed Martin", "type": "國防", "group": "美股個股"},
    {"symbol": "NOC", "name": "Northrop Grumman", "type": "國防", "group": "美股個股"},
    {"symbol": "GS", "name": "Goldman Sachs", "type": "金融股", "group": "美股個股"},
    {"symbol": "MS", "name": "Morgan Stanley", "type": "金融股", "group": "美股個股"},
    {"symbol": "BAC", "name": "Bank of America", "type": "金融股", "group": "美股個股"},
    {"symbol": "WFC", "name": "Wells Fargo", "type": "金融股", "group": "美股個股"},
    {"symbol": "SCHW", "name": "Charles Schwab", "type": "金融股", "group": "美股個股"},
    {"symbol": "O", "name": "Realty Income", "type": "REIT", "group": "美股個股"},
    {"symbol": "PLD", "name": "Prologis", "type": "REIT", "group": "美股個股"},
    {"symbol": "VNQ", "name": "Vanguard Real Estate ETF", "type": "REIT ETF", "group": "美股 ETF"},
    {"symbol": "ARKK", "name": "ARK Innovation ETF", "type": "主題 ETF", "group": "美股 ETF"},
    {"symbol": "ARKW", "name": "ARK Next Generation Internet ETF", "type": "主題 ETF", "group": "美股 ETF"},
    {"symbol": "XLY", "name": "Consumer Discretionary Select Sector SPDR Fund", "type": "類股 ETF", "group": "美股 ETF"},
    {"symbol": "XLP", "name": "Consumer Staples Select Sector SPDR Fund", "type": "類股 ETF", "group": "美股 ETF"},
    {"symbol": "XLE", "name": "Energy Select Sector SPDR Fund", "type": "類股 ETF", "group": "美股 ETF"},
    {"symbol": "XLV", "name": "Health Care Select Sector SPDR Fund", "type": "類股 ETF", "group": "美股 ETF"},
    {"symbol": "XLI", "name": "Industrial Select Sector SPDR Fund", "type": "類股 ETF", "group": "美股 ETF"},
    {"symbol": "XLU", "name": "Utilities Select Sector SPDR Fund", "type": "類股 ETF", "group": "美股 ETF"},
    {"symbol": "XLB", "name": "Materials Select Sector SPDR Fund", "type": "類股 ETF", "group": "美股 ETF"},
    {"symbol": "XLRE", "name": "Real Estate Select Sector SPDR Fund", "type": "類股 ETF", "group": "美股 ETF"},
    {"symbol": "SPLG", "name": "SPDR Portfolio S&P 500 ETF", "type": "大盤 ETF", "group": "美股 ETF"},
    {"symbol": "IVV", "name": "iShares Core S&P 500 ETF", "type": "大盤 ETF", "group": "美股 ETF"},
    {"symbol": "SCHD", "name": "Schwab US Dividend Equity ETF", "type": "股息 ETF", "group": "美股 ETF"},
    {"symbol": "VIG", "name": "Vanguard Dividend Appreciation ETF", "type": "股息 ETF", "group": "美股 ETF"},
    {"symbol": "VYM", "name": "Vanguard High Dividend Yield ETF", "type": "股息 ETF", "group": "美股 ETF"},
    {"symbol": "JEPI", "name": "JPMorgan Equity Premium Income ETF", "type": "收益 ETF", "group": "美股 ETF"},
    {"symbol": "JEPQ", "name": "JPMorgan Nasdaq Equity Premium Income ETF", "type": "收益 ETF", "group": "美股 ETF"},
    {"symbol": "DGRW", "name": "WisdomTree US Quality Dividend Growth Fund", "type": "股息 ETF", "group": "美股 ETF"},
    {"symbol": "USMV", "name": "iShares MSCI USA Min Vol Factor ETF", "type": "因子 ETF", "group": "美股 ETF"},
    {"symbol": "MTUM", "name": "iShares MSCI USA Momentum Factor ETF", "type": "因子 ETF", "group": "美股 ETF"},
    {"symbol": "QUAL", "name": "iShares MSCI USA Quality Factor ETF", "type": "因子 ETF", "group": "美股 ETF"},
    {"symbol": "VUG", "name": "Vanguard Growth ETF", "type": "成長 ETF", "group": "美股 ETF"},
    {"symbol": "VTV", "name": "Vanguard Value ETF", "type": "價值 ETF", "group": "美股 ETF"},
    {"symbol": "IJR", "name": "iShares Core S&P Small-Cap ETF", "type": "小型股 ETF", "group": "美股 ETF"},
    {"symbol": "MDY", "name": "SPDR S&P MidCap 400 ETF", "type": "中型股 ETF", "group": "美股 ETF"},
    {"symbol": "EFA", "name": "iShares MSCI EAFE ETF", "type": "國際 ETF", "group": "美股 ETF"},
    {"symbol": "EEM", "name": "iShares MSCI Emerging Markets ETF", "type": "新興市場 ETF", "group": "美股 ETF"},
    {"symbol": "VEA", "name": "Vanguard FTSE Developed Markets ETF", "type": "國際 ETF", "group": "美股 ETF"},
    {"symbol": "VWO", "name": "Vanguard FTSE Emerging Markets ETF", "type": "新興市場 ETF", "group": "美股 ETF"},
    {"symbol": "TLT", "name": "iShares 20+ Year Treasury Bond ETF", "type": "債券 ETF", "group": "美股 ETF"},
    {"symbol": "IEF", "name": "iShares 7-10 Year Treasury Bond ETF", "type": "債券 ETF", "group": "美股 ETF"},
    {"symbol": "SHY", "name": "iShares 1-3 Year Treasury Bond ETF", "type": "債券 ETF", "group": "美股 ETF"},
    {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "type": "債券 ETF", "group": "美股 ETF"},
    {"symbol": "AGG", "name": "iShares Core U.S. Aggregate Bond ETF", "type": "債券 ETF", "group": "美股 ETF"},
    {"symbol": "LQD", "name": "iShares iBoxx Investment Grade Corporate Bond ETF", "type": "信用債 ETF", "group": "美股 ETF"},
    {"symbol": "HYG", "name": "iShares iBoxx High Yield Corporate Bond ETF", "type": "高收益債 ETF", "group": "美股 ETF"},
    {"symbol": "GLD", "name": "SPDR Gold Shares", "type": "黃金 ETF", "group": "美股 ETF"},
    {"symbol": "IAU", "name": "iShares Gold Trust", "type": "黃金 ETF", "group": "美股 ETF"},
    {"symbol": "SLV", "name": "iShares Silver Trust", "type": "白銀 ETF", "group": "美股 ETF"},
    {"symbol": "USO", "name": "United States Oil Fund", "type": "能源 ETF", "group": "美股 ETF"},
    {"symbol": "BITO", "name": "ProShares Bitcoin Strategy ETF", "type": "加密 ETF", "group": "美股 ETF"},
    {"symbol": "IBIT", "name": "iShares Bitcoin Trust ETF", "type": "加密 ETF", "group": "美股 ETF"},
    {"symbol": "GBTC", "name": "Grayscale Bitcoin Trust ETF", "type": "加密 ETF", "group": "美股 ETF"},
    {"symbol": "SQQQ", "name": "ProShares UltraPro Short QQQ", "type": "反向 ETF", "group": "美股 ETF"},
    {"symbol": "TQQQ", "name": "ProShares UltraPro QQQ", "type": "槓桿 ETF", "group": "美股 ETF"},
    {"symbol": "SOXL", "name": "Direxion Daily Semiconductor Bull 3X Shares", "type": "槓桿 ETF", "group": "美股 ETF"},
    {"symbol": "SOXS", "name": "Direxion Daily Semiconductor Bear 3X Shares", "type": "反向 ETF", "group": "美股 ETF"},
]
US_MARKET_SEARCH_UNIVERSE = list({item["symbol"].upper(): item for item in US_MARKET_SEARCH_UNIVERSE}.values())
