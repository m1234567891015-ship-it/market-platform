"""TD-03 H-11-04 rollout eligibility gate.

This is a read-only gate report.  It never connects to Redis, changes
environment variables, edits deployment files, or touches production data.
It records the safe current state and keeps rollout blocked until the real
staging evidence and manual approval exist.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def configured_workers() -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for filename in ("Procfile", "render.yaml"):
        text = (ROOT / filename).read_text(encoding="utf-8")
        match = re.search(r"--workers(?:=|\s+)(\d+)", text)
        result[filename] = int(match.group(1)) if match else None
    return result


def rollout_gate() -> dict[str, Any]:
    redis_url_present = bool(str(os.environ.get("MARKET_PULSE_REDIS_URL") or "").strip())
    modes = {
        "rate_limit": str(os.environ.get("MARKET_PULSE_RATE_LIMIT_MODE") or "local").strip().lower(),
        "cache_l2": str(os.environ.get("MARKET_PULSE_CACHE_L2_MODE") or "local").strip().lower(),
        "single_flight": str(os.environ.get("MARKET_PULSE_SINGLE_FLIGHT_MODE") or "local").strip().lower(),
        "background_lease": str(os.environ.get("MARKET_PULSE_BACKGROUND_LEASE_MODE") or "local").strip().lower(),
    }
    workers = configured_workers()
    safe_mode = all(value == "local" for value in modes.values())
    single_worker = workers == {"Procfile": 1, "render.yaml": 1}
    checks = {
        "current_safe_mode": {
            "status": "pass" if safe_mode else "blocked",
            "modes": modes,
            "required": "all shared modes remain local before approval",
        },
        "deployment_worker_gate": {
            "status": "pass" if single_worker else "blocked",
            "workers": workers,
            "required": "Procfile and render.yaml remain at one worker",
        },
        "redis_url": {
            "status": "pass" if redis_url_present else "blocked",
            "value": "present-redacted" if redis_url_present else "absent",
            "required": "staging secret store supplies MARKET_PULSE_REDIS_URL",
        },
        "real_redis_health": {"status": "not-run", "required": "PING and TTL sentinel read-back"},
        "backup_restore": {"status": "not-run", "required": "staging snapshot/checkpoint and isolated restore evidence"},
        "h11_02_real_bucket_contract": {"status": "not-run", "required": "Redis contract for the six JSON-safe L2 buckets"},
        "h11_03_real_dual_worker": {"status": "not-run", "required": "staging load, latency and disconnect/fault evidence"},
        "observation_period": {"status": "blocked", "required": "approved observation window with no unexplained errors"},
        "manual_rollout_approval": {"status": "blocked", "required": "explicit human approval for a separate deployment batch"},
    }
    required_checks = (
        "redis_url",
        "real_redis_health",
        "backup_restore",
        "h11_02_real_bucket_contract",
        "h11_03_real_dual_worker",
        "observation_period",
        "manual_rollout_approval",
    )
    eligible = safe_mode and single_worker and all(checks[name]["status"] == "pass" for name in required_checks)
    return {
        "eligible": eligible,
        "status": "eligible" if eligible else "blocked",
        "reason": "all staging evidence and manual approval are present" if eligible else "real Redis/staging evidence, observation period and manual rollout approval are missing",
        "checks": checks,
        "rollback_order": [
            "disable all shared modes (local)",
            "restore single worker (--workers 1)",
            "rollback the individual adapter/deployment change",
        ],
        "prohibited_in_this_batch": [
            "deployment configuration change",
            "baseline/CSP change",
            "production data or SQLite/twse-cache.json change",
        ],
    }


def main() -> int:
    print(json.dumps(rollout_gate(), ensure_ascii=False, indent=2, sort_keys=True))
    print("TD03_H11_04_ROLLOUT_GATE_BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
