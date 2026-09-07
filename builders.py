"""Response/data-shaping `build_*` functions extracted from app.py (TD-01
slice 4), starting with 7 small, dependency-free leaf builders (batch 0),
extended with the TAIFEX/options-chain + derivatives-misc cluster (batch 1,
19 functions), the Yahoo/sector + technical-analysis cluster (batch 2,
12 functions), the stock-detail / institutional cluster (batch 3,
15 functions), the US-market / global-market cluster (batch 4, 23 functions),
and the site-data composites (batch 5, FINAL - 3 functions). This completes
the full 79-function `build_*` extraction from app.py.

TD-01 slice 5 batch A0 follow-up: `get_taiwan_option_product`, `TAIWAN_OPTION_PRODUCTS`,
`TAIWAN_OPTION_DEFAULT_PRODUCT`, `YAHOO_TW_FUTURE_URL`, `YAHOO_TW_FUTURE_UNCOVERED_URL`,
`YAHOO_TW_OPTION_URL`, and `YAHOO_TW_FUTURE_TECHNICAL_GROUPS` - documented
throughout the batch notes below as deferred-`import app` STAYS names - have
now moved out of app.py into a new `parsers.py` module (app.py's own
never-modularized parsing/helper layer, finally given a home now that all
`build_*`/`fetch_*` extraction is complete). Every call site in this file
that reached them via `app.X` has been simplified to a direct bare name
(module-level `from parsers import (...)` added above), since
`builders.py -> parsers.py` is a safe one-directional import edge. The batch
notes below are left as originally written for historical accuracy about
*why* each name was classified STAYS at the time: that reasoning ("heavily
shared with still-resident app.py code") is exactly what made them
extraction candidates once the code sharing them all moved out too.
`normalize_taiwan_option_underlying` (this module) is the one exception still
reached by `parsers.py` via a deferred `import app` rather than a direct
import, to avoid a `parsers.py -> builders.py -> parsers.py` cycle - see
`parsers.py`'s own docstring for the full explanation.

Batch 5 brings the three top-level site-data composites -
`build_site_data`, `build_live_sector_site_data`, `build_live_market_overview_data` -
the last functions in this slice because they depend on nearly every builder
moved in batches 0-4. `build_site_data`'s only caller is `cache.py:281`
(inside `update_loop`'s deferred `import app` block), not a route - it
already called `app.build_site_data(...)` by attribute, which keeps
resolving once app.py re-imports the name from here, so `cache.py` needed no
changes. `build_live_sector_site_data`/`build_live_market_overview_data` are
each called by their own route (`api_live_sectors`, `api_live_overview`),
plus `api_site_data`'s `?refresh=1` path for the former.

`build_site_data` had zero test coverage, direct or indirect (its only
caller is a background cache-refresh path, not exercised by e2e_smoke.py) -
added `test_build_site_data_assembles_snapshot_from_sub_builders` before the
move, per the standing rule, mocking every sub-builder/fetcher it calls and
asserting on the assembled snapshot shape. `build_live_sector_site_data`
already had indirect route-level coverage (both routes are hit by
`e2e_smoke.py`), so no additional test was needed for it or its sibling.

Many STAYS names reached via deferred `import app` in this batch:
`LOGGER`, `taipei_now`, `DeadlineThreadPoolExecutor` (a small
`ThreadPoolExecutor` subclass with a non-blocking `__exit__`),
`market_payload_has_complete_index_tables`, `weighted_index_history_has_volume`,
`weighted_index_history_is_usable`, `upsert_latest_weighted_index_point`,
`parse_tpex_quotes`, `parse_all_stocks`, `enrich_yahoo_cards_with_market_stats`,
`parse_market_overview`, `parse_sectors`, `parse_institutions`,
`parse_market_statistics`, `merge_site_data_with_fallback` - all pure
parsing/merging helpers that stay in app.py since nothing else in this slice
needed to move them (no other `build_*` function depends on them, so they
were never flagged SHARED-PURE in any earlier batch).

Batch 4 brings `build_global_market_item` (the highest fan-in/fan-out node
in the whole slice - called by 4 other batch-4 builders, 9 routes, and both
`build_global_market_payload`/`build_us_etf_center_payload`) plus its
exclusive yield-curve/FRED/Trading-Economics/Taiwan-quote-fallback item
builders and their helper clusters, and the full `build_us_market_symbol_detail`
tree (US valuation/company-profile/margin-proxy/ownership-trading builders,
each with a Yahoo-quote-summary path and a Nasdaq-supplement merge path,
plus their `format_us_*`/`parse_us_*`/`nasdaq_*` helper clusters - all
verified EXCLUSIVE to this batch). Also `build_global_market_payload` and
`build_us_etf_center_payload`/`build_us_etf_quote_specs`.

Two module constants (`PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE`,
`PUBLIC_MARKET_ITEM_ERROR_MESSAGE`) moved from app.py alongside this batch:
both were single-use-by-fan-out but colocated in app.py with a third,
heavily-shared constant that stays. `build_txo_option_market_item` (moved in
batch 1) previously reached the first one via a deferred `import app` -
since both functions now live in the same module, that reference is
simplified to a plain bare name, eliminating a cross-module call that's no
longer necessary. `enrich_global_market_spec` (+ its exclusive
`infer_global_asset_metadata` helper) is SHARED-PURE - also called by
`find_derivative_spec`, a non-`build_*` app.py helper that stays - so it
moves and gets re-imported into app.py the same way. `global_market_refresh_requested`,
`get_taiwan_option_product`, `DERIVATIVES_STORE`, `LOGGER`, `TZ`, and
`taipei_now` stay in app.py (heavily shared with still-resident code,
including the final batch's 3 site-data composites) and are reached via
deferred `import app`, same pattern as every earlier batch.

Fixes 3 more pre-existing latent `NameError` call sites for the
`build_yahoo_chart_series` import bug documented in batch 2's docstring
(inside `build_global_market_item`, `build_us_market_symbol_detail`, and
`estimate_us_beta` - all now correctly resolve via this module's existing
`fetchers` import). Two more dead functions found and moved as-is with
`# DEADCODE-CANDIDATE` markers, per the standing rule: `format_us_ratio`,
`format_us_percent_value` (zero callers anywhere, confirmed by grep).

Batch 3 brings `build_stock_detail` (the largest single builder, ~300 lines)
and everything it calls: `build_fallback_company_profile`,
`build_latest_stock_institutional_trade`, `build_institutional_trade_candidate_dates`,
`build_etf_components` (+ its exclusive `ETF_COMPONENT_PRESETS` constant),
`build_fallback_history_rows`, `build_chip_summary` (+ `build_main_force_proxy`,
its exclusive `format_chip_lots`/`format_chip_percent` helpers),
`build_analysis_sections`. Also: `build_stock_institutional_trade_record` and
`build_stock_institutional_trade_summary` (2 of the 6 functions `fetchers.py`
reaches via deferred `import app` - both now re-exported from here so those
call sites need zero changes), `build_institutional_history_from_yahoo`,
`build_institution_summary`/`build_institution_trend` (called by
`build_site_data`/`build_live_sector_site_data`/`build_live_market_overview_data`,
all three still resident in app.py until batch 5 - re-imported into app.py so
those bare-name calls keep resolving), and `build_news` (same situation,
called by the same three not-yet-moved composites).

Two functions exclusive to `build_stock_detail` (`is_valid_history_row`,
`sanitize_history_rows`) have their own direct unit tests referencing them as
`app.X` (`test_stock_history_sanitizer_drops_invalid_ohlc_rows`,
`test_yahoo_history_rows_skip_incomplete_ohlc_points`) - re-exported from
app.py's import block so those tests keep passing unmodified. `STOCK_HISTORY_RECENT_MONTHS`/
`STOCK_HISTORY_MAX_MONTHS` are SHARED-PURE (also used directly by
`api_stock_detail` and by a test assertion) - same treatment. `taipei_now`
and `parse_institutions` stay in app.py (widely shared with still-resident
code) and are reached via deferred `import app`, same pattern as every
earlier batch. Added a characterization test for `build_news`
(`test_build_news_summarizes_market_sectors_and_institutions`) before the
move, per the standing rule - it previously had zero test coverage, direct
or indirect.

Batch 2 brings the Yahoo class-quote-card builder and its exclusive HTML/JSON
scraping cluster (`parse_yahoo_class_quote_rows`, `parse_yahoo_class_quote_json_list`,
`parse_yahoo_class_quote_embedded_list`, `parse_yahoo_class_quote_date`,
`yahoo_field_text`, `parse_yahoo_quote_items`) - `parse_yahoo_quote_items` is
one of the 6 functions `fetchers.py` already reaches via a deferred
`import app` (`fetch_yahoo_class_quote_pages` calls `app.parse_yahoo_quote_items`),
so it's re-exported from app.py's `from builders import (...)` block like
everything else that crosses this boundary. Also in this batch: the sector
group/summary-series builders, the intraday/index technical-analysis pair,
the sector fund-flow builder (with its exclusive `format_fund_flow_amount`
helper), the intraday-index-candle and sector-history builders (sharing
`find_table_by_field_candidates`/`resolve_sector_key`/`parse_index_close_values`/
`parse_index_activities` with `parse_sectors`, which stays in app.py), the
summary-cards-from-payload builder, and the all-market penny-sector
recommendation builder (with its exclusive 120-line refresh helper,
`_refresh_all_market_penny_sector_recommendations`).

Fixes a pre-existing bug in the moved `build_weighted_index_history_series`:
it called `build_yahoo_chart_series` without ever importing it (dead
`NameError` in app.py predating this slice) - now correctly imported from
`fetchers`. app.py's other 5 call sites of the same function (its own
`from fetchers import (...)` block never had it either) are untouched here -
out of scope for this batch, left exactly as broken as before for a future
cleanup pass.

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
two independent full-repo searches) moved here unmodified rather than being
deleted at the time, each marked with a `# DEADCODE-CANDIDATE` comment for
the eventual TD-05 registry cleanup: `build_stock_search_url`,
`build_site_data_view`, and (added in batch 1) `build_yahoo_options_chain`.
All 3 were reconfirmed zero-callers via a final repo-wide scan (including
app.js/HTML/test files, and a check for dynamic/reflective dispatch) and
deleted in TD-05 batch 12.

Batch 1 (TAIFEX/options-chain + derivatives misc, 19 functions) brings the
TAIFEX/Yahoo TXO option-chain builders, the TAIFEX global-market item
builders (open interest, option-market summary, product volume summary,
stock-derivative aggregate), the generic derivative-candle/futures-AI-analysis
pair, the live institution payload builder, and the five public
options-chain aggregators (CBOE, Barchart, Deribit, Bybit, plus the
dispatcher). Each brings its exclusive parsing/formatting helpers and
provider-specific config constants (verified by grep to have no callers
outside this batch) - too many to enumerate individually here; see inline
placement. Two functions (`build_taifex_txo_option_payload`,
`build_derivative_candles`) are 2 of the 6 functions `fetchers.py` already
reaches via a deferred `import app` - those call sites need zero changes,
same reasoning as batch 0. `build_institution_payload_live` is also
`@patch.object(app, "build_institution_payload_live", ...)`-mocked in
`test_derivatives_platform.py`, so it must stay re-exported from app.py's
top-level namespace, not just called internally.

Several moved functions call back into TAIFEX/option domain-config lookups
that stay in app.py (`get_taiwan_option_product`, `TAIWAN_OPTION_PRODUCTS`,
`YAHOO_TW_FUTURE_TECHNICAL_GROUPS`, `PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE`,
`YAHOO_TW_FUTURE_UNCOVERED_URL`, `global_market_refresh_requested`, `LOGGER`,
`TZ`) via the same deferred `import app` pattern used in batch 0 - each is
heavily shared with other still-resident app.py builder/route code (`build_global_market_item`,
`build_global_market_payload`, 3+ routes), so they don't move. Two pure
helpers (`summarize_taifex_option_rows`, `calculate_taifex_max_pain`,
`normalize_taiwan_option_underlying`) are also called from non-build app.py
code (`supplement_taifex_option_payload_with_yahoo_oi`, `get_taiwan_option_product`)
but are pure enough to move-and-reimport, same as batch 0's URL builders.
"""
from __future__ import annotations

