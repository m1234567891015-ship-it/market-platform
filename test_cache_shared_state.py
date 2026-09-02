"""H-05-04 cache-flight lease integration tests."""
from __future__ import annotations

import os
import time
import unittest
from unittest.mock import Mock, patch

import cache
from shared_state import InMemorySharedStateAdapter, SharedStateUnavailable


class FakeClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class CacheFlightLeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        with cache.cache_flight_lock:
            cache.cache_flights.clear()
        with cache.taifex_options_chain_inflight_lock:
            cache.taifex_options_chain_inflight.clear()

    def tearDown(self) -> None:
        with cache.cache_flight_lock:
            cache.cache_flights.clear()
        with cache.taifex_options_chain_inflight_lock:
            cache.taifex_options_chain_inflight.clear()

    def test_local_mode_preserves_event_based_single_flight(self) -> None:
        with patch.dict(os.environ, {"MARKET_PULSE_SINGLE_FLIGHT_MODE": "local"}):
            is_leader, leader = cache.claim_cache_flight("local-key")
            is_follower, follower = cache.claim_cache_flight("local-key")
            self.assertTrue(is_leader)
            self.assertFalse(is_follower)
            self.assertFalse(follower.wait(0.01))
            cache.finish_cache_flight("local-key", leader)
            self.assertTrue(follower.wait(0.01))

    def test_shared_mode_waits_for_cross_process_lease_release(self) -> None:
        adapter = InMemorySharedStateAdapter()
        with patch.dict(os.environ, {"MARKET_PULSE_SINGLE_FLIGHT_MODE": "redis"}), \
                patch.object(cache, "_get_single_flight_shared_adapter", return_value=adapter):
            is_leader, leader = cache.claim_cache_flight("shared-key")
            self.assertTrue(is_leader)

            # A separate process has no local event, so clear this process's
            # local registry to exercise the Redis-lease follower path.
            with cache.cache_flight_lock:
                cache.cache_flights.clear()
            is_follower, follower = cache.claim_cache_flight("shared-key")
            self.assertFalse(is_follower)
            started = time.monotonic()
            self.assertFalse(follower.wait(0.01))
            self.assertLess(time.monotonic() - started, 1)

            cache.finish_cache_flight("shared-key", leader)
            self.assertTrue(follower.wait(0.01))

    def test_shared_mode_owner_token_fences_stale_leader_release(self) -> None:
        clock = FakeClock()
        adapter = InMemorySharedStateAdapter(clock=clock)
        with patch.dict(os.environ, {"MARKET_PULSE_SINGLE_FLIGHT_MODE": "redis"}), \
                patch.object(cache, "_get_single_flight_shared_adapter", return_value=adapter):
            is_old_leader, old_leader = cache.claim_cache_flight("fenced-key")
            self.assertTrue(is_old_leader)
            with cache.cache_flight_lock:
                cache.cache_flights.clear()
            clock.advance(cache.SINGLE_FLIGHT_LEASE_TTL_SECONDS + 1)
            is_new_leader, new_leader = cache.claim_cache_flight("fenced-key")
            self.assertTrue(is_new_leader)

            cache.finish_cache_flight("fenced-key", old_leader)
            self.assertFalse(new_leader.wait(0.01))
            cache.finish_cache_flight("fenced-key", new_leader)

    def test_shared_mode_backend_failure_degrades_to_local_leader(self) -> None:
        with patch.dict(os.environ, {"MARKET_PULSE_SINGLE_FLIGHT_MODE": "redis"}), \
                patch.object(
                    cache,
                    "_get_single_flight_shared_adapter",
                    side_effect=SharedStateUnavailable("test disconnect"),
                ):
            is_leader, handle = cache.claim_cache_flight("fallback-key")
            self.assertTrue(is_leader)
            self.assertFalse(handle.uses_shared_lease)
            cache.finish_cache_flight("fallback-key", handle)

    def test_options_chain_uses_the_same_lease_contract(self) -> None:
        adapter = InMemorySharedStateAdapter()
        with patch.dict(os.environ, {"MARKET_PULSE_SINGLE_FLIGHT_MODE": "redis"}), \
                patch.object(cache, "_get_single_flight_shared_adapter", return_value=adapter):
            is_leader, leader = cache.claim_taifex_options_chain_flight("TXO:20260831:")
            self.assertTrue(is_leader)
            with cache.taifex_options_chain_inflight_lock:
                cache.taifex_options_chain_inflight.clear()
            is_follower, follower = cache.claim_taifex_options_chain_flight("TXO:20260831:")
            self.assertFalse(is_follower)
            cache.finish_taifex_options_chain_flight("TXO:20260831:", leader)
            self.assertTrue(follower.wait(0.01))


