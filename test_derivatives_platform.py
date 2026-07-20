import sqlite3
import ssl
import tempfile
import threading
import time
import unittest
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import Request

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")

import app
import builders
import cache
import fetch_registry
import fetchers
import market_config
import routes_derivatives
import routes_global_market
import routes_twse
import security
from derivatives_store import DerivativesStore


FUTURES_ITEM = {
    "symbol": "TX",
    "name": "Taiwan Index Futures",
    "type": "Taiwan Index Futures",
    "group": "Taiwan Futures",
    "close": "21000",
    "open": "20800",
    "high": "21100",
    "low": "20750",
    "volume": "12345",
    "openInterest": "98765",
    "pct": "+0.80%",
    "date": "2026-06-20",
    "source": "TAIFEX",
    "series": [
        {"date": "2026-06-18", "open": 20700, "high": 20900, "low": 20600, "close": 20800, "volume": 100},
        {"date": "2026-06-19", "open": 20800, "high": 21100, "low": 20750, "close": 21000, "volume": 120},
    ],
}

OPTIONS_CHAIN = {
    "underlying": "TXO",
    "name": "Taiwan Index Options",
    "tradeDate": "2026-06-20",
    "selectedExpiry": "202606",
    "expirations": [{"code": "202606", "expiryDate": "2026-06-17"}],
    "summary": {
        "callOpenInterest": 1000,
        "putOpenInterest": 1100,
        "putCallRatio": 1.1,
        "volumePutCallRatio": 0.9,
        "maxPain": 21000,
    },
    "chain": [],
    "distribution": [],
    "source": {"primary": "TAIFEX"},
    "analysis": {
        "bias": "Range bound",
        "supportLevel": 20800,
        "resistanceLevel": 21200,
        "riskLevel": "Medium",
        "marketScore": 52,
        "riskScore": 48,
        "confidenceScore": 66,
        "scoreFormula": {"marketScore": "test", "riskScore": "test", "confidenceScore": "test"},
        "crossValidation": [{"name": "PCR", "status": "available", "signal": "1.10"}],
        "strategySuggestion": "Range strategy.",
        "reasons": ["PCR is balanced."],
        "scenarios": [],
        "disclaimer": "Research only.",
    },
}


def market_payload(category):
    return {
        "category": category,
        "title": "Futures" if category == "futures" else "Options",
        "kicker": category,
        "subtitle": "test payload",
        "source": "Test source",
        "updatedAt": "2026-06-20 12:00:00",
        "summary": {"count": 1, "advancers": 1, "decliners": 0, "avgPct": "+0.80%"},
        "items": [FUTURES_ITEM],
        "taiwanOptionChain": OPTIONS_CHAIN,
    }


class DerivativesPlatformApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_store = app.DERIVATIVES_STORE
        cls._original_admin_token = os.environ.get("DERIVATIVES_ADMIN_TOKEN")
        os.environ["DERIVATIVES_ADMIN_TOKEN"] = "test-admin-token"
        cls._test_db_path = Path(cls._tmpdir.name) / "derivatives-test.sqlite3"
        app.DERIVATIVES_STORE = DerivativesStore(cls._test_db_path)
        app.DERIVATIVES_STORE.initialize()

    @classmethod
    def tearDownClass(cls):
        app.DERIVATIVES_STORE = cls._original_store
        if cls._original_admin_token is None:
            os.environ.pop("DERIVATIVES_ADMIN_TOKEN", None)
        else:
            os.environ["DERIVATIVES_ADMIN_TOKEN"] = cls._original_admin_token
        cls._tmpdir.cleanup()

    def setUp(self):
        self.client = app.app.test_client()

    def assert_success(self, response):
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertIn("data", body)
        self.assertIn("updated_at", body)
        return body["data"]

    def set_fake_twse_cache(self):
        site_data = {
            "cachedAt": "2026-06-20 12:00:00",
            "snapshotDate": "2026-06-20",
            "sectors": [{"name": "台灣加權指數", "sourceName": "發行量加權股價指數"}],
            "news": [],
        }
        stocks = [{
            "code": "2330",
            "name": "台積電",
            "market": "TWSE",
            "value": "1100.00",
            "close": "1100.00",
            "change": "+10.00",
            "pct": "+0.91%",
        }]
        with app.cache_lock:
            app.cache_data["site_data"] = site_data
            app.cache_data["all_stocks"] = stocks
            app.cache_data["market_date"] = "20260620"
            app.cache_data["cached_at"] = "2026-06-20 12:00:00"
            app.cache_data["last_error"] = None
            app.cache_data["stock_details"] = {}
        return site_data, stocks

    @patch.object(routes_derivatives, "build_global_market_payload", side_effect=lambda category, limit=None, **kwargs: market_payload(category))
    def test_index_futures_and_options_contracts(self, _payload):
        index_data = self.assert_success(self.client.get("/api/index"))
        self.assertIn("futures", index_data)
        futures_data = self.assert_success(self.client.get("/api/futures?sort=open_interest"))
        self.assertEqual(futures_data["items"][0]["symbol"], "TX")
        options_data = self.assert_success(self.client.get("/api/options?underlying=TXO"))
        self.assertEqual(options_data["selectedExpiry"], "202606")

    @patch.object(routes_derivatives, "fetch_taifex_futures_price_candles", return_value=[])
    @patch.object(routes_derivatives, "build_global_market_item", return_value=FUTURES_ITEM)
    def test_future_detail_candles_and_open_interest(self, _item, _taifex_candles):
        detail = self.assert_success(self.client.get("/api/futures/TX"))
        self.assertEqual(detail["symbol"], "TX")
        candles = self.assert_success(self.client.get("/api/futures/TX/candles?interval=day"))
        self.assertEqual(len(candles["candles"]), 2)
        open_interest = self.assert_success(self.client.get("/api/open-interest?symbol=TX"))
        self.assertEqual(open_interest["openInterest"], "98765")

    @patch.object(fetchers, "fetch_taifex_txo_option_chain", return_value=OPTIONS_CHAIN)
    def test_txo_chain_pcr_maxpain_and_ai(self, _chain):
        chain = self.assert_success(self.client.get("/api/options/chain?underlying=TXO"))
        self.assertEqual(chain["underlying"], "TXO")
        pcr = self.assert_success(self.client.get("/api/pcr?underlying=TXO"))
        self.assertEqual(pcr["putCallRatio"], 1.1)
        max_pain = self.assert_success(self.client.get("/api/maxpain?underlying=TXO"))
        self.assertEqual(max_pain["maxPain"], 21000)
        analysis = self.assert_success(self.client.get("/api/ai-analysis?target=TXO"))
        self.assertEqual(analysis["riskLevel"], "Medium")

    def test_taiwan_option_product_switch_routes(self):
        calls = []

        def fake_chain(expiry=None, market_date=None, source="auto", underlying="TXO"):
            calls.append((underlying, expiry, source, market_date))
            return {
                **OPTIONS_CHAIN,
                "underlying": underlying,
                "name": f"{underlying} Options",
                "shortName": underlying,
                "selectedExpiry": expiry or OPTIONS_CHAIN["selectedExpiry"],
            }

        with patch.object(routes_derivatives, "fetch_txo_option_chain", side_effect=fake_chain):
            for symbol in ("TXO", "TFO", "TEO", "CDO", "DVO", "DHO", "T50O"):
                chain = self.assert_success(
                    self.client.get(f"/api/options/chain?underlying={symbol}&expiry=202703&source=auto")
                )
                self.assertEqual(chain["underlying"], symbol)
                self.assertEqual(chain["selectedExpiry"], "202703")

        self.assertEqual(
            calls,
            [
                ("TXO", "202703", "auto", None),
                ("TFO", "202703", "auto", None),
                ("TEO", "202703", "auto", None),
                ("CDO", "202703", "auto", None),
                ("DVO", "202703", "auto", None),
                ("DHO", "202703", "auto", None),
                ("T50O", "202703", "auto", None),
            ],
        )

    def test_real_option_product_source_mappings(self):
        self.assertEqual(app.TAIWAN_OPTION_PRODUCTS["CDO"]["taifexCommodity"], "CDO")
        self.assertEqual(app.TAIWAN_OPTION_PRODUCTS["DVO"]["taifexCommodity"], "DVO")
        self.assertEqual(app.TAIWAN_OPTION_PRODUCTS["DHO"]["taifexCommodity"], "DHO")
        self.assertEqual(app.TAIWAN_OPTION_PRODUCTS["T50O"]["taifexCommodity"], "NYO")
        self.assertEqual(builders.BARCHART_FUTURES_OPTIONS_ROOTS["ZT=F"], "ZT")
        self.assertEqual(builders.BARCHART_FUTURES_OPTIONS_ROOTS["ZF=F"], "ZF")
        self.assertEqual(builders.BARCHART_FUTURES_OPTIONS_ROOTS["ZN=F"], "ZN")
        self.assertEqual(builders.BARCHART_FUTURES_OPTIONS_ROOTS["ZB=F"], "ZB")

        option_specs = app.GLOBAL_MARKET_CATEGORIES["options"]["items"]
        option_symbols = {item["symbol"] for item in option_specs}
        self.assertTrue({"SVIX", "VXZ", "VIXM"}.issubset(option_symbols))
        self.assertTrue({"^VXN", "^VXD", "^RVX", "^GVZ", "^OVX"}.isdisjoint(option_symbols))
        by_symbol = {item["symbol"]: item for item in option_specs}
        self.assertEqual(by_symbol["2330.TW"]["taifexCommodity"], "CDO")
        self.assertEqual(by_symbol["2454.TW"]["taifexCommodity"], "DVO")
        self.assertEqual(by_symbol["2317.TW"]["taifexCommodity"], "DHO")
        self.assertEqual(by_symbol["SOL-USD"]["optionChainSymbol"], "BYBIT_SOL")
        self.assertEqual(by_symbol["XRP-USD"]["optionChainSymbol"], "BYBIT_XRP")
        self.assertIn("沒有掛牌選擇權", by_symbol["0056.TW"]["optionChainUnavailableReason"])

    @patch.object(builders, "write_memory_cache")
    @patch.object(builders, "read_memory_cache", return_value=None)
    @patch.object(builders, "fetch_json")
    def test_bybit_option_chain_uses_real_call_put_tickers(self, fetch_json_mock, _read_cache, _write_cache):
        fetch_json_mock.return_value = {
            "retCode": 0,
            "retMsg": "OK",
            "result": {
                "list": [
                    {
                        "symbol": "SOL-31JUL26-100-C-USDT",
                        "lastPrice": "2.5",
                        "bid1Price": "2.4",
                        "ask1Price": "2.6",
                        "markPrice": "2.5",
                        "markIv": "0.65",
                        "volume24h": "12",
                        "openInterest": "30",
                        "underlyingPrice": "101.25",
                    },
                    {
                        "symbol": "SOL-31JUL26-100-P-USDT",
                        "lastPrice": "1.8",
                        "bid1Price": "1.7",
                        "ask1Price": "1.9",
                        "markPrice": "1.8",
                        "markIv": "0.70",
                        "volume24h": "9",
                        "openInterest": "22",
                        "underlyingPrice": "101.25",
                    },
                ],
            },
        }
        chain = app.build_public_options_chain("BYBIT_SOL")
        self.assertEqual(chain["symbol"], "BYBIT_SOL")
        self.assertEqual(chain["source"], "Bybit Public Options API")
        self.assertEqual(chain["price"], 101.25)
        self.assertEqual(chain["summary"]["callCount"], 1)
        self.assertEqual(chain["summary"]["putCount"], 1)
        self.assertEqual(chain["calls"][0]["strike"], 100.0)
        self.assertEqual(chain["puts"][0]["openInterest"], 22.0)
    @patch.object(app.DERIVATIVES_STORE, "record_news")
    @patch.object(routes_derivatives, "fetch_yahoo_us_symbol_news", return_value=[{
        "title": "Options market update",
        "source": "Test News",
        "publishedAt": "2026-06-20 12:00",
        "link": "https://example.test/news",
    }])
    @patch.object(routes_derivatives, "build_institution_payload_live", return_value=None)
    def test_news_and_institution_pending_response(self, _live, _news, _record):
        news = self.assert_success(self.client.get("/api/news?symbol=%5EVIX"))
        self.assertEqual(news["count"], 1)
        response = self.client.get("/api/institution?product=TX")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["summary"]["status"], "source_pending")
        self.assertEqual(len(data["rows"]), 4)

    @patch.object(builders, "fetch_taifex_institution_detail_rows", return_value=[
        {"Date": "20260708", "ContractCode": "臺股期貨", "Item": "自營商", "TradingVolume(Long)": "100", "TradingVolume(Short)": "40", "TradingVolume(Net)": "60"},
        {"Date": "20260708", "ContractCode": "臺股期貨", "Item": "投信", "TradingVolume(Long)": "10", "TradingVolume(Short)": "5", "TradingVolume(Net)": "5"},
        {"Date": "20260708", "ContractCode": "臺股期貨", "Item": "外資及陸資", "TradingVolume(Long)": "200", "TradingVolume(Short)": "300", "TradingVolume(Net)": "-100"},
    ])
    def test_institution_live_fetch_when_not_imported(self, _rows):
        response = self.client.get("/api/institution?product=TX")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()["data"]
        self.assertEqual(data["summary"]["status"], "connected")
        self.assertEqual(data["summary"]["netContracts"], -35)
        self.assertEqual(data["tradeDate"], "2026-07-08")
        total_row = next(row for row in data["rows"] if row["institution"] == "合計")
        self.assertEqual(total_row["netContracts"], -35)

    @patch.object(builders, "fetch_taifex_openapi_list")
    def test_stock_futures_and_options_aggregate_connected(self, mock_fetch):
        def fake_fetch(url, cache_seconds, timeout=20):
            if url == builders.TAIFEX_SSF_LIST_OPENAPI_URL:
                return [{"Contract": "CDF", "StockCode": "2330", "StockName": "台積電", "Type": "上市普通股標的證券"}]
            if url == builders.TAIFEX_FUTURES_DAILY_OPENAPI_URL:
                return [{"Date": "20260708", "Contract": "CDF", "Volume": "500", "OpenInterest": "1200", "Last": "1100"}]
            return []
        mock_fetch.side_effect = fake_fetch
        spec = {"symbol": "STF", "name": "股票期貨", "dataProvider": "taifex_product_status"}
        item = app.build_taifex_stock_derivative_aggregate_item(spec)
        self.assertEqual(item["status"], "connected")
        self.assertEqual(item["openInterestValue"], 1200)
        self.assertEqual(item["leaderStockName"], "台積電")

    @patch.object(builders, "fetch_twse_listed_industry_map", return_value={"2330": "半導體業"})
    @patch.object(builders, "fetch_stock_institutions_payload_near")
    def test_sector_fund_flow_aggregates_institutional_net_buy(self, mock_institutions, _industry_map):
        # T86 row layout: [code, name, ..., foreignShares(4), ..., trustShares(10),
        # dealerShares(11), ..., totalShares(18)]
        row = ["2330", "台積電"] + ["0"] * 17
        row[4] = "1000000"
        row[10] = "200000"
        row[11] = "50000"
        row[18] = "1250000"
        mock_institutions.return_value = (
            {"stat": "OK", "data": [row]},
            "20260620",
        )
        stocks = [{
            "code": "2330",
            "name": "台積電",
            "market": "TWSE",
            "securityType": "STOCK",
            "close": "600",
            "pct": "+1.50%",
            "turnover": "750000000",
        }]
        payload = app.build_sector_fund_flow(stocks, "20260620")
        self.assertTrue(payload["available"])
        self.assertEqual(payload["date"], "2026-06-20")
        self.assertEqual(payload["marketDate"], "2026-06-20")
        self.assertEqual(payload["sectorCount"], 1)
        sector = payload["rows"][0]
        self.assertEqual(sector["name"], "半導體業")
        self.assertEqual(sector["netAmountValue"], 1250000 * 600)
        self.assertEqual(sector["stockCount"], 1)
        self.assertEqual(sector["topStocks"][0]["code"], "2330")

    def test_build_news_summarizes_market_sectors_and_institutions(self):
        site_data = {
            "snapshotDate": "2026-07-18",
            "sectors": [
                {"name": "台灣加權指數", "pct": "+0.50%"},
                {"name": "半導體", "pct": "+2.00%"},
                {"name": "航運", "pct": "-1.50%"},
            ],
            "marketOverview": [{
                "name": "加權指數",
                "value": "23000",
                "pct": "+0.50%",
                "volume": "250000000",
                "turnoverValue": "350000000000",
                "tradeCount": "1800000",
            }],
            "marketStats": {},
            "institutions": [{"name": "合計", "diffValue": 1500000000}],
            "institutionSummary": [
                {"key": "foreign", "diffValue": 1000000000},
                {"key": "trust", "diffValue": 300000000},
                {"key": "dealer", "diffValue": 200000000},
            ],
            "institutionTrend": {
                "foreign": {"label": "連3買"},
                "trust": {"label": "連2買"},
                "dealer": {"label": "區間整理"},
            },
            "sourceLinks": {
                "market": "https://example.test/market",
                "institutions": "https://example.test/institutions",
            },
        }
        news = app.build_news(site_data)
        self.assertEqual(len(news), 3)
        self.assertEqual([item["tag"] for item in news], ["大盤", "指數", "法人"])
        self.assertIn("23000", news[0]["title"])
        self.assertEqual(news[0]["link"], "https://example.test/market")
        self.assertIn("半導體", news[1]["title"])
        self.assertIn("航運", news[1]["title"])
        self.assertIn("三大法人合計買超", news[2]["title"])
        self.assertIn("連3買", news[2]["body"])
        self.assertEqual(news[2]["link"], "https://example.test/institutions")

    @patch.object(builders, "build_news", return_value=[])
    @patch.object(builders, "build_yahoo_summary_series", side_effect=lambda cards, benchmark: cards)
    @patch.object(builders, "build_sector_fund_flow", return_value={"available": False, "rows": []})
    @patch.object(builders, "build_weighted_index_history_series", return_value=[])
    @patch.object(builders, "build_sector_history_series", return_value={"發行量加權股價指數": []})
    @patch.object(builders, "build_summary_cards_from_payload", return_value=[])
    @patch.object(builders, "build_yahoo_sector_groups", return_value=({}, {}))
    @patch.object(builders, "fetch_yahoo_sector_catalog", return_value={})
    @patch.object(builders, "fetch_yahoo_tpex_etfs", return_value={})
    @patch.object(builders, "fetch_tpex_mainboard_quotes", return_value=([], None))
    @patch.object(builders, "fetch_market_macro_factors", return_value={})
    @patch.object(builders, "fetch_international_market_indexes", return_value=[])
    @patch.object(builders, "fetch_market_volatility_indicator", return_value=None)
    @patch.object(builders, "fetch_json", return_value={"stat": "OK", "data": []})
    @patch.object(builders, "find_latest_dataset", return_value=({"stat": "OK", "data": []}, "20260718"))
    @patch.object(builders, "weighted_index_history_has_volume", return_value=True)
    @patch.object(builders, "upsert_latest_weighted_index_point", side_effect=lambda series, *a, **kw: series)
    @patch.object(builders, "parse_tpex_quotes", return_value=[])
    @patch.object(builders, "parse_all_stocks", return_value=[{
        "code": "2330", "name": "台積電", "market": "TWSE", "securityType": "STOCK",
        "close": "600", "pct": "+1.00%",
    }])
    @patch.object(builders, "parse_market_overview", return_value=[])
    @patch.object(builders, "parse_sectors", return_value=[])
    @patch.object(builders, "parse_institutions", return_value=[])
    @patch.object(builders, "parse_market_statistics", return_value={})
    def test_build_site_data_assembles_snapshot_from_sub_builders(self, *_mocks):
        site_data, all_stocks, market_date = app.build_site_data()
        self.assertEqual(market_date, "20260718")
        self.assertEqual(site_data["snapshotDate"], "2026-07-18")
        self.assertEqual(site_data["institutionDate"], "2026-07-18")
        self.assertEqual(len(all_stocks), 1)
        self.assertEqual(all_stocks[0]["code"], "2330")
        self.assertEqual(site_data["stockCount"], 1)
        self.assertEqual(site_data["tpexStockCount"], 0)
        self.assertEqual(site_data["sectors"], [])
        self.assertEqual(site_data["institutions"], [])
        self.assertEqual(site_data["news"], [])
        self.assertIn("sourceLinks", site_data)
        self.assertIn("yahooSectorGroups", site_data)

    @patch.object(routes_derivatives, "fetch_taiex_spot_snapshot", return_value={"value": 20900, "date": "2026-06-20", "source": "TWSE"})
    @patch.object(routes_derivatives, "build_global_market_item", return_value=FUTURES_ITEM)
    def test_basis_contract(self, _item, _spot):
        basis = self.assert_success(self.client.get("/api/basis?future=TX&spot=TAIEX"))
        self.assertEqual(basis["future"], "TX")
        self.assertEqual(basis["spot"], "TAIEX")
        self.assertEqual(basis["basis"], 100)
        self.assertIn("basisPct", basis)

    @patch.object(fetchers, "fetch_taifex_txo_option_chain", return_value=OPTIONS_CHAIN)
    def test_ai_decision_fields(self, _chain):
        analysis = self.assert_success(self.client.get("/api/ai-analysis?target=TXO"))
        self.assertIn("marketScore", analysis)
        self.assertIn("riskScore", analysis)
        self.assertIn("confidenceScore", analysis)
        self.assertIn("scoreFormula", analysis)
        self.assertIn("crossValidation", analysis)
        self.assertIn("strategySuggestion", analysis)

    def test_v1_status_contract(self):
        status = self.assert_success(self.client.get("/api/derivatives/v1-status"))
        self.assertEqual(status["scope"], "domestic_derivatives")
        self.assertIn("futures", status)
        self.assertIn("options", status)
        self.assertIn("aiScoreFormula", status)
        self.assertIn("institutionImport", status)

    @patch.object(routes_twse, "build_stock_detail", return_value={"code": "2330", "name": "台積電", "historyCount": 1})
    def test_twse_core_routes_use_cached_payloads(self, _detail):
        self.set_fake_twse_cache()
        site = self.client.get("/api/twse/site-data").get_json()
        self.assertEqual(site["cachedAt"], "2026-06-20 12:00:00")
        all_stocks = self.client.get("/api/twse/all-stocks").get_json()
        self.assertEqual(all_stocks["count"], 1)
        search = self.client.get("/api/twse/search?q=2330").get_json()
        self.assertEqual(search["count"], 1)
        detail = self.client.get("/api/twse/stock/2330?quick=1").get_json()
        self.assertEqual(detail["code"], "2330")
        self.assertEqual(detail["cachedAt"], "2026-06-20 12:00:00")

    @patch.object(routes_global_market, "fetch_yahoo_us_market_search", return_value=[])
    @patch.object(routes_global_market, "fetch_nyse_us_market_search", return_value=([], {}))
    @patch.object(routes_global_market, "search_us_listed_universe", return_value=([
        {"symbol": "AAPL", "name": "Apple Inc.", "group": "美股個股", "source": "test"}
    ], {"美股個股": 1}, "test source"))
    def test_us_market_search_route_merges_mocked_sources(self, _listed, _nyse, _yahoo):
        payload = self.client.get("/api/us-market/search?q=AAPL").get_json()
        self.assertEqual(payload["query"], "AAPL")
        self.assertGreaterEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["symbol"], "AAPL")

    def test_stock_history_sanitizer_drops_invalid_ohlc_rows(self):
        rows = [
            ["115/06/30", "1000", "", "106.85", "108.25", "106.75", "107.80", "+3.35"],
            ["115/07/01", "0", "", "0.00", "0.00", "0.00", "109.69", "+1.89"],
            ["115/07/02", "1000", "", "107.20", "108.95", "106.90", "108.80", "-0.89"],
            ["115/07/03", "1000", "", "110.00", "109.00", "108.00", "110.50", "+1.70"],
        ]
        sanitized = app.sanitize_history_rows(rows)
        self.assertEqual([row[0] for row in sanitized], ["115/06/30", "115/07/02"])

    @patch.object(fetchers, "fetch_text", side_effect=RuntimeError("news unavailable"))
    def test_etf_stock_news_uses_non_empty_fallback(self, _fetch_text):
        stock = {"code": "0050", "name": "元大台灣50", "market": "TWSE", "securityType": "ETF"}
        news = app.fetch_stock_news(stock, 6)
        self.assertGreaterEqual(len(news), 3)
        self.assertIn("Yahoo ETF 新聞", news[0]["title"])
        self.assertIn("news.google.com/search", news[1]["link"])

    @patch.object(fetchers, "fetch_text")
    def test_yahoo_broker_trading_parser_reads_broker_tables(self, fetch_text_mock):
        fetch_text_mock.return_value = """
        <section>
          <div>資料時間：</div><div>2026/07/01</div>
          <div>主力買賣超(張)</div><div>20,960</div>
          <div>主力買超(張)</div><div>27,527</div>
          <div>主力賣超(張)</div><div>-6,567</div>
          <div>買賣超佔成交量</div><div>29.06%</div>
          <div>買超券商</div><div>買進</div><div>賣出</div><div>買超張數</div>
          <div>元大總公司</div><div>19,878</div><div>9,973</div><div>9,905</div>
          <div>賣超券商</div><div>買進</div><div>賣出</div><div>賣超張數</div>
          <div>國泰敦南</div><div>1,996</div><div>3,791</div><div>-1,795</div>
        </section>
        """
        stock = {"code": "0050", "name": "元大台灣50", "market": "TWSE", "securityType": "ETF"}
        payload = app.fetch_yahoo_broker_trading(stock, 15)
        self.assertEqual(payload["summary"]["netLots"], 20960)
        self.assertEqual(payload["buyBrokers"][0]["broker"], "元大總公司")
        self.assertEqual(payload["sellBrokers"][0]["net"], -1795)

    @patch.object(fetchers, "fetch_text")
    def test_yahoo_major_holders_parser_reads_rows(self, fetch_text_mock):
        fetch_text_mock.return_value = """
        <section>
          <div>年度/日期</div><div>外資籌碼</div><div>大戶籌碼</div><div>董監持股</div><div>股價</div>
          <div>2026/06/26</div><div>5.24%</div><div>18.42%</div><div>10.58%</div><div>103.10</div>
          <div>2026/06/18</div><div>6.87%</div><div>17.31%</div><div>10.58%</div><div>107.30</div>
        </section>
        """
        stock = {"code": "1513", "name": "中興電", "market": "TWSE", "securityType": "STOCK"}
        payload = app.fetch_yahoo_major_holders(stock, 30)
        self.assertEqual(payload["latest"]["date"], "2026-06-26")
        self.assertEqual(payload["latest"]["majorHolderRatio"], 18.42)
        self.assertEqual(len(payload["rows"]), 2)

    @patch.object(app, "fetch_yahoo_history_rows", return_value=[
        ["115/06/30", "1000", "", "106.85", "108.25", "106.75", "107.80", "+3.35"],
        ["115/07/02", "1000", "", "107.20", "108.95", "106.90", "108.80", "-0.89"],
    ])
    def test_etf_stock_detail_always_has_news_items(self, _history):
        stock = {
            "code": "0050",
            "name": "元大台灣50",
            "market": "TWSE",
            "marketLabel": "上市",
            "securityType": "ETF",
            "close": "108.80",
            "change": "-0.89",
            "pct": "-0.81%",
            "volume": "73,421,155",
            "trades": "108,165",
            "turnover": "7,929,812,970",
            "open": "107.20",
            "high": "108.95",
            "low": "106.90",
            "bid": "108.75",
            "bidVolume": "213",
            "ask": "108.80",
            "askVolume": "393",
        }
        detail = app.build_stock_detail(stock, "20260702", quick=True)
        self.assertTrue(detail["isEtf"])
        self.assertGreaterEqual(len(detail["companyNews"]), 1)
        self.assertIn("google", detail["newsLinks"])
        self.assertEqual(
            [card["title"] for card in detail["chipSummary"]["cards"]],
            ["法人買賣", "主力進出", "資券變化", "大戶籌碼"],
        )

    @patch.object(fetchers, "fetch_yahoo_chart")
    def test_yahoo_history_rows_skip_incomplete_ohlc_points(self, chart_mock):
        timestamps = [
            int(datetime(2026, 6, 30, tzinfo=app.TZ).timestamp()),
            int(datetime(2026, 7, 1, tzinfo=app.TZ).timestamp()),
            int(datetime(2026, 7, 2, tzinfo=app.TZ).timestamp()),
        ]
        chart_mock.return_value = {
            "timestamp": timestamps,
            "meta": {"chartPreviousClose": 104.45},
            "indicators": {
                "quote": [{
                    "open": [106.85, 0.0, 107.20],
                    "high": [108.25, 0.0, 108.95],
                    "low": [106.75, 0.0, 106.90],
                    "close": [107.80, 109.69, 108.80],
                    "volume": [103816325, 0, 73053059],
                }]
            },
        }
        diagnostics = {}
        rows = app.fetch_yahoo_history_rows(
            "0050",
            app.STOCK_HISTORY_RECENT_MONTHS,
            market="TWSE",
            diagnostics=diagnostics,
        )
        self.assertEqual([row[0] for row in rows], ["115/06/30", "115/07/02"])
        self.assertEqual(diagnostics["invalid_rows"], 1)
        self.assertTrue(all(app.is_valid_history_row(row) for row in rows))

    @patch.object(cache, "load_disk_cache", return_value=None)
    def test_ensure_cache_allows_only_one_cold_refresh(self, _load):
        previous = {
            "site_data": app.cache_data["site_data"],
            "all_stocks": app.cache_data["all_stocks"],
            "market_date": app.cache_data["market_date"],
            "cached_at": app.cache_data["cached_at"],
            "last_error": app.cache_data["last_error"],
        }
        calls = {"count": 0}
        call_lock = threading.Lock()

        def fake_refresh():
            time.sleep(0.03)
            with call_lock:
                calls["count"] += 1
            self.set_fake_twse_cache()

        with app.cache_lock:
            app.cache_data["site_data"] = None
            app.cache_data["all_stocks"] = []
            app.cache_data["market_date"] = None
            app.cache_data["cached_at"] = None
            app.cache_data["last_error"] = None
        try:
            with patch.object(cache, "refresh_cache", side_effect=fake_refresh):
                threads = [threading.Thread(target=cache.ensure_cache) for _ in range(5)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
            self.assertEqual(calls["count"], 1)
        finally:
            with app.cache_lock:
                app.cache_data.update(previous)

    def test_institution_import_flow(self):
        payload = {
            "rows": [
                {
                    "institution": "外資",
                    "product_code": "TX_TEST",
                    "long_contracts": 120,
                    "short_contracts": 80,
                    "net_contracts": 40,
                    "trade_date": "2026-06-20",
                }
            ]
        }
        denied = self.client.post("/api/institution/import", json=payload)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.get_json()["error_code"], "ADMIN_AUTH_REQUIRED")
        query_denied = self.client.post("/api/institution/import?admin_token=test-admin-token", json=payload)
        self.assertEqual(query_denied.status_code, 403)
        self.assertEqual(query_denied.get_json()["error_code"], "ADMIN_AUTH_REQUIRED")
        imported = self.assert_success(
            self.client.post("/api/institution/import", json=payload, headers={"X-Admin-Token": "test-admin-token"})
        )
        self.assertEqual(imported["inserted"], 1)
        institution = self.assert_success(self.client.get("/api/institution?product=TX_TEST"))
        self.assertEqual(institution["summary"]["status"], "imported")
        self.assertGreaterEqual(len(institution["rows"]), 1)

    def test_static_whitelist_blocks_source_and_database_downloads(self):
        self.assertFalse(Path("assets/app.py").exists())
        for path, expected_status in [
            ("/app.js", 200),
            ("/assets/app-icon.svg", 200),
            ("/derivatives-status.html", 200),
            ("/app.py", 404),
            ("/derivatives-platform.sqlite3", 404),
            ("/assets/app.py", 404),
        ]:
            response = self.client.get(path)
            try:
                self.assertEqual(response.status_code, expected_status, path)
            finally:
                response.close()

    def test_taifex_txo_fixture_parser(self):
        fixture = Path("tests/fixtures/taifex_txo_sample.html").read_text(encoding="utf-8")
        rows = app.parse_taifex_txo_option_rows(fixture, spot_price=21050)
        self.assertEqual(len(rows), 2)
        summary = app.summarize_taifex_option_rows(rows)
        self.assertEqual(summary["callOpenInterest"], 1000)
        self.assertEqual(summary["putOpenInterest"], 1100)
        self.assertAlmostEqual(summary["putCallRatio"], 1.1)
        chain = app.build_taifex_option_chain(rows)
        max_pain = app.calculate_taifex_max_pain(chain)
        self.assertEqual(max_pain["strike"], 21000)

    def test_taifex_option_payload_skips_expired_default_expiry(self):
        today = datetime.now(app.TZ).date()
        expired_date = (today - timedelta(days=1)).isoformat()
        active_date = (today + timedelta(days=4)).isoformat()
        rows = [
            {
                "expiry": "EXPIRED",
                "expiryDate": expired_date,
                "strike": 21000,
                "optionType": "call",
                "openInterest": 9000,
                "volume": 100,
            },
            {
                "expiry": "ACTIVE",
                "expiryDate": active_date,
                "strike": 21100,
                "optionType": "call",
                "openInterest": 500,
                "volume": 50,
            },
            {
                "expiry": "ACTIVE",
                "expiryDate": active_date,
                "strike": 21100,
                "optionType": "put",
                "openInterest": 600,
                "volume": 60,
            },
        ]
        payload = app.build_taifex_txo_option_payload(
            rows,
            trade_date=today.isoformat(),
            spot_snapshot={"value": 21100, "date": today.isoformat()},
        )
        self.assertEqual(payload["selectedExpiry"], "ACTIVE")
        self.assertEqual(payload["selectedExpiryDate"], active_date)

    @patch.object(app, "fetch_yahoo_txo_option_chain")
    def test_taifex_option_payload_supplements_matching_yahoo_intraday_oi(self, yahoo_chain):
        taifex_payload = {
            "selectedExpiry": "202607",
            "summary": {"totalOpenInterest": 0, "atmStrike": 45500},
            "chain": [
                {
                    "strike": 45500,
                    "call": {"strike": 45500, "optionType": "call", "openInterest": 0, "volume": 10},
                    "put": {"strike": 45500, "optionType": "put", "openInterest": 0, "volume": 12},
                },
            ],
            "distribution": [],
            "expirations": [{"code": "202607", "totalOpenInterest": 0}],
            "spot": {"value": 45750},
            "source": {"primary": "TAIFEX 選擇權每日交易行情查詢"},
        }
        yahoo_chain.return_value = {
            "selectedExpiry": "台指2607",
            "tradeDate": "2026-07-08",
            "chain": [
                {
                    "strike": 45500,
                    "call": {"openInterest": 498, "volume": 29105, "bid": 28.0, "ask": 28.5},
                    "put": {"openInterest": 964, "volume": 28666, "bid": 0.1, "ask": 0.3},
                },
            ],
        }
        supplemented = app.supplement_taifex_option_payload_with_yahoo_oi(taifex_payload)
        summary = supplemented["summary"]
        self.assertEqual(summary["callOpenInterest"], 498)
        self.assertEqual(summary["putOpenInterest"], 964)
        self.assertAlmostEqual(summary["putCallRatio"], 964 / 498)
        self.assertEqual(supplemented["chain"][0]["call"]["openInterestSource"], "Yahoo 股市盤中未平倉")
        self.assertEqual(supplemented["source"]["intradayOiProvider"], "Yahoo 股市台灣選擇權盤中未平倉")

    @patch.object(fetchers, "get_yahoo_options_crumb", return_value="test-crumb")
    def test_fetch_yahoo_options_payload_reaches_cboe_expiration_parser(self, _crumb):
        """Regression guard (TD-01 slice 5 batch B4): fetch_yahoo_options_payload's
        deferred `import builders` call for parse_cboe_expiration_request must
        resolve. TD-01 slice 4 moved this function from app.py to builders.py
        without fetchers.py's `app.parse_cboe_expiration_request` reference
        being updated - a silent AttributeError on every call, undetected until
        a slice-5 full-repo audit. This test exercises the exact call site."""
        captured_urls = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return b'{"optionChain": {"result": []}}'

        def fake_open(req, timeout=20):
            captured_urls.append(req.full_url)
            return FakeResponse()

        with patch.object(fetchers, "_yahoo_options_opener") as mock_opener:
            mock_opener.open.side_effect = fake_open
            result = fetchers.fetch_yahoo_options_payload("AAPL", expiration="2026-08-21")

        self.assertEqual(result, {"optionChain": {"result": []}})
        self.assertEqual(len(captured_urls), 1)
        expected_timestamp = builders.parse_cboe_expiration_request("2026-08-21")
        self.assertIsNotNone(expected_timestamp)
        self.assertIn(f"date={expected_timestamp}", captured_urls[0])

    def test_fetch_taifex_txo_option_chain_uses_public_error_message_on_empty_result(self):
        """Regression guard (TD-01 slice 5 batch B4): fetch_taifex_txo_option_chain's
        deferred `import builders` call for PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE
        must resolve. TD-01 slice 4 moved this constant from app.py to
        builders.py without fetchers.py's `app.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE`
        reference being updated - a silent AttributeError on the all-sources-
        empty fallback path, undetected until a slice-5 full-repo audit."""
        market_date = datetime.now(app.TZ).strftime("%Y%m%d")
        cache_key_prefix = "TXO:"
        with cache.cache_lock:
            for key in [key for key in cache.cache_data["taifex_options_chain"] if key.startswith(cache_key_prefix)]:
                del cache.cache_data["taifex_options_chain"][key]
        with patch.object(fetchers, "fetch_form_text", side_effect=RuntimeError("no data available")):
            result = fetchers.fetch_taifex_txo_option_chain(underlying="TXO", market_date=market_date)
        self.assertEqual(result["error"], builders.PUBLIC_TAIFEX_OPTION_CHAIN_ERROR_MESSAGE)
        self.assertIn("availableProducts", result)

    def test_yahoo_txo_underlying_snapshot_parses_benchmark_line(self):
        snapshot = app.parse_yahoo_txo_underlying_snapshot([
            "加權股價指數：45,734.41",
            "漲跌(%)：▲255.30 (0.56%)",
            "最高：45,837.12",
            "最低：45,036.64",
            "成交量(億)：9,606.04",
        ])
        self.assertEqual(snapshot["value"], 45734.41)
        self.assertEqual(snapshot["change"], 255.30)
        self.assertEqual(snapshot["pct"], 0.56)
        self.assertEqual(snapshot["high"], 45837.12)
        self.assertEqual(snapshot["low"], 45036.64)
        self.assertEqual(snapshot["volumeBillion"], 9606.04)

    def test_taifex_futures_oi_fixture_parser(self):
        fixture = Path("tests/fixtures/taifex_futures_oi_sample.html").read_text(encoding="utf-8")
        self.assertEqual(app.parse_taifex_open_interest_by_header(fixture, "MTX"), 45678)
        self.assertEqual(app.parse_taifex_open_interest_by_header(fixture, "SOF"), 1234)

    def test_twse_market_fixture_parser(self):
        fixture = json.loads(Path("tests/fixtures/twse_market_sample.json").read_text(encoding="utf-8"))
        overview = app.parse_market_overview(fixture)
        stocks = app.parse_all_stocks(fixture)
        weighted = next(item for item in overview if item["name"] == "發行量加權股價指數")
        self.assertEqual(weighted["value"], "21000.00")
        self.assertEqual(weighted["change"], "+120.50")
        self.assertEqual(weighted["volumeValue"], 7000000000)
        self.assertEqual(stocks[0]["code"], "2330")
        self.assertEqual(stocks[0]["pct"], "+0.91%")

    def test_store_deduplicates_snapshots_and_ai_reports(self):
        app.DERIVATIVES_STORE.record_option_chain(OPTIONS_CHAIN, "2026-06-20T12:00:00+08:00")
        app.DERIVATIVES_STORE.record_option_chain(OPTIONS_CHAIN, "2026-06-20T12:01:00+08:00")
        app.DERIVATIVES_STORE.record_ai_report("TXO_DEDUPE", OPTIONS_CHAIN["analysis"], "2026-06-20T12:00:00+08:00")
        app.DERIVATIVES_STORE.record_ai_report("TXO_DEDUPE", OPTIONS_CHAIN["analysis"], "2026-06-20T12:01:00+08:00")
        cls_path = self._test_db_path
        connection = sqlite3.connect(cls_path)
        try:
            snapshot_count = connection.execute(
                "SELECT COUNT(*) FROM option_chain_snapshot WHERE underlying = 'TXO' AND trade_date = '2026-06-20'"
            ).fetchone()[0]
            ai_count = connection.execute(
                "SELECT COUNT(*) FROM ai_analysis_report WHERE target_symbol = 'TXO_DEDUPE'"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(snapshot_count, 1, cls_path)
        self.assertEqual(ai_count, 1)

    def test_store_uses_wal_and_prune_allowlist(self):
        connection = app.DERIVATIVES_STORE._connect()
        try:
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            connection.close()
        self.assertIn(journal_mode.lower(), {"wal", "memory"})
        connection = sqlite3.connect(self._test_db_path)
        try:
            for index in range(5):
                connection.execute(
                    "INSERT INTO system_log(level, module, message, created_at) VALUES (?, ?, ?, ?)",
                    ("INFO", "unit-prune", f"message-{index}", f"2026-06-20T12:0{index}:00+08:00"),
                )
            app.DERIVATIVES_STORE._prune_to_limit(connection, "system_log", "module", "unit-prune", 2)
            remaining = connection.execute(
                "SELECT COUNT(*) FROM system_log WHERE module = ?",
                ("unit-prune",),
            ).fetchone()[0]
            self.assertEqual(remaining, 2)
            with self.assertRaises(ValueError):
                app.DERIVATIVES_STORE._prune_to_limit(connection, "system_log", "level", "INFO", 10)
        finally:
            connection.close()

    def test_market_news_recording_prunes_to_retention(self):
        original_retention = app.DERIVATIVES_STORE.MARKET_NEWS_RETENTION
        app.DERIVATIVES_STORE.MARKET_NEWS_RETENTION = 2
        try:
            app.DERIVATIVES_STORE.record_news("unit-prune-news", [
                {"title": f"news-{index}", "source": "unit", "publishedAt": f"2026-06-20 12:0{index}"}
                for index in range(5)
            ])
            connection = sqlite3.connect(self._test_db_path)
            try:
                remaining = connection.execute(
                    "SELECT COUNT(*) FROM market_news WHERE category = ?",
                    ("unit-prune-news",),
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(remaining, 2)
        finally:
            app.DERIVATIVES_STORE.MARKET_NEWS_RETENTION = original_retention

    def test_api_rate_limit_returns_standard_429(self):
        original_limit = security.API_RATE_LIMIT_PER_WINDOW
        security.API_RATE_LIMIT_PER_WINDOW = 2
        with security.API_RATE_LIMIT_LOCK:
            security.API_RATE_LIMIT_STATE.clear()
        try:
            self.assertEqual(self.client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.1"}).status_code, 200)
            self.assertEqual(self.client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.2"}).status_code, 200)
            response = self.client.get("/api/derivatives/v1-status", headers={"X-Forwarded-For": "203.0.113.3"})
            self.assertEqual(response.status_code, 429)
            body = response.get_json()
            self.assertFalse(body["success"])
            self.assertEqual(body["error_code"], "RATE_LIMITED")
            self.assertIn("Retry-After", response.headers)
        finally:
            security.API_RATE_LIMIT_PER_WINDOW = original_limit
            with security.API_RATE_LIMIT_LOCK:
                security.API_RATE_LIMIT_STATE.clear()

    def test_api_rate_limit_state_discards_expired_clients(self):
        original_cleanup = security.API_RATE_LIMIT_LAST_CLEANUP
        try:
            with security.API_RATE_LIMIT_LOCK:
                security.API_RATE_LIMIT_STATE.clear()
                security.API_RATE_LIMIT_STATE["stale-client"] = [0.0]
                security.API_RATE_LIMIT_LAST_CLEANUP = -security.API_RATE_LIMIT_WINDOW_SECONDS * 2
            response = self.client.get("/api/derivatives/v1-status")
            self.assertEqual(response.status_code, 200)
            with security.API_RATE_LIMIT_LOCK:
                self.assertNotIn("stale-client", security.API_RATE_LIMIT_STATE)
        finally:
            with security.API_RATE_LIMIT_LOCK:
                security.API_RATE_LIMIT_LAST_CLEANUP = original_cleanup
                security.API_RATE_LIMIT_STATE.clear()

    def test_rate_limit_identity_ignores_untrusted_forwarded_for(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        security_source = Path("security.py").read_text(encoding="utf-8")
        self.assertNotIn('request.headers.get("X-Forwarded-For")', security_source)
        self.assertIn("ProxyFix", app_source)

    def test_api_404_uses_standard_error_payload(self):
        response = self.client.get("/api/does-not-exist")
        self.assertEqual(response.status_code, 404)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error_code"], "NOT_FOUND")

    def test_reported_frontend_xss_slots_escape_html(self):
        script = Path("app.js").read_text(encoding="utf-8")
        self.assertNotIn("<h3>${stock.code} ${stock.name}</h3>", script)
        self.assertNotIn("<strong>${stock.code} ${stock.name}</strong>", script)
        self.assertNotIn("<span class=\"news-tag\">${item.tag}</span>", script)
        self.assertIn("${escapeHtml(stock.code)} ${escapeHtml(stock.name)}", script)
        self.assertIn("<span class=\"news-tag\">${escapeHtml(item.tag)}</span>", script)
        self.assertIn("<strong>${escapeHtml(item.title)}</strong>", script)
        self.assertIn("${escapeHtml(activeSector.name)}", script)
        self.assertIn("${escapeHtml(zone.dataset.label || point.label)}", script)
        self.assertIn("${escapeHtml(zone.dataset.sectorOpen || \"--\")}", script)

    def test_frontend_url_and_inner_html_safety_rules(self):
        script = Path("app.js").read_text(encoding="utf-8")
        self.assertIn("function safeUrl(", script)
        self.assertIn("function sanitizeHtml(", script)
        self.assertIn("let nativeInnerHtmlDescriptor", script)
        self.assertIn("nativeInnerHtmlDescriptor.set.call(template, html)", script)
        self.assertIn("Element.prototype, \"innerHTML\"", script)
        self.assertNotIn('href="${profile.website}"', script)
        self.assertNotIn('href="${escapeHtml(profile.website)}"', script)
        self.assertNotIn('href="${escapeHtml(item.link', script)
        self.assertNotIn('href="${escapeHtml(item.url', script)
        self.assertNotIn('href="${escapeHtml(validation.referenceUrl', script)
        self.assertNotIn('href="${escapeHtml(margin.sourceLink', script)
        unsafe_href_lines = [
            line.strip()
            for line in script.splitlines()
            if 'href="${' in line and 'href="${safeUrl(' not in line and "querySelector" not in line
        ]
        unsafe_src_lines = [
            line.strip()
            for line in script.splitlines()
            if 'src="${' in line and 'src="${safeUrl(' not in line
        ]
        self.assertEqual([], unsafe_href_lines)
        self.assertEqual([], unsafe_src_lines)

    def test_frontend_safe_url_blocks_script_protocols(self):
        script = Path("app.js").read_text(encoding="utf-8")
        self.assertIn('compact.startsWith("javascript:")', script)
        self.assertIn('compact.startsWith("data:")', script)
        self.assertIn('compact.startsWith("vbscript:")', script)

    def test_api_errors_do_not_expose_exception_details(self):
        source = Path("app.py").read_text(encoding="utf-8")
        cache_source = Path("cache.py").read_text(encoding="utf-8")
        self.assertNotIn('f"資料來源暫不可用：{exc}"', source)
        self.assertNotIn('f"期現貨價差資料暫不可用：{exc}"', source)
        self.assertNotIn('f"選擇權資料暫時無法載入：{exc}"', source)
        self.assertNotIn("{exc}", source)
        self.assertNotIn("str(exc)", source)
        self.assertNotIn("{exc}", cache_source)
        self.assertNotIn("str(exc)", cache_source)
        self.assertNotIn('cache_data["last_error"] = str(exc)', cache_source)
        self.assertIn('cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE', cache_source)
        self.assertIn("PUBLIC_DATA_SOURCE_ERROR_MESSAGE", source)
        self.assertIn("def api_exception_response", source)
        self.assertIn("LOGGER.exception", source)

    def test_security_guardrail_script_passes(self):
        result = subprocess.run(
            [sys.executable, "security_guardrail_check.py"],
            cwd=Path(__file__).resolve().parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("SECURITY_GUARDRAIL_OK", result.stdout)

    def test_invalid_symbol_has_standard_error(self):
        response = self.client.get("/api/futures/UNKNOWN")
        self.assertEqual(response.status_code, 404)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error_code"], "INVALID_SYMBOL")
        self.assertIn("message", body["error"])

    # --- Characterization tests for TD-01 slice 1 (security.py extraction) ---
    # Golden-output tests written against the current app.py, before
    # add_security_headers / enforce_api_rate_limit / the SSL fallback cluster
    # move to security.py. Must stay green after the move.

    def test_security_headers_have_expected_values(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertEqual(response.headers.get("Permissions-Policy"), "camera=(), microphone=(), geolocation=()")
        self.assertEqual(
            response.headers.get("Content-Security-Policy"),
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; manifest-src 'self'; "
            "worker-src 'self'; base-uri 'self'; frame-ancestors 'none'",
        )
        self.assertEqual(response.headers.get("Strict-Transport-Security"), "max-age=31536000; includeSubDomains")

    def test_is_ssl_error_classifies_cert_verification_failures(self):
        self.assertTrue(security._is_ssl_error(ssl.SSLCertVerificationError("certificate verify failed")))
        self.assertTrue(security._is_ssl_error(URLError(ssl.SSLCertVerificationError("certificate verify failed"))))
        self.assertFalse(security._is_ssl_error(ValueError("unrelated error")))

    def test_is_production_environment_reads_env_vars(self):
        with patch.dict(os.environ, {"MARKET_PULSE_ENV": "production"}, clear=False):
            self.assertTrue(security._is_production_environment())
        removed = {name: os.environ.pop(name, None) for name in ("MARKET_PULSE_ENV", "FLASK_ENV", "RENDER", "RENDER_SERVICE_ID", "RENDER_EXTERNAL_URL")}
        try:
            self.assertFalse(security._is_production_environment())
        finally:
            for name, value in removed.items():
                if value is not None:
                    os.environ[name] = value

    def test_urlopen_with_ssl_fallback_falls_back_for_allowed_host_in_non_production(self):
        request = Request("https://www.twse.com.tw/some/path")
        cert_error = ssl.SSLCertVerificationError("certificate verify failed")
        sentinel = object()
        calls = {"count": 0}

        def fake_urlopen(_req, timeout=None, context=None):
            calls["count"] += 1
            if calls["count"] == 1:
                raise cert_error
            return sentinel

        with patch.object(security, "urlopen", side_effect=fake_urlopen), \
                patch.object(security, "_is_production_environment", return_value=False), \
                patch.dict(os.environ, {"ALLOW_UNVERIFIED_SSL_FALLBACK": "1"}):
            result = security._urlopen_with_ssl_fallback(request, timeout=5)
        self.assertIs(result, sentinel)
        self.assertEqual(calls["count"], 2)

    def test_urlopen_with_ssl_fallback_requires_explicit_opt_in_outside_production(self):
        """TD-07 regression guard: non-production must not auto-allow fallback without ALLOW_UNVERIFIED_SSL_FALLBACK=1.

        fake_urlopen only fails the *first* (verified) call and would succeed
        on a second (unverified) call, so this only passes if the code never
        reaches that second call - i.e. the opt-in gate actually blocked it,
        not merely because the mock ran out of failures to raise.
        """
        request = Request("https://www.twse.com.tw/some/path")
        cert_error = ssl.SSLCertVerificationError("certificate verify failed")
        sentinel = object()
        calls = {"count": 0}

        def fake_urlopen(_req, timeout=None, context=None):
            calls["count"] += 1
            if calls["count"] == 1:
                raise cert_error
            return sentinel

        removed = os.environ.pop("ALLOW_UNVERIFIED_SSL_FALLBACK", None)
        try:
            with patch.object(security, "urlopen", side_effect=fake_urlopen), \
                    patch.object(security, "_is_production_environment", return_value=False):
                with self.assertRaises(ssl.SSLCertVerificationError):
                    security._urlopen_with_ssl_fallback(request, timeout=5)
            self.assertEqual(calls["count"], 1, "must not attempt an unverified fallback call without explicit opt-in")
        finally:
            if removed is not None:
                os.environ["ALLOW_UNVERIFIED_SSL_FALLBACK"] = removed

    def test_urlopen_with_ssl_fallback_tdcc_attempts_verified_connection_first(self):
        """TD-07 regression guard: smart.tdcc.com.tw must no longer skip verification unconditionally."""
        request = Request("https://smart.tdcc.com.tw/some/path")
        cert_error = ssl.SSLCertVerificationError("certificate verify failed")
        sentinel = object()
        calls = {"count": 0}

        def fake_urlopen(_req, timeout=None, context=None):
            calls["count"] += 1
            if calls["count"] == 1:
                raise cert_error
            return sentinel

        with patch.object(security, "urlopen", side_effect=fake_urlopen), \
                patch.object(security, "_is_production_environment", return_value=False), \
                patch.dict(os.environ, {"ALLOW_UNVERIFIED_SSL_FALLBACK": "1"}):
            result = security._urlopen_with_ssl_fallback(request, timeout=5)
        self.assertIs(result, sentinel)
        self.assertEqual(calls["count"], 2, "verified urlopen must be attempted before any unverified fallback")

    def test_urlopen_with_ssl_fallback_blocks_in_production(self):
        request = Request("https://www.twse.com.tw/some/path")
        cert_error = ssl.SSLCertVerificationError("certificate verify failed")

        def fake_urlopen(_req, timeout=None, context=None):
            raise cert_error

        with patch.object(security, "urlopen", side_effect=fake_urlopen), patch.object(security, "_is_production_environment", return_value=True):
            with self.assertRaises(ssl.SSLCertVerificationError):
                security._urlopen_with_ssl_fallback(request, timeout=5)

    def test_urlopen_with_ssl_fallback_rejects_non_allowlisted_host(self):
        request = Request("https://not-allowed.example.com/some/path")
        cert_error = ssl.SSLCertVerificationError("certificate verify failed")

        def fake_urlopen(_req, timeout=None, context=None):
            raise cert_error

        with patch.object(security, "urlopen", side_effect=fake_urlopen), patch.object(security, "_is_production_environment", return_value=False):
            with self.assertRaises(ssl.SSLCertVerificationError):
                security._urlopen_with_ssl_fallback(request, timeout=5)

    # ---- TD-05 batch 1: fetch_registry self-audit invariants ----
    # These tests register synthetic SourceSpecs (not real production entries -
    # those start appearing in batch 2) purely to prove register()/validate_registry()
    # actually catch the violations they claim to catch, since an empty registry
    # would make the checks trivially pass without proving anything.

    def _register_temp_spec(self, spec):
        self.addCleanup(fetch_registry.REGISTRY.pop, spec.name, None)
        fetch_registry.register(spec)

    def test_fetch_registry_register_rejects_duplicate_name(self):
        self._register_temp_spec(fetch_registry.SourceSpec(name="td05_test_dup", url="https://example.com/a"))
        with self.assertRaises(ValueError):
            fetch_registry.register(fetch_registry.SourceSpec(name="td05_test_dup", url="https://example.com/b"))

    def test_fetch_registry_validate_registry_flags_empty_url(self):
        self._register_temp_spec(fetch_registry.SourceSpec(name="td05_test_empty_url", url=""))
        problems = fetch_registry.validate_registry()
        self.assertTrue(any("td05_test_empty_url" in problem and "url is empty" in problem for problem in problems))

    def test_fetch_registry_validate_registry_flags_unresolvable_parser(self):
        self._register_temp_spec(fetch_registry.SourceSpec(
            name="td05_test_bad_parser", url="https://example.com/a", parser="not-callable",
        ))
        problems = fetch_registry.validate_registry()
        self.assertTrue(any("td05_test_bad_parser" in problem and "parser is not callable" in problem for problem in problems))

    def test_fetch_registry_validate_registry_flags_ttl_not_a_named_constant(self):
        self._register_temp_spec(fetch_registry.SourceSpec(
            name="td05_test_bad_ttl", url="https://example.com/a", ttl_seconds=123456789,
        ))
        problems = fetch_registry.validate_registry()
        self.assertTrue(any("td05_test_bad_ttl" in problem and "ttl_seconds" in problem for problem in problems))

    def test_fetch_registry_validate_registry_passes_for_well_formed_entry(self):
        known_ttl = next(iter(fetch_registry._known_ttl_values()))
        self._register_temp_spec(fetch_registry.SourceSpec(
            name="td05_test_well_formed", url="https://example.com/a", parser=str, ttl_seconds=known_ttl,
        ))
        problems = fetch_registry.validate_registry()
        self.assertFalse(any("td05_test_well_formed" in problem for problem in problems))

    def test_fetch_from_registry_parses_and_caches_json_response(self):
        calls = {"count": 0}

        def fake_urlopen(_req, timeout=None):
            calls["count"] += 1
            response = MagicMock()
            response.read.return_value = b'{"value": 42}'
            response.headers = {}
            response.__enter__ = lambda self=response: self
            response.__exit__ = lambda self, *exc: False
            return response

        self._register_temp_spec(fetch_registry.SourceSpec(
            name="td05_test_fetch",
            url="https://example.com/data",
            parser=lambda payload: payload["value"],
            cache_bucket="td05_test_bucket",
            ttl_seconds=next(iter(fetch_registry._known_ttl_values())),
        ))
        self.addCleanup(cache.cache_data.pop, "td05_test_bucket", None)

        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", side_effect=fake_urlopen):
            first = fetch_registry.fetch_from_registry("td05_test_fetch")
            second = fetch_registry.fetch_from_registry("td05_test_fetch")

        self.assertEqual(first, 42)
        self.assertEqual(second, 42)
        self.assertEqual(calls["count"], 1, "second call must be served from cache, not a second HTTP request")

    # ---- TD-05 batch 2: TWSE core fetcher characterization ----
    # These patch fetch_registry._urlopen_with_ssl_fallback (the real network
    # choke point after migration), NOT fetchers.fetch_json - fetch_from_registry
    # builds its own Request rather than delegating to fetch_json, so a mock on
    # fetch_json would silently never be called post-migration and these tests
    # would stop testing anything. Each fake response is a context-manager mock
    # matching what `with _urlopen_with_ssl_fallback(...) as response:` expects.

    def _fake_json_response(self, payload):
        response = MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.headers = {}
        response.__enter__ = lambda self=response: self
        response.__exit__ = lambda self, *exc: False
        return response

    def test_fetch_twse_margin_summary_aggregates_rows(self):
        rows = [
            {"融資今日餘額": "100", "融資前日餘額": "80", "融券今日餘額": "10", "融券前日餘額": "5"},
            {"融資今日餘額": "50", "融資前日餘額": "50", "融券今日餘額": "0", "融券前日餘額": "0"},
        ]
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(rows)) as mock_urlopen:
            result = fetchers.fetch_twse_margin_summary()
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.TWSE_MARGIN_URL)
        self.assertEqual(timeout, 15)
        self.assertEqual(result["financingBalance"], 150.0)
        self.assertEqual(result["financingPrevious"], 130.0)
        self.assertEqual(result["financingChange"], 20.0)
        self.assertEqual(result["shortBalance"], 10.0)
        self.assertEqual(result["sourceLink"], fetchers.TWSE_MARGIN_URL)

    def test_fetch_stock_margin_trading_tpex_branch(self):
        stock = {"code": "1234", "market": "TPEX"}
        row = {
            "SecuritiesCompanyCode": "1234", "Date": "1150719", "MarginPurchase": "1", "MarginSales": "2",
            "CashRedemption": "3", "MarginPurchaseBalancePreviousDay": "10", "MarginPurchaseBalance": "12",
            "MarginPurchaseUtilizationRate": "5", "ShortConvering": "1", "ShortSale": "2",
            "StockRedemption": "0", "ShortSaleBalancePreviousDay": "4", "ShortSaleBalance": "5",
            "ShortSaleUtilizationRate": "1", "Offsetting": "0",
        }
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response([row])) as mock_urlopen:
            result = fetchers.fetch_stock_margin_trading(stock)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_tpex_openapi_url("tpex_mainboard_margin_balance"))
        self.assertEqual(timeout, 15)
        self.assertEqual(result["financingBalance"], 12.0)
        self.assertEqual(result["financingPrevious"], 10.0)
        self.assertEqual(result["financingChange"], 2.0)
        self.assertEqual(result["shortBalance"], 5.0)
        self.assertEqual(result["sourceNote"], "櫃買中心上櫃股票融資融券餘額。")

    def test_fetch_stock_margin_trading_twse_branch(self):
        stock = {"code": "2330", "market": "TWSE"}
        row = {
            "股票代號": "2330", "融資買進": "1", "融資賣出": "2", "融資現金償還": "0",
            "融資前日餘額": "10", "融資今日餘額": "12", "融券買進": "1", "融券賣出": "2",
            "融券現券償還": "0", "融券前日餘額": "4", "融券今日餘額": "5", "資券互抵": "0",
        }
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response([row])) as mock_urlopen:
            result = fetchers.fetch_stock_margin_trading(stock)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.TWSE_MARGIN_URL)
        self.assertEqual(timeout, 15)
        self.assertEqual(result["financingBalance"], 12.0)
        self.assertEqual(result["financingPrevious"], 10.0)
        self.assertEqual(result["shortBalance"], 5.0)
        self.assertEqual(result["sourceLink"], fetchers.TWSE_MARGIN_URL)

    def test_fetch_twse_listed_industry_map_builds_code_to_industry_map(self):
        rows = [{"公司代號": "2330", "產業別": "24"}]
        with cache.cache_lock:
            cache.cache_data.pop("twse_company_industries", None)
        self.addCleanup(lambda: cache.cache_data.pop("twse_company_industries", None))
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(rows)) as mock_urlopen:
            result = fetchers.fetch_twse_listed_industry_map(timeout=12)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, f"{fetchers.TWSE_OPENAPI_BASE}/opendata/t187ap03_L")
        self.assertEqual(timeout, 12)
        self.assertEqual(result, {"2330": fetchers.TWSE_INDUSTRY_CODE_NAMES["24"]})

    def test_fetch_stock_institutions_payload_near_scans_backward_on_empty_dataset(self):
        empty_payload = {"stat": "OK!not-a-stat-match", "data": []}
        good_payload = {"stat": "OK", "data": [["x"]]}
        with patch.object(
            fetch_registry, "_urlopen_with_ssl_fallback",
            side_effect=[self._fake_json_response(empty_payload), self._fake_json_response(good_payload)],
        ) as mock_urlopen:
            payload, used_date = fetchers.fetch_stock_institutions_payload_near("20260721", lookback_days=3)
        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(payload, good_payload)
        self.assertEqual(used_date, "20260720")

    def test_fetch_stock_valuation_tpex_branch(self):
        stock = {"code": "1234", "market": "TPEX"}
        row = {
            "SecuritiesCompanyCode": "1234", "Date": "1150719", "PriceEarningRatio": "10.5",
            "YieldRatio": "2.1", "PriceBookRatio": "1.5", "DividendPerShare": "1.0",
        }
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response([row])) as mock_urlopen:
            result = fetchers.fetch_stock_valuation(stock)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_tpex_openapi_url("tpex_mainboard_peratio_analysis"))
        self.assertEqual(timeout, 10)
        self.assertEqual(result["peRatio"], "10.5")
        self.assertEqual(result["dividendYield"], "2.1")
        self.assertEqual(result["date"], "2026-07-19")

    def test_fetch_stock_valuation_twse_branch(self):
        stock = {"code": "2330", "market": "TWSE"}
        row = {"Code": "2330", "Date": "1150719", "PEratio": "18.2", "DividendYield": "1.9", "PBratio": "5.1"}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response([row])) as mock_urlopen:
            result = fetchers.fetch_stock_valuation(stock)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, f"{fetchers.TWSE_OPENAPI_BASE}/exchangeReport/BWIBBU_ALL")
        self.assertEqual(timeout, 10)
        self.assertEqual(result["peRatio"], "18.2")
        self.assertEqual(result["dividendYield"], "1.9")

    def test_fetch_stock_valuation_on_date_tpex_branch(self):
        stock = {"code": "1234", "market": "TPEX"}
        payload = {"date": "20260719", "tables": [{"data": [["1234", "x", "10.5", "1.0", "x", "2.1", "1.5"]]}]}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_stock_valuation_on_date(stock, "20260719")
        request, timeout = mock_urlopen.call_args[0]
        expected_url = "https://www.tpex.org.tw/www/zh-tw/afterTrading/peQryDate?" + fetchers.urlencode(
            {"date": "2026/07/19", "id": "", "response": "json"}
        )
        self.assertEqual(request.full_url, expected_url)
        self.assertEqual(timeout, 15)
        self.assertEqual(result["peRatio"], 10.5)
        self.assertEqual(result["dividendYield"], 2.1)
        self.assertEqual(result["pbRatio"], 1.5)

    def test_fetch_stock_valuation_on_date_twse_branch(self):
        stock = {"code": "2330", "market": "TWSE"}
        payload = {"date": "20260719", "data": [["2330", "x", "500", "2.0", "x", "18.2", "5.1"]]}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_stock_valuation_on_date(stock, "20260719")
        request, timeout = mock_urlopen.call_args[0]
        expected_url = f"{fetchers.TWSE_BASE}/rwd/zh/afterTrading/BWIBBU_d?" + fetchers.urlencode(
            {"date": "20260719", "selectType": "ALL", "response": "json"}
        )
        self.assertEqual(request.full_url, expected_url)
        self.assertEqual(timeout, 15)
        self.assertEqual(result["peRatio"], 18.2)
        self.assertEqual(result["dividendYield"], 2.0)
        self.assertEqual(result["dividendPerShare"], round(500 * 2.0 / 100, 4))

    def test_fetch_stock_company_profile_tpex_branch(self):
        stock = {"code": "1234", "name": "Fallback Name", "market": "TPEX"}
        row = {
            "SecuritiesCompanyCode": "1234", "CompanyName": "測試公司", "SecuritiesIndustryCode": "24",
            "Chairman": "王小明", "GeneralManager": "李小華", "Paidin.Capital.NTDollars": "1000000000",
            "DateOfIncorporation": "19900101", "DateOfListing": "20000101", "Address": "台北市",
            "Telephone": "02-1234", "WebAddress": "https://example.com",
        }
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response([row])) as mock_urlopen:
            result = fetchers.fetch_stock_company_profile(stock)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_tpex_openapi_url("mopsfin_t187ap03_O"))
        self.assertEqual(timeout, 10)
        self.assertEqual(result["fullName"], "測試公司")
        self.assertEqual(result["chairman"], "王小明")
        self.assertEqual(result["capital"], fetchers.format_company_capital("1000000000"))

    def test_fetch_stock_company_profile_twse_branch(self):
        stock = {"code": "2330", "name": "Fallback Name", "market": "TWSE"}
        row = {
            "公司代號": "2330", "公司名稱": "台積電", "產業別": "半導體業", "董事長": "劉德音",
            "總經理": "魏哲家", "實收資本額": "259304805200", "成立日期": "760221",
            "上市日期": "870704", "地址": "新竹市", "總機電話": "03-5636688", "網址": "https://tsmc.com",
        }
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response([row])) as mock_urlopen:
            result = fetchers.fetch_stock_company_profile(stock)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, f"{fetchers.TWSE_OPENAPI_BASE}/opendata/t187ap03_L")
        self.assertEqual(timeout, 10)
        self.assertEqual(result["fullName"], "台積電")
        self.assertEqual(result["chairman"], "劉德音")

    # ---- TD-05 batch 3: TWSE institutional/history fetcher characterization ----
    # fetch_stock_institutional_trades and fetch_stock_institutional_trade_history
    # are unchanged in this batch (the former calls the shared find_latest_dataset
    # retry helper, unrelated to any single SourceSpec; the latter is a pure
    # ThreadPoolExecutor fan-out over fetch_stock_institutional_trade_for_date and
    # benefits from that function's migration transparently) - no new tests needed
    # for functions with zero behavioral surface changed.

    def test_fetch_stock_institutional_trade_for_date_retries_and_delegates_to_builder(self):
        stock = {"code": "2330"}
        payload = {"stat": "OK", "data": [["2330", "x"]]}
        sentinel = {"date": "2026-07-19"}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen, \
                patch.object(app, "build_stock_institutional_trade_record", return_value=sentinel) as mock_builder:
            result = fetchers.fetch_stock_institutional_trade_for_date(stock, "20260719")
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_stock_institutions_url("20260719"))
        self.assertEqual(timeout, 10)
        mock_builder.assert_called_once_with(["2330", "x"], "20260719")
        self.assertEqual(result, sentinel)

    def test_fetch_stock_history_rows_uses_stock_day_registry_entry(self):
        payload = {"data": [["115/07/01", "x"], ["115/07/02", "y"]]}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            rows = fetchers.fetch_stock_history_rows("2330", "20260719", months_back=1)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_stock_day_url(fetchers.shift_month("20260719", 0), "2330"))
        self.assertEqual(timeout, fetchers.STOCK_HISTORY_TIMEOUT_SECONDS)
        self.assertEqual(len(rows), 2)

    def test_fetch_recent_trade_rows_uses_stock_day_registry_entry(self):
        payload = {"data": [["115/07/01", "a", "b", "c", "d", "e", "f", "g", "h"]]}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            rows = fetchers.fetch_recent_trade_rows("2330", "20260719")
        self.assertEqual(mock_urlopen.call_count, fetchers.SECTOR_CHART_TRADE_MONTHS)
        _, timeout = mock_urlopen.call_args[0]
        self.assertEqual(timeout, fetchers.SECTOR_CHART_TRADE_TIMEOUT_SECONDS)
        self.assertEqual(len(rows), 1)

    def test_fetch_live_index_activity_returns_payload_when_dataset_has_rows(self):
        payload = {"stat": "OK", "data": [["x"]]}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_live_index_activity("20260719")
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_index_activity_url("20260719"))
        self.assertEqual(timeout, 10)
        self.assertEqual(result, payload)

    def test_fetch_live_index_activity_returns_none_on_fetch_error(self):
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", side_effect=RuntimeError("boom")):
            result = fetchers.fetch_live_index_activity("20260719")
        self.assertIsNone(result)

    def test_fetch_live_index_intraday_returns_payload_when_dataset_has_rows(self):
        payload = {"stat": "OK", "data": [["x"]]}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_live_index_intraday("20260719")
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_index_intraday_url("20260719"))
        self.assertEqual(timeout, 10)
        self.assertEqual(result, payload)

    # ---- TD-05 batch 4: TWSE/TPEX misc + fan-out characterization ----
    # fetch_live_stock_universe and fetch_live_stock_search_results are unchanged
    # in this batch - both are pure orchestration (ThreadPoolExecutor fan-out over
    # find_latest_dataset + fetch_tpex_mainboard_quotes + fetch_yahoo_tpex_etfs,
    # plus deferred app.* parsers) with no direct fetch_json/fetch_text calls of
    # their own; they benefit from the two functions below being migrated without
    # any changes of their own, so no new tests needed for them specifically.

    def _fake_text_response(self, text, content_type=""):
        response = MagicMock()
        response.read.return_value = text.encode("utf-8")
        response.headers = {"Content-Type": content_type}
        response.__enter__ = lambda self=response: self
        response.__exit__ = lambda self, *exc: False
        return response

    def test_fetch_yahoo_tpex_etfs_parses_code_to_name_map(self):
        html = (
            'blah <a href="https://tw.stock.yahoo.com/quote/1234.TWO">'
            '<div class="Lh(20px)">測試ETF</div></a>'
        )
        with cache.cache_lock:
            cache.cache_data.pop("external_text", None)
        self.addCleanup(lambda: cache.cache_data.pop("external_text", None))
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_text_response(html)) as mock_urlopen:
            result = fetchers.fetch_yahoo_tpex_etfs(timeout=8)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.YAHOO_TPEX_ETF_URL)
        self.assertEqual(timeout, 8)
        self.assertEqual(result, {"1234": "測試ETF"})

    def test_fetch_yahoo_tpex_etfs_second_call_served_from_cache(self):
        html = (
            'blah <a href="https://tw.stock.yahoo.com/quote/1234.TWO">'
            '<div class="Lh(20px)">測試ETF</div></a>'
        )
        with cache.cache_lock:
            cache.cache_data.pop("external_text", None)
        self.addCleanup(lambda: cache.cache_data.pop("external_text", None))
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_text_response(html)) as mock_urlopen:
            fetchers.fetch_yahoo_tpex_etfs(timeout=8)
            fetchers.fetch_yahoo_tpex_etfs(timeout=8)
        self.assertEqual(mock_urlopen.call_count, 1, "second call must be served from the external_text cache")

    def test_fetch_tpex_mainboard_quotes_extracts_snapshot_date(self):
        payload = [{"Date": "1150719", "SecuritiesCompanyCode": "1234"}]
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            rows, snapshot_date = fetchers.fetch_tpex_mainboard_quotes(timeout=10)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_tpex_openapi_url("tpex_mainboard_quotes"))
        self.assertEqual(timeout, 10)
        self.assertEqual(rows, payload)
        self.assertEqual(snapshot_date, fetchers.parse_compact_roc_date("1150719"))

    # ---- TD-05 batch 5: Yahoo Finance global core characterization ----
    # fetch_market_volatility_indicator, fetch_international_market_indexes,
    # fetch_taiex_spot_snapshot, fetch_yahoo_spot_snapshot,
    # fetch_yahoo_trading_dates_for_institutional_range, and fetch_yahoo_history_rows
    # are all unchanged in this batch - each is pure orchestration over
    # fetch_yahoo_chart/fetch_yahoo_symbol_chart (confirmed by reading each in full,
    # zero direct fetch_json calls), so they benefit from those two functions'
    # migration transparently. The plan flagged fetch_market_volatility_indicator
    # for a shape check before assuming it was registry-eligible; it turned out to
    # be an orchestrator, not a flat fetcher - this is exactly the kind of
    # re-verification-at-batch-time the plan called for.

    def test_fetch_yahoo_chart_unwraps_first_chart_result(self):
        payload = {"chart": {"result": [{"timestamp": [1]}]}}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_yahoo_chart("2330", range_name="5d", interval="1d", market="TWSE")
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_yahoo_chart_url("2330", "5d", "1d", "TWSE"))
        self.assertEqual(timeout, 10)
        self.assertEqual(result, {"timestamp": [1]})

    def test_fetch_yahoo_chart_returns_none_when_no_results(self):
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response({"chart": {"result": []}})):
            result = fetchers.fetch_yahoo_chart("2330")
        self.assertIsNone(result)

    def test_fetch_yahoo_symbol_chart_unwraps_first_chart_result(self):
        payload = {"chart": {"result": [{"timestamp": [1, 2]}]}}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_yahoo_symbol_chart("^VIX", "3mo", "1d")
        request, timeout = mock_urlopen.call_args[0]
        expected_params = fetchers.urlencode({"range": "3mo", "interval": "1d", "includePrePost": "false"})
        self.assertEqual(request.full_url, f"{fetchers.YAHOO_CHART_BASE}/%5EVIX?{expected_params}")
        self.assertEqual(timeout, 10)
        self.assertEqual(result, {"timestamp": [1, 2]})

    def test_fetch_yahoo_quote_summary_unwraps_first_result(self):
        payload = {"quoteSummary": {"result": [{"price": {"regularMarketPrice": 123.4}}]}}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_yahoo_quote_summary("AAPL")
        request, timeout = mock_urlopen.call_args[0]
        expected_params = fetchers.urlencode({"modules": fetchers.YAHOO_QUOTE_SUMMARY_MODULES})
        self.assertEqual(request.full_url, f"{fetchers.YAHOO_QUOTE_SUMMARY_BASE}/AAPL?{expected_params}")
        self.assertEqual(timeout, 10)
        self.assertEqual(result, {"price": {"regularMarketPrice": 123.4}})

    def test_fetch_yahoo_spot_snapshot_derives_change_from_migrated_chart(self):
        """Integration check: fetch_yahoo_spot_snapshot -> fetch_yahoo_symbol_chart -> registry, end to end."""
        payload = {
            "chart": {"result": [{
                "meta": {"regularMarketPrice": 110.0, "chartPreviousClose": 100.0},
                "timestamp": [1, 2],
                "indicators": {"quote": [{"close": [100.0, 110.0], "open": [99.0, 108.0], "high": [111.0, 111.0], "low": [98.0, 107.0], "volume": [1000, 2000]}]},
            }]},
        }
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_yahoo_spot_snapshot("^TWII", "台灣加權指數")
        request, _ = mock_urlopen.call_args[0]
        expected_params = fetchers.urlencode({"range": "5d", "interval": "1d", "includePrePost": "false"})
        self.assertEqual(request.full_url, f"{fetchers.YAHOO_CHART_BASE}/%5ETWII?{expected_params}")
        self.assertEqual(result["value"], 110.0)
        self.assertEqual(result["change"], 10.0)

    # ---- TD-05 batch 6: Yahoo Finance global remainder characterization ----
    # fetch_us_market_overview_news (ThreadPoolExecutor fan-out over
    # fetch_yahoo_us_symbol_news) and fetch_taiwan_option_spot_snapshot
    # (dispatches to fetch_taiex_spot_snapshot/fetch_yahoo_spot_snapshot, both
    # already registry-backed since batch 5) are unchanged - pure orchestration,
    # confirmed by reading each in full. fetch_yahoo_options_payload and its
    # get_yahoo_options_crumb helper are the plan's documented cookie-jar
    # exception (own _yahoo_options_opener, bypasses _urlopen_with_ssl_fallback
    # entirely) - confirmed unchanged, already covered by the existing
    # test_fetch_yahoo_options_payload_reaches_cboe_expiration_parser regression
    # guard from TD-01, which still passes untouched.

    def test_fetch_yahoo_us_symbol_news_maps_items(self):
        payload = {"news": [{"title": "Headline", "publisher": "Reuters", "providerPublishTime": 1750000000, "link": "https://example.com/a"}]}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_yahoo_us_symbol_news("AAPL", limit=6)
        request, timeout = mock_urlopen.call_args[0]
        expected_params = fetchers.urlencode({"q": "AAPL", "quotesCount": "0", "newsCount": "6", "enableFuzzyQuery": "false"})
        self.assertEqual(request.full_url, f"{fetchers.YAHOO_SEARCH_BASE}?{expected_params}")
        self.assertEqual(timeout, 8)
        self.assertEqual(result[0]["title"], "Headline")
        self.assertEqual(result[0]["source"], "Reuters")
        self.assertEqual(result[0]["link"], "https://example.com/a")

    def test_fetch_yahoo_us_market_search_filters_by_quote_type_and_exchange(self):
        payload = {"quotes": [
            {"quoteType": "EQUITY", "symbol": "AAPL", "exchange": "NMS", "shortname": "Apple Inc."},
            {"quoteType": "EQUITY", "symbol": "AAPL.TW", "exchange": "NMS", "shortname": "Wrong market"},
            {"quoteType": "CRYPTOCURRENCY", "symbol": "BTC-USD", "exchange": "CCC"},
        ]}
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(payload)) as mock_urlopen:
            result = fetchers.fetch_yahoo_us_market_search("apple", limit=20)
        request, timeout = mock_urlopen.call_args[0]
        expected_params = fetchers.urlencode({"q": "apple", "quotesCount": "20", "newsCount": "0", "enableFuzzyQuery": "true"})
        self.assertEqual(request.full_url, f"{fetchers.YAHOO_SEARCH_BASE}?{expected_params}")
        self.assertEqual(timeout, 8)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], "AAPL")

    def test_fetch_yahoo_us_market_search_empty_query_returns_empty_without_fetching(self):
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback") as mock_urlopen:
            result = fetchers.fetch_yahoo_us_market_search("   ", limit=20)
        mock_urlopen.assert_not_called()
        self.assertEqual(result, [])

    # ---- TD-05 batch 7: TAIFEX simple lookups + Finding B TTL promotion ----
    # The rest of the 13-function TAIFEX cluster (download candles, daily market
    # report scan loop, price/technical candle orchestrators, all 3 open-interest
    # functions) turned out NOT to be registry-eligible under re-verification:
    # each is either a FORM-POST fetch (fetch_form_text - the registry has no FORM
    # support, matching the plan's own prediction this would be rarely used given
    # how structurally complex TAIFEX's form endpoints already are) or a pure
    # orchestrator over other hand-written functions. Deferred to batch 8's
    # explicit "stays hand-written" confirmation pass rather than forced in here.

    def test_fetch_taifex_latest_futures_market_snapshot_uses_registry_entry(self):
        rows = [{"symbol": "TX"}]
        with patch.object(fetchers, "select_taifex_daily_market_row", return_value=rows[0]) as mock_select, \
                patch.object(fetchers, "normalize_taifex_daily_market_row", return_value={"date": "2026-07-19"}), \
                patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_json_response(rows)) as mock_urlopen:
            result = fetchers.fetch_taifex_latest_futures_market_snapshot("TX")
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.TAIFEX_FUTURES_DAILY_OPENAPI_URL)
        self.assertEqual(timeout, 15)
        mock_select.assert_called_once_with(rows, "TX")
        self.assertEqual(result["date"], "2026-07-19")
        self.assertEqual(result["sourceLink"], fetchers.TAIFEX_FUTURES_DAILY_OPENAPI_URL)

    def test_fetch_taifex_previous30_tick_dates_extracts_and_dedupes(self):
        html = "Daily_2026_07_17.zip Daily_2026_07_16.zip Daily_2026_07_17.zip"
        with cache.cache_lock:
            cache.cache_data.pop("external_text", None)
        self.addCleanup(lambda: cache.cache_data.pop("external_text", None))
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_text_response(html)) as mock_urlopen:
            dates = fetchers.fetch_taifex_previous30_tick_dates()
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.TAIFEX_FUTURES_PREVIOUS30_SALES_URL)
        self.assertEqual(timeout, 15)
        self.assertEqual(dates, ["2026-07-17", "2026-07-16"])

    def test_fetch_taifex_previous30_futures_tick_candles_fetches_binary_per_date(self):
        with patch.object(fetchers, "fetch_taifex_previous30_tick_dates", return_value=["2026-07-17"]), \
                patch.object(fetchers, "parse_taifex_daily_tick_csv_candle", return_value={"time": "2026-07-17"}) as mock_parse, \
                patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=self._fake_text_response("binary-ish")) as mock_urlopen:
            candles = fetchers.fetch_taifex_previous30_futures_tick_candles("TX", max_observations=5)
        request, timeout = mock_urlopen.call_args[0]
        self.assertEqual(request.full_url, fetchers.build_taifex_daily_tick_csv_url("2026-07-17"))
        self.assertEqual(timeout, 20)
        mock_parse.assert_called_once()
        self.assertEqual(candles, [{"time": "2026-07-17"}])

    def test_yahoo_tw_future_technical_candle_ttl_is_named_constant_not_literal(self):
        """Finding B regression guard: the TTL must come from a named constant."""
        self.assertEqual(fetchers.YAHOO_TW_FUTURE_TECHNICAL_CANDLE_CACHE_SECONDS, 900)
        cache_key = "TX:TX01:202607:day"
        with cache.cache_lock:
            cache.cache_data.setdefault("yahoo_tw_future_technical_candles", {})[cache_key] = {
                "stored_at": time.time(), "payload": {"sentinel": True},
            }
        self.addCleanup(lambda: cache.cache_data.pop("yahoo_tw_future_technical_candles", None))
        cached = cache.read_memory_cache(
            "yahoo_tw_future_technical_candles", cache_key, fetchers.YAHOO_TW_FUTURE_TECHNICAL_CANDLE_CACHE_SECONDS,
        )
        self.assertEqual(cached, {"sentinel": True})

    # ---- TD-05 batch 8: TAIFEX complex fetchers stay hand-written + TTL merge ----
    # fetch_taifex_txo_option_chain (12-day scan + leader/follower coalescing +
    # FORM-POST + direct cache_data manipulation), fetch_taifex_openapi_list (a
    # generic caller-parameterized cache wrapper, not a single fixed source - its
    # url/cache_seconds come from the CALLER, so it doesn't fit a one-row
    # SourceSpec any more than fetch_json itself would), fetch_taifex_institution_detail_rows
    # (thin dispatcher delegating to fetch_taifex_openapi_list), and
    # fetch_taiwan_option_chain (TAIFEX-vs-Yahoo source-mode dispatcher/fallback)
    # are all confirmed unchanged by reading each in full - no new fetch tests
    # needed since none of their fetch behavior changed.

    def test_options_chain_cache_seconds_merged_across_modules(self):
        """TD-12: US_/YAHOO_/BARCHART_/TAIFEX_OPTIONS_CHAIN_CACHE_SECONDS (4 names,
        all 300s) are now one constant, imported from market_config by both
        fetchers.py and builders.py - not 4 independently-declared 300s."""
        self.assertEqual(market_config.OPTIONS_CHAIN_CACHE_SECONDS, 300)
        self.assertIs(fetchers.OPTIONS_CHAIN_CACHE_SECONDS, market_config.OPTIONS_CHAIN_CACHE_SECONDS)
        self.assertIs(builders.OPTIONS_CHAIN_CACHE_SECONDS, market_config.OPTIONS_CHAIN_CACHE_SECONDS)
        for removed_name in (
            "US_OPTIONS_CHAIN_CACHE_SECONDS", "YAHOO_OPTIONS_CHAIN_CACHE_SECONDS",
            "BARCHART_OPTIONS_CHAIN_CACHE_SECONDS", "TAIFEX_OPTIONS_CHAIN_CACHE_SECONDS",
        ):
            self.assertFalse(hasattr(builders, removed_name))
            self.assertFalse(hasattr(fetchers, removed_name))
            self.assertFalse(hasattr(market_config, removed_name))


if __name__ == "__main__":
    unittest.main()
