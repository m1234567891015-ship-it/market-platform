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
    parser = argparse.ArgumentParser(description="H11-04 free-tier logical backup/restore acceptance")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("H11_04_OUTPUT_DIR", str(Path(os.environ.get("TEMP", "/tmp")) / "h11-04-backup")),
    )
    args = parser.parse_args()
    try:
        report = execute(run_id_from_args(args.run_id), Path(args.output_dir))
    except ProbeFailure as exc:
        print(json.dumps({"status": "fail", "error_type": type(exc).__name__, "failure_stage": exc.stage}, sort_keys=True))
        return 1
    except Exception as exc:
        # Never print exception text: backend errors can contain connection details.
        print(json.dumps({"status": "fail", "error_type": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    print("H11_04_APPLICATION_MANAGED_BACKUP_RESTORE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
