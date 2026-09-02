"""TD-03 offline staging/canary preflight.

This preflight models two workers sharing one adapter without importing
``app.py``, starting Flask, touching SQLite, or writing the production cache.
It is intentionally offline: a real Redis canary is reported as pending until
the staging environment supplies an explicit ``MARKET_PULSE_REDIS_URL``.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared_state import (  # noqa: E402
    InMemorySharedStateAdapter,
    SharedStateAdapter,
    SharedStateUnavailable,
)


@dataclass
class FakeClock:
    value: float = 1_000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class Worker:
    """Small worker facade making cross-worker assertions explicit."""

    def __init__(self, name: str, adapter: SharedStateAdapter) -> None:
        self.name = name
        self.adapter = adapter

    def rate_limit_hit(self, client_key: str, now: float) -> int | None:
        return self.adapter.rate_limit_hit(client_key, now, 60, 1, 10)

    def cache_get(self, namespace: str, key: str) -> Any | None:
        return self.adapter.cache_get(namespace, key)

    def cache_set(self, namespace: str, key: str, payload: Any, ttl_seconds: float) -> None:
        self.adapter.cache_set(namespace, key, payload, ttl_seconds)

    def acquire(self, lease_name: str, ttl_seconds: float) -> tuple[str, bool]:
        token = f"{self.name}:owner"
        return token, self.adapter.acquire_lease(lease_name, token, ttl_seconds)


class FaultInjectingAdapter:
    """Adapter wrapper that raises a shared-backend error for selected calls."""

    def __init__(self, adapter: SharedStateAdapter, failing_operation: str) -> None:
        self._adapter = adapter
        self._failing_operation = failing_operation

    def _call(self, operation: str, callback: Callable[[], Any]) -> Any:
        if operation == self._failing_operation:
            raise SharedStateUnavailable(f"injected {operation} disconnect")
        return callback()

    def rate_limit_hit(self, client_key: str, now: float, window_seconds: float, limit: int, max_clients: int) -> int | None:
        return self._call("rate_limit_hit", lambda: self._adapter.rate_limit_hit(client_key, now, window_seconds, limit, max_clients))

    def cache_get(self, namespace: str, key: str) -> Any | None:
        return self._call("cache_get", lambda: self._adapter.cache_get(namespace, key))

    def cache_set(self, namespace: str, key: str, payload: Any, ttl_seconds: float) -> None:
        self._call("cache_set", lambda: self._adapter.cache_set(namespace, key, payload, ttl_seconds))

    def acquire_lease(self, name: str, owner_token: str, ttl_seconds: float) -> bool:
        return self._call("acquire_lease", lambda: self._adapter.acquire_lease(name, owner_token, ttl_seconds))

    def renew_lease(self, name: str, owner_token: str, ttl_seconds: float) -> bool:
        return self._call("renew_lease", lambda: self._adapter.renew_lease(name, owner_token, ttl_seconds))

    def release_lease(self, name: str, owner_token: str) -> bool:
        return self._call("release_lease", lambda: self._adapter.release_lease(name, owner_token))

    def lease_is_active(self, name: str) -> bool:
        return self._call("lease_is_active", lambda: self._adapter.lease_is_active(name))


def configured_workers() -> dict[str, int | None]:
    values: dict[str, int | None] = {}
    for name in ("Procfile", "render.yaml"):
        text = (ROOT / name).read_text(encoding="utf-8")
        match = re.search(r"--workers(?:=|\s+)(\d+)", text)
        values[name] = int(match.group(1)) if match else None
    return values


def assert_single_worker_deployment() -> dict[str, Any]:
    workers = configured_workers()
    if workers != {"Procfile": 1, "render.yaml": 1}:
        raise AssertionError(f"deployment worker gate failed: {workers}")
    return {"status": "pass", "workers": workers, "gate": "both deployment entries remain at one worker"}


def run_normal_canary() -> dict[str, Any]:
    clock = FakeClock()
    adapter = InMemorySharedStateAdapter(clock=clock)
    worker_a = Worker("worker-a", adapter)
    worker_b = Worker("worker-b", adapter)
    namespace = "market-pulse:v1:cache-v13:canary"

    first_hit = worker_a.rate_limit_hit("canary-client", clock())
    second_hit = worker_b.rate_limit_hit("canary-client", clock() + 1)
    if first_hit is not None or not second_hit or second_hit <= 0:
        raise AssertionError(f"shared rate-limit assertion failed: {first_hit=}, {second_hit=}")

    worker_a.cache_set(namespace, "shared-key", {"writer": "worker-a", "safe": True}, 30)
    cache_readback = worker_b.cache_get(namespace, "shared-key")
    if cache_readback != {"writer": "worker-a", "safe": True}:
        raise AssertionError(f"cross-worker cache assertion failed: {cache_readback!r}")

    lease_name = "cache-flight:canary"
    token_a, acquired_a = worker_a.acquire(lease_name, 10)
    token_b, acquired_b = worker_b.acquire(lease_name, 10)
    if not acquired_a or acquired_b or not adapter.release_lease(lease_name, token_a):
        raise AssertionError("lease contention/release assertion failed")
    if not adapter.acquire_lease(lease_name, token_b, 10):
        raise AssertionError("lease takeover after release assertion failed")
    if not adapter.release_lease(lease_name, token_b):
        raise AssertionError("new owner release assertion failed")

    stale_lease = "cache-flight:stale-canary"
    if not adapter.acquire_lease(stale_lease, token_a, 5):
        raise AssertionError("stale lease initial claim failed")
    clock.advance(6)
    if not adapter.acquire_lease(stale_lease, token_b, 5):
        raise AssertionError("expired lease takeover failed")
    if adapter.release_lease(stale_lease, token_a):
        raise AssertionError("stale owner released the new lease")
    if not adapter.release_lease(stale_lease, token_b):
        raise AssertionError("current owner could not release takeover lease")

    scheduler_lease = "background-updater"
    _, scheduler_a = worker_a.acquire(scheduler_lease, 5)
    _, scheduler_b = worker_b.acquire(scheduler_lease, 5)
    if not scheduler_a or scheduler_b:
        raise AssertionError("scheduler single-owner contention assertion failed")
    clock.advance(6)
    _, scheduler_takeover = worker_b.acquire(scheduler_lease, 5)
    if not scheduler_takeover:
        raise AssertionError("scheduler takeover after expiry assertion failed")

    return {
        "status": "pass",
        "workers": [worker_a.name, worker_b.name],
        "shared_rate_limit": {"first_hit": first_hit, "second_hit_retry_after": second_hit},
        "shared_cache_readback": cache_readback,
        "lease_contention_and_fencing": "pass",
        "background_scheduler_single_owner_and_takeover": "pass",
    }


def run_fault_injection() -> dict[str, Any]:
    backend = InMemorySharedStateAdapter()
    checks: dict[str, str] = {}
    for operation in ("rate_limit_hit", "cache_get", "acquire_lease", "lease_is_active"):
        adapter = FaultInjectingAdapter(backend, operation)
        try:
            if operation == "rate_limit_hit":
                adapter.rate_limit_hit("fault-client", 1_000, 60, 1, 10)
            elif operation == "cache_get":
                adapter.cache_get("canary", "fault-key")
            elif operation == "acquire_lease":
                adapter.acquire_lease("fault-lease", "fault-owner", 10)
            else:
                adapter.lease_is_active("fault-lease")
        except SharedStateUnavailable:
            checks[operation] = "explicit-unavailable"
        else:
            raise AssertionError(f"fault injection was not surfaced for {operation}")
    return {"status": "pass", "checks": checks, "policy": "backend failure is explicit; no local lock is silently created"}


def run_offline_canary() -> dict[str, Any]:
    deployment = assert_single_worker_deployment()
    normal = run_normal_canary()
    fault_injection = run_fault_injection()
    redis_status = {
        "status": "not-run",
        "reason": "MARKET_PULSE_REDIS_URL is not configured; offline preflight does not claim real Redis validation",
    }
    if os.environ.get("MARKET_PULSE_REDIS_URL"):
        redis_status["reason"] = "URL exists, but this offline preflight intentionally does not open external connections"
    return {
        "deployment": deployment,
        "normal": normal,
        "fault_injection": fault_injection,
        "real_redis_canary": redis_status,
    }


def main() -> int:
    report = run_offline_canary()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("TD03_SHARED_STATE_CANARY_OFFLINE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