import copy
import json
import logging
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request

from cache import (
    PENNY_SECTOR_RECOMMENDATION_CACHE_SECONDS,
    cache_data,
    cache_lock,
    claim_cache_flight,
    finish_cache_flight,
    penny_sector_recommendation_cache,
    penny_sector_recommendation_lock,
    read_memory_cache,
    sanitize_site_data,
    wait_for_cache_flight,
    write_memory_cache,
)
from derivatives.analytics import enrich_futures_ai_decision, enrich_option_ai_decision
from derivatives.catalog import TAIWAN_FUTURES_V1, TAIWAN_OPTIONS_V1, apply_taifex_defaults, v1_product_status
from derivatives.futures import build_source_pending_market_item, is_source_pending_product
from fetchers import (
    TAIFEX_FUTURES_DAILY_OPENAPI_URL,
    barchart_options_headers,
    build_index_activity_url,
    build_index_intraday_url,
    build_market_url,
    build_stock_institutions_url,
    build_stock_news_fallback,
    build_tpex_openapi_url,
    build_yahoo_chart_series,
    collect_futures_until_deadline,
    deadline_after,
    dataset_has_rows,
    detect_tone,
    extract_balanced_segment,
    extract_visible_text_lines,
    fetch_barchart_options_context,
    fetch_etf_dividend_info,
    fetch_fred_observation_rows,
    fetch_international_market_indexes,
    fetch_json,
    fetch_live_index_activity,
    fetch_live_index_intraday,
    fetch_market_macro_factors,
    fetch_market_volatility_indicator,
    fetch_nasdaq_us_supplement,
    fetch_shareholder_distribution,
    fetch_stock_company_profile,
    fetch_stock_history_rows,
    fetch_stock_institutions_payload_near,
    fetch_stock_institutional_trade_history,
    fetch_stock_margin_trading,
    fetch_stock_news,
    fetch_stock_valuation,
    fetch_stock_valuation_history,
    fetch_taifex_institution_detail_rows,
    fetch_taifex_latest_futures_market_snapshot,
    fetch_taifex_openapi_list,
    fetch_taiwan_option_spot_snapshot,
    fetch_text,
    fetch_tpex_mainboard_quotes,
    fetch_trading_economics_taiwan_10y,
    fetch_txo_option_chain,
    fetch_twse_listed_industry_map,
    fetch_us_etf_directory_items,
    fetch_us_market_overview_news,
    fetch_us_treasury_yield_curve,
    fetch_us_treasury_yield_curve_rows,
    fetch_yahoo_broker_trading,
    fetch_yahoo_class_quote_pages,
    fetch_yahoo_history_rows,
    fetch_yahoo_institutional_trading,
    fetch_yahoo_major_holders,
    fetch_yahoo_margin_trading,
    fetch_yahoo_options_payload,
    fetch_yahoo_quote_summary,
    fetch_yahoo_sector_catalog,
    fetch_yahoo_symbol_chart,
    fetch_yahoo_taiwan_future_quote,
    fetch_yahoo_tpex_etfs,
    fetch_yahoo_us_symbol_news,
    filter_us_etf_items,
    find_latest_dataset,
    format_percent,
    format_roc_date,
    format_signed,
    format_whole_number,
    is_etf_stock,
    is_valid_ohlc_values,
    normalize_taifex_date_text,
    normalize_us_market_search_item,
    normalize_us_symbol_for_yahoo,
    parse_float,
    parse_fred_date,
    parse_public_options_number,
    parse_roc_date,
    parse_taifex_market_number,
    FUTURES_BACKEND_BUDGET_SECONDS,
    OPTIONS_BACKEND_BUDGET_SECONDS,
    YAHOO_MAX_RETRY,
    remaining_budget,
    shift_month,
)
from parsers import (
    TAIWAN_OPTION_DEFAULT_PRODUCT,
    TAIWAN_OPTION_PRODUCTS,
    YAHOO_TW_FUTURE_TECHNICAL_GROUPS,
    YAHOO_TW_FUTURE_UNCOVERED_URL,
    YAHOO_TW_FUTURE_URL,
    YAHOO_TW_OPTION_URL,
    enrich_yahoo_cards_with_market_stats,
    find_table_by_field,
    get_taiwan_option_product,
    market_payload_has_complete_index_tables,
    merge_site_data_with_fallback,
    parse_all_stocks,
    parse_index_activities,
    parse_institutions,
    parse_market_overview,
    parse_market_statistics,
    parse_sectors,
    parse_tpex_quotes,
    upsert_latest_weighted_index_point,
    weighted_index_history_has_volume,
    weighted_index_history_is_usable,
)
from market_config import (
    ASSET_CATEGORY_SOURCE_INFO,
    ASSET_REGION_ORDER,
    CACHE_TTL_SECONDS,
    CBOE_OPTIONS_BASE,
    GLOBAL_MACRO_ASSET_SCHEMA,
    GLOBAL_MARKET_CATEGORIES,
    OPTIONS_CHAIN_CACHE_SECONDS,
    SECTOR_INDEX_LOOKUP,
    SUPPORTED_CHART_INTERVALS,
    TAIFEX_FUTURES_DAILY_URL,
    TAIFEX_OPTIONS_DAILY_URL,
    TAIFEX_OPTIONS_PC_RATIO_URL,
    TARGET_INDEX_NAMES,
    TDCC_HOLDING_DISTRIBUTION_URL,
    TWSE_BASE,
    TWSE_MARGIN_URL,
    TWSE_OPENAPI_BASE,
    US_MARKET_SEARCH_UNIVERSE,
    US_TREASURY_YIELD_CURVE_CSV_URL,
    YAHOO_CLASS_HOME_URL,
    YAHOO_CONCEPT_CLASS_URL,
    YAHOO_ELECTRONIC_CLASS_URL,
    YAHOO_GROUP_CLASS_URL,
    YAHOO_LISTED_CLASS_URL,
    YAHOO_TPEX_EMERGING_CLASS_URL,
    YAHOO_TPEX_ETF_URL,
    YAHOO_TPEX_OTC_CLASS_URL,
)

