"""Response/data-shaping `build_*` functions extracted from app.py (TD-01
slice 4, batch 0), starting with 7 small, dependency-free leaf builders.

These have zero dependency on any other `build_*` function, which is why they
move first: `build_stock_search_url`, `build_institutions_url`,
`build_weighted_index_history_url` are pure TWSE URL builders (`TWSE_BASE`
from `market_config` is a shared constant, imported here and still used
directly by app.py elsewhere - no conflict). `build_stocks_view`/
`build_site_data_view` are response-view slimmers for the `?view=` query
param, along with their exclusive helper (`slim_stock_for_bootstrap`) and
constants (`BOOTSTRAP_STOCK_KEYS`, `SECTOR_SITE_DATA_KEYS`,
`SEARCH_SITE_DATA_KEYS`) - a whole-file grep confirmed none of these three
names are referenced anywhere outside this cluster, so they move as a unit.

`build_yahoo_taiwan_future_technical_url` and `build_yahoo_taiwan_option_url`
are two of the six functions `fetchers.py` already reaches via a deferred
`import app` (`app.build_yahoo_taiwan_future_technical_url` at fetchers.py:3282,
`app.build_yahoo_taiwan_option_url` at fetchers.py:3577) - those call sites
need zero changes, since app.py re-imports both names from this module below,
so `app.build_X(...)` attribute lookups keep resolving exactly as before.
Internally, both call back into config/lookup helpers that stay in app.py
(`get_taiwan_option_product`, a TAIFEX-domain product-config lookup used by
~18 other route/builder call sites; the `YAHOO_TW_FUTURE_URL`/
`YAHOO_TW_OPTION_URL` constants, still used directly by other app.py builders
that aren't moving yet) via a deferred `import app`, same pattern fetchers.py
already established - required here too, since app.py imports this module
near the top of its own file (before those constants are even defined), so a
module-level `from app import ...` would be a load-time circular import.

Three functions found with zero callers anywhere in the repo (confirmed by
two independent full-repo searches) move here unmodified rather than being
deleted, per the standing behavior-preserving-refactor rule - each is marked
with a `# DEADCODE-CANDIDATE` comment for a future TD-05 registry cleanup:
`build_stock_search_url`, `build_site_data_view`, and (added in batch 1)
`build_yahoo_options_chain`.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from market_config import TWSE_BASE


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


# DEADCODE-CANDIDATE (confirmed zero callers 2026-07-18)
def build_stock_search_url(date_str: str, keyword: str) -> str:
    params = {"response": "json", "date": date_str, "keyword": keyword}
    return f"{TWSE_BASE}/rwd/zh/afterTrading/STOCK_DAY_AVG?{urlencode(params)}"


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


# DEADCODE-CANDIDATE (confirmed zero callers 2026-07-18)
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


def build_yahoo_taiwan_future_technical_url(code: str) -> str:
    import app

    clean_code = str(code or "").strip().upper()
    if not clean_code:
        return ""
    return f"{app.YAHOO_TW_FUTURE_URL}/{quote(clean_code, safe='')}/technical-analysis"


def build_yahoo_taiwan_option_url(underlying: str | None = None, expiry: str | None = None) -> str:
    import app

    product = app.get_taiwan_option_product(underlying)
    opcm = str(product.get("yahooOpcm") or "").strip()
    if not opcm:
        return app.YAHOO_TW_OPTION_URL
    params = {
        "opmr": "optionfull",
        "opcm": opcm,
    }
    expiry_text = str(expiry or "").strip()
    if expiry_text:
        params["opym"] = expiry_text
    return f"{app.YAHOO_TW_OPTION_URL}?{urlencode(params)}"


def build_institutions_url(date_str: str) -> str:
    params = {"response": "json", "dayDate": date_str, "type": "day"}
    return f"{TWSE_BASE}/fund/BFI82U?{urlencode(params)}"


def build_weighted_index_history_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str}
    return f"{TWSE_BASE}/indicesReport/MI_5MINS_HIST?{urlencode(params)}"
