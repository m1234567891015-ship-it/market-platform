"""Data-normalization/parsing helpers extracted from app.py (TD-01 slice 5),
starting with the TAIFEX/Yahoo Taiwan-option domain-config constants and the
pure options-pricing functions (batch A0). This is the first of the two
`parsers.py`-building batches (A0-A2) that must land before slice 5's route
extraction (Phase B) can begin, since nearly every route depends on this
block.

Historical note: this ~1,693-line block (originally app.py:499-2191) was
*never* moved during slices 3/4 (the fetchers.py/builders.py extractions),
even though several of its functions are named similarly to that era's
`fetch_*`/`build_*` work — it predates that naming convention and was left as
app.py-local "STAYS" content, reached by builders.py/fetchers.py via the
deferred `import app` pattern documented extensively in both of those
modules' docstrings (e.g. builders.py:148-155, 181-191). Now that all 79
`build_*` and 86 `fetch_*` functions are fully extracted, this module gives
that leftover shared-parsing layer a proper home instead of leaving it as
permanent app.py residue.

Batch A0 moves:
- TAIFEX/Yahoo Taiwan-option domain-config constants: `TAIWAN_OPTION_PRODUCTS`,
  `TAIWAN_OPTION_DEFAULT_PRODUCT`, `YAHOO_TW_FUTURE_URL`,
  `YAHOO_TW_FUTURE_UNCOVERED_URL`, `YAHOO_TW_OPTION_URL`,
  `YAHOO_TW_FUTURE_CODE_TO_SYMBOL`, `YAHOO_TW_FUTURE_CODE_PREFIX_TO_SYMBOL`,
  `YAHOO_TW_FUTURE_TECHNICAL_GROUPS`. `YAHOO_TW_OPTION_WTXO_URL` moves too,
  marked DEADCODE-CANDIDATE (confirmed zero callers anywhere in the repo by
  grep) per the standing behavior-preserving-refactor rule from slices 3/4.
- The options-pricing cluster: `normal_cdf` (exclusive helper),
  `black_scholes_index_option_price`, `estimate_index_option_iv` — verified
  by grep to have zero callers anywhere outside the app.py block being moved
  in this slice (only called from `parse_taifex_txo_option_rows`/
  `parse_yahoo_txo_option_table`, both landing in batch A1), and no test
  coverage (direct or `@patch.object`) to preserve.
- Two small TAIFEX-option lookup functions built directly on
  `TAIWAN_OPTION_PRODUCTS`: `get_taiwan_option_product`, `normalize_taiwan_option_source`.
  `get_taiwan_option_product` is the single most-referenced name in this
  batch — used via deferred `import app` from ~10 call sites across
  builders.py and fetchers.py (both modules' docstrings call it out by name
  as "TAIFEX-domain config, stays in app.py"; that documentation is now
  stale and has been corrected there and here).

Import-direction note (why `estimate_index_option_iv` still needs a deferred
`import app`, and why fetchers.py's call sites for these names were
deliberately left untouched): this module needs `from fetchers import
TAIFEX_FUTURES_DATA_DOWNLOAD_URL` (one plain string constant, embedded in
`YAHOO_TW_FUTURE_TECHNICAL_GROUPS`'s "TMF" entry) at module level, which
means `fetchers.py -> parsers.py` would be a real circular import if
fetchers.py also imported from parsers.py at module level. So this module
never imports from `builders.py`/`fetchers.py` for anything *except* that one
fetchers.py constant (fetchers.py has zero dependency back on this module),
and `builders.py`'s existing deferred-`import app` call sites for these names
were simplified to direct `from parsers import ...` (safe: builders.py ->
parsers.py is a one-directional edge, builders.py already depends on
fetchers.py the same way), while `fetchers.py`'s equivalent call sites were
left as `app.get_taiwan_option_product(...)` etc., unchanged - they still
resolve correctly since app.py re-imports these names from this module below,
they just take one more hop through app.py's namespace rather than a direct
import. `get_taiwan_option_product` itself needs `normalize_taiwan_option_underlying`,
which lives in builders.py (moved there in slice 4 batch 1) - for the same
one-directional-dependency reason, it's reached here via a deferred
`import app` (app.py re-exports it from builders.py), not a direct
`from builders import ...`, to avoid the opposite-direction cycle.
`estimate_index_option_iv` needs `TZ`, which stays in app.py's bootstrap
section (module-load-order reasons, same as every other slice) - reached the
same way.

Batch A1 moves the `parse_*` cluster (`parse_taifex_txo_option_rows`,
`parse_yahoo_txo_option_table`, `parse_yahoo_taiwan_future_quotes`,
`parse_all_stocks`, `parse_tpex_quotes`, `parse_sectors`, `parse_institutions`,
`parse_market_overview`, `parse_market_statistics`) plus every helper found
(by grep) to be exclusive to this cluster: `classify_tpex_security`,
`parse_yahoo_tw_future_date`, `parse_yahoo_tw_future_number`,
`parse_taifex_number`, `parse_taifex_contract_date`, `strip_html`,
`parse_sign`, `find_table_by_title`. `parse_yahoo_tw_future_date`/`_number`
are SHARED-PURE (also called by two still-resident app.py functions,
`parse_yahoo_txo_underlying_snapshot`/`parse_yahoo_txo_option_page`) so
they're re-imported into app.py the same way as every other SHARED-PURE name
in this codebase's extraction slices. `strip_html`/`parse_sign` looked
SHARED at first glance (`parse_sign` calls `strip_html`) but both are
exclusively called by functions in this same batch, so they're EXCLUSIVE to
the cluster as a whole, not to any single function within it. Two more
turned out SHARED-PURE on a second, wider repo-grep pass after the initial
per-batch research missed them: `find_table_by_field` (also called by
builders.py's `parse_index_close_values`) and `parse_index_activities` (also
called by builders.py's `build_sector_history_snapshot`) - both re-imported
directly into builders.py (`builders.py -> parsers.py` is the safe
direction), which incidentally let two more of builders.py's `import app`
statements be dropped entirely (`parse_index_close_values`,
`build_sector_history_snapshot` no longer need it).

Three of these functions call into `builders.py`-resident response-shaping
code (`build_intraday_technical_analysis` for `parse_all_stocks`/
`parse_tpex_quotes`; `build_intraday_index_candles`/
`build_index_technical_analysis`/`resolve_sector_key` for `parse_sectors`) -
reached via a deferred `import app`, the same one-directional-cycle-avoidance
reason as `get_taiwan_option_product`'s call into
`normalize_taiwan_option_underlying` in batch A0's note above (this module
cannot import from `builders.py` at module level, since `builders.py` already
imports from this module). `TARGET_INDEX_NAMES`/`INDEX_DISPLAY_NAMES`
(market_config.py) and `detect_tone`/`parse_float`/`format_signed`/
`format_percent`/`format_whole_number`/`extract_visible_text_lines`
(fetchers.py) are safe to import directly at module level - neither module
depends back on this one.

Batch A2 is the LAST batch touching app.py's originally-499-2191
never-modularized block (Phase A of TD-01 slice 5). It moves everything left
in that block except code proven SHARED with still-resident app.py routes/
helpers: `merge_site_data_with_fallback`, `enrich_yahoo_cards_with_market_stats`,
`enrich_stocks_with_industry`, `market_payload_has_complete_index_tables`
(+ its exclusive private helpers `payload_has_field_candidates`,
`market_payload_has_stock_table`, `market_payload_has_index_table`),
`weighted_index_history_is_usable`, `weighted_index_history_has_volume`,
`upsert_latest_weighted_index_point`, `find_stock_by_query`,
`refresh_tpex_cache`, `pick_exact_live_stock`, `find_derivative_spec`.
`find_derivative_spec` sits far downstream, separated from the rest of this
cluster by ~13 live `@app.route` handlers - moved anyway since it's still
part of the same never-extracted helper category, just physically distant.

Explicitly NOT moved despite falling inside the numeric line range, because
grep found real callers in still-resident app.py route code (or, for
`taipei_now`, extensive use across builders.py/fetchers.py/live_source_validation.py
as an established STAYS name per builders.py's own docstring): `taipei_now`,
`apply_yahoo_quote`, `format_market_date`, `derivative_request_limit`,
`global_market_refresh_requested` (the last of these was already correctly
identified as a builders.py-only STAYS name in slice 4's batch 1 notes).
Also NOT moved: a 9-function TAIFEX/Yahoo option-chain-with-open-interest
supplementing cluster (`infer_yahoo_taiwan_future_symbol_from_code` through
`supplement_taifex_option_payload_with_yahoo_oi`) sitting between
`merge_site_data_with_fallback` and `enrich_yahoo_cards_with_market_stats` -
a distinct domain (option-chain OI reconciliation, not generic parsing/
merging) never in this batch's planned scope, left for a future TD-01
sub-item if one is ever opened.

Five functions turned out to be dead code (zero callers anywhere in the
repo, confirmed by exhaustive grep across every `.py` file including
`live_source_validation.py`, `regression/`, `derivatives/`) - moved as-is
with `# DEADCODE-CANDIDATE` markers per the standing rule rather than
deleted: `merge_trade_counts`, `sector_aliases`, `sync_yahoo_quotes`,
`site_data_has_complete_sector_payload`, `site_data_recent_enough`.
`sync_yahoo_quotes`'s only call site (`apply_yahoo_quote`) is itself a STAYS
function - the two were already logically disconnected from any real
execution path.

`upsert_latest_weighted_index_point` calls `parse_index_close_values(...)`,
a name never imported into app.py's namespace anywhere (defined at
builders.py:2418, used only internally there) - this has silently raised
`NameError` at runtime since before this slice, swallowed by a broad
`except Exception:` that falls back to candle data instead. Moved verbatim
per the behavior-preserving-refactor rule, same treatment as the
`build_yahoo_chart_series` `NameError` documented in builders.py's own
batch-2 docstring note - not "fixed" here either.

Many STAYS names reached via deferred `import app` in this batch: `LOGGER`,
`TZ`, `taipei_now`, `WEIGHTED_INDEX_HISTORY_TRADING_DAYS`, `apply_yahoo_quote`
(from `sync_yahoo_quotes`, the dead function), and several `builders.py`-resident
response-shaping functions this module cannot import directly
(`build_intraday_index_candles`, `build_sector_history_series`,
`build_yahoo_class_quote_cards`, `build_summary_cards_from_payload`,
`build_yahoo_summary_series`, `build_tpex_openapi_url`,
`enrich_global_market_spec`) - same one-directional-cycle-avoidance reason
as every prior batch. `cache_data`/`cache_lock`/`save_disk_cache` (cache.py)
and `fetch_tpex_mainboard_quotes`/`fetch_yahoo_tpex_etfs`/`fetch_json`/
`fetch_twse_listed_industry_map`/`fetch_live_stock_search_results`/
`normalize_market_request`/`parse_roc_date` (fetchers.py) and
`GLOBAL_MARKET_CATEGORIES`/`LISTED_SECTOR_INDEX_SPECS`/
`YAHOO_TPEX_OTC_CLASS_URL`/`YAHOO_TPEX_EMERGING_CLASS_URL` (market_config.py)
are all safe to import directly at module level - none of those modules
depend back on this one.
"""
from __future__ import annotations

