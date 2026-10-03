"""Build deterministic, non-authoritative P2-03 Amendment 002 closure hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import OrderedDict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DEFAULT = ROOT / ".tmp" / "p203-formal-closure"
DB_PATH = ROOT / "data" / "p203-prospective-ledger.sqlite3"
EXPECTED = {
    "originalProtocol": "0ab04d326962a48439f0a762f5967d0268d8137fae6e26e07db5c7ca39c55290",
    "amendment001": "80ae6beafeeebc68776249625162d6a18736cd1c91981708b71c9dbda852ae0a",
    "originalManifest": "9fbfd8cfe02bd47ace7893161bb6a5c1b6e9cba8639c6063c174cd91ef018ffb",
    "effectiveIdentity001": "f229f03eb3d931aae96d1e994cb8725f8a73676132632da28c94cc9e4d8fcafc",
    "series": "90ca05e0472b09ba3f67e641dae16f8ed9ad310fc87d056e7fd2c3e0baa1c48f",
    "selectionTrace": "a1f5bfd250f1cb94f09a7324f5314686fc29e298cde649a26dd4f817e11e251a",
    "database": "73db5d58f9cc1b2f5723ddbb86678036a6e5c67d322cf492d3b2d0f4d2f23df4",
}
RELEVANT_FILES = (
    "docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md",
    "docs/P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md",
    "docs/P2_03_PROTOCOL_AMENDMENT_002.md",
    "docs/P2_03_FORMAL_CLOSURE.md",
    "docs/INVESTMENT_DECISION_EXECUTION_STATUS.md",
    "scripts/p203_roll_continuity_feasibility_audit.py",
    "scripts/p203_v2_historical_development.py",
    "scripts/p203_prospective_evidence_runner.py",
    "derivatives/probability_forecast.py",
    "regression/test_fetch_registry_bom.py",
    "regression/test_p0a_market_time_integrity.py",
    "regression/test_p203_source_provenance.py",
    "regression/test_p203_prospective_evidence_runner.py",
    "regression/test_p203_v2_historical_development.py",
    "regression/test_p203_amendment_002_closure.py",
    "regression/test_p2_02_outcome_evaluation.py",
    "regression/test_p2_03_probability_forecast.py",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(relative: str) -> str:
    return sha256((ROOT / relative).read_bytes())


def build_identity() -> tuple[dict[str, Any], bytes, str]:
    original_hash = sha256_file("docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md")
    amendment001_hash = sha256_file("docs/P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md")
    amendment002_hash = sha256_file("docs/P2_03_PROTOCOL_AMENDMENT_002.md")
    original_manifest_hash = sha256_file(".tmp/p203-v2-protocol/protocol_manifest.json")
    identity001_hash = sha256_file(".tmp/p203-v2-protocol/effective_protocol_identity.json")
    observed = {
        "originalProtocol": original_hash,
        "amendment001": amendment001_hash,
        "originalManifest": original_manifest_hash,
        "effectiveIdentity001": identity001_hash,
    }
    if observed != {key: EXPECTED[key] for key in observed}:
        raise ValueError(f"frozen protocol identity mismatch: {observed}")

    identity = OrderedDict([
        ("identityVersion", "P2-03-EFFECTIVE-PROTOCOL-IDENTITY-2"),
        ("status", "FORMALLY_APPROVED_BY_PROJECT_OWNER"),
        ("effectiveVersion", "P2-03-RESEARCH-V2-PRE-REGISTRATION-1.0+AMENDMENT-001+AMENDMENT-002"),
        ("effectiveProtocol", "ORIGINAL_PROTOCOL_PLUS_AMENDMENT_001_PLUS_AMENDMENT_002"),
        ("originalProtocolPath", "docs/P2_03_RESEARCH_V2_PRE_REGISTRATION.md"),
        ("originalProtocolSha256", original_hash),
        ("originalFrozenManifestPath", ".tmp/p203-v2-protocol/protocol_manifest.json"),
        ("originalFrozenManifestSha256", original_manifest_hash),
        ("amendment001Id", "P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001"),
        ("amendment001Path", "docs/P2_03_RESEARCH_V2_PROTOCOL_AMENDMENT_001.md"),
        ("amendment001Sha256", amendment001_hash),
        ("priorEffectiveIdentityPath", ".tmp/p203-v2-protocol/effective_protocol_identity.json"),
        ("priorEffectiveIdentitySha256", identity001_hash),
        ("amendment002Id", "P2_03_PROTOCOL_AMENDMENT_002"),
        ("amendment002Path", "docs/P2_03_PROTOCOL_AMENDMENT_002.md"),
        ("amendment002Sha256", amendment002_hash),
        ("approvalProvenance", OrderedDict([
            ("authority", "PROJECT_OWNER"),
            ("decision", "FORMALLY_APPROVED"),
            ("authorization", "P2-03 — FINAL SIMPLIFICATION + AMENDMENT 002 + FORMAL CLOSURE"),
            ("date", "2026-10-02"),
        ])),
    ])
    payload = (json.dumps(identity, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return identity, payload, sha256(payload)


def database_snapshot() -> dict[str, Any]:
    uri = DB_PATH.resolve().as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        counts = {
            "decision_ledger": int(connection.execute("SELECT COUNT(*) FROM decision_ledger").fetchone()[0]),
            "decision_outcome": int(connection.execute("SELECT COUNT(*) FROM decision_outcome").fetchone()[0]),
        }
    digest = sha256_file("data/p203-prospective-ledger.sqlite3")
    if digest != EXPECTED["database"] or counts != {"decision_ledger": 1, "decision_outcome": 0}:
        raise ValueError(f"authoritative prospective database baseline mismatch: {digest} {counts}")
    return {"sha256": digest, "counts": counts, "inspection": "READ_ONLY_IMMUTABLE"}


def build_manifest(identity_hash: str) -> dict[str, Any]:
    file_hashes = {relative: sha256_file(relative) for relative in RELEVANT_FILES}
    historical_inputs = {
        ".tmp/p203-historical-research-v1r1/rebuilt_daily_series.csv": sha256_file(
            ".tmp/p203-historical-research-v1r1/rebuilt_daily_series.csv"
        ),
        ".tmp/p203-historical-research-v1r1/selection_trace.csv": sha256_file(
            ".tmp/p203-historical-research-v1r1/selection_trace.csv"
        ),
    }
    if historical_inputs[next(iter(historical_inputs))] != EXPECTED["series"]:
        raise ValueError("frozen historical selected series hash drift")
    if historical_inputs[list(historical_inputs)[1]] != EXPECTED["selectionTrace"]:
        raise ValueError("frozen historical selection trace hash drift")
    return {
        "manifestVersion": "P2-03-FORMAL-CLOSURE-MANIFEST-1",
        "classification": "LOCAL_GOVERNANCE_CLOSURE_EVIDENCE_NOT_MODEL_VALIDATION",
        "protocolHashes": {
            "originalProtocol": EXPECTED["originalProtocol"],
            "amendment001": EXPECTED["amendment001"],
            "amendment002": file_hashes["docs/P2_03_PROTOCOL_AMENDMENT_002.md"],
            "priorEffectiveIdentity001": EXPECTED["effectiveIdentity001"],
            "newEffectiveIdentity": identity_hash,
        },
        "historicalFrozenInputs": historical_inputs,
        "relevantFileSha256": file_hashes,
        "authoritativeProspectiveDb": database_snapshot(),
        "historicalEvidence": {"selectedSessions": 441, "eligibleLabels": 19, "forecasts": 0, "oosPairs": 0},
        "prospectiveEvidence": {"eligibleMaturedLabels": 0, "persistedForecasts": 0, "validOosPairs": 0,
                                "probabilityLabelAllowed": False},
        "closureStatus": "P2-03_CLOSED_ONLY_AS_ENGINEERING_AND_GOVERNANCE_COMPLETION",
        "nonClaims": [
            "historical_predictive_validity", "prospective_predictive_validity", "positive_brier_skill_score",
            "auc_above_0_5", "calibration_quality", "profitability", "probability_label_approval",
            "production_trading_edge",
        ],
    }


def generate(output_dir: Path) -> dict[str, str]:
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite closure-manifest artifacts: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    _, identity_payload, identity_hash = build_identity()
    manifest = build_manifest(identity_hash)
    manifest_payload = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output_dir / "effective_protocol_identity_amendment_002.json").write_bytes(identity_payload)
    (output_dir / "manifest.json").write_bytes(manifest_payload)
    return {"identitySha256": identity_hash, "manifestSha256": sha256(manifest_payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DEFAULT)
    args = parser.parse_args()
    print(json.dumps(generate(args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