LOGGER = logging.getLogger("market_pulse")


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


def build_yahoo_taiwan_future_technical_url(code: str) -> str:
    clean_code = str(code or "").strip().upper()
    if not clean_code:
        return ""
    return f"{YAHOO_TW_FUTURE_URL}/{quote(clean_code, safe='')}/technical-analysis"


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


def build_institutions_url(date_str: str) -> str:
    params = {"response": "json", "dayDate": date_str, "type": "day"}
    return f"{TWSE_BASE}/fund/BFI82U?{urlencode(params)}"


def build_weighted_index_history_url(date_str: str) -> str:
    params = {"response": "json", "date": date_str}
    return f"{TWSE_BASE}/indicesReport/MI_5MINS_HIST?{urlencode(params)}"


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


def format_price_value(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "--"


def normalize_taiwan_option_underlying(value: str | None = None) -> str:
    clean = str(value or TAIWAN_OPTION_DEFAULT_PRODUCT).strip().upper()
    return clean if clean in TAIWAN_OPTION_PRODUCTS else TAIWAN_OPTION_DEFAULT_PRODUCT


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
    import app

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
        today = datetime.now(app.TZ).date()
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


def parse_market_iso_date(value: Any) -> datetime | None:
    text = str(value or "").strip()
    for date_format in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue
    return None


def yahoo_future_quote_can_override_taifex(yahoo_quote: dict[str, Any] | None, snapshot: dict[str, Any] | None) -> bool:
    from datetime import timedelta

    if not yahoo_quote:
        return False
    if not snapshot:
        return parse_float(str(yahoo_quote.get("close") or "")) is not None
    yahoo_date = parse_market_iso_date(yahoo_quote.get("date"))
    snapshot_date = parse_market_iso_date(snapshot.get("date"))
    if yahoo_date is None or snapshot_date is None:
        return False
    return yahoo_date >= snapshot_date - timedelta(days=1)


def build_taifex_open_interest_item(
    spec: dict[str, Any],
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    import app

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
        snapshot = fetch_taifex_latest_futures_market_snapshot(commodity, deadline=deadline)
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.exception("TAIFEX futures daily market item fetch failed for symbol=%s", symbol, exc_info=exc)
        snapshot = None
    yahoo_quote = None
    try:
        yahoo_quote = fetch_yahoo_taiwan_future_quote(symbol, deadline=deadline)
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.warning("Yahoo Taiwan futures quote fetch failed for symbol=%s: %s", symbol, exc)
    if not snapshot and not yahoo_quote:
        return {**base_item, "error": "TAIFEX / Yahoo 期貨行情暫無可用資料"}

    use_yahoo_quote = yahoo_future_quote_can_override_taifex(yahoo_quote, snapshot)
    quote_data = yahoo_quote if use_yahoo_quote else (snapshot or {})
    open_value = parse_float(str(quote_data.get("open") or ""))
    high_value = parse_float(str(quote_data.get("high") or ""))
    low_value = parse_float(str(quote_data.get("low") or ""))
    close_value = parse_float(str(quote_data.get("close") or ""))
    volume_value = parse_float(str(quote_data.get("volume") or ""))
    open_interest = (
        parse_float(str(quote_data.get("openInterest") or ""))
        or parse_float(str((snapshot or {}).get("openInterest") or ""))
        or parse_float(str((yahoo_quote or {}).get("openInterest") or ""))
    )
    settlement = parse_float(str((snapshot or {}).get("settlement") or ""))
    change = parse_float(str(quote_data.get("change") or ""))
    pct = parse_float(str(quote_data.get("changePct") or ""))
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
        "date": quote_data.get("date") or (snapshot or {}).get("date") or "--",
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


def build_txo_option_market_item(
    spec: dict[str, Any],
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    import app

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
        chain = fetch_txo_option_chain(source="auto", underlying=symbol, deadline=deadline)
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.exception("%s option market item fetch failed", symbol, exc_info=exc)
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


def taifex_underlying_is_etf(underlying_row: dict[str, Any]) -> bool:
    return "ETF" in str(underlying_row.get("Type") or "")


TAIFEX_OPTIONS_PRODUCT_DAILY_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/Daily_OPT"
TAIFEX_STOCK_DERIVATIVE_AGGREGATE_CACHE_SECONDS = CACHE_TTL_SECONDS["taifex_stock_derivative_aggregate"]


def build_taifex_option_product_volume_summary_item(
    spec: dict[str, Any],
    base_item: dict[str, Any],
    *,
    category_label: str,
    product_label: str,
) -> dict[str, Any] | None:
    import app

    product_code = {"STO": "STC", "ETO": "ETC"}.get(str(spec.get("symbol") or "").strip().upper())
    if not product_code:
        return None
    try:
        rows = fetch_taifex_openapi_list(
            TAIFEX_OPTIONS_PRODUCT_DAILY_OPENAPI_URL,
            TAIFEX_STOCK_DERIVATIVE_AGGREGATE_CACHE_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.warning("TAIFEX Daily_OPT aggregate fetch failed for %s: %s", product_code, exc)
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


TAIFEX_OPTIONS_DAILY_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportOpt"
TAIFEX_SSF_LIST_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/SSFLists"
TAIFEX_SSO_LIST_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/SSOLists"
TAIFEX_UNDERLYING_LIST_CACHE_SECONDS = CACHE_TTL_SECONDS["taifex_underlying_list"]


def build_taifex_stock_derivative_aggregate_item(spec: dict[str, Any]) -> dict[str, Any]:
    """Aggregate TAIFEX OpenAPI daily reports across every individual stock/ETF futures or options
    contract, since TAIFEX has no single commodity code representing "all stock futures" etc."""
    import app

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
        app.LOGGER.warning("TAIFEX underlying list fetch failed for %s: %s", symbol, exc)
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
        app.LOGGER.warning("TAIFEX daily report fetch failed for %s: %s", symbol, exc)
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


TAIFEX_INSTITUTION_ITEM_LABEL_MAP = {"自營商": "自營商", "投信": "投信", "外資及陸資": "外資"}


def build_institution_payload_live(
    product: str,
    source_url: str,
    *,
    deadline: float | None = None,
) -> dict[str, Any] | None:
    import app

    try:
        rows = fetch_taifex_institution_detail_rows(product, deadline=deadline)
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.warning("TAIFEX institution live fetch failed for %s: %s", product, exc)
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


BARCHART_CORE_QUOTES_URL = "https://www.barchart.com/proxies/core-api/v1/quotes/get"
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
DERIBIT_OPTIONS_CHAIN_CACHE_SECONDS = CACHE_TTL_SECONDS["deribit_options_chain"]
DERIBIT_OPTIONS_CURRENCY_BY_SYMBOL = {
    "DERIBIT_BTC": "BTC",
    "DERIBIT_ETH": "ETH",
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
}
BYBIT_OPTIONS_TICKERS_URL = "https://api.bybit.com/v5/market/tickers"
BYBIT_OPTIONS_CHAIN_CACHE_SECONDS = CACHE_TTL_SECONDS["bybit_options_chain"]
BYBIT_OPTIONS_BASE_COIN_BY_SYMBOL = {
    "BYBIT_SOL": "SOL",
    "BYBIT_XRP": "XRP",
    "SOL-USD": "SOL",
    "XRP-USD": "XRP",
}


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
    import app

    if not expirations:
        return None
    if requested in expirations:
        return requested
    today = datetime.now(app.TZ).date()
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
    import app

    clean_symbol = normalize_us_symbol_for_yahoo(re.sub(r"[^A-Za-z0-9=.^_-]", "", symbol or "").upper())
    if not clean_symbol:
        return {"error": "Invalid option underlying symbol."}
    contract_root = clean_symbol[1:] if clean_symbol.startswith("_") else clean_symbol
    cache_key = f"{clean_symbol}:{expiration or ''}"
    if not app.global_market_refresh_requested():
        cached_chain = read_memory_cache("us_options_chains", cache_key, OPTIONS_CHAIN_CACHE_SECONDS)
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
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result), OPTIONS_CHAIN_CACHE_SECONDS)
    return result


def normalize_yahoo_option_contract(contract: dict[str, Any]) -> dict[str, Any]:
    expiration = contract.get("expiration")
    expiration_date = None
    if expiration is not None:
        try:
            expiration_date = datetime.fromtimestamp(int(expiration), timezone.utc).strftime("%Y-%m-%d")
        except Exception as exc:
            LOGGER.debug("Unable to normalize Yahoo option expiration=%r", expiration, exc_info=exc)
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
    import app

    clean_symbol = normalize_us_symbol_for_yahoo(re.sub(r"[^A-Za-z0-9=.^_-]", "", symbol or "").upper())
    root = BARCHART_FUTURES_OPTIONS_ROOTS.get(clean_symbol)
    if not root:
        return {"symbol": clean_symbol, "error": "Barchart futures options source is not mapped for this product."}

    cache_key = f"barchart:{clean_symbol}:{expiration or ''}"
    if not app.global_market_refresh_requested():
        cached_chain = read_memory_cache("us_options_chains", cache_key, OPTIONS_CHAIN_CACHE_SECONDS)
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
        "timestamp": datetime.now(app.TZ).isoformat(),
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
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result_payload), OPTIONS_CHAIN_CACHE_SECONDS)
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
    import app

    clean_symbol = re.sub(r"[^A-Za-z0-9_-]", "", symbol or "").upper()
    currency = DERIBIT_OPTIONS_CURRENCY_BY_SYMBOL.get(clean_symbol)
    if not currency:
        return {"symbol": clean_symbol, "error": "Deribit options source is not mapped for this product."}

    cache_key = f"deribit:{clean_symbol}:{expiration or ''}"
    if not app.global_market_refresh_requested():
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
        "timestamp": datetime.now(app.TZ).isoformat(),
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
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result_payload), DERIBIT_OPTIONS_CHAIN_CACHE_SECONDS)
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
    import app

    clean_symbol = re.sub(r"[^A-Za-z0-9_-]", "", symbol or "").upper()
    base_coin = BYBIT_OPTIONS_BASE_COIN_BY_SYMBOL.get(clean_symbol)
    if not base_coin:
        return {"symbol": clean_symbol, "error": "Bybit options source is not mapped for this product."}

    cache_key = f"bybit:{clean_symbol}:{expiration or ''}"
    if not app.global_market_refresh_requested():
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
        "timestamp": datetime.now(app.TZ).isoformat(),
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
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result_payload), BYBIT_OPTIONS_CHAIN_CACHE_SECONDS)
    return result_payload


