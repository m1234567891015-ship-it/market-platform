"""P4-01 provider transport boundary and behavior regressions."""
from __future__ import annotations

import ast
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")

import builders
import fetchers


class _Response:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._payload


class _Opener:
    def __init__(self, payload: dict):
        self.payload = payload
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return _Response(self.payload)


class P401BuildersFetchersDomainTests(unittest.TestCase):
    def test_builders_has_no_outbound_transport_calls(self):
        tree = ast.parse((ROOT / "builders.py").read_text(encoding="utf-8"))
        forbidden = {
            "fetch_json",
            "fetch_text",
            "Request",
            "urlopen",
            "build_opener",
            "_urlopen_with_ssl_fallback",
        }
        calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else ""
            if name in forbidden:
                calls.append((name, node.lineno))
        self.assertEqual(calls, [])

    def test_twse_and_tpex_named_fetchers_preserve_url_and_timeout(self):
        cases = [
            (fetchers.fetch_twse_market_payload, "20260718", fetchers.build_market_url("20260718"), 41),
            (fetchers.fetch_twse_index_activity_payload, "20260718", fetchers.build_index_activity_url("20260718"), 42),
            (fetchers.fetch_twse_index_intraday_payload, "20260718", fetchers.build_index_intraday_url("20260718"), 43),
            (fetchers.fetch_twse_weighted_index_history_payload, "20260701", fetchers.build_weighted_index_history_url("20260701"), 44),
            (fetchers.fetch_twse_institutions_daily_payload, "20260718", fetchers.build_institutions_url("20260718"), 45),
            (fetchers.fetch_tpex_openapi_payload, "tpex_esb_highlight", fetchers.build_tpex_openapi_url("tpex_esb_highlight"), 46),
        ]
        with patch.object(fetchers, "fetch_json", return_value={"fixture": True}) as fetch_json:
            for adapter, argument, expected_url, timeout in cases:
                with self.subTest(adapter=adapter.__name__):
                    self.assertEqual(adapter(argument, timeout=timeout), {"fixture": True})
                    fetch_json.assert_called_with(expected_url, timeout=timeout)

    def test_yahoo_class_page_adapter_preserves_url_and_timeout(self):
        with patch.object(fetchers, "fetch_text", return_value="<html>fixture</html>") as fetch_text:
            result = fetchers.fetch_yahoo_class_quote_page("https://example.test/class", timeout=13)
        self.assertEqual(result, "<html>fixture</html>")
        fetch_text.assert_called_once_with("https://example.test/class", timeout=13)

    def test_malformed_provider_data_and_invalid_numeric_contracts_fail_closed(self):
        with patch.object(fetchers, "fetch_json", side_effect=json.JSONDecodeError("fixture malformed", "{", 0)):
            with self.assertRaises(json.JSONDecodeError):
                fetchers.fetch_twse_market_payload("20260718")

        self.assertIsNone(fetchers.normalize_barchart_option_contract(
            {"strike": "not-a-number"}, "call", None, None,
        ))
        self.assertIsNone(fetchers.normalize_deribit_option_contract({"instrument_name": "unrecognized"}))
        self.assertIsNone(fetchers.normalize_bybit_option_contract({"symbol": "unrecognized"}, "SOL"))

        with patch.object(fetchers, "fetch_json", return_value={"result": {"list": [
            {"symbol": "unrecognized", "lastPrice": "999", "underlyingPrice": "123"},
        ]}}):
            invalid = fetchers.fetch_bybit_options_chain_data("SOL")
        self.assertEqual(invalid["contracts"], [])
        self.assertEqual(invalid["underlyingPricesByExpiration"], {})

    def test_latest_twse_adapters_keep_provider_date_search_contract(self):
        validator = object()
        with patch.object(fetchers, "find_latest_dataset", return_value=({}, "20260718")) as find_latest:
            self.assertEqual(fetchers.fetch_latest_twse_market_payload(validator, 7), ({}, "20260718"))
            find_latest.assert_called_once_with(fetchers.build_market_url, lookback_days=7, validator=validator)
            find_latest.reset_mock()
            self.assertEqual(fetchers.fetch_latest_twse_institutions_payload(7), ({}, "20260718"))
            find_latest.assert_called_once_with(fetchers.build_institutions_url, lookback_days=7)

    def test_barchart_cookie_request_and_normalized_result_stay_inside_fetcher(self):
        opener = _Opener({
            "data": {
                "Call": [{"strike": "100", "lastPrice": "2.5", "bidPrice": "2.4", "askPrice": "2.6", "longSymbol": "GCZ6 C100"}],
                "Put": [{"strike": "95", "lastPrice": "1.2", "openInterest": "8", "symbol": "GCZ6 P95"}],
            },
        })
        context = {
            "contract": "GCZ6",
            "pageUrl": "https://www.barchart.com/futures/quotes/GC*0/options",
            "opener": opener,
            "xsrf": "token%2Fvalue",
            "expiration": 1798761600,
            "expirationDate": "2026-12-31",
            "weightedImpliedVolatility": 0.21,
            "optionPointValue": 100,
            "price": 4100.5,
        }
        with patch.object(fetchers, "fetch_barchart_options_context", return_value=context):
            result = fetchers.fetch_barchart_futures_options_payload("GC", "GCZ6")

        self.assertEqual(opener.timeout, 30)
        self.assertEqual(opener.request.get_header("X-xsrf-token"), "token/value")
        query = parse_qs(urlsplit(opener.request.full_url).query)
        self.assertEqual(query["symbol"], ["GCZ6"])
        self.assertEqual(query["groupBy"], ["optionType"])
        self.assertEqual(result["contractSymbol"], "GCZ6")
        self.assertEqual(result["calls"][0]["type"], "call")
        self.assertEqual(result["calls"][0]["strike"], 100.0)
        self.assertEqual(result["puts"][0]["type"], "put")
        self.assertEqual(result["expirationDate"], "2026-12-31")
        self.assertEqual(result["sourceUrl"], context["pageUrl"])
        self.assertNotIn("opener", result)

    def test_barchart_empty_envelope_stays_empty(self):
        opener = _Opener({"data": {"Call": [], "Put": []}})
        context = {
            "contract": "GCZ6", "pageUrl": "https://example.test/options", "opener": opener,
            "xsrf": "", "expiration": None, "expirationDate": None,
        }
        with patch.object(fetchers, "fetch_barchart_options_context", return_value=context):
            result = fetchers.fetch_barchart_futures_options_payload("GC")
        self.assertEqual(result["calls"], [])
        self.assertEqual(result["puts"], [])

    def test_deribit_adapter_is_deterministic_and_preserves_provider_failure(self):
        payload = {"result": [{
            "instrument_name": "BTC-31JUL26-100000-C", "mark_price": "0.03", "bid_price": "0.02",
            "ask_price": "0.04", "volume": "3", "open_interest": "9", "mark_iv": "0.6",
            "underlying_price": "101000",
        }]}
        with patch.object(fetchers, "fetch_json", return_value=payload) as fetch_json:
            first = fetchers.fetch_deribit_options_chain_data("BTC")
            second = fetchers.fetch_deribit_options_chain_data("BTC")
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual(first["contracts"][0]["type"], "call")
        self.assertEqual(first["contracts"][0]["strike"], 100000.0)
        self.assertEqual(first["underlyingPricesByExpiration"][first["contracts"][0]["expiration"]], [101000.0])
        self.assertEqual(fetch_json.call_count, 2)
        with patch.object(fetchers, "fetch_json", side_effect=TimeoutError("fixture timeout")):
            with self.assertRaisesRegex(TimeoutError, "fixture timeout"):
                fetchers.fetch_deribit_options_chain_data("BTC")

    def test_bybit_adapter_is_deterministic_and_keeps_error_message(self):
        payload = {"retMsg": "fixture unavailable", "result": {"list": [
            {"symbol": "SOL-31JUL26-100-C-USDT", "lastPrice": "2.5", "bid1Price": "2.4",
             "ask1Price": "2.6", "markIv": "0.65", "volume24h": "12", "openInterest": "30",
             "underlyingPrice": "101.25"},
            {"symbol": "SOL-31JUL26-100-P-USDT", "lastPrice": "1.8", "openInterest": "22", "indexPrice": "101.25"},
        ]}}
        with patch.object(fetchers, "fetch_json", return_value=payload):
            first = fetchers.fetch_bybit_options_chain_data("SOL")
            second = fetchers.fetch_bybit_options_chain_data("SOL")
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertEqual([item["type"] for item in first["contracts"]], ["call", "put"])
        expiration = first["contracts"][0]["expiration"]
        self.assertEqual(first["underlyingPricesByExpiration"][expiration], [101.25, 101.25])
        with patch.object(fetchers, "fetch_json", return_value={"retMsg": "provider failed", "result": {"list": []}}):
            empty = fetchers.fetch_bybit_options_chain_data("SOL")
        self.assertEqual(empty["contracts"], [])
        self.assertEqual(empty["errorMessage"], "provider failed")

    def test_bybit_builder_output_is_deterministic_and_empty_stays_error(self):
        import app

        expiration = 1785456000
        provider = {
            "contracts": [{
                "contractSymbol": "SOL-31JUL26-100-C-USDT", "strike": 100.0, "lastPrice": 2.5,
                "bid": 2.4, "ask": 2.6, "change": None, "percentChange": None, "volume": 12.0,
                "openInterest": 30.0, "impliedVolatility": 0.65, "expiration": expiration,
                "expirationDate": "2026-07-31", "inTheMoney": None, "delta": None, "gamma": None,
                "theta": None, "vega": None, "type": "call",
            }],
            "underlyingPricesByExpiration": {expiration: [101.25]},
            "errorMessage": "provider returned no contracts",
            "sourceUrl": "https://api.bybit.com/v5/market/tickers?category=option&baseCoin=SOL",
        }
        with patch.object(app, "global_market_refresh_requested", return_value=True), \
                patch.object(builders, "fetch_bybit_options_chain_data", return_value=provider), \
                patch.object(builders, "write_memory_cache"):
            first = builders.build_bybit_options_chain("BYBIT_SOL")
            second = builders.build_bybit_options_chain("BYBIT_SOL")
        comparable = lambda payload: {key: value for key, value in payload.items() if key != "timestamp"}
        self.assertEqual(json.dumps(comparable(first), sort_keys=True), json.dumps(comparable(second), sort_keys=True))
        self.assertEqual(first["price"], 101.25)
        self.assertEqual(first["summary"]["callCount"], 1)

        provider["contracts"] = []
        with patch.object(app, "global_market_refresh_requested", return_value=True), \
                patch.object(builders, "fetch_bybit_options_chain_data", return_value=provider):
            empty = builders.build_bybit_options_chain("BYBIT_SOL")
        self.assertEqual(empty["error"], "provider returned no contracts")
        self.assertEqual(empty["sourceUrl"], provider["sourceUrl"])


if __name__ == "__main__":
    unittest.main()
