"""US-market search vertical slice.

This module owns the search-specific orchestration boundary: local seed
matching, listed-universe matching, and the API payload assembled from the
independent listed-directory, NYSE, and Yahoo providers.  Provider fetchers
remain in ``fetchers.py`` for now; this slice keeps the route adapter thin and
gives the search contract one independently testable composition point.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fetchers import (
    fetch_nasdaq_trader_us_listed_universe,
    fetch_nyse_us_market_search,
    fetch_us_listed_universe_with_fallback,
    fetch_yahoo_us_market_search,
    normalize_us_market_search_item,
)
from market_config import US_MARKET_SEARCH_UNIVERSE


LOGGER = logging.getLogger("market_pulse")


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


def search_us_listed_universe(
    query: str, limit: int = 80
) -> tuple[list[dict[str, Any]], dict[str, int], str]:
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


def build_us_market_search_payload(query: str) -> dict[str, Any]:
    """Assemble the stable ``/api/us-market/search`` response payload."""
    query = query.strip()
    if not query:
        totals: dict[str, int] = {}
        source = "Nasdaq Trader 官方 Symbol Directory"
        try:
            _items, totals = fetch_nasdaq_trader_us_listed_universe(False)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Nasdaq Trader empty-query lookup failed", exc_info=exc)
            totals = {
                "美股個股": sum(1 for item in US_MARKET_SEARCH_UNIVERSE if item.get("group") == "美股個股"),
                "美股 ETF": sum(1 for item in US_MARKET_SEARCH_UNIVERSE if item.get("group") == "美股 ETF"),
            }
            source = "內建美股/ETF清單"
        return {
            "query": query,
            "count": 0,
            "totals": totals,
            "source": source,
            "results": [],
            "message": "請輸入代號或名稱後搜尋全上市美股 / ETF。",
        }

    def run_listed_search() -> tuple[list[dict[str, Any]], dict[str, int], str]:
        try:
            return search_us_listed_universe(query, 120)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Listed U.S. market search failed for query=%r", query, exc_info=exc)
            return [], {}, ""

    def run_nyse_search() -> tuple[list[dict[str, Any]], dict[str, int]]:
        try:
            return fetch_nyse_us_market_search(query, 60)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("NYSE U.S. market search failed for query=%r", query, exc_info=exc)
            return [], {}

    def run_yahoo_search() -> list[dict[str, Any]]:
        try:
            return fetch_yahoo_us_market_search(query, 20)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Yahoo U.S. market search failed for query=%r", query, exc_info=exc)
            return []

    # These sources are independent and are merged rather than tried until
    # success, so preserve the existing concurrent fetch behavior.
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
    return {
        "query": query,
        "count": len(results),
        "totals": totals,
        "source": " + ".join(dict.fromkeys(sources)) or "NYSE Listings Directory + Yahoo Finance 行情補充",
        "results": results,
    }
