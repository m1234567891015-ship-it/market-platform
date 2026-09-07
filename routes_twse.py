"""TWSE/TPEX market routes extracted from app.py (TD-01 slice 5, Phase B,
batch B2) - the 3rd of 4 domain Blueprint modules. Holds 16 routes covering
live market/sector/stock data, Yahoo sector snapshots, TWSE ETFs, and
per-stock detail/shareholders/institutional-history, in two disjoint app.py
regions (originally 815-1104 and 1576-1994 - a ~470-line gap of derivatives/
futures/options routes, out of scope for this batch, sits between them, same
split pattern batch B1 found for the global-market/US-market routes).
Registered on the main `app` object via `app.register_blueprint(bp)` - see
`routes_system.py`'s docstring (batch B0) for the endpoint-naming/
security-hook safety analysis that applies identically here.

`format_market_date` (EXCLUSIVE to `api_live_stocks`/`api_live_stock_search`,
both in this batch) and the ETF-classification cluster
(`TW_ETF_CATEGORY_DEFINITIONS`, `classify_tw_etf_category`,
`normalize_tw_etf_item`, `tw_etf_sort_key` - all EXCLUSIVE to `/api/twse/etfs`)
move with their callers, grep-confirmed zero callers elsewhere.
`SECTOR_CHART_CACHE_SECONDS` (EXCLUSIVE to `/api/yahoo/sector-chart`) moves
too, redefined locally rather than reached via import.

`apply_yahoo_quote` is explicitly NOT moved despite being physically
adjacent (immediately before `format_market_date`) and called from this
batch's `api_stock_detail` - it's SHARED (also reached by `parsers.py` via a
deferred `import app`, already documented in `parsers.py`'s own docstring as
a STAYS name), so `api_stock_detail` reaches it the same way, via deferred
`import app`. `global_market_refresh_requested`/`derivative_request_limit`
sit in the gap between this batch's two regions but belong to the
derivatives-domain routes still resident in app.py - not part of this batch.

`LOGGER`/`taipei_now`/`api_error_payload`/`api_exception_response`/
`PUBLIC_DATA_SOURCE_ERROR_MESSAGE` are app.py-local shared utilities reached
via a deferred `import app` inside each function that needs them, same
one-directional-dependency reason as every other route module this slice.
Everything else (`build_*`/`fetch_*`/parser names/cache primitives/
market_config constants) is safe to import directly at module level - none
of those modules import route modules back.

Test-patch fix: `test_twse_core_routes_use_cached_payloads` patched
`build_stock_detail` as `app.X`, but `api_stock_detail` now calls it as a
bare name resolved via this module's own import - repointed to
`@patch.object(routes_twse, "build_stock_detail", ...)`, same bare-name-
resolution lesson as every prior batch this slice.
"""
from __future__ import annotations

import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from builders import (
    STOCK_HISTORY_MAX_MONTHS,
    STOCK_HISTORY_RECENT_MONTHS,
    build_all_market_penny_sector_recommendations,
    build_institutional_history_from_yahoo,
    build_institutional_trade_candidate_dates,
    build_latest_stock_institutional_trade,
    build_live_market_overview_data,
    build_live_sector_site_data,
    build_stock_detail,
    build_stocks_view,
    build_yahoo_class_quote_cards,
)
from cache import (
    cache_data,
    cache_lock,
    claim_cache_flight,
    ensure_cache,
    finish_cache_flight,
    read_memory_cache,
    save_disk_cache,
    wait_for_cache_flight,
    write_memory_cache,
)
from fetchers import (
    build_yahoo_chart_series,
    detect_tone,
    fetch_international_market_indexes,
    fetch_live_stock_search_results,
    fetch_live_stock_universe,
    fetch_shareholder_distribution,
    fetch_stock_institutional_trade_history,
    fetch_yahoo_chart,
    fetch_yahoo_history_rows,
    fetch_yahoo_institutional_trading,
    fetch_yahoo_sector_catalog,
    fetch_yahoo_symbol_chart,
    fetch_yahoo_trading_dates_for_institutional_range,
    format_percent,
    format_signed,
    format_whole_number,
    get_institutional_history_range_config,
    is_etf_stock,
    normalize_market_request,
    parse_float,
)
from market_config import CACHE_TTL_SECONDS, INTERNATIONAL_INDEX_SPECS, YAHOO_TPEX_ETF_URL
from parsers import enrich_stocks_with_industry, find_stock_by_query, pick_exact_live_stock


bp = Blueprint("twse", __name__)


