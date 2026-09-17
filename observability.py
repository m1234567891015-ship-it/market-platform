"""Small, dependency-free runtime observability registry.

The registry intentionally keeps bounded process-local observations.  The
deployment contract currently pins the application to one worker, and this
module does not introduce a monitoring vendor or an external state store.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import logging
import math
import re
import threading
import time
from typing import Any, Callable, Iterable
from urllib.parse import urlsplit


LOGGER = logging.getLogger("market_pulse")

API_WINDOW_SECONDS = 15 * 60
API_ALERT_WINDOW_SECONDS = 10 * 60
API_LATENCY_CRITICAL_WINDOW_SECONDS = 5 * 60
MAX_API_SAMPLES = 10_000
MAX_PROVIDER_EVENTS = 512
MAX_STALE_EVENTS = 1_000
MAX_CACHE_ENTRIES = 64

FAILURE_CLASSES = frozenset(
    {
        "timeout",
        "network_error",
        "http_error",
        "rate_limited",
        "invalid_response",
        "empty_response",
        "parse_error",
        "other_bounded_class",
    }
)
ALERT_RANK = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
BOUNDED_CACHE_NAMES = frozenset(
    {
        "site_data",
        "stock_details",
        "sector_charts",
        "global_markets",
        "global_market_items",
        "external_text",
        "taifex_options_chain",
        "taifex_openapi_list",
        "us_options_chains",
        "yahoo_tw_option_chain",
        "yahoo_tw_stock_resources",
        "yahoo_tw_future_technical_candles",
        "us_etf_center",
        "international_market_indexes",
        "treasury_yield_curve_rows",
        "shareholder_distributions",
        "other",
    }
)
BOUNDED_PROVIDERS = frozenset(
    {
        "twse",
        "tpex",
        "taifex",
        "yahoo",
        "tdcc",
        "treasury",
        "fred",
        "tradingeconomics",
        "cboe",
        "nasdaq",
        "nyse",
        "google_news",
        "barchart",
        "other",
    }
)
BOUNDED_STALE_REASONS = frozenset(
    {
        "provider_unavailable",
        "provider_timeout",
        "empty_response",
        "parse_error",
        "cooldown",
        "upstream_failure",
        "other",
    }
)

PROVIDER_HOSTS = {
    "www.taifex.com.tw": "taifex",
    "openapi.taifex.com.tw": "taifex",
    "www.twse.com.tw": "twse",
    "openapi.twse.com.tw": "twse",
    "www.tpex.org.tw": "tpex",
    "query1.finance.yahoo.com": "yahoo",
    "query2.finance.yahoo.com": "yahoo",
    "finance.yahoo.com": "yahoo",
    "tw.stock.yahoo.com": "yahoo",
    "smart.tdcc.com.tw": "tdcc",
    "home.treasury.gov": "treasury",
    "fred.stlouisfed.org": "fred",
    "tradingeconomics.com": "tradingeconomics",
    "cdn.cboe.com": "cboe",
    "www.nasdaq.com": "nasdaq",
    "nasdaqtrader.com": "nasdaq",
    "www.nyse.com": "nyse",
    "news.google.com": "google_news",
    "www.barchart.com": "barchart",
}


def _clock() -> float:
    return time.time()


def _iso(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc).isoformat()


def _bounded_label(value: Any, *, fallback: str = "other", limit: int = 48) -> str:
    rendered = re.sub(r"[^A-Za-z0-9_.:-]", "_", str(value or "")).strip("_")
    return rendered[:limit] or fallback


def _bounded_route(value: Any) -> str:
    rendered = re.sub(r"[^A-Za-z0-9_./<>:-]", "_", str(value or ""))
    rendered = re.sub(r"/{2,}", "/", rendered)
    return rendered[:120] or "/api/<route>"


def normalize_provider(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    host = (urlsplit(raw).hostname or raw).strip().lower()
    if host in PROVIDER_HOSTS:
        return PROVIDER_HOSTS[host]
    if host.endswith(".taifex.com.tw"):
        return "taifex"
    if host.endswith(".twse.com.tw"):
        return "twse"
    if host.endswith(".yahoo.com"):
        return "yahoo"
    return host if host in BOUNDED_PROVIDERS else "other"


def normalize_failure_class(error: Any = None, *, http_status: int | None = None) -> str:
    if http_status == 429:
        return "rate_limited"
    if http_status is not None and http_status >= 400:
        return "http_error"
    name = type(error).__name__.lower() if error is not None and not isinstance(error, str) else ""
    text = str(error or "").lower()
    if "jsondecode" in name or "invalid response" in text:
        return "invalid_response"
    if "empty response" in text or "empty" in text and "response" in text:
        return "empty_response"
    if "parse" in name or "parse_error" in text:
        return "parse_error"
    if "timeout" in name or "timeout" in text:
        return "timeout"
    if isinstance(error, OSError) or any(token in name for token in ("urlerror", "network", "connection")):
        return "network_error"
    return "other_bounded_class"


def normalize_route(route: str | None) -> str:
    raw = str(route or "").split("?", 1)[0]
    if raw.startswith("/api/") and "<" in raw:
        return _bounded_route(raw)
    if raw.startswith("/api/") and raw.count("/") <= 4 and not re.search(r"/[^/]*(?:\d{2,}|[A-Z]{2,}[A-Z0-9_-]*)", raw):
        return _bounded_route(raw)
    if raw == "/api":
        return "/api"
    return "/api/<unmatched>" if raw.startswith("/api/") else "/<non-api>"


def _status_class(status_code: int) -> str:
    code = int(status_code)
    return f"{code // 100}xx" if 100 <= code <= 599 else "other"


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return None
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return round(value, 3)


class _ObservabilityState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.api_samples: deque[dict[str, Any]] = deque(maxlen=MAX_API_SAMPLES)
        self.providers: dict[str, dict[str, Any]] = {}
        self.caches: dict[str, dict[str, Any]] = {}
        self.stale_events: deque[dict[str, Any]] = deque(maxlen=MAX_STALE_EVENTS)
        self.stale_active_since: dict[str, float] = {}
        self.stale_required_since: float | None = None
        self.readiness = {"current": "warming", "lastSeenAt": None, "notReadySince": None}


STATE = _ObservabilityState()


def reset_observability() -> None:
    with STATE.lock:
        STATE.api_samples.clear()
        STATE.providers.clear()
        STATE.caches.clear()
        STATE.stale_events.clear()
        STATE.stale_active_since.clear()
        STATE.stale_required_since = None
        STATE.readiness = {"current": "warming", "lastSeenAt": None, "notReadySince": None}


def _prune(samples: deque[dict[str, Any]], now: float, window: float) -> None:
    cutoff = now - window
    while samples and float(samples[0]["timestamp"]) < cutoff:
        samples.popleft()


def record_api_request(
    route: str,
    method: str,
    status_code: int,
    duration_ms: float,
    *,
    error_class: str | None = None,
    timestamp: float | None = None,
) -> None:
    observed_at = _clock() if timestamp is None else float(timestamp)
    route_key = normalize_route(route)
    method_key = _bounded_label(method, fallback="GET", limit=8).upper()
    status_key = _status_class(status_code)
    sample = {
        "timestamp": observed_at,
        "route": route_key,
        "method": method_key,
        "status_class": status_key,
        "status_code": int(status_code),
        "duration_ms": round(max(0.0, float(duration_ms)), 3),
        "error_class": error_class if error_class in FAILURE_CLASSES else (normalize_failure_class(error_class) if error_class else None),
    }
    with STATE.lock:
        STATE.api_samples.append(sample)
        _prune(STATE.api_samples, observed_at, API_WINDOW_SECONDS)
    LOGGER.info(
        "event=observability.api_request timestamp=%s component=api route=%s method=%s result=%s status_class=%s duration_ms=%.3f",
        _iso(observed_at), route_key, method_key, status_key, status_key, sample["duration_ms"],
    )


def _api_metrics(now: float, window_seconds: float) -> dict[str, Any]:
    with STATE.lock:
        samples = [item for item in STATE.api_samples if now - float(item["timestamp"]) <= window_seconds]
    durations = [float(item["duration_ms"]) for item in samples]
    status_classes: dict[str, int] = {}
    error_classes: dict[str, int] = {}
    routes: dict[str, dict[str, Any]] = {}
    for item in samples:
        status = str(item["status_class"])
        status_classes[status] = status_classes.get(status, 0) + 1
        error_class = item.get("error_class")
        if error_class:
            error_classes[error_class] = error_classes.get(error_class, 0) + 1
        route = str(item["route"])
        route_metrics = routes.setdefault(route, {"request_count": 0, "status_classes": {}, "error_classes": {}, "durations_ms": []})
        route_metrics["request_count"] += 1
        route_metrics["status_classes"][status] = route_metrics["status_classes"].get(status, 0) + 1
        if error_class:
            route_metrics["error_classes"][error_class] = route_metrics["error_classes"].get(error_class, 0) + 1
        route_metrics["durations_ms"].append(float(item["duration_ms"]))
    for route_metrics in routes.values():
        values = route_metrics.pop("durations_ms")
        route_metrics["latency_ms"] = {
            "count": len(values),
            "p50": _percentile(values, 0.50),
            "p95": _percentile(values, 0.95),
            "p99": _percentile(values, 0.99),
        }
    five_xx = sum(count for status, count in status_classes.items() if status == "5xx")
    return {
        "window_seconds": int(window_seconds),
        "request_count": len(samples),
        "status_classes": status_classes,
        "error_classes": error_classes,
        "latency_ms": {
            "count": len(durations),
            "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95),
            "p99": _percentile(durations, 0.99),
        },
        "five_xx_count": five_xx,
        "five_xx_rate": round(five_xx / len(samples), 6) if samples else 0.0,
        "by_route": routes,
    }


def _provider_state(provider: str) -> dict[str, Any]:
    key = normalize_provider(provider)
    return STATE.providers.setdefault(
        key,
        {
            "provider": key,
            "attempt_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "validation_failure_count": 0,
            "consecutive_failures": 0,
            "last_attempt": None,
            "last_success": None,
            "last_failure": None,
            "last_failure_class": None,
            "current_state": "unknown",
            "unavailable_since": None,
            "events": deque(maxlen=MAX_PROVIDER_EVENTS),
        },
    )


def record_provider_attempt(provider: str, *, timestamp: float | None = None) -> None:
    observed_at = _clock() if timestamp is None else float(timestamp)
    with STATE.lock:
        state = _provider_state(provider)
        state["attempt_count"] += 1
        state["last_attempt"] = observed_at
        state["events"].append({"timestamp": observed_at, "result": "attempt"})
    LOGGER.info("event=observability.provider timestamp=%s component=provider provider=%s result=attempt", _iso(observed_at), normalize_provider(provider))


def record_provider_success(provider: str, *, timestamp: float | None = None) -> None:
    observed_at = _clock() if timestamp is None else float(timestamp)
    with STATE.lock:
        state = _provider_state(provider)
        state["success_count"] += 1
        state["last_success"] = observed_at
        state["consecutive_failures"] = 0
        state["current_state"] = "available"
        state["unavailable_since"] = None
        state["events"].append({"timestamp": observed_at, "result": "success"})
    LOGGER.info("event=observability.provider timestamp=%s component=provider provider=%s result=success", _iso(observed_at), normalize_provider(provider))


def record_provider_failure(
    provider: str,
    failure_class: str | None = None,
    *,
    error: Any = None,
    http_status: int | None = None,
    timestamp: float | None = None,
) -> None:
    observed_at = _clock() if timestamp is None else float(timestamp)
    normalized_class = failure_class if failure_class in FAILURE_CLASSES else normalize_failure_class(error, http_status=http_status)
    with STATE.lock:
        state = _provider_state(provider)
        state["failure_count"] += 1
        state["last_failure"] = observed_at
        state["last_failure_class"] = normalized_class
        state["consecutive_failures"] += 1
        if state["unavailable_since"] is None:
            state["unavailable_since"] = observed_at
        state["current_state"] = "unavailable"
        state["events"].append({"timestamp": observed_at, "result": "failure", "failure_class": normalized_class})
    LOGGER.info(
        "event=observability.provider timestamp=%s component=provider provider=%s result=failure error_class=%s",
        _iso(observed_at), normalize_provider(provider), normalized_class,
    )


def record_provider_validation_failure(
    provider: str,
    failure_class: str,
    *,
    timestamp: float | None = None,
) -> None:
    observed_at = _clock() if timestamp is None else float(timestamp)
    normalized_class = failure_class if failure_class in FAILURE_CLASSES else "other_bounded_class"
    with STATE.lock:
        state = _provider_state(provider)
        state["failure_count"] += 1
        state["validation_failure_count"] += 1
        state["last_failure"] = observed_at
        state["last_failure_class"] = normalized_class
        state["consecutive_failures"] += 1
        if state["unavailable_since"] is None:
            state["unavailable_since"] = observed_at
        state["current_state"] = "unavailable"
        state["events"].append({"timestamp": observed_at, "result": "failure", "failure_class": normalized_class})
    LOGGER.info(
        "event=observability.provider_validation timestamp=%s component=provider provider=%s result=failure error_class=%s",
        _iso(observed_at), normalize_provider(provider), normalized_class,
    )


def _provider_snapshot(now: float) -> dict[str, Any]:
    result: dict[str, Any] = {}
    with STATE.lock:
        for key, state in STATE.providers.items():
            events = [event for event in state["events"] if now - float(event["timestamp"]) <= API_ALERT_WINDOW_SECONDS]
            attempts = sum(event["result"] == "attempt" for event in events)
            failures = sum(event["result"] == "failure" for event in events)
            result[key] = {
                "provider": key,
                "attempt_count": state["attempt_count"],
                "success_count": state["success_count"],
                "failure_count": state["failure_count"],
                "validation_failure_count": state["validation_failure_count"],
                "attempts_10m": attempts,
                "failures_10m": failures,
                "failure_rate_10m": round(failures / attempts, 6) if attempts else 0.0,
                "consecutive_failures": state["consecutive_failures"],
                "last_attempt": _iso(state["last_attempt"]),
                "last_success": _iso(state["last_success"]),
                "last_failure": _iso(state["last_failure"]),
                "last_failure_class": state["last_failure_class"],
                "current_state": state["current_state"],
                "unavailable_since": _iso(state["unavailable_since"]),
                "unavailable_for_seconds": max(0.0, now - float(state["unavailable_since"])) if state["unavailable_since"] is not None else 0.0,
            }
    return result


def _normalize_cache_name(name: str) -> str:
    key = _bounded_label(name, fallback="other")
    return key if key in BOUNDED_CACHE_NAMES else "other"


def _parse_timestamp(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def record_cache_state(
    name: str,
    stored_at: float | str | None,
    ttl_seconds: float | int | None,
    *,
    source: str | None = None,
    timestamp: float | None = None,
) -> None:
    now = _clock() if timestamp is None else float(timestamp)
    stored_timestamp = _parse_timestamp(stored_at)
    ttl = max(0.0, float(ttl_seconds)) if ttl_seconds is not None else None
    cache_name = _normalize_cache_name(name)
    age = None if stored_timestamp is None or stored_timestamp <= 0 else max(0.0, now - stored_timestamp)
    status = "missing" if age is None else ("fresh" if ttl is not None and age <= ttl else "stale")
    with STATE.lock:
        if len(STATE.caches) >= MAX_CACHE_ENTRIES and cache_name not in STATE.caches:
            STATE.caches.pop(next(iter(STATE.caches)))
        STATE.caches[cache_name] = {
            "cache": cache_name,
            "stored_at": _iso(stored_timestamp),
            "age_seconds": round(age, 3) if age is not None else None,
            "ttl_seconds": ttl,
            "status": status,
            "source": _normalize_provider_source(source),
            "observed_at": _iso(now),
        }
        if status == "fresh":
            clear_stale_fallback(source=cache_name)
    LOGGER.info(
        "event=observability.cache timestamp=%s component=cache cache=%s result=%s age_seconds=%s ttl_seconds=%s",
        _iso(now), cache_name, status, "-" if age is None else round(age, 3), "-" if ttl is None else round(ttl, 3),
    )


def _normalize_provider_source(value: str | None) -> str | None:
    if not value:
        return None
    key = normalize_provider(value)
    return key if key != "other" else _bounded_label(value, fallback="other", limit=32)


def record_stale_fallback(
    provider: str,
    source: str,
    reason: str,
    *,
    stale_at: float | str | None = None,
    ttl_seconds: float | int | None = None,
    timestamp: float | None = None,
) -> None:
    observed_at = _clock() if timestamp is None else float(timestamp)
    stale_timestamp = _parse_timestamp(stale_at)
    age = None if stale_timestamp is None else max(0.0, observed_at - stale_timestamp)
    provider_key = normalize_provider(provider)
    source_key = _normalize_cache_name(source)
    reason_key = reason if reason in BOUNDED_STALE_REASONS else "other"
    event = {
        "timestamp": observed_at,
        "provider": provider_key,
        "source": source_key,
        "reason": reason_key,
        "stale_at": _iso(stale_timestamp),
        "stale_age_seconds": round(age, 3) if age is not None else None,
        "ttl_seconds": max(0.0, float(ttl_seconds)) if ttl_seconds is not None else None,
    }
    with STATE.lock:
        STATE.stale_events.append(event)
        STATE.stale_active_since.setdefault(source_key, observed_at)
        STATE.stale_required_since = min(STATE.stale_active_since.values())
    LOGGER.info(
        "event=observability.stale_fallback timestamp=%s component=cache provider=%s source=%s result=stale reason=%s stale_age_ms=%s",
        _iso(observed_at), provider_key, source_key, reason_key, "-" if age is None else round(age * 1000, 3),
    )


def clear_stale_fallback(source: str | None = None) -> None:
    with STATE.lock:
        if source is None:
            STATE.stale_active_since.clear()
        else:
            STATE.stale_active_since.pop(_normalize_cache_name(source), None)
        STATE.stale_required_since = min(STATE.stale_active_since.values(), default=None)


def record_readiness(readiness: str, *, timestamp: float | None = None) -> None:
    observed_at = _clock() if timestamp is None else float(timestamp)
    state = readiness if readiness in {"warming", "degraded", "partial", "ready"} else "unknown"
    with STATE.lock:
        previous = STATE.readiness["current"]
        STATE.readiness["current"] = state
        STATE.readiness["lastSeenAt"] = observed_at
        if state == "ready":
            STATE.readiness["notReadySince"] = None
        elif previous == "ready" or STATE.readiness["notReadySince"] is None:
            STATE.readiness["notReadySince"] = observed_at
    LOGGER.info("event=observability.readiness timestamp=%s component=application result=%s status=%s", _iso(observed_at), state, state)


def _severity_for_api(now: float) -> tuple[str, dict[str, Any]]:
    short = _api_metrics(now, API_LATENCY_CRITICAL_WINDOW_SECONDS)
    long = _api_metrics(now, API_ALERT_WINDOW_SECONDS)
    if short["request_count"] >= 10 and (short["latency_ms"]["p95"] or 0) > 10_000:
        return "CRITICAL", {"reason": "p95_gt_10s", "p95_ms": short["latency_ms"]["p95"], "eligible_requests": short["request_count"]}
    if long["request_count"] >= 20 and (long["latency_ms"]["p95"] or 0) > 5_000:
        return "WARNING", {"reason": "p95_gt_5s", "p95_ms": long["latency_ms"]["p95"], "eligible_requests": long["request_count"]}
    return "NORMAL", {"eligible_requests": long["request_count"], "p95_ms": long["latency_ms"]["p95"]}


def evaluate_alert_conditions(
    *,
    now: float | None = None,
    authorized_window: bool = False,
    cold_start: bool = False,
    applicable_providers: set[str] | None = None,
    applicable_caches: set[str] | None = None,
) -> dict[str, Any]:
    observed_at = _clock() if now is None else float(now)
    conditions: list[dict[str, Any]] = []

    api = _api_metrics(observed_at, API_ALERT_WINDOW_SECONDS)
    if api["request_count"] >= 20 and api["five_xx_rate"] >= 0.02:
        conditions.append({"name": "api_5xx", "status": "WARNING", "five_xx_rate": api["five_xx_rate"], "requests": api["request_count"]})
    else:
        conditions.append({"name": "api_5xx", "status": "NORMAL", "five_xx_rate": api["five_xx_rate"], "requests": api["request_count"]})

    latency_status, latency_details = _severity_for_api(observed_at)
    conditions.append({"name": "api_latency", "status": latency_status, **latency_details})

    provider_snapshot = _provider_snapshot(observed_at)
    for provider, summary in provider_snapshot.items():
        if applicable_providers is not None and provider not in {normalize_provider(item) for item in applicable_providers}:
            continue
        if summary["unavailable_for_seconds"] >= 15 * 60:
            provider_status = "CRITICAL"
        elif int(summary.get("consecutive_failures") or 0) >= 3 or (
            summary["failure_rate_10m"] >= 0.20 and summary["attempts_10m"] >= 5
        ):
            provider_status = "WARNING"
        else:
            provider_status = "NORMAL"
        conditions.append({"name": f"provider:{provider}", "status": provider_status, **summary})

    with STATE.lock:
        cache_entries = deepcopy(STATE.caches)
        stale_events = [event for event in STATE.stale_events if observed_at - float(event["timestamp"]) <= 15 * 60]
        stale_required_since = STATE.stale_required_since
        readiness = deepcopy(STATE.readiness)
    for cache_name, cache in cache_entries.items():
        if applicable_caches is not None and cache_name not in {_normalize_cache_name(item) for item in applicable_caches}:
            continue
        ttl = cache.get("ttl_seconds")
        age = cache.get("age_seconds")
        status = "NORMAL"
        if ttl and age is not None and age > 4 * ttl:
            status = "CRITICAL"
        elif ttl and age is not None and age > 2 * ttl:
            status = "WARNING"
        conditions.append({"name": f"cache:{cache_name}", "status": status, "age_seconds": age, "ttl_seconds": ttl, "freshness": cache.get("status")})

    stale_status = "NORMAL"
    if stale_required_since is not None and observed_at - stale_required_since >= 30 * 60:
        stale_status = "CRITICAL"
    elif len(stale_events) >= 5 or any(
        event.get("ttl_seconds") and event.get("stale_age_seconds") is not None and event["stale_age_seconds"] > 2 * event["ttl_seconds"]
        for event in stale_events
    ):
        stale_status = "WARNING"
    conditions.append({"name": "stale_fallback", "status": stale_status, "event_count_15m": len(stale_events)})

    readiness_status = "NORMAL"
    suppressed = authorized_window or cold_start
    if not suppressed and readiness.get("notReadySince") is not None and observed_at - float(readiness["notReadySince"]) >= 15 * 60:
        readiness_status = "CRITICAL"
    conditions.append({"name": "application_readiness", "status": readiness_status, "readiness": readiness.get("current"), "suppressed": suppressed})

    overall = max((condition["status"] for condition in conditions), key=lambda value: ALERT_RANK[value], default="NORMAL")
    return {"status": overall, "evaluated_at": _iso(observed_at), "conditions": conditions}


def get_observability_snapshot(*, now: float | None = None) -> dict[str, Any]:
    observed_at = _clock() if now is None else float(now)
    api = _api_metrics(observed_at, API_ALERT_WINDOW_SECONDS)
    api_duration = api["latency_ms"]
    with STATE.lock:
        caches = deepcopy(STATE.caches)
        stale_events = [event for event in STATE.stale_events if observed_at - float(event["timestamp"]) <= 15 * 60]
        readiness = deepcopy(STATE.readiness)
    return {
        "evaluated_at": _iso(observed_at),
        "api.request.count": api["request_count"],
        "api.request.duration": {"count": api_duration["count"], "p50": api_duration["p50"], "p95": api_duration["p95"], "p99": api_duration["p99"]},
        "api.response.5xx.count": api["five_xx_count"],
        "api": api,
        "providers": _provider_snapshot(observed_at),
        "caches": caches,
        "stale_fallback": {"event_count_15m": len(stale_events), "events": stale_events},
        "readiness": readiness,
        "alerts": evaluate_alert_conditions(now=observed_at),
    }


def api_observability_before_request() -> None:
    from flask import g, request

    if request.path == "/api" or request.path.startswith("/api/"):
        route = request.url_rule.rule if request.url_rule is not None else request.path
        g.api_observability = {"started_at": _clock(), "route": normalize_route(route), "method": request.method}


def api_observability_after_request(response: Any) -> Any:
    from flask import g, request

    state = getattr(g, "api_observability", None)
    if state is not None:
        duration_ms = (_clock() - float(state["started_at"])) * 1000
        record_api_request(
            state["route"],
            state["method"],
            response.status_code,
            duration_ms,
            error_class=normalize_failure_class(http_status=response.status_code) if response.status_code >= 400 else None,
        )
    return response


def with_clock(clock: Callable[[], float]) -> Callable[[], None]:
    """Temporarily replace the clock for deterministic tests."""
    global _clock
    previous = _clock
    _clock = clock

    def restore() -> None:
        global _clock
        _clock = previous

    return restore
