"""Shared-state contracts and backends for TD-03.

H-05-02 defines the boundary only.  Nothing in the production request path
 imports this module yet.  The in-memory backend is deterministic and is used
 by the contract tests; the Redis backend accepts an already-configured
 redis-py-compatible client so the application does not gain a mandatory
 dependency until a later, separately approved migration batch.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Protocol


class SharedStateError(RuntimeError):
    """Base error for an unavailable or invalid shared-state operation."""


class SharedStateTimeout(SharedStateError):
    """The shared-state operation exceeded its configured timeout."""


class SharedStateUnavailable(SharedStateError):
    """The shared-state backend is disconnected or otherwise unavailable."""


class SharedStateClient(Protocol):
    """Minimal redis-py-compatible client surface used by the adapter."""

    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> Any: ...

    def get(self, key: str) -> Any: ...

    def exists(self, key: str) -> Any: ...

    def set(self, key: str, value: str, **kwargs: Any) -> Any: ...


class SharedStateAdapter(Protocol):
    """Contract for cross-worker rate-limit, cache and lease state."""

    def rate_limit_hit(
        self,
        client_key: str,
        now: float,
        window_seconds: float,
        limit: int,
        max_clients: int,
    ) -> int | None: ...

    def cache_get(self, namespace: str, key: str) -> Any | None: ...

    def cache_set(self, namespace: str, key: str, payload: Any, ttl_seconds: float) -> None: ...

    def acquire_lease(self, name: str, owner_token: str, ttl_seconds: float) -> bool: ...

    def renew_lease(self, name: str, owner_token: str, ttl_seconds: float) -> bool: ...

    def release_lease(self, name: str, owner_token: str) -> bool: ...

    def lease_is_active(self, name: str) -> bool: ...


def _json_copy(payload: Any) -> Any:
    """Validate JSON-shaped cache data and mimic Redis serialization locally."""
    return json.loads(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _error_from_backend(exc: Exception) -> SharedStateError:
    error_name = type(exc).__name__.lower()
    message = str(exc) or error_name
    if isinstance(exc, TimeoutError) or "timeout" in error_name:
        return SharedStateTimeout(message)
    if isinstance(exc, ConnectionError) or any(token in error_name for token in ("connection", "disconnect", "redis")):
        return SharedStateUnavailable(message)
    return SharedStateError(message)


@dataclass
class _Lease:
    owner_token: str
    expires_at: float


class InMemorySharedStateAdapter:
    """Process-local reference backend used as the mandatory contract fixture."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.time
        self._lock = threading.RLock()
        self._rate_limit_state: dict[str, list[float]] = {}
        self._rate_limit_last_seen: dict[str, float] = {}
        self._cache: dict[tuple[str, str], tuple[float, Any]] = {}
        self._leases: dict[str, _Lease] = {}

    def _now(self) -> float:
        return float(self._clock())

    def _purge_rate_limit(self, now: float, window_seconds: float) -> None:
        for client_key, timestamps in list(self._rate_limit_state.items()):
            recent = [timestamp for timestamp in timestamps if now - timestamp < window_seconds]
            if recent:
                self._rate_limit_state[client_key] = recent
            else:
                self._rate_limit_state.pop(client_key, None)
                self._rate_limit_last_seen.pop(client_key, None)

    def rate_limit_hit(
        self,
        client_key: str,
        now: float,
        window_seconds: float,
        limit: int,
        max_clients: int,
    ) -> int | None:
        if window_seconds <= 0 or limit <= 0:
            return None
        with self._lock:
            self._purge_rate_limit(now, window_seconds)
            recent = self._rate_limit_state.setdefault(client_key, [])
            if len(recent) >= limit:
                return max(1, int(window_seconds - (now - recent[0])))
            recent.append(now)
            self._rate_limit_last_seen[client_key] = now
            while len(self._rate_limit_state) > max_clients:
                oldest = min(self._rate_limit_last_seen, key=self._rate_limit_last_seen.get)
                self._rate_limit_state.pop(oldest, None)
                self._rate_limit_last_seen.pop(oldest, None)
            return None

    def cache_get(self, namespace: str, key: str) -> Any | None:
        now = self._now()
        with self._lock:
            entry = self._cache.get((namespace, key))
            if entry is None:
                return None
            expires_at, payload = entry
            if expires_at <= now:
                self._cache.pop((namespace, key), None)
                return None
            return copy.deepcopy(payload)

    def cache_set(self, namespace: str, key: str, payload: Any, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        stored_payload = _json_copy(payload)
        with self._lock:
            self._cache[(namespace, key)] = (self._now() + ttl_seconds, stored_payload)

    def _purge_expired_lease(self, name: str) -> _Lease | None:
        lease = self._leases.get(name)
        if lease is not None and lease.expires_at <= self._now():
            self._leases.pop(name, None)
            return None
        return lease

    def acquire_lease(self, name: str, owner_token: str, ttl_seconds: float) -> bool:
        if ttl_seconds <= 0 or not owner_token:
            raise ValueError("lease owner_token and positive ttl_seconds are required")
        with self._lock:
            if self._purge_expired_lease(name) is not None:
                return False
            self._leases[name] = _Lease(owner_token, self._now() + ttl_seconds)
            return True

    def renew_lease(self, name: str, owner_token: str, ttl_seconds: float) -> bool:
        if ttl_seconds <= 0 or not owner_token:
            raise ValueError("lease owner_token and positive ttl_seconds are required")
        with self._lock:
            lease = self._purge_expired_lease(name)
            if lease is None or lease.owner_token != owner_token:
                return False
            lease.expires_at = self._now() + ttl_seconds
            return True

    def release_lease(self, name: str, owner_token: str) -> bool:
        with self._lock:
            lease = self._purge_expired_lease(name)
            if lease is None or lease.owner_token != owner_token:
                return False
            self._leases.pop(name, None)
            return True

    def lease_is_active(self, name: str) -> bool:
        with self._lock:
            return self._purge_expired_lease(name) is not None


_RATE_LIMIT_LUA = """
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local max_clients = tonumber(ARGV[4])
local member = ARGV[5]
local client_key = KEYS[1]
local clients_key = KEYS[2]
redis.call('ZREMRANGEBYSCORE', client_key, '-inf', now - window)
redis.call('ZREMRANGEBYSCORE', clients_key, '-inf', now - window)
local recent_count = redis.call('ZCARD', client_key)
if recent_count >= limit then
  local first = redis.call('ZRANGE', client_key, 0, 0, 'WITHSCORES')
  local retry_after = math.max(1, math.floor(window - (now - tonumber(first[2]))))
  return retry_after
end
if redis.call('EXISTS', client_key) == 0 then
  while redis.call('ZCARD', clients_key) >= max_clients do
    local oldest = redis.call('ZRANGE', clients_key, 0, 0)
    if #oldest == 0 then break end
    redis.call('ZREM', clients_key, oldest[1])
    redis.call('DEL', oldest[1])
  end
  redis.call('ZADD', clients_key, now, client_key)
end
redis.call('ZADD', clients_key, now, client_key)
redis.call('ZADD', client_key, now, member)
redis.call('EXPIRE', client_key, math.ceil(window))
redis.call('EXPIRE', clients_key, math.ceil(window))
return 0
"""

_LEASE_RENEW_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('EXPIRE', KEYS[1], math.ceil(tonumber(ARGV[2])))
end
return 0
"""

_LEASE_RELEASE_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


class RedisSharedStateAdapter:
    """Redis implementation using an injected redis-py-compatible client."""

    def __init__(self, client: SharedStateClient, namespace: str = "market-pulse:v1") -> None:
        self._client = client
        self._namespace = namespace.strip(":") or "market-pulse:v1"

    def _key(self, kind: str, *parts: str) -> str:
        return ":".join((self._namespace, kind, *(str(part).strip(":") for part in parts)))

    def _digest_key(self, kind: str, *parts: str) -> str:
        material = "\x1f".join(str(part) for part in parts).encode("utf-8")
        return self._key(kind, hashlib.sha256(material).hexdigest())

    def _call(self, operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except SharedStateError:
            raise
        except Exception as exc:
            raise _error_from_backend(exc) from exc

    def rate_limit_hit(
        self,
        client_key: str,
        now: float,
        window_seconds: float,
        limit: int,
        max_clients: int,
    ) -> int | None:
        if window_seconds <= 0 or limit <= 0:
            return None
        client_digest = hashlib.sha256(str(client_key).encode("utf-8")).hexdigest()
        client_zset = self._key("rate-limit", client_digest)
        clients_zset = self._key("rate-limit-clients")
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        result = self._call(
            lambda: self._client.eval(
                _RATE_LIMIT_LUA,
                2,
                client_zset,
                clients_zset,
                str(float(now)),
                str(float(window_seconds)),
                str(int(limit)),
                str(int(max_clients)),
                member,
            )
        )
        retry_after = int(result or 0)
        return retry_after or None

    def cache_get(self, namespace: str, key: str) -> Any | None:
        redis_key = self._digest_key("cache", namespace, key)
        raw = self._call(lambda: self._client.get(redis_key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            envelope = json.loads(str(raw))
            if not isinstance(envelope, dict) or float(envelope["expires_at"]) <= time.time():
                return None
            return envelope["payload"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SharedStateError("invalid shared cache envelope") from exc

    def cache_set(self, namespace: str, key: str, payload: Any, ttl_seconds: float) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        redis_key = self._digest_key("cache", namespace, key)
        envelope = json.dumps(
            {"expires_at": time.time() + ttl_seconds, "payload": _json_copy(payload)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._call(lambda: self._client.set(redis_key, envelope, ex=max(1, int(ttl_seconds))))

    def acquire_lease(self, name: str, owner_token: str, ttl_seconds: float) -> bool:
        if ttl_seconds <= 0 or not owner_token:
            raise ValueError("lease owner_token and positive ttl_seconds are required")
        redis_key = self._digest_key("lease", name)
        result = self._call(
            lambda: self._client.set(redis_key, owner_token, nx=True, ex=max(1, int(ttl_seconds)))
        )
        return bool(result)

    def renew_lease(self, name: str, owner_token: str, ttl_seconds: float) -> bool:
        if ttl_seconds <= 0 or not owner_token:
            raise ValueError("lease owner_token and positive ttl_seconds are required")
        redis_key = self._digest_key("lease", name)
        result = self._call(
            lambda: self._client.eval(
                _LEASE_RENEW_LUA,
                1,
                redis_key,
                owner_token,
                str(float(ttl_seconds)),
            )
        )
        return bool(result)

    def release_lease(self, name: str, owner_token: str) -> bool:
        if not owner_token:
            return False
        redis_key = self._digest_key("lease", name)
        result = self._call(
            lambda: self._client.eval(_LEASE_RELEASE_LUA, 1, redis_key, owner_token)
        )
        return bool(result)

    def lease_is_active(self, name: str) -> bool:
        redis_key = self._digest_key("lease", name)
        return bool(self._call(lambda: self._client.exists(redis_key)))
