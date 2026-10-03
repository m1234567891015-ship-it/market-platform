import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fetch_registry
import fetchers


class FakeResponse(BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


class FetchRegistryBomTests(unittest.TestCase):
    source_name = "regression_utf8_bom_json"
    LIVE_TAIFEX_HEADER = (
        "日期,契約代號,到期月份(週別),開盤價,最高價,最低價,最後成交價,漲跌價,漲跌%,"
        "合計成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,"
        "是否因訊息面暫停交易,交易時段,價差對單式委託成交量"
    )
    LIVE_TAIFEX_ROW = (
        "20261002,TX,202610,22000,22100,21900,22050,100,0.46%,12345,22050,45678,"
        "22049,22051,22100,19000,否,一般,0"
    )

    @classmethod
    def setUpClass(cls):
        fetch_registry.register(fetch_registry.SourceSpec(
            name=cls.source_name,
            url="https://example.invalid/regression.json",
        ))

    @classmethod
    def tearDownClass(cls):
        fetch_registry.REGISTRY.pop(cls.source_name, None)

    def fetch_payload(self, raw, source_name=None):
        response = FakeResponse(raw)
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=response):
            return fetch_registry.fetch_from_registry(source_name or self.source_name)

    def test_plain_utf8_json_is_unchanged_for_non_taifex_provider(self):
        expected = {"provider": "other", "rows": [1, 2]}
        self.assertEqual(self.fetch_payload(json.dumps(expected).encode("utf-8")), expected)

    def test_single_leading_utf8_bom_parses_valid_json(self):
        raw = b"\xef\xbb\xbf" + b'{"ok":true,"value":7}'
        self.assertEqual(self.fetch_payload(raw), {"ok": True, "value": 7})

    def test_internal_u_feff_in_json_string_is_preserved(self):
        expected = {"text": "left\ufeffright"}
        self.assertEqual(self.fetch_payload(json.dumps(expected).encode("utf-8")), expected)

    def test_malformed_empty_html_invalid_bytes_and_nonleading_bom_fail(self):
        invalid_payloads = (
            b"{not-json",
            b"",
            b"<!doctype html><html>error</html>",
            b"\xff\xfe\xfa",
            b'{"ok":true}\xef\xbb\xbf',
            b"\xef\xbb\xbf\xef\xbb\xbf{\"ok\":true}",
        )
        for raw in invalid_payloads:
            with self.subTest(raw=raw), self.assertRaises((json.JSONDecodeError, UnicodeDecodeError)):
                self.fetch_payload(raw)

    def test_taifex_tx_fixture_parses_market_date(self):
        fixture = [{
            "Date": "2026/10/02",
            "Contract": "TX",
            "ContractMonth(Week)": "202610",
            "Open": "22000",
            "High": "22100",
            "Low": "21900",
            "Last": "22050",
            "SettlementPrice": "22050",
            "Volume": "12345",
            "OpenInterest": "45678",
        }]
        raw = b"\xef\xbb\xbf" + json.dumps(fixture).encode("utf-8")
        response = FakeResponse(raw)
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=response):
            snapshot = fetchers.fetch_taifex_latest_futures_market_snapshot("TX")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["date"], "2026-10-02")
        self.assertEqual(snapshot["contract"], "TX")

    def test_taifex_bom_prefixed_csv_response_parses_tx_market_date(self):
        fixture = (
            "日期,契約,交易,到期月份(週別),開盤價,最高價,最低價,最後成交價,漲跌,漲跌價差,漲跌%,"
            "合計成交量,結算價,未沖銷契約數\n"
            "2026/10/02,TX,一般,202610,22000,22100,21900,22050,+,100,0.46%,12345,22050,45678\n"
        ).encode("utf-8-sig")
        response = FakeResponse(fixture)
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=response):
            snapshot = fetchers.fetch_taifex_latest_futures_market_snapshot("TX")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["date"], "2026-10-02")
        self.assertEqual(snapshot["contract"], "TX")
        self.assertEqual(snapshot["close"], 22050.0)
        self.assertEqual(snapshot["volume"], 12345.0)
        self.assertEqual(snapshot["openInterest"], 45678.0)

    def test_taifex_unrecognized_or_invalid_responses_fail_closed(self):
        invalid_payloads = (
            b"",
            b" \t\r\n",
            b"<!doctype html><html><body>error</body></html>",
            b"{not-json",
            b"\xff\xfe\xfa",
            b'{"ok":true}\xef\xbb\xbf',
            b"\xef\xbb\xbf\xef\xbb\xbf{\"ok\":true}",
        )
        for raw in invalid_payloads:
            response = FakeResponse(raw)
            with self.subTest(raw=raw), \
                    patch.object(fetch_registry, "_urlopen_with_ssl_fallback", return_value=response), \
                    self.assertRaises((json.JSONDecodeError, UnicodeDecodeError, ValueError)):
                fetchers.fetch_taifex_latest_futures_market_snapshot("TX")

    def test_actual_live_header_aliases_parse_bom_prefixed_tx_row(self):
        raw = f"{self.LIVE_TAIFEX_HEADER}\n{self.LIVE_TAIFEX_ROW}\n".encode("utf-8-sig")
        rows = fetchers.parse_taifex_daily_market_report_response(raw)
        snapshot = fetchers.normalize_taifex_daily_market_row(
            fetchers.select_taifex_daily_market_row(rows, "TX")
        )
        self.assertEqual(len(self.LIVE_TAIFEX_HEADER.split(",")), 19)
        self.assertEqual(len(self.LIVE_TAIFEX_ROW.split(",")), 19)
        self.assertEqual(snapshot["date"], "2026-10-02")
        self.assertEqual(snapshot["contract"], "TX")
        self.assertEqual(snapshot["month"], "202610")
        self.assertEqual(snapshot["open"], 22000.0)
        self.assertEqual(snapshot["high"], 22100.0)
        self.assertEqual(snapshot["low"], 21900.0)
        self.assertEqual(snapshot["close"], 22050.0)
        self.assertEqual(snapshot["volume"], 12345.0)
        self.assertEqual(snapshot["openInterest"], 45678.0)

    def test_live_header_mapping_tolerates_reordering_and_extra_optional_column(self):
        columns = self.LIVE_TAIFEX_HEADER.split(",")
        values = self.LIVE_TAIFEX_ROW.split(",")
        order = list(reversed(range(len(columns))))
        reordered = ",".join([columns[index] for index in order] + ["新 optional 欄位"])
        reordered_row = ",".join([values[index] for index in order] + ["extra"])
        raw = f"{reordered}\r\n{reordered_row}\r\n".encode("utf-8")
        rows = fetchers.parse_taifex_daily_market_report_response(raw)
        snapshot = fetchers.normalize_taifex_daily_market_row(
            fetchers.select_taifex_daily_market_row(rows, "TX")
        )
        expected_rows = fetchers.parse_taifex_daily_market_report_response(
            f"{self.LIVE_TAIFEX_HEADER}\n{self.LIVE_TAIFEX_ROW}\n".encode("utf-8")
        )
        expected = fetchers.normalize_taifex_daily_market_row(
            fetchers.select_taifex_daily_market_row(expected_rows, "TX")
        )
        self.assertEqual(snapshot, expected)

    def test_unknown_header_and_missing_required_column_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "TAIFEX_CSV_REQUIRED_COLUMN_MISSING"):
            fetchers.parse_taifex_daily_market_report_response(b"foo,bar,baz\na,b,c\n")
        columns = self.LIVE_TAIFEX_HEADER.split(",")
        values = self.LIVE_TAIFEX_ROW.split(",")
        contract_index = columns.index("契約代號")
        columns.pop(contract_index)
        values.pop(contract_index)
        missing_contract = f"{','.join(columns)}\n{','.join(values)}\n".encode("utf-8")
        with self.assertRaisesRegex(ValueError, "TAIFEX_CSV_REQUIRED_COLUMN_MISSING: Contract"):
            fetchers.parse_taifex_daily_market_report_response(missing_contract)

    def test_csv_row_width_mismatch_fails_closed(self):
        values = self.LIVE_TAIFEX_ROW.split(",")[:-1]
        raw = f"{self.LIVE_TAIFEX_HEADER}\n{','.join(values)}\n".encode("utf-8")
        with self.assertRaisesRegex(ValueError, "TAIFEX_CSV_INVALID_ROW"):
            fetchers.parse_taifex_daily_market_report_response(raw)


if __name__ == "__main__":
    unittest.main()
