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

Later batches move the remaining per-source fetchers (Yahoo global, TAIFEX,
Yahoo Taiwan, everything else). Three later-batch functions
(`fetch_yahoo_tw_stock_resource`, `fetch_yahoo_options_payload`,
`fetch_barchart_options_context`) intentionally do NOT go through this
module's helpers - they call `_urlopen_with_ssl_fallback` directly or use
their own cookie-jar opener - documented when they move.
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cache import cache_data, cache_lock, read_memory_cache, write_memory_cache
from market_config import (
    NASDAQ_API_BASE,
    NASDAQ_USER_AGENT,
    TPEX_OPENAPI_BASE,
    TWSE_BASE,
    TWSE_MARGIN_URL,
    TWSE_OPENAPI_BASE,
    USER_AGENT,
    YAHOO_TPEX_ETF_URL,
)
from security import _urlopen_with_ssl_fallback

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
