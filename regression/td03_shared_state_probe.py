"""TD-03 shared-state inventory and two-process probe.

This script intentionally imports only cache/security configuration modules. It
does not import app.py, start a server, touch SQLite, or write the production
cache file. The child mode demonstrates the current process-local boundary by
running one state operation in each of two independent Python processes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def child_probe(role: str) -> int:
    import cache
    import security

    security.API_RATE_LIMIT_PER_WINDOW = 1
    with security.API_RATE_LIMIT_LOCK:
        security.API_RATE_LIMIT_STATE.clear()
    rate_limit_retry_after = security.register_rate_limit_window_hit("td03-probe-client", 100.0)

    cache_value = None
    if role == "writer":
        cache.write_memory_cache("global_markets", "td03-probe-key", {"owner": role})
        cache_value = cache.read_memory_cache("global_markets", "td03-probe-key", 60)
    else:
        cache_value = cache.read_memory_cache("global_markets", "td03-probe-key", 60)

    is_leader, event = cache.claim_cache_flight("td03-probe-key")
    cache.finish_cache_flight("td03-probe-key", event)
    print(
        json.dumps(
            {
                "role": role,
                "rate_limit_first_hit_retry_after": rate_limit_retry_after,
                "cache_readback": cache_value,
                "cache_flight_is_leader": is_leader,
            },
            ensure_ascii=False,
        )
    )
    return 0


def configured_workers() -> dict[str, int | None]:
    values: dict[str, int | None] = {}
    for name in ("Procfile", "render.yaml"):
        text = (ROOT / name).read_text(encoding="utf-8")
        match = re.search(r"--workers(?:=|\s+)(\d+)", text)
        values[name] = int(match.group(1)) if match else None
    return values


def inventory() -> dict[str, Any]:
    import cache
    import market_config
    import security

    return {
        "process_local_state": [
            {"name": "API_RATE_LIMIT_STATE", "module": "security.py", "purpose": "per-client sliding-window rate limit"},
            {"name": "cache_data", "module": "cache.py", "purpose": "memory cache and process-local snapshots"},
            {"name": "cache_flights", "module": "cache.py", "purpose": "generic request coalescing"},
            {"name": "penny_sector_recommendation_cache", "module": "cache.py", "purpose": "30-minute recommendation cache"},
            {"name": "taifex_options_chain_inflight", "module": "cache.py", "purpose": "options-chain request coalescing"},
        ],
        "locks": [
            "API_RATE_LIMIT_LOCK",
            "cache_lock",
            "cache_refresh_lock",
            "cache_flight_lock",
            "background_updater_lock",
            "penny_sector_recommendation_lock",
            "taifex_options_chain_inflight_lock",
        ],
        "rate_limit": {
            "window_seconds": security.API_RATE_LIMIT_WINDOW_SECONDS,
            "per_window": security.API_RATE_LIMIT_PER_WINDOW,
            "max_clients": security.API_RATE_LIMIT_MAX_CLIENTS,
            "theoretical_timestamp_slots": security.API_RATE_LIMIT_MAX_CLIENTS * security.API_RATE_LIMIT_PER_WINDOW,
        },
        "cache": {
            "bucket_count": len(market_config.CACHE_BUCKET_MAX_ENTRIES),
            "bucket_caps_total": sum(market_config.CACHE_BUCKET_MAX_ENTRIES.values()),
            "bucket_caps": dict(market_config.CACHE_BUCKET_MAX_ENTRIES),
            "cache_flight_wait_seconds": cache.CACHE_FLIGHT_WAIT_SECONDS,
        },
        "deployment_workers": configured_workers(),
        "persistent_state": {
            "disk_cache": "MARKET_PULSE_CACHE_FILE / twse-cache.json",
            "derivatives_store": "DERIVATIVES_DB_PATH / derivatives-platform.sqlite3",
            "scope": "persistent data; not used as a cross-worker lock",
        },
    }


def run_child(role: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["MARKET_PULSE_DISABLE_BACKGROUND"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--child", role],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    payload = json.loads(result.stdout.strip())
    payload["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=("writer", "reader"))
    args = parser.parse_args()
    if args.child:
        return child_probe(args.child)

    writer = run_child("writer")
    reader = run_child("reader")
    report = {
        "probe": "TD03_SHARED_STATE_PROBE",
        "inventory": inventory(),
        "two_process_observation": {
            "writer": writer,
            "reader": reader,
            "rate_limit_is_process_local": writer["rate_limit_first_hit_retry_after"] is None and reader["rate_limit_first_hit_retry_after"] is None,
            "memory_cache_is_process_local": writer["cache_readback"] is not None and reader["cache_readback"] is None,
            "cache_flight_is_process_local": writer["cache_flight_is_leader"] and reader["cache_flight_is_leader"],
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print("TD03_SHARED_STATE_PROBE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
