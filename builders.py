"""Response/data-shaping `build_*` functions extracted from app.py (TD-01
slice 4), starting with 7 small, dependency-free leaf builders (batch 0),
extended with the TAIFEX/options-chain + derivatives-misc cluster (batch 1,
19 functions), and the Yahoo/sector + technical-analysis cluster (batch 2,
12 functions).

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
two independent full-repo searches) move here unmodified rather than being
deleted, per the standing behavior-preserving-refactor rule - each is marked
with a `# DEADCODE-CANDIDATE` comment for a future TD-05 registry cleanup:
`build_stock_search_url`, `build_site_data_view`, and (added in batch 1)
`build_yahoo_options_chain`.

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
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request

from cache import (
    CACHE_FLIGHT_WAIT_SECONDS,
    PENNY_SECTOR_RECOMMENDATION_CACHE_SECONDS,
    cache_data,
    cache_lock,
    claim_cache_flight,
    finish_cache_flight,
    penny_sector_recommendation_cache,
    penny_sector_recommendation_lock,
    read_memory_cache,
    write_memory_cache,
)
from derivatives.analytics import enrich_futures_ai_decision, enrich_option_ai_decision
from derivatives.futures import build_source_pending_market_item
from fetchers import (
    TAIFEX_FUTURES_DAILY_OPENAPI_URL,
    barchart_options_headers,
    build_index_activity_url,
    build_market_url,
    build_stock_institutions_url,
    build_yahoo_chart_series,
    dataset_has_rows,
    detect_tone,
    extract_balanced_segment,
    extract_visible_text_lines,
    fetch_barchart_options_context,
    fetch_json,
    fetch_stock_institutions_payload_near,
    fetch_taifex_institution_detail_rows,
    fetch_taifex_latest_futures_market_snapshot,
    fetch_taifex_openapi_list,
    fetch_taiwan_option_spot_snapshot,
    fetch_text,
    fetch_txo_option_chain,
    fetch_twse_listed_industry_map,
    fetch_yahoo_class_quote_pages,
    fetch_yahoo_options_payload,
    fetch_yahoo_sector_catalog,
    fetch_yahoo_symbol_chart,
    fetch_yahoo_taiwan_future_quote,
    format_percent,
    format_signed,
    format_whole_number,
    is_etf_stock,
    normalize_taifex_date_text,
    normalize_us_symbol_for_yahoo,
    parse_float,
    parse_public_options_number,
    parse_taifex_market_number,
    shift_month,
)
from market_config import (
    CBOE_OPTIONS_BASE,
    SECTOR_INDEX_LOOKUP,
    TAIFEX_OPTIONS_DAILY_URL,
    TAIFEX_OPTIONS_PC_RATIO_URL,
    TWSE_BASE,
    YAHOO_CONCEPT_CLASS_URL,
    YAHOO_ELECTRONIC_CLASS_URL,
    YAHOO_GROUP_CLASS_URL,
    YAHOO_LISTED_CLASS_URL,
    YAHOO_TPEX_EMERGING_CLASS_URL,
    YAHOO_TPEX_OTC_CLASS_URL,
)


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
    import app

    clean_symbol = str(symbol or "").strip().upper()
    group = app.YAHOO_TW_FUTURE_TECHNICAL_GROUPS.get(clean_symbol)
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
    import app

    clean = str(value or app.TAIWAN_OPTION_DEFAULT_PRODUCT).strip().upper()
    return clean if clean in app.TAIWAN_OPTION_PRODUCTS else app.TAIWAN_OPTION_DEFAULT_PRODUCT


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

    product = app.get_taiwan_option_product(underlying)
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
            for key, item in app.TAIWAN_OPTION_PRODUCTS.items()
        ],
    }


def build_yahoo_txo_option_payload(
    rows: list[dict[str, Any]],
    trade_date: str,
    expiry_code: str,
    spot_snapshot: dict[str, Any],
    underlying: str | None = "TXO",
) -> dict[str, Any]:
    import app

    product = app.get_taiwan_option_product(underlying)
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
            for key, item in app.TAIWAN_OPTION_PRODUCTS.items()
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


def build_taifex_open_interest_item(spec: dict[str, Any]) -> dict[str, Any]:
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
        snapshot = fetch_taifex_latest_futures_market_snapshot(commodity)
    except Exception as exc:  # noqa: BLE001
        app.LOGGER.exception("TAIFEX futures daily market item fetch failed for symbol=%s", symbol, exc_info=exc)
        snapshot = None
    yahoo_quote = None
    try:
        yahoo_quote = fetch_yahoo_taiwan_future_quote(symbol)
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
        "quoteSourceUrl": app.YAHOO_TW_FUTURE_UNCOVERED_URL if yahoo_quote else "",
        "yahooFutureCode": (yahoo_quote or {}).get("yahooCode") or technical_profile.get("primaryCode") or "",
        "technicalAnalysisUrl": technical_profile.get("primaryUrl") or "",
        "technicalAnalysisSource": technical_profile.get("source") or "",
        "technicalContracts": technical_profile.get("contracts") or [],
        "source": "Yahoo 股市即時期指報價 / TAIFEX 官方期貨日報" if use_yahoo_quote else "TAIFEX 官方期貨日報",
        "dataSource": "Yahoo 股市即時期指報價 / TAIFEX 官方期貨日報" if use_yahoo_quote else "TAIFEX 官方期貨日報",
        "sourceNote": " ".join(source_note_parts),
        "sourceLink": app.YAHOO_TW_FUTURE_UNCOVERED_URL if use_yahoo_quote else (snapshot or {}).get("sourceLink") or base_item["sourceUrl"],
        "taifexSourceLink": (snapshot or {}).get("sourceLink") or TAIFEX_FUTURES_DAILY_OPENAPI_URL,
        "series": series,
    }


def build_txo_option_market_item(spec: dict[str, Any]) -> dict[str, Any]:
    import app

    symbol = normalize_taiwan_option_underlying(str(spec.get("taifexCommodity") or spec.get("symbol") or "TXO"))
    product = app.get_taiwan_option_product(symbol)

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
        app.LOGGER.exception("%s option market item fetch failed", symbol, exc_info=exc)
        return {**base_item, "error": app.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE}
    if chain.get("error"):
        return {**base_item, "error": str(chain.get("error") or app.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE)}

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
TAIFEX_STOCK_DERIVATIVE_AGGREGATE_CACHE_SECONDS = 15 * 60


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
TAIFEX_UNDERLYING_LIST_CACHE_SECONDS = 6 * 60 * 60


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


def build_institution_payload_live(product: str, source_url: str) -> dict[str, Any] | None:
    import app

    try:
        rows = fetch_taifex_institution_detail_rows(product)
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


US_OPTIONS_CHAIN_CACHE_SECONDS = 5 * 60
YAHOO_OPTIONS_CHAIN_CACHE_SECONDS = 5 * 60
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


# DEADCODE-CANDIDATE (confirmed zero callers 2026-07-18)
def build_yahoo_options_chain(symbol: str, expiration: str | None = None) -> dict[str, Any]:
    import app

    clean_symbol = normalize_us_symbol_for_yahoo(re.sub(r"[^A-Za-z0-9=.^_-]", "", symbol or "").upper())
    if not clean_symbol:
        return {"error": "Invalid option underlying symbol."}
    cache_key = f"yahoo:{clean_symbol}:{expiration or ''}"
    if not app.global_market_refresh_requested():
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
    write_memory_cache("us_options_chains", cache_key, copy.deepcopy(result_payload))
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
SECTOR_FUND_FLOW_CACHE_SECONDS = 10 * 60


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
    import app

    try:
        index_table = app.find_table_by_field(payload, "指數")
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
    import app

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
            activities = app.parse_index_activities(activity_payload) if dataset_has_rows(activity_payload) else {}
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
        app.parse_market_statistics(payload),
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
