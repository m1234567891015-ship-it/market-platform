"""Rebuild the current TD-15 residual CSS inventory without deleting anything.

This is the R0 gate: it deliberately treats the historical classification as
a candidate source only, then re-resolves current files, current line numbers,
literal references, dynamic-prefix hints, and grouped/at-rule context.
"""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable

from slice_css_batch import parse_blocks


ROOT = Path(__file__).resolve().parent.parent
CLASSIFICATION = ROOT / "docs" / "td15_css_classification.md"
CSS_REPORT = ROOT / "docs" / "css_unused_report.md"
BASELINE_FRONTEND = ROOT / "regression" / "baseline" / "frontend_manifest.json"
BASELINE_INTERACTIONS = ROOT / "regression" / "baseline" / "interactions" / "manifest.json"
DEFAULT_SNAPSHOT_DATE = "2026-08-31"


def artifact_paths(snapshot_date: str) -> tuple[Path, Path]:
    return (
        ROOT / "docs" / f"TD15_residual_inventory_{snapshot_date}.json",
        ROOT / "docs" / f"TD15_residual_inventory_{snapshot_date}.md",
    )

# Headers are already isolated CSS selectors; matching every class/id token is
# required so chained selectors such as `.foo.bar` retain the `.bar` branch.
CLASS_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")
ID_RE = re.compile(r"#([A-Za-z_][A-Za-z0-9_-]*)")
TABLE_CLASS_RE = re.compile(r"^\| `\.([A-Za-z_][A-Za-z0-9_-]*)` \|")
TABLE_ID_RE = re.compile(r"^\| `#([A-Za-z_][A-Za-z0-9_-]*)` \|")
USAGE_RE_TEMPLATE = r"(?<![A-Za-z0-9_-]){name}(?![A-Za-z0-9_-])"

