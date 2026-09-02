"""Close TD15-REMAIN-07 after the final CSS deletion-candidate audit.

This gate reconciles the REMAIN-05 and REMAIN-06 review queues against the
REMAIN-01 source and current CSS identities.  When no block is a deletion
candidate, the authorized action is an explicit no-op closure: no CSS rule,
baseline, or runtime data is edited.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "regression"
SNAPSHOT_DATE = "2026-09-01"
SOURCE_JSON = ROOT / "docs" / "TD15_REMAIN_01_css_rebaseline_2026-09-01.json"
INVENTORY_JSON = ROOT / "docs" / "TD15_residual_inventory_2026-09-01.json"
REMAIN_04_JSON = ROOT / "docs" / "TD15_REMAIN_04_review_manifest_2026-09-01.json"
REMAIN_05_JSON = ROOT / "docs" / "TD15_REMAIN_05_review_manifest_2026-09-01.json"
REMAIN_06_JSON = ROOT / "docs" / "TD15_REMAIN_06_review_manifest_2026-09-01.json"
OUTPUT_JSON = ROOT / "docs" / "TD15_REMAIN_07_closure_manifest_2026-09-01.json"
OUTPUT_MD = ROOT / "docs" / "TD15_REMAIN_07_evidence_2026-09-01.md"
EXPECTED_BLOCKS = 263
PACKET_LIMIT = 20
OWNER_ROLE = "TD15-CSS-review-owner"
ALLOWED_DISPOSITIONS = {"retain", "observe", "delete_candidate", "blocked"}


class ClosureFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ClosureFailure(message)


def read_json(path: Path) -> dict:
    require(path.is_file(), f"missing required artifact: {path.relative_to(ROOT)}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), f"expected JSON object: {path.relative_to(ROOT)}")
    return value


def identity(item: dict) -> tuple[str, int, int, str]:
    exact = item.get("exact_identity", item)
    return (
        str(exact.get("file", "")),
        int(exact.get("startLine", 0)),
        int(exact.get("endLine", 0)),
        str(exact.get("sha256", "")),
    )


def identity_dict(item: dict) -> dict:
    exact = item.get("exact_identity", item)
    return {
        "file": str(exact.get("file", "")),
        "startLine": int(exact.get("startLine", 0)),
        "endLine": int(exact.get("endLine", 0)),
        "selector": str(exact.get("selector", "")),
        "sha256": str(exact.get("sha256", "")),
    }


def load_current_css_blocks() -> dict[tuple[str, int, int, str], dict]:
    sys.path.insert(0, str(REGRESSION))
    from td15_residual_inventory import css_paths, flatten_rules, sha256_bytes

    blocks: dict[tuple[str, int, int, str], dict] = {}
    for path in css_paths():
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        relative = path.relative_to(ROOT).as_posix()
        for parsed in flatten_rules(text):
            start = parsed["start"]
            end = parsed["end"]
            block = {
                "file": relative,
                "startLine": text.count("\n", 0, start) + 1,
                "endLine": text.count("\n", 0, end - 1) + 1,
                "selector": parsed["header"],
                "context": parsed["context"],
                "sha256": sha256_bytes(text[start:end].encode("utf-8")),
            }
            blocks[identity(block)] = block
    return blocks


def source_hashes() -> dict[str, dict]:
    hashes = {}
    sys.path.insert(0, str(REGRESSION))
    from td15_residual_inventory import css_paths, sha256_bytes

    for path in css_paths():
        raw = path.read_bytes()
        hashes[path.relative_to(ROOT).as_posix()] = {
            "bytes": len(raw),
            "sha256": sha256_bytes(raw),
        }
    return hashes


def validate_review_manifest(manifest: dict, batch: str, expected: int) -> list[dict]:
    require(manifest.get("batch") == batch, f"input is not the {batch} manifest")
    require(manifest.get("snapshot_date") == SNAPSHOT_DATE, f"{batch} snapshot date mismatch")
    require(manifest.get("authorization", {}).get("deletion_authorized") is False, f"{batch} authorizes deletion")
    scope = manifest.get("scope", {})
    require(scope.get("css_rule_blocks") == expected, f"{batch} scope mismatch")
    require(scope.get("frontend_pages") == 21, f"{batch} frontend page scope mismatch")
    require(scope.get("interaction_steps") == 94, f"{batch} interaction scope mismatch")
    reviews = manifest.get("reviews", [])
    require(len(reviews) == expected, f"{batch} review count mismatch")
    for item in reviews:
        exact = item.get("exact_identity")
        require(isinstance(exact, dict), f"{batch} review lacks exact identity")
        require(all(exact.get(key) for key in ("file", "selector", "sha256")), f"{batch} review identity incomplete")
        require(int(exact.get("startLine", 0)) > 0 and int(exact.get("endLine", 0)) >= int(exact["startLine"]), f"{batch} review line identity invalid")
        require(item.get("deletion_authorized") is False, f"{batch} review authorizes deletion")
        require(item.get("disposition") in ALLOWED_DISPOSITIONS, f"{batch} has invalid disposition")
        require(item.get("responsible_role") == OWNER_ROLE, f"{batch} review owner mismatch")
    return reviews


def packet_summary(manifest: dict) -> list[dict]:
    packets = []
    for packet in manifest.get("packets", []):
        count = int(packet.get("block_count", 0))
        require(0 < count <= PACKET_LIMIT, f"packet exceeds {PACKET_LIMIT}: {packet.get('packet_id')}")
        require(count == len(packet.get("review_ids", [])), f"packet review count mismatch: {packet.get('packet_id')}")
        packets.append({
            "packet_id": packet.get("packet_id"),
            "category": packet.get("category"),
            "block_count": count,
            "responsible_role": packet.get("responsible_role"),
            "disposition_set": sorted(packet.get("disposition_set", [])),
        })
    return packets


def compact_review(item: dict, batch: str, sequence: int) -> dict:
    exact = identity_dict(item)
    return {
        "review_id": f"TD15-REMAIN-07-{sequence:03d}",
        "upstream_batch": batch,
        "upstream_review_id": item.get("review_id"),
        "packet_id": item.get("packet_id"),
        "exact_identity": exact,
        "candidate_classes": sorted(item.get("candidate_classes", [])),
        "final_disposition": item.get("disposition"),
        "decision_reason": item.get("decision_reason", ""),
        "responsible_role": item.get("responsible_role"),
    }


def build_closure() -> dict:
    source = read_json(SOURCE_JSON)
    inventory = read_json(INVENTORY_JSON)
    remain_04 = read_json(REMAIN_04_JSON)
    remain_05 = read_json(REMAIN_05_JSON)
    remain_06 = read_json(REMAIN_06_JSON)

    require(source.get("snapshot_date") == SNAPSHOT_DATE, "REMAIN-01 snapshot date mismatch")
    source_blocks = source.get("rule_blocks", [])
    source_by_identity = {identity(block): block for block in source_blocks}
    require(len(source_blocks) == EXPECTED_BLOCKS, "REMAIN-01 source block count is not 263")
    require(len(source_by_identity) == EXPECTED_BLOCKS, "REMAIN-01 source identities are not unique")
    require(inventory.get("current_state", {}).get("candidate_bearing_rule_blocks") == EXPECTED_BLOCKS, "R0 candidate block count mismatch")

    require(remain_04.get("scope", {}).get("css_rule_blocks") == EXPECTED_BLOCKS, "REMAIN-04 scope mismatch")
    require(remain_04.get("authorization", {}).get("deletion_authorized") is False, "REMAIN-04 authorizes deletion")
    reviews_05 = validate_review_manifest(remain_05, "TD15-REMAIN-05", 65)
    reviews_06 = validate_review_manifest(remain_06, "TD15-REMAIN-06", 198)
    packets = packet_summary(remain_05) + packet_summary(remain_06)
    require(len(packets) == 14, "expected 14 review packets")

    all_reviews = [("TD15-REMAIN-05", item) for item in reviews_05] + [("TD15-REMAIN-06", item) for item in reviews_06]
    review_identities = [identity(item) for _, item in all_reviews]
    require(len(set(review_identities)) == EXPECTED_BLOCKS, "final review identities are not unique")
    require(set(review_identities) == set(source_by_identity), "final review identities do not match REMAIN-01 source")
    for batch, item in all_reviews:
        key = identity(item)
        require(item.get("exact_identity", {}).get("selector") == source_by_identity[key].get("selector"), f"selector mismatch in {batch} {item.get('review_id')}")

    current_blocks = load_current_css_blocks()
    current_source_identity_set = set(current_blocks).intersection(source_by_identity)
    require(current_source_identity_set == set(source_by_identity), "current CSS no longer matches source identity set")
    current_hashes = source_hashes()
    recorded_hashes = inventory.get("current_state", {}).get("css_source_hashes", {})
    require(current_hashes == recorded_hashes, "CSS source hashes changed since R0")

    disposition_counts = {name: 0 for name in sorted(ALLOWED_DISPOSITIONS)}
    compact_reviews = []
    for sequence, (batch, item) in enumerate(sorted(all_reviews, key=lambda pair: identity(pair[1])), 1):
        disposition = item["disposition"]
        disposition_counts[disposition] += 1
        compact_reviews.append(compact_review(item, batch, sequence))
    require(sum(disposition_counts.values()) == EXPECTED_BLOCKS, "final disposition total mismatch")
    require(disposition_counts["delete_candidate"] == 0, "delete candidates remain; closure must not be no-op")
    require(disposition_counts["blocked"] == 0, "blocked reviews remain; closure is not safe")
    require(disposition_counts["retain"] == EXPECTED_BLOCKS, "not all reviewed blocks are retained")

    return {
        "schema_version": 1,
        "batch": "TD15-REMAIN-07",
        "snapshot_date": SNAPSHOT_DATE,
        "status": "TD15_REMAIN_07_PASS_NO_DELETION",
        "inputs": [
            "docs/TD15_residual_inventory_2026-09-01.json",
            "docs/TD15_REMAIN_01_css_rebaseline_2026-09-01.json",
            "docs/TD15_REMAIN_04_review_manifest_2026-09-01.json",
            "docs/TD15_REMAIN_05_review_manifest_2026-09-01.json",
            "docs/TD15_REMAIN_06_review_manifest_2026-09-01.json",
        ],
        "scope": {
            "css_rule_blocks": EXPECTED_BLOCKS,
            "final_reviews": EXPECTED_BLOCKS,
            "frontend_pages": 21,
            "interaction_steps": 94,
            "review_packets": len(packets),
            "packet_limit": PACKET_LIMIT,
        },
        "disposition_counts": disposition_counts,
        "closure": {
            "deletion_executed": False,
            "deletion_batch_count": 0,
            "reverse_diff_required": False,
            "reason": "REMAIN-05/06 produced no delete candidates; all 263 blocks retain.",
            "css_source_hashes_unchanged": True,
            "final_identity_set_matches_source": True,
            "baseline_changed": False,
            "runtime_data_modified": False,
            "owner": OWNER_ROLE,
        },
        "source_hashes": current_hashes,
        "packets": packets,
        "reviews": compact_reviews,
    }


def selector_inline(selector: str) -> str:
    return " ".join(selector.split()).replace("|", "\\|")


def markdown_report(closure: dict) -> str:
    counts = closure["disposition_counts"]
    lines = [
        "# TD15-REMAIN-07 closure evidence（2026-09-01）",
        "",
        "本批依授權執行最終 CSS residual closure。REMAIN-05 的 65 個 grouped／compound／responsive／state blocks 與 REMAIN-06 的 198 個 dynamic／status／direct-reference blocks 均完成核對；沒有任何 `delete_candidate`，因此本批採 no-op closure。",
        "",
        "## 結論",
        "",
        f"- 狀態：`{closure['status']}`。最終對帳 {closure['scope']['final_reviews']}/{closure['scope']['css_rule_blocks']} 個 rule blocks。",
        f"- disposition：retain={counts['retain']}、observe={counts['observe']}、delete_candidate={counts['delete_candidate']}、blocked={counts['blocked']}。",
        "- 未執行 CSS 刪除、未產生 reverse diff，亦未修改 HTML／JS、baseline 或 runtime data。",
        "- REMAIN-01 source identity set 與目前 CSS 完全一致；9 個 CSS source hash 完全一致。",
        "",
        "## Review packets",
        "",
        "| packet | category | blocks | disposition | owner |",
        "|---|---|---:|---|---|",
    ]
    for packet in closure["packets"]:
        dispositions = ", ".join(packet["disposition_set"])
        lines.append(f"| `{packet['packet_id']}` | {packet['category']} | {packet['block_count']} | `{dispositions}` | `{packet['responsible_role']}` |")
    lines.extend([
        "",
        "## Final block ledger",
        "",
        "每筆均保留 upstream review 的 exact file／line／selector／SHA-256 identity 與決策理由；完整 evidence 仍見 REMAIN-05／06 manifest。",
        "",
        "| closure id | upstream | packet | current identity | disposition | reason |",
        "|---|---|---|---|---|---|",
    ])
    for item in closure["reviews"]:
        exact = item["exact_identity"]
        location = f"`{exact['file']}:{exact['startLine']}-{exact['endLine']}` / `{exact['sha256']}`"
        reason = item["decision_reason"].replace("|", "\\|")
        lines.append(f"| `{item['review_id']}` | `{item['upstream_review_id']}` | `{item['packet_id']}` | {location} / `{selector_inline(exact['selector'])}` | `{item['final_disposition']}` | {reason} |")
    lines.extend([
        "",
        "## Verification boundary",
        "",
        "本 closure gate 只確認 review queue 已關閉且無可安全刪除項目；若未來出現新的 deletion candidate，必須另開不超過 20 個 rule blocks 的刪除批次，保留刪除前 exact identity、reverse diff、六層驗證與獨立紀錄。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write JSON and Markdown closure evidence")
    parser.add_argument("--check", action="store_true", help="rebuild and validate closure evidence")
    args = parser.parse_args()
    try:
        date.fromisoformat(SNAPSHOT_DATE)
        closure = build_closure()
        if args.write:
            OUTPUT_JSON.write_text(json.dumps(closure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
            OUTPUT_MD.write_text(markdown_report(closure), encoding="utf-8", newline="")
        print(
            "TD15_REMAIN_07_OK: "
            f"blocks={closure['scope']['css_rule_blocks']} "
            f"final_reviews={closure['scope']['final_reviews']} "
            f"retain={closure['disposition_counts']['retain']} "
            f"observe={closure['disposition_counts']['observe']} "
            f"delete_candidate={closure['disposition_counts']['delete_candidate']} "
            f"blocked={closure['disposition_counts']['blocked']} "
            f"deletion_executed={str(closure['closure']['deletion_executed']).lower()}"
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError, ClosureFailure) as exc:
        print(f"TD15_REMAIN_07_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
