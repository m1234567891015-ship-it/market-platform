"""TD-05: declarative source registry + unified HTTP client for fetchers.py.

Scope boundary (decided and confirmed before batch 1, kept here as the
authoritative reference for every later batch): this registry only expresses
the flat shape "URL (+ params) -> HTTP call -> optional parse -> optional
TTL cache" as data. It deliberately does NOT express control flow. Anything
with real control flow stays a hand-written Python function that may call
`fetch_from_registry(...)` one or more times internally, but the control
flow itself (which source to try first, whether to retry, how to fall back)
is never encoded as SourceSpec fields. Concretely, out of scope for a
SourceSpec entry:

- Multi-source fallback/dispatch (e.g. "try TAIFEX, fall back to Yahoo on
  error") - this is an if/try-except in a regular function, not registry
  data. A registry entry has exactly one URL (or one URL-building callable)
  and exactly one parser; it is not a chain.
- Fan-out / concurrency orchestration (e.g. ThreadPoolExecutor spreading
  across several sources at once).
- Retry-with-backoff loops, leader/follower request coalescing, or any
  other stateful control flow beyond the registry's own TTL-cache check.
- Requests that need a persistent or per-call cookie jar / opener (a few
  Yahoo/Barchart sources authenticate via cookies obtained from a prior
  request) - these keep using their own `build_opener(HTTPCookieProcessor(...))`
  and never route through `fetch_from_registry`.

Rationale: forcing any of the above into SourceSpec fields would turn the
registry into a small interpreter for control flow expressed as data, which
is harder to read than the equivalent Python and defeats the point of a
declarative registry (the "leaky abstraction" this design explicitly avoids).
The registry's job is narrowly to delete the ~80-line boilerplate repeated
across the ~60-65 fetchers that really are just "one URL, one parser, one
TTL" - not to describe every fetcher in the file.

This module has no dependency on fetchers.py at import time (leaf module,
same layering rule as cache.py/security.py/market_config.py) - it is
imported BY fetchers.py, never the reverse.
"""
from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Callable, Literal
from urllib.request import Request

import market_config
from cache import read_memory_cache, write_memory_cache
from security import _urlopen_with_ssl_fallback

DEFAULT_USER_AGENT = "market-pulse-fetcher/1.0"


@dataclass(frozen=True)
class SourceSpec:
    """One declarative fetch source. See module docstring for what does NOT
    belong here (fallback/retry/fan-out/cookie-jar control flow)."""

    name: str
    url: str | Callable[..., str]
    method: Literal["GET", "POST", "FORM"] = "GET"
    response_type: Literal["json", "text", "binary"] = "json"
    headers: dict[str, str] | None = None
    decode: Literal["utf8", "sniff_cp950_big5"] = "utf8"
    decode_errors: Literal["strict", "ignore", "replace"] = "strict"
    timeout: int = 30
    cache_bucket: str | None = None
    cache_key: Callable[..., str] | None = None
    ttl_seconds: int | None = None
    parser: Callable[[Any], Any] | None = None
    params: dict[str, Any] | None = None


REGISTRY: dict[str, SourceSpec] = {}


def register(spec: SourceSpec) -> None:
    """Register *spec*. Raises if the name is already taken - this is the
    uniqueness enforcement (fail at registration time, not a later audit)."""
    if spec.name in REGISTRY:
        raise ValueError(f"fetch_registry: duplicate SourceSpec name {spec.name!r}")
    REGISTRY[spec.name] = spec


