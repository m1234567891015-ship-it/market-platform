"""TD-03 production shared-mode integration probe against isolated staging Redis.

The probe exercises the existing security/cache integration paths without
starting the Flask server or writing production data. It is intentionally a
staging evidence runner: deployment files, worker count and production
defaults remain unchanged.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cache  # noqa: E402
import security  # noqa: E402


def reset_adapters() -> None:
    security.API_RATE_LIMIT_SHARED_ADAPTER = None
    cache.cache_l2_shared_adapter = None
    cache.single_flight_shared_adapter = None
    cache.background_updater_shared_adapter = None


def clear_local_cache(bucket: str, key: str) -> None:
    with cache.cache_lock:
        cache.cache_data.setdefault(bucket, {}).pop(key, None)


def process_shared_race(key: str, start: Any, output: Any) -> None:
    try:
        app = Flask(f"td03-worker-{os.getpid()}")
        start.wait(10)
        with app.test_request_context("/api/td03", environ_base={"REMOTE_ADDR": "td03-shared-client"}):
            response = security.enforce_api_rate_limit()
        is_leader, handle = cache.claim_cache_flight(key)
        output.put(
            {
                "pid": os.getpid(),
                "rate_accepted": response is None,
                "rate_status": response.status_code if response is not None else 200,
                "flight_leader": is_leader,
                "uses_shared_lease": handle.uses_shared_lease,
            }
        )
    except Exception as exc:  # pragma: no cover - surfaced in parent report
        output.put({"pid": os.getpid(), "error": f"{type(exc).__name__}: {exc}"})


def process_cache_action(action: str, key: str, start: Any, output: Any) -> None:
    try:
        start.wait(10)
        if action == "set":
            cache.write_memory_cache("global_markets", key, {"from_worker": True}, 30)
            output.put({"pid": os.getpid(), "set": True})
            return
        value = cache.read_memory_cache("global_markets", key, 30)
        output.put({"pid": os.getpid(), "value": value})
    except Exception as exc:  # pragma: no cover - surfaced in parent report
        output.put({"pid": os.getpid(), "error": f"{type(exc).__name__}: {exc}"})


def run_dual_worker_paths() -> dict[str, Any]:
    context = mp.get_context("spawn")
    start = context.Event()
    output = context.Queue()
    key = f"td03-dual:{uuid.uuid4().hex}"
    processes = [context.Process(target=process_shared_race, args=(key, start, output)) for _ in range(2)]
    for process in processes:
        process.start()
    start.set()
    results = [output.get(timeout=20) for _ in processes]
    for process in processes:
        process.join(20)
    if any(result.get("error") for result in results) or any(process.exitcode != 0 for process in processes):
        raise AssertionError(f"production dual-worker race failed: {results!r}")
    if sum(bool(result.get("rate_accepted")) for result in results) != 1:
        raise AssertionError(f"production rate-limit did not allow exactly one worker: {results!r}")
    if sum(bool(result.get("flight_leader")) for result in results) != 1:
        raise AssertionError(f"production single-flight did not elect exactly one leader: {results!r}")

    cache_key = f"td03-cache:{uuid.uuid4().hex}"
    for action in ("set", "get"):
        start = context.Event()
        output = context.Queue()
        process = context.Process(target=process_cache_action, args=(action, cache_key, start, output))
        process.start()
        start.set()
        result = output.get(timeout=20)
        process.join(20)
        if process.exitcode != 0 or result.get("error"):
            raise AssertionError(f"production cross-worker cache {action} failed: {result!r}")
        if action == "get" and result.get("value") != {"from_worker": True}:
            raise AssertionError(f"production cross-worker cache read-back failed: {result!r}")
    return {
        "status": "pass",
        "processes": 2,
        "shared_rate_limit_single_accept": True,
        "shared_single_flight_single_leader": True,
        "shared_cache_cross_process_readback": True,
    }


def run_single_process_paths() -> dict[str, Any]:
    reset_adapters()
    app = Flask("td03-production-shared-mode")
    security.API_RATE_LIMIT_PER_WINDOW = 1
    with security.API_RATE_LIMIT_LOCK:
        security.API_RATE_LIMIT_STATE.clear()
    with app.test_request_context("/api/td03", environ_base={"REMOTE_ADDR": "td03-local-client"}):
        first = security.enforce_api_rate_limit()
    with app.test_request_context("/api/td03", environ_base={"REMOTE_ADDR": "td03-local-client"}):
        second = security.enforce_api_rate_limit()
    if first is not None or second is None or second.status_code != 429:
        raise AssertionError("production Redis rate-limit path did not enforce shared result")
    with security.API_RATE_LIMIT_LOCK:
        if security.API_RATE_LIMIT_STATE:
            raise AssertionError("production Redis rate-limit path wrote local state")

    cache_key = f"td03-l2:{uuid.uuid4().hex}"
    cache.write_memory_cache("global_markets", cache_key, {"shared": True}, 30)
    clear_local_cache("global_markets", cache_key)
    if cache.read_memory_cache("global_markets", cache_key, 30) != {"shared": True}:
        raise AssertionError("production Redis L2 did not promote shared cache hit")

    flight_key = f"td03-flight:{uuid.uuid4().hex}"
    is_leader, handle = cache.claim_cache_flight(flight_key)
    if not is_leader or not handle.uses_shared_lease:
        raise AssertionError("production Redis single-flight did not acquire shared lease")
    cache.finish_cache_flight(flight_key, handle)

    with patch.object(cache, "_run_background_refresh_tasks", Mock()) as refresh:
        if not cache.run_background_update_cycle() or not refresh.called:
            raise AssertionError("production Redis background lease did not own refresh cycle")
    return {
        "status": "pass",
        "rate_limit": "shared-result-and-no-local-write",
        "cache_l2": "shared-readback-and-promotion",
        "single_flight": "shared-lease-acquire-and-release",
        "background_lease": "shared-owner-refresh-and-release",
    }


def run_fault_paths() -> dict[str, str]:
    bad_url = "redis://127.0.0.1:6392/1"
    previous_url = os.environ.get("MARKET_PULSE_REDIS_URL")
    os.environ["MARKET_PULSE_REDIS_URL"] = bad_url
    try:
        reset_adapters()
        app = Flask("td03-production-faults")
        with app.test_request_context("/api/td03", environ_base={"REMOTE_ADDR": "td03-fault-client"}):
            response = security.enforce_api_rate_limit()
        if response is None or response.status_code != 503 or response.get_json().get("error_code") != "RATE_LIMIT_BACKEND_UNAVAILABLE":
            raise AssertionError("real Redis rate-limit disconnect did not fail closed")

        reset_adapters()
        key = f"td03-fault-cache:{uuid.uuid4().hex}"
        cache.write_memory_cache("global_markets", key, {"local": True}, 30)
        if cache.read_memory_cache("global_markets", key, 30) != {"local": True}:
            raise AssertionError("real Redis L2 disconnect did not preserve local fallback")
        clear_local_cache("global_markets", key)
        if cache.read_memory_cache("global_markets", key, 30) is not None:
            raise AssertionError("real Redis L2 disconnect returned unavailable shared data")

        reset_adapters()
        fault_flight_key = f"td03-fault-flight:{uuid.uuid4().hex}"
        is_leader, handle = cache.claim_cache_flight(fault_flight_key)
        if not is_leader or handle.uses_shared_lease:
            raise AssertionError("real Redis single-flight disconnect did not use local fallback")
        cache.finish_cache_flight(fault_flight_key, handle)

        reset_adapters()
        with patch.object(cache, "_run_background_refresh_tasks", Mock()) as refresh:
            if cache.run_background_update_cycle() or refresh.called:
                raise AssertionError("real Redis background disconnect did not skip refresh")
        return {
            "rate_limit": "fail-closed-503",
            "cache_l2": "local-fallback",
            "single_flight": "local-fallback",
            "background_lease": "skip-round",
        }
    finally:
        if previous_url is None:
            os.environ.pop("MARKET_PULSE_REDIS_URL", None)
        else:
            os.environ["MARKET_PULSE_REDIS_URL"] = previous_url


def main() -> int:
    required = os.environ.get("MARKET_PULSE_REDIS_URL", "").strip()
    if not required:
        raise SystemExit("MARKET_PULSE_REDIS_URL is required")
    namespace = os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", "market-pulse:staging:td03-prod").strip(":")
    namespace = f"{namespace}:{uuid.uuid4().hex}"
    os.environ["MARKET_PULSE_SHARED_STATE_NAMESPACE"] = namespace
    security.API_RATE_LIMIT_SHARED_NAMESPACE = namespace
    os.environ["MARKET_PULSE_RATE_LIMIT_MODE"] = "redis"
    os.environ["MARKET_PULSE_CACHE_L2_MODE"] = "redis"
    os.environ["MARKET_PULSE_SINGLE_FLIGHT_MODE"] = "redis"
    os.environ["MARKET_PULSE_BACKGROUND_LEASE_MODE"] = "redis"
    os.environ["MARKET_PULSE_API_RATE_LIMIT_PER_MINUTE"] = "1"
    security.API_RATE_LIMIT_PER_WINDOW = 1
    report = {
        "status": "pass",
        "single_process": run_single_process_paths(),
        "dual_worker": run_dual_worker_paths(),
        "fault_injection": run_fault_paths(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("TD03_PRODUCTION_SHARED_MODE_PROBE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
