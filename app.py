from __future__ import annotations

import copy
import json
import logging
import math
import os
import re
import threading
import time
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import unescape
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

from derivatives.analytics import build_basis_payload
from derivatives.ai import build_unavailable_ai_analysis as build_derivatives_unavailable_ai_analysis
from derivatives.catalog import TAIWAN_FUTURES_V1, TAIWAN_OPTIONS_V1, apply_taifex_defaults, v1_product_status
from derivatives.institution import build_institution_payload_from_rows, build_pending_institution_payload, normalize_institution_row, parse_institution_csv
from derivatives.options import build_unavailable_option_chain as build_derivatives_unavailable_option_chain
from derivatives_store import DerivativesStore
from cache import (
    BUNDLED_CACHE_FILE,
    CACHE_FILE,
    CACHE_FLIGHT_WAIT_SECONDS,
    CACHE_VERSION,
    PENNY_SECTOR_RECOMMENDATION_CACHE_SECONDS,
    background_updater_enabled,
    build_disk_cache_snapshot,
    cache_data,
    cache_flight_lock,
    cache_flights,
    cache_lock,
    cache_refresh_lock,
    claim_cache_flight,
    deserialize_treasury_yield_curve_cache,
    ensure_cache,
    finish_cache_flight,
    load_disk_cache,
    penny_sector_recommendation_cache,
    penny_sector_recommendation_lock,
    read_memory_cache,
    refresh_cache,
    sanitize_site_data,
    save_disk_cache,
    serialize_treasury_yield_curve_cache,
    start_background_updater,
    write_memory_cache,
)
from security import (
    add_security_headers,
    enforce_api_rate_limit,
    is_authorized_derivatives_admin,
    _urlopen_with_ssl_fallback,
)
from fetchers import (
    EXTERNAL_TEXT_CACHE_SECONDS,
    TAIFEX_FUTURES_DAILY_OPENAPI_URL,
    TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
    TAIFEX_INSTITUTION_FUTURES_DETAIL_OPENAPI_URL,
    TAIFEX_INSTITUTION_OPTIONS_DETAIL_OPENAPI_URL,
    barchart_options_headers,
    build_index_activity_url,
    build_index_intraday_url,
    build_market_url,
    build_stock_day_url,
    build_stock_institutions_url,
    build_stock_news_fallback,
    build_tpex_openapi_url,
    build_yahoo_macro_snapshot,
    collect_futures_until_deadline,
    dataset_has_rows,
    detect_tone,
    extract_balanced_segment,
    extract_meta_description,
    extract_visible_text_lines,
    fetch_barchart_options_context,
    fetch_binary,
    fetch_etf_dividend_info,
    fetch_form_text,
    fetch_fred_observation_rows,
    fetch_json,
    fetch_live_index_activity,
    fetch_live_index_intraday,
    fetch_market_macro_factors,
    fetch_market_volatility_indicator,
    fetch_nasdaq_company_financials,
    fetch_nasdaq_company_insider_trades,
    fetch_nasdaq_company_institutional_holdings,
    fetch_nasdaq_company_profile,
    fetch_nasdaq_json,
    fetch_nasdaq_quote_endpoint,
    fetch_nasdaq_trader_us_listed_universe,
    fetch_nasdaq_us_supplement,
    fetch_nyse_directory_items,
    fetch_nyse_us_market_search,
    fetch_recent_trade_rows,
    fetch_stock_company_profile,
    fetch_stock_history_rows,
    fetch_stock_institutional_trades,
    fetch_stock_institutional_trade_for_date,
    fetch_stock_institutions_payload_near,
    fetch_stock_margin_trading,
    fetch_stock_news,
    fetch_stock_valuation,
    fetch_stock_valuation_history,
    fetch_stock_valuation_on_date,
    fetch_taiex_spot_snapshot,
    fetch_taifex_futures_open_interest,
    fetch_taifex_futures_price_candles,
    fetch_taifex_futures_technical_candles,
    fetch_taifex_institution_detail_rows,
    fetch_taifex_latest_futures_market_snapshot,
    fetch_taifex_openapi_list,
    fetch_taifex_tx_open_interest,
    fetch_taifex_txo_option_chain,
    fetch_taiwan_option_chain,
    fetch_taiwan_option_spot_snapshot,
    fetch_tdcc_holding_distribution_text,
    fetch_text,
    fetch_tpex_mainboard_quotes,
    fetch_trading_economics_taiwan_10y,
    fetch_twse_listed_industry_map,
    fetch_twse_margin_summary,
    fetch_txo_option_chain,
    fetch_us_etf_directory_items,
    fetch_us_listed_universe_with_fallback,
    fetch_us_market_overview_news,
    fetch_us_treasury_yield_curve,
    fetch_us_treasury_yield_curve_rows,
    fetch_yahoo_broker_trading,
    fetch_yahoo_chart,
    fetch_yahoo_class_quote_pages,
    fetch_yahoo_history_rows,
    fetch_yahoo_major_holders,
    fetch_yahoo_margin_accumulation_rows,
    fetch_yahoo_margin_period_rows,
    fetch_yahoo_margin_trading,
    fetch_yahoo_options_payload,
    fetch_yahoo_quote_summary,
    fetch_yahoo_spot_snapshot,
    fetch_yahoo_taiwan_future_quote,
    fetch_yahoo_taiwan_future_quotes,
    fetch_yahoo_tpex_etfs,
    fetch_yahoo_tw_stock_resource,
    fetch_yahoo_txo_option_chain,
    fetch_yahoo_us_market_search,
    fetch_yahoo_us_symbol_news,
    filter_us_etf_items,
    find_latest_dataset,
    format_percent,
    format_roc_date,
    format_signed,
    format_whole_number,
    is_finite_positive,
    is_valid_ohlc_values,
    normalize_taifex_date_text,
    normalize_us_market_search_item,
    normalize_us_symbol_for_yahoo,
    parse_barchart_expiration_date,
    parse_english_market_date,
    parse_float,
    parse_fred_date,
    parse_nasdaq_symbol_directory,
    parse_public_options_number,
    parse_roc_date,
    parse_taifex_market_number,
    parse_taifex_open_interest_by_header,
    parse_tdcc_holding_distributions,
    post_json,
    shift_month,
    should_cache_external_text,
)
from builders import (
    STOCK_HISTORY_RECENT_MONTHS,
    build_derivative_candles,
    build_futures_ai_analysis,
    build_index_technical_analysis,
    build_institution_payload_live,
    build_institution_summary,
    build_institution_trend,
    build_global_market_item,
    build_global_market_payload,
    build_institutions_url,
    build_intraday_index_candles,
    build_intraday_technical_analysis,
    build_news,
    build_public_options_chain,
    build_sector_fund_flow,
    build_sector_history_series,
    build_site_data,
    build_site_data_view,
    build_stock_detail,
    build_stock_institutional_trade_record,
    build_stock_institutional_trade_summary,
    build_stock_search_url,
    build_summary_cards_from_payload,
    build_taifex_open_interest_item,
    build_taifex_option_ai_analysis,
    build_taifex_option_chain,
    build_taifex_option_distribution,
    build_taifex_stock_derivative_aggregate_item,
    build_taifex_txo_option_payload,
    build_txo_option_market_item,
    build_weighted_index_history_series,
    build_weighted_index_history_url,
    build_yahoo_class_quote_cards,
    build_yahoo_sector_groups,
    build_yahoo_summary_series,
    build_yahoo_taiwan_future_technical_profile,
    build_yahoo_taiwan_future_technical_url,
    build_yahoo_taiwan_option_url,
    build_yahoo_txo_option_payload,
    calculate_taifex_max_pain,
    enrich_global_market_spec,
    is_valid_history_row,
    normalize_futures_yahoo_uncovered_links,
    normalize_taiwan_option_underlying,
    parse_yahoo_quote_items,
    resolve_sector_key,
    sanitize_history_rows,
    summarize_taifex_option_rows,
)
from parsers import (
    TAIWAN_OPTION_DEFAULT_PRODUCT,
    TAIWAN_OPTION_PRODUCTS,
    YAHOO_TW_FUTURE_CODE_PREFIX_TO_SYMBOL,
    YAHOO_TW_FUTURE_CODE_TO_SYMBOL,
    YAHOO_TW_FUTURE_TECHNICAL_GROUPS,
    YAHOO_TW_FUTURE_UNCOVERED_URL,
    estimate_index_option_iv,
    find_derivative_spec,
    find_stock_by_query,
    get_taiwan_option_product,
    market_payload_has_complete_index_tables,
    normalize_taiwan_option_source,
    parse_all_stocks,
    parse_institutions,
    parse_market_overview,
    parse_market_statistics,
    parse_sectors,
    parse_taifex_txo_option_rows,
    parse_tpex_quotes,
    parse_yahoo_taiwan_future_quotes,
    parse_yahoo_tw_future_date,
    parse_yahoo_tw_future_number,
    parse_yahoo_txo_option_table,
    refresh_tpex_cache,
)
from market_config import (
    CBOE_OPTIONS_BASE,
    EXCLUDED_SECTOR_SOURCE_NAMES,
    GLOBAL_MARKET_CATEGORIES,
    INDEX_DISPLAY_NAMES,
    LISTED_SECTOR_INDEX_ORDER,
    LISTED_SECTOR_INDEX_SPECS,
    NASDAQ_API_BASE,
    NASDAQ_USER_AGENT,
    SECTOR_INDEX_DISPLAY_NAMES,
    TAIFEX_FUTURES_DAILY_URL,
    TAIFEX_OPTIONS_DAILY_URL,
    TAIFEX_OPTIONS_PC_RATIO_URL,
    TARGET_INDEX_NAMES,
    TPEX_OPENAPI_BASE,
    TWSE_BASE,
    TWSE_MARGIN_URL,
    USER_AGENT,
    YAHOO_CHART_BASE,
    YAHOO_CLASS_HOME_URL,
    YAHOO_CONCEPT_CLASS_URL,
    YAHOO_ELECTRONIC_CLASS_URL,
    YAHOO_GROUP_CLASS_URL,
    YAHOO_LISTED_CLASS_URL,
    YAHOO_QUOTE_SUMMARY_BASE,
    YAHOO_SEARCH_BASE,
    YAHOO_TPEX_EMERGING_CLASS_URL,
    YAHOO_TPEX_OTC_CLASS_URL,
)
from routes_global_market import bp as global_market_bp
from routes_system import bp as system_bp
from routes_twse import bp as twse_bp