import copy
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html import unescape
from typing import Any

from cache import cache_data, cache_lock, save_disk_cache
from fetchers import (
    TAIFEX_FUTURES_DATA_DOWNLOAD_URL,
    detect_tone,
    extract_visible_text_lines,
    fetch_json,
    fetch_live_stock_search_results,
    fetch_tpex_mainboard_quotes,
    fetch_twse_listed_industry_map,
    fetch_yahoo_tpex_etfs,
    format_percent,
    format_signed,
    format_whole_number,
    normalize_market_request,
    parse_float,
    parse_roc_date,
)
from market_config import (
    GLOBAL_MARKET_CATEGORIES,
    INDEX_DISPLAY_NAMES,
    LISTED_SECTOR_INDEX_SPECS,
    TARGET_INDEX_NAMES,
    YAHOO_TPEX_EMERGING_CLASS_URL,
    YAHOO_TPEX_OTC_CLASS_URL,
)


YAHOO_TW_FUTURE_URL = "https://tw.stock.yahoo.com/future"
YAHOO_TW_FUTURE_UNCOVERED_URL = "https://tw.stock.yahoo.com/future/futures_uncovered.html"
YAHOO_TW_OPTION_URL = "https://tw.stock.yahoo.com/future/options.html"
YAHOO_TW_OPTION_WTXO_URL = f"{YAHOO_TW_OPTION_URL}?opmr=optionfull&opcm=WTXO"  # DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
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
    import app

    if option_price is None or spot is None or strike is None or option_price <= 0 or spot <= 0 or strike <= 0:
        return None
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").replace(tzinfo=app.TZ)
    except ValueError:
        return None
    now = datetime.now(app.TZ)
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
    import app

    underlying = app.normalize_taiwan_option_underlying(value)
    return {**TAIWAN_OPTION_PRODUCTS[underlying], "symbol": underlying}


