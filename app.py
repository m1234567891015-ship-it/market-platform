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

from flask import Flask, Response, abort, jsonify, redirect, request, send_from_directory
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
    fetch_international_market_indexes,
    fetch_json,
    fetch_live_index_activity,
    fetch_live_index_intraday,
    fetch_live_stock_search_results,
    fetch_live_stock_universe,
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
    fetch_shareholder_distribution,
    fetch_stock_company_profile,
    fetch_stock_history_rows,
    fetch_stock_institutional_trades,
    fetch_stock_institutional_trade_for_date,
    fetch_stock_institutional_trade_history,
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
    fetch_yahoo_institutional_trading,
    fetch_yahoo_major_holders,
    fetch_yahoo_margin_accumulation_rows,
    fetch_yahoo_margin_period_rows,
    fetch_yahoo_margin_trading,
    fetch_yahoo_options_payload,
    fetch_yahoo_quote_summary,
    fetch_yahoo_sector_catalog,
    fetch_yahoo_spot_snapshot,
    fetch_yahoo_symbol_chart,
    fetch_yahoo_taiwan_future_quote,
    fetch_yahoo_taiwan_future_quotes,
    fetch_yahoo_tpex_etfs,
    fetch_yahoo_trading_dates_for_institutional_range,
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
    get_institutional_history_range_config,
    is_etf_stock,
    is_finite_positive,
    is_valid_ohlc_values,
    normalize_market_request,
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
    STOCK_HISTORY_MAX_MONTHS,
    STOCK_HISTORY_RECENT_MONTHS,
    build_all_market_penny_sector_recommendations,
    build_derivative_candles,
    build_futures_ai_analysis,
    build_index_technical_analysis,
    build_institution_payload_live,
    build_institution_summary,
    build_institution_trend,
    build_global_market_item,
    build_global_market_payload,
    build_institutional_history_from_yahoo,
    build_institutional_trade_candidate_dates,
    build_institutions_url,
    build_intraday_index_candles,
    build_intraday_technical_analysis,
    build_latest_stock_institutional_trade,
    build_news,
    build_public_options_chain,
    build_sector_fund_flow,
    build_sector_history_series,
    build_site_data_view,
    build_stock_detail,
    build_stock_institutional_trade_record,
    build_stock_institutional_trade_summary,
    build_stock_search_url,
    build_stocks_view,
    build_summary_cards_from_payload,
    build_taifex_open_interest_item,
    build_taifex_option_ai_analysis,
    build_taifex_option_chain,
    build_taifex_option_distribution,
    build_taifex_stock_derivative_aggregate_item,
    build_taifex_txo_option_payload,
    build_txo_option_market_item,
    build_us_etf_center_payload,
    build_us_market_symbol_detail,
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
from market_config import (
    ASSET_STATIC_FILES,
    CBOE_OPTIONS_BASE,
    EXCLUDED_SECTOR_SOURCE_NAMES,
    GLOBAL_MARKET_CACHE_SECONDS,
    GLOBAL_MARKET_CATEGORIES,
    GLOBAL_MARKET_DEFAULT_LOAD_LIMIT,
    GLOBAL_MARKET_MAX_LOAD_LIMIT,
    INDEX_DISPLAY_NAMES,
    INTERNATIONAL_INDEX_SPECS,
    LISTED_SECTOR_INDEX_ORDER,
    LISTED_SECTOR_INDEX_SPECS,
    NASDAQ_API_BASE,
    NASDAQ_USER_AGENT,
    PAGE_ROUTES,
    ROOT_STATIC_FILES,
    SECTOR_INDEX_DISPLAY_NAMES,
    TAIFEX_FUTURES_DAILY_URL,
    TAIFEX_OPTIONS_DAILY_URL,
    TAIFEX_OPTIONS_PC_RATIO_URL,
    TARGET_INDEX_NAMES,
    TPEX_OPENAPI_BASE,
    TWSE_BASE,
    TWSE_MARGIN_URL,
    US_MARKET_SEARCH_UNIVERSE,
    US_SECTOR_STOCK_GROUPS,
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
    YAHOO_TPEX_ETF_URL,
    YAHOO_TPEX_OTC_CLASS_URL,
)


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
SECTOR_CHART_CACHE_SECONDS = 300
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


YAHOO_TW_FUTURE_URL = "https://tw.stock.yahoo.com/future"
YAHOO_TW_FUTURE_UNCOVERED_URL = "https://tw.stock.yahoo.com/future/futures_uncovered.html"
YAHOO_TW_OPTION_URL = "https://tw.stock.yahoo.com/future/options.html"
YAHOO_TW_OPTION_WTXO_URL = f"{YAHOO_TW_OPTION_URL}?opmr=optionfull&opcm=WTXO"
TAIWAN_OPTION_PRODUCTS = {
    "TXO": {
        "name": "臺指選擇權",
        "shortName": "台指選",
        "taifexCommodity": "TXO",
        "yahooOpcm": "WTXO",
        "yahooLabelPrefix": "台指",
        "spotSymbol": "^TWII",
        "spotName": "台灣加權指數",
    },
    "MXO": {
        "name": "小型臺指選擇權",
        "shortName": "小台選",
        "taifexCommodity": "TXO",
        "yahooOpcm": None,
        "yahooLabelPrefix": "小台",
        "spotSymbol": "^TWII",
        "spotName": "台灣加權指數",
        "sourceAliasOf": "TXO",
        "sourceNote": "TAIFEX 目前未列獨立小型臺指選擇權逐履約價，系統以同標的臺指選擇權 TXO 官方鏈作風險參照。",
    },
    "TFO": {
        "name": "金融選擇權",
        "shortName": "金指選",
        "taifexCommodity": "TFO",
        "yahooOpcm": "WTFO",
        "yahooLabelPrefix": "金指",
        "spotSymbol": None,
        "spotName": "金融保險類指數",
    },
    "TEO": {
        "name": "電子選擇權",
        "shortName": "電指選",
        "taifexCommodity": "TEO",
        "yahooOpcm": "WTEO",
        "yahooLabelPrefix": "電指",
        "spotSymbol": None,
        "spotName": "電子類指數",
    },
    "CDO": {
        "name": "台積電選擇權",
        "shortName": "台積電選",
        "taifexCommodity": "CDO",
        "yahooOpcm": None,
        "yahooLabelPrefix": "台積電",
        "spotSymbol": "2330.TW",
        "spotName": "台積電",
    },
    "DVO": {
        "name": "聯發科選擇權",
        "shortName": "聯發科選",
        "taifexCommodity": "DVO",
        "yahooOpcm": None,
        "yahooLabelPrefix": "聯發科",
        "spotSymbol": "2454.TW",
        "spotName": "聯發科",
    },
    "DHO": {
        "name": "鴻海選擇權",
        "shortName": "鴻海選",
        "taifexCommodity": "DHO",
        "yahooOpcm": None,
        "yahooLabelPrefix": "鴻海",
        "spotSymbol": "2317.TW",
        "spotName": "鴻海",
    },    "T50O": {
        "name": "臺灣50選擇權",
        "shortName": "臺灣50選",
        "taifexCommodity": "NYO",
        "yahooOpcm": None,
        "yahooLabelPrefix": "臺灣50",
        "spotSymbol": "0050.TW",
        "spotName": "元大台灣50 ETF",
        "sourceAliasOf": "NYO",
        "sourceNote": "TAIFEX 官方商品代碼為 NYO（元大台灣50 ETF 選擇權），畫面以 T50O 顯示方便辨識。",
    },
}
TAIWAN_OPTION_DEFAULT_PRODUCT = "TXO"
YAHOO_TW_FUTURE_CODE_TO_SYMBOL = {
    "WTX&": "TX",
    "WMT&": "MTX",
    "WTE&": "TE",
    "WTF&": "TF",
    "WXI&": "XIF",
    "WGT&": "SOF",
}
YAHOO_TW_FUTURE_CODE_PREFIX_TO_SYMBOL = {
    "WTX": "TX",
    "WMT": "MTX",
    "TMF": "TMF",
    "WTE": "TE",
    "WTF": "TF",
    "WXI": "XIF",
    "WGT": "SOF",
}
YAHOO_TW_FUTURE_TECHNICAL_GROUPS = {
    "TX": {
        "name": "台指期",
        "primaryCode": "WTX&",
        "contracts": [
            ("近一", "WTX&", "near"),
            ("近二", "WTX@", "near"),
            ("現貨", "WTX00", "spot"),
            ("2607", "WTXN6", "month"),
            ("2608", "WTXQ6", "month"),
            ("2609", "WTXU6", "month"),
            ("2612", "WTXZ6", "month"),
            ("2703", "WTXH7", "month"),
            ("2706", "WTXM7", "month"),
        ],
    },
    "MTX": {
        "name": "小台指",
        "primaryCode": "WMT&",
        "contracts": [
            ("近一", "WMT&", "near"),
            ("近二", "WMT@", "near"),
            ("現貨", "WMT00", "spot"),
            ("2607", "WMTN6", "month"),
            ("2608", "WMTQ6", "month"),
            ("2609", "WMTU6", "month"),
            ("2612", "WMTZ6", "month"),
            ("2703", "WMTH7", "month"),
            ("2706", "WMTM7", "month"),
        ],
    },
    "TMF": {
        "name": "微型臺指",
        "primaryCode": "TMF",
        "source": "TAIFEX 官方期貨每日行情下載",
        "sourceUrl": TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
        "contracts": [
            ("主力", "TMF", "near"),
            ("2607", "TMFN6", "month"),
            ("2608", "TMFQ6", "month"),
            ("2609", "TMFU6", "month"),
            ("2612", "TMFZ6", "month"),
            ("2703", "TMFH7", "month"),
            ("2706", "TMFM7", "month"),
        ],
    },
    "TE": {
        "name": "電子期",
        "primaryCode": "WTE&",
        "contracts": [
            ("近一", "WTE&", "near"),
            ("近二", "WTE@", "near"),
            ("現貨", "WTE00", "spot"),
            ("2607", "WTEN6", "month"),
            ("2608", "WTEQ6", "month"),
            ("2609", "WTEU6", "month"),
            ("2612", "WTEZ6", "month"),
            ("2703", "WTEH7", "month"),
            ("2706", "WTEM7", "month"),
        ],
    },
    "TF": {
        "name": "金融期",
        "primaryCode": "WTF&",
        "contracts": [
            ("近一", "WTF&", "near"),
            ("近二", "WTF@", "near"),
            ("現貨", "WTF00", "spot"),
            ("2607", "WTFN6", "month"),
            ("2608", "WTFQ6", "month"),
            ("2609", "WTFU6", "month"),
            ("2612", "WTFZ6", "month"),
            ("2703", "WTFH7", "month"),
            ("2706", "WTFM7", "month"),
        ],
    },
    "XIF": {
        "name": "非金電期",
        "primaryCode": "WXI&",
        "contracts": [
            ("近一", "WXI&", "near"),
            ("近二", "WXI@", "near"),
            ("現貨", "WXI00", "spot"),
            ("2607", "WXIN6", "month"),
            ("2608", "WXIQ6", "month"),
            ("2609", "WXIU6", "month"),
            ("2612", "WXIZ6", "month"),
            ("2703", "WXIH7", "month"),
            ("2706", "WXIM7", "month"),
        ],
    },
    "SOF": {
        "name": "櫃買期",
        "primaryCode": "WGT&",
        "contracts": [
            ("近一", "WGT&", "near"),
            ("近二", "WGT@", "near"),
            ("現貨", "WGT00", "spot"),
            ("2607", "WGTN6", "month"),
            ("2608", "WGTQ6", "month"),
            ("2609", "WGTU6", "month"),
            ("2612", "WGTZ6", "month"),
            ("2703", "WGTH7", "month"),
            ("2706", "WGTM7", "month"),
        ],
    },
}

def merge_site_data_with_fallback(
    fresh_site_data: dict[str, Any],
    existing_site_data: dict[str, Any] | None,
) -> dict[str, Any]:
    if not existing_site_data:
        return fresh_site_data

    merged = dict(fresh_site_data)

    def keep_existing_list(key: str) -> None:
        fresh_value = merged.get(key)
        existing_value = existing_site_data.get(key)
        if isinstance(fresh_value, list) and fresh_value:
            return
        if isinstance(existing_value, list) and existing_value:
            merged[key] = existing_value

    keep_existing_list("sectors")
    keep_existing_list("institutions")
    keep_existing_list("marketOverview")
    keep_existing_list("news")

    fresh_sector_flow = merged.get("sectorFundFlow") or {}
    existing_sector_flow = existing_site_data.get("sectorFundFlow") or {}
    if (
        not (isinstance(fresh_sector_flow, dict) and fresh_sector_flow.get("rows"))
        and isinstance(existing_sector_flow, dict)
        and existing_sector_flow.get("rows")
    ):
        merged["sectorFundFlow"] = existing_sector_flow

    fresh_highlights = dict(merged.get("tpexHighlights") or {})
    existing_highlights = existing_site_data.get("tpexHighlights") or {}
    for key in ("mainboard", "emerging", "emergingStats"):
        fresh_value = fresh_highlights.get(key)
        existing_value = existing_highlights.get(key)
        if isinstance(fresh_value, list) and fresh_value:
            continue
        if isinstance(existing_value, list) and existing_value:
            fresh_highlights[key] = existing_value
    if fresh_highlights:
        merged["tpexHighlights"] = fresh_highlights

    fresh_yahoo_groups = dict(merged.get("yahooSectorGroups") or {})
    existing_yahoo_groups = existing_site_data.get("yahooSectorGroups") or {}
    for key in ("listed", "otc", "emerging", "electronic", "concept", "group"):
        fresh_value = fresh_yahoo_groups.get(key)
        existing_value = existing_yahoo_groups.get(key)
        if isinstance(fresh_value, list) and fresh_value:
            continue
        if isinstance(existing_value, list) and existing_value:
            fresh_yahoo_groups[key] = existing_value
    if fresh_yahoo_groups:
        merged["yahooSectorGroups"] = fresh_yahoo_groups

    fresh_yahoo_catalog = dict(merged.get("yahooSectorCatalog") or {})
    existing_yahoo_catalog = existing_site_data.get("yahooSectorCatalog") or {}
    for key in ("listed", "otc", "emerging", "electronic", "concept", "group"):
        fresh_value = fresh_yahoo_catalog.get(key)
        existing_value = existing_yahoo_catalog.get(key)
        if isinstance(fresh_value, list) and fresh_value:
            continue
        if isinstance(existing_value, list) and existing_value:
            fresh_yahoo_catalog[key] = existing_value
    if fresh_yahoo_catalog:
        merged["yahooSectorCatalog"] = fresh_yahoo_catalog

    if not merged.get("marketVolatility") and existing_site_data.get("marketVolatility"):
        merged["marketVolatility"] = existing_site_data["marketVolatility"]
    if not merged.get("marketInternationalIndexes") and existing_site_data.get("marketInternationalIndexes"):
        merged["marketInternationalIndexes"] = existing_site_data["marketInternationalIndexes"]
    fresh_macro = dict(merged.get("marketMacroFactors") or {})
    existing_macro = existing_site_data.get("marketMacroFactors") or {}
    for key in ("dxy", "us10y", "usdTwd", "marginTrading", "txOpenInterest"):
        if not fresh_macro.get(key) and existing_macro.get(key):
            fresh_macro[key] = existing_macro[key]
    if fresh_macro:
        merged["marketMacroFactors"] = fresh_macro

    return merged