BASE_DIR = Path(__file__).resolve().parent
DERIVATIVES_STORE = DerivativesStore(os.environ.get("DERIVATIVES_DB_PATH", str(BASE_DIR / "derivatives-platform.sqlite3")))
DERIVATIVES_STORE.initialize()
LOG_LEVEL = str(os.environ.get("MARKET_PULSE_LOG_LEVEL") or "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger("market_pulse")
try:
    TZ = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:
    TZ = timezone(timedelta(hours=8))
WEIGHTED_INDEX_HISTORY_TRADING_DAYS = 480


class DeadlineThreadPoolExecutor(ThreadPoolExecutor):
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=False, cancel_futures=True)
        return False


def extend_global_market_catalog(category: str, additions: list[dict[str, Any]]) -> None:
    existing = GLOBAL_MARKET_CATEGORIES[category]["items"]
    symbols = {str(item.get("symbol") or "").upper() for item in existing}
    for item in additions:
        symbol = str(item.get("symbol") or "").upper()
        if symbol and symbol not in symbols:
            existing.append(item)
            symbols.add(symbol)


def insert_global_market_catalog_after(category: str, after_symbol: str, item: dict[str, Any]) -> None:
    existing = GLOBAL_MARKET_CATEGORIES[category]["items"]
    symbol = str(item.get("symbol") or "").upper()
    if not symbol or any(str(existing_item.get("symbol") or "").upper() == symbol for existing_item in existing):
        return
    after_key = str(after_symbol or "").upper()
    insert_at = next(
        (index + 1 for index, existing_item in enumerate(existing) if str(existing_item.get("symbol") or "").upper() == after_key),
        len(existing),
    )
    existing.insert(insert_at, item)


insert_global_market_catalog_after("futures", "SOF", {
    "symbol": "XIF",
    "name": "非金電期貨 XIF 未平倉",
    "type": "台灣非金電指數期貨",
    "group": "國內指數期貨",
    "region": "台灣",
    "market": "台灣",
    "exchange": "TAIFEX",
    "dataSource": "TAIFEX 官方期貨日報",
    "referenceSource": "TAIFEX 非金電期貨契約規格",
    "sourceUrl": TAIFEX_FUTURES_DAILY_URL,
    "dataProvider": "taifex_futures_open_interest",
    "taifexCommodity": "XIF",
    "metricLabel": "未平倉量",
    "v1Status": "connected",
})


extend_global_market_catalog("futures", [
    {"symbol": "MYM=F", "name": "Micro E-mini Dow Futures", "type": "股指期貨"},
    {"symbol": "M2K=F", "name": "Micro E-mini Russell 2000 Futures", "type": "股指期貨"},
    {"symbol": "6E=F", "name": "Euro FX Futures", "type": "外匯期貨"},
    {"symbol": "6J=F", "name": "Japanese Yen Futures", "type": "外匯期貨"},
    {"symbol": "6B=F", "name": "British Pound Futures", "type": "外匯期貨"},
    {"symbol": "6A=F", "name": "Australian Dollar Futures", "type": "外匯期貨"},
    {"symbol": "6C=F", "name": "Canadian Dollar Futures", "type": "外匯期貨"},
    {"symbol": "DX=F", "name": "U.S. Dollar Index Futures", "type": "外匯期貨"},
    {"symbol": "ZQ=F", "name": "30-Day Fed Funds Futures", "type": "利率期貨"},
    {"symbol": "UB=F", "name": "Ultra U.S. Treasury Bond Futures", "type": "利率期貨"},
    {"symbol": "MCL=F", "name": "Micro WTI Crude Oil Futures", "type": "能源期貨"},
    {"symbol": "QG=F", "name": "E-mini Natural Gas Futures", "type": "能源期貨"},
    {"symbol": "MGC=F", "name": "Micro Gold Futures", "type": "貴金屬期貨"},
    {"symbol": "SIL=F", "name": "Micro Silver Futures", "type": "貴金屬期貨"},
    {"symbol": "ZL=F", "name": "Soybean Oil Futures", "type": "農產品期貨"},
    {"symbol": "ZM=F", "name": "Soybean Meal Futures", "type": "農產品期貨"},
    {"symbol": "KE=F", "name": "Kansas City Wheat Futures", "type": "農產品期貨"},
    {"symbol": "ZO=F", "name": "Oat Futures", "type": "農產品期貨"},
    {"symbol": "CC=F", "name": "Cocoa Futures", "type": "軟性商品期貨"},
    {"symbol": "OJ=F", "name": "Orange Juice Futures", "type": "軟性商品期貨"},
    {"symbol": "GF=F", "name": "Feeder Cattle Futures", "type": "畜牧期貨"},
])