def build_public_options_chain(symbol: str, expiration: str | None = None) -> dict[str, Any]:
    import app

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
        app.LOGGER.warning("Cboe options source failed for %s", clean_symbol, exc_info=exc)
        cboe_error = "Cboe options source temporarily unavailable."

    return cboe_chain or {
        "symbol": clean_symbol,
        "error": cboe_error or "Options source returned no contracts.",
        "source": "Cboe Delayed Quotes Options",
        "fallbackBlocked": True,
        "fallbackBlockedReason": "API source is locked to the requested product's Call/Put strike chain.",
    }


STOCK_HISTORY_TIMEOUT_SECONDS = 8
SECTOR_HISTORY_TRADING_DAYS = 30
SECTOR_FUND_FLOW_CACHE_SECONDS = CACHE_TTL_SECONDS["sector_fund_flow"]


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
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Sector history market fetch failed for date=%s; skipping snapshot",
            date_str,
            exc_info=exc,
        )
        return None
    if not dataset_has_rows(payload):
        return None

    activities = {}
    if include_activity:
        try:
            activity_payload = fetch_json(build_index_activity_url(date_str), STOCK_HISTORY_TIMEOUT_SECONDS)
            activities = parse_index_activities(activity_payload) if dataset_has_rows(activity_payload) else {}
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Sector history activity fetch failed for date=%s; using empty activity mapping",
                date_str,
                exc_info=exc,
            )
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
    import app

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
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug(
                    "Sector history snapshot failed for date=%s; skipping snapshot",
                    futures[future],
                    exc_info=exc,
                )
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
            app.WEIGHTED_INDEX_HISTORY_TRADING_DAYS,
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
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Weighted index Yahoo history fetch failed for date=%s; using TWSE history fallback",
            latest_market_date,
            exc_info=exc,
        )
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
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Weighted index history fetch failed for month=%s; skipping month",
                month_date,
                exc_info=exc,
            )
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