class CacheL2Tests(unittest.TestCase):
    bucket = "global_market_items"
    h11_json_buckets = (
        "global_markets",
        "sector_charts",
        "stock_details",
        "taifex_options_chain",
        "us_etf_center",
        "yahoo_tw_option_chain",
    )

    def tearDown(self) -> None:
        with cache.cache_lock:
            cache.cache_data.get(self.bucket, {}).pop("l2-test-key", None)

    def test_local_mode_does_not_create_or_call_l2_backend(self) -> None:
        with patch.dict(os.environ, {"MARKET_PULSE_CACHE_L2_MODE": "local"}), \
                patch.object(cache, "_get_cache_l2_shared_adapter") as get_adapter:
            cache.write_memory_cache(self.bucket, "l2-test-key", {"value": "local"}, 30)
            self.assertEqual(cache.read_memory_cache(self.bucket, "l2-test-key", 30), {"value": "local"})
            get_adapter.assert_not_called()

    def test_redis_l2_write_survives_l1_clear_and_promotes_on_read(self) -> None:
        adapter = InMemorySharedStateAdapter()
        with patch.dict(os.environ, {"MARKET_PULSE_CACHE_L2_MODE": "redis"}), \
                patch.object(cache, "_get_cache_l2_shared_adapter", return_value=adapter):
            cache.write_memory_cache(self.bucket, "l2-test-key", {"value": 42}, 30)
            with cache.cache_lock:
                cache.cache_data[self.bucket].pop("l2-test-key", None)
            self.assertEqual(cache.read_memory_cache(self.bucket, "l2-test-key", 30), {"value": 42})
            with cache.cache_lock:
                self.assertEqual(cache.cache_data[self.bucket]["l2-test-key"]["payload"], {"value": 42})
        self.assertTrue(cache._cache_l2_namespace(self.bucket).endswith(":cache-v13:" + self.bucket))

    def test_l2_backend_failure_keeps_local_write_and_returns_local_miss(self) -> None:
        class FailingAdapter:
            def cache_get(self, _namespace: str, _key: str) -> None:
                raise SharedStateUnavailable("test disconnect")

            def cache_set(self, _namespace: str, _key: str, _payload: object, _ttl: float) -> None:
                raise SharedStateUnavailable("test disconnect")

        with patch.dict(os.environ, {"MARKET_PULSE_CACHE_L2_MODE": "redis"}), \
                patch.object(cache, "_get_cache_l2_shared_adapter", return_value=FailingAdapter()):
            cache.write_memory_cache(self.bucket, "l2-test-key", {"value": "local"}, 30)
            self.assertEqual(cache.read_memory_cache(self.bucket, "l2-test-key", 30), {"value": "local"})
            with cache.cache_lock:
                cache.cache_data[self.bucket].pop("l2-test-key", None)
            self.assertIsNone(cache.read_memory_cache(self.bucket, "l2-test-key", 30))

    def test_binary_external_text_bucket_is_not_in_initial_l2_allowlist(self) -> None:
        adapter = InMemorySharedStateAdapter()
        with patch.dict(os.environ, {"MARKET_PULSE_CACHE_L2_MODE": "redis"}), \
                patch.object(cache, "_get_cache_l2_shared_adapter", return_value=adapter) as get_adapter:
            cache.write_memory_cache("external_text", "l2-test-key", b"binary", 30)
            self.assertEqual(cache.read_memory_cache("external_text", "l2-test-key", 30), b"binary")
            get_adapter.assert_not_called()

    def test_h11_json_buckets_promote_from_l2_and_expire_by_ttl(self) -> None:
        clock = FakeClock()
        adapter = InMemorySharedStateAdapter(clock=clock)
        with patch.dict(os.environ, {"MARKET_PULSE_CACHE_L2_MODE": "redis"}), \
                patch.object(cache, "_get_cache_l2_shared_adapter", return_value=adapter):
            for bucket in self.h11_json_buckets:
                key = f"h11-{bucket}"
                payload = {"bucket": bucket, "items": [1, {"safe": True}], "nullable": None}
                with cache.cache_lock:
                    cache.cache_data.setdefault(bucket, {}).pop(key, None)
                cache.write_memory_cache(bucket, key, payload, 2)
                with cache.cache_lock:
                    cache.cache_data[bucket].pop(key, None)
                self.assertEqual(cache.read_memory_cache(bucket, key, 2), payload)
                with cache.cache_lock:
                    cache.cache_data[bucket].pop(key, None)
                clock.advance(2.1)
                self.assertIsNone(cache.read_memory_cache(bucket, key, 2))

    def test_h11_json_buckets_keep_local_fallback_on_l2_disconnect(self) -> None:
        class FailingAdapter:
            def cache_get(self, _namespace: str, _key: str) -> None:
                raise SharedStateUnavailable("test disconnect")

            def cache_set(self, _namespace: str, _key: str, _payload: object, _ttl: float) -> None:
                raise SharedStateUnavailable("test disconnect")

        with patch.dict(os.environ, {"MARKET_PULSE_CACHE_L2_MODE": "redis"}), \
                patch.object(cache, "_get_cache_l2_shared_adapter", return_value=FailingAdapter()):
            for bucket in self.h11_json_buckets:
                key = f"h11-failure-{bucket}"
                payload = {"bucket": bucket, "safe": True}
                with cache.cache_lock:
                    cache.cache_data.setdefault(bucket, {}).pop(key, None)
                cache.write_memory_cache(bucket, key, payload, 30)
                self.assertEqual(cache.read_memory_cache(bucket, key, 30), payload)
                with cache.cache_lock:
                    cache.cache_data[bucket].pop(key, None)
                self.assertIsNone(cache.read_memory_cache(bucket, key, 30))