extend_global_market_catalog("options", [
    {"symbol": "SVIX", "name": "SVIX 波動率 ETF Options", "type": "反向波動率 ETF 選擇權", "group": "波動率選擇權", "region": "美國", "market": "Cboe / NYSE Arca", "exchange": "Cboe", "optionCategory": "波動率選擇權", "optionSubcategory": "反向 VIX ETF", "optionSourceRole": "真實 ETF 選擇權鏈"},
    {"symbol": "VXZ", "name": "VXZ 中期期貨波動率 ETN Options", "type": "波動率 ETN 選擇權", "group": "波動率選擇權", "region": "美國", "market": "Cboe / NYSE Arca", "exchange": "Cboe", "optionCategory": "波動率選擇權", "optionSubcategory": "中期 VIX ETN", "optionSourceRole": "真實 ETN 選擇權鏈"},
    {"symbol": "VIXM", "name": "VIXM 中期期貨波動率 ETF Options", "type": "波動率 ETF 選擇權", "group": "波動率選擇權", "region": "美國", "market": "Cboe / NYSE Arca", "exchange": "Cboe", "optionCategory": "波動率選擇權", "optionSubcategory": "中期 VIX ETF", "optionSourceRole": "真實 ETF 選擇權鏈"},
    {"symbol": "XLE", "name": "Energy Select Sector SPDR", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "能源類股 ETF", "optionSourceRole": "ETF 標的行情代理"},
    {"symbol": "XLF", "name": "Financial Select Sector SPDR", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "金融類股 ETF", "optionSourceRole": "ETF 標的行情代理"},
    {"symbol": "XLK", "fallbackSymbols": ["QQQ", "SMH", "SOXX"], "name": "Technology Select Sector SPDR", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "科技類股 ETF", "optionSourceRole": "ETF 標的行情代理"},
    {"symbol": "XLV", "name": "Health Care Select Sector SPDR", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "醫療類股 ETF", "optionSourceRole": "ETF 標的行情代理"},
    {"symbol": "SMH", "name": "VanEck Semiconductor ETF", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "半導體 ETF", "optionSourceRole": "ETF 標的行情代理"},
    {"symbol": "SOXX", "fallbackSymbols": ["SMH", "QQQ"], "name": "iShares Semiconductor ETF", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "半導體 ETF", "optionSourceRole": "ETF 標的行情代理"},
    {"symbol": "XBI", "name": "SPDR S&P Biotech ETF", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "生技 ETF", "optionSourceRole": "ETF 標的行情代理"},
    {"symbol": "USO", "fallbackSymbols": ["CL=F", "XLE"], "name": "United States Oil Fund", "type": "ETF 選擇權標的", "group": "美國 ETF 選擇權", "region": "美國", "market": "OCC / NYSE Arca", "exchange": "Yahoo Finance / OCC", "optionCategory": "ETF 選擇權", "optionSubcategory": "原油 ETF", "optionSourceRole": "ETF 標的行情代理"},
    {"symbol": "BAC", "name": "Bank of America", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / NYSE", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國金融", "optionSourceRole": "個股標的行情代理"},
    {"symbol": "NFLX", "name": "Netflix", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國科技 / 通訊服務", "optionSourceRole": "個股標的行情代理"},
    {"symbol": "GOOGL", "name": "Alphabet", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國科技 / 通訊服務", "optionSourceRole": "個股標的行情代理"},
    {"symbol": "AVGO", "fallbackSymbols": ["SMH", "SOXX", "QQQ"], "name": "Broadcom", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國半導體", "optionSourceRole": "個股標的行情代理"},
    {"symbol": "AMD", "name": "AMD", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國半導體", "optionSourceRole": "個股標的行情代理"},
    {"symbol": "PLTR", "fallbackSymbols": ["ARKK", "QQQ"], "name": "Palantir Technologies", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國 AI 軟體", "optionSourceRole": "個股標的行情代理"},
    {"symbol": "COIN", "name": "Coinbase Global", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / Nasdaq", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國加密資產", "optionSourceRole": "個股標的行情代理"},
    {"symbol": "GME", "name": "GameStop", "type": "股票選擇權標的", "group": "美國股票選擇權", "region": "美國", "market": "OCC / NYSE", "exchange": "Yahoo Finance / OCC", "optionCategory": "股票選擇權", "optionSubcategory": "美國高波動個股", "optionSourceRole": "個股標的行情代理"},
])

extend_global_market_catalog("precious-metals", [
    {"symbol": "XAUUSD=X", "name": "Gold Spot USD", "type": "貴金屬現貨"},
    {"symbol": "XAGUSD=X", "name": "Silver Spot USD", "type": "貴金屬現貨"},
    {"symbol": "XPTUSD=X", "name": "Platinum Spot USD", "type": "貴金屬現貨"},
    {"symbol": "XPDUSD=X", "name": "Palladium Spot USD", "type": "貴金屬現貨"},
    {"symbol": "SGOL", "name": "abrdn Physical Gold Shares ETF", "type": "ETF"},
    {"symbol": "BAR", "name": "GraniteShares Gold Trust", "type": "ETF"},
    {"symbol": "AAAU", "name": "Goldman Sachs Physical Gold ETF", "type": "ETF"},
    {"symbol": "SIVR", "name": "abrdn Physical Silver Shares ETF", "type": "ETF"},
    {"symbol": "PSLV", "name": "Sprott Physical Silver Trust", "type": "ETF"},
    {"symbol": "PLTM", "name": "GraniteShares Platinum Trust", "type": "ETF"},
    {"symbol": "COPX", "name": "Global X Copper Miners ETF", "type": "礦業 ETF"},
    {"symbol": "GDX", "name": "VanEck Gold Miners ETF", "type": "礦業 ETF"},
    {"symbol": "GDXJ", "name": "VanEck Junior Gold Miners ETF", "type": "礦業 ETF"},
    {"symbol": "SIL", "name": "Global X Silver Miners ETF", "type": "礦業 ETF"},
    {"symbol": "SILJ", "name": "Amplify Junior Silver Miners ETF", "type": "礦業 ETF"},
    {"symbol": "RING", "name": "iShares MSCI Global Gold Miners ETF", "type": "礦業 ETF"},
    {"symbol": "WPM", "name": "Wheaton Precious Metals", "type": "貴金屬個股"},
    {"symbol": "NEM", "name": "Newmont", "type": "貴金屬礦商個股"},
    {"symbol": "GOLD", "name": "Barrick Gold", "type": "貴金屬礦商個股"},
    {"symbol": "AEM", "name": "Agnico Eagle Mines", "type": "貴金屬礦商個股"},
    {"symbol": "FNV", "name": "Franco-Nevada", "type": "貴金屬礦商個股"},
])

extend_global_market_catalog("bonds", [
    {"symbol": "SCHO", "name": "Schwab Short-Term U.S. Treasury ETF", "type": "債券 ETF"},
    {"symbol": "BIL", "name": "SPDR Bloomberg 1-3 Month T-Bill ETF", "type": "債券 ETF"},
    {"symbol": "SGOV", "name": "iShares 0-3 Month Treasury Bond ETF", "type": "債券 ETF"},
    {"symbol": "USFR", "name": "WisdomTree Floating Rate Treasury Fund", "type": "浮動利率債 ETF"},
    {"symbol": "TFLO", "name": "iShares Treasury Floating Rate Bond ETF", "type": "浮動利率債 ETF"},
    {"symbol": "IEI", "name": "iShares 3-7 Year Treasury Bond ETF", "type": "債券 ETF"},
    {"symbol": "SCHR", "name": "Schwab Intermediate-Term U.S. Treasury ETF", "type": "債券 ETF"},
    {"symbol": "BIV", "name": "Vanguard Intermediate-Term Bond ETF", "type": "債券 ETF"},
    {"symbol": "EDV", "name": "Vanguard Extended Duration Treasury ETF", "type": "債券 ETF"},
    {"symbol": "GOVZ", "name": "iShares 25+ Year Treasury STRIPS Bond ETF", "type": "債券 ETF"},
    {"symbol": "SCHZ", "name": "Schwab U.S. Aggregate Bond ETF", "type": "債券 ETF"},
    {"symbol": "BNDX", "name": "Vanguard Total International Bond ETF", "type": "全球債券 ETF"},
    {"symbol": "IAGG", "name": "iShares International Aggregate Bond ETF", "type": "全球債券 ETF"},
    {"symbol": "VCSH", "name": "Vanguard Short-Term Corporate Bond ETF", "type": "信用債 ETF"},
    {"symbol": "VCIT", "name": "Vanguard Intermediate-Term Corporate Bond ETF", "type": "信用債 ETF"},
    {"symbol": "IGIB", "name": "iShares 5-10 Year Investment Grade Corporate Bond ETF", "type": "信用債 ETF"},
    {"symbol": "SJNK", "name": "SPDR Bloomberg Short Term High Yield Bond ETF", "type": "信用債 ETF"},
    {"symbol": "ANGL", "name": "VanEck Fallen Angel High Yield Bond ETF", "type": "信用債 ETF"},
    {"symbol": "SCHP", "name": "Schwab U.S. TIPS ETF", "type": "抗通膨債 ETF"},
    {"symbol": "VTIP", "name": "Vanguard Short-Term Inflation-Protected Securities ETF", "type": "抗通膨債 ETF"},
    {"symbol": "MBB", "name": "iShares MBS ETF", "type": "MBS ETF"},
    {"symbol": "VMBS", "name": "Vanguard Mortgage-Backed Securities ETF", "type": "MBS ETF"},
    {"symbol": "VTEB", "name": "Vanguard Tax-Exempt Bond ETF", "type": "市政債 ETF"},
])


def remove_global_market_symbols(category: str, symbols: set[str]) -> None:
    blocked = {symbol.upper() for symbol in symbols}
    GLOBAL_MARKET_CATEGORIES[category]["items"] = [
        item for item in GLOBAL_MARKET_CATEGORIES[category]["items"]
        if str(item.get("symbol") or "").upper() not in blocked
    ]


# Yahoo Finance 無穩定日線回傳的代號不納入預設有效目錄；避免把無法驗證的標的當成行情資料。
remove_global_market_symbols("futures", {"DX=F"})
remove_global_market_symbols("options", {"^RVX"})
remove_global_market_symbols("precious-metals", {"XAUUSD=X", "XAGUSD=X", "XPTUSD=X", "XPDUSD=X"})





app = Flask(__name__, static_folder=None)
if str(os.environ.get("MARKET_PULSE_TRUST_PROXY") or "").strip().lower() in {"1", "true", "yes"}:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

PUBLIC_DATA_SOURCE_ERROR_MESSAGE = "資料來源暫不可用，請稍後再試"
PUBLIC_TAIFEX_OPEN_INTEREST_ERROR_MESSAGE = "TAIFEX 未平倉資料暫時無法載入，請稍後再試"


def api_success_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "data": data, "updated_at": datetime.now(TZ).isoformat()}


def api_error_payload(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "error_code": code, "error": {"code": code, "message": message}}


def api_exception_response(code: str, public_message: str, exc: Exception, status: int = 502):
    LOGGER.exception("API %s: %s", code, public_message, exc_info=exc)
    return jsonify(api_error_payload(code, public_message)), status


app.after_request(add_security_headers)
app.before_request(enforce_api_rate_limit)
app.register_blueprint(system_bp)
app.register_blueprint(global_market_bp)
app.register_blueprint(twse_bp)


def taipei_now() -> datetime:
    return datetime.now(TZ)


def infer_yahoo_taiwan_future_symbol_from_code(code: str) -> str:
    clean_code = str(code or "").strip().upper()
    if not clean_code:
        return ""
    for symbol, group in YAHOO_TW_FUTURE_TECHNICAL_GROUPS.items():
        for _, contract_code, _ in group.get("contracts") or []:
            if str(contract_code or "").strip().upper() == clean_code:
                return symbol
    for prefix, symbol in YAHOO_TW_FUTURE_CODE_PREFIX_TO_SYMBOL.items():
        if clean_code.startswith(prefix):
            return symbol
    return YAHOO_TW_FUTURE_CODE_TO_SYMBOL.get(clean_code, "")


def find_yahoo_taiwan_future_technical_contract(symbol: str, code: str = "") -> dict[str, Any] | None:
    clean_symbol = str(symbol or "").strip().upper()
    profile = build_yahoo_taiwan_future_technical_profile(clean_symbol)
    contracts = [item for item in profile.get("contracts") or [] if isinstance(item, dict)]
    if not contracts:
        return None
    clean_code = str(code or profile.get("primaryCode") or "").strip().upper()
    selected = next((item for item in contracts if str(item.get("code") or "").strip().upper() == clean_code), None)
    return selected or next((item for item in contracts if item.get("isPrimary")), None) or contracts[0]


def parse_yahoo_txo_option_contract_label(lines: list[str], underlying: str | None = "TXO") -> str:
    product = get_taiwan_option_product(underlying)
    prefix = str(product.get("yahooLabelPrefix") or "台指")
    for line in lines:
        label = str(line or "").strip()
        if re.fullmatch(rf"{re.escape(prefix)}(?:2W)?\d{{4}}", label):
            return label
    return product["shortName"]


def parse_yahoo_txo_underlying_snapshot(lines: list[str]) -> dict[str, Any]:
    snapshot = {"symbol": "^TWII", "name": "台灣加權指數", "value": None, "source": "Yahoo 股市台灣選擇權頁"}
    text = " ".join(str(line or "").strip() for line in lines if str(line or "").strip())
    value_match = re.search(r"加權股價指數\s*[：:]\s*([0-9,]+(?:\.\d+)?)", text)
    if value_match:
        snapshot["value"] = parse_yahoo_tw_future_number(value_match.group(1))
    change_match = re.search(r"漲跌\(%\)\s*[：:]\s*([▲▼+-]?)\s*([0-9,]+(?:\.\d+)?)\s*\(([+-]?[0-9,]+(?:\.\d+)?)%\)", text)
    if change_match:
        direction, change_text, pct_text = change_match.groups()
        change = parse_yahoo_tw_future_number(change_text)
        pct = parse_yahoo_tw_future_number(pct_text)
        if direction == "▼" and change is not None:
            change *= -1
        if direction == "▼" and pct is not None:
            pct *= -1
        snapshot["change"] = change
        snapshot["pct"] = pct
    high_match = re.search(r"最高\s*[：:]\s*([0-9,]+(?:\.\d+)?)", text)
    low_match = re.search(r"最低\s*[：:]\s*([0-9,]+(?:\.\d+)?)", text)
    volume_match = re.search(r"成交量\(億\)\s*[：:]\s*([0-9,]+(?:\.\d+)?)", text)
    if high_match:
        snapshot["high"] = parse_yahoo_tw_future_number(high_match.group(1))
    if low_match:
        snapshot["low"] = parse_yahoo_tw_future_number(low_match.group(1))
    if volume_match:
        snapshot["volumeBillion"] = parse_yahoo_tw_future_number(volume_match.group(1))
    return snapshot


def normalize_yahoo_txo_expiry_code(label: str | None) -> str:
    text = str(label or "").strip()
    match = re.search(r"台指(?:(\d)W)?(\d{2})(\d{2})", text)
    if not match:
        return text
    week, yy, month = match.groups()
    code = f"20{yy}{month}"
    return f"{code}W{week}" if week else code


def parse_yahoo_txo_option_page(html: str, underlying: str | None = "TXO", expiry: str | None = None) -> dict[str, Any]:
    product = get_taiwan_option_product(underlying)
    yahoo_url = build_yahoo_taiwan_option_url(product["symbol"], expiry)
    lines = [line.strip() for line in extract_visible_text_lines(html) if line.strip()]
    if not lines:
        return {
            "underlying": product["symbol"],
            "name": product["name"],
            "market": "台灣",
            "exchange": "Yahoo 股市",
            "error": "Yahoo 選擇權頁暫時未回傳可解析內容",
            "source": {"primary": "Yahoo 股市台灣選擇權報價", "primaryUrl": yahoo_url},
        }
    trade_date = next((parse_yahoo_tw_future_date(line) for line in lines if "資料時間" in line), "")
    trade_date = trade_date or datetime.now(TZ).strftime("%Y-%m-%d")
    expiry_code = normalize_yahoo_txo_expiry_code(parse_yahoo_txo_option_contract_label(lines, product["symbol"]))
    if expiry and not re.fullmatch(r"\d{6}(?:W\d)?", str(expiry_code or "")):
        expiry_code = expiry
    spot_snapshot = parse_yahoo_txo_underlying_snapshot(lines)
    if spot_snapshot.get("value") is None:
        spot_snapshot = {**fetch_taiwan_option_spot_snapshot(product["symbol"]), **spot_snapshot}
    rows = parse_yahoo_txo_option_table(lines, trade_date, expiry_code, spot_snapshot.get("value"), product["symbol"])
    if not rows:
        return {
            "underlying": product["symbol"],
            "name": product["name"],
            "market": "台灣",
            "exchange": "Yahoo 股市",
            "tradeDate": trade_date,
            "selectedExpiry": expiry_code,
            "spot": spot_snapshot,
            "error": "Yahoo 選擇權頁暫時無法解析買權 / 賣權鏈",
            "source": {"primary": "Yahoo 股市台灣選擇權報價", "primaryUrl": yahoo_url},
        }
    return build_yahoo_txo_option_payload(rows, trade_date, expiry_code, spot_snapshot, product["symbol"])


def flatten_taifex_option_chain(chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in chain:
        for side, option_type in (("call", "call"), ("put", "put")):
            row = copy.deepcopy(item.get(side) or {})
            if not row:
                continue
            row.setdefault("strike", item.get("strike"))
            row.setdefault("optionType", option_type)
            rows.append(row)
    return rows


def merge_option_side_with_intraday_oi(base: dict[str, Any] | None, supplement: dict[str, Any] | None) -> dict[str, Any] | None:
    if not base and not supplement:
        return None
    merged = copy.deepcopy(base or supplement or {})
    supplement = supplement or {}
    supplemental_oi = parse_float(str(supplement.get("openInterest") or ""))
    if supplemental_oi is not None and supplemental_oi > 0 and not parse_float(str(merged.get("openInterest") or "")):
        merged["openInterest"] = supplemental_oi
        merged["openInterestSource"] = "Yahoo 股市盤中未平倉"
    for field in ("bid", "ask", "last", "settlement", "change", "quoteTime"):
        if merged.get(field) in (None, "", "--") and supplement.get(field) not in (None, "", "--"):
            merged[field] = supplement.get(field)
    if supplement.get("volume") not in (None, "", 0) and not merged.get("volume"):
        merged["volume"] = supplement.get("volume")
    return merged


def supplement_taifex_option_payload_with_yahoo_oi(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    selected = str(payload.get("selectedExpiry") or "").strip()
    product = get_taiwan_option_product(str(payload.get("underlying") or "TXO"))
    if not product.get("yahooOpcm"):
        return payload
    yahoo_url = build_yahoo_taiwan_option_url(product["symbol"], selected or None)
    try:
        yahoo_payload = fetch_yahoo_txo_option_chain(selected or None, product["symbol"])
    except Exception as exc:  # noqa: BLE001
        LOGGER.info("Yahoo %s intraday OI supplement unavailable", product["symbol"], exc_info=exc)
        return payload
    if yahoo_payload.get("error"):
        return payload
    chain = copy.deepcopy(payload.get("chain") or [])
    next_payload = copy.deepcopy(payload)
    yahoo_spot = yahoo_payload.get("spot") or {}
    yahoo_spot_value = parse_float(str(yahoo_spot.get("value") or ""))
    if yahoo_spot_value is not None:
        next_summary = {**summary}
        if chain:
            next_summary["atmStrike"] = min(
                [item["strike"] for item in chain],
                key=lambda strike: abs(float(strike) - float(yahoo_spot_value)),
                default=next_summary.get("atmStrike"),
            )
        max_pain_for_spot = calculate_taifex_max_pain(chain) if chain else {"strike": next_summary.get("maxPain"), "loss": next_summary.get("maxPainLoss")}
        next_summary["maxPain"] = max_pain_for_spot.get("strike")
        next_summary["maxPainLoss"] = max_pain_for_spot.get("loss")
        next_payload = {
            **next_payload,
            "summary": next_summary,
            "spot": {**(payload.get("spot") or {}), **yahoo_spot, "source": "Yahoo 股市台灣選擇權頁"},
            "analysis": build_taifex_option_ai_analysis(next_summary, chain, max_pain_for_spot, yahoo_spot_value) if chain else payload.get("analysis"),
            "spotSupplement": {
                "provider": "Yahoo 股市台灣選擇權",
                "sourceUrl": yahoo_url,
                "fields": ["加權股價指數", "漲跌", "最高", "最低", "成交量(億)"],
            },
            "source": {
                **(payload.get("source") or {}),
                "primary": "TAIFEX 選擇權每日交易行情查詢",
                "spotProvider": "Yahoo 股市台灣選擇權頁加權指數",
                "spotUrl": yahoo_url,
            },
        }
        summary = next_summary
    if parse_float(str(summary.get("totalOpenInterest") or "")) not in (None, 0) or not selected:
        return next_payload
    yahoo_expiry = normalize_yahoo_txo_expiry_code(str(yahoo_payload.get("selectedExpiry") or ""))
    if yahoo_expiry != selected:
        return next_payload
    yahoo_chain = yahoo_payload.get("chain") or []
    yahoo_by_strike = {float(item.get("strike")): item for item in yahoo_chain if item.get("strike") is not None}
    if not yahoo_by_strike:
        return next_payload
    changed = False
    for item in chain:
        strike = parse_float(str(item.get("strike") or ""))
        if strike is None:
            continue
        supplement = yahoo_by_strike.get(float(strike))
        if not supplement:
            continue
        for side in ("call", "put"):
            before = parse_float(str((item.get(side) or {}).get("openInterest") or ""))
            item[side] = merge_option_side_with_intraday_oi(item.get(side), supplement.get(side))
            after = parse_float(str((item.get(side) or {}).get("openInterest") or ""))
            if (before in (None, 0)) and after not in (None, 0):
                changed = True
        item["callOpenInterest"] = float((item.get("call") or {}).get("openInterest") or 0)
        item["putOpenInterest"] = float((item.get("put") or {}).get("openInterest") or 0)
        item["callVolume"] = float((item.get("call") or {}).get("volume") or item.get("callVolume") or 0)
        item["putVolume"] = float((item.get("put") or {}).get("volume") or item.get("putVolume") or 0)
    if not changed:
        return next_payload
    flat_rows = flatten_taifex_option_chain(chain)
    next_summary = {**summary, **summarize_taifex_option_rows(flat_rows)}
    max_pain = calculate_taifex_max_pain(chain)
    next_summary["maxPain"] = max_pain.get("strike")
    next_summary["maxPainLoss"] = max_pain.get("loss")
    spot = (next_payload.get("spot") or {}).get("value")
    next_payload = {
        **next_payload,
        "chain": chain,
        "summary": next_summary,
        "distribution": build_taifex_option_distribution(chain),
        "analysis": build_taifex_option_ai_analysis(next_summary, chain, max_pain, spot),
        "oiSupplement": {
            "provider": "Yahoo 股市台灣選擇權",
            "sourceUrl": yahoo_url,
            "matchedExpiry": yahoo_expiry,
            "tradeDate": yahoo_payload.get("tradeDate"),
        },
        "source": {
            **(next_payload.get("source") or {}),
            "primary": "TAIFEX 選擇權每日交易行情查詢",
            "intradayOiProvider": "Yahoo 股市台灣選擇權盤中未平倉",
            "intradayOiUrl": yahoo_url,
            "oiNote": "TAIFEX 官方日報盤中未平倉若為 0，系統以同到期月份 Yahoo 盤中選擇權鏈補入 OI，不匹配月份不補值。",
        },
    }
    next_expirations = []
    for item in payload.get("expirations") or []:
        if str(item.get("code") or "") == selected:
            next_expirations.append({**item, **next_summary})
        else:
            next_expirations.append(item)
    next_payload["expirations"] = next_expirations
    return next_payload


def apply_yahoo_quote(stock: dict[str, Any]) -> dict[str, Any]:
    if stock.get("market") != "TPEx":
        return stock

    try:
        chart = fetch_yahoo_chart(stock["code"], range_name="1d", interval="1m")
    except Exception:  # noqa: BLE001
        return stock
    if not chart:
        return stock

    meta = chart.get("meta") or {}
    quotes = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    opens = [value for value in quotes.get("open", []) if value is not None]
    close_value = parse_float(str(meta.get("regularMarketPrice", "")))
    previous_close = parse_float(str(meta.get("chartPreviousClose", "")))
    signed_change = close_value - previous_close if close_value is not None and previous_close is not None else None
    pct = (signed_change / previous_close) * 100 if signed_change is not None and previous_close not in (None, 0) else None

    updated = dict(stock)
    updated.update(
        {
            "open": f"{opens[0]:,.2f}" if opens else stock.get("open", "--"),
            "high": format_signed(parse_float(str(meta.get("regularMarketDayHigh", "")))).lstrip("+"),
            "low": format_signed(parse_float(str(meta.get("regularMarketDayLow", "")))).lstrip("+"),
            "close": format_signed(close_value).lstrip("+"),
            "change": format_signed(signed_change),
            "pct": format_percent(pct),
            "volume": format_whole_number(parse_float(str(meta.get("regularMarketVolume", "")))),
            "tone": detect_tone(signed_change),
            "quoteSource": "Yahoo奇摩股市",
            "yahooSymbol": str(meta.get("symbol") or f"{stock['code']}.TWO"),
        }
    )
    return updated


def global_market_refresh_requested() -> bool:
    try:
        return request.args.get("refresh") in {"1", "true", "yes"}
    except RuntimeError:
        return False


def derivative_request_limit(default: int = 24, maximum: int = 100) -> int:
    raw_limit = str(request.args.get("limit") or default).strip().lower()
    if raw_limit in {"all", "full", "0"}:
        return maximum
    try:
        requested = int(raw_limit)
    except ValueError:
        requested = default
    return min(max(requested, 1), maximum)


@app.route("/api/index")
def api_derivatives_index():
    try:
        futures = build_global_market_payload("futures", min(12, derivative_request_limit(12, 24)))
        options = build_global_market_payload("options", min(12, derivative_request_limit(12, 24)))
        chain = options.get("taiwanOptionChain") or {}
        return jsonify(api_success_payload({
            "futures": futures.get("summary") or {},
            "options": options.get("summary") or {},
            "taiwanOption": {
                "tradeDate": chain.get("tradeDate"),
                "expiry": chain.get("selectedExpiry"),
                "summary": chain.get("summary") or {},
                "analysis": chain.get("analysis") or {},
            },
            "sources": {"futures": futures.get("source"), "options": options.get("source")},
        }))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/derivatives/v1-status")
def api_derivatives_v1_status():
    futures_items = [apply_taifex_defaults(item, TAIFEX_FUTURES_DAILY_URL, TAIFEX_OPTIONS_DAILY_URL) for item in TAIWAN_FUTURES_V1]
    option_items = [apply_taifex_defaults(item, TAIFEX_FUTURES_DAILY_URL, TAIFEX_OPTIONS_DAILY_URL) for item in TAIWAN_OPTIONS_V1]
    institutional_count = len(DERIVATIVES_STORE.institutional_positions(str(request.args.get("product") or "TX").strip().upper(), 200))
    return jsonify(api_success_payload({
        "version": "V1.0",
        "scope": "domestic_derivatives",
        "futures": futures_items,
        "options": option_items,
        "coverage": v1_product_status(futures_items, option_items),
        "institutionImport": {
            "endpoint": "/api/institution/import",
            "formats": ["JSON rows", "CSV"],
            "requiredFields": ["institution", "product_code", "trade_date"],
            "optionalFields": ["long_contracts", "short_contracts", "net_contracts"],
            "currentProductRows": institutional_count,
        },
        "aiScoreFormula": {
            "marketScore": "Options: PCR, Volume PCR, Max Pain gap, OI wall; Futures: price change. All scores clamped 0-100.",
            "riskScore": "Options: PCR imbalance, Volume PCR imbalance, Max Pain gap and OI wall break; Futures: downside momentum and OI availability.",
            "confidenceScore": "Count of available evidence layers plus chain/candle depth bonus.",
            "sourcePendingPenalty": "Missing evidence lowers confidence and raises data-risk messaging; no fake data is generated.",
        },
        "basis": {
            "endpoint": "/api/basis?future=TX&spot=TAIEX",
            "formula": "basis = futurePrice - spotPrice; basisPct = basis / spotPrice * 100",
        },
    }))


@app.route("/api/futures")
def api_futures():
    category_filter = str(request.args.get("category") or "").strip().lower()
    sort_key = str(request.args.get("sort") or "").strip().lower()
    try:
        payload = build_global_market_payload("futures", derivative_request_limit())
        items = [normalize_futures_yahoo_uncovered_links(item) for item in list(payload.get("items") or [])]
        if category_filter:
            items = [item for item in items if category_filter in f"{item.get('type', '')} {item.get('group', '')}".lower()]
        if sort_key in {"pct", "change", "volume", "open_interest"}:
            field = "openInterest" if sort_key == "open_interest" else sort_key
            items.sort(key=lambda item: parse_float(str(item.get(field) or "")) or float("-inf"), reverse=True)
        return jsonify(api_success_payload({**payload, "items": items, "count": len(items)}))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/futures/<symbol>")
def api_future_detail(symbol: str):
    spec = find_derivative_spec("futures", symbol)
    if not spec:
        return jsonify(api_error_payload("INVALID_SYMBOL", "商品代碼不存在")), 404
    try:
        item = build_global_market_item(spec)
        if item.get("error"):
            return jsonify(api_error_payload("EMPTY_RESULT", str(item.get("error")))), 200
        return jsonify(api_success_payload(item))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/futures/<symbol>/candles")
def api_future_candles(symbol: str):
    interval = str(request.args.get("interval") or "day").strip().lower()
    if interval not in {"day", "week", "month", "all"}:
        return jsonify(api_error_payload("INVALID_DATE", "interval 僅支援 day、week、month、all")), 400
    spec = find_derivative_spec("futures", symbol)
    if not spec:
        return jsonify(api_error_payload("INVALID_SYMBOL", "商品代碼不存在")), 404
    try:
        if spec.get("dataProvider") in {"taifex_tx_open_interest", "taifex_txo_open_interest", "taifex_futures_open_interest"}:
            commodity = str(spec.get("taifexCommodity") or spec.get("symbol") or symbol).strip().upper()
            candles = fetch_taifex_futures_price_candles(commodity, max_observations=30)
            if interval not in {"day", "all"}:
                candles = build_derivative_candles({"series": [
                    {
                        "date": row.get("time"),
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "volume": row.get("volume"),
                    }
                    for row in candles
                ]}, interval)
            if not candles:
                fallback_item = build_global_market_item(spec)
                fallback_candles = build_derivative_candles(fallback_item, interval)
                if fallback_candles:
                    return jsonify(api_success_payload({
                        "symbol": spec.get("symbol"),
                        "interval": interval,
                        "candles": fallback_candles,
                        "source": fallback_item.get("source") or "期貨商品既有序列",
                    }))
                return jsonify(api_error_payload("EMPTY_RESULT", "TAIFEX 官方 K 線資料暫時無法載入")), 200
            return jsonify(api_success_payload({"symbol": spec.get("symbol"), "interval": interval, "candles": candles, "source": "TAIFEX 官方期貨每日交易行情"}))
        item = build_global_market_item(spec)
        candles = build_derivative_candles(item, interval)
        if not candles:
            return jsonify(api_error_payload("EMPTY_RESULT", str(item.get("error") or "查無 K 線資料"))), 200
        return jsonify(api_success_payload({"symbol": item.get("symbol"), "interval": interval, "candles": candles, "source": item.get("source")}))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/options")
def api_options():
    underlying = str(request.args.get("underlying") or "TXO").strip().upper()
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    if underlying in {"STO", "ETO"}:
        spec = find_derivative_spec("options", underlying)
        if not spec:
            return jsonify(api_error_payload("INVALID_SYMBOL", "商品代碼不存在")), 404
        item = build_global_market_item(spec)
        chain_status = "source_pending" if item.get("status") == "source_pending" or item.get("error") else "aggregate_connected"
        return jsonify(api_success_payload({
            "underlying": underlying,
            "products": [item],
            "selectedExpiry": None,
            "expirations": [],
            "optionChainSource": {
                "primary": item.get("dataSource") or spec.get("dataSource"),
                "primaryUrl": item.get("sourceLink") or spec.get("sourceUrl"),
                "status": chain_status,
            },
            "message": item.get("dataStatus") or item.get("error") or "TAIFEX 標的選擇權目前僅提供未平倉量／成交量彙總，尚未提供逐履約價選擇權鏈。",
        }))
    if underlying not in TAIWAN_OPTION_PRODUCTS:
        supported = "、".join(TAIWAN_OPTION_PRODUCTS.keys())
        return jsonify(api_error_payload("INVALID_SYMBOL", f"目前國內選擇權鏈支援 {supported}；STO/ETO 以彙總資料揭露")), 400
    try:
        payload = build_global_market_payload("options", derivative_request_limit(default=100), option_source=source, option_underlying=underlying)
        chain = payload.get("taiwanOptionChain") or {}
        if chain.get("error"):
            chain = build_derivatives_unavailable_option_chain(str(chain.get("error")), TAIFEX_OPTIONS_DAILY_URL, underlying)
            payload["taiwanOptionChain"] = chain
        return jsonify(api_success_payload({
            **payload,
            "underlying": underlying,
            "products": payload.get("items") or [],
            "expirations": chain.get("expirations") or [],
            "selectedExpiry": chain.get("selectedExpiry"),
            "optionChainSource": chain.get("source") or {},
        }))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/open-interest")
def api_open_interest():
    symbol = str(request.args.get("symbol") or "TXO").strip().upper()
    date = str(request.args.get("date") or "").strip() or None
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        if symbol in TAIWAN_OPTION_PRODUCTS:
            data = fetch_txo_option_chain(market_date=date, source=source, underlying=symbol)
            if data.get("error"):
                return jsonify(api_error_payload("EMPTY_RESULT", str(data.get("error")))), 200
            summary = data.get("summary") or {}
            return jsonify(api_success_payload({
                "symbol": symbol,
                "tradeDate": data.get("tradeDate"),
                "callOpenInterest": summary.get("callOpenInterest"),
                "putOpenInterest": summary.get("putOpenInterest"),
                "putCallRatio": summary.get("putCallRatio"),
                "distribution": data.get("distribution") or [],
                "source": data.get("source") or {},
            }))
        spec = find_derivative_spec("futures", symbol)
        if not spec or not str(spec.get("dataProvider") or "").startswith("taifex_"):
            return jsonify(api_error_payload("INVALID_SYMBOL", "目前僅支援 TAIFEX 期貨或國內官方選擇權鏈")), 400
        item = build_global_market_item(spec)
        if item.get("error"):
            return jsonify(api_error_payload("EMPTY_RESULT", str(item.get("error")))), 200
        return jsonify(api_success_payload({
            "symbol": symbol,
            "tradeDate": item.get("date"),
            "openInterest": item.get("openInterest"),
            "previousOpenInterest": item.get("previousOpenInterest"),
            "change": item.get("change"),
            "changePct": item.get("pct"),
            "source": item.get("sourceLink") or item.get("sourceUrl"),
        }))
    except ValueError:
        return jsonify(api_error_payload("INVALID_DATE", "日期格式需為 YYYYMMDD 或 YYYY-MM-DD")), 400
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/institution")
def api_institutional_position():
    product = str(request.args.get("product") or "TX").strip().upper()
    rows = DERIVATIVES_STORE.institutional_positions(product)
    if rows:
        payload = build_institution_payload_from_rows(product, rows, TAIFEX_FUTURES_DAILY_URL)
    else:
        is_option = product in {"TXO", "STO", "ETO"}
        source_url = TAIFEX_INSTITUTION_OPTIONS_DETAIL_OPENAPI_URL if is_option else TAIFEX_INSTITUTION_FUTURES_DETAIL_OPENAPI_URL
        payload = build_institution_payload_live(product, source_url) or build_pending_institution_payload(product, TAIFEX_FUTURES_DAILY_URL)
    return jsonify(api_success_payload(payload))


@app.route("/api/institution/import", methods=["POST"])
def api_institution_import():
    if not is_authorized_derivatives_admin():
        return jsonify(api_error_payload("ADMIN_AUTH_REQUIRED", "法人資料匯入需提供有效管理金鑰")), 403
    rows: list[dict[str, Any]] = []
    if request.is_json:
        body = request.get_json(silent=True) or {}
        raw_rows = body.get("rows") if isinstance(body, dict) else None
        if isinstance(raw_rows, list):
            rows = [normalize_institution_row(row) for row in raw_rows if isinstance(row, dict)]
        elif isinstance(body, dict) and "csv" in body:
            rows = parse_institution_csv(str(body.get("csv") or ""))
    else:
        rows = parse_institution_csv(request.get_data(as_text=True) or "")
    rows = [row for row in rows if row.get("institution") and row.get("product_code") and row.get("trade_date")]
    if not rows:
        return jsonify(api_error_payload("INVALID_PAYLOAD", "請提供 rows JSON 或 CSV，欄位需含 institution/product_code/trade_date")), 400
    inserted = DERIVATIVES_STORE.record_institutional_positions(rows)
    product = str(rows[0].get("product_code") or "").upper()
    payload = build_institution_payload_from_rows(product, DERIVATIVES_STORE.institutional_positions(product), TAIFEX_FUTURES_DAILY_URL)
    return jsonify(api_success_payload({"inserted": inserted, "product": product, "institution": payload}))


@app.route("/api/basis")
def api_basis():
    future_symbol = str(request.args.get("future") or "TX").strip().upper()
    spot_symbol = str(request.args.get("spot") or "TAIEX").strip().upper()
    if spot_symbol not in {"TAIEX", "TWII", "加權指數"}:
        return jsonify(api_error_payload("INVALID_SYMBOL", "spot 目前支援 TAIEX 台灣加權指數")), 400
    spec = find_derivative_spec("futures", future_symbol)
    if not spec:
        return jsonify(api_error_payload("INVALID_SYMBOL", "期貨商品代碼不存在")), 404
    try:
        future_item = build_global_market_item(spec)
        spot_snapshot = fetch_taiex_spot_snapshot()
        history = []
        future_series = future_item.get("series") or []
        spot_value = parse_float(str(spot_snapshot.get("value") or ""))
        for row in future_series[-20:]:
            future_close = parse_float(str(row.get("close") or ""))
            basis = future_close - spot_value if future_close is not None and spot_value is not None else None
            history.append({
                "date": row.get("date") or row.get("time"),
                "futurePrice": future_close,
                "spotPrice": spot_value,
                "basis": basis,
                "basisPct": (basis / spot_value * 100) if basis is not None and spot_value else None,
            })
        payload = build_basis_payload(future_item, spot_snapshot, history)
        return jsonify(api_success_payload(payload))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/news")
def api_derivatives_news():
    category = str(request.args.get("category") or "derivatives").strip().lower()
    symbol = str(request.args.get("symbol") or "^VIX").strip().upper()
    limit = derivative_request_limit(8, 20)
    try:
        items = fetch_yahoo_us_symbol_news(symbol, limit)
        if not items:
            return jsonify(api_error_payload("EMPTY_RESULT", "目前查無市場新聞資料")), 200
        for item in items:
            item.setdefault("summary", "公開新聞標題與來源，請開啟連結查看完整內容。")
        DERIVATIVES_STORE.record_news(category, items)
        return jsonify(api_success_payload({"category": category, "symbol": symbol, "items": items, "count": len(items)}))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/ai-analysis")
def api_derivatives_ai_analysis():
    target = str(request.args.get("target") or "TXO").strip().upper()
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        if target in TAIWAN_OPTION_PRODUCTS:
            data = fetch_txo_option_chain(expiry=str(request.args.get("expiry") or "").strip() or None, source=source, underlying=target)
            if data.get("error"):
                analysis = build_derivatives_unavailable_ai_analysis(target, str(data.get("error")))
                return jsonify(api_success_payload(analysis))
            analysis = data.get("analysis") or {}
        else:
            spec = find_derivative_spec("futures", target)
            if not spec:
                return jsonify(api_error_payload("INVALID_SYMBOL", "商品代碼不存在")), 404
            item = build_global_market_item(spec)
            if item.get("error"):
                analysis = build_derivatives_unavailable_ai_analysis(target, str(item.get("error")))
                return jsonify(api_success_payload(analysis))
            analysis = build_futures_ai_analysis(item)
        DERIVATIVES_STORE.record_ai_report(target, analysis, datetime.now(TZ).isoformat())
        return jsonify(api_success_payload(analysis))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/futures/<symbol>/technical-candles")
def api_future_technical_candles(symbol: str):
    interval = str(request.args.get("interval") or "day").strip().lower()
    if interval not in {"day", "week", "month", "all"}:
        return jsonify(api_error_payload("INVALID_DATE", "interval 只能是 day、week、month 或 all")), 400
    spec = find_derivative_spec("futures", symbol)
    if not spec:
        return jsonify(api_error_payload("INVALID_SYMBOL", "期貨商品不存在")), 404
    commodity = str(spec.get("taifexCommodity") or spec.get("symbol") or symbol).strip().upper()
    code = str(request.args.get("code") or "").strip().upper()
    try:
        payload = fetch_taifex_futures_technical_candles(commodity, code=code, interval=interval)
        if payload.get("error"):
            return jsonify(api_error_payload("EMPTY_RESULT", str(payload.get("error")))), 200
        if not payload.get("candles"):
            contract = payload.get("contract") or {}
            label = contract.get("label") or payload.get("code") or code or commodity
            month = payload.get("contractMonth") or "主力連續"
            return jsonify(api_error_payload(
                "EMPTY_RESULT",
                f"{commodity} {label}（{month}）目前沒有足夠的 TAIFEX K 線資料。",
            )), 200
        return jsonify(api_success_payload(payload))
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@app.route("/api/options/chain")
def api_options_chain():
    underlying = normalize_taiwan_option_underlying(str(request.args.get("underlying") or "TXO"))
    expiry = str(request.args.get("expiry") or "").strip() or None
    date = str(request.args.get("date") or "").strip() or None
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        data = fetch_txo_option_chain(expiry=expiry, market_date=date, source=source, underlying=underlying)
    except ValueError:
        return jsonify(api_error_payload("INVALID_DATE", "日期格式需為 YYYYMMDD 或 YYYY-MM-DD")), 400
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)
    if data.get("error"):
        return jsonify(api_success_payload(build_derivatives_unavailable_option_chain(str(data.get("error")), TAIFEX_OPTIONS_DAILY_URL, underlying)))
    DERIVATIVES_STORE.record_option_chain(data, datetime.now(TZ).isoformat())
    return jsonify(api_success_payload(data))


@app.route("/api/pcr")
def api_options_pcr():
    underlying = normalize_taiwan_option_underlying(str(request.args.get("underlying") or "TXO"))
    expiry = str(request.args.get("expiry") or "").strip() or None
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        data = fetch_txo_option_chain(expiry=expiry, market_date=str(request.args.get("date") or "").strip() or None, source=source, underlying=underlying)
    except ValueError:
        return jsonify(api_error_payload("INVALID_DATE", "日期格式需為 YYYYMMDD 或 YYYY-MM-DD")), 400
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)
    if data.get("error"):
        data = build_derivatives_unavailable_option_chain(str(data.get("error")), TAIFEX_OPTIONS_DAILY_URL, underlying)
        summary = data.get("summary") or {}
        return jsonify(api_success_payload({
            "underlying": underlying,
            "expiry": None,
            "tradeDate": None,
            "putCallRatio": summary.get("putCallRatio"),
            "volumePutCallRatio": summary.get("volumePutCallRatio"),
            "putOpenInterest": summary.get("putOpenInterest"),
            "callOpenInterest": summary.get("callOpenInterest"),
            "history": DERIVATIVES_STORE.option_pcr_history(underlying),
            "source": (data.get("source") or {}).get("primary"),
            "status": data.get("status"),
            "message": data.get("message"),
        }))
    DERIVATIVES_STORE.record_option_chain(data, datetime.now(TZ).isoformat())
    summary = data.get("summary") or {}
    return jsonify(api_success_payload({
        "underlying": underlying,
        "expiry": data.get("selectedExpiry"),
        "tradeDate": data.get("tradeDate"),
        "putCallRatio": summary.get("putCallRatio"),
        "volumePutCallRatio": summary.get("volumePutCallRatio"),
        "putOpenInterest": summary.get("putOpenInterest"),
        "callOpenInterest": summary.get("callOpenInterest"),
        "history": DERIVATIVES_STORE.option_pcr_history(underlying),
        "source": (data.get("source") or {}).get("primary"),
    }))


@app.route("/api/maxpain")
def api_options_maxpain():
    underlying = normalize_taiwan_option_underlying(str(request.args.get("underlying") or "TXO"))
    expiry = str(request.args.get("expiry") or "").strip() or None
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        data = fetch_txo_option_chain(expiry=expiry, market_date=str(request.args.get("date") or "").strip() or None, source=source, underlying=underlying)
    except ValueError:
        return jsonify(api_error_payload("INVALID_DATE", "日期格式需為 YYYYMMDD 或 YYYY-MM-DD")), 400
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("DATA_SOURCE_ERROR", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)
    if data.get("error"):
        data = build_derivatives_unavailable_option_chain(str(data.get("error")), TAIFEX_OPTIONS_DAILY_URL, underlying)
        summary = data.get("summary") or {}
        analysis = data.get("analysis") or {}
        return jsonify(api_success_payload({
            "underlying": underlying,
            "expiry": None,
            "tradeDate": None,
            "maxPain": summary.get("maxPain"),
            "maxPainLoss": summary.get("maxPainLoss"),
            "supportLevel": analysis.get("supportLevel"),
            "resistanceLevel": analysis.get("resistanceLevel"),
            "source": (data.get("source") or {}).get("primary"),
            "status": data.get("status"),
            "message": data.get("message"),
        }))
    DERIVATIVES_STORE.record_option_chain(data, datetime.now(TZ).isoformat())
    summary = data.get("summary") or {}
    analysis = data.get("analysis") or {}
    return jsonify(api_success_payload({
        "underlying": underlying,
        "expiry": data.get("selectedExpiry"),
        "tradeDate": data.get("tradeDate"),
        "maxPain": summary.get("maxPain"),
        "maxPainLoss": summary.get("maxPainLoss"),
        "supportLevel": analysis.get("supportLevel"),
        "resistanceLevel": analysis.get("resistanceLevel"),
        "source": (data.get("source") or {}).get("primary"),
    }))


@app.errorhandler(404)
def handle_not_found(error):
    if request.path.startswith("/api/"):
        return jsonify(api_error_payload("NOT_FOUND", "找不到指定的 API 或資源")), 404
    return str(getattr(error, "description", "Not Found")), 404


@app.errorhandler(500)
def handle_internal_error(error):
    LOGGER.exception("Unhandled server error", exc_info=error)
    if request.path.startswith("/api/"):
        return jsonify(api_error_payload("INTERNAL_ERROR", "服務暫時無法處理請求")), 500
    return "Internal Server Error", 500


if __name__ == "__main__":
    if background_updater_enabled():
        start_background_updater()
    app.run(
        host=os.environ.get("MARKET_PULSE_HOST", "127.0.0.1"),
        port=int(os.environ.get("MARKET_PULSE_PORT", "5000")),
        debug=False,
        threaded=True,
    )
else:
    # When loaded by a WSGI server (gunicorn, uWSGI, etc.) we still need
    # to spin up the background updater.
    if background_updater_enabled():
        start_background_updater()