def normalize_taiwan_option_source(value: str | None = None) -> str:
    clean = str(value or "auto").strip().lower()
    return clean if clean in {"auto", "taifex", "yahoo"} else "auto"


def classify_tpex_security(code: str, yahoo_etf_codes: set[str]) -> tuple[str | None, str | None]:
    if code in yahoo_etf_codes or re.fullmatch(r"00[A-Z0-9]{4}", code, re.IGNORECASE):
        return "ETF", "上櫃ETF"
    if re.fullmatch(r"\d{4}A?", code, re.IGNORECASE):
        return "STOCK", "上櫃個股"
    return None, None


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
    import app

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
        quote_date = datetime.now(app.TZ).strftime("%Y-%m-%d")
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


def parse_taifex_number(value: Any) -> float | None:
    cleaned = unescape(str(value or "")).replace(",", "").replace("%", "").strip()
    cleaned = cleaned.replace("▲", "").replace("▼", "").replace("△", "").replace("▽", "")
    cleaned = cleaned.replace("−", "-")
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


def parse_all_stocks(market_payload: dict[str, Any]) -> list[dict[str, Any]]:
    import app

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
            "technicalAnalysis": app.build_intraday_technical_analysis(
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
    import app

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
            "technicalAnalysis": app.build_intraday_technical_analysis(
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
    import app

    index_table = find_table_by_title(market_payload, "價格指數")
    rows: dict[str, list[str]] = {}
    for row in index_table.get("data", []):
        if not row:
            continue
        canonical = app.resolve_sector_key(str(row[0]))
        if canonical:
            rows[canonical] = row

    activity_rows: dict[str, dict[str, Any]] = {}
    if activities_payload:
        for name, item in parse_index_activities(activities_payload).items():
            canonical = app.resolve_sector_key(name)
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
    intraday_candles = app.build_intraday_index_candles(intraday_payload, TARGET_INDEX_NAMES) if intraday_payload else {}
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
                "technicalAnalysis": app.build_index_technical_analysis(
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


def merge_trade_counts(  # DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
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
    import app

    try:
        industry_map = fetch_twse_listed_industry_map()
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.warning("TWSE industry enrichment unavailable: %s", exc)
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


def sector_aliases(key: str) -> list[str]:  # DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
    if key == "發行量加權股價指數":
        return ["發行量加權股價指數"]
    for item in LISTED_SECTOR_INDEX_SPECS:
        if item["key"] == key:
            return [key, *item.get("aliases", [])]
    return [key]


def weighted_index_history_is_usable(series: list[dict[str, Any]], latest_market_date: str) -> bool:
    import app

    if len(series) < min(app.WEIGHTED_INDEX_HISTORY_TRADING_DAYS, 360):
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
    import app

    latest_iso = datetime.strptime(market_date, "%Y%m%d").strftime("%Y-%m-%d")
    try:
        close_value = parse_index_close_values(
            market_payload,
            ["發行量加權股價指數"],
        ).get("發行量加權股價指數")
    except Exception:  # noqa: BLE001
        app.LOGGER.warning("Weighted index close table unavailable for date=%s", market_date)
        close_value = None
    candles = (
        app.build_intraday_index_candles(intraday_payload, ["發行量加權股價指數"], 5)
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
    return updated[-app.WEIGHTED_INDEX_HISTORY_TRADING_DAYS:]


def sync_yahoo_quotes(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:  # DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
    import app

    tpex_indices = [index for index, stock in enumerate(stocks) if stock.get("market") == "TPEx"]
    if not tpex_indices:
        return stocks

    synced = list(stocks)
    with ThreadPoolExecutor(max_workers=min(6, len(tpex_indices))) as executor:
        futures = {executor.submit(app.apply_yahoo_quote, stocks[index]): index for index in tpex_indices}
        for future in as_completed(futures):
            index = futures[future]
            try:
                synced[index] = future.result()
            except Exception as exc:  # noqa: BLE001
                app.LOGGER.debug(
                    "Yahoo quote sync failed for index=%s code=%s; using original stock",
                    index,
                    stocks[index].get("code"),
                    exc_info=exc,
                )
                synced[index] = stocks[index]
    return synced


def find_stock_by_query(query: str, stocks: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    keyword = query.strip().lower()
    if not keyword:
        return []

    exact_code: list[dict[str, Any]] = []
    prefix_code: list[dict[str, Any]] = []
    partial_code: list[dict[str, Any]] = []
    prefix_name: list[dict[str, Any]] = []
    name_matches: list[dict[str, Any]] = []

    for stock in stocks if isinstance(stocks, list) else []:
        if not isinstance(stock, dict) or not stock.get("code") or not stock.get("name"):
            continue
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
        item_key = (str(item.get("market", "")), str(item.get("code", "")))
        if item_key in seen:
            continue
        seen.add(item_key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def refresh_tpex_cache() -> None:
    import app

    quotes, quote_date = fetch_tpex_mainboard_quotes()
    try:
        yahoo_etfs = fetch_yahoo_tpex_etfs()
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.debug(
            "Yahoo TPEx ETF fetch failed; using empty ETF mapping",
            exc_info=exc,
        )
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
        history_series_by_index = app.build_sector_history_series(existing_market_date or quote_date, TARGET_INDEX_NAMES)
    benchmark_day_series = history_series_by_index.get("發行量加權股價指數", [])

    try:
        tpex_mainboard_highlight, yahoo_tpex_otc_date = app.build_yahoo_class_quote_cards(YAHOO_TPEX_OTC_CLASS_URL, "上櫃", limit=6)
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.debug(
            "Yahoo OTC class cards unavailable; using empty highlight fallback",
            exc_info=exc,
        )
        tpex_mainboard_highlight = []
        yahoo_tpex_otc_date = None
    try:
        tpex_esb_highlight, yahoo_tpex_emerging_date = app.build_yahoo_class_quote_cards(YAHOO_TPEX_EMERGING_CLASS_URL, "興櫃", limit=6)
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.debug(
            "Yahoo emerging class cards unavailable; using empty highlight fallback",
            exc_info=exc,
        )
        tpex_esb_highlight = []
        yahoo_tpex_emerging_date = None
    if not tpex_mainboard_highlight:
        tpex_mainboard_highlight = app.build_summary_cards_from_payload(
            fetch_json(app.build_tpex_openapi_url("tpex_mainborad_highlight")),
            "上櫃",
            limit=6,
        )
    if not tpex_esb_highlight:
        tpex_esb_highlight = app.build_summary_cards_from_payload(
            fetch_json(app.build_tpex_openapi_url("tpex_esb_highlight")),
            "興櫃",
            limit=6,
        )
    tpex_mainboard_highlight = app.build_yahoo_summary_series(tpex_mainboard_highlight, benchmark_day_series)
    tpex_esb_highlight = app.build_yahoo_summary_series(tpex_esb_highlight, benchmark_day_series)

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


def site_data_has_complete_sector_payload(site_data: dict[str, Any] | None) -> bool:  # DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
    import app

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
        and weighted_history_count >= min(app.WEIGHTED_INDEX_HISTORY_TRADING_DAYS, 360)
        and complete_sector_histories >= 10
        and len(international) >= 18
        and len(volatility.get("series") or []) >= 20
    )


def site_data_recent_enough(site_data: dict[str, Any] | None, max_age_seconds: int = 1800) -> bool:  # DEADCODE-CANDIDATE (confirmed zero callers 2026-07-19)
    import app

    cached_at = str((site_data or {}).get("cachedAt") or "")
    if not cached_at:
        return False
    try:
        cached_dt = datetime.strptime(cached_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=app.TZ)
    except ValueError:
        return False
    return (app.taipei_now() - cached_dt).total_seconds() <= max_age_seconds


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


def find_derivative_spec(category: str, symbol: str) -> dict[str, Any] | None:
    import app

    clean_symbol = str(symbol or "").strip().upper()
    for item in GLOBAL_MARKET_CATEGORIES.get(category, {}).get("items", []):
        if str(item.get("symbol") or "").strip().upper() == clean_symbol:
            return app.enrich_global_market_spec(item, category)
    return None
