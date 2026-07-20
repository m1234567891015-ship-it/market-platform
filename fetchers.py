"""Generic HTTP fetch helpers extracted from app.py (TD-01 slice 3, batch 0),
extended with the TWSE/TPEX fetch_* functions and their supporting pure
utilities (batch 1).

TD-01 slice 5 batch A0 note: every `app.X` deferred-import call site described
below for `get_taiwan_option_product`, `TAIWAN_OPTION_PRODUCTS`,
`normalize_taiwan_option_source`, `YAHOO_TW_FUTURE_UNCOVERED_URL`,
`YAHOO_TW_OPTION_URL`, and `YAHOO_TW_FUTURE_CODE_TO_SYMBOL`/
`YAHOO_TW_FUTURE_TECHNICAL_GROUPS` (the latter two reached transitively via
`app.parse_yahoo_taiwan_future_quotes`) now resolve through a `parsers.py`
module rather than app.py-local definitions - but the call sites themselves
are **unchanged** (still `import app; app.X(...)`), and deliberately so: this
module must not import `parsers.py` directly, because `parsers.py` itself
needs a `from fetchers import TAIFEX_FUTURES_DATA_DOWNLOAD_URL` at module
level, and a `fetchers.py -> parsers.py -> fetchers.py` cycle would break at
import time. app.py re-imports these names from `parsers.py` the same way it
re-imports STAYS names from `builders.py`, so `app.get_taiwan_option_product`
etc. keep resolving exactly as before - just with one more hop behind the
scenes. See `parsers.py`'s own docstring and `builders.py`'s TD-01 slice 5
batch A0 note for the full picture (builders.py's equivalent call sites *were*
simplified to direct imports, since `builders.py -> parsers.py` is a safe
one-directional edge with no such cycle).

TD-01 slice 5 batch A1 note: the same "call site unchanged, destination moved"
treatment now also applies to `app.parse_taifex_txo_option_rows`
(`fetch_taifex_txo_option_chain`, line ~3496) and
`app.parse_yahoo_taiwan_future_quotes` (`fetch_yahoo_taiwan_future_quotes`,
line ~3559) - both functions themselves moved from app.py to `parsers.py` in
batch A1, for the identical one-directional-dependency reason above.

TD-01 slice 5 batch B4 regression fix: batch 2's and batch 3's notes below
(describing `app.parse_cboe_expiration_request` and
`app.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE`) were accurate when written in
slice 3, but became **stale and silently broken** in TD-01 slice 4 (batches 2
and 4), when both names moved from app.py to `builders.py` without either
deferred-import call site being updated - a real regression (the original
app.py-resident references were valid; the slice-4 move is what broke them),
caught by a full-repo audit during slice 5's closing batch. Both call sites
(`fetch_yahoo_options_payload`, `fetch_taifex_txo_option_chain`) now use a
separate deferred `import builders` targeting `builders.parse_cboe_expiration_request`
/ `builders.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE` directly, alongside the
existing `import app` where a function still needs both (`fetch_taifex_txo_option_chain`
still reaches `app.get_taiwan_option_product`/`app.supplement_taifex_option_payload_with_yahoo_oi`/
`app.parse_taifex_txo_option_rows`/`app.build_taifex_txo_option_payload`/
`app.TAIWAN_OPTION_PRODUCTS` for names that either stayed in app.py or are
re-exported through it). A full-repo scan (all `app.X`/`builders.X`/
`fetchers.X`/`parsers.X`/`cache.X`/`security.X`/`market_config.X`/
`derivatives_store.X` deferred-import references checked against each target
module's actual namespace) confirmed these were the only 2 broken references
anywhere in the repo - see `test_derivatives_platform.py`'s
`test_fetch_yahoo_options_payload_reaches_cboe_expiration_parser` and
`test_fetch_taifex_txo_option_chain_uses_public_error_message_on_empty_result`
for the regression-guard tests added alongside this fix. The batch 2/3 prose
below is left as originally written for historical accuracy about the
reasoning *at the time*; it no longer describes where these two names
currently live.

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

Batch 4 (Yahoo Taiwan, `tw.stock.yahoo.com`, 15 functions) brings the Yahoo
option-chain, sector-catalog, class-quote-page, and margin/broker/holder
HTML-scraping fetchers, plus their exclusive parsing-helper clusters
(`build_yahoo_quote_symbol`/`build_yahoo_quote_page_url`/
`build_yahoo_tw_stock_resource_url`, the `YahooClassCatalogParser` HTML
parser, and the whole `normalize_yahoo_date_text` ... `parse_yahoo_broker_rows_from_lines`
margin/broker parsing cluster - including `parse_yahoo_broker_row`, which a
whole-file grep found has zero callers anywhere, dead code carried over
verbatim since a behavior-preserving move doesn't delete things). Two more
shared pure helpers used by both this batch and staying HTML/JSON scrapers
(`extract_visible_text_lines`/`VisibleTextExtractor`, `extract_balanced_segment`)
move and get imported back into app.py, same pattern as batch 1/2's shared
utilities. `fetch_yahoo_tw_stock_resource` is this batch's bare-`_urlopen_with_ssl_fallback`
exception (builds its own `Request`, bypasses `fetch_json`/`fetch_text`).

Several functions in this batch reach into option-chain/class-quote/future-quote
domain code that stays in app.py via a deferred `import app`, same pattern as
batches 2-3:
- `fetch_yahoo_taiwan_future_quotes` calls `app.parse_yahoo_taiwan_future_quotes`
  and reads `app.YAHOO_TW_FUTURE_UNCOVERED_URL` - a large future-quote-page
  parser keyed off `YAHOO_TW_FUTURE_CODE_TO_SYMBOL`, a config dict shared with
  other staying future-technical-analysis code (batch 3's docstring already
  flagged this cluster).
- `fetch_yahoo_txo_option_chain` calls `app.get_taiwan_option_product`,
  `app.build_yahoo_taiwan_option_url`, `app.parse_yahoo_txo_option_page` (itself
  backed by a dozen further staying option-payload helpers), and reads
  `app.YAHOO_TW_OPTION_URL`/`app.TAIWAN_OPTION_PRODUCTS`.
- `fetch_taiwan_option_chain` calls `app.get_taiwan_option_product` and
  `app.normalize_taiwan_option_source` (both already-established TAIFEX-domain
  config lookups); it calls `fetch_taifex_txo_option_chain` and
  `fetch_yahoo_txo_option_chain` as bare names since both now live in this
  same module.
- `fetch_yahoo_class_quote_pages` calls `app.parse_yahoo_quote_items`, a
  class-quote JSON/HTML parser shared with a staying builder
  (`build_yahoo_class_quote_cards`, which also calls this batch's
  `fetch_yahoo_class_quote_pages` back via app.py's re-import).

Batch 5 (everything else, 20 functions - the last batch) brings TDCC, Google
News, US Treasury, FRED, Trading Economics, NASDAQ, NYSE, Barchart, and the
cross-source composite dispatchers (`fetch_market_macro_factors`,
`fetch_us_listed_universe_with_fallback`, `fetch_us_etf_directory_items`).
Unlike batches 2-4, none of this batch's shared dependencies are app.py
"builder" domain code - they're all generic, pure parsing/formatting helpers
(`is_etf_stock`, `build_stock_news_fallback`, `collect_futures_until_deadline`,
`parse_fred_date`, `normalize_us_symbol_for_yahoo`, `filter_us_etf_items`,
`barchart_options_headers`, `parse_public_options_number` - the last one is a
30+-call-site sibling of `parse_float`), so they all move here and get
imported back into app.py, with zero deferred `import app` calls needed
anywhere in this batch. Exclusive helpers moving alongside their sole callers:
`build_yahoo_macro_snapshot`, `parse_tdcc_holding_distributions`,
`extract_meta_description`, `parse_english_market_date`, the
`nasdaq_data`/`nasdaq_status_ok` pair, `parse_nasdaq_symbol_directory`,
`normalize_nyse_directory_item`, `parse_barchart_expiration_date`.
`fetch_barchart_options_context` is this batch's cookie-jar-opener exception
(builds a fresh `CookieJar`/opener per call, hands the live opener back to
`build_barchart_futures_options_chain` in app.py for a follow-up authenticated
request - a stateful return-value hand-off, not shared module state, so
moving the fetch function is safe).

This batch also resolves the last `fetch_*` gap `cache.py`'s module docstring
flagged: `build_site_data`/`refresh_tpex_cache` now resolve every direct
`fetch_*` call through `fetchers.py` imports (`fetch_market_macro_factors` was
the only holdout).
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
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit
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
    save_disk_cache,
    taifex_options_chain_inflight,
    taifex_options_chain_inflight_lock,
    write_memory_cache,
)
from fetch_registry import SourceSpec, fetch_from_registry, register
from market_config import (
    FRED_GRAPH_CSV_BASE,
    GLOBAL_MARKET_CACHE_SECONDS,
    GOOGLE_NEWS_RSS_BASE,
    INTERNATIONAL_INDEX_SPECS,
    NASDAQ_API_BASE,
    NASDAQ_LISTED_URL,
    NASDAQ_OTHER_LISTED_URL,
    NASDAQ_USER_AGENT,
    NYSE_QUOTES_FILTER_URL,
    TAIFEX_FUTURES_DAILY_URL,
    TAIFEX_OPTIONS_CHAIN_CACHE_SECONDS,
    TAIFEX_OPTIONS_DAILY_URL,
    TDCC_HOLDING_CACHE_SECONDS,
    TDCC_HOLDING_DISTRIBUTION_FALLBACK_URL,
    TDCC_HOLDING_DISTRIBUTION_URL,
    TPEX_OPENAPI_BASE,
    TRADING_ECONOMICS_TAIWAN_10Y_URL,
    TWSE_BASE,
    TWSE_MARGIN_URL,
    TWSE_OPENAPI_BASE,
    US_LISTED_UNIVERSE_CACHE_SECONDS,
    US_MARKET_SEARCH_UNIVERSE,
    US_TREASURY_YIELD_CURVE_CSV_URL,
    USER_AGENT,
    YAHOO_CHART_BASE,
    YAHOO_CLASS_HOME_URL,
    YAHOO_QUOTE_SUMMARY_BASE,
    YAHOO_SEARCH_BASE,
    YAHOO_TPEX_ETF_URL,
)
from security import _urlopen_with_ssl_fallback

TREASURY_YIELD_CURVE_CACHE_SECONDS = 6 * 60 * 60
BARCHART_FUTURES_OPTIONS_PAGE_BASE = "https://www.barchart.com/futures/quotes"

YAHOO_TW_FUTURE_CACHE_SECONDS = 60
YAHOO_TW_OPTION_CACHE_SECONDS = 60
YAHOO_TW_STOCK_RESOURCE_CACHE_SECONDS = 5 * 60

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


class VisibleTextExtractor(HTMLParser):
    BLOCK_TAGS = {
        "article", "aside", "div", "footer", "header", "li", "main", "nav", "p",
        "section", "table", "tbody", "td", "th", "tr", "ul", "ol",
        "h1", "h2", "h3", "h4", "h5", "h6", "a", "button", "span", "strong",
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


def is_etf_stock(stock: dict[str, Any]) -> bool:
    security_type = str(stock.get("securityType") or "").upper()
    code = str(stock.get("code") or "")
    name = str(stock.get("name") or "").upper()
    return security_type == "ETF" or code.startswith("00") or "ETF" in name


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


def parse_fred_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
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


def parse_english_market_date(value: str) -> datetime | None:
    text = str(value or "").strip()
    for date_format in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    return None


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


def parse_tdcc_holding_distributions(text: str) -> dict[str, dict[str, Any]]:
    distributions: dict[str, dict[str, Any]] = {}
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
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


register(SourceSpec(
    name="yahoo_tpex_etf_page",
    url=YAHOO_TPEX_ETF_URL,
    response_type="text",
    decode="sniff_cp950_big5",
    decode_errors="ignore",
    cache_bucket="external_text",
    cache_key=lambda: f"GET:{YAHOO_TPEX_ETF_URL}",
    ttl_seconds=EXTERNAL_TEXT_CACHE_SECONDS,
))


def fetch_yahoo_tpex_etfs(timeout: int = 8) -> dict[str, str]:
    page = fetch_from_registry("yahoo_tpex_etf_page", timeout=timeout)
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


register(SourceSpec(name="tpex_mainboard_quotes", url=build_tpex_openapi_url("tpex_mainboard_quotes")))


def fetch_tpex_mainboard_quotes(timeout: int = 10) -> tuple[list[dict[str, Any]], str | None]:
    payload = fetch_from_registry("tpex_mainboard_quotes", timeout=timeout)
    if not isinstance(payload, list):
        return [], None

    snapshot_date = parse_compact_roc_date(str(payload[0].get("Date"))) if payload else None
    return payload, snapshot_date


register(SourceSpec(name="twse_margin_summary", url=TWSE_MARGIN_URL, timeout=15))


def fetch_twse_margin_summary() -> dict[str, Any] | None:
    rows = fetch_from_registry("twse_margin_summary")
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


register(SourceSpec(name="stock_margin_trading_tpex", url=build_tpex_openapi_url("tpex_mainboard_margin_balance"), timeout=15))
register(SourceSpec(name="stock_margin_trading_twse", url=TWSE_MARGIN_URL, timeout=15))


def fetch_stock_margin_trading(stock: dict[str, Any]) -> dict[str, Any] | None:
    code = str(stock.get("code") or "").strip()
    market = str(stock.get("market") or "TWSE").upper()
    if not code:
        return None
    if market == "TPEX":
        rows = fetch_from_registry("stock_margin_trading_tpex")
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
        rows = fetch_from_registry("stock_margin_trading_twse")
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


register(SourceSpec(name="twse_listed_industry_rows", url=f"{TWSE_OPENAPI_BASE}/opendata/t187ap03_L"))


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
        rows = fetch_from_registry("twse_listed_industry_rows", timeout=timeout)
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


register(SourceSpec(name="stock_institutions_payload", url=build_stock_institutions_url))


def fetch_stock_institutions_payload_near(date_str: str, lookback_days: int = 7) -> tuple[dict[str, Any], str]:
    try:
        base_date = datetime.strptime(str(date_str), "%Y%m%d").date()
    except ValueError:
        base_date = taipei_now().date()

    for offset in range(lookback_days + 1):
        target = (base_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            payload = fetch_from_registry("stock_institutions_payload", target, timeout=15)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            LOGGER.warning("TWSE T86 sector fund flow fetch failed for date=%s: %s", target, exc)
            continue
        if dataset_has_rows(payload):
            return payload, target
    return {}, date_str


register(SourceSpec(name="stock_valuation_tpex", url=build_tpex_openapi_url("tpex_mainboard_peratio_analysis"), timeout=10))
register(SourceSpec(name="stock_valuation_twse", url=f"{TWSE_OPENAPI_BASE}/exchangeReport/BWIBBU_ALL", timeout=10))


def fetch_stock_valuation(stock: dict[str, Any]) -> dict[str, Any]:
    market = str(stock.get("market") or "TWSE").upper()
    if market == "TPEX":
        rows = fetch_from_registry("stock_valuation_tpex")
        code_key = "SecuritiesCompanyCode"
        field_map = {
            "date": "Date",
            "peRatio": "PriceEarningRatio",
            "dividendYield": "YieldRatio",
            "pbRatio": "PriceBookRatio",
            "dividendPerShare": "DividendPerShare",
        }
    else:
        rows = fetch_from_registry("stock_valuation_twse")
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


register(SourceSpec(
    name="stock_valuation_on_date_tpex",
    url=lambda date_value: (
        "https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate?"
        + urlencode({"date": date_value, "id": "", "response": "json"})
    ),
    timeout=15,
))
register(SourceSpec(
    name="stock_valuation_on_date_twse",
    url=lambda date_str: (
        f"{TWSE_BASE}/rwd/zh/afterTrading/BWIBBU_d?"
        + urlencode({"date": date_str, "selectType": "ALL", "response": "json"})
    ),
    timeout=15,
))


def fetch_stock_valuation_on_date(stock: dict[str, Any], date_str: str) -> dict[str, Any]:
    market = str(stock.get("market") or "TWSE").upper()
    code = str(stock["code"])
    if market == "TPEX":
        date_value = datetime.strptime(date_str, "%Y%m%d").strftime("%Y/%m/%d")
        payload = fetch_from_registry("stock_valuation_on_date_tpex", date_value)
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

    payload = fetch_from_registry("stock_valuation_on_date_twse", date_str)
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


register(SourceSpec(name="stock_company_profile_tpex", url=build_tpex_openapi_url("mopsfin_t187ap03_O"), timeout=10))
register(SourceSpec(name="stock_company_profile_twse", url=f"{TWSE_OPENAPI_BASE}/opendata/t187ap03_L", timeout=10))


def fetch_stock_company_profile(stock: dict[str, Any]) -> dict[str, Any]:
    market = str(stock.get("market") or "TWSE").upper()
    code = str(stock["code"])
    if market == "TPEX":
        rows = fetch_from_registry("stock_company_profile_tpex")
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

    rows = fetch_from_registry("stock_company_profile_twse")
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


register(SourceSpec(name="stock_institutional_trade_for_date", url=build_stock_institutions_url))


def fetch_stock_institutional_trade_for_date(
    stock: dict[str, Any],
    date_str: str,
) -> dict[str, Any]:
    import app  # deferred: build_stock_institutional_trade_record stays in app.py (builder layer)

    payload: dict[str, Any] = {}
    for attempt in range(3):
        try:
            payload = fetch_from_registry("stock_institutional_trade_for_date", date_str, timeout=10)
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


register(SourceSpec(name="stock_day_candles", url=build_stock_day_url))


def fetch_stock_history_rows(stock_no: str, date_str: str, months_back: int = STOCK_HISTORY_MAX_MONTHS) -> list[list[str]]:
    rows_by_date: dict[str, list[str]] = {}
    empty_months_after_data = 0

    def fetch_month(offset: int) -> list[list[str]]:
        target = shift_month(date_str, offset)
        try:
            payload = fetch_from_registry("stock_day_candles", target, stock_no, timeout=STOCK_HISTORY_TIMEOUT_SECONDS)
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
            payload = fetch_from_registry("stock_day_candles", target, stock_no, timeout=SECTOR_CHART_TRADE_TIMEOUT_SECONDS)
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


register(SourceSpec(name="live_index_activity", url=build_index_activity_url))
register(SourceSpec(name="live_index_intraday", url=build_index_intraday_url))


def fetch_live_index_activity(market_date: str) -> dict[str, Any] | None:
    try:
        payload = fetch_from_registry("live_index_activity", market_date, timeout=10)
    except Exception:  # noqa: BLE001
        LOGGER.exception("Live index activity fetch failed")
        return None
    return payload if dataset_has_rows(payload) else None


def fetch_live_index_intraday(market_date: str) -> dict[str, Any] | None:
    try:
        payload = fetch_from_registry("live_index_intraday", market_date, timeout=10)
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
    import builders  # deferred: parse_cboe_expiration_request moved to builders.py in TD-01 slice 4 (was app.py-resident when this comment was originally written in slice 3 batch 5) - deferred to avoid a load-time fetchers.py<->builders.py cycle, same reasoning as every `import app` deferred-import elsewhere in this file, just targeting builders.py directly since that's this name's actual home now

    crumb = get_yahoo_options_crumb(clean_symbol)
    params = {"crumb": crumb}
    requested_expiration = builders.parse_cboe_expiration_request(expiration)
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
    import builders  # deferred: PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE moved to builders.py in TD-01 slice 4 - separate deferred import from `app` above since this one name's home diverged from the rest of this function's app.X references

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
            "error": builders.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE,
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


def fetch_yahoo_taiwan_future_quotes(timeout: int = 10) -> dict[str, dict[str, Any]]:
    import app  # deferred: parse_yahoo_taiwan_future_quotes is future-technical domain, stays in app.py

    now = time.time()
    with cache_lock:
        cached = cache_data.get("yahoo_tw_future_quotes") or {}
        cached_items = cached.get("items") if isinstance(cached, dict) else None
        if cached_items and now - float(cached.get("stored_at") or 0) < YAHOO_TW_FUTURE_CACHE_SECONDS:
            return copy.deepcopy(cached_items)
    html = fetch_text(app.YAHOO_TW_FUTURE_UNCOVERED_URL, timeout=timeout)
    quotes = app.parse_yahoo_taiwan_future_quotes(html)
    with cache_lock:
        cache_data["yahoo_tw_future_quotes"] = {"stored_at": now, "items": copy.deepcopy(quotes)}
    return quotes


def fetch_yahoo_taiwan_future_quote(symbol: str, timeout: int = 10) -> dict[str, Any] | None:
    clean_symbol = str(symbol or "").strip().upper()
    if not clean_symbol:
        return None
    return fetch_yahoo_taiwan_future_quotes(timeout=timeout).get(clean_symbol)


def fetch_yahoo_txo_option_chain(expiry: str | None = None, underlying: str | None = "TXO") -> dict[str, Any]:
    import app  # deferred: option-chain product config + HTML payload parser stay in app.py

    product = app.get_taiwan_option_product(underlying)
    if not product.get("yahooOpcm"):
        return {
            "underlying": product["symbol"],
            "name": product["name"],
            "shortName": product["shortName"],
            "market": "台灣",
            "exchange": "Yahoo 股市",
            "error": f"{product['shortName']} 沒有 Yahoo 台灣選擇權逐履約價商品代碼，未使用 WTXO 代替。",
            "source": {"primary": "Yahoo 股市台灣選擇權報價", "primaryUrl": app.YAHOO_TW_OPTION_URL, "mode": "yahoo"},
            "availableProducts": [
                {"symbol": key, "name": item["name"], "shortName": item["shortName"]}
                for key, item in app.TAIWAN_OPTION_PRODUCTS.items()
            ],
        }
    now = time.time()
    cache_key = f"{product['symbol']}:{expiry or ''}"
    with cache_lock:
        cached = cache_data["yahoo_tw_option_chain"].get(cache_key)
    if cached and now - cached.get("stored_at", 0) < YAHOO_TW_OPTION_CACHE_SECONDS:
        return {**cached["payload"], "cached": True}
    yahoo_url = app.build_yahoo_taiwan_option_url(product["symbol"], expiry)
    html = fetch_text(yahoo_url, timeout=12)
    payload = app.parse_yahoo_txo_option_page(html, product["symbol"], expiry)
    if not payload.get("error"):
        with cache_lock:
            cache_data["yahoo_tw_option_chain"][cache_key] = {"stored_at": now, "payload": payload}
    return {**payload, "cached": False}


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
    import app  # deferred: TAIFEX-domain product config/source-mode lookups stay in app.py

    product = app.get_taiwan_option_product(underlying)
    source_mode = app.normalize_taiwan_option_source(source)
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


def fetch_yahoo_sector_catalog(timeout: int = 8) -> dict[str, list[dict[str, str]]]:
    html = fetch_text(YAHOO_CLASS_HOME_URL, timeout=timeout)
    parser = YahooClassCatalogParser()
    parser.feed(html)
    parser.close()
    return parser.catalog


def fetch_yahoo_class_quote_pages(
    url: str,
    snapshot_date: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    import app  # deferred: parse_yahoo_quote_items is class-quote domain, stays in app.py

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
        for row in app.parse_yahoo_quote_items(payload.get("list", []), snapshot_date):
            code = str(row.get("code") or "").upper()
            if code and code not in seen_codes:
                seen_codes.add(code)
                rows.append(row)
                if len(rows) >= limit:
                    return rows
    return rows


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


def fetch_yahoo_margin_accumulation_rows(symbol: str, referer: str) -> list[dict[str, Any]]:
    payload = fetch_yahoo_tw_stock_resource(
        "StockServices.credits",
        {"accumulation": "true", "symbol": symbol},
        referer=referer,
        timeout=10,
    )
    return normalize_yahoo_margin_accumulation_rows(payload)


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
                "source": "Yahoo ?∪?憭扳蝐Ⅳ",
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