KNOWN_DYNAMIC_PREFIXES = (
    "asset-",
    "asset-finance-trend-",
    "bond-",
    "institution-card-",
    "is-",
    "is-line-",
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

STATUS_MARKERS = (
    "-active",
    "-alert",
    "-current",
    "-disabled",
    "-down",
    "-focus",
    "-hover",
    "-negative",
    "-positive",
    "-previous",
    "-stale",
    "-up",
    "-warning",
)

HISTORICAL_DELETIONS = [
    {"batch": "H-04-01", "blocks": 2, "selectors": "backtest-signal", "file": "split-02.css"},
    {"batch": "H-04-02", "blocks": 3, "selectors": "chart-stack, chart-area, chart-points", "file": "assets/styles.css"},
    {"batch": "H-04-03", "blocks": 5, "selectors": "class-hero-value-row, class-hero-metrics", "file": "assets/styles.css"},
    {"batch": "H-04-04", "blocks": 4, "selectors": "chip-summary-card", "file": "split-03.css"},
    {"batch": "H-04-05", "blocks": 1, "selectors": "futures-timeframe-chip", "file": "split-04.css"},
    {"batch": "H-04-06", "blocks": 7, "selectors": "us-architecture-node", "file": "split-04.css"},
    {"batch": "H-04-07", "blocks": 2, "selectors": "options-heat-cell", "file": "split-05.css"},
    {"batch": "H-04-08", "blocks": 1, "selectors": "options-market-chain-data-table", "file": "split-06.css"},
    {"batch": "H-04-09", "blocks": 2, "selectors": "us-etf-category-filters", "file": "split-04.css"},
    {"batch": "H-04-10", "blocks": 2, "selectors": "us-sector-plain-result", "file": "split-03.css"},
    {"batch": "H-09-03", "blocks": 3, "selectors": "us-sector-end-label", "file": "split-03.css"},
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def classification_candidates() -> tuple[set[str], set[str]]:
    lines = read_utf8(CLASSIFICATION).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## Class 分類表"))
    end = next(i for i, line in enumerate(lines[start + 1:], start + 1) if line.startswith("## ID 候選"))
    class_names = {match.group(1) for line in lines[start:end] if (match := TABLE_CLASS_RE.match(line))}
    id_names = {match.group(1) for line in lines[end:] if (match := TABLE_ID_RE.match(line))}
    return class_names, id_names


def css_paths() -> list[Path]:
    paths = sorted(ROOT.glob("split-*.css"))
    for relative in (Path("styles.css"), Path("assets/styles.css")):
        path = ROOT / relative
        if path.exists():
            paths.append(path)
    return paths


def flatten_rules(text: str, base_offset: int = 0, context: tuple[str, ...] = ()) -> Iterable[dict]:
    """Yield rule blocks, including rules nested in media/supports blocks."""
    for block in parse_blocks(text):
        if block["kind"] == "rule":
            start = base_offset + block["start"]
            end = base_offset + block["end"]
            yield {
                "start": start,
                "end": end,
                "startLine": block["startLine"],
                "header": block["header"],
                "context": list(context),
            }
        elif block["kind"] == "atrule":
            header = block["header"].strip()
            if header.lower().startswith(("@keyframes", "@font-face")):
                continue
            local = text[block["start"]:block["end"]]
            brace = local.find("{")
            if brace < 0 or not local.endswith("}"):
                continue
            body_start = block["start"] + brace + 1
            body_end = block["end"] - 1
            yield from flatten_rules(
                text[body_start:body_end],
                base_offset + body_start,
                context + (header,),
            )


def source_files_for_usage() -> list[Path]:
    allowed = {".html", ".js", ".py"}
    excluded_parts = {".git", ".tmp", "docs"}
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed:
            continue
        relative_parts = set(path.relative_to(ROOT).parts)
        if relative_parts.intersection(excluded_parts) or "baseline" in relative_parts:
            continue
        files.append(path)
    return sorted(files)


def literal_usage(candidates: set[str]) -> dict[str, list[dict]]:
    hits = {candidate: [] for candidate in candidates}
    files = source_files_for_usage()
    for candidate in sorted(candidates):
        pattern = re.compile(USAGE_RE_TEMPLATE.format(name=re.escape(candidate)))
        for path in files:
            for line_number, line in enumerate(read_utf8(path).splitlines(), 1):
                if pattern.search(line):
                    hits[candidate].append(
                        {"file": path.relative_to(ROOT).as_posix(), "line": line_number}
                    )
    return hits


def html_css_assets() -> list[str]:
    assets: set[str] = set()
    pattern = re.compile(r"<link\b[^>]+href=[\"']([^\"']+\.css(?:\?[^\"']*)?)[\"']", re.IGNORECASE)
    for page in sorted(ROOT.glob("*.html")):
        assets.update(pattern.findall(read_utf8(page)))
    return sorted(assets)


def classify_block(block: dict, candidates: set[str], usage: dict[str, list[dict]]) -> dict:
    selector_classes = sorted(set(CLASS_RE.findall(block["header"])))
    candidate_classes = sorted(set(selector_classes).intersection(candidates))
    noncandidate_classes = sorted(set(selector_classes).difference(candidates))
    dynamic_classes = [
        name for name in candidate_classes if any(name.startswith(prefix) for prefix in KNOWN_DYNAMIC_PREFIXES)
    ]
    status_classes = [
        name for name in candidate_classes if name.startswith("is-") or any(marker in name for marker in STATUS_MARKERS)
    ]
    direct_refs = sorted({
        hit["file"] + ":" + str(hit["line"])
        for name in candidate_classes
        for hit in usage[name]
    })
    if dynamic_classes or status_classes or direct_refs:
        decision = "retain-dynamic-status-or-direct-reference"
    elif noncandidate_classes or ID_RE.search(block["header"]):
        decision = "retain-grouped-or-compound-review"
    else:
        decision = "candidate-only-review"
    return {
        "file": block["file"],
        "startLine": block["startLine"],
        "endLine": block["endLine"],
        "selector": block["header"],
        "context": block["context"],
        "selector_classes": selector_classes,
        "candidate_classes": candidate_classes,
        "noncandidate_classes": noncandidate_classes,
        "dynamic_classes": dynamic_classes,
        "status_classes": status_classes,
        "direct_usage_hits": direct_refs,
        "decision": decision,
        "sha256": block["sha256"],
    }


def build_inventory(snapshot_date: str = DEFAULT_SNAPSHOT_DATE) -> dict:
    candidates, id_candidates = classification_candidates()
    usage = literal_usage(candidates)
    all_blocks: list[dict] = []
    source_hashes = {}
    for path in css_paths():
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        relative = path.relative_to(ROOT).as_posix()
        source_hashes[relative] = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
        for block in flatten_rules(text):
            start, end = block["start"], block["end"]
            block["file"] = relative
            block["endLine"] = text.count("\n", 0, end - 1) + 1
            block["startLine"] = text.count("\n", 0, start) + 1
            block["sha256"] = sha256_bytes(text[start:end].encode("utf-8"))
            if set(CLASS_RE.findall(block["header"])).intersection(candidates):
                all_blocks.append(block)

    classified = [classify_block(block, candidates, usage) for block in all_blocks]
    current_candidate_names = sorted({name for block in classified for name in block["candidate_classes"]})
    candidate_only = [block for block in classified if block["decision"] == "candidate-only-review"]
    current_css_class_names = sorted({name for block in classified for name in block["selector_classes"]})
    historical_blocks = sum(item["blocks"] for item in HISTORICAL_DELETIONS)
    frontend_manifest = json.loads(BASELINE_FRONTEND.read_text(encoding="utf-8-sig"))
    interaction_manifest = json.loads(BASELINE_INTERACTIONS.read_text(encoding="utf-8-sig"))
    return {
        "schema_version": 1,
        "snapshot_date": snapshot_date,
        "status": "R0_PASS_NO_DELETION",
        "scope": {
            "classification_source": CLASSIFICATION.relative_to(ROOT).as_posix(),
            "css_sources": [path.relative_to(ROOT).as_posix() for path in css_paths()],
            "usage_extensions": [".html", ".js", ".py"],
            "usage_excluded": ["docs", "regression/baseline", ".tmp"],
        },
        "classification_snapshot": {
            "css_class_candidates": len(candidates),
            "css_id_candidates": len(id_candidates),
            "css_id_candidates_excluded_as_nonexistent": sorted(id_candidates),
        },
        "current_state": {
            "css_source_hashes": source_hashes,
            "html_css_assets": html_css_assets(),
            "candidate_bearing_rule_blocks": len(classified),
            "current_candidate_names": current_candidate_names,
            "current_candidate_name_count": len(current_candidate_names),
            "candidate_only_review_blocks": len(candidate_only),
            "decision_counts": {
                decision: sum(1 for block in classified if block["decision"] == decision)
                for decision in sorted({block["decision"] for block in classified})
            },
        },
        "historical_reconciliation": {
            "recorded_deleted_rule_blocks": historical_blocks,
            "recorded_batches": HISTORICAL_DELETIONS,
            "must_not_reuse_historical_line_numbers": True,
        },
        "page_and_interaction_scope": {
            "frontend_page_count": frontend_manifest.get("page_count"),
            "frontend_pages_listed": len(frontend_manifest.get("pages", [])),
            "interaction_page_count": interaction_manifest.get("page_count"),
            "interaction_step_count": interaction_manifest.get("step_count_total"),
        },
        "candidate_usage": {
            name: usage[name]
            for name in sorted(candidates)
            if usage[name]
        },
        "rule_blocks": classified,
        "next_gate": {
            "next_action": "R1/R2 candidate review only after human selection",
            "deletion_authorized_by_this_report": False,
            "required_before_delete": [
                "review exact current rule-block manifest",
                "confirm every selector branch is dead",
                "confirm no dynamic/status/responsive/interaction dependency",
                "limit batch to 20 rule blocks",
            ],
        },
    }


def markdown_report(inventory: dict) -> str:
    current = inventory["current_state"]
    counts = current["decision_counts"]
    lines = [
        f"# TD-15 residual inventory（R0，{inventory['snapshot_date']}）",
        "",
        "本報告由 `regression/td15_residual_inventory.py` 重新解析目前工作樹產生。R0 只做現況盤點與歷史刪除對帳，**不刪除任何 CSS／JS，不更新 baseline**。",
        "",
        "## 結論",
        "",
        f"- 狀態：`{inventory['status']}`。分類快照為 {inventory['classification_snapshot']['css_class_candidates']} 個 CSS class、{inventory['classification_snapshot']['css_id_candidates']} 個 ID；ID 候選均列為不存在的獨立 selector。",
        f"- 目前重新解析到 {current['candidate_bearing_rule_blocks']} 個含候選 class 的 rule blocks，涉及 {current['current_candidate_name_count']} 個目前仍出現的候選名稱。",
        f"- 初步分流：`candidate-only-review` {counts.get('candidate-only-review', 0)}、`retain-grouped-or-compound-review` {counts.get('retain-grouped-or-compound-review', 0)}、`retain-dynamic-status-or-direct-reference` {counts.get('retain-dynamic-status-or-direct-reference', 0)}。這些是 R1/R2 review queue，不是刪除授權。",
        f"- 歷史 H-04-01～10 與 H-09-03 已記錄刪除 {inventory['historical_reconciliation']['recorded_deleted_rule_blocks']} 個 rule blocks；舊行號不可重用。",
        f"- Page／interaction scope：{inventory['page_and_interaction_scope']['frontend_page_count']} 頁、{inventory['page_and_interaction_scope']['interaction_step_count']} 條 interaction steps。",
        "",
        "## 歷史批次對帳",
        "",
        "| batch | file | blocks | selectors |",
        "|---|---|---:|---|",
    ]
    for item in inventory["historical_reconciliation"]["recorded_batches"]:
        lines.append(f"| {item['batch']} | `{item['file']}` | {item['blocks']} | `{item['selectors']}` |")
    lines.extend([
        "",
        "## 後續 gate",
        "",
        "1. 先人工選定一個不超過 20 個 rule blocks 的 queue，核對 manifest 中的 current file／line／hash。",
        "2. `candidate-only-review` 仍需補 CSS cascade、HTML／JS／Python literal、root JS dynamic pattern、responsive／state 與 21 頁／94 條證據。",
        "3. 任何 direct reference、dynamic prefix、status marker、grouped／compound branch 或 responsive context 都保留或降級觀察。",
        "4. 通過人工確認後才可使用 `delete_css_rules.py`；本 R0 報告本身不授權刪除。",
        "",
        "## Downstream closure（2026-09-01）",
        "",
        "REMAIN-04～07 已完成全量 263 blocks 的 review 與 closure。最終 disposition 為 `retain=263`、`observe=0`、`delete_candidate=0`、`blocked=0`；REMAIN-07 因無候選而採 no-op closure，未執行 CSS 刪除。詳見 `TD15_REMAIN_07_evidence_2026-09-01.md`。",
        "",
        "完整 machine-readable rule-block manifest 見同名 JSON。",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write JSON and Markdown reports")
    parser.add_argument("--check", action="store_true", help="rebuild and validate the R0 inventory")
    parser.add_argument(
        "--snapshot-date",
        default=DEFAULT_SNAPSHOT_DATE,
        help=f"snapshot date used in the report filenames (default: {DEFAULT_SNAPSHOT_DATE})",
    )
    args = parser.parse_args()
    try:
        date.fromisoformat(args.snapshot_date)
        json_output, md_output = artifact_paths(args.snapshot_date)
        inventory = build_inventory(args.snapshot_date)
        if inventory["page_and_interaction_scope"]["frontend_page_count"] != 21:
            raise ValueError("frontend manifest page count is not 21")
        if inventory["page_and_interaction_scope"]["interaction_step_count"] != 94:
            raise ValueError("interaction manifest step count is not 94")
        if args.write:
            json_output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
            md_output.write_text(markdown_report(inventory), encoding="utf-8", newline="")
        print(
            "TD15_R0_OK: "
            f"classified_css_classes={inventory['classification_snapshot']['css_class_candidates']} "
            f"current_candidate_blocks={inventory['current_state']['candidate_bearing_rule_blocks']} "
            f"candidate_only_review_blocks={inventory['current_state']['candidate_only_review_blocks']} "
            f"historical_deleted_blocks={inventory['historical_reconciliation']['recorded_deleted_rule_blocks']} "
            "deletion=0"
        )
        return 0
    except (OSError, ValueError, StopIteration, json.JSONDecodeError) as exc:
        print(f"TD15_R0_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