def fetch_from_registry(
    name: str,
    *url_args: Any,
    cache_key_args: tuple | None = None,
    force: bool = False,
    timeout: int | None = None,
    **params: Any,
) -> Any:
    """Resolve and execute the SourceSpec registered under *name*.

    *timeout*, if given, overrides the spec's own default for this one call
    (several existing fetch_* wrappers accept a caller-overridable timeout
    parameter; this preserves that without threading it through the URL
    builder's **params).

    *cache_key_args*, if omitted, defaults to *url_args* - the common case is
    that whatever identifies the URL also identifies the cache entry. Pass it
    explicitly only when the two genuinely differ. Defaulting this way (rather
    than to `()`) matters: a `spec.cache_key` callable that needs args but
    silently receives none raises a TypeError deep inside this function,
    which a caller wrapped in a broad `except Exception` (a common pattern in
    this codebase) will swallow into a misleadingly "successful" empty
    result - safer to default to the args that are already right there.
    """
    spec = REGISTRY[name]
    url = spec.url(*url_args, **params) if callable(spec.url) else spec.url
    headers = spec.headers or {"User-Agent": DEFAULT_USER_AGENT}
    resolved_cache_key_args = url_args if cache_key_args is None else cache_key_args

    cache_key = None
    if spec.cache_bucket and not force:
        cache_key = spec.cache_key(*resolved_cache_key_args) if spec.cache_key else url
        cached = read_memory_cache(spec.cache_bucket, cache_key, spec.ttl_seconds or 0)
        if cached is not None:
            return cached

    req = Request(url, headers=headers, method="POST" if spec.method == "POST" else "GET")
    with _urlopen_with_ssl_fallback(req, timeout if timeout is not None else spec.timeout) as response:
        raw = response.read()
        if spec.response_type == "binary":
            payload: Any = raw
        elif spec.response_type == "text":
            if spec.decode == "sniff_cp950_big5":
                content_type = str(response.headers.get("Content-Type") or "").lower()
                encoding = "cp950" if ("ms950" in content_type or "big5" in content_type) else "utf-8"
            else:
                encoding = "utf-8"
            payload = raw.decode(encoding, errors=spec.decode_errors)
        else:
            payload = json.loads(raw.decode("utf-8"))

    result = spec.parser(payload) if spec.parser else payload
    if spec.cache_bucket and cache_key is not None:
        write_memory_cache(spec.cache_bucket, cache_key, result, spec.ttl_seconds)
    return result


def _known_ttl_values() -> set[int]:
    """TTL values declared as named constants in market_config.py right now.

    Deliberately introspective rather than a hardcoded list: as later
    batches migrate more *_CACHE_SECONDS constants into market_config.py,
    this grows automatically without needing to be edited per batch.
    """
    values: set[int] = set()
    for attr_name in dir(market_config):
        if attr_name.startswith("_"):
            continue
        if "CACHE_SECONDS" in attr_name or attr_name.endswith("_TTL_SECONDS"):
            value = getattr(market_config, attr_name)
            if isinstance(value, int):
                values.add(value)
    return values


def validate_registry() -> list[str]:
    """Self-audit the registry. Returns a list of problem descriptions
    (empty list = clean). Checked invariants:

    - every SourceSpec.url is non-empty (static strings only; callables are
      trusted since their output can't be checked without invoking them)
    - every SourceSpec.parser, if set, is callable
    - every SourceSpec.ttl_seconds, if set, matches a named constant in
      market_config.py (catches the Finding B class of bug: a bare TTL
      literal that was never promoted to a named constant)
    - every SourceSpec.cache_key, if set, is callable and takes the same
      number of parameters as spec.url does (0 if url is a static string).
      fetch_from_registry() defaults cache_key_args to url_args, so a
      cache_key callable that doesn't accept the same shape of arguments
      as url would either crash at call time or (worse) only work by
      accident for calls that happen to pass a matching cache_key_args
      override explicitly - this check catches the mismatch at registration
      time instead of waiting for a specific call site to expose it.

    Name uniqueness is enforced at register() time, not here (see above).
    """
    problems: list[str] = []
    known_ttls = _known_ttl_values()
    for spec in REGISTRY.values():
        if isinstance(spec.url, str) and not spec.url.strip():
            problems.append(f"{spec.name}: url is empty")
        if spec.parser is not None and not callable(spec.parser):
            problems.append(f"{spec.name}: parser is not callable")
        if spec.ttl_seconds is not None and spec.ttl_seconds not in known_ttls:
            problems.append(
                f"{spec.name}: ttl_seconds={spec.ttl_seconds} does not match any "
                f"*_CACHE_SECONDS/*_TTL_SECONDS constant in market_config.py"
            )
        if spec.cache_key is not None:
            if not callable(spec.cache_key):
                problems.append(f"{spec.name}: cache_key is not callable")
            else:
                expected_params = len(inspect.signature(spec.url).parameters) if callable(spec.url) else 0
                try:
                    actual_params = len(inspect.signature(spec.cache_key).parameters)
                except (TypeError, ValueError):
                    actual_params = None
                if actual_params is not None and actual_params != expected_params:
                    problems.append(
                        f"{spec.name}: cache_key takes {actual_params} arg(s) but url takes "
                        f"{expected_params} - cache_key_args defaults to url_args in "
                        f"fetch_from_registry(), so these must match unless every call site "
                        f"passes an explicit cache_key_args override"
                    )
    return problems
