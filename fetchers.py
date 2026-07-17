"""Generic HTTP fetch helpers extracted from app.py (TD-01 slice 3, batch 0),
extended with the TWSE/TPEX fetch_* functions and their supporting pure
utilities (batch 1).

These are the foundational functions ~80% of app.py's 86 `fetch_*` functions
build on: `fetch_json`/`fetch_nasdaq_json`/`post_json` for JSON APIs, and
`fetch_text`/`fetch_binary`/`fetch_form_text` for scraped/CSV/form-POSTed
sources with an optional memory-cache gate (`should_cache_external_text`,
gated to a handful of known-slow/rate-sensitive hosts). All six route outbound
requests through `security.py`'s `_urlopen_with_ssl_fallback`, so this module
is the single place SSL-fallback policy actually gets exercised from.

Batch 1 (TWSE/TPEX, 19 functions) also brings along a cluster of pure,
zero-dependency parsing/formatting/URL-building helpers that these fetchers
call directly (`parse_float`, `parse_roc_date`, `format_signed`,
`format_whole_number`, `format_percent`, `dataset_has_rows`,
`find_latest_dataset`, `shift_month`, `format_openapi_date`,
`pick_mapping_text`, `format_company_date`, `format_company_capital`,
`parse_compact_roc_date`, `normalize_market_request`, the live-search-dedup
helpers, and the `build_*_url` functions). Several of these are also used by
`build_*` functions that stay in app.py (e.g. `build_sector_history_snapshot`,
`build_live_sector_site_data`) - app.py imports them back from here, same as
it already does for `fetch_json` etc. Two batch-1 functions
(`fetch_stock_institutional_trade_for_date`, `fetch_stock_institutional_trade_history`)
call `build_stock_institutional_trade_record`/`build_stock_institutional_trade_summary`,
and `fetch_live_stock_universe`/`fetch_live_stock_search_results` call
`parse_all_stocks`/`parse_tpex_quotes`/`find_stock_by_query` - all four of
these are response-shape "builder" functions that stay in app.py, so those
calls use a deferred `import app` (module-level, not `from app import ...`)
exactly like `cache.py`'s `refresh_cache`/`update_loop` call `app.build_site_data`/
`app.refresh_tpex_cache` - this avoids a load-time circular import while
keeping `patch.object(app, "...")` on those builder functions working.

Batch 2 (Yahoo Finance global, 14 functions) brings the Yahoo chart/quote/news/
search fetchers plus their shared pure helpers (`build_yahoo_chart_series`,
`detect_tone`, `is_finite_positive`/`is_valid_ohlc_values`/`format_roc_date`,
`get_institutional_history_range_config`, `normalize_us_market_search_item`) -
app.py imports these back for its own builder/route code, same pattern as
batch 1. `fetch_yahoo_options_payload` is this batch's cookie-jar-opener
exception (own `_yahoo_options_cookie_jar`/`_yahoo_options_opener`, bypasses
`fetch_json`/`_urlopen_with_ssl_fallback` entirely) and calls
`app.parse_cboe_expiration_request` via a deferred import since that parser
belongs to the CBOE domain cluster staying in app.py until batch 5.
`fetch_taiwan_option_spot_snapshot` similarly calls `app.get_taiwan_option_product`
via deferred import - that's a TAIFEX-domain config lookup used by ~18 route/
builder call sites, not a generic parsing utility, so it stays in app.py.

Batch 3 (TAIFEX, 13 functions) brings the futures/options daily-report and
open-interest fetchers plus their exclusive HTML/CSV parsing helpers
(`select_taifex_daily_market_row`, `normalize_taifex_daily_market_row`,
`parse_taifex_daily_market_html_rows`, `parse_taifex_futures_download_candles`,
`parse_taifex_tx_open_interest`, `parse_taifex_open_interest_by_header`,
`build_taifex_daily_tick_csv_url`, `parse_taifex_daily_tick_csv_candle`,
`parse_taifex_query_date`) and the `taifex_open_interest_lock` politeness
semaphore that throttles TAIFEX's fragile HTML query-form endpoints. Two more
shared pure helpers (`parse_taifex_market_number`, `normalize_taifex_date_text`)
are also used by app.py builders (`build_taifex_stock_derivative_aggregate_item`,
`build_institution_payload_live`) that stay in app.py, so those import back.
Three functions in this batch reach into option-chain/Yahoo-Taiwan-technical
domain code that stays in app.py via a deferred `import app`, same pattern as
batch 2's CBOE/TAIFEX-config calls:
- `fetch_taifex_txo_option_chain` calls `app.get_taiwan_option_product`,
  `app.supplement_taifex_option_payload_with_yahoo_oi`,
  `app.parse_taifex_txo_option_rows`, `app.build_taifex_txo_option_payload`,
  and reads `app.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE`/`app.TAIWAN_OPTION_PRODUCTS`
  - these are large option-chain response builders and a 13-call-site config
  dict, not generic fetch-layer code.
- `fetch_taifex_futures_technical_candles` calls
  `app.find_yahoo_taiwan_future_technical_contract`,
  `app.infer_yahoo_taiwan_future_symbol_from_code`, and
  `app.build_yahoo_taiwan_future_technical_url` - these belong to the
  Yahoo-Taiwan-technical-analysis domain that moves in batch 4, not this one.
- `build_taifex_futures_interval_candles` (this batch's own exclusive helper)
  calls `app.build_derivative_candles`, a generic candle formatter shared by
  5+ other call sites across app.py's derivatives routes/builders.

Later batches move the remaining per-source fetchers (Yahoo Taiwan, everything
else). Two later-batch functions (`fetch_yahoo_tw_stock_resource`,
`fetch_barchart_options_context`) intentionally do NOT go through this
module's helpers - they call `_urlopen_with_ssl_fallback` directly or use
their own cookie-jar opener - documented when they move.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import logging
import math
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from html import unescape
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cache import (
    CACHE_FLIGHT_WAIT_SECONDS,
    _yahoo_options_crumb,
    cache_data,
    cache_lock,
    claim_cache_flight,
    finish_cache_flight,
    read_memory_cache,
    taifex_options_chain_inflight,
    taifex_options_chain_inflight_lock,
    write_memory_cache,
)
from market_config import (
    GLOBAL_MARKET_CACHE_SECONDS,
    INTERNATIONAL_INDEX_SPECS,
    NASDAQ_API_BASE,
    NASDAQ_USER_AGENT,
    TAIFEX_FUTURES_DAILY_URL,
    TAIFEX_OPTIONS_CHAIN_CACHE_SECONDS,
    TAIFEX_OPTIONS_DAILY_URL,
    TPEX_OPENAPI_BASE,
    TWSE_BASE,
    TWSE_MARGIN_URL,
    TWSE_OPENAPI_BASE,
    USER_AGENT,
    YAHOO_CHART_BASE,
    YAHOO_QUOTE_SUMMARY_BASE,
    YAHOO_SEARCH_BASE,
    YAHOO_TPEX_ETF_URL,
)
from security import _urlopen_with_ssl_fallback

TAIFEX_FORM_QUERY_CONCURRENCY = 2
TAIFEX_FUTURES_DAILY_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
TAIFEX_INSTITUTION_FUTURES_DETAIL_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
TAIFEX_INSTITUTION_OPTIONS_DETAIL_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfOptionsContractsBytheDate"
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

# TAIFEX's HTML query-form endpoints (DailyMarketReport / futures data download) are not a
# real API and are fragile under bursty concurrent traffic, so calls to them are throttled
# to a small bounded number in flight (with a short pacing sleep per call) instead of being
# fired without limit.
taifex_open_interest_lock = threading.Semaphore(2)

YAHOO_OPTIONS_CHAIN_BASE = "https://query1.finance.yahoo.com/v7/finance/options"
YAHOO_OPTIONS_CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
YAHOO_OPTIONS_PAGE_BASE = "https://finance.yahoo.com/quote"
YAHOO_OPTIONS_CRUMB_CACHE_SECONDS = 45 * 60
_yahoo_options_cookie_jar = CookieJar()
_yahoo_options_opener = build_opener(HTTPCookieProcessor(_yahoo_options_cookie_jar))

LOGGER = logging.getLogger("market_pulse")
try:
    TZ = ZoneInfo("Asia/Taipei")
except ZoneInfoNotFoundError:
    TZ = timezone(timedelta(hours=8))

EXTERNAL_TEXT_CACHE_SECONDS = 5 * 60

TWSE_COMPANY_INDUSTRY_CACHE_SECONDS = 12 * 60 * 60
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

SECTOR_CHART_TRADE_MONTHS = 3
SECTOR_CHART_TRADE_TIMEOUT_SECONDS = 4
STOCK_HISTORY_TIMEOUT_SECONDS = 8
STOCK_HISTORY_MAX_MONTHS = 480
STOCK_HISTORY_EMPTY_STOP_MONTHS = 24
STOCK_HISTORY_FETCH_BATCH_SIZE = 12

LIVE_SEARCH_DEDUP_SECONDS = 8.0

INSTITUTIONAL_HISTORY_RANGE_CONFIG = {
    "1m": {"limit": 24, "days": 45, "chart_range": "3mo", "stride": 1},
    "3m": {"limit": 66, "days": 120, "chart_range": "6mo", "stride": 1},
    "6m": {"limit": 90, "days": 220, "chart_range": "1y", "stride": 2},
    "1y": {"limit": 110, "days": 420, "chart_range": "2y", "stride": 4},
}


def taipei_now() -> datetime:
    return datetime.now(TZ)


def parse_float(value: str) -> float | None:
    cleaned = (value or "").replace(",", "").strip()
    if not cleaned or cleaned == "--":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_roc_date(value: str) -> datetime:
    year, month, day = [int(part) for part in value.split("/")]
    return datetime(year + 1911, month, day)


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


def dataset_has_rows(payload: dict[str, Any]) -> bool:
    if payload.get("stat") != "OK":
        return False

    if isinstance(payload.get("data"), list) and payload.get("data"):
        return True

    for table in payload.get("tables", []):
        if isinstance(table.get("data"), list) and table.get("data"):
            return True

    return False


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


def shift_month(date_str: str, months_back: int) -> str:
    base_date = datetime.strptime(date_str, "%Y%m%d")
    total_months = base_date.year * 12 + (base_date.month - 1) - months_back
    year, month_idx = divmod(total_months, 12)
    month = month_idx + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return datetime(year, month, day).strftime("%Y%m%d")


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


def pick_mapping_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


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


def normalize_market_request(value: str | None) -> str:
    market = str(value or "").strip().upper()
    if market in {"TPEX", "TWO", "OTC", "上櫃"}:
        return "TPEX"
    if market in {"TWSE", "TW", "LISTED", "上市"}:
        return "TWSE"
    return market


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


def build_tpex_openapi_url(endpoint: str) -> str:
    return f"{TPEX_OPENAPI_BASE}/{endpoint}"


def build_stock_institutions_url(date_str: str) -> str:
    params = {"date": date_str, "selectType": "ALLBUT0999", "response": "json"}
    return f"{TWSE_BASE}/rwd/zh/fund/T86?{urlencode(params)}"


def build_stock_day_url(date_str: str, stock_no: str) -> str:
    params = {"response": "json", "date": date_str, "stockNo": stock_no}
    return f"{TWSE_BASE}/exchangeReport/STOCK_DAY?{urlencode(params)}"


def build_market_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str, "type": "ALLBUT0999"}
    return f"{TWSE_BASE}/exchangeReport/MI_INDEX?{urlencode(params)}"


def build_index_activity_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str}
    return f"{TWSE_BASE}/exchangeReport/BFIAMU?{urlencode(params)}"


def build_index_intraday_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str}
    return f"{TWSE_BASE}/exchangeReport/MI_5MINS_INDEX?{urlencode(params)}"


def build_yahoo_chart_url(code: str, range_name: str, interval: str, market: str = "TPEx") -> str:
    params = urlencode({"range": range_name, "interval": interval, "includePrePost": "false"})
    suffix = "TWO" if market.upper() == "TPEX" else "TW"
    return f"{YAHOO_CHART_BASE}/{code}.{suffix}?{params}"


def detect_tone(value: float | None) -> str:
    if value is None or value == 0:
        return "flat"
    return "up" if value > 0 else "down"


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


def format_roc_date(value: datetime) -> str:
    return f"{value.year - 1911}/{value.month:02d}/{value.day:02d}"


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


def get_institutional_history_range_config(range_key: str) -> dict[str, int | str]:
    return INSTITUTIONAL_HISTORY_RANGE_CONFIG.get(
        str(range_key or "").strip().lower(),
        {"limit": 30, "days": 100, "chart_range": "6mo", "stride": 1},
    )


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


def parse_taifex_query_date(value: str | None = None) -> str:
    if not value:
        return datetime.now(TZ).strftime("%Y%m%d")
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        raise ValueError("INVALID_DATE")
    datetime.strptime(digits, "%Y%m%d")
    return digits


def build_taifex_futures_interval_candles(
    raw_candles: list[dict[str, Any]],
    interval: str,
) -> list[dict[str, Any]]:
    import app  # deferred: build_derivative_candles is a generic candle formatter, stays in app.py

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
    return app.build_derivative_candles({"series": series}, interval)


def should_cache_external_text(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host in {"www.taifex.com.tw", "tw.stock.yahoo.com", "home.treasury.gov", "fred.stlouisfed.org", "tradingeconomics.com"}


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


def fetch_tpex_mainboard_quotes(timeout: int = 10) -> tuple[list[dict[str, Any]], str | None]:
    payload = fetch_json(build_tpex_openapi_url("tpex_mainboard_quotes"), timeout=timeout)
    if not isinstance(payload, list):
        return [], None

    snapshot_date = parse_compact_roc_date(str(payload[0].get("Date"))) if payload else None
    return payload, snapshot_date


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


def fetch_stock_institutional_trade_for_date(
    stock: dict[str, Any],
    date_str: str,
) -> dict[str, Any]:
    import app  # deferred: build_stock_institutional_trade_record stays in app.py (builder layer)

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
    return app.build_stock_institutional_trade_record(row, date_str)


def fetch_stock_institutional_trade_history(
    stock: dict[str, Any],
    date_str: str,
    limit: int = 30,
    trading_dates: list[str] | None = None,
) -> dict[str, Any]:
    import app  # deferred: build_stock_institutional_trade_summary stays in app.py (builder layer)

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
        str(period): app.build_stock_institutional_trade_summary(rows[:period], period)
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


def fetch_live_stock_universe() -> tuple[list[dict[str, Any]], dict[str, Any], str, str | None]:
    import app  # deferred: parse_all_stocks/parse_tpex_quotes stay in app.py (builder layer)

    with ThreadPoolExecutor(max_workers=3) as executor:
        market_future = executor.submit(find_latest_dataset, build_market_url, 7)
        tpex_quotes_future = executor.submit(fetch_tpex_mainboard_quotes)
        yahoo_etfs_future = executor.submit(fetch_yahoo_tpex_etfs)

        market_payload, market_date = market_future.result()
        twse_stocks = app.parse_all_stocks(market_payload)

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

    tpex_stocks = app.parse_tpex_quotes(tpex_quotes, yahoo_etfs) if tpex_quotes else []
    return [*twse_stocks, *tpex_stocks], market_payload, market_date, tpex_quote_date


def fetch_live_stock_search_results(
    query: str,
    requested_market: str = "",
    limit: int = 20,
) -> tuple[list[dict[str, Any]], str, str | None, list[str]]:
    import app  # deferred: parse_all_stocks/parse_tpex_quotes/find_stock_by_query stay in app.py (builder layer)

    keyword = query.strip()
    if not keyword:
        return [], "", None, []

    recent = get_recent_live_search_result(keyword, requested_market, limit)
    if recent:
        return recent

    normalized_market = normalize_market_request(requested_market)
    market_payload, market_date = find_latest_dataset(build_market_url, 7)
    twse_stocks = app.parse_all_stocks(market_payload)
    twse_matches = app.find_stock_by_query(keyword, twse_stocks, limit=limit)
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
    tpex_stocks = app.parse_tpex_quotes(tpex_quotes, yahoo_etfs)
    if normalized_market == "TPEX":
        return remember_live_search_result(
            keyword,
            requested_market,
            limit,
            (app.find_stock_by_query(keyword, tpex_stocks, limit=limit), market_date, tpex_quote_date, ["TPEx"]),
        )

    matches = app.find_stock_by_query(keyword, [*twse_stocks, *tpex_stocks], limit=limit)
    return remember_live_search_result(
        keyword,
        requested_market,
        limit,
        (matches, market_date, tpex_quote_date, ["TWSE", "TPEx"]),
    )


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


def fetch_yahoo_options_payload(clean_symbol: str, expiration: str | None = None, retry: bool = True) -> dict[str, Any]:
    import app  # deferred: parse_cboe_expiration_request is CBOE-domain, stays in app.py (slice 3 batch 5)

    crumb = get_yahoo_options_crumb(clean_symbol)
    params = {"crumb": crumb}
    requested_expiration = app.parse_cboe_expiration_request(expiration)
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


def fetch_taiwan_option_spot_snapshot(underlying: str | None = None) -> dict[str, Any]:
    import app  # deferred: get_taiwan_option_product is TAIFEX-domain config, stays in app.py

    product = app.get_taiwan_option_product(underlying)
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


def fetch_taifex_futures_technical_candles(
    symbol: str,
    code: str = "",
    interval: str = "day",
) -> dict[str, Any]:
    import app  # deferred: Yahoo-Taiwan-technical-analysis domain helpers stay in app.py until batch 4

    clean_symbol = str(symbol or "").strip().upper()
    clean_interval = str(interval or "day").strip().lower()
    if clean_interval not in {"day", "week", "month", "all"}:
        clean_interval = "day"
    selected_contract = app.find_yahoo_taiwan_future_technical_contract(clean_symbol, code)
    if not selected_contract:
        return {"error": "找不到對應的 Yahoo 技術契約。"}
    selected_code = str(selected_contract.get("code") or "").strip().upper()
    inferred_symbol = app.infer_yahoo_taiwan_future_symbol_from_code(selected_code)
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
        "technicalAnalysisUrl": selected_contract.get("url") or app.build_yahoo_taiwan_future_technical_url(selected_code),
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


def fetch_taifex_txo_option_chain(
    expiry: str | None = None,
    market_date: str | None = None,
    underlying: str | None = "TXO",
) -> dict[str, Any]:
    import app  # deferred: option-chain response builders + TAIFEX product config stay in app.py

    product = app.get_taiwan_option_product(underlying)
    query_date = parse_taifex_query_date(market_date)
    cache_key = f"{product['symbol']}:{query_date}:{expiry or ''}"
    now = time.time()
    with cache_lock:
        cached = cache_data["taifex_options_chain"].get(cache_key)
    if cached and now - cached.get("stored_at", 0) < TAIFEX_OPTIONS_CHAIN_CACHE_SECONDS:
        return {**app.supplement_taifex_option_payload_with_yahoo_oi(cached["payload"]), "cached": True}

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
            return {**app.supplement_taifex_option_payload_with_yahoo_oi(cached["payload"]), "cached": True}
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
                rows = app.parse_taifex_txo_option_rows(html, spot_snapshot.get("value"), product["symbol"])
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("TAIFEX %s option chain fetch failed for date=%s", product["symbol"], date_text, exc_info=exc)
                rows = []
            if not rows:
                continue
            payload = app.supplement_taifex_option_payload_with_yahoo_oi(
                app.build_taifex_txo_option_payload(rows, target.strftime("%Y-%m-%d"), expiry, product["symbol"], spot_snapshot)
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
            "error": app.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE,
            "source": {"primary": "TAIFEX 選擇權每日交易行情查詢", "primaryUrl": TAIFEX_OPTIONS_DAILY_URL, "mode": "taifex"},
            "availableProducts": [
                {"symbol": key, "name": item["name"], "shortName": item["shortName"]}
                for key, item in app.TAIWAN_OPTION_PRODUCTS.items()
            ],
        }
    finally:
        if is_leader:
            with taifex_options_chain_inflight_lock:
                taifex_options_chain_inflight.pop(cache_key, None)
            leader_event.set()


def fetch_taifex_openapi_list(url: str, cache_seconds: int, timeout: int = 20) -> list[dict[str, Any]]:
    cached = read_memory_cache("taifex_openapi_list", url, cache_seconds)
    if cached is not None:
        return cached
    rows = fetch_json(url, timeout=timeout)
    if not isinstance(rows, list):
        rows = []
    write_memory_cache("taifex_openapi_list", url, rows)
    return rows


def fetch_taifex_institution_detail_rows(product: str) -> list[dict[str, Any]]:
    contract_name = PRODUCT_TO_TAIFEX_INSTITUTION_CONTRACT.get(product)
    if not contract_name:
        return []
    is_option = product in {"TXO", "STO", "ETO"}
    url = TAIFEX_INSTITUTION_OPTIONS_DETAIL_OPENAPI_URL if is_option else TAIFEX_INSTITUTION_FUTURES_DETAIL_OPENAPI_URL
    rows = fetch_taifex_openapi_list(url, TAIFEX_INSTITUTION_DETAIL_CACHE_SECONDS)
    return [row for row in rows if str(row.get("ContractCode") or "").strip() == contract_name]