def format_fund_flow_amount(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{format_signed(value / 100_000_000, 1)} 億"


def build_sector_fund_flow(stocks: list[dict[str, Any]], market_date: str) -> dict[str, Any]:
    import app

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
        app.LOGGER.exception("Sector fund flow build failed")
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


def build_yahoo_class_quote_cards(
    url: str,
    prefix: str,
    limit: int = 6,
    timeout: int = 8,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        html = fetch_text(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Yahoo class quote page fetch failed for prefix=%s url=%s; using empty cards",
            prefix,
            url,
            exc_info=exc,
        )
        return [], None

    rows, snapshot_date, _ = parse_yahoo_class_quote_rows(html)
    if len(rows) < limit:
        try:
            paged_rows = fetch_yahoo_class_quote_pages(url, snapshot_date, limit)
            if paged_rows:
                rows = paged_rows
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Yahoo class quote pagination failed for prefix=%s url=%s; using primary page rows",
                prefix,
                url,
                exc_info=exc,
            )
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
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Yahoo sector group fetch failed for key=%s prefix=%s; using empty group",
                key,
                prefix,
                exc_info=exc,
            )
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


def _refresh_all_market_penny_sector_recommendations() -> dict[str, Any]:
    import app

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
            app.LOGGER.warning("Penny sector category fetch failed group=%s name=%s: %s", group_key, name, exc)
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
        "updatedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
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
        wait_for_cache_flight(flight)
        with penny_sector_recommendation_lock:
            cached_payload = penny_sector_recommendation_cache.get("payload")
        if cached_payload:
            return copy.deepcopy(cached_payload)
        raise RuntimeError("三市場類股成分股同步未完成，請稍後再試")

    try:
        return _refresh_all_market_penny_sector_recommendations()
    finally:
        finish_cache_flight("penny-sector-recommendations", flight)


