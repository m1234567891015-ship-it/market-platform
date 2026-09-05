"""Taiwan derivatives (TAIFEX futures/options) routes extracted from app.py
(TD-01 slice 5, Phase B, batch B3) - the 4th and LAST of 4 domain Blueprint
modules. Holds 16 routes (index/futures/options/institution/basis/news/
ai-analysis/pcr/maxpain), one single contiguous block (originally
app.py:810-1258 for the routes plus their one exclusive helper, unlike the
two-region splits batches B1/B2 hit for the other route domains).
Registered on the main `app` object via `app.register_blueprint(bp)` - see
`routes_system.py`'s docstring (batch B0) for the endpoint-naming/
security-hook safety analysis that applies identically here. This is the
final route-extraction batch of TD-01 slice 5: after this commit, app.py has
zero remaining `@app.route` decorators.

`derivative_request_limit` is EXCLUSIVE (grep-confirmed zero callers
anywhere outside this batch's 4 call sites) and moves with its callers.
`find_derivative_spec` already lives in `parsers.py` (moved in an earlier
batch of this slice) - this module just imports it normally, nothing to
physically move.

Explicitly NOT moved despite sitting immediately adjacent: the 9-function
TAIFEX/Yahoo option-chain-open-interest-supplementing cluster
(`infer_yahoo_taiwan_future_symbol_from_code` through
`supplement_taifex_option_payload_with_yahoo_oi`) - grep-confirmed that none
of these 16 routes call any function in that cluster directly (they call
`fetch_txo_option_chain`, which internally reaches the cluster via its own
deferred `import app` inside fetchers.py); `apply_yahoo_quote` and
`global_market_refresh_requested` - both SHARED with other already-extracted
modules (`parsers.py`, `builders.py` respectively), already documented as
STAYS names in this slice's earlier batches. `PUBLIC_TAIFEX_OPEN_INTEREST_ERROR_MESSAGE`
(app.py:475) is dead code (zero callers anywhere in the repo) - left alone,
out of scope for a routes-only batch.

`DERIVATIVES_STORE` is a module-level singleton that must stay defined in
app.py (also reached by `builders.py` via deferred `import app` and by
`security.py` via a deferred `from app import DERIVATIVES_STORE`) - reached
here the same way. `LOGGER`/`TZ`/`api_success_payload`/`api_error_payload`/
`api_exception_response`/`PUBLIC_DATA_SOURCE_ERROR_MESSAGE` are app.py-local
shared utilities reached via a deferred `import app` inside each function
that needs them, same one-directional-dependency reason as every other
route module this slice. Everything else (`build_*`/`fetch_*`/parser names/
the already-modular `derivatives.*` sub-package/market_config constants/
`is_authorized_derivatives_admin`) is safe to import directly at module
level - none of those modules import route modules back.

Test-patch fixes (8, all the established bare-name-resolution lesson from
every prior batch this slice): `build_global_market_payload`,
`fetch_taifex_futures_price_candles`, `build_global_market_item`,
`fetch_yahoo_us_symbol_news`, `build_institution_payload_live`,
`fetch_taiex_spot_snapshot` were patched as `app.X` across several tests but
are now called as bare names resolved via this module's own imports -
repointed to `@patch.object(routes_derivatives, "X", ...)`.
`@patch.object(fetchers, "fetch_taifex_txo_option_chain", ...)` and the
`app.supplement_taifex_option_payload_with_yahoo_oi`/
`app.fetch_yahoo_txo_option_chain` references in the OI-supplement cluster's
own test needed no changes (neither is one of this batch's 16 routes).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Blueprint, jsonify, request

from builders import (
    build_derivative_candles,
    build_futures_ai_analysis,
    build_global_market_item,
    build_global_market_payload,
    build_institution_payload_live,
    normalize_futures_yahoo_uncovered_links,
    normalize_taiwan_option_underlying,
)
from derivatives.ai import build_unavailable_ai_analysis as build_derivatives_unavailable_ai_analysis
from derivatives.analytics import build_basis_payload, positive_number
from derivatives.catalog import TAIWAN_FUTURES_V1, TAIWAN_OPTIONS_V1, apply_taifex_defaults, v1_product_status
from derivatives.institution import (
    build_institution_payload_from_rows,
    build_pending_institution_payload,
    normalize_institution_row,
    parse_institution_csv,
)
from derivatives.options import build_unavailable_option_chain as build_derivatives_unavailable_option_chain
from fetchers import (
    TAIFEX_INSTITUTION_FUTURES_DETAIL_OPENAPI_URL,
    TAIFEX_INSTITUTION_OPTIONS_DETAIL_OPENAPI_URL,
    fetch_taiex_spot_snapshot,
    fetch_taifex_futures_price_candles,
    fetch_taifex_futures_technical_candles,
    fetch_txo_option_chain,
    fetch_yahoo_us_symbol_news,
    parse_float,
)
from market_config import TAIFEX_FUTURES_DAILY_URL, TAIFEX_OPTIONS_DAILY_URL
from parsers import TAIWAN_OPTION_PRODUCTS, find_derivative_spec, normalize_taiwan_option_source
from security import is_authorized_derivatives_admin


bp = Blueprint("derivatives", __name__)


def derivative_request_limit(default: int = 24, maximum: int = 100) -> int:
    raw_limit = str(request.args.get("limit") or default).strip().lower()
    if raw_limit in {"all", "full", "0"}:
        return maximum
    try:
        requested = int(raw_limit)
    except ValueError:
        requested = default
    return min(max(requested, 1), maximum)


@bp.route("/api/index")
def api_derivatives_index():
    import app

    try:
        futures = build_global_market_payload("futures", min(12, derivative_request_limit(12, 24)))
        options = build_global_market_payload("options", min(12, derivative_request_limit(12, 24)))
        chain = options.get("taiwanOptionChain") or {}
        return jsonify(app.api_success_payload({
            "futures": futures.get("summary") or {},
            "options": options.get("summary") or {},
            "taiwanOption": {
                "tradeDate": chain.get("tradeDate"),
                "expiry": chain.get("selectedExpiry"),
                "summary": chain.get("summary") or {},
                "analysis": chain.get("analysis") or {},
            },
            "sources": {"futures": futures.get("source"), "options": options.get("source")},
        }))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/derivatives/v1-status")
def api_derivatives_v1_status():
    import app

    futures_items = [apply_taifex_defaults(item, TAIFEX_FUTURES_DAILY_URL, TAIFEX_OPTIONS_DAILY_URL) for item in TAIWAN_FUTURES_V1]
    option_items = [apply_taifex_defaults(item, TAIFEX_FUTURES_DAILY_URL, TAIFEX_OPTIONS_DAILY_URL) for item in TAIWAN_OPTIONS_V1]
    institutional_count = len(app.DERIVATIVES_STORE.institutional_positions(str(request.args.get("product") or "TX").strip().upper(), 200))
    return jsonify(app.api_success_payload({
        "version": "V1.0",
        "scope": "domestic_derivatives",
        "futures": futures_items,
        "options": option_items,
        "coverage": v1_product_status(futures_items, option_items),
        "institutionImport": {
            "endpoint": "/api/institution/import",
            "formats": ["JSON rows", "CSV"],
            "requiredFields": ["institution", "product_code", "trade_date"],
            "optionalFields": ["long_contracts", "short_contracts", "net_contracts"],
            "currentProductRows": institutional_count,
        },
        "aiScoreFormula": {
            "marketScore": "Options: PCR, Volume PCR, Max Pain gap, OI wall; Futures: price change. All scores clamped 0-100.",
            "riskScore": "Options: PCR imbalance, Volume PCR imbalance, Max Pain gap and OI wall break; Futures: downside momentum and OI availability.",
            "confidenceScore": "Count of available evidence layers plus chain/candle depth bonus.",
            "sourcePendingPenalty": "Missing evidence lowers confidence and raises data-risk messaging; no fake data is generated.",
        },
        "basis": {
            "endpoint": "/api/basis?future=TX&spot=TAIEX",
            "formula": "basis = futurePrice - spotPrice; basisPct = basis / spotPrice * 100",
        },
    }))


@bp.route("/api/futures")
def api_futures():
    import app

    category_filter = str(request.args.get("category") or "").strip().lower()
    sort_key = str(request.args.get("sort") or "").strip().lower()
    try:
        payload = build_global_market_payload("futures", derivative_request_limit())
        items = [normalize_futures_yahoo_uncovered_links(item) for item in list(payload.get("items") or [])]
        if category_filter:
            items = [item for item in items if category_filter in f"{item.get('type', '')} {item.get('group', '')}".lower()]
        if sort_key in {"pct", "change", "volume", "open_interest"}:
            field = "openInterest" if sort_key == "open_interest" else sort_key
            items.sort(key=lambda item: parse_float(str(item.get(field) or "")) or float("-inf"), reverse=True)
        return jsonify(app.api_success_payload({**payload, "items": items, "count": len(items)}))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/futures/<symbol>")
def api_future_detail(symbol: str):
    import app

    spec = find_derivative_spec("futures", symbol)
    if not spec:
        return jsonify(app.api_error_payload("INVALID_SYMBOL", "商品代碼不存在")), 404
    try:
        item = build_global_market_item(spec)
        if item.get("error"):
            return jsonify(app.api_error_payload("EMPTY_RESULT", str(item.get("error")))), 200
        return jsonify(app.api_success_payload(item))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/futures/<symbol>/candles")
def api_future_candles(symbol: str):
    import app

    interval = str(request.args.get("interval") or "day").strip().lower()
    if interval not in {"day", "week", "month", "all"}:
        return jsonify(app.api_error_payload("INVALID_DATE", "interval 僅支援 day、week、month、all")), 400
    spec = find_derivative_spec("futures", symbol)
    if not spec:
        return jsonify(app.api_error_payload("INVALID_SYMBOL", "商品代碼不存在")), 404
    try:
        if spec.get("dataProvider") in {"taifex_tx_open_interest", "taifex_txo_open_interest", "taifex_futures_open_interest"}:
            commodity = str(spec.get("taifexCommodity") or spec.get("symbol") or symbol).strip().upper()
            candles = fetch_taifex_futures_price_candles(commodity, max_observations=30)
            if interval not in {"day", "all"}:
                candles = build_derivative_candles({"series": [
                    {
                        "date": row.get("time"),
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "volume": row.get("volume"),
                    }
                    for row in candles
                ]}, interval)
            if not candles:
                fallback_item = build_global_market_item(spec)
                fallback_candles = build_derivative_candles(fallback_item, interval)
                if fallback_candles:
                    return jsonify(app.api_success_payload({
                        "symbol": spec.get("symbol"),
                        "interval": interval,
                        "candles": fallback_candles,
                        "source": fallback_item.get("source") or "期貨商品既有序列",
                    }))
                return jsonify(app.api_error_payload("EMPTY_RESULT", "TAIFEX 官方 K 線資料暫時無法載入")), 200
            return jsonify(app.api_success_payload({"symbol": spec.get("symbol"), "interval": interval, "candles": candles, "source": "TAIFEX 官方期貨每日交易行情"}))
        item = build_global_market_item(spec)
        candles = build_derivative_candles(item, interval)
        if not candles:
            return jsonify(app.api_error_payload("EMPTY_RESULT", str(item.get("error") or "查無 K 線資料"))), 200
        return jsonify(app.api_success_payload({"symbol": item.get("symbol"), "interval": interval, "candles": candles, "source": item.get("source")}))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/options")
def api_options():
    import app

    underlying = str(request.args.get("underlying") or "TXO").strip().upper()
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    if underlying in {"STO", "ETO"}:
        spec = find_derivative_spec("options", underlying)
        if not spec:
            return jsonify(app.api_error_payload("INVALID_SYMBOL", "商品代碼不存在")), 404
        item = build_global_market_item(spec)
        chain_status = "source_pending" if item.get("status") == "source_pending" or item.get("error") else "aggregate_connected"
        return jsonify(app.api_success_payload({
            "underlying": underlying,
            "products": [item],
            "selectedExpiry": None,
            "expirations": [],
            "optionChainSource": {
                "primary": item.get("dataSource") or spec.get("dataSource"),
                "primaryUrl": item.get("sourceLink") or spec.get("sourceUrl"),
                "status": chain_status,
            },
            "message": item.get("dataStatus") or item.get("error") or "TAIFEX 標的選擇權目前僅提供未平倉量／成交量彙總，尚未提供逐履約價選擇權鏈。",
        }))
    if underlying not in TAIWAN_OPTION_PRODUCTS:
        supported = "、".join(TAIWAN_OPTION_PRODUCTS.keys())
        return jsonify(app.api_error_payload("INVALID_SYMBOL", f"目前國內選擇權鏈支援 {supported}；STO/ETO 以彙總資料揭露")), 400
    try:
        payload = build_global_market_payload("options", derivative_request_limit(default=100), option_source=source, option_underlying=underlying)
        chain = payload.get("taiwanOptionChain") or {}
        if chain.get("error"):
            chain = build_derivatives_unavailable_option_chain(str(chain.get("error")), TAIFEX_OPTIONS_DAILY_URL, underlying)
            payload["taiwanOptionChain"] = chain
        return jsonify(app.api_success_payload({
            **payload,
            "underlying": underlying,
            "products": payload.get("items") or [],
            "expirations": chain.get("expirations") or [],
            "selectedExpiry": chain.get("selectedExpiry"),
            "optionChainSource": chain.get("source") or {},
        }))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/open-interest")
def api_open_interest():
    import app

    symbol = str(request.args.get("symbol") or "TXO").strip().upper()
    date = str(request.args.get("date") or "").strip() or None
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        if symbol in TAIWAN_OPTION_PRODUCTS:
            data = fetch_txo_option_chain(market_date=date, source=source, underlying=symbol)
            if data.get("error"):
                return jsonify(app.api_error_payload("EMPTY_RESULT", str(data.get("error")))), 200
            summary = data.get("summary") or {}
            return jsonify(app.api_success_payload({
                "symbol": symbol,
                "tradeDate": data.get("tradeDate"),
                "callOpenInterest": summary.get("callOpenInterest"),
                "putOpenInterest": summary.get("putOpenInterest"),
                "putCallRatio": summary.get("putCallRatio"),
                "distribution": data.get("distribution") or [],
                "source": data.get("source") or {},
            }))
        spec = find_derivative_spec("futures", symbol)
        if not spec or not str(spec.get("dataProvider") or "").startswith("taifex_"):
            return jsonify(app.api_error_payload("INVALID_SYMBOL", "目前僅支援 TAIFEX 期貨或國內官方選擇權鏈")), 400
        item = build_global_market_item(spec)
        if item.get("error"):
            return jsonify(app.api_error_payload("EMPTY_RESULT", str(item.get("error")))), 200
        return jsonify(app.api_success_payload({
            "symbol": symbol,
            "tradeDate": item.get("date"),
            "openInterest": item.get("openInterest"),
            "previousOpenInterest": item.get("previousOpenInterest"),
            "change": item.get("change"),
            "changePct": item.get("pct"),
            "source": item.get("sourceLink") or item.get("sourceUrl"),
        }))
    except ValueError:
        return jsonify(app.api_error_payload("INVALID_DATE", "日期格式需為 YYYYMMDD 或 YYYY-MM-DD")), 400
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/institution")
def api_institutional_position():
    import app

    product = str(request.args.get("product") or "TX").strip().upper()
    rows = app.DERIVATIVES_STORE.institutional_positions(product)
    if rows:
        payload = build_institution_payload_from_rows(product, rows, TAIFEX_FUTURES_DAILY_URL)
    else:
        is_option = product in {"TXO", "STO", "ETO"}
        source_url = TAIFEX_INSTITUTION_OPTIONS_DETAIL_OPENAPI_URL if is_option else TAIFEX_INSTITUTION_FUTURES_DETAIL_OPENAPI_URL
        payload = build_institution_payload_live(product, source_url) or build_pending_institution_payload(product, TAIFEX_FUTURES_DAILY_URL)
    return jsonify(app.api_success_payload(payload))


@bp.route("/api/institution/import", methods=["POST"])
def api_institution_import():
    import app

    if not is_authorized_derivatives_admin():
        return jsonify(app.api_error_payload("ADMIN_AUTH_REQUIRED", "法人資料匯入需提供有效管理金鑰")), 403
    rows: list[dict[str, Any]] = []
    if request.is_json:
        body = request.get_json(silent=True) or {}
        raw_rows = body.get("rows") if isinstance(body, dict) else None
        if isinstance(raw_rows, list):
            rows = [normalize_institution_row(row) for row in raw_rows if isinstance(row, dict)]
        elif isinstance(body, dict) and "csv" in body:
            rows = parse_institution_csv(str(body.get("csv") or ""))
    else:
        rows = parse_institution_csv(request.get_data(as_text=True) or "")
    rows = [row for row in rows if row.get("institution") and row.get("product_code") and row.get("trade_date")]
    if not rows:
        return jsonify(app.api_error_payload("INVALID_PAYLOAD", "請提供 rows JSON 或 CSV，欄位需含 institution/product_code/trade_date")), 400
    inserted = app.DERIVATIVES_STORE.record_institutional_positions(rows)
    product = str(rows[0].get("product_code") or "").upper()
    payload = build_institution_payload_from_rows(product, app.DERIVATIVES_STORE.institutional_positions(product), TAIFEX_FUTURES_DAILY_URL)
    return jsonify(app.api_success_payload({"inserted": inserted, "product": product, "institution": payload}))


@bp.route("/api/basis")
def api_basis():
    import app

    future_symbol = str(request.args.get("future") or "TX").strip().upper()
    spot_symbol = str(request.args.get("spot") or "TAIEX").strip().upper()
    if spot_symbol not in {"TAIEX", "TWII", "加權指數"}:
        return jsonify(app.api_error_payload("INVALID_SYMBOL", "spot 目前支援 TAIEX 台灣加權指數")), 400
    spec = find_derivative_spec("futures", future_symbol)
    if not spec:
        return jsonify(app.api_error_payload("INVALID_SYMBOL", "期貨商品代碼不存在")), 404
    try:
        try:
            future_item = build_global_market_item(spec)
        except Exception as exc:  # noqa: BLE001
            app.LOGGER.warning("Basis future source failed for symbol=%s: %s", future_symbol, exc)
            future_item = {"symbol": future_symbol, "error": "期貨資料來源暫不可用"}
        try:
            spot_snapshot = fetch_taiex_spot_snapshot() or {}
        except Exception as exc:  # noqa: BLE001
            app.LOGGER.warning("Basis spot source failed for symbol=%s: %s", spot_symbol, exc)
            spot_snapshot = {"source": "Yahoo Finance", "error": "台灣加權指數現貨資料來源暫不可用"}
        if not isinstance(future_item, dict):
            future_item = {"symbol": future_symbol, "error": "期貨資料來源回應格式無效"}
        if not isinstance(spot_snapshot, dict):
            spot_snapshot = {"source": "Yahoo Finance", "error": "台灣加權指數現貨資料來源回應格式無效"}
        history = []
        future_series = future_item.get("series") or []
        spot_value = positive_number(spot_snapshot.get("value"), spot_snapshot.get("close"))
        for row in future_series[-20:]:
            if not isinstance(row, dict):
                continue
            future_close = positive_number(row.get("close"))
            basis = future_close - spot_value if future_close is not None and spot_value is not None else None
            history.append({
                "date": row.get("date") or row.get("time"),
                "futurePrice": future_close,
                "spotPrice": spot_value,
                "basis": basis,
                "basisPct": (basis / spot_value * 100) if basis is not None and spot_value is not None else None,
            })
        payload = build_basis_payload(future_item, spot_snapshot, history)
        return jsonify(app.api_success_payload(payload))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/news")
def api_derivatives_news():
    import app

    category = str(request.args.get("category") or "derivatives").strip().lower()
    symbol = str(request.args.get("symbol") or "^VIX").strip().upper()
    limit = derivative_request_limit(8, 20)
    try:
        items = fetch_yahoo_us_symbol_news(symbol, limit)
        if not items:
            return jsonify(app.api_error_payload("EMPTY_RESULT", "目前查無市場新聞資料")), 200
        for item in items:
            item.setdefault("summary", "公開新聞標題與來源，請開啟連結查看完整內容。")
        app.DERIVATIVES_STORE.record_news(category, items)
        return jsonify(app.api_success_payload({"category": category, "symbol": symbol, "items": items, "count": len(items)}))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/ai-analysis")
def api_derivatives_ai_analysis():
    import app

    target = str(request.args.get("target") or "TXO").strip().upper()
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        if target in TAIWAN_OPTION_PRODUCTS:
            data = fetch_txo_option_chain(expiry=str(request.args.get("expiry") or "").strip() or None, source=source, underlying=target)
            if data.get("error"):
                analysis = build_derivatives_unavailable_ai_analysis(target, str(data.get("error")))
                return jsonify(app.api_success_payload(analysis))
            analysis = data.get("analysis") or {}
        else:
            spec = find_derivative_spec("futures", target)
            if not spec:
                return jsonify(app.api_error_payload("INVALID_SYMBOL", "商品代碼不存在")), 404
            item = build_global_market_item(spec)
            if item.get("error"):
                analysis = build_derivatives_unavailable_ai_analysis(target, str(item.get("error")))
                return jsonify(app.api_success_payload(analysis))
            analysis = build_futures_ai_analysis(item)
        app.DERIVATIVES_STORE.record_ai_report(target, analysis, datetime.now(app.TZ).isoformat())
        return jsonify(app.api_success_payload(analysis))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/futures/<symbol>/technical-candles")
def api_future_technical_candles(symbol: str):
    import app

    interval = str(request.args.get("interval") or "day").strip().lower()
    if interval not in {"day", "week", "month", "all"}:
        return jsonify(app.api_error_payload("INVALID_DATE", "interval 只能是 day、week、month 或 all")), 400
    spec = find_derivative_spec("futures", symbol)
    if not spec:
        return jsonify(app.api_error_payload("INVALID_SYMBOL", "期貨商品不存在")), 404
    commodity = str(spec.get("taifexCommodity") or spec.get("symbol") or symbol).strip().upper()
    code = str(request.args.get("code") or "").strip().upper()
    try:
        payload = fetch_taifex_futures_technical_candles(commodity, code=code, interval=interval)
        if payload.get("error"):
            return jsonify(app.api_error_payload("EMPTY_RESULT", str(payload.get("error")))), 200
        if not payload.get("candles"):
            contract = payload.get("contract") or {}
            label = contract.get("label") or payload.get("code") or code or commodity
            month = payload.get("contractMonth") or "主力連續"
            return jsonify(app.api_error_payload(
                "EMPTY_RESULT",
                f"{commodity} {label}（{month}）目前沒有足夠的 TAIFEX K 線資料。",
            )), 200
        return jsonify(app.api_success_payload(payload))
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)


@bp.route("/api/options/chain")
def api_options_chain():
    import app

    underlying = normalize_taiwan_option_underlying(str(request.args.get("underlying") or "TXO"))
    expiry = str(request.args.get("expiry") or "").strip() or None
    date = str(request.args.get("date") or "").strip() or None
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        data = fetch_txo_option_chain(expiry=expiry, market_date=date, source=source, underlying=underlying)
    except ValueError:
        return jsonify(app.api_error_payload("INVALID_DATE", "日期格式需為 YYYYMMDD 或 YYYY-MM-DD")), 400
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)
    if data.get("error"):
        return jsonify(app.api_success_payload(build_derivatives_unavailable_option_chain(str(data.get("error")), TAIFEX_OPTIONS_DAILY_URL, underlying)))
    app.DERIVATIVES_STORE.record_option_chain(data, datetime.now(app.TZ).isoformat())
    return jsonify(app.api_success_payload(data))


@bp.route("/api/pcr")
def api_options_pcr():
    import app

    underlying = normalize_taiwan_option_underlying(str(request.args.get("underlying") or "TXO"))
    expiry = str(request.args.get("expiry") or "").strip() or None
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        data = fetch_txo_option_chain(expiry=expiry, market_date=str(request.args.get("date") or "").strip() or None, source=source, underlying=underlying)
    except ValueError:
        return jsonify(app.api_error_payload("INVALID_DATE", "日期格式需為 YYYYMMDD 或 YYYY-MM-DD")), 400
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)
    if data.get("error"):
        data = build_derivatives_unavailable_option_chain(str(data.get("error")), TAIFEX_OPTIONS_DAILY_URL, underlying)
        summary = data.get("summary") or {}
        return jsonify(app.api_success_payload({
            "underlying": underlying,
            "expiry": None,
            "tradeDate": None,
            "putCallRatio": summary.get("putCallRatio"),
            "volumePutCallRatio": summary.get("volumePutCallRatio"),
            "putOpenInterest": summary.get("putOpenInterest"),
            "callOpenInterest": summary.get("callOpenInterest"),
            "history": app.DERIVATIVES_STORE.option_pcr_history(underlying),
            "source": (data.get("source") or {}).get("primary"),
            "status": data.get("status"),
            "message": data.get("message"),
        }))
    app.DERIVATIVES_STORE.record_option_chain(data, datetime.now(app.TZ).isoformat())
    summary = data.get("summary") or {}
    return jsonify(app.api_success_payload({
        "underlying": underlying,
        "expiry": data.get("selectedExpiry"),
        "tradeDate": data.get("tradeDate"),
        "putCallRatio": summary.get("putCallRatio"),
        "volumePutCallRatio": summary.get("volumePutCallRatio"),
        "putOpenInterest": summary.get("putOpenInterest"),
        "callOpenInterest": summary.get("callOpenInterest"),
        "history": app.DERIVATIVES_STORE.option_pcr_history(underlying),
        "source": (data.get("source") or {}).get("primary"),
    }))


@bp.route("/api/maxpain")
def api_options_maxpain():
    import app

    underlying = normalize_taiwan_option_underlying(str(request.args.get("underlying") or "TXO"))
    expiry = str(request.args.get("expiry") or "").strip() or None
    source = normalize_taiwan_option_source(str(request.args.get("source") or request.args.get("optionSource") or "auto"))
    try:
        data = fetch_txo_option_chain(expiry=expiry, market_date=str(request.args.get("date") or "").strip() or None, source=source, underlying=underlying)
    except ValueError:
        return jsonify(app.api_error_payload("INVALID_DATE", "日期格式需為 YYYYMMDD 或 YYYY-MM-DD")), 400
    except Exception as exc:  # noqa: BLE001
        return app.api_exception_response("DATA_SOURCE_ERROR", app.PUBLIC_DATA_SOURCE_ERROR_MESSAGE, exc, 502)
    if data.get("error"):
        data = build_derivatives_unavailable_option_chain(str(data.get("error")), TAIFEX_OPTIONS_DAILY_URL, underlying)
        summary = data.get("summary") or {}
        analysis = data.get("analysis") or {}
        return jsonify(app.api_success_payload({
            "underlying": underlying,
            "expiry": None,
            "tradeDate": None,
            "maxPain": summary.get("maxPain"),
            "maxPainLoss": summary.get("maxPainLoss"),
            "supportLevel": analysis.get("supportLevel"),
            "resistanceLevel": analysis.get("resistanceLevel"),
            "source": (data.get("source") or {}).get("primary"),
            "status": data.get("status"),
            "message": data.get("message"),
        }))
    app.DERIVATIVES_STORE.record_option_chain(data, datetime.now(app.TZ).isoformat())
    summary = data.get("summary") or {}
    analysis = data.get("analysis") or {}
    return jsonify(app.api_success_payload({
        "underlying": underlying,
        "expiry": data.get("selectedExpiry"),
        "tradeDate": data.get("tradeDate"),
        "maxPain": summary.get("maxPain"),
        "maxPainLoss": summary.get("maxPainLoss"),
        "supportLevel": analysis.get("supportLevel"),
        "resistanceLevel": analysis.get("resistanceLevel"),
        "source": (data.get("source") or {}).get("primary"),
    }))
