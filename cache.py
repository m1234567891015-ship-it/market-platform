"""In-memory cache state extracted from app.py (TD-01 slice 2a).

This is a data-only slice: locks, registries, and the shared cache_data dict,
with no behavior change. The functions that operate on this state
(load_disk_cache, refresh_cache, ensure_cache, read/write_memory_cache, etc.)
still live in app.py for now and import these names back — every existing
mutation of this state is in-place (dict item assignment, lock context
managers), never a wholesale reassignment of the name itself, so re-exporting
into app.py's namespace via `from cache import ...` preserves identity and
behavior exactly.

background_updater_lock/background_updater_started are deliberately NOT here:
they're only ever read/written inside start_background_updater via a `global`
statement, and that function hasn't moved yet. Splitting a rebound (not just
mutated) variable from its only reader/writer would make the two diverge
silently (see TD-01 slice 1's API_RATE_LIMIT_PER_WINDOW lesson) - so that pair
moves together with the function itself in a later slice.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
BUNDLED_CACHE_FILE = BASE_DIR / "twse-cache.json"
CACHE_FILE = Path(os.environ.get("MARKET_PULSE_CACHE_FILE", str(BUNDLED_CACHE_FILE)))
CACHE_VERSION = 13

cache_lock = threading.RLock()
cache_refresh_lock = threading.Lock()
cache_flight_lock = threading.Lock()
cache_flights: dict[str, threading.Event] = {}
CACHE_FLIGHT_WAIT_SECONDS = 120

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
}

_yahoo_options_crumb: dict[str, Any] = {"value": "", "stored_at": 0.0}
