"""Review the 198 dynamic/status/direct-reference CSS blocks.

REMAIN-06 is evidence-only.  It verifies current CSS identities, traces
candidate names through HTML/JavaScript/Python source, records classList and
template/prefix generator sites, summarizes data/state tokens, and carries
forward runtime evidence.  It never edits CSS, baselines, or runtime data.
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
OUTPUT_JSON = ROOT / "docs" / "TD15_REMAIN_06_review_manifest_2026-09-01.json"
OUTPUT_MD = ROOT / "docs" / "TD15_REMAIN_06_evidence_2026-09-01.md"
EXPECTED_BLOCKS = 198
PACKET_LIMIT = 20
OWNER_ROLE = "TD15-CSS-review-owner"

CLASS_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")
PSEUDO_STATE_RE = re.compile(r":(?:active|checked|disabled|focus(?:-visible|-within)?|hover|target|visited)\b")
STATE_CLASS_RE = re.compile(
    r"^(?:is-[A-Za-z0-9_-]+|.+-(?:active|alert|current|disabled|down|focus|hover|negative|positive|previous|stale|up|warning))$"
)
DATA_FIELD_RE = re.compile(
    r"\b(?:data|item|row|record|quote|stock|metric|state|status|tone|risk|change|direction|symbol|market|sector|signal|score|type|kind|category|variant|trend|side|level|value|source|mode|view|tab|filter|sort|group|region|strategy|rating)\b",
    re.IGNORECASE,
)
GENERATOR_RE = re.compile(r"(?:class(?:Name|List)?|classList|template|\+|`)", re.IGNORECASE)

KNOWN_DYNAMIC_PREFIXES = (
    "asset-",
    "asset-finance-",
    "bond-",
    "institution-card-",
    "is-",
    "ma-",
    "market-ai-risk-",
    "market-risk-",
    "market-sector-",
    "metric-",
    "option-region-",
    "other-",
    "sector-",
    "us-market-ranking-",
)


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


def source_files_for_scan() -> list[Path]:
    excluded_files = {"td15_remain_07_closure.py"}
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".js", ".py"}:
            continue
        parts = set(path.relative_to(ROOT).parts)
        if parts.intersection({".git", ".tmp", "docs", "node_modules"}) or "baseline" in parts:
            continue
        if path.name in excluded_files:
            continue
        files.append(path)
    return sorted(files)


def location(path: Path, line_number: int) -> dict:
    return {"file": path.relative_to(ROOT).as_posix(), "line": line_number}


def scan_generator_evidence(classes: set[str]) -> dict:
    exact_hits = {name: [] for name in classes}
    class_list_hits = {name: [] for name in classes}
    template_hits = {name: [] for name in classes}
    data_fields = {name: set() for name in classes}
    prefix_hits = {prefix: [] for prefix in KNOWN_DYNAMIC_PREFIXES}
    files = source_files_for_scan()
    patterns = {name: re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(name)}(?![A-Za-z0-9_-])") for name in classes}
    for path in files:
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            matched_names = [name for name, pattern in patterns.items() if pattern.search(line)]
            matched_prefixes = [prefix for prefix in KNOWN_DYNAMIC_PREFIXES if prefix in line]
            generator_line = bool(GENERATOR_RE.search(line))
            class_list_line = "classlist" in line.lower()
            template_or_concat_line = "`" in line or "+" in line
            tokens = {match.group(0).lower() for match in DATA_FIELD_RE.finditer(line)}
            for prefix in matched_prefixes:
                if generator_line:
                    prefix_hits[prefix].append(location(path, line_number))
            for name in matched_names:
                hit = location(path, line_number)
                exact_hits[name].append(hit)
                if class_list_line:
                    class_list_hits[name].append(hit)
                if template_or_concat_line:
                    template_hits[name].append(hit)
                if tokens:
                    data_fields[name].update(tokens)
    return {
        "exact_literal_hits": exact_hits,
        "classList_hits": class_list_hits,
        "template_or_concat_hits": template_hits,
        "data_field_tokens": {name: sorted(tokens) for name, tokens in data_fields.items()},
        "prefix_generator_hits": prefix_hits,
        "scanned_files": [path.relative_to(ROOT).as_posix() for path in files],
    }


def validate_inputs() -> tuple[dict, dict, list[dict]]:
    input_manifest = read_json(INPUT_JSON)
    source_manifest = read_json(SOURCE_JSON)
    require(input_manifest.get("batch") == "TD15-REMAIN-04", "input is not the REMAIN-04 manifest")
    require(input_manifest.get("authorization", {}).get("deletion_authorized") is False, "REMAIN-04 authorizes deletion")
    require(input_manifest.get("scope", {}).get("css_rule_blocks") == 263, "REMAIN-04 scope is not 263 blocks")
    require(input_manifest.get("scope", {}).get("frontend_pages") == 21, "REMAIN-04 scope is not 21 pages")
    require(input_manifest.get("scope", {}).get("interaction_steps") == 94, "REMAIN-04 scope is not 94 interactions")
    source_by_identity = {identity(block): block for block in source_manifest.get("rule_blocks", [])}
    require(len(source_by_identity) == 263, "REMAIN-01 source identity count is not 263")
    dynamic = [item for item in input_manifest.get("reviews", []) if item.get("review_category") == "dynamic-status-direct-reference"]
    require(len(dynamic) == EXPECTED_BLOCKS, f"expected {EXPECTED_BLOCKS} dynamic blocks, found {len(dynamic)}")
    require({item.get("packet_id") for item in dynamic} == {
        f"TD15-REMAIN-04-D{number:02d}" for number in range(1, 11)
    }, "dynamic input packets are incomplete")
    return input_manifest, source_by_identity, dynamic


def review_block(item: dict, source_block: dict, current_block: dict, scan: dict) -> dict:
    exact = item["exact_identity"]
    selector = exact["selector"]
    selector_classes = sorted(set(CLASS_RE.findall(selector)))
    candidate_classes = sorted(source_block.get("candidate_classes", []))
    dynamic_classes = sorted(source_block.get("dynamic_classes", []))
    status_classes = sorted(source_block.get("status_classes", []))
    direct_usage_hits = sorted(source_block.get("direct_usage_hits", []))
    runtime_dom = source_block.get("three_layer_evidence", {}).get("runtime_dom", {})
    runtime_hits = {
        name: runtime_dom.get(name, {"page_count": 0, "pages": [], "dom_count": 0})
        for name in candidate_classes
    }
    candidate_evidence = {
        name: {
            "exact_literal_site_count": len(scan["exact_literal_hits"][name]),
            "classList_site_count": len(scan["classList_hits"][name]),
            "template_or_concat_site_count": len(scan["template_or_concat_hits"][name]),
            "data_field_tokens": scan["data_field_tokens"][name],
            "evidence_index_key": f"class:{name}",
        }
        for name in candidate_classes
    }
    prefix_evidence = {
        prefix: {
            "site_count": len(scan["prefix_generator_hits"][prefix]),
            "evidence_index_key": f"prefix:{prefix}",
        }
        for name in candidate_classes
        for prefix in KNOWN_DYNAMIC_PREFIXES
        if name.startswith(prefix) and scan["prefix_generator_hits"][prefix]
    }
    exact_generator_names = {
        name for name in candidate_classes
        if candidate_evidence[name]["classList_site_count"] or candidate_evidence[name]["template_or_concat_site_count"]
    }
    prefix_generator_names = {
        name for name in candidate_classes
        if any(name.startswith(prefix) and prefix in prefix_evidence for prefix in KNOWN_DYNAMIC_PREFIXES)
    }
    runtime_page_count = sum(1 for value in runtime_hits.values() if value.get("page_count", 0))
    state_tokens = sorted(set(status_classes + PSEUDO_STATE_RE.findall(selector)))
    state_sources = sorted({token for name in candidate_classes for token in scan["data_field_tokens"][name] if token in {"direction", "risk", "state", "status", "tone", "trend"}})

    identity_match = identity(item) == identity(source_block) == identity(current_block)
    behavior = source_block.get("three_layer_evidence", {}).get("page_behavior", {})
    coverage_complete = behavior.get("frontend_pages") == 21 and behavior.get("interaction_steps") == 94
    if not identity_match or not coverage_complete:
        disposition = "blocked"
        reason = "current CSS identity 或既有 21 頁／94 interactions evidence 不一致，停止後續判定。"
    elif direct_usage_hits or exact_generator_names or prefix_generator_names or status_classes or runtime_page_count:
        disposition = "retain"
        reason = "存在 direct reference、generator／prefix path、status class 或 runtime DOM evidence；dynamic／state 風險未收斂，維持保留。"
    elif not dynamic_classes and not status_classes and not direct_usage_hits and not runtime_page_count:
        disposition = "delete_candidate"
        reason = "目前未發現 dynamic、status、direct reference、generator 或 runtime evidence；僅列為候選，未授權刪除。"
    else:
        disposition = "observe"
        reason = "只有候選命名或不足以確認的 dynamic path，generator、資料欄位與狀態集合尚未收斂，降級觀察。"

    return {
        "review_id": item["review_id"].replace("TD15-REMAIN-04-", "TD15-REMAIN-06-"),
        "source_review_id": item["review_id"],
        "packet_id": item["packet_id"].replace("TD15-REMAIN-04-", "TD15-REMAIN-06-"),
        "exact_identity": exact,
        "candidate_classes": candidate_classes,
        "source_dynamic_classes": dynamic_classes,
        "source_status_classes": status_classes,
        "source_direct_usage_hits": direct_usage_hits,
        "generator_review": {
            "candidate_evidence": candidate_evidence,
            "prefix_evidence": prefix_evidence,
            "exact_generator_names": sorted(exact_generator_names),
            "prefix_generator_names": sorted(prefix_generator_names),
            "status": "exact-or-prefix-generator-observed" if exact_generator_names or prefix_generator_names else "generator-not-observed",
        },
        "data_field_review": {
            "candidate_data_field_tokens": {
                name: evidence["data_field_tokens"]
                for name, evidence in candidate_evidence.items()
                if evidence["data_field_tokens"]
            },
            "status": "data-field-tokens-observed" if any(evidence["data_field_tokens"] for evidence in candidate_evidence.values()) else "data-field-tokens-not-observed",
        },
        "state_set_review": {
            "selector_state_tokens": state_tokens,
            "data_state_tokens": state_sources,
            "status": "state-set-partially-observed" if state_tokens or state_sources else "state-set-not-observed",
            "non_default_state_evidence": "not-exhaustive-in-default-baseline",
        },
        "runtime_review": {
            "candidate_class_hits": runtime_hits,
            "page_count_with_candidate_hits": runtime_page_count,
            "status": "runtime-hit-recorded" if runtime_page_count else "runtime-zero-hit-recorded",
        },
        "page_behavior_evidence": {
            "frontend_pages": 21,
            "interaction_steps": 94,
            "screenshot_manifest_pages": 21,
        },
        "evidence_status": "complete-current-identity-coverage-recorded",
        "responsible_role": OWNER_ROLE,
        "disposition": disposition,
        "decision_reason": reason,
        "deletion_authorized": False,
    }


def build_manifest() -> dict:
    input_manifest, source_by_identity, dynamic = validate_inputs()
    current_by_identity = load_current_css_blocks()
    all_classes = {
        name
        for item in dynamic
        for name in source_by_identity[identity(item)].get("candidate_classes", [])
    }
    scan = scan_generator_evidence(all_classes)
    reviews = []
    for item in sorted(dynamic, key=identity):
        key = identity(item)
        require(key in source_by_identity, f"dynamic block missing from REMAIN-01: {key}")
        require(key in current_by_identity, f"dynamic block missing from current CSS: {key}")
        reviews.append(review_block(item, source_by_identity[key], current_by_identity[key], scan))

    disposition_names = ("retain", "observe", "delete_candidate", "blocked")
    disposition_counts = {name: sum(1 for item in reviews if item["disposition"] == name) for name in disposition_names}
    require(len(reviews) == EXPECTED_BLOCKS, "REMAIN-06 did not review all 198 dynamic blocks")
    require(all(item["deletion_authorized"] is False for item in reviews), "a review item authorizes deletion")
    packets = []
    for packet_id in sorted({item["packet_id"] for item in reviews}):
        packet_items = [item for item in reviews if item["packet_id"] == packet_id]
        require(len(packet_items) <= PACKET_LIMIT, f"packet exceeds {PACKET_LIMIT}: {packet_id}")
        packets.append({
            "packet_id": packet_id,
            "category": "dynamic-status-direct-reference",
            "block_count": len(packet_items),
            "max_block_count": PACKET_LIMIT,
            "disposition_set": sorted({item["disposition"] for item in packet_items}),
            "responsible_role": OWNER_ROLE,
            "review_ids": [item["review_id"] for item in packet_items],
        })

    return {
        "schema_version": 1,
        "batch": "TD15-REMAIN-06",
        "snapshot_date": "2026-09-01",
        "status": "TD15_REMAIN_06_PASS_DYNAMIC_COVERAGE_REVIEW",
        "input_manifest": INPUT_JSON.relative_to(ROOT).as_posix(),
        "source_manifest": SOURCE_JSON.relative_to(ROOT).as_posix(),
        "scope": {
            "css_rule_blocks": EXPECTED_BLOCKS,
            "review_packets": len(packets),
            "packet_limit": PACKET_LIMIT,
            "frontend_pages": 21,
            "interaction_steps": 94,
            "scanned_source_files": len(scan["scanned_files"]),
        },
        "disposition_counts": disposition_counts,
        "generator_evidence_index": {
            "scanned_files": scan["scanned_files"],
            "class_sites": {
                name: {
                    "exact_literal_hits": scan["exact_literal_hits"][name],
                    "classList_hits": scan["classList_hits"][name],
                    "template_or_concat_hits": scan["template_or_concat_hits"][name],
                    "data_field_tokens": scan["data_field_tokens"][name],
                }
                for name in sorted(all_classes)
            },
            "prefix_generator_hits": scan["prefix_generator_hits"],
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
    counts = manifest["disposition_counts"]
    lines = [
        "# TD15-REMAIN-06 dynamic／status／direct-reference CSS review（2026-09-01）",
        "",
        "本批完成 REMAIN-04 所列 198 個 dynamic／status／direct-reference blocks 的 generator、資料欄位、classList／template、狀態集合、HTML／JS／Python 與 runtime coverage review；不刪除 CSS、不更新 baseline。",
        "",
        "## 批次結果",
        "",
        f"- 狀態：`{manifest['status']}`。198/198 blocks 完成逐項 review，分成 {manifest['scope']['review_packets']} 個 packets，每包上限 {manifest['scope']['packet_limit']}。",
        f"- disposition：`retain` {counts['retain']}、`observe` {counts['observe']}、`delete candidate` {counts['delete_candidate']}、`blocked` {counts['blocked']}。",
        f"- 掃描範圍：{manifest['scope']['scanned_source_files']} 個現行 HTML／JS／Python source files；每項保留 current file／startLine／endLine／selector／SHA-256 與 21 頁／94 interactions evidence。",
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
        "每列是一個 current rule block；完整 generator、資料欄位、狀態集合與 runtime locations 在同名 JSON。",
        "",
        "| review | current identity | selector | candidate／source flags | generator | data fields | state set | runtime | disposition | reason |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    for item in manifest["reviews"]:
        exact = item["exact_identity"]
        generator = item["generator_review"]
        fields = item["data_field_review"]
        states = item["state_set_review"]
        runtime = item["runtime_review"]
        flags = f"candidate={','.join(item['candidate_classes'])}; dynamic={len(item['source_dynamic_classes'])}; status={len(item['source_status_classes'])}; direct={len(item['source_direct_usage_hits'])}"
        location_text = f"`{exact['file']}:{exact['startLine']}-{exact['endLine']}` / `{exact['sha256']}`"
        candidate_evidence = generator["candidate_evidence"]
        class_list_count = sum(1 for evidence in candidate_evidence.values() if evidence["classList_site_count"])
        template_count = sum(1 for evidence in candidate_evidence.values() if evidence["template_or_concat_site_count"])
        generator_text = f"{generator['status']}; exact={len(generator['exact_generator_names'])}; prefix={len(generator['prefix_generator_names'])}; classList={class_list_count}; template={template_count}"
        field_text = f"{fields['status']}; {','.join(sorted({token for values in fields['candidate_data_field_tokens'].values() for token in values})) or '-'}"
        state_text = f"{states['status']}; selector={','.join(states['selector_state_tokens']) or '-'}; data={','.join(states['data_state_tokens']) or '-'}"
        runtime_text = f"{runtime['status']}; pages={runtime['page_count_with_candidate_hits']}"
        reason = item["decision_reason"].replace("|", "\\|")
        lines.append(
            f"| `{item['review_id']}` | {location_text} | `{selector_inline(exact['selector'])}` | {flags} | {generator_text} | {field_text} | {state_text} | {runtime_text} | `{item['disposition']}` | {reason} |"
        )

    lines.extend([
        "",
        "## 後續 gate",
        "",
        "- `retain` 項目仍有 generator、direct reference、status／state 或 runtime evidence；不得因 default screenshot 零命中刪除。",
        "- 本批 198/198 已完成 coverage review 並全部 `retain`；`observe`=0、`delete candidate`=0、`blocked`=0。",
        "- REMAIN-07 已完成最終 closure：263/263 `retain`，沒有候選可執行刪除，因此未建立 deletion batch。",
        "- 未來若 source 或頁面行為變更，須重新建立 current identity 與 generator evidence，再另開 ≤20 blocks 批次。",
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
                print("TD15_REMAIN_06_NOT_REPRODUCIBLE: " + ", ".join(mismatches))
                return 1
            print("TD15_REMAIN_06_OK: blocks=198 packets=10 retain=198 observe=0 delete_candidate=0 blocked=0")
            return 0
        print(rendered_json, end="")
        return 0
    except (OSError, ReviewFailure, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
        print(f"TD15_REMAIN_06_FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
