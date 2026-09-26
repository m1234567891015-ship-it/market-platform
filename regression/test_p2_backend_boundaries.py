"""Deterministic P2 backend boundary and import-order evidence."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")

import app
import builders
import cache
import routes_global_market
from derivatives_store import DerivativesStore


class P2BackendBoundaryTests(unittest.TestCase):
    def test_global_market_route_delegates_to_builder_boundary(self):
        payload = {
            "category": "options",
            "items": [],
            "summary": {"count": 0},
        }
        with tempfile.TemporaryDirectory(prefix="p2-route-store-") as temp_dir:
            flask_app = app.create_app(
                {"TESTING": True},
                derivatives_store=DerivativesStore(str(Path(temp_dir) / "derivatives.sqlite3")),
            )
            with patch.object(routes_global_market, "read_memory_cache", return_value=None), patch.object(
                routes_global_market, "build_global_market_payload", return_value=payload
            ) as build_payload:
                response = flask_app.test_client().get("/api/global-market/options?limit=1")

        self.assertEqual(200, response.status_code)
        self.assertEqual({**payload, "cached": False}, response.get_json())
        build_payload.assert_called_once_with("options", 1, option_source="auto", option_underlying="TXO")

    def test_cboe_slice_keeps_transport_parser_and_builder_separate(self):
        source_url = "https://cdn.cboe.com/api/global/delayed_quotes/options/SPY.json"
        payload = {
            "timestamp": "2026-09-25T00:00:00Z",
            "data": {
                "symbol": "SPY",
                "current_price": 600.0,
                "price_change": 1.0,
                "price_change_percent": 0.16,
                "options": [
                    {
                        "option": "SPY270115C00600000",
                        "last_trade_price": 12.5,
                        "bid": 12.4,
                        "ask": 12.6,
                        "volume": 10,
                        "open_interest": 100,
                    },
                    {
                        "option": "SPY270115P00600000",
                        "last_trade_price": 11.5,
                        "bid": 11.4,
                        "ask": 11.6,
                        "volume": 12,
                        "open_interest": 120,
                    },
                ],
            },
        }
        with patch.object(builders, "read_memory_cache", return_value=None), patch.object(
            builders, "write_memory_cache"
        ), patch.object(
            builders, "fetch_cboe_options_payload", return_value=(payload, source_url)
        ) as fetch_payload:
            result = builders.build_cboe_options_chain("SPY", "2027-01-15")

        fetch_payload.assert_called_once_with("SPY")
        self.assertEqual(source_url, result["sourceUrl"])
        self.assertEqual(1, result["summary"]["callCount"])
        self.assertEqual(1, result["summary"]["putCount"])
        self.assertEqual(600.0, result["calls"][0]["strike"])
        self.assertEqual("call", result["calls"][0]["type"])
        self.assertEqual("put", result["puts"][0]["type"])

    def test_factory_registers_error_handlers_and_is_repeatable(self):
        with tempfile.TemporaryDirectory(prefix="p2-factory-store-") as temp_dir:
            def make_app(name: str):
                return app.create_app(
                    {"TESTING": True, "APPLICATION_ROOT": name},
                    derivatives_store=DerivativesStore(str(Path(temp_dir) / f"{name}.sqlite3")),
                )

            first = make_app("first")
            second = make_app("second")
            first_rules = list(first.url_map.iter_rules())
            second_rules = list(second.url_map.iter_rules())
            response = first.test_client().get("/api/does-not-exist")

        self.assertEqual(len(first_rules), len(second_rules))
        self.assertEqual(len(first_rules), len({rule.rule for rule in first_rules}))
        self.assertEqual(404, response.status_code)
        self.assertEqual("NOT_FOUND", response.get_json()["error_code"])
        self.assertFalse(cache.background_updater_started)

    def test_import_orders_and_repeated_factory_construction(self):
        orders = [
            ("app", "builders"),
            ("builders", "fetchers"),
            ("fetchers", "parsers"),
            ("routes_twse", "builders"),
            ("routes_derivatives", "builders"),
        ]
        script = (
            "import importlib; "
            "[importlib.import_module(name) for name in ORDER]; "
            "import app; app.create_app(); app.create_app(); print('P2_IMPORT_OK')"
        )
        for order in orders:
            with self.subTest(order=order):
                env = os.environ.copy()
                env["PYTHONPATH"] = str(ROOT)
                env["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
                env["MARKET_PULSE_LOG_LEVEL"] = "CRITICAL"
                result = subprocess.run(
                    [sys.executable, "-c", f"ORDER={order!r}; {script}"],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("P2_IMPORT_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
