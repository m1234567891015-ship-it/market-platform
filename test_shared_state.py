"""H-05-02 shared-state contract tests.

The in-memory backend is mandatory and deterministic.  A real Redis contract
run is opt-in through MARKET_PULSE_REDIS_URL so the base project keeps Redis
out of its production and regression dependencies until a later batch.
"""
from __future__ import annotations

import os
import time
import unittest
import uuid
from unittest.mock import patch

from flask import Flask

import security
from shared_state import (
    InMemorySharedStateAdapter,
    RedisSharedStateAdapter,
    SharedStateTimeout,
    SharedStateUnavailable,
)


class FakeClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def assert_shared_state_contract(test: unittest.TestCase, adapter: object, clock: FakeClock | None = None) -> None:
    cache_namespace = f"contract-{uuid.uuid4().hex}"
    cache_key = "json-cache"
    adapter.cache_set(cache_namespace, cache_key, {"value": 7, "nested": ["ok"]}, 30)
    test.assertEqual(adapter.cache_get(cache_namespace, cache_key), {"value": 7, "nested": ["ok"]})

    if clock is not None:
        clock.advance(31)
        test.assertIsNone(adapter.cache_get(cache_namespace, cache_key))

    client_key = f"client-{uuid.uuid4().hex}"
    now = clock.value if clock is not None else time.time()
    test.assertIsNone(adapter.rate_limit_hit(client_key, now, 60, 2, 10))
    test.assertIsNone(adapter.rate_limit_hit(client_key, now + 1, 60, 2, 10))
    test.assertEqual(adapter.rate_limit_hit(client_key, now + 2, 60, 2, 10), 58)

    lease_name = f"lease-{uuid.uuid4().hex}"
    test.assertTrue(adapter.acquire_lease(lease_name, "owner-a", 30))
    test.assertFalse(adapter.acquire_lease(lease_name, "owner-b", 30))
    test.assertFalse(adapter.renew_lease(lease_name, "owner-b", 30))
    test.assertTrue(adapter.renew_lease(lease_name, "owner-a", 30))
    test.assertFalse(adapter.release_lease(lease_name, "owner-b"))
    test.assertTrue(adapter.release_lease(lease_name, "owner-a"))