def ensure_cache_or_error(error_code: str):
    import app

    try:
        ensure_cache()
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response(error_code, app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
    return None


@bp.route("/api/twse/site-data")
def api_site_data():
    import app

    refresh = request.args.get("refresh", "").strip().lower() in {"1", "true", "yes", "on"}
    if refresh:
        try:
            return jsonify(build_live_sector_site_data())
        except Exception as exc:  # noqa: BLE001
            return app.api_exception_response("LIVE_SITE_DATA_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
    cache_error = ensure_cache_or_error("SITE_DATA_UNAVAILABLE")
    if cache_error is not None:
        return cache_error
    with cache_lock:
        return jsonify(cache_data["site_data"])


@bp.route("/api/twse/live-sectors")
def api_live_sectors():
    import app

    try:
        return jsonify(build_live_sector_site_data())
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("LIVE_SECTORS_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)


@bp.route("/api/twse/live-overview")
def api_live_overview():
    import app

    try:
        return jsonify(build_live_market_overview_data())
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("LIVE_OVERVIEW_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)


def format_market_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return date_str


@bp.route("/api/twse/live-stocks")
def api_live_stocks():
    import app

    try:
        stocks, _market_payload, market_date, tpex_quote_date = fetch_live_stock_universe()
        stocks = enrich_stocks_with_industry(stocks)
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("LIVE_STOCKS_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)

    return jsonify(
        {
            "snapshotDate": format_market_date(market_date),
            "tpexStockDate": format_market_date(tpex_quote_date),
            "refreshedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(stocks),
            "stocks": build_stocks_view(stocks, "search"),
            "source": "TWSE / TPEx 即時同步",
        }
    )


@bp.route("/api/twse/live-search")
def api_live_stock_search():
    import app

    query = request.args.get("q", "").strip()
    requested_market = request.args.get("market", "").strip()
    if not query:
        return jsonify(
            {
                "query": query,
                "snapshotDate": None,
                "tpexStockDate": None,
                "refreshedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
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
        return app.api_exception_response("LIVE_SEARCH_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)

    return jsonify(
        {
            "query": query,
            "snapshotDate": format_market_date(market_date),
            "tpexStockDate": format_market_date(tpex_quote_date),
            "refreshedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(matches),
            "results": build_stocks_view(matches, "search"),
            "source": " / ".join(sources) + " live search" if sources else "live search",
            "sources": sources,
        }
    )


@bp.route("/api/yahoo/sector")
def api_yahoo_sector():
    import app

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
        return app.api_exception_response("YAHOO_SECTOR_CATALOG_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)

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


SECTOR_CHART_CACHE_SECONDS = CACHE_TTL_SECONDS["sector_chart"]


@bp.route("/api/yahoo/sector-chart")
def api_yahoo_sector_chart():
    import app

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
    cached_chart = read_memory_cache("sector_charts", cache_key, SECTOR_CHART_CACHE_SECONDS)
    if cached_chart is not None:
        return jsonify(cached_chart)

    with ThreadPoolExecutor(max_workers=2) as executor:
        history_future = (
            executor.submit(fetch_yahoo_symbol_chart, yahoo_symbol, "2y", "1d")
            if yahoo_symbol
            else executor.submit(fetch_yahoo_chart, symbol, "2y", "1d", market)
        )
        benchmark_future = executor.submit(fetch_yahoo_symbol_chart, "^TWII", "2y", "1d")
        try:
            history_chart = history_future.result()
        except Exception as exc:  # noqa: BLE001
            app.LOGGER.debug(
                "Yahoo sector chart history fetch failed for symbol=%s market=%s; using empty history chart",
                symbol,
                market,
                exc_info=exc,
            )
            history_chart = None
        try:
            benchmark_chart = benchmark_future.result()
        except Exception as exc:  # noqa: BLE001
            app.LOGGER.debug(
                "Yahoo sector chart benchmark fetch failed for symbol=%s; using empty benchmark chart",
                symbol,
                exc_info=exc,
            )
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
    write_memory_cache("sector_charts", cache_key, payload, SECTOR_CHART_CACHE_SECONDS)
    return jsonify(payload)


@bp.route("/api/market/penny-sector-recommendations")
def api_market_penny_sector_recommendations():
    import app

    try:
        return jsonify(build_all_market_penny_sector_recommendations())
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("PENNY_SECTOR_RECOMMENDATIONS_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)


@bp.route("/api/market/international-indexes")
def api_market_international_indexes():
    cache_error = ensure_cache_or_error("MARKET_INDEX_CACHE_UNAVAILABLE")
    if cache_error is not None:
        return cache_error
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


@bp.route("/twse-data.js")
def twse_data_script():
    cache_error = ensure_cache_or_error("TWSE_DATA_SCRIPT_UNAVAILABLE")
    if cache_error is not None:
        return cache_error
    with cache_lock:
        site_payload = json.dumps(cache_data["site_data"], ensure_ascii=False)
        stocks_payload = json.dumps(cache_data["all_stocks"], ensure_ascii=False)
    script = (
        f"window.TWSE_DATA = {site_payload};\n"
        f"window.TWSE_ALL_STOCKS = {stocks_payload};\n"
    )
    return Response(script, mimetype="application/javascript")


@bp.route("/api/twse/all-stocks")
def api_all_stocks():
    cache_error = ensure_cache_or_error("ALL_STOCKS_UNAVAILABLE")
    if cache_error is not None:
        return cache_error
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


@bp.route("/api/twse/etfs")
def api_twse_etfs():
    cache_error = ensure_cache_or_error("TWSE_ETFS_UNAVAILABLE")
    if cache_error is not None:
        return cache_error
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


@bp.route("/api/twse/search")
def api_stock_search():
    import app

    cache_error = ensure_cache_or_error("STOCK_SEARCH_UNAVAILABLE")
    if cache_error is not None:
        return cache_error
    query = request.args.get("q", "").strip()
    with cache_lock:
        raw_stocks = cache_data.get("all_stocks")
        stocks = list(raw_stocks) if isinstance(raw_stocks, list) else []
        cached_at = cache_data["cached_at"]
        market_date = cache_data["market_date"]

    try:
        matches = find_stock_by_query(query, stocks)
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("STOCK_SEARCH_INVALID_DATA", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
    return jsonify(
        {
            "query": query,
            "snapshotDate": datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d") if market_date else None,
            "cachedAt": cached_at,
            "count": len(matches),
            "results": matches,
        }
    )


@bp.route("/api/twse/stock/<code>")
def api_stock_detail(code: str):
    import app

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
            return app.api_exception_response("LIVE_STOCK_DETAIL_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
        if stock is None:
            return jsonify({"error": "查無個股資料", "code": code_key}), 404
        if stock.get("market") == "TPEx" and not quick:
            stock = app.apply_yahoo_quote(stock)
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
        detail = {**detail, "cachedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S")}
        return jsonify(detail)

    cache_error = ensure_cache_or_error("STOCK_DETAIL_UNAVAILABLE")
    if cache_error is not None:
        return cache_error
    with cache_lock:
        stocks = list(cache_data["all_stocks"])
        market_date = cache_data["market_date"]
        cached_at = cache_data["cached_at"]
        site_data = cache_data["site_data"]

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
    detail = read_memory_cache("stock_details", cache_key, CACHE_TTL_SECONDS["stock_detail"])

    if detail is None:
        is_leader, flight = claim_cache_flight(f"stock-detail:{cache_key}")
        if not is_leader:
            wait_for_cache_flight(flight)
            detail = read_memory_cache("stock_details", cache_key, CACHE_TTL_SECONDS["stock_detail"])
            if detail is None:
                return jsonify(app.api_error_payload("CACHE_REFRESH_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE)), 503
        else:
            try:
                if stock.get("market") == "TPEx" and not quick:
                    stock = app.apply_yahoo_quote(stock)
                detail = build_stock_detail(
                    stock,
                    market_date,
                    site_data=site_data,
                    months_back=months_back,
                    quick=quick,
                    include_shareholders=not defer_slow,
                    include_institutional_history=not defer_slow,
                )
                write_memory_cache("stock_details", cache_key, detail, CACHE_TTL_SECONDS["stock_detail"])
            finally:
                finish_cache_flight(f"stock-detail:{cache_key}", flight)

    detail = {**detail, "cachedAt": cached_at}
    return jsonify(detail)


@bp.route("/api/twse/stock/<code>/shareholders")
def api_stock_shareholders(code: str):
    import app

    try:
        distribution = fetch_shareholder_distribution(str(code).strip())
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("LIVE_SHAREHOLDERS_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
    return jsonify(
        {
            "code": str(code).strip(),
            "shareholderDistribution": distribution,
            "cachedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


@bp.route("/api/twse/stock/<code>/institutional-history")
def api_stock_institutional_history(code: str):
    import app

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
        return app.api_exception_response("LIVE_INSTITUTIONAL_HISTORY_UNAVAILABLE", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc)
    if stock is None:
        return jsonify({"error": "查無個股資料", "code": code_key}), 404

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
                "cachedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    trading_dates: list[str] = []
    if range_key:
        try:
            trading_dates = fetch_yahoo_trading_dates_for_institutional_range(stock, range_key)
        except Exception:  # noqa: BLE001
            app.LOGGER.exception("Yahoo trading dates for institutional range failed for %s", code_key)
            trading_dates = []
    if not trading_dates:
        try:
            rows = fetch_yahoo_history_rows(stock["code"], STOCK_HISTORY_RECENT_MONTHS, market=stock.get("market") or "TWSE")
        except Exception as exc:  # noqa: BLE001
            app.LOGGER.debug(
                "Yahoo institutional history seed fetch failed for code=%s market_date=%s; using empty rows",
                code_key,
                market_date,
                exc_info=exc,
            )
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
            "cachedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
