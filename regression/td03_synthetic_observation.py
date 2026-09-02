"""TD-03 accelerated synthetic observation for a Redis/Valkey endpoint.

This is a substitute validation runner, not a production observation-period
claim. It repeatedly exercises the shared-state health, cache TTL, sliding
window rate limit and owner-token lease paths for a bounded duration. The
endpoint is supplied through ``MARKET_PULSE_REDIS_URL`` and is never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_state import RedisSharedStateAdapter  # noqa: E402


def open_client(url: str):
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - requirements guard
        raise RuntimeError("redis package is required") from exc
    return redis.Redis.from_url(
        url,
        protocol=2,
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )


def run_cycle(client: Any, adapter: RedisSharedStateAdapter, namespace: str, cycle: int) -> float:
    started = time.perf_counter()
    if not client.ping():
        raise AssertionError("Redis PING returned false")

    cache_key = f"observation:{cycle}:{uuid.uuid4().hex}"
    payload = {"cycle": cycle, "probe": "td03-synthetic-observation"}
    adapter.cache_set(namespace, cache_key, payload, 5)
    if adapter.cache_get(namespace, cache_key) != payload:
        raise AssertionError("shared cache read-back failed")

    rate_key = f"observation-rate:{cycle}:{uuid.uuid4().hex}"
    now = time.time()
    if adapter.rate_limit_hit(rate_key, now, 60, 2, 100) is not None:
        raise AssertionError("first rate-limit hit was rejected")
    if adapter.rate_limit_hit(rate_key, now + 1, 60, 2, 100) is not None:
        raise AssertionError("second rate-limit hit was rejected")
    if not adapter.rate_limit_hit(rate_key, now + 2, 60, 2, 100):
        raise AssertionError("third rate-limit hit was not rejected")

    lease_name = f"observation-lease:{cycle}:{uuid.uuid4().hex}"
    owner = f"observation-owner:{uuid.uuid4().hex}"
    if not adapter.acquire_lease(lease_name, owner, 5):
        raise AssertionError("lease acquire failed")
    try:
        if not adapter.renew_lease(lease_name, owner, 5):
            raise AssertionError("lease renewal failed")
    finally:
        if not adapter.release_lease(lease_name, owner):
            raise AssertionError("lease release failed")
    return time.perf_counter() - started


def run(url: str, namespace: str, duration_seconds: float, interval_seconds: float) -> dict[str, Any]:
    if duration_seconds <= 0 or interval_seconds < 0:
        raise ValueError("duration_seconds must be positive and interval_seconds cannot be negative")
    client = open_client(url)
    latencies: list[float] = []
    cycles = 0
    deadline = time.monotonic() + duration_seconds
    try:
        client.ping()
        adapter = RedisSharedStateAdapter(client, namespace=namespace)
        while cycles == 0 or time.monotonic() < deadline:
            latencies.append(run_cycle(client, adapter, namespace, cycles))
            cycles += 1
            if time.monotonic() >= deadline:
                break
            time.sleep(min(interval_seconds, max(0.0, deadline - time.monotonic())))
        return {
            "status": "pass",
            "namespace": namespace,
            "duration_seconds": round(duration_seconds, 3),
            "cycles": cycles,
            "cycle_latency_ms": {
                "p50": round(statistics.median(latencies) * 1000, 3),
                "max": round(max(latencies) * 1000, 3),
            },
        }
    finally:
        keys = list(client.scan_iter(match=f"{namespace}:*", count=100))
        if keys:
            client.delete(*keys)
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("MARKET_PULSE_REDIS_URL", ""))
    parser.add_argument("--namespace", default=os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", ""))
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if not args.url:
        parser.error("--url or MARKET_PULSE_REDIS_URL is required")
    namespace = args.namespace.strip(":") or f"market-pulse:observation:td03:{uuid.uuid4().hex}"
    report = run(args.url, namespace, args.duration_seconds, args.interval_seconds)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("TD03_SYNTHETIC_OBSERVATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
