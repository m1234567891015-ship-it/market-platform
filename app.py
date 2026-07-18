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
from derivatives.futures import build_source_pending_market_item, is_source_pending_product
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
    build_all_market_penny_sector_recommendations,
    build_derivative_candles,
    build_futures_ai_analysis,
    build_index_technical_analysis,
    build_institution_payload_live,
    build_institutions_url,
    build_intraday_index_candles,
    build_intraday_technical_analysis,
    build_public_options_chain,
    build_sector_fund_flow,
    build_sector_history_series,
    build_site_data_view,
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
    normalize_taiwan_option_underlying,
    parse_yahoo_quote_items,
    resolve_sector_key,
    summarize_taifex_option_rows,
)
from market_config import (
    ASSET_CATEGORY_SOURCE_INFO,
    ASSET_REGION_ORDER,
    ASSET_STATIC_FILES,
    CBOE_OPTIONS_BASE,
    EXCLUDED_SECTOR_SOURCE_NAMES,
    GLOBAL_MACRO_ASSET_SCHEMA,
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
    SECTOR_INDEX_LOOKUP,
    SUPPORTED_CHART_INTERVALS,
    TAIFEX_FUTURES_DAILY_URL,
    TAIFEX_OPTIONS_DAILY_URL,
    TAIFEX_OPTIONS_PC_RATIO_URL,
    TARGET_INDEX_NAMES,
    TDCC_HOLDING_DISTRIBUTION_URL,
    TPEX_OPENAPI_BASE,
    TWSE_BASE,
    TWSE_MARGIN_URL,
    TWSE_OPENAPI_BASE,
    US_TREASURY_YIELD_CURVE_CSV_URL,
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
STOCK_HISTORY_RECENT_MONTHS = 3
STOCK_HISTORY_MAX_MONTHS = 480
WEIGHTED_INDEX_HISTORY_TRADING_DAYS = 480
GLOBAL_MARKET_ITEM_CACHE_SECONDS = 5 * 60


class DeadlineThreadPoolExecutor(ThreadPoolExecutor):
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=False, cancel_futures=True)
        return False


def infer_global_asset_metadata(spec: dict[str, Any], category: str) -> dict[str, str]:
    symbol = str(spec.get("symbol") or "").upper()
    name = str(spec.get("name") or "")
    type_text = str(spec.get("type") or "")
    text = f"{symbol} {name} {type_text}".lower()
    source_info = ASSET_CATEGORY_SOURCE_INFO.get(category, {})
    region = str(spec.get("region") or "")
    market = str(spec.get("market") or "")
    exchange = str(spec.get("exchange") or "")

    if not region:
        if spec.get("dataProvider") in {"taifex_tx_open_interest", "taifex_txo_open_interest"} or symbol.endswith(".TW") or symbol.endswith(".TWO"):
            region = "台灣"
        elif any(token in text for token in ("brent", "euro", "british pound", "eurex", "ice europe", "stoxx", "bund")):
            region = "歐洲"
        elif any(token in text for token in ("japanese", "yen", "australian", "asia", "sgx", "nikkei")):
            region = "亞洲"
        elif any(token in text for token in ("international", "global", "ex-us", "world")):
            region = "全球 / 其他"
        else:
            region = "美國"

    if not market:
        market = {
            "台灣": "台灣",
            "美國": "美國",
            "歐洲": "歐洲",
            "亞洲": "亞洲",
        }.get(region, "全球 / 其他")

    if not exchange:
        if spec.get("dataProvider") in {"taifex_tx_open_interest", "taifex_txo_open_interest"}:
            exchange = "TAIFEX"
        elif category == "options" and (symbol.startswith("^VI") or symbol in {"^SKEW", "^GVZ", "^OVX", "^VXD", "^VXN"}):
            exchange = "Cboe"
        elif category == "options":
            exchange = "OCC / Options exchanges"
        elif category == "bonds" and symbol.startswith("^"):
            exchange = "U.S. Treasury / Yahoo"
        elif category == "bonds":
            exchange = "NYSE Arca / Nasdaq ETF"
        elif category == "precious-metals" and symbol.endswith("=F"):
            exchange = "COMEX / NYMEX"
        elif category == "precious-metals":
            exchange = "NYSE Arca / LBMA reference"
        elif category == "futures":
            if symbol in {"ZB=F", "ZN=F", "ZF=F", "ZT=F", "ZQ=F", "UB=F", "ZC=F", "ZW=F", "ZS=F", "ZL=F", "ZM=F", "ZO=F"}:
                exchange = "CBOT"
            elif symbol in {"GC=F", "SI=F", "MGC=F", "SIL=F", "HG=F"}:
                exchange = "COMEX"
            elif symbol in {"CL=F", "MCL=F", "NG=F", "QG=F", "RB=F", "HO=F", "PL=F", "PA=F"}:
                exchange = "NYMEX"
            elif symbol in {"BZ=F", "KC=F", "SB=F", "CT=F", "CC=F", "OJ=F"}:
                exchange = "ICE"
            else:
                exchange = "CME"

    return {
        "region": region,
        "market": market,
        "exchange": exchange,
        "dataSource": str(spec.get("dataSource") or source_info.get("primary") or "Yahoo Finance"),
        "referenceSource": str(spec.get("referenceSource") or source_info.get("reference") or ""),
        "sourceUrl": str(spec.get("sourceUrl") or source_info.get("referenceUrl") or ""),
    }


def enrich_global_market_spec(spec: dict[str, Any], category: str) -> dict[str, Any]:
    metadata = infer_global_asset_metadata(spec, category)
    return {**spec, **{key: value for key, value in metadata.items() if value}}


def summarize_asset_regions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, dict[str, int]] = {}
    for item in items:
        region = str(item.get("region") or "全球 / 其他")
        bucket = counts.setdefault(region, {"total": 0, "usable": 0})
        bucket["total"] += 1
        if not item.get("error") and parse_float(str(item.get("close") or "")) is not None:
            bucket["usable"] += 1
    ordered = [region for region in ASSET_REGION_ORDER if region in counts]
    ordered.extend(sorted(region for region in counts if region not in ordered))
    return [{"region": region, **counts[region]} for region in ordered]


def classify_futures_market_scope(item: dict[str, Any]) -> str:
    region = str(item.get("region") or "")
    exchange = str(item.get("exchange") or item.get("dataSource") or "").upper()
    if region == "台灣" or "TAIFEX" in exchange:
        return "taiwan"
    if any(token in exchange for token in ("ICE", "SGX", "JPX", "HKEX", "EUREX")):
        return "international"
    if any(token in exchange for token in ("CME", "CBOT", "NYMEX", "COMEX")) or region == "美國":
        return "us"
    return "international"