class BackgroundUpdaterLeaseTests(unittest.TestCase):
    def test_local_mode_runs_refresh_without_shared_backend(self) -> None:
        with patch.dict(os.environ, {"MARKET_PULSE_BACKGROUND_LEASE_MODE": "local"}), \
                patch.object(cache, "_run_background_refresh_tasks") as refresh_tasks, \
                patch.object(cache, "_get_background_updater_shared_adapter") as get_adapter:
            self.assertTrue(cache.run_background_update_cycle())
            refresh_tasks.assert_called_once()
            get_adapter.assert_not_called()

    def test_shared_mode_skips_when_another_worker_holds_lease(self) -> None:
        adapter = InMemorySharedStateAdapter()
        self.assertTrue(adapter.acquire_lease(cache.BACKGROUND_UPDATER_LEASE_NAME, "other-worker", 120))
        with patch.dict(os.environ, {"MARKET_PULSE_BACKGROUND_LEASE_MODE": "redis"}), \
                patch.object(cache, "_get_background_updater_shared_adapter", return_value=adapter), \
                patch.object(cache, "_run_background_refresh_tasks") as refresh_tasks:
            self.assertFalse(cache.run_background_update_cycle())
            refresh_tasks.assert_not_called()

    def test_shared_mode_refreshes_and_releases_owner_lease(self) -> None:
        adapter = InMemorySharedStateAdapter()
        with patch.dict(os.environ, {"MARKET_PULSE_BACKGROUND_LEASE_MODE": "redis"}), \
                patch.object(cache, "_get_background_updater_shared_adapter", return_value=adapter), \
                patch.object(cache, "_run_background_refresh_tasks") as refresh_tasks:
            self.assertTrue(cache.run_background_update_cycle())
            refresh_tasks.assert_called_once()
        self.assertFalse(adapter.lease_is_active(cache.BACKGROUND_UPDATER_LEASE_NAME))

    def test_shared_mode_renews_lease_during_a_long_refresh(self) -> None:
        adapter = InMemorySharedStateAdapter()
        recording_adapter = Mock(wraps=adapter)
        with patch.dict(os.environ, {"MARKET_PULSE_BACKGROUND_LEASE_MODE": "redis"}), \
                patch.object(cache, "_get_background_updater_shared_adapter", return_value=recording_adapter), \
                patch.object(cache, "BACKGROUND_UPDATER_RENEW_INTERVAL_SECONDS", 0.01), \
                patch.object(cache, "_run_background_refresh_tasks", side_effect=lambda: time.sleep(0.04)):
            self.assertTrue(cache.run_background_update_cycle())
        self.assertTrue(recording_adapter.renew_lease.called)

    def test_expired_lease_can_be_taken_over(self) -> None:
        clock = FakeClock()
        adapter = InMemorySharedStateAdapter(clock=clock)
        self.assertTrue(adapter.acquire_lease(cache.BACKGROUND_UPDATER_LEASE_NAME, "old-worker", 120))
        clock.advance(121)
        with patch.dict(os.environ, {"MARKET_PULSE_BACKGROUND_LEASE_MODE": "redis"}), \
                patch.object(cache, "_get_background_updater_shared_adapter", return_value=adapter), \
                patch.object(cache, "_run_background_refresh_tasks") as refresh_tasks:
            self.assertTrue(cache.run_background_update_cycle())
            refresh_tasks.assert_called_once()
        self.assertFalse(adapter.lease_is_active(cache.BACKGROUND_UPDATER_LEASE_NAME))

    def test_shared_backend_failure_skips_refresh_instead_of_local_fallback(self) -> None:
        with patch.dict(os.environ, {"MARKET_PULSE_BACKGROUND_LEASE_MODE": "redis"}), \
                patch.object(
                    cache,
                    "_get_background_updater_shared_adapter",
                    side_effect=SharedStateUnavailable("test disconnect"),
                ), \
                patch.object(cache, "_run_background_refresh_tasks") as refresh_tasks:
            self.assertFalse(cache.run_background_update_cycle())
            refresh_tasks.assert_not_called()


if __name__ == "__main__":
    unittest.main()
