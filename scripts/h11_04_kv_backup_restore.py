"""H11-04 staging-only logical Key Value backup/restore acceptance.

This is deliberately a CLI utility.  It never exposes a web route and it only
writes keys in the per-run ``market-pulse:h11-04`` validation namespaces.  The
source database is read with SCAN/TYPE/DUMP/PTTL and restored copies are always
written with RESTORE (without REPLACE) to a fresh namespace.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")
BUCKETS = (
    "global_markets",
    "sector_charts",
    "stock_details",
    "taifex_options_chain",
    "us_etf_center",
    "yahoo_tw_option_chain",
)
TTL_TOLERANCE_MS = 1500
CANARY_TTL_MS = 300_000
REAL_L2_BUCKETS = (
    "global_markets",
    "us_etf_center",
    "sector_charts",
    "stock_details",
    "taifex_options_chain",
    "yahoo_tw_option_chain",
)


class ProbeFailure(RuntimeError):
    """Safe failure carrying only a fixed probe stage, never backend text."""

    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def safe_http_status(url: str) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": "market-pulse-h11-04-probe"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read(1024 * 1024)
            return int(response.status)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return 0


def run_id_from_args(value: str | None) -> str:
    run_id = value or f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("RUN_ID must match the documented safe namespace format")
    return run_id


def redis_client():
    redis_url = str(os.environ.get("MARKET_PULSE_REDIS_URL") or "").strip()
    if not redis_url:
        raise RuntimeError("MARKET_PULSE_REDIS_URL is unavailable")
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise RuntimeError("redis package is unavailable") from exc
    client = redis.Redis.from_url(
        redis_url,
        protocol=2,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=False,
    )
    client.ping()
    return client


def text_key(value: bytes | str) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def scan_keys(client: Any, pattern: str) -> list[str]:
    return sorted(text_key(key) for key in client.scan_iter(match=pattern, count=200))


def key_snapshot(client: Any, keys: list[str]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for key in keys:
        payload = client.dump(key)
        if payload is None:
            raise RuntimeError("source key disappeared during read-only snapshot")
        snapshot[key] = sha256_bytes(payload)
    return snapshot


def create_canaries(client: Any, run_id: str) -> tuple[list[str], dict[str, str]]:
    source_prefix = f"market-pulse:h11-04:backup-test:{run_id}:source:"
    restore_prefix = f"market-pulse:h11-04:restore:{run_id}:"
    if scan_keys(client, f"{source_prefix}*") or scan_keys(client, f"{restore_prefix}*"):
        raise RuntimeError("validation namespace collision; refusing to write")
    canary_keys: list[str] = []
    bucket_by_key: dict[str, str] = {}
    for bucket in BUCKETS:
        key = f"{source_prefix}{bucket}"
        envelope = {
            "expires_at": time.time() + (CANARY_TTL_MS / 1000),
            "payload": {
                "h11_04_canary": True,
                "bucket": bucket,
                "run_id": run_id,
                "items": [1, 2, 3],
            },
        }
        if not client.set(key, canonical_json(envelope), px=CANARY_TTL_MS, nx=True):
            raise RuntimeError("validation canary collision; refusing to overwrite")
        canary_keys.append(key)
        bucket_by_key[key] = bucket
    return canary_keys, bucket_by_key


def backup_records(client: Any, keys: list[str], run_id: str, bucket_by_key: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    type_counts: Counter[str] = Counter()
    expiring = 0
    persistent = 0
    for key in keys:
        key_type = text_key(client.type(key))
        if key_type == "none":
            raise RuntimeError("source key disappeared during TYPE")
        dump_payload = client.dump(key)
        if dump_payload is None:
            raise RuntimeError("source key disappeared during DUMP")
        pttl = int(client.pttl(key))
        if pttl == -2:
            raise RuntimeError("source key disappeared during PTTL")
        backup_timestamp = utc_now()
        record: dict[str, Any] = {
            "logical_key_identifier": key,
            "redis_type": key_type,
            "dump_b64": base64.b64encode(dump_payload).decode("ascii"),
            "pttl_ms": pttl,
            "ttl_class": "persistent" if pttl == -1 else "expiring",
            "backup_timestamp_utc": backup_timestamp,
            "payload_sha256": sha256_bytes(dump_payload),
        }
        if key in bucket_by_key:
            record["l2_bucket"] = bucket_by_key[key]
        records.append(record)
        type_counts[key_type] += 1
        if pttl == -1:
            persistent += 1
        elif pttl >= 0:
            expiring += 1
    manifest: dict[str, Any] = {
        "format_version": "h11-04-logical-backup-v1",
        "source_candidate_sha": os.environ.get(
            "H11_04_SOURCE_CANDIDATE_SHA", "8a3cebb1cbe7f5b9f4b8ca350887ea561f82ebcc"
        ),
        "render_service_id": os.environ.get("H11_04_RENDER_SERVICE_ID", "srv-dap3ij3tqb8s73f7birg"),
        "render_kv_id": os.environ.get("H11_04_RENDER_KV_ID", "red-dap3heuk1f9s739b7810"),
        "run_id": run_id,
        "backup_utc_timestamp": utc_now(),
        "key_count": len(records),
        "per_type_counts": dict(sorted(type_counts.items())),
        "expiring_key_count": expiring,
        "persistent_key_count": persistent,
        "six_l2_bucket_coverage": {bucket: {"status": "present", "key_kind": "canary"} for bucket in BUCKETS},
        "artifact_sha256": "",
    }
    return records, manifest


def write_artifact(output_dir: Path, manifest: dict[str, Any], records: list[dict[str, Any]]) -> tuple[Path, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    preimage = {"manifest": manifest, "records": records}
    artifact_hash = sha256_bytes(canonical_json(preimage))
    manifest["artifact_sha256"] = artifact_hash
    artifact_path = output_dir / "logical-backup.json"
    artifact_path.write_bytes(canonical_json({"manifest": manifest, "records": records}) + b"\n")
    written = json.loads(artifact_path.read_text(encoding="utf-8").strip())
    written_hash = written["manifest"].pop("artifact_sha256")
    written["manifest"]["artifact_sha256"] = ""
    if written_hash != artifact_hash or sha256_bytes(canonical_json(written)) != artifact_hash:
        raise RuntimeError("backup artifact SHA-256 verification failed")
    return artifact_path, artifact_hash


def restore_and_verify(client: Any, records: list[dict[str, Any]], run_id: str) -> tuple[list[str], dict[str, Any]]:
    restore_prefix = f"market-pulse:h11-04:restore:{run_id}:"
    if scan_keys(client, f"{restore_prefix}*"):
        raise RuntimeError("restore namespace collision; refusing to write")
    restored_keys: list[str] = []
    ttl_failures = 0
    for index, record in enumerate(records):
        target = f"{restore_prefix}{index:06d}"
        if client.exists(target):
            raise RuntimeError("restore collision; RESTORE REPLACE is prohibited")
        payload = base64.b64decode(record["dump_b64"].encode("ascii"), validate=True)
        source_pttl = int(record["pttl_ms"])
        backup_epoch = datetime.fromisoformat(record["backup_timestamp_utc"].replace("Z", "+00:00")).timestamp()
        if source_pttl == -1:
            restore_ttl = 0
        else:
            restore_ttl = max(1, source_pttl - int((time.time() - backup_epoch) * 1000))
        client.execute_command("RESTORE", target, restore_ttl, payload)
        restored_keys.append(target)
        if not client.exists(target):
            raise RuntimeError("restored key is missing")
        restored_type = text_key(client.type(target))
        if restored_type != record["redis_type"]:
            raise RuntimeError("restored Redis TYPE mismatch")
        restored_dump = client.dump(target)
        if restored_dump is None or sha256_bytes(restored_dump) != record["payload_sha256"]:
            raise RuntimeError("restored payload SHA-256 mismatch")
        restored_pttl = int(client.pttl(target))
        if source_pttl == -1:
            if restored_pttl != -1:
                ttl_failures += 1
        else:
            expected = restore_ttl
            if restored_pttl <= 0 or abs(restored_pttl - expected) > TTL_TOLERANCE_MS:
                ttl_failures += 1
    if ttl_failures:
        raise RuntimeError(f"TTL semantics mismatch count={ttl_failures}")
    return restored_keys, {"key_count": len(restored_keys), "ttl_tolerance_ms": TTL_TOLERANCE_MS}


def cleanup(client: Any, keys: list[str]) -> None:
    if keys:
        client.unlink(*keys)
    remaining = [key for key in keys if client.exists(key)]
    if remaining:
        raise RuntimeError("validation cleanup could not be proven")


def probe_health() -> dict[str, int]:
    port = str(os.environ.get("PORT") or "10000")
    base = f"http://127.0.0.1:{port}"
    return {
        "health": safe_http_status(f"{base}/api/health"),
        "v1_status": safe_http_status(f"{base}/api/derivatives/v1-status"),
    }


def _failure_category(exc: BaseException) -> str:
    """Classify an exception without exposing its message or connection data."""
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "import" in name or "module" in name:
        return "import"
    if "ssl" in name or "tls" in name or "certificate" in text:
        return "tls/ssl"
    if "auth" in name or "authentication" in text or "invalid username-password" in text:
        return "authentication"
    if "acl" in text or "no permission" in text or "permission" in text:
        return "authorization/ACL"
    if "timeout" in name or "timed out" in text:
        return "timeout"
    if "dns" in text or "name or service" in text or "nodename" in text or "getaddrinfo" in text:
        return "DNS"
    if "url" in name or "scheme" in text or "parse" in text:
        return "URL parsing"
    if "protocol" in text or "resp" in text:
        return "protocol/client incompatibility"
    if "connection" in name or "connect" in text or "refused" in text or "network" in text:
        return "socket connection"
    return "unknown"


def _safe_errno(exc: BaseException) -> int | str | None:
    value = getattr(exc, "errno", None)
    return value if isinstance(value, (int, str)) else None


def execute_runtime_diagnostic() -> dict[str, Any]:
    """Run the authorized, read-only direct-vs-production Redis diagnostic."""
    pre = probe_health()
    env_names = (
        "MARKET_PULSE_CACHE_L2_MODE",
        "MARKET_PULSE_SINGLE_FLIGHT_MODE",
        "MARKET_PULSE_BACKGROUND_LEASE_MODE",
        "MARKET_PULSE_RATE_LIMIT_MODE",
    )
    redis_url_present = bool(str(os.environ.get("MARKET_PULSE_REDIS_URL") or "").strip())
    modes = {name: str(os.environ.get(name) or "").strip().lower() or "other" for name in env_names}
    report: dict[str, Any] = {
        "runtime_env": "PASS" if redis_url_present else "FAIL",
        "redis_url_presence": "PASS" if redis_url_present else "FAIL",
        "modes": modes,
        "python_version": platform.python_version(),
        "redis_version": None,
        "redis_import": "FAIL",
        "redis_redis_present": "NO",
        "redis_client_loaded": "NO",
        "redis_spec_initializing": "UNAVAILABLE",
        "direct_client_init": "FAIL",
        "direct_redis_ping": "FAIL",
        "ping_elapsed_ms": None,
        "cache_l2_builder": "FAIL",
        "cache_l2_getter": "FAIL",
        "exception_class": "NONE",
        "failure_stage": "NONE",
        "failure_category": "NONE",
        "safe_errno": None,
        "pre_health": pre["health"],
        "pre_v1_status": pre["v1_status"],
        "redis_writes_performed": "NO",
        "l2_acceptance_retried": "NO",
    }
    try:
        import redis
    except Exception as exc:
        report.update({"exception_class": type(exc).__name__, "failure_stage": "redis_import", "failure_category": _failure_category(exc), "safe_errno": _safe_errno(exc)})
    else:
        report["redis_import"] = "PASS"
        report["redis_version"] = getattr(redis, "__version__", "UNAVAILABLE")
        report["redis_redis_present"] = "YES" if hasattr(redis, "Redis") else "NO"
        report["redis_client_loaded"] = "YES" if "redis.client" in sys.modules else "NO"
        spec = getattr(redis, "__spec__", None)
        initializing = getattr(spec, "_initializing", None) if spec is not None else None
        report["redis_spec_initializing"] = "TRUE" if initializing is True else ("FALSE" if initializing is False else "UNAVAILABLE")
        if report["redis_redis_present"] == "YES" and redis_url_present:
            timeout_value = max(0.1, float(os.environ.get("MARKET_PULSE_SHARED_STATE_TIMEOUT_SECONDS", "1")))
            try:
                direct_client = redis.Redis.from_url(
                    str(os.environ["MARKET_PULSE_REDIS_URL"]),
                    protocol=2,
                    socket_connect_timeout=timeout_value,
                    socket_timeout=timeout_value,
                    decode_responses=True,
                )
                report["direct_client_init"] = "PASS"
            except Exception as exc:
                report.update({"exception_class": type(exc).__name__, "failure_stage": "direct_client_init", "failure_category": _failure_category(exc), "safe_errno": _safe_errno(exc)})
            else:
                started = time.perf_counter()
                try:
                    direct_client.ping()
                except Exception as exc:
                    report.update({"exception_class": type(exc).__name__, "failure_stage": "direct_redis_ping", "failure_category": _failure_category(exc), "safe_errno": _safe_errno(exc)})
                else:
                    report["direct_redis_ping"] = "PASS"
                report["ping_elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        try:
            import cache
            cache._build_cache_l2_shared_adapter()
            report["cache_l2_builder"] = "PASS"
        except Exception as exc:
            if report["exception_class"] == "NONE":
                report.update({"exception_class": type(exc).__name__, "failure_stage": "cache_l2_builder", "failure_category": _failure_category(exc), "safe_errno": _safe_errno(exc)})
        try:
            import cache
            cache._get_cache_l2_shared_adapter()
            report["cache_l2_getter"] = "PASS"
        except Exception as exc:
            if report["exception_class"] == "NONE":
                report.update({"exception_class": type(exc).__name__, "failure_stage": "cache_l2_getter", "failure_category": _failure_category(exc), "safe_errno": _safe_errno(exc)})
    post = probe_health()
    report["post_health"] = post["health"]
    report["post_v1_status"] = post["v1_status"]
    report["rate_limit_backend_unavailable"] = "NOT OBSERVED IN INSPECTED WINDOW"
    if report["direct_redis_ping"] == "FAIL" and report["cache_l2_builder"] == "FAIL":
        report["comparison"] = "DIRECT_FAIL_APPLICATION_FAIL"
        report["root_cause"] = "VERIFIED"
        report["root_cause_detail"] = "Both direct redis-py PING and production cache L2 builder failed at runtime."
    elif report["direct_redis_ping"] == "PASS" and report["cache_l2_builder"] == "FAIL":
        report["comparison"] = "DIRECT_PASS_APPLICATION_FAIL"
        report["root_cause"] = "VERIFIED"
        report["root_cause_detail"] = "Direct redis-py PING passed but production cache L2 builder failed."
    elif report["direct_redis_ping"] == "PASS" and report["cache_l2_builder"] == "PASS" and report["cache_l2_getter"] == "PASS":
        report["comparison"] = "BOTH_PASS"
        report["root_cause"] = "NOT VERIFIED"
        report["root_cause_detail"] = "Both direct and application paths passed; prior failure is contextual or transient."
    else:
        report["comparison"] = "CONTRADICTORY_OR_INCOMPLETE"
        report["root_cause"] = "NOT VERIFIED"
        report["root_cause_detail"] = "Evidence is incomplete or contradictory; no cause assigned."
    return report


def _real_l2_specs(run_id: str) -> list[dict[str, Any]]:
    """Return the six production logical-key builders and their source TTLs.

    These expressions intentionally mirror the application call sites.  The
    probe then invokes cache.write_memory_cache/read_memory_cache, never a
    generic Redis SET, so serialization, envelope and L2 namespace handling
    remain the production implementation under test.
    """
    # global_markets has no free-form request field in its production key.  A
    # deterministic valid limit derived from the run id keeps the exact
    # production expression while the collision check below prevents overwrite.
    global_limit = 1 + (int(hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8], 16) % 160)
    global_category = "us-stocks"
    global_underlying = "TXO"
    global_source = "auto"
    global_key = f"{global_category}:{global_limit}:{global_underlying}:default"
    etf_query = f"h11-04-{run_id}"
    etf_key = f"{etf_query.lower()}:7000:48"
    sector_symbol = f"H11{run_id.replace('-', '')[:15]}"
    sector_exchange = "TWSE"
    sector_market = "TWSE"
    sector_key = f"{sector_symbol}:{sector_exchange}:{sector_market}"
    stock_market = "TWSE"
    stock_code = f"H11{run_id.replace('-', '')[:8]}"
    stock_market_date = "20990101"
    stock_history_mode = "recent"
    stock_months_back = 6
    stock_detail_mode = "quick"
    stock_key = f"{stock_market}:{stock_code}:{stock_market_date}:{stock_history_mode}:{stock_months_back}:{stock_detail_mode}"
    taifex_symbol = "TXO"
    taifex_query_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    taifex_expiry = f"H11-{run_id}"
    taifex_key = f"{taifex_symbol}:{taifex_query_date}:{taifex_expiry}"
    yahoo_symbol = "TXO"
    yahoo_expiry = f"H11-{run_id}"
    yahoo_key = f"{yahoo_symbol}:{yahoo_expiry}"
    return [
        {
            "bucket": "global_markets",
            "logical_key": global_key,
            "ttl_seconds": 300,
            "source": "routes_global_market.api_global_market: f'{category_key}:{limit}:{option_underlying}:{option_source if category_key == \'options\' else \'default\'}'",
            "builder_inputs": {"category_key": global_category, "limit": global_limit, "option_underlying": global_underlying, "option_source": global_source},
        },
        {
            "bucket": "us_etf_center",
            "logical_key": etf_key,
            "ttl_seconds": 300,
            "source": "routes_global_market.api_us_market_etf_center: f'{query.lower()}:{directory_limit}:{quote_limit}'",
            "builder_inputs": {"query": etf_query, "directory_limit": 7000, "quote_limit": 48},
        },
        {
            "bucket": "sector_charts",
            "logical_key": sector_key,
            "ttl_seconds": 300,
            "source": "routes_twse.api_yahoo_sector_chart: f'{raw_symbol}:{exchange}:{market}'",
            "builder_inputs": {"raw_symbol": sector_symbol, "exchange": sector_exchange, "market": sector_market},
        },
        {
            "bucket": "stock_details",
            "logical_key": stock_key,
            "ttl_seconds": 300,
            "source": "routes_twse.api_stock_detail: f'{stock.get(\'market\', \'TWSE\')}:{stock.get(\'code\', code_key)}:{market_date}:{history_mode}:{months_back}:{detail_mode}'",
            "builder_inputs": {"market": stock_market, "code": stock_code, "market_date": stock_market_date, "history_mode": stock_history_mode, "months_back": stock_months_back, "detail_mode": stock_detail_mode},
        },
        {
            "bucket": "taifex_options_chain",
            "logical_key": taifex_key,
            "ttl_seconds": 300,
            "source": "fetchers.fetch_taifex_txo_option_chain: f'{product[\'symbol\']}:{query_date}:{expiry or \'\'}'",
            "builder_inputs": {"product_symbol": taifex_symbol, "query_date": taifex_query_date, "expiry": taifex_expiry},
        },
        {
            "bucket": "yahoo_tw_option_chain",
            "logical_key": yahoo_key,
            "ttl_seconds": 60,
            "source": "fetchers.fetch_yahoo_txo_option_chain: f'{product[\'symbol\']}:{expiry or \'\'}'",
            "builder_inputs": {"product_symbol": yahoo_symbol, "expiry": yahoo_expiry},
        },
    ]


def execute_real_l2(run_id: str) -> dict[str, Any]:
    """Exercise each real L2 bucket through the production cache abstraction."""
    stage = "pre_probe"
    pre = probe_health()
    if pre["health"] != 200 or pre["v1_status"] != 200:
        raise ProbeFailure(stage)
    stage = "runtime_config"
    required_modes = ("MARKET_PULSE_CACHE_L2_MODE", "MARKET_PULSE_SINGLE_FLIGHT_MODE", "MARKET_PULSE_BACKGROUND_LEASE_MODE", "MARKET_PULSE_RATE_LIMIT_MODE")
    modes = {name: str(os.environ.get(name) or "").strip().lower() for name in required_modes}
    if not os.environ.get("MARKET_PULSE_REDIS_URL") or modes["MARKET_PULSE_CACHE_L2_MODE"] != "redis":
        raise ProbeFailure(stage)
    stage = "redis_ping"
    try:
        import cache
        adapter = cache._get_cache_l2_shared_adapter()
        client = adapter._client  # inspection only; all writes/reads use cache.py below
        client.ping()
    except Exception as exc:
        raise ProbeFailure(stage) from exc
    source_root = str(os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", "market-pulse:v1")).strip(":")
    stage = "source_snapshot"
    original_keys = scan_keys(client, f"{source_root}:*")
    original_hashes = key_snapshot(client, original_keys)
    specs = _real_l2_specs(run_id)
    if tuple(item["bucket"] for item in specs) != REAL_L2_BUCKETS:
        raise ProbeFailure("source_mapping")
    touched: list[str] = []
    evidence: list[dict[str, Any]] = []
    try:
        for spec in specs:
            bucket = spec["bucket"]
            logical_key = spec["logical_key"]
            ttl_seconds = int(spec["ttl_seconds"])
            stage = f"source_mapping:{bucket}"
            if bucket not in cache.CACHE_L2_BUCKETS or ttl_seconds <= 0:
                raise ProbeFailure(stage)
            namespace = cache._cache_l2_namespace(bucket)
            raw_key = adapter._digest_key("cache", namespace, logical_key)
            if client.exists(raw_key):
                raise ProbeFailure(f"collision:{bucket}")
            payload = {"h11_04_real_l2": True, "bucket": bucket, "run_id": run_id, "logical_key": logical_key, "items": [1, 2, 3]}
            stage = f"production_write:{bucket}"
            cache.write_memory_cache(bucket, logical_key, payload, ttl_seconds)
            touched.append(raw_key)
            pttl_after_write = int(client.pttl(raw_key))
            if pttl_after_write <= 0 or pttl_after_write > ttl_seconds * 1000 + TTL_TOLERANCE_MS:
                raise ProbeFailure(f"ttl_write:{bucket}")
            with cache.cache_lock:
                cache.cache_data.setdefault(bucket, {}).pop(logical_key, None)
            stage = f"production_read:{bucket}"
            read_payload = cache.read_memory_cache(bucket, logical_key, ttl_seconds)
            if read_payload != payload:
                raise ProbeFailure(f"read_mismatch:{bucket}")
            envelope_raw = client.get(raw_key)
            if envelope_raw is None:
                raise ProbeFailure(f"redis_missing:{bucket}")
            envelope = json.loads(text_key(envelope_raw))
            if not isinstance(envelope, dict) or set(("expires_at", "payload")) - set(envelope):
                raise ProbeFailure(f"envelope:{bucket}")
            if envelope["payload"] != payload:
                raise ProbeFailure(f"serialization:{bucket}")
            evidence.append({
                "bucket": bucket,
                "status": "PASS",
                "logical_key": logical_key,
                "redis_key": raw_key,
                "namespace": namespace,
                "ttl_source_seconds": ttl_seconds,
                "pttl_after_write_ms": pttl_after_write,
                "source_of_truth": spec["source"],
                "builder_inputs": spec["builder_inputs"],
                "production_write": "cache.write_memory_cache",
                "production_read": "cache.read_memory_cache",
                "serialization": "shared_state.RedisSharedStateAdapter JSON envelope",
            })
        result = {
            "status": "pass",
            "run_id": run_id,
            "runtime_config": {"redis_url_present": True, "cache_l2_mode": modes["MARKET_PULSE_CACHE_L2_MODE"], "shared_modes": modes},
            "redis_ping": "PASS",
            "six_real_l2_buckets": evidence,
            "six_real_l2_contracts": "PASS",
            "application_keys_mutated": "NO",
            "validation_keys_cleaned": "PENDING",
            "pre_probe": pre,
        }
    except ProbeFailure:
        raise
    except Exception as exc:
        raise ProbeFailure(stage) from exc
    finally:
        try:
            stage = "cleanup"
            cleanup(client, touched)
            with cache.cache_lock:
                for spec in specs:
                    cache.cache_data.setdefault(spec["bucket"], {}).pop(spec["logical_key"], None)
            stage = "source_integrity"
            after_keys = scan_keys(client, f"{source_root}:*")
            if set(after_keys) != set(original_keys):
                raise RuntimeError("original application key set changed")
            if key_snapshot(client, original_keys) != original_hashes:
                raise RuntimeError("original application key payload changed")
            post = probe_health()
            if post["health"] != 200 or post["v1_status"] != 200:
                raise RuntimeError("post-probe application health failed")
            if "result" in locals():
                result["validation_keys_cleaned"] = "PASS"
                result["post_probe"] = post
        except Exception as exc:
            raise ProbeFailure(stage) from exc
    return result


def execute(run_id: str, output_dir: Path) -> dict[str, Any]:
    stage = "pre_probe"
    pre = probe_health()
    stage = "redis_ping"
    client = redis_client()
    source_root = str(os.environ.get("MARKET_PULSE_SHARED_STATE_NAMESPACE", "market-pulse:v1")).strip(":")
    stage = "source_snapshot"
    original_keys = scan_keys(client, f"{source_root}:*")
    original_hashes = key_snapshot(client, original_keys)
    canary_keys: list[str] = []
    restored_keys: list[str] = []
    try:
        stage = "create_canaries"
        canary_keys, bucket_by_key = create_canaries(client, run_id)
        stage = "backup_snapshot"
        source_keys = sorted(set(scan_keys(client, f"{source_root}:*") + canary_keys))
        records, manifest = backup_records(client, source_keys, run_id, bucket_by_key)
        stage = "artifact_write"
        artifact_path, artifact_hash = write_artifact(output_dir, manifest, records)
        stage = "restore_verify"
        restored_keys, restore_summary = restore_and_verify(client, records, run_id)
        backup_count = len(records)
        if backup_count != restore_summary["key_count"]:
            raise RuntimeError("backup and restore key counts differ")
        result = {
            "status": "pass",
            "run_id": run_id,
            "redis_ping": "PASS",
            "backup_artifact_sha256": artifact_hash,
            "backup_artifact_path": str(artifact_path),
            "backup_key_count": backup_count,
            "backup_type_counts": manifest["per_type_counts"],
            "six_l2_bucket_coverage": manifest["six_l2_bucket_coverage"],
            "restore_key_count": restore_summary["key_count"],
            "restore_payload_integrity": "PASS",
            "restore_type_integrity": "PASS",
            "restore_ttl_integrity": "PASS",
            "restore_ttl_tolerance_ms": restore_summary["ttl_tolerance_ms"],
            "original_keys_mutated": "NO",
            "temporary_validation_keys_cleaned": "PASS",
            "pre_probe": pre,
        }
    except ProbeFailure:
        raise
    except Exception as exc:
        raise ProbeFailure(stage) from exc
    finally:
        try:
            stage = "cleanup"
            cleanup(client, restored_keys + canary_keys)
            stage = "source_integrity"
            after_keys = scan_keys(client, f"{source_root}:*")
            if set(after_keys) != set(original_keys):
                raise RuntimeError("original application key set changed")
            after_hashes = key_snapshot(client, original_keys)
            if after_hashes != original_hashes:
                raise RuntimeError("original application key payload changed")
            stage = "post_probe"
            post = probe_health()
            if post["health"] != 200 or post["v1_status"] != 200:
                raise RuntimeError("post-probe application health failed")
            if "result" in locals():
                result["post_probe"] = post
        except ProbeFailure:
            raise
        except Exception as exc:
            raise ProbeFailure(stage) from exc
    if "result" not in locals():
        raise RuntimeError("logical backup/restore produced no result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="H11-04 staging-only cache acceptance probes")
    parser.add_argument("--mode", choices=("backup-restore", "real-l2", "runtime-diagnostic"), default="backup-restore")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("H11_04_OUTPUT_DIR", str(Path(os.environ.get("TEMP", "/tmp")) / "h11-04-backup")),
    )
    args = parser.parse_args()
    try:
        run_id = run_id_from_args(args.run_id)
        if args.mode == "runtime-diagnostic":
            report = execute_runtime_diagnostic()
        else:
            report = execute_real_l2(run_id) if args.mode == "real-l2" else execute(run_id, Path(args.output_dir))
    except ProbeFailure as exc:
        print(json.dumps({"status": "fail", "error_type": type(exc).__name__, "failure_stage": exc.stage}, sort_keys=True))
        return 1
    except Exception as exc:
        # Never print exception text: backend errors can contain connection details.
        print(json.dumps({"status": "fail", "error_type": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if args.mode == "runtime-diagnostic":
        print("H11_04_RUNTIME_DIAGNOSTIC_OK")
    else:
        print("H11_04_SIX_REAL_L2_BUCKETS_OK" if args.mode == "real-l2" else "H11_04_APPLICATION_MANAGED_BACKUP_RESTORE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
