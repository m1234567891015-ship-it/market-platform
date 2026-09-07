"""Offline guardrails for request-starvation remediation Slice B."""

from __future__ import annotations

import threading
import time
import unittest
from urllib.error import URLError
from unittest.mock import patch

import cache
import fetch_registry
import fetchers
from fetch_registry import deadline_after


class RequestStarvationSliceBTests(unittest.TestCase):
    def setUp(self) -> None:
        with cache.cache_flight_lock:
            cache.cache_flights.clear()
        with cache.provider_cooldown_lock:
            cache.provider_cooldowns.clear()

    def tearDown(self) -> None:
        with cache.cache_flight_lock:
            cache.cache_flights.clear()
        with cache.provider_cooldown_lock:
            cache.provider_cooldowns.clear()

    def test_request_and_background_callers_share_one_slow_operation(self) -> None:
        started = threading.Event()
        release = threading.Event()
        calls = 0
        calls_lock = threading.Lock()
        results: list[dict[str, int]] = []

        def slow_provider() -> dict[str, int]:
            nonlocal calls
            with calls_lock:
                calls += 1
            started.set()
            self.assertTrue(release.wait(1.0))
            return {"value": 42}

        def invoke() -> None:
            results.append(
                cache.run_cache_single_flight(
                    "slice-b:tpex:quotes",
                    slow_provider,
                    deadline=deadline_after(1.0),
                    provider_key="host:tpex.example",
                )
            )

        leader = threading.Thread(target=invoke)
        follower = threading.Thread(target=invoke)
        leader.start()
        self.assertTrue(started.wait(1.0))
        follower.start()
        time.sleep(0.03)
        release.set()
        leader.join(1.0)
        follower.join(1.0)

        self.assertEqual(calls, 1)
        self.assertEqual(results, [{"value": 42}, {"value": 42}])

    def test_registry_provider_request_and_background_collision_fetches_once(self) -> None:
        started = threading.Event()
        release = threading.Event()
        calls = 0

        class Response:
            headers: dict[str, str] = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'[{"Date":"1150719"}]'

        def fake_urlopen(_request, _timeout):
            nonlocal calls
            calls += 1
            started.set()
            release.wait(1.0)
            return Response()

        results: list[tuple[list[dict[str, str]], str | None]] = []
        with patch.object(fetch_registry, "_urlopen_with_ssl_fallback", side_effect=fake_urlopen):
            request_thread = threading.Thread(
                target=lambda: results.append(fetchers.fetch_tpex_mainboard_quotes(timeout=1))
            )
            background_thread = threading.Thread(
                target=lambda: results.append(fetchers.fetch_tpex_mainboard_quotes(timeout=1))
            )
            request_thread.start()
            self.assertTrue(started.wait(1.0))
            background_thread.start()
            release.set()
            request_thread.join(1.0)
            background_thread.join(1.0)

        self.assertFalse(request_thread.is_alive() or background_thread.is_alive())
        self.assertEqual(calls, 1)
        self.assertEqual(len(results), 2)

    def test_follower_stops_at_its_deadline_without_duplicate_call(self) -> None:
        started = threading.Event()
        release = threading.Event()
        calls = 0

        def slow_provider() -> str:
            nonlocal calls
            calls += 1
            started.set()
            release.wait(1.0)
            return "ok"

        leader_result: list[str] = []
        leader = threading.Thread(
            target=lambda: leader_result.append(
                cache.run_cache_single_flight("slice-b:deadline", slow_provider, provider_key="host:deadline")
            )
        )
        leader.start()
        self.assertTrue(started.wait(1.0))
        follower_started = time.monotonic()
        with self.assertRaises(cache.ProviderFlightUnavailable):
            cache.run_cache_single_flight(
                "slice-b:deadline",
                slow_provider,
                deadline=deadline_after(0.05),
                provider_key="host:deadline",
            )
        self.assertLess(time.monotonic() - follower_started, 0.5)
        self.assertEqual(calls, 1)
        release.set()
        leader.join(1.0)
        self.assertEqual(leader_result, ["ok"])

    def test_timeout_leader_failure_releases_followers(self) -> None:
        started = threading.Event()
        release = threading.Event()
        calls = 0

        def timeout_provider() -> None:
            nonlocal calls
            calls += 1
            started.set()
            release.wait(1.0)
            raise TimeoutError("provider timeout")

        leader_result: list[type[BaseException]] = []

        def run_leader() -> None:
            try:
                cache.run_cache_single_flight("slice-b:timeout", timeout_provider, provider_key="host:timeout")
            except BaseException as exc:  # noqa: BLE001
                leader_result.append(type(exc))

        leader = threading.Thread(target=run_leader)
        leader.start()
        self.assertTrue(started.wait(1.0))
        follower_result: list[type[BaseException]] = []

        def run_follower() -> None:
            try:
                cache.run_cache_single_flight(
                    "slice-b:timeout",
                    timeout_provider,
                    deadline=deadline_after(1.0),
                    provider_key="host:timeout",
                )
            except BaseException as exc:  # noqa: BLE001
                follower_result.append(type(exc))

        follower = threading.Thread(target=run_follower)
        follower.start()
        release.set()
        leader.join(1.0)
        follower.join(1.0)
        self.assertEqual(calls, 1)
        self.assertEqual(leader_result, [TimeoutError])
        self.assertEqual(follower_result, [TimeoutError])

    def test_option_chain_follower_fail_closes_after_deadline_without_rescan(self) -> None:
        key = "TXO:20990105:"
        is_leader, leader_handle = cache.claim_taifex_options_chain_flight(key)
        self.assertTrue(is_leader)
        try:
            with patch.object(fetchers, "fetch_form_text") as fetch_form:
                result = fetchers.fetch_taifex_txo_option_chain(
                    market_date="20990105",
                    underlying="TXO",
                    deadline=deadline_after(0.05),
                )
            self.assertIn("error", result)
            fetch_form.assert_not_called()
        finally:
            cache.finish_taifex_options_chain_flight(key, leader_handle)

    def test_provider_failure_cooldown_is_bounded_and_isolated(self) -> None:
        calls = {"failed": 0, "other": 0}

        def failed_provider() -> None:
            calls["failed"] += 1
            raise URLError("offline")

        with patch.object(cache, "PROVIDER_FAILURE_COOLDOWN_SECONDS", 0.05):
            with self.assertRaises(URLError):
                cache.run_cache_single_flight("slice-b:failed", failed_provider, provider_key="host:failed")
            with self.assertRaises(cache.ProviderCooldownError):
                cache.run_cache_single_flight("slice-b:failed", failed_provider, provider_key="host:failed")

            result = cache.run_cache_single_flight(
                "slice-b:other",
                lambda: calls.__setitem__("other", calls["other"] + 1) or "other",
                provider_key="host:other",
            )
            self.assertEqual(result, "other")
            self.assertEqual(calls["other"], 1)
            time.sleep(0.07)
            with self.assertRaises(URLError):
                cache.run_cache_single_flight("slice-b:failed:retry", failed_provider, provider_key="host:failed")

        self.assertEqual(calls["failed"], 2)

    def test_leader_exception_clears_flight_for_future_attempt(self) -> None:
        with self.assertRaises(RuntimeError):
            cache.run_cache_single_flight("slice-b:exception", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = cache.run_cache_single_flight("slice-b:exception", lambda: "recovered")
        self.assertEqual(result, "recovered")

    def test_refresh_coordination_lock_is_available_during_slow_refresh(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def slow_refresh() -> None:
            started.set()
            release.wait(1.0)

        with patch.object(cache, "_refresh_cache_impl", side_effect=slow_refresh):
            worker = threading.Thread(target=cache.refresh_cache)
            worker.start()
            self.assertTrue(started.wait(1.0))
            self.assertTrue(cache.cache_refresh_lock.acquire(timeout=0.05))
            cache.cache_refresh_lock.release()
            self.assertTrue(cache.cache_lock.acquire(timeout=0.05))
            cache.cache_lock.release()
            release.set()
            worker.join(1.0)

        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