STOCK_HISTORY_RECENT_MONTHS = 3
STOCK_HISTORY_MAX_MONTHS = 480


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
    import app

    candidates: list[str] = []
    seen: set[str] = set()

    def add_date(value: str) -> None:
        if re.fullmatch(r"\d{8}", value) and value not in seen:
            candidates.append(value)
            seen.add(value)

    add_date(app.taipei_now().strftime("%Y%m%d"))
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
    import app

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
        base_date = app.taipei_now().date()

    for offset in range(1, lookback_days + 1):
        if len(rows) >= max_rows:
            break
        date_str = (base_date - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            payload = fetch_json(build_institutions_url(date_str), timeout=8)
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Institution trend fetch failed for date=%s; skipping date",
                date_str,
                exc_info=exc,
            )
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
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Yahoo history fetch failed for stock=%s in quick mode; using fallback history",
                stock.get("code"),
                exc_info=exc,
            )
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
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Yahoo history fetch failed for stock=%s; trying fallback history",
                stock.get("code"),
                exc_info=exc,
            )
            rows = []
        history_rows_removed += yahoo_diagnostics.get("invalid_rows", 0)
        raw_row_count = len(rows)
        rows = sanitize_history_rows(rows)
        history_rows_removed += raw_row_count - len(rows)
        if not rows and market != "TPEx":
            try:
                rows = fetch_stock_history_rows(stock["code"], date_str, months_back=months_back)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug(
                    "TWSE history fallback failed for stock=%s; using generated fallback history",
                    stock.get("code"),
                    exc_info=exc,
                )
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
                "companyProfile": executor.submit(fetch_stock_company_profile, stock),
            })
            # The two-row history generated by build_fallback_history_rows is
            # only a display-safe placeholder for the technical section. It
            # must not become a fake valuation history (e.g. two consecutive
            # days presented as the promised six monthly observations).
            if not used_fallback_history:
                futures["valuationHistory"] = executor.submit(
                    fetch_stock_valuation_history,
                    stock,
                    rows,
                    5,
                )
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
    if not used_fallback_history and latest_valuation_date and not any(
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


PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE = "TAIFEX 選擇權鏈暫時無法載入，請稍後再試"
PUBLIC_MARKET_ITEM_ERROR_MESSAGE = "行情資料暫時無法載入，請稍後再試"


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


GLOBAL_MARKET_ITEM_CACHE_SECONDS = CACHE_TTL_SECONDS["global_market_item"]


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
    write_memory_cache("global_market_items", cache_key, copy.deepcopy(item), GLOBAL_MARKET_ITEM_CACHE_SECONDS)
    return item


def build_us_treasury_yield_curve_item(spec: dict[str, Any], base_item: dict[str, Any]) -> dict[str, Any]:
    import app

    maturity = str(spec.get("treasuryMaturity") or "2 Yr")
    try:
        dated_rows = fetch_us_treasury_yield_curve_rows()
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.exception("U.S. Treasury yield curve fetch failed", exc_info=exc)
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
    import app

    return (app.taipei_now().date() - date_value.date()).days > FALLBACK_OBSERVATION_MAX_AGE_DAYS


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
    import app

    series_id = str(spec.get("fredSeriesId") or "").strip().upper()
    observations: list[tuple[datetime, float]] = []
    source_note = spec.get("dataSource") or "FRED"
    source_status = "live"
    try:
        observations = fetch_fred_observation_rows(series_id)
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.warning("FRED series fetch failed for %s: %s", series_id, exc)
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
    import app

    try:
        observation = fetch_trading_economics_taiwan_10y()
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.warning("Trading Economics Taiwan 10Y fetch failed: %s", exc)
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
        import app

        try:
            app.load_disk_cache()
        except Exception as exc:  # noqa: BLE001
            app.LOGGER.debug("Unable to load disk cache for Taiwan quote fallback", exc_info=exc)
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


def build_global_market_item(
    spec: dict[str, Any],
    *,
    deadline: float | None = None,
) -> dict[str, Any]:
    import app

    symbol = str(spec.get("symbol") or "").strip()
    item_cache_key = global_market_item_cache_key(spec)
    if not app.global_market_refresh_requested():
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
            return cache_global_market_item(item_cache_key, build_txo_option_market_item(spec, deadline=deadline))
        if spec.get("dataProvider") in {"taifex_tx_open_interest", "taifex_txo_open_interest", "taifex_futures_open_interest"}:
            return cache_global_market_item(item_cache_key, build_taifex_open_interest_item(spec, deadline=deadline))
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
            for attempt in range(YAHOO_MAX_RETRY + 1):
                if deadline is not None and (remaining_budget(deadline) or 0) <= 0:
                    break
                try:
                    chart = fetch_yahoo_symbol_chart(selected_symbol, "1y", "1d", deadline=deadline)
                    series = build_yahoo_chart_series(chart, volume_divisor=1)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.debug(
                        "Global market Yahoo chart fetch failed for symbol=%s candidate=%s attempt=%s; retrying or using fallback",
                        symbol,
                        selected_symbol,
                        attempt + 1,
                        exc_info=exc,
                    )
                    chart = None
                    series = []
                if len(series) >= 2:
                    break
                if attempt < YAHOO_MAX_RETRY:
                    remaining = remaining_budget(deadline)
                    if remaining is not None:
                        if remaining <= 0:
                            break
                        time.sleep(min(0.15, remaining))
                    else:
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
        app.LOGGER.exception("Global market item fetch failed for symbol=%s", symbol, exc_info=exc)
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


# DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
def format_us_ratio(value: Any, digits: int = 2) -> str:
    parsed = parse_us_display_number(value)
    return f"{parsed:.{digits}f}" if parsed is not None else "N/A"


# DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
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
    import app

    raw = yahoo_field_raw(value)
    parsed = parse_float(str(raw or ""))
    if parsed is None:
        return "--"
    try:
        return datetime.fromtimestamp(parsed, app.TZ).strftime("%Y-%m-%d")
    except (OSError, ValueError):
        return "--"


def build_us_valuation(summary: dict[str, Any]) -> dict[str, Any]:
    import app

    summary_detail = summary.get("summaryDetail") or {}
    key_stats = summary.get("defaultKeyStatistics") or {}
    financial = summary.get("financialData") or {}
    price = summary.get("price") or {}
    dividend_yield = yahoo_field_raw(summary_detail.get("dividendYield"))
    if isinstance(dividend_yield, (int, float)):
        dividend_yield = dividend_yield * 100
    return {
        "date": datetime.now(app.TZ).strftime("%Y-%m-%d"),
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
    import app

    return {
        "date": datetime.now(app.TZ).strftime("%Y-%m-%d"),
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
        "aum": "N/A",
        "expenseRatio": "N/A",
        "averageVolume": "N/A",
        "fiftyTwoWeekRange": "N/A",
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
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "U.S. beta benchmark fetch failed for symbol=%s; using unavailable beta",
            clean_symbol,
            exc_info=exc,
        )
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
    import app

    raw = yahoo_field_raw(value)
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, app.TZ).strftime("%Y-%m-%d")
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
    import app

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
        "date": datetime.now(app.TZ).strftime("%Y-%m-%d"),
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
    import app

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
        merged["date"] = datetime.now(app.TZ).strftime("%Y-%m-%d")
        merged["sourceNote"] = (
            "資料來源：Nasdaq institutional-holdings / insider-trades 公開 API；"
            "Yahoo holders 模組若取得授權則作為補充，正式申報仍以 SEC EDGAR 為準。"
        )
        merged["sourceLink"] = f"https://www.nasdaq.com/market-activity/stocks/{quote(symbol.lower(), safe='')}/institutional-holdings"
    return merged


def build_us_market_symbol_detail(spec: dict[str, Any]) -> dict[str, Any]:
    item = build_global_market_item(spec)
    if item.get("error"):
        item_type = str(item.get("type") or spec.get("type") or "").upper()
        is_etf = item.get("group") == "美股 ETF" or "ETF" in item_type or "FUND" in item_type
        if not is_etf:
            return item
        data_symbol = str(item.get("dataSymbol") or item.get("symbol") or spec.get("symbol") or "")
        return {
            **{key: value for key, value in item.items() if key != "error"},
            "group": "美股 ETF",
            "type": item.get("type") or "ETF",
            "detailMode": "fallback",
            "historyRange": "5y",
            "dataStatus": "ETF 公開資料目前同步中，已保留分析區塊。",
            "valuation": build_us_fallback_valuation(item),
            "valuationHistory": [],
            "companyProfile": build_us_fallback_company_profile(data_symbol, item),
            "companyNews": [],
            "marginTrading": build_us_fallback_margin_proxy(),
            "ownershipTrading": build_us_fallback_ownership_trading(data_symbol),
            "etfComponents": {
                "title": "ETF 成分股比例",
                "summary": "ETF 持股資料目前同步中；取得 Yahoo Finance Top Holdings 後會在此顯示配置比例。",
                "holdings": [],
                "sourceNote": "目前無法取得即時持股明細，請以發行商公告為準。",
                "sourceLink": "https://finance.yahoo.com/",
            },
            "isEtf": True,
            "newsLinks": {
                "yahoo": f"https://finance.yahoo.com/quote/{quote(data_symbol, safe='')}/news",
                "profile": f"https://finance.yahoo.com/quote/{quote(data_symbol, safe='')}/profile",
                "sec": f"https://www.sec.gov/edgar/search/#/q={quote(data_symbol, safe='')}",
            },
        }
    data_symbol = str(item.get("dataSymbol") or item.get("symbol") or spec.get("symbol") or "")
    try:
        chart = fetch_yahoo_symbol_chart(data_symbol, "5y", "1d")
        long_series = build_yahoo_chart_series(chart, volume_divisor=1)
        if len(long_series) >= len(item.get("series") or []):
            item["series"] = long_series
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "U.S. market detail long history fetch failed for symbol=%s; keeping existing series",
            data_symbol,
            exc_info=exc,
        )
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
            except Exception as exc:  # noqa: BLE001
                fallback_name = (
                    "empty summary"
                    if key == "summary"
                    else "empty news list"
                    if key == "news"
                    else "empty Nasdaq supplement"
                )
                LOGGER.debug(
                    "U.S. market detail component fetch failed for symbol=%s key=%s; using %s fallback",
                    data_symbol,
                    key,
                    fallback_name,
                    exc_info=exc,
                )
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
    item_type = str(item.get("type") or spec.get("type") or "").upper()
    is_etf = (
        "ETF" in quote_type
        or "FUND" in quote_type
        or item.get("group") == "美股 ETF"
        or "ETF" in item_type
    )
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
    import app

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
        fresh = abs((datetime.now(app.TZ).date() - datetime.strptime(latest_date, "%Y-%m-%d").date()).days) <= 12
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
    option_underlying: str = "TXO",
) -> dict[str, Any]:
    import app

    spec = GLOBAL_MARKET_CATEGORIES[category]
    catalog_items = [enrich_global_market_spec(item, category) for item in spec["items"]]
    selected_specs = catalog_items[:limit] if limit else catalog_items
    items: list[dict[str, Any]] = []
    endpoint_budget = (
        FUTURES_BACKEND_BUDGET_SECONDS if category == "futures"
        else OPTIONS_BACKEND_BUDGET_SECONDS if category == "options"
        else None
    )
    deadline = deadline_after(endpoint_budget) if endpoint_budget is not None else None
    # Item fetches are independent I/O-bound Yahoo Finance / TAIFEX lookups (each already
    # throttled at its own external-source layer where that source needs it, e.g. the TAIFEX
    # form-query semaphore), so a wider pool here mainly cuts wall-clock wait time.
    max_workers = min(6 if category == "options" else 8, len(selected_specs))
    executor_cls = app.DeadlineThreadPoolExecutor if deadline is not None else ThreadPoolExecutor
    executor = executor_cls(max_workers=max_workers)
    futures = {
        executor.submit(build_global_market_item, item, deadline=deadline): item
        for item in selected_specs
    }

    def append_failed_item(item_spec: dict[str, Any], exc: Exception | None = None) -> None:
        if category not in {"futures", "options"}:
            if exc is not None:
                raise exc
            return
        symbol = str(item_spec.get("symbol") or "").strip()
        if exc is not None:
            app.LOGGER.exception("Global %s item fan-out failed for symbol=%s", category, symbol, exc_info=exc)
        items.append({
            "symbol": symbol,
            "name": item_spec.get("name") or symbol,
            "type": item_spec.get("type") or "市場商品",
            "group": item_spec.get("group") or item_spec.get("type") or "市場商品",
            "region": item_spec.get("region") or "全球 / 其他",
            "market": item_spec.get("market") or item_spec.get("region") or "全球 / 其他",
            "exchange": item_spec.get("exchange") or "",
            "source": item_spec.get("dataSource") or "Yahoo Finance",
            "dataSource": item_spec.get("dataSource") or "Yahoo Finance",
            "sourceUrl": item_spec.get("sourceUrl") or "",
            "status": "source_pending",
            "error": PUBLIC_MARKET_ITEM_ERROR_MESSAGE,
            "dataStatus": "單一商品資料來源失敗，保留商品識別並停止填入行情數值。",
            "series": [],
        })

    try:
        if deadline is None:
            done, pending = wait(futures)
        else:
            done, pending = wait(futures, timeout=max(0.0, remaining_budget(deadline) or 0.0))
        for future in done:
            item_spec = futures[future]
            try:
                items.append(future.result())
            except Exception as exc:  # noqa: BLE001
                append_failed_item(item_spec, exc)
        for future in pending:
            item_spec = futures[future]
            future.cancel()
            append_failed_item(item_spec)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

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
        "updatedAt": datetime.now(app.TZ).strftime("%Y-%m-%d %H:%M:%S"),
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
            app.LOGGER.exception("US market overview news payload fetch failed", exc_info=exc)
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
            payload["taiwanOptionChain"] = fetch_txo_option_chain(
                source=option_source,
                underlying=option_underlying,
                deadline=deadline,
            )
        except Exception as exc:  # noqa: BLE001
            product = get_taiwan_option_product(option_underlying)
            app.LOGGER.exception("%s option chain payload fetch failed", product["symbol"], exc_info=exc)
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
            app.DERIVATIVES_STORE.record_futures_payload(payload)
        elif category == "options":
            option_chain = payload.get("taiwanOptionChain") or {}
            app.DERIVATIVES_STORE.record_option_chain(option_chain, str(payload.get("updatedAt") or ""))
            if option_chain.get("analysis"):
                app.DERIVATIVES_STORE.record_ai_report(str(option_chain.get("underlying") or option_underlying), option_chain["analysis"], str(payload.get("updatedAt") or ""))
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.exception("Failed to persist derivatives payload", exc_info=exc)
    return payload


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
    import app

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
        "updatedAt": datetime.now(app.TZ).strftime("%Y-%m-%d %H:%M:%S"),
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


