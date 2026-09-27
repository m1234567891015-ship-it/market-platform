from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import app
import builders
import fetchers
import parsers
from derivatives_store import DerivativesStore


def _yahoo_lines(date_line: str = "") -> list[str]:
    lines = [date_line] if date_line else []
    lines.extend([
        "台指期",
        "WTX&",
        "--", "--", "22000", "+10", "+0.05%", "100", "21990", "22010", "21980",
        "--", "21990", "1000", "09:00",
    ])
    return lines


class P0AMarketTimeIntegrityTests(unittest.TestCase):
    def test_yahoo_without_market_date_stays_unknown(self) -> None:
        with patch.object(parsers, "extract_visible_text_lines", return_value=_yahoo_lines()):
            quote = parsers.parse_yahoo_taiwan_future_quotes("fixture")["TX"]

        self.assertEqual(quote["date"], "")
        self.assertIsNone(quote["marketAsOf"])

    def test_yahoo_explicit_market_date_is_preserved(self) -> None:
        with patch.object(
            parsers,
            "extract_visible_text_lines",
            return_value=_yahoo_lines("資料時間：2026/09/25 13:45"),
        ):
            quote = parsers.parse_yahoo_taiwan_future_quotes("fixture")["TX"]

        self.assertEqual(quote["date"], "2026-09-25")
        self.assertEqual(quote["marketAsOf"], "2026-09-25")
        self.assertEqual(quote["sourceUpdatedAt"], "資料時間：2026/09/25 13:45")

    def test_fetch_keeps_saturday_observation_separate_from_unknown_market_date(self) -> None:
        saturday = datetime.fromisoformat("2026-09-26T09:00:00+08:00")
        with patch.dict(fetchers.cache_data, {"yahoo_tw_future_quotes": {}}), \
                patch.object(fetchers, "fetch_text", return_value="fixture"), \
                patch.object(app, "parse_yahoo_taiwan_future_quotes", return_value={
                    "TX": {"date": "", "marketAsOf": None, "close": 22000},
                }), \
                patch.object(app, "taipei_now", return_value=saturday):
            quote = fetchers.fetch_yahoo_taiwan_future_quotes()["TX"]

        self.assertEqual(quote["observedAt"], "2026-09-26T09:00:00+08:00")
        self.assertIsNone(quote["marketAsOf"])

    def test_weekend_observation_does_not_override_known_taifex_market_date(self) -> None:
        spec = {"symbol": "TX", "name": "臺股期貨", "taifexCommodity": "TX"}
        snapshot = {"date": "2026-09-25", "close": 21900, "openInterest": 100}
        yahoo = {
            "date": "", "marketAsOf": None, "observedAt": "2026-09-26T09:00:00+08:00",
            "close": 22000, "openInterest": 200,
        }
        with patch.object(builders, "build_yahoo_taiwan_future_technical_profile", return_value={}), \
                patch.object(builders, "fetch_taifex_latest_futures_market_snapshot", return_value=snapshot), \
                patch.object(builders, "fetch_yahoo_taiwan_future_quote", return_value=yahoo):
            item = builders.build_taifex_open_interest_item(spec)

        self.assertEqual(item["date"], "2026-09-25")
        self.assertEqual(item["close"], "21900.00")
        self.assertEqual(item["quoteStatus"], "taifex-official")

    def test_known_yahoo_market_date_uses_deterministic_freshness_rule(self) -> None:
        self.assertTrue(builders.yahoo_future_quote_can_override_taifex(
            {"date": "2026-09-25", "close": 22000}, {"date": "2026-09-25", "close": 21900},
        ))
        self.assertTrue(builders.yahoo_future_quote_can_override_taifex(
            {"date": "2026-09-24", "close": 22000}, {"date": "2026-09-25", "close": 21900},
        ))
        self.assertFalse(builders.yahoo_future_quote_can_override_taifex(
            {"date": "", "marketAsOf": None, "observedAt": "2026-09-26T09:00:00+08:00", "close": 22000},
            {"date": "2026-09-25", "close": 21900},
        ))

    def test_persistence_uses_market_date_and_skips_unknown_market_time(self) -> None:
        with tempfile.TemporaryDirectory(prefix="p0a-market-time-") as temp_dir:
            db_path = Path(temp_dir) / "derivatives.sqlite3"
            store = DerivativesStore(db_path)
            store.initialize()
            store.record_futures_payload({
                "updatedAt": "2026-09-26 09:00:00",
                "source": "Yahoo / TAIFEX fixture",
                "items": [
                    {"symbol": "TX", "name": "TX", "close": "22000", "openInterest": 10,
                     "date": "2026-09-26", "marketAsOf": None, "observedAt": "2026-09-26T09:00:00+08:00"},
                    {"symbol": "MTX", "name": "MTX", "close": "22000", "openInterest": 20,
                     "date": "2026-09-25", "marketAsOf": "2026-09-25"},
                ],
            })
            connection = sqlite3.connect(db_path)
            try:
                quotes = connection.execute(
                    "SELECT symbol, trade_time FROM futures_quote ORDER BY symbol"
                ).fetchall()
                oi_dates = connection.execute(
                    "SELECT symbol, trade_date FROM open_interest ORDER BY symbol"
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(quotes, [("MTX", "2026-09-25")])
        self.assertEqual(oi_dates, [("MTX", "2026-09-25")])


if __name__ == "__main__":
    unittest.main()
