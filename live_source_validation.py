from __future__ import annotations

import json
import os
from datetime import timedelta

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
import app


def recent_taipei_dates(lookback_days: int = 14) -> list[str]:
    today = app.taipei_now().date()
    return [(today - timedelta(days=offset)).strftime("%Y%m%d") for offset in range(lookback_days + 1)]


def validate_taifex() -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    for trade_date in recent_taipei_dates():
        oi = app.fetch_taifex_futures_open_interest(trade_date, "MTX")
        chain = app.fetch_taifex_txo_option_chain(market_date=trade_date)
        errors = [value for value in (oi.get("error"), chain.get("error")) if value]
        if not errors and chain.get("chain"):
            return {
                "source": "TAIFEX",
                "ok": True,
                "trade_date": trade_date,
                "mtx_open_interest": oi.get("openInterest"),
                "txo_chain_rows": len(chain.get("chain") or []),
                "errors": [],
            }
        attempts.append({"trade_date": trade_date, "errors": errors})
    return {
        "source": "TAIFEX",
        "ok": False,
        "attempts": attempts,
    }


def validate_twse() -> dict[str, object]:
    payload, market_date = app.find_latest_dataset(
        app.build_market_url,
        validator=app.market_payload_has_complete_index_tables,
    )
    tables = payload.get("tables") or [] if isinstance(payload, dict) else []
    if not tables:
        return {
            "source": "TWSE MI_INDEX",
            "ok": False,
            "status": payload.get("stat") if isinstance(payload, dict) else "unexpected response",
            "reason": "Source returned no market tables for the requested trade date.",
        }
    overview = app.parse_market_overview(payload)
    stocks = app.parse_all_stocks(payload)
    return {
        "source": "TWSE MI_INDEX",
        "ok": bool(overview and stocks),
        "trade_date": market_date,
        "overview_rows": len(overview),
        "stock_rows": len(stocks),
    }


def main() -> None:
    results = []
    for validator in (validate_taifex, validate_twse):
        try:
            results.append(validator())
        except Exception as exc:  # noqa: BLE001
            results.append({"source": validator.__name__, "ok": False, "error": repr(exc)})
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if not all(result.get("ok") is True for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