def taipei_now() -> datetime:
    return datetime.now(TZ)


def classify_tpex_security(code: str, yahoo_etf_codes: set[str]) -> tuple[str | None, str | None]:
    if code in yahoo_etf_codes or re.fullmatch(r"00[A-Z0-9]{4}", code, re.IGNORECASE):
        return "ETF", "上櫃ETF"
    if re.fullmatch(r"\d{4}A?", code, re.IGNORECASE):
        return "STOCK", "上櫃個股"
    return None, None


def merge_trade_counts(
    series: list[dict[str, str]],
    history_rows: list[list[str]],
) -> list[dict[str, str]]:
    trades_by_date: dict[str, str] = {}
    for row in history_rows:
        if len(row) <= 8:
            continue
        try:
            trade_date = parse_roc_date(str(row[0])).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        trades = format_whole_number(parse_float(str(row[8])))
        if trades != "--":
            trades_by_date[trade_date] = trades

    return [
        {**item, **({"trades": trades_by_date[item["date"]]} if item.get("date") in trades_by_date else {})}
        for item in series
    ]


def parse_yahoo_tw_future_date(value: Any) -> str:
    text = str(value or "").strip()
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text)
    if not match:
        return ""
    year, month, day = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def parse_yahoo_tw_future_number(value: Any) -> float | None:
    text = (
        str(value or "")
        .replace(",", "")
        .replace("%", "")
        .replace("+", "")
        .replace("−", "-")
        .strip()
    )
    if not text or text in {"-", "--"}:
        return None
    return parse_float(text)


def parse_yahoo_taiwan_future_quotes(html: str) -> dict[str, dict[str, Any]]:
    lines = [line.strip() for line in extract_visible_text_lines(html) if line.strip()]
    if not lines:
        return {}
    quote_date = ""
    for line in lines:
        if "資料時間" in line:
            quote_date = parse_yahoo_tw_future_date(line)
            if quote_date:
                break
    if not quote_date:
        quote_date = datetime.now(TZ).strftime("%Y-%m-%d")
    quotes: dict[str, dict[str, Any]] = {}
    row_width = 13
    for index, line in enumerate(lines):
        code = line.strip().upper()
        symbol = YAHOO_TW_FUTURE_CODE_TO_SYMBOL.get(code)
        if not symbol:
            continue
        values = lines[index + 1 : index + 1 + row_width]
        if len(values) < row_width:
            continue
        (
            bid_text,
            ask_text,
            last_text,
            change_text,
            pct_text,
            volume_text,
            open_text,
            high_text,
            low_text,
            basis_text,
            reference_text,
            open_interest_text,
            quote_time,
        ) = values
        close_value = parse_yahoo_tw_future_number(last_text)
        if close_value is None:
            continue
        quotes[symbol] = {
            "symbol": symbol,
            "yahooCode": code,
            "name": lines[index - 1] if index > 0 else symbol,
            "date": quote_date,
            "bid": parse_yahoo_tw_future_number(bid_text),
            "ask": parse_yahoo_tw_future_number(ask_text),
            "close": close_value,
            "change": parse_yahoo_tw_future_number(change_text),
            "changePct": parse_yahoo_tw_future_number(pct_text),
            "volume": parse_yahoo_tw_future_number(volume_text),
            "open": parse_yahoo_tw_future_number(open_text),
            "high": parse_yahoo_tw_future_number(high_text),
            "low": parse_yahoo_tw_future_number(low_text),
            "basis": parse_yahoo_tw_future_number(basis_text),
            "referencePrice": parse_yahoo_tw_future_number(reference_text),
            "openInterest": parse_yahoo_tw_future_number(open_interest_text),
            "quoteTime": quote_time,
            "sourceLink": YAHOO_TW_FUTURE_UNCOVERED_URL,
            "sourceNote": "Yahoo 股市即時期指報價，作為 TAIFEX 官方日報的盤中報價補強。",
        }
    return quotes


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


def parse_taifex_number(value: Any) -> float | None:
    cleaned = unescape(str(value or "")).replace(",", "").replace("%", "").strip()
    cleaned = cleaned.replace("▲", "").replace("▼", "").replace("△", "").replace("▽", "")
    cleaned = cleaned.replace("\u2212", "-")
    if cleaned in {"", "-", "--", "X", "x"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_taifex_contract_date(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 8:
        return ""
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def black_scholes_index_option_price(
    spot: float,
    strike: float,
    years_to_expiry: float,
    rate: float,
    sigma: float,
    option_type: str,
) -> float:
    if spot <= 0 or strike <= 0 or years_to_expiry <= 0 or sigma <= 0:
        intrinsic = max(0.0, spot - strike) if option_type == "call" else max(0.0, strike - spot)
        return intrinsic
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * years_to_expiry) / (sigma * math.sqrt(years_to_expiry))
    d2 = d1 - sigma * math.sqrt(years_to_expiry)
    discounted_strike = strike * math.exp(-rate * years_to_expiry)
    if option_type == "call":
        return spot * normal_cdf(d1) - discounted_strike * normal_cdf(d2)
    return discounted_strike * normal_cdf(-d2) - spot * normal_cdf(-d1)


def estimate_index_option_iv(
    option_price: float | None,
    spot: float | None,
    strike: float | None,
    expiry_date: str,
    option_type: str,
    rate: float = 0.015,
) -> float | None:
    if option_price is None or spot is None or strike is None or option_price <= 0 or spot <= 0 or strike <= 0:
        return None
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").replace(tzinfo=TZ)
    except ValueError:
        return None
    now = datetime.now(TZ)
    years_to_expiry = max((expiry - now).total_seconds() / (365.0 * 24 * 60 * 60), 1 / 365)
    intrinsic = max(0.0, spot - strike) if option_type == "call" else max(0.0, strike - spot)
    if option_price < intrinsic * 0.98:
        return None
    low = 0.005
    high = 3.0
    for _ in range(42):
        mid = (low + high) / 2
        model_price = black_scholes_index_option_price(spot, strike, years_to_expiry, rate, mid, option_type)
        if model_price > option_price:
            high = mid
        else:
            low = mid
    implied = (low + high) / 2
    return implied if 0.005 <= implied <= 3.0 else None


def get_taiwan_option_product(value: str | None = None) -> dict[str, Any]:
    underlying = normalize_taiwan_option_underlying(value)
    return {**TAIWAN_OPTION_PRODUCTS[underlying], "symbol": underlying}


def normalize_taiwan_option_source(value: str | None = None) -> str:
    clean = str(value or "auto").strip().lower()
    return clean if clean in {"auto", "taifex", "yahoo"} else "auto"


def parse_taifex_txo_option_rows(
    html: str,
    spot_price: float | None = None,
    underlying: str | None = "TXO",
) -> list[dict[str, Any]]:
    product = get_taiwan_option_product(underlying)
    commodity = str(product.get("taifexCommodity") or product["symbol"]).upper()
    rows: list[dict[str, Any]] = []
    for row_match in re.finditer(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        cells = [
            re.sub(r"\s+", " ", unescape(re.sub(r"(?is)<[^>]+>", " ", cell))).strip()
            for cell in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row_match.group(1))
        ]
        if len(cells) < 16 or str(cells[0]).strip().upper() != commodity:
            continue
        has_contract_expiry = bool(re.fullmatch(r"\d{8}", cells[2] if len(cells) > 2 else ""))
        has_split_volume = len(cells) >= 20
        index_map = {
            "expiry": 1,
            "expiry_date": 2 if has_contract_expiry else None,
            "strike": 3 if has_contract_expiry else 2,
            "option_type": 4 if has_contract_expiry else 3,
            "open": 5 if has_contract_expiry else 4,
            "high": 6 if has_contract_expiry else 5,
            "low": 7 if has_contract_expiry else 6,
            "last": 8 if has_contract_expiry else 7,
            "settlement": 9 if has_contract_expiry else 8,
            "change": 10 if has_contract_expiry else 9,
            "change_pct": 11 if has_contract_expiry else 10,
            "after_hours_volume": 12 if has_split_volume and has_contract_expiry else 11 if has_split_volume else None,
            "regular_volume": 13 if has_split_volume and has_contract_expiry else 12 if has_split_volume else None,
            "volume": 14 if has_split_volume and has_contract_expiry else 13 if has_split_volume else 12 if has_contract_expiry else 11,
            "open_interest": 15 if has_split_volume and has_contract_expiry else 14 if has_split_volume else 13 if has_contract_expiry else 12,
            "bid": 16 if has_split_volume and has_contract_expiry else 15 if has_split_volume else 14 if has_contract_expiry else 13,
            "ask": 17 if has_split_volume and has_contract_expiry else 16 if has_split_volume else 15 if has_contract_expiry else 14,
            "historical_high": 18 if has_split_volume and has_contract_expiry else 17 if has_split_volume else 16 if has_contract_expiry else 15,
            "historical_low": 19 if has_split_volume and has_contract_expiry else 18 if has_split_volume else 17 if has_contract_expiry else 16,
        }
        option_label = str(cells[index_map["option_type"]] if index_map["option_type"] < len(cells) else "").strip()
        option_type = "call" if option_label.lower() == "call" else "put" if option_label.lower() == "put" else ""
        strike = parse_taifex_number(cells[index_map["strike"]] if index_map["strike"] < len(cells) else "")
        expiry_code = str(cells[index_map["expiry"]] if index_map["expiry"] < len(cells) else "").strip()
        if not option_type or strike is None or not expiry_code:
            continue
        expiry_date = ""
        if index_map["expiry_date"] is not None and index_map["expiry_date"] < len(cells):
            expiry_date = parse_taifex_contract_date(cells[index_map["expiry_date"]])
        bid = parse_taifex_number(cells[index_map["bid"]] if index_map["bid"] < len(cells) else "")
        ask = parse_taifex_number(cells[index_map["ask"]] if index_map["ask"] < len(cells) else "")
        last = parse_taifex_number(cells[index_map["last"]] if index_map["last"] < len(cells) else "")
        settlement = parse_taifex_number(cells[index_map["settlement"]] if index_map["settlement"] < len(cells) else "")
        mid_price = (bid + ask) / 2 if bid is not None and ask is not None and ask > 0 else None
        iv_price = settlement if settlement is not None else last if last is not None else mid_price
        implied_volatility = estimate_index_option_iv(iv_price, spot_price, strike, expiry_date, option_type)
        rows.append({
            "symbol": f"{product['symbol']}-{expiry_code}-{int(strike)}-{'C' if option_type == 'call' else 'P'}",
            "underlying": product["symbol"],
            "expiry": expiry_code,
            "expiryDate": expiry_date,
            "strike": strike,
            "optionType": option_type,
            "open": parse_taifex_number(cells[index_map["open"]] if index_map["open"] < len(cells) else ""),
            "high": parse_taifex_number(cells[index_map["high"]] if index_map["high"] < len(cells) else ""),
            "low": parse_taifex_number(cells[index_map["low"]] if index_map["low"] < len(cells) else ""),
            "last": last,
            "settlement": settlement,
            "change": parse_taifex_number(cells[index_map["change"]] if index_map["change"] < len(cells) else ""),
            "changePct": parse_taifex_number(cells[index_map["change_pct"]] if index_map["change_pct"] < len(cells) else ""),
            "volume": parse_taifex_number(cells[index_map["volume"]] if index_map["volume"] < len(cells) else "") or 0,
            "openInterest": parse_taifex_number(cells[index_map["open_interest"]] if index_map["open_interest"] < len(cells) else "") or 0,
            "afterHoursVolume": parse_taifex_number(cells[index_map["after_hours_volume"]] if index_map["after_hours_volume"] is not None and index_map["after_hours_volume"] < len(cells) else "") or 0,
            "regularVolume": parse_taifex_number(cells[index_map["regular_volume"]] if index_map["regular_volume"] is not None and index_map["regular_volume"] < len(cells) else "") or 0,
            "bid": bid,
            "ask": ask,
            "historicalHigh": parse_taifex_number(cells[index_map["historical_high"]] if index_map["historical_high"] < len(cells) else ""),
            "historicalLow": parse_taifex_number(cells[index_map["historical_low"]] if index_map["historical_low"] < len(cells) else ""),
            "impliedVolatility": round(implied_volatility, 4) if implied_volatility is not None else None,
            "ivSource": "Black-Scholes proxy from TAIFEX price" if implied_volatility is not None else "待接 TAIFEX Delta / 合法行情供應商 IV",
        })
    return rows


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


def parse_yahoo_txo_option_table(
    lines: list[str],
    trade_date: str,
    expiry_code: str,
    spot_price: float | None,
    underlying: str | None = "TXO",
) -> list[dict[str, Any]]:
    product = get_taiwan_option_product(underlying)
    try:
        put_header_index = next(index for index, line in enumerate(lines) if "賣權 Put" in line)
    except StopIteration:
        return []
    time_indices = [index for index in range(put_header_index, min(len(lines), put_header_index + 40)) if lines[index].strip() == "時間"]
    start_index = (time_indices[-1] + 1) if time_indices else put_header_index + 1
    tokens = [line.strip() for line in lines[start_index:] if line.strip()]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[float, str]] = set()
    index = 0
    row_width = 15
    while index + row_width <= len(tokens):
        window = tokens[index : index + row_width]
        strike = parse_yahoo_tw_future_number(window[7])
        if strike is None or not 10000 <= strike <= 70000:
            index += 1
            continue
        key = (float(strike), expiry_code)
        if key in seen:
            index += row_width
            continue
        seen.add(key)
        call_values = window[:7]
        put_values = window[8:15]
        for option_type, values in (("call", call_values), ("put", put_values)):
            bid = parse_yahoo_tw_future_number(values[0])
            ask = parse_yahoo_tw_future_number(values[1])
            last = parse_yahoo_tw_future_number(values[2])
            change = parse_yahoo_tw_future_number(values[3])
            open_interest = parse_yahoo_tw_future_number(values[4]) or 0
            volume = parse_yahoo_tw_future_number(values[5]) or 0
            if not any(value is not None for value in (bid, ask, last, change)) and not open_interest and not volume:
                continue
            mid_price = (bid + ask) / 2 if bid is not None and ask is not None and ask > 0 else None
            iv_price = last if last is not None else mid_price
            implied_volatility = estimate_index_option_iv(iv_price, spot_price, strike, "", option_type)
            rows.append({
                "symbol": f"{product['symbol']}-{expiry_code}-{int(strike)}-{'C' if option_type == 'call' else 'P'}",
                "underlying": product["symbol"],
                "expiry": expiry_code,
                "expiryDate": "",
                "strike": strike,
                "optionType": option_type,
                "open": None,
                "high": None,
                "low": None,
                "last": last,
                "settlement": last,
                "change": change,
                "changePct": None,
                "volume": volume,
                "openInterest": open_interest,
                "bid": bid,
                "ask": ask,
                "quoteTime": values[6] if len(values) > 6 else "",
                "historicalHigh": None,
                "historicalLow": None,
                "impliedVolatility": round(implied_volatility, 4) if implied_volatility is not None else None,
                "ivSource": "Black-Scholes proxy from Yahoo option price" if implied_volatility is not None else "Yahoo 頁面未提供完整 IV，保留待合法行情 IV 補齊",
                "source": "Yahoo 股市台灣選擇權",
            })
        index += row_width
    return rows


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


