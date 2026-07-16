from __future__ import annotations

import copy
import csv
import io
import json
import logging
import math
import os
import re
import threading
import time
import zipfile
import xml.etree.ElementTree as ET
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, Response, abort, jsonify, redirect, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from derivatives.analytics import build_basis_payload, enrich_futures_ai_decision, enrich_option_ai_decision
from derivatives.ai import build_unavailable_ai_analysis as build_derivatives_unavailable_ai_analysis
from derivatives.catalog import TAIWAN_FUTURES_V1, TAIWAN_OPTIONS_V1, apply_taifex_defaults, v1_product_status
from derivatives.futures import build_source_pending_market_item, is_source_pending_product
from derivatives.institution import build_institution_payload_from_rows, build_pending_institution_payload, normalize_institution_row, parse_institution_csv
from derivatives.options import build_unavailable_option_chain as build_derivatives_unavailable_option_chain
from derivatives_store import DerivativesStore
from security import (
    add_security_headers,
    enforce_api_rate_limit,
    is_authorized_derivatives_admin,
    _urlopen_with_ssl_fallback,
)
from market_config import (
    ASSET_CATEGORY_SOURCE_INFO,
    ASSET_REGION_ORDER,
    ASSET_STATIC_FILES,
    CBOE_OPTIONS_BASE,
    EXCLUDED_SECTOR_SOURCE_NAMES,
    FRED_GRAPH_CSV_BASE,
    GLOBAL_MACRO_ASSET_SCHEMA,
    GLOBAL_MARKET_CACHE_SECONDS,
    GLOBAL_MARKET_CATEGORIES,
    GLOBAL_MARKET_DEFAULT_LOAD_LIMIT,
    GLOBAL_MARKET_MAX_LOAD_LIMIT,
    GOOGLE_NEWS_RSS_BASE,
    INDEX_DISPLAY_NAMES,
    INTERNATIONAL_INDEX_SPECS,
    LISTED_SECTOR_INDEX_ORDER,
    LISTED_SECTOR_INDEX_SPECS,
    NASDAQ_API_BASE,
    NASDAQ_LISTED_URL,
    NASDAQ_OTHER_LISTED_URL,
    NASDAQ_USER_AGENT,
    NYSE_QUOTES_FILTER_URL,
    PAGE_ROUTES,
    ROOT_STATIC_FILES,
    SECTOR_INDEX_DISPLAY_NAMES,
    SECTOR_INDEX_LOOKUP,
    SUPPORTED_CHART_INTERVALS,
    TAIFEX_FUTURES_DAILY_URL,
    TAIFEX_OPTIONS_CHAIN_CACHE_SECONDS,
    TAIFEX_OPTIONS_DAILY_URL,
    TAIFEX_OPTIONS_PC_RATIO_URL,
    TARGET_INDEX_NAMES,
    TDCC_HOLDING_CACHE_SECONDS,
    TDCC_HOLDING_DISTRIBUTION_FALLBACK_URL,
    TDCC_HOLDING_DISTRIBUTION_URL,
    TPEX_OPENAPI_BASE,
    TRADING_ECONOMICS_TAIWAN_10Y_URL,
    TWSE_BASE,
    TWSE_MARGIN_URL,
    TWSE_OPENAPI_BASE,
    US_TREASURY_YIELD_CURVE_CSV_URL,
    US_LISTED_UNIVERSE_CACHE_SECONDS,
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
BUNDLED_CACHE_FILE = BASE_DIR / "twse-cache.json"
CACHE_FILE = Path(os.environ.get("MARKET_PULSE_CACHE_FILE", str(BUNDLED_CACHE_FILE)))
DERIVATIVES_STORE = DerivativesStore(os.environ.get("DERIVATIVES_DB_PATH", str(BASE_DIR / "derivatives-platform.sqlite3")))
DERIVATIVES_STORE.initialize()
LOG_LEVEL = str(os.environ.get("MARKET_PULSE_LOG_LEVEL") or "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
LOGGER = logging.getLogger("market_pulse")
CACHE_VERSION = 13
try:
    TZ = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:
    TZ = timezone(timedelta(hours=8))
UPDATE_INTERVAL_SECONDS = 60
SECTOR_CHART_CACHE_SECONDS = 300
SECTOR_CHART_TRADE_MONTHS = 3
SECTOR_CHART_TRADE_TIMEOUT_SECONDS = 4
STOCK_HISTORY_RECENT_MONTHS = 3
STOCK_HISTORY_TIMEOUT_SECONDS = 8
STOCK_HISTORY_MAX_MONTHS = 480
STOCK_HISTORY_EMPTY_STOP_MONTHS = 24
STOCK_HISTORY_FETCH_BATCH_SIZE = 12
SECTOR_HISTORY_TRADING_DAYS = 30
WEIGHTED_INDEX_HISTORY_TRADING_DAYS = 480
EXTERNAL_TEXT_CACHE_SECONDS = 5 * 60
GLOBAL_MARKET_ITEM_CACHE_SECONDS = 5 * 60
TREASURY_YIELD_CURVE_CACHE_SECONDS = 6 * 60 * 60
US_OPTIONS_CHAIN_CACHE_SECONDS = 5 * 60
YAHOO_TW_STOCK_RESOURCE_CACHE_SECONDS = 5 * 60
TWSE_COMPANY_INDUSTRY_CACHE_SECONDS = 12 * 60 * 60
SECTOR_FUND_FLOW_CACHE_SECONDS = 10 * 60
TWSE_INDUSTRY_CODE_NAMES = {
    "01": "水泥",
    "02": "食品",
    "03": "塑膠",
    "04": "紡織纖維",
    "05": "電機機械",
    "06": "電器電纜",
    "08": "玻璃陶瓷",
    "09": "造紙",
    "10": "鋼鐵",
    "11": "橡膠",
    "12": "汽車",
    "14": "建材營造",
    "15": "航運",
    "16": "觀光餐旅",
    "17": "金融保險",
    "18": "貿易百貨",
    "20": "其他",
    "21": "化學",
    "22": "生技醫療",
    "23": "油電燃氣",
    "24": "半導體",
    "25": "電腦及週邊設備",
    "26": "光電",
    "27": "通信網路",
    "28": "電子零組件",
    "29": "電子通路",
    "30": "資訊服務",
    "31": "其他電子",
    "32": "文化創意",
    "33": "農業科技",
    "34": "電子商務",
    "35": "綠能環保",
    "36": "數位雲端",
    "37": "運動休閒",
    "38": "居家生活",
}


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

PUBLIC_CACHE_ERROR_MESSAGE = "背景資料更新暫時無法完成，請稍後再試"
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


cache_lock = threading.RLock()
cache_refresh_lock = threading.Lock()
cache_flight_lock = threading.Lock()
cache_flights: dict[str, threading.Event] = {}
CACHE_FLIGHT_WAIT_SECONDS = 120
background_updater_lock = threading.Lock()
background_updater_started = False
penny_sector_recommendation_lock = threading.Lock()
penny_sector_recommendation_cache: dict[str, Any] = {}
PENNY_SECTOR_RECOMMENDATION_CACHE_SECONDS = 30 * 60
# TAIFEX's HTML query-form endpoints (DailyMarketReport / futures data download) are not a
# real API and are fragile under bursty concurrent traffic, so calls to them are throttled
# to a small bounded number in flight (with a short pacing sleep per call) instead of being
# fired without limit. This keeps the site a well-behaved client of a real, live source
# rather than caching or fabricating data to hide slow/blocked responses.
taifex_open_interest_lock = threading.Semaphore(2)
TAIFEX_FORM_QUERY_CONCURRENCY = 2
# Coalesces concurrent requests for the same option-chain cache key (e.g. a page that fires
# /api/options/chain and /api/ai-analysis for the same underlying at once) so only one of them
# runs the ~12-day TAIFEX scan; the rest wait for and reuse that real result instead of each
# triggering their own redundant scan.
taifex_options_chain_inflight: dict[str, threading.Event] = {}
taifex_options_chain_inflight_lock = threading.Lock()
TAIFEX_FUTURES_DAILY_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
TAIFEX_OPTIONS_DAILY_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportOpt"
TAIFEX_OPTIONS_PRODUCT_DAILY_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/Daily_OPT"
TAIFEX_SSF_LIST_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/SSFLists"
TAIFEX_SSO_LIST_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/SSOLists"
TAIFEX_INSTITUTION_FUTURES_DETAIL_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
TAIFEX_INSTITUTION_OPTIONS_DETAIL_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfOptionsContractsBytheDate"
TAIFEX_UNDERLYING_LIST_CACHE_SECONDS = 6 * 60 * 60
TAIFEX_STOCK_DERIVATIVE_AGGREGATE_CACHE_SECONDS = 15 * 60
TAIFEX_INSTITUTION_DETAIL_CACHE_SECONDS = 15 * 60
PRODUCT_TO_TAIFEX_INSTITUTION_CONTRACT = {
    "TX": "臺股期貨",
    "MTX": "小型臺指期貨",
    "TMF": "微型臺指期貨",
    "TE": "電子期貨",
    "TF": "金融期貨",
    "SOF": "櫃買指數期貨",
    "STF": "股票期貨",
    "ETF-F": "ETF期貨",
    "TXO": "臺指選擇權",
    "STO": "股票選擇權",
    "ETO": "ETF選擇權",
}
TAIFEX_FUTURES_DATA_DOWNLOAD_URL = "https://www.taifex.com.tw/cht/3/futDataDown"
TAIFEX_FUTURES_PREVIOUS30_SALES_URL = "https://www.taifex.com.tw/cht/3/futPrevious30DaysSalesData"
TAIFEX_FUTURES_DAILY_TICK_CSV_BASE = "https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV"
YAHOO_TW_FUTURE_URL = "https://tw.stock.yahoo.com/future"
YAHOO_TW_FUTURE_UNCOVERED_URL = "https://tw.stock.yahoo.com/future/futures_uncovered.html"
YAHOO_TW_FUTURE_CACHE_SECONDS = 60
YAHOO_TW_OPTION_URL = "https://tw.stock.yahoo.com/future/options.html"
YAHOO_TW_OPTION_WTXO_URL = f"{YAHOO_TW_OPTION_URL}?opmr=optionfull&opcm=WTXO"
YAHOO_TW_OPTION_CACHE_SECONDS = 60
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
TAIFEX_FUTURE_MONTH_CODE_TO_MONTH = {
    "F": "01",
    "G": "02",
    "H": "03",
    "J": "04",
    "K": "05",
    "M": "06",
    "N": "07",
    "Q": "08",
    "U": "09",
    "V": "10",
    "X": "11",
    "Z": "12",
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
cache_data: dict[str, Any] = {
    "site_data": None,
    "all_stocks": [],
    "market_date": None,
    "cached_at": None,
    "last_error": None,
    "stock_details": {},
    "sector_charts": {},
    "global_markets": {},
    "international_market_indexes": {"stored_at": 0.0, "payload": []},
    "global_market_items": {},
    "external_text": {},
    "treasury_yield_curve_rows": {"stored_at": 0.0, "rows": []},
    "us_options_chains": {},
    "yahoo_tw_option_chain": {},
    "yahoo_tw_stock_resources": {},
    "us_etf_center": {},
    "taifex_options_chain": {},
    "us_listed_universe": {"stored_at": 0.0, "items": [], "totals": {}},
    "shareholder_distributions": {},
    "shareholder_distributions_stored_at": 0.0,
    "live_search_dedup": {},
    "twse_company_industries": {"stored_at": 0.0, "items": {}},
    "sector_fund_flow": {},
    "yahoo_tw_future_quotes": {"stored_at": 0.0, "items": {}},
    "yahoo_tw_future_technical_candles": {},
}
LIVE_SEARCH_DEDUP_SECONDS = 8.0
YAHOO_OPTIONS_CHAIN_BASE = "https://query1.finance.yahoo.com/v7/finance/options"
YAHOO_OPTIONS_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
YAHOO_OPTIONS_PAGE_BASE = "https://finance.yahoo.com/quote"
YAHOO_OPTIONS_CHAIN_CACHE_SECONDS = 5 * 60
YAHOO_OPTIONS_CRUMB_CACHE_SECONDS = 45 * 60
BARCHART_FUTURES_OPTIONS_PAGE_BASE = "https://www.barchart.com/futures/quotes"
BARCHART_CORE_QUOTES_URL = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
BARCHART_OPTIONS_CHAIN_CACHE_SECONDS = 5 * 60
BARCHART_FUTURES_OPTIONS_ROOTS = {
    "GC=F": "GC",
    "SI=F": "SI",
    "PL=F": "PL",
    "PA=F": "PA",
    "HG=F": "HG",
    "CL=F": "CL",
    "NG=F": "NG",
    "RB=F": "RB",
    "HO=F": "HO",
    "ZS=F": "ZS",
    "ZC=F": "ZC",
    "ZW=F": "ZW",
    "KC=F": "KC",
    "CC=F": "CC",
    "SB=F": "SB",
    "CT=F": "CT",
    "LE=F": "LE",
    "HE=F": "HE",
    "ZQ=F": "ZQ",
    "ZT=F": "ZT",
    "ZF=F": "ZF",
    "ZN=F": "ZN",
    "ZB=F": "ZB",
    "E6=F": "E6",
    "J6=F": "J6",
    "B6=F": "B6",
    "A6=F": "A6",
    "D6=F": "D6",
}
DERIBIT_OPTIONS_SUMMARY_URL = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
DERIBIT_OPTIONS_CHAIN_CACHE_SECONDS = 60
DERIBIT_OPTIONS_CURRENCY_BY_SYMBOL = {
    "DERIBIT_BTC": "BTC",
    "DERIBIT_ETH": "ETH",
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
}
BYBIT_OPTIONS_TICKERS_URL = "https://api.bybit.com/v5/market/tickers"
BYBIT_OPTIONS_CHAIN_CACHE_SECONDS = 60
BYBIT_OPTIONS_BASE_COIN_BY_SYMBOL = {
    "BYBIT_SOL": "SOL",
    "BYBIT_XRP": "XRP",
    "SOL-USD": "SOL",
    "XRP-USD": "XRP",
}
_yahoo_options_cookie_jar = CookieJar()
_yahoo_options_opener = build_opener(HTTPCookieProcessor(_yahoo_options_cookie_jar))
_yahoo_options_crumb: dict[str, Any] = {"value": "", "stored_at": 0.0}


def read_memory_cache(bucket: str, key: str, ttl_seconds: int | float) -> Any | None:
    now = time.time()
    with cache_lock:
        cached = cache_data.get(bucket, {}).get(key)
    if cached and now - float(cached.get("stored_at") or 0) < ttl_seconds:
        return cached.get("payload")
    return None


def write_memory_cache(bucket: str, key: str, payload: Any) -> None:
    with cache_lock:
        cache_data.setdefault(bucket, {})[key] = {"stored_at": time.time(), "payload": payload}


def claim_cache_flight(key: str) -> tuple[bool, threading.Event]:
    """Elect one request to refresh a cache key while concurrent requests wait."""
    with cache_flight_lock:
        event = cache_flights.get(key)
        if event is not None:
            return False, event
        event = threading.Event()
        cache_flights[key] = event
        return True, event


def finish_cache_flight(key: str, event: threading.Event) -> None:
    with cache_flight_lock:
        if cache_flights.get(key) is event:
            cache_flights.pop(key, None)
            event.set()


def should_cache_external_text(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in {"www.taifex.com.tw", "tw.stock.yahoo.com", "home.treasury.gov", "fred.stlouisfed.org", "tradingeconomics.com"}


def live_search_dedup_key(query: str, requested_market: str, limit: int) -> str:
    return f"{query.strip().lower()}:{normalize_market_request(requested_market)}:{limit}"


def get_recent_live_search_result(query: str, requested_market: str, limit: int):
    key = live_search_dedup_key(query, requested_market, limit)
    now = time.time()
    with cache_lock:
        item = cache_data["live_search_dedup"].get(key)
        if item and now - float(item.get("stored_at") or 0) <= LIVE_SEARCH_DEDUP_SECONDS:
            return item.get("payload")
    return None


def remember_live_search_result(
    query: str,
    requested_market: str,
    limit: int,
    payload: tuple[list[dict[str, Any]], str, str | None, list[str]],
) -> tuple[list[dict[str, Any]], str, str | None, list[str]]:
    key = live_search_dedup_key(query, requested_market, limit)
    now = time.time()
    with cache_lock:
        cache_data["live_search_dedup"] = {
            stored_key: stored_value
            for stored_key, stored_value in cache_data["live_search_dedup"].items()
            if now - float(stored_value.get("stored_at") or 0) <= LIVE_SEARCH_DEDUP_SECONDS
        }
        cache_data["live_search_dedup"][key] = {"stored_at": now, "payload": payload}
    return payload


def build_stock_search_url(date_str: str, keyword: str) -> str:
    params = {"response": "json", "date": date_str, "keyword": keyword}
    return f"{TWSE_BASE}/rwd/zh/afterTrading/STOCK_DAY_AVG?{urlencode(params)}"


def build_tpex_openapi_url(endpoint: str) -> str:
    return f"{TPEX_OPENAPI_BASE}/{endpoint}"


def serialize_treasury_yield_curve_cache(cached: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = cached if cached is not None else (cache_data.get("treasury_yield_curve_rows") or {})
    serialized_rows = []
    for date_value, row in cached.get("rows") or []:
        if isinstance(date_value, datetime):
            date_text = date_value.strftime("%Y-%m-%d")
        else:
            date_text = str(date_value or "")
        if date_text and isinstance(row, dict):
            serialized_rows.append({"date": date_text, "row": row})
    return {
        "stored_at": float(cached.get("stored_at") or 0),
        "rows": serialized_rows,
    }


def deserialize_treasury_yield_curve_cache(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    rows: list[tuple[datetime, dict[str, str]]] = []
    for item in payload.get("rows") or []:
        if not isinstance(item, dict) or not isinstance(item.get("row"), dict):
            continue
        date_text = str(item.get("date") or item["row"].get("Date") or "").strip()
        parsed_date = None
        for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                parsed_date = datetime.strptime(date_text, date_format)
                break
            except ValueError:
                continue
        if parsed_date is not None:
            rows.append((parsed_date, item["row"]))
    if not rows:
        return None
    return {
        "stored_at": float(payload.get("stored_at") or 0),
        "rows": sorted(rows, key=lambda item: item[0]),
    }


def load_disk_cache() -> bool:
    try:
        cache_source = CACHE_FILE if CACHE_FILE.exists() else BUNDLED_CACHE_FILE
        if not cache_source.exists():
            return False
        payload = json.loads(cache_source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Disk cache load skipped for %s: %s", cache_source if "cache_source" in locals() else CACHE_FILE, exc)
        return False

    if not isinstance(payload, dict):
        LOGGER.warning("Disk cache load skipped for %s: expected a JSON object", cache_source)
        return False

    cache_version = payload.get("cache_version")
    if cache_version is not None and cache_version != CACHE_VERSION:
        return False
    with cache_lock:
        cache_data["site_data"] = sanitize_site_data(payload.get("site_data"))
        cache_data["all_stocks"] = payload.get("all_stocks", [])
        cache_data["market_date"] = payload.get("market_date")
        cache_data["cached_at"] = payload.get("cached_at")
        treasury_rows = deserialize_treasury_yield_curve_cache(payload.get("treasury_yield_curve_rows"))
        if treasury_rows:
            cache_data["treasury_yield_curve_rows"] = treasury_rows
    return True


def build_disk_cache_snapshot() -> dict[str, Any]:
    """Capture one internally consistent cache generation before writing it to disk."""
    with cache_lock:
        treasury_rows = copy.deepcopy(cache_data.get("treasury_yield_curve_rows") or {})
        return {
            "cache_version": CACHE_VERSION,
            "site_data": copy.deepcopy(cache_data["site_data"]),
            "all_stocks": copy.deepcopy(cache_data["all_stocks"]),
            "market_date": cache_data["market_date"],
            "cached_at": cache_data["cached_at"],
            "treasury_yield_curve_rows": serialize_treasury_yield_curve_cache(treasury_rows),
        }


def save_disk_cache(snapshot: dict[str, Any] | None = None) -> None:
    # Serialize outside the shared cache lock. The snapshot is already a single generation.
    payload = snapshot if snapshot is not None else build_disk_cache_snapshot()
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = CACHE_FILE.with_suffix(f"{CACHE_FILE.suffix}.tmp")
    try:
        temporary_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary_file.replace(CACHE_FILE)
    except OSError as exc:
        LOGGER.exception("Disk cache save failed for %s", CACHE_FILE, exc_info=exc)
        try:
            temporary_file.unlink(missing_ok=True)
        except OSError:
            pass


def sanitize_site_data(site_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not site_data:
        return site_data

    sectors = site_data.get("sectors")
    if isinstance(sectors, list):
        site_data = dict(site_data)
        site_data["sectors"] = [
            item
            for item in sectors
            if item.get("sourceName") not in EXCLUDED_SECTOR_SOURCE_NAMES and item.get("name") not in EXCLUDED_SECTOR_SOURCE_NAMES
        ]
    yahoo_groups = site_data.get("yahooSectorGroups")
    if isinstance(yahoo_groups, dict):
        site_data = dict(site_data)
        sanitized_groups: dict[str, list[dict[str, Any]]] = {}
        for group_key, cards in yahoo_groups.items():
            sanitized_cards = []
            for card in cards if isinstance(cards, list) else []:
                sanitized_card = dict(card)
                sanitized_card.pop("trades", None)
                series = dict(sanitized_card.get("comparisonSeries") or {})
                series["day"] = [
                    {key: value for key, value in point.items() if key != "trades"}
                    for point in series.get("day", [])
                ]
                sanitized_card["comparisonSeries"] = series
                sanitized_cards.append(sanitized_card)
            sanitized_groups[group_key] = sanitized_cards
        site_data["yahooSectorGroups"] = sanitized_groups
    return site_data


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


BOOTSTRAP_STOCK_KEYS = (
    "code",
    "name",
    "market",
    "marketLabel",
    "securityType",
    "industry",
    "volume",
    "trades",
    "turnover",
    "open",
    "high",
    "low",
    "close",
    "change",
    "pct",
    "bid",
    "bidVolume",
    "ask",
    "askVolume",
    "tone",
)

SECTOR_SITE_DATA_KEYS = (
    "snapshotDate",
    "institutionDate",
    "activityDate",
    "intradayDate",
    "cachedAt",
    "stockCount",
    "tpexStockCount",
    "tpexEtfCount",
    "tpexStockDate",
    "yahooOtcDate",
    "yahooEmergingDate",
    "yahooSectorDates",
    "marketStats",
    "marketVolatility",
    "marketInternationalIndexes",
    "sourceLinks",
    "marketOverview",
    "sectors",
    "sectorFundFlow",
    "tpexHighlights",
    "yahooSectorGroups",
    "yahooSectorCatalog",
)

SEARCH_SITE_DATA_KEYS = (
    "snapshotDate",
    "cachedAt",
    "stockCount",
    "tpexStockCount",
    "tpexEtfCount",
    "tpexStockDate",
)


def slim_stock_for_bootstrap(stock: dict[str, Any]) -> dict[str, Any]:
    return {
        key: stock[key]
        for key in BOOTSTRAP_STOCK_KEYS
        if key in stock
    }


def build_stocks_view(stocks: list[dict[str, Any]], view: str) -> list[dict[str, Any]]:
    if view == "sectors":
        return []
    return [slim_stock_for_bootstrap(stock) for stock in stocks]


def build_site_data_view(site_data: dict[str, Any] | None, view: str) -> dict[str, Any] | None:
    if not site_data:
        return site_data
    if view == "sectors":
        return {
            key: site_data[key]
            for key in SECTOR_SITE_DATA_KEYS
            if key in site_data
        }
    if view == "search":
        return {
            key: site_data[key]
            for key in SEARCH_SITE_DATA_KEYS
            if key in site_data
        }
    return site_data


def taipei_now() -> datetime:
    return datetime.now(TZ)


def fetch_json(url: str, timeout: int = 30) -> Any:
    headers = {"User-Agent": USER_AGENT}
    if "twse.com.tw" in url:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Connection": "close",
        }
    req = Request(url, headers=headers)
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        return json.loads(response.read().decode("utf-8"))
def fetch_nasdaq_json(path: str, timeout: int = 12) -> Any:
    url = path if path.startswith("http") else f"{NASDAQ_API_BASE}{path}"
    req = Request(url, headers={
        "User-Agent": NASDAQ_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    })
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], timeout: int = 30, headers: dict[str, str] | None = None) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
        **(headers or {}),
    }
    req = Request(url, data=body, headers=request_headers, method="POST")
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_compact_roc_date(value: str | None) -> str | None:
    cleaned = re.sub(r"\D", "", (value or "").strip())
    if len(cleaned) != 7:
        return None

    try:
        roc_year = int(cleaned[:3])
        month = int(cleaned[3:5])
        day = int(cleaned[5:7])
        return datetime(roc_year + 1911, month, day).strftime("%Y%m%d")
    except ValueError:
        return None


def parse_twse_table_date(value: str | None) -> str | None:
    cleaned = re.sub(r"\D", "", (value or "").strip())
    if len(cleaned) == 7:
        try:
            roc_year = int(cleaned[:3])
            month = int(cleaned[3:5])
            day = int(cleaned[5:7])
            return datetime(roc_year + 1911, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None
    if len(cleaned) == 8:
        try:
            year = int(cleaned[:4])
            month = int(cleaned[4:6])
            day = int(cleaned[6:8])
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def fetch_yahoo_tpex_etfs(timeout: int = 8) -> dict[str, str]:
    page = fetch_text(YAHOO_TPEX_ETF_URL, timeout=timeout)
    etfs: dict[str, str] = {}
    link_pattern = re.compile(r'href="https://tw\.stock\.yahoo\.com/quote/([^"]+)\.TWO"', re.IGNORECASE)
    name_pattern = re.compile(r'<div class="[^"]*Lh\(20px\)[^"]*">([^<]+)</div>', re.IGNORECASE)

    for match in link_pattern.finditer(page):
        code = match.group(1).strip()
        nearby = page[match.end() : match.end() + 600]
        name_match = name_pattern.search(nearby)
        if name_match:
            etfs[code] = unescape(name_match.group(1)).strip()
    return etfs


def classify_tpex_security(code: str, yahoo_etf_codes: set[str]) -> tuple[str | None, str | None]:
    if code in yahoo_etf_codes or re.fullmatch(r"00[A-Z0-9]{4}", code, re.IGNORECASE):
        return "ETF", "上櫃ETF"
    if re.fullmatch(r"\d{4}A?", code, re.IGNORECASE):
        return "STOCK", "上櫃個股"
    return None, None


def fetch_tpex_mainboard_quotes(timeout: int = 10) -> tuple[list[dict[str, Any]], str | None]:
    payload = fetch_json(build_tpex_openapi_url("tpex_mainboard_quotes"), timeout=timeout)
    if not isinstance(payload, list):
        return [], None

    snapshot_date = parse_compact_roc_date(str(payload[0].get("Date"))) if payload else None
    return payload, snapshot_date


def build_yahoo_chart_url(code: str, range_name: str, interval: str, market: str = "TPEx") -> str:
    params = urlencode({"range": range_name, "interval": interval, "includePrePost": "false"})
    suffix = "TWO" if market.upper() == "TPEX" else "TW"
    return f"{YAHOO_CHART_BASE}/{code}.{suffix}?{params}"


def fetch_yahoo_chart(
    code: str,
    range_name: str = "5d",
    interval: str = "1d",
    market: str = "TPEx",
) -> dict[str, Any] | None:
    payload = fetch_json(build_yahoo_chart_url(code, range_name, interval, market), timeout=10)
    results = ((payload or {}).get("chart") or {}).get("result") or []
    return results[0] if results else None


def fetch_yahoo_symbol_chart(symbol: str, range_name: str = "2y", interval: str = "1d") -> dict[str, Any] | None:
    params = urlencode({"range": range_name, "interval": interval, "includePrePost": "false"})
    payload = fetch_json(f"{YAHOO_CHART_BASE}/{quote(symbol, safe='')}?{params}", timeout=10)
    results = ((payload or {}).get("chart") or {}).get("result") or []
    return results[0] if results else None


def build_yahoo_chart_series(
    chart: dict[str, Any] | None,
    intraday: bool = False,
    volume_divisor: float = 1000,
) -> list[dict[str, str]]:
    if not chart:
        return []
    timestamps = chart.get("timestamp") or []
    quotes = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quotes.get("open") or []
    highs = quotes.get("high") or []
    lows = quotes.get("low") or []
    closes = quotes.get("close") or []
    volumes = quotes.get("volume") or []
    series: list[dict[str, str]] = []
    for index, timestamp in enumerate(timestamps):
        close_value = closes[index] if index < len(closes) else None
        if close_value is None:
            continue
        trade_time = datetime.fromtimestamp(timestamp, TZ)
        raw_volume = volumes[index] if index < len(volumes) else None
        volume_value = (raw_volume / volume_divisor) if raw_volume is not None else None
        item = {
            "open": f"{(opens[index] if index < len(opens) and opens[index] is not None else close_value):.2f}",
            "high": f"{(highs[index] if index < len(highs) and highs[index] is not None else close_value):.2f}",
            "low": f"{(lows[index] if index < len(lows) and lows[index] is not None else close_value):.2f}",
            "close": f"{close_value:.2f}",
            "volume": format_whole_number(volume_value) if volume_value is not None else "--",
        }
        if volume_value is not None:
            item["volumeValue"] = str(volume_value)
        if intraday:
            item["time"] = trade_time.strftime("%H:%M")
        else:
            item["date"] = trade_time.strftime("%Y-%m-%d")
        series.append(item)
    return series


def fetch_market_volatility_indicator(weighted_series: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """Fetch Yahoo Finance ^VIX and expose it as the site's volatility index."""
    chart = fetch_yahoo_symbol_chart("^VIX", "3mo", "1d")
    series = build_yahoo_chart_series(chart, volume_divisor=1)
    closes = [parse_float(str(item.get("close"))) for item in series]
    closes = [value for value in closes if value is not None]
    if len(closes) < 2:
        return None

    latest = closes[-1]
    previous = closes[-2]
    change = latest - previous if previous is not None else None
    pct = (change / previous * 100) if previous not in (None, 0) and change is not None else None
    if latest < 15:
        level = "非理性樂觀"
        summary = "大盤通常處於牛市或緩漲波段，但須留意市場過度樂觀，可能隱含賣壓風險。"
        tone = "up"
    elif latest < 20:
        level = "常態穩定"
        summary = "市場預期變動不大，大盤走勢相對平穩，屬於較健康的交易環境。"
        tone = "up"
    elif latest < 30:
        level = "警戒焦慮"
        summary = "市場波動開始加劇，大盤可能面臨修正或多空交戰，投資人應注意風險。"
        tone = "neutral"
    elif latest >= 40:
        level = "極度恐慌"
        summary = "大盤通常伴隨非理性大規模拋售，但也暗示市場可能短期內出現落底反彈契機。"
        tone = "down"
    else:
        level = "高恐慌"
        summary = "市場恐慌情緒偏高，短線波動可能劇烈，台股操作宜降低追價與槓桿。"
        tone = "down"

    return {
        "name": "VIX",
        "symbol": "^VIX",
        "label": "VIX 指數",
        "value": f"{latest:.2f}",
        "change": format_signed(change) if change is not None else "--",
        "pct": format_percent(pct) if pct is not None else "--",
        "level": level,
        "summary": summary,
        "tone": tone,
        "date": series[-1].get("date") if series else None,
        "series": [
            {"date": item.get("date"), "value": item.get("close")}
            for item in series[-45:]
            if item.get("date") and item.get("close")
        ],
        "sourceLink": "https://finance.yahoo.com/quote/%5EVIX/",
        "sourceNote": "Yahoo Finance ^VIX，反映美股 S&P 500 選擇權隱含波動率。",
    }


def _refresh_international_market_indexes() -> list[dict[str, Any]]:
    indexes: list[dict[str, Any]] = []
    with cache_lock:
        cached_market_indexes = list((cache_data.get("site_data") or {}).get("marketInternationalIndexes") or [])
    cached_by_key = {
        str(item.get("key") or ""): item
        for item in cached_market_indexes
        if isinstance(item, dict) and item.get("key")
    }

    def fallback_index_item(spec: dict[str, Any]) -> dict[str, Any]:
        cached = cached_by_key.get(str(spec.get("key") or ""))
        cached_series = cached.get("series") if isinstance(cached, dict) else None
        if isinstance(cached, dict) and isinstance(cached_series, list) and len(cached_series) >= 2:
            return {
                **cached,
                "sourceStatus": "cached",
                "sourceNote": "即時 Yahoo Finance 歷史資料暫時無法取得，先沿用上一筆有效快取。",
            }
        return {
            "key": spec["key"],
            "name": spec["name"],
            "symbol": spec["symbol"],
            "resolvedSymbol": spec["symbol"],
            "market": spec.get("market"),
            "proxy": spec.get("proxy"),
            "value": "--",
            "change": "--",
            "pct": "--",
            "open": "--",
            "previousClose": "--",
            "high": "--",
            "low": "--",
            "volume": "--",
            "volumeValue": None,
            "tone": "flat",
            "date": None,
            "series": [],
            "sourceStatus": "unavailable",
            "sourceNote": "Yahoo Finance 即時歷史資料暫時無法取得，保留目錄避免前端選項遺失。",
            "sourceLink": f"https://finance.yahoo.com/quote/{quote(spec['symbol'], safe='')}/",
        }

    def fetch_one(spec: dict[str, Any]) -> dict[str, Any] | None:
        symbols = [spec["symbol"], *spec.get("fallbackSymbols", [])]
        selected_symbol = ""
        series: list[dict[str, Any]] = []
        for symbol in symbols:
            try:
                chart = fetch_yahoo_symbol_chart(symbol, "1y", "1d")
                series = build_yahoo_chart_series(chart, volume_divisor=1)
            except Exception:  # noqa: BLE001
                series = []
            if len(series) >= 2:
                selected_symbol = symbol
                break

        closes = [parse_float(str(item.get("close"))) for item in series]
        closes = [value for value in closes if value is not None]
        if not closes:
            return fallback_index_item(spec)
        latest = closes[-1]
        previous = closes[-2] if len(closes) >= 2 else None
        change = latest - previous if previous is not None else None
        pct = (change / previous * 100) if previous not in (None, 0) and change is not None else None
        resolved_symbol = selected_symbol or spec["symbol"]
        latest_bar = series[-1] if series else {}
        latest_open = parse_float(str(latest_bar.get("open") or ""))
        latest_high = parse_float(str(latest_bar.get("high") or ""))
        latest_low = parse_float(str(latest_bar.get("low") or ""))
        latest_volume = parse_float(str(latest_bar.get("volumeValue") or latest_bar.get("volume") or ""))
        return {
            "key": spec["key"],
            "name": spec["name"],
            "symbol": spec["symbol"],
            "resolvedSymbol": resolved_symbol,
            "market": spec["market"],
            "proxy": spec.get("proxy"),
            "value": f"{latest:.2f}",
            "change": format_signed(change) if change is not None else "--",
            "pct": format_percent(pct) if pct is not None else "--",
            "open": f"{latest_open:.2f}" if latest_open is not None else "--",
            "previousClose": f"{previous:.2f}" if previous is not None else "--",
            "high": f"{latest_high:.2f}" if latest_high is not None else "--",
            "low": f"{latest_low:.2f}" if latest_low is not None else "--",
            "volume": format_whole_number(latest_volume) if latest_volume is not None else "--",
            "volumeValue": str(latest_volume) if latest_volume is not None else None,
            "tone": detect_tone(change or 0.0),
            "date": series[-1].get("date") if series else None,
            "series": [
                {"date": item.get("date"), "value": item.get("close")}
                for item in series[-180:]
                if item.get("date") and item.get("close")
            ],
            "sourceStatus": "live",
            "sourceLink": f"https://finance.yahoo.com/quote/{quote(resolved_symbol, safe='')}/",
        }

    with ThreadPoolExecutor(max_workers=min(8, len(INTERNATIONAL_INDEX_SPECS))) as executor:
        futures = [executor.submit(fetch_one, spec) for spec in INTERNATIONAL_INDEX_SPECS]
        for future in as_completed(futures):
            try:
                item = future.result()
            except Exception:  # noqa: BLE001
                item = None
            if item:
                indexes.append(item)

    by_key = {
        str(item.get("key") or ""): item
        for item in indexes
        if isinstance(item, dict) and item.get("key")
    }
    complete_indexes = [
        by_key.get(str(spec["key"])) or fallback_index_item(spec)
        for spec in INTERNATIONAL_INDEX_SPECS
    ]
    order = {spec["key"]: index for index, spec in enumerate(INTERNATIONAL_INDEX_SPECS)}
    return sorted(complete_indexes, key=lambda item: order.get(str(item.get("key")), 999))


def fetch_international_market_indexes() -> list[dict[str, Any]]:
    now = time.time()
    with cache_lock:
        cached = cache_data.get("international_market_indexes") or {}
        cached_payload = cached.get("payload") or []
        if cached_payload and now - float(cached.get("stored_at") or 0) < GLOBAL_MARKET_CACHE_SECONDS:
            return copy.deepcopy(cached_payload)

    is_leader, flight = claim_cache_flight("international-market-indexes")
    if not is_leader:
        flight.wait(CACHE_FLIGHT_WAIT_SECONDS)
        with cache_lock:
            refreshed = cache_data.get("international_market_indexes") or {}
            refreshed_payload = refreshed.get("payload") or []
        if refreshed_payload:
            return copy.deepcopy(refreshed_payload)
        raise RuntimeError("國際指數同步未完成，請稍後再試")

    try:
        indexes = _refresh_international_market_indexes()
        with cache_lock:
            cache_data["international_market_indexes"] = {
                "stored_at": time.time(),
                "payload": copy.deepcopy(indexes),
            }
        return indexes
    finally:
        finish_cache_flight("international-market-indexes", flight)


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


def fetch_text(url: str, timeout: int = 30) -> str:
    cache_key = f"GET:{url}"
    if should_cache_external_text(url):
        cached = read_memory_cache("external_text", cache_key, EXTERNAL_TEXT_CACHE_SECONDS)
        if cached is not None:
            return str(cached)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        raw = response.read()
        content_type = str(response.headers.get("Content-Type") or "").lower()
    encoding = "cp950" if "ms950" in content_type or "big5" in content_type else "utf-8"
    text = raw.decode(encoding, errors="ignore")
    if should_cache_external_text(url):
        write_memory_cache("external_text", cache_key, text)
    return text


def fetch_binary(url: str, timeout: int = 30) -> bytes:
    cache_key = f"BIN:{url}"
    if should_cache_external_text(url):
        cached = read_memory_cache("external_text", cache_key, EXTERNAL_TEXT_CACHE_SECONDS)
        if cached is not None:
            return bytes(cached)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        payload = response.read()
    if should_cache_external_text(url):
        write_memory_cache("external_text", cache_key, payload)
    return payload


def fetch_form_text(url: str, fields: dict[str, str], timeout: int = 30) -> str:
    encoded_fields = urlencode(sorted((str(key), str(value)) for key, value in fields.items()))
    cache_key = f"FORM:{url}:{encoded_fields}"
    if should_cache_external_text(url):
        cached = read_memory_cache("external_text", cache_key, EXTERNAL_TEXT_CACHE_SECONDS)
        if cached is not None:
            return str(cached)
    payload = encoded_fields.encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        raw = response.read()
        content_type = str(response.headers.get("Content-Type") or "").lower()
    encoding = "cp950" if "ms950" in content_type or "big5" in content_type else "utf-8"
    text = raw.decode(encoding, errors="ignore")
    if should_cache_external_text(url):
        write_memory_cache("external_text", cache_key, text)
    return text


def fetch_tdcc_holding_distribution_text(timeout: int = 12) -> str:
    attempts = (
        TDCC_HOLDING_DISTRIBUTION_URL,
        TDCC_HOLDING_DISTRIBUTION_URL,
        TDCC_HOLDING_DISTRIBUTION_FALLBACK_URL,
    )
    errors: list[str] = []
    last_exc: Exception | None = None
    for index, url in enumerate(attempts):
        try:
            return fetch_text(url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            errors.append(f"{url}: {exc!r}")
            if index < len(attempts) - 1:
                time.sleep(0.5)
    raise RuntimeError("TDCC holding distribution unavailable after retries: " + " | ".join(errors)) from last_exc


def build_yahoo_macro_snapshot(symbol: str) -> dict[str, Any] | None:
    chart = fetch_yahoo_symbol_chart(symbol, "3mo", "1d")
    series = build_yahoo_chart_series(chart, volume_divisor=1)
    closes = [parse_float(str(item.get("close") or "")) for item in series]
    closes = [value for value in closes if value is not None]
    if len(closes) < 2:
        return None
    latest = closes[-1]
    previous = closes[-2]
    change = latest - previous
    pct = change / previous * 100 if previous else None
    return {
        "symbol": symbol,
        "value": latest,
        "previous": previous,
        "change": change,
        "pct": pct,
        "date": series[-1].get("date") if series else None,
        "sourceLink": f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/",
    }


def fetch_twse_margin_summary() -> dict[str, Any] | None:
    rows = fetch_json(TWSE_MARGIN_URL, timeout=15)
    if not isinstance(rows, list) or not rows:
        return None
    financing_current = 0.0
    financing_previous = 0.0
    short_current = 0.0
    short_previous = 0.0
    valid_rows = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        current_financing = parse_float(str(row.get("融資今日餘額") or ""))
        previous_financing = parse_float(str(row.get("融資前日餘額") or ""))
        current_short = parse_float(str(row.get("融券今日餘額") or ""))
        previous_short = parse_float(str(row.get("融券前日餘額") or ""))
        if current_financing is None and previous_financing is None:
            continue
        financing_current += current_financing or 0
        financing_previous += previous_financing or 0
        short_current += current_short or 0
        short_previous += previous_short or 0
        valid_rows += 1
    if not valid_rows:
        return None
    financing_change = financing_current - financing_previous
    short_change = short_current - short_previous
    return {
        "financingBalance": financing_current,
        "financingPrevious": financing_previous,
        "financingChange": financing_change,
        "financingChangePct": financing_change / financing_previous * 100 if financing_previous else None,
        "shortBalance": short_current,
        "shortPrevious": short_previous,
        "shortChange": short_change,
        "shortChangePct": short_change / short_previous * 100 if short_previous else None,
        "sourceLink": TWSE_MARGIN_URL,
        "sourceNote": "臺灣證券交易所集中市場融資融券餘額。",
    }


def format_openapi_date(value: Any) -> str | None:
    text = re.sub(r"\D", "", str(value or ""))
    if len(text) == 7:
        try:
            return datetime(int(text[:3]) + 1911, int(text[3:5]), int(text[5:7])).strftime("%Y-%m-%d")
        except ValueError:
            return None
    if len(text) == 8:
        try:
            return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def fetch_stock_margin_trading(stock: dict[str, Any]) -> dict[str, Any] | None:
    code = str(stock.get("code") or "").strip()
    market = str(stock.get("market") or "TWSE").upper()
    if not code:
        return None
    if market == "TPEX":
        rows = fetch_json(build_tpex_openapi_url("tpex_mainboard_margin_balance"), timeout=15)
        row = next(
            (
                item for item in rows if isinstance(item, dict)
                and str(item.get("SecuritiesCompanyCode") or "").strip() == code
            ),
            None,
        )
        if not row:
            return None
        financing_previous = parse_float(str(row.get("MarginPurchaseBalancePreviousDay") or ""))
        financing_balance = parse_float(str(row.get("MarginPurchaseBalance") or ""))
        short_previous = parse_float(str(row.get("ShortSaleBalancePreviousDay") or ""))
        short_balance = parse_float(str(row.get("ShortSaleBalance") or ""))
        source_link = build_tpex_openapi_url("tpex_mainboard_margin_balance")
        payload = {
            "date": format_openapi_date(row.get("Date")),
            "financingBuy": parse_float(str(row.get("MarginPurchase") or "")),
            "financingSell": parse_float(str(row.get("MarginSales") or "")),
            "financingCashRedemption": parse_float(str(row.get("CashRedemption") or "")),
            "financingPrevious": financing_previous,
            "financingBalance": financing_balance,
            "financingUtilizationRate": parse_float(str(row.get("MarginPurchaseUtilizationRate") or "")),
            "shortBuy": parse_float(str(row.get("ShortConvering") or "")),
            "shortSell": parse_float(str(row.get("ShortSale") or "")),
            "shortStockRedemption": parse_float(str(row.get("StockRedemption") or "")),
            "shortPrevious": short_previous,
            "shortBalance": short_balance,
            "shortUtilizationRate": parse_float(str(row.get("ShortSaleUtilizationRate") or "")),
            "offsetting": parse_float(str(row.get("Offsetting") or "")),
            "sourceLink": source_link,
            "sourceNote": "櫃買中心上櫃股票融資融券餘額。",
        }
    else:
        rows = fetch_json(TWSE_MARGIN_URL, timeout=15)
        row = next(
            (
                item for item in rows if isinstance(item, dict)
                and str(item.get("股票代號") or "").strip() == code
            ),
            None,
        )
        if not row:
            return None
        financing_previous = parse_float(str(row.get("融資前日餘額") or ""))
        financing_balance = parse_float(str(row.get("融資今日餘額") or ""))
        short_previous = parse_float(str(row.get("融券前日餘額") or ""))
        short_balance = parse_float(str(row.get("融券今日餘額") or ""))
        payload = {
            "date": None,
            "financingBuy": parse_float(str(row.get("融資買進") or "")),
            "financingSell": parse_float(str(row.get("融資賣出") or "")),
            "financingCashRedemption": parse_float(str(row.get("融資現金償還") or "")),
            "financingPrevious": financing_previous,
            "financingBalance": financing_balance,
            "financingUtilizationRate": None,
            "shortBuy": parse_float(str(row.get("融券買進") or "")),
            "shortSell": parse_float(str(row.get("融券賣出") or "")),
            "shortStockRedemption": parse_float(str(row.get("融券現券償還") or "")),
            "shortPrevious": short_previous,
            "shortBalance": short_balance,
            "shortUtilizationRate": None,
            "offsetting": parse_float(str(row.get("資券互抵") or "")),
            "sourceLink": TWSE_MARGIN_URL,
            "sourceNote": "臺灣證券交易所集中市場融資融券餘額。",
        }
    payload["financingChange"] = (
        financing_balance - financing_previous
        if financing_balance is not None and financing_previous is not None else None
    )
    payload["shortChange"] = (
        short_balance - short_previous
        if short_balance is not None and short_previous is not None else None
    )
    payload["shortFinancingRatio"] = (
        short_balance / financing_balance * 100
        if short_balance is not None and financing_balance not in (None, 0) else None
    )
    return payload


def parse_taifex_tx_open_interest(html: str) -> float | None:
    total = 0.0
    matched = 0
    for row_match in re.finditer(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        cells = [
            re.sub(r"\s+", " ", unescape(re.sub(r"(?is)<[^>]+>", " ", cell))).strip()
            for cell in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row_match.group(1))
        ]
        if len(cells) < 13 or cells[0] != "TX":
            continue
        open_interest = parse_float(cells[12].replace(",", ""))
        if open_interest is None:
            continue
        total += open_interest
        matched += 1
    return total if matched else None


def parse_taifex_open_interest_by_header(html: str, symbol: str) -> float | None:
    header_index: int | None = None
    total = 0.0
    matched = 0
    for row_match in re.finditer(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        cells = [
            re.sub(r"\s+", " ", unescape(re.sub(r"(?is)<[^>]+>", " ", cell))).strip()
            for cell in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row_match.group(1))
        ]
        if not cells:
            continue
        normalized_cells = [cell.replace(" ", "") for cell in cells]
        if header_index is None and any("未沖銷契約量" in cell or "未平倉" in cell for cell in normalized_cells):
            for index, cell in enumerate(normalized_cells):
                if "未沖銷契約量" in cell or "未平倉" in cell:
                    header_index = index
                    break
            continue
        if cells[0] != symbol:
            continue
        candidate_indexes = [header_index] if header_index is not None else [11, 12, len(cells) - 1]
        for index in candidate_indexes:
            if index is None or index < 0 or index >= len(cells):
                continue
            open_interest = parse_float(cells[index].replace(",", ""))
            if open_interest is None:
                continue
            total += open_interest
            matched += 1
            break
    return total if matched else None


def parse_taifex_market_number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text or text.upper() in {"NULL", "NAN"} or text in {"-", "--"}:
        return None
    return parse_float(text)


def normalize_taifex_date_text(value: Any) -> str:
    text = re.sub(r"\D", "", str(value or ""))
    if len(text) >= 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return str(value or "")


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


def fetch_yahoo_taiwan_future_quotes(timeout: int = 10) -> dict[str, dict[str, Any]]:
    now = time.time()
    with cache_lock:
        cached = cache_data.get("yahoo_tw_future_quotes") or {}
        cached_items = cached.get("items") if isinstance(cached, dict) else None
        if cached_items and now - float(cached.get("stored_at") or 0) < YAHOO_TW_FUTURE_CACHE_SECONDS:
            return copy.deepcopy(cached_items)
    html = fetch_text(YAHOO_TW_FUTURE_UNCOVERED_URL, timeout=timeout)
    quotes = parse_yahoo_taiwan_future_quotes(html)
    with cache_lock:
        cache_data["yahoo_tw_future_quotes"] = {"stored_at": now, "items": copy.deepcopy(quotes)}
    return quotes


def fetch_yahoo_taiwan_future_quote(symbol: str, timeout: int = 10) -> dict[str, Any] | None:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol:
        return None
    return fetch_yahoo_taiwan_future_quotes(timeout=timeout).get(clean_symbol)


def build_yahoo_taiwan_future_technical_url(code: str) -> str:
    clean_code = str(code or "").strip().upper()
    if not clean_code:
        return ""
    return f"{YAHOO_TW_FUTURE_URL}/{quote(clean_code, safe='')}/technical-analysis"


def parse_yahoo_taiwan_future_contract_month(label: str, code: str, kind: str) -> str:
    clean_kind = str(kind or "").strip().lower()
    clean_label = str(label or "").strip()
    clean_code = str(code or "").strip().upper()
    if clean_kind != "month":
        return ""
    if re.fullmatch(r"\d{4}", clean_label):
        return f"20{clean_label}"
    match = re.match(r"^W[A-Z]{2}([FGHJKMNQUVXZ])(\d)$", clean_code)
    if not match:
        return ""
    month = TAIFEX_FUTURE_MONTH_CODE_TO_MONTH.get(match.group(1), "")
    if not month:
        return ""
    return f"202{match.group(2)}{month}"


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


def build_yahoo_taiwan_future_technical_profile(symbol: str) -> dict[str, Any]:
    clean_symbol = str(symbol or "").strip().upper()
    group = YAHOO_TW_FUTURE_TECHNICAL_GROUPS.get(clean_symbol)
    if not group:
        return {}
    primary_code = str(group.get("primaryCode") or "").strip().upper()
    source_name = str(group.get("source") or "Yahoo 股市期貨技術分析")
    source_url = str(group.get("sourceUrl") or build_yahoo_taiwan_future_technical_url(primary_code))
    use_yahoo_url = not group.get("sourceUrl")
    contracts = []
    for label, code, kind in group.get("contracts") or []:
        clean_code = str(code or "").strip().upper()
        contract_url = build_yahoo_taiwan_future_technical_url(clean_code) if use_yahoo_url else source_url
        contracts.append({
            "label": str(label or clean_code),
            "code": clean_code,
            "kind": str(kind or "contract"),
            "contractMonth": parse_yahoo_taiwan_future_contract_month(str(label or ""), clean_code, str(kind or "")),
            "url": contract_url,
            "isPrimary": clean_code == primary_code,
        })
    return {
        "symbol": clean_symbol,
        "name": group.get("name") or clean_symbol,
        "primaryCode": primary_code,
        "primaryUrl": source_url if not use_yahoo_url else build_yahoo_taiwan_future_technical_url(primary_code),
        "source": source_name,
        "sourceUrl": source_url,
        "contracts": contracts,
    }


def parse_market_iso_date(value: Any) -> datetime | None:
    text = str(value or "").strip()
    for date_format in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    return None


def yahoo_future_quote_can_override_taifex(yahoo_quote: dict[str, Any] | None, snapshot: dict[str, Any] | None) -> bool:
    if not yahoo_quote:
        return False
    if not snapshot:
        return parse_float(str(yahoo_quote.get("close") or "")) is not None
    yahoo_date = parse_market_iso_date(yahoo_quote.get("date"))
    snapshot_date = parse_market_iso_date(snapshot.get("date"))
    if yahoo_date is None or snapshot_date is None:
        return False
    return yahoo_date >= snapshot_date - timedelta(days=1)


def format_price_value(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "--"


def select_taifex_daily_market_row(rows: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    clean_symbol = str(symbol or "").strip().upper()
    candidates = []
    for row in rows:
        if str(row.get("Contract") or "").strip().upper() != clean_symbol:
            continue
        close_value = parse_taifex_market_number(row.get("Last")) or parse_taifex_market_number(row.get("SettlementPrice"))
        if close_value is None:
            continue
        volume_value = parse_taifex_market_number(row.get("Volume")) or 0
        settlement_value = parse_taifex_market_number(row.get("SettlementPrice"))
        open_interest = parse_taifex_market_number(row.get("OpenInterest"))
        score = volume_value
        if settlement_value is not None:
            score += 1_000_000_000
        if open_interest is not None:
            score += 100_000_000
        candidates.append((score, row))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]


def normalize_taifex_daily_market_row(row: dict[str, Any]) -> dict[str, Any] | None:
    close_value = parse_taifex_market_number(row.get("Last")) or parse_taifex_market_number(row.get("SettlementPrice"))
    if close_value is None:
        return None
    open_value = parse_taifex_market_number(row.get("Open")) or close_value
    high_value = parse_taifex_market_number(row.get("High")) or max(open_value, close_value)
    low_value = parse_taifex_market_number(row.get("Low")) or min(open_value, close_value)
    volume_value = parse_taifex_market_number(row.get("Volume")) or 0
    open_interest = parse_taifex_market_number(row.get("OpenInterest"))
    settlement = parse_taifex_market_number(row.get("SettlementPrice"))
    return {
        "date": normalize_taifex_date_text(row.get("Date")),
        "contract": str(row.get("Contract") or ""),
        "month": str(row.get("ContractMonth(Week)") or row.get("ContractMonth") or ""),
        "open": open_value,
        "high": high_value,
        "low": low_value,
        "close": close_value,
        "settlement": settlement,
        "volume": volume_value,
        "openInterest": open_interest,
        "change": parse_taifex_market_number(row.get("Change")),
        "changePct": parse_taifex_market_number(row.get("%")),
    }


def fetch_taifex_latest_futures_market_snapshot(symbol: str) -> dict[str, Any] | None:
    rows = fetch_json(TAIFEX_FUTURES_DAILY_OPENAPI_URL, timeout=15)
    if not isinstance(rows, list):
        return None
    selected = select_taifex_daily_market_row(rows, symbol)
    if not selected:
        return None
    normalized = normalize_taifex_daily_market_row(selected)
    if not normalized:
        return None
    return {
        **normalized,
        "observations": [normalized],
        "sourceLink": TAIFEX_FUTURES_DAILY_OPENAPI_URL,
        "sourceNote": "臺灣期貨交易所 OpenAPI 期貨每日交易行情。",
    }


def parse_taifex_daily_market_html_rows(html: str, symbol: str, date_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    header_map: dict[str, int] = {}
    aliases = {
        "Contract": ("契約", "商品"),
        "ContractMonth(Week)": ("到期月份", "契約月份", "月份"),
        "Open": ("開盤",),
        "High": ("最高",),
        "Low": ("最低",),
        "Last": ("最後成交", "收盤",),
        "Change": ("漲跌價", "漲跌"),
        "%": ("漲跌%", "%"),
        "Volume": ("成交量", "合計成交量"),
        "SettlementPrice": ("結算價",),
        "OpenInterest": ("未沖銷", "未平倉"),
        "TradingSession": ("交易時段",),
    }
    fallback_indexes = {
        "Contract": 0,
        "ContractMonth(Week)": 1,
        "Open": 2,
        "High": 3,
        "Low": 4,
        "Last": 5,
        "Change": 6,
        "%": 7,
        "Volume": 8,
        "SettlementPrice": 9,
        "OpenInterest": 10,
    }
    for row_match in re.finditer(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        cells = [
            re.sub(r"\s+", " ", unescape(re.sub(r"(?is)<[^>]+>", " ", cell))).strip()
            for cell in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row_match.group(1))
        ]
        if not cells:
            continue
        normalized_cells = [cell.replace(" ", "") for cell in cells]
        if any("開盤" in cell for cell in normalized_cells) and any(("契約" in cell or "商品" in cell) for cell in normalized_cells):
            for field, names in aliases.items():
                for index, cell in enumerate(normalized_cells):
                    if any(name in cell for name in names):
                        header_map[field] = index
                        break
            continue
        contract_index = header_map.get("Contract", fallback_indexes["Contract"])
        if contract_index >= len(cells) or str(cells[contract_index]).strip().upper() != str(symbol or "").strip().upper():
            continue
        row: dict[str, Any] = {"Date": date_text}
        for field, fallback_index in fallback_indexes.items():
            index = header_map.get(field, fallback_index)
            row[field] = cells[index] if 0 <= index < len(cells) else ""
        trading_index = header_map.get("TradingSession")
        if trading_index is not None and 0 <= trading_index < len(cells):
            row["TradingSession"] = cells[trading_index]
        rows.append(row)
    return rows


def parse_taifex_futures_download_candles(
    text: str,
    symbol: str,
    contract_month: str = "",
) -> list[dict[str, Any]]:
    clean_symbol = str(symbol or "").strip().upper()
    clean_contract_month = re.sub(r"\D", "", str(contract_month or ""))
    if not clean_symbol or not text:
        return []
    selected_by_date: dict[str, tuple[float, dict[str, Any]]] = {}
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    for row in reader:
        if len(row) < 18:
            continue
        date_text = str(row[0] or "").strip().replace("/", "-")
        contract = str(row[1] or "").strip().upper()
        contract_month = str(row[2] or "").strip()
        session = str(row[17] or "").strip()
        if contract != clean_symbol or session != "一般" or "/" in contract_month:
            continue
        if clean_contract_month and contract_month != clean_contract_month:
            continue
        open_value = parse_taifex_market_number(row[3])
        high_value = parse_taifex_market_number(row[4])
        low_value = parse_taifex_market_number(row[5])
        close_value = parse_taifex_market_number(row[6])
        volume_value = parse_taifex_market_number(row[9]) or 0
        if not date_text or None in {open_value, high_value, low_value, close_value}:
            continue
        candle = {
            "time": date_text,
            "contractMonth": contract_month,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "close": close_value,
            "change": parse_taifex_market_number(row[7]),
            "changePct": parse_taifex_market_number(str(row[8] or "").replace("%", "")),
            "volume": volume_value,
            "settlement": parse_taifex_market_number(row[10]),
            "openInterest": parse_taifex_market_number(row[11]),
            "source": "TAIFEX 期貨每日行情下載",
        }
        previous = selected_by_date.get(date_text)
        if previous is None or volume_value > previous[0]:
            selected_by_date[date_text] = (volume_value, candle)
    return [
        item[1]
        for item in sorted(selected_by_date.values(), key=lambda pair: str(pair[1].get("time") or ""))
    ]


def fetch_taifex_futures_download_candles(
    symbol: str,
    max_observations: int = 30,
    contract_month: str = "",
    max_windows: int | None = None,
) -> list[dict[str, Any]]:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol:
        return []
    combined: dict[str, dict[str, Any]] = {}
    end_date = datetime.now(TZ).date()
    window_limit = max_windows if max_windows is not None else max(3, math.ceil(max_observations / 18) + 2)

    window_ranges: list[tuple[Any, Any]] = []
    cursor = end_date
    for _ in range(window_limit):
        start = cursor - timedelta(days=30)
        window_ranges.append((start, cursor))
        cursor = start - timedelta(days=1)

    def fetch_window(window: tuple[Any, Any]) -> str:
        start, end = window
        fields = {
            "down_type": "1",
            "commodity_id": clean_symbol,
            "commodity_id2": "",
            "queryStartDate": start.strftime("%Y/%m/%d"),
            "queryEndDate": end.strftime("%Y/%m/%d"),
        }
        with taifex_open_interest_lock:
            try:
                text = fetch_form_text(TAIFEX_FUTURES_DATA_DOWNLOAD_URL, fields, timeout=25)
            except Exception:  # noqa: BLE001
                LOGGER.warning("TAIFEX futures data download failed for %s", clean_symbol, exc_info=True)
                text = ""
            time.sleep(0.08)
        return text

    # Windows are fetched in small concurrent batches (bounded by the same TAIFEX
    # politeness semaphore every window already waits on) instead of one at a time,
    # while still checking the same early-stop condition between batches.
    for batch_start in range(0, len(window_ranges), TAIFEX_FORM_QUERY_CONCURRENCY):
        if len(combined) >= max_observations:
            break
        batch = window_ranges[batch_start : batch_start + TAIFEX_FORM_QUERY_CONCURRENCY]
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            texts = list(executor.map(fetch_window, batch))
        for text in texts:
            for candle in parse_taifex_futures_download_candles(text, clean_symbol, contract_month=contract_month):
                time_key = str(candle.get("time") or "")
                if time_key:
                    combined[time_key] = candle

    return sorted(combined.values(), key=lambda row: str(row.get("time") or ""))[-max_observations:]


def fetch_taifex_previous30_tick_dates() -> list[str]:
    html = fetch_text(TAIFEX_FUTURES_PREVIOUS30_SALES_URL, timeout=15)
    dates: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"Daily_(\d{4})_(\d{2})_(\d{2})\.zip", html):
        date_text = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        if date_text in seen:
            continue
        seen.add(date_text)
        dates.append(date_text)
    return dates


def build_taifex_daily_tick_csv_url(date_text: str) -> str:
    compact = str(date_text or "").strip().replace("-", "_").replace("/", "_")
    if re.fullmatch(r"\d{8}", compact):
        compact = f"{compact[:4]}_{compact[4:6]}_{compact[6:]}"
    return f"{TAIFEX_FUTURES_DAILY_TICK_CSV_BASE}/Daily_{compact}.zip"


def parse_taifex_daily_tick_csv_candle(payload: bytes, symbol: str, date_text: str) -> dict[str, Any] | None:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol or not payload:
        return None
    compact_date = str(date_text or "").strip().replace("-", "").replace("/", "")
    contract_rows: dict[str, list[tuple[str, str, int, float, float]]] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not names:
                return None
            raw = archive.read(names[0])
    except Exception:  # noqa: BLE001
        LOGGER.warning("TAIFEX daily tick zip parse failed for %s %s", clean_symbol, date_text, exc_info=True)
        return None
    text = raw.decode("cp950", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    next(reader, None)
    for index, row in enumerate(reader):
        if len(row) < 6:
            continue
        trade_date = str(row[0] or "").strip()
        product = str(row[1] or "").strip().upper()
        contract_month = str(row[2] or "").strip()
        trade_time = str(row[3] or "").strip().zfill(6)
        if (
            product != clean_symbol
            or trade_date != compact_date
            or "/" in contract_month
            or not ("084500" <= trade_time <= "134500")
        ):
            continue
        price_value = parse_taifex_market_number(row[4])
        quantity_value = parse_taifex_market_number(row[5])
        if price_value is None or quantity_value is None:
            continue
        contract_rows.setdefault(contract_month, []).append((
            trade_date,
            trade_time,
            index,
            price_value,
            quantity_value / 2,
        ))
    if not contract_rows:
        return None
    contract_month, trades = max(contract_rows.items(), key=lambda item: sum(row[4] for row in item[1]))
    trades = sorted(trades, key=lambda item: (item[0], item[1], item[2]))
    prices = [row[3] for row in trades]
    volume_value = sum(row[4] for row in trades)
    if not prices:
        return None
    return {
        "time": datetime.strptime(compact_date, "%Y%m%d").strftime("%Y-%m-%d") if re.fullmatch(r"\d{8}", compact_date) else date_text,
        "contractMonth": contract_month,
        "open": prices[0],
        "high": max(prices),
        "low": min(prices),
        "close": prices[-1],
        "volume": volume_value,
        "source": "TAIFEX 前30個交易日期貨每筆成交 CSV",
    }


def fetch_taifex_previous30_futures_tick_candles(symbol: str, max_observations: int = 30) -> list[dict[str, Any]]:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol:
        return []
    dates = fetch_taifex_previous30_tick_dates()
    candles: list[dict[str, Any]] = []
    for date_text in dates[:max(1, int(max_observations))]:
        url = build_taifex_daily_tick_csv_url(date_text)
        try:
            payload = fetch_binary(url, timeout=20)
        except Exception:  # noqa: BLE001
            LOGGER.warning("TAIFEX daily tick csv fetch failed for %s %s", clean_symbol, date_text, exc_info=True)
            continue
        candle = parse_taifex_daily_tick_csv_candle(payload, clean_symbol, date_text)
        if candle:
            candles.append(candle)
    return sorted(candles, key=lambda row: str(row.get("time") or ""))[-max_observations:]


def fetch_taifex_daily_market_report_candles(symbol: str, max_observations: int = 12) -> list[dict[str, Any]]:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol:
        return []
    requested = datetime.now(TZ)
    candles: list[dict[str, Any]] = []
    max_scan_days = max(20, int(max_observations * 2.2) + 8)
    for offset in range(max_scan_days):
        target = requested - timedelta(days=offset)
        if target.weekday() >= 5:
            continue
        date_for_form = target.strftime("%Y/%m/%d")
        date_for_row = target.strftime("%Y%m%d")
        with taifex_open_interest_lock:
            html = fetch_form_text(
                TAIFEX_FUTURES_DAILY_URL,
                {
                    "queryType": "2",
                    "marketCode": "0",
                    "commodity_id": clean_symbol,
                    "commodity_idt": clean_symbol,
                    "queryDate": date_for_form,
                },
                timeout=15,
            )
            time.sleep(0.08)
        selected = select_taifex_daily_market_row(parse_taifex_daily_market_html_rows(html, clean_symbol, date_for_row), clean_symbol)
        normalized = normalize_taifex_daily_market_row(selected or {})
        if not normalized:
            continue
        candles.append({
            "time": normalized["date"],
            "open": normalized["open"],
            "high": normalized["high"],
            "low": normalized["low"],
            "close": normalized["close"],
            "volume": normalized["volume"],
            "openInterest": normalized.get("openInterest"),
            "settlement": normalized.get("settlement"),
        })
        if len(candles) >= max_observations:
            break
    return list(reversed(candles))


def fetch_taifex_futures_price_candles(symbol: str, max_observations: int = 30) -> list[dict[str, Any]]:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol:
        return []
    combined: dict[str, dict[str, Any]] = {}
    try:
        for candle in fetch_taifex_futures_download_candles(clean_symbol, max_observations):
            time_key = str(candle.get("time") or "")
            if time_key:
                combined[time_key] = candle
    except Exception:  # noqa: BLE001
        LOGGER.warning("TAIFEX futures data download candles failed for %s", clean_symbol, exc_info=True)
    if len(combined) < 2:
        try:
            report_candles = fetch_taifex_daily_market_report_candles(clean_symbol, min(max_observations, 12))
        except Exception:  # noqa: BLE001
            LOGGER.warning("TAIFEX daily market report candles failed for %s", clean_symbol, exc_info=True)
            report_candles = []
        for candle in report_candles:
            time_key = str(candle.get("time") or "")
            if not time_key:
                continue
            existing = combined.get(time_key, {})
            merged = {**existing}
            for key, value in candle.items():
                if value not in {None, ""}:
                    merged[key] = value
            combined[time_key] = merged
    return sorted(combined.values(), key=lambda row: str(row.get("time") or ""))[-max_observations:]


def find_yahoo_taiwan_future_technical_contract(symbol: str, code: str = "") -> dict[str, Any] | None:
    clean_symbol = str(symbol or "").strip().upper()
    profile = build_yahoo_taiwan_future_technical_profile(clean_symbol)
    contracts = [item for item in profile.get("contracts") or [] if isinstance(item, dict)]
    if not contracts:
        return None
    clean_code = str(code or profile.get("primaryCode") or "").strip().upper()
    selected = next((item for item in contracts if str(item.get("code") or "").strip().upper() == clean_code), None)
    return selected or next((item for item in contracts if item.get("isPrimary")), None) or contracts[0]


def build_taifex_futures_interval_candles(
    raw_candles: list[dict[str, Any]],
    interval: str,
) -> list[dict[str, Any]]:
    series = [
        {
            "date": row.get("time") or row.get("date") or "",
            "open": row.get("open"),
            "high": row.get("high"),
            "low": row.get("low"),
            "close": row.get("close"),
            "volume": row.get("volume"),
            "volumeValue": row.get("volume"),
            "settlement": row.get("settlement"),
            "openInterest": row.get("openInterest"),
        }
        for row in raw_candles
    ]
    return build_derivative_candles({"series": series}, interval)


def fetch_taifex_futures_technical_candles(
    symbol: str,
    code: str = "",
    interval: str = "day",
) -> dict[str, Any]:
    clean_symbol = str(symbol or "").strip().upper()
    clean_interval = str(interval or "day").strip().lower()
    if clean_interval not in {"day", "week", "month", "all"}:
        clean_interval = "day"
    selected_contract = find_yahoo_taiwan_future_technical_contract(clean_symbol, code)
    if not selected_contract:
        return {"error": "找不到對應的 Yahoo 技術契約。"}
    selected_code = str(selected_contract.get("code") or "").strip().upper()
    inferred_symbol = infer_yahoo_taiwan_future_symbol_from_code(selected_code)
    if inferred_symbol and inferred_symbol != clean_symbol:
        return {"error": "Yahoo 技術代碼與目前期貨商品不一致。"}

    contract_month = str(selected_contract.get("contractMonth") or "").strip()
    cache_key = f"{clean_symbol}:{selected_code}:{contract_month or 'continuous'}:{clean_interval}"
    cached = read_memory_cache("yahoo_tw_future_technical_candles", cache_key, 900)
    if cached is not None:
        return cached

    raw_targets = {
        "day": 90,
        "week": 280,
        "month": 620,
        "all": 620,
    }
    raw_limit = raw_targets.get(clean_interval, 90)
    max_windows = max(4, math.ceil(raw_limit / 18) + 2)
    raw_candles = fetch_taifex_futures_download_candles(
        clean_symbol,
        max_observations=raw_limit,
        contract_month=contract_month,
        max_windows=max_windows,
    )
    candles = build_taifex_futures_interval_candles(raw_candles, clean_interval)
    candles = candles[-90:] if clean_interval in {"week", "month", "all"} else candles[-90:]
    payload = {
        "symbol": clean_symbol,
        "interval": clean_interval,
        "code": selected_code,
        "contract": selected_contract,
        "contractMonth": contract_month,
        "candles": candles,
        "count": len(candles),
        "source": "TAIFEX 期貨每日行情下載（依技術契約代碼對應月份）",
        "sourceUrl": TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
        "technicalAnalysisUrl": selected_contract.get("url") or build_yahoo_taiwan_future_technical_url(selected_code),
    }
    write_memory_cache("yahoo_tw_future_technical_candles", cache_key, payload)
    return payload


def fetch_taifex_tx_open_interest(market_date: str, max_observations: int = 2) -> dict[str, Any] | None:
    requested = datetime.strptime(market_date, "%Y%m%d")
    observations: list[dict[str, Any]] = []
    target_observations = max(1, int(max_observations or 1))
    max_scan_days = max(12, target_observations * 3 + 8)
    for offset in range(max_scan_days):
        target = requested - timedelta(days=offset)
        if target.weekday() >= 5:
            continue
        date_text = target.strftime("%Y/%m/%d")
        with taifex_open_interest_lock:
            html = fetch_form_text(
                TAIFEX_FUTURES_DAILY_URL,
                {
                    "queryType": "2",
                    "marketCode": "0",
                    "commodity_id": "TX",
                    "commodity_idt": "TX",
                    "queryDate": date_text,
                },
                timeout=15,
            )
            time.sleep(0.04)
        open_interest = parse_taifex_tx_open_interest(html)
        if open_interest is None:
            continue
        observations.append({"date": target.strftime("%Y-%m-%d"), "value": open_interest})
        if len(observations) >= target_observations:
            break
    if not observations:
        return None
    current = observations[0]
    previous = observations[1] if len(observations) > 1 else None
    change = current["value"] - previous["value"] if previous else None
    return {
        "date": current["date"],
        "openInterest": current["value"],
        "previousOpenInterest": previous["value"] if previous else None,
        "change": change,
        "changePct": change / previous["value"] * 100 if previous and previous["value"] else None,
        "observations": list(reversed(observations)),
        "sourceLink": TAIFEX_FUTURES_DAILY_URL,
        "sourceNote": "臺灣期貨交易所臺股期貨一般交易時段未沖銷契約量。",
    }


def fetch_taifex_futures_open_interest(market_date: str, commodity_id: str, max_observations: int = 2) -> dict[str, Any] | None:
    """Fetch TAIFEX official open interest for one futures product without estimating prices."""
    commodity = str(commodity_id or "").strip().upper()
    if not commodity:
        return None
    requested = datetime.strptime(market_date, "%Y%m%d")
    observations: list[dict[str, Any]] = []
    target_observations = max(1, int(max_observations or 1))
    max_scan_days = max(12, target_observations * 3 + 8)
    for offset in range(max_scan_days):
        target = requested - timedelta(days=offset)
        if target.weekday() >= 5:
            continue
        with taifex_open_interest_lock:
            html = fetch_form_text(
                TAIFEX_FUTURES_DAILY_URL,
                {
                    "queryType": "2",
                    "marketCode": "0",
                    "commodity_id": commodity,
                    "commodity_idt": commodity,
                    "queryDate": target.strftime("%Y/%m/%d"),
                },
                timeout=15,
            )
            time.sleep(0.04)
        open_interest = parse_taifex_open_interest_by_header(html, commodity)
        if open_interest is None:
            continue
        observations.append({"date": target.strftime("%Y-%m-%d"), "value": open_interest})
        if len(observations) >= target_observations:
            break
    if not observations:
        return None
    current = observations[0]
    previous = observations[1] if len(observations) > 1 else None
    change = current["value"] - previous["value"] if previous else None
    return {
        "date": current["date"],
        "openInterest": current["value"],
        "previousOpenInterest": previous["value"] if previous else None,
        "change": change,
        "changePct": change / previous["value"] * 100 if previous and previous["value"] else None,
        "observations": list(reversed(observations)),
        "sourceLink": TAIFEX_FUTURES_DAILY_URL,
        "sourceNote": f"臺灣期貨交易所 {commodity} 一般交易時段未沖銷契約量。",
    }


def fetch_taifex_txo_open_interest(market_date: str, max_observations: int = 2) -> dict[str, Any] | None:
    requested = datetime.strptime(market_date, "%Y%m%d")
    observations: list[dict[str, Any]] = []
    target_observations = max(1, int(max_observations or 1))
    for offset in range(12):
        target = requested - timedelta(days=offset)
        if target.weekday() >= 5:
            continue
        date_text = target.strftime("%Y/%m/%d")
        html = fetch_form_text(
            TAIFEX_OPTIONS_DAILY_URL,
            {
                "queryType": "2",
                "marketCode": "0",
                "commodity_id": "TXO",
                "commodity_idt": "TXO",
                "queryDate": date_text,
            },
            timeout=15,
        )
        open_interest = parse_taifex_open_interest_by_header(html, "TXO")
        if open_interest is None:
            continue
        observations.append({"date": target.strftime("%Y-%m-%d"), "value": open_interest})
        if len(observations) >= target_observations:
            break
    if not observations:
        return None
    current = observations[0]
    previous = observations[1] if len(observations) > 1 else None
    change = current["value"] - previous["value"] if previous else None
    return {
        "date": current["date"],
        "openInterest": current["value"],
        "previousOpenInterest": previous["value"] if previous else None,
        "change": change,
        "changePct": change / previous["value"] * 100 if previous and previous["value"] else None,
        "sourceLink": TAIFEX_OPTIONS_DAILY_URL,
        "sourceNote": "臺灣期貨交易所台指選擇權一般交易時段未沖銷契約量。",
    }


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


def parse_taifex_query_date(value: str | None = None) -> str:
    if not value:
        return datetime.now(TZ).strftime("%Y%m%d")
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        raise ValueError("INVALID_DATE")
    datetime.strptime(digits, "%Y%m%d")
    return digits


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


def fetch_taiex_spot_snapshot() -> dict[str, Any]:
    return fetch_yahoo_spot_snapshot("^TWII", "台灣加權指數")


def fetch_yahoo_spot_snapshot(symbol: str, name: str) -> dict[str, Any]:
    try:
        chart = fetch_yahoo_symbol_chart(symbol, "5d", "1d")
        series = build_yahoo_chart_series(chart, volume_divisor=1)
        meta = (chart or {}).get("meta") or {}
    except Exception:  # noqa: BLE001
        series = []
        meta = {}
    if not series:
        return {"symbol": symbol, "name": name, "value": None, "source": "Yahoo Finance"}
    latest = series[-1]
    previous = series[-2] if len(series) >= 2 else {}
    value = parse_float(str(meta.get("regularMarketPrice") or "")) or parse_float(str(latest.get("close") or ""))
    previous_value = parse_float(str(meta.get("chartPreviousClose") or "")) or parse_float(str(previous.get("close") or ""))
    change = value - previous_value if value is not None and previous_value is not None else None
    pct = change / previous_value * 100 if change is not None and previous_value not in (None, 0) else None
    return {
        "symbol": symbol,
        "name": name,
        "value": value,
        "previousValue": previous_value,
        "change": change,
        "pct": pct,
        "high": parse_float(str(meta.get("regularMarketDayHigh") or "")) or parse_float(str(latest.get("high") or "")),
        "low": parse_float(str(meta.get("regularMarketDayLow") or "")) or parse_float(str(latest.get("low") or "")),
        "volume": parse_float(str(meta.get("regularMarketVolume") or "")) or parse_float(str(latest.get("volumeValue") or latest.get("volume") or "")),
        "date": latest.get("date") or "",
        "source": "Yahoo Finance",
    }


def normalize_taiwan_option_underlying(value: str | None = None) -> str:
    clean = str(value or TAIWAN_OPTION_DEFAULT_PRODUCT).strip().upper()
    return clean if clean in TAIWAN_OPTION_PRODUCTS else TAIWAN_OPTION_DEFAULT_PRODUCT


def get_taiwan_option_product(value: str | None = None) -> dict[str, Any]:
    underlying = normalize_taiwan_option_underlying(value)
    return {**TAIWAN_OPTION_PRODUCTS[underlying], "symbol": underlying}


def normalize_taiwan_option_source(value: str | None = None) -> str:
    clean = str(value or "auto").strip().lower()
    return clean if clean in {"auto", "taifex", "yahoo"} else "auto"


def build_yahoo_taiwan_option_url(underlying: str | None = None, expiry: str | None = None) -> str:
    product = get_taiwan_option_product(underlying)
    opcm = str(product.get("yahooOpcm") or "").strip()
    if not opcm:
        return YAHOO_TW_OPTION_URL
    params = {
        "opmr": "optionfull",
        "opcm": opcm,
    }
    expiry_text = str(expiry or "").strip()
    if expiry_text:
        params["opym"] = expiry_text
    return f"{YAHOO_TW_OPTION_URL}?{urlencode(params)}"


def fetch_taiwan_option_spot_snapshot(underlying: str | None = None) -> dict[str, Any]:
    product = get_taiwan_option_product(underlying)
    spot_symbol = str(product.get("spotSymbol") or "").strip()
    if spot_symbol:
        if spot_symbol == "^TWII":
            return fetch_taiex_spot_snapshot()
        return fetch_yahoo_spot_snapshot(spot_symbol, str(product.get("spotName") or product.get("name") or spot_symbol))
    return {
        "symbol": product["symbol"],
        "name": product.get("spotName") or product.get("name") or product["symbol"],
        "value": None,
        "source": "TAIFEX 官方日報未提供可直接比對的現貨基準；以履約價、OI 與最大痛點定位。",
    }


def select_option_atm_strike(chain: list[dict[str, Any]], spot: float | None, max_pain: dict[str, Any]) -> float | None:
    strikes = [float(item["strike"]) for item in chain if item.get("strike") is not None]
    if not strikes:
        return None
    if spot is not None:
        return min(strikes, key=lambda strike: abs(strike - float(spot)))
    max_pain_strike = parse_float(str(max_pain.get("strike") or ""))
    if max_pain_strike is not None:
        return max_pain_strike
    ranked = sorted(
        chain,
        key=lambda item: (float(item.get("callOpenInterest") or 0) + float(item.get("putOpenInterest") or 0)),
        reverse=True,
    )
    if ranked and (float(ranked[0].get("callOpenInterest") or 0) + float(ranked[0].get("putOpenInterest") or 0)) > 0:
        return parse_float(str(ranked[0].get("strike") or ""))
    return strikes[len(strikes) // 2]


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


def summarize_taifex_option_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [row for row in rows if row.get("optionType") == "call"]
    puts = [row for row in rows if row.get("optionType") == "put"]
    call_oi = sum(float(row.get("openInterest") or 0) for row in calls)
    put_oi = sum(float(row.get("openInterest") or 0) for row in puts)
    call_volume = sum(float(row.get("volume") or 0) for row in calls)
    put_volume = sum(float(row.get("volume") or 0) for row in puts)
    return {
        "contractCount": len(rows),
        "callCount": len(calls),
        "putCount": len(puts),
        "callOpenInterest": call_oi,
        "putOpenInterest": put_oi,
        "totalOpenInterest": call_oi + put_oi,
        "callVolume": call_volume,
        "putVolume": put_volume,
        "totalVolume": call_volume + put_volume,
        "putCallRatio": put_oi / call_oi if call_oi else None,
        "volumePutCallRatio": put_volume / call_volume if call_volume else None,
    }


def calculate_taifex_max_pain(chain: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [float(item["strike"]) for item in chain if item.get("strike") is not None]
    if not candidates:
        return {"strike": None, "loss": None}
    best_strike = None
    best_loss = None
    for candidate in candidates:
        loss = 0.0
        for item in chain:
            strike = float(item.get("strike") or 0)
            call_oi = float((item.get("call") or {}).get("openInterest") or 0)
            put_oi = float((item.get("put") or {}).get("openInterest") or 0)
            loss += call_oi * max(0.0, candidate - strike)
            loss += put_oi * max(0.0, strike - candidate)
        if best_loss is None or loss < best_loss:
            best_loss = loss
            best_strike = candidate
    return {"strike": best_strike, "loss": best_loss}


def build_taifex_option_chain(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[float, dict[str, Any]] = {}
    for row in rows:
        strike = float(row.get("strike") or 0)
        if strike <= 0:
            continue
        item = grouped.setdefault(strike, {"strike": strike, "call": None, "put": None})
        side = "call" if row.get("optionType") == "call" else "put"
        item[side] = row
    chain = [grouped[strike] for strike in sorted(grouped)]
    for item in chain:
        call = item.get("call") or {}
        put = item.get("put") or {}
        item["callOpenInterest"] = float(call.get("openInterest") or 0)
        item["putOpenInterest"] = float(put.get("openInterest") or 0)
        item["callVolume"] = float(call.get("volume") or 0)
        item["putVolume"] = float(put.get("volume") or 0)
    return chain


def build_taifex_option_distribution(chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strike": item.get("strike"),
            "callOpenInterest": item.get("callOpenInterest") or 0,
            "putOpenInterest": item.get("putOpenInterest") or 0,
            "callVolume": item.get("callVolume") or 0,
            "putVolume": item.get("putVolume") or 0,
        }
        for item in chain
    ]


def build_taifex_option_ai_analysis(
    summary: dict[str, Any],
    chain: list[dict[str, Any]],
    max_pain: dict[str, Any],
    spot: float | None,
) -> dict[str, Any]:
    pcr = summary.get("putCallRatio")
    volume_pcr = summary.get("volumePutCallRatio")
    support = max(chain, key=lambda item: item.get("putOpenInterest") or 0, default={}).get("strike")
    resistance = max(chain, key=lambda item: item.get("callOpenInterest") or 0, default={}).get("strike")
    max_pain_strike = max_pain.get("strike")
    reasons: list[str] = []
    if pcr is not None:
        if pcr >= 1.25:
            reasons.append(f"未平倉 Put/Call Ratio {pcr:.2f}，避險需求偏高。")
        elif pcr <= 0.75:
            reasons.append(f"未平倉 Put/Call Ratio {pcr:.2f}，Call OI 相對集中。")
        else:
            reasons.append(f"未平倉 Put/Call Ratio {pcr:.2f}，多空籌碼接近平衡。")
    if max_pain_strike is not None:
        reasons.append(f"最大痛點位於 {max_pain_strike:,.0f}，可作到期前價位磁吸參考。")
    if support is not None and resistance is not None:
        reasons.append(f"Put OI 主要支撐 {support:,.0f}，Call OI 主要壓力 {resistance:,.0f}。")
    if volume_pcr is not None:
        reasons.append(f"成交量 Put/Call Ratio {volume_pcr:.2f}，反映當日交易偏向。")

    if pcr is None:
        bias = "資料不足"
        risk_level = "中"
    elif pcr >= 1.35:
        bias = "避險升溫"
        risk_level = "高"
    elif pcr <= 0.7:
        bias = "偏多但追價風險升高"
        risk_level = "中"
    else:
        bias = "區間震盪"
        risk_level = "中"
    if spot and max_pain_strike and abs(spot - max_pain_strike) / spot <= 0.01:
        risk_level = "低" if risk_level == "中" else risk_level
        reasons.append("現貨指數接近最大痛點，短線可能以區間整理為主。")

    analysis = {
        "bias": bias,
        "riskLevel": risk_level,
        "supportLevel": support,
        "resistanceLevel": resistance,
        "maxPain": max_pain_strike,
        "reasons": reasons,
        "scenarios": [
            {
                "name": "偏多",
                "condition": "指數站上 Call OI 壓力區並伴隨 Put OI 下移。",
                "view": "短線上攻機率提高，但需留意 IV 回落造成權利金收縮。",
            },
            {
                "name": "震盪",
                "condition": "指數貼近最大痛點且 PCR 維持 0.8~1.2。",
                "view": "賣方時間價值優勢較明顯，突破前以區間與價差策略觀察。",
            },
            {
                "name": "偏空",
                "condition": "PCR 快速升高且跌破主要 Put OI 支撐。",
                "view": "避險需求升溫，需降低槓桿並檢查保證金風險。",
            },
        ],
        "disclaimer": "AI 分析僅依 TAIFEX 公開資料與系統計算產生，僅供研究參考，不保證獲利。",
    }
    return enrich_option_ai_decision(analysis, summary, chain, spot)


def build_taifex_txo_option_payload(
    rows: list[dict[str, Any]],
    trade_date: str,
    requested_expiry: str | None = None,
    underlying: str | None = "TXO",
    spot_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    product = get_taiwan_option_product(underlying)
    expiry_groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        expiry_groups.setdefault(str(row.get("expiry") or ""), []).append(row)
    expiries = []
    for code, group_rows in expiry_groups.items():
        group_summary = summarize_taifex_option_rows(group_rows)
        expiries.append({
            "code": code,
            "expiryDate": next((row.get("expiryDate") for row in group_rows if row.get("expiryDate")), ""),
            **group_summary,
        })
    expiries.sort(key=lambda item: (item.get("expiryDate") or "9999-12-31", item.get("code") or ""))
    selected = requested_expiry if requested_expiry in expiry_groups else None
    if selected is None:
        today = datetime.now(TZ).date()
        active_expiries = []
        for item in expiries:
            expiry_date_text = str(item.get("expiryDate") or "").strip()
            try:
                expiry_date = datetime.strptime(expiry_date_text, "%Y-%m-%d").date()
            except ValueError:
                continue
            if expiry_date >= today:
                active_expiries.append(item)
        selected = next(
            (item["code"] for item in active_expiries if item.get("totalOpenInterest", 0) > 0),
            next(
                (item["code"] for item in expiries if item.get("totalOpenInterest", 0) > 0),
                expiries[0]["code"] if expiries else "",
            ),
        )
    selected_rows = expiry_groups.get(selected, [])
    chain = build_taifex_option_chain(selected_rows)
    summary = summarize_taifex_option_rows(selected_rows)
    max_pain = calculate_taifex_max_pain(chain)
    spot_snapshot = spot_snapshot or fetch_taiwan_option_spot_snapshot(product["symbol"])
    spot = spot_snapshot.get("value")
    summary["maxPain"] = max_pain.get("strike")
    summary["maxPainLoss"] = max_pain.get("loss")
    summary["atmStrike"] = select_option_atm_strike(chain, spot, max_pain)
    return {
        "underlying": product["symbol"],
        "name": product["name"],
        "shortName": product["shortName"],
        "market": "台灣",
        "exchange": "TAIFEX",
        "tradeDate": trade_date,
        "selectedExpiry": selected,
        "selectedExpiryDate": next((item.get("expiryDate") for item in expiries if item.get("code") == selected), ""),
        "expirations": expiries,
        "summary": summary,
        "chain": chain,
        "distribution": build_taifex_option_distribution(chain),
        "spot": spot_snapshot,
        "analysis": build_taifex_option_ai_analysis(summary, chain, max_pain, spot),
        "schema": {
            "optionsProduct": product["symbol"],
            "optionsContractKey": "underlying + expiry + strike + option_type",
            "optionsQuoteFields": ["last", "bid", "ask", "volume", "openInterest", "impliedVolatility"],
            "analysisFields": ["putCallRatio", "maxPain", "supportLevel", "resistanceLevel", "riskLevel"],
        },
        "source": {
            "primary": product.get("sourceNote") or "TAIFEX 選擇權每日交易行情查詢",
            "primaryUrl": TAIFEX_OPTIONS_DAILY_URL,
            "mode": "taifex",
            "sourceContract": product.get("taifexCommodity"),
            "displayProduct": product["symbol"],
            "pcrUrl": TAIFEX_OPTIONS_PC_RATIO_URL,
            "ivNote": "TAIFEX 日報未提供完整 IV 欄位；IV 以價格、履約價、到期日與標的現貨估算，欄位保留供日後接合法行情 IV。",
        },
        "availableProducts": [
            {"symbol": key, "name": item["name"], "shortName": item["shortName"]}
            for key, item in TAIWAN_OPTION_PRODUCTS.items()
        ],
    }


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


def build_yahoo_txo_option_payload(
    rows: list[dict[str, Any]],
    trade_date: str,
    expiry_code: str,
    spot_snapshot: dict[str, Any],
    underlying: str | None = "TXO",
) -> dict[str, Any]:
    product = get_taiwan_option_product(underlying)
    chain = build_taifex_option_chain(rows)
    summary = summarize_taifex_option_rows(rows)
    max_pain = calculate_taifex_max_pain(chain)
    spot = spot_snapshot.get("value")
    summary["maxPain"] = max_pain.get("strike")
    summary["maxPainLoss"] = max_pain.get("loss")
    summary["atmStrike"] = select_option_atm_strike(chain, spot, max_pain)
    expirations = [{
        "code": expiry_code,
        "expiryDate": "",
        **summary,
    }]
    return {
        "underlying": product["symbol"],
        "name": product["name"],
        "shortName": product["shortName"],
        "market": "台灣",
        "exchange": "Yahoo 股市 / TAIFEX",
        "tradeDate": trade_date,
        "selectedExpiry": expiry_code,
        "selectedExpiryDate": "",
        "expirations": expirations,
        "summary": summary,
        "chain": chain,
        "distribution": build_taifex_option_distribution(chain),
        "spot": spot_snapshot,
        "analysis": build_taifex_option_ai_analysis(summary, chain, max_pain, spot),
        "schema": {
            "optionsProduct": product["symbol"],
            "optionsContractKey": "underlying + expiry + strike + option_type",
            "optionsQuoteFields": ["last", "bid", "ask", "volume", "openInterest", "quoteTime"],
            "analysisFields": ["putCallRatio", "maxPain", "supportLevel", "resistanceLevel", "riskLevel"],
        },
        "source": {
            "primary": "Yahoo 股市台灣選擇權報價",
            "primaryUrl": build_yahoo_taiwan_option_url(product["symbol"], expiry_code),
            "mode": "yahoo",
            "officialReference": "TAIFEX 選擇權每日交易行情查詢",
            "officialReferenceUrl": TAIFEX_OPTIONS_DAILY_URL,
            "ivNote": "Yahoo 頁面提供買進、賣出、成交、漲跌、未平倉、總量與時間；IV 若缺漏則不假造。",
        },
        "availableProducts": [
            {"symbol": key, "name": item["name"], "shortName": item["shortName"]}
            for key, item in TAIWAN_OPTION_PRODUCTS.items()
        ],
    }


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


def fetch_yahoo_txo_option_chain(expiry: str | None = None, underlying: str | None = "TXO") -> dict[str, Any]:
    product = get_taiwan_option_product(underlying)
    if not product.get("yahooOpcm"):
        return {
            "underlying": product["symbol"],
            "name": product["name"],
            "shortName": product["shortName"],
            "market": "台灣",
            "exchange": "Yahoo 股市",
            "error": f"{product['shortName']} 沒有 Yahoo 台灣選擇權逐履約價商品代碼，未使用 WTXO 代替。",
            "source": {"primary": "Yahoo 股市台灣選擇權報價", "primaryUrl": YAHOO_TW_OPTION_URL, "mode": "yahoo"},
            "availableProducts": [
                {"symbol": key, "name": item["name"], "shortName": item["shortName"]}
                for key, item in TAIWAN_OPTION_PRODUCTS.items()
            ],
        }
    now = time.time()
    cache_key = f"{product['symbol']}:{expiry or ''}"
    with cache_lock:
        cached = cache_data["yahoo_tw_option_chain"].get(cache_key)
    if cached and now - cached.get("stored_at", 0) < YAHOO_TW_OPTION_CACHE_SECONDS:
        return {**cached["payload"], "cached": True}
    yahoo_url = build_yahoo_taiwan_option_url(product["symbol"], expiry)
    html = fetch_text(yahoo_url, timeout=12)
    payload = parse_yahoo_txo_option_page(html, product["symbol"], expiry)
    if not payload.get("error"):
        with cache_lock:
            cache_data["yahoo_tw_option_chain"][cache_key] = {"stored_at": now, "payload": payload}
    return {**payload, "cached": False}


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


def fetch_txo_option_chain(
    expiry: str | None = None,
    market_date: str | None = None,
    source: str = "auto",
    underlying: str | None = "TXO",
) -> dict[str, Any]:
    return fetch_taiwan_option_chain(underlying=underlying, expiry=expiry, market_date=market_date, source=source)


def fetch_taiwan_option_chain(
    underlying: str | None = "TXO",
    expiry: str | None = None,
    market_date: str | None = None,
    source: str = "auto",
) -> dict[str, Any]:
    product = get_taiwan_option_product(underlying)
    source_mode = normalize_taiwan_option_source(source)
    if source_mode == "yahoo":
        return fetch_yahoo_txo_option_chain(expiry, product["symbol"])
    official = fetch_taifex_txo_option_chain(expiry=expiry, market_date=market_date, underlying=product["symbol"])
    if source_mode == "taifex" or not official.get("error"):
        return official
    try:
        fallback = fetch_yahoo_txo_option_chain(expiry, product["symbol"])
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Yahoo %s fallback failed after TAIFEX option-chain miss", product["symbol"], exc_info=exc)
        return official
    if fallback.get("error"):
        return {**official, "fallbackError": fallback.get("error")}
    return {
        **fallback,
        "fallbackFrom": "taifex",
        "fallbackReason": official.get("error"),
        "source": {
            **(fallback.get("source") or {}),
            "primary": "Yahoo 股市台灣選擇權報價（TAIFEX 官方日報暫無資料時後備）",
            "officialReference": "TAIFEX 選擇權每日交易行情查詢",
            "officialReferenceUrl": TAIFEX_OPTIONS_DAILY_URL,
            "mode": "auto-yahoo-fallback",
        },
    }


def fetch_taifex_txo_option_chain(
    expiry: str | None = None,
    market_date: str | None = None,
    underlying: str | None = "TXO",
) -> dict[str, Any]:
    product = get_taiwan_option_product(underlying)
    query_date = parse_taifex_query_date(market_date)
    cache_key = f"{product['symbol']}:{query_date}:{expiry or ''}"
    now = time.time()
    with cache_lock:
        cached = cache_data["taifex_options_chain"].get(cache_key)
    if cached and now - cached.get("stored_at", 0) < TAIFEX_OPTIONS_CHAIN_CACHE_SECONDS:
        return {**supplement_taifex_option_payload_with_yahoo_oi(cached["payload"]), "cached": True}

    with taifex_options_chain_inflight_lock:
        leader_event = taifex_options_chain_inflight.get(cache_key)
        is_leader = leader_event is None
        if is_leader:
            leader_event = threading.Event()
            taifex_options_chain_inflight[cache_key] = leader_event

    if not is_leader:
        leader_event.wait(timeout=30)
        with cache_lock:
            cached = cache_data["taifex_options_chain"].get(cache_key)
        if cached and time.time() - cached.get("stored_at", 0) < TAIFEX_OPTIONS_CHAIN_CACHE_SECONDS:
            return {**supplement_taifex_option_payload_with_yahoo_oi(cached["payload"]), "cached": True}
        # The leader's scan didn't leave a usable cache entry (e.g. no data for any
        # scanned date) -- fall through and run our own scan rather than giving up.

    try:
        requested = datetime.strptime(query_date, "%Y%m%d")
        for offset in range(12):
            target = requested - timedelta(days=offset)
            if target.weekday() >= 5:
                continue
            date_text = target.strftime("%Y/%m/%d")
            try:
                html = fetch_form_text(
                    TAIFEX_OPTIONS_DAILY_URL,
                    {
                        "queryType": "2",
                        "marketCode": "0",
                        "commodity_id": product["taifexCommodity"],
                        "commodity_idt": product["taifexCommodity"],
                        "queryDate": date_text,
                    },
                    timeout=18,
                )
                spot_snapshot = fetch_taiwan_option_spot_snapshot(product["symbol"])
                rows = parse_taifex_txo_option_rows(html, spot_snapshot.get("value"), product["symbol"])
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("TAIFEX %s option chain fetch failed for date=%s", product["symbol"], date_text, exc_info=exc)
                rows = []
            if not rows:
                continue
            payload = supplement_taifex_option_payload_with_yahoo_oi(
                build_taifex_txo_option_payload(rows, target.strftime("%Y-%m-%d"), expiry, product["symbol"], spot_snapshot)
            )
            with cache_lock:
                cache_data["taifex_options_chain"][cache_key] = {"stored_at": now, "payload": payload}
            return {**payload, "cached": False}
        return {
            "underlying": product["symbol"],
            "name": product["name"],
            "shortName": product["shortName"],
            "market": "台灣",
            "exchange": "TAIFEX",
            "error": PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE,
            "source": {"primary": "TAIFEX 選擇權每日交易行情查詢", "primaryUrl": TAIFEX_OPTIONS_DAILY_URL, "mode": "taifex"},
            "availableProducts": [
                {"symbol": key, "name": item["name"], "shortName": item["shortName"]}
                for key, item in TAIWAN_OPTION_PRODUCTS.items()
            ],
        }
    finally:
        if is_leader:
            with taifex_options_chain_inflight_lock:
                taifex_options_chain_inflight.pop(cache_key, None)
            leader_event.set()


def fetch_market_macro_factors(market_date: str) -> dict[str, Any]:
    tasks = {
        "dxy": lambda: build_yahoo_macro_snapshot("DX-Y.NYB"),
        "us10y": lambda: build_yahoo_macro_snapshot("^TNX"),
        "usdTwd": lambda: build_yahoo_macro_snapshot("TWD=X"),
        "marginTrading": fetch_twse_margin_summary,
        "txOpenInterest": lambda: fetch_taifex_tx_open_interest(market_date),
    }
    result: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {executor.submit(callback): key for key, callback in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                value = future.result()
            except Exception:  # noqa: BLE001
                value = None
            if value:
                result[key] = value
    return result


def parse_tdcc_holding_distributions(text: str) -> dict[str, dict[str, Any]]:
    distributions: dict[str, dict[str, Any]] = {}
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    for row in reader:
        code = str(row.get("證券代號") or "").strip()
        grade = parse_float(str(row.get("持股分級") or ""))
        ratio = parse_float(str(row.get("占集保庫存數比例%") or ""))
        if not code or grade is None or ratio is None or int(grade) >= 16:
            continue

        item = distributions.setdefault(
            code,
            {
                "date": str(row.get("資料日期") or "").strip(),
                "largeHolderRatio": 0.0,
                "retailHolderRatio": 0.0,
                "otherHolderRatio": 0.0,
            },
        )
        if int(grade) <= 3:
            item["retailHolderRatio"] += ratio
        elif int(grade) >= 12:
            item["largeHolderRatio"] += ratio
        else:
            item["otherHolderRatio"] += ratio

    for item in distributions.values():
        raw_date = item["date"]
        if re.fullmatch(r"\d{8}", raw_date):
            item["date"] = datetime.strptime(raw_date, "%Y%m%d").strftime("%Y-%m-%d")
        for key in ("largeHolderRatio", "retailHolderRatio", "otherHolderRatio"):
            item[key] = round(item[key], 2)
        item["largeHolderThreshold"] = "400 張以上"
        item["retailHolderThreshold"] = "10 張以下"
        item["source"] = "臺灣集中保管結算所"
        item["sourceLink"] = TDCC_HOLDING_DISTRIBUTION_URL
    return distributions


def fetch_shareholder_distribution(code: str) -> dict[str, Any]:
    def unavailable(reason: str) -> dict[str, Any]:
        return {
            "available": False,
            "date": "--",
            "largeHolderRatio": None,
            "retailHolderRatio": None,
            "otherHolderRatio": None,
            "largeHolderThreshold": "400 張以上",
            "retailHolderThreshold": "10 張以下",
            "source": "臺灣集中保管結算所",
            "sourceLink": TDCC_HOLDING_DISTRIBUTION_URL,
            "sourceNote": reason,
        }

    normalized_code = str(code or "").strip().upper()
    now = time.time()
    with cache_lock:
        stored_at = cache_data["shareholder_distributions_stored_at"]
        cached = cache_data["shareholder_distributions"].get(normalized_code)
        cache_fresh = bool(stored_at and now - stored_at < TDCC_HOLDING_CACHE_SECONDS)
    if cache_fresh:
        return cached or unavailable("集保持股分布目前未提供此代號資料。")

    try:
        distributions = parse_tdcc_holding_distributions(fetch_tdcc_holding_distribution_text(timeout=12))
    except Exception:  # noqa: BLE001
        LOGGER.exception("TDCC shareholder distribution fetch failed")
        if cached:
            return {
                **cached,
                "stale": True,
                "sourceNote": "集保資料來源暫時無法連線，顯示最近一次快取資料。",
            }
        return unavailable("集保資料來源暫時無法連線。")
    if not distributions:
        if cached:
            return {
                **cached,
                "stale": True,
                "sourceNote": "集保資料來源暫時未回傳可解析資料，顯示最近一次快取資料。",
            }
        return unavailable("集保資料來源暫時未回傳可解析資料。")
    with cache_lock:
        cache_data["shareholder_distributions"] = distributions
        cache_data["shareholder_distributions_stored_at"] = now
    return distributions.get(normalized_code, unavailable("集保持股分布目前未提供此代號資料。"))


class VisibleTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "article",
        "aside",
        "div",
        "footer",
        "header",
        "li",
        "main",
        "nav",
        "p",
        "section",
        "table",
        "tbody",
        "td",
        "th",
        "tr",
        "ul",
        "ol",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "a",
        "button",
        "span",
        "strong",
    }

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self._buffer: list[str] = []
        self._skip_depth = 0

    def _flush(self) -> None:
        if not self._buffer:
            return
        line = re.sub(r"\s+", " ", " ".join(self._buffer)).strip()
        if line:
            self.lines.append(line)
        self._buffer = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # noqa: ARG002
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "br" or tag in self.BLOCK_TAGS:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = unescape(data or "").strip()
        if cleaned:
            self._buffer.append(cleaned)

    def close(self) -> None:
        self._flush()
        super().close()


def extract_visible_text_lines(html: str) -> list[str]:
    extractor = VisibleTextExtractor()
    extractor.feed(html or "")
    extractor.close()
    return extractor.lines


class YahooClassCatalogParser(HTMLParser):
    GROUP_KEYS = {
        "上市類股": "listed",
        "上櫃類股": "otc",
        "興櫃類股": "emerging",
        "電子產業": "electronic",
        "概念股": "concept",
        "集團股": "group",
    }

    def __init__(self) -> None:
        super().__init__()
        self.catalog: dict[str, list[dict[str, str]]] = {key: [] for key in self.GROUP_KEYS.values()}
        self.current_group: str | None = None
        self.capture_h2 = False
        self.h2_text: list[str] = []
        self.anchor_href: str | None = None
        self.anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self.capture_h2 = True
            self.h2_text = []
        elif tag == "a":
            self.anchor_href = dict(attrs).get("href")
            self.anchor_text = []

    def handle_data(self, data: str) -> None:
        text = unescape(data or "").strip()
        if not text:
            return
        if self.capture_h2:
            self.h2_text.append(text)
        if self.anchor_href is not None:
            self.anchor_text.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            heading = " ".join(self.h2_text).strip()
            self.current_group = self.GROUP_KEYS.get(heading)
            self.capture_h2 = False
            self.h2_text = []
            return
        if tag != "a" or self.anchor_href is None:
            return

        name = " ".join(self.anchor_text).strip()
        href = self.anchor_href
        if self.current_group and name and "/class-quote?" in href:
            url = urljoin(YAHOO_CLASS_HOME_URL, href)
            if not any(item["url"] == url for item in self.catalog[self.current_group]):
                self.catalog[self.current_group].append({"name": name, "url": url})
        self.anchor_href = None
        self.anchor_text = []


def fetch_yahoo_sector_catalog(timeout: int = 8) -> dict[str, list[dict[str, str]]]:
    html = fetch_text(YAHOO_CLASS_HOME_URL, timeout=timeout)
    parser = YahooClassCatalogParser()
    parser.feed(html)
    parser.close()
    return parser.catalog


def extract_balanced_segment(text: str, start_index: int, open_char: str, close_char: str) -> str | None:
    if start_index < 0 or start_index >= len(text) or text[start_index] != open_char:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start_index, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == open_char:
            depth += 1
            continue
        if char == close_char:
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]
    return None


def parse_yahoo_class_quote_json_list(html: str, exchange: str, sector_id: str) -> list[dict[str, Any]]:
    params_marker = f'"params":{{"exchange":"{exchange}","sectorId":"{sector_id}","offset":0}}'
    params_index = html.find(params_marker)
    if params_index < 0:
        params_match = re.search(
            rf'"params":\{{"exchange":"{re.escape(exchange)}","sectorId":"{re.escape(sector_id)}","offset":0\}}',
            html,
        )
        if not params_match:
            return []
        params_index = params_match.start()

    list_key_index = html.find('"list":', params_index)
    if list_key_index < 0:
        return []

    list_start = html.find("[", list_key_index)
    if list_start < 0:
        return []

    segment = extract_balanced_segment(html, list_start, "[", "]")
    if not segment:
        return []

    sanitized_segment = re.sub(r"(?<![\w$])undefined(?![\w$])", "null", segment)
    try:
        payload = json.loads(sanitized_segment)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def parse_yahoo_class_quote_embedded_list(html: str) -> list[dict[str, Any]]:
    for match in re.finditer(r'"params":\{([^{}]+)\},"list":', html):
        params_text = match.group(1)
        if '"offset":0' not in params_text:
            continue
        if '"exchange":' not in params_text and '"category":' not in params_text:
            continue

        list_start = html.find("[", match.end())
        if list_start < 0:
            continue
        segment = extract_balanced_segment(html, list_start, "[", "]")
        if not segment:
            continue

        sanitized_segment = re.sub(r"(?<![\w$])undefined(?![\w$])", "null", segment)
        try:
            payload = json.loads(sanitized_segment)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
    return []


def parse_yahoo_class_quote_date(html: str) -> str | None:
    match = re.search(r'<time[^>]*datatime="(\d{4}/\d{2}/\d{2})"', html, re.IGNORECASE)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y/%m/%d").strftime("%Y-%m-%d")
    except ValueError:
        return match.group(1)


def yahoo_field_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("fmt", "raw"):
            item = value.get(key)
            if item not in (None, ""):
                return str(item)
        return "--"
    if value in (None, ""):
        return "--"
    return str(value)


def parse_yahoo_quote_items(
    payload: list[dict[str, Any]],
    snapshot_date: str | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    note_suffix = f" · {snapshot_date}" if snapshot_date else ""
    for item in payload:
        price = item.get("price") if isinstance(item.get("price"), dict) else {}
        change = item.get("change") if isinstance(item.get("change"), dict) else {}
        symbol_name = str(
            item.get("symbolName")
            or item.get("relatedSymbolName")
            or item.get("symbol")
            or item.get("messageBoardId")
            or ""
        ).strip()
        symbol_code = str(item.get("symbol") or item.get("messageBoardId") or symbol_name).strip()
        change_value = parse_float(str(change.get("raw") if isinstance(change, dict) else item.get("change") or "").replace("%", ""))
        pct_value = parse_float(str(item.get("changePercent") or "").replace("%", ""))
        rows.append(
            {
                "name": symbol_name or symbol_code,
                "code": symbol_code,
                "exchange": str(item.get("exchange") or ""),
                "value": yahoo_field_text(price),
                "change": format_signed(change_value) if change_value is not None else yahoo_field_text(change),
                "pct": format_percent(pct_value) if pct_value is not None else str(item.get("changePercent") or "--"),
                "open": yahoo_field_text(item.get("regularMarketOpen")),
                "previousClose": yahoo_field_text(item.get("regularMarketPreviousClose")),
                "high": yahoo_field_text(item.get("regularMarketDayHigh")),
                "low": yahoo_field_text(item.get("regularMarketDayLow")),
                "volume": yahoo_field_text(item.get("volume") or item.get("singleVolume")),
                "turnoverM": yahoo_field_text(item.get("turnoverM")),
                "time": yahoo_field_text(item.get("regularMarketTime")),
                "note": "同步資料" + note_suffix,
            }
        )
    return rows


def parse_yahoo_class_quote_rows(html: str) -> tuple[list[dict[str, Any]], str | None, str | None]:
    title = None
    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.IGNORECASE)
    if title_match:
        title = unescape(title_match.group(1)).strip()

    snapshot_date = parse_yahoo_class_quote_date(html)

    exchange_match = re.search(r'"params":\{"exchange":"([^"]+)","sectorId":"([^"]+)","offset":0\}', html)
    rows: list[dict[str, Any]] = []
    payload: list[dict[str, Any]] = []
    if exchange_match:
        exchange = exchange_match.group(1)
        sector_id = exchange_match.group(2)
        payload = parse_yahoo_class_quote_json_list(html, exchange, sector_id)
    if not payload:
        payload = parse_yahoo_class_quote_embedded_list(html)
    if payload:
        rows = parse_yahoo_quote_items(payload, snapshot_date)
        if rows:
            return rows, snapshot_date, title

    lines = [line.strip() for line in extract_visible_text_lines(html) if line.strip()]
    if not lines:
        return [], snapshot_date, title

    header_index = next((index for index, line in enumerate(lines) if "股票名稱/代號" in line), None)
    if header_index is None:
        return [], snapshot_date, title

    start_index = next((index for index in range(header_index + 1, len(lines)) if lines[index].startswith("*")), len(lines))
    index = start_index
    while index < len(lines):
        token = lines[index].lstrip()
        if not token.startswith("*"):
            index += 1
            continue

        name = token.lstrip("*").strip()
        cursor = index + 1
        if not name and cursor < len(lines):
            name = lines[cursor].strip()
            cursor += 1
        if cursor >= len(lines):
            break

        code = lines[cursor].strip()
        if not (code.startswith("^") or re.fullmatch(r"(?:[A-Z0-9]{2,12}(?:\.[A-Z]{2,3})?)", code, re.IGNORECASE)):
            index += 1
            continue
        cursor += 1

        values: list[str] = []
        while cursor < len(lines) and len(values) < 9:
            current = lines[cursor].strip()
            cursor += 1
            if not current:
                continue
            if current in {"即時行情", "法人買賣", "股票名稱/代號", "股價", "漲跌", "漲跌幅(%)", "開盤", "昨收", "最高", "最低", "成交量(張)", "時間"}:
                continue
            values.append(current)

        if len(values) < 9:
            index += 1
            continue

        value, change, pct, open_value, previous_close, high_value, low_value, volume, time_value = values[:9]
        rows.append(
            {
                "name": name,
                "code": code,
                "exchange": "",
                "value": value,
                "change": change,
                "pct": pct,
                "open": open_value,
                "previousClose": previous_close,
                "high": high_value,
                "low": low_value,
                "volume": volume,
                "time": time_value,
                "note": "同步資料" + (f" · {snapshot_date}" if snapshot_date else ""),
            }
        )
        index = cursor

    return rows, snapshot_date, title


def fetch_yahoo_class_quote_pages(
    url: str,
    snapshot_date: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    query = dict(parse_qsl(urlsplit(url).query))
    if not query:
        return []
    if query.get("category"):
        query["categoryName"] = query.pop("category")

    def fetch_page(offset: int) -> dict[str, Any]:
        params = {**query, "offset": str(offset)}
        resource_params = ";".join(
            f"{quote(str(key), safe='')}={quote(str(value), safe='')}"
            for key, value in params.items()
            if value not in (None, "")
        )
        payload = fetch_json(
            f"https://tw.stock.yahoo.com/_td-stock/api/resource/StockServices.getClassQuotes;{resource_params}",
            timeout=10,
        )
        return payload if isinstance(payload, dict) else {}

    first_payload = fetch_page(0)
    first_items = first_payload.get("list", [])
    if not first_items:
        return []
    pagination = first_payload.get("pagination", {})
    results_total = int(parse_float(str(pagination.get("resultsTotal") or "")) or len(first_items))
    target_count = min(limit, results_total)
    page_size = len(first_items)
    payloads = [first_payload]
    offsets = list(range(page_size, target_count, page_size))
    if offsets:
        with ThreadPoolExecutor(max_workers=min(8, len(offsets))) as executor:
            futures = {executor.submit(fetch_page, offset): offset for offset in offsets}
            fetched = []
            for future in as_completed(futures):
                try:
                    fetched.append((futures[future], future.result()))
                except Exception:  # noqa: BLE001
                    continue
            payloads.extend(payload for _, payload in sorted(fetched))

    rows: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for payload in payloads:
        for row in parse_yahoo_quote_items(payload.get("list", []), snapshot_date):
            code = str(row.get("code") or "").upper()
            if code and code not in seen_codes:
                seen_codes.add(code)
                rows.append(row)
                if len(rows) >= limit:
                    return rows
    return rows


def build_yahoo_class_quote_cards(
    url: str,
    prefix: str,
    limit: int = 6,
    timeout: int = 8,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        html = fetch_text(url, timeout=timeout)
    except Exception:  # noqa: BLE001
        return [], None

    rows, snapshot_date, _ = parse_yahoo_class_quote_rows(html)
    if len(rows) < limit:
        try:
            paged_rows = fetch_yahoo_class_quote_pages(url, snapshot_date, limit)
            if paged_rows:
                rows = paged_rows
        except Exception:  # noqa: BLE001
            pass
    cards: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:limit]):
        change_value = parse_float(str(row.get("change", "")).replace("%", ""))
        pct_value = parse_float(str(row.get("pct", "")).replace("%", ""))
        price_value = parse_float(str(row.get("value") or ""))
        open_value = parse_float(str(row.get("open") or ""))
        high_value = parse_float(str(row.get("high") or ""))
        low_value = parse_float(str(row.get("low") or ""))
        previous_close = parse_float(str(row.get("previousClose") or ""))
        raw_volume = parse_float(str(row.get("volume") or ""))
        raw_turnover_m = parse_float(str(row.get("turnoverM") or ""))
        is_equity = bool(
            re.fullmatch(
                r"\d{4,6}[A-Z]?(?:\.(?:TW|TWO))?",
                str(row.get("code") or ""),
                re.IGNORECASE,
            )
        )
        volume_shares = raw_volume if is_equity else None
        volume_lots = (volume_shares / 1000) if volume_shares is not None else raw_volume
        turnover_value = (
            raw_turnover_m * 1_000_000
            if raw_turnover_m is not None and raw_turnover_m > 0
            else price_value * volume_shares
            if price_value is not None and volume_shares is not None
            else None
        )
        cards.append(
            {
                "name": str(row.get("name") or f"{prefix}{index + 1}"),
                "value": str(row.get("value") or "--"),
                "change": str(row.get("change") or "--"),
                "pct": str(row.get("pct") or "--"),
                "tone": detect_tone(change_value if change_value is not None else pct_value),
                "open": str(row.get("open") or "--"),
                "high": str(row.get("high") or "--"),
                "low": str(row.get("low") or "--"),
                "previousClose": str(row.get("previousClose") or "--"),
                "time": str(row.get("time") or "--"),
                "volume": format_whole_number(volume_lots) if volume_lots is not None else "--",
                "volumeValue": volume_lots,
                "turnover": format_whole_number(turnover_value) if turnover_value is not None else "--",
                "turnoverValue": turnover_value,
                "note": str(row.get("note") or ""),
                "sourceName": str(row.get("code") or row.get("name") or f"{prefix}{index + 1}"),
                "exchange": str(row.get("exchange") or ""),
                "summaryOnly": True,
                "technicalAnalysis": build_intraday_technical_analysis(
                    open_value=open_value,
                    high_value=high_value,
                    low_value=low_value,
                    close_value=price_value,
                    signed_change=change_value,
                    pct=pct_value,
                ),
            }
        )

    valid_cards = [
        card
        for card in cards
        if card.get("value") not in (None, "", "--", "-")
    ]
    if valid_cards:
        cards = valid_cards
    return cards, snapshot_date


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


def build_yahoo_sector_groups(limit: int = 30, timeout: int = 8) -> tuple[dict[str, list[dict[str, Any]]], dict[str, str | None]]:
    specs = {
        "listed": (YAHOO_LISTED_CLASS_URL, "上市"),
        "otc": (YAHOO_TPEX_OTC_CLASS_URL, "上櫃"),
        "emerging": (YAHOO_TPEX_EMERGING_CLASS_URL, "興櫃"),
        "electronic": (YAHOO_ELECTRONIC_CLASS_URL, "電子"),
        "concept": (YAHOO_CONCEPT_CLASS_URL, "概念"),
        "group": (YAHOO_GROUP_CLASS_URL, "集團"),
    }
    groups: dict[str, list[dict[str, Any]]] = {}
    dates: dict[str, str | None] = {}

    def fetch_group(key: str, url: str, prefix: str) -> tuple[str, list[dict[str, Any]], str | None]:
        try:
            cards, snapshot_date = build_yahoo_class_quote_cards(url, prefix, limit=limit, timeout=timeout)
        except Exception:  # noqa: BLE001
            cards, snapshot_date = [], None
        return key, cards, snapshot_date

    with ThreadPoolExecutor(max_workers=len(specs)) as executor:
        futures = [
            executor.submit(fetch_group, key, url, prefix)
            for key, (url, prefix) in specs.items()
        ]
        for future in as_completed(futures):
            key, cards, snapshot_date = future.result()
            groups[key] = cards
            dates[key] = snapshot_date

    for key in specs:
        groups.setdefault(key, [])
        dates.setdefault(key, None)
    return groups, dates


def build_yahoo_summary_series(
    cards: list[dict[str, Any]],
    benchmark_day_series: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    if not cards or not benchmark_day_series or len(benchmark_day_series) < 2:
        return cards

    previous_day = benchmark_day_series[-2]
    latest_day = benchmark_day_series[-1]
    previous_date = str(previous_day.get("date") or "")
    latest_date = str(latest_day.get("date") or "")
    if not previous_date or not latest_date:
        return cards

    enriched_cards: list[dict[str, Any]] = []
    for card in cards:
        current_close = parse_float(str(card.get("value") or ""))
        previous_close = parse_float(str(card.get("previousClose") or ""))
        if current_close is None or previous_close is None:
            enriched_cards.append(card)
            continue

        open_value = parse_float(str(card.get("open") or "")) or previous_close
        high_value = parse_float(str(card.get("high") or "")) or current_close
        low_value = parse_float(str(card.get("low") or "")) or current_close
        change_value = current_close - previous_close
        volume_value = str(card.get("volume") or "--")
        turnover_value = str(card.get("turnover") or "--")

        enriched_cards.append(
            {
                **card,
                "open": f"{open_value:.2f}",
                "high": f"{high_value:.2f}",
                "low": f"{low_value:.2f}",
                "previousClose": f"{previous_close:.2f}",
                "candles": [
                    {
                        "date": previous_date,
                        "open": f"{previous_close:.2f}",
                        "high": f"{previous_close:.2f}",
                        "low": f"{previous_close:.2f}",
                        "close": f"{previous_close:.2f}",
                        "change": format_signed(0.0),
                        "volume": volume_value,
                        "turnover": turnover_value,
                    },
                    {
                        "date": latest_date,
                        "open": f"{open_value:.2f}",
                        "high": f"{high_value:.2f}",
                        "low": f"{low_value:.2f}",
                        "close": f"{current_close:.2f}",
                        "change": format_signed(change_value),
                        "volume": volume_value,
                        "turnover": turnover_value,
                    },
                ],
                "comparisonSeries": {
                    "day": [
                        {
                            "date": previous_date,
                            "close": f"{previous_close:.2f}",
                            "volume": volume_value,
                            "turnover": turnover_value,
                        },
                        {
                            "date": latest_date,
                            "close": f"{current_close:.2f}",
                            "volume": volume_value,
                            "turnover": turnover_value,
                        },
                    ]
                },
                "chartIntervals": {
                    "supported": ["day", "week"],
                    "intradayAvailable": False,
                    "intradayUnavailableReason": "上櫃與興櫃以日線比較為主。",
                },
            }
        )

    return enriched_cards


def build_market_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str, "type": "ALLBUT0999"}
    return f"{TWSE_BASE}/exchangeReport/MI_INDEX?{urlencode(params)}"


def build_institutions_url(date_str: str) -> str:
    params = {"response": "json", "dayDate": date_str, "type": "day"}
    return f"{TWSE_BASE}/fund/BFI82U?{urlencode(params)}"


def build_stock_institutions_url(date_str: str) -> str:
    params = {"date": date_str, "selectType": "ALLBUT0999", "response": "json"}
    return f"{TWSE_BASE}/rwd/zh/fund/T86?{urlencode(params)}"


def pick_mapping_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def fetch_twse_listed_industry_map(timeout: int = 12) -> dict[str, str]:
    now = time.monotonic()
    with cache_lock:
        cached = cache_data.get("twse_company_industries") or {}
        cached_items = cached.get("items")
        if (
            isinstance(cached_items, dict)
            and cached_items
            and now - float(cached.get("stored_at") or 0) <= TWSE_COMPANY_INDUSTRY_CACHE_SECONDS
        ):
            return dict(cached_items)

    try:
        rows = fetch_json(f"{TWSE_OPENAPI_BASE}/opendata/t187ap03_L", timeout=timeout)
    except Exception:  # noqa: BLE001
        LOGGER.exception("TWSE listed industry map fetch failed")
        return {}

    items: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        code = pick_mapping_text(row, "公司代號", "SecuritiesCompanyCode", "Code", "代號")
        industry_code = pick_mapping_text(row, "產業別", "SecuritiesIndustryCode", "Industry", "industry")
        industry = TWSE_INDUSTRY_CODE_NAMES.get(industry_code.zfill(2), industry_code)
        if code and industry and industry != "--":
            items[code] = industry

    if items:
        with cache_lock:
            cache_data["twse_company_industries"] = {"stored_at": now, "items": dict(items)}
    return items


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


def fetch_stock_institutions_payload_near(date_str: str, lookback_days: int = 7) -> tuple[dict[str, Any], str]:
    try:
        base_date = datetime.strptime(str(date_str), "%Y%m%d").date()
    except ValueError:
        base_date = taipei_now().date()

    for offset in range(lookback_days + 1):
        target = (base_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            payload = fetch_json(build_stock_institutions_url(target), timeout=15)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            LOGGER.warning("TWSE T86 sector fund flow fetch failed for date=%s: %s", target, exc)
            continue
        if dataset_has_rows(payload):
            return payload, target
    return {}, date_str


def format_fund_flow_amount(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{format_signed(value / 100_000_000, 1)} 億"


def build_sector_fund_flow(stocks: list[dict[str, Any]], market_date: str) -> dict[str, Any]:
    now = time.monotonic()
    cache_key = str(market_date or "")
    with cache_lock:
        cached = cache_data.get("sector_fund_flow") or {}
        if (
            cached.get("date_key") == cache_key
            and cached.get("payload")
            and now - float(cached.get("stored_at") or 0) <= SECTOR_FUND_FLOW_CACHE_SECONDS
        ):
            return copy.deepcopy(cached["payload"])

    try:
        institution_payload, report_date = fetch_stock_institutions_payload_near(market_date)
        industry_map = fetch_twse_listed_industry_map()
        if not dataset_has_rows(institution_payload) or not industry_map:
            raise RuntimeError("TWSE T86 or industry map unavailable")

        stock_lookup = {
            str(stock.get("code") or "").strip(): stock
            for stock in stocks
            if str(stock.get("market") or "TWSE").upper() == "TWSE"
            and not is_etf_stock(stock)
            and str(stock.get("code") or "").strip()
        }
        sectors: dict[str, dict[str, Any]] = {}

        for row in institution_payload.get("data", []):
            if not isinstance(row, list) or len(row) < 19:
                continue
            code = str(row[0] or "").strip()
            stock = stock_lookup.get(code)
            industry = industry_map.get(code)
            if not stock or not industry:
                continue

            close_value = parse_float(str(stock.get("close") or ""))
            if close_value is None or close_value <= 0:
                continue

            foreign_shares = parse_float(str(row[4])) if len(row) > 4 else None
            trust_shares = parse_float(str(row[10])) if len(row) > 10 else None
            dealer_shares = parse_float(str(row[11])) if len(row) > 11 else None
            total_shares = parse_float(str(row[18])) if len(row) > 18 else None
            if total_shares is None:
                components = [foreign_shares, trust_shares, dealer_shares]
                if not any(value is not None for value in components):
                    continue
                total_shares = sum(value or 0.0 for value in components)

            foreign_amount = (foreign_shares or 0.0) * close_value
            trust_amount = (trust_shares or 0.0) * close_value
            dealer_amount = (dealer_shares or 0.0) * close_value
            net_amount = total_shares * close_value
            pct_value = parse_float(str(stock.get("pct") or "").replace("%", ""))
            turnover_value = parse_float(str(stock.get("turnover") or ""))

            sector = sectors.setdefault(
                industry,
                {
                    "name": industry,
                    "netAmountValue": 0.0,
                    "foreignAmountValue": 0.0,
                    "trustAmountValue": 0.0,
                    "dealerAmountValue": 0.0,
                    "netSharesValue": 0.0,
                    "foreignSharesValue": 0.0,
                    "trustSharesValue": 0.0,
                    "dealerSharesValue": 0.0,
                    "turnoverValue": 0.0,
                    "stockCount": 0,
                    "advancers": 0,
                    "decliners": 0,
                    "pctValues": [],
                    "topStocks": [],
                },
            )
            sector["netAmountValue"] += net_amount
            sector["foreignAmountValue"] += foreign_amount
            sector["trustAmountValue"] += trust_amount
            sector["dealerAmountValue"] += dealer_amount
            sector["netSharesValue"] += total_shares
            sector["foreignSharesValue"] += foreign_shares or 0.0
            sector["trustSharesValue"] += trust_shares or 0.0
            sector["dealerSharesValue"] += dealer_shares or 0.0
            sector["stockCount"] += 1
            if turnover_value is not None:
                sector["turnoverValue"] += turnover_value
            if pct_value is not None:
                sector["pctValues"].append(pct_value)
                if pct_value > 0:
                    sector["advancers"] += 1
                elif pct_value < 0:
                    sector["decliners"] += 1
            sector["topStocks"].append(
                {
                    "code": code,
                    "name": str(stock.get("name") or row[1] or "").strip(),
                    "close": stock.get("close") or "--",
                    "closeValue": close_value,
                    "pct": stock.get("pct") or "--",
                    "tone": detect_tone(net_amount),
                    "netAmountValue": net_amount,
                    "foreignAmountValue": foreign_amount,
                    "trustAmountValue": trust_amount,
                    "dealerAmountValue": dealer_amount,
                    "netLotsValue": total_shares / 1000,
                    "absNetAmountValue": abs(net_amount),
                }
            )

        rows: list[dict[str, Any]] = []
        total_abs_net = sum(abs(item["netAmountValue"]) for item in sectors.values())
        for sector in sectors.values():
            pct_values = sector.pop("pctValues", [])
            avg_pct = sum(pct_values) / len(pct_values) if pct_values else None
            penny_stocks = []
            for stock in sector["topStocks"]:
                close_value = stock.get("closeValue")
                if close_value is None or close_value <= 0 or close_value > 50:
                    continue
                pct_value = parse_float(str(stock.get("pct") or "").replace("%", "")) or 0.0
                net_value = stock.get("netAmountValue") or 0.0
                flow_strength = min(15.0, math.log10(abs(net_value) + 1.0) * 1.5)
                score = 50.0 + pct_value * 4.0 + (10.0 if net_value > 0 else -8.0) + flow_strength - (close_value / 50.0 * 5.0)
                penny_stocks.append(
                    {
                        "code": stock.get("code"),
                        "name": stock.get("name"),
                        "close": stock.get("close"),
                        "closeValue": close_value,
                        "pct": stock.get("pct"),
                        "pctValue": pct_value,
                        "tone": detect_tone(pct_value),
                        "netAmountValue": net_value,
                        "netAmount": format_fund_flow_amount(net_value),
                        "score": max(0, min(99, round(score))),
                    }
                )
            penny_stocks.sort(
                key=lambda item: (
                    item.get("score") or 0,
                    item.get("netAmountValue") or 0,
                    item.get("pctValue") or 0,
                ),
                reverse=True,
            )
            top_stocks = sorted(
                sector["topStocks"],
                key=lambda item: item.get("absNetAmountValue") or 0,
                reverse=True,
            )[:4]
            for stock in top_stocks:
                stock.pop("absNetAmountValue", None)
                stock["netAmount"] = format_fund_flow_amount(stock.get("netAmountValue"))
                stock["foreignAmount"] = format_fund_flow_amount(stock.get("foreignAmountValue"))
                stock["trustAmount"] = format_fund_flow_amount(stock.get("trustAmountValue"))
                stock["dealerAmount"] = format_fund_flow_amount(stock.get("dealerAmountValue"))

            net_amount = sector["netAmountValue"]
            rows.append(
                {
                    "name": sector["name"],
                    "tone": detect_tone(net_amount),
                    "netAmountValue": net_amount,
                    "netAmount": format_fund_flow_amount(net_amount),
                    "foreignAmountValue": sector["foreignAmountValue"],
                    "foreignAmount": format_fund_flow_amount(sector["foreignAmountValue"]),
                    "trustAmountValue": sector["trustAmountValue"],
                    "trustAmount": format_fund_flow_amount(sector["trustAmountValue"]),
                    "dealerAmountValue": sector["dealerAmountValue"],
                    "dealerAmount": format_fund_flow_amount(sector["dealerAmountValue"]),
                    "netLotsValue": sector["netSharesValue"] / 1000,
                    "foreignLotsValue": sector["foreignSharesValue"] / 1000,
                    "trustLotsValue": sector["trustSharesValue"] / 1000,
                    "dealerLotsValue": sector["dealerSharesValue"] / 1000,
                    "turnoverValue": sector["turnoverValue"],
                    "stockCount": sector["stockCount"],
                    "advancers": sector["advancers"],
                    "decliners": sector["decliners"],
                    "avgPctValue": avg_pct,
                    "avgPct": format_percent(avg_pct),
                    "flowSharePct": (abs(net_amount) / total_abs_net * 100) if total_abs_net else 0,
                    "topStocks": top_stocks,
                    "pennyStocks": penny_stocks[:12],
                    "pennyStockCount": len(penny_stocks),
                }
            )

        ranked_rows = sorted(rows, key=lambda item: abs(item.get("netAmountValue") or 0), reverse=True)
        inflows = sorted(
            [item for item in ranked_rows if (item.get("netAmountValue") or 0) > 0],
            key=lambda item: item.get("netAmountValue") or 0,
            reverse=True,
        )
        outflows = sorted(
            [item for item in ranked_rows if (item.get("netAmountValue") or 0) < 0],
            key=lambda item: item.get("netAmountValue") or 0,
        )
        net_buy_total = sum(item.get("netAmountValue") or 0 for item in inflows)
        net_sell_total = sum(item.get("netAmountValue") or 0 for item in outflows)
        report_date_iso = datetime.strptime(report_date, "%Y%m%d").strftime("%Y-%m-%d")
        market_date_iso = datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d")
        payload = {
            "available": bool(ranked_rows),
            "date": report_date_iso,
            "marketDate": market_date_iso,
            "rows": ranked_rows,
            "inflows": inflows[:10],
            "outflows": outflows[:10],
            "netBuyTotalValue": net_buy_total,
            "netBuyTotal": format_fund_flow_amount(net_buy_total),
            "netSellTotalValue": net_sell_total,
            "netSellTotal": format_fund_flow_amount(net_sell_total),
            "netTotalValue": net_buy_total + net_sell_total,
            "netTotal": format_fund_flow_amount(net_buy_total + net_sell_total),
            "coveredStockCount": sum(item.get("stockCount") or 0 for item in ranked_rows),
            "sectorCount": len(ranked_rows),
            "unit": "新台幣億元",
            "source": "TWSE T86 + TWSE OpenAPI",
            "sourceLink": build_stock_institutions_url(report_date),
            "sourceNote": "以證交所 T86 法人買賣超股數乘以當日收盤價估算，涵蓋上市普通股並排除 ETF/特殊商品。",
        }
    except Exception:  # noqa: BLE001
        LOGGER.exception("Sector fund flow build failed")
        payload = {
            "available": False,
            "date": "",
            "marketDate": "",
            "rows": [],
            "inflows": [],
            "outflows": [],
            "source": "TWSE T86 + TWSE OpenAPI",
            "sourceLink": build_stock_institutions_url(market_date) if re.fullmatch(r"\d{8}", str(market_date or "")) else "",
            "sourceNote": "類股資金流向暫時無法同步，請稍後重新整理。",
        }

    with cache_lock:
        cache_data["sector_fund_flow"] = {
            "date_key": cache_key,
            "stored_at": now,
            "payload": copy.deepcopy(payload),
        }
    return payload


def fetch_stock_valuation(stock: dict[str, Any]) -> dict[str, Any]:
    market = str(stock.get("market") or "TWSE").upper()
    if market == "TPEX":
        rows = fetch_json(build_tpex_openapi_url("tpex_mainboard_peratio_analysis"), timeout=10)
        code_key = "SecuritiesCompanyCode"
        field_map = {
            "date": "Date",
            "peRatio": "PriceEarningRatio",
            "dividendYield": "YieldRatio",
            "pbRatio": "PriceBookRatio",
            "dividendPerShare": "DividendPerShare",
        }
    else:
        rows = fetch_json(f"{TWSE_OPENAPI_BASE}/exchangeReport/BWIBBU_ALL", timeout=10)
        code_key = "Code"
        field_map = {
            "date": "Date",
            "peRatio": "PEratio",
            "dividendYield": "DividendYield",
            "pbRatio": "PBratio",
        }
    if not isinstance(rows, list):
        return {}
    matched = next((row for row in rows if str(row.get(code_key, "")).strip() == str(stock["code"])), None)
    if not matched:
        return {}
    result = {
        key: (str(matched.get(source_key, "")).strip() or "--")
        for key, source_key in field_map.items()
    }
    raw_date = result.get("date", "")
    if re.fullmatch(r"\d{7}", raw_date):
        result["date"] = f"{int(raw_date[:3]) + 1911}-{raw_date[3:5]}-{raw_date[5:7]}"
    return result


def fetch_stock_valuation_on_date(stock: dict[str, Any], date_str: str) -> dict[str, Any]:
    market = str(stock.get("market") or "TWSE").upper()
    code = str(stock["code"])
    if market == "TPEX":
        date_value = datetime.strptime(date_str, "%Y%m%d").strftime("%Y/%m/%d")
        payload = fetch_json(
            f"https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate?"
            + urlencode({"date": date_value, "id": "", "response": "json"}),
            timeout=15,
        )
        tables = payload.get("tables") or []
        rows = tables[0].get("data", []) if tables else []
        row = next((item for item in rows if str(item[0]).strip() == code), None)
        if not row:
            return {}
        return {
            "date": datetime.strptime(str(payload.get("date") or date_str), "%Y%m%d").strftime("%Y-%m-%d"),
            "peRatio": parse_float(str(row[2])),
            "dividendPerShare": parse_float(str(row[3])),
            "dividendYield": parse_float(str(row[5])),
            "pbRatio": parse_float(str(row[6])),
        }

    payload = fetch_json(
        f"{TWSE_BASE}/rwd/zh/afterTrading/BWIBBU_d?"
        + urlencode({"date": date_str, "selectType": "ALL", "response": "json"}),
        timeout=15,
    )
    row = next(
        (item for item in payload.get("data", []) if str(item[0]).strip() == code),
        None,
    )
    if not row:
        return {}
    close_value = parse_float(str(row[2]))
    yield_value = parse_float(str(row[3]))
    dividend = (
        close_value * yield_value / 100
        if close_value is not None and yield_value is not None
        else None
    )
    return {
        "date": datetime.strptime(str(payload.get("date") or date_str), "%Y%m%d").strftime("%Y-%m-%d"),
        "peRatio": parse_float(str(row[5])),
        "dividendPerShare": round(dividend, 4) if dividend is not None else None,
        "dividendYield": yield_value,
        "pbRatio": parse_float(str(row[6])),
    }


def fetch_stock_valuation_history(
    stock: dict[str, Any],
    history_rows: list[list[str]],
    limit: int = 6,
) -> list[dict[str, Any]]:
    monthly_dates: dict[str, str] = {}
    for row in history_rows:
        try:
            date_value = parse_roc_date(str(row[0]))
        except (TypeError, ValueError):
            continue
        date_str = date_value.strftime("%Y%m%d")
        month_key = date_str[:6]
        monthly_dates[month_key] = max(monthly_dates.get(month_key, ""), date_str)

    all_dates = sorted(monthly_dates.values())
    targets = all_dates[-(limit + 1):-1] if len(all_dates) > 1 else all_dates[-limit:]
    if not targets:
        return []

    points: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(targets))) as executor:
        futures = {
            executor.submit(fetch_stock_valuation_on_date, stock, target): target
            for target in targets
        }
        for future in as_completed(futures):
            try:
                point = future.result()
            except Exception:  # noqa: BLE001
                point = {}
            if point:
                points.append(point)
    return sorted(points, key=lambda item: item["date"])


def format_company_date(value: Any) -> str:
    cleaned = re.sub(r"\D", "", str(value or ""))
    if len(cleaned) == 8:
        try:
            return datetime.strptime(cleaned, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return str(value or "--").strip() or "--"


def format_company_capital(value: Any) -> str:
    amount = parse_float(str(value or ""))
    if amount is None:
        return "--"
    return f"{amount / 100_000_000:,.2f} 億元"


def fetch_stock_company_profile(stock: dict[str, Any]) -> dict[str, Any]:
    market = str(stock.get("market") or "TWSE").upper()
    code = str(stock["code"])
    if market == "TPEX":
        rows = fetch_json(build_tpex_openapi_url("mopsfin_t187ap03_O"), timeout=10)
        matched = next(
            (
                row for row in rows
                if str(row.get("SecuritiesCompanyCode", "")).strip() == code
            ),
            None,
        )
        if not matched:
            return {}
        return {
            "fullName": str(matched.get("CompanyName") or stock.get("name") or "").strip(),
            "industry": str(matched.get("SecuritiesIndustryCode") or "--").strip(),
            "chairman": str(matched.get("Chairman") or "--").strip(),
            "generalManager": str(matched.get("GeneralManager") or "--").strip(),
            "capital": format_company_capital(matched.get("Paidin.Capital.NTDollars")),
            "establishedDate": format_company_date(matched.get("DateOfIncorporation")),
            "listingDate": format_company_date(matched.get("DateOfListing")),
            "address": str(matched.get("Address") or "--").strip(),
            "telephone": str(matched.get("Telephone") or "--").strip(),
            "website": str(matched.get("WebAddress") or "").strip().rstrip("　"),
        }

    rows = fetch_json(f"{TWSE_OPENAPI_BASE}/opendata/t187ap03_L", timeout=10)
    matched = next(
        (row for row in rows if str(row.get("公司代號", "")).strip() == code),
        None,
    )
    if not matched:
        return {}
    return {
        "fullName": str(matched.get("公司名稱") or stock.get("name") or "").strip(),
        "industry": str(matched.get("產業別") or "--").strip(),
        "chairman": str(matched.get("董事長") or "--").strip(),
        "generalManager": str(matched.get("總經理") or "--").strip(),
        "capital": format_company_capital(matched.get("實收資本額")),
        "establishedDate": format_company_date(matched.get("成立日期")),
        "listingDate": format_company_date(matched.get("上市日期")),
        "address": str(matched.get("地址") or matched.get("住址") or "--").strip(),
        "telephone": str(matched.get("總機電話") or "--").strip(),
        "website": str(matched.get("網址") or "").strip(),
    }


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


def build_stock_news_fallback(stock: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    code = str(stock.get("code") or "").strip()
    name = str(stock.get("name") or "").strip()
    market = str(stock.get("market") or "").strip().upper()
    suffix = "TWO" if market == "TPEX" else "TW"
    yahoo_link = f"https://tw.stock.yahoo.com/quote/{quote(f'{code}.{suffix}', safe='')}/news"
    is_etf = is_etf_stock(stock)
    google_query = f"{code} {name} ETF 配息 成分股 公告" if is_etf else f"{code} {name} 台股 新聞"
    google_link = f"https://news.google.com/search?{urlencode({'q': google_query, 'hl': 'zh-TW', 'gl': 'TW', 'ceid': 'TW:zh-Hant'})}"
    fallback_items = [
        {
            "title": f"{code} {name} {'Yahoo ETF 新聞' if is_etf else 'Yahoo 個股新聞'}",
            "link": yahoo_link,
            "source": "Yahoo 奇摩股市",
            "publishedAt": "即時來源",
        },
        {
            "title": f"{code} {name} Google 新聞搜尋",
            "link": google_link,
            "source": "Google 新聞",
            "publishedAt": "即時來源",
        },
        {
            "title": f"{code} {name} 公開資訊觀測站重大訊息",
            "link": "https://mops.twse.com.tw/mops/#/web/t05st01",
            "source": "公開資訊觀測站",
            "publishedAt": "即時來源",
        },
    ]
    return fallback_items[:limit]


def fetch_stock_news(stock: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    code = str(stock.get("code") or "").strip()
    name = str(stock.get("name") or "").strip()
    is_etf = is_etf_stock(stock)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    if is_etf:
        queries = [
            f'"{name}" {code} ETF when:30d',
            f'"{name}" ETF 配息 成分股',
            f'{code} ETF 投信 公告',
        ]
    else:
        queries = [
            f'"{name}" {code} 股票 when:30d',
            f'"{name}" {code} 台股',
            f'{name} {code} 財報 法人',
        ]
    queries = [query for query in queries if query.strip()]

    def fetch_news_query(query: str) -> list[dict[str, Any]]:
        url = f"{GOOGLE_NEWS_RSS_BASE}?{urlencode({'q': query, 'hl': 'zh-TW', 'gl': 'TW', 'ceid': 'TW:zh-Hant'})}"
        try:
            xml_text = fetch_text(url, timeout=7)
            root = ET.fromstring(xml_text)
        except Exception:  # noqa: BLE001
            LOGGER.exception("Google News RSS fetch failed for %s", code)
            return []
        query_items: list[dict[str, Any]] = []
        for item in root.findall("./channel/item"):
            title = str(item.findtext("title") or "").strip()
            link = str(item.findtext("link") or "").strip()
            published = str(item.findtext("pubDate") or "").strip()
            source_node = item.find("source")
            source = str(source_node.text or "").strip() if source_node is not None else ""
            if (
                not title
                or not link
                or title in seen
                or "youtube.com/" in title.lower()
                or "watch?" in title.lower()
                or source.lower() == "cmoney"
                or "股市爆料同學會" in title
            ):
                continue
            try:
                published = datetime.strptime(published, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass
            query_items.append(
                {
                    "title": title,
                    "link": link,
                    "source": source or "Google 新聞",
                    "publishedAt": published or "--",
                }
            )
            if len(query_items) >= limit:
                break
        return query_items

    executor = ThreadPoolExecutor(max_workers=min(3, len(queries)))
    try:
        futures = {query: executor.submit(fetch_news_query, query) for query in queries}
        fetched = collect_futures_until_deadline(executor, futures, 8, {"news"})
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    for query in queries:
        for item in fetched.get(query, []):
            title = str(item.get("title") or "")
            if title in seen:
                continue
            seen.add(title)
            items.append(item)
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break

    if items:
        return items[:limit]

    return build_stock_news_fallback(stock, limit)


def build_yahoo_quote_symbol(stock: dict[str, Any]) -> str:
    market = str(stock.get("market") or "").strip().upper()
    suffix = "TWO" if market == "TPEX" else "TW"
    return f"{stock.get('code', '')}.{suffix}"


def build_yahoo_quote_page_url(stock: dict[str, Any], page: str) -> str:
    symbol = quote(build_yahoo_quote_symbol(stock), safe="")
    return f"https://tw.stock.yahoo.com/quote/{symbol}/{page.strip('/')}"


def build_yahoo_tw_stock_resource_url(resource: str, params: dict[str, Any]) -> str:
    encoded_params = "".join(
        f";{quote(str(key), safe='')}={quote(str(value), safe='')}"
        for key, value in params.items()
        if value is not None and str(value) != ""
    )
    return f"https://tw.stock.yahoo.com/_td-stock/api/resource/{quote(resource, safe='.')}{encoded_params}"


def fetch_yahoo_tw_stock_resource(
    resource: str,
    params: dict[str, Any],
    referer: str,
    timeout: int = 10,
) -> Any:
    cache_key = json.dumps({"resource": resource, "params": params}, sort_keys=True, ensure_ascii=False)
    cached = read_memory_cache(
        "yahoo_tw_stock_resources",
        cache_key,
        YAHOO_TW_STOCK_RESOURCE_CACHE_SECONDS,
    )
    if cached is not None:
        return cached

    url = build_yahoo_tw_stock_resource_url(resource, params)
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Referer": referer,
            "Connection": "close",
        },
    )
    with _urlopen_with_ssl_fallback(req, timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    write_memory_cache("yahoo_tw_stock_resources", cache_key, payload)
    return payload


def normalize_yahoo_date_text(value: Any) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{4}/\d{2}/\d{2}", text):
        return text.replace("/", "-")
    return text


def parse_yahoo_number(value: Any) -> float | None:
    if value is None:
        return None
    return parse_float(str(value))


def normalize_yahoo_credit_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    if re.fullmatch(r"\d{4}/\d{2}/\d{2}", text):
        return text.replace("/", "-")
    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})T", text)
    if iso_match:
        return iso_match.group(1)
    return normalize_yahoo_date_text(text)


def yahoo_chart_date_label(date_text: str) -> str:
    match = re.match(r"^\d{4}-(\d{2})-(\d{2})$", str(date_text or ""))
    if not match:
        return str(date_text or "")[-5:].replace("-", "/")
    return f"{int(match.group(1))}/{int(match.group(2))}"


def yahoo_margin_diff(add_value: Any, subtract_value: Any, repay_value: Any = None) -> float | None:
    add = parse_yahoo_number(add_value)
    subtract = parse_yahoo_number(subtract_value)
    repay = parse_yahoo_number(repay_value)
    if add is None and subtract is None and repay is None:
        return None
    return (add or 0.0) - (subtract or 0.0) - (repay or 0.0)


def yahoo_usage_ratio_to_percent(value: Any) -> float | None:
    parsed = parse_yahoo_number(value)
    return parsed * 100 if parsed is not None else None


def normalize_yahoo_margin_credit_rows(
    payload: Any,
    symbol: str,
    daily_limit: int,
    chart_limit: int,
) -> dict[str, Any]:
    result_payload = (((payload or {}).get("data") or {}).get("result") or {})
    credits = result_payload.get("credits") or []
    trend = result_payload.get("trend") if isinstance(result_payload.get("trend"), dict) else {}
    rows: list[dict[str, Any]] = []
    for raw in credits:
        if not isinstance(raw, dict):
            continue
        date_text = normalize_yahoo_credit_date(raw.get("date"))
        if not date_text:
            continue
        quote_stats = raw.get("quoteStats") if isinstance(raw.get("quoteStats"), dict) else {}
        row = {
            "date": date_text,
            "endDate": normalize_yahoo_credit_date(raw.get("endDate")),
            "period": str(raw.get("period") or "day"),
            "totalDays": parse_yahoo_number(raw.get("totalDays")),
            "label": yahoo_chart_date_label(date_text),
            "closePrice": parse_yahoo_number(quote_stats.get("closePrice")),
            "changePct": parse_yahoo_number(quote_stats.get("changePercent")),
            "financingBuy": parse_yahoo_number(raw.get("financingBuyVolK")),
            "financingSell": parse_yahoo_number(raw.get("financingSellVolK")),
            "financingRepayment": parse_yahoo_number(raw.get("financingPaybackVolK")),
            "financingChange": yahoo_margin_diff(
                raw.get("financingBuyVolK"),
                raw.get("financingSellVolK"),
                raw.get("financingPaybackVolK"),
            ),
            "financingBalance": parse_yahoo_number(raw.get("financingTotalVolK")),
            "financingUtilizationRate": yahoo_usage_ratio_to_percent(raw.get("financingUsageRatio")),
            "shortBuy": parse_yahoo_number(raw.get("shortBuyVolK")),
            "shortSell": parse_yahoo_number(raw.get("shortSellVolK")),
            "shortRepayment": parse_yahoo_number(raw.get("shortRepayVolK")),
            "shortChange": yahoo_margin_diff(
                raw.get("shortSellVolK"),
                raw.get("shortBuyVolK"),
                raw.get("shortRepayVolK"),
            ),
            "shortBalance": parse_yahoo_number(raw.get("shortTotalVolK")),
            "shortLimit": parse_yahoo_number(raw.get("shortLimitVolK")),
            "shortUtilizationRate": yahoo_usage_ratio_to_percent(raw.get("shortUsageRatio")),
            "shortFinancingRatio": parse_yahoo_number(raw.get("shortFinancingPercent")),
            "offsetting": parse_yahoo_number(raw.get("dayTradingVolK")),
            "lendingSell": parse_yahoo_number(raw.get("lendingSellVolK")),
            "lendingRepay": parse_yahoo_number(raw.get("lendingRepayVolK")),
            "lendingChange": yahoo_margin_diff(raw.get("lendingSellVolK"), raw.get("lendingRepayVolK")),
            "lendingBalance": parse_yahoo_number(raw.get("lendingTotalVolK")),
        }
        rows.append(row)

    if not rows:
        return {}

    newest_first = sorted(rows, key=lambda item: str(item.get("date") or ""), reverse=True)
    chart_rows = sorted(rows, key=lambda item: str(item.get("date") or ""))[-chart_limit:]
    previous_lending_balance: float | None = None
    for row in chart_rows:
        lending_balance = row.get("lendingBalance")
        if lending_balance is None:
            row["lendingBalance"] = previous_lending_balance
        else:
            previous_lending_balance = lending_balance

    latest = newest_first[0]
    financing_trend = trend.get("financing") if isinstance(trend.get("financing"), dict) else {}
    short_trend = trend.get("tradeShort") if isinstance(trend.get("tradeShort"), dict) else {}
    ratio_trend = trend.get("shortFinancingPercent") if isinstance(trend.get("shortFinancingPercent"), dict) else {}
    overview_rows = [
        {
            "key": "financing",
            "name": "融資",
            "buy": latest.get("financingBuy"),
            "sell": latest.get("financingSell"),
            "repayment": latest.get("financingRepayment"),
            "change": latest.get("financingChange"),
            "balance": latest.get("financingBalance"),
            "utilizationRate": latest.get("financingUtilizationRate"),
            "streak": str(financing_trend.get("text") or "--"),
        },
        {
            "key": "short",
            "name": "融券",
            "buy": latest.get("shortBuy"),
            "sell": latest.get("shortSell"),
            "repayment": latest.get("shortRepayment"),
            "change": latest.get("shortChange"),
            "balance": latest.get("shortBalance"),
            "utilizationRate": latest.get("shortUtilizationRate"),
            "streak": str(short_trend.get("text") or "--"),
            "offsetting": latest.get("offsetting"),
            "shortFinancingRatio": latest.get("shortFinancingRatio"),
            "ratioStreak": str(ratio_trend.get("text") or ""),
        },
    ]
    return {
        "date": latest.get("date"),
        "overviewRows": overview_rows,
        "dailyRows": newest_first[:daily_limit],
        "marginBalancePeriodRows": {"day": newest_first[:30]},
        "marginBalanceChartRows": chart_rows,
        "marginBalanceChartDataKey": f"marginBalanceChart-{len(chart_rows)}-{symbol}-1y",
        "marginBalanceChartSource": "Yahoo StockServices.creditsWithQuoteStats",
        "marginSummaryTrend": trend,
        "financingBuy": latest.get("financingBuy"),
        "financingSell": latest.get("financingSell"),
        "financingCashRedemption": latest.get("financingRepayment"),
        "financingChange": latest.get("financingChange"),
        "financingBalance": latest.get("financingBalance"),
        "financingUtilizationRate": latest.get("financingUtilizationRate"),
        "shortBuy": latest.get("shortBuy"),
        "shortSell": latest.get("shortSell"),
        "shortStockRedemption": latest.get("shortRepayment"),
        "shortChange": latest.get("shortChange"),
        "shortBalance": latest.get("shortBalance"),
        "shortUtilizationRate": latest.get("shortUtilizationRate"),
        "shortFinancingRatio": latest.get("shortFinancingRatio"),
        "offsetting": latest.get("offsetting"),
        "unit": "張",
    }


def fetch_yahoo_margin_period_rows(
    symbol: str,
    referer: str,
    period: str,
    limit: int = 30,
) -> list[dict[str, Any]]:
    payload = fetch_yahoo_tw_stock_resource(
        "StockServices.creditsWithQuoteStats",
        {"limit": str(limit), "period": period, "symbol": symbol},
        referer=referer,
        timeout=10,
    )
    result = normalize_yahoo_margin_credit_rows(payload, symbol, limit, limit)
    return list((result.get("dailyRows") or [])[:limit]) if result else []


def normalize_yahoo_margin_accumulation_rows(payload: Any) -> list[dict[str, Any]]:
    credits = ((((payload or {}).get("data") or {}).get("result") or {}).get("credits") or [])
    label_map = {
        "2D": "2日",
        "3D": "3日",
        "5D": "5日",
        "10D": "10日",
        "1M": "1月",
        "3M": "3月",
        "6M": "6月",
        "1Y": "1年",
    }
    rows: list[dict[str, Any]] = []
    for raw in credits:
        if not isinstance(raw, dict):
            continue
        period_sum = str(raw.get("periodSum") or "").strip()
        if not period_sum:
            continue
        rows.append({
            "periodSum": period_sum,
            "label": label_map.get(period_sum, period_sum),
            "date": normalize_yahoo_credit_date(raw.get("date")),
            "endDate": normalize_yahoo_credit_date(raw.get("endDate")),
            "totalDays": parse_yahoo_number(raw.get("totalDays")),
            "financingChange": yahoo_margin_diff(
                raw.get("financingBuyVolK"),
                raw.get("financingSellVolK"),
                raw.get("financingPaybackVolK"),
            ),
            "shortChange": yahoo_margin_diff(
                raw.get("shortSellVolK"),
                raw.get("shortBuyVolK"),
                raw.get("shortRepayVolK"),
            ),
            "shortFinancingRatioChange": parse_yahoo_number(raw.get("shortFinancingPercentChange")),
        })
    order = {key: index for index, key in enumerate(label_map)}
    return sorted(rows, key=lambda row: order.get(str(row.get("periodSum") or ""), 999))


def fetch_yahoo_margin_accumulation_rows(symbol: str, referer: str) -> list[dict[str, Any]]:
    payload = fetch_yahoo_tw_stock_resource(
        "StockServices.credits",
        {"accumulation": "true", "symbol": symbol},
        referer=referer,
        timeout=10,
    )
    return normalize_yahoo_margin_accumulation_rows(payload)


def parse_yahoo_margin_balance_chart_rows(html: str) -> tuple[list[dict[str, Any]], str]:
    key_match = re.search(r'"marginBalanceChartDataKey"\s*:\s*"([^"]+)"', html)
    data_key = key_match.group(1) if key_match else ""
    if not data_key:
        fallback_match = re.search(r'"(marginBalanceChart-\d+-[^"]+)"\s*:\s*\{"data"\s*:\s*\{"list"', html)
        data_key = fallback_match.group(1) if fallback_match else ""
    if not data_key:
        return [], ""

    key_index = html.find(f'"{data_key}"')
    if key_index < 0:
        return [], data_key
    object_start = html.find("{", key_index + len(data_key) + 2)
    segment = extract_balanced_segment(html, object_start, "{", "}") if object_start >= 0 else None
    if not segment:
        return [], data_key
    try:
        payload = json.loads(segment)
    except json.JSONDecodeError:
        return [], data_key
    raw_rows = ((payload.get("data") or {}).get("list") or []) if isinstance(payload, dict) else []
    rows: list[dict[str, Any]] = []
    previous_lending_balance: float | None = None
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        date_text = normalize_yahoo_date_text(raw.get("fullDate")) or str(raw.get("date") or "")
        lending_balance = parse_yahoo_number(raw.get("lendingTotalVolK"))
        if lending_balance is None:
            lending_balance = previous_lending_balance
        else:
            previous_lending_balance = lending_balance
        rows.append({
            "date": date_text,
            "label": str(raw.get("date") or date_text[-5:].replace("-", "/") or ""),
            "closePrice": parse_yahoo_number(raw.get("closePrice")),
            "changePct": parse_yahoo_number(raw.get("changePercent")),
            "financingChange": parse_yahoo_number(raw.get("financingDiffK")),
            "financingBalance": parse_yahoo_number(raw.get("financingTotalVolK")),
            "shortChange": parse_yahoo_number(raw.get("shortDiffK")),
            "shortBalance": parse_yahoo_number(raw.get("shortTotalVolK")),
            "lendingChange": parse_yahoo_number(raw.get("lendingDiffK")),
            "lendingBalance": lending_balance,
        })
    return [row for row in rows if row.get("date")], data_key


def parse_yahoo_broker_row(line: str) -> dict[str, Any] | None:
    match = re.match(r"^(.+?)\s+([0-9,]+)\s+([0-9,]+)\s*([+-]?[0-9,]+)$", line.strip())
    if not match:
        return None
    broker, buy, sell, net = match.groups()
    return {
        "broker": broker.strip(),
        "buy": parse_float(buy),
        "sell": parse_float(sell),
        "net": parse_float(net),
    }


def parse_yahoo_broker_rows_from_lines(
    lines: list[str],
    start_label: str,
    stop_labels: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    try:
        index = lines.index(start_label)
    except ValueError:
        return []
    cursor = index + 1
    while cursor < len(lines) and lines[cursor] in {"買進", "賣出", "買超張數", "賣超張數"}:
        cursor += 1

    rows: list[dict[str, Any]] = []
    while cursor + 3 < len(lines) and len(rows) < limit:
        if lines[cursor] in stop_labels:
            break
        broker = str(lines[cursor] or "").strip()
        buy = parse_float(str(lines[cursor + 1] or ""))
        sell = parse_float(str(lines[cursor + 2] or ""))
        net = parse_float(str(lines[cursor + 3] or ""))
        if not broker or buy is None or sell is None or net is None:
            cursor += 1
            continue
        rows.append({"broker": broker, "buy": buy, "sell": sell, "net": net})
        cursor += 4
    return rows


def fetch_yahoo_broker_trading(stock: dict[str, Any], limit: int = 15) -> dict[str, Any]:
    url = build_yahoo_quote_page_url(stock, "broker-trading")
    try:
        lines = extract_visible_text_lines(fetch_text(url, timeout=10))
    except Exception:  # noqa: BLE001
        LOGGER.exception("Yahoo broker trading fetch failed for %s", stock.get("code"))
        return {}

    def value_after(label: str) -> str:
        try:
            index = lines.index(label)
        except ValueError:
            return "--"
        for value in lines[index + 1:index + 4]:
            cleaned = str(value).strip()
            if cleaned and cleaned != label:
                return cleaned
        return "--"

    date_text = normalize_yahoo_date_text(value_after("資料時間："))
    if date_text == "--":
        for line in lines:
            if line.startswith("資料時間："):
                date_text = normalize_yahoo_date_text(line.replace("資料時間：", "", 1).strip() or "--")
                break

    buy_rows = parse_yahoo_broker_rows_from_lines(lines, "買超券商", {"賣超券商"}, limit)
    sell_rows = parse_yahoo_broker_rows_from_lines(lines, "賣超券商", {"即時走勢", "相關新聞", "個股公告"}, limit)

    net_text = value_after("主力買賣超(張)")
    buy_text = value_after("主力買超(張)")
    sell_text = value_after("主力賣超(張)")
    volume_ratio = value_after("買賣超佔成交量")
    if not buy_rows and not sell_rows and net_text == "--":
        return {}
    return {
        "date": date_text,
        "summary": {
            "netLots": parse_float(net_text),
            "buyLots": parse_float(buy_text),
            "sellLots": parse_float(sell_text),
            "volumeRatio": volume_ratio,
        },
        "buyBrokers": buy_rows,
        "sellBrokers": sell_rows,
        "source": "Yahoo 股市主力進出",
        "sourceLink": url,
        "sourceNote": "主力進出同步自 Yahoo 股市券商分點頁，呈現實際券商分點買賣超。",
    }


def fetch_yahoo_major_holders(stock: dict[str, Any], limit: int = 260) -> dict[str, Any]:
    url = build_yahoo_quote_page_url(stock, "major-holders")
    try:
        lines = extract_visible_text_lines(fetch_text(url, timeout=10))
    except Exception:  # noqa: BLE001
        LOGGER.exception("Yahoo major holders fetch failed for %s", stock.get("code"))
        return {}

    for header_index in range(0, max(0, len(lines) - 4)):
        header = [str(item or "").strip() for item in lines[header_index:header_index + 5]]
        if not (
            header[0] in {"年度/日期", "日期"}
            and "外資籌碼" in header[1]
            and "大戶籌碼" in header[2]
            and "董監持股" in header[3]
            and "股價" in header[4]
        ):
            continue

        rows: list[dict[str, Any]] = []
        cursor = header_index + 5
        while cursor + 4 < len(lines) and len(rows) < limit:
            date_text = str(lines[cursor] or "").strip()
            if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", date_text):
                cursor += 1
                continue
            rows.append({
                "date": normalize_yahoo_date_text(date_text),
                "foreignChipRatio": parse_float(str(lines[cursor + 1]).replace("%", "")),
                "majorHolderRatio": parse_float(str(lines[cursor + 2]).replace("%", "")),
                "directorHoldingRatio": parse_float(str(lines[cursor + 3]).replace("%", "")),
                "price": parse_float(str(lines[cursor + 4]).replace(",", "")),
            })
            cursor += 5

        if rows:
            latest = rows[0]
            return {
                "date": latest.get("date"),
                "latest": latest,
                "rows": rows,
                "source": "Yahoo ?∪?憭扳蝐Ⅳ",
                "sourceLink": url,
                "sourceNote": "大戶籌碼同步自 Yahoo 股市大戶籌碼頁，包含外資籌碼、大戶籌碼、董監持股與股價。",
            }

    try:
        index = lines.index("年度/日期")
    except ValueError:
        return {}

    cursor = index + 1
    while cursor < len(lines) and lines[cursor] in {"外資籌碼", "大戶籌碼", "董監持股", "股價"}:
        cursor += 1

    rows: list[dict[str, Any]] = []
    while cursor + 4 < len(lines) and len(rows) < limit:
        date_text = str(lines[cursor] or "").strip()
        if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", date_text):
            cursor += 1
            continue
        row = {
            "date": normalize_yahoo_date_text(date_text),
            "foreignChipRatio": parse_float(str(lines[cursor + 1]).replace("%", "")),
            "majorHolderRatio": parse_float(str(lines[cursor + 2]).replace("%", "")),
            "directorHoldingRatio": parse_float(str(lines[cursor + 3]).replace("%", "")),
            "price": parse_float(str(lines[cursor + 4])),
        }
        rows.append(row)
        cursor += 5

    if not rows:
        return {}
    latest = rows[0]
    return {
        "date": latest.get("date"),
        "latest": latest,
        "rows": rows,
        "source": "Yahoo 股市大戶籌碼",
        "sourceLink": url,
        "sourceNote": "大戶籌碼同步自 Yahoo 股市大戶籌碼頁，ETF 若未揭露大戶欄位則顯示該頁提供之外資籌碼序列。",
    }


def fetch_yahoo_institutional_trading(stock: dict[str, Any], limit: int = 1300) -> dict[str, Any]:
    url = build_yahoo_quote_page_url(stock, "institutional-trading")
    try:
        lines = extract_visible_text_lines(fetch_text(url, timeout=10))
    except Exception:  # noqa: BLE001
        LOGGER.exception("Yahoo institutional trading fetch failed for %s", stock.get("code"))
        return {}

    try:
        overview_start = lines.index("法人買賣總覽")
    except ValueError:
        overview_start = -1
    try:
        daily_start = lines.index("法人逐日買賣超")
    except ValueError:
        daily_start = -1

    date_text = ""
    if overview_start >= 0:
        for index in range(overview_start, min(len(lines), overview_start + 12)):
            if lines[index] == "資料時間：" and index + 1 < len(lines):
                date_text = normalize_yahoo_date_text(lines[index + 1])
                break

    overview_rows: list[dict[str, Any]] = []
    if overview_start >= 0 and daily_start > overview_start:
        cursor = overview_start
        names = {"外資", "投信", "自營商", "三大法人"}
        while cursor + 4 < daily_start:
            name = str(lines[cursor] or "").strip()
            if name in names:
                overview_rows.append({
                    "name": name,
                    "buyLots": parse_float(str(lines[cursor + 1] or "")),
                    "sellLots": parse_float(str(lines[cursor + 2] or "")),
                    "netLots": parse_float(str(lines[cursor + 3] or "")),
                    "streak": str(lines[cursor + 4] or "").strip(),
                })
                cursor += 5
            else:
                cursor += 1

    daily_rows: list[dict[str, Any]] = []
    if daily_start >= 0:
        cursor = daily_start
        while cursor + 7 < len(lines) and len(daily_rows) < limit:
            raw_date = str(lines[cursor] or "").strip()
            if re.fullmatch(r"\d{4}/\d{2}/\d{2}", raw_date):
                daily_rows.append({
                    "date": normalize_yahoo_date_text(raw_date),
                    "label": raw_date[5:],
                    "foreignLotsValue": parse_float(str(lines[cursor + 1] or "")),
                    "trustLotsValue": parse_float(str(lines[cursor + 2] or "")),
                    "dealerLotsValue": parse_float(str(lines[cursor + 3] or "")),
                    "totalLotsValue": parse_float(str(lines[cursor + 4] or "")),
                    "foreignChipRatio": parse_float(str(lines[cursor + 5] or "").replace("%", "")),
                    "changePct": parse_float(str(lines[cursor + 6] or "").replace("%", "")),
                    "volume": parse_float(str(lines[cursor + 7] or "")),
                })
                cursor += 8
            else:
                cursor += 1

    if not overview_rows and not daily_rows:
        return {}
    return {
        "date": date_text,
        "overviewRows": overview_rows,
        "dailyRows": daily_rows,
        "unit": "張",
        "source": "Yahoo 股市法人買賣",
        "sourceLink": url,
        "sourceNote": "法人買賣同步自 Yahoo 股市法人買賣頁，含總覽與逐日買賣超。",
    }


def fetch_yahoo_margin_trading(stock: dict[str, Any], limit: int = 60) -> dict[str, Any]:
    url = build_yahoo_quote_page_url(stock, "margin")
    symbol = build_yahoo_quote_symbol(stock)
    daily_limit = max(1, int(limit or 60))
    chart_limit = max(365, daily_limit)
    try:
        payload = fetch_yahoo_tw_stock_resource(
            "StockServices.creditsWithQuoteStats",
            {"limit": str(chart_limit), "symbol": symbol},
            referer=url,
            timeout=10,
        )
        resource_result = normalize_yahoo_margin_credit_rows(payload, symbol, daily_limit, chart_limit)
        if resource_result:
            period_rows = {
                "day": list((resource_result.get("dailyRows") or [])[:30]),
            }
            for period in ("week", "month", "quarter"):
                try:
                    period_rows[period] = fetch_yahoo_margin_period_rows(symbol, url, period, 30)
                except Exception:  # noqa: BLE001
                    LOGGER.warning(
                        "Yahoo margin %s period fetch failed for %s",
                        period,
                        stock.get("code"),
                        exc_info=True,
                    )
                    period_rows[period] = []
            resource_result["marginBalancePeriodRows"] = period_rows
            try:
                resource_result["marginSummaryAccumulationRows"] = fetch_yahoo_margin_accumulation_rows(symbol, url)
            except Exception:  # noqa: BLE001
                LOGGER.warning(
                    "Yahoo margin accumulation fetch failed for %s",
                    stock.get("code"),
                    exc_info=True,
                )
                resource_result["marginSummaryAccumulationRows"] = []
            return {
                **resource_result,
                "source": "Yahoo 股市資券變化",
                "sourceLink": url,
                "sourceNote": "資券餘額變化同步自 Yahoo 股市資券變化 API，含融資餘額、融券餘額、借券賣出餘額與逐日增減。",
            }
    except Exception:  # noqa: BLE001
        LOGGER.warning("Yahoo margin resource fetch failed for %s; falling back to page HTML", stock.get("code"), exc_info=True)

    try:
        html = fetch_text(url, timeout=10)
        lines = extract_visible_text_lines(html)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Yahoo margin trading fetch failed for %s", stock.get("code"))
        return {}
    chart_rows, chart_data_key = parse_yahoo_margin_balance_chart_rows(html)

    try:
        overview_start = lines.index("資券變化總覽")
    except ValueError:
        overview_start = -1
    try:
        chart_start = lines.index("資券餘額變化")
    except ValueError:
        chart_start = -1
    try:
        daily_start = lines.index("資券餘額逐日增減")
    except ValueError:
        daily_start = -1

    date_text = ""
    if overview_start >= 0:
        for index in range(overview_start, min(len(lines), overview_start + 12)):
            if lines[index] == "資料時間：" and index + 1 < len(lines):
                date_text = normalize_yahoo_date_text(lines[index + 1])
                break

    overview_rows: list[dict[str, Any]] = []
    if overview_start >= 0 and chart_start > overview_start:
        try:
            financing_index = lines.index("融資", overview_start, chart_start)
            short_index = lines.index("融券", financing_index + 1, chart_start)
            values = [str(item or "").strip() for item in lines[short_index + 1:chart_start]]
            if len(values) >= 16:
                overview_rows = [
                    {
                        "key": "financing",
                        "name": "融資",
                        "buy": parse_float(values[0]),
                        "sell": parse_float(values[2]),
                        "repayment": parse_float(values[4]),
                        "change": parse_float(values[6]),
                        "balance": parse_float(values[8]),
                        "utilizationRate": parse_float(values[10].replace("%", "")),
                        "streak": values[12],
                    },
                    {
                        "key": "short",
                        "name": "融券",
                        "buy": parse_float(values[1]),
                        "sell": parse_float(values[3]),
                        "repayment": parse_float(values[5]),
                        "change": parse_float(values[7]),
                        "balance": parse_float(values[9]),
                        "utilizationRate": parse_float(values[11].replace("%", "")),
                        "streak": values[13],
                        "offsetting": parse_float(values[14]) if len(values) > 14 else None,
                        "shortFinancingRatio": parse_float(values[15].replace("%", "")) if len(values) > 15 else None,
                        "ratioStreak": values[16] if len(values) > 16 else "",
                    },
                ]
        except ValueError:
            overview_rows = []

    daily_rows: list[dict[str, Any]] = []
    if daily_start >= 0:
        cursor = daily_start
        while cursor + 8 < len(lines) and len(daily_rows) < limit:
            raw_date = str(lines[cursor] or "").strip()
            if re.fullmatch(r"\d{4}/\d{2}/\d{2}", raw_date):
                daily_rows.append({
                    "date": normalize_yahoo_date_text(raw_date),
                    "label": raw_date[5:],
                    "financingChange": parse_float(str(lines[cursor + 1] or "")),
                    "financingBalance": parse_float(str(lines[cursor + 2] or "")),
                    "financingUtilizationRate": parse_float(str(lines[cursor + 3] or "").replace("%", "")),
                    "shortChange": parse_float(str(lines[cursor + 4] or "")),
                    "shortBalance": parse_float(str(lines[cursor + 5] or "")),
                    "shortUtilizationRate": parse_float(str(lines[cursor + 6] or "").replace("%", "")),
                    "shortFinancingRatio": parse_float(str(lines[cursor + 7] or "").replace("%", "")),
                    "offsetting": parse_float(str(lines[cursor + 8] or "")),
                })
                cursor += 9
            else:
                cursor += 1

    if chart_rows:
        latest_chart = chart_rows[-1]
        if not date_text:
            date_text = str(latest_chart.get("date") or "")
        if not daily_rows:
            daily_rows = list(reversed(chart_rows[-daily_limit:]))

    if not overview_rows and not daily_rows and not chart_rows:
        return {}
    return {
        "date": date_text,
        "overviewRows": overview_rows,
        "dailyRows": daily_rows,
        "marginBalancePeriodRows": {"day": daily_rows[:30]},
        "marginSummaryAccumulationRows": [],
        "marginBalanceChartRows": chart_rows,
        "marginBalanceChartDataKey": chart_data_key,
        "marginBalanceChartSource": "Yahoo embedded marginBalanceChart",
        "unit": "張",
        "source": "Yahoo 股市資券變化",
        "sourceLink": url,
        "sourceNote": "資券餘額變化同步自 Yahoo 股市資券變化頁，含融資餘額、融券餘額、借券賣出餘額與逐日增減。",
    }


def fetch_stock_institutional_trades(stock: dict[str, Any], date_str: str) -> dict[str, Any]:
    if str(stock.get("market") or "TWSE").upper() != "TWSE":
        return {}
    payload, report_date = find_latest_dataset(build_stock_institutions_url)
    row = next(
        (item for item in payload.get("data", []) if str(item[0]).strip() == str(stock["code"])),
        None,
    )
    if not row:
        return {}
    foreign = parse_float(row[4])
    trust = parse_float(row[10])
    dealer = parse_float(row[11])
    total = parse_float(row[18])
    return {
        "date": datetime.strptime(report_date, "%Y%m%d").strftime("%Y-%m-%d"),
        "foreign": format_signed(foreign, 0),
        "trust": format_signed(trust, 0),
        "dealer": format_signed(dealer, 0),
        "total": format_signed(total, 0),
        "foreignValue": foreign,
        "trustValue": trust,
        "dealerValue": dealer,
        "totalValue": total,
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


def fetch_stock_institutional_trade_for_date(
    stock: dict[str, Any],
    date_str: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for attempt in range(3):
        try:
            payload = fetch_json(build_stock_institutions_url(date_str), timeout=10)
            break
        except Exception:  # noqa: BLE001
            if attempt >= 2:
                raise
            time.sleep(0.15 * (attempt + 1))
    if not dataset_has_rows(payload):
        return {}
    row = next(
        (item for item in payload.get("data", []) if str(item[0]).strip() == str(stock["code"])),
        None,
    )
    if not row:
        return {}
    return build_stock_institutional_trade_record(row, date_str)


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



INSTITUTIONAL_HISTORY_RANGE_CONFIG = {
    "1m": {"limit": 24, "days": 45, "chart_range": "3mo", "stride": 1},
    "3m": {"limit": 66, "days": 120, "chart_range": "6mo", "stride": 1},
    "6m": {"limit": 90, "days": 220, "chart_range": "1y", "stride": 2},
    "1y": {"limit": 110, "days": 420, "chart_range": "2y", "stride": 4},
}


def get_institutional_history_range_config(range_key: str) -> dict[str, int | str]:
    return INSTITUTIONAL_HISTORY_RANGE_CONFIG.get(
        str(range_key or "").strip().lower(),
        {"limit": 30, "days": 100, "chart_range": "6mo", "stride": 1},
    )


def fetch_yahoo_trading_dates_for_institutional_range(
    stock: dict[str, Any],
    range_key: str,
) -> list[str]:
    config = get_institutional_history_range_config(range_key)
    chart = fetch_yahoo_chart(
        str(stock.get("code") or ""),
        range_name=str(config.get("chart_range") or "1y"),
        interval="1d",
        market=str(stock.get("market") or "TWSE"),
    )
    timestamps = chart.get("timestamp") if isinstance(chart, dict) else []
    if not timestamps:
        return []
    dates = sorted({
        datetime.fromtimestamp(timestamp, TZ).date()
        for timestamp in timestamps
        if isinstance(timestamp, (int, float))
    }, reverse=True)
    if not dates:
        return []
    latest = dates[0]
    cutoff = latest - timedelta(days=int(config.get("days") or 120))
    stride = max(1, int(config.get("stride") or 1))
    filtered = [item for item in dates if item >= cutoff]
    sampled = [item for index, item in enumerate(filtered) if index % stride == 0]
    if filtered and filtered[0] not in sampled:
        sampled.insert(0, filtered[0])
    return [item.strftime("%Y%m%d") for item in sampled]


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
def collect_futures_until_deadline(
    executor: ThreadPoolExecutor,
    futures: dict[str, Any],
    timeout: float,
    list_defaults: set[str] | None = None,
) -> dict[str, Any]:
    list_defaults = list_defaults or set()
    if not futures:
        return {}

    future_to_key = {future: key for key, future in futures.items()}
    done, pending = wait(future_to_key.keys(), timeout=timeout)
    fetched: dict[str, Any] = {}
    for future in done:
        key = future_to_key[future]
        try:
            fetched[key] = future.result()
        except Exception:  # noqa: BLE001
            fetched[key] = [] if key in list_defaults else {}

    for future in pending:
        key = future_to_key[future]
        future.cancel()
        fetched[key] = [] if key in list_defaults else {}

    if pending:
        executor.shutdown(wait=False, cancel_futures=True)
    return fetched


def fetch_stock_institutional_trade_history(
    stock: dict[str, Any],
    date_str: str,
    limit: int = 30,
    trading_dates: list[str] | None = None,
) -> dict[str, Any]:
    periods = [5, 10, 20, 30]
    max_period = max(max(periods), limit)
    if str(stock.get("market") or "TWSE").upper() != "TWSE":
        return {
            "available": False,
            "unit": "張",
            "periods": periods,
            "defaultPeriod": 5,
            "rows": [],
            "summaries": {},
            "source": "TWSE T86",
            "sourceNote": "目前僅支援上市股票的證交所 T86 法人買賣超明細。",
        }

    try:
        base_date = datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        base_date = taipei_now().date()
    base_date = max(base_date, taipei_now().date())

    if trading_dates:
        candidates = []
        seen_candidates: set[str] = set()
        for item in trading_dates:
            if re.fullmatch(r"\d{8}", str(item or "")) and item not in seen_candidates:
                candidates.append(str(item))
                seen_candidates.add(str(item))
    else:
        lookback_days = max(80, max_period * 3)
        candidates = [
            (base_date - timedelta(days=offset)).strftime("%Y%m%d")
            for offset in range(lookback_days + 1)
        ]
    records: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    batch_size = 12 if trading_dates else 8
    max_workers = 6 if trading_dates else 4
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start:start + batch_size]
        with ThreadPoolExecutor(max_workers=min(max_workers, len(batch))) as executor:
            futures = {
                executor.submit(fetch_stock_institutional_trade_for_date, stock, target): target
                for target in batch
            }
            for future in as_completed(futures):
                try:
                    record = future.result()
                except Exception:  # noqa: BLE001
                    record = {}
                record_date = str(record.get("date") or "")
                if record and record_date and record_date not in seen_dates:
                    records.append(record)
                    seen_dates.add(record_date)
        if len(records) >= max_period:
            break

    rows = sorted(records, key=lambda item: str(item.get("date") or ""), reverse=True)[:max_period]
    latest_date = rows[0]["date"].replace("-", "") if rows else date_str
    summaries = {
        str(period): build_stock_institutional_trade_summary(rows[:period], period)
        for period in periods
        if rows
    }
    return {
        "available": bool(rows),
        "unit": "張",
        "limit": max_period,
        "periods": periods,
        "defaultPeriod": 5,
        "rows": rows,
        "summaries": summaries,
        "summary": summaries.get("5", {}),
        "source": "TWSE T86",
        "sourceLink": build_stock_institutions_url(latest_date),
        "sourceNote": "法人買賣超明細同步自證交所 T86，每日公告後更新。",
    }


def build_index_activity_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str}
    return f"{TWSE_BASE}/exchangeReport/BFIAMU?{urlencode(params)}"


def build_index_intraday_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str}
    return f"{TWSE_BASE}/exchangeReport/MI_5MINS_INDEX?{urlencode(params)}"


def build_weighted_index_history_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str}
    return f"{TWSE_BASE}/indicesReport/MI_5MINS_HIST?{urlencode(params)}"


def build_stock_day_url(date_str: str, stock_no: str) -> str:
    params = {"response": "json", "date": date_str, "stockNo": stock_no}
    return f"{TWSE_BASE}/exchangeReport/STOCK_DAY?{urlencode(params)}"


def shift_month(date_str: str, months_back: int) -> str:
    base_date = datetime.strptime(date_str, "%Y%m%d")
    total_months = base_date.year * 12 + (base_date.month - 1) - months_back
    year, month_idx = divmod(total_months, 12)
    month = month_idx + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return datetime(year, month, day).strftime("%Y%m%d")


def find_latest_dataset(builder, lookback_days: int = 10, validator=None) -> tuple[dict[str, Any], str]:
    now = taipei_now().date()
    errors: list[str] = []

    for offset in range(lookback_days + 1):
        target_date = now - timedelta(days=offset)
        date_str = target_date.strftime("%Y%m%d")
        try:
            payload = fetch_json(builder(date_str))
        except (HTTPError, URLError, TimeoutError) as exc:
            LOGGER.warning("TWSE dataset fetch failed for date=%s", date_str, exc_info=exc)
            errors.append(date_str)
            continue

        if dataset_has_rows(payload) and (validator is None or validator(payload)):
            return payload, date_str
        if dataset_has_rows(payload):
            errors.append(f"{date_str}: incomplete")

    checked_dates = ", ".join(errors) if errors else "none"
    raise RuntimeError(f"TWSE dataset unavailable for recent {lookback_days + 1} days; checked dates: {checked_dates}")


def dataset_has_rows(payload: dict[str, Any]) -> bool:
    if payload.get("stat") != "OK":
        return False

    if isinstance(payload.get("data"), list) and payload.get("data"):
        return True

    for table in payload.get("tables", []):
        if isinstance(table.get("data"), list) and table.get("data"):
            return True

    return False


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


def parse_float(value: str) -> float | None:
    cleaned = (value or "").replace(",", "").strip()
    if not cleaned or cleaned == "--":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def format_whole_number(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{int(round(value)):,}"


def format_signed(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "--"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:,.{digits}f}"


def format_percent(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "--"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.{digits}f}%"


def detect_tone(value: float | None) -> str:
    if value is None or value == 0:
        return "flat"
    return "up" if value > 0 else "down"


def build_intraday_technical_analysis(
    open_value: float | None,
    high_value: float | None,
    low_value: float | None,
    close_value: float | None,
    signed_change: float | None,
    pct: float | None,
) -> dict[str, Any]:
    if close_value is None:
        return {
            "bias": "neutral",
            "signal": "資料不足",
            "strength": "low",
            "volatilityPct": "--",
            "candle": "unknown",
        }

    candle = "unknown"
    if None not in (open_value, close_value):
        if close_value > open_value:
            candle = "bullish"
        elif close_value < open_value:
            candle = "bearish"
        else:
            candle = "doji"

    volatility_pct = None
    if None not in (open_value, high_value, low_value) and open_value != 0:
        volatility_pct = ((high_value - low_value) / open_value) * 100

    bias = "neutral"
    signal = "區間整理"
    strength = "medium"
    if pct is not None:
        if pct >= 3:
            bias = "bullish"
            signal = "多方突破"
            strength = "high"
        elif pct >= 0.8:
            bias = "bullish"
            signal = "偏多續強"
            strength = "medium"
        elif pct <= -3:
            bias = "bearish"
            signal = "空方轉弱"
            strength = "high"
        elif pct <= -0.8:
            bias = "bearish"
            signal = "偏空修正"
            strength = "medium"

    if bias == "neutral" and signed_change == 0:
        strength = "low"

    return {
        "bias": bias,
        "signal": signal,
        "strength": strength,
        "volatilityPct": f"{volatility_pct:.2f}" if volatility_pct is not None else "--",
        "candle": candle,
    }


def build_index_technical_analysis(
    name: str,
    value: float | None,
    signed_change: float | None,
    pct: float | None,
    volume_value: float | None = None,
    turnover_value: float | None = None,
    trade_count: float | None = None,
    max_volume_value: float | None = None,
    max_turnover_value: float | None = None,
    max_trade_count: float | None = None,
) -> dict[str, Any]:
    bias = "neutral"
    signal = "區間整理"
    strength = "medium"

    if pct is not None:
        if pct >= 1.5:
            bias = "bullish"
            signal = "多方突破"
            strength = "high"
        elif pct >= 0.5:
            bias = "bullish"
            signal = "偏多續強"
            strength = "medium"
        elif pct <= -1.5:
            bias = "bearish"
            signal = "空方轉弱"
            strength = "high"
        elif pct <= -0.5:
            bias = "bearish"
            signal = "偏空修正"
            strength = "medium"
        else:
            strength = "low"

    if pct == 0:
        strength = "low"

    range_state = "站上平盤" if signed_change and signed_change > 0 else "失守平盤" if signed_change and signed_change < 0 else "平盤整理"
    volume_ratio = (volume_value / max_volume_value) if volume_value is not None and max_volume_value not in (None, 0) else None
    turnover_ratio = (turnover_value / max_turnover_value) if turnover_value is not None and max_turnover_value not in (None, 0) else None
    trade_ratio = (trade_count / max_trade_count) if trade_count is not None and max_trade_count not in (None, 0) else None
    activity_score = max(filter(lambda item: item is not None, [volume_ratio, turnover_ratio, trade_ratio]), default=None)
    activity_level = "熱絡" if activity_score is not None and activity_score >= 0.66 else "溫和" if activity_score is not None and activity_score >= 0.33 else "清淡"
    summary = f"{name} {signal}，目前{range_state}，成交動能{activity_level}。"
    if value is None:
        summary = f"{name} 資料不足，暫以盤面強弱訊號觀察。"

    return {
        "bias": bias,
        "signal": signal,
        "strength": strength,
        "summary": summary,
        "rangeState": range_state,
        "momentum": "強" if strength == "high" else "中" if strength == "medium" else "弱",
        "activityLevel": activity_level,
        "activityScore": round(activity_score * 100, 1) if activity_score is not None else None,
        "volumeRatio": round(volume_ratio * 100, 1) if volume_ratio is not None else None,
        "turnoverRatio": round(turnover_ratio * 100, 1) if turnover_ratio is not None else None,
        "tradeRatio": round(trade_ratio * 100, 1) if trade_ratio is not None else None,
    }


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


def find_table_by_field_candidates(payload: dict[str, Any], candidates: list[str]) -> dict[str, Any]:
    for table in payload.get("tables", []):
        fields = table.get("fields", [])
        if any(candidate in fields for candidate in candidates):
            return table
    if isinstance(payload.get("fields"), list) and isinstance(payload.get("data"), list):
        if any(candidate in payload.get("fields", []) for candidate in candidates):
            return payload
    raise RuntimeError(f"Unable to locate TWSE table with fields: {', '.join(candidates)}")


def resolve_sector_key(name: str) -> str | None:
    return SECTOR_INDEX_LOOKUP.get(name)


def sector_aliases(key: str) -> list[str]:
    if key == "發行量加權股價指數":
        return ["發行量加權股價指數"]
    for item in LISTED_SECTOR_INDEX_SPECS:
        if item["key"] == key:
            return [key, *item.get("aliases", [])]
    return [key]


def parse_time_label(value: str) -> str | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 4:
        return None
    hour = digits[:2]
    minute = digits[2:4]
    return f"{hour}:{minute}"


def bucket_time_label(time_label: str, interval_minutes: int = 15) -> str | None:
    if not time_label or ":" not in time_label:
        return None
    hour_str, minute_str = time_label.split(":", 1)
    hour = int(hour_str)
    minute = int(minute_str)
    bucket_minute = (minute // interval_minutes) * interval_minutes
    return f"{hour:02d}:{bucket_minute:02d}"


def build_intraday_index_candles(
    payload: dict[str, Any],
    target_names: list[str],
    interval_minutes: int = 5,
) -> dict[str, list[dict[str, str]]]:
    table = find_table_by_field_candidates(payload, ["時間", "Time"])
    fields = table.get("fields", [])
    rows = table.get("data", [])
    if not fields or not rows:
        return {}

    time_index = next((idx for idx, field in enumerate(fields) if field in {"時間", "Time"}), None)
    if time_index is None:
        return {}

    column_lookup = {field: idx for idx, field in enumerate(fields)}
    candles_by_index: dict[str, dict[str, dict[str, float]]] = {name: {} for name in target_names}

    for row in rows:
        if not isinstance(row, list) or len(row) <= time_index:
            continue
        time_label = parse_time_label(str(row[time_index]))
        bucket = bucket_time_label(time_label or "", interval_minutes)
        if bucket is None:
            continue

        for field_name, field_index in column_lookup.items():
            index_name = resolve_sector_key(field_name)
            if index_name is None or index_name not in target_names:
                continue
            value = parse_float(row[field_index])
            if value is None:
                continue

            candle = candles_by_index[index_name].get(bucket)
            if candle is None:
                candles_by_index[index_name][bucket] = {
                    "open": value,
                    "high": value,
                    "low": value,
                    "close": value,
                }
                continue

            candle["high"] = max(candle["high"], value)
            candle["low"] = min(candle["low"], value)
            candle["close"] = value

    formatted: dict[str, list[dict[str, str]]] = {}
    for index_name, bucket_items in candles_by_index.items():
        ordered = []
        for bucket, candle in sorted(bucket_items.items()):
            ordered.append(
                {
                    "time": bucket,
                    "open": f"{candle['open']:.2f}",
                    "high": f"{candle['high']:.2f}",
                    "low": f"{candle['low']:.2f}",
                    "close": f"{candle['close']:.2f}",
                }
            )
        formatted[index_name] = ordered

    return formatted


def parse_index_close_values(payload: dict[str, Any], target_names: list[str]) -> dict[str, float]:
    try:
        index_table = find_table_by_field(payload, "指數")
    except RuntimeError:
        index_table = find_table_by_field_candidates(payload, ["指數", "收盤指數", "發行量加權股價指數"])
    rows = {row[0]: row for row in index_table.get("data", [])}
    close_values: dict[str, float] = {}
    for row_name, row in rows.items():
        target = resolve_sector_key(row_name)
        if target is None or target not in target_names:
            continue
        value = None
        for cell in row[1:]:
            value = parse_float(cell)
            if value is not None:
                break
        if value is None:
            continue
        close_values[target] = value
    return close_values


def build_sector_history_snapshot(
    date_str: str,
    target_names: list[str],
    include_activity: bool = True,
) -> tuple[str, dict[str, float], dict[str, Any], dict[str, dict[str, Any]]] | None:
    try:
        payload = fetch_json(build_market_url(date_str), STOCK_HISTORY_TIMEOUT_SECONDS)
    except Exception:  # noqa: BLE001
        return None
    if not dataset_has_rows(payload):
        return None

    activities = {}
    if include_activity:
        try:
            activity_payload = fetch_json(build_index_activity_url(date_str), STOCK_HISTORY_TIMEOUT_SECONDS)
            activities = parse_index_activities(activity_payload) if dataset_has_rows(activity_payload) else {}
        except Exception:  # noqa: BLE001
            activities = {}

    close_values = parse_index_close_values(payload, target_names)
    if not close_values:
        return None
    canonical_activities = {
        canonical: activity
        for name, activity in activities.items()
        if (canonical := resolve_sector_key(name)) is not None
    }
    return (
        datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d"),
        close_values,
        parse_market_statistics(payload),
        canonical_activities,
    )


def build_sector_history_series(
    latest_market_date: str,
    target_names: list[str],
    trading_days: int = SECTOR_HISTORY_TRADING_DAYS,
    weighted_trading_days: int | None = None,
    lookback_days: int | None = None,
    include_activity: bool = True,
) -> dict[str, list[dict[str, str]]]:
    latest_date = datetime.strptime(latest_market_date, "%Y%m%d").date()
    history_rows: list[tuple[str, dict[str, float], dict[str, Any], dict[str, dict[str, Any]]]] = []
    history_lookback_days = lookback_days if lookback_days is not None else max(int(trading_days * 2.2), 90)
    candidate_dates = [
        (latest_date - timedelta(days=offset)).strftime("%Y%m%d")
        for offset in range(history_lookback_days)
    ]

    with ThreadPoolExecutor(max_workers=min(10, len(candidate_dates))) as executor:
        futures = {
            executor.submit(build_sector_history_snapshot, date_str, target_names, include_activity): date_str
            for date_str in candidate_dates
        }
        for future in as_completed(futures):
            try:
                snapshot = future.result()
            except Exception:  # noqa: BLE001
                snapshot = None
            if snapshot is None:
                continue
            history_rows.append(snapshot)
            if len(history_rows) >= trading_days:
                for pending in futures:
                    pending.cancel()
                break

    history_rows = sorted(history_rows, key=lambda item: item[0])[-trading_days:]
    series_by_index: dict[str, list[dict[str, str]]] = {name: [] for name in target_names}
    for snapshot_date, close_values, market_stats, activities in history_rows:
        for target in target_names:
            close_value = close_values.get(target)
            if close_value is None:
                continue
            entry: dict[str, str] = {
                "date": snapshot_date,
                "close": f"{close_value:.2f}",
            }
            activity = activities.get(target, {})
            for key in ("volume", "turnover", "trades"):
                value = activity.get(key)
                if value and value != "--":
                    entry[key] = value
            volume_value = activity.get("volumeValue")
            if volume_value is not None:
                entry["volumeValue"] = str(volume_value)
            # Attach market-wide volume for the weighted index
            if target == "發行量加權股價指數" and market_stats:
                volume_val = market_stats.get("volumeValue")
                turnover_val = market_stats.get("turnoverValue")
                if volume_val is not None:
                    entry["volume"] = format_whole_number(volume_val) or "--"
                    entry["volumeValue"] = str(volume_val)
                if turnover_val is not None:
                    entry["turnover"] = format_whole_number(turnover_val) or "--"
            series_by_index[target].append(entry)

    if "發行量加權股價指數" in target_names:
        weighted_days = weighted_trading_days if weighted_trading_days is not None else max(
            trading_days,
            WEIGHTED_INDEX_HISTORY_TRADING_DAYS,
        )
        weighted_series = build_weighted_index_history_series(
            latest_market_date,
            weighted_days,
        )
        if weighted_series:
            series_by_index["發行量加權股價指數"] = weighted_series

    return series_by_index


def build_weighted_index_history_series(latest_market_date: str, trading_days: int = SECTOR_HISTORY_TRADING_DAYS) -> list[dict[str, str]]:
    lookback_months = max(4, (trading_days // 18) + 2)
    seen_dates: set[str] = set()
    series: list[dict[str, str]] = []
    twse_blocked = False
    latest_iso = datetime.strptime(latest_market_date, "%Y%m%d").strftime("%Y-%m-%d")

    try:
        yahoo_series = build_yahoo_chart_series(
            fetch_yahoo_symbol_chart("^TWII", "2y", "1d"),
            volume_divisor=1,
        )
    except Exception:  # noqa: BLE001
        yahoo_series = []
    yahoo_series = [item for item in yahoo_series if item.get("date", "") <= latest_iso]
    if len(yahoo_series) >= min(trading_days, 360):
        return yahoo_series[-trading_days:]

    for offset in range(lookback_months):
        month_date = shift_month(latest_market_date, offset)
        try:
            payload = fetch_json(build_weighted_index_history_url(month_date), timeout=STOCK_HISTORY_TIMEOUT_SECONDS)
        except HTTPError as exc:
            if exc.code in {403, 429}:
                twse_blocked = True
                break
            continue
        except Exception:  # noqa: BLE001
            continue
        if not dataset_has_rows(payload):
            continue

        try:
            table = find_table_by_field_candidates(payload, ["日期", "Date"])
        except RuntimeError:
            table = payload if isinstance(payload.get("data"), list) else {}
        rows = table.get("data", []) if isinstance(table, dict) else []
        if not rows:
            continue

        for row in rows:
            if not row or len(row) < 5:
                continue
            snapshot_date = parse_twse_table_date(str(row[0]))
            close_value = parse_float(row[4])
            if not snapshot_date or close_value is None or snapshot_date in seen_dates:
                continue
            seen_dates.add(snapshot_date)
            open_value = parse_float(row[1])
            high_value = parse_float(row[2])
            low_value = parse_float(row[3])
            entry: dict[str, str] = {
                "date": snapshot_date,
                "close": f"{close_value:.2f}",
            }
            if open_value is not None:
                entry["open"] = f"{open_value:.2f}"
            if high_value is not None:
                entry["high"] = f"{high_value:.2f}"
            if low_value is not None:
                entry["low"] = f"{low_value:.2f}"
            series.append(entry)

    series.sort(key=lambda item: item["date"])
    if len(series) >= min(trading_days, 120):
        yahoo_by_date = {item.get("date"): item for item in yahoo_series if item.get("date")}
        for item in series:
            yahoo_item = yahoo_by_date.get(item.get("date"))
            if not yahoo_item:
                continue
            for key in ("volume", "volumeValue"):
                if yahoo_item.get(key) not in (None, "", "--"):
                    item[key] = yahoo_item[key]
        return series[-trading_days:]

    if yahoo_series:
        return yahoo_series[-trading_days:]
    return [] if twse_blocked else series[-trading_days:]


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


def extract_first_table_rows(payload: Any) -> tuple[list[str], list[Any]]:
    if isinstance(payload, list):
        return [], payload
    if not isinstance(payload, dict):
        return [], []

    tables = payload.get("tables")
    if isinstance(tables, list):
        for table in tables:
            data = table.get("data")
            if isinstance(data, list) and data:
                fields = table.get("fields", [])
                return fields if isinstance(fields, list) else [], data
    fields = payload.get("fields")
    data = payload.get("data")
    if isinstance(fields, list) and isinstance(data, list) and data:
        return fields, data
    return [], []


def build_summary_cards_from_payload(payload: dict[str, Any], prefix: str, limit: int = 6) -> list[dict[str, Any]]:
    _, rows = extract_first_table_rows(payload)
    cards: list[dict[str, Any]] = []
    for index, row in enumerate(rows[:limit]):
        if isinstance(row, dict):
            name = str(
                row.get("name")
                or row.get("title")
                or row.get("index")
                or row.get("symbol")
                or row.get("代號")
                or row.get("指數")
                or f"{prefix}{index + 1}"
            )
            value = str(row.get("value") or row.get("close") or row.get("收盤") or row.get("current") or "--")
            change_raw = row.get("change") or row.get("漲跌") or row.get("diff")
            pct_raw = row.get("pct") or row.get("漲跌幅") or row.get("percentage")
            tone_value = parse_float(str(change_raw).replace("%", "")) if change_raw is not None else parse_float(str(pct_raw).replace("%", "")) if pct_raw is not None else None
            cards.append(
                {
                    "name": name,
                    "value": value,
                    "change": format_signed(parse_float(str(change_raw).replace("%", ""))) if change_raw is not None else "--",
                    "pct": format_percent(parse_float(str(pct_raw).replace("%", ""))) if pct_raw is not None else "--",
                    "tone": detect_tone(tone_value),
                    "volume": str(row.get("volume") or row.get("成交股數") or "--"),
                    "turnover": str(row.get("turnover") or row.get("成交金額") or "--"),
                    "trades": str(row.get("trades") or row.get("成交筆數") or "--"),
                    "note": str(row.get("note") or row.get("說明") or row.get("remark") or ""),
                    "sourceName": name,
                }
            )
            continue

        if not isinstance(row, list) or not row:
            continue
        name = str(row[0]).strip() or f"{prefix}{index + 1}"
        value = str(row[1]).strip() if len(row) > 1 else "--"
        change_raw = row[2] if len(row) > 2 else None
        pct_raw = row[3] if len(row) > 3 else None
        tone_value = parse_float(str(change_raw).replace("%", "")) if change_raw is not None else parse_float(str(pct_raw).replace("%", "")) if pct_raw is not None else None
        cards.append(
            {
                "name": name,
                "value": value,
                "change": str(change_raw).strip() if change_raw is not None else "--",
                "pct": str(pct_raw).strip() if pct_raw is not None else "--",
                "tone": detect_tone(tone_value),
                "volume": str(row[4]).strip() if len(row) > 4 else "--",
                "turnover": str(row[5]).strip() if len(row) > 5 else "--",
                "trades": str(row[6]).strip() if len(row) > 6 else "--",
                "note": str(row[7]).strip() if len(row) > 7 else "",
                "sourceName": name,
            }
        )
    return cards


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


def parse_roc_date(value: str) -> datetime:
    year, month, day = [int(part) for part in value.split("/")]
    return datetime(year + 1911, month, day)


def format_roc_date(value: datetime) -> str:
    return f"{value.year - 1911}/{value.month:02d}/{value.day:02d}"


def is_finite_positive(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value > 0


def is_valid_ohlc_values(
    open_value: float | None,
    high_value: float | None,
    low_value: float | None,
    close_value: float | None,
) -> bool:
    if not all(is_finite_positive(value) for value in (open_value, high_value, low_value, close_value)):
        return False
    assert open_value is not None and high_value is not None and low_value is not None and close_value is not None
    return high_value >= max(open_value, close_value) and low_value <= min(open_value, close_value)


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


def fetch_stock_history_rows(stock_no: str, date_str: str, months_back: int = STOCK_HISTORY_MAX_MONTHS) -> list[list[str]]:
    rows_by_date: dict[str, list[str]] = {}
    empty_months_after_data = 0

    def fetch_month(offset: int) -> list[list[str]]:
        target = shift_month(date_str, offset)
        try:
            payload = fetch_json(build_stock_day_url(target, stock_no), timeout=STOCK_HISTORY_TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001
            return []
        return payload.get("data", []) if isinstance(payload, dict) else []

    # Same TWSE STOCK_DAY per-month endpoint as fetch_recent_trade_rows, fetched in
    # concurrent batches instead of one blocking request at a time. Batches (not one
    # big pool) preserve the early-stop scan: once STOCK_HISTORY_EMPTY_STOP_MONTHS
    # consecutive empty months follow real data, older months are never requested.
    for batch_start in range(0, months_back, STOCK_HISTORY_FETCH_BATCH_SIZE):
        batch_offsets = range(batch_start, min(batch_start + STOCK_HISTORY_FETCH_BATCH_SIZE, months_back))
        with ThreadPoolExecutor(max_workers=len(batch_offsets)) as executor:
            batch_rows = list(executor.map(fetch_month, batch_offsets))

        for rows in batch_rows:
            if rows:
                empty_months_after_data = 0
                for row in rows:
                    rows_by_date[row[0]] = row
            elif rows_by_date:
                empty_months_after_data += 1

        if rows_by_date and empty_months_after_data >= STOCK_HISTORY_EMPTY_STOP_MONTHS:
            break

    return sorted(rows_by_date.values(), key=lambda row: parse_roc_date(row[0]))


def fetch_recent_trade_rows(stock_no: str, date_str: str) -> list[list[str]]:
    targets = [shift_month(date_str, offset) for offset in range(SECTOR_CHART_TRADE_MONTHS)]
    rows_by_date: dict[str, list[str]] = {}

    def fetch_month(target: str) -> list[list[str]]:
        try:
            payload = fetch_json(
                build_stock_day_url(target, stock_no),
                timeout=SECTOR_CHART_TRADE_TIMEOUT_SECONDS,
            )
        except Exception:  # noqa: BLE001
            return []
        return payload.get("data", []) if isinstance(payload, dict) else []

    with ThreadPoolExecutor(max_workers=len(targets)) as executor:
        futures = [executor.submit(fetch_month, target) for target in targets]
        for future in as_completed(futures):
            for row in future.result():
                if len(row) > 8:
                    rows_by_date[str(row[0])] = row

    return sorted(rows_by_date.values(), key=lambda row: parse_roc_date(row[0]))


def fetch_yahoo_history_rows(
    stock_no: str,
    months_back: int,
    market: str = "TWSE",
    diagnostics: dict[str, int] | None = None,
) -> list[list[str]]:
    range_name = "5y" if months_back == STOCK_HISTORY_MAX_MONTHS else "2y"
    chart = fetch_yahoo_chart(stock_no, range_name=range_name, interval="1d", market=market)
    if not chart:
        return []

    timestamps = chart.get("timestamp") or []
    quotes = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    opens = quotes.get("open") or []
    highs = quotes.get("high") or []
    lows = quotes.get("low") or []
    closes = quotes.get("close") or []
    volumes = quotes.get("volume") or []
    previous_close = parse_float(str((chart.get("meta") or {}).get("chartPreviousClose", "")))
    rows: list[list[str]] = []

    for index, timestamp in enumerate(timestamps):
        close_value = parse_float(str(closes[index] if index < len(closes) else ""))
        if close_value is None:
            if diagnostics is not None:
                diagnostics["invalid_rows"] = diagnostics.get("invalid_rows", 0) + 1
            continue
        open_value = parse_float(str(opens[index] if index < len(opens) else ""))
        high_value = parse_float(str(highs[index] if index < len(highs) else ""))
        low_value = parse_float(str(lows[index] if index < len(lows) else ""))
        volume_value = parse_float(str(volumes[index] if index < len(volumes) else ""))
        change_value = close_value - previous_close if previous_close is not None else None
        if not is_valid_ohlc_values(open_value, high_value, low_value, close_value):
            if diagnostics is not None:
                diagnostics["invalid_rows"] = diagnostics.get("invalid_rows", 0) + 1
            if is_finite_positive(close_value):
                previous_close = close_value
            continue
        trade_date = datetime.fromtimestamp(timestamp, TZ).replace(tzinfo=None)
        rows.append(
            [
                format_roc_date(trade_date),
                format_whole_number(volume_value),
                "",
                format_signed(open_value).lstrip("+"),
                format_signed(high_value).lstrip("+"),
                format_signed(low_value).lstrip("+"),
                format_signed(close_value).lstrip("+"),
                format_signed(change_value),
            ]
        )
        previous_close = close_value

    return rows


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


def is_etf_stock(stock: dict[str, Any]) -> bool:
    security_type = str(stock.get("securityType") or "").upper()
    code = str(stock.get("code") or "")
    name = str(stock.get("name") or "").upper()
    return security_type == "ETF" or code.startswith("00") or "ETF" in name


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


def format_yahoo_iso_date(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "--"
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d")
    except ValueError:
        return raw[:10] if len(raw) >= 10 else raw


def yahoo_number_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("fmt") or value.get("raw") or value.get("sort") or "--")
    if value in (None, ""):
        return "--"
    return str(value)


def fetch_etf_dividend_info(stock: dict[str, Any], limit: int = 6) -> dict[str, Any]:
    market = str(stock.get("market") or "TWSE").upper()
    suffix = "TWO" if market == "TPEX" else "TW"
    symbol = f"{stock['code']}.{suffix}"
    url = f"https://tw.stock.yahoo.com/quote/{quote(symbol, safe='')}/dividend"
    html = fetch_text(url, timeout=20)

    fundamental: dict[str, Any] = {}
    fundamental_marker = '"QuoteFundamental":{"fundamental":{"data":'
    fundamental_index = html.find(fundamental_marker)
    if fundamental_index >= 0:
        start = html.find("{", fundamental_index + len(fundamental_marker) - 1)
        segment = extract_balanced_segment(html, start, "{", "}")
        if segment:
            try:
                fundamental = json.loads(segment)
            except json.JSONDecodeError:
                fundamental = {}

    dividend_items: list[dict[str, Any]] = []
    dividend_key_match = re.search(r'"dividendDataKey":"([^"]+)"', html)
    if dividend_key_match:
        key = dividend_key_match.group(1)
        marker = f'"{key}":{{"data":'
        key_index = html.find(marker)
        if key_index >= 0:
            start = html.find("{", key_index + len(marker) - 1)
            segment = extract_balanced_segment(html, start, "{", "}")
            if segment:
                try:
                    dividend_data = json.loads(segment)
                    dividend_items = [
                        item for item in dividend_data.get("dividends", [])
                        if item.get("recordType") == "SUB"
                    ][:limit]
                except (json.JSONDecodeError, AttributeError):
                    dividend_items = []

    latest = fundamental.get("latestDividend") or {}
    latest_cash = latest.get("exDividend") or {}
    ex_dividend = fundamental.get("exDividend") or {}
    recent = []
    for item in dividend_items:
        cash = item.get("exDividend") or {}
        recent.append({
            "year": str(item.get("year") or "--"),
            "period": str(item.get("period") or "--"),
            "exDate": format_yahoo_iso_date(item.get("exDate") or cash.get("date")),
            "cashDividend": yahoo_number_text(cash.get("cash") or item.get("totalDividend")),
            "cashPayDate": format_yahoo_iso_date(cash.get("cashPayDate")),
            "yieldByExDate": yahoo_number_text(item.get("ytmCashByExDate")),
            "accYieldByPayDateYear": yahoo_number_text(item.get("ytmCashAccByPayDateY")),
            "previousClose": yahoo_number_text(item.get("exDatePreviousClose")),
            "recoveryDays": yahoo_number_text(cash.get("recoveryDays")),
        })

    return {
        "title": "ETF 股利資訊",
        "summary": "ETF 配息資料同步自 Yahoo 股市股利政策頁，呈現最新配息與近次除息紀錄。",
        "symbol": symbol,
        "latest": {
            "year": str(latest.get("year") or "--"),
            "period": str(latest.get("period") or "--"),
            "cashDividend": yahoo_number_text(latest_cash.get("cash")),
            "exDate": format_yahoo_iso_date(latest_cash.get("date") or ex_dividend.get("date")),
            "cashPayDate": format_yahoo_iso_date(latest_cash.get("cashPayDate") or ex_dividend.get("cashPayDate")),
            "isUpcoming": bool(latest.get("isUpcoming") or latest_cash.get("isUpcoming")),
        },
        "totals": {
            "totalDividends": yahoo_number_text(fundamental.get("totalDividends")),
            "averageYield": yahoo_number_text(fundamental.get("avgYTM")),
            "averageYears": yahoo_number_text(fundamental.get("avgYear")),
            "continuousYears": yahoo_number_text(fundamental.get("continuous")),
        },
        "recent": recent,
        "sourceNote": "資料來源：Yahoo 股市股利政策頁。",
        "sourceLink": url,
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


def refresh_cache() -> None:
    with cache_lock:
        existing_site_data = copy.deepcopy(cache_data["site_data"])
        existing_market_date = cache_data["market_date"]

    site_data, all_stocks, market_date_iso = build_site_data(
        existing_site_data=existing_site_data,
        existing_market_date=existing_market_date,
    )

    with cache_lock:
        cache_data["site_data"] = site_data
        cache_data["all_stocks"] = all_stocks
        cache_data["market_date"] = market_date_iso
        cache_data["cached_at"] = site_data["cachedAt"]
        cache_data["last_error"] = None
        cache_data["stock_details"] = {}
    save_disk_cache()


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


def fetch_live_stock_universe() -> tuple[list[dict[str, Any]], dict[str, Any], str, str | None]:
    with ThreadPoolExecutor(max_workers=3) as executor:
        market_future = executor.submit(find_latest_dataset, build_market_url, 7)
        tpex_quotes_future = executor.submit(fetch_tpex_mainboard_quotes)
        yahoo_etfs_future = executor.submit(fetch_yahoo_tpex_etfs)

        market_payload, market_date = market_future.result()
        twse_stocks = parse_all_stocks(market_payload)

        tpex_quotes: list[dict[str, Any]] = []
        tpex_quote_date: str | None = None
        try:
            tpex_quotes, tpex_quote_date = tpex_quotes_future.result()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live TPEx quotes fetch failed")

        try:
            yahoo_etfs = yahoo_etfs_future.result()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live Yahoo TPEx ETF fetch failed")
            yahoo_etfs = {}

    tpex_stocks = parse_tpex_quotes(tpex_quotes, yahoo_etfs) if tpex_quotes else []
    return [*twse_stocks, *tpex_stocks], market_payload, market_date, tpex_quote_date


def normalize_market_request(value: str | None) -> str:
    market = str(value or "").strip().upper()
    if market in {"TPEX", "TWO", "OTC", "上櫃"}:
        return "TPEX"
    if market in {"TWSE", "TW", "LISTED", "上市"}:
        return "TWSE"
    return market


def fetch_live_stock_search_results(
    query: str,
    requested_market: str = "",
    limit: int = 20,
) -> tuple[list[dict[str, Any]], str, str | None, list[str]]:
    keyword = query.strip()
    if not keyword:
        return [], "", None, []

    recent = get_recent_live_search_result(keyword, requested_market, limit)
    if recent:
        return recent

    normalized_market = normalize_market_request(requested_market)
    market_payload, market_date = find_latest_dataset(build_market_url, 7)
    twse_stocks = parse_all_stocks(market_payload)
    twse_matches = find_stock_by_query(keyword, twse_stocks, limit=limit)
    is_exact_code = re.fullmatch(r"[0-9A-Za-z]{4,8}", keyword) is not None

    if normalized_market != "TPEX":
        exact_twse = next((stock for stock in twse_matches if str(stock.get("code")) == keyword), None)
        if exact_twse and (normalized_market in {"", "TWSE"} or is_exact_code):
            return remember_live_search_result(
                keyword,
                requested_market,
                limit,
                (twse_matches[:limit], market_date, None, ["TWSE"]),
            )

    if normalized_market == "TWSE":
        return remember_live_search_result(
            keyword,
            requested_market,
            limit,
            (twse_matches[:limit], market_date, None, ["TWSE"]),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        tpex_quotes_future = executor.submit(fetch_tpex_mainboard_quotes)
        yahoo_etfs_future = executor.submit(fetch_yahoo_tpex_etfs)
        tpex_quotes, tpex_quote_date = tpex_quotes_future.result()
        if not tpex_quotes:
            raise RuntimeError("TPEx live quote source returned no rows")
        try:
            yahoo_etfs = yahoo_etfs_future.result()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Live search Yahoo TPEx ETF names fetch failed")
            yahoo_etfs = {}
    tpex_stocks = parse_tpex_quotes(tpex_quotes, yahoo_etfs)
    if normalized_market == "TPEX":
        return remember_live_search_result(
            keyword,
            requested_market,
            limit,
            (find_stock_by_query(keyword, tpex_stocks, limit=limit), market_date, tpex_quote_date, ["TPEx"]),
        )

    matches = find_stock_by_query(keyword, [*twse_stocks, *tpex_stocks], limit=limit)
    return remember_live_search_result(
        keyword,
        requested_market,
        limit,
        (matches, market_date, tpex_quote_date, ["TWSE", "TPEx"]),
    )


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


def fetch_live_index_activity(market_date: str) -> dict[str, Any] | None:
    try:
        payload = fetch_json(build_index_activity_url(market_date), timeout=10)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Live index activity fetch failed")
        return None
    return payload if dataset_has_rows(payload) else None


def fetch_live_index_intraday(market_date: str) -> dict[str, Any] | None:
    try:
        payload = fetch_json(build_index_intraday_url(market_date), timeout=10)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Live index intraday fetch failed")
        return None
    return payload if dataset_has_rows(payload) else None


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


def update_loop() -> None:
    while True:
        try:
            refresh_tpex_cache()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Background TPEx cache refresh failed")
            with cache_lock:
                cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE
        try:
            refresh_cache()
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Background TWSE cache refresh failed")
            with cache_lock:
                cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE
        time.sleep(UPDATE_INTERVAL_SECONDS)


def ensure_cache() -> None:
    with cache_lock:
        has_site_data = cache_data["site_data"] is not None
    if not has_site_data:
        load_disk_cache()
    with cache_lock:
        has_site_data = cache_data["site_data"] is not None
    if not has_site_data:
        with cache_refresh_lock:
            with cache_lock:
                has_site_data = cache_data["site_data"] is not None
            if has_site_data:
                return
            load_disk_cache()
            with cache_lock:
                has_site_data = cache_data["site_data"] is not None
            if has_site_data:
                return
            LOGGER.info("Cold cache refresh started")
            try:
                refresh_cache()
            except Exception:
                LOGGER.exception("Cold cache refresh failed")
                raise
            LOGGER.info("Cold cache refresh finished")
        return


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


def _refresh_all_market_penny_sector_recommendations() -> dict[str, Any]:
    now = time.monotonic()
    catalog = fetch_yahoo_sector_catalog()
    market_specs = [
        ("listed", "上市"),
        ("otc", "上櫃"),
        ("emerging", "興櫃"),
    ]
    excluded_category_pattern = re.compile(r"ETF|ETN|認購|認售|牛證|熊證|受益證券|指數類|全市場資訊", re.I)

    def fetch_category(group_key: str, market_label: str, index: int, category: dict[str, Any]) -> dict[str, Any]:
        name = str(category.get("name") or f"類股 {index + 1}").strip()
        if excluded_category_pattern.search(name):
            return {"skip": True, "group": group_key, "marketLabel": market_label, "name": name}
        try:
            cards, snapshot_date = build_yahoo_class_quote_cards(
                str(category.get("url") or ""),
                name,
                limit=500,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Penny sector category fetch failed group=%s name=%s: %s", group_key, name, exc)
            return {
                "group": group_key,
                "marketLabel": market_label,
                "index": index,
                "name": name,
                "snapshotDate": None,
                "stockCount": 0,
                "pennyStockCount": 0,
                "pennyStocks": [],
                "error": True,
            }

        penny_stocks = []
        component_count = 0
        for item in cards:
            symbol = str(item.get("sourceName") or "").strip().upper()
            if not re.fullmatch(r"\d{4,6}[A-Z]?\.(?:TW|TWO)", symbol):
                continue
            component_count += 1
            close_value = parse_float(str(item.get("value") or item.get("close") or ""))
            if close_value is None or close_value <= 0 or close_value > 50:
                continue
            pct_value = parse_float(str(item.get("pct") or "").replace("%", "")) or 0.0
            volume_value = parse_float(str(item.get("volumeValue") or item.get("volume") or "")) or 0.0
            liquidity_score = min(18.0, math.log10(volume_value + 1.0) * 3.0)
            score = 50.0 + pct_value * 4.0 + liquidity_score - close_value / 50.0 * 5.0
            code = symbol.split(".", 1)[0]
            penny_stocks.append(
                {
                    "code": code,
                    "name": str(item.get("name") or code),
                    "market": "TWSE" if symbol.endswith(".TW") else "TPEX",
                    "marketLabel": market_label,
                    "close": item.get("value") or item.get("close") or "--",
                    "closeValue": close_value,
                    "pct": item.get("pct") or "--",
                    "pctValue": pct_value,
                    "tone": detect_tone(pct_value),
                    "volume": item.get("volume") or "--",
                    "volumeValue": volume_value,
                    "score": max(0, min(99, round(score))),
                }
            )
        penny_stocks.sort(
            key=lambda item: (item.get("score") or 0, item.get("volumeValue") or 0, item.get("pctValue") or 0),
            reverse=True,
        )
        return {
            "group": group_key,
            "marketLabel": market_label,
            "index": index,
            "name": name,
            "snapshotDate": snapshot_date,
            "stockCount": component_count,
            "pennyStockCount": len(penny_stocks),
            "pennyStocks": penny_stocks[:10],
            "sourceUrl": category.get("url"),
        }

    futures = []
    results: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in market_specs}
    with ThreadPoolExecutor(max_workers=6) as executor:
        for group_key, market_label in market_specs:
            for index, category in enumerate(catalog.get(group_key) or []):
                futures.append(executor.submit(fetch_category, group_key, market_label, index, category))
        for future in as_completed(futures):
            item = future.result()
            if item.get("skip"):
                continue
            results[item["group"]].append(item)

    markets = []
    for group_key, market_label in market_specs:
        sectors = sorted(results[group_key], key=lambda item: item.get("index") or 0)
        available_sectors = [item for item in sectors if item.get("pennyStockCount")]
        markets.append(
            {
                "key": group_key,
                "label": market_label,
                "catalogCount": len(catalog.get(group_key) or []),
                "sectorCount": len(sectors),
                "availableSectorCount": len(available_sectors),
                "pennyStockCount": sum(item.get("pennyStockCount") or 0 for item in sectors),
                "sectors": sectors,
            }
        )
    payload = {
        "available": any(market.get("availableSectorCount") for market in markets),
        "updatedAt": taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
        "priceLimit": 50,
        "markets": markets,
        "source": "Yahoo奇摩股市類股成分股",
        "sourceNote": "逐一整理上市、上櫃、興櫃類股成分股，篩選收盤價 50 元以下股票；排除 ETF、ETN、權證、牛熊證與純指數分類。",
    }
    with penny_sector_recommendation_lock:
        penny_sector_recommendation_cache["stored_at"] = now
        penny_sector_recommendation_cache["payload"] = copy.deepcopy(payload)
    return payload


def build_all_market_penny_sector_recommendations() -> dict[str, Any]:
    now = time.monotonic()
    with penny_sector_recommendation_lock:
        cached_payload = penny_sector_recommendation_cache.get("payload")
        stored_at = float(penny_sector_recommendation_cache.get("stored_at") or 0)
        if cached_payload and now - stored_at < PENNY_SECTOR_RECOMMENDATION_CACHE_SECONDS:
            return copy.deepcopy(cached_payload)

    is_leader, flight = claim_cache_flight("penny-sector-recommendations")
    if not is_leader:
        flight.wait(CACHE_FLIGHT_WAIT_SECONDS)
        with penny_sector_recommendation_lock:
            cached_payload = penny_sector_recommendation_cache.get("payload")
        if cached_payload:
            return copy.deepcopy(cached_payload)
        raise RuntimeError("三市場類股成分股同步未完成，請稍後再試")

    try:
        return _refresh_all_market_penny_sector_recommendations()
    finally:
        finish_cache_flight("penny-sector-recommendations", flight)


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


def build_taifex_open_interest_item(spec: dict[str, Any]) -> dict[str, Any]:
    symbol = str(spec.get("symbol") or "").strip()
    commodity = str(spec.get("taifexCommodity") or symbol).strip().upper()
    display_name = re.sub(r"\s*未平倉\s*$", "", str(spec.get("name") or symbol)).strip() or symbol
    technical_profile = build_yahoo_taiwan_future_technical_profile(symbol)
    base_item = {
        "symbol": symbol,
        "dataSymbol": symbol,
        "name": display_name,
        "type": spec.get("type") or "台灣衍生商品",
        "group": spec.get("group") or spec.get("type") or "台灣衍生商品",
        "region": spec.get("region") or "台灣",
        "market": spec.get("market") or "台灣",
        "exchange": spec.get("exchange") or "TAIFEX",
        "source": "TAIFEX 官方期貨日報",
        "dataSource": "TAIFEX 官方期貨日報",
        "referenceSource": spec.get("referenceSource") or "TAIFEX 契約規格",
        "sourceUrl": TAIFEX_FUTURES_DAILY_OPENAPI_URL,
        "metricLabel": "成交量",
        "currency": "TWD",
        "quoteSource": "",
        "quoteSourceUrl": "",
        "yahooFutureCode": technical_profile.get("primaryCode") or "",
        "technicalAnalysisUrl": technical_profile.get("primaryUrl") or "",
        "technicalAnalysisSource": technical_profile.get("source") or "",
        "technicalContracts": technical_profile.get("contracts") or [],
    }
    snapshot = None
    try:
        snapshot = fetch_taifex_latest_futures_market_snapshot(commodity)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("TAIFEX futures daily market item fetch failed for symbol=%s", symbol, exc_info=exc)
        snapshot = None
    yahoo_quote = None
    try:
        yahoo_quote = fetch_yahoo_taiwan_future_quote(symbol)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Yahoo Taiwan futures quote fetch failed for symbol=%s: %s", symbol, exc)
    if not snapshot and not yahoo_quote:
        return {**base_item, "error": "TAIFEX / Yahoo 期貨行情暫無可用資料"}

    use_yahoo_quote = yahoo_future_quote_can_override_taifex(yahoo_quote, snapshot)
    quote = yahoo_quote if use_yahoo_quote else (snapshot or {})
    open_value = parse_float(str(quote.get("open") or ""))
    high_value = parse_float(str(quote.get("high") or ""))
    low_value = parse_float(str(quote.get("low") or ""))
    close_value = parse_float(str(quote.get("close") or ""))
    volume_value = parse_float(str(quote.get("volume") or ""))
    open_interest = (
        parse_float(str(quote.get("openInterest") or ""))
        or parse_float(str((snapshot or {}).get("openInterest") or ""))
        or parse_float(str((yahoo_quote or {}).get("openInterest") or ""))
    )
    settlement = parse_float(str((snapshot or {}).get("settlement") or ""))
    change = parse_float(str(quote.get("change") or ""))
    pct = parse_float(str(quote.get("changePct") or ""))
    series = []
    for observation in (snapshot or {}).get("observations") or []:
        value = parse_float(str(observation.get("close") or ""))
        if value is None:
            continue
        series.append({
            "date": observation.get("date") or "",
            "open": observation.get("open") or value,
            "high": observation.get("high") or value,
            "low": observation.get("low") or value,
            "close": value,
            "volume": observation.get("volume") or 0,
            "volumeValue": observation.get("volume") or 0,
            "openInterest": observation.get("openInterest"),
            "settlement": observation.get("settlement"),
        })
    if use_yahoo_quote and yahoo_quote:
        yahoo_date = yahoo_quote.get("date") or (snapshot or {}).get("date") or ""
        yahoo_series_row = {
            "date": yahoo_date,
            "open": yahoo_quote.get("open") or close_value,
            "high": yahoo_quote.get("high") or close_value,
            "low": yahoo_quote.get("low") or close_value,
            "close": close_value,
            "volume": yahoo_quote.get("volume") or 0,
            "volumeValue": yahoo_quote.get("volume") or 0,
            "openInterest": open_interest,
            "settlement": settlement,
            "source": "Yahoo 股市即時期指報價",
        }
        if yahoo_date and close_value is not None:
            series = [row for row in series if row.get("date") != yahoo_date]
            series.append(yahoo_series_row)
            series.sort(key=lambda row: str(row.get("date") or ""))
    quote_status = "yahoo-live" if use_yahoo_quote else "taifex-official"
    source_note_parts = [
        "TAIFEX 官方期貨每日交易行情提供官方日報、結算價與未平倉資料。"
    ]
    if yahoo_quote:
        yahoo_status_text = "已導入並覆蓋最新報價" if use_yahoo_quote else "已導入但日期較舊，僅作來源揭露"
        source_note_parts.append(
            f"Yahoo 股市即時期指報價 {yahoo_quote.get('date') or '--'} {yahoo_quote.get('quoteTime') or '--'}：{yahoo_status_text}。"
        )
    return {
        **base_item,
        "dataSymbol": commodity,
        "date": quote.get("date") or (snapshot or {}).get("date") or "--",
        "open": format_price_value(open_value),
        "high": format_price_value(high_value),
        "low": format_price_value(low_value),
        "close": format_price_value(close_value),
        "settlement": format_price_value(settlement),
        "change": format_signed(change) if change is not None else "--",
        "pct": format_percent(pct) if pct is not None else "--",
        "periodReturn": format_percent(pct) if pct is not None else "--",
        "volume": format_whole_number(volume_value) if volume_value is not None else "--",
        "volumeValue": volume_value,
        "openInterest": format_whole_number(open_interest),
        "openInterestValue": open_interest,
        "bid": format_price_value(parse_float(str((yahoo_quote or {}).get("bid") or ""))),
        "ask": format_price_value(parse_float(str((yahoo_quote or {}).get("ask") or ""))),
        "basis": format_price_value(parse_float(str((yahoo_quote or {}).get("basis") or ""))),
        "referencePrice": format_price_value(parse_float(str((yahoo_quote or {}).get("referencePrice") or ""))),
        "quoteTime": str((yahoo_quote or {}).get("quoteTime") or "--"),
        "quoteDate": str((yahoo_quote or {}).get("date") or "--"),
        "quoteStatus": quote_status,
        "quoteSource": "Yahoo 股市即時期指報價" if yahoo_quote else "",
        "quoteSourceUrl": YAHOO_TW_FUTURE_UNCOVERED_URL if yahoo_quote else "",
        "yahooFutureCode": (yahoo_quote or {}).get("yahooCode") or technical_profile.get("primaryCode") or "",
        "technicalAnalysisUrl": technical_profile.get("primaryUrl") or "",
        "technicalAnalysisSource": technical_profile.get("source") or "",
        "technicalContracts": technical_profile.get("contracts") or [],
        "source": "Yahoo 股市即時期指報價 / TAIFEX 官方期貨日報" if use_yahoo_quote else "TAIFEX 官方期貨日報",
        "dataSource": "Yahoo 股市即時期指報價 / TAIFEX 官方期貨日報" if use_yahoo_quote else "TAIFEX 官方期貨日報",
        "sourceNote": " ".join(source_note_parts),
        "sourceLink": YAHOO_TW_FUTURE_UNCOVERED_URL if use_yahoo_quote else (snapshot or {}).get("sourceLink") or base_item["sourceUrl"],
        "taifexSourceLink": (snapshot or {}).get("sourceLink") or TAIFEX_FUTURES_DAILY_OPENAPI_URL,
        "series": series,
    }


def fetch_us_treasury_yield_curve_rows() -> list[tuple[datetime, dict[str, str]]]:
    now = time.time()
    with cache_lock:
        cached = cache_data.get("treasury_yield_curve_rows") or {}
    if cached and now - float(cached.get("stored_at") or 0) < TREASURY_YIELD_CURVE_CACHE_SECONDS:
        rows = cached.get("rows") or []
        if rows:
            return rows

    text = fetch_text(US_TREASURY_YIELD_CURVE_CSV_URL, timeout=12)
    rows = list(csv.DictReader(io.StringIO(text)))
    dated_rows: list[tuple[datetime, dict[str, str]]] = []
    for row in rows:
        date_text = str(row.get("Date") or row.get("DATE") or "").strip()
        try:
            dated_rows.append((datetime.strptime(date_text, "%m/%d/%Y"), row))
        except ValueError:
            continue
    sorted_rows = sorted(dated_rows, key=lambda item: item[0])
    if sorted_rows:
        with cache_lock:
            cache_data["treasury_yield_curve_rows"] = {"stored_at": now, "rows": sorted_rows}
        save_disk_cache()
    return sorted_rows


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


def build_txo_option_market_item(spec: dict[str, Any]) -> dict[str, Any]:
    symbol = normalize_taiwan_option_underlying(str(spec.get("taifexCommodity") or spec.get("symbol") or "TXO"))
    product = get_taiwan_option_product(symbol)
    def first_number(*values: Any) -> float | None:
        for value in values:
            if value in (None, ""):
                continue
            parsed = parse_float(str(value))
            if parsed is not None:
                return parsed
        return None

    base_item = {
        "symbol": symbol,
        "dataSymbol": symbol,
        "name": spec.get("name") or product["name"],
        "type": spec.get("type") or "Taiwan index option",
        "group": spec.get("group") or spec.get("type") or "Taiwan options",
        "region": spec.get("region") or "台灣",
        "market": spec.get("market") or "台灣",
        "exchange": spec.get("exchange") or "TAIFEX",
        "source": "TAIFEX 選擇權官方日報",
        "dataSource": "TAIFEX 選擇權官方日報",
        "referenceSource": spec.get("referenceSource") or "TAIFEX option daily market report",
        "sourceUrl": spec.get("sourceUrl") or TAIFEX_OPTIONS_DAILY_URL,
        "metricLabel": "未平倉",
        "currency": "TWD",
        "optionCategory": spec.get("optionCategory") or "",
        "optionSubcategory": spec.get("optionSubcategory") or "",
        "optionSourceRole": spec.get("optionSourceRole") or "",
        "taifexCommodity": spec.get("taifexCommodity") or "",
        "optionChainSymbol": spec.get("optionChainSymbol") or "",
        "optionChainUnavailableReason": spec.get("optionChainUnavailableReason") or "",
    }
    try:
        chain = fetch_txo_option_chain(source="auto", underlying=symbol)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("%s option market item fetch failed", symbol, exc_info=exc)
        return {**base_item, "error": PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE}
    if chain.get("error"):
        return {**base_item, "error": str(chain.get("error") or PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE)}

    summary = chain.get("summary") or {}
    spot = chain.get("spot") or {}
    close_value = first_number(spot.get("value"), summary.get("atmStrike"), summary.get("maxPain"))
    previous_close = first_number(spot.get("previousValue"))
    change = first_number(spot.get("change"))
    pct = first_number(spot.get("pct"))
    total_volume = first_number(summary.get("totalVolume"))
    total_oi = first_number(summary.get("totalOpenInterest"))
    date_text = str(chain.get("tradeDate") or spot.get("date") or "--")
    series_row = {
        "date": date_text,
        "open": format_price_value(close_value),
        "high": format_price_value(close_value),
        "low": format_price_value(close_value),
        "close": format_price_value(close_value),
        "volume": format_whole_number(total_volume),
        "volumeValue": total_volume,
        "openInterest": total_oi,
        "source": f"{symbol} option chain summary",
    }
    return {
        **base_item,
        "date": date_text,
        "open": format_price_value(close_value),
        "high": format_price_value(close_value),
        "low": format_price_value(close_value),
        "close": format_price_value(close_value),
        "previousClose": format_price_value(previous_close),
        "change": format_signed(change) if change is not None else "--",
        "pct": format_percent(pct) if pct is not None else "--",
        "periodReturn": format_percent(pct) if pct is not None else "--",
        "volume": format_whole_number(total_volume),
        "volumeValue": total_volume,
        "openInterest": format_whole_number(total_oi),
        "openInterestValue": total_oi,
        "putCallRatio": summary.get("putCallRatio"),
        "volumePutCallRatio": summary.get("volumePutCallRatio"),
        "callOpenInterest": summary.get("callOpenInterest"),
        "putOpenInterest": summary.get("putOpenInterest"),
        "callVolume": summary.get("callVolume"),
        "putVolume": summary.get("putVolume"),
        "atmStrike": summary.get("atmStrike"),
        "maxPain": summary.get("maxPain"),
        "selectedExpiry": chain.get("selectedExpiry") or "",
        "selectedExpiryDate": chain.get("selectedExpiryDate") or "",
        "quoteStatus": "txo-chain-summary",
        "source": str((chain.get("source") or {}).get("primary") or base_item["source"]),
        "dataSource": str((chain.get("source") or {}).get("primary") or base_item["dataSource"]),
        "sourceNote": f"{symbol} item is filled from the selected option-chain summary: spot/ATM, max pain, volume and open interest.",
        "sourceLink": str((chain.get("source") or {}).get("primaryUrl") or base_item["sourceUrl"]),
        "series": [series_row] if close_value is not None else [],
    }


def fetch_taifex_openapi_list(url: str, cache_seconds: int, timeout: int = 20) -> list[dict[str, Any]]:
    cached = read_memory_cache("taifex_openapi_list", url, cache_seconds)
    if cached is not None:
        return cached
    rows = fetch_json(url, timeout=timeout)
    if not isinstance(rows, list):
        rows = []
    write_memory_cache("taifex_openapi_list", url, rows)
    return rows


def taifex_underlying_is_etf(underlying_row: dict[str, Any]) -> bool:
    return "ETF" in str(underlying_row.get("Type") or "")


def build_taifex_option_product_volume_summary_item(
    spec: dict[str, Any],
    base_item: dict[str, Any],
    *,
    category_label: str,
    product_label: str,
) -> dict[str, Any] | None:
    product_code = {"STO": "STC", "ETO": "ETC"}.get(str(spec.get("symbol") or "").strip().upper())
    if not product_code:
        return None
    try:
        rows = fetch_taifex_openapi_list(
            TAIFEX_OPTIONS_PRODUCT_DAILY_OPENAPI_URL,
            TAIFEX_STOCK_DERIVATIVE_AGGREGATE_CACHE_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("TAIFEX Daily_OPT aggregate fetch failed for %s: %s", product_code, exc)
        return None
    relevant_rows = [
        row for row in rows
        if str(row.get("Contract") or "").strip().upper() == product_code
    ]
    if not relevant_rows:
        return None
    latest_date = max(str(row.get("Date") or "") for row in relevant_rows)
    latest_rows = [row for row in relevant_rows if str(row.get("Date") or "") == latest_date]
    total_volume = sum(parse_taifex_market_number(row.get("Volume")) or 0 for row in latest_rows)
    date_text = normalize_taifex_date_text(latest_date)
    series = []
    by_date: dict[str, float] = {}
    for row in relevant_rows:
        date_key = str(row.get("Date") or "")
        if not date_key:
            continue
        by_date[date_key] = by_date.get(date_key, 0) + (parse_taifex_market_number(row.get("Volume")) or 0)
    for date_key, volume in sorted(by_date.items())[-60:]:
        normalized_date = normalize_taifex_date_text(date_key)
        series.append({
            "date": normalized_date,
            "open": format_whole_number(volume),
            "high": format_whole_number(volume),
            "low": format_whole_number(volume),
            "close": format_whole_number(volume),
            "volume": format_whole_number(volume),
            "volumeValue": volume,
            "source": "TAIFEX Daily_OPT aggregate",
        })
    return {
        **base_item,
        "date": date_text or "--",
        "open": format_whole_number(total_volume),
        "high": format_whole_number(total_volume),
        "low": format_whole_number(total_volume),
        "close": format_whole_number(total_volume),
        "change": "--",
        "pct": "--",
        "periodReturn": "--",
        "volume": format_whole_number(total_volume),
        "volumeValue": total_volume,
        "openInterest": "--",
        "openInterestValue": None,
        "contractCount": len(latest_rows),
        "activeContractCount": sum(1 for row in latest_rows if (parse_taifex_market_number(row.get("Volume")) or 0) > 0),
        "leaderContract": product_code,
        "status": "connected",
        "v1Status": "connected",
        "metricLabel": "成交量",
        "dataSource": "TAIFEX Daily_OPT 官方分類成交量",
        "dataStatus": f"TAIFEX Daily_OPT 官方彙總 {category_label}{product_label} {product_code} 分類成交量；標的清單端點無法使用時以此補齊卡片數值。",
        "sourceNote": (
            f"TAIFEX Daily_OPT 依期貨商、日期與商品分類彙總 {product_code} 成交量；"
            f"最新日期 {date_text or '--'}，總成交量 {format_whole_number(total_volume)}。"
        ),
        "sourceLink": TAIFEX_OPTIONS_PRODUCT_DAILY_OPENAPI_URL,
        "series": series,
    }


def build_taifex_stock_derivative_aggregate_item(spec: dict[str, Any]) -> dict[str, Any]:
    """Aggregate TAIFEX OpenAPI daily reports across every individual stock/ETF futures or options
    contract, since TAIFEX has no single commodity code representing "all stock futures" etc."""
    symbol = str(spec.get("symbol") or "").strip().upper()
    is_option = symbol in {"STO", "ETO"}
    is_etf = symbol in {"ETF-F", "ETO"}
    list_url = TAIFEX_SSO_LIST_OPENAPI_URL if is_option else TAIFEX_SSF_LIST_OPENAPI_URL
    report_url = TAIFEX_OPTIONS_DAILY_OPENAPI_URL if is_option else TAIFEX_FUTURES_DAILY_OPENAPI_URL
    base_item = {
        "symbol": symbol,
        "dataSymbol": symbol,
        "name": spec.get("name") or symbol,
        "type": spec.get("type") or "TAIFEX 標的衍生商品",
        "group": spec.get("group") or spec.get("type") or "TAIFEX 標的衍生商品",
        "region": spec.get("region") or "台灣",
        "market": spec.get("market") or "台灣",
        "exchange": spec.get("exchange") or "TAIFEX",
        "source": "TAIFEX OpenAPI",
        "dataSource": "TAIFEX OpenAPI 標的清單 + 每日交易行情",
        "referenceSource": spec.get("referenceSource") or "TAIFEX OpenAPI",
        "sourceUrl": report_url,
        "metricLabel": "未平倉量",
        "currency": "TWD",
        "optionCategory": spec.get("optionCategory") or "",
        "optionSubcategory": spec.get("optionSubcategory") or "",
        "optionSourceRole": spec.get("optionSourceRole") or "",
        "taifexCommodity": spec.get("taifexCommodity") or "",
        "optionChainSymbol": spec.get("optionChainSymbol") or "",
        "optionChainUnavailableReason": spec.get("optionChainUnavailableReason") or "",
    }
    try:
        underlyings = fetch_taifex_openapi_list(list_url, TAIFEX_UNDERLYING_LIST_CACHE_SECONDS)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("TAIFEX underlying list fetch failed for %s: %s", symbol, exc)
        underlyings = []
    contract_lookup = {
        str(row.get("Contract") or "").strip().upper(): row
        for row in underlyings
        if row.get("Contract")
    }
    matching_contracts = {
        code for code, row in contract_lookup.items()
        if taifex_underlying_is_etf(row) == is_etf
    }
    if not matching_contracts:
        if is_option:
            fallback_item = build_taifex_option_product_volume_summary_item(
                spec,
                base_item,
                category_label="ETF" if is_etf else "個股",
                product_label="選擇權",
            )
            if fallback_item:
                return fallback_item
        return build_source_pending_market_item(base_item, {
            **spec,
            "dataStatus": spec.get("dataStatus") or f"TAIFEX {symbol} 標的清單暫無可用資料。",
        })
    try:
        report_rows = fetch_taifex_openapi_list(report_url, TAIFEX_STOCK_DERIVATIVE_AGGREGATE_CACHE_SECONDS)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("TAIFEX daily report fetch failed for %s: %s", symbol, exc)
        report_rows = []
    relevant_rows = [
        row for row in report_rows
        if str(row.get("Contract") or "").strip().upper() in matching_contracts
    ]
    if not relevant_rows:
        if is_option:
            fallback_item = build_taifex_option_product_volume_summary_item(
                spec,
                base_item,
                category_label="ETF" if is_etf else "個股",
                product_label="選擇權",
            )
            if fallback_item:
                return fallback_item
        return {**base_item, "error": "TAIFEX 每日行情暫無可用資料"}

    total_volume = sum(parse_taifex_market_number(row.get("Volume")) or 0 for row in relevant_rows)
    total_oi = sum(parse_taifex_market_number(row.get("OpenInterest")) or 0 for row in relevant_rows)
    active_contracts = {
        str(row.get("Contract") or "").strip().upper()
        for row in relevant_rows
        if (parse_taifex_market_number(row.get("Volume")) or 0) > 0
    }
    date_text = normalize_taifex_date_text(relevant_rows[0].get("Date"))
    leader_row = max(relevant_rows, key=lambda row: parse_taifex_market_number(row.get("Volume")) or 0)
    leader_contract = str(leader_row.get("Contract") or "").strip().upper()
    leader_info = contract_lookup.get(leader_contract) or {}
    leader_close = parse_taifex_market_number(leader_row.get("Last")) or parse_taifex_market_number(leader_row.get("SettlementPrice"))
    category_label = "ETF" if is_etf else "個股"
    product_label = "選擇權" if is_option else "期貨"
    aggregate_close = total_oi if total_oi > 0 else total_volume
    aggregate_series_row = {
        "date": date_text or "--",
        "open": format_whole_number(aggregate_close),
        "high": format_whole_number(aggregate_close),
        "low": format_whole_number(aggregate_close),
        "close": format_whole_number(aggregate_close),
        "volume": format_whole_number(total_volume),
        "volumeValue": total_volume,
        "openInterest": total_oi,
        "source": "TAIFEX OpenAPI aggregate",
    }
    return {
        **base_item,
        "date": date_text or "--",
        "open": format_whole_number(aggregate_close),
        "high": format_whole_number(aggregate_close),
        "low": format_whole_number(aggregate_close),
        "close": format_whole_number(aggregate_close),
        "change": "--",
        "pct": "--",
        "periodReturn": "--",
        "volume": format_whole_number(total_volume),
        "volumeValue": total_volume,
        "openInterest": format_whole_number(total_oi),
        "openInterestValue": total_oi,
        "contractCount": len(matching_contracts),
        "activeContractCount": len(active_contracts),
        "leaderContract": leader_contract,
        "leaderStockCode": leader_info.get("StockCode") or "",
        "leaderStockName": leader_info.get("StockName") or "",
        "leaderClose": format_price_value(leader_close),
        "status": "connected",
        "v1Status": "connected",
        "dataStatus": f"TAIFEX OpenAPI 即時彙總 {len(matching_contracts)} 檔{category_label}{product_label}契約，{len(active_contracts)} 檔今日有成交。",
        "sourceNote": (
            f"未平倉量與成交量彙總自 TAIFEX OpenAPI 標的清單（{len(matching_contracts)} 檔契約）與每日交易行情；"
            f"成交最活躍標的為 {leader_info.get('StockName') or leader_contract}。資料日期 {date_text or '--'}。"
        ),
        "sourceLink": report_url,
        "series": [aggregate_series_row] if aggregate_close > 0 else [],
    }


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


def parse_fred_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    return None


def fetch_fred_observation_rows(series_id: str, timeout: int = 8) -> list[tuple[datetime, float]]:
    clean_id = str(series_id or "").strip().upper()
    if not clean_id:
        return []
    url = f"{FRED_GRAPH_CSV_BASE}?{urlencode({'id': clean_id})}"
    text = fetch_text(url, timeout=timeout)
    rows = list(csv.DictReader(io.StringIO(text)))
    observations: list[tuple[datetime, float]] = []
    for row in rows:
        date_value = parse_fred_date(str(row.get("observation_date") or row.get("DATE") or row.get("date") or ""))
        if date_value is None:
            continue
        raw_value = row.get(clean_id)
        if raw_value is None:
            value_columns = [value for key, value in row.items() if key and key.lower() not in {"observation_date", "date"}]
            raw_value = value_columns[0] if value_columns else None
        observed_value = parse_float(str(raw_value or ""))
        if observed_value is None:
            continue
        observations.append((date_value, observed_value))
    return sorted(observations, key=lambda item: item[0])


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


def parse_english_market_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    for date_format in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    return None


def extract_meta_description(html: str) -> str:
    match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if not match:
        match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', html, re.I)
    return unescape(match.group(1)) if match else ""


def fetch_trading_economics_taiwan_10y(timeout: int = 10) -> dict[str, Any] | None:
    html = fetch_text(TRADING_ECONOMICS_TAIWAN_10Y_URL, timeout=timeout)
    description = extract_meta_description(html)
    if not description:
        return None
    value_match = re.search(r"Taiwan\s+10Y\s+Bond\s+Yield.*?\bto\s+([0-9]+(?:\.[0-9]+)?)%\s+on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", description, re.I)
    if not value_match:
        value_match = re.search(r"([0-9]+(?:\.[0-9]+)?)%\s+on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", description, re.I)
    if not value_match:
        return None
    close_value = parse_float(value_match.group(1))
    date_value = parse_english_market_date(value_match.group(2))
    if close_value is None or date_value is None:
        return None
    change = None
    change_match = re.search(r"marking\s+a\s+([0-9]+(?:\.[0-9]+)?)\s+percentage\s+points?\s+(increase|decrease)", description, re.I)
    if not change_match:
        change_match = re.search(
            r"\b(risen|fallen|increased|decreased|gained|lost|climbed|dropped|rose|fell)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s+(?:percentage\s+)?points?",
            description,
            re.I,
        )
        if change_match:
            direction_word, magnitude_text = change_match.group(1), change_match.group(2)
            raw_change = parse_float(magnitude_text)
            if raw_change is not None:
                falling_words = {"fallen", "decreased", "lost", "dropped", "fell"}
                change = -raw_change if direction_word.lower() in falling_words else raw_change
    else:
        raw_change = parse_float(change_match.group(1))
        if raw_change is not None:
            change = raw_change if change_match.group(2).lower() == "increase" else -raw_change
    return {
        "date": date_value.strftime("%Y-%m-%d"),
        "value": close_value,
        "change": change,
        "description": description,
        "source": "Trading Economics Taiwan 10-Year Government Bond Yield",
        "sourceStatus": "live",
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


def nasdaq_status_ok(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = payload.get("status") or {}
    code = status.get("rCode")
    return code in {200, "200", None}


def nasdaq_data(payload: Any) -> Any:
    if not nasdaq_status_ok(payload):
        return None
    return payload.get("data") if isinstance(payload, dict) else None


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


def fetch_yahoo_quote_summary(symbol: str) -> dict[str, Any]:
    modules = ",".join([
        "price",
        "summaryProfile",
        "assetProfile",
        "summaryDetail",
        "defaultKeyStatistics",
        "financialData",
        "calendarEvents",
        "fundProfile",
        "topHoldings",
        "majorHoldersBreakdown",
        "institutionOwnership",
        "fundOwnership",
        "insiderTransactions",
        "insiderHolders",
        "netSharePurchaseActivity",
    ])
    params = urlencode({"modules": modules})
    payload = fetch_json(f"{YAHOO_QUOTE_SUMMARY_BASE}/{quote(symbol, safe='')}?{params}", timeout=10)
    result = ((payload.get("quoteSummary") or {}).get("result") or [None])[0] if isinstance(payload, dict) else None
    return result or {}


def fetch_yahoo_us_symbol_news(symbol: str, limit: int = 6) -> list[dict[str, Any]]:
    params = urlencode({
        "q": symbol,
        "quotesCount": "0",
        "newsCount": str(limit),
        "enableFuzzyQuery": "false",
    })
    payload = fetch_json(f"{YAHOO_SEARCH_BASE}?{params}", timeout=8)
    news = payload.get("news") if isinstance(payload, dict) else []
    results: list[dict[str, Any]] = []
    for item in news or []:
        published = item.get("providerPublishTime")
        published_text = "--"
        if published:
            try:
                published_text = datetime.fromtimestamp(int(published), TZ).strftime("%Y-%m-%d %H:%M")
            except (TypeError, ValueError, OSError):
                published_text = "--"
        results.append({
            "title": str(item.get("title") or "--"),
            "source": str(item.get("publisher") or "Yahoo Finance"),
            "publishedAt": published_text,
            "link": str(item.get("link") or f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/news"),
        })
    return results[:limit]


def fetch_us_market_overview_news(limit: int = 8) -> list[dict[str, Any]]:
    queries = ["SPY", "QQQ", "^GSPC", "^IXIC", "^VIX"]
    news_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=min(len(queries), 5)) as executor:
        futures = {executor.submit(fetch_yahoo_us_symbol_news, query, 4): query for query in queries}
        for future in as_completed(futures):
            try:
                items = future.result(timeout=10)
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("US market overview news fetch failed for %s", futures[future], exc_info=exc)
                continue
            for item in items:
                key = str(item.get("link") or item.get("title") or "").strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                news_items.append({
                    "tag": "Yahoo Finance",
                    "title": item.get("title") or "--",
                    "body": f"{item.get('source') or 'Yahoo Finance'} · {item.get('publishedAt') or '--'}",
                    "source": item.get("source") or "Yahoo Finance",
                    "publishedAt": item.get("publishedAt") or "--",
                    "link": item.get("link") or "https://finance.yahoo.com/",
                })
                if len(news_items) >= limit:
                    return news_items
    return news_items[:limit]


def fetch_nasdaq_quote_endpoint(symbol: str, endpoint: str, asset_classes: list[str]) -> dict[str, Any]:
    clean_symbol = quote(symbol.upper(), safe="")
    for asset_class in asset_classes:
        try:
            payload = fetch_nasdaq_json(f"/quote/{clean_symbol}/{endpoint}?assetclass={asset_class}", timeout=10)
        except Exception:  # noqa: BLE001
            continue
        data = nasdaq_data(payload)
        if data:
            return {"assetClass": asset_class, "payload": payload, "data": data}
    return {}


def fetch_nasdaq_company_profile(symbol: str) -> dict[str, Any]:
    try:
        payload = fetch_nasdaq_json(f"/company/{quote(symbol.upper(), safe='')}/company-profile", timeout=10)
    except Exception:  # noqa: BLE001
        return {}
    data = nasdaq_data(payload)
    return data if isinstance(data, dict) else {}


def fetch_nasdaq_company_financials(symbol: str) -> dict[str, Any]:
    try:
        payload = fetch_nasdaq_json(f"/company/{quote(symbol.upper(), safe='')}/financials?frequency=1", timeout=12)
    except Exception:  # noqa: BLE001
        return {}
    data = nasdaq_data(payload)
    return data if isinstance(data, dict) else {}


def fetch_nasdaq_company_institutional_holdings(symbol: str) -> dict[str, Any]:
    try:
        payload = fetch_nasdaq_json(f"/company/{quote(symbol.upper(), safe='')}/institutional-holdings", timeout=12)
    except Exception:  # noqa: BLE001
        return {}
    data = nasdaq_data(payload)
    return data if isinstance(data, dict) else {}


def fetch_nasdaq_company_insider_trades(symbol: str) -> dict[str, Any]:
    try:
        payload = fetch_nasdaq_json(f"/company/{quote(symbol.upper(), safe='')}/insider-trades", timeout=12)
    except Exception:  # noqa: BLE001
        return {}
    data = nasdaq_data(payload)
    return data if isinstance(data, dict) else {}


def fetch_nasdaq_us_supplement(symbol: str, is_etf_hint: bool = False) -> dict[str, Any]:
    asset_classes = ["etf", "stocks"] if is_etf_hint else ["stocks", "etf"]
    supplement: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            "summary": executor.submit(fetch_nasdaq_quote_endpoint, symbol, "summary", asset_classes),
            "dividends": executor.submit(fetch_nasdaq_quote_endpoint, symbol, "dividends", asset_classes),
            "shortInterest": executor.submit(fetch_nasdaq_quote_endpoint, symbol, "short-interest", ["stocks"]),
            "profile": executor.submit(fetch_nasdaq_company_profile, symbol),
            "financials": executor.submit(fetch_nasdaq_company_financials, symbol),
            "institutionalHoldings": executor.submit(fetch_nasdaq_company_institutional_holdings, symbol),
            "insiderTrades": executor.submit(fetch_nasdaq_company_insider_trades, symbol),
        }
        for key, future in futures.items():
            try:
                supplement[key] = future.result(timeout=14)
            except Exception:  # noqa: BLE001
                supplement[key] = {}
    return supplement


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


def fetch_us_treasury_yield_curve() -> dict[str, Any]:
    try:
        dated_rows = fetch_us_treasury_yield_curve_rows()
    except Exception:  # noqa: BLE001
        return {}
    if not dated_rows:
        return {}
    date_value, row = max(dated_rows, key=lambda item: item[0])
    yields = {
        key: parse_float(str(row.get(key) or ""))
        for key in ("3 Mo", "2 Yr", "5 Yr", "10 Yr", "30 Yr")
    }
    return {
        "date": date_value.strftime("%Y-%m-%d"),
        "yields": {key: value for key, value in yields.items() if value is not None},
        "source": "U.S. Treasury Daily Treasury Par Yield Curve",
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


def build_derivative_candles(item: dict[str, Any], interval: str) -> list[dict[str, Any]]:
    raw_series = item.get("series") or []
    candles = []
    for row in raw_series:
        close = parse_float(str(row.get("close") or ""))
        if close is None:
            continue
        candles.append({
            "time": str(row.get("date") or row.get("time") or ""),
            "open": parse_float(str(row.get("open") or close)),
            "high": parse_float(str(row.get("high") or close)),
            "low": parse_float(str(row.get("low") or close)),
            "close": close,
            "volume": parse_float(str(row.get("volumeValue") or row.get("volume") or "")),
            "settlement": parse_float(str(row.get("settlement") or "")),
            "openInterest": parse_float(str(row.get("openInterest") or "")),
        })
    if interval in {"day", "all"}:
        return candles
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candle in candles:
        try:
            date = datetime.strptime(candle["time"][:10], "%Y-%m-%d")
        except ValueError:
            continue
        key = f"{date.isocalendar().year}-W{date.isocalendar().week:02d}" if interval == "week" else date.strftime("%Y-%m")
        grouped.setdefault(key, []).append(candle)
    results = []
    for key, rows in grouped.items():
        results.append({
            "time": key,
            "open": rows[0]["open"],
            "high": max(row["high"] for row in rows if row["high"] is not None),
            "low": min(row["low"] for row in rows if row["low"] is not None),
            "close": rows[-1]["close"],
            "volume": sum(row["volume"] or 0 for row in rows),
            "settlement": rows[-1].get("settlement"),
            "openInterest": rows[-1].get("openInterest"),
        })
    return results


def build_futures_ai_analysis(item: dict[str, Any]) -> dict[str, Any]:
    candles = build_derivative_candles(item, "day")
    recent = candles[-20:]
    close = parse_float(str(item.get("close") or ""))
    pct = parse_float(str(item.get("pct") or ""))
    support = min((row.get("low") for row in recent if row.get("low") is not None), default=None)
    resistance = max((row.get("high") for row in recent if row.get("high") is not None), default=None)
    if pct is None:
        bias, risk_level = "資料不足", "中"
    elif pct > 0.6:
        bias, risk_level = "短線偏多", "中"
    elif pct < -0.6:
        bias, risk_level = "短線偏空", "高"
    else:
        bias, risk_level = "區間震盪", "中"
    reasons = [
        f"最新變動 {item.get('pct') or '--'}，資料日期 {item.get('date') or '--'}。",
        f"近 20 根日線支撐 {support:,.2f}。" if support is not None else "近 20 根日線資料不足，暫不估算支撐。",
        f"近 20 根日線壓力 {resistance:,.2f}。" if resistance is not None else "近 20 根日線資料不足，暫不估算壓力。",
    ]
    if item.get("openInterest") not in {None, "--"}:
        reasons.append(f"未平倉量 {item.get('openInterest')}，需與價格及保證金風險同步判讀。")
    analysis = {
        "target": item.get("symbol"),
        "bias": bias,
        "supportLevel": support,
        "resistanceLevel": resistance,
        "riskLevel": risk_level,
        "reasons": reasons,
        "scenarios": [
            {"name": "偏多", "condition": "突破近 20 日壓力並有量能確認。", "view": "採分批與停損管理，避免槓桿過度集中。"},
            {"name": "震盪", "condition": "價格維持在支撐與壓力之間。", "view": "控制部位，等待方向與未平倉變化同步。"},
            {"name": "偏空", "condition": "跌破近 20 日支撐且未平倉風險上升。", "view": "降低槓桿並檢查保證金與停損。"},
        ],
        "disclaimer": "AI 分析以公開行情與系統規則計算，僅供研究參考，不保證獲利。",
    }
    return enrich_futures_ai_decision(analysis, item, candles)


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


TAIFEX_INSTITUTION_ITEM_LABEL_MAP = {"自營商": "自營商", "投信": "投信", "外資及陸資": "外資"}


def fetch_taifex_institution_detail_rows(product: str) -> list[dict[str, Any]]:
    contract_name = PRODUCT_TO_TAIFEX_INSTITUTION_CONTRACT.get(product)
    if not contract_name:
        return []
    is_option = product in {"TXO", "STO", "ETO"}
    url = TAIFEX_INSTITUTION_OPTIONS_DETAIL_OPENAPI_URL if is_option else TAIFEX_INSTITUTION_FUTURES_DETAIL_OPENAPI_URL
    rows = fetch_taifex_openapi_list(url, TAIFEX_INSTITUTION_DETAIL_CACHE_SECONDS)
    return [row for row in rows if str(row.get("ContractCode") or "").strip() == contract_name]


def build_institution_payload_live(product: str, source_url: str) -> dict[str, Any] | None:
    try:
        rows = fetch_taifex_institution_detail_rows(product)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("TAIFEX institution live fetch failed for %s: %s", product, exc)
        return None
    if not rows:
        return None
    trade_date = ""
    net_total = 0.0
    long_total = 0.0
    short_total = 0.0
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        raw_label = str(row.get("Item") or "").strip()
        label = TAIFEX_INSTITUTION_ITEM_LABEL_MAP.get(raw_label, raw_label)
        long_v = parse_taifex_market_number(row.get("TradingVolume(Long)")) or 0
        short_v = parse_taifex_market_number(row.get("TradingVolume(Short)")) or 0
        net_v = parse_taifex_market_number(row.get("TradingVolume(Net)"))
        if net_v is None:
            net_v = long_v - short_v
        trade_date = normalize_taifex_date_text(row.get("Date")) or trade_date
        long_total += long_v
        short_total += short_v
        net_total += net_v
        out_rows.append({
            "institution": label,
            "longContracts": long_v,
            "shortContracts": short_v,
            "netContracts": net_v,
            "status": "connected",
        })
    out_rows.append({
        "institution": "合計",
        "longContracts": long_total,
        "shortContracts": short_total,
        "netContracts": net_total,
        "status": "connected",
    })
    return {
        "product": product,
        "tradeDate": trade_date or None,
        "rows": out_rows,
        "summary": {
            "netContracts": net_total,
            "bias": "法人偏多" if net_total > 0 else "法人偏空" if net_total < 0 else "法人中性",
            "status": "connected",
        },
        "source": {"name": "TAIFEX OpenAPI 三大法人-區分期貨與選擇權契約-依日期", "url": source_url},
        "message": f"{product} 法人交易口數已由 TAIFEX OpenAPI 即時彙總取得，資料日期 {trade_date or '--'}。",
    }


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


def normalize_us_market_search_item(item: dict[str, Any]) -> dict[str, Any]:
    symbol = str(item.get("symbol") or "").strip().upper()
    name = str(item.get("name") or item.get("shortname") or item.get("longname") or symbol).strip()
    quote_type = str(item.get("quoteType") or item.get("type") or "").upper()
    if "ETF" in quote_type or "FUND" in quote_type:
        group = "美股 ETF"
        item_type = "ETF"
    elif item.get("group"):
        group = str(item.get("group"))
        item_type = str(item.get("type") or "美股 / ETF")
    else:
        group = "美股個股"
        item_type = "美股個股"
    return {
        "symbol": symbol,
        "name": name,
        "type": item_type,
        "group": group,
        "exchange": item.get("exchange") or item.get("exchDisp") or "",
        "nyseUrl": item.get("nyseUrl") or item.get("url") or "",
        "source": item.get("source") or "Yahoo Finance",
    }


def normalize_us_symbol_for_yahoo(symbol: str) -> str:
    clean = str(symbol or "").strip().upper()
    if "." in clean and not clean.startswith("^"):
        return clean.replace(".", "-")
    return clean


def parse_nasdaq_symbol_directory(text: str, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or "|" not in lines[0]:
        return rows
    headers = lines[0].split("|")
    exchange_map = {
        "A": "NYSE American",
        "N": "NYSE",
        "P": "NYSE Arca",
        "Z": "Cboe BZX",
        "V": "IEX",
    }
    for line in lines[1:]:
        if line.startswith("File Creation Time"):
            break
        values = line.split("|")
        if len(values) != len(headers):
            continue
        item = dict(zip(headers, values))
        test_issue = str(item.get("Test Issue") or "").upper()
        if test_issue == "Y":
            continue
        symbol = str(item.get("Symbol") or item.get("ACT Symbol") or "").strip().upper()
        name = str(item.get("Security Name") or symbol).strip()
        if not symbol or not name:
            continue
        is_etf = str(item.get("ETF") or "").upper() == "Y"
        exchange_code = str(item.get("Exchange") or "").upper()
        exchange = "NASDAQ" if source == "Nasdaq Trader Nasdaq Listed" else exchange_map.get(exchange_code, exchange_code)
        rows.append(normalize_us_market_search_item({
            "symbol": normalize_us_symbol_for_yahoo(symbol),
            "name": name,
            "type": "Listed ETF" if is_etf else "Listed Equity",
            "group": "美股 ETF" if is_etf else "美股個股",
            "exchange": exchange,
            "source": source,
        }))
    return rows


def fetch_nasdaq_trader_us_listed_universe(force: bool = False) -> tuple[list[dict[str, Any]], dict[str, int]]:
    now = time.time()
    with cache_lock:
        cached = cache_data.get("us_listed_universe") or {}
        if (
            not force
            and cached.get("items")
            and now - float(cached.get("stored_at") or 0) < US_LISTED_UNIVERSE_CACHE_SECONDS
        ):
            return list(cached.get("items") or []), dict(cached.get("totals") or {})

    is_leader, flight = claim_cache_flight("us-listed-universe")
    if not is_leader:
        flight.wait(CACHE_FLIGHT_WAIT_SECONDS)
        with cache_lock:
            refreshed = cache_data.get("us_listed_universe") or {}
            if refreshed.get("items"):
                return list(refreshed.get("items") or []), dict(refreshed.get("totals") or {})
        raise RuntimeError("美股上市清單同步未完成，請稍後再試")

    try:
        sources = [
            (NASDAQ_LISTED_URL, "Nasdaq Trader Nasdaq Listed"),
            (NASDAQ_OTHER_LISTED_URL, "Nasdaq Trader Other Listed"),
        ]
        items: list[dict[str, Any]] = []
        for url, source in sources:
            text = fetch_text(url, timeout=12)
            items.extend(parse_nasdaq_symbol_directory(text, source))

        merged: dict[str, dict[str, Any]] = {}
        for item in [*items, *US_MARKET_SEARCH_UNIVERSE]:
            symbol = item.get("symbol")
            if symbol and symbol not in merged:
                merged[symbol] = normalize_us_market_search_item(item)
        results = sorted(merged.values(), key=lambda item: (item.get("group") != "美股個股", item.get("symbol") or ""))
        totals = {
            "美股個股": sum(1 for item in results if item.get("group") == "美股個股"),
            "美股 ETF": sum(1 for item in results if item.get("group") == "美股 ETF"),
        }
        with cache_lock:
            cache_data["us_listed_universe"] = {"stored_at": now, "items": results, "totals": totals}
        return results, totals
    finally:
        finish_cache_flight("us-listed-universe", flight)


def fetch_us_listed_universe_with_fallback(force: bool = False) -> tuple[list[dict[str, Any]], dict[str, int], str]:
    """Nasdaq Trader is the primary live symbol directory; NYSE's directory is a second
    independent live source before ever falling back to the small built-in seed list."""
    try:
        universe, totals = fetch_nasdaq_trader_us_listed_universe(force)
        return universe, totals, "Nasdaq Trader 官方 Symbol Directory"
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Nasdaq Trader listed universe fetch failed, trying NYSE directory: %s", exc)
    try:
        equities, equity_total = fetch_nyse_directory_items(instrument_type="EQUITY", group="美股個股")
        etfs, etf_total = fetch_nyse_directory_items(instrument_type="EXCHANGE_TRADED_FUND", group="美股 ETF")
        merged: dict[str, dict[str, Any]] = {}
        for item in [*equities, *etfs, *US_MARKET_SEARCH_UNIVERSE]:
            symbol = item.get("symbol")
            if symbol and symbol not in merged:
                merged[symbol] = normalize_us_market_search_item(item)
        results = sorted(merged.values(), key=lambda item: (item.get("group") != "美股個股", item.get("symbol") or ""))
        return results, {"美股個股": equity_total, "美股 ETF": etf_total}, "NYSE Listings Directory"
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("NYSE listed universe fetch failed, using built-in seed list: %s", exc)
    universe = [normalize_us_market_search_item(item) for item in US_MARKET_SEARCH_UNIVERSE]
    totals = {
        "美股個股": sum(1 for item in universe if item.get("group") == "美股個股"),
        "美股 ETF": sum(1 for item in universe if item.get("group") == "美股 ETF"),
    }
    return universe, totals, "內建美股/ETF清單（Nasdaq Trader 與 NYSE 官方目錄皆暫時無法載入）"


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


def normalize_nyse_directory_item(item: dict[str, Any], group: str) -> dict[str, Any] | None:
    symbol = str(item.get("normalizedTicker") or item.get("symbolExchangeTicker") or "").strip().upper()
    name = str(item.get("instrumentName") or symbol).strip()
    if not symbol or not name:
        return None
    return normalize_us_market_search_item({
        "symbol": symbol,
        "name": name.title() if name.isupper() else name,
        "type": "NYSE 個股" if group == "美股個股" else "NYSE ETF",
        "group": group,
        "exchange": item.get("url", "").split("/quote/")[-1].split(":")[0] if item.get("url") else "",
        "nyseUrl": item.get("url") or "",
        "source": "NYSE Listings Directory",
    })


def fetch_nyse_us_market_search(query: str, limit_per_type: int = 40) -> tuple[list[dict[str, Any]], dict[str, int]]:
    keyword = query.strip()
    types = [
        ("EQUITY", "美股個股", "https://www.nyse.com/listings_directory/stock"),
        ("EXCHANGE_TRADED_FUND", "美股 ETF", "https://www.nyse.com/listings_directory/etf"),
    ]
    results: list[dict[str, Any]] = []
    totals: dict[str, int] = {}
    for instrument_type, group, referer in types:
        payload = {
            "instrumentType": instrument_type,
            "pageNumber": 1,
            "sortColumn": "NORMALIZED_TICKER",
            "sortOrder": "ASC",
            "maxResultsPerPage": limit_per_type,
            "filterToken": keyword,
        }
        response = post_json(
            NYSE_QUOTES_FILTER_URL,
            payload,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
                "Origin": "https://www.nyse.com",
                "Referer": referer,
            },
        )
        values = response.get("value") if isinstance(response, dict) else response if isinstance(response, list) else []
        if values:
            total = parse_float(str(values[0].get("total") or ""))
            totals[group] = int(total) if total is not None else len(values)
        else:
            totals[group] = 0
        for value in values or []:
            normalized = normalize_nyse_directory_item(value, group)
            if normalized:
                results.append(normalized)
    return results, totals


def fetch_nyse_directory_items(
    query: str = "",
    instrument_type: str = "EQUITY",
    group: str = "美股個股",
    limit: int = 7000,
) -> tuple[list[dict[str, Any]], int]:
    referer = "https://www.nyse.com/listings_directory/stock" if instrument_type == "EQUITY" else "https://www.nyse.com/listings_directory/etf"
    payload = {
        "instrumentType": instrument_type,
        "pageNumber": 1,
        "sortColumn": "NORMALIZED_TICKER",
        "sortOrder": "ASC",
        "maxResultsPerPage": limit,
        "filterToken": query.strip(),
    }
    response = post_json(
        NYSE_QUOTES_FILTER_URL,
        payload,
        timeout=14,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Origin": "https://www.nyse.com",
            "Referer": referer,
        },
    )
    values = response.get("value") if isinstance(response, dict) else response if isinstance(response, list) else []
    total = 0
    if values:
        parsed_total = parse_float(str(values[0].get("total") or ""))
        total = int(parsed_total) if parsed_total is not None else len(values)
    results = []
    for value in values or []:
        normalized = normalize_nyse_directory_item(value, group)
        if normalized:
            results.append(normalized)
    return results, total


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


def filter_us_etf_items(items: list[dict[str, Any]], query: str = "") -> list[dict[str, Any]]:
    keyword = query.strip().lower()
    results = []
    for item in items:
        normalized = normalize_us_market_search_item(item)
        if normalized.get("group") != "美股 ETF":
            continue
        if keyword:
            haystack = " ".join(str(normalized.get(key) or "").lower() for key in ("symbol", "name", "type", "exchange"))
            if keyword not in haystack:
                continue
        results.append(normalized)
    return results


def fetch_us_etf_directory_items(query: str = "", limit: int = 7000, refresh: bool = False) -> tuple[list[dict[str, Any]], int, str, str]:
    try:
        universe, totals = fetch_nasdaq_trader_us_listed_universe(refresh)
        filtered = filter_us_etf_items(universe, query)
        total = len(filtered) if query.strip() else int(totals.get("美股 ETF") or len(filtered))
        return filtered[:limit], total, "Nasdaq Trader 官方 Symbol Directory", ""
    except Exception as primary_exc:
        LOGGER.exception("Nasdaq Trader ETF directory fallback used", exc_info=primary_exc)
        try:
            results, total = fetch_nyse_directory_items(query, "EXCHANGE_TRADED_FUND", "美股 ETF", limit)
            return results, total, "NYSE Listings Directory", ""
        except Exception as secondary_exc:
            LOGGER.exception("NYSE ETF directory fallback used", exc_info=secondary_exc)
            fallback = filter_us_etf_items(US_MARKET_SEARCH_UNIVERSE, query)[:limit]
            return fallback, len(fallback), "內建美股 ETF 清單", "官方 ETF 目錄暫時無法載入，已改用內建清單"


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


def fetch_yahoo_us_market_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    params = urlencode({
        "q": query.strip(),
        "quotesCount": str(limit),
        "newsCount": "0",
        "enableFuzzyQuery": "true",
    })
    payload = fetch_json(f"{YAHOO_SEARCH_BASE}?{params}", timeout=8)
    quotes = payload.get("quotes") if isinstance(payload, dict) else []
    results = []
    for quote_item in quotes or []:
        quote_type = str(quote_item.get("quoteType") or "").upper()
        symbol = str(quote_item.get("symbol") or "").strip().upper()
        exchange = str(quote_item.get("exchange") or quote_item.get("exchDisp") or "")
        if not symbol or quote_type not in {"EQUITY", "ETF", "MUTUALFUND"}:
            continue
        if quote_type == "EQUITY" and "." in symbol:
            continue
        if exchange and not any(token in exchange.upper() for token in ("NMS", "NYQ", "NAS", "ASE", "PCX", "BATS", "NASDAQ", "NYSE", "AMEX")):
            continue
        results.append(normalize_us_market_search_item({
            "symbol": symbol,
            "name": quote_item.get("shortname") or quote_item.get("longname") or symbol,
            "quoteType": quote_type,
            "exchange": exchange,
            "source": "Yahoo Finance 搜尋",
        }))
    return results


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


def parse_cboe_option_symbol(contract_symbol: str) -> dict[str, Any] | None:
    match = re.match(r"^(.+?)(\d{6})([CP])(\d{8})$", str(contract_symbol or "").strip().upper())
    if not match:
        return None
    root, date_code, option_type, strike_code = match.groups()
    year = 2000 + int(date_code[:2])
    month = int(date_code[2:4])
    day = int(date_code[4:6])
    try:
        expiration_dt = datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None
    return {
        "root": root,
        "expiration": int(expiration_dt.timestamp()),
        "expirationDate": expiration_dt.strftime("%Y-%m-%d"),
        "optionType": "call" if option_type == "C" else "put",
        "strike": int(strike_code) / 1000,
    }


def parse_cboe_expiration_request(value: str | None) -> int | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    if clean.isdigit():
        if len(clean) == 6:
            parsed = parse_cboe_option_symbol(f"X{clean}C00000000")
            return int(parsed["expiration"]) if parsed else None
        timestamp = int(clean)
        return timestamp // 1000 if timestamp > 100000000000 else timestamp
    for date_format in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return int(datetime.strptime(clean, date_format).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    return None


def normalize_cboe_option_contract(contract: dict[str, Any], clean_symbol: str) -> dict[str, Any] | None:
    parsed = parse_cboe_option_symbol(str(contract.get("option") or ""))
    if not parsed or parsed["root"] != clean_symbol:
        return None
    last_price = contract.get("last_trade_price")
    if last_price is None:
        last_price = contract.get("theo")
    return {
        "contractSymbol": contract.get("option") or "",
        "strike": parsed["strike"],
        "lastPrice": last_price,
        "bid": contract.get("bid"),
        "ask": contract.get("ask"),
        "change": contract.get("change"),
        "percentChange": contract.get("percent_change"),
        "volume": contract.get("volume"),
        "openInterest": contract.get("open_interest"),
        "impliedVolatility": contract.get("iv"),
        "expiration": parsed["expiration"],
        "expirationDate": parsed["expirationDate"],
        "inTheMoney": None,
        "delta": contract.get("delta"),
        "gamma": contract.get("gamma"),
        "theta": contract.get("theta"),
        "vega": contract.get("vega"),
        "rho": contract.get("rho"),
        "type": parsed["optionType"],
    }


def pick_cboe_expiration(expirations: list[int], requested: int | None = None) -> int | None:
    if not expirations:
        return None
    if requested in expirations:
        return requested
    today = datetime.now(TZ).date()
    future_expirations = [
        value
        for value in expirations
        if datetime.fromtimestamp(value, timezone.utc).date() >= today
    ]
    return future_expirations[0] if future_expirations else expirations[0]


def sum_contract_metric(contracts: list[dict[str, Any]], key: str) -> int:
    total = 0.0
    for contract in contracts:
        value = parse_float(str(contract.get(key) or ""))
        if value is not None:
            total += value
    return int(round(total))


def build_cboe_options_chain(symbol: str, expiration: str | None = None) -> dict[str, Any]:
    clean_symbol = normalize_us_symbol_for_yahoo(re.sub(r"[^A-Za-z0-9=.^_-]", "", symbol or "").upper())
    if not clean_symbol:
        return {"error": "Invalid option underlying symbol."}
    contract_root = clean_symbol[1:] if clean_symbol.startswith("_") else clean_symbol
    cache_key = f"{clean_symbol}:{expiration or ''}"
    if not global_market_refresh_requested():
        cached_chain = read_memory_cache("us_options_chains", cache_key, US_OPTIONS_CHAIN_CACHE_SECONDS)
        if cached_chain is not None:
            return copy.deepcopy(cached_chain)
    url = f"{CBOE_OPTIONS_BASE}/{quote(clean_symbol)}.json"
    payload = fetch_json(url, timeout=15)
    data = payload.get("data") if isinstance(payload, dict) else None
    raw_options = data.get("options") if isinstance(data, dict) else None
    if not isinstance(raw_options, list):
        return {"symbol": clean_symbol, "error": "Cboe options source returned no contracts.", "sourceUrl": url}

    normalized = [
        item
        for item in (normalize_cboe_option_contract(contract, contract_root) for contract in raw_options)
        if item is not None
    ]
    if not normalized:
        return {"symbol": clean_symbol, "error": "Cboe options source returned no contracts.", "sourceUrl": url}

    expirations = sorted({int(item["expiration"]) for item in normalized})
    selected_expiration = pick_cboe_expiration(expirations, parse_cboe_expiration_request(expiration))
    selected_contracts = [item for item in normalized if item["expiration"] == selected_expiration]
    calls = sorted((item for item in selected_contracts if item["type"] == "call"), key=lambda item: item["strike"])
    puts = sorted((item for item in selected_contracts if item["type"] == "put"), key=lambda item: item["strike"])

    result = {
        "symbol": clean_symbol,
        "name": data.get("symbol") or clean_symbol,
        "price": data.get("current_price"),
        "change": data.get("price_change"),
        "pct": data.get("price_change_percent"),
        "currency": "USD",
        "source": "Cboe Delayed Quotes Options",
        "sourceUrl": url,
        "timestamp": payload.get("timestamp"),
        "expirationDates": expirations,
        "selectedExpiration": selected_expiration,
        "summary": {
            "callCount": len(calls),
            "putCount": len(puts),
            "totalContracts": len(calls) + len(puts),
            "callOpenInterest": sum_contract_metric(calls, "openInterest"),
            "putOpenInterest": sum_contract_metric(puts, "openInterest"),
        },
        "calls": calls[:200],
        "puts": puts[:200],
    }
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result))
    return result


def yahoo_options_headers(accept: str = "application/json") -> dict[str, str]:
    return {
        "User-Agent": NASDAQ_USER_AGENT,
        "Accept": accept,
        "Referer": "https://finance.yahoo.com/",
        "Origin": "https://finance.yahoo.com",
    }


def get_yahoo_options_crumb(symbol: str) -> str:
    now = time.time()
    with cache_lock:
        cached_value = str(_yahoo_options_crumb.get("value") or "")
        cached_at = float(_yahoo_options_crumb.get("stored_at") or 0)
    if cached_value and now - cached_at < YAHOO_OPTIONS_CRUMB_CACHE_SECONDS:
        return cached_value

    page_symbol = quote(symbol or "SPY", safe="")
    page_url = f"{YAHOO_OPTIONS_PAGE_BASE}/{page_symbol}/options/"
    page_req = Request(page_url, headers=yahoo_options_headers("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"))
    with _yahoo_options_opener.open(page_req, timeout=20) as response:
        response.read(2048)

    crumb_req = Request(YAHOO_OPTIONS_CRUMB_URL, headers=yahoo_options_headers("text/plain,*/*"))
    with _yahoo_options_opener.open(crumb_req, timeout=20) as response:
        crumb = response.read().decode("utf-8").strip()
    if not crumb:
        raise RuntimeError("Yahoo options crumb is empty.")
    with cache_lock:
        _yahoo_options_crumb["value"] = crumb
        _yahoo_options_crumb["stored_at"] = now
    return crumb


def fetch_yahoo_options_payload(clean_symbol: str, expiration: str | None = None, retry: bool = True) -> dict[str, Any]:
    crumb = get_yahoo_options_crumb(clean_symbol)
    params = {"crumb": crumb}
    requested_expiration = parse_cboe_expiration_request(expiration)
    if requested_expiration is not None:
        params["date"] = str(requested_expiration)
    url = f"{YAHOO_OPTIONS_CHAIN_BASE}/{quote(clean_symbol, safe='')}?{urlencode(params)}"
    req = Request(url, headers=yahoo_options_headers("application/json, text/plain, */*"))
    try:
        with _yahoo_options_opener.open(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if retry and exc.code in {401, 403}:
            with cache_lock:
                _yahoo_options_crumb["value"] = ""
                _yahoo_options_crumb["stored_at"] = 0.0
            return fetch_yahoo_options_payload(clean_symbol, expiration, retry=False)
        raise


def normalize_yahoo_option_contract(contract: dict[str, Any]) -> dict[str, Any]:
    expiration = contract.get("expiration")
    expiration_date = None
    if expiration is not None:
        try:
            expiration_date = datetime.fromtimestamp(int(expiration), timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            expiration_date = None
    symbol = str(contract.get("contractSymbol") or "")
    return {
        "contractSymbol": symbol,
        "strike": contract.get("strike"),
        "lastPrice": contract.get("lastPrice"),
        "bid": contract.get("bid"),
        "ask": contract.get("ask"),
        "change": contract.get("change"),
        "percentChange": contract.get("percentChange"),
        "volume": contract.get("volume"),
        "openInterest": contract.get("openInterest"),
        "impliedVolatility": contract.get("impliedVolatility"),
        "expiration": expiration,
        "expirationDate": expiration_date,
        "inTheMoney": contract.get("inTheMoney"),
        "type": "put" if symbol.upper().rfind("P") > symbol.upper().rfind("C") else "call",
    }


def build_yahoo_options_chain(symbol: str, expiration: str | None = None) -> dict[str, Any]:
    clean_symbol = normalize_us_symbol_for_yahoo(re.sub(r"[^A-Za-z0-9=.^_-]", "", symbol or "").upper())
    if not clean_symbol:
        return {"error": "Invalid option underlying symbol."}
    cache_key = f"yahoo:{clean_symbol}:{expiration or ''}"
    if not global_market_refresh_requested():
        cached_chain = read_memory_cache("us_options_chains", cache_key, YAHOO_OPTIONS_CHAIN_CACHE_SECONDS)
        if cached_chain is not None:
            return copy.deepcopy(cached_chain)

    payload = fetch_yahoo_options_payload(clean_symbol, expiration)
    option_chain = payload.get("optionChain") if isinstance(payload, dict) else {}
    result = ((option_chain or {}).get("result") or [None])[0]
    if not result:
        error = (option_chain or {}).get("error") or {}
        description = error.get("description") if isinstance(error, dict) else None
        return {"symbol": clean_symbol, "error": description or "Yahoo options source returned no contracts.", "source": "Yahoo Finance Options"}

    quote_info = result.get("quote") or {}
    expirations = [int(value) for value in (result.get("expirationDates") or []) if str(value).isdigit()]
    options = (result.get("options") or [{}])[0] or {}
    selected_expiration = options.get("expirationDate") or pick_cboe_expiration(expirations, parse_cboe_expiration_request(expiration))
    calls = [normalize_yahoo_option_contract(item) for item in (options.get("calls") or [])]
    puts = [normalize_yahoo_option_contract(item) for item in (options.get("puts") or [])]
    if not calls and not puts:
        return {"symbol": clean_symbol, "error": "Yahoo options source returned no contracts.", "source": "Yahoo Finance Options"}

    result_payload = {
        "symbol": clean_symbol,
        "name": quote_info.get("shortName") or quote_info.get("longName") or quote_info.get("symbol") or clean_symbol,
        "price": quote_info.get("regularMarketPrice"),
        "change": quote_info.get("regularMarketChange"),
        "pct": quote_info.get("regularMarketChangePercent"),
        "currency": quote_info.get("currency") or "USD",
        "source": "Yahoo Finance Options",
        "sourceUrl": f"https://finance.yahoo.com/quote/{quote(clean_symbol, safe='')}/options/",
        "timestamp": payload.get("timestamp"),
        "expirationDates": expirations,
        "selectedExpiration": selected_expiration,
        "summary": {
            "callCount": len(calls),
            "putCount": len(puts),
            "totalContracts": len(calls) + len(puts),
            "callOpenInterest": sum_contract_metric(calls, "openInterest"),
            "putOpenInterest": sum_contract_metric(puts, "openInterest"),
        },
        "calls": sorted(calls, key=lambda item: parse_float(str(item.get("strike") or "")) or 0)[:200],
        "puts": sorted(puts, key=lambda item: parse_float(str(item.get("strike") or "")) or 0)[:200],
    }
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result_payload))
    return result_payload


def parse_public_options_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    cleaned = re.sub(r"[^0-9.+-]", "", str(value).replace(",", "").strip())
    if not cleaned or cleaned in {"+", "-", ".", "+.", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def unix_timestamp_from_iso_date(date_text: str | None) -> int | None:
    if not date_text:
        return None
    try:
        return int(datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def parse_barchart_expiration_date(date_text: str | None) -> tuple[str | None, int | None]:
    cleaned = str(date_text or "").strip()
    if not cleaned:
        return None, None
    for pattern in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(cleaned, pattern).replace(tzinfo=timezone.utc)
            return parsed.strftime("%Y-%m-%d"), int(parsed.timestamp())
        except ValueError:
            continue
    return None, None


def barchart_options_headers(accept: str = "application/json", referer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": NASDAQ_USER_AGENT,
        "Accept": accept,
    }
    if referer:
        headers["Referer"] = referer
    return headers


def fetch_barchart_options_context(root: str) -> dict[str, Any]:
    clean_root = re.sub(r"[^A-Za-z0-9]", "", str(root or "").upper())
    if not clean_root:
        raise RuntimeError("Barchart futures options root is empty.")
    page_symbol = f"{clean_root}*0"
    page_url = f"{BARCHART_FUTURES_OPTIONS_PAGE_BASE}/{quote(page_symbol, safe='')}/options"
    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    page_req = Request(page_url, headers=barchart_options_headers("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"))
    with opener.open(page_req, timeout=25) as response:
        html = response.read().decode("utf-8", errors="replace")
    decoded = unescape(html)
    contract_match = re.search(
        r'data-api-config="\{"api":\{"method":"quotes","symbol":"([^"]+)","list":"futures\.options"',
        decoded,
    )
    if not contract_match:
        raise RuntimeError("Barchart options source returned no contract month.")

    text = re.sub(r"<[^>]+>", " ", decoded)
    text = re.sub(r"\s+", " ", text)
    expiration_date = None
    expiration_ts = None
    expiration_match = re.search(r"to expiration on\s+(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
    if expiration_match:
        expiration_date, expiration_ts = parse_barchart_expiration_date(expiration_match.group(1))
    iv_match = re.search(r"Implied Volatility:\s*([0-9.]+)%", text, re.IGNORECASE)
    option_point_match = re.search(r"Price Value of Option point:\s*\$?([0-9,.]+)", text, re.IGNORECASE)
    price_match = re.search(r'"lastPrice":\s*([0-9.]+)', decoded)

    xsrf = ""
    for cookie in cookie_jar:
        if cookie.name == "XSRF-TOKEN":
            xsrf = cookie.value
            break

    return {
        "root": clean_root,
        "contract": contract_match.group(1),
        "pageUrl": page_url,
        "opener": opener,
        "xsrf": xsrf,
        "expirationDate": expiration_date,
        "expiration": expiration_ts,
        "weightedImpliedVolatility": parse_public_options_number(iv_match.group(1)) if iv_match else None,
        "optionPointValue": parse_public_options_number(option_point_match.group(1)) if option_point_match else None,
        "price": parse_public_options_number(price_match.group(1)) if price_match else None,
    }


def normalize_barchart_option_contract(contract: dict[str, Any], option_type: str, expiration: int | None, expiration_date: str | None) -> dict[str, Any] | None:
    strike = parse_public_options_number(contract.get("strike"))
    if strike is None:
        return None
    option_type_clean = "put" if str(option_type or contract.get("optionType") or "").lower().startswith("p") else "call"
    return {
        "contractSymbol": contract.get("longSymbol") or contract.get("symbol") or "",
        "strike": strike,
        "lastPrice": parse_public_options_number(contract.get("lastPrice")),
        "bid": parse_public_options_number(contract.get("bidPrice")),
        "ask": parse_public_options_number(contract.get("askPrice")),
        "change": parse_public_options_number(contract.get("priceChange")),
        "percentChange": None,
        "volume": parse_public_options_number(contract.get("volume")),
        "openInterest": parse_public_options_number(contract.get("openInterest")),
        "impliedVolatility": parse_public_options_number(contract.get("impliedVolatility")),
        "expiration": expiration,
        "expirationDate": expiration_date,
        "inTheMoney": None,
        "type": option_type_clean,
    }


def build_barchart_futures_options_chain(symbol: str, expiration: str | None = None) -> dict[str, Any]:
    clean_symbol = normalize_us_symbol_for_yahoo(re.sub(r"[^A-Za-z0-9=.^_-]", "", symbol or "").upper())
    root = BARCHART_FUTURES_OPTIONS_ROOTS.get(clean_symbol)
    if not root:
        return {"symbol": clean_symbol, "error": "Barchart futures options source is not mapped for this product."}

    cache_key = f"barchart:{clean_symbol}:{expiration or ''}"
    if not global_market_refresh_requested():
        cached_chain = read_memory_cache("us_options_chains", cache_key, BARCHART_OPTIONS_CHAIN_CACHE_SECONDS)
        if cached_chain is not None:
            return copy.deepcopy(cached_chain)

    context = fetch_barchart_options_context(root)
    contract_symbol = re.sub(r"[^A-Za-z0-9]", "", str(expiration or context["contract"]).upper()) or context["contract"]
    params = {
        "symbol": contract_symbol,
        "list": "futures.options",
        "fields": "strike,lastPrice,priceChange,bidPrice,askPrice,volume,openInterest,impliedVolatility,tradeTime,longSymbol,optionType,symbol",
        "groupBy": "optionType",
        "orderBy": "strike",
        "orderDir": "asc",
        "meta": "field.shortName,field.description,field.type",
    }
    api_url = f"{BARCHART_CORE_QUOTES_URL}?{urlencode(params)}"
    headers = barchart_options_headers("application/json, text/plain, */*", context["pageUrl"])
    if context.get("xsrf"):
        headers["X-XSRF-TOKEN"] = unquote(str(context["xsrf"]))
    api_req = Request(api_url, headers=headers)
    with context["opener"].open(api_req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    data = payload.get("data") if isinstance(payload, dict) else {}
    raw_calls = data.get("Call") or data.get("call") or []
    raw_puts = data.get("Put") or data.get("put") or []
    expiration_ts = context.get("expiration")
    expiration_date = context.get("expirationDate")
    calls = [
        item
        for item in (normalize_barchart_option_contract(contract, "call", expiration_ts, expiration_date) for contract in raw_calls)
        if item is not None
    ]
    puts = [
        item
        for item in (normalize_barchart_option_contract(contract, "put", expiration_ts, expiration_date) for contract in raw_puts)
        if item is not None
    ]
    if not calls and not puts:
        return {"symbol": clean_symbol, "error": "Barchart futures options source returned no contracts.", "source": "Barchart Futures Options", "sourceUrl": context["pageUrl"]}

    selected_expiration = f"{contract_symbol} {expiration_date}".strip() if expiration_date else contract_symbol
    result_payload = {
        "symbol": clean_symbol,
        "name": f"{root} Futures Options",
        "price": context.get("price"),
        "change": None,
        "pct": None,
        "currency": "USD",
        "source": "Barchart Futures Options",
        "sourceUrl": context["pageUrl"],
        "timestamp": datetime.now(TZ).isoformat(),
        "expirationDates": [],
        "selectedExpiration": selected_expiration,
        "selectedExpirationTimestamp": expiration_ts,
        "selectedExpirationSymbol": contract_symbol,
        "summary": {
            "callCount": len(calls),
            "putCount": len(puts),
            "totalContracts": len(calls) + len(puts),
            "callOpenInterest": sum_contract_metric(calls, "openInterest"),
            "putOpenInterest": sum_contract_metric(puts, "openInterest"),
            "weightedImpliedVolatility": context.get("weightedImpliedVolatility"),
            "optionPointValue": context.get("optionPointValue"),
        },
        "calls": sorted(calls, key=lambda item: item["strike"]),
        "puts": sorted(puts, key=lambda item: item["strike"]),
    }
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result_payload))
    return result_payload


def parse_deribit_instrument_name(name: str) -> dict[str, Any] | None:
    match = re.match(r"^([A-Z]+)-(\d{1,2}[A-Z]{3}\d{2})-([0-9.]+)-([CP])$", str(name or "").upper())
    if not match:
        return None
    try:
        expiration_dt = datetime.strptime(match.group(2), "%d%b%y").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return {
        "currency": match.group(1),
        "expiration": int(expiration_dt.timestamp()),
        "expirationDate": expiration_dt.strftime("%Y-%m-%d"),
        "strike": float(match.group(3)),
        "type": "call" if match.group(4) == "C" else "put",
    }


def normalize_deribit_option_contract(contract: dict[str, Any]) -> dict[str, Any] | None:
    parsed = parse_deribit_instrument_name(str(contract.get("instrument_name") or ""))
    if not parsed:
        return None
    return {
        "contractSymbol": contract.get("instrument_name") or "",
        "strike": parsed["strike"],
        "lastPrice": parse_public_options_number(contract.get("mark_price")),
        "bid": parse_public_options_number(contract.get("bid_price")),
        "ask": parse_public_options_number(contract.get("ask_price")),
        "change": None,
        "percentChange": None,
        "volume": parse_public_options_number(contract.get("volume")),
        "openInterest": parse_public_options_number(contract.get("open_interest")),
        "impliedVolatility": parse_public_options_number(contract.get("mark_iv")),
        "expiration": parsed["expiration"],
        "expirationDate": parsed["expirationDate"],
        "inTheMoney": None,
        "type": parsed["type"],
    }


def build_deribit_options_chain(symbol: str, expiration: str | None = None) -> dict[str, Any]:
    clean_symbol = re.sub(r"[^A-Za-z0-9_-]", "", symbol or "").upper()
    currency = DERIBIT_OPTIONS_CURRENCY_BY_SYMBOL.get(clean_symbol)
    if not currency:
        return {"symbol": clean_symbol, "error": "Deribit options source is not mapped for this product."}

    cache_key = f"deribit:{clean_symbol}:{expiration or ''}"
    if not global_market_refresh_requested():
        cached_chain = read_memory_cache("us_options_chains", cache_key, DERIBIT_OPTIONS_CHAIN_CACHE_SECONDS)
        if cached_chain is not None:
            return copy.deepcopy(cached_chain)

    params = {"currency": currency, "kind": "option"}
    url = f"{DERIBIT_OPTIONS_SUMMARY_URL}?{urlencode(params)}"
    payload = fetch_json(url, timeout=20)
    raw_items = payload.get("result") if isinstance(payload, dict) else []
    normalized = [
        item
        for item in (normalize_deribit_option_contract(contract) for contract in (raw_items or []))
        if item is not None
    ]
    if not normalized:
        return {"symbol": clean_symbol, "error": "Deribit options source returned no contracts.", "source": "Deribit Options", "sourceUrl": url}

    expirations = sorted({int(item["expiration"]) for item in normalized})
    selected_expiration = pick_cboe_expiration(expirations, parse_cboe_expiration_request(expiration))
    selected_contracts = [item for item in normalized if item["expiration"] == selected_expiration]
    calls = sorted((item for item in selected_contracts if item["type"] == "call"), key=lambda item: item["strike"])
    puts = sorted((item for item in selected_contracts if item["type"] == "put"), key=lambda item: item["strike"])
    selected_raw = [
        contract
        for contract in (raw_items or [])
        if (parse_deribit_instrument_name(str(contract.get("instrument_name") or "")) or {}).get("expiration") == selected_expiration
    ]
    underlying_values = [
        parse_public_options_number(contract.get("underlying_price"))
        for contract in selected_raw
        if parse_public_options_number(contract.get("underlying_price")) is not None
    ]
    price = underlying_values[0] if underlying_values else None

    result_payload = {
        "symbol": clean_symbol,
        "name": f"{currency} Options",
        "price": price,
        "change": None,
        "pct": None,
        "currency": "USD",
        "source": "Deribit Options",
        "sourceUrl": url,
        "timestamp": datetime.now(TZ).isoformat(),
        "expirationDates": expirations,
        "selectedExpiration": selected_expiration,
        "summary": {
            "callCount": len(calls),
            "putCount": len(puts),
            "totalContracts": len(calls) + len(puts),
            "callOpenInterest": sum_contract_metric(calls, "openInterest"),
            "putOpenInterest": sum_contract_metric(puts, "openInterest"),
        },
        "calls": calls,
        "puts": puts,
    }
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result_payload))
    return result_payload


def parse_bybit_option_symbol(symbol: str) -> dict[str, Any] | None:
    match = re.match(
        r"^([A-Z0-9]+)-(\d{1,2}[A-Z]{3}\d{2})-([0-9.]+)-([CP])(?:-[A-Z0-9]+)?$",
        str(symbol or "").strip().upper(),
    )
    if not match:
        return None
    try:
        expiration_dt = datetime.strptime(match.group(2), "%d%b%y").replace(tzinfo=timezone.utc)
        strike = float(match.group(3))
    except ValueError:
        return None
    return {
        "baseCoin": match.group(1),
        "expiration": int(expiration_dt.timestamp()),
        "expirationDate": expiration_dt.strftime("%Y-%m-%d"),
        "strike": strike,
        "type": "call" if match.group(4) == "C" else "put",
    }


def normalize_bybit_option_contract(contract: dict[str, Any], base_coin: str) -> dict[str, Any] | None:
    parsed = parse_bybit_option_symbol(str(contract.get("symbol") or ""))
    if not parsed or parsed["baseCoin"] != base_coin:
        return None
    last_price = parse_public_options_number(contract.get("lastPrice"))
    mark_price = parse_public_options_number(contract.get("markPrice"))
    return {
        "contractSymbol": contract.get("symbol") or "",
        "strike": parsed["strike"],
        "lastPrice": last_price if last_price not in (None, 0) else mark_price,
        "bid": parse_public_options_number(contract.get("bid1Price")),
        "ask": parse_public_options_number(contract.get("ask1Price")),
        "change": parse_public_options_number(contract.get("change24h")),
        "percentChange": parse_public_options_number(contract.get("change24h")),
        "volume": parse_public_options_number(contract.get("volume24h")),
        "openInterest": parse_public_options_number(contract.get("openInterest")),
        "impliedVolatility": parse_public_options_number(contract.get("markIv")),
        "expiration": parsed["expiration"],
        "expirationDate": parsed["expirationDate"],
        "inTheMoney": None,
        "delta": parse_public_options_number(contract.get("delta")),
        "gamma": parse_public_options_number(contract.get("gamma")),
        "theta": parse_public_options_number(contract.get("theta")),
        "vega": parse_public_options_number(contract.get("vega")),
        "type": parsed["type"],
    }


def build_bybit_options_chain(symbol: str, expiration: str | None = None) -> dict[str, Any]:
    clean_symbol = re.sub(r"[^A-Za-z0-9_-]", "", symbol or "").upper()
    base_coin = BYBIT_OPTIONS_BASE_COIN_BY_SYMBOL.get(clean_symbol)
    if not base_coin:
        return {"symbol": clean_symbol, "error": "Bybit options source is not mapped for this product."}

    cache_key = f"bybit:{clean_symbol}:{expiration or ''}"
    if not global_market_refresh_requested():
        cached_chain = read_memory_cache("us_options_chains", cache_key, BYBIT_OPTIONS_CHAIN_CACHE_SECONDS)
        if cached_chain is not None:
            return copy.deepcopy(cached_chain)

    url = f"{BYBIT_OPTIONS_TICKERS_URL}?{urlencode({'category': 'option', 'baseCoin': base_coin})}"
    payload = fetch_json(url, timeout=30)
    result = payload.get("result") if isinstance(payload, dict) else {}
    raw_items = result.get("list") if isinstance(result, dict) else []
    normalized = [
        item
        for item in (normalize_bybit_option_contract(contract, base_coin) for contract in (raw_items or []))
        if item is not None
    ]
    if not normalized:
        message = str(payload.get("retMsg") or "Bybit options source returned no contracts.") if isinstance(payload, dict) else "Bybit options source returned no contracts."
        return {"symbol": clean_symbol, "error": message, "source": "Bybit Public Options API", "sourceUrl": url}

    expirations = sorted({int(item["expiration"]) for item in normalized})
    selected_expiration = pick_cboe_expiration(expirations, parse_cboe_expiration_request(expiration))
    selected_contracts = [item for item in normalized if item["expiration"] == selected_expiration]
    calls = sorted((item for item in selected_contracts if item["type"] == "call"), key=lambda item: item["strike"])
    puts = sorted((item for item in selected_contracts if item["type"] == "put"), key=lambda item: item["strike"])
    selected_symbols = {item["contractSymbol"] for item in selected_contracts}
    selected_raw = [item for item in (raw_items or []) if str(item.get("symbol") or "") in selected_symbols]
    price = next(
        (
            value
            for item in selected_raw
            for value in (
                parse_public_options_number(item.get("underlyingPrice")),
                parse_public_options_number(item.get("indexPrice")),
            )
            if value is not None
        ),
        None,
    )

    result_payload = {
        "symbol": clean_symbol,
        "name": f"{base_coin} Options",
        "price": price,
        "change": None,
        "pct": None,
        "currency": "USDT",
        "source": "Bybit Public Options API",
        "sourceUrl": url,
        "timestamp": datetime.now(TZ).isoformat(),
        "expirationDates": expirations,
        "selectedExpiration": selected_expiration,
        "summary": {
            "callCount": len(calls),
            "putCount": len(puts),
            "totalContracts": len(calls) + len(puts),
            "callOpenInterest": sum_contract_metric(calls, "openInterest"),
            "putOpenInterest": sum_contract_metric(puts, "openInterest"),
        },
        "calls": calls,
        "puts": puts,
    }
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result_payload))
    return result_payload

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


def build_public_options_chain(symbol: str, expiration: str | None = None) -> dict[str, Any]:
    clean_symbol = normalize_us_symbol_for_yahoo(re.sub(r"[^A-Za-z0-9=.^_-]", "", symbol or "").upper())
    if clean_symbol in BYBIT_OPTIONS_BASE_COIN_BY_SYMBOL:
        return build_bybit_options_chain(clean_symbol, expiration)
    if clean_symbol in DERIBIT_OPTIONS_CURRENCY_BY_SYMBOL:
        return build_deribit_options_chain(clean_symbol, expiration)
    if clean_symbol in BARCHART_FUTURES_OPTIONS_ROOTS:
        return build_barchart_futures_options_chain(clean_symbol, expiration)

    cboe_chain: dict[str, Any] | None = None
    cboe_error = ""
    try:
        cboe_chain = build_cboe_options_chain(clean_symbol, expiration)
        if not cboe_chain.get("error"):
            return cboe_chain
        cboe_error = str(cboe_chain.get("error") or "")
    except Exception as exc:
        LOGGER.warning("Cboe options source failed for %s", clean_symbol, exc_info=exc)
        cboe_error = "Cboe options source temporarily unavailable."

    return cboe_chain or {
        "symbol": clean_symbol,
        "error": cboe_error or "Options source returned no contracts.",
        "source": "Cboe Delayed Quotes Options",
        "fallbackBlocked": True,
        "fallbackBlockedReason": "API source is locked to the requested product's Call/Put strike chain.",
    }


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


def start_background_updater() -> None:
    global background_updater_started
    with background_updater_lock:
        if background_updater_started:
            return
        background_updater_started = True
    try:
        load_disk_cache()
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Initial disk cache load failed")
        with cache_lock:
            cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE
    thread = threading.Thread(target=update_loop, daemon=True)
    thread.start()


def background_updater_enabled() -> bool:
    return str(os.environ.get("MARKET_PULSE_DISABLE_BACKGROUND") or "").strip() != "1"


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
