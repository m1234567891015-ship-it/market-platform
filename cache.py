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

from market_config import EXCLUDED_SECTOR_SOURCE_NAMES

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
cache_flights: dict[str, threading.Event] = {}
CACHE_FLIGHT_WAIT_SECONDS = 120

background_updater_lock = threading.Lock()
background_updater_started = False

penny_sector_recommendation_lock = threading.Lock()
penny_sector_recommendation_cache: dict[str, Any] = {}
PENNY_SECTOR_RECOMMENDATION_CACHE_SECONDS = 30 * 60

# Coalesces concurrent requests for the same option-chain cache key (e.g. a page that fires
# /api/options/chain and /api/ai-analysis for the same underlying at once) so only one of them
# runs the ~12-day TAIFEX scan; the rest wait for and reuse that real result instead of each
# triggering their own redundant scan.
taifex_options_chain_inflight: dict[str, threading.Event] = {}
taifex_options_chain_inflight_lock = threading.Lock()

cache_data: dict[str, Any] = {
    "site_data": None,
    "all_stocks": [],
    "market_date": None,
    "cached_at": None,
    "last_error": None,
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
# live_search_dedup already had its own eviction (a full O(n) rebuild-filter
# per write) before this and is deliberately handled as its own follow-up
# change, not folded in here.
BUCKET_CAPS: dict[str, int] = {
    "stock_details": 2500,
    "yahoo_tw_stock_resources": 3000,
    "us_options_chains": 500,
    "yahoo_tw_option_chain": 150,
    "taifex_options_chain": 300,
    "external_text": 500,
    "global_market_items": 300,
    "global_markets": 100,
    "us_etf_center": 500,
    "sector_charts": 150,
    "yahoo_tw_future_technical_candles": 200,
    "taifex_openapi_list": 100,
}


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


def read_memory_cache(bucket: str, key: str, ttl_seconds: int | float) -> Any | None:
    now = time.time()
    with cache_lock:
        cached = cache_data.get(bucket, {}).get(key)
    if cached and now - float(cached.get("stored_at") or 0) < ttl_seconds:
        return cached.get("payload")
    return None


def write_memory_cache(bucket: str, key: str, payload: Any) -> None:
    with cache_lock:
        cache_data.setdefault(bucket, {})[key] = {"stored_at": time.time(), "payload": payload}
        enforce_bucket_cap(bucket)


def claim_cache_flight(key: str) -> tuple[bool, threading.Event]:
    """Elect one request to refresh a cache key while concurrent requests wait."""
    with cache_flight_lock:
        event = cache_flights.get(key)
        if event is not None:
            return False, event
        event = threading.Event()
        cache_flights[key] = event
        return True, event


def finish_cache_flight(key: str, event: threading.Event) -> None:
    with cache_flight_lock:
        if cache_flights.get(key) is event:
            cache_flights.pop(key, None)
            event.set()


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
        treasury_rows = deserialize_treasury_yield_curve_cache(payload.get("treasury_yield_curve_rows"))
        if treasury_rows:
            cache_data["treasury_yield_curve_rows"] = treasury_rows
    return True


def build_disk_cache_snapshot() -> dict[str, Any]:
    """Capture one internally consistent cache generation before writing it to disk."""
    with cache_lock:
        treasury_rows = copy.deepcopy(cache_data.get("treasury_yield_curve_rows") or {})
        return {
            "cache_version": CACHE_VERSION,
            "site_data": copy.deepcopy(cache_data["site_data"]),
            "all_stocks": copy.deepcopy(cache_data["all_stocks"]),
            "market_date": cache_data["market_date"],
            "cached_at": cache_data["cached_at"],
            "treasury_yield_curve_rows": serialize_treasury_yield_curve_cache(treasury_rows),
        }


def save_disk_cache(snapshot: dict[str, Any] | None = None) -> None:
    # Serialize outside the shared cache lock. The snapshot is already a single generation.
    payload = snapshot if snapshot is not None else build_disk_cache_snapshot()
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


def refresh_cache() -> None:
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


def update_loop() -> None:
    import app  # deferred: refresh_tpex_cache hasn't moved out of app.py yet (TD-01 slice 2c)

    while True:
        try:
            app.refresh_tpex_cache()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Background TPEx cache refresh failed")
            with cache_lock:
                cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE
        try:
            refresh_cache()
        except Exception:  # noqa: BLE001
            LOGGER.exception("Background TWSE cache refresh failed")
            with cache_lock:
                cache_data["last_error"] = PUBLIC_CACHE_ERROR_MESSAGE
        time.sleep(UPDATE_INTERVAL_SECONDS)


def ensure_cache() -> None:
    with cache_lock:
        has_site_data = cache_data["site_data"] is not None
    if not has_site_data:
        load_disk_cache()
    with cache_lock:
        has_site_data = cache_data["site_data"] is not None
    if not has_site_data:
        with cache_refresh_lock:
            with cache_lock:
                has_site_data = cache_data["site_data"] is not None
            if has_site_data:
                return
            load_disk_cache()
            with cache_lock:
                has_site_data = cache_data["site_data"] is not None
            if has_site_data:
                return
            LOGGER.info("Cold cache refresh started")
            try:
                refresh_cache()
            except Exception:
                LOGGER.exception("Cold cache refresh failed")
                raise
            LOGGER.info("Cold cache refresh finished")
        return


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
