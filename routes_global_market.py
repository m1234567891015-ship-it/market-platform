"""Global/international market routes extracted from app.py (TD-01 slice 5,
Phase B, batch B1) - the 2nd of 4 domain Blueprint modules. Holds the
global-market catalog route (`/api/global-market/<category>`, originally
app.py:1120-1181, a physically isolated island) plus the 7 `/api/us-market/*`
routes and their exclusive helpers (originally app.py:1646-1983, one
contiguous cluster). Registered on the main `app` object in app.py via
`app.register_blueprint(bp)` - see `routes_system.py`'s docstring (batch B0)
for the endpoint-naming/security-hook safety analysis that applies
identically here.

`search_us_market_universe`, `find_us_listed_symbol`,
`US_ETF_CENTER_CACHE_SECONDS`, `lock_public_option_chain_payload` are
EXCLUSIVE helpers (grep-confirmed zero callers outside this route cluster).
`search_us_listed_universe` is EXCLUSIVE too but has a direct test patch
(`test_us_market_search_route_merges_mocked_sources`) that needed repointing
from `@patch.object(app, ...)` to `@patch.object(routes_global_market, ...)`
in this batch's commit, along with 2 fetchers.py-name patches on the same
test (`fetch_yahoo_us_market_search`/`fetch_nyse_us_market_search`) - same
bare-name-resolution lesson as every prior batch this slice.
`unix_timestamp_from_iso_date` and `can_use_yahoo_options_fallback` are dead
code (zero callers anywhere in the repo, confirmed by exhaustive grep,
including inside their own neighboring routes) - moved as-is with
`# DEADCODE-CANDIDATE` markers per the standing rule rather than deleted.

Explicitly NOT moved despite sitting immediately adjacent to
`api_global_market`: `global_market_refresh_requested` (called 6x from
builders.py, already documented as STAYS in parsers.py's batch A2 notes) and
`derivative_request_limit` (called by 4 sibling derivatives routes still
resident in app.py, moving in a later batch). Neither is called by any of
this batch's 8 routes.

`GLOBAL_MARKET_CATEGORIES` is imported directly from `market_config.py` -
its in-place mutation (`extend_global_market_catalog`/
`insert_global_market_catalog_after`/`remove_global_market_symbols`) runs at
app.py module-load time, before this module's routes ever serve a request
(app.py imports this blueprint module near its own top, after those
mutations already ran), so the shared dict object is already in its final
state by the time any route here reads it.

`api_error_payload`/`PUBLIC_DATA_SOURCE_ERROR_MESSAGE`/`LOGGER` are
app.py-local shared utilities (dozens of other call sites across app.py)
reached via a deferred `import app` inside each function that needs them -
same one-directional-dependency reason as every other extraction in this
codebase (a module-level import would be a load-time circular import, since
app.py imports this blueprint module before those names are even defined).
`build_global_market_payload`/`build_us_etf_center_payload`/
`build_public_options_chain`/`build_us_market_symbol_detail`/
`build_global_market_item` (builders.py), the various `fetch_*`/
`normalize_us_*` names (fetchers.py), `normalize_taiwan_option_underlying`
(builders.py), `normalize_taiwan_option_source`/`TAIWAN_OPTION_DEFAULT_PRODUCT`
(parsers.py), and `cache_data`/`cache_lock`/`claim_cache_flight`/
`finish_cache_flight`/`CACHE_FLIGHT_WAIT_SECONDS` (cache.py) are all safe to
import directly at module level - none of those modules import route
modules back.
"""
from __future__ import annotations

import copy
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, request

from builders import (
    build_global_market_item,
    build_global_market_payload,
    build_public_options_chain,
    build_us_etf_center_payload,
    build_us_market_symbol_detail,
    normalize_futures_yahoo_uncovered_links,
    normalize_taiwan_option_underlying,
)
from cache import (
    CACHE_FLIGHT_WAIT_SECONDS,
    cache_data,
    cache_lock,
    claim_cache_flight,
    enforce_bucket_cap,
    finish_cache_flight,
)
from fetchers import (
    fetch_nasdaq_trader_us_listed_universe,
    fetch_nyse_directory_items,
    fetch_nyse_us_market_search,
    fetch_us_listed_universe_with_fallback,
    fetch_yahoo_us_market_search,
    normalize_us_market_search_item,
    normalize_us_symbol_for_yahoo,
    parse_float,
)
from market_config import (
    GLOBAL_MARKET_CACHE_SECONDS,
    GLOBAL_MARKET_CATEGORIES,
    GLOBAL_MARKET_DEFAULT_LOAD_LIMIT,
    GLOBAL_MARKET_MAX_LOAD_LIMIT,
    US_MARKET_SEARCH_UNIVERSE,
    US_SECTOR_STOCK_GROUPS,
)
from parsers import TAIWAN_OPTION_DEFAULT_PRODUCT, normalize_taiwan_option_source


bp = Blueprint("global_market", __name__)


@bp.route("/api/global-market/<category>")
def api_global_market(category: str):
    import app

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
        return jsonify(app.api_error_payload("CACHE_REFRESH_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE)), 503

    try:
        payload = build_global_market_payload(category_key, limit, option_source=option_source, option_underlying=option_underlying)
        with cache_lock:
            cache_data["global_markets"][cache_key] = {"stored_at": time.time(), "payload": payload}
            enforce_bucket_cap("global_markets")
        return jsonify({**payload, "cached": False})
    finally:
        finish_cache_flight(f"global-market:{cache_key}", flight)


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


@bp.route("/api/us-market/etf-center")
def api_us_market_etf_center():
    import app

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
        return jsonify(app.api_error_payload("CACHE_REFRESH_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE)), 503

    try:
        payload = build_us_etf_center_payload(query, directory_limit, quote_limit, refresh)
        with cache_lock:
            cache_data["us_etf_center"][cache_key] = {"stored_at": time.time(), "payload": payload}
            enforce_bucket_cap("us_etf_center")
        return jsonify({**payload, "cached": False})
    finally:
        finish_cache_flight(f"us-etf-center:{cache_key}", flight)


@bp.route("/api/us-market/search")
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


@bp.route("/api/us-market/listed")
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


@bp.route("/api/us-market/nyse-listed")
def api_us_market_nyse_listed():
    import app

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
        app.LOGGER.exception("NYSE listed directory fallback used", exc_info=exc)
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


def unix_timestamp_from_iso_date(date_text: str | None) -> int | None:  # DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
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


def can_use_yahoo_options_fallback(clean_symbol: str) -> bool:  # DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
    return bool(clean_symbol and not clean_symbol.startswith(("_", "^")) and "=F" not in clean_symbol and "=X" not in clean_symbol and not clean_symbol.endswith("-USD"))


@bp.route("/api/us-market/options-chain/<symbol>")
def api_us_market_options_chain(symbol: str):
    import app

    expiration = request.args.get("expiration")
    try:
        chain = build_public_options_chain(symbol, expiration)
    except Exception as exc:
        app.LOGGER.exception("US options chain load failed", exc_info=exc)
        chain = {
            "symbol": normalize_us_symbol_for_yahoo(symbol),
            "error": "選擇權資料暫時無法載入，請稍後再試",
            "source": "Cboe Delayed Quotes Options",
        }
    chain = lock_public_option_chain_payload(chain, symbol)
    status = 400 if chain.get("error") and not chain.get("symbol") else 200
    return jsonify(chain), status


@bp.route("/api/us-market/symbol/<symbol>")
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


@bp.route("/api/us-market/sector-stocks")
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