def enrich_yahoo_cards_with_market_stats(
    cards: list[dict[str, Any]],
    stocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stock_lookup = {
        str(stock.get("code") or "").strip().upper(): stock
        for stock in stocks
        if stock.get("code")
    }
    enriched: list[dict[str, Any]] = []
    for card in cards:
        source_name = str(card.get("sourceName") or "").strip().upper()
        code = source_name.split(".", 1)[0]
        stock = stock_lookup.get(code)
        if not stock:
            enriched.append(card)
            continue

        volume_shares = parse_float(str(stock.get("volume") or ""))
        volume_lots = volume_shares / 1000 if volume_shares is not None else None
        turnover_value = parse_float(str(stock.get("turnover") or ""))
        enriched.append(
            {
                **card,
                "volume": format_whole_number(volume_lots) if volume_lots is not None else card.get("volume", "--"),
                "volumeValue": volume_lots if volume_lots is not None else card.get("volumeValue"),
                "turnover": format_whole_number(turnover_value) if turnover_value is not None else card.get("turnover", "--"),
                "turnoverValue": turnover_value if turnover_value is not None else card.get("turnoverValue"),
            }
        )
    return enriched


def enrich_stocks_with_industry(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        industry_map = fetch_twse_listed_industry_map()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("TWSE industry enrichment unavailable: %s", exc)
        industry_map = {}
    enriched: list[dict[str, Any]] = []
    for stock in stocks:
        code = str(stock.get("code") or "").strip()
        market = str(stock.get("market") or "").strip().upper()
        security_type = str(stock.get("securityType") or "").strip().upper()
        market_label = str(stock.get("marketLabel") or "").strip()
        industry = str(stock.get("industry") or "").strip()
        if market == "TWSE" and code in industry_map:
            industry = industry_map[code]
        elif security_type == "ETF":
            industry = "ETF"
        elif market == "TPEX":
            industry = market_label or "上櫃股票"
        enriched.append({**stock, **({"industry": industry} if industry else {})})
    return enriched


def payload_has_field_candidates(payload: dict[str, Any], candidates: list[str]) -> bool:
    if isinstance(payload.get("fields"), list) and any(candidate in payload.get("fields", []) for candidate in candidates):
        return True
    return any(
        isinstance(table.get("fields"), list)
        and any(candidate in table.get("fields", []) for candidate in candidates)
        and isinstance(table.get("data"), list)
        and bool(table.get("data"))
        for table in payload.get("tables", [])
    )


def market_payload_has_stock_table(payload: dict[str, Any]) -> bool:
    return payload_has_field_candidates(payload, ["證券代號"])


def market_payload_has_index_table(payload: dict[str, Any]) -> bool:
    return payload_has_field_candidates(payload, ["指數", "收盤指數", "發行量加權股價指數"])


def market_payload_has_complete_index_tables(payload: dict[str, Any]) -> bool:
    return market_payload_has_stock_table(payload) and market_payload_has_index_table(payload)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_sign(raw_sign: str) -> str:
    cleaned = strip_html(raw_sign)
    if "+" in cleaned:
        return "+"
    if "-" in cleaned:
        return "-"
    if "X" in cleaned.upper():
        return "X"
    return ""


def find_table_by_field(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    for table in payload.get("tables", []):
        if field_name in table.get("fields", []):
            return table
    raise RuntimeError(f"Unable to locate TWSE table with field: {field_name}")


def find_table_by_title(payload: dict[str, Any], keyword: str) -> dict[str, Any]:
    for table in payload.get("tables", []):
        if keyword in table.get("title", ""):
            return table
    raise RuntimeError(f"Unable to locate TWSE table with title containing: {keyword}")


def sector_aliases(key: str) -> list[str]:
    if key == "發行量加權股價指數":
        return ["發行量加權股價指數"]
    for item in LISTED_SECTOR_INDEX_SPECS:
        if item["key"] == key:
            return [key, *item.get("aliases", [])]
    return [key]


def weighted_index_history_is_usable(series: list[dict[str, Any]], latest_market_date: str) -> bool:
    if len(series) < min(WEIGHTED_INDEX_HISTORY_TRADING_DAYS, 360):
        return False
    expected_latest = datetime.strptime(latest_market_date, "%Y%m%d").strftime("%Y-%m-%d")
    dates: list[datetime] = []
    for item in series:
        try:
            dates.append(datetime.strptime(str(item.get("date", "")), "%Y-%m-%d"))
        except ValueError:
            return False
    if dates[-1].strftime("%Y-%m-%d") != expected_latest:
        return False
    return all(
        0 < (current - previous).days <= 15
        for previous, current in zip(dates, dates[1:])
    )


def weighted_index_history_has_volume(series: list[dict[str, Any]]) -> bool:
    if len(series) < 20:
        return False
    volume_count = sum(
        1
        for item in series
        if parse_float(str(item.get("volumeValue") or item.get("volume") or "")) not in (None, 0)
    )
    return volume_count >= min(60, max(20, len(series) // 3))


def upsert_latest_weighted_index_point(
    series: list[dict[str, Any]],
    market_date: str,
    market_payload: dict[str, Any],
    intraday_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    latest_iso = datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d")
    try:
        close_value = parse_index_close_values(
            market_payload,
            ["發行量加權股價指數"],
        ).get("發行量加權股價指數")
    except Exception:  # noqa: BLE001
        LOGGER.warning("Weighted index close table unavailable for date=%s", market_date)
        close_value = None
    candles = (
        build_intraday_index_candles(intraday_payload, ["發行量加權股價指數"], 5)
        .get("發行量加權股價指數", [])
        if intraday_payload else []
    )
    if close_value is None and candles:
        close_value = parse_float(candles[-1].get("close"))
    if close_value is None:
        return series

    point: dict[str, Any] = {
        "date": latest_iso,
        "close": f"{close_value:.2f}",
    }
    if candles:
        open_value = parse_float(candles[0].get("open"))
        highs = [parse_float(item.get("high")) for item in candles]
        lows = [parse_float(item.get("low")) for item in candles]
        valid_highs = [value for value in highs if value is not None]
        valid_lows = [value for value in lows if value is not None]
        if open_value is not None:
            point["open"] = f"{open_value:.2f}"
        if valid_highs:
            point["high"] = f"{max(valid_highs):.2f}"
        if valid_lows:
            point["low"] = f"{min(valid_lows):.2f}"
    market_stats = parse_market_statistics(market_payload)
    if market_stats:
        for key in ("volume", "turnover", "trades"):
            value = market_stats.get(key)
            if value and value != "--":
                point[key] = value
        if market_stats.get("volumeValue") is not None:
            volume_lots = float(market_stats["volumeValue"]) / 1000
            point["volume"] = format_whole_number(volume_lots)
            point["volumeValue"] = str(volume_lots)

    updated = [item for item in series if item.get("date") != latest_iso]
    updated.append(point)
    updated.sort(key=lambda item: item.get("date", ""))
    return updated[-WEIGHTED_INDEX_HISTORY_TRADING_DAYS:]


def parse_all_stocks(market_payload: dict[str, Any]) -> list[dict[str, Any]]:
    stock_table = find_table_by_field(market_payload, "證券代號")
    stocks: list[dict[str, Any]] = []

    for row in stock_table.get("data", []):
        code = row[0]
        name = row[1]
        open_value = parse_float(row[5])
        high_value = parse_float(row[6])
        low_value = parse_float(row[7])
        close = parse_float(row[8])
        change_value = parse_float(row[10]) or 0.0
        sign = parse_sign(row[9])
        signed_change = change_value if sign == "+" else -change_value if sign == "-" else 0.0
        previous_close = close - signed_change if close is not None else None
        pct = None
        if close is not None and previous_close not in (None, 0):
            pct = (signed_change / previous_close) * 100
        stock = {
            "code": code,
            "name": name,
            "market": "TWSE",
            "marketLabel": "上市",
            "volume": row[2],
            "trades": row[3],
            "turnover": row[4],
            "open": row[5],
            "high": row[6],
            "low": row[7],
            "close": row[8],
            "change": format_signed(signed_change),
            "pct": format_percent(pct),
            "bid": row[11],
            "bidVolume": row[12],
            "ask": row[13],
            "askVolume": row[14],
            "tone": detect_tone(signed_change),
            "technicalAnalysis": build_intraday_technical_analysis(
                open_value=open_value,
                high_value=high_value,
                low_value=low_value,
                close_value=close,
                signed_change=signed_change,
                pct=pct,
            ),
        }
        stocks.append(stock)

    return stocks


def parse_tpex_quotes(
    quotes_payload: list[dict[str, Any]],
    yahoo_etfs: dict[str, str],
) -> list[dict[str, Any]]:
    stocks: list[dict[str, Any]] = []
    yahoo_etf_codes = set(yahoo_etfs)

    for row in quotes_payload:
        code = str(row.get("SecuritiesCompanyCode", "")).strip()
        if not code:
            continue

        name = strip_html(str(row.get("CompanyName", "")))
        security_type, market_label = classify_tpex_security(code, yahoo_etf_codes)
        if security_type is None:
            continue
        if security_type == "ETF" and yahoo_etfs.get(code):
            name = yahoo_etfs[code]

        close = parse_float(str(row.get("Close", "")))
        signed_change = parse_float(str(row.get("Change", ""))) or 0.0
        previous_close = close - signed_change if close is not None else None
        pct = None
        if close is not None and previous_close not in (None, 0):
            pct = (signed_change / previous_close) * 100

        open_value = parse_float(str(row.get("Open", "")))
        high_value = parse_float(str(row.get("High", "")))
        low_value = parse_float(str(row.get("Low", "")))

        stock = {
            "code": code,
            "name": name,
            "market": "TPEx",
            "marketLabel": market_label,
            "securityType": security_type,
            "yahooSymbol": f"{code}.TWO",
            "quoteSource": "TPEx",
            "volume": str(row.get("TradingShares", "--")) or "--",
            "trades": str(row.get("TransactionNumber", "--")) or "--",
            "turnover": str(row.get("TransactionAmount", "--")) or "--",
            "open": str(row.get("Open", "--")) or "--",
            "high": str(row.get("High", "--")) or "--",
            "low": str(row.get("Low", "--")) or "--",
            "close": str(row.get("Close", "--")) or "--",
            "change": format_signed(signed_change),
            "pct": format_percent(pct),
            "bid": str(row.get("LatestBidPrice", "--")) or "--",
            "bidVolume": "--",
            "ask": str(row.get("LatesAskPrice", "--")) or "--",
            "askVolume": "--",
            "tone": detect_tone(signed_change),
            "technicalAnalysis": build_intraday_technical_analysis(
                open_value=open_value,
                high_value=high_value,
                low_value=low_value,
                close_value=close,
                signed_change=signed_change,
                pct=pct,
            ),
        }
        stocks.append(stock)

    return stocks


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


def sync_yahoo_quotes(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tpex_indices = [index for index, stock in enumerate(stocks) if stock.get("market") == "TPEx"]
    if not tpex_indices:
        return stocks

    synced = list(stocks)
    with ThreadPoolExecutor(max_workers=min(6, len(tpex_indices))) as executor:
        futures = {executor.submit(apply_yahoo_quote, stocks[index]): index for index in tpex_indices}
        for future in as_completed(futures):
            index = futures[future]
            try:
                synced[index] = future.result()
            except Exception:  # noqa: BLE001
                synced[index] = stocks[index]
    return synced


def parse_market_overview(market_payload: dict[str, Any]) -> list[dict[str, Any]]:
    index_table = find_table_by_title(market_payload, "價格指數")
    market_stats = parse_market_statistics(market_payload)
    targets = [
        "發行量加權股價指數",
        "電子工業類指數",
        "半導體類指數",
        "金融保險類指數",
    ]
    rows = {row[0]: row for row in index_table.get("data", [])}
    items: list[dict[str, Any]] = []

    for target in targets:
        row = rows[target]
        pct_value = parse_float(row[4])
        change_value = parse_float(row[3])
        sign = parse_sign(row[2])
        signed_change = change_value if sign == "+" else -change_value if sign == "-" else change_value
        stats = market_stats if target == "發行量加權股價指數" else {}
        items.append(
            {
                "name": target,
                "value": row[1],
                "change": format_signed(signed_change),
                "pct": format_percent(pct_value),
                "tone": detect_tone(pct_value),
                "volume": stats.get("volume", "--"),
                "turnover": stats.get("turnover", "--"),
                "trades": stats.get("trades", "--"),
                "volumeValue": stats.get("volumeValue"),
                "turnoverValue": stats.get("turnoverValue"),
                "tradeCount": stats.get("tradeCount"),
            }
        )

    return items


def parse_market_statistics(payload: dict[str, Any]) -> dict[str, Any]:
    stats_table = find_table_by_title(payload, "大盤統計資訊")
    rows = stats_table.get("data", [])
    if not rows:
        return {}

    row_lookup = {str(row[0]).strip(): row for row in rows if row}
    total_row = row_lookup.get("證券合計(1+6+14+15)") or row_lookup.get("總計(1~15)")

    amount_value = volume_value = trade_count = None
    if total_row and len(total_row) >= 4:
        amount_value = parse_float(total_row[1])
        volume_value = parse_float(total_row[2])
        trade_count = parse_float(total_row[3])
    else:
        included_rows = []
        for row in rows:
            if not row or len(row) < 4:
                continue
            label = str(row[0]).strip()
            if label in {"1.一般股票", "6.變更交易股票", "14.創新板股票", "15.創新板-變更交易方法股票"}:
                included_rows.append(row)
        if included_rows:
            amount_value = sum(parse_float(row[1]) or 0 for row in included_rows)
            volume_value = sum(parse_float(row[2]) or 0 for row in included_rows)
            trade_count = sum(parse_float(row[3]) or 0 for row in included_rows)

    return {
        "label": str(total_row[0]).strip() if total_row else "證券合計",
        "turnover": format_whole_number(amount_value),
        "volume": format_whole_number(volume_value),
        "trades": format_whole_number(trade_count),
        "turnoverValue": amount_value,
        "volumeValue": volume_value,
        "tradeCount": trade_count,
    }


def parse_index_activities(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    activities: dict[str, dict[str, Any]] = {}
    for row in payload.get("data", []):
        if not row:
            continue
        name = str(row[0]).strip()
        volume_value = parse_float(row[1])
        turnover_value = parse_float(row[2])
        trade_count = parse_float(row[3])
        activities[name] = {
            "volume": format_whole_number(volume_value),
            "turnover": format_whole_number(turnover_value),
            "trades": format_whole_number(trade_count),
            "activityChange": format_signed(parse_float(row[4])),
            "volumeValue": volume_value,
            "turnoverValue": turnover_value,
            "tradeCount": trade_count,
        }
    return activities


def parse_sectors(
    market_payload: dict[str, Any],
    activities_payload: dict[str, Any] | None = None,
    intraday_payload: dict[str, Any] | None = None,
    history_series_by_index: dict[str, list[dict[str, str]]] | None = None,
) -> list[dict[str, Any]]:
    index_table = find_table_by_title(market_payload, "價格指數")
    rows: dict[str, list[str]] = {}
    for row in index_table.get("data", []):
        if not row:
            continue
        canonical = resolve_sector_key(str(row[0]))
        if canonical:
            rows[canonical] = row

    activity_rows: dict[str, dict[str, Any]] = {}
    if activities_payload:
        for name, item in parse_index_activities(activities_payload).items():
            canonical = resolve_sector_key(name)
            if canonical:
                activity_rows[canonical] = item

    market_stats = parse_market_statistics(market_payload)
    merged_activity_rows = dict(activity_rows)
    if market_stats:
        weighted_activity = {
            **merged_activity_rows.get("發行量加權股價指數", {}),
            **market_stats,
        }
        merged_activity_rows["發行量加權股價指數"] = weighted_activity
    intraday_candles = build_intraday_index_candles(intraday_payload, TARGET_INDEX_NAMES) if intraday_payload else {}
    selected_activity_values = [
        merged_activity_rows[target]
        for target in TARGET_INDEX_NAMES
        if target in merged_activity_rows
    ]
    max_volume_value = max((item["volumeValue"] for item in selected_activity_values if item.get("volumeValue") is not None), default=None)
    max_turnover_value = max((item["turnoverValue"] for item in selected_activity_values if item.get("turnoverValue") is not None), default=None)
    max_trade_count = max((item["tradeCount"] for item in selected_activity_values if item.get("tradeCount") is not None), default=None)
    index_rows: list[dict[str, Any]] = []

    for target in TARGET_INDEX_NAMES:
        row = rows.get(target)
        if row is None:
            continue
        pct_value = parse_float(row[4])
        change_value = parse_float(row[3])
        sign = parse_sign(row[2])
        signed_change = change_value if sign == "+" else -change_value if sign == "-" else change_value
        activity = merged_activity_rows.get(target, {})
        display_name = INDEX_DISPLAY_NAMES.get(target, target)
        candles = intraday_candles.get(target, [])
        index_rows.append(
            {
                "name": display_name,
                "sourceName": target,
                "chartSource": "twse",
                "value": row[1],
                "change": format_signed(signed_change),
                "pct": format_percent(pct_value),
                "pctValue": pct_value if pct_value is not None else -9999.0,
                "tone": detect_tone(pct_value),
                "volume": activity.get("volume", "--"),
                "turnover": activity.get("turnover", "--"),
                "trades": activity.get("trades", "--"),
                "activityChange": activity.get("activityChange", "--"),
                "candles": candles,
                "comparisonSeries": {
                    "day": (history_series_by_index or {}).get(target, []),
                },
                "technicalAnalysis": build_index_technical_analysis(
                    name=display_name,
                    value=parse_float(row[1]),
                    signed_change=signed_change,
                    pct=pct_value,
                    volume_value=activity.get("volumeValue"),
                    turnover_value=activity.get("turnoverValue"),
                    trade_count=activity.get("tradeCount"),
                    max_volume_value=max_volume_value,
                    max_turnover_value=max_turnover_value,
                    max_trade_count=max_trade_count,
                ),
            }
        )
    notes = [
        "大盤核心指標，先確認整體市場方向與風險偏好。",
        "電子供應鏈關鍵觀察指標，可對照 AI 與硬體族群資金。",
        "景氣循環敏感族群，常反映原物料與基建預期。",
        "電子權值與景氣預期的重要風向球。",
        "補漲或避險切換時常有資金輪動跡象。",
        "量體較小，適合觀察短線資金是否集中點火。",
    ]
    for index, item in enumerate(index_rows):
        item["note"] = notes[index] if index < len(notes) else "依證交所產業指數排序。"
        item.pop("pctValue", None)
    return index_rows


def parse_institutions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in payload.get("data", []):
        name = row[0]
        if name == "外資自營商":
            continue
        diff_value = parse_float(row[3])
        items.append(
            {
                "name": name,
                "buy": row[1],
                "sell": row[2],
                "diff": format_signed(diff_value, 0),
                "buyValue": parse_float(row[1]),
                "sellValue": parse_float(row[2]),
                "diffValue": diff_value,
                "tone": detect_tone(diff_value),
            }
        )
    return items


def find_stock_by_query(query: str, stocks: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    keyword = query.strip().lower()
    if not keyword:
        return []

    exact_code: list[dict[str, Any]] = []
    prefix_code: list[dict[str, Any]] = []
    partial_code: list[dict[str, Any]] = []
    prefix_name: list[dict[str, Any]] = []
    name_matches: list[dict[str, Any]] = []

    for stock in stocks:
        code = str(stock["code"]).lower()
        name = str(stock["name"]).lower()
        if code == keyword:
            exact_code.append(stock)
        elif code.startswith(keyword):
            prefix_code.append(stock)
        elif keyword in code:
            partial_code.append(stock)
        elif name.startswith(keyword):
            prefix_name.append(stock)
        elif keyword in name:
            name_matches.append(stock)

    combined = exact_code + prefix_code + partial_code + prefix_name + name_matches
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in combined:
        item_key = (str(item.get("market", "")), str(item["code"]))
        if item_key in seen:
            continue
        seen.add(item_key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def build_site_data(
    existing_site_data: dict[str, Any] | None = None,
    existing_market_date: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    market_payload, market_date = find_latest_dataset(
        build_market_url,
        validator=market_payload_has_complete_index_tables,
    )
    institution_payload, institution_date = find_latest_dataset(build_institutions_url)
    tpex_mainboard_quotes: list[dict[str, Any]] = []
    tpex_mainboard_quote_date: str | None = None
    yahoo_tpex_etfs: dict[str, str] = {}
    tpex_mainboard_highlight: list[dict[str, Any]] = []
    tpex_esb_highlight: list[dict[str, Any]] = []
    tpex_esb_latest_statistics: list[dict[str, Any]] = []
    yahoo_tpex_otc_date: str | None = None
    yahoo_tpex_emerging_date: str | None = None
    yahoo_sector_groups: dict[str, list[dict[str, Any]]] = {}
    yahoo_sector_dates: dict[str, str | None] = {}
    yahoo_sector_catalog: dict[str, list[dict[str, str]]] = {}
    try:
        tpex_mainboard_quotes, tpex_mainboard_quote_date = fetch_tpex_mainboard_quotes()
    except Exception:  # noqa: BLE001
        tpex_mainboard_quotes = []
        tpex_mainboard_quote_date = None
    try:
        yahoo_tpex_etfs = fetch_yahoo_tpex_etfs()
    except Exception:  # noqa: BLE001
        yahoo_tpex_etfs = {}
    try:
        yahoo_sector_catalog = fetch_yahoo_sector_catalog()
    except Exception:  # noqa: BLE001
        yahoo_sector_catalog = {}
    yahoo_sector_groups, yahoo_sector_dates = build_yahoo_sector_groups()
    tpex_mainboard_highlight = yahoo_sector_groups.get("otc", [])[:6]
    tpex_esb_highlight = yahoo_sector_groups.get("emerging", [])[:6]
    yahoo_tpex_otc_date = yahoo_sector_dates.get("otc")
    yahoo_tpex_emerging_date = yahoo_sector_dates.get("emerging")
    if not tpex_mainboard_highlight:
        try:
            tpex_mainboard_highlight = build_summary_cards_from_payload(
                fetch_json(build_tpex_openapi_url("tpex_mainborad_highlight")),
                "上櫃",
                limit=6,
            )
        except Exception:  # noqa: BLE001
            tpex_mainboard_highlight = []
    if not tpex_esb_highlight:
        try:
            tpex_esb_highlight = build_summary_cards_from_payload(
                fetch_json(build_tpex_openapi_url("tpex_esb_highlight")),
                "興櫃",
                limit=6,
            )
        except Exception:  # noqa: BLE001
            tpex_esb_highlight = []
    if not tpex_esb_latest_statistics:
        try:
            tpex_esb_latest_statistics = build_summary_cards_from_payload(
                fetch_json(build_tpex_openapi_url("tpex_esb_latest_statistics")),
                "興櫃統計",
                limit=6,
            )
        except Exception:  # noqa: BLE001
            tpex_esb_latest_statistics = []
    activity_payload = None
    activity_date = market_date
    try:
        same_day_activity = fetch_json(build_index_activity_url(market_date))
        if dataset_has_rows(same_day_activity):
            activity_payload = same_day_activity
        else:
            activity_date = None
    except Exception:  # noqa: BLE001
        activity_date = None
    try:
        same_day_intraday = fetch_json(build_index_intraday_url(market_date))
        if dataset_has_rows(same_day_intraday):
            intraday_payload, intraday_date = same_day_intraday, market_date
        else:
            intraday_payload, intraday_date = None, market_date
    except Exception:  # noqa: BLE001
        intraday_payload, intraday_date = None, market_date
    existing_history_has_trades = any(
        point.get("trades") not in (None, "", "--")
        for item in (existing_site_data or {}).get("sectors", [])
        if item.get("sourceName") != "發行量加權股價指數"
        for point in ((item.get("comparisonSeries") or {}).get("day") or [])
    )
    if existing_site_data and existing_market_date == market_date and existing_history_has_trades:
        history_series_by_index = {
            item.get("sourceName"): (item.get("comparisonSeries", {}) or {}).get("day", [])
            for item in existing_site_data.get("sectors", [])
            if item.get("sourceName")
        }
        weighted_series = history_series_by_index.get("發行量加權股價指數", [])
        if not weighted_index_history_is_usable(weighted_series, market_date) or not weighted_index_history_has_volume(weighted_series):
            history_series_by_index["發行量加權股價指數"] = build_weighted_index_history_series(
                market_date,
                WEIGHTED_INDEX_HISTORY_TRADING_DAYS,
            )
    else:
        history_series_by_index = build_sector_history_series(market_date, TARGET_INDEX_NAMES)
    if not weighted_index_history_has_volume(history_series_by_index.get("發行量加權股價指數", [])):
        history_series_by_index["發行量加權股價指數"] = build_weighted_index_history_series(
            market_date,
            WEIGHTED_INDEX_HISTORY_TRADING_DAYS,
        )
    history_series_by_index["發行量加權股價指數"] = upsert_latest_weighted_index_point(
        history_series_by_index.get("發行量加權股價指數", []),
        market_date,
        market_payload,
        intraday_payload,
    )
    tpex_stocks = parse_tpex_quotes(tpex_mainboard_quotes, yahoo_tpex_etfs)
    twse_stocks = parse_all_stocks(market_payload)
    all_stocks = [*twse_stocks, *tpex_stocks]
    yahoo_sector_groups = {
        key: enrich_yahoo_cards_with_market_stats(cards, all_stocks)
        for key, cards in yahoo_sector_groups.items()
    }
    market_overview = parse_market_overview(market_payload)
    sectors = parse_sectors(market_payload, activity_payload, intraday_payload, history_series_by_index)
    institutions = parse_institutions(institution_payload)
    institution_summary = build_institution_summary(institutions)
    try:
        institution_trend = build_institution_trend(institution_payload, institution_date)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Institution trend build failed")
        institution_trend = {}
    market_stats = parse_market_statistics(market_payload)
    try:
        market_volatility = fetch_market_volatility_indicator(
            history_series_by_index.get("發行量加權股價指數", []),
        )
    except Exception:  # noqa: BLE001
        market_volatility = None
    try:
        market_international_indexes = fetch_international_market_indexes()
    except Exception:  # noqa: BLE001
        market_international_indexes = []
    try:
        market_macro_factors = fetch_market_macro_factors(market_date)
    except Exception:  # noqa: BLE001
        market_macro_factors = {}
    sector_fund_flow = build_sector_fund_flow(twse_stocks, market_date)
    cached_at = taipei_now().strftime("%Y-%m-%d %H:%M:%S")
    benchmark_day_series = history_series_by_index.get("發行量加權股價指數", [])
    tpex_mainboard_highlight = build_yahoo_summary_series(tpex_mainboard_highlight, benchmark_day_series)
    tpex_esb_highlight = build_yahoo_summary_series(tpex_esb_highlight, benchmark_day_series)
    for key, cards in yahoo_sector_groups.items():
        yahoo_sector_groups[key] = build_yahoo_summary_series(cards, benchmark_day_series)

    site_data = {
        "snapshotDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "institutionDate": datetime.strptime(institution_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "activityDate": datetime.strptime(activity_date, "%Y%m%d").strftime("%Y-%m-%d") if activity_date else None,
        "intradayDate": datetime.strptime(intraday_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "cachedAt": cached_at,
        "stockCount": len(all_stocks),
        "tpexStockCount": len(tpex_stocks),
        "tpexEtfCount": sum(1 for item in tpex_stocks if item.get("securityType") == "ETF"),
        "tpexStockDate": datetime.strptime(tpex_mainboard_quote_date, "%Y%m%d").strftime("%Y-%m-%d") if tpex_mainboard_quote_date else None,
        "yahooOtcDate": yahoo_tpex_otc_date,
        "yahooEmergingDate": yahoo_tpex_emerging_date,
        "yahooSectorDates": yahoo_sector_dates,
        "marketStats": market_stats,
        "marketVolatility": market_volatility,
        "marketInternationalIndexes": market_international_indexes,
        "marketMacroFactors": market_macro_factors,
        "sourceLinks": {
            "market": build_market_url(market_date),
            "institutions": build_institutions_url(institution_date),
            "indexActivity": build_index_activity_url(activity_date) if activity_date else None,
            "indexIntraday": build_index_intraday_url(intraday_date),
            "tpexEtfs": YAHOO_TPEX_ETF_URL,
            "yahooOtcClassQuote": YAHOO_TPEX_OTC_CLASS_URL,
            "yahooEmergingClassQuote": YAHOO_TPEX_EMERGING_CLASS_URL,
            "yahooListedClassQuote": YAHOO_LISTED_CLASS_URL,
            "yahooClassHome": YAHOO_CLASS_HOME_URL,
            "yahooElectronicClassQuote": YAHOO_ELECTRONIC_CLASS_URL,
            "yahooConceptClassQuote": YAHOO_CONCEPT_CLASS_URL,
            "yahooGroupClassQuote": YAHOO_GROUP_CLASS_URL,
            "yahooInternationalIndexes": "https://finance.yahoo.com/",
            "twseMarginTrading": TWSE_MARGIN_URL,
            "taifexFuturesOpenInterest": TAIFEX_FUTURES_DAILY_URL,
        },
        "marketOverview": market_overview,
        "sectors": sectors,
        "sectorFundFlow": sector_fund_flow,
        "institutions": institutions,
        "institutionSummary": institution_summary,
        "institutionTrend": institution_trend,
        "tpexHighlights": {
            "mainboard": tpex_mainboard_highlight,
            "emerging": tpex_esb_highlight,
            "emergingStats": [],
        },
        "yahooSectorGroups": yahoo_sector_groups,
        "yahooSectorCatalog": yahoo_sector_catalog,
    }
    site_data = merge_site_data_with_fallback(site_data, existing_site_data)
    site_data["news"] = build_news(site_data)

    return sanitize_site_data(site_data), all_stocks, market_date


def refresh_tpex_cache() -> None:
    quotes, quote_date = fetch_tpex_mainboard_quotes()
    try:
        yahoo_etfs = fetch_yahoo_tpex_etfs()
    except Exception:  # noqa: BLE001
        yahoo_etfs = {}
    tpex_stocks = parse_tpex_quotes(quotes, yahoo_etfs)
    if not tpex_stocks:
        return

    with cache_lock:
        existing_site_data = copy.deepcopy(cache_data["site_data"])
        existing_market_date = cache_data["market_date"]
    if existing_site_data and existing_market_date:
        history_series_by_index = {
            item.get("sourceName"): (item.get("comparisonSeries", {}) or {}).get("day", [])
            for item in existing_site_data.get("sectors", [])
            if item.get("sourceName")
        }
    else:
        history_series_by_index = build_sector_history_series(existing_market_date or quote_date, TARGET_INDEX_NAMES)
    benchmark_day_series = history_series_by_index.get("發行量加權股價指數", [])

    try:
        tpex_mainboard_highlight, yahoo_tpex_otc_date = build_yahoo_class_quote_cards(YAHOO_TPEX_OTC_CLASS_URL, "上櫃", limit=6)
    except Exception:  # noqa: BLE001
        tpex_mainboard_highlight = []
        yahoo_tpex_otc_date = None
    try:
        tpex_esb_highlight, yahoo_tpex_emerging_date = build_yahoo_class_quote_cards(YAHOO_TPEX_EMERGING_CLASS_URL, "興櫃", limit=6)
    except Exception:  # noqa: BLE001
        tpex_esb_highlight = []
        yahoo_tpex_emerging_date = None
    if not tpex_mainboard_highlight:
        tpex_mainboard_highlight = build_summary_cards_from_payload(
            fetch_json(build_tpex_openapi_url("tpex_mainborad_highlight")),
            "上櫃",
            limit=6,
        )
    if not tpex_esb_highlight:
        tpex_esb_highlight = build_summary_cards_from_payload(
            fetch_json(build_tpex_openapi_url("tpex_esb_highlight")),
            "興櫃",
            limit=6,
        )
    tpex_mainboard_highlight = build_yahoo_summary_series(tpex_mainboard_highlight, benchmark_day_series)
    tpex_esb_highlight = build_yahoo_summary_series(tpex_esb_highlight, benchmark_day_series)

    with cache_lock:
        listed_stocks = [
            stock for stock in cache_data["all_stocks"]
            if stock.get("market") != "TPEx"
        ]
        cache_data["all_stocks"] = [*listed_stocks, *tpex_stocks]
        if cache_data["site_data"]:
            site_data = dict(cache_data["site_data"])
            site_data["stockCount"] = len(cache_data["all_stocks"])
            site_data["tpexStockCount"] = len(tpex_stocks)
            site_data["tpexEtfCount"] = sum(
                1 for stock in tpex_stocks
                if stock.get("securityType") == "ETF"
            )
            site_data["tpexStockDate"] = (
                datetime.strptime(quote_date, "%Y%m%d").strftime("%Y-%m-%d")
                if quote_date else None
            )
            site_data["yahooOtcDate"] = yahoo_tpex_otc_date
            site_data["yahooEmergingDate"] = yahoo_tpex_emerging_date
            site_data["tpexHighlights"] = {
                "mainboard": tpex_mainboard_highlight,
                "emerging": tpex_esb_highlight,
                "emergingStats": [],
            }
            cache_data["site_data"] = site_data
    save_disk_cache()


def format_market_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return date_str


def site_data_has_complete_sector_payload(site_data: dict[str, Any] | None) -> bool:
    if not site_data:
        return False
    sectors = site_data.get("sectors") or []
    international = site_data.get("marketInternationalIndexes") or []
    volatility = site_data.get("marketVolatility") or {}
    weighted = next(
        (
            item for item in sectors
            if item.get("sourceName") == "發行量加權股價指數" or item.get("name") == "台灣加權指數"
        ),
        {},
    )
    weighted_history_count = len(((weighted.get("comparisonSeries") or {}).get("day") or []))
    sector_history_counts = [
        len(((item.get("comparisonSeries") or {}).get("day") or []))
        for item in sectors
        if item.get("sourceName") != "發行量加權股價指數" and item.get("name") != "台灣加權指數"
    ]
    complete_sector_histories = sum(1 for count in sector_history_counts if count >= 20)
    return (
        len(sectors) >= 20
        and weighted_history_count >= min(WEIGHTED_INDEX_HISTORY_TRADING_DAYS, 360)
        and complete_sector_histories >= 10
        and len(international) >= 18
        and len(volatility.get("series") or []) >= 20
    )


def site_data_recent_enough(site_data: dict[str, Any] | None, max_age_seconds: int = 1800) -> bool:
    cached_at = str((site_data or {}).get("cachedAt") or "")
    if not cached_at:
        return False
    try:
        cached_dt = datetime.strptime(cached_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=TZ)
    except ValueError:
        return False
    return (taipei_now() - cached_dt).total_seconds() <= max_age_seconds


def pick_exact_live_stock(
    code: str,
    requested_market: str = "",
) -> tuple[dict[str, Any] | None, str, str | None, list[str]]:
    normalized_code = str(code or "").strip().upper()
    matches, market_date, tpex_quote_date, sources = fetch_live_stock_search_results(
        normalized_code,
        requested_market=requested_market,
        limit=20,
    )
    normalized_market = normalize_market_request(requested_market)
    stock = next(
        (
            item for item in matches
            if str(item.get("code") or "").strip().upper() == normalized_code
            and (not normalized_market or normalize_market_request(str(item.get("market"))) == normalized_market)
        ),
        None,
    )
    if stock is None and matches:
        stock = next(
            (
                item for item in matches
                if str(item.get("code") or "").strip().upper() == normalized_code
            ),
            None,
        )
    return stock, market_date, tpex_quote_date, sources




def build_live_sector_site_data() -> dict[str, Any]:
    """Build a live sectors payload without rebuilding every dashboard dataset."""
    with DeadlineThreadPoolExecutor(max_workers=7) as executor:
        market_future = executor.submit(
            find_latest_dataset,
            build_market_url,
            7,
            market_payload_has_complete_index_tables,
        )
        institution_future = executor.submit(find_latest_dataset, build_institutions_url, 7)
        yahoo_groups_future = executor.submit(build_yahoo_sector_groups, 12, 8)
        yahoo_catalog_future = executor.submit(fetch_yahoo_sector_catalog, 8)
        volatility_future = executor.submit(fetch_market_volatility_indicator, [])

        market_payload, market_date = market_future.result()
        activity_future = executor.submit(fetch_live_index_activity, market_date)
        intraday_future = executor.submit(fetch_live_index_intraday, market_date)
        history_future = executor.submit(
            build_sector_history_series,
            market_date,
            TARGET_INDEX_NAMES,
            20,
            120,
            45,
            False,
        )

        try:
            institution_payload, institution_date = institution_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live sectors institution fetch failed")
            institution_payload, institution_date = {"data": []}, market_date

        try:
            activity_payload = activity_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live sectors index activity fetch failed")
            activity_payload = None

        try:
            intraday_payload = intraday_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live sectors intraday fetch failed")
            intraday_payload = None

        try:
            history_series_by_index = history_future.result(timeout=18)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live sectors history fetch failed")
            history_series_by_index = {}

        try:
            yahoo_sector_groups, yahoo_sector_dates = yahoo_groups_future.result(timeout=20)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Live sectors Yahoo group fetch unavailable: %s", exc)
            yahoo_sector_groups, yahoo_sector_dates = {}, {}

        try:
            yahoo_sector_catalog = yahoo_catalog_future.result(timeout=10)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live sectors Yahoo catalog fetch failed")
            yahoo_sector_catalog = {}

        try:
            market_volatility = volatility_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live sectors VIX fetch failed")
            market_volatility = None

    if not weighted_index_history_has_volume(history_series_by_index.get("發行量加權股價指數", [])):
        try:
            history_series_by_index["發行量加權股價指數"] = build_weighted_index_history_series(market_date, 120)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live sectors weighted index history fetch failed")

    history_series_by_index["發行量加權股價指數"] = upsert_latest_weighted_index_point(
        history_series_by_index.get("發行量加權股價指數", []),
        market_date,
        market_payload,
        intraday_payload,
    )

    benchmark_day_series = history_series_by_index.get("發行量加權股價指數", [])
    twse_stocks = parse_all_stocks(market_payload)
    sector_fund_flow = build_sector_fund_flow(twse_stocks, market_date)
    yahoo_sector_groups["listed"] = []
    yahoo_sector_groups = {
        key: build_yahoo_summary_series(cards, benchmark_day_series)
        for key, cards in (yahoo_sector_groups or {}).items()
    }
    tpex_mainboard_highlight = yahoo_sector_groups.get("otc", [])[:6]
    tpex_esb_highlight = yahoo_sector_groups.get("emerging", [])[:6]

    sectors = parse_sectors(market_payload, activity_payload, intraday_payload, history_series_by_index)
    institutions = parse_institutions(institution_payload)
    institution_summary = build_institution_summary(institutions)
    try:
        institution_trend = build_institution_trend(institution_payload, institution_date)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Live sectors institution trend build failed")
        institution_trend = {}
    market_overview = parse_market_overview(market_payload)
    market_stats = parse_market_statistics(market_payload)
    cached_at = taipei_now().strftime("%Y-%m-%d %H:%M:%S")
    activity_date = market_date if activity_payload else None

    site_data = {
        "snapshotDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "institutionDate": datetime.strptime(institution_date, "%Y%m%d").strftime("%Y-%m-%d") if institution_date else None,
        "activityDate": datetime.strptime(activity_date, "%Y%m%d").strftime("%Y-%m-%d") if activity_date else None,
        "intradayDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "cachedAt": cached_at,
        "stockCount": len(twse_stocks),
        "tpexStockCount": None,
        "tpexEtfCount": None,
        "tpexStockDate": None,
        "yahooOtcDate": yahoo_sector_dates.get("otc"),
        "yahooEmergingDate": yahoo_sector_dates.get("emerging"),
        "yahooSectorDates": yahoo_sector_dates,
        "marketStats": market_stats,
        "marketVolatility": market_volatility,
        "marketInternationalIndexes": copy.deepcopy((cache_data.get("site_data") or {}).get("marketInternationalIndexes") or []),
        "marketMacroFactors": {},
        "sourceLinks": {
            "market": build_market_url(market_date),
            "institutions": build_institutions_url(institution_date) if institution_date else None,
            "indexActivity": build_index_activity_url(activity_date) if activity_date else None,
            "indexIntraday": build_index_intraday_url(market_date),
            "yahooListedClassQuote": YAHOO_LISTED_CLASS_URL,
            "yahooOtcClassQuote": YAHOO_TPEX_OTC_CLASS_URL,
            "yahooEmergingClassQuote": YAHOO_TPEX_EMERGING_CLASS_URL,
            "yahooClassHome": YAHOO_CLASS_HOME_URL,
            "yahooElectronicClassQuote": YAHOO_ELECTRONIC_CLASS_URL,
            "yahooConceptClassQuote": YAHOO_CONCEPT_CLASS_URL,
            "yahooGroupClassQuote": YAHOO_GROUP_CLASS_URL,
        },
        "marketOverview": market_overview,
        "sectors": sectors,
        "sectorFundFlow": sector_fund_flow,
        "institutions": institutions,
        "institutionSummary": institution_summary,
        "institutionTrend": institution_trend,
        "tpexHighlights": {
            "mainboard": tpex_mainboard_highlight,
            "emerging": tpex_esb_highlight,
            "emergingStats": [],
        },
        "yahooSectorGroups": yahoo_sector_groups,
        "yahooSectorCatalog": yahoo_sector_catalog,
        "liveOptimized": True,
    }
    if institutions and sectors:
        try:
            site_data["news"] = build_news(site_data)
        except Exception:  # noqa: BLE001
            site_data["news"] = []
    else:
        site_data["news"] = []

    return sanitize_site_data(site_data)


def build_live_market_overview_data() -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=6) as executor:
        market_future = executor.submit(
            find_latest_dataset,
            build_market_url,
            7,
            market_payload_has_complete_index_tables,
        )
        institution_future = executor.submit(find_latest_dataset, build_institutions_url, 7)
        vix_future = executor.submit(fetch_market_volatility_indicator, [])
        tpex_future = executor.submit(fetch_tpex_mainboard_quotes)
        yahoo_groups_future = executor.submit(build_yahoo_sector_groups, 30, 8)

        market_payload, market_date = market_future.result()
        institution_payload, institution_date = institution_future.result()
        try:
            market_volatility = vix_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live overview VIX fetch failed")
            market_volatility = None
        try:
            tpex_quotes, tpex_quote_date = tpex_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live overview TPEx quotes fetch failed")
            tpex_quotes, tpex_quote_date = [], None
        try:
            yahoo_sector_groups, yahoo_sector_dates = yahoo_groups_future.result(timeout=20)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Live overview Yahoo sector group fetch unavailable: %s", exc)
            yahoo_sector_groups, yahoo_sector_dates = {}, {}

    activity_payload = fetch_live_index_activity(market_date)
    intraday_payload = fetch_live_index_intraday(market_date)
    sectors = parse_sectors(market_payload, activity_payload, intraday_payload, {})
    market_overview = parse_market_overview(market_payload)
    institutions = parse_institutions(institution_payload)
    institution_summary = build_institution_summary(institutions)
    try:
        institution_trend = build_institution_trend(institution_payload, institution_date)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Live overview institution trend build failed")
        institution_trend = {}
    twse_stocks = parse_all_stocks(market_payload)
    sector_fund_flow = build_sector_fund_flow(twse_stocks, market_date)
    tpex_stocks = parse_tpex_quotes(tpex_quotes, {}) if tpex_quotes else []
    all_stocks = [*twse_stocks, *tpex_stocks]
    site_data = {
        "snapshotDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "institutionDate": datetime.strptime(institution_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "activityDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d") if activity_payload else None,
        "intradayDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "cachedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
        "stockCount": len(all_stocks),
        "tpexStockCount": len(tpex_stocks),
        "tpexStockDate": datetime.strptime(tpex_quote_date, "%Y%m%d").strftime("%Y-%m-%d") if tpex_quote_date else None,
        "yahooOtcDate": yahoo_sector_dates.get("otc"),
        "yahooEmergingDate": yahoo_sector_dates.get("emerging"),
        "yahooSectorDates": yahoo_sector_dates,
        "marketStats": parse_market_statistics(market_payload),
        "marketVolatility": market_volatility,
        "marketInternationalIndexes": copy.deepcopy((cache_data.get("site_data") or {}).get("marketInternationalIndexes") or []),
        "marketMacroFactors": {},
        "sourceLinks": {
            "market": build_market_url(market_date),
            "institutions": build_institutions_url(institution_date),
            "indexActivity": build_index_activity_url(market_date) if activity_payload else None,
            "indexIntraday": build_index_intraday_url(market_date),
            "yahooListedClassQuote": YAHOO_LISTED_CLASS_URL,
            "yahooOtcClassQuote": YAHOO_TPEX_OTC_CLASS_URL,
            "yahooEmergingClassQuote": YAHOO_TPEX_EMERGING_CLASS_URL,
            "yahooClassHome": YAHOO_CLASS_HOME_URL,
            "yahooInternationalIndexes": "https://finance.yahoo.com/",
            "twseMarginTrading": TWSE_MARGIN_URL,
            "taifexFuturesOpenInterest": TAIFEX_FUTURES_DAILY_URL,
        },
        "marketOverview": market_overview,
        "sectors": sectors,
        "sectorFundFlow": sector_fund_flow,
        "institutions": institutions,
        "institutionSummary": institution_summary,
        "institutionTrend": institution_trend,
        "stocks": build_stocks_view(all_stocks, "search"),
        "tpexHighlights": {
            "mainboard": (yahoo_sector_groups.get("otc") or [])[:6],
            "emerging": (yahoo_sector_groups.get("emerging") or [])[:6],
            "emergingStats": [],
        },
        "yahooSectorGroups": yahoo_sector_groups,
        "yahooSectorCatalog": {},
    }
    site_data["news"] = build_news(site_data)
    return sanitize_site_data(site_data)



@app.route("/api/health")
def api_health():
    with cache_lock:
        return jsonify(
            {
                "status": "ok" if cache_data["site_data"] else "warming",
                "cachedAt": cache_data["cached_at"],
                "lastError": cache_data["last_error"],
            }
        )


@app.route("/api/twse/site-data")
def api_site_data():
    refresh = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes", "on"}
    if refresh:
        try:
            return jsonify(build_live_sector_site_data())
        except Exception as exc:  # noqa: BLE001
            return api_exception_response("LIVE_SITE_DATA_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
    ensure_cache()
    with cache_lock:
        return jsonify(cache_data["site_data"])


@app.route("/api/twse/live-sectors")
def api_live_sectors():
    try:
        return jsonify(build_live_sector_site_data())
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("LIVE_SECTORS_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)


@app.route("/api/twse/live-overview")
def api_live_overview():
    try:
        return jsonify(build_live_market_overview_data())
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("LIVE_OVERVIEW_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)


@app.route("/api/twse/live-stocks")
def api_live_stocks():
    try:
        stocks, _market_payload, market_date, tpex_quote_date = fetch_live_stock_universe()
        stocks = enrich_stocks_with_industry(stocks)
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("LIVE_STOCKS_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)

    return jsonify(
        {
            "snapshotDate": format_market_date(market_date),
            "tpexStockDate": format_market_date(tpex_quote_date),
            "refreshedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(stocks),
            "stocks": build_stocks_view(stocks, "search"),
            "source": "TWSE / TPEx 即時同步",
        }
    )


@app.route("/api/twse/live-search")
def api_live_stock_search():
    query = request.args.get("q", "").strip()
    requested_market = request.args.get("market", "").strip()
    if not query:
        return jsonify(
            {
                "query": query,
                "snapshotDate": None,
                "tpexStockDate": None,
                "refreshedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
                "count": 0,
                "results": [],
                "source": "TWSE / TPEx live search",
                "sources": [],
            }
        )
    try:
        matches, market_date, tpex_quote_date, sources = fetch_live_stock_search_results(
            query,
            requested_market=requested_market,
            limit=20,
        )
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("LIVE_SEARCH_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)

    return jsonify(
        {
            "query": query,
            "snapshotDate": format_market_date(market_date),
            "tpexStockDate": format_market_date(tpex_quote_date),
            "refreshedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(matches),
            "results": build_stocks_view(matches, "search"),
            "source": " / ".join(sources) + " live search" if sources else "live search",
            "sources": sources,
        }
    )


@app.route("/api/yahoo/sector")
def api_yahoo_sector():
    group_key = request.args.get("group", "").strip()
    try:
        category_index = int(request.args.get("index", "0"))
    except ValueError:
        return jsonify({"error": "分類索引格式錯誤"}), 400

    if group_key not in {"listed", "otc", "emerging", "electronic", "concept", "group"}:
        return jsonify({"error": "查無 Yahoo 類股分類"}), 404
    try:
        catalog = fetch_yahoo_sector_catalog()
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("YAHOO_SECTOR_CATALOG_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)

    categories = catalog.get(group_key) or []
    if category_index < 0 or category_index >= len(categories):
        return jsonify({"error": "查無 Yahoo 子分類"}), 404

    category = categories[category_index]
    cards, snapshot_date = build_yahoo_class_quote_cards(
        str(category.get("url") or ""),
        str(category.get("name") or "類股"),
        limit=500,
    )
    return jsonify(
        {
            "group": group_key,
            "index": category_index,
            "name": category.get("name"),
            "source": "Yahoo奇摩股市",
            "snapshotDate": snapshot_date,
            "count": len(cards),
            "items": cards,
        }
    )


@app.route("/api/yahoo/sector-chart")
def api_yahoo_sector_chart():
    raw_symbol = request.args.get("symbol", "").strip().upper()
    exchange = request.args.get("exchange", "").strip().upper()
    equity_match = re.fullmatch(r"(\d{4,6}[A-Z]?)(?:\.(TW|TWO))?", raw_symbol)
    yahoo_symbol_match = re.fullmatch(r"\^?[A-Z0-9][A-Z0-9.^_-]{1,19}", raw_symbol)
    if not equity_match and not yahoo_symbol_match:
        return jsonify({"error": "股票代號格式錯誤"}), 400

    symbol = equity_match.group(1) if equity_match else raw_symbol
    symbol_suffix = equity_match.group(2) if equity_match else ""
    market = "TWSE" if exchange in {"TAI", "TW", "TWSE"} or symbol_suffix == "TW" else "TPEx"
    yahoo_symbol = raw_symbol if not equity_match else ""
    cache_key = f"{raw_symbol}:{exchange}:{market}"
    now = time.monotonic()
    with cache_lock:
        cached_chart = cache_data["sector_charts"].get(cache_key)
        if cached_chart and now - cached_chart["stored_at"] < SECTOR_CHART_CACHE_SECONDS:
            return jsonify(cached_chart["payload"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        history_future = (
            executor.submit(fetch_yahoo_symbol_chart, yahoo_symbol, "2y", "1d")
            if yahoo_symbol
            else executor.submit(fetch_yahoo_chart, symbol, "2y", "1d", market)
        )
        benchmark_future = executor.submit(fetch_yahoo_symbol_chart, "^TWII", "2y", "1d")
        try:
            history_chart = history_future.result()
        except Exception:  # noqa: BLE001
            history_chart = None
        try:
            benchmark_chart = benchmark_future.result()
        except Exception:  # noqa: BLE001
            benchmark_chart = None

    day_series = build_yahoo_chart_series(history_chart)
    benchmark_day_series = build_yahoo_chart_series(benchmark_chart)
    if len(day_series) < 20:
        return jsonify(
            {
                "symbol": symbol,
                "exchange": exchange,
                "market": market,
                "value": "--",
                "change": "--",
                "pct": "--",
                "tone": "neutral",
                "volume": "--",
                "turnover": "--",
                "trades": "--",
                "candles": [],
                "comparisonSeries": {"day": [], "benchmark": benchmark_day_series},
                "summaryOnly": True,
                "chartUnavailable": True,
                "chartUnavailableReason": "Yahoo 歷史走勢資料不足",
                "sourceLink": f"https://tw.stock.yahoo.com/quote/{quote(raw_symbol, safe='')}",
            }
        )
    latest_close = parse_float(day_series[-1].get("close")) if day_series else None
    previous_close = parse_float(day_series[-2].get("close")) if len(day_series) > 1 else None
    latest_change = (
        latest_close - previous_close
        if latest_close is not None and previous_close is not None
        else None
    )
    latest_pct = (
        latest_change / previous_close * 100
        if latest_change is not None and previous_close not in (None, 0)
        else None
    )
    latest_volume = "--"
    latest_turnover = "--"
    latest_trades = "--"
    if equity_match:
        with cache_lock:
            current_stock = next(
                (
                    stock
                    for stock in cache_data.get("all_stocks", [])
                    if str(stock.get("code", "")).upper() == symbol
                ),
                None,
            )
        current_stock = current_stock or {}
        volume_shares = parse_float(str(current_stock.get("volume") or ""))
        latest_volume = (
            format_whole_number(volume_shares / 1000)
            if volume_shares is not None
            else "--"
        )
        latest_turnover = str(current_stock.get("turnover") or "--")
        latest_trades = str(current_stock.get("trades") or "--")
        if day_series:
            if latest_volume != "--":
                day_series[-1]["volume"] = latest_volume
            if latest_turnover != "--":
                day_series[-1]["turnover"] = latest_turnover
            if latest_trades != "--":
                day_series[-1]["trades"] = latest_trades
    payload = {
        "symbol": symbol,
        "exchange": exchange,
        "market": market,
        "value": f"{latest_close:.2f}" if latest_close is not None else "--",
        "change": format_signed(latest_change),
        "pct": format_percent(latest_pct),
        "tone": detect_tone(latest_change),
        "volume": latest_volume,
        "turnover": latest_turnover,
        "trades": latest_trades,
        "candles": [],
        "comparisonSeries": {"day": day_series},
        "benchmarkComparisonSeries": {"day": benchmark_day_series},
        "chartIntervals": {
            "supported": ["day", "week"],
            "intradayAvailable": False,
        },
    }
    with cache_lock:
        cache_data["sector_charts"][cache_key] = {
            "stored_at": now,
            "payload": payload,
        }
    return jsonify(payload)


@app.route("/api/market/penny-sector-recommendations")
def api_market_penny_sector_recommendations():
    try:
        return jsonify(build_all_market_penny_sector_recommendations())
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("PENNY_SECTOR_RECOMMENDATIONS_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)

@app.route("/api/market/international-indexes")
def api_market_international_indexes():
    ensure_cache()
    with cache_lock:
        site_data = cache_data["site_data"] or {}
        cached_indexes = site_data.get("marketInternationalIndexes") or []
    cached_usable_count = sum(
        1
        for item in cached_indexes
        if isinstance(item, dict) and len(item.get("series") or []) >= 2
    )
    if len(cached_indexes) >= len(INTERNATIONAL_INDEX_SPECS) and cached_usable_count >= 12:
        return jsonify({"count": len(cached_indexes), "indexes": cached_indexes, "cached": True})

    indexes = fetch_international_market_indexes()
    with cache_lock:
        if cache_data["site_data"]:
            cache_data["site_data"]["marketInternationalIndexes"] = indexes
            save_disk_cache()
    return jsonify({"count": len(indexes), "indexes": indexes, "cached": False})


def global_market_refresh_requested() -> bool:
    try:
        return request.args.get("refresh") in {"1", "true", "yes"}
    except RuntimeError:
        return False



@app.route("/api/global-market/<category>")
def api_global_market(category: str):
    category_key = category.strip().lower()
    if category_key not in GLOBAL_MARKET_CATEGORIES:
        return jsonify({"error": "不支援的市場分類"}), 404

    refresh = request.args.get("refresh") in {"1", "true", "yes"}
    option_source = normalize_taiwan_option_source(str(request.args.get("optionSource") or request.args.get("source") or "auto"))
    option_underlying = normalize_taiwan_option_underlying(str(request.args.get("underlying") or request.args.get("optionUnderlying") or TAIWAN_OPTION_DEFAULT_PRODUCT))
    raw_limit = str(request.args.get("limit") or "").strip().lower()
    if raw_limit in {"all", "full", "0"}:
        requested_limit = len(GLOBAL_MARKET_CATEGORIES[category_key]["items"])
    else:
        try:
            requested_limit = int(raw_limit or str(GLOBAL_MARKET_DEFAULT_LOAD_LIMIT))
        except ValueError:
            requested_limit = GLOBAL_MARKET_DEFAULT_LOAD_LIMIT
    limit = min(max(requested_limit, 1), GLOBAL_MARKET_MAX_LOAD_LIMIT)
    now = time.time()
    cache_key = f"{category_key}:{limit}:{option_underlying}:{option_source if category_key == 'options' else 'default'}"
    with cache_lock:
        cached = cache_data["global_markets"].get(cache_key)
    cached_payload = cached.get("payload") if cached else None
    cached_items = cached_payload.get("items", []) if isinstance(cached_payload, dict) else []
    cached_vix = next((item for item in cached_items if item.get("symbol") == "^VIX"), None)
    cache_is_stale_us_vix = category_key == "us-stocks" and (not cached_vix or cached_vix.get("error") or cached_vix.get("close") in {None, "--"})
    cache_has_missing_items = any(
        item.get("error") or parse_float(str(item.get("close") or "")) is None
        for item in cached_items
    )
    cache_is_stale_derivative_payload = category_key in {"futures", "options"} and cache_has_missing_items
    if (
        not refresh
        and cached
        and not cache_is_stale_us_vix
        and not cache_is_stale_derivative_payload
        and now - cached.get("stored_at", 0) < GLOBAL_MARKET_CACHE_SECONDS
    ):
        cached_payload = copy.deepcopy(cached["payload"])
        if category_key == "futures":
            cached_payload["items"] = [normalize_futures_yahoo_uncovered_links(item) for item in cached_payload.get("items", [])]
        return jsonify({**cached_payload, "cached": True})

    is_leader, flight = claim_cache_flight(f"global-market:{cache_key}")
    if not is_leader:
        flight.wait(CACHE_FLIGHT_WAIT_SECONDS)
        with cache_lock:
            refreshed = cache_data["global_markets"].get(cache_key)
        if refreshed and refreshed.get("payload"):
            shared_payload = copy.deepcopy(refreshed["payload"])
            if category_key == "futures":
                shared_payload["items"] = [normalize_futures_yahoo_uncovered_links(item) for item in shared_payload.get("items", [])]
            return jsonify({**shared_payload, "cached": True})
        return jsonify(api_error_payload("CACHE_REFRESH_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE)), 503

    try:
        payload = build_global_market_payload(category_key, limit, option_source=option_source, option_underlying=option_underlying)
        with cache_lock:
            cache_data["global_markets"][cache_key] = {"stored_at": time.time(), "payload": payload}
        return jsonify({**payload, "cached": False})
    finally:
        finish_cache_flight(f"global-market:{cache_key}", flight)


def derivative_request_limit(default: int = 24, maximum: int = 100) -> int:
    raw_limit = str(request.args.get("limit") or default).strip().lower()
    if raw_limit in {"all", "full", "0"}:
        return maximum
    try:
        requested = int(raw_limit)
    except ValueError:
        requested = default
    return min(max(requested, 1), maximum)


def find_derivative_spec(category: str, symbol: str) -> dict[str, Any] | None:
    clean_symbol = str(symbol or "").strip().upper()
    for item in GLOBAL_MARKET_CATEGORIES.get(category, {}).get("items", []):
        if str(item.get("symbol") or "").strip().upper() == clean_symbol:
            return enrich_global_market_spec(item, category)
    return None


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


def search_us_market_universe(query: str, limit: int = 40) -> list[dict[str, Any]]:
    keyword = query.strip().lower()
    if not keyword:
        return [normalize_us_market_search_item(item) for item in US_MARKET_SEARCH_UNIVERSE[:limit]]
    matches = []
    for item in US_MARKET_SEARCH_UNIVERSE:
        symbol = str(item.get("symbol") or "").lower()
        name = str(item.get("name") or "").lower()
        group = str(item.get("group") or "").lower()
        item_type = str(item.get("type") or "").lower()
        if keyword in symbol or keyword in name or keyword in group or keyword in item_type:
            matches.append(normalize_us_market_search_item({**item, "source": "內建美股/ETF清單"}))
    return matches[:limit]


def search_us_listed_universe(query: str, limit: int = 80) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    keyword = query.strip().lower()
    keyword_alt = keyword.replace(".", "-")
    if not keyword:
        return [], {}, "請輸入代號或名稱後搜尋全上市美股 / ETF"
    universe, totals, source = fetch_us_listed_universe_with_fallback(False)
    matches: list[dict[str, Any]] = []
    for item in universe:
        symbol = str(item.get("symbol") or "").lower()
        name = str(item.get("name") or "").lower()
        group = str(item.get("group") or "").lower()
        item_type = str(item.get("type") or "").lower()
        exchange = str(item.get("exchange") or "").lower()
        if (
            symbol.startswith(keyword)
            or keyword in symbol
            or (keyword_alt and (symbol.startswith(keyword_alt) or keyword_alt in symbol))
            or keyword in name
            or keyword in group
            or keyword in item_type
            or keyword in exchange
        ):
            matches.append(normalize_us_market_search_item(item))
            if len(matches) >= limit:
                break
    return matches, totals, source


def find_us_listed_symbol(symbol: str) -> dict[str, Any] | None:
    clean_symbol = normalize_us_symbol_for_yahoo(symbol)
    universe, _totals, _source = fetch_us_listed_universe_with_fallback(False)
    return next((item for item in universe if str(item.get("symbol") or "").upper() == clean_symbol), None)


US_ETF_CENTER_CACHE_SECONDS = 5 * 60


@app.route("/api/us-market/etf-center")
def api_us_market_etf_center():
    query = request.args.get("q", "").strip()
    refresh = request.args.get("refresh") in {"1", "true", "yes"}
    try:
        directory_limit = min(max(int(request.args.get("directoryLimit", "7000")), 1), 8000)
    except ValueError:
        directory_limit = 7000
    try:
        quote_limit = min(max(int(request.args.get("quoteLimit", "48")), 0), 80)
    except ValueError:
        quote_limit = 48

    now = time.time()
    cache_key = f"{query.lower()}:{directory_limit}:{quote_limit}"
    with cache_lock:
        cached = cache_data["us_etf_center"].get(cache_key)
    if not refresh and cached and now - cached.get("stored_at", 0) < US_ETF_CENTER_CACHE_SECONDS:
        return jsonify({**cached["payload"], "cached": True})

    is_leader, flight = claim_cache_flight(f"us-etf-center:{cache_key}")
    if not is_leader:
        flight.wait(CACHE_FLIGHT_WAIT_SECONDS)
        with cache_lock:
            refreshed = cache_data["us_etf_center"].get(cache_key)
        if refreshed and refreshed.get("payload"):
            return jsonify({**copy.deepcopy(refreshed["payload"]), "cached": True})
        return jsonify(api_error_payload("CACHE_REFRESH_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE)), 503

    try:
        payload = build_us_etf_center_payload(query, directory_limit, quote_limit, refresh)
        with cache_lock:
            cache_data["us_etf_center"][cache_key] = {"stored_at": time.time(), "payload": payload}
        return jsonify({**payload, "cached": False})
    finally:
        finish_cache_flight(f"us-etf-center:{cache_key}", flight)


@app.route("/api/us-market/search")
def api_us_market_search():
    query = request.args.get("q", "").strip()
    if not query:
        totals: dict[str, int] = {}
        source = "Nasdaq Trader 官方 Symbol Directory"
        try:
            _items, totals = fetch_nasdaq_trader_us_listed_universe(False)
        except Exception:
            totals = {
                "美股個股": sum(1 for item in US_MARKET_SEARCH_UNIVERSE if item.get("group") == "美股個股"),
                "美股 ETF": sum(1 for item in US_MARKET_SEARCH_UNIVERSE if item.get("group") == "美股 ETF"),
            }
            source = "內建美股/ETF清單"
        return jsonify({
            "query": query,
            "count": 0,
            "totals": totals,
            "source": source,
            "results": [],
            "message": "請輸入代號或名稱後搜尋全上市美股 / ETF。",
        })
    def run_listed_search() -> tuple[list[dict[str, Any]], dict[str, int], str]:
        try:
            return search_us_listed_universe(query, 120)
        except Exception:
            return [], {}, ""

    def run_nyse_search() -> tuple[list[dict[str, Any]], dict[str, int]]:
        try:
            return fetch_nyse_us_market_search(query, 60)
        except Exception:
            return [], {}

    def run_yahoo_search() -> list[dict[str, Any]]:
        try:
            return fetch_yahoo_us_market_search(query, 20)
        except Exception:
            return []

    # These four sources are independent (results are merged, not tried-until-success),
    # so they are fetched concurrently instead of one blocking call after another.
    local_results = search_us_market_universe(query, 30)
    with ThreadPoolExecutor(max_workers=3) as executor:
        listed_future = executor.submit(run_listed_search)
        nyse_future = executor.submit(run_nyse_search)
        yahoo_future = executor.submit(run_yahoo_search)
        listed_results, listed_totals, listed_source = listed_future.result()
        nyse_results, nyse_totals = nyse_future.result()
        yahoo_results = yahoo_future.result()

    merged: dict[str, dict[str, Any]] = {}
    for item in [*listed_results, *nyse_results, *local_results, *yahoo_results]:
        symbol = item.get("symbol")
        if symbol and symbol not in merged:
            merged[symbol] = item
    results = list(merged.values())[:120]
    totals = {**nyse_totals, **listed_totals}
    sources = [source for source in [listed_source, "NYSE Listings Directory", "Yahoo Finance 行情補充"] if source]
    return jsonify({
        "query": query,
        "count": len(results),
        "totals": totals,
        "source": " + ".join(dict.fromkeys(sources)) or "NYSE Listings Directory + Yahoo Finance 行情補充",
        "results": results,
    })


@app.route("/api/us-market/listed")
def api_us_market_listed():
    query = request.args.get("q", "").strip().lower()
    try:
        limit = min(max(int(request.args.get("limit", "200")), 1), 8000)
    except ValueError:
        limit = 200
    refresh = request.args.get("refresh") in {"1", "true", "yes"}
    universe, totals, source = fetch_us_listed_universe_with_fallback(refresh)

    if query:
        filtered = []
        for item in universe:
            haystack = " ".join(str(item.get(key) or "").lower() for key in ("symbol", "name", "type", "group", "exchange"))
            if query in haystack:
                filtered.append(item)
    else:
        filtered = universe
    return jsonify({
        "query": query,
        "count": len(filtered),
        "returned": min(len(filtered), limit),
        "totals": totals,
        "source": source,
        "results": filtered[:limit],
    })


@app.route("/api/us-market/nyse-listed")
def api_us_market_nyse_listed():
    query = request.args.get("q", "").strip()
    kind = request.args.get("kind", "stock").strip().lower()
    try:
        limit = min(max(int(request.args.get("limit", "7000")), 1), 8000)
    except ValueError:
        limit = 7000
    instrument_type = "EXCHANGE_TRADED_FUND" if kind in {"etf", "fund"} else "EQUITY"
    group = "美股 ETF" if instrument_type == "EXCHANGE_TRADED_FUND" else "美股個股"
    try:
        results, total = fetch_nyse_directory_items(query, instrument_type, group, limit)
        source = "NYSE Listings Directory"
        error = ""
    except Exception as exc:
        LOGGER.exception("NYSE listed directory fallback used", exc_info=exc)
        results = [
            normalize_us_market_search_item(item)
            for item in US_MARKET_SEARCH_UNIVERSE
            if item.get("group") == group and (
                not query
                or query.lower() in str(item.get("symbol", "")).lower()
                or query.lower() in str(item.get("name", "")).lower()
            )
        ][:limit]
        total = len(results)
        source = "內建美股清單"
        error = "NYSE 官方目錄暫時無法載入，已改用內建清單"
    return jsonify({
        "query": query,
        "kind": kind,
        "instrumentType": instrument_type,
        "group": group,
        "total": total,
        "count": len(results),
        "returned": len(results),
        "source": source,
        "error": error,
        "results": results,
    })


def unix_timestamp_from_iso_date(date_text: str | None) -> int | None:
    if not date_text:
        return None
    try:
        return int(datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def lock_public_option_chain_payload(payload: dict[str, Any], requested_symbol: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    clean_requested = normalize_us_symbol_for_yahoo(re.sub(r"[^A-Za-z0-9=.^_-]", "", requested_symbol or "").upper())
    source = str(payload.get("source") or "")
    source_url = str(payload.get("sourceUrl") or "")
    chain_symbol = str(payload.get("symbol") or clean_requested)
    locked_payload = {
        **payload,
        "sourceLocked": True,
        "apiDataLocked": True,
        "apiLocked": True,
        "proxyAllowed": False,
        "fallbackAllowed": False,
        "sourceLock": {
            "status": "locked",
            "scope": "exact_product_call_put_chain",
            "requestedSymbol": clean_requested,
            "chainSymbol": chain_symbol,
            "isSameProduct": chain_symbol == clean_requested,
            "source": source,
            "sourceUrl": source_url,
            "apiProvider": source,
            "apiEndpoint": source_url,
            "proxyAllowed": False,
            "fallbackAllowed": False,
            "sameUnderlyingFallbackAllowed": False,
            "policy": "Use only verified same-product Call/Put strike chain APIs. Do not substitute another product as proxy.",
        },
    }
    return locked_payload


def can_use_yahoo_options_fallback(clean_symbol: str) -> bool:
    return bool(clean_symbol and not clean_symbol.startswith(("_", "^")) and "=F" not in clean_symbol and "=X" not in clean_symbol and not clean_symbol.endswith("-USD"))


@app.route("/api/us-market/options-chain/<symbol>")
def api_us_market_options_chain(symbol: str):
    expiration = request.args.get("expiration")
    try:
        chain = build_public_options_chain(symbol, expiration)
    except Exception as exc:
        LOGGER.exception("US options chain load failed", exc_info=exc)
        chain = {
            "symbol": normalize_us_symbol_for_yahoo(symbol),
            "error": "選擇權資料暫時無法載入，請稍後再試",
            "source": "Cboe Delayed Quotes Options",
        }
    chain = lock_public_option_chain_payload(chain, symbol)
    status = 400 if chain.get("error") and not chain.get("symbol") else 200
    return jsonify(chain), status


@app.route("/api/us-market/symbol/<symbol>")
def api_us_market_symbol(symbol: str):
    clean_symbol = re.sub(r"[^A-Za-z0-9=.^_-]", "", symbol or "").upper()
    if not clean_symbol:
        return jsonify({"error": "請輸入美股代號"}), 400

    clean_symbol = normalize_us_symbol_for_yahoo(clean_symbol)
    matched = find_us_listed_symbol(clean_symbol)
    spec = matched or {
        "symbol": clean_symbol,
        "name": clean_symbol,
        "type": "美股 / ETF",
        "group": "美股搜尋",
    }
    item = build_us_market_symbol_detail(spec)
    return jsonify(item)


@app.route("/api/us-market/sector-stocks")
def api_us_market_sector_stocks():
    sector_key = request.args.get("sector", "^SP500-45").strip()
    group = US_SECTOR_STOCK_GROUPS.get(sector_key) or US_SECTOR_STOCK_GROUPS["^SP500-45"]
    try:
        limit = min(max(int(request.args.get("limit", "12")), 1), 30)
    except ValueError:
        limit = 12

    specs = [
        {**stock, "group": "美股個股", "sectorKey": sector_key, "sectorLabel": group["label"]}
        for stock in group["stocks"][:limit]
    ]
    items: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(6, len(specs))) as executor:
        futures = [executor.submit(build_global_market_item, spec) for spec in specs]
        for future in as_completed(futures):
            items.append(future.result())
    order = {spec["symbol"]: index for index, spec in enumerate(specs)}
    items.sort(key=lambda item: order.get(str(item.get("symbol")), 999))
    usable = [item for item in items if not item.get("error")]
    return jsonify({
        "sector": sector_key,
        "label": group["label"],
        "count": len(items),
        "usable": len(usable),
        "source": "Yahoo Finance 線上資料",
        "items": items,
    })


@app.route("/twse-data.js")
def twse_data_script():
    ensure_cache()
    with cache_lock:
        site_payload = json.dumps(cache_data["site_data"], ensure_ascii=False)
        stocks_payload = json.dumps(cache_data["all_stocks"], ensure_ascii=False)
    script = (
        f"window.TWSE_DATA = {site_payload};\n"
        f"window.TWSE_ALL_STOCKS = {stocks_payload};\n"
    )
    return Response(script, mimetype="application/javascript")


@app.route("/api/twse/all-stocks")
def api_all_stocks():
    ensure_cache()
    with cache_lock:
        stocks = list(cache_data["all_stocks"])
        market_date = cache_data["market_date"]
        cached_at = cache_data["cached_at"]

    return jsonify(
        {
            "snapshotDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d"),
            "cachedAt": cached_at,
            "count": len(stocks),
            "stocks": stocks,
        }
    )


TW_ETF_CATEGORY_DEFINITIONS = [
    {"key": "high-dividend", "label": "高股息 / 收益", "keywords": ("高股息", "高息", "收益", "股利", "股息", "優息", "息收")},
    {"key": "market-cap", "label": "市值型 / 大盤", "keywords": ("50", "五十", "台灣50", "臺灣50", "摩台", "加權", "市值", "臺灣卓越")},
    {"key": "technology", "label": "科技 / 半導體", "keywords": ("科技", "半導體", "電子", "AI", "5G", "電動車", "晶片", "未來")},
    {"key": "finance", "label": "金融 / 低波", "keywords": ("金融", "低波", "低碳", "ESG", "永續", "治理")},
    {"key": "bond", "label": "債券 / 固收", "keywords": ("債", "公司債", "投資級", "美債", "公債", "金融債", "優選收益")},
    {"key": "leveraged-inverse", "label": "槓桿 / 反向", "keywords": ("正2", "反1", "反向", "槓桿", "2X", "2倍")},
    {"key": "overseas", "label": "海外 / 主題", "keywords": ("美國", "日本", "中國", "印度", "越南", "全球", "NASDAQ", "標普", "S&P", "道瓊", "恆生", "香港")},
    {"key": "active", "label": "主動式", "keywords": ("主動",)},
]


def classify_tw_etf_category(stock: dict[str, Any]) -> dict[str, str]:
    name = str(stock.get("name") or "")
    code = str(stock.get("code") or "")
    text = f"{code} {name}".upper()
    for category in TW_ETF_CATEGORY_DEFINITIONS:
        if any(keyword.upper() in text for keyword in category["keywords"]):
            return {"key": category["key"], "label": category["label"]}
    return {"key": "other", "label": "其他 ETF"}


def normalize_tw_etf_item(stock: dict[str, Any]) -> dict[str, Any]:
    pct_value = parse_float(str(stock.get("pct") or ""))
    volume_value = parse_float(str(stock.get("volumeValue") or stock.get("volume") or ""))
    turnover_value = parse_float(str(stock.get("turnoverValue") or stock.get("turnover") or ""))
    volatility_value = parse_float(str((stock.get("technicalAnalysis") or {}).get("volatilityPct") or ""))
    category = classify_tw_etf_category(stock)
    code = str(stock.get("code") or "")
    name = str(stock.get("name") or "")
    is_high_dividend = category["key"] == "high-dividend"
    is_bond = category["key"] == "bond"
    is_leveraged = category["key"] == "leveraged-inverse"
    liquidity_score = 0
    if volume_value is not None:
        liquidity_score = min(35, math.log10(max(volume_value, 1)) * 5)
    risk_score = (
        (volatility_value or 0) * 12
        + abs(pct_value or 0) * 4
        + (18 if is_leveraged else 0)
        + max(0, 20 - liquidity_score)
    )
    risk_level = "低"
    if risk_score >= 55:
        risk_level = "高"
    elif risk_score >= 32:
        risk_level = "中"
    dividend_profile = "依投信公告"
    if is_high_dividend:
        dividend_profile = "高股息 ETF，適合搭配除息日、填息天數與年化配息率觀察"
    elif is_bond:
        dividend_profile = "債券 ETF，配息與利率週期、匯率與信用利差連動"
    elif is_leveraged:
        dividend_profile = "槓桿/反向 ETF，偏交易工具，不宜只用配息觀察"
    return {
        "code": code,
        "name": name,
        "market": stock.get("market") or "",
        "marketLabel": stock.get("marketLabel") or "",
        "category": category["key"],
        "categoryLabel": category["label"],
        "close": stock.get("close") or "--",
        "change": stock.get("change") or "--",
        "pct": stock.get("pct") or "--",
        "pctValue": pct_value,
        "volume": stock.get("volume") or "--",
        "volumeValue": volume_value,
        "turnover": stock.get("turnover") or "--",
        "turnoverValue": turnover_value,
        "trades": stock.get("trades") or "--",
        "open": stock.get("open") or "--",
        "high": stock.get("high") or "--",
        "low": stock.get("low") or "--",
        "tone": stock.get("tone") or "flat",
        "technicalAnalysis": stock.get("technicalAnalysis") or {},
        "volatilityPct": volatility_value,
        "riskScore": round(risk_score, 2),
        "riskLevel": risk_level,
        "dividendProfile": dividend_profile,
        "detailUrl": f"tw-stock-search.html?q={quote(code)}&market={quote(str(stock.get('market') or ''))}",
    }


def tw_etf_sort_key(item: dict[str, Any], sort_key: str) -> Any:
    if sort_key == "return_asc":
        return item.get("pctValue") if item.get("pctValue") is not None else 999999
    if sort_key == "volume_desc":
        return -(item.get("volumeValue") or 0)
    if sort_key == "turnover_desc":
        return -(item.get("turnoverValue") or 0)
    if sort_key == "volatility_desc":
        return -(item.get("volatilityPct") or 0)
    if sort_key == "risk_desc":
        return -(item.get("riskScore") or 0)
    if sort_key == "code":
        return str(item.get("code") or "")
    return -(item.get("pctValue") if item.get("pctValue") is not None else -999999)


@app.route("/api/twse/etfs")
def api_twse_etfs():
    ensure_cache()
    query = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "all").strip()
    sort_key = request.args.get("sort", "return_desc").strip()
    limit_text = request.args.get("limit", "240").strip().lower()
    try:
        limit = 1000 if limit_text == "all" else min(max(int(limit_text), 1), 1000)
    except ValueError:
        limit = 240

    with cache_lock:
        stocks = list(cache_data["all_stocks"])
        market_date = cache_data["market_date"]
        cached_at = cache_data["cached_at"]
        site_data = dict(cache_data.get("site_data") or {})

    etfs = [normalize_tw_etf_item(stock) for stock in stocks if is_etf_stock(stock)]
    category_counts: dict[str, int] = {}
    for item in etfs:
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1

    filtered = etfs
    if category and category != "all":
        filtered = [item for item in filtered if item["category"] == category]
    if query:
        filtered = [
            item for item in filtered
            if query in str(item.get("code") or "").lower()
            or query in str(item.get("name") or "").lower()
            or query in str(item.get("categoryLabel") or "").lower()
        ]
    filtered.sort(key=lambda item: tw_etf_sort_key(item, sort_key))
    returned = filtered[:limit]

    values = [item["pctValue"] for item in etfs if item.get("pctValue") is not None]
    total_volume = sum(item.get("volumeValue") or 0 for item in etfs)
    total_turnover = sum(item.get("turnoverValue") or 0 for item in etfs)
    default_compare_codes = ["0050", "006208", "0056", "00878", "00919", "00929"]
    compare_items = [item for code in default_compare_codes for item in etfs if item["code"] == code]
    if len(compare_items) < 4:
        existing_codes = {item["code"] for item in compare_items}
        compare_items.extend([item for item in sorted(etfs, key=lambda entry: -(entry.get("turnoverValue") or 0)) if item["code"] not in existing_codes][: 6 - len(compare_items)])

    return jsonify({
        "query": query,
        "category": category,
        "sort": sort_key,
        "snapshotDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d") if market_date else site_data.get("snapshotDate"),
        "cachedAt": cached_at,
        "count": len(filtered),
        "totalCount": len(etfs),
        "returned": len(returned),
        "categories": [
            {"key": "all", "label": "全部 ETF", "count": len(etfs)},
            *[
                {"key": item["key"], "label": item["label"], "count": category_counts.get(item["key"], 0)}
                for item in TW_ETF_CATEGORY_DEFINITIONS
            ],
            {"key": "other", "label": "其他 ETF", "count": category_counts.get("other", 0)},
        ],
        "summary": {
            "twseCount": sum(1 for item in etfs if str(item.get("market")).upper() == "TWSE"),
            "tpexCount": sum(1 for item in etfs if str(item.get("market")).upper() == "TPEX"),
            "highDividendCount": category_counts.get("high-dividend", 0),
            "bondCount": category_counts.get("bond", 0),
            "leveragedInverseCount": category_counts.get("leveraged-inverse", 0),
            "averageReturnPct": round(sum(values) / len(values), 2) if values else None,
            "totalVolume": total_volume,
            "totalTurnover": total_turnover,
        },
        "rankings": {
            "topReturn": sorted(etfs, key=lambda item: -(item.get("pctValue") if item.get("pctValue") is not None else -999999))[:8],
            "weakReturn": sorted(etfs, key=lambda item: item.get("pctValue") if item.get("pctValue") is not None else 999999)[:8],
            "topVolume": sorted(etfs, key=lambda item: -(item.get("volumeValue") or 0))[:8],
            "highRisk": sorted(etfs, key=lambda item: -(item.get("riskScore") or 0))[:8],
            "highDividend": [item for item in sorted(etfs, key=lambda entry: -(entry.get("turnoverValue") or 0)) if item["category"] == "high-dividend"][:8],
        },
        "compare": compare_items[:6],
        "items": returned,
        "sourceLinks": {
            "twseEtf": "https://www.twse.com.tw/zh/products/securities/etf/products/domestic.html",
            "tpexEtf": YAHOO_TPEX_ETF_URL,
        },
    })


@app.route("/api/twse/search")
def api_stock_search():
    ensure_cache()
    query = request.args.get("q", "").strip()
    with cache_lock:
        stocks = list(cache_data["all_stocks"])
        cached_at = cache_data["cached_at"]
        market_date = cache_data["market_date"]

    matches = find_stock_by_query(query, stocks)
    return jsonify(
        {
            "query": query,
            "snapshotDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d") if market_date else None,
            "cachedAt": cached_at,
            "count": len(matches),
            "results": matches,
        }
    )


@app.route("/api/twse/stock/<code>")
def api_stock_detail(code: str):
    history_mode = request.args.get("history", "recent").strip().lower()
    refresh = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes", "on"}
    quick = request.args.get("quick", "").strip().lower() in {"1", "true", "yes", "on"}
    defer_slow = request.args.get("deferSlow", "").strip().lower() in {"1", "true", "yes", "on"}
    requested_market = request.args.get("market", "").strip().upper()
    code_key = str(code or "").strip().upper()
    months_back = STOCK_HISTORY_MAX_MONTHS if history_mode == "all" else STOCK_HISTORY_RECENT_MONTHS

    if refresh:
        try:
            stock, market_date, tpex_quote_date, _sources = pick_exact_live_stock(code_key, requested_market)
            if stock is None and requested_market:
                stock, market_date, tpex_quote_date, _sources = pick_exact_live_stock(code_key, "")
        except Exception as exc:  # noqa: BLE001
            return api_exception_response("LIVE_STOCK_DETAIL_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
        if stock is None:
            return jsonify({"error": "查無個股資料", "code": code_key}), 404
        if stock.get("market") == "TPEx" and not quick:
            stock = apply_yahoo_quote(stock)
        detail_market_date = tpex_quote_date if stock.get("market") == "TPEx" and tpex_quote_date else market_date
        detail = build_stock_detail(
            stock,
            detail_market_date,
            site_data=None,
            months_back=months_back,
            quick=quick,
            include_shareholders=not defer_slow,
            include_institutional_history=not defer_slow,
        )
        detail = {**detail, "cachedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S")}
        return jsonify(detail)

    ensure_cache()
    with cache_lock:
        stocks = list(cache_data["all_stocks"])
        market_date = cache_data["market_date"]
        cached_at = cache_data["cached_at"]
        site_data = cache_data["site_data"]
        stock_details = cache_data["stock_details"]

    stock = next(
        (
            item
            for item in stocks
            if str(item.get("code") or "").strip().upper() == code_key
            and (not requested_market or normalize_market_request(str(item.get("market", ""))) == normalize_market_request(requested_market))
        ),
        None,
    )
    if stock is None and requested_market:
        stock = next(
            (
                item
                for item in stocks
                if str(item.get("code") or "").strip().upper() == code_key
            ),
            None,
        )
    if stock is None:
        return jsonify({"error": "查無個股資料", "code": code_key}), 404
    detail_mode = "quick" if quick else "full"
    cache_key = f"{stock.get('market', 'TWSE')}:{stock.get('code', code_key)}:{market_date}:{history_mode}:{months_back}:{detail_mode}"
    with cache_lock:
        detail = stock_details.get(cache_key)

    if detail is None:
        is_leader, flight = claim_cache_flight(f"stock-detail:{cache_key}")
        if not is_leader:
            flight.wait(CACHE_FLIGHT_WAIT_SECONDS)
            with cache_lock:
                detail = cache_data["stock_details"].get(cache_key)
            if detail is None:
                return jsonify(api_error_payload("CACHE_REFRESH_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE)), 503
        else:
            try:
                if stock.get("market") == "TPEx" and not quick:
                    stock = apply_yahoo_quote(stock)
                detail = build_stock_detail(
                    stock,
                    market_date,
                    site_data=site_data,
                    months_back=months_back,
                    quick=quick,
                    include_shareholders=not defer_slow,
                    include_institutional_history=not defer_slow,
                )
                with cache_lock:
                    cache_data["stock_details"][cache_key] = detail
            finally:
                finish_cache_flight(f"stock-detail:{cache_key}", flight)

    detail = {**detail, "cachedAt": cached_at}
    return jsonify(detail)


@app.route("/api/twse/stock/<code>/shareholders")
def api_stock_shareholders(code: str):
    try:
        distribution = fetch_shareholder_distribution(str(code).strip())
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("LIVE_SHAREHOLDERS_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
    return jsonify(
        {
            "code": str(code).strip(),
            "shareholderDistribution": distribution,
            "cachedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


@app.route("/api/twse/stock/<code>/institutional-history")
def api_stock_institutional_history(code: str):
    requested_market = request.args.get("market", "").strip().upper()
    code_key = str(code or "").strip().upper()
    range_key = request.args.get("range", "").strip().lower()
    range_config = get_institutional_history_range_config(range_key)
    try:
        requested_limit = int(request.args.get("limit") or range_config.get("limit") or 30)
    except (TypeError, ValueError):
        requested_limit = int(range_config.get("limit") or 30)
    requested_limit = max(5, min(requested_limit, int(range_config.get("limit") or requested_limit)))

    try:
        stock, market_date, _tpex_quote_date, _sources = pick_exact_live_stock(code_key, requested_market)
        if stock is None and requested_market:
            stock, market_date, _tpex_quote_date, _sources = pick_exact_live_stock(code_key, "")
    except Exception as exc:  # noqa: BLE001
        return api_exception_response("LIVE_INSTITUTIONAL_HISTORY_UNAVAILABLE", PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
    if stock is None:
        return jsonify({"error": "\u67e5\u7121\u500b\u80a1\u8cc7\u6599", "code": code_key}), 404

    market = str(stock.get("market") or "TWSE").upper()
    if market != "TWSE":
        yahoo_payload = fetch_yahoo_institutional_trading(stock, requested_limit)
        history = build_institutional_history_from_yahoo(yahoo_payload, requested_limit)
        history["range"] = range_key or "yahoo"
        return jsonify(
            {
                "code": code_key,
                "market": stock.get("market"),
                "institutionalTradeHistory": history,
                "institutionalTrades": build_latest_stock_institutional_trade(history),
                "cachedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    trading_dates: list[str] = []
    if range_key:
        try:
            trading_dates = fetch_yahoo_trading_dates_for_institutional_range(stock, range_key)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Yahoo trading dates for institutional range failed for %s", code_key)
            trading_dates = []
    if not trading_dates:
        try:
            rows = fetch_yahoo_history_rows(stock["code"], STOCK_HISTORY_RECENT_MONTHS, market=stock.get("market") or "TWSE")
        except Exception:  # noqa: BLE001
            rows = []
        trading_dates = build_institutional_trade_candidate_dates(rows, market_date, max(70, requested_limit * 2))

    history = fetch_stock_institutional_trade_history(stock, market_date, requested_limit, trading_dates)
    if not history.get("rows"):
        yahoo_payload = fetch_yahoo_institutional_trading(stock, requested_limit)
        history = build_institutional_history_from_yahoo(yahoo_payload, requested_limit)
    history["range"] = range_key or "recent"
    if history.get("source") == "TWSE T86":
        history["sourceNote"] = "TWSE T86 real institutional trading data. Long ranges use sampled trading dates for responsive loading."
    history["requestedLimit"] = requested_limit
    history["candidateCount"] = len(trading_dates)
    return jsonify(
        {
            "code": code_key,
            "market": stock.get("market"),
            "institutionalTradeHistory": history,
            "institutionalTrades": build_latest_stock_institutional_trade(history),
            "cachedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )

@app.route("/manifest.webmanifest")
def pwa_manifest():
    response = send_from_directory(BASE_DIR, "manifest.webmanifest", mimetype="application/manifest+json")
    return no_store_static_response(response)


@app.route("/service-worker.js")
def pwa_service_worker():
    response = send_from_directory(BASE_DIR, "service-worker.js", mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return no_store_static_response(response)


def no_store_static_response(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def send_no_store_root_file(filename: str, **kwargs: Any) -> Response:
    response = send_from_directory(BASE_DIR, filename, **kwargs)
    return no_store_static_response(response)


def redirect_legacy_page(target: str):
    query = request.query_string.decode("utf-8")
    if query:
        target = f"{target}?{query}"
    return redirect(target, code=301)


@app.route("/sectors.html")
def legacy_sectors_page():
    return redirect_legacy_page("/tw-stocks.html")


@app.route("/stock-search.html")
def legacy_stock_search_page():
    return redirect_legacy_page("/tw-stock-search.html")


@app.route("/Optional-stocks.html")
def legacy_optional_stocks_page():
    return redirect_legacy_page("/tw-Optional-stocks.html")



for page_index, (route, filename) in enumerate(PAGE_ROUTES.items()):
    app.add_url_rule(
        route,
        endpoint=f"static_page_{page_index}_{filename}",
        view_func=lambda filename=filename: send_no_store_root_file(filename),
    )


@app.route("/assets/<path:filename>")
def whitelisted_assets(filename: str):
    normalized = filename.replace("\\", "/").lstrip("/")
    if "/" in normalized or normalized not in ASSET_STATIC_FILES:
        abort(404)
    return send_from_directory(BASE_DIR / "assets", normalized)


@app.route("/<path:filename>")
def static_files(filename: str):
    normalized = filename.replace("\\", "/").lstrip("/")
    if "/" in normalized or normalized not in ROOT_STATIC_FILES:
        abort(404)
    return send_no_store_root_file(normalized)


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
