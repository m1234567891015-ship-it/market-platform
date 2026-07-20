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


def fetch_from_registry(name: str, *url_args: Any, cache_key_args: tuple = (), force: bool = False, **params: Any) -> Any:
    """Resolve and execute the SourceSpec registered under *name*."""
    spec = REGISTRY[name]
    url = spec.url(*url_args, **params) if callable(spec.url) else spec.url
    headers = spec.headers or {"User-Agent": DEFAULT_USER_AGENT}

    cache_key = None
    if spec.cache_bucket and not force:
        cache_key = spec.cache_key(*cache_key_args) if spec.cache_key else url
        cached = read_memory_cache(spec.cache_bucket, cache_key, spec.ttl_seconds or 0)
        if cached is not None:
            return cached

    req = Request(url, headers=headers, method="POST" if spec.method == "POST" else "GET")
    with _urlopen_with_ssl_fallback(req, spec.timeout) as response:
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
        write_memory_cache(spec.cache_bucket, cache_key, result)
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
    return problems
