"""TD-03 H-11-03 offline dual-worker load and fault-injection canary.

The canary exercises the shared-state contract with two concurrent worker
facades and the existing cache/security integration.  It deliberately does
not import ``app.py``, start Flask, open a Redis connection, or touch the
production SQLite/JSON cache.  A real staging run remains opt-in and is
reported as pending until ``MARKET_PULSE_REDIS_URL`` is supplied.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cache  # noqa: E402
import security  # noqa: E402
from shared_state import InMemorySharedStateAdapter, SharedStateUnavailable  # noqa: E402


JSON_SAFE_BUCKETS = (
    "global_markets",
    "sector_charts",
    "stock_details",
    "taifex_options_chain",
    "us_etf_center",
    "yahoo_tw_option_chain",
)


@dataclass
class FakeClock:
    value: float = 1_000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class Worker:
    def __init__(self, name: str, adapter: InMemorySharedStateAdapter) -> None:
        self.name = name
        self.adapter = adapter

    def rate_limit_hit(self, client_key: str, now: float) -> int | None:
        return self.adapter.rate_limit_hit(client_key, now, 60, 1, 100)

    def cache_set(self, namespace: str, key: str, payload: Any, ttl_seconds: float) -> None:
        self.adapter.cache_set(namespace, key, payload, ttl_seconds)

    def cache_get(self, namespace: str, key: str) -> Any | None:
        return self.adapter.cache_get(namespace, key)

    def acquire_lease(self, name: str, ttl_seconds: float) -> tuple[str, bool]:
        token = f"{self.name}:owner"
        return token, self.adapter.acquire_lease(name, token, ttl_seconds)


def run_dual_worker_load(requests_per_worker: int = 50) -> dict[str, Any]:
    clock = FakeClock()
    adapter = InMemorySharedStateAdapter(clock=clock)
    workers = (Worker("worker-a", adapter), Worker("worker-b", adapter))

    def load_worker(worker: Worker) -> dict[str, int]:
        accepted = 0
        rejected = 0
        for index in range(requests_per_worker):
            retry_after = worker.rate_limit_hit(f"h11-03-client-{index}", clock())
            if retry_after is None:
                accepted += 1
            else:
                rejected += 1
        return {"accepted": accepted, "rejected": rejected}

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(load_worker, workers))
    expected_rejected = requests_per_worker
    if sum(item["accepted"] for item in results) != requests_per_worker:
        raise AssertionError(f"dual-worker rate-limit load did not share one window: {results!r}")
    if sum(item["rejected"] for item in results) != expected_rejected:
        raise AssertionError(f"dual-worker rate-limit rejection count mismatch: {results!r}")

    namespace = "market-pulse:staging:h11-03:cache-v13"
    for bucket in JSON_SAFE_BUCKETS:
        key = f"load:{bucket}"
        workers[0].cache_set(namespace, key, {"bucket": bucket, "safe": True}, 30)
        if workers[1].cache_get(namespace, key) != {"bucket": bucket, "safe": True}:
            raise AssertionError(f"cross-worker cache readback failed for {bucket}")

    lease_results: dict[str, str] = {}
    for lease_name in ("cache-flight:h11-03", "options-flight:h11-03", "background-updater"):
        token_a, acquired_a = workers[0].acquire_lease(lease_name, 10)
        token_b, acquired_b = workers[1].acquire_lease(lease_name, 10)
        if not acquired_a or acquired_b:
            raise AssertionError(f"single-owner contention failed for {lease_name}")
        if not adapter.release_lease(lease_name, token_a):
            raise AssertionError(f"first owner release failed for {lease_name}")
        if not adapter.acquire_lease(lease_name, token_b, 10):
            raise AssertionError(f"takeover after release failed for {lease_name}")
        if not adapter.release_lease(lease_name, token_b):
            raise AssertionError(f"takeover owner release failed for {lease_name}")
        lease_results[lease_name] = "single-owner-and-takeover-pass"

    stale_name = "options-flight:h11-03-stale"
    token_a, _ = workers[0].acquire_lease(stale_name, 5)
    clock.advance(6)
    token_b, acquired_b = workers[1].acquire_lease(stale_name, 5)
    if not acquired_b or adapter.release_lease(stale_name, token_a) or not adapter.release_lease(stale_name, token_b):
        raise AssertionError("owner-token fencing failed during options lease takeover")

    return {
        "status": "pass",
        "workers": [worker.name for worker in workers],
        "requests_per_worker": requests_per_worker,
        "total_requests": requests_per_worker * len(workers),
        "rate_limit": {
            "accepted": sum(item["accepted"] for item in results),
            "rejected": sum(item["rejected"] for item in results),
            "shared_window": True,
        },
        "l2_buckets": list(JSON_SAFE_BUCKETS),
        "leases": lease_results,
        "options_owner_token_fencing": "pass",
    }


def run_fault_injection() -> dict[str, str]:
    outcomes: dict[str, str] = {}
    test_app = Flask("td03-h11-03-fault-test")
    original_limit = security.API_RATE_LIMIT_PER_WINDOW
    try:
        security.API_RATE_LIMIT_PER_WINDOW = 1
        with patch.dict(os.environ, {"MARKET_PULSE_RATE_LIMIT_MODE": "redis"}), \
                patch.object(
                    security,
                    "_register_shared_rate_limit_window_hit",
                    side_effect=SharedStateUnavailable("h11-03 injected disconnect"),
                ):
            with test_app.test_request_context("/api/test", environ_base={"REMOTE_ADDR": "h11-03-client"}):
                response = security.enforce_api_rate_limit()
        if response is None or response.status_code != 503 or response.get_json().get("error_code") != "RATE_LIMIT_BACKEND_UNAVAILABLE":
            raise AssertionError("rate-limit fault did not fail closed")
        outcomes["rate_limit"] = "fail-closed-503"
    finally:
        security.API_RATE_LIMIT_PER_WINDOW = original_limit

    cache_key = "h11-03-fault-cache"
    with patch.dict(os.environ, {"MARKET_PULSE_CACHE_L2_MODE": "redis"}), \
            patch.object(cache, "_get_cache_l2_shared_adapter", side_effect=SharedStateUnavailable("h11-03 injected disconnect")):
        cache.write_memory_cache("global_markets", cache_key, {"safe": True}, 30)
        if cache.read_memory_cache("global_markets", cache_key, 30) != {"safe": True}:
            raise AssertionError("cache L2 fault did not preserve local fallback")
        with cache.cache_lock:
            cache.cache_data["global_markets"].pop(cache_key, None)
        if cache.read_memory_cache("global_markets", cache_key, 30) is not None:
            raise AssertionError("cache L2 fault unexpectedly returned unavailable shared data")
    outcomes["cache_l2"] = "local-fallback"

    with patch.dict(os.environ, {"MARKET_PULSE_SINGLE_FLIGHT_MODE": "redis"}), \
            patch.object(cache, "_get_single_flight_shared_adapter", side_effect=SharedStateUnavailable("h11-03 injected disconnect")):
        is_leader, handle = cache.claim_cache_flight("h11-03-single-flight")
        if not is_leader or handle.uses_shared_lease:
            raise AssertionError("single-flight fault did not return local fallback leader")
        cache.finish_cache_flight("h11-03-single-flight", handle)
    outcomes["single_flight"] = "local-fallback"

    with patch.dict(os.environ, {"MARKET_PULSE_SINGLE_FLIGHT_MODE": "redis"}), \
            patch.object(cache, "_get_single_flight_shared_adapter", side_effect=SharedStateUnavailable("h11-03 injected disconnect")):
        is_leader, handle = cache.claim_taifex_options_chain_flight("h11-03-options")
        if not is_leader or handle.uses_shared_lease:
            raise AssertionError("options lease fault did not return local fallback leader")
        cache.finish_taifex_options_chain_flight("h11-03-options", handle)
    outcomes["options_lease"] = "local-fallback"

    refresh_tasks = Mock()
    with patch.dict(os.environ, {"MARKET_PULSE_BACKGROUND_LEASE_MODE": "redis"}), \
            patch.object(cache, "_get_background_updater_shared_adapter", side_effect=SharedStateUnavailable("h11-03 injected disconnect")), \
            patch.object(cache, "_run_background_refresh_tasks", refresh_tasks):
        if cache.run_background_update_cycle() or refresh_tasks.called:
            raise AssertionError("background lease fault did not skip refresh")
    outcomes["background_updater"] = "skip-round"
    return outcomes


def run_offline_canary() -> dict[str, Any]:
    report = {
        "dual_worker_load": run_dual_worker_load(),
        "fault_injection": run_fault_injection(),
        "real_redis_canary": {
            "status": "not-run",
            "reason": "MARKET_PULSE_REDIS_URL is not configured; offline canary does not open external connections",
        },
    }
    if os.environ.get("MARKET_PULSE_REDIS_URL"):
        report["real_redis_canary"]["reason"] = "URL exists, but this offline canary intentionally does not open external connections"
    return report


def main() -> int:
    print(json.dumps(run_offline_canary(), ensure_ascii=False, indent=2, sort_keys=True))
    print("TD03_H11_03_CANARY_OFFLINE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
