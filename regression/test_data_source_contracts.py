"""Offline contracts for TWSE search and live market data source states."""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import app
import cache
import routes_twse
from data_source_status import annotate_source_error, annotate_source_payload, providers_are_stale

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "data_source_contracts.json"
os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")


class DataSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixed_endpoint_contract_fixtures_use_canonical_states(self):
        type_map = {"str": str, "int": int, "list": list, "dict": dict}
        self.assertEqual(
            {"healthy", "stale", "temporarily_unavailable", "invalid_payload"},
            {case["status"] for case in self.fixtures.values()},
        )
        for name, fixture in self.fixtures.items():
            with self.subTest(name=name):
                if fixture.get("kind") == "error":
                    self.assertEqual(
                        fixture["status"],
                        annotate_source_error(fixture["payload"], fixture["status"])["sourceStatus"],
                    )
                    continue
                required = {key: type_map[value] for key, value in fixture["required"].items()}
                result = annotate_source_payload(
                    fixture["payload"],
                    required,
                    stale=fixture.get("stale", False),
                    non_empty_fields=tuple(fixture.get("non_empty", ())),
                )
                self.assertEqual(fixture["status"], result["sourceStatus"])
                if fixture["status"] in {"healthy", "stale"}:
                    self.assertIn("sourceUpdatedAt", result)

    def test_provider_refresh_failure_marks_retained_cache_stale(self):
        self.assertTrue(providers_are_stale({"twse": {"status": "timeout"}}))
        self.assertFalse(providers_are_stale({"twse": {"status": "available"}}))

    def test_cached_stock_search_exposes_stale_state_without_hiding_matches(self):
        previous = {
            key: cache.cache_data[key]
            for key in ("all_stocks", "cached_at", "market_date", "provider_status")
        }
        cache.cache_data.update(
            {
                "all_stocks": [{"code": "2330", "name": "台積電", "market": "TWSE"}],
                "cached_at": "2026-09-22 09:00:00",
                "market_date": "20260921",
                "provider_status": {"twse": {"status": "timeout"}},
            }
        )
        try:
            with patch.object(routes_twse, "ensure_cache"), app.app.test_request_context(
                "/api/twse/search?q=2330"
            ):
                response = routes_twse.api_stock_search()
            body = response.get_json()
            self.assertEqual("stale", body["sourceStatus"])
            self.assertEqual(1, body["count"])
            self.assertEqual("2330", body["results"][0]["code"])
        finally:
            cache.cache_data.update(previous)

    def test_live_search_source_error_is_not_an_empty_success(self):
        with patch.object(routes_twse, "fetch_live_stock_search_results", side_effect=OSError("fixture outage")):
            with app.app.test_request_context("/api/twse/live-search?q=2330"):
                response, status_code = routes_twse.api_live_stock_search()
        self.assertEqual(502, status_code)
        self.assertEqual("temporarily_unavailable", response.get_json()["sourceStatus"])

    def test_site_data_invalid_shape_is_marked_not_renderable(self):
        with patch.object(routes_twse, "build_live_sector_site_data", return_value={"snapshotDate": "2026-09-21"}):
            with app.app.test_request_context("/api/twse/site-data?refresh=1"):
                response = routes_twse.api_site_data()
        body = response.get_json()
        self.assertEqual("invalid_payload", body["sourceStatus"])
        self.assertEqual("2026-09-21", body["sourceUpdatedAt"])

    def test_live_search_empty_result_is_success_with_timestamp(self):
        fixed = self.fixtures["live_search_empty_is_valid"]["payload"]
        with patch.object(
            routes_twse,
            "fetch_live_stock_search_results",
            return_value=([], "20260921", None, ["TWSE"]),
        ), patch.object(app, "taipei_now") as now:
            now.return_value.strftime.return_value = fixed["refreshedAt"]
            with app.app.test_request_context("/api/twse/live-search?q=no-match"):
                response = routes_twse.api_live_stock_search()
        body = response.get_json()
        self.assertEqual("healthy", body["sourceStatus"])
        self.assertEqual([], body["results"])
        self.assertEqual(fixed["refreshedAt"], body["sourceUpdatedAt"])

    def test_site_data_success_contract_keeps_source_time(self):
        payload = self.fixtures["site_data"]["payload"]
        with patch.object(routes_twse, "build_live_sector_site_data", return_value=payload):
            with app.app.test_request_context("/api/twse/site-data?refresh=1"):
                response = routes_twse.api_site_data()
        body = response.get_json()
        self.assertEqual("healthy", body["sourceStatus"])
        self.assertEqual(payload["cachedAt"], body["sourceUpdatedAt"])

    def test_live_overview_and_sectors_contracts(self):
        for route, fixture_name, builder_name in (
            (routes_twse.api_live_sectors, "live_sectors", "build_live_sector_site_data"),
            (routes_twse.api_live_overview, "live_overview", "build_live_market_overview_data"),
        ):
            with self.subTest(fixture=fixture_name):
                payload = self.fixtures[fixture_name]["payload"]
                with patch.object(routes_twse, builder_name, return_value=payload):
                    with app.app.test_request_context("/api/twse/live-data"):
                        response = route()
                body = response.get_json()
                self.assertEqual("healthy", body["sourceStatus"])
                self.assertEqual(payload["cachedAt"], body["sourceUpdatedAt"])

    def test_live_stock_universe_contract_rejects_an_empty_market(self):
        with patch.object(routes_twse, "fetch_live_stock_universe", return_value=([], {}, "20260921", None)), patch.object(
            routes_twse, "enrich_stocks_with_industry", side_effect=lambda stocks: stocks
        ), patch.object(routes_twse, "build_stocks_view", side_effect=lambda stocks, _mode: stocks), patch.object(
            app, "taipei_now"
        ) as now:
            now.return_value.strftime.return_value = "2026-09-22 09:00:00"
            with app.app.test_request_context("/api/twse/live-stocks"):
                response = routes_twse.api_live_stocks()
        self.assertEqual("invalid_payload", response.get_json()["sourceStatus"])


if __name__ == "__main__":
    unittest.main()
