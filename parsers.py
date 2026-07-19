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
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from fetchers import TAIFEX_FUTURES_DATA_DOWNLOAD_URL


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