def summarize_futures_market_scopes(catalog_items: list[dict[str, Any]], loaded_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {"taiwan": "台灣期貨", "us": "美國期貨", "international": "國際期貨"}
    counts = {
        key: {"key": key, "label": label, "total": 0, "loaded": 0, "usable": 0}
        for key, label in labels.items()
    }
    for item in catalog_items:
        counts[classify_futures_market_scope(item)]["total"] += 1
    for item in loaded_items:
        bucket = counts[classify_futures_market_scope(item)]
        bucket["loaded"] += 1
        if not item.get("error") and parse_float(str(item.get("close") or "")) is not None:
            bucket["usable"] += 1
    return [counts["taiwan"], counts["us"], counts["international"]]


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
PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE = "TAIFEX 選擇權鏈暫時無法載入，請稍後再試"
PUBLIC_TAIFEX_OPEN_INTEREST_ERROR_MESSAGE = "TAIFEX 未平倉資料暫時無法載入，請稍後再試"
PUBLIC_MARKET_ITEM_ERROR_MESSAGE = "行情資料暫時無法載入，請稍後再試"


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


def build_fallback_company_profile(
    stock: dict[str, Any],
    valuation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    valuation = valuation or {}
    market = str(stock.get("market") or "TWSE").upper()
    code = str(stock.get("code") or "").strip()
    name = str(stock.get("name") or "").strip()
    security_type = str(stock.get("securityType") or "").strip()
    market_label = str(stock.get("marketLabel") or ("上櫃" if market == "TPEX" else "上市")).strip()
    profile_link = (
        f"https://tw.stock.yahoo.com/quote/{quote(code, safe='')}.TWO/profile"
        if market == "TPEX"
        else f"https://tw.stock.yahoo.com/quote/{quote(code, safe='')}.TW/profile"
    )
    source_link = (
        build_tpex_openapi_url("mopsfin_t187ap03_O")
        if market == "TPEX"
        else f"{TWSE_OPENAPI_BASE}/opendata/t187ap03_L"
    )
    industry_label = " / ".join(
        item for item in [market_label, security_type if security_type and security_type != "STOCK" else "普通股"] if item
    )
    valuation_bits = [
        f"估值日 {valuation.get('date')}" if valuation.get("date") not in (None, "", "--") else "",
        f"本益比 {valuation.get('peRatio')}" if valuation.get("peRatio") not in (None, "", "--") else "",
        f"股價淨值比 {valuation.get('pbRatio')}" if valuation.get("pbRatio") not in (None, "", "--") else "",
        f"殖利率 {valuation.get('dividendYield')}%" if valuation.get("dividendYield") not in (None, "", "--") else "",
    ]
    return {
        "fullName": f"{code} {name}".strip() or name or code,
        "industry": industry_label or "--",
        "chairman": "--",
        "generalManager": "--",
        "capital": "--",
        "establishedDate": "--",
        "listingDate": "--",
        "address": "--",
        "telephone": "--",
        "website": profile_link,
        "sourceStatus": "fallback",
        "sourceNote": (
            "官方公司基本資料暫時未取得；目前保留市場、證券類型與估值摘要，"
            "並提供 Yahoo 個股與交易所 OpenAPI 來源供核對。"
        ),
        "sourceLink": source_link,
        "summary": "；".join(bit for bit in valuation_bits if bit) or f"{market_label} {security_type or '股票'}行情與估值資料已同步。",
    }


def build_stock_institutional_trade_record(row: list[Any], report_date: str) -> dict[str, Any]:
    foreign = parse_float(str(row[4])) if len(row) > 4 else None
    trust = parse_float(str(row[10])) if len(row) > 10 else None
    dealer = parse_float(str(row[11])) if len(row) > 11 else None
    total = parse_float(str(row[18])) if len(row) > 18 else None
    report_datetime = datetime.strptime(report_date, "%Y%m%d")
    return {
        "date": report_datetime.strftime("%Y-%m-%d"),
        "label": report_datetime.strftime("%m/%d"),
        "foreignValue": foreign,
        "trustValue": trust,
        "dealerValue": dealer,
        "totalValue": total,
        "foreignLotsValue": foreign / 1000 if foreign is not None else None,
        "trustLotsValue": trust / 1000 if trust is not None else None,
        "dealerLotsValue": dealer / 1000 if dealer is not None else None,
        "totalLotsValue": total / 1000 if total is not None else None,
    }


def build_stock_institutional_trade_summary(
    rows: list[dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "date": "",
        "label": f"{limit}日" if len(rows) >= limit else f"{len(rows)}日",
    }
    for key in ("foreign", "trust", "dealer", "total"):
        raw_key = f"{key}Value"
        lot_key = f"{key}LotsValue"
        values = [item.get(raw_key) for item in rows if isinstance(item.get(raw_key), (int, float))]
        total_value = sum(values) if values else None
        summary[raw_key] = total_value
        summary[lot_key] = total_value / 1000 if total_value is not None else None
    return summary


def build_latest_stock_institutional_trade(
    history: dict[str, Any],
) -> dict[str, Any]:
    rows = history.get("rows") if isinstance(history, dict) else []
    latest = rows[0] if isinstance(rows, list) and rows else {}
    if not latest:
        return {}
    foreign = latest.get("foreignValue")
    trust = latest.get("trustValue")
    dealer = latest.get("dealerValue")
    total = latest.get("totalValue")
    return {
        "date": latest.get("date") or "",
        "foreign": format_signed(foreign, 0),
        "trust": format_signed(trust, 0),
        "dealer": format_signed(dealer, 0),
        "total": format_signed(total, 0),
        "foreignValue": foreign,
        "trustValue": trust,
        "dealerValue": dealer,
        "totalValue": total,
    }


def build_institutional_trade_candidate_dates(
    history_rows: list[list[str]],
    date_str: str,
    limit: int,
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add_date(value: str) -> None:
        if re.fullmatch(r"\d{8}", value) and value not in seen:
            candidates.append(value)
            seen.add(value)

    add_date(taipei_now().strftime("%Y%m%d"))
    add_date(date_str)

    for row in reversed(history_rows):
        if not row:
            continue
        try:
            add_date(parse_roc_date(str(row[0])).strftime("%Y%m%d"))
        except (TypeError, ValueError):
            continue
        if len(candidates) >= limit:
            break

    return candidates



def build_institutional_history_from_yahoo(
    payload: dict[str, Any],
    limit: int = 1300,
) -> dict[str, Any]:
    raw_rows = payload.get("dailyRows") if isinstance(payload, dict) else []
    rows: list[dict[str, Any]] = []
    for row in (raw_rows or [])[:limit]:
        foreign_lots = parse_float(str(row.get("foreignLotsValue") or ""))
        trust_lots = parse_float(str(row.get("trustLotsValue") or ""))
        dealer_lots = parse_float(str(row.get("dealerLotsValue") or ""))
        total_lots = parse_float(str(row.get("totalLotsValue") or ""))
        rows.append({
            "date": row.get("date") or "",
            "label": row.get("label") or str(row.get("date") or "")[5:],
            "foreignLotsValue": foreign_lots,
            "trustLotsValue": trust_lots,
            "dealerLotsValue": dealer_lots,
            "totalLotsValue": total_lots,
            "foreignValue": foreign_lots * 1000 if foreign_lots is not None else None,
            "trustValue": trust_lots * 1000 if trust_lots is not None else None,
            "dealerValue": dealer_lots * 1000 if dealer_lots is not None else None,
            "totalValue": total_lots * 1000 if total_lots is not None else None,
            "foreignChipRatio": row.get("foreignChipRatio"),
            "changePct": row.get("changePct"),
            "volume": row.get("volume"),
        })
    periods = [5, 10, 20, 30]
    summaries = {
        str(period): build_stock_institutional_trade_summary(rows[:period], period)
        for period in periods
        if rows
    }
    return {
        "available": bool(rows),
        "unit": "lots",
        "limit": limit,
        "periods": periods,
        "defaultPeriod": 5,
        "rows": rows,
        "summaries": summaries,
        "summary": summaries.get("5", {}),
        "source": payload.get("source") or "Yahoo Taiwan Stock",
        "sourceLink": payload.get("sourceLink") or "",
        "sourceNote": "Yahoo real institutional trading rows. Long TPEx ranges are limited by Yahoo availability.",
    }


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


def build_institution_summary(institutions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = [
        ("foreign", "外資", lambda name: name.startswith("外資")),
        ("dealer", "自營商", lambda name: name.startswith("自營商")),
        ("trust", "投信", lambda name: name == "投信"),
    ]
    summaries: list[dict[str, Any]] = []
    for key, label, matcher in groups:
        matched = [item for item in institutions if matcher(str(item.get("name", "")))]
        if not matched:
            continue
        buy_value = sum(item.get("buyValue") or 0 for item in matched)
        sell_value = sum(item.get("sellValue") or 0 for item in matched)
        diff_value = sum(item.get("diffValue") or 0 for item in matched)
        summaries.append(
            {
                "key": key,
                "name": label,
                "buy": format_whole_number(buy_value),
                "sell": format_whole_number(sell_value),
                "diff": format_signed(diff_value, 0),
                "buyValue": buy_value,
                "sellValue": sell_value,
                "diffValue": diff_value,
                "tone": detect_tone(diff_value),
                "sources": [item["name"] for item in matched],
            }
        )
    return summaries


def build_institution_trend(
    latest_payload: dict[str, Any] | None = None,
    latest_date: str | None = None,
    lookback_days: int = 12,
    max_rows: int = 5,
) -> dict[str, Any]:
    """Summarize recent institutional flow continuity for market AI notes."""
    rows: list[dict[str, Any]] = []
    seen_dates: set[str] = set()

    def append_payload(payload: dict[str, Any] | None, date_str: str | None) -> None:
        if not payload or not date_str or date_str in seen_dates or not dataset_has_rows(payload):
            return
        institutions = parse_institutions(payload)
        summary = build_institution_summary(institutions)
        foreign = next((item for item in summary if item.get("key") == "foreign"), None)
        dealer = next((item for item in summary if item.get("key") == "dealer"), None)
        trust = next((item for item in summary if item.get("key") == "trust"), None)
        total = next((item for item in institutions if item.get("name") == "合計"), None)
        rows.append(
            {
                "date": datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
                "foreign": foreign.get("diff") if foreign else "--",
                "foreignValue": foreign.get("diffValue") if foreign else None,
                "dealer": dealer.get("diff") if dealer else "--",
                "dealerValue": dealer.get("diffValue") if dealer else None,
                "trust": trust.get("diff") if trust else "--",
                "trustValue": trust.get("diffValue") if trust else None,
                "total": total.get("diff") if total else "--",
                "totalValue": total.get("diffValue") if total else None,
            }
        )
        seen_dates.add(date_str)

    append_payload(latest_payload, latest_date)
    try:
        base_date = datetime.strptime(latest_date or "", "%Y%m%d").date()
    except ValueError:
        base_date = taipei_now().date()

    for offset in range(1, lookback_days + 1):
        if len(rows) >= max_rows:
            break
        date_str = (base_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            payload = fetch_json(build_institutions_url(date_str), timeout=8)
        except Exception:  # noqa: BLE001
            continue
        append_payload(payload, date_str)

    def streak_for(key: str) -> dict[str, Any]:
        valid = [row for row in rows if isinstance(row.get(f"{key}Value"), (int, float))]
        if not valid:
            return {"direction": "flat", "count": 0, "label": "資料不足", "summary": "法人連續性資料仍在同步。"}
        first_value = valid[0].get(f"{key}Value") or 0
        if first_value > 0:
            direction = "buy"
        elif first_value < 0:
            direction = "sell"
        else:
            direction = "flat"
        count = 0
        for row in valid:
            value = row.get(f"{key}Value") or 0
            if direction == "buy" and value > 0:
                count += 1
            elif direction == "sell" and value < 0:
                count += 1
            elif direction == "flat" and value == 0:
                count += 1
            else:
                break
        direction_text = "買超" if direction == "buy" else "賣超" if direction == "sell" else "持平"
        label = f"連 {count} {direction_text}" if count > 1 else f"今日{direction_text}"
        summary = f"{valid[0].get('date', '')} {direction_text} {format_whole_number(abs(first_value))} 元，{label}。"
        return {"direction": direction, "count": count, "label": label, "summary": summary}

    return {
        "rows": rows,
        "foreign": streak_for("foreign"),
        "dealer": streak_for("dealer"),
        "trust": streak_for("trust"),
        "total": streak_for("total"),
    }


def is_valid_history_row(row: list[str]) -> bool:
    if len(row) < 7:
        return False
    return is_valid_ohlc_values(
        parse_float(str(row[3])),
        parse_float(str(row[4])),
        parse_float(str(row[5])),
        parse_float(str(row[6])),
    )


def sanitize_history_rows(rows: list[list[str]]) -> list[list[str]]:
    return [row for row in rows if is_valid_history_row(row)]


def build_fallback_history_rows(stock: dict[str, Any], date_str: str) -> list[list[str]]:
    close_value = parse_float(stock.get("close"))
    change_value = parse_float(stock.get("change")) or 0.0
    if close_value is None:
        return []

    snapshot_date = datetime.strptime(date_str, "%Y%m%d")
    previous_date = snapshot_date - timedelta(days=1)
    while previous_date.weekday() >= 5:
        previous_date -= timedelta(days=1)
    previous_close = close_value - change_value
    open_value = stock.get("open") if parse_float(stock.get("open")) is not None else f"{previous_close:,.2f}"
    high_value = stock.get("high") if parse_float(stock.get("high")) is not None else stock.get("close")
    low_value = stock.get("low") if parse_float(stock.get("low")) is not None else stock.get("close")
    volume = stock.get("volume") or "0"

    return [
        [format_roc_date(previous_date), "0", "", f"{previous_close:,.2f}", f"{previous_close:,.2f}", f"{previous_close:,.2f}", f"{previous_close:,.2f}", "0.00"],
        [format_roc_date(snapshot_date), volume, "", open_value, high_value, low_value, stock["close"], stock["change"]],
    ]




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


def format_chip_lots(value: float | None, digits: int = 0, signed: bool = False) -> str:
    if value is None:
        return "--"
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value:,.{digits}f} 張"


def format_chip_percent(value: float | None, digits: int = 2, signed: bool = False) -> str:
    if value is None:
        return "--"
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value:.{digits}f}%"


def build_main_force_proxy(
    stock: dict[str, Any],
    avg_volume_5: float | None,
    pct_value: float | None,
    broker_trading: dict[str, Any] | None = None,
) -> dict[str, Any]:
    broker_trading = broker_trading or {}
    broker_summary = broker_trading.get("summary") if isinstance(broker_trading, dict) else {}
    broker_summary = broker_summary if isinstance(broker_summary, dict) else {}
    broker_net_lots = parse_float(str(broker_summary.get("netLots") or ""))
    has_broker_data = bool(
        broker_trading
        and (
            broker_net_lots is not None
            or broker_trading.get("buyBrokers")
            or broker_trading.get("sellBrokers")
        )
    )
    label = (
        "偏買進" if broker_net_lots is not None and broker_net_lots > 0
        else "偏賣出" if broker_net_lots is not None and broker_net_lots < 0
        else "換手觀察" if has_broker_data
        else "未取得"
    )
    tone = detect_tone(broker_net_lots) if has_broker_data else "flat"

    return {
        "key": "mainForce",
        "title": "主力進出",
        "label": label,
        "tone": tone,
        "metrics": [
            {"label": "主力買賣超", "value": format_chip_lots(broker_net_lots, 0, True) if broker_net_lots is not None else label},
            {"label": "主力買超", "value": format_chip_lots(parse_float(str(broker_summary.get("buyLots") or "")), 0)},
            {"label": "主力賣超", "value": format_chip_lots(parse_float(str(broker_summary.get("sellLots") or "")), 0)},
            {"label": "佔成交量", "value": str(broker_summary.get("volumeRatio") or "--")},
        ],
        "items": [
            (
                f"Yahoo 主力進出資料時間 {broker_trading.get('date', '--')}，買超券商 {len(broker_trading.get('buyBrokers') or [])} 家、賣超券商 {len(broker_trading.get('sellBrokers') or [])} 家。"
                if has_broker_data else "主力進出資料未取得；不使用量價代理替代。"
            ),
            "買超/賣超券商明細以 Yahoo 主力進出頁解析結果呈現。" if has_broker_data else "請稍後重新同步資料來源。",
        ],
        "source": broker_trading.get("source") or "Yahoo 股市主力進出",
        "sourceLink": broker_trading.get("sourceLink") or "",
        "sourceNote": broker_trading.get("sourceNote") or "主力進出未取得時不使用代理推估。",
    }


def build_chip_summary(
    stock: dict[str, Any],
    avg_volume_5: float | None,
    pct_value: float | None,
    institutional_trades: dict[str, Any] | None,
    institutional_trade_history: dict[str, Any] | None,
    shareholder_distribution: dict[str, Any] | None,
    margin_trading: dict[str, Any] | None,
    broker_trading: dict[str, Any] | None = None,
) -> dict[str, Any]:
    institutional_trades = institutional_trades or {}
    institutional_trade_history = institutional_trade_history or {}
    shareholder_distribution = shareholder_distribution or {}
    margin_trading = margin_trading or {}
    is_etf = is_etf_stock(stock)

    total_institutional = parse_float(str(institutional_trades.get("totalValue") or ""))
    foreign_value = parse_float(str(institutional_trades.get("foreignValue") or ""))
    trust_value = parse_float(str(institutional_trades.get("trustValue") or ""))
    dealer_value = parse_float(str(institutional_trades.get("dealerValue") or ""))
    institutional_label = (
        "買超" if total_institutional is not None and total_institutional > 0
        else "賣超" if total_institutional is not None and total_institutional < 0
        else "待同步"
    )
    institutional_card = {
        "key": "institutional",
        "title": "法人買賣",
        "label": institutional_label,
        "tone": detect_tone(total_institutional),
        "metrics": [
            {"label": "三大法人", "value": format_chip_lots(total_institutional / 1000 if total_institutional is not None else None, 0, True)},
            {"label": "外資", "value": format_chip_lots(foreign_value / 1000 if foreign_value is not None else None, 0, True)},
            {"label": "投信", "value": format_chip_lots(trust_value / 1000 if trust_value is not None else None, 0, True)},
            {"label": "自營商", "value": format_chip_lots(dealer_value / 1000 if dealer_value is not None else None, 0, True)},
        ],
        "items": [
            (
                f"{institutional_trades.get('date', '--')} 三大法人合計 {format_chip_lots(total_institutional / 1000 if total_institutional is not None else None, 0, True)}。"
                if institutional_trades else str(institutional_trade_history.get("sourceNote") or "法人買賣超明細目前未取得。")
            ),
            "ETF 法人買賣同樣以交易所法人買賣超口徑觀察資金方向。" if is_etf else "個股法人買賣可搭配投信連續性與外資方向觀察。",
        ],
        "source": institutional_trade_history.get("source") or "TWSE T86",
        "sourceLink": institutional_trade_history.get("sourceLink") or "",
        "sourceNote": institutional_trade_history.get("sourceNote") or "法人買賣超明細同步自交易所公開資料。",
    }

    main_force_card = build_main_force_proxy(stock, avg_volume_5, pct_value, broker_trading)

    financing_change_value = parse_float(str(margin_trading.get("financingChange") or ""))
    short_change_value = parse_float(str(margin_trading.get("shortChange") or ""))
    financing_balance = parse_float(str(margin_trading.get("financingBalance") or ""))
    short_balance = parse_float(str(margin_trading.get("shortBalance") or ""))
    ratio = parse_float(str(margin_trading.get("shortFinancingRatio") or ""))
    margin_label = (
        "券增資減" if short_change_value is not None and short_change_value > 0 and (financing_change_value or 0) <= 0
        else "資增券減" if financing_change_value is not None and financing_change_value > 0 and (short_change_value or 0) <= 0
        else "同步增加" if (financing_change_value or 0) > 0 and (short_change_value or 0) > 0
        else "待同步"
    )
    margin_card = {
        "key": "margin",
        "title": "資券變化",
        "label": margin_label,
        "tone": "down" if margin_label == "券增資減" else "up" if margin_label == "資增券減" else "flat",
        "metrics": [
            {"label": "融資增減", "value": format_chip_lots(financing_change_value, 0, True)},
            {"label": "融券增減", "value": format_chip_lots(short_change_value, 0, True)},
            {"label": "融資餘額", "value": format_chip_lots(financing_balance, 0)},
            {"label": "券資比", "value": format_chip_percent(ratio, 2)},
        ],
        "items": [
            (
                f"融資餘額 {format_chip_lots(financing_balance, 0)}，融券餘額 {format_chip_lots(short_balance, 0)}。"
                if margin_trading else "資券資料目前未取得。"
            ),
            (
                f"資券互抵 {format_chip_lots(parse_float(str(margin_trading.get('offsetting') or '')), 0)}。"
                if margin_trading else "上市/上櫃資券資料以交易所公告為準。"
            ),
        ],
        "source": "交易所資券",
        "sourceLink": margin_trading.get("sourceLink") or "",
        "sourceNote": margin_trading.get("sourceNote") or "融資融券資料以交易所公告為準。",
    }

    large_ratio = parse_float(str(shareholder_distribution.get("largeHolderRatio") or ""))
    retail_ratio = parse_float(str(shareholder_distribution.get("retailHolderRatio") or ""))
    other_ratio = parse_float(str(shareholder_distribution.get("otherHolderRatio") or ""))
    holder_available = shareholder_distribution.get("available", True) is not False and large_ratio is not None
    holder_label = (
        "集中" if large_ratio is not None and large_ratio >= 60
        else "分散" if large_ratio is not None and large_ratio < 35
        else "觀察" if holder_available
        else "待同步"
    )
    holder_card = {
        "key": "largeHolder",
        "title": "大戶籌碼",
        "label": holder_label,
        "tone": "up" if holder_label == "集中" else "down" if holder_label == "分散" else "flat",
        "metrics": [
            {"label": "大戶", "value": format_chip_percent(large_ratio, 2)},
            {"label": "散戶", "value": format_chip_percent(retail_ratio, 2)},
            {"label": "其他", "value": format_chip_percent(other_ratio, 2)},
            {"label": "日期", "value": str(shareholder_distribution.get("date") or "--")},
        ],
        "items": [
            (
                f"大戶門檻 {shareholder_distribution.get('largeHolderThreshold', '400 張以上')}，持股占比 {format_chip_percent(large_ratio, 2)}。"
                if holder_available else str(shareholder_distribution.get("sourceNote") or "大戶籌碼目前未取得。")
            ),
            "ETF 集保分布可觀察受益人籌碼集中度；個股則可輔助判斷大戶與散戶結構。",
        ],
        "source": shareholder_distribution.get("source") or "臺灣集中保管結算所",
        "sourceLink": shareholder_distribution.get("sourceLink") or TDCC_HOLDING_DISTRIBUTION_URL,
        "sourceNote": shareholder_distribution.get("sourceNote") or "集保持股分級資料同步自臺灣集中保管結算所。",
    }

    return {
        "title": "籌碼四象限",
        "summary": "整合法人買賣、主力進出、資券變化與大戶籌碼；官方資料未提供處以代理或待同步標示。",
        "cards": [institutional_card, main_force_card, margin_card, holder_card],
    }


def build_analysis_sections(
    stock: dict[str, Any],
    closes: list[float],
    volumes: list[float],
    highs: list[float],
    lows: list[float],
    ma5: float | None,
    avg_volume_5: float | None,
    site_data: dict[str, Any] | None,
    valuation: dict[str, Any] | None = None,
    institutional_trades: dict[str, Any] | None = None,
    shareholder_distribution: dict[str, Any] | None = None,
    margin_trading: dict[str, Any] | None = None,
    etf_components: dict[str, Any] | None = None,
    etf_dividend_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    valuation = valuation or {}
    institutional_trades = institutional_trades or {}
    shareholder_distribution = shareholder_distribution or {}
    margin_trading = margin_trading or {}
    close_value = parse_float(stock["close"])
    open_value = parse_float(stock["open"])
    high_value = parse_float(stock["high"])
    low_value = parse_float(stock["low"])
    turnover_value = parse_float(stock["turnover"])
    trades_value = parse_float(stock["trades"])
    bid_volume = parse_float(stock["bidVolume"])
    ask_volume = parse_float(stock["askVolume"])
    latest_volume = parse_float(stock["volume"])
    pct_value = parse_float(stock["pct"].replace("%", "")) if stock.get("pct") not in (None, "--") else None
    holder_large_ratio = parse_float(str(shareholder_distribution.get("largeHolderRatio", ""))) if shareholder_distribution else None
    holder_retail_ratio = parse_float(str(shareholder_distribution.get("retailHolderRatio", ""))) if shareholder_distribution else None
    holder_available = (
        bool(shareholder_distribution)
        and shareholder_distribution.get("available", True) is not False
        and holder_large_ratio is not None
        and holder_retail_ratio is not None
    )

    range_position = None
    if close_value is not None and highs and lows and max(highs) != min(lows):
        range_position = (close_value - min(lows)) / (max(highs) - min(lows))

    volume_ratio = None
    if latest_volume is not None and avg_volume_5 not in (None, 0):
        volume_ratio = latest_volume / avg_volume_5

    market_overview = site_data["marketOverview"][0] if site_data and site_data.get("marketOverview") else None
    market_pct = parse_float(str(market_overview.get("pct", "")).replace("%", "")) if market_overview else None
    relative_pct = pct_value - market_pct if pct_value is not None and market_pct is not None else None
    market_label = stock.get("marketLabel") or (
        "上櫃" if str(stock.get("market", "")).upper() == "TPEX" else "上市"
    )
    is_etf = is_etf_stock(stock)

    technical_items = [
        f"收盤價 {stock['close']}，5 日均價 {f'{ma5:,.2f}' if ma5 is not None else '--'}。",
        "收盤站上 5 日均價，短線結構偏強。" if ma5 is not None and close_value is not None and close_value >= ma5 else "收盤位於 5 日均價下方，短線仍需觀察支撐。",
        f"月內區間 {min(lows):,.2f} 至 {max(highs):,.2f}，目前位於區間 {range_position * 100:,.1f}% 位置。" if range_position is not None else "月內高低點資料不足。",
        f"當日震幅 {((high_value - low_value) / open_value) * 100:,.2f}%。" if None not in (high_value, low_value, open_value) and open_value != 0 else "當日震幅資料不足。",
    ]

    if is_etf:
        etf_components = etf_components or {}
        etf_dividend_info = etf_dividend_info or {}
        holdings = etf_components.get("holdings") if isinstance(etf_components, dict) else []
        holdings = holdings if isinstance(holdings, list) else []
        top_holding = holdings[0] if holdings else {}
        top_weight = parse_float(str(top_holding.get("weight", ""))) if isinstance(top_holding, dict) else None
        top5_weight = sum(
            parse_float(str(item.get("weight", ""))) or 0
            for item in holdings[:5]
            if isinstance(item, dict)
        ) if holdings else None
        latest_dividend = (etf_dividend_info.get("latest") or {}) if isinstance(etf_dividend_info, dict) else {}
        dividend_totals = (etf_dividend_info.get("totals") or {}) if isinstance(etf_dividend_info, dict) else {}
        recent_dividends = etf_dividend_info.get("recent") if isinstance(etf_dividend_info, dict) else []
        recent_dividends = recent_dividends if isinstance(recent_dividends, list) else []
        latest_cash_dividend = str(latest_dividend.get("cashDividend", "")).strip()
        has_latest_dividend = latest_cash_dividend not in {"", "--", "-", "N/A", "NA"}
        total_dividends_text = str(dividend_totals.get("totalDividends", "")).strip()
        continuous_years_text = str(dividend_totals.get("continuousYears", "")).strip()
        has_dividend_totals = (
            total_dividends_text not in {"", "--", "-", "N/A", "NA", "0"}
            or continuous_years_text not in {"", "--", "-", "N/A", "NA", "0"}
        )
        bid_value = parse_float(str(stock.get("bid", "")))
        ask_value = parse_float(str(stock.get("ask", "")))
        spread_value = (ask_value - bid_value) if bid_value is not None and ask_value is not None and ask_value >= bid_value else None
        spread_pct = (spread_value / close_value * 100) if spread_value is not None and close_value not in (None, 0) else None
        volatility_pct = parse_float(str((stock.get("technicalAnalysis") or {}).get("volatilityPct", "")))
        etf_type_note = (
            "槓桿/反向 ETF，偏交易工具，籌碼與風險需以量能、折溢價與波動控管為主。"
            if any(keyword in str(stock.get("name", "")) for keyword in ("正2", "反1", "反向", "槓桿"))
            else "ETF 以追蹤標的、成分配置、配息與流動性作為核心分析，不適用一般個股本益比與股價淨值比判讀。"
        )
        fundamental_items = [
            etf_type_note,
            (
                f"ETF 成分股比例：最大配置為 {top_holding.get('name', '--')} "
                f"{top_weight:.1f}%，前 5 大配置合計約 {top5_weight:.1f}%。"
                if holdings and top_weight is not None and top5_weight is not None
                else "ETF 成分股比例尚未取得完整明細，請以投信每日公告為準。"
            ),
            (
                f"近次配息 {latest_cash_dividend} 元，除息日 {latest_dividend.get('exDate', '--')}，"
                f"平均殖利率 {dividend_totals.get('averageYield', '--')}%。"
                if has_latest_dividend
                else "ETF 股利資訊尚未取得近次配息，收益型 ETF 需再核對除息日、發放日與填息天數。"
            ),
            (
                f"累計股利 {dividend_totals.get('totalDividends', '--')} 元，連續配息年數 {dividend_totals.get('continuousYears', '--')} 年。"
                if has_dividend_totals else "累計股利與連續配息年數目前未取得，或此 ETF 不是以配息為主要目的。"
            ),
            f"成交金額 {stock.get('turnover', '--')}，成交量 {stock.get('volume', '--')}，用於判斷 ETF 流動性與交易滑價風險。",
            "淨值折溢價、費用率與追蹤誤差目前尚未串接；若要做長期配置，仍需以投信公告與基金公開說明書補強。",
        ]
        chips_items = [
            f"ETF 籌碼面以成交量、成交值、買賣價差、折溢價與申贖變化作為代理，不直接套用一般個股法人/集保持股口徑。",
            f"成交量 {stock.get('volume', '--')}，成交筆數 {stock.get('trades', '--')}，成交金額 {stock.get('turnover', '--')}。",
            f"最新成交量約為 5 日均量的 {volume_ratio:,.2f} 倍。" if volume_ratio is not None else "5 日均量資料不足，量能變化需持續觀察。",
            (
                f"委買 {stock.get('bidVolume', '--')}、委賣 {stock.get('askVolume', '--')}；"
                f"買賣價差約 {spread_value:.2f} 元（{spread_pct:.2f}%）。"
                if spread_value is not None and spread_pct is not None else
                f"委買 {stock.get('bidVolume', '--')}、委賣 {stock.get('askVolume', '--')}；買賣價差資料不足。"
            ),
            (
                f"波動度 {volatility_pct:.2f}%，當日震幅 {((high_value - low_value) / open_value) * 100:,.2f}%。"
                if volatility_pct is not None and None not in (high_value, low_value, open_value) and open_value != 0 else
                "波動度或當日震幅資料不足。"
            ),
            (
                f"ETF 股利資訊已有 {len(recent_dividends)} 筆近次配息紀錄，可搭配填息天數觀察收益品質。"
                if recent_dividends else "ETF 配息紀錄目前未取得，收益型 ETF 不宜只用名稱判斷。"
            ),
        ]
        news_items = [
            f"{market_label} ETF，當日漲跌幅 {stock.get('pct', '--')}。",
            (
                f"加權指數漲跌幅 {market_overview['pct']}，ETF 相對大盤強弱 {relative_pct:+.2f} 個百分點。"
                if market_overview and relative_pct is not None else "大盤相對強弱資料目前未取得。"
            ),
            (
                "ETF 表現優於大盤，需確認是否由成分集中度或主題曝險推動。" if relative_pct is not None and relative_pct > 0 else
                "ETF 表現弱於大盤，需檢查成分配置、折溢價與量能是否同步轉弱。" if relative_pct is not None and relative_pct < 0 else
                "ETF 表現與大盤接近，可回到追蹤標的與費用結構比較。"
            ),
        ]
        return {
            "technical": {
                "title": "技術趨勢",
                "summary": technical_items[1],
                "items": technical_items,
            },
            "chips": {
                "title": "ETF 籌碼與流動性",
                "summary": chips_items[1],
                "items": chips_items,
                "skipSupplementalPanels": True,
            },
            "fundamental": {
                "title": "ETF 基本面",
                "summary": fundamental_items[1],
                "items": fundamental_items,
            },
            "news": {
                "title": "市場脈絡",
                "summary": news_items[1],
                "items": news_items,
            },
        }

    chips_items = [
        (
            f"集保持股分布（{shareholder_distribution['date']}）：大戶 "
            f"{holder_large_ratio:.2f}%、散戶 "
            f"{holder_retail_ratio:.2f}%。"
            if holder_available else str(shareholder_distribution.get("sourceNote") or "集保持股分布目前未取得。")
        ),
        f"成交量 {stock['volume']}，成交筆數 {stock['trades']}。",
        f"最新成交量約為 5 日均量的 {volume_ratio:,.2f} 倍。" if volume_ratio is not None else "5 日均量資料不足。",
        f"委買 {stock['bidVolume']}、委賣 {stock['askVolume']}。" if bid_volume is not None and ask_volume is not None else "委買委賣資料不足。",
        (
            f"個股法人（{institutional_trades['date']}）：外資 {institutional_trades['foreign']} 股、"
            f"投信 {institutional_trades['trust']} 股、自營商 {institutional_trades['dealer']} 股。"
            if institutional_trades else f"{market_label}個股法人明細目前未取得。"
        ),
        f"三大法人合計 {institutional_trades['total']} 股。" if institutional_trades else "法人合計資料目前未取得。",
        (
            f"融資餘額 {margin_trading['financingBalance']:,.0f} 張，"
            f"較前日 {margin_trading['financingChange']:+,.0f} 張；"
            f"融券餘額 {margin_trading['shortBalance']:,.0f} 張，"
            f"較前日 {margin_trading['shortChange']:+,.0f} 張。"
            if margin_trading
            and margin_trading.get("financingBalance") is not None
            and margin_trading.get("financingChange") is not None
            and margin_trading.get("shortBalance") is not None
            and margin_trading.get("shortChange") is not None
            else "個股融資融券資料目前未取得。"
        ),
    ]

    fundamental_items = [
        f"本益比 {valuation.get('peRatio', '--')}。",
        f"殖利率 {valuation.get('dividendYield', '--')}%。",
        f"股價淨值比 {valuation.get('pbRatio', '--')}。",
        (
            f"每股股利 {valuation['dividendPerShare']} 元。"
            if valuation.get("dividendPerShare") not in (None, "", "--") else
            f"成交金額 {stock['turnover']}。" if turnover_value else "成交金額資料不足。"
        ),
        f"估值資料日期 {valuation.get('date', '--')}。",
    ]

    news_items = [
        f"{market_label}股票，個股漲跌幅 {stock['pct']}。",
        (
            f"加權指數漲跌幅 {market_overview['pct']}，個股相對大盤強弱 {relative_pct:+.2f} 個百分點。"
            if market_overview and relative_pct is not None else "大盤相對強弱資料目前未取得。"
        ),
        (
            "個股表現優於大盤。" if relative_pct is not None and relative_pct > 0 else
            "個股表現弱於大盤。" if relative_pct is not None and relative_pct < 0 else
            "個股表現與大盤接近。"
        ),
    ]

    return {
        "technical": {
            "title": "技術趨勢",
            "summary": technical_items[1],
            "items": technical_items,
        },
        "chips": {
            "title": "籌碼觀察",
            "summary": (
                f"大戶持股 {shareholder_distribution['largeHolderRatio']:.2f}%、"
                f"散戶持股 {shareholder_distribution['retailHolderRatio']:.2f}%。"
                if holder_available else chips_items[4]
            ),
            "items": chips_items,
            "holderDistribution": shareholder_distribution,
            "marginTrading": margin_trading,
        },
        "fundamental": {
            "title": "基本面觀察",
            "summary": (
                f"本益比 {valuation.get('peRatio', '--')}、殖利率 {valuation.get('dividendYield', '--')}%。"
            ),
            "items": fundamental_items,
        },
        "news": {
            "title": "市場脈絡",
            "summary": news_items[1],
            "items": news_items,
        },
    }


ETF_COMPONENT_PRESETS: dict[str, list[dict[str, Any]]] = {
    "0050": [
        {"name": "台積電", "code": "2330", "weight": 55.0},
        {"name": "鴻海", "code": "2317", "weight": 5.0},
        {"name": "聯發科", "code": "2454", "weight": 4.0},
        {"name": "台達電", "code": "2308", "weight": 3.8},
        {"name": "富邦金", "code": "2881", "weight": 2.5},
        {"name": "中信金", "code": "2891", "weight": 2.4},
        {"name": "廣達", "code": "2382", "weight": 2.3},
        {"name": "聯電", "code": "2303", "weight": 1.8},
        {"name": "國泰金", "code": "2882", "weight": 1.8},
        {"name": "日月光投控", "code": "3711", "weight": 1.7},
        {"name": "其他成分股", "code": "--", "weight": 19.7},
    ],
    "006208": [
        {"name": "台積電", "code": "2330", "weight": 55.0},
        {"name": "鴻海", "code": "2317", "weight": 5.0},
        {"name": "聯發科", "code": "2454", "weight": 4.0},
        {"name": "台達電", "code": "2308", "weight": 3.8},
        {"name": "富邦金", "code": "2881", "weight": 2.5},
        {"name": "中信金", "code": "2891", "weight": 2.4},
        {"name": "廣達", "code": "2382", "weight": 2.3},
        {"name": "聯電", "code": "2303", "weight": 1.8},
        {"name": "國泰金", "code": "2882", "weight": 1.8},
        {"name": "日月光投控", "code": "3711", "weight": 1.7},
        {"name": "其他成分股", "code": "--", "weight": 19.7},
    ],
}


def build_etf_components(stock: dict[str, Any]) -> dict[str, Any]:
    code = str(stock.get("code") or "")
    name = str(stock.get("name") or "")
    preset = ETF_COMPONENT_PRESETS.get(code)
    if preset:
        return {
            "title": "ETF 成分股比例",
            "summary": "以追蹤指數主要權重股呈現 ETF 持股結構；實際比例仍以投信每日公告為準。",
            "holdings": preset,
            "sourceNote": "台灣 50 相關 ETF 參考公開成分股與權重結構整理。",
            "sourceLink": "https://www.twse.com.tw/zh/products/securities/etf/products/domestic.html",
        }

    if any(keyword in name for keyword in ("高股息", "收益", "股息")):
        holdings = [
            {"name": "金融與高股息成分", "code": "--", "weight": 35.0},
            {"name": "電子權值與成熟科技", "code": "--", "weight": 30.0},
            {"name": "傳產與防禦型成分", "code": "--", "weight": 20.0},
            {"name": "現金與其他調整項", "code": "--", "weight": 15.0},
        ]
    elif any(keyword in name for keyword in ("半導體", "科技", "電子", "AI")):
        holdings = [
            {"name": "半導體與 IC 設計", "code": "--", "weight": 45.0},
            {"name": "電子零組件與伺服器", "code": "--", "weight": 28.0},
            {"name": "通訊與其他科技", "code": "--", "weight": 17.0},
            {"name": "現金與其他調整項", "code": "--", "weight": 10.0},
        ]
    elif any(keyword in name for keyword in ("ESG", "永續", "低碳")):
        holdings = [
            {"name": "大型電子 ESG 成分", "code": "--", "weight": 40.0},
            {"name": "金融與治理評級成分", "code": "--", "weight": 25.0},
            {"name": "低碳轉型與傳產成分", "code": "--", "weight": 20.0},
            {"name": "現金與其他調整項", "code": "--", "weight": 15.0},
        ]
    else:
        holdings = [
            {"name": "主要追蹤指數成分", "code": "--", "weight": 50.0},
            {"name": "次要成分與產業配置", "code": "--", "weight": 30.0},
            {"name": "現金、期貨或其他調整項", "code": "--", "weight": 20.0},
        ]
    return {
        "title": "ETF 成分股比例",
        "summary": "此 ETF 未取得即時完整持股明細，先以名稱與追蹤主題整理配置比例參考。",
        "holdings": holdings,
        "sourceNote": "請以發行投信每日公告之 ETF 投資組合明細為最終依據。",
        "sourceLink": "https://www.twse.com.tw/zh/products/securities/etf/products/domestic.html",
    }


def build_stock_detail(
    stock: dict[str, Any],
    date_str: str,
    site_data: dict[str, Any] | None = None,
    months_back: int = STOCK_HISTORY_RECENT_MONTHS,
    quick: bool = False,
    include_shareholders: bool = True,
    include_institutional_history: bool = True,
) -> dict[str, Any]:
    used_fallback_history = False
    history_rows_removed = 0
    market = stock.get("market") or "TWSE"
    if quick:
        yahoo_diagnostics: dict[str, int] = {}
        try:
            rows = fetch_yahoo_history_rows(
                stock["code"],
                STOCK_HISTORY_RECENT_MONTHS,
                market=market,
                diagnostics=yahoo_diagnostics,
            )
        except Exception:  # noqa: BLE001
            rows = []
        history_rows_removed += yahoo_diagnostics.get("invalid_rows", 0)
        raw_row_count = len(rows)
        rows = sanitize_history_rows(rows)
        history_rows_removed += raw_row_count - len(rows)
        if not rows:
            rows = build_fallback_history_rows(stock, date_str)
            used_fallback_history = bool(rows)
    else:
        yahoo_diagnostics: dict[str, int] = {}
        try:
            rows = fetch_yahoo_history_rows(
                stock["code"],
                months_back,
                market=market,
                diagnostics=yahoo_diagnostics,
            )
        except Exception:  # noqa: BLE001
            rows = []
        history_rows_removed += yahoo_diagnostics.get("invalid_rows", 0)
        raw_row_count = len(rows)
        rows = sanitize_history_rows(rows)
        history_rows_removed += raw_row_count - len(rows)
        if not rows and market != "TPEx":
            try:
                rows = fetch_stock_history_rows(stock["code"], date_str, months_back=months_back)
            except Exception:  # noqa: BLE001
                rows = []
            raw_row_count = len(rows)
            rows = sanitize_history_rows(rows)
            history_rows_removed += raw_row_count - len(rows)
        if not rows:
            rows = build_fallback_history_rows(stock, date_str)
            used_fallback_history = bool(rows)
    raw_row_count = len(rows)
    rows = sanitize_history_rows(rows)
    history_rows_removed += raw_row_count - len(rows)

    is_etf = is_etf_stock(stock)
    futures: dict[str, Any] = {}
    supplemental_timeout = 8 if quick else 10 if is_etf else 12
    executor = ThreadPoolExecutor(max_workers=2 if quick else 4 if is_etf else 7)
    try:
        if not quick:
            futures["companyNews"] = executor.submit(fetch_stock_news, stock, 6)
            futures["marginTrading"] = executor.submit(fetch_stock_margin_trading, stock)
            futures["brokerTrading"] = executor.submit(fetch_yahoo_broker_trading, stock, 15)
            futures["majorHolderData"] = executor.submit(fetch_yahoo_major_holders, stock, 260)
            futures["yahooInstitutionalTrading"] = executor.submit(fetch_yahoo_institutional_trading, stock, 1300)
            futures["yahooMarginTrading"] = executor.submit(fetch_yahoo_margin_trading, stock, 60)
            if include_institutional_history:
                institutional_dates = build_institutional_trade_candidate_dates(rows, date_str, 70)
                futures["institutionalHistory"] = executor.submit(
                    fetch_stock_institutional_trade_history,
                    stock,
                    date_str,
                    30,
                    institutional_dates,
                )
            if include_shareholders:
                futures["shareholders"] = executor.submit(fetch_shareholder_distribution, stock["code"])
            if is_etf:
                futures["etfDividendInfo"] = executor.submit(fetch_etf_dividend_info, stock, 6)
        if not quick and not is_etf:
            futures.update({
                "valuation": executor.submit(fetch_stock_valuation, stock),
                "valuationHistory": executor.submit(fetch_stock_valuation_history, stock, rows, 5),
                "companyProfile": executor.submit(fetch_stock_company_profile, stock),
            })
        fetched = collect_futures_until_deadline(
            executor,
            futures,
            supplemental_timeout,
            {"valuationHistory", "companyNews"},
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    valuation = fetched.get("valuation", {})
    institutional_trade_history = fetched.get("institutionalHistory", {})
    institutional_trades = build_latest_stock_institutional_trade(institutional_trade_history)
    shareholder_distribution = fetched.get("shareholders", {})
    margin_trading = fetched.get("marginTrading", {})
    broker_trading = fetched.get("brokerTrading", {})
    major_holder_data = fetched.get("majorHolderData", {})
    yahoo_institutional_trading = fetched.get("yahooInstitutionalTrading", {})
    yahoo_margin_trading = fetched.get("yahooMarginTrading", {})
    valuation_history = fetched.get("valuationHistory", [])
    company_profile = fetched.get("companyProfile", {})
    company_news = fetched.get("companyNews", [])
    etf_components = build_etf_components(stock) if is_etf else None
    etf_dividend_info = fetched.get("etfDividendInfo", {}) if is_etf else {}
    if is_etf and not company_news:
        company_news = build_stock_news_fallback(stock, 6)
    if not is_etf and not company_profile:
        company_profile = build_fallback_company_profile(stock, valuation)
    if yahoo_margin_trading:
        margin_trading = {
            **(margin_trading or {}),
            **yahoo_margin_trading,
            "yahoo": yahoo_margin_trading,
            "dailyRows": yahoo_margin_trading.get("dailyRows") or [],
            "marginBalancePeriodRows": yahoo_margin_trading.get("marginBalancePeriodRows") or {},
            "marginSummaryAccumulationRows": yahoo_margin_trading.get("marginSummaryAccumulationRows") or [],
            "overviewRows": yahoo_margin_trading.get("overviewRows") or [],
            "marginBalanceChartRows": yahoo_margin_trading.get("marginBalanceChartRows") or [],
            "marginBalanceChartDataKey": yahoo_margin_trading.get("marginBalanceChartDataKey") or "",
            "marginBalanceChartSource": yahoo_margin_trading.get("marginBalanceChartSource") or "",
            "sourceLink": yahoo_margin_trading.get("sourceLink") or (margin_trading or {}).get("sourceLink"),
            "sourceNote": yahoo_margin_trading.get("sourceNote") or (margin_trading or {}).get("sourceNote"),
            "date": yahoo_margin_trading.get("date") or (margin_trading or {}).get("date"),
        }

    latest_valuation_date = str(valuation.get("date") or "")
    if latest_valuation_date and not any(
        item.get("date") == latest_valuation_date for item in valuation_history
    ):
        latest_yield = parse_float(str(valuation.get("dividendYield") or ""))
        latest_close = parse_float(str(stock.get("close") or ""))
        latest_dividend = parse_float(str(valuation.get("dividendPerShare") or ""))
        if latest_dividend is None and latest_close is not None and latest_yield is not None:
            latest_dividend = round(latest_close * latest_yield / 100, 4)
        valuation_history.append(
            {
                "date": latest_valuation_date,
                "peRatio": parse_float(str(valuation.get("peRatio") or "")),
                "dividendPerShare": latest_dividend,
                "dividendYield": latest_yield,
                "pbRatio": parse_float(str(valuation.get("pbRatio") or "")),
            }
        )
        valuation_history = sorted(valuation_history, key=lambda item: item["date"])[-6:]

    recent_rows = rows[-5:] if len(rows) >= 5 else rows
    closes = [parse_float(row[6]) for row in recent_rows if parse_float(row[6]) is not None]
    volumes = [parse_float(row[1]) for row in recent_rows if parse_float(row[1]) is not None]
    highs = [parse_float(row[4]) for row in rows if parse_float(row[4]) is not None]
    lows = [parse_float(row[5]) for row in rows if parse_float(row[5]) is not None]
    ma5 = sum(closes) / len(closes) if closes else None
    avg_volume_5 = sum(volumes) / len(volumes) if volumes else None
    close_value = parse_float(stock["close"])
    pct_value = parse_float(str(stock.get("pct", "")).replace("%", "")) if stock.get("pct") not in (None, "--") else None
    if ma5 is None:
        trend = "缺少 5 日均價資料"
    else:
        trend = "收盤高於 5 日均價" if close_value is not None and close_value >= ma5 else "收盤低於 5 日均價"

    chip_summary = build_chip_summary(
        stock=stock,
        avg_volume_5=avg_volume_5,
        pct_value=pct_value,
        institutional_trades=institutional_trades,
        institutional_trade_history=institutional_trade_history,
        shareholder_distribution=shareholder_distribution,
        margin_trading=margin_trading,
        broker_trading=broker_trading,
    )
    analysis = build_analysis_sections(
        stock=stock,
        closes=closes,
        volumes=volumes,
        highs=highs,
        lows=lows,
        ma5=ma5,
        avg_volume_5=avg_volume_5,
        site_data=site_data,
        valuation=valuation,
        institutional_trades=institutional_trades,
        shareholder_distribution=shareholder_distribution,
        margin_trading=margin_trading,
        etf_components=etf_components,
        etf_dividend_info=etf_dividend_info,
    )
    if isinstance(analysis.get("chips"), dict):
        analysis["chips"]["chipSummary"] = chip_summary

    history_days = [
        {
            "date": row[0],
            "open": row[3],
            "high": row[4],
            "low": row[5],
            "close": row[6],
            "change": row[7],
            "volume": row[1],
        }
        for row in rows
    ]

    full_close_series = [parse_float(item["close"]) for item in history_days]
    ma_windows = {}
    for window in (5, 20, 60):
        valid = [value for value in full_close_series[-window:] if value is not None]
        ma_windows[f"ma{window}"] = f"{(sum(valid) / len(valid)):,.2f}" if valid else "--"

    return {
        **stock,
        "snapshotDate": datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
        "ma5": f"{ma5:,.2f}" if ma5 is not None else "--",
        "ma20": ma_windows["ma20"],
        "ma60": ma_windows["ma60"],
        "monthHigh": f"{max(highs):,.2f}" if highs else "--",
        "monthLow": f"{min(lows):,.2f}" if lows else "--",
        "avgVolume5": f"{avg_volume_5:,.0f}" if avg_volume_5 is not None else "--",
        "trend": trend,
        "recentDays": [
            {
                "date": row[0],
                "open": row[3],
                "high": row[4],
                "low": row[5],
                "close": row[6],
                "change": row[7],
                "volume": row[1],
            }
            for row in recent_rows
        ],
        "historyDays": history_days,
        "historyCount": len(history_days),
        "historyStartDate": history_days[0]["date"] if history_days else None,
        "historyEndDate": history_days[-1]["date"] if history_days else None,
        "historyWarning": (
            f"已排除 {history_rows_removed} 筆不完整或不合理的 K 線資料。"
            if history_rows_removed else None
        ),
        "historyInvalidRowsRemoved": history_rows_removed,
        "isFallbackHistory": used_fallback_history,
        "allHistoryLoaded": months_back == STOCK_HISTORY_MAX_MONTHS,
        "chartIntervals": {
            "intradayAvailable": False,
            "intradayUnavailableReason": (
                "Yahoo奇摩股市同步日級歷史行情，不包含本站可用的分鐘級歷史 K 線。"
                if not used_fallback_history
                else "歷史行情來源暫時無法連線，目前顯示快取行情。"
            ),
            "supported": SUPPORTED_CHART_INTERVALS,
        },
        "analysis": analysis,
        "chipSummary": chip_summary,
        "valuation": valuation,
        "valuationHistory": valuation_history,
        "companyProfile": company_profile,
        "etfComponents": etf_components,
        "etfDividendInfo": etf_dividend_info,
        "isEtf": is_etf,
        "detailMode": "quick" if quick else "full",
        "companyNews": company_news,
        "newsLinks": {
            "yahoo": (
                f"https://tw.stock.yahoo.com/quote/{stock['code']}.TWO/news"
                if str(market).upper() == "TPEX"
                else f"https://tw.stock.yahoo.com/quote/{stock['code']}.TW/news"
            ),
            "google": (
                "https://news.google.com/search?"
                + urlencode({
                    "q": (
                        f"{stock['code']} {stock.get('name', '')} ETF 配息 成分股 公告"
                        if is_etf else f"{stock['code']} {stock.get('name', '')} 台股 新聞"
                    ),
                    "hl": "zh-TW",
                    "gl": "TW",
                    "ceid": "TW:zh-Hant",
                })
            ),
            "mops": "https://mops.twse.com.tw/mops/#/web/t05st01",
        },
        "institutionalTrades": institutional_trades,
        "institutionalTradeHistory": institutional_trade_history,
        "yahooInstitutionalTrading": yahoo_institutional_trading,
        "brokerTrading": broker_trading,
        "majorHolderData": major_holder_data,
        "shareholderDistribution": shareholder_distribution,
        "marginTrading": margin_trading,
        "sourceLink": (
            f"https://tw.stock.yahoo.com/quote/{stock['code']}.TWO"
            if market == "TPEx"
            else f"https://tw.stock.yahoo.com/quote/{stock['code']}.TW"
        ),
    }


def build_news(site_data: dict[str, Any]) -> list[dict[str, Any]]:
    tracked_indices = [
        item for item in site_data.get("sectors", [])
        if item.get("name") != "台灣加權指數"
    ]
    ranked_indices = sorted(
        [
            {
                **item,
                "pctNumeric": parse_float(str(item.get("pct", "")).replace("%", "")),
            }
            for item in tracked_indices
        ],
        key=lambda item: item.get("pctNumeric") if item.get("pctNumeric") is not None else -9999.0,
        reverse=True,
    )
    strongest_sector = ranked_indices[0] if ranked_indices else {}
    weakest_sector = ranked_indices[-1] if ranked_indices else {}
    advancing = sum(1 for item in ranked_indices if (item.get("pctNumeric") or 0) > 0)
    declining = sum(1 for item in ranked_indices if (item.get("pctNumeric") or 0) < 0)
    unchanged = sum(1 for item in ranked_indices if (item.get("pctNumeric") or 0) == 0)
    breadth_total = advancing + declining + unchanged
    breadth_ratio = advancing / breadth_total if breadth_total else 0.5
    breadth_text = (
        "買盤擴散"
        if breadth_ratio >= 0.6 else
        "賣壓擴散"
        if breadth_ratio <= 0.4 else
        "多空分歧"
    )
    breadth_percent_text = f"{breadth_ratio * 100:.0f}%" if breadth_total else "--"
    market_overview = (site_data.get("marketOverview") or [{}])[0]
    market_stats = site_data.get("marketStats") or {}
    market_pct = parse_float(str(market_overview.get("pct", "")).replace("%", ""))
    market_volume = parse_float(str(market_overview.get("volume", "")))
    market_turnover = parse_float(str(
        market_overview.get("turnoverValue")
        or market_overview.get("turnover")
        or market_stats.get("turnoverValue")
        or market_stats.get("turnover")
        or ""
    ))
    market_trade_count = parse_float(str(
        market_overview.get("tradeCount")
        or market_overview.get("trades")
        or market_stats.get("tradeCount")
        or market_stats.get("trades")
        or ""
    ))
    market_volume_text = (
        f"{market_volume / 100000000:,.1f} 億股"
        if market_volume is not None and market_volume >= 100000000 else
        str(market_overview.get("volume") or "--")
    )
    market_turnover_text = f"{market_turnover / 100000000:,.1f} 億元" if market_turnover is not None else "--"
    market_trade_text = f"{market_trade_count / 10000:,.1f} 萬筆" if market_trade_count is not None else "--"
    market_direction = (
        "偏多續航"
        if market_pct is not None and market_pct >= 0.5 else
        "震盪偏穩"
        if market_pct is not None and market_pct >= 0 else
        "回測承壓"
        if market_pct is not None and market_pct <= -0.5 else
        "小幅整理"
    )
    institutions = site_data.get("institutions") or []
    institution_summary = site_data.get("institutionSummary") or []
    institution_total = next((item for item in institutions if item.get("name") == "合計"), None)
    institution_net = None
    if isinstance(institution_total, dict):
        institution_net = parse_float(str(institution_total.get("diffValue") or institution_total.get("diff") or ""))
    if institution_net is None:
        institution_net = sum((item.get("diffValue") or 0) for item in institution_summary)
    foreign = next((item for item in institution_summary if item.get("key") == "foreign"), None)
    trust = next((item for item in institution_summary if item.get("key") == "trust"), None)
    dealer = next((item for item in institution_summary if item.get("key") == "dealer"), None)
    institution_trend = site_data.get("institutionTrend") or {}
    source_links = site_data.get("sourceLinks") or {}

    def amount_text(value: Any, signed: bool = False) -> str:
        number = value if isinstance(value, (int, float)) else parse_float(str(value))
        if number is None:
            return "--"
        prefix = "+" if signed and number > 0 else ""
        return f"{prefix}{number / 100000000:,.1f} 億"

    def sector_text(item: dict[str, Any]) -> str:
        name = item.get("name") or "族群"
        pct = item.get("pct") or "--"
        return f"{name} {pct}"

    def trend_label(key: str, fallback: str = "連續性待同步") -> str:
        trend = institution_trend.get(key) if isinstance(institution_trend, dict) else None
        return str((trend or {}).get("label") or fallback)

    leader_names = "、".join(sector_text(item) for item in ranked_indices[:3] if item.get("name")) or "強勢族群同步中"
    weak_names = "、".join(sector_text(item) for item in ranked_indices[-3:] if item.get("name")) or "弱勢族群同步中"
    spread = None
    if strongest_sector.get("pctNumeric") is not None and weakest_sector.get("pctNumeric") is not None:
        spread = (strongest_sector.get("pctNumeric") or 0) - (weakest_sector.get("pctNumeric") or 0)
    spread_text = f"{spread:.2f} 個百分點" if spread is not None else "--"
    overview_indices = site_data.get("marketOverview") or []

    def find_index_row(*keywords: str) -> dict[str, Any] | None:
        rows = [*overview_indices, *ranked_indices]
        return next(
            (
                item for item in rows
                if all(keyword in str(item.get("name") or "") for keyword in keywords)
            ),
            None,
        )

    electronic_sector = find_index_row("電子")
    semiconductor_sector = find_index_row("半導體")
    tech_context_parts = []
    if electronic_sector:
        tech_context_parts.append(f"電子 {electronic_sector.get('pct', '--')}")
    if semiconductor_sector:
        tech_context_parts.append(f"半導體 {semiconductor_sector.get('pct', '--')}")
    tech_context = "、".join(tech_context_parts) if tech_context_parts else "權值科技資料同步中"
    net_direction = "買超" if (institution_net or 0) >= 0 else "賣超"
    foreign_value = foreign.get("diffValue") if foreign else None
    trust_value = trust.get("diffValue") if trust else None
    dealer_value = dealer.get("diffValue") if dealer else None
    institutional_pressure = (
        "外資主導調節"
        if (foreign_value or 0) < 0 and (institution_net or 0) < 0 else
        "外資帶動回補"
        if (foreign_value or 0) > 0 and (institution_net or 0) > 0 else
        "法人結構分歧"
        if (foreign_value or 0) * (trust_value or 0) < 0 else
        "資金面中性觀察"
    )
    net_context = (
        "資金面對指數形成支撐"
        if (institution_net or 0) >= 0 else
        "資金面仍偏向調節"
    )

    return [
        {
            "tag": "大盤",
            "title": f"{site_data['snapshotDate']} 加權指數 {market_overview.get('value', '--')} 點，{market_direction}但廣度{breadth_text}",
            "body": (
                f"加權指數漲跌幅 {market_overview.get('pct', '--')}、成交金額 {market_turnover_text}、成交量 {market_volume_text}，"
                f"成交筆數約 {market_trade_text}。{breadth_total} 個追蹤類股中 {advancing} 漲、{declining} 跌、{unchanged} 平，"
                f"上漲占比 {breadth_percent_text}，顯示盤勢不是只看指數點位，而要同步檢查買盤是否擴散。"
                "隔日若量能維持且強勢族群未快速退潮，盤勢較有機會延續；若指數守平盤但廣度轉弱，需防震盪整理。"
            ),
            "link": source_links.get("market"),
        },
        {
            "tag": "指數",
            "title": f"{strongest_sector.get('name', '強勢族群')} 領先，{weakest_sector.get('name', '弱勢族群')} 落後，強弱差 {spread_text}",
            "body": (
                f"領漲端為 {leader_names}，落後端為 {weak_names}。"
                f"權值科技同步觀察 {tech_context}，若科技權值偏弱但傳產或防禦族群走強，代表資金正在輪動而非全面追價。"
                "操作上可優先比對領先族群的成交金額與個股擴散度；若強弱差收斂，則表示輪動降溫，追高勝率會下降。"
            ),
            "link": source_links.get("market"),
        },
        {
            "tag": "法人",
            "title": f"三大法人合計{net_direction} {amount_text(abs(institution_net or 0))}，{institutional_pressure}",
            "body": (
                f"外資 {amount_text(foreign_value, True)}（{trend_label('foreign')}）、"
                f"投信 {amount_text(trust_value, True)}（{trend_label('trust')}）、"
                f"自營商 {amount_text(dealer_value, True)}（{trend_label('dealer')}）。"
                f"目前{net_context}；若法人賣超集中在外資且指數仍小漲，代表內資與族群輪動正在吸收賣壓，"
                "隔日需追蹤外資賣超是否收斂，以及投信承接是否仍集中在強勢族群。"
            ),
            "link": source_links.get("institutions"),
        },
    ]


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


def global_market_item_cache_key(spec: dict[str, Any]) -> str:
    fields = {
        "symbol": spec.get("symbol"),
        "provider": spec.get("dataProvider"),
        "fallbacks": spec.get("fallbackSymbols") or [],
        "sourceUrl": spec.get("sourceUrl"),
        "treasuryMaturity": spec.get("treasuryMaturity"),
        "fredSeriesId": spec.get("fredSeriesId"),
        "taifexCommodity": spec.get("taifexCommodity"),
        "optionChainSymbol": spec.get("optionChainSymbol"),
        "optionChainUnavailableReason": spec.get("optionChainUnavailableReason"),
        "v1Status": spec.get("v1Status"),
    }
    return json.dumps(fields, ensure_ascii=False, sort_keys=True, default=str)


def cache_global_market_item(cache_key: str, item: dict[str, Any]) -> dict[str, Any]:
    write_memory_cache("global_market_items", cache_key, copy.deepcopy(item))
    return item



def build_us_treasury_yield_curve_item(spec: dict[str, Any], base_item: dict[str, Any]) -> dict[str, Any]:
    maturity = str(spec.get("treasuryMaturity") or "2 Yr")
    try:
        dated_rows = fetch_us_treasury_yield_curve_rows()
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("U.S. Treasury yield curve fetch failed", exc_info=exc)
        return {**base_item, "error": "U.S. Treasury 官方殖利率暫時無法載入"}

    series: list[dict[str, Any]] = []
    for date_value, row in dated_rows:
        yield_value = parse_float(str(row.get(maturity) or ""))
        if yield_value is None:
            continue
        formatted = f"{yield_value:.2f}"
        series.append({
            "date": date_value.strftime("%Y-%m-%d"),
            "open": formatted,
            "high": formatted,
            "low": formatted,
            "close": formatted,
            "volume": "0",
            "volumeValue": 0,
        })
    if len(series) < 2:
        return {**base_item, "error": f"U.S. Treasury 官方 {maturity} 殖利率暫無可用資料"}

    latest = series[-1]
    previous = series[-2]
    close_value = parse_float(str(latest.get("close") or ""))
    previous_close = parse_float(str(previous.get("close") or ""))
    first_close = parse_float(str(series[0].get("close") or ""))
    change = close_value - previous_close if close_value is not None and previous_close is not None else None
    pct = change / previous_close * 100 if change is not None and previous_close not in (None, 0) else None
    period_return = (
        (close_value - first_close) / first_close * 100
        if close_value is not None and first_close not in (None, 0)
        else None
    )
    return {
        **base_item,
        "dataSymbol": spec.get("symbol") or maturity,
        "currency": "%",
        "exchange": base_item.get("exchange") or "U.S. Treasury",
        "date": latest.get("date") or "",
        "open": latest.get("close") or "--",
        "high": latest.get("close") or "--",
        "low": latest.get("close") or "--",
        "close": latest.get("close") or "--",
        "previousClose": previous.get("close") or "--",
        "change": format_signed(change) if change is not None else "--",
        "pct": format_percent(pct) if pct is not None else "--",
        "periodReturn": format_percent(period_return) if period_return is not None else "--",
        "volume": "--",
        "sourceLink": base_item.get("sourceUrl") or US_TREASURY_YIELD_CURVE_CSV_URL,
        "series": series[-240:],
    }


FALLBACK_OBSERVATION_MAX_AGE_DAYS = 400


def is_fallback_observation_stale(date_value: datetime) -> bool:
    return (taipei_now().date() - date_value.date()).days > FALLBACK_OBSERVATION_MAX_AGE_DAYS


def fallback_fred_observation(spec: dict[str, Any]) -> list[tuple[datetime, float]]:
    fallback = spec.get("fallbackObservation") or {}
    value = parse_float(str(fallback.get("value") or ""))
    date_value = parse_fred_date(str(fallback.get("date") or ""))
    if value is None or date_value is None:
        return []
    if is_fallback_observation_stale(date_value):
        return []
    return [(date_value, value)]


def build_fred_latest_observation_item(spec: dict[str, Any], base_item: dict[str, Any]) -> dict[str, Any]:
    series_id = str(spec.get("fredSeriesId") or "").strip().upper()
    observations: list[tuple[datetime, float]] = []
    source_note = spec.get("dataSource") or "FRED"
    source_status = "live"
    try:
        observations = fetch_fred_observation_rows(series_id)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("FRED series fetch failed for %s: %s", series_id, exc)
        observations = fallback_fred_observation(spec)
        source_status = "snapshot"
        source_note = str((spec.get("fallbackObservation") or {}).get("source") or "FRED snapshot fallback")

    if not observations:
        return {**base_item, "error": f"FRED {series_id} 暫無可用資料"}

    series = []
    for date_value, value in observations[-240:]:
        formatted = f"{value:.2f}"
        series.append({
            "date": date_value.strftime("%Y-%m-%d"),
            "open": formatted,
            "high": formatted,
            "low": formatted,
            "close": formatted,
            "volume": "0",
            "volumeValue": 0,
        })
    latest = series[-1]
    previous = series[-2] if len(series) >= 2 else {}
    close_value = parse_float(str(latest.get("close") or ""))
    previous_close = parse_float(str(previous.get("close") or ""))
    first_close = parse_float(str(series[0].get("close") or ""))
    change = close_value - previous_close if close_value is not None and previous_close is not None else None
    pct = change / previous_close * 100 if change is not None and previous_close not in (None, 0) else None
    period_return = (
        (close_value - first_close) / first_close * 100
        if close_value is not None and first_close not in (None, 0)
        else None
    )
    return {
        **base_item,
        "dataSymbol": series_id or spec.get("symbol") or "",
        "currency": "%",
        "date": latest.get("date") or "--",
        "open": latest.get("close") or "--",
        "high": latest.get("close") or "--",
        "low": latest.get("close") or "--",
        "close": latest.get("close") or "--",
        "previousClose": previous.get("close") or "--",
        "change": format_signed(change) if change is not None else "--",
        "pct": format_percent(pct) if pct is not None else "--",
        "periodReturn": format_percent(period_return) if period_return is not None else "--",
        "volume": "--",
        "source": source_note,
        "dataSource": source_note,
        "sourceStatus": source_status,
        "sourceNote": f"{source_note}；series {series_id}。數值單位為百分比。" if series_id else source_note,
        "sourceLink": base_item.get("sourceUrl") or f"https://fred.stlouisfed.org/series/{quote(series_id, safe='')}",
        "series": series,
    }


def fallback_single_yield_observation(spec: dict[str, Any]) -> dict[str, Any] | None:
    fallback = spec.get("fallbackObservation") or {}
    value = parse_float(str(fallback.get("value") or ""))
    date_value = parse_fred_date(str(fallback.get("date") or ""))
    if value is None or date_value is None:
        return None
    if is_fallback_observation_stale(date_value):
        return None
    change = parse_float(str(fallback.get("change") or ""))
    return {
        "date": date_value.strftime("%Y-%m-%d"),
        "value": value,
        "change": change,
        "description": "",
        "source": str(fallback.get("source") or "snapshot fallback"),
        "sourceStatus": "snapshot",
    }


def build_single_yield_item_from_observation(
    spec: dict[str, Any],
    base_item: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    close_value = parse_float(str(observation.get("value") or ""))
    change = parse_float(str(observation.get("change") or ""))
    if close_value is None:
        return {**base_item, "error": f"{base_item.get('name') or base_item.get('symbol')} 暫無可用殖利率資料"}
    previous_close = close_value - change if change is not None else None
    pct = change / previous_close * 100 if change is not None and previous_close not in (None, 0) else None
    formatted = f"{close_value:.2f}"
    previous_formatted = f"{previous_close:.2f}" if previous_close is not None else "--"
    date_text = str(observation.get("date") or "--")
    return {
        **base_item,
        "dataSymbol": spec.get("symbol") or base_item.get("symbol") or "",
        "currency": "%",
        "date": date_text,
        "open": formatted,
        "high": formatted,
        "low": formatted,
        "close": formatted,
        "previousClose": previous_formatted,
        "change": format_signed(change) if change is not None else "--",
        "pct": format_percent(pct) if pct is not None else "--",
        "periodReturn": format_percent(pct) if pct is not None else "--",
        "volume": "--",
        "source": observation.get("source") or base_item.get("source") or "",
        "dataSource": observation.get("source") or base_item.get("dataSource") or "",
        "sourceStatus": observation.get("sourceStatus") or "live",
        "sourceNote": observation.get("description") or f"{observation.get('source') or base_item.get('referenceSource') or ''}；數值單位為百分比。",
        "sourceLink": base_item.get("sourceUrl") or "",
        "series": [{
            "date": date_text,
            "open": formatted,
            "high": formatted,
            "low": formatted,
            "close": formatted,
            "volume": "0",
            "volumeValue": 0,
        }],
    }


def build_trading_economics_taiwan_10y_item(spec: dict[str, Any], base_item: dict[str, Any]) -> dict[str, Any]:
    try:
        observation = fetch_trading_economics_taiwan_10y()
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Trading Economics Taiwan 10Y fetch failed: %s", exc)
        observation = None
    if not observation:
        observation = fallback_single_yield_observation(spec)
    if not observation:
        return {**base_item, "error": "台灣 10Y 公債殖利率暫無可用資料"}
    return build_single_yield_item_from_observation(spec, base_item, observation)


def normalize_taiwan_quote_code(symbol: str) -> str:
    code = str(symbol or "").strip().upper()
    for suffix in (".TW", ".TWO"):
        if code.endswith(suffix):
            return code[: -len(suffix)]
    return code


def cached_taiwan_quote_row(symbol: str) -> dict[str, Any] | None:
    code = normalize_taiwan_quote_code(symbol)
    if not code:
        return None
    with cache_lock:
        rows = list(cache_data.get("all_stocks") or [])
    if not rows:
        try:
            load_disk_cache()
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Unable to load disk cache for Taiwan quote fallback", exc_info=exc)
        with cache_lock:
            rows = list(cache_data.get("all_stocks") or [])
    return next((row for row in rows if str(row.get("code") or "").upper() == code), None)


def build_taiwan_quote_fallback_item(spec: dict[str, Any], base_item: dict[str, Any]) -> dict[str, Any] | None:
    symbol = str(spec.get("symbol") or "")
    if not (symbol.upper().endswith(".TW") or symbol.upper().endswith(".TWO")):
        return None
    row = cached_taiwan_quote_row(symbol)
    if not row:
        return None
    close_value = parse_float(str(row.get("close") or ""))
    if close_value is None:
        return None
    change_value = parse_float(str(row.get("change") or ""))
    previous_close = close_value - change_value if change_value is not None else None
    with cache_lock:
        market_date = cache_data.get("market_date")
        site_data = cache_data.get("site_data") or {}
    date_text = str(site_data.get("snapshotDate") or "")
    if not date_text and market_date:
        try:
            date_text = datetime.strptime(str(market_date), "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            date_text = str(market_date)
    return {
        **base_item,
        "dataSymbol": symbol,
        "name": spec.get("name") or row.get("name") or base_item.get("name"),
        "currency": "TWD",
        "exchange": base_item.get("exchange") or row.get("market") or "TWSE",
        "date": date_text,
        "open": str(row.get("open") or "--"),
        "high": str(row.get("high") or "--"),
        "low": str(row.get("low") or "--"),
        "close": f"{close_value:.2f}",
        "previousClose": f"{previous_close:.2f}" if previous_close is not None else "--",
        "change": str(row.get("change") or "--"),
        "pct": str(row.get("pct") or "--"),
        "periodReturn": "--",
        "volume": str(row.get("volume") or "--"),
        "volumeValue": parse_float(str(row.get("volume") or "")),
        "source": f"{base_item.get('source') or 'Yahoo Finance'} / TWSE 快取備援",
        "dataSource": f"{base_item.get('dataSource') or 'Yahoo Finance'} / TWSE 快取備援",
        "sourceLink": f"https://tw.stock.yahoo.com/quote/{symbol}",
        "technicalAnalysis": row.get("technicalAnalysis") or {},
        "series": [{
            "date": date_text,
            "open": str(row.get("open") or "--"),
            "high": str(row.get("high") or "--"),
            "low": str(row.get("low") or "--"),
            "close": f"{close_value:.2f}",
            "volume": str(row.get("volume") or "--"),
            "volumeValue": parse_float(str(row.get("volume") or "")),
        }],
    }


def build_global_market_item(spec: dict[str, Any]) -> dict[str, Any]:
    symbol = str(spec.get("symbol") or "").strip()
    item_cache_key = global_market_item_cache_key(spec)
    if not global_market_refresh_requested():
        cached_item = read_memory_cache("global_market_items", item_cache_key, GLOBAL_MARKET_ITEM_CACHE_SECONDS)
        cached_close = parse_float(str((cached_item or {}).get("close") or ""))
        if cached_item is not None and not cached_item.get("error") and cached_close is not None:
            return copy.deepcopy(cached_item)

    item = {
        "symbol": symbol,
        "name": spec.get("name") or symbol,
        "type": spec.get("type") or "市場商品",
        "group": spec.get("group") or spec.get("type") or "市場商品",
        "region": spec.get("region") or "全球 / 其他",
        "market": spec.get("market") or spec.get("region") or "全球 / 其他",
        "exchange": spec.get("exchange") or "",
        "source": spec.get("dataSource") or "Yahoo Finance",
        "dataSource": spec.get("dataSource") or "Yahoo Finance",
        "referenceSource": spec.get("referenceSource") or "",
        "sourceUrl": spec.get("sourceUrl") or "",
        "metricLabel": spec.get("metricLabel") or "成交量",
        "optionCategory": spec.get("optionCategory") or "",
        "optionSubcategory": spec.get("optionSubcategory") or "",
        "optionSourceRole": spec.get("optionSourceRole") or "",
        "taifexCommodity": spec.get("taifexCommodity") or "",
        "optionChainSymbol": spec.get("optionChainSymbol") or "",
        "optionChainUnavailableReason": spec.get("optionChainUnavailableReason") or "",
        "documentCategory": spec.get("documentCategory") or "",
    }
    try:
        if spec.get("dataProvider") in {"taifex_option_product_status", "taifex_product_status"}:
            return cache_global_market_item(item_cache_key, build_taifex_stock_derivative_aggregate_item(spec))
        if is_source_pending_product(spec):
            return cache_global_market_item(item_cache_key, build_source_pending_market_item(item, spec))
        if spec.get("dataProvider") == "taifex_txo_open_interest":
            return cache_global_market_item(item_cache_key, build_txo_option_market_item(spec))
        if spec.get("dataProvider") in {"taifex_tx_open_interest", "taifex_txo_open_interest", "taifex_futures_open_interest"}:
            return cache_global_market_item(item_cache_key, build_taifex_open_interest_item(spec))
        if spec.get("dataProvider") == "us_treasury_yield_curve":
            return cache_global_market_item(item_cache_key, build_us_treasury_yield_curve_item(spec, item))
        if spec.get("dataProvider") == "fred_latest_observation":
            return cache_global_market_item(item_cache_key, build_fred_latest_observation_item(spec, item))
        if spec.get("dataProvider") == "trading_economics_taiwan_10y":
            return cache_global_market_item(item_cache_key, build_trading_economics_taiwan_10y_item(spec, item))
        chart = None
        selected_symbol = symbol
        series: list[dict[str, Any]] = []
        candidates = list(dict.fromkeys(str(candidate or "").strip() for candidate in [symbol, *spec.get("fallbackSymbols", [])] if str(candidate or "").strip()))
        for candidate in candidates:
            selected_symbol = str(candidate or "").strip()
            for attempt in range(2):
                try:
                    chart = fetch_yahoo_symbol_chart(selected_symbol, "1y", "1d")
                    series = build_yahoo_chart_series(chart, volume_divisor=1)
                except Exception:  # noqa: BLE001
                    chart = None
                    series = []
                if len(series) >= 2:
                    break
                if attempt == 0:
                    time.sleep(0.15)
            if len(series) >= 2:
                break
        meta = (chart or {}).get("meta") or {}
        if not series:
            taiwan_fallback = build_taiwan_quote_fallback_item(spec, item)
            if taiwan_fallback:
                return cache_global_market_item(item_cache_key, taiwan_fallback)
            return {**item, "error": "Yahoo Finance 暫無可用歷史資料"}

        latest = series[-1]
        previous = series[-2] if len(series) > 1 else {}
        close_value = parse_float(str(latest.get("close") or ""))
        previous_close = parse_float(str(meta.get("previousClose") or previous.get("close") or ""))
        open_value = parse_float(str(latest.get("open") or ""))
        high_value = parse_float(str(latest.get("high") or ""))
        low_value = parse_float(str(latest.get("low") or ""))
        volume_value = parse_float(str(latest.get("volumeValue") or latest.get("volume") or ""))
        first_close = parse_float(str(series[0].get("close") or ""))
        change = close_value - previous_close if close_value is not None and previous_close not in (None, 0) else None
        pct = (change / previous_close * 100) if change is not None and previous_close not in (None, 0) else None
        period_return = (
            (close_value - first_close) / first_close * 100
            if close_value is not None and first_close not in (None, 0)
            else None
        )
        result = {
            **item,
            "dataSymbol": selected_symbol,
            "currency": meta.get("currency") or "",
            "exchange": item.get("exchange") or meta.get("exchangeName") or meta.get("fullExchangeName") or "",
            "date": latest.get("date") or "",
            "open": f"{open_value:.2f}" if open_value is not None else "--",
            "high": f"{high_value:.2f}" if high_value is not None else "--",
            "low": f"{low_value:.2f}" if low_value is not None else "--",
            "close": f"{close_value:.2f}" if close_value is not None else "--",
            "previousClose": f"{previous_close:.2f}" if previous_close is not None else "--",
            "change": format_signed(change) if change is not None else "--",
            "pct": format_percent(pct) if pct is not None else "--",
            "periodReturn": format_percent(period_return) if period_return is not None else "--",
            "volume": format_whole_number(volume_value) if volume_value is not None else "--",
            "series": series[-240:],
        }
        return cache_global_market_item(item_cache_key, result)
    except Exception as exc:
        LOGGER.exception("Global market item fetch failed for symbol=%s", symbol, exc_info=exc)
        taiwan_fallback = build_taiwan_quote_fallback_item(spec, item)
        if taiwan_fallback:
            return cache_global_market_item(item_cache_key, taiwan_fallback)
        return cache_global_market_item(item_cache_key, {**item, "error": PUBLIC_MARKET_ITEM_ERROR_MESSAGE})


def yahoo_field_raw(value: Any) -> float | str | None:
    if isinstance(value, dict):
        if value.get("raw") is not None:
            return value.get("raw")
        if value.get("fmt") is not None:
            return value.get("fmt")
    return value if value not in ("", None) else None


def yahoo_field_fmt(value: Any, digits: int = 2) -> str:
    if isinstance(value, dict):
        if value.get("fmt") not in (None, ""):
            return str(value.get("fmt"))
        value = value.get("raw")
    parsed = parse_float(str(value or ""))
    if parsed is None:
        return "--"
    return f"{parsed:,.{digits}f}"


def format_us_large_number(value: Any) -> str:
    parsed = parse_float(str(value if not isinstance(value, dict) else value.get("raw") or ""))
    if parsed is None:
        return "--"
    abs_value = abs(parsed)
    if abs_value >= 1_000_000_000_000:
        return f"{parsed / 1_000_000_000_000:.2f}T"
    if abs_value >= 1_000_000_000:
        return f"{parsed / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"{parsed / 1_000_000:.2f}M"
    return f"{parsed:,.0f}"


def us_value_missing(value: Any) -> bool:
    text = str(value or "").strip()
    return text in {"", "--", "-", "N/A", "NA", "None", "null", "--%", "-%"}


def display_or_na(value: Any) -> str:
    return "N/A" if us_value_missing(value) else str(value).strip()


def parse_us_display_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("raw") if value.get("raw") is not None else value.get("value") or value.get("fmt")
    text = str(value).strip()
    if us_value_missing(text):
        return None
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    multiplier = 1.0
    suffix_match = re.search(r"([KMBT])(?:\s|\(|$)", text, re.IGNORECASE)
    if suffix_match:
        suffix = suffix_match.group(1).upper()
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}.get(suffix, 1.0)
    cleaned = (
        text.replace("$", "")
        .replace(",", "")
        .replace("%", "")
        .replace("+", "")
        .replace("約", "")
        .replace("估", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )
    cleaned = re.sub(r"[KMBT]", "", cleaned, flags=re.IGNORECASE).strip()
    if not cleaned:
        return None
    try:
        parsed = float(cleaned) * multiplier
    except ValueError:
        return None
    return -parsed if negative and parsed > 0 else parsed


def format_us_ratio(value: Any, digits: int = 2) -> str:
    parsed = parse_us_display_number(value)
    return f"{parsed:.{digits}f}" if parsed is not None else "N/A"


def format_us_percent_value(value: Any, digits: int = 2) -> str:
    parsed = parse_us_display_number(value)
    return f"{parsed:.{digits}f}" if parsed is not None else "N/A"


def format_us_large_number_from_float(value: float | None, estimated: bool = False) -> str:
    if value is None or not math.isfinite(value):
        return "N/A"
    text = format_us_large_number(value)
    return f"{text} (估)" if estimated and text != "--" else text


def nasdaq_labeled_value(container: dict[str, Any] | None, key: str) -> Any:
    item = (container or {}).get(key)
    if isinstance(item, dict):
        return item.get("value")
    return item


def nasdaq_table_row_value(table: dict[str, Any] | None, row_names: list[str], column: str = "value2") -> Any:
    names = [name.lower() for name in row_names]
    for row in (table or {}).get("rows") or []:
        label = str(row.get("value1") or "").strip().lower()
        if any(name in label for name in names):
            value = row.get(column)
            if not us_value_missing(value):
                return value
    return None


def parse_nasdaq_financial_value(value: Any) -> float | None:
    parsed = parse_us_display_number(value)
    if parsed is None:
        return None
    return parsed * 1000


def parse_us_date(value: Any) -> str:
    text = str(value or "").strip()
    if us_value_missing(text):
        return "--"
    for fmt in ("%m/%d/%Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


def format_us_unix_date(value: Any) -> str:
    raw = yahoo_field_raw(value)
    parsed = parse_float(str(raw or ""))
    if parsed is None:
        return "--"
    try:
        return datetime.fromtimestamp(parsed, TZ).strftime("%Y-%m-%d")
    except (OSError, ValueError):
        return "--"



def build_us_valuation(summary: dict[str, Any]) -> dict[str, Any]:
    summary_detail = summary.get("summaryDetail") or {}
    key_stats = summary.get("defaultKeyStatistics") or {}
    financial = summary.get("financialData") or {}
    price = summary.get("price") or {}
    dividend_yield = yahoo_field_raw(summary_detail.get("dividendYield"))
    if isinstance(dividend_yield, (int, float)):
        dividend_yield = dividend_yield * 100
    return {
        "date": datetime.now(TZ).strftime("%Y-%m-%d"),
        "peRatio": yahoo_field_fmt(summary_detail.get("trailingPE") or key_stats.get("trailingPE")),
        "forwardPE": yahoo_field_fmt(summary_detail.get("forwardPE") or key_stats.get("forwardPE")),
        "pbRatio": yahoo_field_fmt(key_stats.get("priceToBook")),
        "priceToSales": yahoo_field_fmt(key_stats.get("priceToSalesTrailing12Months")),
        "dividendYield": f"{dividend_yield:.2f}" if isinstance(dividend_yield, (int, float)) else yahoo_field_fmt(summary_detail.get("dividendYield")),
        "dividendPerShare": yahoo_field_fmt(summary_detail.get("dividendRate")),
        "marketCap": format_us_large_number(price.get("marketCap") or summary_detail.get("marketCap")),
        "enterpriseValue": format_us_large_number(key_stats.get("enterpriseValue")),
        "beta": yahoo_field_fmt(summary_detail.get("beta")),
        "profitMargins": yahoo_field_fmt(financial.get("profitMargins")),
        "revenueGrowth": yahoo_field_fmt(financial.get("revenueGrowth")),
        "sourceNote": "Yahoo Finance quote summary；美股估值欄位可能因標的或資料授權而缺漏。",
    }


def build_us_fallback_valuation(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "date": datetime.now(TZ).strftime("%Y-%m-%d"),
        "peRatio": "N/A",
        "forwardPE": "N/A",
        "pbRatio": "N/A",
        "priceToSales": "N/A",
        "dividendYield": "N/A",
        "dividendPerShare": "N/A",
        "marketCap": "N/A",
        "enterpriseValue": "N/A",
        "beta": "N/A",
        "profitMargins": "N/A",
        "revenueGrowth": "N/A",
        "sourceNote": "Yahoo quote summary 進階估值暫時無法授權取得；目前以行情、歷史價格與外部連結提供基本分析骨架。",
    }


def nasdaq_dividend_header_value(dividends_data: dict[str, Any], label: str) -> Any:
    target = label.lower()
    for item in dividends_data.get("dividendHeaderValues") or []:
        if target in str(item.get("label") or "").lower():
            return item.get("value")
    return None


def merge_us_nasdaq_valuation(
    valuation: dict[str, Any],
    nasdaq: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(valuation or {})
    summary_data = ((nasdaq.get("summary") or {}).get("data") or {}).get("summaryData") or {}
    dividends_data = (nasdaq.get("dividends") or {}).get("data") or {}
    financials = nasdaq.get("financials") or {}
    latest_close = parse_us_display_number(item.get("close"))

    market_cap = parse_us_display_number(nasdaq_labeled_value(summary_data, "MarketCap"))
    annual_dividend = (
        parse_us_display_number(nasdaq_labeled_value(summary_data, "AnnualizedDividend"))
        or parse_us_display_number(dividends_data.get("annualizedDividend"))
        or parse_us_display_number(nasdaq_dividend_header_value(dividends_data, "Annual Dividend"))
    )
    dividend_yield = (
        parse_us_display_number(nasdaq_labeled_value(summary_data, "Yield"))
        or parse_us_display_number(dividends_data.get("yield"))
        or parse_us_display_number(nasdaq_dividend_header_value(dividends_data, "Dividend Yield"))
    )
    pe_ratio = (
        parse_us_display_number(nasdaq_dividend_header_value(dividends_data, "P/E Ratio"))
        or parse_us_display_number(dividends_data.get("payoutRatio"))
    )
    beta = parse_us_display_number(nasdaq_labeled_value(summary_data, "Beta"))

    income_table = financials.get("incomeStatementTable") or {}
    balance_table = financials.get("balanceSheetTable") or {}
    ratios_table = financials.get("financialRatiosTable") or {}
    latest_revenue = parse_nasdaq_financial_value(nasdaq_table_row_value(income_table, ["Total Revenue"]))
    prior_revenue = parse_nasdaq_financial_value(nasdaq_table_row_value(income_table, ["Total Revenue"], "value3"))
    latest_equity = parse_nasdaq_financial_value(nasdaq_table_row_value(
        balance_table,
        ["Total Equity", "Stockholders' Equity", "Shareholders' Equity", "Total Stockholder"],
    ))
    profit_margin = parse_us_display_number(nasdaq_table_row_value(ratios_table, ["Profit Margin"]))

    if market_cap is not None:
        merged["marketCap"] = format_us_large_number(market_cap)
        if us_value_missing(merged.get("enterpriseValue")):
            merged["enterpriseValue"] = f"約 {format_us_large_number(market_cap)}"
    if annual_dividend is not None:
        merged["dividendPerShare"] = f"{annual_dividend:.2f}"
    if dividend_yield is not None:
        merged["dividendYield"] = f"{dividend_yield:.2f}"
    if pe_ratio is not None:
        merged["peRatio"] = f"{pe_ratio:.2f}"
    if beta is not None:
        merged["beta"] = f"{beta:.2f}"
    if profit_margin is not None:
        merged["profitMargins"] = f"{profit_margin:.2f}"
    if latest_revenue and prior_revenue:
        merged["revenueGrowth"] = f"{((latest_revenue - prior_revenue) / prior_revenue * 100):.2f}"
    if market_cap is not None and latest_revenue:
        merged["priceToSales"] = f"{(market_cap / latest_revenue):.2f}"
    if market_cap is not None and latest_equity:
        merged["pbRatio"] = f"{(market_cap / latest_equity):.2f}"
    if us_value_missing(merged.get("forwardPE")):
        merged["forwardPE"] = "N/A"

    one_year_target = nasdaq_labeled_value(summary_data, "OneYrTarget")
    average_volume = nasdaq_labeled_value(summary_data, "AverageVolume") or nasdaq_labeled_value(summary_data, "FiftyDayAvgDailyVol")
    range_52w = nasdaq_labeled_value(summary_data, "FiftTwoWeekHighLow") or nasdaq_labeled_value(summary_data, "fiftyTwoWeekHighLow")
    aum = parse_us_display_number(nasdaq_labeled_value(summary_data, "AUM"))
    expense_ratio = nasdaq_labeled_value(summary_data, "ExpenseRatio")
    if not us_value_missing(one_year_target):
        merged["oneYearTarget"] = str(one_year_target)
    if not us_value_missing(average_volume):
        merged["averageVolume"] = str(average_volume)
    if not us_value_missing(range_52w):
        merged["fiftyTwoWeekRange"] = str(range_52w)
    if aum is not None:
        merged["aum"] = format_us_large_number(aum * 1000)
    if not us_value_missing(expense_ratio):
        merged["expenseRatio"] = str(expense_ratio)

    for key in ("peRatio", "forwardPE", "pbRatio", "priceToSales", "dividendYield", "dividendPerShare", "marketCap", "enterpriseValue", "beta", "profitMargins", "revenueGrowth"):
        merged[key] = display_or_na(merged.get(key))
    if latest_close and pe_ratio and us_value_missing(merged.get("trailingEps")):
        merged["trailingEps"] = f"{(latest_close / pe_ratio):.2f}"
    merged["sourceNote"] = (
        "估值欄位優先使用 Yahoo quote summary；缺漏時以 Nasdaq summary、dividends 與 annual financials 補齊，"
        "Enterprise Value 若無公開值則以市值近似標示。"
    )
    return merged


def build_us_company_profile(symbol: str, summary: dict[str, Any], fallback_name: str = "") -> dict[str, Any]:
    profile = summary.get("assetProfile") or summary.get("summaryProfile") or {}
    fund_profile = summary.get("fundProfile") or {}
    price = summary.get("price") or {}
    long_name = price.get("longName") or price.get("shortName") or fallback_name or symbol
    address_parts = [
        profile.get("address1"),
        profile.get("city"),
        profile.get("state"),
        profile.get("zip"),
        profile.get("country"),
    ]
    return {
        "fullName": str(long_name or symbol),
        "industry": str(profile.get("industry") or fund_profile.get("categoryName") or "--"),
        "sector": str(profile.get("sector") or fund_profile.get("family") or "--"),
        "country": str(profile.get("country") or "--"),
        "website": str(profile.get("website") or ""),
        "telephone": str(profile.get("phone") or "--"),
        "address": ", ".join(str(part) for part in address_parts if part) or "--",
        "employees": format_us_large_number(profile.get("fullTimeEmployees")),
        "businessSummary": str(profile.get("longBusinessSummary") or fund_profile.get("legalType") or "公司摘要目前未取得。"),
        "exchange": str(price.get("exchangeName") or price.get("exchange") or "--"),
    }


def build_us_fallback_company_profile(symbol: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "fullName": str(item.get("name") or symbol),
        "industry": str(item.get("type") or "N/A"),
        "sector": str(item.get("group") or "N/A"),
        "country": "United States",
        "website": "",
        "telephone": "N/A",
        "address": "N/A",
        "employees": "N/A",
        "businessSummary": "公司基本資料暫時無法由 Yahoo quote summary 取得；請使用 Yahoo Finance、SEC EDGAR 或公司 IR 連結核對。",
        "exchange": str(item.get("exchange") or "N/A"),
    }


def merge_us_nasdaq_company_profile(
    profile: dict[str, Any],
    nasdaq: dict[str, Any],
    item: dict[str, Any],
    symbol: str,
) -> dict[str, Any]:
    merged = dict(profile or {})
    company = nasdaq.get("profile") or {}
    summary_data = ((nasdaq.get("summary") or {}).get("data") or {}).get("summaryData") or {}
    company_name = company.get("CompanyName", {}).get("value") if isinstance(company.get("CompanyName"), dict) else None
    if company_name:
        merged["fullName"] = str(company_name)
    if not us_value_missing(nasdaq_labeled_value(summary_data, "Industry")):
        merged["industry"] = str(nasdaq_labeled_value(summary_data, "Industry"))
    if not us_value_missing(company.get("Industry", {}).get("value") if isinstance(company.get("Industry"), dict) else None):
        merged["industry"] = str(company["Industry"]["value"])
    if not us_value_missing(nasdaq_labeled_value(summary_data, "Sector")):
        merged["sector"] = str(nasdaq_labeled_value(summary_data, "Sector"))
    if not us_value_missing(company.get("Sector", {}).get("value") if isinstance(company.get("Sector"), dict) else None):
        merged["sector"] = str(company["Sector"]["value"])
    if not us_value_missing(nasdaq_labeled_value(summary_data, "Exchange")):
        merged["exchange"] = str(nasdaq_labeled_value(summary_data, "Exchange"))
    address = company.get("Address", {}).get("value") if isinstance(company.get("Address"), dict) else None
    if not us_value_missing(address):
        merged["address"] = str(address)
        if "United States" in str(address):
            merged["country"] = "United States"
    phone = company.get("Phone", {}).get("value") if isinstance(company.get("Phone"), dict) else None
    if not us_value_missing(phone):
        merged["telephone"] = str(phone)
    website = company.get("CompanyUrl", {}).get("value") if isinstance(company.get("CompanyUrl"), dict) else None
    if not us_value_missing(website):
        merged["website"] = str(website)
    description = company.get("CompanyDescription", {}).get("value") if isinstance(company.get("CompanyDescription"), dict) else None
    if not us_value_missing(description):
        merged["businessSummary"] = str(description)
    if us_value_missing(merged.get("fullName")):
        merged["fullName"] = str(item.get("name") or symbol)
    for key in ("industry", "sector", "country", "telephone", "address", "employees", "exchange"):
        merged[key] = display_or_na(merged.get(key))
    return merged


def build_us_margin_proxy(summary: dict[str, Any]) -> dict[str, Any]:
    key_stats = summary.get("defaultKeyStatistics") or {}
    shares_short = yahoo_field_raw(key_stats.get("sharesShort"))
    shares_short_prior = yahoo_field_raw(key_stats.get("sharesShortPriorMonth"))
    short_change = None
    if isinstance(shares_short, (int, float)) and isinstance(shares_short_prior, (int, float)):
        short_change = shares_short - shares_short_prior
    return {
        "date": format_us_unix_date(key_stats.get("dateShortInterest")),
        "sourceNote": "美股沒有台股融資融券同口徑資料；此區以 Yahoo Short Interest 作為空方籌碼代理。",
        "shortInterest": format_us_large_number(shares_short),
        "shortInterestPrior": format_us_large_number(shares_short_prior),
        "shortInterestChange": format_us_large_number(short_change),
        "shortRatio": yahoo_field_fmt(key_stats.get("shortRatio")),
        "shortPercentOfFloat": yahoo_field_fmt(key_stats.get("shortPercentOfFloat")),
        "shortPercentOfSharesOutstanding": yahoo_field_fmt(key_stats.get("shortPercentOfSharesOutstanding")),
        "sharesOutstanding": format_us_large_number(key_stats.get("sharesOutstanding")),
        "floatShares": format_us_large_number(key_stats.get("floatShares")),
    }


def build_us_fallback_margin_proxy() -> dict[str, Any]:
    return {
        "date": "N/A",
        "sourceNote": "Short Interest 需 Yahoo quote summary 授權資料；目前保留融資融券分析欄位並提示資料缺口。",
        "shortInterest": "N/A",
        "shortInterestPrior": "N/A",
        "shortInterestChange": "N/A",
        "shortRatio": "N/A",
        "shortPercentOfFloat": "N/A",
        "shortPercentOfSharesOutstanding": "N/A",
        "sharesOutstanding": "N/A",
        "floatShares": "N/A",
    }


def merge_us_nasdaq_margin_proxy(
    margin: dict[str, Any],
    nasdaq: dict[str, Any],
    item: dict[str, Any],
    valuation: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(margin or {})
    short_data = (nasdaq.get("shortInterest") or {}).get("data") or {}
    rows = (((short_data.get("shortInterestTable") or {}).get("rows")) or [])
    latest = rows[0] if rows else {}
    prior = rows[1] if len(rows) > 1 else {}
    latest_interest = parse_us_display_number(latest.get("interest"))
    prior_interest = parse_us_display_number(prior.get("interest"))
    latest_close = parse_us_display_number(item.get("close"))
    market_cap = parse_us_display_number(valuation.get("marketCap"))
    estimated_shares = (market_cap / latest_close) if market_cap and latest_close else None
    if latest:
        merged["date"] = parse_us_date(latest.get("settlementDate"))
        merged["shortInterest"] = format_us_large_number_from_float(latest_interest)
        merged["shortInterestPrior"] = format_us_large_number_from_float(prior_interest)
        merged["shortInterestChange"] = format_us_large_number_from_float(
            latest_interest - prior_interest if latest_interest is not None and prior_interest is not None else None,
        )
        days_to_cover = parse_us_display_number(latest.get("daysToCover"))
        if days_to_cover is not None:
            merged["shortRatio"] = f"{days_to_cover:.2f}"
    if estimated_shares:
        merged["sharesOutstanding"] = format_us_large_number_from_float(estimated_shares, estimated=True)
        if us_value_missing(merged.get("floatShares")):
            merged["floatShares"] = format_us_large_number_from_float(estimated_shares, estimated=True)
    if latest_interest is not None and estimated_shares:
        short_pct = latest_interest / estimated_shares * 100
        merged["shortPercentOfSharesOutstanding"] = f"{short_pct:.2f}%"
        if us_value_missing(merged.get("shortPercentOfFloat")):
            merged["shortPercentOfFloat"] = f"{short_pct:.2f}%"
    for key in ("date", "shortInterest", "shortInterestPrior", "shortInterestChange", "shortRatio", "shortPercentOfFloat", "shortPercentOfSharesOutstanding", "sharesOutstanding", "floatShares"):
        merged[key] = display_or_na(merged.get(key))
    if latest:
        merged["sourceNote"] = (
            "Short Interest 使用 Nasdaq short-interest 公開資料；在外股數與 Short % 若無交易所直接欄位，"
            "以市值 / 最新股價估算作為分析代理。"
        )
    else:
        merged["sourceNote"] = "Nasdaq 未提供此標的 Short Interest；ETF 或非 Nasdaq listed 標的可能不支援空單明細。"
    return merged


def build_us_valuation_history(
    series: list[dict[str, Any]],
    summary: dict[str, Any],
    valuation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    key_stats = summary.get("defaultKeyStatistics") or {}
    summary_detail = summary.get("summaryDetail") or {}
    eps = yahoo_field_raw(key_stats.get("trailingEps"))
    book_value = yahoo_field_raw(key_stats.get("bookValue"))
    dividend_rate = yahoo_field_raw(summary_detail.get("dividendRate"))
    current_close = parse_us_display_number((series or [])[-1].get("close")) if series else None
    valuation = valuation or {}
    pe_ratio = parse_us_display_number(valuation.get("peRatio"))
    pb_ratio = parse_us_display_number(valuation.get("pbRatio"))
    if not isinstance(eps, (int, float)) and current_close and pe_ratio:
        eps = current_close / pe_ratio
    if not isinstance(book_value, (int, float)) and current_close and pb_ratio:
        book_value = current_close / pb_ratio
    if not isinstance(dividend_rate, (int, float)):
        dividend_rate = parse_us_display_number(valuation.get("dividendPerShare"))
    month_end: dict[str, dict[str, Any]] = {}
    for item in series:
        date_text = str(item.get("date") or "")
        if len(date_text) < 7:
            continue
        month_end[date_text[:7]] = item
    history = []
    for item in list(month_end.values())[-6:]:
        close_value = parse_float(str(item.get("close") or ""))
        if close_value is None:
            continue
        pe_ratio = close_value / eps if isinstance(eps, (int, float)) and eps else None
        pb_ratio = close_value / book_value if isinstance(book_value, (int, float)) and book_value else None
        dividend_yield = (dividend_rate / close_value * 100) if isinstance(dividend_rate, (int, float)) and close_value else None
        history.append({
            "date": item.get("date"),
            "close": round(close_value, 2),
            "peRatio": round(pe_ratio, 2) if pe_ratio is not None else None,
            "dividendPerShare": round(dividend_rate, 4) if isinstance(dividend_rate, (int, float)) else None,
            "dividendYield": round(dividend_yield, 2) if dividend_yield is not None else None,
            "pbRatio": round(pb_ratio, 2) if pb_ratio is not None else None,
        })
    return history


def estimate_us_beta_from_series(
    stock_series: list[dict[str, Any]],
    benchmark_series: list[dict[str, Any]],
) -> float | None:
    stock_by_date = {
        str(item.get("date")): parse_us_display_number(item.get("close"))
        for item in stock_series or []
        if item.get("date")
    }
    benchmark_by_date = {
        str(item.get("date")): parse_us_display_number(item.get("close"))
        for item in benchmark_series or []
        if item.get("date")
    }
    dates = sorted(set(stock_by_date) & set(benchmark_by_date))
    stock_returns: list[float] = []
    benchmark_returns: list[float] = []
    for previous_date, current_date in zip(dates, dates[1:]):
        previous_stock = stock_by_date.get(previous_date)
        current_stock = stock_by_date.get(current_date)
        previous_benchmark = benchmark_by_date.get(previous_date)
        current_benchmark = benchmark_by_date.get(current_date)
        if not all(value not in (None, 0) for value in (previous_stock, current_stock, previous_benchmark, current_benchmark)):
            continue
        stock_returns.append((current_stock - previous_stock) / previous_stock)  # type: ignore[operator]
        benchmark_returns.append((current_benchmark - previous_benchmark) / previous_benchmark)  # type: ignore[operator]
    if len(stock_returns) < 60 or len(stock_returns) != len(benchmark_returns):
        return None
    stock_mean = sum(stock_returns) / len(stock_returns)
    benchmark_mean = sum(benchmark_returns) / len(benchmark_returns)
    covariance = sum((s - stock_mean) * (b - benchmark_mean) for s, b in zip(stock_returns, benchmark_returns))
    variance = sum((b - benchmark_mean) ** 2 for b in benchmark_returns)
    if variance == 0:
        return None
    beta = covariance / variance
    return beta if math.isfinite(beta) else None


def estimate_us_beta(symbol: str, stock_series: list[dict[str, Any]]) -> float | None:
    clean_symbol = symbol.upper()
    if clean_symbol in {"SPY", "^GSPC", "VOO", "IVV"}:
        return 1.0
    try:
        benchmark_chart = fetch_yahoo_symbol_chart("SPY", "2y", "1d")
        benchmark_series = build_yahoo_chart_series(benchmark_chart, volume_divisor=1)
    except Exception:  # noqa: BLE001
        return None
    return estimate_us_beta_from_series(stock_series[-520:], benchmark_series[-520:])


def build_us_etf_components(summary: dict[str, Any]) -> dict[str, Any]:
    top_holdings = summary.get("topHoldings") or {}
    holdings = []
    for item in top_holdings.get("holdings") or []:
        raw_weight = yahoo_field_raw(item.get("holdingPercent"))
        weight = raw_weight * 100 if isinstance(raw_weight, (int, float)) and raw_weight <= 1 else raw_weight
        holdings.append({
            "name": item.get("holdingName") or item.get("symbol") or "--",
            "code": item.get("symbol") or "--",
            "weight": round(float(weight), 2) if isinstance(weight, (int, float)) else 0,
        })
    if not holdings:
        return {}
    return {
        "title": "ETF 成分股比例",
        "summary": "Yahoo Finance Top Holdings，實際權重請以發行商公告為準。",
        "holdings": holdings[:12],
        "sourceNote": "資料來源：Yahoo Finance top holdings。",
        "sourceLink": "https://finance.yahoo.com/",
    }


def format_us_ownership_percent(value: Any) -> str:
    raw = yahoo_field_raw(value)
    parsed = parse_us_display_number(raw)
    if parsed is None:
        return "N/A"
    if abs(parsed) <= 1 and "%" not in str(raw or ""):
        parsed *= 100
    return f"{parsed:.2f}%"


def format_yahoo_ownership_date(value: Any) -> str:
    raw = yahoo_field_raw(value)
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, TZ).strftime("%Y-%m-%d")
        except (OSError, ValueError):
            return "--"
    return parse_us_date(raw)


def build_us_ownership_rows(container: dict[str, Any], limit: int = 8) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in (container or {}).get("ownershipList") or []:
        rows.append({
            "name": str(entry.get("organization") or entry.get("name") or "--"),
            "reportDate": format_yahoo_ownership_date(entry.get("reportDate")),
            "pctHeld": format_us_ownership_percent(entry.get("pctHeld")),
            "position": format_us_large_number(entry.get("position")),
            "value": format_us_large_number(entry.get("value")),
        })
    return rows[:limit]


def build_us_insider_transaction_rows(container: dict[str, Any], limit: int = 8) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in (container or {}).get("transactions") or []:
        rows.append({
            "name": str(entry.get("filerName") or entry.get("ownerName") or "--"),
            "date": format_yahoo_ownership_date(entry.get("startDate")),
            "transaction": str(entry.get("transactionText") or entry.get("transactionCode") or "--"),
            "ownership": str(entry.get("ownership") or "--"),
            "shares": format_us_large_number(entry.get("shares")),
            "value": format_us_large_number(entry.get("value")),
        })
    return rows[:limit]


def build_us_insider_holder_rows(container: dict[str, Any], limit: int = 6) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for entry in (container or {}).get("holders") or []:
        rows.append({
            "name": str(entry.get("name") or "--"),
            "relation": str(entry.get("relation") or "--"),
            "latestDate": format_yahoo_ownership_date(entry.get("latestTransDate")),
            "directShares": format_us_large_number(entry.get("positionDirect")),
            "indirectShares": format_us_large_number(entry.get("positionIndirect")),
        })
    return rows[:limit]


def build_us_ownership_trading(summary: dict[str, Any], symbol: str) -> dict[str, Any]:
    key_stats = summary.get("defaultKeyStatistics") or {}
    major_holders = summary.get("majorHoldersBreakdown") or {}
    net_activity = summary.get("netSharePurchaseActivity") or {}
    institution_rows = build_us_ownership_rows(summary.get("institutionOwnership") or {})
    fund_rows = build_us_ownership_rows(summary.get("fundOwnership") or {})
    insider_transactions = build_us_insider_transaction_rows(summary.get("insiderTransactions") or {})
    insider_holders = build_us_insider_holder_rows(summary.get("insiderHolders") or {})
    metrics = {
        "insiderHeldPct": format_us_ownership_percent(
            major_holders.get("insidersPercentHeld") or key_stats.get("heldPercentInsiders"),
        ),
        "institutionsHeldPct": format_us_ownership_percent(
            major_holders.get("institutionsPercentHeld") or key_stats.get("heldPercentInstitutions"),
        ),
        "institutionsFloatPct": format_us_ownership_percent(major_holders.get("institutionsFloatPercentHeld")),
        "institutionsCount": display_or_na(yahoo_field_fmt(major_holders.get("institutionsCount"), 0)),
        "totalInsiderShares": format_us_large_number(net_activity.get("totalInsiderShares")),
        "netInsiderShares": format_us_large_number(net_activity.get("netInfoShares")),
        "netInsiderPct": format_us_ownership_percent(net_activity.get("netPercentInsiderShares")),
        "buyInsiderShares": format_us_large_number(net_activity.get("buyInfoShares")),
        "sellInsiderShares": format_us_large_number(net_activity.get("sellInfoShares")),
        "period": display_or_na(net_activity.get("period")),
    }
    return {
        "date": datetime.now(TZ).strftime("%Y-%m-%d"),
        "metrics": metrics,
        "institutionOwners": institution_rows,
        "fundOwners": fund_rows,
        "insiderTransactions": insider_transactions,
        "insiderHolders": insider_holders,
        "sourceNote": "資料來源：Yahoo Finance quoteSummary major holders / ownership modules；申報仍以 SEC EDGAR 與公司文件為準。",
        "sourceLink": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/holders",
    }


def build_us_fallback_ownership_trading(symbol: str) -> dict[str, Any]:
    return {
        "date": "N/A",
        "metrics": {
            "insiderHeldPct": "N/A",
            "institutionsHeldPct": "N/A",
            "institutionsFloatPct": "N/A",
            "institutionsCount": "N/A",
            "totalInsiderShares": "N/A",
            "netInsiderShares": "N/A",
            "netInsiderPct": "N/A",
            "buyInsiderShares": "N/A",
            "sellInsiderShares": "N/A",
            "period": "N/A",
        },
        "institutionOwners": [],
        "fundOwners": [],
        "insiderTransactions": [],
        "insiderHolders": [],
        "sourceNote": "Yahoo Finance 持有人模組目前未回傳資料；請以 SEC EDGAR 或公司 IR 文件核對。",
        "sourceLink": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/holders",
    }


def merge_us_nasdaq_ownership_trading(
    ownership: dict[str, Any],
    nasdaq: dict[str, Any],
    symbol: str,
) -> dict[str, Any]:
    merged = dict(ownership or {})
    metrics = dict(merged.get("metrics") or {})
    institutional = nasdaq.get("institutionalHoldings") or {}
    insider = nasdaq.get("insiderTrades") or {}
    ownership_summary = institutional.get("ownershipSummary") or {}
    holdings_transactions = institutional.get("holdingsTransactions") or {}
    holdings_table = (holdings_transactions.get("table") or {})
    holdings_rows = holdings_table.get("rows") or []
    outstanding_millions = parse_us_display_number(nasdaq_labeled_value(ownership_summary, "ShareoutstandingTotal"))
    outstanding_shares = outstanding_millions * 1_000_000 if outstanding_millions is not None else None

    institutional_pct = nasdaq_labeled_value(ownership_summary, "SharesOutstandingPCT")
    if not us_value_missing(institutional_pct):
        metrics["institutionsHeldPct"] = format_us_ownership_percent(institutional_pct)
    total_value = parse_us_display_number(nasdaq_labeled_value(ownership_summary, "TotalHoldingsValue"))
    if total_value is not None:
        metrics["totalInstitutionalValue"] = format_us_large_number_from_float(total_value * 1_000_000)
    if outstanding_shares is not None:
        metrics["sharesOutstanding"] = format_us_large_number_from_float(outstanding_shares)
    if not us_value_missing(holdings_transactions.get("totalRecords")):
        metrics["institutionsCount"] = str(holdings_transactions.get("totalRecords")).strip()

    institution_rows: list[dict[str, str]] = []
    for row in holdings_rows[:12]:
        shares_held = parse_us_display_number(row.get("sharesHeld"))
        market_value = parse_us_display_number(row.get("marketValue"))
        held_pct = (shares_held / outstanding_shares * 100) if shares_held is not None and outstanding_shares else None
        institution_rows.append({
            "name": str(row.get("ownerName") or "--"),
            "reportDate": parse_us_date(row.get("date")),
            "pctHeld": f"{held_pct:.2f}%" if held_pct is not None else "N/A",
            "position": format_us_large_number_from_float(shares_held),
            "value": format_us_large_number_from_float(market_value * 1_000 if market_value is not None else None),
            "changeShares": format_us_large_number_from_float(parse_us_display_number(row.get("sharesChange"))),
            "changePct": display_or_na(row.get("sharesChangePCT")),
        })
    if institution_rows:
        merged["institutionOwners"] = institution_rows

    activity_rows: list[dict[str, str]] = []
    for table_name in ("activePositions", "newSoldOutPositions"):
        table = institutional.get(table_name) or {}
        for row in table.get("rows") or []:
            activity_rows.append({
                "name": str(row.get("positions") or "--"),
                "reportDate": parse_us_date(table.get("asOf")) if table.get("asOf") else "--",
                "pctHeld": display_or_na(row.get("holders")),
                "position": display_or_na(row.get("shares")),
                "value": "持有人數 / 股數",
            })
    if activity_rows:
        merged["positionActivity"] = activity_rows[:8]

    share_rows = ((insider.get("numberOfSharesTraded") or {}).get("rows")) or []
    for row in share_rows:
        label = str(row.get("insiderTrade") or "").lower()
        if "bought" in label:
            metrics["buyInsiderShares"] = display_or_na(row.get("months3"))
        elif "sold" in label:
            metrics["sellInsiderShares"] = display_or_na(row.get("months3"))
        elif "net activity" in label:
            metrics["netInsiderShares"] = display_or_na(row.get("months3"))

    transaction_rows = (((insider.get("transactionTable") or {}).get("table") or {}).get("rows")) or []
    insider_transactions: list[dict[str, str]] = []
    insider_holders_by_name: dict[str, dict[str, str]] = {}
    for row in transaction_rows[:12]:
        name = str(row.get("insider") or "--")
        own_type = str(row.get("ownType") or "--")
        shares_held = display_or_na(row.get("sharesHeld"))
        insider_transactions.append({
            "name": name,
            "date": parse_us_date(row.get("lastDate")),
            "transaction": str(row.get("transactionType") or "--"),
            "ownership": own_type,
            "shares": display_or_na(row.get("sharesTraded")),
            "value": display_or_na(row.get("lastPrice")),
            "relation": str(row.get("relation") or "--"),
        })
        holder = insider_holders_by_name.setdefault(name, {
            "name": name,
            "relation": str(row.get("relation") or "--"),
            "latestDate": parse_us_date(row.get("lastDate")),
            "directShares": "N/A",
            "indirectShares": "N/A",
        })
        if own_type.lower() == "direct":
            holder["directShares"] = shares_held
        elif own_type.lower() == "indirect":
            holder["indirectShares"] = shares_held
    if insider_transactions:
        merged["insiderTransactions"] = insider_transactions
        merged["insiderHolders"] = list(insider_holders_by_name.values())[:8]

    merged["metrics"] = {key: display_or_na(value) for key, value in metrics.items()}
    if institution_rows or activity_rows or insider_transactions:
        merged["date"] = datetime.now(TZ).strftime("%Y-%m-%d")
        merged["sourceNote"] = (
            "資料來源：Nasdaq institutional-holdings / insider-trades 公開 API；"
            "Yahoo holders 模組若取得授權則作為補充，正式申報仍以 SEC EDGAR 為準。"
        )
        merged["sourceLink"] = f"https://www.nasdaq.com/market-activity/stocks/{quote(symbol.lower(), safe='')}/institutional-holdings"
    return merged


def build_us_market_symbol_detail(spec: dict[str, Any]) -> dict[str, Any]:
    item = build_global_market_item(spec)
    if item.get("error"):
        return item
    data_symbol = str(item.get("dataSymbol") or item.get("symbol") or spec.get("symbol") or "")
    try:
        chart = fetch_yahoo_symbol_chart(data_symbol, "5y", "1d")
        long_series = build_yahoo_chart_series(chart, volume_divisor=1)
        if len(long_series) >= len(item.get("series") or []):
            item["series"] = long_series
    except Exception:  # noqa: BLE001
        pass

    summary: dict[str, Any] = {}
    company_news: list[dict[str, Any]] = []
    nasdaq_supplement: dict[str, Any] = {}
    is_etf_hint = item.get("group") == "美股 ETF" or "ETF" in str(item.get("type") or "").upper()
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            "summary": executor.submit(fetch_yahoo_quote_summary, data_symbol),
            "news": executor.submit(fetch_yahoo_us_symbol_news, data_symbol, 6),
            "nasdaq": executor.submit(fetch_nasdaq_us_supplement, data_symbol, is_etf_hint),
        }
        for key, future in futures.items():
            try:
                if key == "summary":
                    summary = future.result(timeout=12)
                elif key == "news":
                    company_news = future.result(timeout=10)
                else:
                    nasdaq_supplement = future.result(timeout=16)
            except Exception:  # noqa: BLE001
                if key == "summary":
                    summary = {}
                elif key == "news":
                    company_news = []
                else:
                    nasdaq_supplement = {}

    valuation = build_us_valuation(summary) if summary else build_us_fallback_valuation(item)
    valuation = merge_us_nasdaq_valuation(valuation, nasdaq_supplement, item)
    if us_value_missing(valuation.get("beta")):
        beta_estimate = estimate_us_beta(data_symbol, item.get("series") or [])
        if beta_estimate is not None:
            valuation["beta"] = f"{beta_estimate:.2f} (估)"
    company_profile = (
        build_us_company_profile(data_symbol, summary, item.get("name") or data_symbol)
        if summary
        else build_us_fallback_company_profile(data_symbol, item)
    )
    company_profile = merge_us_nasdaq_company_profile(company_profile, nasdaq_supplement, item, data_symbol)
    margin_proxy = build_us_margin_proxy(summary) if summary else build_us_fallback_margin_proxy()
    margin_proxy = merge_us_nasdaq_margin_proxy(margin_proxy, nasdaq_supplement, item, valuation)
    ownership_trading = (
        build_us_ownership_trading(summary, data_symbol)
        if summary
        else build_us_fallback_ownership_trading(data_symbol)
    )
    ownership_trading = merge_us_nasdaq_ownership_trading(ownership_trading, nasdaq_supplement, data_symbol)
    valuation_history = build_us_valuation_history(item.get("series") or [], summary or {}, valuation)
    etf_components = build_us_etf_components(summary) if summary else {}
    nasdaq_asset_class = str(((nasdaq_supplement.get("summary") or {}).get("data") or {}).get("assetClass") or "")
    quote_type = str(((summary.get("price") or {}).get("quoteType") or nasdaq_asset_class or item.get("group") or "")).upper()
    is_etf = "ETF" in quote_type or "FUND" in quote_type or item.get("group") == "美股 ETF"
    return {
        **item,
        "group": "美股 ETF" if is_etf else item.get("group") or "美股個股",
        "type": item.get("type") or ("ETF" if is_etf else "美股個股"),
        "detailMode": "full",
        "historyRange": "5y",
        "valuation": valuation,
        "valuationHistory": valuation_history,
        "companyProfile": company_profile,
        "companyNews": company_news,
        "marginTrading": margin_proxy,
        "ownershipTrading": ownership_trading,
        "etfComponents": etf_components if is_etf else {},
        "isEtf": is_etf,
        "newsLinks": {
            "yahoo": f"https://finance.yahoo.com/quote/{quote(data_symbol, safe='')}/news",
            "profile": f"https://finance.yahoo.com/quote/{quote(data_symbol, safe='')}/profile",
            "sec": f"https://www.sec.gov/edgar/search/#/q={quote(data_symbol, safe='')}",
        },
    }


def validate_global_market_item(item: dict[str, Any], category: str) -> dict[str, Any]:
    source_info = ASSET_CATEGORY_SOURCE_INFO.get(category, {})
    if item.get("error"):
        return {
            "status": "failed",
            "primarySource": source_info.get("primary", "Yahoo Finance 歷史行情"),
            "referenceSource": source_info.get("reference", ""),
            "checks": {"history": False, "ohlc": False, "closeMatch": False, "fresh": False},
        }
    series = item.get("series") or []
    close = parse_float(str(item.get("close") or ""))
    latest = series[-1] if series else {}
    latest_close = parse_float(str(latest.get("close") or ""))
    history_ok = len(series) >= 20
    close_match = (
        close is not None
        and latest_close is not None
        and abs(close - latest_close) <= max(0.01, abs(latest_close) * 0.001)
    )
    ohlc_ok = True
    for row in series[-20:]:
        open_value = parse_float(str(row.get("open") or ""))
        high_value = parse_float(str(row.get("high") or ""))
        low_value = parse_float(str(row.get("low") or ""))
        row_close = parse_float(str(row.get("close") or ""))
        if None in {open_value, high_value, low_value, row_close}:
            ohlc_ok = False
            break
        if high_value < max(open_value, row_close) or low_value > min(open_value, row_close):
            ohlc_ok = False
            break
    fresh = False
    latest_date = str(latest.get("date") or item.get("date") or "")
    try:
        fresh = abs((datetime.now(TZ).date() - datetime.strptime(latest_date, "%Y-%m-%d").date()).days) <= 12
    except ValueError:
        fresh = False
    status = "verified" if history_ok and close_match and ohlc_ok and fresh else "limited"
    return {
        "status": status,
        "primarySource": source_info.get("primary", "Yahoo Finance 歷史行情"),
        "referenceSource": source_info.get("reference", ""),
        "referenceUrl": source_info.get("referenceUrl", ""),
        "checks": {
            "history": history_ok,
            "ohlc": ohlc_ok,
            "closeMatch": close_match,
            "fresh": fresh,
        },
    }


def apply_treasury_secondary_validation(items: list[dict[str, Any]], treasury_curve: dict[str, Any]) -> int:
    mapping = {"^IRX": "3 Mo", "US2Y": "2 Yr", "^FVX": "5 Yr", "^TNX": "10 Yr", "^TYX": "30 Yr"}
    treasury_yields = treasury_curve.get("yields") or {}
    matched = 0
    for item in items:
        maturity = mapping.get(str(item.get("symbol") or "").upper())
        reference_value = treasury_yields.get(maturity) if maturity else None
        if reference_value is None:
            continue
        yahoo_value = parse_float(str(item.get("close") or ""))
        if yahoo_value is None:
            continue
        normalized_value = min((yahoo_value, yahoo_value / 10, yahoo_value * 10), key=lambda value: abs(value - reference_value))
        difference = abs(normalized_value - reference_value)
        secondary_status = "matched" if difference <= 0.5 else "review"
        item.setdefault("verification", {})["secondary"] = {
            "source": treasury_curve.get("source"),
            "date": treasury_curve.get("date"),
            "referenceValue": reference_value,
            "difference": round(difference, 3),
            "status": secondary_status,
        }
        if secondary_status == "matched":
            matched += 1
    return matched


def normalize_futures_yahoo_uncovered_links(item: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(item, dict):
        return item
    quote_source_url = str(item.get("quoteSourceUrl") or "")
    source_link = str(item.get("sourceLink") or "")
    has_yahoo_future_quote = (
        item.get("quoteStatus") == "yahoo-live"
        or bool(item.get("yahooFutureCode"))
        or quote_source_url.rstrip("/") == YAHOO_TW_FUTURE_URL
        or source_link.rstrip("/") == YAHOO_TW_FUTURE_URL
    )
    if has_yahoo_future_quote:
        item["quoteSourceUrl"] = YAHOO_TW_FUTURE_UNCOVERED_URL
        if not source_link or source_link.rstrip("/") == YAHOO_TW_FUTURE_URL or item.get("quoteStatus") == "yahoo-live":
            item["sourceLink"] = YAHOO_TW_FUTURE_UNCOVERED_URL
    return item


def build_global_market_payload(
    category: str,
    limit: int | None = None,
    option_source: str = "auto",
    option_underlying: str = TAIWAN_OPTION_DEFAULT_PRODUCT,
) -> dict[str, Any]:
    spec = GLOBAL_MARKET_CATEGORIES[category]
    catalog_items = [enrich_global_market_spec(item, category) for item in spec["items"]]
    selected_specs = catalog_items[:limit] if limit else catalog_items
    items: list[dict[str, Any]] = []
    # Item fetches are independent I/O-bound Yahoo Finance / TAIFEX lookups (each already
    # throttled at its own external-source layer where that source needs it, e.g. the TAIFEX
    # form-query semaphore), so a wider pool here mainly cuts wall-clock wait time.
    max_workers = min(6 if category == "options" else 8, len(selected_specs))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(build_global_market_item, item) for item in selected_specs]
        for future in as_completed(futures):
            items.append(future.result())

    item_order = {item["symbol"]: index for index, item in enumerate(selected_specs)}
    items.sort(key=lambda item: item_order.get(item.get("symbol"), 999))
    if category == "futures":
        items = [normalize_futures_yahoo_uncovered_links(item) for item in items]
    for item in items:
        item["verification"] = validate_global_market_item(item, category)
    treasury_curve = fetch_us_treasury_yield_curve() if category == "bonds" else {}
    secondary_matched = apply_treasury_secondary_validation(items, treasury_curve) if treasury_curve else 0
    usable = [item for item in items if not item.get("error") and parse_float(str(item.get("close") or "")) is not None]
    verified_count = sum(1 for item in items if (item.get("verification") or {}).get("status") == "verified")
    limited_count = sum(1 for item in items if (item.get("verification") or {}).get("status") == "limited")
    advancers = sum(1 for item in usable if (parse_float(str(item.get("pct") or "")) or 0) > 0)
    decliners = sum(1 for item in usable if (parse_float(str(item.get("pct") or "")) or 0) < 0)
    avg_pct_values = [parse_float(str(item.get("pct") or "")) for item in usable]
    avg_pct_values = [value for value in avg_pct_values if value is not None]
    avg_pct = sum(avg_pct_values) / len(avg_pct_values) if avg_pct_values else None
    strongest = max(usable, key=lambda item: parse_float(str(item.get("pct") or "")) or -999999, default=None)
    weakest = min(usable, key=lambda item: parse_float(str(item.get("pct") or "")) or 999999, default=None)
    region_breakdown = summarize_asset_regions(items)
    catalog_region_breakdown = summarize_asset_regions(catalog_items)
    payload = {
        "category": category,
        "title": spec["title"],
        "kicker": spec["kicker"],
        "subtitle": spec["subtitle"],
        "source": ASSET_CATEGORY_SOURCE_INFO.get(category, {}).get("primary", "Yahoo Finance 線上資料"),
        "sourceInfo": ASSET_CATEGORY_SOURCE_INFO.get(category, {}),
        "macroSchema": GLOBAL_MACRO_ASSET_SCHEMA,
        "updatedAt": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "catalogCount": len(catalog_items),
        "loadedCount": len(items),
        "loadLimit": limit,
        "regionBreakdown": region_breakdown,
        "catalogRegionBreakdown": catalog_region_breakdown,
        "validation": {
            "verifiedCount": verified_count,
            "limitedCount": limited_count,
            "failedCount": len(items) - len(usable),
            "primary": ASSET_CATEGORY_SOURCE_INFO.get(category, {}).get("primary", "Yahoo Finance 歷史行情"),
            "reference": ASSET_CATEGORY_SOURCE_INFO.get(category, {}).get("reference", ""),
            "referenceUrl": ASSET_CATEGORY_SOURCE_INFO.get(category, {}).get("referenceUrl", ""),
            "secondaryMatchedCount": secondary_matched,
            "treasuryCurve": treasury_curve if category == "bonds" else {},
        },
        "summary": {
            "count": len(usable),
            "advancers": advancers,
            "decliners": decliners,
            "avgPct": format_percent(avg_pct) if avg_pct is not None else "--",
            "strongest": strongest["name"] if strongest else "--",
            "strongestPct": strongest.get("pct") if strongest else "--",
            "weakest": weakest["name"] if weakest else "--",
            "weakestPct": weakest.get("pct") if weakest else "--",
        },
        "items": items,
    }
    if category == "us-stocks":
        try:
            payload["news"] = fetch_us_market_overview_news(8)
            if "News" not in str(payload.get("source") or ""):
                payload["source"] = f"{payload['source']} + Yahoo Finance News"
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("US market overview news payload fetch failed", exc_info=exc)
            payload["news"] = []
    if category in {"futures", "options"}:
        payload["v1Scope"] = "domestic_derivatives"
        payload["v1ProductStatus"] = v1_product_status(
            [apply_taifex_defaults(item, TAIFEX_FUTURES_DAILY_URL, TAIFEX_OPTIONS_DAILY_URL) for item in TAIWAN_FUTURES_V1],
            [apply_taifex_defaults(item, TAIFEX_FUTURES_DAILY_URL, TAIFEX_OPTIONS_DAILY_URL) for item in TAIWAN_OPTIONS_V1],
        )
        if category == "futures":
            payload["futuresMarketBreakdown"] = summarize_futures_market_scopes(catalog_items, items)
    if category == "options":
        try:
            payload["taiwanOptionChain"] = fetch_txo_option_chain(source=option_source, underlying=option_underlying)
        except Exception as exc:  # noqa: BLE001
            product = get_taiwan_option_product(option_underlying)
            LOGGER.exception("%s option chain payload fetch failed", product["symbol"], exc_info=exc)
            payload["taiwanOptionChain"] = {
                "underlying": product["symbol"],
                "name": product["name"],
                "error": PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE,
                "source": {
                    "primary": "TAIFEX / Yahoo 台灣選擇權",
                    "primaryUrl": TAIFEX_OPTIONS_DAILY_URL,
                    "secondaryUrl": build_yahoo_taiwan_option_url(product["symbol"]),
                },
            }
    try:
        if category == "futures":
            DERIVATIVES_STORE.record_futures_payload(payload)
        elif category == "options":
            option_chain = payload.get("taiwanOptionChain") or {}
            DERIVATIVES_STORE.record_option_chain(option_chain, str(payload.get("updatedAt") or ""))
            if option_chain.get("analysis"):
                DERIVATIVES_STORE.record_ai_report(str(option_chain.get("underlying") or option_underlying), option_chain["analysis"], str(payload.get("updatedAt") or ""))
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Failed to persist derivatives payload", exc_info=exc)
    return payload


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
US_ETF_POPULAR_YAHOO_SYMBOLS = [
    "SPY", "QQQ", "VOO", "IVV", "VTI", "IWM", "SPLG", "DIA",
    "SCHD", "VIG", "VYM", "JEPI", "JEPQ", "DGRW",
    "XLK", "XLF", "XLV", "XLE", "XLY", "XLI", "XLU", "XLP", "XLB", "XLRE",
    "SMH", "SOXX", "XBI", "KRE", "VNQ", "IYR",
    "EFA", "EEM", "VEA", "VWO", "IEFA", "IEMG", "VXUS",
    "TLT", "IEF", "SHY", "BND", "AGG", "LQD", "HYG",
    "GLD", "IAU", "SLV", "USO",
    "IBIT", "BITO", "GBTC",
    "TQQQ", "SQQQ", "SOXL", "SOXS",
    "ARKK", "ARKW", "BOTZ", "CIBR", "TAN", "ICLN", "LIT",
]
US_ETF_POPULAR_FALLBACKS = {
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust",
    "VOO": "Vanguard S&P 500 ETF",
    "IVV": "iShares Core S&P 500 ETF",
    "VTI": "Vanguard Total Stock Market ETF",
    "IWM": "iShares Russell 2000 ETF",
    "SPLG": "SPDR Portfolio S&P 500 ETF",
    "DIA": "SPDR Dow Jones Industrial Average ETF",
    "SCHD": "Schwab U.S. Dividend Equity ETF",
    "VIG": "Vanguard Dividend Appreciation ETF",
    "VYM": "Vanguard High Dividend Yield ETF",
    "JEPI": "JPMorgan Equity Premium Income ETF",
    "JEPQ": "JPMorgan Nasdaq Equity Premium Income ETF",
    "DGRW": "WisdomTree U.S. Quality Dividend Growth Fund",
    "XLK": "Technology Select Sector SPDR Fund",
    "XLF": "Financial Select Sector SPDR Fund",
    "XLV": "Health Care Select Sector SPDR Fund",
    "XLE": "Energy Select Sector SPDR Fund",
    "XLY": "Consumer Discretionary Select Sector SPDR Fund",
    "XLI": "Industrial Select Sector SPDR Fund",
    "XLU": "Utilities Select Sector SPDR Fund",
    "XLP": "Consumer Staples Select Sector SPDR Fund",
    "XLB": "Materials Select Sector SPDR Fund",
    "XLRE": "Real Estate Select Sector SPDR Fund",
    "SMH": "VanEck Semiconductor ETF",
    "SOXX": "iShares Semiconductor ETF",
    "XBI": "SPDR S&P Biotech ETF",
    "KRE": "SPDR S&P Regional Banking ETF",
    "VNQ": "Vanguard Real Estate ETF",
    "IYR": "iShares U.S. Real Estate ETF",
    "EFA": "iShares MSCI EAFE ETF",
    "EEM": "iShares MSCI Emerging Markets ETF",
    "VEA": "Vanguard FTSE Developed Markets ETF",
    "VWO": "Vanguard FTSE Emerging Markets ETF",
    "IEFA": "iShares Core MSCI EAFE ETF",
    "IEMG": "iShares Core MSCI Emerging Markets ETF",
    "VXUS": "Vanguard Total International Stock ETF",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "IEF": "iShares 7-10 Year Treasury Bond ETF",
    "SHY": "iShares 1-3 Year Treasury Bond ETF",
    "BND": "Vanguard Total Bond Market ETF",
    "AGG": "iShares Core U.S. Aggregate Bond ETF",
    "LQD": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
    "HYG": "iShares iBoxx $ High Yield Corporate Bond ETF",
    "GLD": "SPDR Gold Shares",
    "IAU": "iShares Gold Trust",
    "SLV": "iShares Silver Trust",
    "USO": "United States Oil Fund",
    "IBIT": "iShares Bitcoin Trust ETF",
    "BITO": "ProShares Bitcoin Strategy ETF",
    "GBTC": "Grayscale Bitcoin Trust ETF",
    "TQQQ": "ProShares UltraPro QQQ",
    "SQQQ": "ProShares UltraPro Short QQQ",
    "SOXL": "Direxion Daily Semiconductor Bull 3X Shares",
    "SOXS": "Direxion Daily Semiconductor Bear 3X Shares",
    "ARKK": "ARK Innovation ETF",
    "ARKW": "ARK Next Generation Internet ETF",
    "BOTZ": "Global X Robotics & Artificial Intelligence ETF",
    "CIBR": "First Trust Nasdaq Cybersecurity ETF",
    "TAN": "Invesco Solar ETF",
    "ICLN": "iShares Global Clean Energy ETF",
    "LIT": "Global X Lithium & Battery Tech ETF",
}


def build_us_etf_quote_specs(directory_items: list[dict[str, Any]], quote_limit: int, prefer_directory_first: bool = False) -> list[dict[str, Any]]:
    if quote_limit <= 0:
        return []
    by_symbol: dict[str, dict[str, Any]] = {}
    for item in [*directory_items, *filter_us_etf_items(US_MARKET_SEARCH_UNIVERSE)]:
        symbol = str(item.get("symbol") or "").upper()
        if symbol and symbol not in by_symbol:
            by_symbol[symbol] = normalize_us_market_search_item(item)
    for symbol, name in US_ETF_POPULAR_FALLBACKS.items():
        by_symbol.setdefault(symbol, normalize_us_market_search_item({
            "symbol": symbol,
            "name": name,
            "quoteType": "ETF",
            "exchange": "NYSE Arca / Nasdaq",
            "source": "熱門美股 ETF 內建清單",
        }))

    selected: list[dict[str, Any]] = []
    selected_symbols: set[str] = set()
    if prefer_directory_first:
        for item in directory_items:
            symbol = str(item.get("symbol") or "").upper()
            if symbol and symbol not in selected_symbols:
                selected.append(normalize_us_market_search_item(item))
                selected_symbols.add(symbol)
            if len(selected) >= quote_limit:
                break
    for symbol in US_ETF_POPULAR_YAHOO_SYMBOLS:
        item = by_symbol.get(symbol)
        if item and symbol not in selected_symbols:
            selected.append(item)
            selected_symbols.add(symbol)
        if len(selected) >= quote_limit:
            break
    if len(selected) < quote_limit:
        for item in directory_items:
            symbol = str(item.get("symbol") or "").upper()
            if symbol and symbol not in selected_symbols:
                selected.append(normalize_us_market_search_item(item))
                selected_symbols.add(symbol)
            if len(selected) >= quote_limit:
                break

    specs = []
    for item in selected[:quote_limit]:
        symbol = normalize_us_symbol_for_yahoo(str(item.get("symbol") or ""))
        if not symbol:
            continue
        specs.append(enrich_global_market_spec({
            "symbol": symbol,
            "name": item.get("name") or symbol,
            "type": item.get("type") or "ETF",
            "group": "美股 ETF",
            "region": "美國",
            "market": "美股ETF",
            "exchange": item.get("exchange") or "NYSE Arca / Nasdaq",
            "dataSource": "Yahoo Finance 美股 ETF 行情",
            "referenceSource": item.get("source") or "美股 ETF 線上清單",
            "sourceUrl": f"https://finance.yahoo.com/quote/{quote(symbol)}",
            "metricLabel": "成交量",
        }, "us-stocks"))
    return specs


def build_us_etf_center_payload(query: str = "", directory_limit: int = 7000, quote_limit: int = 48, refresh: bool = False) -> dict[str, Any]:
    directory_items, directory_total, directory_source, directory_error = fetch_us_etf_directory_items(query, directory_limit, refresh)
    quote_specs = build_us_etf_quote_specs(directory_items, quote_limit, bool(query.strip()))
    quote_items: list[dict[str, Any]] = []
    if quote_specs:
        with ThreadPoolExecutor(max_workers=min(6, len(quote_specs))) as executor:
            futures = [executor.submit(build_global_market_item, spec) for spec in quote_specs]
            for future in as_completed(futures):
                quote_items.append(future.result())
        order = {item["symbol"]: index for index, item in enumerate(quote_specs)}
        quote_items.sort(key=lambda item: order.get(item.get("symbol"), 999))

    usable = [item for item in quote_items if not item.get("error") and parse_float(str(item.get("close") or "")) is not None]
    pct_values = [parse_float(str(item.get("pct") or "")) for item in usable]
    pct_values = [value for value in pct_values if value is not None]
    avg_pct = sum(pct_values) / len(pct_values) if pct_values else None
    strongest = max(usable, key=lambda item: parse_float(str(item.get("pct") or "")) or -999999, default=None)
    weakest = min(usable, key=lambda item: parse_float(str(item.get("pct") or "")) or 999999, default=None)
    volume_leader = max(usable, key=lambda item: parse_float(str(item.get("volume") or "")) or -1, default=None)
    quote_source = "Yahoo Finance 美股 ETF 行情" if quote_specs else ""
    source_parts = [directory_source, quote_source]
    return {
        "category": "us-etf",
        "title": "美股ETF",
        "kicker": "US ETF Center",
        "subtitle": "整合美股 ETF 官方上市清單與 Yahoo Finance 美股 ETF 行情。",
        "query": query,
        "source": " + ".join(part for part in source_parts if part),
        "sourceInfo": {
            "primary": directory_source,
            "quote": quote_source,
            "reference": "Nasdaq Trader Symbol Directory / NYSE Listings Directory / Yahoo Finance",
        },
        "updatedAt": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "directory": {
            "query": query,
            "kind": "etf",
            "instrumentType": "EXCHANGE_TRADED_FUND",
            "group": "美股 ETF",
            "total": directory_total,
            "count": len(directory_items),
            "returned": len(directory_items),
            "source": directory_source,
            "error": directory_error,
            "results": directory_items,
        },
        "catalogCount": directory_total,
        "loadedCount": len(quote_items),
        "loadLimit": quote_limit,
        "summary": {
            "directoryCount": len(directory_items),
            "directoryTotal": directory_total,
            "quoteCount": len(usable),
            "advancers": sum(1 for item in usable if (parse_float(str(item.get("pct") or "")) or 0) > 0),
            "decliners": sum(1 for item in usable if (parse_float(str(item.get("pct") or "")) or 0) < 0),
            "avgPct": format_percent(avg_pct) if avg_pct is not None else "--",
            "strongest": strongest.get("symbol") if strongest else "--",
            "strongestPct": strongest.get("pct") if strongest else "--",
            "weakest": weakest.get("symbol") if weakest else "--",
            "weakestPct": weakest.get("pct") if weakest else "--",
            "volumeLeader": volume_leader.get("symbol") if volume_leader else "--",
        },
        "items": quote_items,
        "error": directory_error,
    }



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