def build_site_data(
    existing_site_data: dict[str, Any] | None = None,
    existing_market_date: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    import app

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
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Site data TPEx mainboard quote fetch failed for market_date=%s; using empty quotes",
            market_date,
            exc_info=exc,
        )
        tpex_mainboard_quotes = []
        tpex_mainboard_quote_date = None
    try:
        yahoo_tpex_etfs = fetch_yahoo_tpex_etfs()
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Site data Yahoo TPEx ETF fetch failed for market_date=%s; using empty ETF mapping",
            market_date,
            exc_info=exc,
        )
        yahoo_tpex_etfs = {}
    try:
        yahoo_sector_catalog = fetch_yahoo_sector_catalog()
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Site data Yahoo sector catalog fetch failed for market_date=%s; using empty catalog",
            market_date,
            exc_info=exc,
        )
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
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Site data TPEx mainboard highlight fetch failed for market_date=%s; using empty highlight",
                market_date,
                exc_info=exc,
            )
            tpex_mainboard_highlight = []
    if not tpex_esb_highlight:
        try:
            tpex_esb_highlight = build_summary_cards_from_payload(
                fetch_json(build_tpex_openapi_url("tpex_esb_highlight")),
                "興櫃",
                limit=6,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Site data TPEx emerging highlight fetch failed for market_date=%s; using empty highlight",
                market_date,
                exc_info=exc,
            )
            tpex_esb_highlight = []
    if not tpex_esb_latest_statistics:
        try:
            tpex_esb_latest_statistics = build_summary_cards_from_payload(
                fetch_json(build_tpex_openapi_url("tpex_esb_latest_statistics")),
                "興櫃統計",
                limit=6,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Site data TPEx emerging statistics fetch failed for market_date=%s; using empty statistics",
                market_date,
                exc_info=exc,
            )
            tpex_esb_latest_statistics = []
    activity_payload = None
    activity_date = market_date
    try:
        same_day_activity = fetch_json(build_index_activity_url(market_date))
        if dataset_has_rows(same_day_activity):
            activity_payload = same_day_activity
        else:
            activity_date = None
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Site data index activity fetch failed for market_date=%s; using no activity date",
            market_date,
            exc_info=exc,
        )
        activity_date = None
    try:
        same_day_intraday = fetch_json(build_index_intraday_url(market_date))
        if dataset_has_rows(same_day_intraday):
            intraday_payload, intraday_date = same_day_intraday, market_date
        else:
            intraday_payload, intraday_date = None, market_date
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Site data index intraday fetch failed for market_date=%s; using no intraday payload",
            market_date,
            exc_info=exc,
        )
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
                app.WEIGHTED_INDEX_HISTORY_TRADING_DAYS,
            )
    else:
        history_series_by_index = build_sector_history_series(market_date, TARGET_INDEX_NAMES)
    if not weighted_index_history_has_volume(history_series_by_index.get("發行量加權股價指數", [])):
        history_series_by_index["發行量加權股價指數"] = build_weighted_index_history_series(
            market_date,
            app.WEIGHTED_INDEX_HISTORY_TRADING_DAYS,
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
        app.LOGGER.exception("Institution trend build failed")
        institution_trend = {}
    market_stats = parse_market_statistics(market_payload)
    try:
        market_volatility = fetch_market_volatility_indicator(
            history_series_by_index.get("發行量加權股價指數", []),
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Site data market volatility fetch failed for market_date=%s; using unavailable volatility",
            market_date,
            exc_info=exc,
        )
        market_volatility = None
    try:
        market_international_indexes = fetch_international_market_indexes()
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Site data international indexes fetch failed for market_date=%s; using empty indexes",
            market_date,
            exc_info=exc,
        )
        market_international_indexes = []
    try:
        market_macro_factors = fetch_market_macro_factors(market_date)
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug(
            "Site data macro factors fetch failed for market_date=%s; using empty factors",
            market_date,
            exc_info=exc,
        )
        market_macro_factors = {}
    sector_fund_flow = build_sector_fund_flow(twse_stocks, market_date)
    cached_at = app.taipei_now().strftime("%Y-%m-%d %H:%M:%S")
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


