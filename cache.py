"""In-memory cache state and core cache machinery extracted from app.py
(TD-01 slice 2a + 2b).

Slice 2a moved pure state (locks, registries, the shared cache_data dict).
Slice 2b moves the functions that operate on it: disk persistence
(load/save/build_disk_cache_snapshot), the generic memory-cache accessors
(read/write_memory_cache), request-coalescing (claim/finish_cache_flight),
the background refresh lifecycle (ensure_cache/update_loop/
start_background_updater), and the site-data sanitizer.

Every existing mutation of the state this module owns is in-place (dict item
assignment, lock context managers), never a wholesale reassignment of the
name itself, so re-exporting into app.py's namespace via `from cache import
...` preserves identity and behavior exactly - confirmed by grepping every
consumer across app.py and test_derivatives_platform.py before moving.

refresh_cache is here too, but it only does one thing besides pure cache
bookkeeping: call app.py's build_site_data() to get fresh data. That's a
deferred, call-time `import app` (not `from app import build_site_data`),
which matters for two reasons: it avoids a module-load-time circular import
(app.py imports from cache; cache would otherwise need app at import time),
and `app.build_site_data(...)` re-resolves the attribute on every call, so
`patch.object(app, "build_site_data", ...)`-style test patches still work
correctly from inside this module - a bare `from app import X` copy would
not observe such patches (see TD-01 slice 1's API_RATE_LIMIT_PER_WINDOW
lesson: bare-name calls resolve against the *defining* module's globals).
As of TD-01 slice 4 batch 5 (the builders.py extraction's final batch),
`build_site_data` itself no longer lives in app.py - it now resolves
through app.py's `from builders import build_site_data` re-export, so
`app.build_site_data(...)` still reaches the same function, just one hop
further via app.py's namespace. This module needed no changes for that move.

update_loop makes the same deferred call for app.refresh_tpex_cache(), which
stays in app.py as builder/orchestration code (not a mechanical relocation
like the rest of this file) - it is still resident in app.py, but as of
TD-01 slice 3 (the fetchers.py extraction, batches 1-5) every fetch_* call it
makes now resolves through a `from fetchers import ...` import instead of a
locally-defined function, so the "call chain" this docstring used to flag as
unresolved is fully untangled.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from flask import g, has_request_context
from urllib.parse import urlsplit

from market_config import CACHE_BUCKET_MAX_ENTRIES, CACHE_TTL_SECONDS, EXCLUDED_SECTOR_SOURCE_NAMES
from shared_state import (
    RedisSharedStateAdapter,
    SharedStateAdapter,
    SharedStateError,
    SharedStateTimeout,
    SharedStateUnavailable,
)

LOGGER = logging.getLogger("market_pulse")

BASE_DIR = Path(__file__).resolve().parent
BUNDLED_CACHE_FILE = BASE_DIR / "twse-cache.json"
CACHE_FILE = Path(os.environ.get("MARKET_PULSE_CACHE_FILE", str(BUNDLED_CACHE_FILE)))
CACHE_VERSION = 13
UPDATE_INTERVAL_SECONDS = 60
PUBLIC_CACHE_ERROR_MESSAGE = "背景資料更新暫時無法完成，請稍後再試"

cache_lock = threading.RLock()
cache_refresh_lock = threading.Lock()
cache_flight_lock = threading.Lock()
cache_flights: dict[str, CacheFlightHandle] = {}
CACHE_FLIGHT_WAIT_SECONDS = 120
CACHE_FLIGHT_FOLLOWER_MAX_WAIT_SECONDS = 2.0
SINGLE_FLIGHT_MODE = os.environ.get("MARKET_PULSE_SINGLE_FLIGHT_MODE", "local").strip().lower()
SINGLE_FLIGHT_LEASE_TTL_SECONDS = CACHE_FLIGHT_WAIT_SECONDS
SINGLE_FLIGHT_POLL_SECONDS = 0.25
single_flight_shared_adapter: SharedStateAdapter | None = None
single_flight_shared_adapter_lock = threading.Lock()
CACHE_L2_MODE = os.environ.get("MARKET_PULSE_CACHE_L2_MODE", "local").strip().lower()
CACHE_L2_BUCKETS = frozenset(
    {
        "live_search_dedup",
        "us_options_chains",
        "global_market_items",
        "yahoo_tw_future_technical_candles",
        "taifex_openapi_list",
        "yahoo_tw_stock_resources",
        "global_markets",
        "sector_charts",
        "stock_details",
        "taifex_options_chain",
        "us_etf_center",
        "yahoo_tw_option_chain",
    }
)
CACHE_L2_NAMESPACE = f"{os.environ.get('MARKET_PULSE_SHARED_STATE_NAMESPACE', 'market-pulse:v1')}:cache-v{CACHE_VERSION}"
cache_l2_shared_adapter: SharedStateAdapter | None = None
cache_l2_shared_adapter_lock = threading.Lock()

background_updater_lock = threading.Lock()
background_updater_started = False
BACKGROUND_UPDATER_MODE = os.environ.get("MARKET_PULSE_BACKGROUND_LEASE_MODE", "local").strip().lower()
BACKGROUND_UPDATER_LEASE_NAME = "background-updater"
BACKGROUND_UPDATER_LEASE_TTL_SECONDS = max(120, UPDATE_INTERVAL_SECONDS * 2)
BACKGROUND_UPDATER_RENEW_INTERVAL_SECONDS = max(1.0, BACKGROUND_UPDATER_LEASE_TTL_SECONDS / 3)
background_updater_shared_adapter: SharedStateAdapter | None = None
background_updater_shared_adapter_lock = threading.Lock()

penny_sector_recommendation_lock = threading.Lock()
penny_sector_recommendation_cache: dict[str, Any] = {}
PENNY_SECTOR_RECOMMENDATION_CACHE_SECONDS = CACHE_TTL_SECONDS["penny_sector_recommendation"]

# Coalesces concurrent requests for the same option-chain cache key (e.g. a page that fires
# /api/options/chain and /api/ai-analysis for the same underlying at once) so only one of them
# runs the ~12-day TAIFEX scan; the rest wait for and reuse that real result instead of each
# triggering their own redundant scan.
taifex_options_chain_inflight: dict[str, CacheFlightHandle] = {}
taifex_options_chain_inflight_lock = threading.Lock()

PROVIDER_FAILURE_COOLDOWN_SECONDS = 45.0
PROVIDER_COOLDOWN_MAX_ENTRIES = 64
provider_cooldown_lock = threading.Lock()
provider_cooldowns: dict[str, float] = {}

cache_data: dict[str, Any] = {
    "site_data": None,
    "all_stocks": [],
    "market_date": None,
    "cached_at": None,
    "last_error": None,
    "provider_status": {
        "tpex": {"status": "never_loaded", "lastSuccessAt": None, "lastAttemptAt": None, "lastError": None},
        "twse": {"status": "never_loaded", "lastSuccessAt": None, "lastAttemptAt": None, "lastError": None},
    },
    "stock_details": {},
    "sector_charts": {},
    "global_markets": {},
    "international_market_indexes": {"stored_at": 0.0, "payload": []},
    "global_market_items": {},
    "external_text": {},
    "treasury_yield_curve_rows": {"stored_at": 0.0, "rows": []},
    "us_options_chains": {},
    "yahoo_tw_option_chain": {},
    "yahoo_tw_stock_resources": {},
    "us_etf_center": {},
    "taifex_options_chain": {},
    "us_listed_universe": {"stored_at": 0.0, "items": [], "totals": {}},
    "shareholder_distributions": {},
    "shareholder_distributions_stored_at": 0.0,
    "live_search_dedup": {},
    "twse_company_industries": {"stored_at": 0.0, "items": {}},
    "sector_fund_flow": {},
    "yahoo_tw_future_quotes": {"stored_at": 0.0, "items": {}},
    "yahoo_tw_future_technical_candles": {},
    "taifex_openapi_list": {},
}

_yahoo_options_crumb: dict[str, Any] = {"value": "", "stored_at": 0.0}

# TD-12: bounded LRU cap for the per-key caches that grow one entry per
# distinct (symbol/code/query) combination for the life of the process, with
# no other bound (TD-03/TD-12's "memory only grows, never shrinks" finding).
# Buckets NOT listed here are wholesale-overwrite single blobs (the whole
# dataset replaces atomically on refresh, e.g. international_market_indexes,
# treasury_yield_curve_rows, us_listed_universe) and don't need a cap.
#
# live_search_dedup (行為微調, TD-05 batch 12c): previously the only bucket
# with any bound at all - a hand-rolled O(n) full-dict-rebuild filtering out
# entries older than LIVE_SEARCH_DEDUP_SECONDS on every write. Converted to
# this same shared mechanism: bounded by entry COUNT instead of by
# TTL-triggered purge. This is a genuine behavior change (not pure
# behavior-preserving cleanup like the other 12 buckets below), called out
# separately per its own commit.
BUCKET_CAPS: dict[str, int] = dict(CACHE_BUCKET_MAX_ENTRIES)


def enforce_bucket_cap(bucket: str) -> None:
    """Bound cache_data[bucket] to its BUCKET_CAPS entry (no-op if the bucket
    isn't listed there) by evicting the oldest-inserted keys once it grows
    past the cap. Must be called while already holding cache_lock - this
    mutates cache_data directly, same as every other in-place cache_data
    write in this module and its callers.

    This is insertion-order eviction (relying on a plain dict's guaranteed
    insertion order), not access-recency LRU - the goal is bounding
    previously-unbounded memory growth, not optimizing which entry survives
    longest. True recency-based LRU would need every direct
    `cache_data[bucket].get(key)` read site across the repo to also promote
    that key (not just writes), which is a bigger change than this cleanup
    warrants - the caps below are sized with headroom precisely because
    eviction order is coarse, not perfectly recency-aware.
    """
    cap = BUCKET_CAPS.get(bucket)
    if cap is None:
        return
    entries = cache_data.get(bucket)
    if not isinstance(entries, dict):
        return
    overflow = len(entries) - cap
    if overflow <= 0:
        return
    for key in list(entries.keys())[:overflow]:
        entries.pop(key, None)


def _cache_l2_enabled() -> bool:
    mode = str(os.environ.get("MARKET_PULSE_CACHE_L2_MODE", CACHE_L2_MODE)).strip().lower()
    return mode == "redis"


def _build_cache_l2_shared_adapter() -> SharedStateAdapter:
    redis_url = str(os.environ.get("MARKET_PULSE_REDIS_URL") or "").strip()
    if not redis_url:
        raise SharedStateUnavailable("MARKET_PULSE_REDIS_URL is required for cache L2")
    try:
        import redis
    except ImportError as exc:
        raise SharedStateUnavailable("redis package is required for cache L2") from exc
    timeout_seconds = max(0.1, float(os.environ.get("MARKET_PULSE_SHARED_STATE_TIMEOUT_SECONDS", "1")))
    try:
        client = redis.Redis.from_url(
            redis_url,
            protocol=2,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            decode_responses=True,
        )
        client.ping()
    except TimeoutError as exc:
        raise SharedStateTimeout("Redis cache L2 health check timed out") from exc
    except Exception as exc:
        raise SharedStateUnavailable("Redis cache L2 health check failed") from exc
    return RedisSharedStateAdapter(
        client,
        namespace=str(os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", "market-pulse:v1")),
    )


def _get_cache_l2_shared_adapter() -> SharedStateAdapter:
    global cache_l2_shared_adapter
    if cache_l2_shared_adapter is not None:
        return cache_l2_shared_adapter
    with cache_l2_shared_adapter_lock:
        if cache_l2_shared_adapter is None:
            cache_l2_shared_adapter = _build_cache_l2_shared_adapter()
        return cache_l2_shared_adapter


def _cache_l2_namespace(bucket: str) -> str:
    return f"{CACHE_L2_NAMESPACE}:{bucket}"


def _acquire_cache_lock(deadline: float | None = None) -> bool:
    if deadline is None:
        cache_lock.acquire()
        return True
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return False
    return cache_lock.acquire(timeout=remaining)


def read_memory_cache(
    bucket: str,
    key: str,
    ttl_seconds: int | float,
    *,
    deadline: float | None = None,
) -> Any | None:
    now = time.time()
    if not _acquire_cache_lock(deadline):
        return None
    try:
        cached = cache_data.get(bucket, {}).get(key)
    finally:
        cache_lock.release()
    if cached and now - float(cached.get("stored_at") or 0) < ttl_seconds:
        return cached.get("payload")
    if deadline is None and _cache_l2_enabled() and bucket in CACHE_L2_BUCKETS and ttl_seconds > 0:
        try:
            payload = _get_cache_l2_shared_adapter().cache_get(_cache_l2_namespace(bucket), key)
        except SharedStateError as exc:
            LOGGER.debug("Cache L2 read degraded to local miss bucket=%s error_type=%s", bucket, type(exc).__name__)
        else:
            if payload is not None:
                if not _acquire_cache_lock(deadline):
                    return None
                try:
                    cache_data.setdefault(bucket, {})[key] = {
                        "stored_at": now,
                        "payload": copy.deepcopy(payload),
                    }
                    enforce_bucket_cap(bucket)
                finally:
                    cache_lock.release()
                LOGGER.debug("Cache L2 hit bucket=%s", bucket)
                return payload
    return None


def read_stale_memory_cache(
    bucket: str,
    key: str,
    max_age_seconds: int | float,
    *,
    deadline: float | None = None,
) -> tuple[Any | None, float | None]:
    """Return a locally persisted payload only when its age is explicitly bounded."""
    if not _acquire_cache_lock(deadline):
        return None, None
    try:
        cached = cache_data.get(bucket, {}).get(key)
    finally:
        cache_lock.release()
    if not isinstance(cached, dict):
        return None, None
    stored_at = float(cached.get("stored_at") or 0)
    age = time.time() - stored_at
    if stored_at <= 0 or age < 0 or age > max_age_seconds:
        return None, None
    return cached.get("payload"), stored_at


def write_memory_cache(
    bucket: str,
    key: str,
    payload: Any,
    ttl_seconds: int | float | None = None,
    *,
    deadline: float | None = None,
) -> None:
    if not _acquire_cache_lock(deadline):
        return
    try:
        cache_data.setdefault(bucket, {})[key] = {"stored_at": time.time(), "payload": payload}
        enforce_bucket_cap(bucket)
    finally:
        cache_lock.release()
    if (
        deadline is None
        and _cache_l2_enabled()
        and bucket in CACHE_L2_BUCKETS
        and ttl_seconds
        and ttl_seconds > 0
        and (deadline is None or (deadline - time.monotonic()) > 0)
    ):
        try:
            _get_cache_l2_shared_adapter().cache_set(_cache_l2_namespace(bucket), key, payload, ttl_seconds)
        except (SharedStateError, TypeError, ValueError, OverflowError) as exc:
            LOGGER.debug("Cache L2 write skipped bucket=%s error_type=%s", bucket, type(exc).__name__)


class CacheFlightHandle:
    """Local event plus optional cross-worker lease ownership."""

    def __init__(
        self,
        event: threading.Event,
        shared_adapter: SharedStateAdapter | None = None,
        lease_name: str | None = None,
        owner_token: str | None = None,
    ) -> None:
        self.event = event
        self.shared_adapter = shared_adapter
        self.lease_name = lease_name
        self.owner_token = owner_token
        self.result: Any = None
        self.error: BaseException | None = None
        self.result_ready = False

    @property
    def uses_shared_lease(self) -> bool:
        return self.shared_adapter is not None and self.lease_name is not None

    def wait(self, timeout: float | None = None) -> bool:
        if not self.uses_shared_lease:
            return self.event.wait(timeout)
        wait_seconds = CACHE_FLIGHT_FOLLOWER_MAX_WAIT_SECONDS if timeout is None else max(0.0, timeout)
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                if not self.shared_adapter.lease_is_active(self.lease_name):
                    return True
            except SharedStateError as exc:
                LOGGER.warning("Shared cache-flight wait degraded to local path error_type=%s", type(exc).__name__)
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            time.sleep(min(SINGLE_FLIGHT_POLL_SECONDS, remaining))


class ProviderCooldownError(RuntimeError):
    """A provider is in a short local failure cooldown; no data was fabricated."""


class ProviderFlightUnavailable(RuntimeError):
    """A follower could not obtain a result within its own bounded deadline."""


def provider_key_for_url(url: str) -> str:
    """Return a stable, provider-scoped identity without retaining arbitrary URLs."""
    parsed = urlsplit(str(url or ""))
    host = (parsed.hostname or "").strip().lower()
    return f"host:{host}" if host else f"url:{str(url or '').strip()[:96]}"


def _institution_provider_observe(event: str, **fields: Any) -> None:
    if not has_request_context() or getattr(g, "institution_observability", None) is None:
        return
    import app

    app.institution_observability_log(event, **fields)


def _provider_failure_kind(error: BaseException | str) -> str | None:
    if isinstance(error, str):
        error_text = error.lower()
        error_name = ""
    else:
        error_text = str(error).lower()
        error_name = type(error).__name__.lower()
    if "deadline exhausted before next attempt" in error_text:
        return None
    if "timeout" in error_name or "timeout" in error_text:
        return "timeout"
    if isinstance(error, OSError) or any(token in error_name for token in ("urlerror", "network", "connection")):
        return "network_error"
    return None


def _acquire_lock_with_deadline(lock: threading.Lock, deadline: float | None = None) -> bool:
    if deadline is None:
        lock.acquire()
        return True
    remaining = deadline - time.monotonic()
    if remaining > 0:
        return lock.acquire(timeout=remaining)
    return lock.acquire(blocking=False)


def provider_cooldown_active(provider_key: str, *, deadline: float | None = None) -> bool:
    key = str(provider_key or "").strip()
    if not key:
        return False
    now = time.monotonic()
    if not _acquire_lock_with_deadline(provider_cooldown_lock, deadline):
        return False
    try:
        expires_at = provider_cooldowns.get(key)
        if expires_at is None:
            return False
        if expires_at <= now:
            provider_cooldowns.pop(key, None)
            return False
        return True
    finally:
        provider_cooldown_lock.release()


def check_provider_cooldown(provider_key: str, *, deadline: float | None = None) -> None:
    if provider_cooldown_active(provider_key, deadline=deadline):
        raise ProviderCooldownError(f"provider cooldown active: {provider_key}")


def record_provider_failure(
    provider_key: str,
    error: BaseException | str,
    *,
    deadline: float | None = None,
) -> bool:
    """Record only timeout/network failures in a bounded monotonic map."""
    kind = _provider_failure_kind(error)
    key = str(provider_key or "").strip()
    if not kind or not key:
        return False
    now = time.monotonic()
    if not _acquire_lock_with_deadline(provider_cooldown_lock, deadline):
        return False
    try:
        for expired_key, expires_at in list(provider_cooldowns.items()):
            if expires_at <= now:
                provider_cooldowns.pop(expired_key, None)
        if key not in provider_cooldowns and len(provider_cooldowns) >= PROVIDER_COOLDOWN_MAX_ENTRIES:
            oldest_key = min(provider_cooldowns, key=provider_cooldowns.get)
            provider_cooldowns.pop(oldest_key, None)
        provider_cooldowns[key] = now + PROVIDER_FAILURE_COOLDOWN_SECONDS
    finally:
        provider_cooldown_lock.release()
    return True


def clear_provider_cooldown(provider_key: str, *, deadline: float | None = None) -> None:
    if not _acquire_lock_with_deadline(provider_cooldown_lock, deadline):
        return
    try:
        provider_cooldowns.pop(str(provider_key or "").strip(), None)
    finally:
        provider_cooldown_lock.release()


def wait_for_cache_flight(
    handle: CacheFlightHandle,
    *,
    deadline: float | None = None,
    max_wait: float | None = None,
) -> bool:
    """Wait only within the caller deadline and a short default ceiling."""
    wait_limit = CACHE_FLIGHT_FOLLOWER_MAX_WAIT_SECONDS if max_wait is None else max(0.0, float(max_wait))
    if deadline is not None:
        wait_limit = min(wait_limit, max(0.0, deadline - time.monotonic()))
    return handle.wait(wait_limit)


def run_cache_single_flight(
    key: str,
    operation,
    *,
    deadline: float | None = None,
    provider_key: str | None = None,
    deadline_cleanup: bool = False,
    cleanup_deadline: float | None = None,
) -> Any:
    """Run one process-local operation and return its result to bounded followers."""
    if not deadline_cleanup:
        cleanup_deadline = None
    elif cleanup_deadline is None:
        cleanup_deadline = deadline
    if provider_key:
        check_provider_cooldown(provider_key, deadline=cleanup_deadline)
    instrument_provider = provider_key == "host:openapi.taifex.com.tw"
    if instrument_provider:
        _institution_provider_observe(
            "institution.provider.single_flight.claim.begin",
            provider="taifex",
            provider_host="openapi.taifex.com.tw",
            provider_key=provider_key,
        )
    is_leader, handle = claim_cache_flight(key, deadline=deadline)
    if instrument_provider:
        _institution_provider_observe(
            "institution.provider.single_flight.role",
            provider="taifex",
            provider_host="openapi.taifex.com.tw",
            provider_key=provider_key,
            role="leader" if is_leader else "follower",
        )
    if not is_leader:
        if instrument_provider:
            _institution_provider_observe(
                "institution.provider.single_flight.wait.begin",
                provider="taifex",
                provider_host="openapi.taifex.com.tw",
            )
        wait_completed = wait_for_cache_flight(
            handle,
            deadline=deadline,
            max_wait=None if deadline is None else max(0.0, deadline - time.monotonic()),
        )
        if not wait_completed:
            if instrument_provider:
                _institution_provider_observe(
                    "institution.provider.single_flight.wait.timeout",
                    provider="taifex",
                    provider_host="openapi.taifex.com.tw",
                )
            raise ProviderFlightUnavailable(f"single-flight deadline expired: {key}")
        if instrument_provider:
            _institution_provider_observe(
                "institution.provider.single_flight.wait.end",
                provider="taifex",
                provider_host="openapi.taifex.com.tw",
            )
        if handle.error is not None:
            raise handle.error
        if not handle.result_ready:
            raise ProviderFlightUnavailable(f"single-flight result unavailable: {key}")
        return handle.result
    try:
        if instrument_provider:
            _institution_provider_observe(
                "institution.provider.operation.begin",
                provider="taifex",
                provider_host="openapi.taifex.com.tw",
            )
        result = operation()
        if instrument_provider:
            _institution_provider_observe(
                "institution.provider.operation.end",
                provider="taifex",
                provider_host="openapi.taifex.com.tw",
            )
        handle.result = result
        handle.result_ready = True
        if provider_key:
            clear_provider_cooldown(provider_key, deadline=cleanup_deadline)
        return result
    except BaseException as exc:
        if instrument_provider:
            _institution_provider_observe(
                "institution.provider.operation.error",
                provider="taifex",
                provider_host="openapi.taifex.com.tw",
                exception_class=type(exc).__name__,
            )
        handle.error = exc
        if provider_key:
            record_provider_failure(provider_key, exc, deadline=cleanup_deadline)
        raise
    finally:
        finish_cache_flight(key, handle, deadline=cleanup_deadline)


def _shared_single_flight_mode() -> str:
    mode = str(os.environ.get("MARKET_PULSE_SINGLE_FLIGHT_MODE", SINGLE_FLIGHT_MODE)).strip().lower()
    return mode if mode in {"local", "redis"} else "local"


def _build_single_flight_shared_adapter() -> SharedStateAdapter:
    redis_url = str(os.environ.get("MARKET_PULSE_REDIS_URL") or "").strip()
    if not redis_url:
        raise SharedStateUnavailable("MARKET_PULSE_REDIS_URL is required for shared single-flight")
    try:
        import redis
    except ImportError as exc:
        raise SharedStateUnavailable("redis package is required for shared single-flight") from exc
    timeout_seconds = max(0.1, float(os.environ.get("MARKET_PULSE_SHARED_STATE_TIMEOUT_SECONDS", "1")))
    try:
        client = redis.Redis.from_url(
            redis_url,
            protocol=2,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            decode_responses=True,
        )
        client.ping()
    except TimeoutError as exc:
        raise SharedStateTimeout("Redis single-flight health check timed out") from exc
    except Exception as exc:
        raise SharedStateUnavailable("Redis single-flight health check failed") from exc
    return RedisSharedStateAdapter(
        client,
        namespace=str(os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", "market-pulse:v1")),
    )


def _get_single_flight_shared_adapter() -> SharedStateAdapter:
    global single_flight_shared_adapter
    if single_flight_shared_adapter is not None:
        return single_flight_shared_adapter
    with single_flight_shared_adapter_lock:
        if single_flight_shared_adapter is None:
            single_flight_shared_adapter = _build_single_flight_shared_adapter()
        return single_flight_shared_adapter


def _claim_flight(
    key: str,
    local_flights: dict[str, CacheFlightHandle],
    local_lock: threading.Lock,
    lease_prefix: str,
    deadline: float | None = None,
) -> tuple[bool, CacheFlightHandle]:
    """Claim a local flight and, when enabled, a cross-worker lease."""
    if deadline is None:
        acquired = local_lock.acquire()
    else:
        remaining = deadline - time.monotonic()
        acquired = remaining > 0 and local_lock.acquire(timeout=remaining)
    if not acquired:
        return False, CacheFlightHandle(threading.Event())
    try:
        existing_handle = local_flights.get(key)
        if existing_handle is not None and existing_handle.event.is_set():
            local_flights.pop(key, None)
            existing_handle = None
        if existing_handle is not None:
            return False, existing_handle
        handle = CacheFlightHandle(threading.Event())
        local_flights[key] = handle
    finally:
        local_lock.release()

    if _shared_single_flight_mode() != "redis":
        return True, handle

    lease_name = f"{lease_prefix}:{key}"
    owner_token = f"{os.getpid()}:{threading.get_ident()}:{time.time_ns()}"
    try:
        adapter = _get_single_flight_shared_adapter()
        if adapter.acquire_lease(lease_name, owner_token, SINGLE_FLIGHT_LEASE_TTL_SECONDS):
            handle.shared_adapter = adapter
            handle.lease_name = lease_name
            handle.owner_token = owner_token
            return True, handle
        with local_lock:
            local_flights.pop(key, None)
        return False, CacheFlightHandle(threading.Event(), adapter, lease_name)
    except SharedStateError as exc:
        LOGGER.warning("Shared cache-flight claim degraded to local path error_type=%s", type(exc).__name__)
        return True, handle


def _finish_flight(
    key: str,
    handle: CacheFlightHandle,
    local_flights: dict[str, CacheFlightHandle],
    local_lock: threading.Lock,
    deadline: float | None = None,
) -> None:
    if not _acquire_lock_with_deadline(local_lock, deadline):
        # Wake bounded followers without waiting for a fresh cleanup budget.
        # A later claimant removes this completed handle while holding the
        # same lock, preserving single-flight correctness.
        handle.event.set()
        return
    try:
        if local_flights.get(key) is handle:
            local_flights.pop(key, None)
            handle.event.set()
    finally:
        local_lock.release()
    if handle.uses_shared_lease and handle.owner_token:
        try:
            handle.shared_adapter.release_lease(handle.lease_name, handle.owner_token)
        except SharedStateError as exc:
            LOGGER.warning("Shared cache-flight release failed error_type=%s", type(exc).__name__)


def claim_cache_flight(key: str, *, deadline: float | None = None) -> tuple[bool, CacheFlightHandle]:
    """Elect one request to refresh a cache key while concurrent requests wait."""
    return _claim_flight(key, cache_flights, cache_flight_lock, "cache-flight", deadline)


def finish_cache_flight(key: str, handle: CacheFlightHandle, *, deadline: float | None = None) -> None:
    _finish_flight(key, handle, cache_flights, cache_flight_lock, deadline)


def claim_taifex_options_chain_flight(key: str, *, deadline: float | None = None) -> tuple[bool, CacheFlightHandle]:
    return _claim_flight(key, taifex_options_chain_inflight, taifex_options_chain_inflight_lock, "options-flight", deadline)


def finish_taifex_options_chain_flight(key: str, handle: CacheFlightHandle) -> None:
    _finish_flight(key, handle, taifex_options_chain_inflight, taifex_options_chain_inflight_lock)


def serialize_treasury_yield_curve_cache(cached: dict[str, Any] | None = None) -> dict[str, Any]:
    cached = cached if cached is not None else (cache_data.get("treasury_yield_curve_rows") or {})
    serialized_rows = []
    for date_value, row in cached.get("rows") or []:
        if isinstance(date_value, datetime):
            date_text = date_value.strftime("%Y-%m-%d")
        else:
            date_text = str(date_value or "")
        if date_text and isinstance(row, dict):
            serialized_rows.append({"date": date_text, "row": row})
    return {
        "stored_at": float(cached.get("stored_at") or 0),
        "rows": serialized_rows,
    }


def deserialize_treasury_yield_curve_cache(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    rows: list[tuple[datetime, dict[str, str]]] = []
    for item in payload.get("rows") or []:
        if not isinstance(item, dict) or not isinstance(item.get("row"), dict):
            continue
        date_text = str(item.get("date") or item["row"].get("Date") or "").strip()
        parsed_date = None
        for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                parsed_date = datetime.strptime(date_text, date_format)
                break
            except ValueError:
                continue
        if parsed_date is not None:
            rows.append((parsed_date, item["row"]))
    if not rows:
        return None
    return {
        "stored_at": float(payload.get("stored_at") or 0),
        "rows": sorted(rows, key=lambda item: item[0]),
    }


def sanitize_site_data(site_data: dict[str, Any] | None) -> dict[str, Any] | None:
    if not site_data:
        return site_data

    sectors = site_data.get("sectors")
    if isinstance(sectors, list):
        site_data = dict(site_data)
        site_data["sectors"] = [
            item
            for item in sectors
            if item.get("sourceName") not in EXCLUDED_SECTOR_SOURCE_NAMES and item.get("name") not in EXCLUDED_SECTOR_SOURCE_NAMES
        ]
    yahoo_groups = site_data.get("yahooSectorGroups")
    if isinstance(yahoo_groups, dict):
        site_data = dict(site_data)
        sanitized_groups: dict[str, list[dict[str, Any]]] = {}
        for group_key, cards in yahoo_groups.items():
            sanitized_cards = []
            for card in cards if isinstance(cards, list) else []:
                sanitized_card = dict(card)
                sanitized_card.pop("trades", None)
                series = dict(sanitized_card.get("comparisonSeries") or {})
                series["day"] = [
                    {key: value for key, value in point.items() if key != "trades"}
                    for point in series.get("day", [])
                ]
                sanitized_card["comparisonSeries"] = series
                sanitized_cards.append(sanitized_card)
            sanitized_groups[group_key] = sanitized_cards
        site_data["yahooSectorGroups"] = sanitized_groups
    return site_data


def load_disk_cache() -> bool:
    try:
        cache_source = CACHE_FILE if CACHE_FILE.exists() else BUNDLED_CACHE_FILE
        if not cache_source.exists():
            return False
        payload = json.loads(cache_source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Disk cache load skipped for %s: %s", cache_source if "cache_source" in locals() else CACHE_FILE, exc)
        return False

    if not isinstance(payload, dict):
        LOGGER.warning("Disk cache load skipped for %s: expected a JSON object", cache_source)
        return False

    cache_version = payload.get("cache_version")
    if cache_version is not None and cache_version != CACHE_VERSION:
        return False
    with cache_lock:
        cache_data["site_data"] = sanitize_site_data(payload.get("site_data"))
        cache_data["all_stocks"] = payload.get("all_stocks", [])
        cache_data["market_date"] = payload.get("market_date")
        cache_data["cached_at"] = payload.get("cached_at")
        persisted_options = payload.get("taifex_options_chain")
        if isinstance(persisted_options, dict):
            cache_data["taifex_options_chain"] = persisted_options
        treasury_rows = deserialize_treasury_yield_curve_cache(payload.get("treasury_yield_curve_rows"))
        if treasury_rows:
            cache_data["treasury_yield_curve_rows"] = treasury_rows
    return True


def build_disk_cache_snapshot(*, deadline: float | None = None) -> dict[str, Any]:
    """Capture one internally consistent cache generation before writing it to disk."""
    if not _acquire_cache_lock(deadline):
        raise TimeoutError("disk cache snapshot deadline exhausted")
    try:
        treasury_rows = copy.deepcopy(cache_data.get("treasury_yield_curve_rows") or {})
        return {
            "cache_version": CACHE_VERSION,
            "site_data": copy.deepcopy(cache_data["site_data"]),
            "all_stocks": copy.deepcopy(cache_data["all_stocks"]),
            "market_date": cache_data["market_date"],
            "cached_at": cache_data["cached_at"],
            "taifex_options_chain": copy.deepcopy(cache_data.get("taifex_options_chain") or {}),
            "treasury_yield_curve_rows": serialize_treasury_yield_curve_cache(treasury_rows),
        }
    finally:
        cache_lock.release()


def save_disk_cache(snapshot: dict[str, Any] | None = None, *, deadline: float | None = None) -> None:
    # Serialize outside the shared cache lock. The snapshot is already a single generation.
    # Synchronous filesystem writes have no portable cancellation primitive. A
    # request-scoped caller therefore skips this optional persistence stage;
    # background refreshes retain the existing deadline-free behavior.
    if deadline is not None:
        return
    try:
        payload = snapshot if snapshot is not None else build_disk_cache_snapshot()
    except TimeoutError:
        LOGGER.info("Disk cache save skipped after request deadline expired")
        return
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = CACHE_FILE.with_suffix(f"{CACHE_FILE.suffix}.tmp")
    try:
        temporary_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary_file.replace(CACHE_FILE)
    except OSError as exc:
        LOGGER.exception("Disk cache save failed for %s", CACHE_FILE, exc_info=exc)
        try:
            temporary_file.unlink(missing_ok=True)
        except OSError:
            pass


def _refresh_cache_impl() -> None:
    import app  # deferred: avoids a module-load-time app.py <-> cache.py import cycle

    with cache_lock:
        existing_site_data = copy.deepcopy(cache_data["site_data"])
        existing_market_date = cache_data["market_date"]

    site_data, all_stocks, market_date_iso = app.build_site_data(
        existing_site_data=existing_site_data,
        existing_market_date=existing_market_date,
    )

    with cache_lock:
        cache_data["site_data"] = site_data
        cache_data["all_stocks"] = all_stocks
        cache_data["market_date"] = market_date_iso
        cache_data["cached_at"] = site_data["cachedAt"]
        cache_data["last_error"] = None
        cache_data["stock_details"] = {}
    save_disk_cache()


def refresh_cache(*, deadline: float | None = None) -> bool:
    """Refresh site data without holding a broad coordination lock over I/O."""
    result = run_cache_single_flight(
        "site-data-refresh",
        _refresh_cache_impl,
        deadline=deadline,
    )
    return result is not False


def _background_updater_mode() -> str:
    mode = str(os.environ.get("MARKET_PULSE_BACKGROUND_LEASE_MODE", BACKGROUND_UPDATER_MODE)).strip().lower()
    return mode if mode in {"local", "redis"} else "local"


def _build_background_updater_shared_adapter() -> SharedStateAdapter:
    redis_url = str(os.environ.get("MARKET_PULSE_REDIS_URL") or "").strip()
    if not redis_url:
        raise SharedStateUnavailable("MARKET_PULSE_REDIS_URL is required for background updater lease")
    try:
        import redis
    except ImportError as exc:
        raise SharedStateUnavailable("redis package is required for background updater lease") from exc
    timeout_seconds = max(0.1, float(os.environ.get("MARKET_PULSE_SHARED_STATE_TIMEOUT_SECONDS", "1")))
    try:
        client = redis.Redis.from_url(
            redis_url,
            protocol=2,
            socket_connect_timeout=timeout_seconds,
            socket_timeout=timeout_seconds,
            decode_responses=True,
        )
        client.ping()
    except TimeoutError as exc:
        raise SharedStateTimeout("Redis background updater health check timed out") from exc
    except Exception as exc:
        raise SharedStateUnavailable("Redis background updater health check failed") from exc
    return RedisSharedStateAdapter(
        client,
        namespace=str(os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", "market-pulse:v1")),
    )


def _get_background_updater_shared_adapter() -> SharedStateAdapter:
    global background_updater_shared_adapter
    if background_updater_shared_adapter is not None:
        return background_updater_shared_adapter
    with background_updater_shared_adapter_lock:
        if background_updater_shared_adapter is None:
            background_updater_shared_adapter = _build_background_updater_shared_adapter()
        return background_updater_shared_adapter


def _background_updater_owner_token() -> str:
    return f"{os.getpid()}:{threading.get_ident()}:{time.time_ns()}"


def _renew_background_updater_lease(
    adapter: SharedStateAdapter,
    stop_event: threading.Event,
    lease_lost_event: threading.Event,
    owner_token: str,
) -> None:
    while not stop_event.wait(BACKGROUND_UPDATER_RENEW_INTERVAL_SECONDS):
        try:
            renewed = adapter.renew_lease(
                BACKGROUND_UPDATER_LEASE_NAME,
                owner_token,
                BACKGROUND_UPDATER_LEASE_TTL_SECONDS,
            )
        except SharedStateError as exc:
            lease_lost_event.set()
            LOGGER.warning("Background updater lease renewal failed error_type=%s", type(exc).__name__)
            return
        if not renewed:
            lease_lost_event.set()
            LOGGER.warning("Background updater lease ownership lost")
            return


def _run_background_refresh_tasks() -> None:
    import app  # deferred: refresh_tpex_cache hasn't moved out of app.py yet (TD-01 slice 2c)

    attempt_at = time.time()
    with cache_lock:
        cache_data["provider_status"]["tpex"]["lastAttemptAt"] = attempt_at
    try:
        app.refresh_tpex_cache()
    except Exception as exc:  # noqa: BLE001
        error_kind = type(exc).__name__.lower()
        provider_status = "timeout" if "timeout" in error_kind else "network_error"
        LOGGER.warning("Background provider refresh failed provider=tpex operation=cache_refresh category=%s", provider_status)
        with cache_lock:
            cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE
            cache_data["provider_status"]["tpex"].update({"status": provider_status, "lastError": provider_status})
    else:
        with cache_lock:
            cache_data["provider_status"]["tpex"].update({"status": "available", "lastSuccessAt": time.time(), "lastError": None})

    with cache_lock:
        cache_data["provider_status"]["twse"]["lastAttemptAt"] = time.time()
    try:
        refresh_cache()
    except Exception as exc:  # noqa: BLE001
        error_kind = type(exc).__name__.lower()
        provider_status = "timeout" if "timeout" in error_kind else "network_error"
        LOGGER.warning("Background provider refresh failed provider=twse operation=cache_refresh category=%s", provider_status)
        with cache_lock:
            cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE
            cache_data["provider_status"]["twse"].update({"status": provider_status, "lastError": provider_status})
    else:
        with cache_lock:
            cache_data["provider_status"]["twse"].update({"status": "available", "lastSuccessAt": time.time(), "lastError": None})


def run_background_update_cycle() -> bool:
    """Run one refresh cycle; return whether this process owned the cycle."""
    if _background_updater_mode() != "redis":
        _run_background_refresh_tasks()
        return True

    try:
        adapter = _get_background_updater_shared_adapter()
        owner_token = _background_updater_owner_token()
        acquired = adapter.acquire_lease(
            BACKGROUND_UPDATER_LEASE_NAME,
            owner_token,
            BACKGROUND_UPDATER_LEASE_TTL_SECONDS,
        )
    except SharedStateError as exc:
        LOGGER.warning("Background updater lease unavailable; skipping refresh error_type=%s", type(exc).__name__)
        return False
    if not acquired:
        LOGGER.debug("Background updater lease held by another worker; skipping refresh")
        return False

    stop_event = threading.Event()
    lease_lost_event = threading.Event()
    renew_thread = threading.Thread(
        target=_renew_background_updater_lease,
        args=(adapter, stop_event, lease_lost_event, owner_token),
        daemon=True,
    )
    renew_thread.start()
    try:
        _run_background_refresh_tasks()
    finally:
        stop_event.set()
        renew_thread.join(timeout=max(1.0, BACKGROUND_UPDATER_RENEW_INTERVAL_SECONDS))
        if lease_lost_event.is_set():
            LOGGER.warning("Background updater refresh completed after lease loss")
        try:
            adapter.release_lease(BACKGROUND_UPDATER_LEASE_NAME, owner_token)
        except SharedStateError as exc:
            LOGGER.warning("Background updater lease release failed error_type=%s", type(exc).__name__)
    return True


def update_loop() -> None:
    while True:
        run_background_update_cycle()
        time.sleep(UPDATE_INTERVAL_SECONDS)


def ensure_cache() -> None:
    with cache_lock:
        has_site_data = cache_data["site_data"] is not None
    if not has_site_data:
        load_disk_cache()
    with cache_lock:
        has_site_data = cache_data["site_data"] is not None
    if not has_site_data:
        def cold_refresh() -> bool:
            with cache_lock:
                already_loaded = cache_data["site_data"] is not None
            if already_loaded:
                return True
            load_disk_cache()
            with cache_lock:
                already_loaded = cache_data["site_data"] is not None
            if already_loaded:
                return True
            LOGGER.info("Cold cache refresh started")
            refresh_cache()
            LOGGER.info("Cold cache refresh finished")
            return True

        run_cache_single_flight("site-data-cold-refresh", cold_refresh)
        with cache_lock:
            has_site_data = cache_data["site_data"] is not None
        if not has_site_data:
            raise RuntimeError("冷快取同步未完成，請稍後再試")


def start_background_updater() -> None:
    global background_updater_started
    with background_updater_lock:
        if background_updater_started:
            return
        background_updater_started = True
    try:
        load_disk_cache()
    except Exception:  # noqa: BLE001
        LOGGER.exception("Initial disk cache load failed")
        with cache_lock:
            cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE
    thread = threading.Thread(target=update_loop, daemon=True)
    thread.start()


def background_updater_enabled() -> bool:
    return str(os.environ.get("MARKET_PULSE_DISABLE_BACKGROUND") or "").strip() != "1"