class SharedStateContractTests(unittest.TestCase):
    def test_in_memory_contract_covers_ttl_rate_limit_and_owner_token_lease(self) -> None:
        clock = FakeClock()
        adapter = InMemorySharedStateAdapter(clock=clock)
        assert_shared_state_contract(self, adapter, clock)

        stale_lease = "stale-lease"
        self.assertTrue(adapter.acquire_lease(stale_lease, "owner-a", 5))
        clock.advance(6)
        self.assertTrue(adapter.acquire_lease(stale_lease, "owner-b", 5))

    def test_in_memory_restart_has_no_process_local_state(self) -> None:
        clock = FakeClock()
        first_process = InMemorySharedStateAdapter(clock=clock)
        self.assertTrue(first_process.acquire_lease("restart-lease", "owner-a", 30))
        first_process.cache_set("restart", "key", {"value": 1}, 30)

        second_process = InMemorySharedStateAdapter(clock=clock)
        self.assertIsNone(second_process.cache_get("restart", "key"))
        self.assertTrue(second_process.acquire_lease("restart-lease", "owner-b", 30))

    def test_redis_adapter_translates_timeout_and_disconnect_without_fallback(self) -> None:
        class TimeoutClient:
            def get(self, _key: str) -> None:
                raise TimeoutError("test timeout")

            def set(self, _key: str, _value: str, **_kwargs: object) -> None:
                raise ConnectionError("test disconnect")

        adapter = RedisSharedStateAdapter(TimeoutClient())
        with self.assertRaises(SharedStateTimeout):
            adapter.cache_get("failure", "timeout")
        with self.assertRaises(SharedStateUnavailable):
            adapter.cache_set("failure", "disconnect", {"value": 1}, 30)

    def test_shadow_mode_keeps_local_decision_and_logs_comparison(self) -> None:
        clock = FakeClock()
        adapter = InMemorySharedStateAdapter(clock=clock)
        original_limit = security.API_RATE_LIMIT_PER_WINDOW
        try:
            security.API_RATE_LIMIT_PER_WINDOW = 1
            with security.API_RATE_LIMIT_LOCK:
                security.API_RATE_LIMIT_STATE.clear()
            test_app = Flask("td03-shadow-test")
            with patch.dict(os.environ, {"MARKET_PULSE_RATE_LIMIT_MODE": "shadow"}), \
                    patch.object(security, "_get_rate_limit_shared_adapter", return_value=adapter), \
                    self.assertLogs("market_pulse", level="INFO") as logs:
                with test_app.test_request_context("/api/test", environ_base={"REMOTE_ADDR": "shadow-client"}):
                    self.assertIsNone(security.enforce_api_rate_limit())
                with test_app.test_request_context("/api/test", environ_base={"REMOTE_ADDR": "shadow-client"}):
                    response = security.enforce_api_rate_limit()
                    self.assertEqual(response.status_code, 429)
            self.assertTrue(any("rate_limit_shadow_compare" in record for record in logs.output))
        finally:
            security.API_RATE_LIMIT_PER_WINDOW = original_limit
            with security.API_RATE_LIMIT_LOCK:
                security.API_RATE_LIMIT_STATE.clear()

    def test_redis_mode_uses_shared_result_without_local_write(self) -> None:
        clock = FakeClock()
        adapter = InMemorySharedStateAdapter(clock=clock)
        original_limit = security.API_RATE_LIMIT_PER_WINDOW
        try:
            security.API_RATE_LIMIT_PER_WINDOW = 1
            with security.API_RATE_LIMIT_LOCK:
                security.API_RATE_LIMIT_STATE.clear()
            test_app = Flask("td03-redis-mode-test")
            with patch.dict(os.environ, {"MARKET_PULSE_RATE_LIMIT_MODE": "redis"}), \
                    patch.object(security, "_get_rate_limit_shared_adapter", return_value=adapter):
                with test_app.test_request_context("/api/test", environ_base={"REMOTE_ADDR": "shared-client"}):
                    self.assertIsNone(security.enforce_api_rate_limit())
                with test_app.test_request_context("/api/test", environ_base={"REMOTE_ADDR": "shared-client"}):
                    response = security.enforce_api_rate_limit()
                    self.assertEqual(response.status_code, 429)
            with security.API_RATE_LIMIT_LOCK:
                self.assertEqual(security.API_RATE_LIMIT_STATE, {})
        finally:
            security.API_RATE_LIMIT_PER_WINDOW = original_limit
            with security.API_RATE_LIMIT_LOCK:
                security.API_RATE_LIMIT_STATE.clear()

    def test_redis_mode_fails_closed_when_shared_backend_is_unavailable(self) -> None:
        original_limit = security.API_RATE_LIMIT_PER_WINDOW
        try:
            security.API_RATE_LIMIT_PER_WINDOW = 1
            test_app = Flask("td03-fail-closed-test")
            with patch.dict(os.environ, {"MARKET_PULSE_RATE_LIMIT_MODE": "redis"}), \
                    patch.object(
                        security,
                        "_register_shared_rate_limit_window_hit",
                        side_effect=SharedStateUnavailable("test disconnect"),
                    ):
                with test_app.test_request_context("/api/test", environ_base={"REMOTE_ADDR": "blocked-client"}):
                    response = security.enforce_api_rate_limit()
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.headers["Retry-After"], "5")
            self.assertEqual(response.get_json()["error_code"], "RATE_LIMIT_BACKEND_UNAVAILABLE")
        finally:
            security.API_RATE_LIMIT_PER_WINDOW = original_limit

    @unittest.skipUnless(os.environ.get("MARKET_PULSE_REDIS_URL"), "MARKET_PULSE_REDIS_URL not configured")
    def test_redis_contract_when_configured(self) -> None:
        try:
            import redis
        except ImportError:
            self.skipTest("redis package not installed")
        try:
            client = redis.Redis.from_url(
                os.environ["MARKET_PULSE_REDIS_URL"],
                protocol=2,
                socket_connect_timeout=1,
                socket_timeout=1,
                decode_responses=True,
            )
            client.ping()
        except Exception as exc:
            self.skipTest(f"Redis unavailable: {exc}")
        assert_shared_state_contract(self, RedisSharedStateAdapter(client))


if __name__ == "__main__":
    unittest.main()
