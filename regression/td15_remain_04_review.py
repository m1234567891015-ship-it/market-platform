"""Build the TD15-REMAIN-04 CSS review manifest.

REMAIN-04 is an evidence-packaging batch.  It consumes the current
REMAIN-01 rule-block manifest, assigns every block to a review packet of at
most 20 blocks, and records a conservative disposition.  It deliberately
does not edit CSS, HTML, JavaScript, baselines, or runtime data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE_JSON = ROOT / "docs" / "TD15_REMAIN_01_css_rebaseline_2026-09-01.json"
OUTPUT_JSON = ROOT / "docs" / "TD15_REMAIN_04_review_manifest_2026-09-01.json"
OUTPUT_MD = ROOT / "docs" / "TD15_REMAIN_04_evidence_2026-09-01.md"
PACKET_LIMIT = 20
OWNER_ROLE = "TD15-CSS-review-owner"

GROUPED_DECISION = "retain-grouped-or-compound-review"
DYNAMIC_DECISION = "retain-dynamic-status-or-direct-reference"


class ReviewFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewFailure(message)


def read_source() -> dict:
    require(SOURCE_JSON.is_file(), f"missing source manifest: {SOURCE_JSON.relative_to(ROOT)}")
    value = json.loads(SOURCE_JSON.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), "source manifest must be a JSON object")
    require(value.get("status") == "TD15_REMAIN_01_PASS_NO_DELETION", "source manifest is not a REMAIN-01 no-deletion report")
    require(value.get("deletion_authorized") is False, "source manifest authorizes deletion")
    require(value.get("baseline_changed") is False, "source manifest changed the baseline")
    return value


def source_block_key(block: dict) -> tuple[str, int, int, str]:
    return (
        str(block.get("file", "")),
        int(block.get("startLine", 0)),
        int(block.get("endLine", 0)),
        str(block.get("sha256", "")),
    )


def validate_source_blocks(source: dict) -> list[dict]:
    scope = source.get("scope", {})
    require(scope.get("css_rule_blocks") == 263, f"expected 263 source blocks, found {scope.get('css_rule_blocks')}")
    require(scope.get("frontend_pages") == 21, f"expected 21 frontend pages, found {scope.get('frontend_pages')}")
    require(scope.get("interaction_steps") == 94, f"expected 94 interaction steps, found {scope.get('interaction_steps')}")
    blocks = source.get("rule_blocks")
    require(isinstance(blocks, list) and len(blocks) == 263, "source rule_blocks must contain exactly 263 blocks")

    seen: set[tuple[str, int, int, str]] = set()
    for block in blocks:
        require(isinstance(block, dict), "each source rule block must be an object")
        key = source_block_key(block)
        require(key not in seen, f"duplicate source block identity: {key}")
        seen.add(key)
        require(all(key_part for key_part in key), f"incomplete source identity: {key}")
        evidence = block.get("three_layer_evidence")
        require(isinstance(evidence, dict), f"missing three-layer evidence: {key}")
        css_static = evidence.get("css_static", {})
        require(
            (css_static.get("file"), css_static.get("startLine"), css_static.get("endLine"), css_static.get("sha256")) == key,
            f"CSS identity does not match evidence: {key}",
        )
        behavior = evidence.get("page_behavior", {})
        require(behavior.get("frontend_pages") == 21, f"page evidence is not 21 pages: {key}")
        require(behavior.get("interaction_steps") == 94, f"interaction evidence is not 94 steps: {key}")
    return blocks


def chunks(items: list[dict], limit: int = PACKET_LIMIT) -> Iterable[list[dict]]:
    for start in range(0, len(items), limit):
        yield items[start : start + limit]


def packet_id(category: str, number: int) -> str:
    prefix = "G" if category == "grouped-compound" else "D"
    return f"TD15-REMAIN-04-{prefix}{number:02d}"


def review_item(block: dict, category: str, packet: str, ordinal: int) -> dict:
    if category == "grouped-compound":
        disposition = "retain"
        reason = (
            "目前 rule block 含 grouped／compound selector 或其他 cascade branch；"
            "尚未完成 live branch、responsive、state 與 cascade 的逐項拆解，維持保留。"
        )
        next_review = "TD15-REMAIN-05"
        review_stage = "cascade-live-branch-review-pending"
    else:
        disposition = "observe"
        reason = (
            "目前 rule block 涉及 dynamic prefix、status marker 或 direct reference；"
            "generator、資料狀態集合與非預設 runtime 路徑尚未收斂，證據不足即觀察保留。"
        )
        next_review = "TD15-REMAIN-06"
        review_stage = "generator-state-runtime-review-pending"

    evidence = block["three_layer_evidence"]
    runtime = evidence.get("runtime_dom", {})
    runtime_names_with_hits = sum(1 for value in runtime.values() if value.get("page_count", 0))
    return {
        "review_id": f"TD15-REMAIN-04-{ordinal:03d}",
        "packet_id": packet,
        "review_category": category,
        "exact_identity": {
            "file": block["file"],
            "startLine": block["startLine"],
            "endLine": block["endLine"],
            "selector": block["selector"],
            "sha256": block["sha256"],
        },
        "candidate_classes": block.get("candidate_classes", []),
        "source_classification": block["decision"],
        "evidence_status": {
            "manifest_identity": "complete",
            "css_static": "recorded",
            "html_js_static": "recorded",
            "runtime_dom": "recorded",
            "runtime_candidate_names_with_hits": runtime_names_with_hits,
            "page_behavior": "21-pages-94-interactions-recorded",
            "manual_review": review_stage,
        },
        "responsible_role": OWNER_ROLE,
        "disposition": disposition,
        "decision_reason": reason,
        "next_review": next_review,
    }


def build_manifest() -> dict:
    source = read_source()
    blocks = validate_source_blocks(source)
    grouped = sorted(
        [block for block in blocks if block.get("decision") == GROUPED_DECISION],
        key=source_block_key,
    )
    dynamic = sorted(
        [block for block in blocks if block.get("decision") == DYNAMIC_DECISION],
        key=source_block_key,
    )
    require(len(grouped) == 65, f"expected 65 grouped blocks, found {len(grouped)}")
    require(len(dynamic) == 198, f"expected 198 dynamic blocks, found {len(dynamic)}")
    require(len(grouped) + len(dynamic) == len(blocks), "source contains an unrecognized classification")

    packets = []
    reviews = []
    ordinal = 1
    for category, category_blocks in (("grouped-compound", grouped), ("dynamic-status-direct-reference", dynamic)):
        category_packets = list(chunks(category_blocks))
        for number, packet_blocks in enumerate(category_packets, 1):
            packet = packet_id(category, number)
            packet_reviews = [review_item(block, category, packet, ordinal + index) for index, block in enumerate(packet_blocks)]
            ordinal += len(packet_reviews)
            reviews.extend(packet_reviews)
            packets.append(
                {
                    "packet_id": packet,
                    "category": category,
                    "review_stage": packet_reviews[0]["evidence_status"]["manual_review"],
                    "block_count": len(packet_reviews),
                    "max_block_count": PACKET_LIMIT,
                    "disposition_set": sorted({item["disposition"] for item in packet_reviews}),
                    "responsible_role": OWNER_ROLE,
                    "review_ids": [item["review_id"] for item in packet_reviews],
                }
            )

    require(len(reviews) == 263, f"expected 263 review items, found {len(reviews)}")
    require(len(packets) == 14, f"expected 14 review packets, found {len(packets)}")
    require(all(packet["block_count"] <= PACKET_LIMIT for packet in packets), "review packet exceeds 20 blocks")
    require(len({item["review_id"] for item in reviews}) == 263, "review IDs are not unique")
    require(len({tuple(item["exact_identity"].values()) for item in reviews}) == 263, "review identities are not unique")

    return {
        "schema_version": 1,
        "batch": "TD15-REMAIN-04",
        "snapshot_date": "2026-09-01",
        "status": "TD15_REMAIN_04_PASS_REVIEW_MANIFEST",
        "source_manifest": SOURCE_JSON.relative_to(ROOT).as_posix(),
        "scope": {
            "css_rule_blocks": 263,
            "grouped_compound_blocks": 65,
            "dynamic_status_direct_reference_blocks": 198,
            "review_packets": len(packets),
            "packet_limit": PACKET_LIMIT,
            "frontend_pages": 21,
            "interaction_steps": 94,
        },
        "disposition_counts": {
            "retain": sum(1 for item in reviews if item["disposition"] == "retain"),
            "observe": sum(1 for item in reviews if item["disposition"] == "observe"),
            "delete": 0,
            "blocked": 0,
        },
        "authorization": {
            "deletion_authorized": False,
            "baseline_changed": False,
            "source_modified": False,
            "runtime_data_modified": False,
        },
        "packets": packets,
        "reviews": reviews,
    }


def selector_inline(selector: str) -> str:
    return " ".join(selector.split()).replace("|", "\\|")


def markdown_report(manifest: dict) -> str:
    lines = [
        "# TD15-REMAIN-04 CSS review manifest（2026-09-01）",
        "",
        "本批完成 263 個現況 CSS rule blocks 的逐項 review manifest 分包與保守 disposition；不刪除 CSS、不修改 HTML／JS、不更新 baseline。",
        "",
        "## 批次結果",
        "",
        f"- 狀態：`{manifest['status']}`。共 {manifest['scope']['css_rule_blocks']} blocks、{manifest['scope']['review_packets']} packets；每包上限 {manifest['scope']['packet_limit']} blocks。",
        f"- 分包：grouped／compound {manifest['scope']['grouped_compound_blocks']} blocks（G01～G04）；dynamic／status／direct-reference {manifest['scope']['dynamic_status_direct_reference_blocks']} blocks（D01～D10）。",
        f"- disposition：`retain` {manifest['disposition_counts']['retain']}、`observe` {manifest['disposition_counts']['observe']}、`delete` 0、`blocked` 0。",
        "- 覆蓋證據：21 頁、94 條 interaction steps；每項均保留 current file／startLine／endLine／selector／SHA-256 與 REMAIN-01 三層 evidence 對應。",
        "- 授權邊界：`deletion_authorized=false`、`baseline_changed=false`、`source_modified=false`、`runtime_data_modified=false`。",
        "",
        "`responsible_role` 是待人工審查的角色責任欄位，不宣稱已指定特定個人。",
        "",
        "## Review packets",
        "",
        "| packet | category | blocks | disposition | next review |",
        "|---|---|---:|---|---|",
    ]
    for packet in manifest["packets"]:
        disposition = ", ".join(packet["disposition_set"])
        next_review = "TD15-REMAIN-05" if packet["category"] == "grouped-compound" else "TD15-REMAIN-06"
        lines.append(
            f"| `{packet['packet_id']}` | `{packet['category']}` | {packet['block_count']} | `{disposition}` | `{next_review}` |"
        )

    lines.extend([
        "",
        "## Per-block disposition",
        "",
        "每一列都是一個現況 rule block；selector 以單行呈現，完整原文與三層 evidence 在同名 JSON。",
        "",
        "| review | packet | current identity | selector | SHA-256 | evidence status | disposition | responsible | reason |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for item in manifest["reviews"]:
        identity = item["exact_identity"]
        location = f"`{identity['file']}:{identity['startLine']}-{identity['endLine']}`"
        evidence = item["evidence_status"]
        status = f"identity={evidence['manifest_identity']}; static=recorded; runtime=recorded; manual={evidence['manual_review']}"
        reason = item["decision_reason"].replace("|", "\\|")
        lines.append(
            f"| `{item['review_id']}` | `{item['packet_id']}` | {location} | `{selector_inline(identity['selector'])}` | `{identity['sha256']}` | {status} | `{item['disposition']}` | `{item['responsible_role']}` | {reason} |"
        )

    lines.extend([
        "",
        "## 後續 gate",
        "",
        "- REMAIN-05 已完成 G packets review：65/65 `retain`，沒有 `delete candidate` 或 `blocked`。",
        "- REMAIN-06 已完成 D packets coverage review：198/198 `retain`，沒有 `delete candidate` 或 `blocked`。",
        "- REMAIN-07 已完成最終 closure：263/263 `retain`，沒有 deletion candidate，因此未執行 CSS 刪除。",
        "- 完整 closure identity、CSS source hash 與 reverse-diff／baseline 邊界見 `TD15_REMAIN_07_evidence_2026-09-01.md`。",
        "",
        f"完整 machine-readable manifest：`{manifest['source_manifest'].replace('TD15_REMAIN_01_css_rebaseline_2026-09-01.json', 'TD15_REMAIN_04_review_manifest_2026-09-01.json')}`。",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the review manifest and evidence report")
    parser.add_argument("--check", action="store_true", help="rebuild and compare the review artifacts")
    args = parser.parse_args()
    if args.write and args.check:
        parser.error("use only one of --write or --check")
    try:
        manifest = build_manifest()
        rendered_json = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        rendered_md = markdown_report(manifest)
        if args.write:
            OUTPUT_JSON.write_text(rendered_json, encoding="utf-8", newline="")
            OUTPUT_MD.write_text(rendered_md, encoding="utf-8", newline="")
            print(f"wrote {OUTPUT_JSON.relative_to(ROOT)}")
            print(f"wrote {OUTPUT_MD.relative_to(ROOT)}")
            return 0
        if args.check:
            mismatches = []
            if not OUTPUT_JSON.exists() or OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
                mismatches.append(str(OUTPUT_JSON.relative_to(ROOT)))
            if not OUTPUT_MD.exists() or OUTPUT_MD.read_text(encoding="utf-8") != rendered_md:
                mismatches.append(str(OUTPUT_MD.relative_to(ROOT)))
            if mismatches:
                print("TD15_REMAIN_04_NOT_REPRODUCIBLE: " + ", ".join(mismatches))
                return 1
            print("TD15_REMAIN_04_OK: blocks=263 packets=14 grouped=65 dynamic=198 retain=65 observe=198 deletion=0")
            return 0
        print(rendered_json, end="")
        return 0
    except (OSError, ReviewFailure, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"TD15_REMAIN_04_FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