def build_live_sector_site_data() -> dict[str, Any]:
    """Build a live sectors payload without rebuilding every dashboard dataset."""
    import app

    with app.DeadlineThreadPoolExecutor(max_workers=7) as executor:
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
            app.LOGGER.exception("Live sectors institution fetch failed")
            institution_payload, institution_date = {"data": []}, market_date

        try:
            activity_payload = activity_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            app.LOGGER.exception("Live sectors index activity fetch failed")
            activity_payload = None

        try:
            intraday_payload = intraday_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            app.LOGGER.exception("Live sectors intraday fetch failed")
            intraday_payload = None

        try:
            history_series_by_index = history_future.result(timeout=18)
        except Exception:  # noqa: BLE001
            app.LOGGER.exception("Live sectors history fetch failed")
            history_series_by_index = {}

        try:
            yahoo_sector_groups, yahoo_sector_dates = yahoo_groups_future.result(timeout=20)
        except Exception as exc:  # noqa: BLE001
            app.LOGGER.warning("Live sectors Yahoo group fetch unavailable: %s", exc)
            yahoo_sector_groups, yahoo_sector_dates = {}, {}

        try:
            yahoo_sector_catalog = yahoo_catalog_future.result(timeout=10)
        except Exception:  # noqa: BLE001
            app.LOGGER.exception("Live sectors Yahoo catalog fetch failed")
            yahoo_sector_catalog = {}

        try:
            market_volatility = volatility_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            app.LOGGER.exception("Live sectors VIX fetch failed")
            market_volatility = None

    if not weighted_index_history_has_volume(history_series_by_index.get("發行量加權股價指數", [])):
        try:
            history_series_by_index["發行量加權股價指數"] = build_weighted_index_history_series(market_date, 120)
        except Exception:  # noqa: BLE001
            app.LOGGER.exception("Live sectors weighted index history fetch failed")

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
        app.LOGGER.exception("Live sectors institution trend build failed")
        institution_trend = {}
    market_overview = parse_market_overview(market_payload)
    market_stats = parse_market_statistics(market_payload)
    cached_at = app.taipei_now().strftime("%Y-%m-%d %H:%M:%S")
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
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Live sectors news build failed for market_date=%s; using empty news",
                market_date,
                exc_info=exc,
            )
            site_data["news"] = []
    else:
        site_data["news"] = []

    return sanitize_site_data(site_data)


def build_live_market_overview_data() -> dict[str, Any]:
    import app

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
            app.LOGGER.exception("Live overview VIX fetch failed")
            market_volatility = None
        try:
            tpex_quotes, tpex_quote_date = tpex_future.result(timeout=12)
        except Exception:  # noqa: BLE001
            app.LOGGER.exception("Live overview TPEx quotes fetch failed")
            tpex_quotes, tpex_quote_date = [], None
        try:
            yahoo_sector_groups, yahoo_sector_dates = yahoo_groups_future.result(timeout=20)
        except Exception as exc:  # noqa: BLE001
            app.LOGGER.warning("Live overview Yahoo sector group fetch unavailable: %s", exc)
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
        app.LOGGER.exception("Live overview institution trend build failed")
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
        "cachedAt": app.taipei_now().strftime("%Y-%m-%d %H:%M:%S"),
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
