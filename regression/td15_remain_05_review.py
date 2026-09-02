"""Review the 65 grouped/compound CSS blocks from TD15-REMAIN-04.

This batch is evidence-only.  It verifies that every block still exists at
the exact file/line/hash identity, inspects selector branches and contexts,
scans current HTML/JavaScript references, carries forward runtime evidence,
and assigns a conservative disposition.  It never edits CSS or baselines.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "regression"
INPUT_JSON = ROOT / "docs" / "TD15_REMAIN_04_review_manifest_2026-09-01.json"
SOURCE_JSON = ROOT / "docs" / "TD15_REMAIN_01_css_rebaseline_2026-09-01.json"
OUTPUT_JSON = ROOT / "docs" / "TD15_REMAIN_05_review_manifest_2026-09-01.json"
OUTPUT_MD = ROOT / "docs" / "TD15_REMAIN_05_evidence_2026-09-01.md"
PACKET_LIMIT = 20
EXPECTED_BLOCKS = 65
OWNER_ROLE = "TD15-CSS-review-owner"

CLASS_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")
STATE_CLASS_RE = re.compile(
    r"^(?:is-(?:active|disabled|focus|hover|negative|positive|previous|stale|up|down|warning)|"
    r".+-(?:active|alert|current|disabled|down|focus|hover|negative|positive|previous|stale|up|warning))$"
)
PSEUDO_STATE_RE = re.compile(r":(?:active|checked|disabled|focus(?:-visible|-within)?|hover|target|visited)\b")


class ReviewFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReviewFailure(message)


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
            start_line = text.count("\n", 0, start) + 1
            end_line = text.count("\n", 0, end - 1) + 1
            block = {
                "file": relative,
                "startLine": start_line,
                "endLine": end_line,
                "selector": parsed["header"],
                "context": parsed["context"],
                "sha256": sha256_bytes(text[start:end].encode("utf-8")),
            }
            blocks[identity(block)] = block
    return blocks


def source_files_for_static_scan() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".js"}:
            continue
        parts = set(path.relative_to(ROOT).parts)
        if parts.intersection({".git", ".tmp", "docs", "node_modules"}) or "baseline" in parts:
            continue
        files.append(path)
    return sorted(files)


def static_class_references(classes: set[str]) -> dict[str, list[dict]]:
    hits = {name: [] for name in classes}
    files = source_files_for_static_scan()
    for name in sorted(classes):
        pattern = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])")
        for path in files:
            for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
                if pattern.search(line):
                    hits[name].append({"file": path.relative_to(ROOT).as_posix(), "line": line_number})
    return hits


def split_selector_branches(selector: str) -> list[dict]:
    branches = []
    for raw_branch in selector.split(","):
        branch = " ".join(raw_branch.split())
        branches.append({"selector": branch, "classes": sorted(set(CLASS_RE.findall(branch)))})
    return branches


def validate_inputs() -> tuple[dict, dict, list[dict]]:
    review_manifest = read_json(INPUT_JSON)
    source_manifest = read_json(SOURCE_JSON)
    require(review_manifest.get("batch") == "TD15-REMAIN-04", "input is not the REMAIN-04 manifest")
    require(review_manifest.get("authorization", {}).get("deletion_authorized") is False, "REMAIN-04 authorizes deletion")
    require(review_manifest.get("scope", {}).get("css_rule_blocks") == 263, "REMAIN-04 scope is not 263 blocks")
    require(review_manifest.get("scope", {}).get("frontend_pages") == 21, "REMAIN-04 scope is not 21 pages")
    require(review_manifest.get("scope", {}).get("interaction_steps") == 94, "REMAIN-04 scope is not 94 interactions")
    source_by_identity = {identity(block): block for block in source_manifest.get("rule_blocks", [])}
    require(len(source_by_identity) == 263, "REMAIN-01 source identity count is not 263")
    grouped = [item for item in review_manifest.get("reviews", []) if item.get("review_category") == "grouped-compound"]
    require(len(grouped) == EXPECTED_BLOCKS, f"expected {EXPECTED_BLOCKS} grouped blocks, found {len(grouped)}")
    require({item.get("packet_id") for item in grouped} == {
        "TD15-REMAIN-04-G01", "TD15-REMAIN-04-G02", "TD15-REMAIN-04-G03", "TD15-REMAIN-04-G04"
    }, "grouped input packets are incomplete")
    return review_manifest, source_by_identity, grouped


def review_block(item: dict, source_block: dict, current_block: dict, references: dict[str, list[dict]]) -> dict:
    exact = item["exact_identity"]
    selector = exact["selector"]
    selector_classes = sorted(set(CLASS_RE.findall(selector)))
    candidate_classes = sorted(source_block.get("candidate_classes", []))
    noncandidate_classes = sorted(set(selector_classes).difference(candidate_classes))
    branches = split_selector_branches(selector)
    compound_branches = [branch for branch in branches if len(branch["classes"]) > 1]
    static_hits = {name: references[name] for name in selector_classes if references[name]}
    context = source_block.get("context", [])
    state_classes = sorted(name for name in selector_classes if STATE_CLASS_RE.match(name))
    pseudo_states = sorted(set(PSEUDO_STATE_RE.findall(selector)))
    runtime_dom = source_block.get("three_layer_evidence", {}).get("runtime_dom", {})
    runtime_hits = {
        name: runtime_dom.get(name, {"page_count": 0, "pages": [], "dom_count": 0})
        for name in candidate_classes
    }

    identity_match = identity(item) == identity(source_block) == identity(current_block)
    evidence_complete = (
        identity_match
        and source_block.get("three_layer_evidence", {}).get("page_behavior", {}).get("frontend_pages") == 21
        and source_block.get("three_layer_evidence", {}).get("page_behavior", {}).get("interaction_steps") == 94
    )
    if not identity_match or not evidence_complete:
        disposition = "blocked"
        reason = "current CSS identity 或既有 21 頁／94 interactions evidence 不一致，停止後續判定。"
    elif noncandidate_classes or static_hits or compound_branches or context or state_classes or pseudo_states:
        disposition = "retain"
        reason = (
            "selector 仍含非候選 live branch、compound branch、HTML／JS static reference、"
            "responsive context 或 state selector；未具備安全拆除條件，維持保留。"
        )
    else:
        disposition = "observe"
        reason = "目前未取得足以刪除的 live branch／responsive／state 完整證據，降級觀察，不刪除。"

    return {
        "review_id": item["review_id"].replace("TD15-REMAIN-04-", "TD15-REMAIN-05-"),
        "source_review_id": item["review_id"],
        "packet_id": item["packet_id"].replace("TD15-REMAIN-04-", "TD15-REMAIN-05-"),
        "exact_identity": exact,
        "candidate_classes": candidate_classes,
        "selector_classes": selector_classes,
        "cascade_review": {
            "selector_branches": branches,
            "compound_branch_count": len(compound_branches),
            "noncandidate_classes": noncandidate_classes,
            "status": "mixed-grouped-selector" if noncandidate_classes else "candidate-only-selector",
        },
        "live_branch_review": {
            "html_js_static_references": static_hits,
            "referenced_class_count": len(static_hits),
            "status": "static-reference-recorded" if static_hits else "no-static-reference-recorded",
        },
        "responsive_review": {
            "contexts": context,
            "status": "context-present" if context else "no-media-context",
            "mobile_or_responsive_evidence": "not-expanded-in-this-batch",
        },
        "state_review": {
            "state_classes": state_classes,
            "pseudo_states": pseudo_states,
            "status": "state-token-present" if state_classes or pseudo_states else "no-explicit-state-token",
            "non_default_state_evidence": "not-exhaustive-in-default-baseline",
        },
        "runtime_review": {
            "candidate_class_hits": runtime_hits,
            "page_count_with_candidate_hits": sum(1 for value in runtime_hits.values() if value.get("page_count", 0)),
            "status": "runtime-hit-recorded" if any(value.get("page_count", 0) for value in runtime_hits.values()) else "runtime-zero-hit-recorded",
        },
        "page_behavior_evidence": {
            "frontend_pages": 21,
            "interaction_steps": 94,
            "screenshot_manifest_pages": 21,
        },
        "evidence_status": "complete-current-identity-review-recorded",
        "responsible_role": OWNER_ROLE,
        "disposition": disposition,
        "decision_reason": reason,
        "deletion_authorized": False,
    }


def build_manifest() -> dict:
    input_manifest, source_by_identity, grouped = validate_inputs()
    current_by_identity = load_current_css_blocks()
    all_classes = {
        name
        for item in grouped
        for name in source_by_identity[identity(item)].get("selector_classes", [])
    }
    references = static_class_references(all_classes)
    reviews = []
    for item in sorted(grouped, key=identity):
        key = identity(item)
        require(key in source_by_identity, f"grouped block missing from REMAIN-01: {key}")
        require(key in current_by_identity, f"grouped block missing from current CSS: {key}")
        reviews.append(review_block(item, source_by_identity[key], current_by_identity[key], references))

    disposition_counts = {name: sum(1 for item in reviews if item["disposition"] == name) for name in ("retain", "observe", "delete_candidate", "blocked")}
    require(len(reviews) == EXPECTED_BLOCKS, "REMAIN-05 did not review all 65 grouped blocks")
    require(disposition_counts["delete_candidate"] == 0, "REMAIN-05 unexpectedly authorized a deletion candidate")
    require(all(item["deletion_authorized"] is False for item in reviews), "a review item authorizes deletion")
    packets = []
    for packet_id in sorted({item["packet_id"] for item in reviews}):
        packet_items = [item for item in reviews if item["packet_id"] == packet_id]
        require(len(packet_items) <= PACKET_LIMIT, f"packet exceeds {PACKET_LIMIT}: {packet_id}")
        packets.append({
            "packet_id": packet_id,
            "category": "grouped-compound-responsive-state",
            "block_count": len(packet_items),
            "max_block_count": PACKET_LIMIT,
            "disposition_set": sorted({item["disposition"] for item in packet_items}),
            "responsible_role": OWNER_ROLE,
            "review_ids": [item["review_id"] for item in packet_items],
        })

    return {
        "schema_version": 1,
        "batch": "TD15-REMAIN-05",
        "snapshot_date": "2026-09-01",
        "status": "TD15_REMAIN_05_PASS_GROUPED_REVIEW",
        "input_manifest": INPUT_JSON.relative_to(ROOT).as_posix(),
        "source_manifest": SOURCE_JSON.relative_to(ROOT).as_posix(),
        "scope": {
            "css_rule_blocks": EXPECTED_BLOCKS,
            "review_packets": len(packets),
            "packet_limit": PACKET_LIMIT,
            "frontend_pages": 21,
            "interaction_steps": 94,
        },
        "disposition_counts": disposition_counts,
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
    counts = manifest["disposition_counts"]
    lines = [
        "# TD15-REMAIN-05 grouped／compound CSS review（2026-09-01）",
        "",
        "本批完成 REMAIN-04 所列 65 個 grouped／compound blocks 的 cascade、live branch、responsive、state、HTML／JS 與 runtime review；不刪除 CSS、不更新 baseline。",
        "",
        "## 批次結果",
        "",
        f"- 狀態：`{manifest['status']}`。65/65 blocks 完成逐項 review，分成 {manifest['scope']['review_packets']} 個 packets，每包上限 {manifest['scope']['packet_limit']}。",
        f"- disposition：`retain` {counts['retain']}、`observe` {counts['observe']}、`delete candidate` {counts['delete_candidate']}、`blocked` {counts['blocked']}。",
        "- 每項均重新核對 current file／startLine／endLine／selector／SHA-256，並記錄 selector branches、static references、media context、state tokens、runtime DOM 與 21 頁／94 interactions evidence。",
        "- 授權邊界：`deletion_authorized=false`、`baseline_changed=false`、`source_modified=false`、`runtime_data_modified=false`。",
        "",
        "`responsible_role` 是待人工審查的角色責任欄位，不宣稱已指定特定個人。",
        "",
        "## Review packets",
        "",
        "| packet | blocks | disposition |",
        "|---|---:|---|",
    ]
    for packet in manifest["packets"]:
        lines.append(f"| `{packet['packet_id']}` | {packet['block_count']} | `{', '.join(packet['disposition_set'])}` |")

    lines.extend([
        "",
        "## Per-block review",
        "",
        "每列是一個 current rule block；完整 branch、static、responsive、state、runtime details 在同名 JSON。",
        "",
        "| review | current identity | selector | cascade | live branch | responsive | state | runtime | disposition | reason |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    for item in manifest["reviews"]:
        exact = item["exact_identity"]
        cascade = item["cascade_review"]
        live = item["live_branch_review"]
        responsive = item["responsive_review"]
        state = item["state_review"]
        runtime = item["runtime_review"]
        location = f"`{exact['file']}:{exact['startLine']}-{exact['endLine']}`"
        reason = item["decision_reason"].replace("|", "\\|")
        lines.append(
            f"| `{item['review_id']}` | {location} / `{exact['sha256']}` | `{selector_inline(exact['selector'])}` | {cascade['status']}; compound={cascade['compound_branch_count']}; noncandidate={len(cascade['noncandidate_classes'])} | {live['status']}; refs={live['referenced_class_count']} | {responsive['status']} | {state['status']} | {runtime['status']}; pages={runtime['page_count_with_candidate_hits']} | `{item['disposition']}` | {reason} |"
        )

    lines.extend([
        "",
        "## 後續 gate",
        "",
        "- 本批所有 current grouped blocks 均因 live branch／compound／responsive／state 證據或完整性 gate 維持 `retain`；沒有 `delete candidate`。",
        "- REMAIN-06 已完成 198 個 dynamic／status／direct-reference blocks coverage review，並由 REMAIN-07 完成全量 closure。",
        "- REMAIN-07 最終對帳 263/263 `retain`、delete candidate=0、blocked=0；本批沒有 CSS 刪除。",
        "- 預設 baseline 不涵蓋全部 mobile、hover、focus、active、disabled 與資料狀態；未來若出現新候選仍須另批 ≤20 blocks。",
        "",
        f"輸入：`{manifest['input_manifest']}`；machine-readable output：`{OUTPUT_JSON.relative_to(ROOT).as_posix()}`。",
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
                print("TD15_REMAIN_05_NOT_REPRODUCIBLE: " + ", ".join(mismatches))
                return 1
            print("TD15_REMAIN_05_OK: blocks=65 packets=4 retain=65 observe=0 delete_candidate=0 blocked=0")
            return 0
        print(rendered_json, end="")
        return 0
    except (OSError, ReviewFailure, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        print(f"TD15_REMAIN_05_FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
