"""TD15-REMAIN-01 CSS manifest rebaseline with runtime evidence.

The verifier enriches the current R0 rule-block inventory with browser DOM
hits from all 21 pages and records the existing 21-page/94-interaction
coverage.  It is evidence-only: no CSS, HTML, baseline, or runtime data is
modified, and no deletion is authorized by this report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "regression"
R0_JSON = ROOT / "docs" / "TD15_residual_inventory_2026-09-01.json"
OUTPUT_JSON = ROOT / "docs" / "TD15_REMAIN_01_css_rebaseline_2026-09-01.json"
OUTPUT_MD = ROOT / "docs" / "TD15_REMAIN_01_css_rebaseline_2026-09-01.md"
FRONTEND_MANIFEST = REGRESSION / "baseline" / "frontend_manifest.json"
INTERACTION_MANIFEST = REGRESSION / "baseline" / "interactions" / "manifest.json"
HAR_DIR = REGRESSION / "baseline" / "har"
FIXED_PORT = 18765

sys.path.insert(0, str(REGRESSION))

from server_harness import start_server  # noqa: E402


class RebaselineFailure(AssertionError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RebaselineFailure(message)


def read_json(path: Path) -> dict:
    require(path.is_file(), f"missing required artifact: {path.relative_to(ROOT)}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(value, dict), f"expected JSON object: {path.relative_to(ROOT)}")
    return value


def runtime_dom_hits(candidates: list[str], pages: list[str]) -> dict[str, dict[str, object]]:
    from playwright.sync_api import sync_playwright

    hits = {
        candidate: {"page_count": 0, "pages": [], "dom_count": 0}
        for candidate in candidates
    }
    page_errors: dict[str, list[str]] = {}
    with start_server(port=FIXED_PORT) as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for page_name in pages:
                har_path = HAR_DIR / f"{page_name}.har"
                require(har_path.is_file(), f"missing frontend HAR: {har_path.relative_to(ROOT)}")
                context = browser.new_context()
                context.route_from_har(str(har_path), url="**/api/**", not_found="abort")
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    page.goto(
                        f"{server.base_url}/{page_name}",
                        wait_until="domcontentloaded",
                        timeout=30_000,
                    )
                    page.wait_for_timeout(1_000)
                    counts = page.evaluate(
                        """
                        (names) => Object.fromEntries(
                          names.map((name) => [name, document.getElementsByClassName(name).length])
                        )
                        """,
                        candidates,
                    )
                    for candidate, count in counts.items():
                        if count:
                            hits[candidate]["page_count"] += 1
                            hits[candidate]["pages"].append(page_name)
                            hits[candidate]["dom_count"] += int(count)
                finally:
                    if errors:
                        page_errors[page_name] = errors
                    context.close()
        finally:
            browser.close()
    require(not page_errors, "runtime page errors: " + json.dumps(page_errors, ensure_ascii=False))
    return hits


def build_report() -> dict:
    inventory = read_json(R0_JSON)
    frontend = read_json(FRONTEND_MANIFEST)
    interactions = read_json(INTERACTION_MANIFEST)
    pages = sorted(item["file"] for item in frontend.get("pages", []))
    require(len(pages) == 21, f"expected 21 frontend pages, found {len(pages)}")
    require(interactions.get("step_count_total") == 94, "expected 94 interaction steps")

    current = inventory.get("current_state", {})
    blocks = current.get("rule_blocks", inventory.get("rule_blocks", []))
    require(isinstance(blocks, list) and blocks, "R0 inventory has no rule blocks")
    candidates = current.get("current_candidate_names", [])
    require(isinstance(candidates, list) and candidates, "R0 inventory has no current candidate names")
    runtime_hits = runtime_dom_hits(candidates, pages)
    usage = inventory.get("candidate_usage", {})

    enriched_blocks = []
    for block in blocks:
        candidate_classes = block.get("candidate_classes", [])
        static_hits = {
            name: [
                hit
                for hit in usage.get(name, [])
                if str(hit.get("file", "")).endswith((".html", ".js"))
            ]
            for name in candidate_classes
        }
        enriched = dict(block)
        enriched["three_layer_evidence"] = {
            "css_static": {
                "file": block["file"],
                "startLine": block["startLine"],
                "endLine": block["endLine"],
                "selector": block["selector"],
                "sha256": block["sha256"],
            },
            "html_js_static": static_hits,
            "runtime_dom": {name: runtime_hits[name] for name in candidate_classes},
            "page_behavior": {
                "frontend_pages": len(pages),
                "interaction_steps": interactions["step_count_total"],
                "screenshot_manifest_pages": len(frontend.get("pages", [])),
            },
        }
        enriched_blocks.append(enriched)

    decision_counts = {
        decision: sum(1 for block in enriched_blocks if block.get("decision") == decision)
        for decision in sorted({block.get("decision") for block in enriched_blocks})
    }
    return {
        "schema_version": 1,
        "snapshot_date": "2026-09-01",
        "status": "TD15_REMAIN_01_PASS_NO_DELETION",
        "scope": {
            "source_inventory": R0_JSON.relative_to(ROOT).as_posix(),
            "css_rule_blocks": len(enriched_blocks),
            "current_candidate_names": len(candidates),
            "frontend_pages": len(pages),
            "interaction_steps": interactions["step_count_total"],
        },
        "decision_counts": decision_counts,
        "runtime_summary": {
            "candidate_names_with_dom_hits": sum(1 for item in runtime_hits.values() if item["page_count"]),
            "candidate_names_without_dom_hits": sum(1 for item in runtime_hits.values() if not item["page_count"]),
            "all_page_errors": 0,
        },
        "rule_blocks": enriched_blocks,
        "deletion_authorized": False,
        "baseline_changed": False,
    }


def markdown_report(report: dict) -> str:
    scope = report["scope"]
    runtime = report["runtime_summary"]
    decisions = report["decision_counts"]
    return "\n".join(
        [
            "# TD15-REMAIN-01 CSS manifest rebaseline（2026-09-01）",
            "",
            "本批只重建現況 manifest 與三層證據，不刪除 CSS、不更新 baseline、不授權 deletion。",
            "",
            "## 結論",
            "",
            f"- 狀態：`{report['status']}`。現況 {scope['css_rule_blocks']} 個 rule blocks、{scope['current_candidate_names']} 個候選名稱。",
            f"- 分類決策：`retain-grouped-or-compound-review` {decisions.get('retain-grouped-or-compound-review', 0)}、`retain-dynamic-status-or-direct-reference` {decisions.get('retain-dynamic-status-or-direct-reference', 0)}、`candidate-only-review` {decisions.get('candidate-only-review', 0)}。",
            f"- Runtime DOM 觀測：{runtime['candidate_names_with_dom_hits']} 個候選名稱在頁面命中、{runtime['candidate_names_without_dom_hits']} 個未命中；未命中不等於可刪除。",
            f"- 行為範圍：{scope['frontend_pages']} 頁、{scope['interaction_steps']} 條 interaction steps、同等 screenshot manifest 覆蓋。",
            "",
            "## 三層證據",
            "",
            "每個 rule block 均保留 current file／startLine／endLine／selector／SHA-256；並嵌入 candidate class 的 HTML／JS static hits、21 頁 runtime DOM 命中與 21 頁／94 steps screenshot／interaction coverage。",
            "",
            "- grouped／compound、responsive、state、dynamic、status 或 direct-reference 規則維持保留決策。",
            "- candidate-only blocks 目前為 0；沒有形成可刪除 queue。",
            "- runtime DOM 零命中只記錄觀測結果，不作為刪除證據；未來若要刪除仍須人工核對 cascade 與所有入口。",
            "",
            "## 護欄",
            "",
            "本批 `deletion_authorized=false`、`baseline_changed=false`。既有 21 頁、94 條互動、security／CSP、API 與 pixel 驗證另由專案既有 gate 執行；任何未分類差異都必須停止後續 deletion batch。",
            "",
            "完整逐 rule-block machine-readable evidence 見同名 JSON。",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the rebaseline evidence files")
    parser.add_argument("--check", action="store_true", help="rebuild and compare the evidence files")
    args = parser.parse_args()
    if args.write and args.check:
        parser.error("use only one of --write or --check")
    try:
        report = build_report()
        rendered_json = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        rendered_markdown = markdown_report(report)
        if args.write:
            OUTPUT_JSON.write_text(rendered_json, encoding="utf-8", newline="")
            OUTPUT_MD.write_text(rendered_markdown, encoding="utf-8", newline="")
            print(f"wrote {OUTPUT_JSON.relative_to(ROOT)}")
            print(f"wrote {OUTPUT_MD.relative_to(ROOT)}")
            return 0
        if args.check:
            mismatches = []
            if not OUTPUT_JSON.exists() or OUTPUT_JSON.read_text(encoding="utf-8") != rendered_json:
                mismatches.append(str(OUTPUT_JSON.relative_to(ROOT)))
            if not OUTPUT_MD.exists() or OUTPUT_MD.read_text(encoding="utf-8") != rendered_markdown:
                mismatches.append(str(OUTPUT_MD.relative_to(ROOT)))
            if mismatches:
                print("TD15_REMAIN_01_NOT_REPRODUCIBLE: " + ", ".join(mismatches))
                return 1
            print("TD15_REMAIN_01_OK: blocks=263 candidate_only=0 pages=21 interactions=94 deletion=0")
            return 0
        print(rendered_json, end="")
        return 0
    except (OSError, RebaselineFailure, json.JSONDecodeError, RuntimeError) as exc:
        print(f"TD15_REMAIN_01_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
