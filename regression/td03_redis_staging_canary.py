"""TD-03 real Redis staging health, contract and dual-process canary.

This runner is opt-in through ``MARKET_PULSE_REDIS_URL`` (or ``--url``). It
uses a caller-supplied staging namespace, never imports ``app.py``, and never
touches SQLite or ``twse-cache.json``. The local Windows Redis build used by
the repository can speak RESP2 but not redis-py's default RESP3 handshake, so
the probe selects RESP2 explicitly; production adapter configuration is not
changed by this evidence runner.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
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

from shared_state import RedisSharedStateAdapter, SharedStateError, SharedStateUnavailable  # noqa: E402


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((percentile_value / 100) * (len(ordered) - 1)))))
    return round(ordered[index] * 1000, 3)


def open_client(url: str):
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - requirements guard
        raise RuntimeError("redis package is required") from exc
    return redis.Redis.from_url(
        url,
        protocol=2,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )


def adapter_for(url: str, namespace: str) -> RedisSharedStateAdapter:
    return RedisSharedStateAdapter(open_client(url), namespace=namespace)


def health_and_latency(client: Any, namespace: str) -> dict[str, Any]:
    ping_samples: list[float] = []
    for _ in range(30):
        started = time.perf_counter()
        if not client.ping():
            raise AssertionError("Redis PING returned false")
        ping_samples.append(time.perf_counter() - started)

    sentinel = f"{namespace}:sentinel:{uuid.uuid4().hex}"
    value = f"td03:{uuid.uuid4().hex}"
    try:
        if not client.set(sentinel, value, ex=2):
            raise AssertionError("Redis sentinel write failed")
        if client.get(sentinel) != value:
            raise AssertionError("Redis sentinel read-back failed")
        ttl = int(client.ttl(sentinel))
        if ttl not in (1, 2):
            raise AssertionError(f"Redis sentinel TTL was not short-lived: {ttl}")
    finally:
        client.delete(sentinel)

    info = client.info("server")
    return {
        "status": "pass",
        "redis_version": str(info.get("redis_version", "unknown")),
        "protocol": "RESP2 (local compatibility probe)",
        "sentinel_ttl_seconds": ttl,
        "ping_latency_ms": {
            "count": len(ping_samples),
            "p50": percentile(ping_samples, 50),
            "p95": percentile(ping_samples, 95),
            "p99": percentile(ping_samples, 99),
            "max": round(max(ping_samples) * 1000, 3),
        },
    }


def shared_contract(adapter: RedisSharedStateAdapter, namespace: str) -> dict[str, Any]:
    cache_key = f"cache:{uuid.uuid4().hex}"
    adapter.cache_set(namespace, cache_key, {"json": True, "items": [1, 2, 3]}, 2)
    if adapter.cache_get(namespace, cache_key) != {"json": True, "items": [1, 2, 3]}:
        raise AssertionError("Redis JSON-safe cache read-back failed")
    time.sleep(2.1)
    if adapter.cache_get(namespace, cache_key) is not None:
        raise AssertionError("Redis cache TTL did not expire")

    client_key = f"client:{uuid.uuid4().hex}"
    now = time.time()
    if adapter.rate_limit_hit(client_key, now, 60, 2, 10) is not None:
        raise AssertionError("first Redis rate-limit hit was rejected")
    if adapter.rate_limit_hit(client_key, now + 1, 60, 2, 10) is not None:
        raise AssertionError("second Redis rate-limit hit was rejected")
    retry_after = adapter.rate_limit_hit(client_key, now + 2, 60, 2, 10)
    if not retry_after or retry_after <= 0:
        raise AssertionError("Redis sliding-window rate limit did not reject third hit")

    lease = f"lease:{uuid.uuid4().hex}"
    if not adapter.acquire_lease(lease, "owner-a", 5):
        raise AssertionError("Redis lease initial acquire failed")
    if adapter.acquire_lease(lease, "owner-b", 5):
        raise AssertionError("Redis lease allowed two owners")
    if adapter.renew_lease(lease, "owner-b", 5):
        raise AssertionError("Redis lease allowed stale owner renewal")
    if not adapter.renew_lease(lease, "owner-a", 5):
        raise AssertionError("Redis lease renewal failed for current owner")
    if adapter.release_lease(lease, "owner-b"):
        raise AssertionError("Redis lease allowed stale owner release")
    if not adapter.release_lease(lease, "owner-a"):
        raise AssertionError("Redis lease release failed for current owner")

    return {
        "status": "pass",
        "json_safe_cache_ttl": "pass",
        "sliding_window_rate_limit": "pass",
        "owner_token_fencing": "pass",
    }


def process_action(url: str, namespace: str, action: str, key: str, gate: Any, output: Any) -> None:
    try:
        adapter = adapter_for(url, namespace)
        gate.wait(10)
        if action == "rate_and_lease_race":
            rate = adapter.rate_limit_hit(key, time.time(), 60, 1, 10)
            lease = adapter.acquire_lease(f"{key}:lease", f"owner:{os.getpid()}", 5)
            output.put({"pid": os.getpid(), "rate_accepted": rate is None, "lease_acquired": bool(lease)})
            return
        if action == "cache_set":
            adapter.cache_set(namespace, key, {"writer": os.getpid(), "shared": True}, 30)
            output.put({"pid": os.getpid(), "cache_set": True})
            return
        if action == "cache_get":
            output.put({"pid": os.getpid(), "cache_value": adapter.cache_get(namespace, key)})
            return
        raise ValueError(f"unknown process action: {action}")
    except Exception as exc:  # pragma: no cover - surfaced in parent report
        output.put({"pid": os.getpid(), "error": f"{type(exc).__name__}: {exc}"})


def run_processes(url: str, namespace: str) -> dict[str, Any]:
    context = mp.get_context("spawn")
    race_key = f"race:{uuid.uuid4().hex}"
    gate = context.Event()
    output = context.Queue()
    processes = [
        context.Process(target=process_action, args=(url, namespace, "rate_and_lease_race", race_key, gate, output))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    gate.set()
    race_results = [output.get(timeout=20) for _ in processes]
    for process in processes:
        process.join(20)
    if any(result.get("error") for result in race_results) or any(process.exitcode != 0 for process in processes):
        raise AssertionError(f"dual-process race failed: {race_results!r}")
    if sum(bool(result.get("rate_accepted")) for result in race_results) != 1:
        raise AssertionError(f"dual-process rate-limit was not single-owner: {race_results!r}")
    if sum(bool(result.get("lease_acquired")) for result in race_results) != 1:
        raise AssertionError(f"dual-process lease was not single-owner: {race_results!r}")

    cache_key = f"cross-worker:{uuid.uuid4().hex}"
    for action in ("cache_set", "cache_get"):
        gate = context.Event()
        output = context.Queue()
        process = context.Process(target=process_action, args=(url, namespace, action, cache_key, gate, output))
        process.start()
        gate.set()
        result = output.get(timeout=20)
        process.join(20)
        if process.exitcode != 0 or result.get("error"):
            raise AssertionError(f"cross-process {action} failed: {result!r}")
        if action == "cache_get" and result.get("cache_value", {}).get("shared") is not True:
            raise AssertionError(f"cross-process cache read-back failed: {result!r}")

    return {
        "status": "pass",
        "processes": 2,
        "rate_limit_single_accept": True,
        "lease_single_owner": True,
        "cross_process_cache_readback": True,
    }


def run_disconnect_fault(url: str, namespace: str) -> dict[str, Any]:
    bad_url = url.rsplit(":", 1)[0] + ":6392" if "://" in url else "redis://127.0.0.1:6392/1"
    adapter = adapter_for(bad_url, namespace)
    try:
        adapter.cache_get(namespace, "fault-injection")
    except (SharedStateUnavailable, SharedStateError) as exc:
        return {"status": "pass", "error_type": type(exc).__name__, "policy": "disconnect surfaced explicitly"}
    raise AssertionError("disconnected Redis endpoint did not surface an error")


def cleanup(client: Any, namespace: str) -> int:
    keys = list(client.scan_iter(match=f"{namespace}:*", count=100))
    if keys:
        client.delete(*keys)
    return len(keys)


def run(url: str, namespace: str) -> dict[str, Any]:
    client = open_client(url)
    client.ping()
    try:
        health = health_and_latency(client, namespace)
        adapter = RedisSharedStateAdapter(client, namespace=namespace)
        contract = shared_contract(adapter, namespace)
        dual_process = run_processes(url, namespace)
        fault = run_disconnect_fault(url, namespace)
        return {
            "status": "pass",
            "namespace": namespace,
            "health": health,
            "contract": contract,
            "dual_process": dual_process,
            "disconnect_fault": fault,
        }
    finally:
        cleanup_count = cleanup(client, namespace)
        client.close()
        # Keep cleanup visible without exposing URL or payloads.
        if cleanup_count < 0:  # pragma: no cover
            raise AssertionError("invalid cleanup count")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.environ.get("MARKET_PULSE_REDIS_URL", ""))
    parser.add_argument("--namespace", default=os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", ""))
    args = parser.parse_args()
    if not args.url:
        parser.error("--url or MARKET_PULSE_REDIS_URL is required")
    namespace = args.namespace.strip(":") or f"market-pulse:staging:td03:{uuid.uuid4().hex}"
    report = run(args.url, namespace)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("TD03_REDIS_STAGING_CANARY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
